"""Day46 — STATIC metadata contract tests for the SQLAlchemy 2.0 mapping.

These prove the DECLARED mapping STRUCTURE faithfully matches the Day42 durable
schema (table identity in the app schema, typed columns, server-side defaults,
named UNIQUE/CHECK/FK constraints, ON DELETE RESTRICT, same-Job composite
provenance, no cascade delete, no Pydantic/public-model merge, and the stated
Document/job_documents limitation). They do NOT connect to a database and do NOT
call create_all(); real PostgreSQL runtime behavior is a separate, NOT-RUN,
concern (see the lesson/design validation matrix). Executed with pytest.
"""

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from day46_orm_mapping import (
    Base,
    Job,
    JobAttempt,
    JobEvent,
    OutboxEvent,
    ResultArtifact,
    Tenant,
    UploadSession,
    UNMAPPED_DAY42_TABLES,
)

md = Base.metadata


def table(name):
    return md.tables[f"app.{name}"]


def constraint_names(name):
    return {c.name for c in table(name).constraints if c.name}


def get_constraint(tname, cname):
    for c in table(tname).constraints:
        if c.name == cname:
            return c
    raise AssertionError(f"missing constraint {cname} on {tname}")


# 1. Every mapped table lives in the PostgreSQL "app" schema (Day42 identity).
def test_all_tables_in_app_schema():
    assert md.tables, "no tables mapped"
    for key, t in md.tables.items():
        assert t.schema == "app", f"{key} is not in the app schema"


# 2. Exactly the Day46-scope tables (+ Tenant stub) are mapped; documents and
#    job_documents are the stated, deliberate limitation and must be ABSENT.
def test_scope_tables_present_and_limitation_absent():
    assert set(md.tables) == {
        "app.tenants",
        "app.upload_sessions",
        "app.jobs",
        "app.job_attempts",
        "app.job_events",
        "app.outbox_events",
        "app.result_artifacts",
    }
    assert "app.documents" not in md.tables
    assert "app.job_documents" not in md.tables
    assert UNMAPPED_DAY42_TABLES == ("app.documents", "app.job_documents")


# 3. Job column identity, types and nullability match Day42.
def test_job_columns_types_and_nullability():
    j = table("jobs")
    cols = j.columns
    assert isinstance(cols["job_id"].type, UUID) and cols["job_id"].primary_key
    assert isinstance(cols["job_status"].type, Text) and not cols["job_status"].nullable
    assert isinstance(cols["attempt_count"].type, Integer)
    assert isinstance(cols["cancel_requested"].type, Boolean)
    assert isinstance(cols["provider_metadata"].type, JSONB)
    assert isinstance(cols["created_at"].type, TIMESTAMP) and cols["created_at"].type.timezone
    assert cols["started_at"].nullable and cols["finished_at"].nullable
    assert cols["tenant_id"].nullable is False
    assert cols["idempotency_key"].nullable is False
    # Legacy single-artifact pointer preserved (nullable), not dropped.
    assert "result_object_key" in cols and cols["result_object_key"].nullable


# 4. Status stays TEXT + CHECK, NOT a native enum (an enum change is Day48).
def test_job_status_is_text_not_enum():
    status = table("jobs").columns["job_status"]
    assert type(status.type) is Text  # exactly Text, not Enum
    chk = get_constraint("jobs", "jobs_status_allowed")
    assert isinstance(chk, CheckConstraint)
    for legal in ("queued", "running", "succeeded", "failed", "cancelled"):
        assert legal in str(chk.sqltext)


# 5. Database-generated values are server-side defaults (not app-side).
def test_job_server_side_defaults():
    cols = table("jobs").columns
    assert "gen_random_uuid()" in str(cols["job_id"].server_default.arg)
    assert "now()" in str(cols["created_at"].server_default.arg)
    assert "queued" in str(cols["job_status"].server_default.arg)
    assert "0" in str(cols["attempt_count"].server_default.arg)
    assert "false" in str(cols["cancel_requested"].server_default.arg)
    assert "jsonb" in str(cols["provider_metadata"].server_default.arg)


# 6. Job named constraints are preserved exactly.
def test_job_named_constraints():
    names = constraint_names("jobs")
    for expected in (
        "jobs_tenant_idempotency_unique",
        "jobs_tenant_id_unique",
        "jobs_status_allowed",
        "jobs_attempt_count_non_negative",
        "jobs_succeeded_has_finished_at",
    ):
        assert expected in names, f"missing {expected}"
    uq = get_constraint("jobs", "jobs_tenant_idempotency_unique")
    assert isinstance(uq, UniqueConstraint)
    assert [c.name for c in uq.columns] == ["tenant_id", "idempotency_key"]


# 7. The conditional business invariant is a CHECK (Optional typing does NOT
#    enforce "succeeded implies finished_at").
def test_job_succeeded_requires_finished_at_check():
    chk = get_constraint("jobs", "jobs_succeeded_has_finished_at")
    assert isinstance(chk, CheckConstraint)
    txt = str(chk.sqltext)
    assert "succeeded" in txt and "finished_at" in txt
    # And the column itself is still nullable (the CHECK is the enforcement).
    assert table("jobs").columns["finished_at"].nullable is True


# 8. Job.tenant_id is a named FK to tenants with ON DELETE RESTRICT.
def test_job_tenant_fk_restrict():
    fk = list(table("jobs").columns["tenant_id"].foreign_keys)[0]
    assert fk.column.table.name == "tenants"
    assert fk.ondelete == "RESTRICT"
    assert fk.constraint.name == "jobs_tenant_fk"


# 9. Attempt retry ordinal is scoped to the Job (not global, not tenant-scoped).
def test_attempt_scoped_uniqueness_and_checks():
    names = constraint_names("job_attempts")
    assert "job_attempts_job_number_unique" in names
    assert "job_attempts_job_attempt_unique" in names
    uq = get_constraint("job_attempts", "job_attempts_job_number_unique")
    assert [c.name for c in uq.columns] == ["job_id", "attempt_number"]
    # attempt_number must NOT be a primary key; attempt_id is the identity.
    assert table("job_attempts").columns["attempt_id"].primary_key
    assert not table("job_attempts").columns["attempt_number"].primary_key
    assert "job_attempts_number_positive" in names
    assert "job_attempts_cost_non_negative" in names


# 10. JobEvent proves same-Job Attempt provenance via a composite FK; attempt_id
#     is nullable (a NULL records a Job-level Event).
def test_job_event_composite_provenance_fk():
    fkcs = [c for c in table("job_events").constraints if isinstance(c, ForeignKeyConstraint)]
    composite = [c for c in fkcs if c.name == "job_events_attempt_same_job_fk"]
    assert composite, "missing composite provenance FK"
    fk = composite[0]
    assert list(fk.column_keys) == ["job_id", "attempt_id"]
    assert fk.ondelete == "RESTRICT"
    targets = {e.target_fullname for e in fk.elements}
    assert targets == {"app.job_attempts.job_id", "app.job_attempts.attempt_id"}
    assert table("job_events").columns["attempt_id"].nullable is True


# 11. The job_events "metadata" column keeps its DB name while the Python
#     attribute is renamed (Declarative reserves `metadata`).
def test_job_event_metadata_column_name():
    assert "metadata" in table("job_events").columns
    assert JobEvent.event_metadata.key == "event_metadata"
    assert JobEvent.event_metadata.property.columns[0].name == "metadata"


# 12. Outbox published_at is nullable (checkpoint-not-recorded, not never-sent).
def test_outbox_published_at_nullable():
    assert table("outbox_events").columns["published_at"].nullable is True
    assert isinstance(table("outbox_events").columns["payload"].type, JSONB)


# 13. ResultArtifact stores attempt_id ONLY (no denormalized job_id column).
def test_result_artifact_owns_via_attempt_only():
    cols = table("result_artifacts").columns
    assert "attempt_id" in cols
    assert "job_id" not in cols  # ownership derived through the Attempt
    fk = list(cols["attempt_id"].foreign_keys)[0]
    assert fk.column.table.name == "job_attempts"
    assert fk.ondelete == "RESTRICT"
    assert "result_artifacts_attempt_key_unique" in constraint_names("result_artifacts")


# 14. UploadSession maps its own constraints and stores a reference only.
def test_upload_session_constraints():
    names = constraint_names("upload_sessions")
    assert "upload_sessions_tenant_id_unique" in names
    assert "upload_sessions_status_allowed" in names
    assert table("upload_sessions").columns["object_key"].nullable is False


# 15. EVERY foreign key uses ON DELETE RESTRICT — no CASCADE / SET NULL anywhere
#     (audit/recovery evidence must not be erased by object-graph cleanup).
def test_all_foreign_keys_are_restrict():
    for tname, t in md.tables.items():
        for fk in t.foreign_keys:
            assert fk.ondelete == "RESTRICT", f"{tname}.{fk.parent.name} ondelete={fk.ondelete}"


# 16. No relationship uses a destructive cascade (no delete / delete-orphan);
#     relationships are navigation only.
def test_relationships_have_no_destructive_cascade():
    for cls in (Job, JobAttempt, JobEvent, OutboxEvent, ResultArtifact, UploadSession, Tenant):
        for rel in inspect(cls).relationships:
            casc = rel.cascade
            assert not casc.delete_orphan, f"{cls.__name__}.{rel.key} has delete-orphan"
            assert not casc.delete, f"{cls.__name__}.{rel.key} has delete cascade"


# 17. Typed declarative mapping: columns are ORM-managed Mapped attributes
#     (Mapped[...] = mapped_column(...)), not plain annotations.
def test_typed_declarative_mapping():
    mapper = inspect(Job)
    assert "job_id" in mapper.columns
    assert isinstance(Job.job_id.type, UUID)
    # A representative nullable timestamp is mapped as Mapped[datetime | None].
    assert JobAttempt.finished_at.property.columns[0].nullable is True


# 18. Pydantic public models and these ORM models remain SEPARATE (no merge/
#     inheritance): the ORM Base must not subclass a Pydantic BaseModel, and the
#     Day44 public models are not imported into the persistence layer.
def test_orm_and_pydantic_models_are_separate():
    import day46_orm_mapping as m
    # The ORM Base is a SQLAlchemy DeclarativeBase, unrelated to Pydantic.
    assert "pydantic" not in [b.__module__.split(".")[0] for b in Job.__mro__]
    assert not hasattr(Job, "model_validate")  # not a Pydantic model
    src = open(m.__file__).read()
    assert "day44_pydantic_contracts" not in src  # persistence never imports the public models


# 19. Minimal Tenant stub: identity + slug + created_at only (no navigation
#     relationships), present solely to preserve the tenant FKs/candidate keys.
def test_tenant_is_minimal_support_stub():
    assert set(table("tenants").columns.keys()) == {"tenant_id", "tenant_slug", "created_at"}
    assert not list(inspect(Tenant).relationships)
    assert "tenants_slug_unique" in constraint_names("tenants")
