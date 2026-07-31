"""Additive: reconciliation POLLING/BACKOFF columns on app.job_lease_reconciliation.

Revision ID: 0003b_add_reconciliation_polling
Revises: 0003_add_lease_constraints
Create Date: 2026-07-31

WHY THIS IS A SEPARATE REVISION (not an edit of 0002_expand_lease):
    An Alembic revision is IMMUTABLE once it may have been applied to any real
    database. Editing 0002 (where the queue table is CREATEd) would NOT add these
    columns to a database that already ran 0002 or 0003 -- the table would still be
    missing next_attempt_at/last_checked_at/check_attempts and
    ``run_reconciliation_resolution()`` would fail at runtime with an undefined
    column. So the columns are added FORWARD, additively, here.

PLACEMENT: this revision sits AFTER 0003_add_lease_constraints (the last revision
that a real database may already have applied -- Expand or strict-constraint stage)
and BEFORE 0004_validate_lease. The reconciliation resolver runs during the
Backfill phase (after 0003, before 0004), so the polling columns must exist by
then; they must NOT depend on VALIDATE having run first. This revision only touches
the INDEPENDENT app.job_lease_reconciliation table, never app.jobs, so it is
unaffected by (and does not affect) the strict jobs_running_requires_lease CHECK.

ADDITIVE ONLY. No long data-backfill loop lives in this ``upgrade()``:

  * next_attempt_at timestamptz NOT NULL DEFAULT now() -- RECONCILIATION POLLING
    clock (NOT Job retry, NOT Provider retry). The DDL DEFAULT is what gives every
    EXISTING open row a real, safe initial value: ``now()`` at migration time, so
    every historical open record is immediately DUE and will be picked up by the
    next reconciliation scan. This is a DDL default applied to existing rows by the
    ADD COLUMN itself -- NOT a fabricated Lease/owner/token/terminal/Provider
    outcome, and NOT a separate data backfill (none is needed because ``now()`` IS
    the correct initial value for "check this open record as soon as possible").
  * last_checked_at timestamptz (nullable) -- audit: when a resolver last looked for
    evidence. NULL for existing rows means "not checked yet", which is truthful.
  * check_attempts integer NOT NULL DEFAULT 0 -- audit/backoff counter; existing rows
    correctly start at 0 fruitless checks.

INDEX: the resolver selects with
    WHERE resolution_status = 'open' AND next_attempt_at <= now()
    ORDER BY next_attempt_at
    FOR UPDATE OF r SKIP LOCKED
so a PARTIAL index on (next_attempt_at) WHERE resolution_status = 'open' serves both
the due-filter and the ORDER BY while staying small (only open rows are indexed).
It is created with a plain ``CREATE INDEX`` inside the migration transaction, which
briefly locks writes on this table. SCALE/PERFORMANCE TRADE-OFF: the reconciliation
queue is a small triage table (only unknown-ownership running Jobs, expected to be
a tiny minority), so a plain build is fine. If this table were ever large enough
that a brief write lock mattered, build the index with ``CREATE INDEX CONCURRENTLY``
OUTSIDE a migration transaction instead (it cannot run inside one) -- see the runbook.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003b_add_reconciliation_polling"
down_revision = "0003_add_lease_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN only -- additive and safe for a database already at Expand (0002) or
    # strict-constraint (0003) stage. The NOT NULL DEFAULT now() / DEFAULT 0 give
    # existing rows correct initial values without any data-backfill loop.
    op.execute(
        "ALTER TABLE app.job_lease_reconciliation "
        "ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now(), "
        "ADD COLUMN last_checked_at timestamptz, "
        "ADD COLUMN check_attempts  integer NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE app.job_lease_reconciliation "
        "ADD CONSTRAINT job_lease_reconciliation_check_attempts_nonneg "
        "CHECK (check_attempts >= 0)"
    )
    # Partial index matching the resolver's due-scan (open rows, ordered by due time).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_lease_reconciliation_due "
        "ON app.job_lease_reconciliation (next_attempt_at) "
        "WHERE resolution_status = 'open'"
    )


def downgrade() -> None:
    # Reverse of upgrade(): drop the index, the CHECK, then the columns. Safe only
    # before real reconciliation polling data must be preserved; otherwise forward-fix.
    op.execute("DROP INDEX IF EXISTS app.ix_job_lease_reconciliation_due")
    op.execute(
        "ALTER TABLE app.job_lease_reconciliation "
        "DROP CONSTRAINT IF EXISTS job_lease_reconciliation_check_attempts_nonneg"
    )
    op.execute(
        "ALTER TABLE app.job_lease_reconciliation "
        "DROP COLUMN IF EXISTS check_attempts, "
        "DROP COLUMN IF EXISTS last_checked_at, "
        "DROP COLUMN IF EXISTS next_attempt_at"
    )
