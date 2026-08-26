import os
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from provider_contract import (  # noqa: E402
    AttemptExecutionContract,
    CapabilityProfile,
    ProfileStatus,
    VerificationTier,
)
from recovery_cost import (  # noqa: E402
    AttemptCost,
    BatchItemCostStatus,
    CostStatus,
    ExecutionCertainty,
    FailureClass,
    FallbackPolicy,
    IncidentRecoveryEvidence,
    RecoveryAction,
    mark_unknown,
    may_close_incident,
    plan_recovery,
    record_batch_cost,
    settle,
)
from routing_policy import (  # noqa: E402
    Candidate,
    LatencyEvidence,
    PricingEvidence,
    RoutingPolicy,
    route,
)


def profile(profile_id, contracts=frozenset({"research.v1"})):
    return CapabilityProfile(
        profile_id,
        f"provider-{profile_id}",
        f"model-{profile_id}",
        "api.v1",
        "profile.v1",
        "adapter.v1",
        contracts,
        True,
        VerificationTier.EXECUTED_LOCAL_RUNTIME,
    )


def candidate(
    profile_id,
    *,
    contracts=frozenset({"research.v1"}),
    p95=7_000,
    cost=5,
    observed=900,
    status=ProfileStatus.ACTIVE,
):
    item = profile(profile_id, contracts)
    return Candidate(
        item,
        status,
        LatencyEvidence(profile_id, "PROVIDER_COMPLETE", p95, observed, 200),
        PricingEvidence(profile_id, "pricing.v1", cost, observed, 200),
    )


ROUTE_POLICY = RoutingPolicy("route", "v1", ("A", "C"), 8_000, 6)
SOURCE = AttemptExecutionContract.plan(
    "A1", "job-1", profile("C"), "research.v1"
)
FALLBACK_POLICY = FallbackPolicy(
    "v1",
    3,
    10,
    (
        FailureClass.RATE_LIMITED,
        FailureClass.TRANSPORT_BEFORE_DISPATCH,
        FailureClass.OUTPUT_INVALID,
    ),
)


class Day76Tests(unittest.TestCase):
    def routed(self, items, selector=None):
        return route(
            job_id="job-1",
            attempt_id="A1",
            application_contract="research.v1",
            policy=ROUTE_POLICY,
            candidates=items,
            now_ms=1_000,
            client_selector=selector,
        )

    def recovery(self, **changes):
        values = dict(
            source=SOURCE,
            failure=FailureClass.RATE_LIMITED,
            certainty=ExecutionCertainty.DEFINITELY_NOT_ACCEPTED,
            policy=FALLBACK_POLICY,
            attempt_count=1,
            remaining_deadline_ms=5_000,
            job_cost_and_reservations=4,
            target_estimated_cost=5,
            target=profile("D"),
            target_current_status=ProfileStatus.ACTIVE,
            new_attempt_id="A2",
        )
        values.update(changes)
        return plan_recovery(**values)

    def test_incompatible_excluded_before_preference(self):
        decision, binding = self.routed(
            [candidate("A", contracts=frozenset(), p95=1, cost=1), candidate("C")]
        )
        self.assertEqual((decision.selected_profile_id, binding.profile_id), ("C", "C"))

    def test_client_selector_cannot_choose_disabled(self):
        decision, _ = self.routed(
            [candidate("A"), candidate("C", status=ProfileStatus.DISABLED)], "C"
        )
        self.assertEqual(decision.selected_profile_id, "A")

    def test_client_selector_may_choose_allowed_eligible(self):
        decision, _ = self.routed([candidate("A"), candidate("C")], "C")
        self.assertEqual(decision.selected_profile_id, "C")

    def test_latency_gate_precedes_lower_cost(self):
        decision, _ = self.routed(
            [candidate("A", p95=10_000, cost=2), candidate("C")]
        )
        self.assertEqual(decision.selected_profile_id, "C")

    def test_stale_pricing_fails_closed(self):
        decision, binding = self.routed([candidate("A", observed=700)])
        self.assertIsNone(binding)
        self.assertIn("PRICING_STALE", decision.candidate_decisions[0].reasons)

    def test_binding_and_decision_are_frozen(self):
        decision, binding = self.routed([candidate("A")])
        with self.assertRaises(FrozenInstanceError):
            decision.selected_profile_id = "C"
        with self.assertRaises(FrozenInstanceError):
            binding.profile_id = "C"

    def test_definitely_not_accepted_creates_new_fallback_attempt(self):
        decision, binding = self.recovery()
        self.assertIs(decision.action, RecoveryAction.FALLBACK_NEW_ATTEMPT)
        self.assertEqual((binding.attempt_id, binding.profile_id), ("A2", "D"))

    def test_timeout_unknown_reconciles_without_new_attempt(self):
        decision, binding = self.recovery(
            certainty=ExecutionCertainty.TIMEOUT_UNKNOWN
        )
        self.assertIs(decision.action, RecoveryAction.RECONCILE)
        self.assertIsNone(binding)

    def test_unauthorized_rejects(self):
        decision, _ = self.recovery(failure=FailureClass.UNAUTHORIZED)
        self.assertIs(decision.action, RecoveryAction.REJECT)

    def test_auth_configuration_disables_path(self):
        decision, _ = self.recovery(failure=FailureClass.AUTH_OR_CONFIGURATION)
        self.assertIs(decision.action, RecoveryAction.DISABLE_PATH)

    def test_budget_attempt_and_target_eligibility_block_fallback(self):
        self.assertIs(
            self.recovery(job_cost_and_reservations=6, target_estimated_cost=5)[0].action,
            RecoveryAction.FALLBACK_EXHAUSTED,
        )
        self.assertIs(
            self.recovery(attempt_count=3)[0].action,
            RecoveryAction.FALLBACK_EXHAUSTED,
        )
        self.assertIs(
            self.recovery(target_current_status=ProfileStatus.QUARANTINED)[0].action,
            RecoveryAction.FALLBACK_EXHAUSTED,
        )

    def test_settlement_releases_reservation(self):
        result = settle(
            AttemptCost("A1", "pricing.v2", 4, 5),
            pricing_revision="pricing.v2",
            actual=3,
        )
        self.assertEqual(
            (result.actual, result.released, result.status),
            (3, 2, CostStatus.SETTLED),
        )

    def test_historical_attempt_cannot_use_current_default_pricing(self):
        with self.assertRaises(ValueError):
            settle(
                AttemptCost("A1", "pricing.v2", 4, 5),
                pricing_revision="pricing.v3",
                actual=3,
            )

    def test_timeout_unknown_keeps_reservation_and_unknown_actual(self):
        result = mark_unknown(AttemptCost("A1", "pricing.v2", 4, 5))
        self.assertEqual(
            (result.actual, result.released, result.status),
            (None, 0, CostStatus.PENDING_RECONCILIATION),
        )

    def test_batch_total_does_not_invent_equal_item_actuals(self):
        result = record_batch_cost(("i1", "i2", "i3"), 9)
        self.assertTrue(
            all(
                item.units is None
                and item.status is BatchItemCostStatus.UNKNOWN
                for item in result
            )
        )

    def test_exact_per_item_cost_must_match_total(self):
        result = record_batch_cost(
            ("i1", "i2"), 7, (("i1", 3), ("i2", 4))
        )
        self.assertEqual([item.units for item in result], [3, 4])
        with self.assertRaises(ValueError):
            record_batch_cost(("i1", "i2"), 7, (("i1", -1), ("i2", 8)))

    def test_policy_rollback_alone_cannot_close_incident(self):
        evidence = IncidentRecoveryEvidence(
            True, True, True, False, False, False, False, False, True
        )
        self.assertFalse(may_close_incident(evidence))

    def test_all_recovery_evidence_may_close_incident(self):
        evidence = IncidentRecoveryEvidence(
            True, True, True, True, True, True, True, True, True
        )
        self.assertTrue(may_close_incident(evidence))


if __name__ == "__main__":
    unittest.main()
