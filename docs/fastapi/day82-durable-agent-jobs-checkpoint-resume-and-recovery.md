# Day82 — Durable Agent Jobs, Checkpoint, Resume and Recovery

## 1. Lesson Metadata

- Status: Completed (classroom scope)
- Phase: 7B — Agent Runtime and MCP Engineering
- Date: 2026-09-02
- Version: 1.0
- Difficulty: Senior
- Estimated time: 4–5 hours
- Prerequisites: Day50, Day60, Day78, Day79, Day80 and Day81
- Previous: Day81 — Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets
- Next: Day83 — Human Approval, Interrupt and Escalation Boundaries
- Artifact: `projects/ai-agent/`
- Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`

## 2. Learning Objectives

You can now:

1. explain why process memory and model context cannot own durable Agent state;
2. design an identity/version/binding-bound authoritative Checkpoint;
3. distinguish database commit, Outbox publication, Queue delivery, Worker execution and verified outcome;
4. classify Resume, Retry, Replan, Reconciliation, Repair, Settlement and Compensation;
5. reject stale Checkpoints, fences, Workers and terminal replays;
6. preserve Reservation truth through restart and partial settlement;
7. reason through five crash windows and a mixed bad-release incident;
8. bound automated recovery without converting unknown into failure;
9. explain exactly what the local Artifact proves and does not prove;
10. answer beginner, intermediate and senior durable-Agent questions in English.

## 3. Why This Matters

Day81 made one controller run bounded and truthful, but its in-memory store disappears with the process. A
production Research Agent may run for minutes or hours while Workers restart, leases expire, messages repeat and
Provider responses vanish. Without durable identity and recovery facts, restart can duplicate paid calls, reset
budgets, accept stale writes or silently forget work that was already committed.

Day82 connects Agent engineering to ordinary backend reliability: conditional updates, transaction boundaries,
Transactional Outbox, at-least-once delivery, leases, fences, reconciliation and append-only audit history.

## 4. Roadmap Position

```text
Day78 Application Runtime
-> Day79 Agent Loop
-> Day80 Tool Governance
-> Day81 State / Termination / Loop / Budget Guards
-> Day82 Durable Job / Checkpoint / Resume / Recovery
-> Day83 Human Approval / Interrupt / Escalation
-> Day84 Conversation Memory vs Durable Business State
```

Day82 composes the existing Runtime rather than reimplementing it. Day83 needs a durable interrupt/recovery seam;
Day84 needs today's proof that execution facts and model memory are different lifecycles.

## 5. Lesson Map

```text
volatile process
-> durable Job identity
-> authoritative Checkpoint
-> conditional transaction + Outbox
-> duplicate-safe delivery
-> lease/fence takeover
-> recovery classification
-> Reservation continuation
-> crash exercise
-> bad-release recovery
-> evidence boundary
```

## 6. Core Mental Model

```text
Durable truth survives the Worker.

durable state + identity-bound Checkpoint + execution evidence
-> recovery candidate
-> current identity / lifecycle / authorization / budget / fence guards
-> authoritative conditional apply
-> atomic state + Checkpoint + Reservation + Audit + Outbox Intent
```

The model and framework may advise or transport. The application-owned durable Runtime owns lifecycle semantics;
only its authoritative persistence boundary may change business truth.

## 7. Main Concepts

### Concept 1 — Durable Job and authoritative Checkpoint

#### Tech Lead Question

After restart, should a Worker continue from old model context or committed Job state and Checkpoint?

#### Student Answer

> 从“已提交的权威 Job 状态与 Checkpoint”继续

#### Tech Lead Review

Correct. Process memory is volatile and private to one Worker. A durable Job is an execution entity whose stable
identity, lifecycle, immutable history, reservations and recovery relationships survive process loss.

A Checkpoint is a committed recovery fact bound to the exact tenant, Job, Step, Attempt, state version, fence /
execution generation and immutable execution bindings. It says where the application committed—not what a model
remembers. Logs, cache, Queue ACK, HTTP 200, Provider 404 and framework snapshots are not automatically authority.

#### Engineering Thinking

Checkpoint identity prevents an A0 snapshot from controlling A1. State version prevents version 12 from
overwriting version 13. Checkpoint version, state version, fence and release version solve different problems.

### Concept 2 — Transaction plus Outbox

#### Tech Lead Question

State, Checkpoint, Reservation and Outbox Intent committed, but the process crashed before publish. Create a new
Step or continue the original Intent?

#### Student Answer

> 继续发布原来已经提交的 Outbox Intent

#### Tech Lead Review

Correct. The Step and Reservation already exist. A Relay scans the existing unpublished Outbox row and publishes
the same event identity. It must not create new business work or reserve twice.

Production design uses one transaction:

```sql
UPDATE agent_jobs
SET state_version = state_version + 1,
    fence_token = :next_fence
WHERE tenant_id = :tenant_id
  AND job_id = :job_id
  AND current_step_id = :expected_step
  AND state = :expected_state
  AND state_version = :expected_state_version
  AND fence_token = :expected_fence
RETURNING state_version, fence_token;
```

Only a returned row permits the same transaction to write Checkpoint, Reservation change, Audit Event and Outbox
Intent. This SQL was designed, not run against PostgreSQL.

### Concept 3 — At-least-once and duplicate identity

If a Relay publishes, crashes before recording `published_at`, then republishes, the Broker may deliver twice.
Absence of a publication checkpoint does not prove no publication. Consumer idempotency, current-state guards and
fencing collapse both deliveries into A1. Reusing the same event ID with A2 identity is a conflict, not a safe
duplicate.

```text
duplicate message != duplicate business action
database commit != publication
publication != execution
execution != verified outcome
```

### Concept 4 — Lease, fence and late result

#### Student Answer

W1 with fence 8 could not write after W2 took over with fence 9, but its late result should be:

> 保留为证据并根据原 Attempt identity 进行分类

#### Tech Lead Review

Correct. Lease expiry grants takeover eligibility; it does not prove W1 never executed. Fence rejects W1's stale
write. The result may still help the current owner reconcile, but cannot restore W1's authority or reopen a
terminal Job. Idempotency suppresses the same semantic effect; fencing rejects stale ownership.

### Concept 5 — Resume, Retry and Replan

- Resume continues the same valid Job/Attempt from committed facts and original bindings.
- Retry creates a new Attempt only after definitely-not-dispatched/accepted or explicit safe-retry proof, plus
  current lifecycle, authorization, deadline and budget checks.
- Replan preserves the old Step when current Tool/Provider/policy/context facts make it illegal; new planning gets
  new identities and current bindings.

Tool v1 history is never silently rewritten to v2. Current defaults affect new planning only.

### Concept 6 — Reconciliation and unknown outcome

#### Student Answer

For a dispatched Provider call whose response was lost:

> 原来的 `A1` 进入 `PENDING_RECONCILIATION`

Correct. Preserve A1, the original operation identity and the held Reservation. Provider 404 alone is not proof
of non-execution unless the trusted Provider contract, exact identity and valid retention window make it so.

### Concept 7 — Repair and Compensation

The student correctly classified an incorrect internal `current_checkpoint_id` reference as `Repair`. Repair
fixes internal durable relationships with a new audit operation; it does not delete immutable Checkpoints.

For a verified wrong external publication, the student preserved A2 and created a new Compensation Operation.
Compensation requires current authorization and its own identity/idempotency/lifecycle. A timeout-unknown
Compensation enters its own reconciliation state.

### Concept 8 — Reservation recovery

#### Student Answer

> 应该把这个Reservation结算1800剩下的4200进行释放

Correct. Reservation is held capacity against a budget, not final usage. Unknown usage remains held and is never
treated as zero. Duplicate Resume or Queue delivery cannot reserve twice. Job Goal may complete while accounting
continues reconciliation/settlement without reopening the Job.

### Concept 9 — Bounded recovery

Recovery counts, limits, deadline, generation and evidence fingerprint must themselves be durable. The student
correctly said an in-memory count is ineffective after restart. When automation is exhausted, stop queries and
escalate; retain unknown truth and held Reservation. Day83 owns the complete human-control workflow.

### Concept 10 — Candidate versus authoritative apply

`decide_durable_recovery()` is pure. `InMemoryDurableAgentJobStore.apply()` models the conditional authority
boundary: duplicate, stale and terminal paths do not create executable work; successful paths advance versions,
append Checkpoint/Audit and model Reservation/Outbox change together.

The class and name explicitly state the limitation: an in-memory atomic mutation is not a PostgreSQL transaction
or cross-process durability proof.

## 8. Common Misconceptions

- Process memory survived one test, so it is durable. It is volatile and not shared authority.
- A Checkpoint is a model summary. It is an identity/version-bound committed execution fact.
- `published_at IS NULL` proves no publish. Publish may have succeeded before the Relay crashed.
- Queue redelivery means create a new Attempt. Duplicate transport is not new business intent.
- Lease expiry proves W1 did nothing. It only expires ownership; external execution may be real.
- Provider 404 proves no execution. Contract, identity, retention and other evidence still matter.
- Current Tool v2 can replace historical v1. Current defaults govern new planning only.
- Reservation is the budget. It is Attempt-bound held capacity against the budget.
- A terminal Job stops accounting. It stops new business progress, not bounded settlement/reconciliation.
- Rollback and tests close an incident. They stop future harm; historical outcomes still need classification.
- Passing in-memory tests proves durability. It proves deterministic local behaviour only.

## 9. Engineering Trade-offs

- Conservative reconciliation may delay progress, but prevents duplicated irreversible effects and false zero cost.
- Rich Checkpoints improve recovery/audit precision, but add schema, migration, storage and privacy obligations.
- Atomic state/Reservation/Outbox transactions reduce crash gaps, but do not create exactly-once cross-system effects.
- Short leases speed takeover, but increase false expiry and late-result frequency; long leases delay recovery.
- Strict immutable bindings may force Replan, but preserve explainability and prevent silent privilege/semantic drift.
- Append-only history costs storage, but enables incident scope, audit and correct compensation.

## 10. Hands-on Exercises

### Exercise 1 — Crash windows

Classify candidate-before-commit, commit-before-publish, publish-before-`published_at`, stale-Worker late result and
Provider-response loss. The student's results preserved commit truth, repeated only original identities and never
equated missing observation with non-execution.

### Exercise 2 — Mixed incident

A1 definitely not dispatched -> release and guarded replan/retry. A2 verified terminal 1800/6000 -> settle 1800,
release 4200, compensate only if unwanted. A3 TIMEOUT_UNKNOWN -> original identity, 6000 held, reconciliation.

### Exercise 3 — Conditional apply

Apply two recovery candidates from the same state version/fence. The in-memory Artifact demonstrates one apply and
one stale/duplicate refusal. A production implementation still requires real PostgreSQL evidence.

## 11. Relevant Framework Connections

PostgreSQL would enforce the conditional transaction and durable ledgers; an Outbox Relay/Broker/Consumer would
provide at-least-once transport. Celery, LangGraph, an Agents SDK or MCP host may adapt around these contracts but
cannot turn a callback, checkpoint object, ACK or retry setting into application business authority.

## 12. AI Backend Connections

Durable recovery protects long-running, expensive Agent work: Provider calls, Tool side effects, token/cost
reservations, immutable Prompt/Provider/Tool/Policy bindings, late responses and release rollback. It prevents
restart from duplicating a paid call or silently changing what an old Attempt meant.

## 13. English Interview

### Beginner

**What is a durable Agent Job?** It is an execution entity whose authoritative identity, lifecycle, Checkpoints,
reservations and recovery history survive process loss in durable storage.

**Why is process memory insufficient?** It is volatile and not a shared source of truth across Workers.

### Intermediate

**Resume versus Retry?** Resume continues the same identity from an authoritative Checkpoint. Retry creates a new
Attempt only after the original is proven not dispatched/accepted or explicitly safe, and after current guards.

**Why can Outbox delivery duplicate?** Broker acceptance may succeed before the Relay records publication. It
republishes the same event, while the Consumer uses idempotency, identity, current state and fencing.

### Senior

**Who owns durable lifecycle?** The application-owned Runtime defines semantics; a database transaction enforces
the guarded apply and commits lifecycle, Checkpoint, Reservation, Audit, Outbox and versions together.

**When is an incident closed?** Not after rollback/tests alone. Closure needs complete affected scope, per-Attempt
classification, reservation settlement/ownership, stale-worker/duplicate safety, audit continuity and controlled
rollout with stop conditions.

## 14. Mental Model Summary

```text
Durable Job        = execution truth that survives process loss
Checkpoint         = identity/version-bound committed recovery position
Resume             = same identity, safe continuation
Retry              = new Attempt after proven safety + current guards
Replan             = old plan retained, new plan under current facts
Reconciliation     = classify original unknown operation
Repair             = fix internal truth/reference
Compensation       = new operation for verified unwanted effect
Lease              = time-bounded ownership
Fence              = stale-writer rejection
Reservation        = Attempt-bound held budget capacity
Outbox             = committed publication intent, delivered at-least-once
```

## 15. Today's Takeaway

A durable Agent does not “continue where the model left off.” It reconstructs control from committed identities,
versions, bindings, reservations and external evidence; classifies what is known and unknown; and only then asks
an authoritative conditional boundary to resume, retry, replan, reconcile, repair, settle, compensate or stop.

## 16. Before Next Lesson Checklist

- [x] Durable Job and process memory are distinct.
- [x] Checkpoint identity/version/binding is explicit.
- [x] State + Checkpoint + Reservation + Audit + Outbox atomicity is designed.
- [x] At-least-once and duplicate Consumer guards are understood.
- [x] Resume/Retry/Replan/Reconciliation/Repair/Compensation are distinct.
- [x] Lease expiry, fence takeover and late-result evidence are classified.
- [x] Unknown Reservation remains held; verified 1800/6000 settles correctly.
- [x] Crash Window and bad-release exercises are complete.
- [x] Beginner, Intermediate and Senior English interviews are complete.
- [x] Thirty-two focused and 325 cumulative deterministic tests pass on Python 3.11.5.
- [ ] Real PostgreSQL transaction, Outbox/queue, multi-process Worker and Provider/Tool/billing recovery are run.
- [ ] Day83 human approval, interrupt and escalation are implemented.
