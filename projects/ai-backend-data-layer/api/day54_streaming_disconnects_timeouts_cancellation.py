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

The streaming/lifecycle/cancellation control flow is Python-standard-library only; the late-result
path REUSES Day53's real (pydantic-backed) strict structured-output validation gate
(`StructuredOutputValidator` + `SchemaRegistry`) so it does not weaken Day53's guarantees.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Iterator, Optional

# Reuse Day53's REAL strict structured-output validation gate + server-owned schema registry —
# the SAME gate, not a weakened Day54 copy (P1-4). This makes pydantic a Day54 dependency too.
from day53_openai_provider_structured_output import (
    SchemaRegistry,
    StructuredOutputValidator,
    ValidationOutcome,
)


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
    attempt_id: Optional[str] = None                      # persisted execution/attempt identity
    schema_name: Optional[str] = None                     # bound execution contract (Day53 schema)
    schema_version: Optional[str] = None


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
                           correlation_id: Optional[str] = None, attempt_id: Optional[str] = None,
                           schema_name: Optional[str] = None,
                           schema_version: Optional[str] = None) -> Job:
        job = Job(job_id=job_id, tenant_id=tenant_id, reserved_tokens=reserved_tokens,
                  correlation_id=correlation_id, attempt_id=attempt_id,
                  schema_name=schema_name, schema_version=schema_version)
        self.jobs[job_id] = job
        return job

    def record_provider_request_id(self, job_id: str, provider_request_id: Optional[str]) -> None:
        """P1-3: as soon as the external Provider request is opened and its id is available,
        persist it to protected Job execution evidence (safe correlation only — NOT a raw prompt
        or payload). This is what lets a later mid-stream cancellation / timeout be reconciled as
        RECONCILE_UNKNOWN_EXTERNAL instead of NO_PROVIDER_EXECUTION_EVIDENCE."""
        if provider_request_id is None:
            return
        with self._lock:
            job = self.jobs[job_id]
            if job.provider_request_id is None:
                job.provider_request_id = provider_request_id

    def guarded_complete_success(self, job_id: str, *, artifact: dict, actual_tokens: Optional[int],
                                 now: datetime) -> TransitionOutcome:
        """Atomic guarded `running/pending -> succeeded` that ALSO writes the Result Artifact + cost
        in the SAME critical section, so duplicate/concurrent late deliveries produce the fact at
        most once. Unknown usage is retained as reconciliation_pending, never fabricated as 0."""
        with self._lock:
            job = self.jobs[job_id]
            if job.status not in LIVE_STATUSES:
                return TransitionOutcome.ZERO_ROWS
            job.status = JobStatus.SUCCEEDED
            if actual_tokens is not None:
                job.cost_state = CostState.SETTLED
                job.settled_tokens = actual_tokens
            else:
                job.cost_state = CostState.RECONCILIATION_PENDING
            job.result_artifact = dict(artifact)
            job.events.append({"type": "job.succeeded", "job_id": job_id,
                               "correlation_id": job.correlation_id})
            return TransitionOutcome.WON

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
                         kind: IntentKind = IntentKind.USER_CANCELLATION,
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
    CANCELLED_PRE_COMPLETION = "cancelled_pre_completion"  # intent seen AFTER the last token, BEFORE completion
    TIMED_OUT_PENDING = "timed_out_pending"    # Provider timeout: PENDING_RECONCILIATION
    COMPLETION_NOOP = "completion_noop"         # guarded zero rows -> stop (already terminal)


def terminal_for_intent(kind: IntentKind) -> JobStatus:
    """Map a durable intent kind to its guarded TERMINAL status. A user cancellation and a Job
    deadline share the durable/auditable/cooperative/guarded protocol but end in DIFFERENT
    terminal facts (P1-1)."""
    return JobStatus.EXPIRED if kind is IntentKind.DEADLINE_EXPIRY else JobStatus.CANCELLED


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
    """Cooperative Worker. Order of cooperative durable-intent checks:
      1. BEFORE the Provider call: if a durable intent exists, do NOT call the Provider and try a
         guarded terminal transition (CANCELLED for a user cancel, EXPIRED for a deadline).
      2. As soon as the Provider request is opened, persist its provider_request_id to protected
         Job execution evidence (P1-3) — before consuming tokens / handling cancel / timeout.
      3. DURING the Provider stream: at safe points, if a durable intent (or an injected
         `cancel_check`) fires, best-effort abort the stream, STOP publishing tokens, record safe
         correlation evidence, hold unknown cost as reconciliation_pending, and try a guarded
         terminal transition (kind-derived). This does NOT prove remote stop or zero cost.
      4. AFTER the last token but BEFORE completion, RE-CHECK the durable intent (P1-2): if one now
         exists, do NOT write `succeeded` — follow the guarded cancel/expiry terminal path instead.
      5. Provider timeout -> PENDING_RECONCILIATION (unknown outcome/usage), no fabricated
         failure/zero cost, no blind re-call.
    Never publishes raw Provider tokens as durable JobEvents."""
    # (1) pre-call cooperative check — kind-derived terminal
    intent = store.open_intent(job_id)
    if intent is not None:
        target = terminal_for_intent(intent.kind)
        outcome = store.guarded_terminal_transition(job_id, target, now=now)
        store.add_event(job_id, "job.cancellation_observed", stage="pre_provider_call",
                        terminal=target.value)
        return WorkerResult(
            WorkerOutcome.CANCELLED_BEFORE_CALL if outcome is TransitionOutcome.WON
            else WorkerOutcome.COMPLETION_NOOP,
            provider_calls=provider.calls,  # 0 — the Provider was never contacted
        )

    if simulate_timeout:
        # The request was opened (id known) but our side received no response in time.
        stream = provider.open_stream()
        store.record_provider_request_id(job_id, stream.request_id)  # (2) persist evidence first
        store.record_timeout_pending(job_id)
        return WorkerResult(WorkerOutcome.TIMED_OUT_PENDING, provider_calls=provider.calls)

    stream = provider.open_stream()
    store.record_provider_request_id(job_id, stream.request_id)  # (2) persist evidence immediately
    tokens_seen = 0
    for _tok in stream:  # transient tokens streamed to the client; NOT persisted as JobEvents
        tokens_seen += 1
        # (3) mid-stream cooperative check
        mid_intent = store.open_intent(job_id)
        if mid_intent is not None or (cancel_check is not None and cancel_check()):
            stream.abort()  # best-effort; does NOT prove remote stop or zero cost
            store.hold_cost_reconciliation(job_id)  # unknown usage -> reconciliation_pending
            store.add_event(job_id, "job.cancellation_observed", stage="mid_stream",
                            provider_request_id=stream.request_id)
            target = terminal_for_intent(mid_intent.kind) if mid_intent is not None else JobStatus.CANCELLED
            outcome = store.guarded_terminal_transition(job_id, target, now=now)
            return WorkerResult(
                WorkerOutcome.CANCELLED_MID_STREAM if outcome is TransitionOutcome.WON
                else WorkerOutcome.COMPLETION_NOOP,
                provider_calls=provider.calls, tokens_seen=tokens_seen,
            )

    # (4) FINAL cooperative check AFTER the last token, BEFORE completion (P1-2)
    final_intent = store.open_intent(job_id)
    if final_intent is not None:
        target = terminal_for_intent(final_intent.kind)
        store.hold_cost_reconciliation(job_id)  # do not fabricate a settled cost while cancelling
        store.add_event(job_id, "job.cancellation_observed", stage="post_stream_pre_completion",
                        provider_request_id=stream.request_id, terminal=target.value)
        outcome = store.guarded_terminal_transition(job_id, target, now=now)
        return WorkerResult(
            WorkerOutcome.CANCELLED_PRE_COMPLETION if outcome is TransitionOutcome.WON
            else WorkerOutcome.COMPLETION_NOOP,
            provider_calls=provider.calls, tokens_seen=tokens_seen,
        )

    # (5) guarded completion — business success + cost settlement (Day53 semantics reused)
    actual = complete_with_tokens if complete_with_tokens is not None else stream.total_tokens
    outcome = store.guarded_complete_success(
        job_id, artifact={"summary": "validated-domain-result", "provider_request_id": stream.request_id},
        actual_tokens=actual, now=now,
    )
    return WorkerResult(
        WorkerOutcome.COMPLETED if outcome is TransitionOutcome.WON else WorkerOutcome.COMPLETION_NOOP,
        provider_calls=provider.calls, tokens_seen=tokens_seen,
    )


def apply_cancellation(store: JobStore, job_id: str, *, now: datetime,
                       target: Optional[JobStatus] = None) -> TransitionOutcome:
    """Apply a durable intent as a guarded terminal transition (used by a re-observing Worker
    after a crash). When `target` is not given, it is DERIVED from the Job's open intent kind
    (CANCELLED for a user cancel, EXPIRED for a deadline) so the crash-recovery path stays
    semantically consistent with the Worker's pre-call/mid-stream paths (P1-1). Repeats are
    absorbed: a second call after the Job is terminal returns ZERO_ROWS."""
    if target is None:
        intent = store.open_intent(job_id)
        target = terminal_for_intent(intent.kind) if intent is not None else JobStatus.CANCELLED
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
    COMPLETED = "completed"                     # matched + validated late result completed the Job (once)
    REFUSED_TERMINAL = "refused_terminal"       # Job already terminal (cancelled/expired/...) -> guarded no-op
    REFUSED_NOT_AWAITING = "refused_not_awaiting"   # Job not in a reconciliation-awaiting state
    REFUSED_IDENTITY_MISMATCH = "refused_identity_mismatch"  # job/attempt/correlation/provider_request_id mismatch or missing
    REFUSED_INVALID_PAYLOAD = "refused_invalid_payload"     # failed the Day53 strict validation gate


def ingest_late_provider_result(
    store: JobStore,
    job_id: str,
    *,
    attempt_id: str,
    correlation_id: str,
    provider_request_id: str,
    raw_payload: dict,
    validator: StructuredOutputValidator,
    now: datetime,
    actual_tokens: Optional[int] = None,
) -> LateResultOutcome:
    """A late Provider result reuses Day53's identity-binding + strict validation boundary — it is
    the EQUIVALENT minimal control-flow abstraction of Day53's `ingest_late_outcome`, not a weaker
    one. It NEVER calls the Adapter/transport. A result completes the Job ONLY when ALL hold:

      * the Job exists and is NON-terminal AND awaiting reconciliation (PENDING_RECONCILIATION);
      * `job_id` + `attempt_id` + `correlation_id` + `provider_request_id` match the persisted
        execution/attempt evidence (a MISSING id is as invalid as a different one);
      * the payload passes the Day53 strict structured-output validation gate for the Job's bound
        `(schema_name, schema_version)` execution contract.

    Any mismatch / missing id / not-awaiting / terminal Job / invalid payload is a SIDE-EFFECT-FREE
    refusal: no status/cost/Result Artifact/event change, and no Provider call. Duplicate/concurrent
    matched deliveries complete the fact AT MOST ONCE via the guarded transition (a terminal Job
    then returns REFUSED_TERMINAL)."""
    job = store.jobs.get(job_id)
    if job is None:
        return LateResultOutcome.REFUSED_IDENTITY_MISMATCH
    # Terminal Job -> guarded no-op (a late result cannot overwrite a cancelled/expired/succeeded fact).
    if job.status in TERMINAL_STATUSES:
        return LateResultOutcome.REFUSED_TERMINAL
    # Must be bound to a persisted attempt that is awaiting reconciliation (e.g. after a timeout).
    if job.status is not JobStatus.PENDING_RECONCILIATION:
        return LateResultOutcome.REFUSED_NOT_AWAITING
    # Identity binding: every persisted id must be present AND equal (missing == mismatch).
    if (job.attempt_id is None or attempt_id != job.attempt_id
            or correlation_id != job.correlation_id
            or job.provider_request_id is None or provider_request_id != job.provider_request_id):
        return LateResultOutcome.REFUSED_IDENTITY_MISMATCH
    # Day53 strict validation gate against the Job's bound execution contract — before any side effect.
    result = validator.validate(job.schema_name or "", job.schema_version or "", raw_payload)
    if result.outcome is not ValidationOutcome.VALID:
        return LateResultOutcome.REFUSED_INVALID_PAYLOAD
    # Guarded, at-most-once completion with the validated domain result + safe metadata only.
    artifact = {
        "domain_result": result.domain_result,
        "schema_name": job.schema_name,
        "schema_version": job.schema_version,
        "provider_request_id": job.provider_request_id,
        "correlation_id": job.correlation_id,
    }
    outcome = store.guarded_complete_success(job_id, artifact=artifact, actual_tokens=actual_tokens, now=now)
    return LateResultOutcome.COMPLETED if outcome is TransitionOutcome.WON else LateResultOutcome.REFUSED_TERMINAL


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
