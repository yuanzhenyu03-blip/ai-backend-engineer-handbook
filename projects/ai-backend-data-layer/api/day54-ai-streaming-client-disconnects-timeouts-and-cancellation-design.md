# Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation (Design + Runbook)

Separate TWO kinds of streaming and THREE independent lifecycles so a client disconnect, Provider uncertainty,
explicit cancellation, and durable Job truth cannot be confused or overwrite one another. Reuses Day52
reservation/reconciliation and Day53 guarded completion / Provider boundary / strict validation; adds a durable,
auditable, cooperative, guarded cancellation/expiry protocol.

Runnable model: [`day54_streaming_disconnects_timeouts_cancellation.py`](day54_streaming_disconnects_timeouts_cancellation.py) +
[`test_day54_streaming_disconnects_timeouts_cancellation.py`](test_day54_streaming_disconnects_timeouts_cancellation.py).

---

## 0. Evidence label (read first)

```text
CONCEPTUAL DESIGN                                   : COMPLETED (this runbook + lesson)
LOCAL IN-MEMORY CONTROL-FLOW RUNTIME                : RUN (pytest)
Real FastAPI / SSE wire behavior                    : NOT RUN
Real OpenAI SDK / network / Provider (token stream) : NOT RUN
Real PostgreSQL transactions/isolation / Redis      : NOT RUN
Celery Worker execution (Day55) / retry-backoff (Day56) / integration / production : NOT RUN / NOT IMPLEMENTED
```

Executed: `python3 -m pytest -q test_day54_streaming_disconnects_timeouts_cancellation.py` -> **27 passed**
(Python 3.10.12, pydantic 2.5.0, pytest 7.4.3). The streaming/lifecycle/cancellation control flow is standard-library
only; the late-result path REUSES Day53's real pydantic-backed strict validation gate (`StructuredOutputValidator` +
`SchemaRegistry`), so pydantic is a dependency (as in Day53) and Day53's guarantees are not weakened. The suite proves
APPLICATION CONTROL FLOW over an in-memory model; it does not prove real FastAPI/SSE, a real Provider token stream,
PostgreSQL, Redis, or Celery. Day53 evidence is not inherited.

SECURITY: no real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.
Provider tokens are transient and never default-persisted as JobEvents; `provider_request_id` is safe correlation
evidence only.

---

## 1. Two kinds of streaming

- **A. Provider token streaming** (`FakeProviderStream`) — transient chunks for ONE Provider request. Never the durable
  truth.
- **B. Durable Job progress/event streaming** — safe observable state for an already-persisted Job, designed for
  subscription/reconnection (`JobStore` events + `reconnect_view`).
- Do NOT treat either as the other's durable truth, and do NOT default-persist raw Provider tokens as `JobEvent`s
  (write/storage cost + unvalidated/partial/sensitive content + Day53 raw-data minimization). Persist only
  low-frequency SAFE lifecycle milestones; persist the final Result Artifact only after Day53 validation + guarded
  completion.

---

## 2. Three independent lifecycles

```text
HTTP client connection lifecycle   -> an SSE disconnect ends only THAT client's subscription (SubscriptionRegistry)
Provider request lifecycle         -> its real state/outcome/usage may stay UNKNOWN after a disconnect/timeout
durable Job lifecycle              -> a PostgreSQL-owned business fact; it does NOT auto-cancel on disconnect (JobStore)
```

Explicit boundary:

```text
HTTP client disconnect
  != the Provider call necessarily stops
  != an already-persisted background Job auto-cancels
  != an already-accepted business commitment disappears
```

`SubscriptionRegistry.disconnect` ends a subscription and NEVER touches the `JobStore`; a reconnecting browser reads
durable state + safe events via `reconnect_view`, not a Provider token replay.

---

## 3. Timeout

- Provider request timeout -> `record_timeout_pending` moves the Job to a NON-terminal `PENDING_RECONCILIATION`.
- The Day52 reservation is RETAINED; unknown usage is never fabricated as `0`; there is no blind Provider re-call.
- The original `202` is NOT retroactively an HTTP `504`; later state is observed through Job reads/events
  (`reconnect_view` shows `pending_reconciliation`).
- The Provider may have raw output, but it does NOT create the application's Result Artifact — only Day53 validation +
  guarded completion creates that.

---

## 4. Cancellation / deadline protocol (durable, auditable, cooperative, guarded)

```text
authorized cancel/expiry request
  -> Router persists a DURABLE, auditable intent FIRST (reason, timestamp, actor/system source, version)  [request_cancellation]
     (the Router must NOT write `cancelled` merely because HTTP arrived)
  -> a cooperative Worker OBSERVES the intent at safe points                                              [run_worker]
  -> a GUARDED terminal transition owns the terminal fact                                                 [JobStore]
  -> observable result via the durable Job view/events
```

- The terminal fact is DERIVED from the intent kind (`terminal_for_intent`): `USER_CANCELLATION -> CANCELLED`,
  `DEADLINE_EXPIRY -> EXPIRED`. This mapping applies CONSISTENTLY to the pre-call check, the mid-stream check, the final
  pre-completion check, and crash re-observation (`apply_cancellation` derives the target from the open intent).
- Pre-call: if an intent exists, the Worker does NOT call the Provider (zero Provider calls) and takes the guarded
  terminal transition.
- Mid-stream: best-effort `stream.abort()` + stop publishing tokens + record safe correlation; hold
  `reconciliation_pending` (this does NOT prove remote stop or zero cost). Then a guarded terminal transition.
- A deadline shares the same durable/auditable/cooperative/guarded constraints with a different trigger.

---

## 5. Provider request ID (recovery evidence)

- As soon as the Provider request/stream opens, `record_provider_request_id` persists the safe `provider_request_id`
  to protected Job execution evidence — BEFORE consuming tokens / handling cancellation / handling timeout.
- This is durable external-execution evidence: a later mid-stream cancellation or timeout then classifies as
  `RECONCILE_UNKNOWN_EXTERNAL`, not `NO_PROVIDER_EXECUTION_EVIDENCE`. It is safe correlation metadata, never a raw
  prompt/payload/token.

---

## 6. Completion race

```text
token loop ends
  -> FINAL cooperative durable-intent re-check (run_worker)
     if an intent now exists -> do NOT write `succeeded`; take the guarded cancel/expiry terminal path (CANCELLED_PRE_COMPLETION)
     else                    -> guarded_complete_success (running/pending -> succeeded, atomic with artifact + cost)
```

- Completion and cancellation/expiry each use a guarded terminal write (`UPDATE ... WHERE status IN (live) RETURNING`,
  modeled by a lock). Exactly ONE wins; the loser sees zero rows (`ZERO_ROWS`) and stops/reconciles rather than
  overwriting.
- `guarded_complete_success` writes the SUCCEEDED status + Result Artifact + cost in ONE critical section, so
  duplicate/concurrent completions produce the fact at most once.

---

## 7. Late result (reuses Day53 identity binding + strict validation)

`ingest_late_provider_result` is the EQUIVALENT minimal control-flow abstraction of Day53's `ingest_late_outcome`, NOT
a weaker one. It NEVER calls the Adapter/transport. A late result completes the Job ONLY when ALL hold:

- the Job is NON-terminal AND awaiting reconciliation (`PENDING_RECONCILIATION`);
- `job_id` + `attempt_id` + `correlation_id` + `provider_request_id` match the persisted execution/attempt evidence
  (a MISSING id is as invalid as a DIFFERENT one);
- the payload passes the Day53 strict `StructuredOutputValidator` gate for the Job's bound `(schema_name,
  schema_version)` execution contract.

Otherwise it is a SIDE-EFFECT-FREE refusal — no status/cost/Result Artifact/event change and no Provider call:

```text
unknown/mismatched job/attempt/correlation/provider_request_id -> REFUSED_IDENTITY_MISMATCH
Job not awaiting reconciliation                                 -> REFUSED_NOT_AWAITING
terminal Job (cancelled/expired/succeeded/failed)              -> REFUSED_TERMINAL (guarded no-op)
payload fails the Day53 strict gate                            -> REFUSED_INVALID_PAYLOAD
matched + validated                                            -> guarded_complete_success -> COMPLETED (at most once)
```

Duplicate/concurrent matched deliveries complete the fact AT MOST ONCE via the guarded transition (a later duplicate
then hits a terminal Job -> `REFUSED_TERMINAL`).

---

## 8. Incident rollback (erroneous SSE-disconnect -> cancellation intent)

- Bad deployment: every SSE disconnect wrongly created a cancellation intent (`DisconnectPolicy`). FIRST roll the
  policy back to stop new harm (`policy.rollback()`) — configuration/policy rollback is NOT a business-fact rollback.
- Do NOT bulk-flip affected terminal Jobs back to `running`.
- Build the affected set from release VERSION + a bounded TIME WINDOW (`build_affected_set`; the window is the period
  the bad release was active — evidence, NOT a retry delay) + stable intent IDs. Retain audit history; never delete
  intents.
- A client idempotency key proves logical Job ACCEPTANCE only, NOT Provider execution. `classify_recovery`: a
  `provider_request_id` present with unknown usage -> `RECONCILE_UNKNOWN_EXTERNAL` (retain reservation, reconcile,
  NEVER a blind state flip or Provider re-call); no request id -> `NO_PROVIDER_EXECUTION_EVIDENCE`. Any
  recovery/re-execution must be explicit, authorized, auditable, and evidence-based (out of Day54 scope).

---

## 9. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| SSE disconnect does not mutate the durable Job | RUN (in-memory) | `SubscriptionRegistry.disconnect`; Job stays `running`, no event/intent |
| Reconnect reads durable state/events, not Provider tokens | RUN (in-memory) | `reconnect_view`; safe milestones only; raw tokens never persisted |
| Provider timeout is non-terminal + unknown-cost reconcile | RUN (in-memory) | `record_timeout_pending` -> `PENDING_RECONCILIATION`, reservation retained, usage None |
| Router persists a durable intent only (no terminal write) | RUN (in-memory) | `request_cancellation`; Job stays `running` |
| Pre-call cancellation prevents the Provider call | RUN (in-memory) | `run_worker` -> `CANCELLED_BEFORE_CALL`, `provider.calls == 0` |
| Mid-stream cancellation is best effort, no fabricated zero cost | RUN (in-memory) | best-effort abort; `reconciliation_pending`, `settled_tokens` None |
| Deadline intent -> EXPIRED; user cancel -> CANCELLED (all paths) | RUN (in-memory) | `terminal_for_intent`; pre-call/mid-stream/pre-completion/crash re-observation |
| provider_request_id persisted at request open | RUN (in-memory) | `record_provider_request_id`; mid-stream cancel/timeout -> RECONCILE_UNKNOWN_EXTERNAL |
| Intent after last token, before completion -> not succeeded | RUN (in-memory) | final cooperative check -> `CANCELLED_PRE_COMPLETION`, no success artifact |
| Completion vs cancellation race has one guarded winner | RUN (in-memory) | two threads; one WON, one ZERO_ROWS; one terminal event |
| Scheduler crash after persisted intent is recoverable | RUN (in-memory) | `scan_open_intents` + `apply_cancellation`; repeat -> zero rows |
| Late result reuses Day53 identity binding + strict validation | RUN (in-memory) | `ingest_late_provider_result`: matched+validated completes once; mismatch/missing-id/not-awaiting/invalid -> side-effect-free refusal; terminal -> `REFUSED_TERMINAL`; duplicate/concurrent -> at most once; 0 Provider calls |
| Erroneous-disconnect-policy recovery refuses blind flip/re-call | RUN (in-memory) | rollback + `build_affected_set` + `classify_recovery`; 0 Provider calls, no flip |
| Real FastAPI/SSE, Provider token stream, PostgreSQL, Redis, Celery | NOT RUN | in-memory model only |

`In-memory control-flow tests do not prove real FastAPI/SSE wire behavior, a real Provider token stream, PostgreSQL
transactions/isolation, Redis, Celery Worker execution, integration, or production.`

---

## 10. Schema honesty

The durable facts modeled in-memory here — the `cancelled`/`expired`/`pending_reconciliation` `JobStatus` values, a
durable cancellation/expiry intent table (reason/actor/timestamp/version), and the per-Job `attempt_id` + bound
`(schema_name, schema_version)` execution-contract fields used for late-result identity binding — are new facts. A real
deployment adds them via a **Day48-safe FORWARD additive migration** (new intent table + any new status allowlist value
via a gated revision) — NOT implemented here, and no published Alembic revision is rewritten. The Day52
reservation/reconciliation and the Day53 guarded completion / Provider boundary / strict validation gate are reused,
not re-implemented.

---

## 11. Boundaries preserved (not implemented here)

Day55 consumes this cancellation/lifecycle contract while adding Celery on a supported broker transport (durable
intent, cooperative checking, guarded terminal writes, ACK/redelivery/idempotency) — it must not hand-build a Celery
substitute, and no Celery runtime is claimed here. Day56 uses the timeout/cancellation distinction to decide
retry/backoff, reconciliation, rate limiting, token-cost control, and backpressure; Day54 implements NO automatic
retry. No arbitrary client-controlled cancellation, arbitrary model IDs, secrets, raw prompts, Document content, raw
Provider payloads, or real credentials are added.
