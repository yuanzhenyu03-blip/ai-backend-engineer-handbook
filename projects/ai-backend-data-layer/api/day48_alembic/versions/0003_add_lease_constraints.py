"""Constraint: add the Lease coherence + running-requires-Lease CHECKs (NOT VALID).

Revision ID: 0003_add_lease_constraints
Revises: 0002_expand_lease
Create Date: 2026-07-31

SEPARATE from the pure Expand (0002) on purpose. This revision closes the OLD/NEW
compatibility window: from here every Writer must obey the new Lease protocol.

PRECONDITIONS (Alembic cannot check them; an operator MUST ensure them BEFORE
applying this revision):
  * the NEW code is deployed and tolerates a NULL Lease (the compatibility window
    from 0002 has been live long enough);
  * OLD Writers are DRAINED / ISOLATED — because ``CHECK ... NOT VALID`` protects
    EVERY future INSERT/UPDATE and does NOT distinguish Writer binary versions.
    An OLD Worker updating a still-``running`` Job with a NULL Lease would be
    REJECTED (23514 check_violation) once this revision is applied.

WHY ``NOT VALID`` still blocks old Workers' FUTURE writes:
  ``NOT VALID`` only skips the one-time SCAN of pre-existing rows; it fully
  ENFORCES the rule on every subsequent INSERT/UPDATE by any writer. So this is a
  Switch-adjacent gate, NOT a "no-op for old code" — apply it only after the old
  write path is closed.

The constraints are added ``NOT VALID`` (future writes protected, legacy rows
tolerated until 0004 VALIDATE). No Backfill loop, no Provider call, no long
transaction here.
"""
from alembic import op

revision = "0003_add_lease_constraints"
down_revision = "0002_expand_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Restrict the reconciliation marker's values on FUTURE writes.
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD CONSTRAINT jobs_lease_backfill_state_allowed "
        "CHECK (lease_backfill_state IS NULL OR lease_backfill_state = 'reconcile') NOT VALID"
    )
    # An all-or-nothing Lease triple.
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD CONSTRAINT jobs_lease_triple_coherent "
        "CHECK ( "
        "  (lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) "
        "  OR "
        "  (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
        ") NOT VALID"
    )
    # Day36 CORE invariant: a running Job MUST carry a complete, trusted Lease.
    # A reconcile-marked running Job with NULL Lease STILL violates this (the
    # reconcile marker is TRIAGE, not RESOLUTION), so 0004 VALIDATE cannot pass
    # until each such row is truthfully resolved.
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD CONSTRAINT jobs_running_requires_lease "
        "CHECK ( "
        "  job_status <> 'running' "
        "  OR "
        "  (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
        ") NOT VALID"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE app.jobs DROP CONSTRAINT IF EXISTS jobs_running_requires_lease")
    op.execute("ALTER TABLE app.jobs DROP CONSTRAINT IF EXISTS jobs_lease_triple_coherent")
    op.execute("ALTER TABLE app.jobs DROP CONSTRAINT IF EXISTS jobs_lease_backfill_state_allowed")
