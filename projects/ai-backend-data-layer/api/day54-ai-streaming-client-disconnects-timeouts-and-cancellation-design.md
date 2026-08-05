# Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation (Design + Runbook)

Separate TWO kinds of streaming and THREE independent lifecycles so a client disconnect, Provider uncertainty,
explicit cancellation, and durable Job truth cannot be confused or overwrite one another. Reuses Day53 guarded
completion, `PENDING_RECONCILIATION`, reservation retention, and unknown-usage honesty; adds a durable, auditable,
cooperative, guarded cancellation/expiry protocol.

Runnable model: [`day54_streaming_disconnects_timeouts_cancellation.py`](day54_streaming_disconnects_timeouts_cancellation.py) +
[`test_day54_streaming_disconnects_timeouts_cancellation.py`](test_day54_streaming_disconnects_timeouts_cancellation.py).

---

## 0. Evidence label (read first)

```text
CONCEPTUAL DESIGN                                   : COMPLETED (this runbook + lesson)
LOCAL IN-MEMORY CONTROL-FLOW RUNTIME                : RUN (pytest, standard-library only)
Real FastAPI / SSE wire behavior                    : NOT RUN
Real OpenAI SDK / network / Provider (token stream) : NOT RUN
Real PostgreSQL transactions/isolation / Redis      : NOT RUN
Celery Worker execution (Day55) / retry-backoff (Day56) / integration / production : NOT RUN / NOT IMPLEMENTED
```

Executed: `python3 -m pytest -q test_day54_streaming_disconnects_timeouts_cancellation.py` -> **15 passed**
(Python 3.10.12, pytest 7.4.3; module + tests are Python-standard-library only). The suite proves APPLICATION CONTROL
FLOW over an in-memory model; it does not prove real FastAPI/SSE, a real Provider token stream, PostgreSQL, Redis, or
Celery. Day53 evidence is not inherited.

SECURITY: no real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.
Provider tokens are transient and never default-persisted as JobEvents.

---

## 1. Three independent lifecycles

```text
HTTP client connection lifecycle   -> an SSE disconnect ends only THAT client's subscription
Provider request lifecycle         -> its real state/outcome/usage may stay UNKNOWN after disconnect/timeout
Durable Job lifecycle              -> a PostgreSQL-owned business fact (queued -> running -> succeeded);
                                      it does NOT auto-cancel on disconnect
```

Explicit production boundary:

```text
HTTP client disconnect
  != the Provider call necessarily stops
  != an already-persisted background Job auto-cancels
  != an already-accepted business commitment disappears
```

The student's first answer conflated the Job lifecycle with the three-lifecycle question. Correction: an SSE
disconnect ends the HTTP subscription only; the Provider request outcome can be unknown; the durable Job stays
`running` unless an explicit durable protocol changes it.

---

## 2. Two kinds of streaming

- **A. Provider token streaming** — transient chunks for ONE Provider request. Never the durable truth.
- **B. Durable Job progress/event streaming** — safe observable state for an already-persisted Job, designed for
  subscription/reconnection.
- Do NOT treat either stream as the other's durable truth. The Worker consumes the Provider token stream; the browser
  subscribes to the durable Job progress/event stream.

---

## 3. Reconnection and the persistence trade-off

- A reconnecting browser reads/subscribes to DURABLE Job state + safe progress events (`reconnect_view`), NOT a replay
  of a Provider token stream.
- Do NOT default-persist every Provider token as a `JobEvent`: it increases writes/storage, can retain
  unvalidated/partial/sensitive content, and conflicts with Day53 raw-data minimization. Persist low-frequency, SAFE
  lifecycle facts/milestones; persist the final Result Artifact only after Day53 validation + guarded completion. A
  replayable partial-text product needs an explicit separate design (minimization, access, retention, idempotency,
  cost).

---

## 4. Timeout model

- HTTP connection timeout limits a particular subscription only.
- Provider request timeout means OUR side did not receive a response in time; Provider execution, raw result, and
  usage can remain UNKNOWN.
- Durable Job deadline is a business policy and must use the durable cancellation/expiry protocol — not confused with
  either local timeout.
- A later Provider timeout cannot retroactively change the original `202` into HTTP `504`; users observe subsequent
  state through Job reads/events (`reconnect_view` returns `pending_reconciliation`).
- The Provider may have created raw output, but it has NOT created the application's `Result Artifact` — that exists
  only after a received result passes Day53 validation and wins guarded completion.
- Preserve Day53 behavior: `PENDING_RECONCILIATION`, reservation retained, no invented zero usage, no blind automatic
  re-call.

---

## 5. Explicit cancellation / deadline protocol

```text
cancel/expiry request (authorized)
  -> PERSIST a durable, auditable intent FIRST (reason, timestamp, actor/system source, version)  [Router]
  -> Worker cooperatively OBSERVES the durable intent at safe points                              [Worker]
       before the Provider call -> do NOT call the Provider; guarded terminal transition
       during a Provider stream  -> best-effort abort + stop publishing + record safe correlation; guarded transition
  -> guarded terminal transition (cancelled / expired)                                            [JobStore]
  -> observable result via the durable Job view/events
```

- The Router must NOT write `cancelled` merely because HTTP arrived (`request_cancellation` persists an intent only).
- A best-effort mid-stream Provider abort does NOT prove remote execution stopped or that cost is zero; unknown usage
  stays `reconciliation_pending`.
- A Scheduler/Worker crash after intent persistence must not lose it: a restarted Worker `scan_open_intents` /
  re-observes it. Observation is at-least-once; the guarded transition absorbs repeats (a second apply -> zero rows).
- A deadline has a DIFFERENT trigger from user cancellation but follows the SAME durable/auditable/cooperative/guarded
  constraints (`IntentKind.DEADLINE_EXPIRY`, terminal `EXPIRED`). Public terminal labels (`cancelled`/`expired`) are
  implementation-specific; do not pretend an unsupported status already exists in schema.

---

## 6. Concurrency: completion vs cancellation/expiry

- Completion and cancellation/expiry each use a guarded terminal write (`guarded_terminal_transition` — models
  `UPDATE ... WHERE status IN (live) RETURNING`). Exactly ONE wins; the loser sees zero rows and stops/reconciles
  rather than overwriting.
- A late valid Provider result AFTER a terminal cancellation/expiry cannot turn the Job into `succeeded`
  (`ingest_late_provider_result` -> `REFUSED_TERMINAL`); no Result Artifact / success overwrite follows the late path.

---

## 7. Production failure / rollback exercise (erroneous disconnect -> cancellation intent)

- Bad deployment: every SSE disconnect wrongly created a cancellation intent (`DisconnectPolicy`). FIRST roll the
  policy back to stop new harm (`policy.rollback()`) — configuration/policy rollback is NOT a business-fact rollback.
- Do NOT bulk-flip affected terminal Jobs back to `running`.
- Build the affected set from release VERSION + a bounded TIME WINDOW (`build_affected_set`; the window is the period
  the bad release was active — evidence, NOT a retry delay) + stable intent IDs.
- Retain audit history; never delete intents. For each Job inspect durable status, attempt history, Provider request
  ID/correlation ID, client idempotency key (acceptance identity only), usage/cost state, and any result evidence.
- Provider request/correlation evidence is needed to determine possible external execution; a client idempotency key
  alone does not prove Provider execution. `classify_recovery`: request id + unknown usage ->
  `RECONCILE_UNKNOWN_EXTERNAL` (retain reservation, reconcile, NEVER blind re-call); no request id ->
  `NO_PROVIDER_EXECUTION_EVIDENCE`. Any recovery/re-execution must be explicit, authorized, auditable, and
  evidence-based (out of Day54 scope).

---

## 8. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| SSE disconnect does not mutate the durable Job | RUN (in-memory) | `SubscriptionRegistry.disconnect`; Job stays `running`, no event/intent |
| Reconnect reads durable state/events, not Provider tokens | RUN (in-memory) | `reconnect_view`; safe milestones only |
| Provider timeout is non-terminal + unknown-cost reconcile | RUN (in-memory) | `record_timeout_pending` -> `PENDING_RECONCILIATION`, reservation retained, usage None |
| Router persists a durable intent only (no terminal write) | RUN (in-memory) | `request_cancellation`; Job stays `running` |
| Pre-call cancellation prevents the Provider call | RUN (in-memory) | `run_worker` -> `CANCELLED_BEFORE_CALL`, `provider.calls == 0` |
| Mid-stream cancellation is best effort, no fabricated zero cost | RUN (in-memory) | best-effort abort; `reconciliation_pending`, `settled_tokens` None |
| Completion vs cancellation race has one guarded winner | RUN (in-memory) | two threads; one WON, one ZERO_ROWS; one terminal event |
| Scheduler crash after persisted intent is recoverable | RUN (in-memory) | `scan_open_intents` + `apply_cancellation`; repeat -> zero rows |
| Terminal cancellation refuses a late valid result | RUN (in-memory) | `ingest_late_provider_result` -> `REFUSED_TERMINAL`, no artifact |
| No default per-token persistence | RUN (in-memory) | Worker completes; raw tokens never in durable events |
| Erroneous-disconnect-policy recovery refuses blind flip/re-call | RUN (in-memory) | rollback + `build_affected_set` + `classify_recovery`; 0 Provider calls, no flip |
| Real FastAPI/SSE, Provider token stream, PostgreSQL, Redis, Celery | NOT RUN | in-memory model only |

`In-memory control-flow tests do not prove real FastAPI/SSE wire behavior, a real Provider token stream, PostgreSQL
transactions/isolation, Redis, Celery Worker execution, integration, or production.`

---

## 9. Schema honesty

The durable Job facts modeled in-memory here (the `cancelled`/`expired` terminal statuses, the
`PENDING_RECONCILIATION` status, and a durable `cancellation/expiry intent` table with reason/actor/timestamp/version)
are new facts. A real deployment adds them via a **Day48-safe FORWARD additive migration** (new intent table + any new
status allowlist value via a gated revision) — NOT implemented here, and no published Alembic revision is rewritten.
The Day52 reservation/reconciliation and the Day53 guarded completion / Provider boundary are reused, not
re-implemented.

---

## 10. Boundaries preserved (not implemented here)

Day55 consumes this cancellation/lifecycle contract while adding Celery on a supported broker transport (durable
intent, cooperative checking, guarded terminal writes, ACK/redelivery/idempotency) — it must not hand-build a Celery
substitute, and no Celery runtime is claimed here. Day56 uses the timeout/cancellation distinction to decide
retry/backoff, reconciliation, rate limiting, token-cost control, and backpressure; Day54 implements NO automatic
retry. No arbitrary client-controlled cancellation, arbitrary model IDs, secrets, raw prompts, Document content, raw
Provider payloads, or real credentials are added.
