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
    RepairFact,
    classify_recovery_sweep,
    classify_repair_integrity,
    in_time_window,
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


def test_in_time_window_predicate_is_bounded():
    # Bounded window [100,200]; None (no persisted time fact) is NEVER in-window.
    assert in_time_window(150, 100, 200) is True
    assert in_time_window(100, 100, 200) is True     # inclusive start
    assert in_time_window(200, 100, 200) is True     # inclusive end
    assert in_time_window(99, 100, 200) is False
    assert in_time_window(201, 100, 200) is False
    assert in_time_window(None, 100, 200) is False   # unknown time -> rejected (not hardcoded True)
    assert in_time_window(150, 200, 100) is False    # inverted window -> rejected


def test_repair_rejected_outside_time_window():
    # Every other condition satisfied, but the candidate is out of the incident window.
    assert is_repair_eligible(_cand(within_time_window=False), "r-bad") is False


def test_repair_rejected_when_attestation_denies_conflict_or_budget():
    # has_conflict / deadline_contract_budget_valid come from the caller attestation; a
    # denied attestation (conflict present, or budget invalid) rejects the repair.
    assert is_repair_eligible(_cand(has_conflict=True), "r-bad") is False
    assert is_repair_eligible(_cand(deadline_contract_budget_valid=False), "r-bad") is False


def _fact(job="j1", rel="r-bad", reason="early_ack", linked=True, job_match=True, is_redispatch=True):
    return RepairFact(job, rel, reason, linked, job_match, is_redispatch)


_EXPECTED = _fact()


def test_repair_integrity_true_duplicate_is_already_applied():
    assert classify_repair_integrity(_fact(), _EXPECTED) == "already_applied"


def test_repair_integrity_no_row_is_repair_failed():
    assert classify_repair_integrity(None, _EXPECTED) == "repair_failed"


def test_repair_integrity_mismatched_repair_facts_are_repair_failed():
    # Different job / release / reason, or no linked Outbox at all.
    assert classify_repair_integrity(_fact(job="j2"), _EXPECTED) == "repair_failed"
    assert classify_repair_integrity(_fact(rel="r-good"), _EXPECTED) == "repair_failed"
    assert classify_repair_integrity(_fact(reason="other"), _EXPECTED) == "repair_failed"
    assert classify_repair_integrity(_fact(linked=False), _EXPECTED) == "repair_failed"


def test_repair_integrity_linked_outbox_wrong_job_is_repair_failed():
    # FK is non-null and a row exists, but the linked Outbox belongs to a DIFFERENT Job.
    assert classify_repair_integrity(_fact(job_match=False), _EXPECTED) == "repair_failed"


def test_repair_integrity_linked_outbox_wrong_event_type_is_repair_failed():
    # FK is non-null and same Job, but the linked Outbox is NOT a job.redispatch_requested intent.
    assert classify_repair_integrity(_fact(is_redispatch=False), _EXPECTED) == "repair_failed"


def test_readiness_revision_gate():
    assert revision_ready("0012_day60_repair_audit_attestation", "0012_day60_repair_audit_attestation") is True
    assert revision_ready("0009_day60_delivery_runtime", "0012_day60_repair_audit_attestation") is False
    assert revision_ready(None, "0012_day60_repair_audit_attestation") is False
