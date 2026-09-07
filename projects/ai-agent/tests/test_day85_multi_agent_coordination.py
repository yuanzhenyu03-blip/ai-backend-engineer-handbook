"""Day85 first-increment deterministic coordination tests."""
from dataclasses import replace
import unittest

from multi_agent_coordination import (
    AcceptanceStatus,
    AggregationStatus,
    CancellationStatus,
    ChildResultCandidate,
    ClaimStatus,
    CurrentCoordinationFacts,
    DispatchStatus,
    FakeWorker,
    FakeWorkerMode,
    HandoffCandidate,
    InMemoryCoordinationStore,
    ResultVerificationStatus,
    WorkerRequest,
)


class Day85CoordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCoordinationStore(
            parent_job_id="parent-1", parent_token_reservation=9_000,
        )
        self.facts = CurrentCoordinationFacts(
            tenant_id="tenant-a",
            delegatable_capabilities=("read_sources.v1", "check_claims.v1"),
            currently_allowed_capabilities=(
                "read_sources.v1", "check_claims.v1",
            ),
            accepted_output_contracts=("evidence_candidate.v1",),
            readable_context_manifests=("context-1",),
            current_policy_version="handoff-policy-v1",
            max_delegation_depth=2,
            max_fan_out=10,
            concurrency_limit=10,
        )

    def candidate(self, handoff_id: str = "handoff-1", **changes: object) -> HandoffCandidate:
        values: dict[str, object] = {
            "tenant_id": "tenant-a",
            "parent_job_id": "parent-1",
            "parent_attempt_id": "parent-attempt-1",
            "parent_step_id": "parent-step-1",
            "handoff_id": handoff_id,
            "idempotency_key": f"idem-{handoff_id}",
            "policy_version": "handoff-policy-v1",
            "objective": "collect scoped evidence",
            "input_contract": "research_input.v1",
            "output_contract": "evidence_candidate.v1",
            "context_manifest_id": "context-1",
            "context_source_versions": (("source-a", 3),),
            "requested_capabilities": ("read_sources.v1",),
            "requested_tokens": 4_000,
            "receiver_role": "source_research",
            "aggregation_slot": "source-evidence",
            "required": True,
            "deadline": 100,
        }
        values.update(changes)
        return HandoffCandidate(**values)

    def accept(self, candidate: HandoffCandidate | None = None):
        return self.store.accept(
            candidate or self.candidate(), facts=self.facts, now=10,
        )

    def dispatch(self, handoff_id: str = "handoff-1", *, worker: str = "worker-a"):
        claim = self.store.claim(
            handoff_id, worker_id=worker, now=20, lease_duration=20,
        )
        decision = self.store.record_provider_dispatch(
            handoff_id, worker_id=worker, fence_token=claim.fence_token,
            required_capability="read_sources.v1",
            current_allowed_capabilities=("read_sources.v1",),
            operation_id=f"operation-{handoff_id}", now=21,
        )
        self.assertEqual(decision.status, DispatchStatus.ALLOWED)
        return claim

    def result(
        self, handoff_id: str = "handoff-1", *, worker: str = "worker-a",
        fence: int = 1, fact_value: str = "confirmed",
    ) -> ChildResultCandidate:
        record = self.store.get(handoff_id)
        return ChildResultCandidate(
            result_id=f"result-{handoff_id}", handoff_id=handoff_id,
            child_attempt_id=record.child_attempt_id, worker_id=worker,
            fence_token=fence,
            output_contract=record.candidate.output_contract,
            source_versions=record.candidate.context_source_versions,
            evidence_reference=f"evidence-{handoff_id}",
            completeness="COMPLETE", fact_key="claim-a",
            fact_value=fact_value,
        )

    def test_scoped_candidate_is_accepted_with_minimal_grant(self) -> None:
        decision = self.accept()
        self.assertEqual(decision.status, AcceptanceStatus.ACCEPTED)
        self.assertEqual(
            decision.record.grant.capabilities, ("read_sources.v1",),
        )
        self.assertEqual(decision.record.allocation.reserved_tokens, 4_000)

    def test_cross_tenant_candidate_is_rejected_before_acceptance(self) -> None:
        decision = self.accept(self.candidate(tenant_id="tenant-b"))
        self.assertEqual(decision.status, AcceptanceStatus.SCOPE_MISMATCH)
        self.assertEqual(self.store.allocated_tokens, 0)

    def test_supervisor_cannot_delegate_publish_capability(self) -> None:
        decision = self.accept(self.candidate(
            requested_capabilities=("publish_research_report.v1",),
        ))
        self.assertEqual(
            decision.status, AcceptanceStatus.CAPABILITY_NOT_DELEGATABLE,
        )

    def test_current_permission_must_also_allow_delegation(self) -> None:
        facts = replace(self.facts, currently_allowed_capabilities=())
        decision = self.store.accept(self.candidate(), facts=facts, now=10)
        self.assertEqual(
            decision.status,
            AcceptanceStatus.CAPABILITY_NOT_CURRENTLY_ALLOWED,
        )

    def test_same_identity_and_fingerprint_is_duplicate(self) -> None:
        first = self.accept()
        second = self.accept()
        self.assertEqual(first.status, AcceptanceStatus.ACCEPTED)
        self.assertEqual(second.status, AcceptanceStatus.DUPLICATE)
        self.assertIs(second.record, first.record)
        self.assertEqual(self.store.allocated_tokens, 4_000)
        self.assertEqual(len(self.store.unpublished_outbox_intents), 1)

    def test_same_identity_with_new_objective_is_semantic_conflict(self) -> None:
        first = self.accept()
        conflict = self.accept(self.candidate(objective="publish the report"))
        self.assertEqual(conflict.status, AcceptanceStatus.SEMANTIC_CONFLICT)
        self.assertIs(conflict.record, first.record)
        self.assertEqual(self.store.allocated_tokens, 4_000)

    def test_missing_output_contract_is_rejected(self) -> None:
        decision = self.accept(self.candidate(output_contract="unknown.v9"))
        self.assertEqual(
            decision.status, AcceptanceStatus.OUTPUT_CONTRACT_REJECTED,
        )

    def test_unreadable_context_is_rejected(self) -> None:
        decision = self.accept(self.candidate(context_manifest_id="revoked"))
        self.assertEqual(decision.status, AcceptanceStatus.CONTEXT_REJECTED)

    def test_three_four_thousand_allocations_cannot_copy_nine_thousand(self) -> None:
        self.assertEqual(self.accept(self.candidate("handoff-a")).status,
                         AcceptanceStatus.ACCEPTED)
        self.assertEqual(self.accept(self.candidate("handoff-b")).status,
                         AcceptanceStatus.ACCEPTED)
        third = self.accept(self.candidate("handoff-c"))
        self.assertEqual(third.status, AcceptanceStatus.BUDGET_EXCEEDED)
        self.assertEqual(self.store.allocated_tokens, 8_000)

    def test_depth_limit_rejects_recursive_worker_candidate(self) -> None:
        decision = self.accept(self.candidate(delegation_depth=3))
        self.assertEqual(
            decision.status, AcceptanceStatus.DELEGATION_DEPTH_EXCEEDED,
        )
        self.assertEqual(self.store.allocated_tokens, 0)

    def test_fan_out_limit_is_independent_of_budget(self) -> None:
        facts = replace(self.facts, max_fan_out=1)
        first = self.store.accept(
            self.candidate("handoff-a", requested_tokens=1_000),
            facts=facts, now=10,
        )
        second = self.store.accept(
            self.candidate("handoff-b", requested_tokens=1_000),
            facts=facts, now=10,
        )
        self.assertEqual(first.status, AcceptanceStatus.ACCEPTED)
        self.assertEqual(second.status, AcceptanceStatus.FAN_OUT_EXCEEDED)

    def test_concurrency_limit_is_independent_of_budget(self) -> None:
        facts = replace(self.facts, concurrency_limit=1)
        first = self.store.accept(
            self.candidate("handoff-a", requested_tokens=1_000),
            facts=facts, now=10,
        )
        second = self.store.accept(
            self.candidate("handoff-b", requested_tokens=1_000),
            facts=facts, now=10,
        )
        self.assertEqual(first.status, AcceptanceStatus.ACCEPTED)
        self.assertEqual(
            second.status, AcceptanceStatus.CONCURRENCY_LIMIT_REACHED,
        )

    def test_outbox_publish_does_not_create_claim(self) -> None:
        self.accept()
        self.assertTrue(self.store.mark_outbox_published(
            "handoff-1", published_at=15,
        ))
        record = self.store.get("handoff-1")
        self.assertIsNotNone(record.outbox_intent.published_at)
        self.assertIsNone(record.claim_owner)

    def test_message_receipt_without_claim_cannot_dispatch(self) -> None:
        self.accept()
        decision = self.store.authorize_provider_dispatch(
            "handoff-1", worker_id="worker-a", fence_token=0,
            required_capability="read_sources.v1",
            current_allowed_capabilities=("read_sources.v1",), now=20,
        )
        self.assertEqual(decision.status, DispatchStatus.HANDOFF_NOT_CLAIMED)
        self.assertEqual(decision.provider_calls, 0)

    def test_worker_can_claim_when_receiver_crashed_before_claim(self) -> None:
        self.accept()
        claim = self.store.claim(
            "handoff-1", worker_id="worker-b", now=20,
            lease_duration=10,
        )
        self.assertEqual(claim.status, ClaimStatus.CLAIMED)
        self.assertEqual(claim.owner, "worker-b")

    def test_duplicate_claim_returns_recorded_ownership(self) -> None:
        self.accept()
        first = self.store.claim(
            "handoff-1", worker_id="worker-a", now=20,
            lease_duration=10,
        )
        duplicate = self.store.claim(
            "handoff-1", worker_id="worker-a", now=21,
            lease_duration=10,
        )
        self.assertEqual(duplicate.status, ClaimStatus.DUPLICATE)
        self.assertEqual(duplicate.fence_token, first.fence_token)

    def test_live_lease_cannot_be_taken_over(self) -> None:
        self.accept()
        self.store.claim(
            "handoff-1", worker_id="worker-a", now=20,
            lease_duration=10,
        )
        takeover = self.store.take_over_expired_lease(
            "handoff-1", worker_id="worker-b", now=29,
            lease_duration=10,
        )
        self.assertEqual(takeover.status, ClaimStatus.HANDOFF_NOT_CLAIMABLE)

    def test_takeover_advances_fence_and_old_worker_cannot_dispatch(self) -> None:
        self.accept()
        old = self.store.claim(
            "handoff-1", worker_id="worker-a", now=20,
            lease_duration=10,
        )
        new = self.store.take_over_expired_lease(
            "handoff-1", worker_id="worker-b", now=30,
            lease_duration=10,
        )
        self.assertGreater(new.fence_token, old.fence_token)
        denied = self.store.authorize_provider_dispatch(
            "handoff-1", worker_id="worker-a",
            fence_token=old.fence_token,
            required_capability="read_sources.v1",
            current_allowed_capabilities=("read_sources.v1",), now=31,
        )
        self.assertEqual(denied.status, DispatchStatus.STALE_FENCE)
        self.assertEqual(denied.provider_calls, 0)

    def test_dispatch_rechecks_current_authorization(self) -> None:
        self.accept()
        claim = self.store.claim(
            "handoff-1", worker_id="worker-a", now=20,
            lease_duration=10,
        )
        denied = self.store.authorize_provider_dispatch(
            "handoff-1", worker_id="worker-a",
            fence_token=claim.fence_token,
            required_capability="read_sources.v1",
            current_allowed_capabilities=(), now=21,
        )
        self.assertEqual(
            denied.status, DispatchStatus.CURRENT_AUTHORIZATION_DENIED,
        )
        self.assertEqual(denied.provider_calls, 0)

    def test_current_source_version_must_match_result_binding(self) -> None:
        self.accept()
        claim = self.dispatch()
        decision = self.store.verify_result(
            self.result(fence=claim.fence_token),
            current_source_versions=(("source-a", 4),),
        )
        self.assertEqual(
            decision.status, ResultVerificationStatus.SOURCE_VERSION_STALE,
        )
        self.assertFalse(decision.applied_to_current_state)

    def test_verified_result_is_still_not_parent_completion(self) -> None:
        self.accept()
        claim = self.dispatch()
        decision = self.store.verify_result(
            self.result(fence=claim.fence_token),
            current_source_versions=(("source-a", 3),),
        )
        self.assertEqual(decision.status, ResultVerificationStatus.VERIFIED)
        aggregation = self.store.aggregate()
        self.assertEqual(aggregation.status, AggregationStatus.READY)
        self.assertFalse(aggregation.parent_completed)

    def test_parent_terminal_late_result_is_evidence_only(self) -> None:
        self.accept()
        claim = self.dispatch()
        self.store.parent_terminal = True
        decision = self.store.verify_result(
            self.result(fence=claim.fence_token),
            current_source_versions=(("source-a", 3),),
        )
        self.assertEqual(
            decision.status, ResultVerificationStatus.PARENT_TERMINAL,
        )
        self.assertFalse(decision.applied_to_current_state)
        self.assertFalse(self.store.result_evidence[-1].applied_to_current_state)

    def test_unknown_outcome_keeps_original_operation_and_allocation_held(self) -> None:
        self.accept()
        self.dispatch()
        self.assertTrue(self.store.mark_outcome_unknown(
            "handoff-1", operation_id="operation-handoff-1",
        ))
        record = self.store.get("handoff-1")
        self.assertEqual(record.state.value, "PENDING_RECONCILIATION")
        self.assertEqual(record.operation_id, "operation-handoff-1")
        self.assertEqual(record.allocation.status, "HELD")

    def test_parent_cancel_releases_undispatched_child(self) -> None:
        self.accept()
        decision = self.store.cancel("handoff-1")
        self.assertEqual(
            decision.status, CancellationStatus.CANCELLED_BEFORE_DISPATCH,
        )
        self.assertEqual(decision.allocation_status, "RELEASED")
        self.assertEqual(self.store.allocated_tokens, 0)

    def test_parent_cancel_after_dispatch_keeps_allocation_held(self) -> None:
        self.accept()
        self.dispatch()
        decision = self.store.cancel("handoff-1")
        self.assertEqual(
            decision.status,
            CancellationStatus.COOPERATIVE_CANCELLATION_PENDING,
        )
        self.assertEqual(decision.allocation_status, "HELD")

    def test_required_child_blocks_fan_in(self) -> None:
        self.accept()
        aggregation = self.store.aggregate()
        self.assertEqual(
            aggregation.status, AggregationStatus.WAITING_FOR_REQUIRED,
        )
        self.assertFalse(aggregation.parent_completed)

    def test_optional_missing_produces_explicit_partial(self) -> None:
        self.accept(self.candidate("required"))
        self.accept(self.candidate(
            "optional", required=False, requested_tokens=1_000,
            aggregation_slot="optional-check",
        ))
        claim = self.dispatch("required")
        self.store.verify_result(
            self.result("required", fence=claim.fence_token),
            current_source_versions=(("source-a", 3),),
        )
        aggregation = self.store.aggregate()
        self.assertEqual(aggregation.status, AggregationStatus.PARTIAL)
        self.assertEqual(aggregation.required_verified, 1)
        self.assertEqual(aggregation.optional_verified, 0)

    def test_conflicting_verified_facts_block_fan_in(self) -> None:
        self.accept(self.candidate("handoff-a"))
        self.accept(self.candidate(
            "handoff-b", requested_tokens=4_000,
            aggregation_slot="fact-check",
        ))
        first_claim = self.dispatch("handoff-a", worker="worker-a")
        second_claim = self.dispatch("handoff-b", worker="worker-b")
        self.store.verify_result(
            self.result(
                "handoff-a", worker="worker-a",
                fence=first_claim.fence_token, fact_value="true",
            ), current_source_versions=(("source-a", 3),),
        )
        self.store.verify_result(
            self.result(
                "handoff-b", worker="worker-b",
                fence=second_claim.fence_token, fact_value="false",
            ), current_source_versions=(("source-a", 3),),
        )
        aggregation = self.store.aggregate()
        self.assertEqual(aggregation.status, AggregationStatus.CONFLICT)
        self.assertFalse(aggregation.parent_completed)

    def test_fake_worker_failure_modes_are_explicit(self) -> None:
        request = WorkerRequest(
            "handoff-1", "child-attempt-1", "research", 1,
        )
        expected = {
            FakeWorkerMode.SUCCESS: ("RESULT_CANDIDATE", 1),
            FakeWorkerMode.FAILURE: ("FAILED", 1),
            FakeWorkerMode.CRASH_BEFORE_CLAIM: ("CRASHED_BEFORE_CLAIM", 0),
            FakeWorkerMode.DELAYED: ("DELAYED", 0),
            FakeWorkerMode.OUTCOME_UNKNOWN: ("PENDING_RECONCILIATION", 1),
            FakeWorkerMode.CONFLICT: ("RESULT_CANDIDATE", 1),
        }
        for mode, facts in expected.items():
            with self.subTest(mode=mode):
                outcome = FakeWorker(mode).execute(request)
                self.assertEqual((outcome.status, outcome.fake_provider_calls), facts)


if __name__ == "__main__":
    unittest.main()
