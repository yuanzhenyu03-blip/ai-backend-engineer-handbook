"""Day46 — SQLAlchemy 2.0 mapping for the Day42 durable data model.

This is a FAITHFUL, executable representation of the EXISTING PostgreSQL durable
contract defined by the Day42 raw SQL (``sql/001_create_jobs.sql`` +
``sql/003_relational_modeling_and_data_integrity.sql``). It does NOT redesign the
schema and it is NOT a new schema authority: PostgreSQL remains the durable
authority; Day46 only maps it, Day47 drives it transactionally, Day48 evolves it.

Scope and honesty:
    * Mapped (Day46 scope): Job, JobAttempt, JobEvent, OutboxEvent, UploadSession,
      ResultArtifact, plus a MINIMAL Tenant support stub required solely to
      preserve the existing tenant foreign keys and candidate keys.
    * NOT mapped (explicit, stated limitation, NOT a half-built relationship):
      ``app.documents`` and the ``app.job_documents`` junction. The Job's
      ``jobs_tenant_id_unique`` candidate key (used by the out-of-scope
      job_documents composite FK) is still preserved as a faithful Job fact.
    * NO native enum change (status stays TEXT + named CHECK — an enum change is
      Day48 migration work). NO cascade delete (Day42 requires ON DELETE
      RESTRICT). ``relationship()`` is navigation only, NOT durable integrity.
    * NO Engine, AsyncSession, transaction, repository, or unit of work is created
      here (Day47). NO Alembic/migration (Day48). Pydantic public models and these
      ORM persistence models remain SEPARATE and are never merged.
    * ``Base.metadata.create_all()`` success would NOT prove compatibility with the
      existing schema; the tests only assert declared mapping STRUCTURE (static
      metadata). Real PostgreSQL runtime behavior is NOT RUN here.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# The existing durable schema lives in the PostgreSQL "app" schema (Day42). Every
# mapped table inherits it, so nothing depends on a session search_path.
APP_SCHEMA = "app"


class Base(DeclarativeBase):
    metadata = MetaData(schema=APP_SCHEMA)


# Reusable column type shorthands that match the Day42 PostgreSQL types exactly.
_UUID = UUID(as_uuid=True)
_TSTZ = TIMESTAMP(timezone=True)


# ---------------------------------------------------------------------------
# Tenant — MINIMAL support stub (not a full aggregate/relationship).
# Present only so the existing tenant FKs and candidate keys resolve; Day46 does
# NOT model tenant ownership behavior or navigation.
# ---------------------------------------------------------------------------
class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_slug: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("tenant_slug", name="tenants_slug_unique"),
    )


# ---------------------------------------------------------------------------
# UploadSession — pre-Document lifecycle; stores an Object Storage REFERENCE and
# lifecycle metadata only (never large bytes, signed URLs, or credentials).
# ---------------------------------------------------------------------------
class UploadSession(Base):
    __tablename__ = "upload_sessions"

    upload_session_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        ForeignKey("app.tenants.tenant_id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'initiated'")
    )
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime.datetime | None] = mapped_column(_TSTZ, nullable=True)

    __table_args__ = (
        # Candidate key that keeps tenant-aware composite references available.
        UniqueConstraint(
            "tenant_id", "upload_session_id", name="upload_sessions_tenant_id_unique"
        ),
        CheckConstraint(
            "session_status IN ('initiated', 'uploading', 'verified', 'failed', 'expired')",
            name="upload_sessions_status_allowed",
        ),
    )


# ---------------------------------------------------------------------------
# Job — the durable business fact. Preserves the Day29 columns plus the Day31
# ownership/identity/legal-state additions.
# ---------------------------------------------------------------------------
class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    provider_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(_TSTZ, nullable=True)
    # Nullable at the column level; the jobs_succeeded_has_finished_at CHECK below
    # is what actually enforces "succeeded implies a finish time" — Optional Python
    # typing and nullable=True do NOT enforce that conditional business state.
    finished_at: Mapped[datetime.datetime | None] = mapped_column(_TSTZ, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Legacy single-artifact pointer (Day29). The normalized owner is
    # ResultArtifact via JobAttempt; this column is preserved (dropping a column
    # apps still read is Day48 work), not re-used as the artifact authority.
    result_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        ForeignKey("app.tenants.tenant_id", ondelete="RESTRICT", name="jobs_tenant_fk"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        # Business key: one client request per tenant creates only ONE Job.
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="jobs_tenant_idempotency_unique"
        ),
        # Candidate key for tenant-aware composite FKs (used by out-of-scope
        # job_documents); preserved as a faithful Job fact.
        UniqueConstraint("tenant_id", "job_id", name="jobs_tenant_id_unique"),
        CheckConstraint(
            "job_status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="jobs_status_allowed",
        ),
        CheckConstraint("attempt_count >= 0", name="jobs_attempt_count_non_negative"),
        CheckConstraint(
            "job_status <> 'succeeded' OR finished_at IS NOT NULL",
            name="jobs_succeeded_has_finished_at",
        ),
    )

    # Navigation only (NOT integrity enforcement, NOT cascade delete). Day42's
    # ON DELETE RESTRICT stays the deletion policy; these relationships never use
    # cascade="all, delete-orphan". passive_deletes="all" tells the ORM to emit NO
    # pre-delete UPDATE/DELETE on the children when a parent is deleted -- so it
    # never tries to NULL a child's NOT NULL foreign key first; PostgreSQL's
    # ON DELETE RESTRICT makes the final decision and rejects the parent delete.
    attempts: Mapped[list["JobAttempt"]] = relationship(
        back_populates="job", passive_deletes="all"
    )
    events: Mapped[list["JobEvent"]] = relationship(
        back_populates="job", passive_deletes="all"
    )
    outbox_events: Mapped[list["OutboxEvent"]] = relationship(
        back_populates="job", passive_deletes="all"
    )


# ---------------------------------------------------------------------------
# JobAttempt — one Job may call the Provider several times. Retry ordinal is
# scoped to the Job, NOT global and NOT tenant-scoped.
# ---------------------------------------------------------------------------
class JobAttempt(Base):
    __tablename__ = "job_attempts"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("app.jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(_TSTZ, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        # Retry ordinal is unique WITHIN one Job (not global, not tenant-scoped).
        UniqueConstraint(
            "job_id", "attempt_number", name="job_attempts_job_number_unique"
        ),
        # Candidate key so JobEvent can prove same-Job Attempt provenance.
        UniqueConstraint(
            "job_id", "attempt_id", name="job_attempts_job_attempt_unique"
        ),
        CheckConstraint("attempt_number > 0", name="job_attempts_number_positive"),
        CheckConstraint(
            "cost_micros IS NULL OR cost_micros >= 0",
            name="job_attempts_cost_non_negative",
        ),
    )

    job: Mapped["Job"] = relationship(back_populates="attempts")
    # passive_deletes="all": no pre-delete NULLing of ResultArtifact.attempt_id;
    # PostgreSQL ON DELETE RESTRICT decides and rejects the Attempt delete.
    result_artifacts: Mapped[list["ResultArtifact"]] = relationship(
        back_populates="attempt", passive_deletes="all"
    )


# ---------------------------------------------------------------------------
# JobEvent — append-oriented lifecycle history. A NULL attempt_id records a
# Job-level Event; a non-NULL attempt_id must belong to the SAME Job (composite
# FK). The plain job_id FK and the composite FK both exist (faithful to Day42).
# ---------------------------------------------------------------------------
class JobEvent(Base):
    __tablename__ = "job_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("app.jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(_UUID, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )
    # "metadata" is reserved by Declarative, so the Python attribute is
    # event_metadata while the actual column name stays "metadata" (faithful).
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        # Composite FK: a non-NULL Attempt provenance must belong to the SAME Job.
        # MATCH SIMPLE default -> a NULL attempt_id leaves the reference unenforced
        # (the intended "optional provenance" / Job-level event behavior).
        ForeignKeyConstraint(
            ["job_id", "attempt_id"],
            ["app.job_attempts.job_id", "app.job_attempts.attempt_id"],
            ondelete="RESTRICT",
            name="job_events_attempt_same_job_fk",
        ),
    )

    job: Mapped["Job"] = relationship(back_populates="events")


# ---------------------------------------------------------------------------
# OutboxEvent — PostgreSQL-owned durable publication INTENT. published_at IS NULL
# means the publish checkpoint is not recorded — NOT proof it was never sent
# (a crash between transport publish and checkpoint permits at-least-once
# redelivery). Day46 only maps it; the messaging design is later.
# ---------------------------------------------------------------------------
class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    outbox_event_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("app.jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )
    published_at: Mapped[datetime.datetime | None] = mapped_column(_TSTZ, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="outbox_events")


# ---------------------------------------------------------------------------
# ResultArtifact — stores attempt_id ONLY; job ownership is DERIVED through the
# Attempt (no duplicated job_id without a measured need + a constraint). Stores
# Object Storage references/metadata, not large bytes.
# ---------------------------------------------------------------------------
class ResultArtifact(Base):
    __tablename__ = "result_artifacts"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, server_default=text("gen_random_uuid()")
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        ForeignKey("app.job_attempts.attempt_id", ondelete="RESTRICT"),
        nullable=False,
    )
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        _TSTZ, nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "object_key", name="result_artifacts_attempt_key_unique"
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="result_artifacts_size_non_negative",
        ),
    )

    attempt: Mapped["JobAttempt"] = relationship(back_populates="result_artifacts")


# Stated, unimplemented Day46 mapping limitation (NOT a half-built relationship):
# the existing app.documents table and the app.job_documents junction are
# deliberately NOT mapped here. They are real Day42 schema; mapping them (and a
# Job.documents relationship) is future scope.
UNMAPPED_DAY42_TABLES = ("app.documents", "app.job_documents")
