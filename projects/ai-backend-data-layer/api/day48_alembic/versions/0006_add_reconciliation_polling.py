"""Additive (branch): reconciliation POLLING/BACKOFF columns on the queue table.

Revision ID: 0006_add_reconciliation_polling
Revises: 0003_add_lease_constraints
Create Date: 2026-07-31

WHY A BRANCH OFF 0003 (and NOT an edit of any published revision, and NOT a linear
append after 0005):

    An applied Alembic revision is IMMUTABLE, and we have NO verifiable evidence that
    0004_validate_lease / 0005_contract_legacy were never applied to a real database.
    So we must NOT rewrite the down_revision of 0004/0005 (a DB already recorded at
    0004 or 0005 would then never auto-apply the polling columns and the resolver
    would reference missing columns).

    A pure LINEAR append after 0005 would also be wrong: a database still at 0003
    would then have to run 0004 (Validate) and 0005 (Contract) BEFORE it could reach
    the polling columns — but the reconciliation resolver runs during the Backfill
    phase, BEFORE Validate. Forcing Validate first is exactly the ordering bug we must
    avoid.

    The correct shape is an INTENTIONAL BRANCH: this revision's parent is
    0003_add_lease_constraints, so a database at 0003 can reach the polling schema
    WITHOUT passing through Validate/Contract, while databases already at 0004 or 0005
    can also apply it (its only dependency, 0003, is in their applied set). The two
    heads (0005_contract_legacy and this revision) are re-unified by the merge
    revision 0007_merge_reconciliation_polling so the graph has a SINGLE head again.
    See the runbook's upgrade matrix + "avoid accidental Validate/Contract" note.

ADDITIVE ONLY. No long data-backfill loop lives in this ``upgrade()``. It touches only
the INDEPENDENT app.job_lease_reconciliation table, never app.jobs, so it neither
depends on nor affects the strict jobs_running_requires_lease CHECK:

  * next_attempt_at timestamptz NOT NULL DEFAULT now() -- RECONCILIATION POLLING clock
    (NOT Job retry, NOT Provider retry). The DDL DEFAULT gives every EXISTING open row
    a real, safe initial value: ``now()`` at migration time, so every historical open
    record is immediately DUE for the next reconciliation scan. This is a DDL default
    applied by ADD COLUMN -- NOT a fabricated Lease/owner/token/terminal/Provider
    outcome, and NOT a separate data backfill (none is needed).
  * last_checked_at timestamptz (nullable) -- audit: last evidence check (NULL = never).
  * check_attempts integer NOT NULL DEFAULT 0 -- audit/backoff counter (existing rows 0).

INDEX: the resolver selects with
    WHERE resolution_status = 'open' AND next_attempt_at <= now()
    ORDER BY next_attempt_at
    FOR UPDATE OF r SKIP LOCKED
so a PARTIAL index on (next_attempt_at) WHERE resolution_status = 'open' serves both the
due-filter and the ORDER BY while staying small. A plain CREATE INDEX inside the
migration briefly locks writes on this SMALL triage table, which is acceptable; if the
table were ever large, build it CREATE INDEX CONCURRENTLY OUTSIDE a migration
transaction (it cannot run inside one) -- see the runbook.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_add_reconciliation_polling"
down_revision = "0003_add_lease_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN only -- additive and safe for a database at ANY applied stage
    # (0003 / 0004 / 0005). The NOT NULL DEFAULT now() / DEFAULT 0 give existing rows
    # correct initial values without any data-backfill loop.
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
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_lease_reconciliation_due "
        "ON app.job_lease_reconciliation (next_attempt_at) "
        "WHERE resolution_status = 'open'"
    )


def downgrade() -> None:
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
