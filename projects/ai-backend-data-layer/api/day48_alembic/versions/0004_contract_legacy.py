"""Contract: destructive removal of legacy compatibility (heavily gated).

Revision ID: 0004_contract_legacy
Revises: 0003_validate_lease
Create Date: 2026-07-31

CONTRACT is destructive and is the LAST phase. Preconditions that MUST hold before
applying this revision (Alembic cannot check them — an operator must):
  * Validate (0003) succeeded and historical rows are proven compliant.
  * Switch is complete: EVERY Writer (Workers, recovery, admin/scripts,
    completion/failure paths) uses the Lease-token protocol and the old path can
    no longer write.
  * Evidence + an observation period have passed with healthy correlation/error
    signals.
Once real Lease data or Provider side effects exist, prefer FORWARD-FIX +
reconciliation over a destructive downgrade.

Concrete contraction: drop the Day42 legacy single-artifact pointer
``app.jobs.result_object_key`` (superseded by the normalized ``result_artifacts``
table; Day42/003 deliberately did NOT drop it, deferring to this safe sequence).
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_contract_legacy"
down_revision = "0003_validate_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Destructive: only run after Validate + Switch + evidence + observation.
    op.drop_column("jobs", "result_object_key", schema="app")


def downgrade() -> None:
    # Re-adds the column as NULLABLE (data already dropped is NOT restored — a
    # downgrade is NOT a time machine). If real reads depended on it, forward-fix
    # and reconcile rather than pretending the old bytes returned.
    op.add_column("jobs", sa.Column("result_object_key", sa.Text(), nullable=True), schema="app")
