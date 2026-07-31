"""Expand: add nullable Lease compatibility columns + CHECK ... NOT VALID.

Revision ID: 0002_expand_lease
Revises: 0001_baseline
Create Date: 2026-07-31

EXPAND phase of Day36's Expand -> Backfill -> Validate -> Switch -> Contract.

Adds the Lease ownership columns as NULLABLE with NO fabricated default: a NULL
honestly means "no PROVED Lease ownership". Do NOT generate tokens for queued,
terminal, or unprovable running Jobs here — that fabrication is forbidden, and
Backfill (a SEPARATE operational step, NOT this upgrade) fills only running Jobs
with trusted ownership evidence.

The coherence rule is added as ``CHECK ... NOT VALID`` so it protects EVERY future
INSERT/UPDATE immediately while temporarily tolerating legacy rows. It is NOT
validated here; ``VALIDATE CONSTRAINT`` is the separate 0003 revision, run only
after all real violations are resolved. This upgrade runs no Backfill loop, calls
no Provider, and holds no long transaction.
"""
from alembic import op

revision = "0002_expand_lease"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, no default: NULL == no proved Lease ownership.
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD COLUMN lease_owner text, "
        "ADD COLUMN lease_token uuid, "
        "ADD COLUMN lease_expires_at timestamptz"
    )
    # Future-write protection: an all-or-nothing Lease triple. NOT VALID protects
    # new INSERT/UPDATE now while tolerating legacy rows until 0003 VALIDATE.
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD CONSTRAINT jobs_lease_triple_coherent "
        "CHECK ( "
        "  (lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) "
        "  OR "
        "  (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
        ") NOT VALID"
    )


def downgrade() -> None:
    # Safe ONLY before any real Lease data or Provider side effects exist. Once
    # real Lease tokens/Provider effects exist, DO NOT downgrade destructively —
    # preserve durable evidence and forward-fix + reconcile instead.
    op.execute("ALTER TABLE app.jobs DROP CONSTRAINT IF EXISTS jobs_lease_triple_coherent")
    op.execute(
        "ALTER TABLE app.jobs "
        "DROP COLUMN IF EXISTS lease_expires_at, "
        "DROP COLUMN IF EXISTS lease_token, "
        "DROP COLUMN IF EXISTS lease_owner"
    )
