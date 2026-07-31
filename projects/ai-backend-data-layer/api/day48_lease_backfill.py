"""Day48 — operational Lease Backfill (SEPARATE from Alembic ``upgrade()``).

This is the BACKFILL phase: a controlled operational data-migration step, run as a
standalone operator script — NOT inside an Alembic ``upgrade()`` (long Backfill
loops must never live in a migration transaction). It:

    * fills ONLY ``running`` Jobs whose Lease columns are still NULL AND for which
      a TRUSTED ownership evidence source still exists — an unknown-ownership
      running Job is NEVER fabricated; it goes to reconciliation/recovery;
    * uses SHORT transactions with ``FOR UPDATE SKIP LOCKED`` batching so it is
      concurrent-safe, idempotent, and RESTARTABLE — the database state is the
      recovery checkpoint (re-selecting ``lease_owner IS NULL`` resumes cleanly);
    * calls NO Provider and holds NO long transaction;
    * is NOT the Day47 Lease runtime protocol and NOT the migration-batch claim of
      a Lease expiry — it is a one-time operational backfill.

Runtime evidence: the accompanying tests exercise this CONTROL FLOW with a FAKE
session and are NOT PostgreSQL proof. A real run needs PostgreSQL + an async
driver and the Expand (0002) revision already applied.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Optional, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True)
class LeaseEvidence:
    """Trusted, pre-existing ownership evidence for ONE running Job. Never
    fabricated — produced only from a trusted source (e.g. an authenticated
    Worker's still-valid registration). ``None`` from the evidence source means
    unknown ownership -> the Job is skipped for reconciliation, not backfilled."""

    job_id: uuid.UUID
    lease_owner: str
    lease_token: uuid.UUID
    lease_expires_at: datetime


class EvidenceSource(Protocol):
    async def prove(self, job_id: uuid.UUID) -> Optional[LeaseEvidence]:
        """Return trusted evidence for a running Job, or None if ownership is
        unknown (-> reconciliation, never fabrication)."""
        ...


async def select_backfill_batch(
    session: AsyncSession, *, batch_size: int
) -> List[uuid.UUID]:
    """One SHORT selection of a concurrent-safe batch. Selects only running Jobs
    with Lease still NULL, locking them with FOR UPDATE SKIP LOCKED so parallel
    backfill workers never contend or double-process a row."""
    result = await session.execute(
        text(
            "SELECT job_id FROM app.jobs "
            "WHERE job_status = 'running' AND lease_owner IS NULL "
            "ORDER BY created_at "
            "FOR UPDATE SKIP LOCKED "
            "LIMIT :batch_size"
        ),
        {"batch_size": batch_size},
    )
    return [row[0] for row in result.fetchall()]


async def apply_lease_evidence(session: AsyncSession, evidence: LeaseEvidence) -> int:
    """Idempotent, restartable guarded write: set the Lease triple ONLY while the
    Job is still running AND still unowned. Re-running is a no-op (0 rows) once a
    row is filled, so an interrupted backfill resumes safely."""
    result = await session.execute(
        text(
            "UPDATE app.jobs "
            "SET lease_owner = :lease_owner, "
            "    lease_token = :lease_token, "
            "    lease_expires_at = :lease_expires_at "
            "WHERE job_id = :job_id "
            "AND job_status = 'running' AND lease_owner IS NULL "
            "RETURNING job_id"
        ),
        {
            "job_id": evidence.job_id,
            "lease_owner": evidence.lease_owner,
            "lease_token": evidence.lease_token,
            "lease_expires_at": evidence.lease_expires_at,
        },
    )
    return len(result.fetchall())


@dataclass
class BackfillReport:
    backfilled: int = 0
    skipped_unknown: int = 0  # running + unowned but NO trusted evidence -> reconcile


async def run_backfill(
    session_factory: async_sessionmaker[AsyncSession],
    evidence_source: EvidenceSource,
    *,
    batch_size: int = 100,
    max_batches: Optional[int] = None,
) -> BackfillReport:
    """Drive the backfill in SHORT, restartable batches. Each batch is its own
    short transaction (select-lock -> apply evidence -> commit). A Job with no
    trusted evidence is SKIPPED (counted for reconciliation), never fabricated.
    Stops when a batch is empty (checkpoint = the database state)."""
    report = BackfillReport()
    batches = 0
    while max_batches is None or batches < max_batches:
        batches += 1
        async with session_factory() as session:
            job_ids = await select_backfill_batch(session, batch_size=batch_size)
            if not job_ids:
                await session.rollback()
                break
            for job_id in job_ids:
                evidence = await evidence_source.prove(job_id)
                if evidence is None:
                    # Unknown ownership -> reconciliation/recovery, NOT fabrication.
                    report.skipped_unknown += 1
                    continue
                report.backfilled += await apply_lease_evidence(session, evidence)
            await session.commit()
    return report
