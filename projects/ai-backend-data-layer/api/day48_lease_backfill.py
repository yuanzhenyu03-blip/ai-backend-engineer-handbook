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
    * TERMINATES the AUTOMATIC loop: every selected Job leaves the AUTOMATIC
      candidate set within the batch — a proved Job gets its Lease (``lease_owner``
      becomes NON-NULL) and an unknown-ownership Job is routed into the INDEPENDENT
      reconciliation queue table ``app.job_lease_reconciliation`` (NOT a column on
      app.jobs), so neither is re-selected by the automatic loop in this run or after
      a restart. Routing writes ONLY the queue, NEVER app.jobs, so it can run AFTER
      the strict jobs_running_requires_lease constraint is live (a marker UPDATE that
      left the row running with a NULL Lease would be REJECTED). Routing fabricates
      NO Lease owner/token/expiry;
    * DOES NOT make an unknown Job compliant. Reconciliation is TRIAGE, not
      RESOLUTION: a routed running Job with a NULL Lease STILL violates the Day36
      ``jobs_running_requires_lease`` invariant and STILL counts as an UNRESOLVED
      running-without-Lease target (routing did not change app.jobs). The migration
      stays INCOMPLETE (do NOT run VALIDATE / Switch / Contract) until every such row
      is truthfully resolved by (a) a trusted Lease backfill or (b) an audited real
      recovery routed to a full boundary (Day47 completion UoW for a verified
      success; guarded terminal-recovery for a verified failure/cancellation) —
      NEVER by queuing alone, NEVER by a requeue, and NEVER by a bare status flip;
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
from enum import Enum
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
    """One SHORT selection of a concurrent-safe batch of AUTOMATIC backfill
    candidates: running Jobs with Lease still NULL AND not already routed in the
    INDEPENDENT reconciliation queue, locked with FOR UPDATE SKIP LOCKED so parallel
    workers never contend. The routed set lives in ``app.job_lease_reconciliation``
    (NOT on app.jobs), so excluding it here makes the AUTOMATIC loop TERMINATE and
    be restart-safe WITHOUT touching the business row — it does NOT mean those rows
    are resolved (see ``count_unresolved_running_without_lease``)."""
    result = await session.execute(
        text(
            "SELECT j.job_id FROM app.jobs j "
            "WHERE j.job_status = 'running' AND j.lease_owner IS NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM app.job_lease_reconciliation r WHERE r.job_id = j.job_id"
            ") "
            "ORDER BY j.created_at "
            "FOR UPDATE SKIP LOCKED "
            "LIMIT :batch_size"
        ),
        {"batch_size": batch_size},
    )
    return [row[0] for row in result.fetchall()]


async def apply_lease_evidence(session: AsyncSession, evidence: LeaseEvidence) -> int:
    """RESOLUTION path (a): a TRUSTED, audited Lease backfill. Idempotent, guarded
    write that sets the Lease triple ONLY while the Job is still running AND still
    unowned — so it resolves a reconcile-routed row too, after which the row
    satisfies jobs_running_requires_lease and is no longer an unresolved target.
    Re-running is a no-op (0 rows) once filled. It writes ONLY app.jobs; closing any
    reconciliation-queue record is a separate audited step
    (``close_reconciliation_record``)."""
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


async def route_to_reconciliation(
    session: AsyncSession, job_id: uuid.UUID, *, reason: str = "unknown_ownership"
) -> int:
    """Persist an unknown-ownership running Job into the INDEPENDENT reconciliation
    queue (``app.job_lease_reconciliation``) so the automatic loop stops re-selecting
    it. This does NOT touch app.jobs — the business row stays ``running`` with a NULL
    Lease, which is CRITICAL: after 0003, any UPDATE that left the row running with a
    NULL Lease would be REJECTED by jobs_running_requires_lease, so triage MUST live
    outside the row. Idempotent + RESTART-safe via UNIQUE(job_id) + ON CONFLICT DO
    NOTHING (re-routing returns 0 rows). Fabricates NO Lease owner/token/expiry and
    NO terminal status. The Job STILL counts as unresolved (see
    ``count_unresolved_running_without_lease``)."""
    result = await session.execute(
        text(
            "INSERT INTO app.job_lease_reconciliation (job_id, reason) "
            "VALUES (:job_id, :reason) "
            "ON CONFLICT (job_id) DO NOTHING "
            "RETURNING reconciliation_id"
        ),
        {"job_id": job_id, "reason": reason},
    )
    return len(result.fetchall())


async def close_reconciliation_record(
    session: AsyncSession, job_id: uuid.UUID
) -> int:
    """AUDIT step: mark an open reconciliation record 'resolved' once the Job has
    been truthfully resolved elsewhere (a trusted Lease backfill or a full audited
    Recovery UoW). Idempotent (an already-resolved / absent record -> 0 rows). This
    does NOT itself resolve the Job — it only closes the triage trail."""
    result = await session.execute(
        text(
            "UPDATE app.job_lease_reconciliation "
            "SET resolution_status = 'resolved', resolved_at = now() "
            "WHERE job_id = :job_id AND resolution_status = 'open' "
            "RETURNING reconciliation_id"
        ),
        {"job_id": job_id},
    )
    return len(result.fetchall())


async def count_unresolved_running_without_lease(session: AsyncSession) -> int:
    """Count EVERY still-violating running-without-Lease row on app.jobs — INCLUDING
    Jobs routed into the reconciliation queue (routing does NOT change app.jobs).
    This is the Day36 ``remaining_targets``: the hard VALIDATE / Switch / Contract
    precondition (must be 0), and being queued for reconciliation does NOT reduce it.
    lease_owner IS NULL is equivalent to a NULL Lease under the triple-coherence
    constraint."""
    result = await session.execute(
        text(
            "SELECT count(*) FROM app.jobs "
            "WHERE job_status = 'running' AND lease_owner IS NULL"
        )
    )
    rows = result.fetchall()
    return int(rows[0][0]) if rows else 0


class UnsafeRecoveryError(ValueError):
    """Raised when a caller asks Day48 to "resolve" an unknown running Job in a way
    that would be unsafe: a requeue (``queued``), a non-terminal state, or a bare
    status flip that fabricates a verified terminal outcome."""


class RecoveryBoundary(str, Enum):
    """Which FULL boundary owns the recovery of an unresolved running Job. Day48's
    migration/backfill layer classifies and ROUTES; it does NOT mutate the row
    itself (a bare status UPDATE cannot honor the Day47 completion contract or the
    guarded terminal-recovery/audit requirements)."""

    COMPLETION_UOW = "day47_guarded_completion_uow"          # verified succeeded
    GUARDED_TERMINAL_RECOVERY = "guarded_terminal_recovery"  # verified failed/cancelled
    KEEP_UNKNOWN = "keep_unknown_reconciliation"             # outcome not verified


# Day42 terminal states (the status allowlist's terminal members). A Job may only
# be RESOLVED into one of these — never back to 'queued' (a requeue) or 'running'.
_VERIFIED_TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


def classify_unknown_running_recovery(verified_outcome: Optional[str]) -> RecoveryBoundary:
    """Classify how an unresolved running-without-Lease Job must be recovered, and
    REFUSE unsafe requests. This performs NO database write — it only routes to the
    correct FULL boundary (Day48 does not orchestrate completion or failure):

        * ``None`` (outcome NOT verified) -> KEEP_UNKNOWN. Stay unknown/reconciliation;
          NEVER requeue and NEVER blindly re-call the Provider (Day47 unknown-outcome
          boundary): the Provider may have already executed, charged, or produced an
          Artifact.
        * ``'succeeded'`` -> COMPLETION_UOW. A verified success MUST go through the
          Day47 guarded completion UoW so it commits finished_at + the ResultArtifact
          reference + the job_succeeded Event together — a bare ``UPDATE
          job_status='succeeded'`` would violate jobs_succeeded_has_finished_at and
          leave partial state. Day48 does NOT perform it.
        * ``'failed'`` / ``'cancelled'`` -> GUARDED_TERMINAL_RECOVERY. A verified
          business failure/cancellation MUST go through the guarded terminal-recovery
          path (state machine + Event + audit), not a bare status flip.
        * ``'queued'`` / ``'running'`` / anything else -> UnsafeRecoveryError.
          Requeuing an unknown Job clears the unresolved count WITHOUT proving whether
          the Provider ran; a non-terminal/unknown status is never a resolution."""
    if verified_outcome is None:
        return RecoveryBoundary.KEEP_UNKNOWN
    if verified_outcome == "succeeded":
        return RecoveryBoundary.COMPLETION_UOW
    if verified_outcome in ("failed", "cancelled"):
        return RecoveryBoundary.GUARDED_TERMINAL_RECOVERY
    raise UnsafeRecoveryError(
        f"cannot resolve an unknown running Job to {verified_outcome!r}: requeuing "
        "('queued') or a non-terminal state is forbidden, and a bare status update "
        "cannot fabricate a verified terminal outcome. 'succeeded' -> Day47 guarded "
        "completion UoW; 'failed'/'cancelled' -> guarded terminal-recovery; an "
        "unverified outcome stays unknown/reconciliation."
    )


@dataclass
class BackfillReport:
    backfilled: int = 0
    routed_to_reconciliation: int = 0  # running + unowned + NO trusted evidence -> persisted 'reconcile'
    # remaining_targets (Day36): ALL still-running rows with a NULL Lease, INCLUDING
    # reconcile-marked ones. VALIDATE/Switch/Contract require this to be 0. A nonzero
    # value means the migration is INCOMPLETE even when the automatic loop has stopped.
    unresolved_running_without_lease: int = 0


async def run_backfill(
    session_factory: async_sessionmaker[AsyncSession],
    evidence_source: EvidenceSource,
    *,
    batch_size: int = 100,
    max_batches: Optional[int] = None,
) -> BackfillReport:
    """Drive the AUTOMATIC backfill in SHORT, restartable batches. Each batch is its
    own short transaction (select-lock -> apply evidence OR route unknowns ->
    commit). A Job with no trusted evidence is ROUTED to a persistent reconciliation
    marker (never fabricated), so it leaves the AUTOMATIC candidate set and the loop
    TERMINATES even with ``max_batches=None``; stops when a batch is empty
    (checkpoint = the database state, so a restart resumes cleanly).

    IMPORTANT: the automatic loop stopping does NOT mean the history is compliant.
    The report exposes ``unresolved_running_without_lease`` (Day36 remaining_targets,
    INCLUDING reconcile-marked rows). VALIDATE / Switch / Contract require that count
    to be 0, reached ONLY by a trusted Lease backfill or an audited real recovery."""
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
                    # Job is not re-selected by the automatic loop. This is TRIAGE,
                    # NOT resolution: the row STILL violates jobs_running_requires_lease
                    # and STILL counts below. No Lease is fabricated.
                    report.routed_to_reconciliation += await route_to_reconciliation(
                        session, job_id
                    )
                    continue
                report.backfilled += await apply_lease_evidence(session, evidence)
            await session.commit()
    # Final DB-backed truth: how many running-without-Lease rows REMAIN (including
    # reconcile-marked ones). This — not "the loop stopped" — is the VALIDATE gate.
    async with session_factory() as session:
        report.unresolved_running_without_lease = (
            await count_unresolved_running_without_lease(session)
        )
        await session.rollback()
    return report
