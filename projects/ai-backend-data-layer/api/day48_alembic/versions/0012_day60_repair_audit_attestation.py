"""Day60 review round 3 — persist the repair incident window + operator attestation.

Revision ID: 0012_day60_repair_audit_attestation
Revises: 0011_day60_lease_realign
Create Date: 2026-08-11

This IS additive/expand-only (unlike 0011, which was a corrective DROP): it adds NULLABLE
audit columns to ``app.job_repair_history`` so an early-ACK repair records the operator's
bounded-eligibility decision as durable, reviewable fact rather than a transient argument:

    incident_start                          timestamptz  -- operator-supplied incident window start
    incident_end                            timestamptz  -- operator-supplied incident window end
    no_conflict_attested                    boolean      -- caller attestation (schema cannot verify)
    deadline_contract_budget_valid_attested boolean      -- caller attestation (schema cannot verify)

Nullable because pre-existing repair rows (if any) had no attestation captured; the
repository never fabricates a historical attestation. New repairs write all four columns in
the SAME repair transaction as ``repair_id`` / ``job_id`` / ``release_version`` and the
linked ``redispatch_outbox_event_id``.

HONEST LIMITS: instructional local migration; NOT a production zero-downtime plan (a large
production table would add the columns CONCURRENTLY / in a separate reviewed step).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_day60_repair_audit_attestation"
down_revision = "0011_day60_lease_realign"
branch_labels = None
depends_on = None

_SCHEMA = "app"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {_SCHEMA}.job_repair_history "
        f"ADD COLUMN IF NOT EXISTS incident_start timestamptz, "
        f"ADD COLUMN IF NOT EXISTS incident_end timestamptz, "
        f"ADD COLUMN IF NOT EXISTS no_conflict_attested boolean, "
        f"ADD COLUMN IF NOT EXISTS deadline_contract_budget_valid_attested boolean"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {_SCHEMA}.job_repair_history "
        f"DROP COLUMN IF EXISTS deadline_contract_budget_valid_attested, "
        f"DROP COLUMN IF EXISTS no_conflict_attested, "
        f"DROP COLUMN IF EXISTS incident_end, "
        f"DROP COLUMN IF EXISTS incident_start"
    )
