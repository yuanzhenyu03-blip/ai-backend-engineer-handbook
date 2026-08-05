# Day55 — Celery, Worker Execution and Long-running AI Jobs (Design + Runbook)

Move accepted long-running AI Jobs from the Day50 Outbox Relay onto a **supported Celery broker transport** and
Celery Workers, WITHOUT losing durable business truth, at-least-once delivery safety, Day54 cancellation semantics, or
honest external-side-effect recovery. Reuses Day40 delivery semantics (delivery/redelivery/ACK/idempotency/poison),
Day50 Job/Outbox/Relay, Day53 strict validation, and the Day54 durable, cooperative, guarded cancellation protocol.

Runnable model: [`day55_celery_worker_execution.py`](day55_celery_worker_execution.py) +
[`test_day55_celery_worker_execution.py`](test_day55_celery_worker_execution.py).

---

## 0. Evidence label (read first)

```text
CONCEPTUAL DESIGN                                    : COMPLETED (this runbook + lesson)
LOCAL IN-MEMORY CONTROL-FLOW RUNTIME                 : RUN (pytest)
Real Celery broker (Redis/RabbitMQ) transport + Worker process : NOT RUN
Real ACK timing / redelivery / visibility timeout    : NOT RUN
Worker-loss / OOM / redelivery fault injection       : NOT RUN
Real PostgreSQL transactions/isolation / Redis        : NOT RUN
Real OpenAI SDK / network / Provider                  : NOT RUN
Day56 retry/backoff/rate-limit/cost/backpressure      : NOT IMPLEMENTED (future)
Day57 integration/failure-injection/recovery suite     : NOT IMPLEMENTED (future)
Production validation                                 : NOT RUN
```

Executed: `python3 -m pytest -q test_day55_celery_worker_execution.py` -> **36 passed**
(Python 3.10.12, pydantic 2.5.0, pytest 7.4.3). Full `projects/ai-backend-data-layer/api/` suite -> **384 passed**.
The delivery/execution/recovery control flow is Python standard library only; the guarded completion REUSES Day53's
real pydantic-backed strict validation gate (`StructuredOutputValidator` + `SchemaRegistry`) and Day54's durable
cancellation terminal mapping (semantics re-expressed in this module's `JobStatus`). The suite proves APPLICATION
CONTROL FLOW over an in-memory model; it does NOT prove a real Celery broker, a real Worker process, real
ACK/redelivery, PostgreSQL, Redis, or the real Provider. **A fake/in-memory test does not prove actual Celery ACK,
broker redelivery, Worker-loss, or PostgreSQL behavior.** Day53/Day54 evidence is not inherited.

SECURITY: no real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.
The Celery envelope carries only small, safe routing metadata (`task_name`, `envelope_version`, `job_id`, tenant id);
PostgreSQL remains authoritative for Job state, budget, tenant authority, and result truth.

---

## 1. Core mental model

```text
Outbox durable intent
  -> publish to a supported Celery broker           (publish BEFORE the checkpoint)
  -> write the Outbox published checkpoint
  -> at-least-once delivery / redelivery
  -> PostgreSQL GUARDED CLAIM decides Provider execution authority   (first duplicate-call gate)
  -> durable Attempt + correlation evidence
  -> Provider call OUTSIDE any DB transaction
  -> validate BEFORE guarded completion

unknown Provider outcome  -> PENDING_RECONCILIATION -> reservation retained -> NO blind re-call
cancel request            -> durable intent FIRST -> optional revoke -> cooperative Worker check
                          -> one guarded winner (cancelled / expired / succeeded)

Celery ACK / SUCCESS  == delivery handled           != Job business success
```

Hard boundaries kept everywhere:

```text
Celery ACK/SUCCESS             != Job succeeded
Broker redelivery              != permission to call the Provider again
Worker identity                != durable Attempt identity
Provider timeout / Worker loss != proof of no Provider execution or zero cost
Celery revoke                  != durable cancellation authority
configuration rollback         != business-fact rollback
```

---

## 2. Guarded claim is the FIRST duplicate-call gate (not lease/fencing)

`JobStore.claim_execution` models an atomic, PostgreSQL-owned guarded claim:

```text
UPDATE jobs SET status='running', lease_owner=:w, open_attempt_id=:a
WHERE job_id=:j AND status IN ('queued','running')
      AND (lease_owner IS NULL OR lease_expiry < now)
RETURNING *;
```

A one-row result gives the Worker execution authority; zero rows means STOP before the Provider call. A **lease** is
temporary ownership; a **fencing token** blocks stale durable writes but cannot prevent or undo an already-issued
Provider request. Neither is the first gate — the guarded claim is. Lease/fencing are secondary and shown only to
mark the distinction (`Job.lease_owner` / `lease_expiry`).

Claim results (`ClaimStatus`): `GRANTED` (authority) · `CONFLICT` (another live Worker holds it -> redeliver later,
do not ACK away) · `ALREADY_TERMINAL` (duplicate of a finished Job -> safe no-op ACK) · `RECONCILE_ONLY`
(`PENDING_RECONCILIATION` redelivery -> reconcile from evidence, NO Provider re-call).

**Lease expiry is not re-authorization (F1).** A lease is temporary ownership; its expiry says nothing about the
external Provider call. If the open `Attempt` already carries Provider execution evidence (at least a
`provider_request_id`), then a redelivery OR a lease-expiry re-claim — even by a new Worker — returns `RECONCILE_ONLY`
and transitions the Job to `PENDING_RECONCILIATION`; the Provider is never re-called. Only a first claim on an Attempt
with no recorded `provider_request_id` is granted execution authority.

---

## 3. Identity layers (each is a DIFFERENT thing)

```text
client_idempotency_key   = one logical API command
job_id                   = durable business fact
celery_delivery_id       = broker delivery occurrence (redelivery changes it)
worker_id                = process handling a delivery
attempt_id               = durable execution attempt
provider_request_id      = external execution evidence
provider_idempotency_key = one intended Provider call
correlation_id           = tracing / reconciliation linkage
```

Redelivery or a new Worker does NOT automatically create a new Attempt. `claim_execution` retains the open Attempt and
its `provider_idempotency_key` on redelivery; only a deliberate, durable, authorized A2 would obtain a new key. Worker
identity and broker delivery are not durable Attempt identity.

---

## 4. ACK timing and Celery task status

```text
early ACK -> Worker crash can silently LOSE the delivery (Job stuck running, no redelivery)
late ACK  -> crash can REDELIVER; the application must absorb duplicates (guarded claim dedups)
```

`AckMode.LATE` is the safe default. ACK and Celery `SUCCESS` mean delivery was reliably handled, not that the business
Job is `succeeded`. A Worker may safely ACK after recording a cancellation, a poison quarantine, a duplicate/no-op, a
`PENDING_RECONCILIATION`, or a validation refusal. `GET /jobs/{job_id}` reads the PostgreSQL durable Job state
(`JobStore`), never the Celery result backend.

---

## 5. Provider uncertainty, Worker loss, OOM, and short transactions

Persist a guarded claim, Attempt, and correlation evidence BEFORE the Provider call. Persist `provider_request_id` as
soon as it is available (`record_provider_request_id`, whose event is attributed to the REAL parent Job via the durable
`attempt_id -> job_id` path and carries `attempt_id` + `provider_request_id` + `correlation_id` as repair evidence, F3).
A long Provider call stays OUTSIDE any database transaction. If
the Provider may have run but result/cost are unknown (`ProviderResultKind.TIMEOUT`), retain the reservation
(`CostState.RECONCILIATION_PENDING`, never fabricated 0), enter `PENDING_RECONCILIATION`, and never blind re-call.

**OOM = Out Of Memory**: the OS/container may kill a Worker without allowing cleanup, so `try/except` alone is
insufficient — durable state written before the call, plus at-least-once redelivery and the guarded claim, are what
make recovery safe. A `PENDING_RECONCILIATION` redelivery returns `RECONCILE_ONLY` and calls the Provider zero times.

---

## 6. Poison vs transient failure

```text
transient failure    -> bounded retry + exponential backoff + jitter   (Day56 depth)
deterministic poison -> durable classification -> quarantine/dead-letter -> NO ordinary requeue
```

Two poison kinds, at two different points:

- **Envelope/transport poison** (`envelope_version` unsupported): the Worker cannot even parse the broker message.
  Detected BEFORE loading the Job -> dead-letter + ACK, zero Provider calls, the Job is untouched
  (`WorkerOutcome.ENVELOPE_POISON_DEADLETTER`).
- **Execution-contract poison** (persisted `execution_contract_version` unsupported): the Worker parsed the message and
  loaded the Job but cannot execute/validate the server-owned contract. Detected AFTER loading the Job -> durable
  `QUARANTINED` classification + ACK, zero Provider calls (`WorkerOutcome.CONTRACT_POISON_QUARANTINE`).

`envelope_version` answers "can the Worker parse this message?"; the persisted execution-contract version answers "can
the Worker execute and validate this Job's contract?" The envelope is small, safe routing metadata; PostgreSQL remains
authoritative. `SUPPORTED_ENVELOPE_VERSIONS` and `SUPPORTED_CONTRACT_VERSIONS` are disjoint.

A transient failure (`ProviderResultKind.TRANSIENT`) retains the Attempt + evidence and lets the delivery redeliver for
a bounded retry (`WorkerOutcome.TRANSIENT_RETRY`); the retry/backoff DEPTH belongs to Day56. It never quarantines and
never fabricates a result.

---

## 7. Day54 cancellation inside Celery

```text
authorized cancellation request
  -> COMMIT durable cancellation intent (reason/actor/timestamp/version)   (FIRST)
  -> optional Celery revoke                                                (best-effort, AFTER commit)
  -> Worker checks the durable intent at safe points
  -> GUARDED terminal result (kind-derived: user cancel -> CANCELLED, deadline -> EXPIRED)
```

`request_cancellation` persists the intent first; the optional `revoke` callable is best-effort delivery/runtime
control, NOT the business authority (it may fail or race — the durable intent still governs). Revoke is called with the
CORRECT Celery task id via the published invariant `celery_task_id == job_id` (F5): the Outbox publisher
(`OutboxRelay.relay`) stamps `envelope.celery_task_id = celery_task_id_for_job(job_id)` and asserts the invariant, so a
durable `job_id` is always sufficient to revoke the right task. The Worker observes the
intent cooperatively:

- **Pre-call**: zero Provider calls, guarded terminal transition (`WorkerOutcome.CANCELLED_PRE_CALL`). This fires in
  TWO places: a pre-claim fast path for a still-`QUEUED` Job, and — critically (F2) — a POST-CLAIM, PRE-PROVIDER re-check
  after the guarded claim succeeds, so an intent persisted while the Job was already `RUNNING` still prevents the
  Provider call.
- **Final pre-completion**: a durable intent written AFTER the last token but BEFORE completion is caught by a final
  cooperative re-check that does NOT write `succeeded` and takes the guarded cancel/expiry path
  (`WorkerOutcome.CANCELLED_PRE_COMPLETION`).
- **Mid-work**: record safe correlation evidence, best-effort abort through the Provider adapter, retain unknown cost,
  guarded terminal transition.

`terminal_for_intent` maps `USER_CANCELLATION -> CANCELLED`, `DEADLINE_EXPIRY -> EXPIRED` — the Day54 semantics,
re-expressed in this module's `JobStatus`. Completion and cancellation each use a guarded terminal write
(`UPDATE ... WHERE status IN (live) RETURNING`), so exactly ONE wins; the loser sees zero rows (`TransitionOutcome.NO_OP`)
and stops/reconciles. A crash after intent persistence is recoverable: re-observation is at-least-once and the guarded
transition absorbs repeats (second apply -> zero rows).

---

## 8. Outbox Relay ordering — publish BEFORE the checkpoint

`OutboxRelay.relay` publishes the Celery task to the broker FIRST, then writes the Outbox `published` checkpoint. A
crash in between may DUPLICATE the publish, which the Worker absorbs via the guarded claim. Checkpointing first could
silently STRAND a queued Job with no broker message. An ambiguous publish outcome is NOT success: retain/recover the
event and accept at-least-once delivery.

---

## 9. Day40 boundary

Reuse Day40 delivery SEMANTICS (at-least-once, redelivery, ACK timing, idempotency, poison), not the Day40 custom Redis
Streams / Consumer Group implementation. If Redis is chosen as the broker, use Celery's supported broker transport. Do
NOT reimplement `XADD` / `XREADGROUP` / `XACK` / pending-entry reclaim as a parallel queue, and do NOT hand-build a
Celery replacement. `CeleryBrokerSim` models only supported broker semantics (publish/deliver/redeliver/ack/visibility
timeout / dead-letter).

---

## 10. Graceful drain and rollback

`graceful_drain`: start verified new Workers, stop old Workers from taking NEW claims (`WorkerPool.stop_new_claims`),
drain in-flight work within a bound, checkpoint durably, then ACK and exit. Abandoned in-flight work redelivers
(at-least-once) rather than being lost. Force-killing Workers is NEVER normal business cancellation.

Integrated incident — an erroneous early-ACK release that can silently lose deliveries:

1. **Roll the policy back FIRST** (`ReleaseConfig.rollback`) — stops FUTURE harm only. It does NOT repair Jobs already
   committed `running` under the bad release. Configuration rollback != business-fact rollback.
2. **Build the affected set** from release version AND a bounded time window AND auditable running evidence
   (`build_affected_set` filters on `Job.running_since` within `[window_start, window_end]`, corroborated by the durable
   `execution_claimed` events; F4). A Job that became `running` OUTSIDE the window — even under the same release — is
   strictly excluded, so historical `running` Jobs are never swept into the repair. Do NOT bulk-flip `running` Jobs to
   `queued`.
3. **Classify repair from evidence** (`classify_repair`): a Job whose Attempt already has a `provider_request_id` may
   have executed at the Provider -> `RECONCILE_ONLY`, never blind re-dispatch. Only Jobs with NO Provider-execution
   evidence are safe under an explicit, guarded, audited `RECONCILE_THEN_GUARDED_REDISPATCH`. A client idempotency key
   proves logical acceptance only, not Provider execution.

---

## 11. Evidence matrix

| Claim | Tier | How shown |
|-------|------|-----------|
| Outbox publishes before the checkpoint; crash-between re-publishes (duplicate absorbed) | LOCAL CONTROL-FLOW | `test_relay_publishes_before_checkpoint`, `test_relay_crash_after_publish_still_enqueued_no_checkpoint` |
| Guarded claim is the first duplicate-call gate; duplicate of a terminal Job -> no-op, zero Provider calls | LOCAL CONTROL-FLOW | `test_guarded_claim_grants_one_row`, `test_duplicate_delivery_of_terminal_job_is_noop`, `test_claim_conflict_when_another_live_worker_holds_lease` |
| Redelivery/new Worker retains the same Attempt + provider idempotency key | LOCAL CONTROL-FLOW | `test_redelivery_retains_same_attempt_and_provider_idempotency_key`, `test_worker_identity_is_not_attempt_identity` |
| Late ACK redelivers on transient; early ACK loses the delivery | LOCAL CONTROL-FLOW | `test_late_ack_redelivers_on_transient_failure`, `test_early_ack_loses_delivery_on_crash_semantics` |
| Provider timeout -> `PENDING_RECONCILIATION`, reservation retained, `provider_request_id` recorded, no blind re-call | LOCAL CONTROL-FLOW | `test_provider_timeout_pending_reconciliation_retains_reservation`, `test_redelivery_of_pending_reconciliation_does_not_recall_provider` |
| Envelope poison dead-letters before Job load; contract poison quarantines after Job load; the two version spaces are disjoint | LOCAL CONTROL-FLOW | `test_envelope_poison_dead_letters_before_job_load`, `test_contract_poison_quarantines_after_job_load`, `test_envelope_and_contract_versions_are_disjoint_concepts` |
| Day54 cancellation: pre-call zero calls -> CANCELLED; deadline -> EXPIRED; final pre-completion prevents succeeded; revoke best-effort after commit; one guarded winner; crash re-observation idempotent | LOCAL CONTROL-FLOW | `test_pre_call_cancellation_zero_provider_calls`, `test_deadline_intent_maps_to_expired`, `test_final_pre_completion_cancellation_prevents_succeeded`, `test_revoke_is_best_effort_not_authority`, `test_completion_and_cancellation_one_guarded_winner`, `test_crash_after_intent_is_reobservable_and_idempotent` |
| Validation before guarded completion (ACK != business success) | LOCAL CONTROL-FLOW | `test_success_path_completes_and_acks`, `test_ack_success_is_not_business_success_until_guarded_complete` |
| Graceful drain stops new claims + drains bounded; config rollback != business-fact rollback; affected set no bulk flip; evidence-based repair | LOCAL CONTROL-FLOW | `test_graceful_drain_stops_new_claims_and_drains_bounded`, `test_config_rollback_is_not_business_fact_rollback`, `test_affected_set_from_release_and_no_bulk_flip`, `test_repair_reconcile_only_when_provider_evidence_exists`, `test_repair_guarded_redispatch_when_no_provider_evidence` |
| F1: lease expiry after Provider evidence -> RECONCILE_ONLY, zero re-calls | LOCAL CONTROL-FLOW | `test_f1_lease_expiry_after_provider_evidence_is_reconcile_only_no_recall`, `test_f1_claim_execution_directly_routes_reconcile_when_evidence_and_lease_expired` |
| F2: an intent persisted after a RUNNING claim blocks the Provider call (pre-Provider re-check) | LOCAL CONTROL-FLOW | `test_f2_cancellation_intent_after_running_claim_blocks_provider_call`, `test_f2_deadline_intent_after_running_claim_maps_to_expired` |
| F3: `provider_request_id_recorded` attributed to the real parent Job with repair evidence | LOCAL CONTROL-FLOW | `test_f3_provider_request_id_event_attributes_to_real_job_with_evidence` |
| F4: affected set excludes same-release running Jobs outside the window / with no running evidence | LOCAL CONTROL-FLOW | `test_f4_affected_set_excludes_same_release_running_job_outside_window`, `test_f4_affected_set_excludes_running_job_with_no_running_evidence` |
| F5: published invariant `celery_task_id == job_id`; revoke uses the invariant task id | LOCAL CONTROL-FLOW | `test_f5_published_celery_task_id_equals_job_id_invariant`, `test_f5_revoke_uses_the_invariant_task_id` |
| Real Celery broker/Worker/ACK/redelivery/visibility-timeout | NOT RUN | requires a real broker + Worker process (Day57 integration) |
| Worker-loss / OOM / fault injection | NOT RUN | requires real process kills (Day57) |
| Real PostgreSQL / Redis / Provider | NOT RUN | fakes only |

---

## 12. Schema honesty

The `cancelled`/`expired`/`pending_reconciliation`/`quarantined` statuses, a durable cancellation/expiry intent table
(reason/actor/timestamp/version), the per-Job `open_attempt_id`, and per-Attempt `provider_idempotency_key` /
`provider_request_id` / `(schema_name, schema_version)` fields are new facts MODELED in-memory. A real deployment adds
them via a **Day48-safe FORWARD additive migration** (new intent + attempt columns/tables, plus any new status
allowlist value via a gated revision) — never a rewrite of published Alembic history. Day50 Job/Outbox/Relay, Day53
guarded completion + strict validation, and the Day54 cancellation protocol are reused, not re-implemented.

---

## 13. Boundaries (not implemented here)

- **Day56** owns retry/backoff DEPTH, provider rate limits, token-cost control, backpressure, and degradation depth.
  Day55 marks a transient failure and lets it redeliver for a bounded retry, but does not implement the backoff policy.
- **Day57** owns the expanded fake-provider, contract, integration, failure-injection, and recovery-verification suite
  (Worker kill after persisted `provider_request_id` and before the terminal write, real broker redelivery, etc.).
- Real Celery, real broker (Redis/RabbitMQ), real Worker processes, real PostgreSQL/Redis, and the real Provider are
  NOT RUN.
