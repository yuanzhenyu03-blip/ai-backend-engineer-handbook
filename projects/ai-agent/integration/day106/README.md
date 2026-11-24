# Day106 L3A/L3B PostgreSQL, pgvector and external-model capstone lab

This opt-in lab binds one Day106 execution across the real Day104 lifecycle
schema, the real Day105 security control-plane schema, and the Day106 durable
release/dispatch/recovery schema. Deterministic model, DLP, destination, and
delivery adapters remain outside PostgreSQL. A passing L3A run is therefore
local-real database evidence, not external-provider or production-readiness
evidence.

L3B reuses the same isolated database boundary and adds an explicitly enabled,
bounded external-model path. It does not turn the model or Provider into release
authority and does not upgrade unexecuted external-DLP or production controls.

## Isolation and safety

- PostgreSQL is published only on `127.0.0.1:55434`.
- The project, database, user, and volume are isolated as `day106-l3` and
  `day106_l3`.
- `DAY106_L3_PG_PASSWORD` is required and must be disposable.
- Init scripts install Day104, Day105, then Day106 through read-only mounts.
- Persisted evidence is limited to IDs, versions, digests, counts, safe reason
  codes, state, and timestamps. Never persist a DSN, password, full prompt,
  protected chunk, candidate text, raw response, attack payload, or raw vector.
- Default tests never connect. Both `DAY106_L3_INTEGRATION=1` and
  `DAY106_L3_DATABASE_URL` are required by an integration runner.

## Start

Run only from this directory:

```bash
export DAY106_L3_PG_PASSWORD="$(openssl rand -hex 24)"
docker compose config --quiet
docker compose up -d --wait
export DAY106_L3_DATABASE_URL="postgresql://day106_l3:${DAY106_L3_PG_PASSWORD}@127.0.0.1:55434/day106_l3"
export DAY106_L3_INTEGRATION=1
```

Create an isolated environment from `projects/ai-agent`:

```bash
python3.12 -m venv .venv-day106-l3
.venv-day106-l3/bin/python -m pip install -r requirements-day106-l3.txt
PYTHONPATH=src:. .venv-day106-l3/bin/python evals/run_day106_l3a_integration.py
```

The integration runner must bind the exact real database Generation,
ReadView, occurrence IDs, and content digests to the same Day106 request,
retrieval/context receipt, candidate decision, and response intent. Separate
Day105 and Day106 PASS results are not an end-to-end execution.

## Reset guard

The repository reset requires all of:

1. `DAY106_L3_INTEGRATION=1`;
2. exact confirmation `RESET_DAY106_L3_SCHEMAS`;
3. `current_database() = 'day106_l3'`.

It drops only the exact `day106_l3`, `day105_l3`, and `day104_l3` schemas.
The caller must then reinstall them in that order. Never use Docker prune.

The L3A/L3B schema is a disposable lab contract, not an online migration. A
volume created with an earlier Day106 schema must be reset and recreated after
changes to `model_invocations`, provider attempts/outcomes, digest checks, or
release triggers. Do not apply the new DDL over earlier Day106 evidence and
claim continuity; preserve the old report as historical evidence, then run a
new execution on a clean volume.

Every model invocation is persisted before generation. `EXTERNAL` invocations
also require an append-only provider-call reservation before network send
(`call_ordinal` is bounded to 1..10). `FAILED` and `UNKNOWN` outcomes may lack
an observed model, response/answer digests, and token counts. `SUCCEEDED`
outcomes require all of them and exact token arithmetic. An external release
cannot commit without the matching successful outcome.

## Restart replay

After an integration report has saved the pre-restart server identity:

```bash
docker compose restart postgres
PYTHONPATH=src:. .venv-day106-l3/bin/python evals/run_day106_l3_restart_replay.py
```

The restart runner uses a new process and fresh connection. It must not install
or reset schemas. It verifies `pg_postmaster_start_time()` advanced and reads
the same durable cross-bound execution and response histories.

## L3B external-model boundary

L3B is opt-in and requires both `DAY106_L3B_INTEGRATION=1` and
`DAY106_L3B_REAL_PROVIDER=1`. The API credential must be injected only into the
runner process through `OPENAI_API_KEY`; never paste it into a command, report,
fixture, log or repository file.

The runner owns an exact five-call budget. Every call uses `store=false`, no
tools, `max_output_tokens=64`, a bounded Prompt and no automatic retry after an
unknown outcome. It persists the model invocation and provider-call reservation
before network send, records only content-safe identities/digests/counts and
requires reconciliation for timeout/408/409/5xx outcomes. Generated reports are
created with exclusive-write semantics and must be followed by a real database
restart report and independent offline replay. The fixture creates no response
dispatch or delivery.

## Cleanup

```bash
docker compose down -v --remove-orphans
unset DAY106_L3_DATABASE_URL DAY106_L3_INTEGRATION DAY106_L3_PG_PASSWORD
```

Cleanup evidence may identify only this project/container/network/volume by
content-safe names or digests.

## Claim boundary

L3A can prove real PostgreSQL transactions, constraints, row/advisory locks,
append-only histories, CAS/winner fencing, restart read-back, and real pgvector
storage/query with deterministic application adapters. It does not prove a
real model/DLP provider, production IAM/RLS/TLS/egress, network partitions,
HA/restore, physical purge, load/soak, canary traffic, or production readiness.

A passing L3B report additionally proves only the recorded bounded real-model
calls and their exact Day106 request/retrieval/context/candidate/release binding.
It still does not prove external DLP, production IAM/RLS/TLS/egress, HA/restore,
physical purge, load/soak/canary or production readiness. Readiness remains
`MORE_EVIDENCE_NEEDED`.
