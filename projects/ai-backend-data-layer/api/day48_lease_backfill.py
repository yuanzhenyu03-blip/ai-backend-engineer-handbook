"""Day48 — operational Lease Backfill (SEPARATE from Alembic ``upgrade()``).

This is the BACKFILL phase: a controlled operational data-migration step, run as a
standalone operator script — NOT inside an Alembic ``upgrade()`` (long Backfill
loops must never live in a migration transaction). It:

    * fills ONLY ``running`` Jobs whose Lease columns are still NULL AND for which
      a TRUSTED ownership evidence source still exists — an unknown-ownership
      running Job is NEVER fabricated; it goes to reconciliation/recovery;
    * uses SHORT transactions with ``FOR UPDATE SKIP LOCKED`` batching so it is
      concurrent-safe, idempotent, and RESTARTABLE — the database state is the
      recovery checkpoint;
    * TERMINATES: every selected Job leaves the candidate set within the batch —
      a proved Job gets its Lease (``lease_owner`` becomes NON-NULL) and an
      unknown-ownership Job is routed to a PERSISTENT reconciliation marker
      (``lease_backfill_state = 'reconcile'``), so neither is re-selected in this
      run or after a restart. Routing NEVER fabricates a Lease owner/token/expiry;
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
    with Lease still NULL AND not yet routed to reconciliation
    (``lease_backfill_state IS NULL``), locking them with FOR UPDATE SKIP LOCKED so
    parallel backfill workers never contend or double-process a row. Excluding
    reconciliation-routed rows is what makes the backfill TERMINATE and be
    restart-safe."""
    result = await session.execute(
        text(
            "SELECT job_id FROM app.jobs "
            "WHERE job_status = 'running' AND lease_owner IS NULL "
            "AND lease_backfill_state IS NULL "  # exclude Jobs already routed to reconciliation
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


async def route_to_reconciliation(session: AsyncSession, job_id: uuid.UUID) -> int:
    """Persist an unknown-ownership running Job into the reconciliation state so it
    leaves the candidate set. Idempotent + guarded (running, still unowned, not yet
    routed) and RESTART-safe: re-running is a no-op (0 rows) once routed. This does
    NOT fabricate any Lease field — lease_owner/token/expiry stay NULL; it only
    records 'ownership could not be proved -> reconcile'."""
    result = await session.execute(
        text(
            "UPDATE app.jobs "
            "SET lease_backfill_state = 'reconcile' "
            "WHERE job_id = :job_id "
            "AND job_status = 'running' AND lease_owner IS NULL "
            "AND lease_backfill_state IS NULL "
            "RETURNING job_id"
        ),
        {"job_id": job_id},
    )
    return len(result.fetchall())


@dataclass
class BackfillReport:
    backfilled: int = 0
    routed_to_reconciliation: int = 0  # running + unowned + NO trusted evidence -> persisted 'reconcile'


async def run_backfill(
    session_factory: async_sessionmaker[AsyncSession],
    evidence_source: EvidenceSource,
    *,
    batch_size: int = 100,
    max_batches: Optional[int] = None,
) -> BackfillReport:
    """Drive the backfill in SHORT, restartable batches. Each batch is its own
    short transaction (select-lock -> apply evidence OR route unknowns -> commit).
    A Job with no trusted evidence is ROUTED to a persistent reconciliation marker
    (never fabricated), so it leaves the candidate set and the loop TERMINATES even
    with ``max_batches=None``; stops when a batch is empty (checkpoint = the
    database state, so a restart resumes cleanly)."""
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
                    # Unknown ownership -> PERSIST a reconciliation marker so this
                    # Job is not re-selected in this run or after a restart. NOT
                    # fabrication: no Lease owner/token/expiry is written.
                    report.routed_to_reconciliation += await route_to_reconciliation(
                        session, job_id
                    )
                    continue
                report.backfilled += await apply_lease_evidence(session, evidence)
            await session.commit()
    return report
