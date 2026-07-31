"""Day42 baseline (stamp target).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-31

This baseline is intentionally a STAMP TARGET, not a schema re-creation. The
Day42 durable schema is created by the independent raw SQL (``sql/001_create_jobs.sql``
+ ``sql/003_relational_modeling_and_data_integrity.sql``), which remains the
authority. ``alembic stamp 0001_baseline`` writes ``alembic_version`` and performs
NO DDL — do this ONLY after an existing database is independently proven to match
the Day42 baseline exactly. A new/empty database applies the Day42 raw SQL first,
is stamped to this baseline, then upgrades to 0002+ (the Lease evolution). The
``alembic_version`` row records a version DECLARATION, not a schema proof.
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stamp target: no DDL. The Day42 raw SQL is the schema authority.
    pass


def downgrade() -> None:
    # No-op: this baseline created nothing to remove.
    pass
