"""Day65 — EXECUTED_LOCAL_RUNTIME tests for the pure recovery/security decision core.

Standard-library only; no browser, no traces/screenshots, no Object Storage, no PostgreSQL, no queue.
Proves the RULES and the required FAILURE/SECURITY paths (one group per classroom exercise). NOT
integration evidence; the LIVE classroom artifact was CONCEPTUAL_STATIC.
"""

from day63_session_gate import SessionMeta
from day65_recovery_security_policy import (
    ActionIdentity,
    CredentialRequest,
    DiagnosticDecision,
    DiagnosticDestination,
    IncidentClass,
    InstructionDecision,
    InstructionSource,
    NavigationDecision,
    NavigationRequest,
    ReconcileNextStep,
    ReconcileResult,
    ReleaseContext,
    ReleaseDecision,
    RetryContext,
    RetryDecision,
    RetryPolicy,
    SecurityStop,
    FenceInputs,
    ServerActionRecord,
    TimeoutClass,
    authorization_still_valid,
    authorize_credential_release,
    authorize_retry,
    classify_captcha,
    classify_incident_item,
    classify_timeout,
    compute_backoff_ms,
    credential_release_allowed,
    cross_origin_forwards_storage_state,
    diagnostics_decision,
    incident_phases,
    instruction_authorized,
    is_prohibited_ip,
    is_retryable_business_failure,
    navigation_allowed,
    reconcile_next_step,
    reconcile_permits_publication,
    reconcile_permits_replay,
    reconcile_unknown,
    retry_eligibility,
    screenshot_proves_publication,
    unknown_may_blind_retry,
    validate_redirect_chain,
)

NOW = 1_000
ORIGIN = "https://research.example.test:443"


# ---- 1) timeout classification ----------------------------------------------------------
def test_post_action_timeout_is_unknown_not_safe_to_retry():
    # request left, no response observed -> UNKNOWN_OUTCOME (may have executed)
    assert classify_timeout(action_request_sent=True, response_observed=False) is TimeoutClass.UNKNOWN_OUTCOME
    # proven non-start (never sent) -> SAFE_TO_RETRY
    assert classify_timeout(action_request_sent=False, response_observed=False) is TimeoutClass.SAFE_TO_RETRY
    assert classify_timeout(action_request_sent=True, response_observed=False, proven_non_start=True) is TimeoutClass.SAFE_TO_RETRY


# ---- 2) reconciliation by strict action identity ----------------------------------------
def _identity(**over):
    d = dict(allowed_origin=ORIGIN, method="POST", normalized_endpoint="/api/exports",
             report_id="42", client_request_id="crq-1", export_id=None)
    d.update(over)
    return ActionIdentity(**d)


def _record(**over):
    d = dict(found=True, allowed_origin=ORIGIN, method="POST", normalized_endpoint="/api/exports",
             report_id="42", client_request_id="crq-1", status="completed", export_id=None)
    d.update(over)
    return ServerActionRecord(**d)


def test_reconcile_uses_strict_identity_not_broad_match():
    expected = _identity()
    # all fields match + terminal status -> confirmed
    assert reconcile_unknown(expected, _record(status="completed")) is ReconcileResult.CONFIRMED_COMPLETED
    assert reconcile_unknown(expected, _record(status="never_started")) is ReconcileResult.CONFIRMED_NOT_STARTED
    # EVERY security field must match exactly; any single mismatch -> STILL_UNKNOWN (not our action)
    assert reconcile_unknown(expected, _record(allowed_origin="https://evil.example.test:443")) is ReconcileResult.STILL_UNKNOWN
    assert reconcile_unknown(expected, _record(method="GET")) is ReconcileResult.STILL_UNKNOWN
    assert reconcile_unknown(expected, _record(normalized_endpoint="/api/other")) is ReconcileResult.STILL_UNKNOWN
    assert reconcile_unknown(expected, _record(report_id="99")) is ReconcileResult.STILL_UNKNOWN
    assert reconcile_unknown(expected, _record(client_request_id="crq-other")) is ReconcileResult.STILL_UNKNOWN
    # authoritative negative proves non-start; a non-authoritative miss stays unknown
    assert reconcile_unknown(expected, ServerActionRecord(False, None, None, None, None, None, "not_found",
                                                          authoritative_negative=True)) is ReconcileResult.CONFIRMED_NOT_STARTED
    assert reconcile_unknown(expected, ServerActionRecord(False, None, None, None, None, None, None)) is ReconcileResult.STILL_UNKNOWN


def test_reconcile_verified_export_id_must_be_bound_and_never_substitute():
    # follow-up phase carries a verified export_id -> the record's export_id must match AND be bound to
    # the same initial client_request_id (which is still required).
    expected = _identity(export_id="exp-7")
    assert reconcile_unknown(expected, _record(export_id="exp-7", status="completed")) is ReconcileResult.CONFIRMED_COMPLETED
    # a wrong export_id -> not our export
    assert reconcile_unknown(expected, _record(export_id="exp-BAD", status="completed")) is ReconcileResult.STILL_UNKNOWN
    # an UNBOUND record (no export_id) cannot satisfy the verified-export phase
    assert reconcile_unknown(expected, _record(export_id=None, status="completed")) is ReconcileResult.STILL_UNKNOWN
    # a matching export_id can NEVER substitute for a mismatched initial client_request_id
    assert reconcile_unknown(expected, _record(export_id="exp-7", client_request_id="crq-other",
                                               status="completed")) is ReconcileResult.STILL_UNKNOWN


def test_accepted_and_in_flight_are_not_completed_no_replay_no_publish():
    expected = _identity()
    # accepted / pending / running are RECEIVED but NOT terminal -> in-flight, never completed
    for st in ("accepted", "pending", "running", "in_progress", "processing", "queued"):
        r = reconcile_unknown(expected, _record(status=st))
        assert r is ReconcileResult.CONFIRMED_ACCEPTED_OR_IN_FLIGHT, st
        assert r is not ReconcileResult.CONFIRMED_COMPLETED
        # in-flight: no replay of the original side effect, no Artifact publication -> keep reconciling
        assert reconcile_permits_replay(r) is False
        assert reconcile_permits_publication(r) is False
        assert reconcile_next_step(r) is ReconcileNextStep.CONTINUE_RECONCILING
    # accepted/in-flight still requires the FULL strict identity; any mismatch is STILL_UNKNOWN
    assert reconcile_unknown(expected, _record(status="accepted", method="GET")) is ReconcileResult.STILL_UNKNOWN
    assert reconcile_unknown(_identity(export_id="exp-7"),
                             _record(status="running", export_id="exp-BAD")) is ReconcileResult.STILL_UNKNOWN


def test_terminal_completed_and_not_started_semantics():
    expected = _identity()
    for st in ("completed", "imported"):
        r = reconcile_unknown(expected, _record(status=st))
        assert r is ReconcileResult.CONFIRMED_COMPLETED, st
        assert reconcile_permits_publication(r) is True       # ONLY a terminal completion may publish
        assert reconcile_permits_replay(r) is False
        assert reconcile_next_step(r) is ReconcileNextStep.PUBLISH_TERMINAL_RESULT
    # only an AUTHORITATIVE negative is CONFIRMED_NOT_STARTED (which alone permits replay/retry)
    neg = ServerActionRecord(False, None, None, None, None, None, "not_found", authoritative_negative=True)
    assert reconcile_unknown(expected, neg) is ReconcileResult.CONFIRMED_NOT_STARTED
    assert reconcile_permits_replay(reconcile_unknown(expected, neg)) is True
    assert reconcile_next_step(ReconcileResult.CONFIRMED_NOT_STARTED) is ReconcileNextStep.ELIGIBLE_FOR_BOUNDED_RETRY
    # a server 'not_found' record that is NOT authoritative-negative stays unknown (never a false non-start)
    assert reconcile_unknown(expected, _record(found=False, status="not_found")) is ReconcileResult.STILL_UNKNOWN


# ---- 3) diagnostics ---------------------------------------------------------------------
def test_diagnostics_only_private_redacted_audited():
    for dest in (DiagnosticDestination.ORDINARY_LOG, DiagnosticDestination.MODEL_CONTEXT,
                 DiagnosticDestination.PROMPT, DiagnosticDestination.PUBLIC_ARTIFACT):
        assert diagnostics_decision(dest, contains_sensitive=False, redacted=True,
                                    access_controlled=True, retention_bounded=True, audited=True) is DiagnosticDecision.DENY_DESTINATION
    priv = DiagnosticDestination.PRIVATE_AUDITED_STORE
    assert diagnostics_decision(priv, contains_sensitive=True, redacted=False, access_controlled=True,
                                retention_bounded=True, audited=True) is DiagnosticDecision.DENY_UNREDACTED
    assert diagnostics_decision(priv, contains_sensitive=True, redacted=True, access_controlled=False,
                                retention_bounded=True, audited=True) is DiagnosticDecision.DENY_NOT_ACCESS_CONTROLLED
    assert diagnostics_decision(priv, contains_sensitive=True, redacted=True, access_controlled=True,
                                retention_bounded=False, audited=True) is DiagnosticDecision.DENY_UNBOUNDED_RETENTION
    assert diagnostics_decision(priv, contains_sensitive=True, redacted=True, access_controlled=True,
                                retention_bounded=True, audited=False) is DiagnosticDecision.DENY_NOT_AUDITED
    assert diagnostics_decision(priv, contains_sensitive=True, redacted=True, access_controlled=True,
                                retention_bounded=True, audited=True) is DiagnosticDecision.ALLOW
    assert screenshot_proves_publication() is False


# ---- 4) navigation / SSRF ----------------------------------------------------------------
def test_navigation_blocks_ssrf_and_cloud_metadata():
    approved = [ORIGIN]
    # cloud-metadata 169.254.169.254 (link-local) is blocked even at an "approved-looking" origin
    assert is_prohibited_ip("169.254.169.254") is True
    assert is_prohibited_ip("127.0.0.1") is True and is_prohibited_ip("10.0.0.5") is True
    assert is_prohibited_ip("192.168.1.9") is True and is_prohibited_ip("::1") is True
    assert is_prohibited_ip("93.184.216.34") is False   # a public address is allowed by IP
    # a page instruction targeting the metadata IP under the approved origin -> BLOCKED_IP
    assert navigation_allowed(NavigationRequest("https", "research.example.test", 443, "169.254.169.254"), approved) is NavigationDecision.BLOCKED_IP
    assert navigation_allowed(NavigationRequest("http", "research.example.test", 443, "93.184.216.34"), approved) is NavigationDecision.BLOCKED_SCHEME
    assert navigation_allowed(NavigationRequest("https", "evil.example.test", 443, "93.184.216.34"), approved) is NavigationDecision.BLOCKED_ORIGIN
    assert navigation_allowed(NavigationRequest("https", "research.example.test", 443, "93.184.216.34"), approved) is NavigationDecision.ALLOW


def test_redirect_chain_revalidated_each_hop():
    approved = [ORIGIN]
    good = NavigationRequest("https", "research.example.test", 443, "93.184.216.34")
    bad = NavigationRequest("https", "research.example.test", 443, "169.254.169.254")  # DNS/IP change
    assert validate_redirect_chain([good, good], approved) is NavigationDecision.ALLOW
    assert validate_redirect_chain([good, bad], approved) is NavigationDecision.BLOCKED_IP


# ---- 5) credential release ---------------------------------------------------------------
def test_credential_release_scoped_and_no_cross_origin_forward():
    ctx = ReleaseContext("tenantA", "sessA", "att-1", [ORIGIN], session_valid=True)
    ok = CredentialRequest("tenantA", "sessA", "att-1", ORIGIN, "export")
    assert credential_release_allowed(ok, ctx) is ReleaseDecision.RELEASE
    # finance cookies to ANOTHER origin -> origin not approved
    assert credential_release_allowed(CredentialRequest("tenantA", "sessA", "att-1", "https://billing.example.test:443", "export"), ctx) is ReleaseDecision.DENY_ORIGIN_NOT_APPROVED
    assert credential_release_allowed(CredentialRequest("tenantB", "sessA", "att-1", ORIGIN, "export"), ctx) is ReleaseDecision.DENY_TENANT_MISMATCH
    assert credential_release_allowed(CredentialRequest("tenantA", "sessA", "att-1", ORIGIN, None), ctx) is ReleaseDecision.DENY_NO_PURPOSE
    assert credential_release_allowed(ok, ReleaseContext("tenantA", "sessA", "att-1", [ORIGIN], session_valid=False)) is ReleaseDecision.DENY_SESSION_INVALID
    assert cross_origin_forwards_storage_state() is False


# ---- 6) instruction authority / prompt injection -----------------------------------------
def test_page_instruction_overreach_is_prompt_injection():
    allowed = ["export_report"]
    # page text asking for a broad export + external upload -> untrusted source -> blocked
    assert instruction_authorized(InstructionSource.PAGE_TEXT, "upload_all_to_external", allowed) is InstructionDecision.PROMPT_INJECTION_BLOCKED
    assert instruction_authorized(InstructionSource.DOM, "export_report", allowed) is InstructionDecision.PROMPT_INJECTION_BLOCKED
    assert instruction_authorized(InstructionSource.MODEL_OUTPUT, "export_report", allowed) is InstructionDecision.PROMPT_INJECTION_BLOCKED
    # authoritative source, but out of contract scope
    assert instruction_authorized(InstructionSource.TASK_CONTRACT, "delete_everything", allowed) is InstructionDecision.OUT_OF_CONTRACT
    assert instruction_authorized(InstructionSource.SERVER_POLICY, "export_report", allowed) is InstructionDecision.AUTHORIZED


# ---- 7) CAPTCHA / human review -----------------------------------------------------------
def test_captcha_is_human_verification_not_retryable():
    stop = classify_captcha(True)
    assert stop is SecurityStop.HUMAN_VERIFICATION_REQUIRED
    assert is_retryable_business_failure(stop) is False
    assert classify_captcha(False) is SecurityStop.NONE


# ---- 8) bounded retry for a proven pre-request 503 --------------------------------------
def _policy(**over):
    d = dict(max_attempts=3, total_budget_ms=60_000, per_attempt_timeout_ms=5_000,
             retryable_errors=["http_503", "connection_reset"], idempotency_key="crq-1")
    d.update(over)
    return RetryPolicy(**d)


def _ctx(**over):
    d = dict(attempt_number=1, elapsed_ms=1_000, remaining_deadline_ms=30_000, failure_class="http_503",
             timeout_class=TimeoutClass.SAFE_TO_RETRY, security_stop=SecurityStop.NONE, authorized=True,
             one_active_owner=True, proven_non_start=False, retry_after_ms=None)
    d.update(over)
    return RetryContext(**d)


def test_proven_pre_request_503_is_bounded_retry():
    assert retry_eligibility(_policy(), _ctx()) is RetryDecision.RETRY
    assert compute_backoff_ms(1, 200) == 200 and compute_backoff_ms(3, 200) == 800
    # each blocking condition is distinct
    assert retry_eligibility(_policy(), _ctx(security_stop=SecurityStop.HUMAN_VERIFICATION_REQUIRED)) is RetryDecision.SECURITY_STOP_BLOCK
    assert retry_eligibility(_policy(), _ctx(timeout_class=TimeoutClass.UNKNOWN_OUTCOME)) is RetryDecision.UNKNOWN_OUTCOME_BLOCK
    assert retry_eligibility(_policy(), _ctx(failure_class="http_400")) is RetryDecision.NOT_RETRYABLE
    assert retry_eligibility(_policy(), _ctx(authorized=False)) is RetryDecision.UNAUTHORIZED
    assert retry_eligibility(_policy(), _ctx(one_active_owner=False)) is RetryDecision.MULTIPLE_OWNERS
    assert retry_eligibility(_policy(), _ctx(attempt_number=3)) is RetryDecision.MAX_ATTEMPTS_EXCEEDED


def test_retry_requires_proven_non_start_or_idempotency_key():
    # default policy carries an idempotency_key -> a non-proven-non-start retry may proceed
    assert retry_eligibility(_policy(), _ctx(proven_non_start=False)) is RetryDecision.RETRY
    # no idempotency key AND not proven non-start -> refuse to replay a possible side effect
    assert retry_eligibility(_policy(idempotency_key=None), _ctx(proven_non_start=False)) is RetryDecision.NOT_IDEMPOTENT_UNPROVEN
    # no idempotency key but PROVEN non-start -> may proceed
    assert retry_eligibility(_policy(idempotency_key=None), _ctx(proven_non_start=True)) is RetryDecision.RETRY


def test_retry_time_cost_must_fit_deadline_and_budget():
    # deadline can't hold the next backoff + one per-attempt timeout (200 + 5000 > 4000) -> DEADLINE_EXCEEDED
    assert retry_eligibility(_policy(), _ctx(remaining_deadline_ms=4_000)) is RetryDecision.DEADLINE_EXCEEDED
    # deadline is fine, but elapsed + backoff + attempt timeout exceeds the total budget
    assert retry_eligibility(_policy(total_budget_ms=5_500), _ctx(elapsed_ms=1_000, remaining_deadline_ms=30_000)) is RetryDecision.BUDGET_EXCEEDED
    # Retry-After sits inside the deadline, but Retry-After + attempt timeout overflows it -> DEADLINE_EXCEEDED
    assert retry_eligibility(_policy(), _ctx(retry_after_ms=8_000, remaining_deadline_ms=10_000)) is RetryDecision.DEADLINE_EXCEEDED
    # a comfortable window succeeds
    assert retry_eligibility(_policy(), _ctx(retry_after_ms=1_000, remaining_deadline_ms=30_000)) is RetryDecision.RETRY


# ---- 9) Retry-After exceeding the task deadline -----------------------------------------
def test_retry_after_exceeding_deadline_creates_no_new_attempt():
    # Retry-After 60s but only 30s of task deadline remain -> no new Attempt
    assert retry_eligibility(_policy(), _ctx(retry_after_ms=60_000, remaining_deadline_ms=30_000)) is RetryDecision.RETRY_DEFERRED
    # deadline already blown
    assert retry_eligibility(_policy(), _ctx(remaining_deadline_ms=0)) is RetryDecision.DEADLINE_EXCEEDED


def test_backoff_jitter_never_produces_negative_wait():
    assert compute_backoff_ms(1, 200, jitter_ms=-10_000) >= 0
    assert compute_backoff_ms(2, 200, jitter_ms=50) == 400 + 50


# ---- 8b) enforced Day63 final-fence gates for RETRY / RELEASE ----------------------------
def _fence(**over):
    meta = SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)
    d = dict(meta=meta, worker_token="wtok-1", claimed_version=3, attempt_id="att-1", now=NOW)
    d.update(over)
    return FenceInputs(**d)


def _bad_fences():
    return {
        "session_revoked": _fence(meta=SessionMeta("revoked", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)),
        "session_expired": _fence(meta=SessionMeta("active", NOW - 1, 3, "att-1", "wtok-1", NOW + 50)),
        "lease_owner_mismatch": _fence(meta=SessionMeta("active", NOW + 100, 3, "other", "wtok-1", NOW + 50)),
        "lease_token_mismatch": _fence(meta=SessionMeta("active", NOW + 100, 3, "att-1", "wrong", NOW + 50)),
        "lease_expired": _fence(meta=SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW - 1)),
        "version_mismatch": _fence(claimed_version=99),
    }


def test_authorization_still_valid_uses_full_fence():
    assert authorization_still_valid(_fence()) is True
    for name, bad in _bad_fences().items():
        assert authorization_still_valid(bad) is False, name


def test_authorize_retry_recomputes_authorized_from_fence_not_caller_flag():
    # a caller-supplied authorized=True can NOT bypass a failing fence
    for name, bad in _bad_fences().items():
        assert authorize_retry(_policy(), _ctx(authorized=True), bad) is RetryDecision.UNAUTHORIZED, name
    # only a valid fence permits RETRY — even when the caller forgot to set authorized
    assert authorize_retry(_policy(), _ctx(authorized=False), _fence()) is RetryDecision.RETRY


def test_authorize_credential_release_recomputes_session_valid_from_fence():
    req = CredentialRequest("tenantA", "sessA", "att-1", ORIGIN, "export")
    ctx = ReleaseContext("tenantA", "sessA", "att-1", [ORIGIN], session_valid=True)
    # a caller-supplied session_valid=True can NOT bypass a failing fence
    for name, bad in _bad_fences().items():
        assert authorize_credential_release(req, ctx, bad) is ReleaseDecision.DENY_SESSION_INVALID, name
    # a valid fence permits RELEASE even when the caller passed session_valid=False
    ctx_false = ReleaseContext("tenantA", "sessA", "att-1", [ORIGIN], session_valid=False)
    assert authorize_credential_release(req, ctx_false, _fence()) is ReleaseDecision.RELEASE


# ---- 10) incident classification (wildcard rollback) ------------------------------------
def test_incident_classification_and_flow():
    assert incident_phases() == ("contain", "scope", "classify", "repair", "controlled_rollout")
    assert classify_incident_item(evidence_complete=True, navigated_unapproved=False,
                                  credential_released=False, artifact_published=False) is IncidentClass.BLOCKED_BEFORE_NAVIGATION
    assert classify_incident_item(evidence_complete=True, navigated_unapproved=True,
                                  credential_released=False, artifact_published=False) is IncidentClass.UNAPPROVED_NAVIGATION_NO_CREDENTIAL_RELEASE
    assert classify_incident_item(evidence_complete=True, navigated_unapproved=True,
                                  credential_released=True, artifact_published=False) is IncidentClass.POSSIBLE_CREDENTIAL_EXPOSURE
    assert classify_incident_item(evidence_complete=True, navigated_unapproved=True,
                                  credential_released=True, artifact_published=True) is IncidentClass.PUBLISHED_ARTIFACT_AFFECTED
    assert classify_incident_item(evidence_complete=False, navigated_unapproved=True,
                                  credential_released=True, artifact_published=True) is IncidentClass.UNKNOWN
    assert unknown_may_blind_retry() is False
