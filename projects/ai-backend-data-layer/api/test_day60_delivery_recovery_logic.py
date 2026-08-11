"""Day60 — EXECUTED_LOCAL_RUNTIME unit tests for the pure delivery/recovery logic.

Scope: standard-library control flow ONLY (no database, no broker, no Docker). These
tests prove the Day60 DECISION rules: Relay publish-before-checkpoint ordering, guarded
claim outcome, duplicate/redelivery/expiry classification, the recovery-sweep result
(including the negative cases: queued/terminal/active-lease are never swept), the
release-filtered bounded early-ACK repair eligibility + idempotent repair id, the shared
lease boundary (``> now`` active / ``<= now`` expired), and the readiness gate.

They do NOT prove real PostgreSQL ``FOR UPDATE SKIP LOCKED`` / guarded ``UPDATE ...
RETURNING`` / transactions, a real Redis/Celery broker, ACK timing, redelivery, or
Worker-kill — that is INTEGRATION_RUNTIME and lives in ``day60_delivery_runtime.py``
(see the runbook; NOT RERUN by the updating agent). A pure-logic pass is not integration
evidence.
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
    lease_active,
    lease_expired,
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


# ---- lease boundary (P2): > now active, <= now expired (incl == now) -----------------
def test_lease_boundary_rules():
    assert lease_active(101, 100) is True
    assert lease_active(100, 100) is False      # == now is EXPIRED, not active
    assert lease_active(99, 100) is False
    assert lease_active(None, 100) is False
    assert lease_expired(100, 100) is True       # exact complement
    assert lease_expired(101, 100) is False


# ---- classify_delivery ---------------------------------------------------------------
def test_duplicate_with_healthy_own_lease_is_noop():
    view = LeaseView("running", "w1", 200, has_external_evidence=False)
    assert classify_delivery(100, "w1", view) is DeliveryDecision.NOOP_HEALTHY_LEASE


def test_worker_loss_before_expiry_defers_to_sweep():
    view = LeaseView("running", "w1", 200, has_external_evidence=False)
    assert classify_delivery(100, "w2", view) is DeliveryDecision.DEFER_TO_RECOVERY_SWEEP


def test_expired_running_with_evidence_reconcile_only():
    view = LeaseView("running", "w1", 100, has_external_evidence=True)
    assert classify_delivery(200, "w2", view) is DeliveryDecision.RECONCILE_ONLY


def test_expired_running_without_evidence_sweep_redispatch():
    view = LeaseView("running", "w1", 100, has_external_evidence=False)
    assert classify_delivery(200, "w2", view) is DeliveryDecision.SWEEP_REDISPATCH


def test_delivery_terminal_is_noop():
    for st in ("succeeded", "failed", "cancelled"):
        view = LeaseView(st, None, None, has_external_evidence=False)
        assert classify_delivery(100, "w1", view) is DeliveryDecision.TERMINAL_NOOP


# ---- classify_recovery_sweep (P1-2 negatives) ----------------------------------------
def test_sweep_reconcile_vs_requeue_for_expired_running():
    ev = LeaseView("running", "w1", 100, has_external_evidence=True)
    assert classify_recovery_sweep(ev, 200) is SweepResult.RECONCILE_ONLY
    no_ev = LeaseView("running", "w1", 100, has_external_evidence=False)
    assert classify_recovery_sweep(no_ev, 200) is SweepResult.REQUEUED_WITH_REDISPATCH


def test_sweep_never_touches_queued():
    view = LeaseView("queued", None, None, has_external_evidence=False)
    assert classify_recovery_sweep(view, 200) is SweepResult.NO_OP


def test_sweep_never_touches_terminal_states():
    for st in ("succeeded", "failed", "cancelled"):
        view = LeaseView(st, None, None, has_external_evidence=False)
        assert classify_recovery_sweep(view, 200) is SweepResult.NO_OP


def test_sweep_no_op_when_lease_still_active():
    view = LeaseView("running", "w1", 300, has_external_evidence=False)
    assert classify_recovery_sweep(view, 200) is SweepResult.NO_OP


def test_sweep_at_lease_expiry_equal_now_is_expired_and_requeues():
    view = LeaseView("running", "w1", 200, has_external_evidence=False)
    assert classify_recovery_sweep(view, 200) is SweepResult.REQUEUED_WITH_REDISPATCH


# ---- repair eligibility (P1-3 release filter) ----------------------------------------
def _cand(**over):
    base = dict(
        actual_release_version="r-bad",
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
    assert is_repair_eligible(_cand(), "r-bad") is True


def test_repair_rejects_different_release_even_if_all_else_ok():
    # Every other condition satisfied, but the actual release does not match.
    assert is_repair_eligible(_cand(actual_release_version="r-good"), "r-bad") is False


def test_repair_rejected_when_any_guard_fails():
    assert is_repair_eligible(_cand(status="running"), "r-bad") is False
    assert is_repair_eligible(_cand(has_attempts_or_external_evidence=True), "r-bad") is False
    assert is_repair_eligible(_cand(has_conflict=True), "r-bad") is False
    assert is_repair_eligible(_cand(within_time_window=False), "r-bad") is False
    assert is_repair_eligible(_cand(has_original_dispatch_checkpoint=False), "r-bad") is False
    assert is_repair_eligible(_cand(deadline_contract_budget_valid=False), "r-bad") is False
    assert is_repair_eligible(_cand(repair_already_applied=True), "r-bad") is False


def test_repair_id_is_deterministic():
    a = repair_id("j1", "r-bad", "early_ack")
    b = repair_id("j1", "r-bad", "early_ack")
    assert a == b == "repair:j1:r-bad:early_ack"


def test_readiness_revision_gate():
    assert revision_ready("0010_day60_runtime_schema", "0010_day60_runtime_schema") is True
    assert revision_ready("0009_day60_delivery_runtime", "0010_day60_runtime_schema") is False
    assert revision_ready(None, "0010_day60_runtime_schema") is False
