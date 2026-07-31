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


# Backoff bounds for reconciliation POLLING (NOT Job retry, NOT Provider retry):
# each fruitless check pushes next_attempt_at forward by an exponentially growing
# interval, capped, so the resolver stops hot-looping on an unprovable record while
# still re-checking it periodically until trusted evidence appears.
DEFAULT_RECONCILIATION_BASE_BACKOFF_SECONDS = 60
DEFAULT_RECONCILIATION_MAX_BACKOFF_SECONDS = 3600


async def defer_reconciliation_record(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    base_backoff_seconds: int = DEFAULT_RECONCILIATION_BASE_BACKOFF_SECONDS,
    max_backoff_seconds: int = DEFAULT_RECONCILIATION_MAX_BACKOFF_SECONDS,
) -> int:
    """POLLING/BACKOFF step for an OPEN record that STILL has no trusted evidence.
    This is a QUEUE-ONLY, short, auditable UPDATE: it records that a check happened
    (``last_checked_at = now()``, ``check_attempts + 1``) and pushes
    ``next_attempt_at`` into the future by an exponential, capped backoff, so the
    SAME record is not re-selected in the current loop (``select_open_reconciliation_batch``
    only returns due records). It does NOT fabricate a Lease, does NOT requeue, does
    NOT touch ``app.jobs`` / ``job_status``, and calls NO Provider — the record stays
    ``resolution_status='open'`` and STILL counts as an unresolved target. This is
    reconciliation POLLING, NOT Job retry and NOT Provider retry. The backoff uses
    the PRE-increment ``check_attempts`` (SQL evaluates all SET right-hand sides
    against the OLD row), so attempt 0 waits ``base`` seconds, then doubles, capped
    at ``max``. Guarded on ``resolution_status='open'`` and idempotent per due-cycle."""
    result = await session.execute(
        text(
            "UPDATE app.job_lease_reconciliation "
            "SET check_attempts = check_attempts + 1, "
            "    last_checked_at = now(), "
            "    next_attempt_at = now() + make_interval(secs => "
            "        LEAST(:base_backoff_seconds * power(2, check_attempts), "
            "              :max_backoff_seconds)) "
            "WHERE job_id = :job_id AND resolution_status = 'open' "
            "RETURNING reconciliation_id"
        ),
        {
            "job_id": job_id,
            "base_backoff_seconds": base_backoff_seconds,
            "max_backoff_seconds": max_backoff_seconds,
        },
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


async def select_open_reconciliation_batch(
    session: AsyncSession, *, batch_size: int
) -> List[uuid.UUID]:
    """One SHORT, concurrent-safe selection of DUE OPEN reconciliation records whose
    Job is STILL running AND still unowned (so a resolution is still needed and still
    legal). "Due" means ``next_attempt_at <= now()`` — a record a resolver just
    deferred (its ``next_attempt_at`` pushed into the future by the backoff) is
    therefore NOT re-selected until it is due again, which is what makes
    ``run_reconciliation_resolution`` TERMINATE in real PostgreSQL even with
    ``max_batches=None`` (it is NOT the fake session returning an empty batch that
    proves termination — it is this due-filter combined with the forward backoff).
    We lock the reconciliation rows with ``FOR UPDATE OF r SKIP LOCKED`` so parallel
    resolvers never contend and a crash mid-batch leaves the record OPEN for a
    restart to retry. This is the ONLY selector that revisits a routed Job — the
    AUTOMATIC candidate query (``select_backfill_batch``) permanently excludes queued
    Jobs, matching real SQL: once a Job has a queue row it is not an automatic
    candidate again; its resolution flows through THIS path instead."""
    result = await session.execute(
        text(
            "SELECT r.job_id "
            "FROM app.job_lease_reconciliation r "
            "JOIN app.jobs j ON j.job_id = r.job_id "
            "WHERE r.resolution_status = 'open' "
            "AND r.next_attempt_at <= now() "
            "AND j.job_status = 'running' AND j.lease_owner IS NULL "
            "ORDER BY r.next_attempt_at "
            "FOR UPDATE OF r SKIP LOCKED "
            "LIMIT :batch_size"
        ),
        {"batch_size": batch_size},
    )
    return [row[0] for row in result.fetchall()]


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
    routed_to_reconciliation: int = 0  # running + unowned + NO trusted evidence -> INSERTed into the queue
    # remaining_targets (Day36): ALL still-running rows with a NULL Lease, INCLUDING
    # queue-routed ones. VALIDATE/Switch/Contract require this to be 0. A nonzero
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
    commit). A Job with no trusted evidence is ROUTED into the INDEPENDENT
    reconciliation queue (never fabricated), so it leaves the AUTOMATIC candidate set
    and the loop TERMINATES even with ``max_batches=None``; stops when a batch is
    empty (checkpoint = the database state, so a restart resumes cleanly).

    This handles AUTOMATIC candidates ONLY. A Job already in the queue is NOT
    re-selected here (``select_backfill_batch`` excludes it, exactly as real SQL
    requires); when trusted evidence appears later it is resolved by the separate
    ``run_reconciliation_resolution`` path.

    IMPORTANT: the automatic loop stopping does NOT mean the history is compliant.
    The report exposes ``unresolved_running_without_lease`` (Day36 remaining_targets,
    INCLUDING queue-routed rows). VALIDATE / Switch / Contract require that count
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
                    # Unknown ownership -> INSERT a reconciliation-queue record so this
                    # Job is not re-selected by the automatic loop. This is TRIAGE,
                    # NOT resolution: the row STILL violates jobs_running_requires_lease
                    # and STILL counts below. No Lease is fabricated. Later resolution
                    # flows through run_reconciliation_resolution.
                    report.routed_to_reconciliation += await route_to_reconciliation(
                        session, job_id
                    )
                    continue
                report.backfilled += await apply_lease_evidence(session, evidence)
            await session.commit()
    # Final DB-backed truth: how many running-without-Lease rows REMAIN (including
    # queue-routed ones). This — not "the loop stopped" — is the VALIDATE gate.
    async with session_factory() as session:
        report.unresolved_running_without_lease = (
            await count_unresolved_running_without_lease(session)
        )
        await session.rollback()
    return report


@dataclass
class ReconciliationResolutionReport:
    # An OPEN record whose Job later gained trusted evidence: the Lease triple was
    # written to app.jobs AND the queue record was closed in the SAME short tx.
    resolved: int = 0
    # An OPEN record whose Job still has NO trusted evidence -> LEFT open (no
    # fabrication, no requeue, no bare status flip, no Provider call).
    still_open: int = 0
    # Day36 remaining_targets after this pass (ALL running app.jobs with a NULL
    # Lease, INCLUDING still-open records). VALIDATE/Switch/Contract require 0.
    unresolved_running_without_lease: int = 0


async def run_reconciliation_resolution(
    session_factory: async_sessionmaker[AsyncSession],
    evidence_source: EvidenceSource,
    *,
    batch_size: int = 100,
    max_batches: Optional[int] = None,
    base_backoff_seconds: int = DEFAULT_RECONCILIATION_BASE_BACKOFF_SECONDS,
    max_backoff_seconds: int = DEFAULT_RECONCILIATION_MAX_BACKOFF_SECONDS,
) -> ReconciliationResolutionReport:
    """RESOLUTION path for records already in the reconciliation queue — the piece
    the AUTOMATIC loop cannot do (``select_backfill_batch`` permanently excludes
    queued Jobs, exactly as real SQL requires). It drives SHORT, restartable batches
    over ``resolution_status='open'`` records whose Job is still running + unowned:

      1. guarded ``UPDATE app.jobs`` writes the FULL Lease triple (apply_lease_evidence);
      2. ONLY if that UPDATE actually affected the row (returned 1) is the queue
         record marked ``resolved`` with ``resolved_at`` — in the SAME short tx.

    If no trusted evidence exists yet, the record is LEFT open AND DEFERRED
    (``defer_reconciliation_record``): a queue-only, short, audited UPDATE bumps
    ``check_attempts`` / ``last_checked_at`` and pushes ``next_attempt_at`` forward by
    an exponential capped backoff — never a fabricated Lease, never a requeue, never
    a bare ``app.jobs.job_status`` flip, never a Provider call. Because the selector
    only returns DUE records (``next_attempt_at <= now()``), deferring guarantees the
    SAME record is not immediately re-selected, so THIS loop TERMINATES in real
    PostgreSQL even with ``max_batches=None`` — termination rests on the due-filter +
    forward backoff, NOT on a fake session returning an empty batch. This is
    reconciliation POLLING/BACKOFF, NOT Job retry and NOT Provider retry.

    If the guarded UPDATE affects 0 rows (e.g. the Job was concurrently resolved so
    it no longer matches running + unowned), the record is NOT closed by this attempt
    — closing is gated on THIS UoW's own successful write, keeping the pass idempotent
    and restart-safe (the checkpoint is the durable DB state). This does NOT reduce
    ``unresolved_running_without_lease`` except by a REAL Lease write; only then may
    VALIDATE/Switch/Contract proceed. Calls NO Provider and holds NO long tx."""
    report = ReconciliationResolutionReport()
    batches = 0
    while max_batches is None or batches < max_batches:
        batches += 1
        async with session_factory() as session:
            job_ids = await select_open_reconciliation_batch(
                session, batch_size=batch_size
            )
            if not job_ids:
                await session.rollback()
                break
            for job_id in job_ids:
                evidence = await evidence_source.prove(job_id)
                if evidence is None:
                    # Still unprovable -> leave the record OPEN, but DEFER it with a
                    # queue-only backoff so this loop does not re-select it and
                    # spin forever. No Lease fabricated, no requeue, no status flip,
                    # no Provider. (Reconciliation polling, not Job/Provider retry.)
                    await defer_reconciliation_record(
                        session,
                        job_id,
                        base_backoff_seconds=base_backoff_seconds,
                        max_backoff_seconds=max_backoff_seconds,
                    )
                    report.still_open += 1
                    continue
                applied = await apply_lease_evidence(session, evidence)
                if applied:
                    # Close the queue record ONLY after the guarded UPDATE succeeded.
                    report.resolved += await close_reconciliation_record(
                        session, job_id
                    )
                else:
                    # The Job no longer matched running + unowned (e.g. resolved
                    # concurrently); do NOT close on this attempt's behalf.
                    report.still_open += 1
            await session.commit()
    async with session_factory() as session:
        report.unresolved_running_without_lease = (
            await count_unresolved_running_without_lease(session)
        )
        await session.rollback()
    return report
