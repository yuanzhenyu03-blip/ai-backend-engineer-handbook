# Day55 — Celery, Worker Execution and Long-running AI Jobs

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation
Previous Lesson: Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation
Next Lesson: Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure
Engineering Artifact: projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md
  + runnable day55_celery_worker_execution.py + test_day55_celery_worker_execution.py (in-memory control flow; 40 passed)
```

Main engineering artifact: a provider-neutral in-memory model of a supported-Celery Worker execution/recovery path —
a Celery-like broker (publish/deliver/redeliver/ACK/visibility-timeout/dead-letter), the Outbox publish-before-checkpoint
ordering, the PostgreSQL-owned guarded claim, ACK timing, poison classification, the Day54 durable cancellation
protocol, graceful drain, and evidence-based incident repair (standard-library control flow; the guarded completion
reuses Day53's pydantic-backed strict validation gate), plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Explain** why the PostgreSQL-owned guarded claim — not a lease or fencing token — is the first duplicate-call gate.
- **Distinguish** all eight identity layers (client idempotency key / job_id / Celery delivery / Worker identity /
  attempt_id / provider_request_id / provider idempotency key / correlation_id).
- **Compare** early vs late ACK and defend late ACK + duplicate absorption.
- **Classify** an unknown Provider outcome as `PENDING_RECONCILIATION` with retained reservation, never a blind re-call.
- **Separate** envelope compatibility (before Job load) from execution-contract compatibility (after Job load).
- **Distinguish** transient failure (bounded retry, Day56 depth) from deterministic poison (quarantine/dead-letter).
- **Design** durable cancellation + optional revoke + cooperative Worker checks inside Celery.
- **Choose** Outbox publish-before-checkpoint ordering and explain the crash windows.
- **Reject** re-implementing the Day40 custom Redis Streams design inside Celery.
- **Recover** an erroneous early-ACK rollout with policy rollback + evidence-based reconciliation, not a bulk state flip.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day54 made the three lifecycles independent and cancellation durable — but the Provider call still ran inline. Real AI
Jobs run for minutes: an eight-minute Provider call cannot hold an HTTP request or a PostgreSQL transaction open. The
moment you move that work onto a broker and Workers, a new class of failure appears: a Worker crashes before it
acknowledges the message; the broker redelivers; two Workers race for the same Job; a malformed message poisons the
queue; a deploy force-kills Workers mid-flight. Get these wrong and you double-bill a customer for a Provider call,
lose an accepted Job silently, or corrupt the business fact by treating "Celery says SUCCESS" as "the Job succeeded."
Day55 puts long-running Provider work on a **supported Celery broker transport** while keeping PostgreSQL as the single
source of business truth: at-least-once delivery is safe because a guarded claim — not the broker — decides who may
call the Provider, and ACK means "delivery handled," never "Job succeeded."

---

## 4. Roadmap Position

```text
Day40 delivery semantics (at-least-once, redelivery, ACK, idempotency, poison)
Day50 Job + Outbox + Relay (one PostgreSQL transaction, fake transport)
Day53 Provider boundary + strict structured-output validation
Day54 three lifecycles + durable cooperative guarded cancellation
        |
        v
Day55 supported-Celery Worker execution of long-running AI Jobs   <-- you are here
        |
        v
Day56 provider resilience, rate limits, token cost, backpressure
        |
        v
Day57 integration / fake-provider / failure-injection / recovery verification
        |
        v
Day58 observability + Phase 4 capstone
```

### Knowledge continuity

```text
Previous Knowledge
  Day40 delivery semantics + Day50 Outbox/Relay + Day53 validation + Day54 cancellation/lifecycles
        |
        v
Current Lesson Concept
  A supported Celery broker + Workers run the Provider call; a PostgreSQL guarded claim owns authority;
  ACK != business success; unknown outcome -> reconciliation; Day54 cancellation preserved
        |
        v
Future Production Usage
  Day56 resilience/cost/backpressure -> Day57 failure-injection verification -> Day58 observability capstone
```

Prerequisites and reused mental models: **Day40** delivery semantics (named, not the Streams implementation),
**Day50** Job/Outbox/Relay + idempotent dispatch, **Day53** guarded completion + strict validation gate, **Day54**
durable, auditable, cooperative, guarded cancellation and `PENDING_RECONCILIATION`. Day56 depends on Day55's reliable
execution/recovery; Day57 depends on it to inject real faults.

---

## 5. Lesson Map

```text
Outbox durable intent
  -> publish to a supported Celery broker (publish BEFORE checkpoint)
  -> at-least-once delivery / redelivery
  -> PostgreSQL guarded claim (execution authority)
  -> durable Attempt + correlation evidence
  -> Provider call OUTSIDE a DB transaction
  -> validate BEFORE guarded completion
  -> unknown outcome -> PENDING_RECONCILIATION (no blind re-call)
  -> cancel -> durable intent + optional revoke + cooperative check -> one guarded winner
  -> ACK / SUCCESS = delivery handled  != Job succeeded
```

---

## 6. Core Mental Model

```text
Celery ACK / SUCCESS  =  delivery reliably handled
Durable Job (PostgreSQL) =  business truth

ACK != succeeded
broker redelivery != permission to call the Provider again
Worker identity != durable Attempt identity
Provider timeout / Worker loss != proof of no execution or zero cost
Celery revoke != durable cancellation authority
configuration rollback != business-fact rollback
```

The broker moves work and guarantees at-least-once delivery. PostgreSQL — through a guarded claim, a durable Attempt,
and guarded terminal transitions — decides who executes, whether a result becomes truth, and who wins a race. The two
are different authorities and must never be confused.

---

## 7. Main Concepts

### Concept 1: The guarded claim is the first duplicate-call gate

**Tech Lead Question:** Two Workers receive the same Job (redelivery). What stops both from calling the paid Provider?

**Student Thinking:** The student reached for ownership primitives: "根据 lease token 以及 fencing token."

**Student Answer:** Lease + fencing token decide who executes.

**Tech Lead Review:** Reasonable — both describe execution ownership — but not the first gate. A **lease** is temporary
ownership; a **fencing token** rejects stale durable writes but cannot prevent or undo an already-issued Provider
request. The first duplicate-call gate is an atomic, PostgreSQL-owned **guarded claim**:

```text
UPDATE jobs SET status='running', open_attempt_id=:a
WHERE job_id=:j AND status IN ('queued','running') AND (lease_owner IS NULL OR lease_expiry < now)
RETURNING *;
```

One row -> this Worker has authority to call the Provider. Zero rows -> STOP before the call. Lease/fencing are
secondary.

**Engineering Thinking:** At-least-once delivery is safe only because authority is decided by a single atomic write in
the system of record, not by the broker and not by wall-clock ownership.

**Production Example:** A GPU inference Job redelivered after a visibility timeout: `claim_execution` grants exactly one
Worker; the duplicate sees zero rows and no-ops. `provider.calls == 0` on the loser.

**Framework Connection:** PostgreSQL `UPDATE ... WHERE ... RETURNING`; Celery redelivery; SQLAlchemy in the real system.

### Concept 2: Identity layers are different

**Tech Lead Question:** A redelivery arrives on a new Worker. New Attempt? New Provider idempotency key?

**Student Thinking / Answer:** "不是，可能之前的 work 又恢复了，新旧两个 worker 重复执行" — a new Worker is not a new
execution; two Workers must not double-execute.

**Tech Lead Review:** Correct. Redelivery or a new Worker does NOT create a new Attempt. A retransmission of Attempt A1
retains the same `provider_idempotency_key`; only a deliberate, durable, authorized A2 gets a new key. The eight layers:

```text
client_idempotency_key   = one logical API command
job_id                   = durable business fact
celery_delivery_id       = broker delivery occurrence
worker_id                = process handling a delivery
attempt_id               = durable execution attempt
provider_request_id      = external execution evidence
provider_idempotency_key = one intended Provider call
correlation_id           = tracing / reconciliation linkage
```

**Engineering Thinking:** Collapsing any two of these is how systems double-bill or lose evidence. `claim_execution`
retains the open Attempt across redelivery; `record_provider_request_id` persists external evidence at request open.

**Production Example:** After a Worker OOM, the redelivered Job resumes the same Attempt and idempotency key, so the
Provider (if it supports idempotency) collapses the retry instead of charging twice.

### Concept 3: ACK and Celery task status

**Tech Lead Question:** Celery reports the task `SUCCESS`. Is the Job succeeded?

**Student Thinking / Answer (EN, Beginner):** "celery task being success means task response success that is a
temporary state. durable job is a truth."

**Tech Lead Review:** Right idea, sharper wording: Celery `SUCCESS`/ACK means the delivery was reliably handled — an
operational delivery/execution status — not a business outcome. A Worker may safely ACK after recording a cancellation,
a poison quarantine, a duplicate no-op, `PENDING_RECONCILIATION`, or a validation refusal.

```text
early ACK -> Worker crash can silently LOSE the delivery
late ACK  -> crash can REDELIVER; the application absorbs duplicates
```

**Engineering Thinking:** `GET /jobs/{job_id}` reads the PostgreSQL durable Job state, never the Celery result backend.
Late ACK + duplicate absorption via the guarded claim is the safe default.

**Production Example:** A dashboard that read the Celery result backend would show "done" while the durable Job is still
`pending_reconciliation` — a lie to the customer. Read the durable Job.

### Concept 4: Provider uncertainty, Worker loss, OOM, short transactions

**Tech Lead Question:** The Worker died mid-call (or timed out). Is cost zero? Can you re-call?

**Student Thinking / Answer:** "不能，成本未知" and "不能，因为 provider 运行未知" — cost is unknown; execution is unknown.
The student also asked, honestly, "OOM 是什么?"

**Tech Lead Review:** Correct. **OOM = Out Of Memory**: the OS/container can kill a Worker without letting it clean up,
so `try/except` alone is insufficient. Persist the guarded claim, Attempt, and correlation evidence BEFORE the call;
keep the long call OUTSIDE any DB transaction. If the outcome is unknown, retain the reservation and enter
`PENDING_RECONCILIATION`; never fabricate zero usage; never blind re-call.

There is a subtle recovery gap here (P1). A Worker can dispatch to the Provider and then OOM *before* it records
`provider_request_id` — so a MISSING request id does NOT prove the Provider did not execute. To close it, the Worker
persists a **conservative durable marker before the call leaves the process**:

```text
guarded claim
-> provider_dispatch_started_at   (external call MAY have started)
-> Provider request (outside any DB transaction)
-> record provider_request_id as soon as available
-> validate / guarded terminal
```

From the moment that marker commits, the system never assumes the Provider did not run. A redelivery of an Attempt that
has EITHER a `provider_request_id` (strong evidence) OR the marker (conservative evidence) returns `RECONCILE_ONLY` and
calls the Provider zero times. Accepting a false positive — the marker was set but the request had not actually left the
process when the Worker died, so the Job reconciles unnecessarily — is the deliberate safety-first trade-off: we never
trade a possible duplicate paid Provider call and duplicate cost for an automatic retry.

**Production Example:** An eight-minute summarization call: a 500-line DB transaction around it would pin a connection
and risk lock timeouts; instead the call runs outside the transaction and only the short guarded writes touch the DB.

### Concept 5: Poison vs transient — and envelope vs execution-contract

**Tech Lead Question:** A message with `job.dispatch.v2` you don't understand — retry it forever?

**Student Thinking / Answer:** The student first labeled it "execution-contract 问题," then, when pushed on transient
failures, said "应该有限重试并采用指数退避+jilt(jitter)... 保留 attempt、event."

**Tech Lead Review:** Two corrections. (1) Transient failure -> bounded retry + exponential backoff + jitter (Day56
depth); deterministic poison -> durable classification + quarantine/dead-letter, NOT an infinite requeue. (2)
`job.dispatch.v2` is an **envelope** compatibility problem — can the Worker even parse the message? — detected BEFORE
loading the Job. An unsupported **persisted execution contract** is detected AFTER loading the Job. They are different
points:

```text
envelope_version unsupported     -> dead-letter + ACK, zero Provider calls, Job untouched
execution_contract unsupported   -> durable QUARANTINED + ACK, zero Provider calls
```

**Engineering Thinking:** The envelope is small, safe routing metadata; PostgreSQL owns Job state, budget, tenant
authority, and result truth. `SUPPORTED_ENVELOPE_VERSIONS` and `SUPPORTED_CONTRACT_VERSIONS` are disjoint.

### Concept 6: Day54 cancellation in Celery

**Tech Lead Question:** A cancel request arrives. Can the Worker just revoke the Celery task?

**Student Thinking / Answer:** "不能，因为有可能撤销失败，还需要持久化撤销意图," and later "读取 cancellation intent."

**Tech Lead Review:** Correct. Commit a durable, auditable cancellation intent FIRST (reason/actor/timestamp/version);
the optional Celery `revoke` is best-effort delivery/runtime control AFTER the commit, never the authority (it can fail
or race). The Worker checks the intent at safe points: pre-call -> zero Provider calls + guarded terminal; final
pre-completion -> a durable intent after the last token still prevents `succeeded`. The terminal is kind-derived
(`terminal_for_intent`: user cancel -> CANCELLED, deadline -> EXPIRED). Completion and cancellation each use a guarded
terminal write, so exactly one wins and the loser sees zero rows.

**Production Example:** A user cancels a running Job; the intent commits, revoke is attempted, and whichever of
completion/cancellation reaches the guarded write first wins — the other no-ops. A crash after the intent is safe: a
restarted Worker re-observes it and the guarded transition absorbs repeats.

### Concept 7: Outbox ordering and graceful drain

**Tech Lead Question:** Publish the Celery task before or after the Outbox checkpoint? And how do you deploy without
killing running Jobs?

**Student Thinking / Answer:** "之后写 published_at，会造成任务挂起" (checkpoint-after is correct; checkpoint-first strands
the Job), and "应该停止 worker 接新 job，drain 还在 in-flight 的 worker."

**Tech Lead Review:** Correct. Publish FIRST, then checkpoint: a crash in between may duplicate the publish (absorbed by
the guarded claim); checkpoint-first could strand a queued Job with no message. Graceful drain: start verified new
Workers, stop old Workers from taking NEW claims, drain in-flight within a bound, checkpoint, ACK, exit — force-kill is
never business cancellation. For the erroneous early-ACK release: the student nailed it — "能解决之后的 worker 再出现同样
情况，不能自动修复已经持久化为 running 的 job." Roll the policy back FIRST (future harm only), build the affected set from
release version + a bounded time window + Worker/Attempt/Event evidence, and reconcile from evidence — a Job with a
`provider_request_id` is `RECONCILE_ONLY`, never a blind re-dispatch.

---

## 8. Common Misconceptions

```text
First duplicate-call gate
❌ A lease / fencing token decides whether a Worker may call the Provider.
✅ An atomic PostgreSQL guarded claim decides. Fencing rejects stale writes; it cannot undo an external side effect.

Poison handling
❌ A poison task should use the same exponential retry as any failure.
✅ Transient -> bounded retry/backoff/jitter (Day56); deterministic poison -> durable classification + quarantine/dead-letter.

Unknown envelope version
❌ `job.dispatch.v2` is an execution-contract problem.
✅ It is envelope compatibility, checked BEFORE loading the Job. Execution-contract compatibility is checked AFTER.

Attempt identity
❌ A new Worker (or redelivery) means a new Attempt and a new Provider idempotency key.
✅ Worker identity and broker delivery are not Attempt identity. A1 redelivery retains A1's key; only an explicit A2 gets a new key.

Celery task success
❌ Celery `SUCCESS` is a temporary business outcome.
✅ It is an operational delivery/execution status; PostgreSQL durable Job truth is authoritative.

Timeout redelivery
❌ A redelivered timed-out Job can begin with guarded completion.
✅ First retain/re-enter PENDING_RECONCILIATION, load the existing Attempt, and do NOT call the Provider; guarded completion follows only a matching, validated late result.

Missing provider_request_id
❌ No provider_request_id means the Provider never executed, so it is safe to re-call.
✅ A Worker can OOM after dispatching but before recording the id. A conservative pre-dispatch marker means "may have executed" — a redelivery reconciles, never blindly re-calls. Missing id != not executed.
```

How to remember: **ACK moves messages; PostgreSQL moves truth.**

---

## 9. Engineering Trade-offs

```text
Early ACK vs Late ACK
Early: message removed immediately; a crash before durable work LOSES the delivery (no redelivery). Lowest duplicate risk, highest loss risk.
Late:  ACK after durable handling; a crash REDELIVERS; the app must absorb duplicates (guarded claim). Choose this for billable, durable Jobs.

Publish-before-checkpoint vs checkpoint-first
Publish-first: a crash may duplicate the publish (absorbed). Safe.
Checkpoint-first: a crash may strand a queued Job with no broker message. Unsafe — avoid.

Supported Celery broker vs hand-built Day40 Streams
Supported Celery: reuses maintained delivery/ACK/redelivery/revoke; less code to get wrong.
Hand-built Streams inside Celery: duplicates XADD/XREADGROUP/XACK/reclaim as a parallel queue. Reject — reuse Day40 SEMANTICS, not the implementation.

Reconcile vs re-dispatch after an incident
Reconcile-only: for Jobs with Provider-execution evidence (provider_request_id) — never blind re-call.
Guarded re-dispatch: only for Jobs with NO execution evidence, and only via an explicit, audited, guarded action.
```

A Tech Lead reviews: is authority decided in the system of record? Is ACK late? Is unknown cost retained, never zeroed?
Is cancellation a durable intent? Is the incident repaired from evidence, not a bulk flip?

---

## 10. Hands-on Exercises

### Exercise 1: Guarded claim vs lease

Question: Show that a redelivery of a terminal Job calls the Provider zero times.

Think First: which check fires first — the claim or the lease?

Starter Artifact: `claim_execution` returning `ALREADY_TERMINAL`; `run_worker` returning `DUPLICATE_NOOP`.

Expected Output: `test_duplicate_delivery_of_terminal_job_is_noop` — `provider.calls == 0`, ACKed.

Explanation: the guarded claim, not the lease, stops the second call.

Follow-up: what does the loser of a live-lease race do? (Answer: `CLAIM_CONFLICT`, do not ACK, redeliver later.)

### Exercise 2: Envelope vs execution-contract poison

Question: Route `job.dispatch.v2` and an `exec.v9` Job to the correct poison handling.

Think First: which is detectable before loading the Job?

Expected Output: `ENVELOPE_POISON_DEADLETTER` (before load) vs `CONTRACT_POISON_QUARANTINE` (after load); both zero
Provider calls; the version spaces are disjoint.

Follow-up: why must neither invoke Provider work?

### Exercise 3: Timeout redelivery

Question: Time out a Provider call, then redeliver the Job. Prove no second Provider call.

Expected Output: first run -> `PENDING_RECONCILIATION` with `provider_request_id` recorded; redelivery ->
`RECONCILE_NO_RECALL`, `provider.calls == 0`.

Follow-up: why is the reservation retained instead of settled to zero?

### Exercise 4: Incident repair

Question: A bad early-ACK release left Jobs `running`. Recover without a bulk flip.

Expected Output: `ReleaseConfig.rollback` (future harm only), `build_affected_set` (no flip), `classify_repair` ->
`RECONCILE_ONLY` where a `provider_request_id` exists, else guarded re-dispatch.

Follow-up: why does a client idempotency key not prove Provider execution?

---

## 11. Relevant Framework Connections

- **Celery**: task protocol, Workers, ACK timing, redelivery, supported broker transport, remote revoke, Worker loss,
  and drain. Model only supported semantics; do not hand-build a replacement.
- **Redis / RabbitMQ**: broker candidates. The broker role is distinct from Celery and from PostgreSQL. If Redis is the
  broker, use Celery's supported transport — not the Day40 custom Streams design.
- **PostgreSQL**: durable Job/Attempt/Event, the guarded claim and guarded terminal transitions, reservation,
  reconciliation, audit, and repair. The single source of business truth.
- **FastAPI**: admission and `GET /jobs/{job_id}` read the durable Job truth; never expose Celery result-backend state
  as public business state.
- **OpenAI-compatible Provider adapter**: the SDK and best-effort stream abort stay behind the application-owned
  boundary; the guarded completion validates the payload (Day53) before it becomes truth.

---

## 12. AI Backend Connections

Long-running, billable Provider work is the defining AI-backend workload: minutes-long generations, unknown token
usage on timeout, strict structured-output validation, raw-data minimization, correlation, cancellation, and cost
reconciliation. Day55's discipline is what keeps an AI backend honest under load: the broker gives you horizontal
Worker scale and at-least-once delivery, but a redelivered message must never mean a second paid Provider call, a
Worker OOM must never zero out a customer's cost, and "Celery says done" must never overwrite a cancelled Job. The
guarded claim, `PENDING_RECONCILIATION`, and the Day54 cancellation protocol are exactly the primitives that let you
run expensive models on unreliable infrastructure without double-billing or losing accepted work.

---

## 13. English Interview

### Key Vocabulary

at-least-once delivery, redelivery, acknowledgement (ACK), visibility timeout, guarded claim, execution authority,
durable Attempt, provider idempotency key, poison message, dead-letter, quarantine, envelope version, execution
contract, reconciliation, graceful drain, revoke.

### Useful Expressions

- "ACK means the delivery was handled, not that the Job succeeded."
- "A guarded claim in PostgreSQL decides execution authority; the broker only delivers."
- "An unknown outcome is reconciliation, not a failure and not a blind retry."

### Beginner Question

*What does it mean when a Celery task reports SUCCESS?* — "It means the delivery was reliably handled — an operational
status. The business Job is only succeeded when PostgreSQL, the source of truth, records it through a guarded
completion. I read the durable Job, not the Celery result backend."

### Intermediate Question

*Two Workers get the same Job. How do you prevent a double Provider call?* — "The first duplicate-call gate is an atomic
PostgreSQL guarded claim — `UPDATE ... WHERE status IN ('queued','running') RETURNING`. One Worker gets one row and the
authority to call the Provider; the other gets zero rows and stops. A lease or fencing token is secondary — fencing
rejects stale writes but can't undo an external call. Redelivery keeps the same Attempt and provider idempotency key."

### Senior Question

*Design cancellation and incident recovery for long-running Celery AI Jobs.* — "Cancellation is a durable, auditable
intent committed first; the Celery revoke is best-effort after the commit, never the authority. Workers check the
intent at safe points: pre-call means zero Provider calls and a guarded terminal; a final pre-completion check stops a
late `succeeded`. Completion and cancellation both use guarded terminal writes, so exactly one wins. For an erroneous
early-ACK release, I roll the configuration back first to stop future harm — that is not a business-fact rollback — then
build an affected set from the release version, a bounded time window, and Worker/Attempt/Event evidence. I don't
bulk-flip running Jobs; I reconcile each from evidence and only re-dispatch, under a guarded audited action, the Jobs
with no Provider-execution evidence."

### Common Weak Answer

"Celery handles retries and idempotency, so redelivery is fine — the task status tells me if the Job worked."

### Strong Answer

"Celery gives me at-least-once delivery and revoke, but authority and truth live in PostgreSQL. A guarded claim decides
who calls the Provider; ACK means delivery handled; an unknown outcome is `PENDING_RECONCILIATION` with the reservation
retained and no blind re-call; cancellation is a durable intent with a cooperative Worker and a guarded terminal
transition. Celery moves messages; PostgreSQL moves truth."

(The final Chinese Mental Model synthesis the student requested is **assistant-assisted**, not independently authored
student prose: 「Celery 只负责可靠投递（ACK/redelivery/revoke 都是投递层）；PostgreSQL 通过 guarded claim、durable
Attempt、guarded terminal 决定谁执行、结果是否成真、竞争谁赢。ACK ≠ 成功，重投 ≠ 允许再调用 Provider，超时/OOM ≠ 没执行或
零成本，撤销先持久化意图再 revoke。」)

---

## 14. Mental Model Summary

```text
Celery ACK / SUCCESS      = delivery reliably handled (NOT Job succeeded)
Guarded claim             = first duplicate-call gate (execution authority, in PostgreSQL)
Lease / fencing           = secondary ownership / stale-write rejection (not the first gate)
Attempt identity          != Worker identity != broker delivery
provider_request_id       = external execution evidence (record at request open)
Provider timeout / OOM     -> PENDING_RECONCILIATION (reservation retained, no blind re-call)
Envelope version          = can the Worker PARSE the message (before Job load)
Execution contract        = can the Worker EXECUTE the Job (after Job load)
Transient failure          -> bounded retry/backoff/jitter (Day56 depth)
Deterministic poison       -> durable classification -> quarantine / dead-letter
Cancellation              = durable intent FIRST -> optional revoke -> cooperative check -> one guarded winner
Outbox                    = publish BEFORE checkpoint
Incident repair           = policy rollback (future harm) + evidence-based reconcile (no bulk flip)
```

---

## 15. Today's Takeaway

- **Most important mental model:** Celery moves messages; PostgreSQL moves truth. ACK/SUCCESS is delivery handled, not
  business success.
- **Most important production risk:** treating broker redelivery as permission to re-call the Provider — double-billing.
  The guarded claim, retained Attempt/idempotency key, and `PENDING_RECONCILIATION` prevent it.
- **Most important trade-off:** late ACK + duplicate absorption over early ACK + silent loss.
- **Most important framework connection:** a supported Celery broker transport reusing Day40 SEMANTICS — never a
  hand-built Streams replacement.
- **Most important AI Backend connection:** unknown Provider cost on timeout/OOM is retained and reconciled, never
  zeroed or blindly re-called.
- **Most important interview answer:** a PostgreSQL guarded claim — not a lease/fencing token — is the first
  duplicate-call gate.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain why a guarded claim, not a lease/fencing token, is the first duplicate-call gate?
- [ ] Can I explain why Celery ACK/SUCCESS is not business success?
- [ ] Can I separate envelope compatibility from execution-contract compatibility?
- [ ] Can I distinguish transient failure from deterministic poison?
- [ ] Can I explain why a timeout/OOM outcome is PENDING_RECONCILIATION, not failed or re-called?
- [ ] Can I design durable cancellation + optional revoke + cooperative checks in Celery?
- [ ] Can I recover an erroneous early-ACK rollout with policy rollback + evidence-based reconciliation?
- [ ] Can I answer an interview question about it in English?
```

---

Related: [`cheat_sheets/fastapi.md`](../../cheat_sheets/fastapi.md) (Day55) ·
[`interview/fastapi.md`](../../interview/fastapi.md) (Day55) ·
[Day55 design/runbook](../../projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md) ·
[model](../../projects/ai-backend-data-layer/api/day55_celery_worker_execution.py) ·
[tests](../../projects/ai-backend-data-layer/api/test_day55_celery_worker_execution.py) ·
[Day54 lesson](day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md)
