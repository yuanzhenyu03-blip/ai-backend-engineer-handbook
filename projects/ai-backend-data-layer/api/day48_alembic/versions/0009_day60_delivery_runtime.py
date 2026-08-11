"""Day60 — forward additive delivery/recovery runtime migration.

Revision ID: 0009_day60_delivery_runtime
Revises: 0008_day59_acceptance
Create Date: 2026-08-10

SCOPE (additive / expand only; NO destructive change to published revisions 0001-0008):
  * ``app.outbox_events`` gains NULLABLE Relay-claim fields so two Relays can claim a row
    with ``FOR UPDATE SKIP LOCKED`` + owner/token/expiry fencing WITHOUT holding a
    database lock across Broker I/O:
        - ``relay_owner``        (text)        which Relay currently holds the claim
        - ``relay_token``        (uuid)        fencing token for a guarded checkpoint
        - ``relay_claim_expiry`` (timestamptz) when an abandoned claim may be re-taken
  * a new ``app.job_repair_history`` table records IMMUTABLE recovery/repair facts. Its
    ``repair_id`` primary key is a DETERMINISTIC idempotency key
    (``repair:{job_id}:{release_version}:{reason}``) so a bounded early-ACK repair (or a
    recovery sweep) writes EXACTLY ONE new redispatch intent per repair, even under
    concurrent/duplicate repair.

WHY ADDITIVE: new nullable columns + a new table with no backfill and no NOT NULL in the
same step, so an API rollback is normally safer than an immediate Alembic downgrade. This
is an INSTRUCTIONAL local migration — it is NOT a production zero-downtime plan (a large
production table would add the columns and build any index CONCURRENTLY, outside a
transaction, with a separate human-reviewed step).

HONEST LIMITS:
  * These columns/table make Relay claim/fencing and idempotent repair REPRESENTABLE; the
    guarded transitions themselves are application control flow proven elsewhere.
  * Published historic revisions (0001-0008) are NOT modified. This revision only extends
    the single head 0008_day59_acceptance.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_day60_delivery_runtime"
down_revision = "0008_day59_acceptance"
branch_labels = None
depends_on = None

_SCHEMA = "app"


def upgrade() -> None:
    # 1) Relay-claim fields on the Outbox (all NULLABLE; no backfill).
    op.execute(
        f"ALTER TABLE {_SCHEMA}.outbox_events "
        f"ADD COLUMN IF NOT EXISTS relay_owner text, "
        f"ADD COLUMN IF NOT EXISTS relay_token uuid, "
        f"ADD COLUMN IF NOT EXISTS relay_claim_expiry timestamptz"
    )
    # 2) Immutable recovery/repair history with a deterministic idempotency key.
    op.execute(
        f"CREATE TABLE IF NOT EXISTS {_SCHEMA}.job_repair_history ("
        f"  repair_id       text        PRIMARY KEY, "
        f"  job_id          uuid        NOT NULL "
        f"                              REFERENCES {_SCHEMA}.jobs(job_id) "
        f"                              ON DELETE RESTRICT, "
        f"  repair_reason   text        NOT NULL, "
        f"  release_version text, "
        f"  created_at      timestamptz NOT NULL DEFAULT now()"
        f")"
    )


def downgrade() -> None:
    # Reverse of the additive expand; safe because nothing depends on these yet.
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.job_repair_history")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.outbox_events "
        f"DROP COLUMN IF EXISTS relay_claim_expiry, "
        f"DROP COLUMN IF EXISTS relay_token, "
        f"DROP COLUMN IF EXISTS relay_owner"
    )
