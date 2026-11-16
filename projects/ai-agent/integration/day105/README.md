# Day105 Level 3 PostgreSQL + pgvector security lab

This opt-in lab upgrades the Day105 security contracts from deterministic
process-local evidence to bounded local Docker integration evidence. It combines
the Day104 lifecycle schema and real pgvector query path with a separate
`day105_l3` application-owned security control-plane schema.

The lab uses deterministic scanner, detector, DLP and model adapters. It does
not claim real Provider behavior or production readiness.

## Safety boundary

- Docker publishes PostgreSQL only on `127.0.0.1:55433`.
- `DAY105_L3_PG_PASSWORD` is required at runtime and is never committed.
- The Compose project, database, user and named volume are isolated to
  `day105-l3` / `day105_l3`.
- A new empty volume installs the Day104 lifecycle schema first and the Day105
  security schema second through read-only init mounts.
- Evidence stores identities, digests, decisions and content-safe metadata. It
  must never store the database URL, password, full prompt, protected chunks,
  answer text, reusable attack payload, secret, cross-tenant content or vectors.
- Cleanup targets only this Compose project and its named volume.

## Start the disposable database

Run from this directory:

```bash
export DAY105_L3_PG_PASSWORD="$(openssl rand -hex 24)"
docker compose config --quiet
docker compose up -d --wait
```

The entrypoint installs both schemas on the first start of the disposable
volume. To verify or idempotently reapply them without resetting data:

```bash
docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U day105_l3 -d day105_l3 \
  < ../day104/schema.sql
docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U day105_l3 -d day105_l3 \
  < schema.sql
```

Create an isolated Python environment from `projects/ai-agent` and use the
explicit integration entrypoint:

```bash
python3.12 -m venv .venv-day105-l3
.venv-day105-l3/bin/python -m pip install -r requirements-day105-l3.txt
export DAY105_L3_DATABASE_URL="postgresql://day105_l3:${DAY105_L3_PG_PASSWORD}@127.0.0.1:55433/day105_l3"
export DAY105_L3_INTEGRATION=1
PYTHONPATH=src:. .venv-day105-l3/bin/python evals/run_day105_l3_integration.py
```

The runner must fail closed when `DAY105_L3_INTEGRATION` or the database URL is
absent. Default tests and CI must not silently connect to this service.

## Reset guard

The integration repository may reset the lab only when all three checks pass:

1. `DAY105_L3_INTEGRATION=1` is present in the calling process.
2. The caller supplies the exact confirmation `RESET_DAY105_L3_SCHEMAS`.
3. PostgreSQL reports `current_database() = 'day105_l3'`.

The database function `public.reset_day105_l3_schemas()` repeats those checks
before dropping the two exact lab schemas. It never drops a database, volume or
unrelated schema. After reset, the runner must reinstall Day104 first and Day105
second before creating evidence.

## Database invariants

- `security_snapshots`, `security_artifacts`, `response_intents` and
  `incident_records` are append-only at the database layer.
- `current_security_snapshots` is the only mutable security table. Updates must
  preserve tenant identity, advance exactly one revision and point to a new
  snapshot. The repository performs the update with a compare-and-swap predicate
  and commits it atomically with its durable transition artifact.
- Snapshot occurrence sets and artifact parent digests use sorted, unique arrays.
- JSON payloads are objects and a recursive database check rejects fields that
  could hold credentials, raw content, prompts, answers, attack payloads,
  destinations or vectors.
- A response intent must reference an exact output-release artifact. A
  non-`PASS` decision can never create a `RELEASE` intent.
- Incident records have exactly one root, one successor per record and no
  cross-incident continuation. Corrections append; they do not overwrite.

## Restart replay

Application-process restart and container restart are separate evidence:

```bash
docker compose restart postgres
```

After the container becomes healthy, the restart runner must use a new process
and connection, must not install or reset schemas, and must verify the saved
G2/G3 identities, current security snapshot, blocked old response intent and
incident history. It also records `pg_postmaster_start_time()` so a new client
connection is not mislabeled as a database restart.

## Cleanup

After the sanitized report and restart replay have been saved:

```bash
docker compose down -v --remove-orphans
unset DAY105_L3_DATABASE_URL DAY105_L3_INTEGRATION DAY105_L3_PG_PASSWORD
```

`down -v` removes only the `day105-l3` project volume. Do not substitute a broad
Docker prune command.

## Claim boundary

A passing run may support local evidence for real PostgreSQL transactions,
constraints, row locks, compare-and-swap, append-only records, restart read-back
and real pgvector storage/query while deterministic security adapters drive the
application-owned gates. It cannot prove real scanner/detector/DLP/model or
external vector Provider behavior, production IAM/RLS/TLS/egress, HA, backup
restore, network partition, physical purge, production load/soak, canary traffic
or production readiness.
