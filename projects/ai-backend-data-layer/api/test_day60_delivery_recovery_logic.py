"""Day60 — EXECUTED_LOCAL_RUNTIME unit tests for the pure delivery/recovery logic.

Scope: standard-library control flow ONLY (no database, no broker, no Docker). These
tests prove the Day60 DECISION rules: Relay publish-before-checkpoint ordering, guarded
claim outcome, duplicate/redelivery/expiry classification, recovery-sweep result, the
bounded early-ACK repair eligibility predicate + idempotent repair id, and the readiness
revision gate.

They do NOT prove real PostgreSQL ``FOR UPDATE SKIP LOCKED`` / guarded ``UPDATE ...
RETURNING`` / transactions, a real Redis/Celery broker, ACK timing, redelivery, or
Worker-kill — that is INTEGRATION_RUNTIME (see the runbook). A pure-logic pass is not
integration evidence.
"""

from day60_delivery_recovery_logic import (
    ClaimOutcome,
    DeliveryDecision,
    LeaseView,
    RelayStep,
    RepairCandidate,
    SweepResult,
    classify_delivery,
    classify_guarded_claim,
    classify_recovery_sweep,
    is_repair_eligible,
    relay_publish_order,
    repair_id,
    revision_ready,
)


def test_relay_publishes_before_checkpoint():
    first, second = relay_publish_order()
    assert first is RelayStep.PUBLISH_TO_BROKER
    assert second is RelayStep.GUARDED_CHECKPOINT


def test_guarded_claim_single_winner():
    assert classify_guarded_claim(1) is ClaimOutcome.WON
    assert classify_guarded_claim(0) is ClaimOutcome.LOST


def test_duplicate_with_healthy_own_lease_is_noop():
    view = LeaseView("running", "w1", 100, has_external_evidence=False)
    assert classify_delivery(50, "w1", view) is DeliveryDecision.NOOP_HEALTHY_LEASE


def test_worker_loss_before_expiry_defers_to_sweep():
    view = LeaseView("running", "w1", 100, has_external_evidence=False)
    # A different worker sees a still-valid lease -> do not seize; defer.
    assert classify_delivery(50, "w2", view) is DeliveryDecision.DEFER_TO_RECOVERY_SWEEP


def test_expired_with_external_evidence_reconcile_only():
    view = LeaseView("running", "w1", 100, has_external_evidence=True)
    assert classify_delivery(200, "w2", view) is DeliveryDecision.RECONCILE_ONLY


def test_expired_without_evidence_sweep_redispatch():
    view = LeaseView("running", "w1", 100, has_external_evidence=False)
    assert classify_delivery(200, "w2", view) is DeliveryDecision.SWEEP_REDISPATCH


def test_recovery_sweep_reconcile_vs_requeue():
    ev = LeaseView("running", "w1", 100, has_external_evidence=True)
    assert classify_recovery_sweep(ev, 200) is SweepResult.RECONCILE_ONLY
    no_ev = LeaseView("running", "w1", 100, has_external_evidence=False)
    assert classify_recovery_sweep(no_ev, 200) is SweepResult.REQUEUED_WITH_REDISPATCH


def test_repair_id_is_deterministic():
    a = repair_id("j1", "r-bad", "early_ack")
    b = repair_id("j1", "r-bad", "early_ack")
    assert a == b == "repair:j1:r-bad:early_ack"


def _base_candidate(**over):
    base = dict(
        bad_release_version="r-bad",
        within_time_window=True,
        status="queued",
        has_original_dispatch_checkpoint=True,
        has_attempts_or_external_evidence=False,
        has_conflict=False,
        deadline_contract_budget_valid=True,
        repair_already_applied=False,
    )
    base.update(over)
    return RepairCandidate(**base)


def test_repair_eligible_happy_path():
    assert is_repair_eligible(_base_candidate()) is True


def test_repair_rejected_when_any_guard_fails():
    assert is_repair_eligible(_base_candidate(status="running")) is False
    assert is_repair_eligible(_base_candidate(has_attempts_or_external_evidence=True)) is False
    assert is_repair_eligible(_base_candidate(has_conflict=True)) is False
    assert is_repair_eligible(_base_candidate(within_time_window=False)) is False
    assert is_repair_eligible(_base_candidate(has_original_dispatch_checkpoint=False)) is False
    assert is_repair_eligible(_base_candidate(deadline_contract_budget_valid=False)) is False
    assert is_repair_eligible(_base_candidate(repair_already_applied=True)) is False


def test_readiness_revision_gate():
    assert revision_ready("0009_day60_delivery_runtime", "0009_day60_delivery_runtime") is True
    assert revision_ready("0008_day59_acceptance", "0009_day60_delivery_runtime") is False
    assert revision_ready(None, "0009_day60_delivery_runtime") is False
