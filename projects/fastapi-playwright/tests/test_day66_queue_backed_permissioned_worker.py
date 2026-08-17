"""Day66 — EXECUTED_LOCAL_RUNTIME tests for the pure queue-backed permissioned-worker decision core.

Standard-library only; no Provider/LLM, no PostgreSQL, no Redis/Celery/Outbox Relay, no Playwright, no
Object Storage. Proves the RULES and the required FAILURE/SECURITY paths (one group per classroom
exercise). NOT integration evidence; the LIVE classroom artifact was CONCEPTUAL_STATIC. Day65's 20 pure
tests and earlier evidence are NOT Day66 validation.
"""

from day63_session_gate import SessionMeta
from day65_recovery_security_policy import (
    FenceInputs,
    ReconcileNextStep,
    ReconcileResult,
    RetryContext,
    RetryDecision,
    RetryPolicy,
    SecurityStop,
    TimeoutClass,
)
from day66_queue_backed_permissioned_worker import (
    AcceptanceBundle,
    AcceptanceOutcome,
    AcceptanceStage,
    CancellationDecision,
    ClaimDecision,
    ClaimRequest,
    RenewDecision,
    RenewLeaseRequest,
    DeliveryDecision,
    EnvelopeDecision,
    ExistingAcceptance,
    ProposalDecision,
    QueueEnvelope,
    RequestFingerprint,
    ServerAuthorizedContract,
    TaskState,
    ToolCallProposal,
    ToolResultDecision,
    ToolResultDraft,
    WorkerIncidentClass,
    accepted_is_not_succeeded,
    ack_only_after_durable_commit,
    atomic_acceptance,
    attempt_id_changes_per_attempt,
    audit_event_is_safe,
    becomes_durable_task_at,
    cancellation_checkpoints,
    classify_cancellation,
    classify_worker_incident,
    direct_in_request_publish_is_safe,
    dispatch_via_relay_after_commit,
    envelope_payload_is_authorization,
    fingerprint_of,
    guarded_claim,
    incident_phases,
    is_terminal,
    lease_expiry_proves_no_external_effect,
    on_delivery,
    recovery_next_step,
    recovery_permits_publication,
    recovery_permits_replay,
    redelivered_worker_returns_result_to_broker,
    renew_lease,
    renewed_expiry,
    retry_is_new_attempt_identity,
    rollback_target_is_worker_release,
    shape_tool_result,
    stale_bytes_are_trusted_artifact,
    stale_published_artifact_is_trusted,
    task_id_stable_across_attempts,
    terminal_publish_allowed,
    validate_envelope,
    validate_tool_proposal,
    worker_retry_decision,
)

NOW = 1_000
ORIGIN = "https://reports.example.test:443"


# ---- 1) tool-call proposal validation -----------------------------------------------------
def _proposal(**over):
    d = dict(is_tool_call=True, operation="browser.export_report", tenant_id="tenantA",
             target_origin=ORIGIN, report_scope="q3", idempotency_key="idem-1")
    d.update(over)
    return ToolCallProposal(**d)


def _contract(**over):
    d = dict(tenant_id="tenantA", allowed_operation="browser.export_report", approved_origin=ORIGIN,
             allowed_report_scope="q3", session_authorized=True, approval_granted=True,
             approval_id="appr-1")
    d.update(over)
    return ServerAuthorizedContract(**d)


def test_tool_proposal_must_match_server_authorized_contract():
    c = _contract()
    assert validate_tool_proposal(_proposal(), c) is ProposalDecision.ACCEPT_NEW
    # a raw model text (not a tool call) is not acceptance
    assert validate_tool_proposal(_proposal(is_tool_call=False), c) is ProposalDecision.REJECT_NOT_A_TOOL_CALL
    # idempotency key is required
    assert validate_tool_proposal(_proposal(idempotency_key=None), c) is ProposalDecision.REJECT_MISSING_IDEMPOTENCY
    # approval must be a SERVER fact: even a (hypothetical) self-asserted proposal cannot approve itself,
    # and a contract without a server-side approval is rejected regardless of the proposal
    assert validate_tool_proposal(_proposal(), _contract(approval_granted=False)) is ProposalDecision.REJECT_UNAPPROVED
    # the proposal's untrusted fields cannot widen the server contract
    assert validate_tool_proposal(_proposal(operation="browser.delete_all"), c) is ProposalDecision.REJECT_POLICY_BLOCKED
    assert validate_tool_proposal(_proposal(tenant_id="tenantB"), c) is ProposalDecision.REJECT_TENANT_MISMATCH
    # a malicious Origin in the proposal is rejected (never trusted)
    assert validate_tool_proposal(_proposal(target_origin="https://evil.example.test:443"), c) is ProposalDecision.REJECT_ORIGIN_NOT_APPROVED
    assert validate_tool_proposal(_proposal(target_origin="http://169.254.169.254:80"), c) is ProposalDecision.REJECT_ORIGIN_NOT_APPROVED
    # a report/data scope outside the contract is rejected
    assert validate_tool_proposal(_proposal(report_scope="q4"), c) is ProposalDecision.REJECT_SCOPE_NOT_ALLOWED
    # no valid Session/authorization binding -> rejected even when everything else matches
    assert validate_tool_proposal(_proposal(), _contract(session_authorized=False)) is ProposalDecision.REJECT_SESSION_UNAUTHORIZED


def test_same_key_same_authorized_intent_is_replay_different_is_rejected():
    c = _contract()
    fp = RequestFingerprint("tenantA", "browser.export_report", ORIGIN, "q3")
    existing = ExistingAcceptance("idem-1", fp)
    assert fingerprint_of(_proposal()) == fp
    # same key + same authorized intent -> idempotent replay of the existing task
    assert validate_tool_proposal(_proposal(), c, existing) is ProposalDecision.REPLAY_EXISTING
    # same key + a DIFFERENT scope: the scope now falls outside the contract, so it is rejected BEFORE
    # the fingerprint check (the contract is the authority, not the prior acceptance)
    assert validate_tool_proposal(_proposal(report_scope="q4"), c, existing) is ProposalDecision.REJECT_SCOPE_NOT_ALLOWED
    # same key + a different-but-contract-allowed intent still trips the fingerprint mismatch guard
    c2 = _contract(allowed_report_scope="q4")
    assert validate_tool_proposal(_proposal(report_scope="q4"), c2, existing) is ProposalDecision.REJECT_FINGERPRINT_MISMATCH


# ---- 2) acceptance lifecycle boundary -----------------------------------------------------
def test_durable_task_only_at_commit_not_provider_response():
    assert becomes_durable_task_at(AcceptanceStage.PROVIDER_PROPOSAL) is False   # "第三步" is only a proposal
    assert becomes_durable_task_at(AcceptanceStage.VALIDATED) is False
    assert becomes_durable_task_at(AcceptanceStage.DURABLY_ACCEPTED) is True


# ---- 3) atomic acceptance + Relay-after-commit -------------------------------------------
def test_atomic_acceptance_all_or_nothing_and_relay():
    assert atomic_acceptance(AcceptanceBundle(True, True, True)) is AcceptanceOutcome.ACCEPTED_202
    # a committed Job without a committed Outbox intent (or any partial) is never a 202
    assert atomic_acceptance(AcceptanceBundle(True, True, False)) is AcceptanceOutcome.ROLLED_BACK
    assert atomic_acceptance(AcceptanceBundle(True, False, True)) is AcceptanceOutcome.ROLLED_BACK
    assert atomic_acceptance(AcceptanceBundle(False, True, True)) is AcceptanceOutcome.ROLLED_BACK
    # dispatch is via an independent Relay AFTER commit, not a direct in-request publish
    assert dispatch_via_relay_after_commit() is True
    assert direct_in_request_publish_is_safe() is False


# ---- 4) minimal versioned queue envelope --------------------------------------------------
def _env(**over):
    d = dict(envelope_version=1, event_id="ev-1", task_id="task-1", trace_id="tr-1",
             event_type="browser.task.dispatch")
    d.update(over)
    return QueueEnvelope(**d)


def test_envelope_is_a_strict_allowlist_with_event_type_and_no_secrets():
    assert validate_envelope(_env()) is EnvelopeDecision.ACCEPT
    # unsupported version -> dead-letter + ACK, load nothing
    assert validate_envelope(_env(envelope_version=2)) is EnvelopeDecision.DEAD_LETTER_UNSUPPORTED_VERSION
    # ANY field beyond the five allowed ones is rejected — a known credential, a session_token, OR an
    # unknown/future field (the security boundary is the allowlist, not a denylist)
    assert validate_envelope(_env(extra_field_names=frozenset({"cookies"}))) is EnvelopeDecision.REJECT_UNKNOWN_FIELD
    assert validate_envelope(_env(extra_field_names=frozenset({"session_token"}))) is EnvelopeDecision.REJECT_UNKNOWN_FIELD
    assert validate_envelope(_env(extra_field_names=frozenset({"some_future_field"}))) is EnvelopeDecision.REJECT_UNKNOWN_FIELD
    # missing identity is rejected
    assert validate_envelope(_env(task_id="")) is EnvelopeDecision.REJECT_MISSING_IDENTITY
    # an event type that is not a browser-task dispatch is rejected
    assert validate_envelope(_env(event_type="billing.invoice.created")) is EnvelopeDecision.REJECT_EVENT_TYPE
    # a valid envelope is a notification, never authorization
    assert envelope_payload_is_authorization() is False


# ---- 5) guarded claim / lease -------------------------------------------------------------
def test_guarded_claim_one_winner_not_queue_delivery():
    # a free ACCEPTED task -> claimed
    assert guarded_claim(ClaimRequest(TaskState.ACCEPTED, None, None, NOW, "att-1")) is ClaimDecision.CLAIMED
    # an expired lease can be re-claimed by a new Attempt
    assert guarded_claim(ClaimRequest(TaskState.RUNNING, "att-old", NOW - 1, NOW, "att-2")) is ClaimDecision.CLAIMED
    # another Attempt holds an UNEXPIRED lease -> denied
    assert guarded_claim(ClaimRequest(TaskState.RUNNING, "att-old", NOW + 100, NOW, "att-2")) is ClaimDecision.DENIED_LEASE_ACTIVE
    # the SAME Attempt cannot re-claim its own still-valid lease (no overwrite via a duplicate path)
    assert guarded_claim(ClaimRequest(TaskState.RUNNING, "att-1", NOW + 100, NOW, "att-1")) is ClaimDecision.DENIED_LEASE_ACTIVE
    # a terminal task is never re-executed
    assert guarded_claim(ClaimRequest(TaskState.SUCCEEDED, None, None, NOW, "att-1")) is ClaimDecision.DENIED_TERMINAL
    # a cancellation-requested task is not claimable
    assert guarded_claim(ClaimRequest(TaskState.CANCELLATION_REQUESTED, None, None, NOW, "att-1")) is ClaimDecision.DENIED_NOT_CLAIMABLE
    assert is_terminal(TaskState.CANCELLED) is True and is_terminal(TaskState.RUNNING) is False


def _renew(**over):
    d = dict(task_state=TaskState.RUNNING, lease_owner="att-1", lease_token="tok-1",
             lease_expires_at=NOW + 50, now=NOW, attempt_id="att-1", worker_token="tok-1",
             new_expires_at=NOW + 500)
    d.update(over)
    return RenewLeaseRequest(**d)


def test_renew_lease_only_current_owner_and_token_on_unexpired_lease():
    # the current owner + token may extend an unexpired lease; the expiry moves, the token does NOT rotate
    assert renew_lease(_renew()) is RenewDecision.RENEWED
    assert renewed_expiry(_renew()) == NOW + 500
    # wrong token / wrong owner / expired lease / not-running can never renew
    assert renew_lease(_renew(worker_token="tok-BAD")) is RenewDecision.DENIED_TOKEN_MISMATCH
    assert renew_lease(_renew(attempt_id="att-2")) is RenewDecision.DENIED_OWNER_MISMATCH
    assert renew_lease(_renew(lease_expires_at=NOW - 1)) is RenewDecision.DENIED_LEASE_EXPIRED
    assert renew_lease(_renew(task_state=TaskState.ACCEPTED)) is RenewDecision.DENIED_NOT_RUNNING
    # a denied renewal yields no new expiry (and an expired lease is re-acquired via guarded_claim instead)
    assert renewed_expiry(_renew(lease_expires_at=NOW - 1)) is None


def test_renew_lease_must_strictly_extend_into_the_future():
    # current lease expires at NOW + 50; a valid renewal must move it strictly FORWARD
    # new expiry in the past / at now -> rejected, current expiry untouched
    assert renew_lease(_renew(new_expires_at=NOW - 10)) is RenewDecision.DENIED_NOT_EXTENDING
    assert renew_lease(_renew(new_expires_at=NOW)) is RenewDecision.DENIED_NOT_EXTENDING
    # new expiry EQUAL to the current lease expiry -> not an extension -> rejected
    assert renew_lease(_renew(new_expires_at=NOW + 50)) is RenewDecision.DENIED_NOT_EXTENDING
    # new expiry EARLIER than the current lease expiry (would shorten) -> rejected
    assert renew_lease(_renew(new_expires_at=NOW + 20)) is RenewDecision.DENIED_NOT_EXTENDING
    # a strict, forward extension -> RENEWED and returns the new expiry
    assert renew_lease(_renew(new_expires_at=NOW + 51)) is RenewDecision.RENEWED
    assert renewed_expiry(_renew(new_expires_at=NOW + 51)) == NOW + 51
    # every rejected renewal writes NO new expiry (the original lease expiry is preserved)
    for bad in (NOW - 10, NOW, NOW + 20, NOW + 50):
        assert renewed_expiry(_renew(new_expires_at=bad)) is None


# ---- 6) stale-write rejection via the Day63 final fence -----------------------------------
def _fence(**over):
    meta = SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)
    d = dict(meta=meta, worker_token="wtok-1", claimed_version=3, attempt_id="att-1", now=NOW)
    d.update(over)
    return FenceInputs(**d)


def test_stale_worker_cannot_publish_even_with_valid_bytes():
    assert terminal_publish_allowed(_fence()) is True
    # Worker A's token was superseded (Worker B took a new token) -> A cannot publish
    assert terminal_publish_allowed(_fence(worker_token="stale")) is False
    # a taken-over owner / expired lease / bumped version all block publication
    assert terminal_publish_allowed(_fence(meta=SessionMeta("active", NOW + 100, 3, "att-2", "wtok-1", NOW + 50))) is False
    assert terminal_publish_allowed(_fence(meta=SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW - 1))) is False
    assert terminal_publish_allowed(_fence(claimed_version=99)) is False
    assert stale_bytes_are_trusted_artifact() is False


# ---- 7) commit-before-ACK + terminal dedupe ----------------------------------------------
def test_delivery_dedupe_and_commit_before_ack():
    # a redelivered message for a terminal task -> ACK duplicate, do NOT re-run Playwright
    assert on_delivery(TaskState.SUCCEEDED, lease_expired=False) is DeliveryDecision.SKIP_TERMINAL_ACK
    assert on_delivery(TaskState.CANCELLED, lease_expired=False) is DeliveryDecision.SKIP_TERMINAL_ACK
    # a RUNNING task whose lease is STILL LIVE is owned by another Attempt -> ACK duplicate, do NOT run
    assert on_delivery(TaskState.RUNNING, lease_expired=False) is DeliveryDecision.SKIP_ACTIVE_LEASE_ACK
    # only a RUNNING task whose lease EXPIRED -> Day65 reconciliation, not a blind re-run
    assert on_delivery(TaskState.RUNNING, lease_expired=True) is DeliveryDecision.RECONCILE_IN_FLIGHT
    # cancellation requested -> cooperative stop
    assert on_delivery(TaskState.CANCELLATION_REQUESTED, lease_expired=False) is DeliveryDecision.STOP_CANCELLATION_REQUESTED
    # a fresh accepted task -> execute
    assert on_delivery(TaskState.ACCEPTED, lease_expired=False) is DeliveryDecision.EXECUTE
    assert ack_only_after_durable_commit() is True
    assert redelivered_worker_returns_result_to_broker() is False


# ---- 8) Day65 UNKNOWN_OUTCOME reconciliation hand-off ------------------------------------
def test_recovery_hands_off_to_day65_reconciliation():
    assert lease_expiry_proves_no_external_effect() is False
    # terminal completion may publish; accepted/in-flight may not; only non-start may replay/retry
    assert recovery_next_step(ReconcileResult.CONFIRMED_COMPLETED) is ReconcileNextStep.PUBLISH_TERMINAL_RESULT
    assert recovery_next_step(ReconcileResult.CONFIRMED_ACCEPTED_OR_IN_FLIGHT) is ReconcileNextStep.CONTINUE_RECONCILING
    assert recovery_next_step(ReconcileResult.CONFIRMED_NOT_STARTED) is ReconcileNextStep.ELIGIBLE_FOR_BOUNDED_RETRY
    assert recovery_permits_publication(ReconcileResult.CONFIRMED_ACCEPTED_OR_IN_FLIGHT) is False
    assert recovery_permits_publication(ReconcileResult.CONFIRMED_COMPLETED) is True
    assert recovery_permits_replay(ReconcileResult.CONFIRMED_ACCEPTED_OR_IN_FLIGHT) is False
    assert recovery_permits_replay(ReconcileResult.CONFIRMED_NOT_STARTED) is True


# ---- 9) safe retry gate + new-attempt identity -------------------------------------------
def _policy(**over):
    d = dict(max_attempts=3, total_budget_ms=60_000, per_attempt_timeout_ms=5_000,
             retryable_errors=["browser_context_start_failed"], idempotency_key="idem-1")
    d.update(over)
    return RetryPolicy(**d)


def _ctx(**over):
    d = dict(attempt_number=1, elapsed_ms=1_000, remaining_deadline_ms=30_000,
             failure_class="browser_context_start_failed", timeout_class=TimeoutClass.SAFE_TO_RETRY,
             security_stop=SecurityStop.NONE, authorized=True, one_active_owner=True,
             proven_non_start=True, retry_after_ms=None)
    d.update(over)
    return RetryContext(**d)


def test_worker_retry_gate_is_fenced_and_new_attempt_identity():
    # a proven BrowserContext non-start with a valid fence -> RETRY (a new auditable Attempt)
    assert worker_retry_decision(_policy(), _ctx(), _fence()) is RetryDecision.RETRY
    # a failing fence (revoked session) can never be retried, even with authorized=True in ctx
    revoked = _fence(meta=SessionMeta("revoked", NOW + 100, 3, "att-1", "wtok-1", NOW + 50))
    assert worker_retry_decision(_policy(), _ctx(authorized=True), revoked) is RetryDecision.UNAUTHORIZED
    # an UNKNOWN_OUTCOME must reconcile first, never blind-retry
    assert worker_retry_decision(_policy(), _ctx(timeout_class=TimeoutClass.UNKNOWN_OUTCOME), _fence()) is RetryDecision.UNKNOWN_OUTCOME_BLOCK
    # a new retry needs a NEW attempt_id AND a NEW lease token
    assert retry_is_new_attempt_identity("att-1", "att-2", "tok-1", "tok-2") is True
    assert retry_is_new_attempt_identity("att-1", "att-1", "tok-1", "tok-2") is False


# ---- 10) cancellation / revocation --------------------------------------------------------
def test_cancellation_is_durable_cooperative_and_checkpointed():
    # external action may have begun -> durable cancellation_requested, not immediate cancelled
    assert classify_cancellation(external_action_may_have_started=True) is CancellationDecision.RECORD_CANCELLATION_REQUESTED
    # provably nothing external happened -> may cancel immediately
    assert classify_cancellation(external_action_may_have_started=False) is CancellationDecision.CANCEL_IMMEDIATELY
    assert cancellation_checkpoints() == ("before_claim", "before_credential_load", "before_critical_action", "before_publication")


# ---- 11) async permissioned-tool response + safe Tool Result -----------------------------
def _draft(**over):
    d = dict(tenant_authorized=True, terminal_succeeded=True, summary_is_safe=True,
             field_names=frozenset({"task_id", "status", "safe_summary", "artifact_ref"}),
             includes_artifact_reference=True)
    d.update(over)
    return ToolResultDraft(**d)


def test_tool_result_is_a_strict_allowlist():
    assert accepted_is_not_succeeded() is True
    assert shape_tool_result(_draft()) is ToolResultDecision.RETURN_SAFE_SUMMARY
    # a minimal task_id + status only is also fine
    assert shape_tool_result(_draft(field_names=frozenset({"task_id", "status"}))) is ToolResultDecision.RETURN_SAFE_SUMMARY
    assert shape_tool_result(_draft(tenant_authorized=False)) is ToolResultDecision.DENY_NOT_AUTHORIZED
    # no result reference until a guarded successful terminal write exists
    assert shape_tool_result(_draft(terminal_succeeded=False)) is ToolResultDecision.DENY_NOT_TERMINAL
    # ANY field outside the allowlist is rejected — a known leak, a credential, OR an unknown/future field
    assert shape_tool_result(_draft(field_names=frozenset({"safe_summary", "raw_csv"}))) is ToolResultDecision.DENY_UNSAFE_FIELD
    assert shape_tool_result(_draft(field_names=frozenset({"safe_summary", "session_token"}))) is ToolResultDecision.DENY_UNSAFE_FIELD
    assert shape_tool_result(_draft(field_names=frozenset({"safe_summary", "authorization"}))) is ToolResultDecision.DENY_UNSAFE_FIELD
    assert shape_tool_result(_draft(field_names=frozenset({"safe_summary", "some_future_field"}))) is ToolResultDecision.DENY_UNSAFE_FIELD
    assert shape_tool_result(_draft(summary_is_safe=False)) is ToolResultDecision.DENY_UNVERIFIED_SUMMARY


# ---- 12) correlation / audit identity -----------------------------------------------------
def test_identity_and_safe_audit():
    assert task_id_stable_across_attempts() is True
    assert attempt_id_changes_per_attempt() is True
    # a non-reversible lease_token_fingerprint is allowlisted; the RAW lease_token capability is NOT
    assert audit_event_is_safe(["task_id", "attempt_id", "lease_token_fingerprint", "state_transition", "timestamp"]) is True
    assert audit_event_is_safe(["task_id", "lease_token"]) is False
    # credentials / unknown / future fields must never be in an audit event (strict allowlist)
    assert audit_event_is_safe(["task_id", "session_token"]) is False
    assert audit_event_is_safe(["task_id", "cookies"]) is False
    assert audit_event_is_safe(["task_id", "raw_csv"]) is False
    assert audit_event_is_safe(["task_id", "some_future_field"]) is False


# ---- 13) incident rollback (stale-Worker fence removal) ----------------------------------
def test_worker_incident_classification_and_flow():
    assert incident_phases() == ("contain", "scope", "classify", "repair", "controlled_rollout")
    assert classify_worker_incident(evidence_complete=True, stale_write_blocked=True,
                                    stale_artifact_published=False, conflicting_attempts=False) is WorkerIncidentClass.BLOCKED_STALE_WRITE
    assert classify_worker_incident(evidence_complete=True, stale_write_blocked=False,
                                    stale_artifact_published=True, conflicting_attempts=False) is WorkerIncidentClass.STALE_ARTIFACT_PUBLISHED
    assert classify_worker_incident(evidence_complete=True, stale_write_blocked=False,
                                    stale_artifact_published=False, conflicting_attempts=True) is WorkerIncidentClass.CONFLICTING_ATTEMPTS
    assert classify_worker_incident(evidence_complete=False, stale_write_blocked=False,
                                    stale_artifact_published=True, conflicting_attempts=False) is WorkerIncidentClass.UNKNOWN
    # a stale-published Artifact is quarantined, not trusted/returned to the LLM
    assert stale_published_artifact_is_trusted() is False
    # a fence-removal regression is repaired by rolling back the Worker RELEASE, not just config
    assert rollback_target_is_worker_release() is True
