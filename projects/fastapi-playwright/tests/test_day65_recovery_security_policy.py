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
    ReconcileResult,
    ReleaseContext,
    ReleaseDecision,
    RetryContext,
    RetryDecision,
    RetryPolicy,
    SecurityStop,
    ServerActionRecord,
    TimeoutClass,
    authorization_still_valid,
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
def test_reconcile_uses_strict_identity_not_broad_match():
    expected = ActionIdentity(ORIGIN, "POST", "/api/exports", "42", "crq-1")
    completed = ServerActionRecord(True, "crq-1", "42", "completed")
    assert reconcile_unknown(expected, completed) is ReconcileResult.CONFIRMED_COMPLETED
    # a DIFFERENT action's record (wrong client_request_id) must NOT be attributed to ours
    other = ServerActionRecord(True, "crq-other", "42", "completed")
    assert reconcile_unknown(expected, other) is ReconcileResult.STILL_UNKNOWN
    # authoritative negative proves non-start -> now safe to retry
    negative = ServerActionRecord(False, None, None, "not_found", authoritative_negative=True)
    assert reconcile_unknown(expected, negative) is ReconcileResult.CONFIRMED_NOT_STARTED
    # a non-authoritative miss stays unknown
    miss = ServerActionRecord(False, None, None, None, authoritative_negative=False)
    assert reconcile_unknown(expected, miss) is ReconcileResult.STILL_UNKNOWN


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
             one_active_owner=True, retry_after_ms=None)
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


# ---- 9) Retry-After exceeding the task deadline -----------------------------------------
def test_retry_after_exceeding_deadline_creates_no_new_attempt():
    # Retry-After 60s but only 30s of task deadline remain -> no new Attempt
    assert retry_eligibility(_policy(), _ctx(retry_after_ms=60_000, remaining_deadline_ms=30_000)) is RetryDecision.RETRY_DEFERRED
    # deadline already blown
    assert retry_eligibility(_policy(), _ctx(remaining_deadline_ms=0)) is RetryDecision.DEADLINE_EXCEEDED


def test_authorization_revalidated_before_retry():
    ok = SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)
    assert authorization_still_valid(ok, "wtok-1", 3, "att-1", NOW) is True
    revoked = SessionMeta("revoked", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)
    assert authorization_still_valid(revoked, "wtok-1", 3, "att-1", NOW) is False


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
