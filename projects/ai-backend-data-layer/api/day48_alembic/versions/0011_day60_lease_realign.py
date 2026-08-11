"""Day60 review round 2 — realign the runtime to the EXISTING lease triple.

Revision ID: 0011_day60_lease_realign
Revises: 0010_day60_runtime_schema
Create Date: 2026-08-11

WHY: revision 0010 mistakenly added a PARALLEL ``app.jobs.lease_expiry`` column. The
authoritative Worker lease is the EXISTING Day48 triple added by 0002_expand_lease and
constrained by 0003_add_lease_constraints:

    lease_owner       text
    lease_token       uuid
    lease_expires_at  timestamptz

    CONSTRAINT jobs_lease_triple_coherent    -- all three NULL or all three NOT NULL
    CONSTRAINT jobs_running_requires_lease   -- a 'running' Job MUST carry the full triple

A parallel ``lease_expiry`` cannot satisfy those CHECKs and would let two "lease" notions
drift. This forward-additive revision DROPS the parallel column so the real runtime uses
ONLY the existing triple. It does NOT edit any published revision (0001-0010 stay
immutable) and it is safe because no data was ever written to ``lease_expiry`` (the Day60
runtime was never executed and this column is brand new).

The 0010 additions that do NOT conflict are KEPT: ``provider_dispatch_started_at``,
``release_version``, the widened status CHECK (adds ``pending_reconciliation``), and the
``job_repair_history.redispatch_outbox_event_id`` UNIQUE link.

HONEST LIMITS: instructional local migration, NOT a production zero-downtime plan.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_day60_lease_realign"
down_revision = "0010_day60_runtime_schema"
branch_labels = None
depends_on = None

_SCHEMA = "app"


def upgrade() -> None:
    # Remove the parallel lease column 0010 added; the authoritative lease is the
    # existing lease_owner/lease_token/lease_expires_at triple (0002/0003).
    op.execute(f"ALTER TABLE {_SCHEMA}.jobs DROP COLUMN IF EXISTS lease_expiry")


def downgrade() -> None:
    # Re-add the (unused) parallel column to reverse this revision only.
    op.execute(f"ALTER TABLE {_SCHEMA}.jobs ADD COLUMN IF NOT EXISTS lease_expiry timestamptz")
