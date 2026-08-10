"""Day59 — forward additive acceptance contract migration.

Revision ID: 0008_day59_acceptance
Revises: 0007_merge_reconciliation_polling
Create Date: 2026-08-10

SCOPE (additive / expand only; NO destructive change):
  * ``app.jobs.request_fingerprint``: a NULLABLE ``varchar(64)`` column holding a
    SHA-256 hex digest of the canonical acceptance request (tenant + idempotency key
    + normalized business input). Nullable so legacy rows created before Day59 stay
    valid; a CHECK enforces the SHA-256 SHAPE only for NON-NULL values.
  * a PARTIAL UNIQUE INDEX guaranteeing AT MOST ONE ``job.dispatch_requested`` Outbox
    intent per Job. Other Outbox event types are unconstrained by this index.

WHY ADDITIVE (expand/contract discipline from Day48): a new column is added NULLABLE
with no backfill and no NOT NULL in the same step, so an API rollback is normally
safer than an immediate Alembic downgrade. Enforcing NOT NULL, backfilling legacy
rows, or building this index CONCURRENTLY on a large production table are SEPARATE,
human-reviewed later steps — this local migration is NOT a production zero-downtime
plan and must not be described as one without further review.

HONEST LIMITS:
  * ``op.create_index(...)`` here is a plain (locking) index build suitable for a
    disposable local database. On a large production ``app.outbox_events`` it would be
    ``CREATE INDEX CONCURRENTLY`` outside a transaction, which is deliberately NOT done
    here.
  * The CHECK validates SHAPE (``^[0-9a-f]{64}$``), NOT that the digest was computed
    correctly; correctness is the application's acceptance-boundary responsibility.
  * Published historic revisions (0001–0007) are NOT modified. This revision only
    extends the single head 0007.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_day59_acceptance"
down_revision = "0007_merge_reconciliation_polling"
branch_labels = None
depends_on = None

_SCHEMA = "app"
_FINGERPRINT_CHECK = "jobs_request_fingerprint_sha256_shape"
_DISPATCH_UNIQUE_INDEX = "outbox_events_one_dispatch_requested_per_job"
_DISPATCH_EVENT_TYPE = "job.dispatch_requested"


def upgrade() -> None:
    # 1) Additive NULLABLE column — no backfill, no NOT NULL (expand step only).
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs "
        f"ADD COLUMN IF NOT EXISTS request_fingerprint varchar(64)"
    )
    # 2) SHA-256 SHAPE check for NON-NULL values only (legacy NULLs stay valid).
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs "
        f"ADD CONSTRAINT {_FINGERPRINT_CHECK} "
        f"CHECK (request_fingerprint IS NULL "
        f"OR request_fingerprint ~ '^[0-9a-f]{{64}}$')"
    )
    # 3) At most ONE 'job.dispatch_requested' Outbox intent per Job (partial unique).
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {_DISPATCH_UNIQUE_INDEX} "
        f"ON {_SCHEMA}.outbox_events (job_id) "
        f"WHERE event_type = '{_DISPATCH_EVENT_TYPE}'"
    )


def downgrade() -> None:
    # Reverse of the additive expand; safe because nothing depends on these yet.
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.{_DISPATCH_UNIQUE_INDEX}")
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs DROP CONSTRAINT IF EXISTS {_FINGERPRINT_CHECK}"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.jobs DROP COLUMN IF EXISTS request_fingerprint"
    )
