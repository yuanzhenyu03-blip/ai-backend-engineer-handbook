# Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day55 — Celery, Worker Execution and Long-running AI Jobs
Previous Lesson: Day55 — Celery, Worker Execution and Long-running AI Jobs
Next Lesson: Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection
Engineering Artifact: projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md
  + runnable day56_provider_resilience.py + test_day56_provider_resilience.py (in-memory control flow; 45 passed)
```

Main engineering artifact: a provider-neutral in-memory model of the admission-to-Provider control plane — bounded
retry + jitter, a shared rate limiter, a tenant cost-reservation ledger, a circuit breaker, admission backpressure, an
execution-certainty classifier, and the `CALL | DEFER | RECONCILE | TERMINAL | NOOP` dispatch decision (standard-library
control flow; imports Day54's `IntentKind`), plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Separate** four authorities: the guarded claim (execution), the rate permit (fleet capacity), the reservation
  (tenant affordability), and the circuit (Provider health).
- **Diagnose** a fleet-wide Provider-429 retry storm and distinguish it from a cache avalanche.
- **Design** bounded exponential backoff with jitter and treat Retry-After as an earliest floor, not a wake-all.
- **Classify** a no-permit-before-call as a durable DEFER, never FAILED or PENDING_RECONCILIATION.
- **Default** a shared-limiter outage to fail closed for new paid calls, with fail-open only as an explicit policy.
- **Reserve** the bounded worst-case cost at acceptance and settle/release actual use against the tenant ledger.
- **Place** backpressure before the durable Job + Outbox commit and map tenant 429 vs system-wide 503.
- **Classify** a Provider 429 by execution certainty, not status code alone; route unknown execution to reconciliation.
- **Design** OPEN/HALF_OPEN progressive circuit recovery instead of a herd release.
- **Recover** a zero-defer bad rollout with configuration containment, a bounded evidence set, per-Job classification,
  guarded audited repair, and a new Outbox dispatch intent.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day55 made execution reliable, but reliability alone will happily melt a Provider. Point 200 Workers at one model and
the first burst of 429s triggers a synchronized retry storm that re-amplifies the overload; a naive "retry on 429" is a
self-inflicted outage. Meanwhile the money side is just as dangerous: reserve the wrong amount and you either
double-book a tenant's budget or let expensive Jobs run for free; treat a 429 as "definitely didn't run" and you
silently drop paid work or double-bill on retry. Day56 is the control plane that decides, for a Job that already holds
execution authority, whether it SHOULD, CAN, and can AFFORD to call the Provider right now — and what to do (defer,
reconcile, expire) when the answer is no. Getting this wrong shows up as retry storms, runaway spend, unbounded queues,
silent quality degradation, and fabricated zero-cost records.

---

## 4. Roadmap Position

```text
Day53 Provider boundary + strict validation
Day54 durable cooperative cancellation
Day55 supported-Celery Worker execution (Celery moves messages; PostgreSQL moves truth)
        |
        v
Day56 admission-to-Provider control plane: capacity, cost, backpressure, resilience   <-- you are here
        |
        v
Day57 fake/deterministic Providers, contract tests, integration, failure injection
        |
        v
Day58 observability + runtime evidence + Phase 4 capstone
```

### Knowledge continuity

```text
Previous Knowledge
  Day55 guarded claim + Outbox + P1 dispatch marker; Day54 durable intents; Day53 evidence honesty
        |
        v
Current Lesson Concept
  A Job with execution authority still needs a rate permit, an intact reservation, and a healthy circuit
  before a paid call; no-permit is a durable DEFER; unknown execution is RECONCILE; backpressure precedes 202
        |
        v
Future Production Usage
  Day57 verifies these policies with fake Providers + failure injection; Day58 makes them observable
```

Prerequisites and reused mental models: **Day55** guarded claim (execution authority) + Outbox + the P1 conservative
dispatch marker; **Day54** durable cancellation/deadline intents and `terminal_for_intent`; **Day53** "missing evidence
is not proof of no execution." Day57 depends on Day56 to have policies worth testing; Day58 depends on it to have
decisions worth observing.

---

## 5. Lesson Map

```text
retry storm != cache avalanche
  -> bounded backoff + jitter (Retry-After = earliest floor)
  -> four authorities: guarded claim | rate permit | reservation | circuit
  -> five outcomes: CALL | DEFER | RECONCILE | TERMINAL | NOOP
  -> no-permit -> durable DEFER (next_attempt_at, no worker sleep, bounded by deadline)
  -> limiter outage -> fail closed (fail-open only explicit)
  -> reservation: worst-case at acceptance -> settle actual -> release unused
  -> backpressure before 202: tenant 429 vs system 503
  -> 429 by execution certainty (unknown -> reconcile)
  -> circuit OPEN/HALF_OPEN progressive probes
  -> deadline expiry: release only w/o evidence, else reconcile
  -> zero-defer incident: rollback + bounded evidence + guarded repair + new Outbox intent
```

---

## 6. Core Mental Model

```text
guarded claim  = who may execute THIS Job          (Day55; PostgreSQL)
rate permit    = may the FLEET call now             (shared limiter; Redis-like)
reservation    = can the TENANT afford it           (durable ledger; PostgreSQL)
circuit        = is the PROVIDER path healthy        (per provider/account/model/region)

CALL      = all four agree
DEFER     = not now, no call made (durable next_attempt_at; no worker sleep)
RECONCILE = it may already have run (unknown) — never blind retry
TERMINAL  = a durable cancel/deadline intent wins a guarded transition
NOOP      = already terminal
```

Day55 answered "who may execute and how not to double-call on redelivery." Day56 answers "even so, should we, can we,
and can we afford to call the Provider right now?" A claim is not a permit; a limiter is not a ledger.

---

## 7. Main Concepts

### Concept 1: Retry storm is not a cache avalanche

**Tech Lead Question:** 200 Workers get Provider 429s and all retry. What is failing, and is this a cache avalanche?

**Student Thinking / Answer:** "不应该会导致缓存雪崩" — the student saw the synchronized amplification but reached for
cache-avalanche terminology.

**Tech Lead Review:** Right instinct, wrong name. A **cache avalanche** is cache expiry dumping load on the backend. A
**retry storm / thundering herd** is failed requests retrying together and re-amplifying the dependency. The fix is
bounded exponential backoff with FULL jitter, and treating `Retry-After` as an EARLIEST retry time — never permission
for every Worker to wake at the same instant.

**Engineering Thinking:** `compute_next_attempt_at` treats Retry-After as an EARLIEST floor and adds a bounded random
jitter ABOVE it — the result is always >= the floor but different Workers get different times. Returning the exact floor
would itself be a wake-all.

**Production Example:** Without jitter, `Retry-After: 30` makes all 200 Workers fire at exactly t+30 and re-trip the
limit. With jitter above the floor they each wake at t+30+rand, spread across a bounded window.

### Concept 2: A guarded claim is not a rate permit

**Tech Lead Question:** The Worker already won the guarded claim. Doesn't that mean it may call the Provider?

**Student Thinking / Answer:** "跨worker共享边界" — the student identified the shared coordination boundary.

**Tech Lead Review:** Correct. The **PostgreSQL guarded claim** decides who may execute ONE durable Job (it prevents
two Workers double-calling for the same Job). A **shared/distributed limiter** decides whether the whole fleet has
capacity to call NOW (it prevents different Jobs together blowing the RPM/TPM/concurrency limit). A claim is not a
permit; they have different owners and different jobs.

**Production Example:** `SharedRateLimiter(capacity=3)`: five Workers each holding a claim for a different Job still get
only three permits; the other two DEFER.

### Concept 3: No permit before a call is a durable DEFER

**Tech Lead Question:** No permit exists before the call. FAILED? PENDING_RECONCILIATION?

**Student Thinking / Answer:** "是一个可恢复的'等待容量/延迟重试'状态" — a recoverable wait-for-capacity state.

**Tech Lead Review:** Correct. Persist a durable defer decision (`retry_reason`, `next_attempt_at`, `defer_count`,
`deadline`) and RELEASE the Worker — do not sleep in the Worker, do not mark the Job failed, and do not mark it
`PENDING_RECONCILIATION` (nothing external happened). A no-permit defer consumes NO execution-retry budget; it uses a
separate bounded defer budget, and `next_attempt_at` is never scheduled past the business deadline.

**Production Example:** `evaluate_dispatch` with `capacity=0` returns `DEFER/no_rate_capacity`, sets `DEFERRED`,
`defer_count=1`, `execution_retry_count=0`.

### Concept 4: Fail closed when the shared limiter is unavailable

**Tech Lead Question:** The shared limiter is down. Keep calling?

**Student Thinking / Answer:** "继续调用provider" — the student first chose fail-open because calls "look available."

**Tech Lead Review:** Corrected to default fail CLOSED for NEW paid calls. Losing the only cross-Worker coordination
boundary means you can no longer bound fleet concurrency, so a burst would melt the Provider. Reads, cancellation,
completed-result reads, and reconciliation still work. A tightly bounded emergency fail-open is an EXPLICIT policy,
never a silent default.

**Production Example:** `limiter.available=False` -> `DEFER/limiter_unavailable_fail_closed`; only
`emergency_fail_open=True` proceeds (without a permit, since the store is down).

### Concept 5: Reserve the worst case; a limiter is not the budget ledger

**Tech Lead Question:** How much budget do you reserve for a Job?

**Student Thinking / Answer:** "500 token" (remaining budget) and, on release, "应该回归到limiter."

**Tech Lead Review:** Two corrections, plus a precision. Reserve the Job's BOUNDED WORST-CASE cost from the persisted
contract, not the remaining balance — if the budget cannot cover the worst case, do not call. The worst case must cover
BOTH sides of a real AI request: a bounded input (prompt) cost AND a bounded output (completion) cost, each with its own
unit price (`max_input_tokens * input_price + max_tokens * output_price`), not output alone. And unused financial
reservation returns to the durable TENANT COST LEDGER, not the rate limiter. Reserve at acceptance; on success settle
actual use and release the unused remainder — and if actual somehow exceeds the reservation, never silently overdraw the
tenant: charge exactly what was reserved, record the overage, and enter a protected reconciliation for the excess.

**Production Example:** input 1000 tok @ 0.03 + output 500 tok @ 0.06 -> worst case 0.06 reserved; actual 0.04 -> 0.02
returned. If actual came back 0.09 (> 0.06), `settle_actual` returns `OVERAGE_RECONCILE`, charges 0.06, records
`cost_overage=0.03`, and holds it for a protected extra-charge decision.

### Concept 6: Backpressure before 202; degrade only if authorized

**Tech Lead Question:** The system is overloaded. Where do you push back, and can a Worker just shrink `max_tokens`?

**Student Thinking / Answer:** "创建 Job 之前拒绝/限速该请求" and "不能，worker只是执行者."

**Tech Lead Review:** Both correct. Backpressure belongs BEFORE the durable Job + Outbox commit: a tenant over its own
quota maps to 429, system-wide unavailability maps to 503, and you never return 202 for a commitment you cannot keep —
nor retroactively turn an accepted Job into a 429/503. And a Worker may NEVER silently reduce persisted `model` or
`max_tokens`; degradation is allowed only when the persisted, product-authorized contract explicitly permits it (down to
a floor).

**Production Example:** `admit_job(system_unavailable=True)` -> 503 (dominates); `apply_authorized_degradation` raises
unless `degradation_allowed` and the target is at/above `min_model`/`min_max_tokens`.

### Concept 7: 429 by execution certainty; circuit progressive recovery; incident repair

**Tech Lead Question:** A 429 came back — did the Provider execute? And how do you recover a Provider that keeps
failing, or a bad release that expired everything?

**Student Thinking / Answer:** "durable fact / cancellation" (these can't be ordinary-retried), "暂时停止向该 Provider
发起新的调用" (circuit open), "不能，应该少量的受控渐进恢复" (progressive), and "第一步回滚错误配置，第二步修复持久化的
job … 写入一个新的 durable Outbox dispatch intent 再由 Relay 发布."

**Tech Lead Review:** All correct, with one sharpening: a Provider 429 alone is NOT universal proof nothing executed —
the Adapter classifies `DEFINITELY_NOT_ACCEPTED` vs `MAY_HAVE_EXECUTED`/`UNKNOWN`, retaining a request id when
available; only definitely-not-accepted can ordinary-defer/retry, unknown execution RECONCILES. A circuit breaker
protects a failure domain: CLOSED allows, OPEN durably defers, HALF_OPEN permits a small progressive probe set — one
success does not release the herd, and a HALF_OPEN probe slot is acquired ATOMICALLY (a lock-guarded try-acquire) only
when a real call happens — so two racing Workers can never both probe past the limit, the loser releases its rate permit
and defers, and a Job that defers for capacity never leaks a slot or strands the circuit. Durable cancellation/terminal
facts OUTRANK a claim: re-check them when a deferred Job wakes. For the zero-defer incident: roll the config back first
(future harm only, not a business-fact rollback), build a bounded affected set from release + window + expiry reason +
evidence + deadline, preserve expired history, and re-dispatch ONLY proven-no-execution, still-valid Jobs via a guarded,
IDEMPOTENT, audited repair whose repair-id claim, reservation, audit record, status change, and single Outbox intent all
run in ONE atomic critical section — so two CONCURRENT repairs of the same id yield exactly one re-dispatch and one
`ALREADY_APPLIED` — Jobs with Provider evidence are RECONCILE_ONLY. (These atomic sections are verified with in-memory
threaded tests; they model, but are not, real database isolation.)

---

## 8. Common Misconceptions

```text
Retry storm
❌ Synchronized 429 retries are a cache avalanche.
✅ They are a retry storm / thundering herd (failed requests re-amplifying the dependency). Cache avalanche = cache expiry loading the backend.

Shared limiter outage
❌ If the limiter is down, keep calling — capacity looks available.
✅ Default fail closed for new paid calls; you lost the only cross-Worker bound. Fail-open is an explicit, bounded policy.

Budget reservation
❌ Reserve the remaining balance / settle later.
✅ Reserve the bounded worst-case cost at acceptance; if it cannot be covered, do not call. Unused money returns to the tenant ledger, not the limiter.

Claim vs limiter
❌ A guarded claim means the Worker may call the Provider.
✅ A claim is per-Job execution authority; a permit is fleet capacity. Both are required.

429 certainty
❌ A 429 proves the Provider did not execute, so retry.
✅ A 429 alone is not proof. Classify execution certainty; unknown/may-have-executed -> reconcile, never blind retry.

Circuit recovery
❌ When the Provider looks healthy, release all deferred Jobs.
✅ HALF_OPEN allows a small progressive probe set; one success does not close the circuit or release the herd.

Degradation
❌ Under load a Worker can shrink max_tokens / swap the model.
✅ Only if the persisted, product-authorized contract permits it, down to a floor. Never a silent mutation.
```

How to remember: **a claim is authority; a permit is capacity; a reservation is money; a circuit is health — and no call means DEFER, unknown call means RECONCILE.**

---

## 9. Engineering Trade-offs

```text
Fail closed vs fail open (limiter outage)
Closed: safe (no fleet-concurrency bound lost); some Jobs wait. Default.
Open: keeps throughput but can melt the Provider and overspend. Only as an explicit, bounded emergency policy.

Defer vs reconcile (no evidence vs unknown)
Defer: nothing external happened -> cheap, bounded retry later. Correct for no-permit / circuit-open.
Reconcile: the call may have run -> never blind retry; protects against double billing. Correct for unknown/evidence.

Worst-case reservation vs remaining-balance
Worst-case: never overspends; may reserve more than used (released on settle). Correct.
Remaining-balance: can double-book or under-reserve; a shared balance races. Reject.

Repair: re-dispatch vs reconcile-only (after incident)
Re-dispatch: only for proven-no-execution, still-valid Jobs, via a new Outbox intent.
Reconcile-only: for any Provider evidence or expired commitment — never blind re-dispatch.
```

A Tech Lead reviews: is backpressure before 202? Is the limiter outage fail-closed? Is the reservation worst-case? Is a
429 classified by certainty, not status alone? Is HALF_OPEN progressive? Does repair write a new Outbox intent, not a
direct queue call?

---

## 10. Hands-on Exercises

### Exercise 1: Diagnose the retry storm

Question: 200 Workers, Provider 429, all retrying. Name the failure and fix the wake pattern.

Think First: what makes them synchronize?

Expected Output: retry storm (not cache avalanche); bounded backoff + full jitter; Retry-After as an earliest floor
(`test_retry_after_is_earliest_floor_not_wake_all`).

Follow-up: why does `Retry-After` alone not prevent the herd?

### Exercise 2: No-permit is DEFER

Question: no rate permit before the call. Which outcome and which counters change?

Expected Output: `DEFER`, `DEFERRED`, `defer_count=1`, `execution_retry_count=0`, zero Provider calls
(`test_no_capacity_defers_with_zero_provider_calls_and_no_execution_retry`).

Follow-up: why not FAILED or PENDING_RECONCILIATION?

### Exercise 3: 429 by certainty

Question: classify 429-with-request-id, bare 429, and 429-not-accepted; which may retry?

Expected Output: MAY_HAVE_EXECUTED / UNKNOWN / DEFINITELY_NOT_ACCEPTED; only the last can ordinary-retry
(`test_execution_certainty_classification`).

Follow-up: what does evidence do in `evaluate_dispatch`? (Forces RECONCILE before capacity gating.)

### Exercise 4: Zero-defer incident repair

Question: a bad release expired capacity-deferred Jobs. Recover without a bulk flip.

Expected Output: `rollback` (future harm only), bounded affected set, re-dispatch only proven-no-execution valid Jobs
via a new Outbox intent, evidence -> RECONCILE_ONLY (`test_repair_*`).

Follow-up: why a new Outbox intent instead of a direct Celery call? (Avoids a dual-write failure.)

---

## 11. Relevant Framework Connections

- **FastAPI**: admission/backpressure runs before the durable Job + Outbox commit; tenant-specific quota rejection (429)
  vs service-wide safe refusal (503); accepted Jobs are observed through durable state, never retro-429/503.
- **PostgreSQL**: the guarded claim, the durable reservation ledger, retry/defer evidence, deadlines, guarded terminal
  transitions, audit records, and evidence-based repair are durable truth.
- **Celery**: delivers and reschedules work; it does not own business authority, rate capacity, or cost truth.
- **Redis (or equivalent)**: possible shared rate-limit / circuit coordination state — TRANSIENT coordination, not
  tenant budget truth; its outage triggers fail-closed.
- **Provider Adapter**: translates vendor status/headers into an application-owned execution-certainty and retryability
  contract.
- **Outbox Relay**: recovery writes a NEW durable intent and publishes after commit; a direct script-to-Celery call
  reintroduces a dual-write failure.

---

## 12. AI Backend Connections

Long-running, billable model calls need distinct controls for one Job's execution authority, fleet-wide Provider quota,
tenant affordability, Provider failure containment, and honest external-side-effect uncertainty. A 429/timeout/503 must
never lead to double billing, unbounded queue growth, silent quality degradation, or a fabricated zero cost. Execution
contracts, worst-case cost reservations, Attempt/provider-request evidence, and durable deferred/reconciliation paths
are what make expensive AI work recoverable and auditable: the reservation protects the tenant's money, the limiter and
circuit protect the shared Provider, and the certainty classifier protects against paying twice for one generation.

---

## 13. English Interview

### Key Vocabulary

retry storm / thundering herd, exponential backoff, full jitter, Retry-After, rate permit, shared limiter, fail closed,
cost reservation, worst-case cost, settle/release, backpressure, admission control, execution certainty, circuit
breaker, half-open probe, defer budget, business deadline, reconcile.

### Useful Expressions

- "A guarded claim is execution authority; a rate permit is fleet capacity — both are required."
- "No permit before a call is a durable defer, not a failure."
- "A 429 alone is not proof nothing executed; unknown execution reconciles."

### Beginner Question

*What is a retry storm and how do you prevent it?* — "It's failed requests retrying together and re-amplifying the
dependency — a thundering herd, not a cache avalanche. I use bounded exponential backoff with full jitter and treat
Retry-After as an earliest retry time, not a signal for every Worker to wake at once."

### Intermediate Question

*A Worker holds the guarded claim. Why might it still not call the Provider?* — "The claim is only per-Job execution
authority. The call also needs fleet capacity from a shared rate limiter, an intact worst-case cost reservation, and a
closed circuit for the Provider. If any is missing and no call was made, it's a durable defer — persist next_attempt_at
and release the Worker, don't sleep and don't fail the Job. If the limiter store is down, I fail closed for new paid
calls."

### Senior Question

*Design cost and failure handling for billable Provider calls, including a bad-config incident.* — "Reserve the bounded
worst-case cost at acceptance from the persisted contract; if the tenant can't cover it, reject with backpressure before
202. On success settle actual use and release the unused money to the tenant ledger, not the limiter. Classify Provider
failures by execution certainty: definitely-not-accepted can defer, unknown or evidence reconciles — never blind retry,
so I don't double-bill. A circuit breaker contains a failing Provider with progressive half-open probes, not a herd
release. If a bad release expired capacity-deferred Jobs, I roll the config back first to stop future harm — that's not
a business-fact rollback — then build a bounded affected set from release, window, expiry reason, and evidence, preserve
the expired history, and re-dispatch only proven-no-execution, still-valid Jobs via a new Outbox dispatch intent; Jobs
with Provider evidence are reconcile-only."

### Common Weak Answer

"Retry on 429 with backoff, and if the limiter is down just keep calling so we don't block."

### Strong Answer

"Backoff with jitter and Retry-After as a floor; classify the 429 by execution certainty; if the shared limiter is down
I fail closed for new paid calls because I've lost the only fleet-concurrency bound. No permit is a durable defer, not a
failure; unknown execution is reconciliation, not a retry."

(The final Chinese Mental Model the student requested is **assistant-assisted**, not independently authored student
prose: 「Day55 解决谁可以执行、重复投递如何不重复调用；Day56 解决即使可以执行，现在是否应该、是否有能力、是否付得起去调用
Provider。guarded claim 是执行权，shared limiter 是容量，reservation 是租户预算，circuit 是 Provider 健康；没有 permit
就 durable defer（记录 next_attempt_at，不让 Worker sleep，不消耗 execution retry，但有 deadline）；外部执行未知就
RECONCILE，429 本身不证明没执行；预算按持久化契约的最坏情况预留，成功后结算并把未用的钱退回租户账本；backpressure 在
202 之前（租户 429、系统 503）；事故先回滚配置再按证据逐个修复，只有证明没有外部执行且承诺仍有效的 Job 才通过新的
Outbox dispatch intent 重投。」)

---

## 14. Mental Model Summary

```text
guarded claim   = execution authority for ONE Job          (Day55; PostgreSQL)
rate permit     = fleet capacity to call now                (shared limiter; Redis-like)
reservation     = tenant affordability, worst-case          (durable ledger; PostgreSQL)
circuit         = Provider-health containment                (per provider/account/model/region)
CALL/DEFER/RECONCILE/TERMINAL/NOOP = the five dispatch outcomes
Retry-After     = earliest floor (jitter breaks the herd)   != wake-all
retry storm     != cache avalanche
no permit        -> durable DEFER (next_attempt_at; no sleep; no execution-retry spend; bounded by deadline)
limiter outage   -> fail closed (fail-open only explicit)
unknown 429/exec -> RECONCILE (never blind retry)
backpressure     -> before 202: tenant 429 vs system 503
degradation      -> only if the persisted contract authorizes it
reservation      -> worst-case = bounded INPUT + OUTPUT cost; settle releases unused to the ledger; actual>reserved -> protected reconciliation (never overdraw)
incident repair  -> config rollback (future harm) + bounded evidence + guarded IDEMPOTENT repair (one Outbox intent per repair id; evidence -> reconcile-only)
```

---

## 15. Today's Takeaway

- **Most important mental model:** four authorities — claim (execution), permit (capacity), reservation (money),
  circuit (health) — and five outcomes CALL/DEFER/RECONCILE/TERMINAL/NOOP.
- **Most important production risk:** a synchronized retry storm and double billing on unknown 429s. Jitter + execution
  certainty + reconcile prevent both.
- **Most important trade-off:** fail closed over fail open when the shared limiter is down.
- **Most important framework connection:** backpressure before the FastAPI 202 / durable Job + Outbox commit.
- **Most important AI Backend connection:** worst-case reservation + settle/release keeps billable Provider work
  affordable and auditable.
- **Most important interview answer:** a guarded claim is not a rate permit; no permit is a durable defer, not a failure.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I separate the guarded claim, the rate permit, the reservation, and the circuit?
- [ ] Can I explain why a retry storm is not a cache avalanche and how jitter + Retry-After fix it?
- [ ] Can I classify a no-permit-before-call as a durable DEFER (not FAILED/PENDING_RECONCILIATION)?
- [ ] Can I justify fail closed on a shared-limiter outage?
- [ ] Can I reserve the worst-case cost and settle/release actual use to the tenant ledger?
- [ ] Can I place backpressure before 202 and map tenant 429 vs system 503?
- [ ] Can I classify a 429 by execution certainty and route unknown execution to reconciliation?
- [ ] Can I design OPEN/HALF_OPEN progressive circuit recovery and a zero-defer incident repair?
- [ ] Can I answer an interview question about it in English?
```

---

Related: [`cheat_sheets/fastapi.md`](../../cheat_sheets/fastapi.md) (Day56) ·
[`interview/fastapi.md`](../../interview/fastapi.md) (Day56) ·
[Day56 design/runbook](../../projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md) ·
[model](../../projects/ai-backend-data-layer/api/day56_provider_resilience.py) ·
[tests](../../projects/ai-backend-data-layer/api/test_day56_provider_resilience.py) ·
[Day55 lesson](day55-celery-worker-execution-and-long-running-ai-jobs.md)
