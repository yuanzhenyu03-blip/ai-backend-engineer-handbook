# Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration (Design & Runbook)

Engineering artifact / runbook for the Day60 Relay + Worker + recovery boundary. It records
the boundaries, the additive `0009` migration, the disposable local run, the evidence
actually captured, and the explicit NOT RUN limits. It is the entry point for
`day60_delivery_recovery_logic.py` (pure decision core), `day60_runtime_app.py` (readiness
app-factory), `day60_celery_config.py` (delivery settings), and the
`0009_day60_delivery_runtime` migration.

## What Day60 proves (and does not)

Day60 makes Day50's transactional Outbox intent a REAL Redis/Celery Relay + Worker path
and proves at-least-once delivery, idempotent execution, Worker-loss recovery, and bounded
repair — while PostgreSQL stays the business-state authority.

```text
Day50 transactional Outbox intent  ·  Day55 Worker/lease ideas  ·  Day59 real HTTP->PostgreSQL acceptance
        |
        v
Day60 real Relay (publish-before-checkpoint) + guarded Worker claim + durable recovery
        |
        v
Day61 real Object Storage + Provider HTTP + provider request evidence + tracing + reconciliation (NOT RUN here)
Day62 consumes the queue lifecycle via real Playwright runtime verification (NOT RUN here)
```

## Relay ordering: publish BEFORE checkpoint

The Relay claims an unpublished Outbox row, **publishes to the Broker FIRST**, then
**guarded-checkpoints `published_at`** under its fencing token. A crash between the two
leaves `published_at IS NULL`, so retry re-delivers → at-least-once. `published_at` is a
DELIVERY checkpoint, never proof the Job executed or succeeded. `published_at IS NULL`
proves only "no Relay checkpoint" — execution truth needs Job/Attempt/Event (and, after
Day61, Provider/Result) facts.

Two Relays coordinate with a PostgreSQL claim: `SELECT ... FOR UPDATE SKIP LOCKED` +
`relay_owner` / `relay_token` / `relay_claim_expiry` (the `0009` columns). The database
lock is NOT held across Broker I/O; the checkpoint is a fenced guarded write keyed by the
token.

## Worker authority: guarded claim + lease fencing

Celery delivery is NOT execution authority. The winning Worker takes authority with a
guarded transition:

```text
UPDATE app.jobs SET job_status='running', lease_owner=:w, lease_expiry=:exp
 WHERE job_status='queued' RETURNING job_id;   -- exactly one winner
```

carrying a lease token + expiry. It then creates Attempt/Event facts and completes the Job
ONLY under the matching lease token. A stale Worker cannot commit after a takeover
(token/owner fencing). Late acknowledgement is configured in `day60_celery_config.py`
(`task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`);
ACK is transport acknowledgement, not a business-state commit.

## Duplicate / redelivery / expiry decision

`day60_delivery_recovery_logic.classify_delivery(...)`:

```text
duplicate while THIS worker holds a credibly active lease   -> NOOP (no Provider call, no 2nd claim)
redelivery to a DIFFERENT worker, lease still unexpired      -> DEFER to the durable PostgreSQL sweep
                                                                (worker-loss only SUSPECTED; do not seize)
EXPIRED lease + external evidence (provider_request_id or    -> RECONCILE_ONLY (PENDING_RECONCILIATION;
  the Day55 provider_dispatch_started_at marker)                never a second Provider call)
EXPIRED lease + NO external evidence                         -> the sweeper may redispatch
```

Celery retry is transport behaviour, NOT recovery authority. Durable recovery authority is
PostgreSQL state + a newly committed Outbox intent.

## Expired-lease recovery sweep

`classify_recovery_sweep(...)`: with external evidence → RECONCILE_ONLY. Without it, the
sweeper atomically moves `running -> queued`, records a recovery audit event, and writes
EXACTLY ONE new `job.redispatch_requested` Outbox intent; the Relay then delivers it.

## Bounded early-ACK repair (contain config first; never `.delay()`)

A bad early-ACK release is contained by rolling back the erroneous configuration FIRST.
Repair does NOT call Celery `.delay()` — `.delay()` is immediate shorthand for
`apply_async()` Broker publication and cannot replace a durable, transactionally coupled,
replayable, auditable database intent. Repair selects a BOUNDED eligible set
(`is_repair_eligible`), re-verifies it inside the repair transaction, records IMMUTABLE
`app.job_repair_history` facts (PRIMARY KEY = the deterministic `repair_id`, so a
duplicate/concurrent repair applies exactly once), and writes exactly one new redispatch
Outbox intent before commit.

Eligibility predicate (all must hold): from the bad release, within the time window, still
`queued`, original dispatch Outbox checkpointed, NO attempts/external evidence, no
conflict, valid deadline/contract/budget, and the repair not already applied.

## The `0009_day60_delivery_runtime` migration

Additive/expand only (published revisions 0001–0008 unchanged):

- `app.outbox_events` gains nullable `relay_owner` / `relay_token` / `relay_claim_expiry`
  (Relay claim + fencing).
- `app.job_repair_history` (`repair_id` PK, `job_id` FK, `repair_reason`, `release_version`,
  `created_at`) records immutable recovery/repair facts and enforces idempotent repair.

The Day59 readiness app pinned exactly `0008` and correctly returns 503 after `0009`. The
Day60 app requires `0009` via an EXPLICIT `create_app(expected_revision=...)` factory
parameter (not hidden mutable module state). This migration is INSTRUCTIONAL — NOT a
production zero-downtime plan.

## Safe disposable local run (OPT-IN; Docker-backed)

Never commit the database/broker URL, password, token, fixture id, container id, or a
`.venv`. Supply URLs via env vars at run time.

```text
# 0) install the OPT-IN integration stack
python3 -m pip install -r requirements-day60.txt

# 1) disposable PostgreSQL 16 + Redis 7 (writable-layer data deleted on stop because of --rm)
docker run --rm -d --name day60-pg    -e POSTGRES_PASSWORD=<local-only> -p 127.0.0.1:5432:5432 postgres:16
docker run --rm -d --name day60-redis -p 127.0.0.1:6379:6379 redis:7

# 2) raw Day42 baseline -> Alembic stamp -> controlled upgrade to 0009
export DAY48_ALEMBIC_DATABASE_URL='postgresql://<user>:<local-only>@127.0.0.1:5432/<db>'
alembic -c day48_alembic/alembic.ini stamp 0001_baseline_day42
alembic -c day48_alembic/alembic.ini upgrade 0009_day60_delivery_runtime

# 3) readiness gate expects 0009
export DAY60_DATABASE_URL='postgresql+asyncpg://<user>:<local-only>@127.0.0.1:5432/<db>'
uvicorn 'day60_runtime_app:create_app()' --factory --host 127.0.0.1 --port 8000

# 4) run the Relay + Worker (Celery over the local Redis broker); verify committed facts
#    from a NEW psql connection (Outbox checkpoint, guarded claim, Attempt/Event/repair facts)
```

`--rm` deletes the container's writable-layer data on stop; named volumes / external
databases persist by design. Disposable containers were an intentional choice here.

## Evidence captured (validation tiers)

Genuinely executed in a disposable local environment during the Day60 class
(`INTEGRATION_RUNTIME` / `EXECUTED_LOCAL_RUNTIME` as noted), against the ORIGINAL classroom
code:

```text
[EXECUTED_LOCAL_RUNTIME] Python syntax compile of the changed modules
[INTEGRATION_RUNTIME] fresh database facts distinguished from concept/static checks
[INTEGRATION_RUNTIME] real Broker queue lifecycle (Redis/Celery)
[INTEGRATION_RUNTIME] Relay crash window -> unpublished intent retried (at-least-once)
[INTEGRATION_RUNTIME] Worker-kill redelivery
[INTEGRATION_RUNTIME] recovery sweep (expired lease, no evidence) -> running->queued + one redispatch intent
[INTEGRATION_RUNTIME] concurrent repair -> exactly one repair applied + one redispatch intent
[INTEGRATION_RUNTIME] final Job/Attempt/Event/Outbox fact set consistent from a fresh connection
```

**INTEGRATION_RUNTIME NOT RERUN by the updating agent.** The repository updating agent
re-ran only `py_compile` of the changed Python files and the standard-library
`test_day60_delivery_recovery_logic.py` (**11 passed**, `EXECUTED_LOCAL_RUNTIME` — pure
decision logic: relay ordering, guarded-claim outcome, duplicate/redelivery/expiry
classification, recovery-sweep result, repair eligibility + idempotent id, readiness gate).
The updating agent has NO Docker/PostgreSQL/Redis available and did NOT re-run the
integration matrix. A pure-logic pass is NOT integration evidence.

## NOT RUN (explicitly not claimed for Day60)

```text
real Provider HTTP traffic, provider request IDs, or cost (Day61)
Object Storage Result Artifact facts (Day61)
OpenTelemetry tracing / real exporter (Day61)
production load, security, zero-downtime migration, or production scheduling
multi-replica deployment
```

Day61 adds Object Storage + real Provider HTTP + provider request evidence + tracing +
conservative reconciliation; Day62 consumes the queue lifecycle via real Playwright
runtime verification. Their runtime evidence must not be blurred into Day60.
