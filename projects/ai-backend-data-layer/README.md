# Production AI Backend Data Layer

The evolving Phase 3 engineering artifact. It turns the Day28 conceptual ownership rule —
**PostgreSQL owns durable Job truth** — into an executable, failure-aware data layer, one lesson at a
time (Day29-Day42).

Current increment: **Day30 — a raw, parameterized SQL operations pack** on top of the Day29 schema.

Lessons:
- Day29 (schema): [`docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md`](../../docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md)
- Day30 (operations): [`docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md`](../../docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md)

---

## Structure (grows with real lessons only)

```text
projects/ai-backend-data-layer/
├── README.md
└── sql/
    ├── 001_create_jobs.sql                        # Day29: the durable Job schema
    └── 002_job_crud_and_guarded_transitions.sql   # Day30: parameterized reads + guarded writes
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

## Day30 increment — parameterized reads and guarded writes

`sql/002_job_crud_and_guarded_transitions.sql` is a **reference pack of statement templates**, not a
migration and not a runnable script: `$1`/`$2`/`$3` must be bound by an application or driver.

| # | Statement | Purpose | Expected affected rows |
|---|---|---|---|
| 1 | `INSERT ... (provider_metadata) VALUES ($1::jsonb) RETURNING ...` | create a Job; PostgreSQL generates the rest | exactly 1 |
| 1b | `INSERT ... DEFAULT VALUES RETURNING ...` | all-defaults variant | exactly 1 |
| 2 | deterministic queued `SELECT` | 20 oldest queued candidates | 0..20 (read) |
| 3a | `WHERE finished_at IS NULL` | unfinished Jobs | 0..N (read) |
| 3b | `WHERE error_message IS NULL OR error_message <> 'timeout'` | errors other than timeout, keeping no-error rows | 0..N (read) |
| 3c | `WHERE error_message IS DISTINCT FROM 'timeout'` | NULL-safe alternative | 0..N (read) |
| 4a | guarded `queued -> running` | worker start | **0 or 1** |
| 4b | guarded `running -> succeeded` (+ `result_object_key`) | worker completion | **0 or 1** |
| 5a | `SET attempt_count = attempt_count + 1` | database-side increment (no lost update) | 0 or 1 |
| 5b | `... WHERE attempt_count = $2` | optimistic expected-value guard | 0 or 1 |
| 6 | guarded cleanup `DELETE ... IN ('', 'banana')` | remove pre-cutoff test rows | 0..N (reconcile first) |

Contracts and boundaries encoded in the file:

- **`WHERE` is the modification boundary.** Every transition carries both the identity (`$1`) and the
  required current state, so a terminal Job can never be restarted.
- **Zero rows means the transition did not apply** — it does **not** prove the Job is absent. The caller
  must not report success.
- **`RETURNING` returns rows, not a count.** Affected-row count evidence comes from the driver's command
  result or the number of rows received.
- **The candidate `SELECT` is not a claim.** Two workers see the same rows; concurrency-safe claiming
  (`FOR UPDATE`, `SKIP LOCKED`) is Day34 and is deliberately absent.
- **`$1` is PostgreSQL/asyncpg-style.** psycopg uses `%s`, SQLAlchemy uses named binds. Adapt the
  placeholder spelling; never build SQL from client input with string formatting.
- **Parameters bind values only** — identifiers and `ASC`/`DESC` require a strict allowlist.
- **`AND` binds tighter than `OR`**, so the cleanup uses `IN ('', 'banana')` instead of an
  unparenthesized chain that would delete every `banana` row regardless of date.

Deliberately **not** in this file: transactions, locking, `CHECK`/`UNIQUE`/foreign keys, indexes, Job
Event/Attempt tables, ORM, and any migration framework (Day31-Day35 and Phase 4).

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

The temporary directory uses a **task-specific fixed prefix** (`day29-pg.XXXXXX`) so cleanup can later
prove the path was created by this procedure. An existing `PGDATA` is never reused or overwritten.

```bash
# Fixed, identifiable prefix. This mktemp template form works on both macOS and Linux.
export DAY29_PG_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/day29-pg.XXXXXX")"
export DAY29_PGDATA="$DAY29_PG_ROOT/data"
export DAY29_PGPORT=5433
export DAY29_PGHOST="$DAY29_PG_ROOT/sock"
mkdir -p "$DAY29_PGHOST"
echo "Disposable cluster root: $DAY29_PG_ROOT"

initdb -D "$DAY29_PGDATA" >/dev/null
pg_ctl -D "$DAY29_PGDATA" -o "-p $DAY29_PGPORT -k $DAY29_PGHOST" -l "$DAY29_PG_ROOT/server.log" start

# A shell FUNCTION (not an alias) so it also works in non-interactive shells/scripts.
# ON_ERROR_STOP=1 makes any SQL error produce a reliable non-zero exit status.
day29psql() { psql -v ON_ERROR_STOP=1 -p "$DAY29_PGPORT" -h "$DAY29_PGHOST" -d ai_backend "$@"; }

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

### 5. NOT NULL rejects NULL — precise assertion of the expected error

This step **asserts a specific PostgreSQL error condition**, `not_null_violation` (SQLSTATE 23502). It is
**not** "any non-zero exit counts as a pass". A nested `EXCEPTION` block catches only that one condition:

- expected `not_null_violation` -> `NOTICE: PASS` and the command exits **0**;
- the INSERT unexpectedly **succeeding** -> the block raises its own exception, so the step **fails**;
- any other failure (missing table `undefined_table`, syntax error, connection refused, wrong database)
  is **not** caught, propagates, and the step **fails** — it is never reported as a pass.

```bash
day29psql <<'SQL'
DO $$
BEGIN
    BEGIN
        INSERT INTO app.jobs (job_status) VALUES (NULL);
        -- Reached only if the NOT NULL constraint did NOT reject the row.
        RAISE EXCEPTION
            'VALIDATION FAILED: NULL job_status was accepted; the NOT NULL constraint is missing';
    EXCEPTION
        WHEN not_null_violation THEN
            RAISE NOTICE 'PASS: NULL job_status rejected with not_null_violation (SQLSTATE 23502)';
    END;
END
$$;
SQL
```

`day29psql` is deliberately the **last command in the block**, so the block's exit status *is* the
verification result — nothing after it can mask a failure:

| Outcome | Exit status |
|---|---|
| Expected `not_null_violation` (SQLSTATE 23502) | **0** |
| NULL unexpectedly accepted (`P0001` raised by the block) | non-zero |
| Missing table, syntax error, wrong database, connection refused | non-zero |

The custom `RAISE EXCEPTION` uses SQLSTATE `P0001`, which the handler does **not** catch, so an
unexpectedly successful INSERT reliably fails the step. Because the exception aborts the block, no row is
left behind. (Do **not** append `echo "exit status: $?"` here: `echo` returns 0 and would overwrite the
real status. If you must print it, capture `rc=$?` first, print, then `return`/`exit "$rc"` explicitly —
never an unconditional `exit` in an interactive shell.)

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

### 10. Clean up (identity-verified before any recursive delete)

A non-empty variable pointing at an existing directory is **not** proof that the path belongs to this
procedure — an overwritten variable could still name something important. The guard below therefore
**verifies the identity of the path** before `pg_ctl stop` or `rm -rf` touches anything:

1. `DAY29_PG_ROOT` matches the task-specific `day29-pg.XXXXXX` prefix created in step 1;
2. it is not `/`, `$HOME`, or the current working directory;
3. `DAY29_PGDATA` is exactly `$DAY29_PG_ROOT/data`;
4. `$DAY29_PGDATA/PG_VERSION` exists (i.e. it really is a PostgreSQL data directory).

If **any** check fails, cleanup is refused with a clear message and nothing is deleted or stopped.

Deletion is additionally gated on PostgreSQL having actually stopped. The shell does **not** abort on a
non-zero `pg_ctl` status by default, so the steps are chained with explicit `if`/`else` rather than
sequential commands — a stop failure or timeout must never be followed by `rm -rf` on a data directory
that may still be in use. Diagnostic variables are cleared **only** on full success.

```bash
day29_cleanup_guard() {
    [ -n "${DAY29_PG_ROOT:-}" ]  || { echo "REFUSING cleanup: DAY29_PG_ROOT is unset/empty." >&2; return 1; }
    [ -n "${DAY29_PGDATA:-}" ]   || { echo "REFUSING cleanup: DAY29_PGDATA is unset/empty." >&2; return 1; }
    case "$DAY29_PG_ROOT" in
        */day29-pg.??????) : ;;
        *) echo "REFUSING cleanup: '$DAY29_PG_ROOT' does not match the day29-pg.XXXXXX prefix." >&2; return 1 ;;
    esac
    [ "$DAY29_PG_ROOT" != "/" ] && [ "$DAY29_PG_ROOT" != "$HOME" ] && [ "$DAY29_PG_ROOT" != "$PWD" ] \
        || { echo "REFUSING cleanup: '$DAY29_PG_ROOT' is /, \$HOME, or the current directory." >&2; return 1; }
    [ -d "$DAY29_PG_ROOT" ] || { echo "REFUSING cleanup: '$DAY29_PG_ROOT' is not a directory." >&2; return 1; }
    [ "$DAY29_PGDATA" = "$DAY29_PG_ROOT/data" ] \
        || { echo "REFUSING cleanup: DAY29_PGDATA is not \$DAY29_PG_ROOT/data." >&2; return 1; }
    [ -f "$DAY29_PGDATA/PG_VERSION" ] \
        || { echo "REFUSING cleanup: no PG_VERSION in '$DAY29_PGDATA' — not a cluster made by this procedure." >&2; return 1; }
    return 0
}

# Printed on every refusal so the cluster can be inspected and removed by hand.
day29_report_vars() {
    {
        echo "  Preserved for diagnosis (NOT unset):"
        echo "    DAY29_PG_ROOT=${DAY29_PG_ROOT:-<unset>}"
        echo "    DAY29_PGDATA=${DAY29_PGDATA:-<unset>}"
        echo "    DAY29_PGPORT=${DAY29_PGPORT:-<unset>}"
        echo "    DAY29_PGHOST=${DAY29_PGHOST:-<unset>}"
        echo "    server log:   ${DAY29_PG_ROOT:-<unset>}/server.log"
    } >&2
}

day29_cleanup() {
    # Gate 1: path identity.
    if ! day29_cleanup_guard; then
        echo "REFUSING cleanup: guard failed. Nothing was stopped or deleted." >&2
        day29_report_vars
        return 1
    fi

    # Gate 2: PostgreSQL must actually stop before anything is removed.
    if ! pg_ctl -D "$DAY29_PGDATA" -m fast stop; then
        echo "REFUSING delete: pg_ctl stop failed or timed out." >&2
        echo "  The data directory may still be in use; it was NOT removed." >&2
        day29_report_vars
        return 1
    fi

    # Gate 3: the delete itself must succeed (and the directory must really be gone).
    rm -rf -- "$DAY29_PG_ROOT"
    rc=$?
    if [ "$rc" -ne 0 ] || [ -e "$DAY29_PG_ROOT" ]; then
        echo "REFUSING to report success: rm -rf failed (status $rc) or the path still exists." >&2
        day29_report_vars
        return 1
    fi

    # Only now is it true that the cluster is stopped and the directory is gone.
    echo "Removed disposable cluster: $DAY29_PG_ROOT"
    unset DAY29_PG_ROOT DAY29_PGDATA DAY29_PGPORT DAY29_PGHOST
    # Remove every helper, including this function itself. Both bash and zsh allow a
    # running function to unset its own definition; the current call still completes.
    unset -f day29psql day29_cleanup_guard day29_report_vars day29_cleanup 2>/dev/null
    return 0
}

day29_cleanup
```

Cleanup outcomes:

| Branch | `pg_ctl stop` | `rm -rf` | Message | Variables + helpers | Exit status |
|---|---|---|---|---|---|
| Guard failed | not run | not run | `REFUSING cleanup` | **preserved + printed** | non-zero |
| Stop failed/timed out | failed | **not run** | `REFUSING delete` | **preserved + printed** | non-zero |
| Delete failed | ok | failed / path remains | `REFUSING to report success` | **preserved + printed** | non-zero |
| Full success | ok | ok, path gone | `Removed disposable cluster: ...` | **all cleared** (vars + 4 helpers) | 0 |

Success is reported **only** after the directory is verifiably gone. On full success the shell is left
clean: all four `DAY29_*` variables and **all four helper functions** (`day29psql`,
`day29_cleanup_guard`, `day29_report_vars`, and `day29_cleanup` itself) are removed — no manual
follow-up step is needed. On any failure the variables **and** the helpers are kept so you can inspect
the cluster and re-run `day29_cleanup` after fixing the cause.

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

### Day30 (`002_job_crud_and_guarded_transitions.sql`)

| Level | Day30 status | Evidence |
|---|---|---|
| Conceptual / manual review | **Done (in class)** | clause chain, NULL logic, parameter boundary, guarded transitions, affected rows, lost update, incident order |
| Static file review | **Done (repository update)** | balanced parens/quotes; 11 statements; every DML has `RETURNING`; guards use `= 'queued'` / `= 'running'`; `DELETE` uses `IN (...)`; only `$1`/`$2`/`$3` parameters; no transactions, locks, constraints, indexes, or DDL; no credentials |
| PostgreSQL parser / syntax execution | **NOT RUN** | no `psql`/PostgreSQL server was available in class or in the repository-update environment |
| Real disposable-PostgreSQL behavior | **NOT RUN** | — |
| Python-driver parameter binding | **NOT RUN** | no application or driver was executed |
| FastAPI / Celery / Object Storage integration | **NOT RUN** | — |
| Transaction / concurrency runtime test | **NOT RUN** | outside Day30 scope (Day33/Day34) |
| Production validation | **NOT RUN** | — |

> The Day29 PostgreSQL 14.18 classroom evidence below belongs to `001_create_jobs.sql` only. It is
> **not** evidence for the Day30 statements.

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
