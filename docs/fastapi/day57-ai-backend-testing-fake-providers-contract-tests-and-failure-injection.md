# Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure
Previous Lesson: Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure
Next Lesson: Day58 — Observability, Correlation Evidence and Phase 4 Capstone
Engineering Artifact: projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md
  + runnable day57_testing_harness.py + test_day57_testing_harness.py (deterministic in-memory verification; 22 passed)
```

Main engineering artifact: a deterministic verification harness — a controllable Fake Provider (scripted outcomes,
independent call log, `request_received` / `release_response` gates), a `FakeClock` + `DeterministicRandom`, an
application-owned `ProviderAdapter`/`ProviderOutcome`, a strict late-result completion contract, and an explicit
four-tier `VALIDATION_MATRIX` — that drives the REAL Day56 policy functions and Day53's real validator, plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Turn** a reliability policy into a repeatable test that asserts the durable fact AND the side effects (call count,
  no new rate permit), not just a status string.
- **Build** a deterministic, controllable Fake Provider (scripted outcomes, call log, gates) and explain why it is not a
  replacement for integration.
- **Classify** execution certainty (DEFINITELY_NOT_ACCEPTED / MAY_HAVE_EXECUTED / UNKNOWN) and prove a missing
  `provider_request_id` is not proof of no execution.
- **Test** the Adapter's application-owned typed outcome, not vendor SDK exception classes or HTTP codes.
- **Classify** valid JSON that violates the persisted schema contract as a contract violation, not business success.
- **Separate** FOUR evidence tiers — conceptual/static, executed local runtime, integration runtime, and production —
  keeping real PostgreSQL/Celery/Redis as INTEGRATION RUNTIME (currently NOT RUN, not "production") and real Provider
  traffic as PRODUCTION (NOT RUN); an in-process double is EXECUTED LOCAL, never integration.
- **Design** deterministic fault injection (FakeClock, controlled gates) instead of sleeps and random kills.
- **Verify** deadline behavior with and without external-execution evidence, and idempotent guarded repair by a unique
  repair id.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day43–Day56 built a backend full of careful reliability rules: unknown execution reconciles, reservations are held,
repairs are idempotent, backoff is jittered. But a rule that is only described is a rule that silently rots. The first
time a Provider returns a bare 429 in production, you find out whether "reconcile, don't retry" was real code or a
paragraph in a doc. Day57 makes the rules repeatable evidence — and, just as importantly, makes the LIMITS of that
evidence honest: a fast in-memory Fake-Provider test proves your application state machine, but it does not prove that a
real PostgreSQL transaction rolled back, that a real Celery broker redelivered after a Worker was killed, or that a real
Redis limiter failed closed. Confusing those tiers is how teams ship a "fully tested" backend that double-charges a
customer the first time a Worker dies mid-call.

---

## 4. Roadmap Position

```text
Day53 provider boundary + strict validation
Day54 durable cancellation
Day55 Celery execution + P1 dispatch marker
Day56 admission-to-Provider control plane (policies)
        |
        v
Day57 turn the policies into repeatable evidence + failure injection   <-- you are here
        |
        v
Day58 observability: structured logs, job_id/trace_id/attempt_id correlation, metrics, traces + Phase 4 capstone
        |
        v
Day59+ Playwright runtime on a backend whose recovery rules are TESTED, not just described
```

### Knowledge continuity

```text
Previous Knowledge
  Day56 policies (guarded claim / rate permit / reservation / circuit; CALL/DEFER/RECONCILE/TERMINAL/NOOP);
  Day55 dispatch marker; Day54 durable cancellation; Day53 strict validation
        |
        v
Current Lesson Concept
  deterministic Fake Provider + Adapter contracts + failure injection prove those rules hold under failure,
  with an explicit four-tier evidence matrix (integration + production are NOT RUN unless actually executed)
        |
        v
Future Production Usage
  Day58 makes the tested decisions observable and closes Phase 4; later phases build on a tested backend
```

Prerequisites reused: Day56 `evaluate_dispatch` / `process_deadline` / `repair_redispatch` / `admit_job` /
`classify_execution_certainty`; Day55's `provider_dispatch_started_at` marker; Day53's real `StructuredOutputValidator`.

---

## 5. Lesson Map

```text
start from a production failure (bare 429)
  -> assert durable fact AND side effects (call count, no new permit)
  -> Fake Provider (scripted, gated) != integration test
  -> execution certainty; missing request id != no execution (dispatch marker)
  -> Adapter typed outcome (no SDK leakage)
  -> schema-contract violation != success
  -> four evidence tiers: conceptual/static / executed-local / integration-runtime (NOT RUN) / production (NOT RUN)
  -> deterministic backoff (FakeClock + scripted random)
  -> deadline with/without evidence; limiter outage fail-closed
  -> late-result strict match; terminal-cancel rejects
  -> bad-release drill: rollback -> bounded set -> guarded idempotent repair (repair_id) -> one Outbox intent
  -> runtime evidence: pytest passed is NOT enough
```

---

## 6. Core Mental Model

```text
policy (Day56)  ->  repeatable evidence (Day57)

Fake Provider test  = deterministic APPLICATION semantics (EXECUTED LOCAL RUNTIME; fast, small)
integration test    = real component/lifecycle boundaries (PostgreSQL / broker / Worker / Redis) = INTEGRATION RUNTIME (NOT RUN)
production          = real Provider traffic / production validation = PRODUCTION (NOT RUN)

business completion  != external execution
missing request id   != no execution   (dispatch marker covers the crash window)
pytest passed        != audit-grade runtime evidence
```

Day56 said WHEN a Job may call the Provider. Day57 PROVES those rules survive failure — and states plainly which tier of
evidence each test actually provides.

---

## 7. Main Concepts

### Concept 1: Test the side effects, not just the status

**Tech Lead Question:** A bare Provider 429 comes back. What is the durable fact, and what else must the test assert?

**Student Thinking / Answer:** "持久化数据库事实应该是 pending_conciliation" — right direction; normalized to
`PENDING_RECONCILIATION`.

**Tech Lead Review:** Correct fact, but a status is not enough. The test must ALSO assert the Provider call count stays
one and no ordinary retry gets a new rate permit — unknown external execution is not safe retry. Reservation stays HELD;
redelivery routes to reconciliation. (In the harness, driving Day56 `evaluate_dispatch` on an Attempt with evidence
returns `RECONCILE` and consumes no permit.)

### Concept 2: Fake Provider is not integration

**Tech Lead Question:** You have a fast Fake Provider test. Are you done?

**Student Thinking / Answer:** In the English interview the student explained Fake Provider tests are fast/small while
integration checks the whole business workflow — refined into "deterministic application semantics vs real
infrastructure boundaries."

**Tech Lead Review:** Exactly. `ControllableFakeProvider` proves the state machine deterministically; only real
PostgreSQL/broker/Worker/Redis prove transactions, redelivery, process loss, and shared coordination. Keep the tiers
separate and label them.

### Concept 3: Missing request id is not proof of no execution

**Tech Lead Question:** No `provider_request_id` came back. Safe to retry?

**Student Thinking / Answer:** The student first proposed an idempotency key for the crash window; corrected to the
conservative `provider_dispatch_started_at` marker as the durable evidence that blocks another call.

**Tech Lead Review:** Correct. A Worker can crash after the request leaves the process and before it records the id. The
Day55 marker forces RECONCILE in that window; an idempotency key reduces risk but is not proof and not permission. The
Adapter must POSITIVELY classify `DEFINITELY_NOT_ACCEPTED` before an ordinary retry; otherwise unknown reconciles.

### Concept 4: Adapter contract, not SDK exceptions

**Tech Lead Question:** What does the Provider contract test assert?

**Student Thinking / Answer:** (Design exercise.) Test the Adapter output, not vendor SDK exception types.

**Tech Lead Review:** Right. `ProviderAdapter.to_outcome` yields an application-owned `ProviderOutcome` (failure kind,
execution certainty, optional request id, safe retry info, safe metadata) — never SDK exception classes, HTTP codes, or
private fields, and it never writes Job state or cost. Bind assertions to that stable contract.

### Concept 5: A valid-JSON schema violation is not success

**Tech Lead Question:** The Provider returned valid JSON that violates the Job's bound schema. Business success?

**Student Thinking / Answer:** Correctly classified it as a contract violation.

**Tech Lead Review:** The persisted `(schema_name, schema_version)` governs result acceptance; current Provider config
governs new calls only. A valid-JSON-but-schema-violating result is a `CONTRACT_VIOLATION` (Day53's real validator) — no
Result Artifact, not succeeded, no blind second call.

### Concept 6: Four evidence tiers and honest runtime evidence

**Tech Lead Question:** Your Day57 suite is green. Is the recovery path validated?

**Student Thinking / Answer:** Correctly identified that Day57's unexecuted matrix is conceptual/static validation and
that real Provider/production validation cannot be claimed; also that `pytest passed` alone is not enough.

**Tech Lead Review:** Right, and be precise with FOUR tiers: conceptual/static; executed local runtime (in-process
deterministic doubles); integration runtime (real PostgreSQL, a real Celery broker + Worker-kill/redelivery, a real
Redis limiter/circuit — currently NOT RUN, and NOT the same as "production"); and production (real Provider traffic /
production validation, NOT RUN). Real Worker-kill/redelivery needs real PostgreSQL + a supported broker + Worker process
+ an independent Fake Provider service whose call log survives Worker loss. Audit-grade evidence preserves the exact command/revision, the fault point,
committed-DB queries via a new connection, the cross-process call log, and broker/Worker lifecycle — not just a pass.

### Concept 7: Deterministic injection + idempotent repair drill

**Tech Lead Question:** How do you test timeout/backoff without flakiness, and recover a bad 429-classifying release?

**Student Thinking / Answer:** Correctly: inject a FakeClock/controlled gate (not sleeps); Retry-After is an earliest
floor, not a wake-all; roll back first, bound the affected set by release + time window + evidence, don't bulk-flip
EXPIRED, evidence means RECONCILE_ONLY, and repair uses a unique `repair_id` with a new Outbox intent (at-least-once
transport, guarded execution). Corrected: missing evidence alone is not permission to retry — safe redispatch needs
proof of no execution plus all eligibility checks.

**Tech Lead Review:** All correct. The harness proves the deterministic decision logic (FakeClock/jitter, guarded
idempotent `repair_redispatch` under two threads -> one `REDISPATCHED`, one `ALREADY_APPLIED`, one Outbox intent); the
real DB/broker concurrency remains an integration tier that is NOT RUN here.

---

## 8. Common Misconceptions

```text
Durable status is enough
❌ Asserting PENDING_RECONCILIATION proves the fix.
✅ Also assert call count stays one and no retry gets a new permit — unknown execution is not safe retry.

Missing request id
❌ No provider_request_id means the Provider didn't run, so retry.
✅ A crash can happen after the request leaves the process; the dispatch marker forces RECONCILE. Missing id != no execution.

Fake test == integration
❌ A green Fake Provider test means the recovery path is validated.
✅ It proves deterministic application semantics; real PostgreSQL/broker/Worker/Redis prove infra boundaries.

pytest passed == evidence
❌ A passing suite is sufficient audit evidence.
✅ Preserve command/revision, fault point, committed-DB queries, cross-process call log, and lifecycle evidence.

Missing evidence == safe retry
❌ No evidence means it's safe to re-dispatch.
✅ Safe redispatch needs POSITIVE proof of no execution plus all eligibility checks; otherwise reconcile.

Repair dedup by attempt id
❌ Use attempt_id to dedupe repair.
✅ Repair is its own durable decision keyed by a unique repair_id; duplicates get ALREADY_APPLIED.
```

How to remember: **prove the fact AND the side effect, and never let a fast fake claim what only real infra can.**

---

## 9. Engineering Trade-offs

```text
Fake Provider vs real integration
Fake: fast, deterministic, controls time/gates; proves application state machine. Cannot prove infra.
Integration: slow, needs disposable PostgreSQL/broker/Redis; proves transactions/redelivery/process-loss. Run in CI on real resources.

Controlled gate vs sleep/random-kill
Gate (asyncio.Event / threading.Event): deterministic, non-flaky fault window.
Sleep/random kill: flaky, unreproducible, not audit evidence. Reject.

Assert status vs assert status + side effects
Status only: passes even if a second paid call happened. Insufficient.
Status + call count + permit + reservation: catches double-billing and blind retries. Required.

Reconcile vs retry on unknown execution
Reconcile (hold reservation): no double charge / duplicate generation. Correct for unknown/evidence.
Retry: only for positively-classified definitely-not-accepted. Everything else reconciles.
```

A Tech Lead reviews: does each test assert side effects, is time controlled, is the evidence tier labeled, and is real
infra honestly marked NOT RUN when it is?

---

## 10. Hands-on Exercises

### Exercise 1: Bare-429 contract

Question: assert the full contract for a bare 429.

Expected Output: `PENDING_RECONCILIATION`, reservation HELD, one Provider call, redelivery reconcile-only
(`test_dispatch_marker_forces_reconcile_only_no_second_call`).

Follow-up: which extra assertion catches a double call? (call count / no new permit.)

### Exercise 2: Deterministic timeout window

Question: open a timeout window without a sleep.

Expected Output: a `ControllableFakeProvider` with `auto_release=False`; assert `request_received`, thread still alive,
nothing returned; then release (`test_controllable_fake_provider_gate_opens_a_deterministic_timeout_window`).

### Exercise 3: Late result

Question: when may a late result complete a Job?

Expected Output: only non-terminal + awaiting + strict schema + all four ids match; terminal CANCELLED rejects
(`test_late_result_*`, `test_terminal_cancelled_job_rejects_matching_late_result`).

### Exercise 4: Bad-release repair drill

Question: recover a release that classified every bare 429 as definitely-not-accepted.

Expected Output: rollback first, bounded affected set, evidence -> RECONCILE_ONLY, guarded idempotent repair with a
unique repair_id and one Outbox intent (`test_repair_is_idempotent_under_concurrency_one_outbox_intent`,
`test_repair_with_provider_evidence_is_reconcile_only`).

---

## 11. Relevant Framework Connections

- **FastAPI**: system-wide admission backpressure returns 503 before the Job + Outbox durable commitment; no retroactive
  429/503 after acceptance; 503 dominates a tenant-quota 429.
- **PostgreSQL**: durable Job/Attempt/marker/reservation/repair facts, transactions and rollback, guarded terminal
  transitions, a concurrent unique repair decision, and committed-state verification via a NEW connection — the tier
  that proves final facts (NOT RUN in this repository update).
- **Celery + supported broker**: at-least-once publish/delivery, Worker kill/redelivery, ACK boundary; broker delivery
  is not business completion (integration tier, NOT RUN here).
- **Redis or equivalent**: transient shared limiter/circuit; outage fails closed for new paid calls; restoration must
  not release a herd (integration tier, NOT RUN here).
- **Provider Adapter**: application-owned typed outcomes and execution-certainty classification; SDK details stay inside
  the Adapter.
- **Outbox Relay**: repair writes a new durable intent before Relay publication; no direct repair-script-to-broker dual
  write.

---

## 12. AI Backend Connections

Billable, long-running AI calls make the business-completion-vs-external-execution distinction expensive to get wrong: a
timeout, a 429, or a Worker loss can create unknown cost and unknown generation, and a naive retry double-charges the
tenant or produces a duplicate answer. Day57's evidence discipline — reservation held on unknown execution, strict bound
schema validation, deterministic fault injection, and evidence-based idempotent repair — is what lets you run expensive
model work on unreliable infrastructure and still prove you never double-billed or corrupted an in-flight Job. Raw
prompt/output minimization keeps tenant data safe while preserving enough safe evidence (IDs, classifications,
timestamps) for recovery and audit.

---

## 13. English Interview

### Key Vocabulary

fake / deterministic provider, contract test, integration test, failure injection, recovery verification, execution
certainty, dispatch marker, reconciliation, held reservation, FakeClock, controlled gate, evidence tier, runtime
evidence, idempotent repair, at-least-once delivery.

### Useful Expressions

- "A durable status is not enough — assert the call count and that no retry got a new permit."
- "A missing request id is not proof of no execution."
- "A fast fake proves application semantics; real infrastructure proves the boundaries."

### Beginner Question

*What is a Fake Provider and why not just use the real one in tests?* — "A Fake Provider is a deterministic test double
with scripted outcomes and controllable timing, so tests are fast and reproducible. The real Provider is nondeterministic,
costs money, and rate-limits you; I use it only in narrow, authorized integration checks — a fake proves my application
behavior, not the real infrastructure boundary."

### Intermediate Question

*A Provider call times out. What's the durable outcome and what must the test assert?* — "pending-reconciliation, hold
the cost reservation, and the Worker can't retry the Provider call. The test must assert the durable status AND that the
Provider call count stayed one and no retry received a new rate permit — a timeout after the Provider received the
request is not proof of no execution, so unknown execution reconciles, it doesn't retry." (Refined from the student's own
answer.)

### Senior Question

*A bad release classified every bare 429 as definitely-not-accepted and expired Jobs. Recover it.* — "First roll the
mapping back to contain future harm — that's not a business-fact rollback. Then build a bounded affected set from the
release version, a bounded time window, the incident reason, and Attempt/defer/Event evidence; don't bulk-flip EXPIRED
to QUEUED. Any Job with a provider_request_id or a dispatch marker is reconcile-only. Only Jobs with positive proof of no
execution, a valid contract, deadline, and budget, and no cancellation intent may be repaired — a guarded, audited,
idempotent repair keyed by a unique repair_id that writes one new Outbox intent. Transport is at-least-once, but guarded
execution stops duplicate delivery from becoming duplicate Provider work. Missing evidence alone is not permission to
retry."

### Common Weak Answer

"The Provider timed out, so retry it; the tests pass, so recovery works."

### Strong Answer

"A timeout is unknown execution: reconcile with the reservation held, don't retry, and prove the call count stayed one.
And a passing fake test is application-level evidence only — real PostgreSQL/broker/Worker/Redis integration is a
separate tier I mark NOT RUN until it actually runs."

(The final Chinese mental model is **assistant-assisted**, not independently authored student prose: 「Day56 规定 AI Job
何时可以调用 Provider；Day57 用可重复测试证明这些规则在故障下仍成立。Fake Provider 不替代 integration：它确定性地验证
应用状态机与 Adapter 语义，真实 PostgreSQL/broker/Worker/Redis 才验证事务、redelivery、进程丢失与共享协调边界。只要
Provider 调用可能已发生（有 provider_request_id 或 provider_dispatch_started_at），就进入 PENDING_RECONCILIATION、
reservation 保持 HELD、只能 reconcile；缺少 request id 不等于没执行。坏发布先 rollback，再按 release+时间窗口+证据
构建有界 affected set，只有证明未执行且契约/deadline/预算/取消状态合格的 Job 才用唯一 repair_id 原子 repair 写一条新
Outbox intent；pytest 通过不是生产验证。」)

---

## 14. Mental Model Summary

```text
policy (Day56)            -> repeatable evidence (Day57)
assert                    = durable fact AND side effects (call count, no new permit, reservation HELD)
Fake Provider             = deterministic application semantics (scripted, gated, call-logged)
integration               = real PostgreSQL / broker / Worker / Redis boundaries (NOT RUN here)
execution certainty       = DEFINITELY_NOT_ACCEPTED (may retry) vs MAY_HAVE_EXECUTED / UNKNOWN (reconcile)
missing request id        != no execution (dispatch marker covers the crash window)
Adapter                   = application-owned typed outcome, never SDK exceptions; never writes Job/cost
schema violation          = contract violation, not success (bound schema_name/version)
FakeClock + scripted rand = deterministic backoff/jitter; Retry-After is an earliest floor
late result               = complete only on non-terminal + awaiting + strict schema + all ids match
repair                    = unique repair_id, guarded + idempotent, one Outbox intent; evidence -> RECONCILE_ONLY
pytest passed             != audit-grade runtime evidence
```

---

## 15. Today's Takeaway

- **Most important mental model:** a policy is only real when a repeatable test asserts the fact AND the side effects.
- **Most important production risk:** a fast fake claiming what only real PostgreSQL/broker/Worker/Redis can prove —
  keep the four evidence tiers honest.
- **Most important trade-off:** controlled gates + FakeClock over sleeps/random kills for deterministic fault injection.
- **Most important framework connection:** real PostgreSQL is required to prove committed rollback and guarded terminal
  transitions; an ORM mock cannot.
- **Most important AI Backend connection:** unknown execution reconciles with the reservation held — never a blind
  retry that double-charges or duplicates a generation.
- **Most important interview answer:** a missing `provider_request_id` is not proof of no execution.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I assert the durable fact AND the side effects (call count, no new permit, reservation HELD)?
- [ ] Can I build a controllable Fake Provider and say why it is not an integration test?
- [ ] Can I explain why a missing request id is not proof of no execution (dispatch marker)?
- [ ] Can I test the Adapter's typed outcome instead of SDK exceptions?
- [ ] Can I classify valid JSON that violates the bound schema as a contract violation?
- [ ] Can I separate the four evidence tiers (conceptual/static, executed local, integration runtime, production)?
- [ ] Can I inject a deterministic timeout window without sleeps?
- [ ] Can I run the bad-release drill: rollback, bounded set, guarded idempotent repair, one Outbox intent?
- [ ] Can I answer an interview question about it in English?
```

---

Related: [`cheat_sheets/fastapi.md`](../../cheat_sheets/fastapi.md) (Day57) ·
[`interview/fastapi.md`](../../interview/fastapi.md) (Day57) ·
[Day57 design/runbook](../../projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md) ·
[harness](../../projects/ai-backend-data-layer/api/day57_testing_harness.py) ·
[tests](../../projects/ai-backend-data-layer/api/test_day57_testing_harness.py) ·
[Day56 lesson](day56-provider-resilience-rate-limits-token-cost-and-backpressure.md)
