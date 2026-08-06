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

Executed: `python3 -m pytest -q test_day56_provider_resilience.py` -> **31 passed**
(Python 3.10.12, pytest 7.4.3). Full `projects/ai-backend-data-layer/api/` suite -> **419 passed**. The model is Python
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
`compute_next_attempt_at(now, attempt_number, retry_after_seconds)` returns the LATER of the jittered backoff and the
Retry-After earliest time. A fleet hitting Provider 429s must NOT wake together: Retry-After is an earliest retry time,
not permission for all Workers to fire at the same instant. A synchronized retry storm / thundering herd re-amplifies
the dependency; it is NOT a cache avalanche (that is cache expiry causing backend load).

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
the persisted contract (`max_tokens / 1000 * price_per_1k_tokens`) — NOT the remaining balance. If the tenant cannot
cover the worst case, do not accept/call. On success, `settle_actual(job, actual)` records real use and RELEASES the
unused remainder back to the tenant ledger (never to the limiter). Unknown execution -> `hold_for_reconciliation`
(reservation held, never zeroed). Proven no execution -> `release_reservation`.

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
(`allow_probe`, `half_open_max_probes`). A single successful probe does NOT close the circuit or release all deferred
Jobs — `record_probe_success(needed_to_close=N)` requires several progressive successes; a failed probe re-opens.

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
Provider execution AND a still-valid deadline (a new reservation re-checks budget); Jobs with Provider evidence, or a
passed deadline, are `RECONCILE_ONLY`. `repair_redispatch` re-opens the Job to `QUEUED` (history preserved in audit) and
writes a NEW `OutboxDispatchIntent` for the Relay to publish after commit — NEVER a direct queue call.

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
| Real Celery/Redis/PostgreSQL/Provider/load/fault-injection | NOT RUN | Day57 integration owns it |

---

## 13. Schema honesty

New facts MODELED in-memory: a `deferred` status; a durable defer record (`retry_reason`, `next_attempt_at`,
`defer_count`, `deadline`); a per-Job `execution_retry_count` vs `defer_count`; a tenant cost-reservation ledger
(reserved/settled/held); and circuit/limiter coordination state. A real deployment adds the durable columns/tables via a
Day48-safe FORWARD additive migration (new status allowlist value + defer/reservation columns via a gated revision),
never a rewrite of published Alembic history. The rate limiter and circuit state are TRANSIENT coordination (Redis-like),
not durable tenant truth. Day55 guarded claim/Outbox/P1 marker and Day54 durable intents are reused.

---

## 14. Boundaries (not implemented here)

- **Day57** owns deterministic/fake-Provider contract tests, integration tests, failure injection, and recovery
  verification (real Worker kills, real broker redelivery, real limiter/circuit stores).
- **Day58** owns observability: structured logs, `job_id` / `trace_id` / `attempt_id` correlation, metrics, traces, and
  runtime evidence for these decisions.
- Real Celery, real Redis distributed limiter/circuit, real PostgreSQL, and real Provider traffic/costs are NOT RUN.
