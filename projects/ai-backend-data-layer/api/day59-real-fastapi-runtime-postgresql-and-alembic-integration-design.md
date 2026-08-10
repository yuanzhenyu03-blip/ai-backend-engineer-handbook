# Day59 — Real FastAPI Runtime, PostgreSQL and Alembic Integration (Design & Runbook)

Engineering artifact / runbook for the Day59 acceptance-boundary integration. It records
the boundaries, prerequisites, a safe disposable local run, the evidence actually
captured, and the explicit NOT RUN limits. It is the entry point for
`day59_runtime_app.py`, `day59_acceptance_logic.py`, the `0008_day59_acceptance`
migration, and the `day48_alembic/env.py` version-table repair.

## What Day59 proves (and does not)

Day59 turns the Day43–Day58 acceptance **contract** into bounded local
`INTEGRATION_RUNTIME` evidence: a real FastAPI/Uvicorn process, a real PostgreSQL, real
Alembic migrations, an atomic acceptance transaction, and committed-state verification
read back from an **independent** connection.

```text
Day43 commit-before-202 + idempotency contract
Day46 ORM mapping  ·  Day47 async Session/Unit-of-Work  ·  Day48 Alembic safe evolution
Day49 Document verification  ·  Day50 idempotent Job + Outbox intent  ·  Day51/52 identity/tenant
        |
        v
Day59 first REAL local integration gate joining those boundaries
        |
        v
Day60 real Redis/Celery Relay+Worker consume the Outbox intent   (NOT RUN here)
Day61 real Object Storage + HTTP Provider adapter + OpenTelemetry (NOT RUN here)
```

## Acceptance boundary (the core rule)

A log line, an in-memory SQLAlchemy `Session`, or an HTTP response is **not** proof of
acceptance. A new Job earns `202` only after ONE short transaction commits:

```text
queued Job
+ persisted request_fingerprint (SHA-256 of the behavior-relevant command: ordered document_ids + normalized business_input (Idempotency-Key is the dedup key, NOT part of the fingerprint))
+ exactly ONE  job.dispatch_requested  Outbox intent
+ Job–Document link(s)
```

The idempotency key travels in the **`Idempotency-Key` header** (Day43 contract), not
the body; a missing or blank header is a `400` before any write, and `document_ids` must
have at least one entry. The whole thing is ONE explicit `async with session.begin()`
(no autobegin-then-`begin()`), using `INSERT ... ON CONFLICT (tenant_id, idempotency_key)
DO NOTHING RETURNING job_id` as the atomic create-or-return — not SELECT-then-INSERT. The
HTTP transaction NEVER calls a Broker, Worker, Provider, or Object Storage. It persists
the Outbox intent for a later Relay (Day60).

## Idempotency and Document lifecycle

- `UNIQUE(tenant_id, idempotency_key)` is the physical dedup mechanism; the persisted
  `request_fingerprint` (SHA-256 of the behavior-relevant command: ordered `document_ids` +
  normalized `business_input`; the Idempotency-Key is the dedup key, NOT in the fingerprint) distinguishes an EXACT retry from the same key reused for a DIFFERENT
  logical request. Because the fingerprint covers the documents, the same key pointing at
  a different Document is a conflict, not a replay.
- When `ON CONFLICT DO NOTHING` returns no row (the key already has a committed Job, or a
  concurrent request won the race), the handler re-reads the existing Job's
  `request_fingerprint` and classifies: same fingerprint returns the first Job with
  `idempotent_replay=true`; a different fingerprint returns `409`. It never assumes replay
  and never swallows an unrelated integrity error.
- Same tenant/key/fingerprint returns the first Job; same tenant/key + different
  `business_input` OR different `document_ids` returns `409`; a fresh key with an
  unverified/wrong-tenant Document returns `422` and writes NO acceptance facts (the whole
  transaction rolls back, so an independent connection reads Job=0 / Outbox=0 / link=0).
- Document verification uses the REAL Day42/Day49 schema: a Document is acceptable only if
  it belongs to this tenant AND its upload session is verified — `app.documents` joined to
  `app.upload_sessions` on `(tenant_id, upload_session_id)` where
  `session_status = 'verified'`. There is NO `documents.verified_at` column.
- Document input ORDER is a persisted business fact, not just a fingerprint input: each
  `app.job_documents` row is written with `document_role = 'input'` and
  `input_order = 1..n` in the client's order, so a later Worker can reconstruct the input
  sequence from PostgreSQL. The client's list is written verbatim — never `set()` or
  `dict.fromkeys()`.
- Duplicate `document_ids` in one request are a MALFORMED command (they collide on the
  `job_documents` primary key and make `input_order` ambiguous): the route rejects them
  with `422` BEFORE opening the transaction, so no Job / Outbox / links are written.
- Idempotency state is checked BEFORE revalidating mutable Document state: an exact
  retry returns the original Job even if the referenced object later became unavailable.
- A verified Document means acceptance-time metadata/provenance + object verification
  succeeded. It does NOT promise future Object Storage readability. A later Worker
  handles unavailable bytes via an explicit recovery/failure path and must NEVER
  retarget the original Job to a newly uploaded Document. New input = new upload/
  verification, new key, new Job.

## Readiness vs liveness

`/livez` = the process is up. `/readyz` = database reachable AND schema at the expected
Alembic revision (`0008_day59_acceptance`). A ready process on the WRONG revision must
return `503` — not silently accept traffic. A readiness failure is not a per-request
`500`.

## Migrations (raw baseline → stamp → controlled upgrade)

1. A blank database cannot run the Alembic chain directly: the Day48 contract requires
   the raw Day42 baseline schema first, then an Alembic **stamp** at `0001_baseline`.
2. Alembic's default `alembic_version.version_num` is `varchar(32)`; revision ids such
   as `0007_merge_reconciliation_polling` (33 chars) do not fit, so the upgrade
   transaction rolls back and the recorded revision stays at the prior value (diagnosed
   from a fresh connection). `env.py` gained a controlled, auditable ONLINE-only
   version-table width repair that widens the column to `varchar(128)` **only when it
   already exists and is too small**. It does not run in FastAPI and does not touch
   application data.
3. `0008_day59_acceptance` is a forward ADDITIVE migration: a nullable
   `app.jobs.request_fingerprint`, a SHA-256-shape CHECK for non-null values, and a
   PARTIAL UNIQUE INDEX allowing only one `job.dispatch_requested` Outbox event per Job.
   Legacy nulls stay valid; enforcing NOT NULL / backfilling / building the index
   `CONCURRENTLY` on a large production table are separate later steps. This is NOT a
   production zero-downtime plan.

Because `0008` is additive, an **API rollback is normally safer than an immediate
Alembic downgrade**; prefer a later forward migration if a schema repair is required.

## The local identity seam (why it is forbidden in production)

`X-Integration-Tenant` exists ONLY when `DAY59_INTEGRATION_TEST=1` AND the database host
is loopback. It is a deliberately constrained integration-test seam so the acceptance
path can be exercised without standing up production identity. It is NOT authentication
and it must NEVER be used as a client-supplied tenant authority: a client that can name
its own tenant can read/write another tenant's data. Production identity remains Day51
JWT authentication + Day52 active-membership/role authorization.

## Safe disposable local run (OPT-IN; Docker-backed)

Never commit the database URL/password, a test token, tenant/user fixture values,
container IDs, or a generated `.venv`. Supply the URL via env vars at run time.

```text
# 0) install the OPT-IN integration stack (async app + sync Alembic drivers)
python3 -m pip install -r requirements-day59.txt   # asyncpg+greenlet (app), psycopg2 (alembic)

# 1) disposable PostgreSQL 16 (writable-layer data is deleted on stop because of --rm)
docker run --rm -d --name day59-pg -e POSTGRES_PASSWORD=<local-only> -p 127.0.0.1:5432:5432 postgres:16

# 2) raw Day42 baseline, then Alembic stamp + controlled upgrade
#    (apply sql/001..008 as the raw baseline, then:)
export DAY48_ALEMBIC_DATABASE_URL='postgresql://<user>:<local-only>@127.0.0.1:5432/<db>'
alembic -c day48_alembic/alembic.ini stamp 0001_baseline_day42
alembic -c day48_alembic/alembic.ini upgrade 0008_day59_acceptance

# 3) run the API and check readiness (expects revision 0008_day59_acceptance)
export DAY59_DATABASE_URL='postgresql+asyncpg://<user>:<local-only>@127.0.0.1:5432/<db>'
export DAY59_INTEGRATION_TEST=1
uvicorn day59_runtime_app:app --host 127.0.0.1 --port 8000

# 4) verify committed facts from a NEW psql connection (not the request Session)
```

`--rm` deletes the container's writable-layer database data when it stops. This does NOT
mean `docker stop` universally deletes all data: named volumes or an external database
persist by design. The disposable container was an intentional choice for this exercise.

## Evidence captured (validation tiers)

The following were genuinely executed in a disposable local environment during the Day59
class, against the ORIGINAL classroom code (`INTEGRATION_RUNTIME` / `EXECUTED_LOCAL_RUNTIME`
as noted). **The Day59 review then corrected the acceptance path** (autobegin/`ON CONFLICT`,
real `upload_sessions.session_status='verified'` Document verification, `Idempotency-Key`
header, fingerprint covering `document_ids`, conflict re-read), so this integration matrix
has **NOT been re-run against the corrected code** — see "INTEGRATION_RUNTIME NOT RERUN"
below.

```text
[EXECUTED_LOCAL_RUNTIME] Python 3.11 syntax compile of the changed modules
[INTEGRATION_RUNTIME] real Uvicorn process + real PostgreSQL 16 container
[INTEGRATION_RUNTIME] raw Day42 baseline -> Alembic stamp -> upgrade through 0008
[INTEGRATION_RUNTIME] /readyz with matching revision; wrong revision -> 503
[INTEGRATION_RUNTIME] valid atomic acceptance: independent query Job=1, dispatch intent=1, Document link=1
[INTEGRATION_RUNTIME] exact-key replay returns the original Job
[INTEGRATION_RUNTIME] same key + different payload -> 409
[INTEGRATION_RUNTIME] invalid/nonexistent Document -> 422 with independent Job=0, Outbox=0, link=0
[INTEGRATION_RUNTIME] two concurrent same-key requests -> one acceptance + one replay; independent 1/1/1
```

A prior version-table-width failure and an async SQL parameter-type failure occurred,
were diagnosed from a fresh connection, and were fixed before the successful reruns.

**INTEGRATION_RUNTIME NOT RERUN.** Re-run by the repository updating agent (Day59 review
fix): `py_compile` of the changed Python files and the standard-library
`test_day59_acceptance_logic.py` (**12 passed**, `EXECUTED_LOCAL_RUNTIME` — pure decision
logic: fingerprint shape/determinism, fingerprint covers ordered documents, replay vs 409
vs fresh, readiness gate). The updating agent has NO Docker/PostgreSQL available and did
NOT re-run the integration matrix against the corrected acceptance path. The corrected
route must be re-run before its `INTEGRATION_RUNTIME` is claimed for the current code. The
pure-logic pass is NOT PostgreSQL integration evidence.

Required integration rerun matrix (NOT RERUN — must be executed against the CORRECTED code
and verified from a fresh connection before any of these is claimed as evidence):

```text
[NOT RERUN] raw Day42 baseline -> Alembic stamp -> upgrade through 0008; /readyz revision gate (wrong -> 503)
[NOT RERUN] valid atomic acceptance -> independent query Job=1, dispatch Outbox=1, links=n
[NOT RERUN] job_documents rows carry document_role='input' and input_order=1..n IN THE CLIENT'S ORDER
[NOT RERUN] exact-key replay (same documents + payload) returns the original Job
[NOT RERUN] same key + different payload -> 409
[NOT RERUN] same key + different Document (or different document order) -> 409
[NOT RERUN] duplicate document_id in one request -> 422 with independent Job=0, Outbox=0, links=0
[NOT RERUN] invalid/wrong-tenant/unverified Document -> 422 with independent Job=0, Outbox=0, links=0
[NOT RERUN] two concurrent same-key + same payload -> one acceptance + one replay; independent 1/1/n
[NOT RERUN] two concurrent same-key + different payload -> one 202 and one 409
```

## NOT RUN (explicitly not claimed for Day59)

```text
real Redis/Celery broker, Relay, Worker, worker-kill or redelivery
real Object Storage / presigned upload / checksum semantics
real HTTP Provider traffic or cost
real OpenTelemetry exporter pipeline
real JWT/JWKS or a production secret manager
production migration lock / load / zero-downtime behavior
multi-replica deployment, load testing, or production validation
```

Day60 (Relay/Worker) and Day61 (Object Storage/Provider/OpenTelemetry) consume these
Day59 boundaries; their runtime evidence must not be blurred into Day59. A verified
Document reference at acceptance does not by itself prove the object remains available to
a later Worker.
