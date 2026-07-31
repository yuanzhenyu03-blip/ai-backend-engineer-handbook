"""Validate: VALIDATE CONSTRAINT (separately gated, after Backfill/reconciliation).

Revision ID: 0003_validate_lease
Revises: 0002_expand_lease
Create Date: 2026-07-31

VALIDATE phase. Run ONLY after the operational Backfill/reconciliation has truly
resolved every legacy violation (an exception queue is NOT resolution). VALIDATE
proves the historical rows also satisfy the already-enforced future rule; it takes
a lighter lock than a fresh validating CHECK and does not re-scan enforced rows.

This is deliberately a SEPARATE revision from Expand: the phases are gated by
deployment, data, Writer-protocol, and observation evidence — not merely to avoid
one long transaction. No Backfill loop lives here.
"""
from alembic import op

revision = "0003_validate_lease"
down_revision = "0002_expand_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fails if any legacy row still violates the rule -> that is the signal that
    # Backfill/reconciliation is not actually complete. Do not "fix" by excluding
    # rows; resolve or reconcile the violation first.
    op.execute("ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_lease_triple_coherent")


def downgrade() -> None:
    # VALIDATE cannot be "un-validated"; the constraint simply returns to being
    # enforced-for-future-only in effect. There is no destructive reverse DDL.
    pass
