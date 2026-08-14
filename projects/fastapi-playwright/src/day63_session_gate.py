"""Day63 — pure Browser-Session authorization / claim decision core (standard library only).

The DECISION CORE for turning Day62's per-task ``BrowserContext`` ownership into an
AUTHENTICATED, tenant-bound, revocable browser-session capability — separated from any real
Playwright/PostgreSQL/credential-store runtime so the RULES are unit-testable WITHOUT a browser,
a database, or a secret store.

Model taught in class:
  * ``Tenant``         = business authorization/isolation scope (NOT a runtime isolation boundary).
  * ``BrowserSession`` = an explicit, tenant/owner/origin-bound, revocable authorization capability.
  * ``storage_state``  = reusable SENSITIVE authentication material — never proof of identity.
  * ``BrowserContext`` = one task's runtime state/isolation container; never shared live across
    tasks or tenants (Day62).
  * Lease/Fencing      = short-lived, attempt-owned CONTINUING authorization — not a one-time login.

The safe Task authorization pipeline (authoritative order):
  1. validate the trusted Job's ``session_id``/``tenant``/``target_origin`` binding;
  2. ATOMICALLY claim the Session for THIS ``attempt_id`` (active + not revoked + not expired +
     lease available) — this is the authoritative current-state/concurrency check;
  3. ONLY the winning Attempt reads/decrypts the protected credential reference;
  4. create a fresh Task ``BrowserContext`` from that storage state;
  5. at the approved Origin, verify a POSITIVE stable identity fact (``principal_id`` and, when
     present, ``organization_id``) against the expected Session binding;
  6. perform only allowed actions, with fencing/session checks before critical actions;
  7. a FINAL fencing check before result publication — publish only if still authorized;
  8. close the Context in ``finally`` on every path (never let cleanup hide the primary error).

Outcomes (each non-AUTHORIZED outcome BLOCKS business-result publication and NEVER becomes a
business ``no result`` nor permits a blind retry):
  * ``AUTHORIZED``                        — proceed.
  * ``AUTHENTICATION_PRECONDITION_FAILED`` — login redirect / inactive or expired / revoked Session,
    or an unbound Job.
  * ``AUTHORIZATION_SESSION_FAILURE``     — authenticated identity does not match the expected binding.
  * ``UNKNOWN_AUTHORIZATION_STATE``       — a lease/fencing check timed out (state unknown).
  * ``SECURITY_FAILURE``                  — an unapproved Origin navigation/popup was observed.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``tests/test_day63_session_gate.py`` (authored + run by the updating agent). They prove the RULES
only — NOT real Chromium state isolation, real PostgreSQL atomic claims, real credential
encryption/KMS/Object Storage, a real Worker, or production. Those are a separate INTEGRATION_RUNTIME
and are NOT RUN (see the design/runbook). The live classroom artifact was ``CONCEPTUAL_STATIC``.
No secrets, real credentials, real Origins, tenant data, or storage-state exports live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------
class Outcome(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    AUTHENTICATION_PRECONDITION_FAILED = "AUTHENTICATION_PRECONDITION_FAILED"
    AUTHORIZATION_SESSION_FAILURE = "AUTHORIZATION_SESSION_FAILURE"
    UNKNOWN_AUTHORIZATION_STATE = "UNKNOWN_AUTHORIZATION_STATE"
    SECURITY_FAILURE = "SECURITY_FAILURE"


NON_AUTHORIZED = frozenset(
    o for o in Outcome if o is not Outcome.AUTHORIZED
)


def blocks_publication(outcome: Outcome) -> bool:
    """Every non-AUTHORIZED outcome blocks business-result publication."""
    return outcome is not Outcome.AUTHORIZED


def may_blind_retry(outcome: Outcome) -> bool:
    """No outcome authorizes a blind retry. A precondition/authorization/security failure is not a
    business ``no result``, and an UNKNOWN state must be reconciled by an explicit Day65 policy,
    never re-driven blindly (a duplicate action could double an external effect)."""
    return False


# ---------------------------------------------------------------------------
# Data (all synthetic; no real identifiers)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SessionBinding:
    """The server-authorized binding recorded on a Job — a candidate ``session_id`` becomes this
    only after the API authorizes it. ``credential_ref`` is a PROTECTED reference, never the
    credential material."""
    tenant_id: str
    session_id: str
    target_origin: str
    owner: str                       # the approved owner (e.g. a service/user principal)
    expected_principal_id: str
    expected_organization_id: Optional[str]
    credential_ref: str


@dataclass(frozen=True)
class SessionMeta:
    """Server-side Session lifecycle + concurrency metadata (PostgreSQL in a real run)."""
    status: str                      # 'active' | 'inactive' | 'revoked'
    expires_at: int                  # epoch seconds
    version: int
    lease_owner: Optional[str]       # the attempt_id holding the lease, or None
    lease_token: Optional[str]
    lease_expires_at: Optional[int]  # epoch seconds


@dataclass(frozen=True)
class JobRequest:
    tenant_id: str
    session_id: str
    target_origin: str
    attempt_id: str


# ---------------------------------------------------------------------------
# 1) Job binding validation
# ---------------------------------------------------------------------------
def validate_job_binding(job: JobRequest, binding: SessionBinding) -> Outcome:
    """The Job must be bound to an approved Session for the SAME tenant/session/origin. A
    client-supplied ``session_id`` is only a candidate reference; a mismatch means the task has no
    approved session binding -> ``AUTHENTICATION_PRECONDITION_FAILED`` (never proceed)."""
    if (
        job.tenant_id == binding.tenant_id
        and job.session_id == binding.session_id
        and job.target_origin == binding.target_origin
    ):
        return Outcome.AUTHORIZED
    return Outcome.AUTHENTICATION_PRECONDITION_FAILED


# ---------------------------------------------------------------------------
# 2) Atomic claim (UPDATE ... RETURNING semantics, modeled purely)
# ---------------------------------------------------------------------------
class ClaimResult(str, Enum):
    CLAIMED = "CLAIMED"                       # this Attempt won the lease
    PRECONDITION_FAILED = "PRECONDITION_FAILED"   # inactive/revoked/expired session
    LEASE_HELD = "LEASE_HELD"                 # another Attempt holds an UNEXPIRED lease


def classify_claim(meta: SessionMeta, attempt_id: str, now: int) -> ClaimResult:
    """Model the authoritative ``UPDATE app.browser_sessions SET lease_owner=:a, lease_token=:t,
    lease_expires_at=:exp WHERE session_id=:s AND status='active' AND expires_at>:now AND
    (lease_owner IS NULL OR lease_owner=:a OR lease_expires_at<=:now) RETURNING ...`` decision.

    * inactive / revoked / expired            -> PRECONDITION_FAILED (no claim, no credential read).
    * another Attempt holds an UNEXPIRED lease -> LEASE_HELD (a second Attempt may NOT seize a
      still-unexpired lease just because the first looks unhealthy; it waits for expiry).
    * otherwise (free / self / expired lease)  -> CLAIMED (the winning Attempt).
    """
    if meta.status != "active" or meta.expires_at <= now:
        return ClaimResult.PRECONDITION_FAILED
    lease_active = (
        meta.lease_owner is not None
        and meta.lease_owner != attempt_id
        and meta.lease_expires_at is not None
        and meta.lease_expires_at > now
    )
    if lease_active:
        return ClaimResult.LEASE_HELD
    return ClaimResult.CLAIMED


def claim_result_to_outcome(claim: ClaimResult) -> Outcome:
    """A non-CLAIMED claim never proceeds. PRECONDITION_FAILED and LEASE_HELD both map to
    ``AUTHENTICATION_PRECONDITION_FAILED`` (the continuing-authorization precondition is not
    currently satisfiable for this Attempt) — never a business ``no result``."""
    if claim is ClaimResult.CLAIMED:
        return Outcome.AUTHORIZED
    return Outcome.AUTHENTICATION_PRECONDITION_FAILED


# ---------------------------------------------------------------------------
# 3) Storage-state allowlist filtering (Origin + Cookie domain)
# ---------------------------------------------------------------------------
def filter_storage_state(
    storage_state: Dict,
    approved_origin: str,
    approved_cookie_domains: List[str],
) -> Dict:
    """Filter an exported ``storage_state`` down to explicit allowlists BEFORE it is persisted or
    imported. Default REJECT: a Cookie whose domain is not in ``approved_cookie_domains`` and an
    origin entry not equal to ``approved_origin`` are dropped. Cross-subdomain SSO (e.g. saving a
    ``.example.com`` Cookie for ``research.example.com``) is an explicit, auditable exception —
    it happens only when that domain is present in the allowlist, never by default."""
    approved = set(approved_cookie_domains)
    cookies = [c for c in storage_state.get("cookies", []) if c.get("domain") in approved]
    origins = [o for o in storage_state.get("origins", []) if o.get("origin") == approved_origin]
    return {"cookies": cookies, "origins": origins}


# ---------------------------------------------------------------------------
# 4) Identity verification at the approved Origin
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ObservedIdentity:
    login_redirect: bool                 # True if the account/identity page redirected to login
    principal_id: Optional[str]          # a STABLE positive identity fact (None if unavailable)
    organization_id: Optional[str]
    display_name: Optional[str] = None   # MUTABLE — never sufficient on its own


def verify_identity(observed: ObservedIdentity, binding: SessionBinding) -> Outcome:
    """A POSITIVE stable identity fact must match the expected Session binding.

    * a login redirect          -> AUTHENTICATION_PRECONDITION_FAILED (session isn't authenticated).
    * no positive principal_id   -> AUTHORIZATION_SESSION_FAILURE (absence of a redirect is NOT proof;
      a mutable display name is NOT proof).
    * principal / org mismatch   -> AUTHORIZATION_SESSION_FAILURE.
    * exact match                -> AUTHORIZED.
    """
    if observed.login_redirect:
        return Outcome.AUTHENTICATION_PRECONDITION_FAILED
    if not observed.principal_id:
        return Outcome.AUTHORIZATION_SESSION_FAILURE
    if observed.principal_id != binding.expected_principal_id:
        return Outcome.AUTHORIZATION_SESSION_FAILURE
    if binding.expected_organization_id is not None and observed.organization_id != binding.expected_organization_id:
        return Outcome.AUTHORIZATION_SESSION_FAILURE
    return Outcome.AUTHORIZED


# ---------------------------------------------------------------------------
# 5) Origin/navigation security check
# ---------------------------------------------------------------------------
def check_navigation(observed_origin: str, approved_origin: str) -> Outcome:
    """Any navigation/popup to an Origin other than the approved business Origin is a
    ``SECURITY_FAILURE`` (the Context must be closed and the result never published). Being on a
    different subdomain of the same site is still unapproved unless it equals ``approved_origin``."""
    return Outcome.AUTHORIZED if observed_origin == approved_origin else Outcome.SECURITY_FAILURE


# ---------------------------------------------------------------------------
# 6) Final fencing check before publication
# ---------------------------------------------------------------------------
def final_fence(
    meta: SessionMeta,
    worker_token: str,
    claimed_version: int,
    now: int,
    *,
    timed_out: bool = False,
) -> Outcome:
    """The last gate before publishing a business result.

    * the fence check TIMED OUT            -> UNKNOWN_AUTHORIZATION_STATE (state unknown; do NOT
      publish and do NOT blind-retry).
    * session revoked/inactive or expired  -> AUTHENTICATION_PRECONDITION_FAILED.
    * lease token superseded or version bumped (a new Session version / re-claim) ->
      AUTHORIZATION_SESSION_FAILURE (this Attempt lost continuing authority).
    * still active + same token + same version -> AUTHORIZED (publish).
    """
    if timed_out:
        return Outcome.UNKNOWN_AUTHORIZATION_STATE
    if meta.status != "active" or meta.expires_at <= now:
        return Outcome.AUTHENTICATION_PRECONDITION_FAILED
    if meta.lease_token != worker_token or meta.version != claimed_version:
        return Outcome.AUTHORIZATION_SESSION_FAILURE
    return Outcome.AUTHORIZED


# ---------------------------------------------------------------------------
# 7) Connection-flow: a new verified login becomes a new Session version only after
#    protected-state persistence AND metadata/audit commit both succeed.
# ---------------------------------------------------------------------------
class PersistOutcome(str, Enum):
    ACTIVATED = "ACTIVATED"                       # protected state + metadata/audit committed
    ORPHAN_INACTIVE = "ORPHAN_INACTIVE"           # protected state saved, metadata tx failed
    REJECTED_NOT_VERIFIED = "REJECTED_NOT_VERIFIED"  # identity not verified before export


def classify_login_persist(identity_verified: bool, state_persisted: bool, metadata_committed: bool) -> PersistOutcome:
    """A verified login is exported, filtered, encrypted, and persisted; the Session becomes a new
    active version ONLY after the metadata/audit commit also succeeds. Never overwrite an old
    credential in place: a failed metadata transaction leaves a PROTECTED but INACTIVE
    candidate/orphan for reconciliation — never an active Session."""
    if not identity_verified:
        return PersistOutcome.REJECTED_NOT_VERIFIED           # do not export state before verifying
    if state_persisted and metadata_committed:
        return PersistOutcome.ACTIVATED
    return PersistOutcome.ORPHAN_INACTIVE


# ---------------------------------------------------------------------------
# Orchestrator — proves the NEGATIVE effects (rejected stages call nothing downstream)
# ---------------------------------------------------------------------------
@dataclass
class TaskDeps:
    """Injected side-effecting collaborators. In a real run these read the encrypted credential,
    build a real BrowserContext, probe identity, and publish the result. Here they are fakes so a
    test can assert exactly which were invoked (and, crucially, which were NOT)."""
    read_credential: Callable[[str], Dict]          # (credential_ref) -> storage_state
    create_context: Callable[[Dict], object]        # (filtered_storage_state) -> context
    probe_identity: Callable[[object], ObservedIdentity]
    observe_origin: Callable[[object], str]
    publish_result: Callable[[object], None]
    close_context: Callable[[object], None]


@dataclass
class TaskReport:
    outcome: Outcome
    published: bool
    invoked: List[str] = field(default_factory=list)   # names of deps actually called, in order
    primary_error: Optional[str] = None
    cleanup_error: Optional[str] = None


def run_task_authorization(
    job: JobRequest,
    binding: SessionBinding,
    meta: SessionMeta,
    deps: TaskDeps,
    *,
    now: int,
    worker_token: str,
    fence_meta: Optional[SessionMeta] = None,
    fence_timed_out: bool = False,
    approved_cookie_domains: Optional[List[str]] = None,
) -> TaskReport:
    """Run the Day63 authorization pipeline with injected deps and return a report that records
    exactly which side effects ran. Guarantees (each verified by a test):

      * a rejected binding or claim -> ``read_credential`` and ``create_context`` are NEVER called;
      * an identity mismatch / login redirect -> the browser business action is NEVER performed and
        nothing is published (Context still closed);
      * an unapproved Origin/popup -> Context closed, ``SECURITY_FAILURE``, nothing published;
      * a failed/UNKNOWN final fence -> the result is NEVER published;
      * the Context is closed in ``finally`` on every path, and a cleanup failure never hides the
        primary error.
    """
    invoked: List[str] = []

    # 1) binding
    o = validate_job_binding(job, binding)
    if o is not Outcome.AUTHORIZED:
        return TaskReport(o, published=False, invoked=invoked)

    # 2) atomic claim (authoritative concurrency/state check)
    claim = classify_claim(meta, job.attempt_id, now)
    if claim is not ClaimResult.CLAIMED:
        return TaskReport(claim_result_to_outcome(claim), published=False, invoked=invoked)

    # 3) ONLY the winning Attempt reads the protected credential
    storage_state = deps.read_credential(binding.credential_ref)
    invoked.append("read_credential")
    filtered = filter_storage_state(
        storage_state, binding.target_origin, approved_cookie_domains or [binding.target_origin]
    )

    context = None
    primary_error = None
    cleanup_error = None
    published = False
    outcome = Outcome.AUTHORIZED
    try:
        # 4) fresh Task Context from the filtered storage state
        context = deps.create_context(filtered)
        invoked.append("create_context")

        # 5) verify a POSITIVE identity fact at the approved Origin
        observed = deps.probe_identity(context)
        invoked.append("probe_identity")
        outcome = verify_identity(observed, binding)

        # 6) origin/security check before the critical action (only if identity authorized)
        if outcome is Outcome.AUTHORIZED:
            origin = deps.observe_origin(context)
            invoked.append("observe_origin")
            outcome = check_navigation(origin, binding.target_origin)

        # 7) FINAL fence before publication (only if still authorized)
        if outcome is Outcome.AUTHORIZED:
            outcome = final_fence(
                fence_meta if fence_meta is not None else meta,
                worker_token,
                meta.version,
                now,
                timed_out=fence_timed_out,
            )

        # publish ONLY when every stage above authorized
        if outcome is Outcome.AUTHORIZED:
            deps.publish_result(context)
            invoked.append("publish_result")
            published = True
    except Exception as exc:  # a business error is primary; an unknown state never publishes
        primary_error = f"{type(exc).__name__}: {exc}"
        if outcome is Outcome.AUTHORIZED:
            outcome = Outcome.UNKNOWN_AUTHORIZATION_STATE
    finally:
        # 8) always close the Context; a cleanup failure is recorded, never hides the primary error
        if context is not None:
            try:
                deps.close_context(context)
                invoked.append("close_context")
            except Exception as close_exc:
                cleanup_error = f"{type(close_exc).__name__}: {close_exc}"

    return TaskReport(outcome, published=published, invoked=invoked,
                      primary_error=primary_error, cleanup_error=cleanup_error)
