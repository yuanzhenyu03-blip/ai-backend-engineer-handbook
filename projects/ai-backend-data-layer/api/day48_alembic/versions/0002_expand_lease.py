"""Expand: add nullable Lease compatibility columns ONLY (no constraints).

Revision ID: 0002_expand_lease
Revises: 0001_baseline
Create Date: 2026-07-31

EXPAND phase of Day36's Expand -> Backfill -> Validate -> Switch -> Contract.

This revision is a PURE Expand: it ADDs nullable columns with NO fabricated
default and adds NO constraint that would require a running Job to already carry
a Lease. That deliberate separation is what makes this a real OLD/NEW code
COMPATIBILITY WINDOW: while only this revision is applied, an OLD Writer can keep
updating a legacy ``running`` Job that has a NULL Lease, because no constraint yet
rejects such a write.

The strict Lease constraints (triple coherence + jobs_running_requires_lease) are
a SEPARATE later revision (0003_add_lease_constraints), applied ONLY AFTER the new
code is deployed and tolerates NULL Lease and the OLD Writers are drained/isolated
— because ``CHECK ... NOT VALID`` protects EVERY future write regardless of the
Writer's binary version (see 0003).

A NULL honestly means "no PROVED Lease ownership". Do NOT generate tokens for
queued, terminal, or unprovable running Jobs — fabrication is forbidden; the
operational Backfill (a SEPARATE step, NOT this upgrade) fills only running Jobs
with trusted ownership evidence and routes unknown ones to reconciliation.

``lease_backfill_state`` (NULLABLE, no default) is the PERSISTENT reconciliation
marker the operational Backfill uses to route an unknown-ownership running Job OUT
of the automatic candidate set (state = 'reconcile'). It fabricates NO Lease field
and does NOT make the Job compliant.
"""
from alembic import op

revision = "0002_expand_lease"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, no default: NULL == no proved Lease ownership. NO constraint here —
    # this is the OLD/NEW compatibility window (old Writers can still write a
    # running-without-Lease row until 0003 tightens the rule).
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD COLUMN lease_owner text, "
        "ADD COLUMN lease_token uuid, "
        "ADD COLUMN lease_expires_at timestamptz, "
        "ADD COLUMN lease_backfill_state text"
    )


def downgrade() -> None:
    # Safe ONLY before any real Lease data or Provider side effects exist. Once
    # real Lease tokens/Provider effects exist, DO NOT downgrade destructively —
    # preserve durable evidence and forward-fix + reconcile instead.
    op.execute(
        "ALTER TABLE app.jobs "
        "DROP COLUMN IF EXISTS lease_backfill_state, "
        "DROP COLUMN IF EXISTS lease_expires_at, "
        "DROP COLUMN IF EXISTS lease_token, "
        "DROP COLUMN IF EXISTS lease_owner"
    )
