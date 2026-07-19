# Production AI Backend Data Layer

The evolving Phase 3 engineering artifact. It turns the Day28 conceptual ownership rule —
**PostgreSQL owns durable Job truth** — into an executable, failure-aware data layer, one lesson at a
time (Day29-Day42).

Current increment: **Day29 — the first minimal raw SQL Job schema.**

Lesson: [`docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md`](../../docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md)

---

## Structure (grows with real lessons only)

```text
projects/ai-backend-data-layer/
├── README.md
└── sql/
    └── 001_create_jobs.sql
```

> **Deviation from `projects/README.md` (stated honestly):** the generic project template lists
> `requirements.txt`, `Dockerfile`, `src/`, `tests/`, and `docs/`. Day29 produced only a README and one
> raw SQL file, so nothing else exists yet. Empty folders and placeholder executables are deliberately
> **not** created; the structure will grow as later Phase 3 lessons produce real content. No ORM is
> used — SQLAlchemy/Alembic are Phase 4.

---

## What this schema is for

```text
Client uploads a verified 500 MB document
-> FastAPI writes (and commits) the Job row      <-- THIS FILE
-> FastAPI returns 202 + job_id
-> a worker later claims the queued Job
```

The row must exist **before** `202` is returned. `202` acknowledges a commitment that already exists
durably; if the API Pod is replaced a millisecond later, the Job is still recoverable.

## Ownership decisions

```text
PostgreSQL     -> the Job row: identity, state, timestamps, counters, flags, references (durable truth)
Object Storage -> the 500 MB source document and large derived artifacts (result_object_key is a REFERENCE)
Redis / Queue  -> transient transport/cache only (not modeled here, not run in Day29)
Process memory -> request-local only; never durable truth
```

Column intent:

| Column | Type | Intent |
|---|---|---|
| `job_id` | `uuid` PK, `DEFAULT gen_random_uuid()` | stable row identity; distributed + non-enumerable |
| `job_status` | `text NOT NULL DEFAULT 'queued'` | evolving lifecycle state |
| `attempt_count` | `integer NOT NULL DEFAULT 0` | retry bookkeeping |
| `cancel_requested` | `boolean NOT NULL DEFAULT false` | cooperative cancellation flag |
| `provider_metadata` | `jsonb NOT NULL DEFAULT '{}'::jsonb` | **bounded** auxiliary metadata only |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | immutable acceptance instant |
| `started_at` | `timestamptz` NULL | NULL -> execution has not started |
| `finished_at` | `timestamptz` NULL | NULL -> not terminal yet |
| `error_message` | `text` NULL | NULL -> no recorded error |
| `result_object_key` | `text` NULL | NULL -> no result artifact yet (Object Storage reference) |

---

## Reproduce the Day29 validation (disposable PostgreSQL)

These commands recreate **every** validation performed in class, in a **throwaway local cluster**.
No credentials, no shared database, no production connection string, no Docker.

> **Status of this section:** the commands below were **authored, not executed, during the repository
> update** — no `psql`, PostgreSQL server, or Docker daemon was available in that environment. They are
> a **static** reproduction procedure. The results quoted under "Verified in class" came from the live
> lesson (PostgreSQL 14.18) and are **classroom evidence only**. Run the steps yourself to reproduce them.

Run from this directory:

```bash
cd projects/ai-backend-data-layer
```

(Or run from the repository root and replace `sql/001_create_jobs.sql` with
`projects/ai-backend-data-layer/sql/001_create_jobs.sql`.)

### 1. Start a disposable cluster

Task-specific variables are used so an existing `PGDATA` is never reused or overwritten.

```bash
export DAY29_PG_ROOT="$(mktemp -d)"
export DAY29_PGDATA="$DAY29_PG_ROOT/data"
export DAY29_PGPORT=5433
export DAY29_PGHOST="$DAY29_PG_ROOT/sock"
mkdir -p "$DAY29_PGHOST"

initdb -D "$DAY29_PGDATA" >/dev/null
pg_ctl -D "$DAY29_PGDATA" -o "-p $DAY29_PGPORT -k $DAY29_PGHOST" -l "$DAY29_PG_ROOT/server.log" start

alias day29psql='psql -p "$DAY29_PGPORT" -h "$DAY29_PGHOST" -d ai_backend'
createdb -p "$DAY29_PGPORT" -h "$DAY29_PGHOST" ai_backend
```

### 2. Apply the schema

```bash
day29psql -f sql/001_create_jobs.sql
```

### 3. Database-generated defaults

```bash
day29psql -c "INSERT INTO app.jobs DEFAULT VALUES RETURNING *;"
```

Expect `queued`, `0`, `false`, `{}`, a `created_at`, and NULL for `started_at`, `finished_at`,
`error_message`, `result_object_key`.

### 4. Session / namespace diagnostics

```bash
day29psql -c "\conninfo"
day29psql -c "SELECT current_database(), current_user, current_schema();"
day29psql -c "SHOW search_path;"
day29psql -c "\dn"
day29psql -c "\dt app.*"
```

The session connects to the **database**; `app.jobs` resolves through explicit qualification even though
`app` is not in `search_path`.

### 5. NOT NULL rejects NULL — **this command is EXPECTED TO FAIL**

```bash
# EXPECTED FAILURE: null value in column "job_status" violates not-null constraint.
# A non-zero exit code here means the constraint works. It is NOT a broken script.
day29psql -c "INSERT INTO app.jobs (job_status) VALUES (NULL);" || echo "^ expected failure: NOT NULL works"
```

### 6. NOT NULL does NOT enforce business validity — these SUCCEED (the known gap)

```bash
day29psql -c "INSERT INTO app.jobs (job_status) VALUES ('') RETURNING job_id, job_status;"
day29psql -c "INSERT INTO app.jobs (job_status) VALUES ('banana') RETURNING job_id, job_status;"
```

Both are accepted — durability is not integrity. A `CHECK`/enum rule is Day31 work.

### 7. timestamptz is one absolute instant

```bash
day29psql -c "SET TIME ZONE 'UTC';           SELECT job_id, created_at, extract(epoch FROM created_at) AS epoch FROM app.jobs ORDER BY created_at LIMIT 1;"
day29psql -c "SET TIME ZONE 'Asia/Shanghai'; SELECT job_id, created_at, extract(epoch FROM created_at) AS epoch FROM app.jobs ORDER BY created_at LIMIT 1;"
```

Different rendering, identical `epoch`.

### 8. Guarded data repair (the `queud` drill)

```bash
# Simulate the bad release writing a misspelled status.
day29psql -c "INSERT INTO app.jobs (job_status) SELECT 'queud' FROM generate_series(1,3);"

# Baseline counts.
day29psql -c "SELECT job_status, count(*) FROM app.jobs GROUP BY job_status ORDER BY job_status;"

# GUARDED repair: narrow WHERE, and capture evidence via RETURNING.
day29psql -c "UPDATE app.jobs SET job_status = 'queued' WHERE job_status = 'queud' RETURNING job_id;"

# Post-repair counts (verify the repair scope).
day29psql -c "SELECT job_status, count(*) FROM app.jobs GROUP BY job_status ORDER BY job_status;"
```

The reported row count plus `RETURNING` are the evidence. Never run an unguarded `UPDATE`.

### 9. Restart persistence

```bash
day29psql -c "SELECT count(*) AS before_restart FROM app.jobs;"
pg_ctl -D "$DAY29_PGDATA" -m fast restart -l "$DAY29_PG_ROOT/server.log"
day29psql -c "SELECT count(*) AS after_restart FROM app.jobs;"
day29psql -c "SELECT job_status, count(*) FROM app.jobs GROUP BY job_status ORDER BY job_status;"
```

This proves **local process-lifecycle persistence only** — not backup recovery, high availability, or
crash durability under hardware failure.

### 10. Clean up (deletes only the directory created by `mktemp` above)

```bash
pg_ctl -D "$DAY29_PGDATA" -m fast stop
# Deletes ONLY this run's mktemp directory. Guarded so an unset variable cannot expand to "rm -rf /".
[ -n "$DAY29_PG_ROOT" ] && [ -d "$DAY29_PG_ROOT" ] && rm -rf "$DAY29_PG_ROOT"
unalias day29psql 2>/dev/null
unset DAY29_PG_ROOT DAY29_PGDATA DAY29_PGPORT DAY29_PGHOST
```

Docker was **not** used and is **not** validated: the Docker CLI existed during class but the daemon was
not running. Do not present a Docker workflow as verified.

---

## Validation matrix

| Level | Day29 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done** | Responsibility, type, NULL/DEFAULT, identity, and repair reasoning reviewed in class |
| SQL syntax / DDL acceptance | **Done (PostgreSQL 14.18)** | `CREATE SCHEMA` + `CREATE TABLE app.jobs` executed successfully |
| Real disposable-PostgreSQL behavior | **Done (selected behaviors)** | defaults, NOT NULL rejection, timestamptz rendering, guarded repair, restart persistence (below) |
| Re-run during this repository update | **NOT RUN** | no `psql`/PostgreSQL server/Docker daemon was available in the repository-update environment |
| Application integration (FastAPI/Celery) | **NOT DONE** | no service was created or connected |
| Production validation | **NOT DONE** | no deployment, HA, backup/restore, or load evidence |

### Verified in class (PostgreSQL 14.18, disposable cluster)

```text
- CREATE SCHEMA and CREATE TABLE succeeded.
- gen_random_uuid() was available and produced a UUID.
- INSERT ... DEFAULT VALUES RETURNING * produced queued / 0 / false / {} / created_at,
  with started_at, finished_at, error_message, result_object_key returned as NULL.
- Explicit job_status NULL failed with a not-null constraint violation.
- Empty job_status AND 'banana' were both ACCEPTED  -> the known missing business constraint.
- The same created_at rendered as 2026-07-19 12:32:00.454132+00 (UTC) and
  2026-07-19 20:32:00.454132+08 (Asia/Shanghai); both had epoch 1784464320.454132.
- Guarded repair drill: three 'queud' rows inserted (baseline empty=1, banana=1, queud=3, queued=1);
  UPDATE ... WHERE job_status = 'queud' reported UPDATE 3 and RETURNING listed the three repaired
  job_ids; post-repair counts were empty=1, banana=1, queued=4.
- PostgreSQL was stopped and restarted; all 6 rows remained (queued=4, banana=1, empty=1).

Session context:
- The session connected to database ai_backend as user yuanzhenyu.
- The target relation was app.jobs.
- search_path was "$user", public.
- current_schema() returned public.
- Explicit qualification allowed app.jobs to resolve even though app was not in search_path.
- Session timezone was Asia/Shanghai.

(A session connects to a DATABASE, never to a schema. `app` is the namespace of the target relation,
not "the schema the session is connected to".)
```

**Not proven by the restart test:** backup recovery, high availability, crash durability under hardware
failure, or production reliability. It showed local process-lifecycle persistence only.

---

## Known gaps (deliberate — future lessons)

```text
Day30  SELECT/INSERT/UPDATE/DELETE/RETURNING, NULL logic, parameterized SQL, guarded transitions
Day31  CHECK (valid job_status, attempt_count >= 0), UNIQUE business/idempotency key, tenant ownership,
       Documents / Job Attempts / Job Events / Outbox Events / Result Artifact refs, foreign keys
Day33  transactions (atomic Job + Outbox insert)
Day34  concurrency-safe claims (FOR UPDATE / SKIP LOCKED), leases, idempotency enforcement
Day35  indexes and query plans
Day36  versioned migrations (this file is a starting point, not a migration framework)
Day37  pooling, roles/least privilege, timeouts, vacuum, backup/PITR, operations
```

Today's schema is durable but **not yet correct-by-construction**: a misspelled `queud` status is
accepted, stored forever, and never claimed by a worker. Durability is not integrity.

Related: [PostgreSQL cheat sheet](../../cheat_sheets/postgresql.md) ·
[PostgreSQL interview](../../interview/postgresql.md) ·
[Day28 architecture blueprint](../../examples/ai-backend-architecture/README.md)
