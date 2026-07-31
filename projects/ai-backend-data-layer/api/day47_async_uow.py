"""Day47 — Async Sessions, Transactions, Repository and Unit of Work.

Drives the FAITHFUL Day46 SQLAlchemy mapping through SHORT, isolated async
database units of work — WITHOUT treating a long external AI-Provider call as
transactional database work. PostgreSQL stays the durable authority; Day46 maps
it, Day47 drives it transactionally, Day48 evolves it.

Scope and honesty:
    * Process-scoped AsyncEngine + async_sessionmaker construction helpers; a
      fresh request/Job-scoped AsyncSession per Unit of Work.
    * Repositories receive the UoW-injected Session and express DB operations;
      they NEVER create Engines/Sessions and NEVER commit or close.
    * The UoW owns one Session, exposes repositories, controls EXPLICIT commit,
      rolls back on exception / uncommitted exit, and ALWAYS closes the Session.
    * Guarded claim = one ``UPDATE ... WHERE job_id=... AND tenant_id=... AND
      job_status='queued' RETURNING ...`` (not SELECT-then-UPDATE). One row =
      claimed; zero rows (including a wrong tenant) = a NORMAL stale/no-op miss
      (no Attempt/Event, not a retryable DB error). Every guarded ``app.jobs``
      mutation (claim/complete/fail) carries ``tenant_id`` as a REQUIRED durable
      ownership predicate (Day42/Day46) — trusted context passed from the
      orchestration, NEVER derived from the job_id (a job_id is not an
      authorization boundary). This is the existing durable tenant predicate, not
      Day52 authentication/authorization.
    * A long/paid Provider call happens OUTSIDE any open DB transaction. Before it,
      the start UoW commits a durable Attempt plus an application-generated
      correlation/idempotency key written into the ``job_started`` Event metadata
      (Day46 defines no correlation column on JobAttempt, and Day47 invents none).
    * Completion is a SECOND short guarded UoW that persists the Day33 atomic
      completion pack in ONE commit: guarded finish Attempt (recording the
      available Provider evidence finished_at + provider_request_id + cost_micros
      in the same ``finished_at IS NULL`` guarded statement) -> guarded
      tenant-scoped running -> succeeded Job -> ResultArtifact reference (Object
      Storage key, never bytes) -> job_succeeded Event. provider_request_id /
      cost_micros may be None when unknown (written as NULL; a None does NOT
      assert a verified value). Any zero-row guard or any failed step rolls the
      WHOLE UoW back (no partial durable state).
    * This module is imported without opening any connection. NO global
      AsyncSession. NO repository-owned commit. It reuses the Day46 ORM models
      (``day46_orm_mapping``); it does NOT redefine Day42 schema authority, use
      ``create_all()`` as compatibility proof, change TEXT+CHECK to enum, or add a
      destructive cascade.
    * Provider I/O and unknown-outcome are modeled as a small fake seam only. The
      complete Day50 idempotent acceptance/Outbox workflow and the Day49 upload
      workflow are NOT implemented here.
    * Runtime evidence: the tests use a FAKE AsyncSession to verify UoW control
      flow. A real PostgreSQL rollback/transaction runtime test is NOT RUN (no
      server/driver available); SQLite is not PostgreSQL evidence for this
      app-schema/PostgreSQL-typed contract.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Reuse the Day46 mapping as the persistence model (no schema redefinition).
from day46_orm_mapping import Job, JobAttempt, JobEvent, ResultArtifact


# ---------------------------------------------------------------------------
# Process-scoped construction helpers (one Engine per PROCESS, via a lifespan /
# Worker composition root — NOT one Engine per deployment, NOT a global Session).
# ---------------------------------------------------------------------------
def create_engine(database_url: str, **kwargs: Any) -> AsyncEngine:
    """Create the process-owned AsyncEngine + connection pool. Call once in the
    API lifespan or Worker startup composition root; dispose it on shutdown.
    Importing this module opens no connection. Use a real async driver URL such
    as ``postgresql+asyncpg://.../app`` (never commit real credentials)."""
    return create_async_engine(database_url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the process-scoped session factory. It creates a NEW AsyncSession on
    demand (one per request/Job UoW) — it is not a shared batch of live Sessions.
    expire_on_commit=False lets us read already-loaded, allowlisted fields after
    commit while building a DTO, without a lazy post-close reload."""
    return async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Guarded outcomes (a zero-row claim/completion is a NORMAL stale/no-op result,
# NOT a database error and NOT a retryable failure).
# ---------------------------------------------------------------------------
class ClaimOutcome(str, Enum):
    CLAIMED = "claimed"
    STALE_NOOP = "stale_noop"


class CompletionOutcome(str, Enum):
    COMPLETED = "completed"
    STALE_NOOP = "stale_noop"


# ---------------------------------------------------------------------------
# Repositories — share the UoW-injected Session; NO commit, NO close, NO Engine.
# ---------------------------------------------------------------------------
class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guarded_claim(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Single guarded transition: UPDATE ... WHERE job_status='queued' AND
        tenant_id=... RETURNING job_id. Returns the number of rows claimed (1 =
        this Worker won; 0 = stale/no-op). NOT SELECT-then-UPDATE, so two Workers
        cannot both claim the same queued Job. tenant_id is a REQUIRED durable
        ownership predicate (Day42/Day46): it is trusted context passed in from
        the orchestration, NOT derived from the job_id — a job_id alone is not an
        authorization boundary. A wrong tenant matches 0 rows and claims nothing."""
        result = await self._session.execute(
            text(
                "UPDATE app.jobs SET job_status = 'running', started_at = now() "
                "WHERE job_id = :job_id AND tenant_id = :tenant_id "
                "AND job_status = 'queued' "
                "RETURNING job_id"
            ),
            {"job_id": job_id, "tenant_id": tenant_id},
        )
        return len(result.fetchall())

    async def guarded_complete(
        self, job_id: uuid.UUID, tenant_id: uuid.UUID, *, finished_at: Optional[datetime] = None
    ) -> int:
        """Guarded terminal transition: only a still-'running' Job OWNED BY THIS
        tenant records success. Returns rows affected (1 = completed; 0 = stale/
        no-op — do NOT overwrite or duplicate terminal facts). The Day46
        jobs_succeeded_has_finished_at CHECK is a STATE invariant; this row guard
        is CONCURRENCY + OWNERSHIP control. tenant_id is a REQUIRED durable
        ownership predicate (trusted context, not derived from job_id); a wrong
        tenant matches 0 rows so NO Artifact/Event is written."""
        result = await self._session.execute(
            text(
                "UPDATE app.jobs SET job_status = 'succeeded', finished_at = :fa "
                "WHERE job_id = :job_id AND tenant_id = :tenant_id "
                "AND job_status = 'running' "
                "RETURNING job_id"
            ),
            {"job_id": job_id, "tenant_id": tenant_id, "fa": finished_at or datetime.now(timezone.utc)},
        )
        return len(result.fetchall())

    async def mark_failed(self, job_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        """Definitive, non-retryable Provider failure -> failed (guarded on
        'running' AND tenant_id). A timeout with UNKNOWN remote outcome must NOT
        use this; it stays unknown/recoverable. tenant_id is a REQUIRED durable
        ownership predicate (trusted context, not derived from job_id)."""
        result = await self._session.execute(
            text(
                "UPDATE app.jobs SET job_status = 'failed', finished_at = now() "
                "WHERE job_id = :job_id AND tenant_id = :tenant_id "
                "AND job_status = 'running' "
                "RETURNING job_id"
            ),
            {"job_id": job_id, "tenant_id": tenant_id},
        )
        return len(result.fetchall())


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job_id: uuid.UUID, attempt_number: int) -> JobAttempt:
        """Create an Attempt. Day46 defines NO correlation-key column on
        JobAttempt, so this repository does NOT accept or persist one — the
        application-generated correlation/idempotency key is written by the
        higher-level start flow into the ``job_started`` Event metadata, in the
        same UoW (see ``start_job``). The Provider's own request ID is persisted
        later, when available."""
        attempt = JobAttempt(
            job_id=job_id,
            attempt_number=attempt_number,
            provider_request_id=None,
            error_code=None,
        )
        self._session.add(attempt)
        # flush so the server-generated attempt_id is available for a dependent
        # Event write WITHOUT committing the transaction.
        await self._session.flush()
        return attempt

    async def finish(
        self,
        job_id: uuid.UUID,
        attempt_id: uuid.UUID,
        *,
        provider_request_id: Optional[str] = None,
        cost_micros: Optional[int] = None,
    ) -> int:
        """Guarded Attempt completion (Day33 completion pack, step 1). In ONE
        guarded statement it records the available Provider evidence —
        ``finished_at``, ``provider_request_id`` and ``cost_micros`` — while
        guarding on job_id, attempt_id AND ``finished_at IS NULL``, so an
        ALREADY-finished Attempt's recorded outcome is never overwritten. Returns
        rows affected: 1 = finished now; 0 = the Attempt does not exist, does not
        belong to this Job, or is already finished -> the caller must ROLL BACK and
        STOP (stale/no-op). ``provider_request_id`` / ``cost_micros`` may be None
        when not yet known (they are written as NULL); a None does NOT assert a
        verified value."""
        result = await self._session.execute(
            text(
                "UPDATE app.job_attempts "
                "SET finished_at = now(), "
                "    provider_request_id = :provider_request_id, "
                "    cost_micros = :cost_micros "
                "WHERE attempt_id = :attempt_id AND job_id = :job_id "
                "AND finished_at IS NULL "
                "RETURNING attempt_id"
            ),
            {
                "attempt_id": attempt_id,
                "job_id": job_id,
                "provider_request_id": provider_request_id,
                "cost_micros": cost_micros,
            },
        )
        return len(result.fetchall())


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        job_id: uuid.UUID,
        event_type: str,
        *,
        attempt_id: Optional[uuid.UUID] = None,
        metadata: Optional[dict] = None,
    ) -> JobEvent:
        event = JobEvent(
            job_id=job_id,
            attempt_id=attempt_id,
            event_type=event_type,
            event_metadata=metadata or {},
        )
        self._session.add(event)
        return event


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        attempt_id: uuid.UUID,
        *,
        object_key: str,
        artifact_type: str = "result",
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        checksum: Optional[str] = None,
    ) -> ResultArtifact:
        """Persist a Day46 ResultArtifact durable REFERENCE (Object Storage
        object_key + metadata) — NEVER the artifact bytes. Ownership is derived
        through the Attempt (Day46: ResultArtifact stores attempt_id only). A
        duplicate (attempt_id, object_key) would raise IntegrityError at flush/
        commit and roll the WHOLE completion UoW back. The external Object Storage
        bytes are NOT part of the DB transaction: a DB rollback does NOT delete
        the external object."""
        artifact = ResultArtifact(
            attempt_id=attempt_id,
            artifact_type=artifact_type,
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum=checksum,
        )
        self._session.add(artifact)
        return artifact


# ---------------------------------------------------------------------------
# Unit of Work — owns ONE Session, exposes repositories, EXPLICIT commit, rolls
# back on exception / uncommitted exit, ALWAYS closes. No auto-commit.
# ---------------------------------------------------------------------------
class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: Optional[AsyncSession] = None
        self._committed = False
        self.jobs: Optional[JobRepository] = None
        self.attempts: Optional[AttemptRepository] = None
        self.events: Optional[EventRepository] = None
        self.artifacts: Optional[ArtifactRepository] = None

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.jobs = JobRepository(self.session)
        self.attempts = AttemptRepository(self.session)
        self.events = EventRepository(self.session)
        self.artifacts = ArtifactRepository(self.session)
        self._committed = False
        return self

    async def commit(self) -> None:
        """EXPLICIT durable decision. Chosen over silent auto-commit so a normal
        branch (e.g. a failed/stale claim) can never accidentally commit work."""
        assert self.session is not None
        await self.session.commit()
        self._committed = True

    async def rollback(self) -> None:
        assert self.session is not None
        await self.session.rollback()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self.session is not None
        try:
            # Roll back on ANY exception OR any exit without an explicit commit.
            # rollback and close are distinct: close does not roll back, and
            # neither disposes the process Engine.
            if exc_type is not None or not self._committed:
                await self.session.rollback()
        finally:
            await self.session.close()


# ---------------------------------------------------------------------------
# Provider seam (fake only in Day47) — a real SDK call is Day53. The point is
# that this call happens OUTSIDE any open DB transaction.
# ---------------------------------------------------------------------------
class ProviderUnknownOutcome(Exception):
    """The remote outcome cannot be proven locally (e.g. a timeout after the call
    began; the Provider may have completed and charged, but the response was
    lost). A first-class RECOVERY state — never fabricate success/failure and
    never blindly re-call."""


class AIProviderSeam(Protocol):
    async def run(self, *, correlation_key: str) -> str:
        """Return an external artifact reference. May raise a definitive failure
        or ``ProviderUnknownOutcome``. NOT called inside a DB transaction."""
        ...


@dataclass
class FakeProvider:
    """Deterministic no-network seam for tests. On success it models the evidence a
    real Provider response would carry (an artifact reference, and optionally a
    provider_request_id and cost_micros) so a test can pass them into the guarded
    completion pack. It performs NO network I/O and is NOT a real Provider SDK."""

    artifact_ref: Optional[str] = None
    provider_request_id: Optional[str] = None
    cost_micros: Optional[int] = None
    raises: Optional[BaseException] = None
    calls: int = 0

    async def run(self, *, correlation_key: str) -> str:
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        assert self.artifact_ref is not None
        return self.artifact_ref


# ---------------------------------------------------------------------------
# Orchestrations — SHORT UoWs around a Provider call that is NOT in a transaction.
# ---------------------------------------------------------------------------
async def start_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID,
    correlation_key: str,
) -> ClaimOutcome:
    """UoW 1: guarded claim (tenant-scoped) -> Attempt (flush) -> job_started Event
    -> commit, committing only if ALL succeed. A zero-row claim (including a wrong
    tenant) is a normal stale/no-op: create NO Attempt/Event and do not commit.
    tenant_id is trusted durable-ownership context, NOT derived from job_id."""
    async with UnitOfWork(session_factory) as uow:
        assert uow.jobs and uow.attempts and uow.events
        claimed = await uow.jobs.guarded_claim(job_id, tenant_id)
        if claimed == 0:
            return ClaimOutcome.STALE_NOOP  # __aexit__ rolls back the empty UoW
        attempt = await uow.attempts.create(job_id, 1)
        await uow.events.append(
            job_id,
            "job_started",
            attempt_id=attempt.attempt_id,
            metadata={"correlation_key": correlation_key},
        )
        await uow.commit()
        return ClaimOutcome.CLAIMED


async def complete_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID,
    attempt_id: uuid.UUID,
    object_key: str,
    artifact_type: str = "result",
    provider_request_id: Optional[str] = None,
    cost_micros: Optional[int] = None,
) -> CompletionOutcome:
    """UoW 2 (a SECOND short guarded UoW, AFTER the Provider call returned): the
    Day33 atomic completion pack in ONE transaction/commit —

        guarded finish Attempt (finished_at IS NULL)
          -> guarded running -> succeeded Job transition
          -> create ResultArtifact durable reference (Object Storage key, not bytes)
          -> append job_succeeded Event
          -> commit

    tenant_id is a REQUIRED durable-ownership predicate on the Job transition
    (trusted context, NOT derived from job_id). provider_request_id / cost_micros
    are the available Provider evidence recorded on the finished Attempt in the
    same statement; either may be None when not yet known (written as NULL — a
    None does NOT assert a verified value).

    Guard order and rollback semantics:
      * Attempt finish returning 0 rows (missing / wrong Job / ALREADY finished)
        -> ROLL BACK and return stale/no-op; never overwrite a finished Attempt.
      * Job transition returning 0 rows (not running OR wrong tenant) -> ROLL BACK;
        write NO ResultArtifact and NO success Event.
      * If the Artifact insert or the Event append fails, the whole UoW rolls back
        (no partial PostgreSQL durable state). The external Artifact bytes are NOT
        part of this transaction; a DB rollback does not delete the external object.
    ``object_key`` is the committed Object Storage reference (verified before this
    UoW); the bytes stay in Object Storage."""
    async with UnitOfWork(session_factory) as uow:
        assert uow.attempts and uow.jobs and uow.artifacts and uow.events
        # 1. Guarded finish of THIS Attempt (job_id + attempt_id + finished_at IS
        #    NULL), recording the available Provider evidence in the same statement.
        finished = await uow.attempts.finish(
            job_id,
            attempt_id,
            provider_request_id=provider_request_id,
            cost_micros=cost_micros,
        )
        if finished == 0:
            # stale/already-finished Attempt -> __aexit__ rolls back the empty UoW.
            return CompletionOutcome.STALE_NOOP
        # 2. Guarded terminal Job transition (only a still-running Job OWNED BY
        #    THIS tenant). A wrong tenant -> 0 rows -> rollback, no Artifact/Event.
        completed = await uow.jobs.guarded_complete(job_id, tenant_id)
        if completed == 0:
            # transition_not_applied -> rollback; no Artifact / no success Event.
            return CompletionOutcome.STALE_NOOP
        # 3. Durable ResultArtifact reference (Object Storage key, never bytes).
        await uow.artifacts.create(
            attempt_id=attempt_id, object_key=object_key, artifact_type=artifact_type
        )
        # 4. Append the success Event (internal business history).
        await uow.events.append(
            job_id,
            "job_succeeded",
            attempt_id=attempt_id,
            metadata={"object_key": object_key},
        )
        # 5. One commit for the whole atomic pack (or the UoW rolls it all back).
        await uow.commit()
        return CompletionOutcome.COMPLETED
