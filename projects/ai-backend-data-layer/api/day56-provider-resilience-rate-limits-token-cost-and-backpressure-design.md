# Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure (Design + Runbook)

Day55 decided WHO may execute one durable Job and how redelivery never re-calls the Provider (Celery moves messages;
PostgreSQL moves truth). Day56 adds the ADMISSION-TO-PROVIDER CONTROL PLANE: even a Job that HOLDS execution authority
still needs current Provider capacity, an intact cost reservation, and a healthy Provider path before an actual paid
call. Reuses Day54 durable intents, Day55 guarded claim + Outbox + P1 dispatch marker, and Day53 evidence honesty.

Runnable model: [`day56_provider_resilience.py`](day56_provider_resilience.py) +
[`test_day56_provider_resilience.py`](test_day56_provider_resilience.py).

---

## 0. Evidence label (read first)

```text
CONCEPTUAL DESIGN                                    : COMPLETED (this runbook + lesson)
LOCAL IN-MEMORY CONTROL-FLOW RUNTIME                 : RUN (pytest)
Real Celery broker/Worker                            : NOT RUN
Real Redis distributed limiter / circuit store        : NOT RUN
Real PostgreSQL transactions/isolation                : NOT RUN
Real Provider traffic / rate limits / costs           : NOT RUN
Load test / thundering-herd at scale                  : NOT RUN
Worker-kill / fault-injection integration             : NOT RUN (Day57)
Observability / runtime evidence                       : NOT IMPLEMENTED (Day58)
Production validation                                 : NOT RUN
```

Executed: `python3 -m pytest -q test_day56_provider_resilience.py` -> **54 passed**
(Python 3.10.12, pytest 7.4.3). Full `projects/ai-backend-data-layer/api/` suite -> **442 passed**. The model is Python
standard library only; it imports Day54's `IntentKind` for the durable cancellation/deadline terminal mapping. The
suite proves APPLICATION CONTROL FLOW over an in-memory model; it does NOT prove a real Celery broker/Worker, a real
Redis distributed limiter/circuit, real PostgreSQL, real Provider traffic/rate limits/costs, load behavior, Worker-kill
fault injection, or production. Day55/Day53 evidence is not inherited.

SECURITY: no real credentials, raw prompts, Document content, raw Provider payloads, or secrets are persisted or logged.
Circuit keys follow the Provider fault domain (`circuit:{provider}:{account}:{model}:{region}`) and never include keys.

---

## 1. Four different authorities (never interchangeable)

```text
guarded claim   -> execution authority for ONE durable Job          (Day55; PostgreSQL UPDATE ... RETURNING)
rate permit     -> fleet-wide Provider capacity to call NOW          (shared limiter; Redis-like coordination)
reservation     -> tenant affordability                             (durable money/token ledger; PostgreSQL)
circuit         -> Provider-health / failure-domain containment     (per provider/account/model/region)
```

A guarded claim is NOT a rate-limit permit (a claim elects a decision-maker for one Job; a permit says the whole fleet
has capacity). A limiter is NOT the budget ledger (capacity is transient coordination; money is durable tenant truth).

---

## 2. Five dispatch outcomes (executable)

`evaluate_dispatch(job, limiter, ledger, circuit, now)` returns one of:

```text
CALL      -> all four authorities agree; make the paid Provider call now (consumes one permit)
DEFER     -> no permit / circuit OPEN / limiter outage / no reservation, and NO call was made:
             persist next_attempt_at + reason + defer_count + deadline, release the Worker (NO sleep)
RECONCILE -> the external call may have executed / is UNKNOWN, or Attempt evidence exists; never blind retry
TERMINAL  -> a durable cancellation/deadline intent wins a guarded terminal transition (CANCELLED/EXPIRED)
NOOP      -> the Job is already terminal; nothing to do
```

Decision order (facts OUTRANK capacity retry): terminal/NOOP -> durable intent (TERMINAL) -> execution evidence
(RECONCILE) -> deadline (TERMINAL EXPIRED) -> circuit -> rate permit -> reservation -> CALL.

---

## 3. Bounded retry + jitter (Retry-After is an earliest floor, not a wake-all)

`backoff_delay_seconds(attempt_number, base, cap, jitter)` is exponential backoff with FULL jitter, bounded by `cap`.
`compute_next_attempt_at(now, attempt_number, retry_after_seconds)` treats Retry-After as an EARLIEST allowed time (a
floor): when the floor dominates the jittered backoff it still adds a BOUNDED random jitter ABOVE the floor, so the
result is always >= the floor but different random draws yield different times (P1-1). A fleet hitting Provider 429s
must NOT wake together: Retry-After is an earliest retry time, never permission for all Workers to fire at the same
instant, and returning the exact floor would itself be a wake-all. A synchronized retry storm / thundering herd
re-amplifies the dependency; it is NOT a cache avalanche (that is cache expiry causing backend load).

---

## 4. Shared rate limiter (fail closed on outage)

`SharedRateLimiter` models fleet capacity (`try_acquire` / `release`, `available` flag for an outage). If the shared
coordination store is unavailable, NEW paid Provider calls fail CLOSED and DEFER by default — losing the only
cross-Worker boundary means we can no longer bound fleet concurrency. Existing Job reads, cancellation, completed-result
reads, and evidence reconciliation still work. A tightly bounded emergency fail-open is an EXPLICIT policy
(`emergency_fail_open=True`), never a default bypass, and proceeds without a permit because the store is down.

---

## 5. Cost reservation ledger (worst-case; settle/release)

`TenantBudgetLedger` is durable money/token truth. `reserve_worst_case(job)` reserves the BOUNDED WORST-CASE cost from
the persisted contract — the SUM of a bounded INPUT cost and a bounded OUTPUT cost, each with its own unit price
(`max_input_tokens/1000 * input_price_per_1k + max_tokens/1000 * output_price_per_1k`) — NOT the remaining balance and
NOT output-only (P1-3). If the tenant cannot cover the worst case, do not accept/call. On success,
`settle_actual(job, actual)` returns a `SettleOutcome`: when `actual <= reserved` it settles and RELEASES the unused
remainder back to the tenant ledger (never to the limiter); when `actual > reserved` it does NOT silently overdraw the
tenant — it charges exactly the reserved amount, records `cost_overage`, sets `RECONCILIATION_PENDING`, and returns
`OVERAGE_RECONCILE` so an explicit, protected extra-charge decision handles the excess (trade-off: safety over automatic
settlement). Unknown execution -> `hold_for_reconciliation` (reservation held, never zeroed). Proven no execution ->
`release_reservation`. `reserve_worst_case` is idempotent (it never double-reserves an existing reservation). All ledger operations (`reserve_worst_case`, `has_reservation`, `settle_actual`, `release_reservation`, `hold_for_reconciliation`, `available`, `can_afford`) run under a ledger-level lock, so the affordability check + balance deduction + reservation write are ONE atomic critical section: two Jobs racing a tenant whose balance covers only one cannot both pass the check and overspend the tenant (P1 concurrency). The in-memory lock models the atomic boundary a real PostgreSQL ledger provides (`UPDATE ... WHERE available - reserved >= :amt RETURNING`, or `SELECT ... FOR UPDATE`) — it is NOT real PostgreSQL isolation, a Redis transaction, or a production guarantee.

---

## 6. Admission backpressure (before the durable Job + Outbox commit)

`admit_job(tenant_over_quota, system_unavailable)` runs BEFORE accepting a durable Job. A tenant over its own admission
policy maps to `REJECT_429_TENANT`; system-wide capacity/dependency unavailability maps to `REJECT_503_SYSTEM`
(system-wide dominates). Do NOT return 202 when the system cannot safely make the commitment, and NEVER retroactively
convert an already-accepted Job into an HTTP 429/503 — the accepted Job is observed through durable state.

---

## 7. Degradation only if the persisted contract authorizes it

`apply_authorized_degradation` returns a degraded contract ONLY when the persisted `ExecutionContract` has
`degradation_allowed=True` and the target stays at/above the authorized floor (`min_model` / `min_max_tokens`). A Worker
under load may NEVER silently reduce persisted `model` or `max_tokens`.

---

## 8. Execution certainty (a 429 is not universal proof)

`classify_execution_certainty(http_status, provider_request_id, accepted_header)` translates a vendor status into an
application-owned certainty: `DEFINITELY_NOT_ACCEPTED` (safe to ordinary-defer/retry), `MAY_HAVE_EXECUTED`, or
`UNKNOWN`. A recorded `provider_request_id` means MAY_HAVE_EXECUTED; a bare 429 is UNKNOWN (reconcile), not universal
proof nothing ran; only a clearly-not-accepted 429 (`accepted_header=False`, no request id) is DEFINITELY_NOT_ACCEPTED.
`can_ordinary_retry` is true only for DEFINITELY_NOT_ACCEPTED. In `evaluate_dispatch`, any Attempt evidence
(`provider_request_id` or the Day55 conservative dispatch marker) forces RECONCILE before any capacity gating.

---

## 9. Circuit breaker (progressive recovery, not herd release)

`CircuitBreaker` keys on the Provider fault domain (`circuit:{provider}:{account}:{model}:{region}`; no secrets).
`CLOSED` allows calls; `OPEN` durably defers new calls; `HALF_OPEN` permits only a small, bounded probe set
(`half_open_max_probes`). The dispatch gate uses the READ-ONLY `has_probe_capacity(key)` only as a cheap early-out; the probe slot is CONSUMED
via the ATOMIC, lock-guarded `try_acquire_probe(key)` at the moment of an actual CALL. Under concurrency exactly ONE of
two racing Workers wins the slot; the loser gets `False` and, if it had already taken a rate permit, RELEASES the permit
and DEFERs — so `half_open_max_probes` is never exceeded and no permit leaks (P1-1 concurrency). A Job that reaches
HALF_OPEN but then DEFERs (no rate capacity, limiter outage, or missing reservation) never consumes a probe slot, so the
circuit cannot get stuck HALF_OPEN; a no-call is never counted as a probe failure. The in-memory `CircuitBreaker` uses ONE
`threading.RLock` to guard ALL per-failure-domain state (`_state`, `_fails`, `_probes_in_flight`, `_probe_successes`), so
every read-modify-write is atomic: concurrent `record_failure` never loses a count (the circuit reliably OPENs at the
threshold) and concurrent probe success/failure never lose an in-flight decrement or overwrite a state transition. RLock
(reentrant) lets a locked method call another locked method (e.g. `state`) without deadlock. This models the atomic
critical section a real store (Redis Lua / a DB row lock) provides — it is NOT a real distributed store. A single successful probe does NOT close the circuit or
release all deferred Jobs — `record_probe_success(needed_to_close=N)` requires several progressive successes; a failed
probe re-opens immediately. Because several probes can be in flight at once, `record_probe_success` only counts toward
recovery (and may CLOSE) when the domain is STILL `HALF_OPEN`: a LATE success that returns after another probe already
failed and re-OPENed the circuit safely releases its in-flight slot but does NOT count, does NOT flip a known failure
back to `CLOSED`, and (being uncounted) does NOT carry into the next `HALF_OPEN` round — a failed probe latches `OPEN`
until an explicit new recovery round.

---

## 10. Defer accounting vs execution retry; deadline expiry

`execution_retry_count` is consumed only when a Provider call actually executed and failed; `defer_count` is the
separate no-permit-before-call budget. A capacity defer consumes NO execution retry but is bounded by the business
deadline (`_defer` never schedules `next_attempt_at` past `job.deadline`). `process_deadline` at the deadline performs a
guarded `EXPIRED` + reservation RELEASE ONLY with proof of no external execution; any evidence/uncertainty ->
`PENDING_RECONCILIATION` with the reservation HELD.

---

## 11. Incident: zero-defer bad release -> containment + evidence-based repair

A bad release set the max defer duration to zero, prematurely EXPIRING capacity-deferred Jobs.
`ReleaseConfig.rollback` stops FUTURE harm only (configuration rollback != business-fact rollback; it does not repair
committed EXPIRED Jobs). `build_capacity_expiry_affected_set` builds a BOUNDED set: same bad release AND `EXPIRED` AND
within the time window AND the capacity expiry reason AND a recorded defer (evidence) — expired history is preserved,
never bulk-flipped. `classify_incident_repair` returns `REDISPATCH_NEW_OUTBOX_INTENT` only for Jobs with proof of no
Provider execution AND a still-valid deadline; Jobs with Provider evidence, or a passed deadline, are `RECONCILE_ONLY`.
`repair_redispatch` is a GUARDED, IDEMPOTENT, AUDITED atomic decision (P1-4 + P1-2 concurrency): the repair-id claim,
every eligibility recheck, the reservation, the audit record, the status transition, and the single Outbox intent all
run inside ONE lock-guarded critical section (`_REPAIR_LOCK`), so two CONCURRENT repairs of the same id cannot both
commit — exactly one returns `REDISPATCHED` and the other `ALREADY_APPLIED`, with NO second Outbox intent and NO second
reservation. The stable repair id (`repair:{job}:{release}:{reason}`, via `repair_id_for`) is recorded on commit. The
in-memory lock models the atomic boundary a real system gets from a per-repair-id DB uniqueness/row lock (e.g.
`INSERT ... ON CONFLICT DO NOTHING`, or `SELECT ... FOR UPDATE`) — it is NOT a real DB transaction, Redis Lua, Celery,
or production guarantee. Eligibility is
re-verified at repair time — still in the affected set, still `EXPIRED`, no durable cancellation intent, deadline not
passed, no Provider-execution evidence, and a fresh worst-case reservation can be made — each with an explicit
`RepairOutcome.BLOCKED_*`. On commit it appends an audit record to `job.repair_history` (the original `EXPIRED` status is
PRESERVED, no unaudited bulk flip), re-opens the Job to `QUEUED`, makes the new reservation, and writes exactly ONE
`OutboxDispatchIntent` (carrying the `repair_id`) for the Relay to publish after commit — NEVER a direct queue call.

---

## 12. Evidence matrix

| Claim | Tier | How shown |
|-------|------|-----------|
| Bounded backoff + full jitter; Retry-After is an earliest floor (no herd) | LOCAL CONTROL-FLOW | `test_backoff_is_bounded_and_jittered`, `test_retry_after_is_earliest_floor_not_wake_all` |
| Shared limiter caps fleet concurrency; guarded claim is not a permit; CALL consumes one permit | LOCAL CONTROL-FLOW | `test_shared_limiter_caps_fleet_concurrency_across_workers`, `test_all_gates_pass_yields_call_and_consumes_one_permit` |
| No-permit-before-call -> DEFER (not FAILED/PENDING_RECONCILIATION), zero execution retry, bounded by deadline | LOCAL CONTROL-FLOW | `test_no_capacity_defers_with_zero_provider_calls_and_no_execution_retry`, `test_defer_never_scheduled_past_deadline` |
| Limiter outage fails closed by default; fail-open only as explicit policy | LOCAL CONTROL-FLOW | `test_limiter_outage_fails_closed_by_default`, `test_limiter_outage_emergency_fail_open_is_explicit_policy` |
| Worst-case reservation (not remaining balance); settle actual + release unused to the ledger; budget-blocked pre-call; missing reservation returns the permit | LOCAL CONTROL-FLOW | `test_reserve_worst_case_not_remaining_balance`, `test_settle_actual_releases_unused_money_to_ledger_not_limiter`, `test_budget_blocked_pre_call_cannot_reserve`, `test_missing_reservation_defers_and_returns_permit` |
| Admission backpressure: tenant 429 vs system 503 (system dominates) | LOCAL CONTROL-FLOW | `test_admission_backpressure_maps_429_and_503` |
| No silent degradation; authorized degradation only within the floor | LOCAL CONTROL-FLOW | `test_silent_degradation_rejected`, `test_authorized_degradation_within_floor_allowed` |
| Execution-certainty classification; evidence/marker forces RECONCILE, not CALL | LOCAL CONTROL-FLOW | `test_execution_certainty_classification`, `test_provider_evidence_forces_reconcile_not_call`, `test_dispatch_marker_only_also_reconciles` |
| Circuit OPEN defers; HALF_OPEN bounded probes (no herd); one probe success does not close | LOCAL CONTROL-FLOW | `test_circuit_open_defers_new_calls`, `test_half_open_allows_bounded_probes_not_herd_release`, `test_single_probe_success_does_not_close_circuit` |
| Cancellation/terminal outrank capacity retry; re-checked on wake | LOCAL CONTROL-FLOW | `test_cancellation_intent_outranks_capacity_retry`, `test_deferred_job_waking_to_terminal_status_is_noop` |
| Deadline expiry releases reservation only w/o evidence; else reconcile + hold | LOCAL CONTROL-FLOW | `test_deadline_expiry_releases_reservation_when_no_execution`, `test_deadline_with_execution_evidence_reconciles_and_holds_reservation` |
| Zero-defer incident: config rollback != fact rollback; bounded affected set; repair only no-evidence valid Jobs via NEW Outbox intent; evidence -> RECONCILE_ONLY | LOCAL CONTROL-FLOW | `test_config_rollback_is_not_business_fact_rollback`, `test_affected_set_bounded_by_release_window_reason`, `test_repair_redispatches_only_no_evidence_valid_jobs_via_new_outbox_intent`, `test_repair_reconcile_only_when_provider_evidence`, `test_repair_reconcile_only_when_deadline_passed` |
| P1-1: Retry-After floor keeps bounded jitter above it (different draws differ, all >= floor) | LOCAL CONTROL-FLOW | `test_retry_after_is_earliest_floor_with_jitter_above_it` |
| P1-2: HALF_OPEN probe slot not leaked on DEFER (no capacity / limiter outage / missing reservation); consumed only at CALL; later Job still probes | LOCAL CONTROL-FLOW | `test_half_open_no_capacity_defer_does_not_leak_probe_slot`, `test_half_open_limiter_outage_defer_does_not_leak_probe_slot`, `test_half_open_missing_reservation_defer_does_not_leak_probe_slot`, `test_half_open_call_consumes_probe_slot_only_on_call` |
| P1-3: worst-case reservation covers bounded input + output; actual>reserved -> protected reconciliation, tenant not overdrawn | LOCAL CONTROL-FLOW | `test_worst_case_cost_includes_bounded_input_and_output`, `test_settle_actual_over_reservation_does_not_bypass_budget` |
| P1-4: guarded idempotent repair (one Outbox intent per repair id); blocked by not-in-set / wrong-status / cancel / deadline / provider-evidence / budget; EXPIRED history preserved | LOCAL CONTROL-FLOW | `test_repair_is_idempotent_one_intent_for_duplicate_calls`, `test_repair_blocked_by_cancellation_intent`, `test_repair_blocked_by_passed_deadline`, `test_repair_blocked_by_insufficient_budget`, `test_repair_blocked_when_not_in_affected_set`, `test_repair_blocked_when_status_not_expired`, `test_repair_reconcile_only_when_provider_evidence` |
| P1-1 concurrency: two Workers race a single HALF_OPEN probe slot -> exactly one CALL, one DEFER, no permit leak (threading.Barrier) | LOCAL IN-MEMORY CONCURRENCY | `test_half_open_probe_acquire_is_atomic_under_concurrency` |
| P1-2 concurrency: two threads repair the same repair id -> exactly one REDISPATCHED + one ALREADY_APPLIED, one Outbox intent, one reservation (threading.Barrier) | LOCAL IN-MEMORY CONCURRENCY | `test_repair_is_atomic_under_concurrency` |
| Budget concurrency: two Jobs race a tenant balance that covers only one -> exactly one reservation, balance never negative, one job_id reserved (threading.Barrier); reserve idempotent per job_id | LOCAL IN-MEMORY CONCURRENCY | `test_reserve_worst_case_is_atomic_under_concurrency`, `test_reserve_worst_case_idempotent_no_double_charge`, `test_concurrent_reserve_and_settle_stay_consistent` |
| Circuit-state concurrency: N concurrent record_failure never lose a count and OPEN at the threshold; concurrent HALF_OPEN probe success/failure keep in-flight + state consistent (threading.Barrier) | LOCAL IN-MEMORY CONCURRENCY | `test_concurrent_record_failure_never_loses_count_and_opens`, `test_concurrent_probe_success_keeps_inflight_and_count_consistent`, `test_concurrent_probe_failure_reopens_and_decrements_consistently` |
| Circuit late-success: a HALF_OPEN success returning after a probe failure re-OPENed the circuit releases its slot but never counts / re-CLOSEs / carries to the next round (controlled-order + concurrent) | LOCAL IN-MEMORY CONCURRENCY | `test_late_probe_success_after_failure_does_not_close_circuit`, `test_stale_success_does_not_carry_into_next_half_open_round`, `test_concurrent_late_success_vs_failure_never_closes_a_reopened_circuit` |
| Real DB isolation / Redis Lua-transaction / Celery / production concurrency | NOT RUN | in-memory locks model the atomic boundary only |
| Real Celery/Redis/PostgreSQL/Provider/load/fault-injection | NOT RUN | Day57 integration owns it |

---

## 13. Schema honesty

New facts MODELED in-memory: a `deferred` status; a durable defer record (`retry_reason`, `next_attempt_at`,
`defer_count`, `deadline`); a per-Job `execution_retry_count` vs `defer_count`; a tenant cost-reservation ledger with
bounded input+output pricing, `reserved`/`settled`/`cost_overage`/`held` state; an audited `repair_history` trail; and
circuit/limiter coordination state. A real deployment adds the durable columns/tables via a
Day48-safe FORWARD additive migration (new status allowlist value + defer/reservation columns via a gated revision),
never a rewrite of published Alembic history. The rate limiter and circuit state are TRANSIENT coordination (Redis-like),
not durable tenant truth. Day55 guarded claim/Outbox/P1 marker and Day54 durable intents are reused.

---

## 14. Boundaries (not implemented here)

- **Day57** owns deterministic/fake-Provider contract tests, integration tests, failure injection, and recovery
  verification (real Worker kills, real broker redelivery, real limiter/circuit stores).
- **Day58** owns observability: structured logs, `job_id` / `trace_id` / `attempt_id` correlation, metrics, traces, and
  runtime evidence for these decisions.
- The concurrency tests (rate-permit / HALF_OPEN probe, guarded repair, tenant budget reservation, and CircuitBreaker
  state transitions) are LOCAL IN-MEMORY CONTROL-FLOW concurrency (Python threads + `threading.Barrier` + in-memory locks). They verify the atomic
  critical sections in THIS model; they are NOT PostgreSQL isolation, a Redis Lua/transaction, a real Celery worker
  fleet, or production concurrency validation.
- Real Celery, real Redis distributed limiter/circuit, real PostgreSQL, and real Provider traffic/costs are NOT RUN.
