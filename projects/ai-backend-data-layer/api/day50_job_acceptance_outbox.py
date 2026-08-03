"""Day50 — idempotent AI Job acceptance + transactional Outbox dispatch intent.

IMPORTANT EVIDENCE LABEL (three distinct claims — do not conflate them):
  * CONCEPTUAL ARTIFACT: the acceptance-idempotency, atomic Job+Outbox UoW, Outbox
    Relay / TransportAdapter, at-least-once redelivery, relay lease/fencing, and
    worker guarded-claim semantics described here and in the design doc.
  * STATIC / FAKE-ADAPTER VERIFICATION: what the pytest suite actually executes — the
    APPLICATION CONTROL FLOW against an IN-MEMORY store that MODELS guarded
    compare-and-set transitions and a FAKE/in-memory TransportAdapter. Determinism is
    demonstrated by deterministic tests (a mock clock; a transport double that fails,
    times out, or crashes after publish). This is control-flow evidence.
  * REAL RUNTIME VERIFICATION: NOT RUN here — no real PostgreSQL (UNIQUE/constraints/
    transaction atomicity/isolation, `INSERT ... ON CONFLICT`, `FOR UPDATE SKIP
    LOCKED`), no real broker/Celery (ACK/redelivery/poison tasks), no real Worker, no
    real Provider, no integration, no production. A fake adapter proves control flow,
    not broker/DB semantics.

No real credentials, broker URLs, signed URLs, or secrets appear anywhere.

Boundary reused from earlier lessons (NOT re-implemented here):
  * Day47 short Unit of Work + guarded state transition (modeled in-memory).
  * Day33 Job + Outbox atomicity; Day34 `FOR UPDATE SKIP LOCKED`/short-claim + lease
    reasoning; Day41 fencing-token reasoning; Day49 reconciliation of unknown external
    outcomes and its verified, tenant-owned Documents (the only accepted Job inputs).
  * Day31/Day46 schema: `app.jobs` already has `idempotency_key` +
    `UNIQUE(tenant_id, idempotency_key)`; `app.outbox_events` has
    `event_type`/`payload`/`published_at`. This module MODELS those and additional
    control-flow fields in memory; it does not redefine or migrate the schema.

SCHEMA-HONESTY: the published schema HAS `UNIQUE(tenant_id, idempotency_key)` (the real
concurrent arbiter for acceptance), but does NOT yet have: a request-fingerprint column
on `jobs`, a `UNIQUE(job_id, event_type)` at-most-one-dispatch-intent constraint on
`outbox_events`, or Outbox Relay operational columns (attempt_count, last_error,
next_attempt_at, dispatch/quarantine state, relay owner/lease/fencing token). Those are
MODELED in-memory here. In the REAL schema they require a Day48-safe FORWARD additive
migration (new nullable columns + a partial/logical unique index via a branch revision);
that migration is NOT implemented here and no published Alembic revision is rewritten.
This module makes NO real PostgreSQL/broker/Worker/Provider runtime claim.

Boundaries deliberately NOT crossed: no exactly-once across PostgreSQL + broker + Worker
+ Provider; the API UoW never calls the transport inside its DB transaction; no DB lock
is held across transport I/O; Day55 owns the real Celery broker/ACK/redelivery/poison
semantics and Day53 owns the real Provider.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional, Protocol

DISPATCH_EVENT_TYPE = "job.dispatch_requested"


# ---------------------------------------------------------------------------
# Request fingerprint — evidence the idempotency key is not reused for another command
# ---------------------------------------------------------------------------
def compute_request_fingerprint(request: dict, *, unordered_documents: bool = False) -> str:
    """Canonical fingerprint over ALL behavior-changing fields of a logical command
    (verified Document/Artifact references, prompt/instruction, model/execution
    profile, output contract, token/quality options, API version). Document ordering
    is canonicalized ONLY when the product contract makes documents a set
    (``unordered_documents=True``); otherwise order is preserved because it can change
    model semantics. The idempotency key itself is NOT fingerprint material."""
    normalized = dict(request)
    docs = normalized.get("documents")
    if unordered_documents and isinstance(docs, list):
        normalized["documents"] = sorted(docs)
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verified-Document directory (Day49 boundary) — the only accepted Job inputs
# ---------------------------------------------------------------------------
class DocumentDirectory(Protocol):
    def is_verified_and_owned(self, tenant_id: uuid.UUID, document_id: str) -> bool: ...


class InMemoryDocumentDirectory:
    """Models Day49's outcome: a Document is an accepted input only if it is VERIFIED
    and owned by the requesting tenant. Document ids are opaque string references (as
    they arrive in the JSON request). NOT a real DB/FK check."""

    def __init__(self) -> None:
        self._verified: set[tuple[uuid.UUID, str]] = set()

    def add_verified(self, tenant_id: uuid.UUID, document_id: str) -> None:
        self._verified.add((tenant_id, str(document_id)))

    def is_verified_and_owned(self, tenant_id: uuid.UUID, document_id: str) -> bool:
        return (tenant_id, str(document_id)) in self._verified


# ---------------------------------------------------------------------------
# Rows + envelope
# ---------------------------------------------------------------------------
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutboxState(str, Enum):
    UNPUBLISHED = "unpublished"  # durable obligation to attempt dispatch
    PUBLISHED = "published"  # Relay publication checkpoint recorded (NOT job success)
    QUARANTINED = "quarantined"  # exhausted/permanent failure -> operational recovery


@dataclass
class JobRow:
    job_id: uuid.UUID
    tenant_id: uuid.UUID
    idempotency_key: str
    request_fingerprint: str
    job_status: JobStatus
    document_ids: tuple[str, ...]
    created_at: datetime


@dataclass
class OutboxRow:
    outbox_event_id: uuid.UUID
    job_id: uuid.UUID
    event_type: str
    payload: dict
    created_at: datetime
    published_at: Optional[datetime] = None
    state: OutboxState = OutboxState.UNPUBLISHED
    attempt_count: int = 0
    last_error: Optional[str] = None
    next_attempt_at: Optional[datetime] = None
    relay_owner: Optional[str] = None  # fencing token of the current Relay claimant
    relay_hold_until: Optional[datetime] = None


@dataclass(frozen=True)
class Envelope:
    """Small, stable message. Queue is NOT Job truth; the Worker re-reads the Job by
    ``job_id``. Never copy prompt, sensitive content, or mutable Document details."""

    outbox_event_id: uuid.UUID
    event_type: str
    job_id: uuid.UUID
    correlation_id: str


def build_envelope(row: OutboxRow) -> Envelope:
    return Envelope(
        outbox_event_id=row.outbox_event_id,
        event_type=row.event_type,
        job_id=row.job_id,
        correlation_id=f"corr-{row.outbox_event_id}",
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class DispatchIntentExists(Exception):
    """Models a logical UNIQUE(job_id, event_type='job.dispatch_requested')."""


class SimulatedCommitFailure(Exception):
    """Injected to prove the acceptance UoW is all-or-nothing in the model."""


class FencingError(Exception):
    """A stale Relay (lease superseded) tried to write a checkpoint."""


class TransportError(Exception):
    """A (transient) transport failure. Never carries a secret/URL in its message."""


class TransportCrashAfterPublish(Exception):
    """Models a Relay crash AFTER a successful publish but BEFORE the checkpoint."""


# ---------------------------------------------------------------------------
# Transport adapter seam (NO real broker)
# ---------------------------------------------------------------------------
class TransportAdapter(Protocol):
    def publish(self, envelope: Envelope) -> None: ...


class InMemoryTransport:
    """Deterministic fake transport. Records published envelopes (duplicates allowed,
    modeling at-least-once). NOT a real broker; no network, no ACK semantics."""

    def __init__(self) -> None:
        self.published: list[Envelope] = []

    def publish(self, envelope: Envelope) -> None:
        self.published.append(envelope)


class FailingTransport:
    """Raises a transient TransportError on publish (models a temporary outage)."""

    def __init__(self, message: str = "transient transport failure") -> None:
        self.message = message

    def publish(self, envelope: Envelope) -> None:
        raise TransportError(self.message)


class CrashAfterPublishTransport:
    """Publishes to a real sink, then raises to model a crash before the checkpoint."""

    def __init__(self, sink: InMemoryTransport) -> None:
        self.sink = sink

    def publish(self, envelope: Envelope) -> None:
        self.sink.publish(envelope)  # the message DID go out (at-least-once)
        raise TransportCrashAfterPublish("crash before published_at checkpoint")


def _redact(exc: Exception) -> str:
    """Store a safe error category, never a secret/URL/broker string."""
    return f"{type(exc).__name__}: transport error (redacted)"


def _require_live_lease(row: "OutboxRow", *, owner_token: str, now: datetime) -> None:
    """Fencing guard: the caller must still own the relay lease AND the lease must not
    have expired. Either a superseded owner or an expired hold is rejected so a stale
    Relay can never write `published_at` or retry state after its lease lapsed."""
    if row.relay_owner != owner_token:
        raise FencingError(f"stale relay {owner_token!r} != owner {row.relay_owner!r}")
    if row.relay_hold_until is None or now >= row.relay_hold_until:
        raise FencingError(f"relay lease for {owner_token!r} has expired")


# ---------------------------------------------------------------------------
# In-memory store — models UNIQUE(tenant,key), atomic Job+Outbox, guarded CAS
# ---------------------------------------------------------------------------
class InMemoryJobStore:
    """Models the durable Job/Outbox facts + guarded transitions. A real
    implementation is a PostgreSQL short transaction with UNIQUE constraints,
    `INSERT ... ON CONFLICT ... RETURNING`, and `FOR UPDATE SKIP LOCKED` (Day47/34).
    This is control flow only."""

    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, JobRow] = {}
        # UNIQUE(tenant_id, idempotency_key) -> job_id
        self._by_idem: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
        self.outbox: dict[uuid.UUID, OutboxRow] = {}
        # logical UNIQUE(job_id, event_type)
        self._dispatch_intents: set[tuple[uuid.UUID, str]] = set()
        # Serializes the acceptance conflict-arbitration + create so a concurrent
        # request cannot double-create. Models the atomic serialization PostgreSQL
        # gives via the UNIQUE index / INSERT ... ON CONFLICT (this is control flow,
        # not real DB isolation).
        self._accept_lock = threading.Lock()

    def find_by_idempotency(self, tenant_id: uuid.UUID, key: str) -> Optional[JobRow]:
        jid = self._by_idem.get((tenant_id, key))
        return self.jobs.get(jid) if jid is not None else None

    def upsert_job_on_conflict(
        self,
        *,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        request_fingerprint: str,
        document_ids: tuple[str, ...],
        now: datetime,
        fail_before_commit: bool = False,
    ) -> tuple[JobRow, Optional[OutboxRow], bool]:
        """ATOMIC acceptance arbiter — models `INSERT ... ON CONFLICT (tenant_id,
        idempotency_key) DO NOTHING RETURNING`. The conflict decision AND the create
        happen INSIDE a single critical section (``self._accept_lock``), so two
        concurrent requests that both read absence cannot both create: the first wins
        and creates the Job + exactly one `job.dispatch_requested` Outbox intent
        together (all-or-nothing; a failure before the commit block leaves NEITHER);
        the second observes the conflict and RETURNS the existing Job WITHOUT creating
        anything. Returns ``(job, outbox_or_existing_intent, created)``. Models the
        atomic serialization PostgreSQL gives via the UNIQUE index — it is control
        flow, NOT proof of real PostgreSQL isolation/transaction behavior."""
        with self._accept_lock:
            existing_id = self._by_idem.get((tenant_id, idempotency_key))
            if existing_id is not None:
                # ON CONFLICT: do not create; return the already-committed winner.
                return self.jobs[existing_id], self._dispatch_intent_for(existing_id), False
            job_id = uuid.uuid4()
            job = JobRow(
                job_id=job_id, tenant_id=tenant_id, idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint, job_status=JobStatus.QUEUED,
                document_ids=document_ids, created_at=now,
            )
            outbox = OutboxRow(
                outbox_event_id=uuid.uuid4(), job_id=job_id, event_type=DISPATCH_EVENT_TYPE,
                payload={"job_id": str(job_id)}, created_at=now, next_attempt_at=now,
            )
            if fail_before_commit:
                raise SimulatedCommitFailure("injected failure before commit")
            # --- single logical commit: both facts together ---
            self.jobs[job_id] = job
            self._by_idem[(tenant_id, idempotency_key)] = job_id
            self.outbox[outbox.outbox_event_id] = outbox
            self._dispatch_intents.add((job_id, DISPATCH_EVENT_TYPE))
            return job, outbox, True

    def _dispatch_intent_for(self, job_id: uuid.UUID) -> Optional[OutboxRow]:
        for row in self.outbox.values():
            if row.job_id == job_id and row.event_type == DISPATCH_EVENT_TYPE:
                return row
        return None

    def add_dispatch_intent(self, job_id: uuid.UUID, now: datetime) -> OutboxRow:
        """Guarded: at most one dispatch intent per Job (UNIQUE(job_id, event_type))."""
        if (job_id, DISPATCH_EVENT_TYPE) in self._dispatch_intents:
            raise DispatchIntentExists(str(job_id))
        outbox = OutboxRow(
            outbox_event_id=uuid.uuid4(), job_id=job_id, event_type=DISPATCH_EVENT_TYPE,
            payload={"job_id": str(job_id)}, created_at=now, next_attempt_at=now,
        )
        self.outbox[outbox.outbox_event_id] = outbox
        self._dispatch_intents.add((job_id, DISPATCH_EVENT_TYPE))
        return outbox

    # -- Relay short claim (models FOR UPDATE SKIP LOCKED + lease/owner) --
    def claim_outbox_batch(
        self, *, owner_token: str, now: datetime, hold_ttl: timedelta, batch_size: int = 10
    ) -> list[uuid.UUID]:
        """Short claim tx: select DUE unpublished intents not held by a live lease, set
        owner+hold, and RETURN their ids. Models `FOR UPDATE SKIP LOCKED`: a row with a
        live lease owned by someone else is skipped. NO transport I/O happens here."""
        claimed: list[uuid.UUID] = []
        for row in self.outbox.values():
            if row.state is not OutboxState.UNPUBLISHED:
                continue
            if row.next_attempt_at is not None and now < row.next_attempt_at:
                continue
            if (
                row.relay_owner is not None
                and row.relay_owner != owner_token
                and row.relay_hold_until is not None
                and now < row.relay_hold_until
            ):
                continue  # SKIP LOCKED: another live claimant owns it
            row.relay_owner = owner_token
            row.relay_hold_until = now + hold_ttl
            claimed.append(row.outbox_event_id)
            if len(claimed) >= batch_size:
                break
        return claimed

    def checkpoint_published_if_owner(
        self, outbox_event_id: uuid.UUID, *, owner_token: str, now: datetime
    ) -> None:
        """Guarded (fenced) checkpoint: record `published_at` ONLY if we still own the
        lease AND the lease has not expired. A stale Relay whose lease was superseded
        OR merely EXPIRED (even before a new owner takes over) raises FencingError and
        cannot write `published_at`."""
        row = self.outbox[outbox_event_id]
        if row.state is OutboxState.PUBLISHED:
            return  # idempotent
        _require_live_lease(row, owner_token=owner_token, now=now)
        row.published_at = now
        row.state = OutboxState.PUBLISHED
        row.relay_owner = None
        row.relay_hold_until = None

    def record_transport_failure(
        self, outbox_event_id: uuid.UUID, *, owner_token: str, exc: Exception,
        next_attempt_at: datetime, max_attempts: int, now: datetime,
    ) -> OutboxState:
        """Guarded failure retention: keep the intent, increment attempt_count, store a
        REDACTED error, set the next retry time, and release the lease so a due retry
        can re-claim. Requires a LIVE lease (owner match AND not expired) — a stale or
        expired Relay cannot record failure/retry state. Exhausting the policy
        quarantines (retains) the intent; it does NOT delete it and does NOT mark the
        Job failed."""
        row = self.outbox[outbox_event_id]
        _require_live_lease(row, owner_token=owner_token, now=now)
        row.attempt_count += 1
        row.last_error = _redact(exc)
        row.next_attempt_at = next_attempt_at
        row.relay_owner = None
        row.relay_hold_until = None
        if row.attempt_count >= max_attempts:
            row.state = OutboxState.QUARANTINED
        return row.state

    # -- Worker guarded claim (models UPDATE ... WHERE job_status='queued' RETURNING) --
    def worker_claim(self, job_id: uuid.UUID) -> bool:
        """Guarded transition queued -> running. Returns True for the single winner
        (one 'row'); duplicate deliveries get False (zero rows) and MUST NOT call the
        Provider."""
        job = self.jobs[job_id]
        if job.job_status is not JobStatus.QUEUED:
            return False
        job.job_status = JobStatus.RUNNING
        return True


# ---------------------------------------------------------------------------
# Acceptance (POST /jobs) — client Idempotency-Key + fingerprint
# ---------------------------------------------------------------------------
class AcceptOutcome(str, Enum):
    CREATED = "created"  # winner: new Job + one dispatch intent
    RETURNED_EXISTING = "returned_existing"  # same key + same fingerprint -> original Job
    CONFLICT = "conflict"  # same key + changed semantics -> 409, no writes
    MISSING_IDEMPOTENCY_KEY = "missing_idempotency_key"  # rejected before any DB write
    DOCUMENT_NOT_VERIFIED = "document_not_verified"  # unverified/cross-tenant input -> reject


@dataclass
class AcceptResult:
    outcome: AcceptOutcome
    job: Optional[JobRow] = None
    outbox: Optional[OutboxRow] = None
    reason: str = ""


def accept_job(
    store: InMemoryJobStore,
    documents: DocumentDirectory,
    *,
    tenant_id: uuid.UUID,
    idempotency_key: Optional[str],
    request: dict,
    now: datetime,
    unordered_documents: bool = False,
    fail_commit: bool = False,
    _after_read_hook: Optional[Callable[[], None]] = None,
) -> AcceptResult:
    """Idempotent acceptance. ORDER matters (review round 1, P1-3):
      1. reject a missing/blank Idempotency-Key BEFORE any DB write;
      2. compute the request fingerprint (the key is NOT fingerprint material);
      3. if a Job already exists for (tenant_id, idempotency_key):
           - same fingerprint -> RETURNED_EXISTING (the original Job) WITHOUT re-running
             the mutable Document admission check (an exact retry must return the
             original Job even if a Document later became unavailable);
           - different fingerprint -> CONFLICT (409; no new durable facts);
      4. only for a NEW command: validate every referenced Document is verified +
         tenant-owned (`DOCUMENT_NOT_VERIFIED` otherwise);
      5. atomic arbiter `upsert_job_on_conflict` (models `INSERT ... ON CONFLICT`): the
         winner creates Job + one dispatch intent (CREATED); a concurrent loser that
         inserted after our step-3 read is arbitrated INSIDE the atomic op and comes
         back as the existing Job -> compare its fingerprint (same -> RETURNED_EXISTING,
         different -> CONFLICT).
    The transport is never called here (that is the Relay, after commit).

    ``_after_read_hook`` is a TEST-ONLY seam to force an interleaving between the
    step-3 existence read and the step-5 atomic arbiter; production callers never pass
    it."""
    if not idempotency_key or not idempotency_key.strip():
        return AcceptResult(AcceptOutcome.MISSING_IDEMPOTENCY_KEY, reason="client must supply a key")

    fingerprint = compute_request_fingerprint(request, unordered_documents=unordered_documents)

    # Idempotent fast path: an existing Job for this key short-circuits BEFORE the
    # mutable Document admission check, so an exact retry is not broken by later
    # Document state changes.
    existing = store.find_by_idempotency(tenant_id, idempotency_key)
    if _after_read_hook is not None:  # test seam: force concurrent interleaving here
        _after_read_hook()
    if existing is not None:
        return _existing_result(store, existing, fingerprint)

    # New command only: validate the referenced Documents are verified + tenant-owned.
    document_ids = tuple(request.get("documents", ()))
    for doc_id in document_ids:
        if not documents.is_verified_and_owned(tenant_id, doc_id):
            return AcceptResult(
                AcceptOutcome.DOCUMENT_NOT_VERIFIED, reason=f"document {doc_id} not verified/owned"
            )

    # Atomic arbiter: create or observe a concurrent winner.
    job, outbox_or_intent, created = store.upsert_job_on_conflict(
        tenant_id=tenant_id, idempotency_key=idempotency_key, request_fingerprint=fingerprint,
        document_ids=document_ids, now=now, fail_before_commit=fail_commit,
    )
    if created:
        return AcceptResult(AcceptOutcome.CREATED, job=job, outbox=outbox_or_intent)
    # We lost a concurrent race: a winner inserted between our read and the arbiter.
    return _existing_result(store, job, fingerprint)


def _existing_result(store: InMemoryJobStore, existing: JobRow, fingerprint: str) -> AcceptResult:
    if existing.request_fingerprint == fingerprint:
        return AcceptResult(
            AcceptOutcome.RETURNED_EXISTING, job=existing,
            outbox=store._dispatch_intent_for(existing.job_id),
        )
    return AcceptResult(
        AcceptOutcome.CONFLICT, job=None, reason="idempotency key reused for a different command"
    )


# ---------------------------------------------------------------------------
# Outbox Relay — at-least-once; no lock over transport I/O; fenced checkpoint
# ---------------------------------------------------------------------------
def compute_next_attempt(
    attempt_count: int,
    *,
    now: datetime,
    base_seconds: float = 1.0,
    cap_seconds: float = 300.0,
    jitter: Callable[[float], float] = lambda ceiling: 0.0,
) -> datetime:
    """Bounded exponential backoff with jitter. ``attempt_count`` is the number of
    failures so far (>=1). The delay is min(base * 2**(attempt-1), cap) plus a jitter in
    [0, delay). ``jitter`` is injectable so tests are deterministic."""
    exp = base_seconds * (2 ** max(0, attempt_count - 1))
    delay = min(exp, cap_seconds)
    return now + timedelta(seconds=delay + jitter(delay))


@dataclass
class RelayReport:
    published: int = 0
    failed: int = 0
    quarantined: int = 0
    crashed_before_checkpoint: int = 0


def run_relay_once(
    store: InMemoryJobStore,
    transport: TransportAdapter,
    *,
    owner_token: str,
    now: datetime,
    hold_ttl: timedelta = timedelta(minutes=1),
    batch_size: int = 10,
    max_attempts: int = 5,
    base_seconds: float = 1.0,
    cap_seconds: float = 300.0,
    jitter: Callable[[float], float] = lambda ceiling: 0.0,
) -> RelayReport:
    """One Relay pass: claim DUE unpublished intents (short tx, lease-owned), then
    publish OUTSIDE any DB lock, then a fenced checkpoint. A crash after publish but
    before the checkpoint leaves ``published_at IS NULL`` -> at-least-once redelivery on
    a later pass (duplicates are acceptable; an accepted Job is never lost). A transient
    failure retains the intent with attempt/error/next_attempt; exhaustion quarantines."""
    report = RelayReport()
    claimed = store.claim_outbox_batch(
        owner_token=owner_token, now=now, hold_ttl=hold_ttl, batch_size=batch_size
    )
    for outbox_event_id in claimed:
        row = store.outbox[outbox_event_id]
        envelope = build_envelope(row)
        try:
            transport.publish(envelope)  # OUTSIDE the DB tx / no lock held
        except TransportCrashAfterPublish:
            # The message went out but we crashed before the checkpoint: leave
            # published_at NULL and the lease to expire -> a later pass republishes.
            report.crashed_before_checkpoint += 1
            continue
        except TransportError as exc:
            state = store.record_transport_failure(
                outbox_event_id, owner_token=owner_token, exc=exc,
                next_attempt_at=compute_next_attempt(
                    row.attempt_count + 1, now=now, base_seconds=base_seconds,
                    cap_seconds=cap_seconds, jitter=jitter,
                ),
                max_attempts=max_attempts, now=now,
            )
            report.failed += 1
            if state is OutboxState.QUARANTINED:
                report.quarantined += 1
            continue
        store.checkpoint_published_if_owner(outbox_event_id, owner_token=owner_token, now=now)
        report.published += 1
    return report
