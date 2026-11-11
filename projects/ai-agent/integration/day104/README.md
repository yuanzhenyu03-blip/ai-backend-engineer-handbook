# Day104 Level 3 PostgreSQL + pgvector lab

This opt-in lab upgrades the Day104 lifecycle from a deterministic process-local
model to bounded `INTEGRATION_RUNTIME` evidence. It uses the Day99 provisionally
selected Provider, PostgreSQL 16 with pgvector 0.8.7, so application truth,
Generation metadata and vectors share one disposable database.

The lab remains local and single-node. It is not production evidence.

## Safety boundary

- Docker publishes PostgreSQL only on `127.0.0.1:55432`.
- `DAY104_L3_PG_PASSWORD` is required at runtime and is never committed.
- The Compose project and named volume are scoped to `day104-l3`.
- The schema is isolated under `day104_l3`; it does not reuse a developer database.
- Evidence must contain digests and versions, never the database URL, password,
  protected content or raw vectors.
- Cleanup targets only this Compose project and its named volume.

## Start the disposable database

Run from this directory:

```bash
export DAY104_L3_PG_PASSWORD="$(openssl rand -hex 24)"
docker compose config --quiet
docker compose up -d --wait
docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U day104_l3 -d day104_l3 < schema.sql
```

Create an isolated Python environment from `projects/ai-agent` and run the
explicit integration entrypoint:

```bash
python3.12 -m venv .venv-day104-l3
.venv-day104-l3/bin/python -m pip install -r requirements-day104-l3.txt
export DAY104_L3_DATABASE_URL="postgresql://day104_l3:${DAY104_L3_PG_PASSWORD}@127.0.0.1:55432/day104_l3"
export DAY104_L3_INTEGRATION=1
PYTHONPATH=src:. .venv-day104-l3/bin/python evals/run_day104_l3_integration.py
```

The runner must fail closed when `DAY104_L3_INTEGRATION` or the database URL is
absent. A normal unit-test run must not silently connect to this service.

## Provider model

pgvector does not expose a Qdrant-style alias. The application database pointer
is authoritative, and every request reads it once and creates a ReadView pinned
to one `generation_id`. Retrieval uses that pinned identity in its SQL predicate.
This avoids treating a separately mutable Provider alias as durable truth.

The lab exercises exact search first as the correctness oracle, then HNSW as a
bounded local comparison. A local recall or latency result does not establish a
production capacity claim.

## Schema invariants

- BuildSnapshot, source/deletion snapshot, Generation build identity, sealed
  artifact, activation record, Inbox receipt and Tombstone identities are set
  once.
- `current_build_snapshots`, active pointers and leases are revisioned mutable
  control-plane facts.
- vector rows can change only before a Generation is sealed. The database rejects
  inserts, updates and deletes after `sealed_at` or a serving lifecycle state.
- lifecycle versions advance exactly once per mutation; state changes follow the
  allowed Day104 graph and fencing tokens never decrease.
- ReadViews bind pointer revision, Generation, BuildSnapshot and authorization
  snapshot. Closing or expiring a view decrements its Generation exactly once in
  the repository transaction.
- deletion Intent, Tombstone and Outbox duty are committed in one transaction;
  operation and idempotency identities are unique.
- lifecycle transitions and activation records are append-only audit facts.

## Cleanup

After the evidence report has been saved and sanitized:

```bash
docker compose down -v --remove-orphans
unset DAY104_L3_DATABASE_URL DAY104_L3_INTEGRATION DAY104_L3_PG_PASSWORD
```

`down -v` removes only the `day104-l3` project volume. Do not substitute a broad
Docker prune command.

## Claim boundary

A passing run can support local `INTEGRATION_RUNTIME` claims for real PostgreSQL
transactions, constraints, row locks, concurrent CAS, restart read-back and real
pgvector writes/search. It cannot prove multi-node leases, replication, backup
restore, WAL erasure, external caches, physical deletion across retained media,
network partitions, load/soak behavior, zero downtime or production readiness.
