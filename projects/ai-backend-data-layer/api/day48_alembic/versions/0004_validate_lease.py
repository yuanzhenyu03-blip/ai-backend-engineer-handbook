"""Validate: VALIDATE CONSTRAINT (separately gated, after Backfill/reconciliation).

Revision ID: 0004_validate_lease
Revises: 0003_add_lease_constraints
Create Date: 2026-07-31

VALIDATE phase. Run ONLY after the operational Backfill/reconciliation has truly
resolved every legacy violation (an exception queue is NOT resolution). VALIDATE
proves the historical rows also satisfy BOTH already-enforced future rules —
jobs_lease_triple_coherent AND the Day36 core jobs_running_requires_lease — with a
lighter lock than a fresh validating CHECK. It FAILS while any running-without-Lease
row remains (reconcile-marked rows included).

This is deliberately a SEPARATE revision from Expand: the phases are gated by
deployment, data, Writer-protocol, and observation evidence — not merely to avoid
one long transaction. No Backfill loop lives here.
"""
from alembic import op

revision = "0004_validate_lease"
down_revision = "0003_add_lease_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fails if any legacy row still violates the rule -> that is the signal that
    # Backfill/reconciliation is not actually complete. Do not "fix" by excluding
    # rows; resolve or reconcile the violation first.
    op.execute("ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_lease_triple_coherent")
    # Day36 CORE: prove EVERY historical running row carries a complete Lease. This
    # FAILS while any running-without-Lease row remains — including reconcile-marked
    # rows (triage is not resolution), so it cannot pass until each is truthfully
    # resolved (a trusted Lease backfill or an audited real state recovery).
    op.execute("ALTER TABLE app.jobs VALIDATE CONSTRAINT jobs_running_requires_lease")


def downgrade() -> None:
    # VALIDATE cannot be "un-validated"; the constraint simply returns to being
    # enforced-for-future-only in effect. There is no destructive reverse DDL.
    pass
