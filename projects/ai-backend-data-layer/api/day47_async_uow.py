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
    * Guarded claim = one ``UPDATE ... WHERE job_status='queued' RETURNING ...``
      (not SELECT-then-UPDATE). One row = claimed; zero rows = a NORMAL stale/
      no-op miss (no Attempt/Event, not a retryable DB error).
    * A long/paid Provider call happens OUTSIDE any open DB transaction. Before it,
      commit a durable Attempt + an application-generated correlation/idempotency
      key. Completion is a SECOND short guarded UoW.
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
from day46_orm_mapping import Job, JobAttempt, JobEvent


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

    async def guarded_claim(self, job_id: uuid.UUID) -> int:
        """Single guarded transition: UPDATE ... WHERE job_status='queued'
        RETURNING job_id. Returns the number of rows claimed (1 = this Worker
        won; 0 = stale/no-op). This is NOT SELECT-then-UPDATE, so two Workers
        cannot both claim the same queued Job."""
        result = await self._session.execute(
            text(
                "UPDATE app.jobs SET job_status = 'running', started_at = now() "
                "WHERE job_id = :job_id AND job_status = 'queued' "
                "RETURNING job_id"
            ),
            {"job_id": job_id},
        )
        return len(result.fetchall())

    async def guarded_complete(
        self, job_id: uuid.UUID, *, finished_at: Optional[datetime] = None
    ) -> int:
        """Guarded terminal transition: only a still-'running' Job records success.
        Returns rows affected (1 = completed; 0 = stale/no-op — do NOT overwrite
        or duplicate terminal facts). The Day46 jobs_succeeded_has_finished_at
        CHECK is a STATE invariant; this row guard is CONCURRENCY control."""
        result = await self._session.execute(
            text(
                "UPDATE app.jobs SET job_status = 'succeeded', finished_at = :fa "
                "WHERE job_id = :job_id AND job_status = 'running' "
                "RETURNING job_id"
            ),
            {"job_id": job_id, "fa": finished_at or datetime.now(timezone.utc)},
        )
        return len(result.fetchall())

    async def mark_failed(self, job_id: uuid.UUID) -> int:
        """Definitive, non-retryable Provider failure -> failed (guarded on
        'running'). A timeout with UNKNOWN remote outcome must NOT use this; it
        stays unknown/recoverable."""
        result = await self._session.execute(
            text(
                "UPDATE app.jobs SET job_status = 'failed', finished_at = now() "
                "WHERE job_id = :job_id AND job_status = 'running' "
                "RETURNING job_id"
            ),
            {"job_id": job_id},
        )
        return len(result.fetchall())


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, job_id: uuid.UUID, attempt_number: int, correlation_key: str
    ) -> JobAttempt:
        """Create an Attempt carrying an APPLICATION-generated correlation/
        idempotency key (committed BEFORE any external call). The Provider's own
        request ID is persisted later, when available."""
        attempt = JobAttempt(
            job_id=job_id,
            attempt_number=attempt_number,
            provider_request_id=None,
            error_code=None,
        )
        # A frequently-queried correlation key would be a typed column in the
        # real schema; kept out of Day46 scope here, so it is illustrated via the
        # Event metadata rather than invented as a new column.
        self._session.add(attempt)
        # flush so the server-generated attempt_id is available for a dependent
        # Event write WITHOUT committing the transaction.
        await self._session.flush()
        return attempt


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

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.jobs = JobRepository(self.session)
        self.attempts = AttemptRepository(self.session)
        self.events = EventRepository(self.session)
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
    """Deterministic no-network seam for tests."""

    artifact_ref: Optional[str] = None
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
    correlation_key: str,
) -> ClaimOutcome:
    """UoW 1: guarded claim -> Attempt (flush) -> job_started Event -> commit,
    committing only if ALL succeed. A zero-row claim is a normal stale/no-op:
    create NO Attempt/Event and do not commit."""
    async with UnitOfWork(session_factory) as uow:
        assert uow.jobs and uow.attempts and uow.events
        claimed = await uow.jobs.guarded_claim(job_id)
        if claimed == 0:
            return ClaimOutcome.STALE_NOOP  # __aexit__ rolls back the empty UoW
        attempt = await uow.attempts.create(job_id, 1, correlation_key)
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
    attempt_id: uuid.UUID,
    artifact_ref: str,
) -> CompletionOutcome:
    """UoW 2 (a SECOND short guarded UoW, AFTER the Provider call returned):
    guarded terminal transition + completion Event together. A zero-row guarded
    completion is a normal stale/no-op: do not overwrite/duplicate facts."""
    async with UnitOfWork(session_factory) as uow:
        assert uow.jobs and uow.events
        completed = await uow.jobs.guarded_complete(job_id)
        if completed == 0:
            return CompletionOutcome.STALE_NOOP
        await uow.events.append(
            job_id,
            "job_succeeded",
            attempt_id=attempt_id,
            metadata={"artifact_ref": artifact_ref},
        )
        await uow.commit()
        return CompletionOutcome.COMPLETED
