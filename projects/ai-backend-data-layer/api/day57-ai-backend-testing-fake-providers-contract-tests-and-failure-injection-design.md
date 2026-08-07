# Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection (Design + Runbook)

Day56 defined the admission-to-Provider control plane (guarded claim / rate permit / reservation / circuit -> CALL /
DEFER / RECONCILE / TERMINAL / NOOP). Day57 turns those POLICIES into REPEATABLE EVIDENCE: a deterministic controllable
Fake Provider, application-owned Adapter contracts, strict structured-output contract checks, deterministic
backoff/jitter, and failure-injection scenarios — driving the REAL Day56 functions and Day53's real validator, not
re-implementing them.

Runnable harness + tests: [`day57_testing_harness.py`](day57_testing_harness.py) +
[`test_day57_testing_harness.py`](test_day57_testing_harness.py).

---

## 0. Evidence label (read first) — FOUR tiers, kept honest

```text
CONCEPTUAL / STATIC DESIGN                                : COMPLETED (this runbook + lesson + scenario catalog)
EXECUTED LOCAL RUNTIME (in-process deterministic doubles) : RUN  (pytest + Day53 real validator)
INTEGRATION RUNTIME (real PostgreSQL)                      : NOT RUN  (real disposable PostgreSQL required)
INTEGRATION RUNTIME (real Celery broker + Worker-kill)     : NOT RUN  (real broker + Worker process + Fake Provider service required)
INTEGRATION RUNTIME (real Redis limiter/circuit)           : NOT RUN  (real Redis coordination store required)
PRODUCTION (real Provider traffic / rate limits / cost)    : NOT RUN  (no production Provider credentials authorized)
```

Note the FOUR distinct tiers: real PostgreSQL, real Celery broker/Worker-kill/redelivery, and a real Redis
limiter/circuit are INTEGRATION RUNTIME (currently NOT RUN) — they are NOT "production". Real Provider traffic and
production validation are the PRODUCTION tier. An in-process deterministic double is EXECUTED LOCAL RUNTIME and is
NEVER integration.

Executed: `python3 -m pytest -q test_day57_testing_harness.py` -> **23 passed** (Python 3.10.12, pydantic 2.5.0,
pytest 7.4.3). Full `projects/ai-backend-data-layer/api/` suite -> **465 passed**. These prove the deterministic
application state machine, the Adapter contract, and failure-injection CONTROL FLOW over in-memory doubles; they do NOT
prove real PostgreSQL rollback/isolation, real Celery broker redelivery, real Worker-kill, a real Redis limiter/circuit,
or real Provider behavior. **`pytest passed` alone is not audit-grade runtime evidence** — a real integration run must
also preserve the exact command + revision/config, the precise fault point, committed-DB-state queries via a NEW
connection, the Fake Provider cross-process call log, and broker delivery / Worker lifecycle evidence.

SECURITY: no secrets, no raw prompts, no raw Provider payloads. Any repair/audit record carries only safe decision
evidence (IDs, release/reason/policy, safe classification, timestamps, evidence presence).

---

## 1. Why testing starts from a production failure

The first scenario is a bare Provider 429: no `provider_request_id`, no reliable proof the request was not accepted. The
required contract is `PENDING_RECONCILIATION`, reservation HELD, exactly ONE Provider call, and any redelivery routed to
reconciliation — never a second call on unknown execution. A durable status alone is insufficient: a test must ALSO
assert the Provider call count stays 1 and no ordinary retry receives a new rate permit.

The recovery is driven EXPLICITLY by the Adapter's `ProviderOutcome`, not by the test guessing.
`decide_and_apply_recovery(job, ledger, outcome, now)` reads `outcome.execution_certainty`: `UNKNOWN` or
`MAY_HAVE_EXECUTED` -> persist the Day55 dispatch marker, move to `PENDING_RECONCILIATION`, HOLD the reservation, return
`RECONCILE` (a later redelivery is reconcile-only); `DEFINITELY_NOT_ACCEPTED` -> return `SAFE_RETRY` (the normal
defer/retry branch) WITHOUT reconciliation, WITHOUT a dispatch marker, and with the reservation still `RESERVED`. A
reverse test proves a positively-not-accepted 429 is never mis-routed into reconciliation.

---

## 2. Fake Provider vs integration test (do not confuse them)

A deterministic Fake Provider is an APPLICATION test harness, not a replacement for integration. `ControllableFakeProvider`
provides scripted outcomes, a cross-call `calls` count, an independent `ProviderCallLog` (that survives "Worker loss"),
optional `provider_request_id` / `accepted` evidence, and `request_received` / `release_response` gates
(`threading.Event`) so a timeout/kill window is CONTROLLED, not timed with sleeps. A Worker timeout is an APPLICATION
decision, not "the thread is still alive": `timeout_outcome_if_deadline_exceeded(provider, now, deadline)` — with a
deadline advanced via `FakeClock` — emits a `timeout`/`UNKNOWN` `ProviderOutcome` once the Provider has received the
request but returned no response by the deadline, and that outcome is routed through the SAME `decide_and_apply_recovery`
path. It proves deterministic application
semantics; a real PostgreSQL/broker/Worker/Redis integration proves real transaction, redelivery, process-loss, and
shared-coordination boundaries.

---

## 3. provider_request_id and the crash window

`provider_request_id` is STRONG execution evidence, but its ABSENCE is not proof of no execution: a Worker can crash
after the request leaves the process and before it persists the id. Day55's conservative durable
`provider_dispatch_started_at` marker forces RECONCILE in that window (verified by driving Day56 `evaluate_dispatch`
with an Attempt that has the marker but no request id). A provider idempotency key reduces risk but is neither proof of
execution nor permission to retry unknown work.

---

## 4. Adapter contract tests (application-owned typed outcome)

`ProviderAdapter.to_outcome` maps a raw Fake Provider signal to a `ProviderOutcome` — `failure_kind`,
`execution_certainty` (via Day56 `classify_execution_certainty`: DEFINITELY_NOT_ACCEPTED / MAY_HAVE_EXECUTED / UNKNOWN),
optional `provider_request_id`, safe `retry_after_seconds`, and safe metadata only. The tests assert the APPLICATION-OWNED
outcome, never raw SDK exception classes, HTTP status codes, or private SDK fields, and the Adapter never writes Job
state or cost records.

---

## 5. Schema-contract violation is not business success

The Job's persisted execution contract (`schema_name`, `schema_version`) governs result validation; current Provider
config governs NEW calls only. A syntactically valid Provider JSON result that violates the bound schema is a CONTRACT
VIOLATION (Day53's real validator returns `CONTRACT_VIOLATION`) — it must not create a Result Artifact, must not mark the
Job succeeded, and must not trigger a blind second call.

---

## 6. Late-result completion contract

`attempt_late_completion` completes a Job ONLY if it is non-terminal AND awaiting reconciliation AND the payload strictly
validates against the bound schema AND every identity matches durable evidence (`job_id` + `attempt_id` +
`correlation_id` + `provider_request_id`; a missing/None durable request id is a mismatch). A terminal CANCELLED Job
rejects even a fully matching late result WITHOUT overwriting state (`REFUSED_TERMINAL`). All refusals are
side-effect-free.

---

## 7. Deterministic backoff / jitter

Backoff/jitter tests inject a `FakeClock` and a `DeterministicRandom` sequence. They assert Retry-After is an EARLIEST
floor, every wake time is at or after it, and different controlled draws are spread — never a wake-all at the exact
Retry-After instant.

---

## 8. Failure-injection scenarios that need REAL infrastructure (NOT RUN here)

These are specified as the scenario catalog but require real, disposable, isolated infrastructure and are NOT executed
in this repository update:

- **Real PostgreSQL** — committed transaction rollback and guarded concurrent terminal transitions. Inject a failure
  after Result Artifact insertion and before cost settlement; after rollback, a NEW connection must observe no partial
  completion facts and the reservation must remain HELD; existing external evidence routes to reconciliation, not a new
  call. An ORM mock cannot prove committed facts.
- **Real Celery broker + Worker process + independent Fake Provider service** — Worker-kill recovery: prove redelivery
  and NO second external call after `provider_dispatch_started_at` is persisted; broker delivery is not business
  completion.
- **Real Redis** — limiter/circuit outage fails closed for new paid calls (Provider calls remain zero, Jobs durably
  DEFERRED with reason + bounded `next_attempt_at` + separate `defer_count`, Worker slots released,
  `execution_retry_count` unchanged); restored capacity must re-evaluate all gates and must not release a herd.
- **Cancellation-vs-completion race** — a controlled barrier/failpoint over real DB concurrency: exactly one guarded
  terminal transition wins; the loser sees zero rows and writes no conflicting Artifact/Event/status.

The harness proves the deterministic decision logic for these (via Day56 functions); it explicitly does NOT claim the
real-infrastructure behavior. `VALIDATION_MATRIX` / `not_run_claims()` encode this taxonomy in code.

---

## 9. Integrated bad-release rollback drill

A bad release classified every bare 429 as definitely-not-accepted. First CONTAIN future harm by rolling back the
mapping (config rollback != business-fact rollback). Then build a BOUNDED affected set from release version + a bounded
time window + incident reason + Attempt/defer/Event evidence. Do NOT bulk-flip EXPIRED Jobs to QUEUED. A
`provider_request_id` or a dispatch marker means RECONCILE_ONLY. Only proven-no-execution Jobs with a valid
contract/deadline/budget and no durable cancellation intent may undergo guarded, audited repair via ONE new Outbox
intent. Repair is a distinct durable decision, not an Attempt identity: a stable `repair:{job_id}:{release_version}:defer_deadline_expired`
id is claimed atomically, so a duplicate/concurrent repair receives `ALREADY_APPLIED` and creates neither a second
reservation nor a second Outbox intent (verified by driving Day56 `repair_redispatch` from two threads).

---

## 10. Repair-history schema (forward-additive DESIGN only — not migrated)

The current Day56 in-memory model records repair history (`was_status`, `repair_id`, `repaired_at`, `reason`) and an
Outbox intent (`job_id`, `created_at`, `reason`, `repair_id`). A real deployment SHOULD add a forward-additive, auditable
`job_repair_history`-style table with a UNIQUE `repair_id` and a separate Outbox event, via a Day48-safe gated migration.
This table and migration are NOT implemented; this section is design only and must not be claimed as existing.

---

## 11. Evidence matrix (what the suite proves vs what is NOT RUN)

| Claim | Tier | How shown |
|-------|------|-----------|
| Deterministic backoff/jitter; Retry-After is an earliest floor, controlled draws spread (no wake-all) | EXECUTED LOCAL | `test_deterministic_backoff_jitter_retry_after_is_floor_not_wake_all` |
| Adapter delivers application-owned typed outcomes + execution certainty; no raw HTTP status / SDK leakage; never writes Job/cost | EXECUTED LOCAL | `test_adapter_classifies_execution_certainty_without_sdk_leakage`, `test_adapter_does_not_touch_job_or_cost` |
| Valid JSON violating the bound schema is a contract violation, not success | EXECUTED LOCAL | `test_valid_json_that_violates_bound_schema_is_contract_violation` |
| Dispatch marker / request-id evidence forces RECONCILE, no second call, reservation HELD | EXECUTED LOCAL | `test_dispatch_marker_forces_reconcile_only_no_second_call`, `test_provider_request_id_evidence_forces_reconcile_only` |
| End-to-end bare-429 -> Adapter `ProviderOutcome(UNKNOWN)` -> `decide_and_apply_recovery` -> PENDING_RECONCILIATION + HELD + exactly one call + no new permit + reconcile-only redelivery | EXECUTED LOCAL | `test_bare_429_end_to_end_application_recovery_chain` |
| DEFINITELY_NOT_ACCEPTED is NOT routed to reconciliation (safe defer/retry; no marker; reservation stays RESERVED) | EXECUTED LOCAL | `test_definitely_not_accepted_is_not_routed_to_reconciliation` |
| Controlled Worker-timeout-after-receipt: an injected-deadline timeout `ProviderOutcome` drives the SAME decision -> PENDING_RECONCILIATION + HELD + no 2nd call (gated, no sleep) | EXECUTED LOCAL | `test_timeout_after_receipt_drives_recovery_via_application_decision` |
| Controllable Fake Provider gate opens a deterministic timeout window (no sleep); receipt recorded | EXECUTED LOCAL | `test_controllable_fake_provider_gate_opens_a_deterministic_timeout_window`, `test_timeout_after_receipt_is_not_proof_of_no_execution` |
| Late-result completes only on full identity + schema match; terminal CANCELLED rejects a matching result | EXECUTED LOCAL | `test_late_result_completes_only_on_full_match`, `test_late_result_rejected_*`, `test_terminal_cancelled_job_rejects_matching_late_result` |
| Limiter outage fails closed: DEFER, zero calls, execution_retry_count unchanged | EXECUTED LOCAL | `test_limiter_outage_fails_closed_defers_zero_calls_unchanged_execution_retry` |
| Deadline: no evidence -> EXPIRED + release; marker -> PENDING_RECONCILIATION + HELD | EXECUTED LOCAL | `test_deadline_without_evidence_expires_and_releases_reservation`, `test_deadline_with_marker_holds_reservation_and_reconciles` |
| Admission backpressure: 503 dominates 429 | EXECUTED LOCAL | `test_admission_backpressure_503_dominates_429` |
| Guarded idempotent repair under concurrency: one Outbox intent per repair id; provider evidence -> RECONCILE_ONLY | EXECUTED LOCAL | `test_repair_is_idempotent_under_concurrency_one_outbox_intent`, `test_repair_with_provider_evidence_is_reconcile_only` |
| Independent Provider call log survives "Worker loss" | EXECUTED LOCAL | `test_provider_call_log_is_independent_of_job_store` |
| Honest evidence taxonomy: integration (PostgreSQL/Celery/Redis) vs production tiers, all NOT RUN; repair table design-only | EXECUTED LOCAL | `test_validation_matrix_separates_integration_from_production_and_marks_not_run` |
| Real PostgreSQL committed rollback + guarded concurrent terminal transition | INTEGRATION RUNTIME — NOT RUN | needs a real disposable PostgreSQL |
| Real Celery broker redelivery + Worker-kill (no 2nd call after dispatch marker) | INTEGRATION RUNTIME — NOT RUN | needs a real broker + Worker process + Fake Provider service |
| Real Redis limiter/circuit outage + restored-capacity no-herd | INTEGRATION RUNTIME — NOT RUN | needs a real Redis coordination store |
| Real Provider traffic / cost / rate limits | PRODUCTION — NOT RUN | no production Provider credentials authorized |

---

## 12. Boundaries

- Day57 VERIFIES the Day43–Day56 policies and INJECTS failures. **Day58** owns structured observability integration
  (structured logs, `job_id` / `trace_id` / `attempt_id` correlation, metrics, traces, runtime evidence) and the Phase 4
  capstone — not implemented here.
- Day59 begins Playwright runtime work on the Phase 4 backend; its future Browser Worker depends on a backend whose
  durable state, redelivery, and failure-recovery rules have been TESTED (the real-infra tiers above) rather than merely
  described.
