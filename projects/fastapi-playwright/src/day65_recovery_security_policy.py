"""Day65 — pure Browser Failure-Recovery + Security-Boundary decision core (standard library only).

Turns Day64's trusted-Artifact browser flow into a RECOVERABLE, SECURITY-BOUNDED capability. It is a
DECISION CORE only — separated from any real Playwright/Object-Storage/PostgreSQL/Worker runtime so the
RULES are unit-testable WITHOUT a browser, a bucket, a database, or a queue. It REUSES the Day63 final
fence (``day63_session_gate.final_fence``) to revalidate authorization before a retry or a credential
release, and it preserves the Day64 strict action identity for reconciliation.

Ten decision areas (one per classroom exercise):
  1. timeout classification: a possible POST-ACTION timeout is ``UNKNOWN_OUTCOME``, never
     ``SAFE_TO_RETRY`` — "no observed completion != proven operation failure".
  2. unknown-outcome reconciliation: match the ORIGINAL action by strict Day64 identity
     (``client_request_id``/``report_id``/verified ``export_id``) + a server status/audit lookup — never
     a broad URL + HTTP 200.
  3. diagnostics: minimal, redacted, private, access-controlled, retention-bounded, audited — NEVER in
     ordinary logs, model context, prompts, or public Artifacts. A screenshot proves page DISPLAY only.
  4. navigation / SSRF: validate scheme + exact Origin (host+port) + resolved IP + task scope; block
     loopback / private / link-local / cloud-metadata; revalidate every redirect and DNS/IP change.
  5. credential release: current tenant/session/attempt + approved Origin + explicit purpose + validity
     + least privilege; cross-Origin navigation NEVER forwards storage state.
  6. instruction authority: only the task contract + server-side policy authorize target/operation/
     data/credentials/upload; DOM/page/download/network/model output are untrusted -> overreach is
     ``PROMPT_INJECTION_BLOCKED``.
  7. CAPTCHA: ``HUMAN_VERIFICATION_REQUIRED`` — never bypass/evade/outsource/disguise as retryable.
  8. bounded retry eligibility: explicit retryable class + proven non-start/idempotency + no
     ``UNKNOWN_OUTCOME`` + no security stop + valid authorization + remaining deadline/budget + ONE owner.
  9. Retry-After vs deadline: a ``Retry-After`` beyond the remaining task deadline ends the task
     (``RETRY_DEFERRED``/``DEADLINE_EXCEEDED``) — never a new Attempt.
 10. incident classification: ``contain -> scope -> classify -> repair -> controlled rollout``;
     ``UNKNOWN`` is reconciled/investigated, never blindly retried.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``tests/test_day65_recovery_security_policy.py``. They prove the RULES only — NOT real Playwright
timeout/reconciliation, real trace/screenshot redaction, real redirect/DNS/IP enforcement, real
storage-state/Cookie behaviour, real CAPTCHA handling, a real audit lookup, a real Worker/queue,
integration, or production (all NOT RUN — see the design/runbook). The live classroom artifact was
``CONCEPTUAL_STATIC``. No secrets, real credentials, real target URLs, Cookies, tokens, customer data,
raw sensitive payloads, screenshots, or CAPTCHA-bypass logic live here.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import List, Optional, Sequence

from day63_session_gate import Outcome, SessionMeta, final_fence


# ---------------------------------------------------------------------------
# 1) Timeout classification — no observed completion != proven failure.
# ---------------------------------------------------------------------------
class TimeoutClass(str, Enum):
    SAFE_TO_RETRY = "SAFE_TO_RETRY"        # proven the action never started (e.g. pre-request failure)
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"    # the action may have executed; do NOT blind-retry


def classify_timeout(action_request_sent: bool, response_observed: bool,
                     proven_non_start: bool = False) -> TimeoutClass:
    """A POST-ACTION timeout (the request left, no response observed) is ``UNKNOWN_OUTCOME`` — a missing
    captured response is not proof the server never accepted the action. Only a PROVEN non-start (the
    request never left / a confirmed pre-request failure) is ``SAFE_TO_RETRY``."""
    if proven_non_start or not action_request_sent:
        return TimeoutClass.SAFE_TO_RETRY
    if response_observed:
        return TimeoutClass.SAFE_TO_RETRY   # a full observed outcome is not "unknown"
    return TimeoutClass.UNKNOWN_OUTCOME


# ---------------------------------------------------------------------------
# 2) Unknown-outcome reconciliation by strict Day64 action identity.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActionIdentity:
    allowed_origin: str
    method: str
    normalized_endpoint: str
    report_id: str
    client_request_id: str
    export_id: Optional[str] = None   # set ONLY for a follow-up query already bound to this initial action


@dataclass(frozen=True)
class ServerActionRecord:
    """An authoritative server-side status/audit record, looked up by OUR FULL action identity — not by
    a broad URL match. The record MUST carry every security field needed to prove it is the SAME Origin,
    the SAME HTTP method, the SAME normalized endpoint, the SAME report, the SAME initial
    ``client_request_id`` and, when that phase uses it, the SAME verified ``export_id``. ``found=False``
    with ``authoritative_negative=True`` means the server proved the action never started."""
    found: bool
    allowed_origin: Optional[str]
    method: Optional[str]
    normalized_endpoint: Optional[str]
    report_id: Optional[str]
    client_request_id: Optional[str]
    status: Optional[str]                  # e.g. "completed" / "accepted" / "not_found"
    export_id: Optional[str] = None
    authoritative_negative: bool = False


class ReconcileResult(str, Enum):
    CONFIRMED_COMPLETED = "CONFIRMED_COMPLETED"    # server proves the original action completed
    CONFIRMED_NOT_STARTED = "CONFIRMED_NOT_STARTED"  # server proves it never started -> now safe to retry
    STILL_UNKNOWN = "STILL_UNKNOWN"                # cannot prove either way -> reconcile/investigate


def reconcile_unknown(expected: ActionIdentity, record: ServerActionRecord) -> ReconcileResult:
    """Reconcile an ``UNKNOWN_OUTCOME`` by matching the ORIGINAL action's FULL strict identity against an
    authoritative server record. EVERY security field must match exactly — a different Origin, HTTP
    method, normalized endpoint, ``report_id``, or ``client_request_id`` means this is NOT our action
    (never a broad URL + 200) -> STILL_UNKNOWN. The initial action is ALWAYS keyed by
    ``client_request_id``; a non-empty ``export_id`` can NEVER substitute for that match. When the
    follow-up phase carries a verified ``export_id`` (``expected.export_id`` is set), the record's
    ``export_id`` must ALSO match exactly and be bound to the same initial identity."""
    if not record.found:
        return ReconcileResult.CONFIRMED_NOT_STARTED if record.authoritative_negative else ReconcileResult.STILL_UNKNOWN
    # Full strict-identity match, always keyed on the initial client_request_id.
    if (
        record.allowed_origin != expected.allowed_origin
        or record.method != expected.method
        or record.normalized_endpoint != expected.normalized_endpoint
        or record.report_id != expected.report_id
        or record.client_request_id != expected.client_request_id
    ):
        return ReconcileResult.STILL_UNKNOWN   # a different action; do not attribute it to ours
    # Verified-export phase: a bound export_id must match exactly (it never replaces the crid match above).
    if expected.export_id is not None:
        if record.export_id is None or record.export_id != expected.export_id:
            return ReconcileResult.STILL_UNKNOWN
    if record.status in ("completed", "accepted", "imported"):
        return ReconcileResult.CONFIRMED_COMPLETED
    if record.status in ("not_found", "never_started"):
        return ReconcileResult.CONFIRMED_NOT_STARTED
    return ReconcileResult.STILL_UNKNOWN


# ---------------------------------------------------------------------------
# 3) Diagnostics — minimal, redacted, private, audited; never logs/model/public.
# ---------------------------------------------------------------------------
class DiagnosticDestination(str, Enum):
    PRIVATE_AUDITED_STORE = "PRIVATE_AUDITED_STORE"   # the ONLY acceptable destination
    ORDINARY_LOG = "ORDINARY_LOG"
    MODEL_CONTEXT = "MODEL_CONTEXT"
    PROMPT = "PROMPT"
    PUBLIC_ARTIFACT = "PUBLIC_ARTIFACT"


class DiagnosticDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY_DESTINATION = "DENY_DESTINATION"   # ordinary log / model context / prompt / public artifact
    DENY_UNREDACTED = "DENY_UNREDACTED"
    DENY_NOT_ACCESS_CONTROLLED = "DENY_NOT_ACCESS_CONTROLLED"
    DENY_UNBOUNDED_RETENTION = "DENY_UNBOUNDED_RETENTION"
    DENY_NOT_AUDITED = "DENY_NOT_AUDITED"


def diagnostics_decision(
    destination: DiagnosticDestination,
    *,
    contains_sensitive: bool,
    redacted: bool,
    access_controlled: bool,
    retention_bounded: bool,
    audited: bool,
) -> DiagnosticDecision:
    """Screenshots, traces, headers, raw payloads, DOM, Cookies, Authorization, tokens, PII and tenant
    data may be sensitive. Diagnostics may ONLY go to a private, access-controlled, retention-bounded,
    audited store, redacted when they contain sensitive material — NEVER an ordinary log, the model
    context, a prompt, or a public Artifact."""
    if destination is not DiagnosticDestination.PRIVATE_AUDITED_STORE:
        return DiagnosticDecision.DENY_DESTINATION
    if contains_sensitive and not redacted:
        return DiagnosticDecision.DENY_UNREDACTED
    if not access_controlled:
        return DiagnosticDecision.DENY_NOT_ACCESS_CONTROLLED
    if not retention_bounded:
        return DiagnosticDecision.DENY_UNBOUNDED_RETENTION
    if not audited:
        return DiagnosticDecision.DENY_NOT_AUDITED
    return DiagnosticDecision.ALLOW


def screenshot_proves_publication() -> bool:
    """A screenshot proves page DISPLAY only; it does NOT prove Export or Artifact publication success."""
    return False


# ---------------------------------------------------------------------------
# 4) Navigation / SSRF gate — scheme + exact Origin + resolved IP + scope.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NavigationRequest:
    scheme: str
    hostname: str
    port: int
    resolved_ip: str          # the IP the hostname RESOLVED to (revalidated on DNS/IP change)


class NavigationDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCKED_SCHEME = "BLOCKED_SCHEME"
    BLOCKED_ORIGIN = "BLOCKED_ORIGIN"       # not an EXACT approved origin (scheme+host+port)
    BLOCKED_IP = "BLOCKED_IP"               # loopback/private/link-local/cloud-metadata/reserved


def is_prohibited_ip(ip: str) -> bool:
    """Block loopback, private, link-local (incl. the 169.254.169.254 cloud-metadata address),
    reserved, multicast, and unspecified targets by their RESOLVED IP."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True   # an unparseable/absent resolved IP is not provably safe -> block
    return (addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved
            or addr.is_multicast or addr.is_unspecified)


def _origin(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{host}:{port}"


def navigation_allowed(
    nav: NavigationRequest,
    approved_origins: Sequence[str],
    *,
    allowed_schemes: Sequence[str] = ("https",),
) -> NavigationDecision:
    """Server-side navigation policy (page content is untrusted input, not authorization). Requires an
    allowed scheme, an EXACT approved Origin (scheme + host + port), and a non-prohibited resolved IP."""
    if nav.scheme not in allowed_schemes:
        return NavigationDecision.BLOCKED_SCHEME
    if _origin(nav.scheme, nav.hostname, nav.port) not in set(approved_origins):
        return NavigationDecision.BLOCKED_ORIGIN
    if is_prohibited_ip(nav.resolved_ip):
        return NavigationDecision.BLOCKED_IP
    return NavigationDecision.ALLOW


def validate_redirect_chain(
    hops: Sequence[NavigationRequest],
    approved_origins: Sequence[str],
    *,
    allowed_schemes: Sequence[str] = ("https",),
) -> NavigationDecision:
    """Revalidate EVERY redirect hop and DNS/IP change with the same policy; the first blocked hop
    stops the chain."""
    for hop in hops:
        d = navigation_allowed(hop, approved_origins, allowed_schemes=allowed_schemes)
        if d is not NavigationDecision.ALLOW:
            return d
    return NavigationDecision.ALLOW


# ---------------------------------------------------------------------------
# 5) Credential release — scoped capability, never browser-task data.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CredentialRequest:
    tenant_id: str
    session_id: str
    attempt_id: str
    target_origin: str
    purpose: Optional[str]


@dataclass(frozen=True)
class ReleaseContext:
    current_tenant: str
    current_session: str
    current_attempt: str
    approved_origins: Sequence[str]
    session_valid: bool


class ReleaseDecision(str, Enum):
    RELEASE = "RELEASE"
    DENY_TENANT_MISMATCH = "DENY_TENANT_MISMATCH"
    DENY_SESSION_MISMATCH = "DENY_SESSION_MISMATCH"
    DENY_ATTEMPT_MISMATCH = "DENY_ATTEMPT_MISMATCH"
    DENY_ORIGIN_NOT_APPROVED = "DENY_ORIGIN_NOT_APPROVED"
    DENY_NO_PURPOSE = "DENY_NO_PURPOSE"
    DENY_SESSION_INVALID = "DENY_SESSION_INVALID"


def credential_release_allowed(req: CredentialRequest, ctx: ReleaseContext) -> ReleaseDecision:
    """Credentials are protected, scoped capabilities — not browser-task data. Release requires the
    CURRENT tenant/session/attempt, an approved target Origin, an explicit purpose, a valid session,
    and least privilege."""
    if req.tenant_id != ctx.current_tenant:
        return ReleaseDecision.DENY_TENANT_MISMATCH
    if req.session_id != ctx.current_session:
        return ReleaseDecision.DENY_SESSION_MISMATCH
    if req.attempt_id != ctx.current_attempt:
        return ReleaseDecision.DENY_ATTEMPT_MISMATCH
    if not ctx.session_valid:
        return ReleaseDecision.DENY_SESSION_INVALID
    if req.target_origin not in set(ctx.approved_origins):
        return ReleaseDecision.DENY_ORIGIN_NOT_APPROVED
    if not req.purpose:
        return ReleaseDecision.DENY_NO_PURPOSE
    return ReleaseDecision.RELEASE


def cross_origin_forwards_storage_state() -> bool:
    """Cross-Origin navigation does NOT copy, export, or forward storage state."""
    return False


# ---------------------------------------------------------------------------
# 6) Instruction authority — task contract + server policy only; else injection.
# ---------------------------------------------------------------------------
class InstructionSource(str, Enum):
    TASK_CONTRACT = "TASK_CONTRACT"        # authoritative
    SERVER_POLICY = "SERVER_POLICY"        # authoritative
    DOM = "DOM"                            # untrusted
    PAGE_TEXT = "PAGE_TEXT"                # untrusted
    DOWNLOAD = "DOWNLOAD"                  # untrusted
    NETWORK_RESPONSE = "NETWORK_RESPONSE"  # untrusted
    MODEL_OUTPUT = "MODEL_OUTPUT"          # untrusted


_AUTHORITATIVE_SOURCES = frozenset({InstructionSource.TASK_CONTRACT, InstructionSource.SERVER_POLICY})


class InstructionDecision(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    PROMPT_INJECTION_BLOCKED = "PROMPT_INJECTION_BLOCKED"   # untrusted source directing an action
    OUT_OF_CONTRACT = "OUT_OF_CONTRACT"                     # authoritative source, action not in scope


def instruction_authorized(
    source: InstructionSource,
    requested_action: str,
    contract_allowed_actions: Sequence[str],
) -> InstructionDecision:
    """The task contract and server-side policy are the SOLE authority for target, operation, data
    scope, credentials, and upload destination. DOM, page text, downloads, network responses, and model
    output are untrusted data; an action they request beyond the contract is ``PROMPT_INJECTION_BLOCKED``."""
    if source not in _AUTHORITATIVE_SOURCES:
        return InstructionDecision.PROMPT_INJECTION_BLOCKED
    if requested_action not in set(contract_allowed_actions):
        return InstructionDecision.OUT_OF_CONTRACT
    return InstructionDecision.AUTHORIZED


# ---------------------------------------------------------------------------
# 7) CAPTCHA / human review — never bypass.
# ---------------------------------------------------------------------------
class SecurityStop(str, Enum):
    NONE = "NONE"
    HUMAN_VERIFICATION_REQUIRED = "HUMAN_VERIFICATION_REQUIRED"


def classify_captcha(captcha_detected: bool) -> SecurityStop:
    """A CAPTCHA is ``HUMAN_VERIFICATION_REQUIRED``: do not bypass, evade, outsource, or disguise it as
    a retryable business failure."""
    return SecurityStop.HUMAN_VERIFICATION_REQUIRED if captcha_detected else SecurityStop.NONE


def is_security_stop(stop: SecurityStop) -> bool:
    return stop is not SecurityStop.NONE


def is_retryable_business_failure(stop: SecurityStop) -> bool:
    """A security stop is NEVER a retryable business failure."""
    return False if is_security_stop(stop) else True


# ---------------------------------------------------------------------------
# 8/9) Bounded retry eligibility + Retry-After vs deadline.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    total_budget_ms: int
    per_attempt_timeout_ms: int
    retryable_errors: Sequence[str]
    idempotency_key: Optional[str]
    base_backoff_ms: int = 200


@dataclass(frozen=True)
class RetryContext:
    attempt_number: int          # 1-based; the attempt that just failed
    elapsed_ms: int
    remaining_deadline_ms: int
    failure_class: str
    timeout_class: TimeoutClass
    security_stop: SecurityStop
    authorized: bool             # RECOMPUTED from the Day63 fence by authorize_retry() — not caller-trusted
    one_active_owner: bool
    proven_non_start: bool = False   # the action is PROVEN never to have started (side-effect-free replay)
    retry_after_ms: Optional[int] = None


class RetryDecision(str, Enum):
    RETRY = "RETRY"
    SECURITY_STOP_BLOCK = "SECURITY_STOP_BLOCK"
    UNKNOWN_OUTCOME_BLOCK = "UNKNOWN_OUTCOME_BLOCK"   # reconcile first; never blind-retry
    NOT_RETRYABLE = "NOT_RETRYABLE"
    NOT_IDEMPOTENT_UNPROVEN = "NOT_IDEMPOTENT_UNPROVEN"  # neither proven non-start NOR a usable idempotency key
    UNAUTHORIZED = "UNAUTHORIZED"
    MULTIPLE_OWNERS = "MULTIPLE_OWNERS"
    MAX_ATTEMPTS_EXCEEDED = "MAX_ATTEMPTS_EXCEEDED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"           # wait + one attempt timeout won't fit the deadline
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"               # elapsed + wait + one attempt timeout won't fit budget
    RETRY_DEFERRED = "RETRY_DEFERRED"                 # Retry-After beyond the deadline -> no new Attempt


def compute_backoff_ms(attempt_number: int, base_backoff_ms: int, jitter_ms: int = 0) -> int:
    """Exponential backoff with (caller-supplied, deterministic) jitter: ``base * 2^(n-1) + jitter``,
    safely clamped so a negative jitter can NEVER produce a negative wait."""
    n = max(1, attempt_number)
    return max(0, base_backoff_ms * (2 ** (n - 1)) + jitter_ms)


def _next_retry_delay_ms(policy: RetryPolicy, ctx: RetryContext) -> int:
    """The conservative wait before the next attempt: the LARGER of the local (nominal, jitter-free)
    exponential backoff and any server ``Retry-After`` — clamped so it is never negative."""
    backoff = compute_backoff_ms(ctx.attempt_number, policy.base_backoff_ms)
    server_wait = ctx.retry_after_ms if ctx.retry_after_ms is not None else 0
    return max(0, backoff, server_wait)


def retry_eligibility(policy: RetryPolicy, ctx: RetryContext) -> RetryDecision:
    """A bounded retry needs, in order: NO security stop; NO ``UNKNOWN_OUTCOME`` (reconcile first); an
    explicit retryable failure class; a PROVEN non-start OR a usable ``idempotency_key``; valid
    tenant/session/lease/task authorization; exactly ONE active owner; attempts left; and the FULL time
    cost — the conservative wait (max of nominal backoff and ``Retry-After``) PLUS one
    ``per_attempt_timeout_ms`` — still fitting inside BOTH the remaining task deadline AND the total
    budget. A ``Retry-After`` beyond the remaining deadline is ``RETRY_DEFERRED`` (never a new Attempt)."""
    if is_security_stop(ctx.security_stop):
        return RetryDecision.SECURITY_STOP_BLOCK
    if ctx.timeout_class is TimeoutClass.UNKNOWN_OUTCOME:
        return RetryDecision.UNKNOWN_OUTCOME_BLOCK
    if ctx.failure_class not in set(policy.retryable_errors):
        return RetryDecision.NOT_RETRYABLE
    if not ctx.proven_non_start and not policy.idempotency_key:
        return RetryDecision.NOT_IDEMPOTENT_UNPROVEN   # unsafe to replay a possible side effect
    if not ctx.authorized:
        return RetryDecision.UNAUTHORIZED
    if not ctx.one_active_owner:
        return RetryDecision.MULTIPLE_OWNERS
    if ctx.attempt_number >= policy.max_attempts:
        return RetryDecision.MAX_ATTEMPTS_EXCEEDED
    if ctx.remaining_deadline_ms <= 0 or ctx.elapsed_ms >= policy.total_budget_ms:
        return RetryDecision.DEADLINE_EXCEEDED
    # A Retry-After that alone exceeds the remaining deadline defers the task with no new Attempt.
    if ctx.retry_after_ms is not None and ctx.retry_after_ms > ctx.remaining_deadline_ms:
        return RetryDecision.RETRY_DEFERRED
    delay = _next_retry_delay_ms(policy, ctx)
    cost = delay + policy.per_attempt_timeout_ms
    # The next wait AND the next per-attempt timeout must both fit inside the remaining deadline ...
    if cost > ctx.remaining_deadline_ms:
        return RetryDecision.DEADLINE_EXCEEDED
    # ... and inside the total time budget once elapsed time is included.
    if ctx.elapsed_ms + cost > policy.total_budget_ms:
        return RetryDecision.BUDGET_EXCEEDED
    return RetryDecision.RETRY


# ---------------------------------------------------------------------------
# 8b) Enforced Day63-fence gates for RETRY and credential RELEASE.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FenceInputs:
    """The Day63 ``final_fence`` inputs re-checked BEFORE any RETRY or credential RELEASE."""
    meta: SessionMeta
    worker_token: str
    claimed_version: int
    attempt_id: str
    now: int
    timed_out: bool = False


def authorization_still_valid(fence: FenceInputs) -> bool:
    """Revalidate the Day63 final fence (active + session-expiry + lease_owner + lease_token +
    lease_expires_at + version). This is the SINGLE source of the ``authorized`` / ``session_valid``
    truth used by the enforced gates below — a caller can NOT bypass it with a hand-written flag."""
    return final_fence(fence.meta, fence.worker_token, fence.claimed_version, fence.attempt_id,
                       fence.now, timed_out=fence.timed_out) is Outcome.AUTHORIZED


def authorize_retry(policy: RetryPolicy, ctx: RetryContext, fence: FenceInputs) -> RetryDecision:
    """ENFORCED retry entry point. It RECOMPUTES ``authorized`` from the live Day63 ``final_fence`` and
    IGNORES any ``ctx.authorized`` the caller supplied, so ``RETRY`` is possible ONLY while the fence
    currently returns ``AUTHORIZED`` (a revoked/expired session, a lost/expired lease, or a superseded
    token/version can never be retried)."""
    enforced = replace(ctx, authorized=authorization_still_valid(fence))
    return retry_eligibility(policy, enforced)


def authorize_credential_release(req: CredentialRequest, ctx: ReleaseContext,
                                 fence: FenceInputs) -> ReleaseDecision:
    """ENFORCED credential-release entry point. It RECOMPUTES ``session_valid`` from the live Day63
    ``final_fence`` and IGNORES any ``ctx.session_valid`` the caller supplied, so credentials are
    released ONLY while the fence currently returns ``AUTHORIZED``."""
    enforced = replace(ctx, session_valid=authorization_still_valid(fence))
    return credential_release_allowed(req, enforced)


# ---------------------------------------------------------------------------
# 10) Incident classification — contain -> scope -> classify -> repair -> rollout.
# ---------------------------------------------------------------------------
class IncidentClass(str, Enum):
    BLOCKED_BEFORE_NAVIGATION = "BLOCKED_BEFORE_NAVIGATION"
    UNAPPROVED_NAVIGATION_NO_CREDENTIAL_RELEASE = "UNAPPROVED_NAVIGATION_NO_CREDENTIAL_RELEASE"
    POSSIBLE_CREDENTIAL_EXPOSURE = "POSSIBLE_CREDENTIAL_EXPOSURE"
    PUBLISHED_ARTIFACT_AFFECTED = "PUBLISHED_ARTIFACT_AFFECTED"
    UNKNOWN = "UNKNOWN"


def classify_incident_item(
    *,
    evidence_complete: bool,
    navigated_unapproved: bool,
    credential_released: bool,
    artifact_published: bool,
) -> IncidentClass:
    """Scope past harm from ACTUALLY-preserved evidence. Incomplete evidence is ``UNKNOWN`` (reconciled
    and investigated, never blindly retried)."""
    if not evidence_complete:
        return IncidentClass.UNKNOWN
    if artifact_published and navigated_unapproved:
        return IncidentClass.PUBLISHED_ARTIFACT_AFFECTED
    if navigated_unapproved and credential_released:
        return IncidentClass.POSSIBLE_CREDENTIAL_EXPOSURE
    if navigated_unapproved:
        return IncidentClass.UNAPPROVED_NAVIGATION_NO_CREDENTIAL_RELEASE
    return IncidentClass.BLOCKED_BEFORE_NAVIGATION


def incident_phases() -> tuple:
    """The incident flow: contain -> scope -> classify -> repair -> controlled rollout."""
    return ("contain", "scope", "classify", "repair", "controlled_rollout")


def unknown_may_blind_retry() -> bool:
    """An ``UNKNOWN`` incident item is reconciled/investigated — never blindly retried."""
    return False
