"""Day55 — Celery, Worker Execution and Long-running AI Jobs.

Move accepted long-running AI Jobs from the Day50 Outbox Relay onto a SUPPORTED Celery broker
transport and Celery Workers, WITHOUT losing durable business truth, at-least-once delivery
safety, Day54 cancellation semantics, or honest external-side-effect recovery.

CORE MENTAL MODEL
-----------------
    Outbox durable intent
      -> publish to a supported Celery broker            (publish BEFORE the checkpoint)
      -> write the Outbox published checkpoint
      -> at-least-once delivery / redelivery
      -> PostgreSQL GUARDED CLAIM decides Provider execution authority   (first duplicate-call gate)
      -> durable Attempt + correlation evidence
      -> Provider call OUTSIDE any DB transaction
      -> validate BEFORE guarded completion

    unknown Provider outcome  -> PENDING_RECONCILIATION -> reservation retained -> NO blind re-call
    cancel request            -> durable intent FIRST -> optional revoke -> cooperative Worker check
                              -> one guarded winner (cancelled / expired / succeeded)

    Celery ACK / SUCCESS  == delivery handled           != Job business success

HARD BOUNDARIES (kept honest everywhere in this module):
    Celery ACK/SUCCESS            != Job succeeded
    Broker redelivery             != permission to call the Provider again
    Worker identity               != durable Attempt identity
    Provider timeout / Worker loss!= proof of no Provider execution or zero cost
    Celery revoke                 != durable cancellation authority
    configuration rollback        != business-fact rollback

EVIDENCE LABEL (do not conflate the tiers):
  * CONCEPTUAL DESIGN: the delivery/execution/recovery boundaries described here + in the runbook.
  * LOCAL IN-MEMORY CONTROL-FLOW RUNTIME: what the pytest suite executes — an in-memory model of a
    Celery-like broker (publish/deliver/redeliver/ACK/visibility timeout), the Outbox publish-before
    -checkpoint ordering, the PostgreSQL-owned guarded claim, ACK timing, poison classification,
    the Day54 durable cancellation protocol, graceful drain, and evidence-based incident repair.
    This proves APPLICATION CONTROL FLOW only.
  * NOT RUN (no such claim): a real Celery broker (Redis/RabbitMQ) transport, a real Worker process,
    real ACK/redelivery/visibility timeouts, Worker-loss/OOM fault injection, real PostgreSQL
    transactions/isolation, the real OpenAI SDK/network/Provider. Day56 owns retry/backoff, rate
    limits, token cost, and backpressure depth — NOT implemented here. Day57 owns the expanded
    integration/failure-injection test suite.

This module is Python standard library only for the delivery/execution/recovery control flow; the
guarded completion REUSES Day53's real pydantic-backed strict validation gate and Day54's durable
cancellation terminal mapping (imported, not re-implemented), so those guarantees are not weakened.

SECURITY: no real credentials, raw prompts, Document content, or raw Provider payloads/tokens are
persisted or logged. The Celery envelope carries only small, safe routing metadata; PostgreSQL
remains authoritative for Job state, budget, tenant authority, and result truth.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional

# Reuse Day53's REAL strict structured-output validation gate (guarded completion validates the
# Provider payload before it becomes durable truth) and Day54's durable cancellation terminal
# mapping (user cancellation -> CANCELLED, deadline -> EXPIRED). Same gates, not weakened copies.
from day53_openai_provider_structured_output import (
    SchemaRegistry,
    StructuredOutputValidator,
    ValidationOutcome,
)
from day54_streaming_disconnects_timeouts_cancellation import IntentKind


# ===========================================================================
# 1. Durable Job lifecycle (PostgreSQL-owned business fact in production)
# ===========================================================================
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"                              # Day54 durable cancellation intent
    EXPIRED = "expired"                                  # Day54 durable deadline intent
    PENDING_RECONCILIATION = "pending_reconciliation"    # Provider timeout / Worker loss: unknown
    QUARANTINED = "quarantined"                          # deterministic Job-contract poison


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED,
     JobStatus.EXPIRED, JobStatus.QUARANTINED}
)
# Still-claimable / still-completable / still-cancellable:
LIVE_STATUSES = frozenset(
    {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PENDING_RECONCILIATION}
)


def terminal_for_intent(kind: IntentKind) -> "JobStatus":
    """Day54 durable-cancellation terminal mapping, expressed in Day55's JobStatus:
    USER_CANCELLATION -> CANCELLED, DEADLINE_EXPIRY -> EXPIRED. Same semantics as Day54's
    terminal_for_intent; re-expressed here so the terminal is THIS module's Job lifecycle enum."""
    return JobStatus.CANCELLED if kind is IntentKind.USER_CANCELLATION else JobStatus.EXPIRED


class CostState(str, Enum):
    NONE = "none"
    RESERVED = "reserved"
    RECONCILIATION_PENDING = "reconciliation_pending"    # Provider may have run; cost unknown
    SETTLED = "settled"


@dataclass
class CancellationIntent:
    """Durable, auditable cancellation/deadline intent (Day54). Persisted BEFORE any signal."""
    kind: IntentKind
    reason: str
    actor: str
    created_at: datetime
    version: int = 1


@dataclass
class Attempt:
    """Durable execution attempt. Worker identity and broker delivery are NOT this identity."""
    attempt_id: str
    attempt_number: int
    provider_idempotency_key: str          # retained across redelivery of the SAME attempt
    correlation_id: str
    provider_request_id: Optional[str] = None   # external execution evidence, recorded at open
    schema_name: str = "research_summary"
    schema_version: str = "v1"


@dataclass
class Job:
    job_id: str
    tenant_id: str
    client_idempotency_key: str
    status: JobStatus
    reserved_tokens: int
    execution_contract_version: str            # persisted server-owned contract version
    cost_state: CostState = CostState.RESERVED
    settled_tokens: Optional[int] = None
    open_attempt_id: Optional[str] = None
    lease_owner: Optional[str] = None          # SECONDARY ownership; NOT the first duplicate gate
    lease_expiry: Optional[datetime] = None
    intent: Optional[CancellationIntent] = None
    result_artifact: Optional[dict] = None
    release_version: Optional[str] = None      # release that produced the current running state
    poison_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# What this Worker/Job can execute — supported compatibility sets
# ---------------------------------------------------------------------------
SUPPORTED_ENVELOPE_VERSIONS = frozenset({"job.dispatch.v1"})       # can the Worker PARSE the message
SUPPORTED_CONTRACT_VERSIONS = frozenset({"exec.v1"})              # can the Worker EXECUTE the Job


class TransitionOutcome(str, Enum):
    APPLIED = "applied"          # one guarded row changed
    NO_OP = "no_op"              # zero rows: someone else already won / not live


# ===========================================================================
# 2. Identity layers (documentation-level; each is a DIFFERENT thing)
# ===========================================================================
IDENTITY_LAYERS = (
    "client_idempotency_key = one logical API command",
    "job_id                 = durable business fact",
    "celery_delivery_id     = broker delivery occurrence (redelivery changes it)",
    "worker_id              = process handling a delivery",
    "attempt_id             = durable execution attempt",
    "provider_request_id    = external execution evidence",
    "provider_idempotency_key = one intended Provider call",
    "correlation_id         = tracing / reconciliation linkage",
)


# ===========================================================================
# 3. Celery-like broker (in-memory model of a SUPPORTED broker transport)
# ===========================================================================
@dataclass
class Envelope:
    """Small, safe routing metadata. NEVER the durable Job truth."""
    task_name: str
    envelope_version: str
    job_id: str
    headers: dict = field(default_factory=dict)


@dataclass
class Delivery:
    delivery_id: str
    envelope: Envelope
    delivery_count: int          # 1 on first delivery, >1 on redelivery (at-least-once)


class DeadLetterQueue:
    """Envelope/transport poison that could not even be parsed into a Job."""
    def __init__(self) -> None:
        self.items: list[Delivery] = []

    def quarantine(self, delivery: Delivery, reason: str) -> None:
        self.items.append(delivery)


class CeleryBrokerSim:
    """Minimal at-least-once broker: publish -> deliver -> (ack | visibility-timeout redelivery).

    Models Celery delivery semantics only. It is NOT the Day40 custom Redis Streams / Consumer
    Group design and does NOT reimplement XADD/XREADGROUP/XACK/pending-entry reclaim. A real
    deployment uses Celery's supported broker transport (Redis or RabbitMQ).
    """

    def __init__(self) -> None:
        self._ready: deque[Delivery] = deque()
        self._inflight: dict[str, Delivery] = {}          # delivered, not yet ACKed
        self.dead_letter = DeadLetterQueue()
        self.publish_count = 0

    def publish(self, envelope: Envelope) -> None:
        self.publish_count += 1
        self._ready.append(Delivery(delivery_id=_new_id("dlv"), envelope=envelope, delivery_count=1))

    def deliver(self) -> Optional[Delivery]:
        if not self._ready:
            return None
        d = self._ready.popleft()
        self._inflight[d.delivery_id] = d
        return d

    def ack(self, delivery_id: str) -> None:
        """Late-ACK success: delivery is reliably handled and removed."""
        self._inflight.pop(delivery_id, None)

    def visibility_timeout(self, delivery_id: str) -> None:
        """Worker crashed/lost before ACK -> broker redelivers (delivery_count increments)."""
        d = self._inflight.pop(delivery_id, None)
        if d is not None:
            self._ready.append(
                Delivery(delivery_id=_new_id("dlv"), envelope=d.envelope,
                         delivery_count=d.delivery_count + 1)
            )

    def dead_letter_delivery(self, delivery: Delivery, reason: str) -> None:
        self.dead_letter.quarantine(delivery, reason)

    def depth(self) -> int:
        return len(self._ready)


# ===========================================================================
# 4. Outbox Relay — publish BEFORE the checkpoint
# ===========================================================================
class OutboxRelay:
    """Publish the Celery task BEFORE writing the Outbox published checkpoint.

    A crash between publish and checkpoint may DUPLICATE the publish, which the Worker absorbs via
    the guarded claim. Checkpointing first could silently STRAND a queued Job with no broker
    message. An ambiguous publish outcome is NOT success: retain/recover the event and accept
    at-least-once delivery.
    """

    def __init__(self, broker: CeleryBrokerSim) -> None:
        self.broker = broker
        self.published_checkpoints: set[str] = set()

    def relay(self, job: Job, *, crash_after_publish: bool = False) -> bool:
        envelope = Envelope(
            task_name="run_ai_job",
            envelope_version="job.dispatch.v1",
            job_id=job.job_id,
            headers={"tenant_id": job.tenant_id},     # safe routing metadata only
        )
        self.broker.publish(envelope)                 # 1) publish FIRST
        if crash_after_publish:
            # Crash before checkpoint: the message is already queued. On recovery the relay will
            # publish again (duplicate), which is safe because the Worker's guarded claim dedups.
            return False
        self.published_checkpoints.add(job.job_id)    # 2) checkpoint AFTER a confirmed publish
        return True


# ===========================================================================
# 5. JobStore — PostgreSQL-owned durable truth + the GUARDED CLAIM
# ===========================================================================
class ClaimStatus(str, Enum):
    GRANTED = "granted"                 # one row: this Worker has execution authority
    CONFLICT = "conflict"               # another live claim holds it -> stop
    ALREADY_TERMINAL = "already_terminal"
    RECONCILE_ONLY = "reconcile_only"   # PENDING_RECONCILIATION: load evidence, do NOT re-call


@dataclass
class ClaimResult:
    status: ClaimStatus
    attempt: Optional[Attempt] = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._attempts: dict[str, Attempt] = {}
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._lease = timedelta(minutes=5)

    # --- creation / lookup -------------------------------------------------
    def create_queued_job(self, job_id: str, *, tenant_id: str, client_idempotency_key: str,
                          reserved_tokens: int, execution_contract_version: str = "exec.v1",
                          release_version: str = "r1") -> Job:
        job = Job(job_id=job_id, tenant_id=tenant_id,
                  client_idempotency_key=client_idempotency_key, status=JobStatus.QUEUED,
                  reserved_tokens=reserved_tokens,
                  execution_contract_version=execution_contract_version,
                  release_version=release_version)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    def add_event(self, job_id: str, event_type: str, **safe_fields: object) -> None:
        # Only low-frequency SAFE lifecycle milestones; never raw tokens/prompts/Documents.
        self.events.append({"job_id": job_id, "type": event_type, **safe_fields})

    # --- durable cancellation intent (Day54) -------------------------------
    def persist_cancellation_intent(self, job_id: str, *, kind: IntentKind, reason: str,
                                    actor: str, now: datetime) -> CancellationIntent:
        with self._lock:
            job = self._jobs[job_id]
            if job.intent is None:
                job.intent = CancellationIntent(kind=kind, reason=reason, actor=actor,
                                                created_at=now)
                self.add_event(job_id, "cancellation_intent_persisted", kind=kind.value)
            return job.intent

    def open_intent(self, job_id: str) -> Optional[CancellationIntent]:
        return self._jobs[job_id].intent

    # --- THE GUARDED CLAIM: first duplicate-call gate ----------------------
    def claim_execution(self, job_id: str, *, worker_id: str, now: datetime) -> ClaimResult:
        """Atomic guarded claim. Models:
            UPDATE jobs SET status='running', lease_owner=:w, open_attempt_id=:a
            WHERE job_id=:j AND status IN ('queued','running')
                  AND (lease_owner IS NULL OR lease_expiry < now) RETURNING *;
        A one-row result grants Provider execution authority; zero rows means STOP before the
        Provider call. Lease/fencing is a SECONDARY concern, never this first gate.
        """
        with self._lock:
            job = self._jobs[job_id]
            if job.status in TERMINAL_STATUSES:
                return ClaimResult(ClaimStatus.ALREADY_TERMINAL)
            if job.status == JobStatus.PENDING_RECONCILIATION:
                # Timeout/Worker-loss redelivery: do NOT re-call the Provider. Reconcile from the
                # existing Attempt evidence (Day54). This is not a fresh guarded completion.
                attempt = self._attempts.get(job.open_attempt_id) if job.open_attempt_id else None
                return ClaimResult(ClaimStatus.RECONCILE_ONLY, attempt=attempt)
            if (job.status == JobStatus.RUNNING and job.lease_owner is not None
                    and job.lease_expiry is not None and job.lease_expiry >= now
                    and job.lease_owner != worker_id):
                return ClaimResult(ClaimStatus.CONFLICT)      # another live Worker holds it
            # Grant. Redelivery/new Worker does NOT mint a new Attempt: retain the open one.
            if job.open_attempt_id is not None:
                attempt = self._attempts[job.open_attempt_id]     # same provider_idempotency_key
            else:
                attempt = Attempt(
                    attempt_id=_new_id("att"), attempt_number=1,
                    provider_idempotency_key=f"pik-{job_id}-1",   # deterministic per attempt
                    correlation_id=_new_id("cor"),
                )
                self._attempts[attempt.attempt_id] = attempt
                job.open_attempt_id = attempt.attempt_id
            job.status = JobStatus.RUNNING
            job.lease_owner = worker_id
            job.lease_expiry = now + self._lease
            self.add_event(job_id, "execution_claimed", worker_id=worker_id,
                           attempt_id=attempt.attempt_id)
            return ClaimResult(ClaimStatus.GRANTED, attempt=attempt)

    def record_provider_request_id(self, attempt_id: str, provider_request_id: str) -> None:
        """Persist external execution evidence AS SOON AS the Provider request is opened."""
        with self._lock:
            att = self._attempts[attempt_id]
            if att.provider_request_id is None:
                att.provider_request_id = provider_request_id
                self.add_event(att.correlation_id, "provider_request_id_recorded")

    # --- reconciliation / cost --------------------------------------------
    def mark_pending_reconciliation(self, job_id: str) -> TransitionOutcome:
        with self._lock:
            job = self._jobs[job_id]
            if job.status not in (JobStatus.RUNNING, JobStatus.QUEUED):
                return TransitionOutcome.NO_OP
            job.status = JobStatus.PENDING_RECONCILIATION
            job.cost_state = CostState.RECONCILIATION_PENDING   # unknown, retained; never 0
            self.add_event(job_id, "pending_reconciliation")
            return TransitionOutcome.APPLIED

    # --- guarded terminal transitions (exactly one winner) -----------------
    def guarded_terminal_transition(self, job_id: str, target: JobStatus, *,
                                    now: datetime) -> TransitionOutcome:
        with self._lock:
            job = self._jobs[job_id]
            if job.status not in LIVE_STATUSES:
                return TransitionOutcome.NO_OP        # zero rows: already terminal
            job.status = target
            self.add_event(job_id, "terminal_transition", to=target.value)
            return TransitionOutcome.APPLIED

    def guarded_complete_success(self, job_id: str, *, artifact: dict,
                                 actual_tokens: Optional[int], now: datetime) -> TransitionOutcome:
        with self._lock:
            job = self._jobs[job_id]
            if job.status not in LIVE_STATUSES:
                return TransitionOutcome.NO_OP        # cancellation/expiry already won
            job.status = JobStatus.SUCCEEDED
            job.result_artifact = artifact
            if actual_tokens is not None:
                job.settled_tokens = actual_tokens
                job.cost_state = CostState.SETTLED
            else:
                job.cost_state = CostState.RECONCILIATION_PENDING
            self.add_event(job_id, "completed_success")
            return TransitionOutcome.APPLIED

    def quarantine_job(self, job_id: str, *, reason: str) -> TransitionOutcome:
        with self._lock:
            job = self._jobs[job_id]
            if job.status in TERMINAL_STATUSES:
                return TransitionOutcome.NO_OP
            job.status = JobStatus.QUARANTINED
            job.poison_reason = reason
            self.add_event(job_id, "quarantined", reason=reason)
            return TransitionOutcome.APPLIED


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ===========================================================================
# 6. Fake deterministic Provider (no network, no credentials)
# ===========================================================================
class ProviderResultKind(str, Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"              # unknown outcome/usage
    TRANSIENT = "transient"          # retryable transport failure (Day56 owns backoff depth)


@dataclass
class FakeProvider:
    kind: ProviderResultKind
    payload: dict = field(default_factory=dict)
    usage_tokens: Optional[int] = None
    request_id: str = "req-fake-1"
    calls: int = 0

    def run(self, *, provider_idempotency_key: str) -> "FakeProvider":
        self.calls += 1
        return self


# ===========================================================================
# 7. Worker execution — ACK timing, poison, cancellation, reconciliation
# ===========================================================================
class AckMode(str, Enum):
    EARLY = "early"     # ACK before durable work: a crash silently LOSES the delivery
    LATE = "late"       # ACK after durable handling: a crash REDELIVERS; app absorbs duplicates


class WorkerOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    ENVELOPE_POISON_DEADLETTER = "envelope_poison_deadletter"
    CONTRACT_POISON_QUARANTINE = "contract_poison_quarantine"
    CANCELLED_PRE_CALL = "cancelled_pre_call"
    CANCELLED_MID_STREAM = "cancelled_mid_stream"
    CANCELLED_PRE_COMPLETION = "cancelled_pre_completion"
    DUPLICATE_NOOP = "duplicate_noop"          # guarded claim returned zero rows
    CLAIM_CONFLICT = "claim_conflict"          # another live Worker holds authority
    RECONCILE_NO_RECALL = "reconcile_no_recall"
    PENDING_RECONCILIATION = "pending_reconciliation"
    TRANSIENT_RETRY = "transient_retry"        # bounded retry belongs to Day56 depth
    VALIDATION_REFUSED = "validation_refused"


@dataclass
class WorkerResult:
    outcome: WorkerOutcome
    acked: bool
    provider_calls: int
    job_status: JobStatus


def run_worker(
    store: JobStore,
    broker: CeleryBrokerSim,
    delivery: Delivery,
    provider: FakeProvider,
    *,
    worker_id: str,
    now: datetime,
    ack_mode: AckMode = AckMode.LATE,
    validator: Optional[StructuredOutputValidator] = None,
    cancel_before_completion: bool = False,
) -> WorkerResult:
    """One Worker handling one broker delivery. ACK/SUCCESS means DELIVERY handled, never that the
    business Job is `succeeded`; `GET /jobs/{id}` reads the durable JobStore, not a result backend.
    """
    env = delivery.envelope

    # (a) ENVELOPE compatibility — BEFORE loading the Job. Can the Worker even parse the message?
    if env.envelope_version not in SUPPORTED_ENVELOPE_VERSIONS:
        broker.dead_letter_delivery(delivery, reason=f"unsupported envelope {env.envelope_version}")
        broker.ack(delivery.delivery_id)      # do NOT ordinary-requeue a deterministic poison
        return WorkerResult(WorkerOutcome.ENVELOPE_POISON_DEADLETTER, True, provider.calls,
                            JobStatus.QUEUED)

    job = store.get(env.job_id)

    # (b) Pre-call durable cancellation intent (Day54): zero Provider calls, guarded terminal.
    intent = store.open_intent(job.job_id)
    if intent is not None and job.status in (JobStatus.QUEUED,):
        store.guarded_terminal_transition(job.job_id, terminal_for_intent(intent.kind), now=now)
        broker.ack(delivery.delivery_id)
        return WorkerResult(WorkerOutcome.CANCELLED_PRE_CALL, True, provider.calls,
                            store.get(job.job_id).status)

    # (c) EXECUTION-CONTRACT compatibility — AFTER loading the Job. Can the Worker execute it?
    if job.execution_contract_version not in SUPPORTED_CONTRACT_VERSIONS:
        store.quarantine_job(job.job_id, reason=f"unsupported contract {job.execution_contract_version}")
        broker.ack(delivery.delivery_id)      # durable classification, not an infinite requeue
        return WorkerResult(WorkerOutcome.CONTRACT_POISON_QUARANTINE, True, provider.calls,
                            store.get(job.job_id).status)

    # (d) GUARDED CLAIM — the first duplicate-call gate.
    claim = store.claim_execution(job.job_id, worker_id=worker_id, now=now)
    if claim.status is ClaimStatus.ALREADY_TERMINAL:
        broker.ack(delivery.delivery_id)      # duplicate delivery of a finished Job: safe no-op
        return WorkerResult(WorkerOutcome.DUPLICATE_NOOP, True, provider.calls,
                            store.get(job.job_id).status)
    if claim.status is ClaimStatus.CONFLICT:
        # Another live Worker owns authority. Redeliver later (do not ACK away the work).
        return WorkerResult(WorkerOutcome.CLAIM_CONFLICT, False, provider.calls,
                            store.get(job.job_id).status)
    if claim.status is ClaimStatus.RECONCILE_ONLY:
        # Timeout/Worker-loss redelivery: reconcile from evidence, NO Provider re-call.
        broker.ack(delivery.delivery_id)
        return WorkerResult(WorkerOutcome.RECONCILE_NO_RECALL, True, provider.calls,
                            JobStatus.PENDING_RECONCILIATION)

    attempt = claim.attempt
    assert attempt is not None

    if ack_mode is AckMode.EARLY:
        # Anti-pattern demonstrated: ACK before durable work. A crash here loses the delivery with
        # the Job stuck RUNNING and no redelivery. Late ACK is the safe default.
        broker.ack(delivery.delivery_id)

    # (e) Provider call OUTSIDE any DB transaction. Record provider_request_id as soon as available.
    result = provider.run(provider_idempotency_key=attempt.provider_idempotency_key)
    store.record_provider_request_id(attempt.attempt_id, result.request_id)

    if result.kind is ProviderResultKind.TIMEOUT:
        # Unknown outcome/usage: PENDING_RECONCILIATION, reservation retained, NO blind re-call.
        store.mark_pending_reconciliation(job.job_id)
        if ack_mode is AckMode.LATE:
            broker.ack(delivery.delivery_id)
        return WorkerResult(WorkerOutcome.PENDING_RECONCILIATION, True, provider.calls,
                            JobStatus.PENDING_RECONCILIATION)

    if result.kind is ProviderResultKind.TRANSIENT:
        # Transient transport failure: bounded retry + backoff is Day56 depth. Retain Attempt +
        # evidence and let the delivery redeliver; do NOT quarantine, do NOT fabricate a result.
        if ack_mode is AckMode.LATE:
            broker.visibility_timeout(delivery.delivery_id)   # redeliver for a bounded retry
        return WorkerResult(WorkerOutcome.TRANSIENT_RETRY, False, provider.calls,
                            store.get(job.job_id).status)

    # (f) SUCCESS path: validate BEFORE guarded completion (Day53 strict gate).
    validator = validator or StructuredOutputValidator(SchemaRegistry())
    vres = validator.validate(attempt.schema_name, attempt.schema_version, result.payload)
    if vres.outcome is not ValidationOutcome.VALID:
        # A validation failure is NOT a business success. Do not write `succeeded`.
        store.mark_pending_reconciliation(job.job_id)
        if ack_mode is AckMode.LATE:
            broker.ack(delivery.delivery_id)
        return WorkerResult(WorkerOutcome.VALIDATION_REFUSED, True, provider.calls,
                            store.get(job.job_id).status)

    # (g) FINAL pre-completion cooperative cancellation re-check (Day54): a durable intent written
    # after the last token but before completion still prevents `succeeded`.
    if cancel_before_completion:
        store.persist_cancellation_intent(job.job_id, kind=IntentKind.USER_CANCELLATION,
                                          reason="late user cancel", actor="user", now=now)
    intent = store.open_intent(job.job_id)
    if intent is not None:
        store.guarded_terminal_transition(job.job_id, terminal_for_intent(intent.kind), now=now)
        if ack_mode is AckMode.LATE:
            broker.ack(delivery.delivery_id)
        return WorkerResult(WorkerOutcome.CANCELLED_PRE_COMPLETION, True, provider.calls,
                            store.get(job.job_id).status)

    # (h) Guarded completion — exactly one winner vs a concurrent cancellation.
    store.guarded_complete_success(job.job_id, artifact=vres.domain_result, actual_tokens=result.usage_tokens,
                                   now=now)
    if ack_mode is AckMode.LATE:
        broker.ack(delivery.delivery_id)
    return WorkerResult(WorkerOutcome.SUCCEEDED, True, provider.calls,
                        store.get(job.job_id).status)


# ===========================================================================
# 8. Cancellation entry point (Router) + optional Celery revoke
# ===========================================================================
def request_cancellation(store: JobStore, job_id: str, *, actor: str, reason: str,
                         now: datetime, kind: IntentKind = IntentKind.USER_CANCELLATION,
                         revoke: Optional[Callable[[str], None]] = None) -> CancellationIntent:
    """Commit the durable cancellation intent FIRST; the optional Celery revoke is best-effort
    delivery/runtime control AFTER the commit, never the business authority.
    """
    intent = store.persist_cancellation_intent(job_id, kind=kind, reason=reason, actor=actor,
                                               now=now)
    if revoke is not None:
        revoke(job_id)      # best-effort; may fail or race — the durable intent still governs
    return intent


# ===========================================================================
# 9. Graceful drain (deploy/rollout) — never a business cancellation
# ===========================================================================
class WorkerPool:
    def __init__(self) -> None:
        self.accepting = True

    def stop_new_claims(self) -> None:
        self.accepting = False


@dataclass
class DrainReport:
    new_workers_started: bool
    old_workers_stopped_new_claims: bool
    inflight_drained: int
    inflight_abandoned: int
    checkpointed: bool


def graceful_drain(pool: WorkerPool, *, inflight: int, drain_bound: int) -> DrainReport:
    """Start verified new Workers, stop old Workers from taking NEW claims, drain in-flight work
    within a bound, checkpoint durably, then ACK and exit. Force-killing Workers is NEVER normal
    business cancellation.
    """
    pool.stop_new_claims()
    drained = min(inflight, drain_bound)
    abandoned = max(0, inflight - drain_bound)     # these redeliver (at-least-once), not lost
    return DrainReport(new_workers_started=True, old_workers_stopped_new_claims=True,
                       inflight_drained=drained, inflight_abandoned=abandoned, checkpointed=True)


# ===========================================================================
# 10. Erroneous early-ACK release incident — evidence-based repair
# ===========================================================================
class ReleaseConfig:
    """Models a bad rollout (e.g. early-ACK) that can silently lose deliveries."""
    def __init__(self, version: str, early_ack: bool) -> None:
        self.version = version
        self.early_ack = early_ack

    def rollback(self) -> None:
        # Stops FUTURE harm only. It does NOT repair Jobs already committed `running` under the bad
        # release. Configuration rollback != business-fact rollback.
        self.early_ack = False


def build_affected_set(store: JobStore, *, release_version: str, window_start: datetime,
                       window_end: datetime) -> list[str]:
    """Build the affected set from release version + a bounded time window + Worker/Attempt/Event
    evidence. Do NOT bulk-flip `running` Jobs to `queued`.
    """
    affected = []
    for job in store._jobs.values():
        if job.release_version == release_version and job.status == JobStatus.RUNNING:
            affected.append(job.job_id)
    return affected


class RepairAction(str, Enum):
    RECONCILE_THEN_GUARDED_REDISPATCH = "reconcile_then_guarded_redispatch"
    RECONCILE_ONLY = "reconcile_only"       # possible Provider execution: never blind re-dispatch


def classify_repair(store: JobStore, job_id: str) -> RepairAction:
    """A Job whose Attempt has a provider_request_id may have executed at the Provider: reconcile,
    never blind re-dispatch. Only Jobs with NO Provider-execution evidence are safe to re-dispatch
    under an explicit, guarded, audited action.
    """
    job = store.get(job_id)
    att = store._attempts.get(job.open_attempt_id) if job.open_attempt_id else None
    if att is not None and att.provider_request_id is not None:
        return RepairAction.RECONCILE_ONLY
    return RepairAction.RECONCILE_THEN_GUARDED_REDISPATCH
