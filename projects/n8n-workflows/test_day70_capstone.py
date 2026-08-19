"""Day70 — EXECUTED_LOCAL_RUNTIME tests for the Phase 6 capstone decision model.

Standard-library only; no n8n, FastAPI, PostgreSQL, Worker/Provider, or credential store. Proves the RULES
across the six capstone decision areas + the polling/observation boundary, plus the n8n workflow static
contract (request body, IF validation, inbound-auth reference) and the Day59 report_scope fingerprint.
Eighteen deterministic tests (the classroom's fourteen pre-fix tests are superseded).
NOT integration evidence: they do not upgrade to INTEGRATION_RUNTIME/PRODUCTION.

Run from ``projects/n8n-workflows/``:  python3 -m pytest -q test_day70_capstone.py
"""

import json
import os
import sys

from day70_capstone import (
    Approval,
    AuthorizationContext,
    AcceptanceRecovery,
    BackendAcceptanceState,
    CredentialCause,
    CredentialDecision,
    DeliveredEvent,
    EventDecision,
    IncidentTask,
    IncidentTaskClass,
    PollDecision,
    PublicationRecovery,
    PublicationStatus,
    TaskObservation,
    acceptance_recovery,
    approval_authorizes,
    approval_binding_complete,
    blind_retry_on_401,
    classify_credential_failure,
    classify_event,
    classify_incident_task,
    guarded_cancellation_result,
    identity_is_new_v7_to_v8,
    identity_is_stable_v7_to_v8,
    not_found_proves_never_accepted,
    observation_failure_changes_durable_state,
    poll_decision,
    publication_recovery,
    http_request_body_expression,
    if_validated_fields,
    webhook_inbound_authentication,
    workflow_sends_report_scope_in_business_input,
)

_WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "day70_minimal_acceptance_workflow.json")


def _load_workflow():
    with open(_WORKFLOW_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# Optional real Day59 fingerprint (authoritative proof that report_scope changes the fingerprint).
_DAY59_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-backend-data-layer", "api"))
if _DAY59_DIR not in sys.path:
    sys.path.insert(0, _DAY59_DIR)
try:
    from day59_acceptance_logic import compute_request_fingerprint as _day59_fingerprint
except Exception:  # pragma: no cover - import guard for isolated runs
    _day59_fingerprint = None

NOW = 1_000


# ---- 1) acceptance recovery ---------------------------------------------------------------
def test_acceptance_recovery_lost_response_is_outcome_unknown_not_reissue():
    # ACCEPTED -> return the existing task_id, never re-accept
    assert acceptance_recovery(BackendAcceptanceState.ACCEPTED, True) is AcceptanceRecovery.RETURN_EXISTING
    # UNKNOWN -> reconcile, never blind reissue
    assert acceptance_recovery(BackendAcceptanceState.UNKNOWN, True) is AcceptanceRecovery.PENDING_RECONCILIATION
    # NOT_FOUND is ambiguous -> reconcile, never treated as never-accepted (and never proves never-accepted)
    assert acceptance_recovery(BackendAcceptanceState.NOT_FOUND, True) is AcceptanceRecovery.PENDING_RECONCILIATION
    assert not_found_proves_never_accepted() is False


def test_acceptance_reissue_requires_never_accepted_and_valid_retention():
    # proven NEVER_ACCEPTED + retention still valid -> reissue same key
    assert acceptance_recovery(BackendAcceptanceState.NEVER_ACCEPTED, True) is AcceptanceRecovery.REISSUE_SAME_KEY
    # proven NEVER_ACCEPTED but retention EXPIRED -> reconcile (same key != unconditional safety)
    assert acceptance_recovery(BackendAcceptanceState.NEVER_ACCEPTED, False) is AcceptanceRecovery.PENDING_RECONCILIATION


# ---- 2) event dedupe / conflict -----------------------------------------------------------
def test_event_same_id_same_fingerprint_is_no_op():
    seen = DeliveredEvent("ev-1", "fp-v7")
    assert classify_event(seen, DeliveredEvent("ev-1", "fp-v7")) is EventDecision.IDEMPOTENT_NO_OP


def test_event_same_id_different_fingerprint_is_conflict():
    seen = DeliveredEvent("ev-1", "fp-v7")
    assert classify_event(seen, DeliveredEvent("ev-1", "fp-v8")) is EventDecision.CONFLICT


def test_event_new_id_processes_new():
    seen = DeliveredEvent("ev-1", "fp-v7")
    assert classify_event(seen, DeliveredEvent("ev-2", "fp-v8")) is EventDecision.PROCESS_NEW
    assert classify_event(None, DeliveredEvent("ev-1", "fp-v7")) is EventDecision.PROCESS_NEW


# ---- 3) exact Approval binding ------------------------------------------------------------
def _approval(**over):
    d = dict(approval_id="approval-301", tenant_id="tenantA", task_id="task-8421", artifact_id="artifact-7",
             artifact_version="v7", action="publish_report", approver_actor="user-9",
             approver_role="Compliance", policy_version="p1", expires_at=NOW + 100, decision="APPROVED",
             decided_at=NOW)
    d.update(over)
    return Approval(**d)


def _ctx(**over):
    d = dict(tenant_id="tenantA", task_id="task-8421", artifact_id="artifact-7", artifact_version="v7",
             action="publish_report", policy_version="p1", required_role="Compliance")
    d.update(over)
    return AuthorizationContext(**d)


def test_approval_binding_must_be_complete():
    assert approval_binding_complete(list(_approval().__dict__.keys())) is True
    # a partial binding (only task_id + artifact_version + approval_id) is insufficient
    assert approval_binding_complete(["approval_id", "task_id", "artifact_version"]) is False


def test_approval_authorizes_requires_exact_full_binding():
    # exact match on every field -> authorized
    assert approval_authorizes(_approval(), _ctx(), NOW) is True
    # ANY single mismatch denies authorization
    assert approval_authorizes(_approval(tenant_id="tenantB"), _ctx(), NOW) is False           # tenant
    assert approval_authorizes(_approval(task_id="task-OTHER"), _ctx(), NOW) is False           # task
    assert approval_authorizes(_approval(artifact_id="artifact-9"), _ctx(), NOW) is False       # artifact_id
    assert approval_authorizes(_approval(artifact_version="v8"), _ctx(), NOW) is False           # v7 != v8
    assert approval_authorizes(_approval(action="delete_report"), _ctx(), NOW) is False          # action
    assert approval_authorizes(_approval(policy_version="p2"), _ctx(), NOW) is False              # policy
    assert approval_authorizes(_approval(approver_role="Intern"), _ctx(required_role="Compliance"), NOW) is False  # role
    assert approval_authorizes(_approval(decision="REJECTED"), _ctx(), NOW) is False              # rejected
    assert approval_authorizes(_approval(expires_at=NOW - 1), _ctx(), NOW) is False               # expired
    # completeness is not the same as authorization: full fields but wrong version still denies
    assert approval_binding_complete(list(_approval().__dict__.keys())) is True
    assert approval_authorizes(_approval(), _ctx(artifact_version="v8"), NOW) is False


def test_v7_to_v8_identity_plan_stable_vs_new():
    for f in ("tenant_id", "task_id", "correlation_id"):
        assert identity_is_stable_v7_to_v8(f) is True
    for f in ("artifact_version", "approval_id", "approval_event_id", "publication_operation_id",
              "publication_idempotency_key"):
        assert identity_is_new_v7_to_v8(f) is True
    # a revalidate-required field is neither auto-stable nor a fresh business-intent identity
    assert identity_is_stable_v7_to_v8("policy_version") is False
    assert identity_is_new_v7_to_v8("policy_version") is False


# ---- 4) publication recovery --------------------------------------------------------------
def test_publication_recovery_matrix():
    assert publication_recovery(PublicationStatus.SUCCEEDED) is PublicationRecovery.DONE_NO_REPUBLISH
    assert publication_recovery(PublicationStatus.PROCESSING) is PublicationRecovery.OBSERVE_SAME_OPERATION
    assert publication_recovery(PublicationStatus.FAILED_TERMINAL) is PublicationRecovery.TERMINAL_NO_RETRY
    assert publication_recovery(PublicationStatus.PENDING_RECONCILIATION) is PublicationRecovery.RECONCILE
    assert publication_recovery(PublicationStatus.NOT_FOUND) is PublicationRecovery.VERIFY_BEFORE_ANY_REISSUE


# ---- 5) credential classification ---------------------------------------------------------
def test_credential_401_is_never_a_blind_retry():
    assert blind_retry_on_401() is False


def test_credential_rotate_only_when_established_else_fix_config():
    for c in (CredentialCause.EXPIRED, CredentialCause.REVOKED, CredentialCause.COMPROMISED,
              CredentialCause.LEAKED, CredentialCause.INVALID):
        assert classify_credential_failure(c) is CredentialDecision.ROTATE
    for c in (CredentialCause.AUDIENCE, CredentialCause.ISSUER, CredentialCause.AUTH_SCHEME,
              CredentialCause.MISSING_HEADER, CredentialCause.WRONG_ENDPOINT, CredentialCause.CLOCK_SKEW):
        assert classify_credential_failure(c) is CredentialDecision.FIX_CONFIGURATION
    assert classify_credential_failure(CredentialCause.UNKNOWN) is CredentialDecision.STOP_AND_CLASSIFY


# ---- 6) incident Task classification ------------------------------------------------------
def test_incident_published_without_approval_is_preserve_and_compensate():
    t = IncidentTask(published=True, approved=False, has_worker_claim=True, provider_dispatched=True,
                     has_artifact=True)
    assert classify_incident_task(t) is IncidentTaskClass.PRESERVE_AND_COMPENSATE


def test_incident_unstarted_is_durable_cancellation_and_running_unknown_is_reconciliation():
    unstarted = IncidentTask(published=False, approved=False, has_worker_claim=False,
                             provider_dispatched=False, has_artifact=False)
    assert classify_incident_task(unstarted) is IncidentTaskClass.DURABLE_CANCELLATION
    running_unknown = IncidentTask(published=False, approved=True, has_worker_claim=True,
                                   provider_dispatched=True, has_artifact=False)
    assert classify_incident_task(running_unknown) is IncidentTaskClass.PENDING_RECONCILIATION
    # a guarded cancellation that changes 0 rows means facts moved -> reclassify
    assert guarded_cancellation_result(1) is IncidentTaskClass.DURABLE_CANCELLATION
    assert guarded_cancellation_result(0) is IncidentTaskClass.RECLASSIFY


# ---- 7) polling / observation boundary ----------------------------------------------------
def test_poll_same_task_and_observation_failure_does_not_change_state():
    assert poll_decision(TaskObservation.QUEUED) is PollDecision.WAIT_AND_REQUERY
    assert poll_decision(TaskObservation.RUNNING) is PollDecision.WAIT_AND_REQUERY
    assert poll_decision(TaskObservation.SUCCEEDED) is PollDecision.CONSUME_RESULT
    assert poll_decision(TaskObservation.FAILED) is PollDecision.TERMINAL
    assert poll_decision(TaskObservation.CANCELLED) is PollDecision.TERMINAL
    assert observation_failure_changes_durable_state() is False


# ---- 8) Workflow static contract (Fix 2/3/4) ----------------------------------------------
def test_workflow_body_sends_report_scope_in_business_input_not_top_level():
    wf = _load_workflow()
    body = http_request_body_expression(wf)
    assert "business_input" in body and "report_scope" in body
    assert "document_ids" in body
    assert workflow_sends_report_scope_in_business_input(wf) is True


def test_workflow_if_validates_report_scope_request_id_and_document_id():
    fields = if_validated_fields(_load_workflow())
    assert {"report_scope", "request_id", "document_id"} <= fields


def test_workflow_webhook_configures_inbound_authentication_reference():
    # The SOURCE configures inbound (caller -> n8n) authentication as a Credential Store reference.
    # This is a design/static fact; the actual class run did NOT exercise inbound auth (see DAY70_CAPSTONE.md).
    assert webhook_inbound_authentication(_load_workflow()) == "headerAuth"


# ---- 9) Day59 request-fingerprint contract (Fix 3) ----------------------------------------
def test_report_scope_change_is_a_different_day59_fingerprint():
    if _day59_fingerprint is None:  # pragma: no cover
        import pytest
        pytest.skip("Day59 acceptance logic not importable in this run")
    # Same document, same idempotency key, DIFFERENT report_scope (inside business_input) -> DIFFERENT
    # fingerprint -> a 409 conflict, NOT a replay of the original Task.
    fp_q3 = _day59_fingerprint(["doc-1"], {"report_scope": "q3"})
    fp_q4 = _day59_fingerprint(["doc-1"], {"report_scope": "q4"})
    assert fp_q3 != fp_q4
    # Same document + same report_scope -> same fingerprint (an idempotent replay).
    assert _day59_fingerprint(["doc-1"], {"report_scope": "q3"}) == fp_q3
    # If report_scope were dropped at the top level it would NOT enter business_input and both bodies would
    # collapse to the same fingerprint -> a wrong replay; that is exactly what the workflow body prevents.
    assert _day59_fingerprint(["doc-1"], {}) == _day59_fingerprint(["doc-1"], {})
