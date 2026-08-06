"""Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure.

Day55 answered "which Worker may execute one durable Job, and how redelivery never re-calls the
Provider" (Celery moves messages; PostgreSQL moves truth). Day56 adds the ADMISSION-TO-PROVIDER
CONTROL PLANE: even a Job that HOLDS execution authority still needs current Provider capacity, an
intact cost reservation, and a healthy Provider path before an actual paid call.

FOUR DIFFERENT AUTHORITIES (never interchangeable):

    guarded claim   -> execution authority for ONE durable Job (Day55; PostgreSQL)
    rate permit     -> fleet-wide Provider capacity to call NOW (shared limiter; Redis-like)
    reservation     -> tenant affordability (durable money/token ledger; PostgreSQL)
    circuit         -> Provider-health / failure-domain containment (per provider/account/model/region)

FIVE DISPATCH OUTCOMES (executable):

    CALL      -> all four gates pass; make the paid Provider call now
    DEFER     -> no permit / circuit OPEN / limiter outage / no reservation yet, and NO call was made;
                 persist next_attempt_at + reason + defer_count + deadline, release the Worker (no sleep)
    RECONCILE -> the external call may have executed / is UNKNOWN (or evidence exists); never blind retry
    TERMINAL  -> a durable cancellation/deadline intent wins a guarded terminal transition
    NOOP      -> the Job is already terminal; nothing to do

CORE INVARIANTS:
    Retry-After is an EARLIEST retry time, not a wake-all signal (jitter breaks the herd).
    A synchronized retry storm / thundering herd is NOT a cache avalanche.
    A guarded claim is NOT a rate permit; a limiter is NOT the budget ledger.
    A shared-limiter OUTAGE fails CLOSED for NEW paid calls (reads/cancel/reconcile still work).
    No-permit-before-call consumes NO execution retry budget; it uses a separate bounded defer budget.
    An HTTP 429 alone does not prove no external execution — the Adapter classifies execution certainty.
    Unknown / may-have-executed -> RECONCILE, never ordinary retry.
    Backpressure lives BEFORE the durable Job + Outbox commit; an accepted Job is never retro-429/503.
    A Worker never silently mutates persisted model / max_tokens; degradation needs a pre-authorized contract.
    Reservation is worst-case at acceptance; success settles actual use and RELEASES unused money to the ledger.
    Recovery preserves history and writes a NEW Outbox dispatch intent — never a direct queue call.

EVIDENCE LABEL (do not conflate the tiers):
  * CONCEPTUAL DESIGN: the control-plane decision paths described here + in the runbook.
  * LOCAL IN-MEMORY CONTROL-FLOW RUNTIME: what the pytest suite executes — bounded retry + jitter,
    a shared limiter across simulated Workers, fail-closed limiter outage, durable defer accounting,
    worst-case reservation + settlement/release, admission backpressure, execution-certainty
    classification, circuit OPEN/HALF_OPEN progressive probes, deadline expiry, and the zero-defer
    incident repair. This proves APPLICATION CONTROL FLOW only.
  * NOT RUN (no such claim): a real Celery broker/Worker, a real Redis distributed limiter/circuit,
    real PostgreSQL transactions/isolation, real Provider traffic / rate limits / costs, load tests,
    Worker-kill fault injection, or production. Day57 owns integration + failure injection; Day58
    owns observability/runtime evidence — NOT implemented here.

This module is Python standard library only; it imports Day54's IntentKind (the durable
cancellation/deadline intent kind) so the terminal mapping stays consistent. No real credentials,
raw prompts, Document content, raw Provider payloads, or secrets are persisted or logged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional

from day54_streaming_disconnects_timeouts_cancellation import IntentKind


# ===========================================================================
# 1. Job lifecycle + domain enums
# ===========================================================================
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DEFERRED = "deferred"                     # durable capacity/health defer (no call made)
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"                   # durable USER_CANCELLATION intent
    EXPIRED = "expired"                       # durable DEADLINE_EXPIRY / defer-deadline
    PENDING_RECONCILIATION = "pending_reconciliation"  # unknown external execution


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}
)
# Still-dispatchable / still-completable (a guarded transition may fire from these):
LIVE_STATUSES = frozenset(
    {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.DEFERRED, JobStatus.PENDING_RECONCILIATION}
)


def terminal_for_intent(kind: IntentKind) -> "JobStatus":
    """Day54 durable-intent terminal mapping in Day56's JobStatus: USER_CANCELLATION -> CANCELLED,
    DEADLINE_EXPIRY -> EXPIRED. Re-expressed locally so the terminal is THIS module's enum."""
    return JobStatus.CANCELLED if kind is IntentKind.USER_CANCELLATION else JobStatus.EXPIRED


class ProviderAction(str, Enum):
    CALL = "call"
    DEFER = "defer"
    RECONCILE = "reconcile"
    TERMINAL = "terminal"
    NOOP = "noop"


class ExecutionCertainty(str, Enum):
    DEFINITELY_NOT_ACCEPTED = "definitely_not_accepted"  # safe to ordinary-defer/retry
    MAY_HAVE_EXECUTED = "may_have_executed"              # RECONCILE, never blind retry
    UNKNOWN = "unknown"                                  # RECONCILE, never blind retry


class CircuitState(str, Enum):
    CLOSED = "closed"          # calls allowed
    OPEN = "open"              # new calls durably deferred
    HALF_OPEN = "half_open"    # a small, controlled progressive probe set only


class CostState(str, Enum):
    NONE = "none"
    RESERVED = "reserved"
    RECONCILIATION_PENDING = "reconciliation_pending"
    SETTLED = "settled"


class SettleOutcome(str, Enum):
    SETTLED = "settled"                        # actual <= reserved: settled + unused released
    OVERAGE_RECONCILE = "overage_reconcile"    # actual > reserved: protected reconciliation (P1-3)


# ===========================================================================
# 2. Execution contract + Job + Attempt + defer record
# ===========================================================================
@dataclass(frozen=True)
class ExecutionContract:
    """Server-owned, product-authorized, PERSISTED at acceptance. A Worker may never silently
    change `model` or `max_tokens`. Degradation is allowed ONLY when this contract pre-authorizes
    it (and only down to `min_model` / `min_max_tokens`)."""
    provider: str
    account: str
    model: str
    region: str
    max_tokens: int                            # max OUTPUT/completion tokens (the LLM output cap)
    output_price_per_1k: float                 # unit price per 1k OUTPUT tokens
    max_input_tokens: int = 0                  # bounded max INPUT/prompt tokens
    input_price_per_1k: float = 0.0            # unit price per 1k INPUT tokens
    degradation_allowed: bool = False
    min_model: Optional[str] = None
    min_max_tokens: Optional[int] = None

    def circuit_key(self) -> str:
        # Follows the actual Provider quota / fault domain. NEVER include secrets/keys.
        return f"circuit:{self.provider}:{self.account}:{self.model}:{self.region}"

    def worst_case_cost(self) -> float:
        # Bounded worst-case monetary cost = bounded INPUT cost + bounded OUTPUT cost. Both the
        # input (prompt) size and the output (completion) cap are bounded by the persisted contract,
        # each with its own unit price, so the reservation truly covers the maximum allowed Provider
        # spend for this Job (P1-3) — not just the output side.
        input_cost = (self.max_input_tokens / 1000.0) * self.input_price_per_1k
        output_cost = (self.max_tokens / 1000.0) * self.output_price_per_1k
        return round(input_cost + output_cost, 6)


@dataclass
class Attempt:
    attempt_id: str
    job_id: str
    provider_idempotency_key: str
    correlation_id: str
    provider_request_id: Optional[str] = None            # strong external-execution evidence
    provider_dispatch_started_at: Optional[datetime] = None  # conservative "may have started" marker


@dataclass
class DeferRecord:
    retry_reason: str
    next_attempt_at: datetime
    defer_count: int
    deadline: datetime


@dataclass
class Job:
    job_id: str
    tenant_id: str
    contract: ExecutionContract
    status: JobStatus
    deadline: datetime                          # business deadline for the whole Job
    cost_state: CostState = CostState.NONE
    reserved_cost: Optional[float] = None
    settled_cost: Optional[float] = None
    cost_overage: Optional[float] = None        # actual-over-reservation excess (P1-3)
    repair_history: list = field(default_factory=list)  # audited repair trail (P1-4)
    attempt: Optional[Attempt] = None
    intent_kind: Optional[IntentKind] = None    # durable cancellation/deadline intent (Day54)
    defer: Optional[DeferRecord] = None
    execution_retry_count: int = 0              # only Provider calls that actually executed & failed
    defer_count: int = 0                        # no-permit-before-call defers (separate budget)
    release_version: str = "r1"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ===========================================================================
# 3. Bounded retry + jitter (Retry-After is an EARLIEST time, not a wake-all)
# ===========================================================================
def backoff_delay_seconds(attempt_number: int, *, base: float = 1.0, cap: float = 60.0,
                          jitter: float = 1.0, rand: Callable[[], float] = None) -> float:
    """Exponential backoff with FULL jitter, bounded by `cap`. `attempt_number` starts at 1.
    Full jitter (rand in [0,1)) spreads a fleet's retries so they do NOT wake together — this is
    what prevents a synchronized retry storm / thundering herd (which is NOT a cache avalanche)."""
    import random
    rand = rand or random.random
    raw = min(cap, base * (2 ** max(0, attempt_number - 1)))
    return round(raw * (1.0 - jitter) + raw * jitter * rand(), 6)


def compute_next_attempt_at(now: datetime, attempt_number: int, *,
                            retry_after_seconds: Optional[float] = None,
                            rand: Callable[[], float] = None,
                            jitter_window_seconds: Optional[float] = None) -> datetime:
    """Compute the next attempt time. Retry-After is an EARLIEST allowed time (a floor), never a
    wake-all signal: when it dominates the jittered backoff we still add a BOUNDED random jitter
    ABOVE the floor so the whole fleet does not wake at the same instant (P1-1). The result is
    always >= the Retry-After floor; different random draws yield different times."""
    import random
    rand = rand or random.random
    backoff = backoff_delay_seconds(attempt_number, rand=rand)
    candidate = now + timedelta(seconds=backoff)
    if retry_after_seconds is None:
        return candidate                       # backoff is itself full-jittered
    earliest = now + timedelta(seconds=retry_after_seconds)
    if candidate > earliest:
        return candidate                       # backoff already dominates and is jittered
    # Retry-After is the FLOOR. Add bounded jitter on top of it (never below). The default jitter
    # window is the bounded backoff magnitude for this attempt (grows with attempts, capped).
    window = (jitter_window_seconds if jitter_window_seconds is not None
              else backoff_delay_seconds(attempt_number, rand=lambda: 1.0))
    return earliest + timedelta(seconds=window * rand())


# ===========================================================================
# 4. Shared rate limiter (fleet capacity; distinct from the guarded claim)
# ===========================================================================
class SharedRateLimiter:
    """A cross-Worker Provider-capacity coordinator (a real system uses Redis or equivalent). It
    decides whether the WHOLE fleet may call now; it is NOT the per-Job guarded claim and NOT the
    budget ledger. If the coordination store is unavailable, NEW paid calls fail CLOSED by default."""

    def __init__(self, capacity: int, *, available: bool = True) -> None:
        self.capacity = capacity
        self._used = 0
        self.available = available            # flip to False to model a limiter/coordination outage

    def try_acquire(self) -> bool:
        if not self.available:
            return False                      # outage -> no permit (caller must fail closed)
        if self._used >= self.capacity:
            return False
        self._used += 1
        return True

    def release(self) -> None:
        if self._used > 0:
            self._used -= 1

    @property
    def in_flight(self) -> int:
        return self._used


# ===========================================================================
# 5. Tenant budget ledger (affordability; distinct from the limiter)
# ===========================================================================
class TenantBudgetLedger:
    """Durable money/token truth per tenant. Reserve the BOUNDED WORST-CASE cost at acceptance;
    settle ACTUAL use on success and RELEASE the unused remainder back HERE (never to the limiter)."""

    def __init__(self, balances: dict[str, float]) -> None:
        self._available = dict(balances)      # tenant_id -> spendable balance
        self._reserved: dict[str, float] = {}  # job_id -> reserved amount

    def can_afford(self, tenant_id: str, amount: float) -> bool:
        return self._available.get(tenant_id, 0.0) + 1e-9 >= amount

    def reserve_worst_case(self, job: Job) -> bool:
        if job.job_id in self._reserved:
            return True                       # idempotent: a reservation already exists
        amount = job.contract.worst_case_cost()
        if not self.can_afford(job.tenant_id, amount):
            return False                      # cannot cover worst case -> do NOT accept/call
        self._available[job.tenant_id] -= amount
        self._reserved[job.job_id] = amount
        job.reserved_cost = amount
        job.cost_state = CostState.RESERVED
        return True

    def has_reservation(self, job: Job) -> bool:
        return job.job_id in self._reserved

    def settle_actual(self, job: Job, actual_cost: float) -> "SettleOutcome":
        """Settle a completed Job against its reservation.

        Trade-off (P1-3): a correct worst-case reservation should always cover actual cost, but if
        `actual_cost > reserved` we must NOT silently bypass the tenant budget by deducting more
        than was reserved (that could overdraw the tenant). Policy chosen here = SAFE PROTECTED
        RECONCILIATION: charge exactly the reserved amount, record the overage, and enter
        RECONCILIATION_PENDING so an explicit, protected extra-charge decision handles the excess.
        Otherwise settle the actual cost and RELEASE the unused remainder back to the tenant
        ledger (never to the limiter)."""
        reserved = self._reserved.pop(job.job_id, 0.0)
        if actual_cost > reserved + 1e-9:
            job.settled_cost = reserved                # charge only what was reserved
            job.cost_overage = round(actual_cost - reserved, 6)
            job.cost_state = CostState.RECONCILIATION_PENDING
            return SettleOutcome.OVERAGE_RECONCILE
        unused = round(reserved - actual_cost, 6)
        if unused > 0:
            self._available[job.tenant_id] += unused   # unused MONEY returns to the ledger
        job.settled_cost = actual_cost
        job.cost_overage = None
        job.cost_state = CostState.SETTLED
        return SettleOutcome.SETTLED

    def release_reservation(self, job: Job) -> None:
        """Full release with NO external execution (safe only when proven not executed)."""
        reserved = self._reserved.pop(job.job_id, 0.0)
        self._available[job.tenant_id] += reserved
        job.cost_state = CostState.NONE
        job.reserved_cost = None

    def hold_for_reconciliation(self, job: Job) -> None:
        """Unknown external execution: keep the reservation held, never release/zero it."""
        job.cost_state = CostState.RECONCILIATION_PENDING

    def available(self, tenant_id: str) -> float:
        return round(self._available.get(tenant_id, 0.0), 6)


# ===========================================================================
# 6. Circuit breaker (Provider failure-domain containment; progressive recovery)
# ===========================================================================
class CircuitBreaker:
    """Per failure-domain key. CLOSED allows calls; OPEN durably defers new calls; HALF_OPEN
    permits only a small, bounded PROGRESSIVE probe set. A single successful probe does NOT release
    all deferred Jobs — recovery is gradual."""

    def __init__(self, *, fail_threshold: int = 5, half_open_max_probes: int = 2) -> None:
        self.fail_threshold = fail_threshold
        self.half_open_max_probes = half_open_max_probes
        self._state: dict[str, CircuitState] = {}
        self._fails: dict[str, int] = {}
        self._probes_in_flight: dict[str, int] = {}
        self._probe_successes: dict[str, int] = {}

    def state(self, key: str) -> CircuitState:
        return self._state.get(key, CircuitState.CLOSED)

    def record_failure(self, key: str) -> None:
        self._fails[key] = self._fails.get(key, 0) + 1
        if self._fails[key] >= self.fail_threshold:
            self._state[key] = CircuitState.OPEN

    def start_half_open(self, key: str) -> None:
        self._state[key] = CircuitState.HALF_OPEN
        self._probes_in_flight[key] = 0
        self._probe_successes[key] = 0

    def has_probe_capacity(self, key: str) -> bool:
        """Read-only: True if a HALF_OPEN probe slot is free. Does NOT consume a slot, so a Job that
        later DEFERs (no capacity / limiter outage / missing reservation) never leaks a slot (P1-2)."""
        if self.state(key) is not CircuitState.HALF_OPEN:
            return False
        return self._probes_in_flight.get(key, 0) < self.half_open_max_probes

    def allow_probe(self, key: str) -> bool:
        """Consume a HALF_OPEN probe slot if one is free (bounded, progressive). Call this ONLY when
        an actual Provider call is about to happen — never merely to gate a decision."""
        if not self.has_probe_capacity(key):
            return False
        self._probes_in_flight[key] = self._probes_in_flight.get(key, 0) + 1
        return True

    def record_probe_success(self, key: str, *, needed_to_close: int = 2) -> None:
        self._probe_successes[key] = self._probe_successes.get(key, 0) + 1
        self._probes_in_flight[key] = max(0, self._probes_in_flight.get(key, 0) - 1)
        if self._probe_successes[key] >= needed_to_close:   # progressive: several probes, not one
            self._state[key] = CircuitState.CLOSED
            self._fails[key] = 0

    def record_probe_failure(self, key: str) -> None:
        self._probes_in_flight[key] = max(0, self._probes_in_flight.get(key, 0) - 1)
        self._state[key] = CircuitState.OPEN               # re-open on a failed probe


# ===========================================================================
# 7. Admission backpressure (BEFORE the durable Job + Outbox commit)
# ===========================================================================
class AdmissionDecision(str, Enum):
    ACCEPT = "accept"
    REJECT_429_TENANT = "reject_429_tenant"     # tenant-specific quota/admission policy
    REJECT_503_SYSTEM = "reject_503_system"     # system-wide capacity/dependency unavailable


def admit_job(*, tenant_over_quota: bool, system_unavailable: bool) -> AdmissionDecision:
    """Backpressure belongs BEFORE accepting a durable Job. A tenant over its own admission policy
    maps to 429; system-wide capacity/dependency unavailability maps to 503. Do NOT return 202 when
    the system cannot safely make the commitment. An accepted Job is NEVER retroactively 429/503."""
    if system_unavailable:
        return AdmissionDecision.REJECT_503_SYSTEM
    if tenant_over_quota:
        return AdmissionDecision.REJECT_429_TENANT
    return AdmissionDecision.ACCEPT


# ===========================================================================
# 8. Provider adapter: classify execution certainty (a 429 is not universal proof)
# ===========================================================================
def classify_execution_certainty(*, http_status: int, provider_request_id: Optional[str],
                                 accepted_header: Optional[bool] = None) -> ExecutionCertainty:
    """Translate a vendor status into an APPLICATION-owned execution-certainty contract. A bare 429
    is NOT universally proof that nothing executed. Only a clearly-not-accepted signal (e.g. a
    pre-admission 429 with no request id and an explicit not-accepted marker) is safe to defer."""
    if provider_request_id:
        return ExecutionCertainty.MAY_HAVE_EXECUTED      # the Provider took a request id
    if http_status == 429 and accepted_header is False:
        return ExecutionCertainty.DEFINITELY_NOT_ACCEPTED
    if http_status in (500, 502, 503, 504):
        return ExecutionCertainty.UNKNOWN                # gateway/timeout: may or may not have run
    if http_status == 429:
        return ExecutionCertainty.UNKNOWN                # ambiguous 429 -> reconcile, not blind retry
    return ExecutionCertainty.UNKNOWN


def can_ordinary_retry(certainty: ExecutionCertainty) -> bool:
    return certainty is ExecutionCertainty.DEFINITELY_NOT_ACCEPTED


# ===========================================================================
# 9. The control-plane dispatch decision (CALL | DEFER | RECONCILE | TERMINAL | NOOP)
# ===========================================================================
@dataclass
class DispatchDecision:
    action: ProviderAction
    reason: str
    next_attempt_at: Optional[datetime] = None
    terminal_status: Optional[JobStatus] = None


def evaluate_dispatch(job: Job, *, limiter: SharedRateLimiter, ledger: TenantBudgetLedger,
                      circuit: CircuitBreaker, now: datetime,
                      emergency_fail_open: bool = False,
                      rand: Callable[[], float] = None) -> DispatchDecision:
    """Decide what a Worker that ALREADY holds the guarded claim may do with the Provider now.
    Ordering matters: durable terminal/cancellation facts and external-execution evidence OUTRANK
    ordinary capacity retry; only after those does capacity/affordability/health gating apply."""

    # (1) Terminal facts and durable cancellation/deadline intent OUTRANK ordinary retry.
    if job.status in TERMINAL_STATUSES:
        return DispatchDecision(ProviderAction.NOOP, "already_terminal")
    if job.intent_kind is not None:
        # Cancellation/deadline drives a guarded terminal transition (not reconciliation).
        return DispatchDecision(ProviderAction.TERMINAL, f"durable_intent:{job.intent_kind.value}",
                                terminal_status=terminal_for_intent(job.intent_kind))

    # (2) External-execution evidence / uncertainty -> RECONCILE, never a blind retry (Day55 P1).
    att = job.attempt
    if att is not None and (att.provider_request_id is not None
                            or att.provider_dispatch_started_at is not None):
        return DispatchDecision(ProviderAction.RECONCILE, "provider_execution_evidence")

    # (3) Business deadline reached while waiting for capacity.
    if now >= job.deadline:
        # Safe EXPIRED + reservation release ONLY with proof of no external execution (there is
        # none here — no evidence in (2)); otherwise it would have reconciled above.
        return DispatchDecision(ProviderAction.TERMINAL, "defer_deadline_expired",
                                terminal_status=JobStatus.EXPIRED)

    # (4) Circuit breaker (Provider-health containment).
    key = job.contract.circuit_key()
    cstate = circuit.state(key)
    if cstate is CircuitState.OPEN:
        return _defer(job, "circuit_open", now, rand)
    if cstate is CircuitState.HALF_OPEN and not circuit.has_probe_capacity(key):
        # Only CHECK capacity here (read-only); the probe slot is consumed at CALL time so a later
        # DEFER (no capacity / limiter outage / missing reservation) never leaks a slot (P1-2).
        return _defer(job, "circuit_half_open_no_probe_slot", now, rand)

    # (5) Fleet capacity permit (shared limiter). An OUTAGE fails CLOSED by default; a tightly
    # bounded emergency fail-open is an EXPLICIT policy only, never a default bypass. When the
    # coordination store is down there is no permit to grant, so fail-open proceeds WITHOUT one.
    permit_acquired = False
    if limiter.available:
        if not limiter.try_acquire():
            return _defer(job, "no_rate_capacity", now, rand)
        permit_acquired = True
    elif not emergency_fail_open:
        return _defer(job, "limiter_unavailable_fail_closed", now, rand)

    # (6) Tenant affordability (reservation must already exist from acceptance).
    if not ledger.has_reservation(job):
        if permit_acquired:
            limiter.release()                 # give the permit back; we are not calling
        return _defer(job, "no_cost_reservation", now, rand)

    # (7) All four authorities agree -> CALL. Consume a HALF_OPEN probe slot NOW (not earlier), so
    # it is only ever taken when a real Provider call is about to happen.
    if cstate is CircuitState.HALF_OPEN:
        circuit.allow_probe(key)
    return DispatchDecision(ProviderAction.CALL, "all_gates_passed")


def _defer(job: Job, reason: str, now: datetime, rand: Callable[[], float]) -> DispatchDecision:
    """Persist a durable defer decision and release the Worker. No Worker sleep. A no-permit defer
    does NOT consume the execution retry budget; it uses the separate bounded defer budget/deadline."""
    job.defer_count += 1
    next_at = compute_next_attempt_at(now, job.defer_count, rand=rand)
    next_at = min(next_at, job.deadline)      # never schedule past the business deadline
    job.defer = DeferRecord(retry_reason=reason, next_attempt_at=next_at,
                            defer_count=job.defer_count, deadline=job.deadline)
    job.status = JobStatus.DEFERRED
    return DispatchDecision(ProviderAction.DEFER, reason, next_attempt_at=next_at)


# ===========================================================================
# 10. Degradation (only if the persisted contract pre-authorizes it)
# ===========================================================================
def apply_authorized_degradation(contract: ExecutionContract, *, target_model: str,
                                 target_max_tokens: int) -> ExecutionContract:
    """Return a degraded contract ONLY when the persisted contract pre-authorizes it and the target
    does not go below the authorized floor. A Worker may NEVER silently reduce model/max_tokens."""
    if not contract.degradation_allowed:
        raise ValueError("degradation not authorized by the persisted contract")
    if contract.min_model is not None and target_model != contract.min_model \
            and target_model != contract.model:
        raise ValueError("target model is not an authorized degradation target")
    if contract.min_max_tokens is not None and target_max_tokens < contract.min_max_tokens:
        raise ValueError("target max_tokens below the authorized floor")
    from dataclasses import replace
    return replace(contract, model=target_model, max_tokens=target_max_tokens)


# ===========================================================================
# 11. Deadline / expiry processing (safe release only with no execution evidence)
# ===========================================================================
def process_deadline(job: Job, ledger: TenantBudgetLedger) -> DispatchDecision:
    """At the defer deadline: guarded EXPIRED + reservation RELEASE is safe ONLY with proof of no
    external execution. If the Attempt shows any execution evidence/uncertainty -> RECONCILE and
    HOLD the reservation (never release/zero it)."""
    att = job.attempt
    if att is not None and (att.provider_request_id is not None
                            or att.provider_dispatch_started_at is not None):
        ledger.hold_for_reconciliation(job)
        job.status = JobStatus.PENDING_RECONCILIATION
        return DispatchDecision(ProviderAction.RECONCILE, "deadline_but_execution_unknown")
    if job.status in TERMINAL_STATUSES:
        return DispatchDecision(ProviderAction.NOOP, "already_terminal")
    ledger.release_reservation(job)           # proven-not-executed: safe to release money
    job.status = JobStatus.EXPIRED
    return DispatchDecision(ProviderAction.TERMINAL, "expired_no_execution",
                            terminal_status=JobStatus.EXPIRED)


# ===========================================================================
# 12. Incident: zero-defer bad release -> containment + evidence-based repair
# ===========================================================================
class ReleaseConfig:
    """Models a bad rollout, e.g. max defer duration set to zero (prematurely expiring
    capacity-deferred Jobs)."""

    def __init__(self, version: str, *, max_defer_seconds: int) -> None:
        self.version = version
        self.max_defer_seconds = max_defer_seconds

    def rollback(self, *, safe_max_defer_seconds: int) -> None:
        # Stops FUTURE harm only. It does NOT repair Jobs already committed EXPIRED. Configuration
        # rollback != business-fact rollback.
        self.max_defer_seconds = safe_max_defer_seconds


def build_capacity_expiry_affected_set(jobs: list[Job], *, release_version: str,
                                       window_start: datetime, window_end: datetime,
                                       expiry_reason: str = "defer_deadline_expired") -> list[str]:
    """Bounded affected set: same bad release AND EXPIRED within the time window AND the capacity
    expiry reason AND a recorded defer (evidence). Preserve expired history; never bulk-flip."""
    out = []
    for j in jobs:
        if j.release_version != release_version or j.status is not JobStatus.EXPIRED:
            continue
        if j.defer is None or j.defer.retry_reason != expiry_reason:
            continue
        rs = j.defer.next_attempt_at
        if rs is None or rs < window_start or rs > window_end:
            continue
        out.append(j.job_id)
    return out


class RepairAction(str, Enum):
    REDISPATCH_NEW_OUTBOX_INTENT = "redispatch_new_outbox_intent"  # proven no execution + valid commitment
    RECONCILE_ONLY = "reconcile_only"                             # Provider evidence: never blind re-dispatch


def classify_incident_repair(job: Job, *, now: datetime) -> RepairAction:
    """Re-dispatch ONLY Jobs with proof of no Provider execution AND a still-valid
    contract/deadline (budget is checked when the new reservation is made). Jobs with any Provider
    evidence are RECONCILE_ONLY."""
    att = job.attempt
    if att is not None and (att.provider_request_id is not None
                            or att.provider_dispatch_started_at is not None):
        return RepairAction.RECONCILE_ONLY
    if now >= job.deadline:
        return RepairAction.RECONCILE_ONLY    # business commitment no longer valid -> do not re-dispatch
    return RepairAction.REDISPATCH_NEW_OUTBOX_INTENT


@dataclass
class OutboxDispatchIntent:
    job_id: str
    created_at: datetime
    reason: str
    repair_id: str


class RepairOutcome(str, Enum):
    REDISPATCHED = "redispatched"                  # committed: one new Outbox intent written
    ALREADY_APPLIED = "already_applied"            # idempotent duplicate: no second intent
    BLOCKED_NOT_IN_AFFECTED_SET = "blocked_not_in_affected_set"
    BLOCKED_WRONG_STATUS = "blocked_wrong_status"
    BLOCKED_CANCELLED = "blocked_cancelled"
    BLOCKED_DEADLINE_PASSED = "blocked_deadline_passed"
    BLOCKED_PROVIDER_EVIDENCE = "blocked_provider_evidence"   # RECONCILE_ONLY, never re-dispatch
    BLOCKED_BUDGET = "blocked_budget"


def repair_id_for(job: Job, *, release_version: str) -> str:
    """Stable repair identity so a repeated repair of the SAME Job/incident is idempotent."""
    return f"repair:{job.job_id}:{release_version}:defer_deadline_expired"


def repair_redispatch(job: Job, outbox: list[OutboxDispatchIntent], repair_ledger: dict,
                      ledger: "TenantBudgetLedger", *, now: datetime, affected_set: set,
                      release_version: str) -> RepairOutcome:
    """Guarded, idempotent, audited repair of ONE capacity-expired Job. The eligibility recheck,
    the status transition, the audit repair record, the new reservation, and the single new Outbox
    dispatch intent are ONE guarded atomic decision (P1-4):

      * idempotent: a repair id (`repair:{job}:{release}:{reason}`) is recorded on commit; a repeat
        with the same id writes NO second Outbox intent and makes NO second reservation;
      * eligibility is re-verified at repair time: still in the affected set, still EXPIRED, no
        durable cancellation intent, deadline not passed, NO Provider-execution evidence, and a new
        worst-case reservation can be made;
      * a Job with a provider_request_id or a pre-dispatch external-call marker stays RECONCILE_ONLY
        and is never re-dispatched;
      * the original EXPIRED history is PRESERVED in an audit trail (no unaudited bulk status flip).
    """
    rid = repair_id_for(job, release_version=release_version)
    if rid in repair_ledger:
        return RepairOutcome.ALREADY_APPLIED       # idempotent: exactly one intent per repair id

    # --- guarded eligibility rechecks (order: cheapest / safety-first) ---
    if job.job_id not in affected_set:
        return RepairOutcome.BLOCKED_NOT_IN_AFFECTED_SET
    if job.status is not JobStatus.EXPIRED:
        return RepairOutcome.BLOCKED_WRONG_STATUS
    if job.intent_kind is not None:
        return RepairOutcome.BLOCKED_CANCELLED     # a durable cancellation outranks repair
    if classify_incident_repair(job, now=now) is not RepairAction.REDISPATCH_NEW_OUTBOX_INTENT:
        # provider evidence -> RECONCILE_ONLY; or deadline already passed
        att = job.attempt
        if att is not None and (att.provider_request_id is not None
                                or att.provider_dispatch_started_at is not None):
            return RepairOutcome.BLOCKED_PROVIDER_EVIDENCE
        return RepairOutcome.BLOCKED_DEADLINE_PASSED
    if not ledger.reserve_worst_case(job):
        return RepairOutcome.BLOCKED_BUDGET        # cannot re-fund the worst case -> do not re-dispatch

    # --- commit the repair atomically: audit history, re-open, one Outbox intent ---
    job.repair_history.append({"was_status": JobStatus.EXPIRED.value, "repair_id": rid,
                               "repaired_at": now, "reason": "capacity_expiry_repair"})
    job.status = JobStatus.QUEUED              # EXPIRED history preserved in repair_history (audited)
    job.defer = None
    outbox.append(OutboxDispatchIntent(job_id=job.job_id, created_at=now,
                                       reason="capacity_expiry_repair", repair_id=rid))
    repair_ledger[rid] = now                   # record the committed repair -> idempotent thereafter
    return RepairOutcome.REDISPATCHED
