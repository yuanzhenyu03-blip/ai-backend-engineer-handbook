"""Expand: additive-only — nullable Lease columns + an INDEPENDENT reconciliation
queue table (no constraints on app.jobs).

Revision ID: 0002_expand_lease
Revises: 0001_baseline
Create Date: 2026-07-31

EXPAND phase of Day36's Expand -> Backfill -> Validate -> Switch -> Contract.

This revision is PURELY ADDITIVE: it ADDs nullable Lease columns to app.jobs with
NO fabricated default and NO constraint, and CREATEs a NEW, independent
reconciliation queue table. Both are compatibility-safe, so this is the OLD/NEW
code COMPATIBILITY WINDOW — while only this revision is applied an OLD Writer can
keep updating a legacy ``running`` Job that has a NULL Lease (no constraint yet
rejects such a write), and it simply ignores the new table.

The strict Lease constraints (triple coherence + jobs_running_requires_lease) are
a SEPARATE later revision (0003_add_lease_constraints), applied ONLY AFTER the new
code is deployed and tolerates NULL Lease and the OLD Writers are drained/isolated
— because ``CHECK ... NOT VALID`` protects EVERY future write regardless of the
Writer's binary version (see 0003).

WHY A SEPARATE RECONCILIATION TABLE (not a column on app.jobs):
    An unknown-ownership running Job cannot be "marked" on app.jobs, because after
    0003 the row is still ``running`` with a NULL Lease and any UPDATE to it is
    REJECTED by jobs_running_requires_lease (NOT VALID checks EVERY future write).
    Reconciliation TRIAGE must therefore live OUTSIDE the business row. This table
    records that a Job was routed for reconciliation WITHOUT changing app.jobs, so
    the Job remains a running-without-Lease row that STILL counts as unresolved and
    STILL blocks VALIDATE/Switch/Contract until it is truthfully resolved.
    Fabricating a Lease owner/token/expiry or a terminal status is forbidden.
"""
from alembic import op

revision = "0002_expand_lease"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, no default: NULL == no proved Lease ownership. NO constraint here —
    # this is the OLD/NEW compatibility window (old Writers can still write a
    # running-without-Lease row until 0003 tightens the rule).
    op.execute(
        "ALTER TABLE app.jobs "
        "ADD COLUMN lease_owner text, "
        "ADD COLUMN lease_token uuid, "
        "ADD COLUMN lease_expires_at timestamptz"
    )
    # Independent reconciliation queue (Day42 conventions: app schema, uuid PK, FK
    # ON DELETE RESTRICT, named constraints). Triage lives HERE, never on app.jobs.
    # UNIQUE(job_id) makes routing idempotent (INSERT ... ON CONFLICT DO NOTHING).
    # next_attempt_at / last_checked_at / check_attempts drive RECONCILIATION
    # POLLING with backoff (NOT Job retry, NOT Provider retry): a resolver that finds
    # no trusted evidence pushes next_attempt_at into the future so the SAME open
    # record is not re-selected in the current loop, which is what makes
    # run_reconciliation_resolution TERMINATE in real PostgreSQL. next_attempt_at
    # defaults to now() so a freshly routed record is immediately due once.
    op.execute(
        "CREATE TABLE app.job_lease_reconciliation ("
        "  reconciliation_id uuid        PRIMARY KEY DEFAULT gen_random_uuid(), "
        "  job_id            uuid        NOT NULL "
        "                                REFERENCES app.jobs(job_id) ON DELETE RESTRICT, "
        "  reason            text        NOT NULL, "
        "  routed_at         timestamptz NOT NULL DEFAULT now(), "
        "  resolution_status text        NOT NULL DEFAULT 'open', "
        "  resolved_at       timestamptz, "
        "  next_attempt_at   timestamptz NOT NULL DEFAULT now(), "
        "  last_checked_at   timestamptz, "
        "  check_attempts    integer     NOT NULL DEFAULT 0, "
        "  CONSTRAINT job_lease_reconciliation_job_unique UNIQUE (job_id), "
        "  CONSTRAINT job_lease_reconciliation_reason_allowed "
        "    CHECK (reason IN ('unknown_ownership')), "
        "  CONSTRAINT job_lease_reconciliation_status_allowed "
        "    CHECK (resolution_status IN ('open', 'resolved')), "
        "  CONSTRAINT job_lease_reconciliation_check_attempts_nonneg "
        "    CHECK (check_attempts >= 0)"
        ")"
    )


def downgrade() -> None:
    # Safe ONLY before any real Lease data or reconciliation triage exists. Once
    # real Lease/triage rows exist, DO NOT downgrade destructively — preserve
    # durable evidence and forward-fix + reconcile instead.
    op.execute("DROP TABLE IF EXISTS app.job_lease_reconciliation")
    op.execute(
        "ALTER TABLE app.jobs "
        "DROP COLUMN IF EXISTS lease_expires_at, "
        "DROP COLUMN IF EXISTS lease_token, "
        "DROP COLUMN IF EXISTS lease_owner"
    )
