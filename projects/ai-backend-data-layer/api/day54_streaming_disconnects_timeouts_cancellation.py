"""Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation.

Separate TWO kinds of streaming and THREE independent lifecycles so a client disconnect,
Provider uncertainty, explicit cancellation, and durable Job truth cannot be confused or
overwrite one another. Reuses Day53 guarded completion, PENDING_RECONCILIATION, reservation
retention, and unknown-usage honesty; adds durable, auditable, cooperative, guarded
cancellation/expiry.

TWO streaming kinds:
  A. Provider token streaming — transient chunks for ONE Provider request (never durable truth).
  B. Durable Job progress/event streaming — safe observable state for an already-persisted Job,
     designed for subscription/reconnection.

THREE independent lifecycles:
  * HTTP client connection lifecycle — an SSE disconnect ends only THAT client's subscription.
  * Provider request lifecycle — its real state/outcome/usage may stay UNKNOWN after a
    disconnect or timeout.
  * Durable Job lifecycle — a PostgreSQL-owned business fact (queued -> running -> succeeded);
    it does NOT auto-cancel on disconnect.

Explicit boundary:
  HTTP disconnect != the Provider call necessarily stops != the persisted Job auto-cancels
  != the accepted business commitment disappears.

EVIDENCE LABEL (do not conflate the tiers):
  * CONCEPTUAL DESIGN: the lifecycle/cancellation boundary described here + in the design doc.
  * LOCAL IN-MEMORY CONTROL-FLOW RUNTIME: what the pytest suite executes — an in-memory model of
    the three lifecycles, SSE subscription, durable cancellation/expiry intent, cooperative
    Worker checks, guarded terminal transitions, the completion-vs-cancellation race, and the
    erroneous-disconnect-policy recovery. This proves APPLICATION CONTROL FLOW only.
  * NOT RUN (no such claim): real FastAPI/SSE wire behavior, the real OpenAI SDK / network /
    Provider, real PostgreSQL transactions/isolation, Redis, Celery. Day55 owns Celery Worker
    execution; Day56 owns retry/backoff/rate-limit/backpressure — NOT implemented here.

SECURITY: no real credentials, raw prompts, Document content, or raw Provider payloads/tokens
are persisted or logged. Provider tokens are transient and never default-persisted as JobEvents.
Standard library only.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Iterator, Optional


# ===========================================================================
# 1. Durable Job lifecycle (PostgreSQL-owned business fact in production)
# ===========================================================================
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"                     # terminal via the durable cancellation protocol
    EXPIRED = "expired"                         # terminal via the durable deadline protocol
    PENDING_RECONCILIATION = "pending_reconciliation"  # Provider timeout: unknown outcome/usage

TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}
)
# Still-completable / still-cancellable (a guarded transition may fire from these):
LIVE_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PENDING_RECONCILIATION})


class CostState(str, Enum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RECONCILIATION_PENDING = "reconciliation_pending"  # unknown usage: reservation retained, never 0


class IntentKind(str, Enum):
    USER_CANCELLATION = "user_cancellation"
    DEADLINE_EXPIRY = "deadline_expiry"


@dataclass(frozen=True)
class CancellationIntent:
    """A DURABLE, auditable cancellation/expiry intent — persisted BEFORE any terminal write.
    It survives process loss and is re-observable at-least-once. It is NOT itself a terminal
    status; a Worker cooperatively reacts and a guarded transition owns the terminal fact."""

    intent_id: str
    job_id: str
    kind: IntentKind
    reason: str
    actor: str                     # user id, or a system source (e.g. "scheduler", "disconnect_bug")
    requested_at: datetime
    release_version: Optional[str] = None  # deployment/version evidence (for rollback triage)


@dataclass
class Job:
    job_id: str
    tenant_id: str
    status: JobStatus = JobStatus.RUNNING
    cost_state: CostState = CostState.RESERVED
    reserved_tokens: int = 0
    settled_tokens: Optional[int] = None
    result_artifact: Optional[dict] = None
    events: list[dict] = field(default_factory=list)      # low-frequency SAFE lifecycle milestones
    intents: list[CancellationIntent] = field(default_factory=list)  # durable audit; never deleted
    provider_request_id: Optional[str] = None             # Provider correlation (external execution)
    correlation_id: Optional[str] = None


class TransitionOutcome(str, Enum):
    WON = "won"                    # this caller performed the guarded terminal write
    ZERO_ROWS = "zero_rows"        # someone else already made it terminal -> stop and reconcile


class JobStore:
    """Durable Job facts + guarded terminal transitions + durable intents. A lock models the
    single-winner guarded `UPDATE ... WHERE status IN (live) RETURNING`. An SSE disconnect never
    calls into this store — disconnect is an HTTP-lifecycle event only."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_running_job(self, job_id: str, *, tenant_id: str, reserved_tokens: int,
                           correlation_id: Optional[str] = None) -> Job:
        job = Job(job_id=job_id, tenant_id=tenant_id, reserved_tokens=reserved_tokens,
                  correlation_id=correlation_id)
        self.jobs[job_id] = job
        return job

    def add_event(self, job_id: str, event_type: str, **safe_fields: object) -> None:
        """Persist a LOW-FREQUENCY, SAFE lifecycle milestone (never a raw Provider token)."""
        job = self.jobs[job_id]
        job.events.append({"type": event_type, "job_id": job_id,
                           "correlation_id": job.correlation_id, **safe_fields})

    def persist_cancellation_intent(self, job_id: str, *, kind: IntentKind, reason: str,
                                    actor: str, now: datetime,
                                    release_version: Optional[str] = None) -> CancellationIntent:
        """Persist the durable intent FIRST (with reason/actor/timestamp/version). This does NOT
        write a terminal status — the Router must never set `cancelled` just because HTTP arrived."""
        with self._lock:
            intent = CancellationIntent(intent_id=str(uuid.uuid4()), job_id=job_id, kind=kind,
                                        reason=reason, actor=actor, requested_at=now,
                                        release_version=release_version)
            self.jobs[job_id].intents.append(intent)
            return intent

    def open_intent(self, job_id: str) -> Optional[CancellationIntent]:
        job = self.jobs.get(job_id)
        if job is None or not job.intents:
            return None
        return job.intents[-1]  # most recent durable intent

    def guarded_terminal_transition(self, job_id: str, target: JobStatus, *, now: datetime,
                                    from_statuses: frozenset = LIVE_STATUSES) -> TransitionOutcome:
        """Guarded terminal write: transition ONLY from a live status. Exactly one caller wins;
        a caller that arrives after the Job is already terminal sees ZERO_ROWS and must stop /
        reconcile rather than overwrite. Models `UPDATE ... WHERE status IN (...) RETURNING`."""
        with self._lock:
            job = self.jobs[job_id]
            if job.status not in from_statuses:
                return TransitionOutcome.ZERO_ROWS
            job.status = target
            job.events.append({"type": f"job.{target.value}", "job_id": job_id,
                               "correlation_id": job.correlation_id})
            return TransitionOutcome.WON

    def record_timeout_pending(self, job_id: str) -> TransitionOutcome:
        """Provider timeout: NON-terminal PENDING_RECONCILIATION, reservation retained, unknown
        usage (never fabricated as 0). Only from a live status; a terminal Job is untouched."""
        with self._lock:
            job = self.jobs[job_id]
            if job.status in TERMINAL_STATUSES:
                return TransitionOutcome.ZERO_ROWS
            job.status = JobStatus.PENDING_RECONCILIATION
            job.cost_state = CostState.RECONCILIATION_PENDING
            job.events.append({"type": "job.provider_timeout_pending_reconciliation",
                               "job_id": job_id, "correlation_id": job.correlation_id})
            return TransitionOutcome.WON

    def hold_cost_reconciliation(self, job_id: str) -> None:
        """Unknown usage: retain reservation + reconciliation_pending; never release, never 0."""
        with self._lock:
            self.jobs[job_id].cost_state = CostState.RECONCILIATION_PENDING

    def settle_cost(self, job_id: str, actual_tokens: int) -> None:
        with self._lock:
            job = self.jobs[job_id]
            job.cost_state = CostState.SETTLED
            job.settled_tokens = actual_tokens


# ===========================================================================
# 2. HTTP client connection lifecycle — SSE subscription (disconnect is local)
# ===========================================================================
@dataclass
class SseSubscription:
    subscription_id: str
    job_id: str
    connected: bool = True


class SubscriptionRegistry:
    """Models SSE subscriptions to a durable Job's progress/event stream. A disconnect ends ONLY
    that subscription; it NEVER touches the JobStore (an HTTP-lifecycle event, not a Job event)."""

    def __init__(self) -> None:
        self.subscriptions: dict[str, SseSubscription] = {}

    def subscribe(self, job_id: str) -> SseSubscription:
        sub = SseSubscription(subscription_id=str(uuid.uuid4()), job_id=job_id)
        self.subscriptions[sub.subscription_id] = sub
        return sub

    def disconnect(self, subscription_id: str) -> None:
        sub = self.subscriptions.get(subscription_id)
        if sub is not None:
            sub.connected = False  # subscription ended; the durable Job is intentionally untouched

    def active_count(self, job_id: str) -> int:
        return sum(1 for s in self.subscriptions.values() if s.job_id == job_id and s.connected)


def reconnect_view(store: JobStore, job_id: str) -> dict:
    """A reconnecting browser reads DURABLE Job state + safe progress events — NOT a replay of a
    Provider token stream (which is transient and never the durable truth)."""
    job = store.jobs[job_id]
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "cost_state": job.cost_state.value,
        "events": [dict(e) for e in job.events],   # safe lifecycle milestones only
    }


# ===========================================================================
# 3. Provider request lifecycle — transient token stream + best-effort abort
# ===========================================================================
class FakeProviderStream:
    """A provider-neutral token stream for ONE Provider request. Tokens are TRANSIENT; they are
    never default-persisted as JobEvents (Day53 raw-data minimization). Tracks whether it was
    started and best-effort aborted, and its (possibly unknown) usage."""

    def __init__(self, tokens: list[str], *, total_tokens: Optional[int] = None,
                 request_id: Optional[str] = None) -> None:
        self._tokens = tokens
        self.total_tokens = total_tokens          # None models UNKNOWN usage (never coerced to 0)
        self.request_id = request_id
        self.started = False
        self.aborted = False

    def __iter__(self) -> Iterator[str]:
        self.started = True
        for tok in self._tokens:
            if self.aborted:
                return
            yield tok

    def abort(self) -> None:
        """Best-effort Provider abort/stream close. Does NOT prove remote execution stopped or
        that cost is zero."""
        self.aborted = True


class FakeProvider:
    """Provider-neutral seam. `.calls` proves whether the Provider was actually contacted (used
    to assert a pre-call cancellation makes zero Provider calls)."""

    def __init__(self, stream_factory: Callable[[], FakeProviderStream]) -> None:
        self._stream_factory = stream_factory
        self.calls = 0

    def open_stream(self) -> FakeProviderStream:
        self.calls += 1
        return self._stream_factory()


# ===========================================================================
# 4. Router: authorize + persist a durable cancellation/expiry intent (no terminal write)
# ===========================================================================
def request_cancellation(store: JobStore, job_id: str, *, actor: str, reason: str, now: datetime,
                         kind: IntentKind = IntentKind.USER_CancellATION if False else IntentKind.USER_CANCELLATION,
                         release_version: Optional[str] = None) -> CancellationIntent:
    """Router-level: an authorized cancel/expiry request persists a DURABLE intent FIRST. It must
    NOT directly write `cancelled` merely because an HTTP request arrived — the Worker reacts
    cooperatively and a guarded transition owns the terminal fact."""
    return store.persist_cancellation_intent(job_id, kind=kind, reason=reason, actor=actor,
                                             now=now, release_version=release_version)


# ===========================================================================
# 5. Worker: cooperative cancellation checks + guarded terminal transition
# ===========================================================================
class WorkerOutcome(str, Enum):
    COMPLETED = "completed"                     # guarded running -> succeeded
    CANCELLED_BEFORE_CALL = "cancelled_before_call"   # intent seen pre-call: no Provider call
    CANCELLED_MID_STREAM = "cancelled_mid_stream"     # best-effort abort; unknown cost retained
    TIMED_OUT_PENDING = "timed_out_pending"    # Provider timeout: PENDING_RECONCILIATION
    COMPLETION_NOOP = "completion_noop"         # guarded zero rows -> stop (already terminal)


@dataclass
class WorkerResult:
    outcome: WorkerOutcome
    provider_calls: int
    tokens_seen: int = 0


def run_worker(
    store: JobStore,
    provider: FakeProvider,
    job_id: str,
    *,
    now: datetime,
    complete_with_tokens: Optional[int] = None,
    simulate_timeout: bool = False,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> WorkerResult:
    """Cooperative Worker. Order of cooperative cancellation checks:
      1. BEFORE the Provider call: if a durable intent exists, do NOT call the Provider and try a
         guarded terminal cancellation.
      2. DURING the Provider stream: at safe points, if a durable intent (or an injected
         `cancel_check`) fires, best-effort abort the Provider stream, STOP publishing tokens,
         record safe correlation evidence, and try a guarded terminal cancellation — this does
         NOT prove remote stop or zero cost, so unknown usage stays reconciliation_pending.
      3. Provider timeout -> record PENDING_RECONCILIATION (unknown outcome/usage), no fabricated
         failure/zero cost, no blind re-call.
      4. Otherwise complete via a guarded running -> succeeded transition.
    Never publishes raw Provider tokens as durable JobEvents."""
    # (1) pre-call cooperative check
    if store.open_intent(job_id) is not None:
        outcome = store.guarded_terminal_transition(job_id, JobStatus.CANCELLED, now=now)
        store.add_event(job_id, "job.cancellation_observed", stage="pre_provider_call")
        return WorkerResult(
            WorkerOutcome.CANCELLED_BEFORE_CALL if outcome is TransitionOutcome.WON
            else WorkerOutcome.COMPLETION_NOOP,
            provider_calls=provider.calls,  # 0 — the Provider was never contacted
        )

    if simulate_timeout:
        provider.calls += 1  # the call was attempted but our side received no response in time
        store.record_timeout_pending(job_id)
        return WorkerResult(WorkerOutcome.TIMED_OUT_PENDING, provider_calls=provider.calls)

    stream = provider.open_stream()
    tokens_seen = 0
    for _tok in stream:  # transient tokens streamed to the client; NOT persisted as JobEvents
        tokens_seen += 1
        # (2) mid-stream cooperative check
        if store.open_intent(job_id) is not None or (cancel_check is not None and cancel_check()):
            stream.abort()  # best-effort; does NOT prove remote stop or zero cost
            store.hold_cost_reconciliation(job_id)  # unknown usage -> reconciliation_pending
            store.add_event(job_id, "job.cancellation_observed", stage="mid_stream",
                            provider_request_id=stream.request_id)
            outcome = store.guarded_terminal_transition(job_id, JobStatus.CANCELLED, now=now)
            return WorkerResult(
                WorkerOutcome.CANCELLED_MID_STREAM if outcome is TransitionOutcome.WON
                else WorkerOutcome.COMPLETION_NOOP,
                provider_calls=provider.calls, tokens_seen=tokens_seen,
            )

    # (4) guarded completion — business success + cost settlement (Day53 semantics reused)
    outcome = store.guarded_terminal_transition(job_id, JobStatus.SUCCEEDED, now=now)
    if outcome is TransitionOutcome.WON:
        actual = complete_with_tokens if complete_with_tokens is not None else stream.total_tokens
        if actual is not None:
            store.settle_cost(job_id, actual)
        else:
            store.hold_cost_reconciliation(job_id)  # valid success, unknown usage -> pending
        with store._lock:
            store.jobs[job_id].result_artifact = {"summary": "validated-domain-result",
                                                  "provider_request_id": stream.request_id}
        return WorkerResult(WorkerOutcome.COMPLETED, provider_calls=provider.calls,
                            tokens_seen=tokens_seen)
    return WorkerResult(WorkerOutcome.COMPLETION_NOOP, provider_calls=provider.calls,
                        tokens_seen=tokens_seen)


def apply_cancellation(store: JobStore, job_id: str, *, now: datetime,
                       target: JobStatus = JobStatus.CANCELLED) -> TransitionOutcome:
    """Apply a durable intent as a guarded terminal transition (used by a re-observing Worker
    after a crash, or by the deadline/expiry path with target=EXPIRED). Repeats are absorbed:
    a second call after the Job is terminal returns ZERO_ROWS."""
    return store.guarded_terminal_transition(job_id, target, now=now)


def scan_open_intents(store: JobStore) -> list[str]:
    """A restarted Worker/Scheduler re-observes durable intents whose Job is still live. Intent
    observation is at-least-once; the guarded transition absorbs repeats. A crash after the intent
    was persisted therefore never loses it."""
    return [jid for jid, job in store.jobs.items()
            if job.intents and job.status in LIVE_STATUSES]


# ===========================================================================
# 6. Late result after a terminal Job — guarded, never overwrites
# ===========================================================================
class LateResultOutcome(str, Enum):
    COMPLETED = "completed"
    REFUSED_TERMINAL = "refused_terminal"      # Job already terminal (e.g. cancelled) -> no overwrite


def ingest_late_provider_result(store: JobStore, job_id: str, *, now: datetime,
                                actual_tokens: Optional[int]) -> LateResultOutcome:
    """A late VALID Provider result after a terminal cancellation/expiry CANNOT turn the Job into
    `succeeded`: the guarded transition sees a terminal status (zero rows), so no Result Artifact
    or success overwrite follows from the late path."""
    outcome = store.guarded_terminal_transition(job_id, JobStatus.SUCCEEDED, now=now)
    if outcome is TransitionOutcome.ZERO_ROWS:
        return LateResultOutcome.REFUSED_TERMINAL
    if actual_tokens is not None:
        store.settle_cost(job_id, actual_tokens)
    with store._lock:
        store.jobs[job_id].result_artifact = {"summary": "validated-domain-result"}
    return LateResultOutcome.COMPLETED


# ===========================================================================
# 7. Erroneous-disconnect-policy incident: rollback + evidence-based recovery
# ===========================================================================
@dataclass
class DisconnectPolicy:
    """Models the buggy deployment where an SSE disconnect wrongly created a cancellation intent.
    Rolling the policy back stops NEW harm; it is NOT a business-fact rollback."""

    disconnect_creates_cancel_intent: bool = False
    release_version: Optional[str] = None

    def rollback(self) -> None:
        self.disconnect_creates_cancel_intent = False  # stop new harmful intents


def on_sse_disconnect(store: JobStore, policy: DisconnectPolicy, subscription: SseSubscription,
                      registry: SubscriptionRegistry, *, now: datetime) -> Optional[CancellationIntent]:
    """Correct behavior: a disconnect ends the subscription only. The BUGGY policy additionally
    (and wrongly) persists a cancellation intent — modeled so the recovery exercise has evidence."""
    registry.disconnect(subscription.subscription_id)
    if policy.disconnect_creates_cancel_intent:
        return store.persist_cancellation_intent(
            subscription.job_id, kind=IntentKind.USER_CANCELLATION,
            reason="sse_disconnect (erroneous policy)", actor="disconnect_bug", now=now,
            release_version=policy.release_version,
        )
    return None


def build_affected_set(store: JobStore, *, release_version: str, window_start: datetime,
                       window_end: datetime) -> list[tuple[str, CancellationIntent]]:
    """Build the affected set from release VERSION + a bounded TIME WINDOW (the period the bad
    release was active — evidence, NOT a retry delay) + stable intent IDs. Used to triage, never
    to bulk-flip."""
    hits: list[tuple[str, CancellationIntent]] = []
    for jid, job in store.jobs.items():
        for intent in job.intents:
            if (intent.release_version == release_version
                    and intent.actor == "disconnect_bug"
                    and window_start <= intent.requested_at <= window_end):
                hits.append((jid, intent))
    return hits


class RecoveryClassification(str, Enum):
    RECONCILE_UNKNOWN_EXTERNAL = "reconcile_unknown_external"  # request id exists, usage unknown -> reconcile
    NO_PROVIDER_EXECUTION_EVIDENCE = "no_provider_execution_evidence"  # nothing proves a Provider ran


def classify_recovery(job: Job) -> RecoveryClassification:
    """Evidence-based recovery classification. A client idempotency key proves logical Job
    ACCEPTANCE only — NOT Provider execution. Provider request/correlation evidence decides
    reconciliation. If a request id exists but result/usage are unknown, retain the reservation
    and reconcile; NEVER blindly re-call the Provider. Any re-execution must be explicit,
    authorized, auditable, and evidence-based (out of Day54 scope)."""
    if job.provider_request_id is not None and job.settled_tokens is None:
        return RecoveryClassification.RECONCILE_UNKNOWN_EXTERNAL
    return RecoveryClassification.NO_PROVIDER_EXECUTION_EVIDENCE
