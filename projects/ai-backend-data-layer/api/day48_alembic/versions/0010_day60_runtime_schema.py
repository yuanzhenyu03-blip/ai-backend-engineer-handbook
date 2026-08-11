"""Day60 review fix — forward-additive schema the real Relay/Worker/recovery runtime needs.

Revision ID: 0010_day60_runtime_schema
Revises: 0009_day60_delivery_runtime
Create Date: 2026-08-11

SCOPE (additive / widening only; published revisions 0001-0009 are NOT modified):
  * ``app.jobs`` gains NULLABLE Worker-lease + conservative-marker fields the guarded
    claim/completion path uses:
        - ``lease_owner``                 (text)        the Worker currently holding authority
        - ``lease_expiry``                (timestamptz) when the lease is considered expired
        - ``provider_dispatch_started_at``(timestamptz) Day55 CONSERVATIVE external-call marker
        - ``release_version``             (text)        the release that produced the running state (repair filter)
  * ``app.jobs`` status CHECK is WIDENED to allow ``'pending_reconciliation'`` (a superset;
    no existing row becomes invalid), so an expired lease WITH external evidence has a
    durable terminal-of-recovery state instead of a blind retry.
  * ``app.job_repair_history`` gains a NULLABLE ``redispatch_outbox_event_id`` (uuid) that
    references the ONE ``app.outbox_events`` row a repair produced, plus a UNIQUE
    constraint. With the existing ``repair_id`` PRIMARY KEY this makes the Day60 repair
    invariant DATABASE-ENFORCED, not a comment:
        - ``repair_id`` PK          -> at most ONE repair fact per (job, release, reason)
        - UNIQUE(redispatch_...id)  -> at most ONE repair may claim a given redispatch intent
    so a concurrent/duplicate repair for the same ``repair_id`` produces exactly one repair
    fact and exactly one redispatch Outbox intent.

WHY A SEPARATE REVISION (not editing 0009): 0009 is already published on ``main``; an
applied revision is immutable. This is the correct forward-additive shape.

HONEST LIMITS: INSTRUCTIONAL local migration; NOT a production zero-downtime plan (a large
production table would add columns and any index CONCURRENTLY, outside a transaction, and
would roll a widened CHECK as a separate ``NOT VALID`` + ``VALIDATE`` step). It adds
nullable columns, widens a CHECK, and adds a UNIQUE constraint only — no backfill, no
NOT NULL.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_day60_runtime_schema"
down_revision = "0009_day60_delivery_runtime"
branch_labels = None
depends_on = None

_SCHEMA = "app"
_STATUS_CHECK = "jobs_status_allowed"
_REPAIR_UNIQUE = "job_repair_history_redispatch_outbox_unique"


def upgrade() -> None:
    # 1) Worker-lease + conservative marker fields (all NULLABLE; no backfill).
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs "
        f"ADD COLUMN IF NOT EXISTS lease_owner text, "
        f"ADD COLUMN IF NOT EXISTS lease_expiry timestamptz, "
        f"ADD COLUMN IF NOT EXISTS provider_dispatch_started_at timestamptz, "
        f"ADD COLUMN IF NOT EXISTS release_version text"
    )
    # 2) Widen the status CHECK to include pending_reconciliation (superset; safe).
    op.execute(f"ALTER TABLE {_SCHEMA}.jobs DROP CONSTRAINT IF EXISTS {_STATUS_CHECK}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs ADD CONSTRAINT {_STATUS_CHECK} "
        f"CHECK (job_status IN "
        f"('queued','running','succeeded','failed','cancelled','pending_reconciliation'))"
    )
    # 3) Repair -> redispatch Outbox link + one-intent UNIQUE.
    op.execute(
        f"ALTER TABLE {_SCHEMA}.job_repair_history "
        f"ADD COLUMN IF NOT EXISTS redispatch_outbox_event_id uuid "
        f"REFERENCES {_SCHEMA}.outbox_events(outbox_event_id) ON DELETE RESTRICT"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.job_repair_history "
        f"ADD CONSTRAINT {_REPAIR_UNIQUE} UNIQUE (redispatch_outbox_event_id)"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {_SCHEMA}.job_repair_history DROP CONSTRAINT IF EXISTS {_REPAIR_UNIQUE}"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.job_repair_history "
        f"DROP COLUMN IF EXISTS redispatch_outbox_event_id"
    )
    # Restore the pre-0010 status CHECK (drop the widened one, re-add the 0003 set).
    op.execute(f"ALTER TABLE {_SCHEMA}.jobs DROP CONSTRAINT IF EXISTS {_STATUS_CHECK}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs ADD CONSTRAINT {_STATUS_CHECK} "
        f"CHECK (job_status IN ('queued','running','succeeded','failed','cancelled'))"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs "
        f"DROP COLUMN IF EXISTS release_version, "
        f"DROP COLUMN IF EXISTS provider_dispatch_started_at, "
        f"DROP COLUMN IF EXISTS lease_expiry, "
        f"DROP COLUMN IF EXISTS lease_owner"
    )
