# Day46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model (Design)

Executable, FAITHFUL mapping of the existing Day42 PostgreSQL durable contract
into SQLAlchemy 2.0 typed declarative models. Runnable code:
[`day46_orm_mapping.py`](day46_orm_mapping.py); executed static tests:
[`test_day46_orm_mapping.py`](test_day46_orm_mapping.py); pinned deps:
[`requirements-day46.txt`](requirements-day46.txt); source of truth:
[`../sql/001_create_jobs.sql`](../sql/001_create_jobs.sql) +
[`../sql/003_relational_modeling_and_data_integrity.sql`](../sql/003_relational_modeling_and_data_integrity.sql).

> Scope honesty: the ORM is an executable REPRESENTATION of the existing
> PostgreSQL contract, **not** a new schema authority. PostgreSQL stays the
> durable authority; **Day46 maps it, Day47 drives it transactionally, Day48
> evolves it safely.** No Engine/AsyncSession/transaction/repository/UoW (Day47),
> no Alembic/migration (Day48), no native-enum change, no Celery/Provider/Object-
> Storage runtime, and no public API endpoint. Pydantic public models and these
> ORM models remain SEPARATE.

---

## 1. Mental model: mapping, not authority

```text
Day42 raw SQL (durable authority)  --faithful map-->  SQLAlchemy 2.0 declarative models
PostgreSQL enforces integrity (PK/UNIQUE/CHECK/FK/RESTRICT); the ORM DECLARES the same facts.
create_all() success != schema compatibility. relationship() = navigation, NOT integrity.
Day46 maps -> Day47 drives (sessions/tx/repo/UoW) -> Day48 evolves (Alembic expand/backfill/validate/switch/contract).
```

---

## 2. Typed declarative mapping (SQLAlchemy 2.0)

```text
class Base(DeclarativeBase): metadata = MetaData(schema="app")   # exact existing "app" schema identity
Mapped[T] = mapped_column(...)   # Mapped[T] marks an ORM-managed typed attribute; mapped_column carries column
                                 # metadata. A plain annotation is NOT the same mapping.
Types map to Day42 exactly: UUID(as_uuid=True), Text, Integer, BigInteger, Boolean, TIMESTAMP(timezone=True), JSONB.
Server-generated values are SERVER-side defaults: gen_random_uuid(), now(), 'queued', 0, false, '{}'::jsonb.
```

---

## 3. Job — identity, ownership, legal states

```text
jobs: job_id uuid PK (gen_random_uuid) | job_status text NOT NULL 'queued' | attempt_count int NOT NULL 0
      cancel_requested bool NOT NULL false | provider_metadata jsonb NOT NULL '{}' | created_at tstz NOT NULL now()
      started_at tstz NULL | finished_at tstz NULL | error_message text NULL | result_object_key text NULL (legacy)
      tenant_id uuid NOT NULL (jobs_tenant_fk -> tenants, RESTRICT) | idempotency_key text NOT NULL
constraints (names preserved):
  jobs_tenant_idempotency_unique UNIQUE(tenant_id, idempotency_key)   # one client request per tenant = one Job
  jobs_tenant_id_unique          UNIQUE(tenant_id, job_id)            # candidate key (used by out-of-scope job_documents)
  jobs_status_allowed            CHECK status IN (queued,running,succeeded,failed,cancelled)   # TEXT+CHECK, NOT enum
  jobs_attempt_count_non_negative CHECK
  jobs_succeeded_has_finished_at CHECK (status <> 'succeeded' OR finished_at IS NOT NULL)
```

`Mapped[datetime | None]` + `nullable=True` describe a nullable COLUMN; they do
**not** replace the CHECK — Optional Python/DB state does not enforce the
conditional business rule. Status stays **TEXT + named CHECK**; a native enum
would be schema evolution (Day48).

---

## 4. JobAttempt / JobEvent — scoped identity and same-Job provenance

```text
job_attempts: attempt_id uuid PK | job_id uuid NOT NULL (-> jobs RESTRICT) | attempt_number int NOT NULL
  job_attempts_job_number_unique  UNIQUE(job_id, attempt_number)   # retry ordinal scoped to the JOB (not global, not tenant)
  job_attempts_job_attempt_unique UNIQUE(job_id, attempt_id)       # candidate key for same-Job provenance
  job_attempts_number_positive CHECK(attempt_number > 0); job_attempts_cost_non_negative CHECK
job_events: event_id uuid PK | job_id uuid NOT NULL (-> jobs RESTRICT) | attempt_id uuid NULL | ... | "metadata" jsonb
  job_events_attempt_same_job_fk FOREIGN KEY (job_id, attempt_id) -> job_attempts(job_id, attempt_id) RESTRICT
```

The COMPOSITE FK proves a non-NULL Attempt belongs to the SAME Job; a NULL
`attempt_id` (MATCH SIMPLE) leaves it unenforced — the intended Job-level Event.
A single Attempt FK would permit a valid Job plus a valid-but-unrelated Attempt.
The composite FK protects provenance; it does **not** limit an Attempt to one
Event. (`metadata` is reserved by Declarative, so the Python attribute is
`event_metadata` while the column name stays `"metadata"`.)

---

## 5. Outbox / ResultArtifact / UploadSession boundaries

```text
outbox_events: PostgreSQL-owned durable dispatch INTENT. published_at NULL = checkpoint NOT recorded,
  NOT proof it was never sent (crash between publish and checkpoint -> at-least-once redelivery). Day46 only maps it.
result_artifacts: stores attempt_id ONLY (job ownership DERIVED via Attempt); NO denormalized job_id without a
  measured need + a constraint preventing contradictory ownership. Object Storage references/metadata, not bytes.
  result_artifacts_attempt_key_unique UNIQUE(attempt_id, object_key); size CHECK.
upload_sessions: Object Storage reference + lifecycle metadata only (never large bytes, signed URLs, credentials).
  upload_sessions_tenant_id_unique UNIQUE(tenant_id, upload_session_id); upload_sessions_status_allowed CHECK.
```

---

## 6. Retention, boundaries, and scope limits

```text
ON DELETE RESTRICT everywhere (Attempts/Events/Outbox/Artifacts carry audit/recovery value): NO cascade,
  NO delete-orphan on any relationship(); relationship() is navigation, not durable integrity enforcement.
Pydantic public models != ORM persistence models: never merged/inherited (no tenant/audit/persistence leak).
Tenant: MINIMAL support stub (identity + slug + created_at) ONLY to preserve the tenant FKs/candidate keys —
  tenant_id is an actual mapped column/FK, not a "derived" field; no full Tenant aggregate/relationship.
Stated limitation: app.documents + app.job_documents are NOT mapped (real Day42 schema, future scope), NOT a
  half-built Job.documents relationship.
NO Engine/AsyncSession/transaction/repository/UoW here (Day47 owns Engine lifecycle: one Engine per process,
  one AsyncSession per request/Job unit of work). Mapping metadata needs no production connection.
```

---

## 7. Wrong-schema failure / reconciliation drill (conceptual)

```text
Scenario: a release whose mapping omitted the "app" schema wrote three accepted Jobs to public.jobs.
Contain : roll back the bad mapping/release to protect FUTURE writes (code rollback != durable-data rollback).
Preserve: classify correlation evidence (release version, job/tenant/request/trace IDs, WHETHER the client was
          already responded to — the most important signal) — never blindly ignore/copy/delete the rows.
Reconcile: audited, idempotent reconciliation of the mis-placed rows against the durable app-schema truth.
```

---

## Run instructions

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day46.txt      # sqlalchemy==2.0.29, pytest==7.4.3
python3 -m py_compile day46_orm_mapping.py test_day46_orm_mapping.py
python3 -m pytest -q test_day46_orm_mapping.py
```

---

## Validation and evidence classification

```text
CONCEPTUAL              : the mapping mirrors the Day42 ownership/integrity/retention/provenance decisions.
STATIC METADATA (RUN)   : 19 pytest cases assert the DECLARED mapping structure against Base.metadata — app-schema
                          identity, typed columns, server defaults, named UNIQUE/CHECK/FK constraints, ON DELETE
                          RESTRICT on every FK, the job_events composite provenance FK, TEXT+CHECK (not enum),
                          no cascade delete, ORM/Pydantic separation, the Tenant stub, and the documents/
                          job_documents limitation. Executed: Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3
                          -> 19 passed. NO database connection and NO create_all() were used.
POSTGRESQL RUNTIME      : NOT RUN. No PostgreSQL server was available in this environment. A real runtime test
                          would first apply the independent Day42 raw SQL (001 + 003) to a fresh database, then
                          assert actual behavior (e.g. a succeeded Job without finished_at is rejected with a
                          CHECK violation / IntegrityError, a duplicate (tenant_id, idempotency_key) is rejected,
                          Job B may reuse attempt_number 1) — a REJECTED write, not an empty query result.
                          create_all() success would NOT be schema-compatibility evidence.
INTEGRATION / PRODUCTION: NOT RUN (Day47 sessions/transactions/repository/UoW; Day48 Alembic; later production).
```

---

Lesson: [`docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md`](../../../docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md)
· Day42 schema: [`../sql/001_create_jobs.sql`](../sql/001_create_jobs.sql), [`../sql/003_relational_modeling_and_data_integrity.sql`](../sql/003_relational_modeling_and_data_integrity.sql)
