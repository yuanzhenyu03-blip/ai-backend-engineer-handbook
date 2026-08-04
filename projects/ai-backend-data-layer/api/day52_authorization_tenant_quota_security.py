"""Day52 — Authorization, Tenant Isolation, Quotas and API Security.

Turns Day51's trusted identity (a verified JWT `sub` -> AuthenticatedIdentity(user_id))
into CURRENT, tenant-scoped, action-specific, cost-aware API authority. Day51 proved WHO
the caller is; Day52 decides whether THIS authenticated user, in THIS tenant, MAY perform
THIS action on THIS resource, and whether the tenant may consume this rate/budget.

EVIDENCE LABEL (do not conflate the tiers):
  * CONCEPTUAL DESIGN: the admission boundary described here and in the design doc.
  * LOCAL PYTHON IN-MEMORY CONTROL-FLOW RUNTIME: what the pytest suite executes — an
    in-memory model of Membership/role authorization, tenant/owner-scoped reads, a guarded
    quota reservation modeling `UPDATE ... WHERE available >= amount RETURNING`, atomic
    Reservation+Job+Outbox with rollback, a fail-closed rate limiter, idempotent recovery,
    and guarded policy repair. This proves APPLICATION CONTROL FLOW only.
  * NOT RUN (no such claim): real PostgreSQL (constraints / transaction / isolation /
    `UPDATE ... RETURNING` / SQLAlchemy / migration / RLS); real Redis (distributed limiter
    atomics / TTL / failover / multi-process); real FastAPI/proxy/browser (Dependency, CORS,
    cookie/CSRF, Header, response wire, routes); Provider/Worker/Outbox transport;
    integration; production.

SECURITY: no real JWT, Provider key, password, raw prompt, Document content, database URL,
or user data is used or logged. Public errors never reveal that another tenant's resource
exists. Audit evidence is metadata only (actor, tenant scope, action, decision).

Standard library only (no external dependencies).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


# ===========================================================================
# 0. Identity carried from Day51 (authentication result — trusted user_id only)
# ===========================================================================
@dataclass(frozen=True)
class AuthenticatedIdentity:
    """The ONLY trusted authentication output (Day51). A request-supplied tenant_id is a
    SELECTOR, never authority — Day52 must prove tenant authority separately."""

    user_id: str


# ===========================================================================
# 1. User / Tenant / Membership / role / action
# ===========================================================================
class MembershipStatus(str, Enum):
    ACTIVE = "active"
    REMOVED = "removed"  # revoked/downgraded membership retained for audit, not deleted


# A role is a maintainable SET OF ACTIONS whose names match the business effect.
# `cancel`/`retry` are their own effects — never folded into `job.create`.
DEFAULT_ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "member": frozenset({"job.create", "job.read_own"}),
    "operator": frozenset({"job.create", "job.read_own", "job.read_all", "job.cancel", "job.retry"}),
    "admin": frozenset({"job.create", "job.read_own", "job.read_all", "job.cancel", "job.retry"}),
}


@dataclass(frozen=True)
class TenantMembership:
    user_id: str
    tenant_id: str
    role: str
    status: MembershipStatus = MembershipStatus.ACTIVE


class MembershipDirectory:
    """Models `tenant_memberships(user_id, tenant_id, role, status)` — the many-to-many
    authority relation. Tenant-A authority never leaks into Tenant-B."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], TenantMembership] = {}

    def add(self, m: TenantMembership) -> None:
        self._by_key[(m.user_id, m.tenant_id)] = m

    def remove_membership(self, user_id: str, tenant_id: str) -> None:
        """Membership removal / downgrade is a fact change checked per request; a stale
        JWT role claim must NOT keep granting authority."""
        m = self._by_key.get((user_id, tenant_id))
        if m is not None:
            self._by_key[(user_id, tenant_id)] = TenantMembership(
                user_id, tenant_id, m.role, MembershipStatus.REMOVED
            )

    def active_membership(self, user_id: str, tenant_id: str) -> Optional[TenantMembership]:
        m = self._by_key.get((user_id, tenant_id))
        if m is None or m.status is not MembershipStatus.ACTIVE:
            return None
        return m


class PolicyStore:
    """Centralized role->actions policy with a version. Mutable so the Day52 production
    exercise can roll back an erroneous grant for FUTURE traffic."""

    def __init__(self, role_actions: Optional[dict[str, frozenset[str]]] = None, *, version: int = 1) -> None:
        self._role_actions: dict[str, frozenset[str]] = dict(role_actions or DEFAULT_ROLE_ACTIONS)
        self.version = version

    def actions_for(self, role: str) -> frozenset[str]:
        return self._role_actions.get(role, frozenset())

    def grant(self, role: str, action: str) -> None:
        self._role_actions[role] = self._role_actions.get(role, frozenset()) | {action}
        self.version += 1

    def revoke(self, role: str, action: str) -> None:
        """Roll back / disable an erroneous centralized grant (fail closed for that action)
        without stopping unrelated safe actions."""
        self._role_actions[role] = self._role_actions.get(role, frozenset()) - {action}
        self.version += 1


# ===========================================================================
# 2. Authorization -> AuthorizedTenantContext (identity + membership + action)
# ===========================================================================
class AuthorizationError(Exception):
    """Generic authorization failure. The public message must NOT reveal which resource,
    tenant, or role was involved (no existence oracle) -> maps to a generic 403."""


class NotFoundError(Exception):
    """A tenant-scoped miss. Public 404 — must not reveal that a resource exists in another
    tenant (no existence oracle)."""


@dataclass(frozen=True)
class AuthorizedTenantContext:
    """Built ONLY after verified identity + active Membership + the required action. This —
    not a client Header/Body — is the authority repositories and RLS must carry."""

    user_id: str
    tenant_id: str
    permissions: frozenset[str]

    def require(self, action: str) -> None:
        if action not in self.permissions:
            raise AuthorizationError("forbidden")


def authorize(
    identity: AuthenticatedIdentity,
    requested_tenant_id: str,
    action: str,
    *,
    memberships: MembershipDirectory,
    policy: PolicyStore,
) -> AuthorizedTenantContext:
    """Client-supplied `requested_tenant_id` is only a selector. Prove authority:
    active Membership in that tenant -> resolve role permissions -> require the action.
    Every failure is a GENERIC AuthorizationError (anti-enumeration)."""
    membership = memberships.active_membership(identity.user_id, requested_tenant_id)
    if membership is None:
        raise AuthorizationError("forbidden")  # no active membership -> no authority
    permissions = policy.actions_for(membership.role)
    if action not in permissions:
        raise AuthorizationError("forbidden")  # generic 403; no resource revealed
    return AuthorizedTenantContext(identity.user_id, requested_tenant_id, permissions)


# ===========================================================================
# 3. Tenant- and owner-scoped resource access (IDOR/BOLA safe)
# ===========================================================================
class JobStatus(str, Enum):
    QUEUED = "queued"
    CANCELLED = "cancelled"


@dataclass
class Job:
    job_id: str
    tenant_id: str
    created_by_user_id: str
    idempotency_key: str
    request_fingerprint: str
    max_tokens: int
    status: JobStatus = JobStatus.QUEUED


class JobRepository:
    """Repositories must CARRY the AuthorizedTenantContext and apply tenant + owner
    predicates — a FastAPI Dependency centralizes policy but does not constrain SQL."""

    def __init__(self, jobs: dict[str, Job]) -> None:
        self._jobs = jobs

    def read_job(self, ctx: AuthorizedTenantContext, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        # Tenant-scoped: WHERE tenant_id = :authorized_tenant_id AND job_id = :job_id.
        if job is None or job.tenant_id != ctx.tenant_id:
            raise NotFoundError("not found")  # cross-tenant miss -> public 404, no oracle
        # job.read_all sees any tenant Job; job.read_own also requires ownership.
        if "job.read_all" not in ctx.permissions:
            ctx.require("job.read_own")
            if job.created_by_user_id != ctx.user_id:
                raise NotFoundError("not found")  # same-tenant colleague's Job is not "own"
        return job


# ===========================================================================
# 4. Rate limit (shared, fail-closed) — distinct from durable quota
# ===========================================================================
class LimiterUnavailable(Exception):
    """The shared limiter is down. On a PAID admission path this is FAIL-CLOSED -> a
    dependency-unavailable 503, NEVER a 429 (429 means a healthy limiter confirmed a
    breach)."""


class TokenBucketRateLimiter:
    """Models a SHARED (e.g. Redis) token bucket: bounded burst (capacity) + sustained
    refill. A single shared coordinator avoids the multi-instance undercount where four
    local counters each allowing 100 admit ~400. This is ephemeral speed control, NOT the
    durable cost/budget truth (that is PostgreSQL, section 5)."""

    def __init__(self, capacity: int, refill_per_minute: int, *, available: bool = True) -> None:
        self.capacity = capacity
        self.refill_per_minute = refill_per_minute
        self.available = available
        self._buckets: dict[str, tuple[float, datetime]] = {}
        self._lock = threading.Lock()

    def set_available(self, available: bool) -> None:
        self.available = available

    def allow(self, key: str, *, now: datetime) -> bool:
        if not self.available:
            raise LimiterUnavailable("rate limiter unavailable")  # caller must fail closed
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            elapsed = (now - last).total_seconds()
            tokens = min(self.capacity, tokens + elapsed * (self.refill_per_minute / 60.0))
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return True
            self._buckets[key] = (tokens, now)
            return False  # healthy limiter, limit exceeded -> caller returns 429 + Retry-After


# ===========================================================================
# 5. Durable token/cost quota + atomic Reservation + Job + Outbox (admission)
# ===========================================================================
class AdmissionOutcome(str, Enum):
    CREATED = "created"                    # new command admitted: reserved + Job + Outbox
    IDEMPOTENT_REPLAY = "idempotent_replay"  # same tenant+key+fingerprint -> original Job, no new cost
    FINGERPRINT_CONFLICT = "conflict"     # same key, changed meaning -> 409, no new facts
    QUOTA_EXCEEDED = "quota_exceeded"     # guarded reservation returned zero rows
    RATE_LIMITED = "rate_limited"         # healthy limiter said no -> 429


class ReservationRollback(Exception):
    """Injected to prove Reservation + Job + Outbox are one all-or-nothing transaction."""


@dataclass
class TenantBudget:
    tenant_id: str
    token_limit: int
    used_tokens: int = 0
    reserved_tokens: int = 0

    @property
    def available(self) -> int:
        return self.token_limit - self.used_tokens - self.reserved_tokens


@dataclass
class AdmissionResult:
    outcome: AdmissionOutcome
    job: Optional[Job] = None
    reason: str = ""


class ReconcileState(str, Enum):
    SETTLED = "settled"                       # actual usage known: moved to used, remainder released
    RECONCILIATION_PENDING = "reconciliation_pending"  # unknown Provider outcome: reservation retained


class AdmissionStore:
    """Durable concurrent arbiter (PostgreSQL in production). One lock models the guarded
    reservation `UPDATE tenant_budgets SET reserved = reserved + :amt WHERE limit - used -
    reserved >= :amt RETURNING` + the atomic Reservation+Job+Outbox transaction."""

    def __init__(self) -> None:
        self.budgets: dict[str, TenantBudget] = {}
        self.jobs: dict[str, Job] = {}
        self._by_idem: dict[tuple[str, str], str] = {}  # (tenant_id, key) -> job_id
        self.outbox: list[dict] = []
        self._reservations: dict[str, int] = {}  # job_id -> reserved amount (for reconcile)
        self._lock = threading.Lock()

    def set_budget(self, budget: TenantBudget) -> None:
        self.budgets[budget.tenant_id] = budget

    def reserve_and_create(
        self,
        ctx: AuthorizedTenantContext,
        *,
        idempotency_key: str,
        request_fingerprint: str,
        max_tokens: int,
        now: datetime,
        fail_after_reserve: bool = False,
    ) -> AdmissionResult:
        """Idempotency runs AFTER authorization (the caller authorized job.create). Then:
          * same (tenant, key): matching fingerprint -> original Job, NO second reservation;
            changed fingerprint -> 409, no new facts (not an authz bypass).
          * new command: guarded reservation; one returned row -> reserve + Job + Outbox in
            ONE transaction (a failure rolls ALL back — no ghost reservation, no unfunded
            Job); zero rows -> QUOTA_EXCEEDED, nothing created."""
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")  # validate per-Job cost bound
        with self._lock:
            existing_id = self._by_idem.get((ctx.tenant_id, idempotency_key))
            if existing_id is not None:
                job = self.jobs[existing_id]
                if job.request_fingerprint == request_fingerprint:
                    return AdmissionResult(AdmissionOutcome.IDEMPOTENT_REPLAY, job=job,
                                           reason="same command replay; no second reservation")
                return AdmissionResult(AdmissionOutcome.FINGERPRINT_CONFLICT,
                                       reason="same key, changed fingerprint")

            budget = self.budgets.get(ctx.tenant_id)
            # Guarded reservation: the WHERE predicate is the single-winner arbiter.
            if budget is None or budget.available < max_tokens:
                return AdmissionResult(AdmissionOutcome.QUOTA_EXCEEDED,
                                       reason="insufficient tenant budget (zero rows)")
            # --- one atomic transaction: reservation + Job + Outbox intent ---
            budget.reserved_tokens += max_tokens
            if fail_after_reserve:
                # Roll ALL of it back: no reservation delta, no Job, no Outbox persist.
                budget.reserved_tokens -= max_tokens
                raise ReservationRollback("injected failure after reservation, before commit")
            job = Job(
                job_id=str(uuid.uuid4()), tenant_id=ctx.tenant_id, created_by_user_id=ctx.user_id,
                idempotency_key=idempotency_key, request_fingerprint=request_fingerprint,
                max_tokens=max_tokens,
            )
            self.jobs[job.job_id] = job
            self._by_idem[(ctx.tenant_id, idempotency_key)] = job.job_id
            self._reservations[job.job_id] = max_tokens
            self.outbox.append({
                "event_type": "job.dispatch_requested", "job_id": job.job_id,
                "tenant_id": ctx.tenant_id, "correlation_id": str(uuid.uuid4()),
            })  # small non-secret envelope only (no prompt/Document content/secret)
            return AdmissionResult(AdmissionOutcome.CREATED, job=job, reason="reserved + Job + Outbox committed")

    def reconcile(self, job_id: str, *, actual_tokens: Optional[int]) -> ReconcileState:
        """Settle a reservation against real Provider usage. Unknown outcome (timeout) does
        NOT release the reservation — preserve evidence and hold reconciliation_pending."""
        with self._lock:
            reserved = self._reservations.get(job_id, 0)
            budget = self.budgets[self.jobs[job_id].tenant_id]
            if actual_tokens is None:
                return ReconcileState.RECONCILIATION_PENDING  # keep reservation; evidence retained
            settle = min(actual_tokens, reserved)
            budget.reserved_tokens -= reserved       # release the whole reservation hold...
            budget.used_tokens += settle             # ...and record only the actual usage
            self._reservations[job_id] = 0
            return ReconcileState.SETTLED


def admit_job(
    identity: AuthenticatedIdentity,
    requested_tenant_id: str,
    *,
    idempotency_key: str,
    request_fingerprint: str,
    max_tokens: int,
    now: datetime,
    memberships: MembershipDirectory,
    policy: PolicyStore,
    store: AdmissionStore,
    limiter: TokenBucketRateLimiter,
    fail_after_reserve: bool = False,
) -> AdmissionResult:
    """The Day52 admission boundary in order:
      1. authorize job.create (identity + active Membership + action);
      2. same-command idempotent recovery FIRST (tenant-scoped, no new cost, no rate-limit)
         — protects a lost-202 retry; removed Membership already blocked it at step 1;
      3. only a NEW command is rate-limited (fail-closed if the limiter is down);
      4. guarded quota reservation + Job + Outbox committed atomically.
    """
    ctx = authorize(identity, requested_tenant_id, "job.create", memberships=memberships, policy=policy)

    # Step 2: same-command recovery before spending limiter budget on a retry.
    existing_id = store._by_idem.get((ctx.tenant_id, idempotency_key))
    if existing_id is not None:
        return store.reserve_and_create(
            ctx, idempotency_key=idempotency_key, request_fingerprint=request_fingerprint,
            max_tokens=max_tokens, now=now,
        )

    # Step 3: rate-limit new commands only. Limiter outage on a paid path -> fail closed.
    if not limiter.allow(f"{ctx.tenant_id}:job.create", now=now):
        return AdmissionResult(AdmissionOutcome.RATE_LIMITED, reason="rate limit exceeded (429 + Retry-After)")

    # Step 4: guarded reservation + Job + Outbox.
    return store.reserve_and_create(
        ctx, idempotency_key=idempotency_key, request_fingerprint=request_fingerprint,
        max_tokens=max_tokens, now=now, fail_after_reserve=fail_after_reserve,
    )


# ===========================================================================
# 6. Production exercise: guarded repair of an erroneous cancel-policy grant
# ===========================================================================
class CancelIntentState(str, Enum):
    PENDING = "pending"
    INVALIDATED = "invalidated"   # bad-policy intent neutralized by a guarded repair (retained)
    EXECUTED = "executed"         # a legitimate cancel already took effect (never overwritten)


@dataclass
class CancelIntent:
    intent_id: str
    tenant_id: str
    job_id: str
    actor_user_id: str
    policy_version: int
    state: CancelIntentState = CancelIntentState.PENDING


class RepairOutcome(str, Enum):
    REPAIRED = "repaired"             # one guarded row updated
    RECONCILE = "reconcile"           # zero rows: facts changed -> stop automatic repair


class CancelIntentLedger:
    """Audit ledger of cancel intents. A bad-policy grant is contained by revoking the
    grant (future traffic) and then a GUARDED, targeted repair of already-created bad
    intents — never a blind delete, never overwriting a later legitimate cancel."""

    def __init__(self) -> None:
        self.intents: dict[str, CancelIntent] = {}
        self._lock = threading.Lock()

    def add(self, intent: CancelIntent) -> None:
        self.intents[intent.intent_id] = intent

    def repair_bad_intent(self, intent_id: str, *, expected_policy_version: int) -> RepairOutcome:
        """Guarded `UPDATE ... WHERE intent_id = :id AND policy_version = :v AND
        state = 'pending' RETURNING`. Zero rows means the fact changed (executed by a
        legitimate later cancel, or a different policy version): STOP and reconcile — never
        overwrite a legitimate cancel or re-run paid Provider work."""
        with self._lock:
            intent = self.intents.get(intent_id)
            if (
                intent is None
                or intent.policy_version != expected_policy_version
                or intent.state is not CancelIntentState.PENDING
            ):
                return RepairOutcome.RECONCILE
            intent.state = CancelIntentState.INVALIDATED  # retained as audit evidence, not deleted
            return RepairOutcome.REPAIRED
