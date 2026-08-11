# Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration (Design & Runbook)

Engineering artifact / runbook for the Day60 Relay + Worker + recovery boundary. It records
the boundaries, the `0009`-`0012` migrations (0009/0010/0012 additive; 0011 a corrective DROP), the disposable local run, the evidence
actually captured, and the explicit NOT RUN limits. It is the entry point for
`day60_delivery_runtime.py` (the REAL Relay/Worker/recovery/repair runtime),
`day60_celery_app.py` (the real Celery app + Worker task), `day60_relay.py` /
`day60_sweeper.py` (the Relay and sweeper process entrypoints),
`day60_delivery_recovery_logic.py` (pure decision core), `day60_runtime_app.py` (readiness
app-factory), `day60_celery_config.py` (delivery settings), and the
`0009_day60_delivery_runtime` + `0010_day60_runtime_schema` + `0011_day60_lease_realign` +
`0012_day60_repair_audit_attestation` migrations.

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

Eligibility predicate (all must hold): the actual release equals the caller-supplied
`affected_release_version`, the persisted dispatch-Outbox time falls in the operator's
incident `[start, end]` window (`in_time_window`, never hardcoded `True`), still `queued`,
original dispatch Outbox checkpointed, NO attempts/external evidence, `no_conflict` and
`deadline_contract_budget_valid` attested, and the repair not already applied. The schema
has no deadline/contract/budget/conflict columns, so those are EXPLICIT, auditable operator
attestations — not silent truths.

Persisted audit (`0012_day60_repair_audit_attestation`): the repair transaction writes the
operator's decision to `app.job_repair_history` — `incident_start`, `incident_end`,
`no_conflict_attested`, `deadline_contract_budget_valid_attested` — alongside `repair_id`,
`job_id`, `release_version`, and the linked `redispatch_outbox_event_id`, so the
bounded-eligibility judgement is durable, reviewable fact (not just a transient argument).

True-duplicate vs failure: on an `IntegrityError` the repair rolls back and RE-READS the
committed `job_repair_history` row for `repair_id` in a FRESH transaction. The re-read JOINs `job_repair_history`
to `outbox_events` on the FK, and only reports `already_applied` when the row MATCHES on
`job_id` / `release_version` / `reason` AND the linked Outbox row (a) exists, (b) has
`job_id` equal to this Job, and (c) has `event_type = 'job.redispatch_requested'` — a non-null
FK alone is NOT sufficient. Anything else — no row, mismatched repair facts, or a
missing/foreign/wrong-type linked Outbox row (e.g. an unrelated UNIQUE/FK violation) — returns
`repair_failed` and is NEVER disguised as an idempotent success.

## The `0009` / `0010` / `0011` / `0012` migrations and the lease triple

Additive/expand only (published revisions 0001–0008 unchanged):

- `app.outbox_events` gains nullable `relay_owner` / `relay_token` / `relay_claim_expiry`
  (Relay claim + fencing).
- `app.job_repair_history` (`repair_id` PK, `job_id` FK, `repair_reason`, `release_version`,
  `created_at`) records immutable recovery/repair facts and enforces idempotent repair.

The authoritative Worker lease is the EXISTING Day48 TRIPLE (`app.jobs.lease_owner` / `lease_token` / `lease_expires_at`, added by `0002_expand_lease` and constrained by `0003_add_lease_constraints`: `jobs_lease_triple_coherent` all-or-nothing + `jobs_running_requires_lease`). `0010_day60_runtime_schema` mistakenly added a PARALLEL `app.jobs.lease_expiry`. `0011_day60_lease_realign` is a **controlled corrective DESTRUCTIVE migration** — it `DROP COLUMN lease_expiry`, so it is NOT "additive"/"expand-only" and is NOT a production zero-downtime or expand/contract example. It is safe ONLY because that column was brand-new and had never been written (the runtime was never executed); the migration realigns the runtime to the existing triple and keeps the non-conflicting 0010 additions (`provider_dispatch_started_at`, `release_version`, the widened status CHECK adding `pending_reconciliation`, and the `job_repair_history.redispatch_outbox_event_id` UNIQUE link). **Production guidance (future, not implemented here):** to drop a live column you keep it, stop reads then writes, and remove it only after a multi-stage migration with monitoring and explicit human confirmation. `0012_day60_repair_audit_attestation` is genuinely additive: it adds nullable `job_repair_history.incident_start`/`incident_end`/`no_conflict_attested`/`deadline_contract_budget_valid_attested` so a repair persists the operator's bounded-eligibility decision (written in the same repair transaction). The guarded claim writes all three lease columns atomically (so it satisfies both CHECKs); completion/expiry-sweep/recovery all use the same triple and match `lease_token` (never mixing the token into `lease_owner`). The Day60 app requires `0012_day60_repair_audit_attestation` via an EXPLICIT `create_app(expected_revision=...)` factory
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

# 2) raw Day42 baseline -> Alembic stamp -> controlled upgrade to the Day60 head (0012_day60_repair_audit_attestation)
export DAY48_ALEMBIC_DATABASE_URL='postgresql://<user>:<local-only>@127.0.0.1:5432/<db>'
alembic -c day48_alembic/alembic.ini stamp 0001_baseline_day42
alembic -c day48_alembic/alembic.ini upgrade 0012_day60_repair_audit_attestation

# 3) readiness gate expects 0012_day60_repair_audit_attestation
export DAY60_DATABASE_URL='postgresql+asyncpg://<user>:<local-only>@127.0.0.1:5432/<db>'
uvicorn 'day60_runtime_app:create_app()' --factory --host 127.0.0.1 --port 8000

# 4) the SYNC URL for the Worker/Relay/sweeper (psycopg2) + the Redis broker
export DAY60_DATABASE_URL_SYNC='postgresql://<user>:<local-only>@127.0.0.1:5432/<db>'
export DAY60_BROKER_URL='redis://127.0.0.1:6379/0'

# 5) start the REAL processes (three terminals). Only the Relay publishes.
DAY60_DATABASE_URL="$DAY60_DATABASE_URL_SYNC"   celery -A day60_celery_app:celery_app worker --loglevel=info --concurrency=1   # Worker (acks_late/reject_on_worker_lost/prefetch 1)
DAY60_DATABASE_URL="$DAY60_DATABASE_URL_SYNC" python3 day60_relay.py              # Relay (claim->apply_async->checkpoint)
DAY60_DATABASE_URL="$DAY60_DATABASE_URL_SYNC" python3 day60_sweeper.py            # recovery sweeper

# 6) inject faults, then verify committed facts from a NEW psql connection:
#    * Relay-after-publish-before-checkpoint: kill the Relay between apply_async and the
#      published_at UPDATE (e.g. a breakpoint / SIGKILL) -> the message redelivers, but the
#      Job has exactly ONE valid guarded completion (lease_token fencing).
#    * Worker-after-claim: SIGKILL the Celery worker after the queued->running claim commits
#      but before completion -> redelivery does NOT double-execute; after lease_expires_at the
#      sweeper writes ONE redispatch intent and a NEW Attempt completes the Job.
```

`--rm` deletes the container's writable-layer data on stop; named volumes / external
databases persist by design. Disposable containers were an intentional choice here.

## Evidence captured (validation tiers)

The Day60 review added a REAL runtime (`day60_delivery_runtime.py`: `OutboxRelay`,
`run_worker_attempt`, `recovery_sweep`, `repair_early_ack`) plus the `0012_day60_repair_audit_attestation`
migration it needs (lease/marker/`release_version` columns, a widened status CHECK adding
`pending_reconciliation`, and a repair→Outbox link with a UNIQUE constraint).

What the updating agent ACTUALLY executed (`EXECUTED_LOCAL_RUNTIME`):

```text
[EXECUTED_LOCAL_RUNTIME] py_compile of every changed Python module (runtime + logic + migrations)
[EXECUTED_LOCAL_RUNTIME] pytest test_day60_delivery_recovery_logic.py + test_day60_runtime_schema_contract.py -> 34 passed
```

The pure-logic + static-contract suites prove the RULES and the runtime SQL SHAPE only
(relay ordering; guarded-claim outcome; duplicate/redelivery/expiry classification; the
recovery-sweep NEGATIVES — queued/terminal/active-lease are never swept; the shared
`> now` active / `<= now` expired lease boundary; the bounded `in_time_window` predicate;
release-filtered + windowed + attested repair eligibility + idempotent id; and a static
check that the runtime writes the FULL lease triple `lease_owner`/`lease_token`/
`lease_expires_at`, matches `lease_token` on completion, and never references the removed
`lease_expiry`). A pure-logic / static-contract pass is NOT integration evidence.

**INTEGRATION_RUNTIME NOT RERUN.** The repository updating agent has NO Docker /
PostgreSQL / Redis / Celery available, so the real Relay/Worker/recovery/repair runtime has
NOT been executed against a real database + broker in this repository state. No integration
result is claimed. The following matrix MUST be executed against the real runtime (from a
fresh database connection) before any `INTEGRATION_RUNTIME` evidence is claimed:

Required integration rerun matrix (NOT RERUN):

```text
[NOT RERUN] raw Day42 baseline -> stamp -> upgrade through 0012_day60_repair_audit_attestation; /readyz expects 0012
[NOT RERUN] a real guarded queued->running claim writes the lease triple WITHOUT tripping jobs_lease_triple_coherent / jobs_running_requires_lease
[NOT RERUN] two competing Workers on one Job -> exactly ONE claim winner
[NOT RERUN] a stale Worker with the OLD lease_token cannot complete (guarded completion returns no row)
[NOT RERUN] successful completion -> Job=succeeded + attempt_count incremented + Attempt.finished_at set + success Event(attempt_id) + lease triple cleared, consistent from a fresh connection
[NOT RERUN] Relay crash AFTER publish, BEFORE checkpoint -> message redelivered, but the Job has exactly ONE valid guarded completion
[NOT RERUN] Worker killed AFTER claim -> redelivery does NOT double-execute; after lease_expires_at the sweeper writes ONE redispatch intent and a NEW Attempt (new attempt_number) completes the Job; the old unfinished Attempt is retained as interrupted evidence
[NOT RERUN] lease_expires_at == now -> the Job IS swept (== now is expired)
[NOT RERUN] expired running + external-dispatch evidence -> job_status='pending_reconciliation', NO second Provider call
[NOT RERUN] concurrent/duplicate early-ACK repair for the same repair_id -> exactly ONE job_repair_history row + ONE linked redispatch intent; the second call returns already_applied only after re-reading a MATCHING committed row
[NOT RERUN] an UNRELATED integrity failure (not a same-repair duplicate) returns repair_failed (never a fake already_applied); the audit row stores incident_start/incident_end + the two attested booleans
[NOT RERUN] repair rejected for: a different release, out of the incident window, an existing Attempt/external evidence, an already-applied repair, or a denied attestation (conflict / deadline-contract-budget)
[NOT RERUN] a queued Job and terminal Jobs (succeeded/failed/cancelled) are NEVER redispatched by the sweeper
```

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
