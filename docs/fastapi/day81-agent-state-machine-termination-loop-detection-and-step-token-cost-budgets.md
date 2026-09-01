# Day81 — Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets

## 1. Lesson Metadata

- Status: Completed (classroom scope)
- Phase: 7B — Agent Runtime and MCP Engineering
- Date: 2026-09-01
- Version: 1.0
- Difficulty: Senior
- Estimated time: 4–5 hours
- Prerequisites: Day71, Day74, Day78, Day79 and Day80
- Previous: Day80 — Tool Registry, Tool Schema and Permission Model
- Next: Day82 — Durable Agent Checkpoints, Resume and Recovery
- Artifact: `projects/ai-agent/`
- Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`

## 2. Learning Objectives

You can now:

1. make verified audit facts—not model prose—the source of state transitions;
2. distinguish terminal, waiting and reconciliation states;
3. order completion, uncertainty, failure, loop and budget guards correctly;
4. detect no-progress loops using verified fingerprints rather than activity;
5. distinguish Step, token, cost and context budgets;
6. reserve capacity only at an authoritative atomic boundary;
7. explain idempotency and fence tokens as different controls;
8. retain identity and history through revocation, rollback and compensation;
9. recover a bad controller release without blind replay;
10. state exactly what local in-memory tests do and do not prove.

## 3. Why This Matters

Day79 can propose a bounded next Step and Day80 can govern which Tools are visible and authorized. Neither alone
prevents a stale worker, an unknown external outcome, a no-progress loop or two controllers from spending the same
remaining budget. Production Agents need an explicit lifecycle whose authority is outside the model.

A state machine is not a decorative enum. It is the place where verified facts, legal transitions, current
authorization, identity, concurrency and reservations become one decision.

## 4. Roadmap Position

```text
Day78 bounded application Runtime
  -> Day79 framework-agnostic Controller
  -> Day80 governed Tool surface
  -> Day81 state / termination / loops / budgets
  -> Day82 durable checkpoint / resume / recovery
```

Day81 consumes Day79 `AgentStepResult` and Day80 governance outcomes. It does not bypass Day74 Tool Admission or
Day78 Runtime verification. Day82 will make the checkpoint and recovery boundary durable.

## 5. Lesson Map

```text
untrusted model recommendation
-> Day79 validated controller result
-> verified audit facts
-> legal transition + ordered guards
-> structured candidate decision
-> compare identity/state/fence + reserve atomically
-> APPLIED CONTINUE only -> executable effect
```

We first define state and events, then establish priority, progress and budgets, and finally apply the decision
under identity and concurrency controls.

## 6. Core Mental Model

```text
Model advice != authority

state + verified event + legal transition + current guards
  -> candidate decision
  -> authoritative conditional apply + reservation + fence advance
  -> effect only after APPLIED
```

The pure decision boundary can be replayed and reviewed. The apply boundary owns mutation. This separation also
prevents a framework callback from acquiring business authority merely because it can call a function.

## 7. Main Concepts

### Concept 1 — State follows verified facts

#### Tech Lead Question

Who controls the target process: the model or the state machine?

#### Student Answer

> The state machine controls the target process based on verified audit facts. The model can only provide recommendations.

#### Tech Lead Review

Correct. Model output is an input candidate. It cannot mark a Job completed, spend a budget, grant permission or
overwrite an Attempt.

#### Engineering Thinking

Represent the proposed action and the authoritative transition as different types. A
`TransitionDecision` includes expected state, Step identity and fence token so an old decision can be rejected.

### Concept 2 — Terminal, waiting and reconciliation are different

`COMPLETED`, `TERMINATED`, `FAILED` and `CANCELLED` are terminal. `WAITING` means a known prerequisite is missing.
`PENDING_RECONCILIATION` means an external outcome, dispatch or usage may exist but is not yet verified.

For `TIMEOUT_UNKNOWN`, keep the original Attempt and reservation:

> It should enter `pending_reconciliation` instead of retrying immediately.

A new retry would be a new external call and could duplicate the first side effect.

### Concept 3 — Guard priority determines truthful terminal state

If the goal is already verified complete, zero remaining Steps does not change the result:

```text
goal 3/3 verified + remaining_steps = 0
-> COMPLETED / GOAL_SATISFIED
```

If the goal is incomplete:

```text
goal 2/3 + remaining_steps = 0
-> TERMINATED / STEP_BUDGET_EXHAUSTED
-> no automatic retry
```

Uncertainty is checked before creating new work. A Job may be complete while an older cost settlement remains in
reconciliation; Job goal lifecycle and accounting lifecycle must not be collapsed.

### Concept 4 — Progress is not activity

A model can alternate Tool names or paraphrase actions forever without changing the verified world. Progress
must be represented by a fingerprint over verified goal, evidence, external state and authorized lifecycle.

When the hard threshold is reached, use `NO_PROGRESS_LOOP_DETECTED`, even if token or cost capacity remains. A
budget is a maximum consumption allowance, not proof that another turn is useful.

### Concept 5 — Four budgets, four questions

| Guard | Question |
|---|---|
| Step | May the controller create another transition? |
| Token | Is Job-level token capacity available to reserve? |
| Cost | Is spend capacity available, including held uncertainty? |
| Context | Does this one request fit the application contract? |

Context admission is:

```text
input_tokens + reserved_output_tokens + safety_margin
  <= application_context_budget
  <= provider_limit
```

Thus a 33k request is rejected under a 32k application limit even if the Provider limit is 128k. Token budget and
context window solve different problems.

### Concept 6 — Reserve and settle explicitly

Planning cannot merely read `remaining_tokens` and later decrement it. Competing controllers could both pass.
The authority boundary conditionally compares identity/state/fence and reserves Step/token/cost capacity in the
same commit.

If 6000 tokens were reserved and verified usage is 1800, settle 1800 and release 4200. If actual usage is unknown,
keep the reservation held and reconcile it; do not treat missing billing evidence as zero cost.

### Concept 7 — Idempotency is not fencing

An idempotency key suppresses duplicate effects for one semantic operation. A fence token makes an old worker's
authority expire. After a lease is revoked, advance the fence; all writes carrying the older token fail, even if
their payload looks valid.

The candidate decision therefore binds Job, Step, Attempt, expected state and fence. A terminal record rejects a
late `CONTINUE` decision.

### Concept 8 — Lifecycle and history survive governance changes

Authorization is checked again before dispatch. If it is revoked, block future execution but preserve the Step,
Attempt and audit trail. Release only capacity proven safe to release.

If Tool v1 is disabled and v2 is available, never rewrite the existing Step to v2. The old binding explains what
was authorized. A new planning operation may create a new Step bound to v2.

### Concept 9 — Compensation is a new operation

Rollback stops future harm; it cannot erase an external event. An already-applied effect is handled by a new,
authorized and auditable compensation operation. If compensation times out after dispatch, its state becomes
`PENDING_RECONCILIATION` as well.

An ambiguous Provider 404 is not proof that nothing happened when a dispatch marker exists. Retention windows,
Provider identity and local audit evidence must be reconciled before retry.

### Concept 10 — Candidate decision versus authoritative apply

The student summarized the separation as:

> 只返回结构化候选决定，由另一个边界原子应用

The teaching store demonstrates conditional apply in memory. The production design calls for a durable
conditional transaction—conceptually `UPDATE ... SET ... WHERE ... RETURNING`—plus reservation and Outbox records.
The repository does not claim that database evidence yet.

## 8. Common Misconceptions

- “The model selected `finish`, so the Job is complete.” Completion still needs verified goal evidence.
- “A different action means progress.” Only a changed verified progress fingerprint counts.
- “Context and token budget are the same.” One fits a request; the other bounds cumulative capacity.
- “Idempotency prevents stale writes.” That is the fence token's job.
- “404 means no Provider call happened.” Dispatch evidence can make the outcome unknown.
- “Rollback can delete the erroneous Step.” History is evidence and must be retained.
- “A compensation call reverses history.” It is a new action with a new identity.
- “Passing in-memory tests proves an atomic database transition.” It does not.

## 9. Engineering Trade-offs

- More states improve truthfulness but require explicit operator and recovery paths.
- Conservative reconciliation delays progress but avoids duplicate irreversible work.
- Application context limits may leave Provider capacity unused but preserve predictable contracts and margin.
- Strong fingerprints require domain-specific verified evidence; overly coarse fingerprints miss progress, while
  overly noisy ones hide loops.
- Atomic reservations reduce concurrency risk but add transaction and ledger complexity.
- Retaining immutable history costs storage but preserves auditability and incident reconstruction.

## 10. Hands-on Exercises

### Exercise A — Transition table

Classify these inputs and explain priority:

1. goal complete, zero Steps;
2. goal incomplete, zero Steps;
3. timeout unknown with unused budget;
4. known approval pending;
5. repeated unresolved fingerprint with cost remaining.

Expected: complete; Step-budget termination; reconciliation; waiting; no-progress termination.

### Exercise B — Reservation race

Create two candidates from the same fence and one remaining Step. Apply both. Verify that one is `APPLIED`, the
other is stale or conflicts, and capacity is consumed once.

### Exercise C — Governance drift

Plan against Tool v1, then disable v1 before apply while v2 is active. Verify that the old Step is retained and no
in-place rewrite occurs.

### Exercise D — Bad-release recovery

For A1 not dispatched, A2 verified terminal and A3 outcome unknown:

- A1: release safe reservations and replan under a stable release;
- A2: settle verified usage, but decide Job completion separately;
- A3: preserve identity, hold reservations and reconcile.

Then add an already-observed external side effect and model compensation as a new operation.

## 11. Relevant Framework Connections

LangGraph, an Agents SDK, MCP hosts and workflow engines may represent nodes, checkpoints or callbacks, but their
objects are adapters around this application-owned contract. Framework retry settings cannot override
`PENDING_RECONCILIATION`, current authorization, terminal state or application budgets. A framework checkpoint is
not automatically an authoritative business checkpoint.

## 12. AI Backend Connections

This design connects Agent reasoning to ordinary backend engineering:

- optimistic concurrency and fencing protect authoritative state;
- reservation ledgers make token and cost admission race-safe;
- append-only lifecycle history supports audit and incident analysis;
- Outbox-style publication prevents “state committed but work not scheduled” gaps;
- reconciliation handles at-least-once delivery and unknown external outcomes;
- current authorization and immutable execution bindings prevent silent privilege drift.

## 13. English Interview

### Q1: Who owns an Agent state transition?

The application-owned state machine. The model only recommends; verified audit facts, legal transitions and
current guards produce a candidate, and an authoritative conditional apply boundary performs the mutation.

### Q2: Why should `TIMEOUT_UNKNOWN` not be retried immediately?

Because dispatch may already have produced an external effect. Preserve the original Attempt identity and held
reservation, enter `PENDING_RECONCILIATION`, and verify the outcome before creating another Attempt.

### Q3: How do idempotency keys and fence tokens differ?

Idempotency collapses duplicate requests for the same semantic operation. A fence token rejects writes from a
worker whose lease or authority has expired. Robust systems often require both.

### Q4: How do you recover from a faulty controller release?

> Suspend new controller planning, step creation, and scheduling; Cancel or isolate erroneous releases/policies;
> Revert subsequent planning to the stable version; Revoke leases for old workers and advance fence tokens;
> Re-examine current lifecycles, releases, and authorizations at the Provider/Tool operational boundary; Determine
> the scope of impact based on release versions, time windows, and identities; Preserve the full history of Jobs,
> Steps, Attempts, Tool Calls, and reservations for all entities; Handle the recovery of in-flight Attempts;
> Separately classify, validate, and reconcile external events that have already occurred using new, auditable
> operations.

Passing tests on the restored version is necessary but not sufficient; closure needs scoped entities, reconciled
outcomes, settled reservations, audit continuity and controlled rollout.

## 14. Mental Model Summary

> Agent 状态机不是把模型说的话直接变成状态。模型只能给建议；系统用已验证的审计事实、当前生命周期、
> 授权、工具绑定、进展证据和预算守卫生成结构化候选决定，再由一个原子权威边界比较 Job/Step/Attempt、
> 旧状态和 fence token，提交状态、预算预留与新 fence。只有真正 `APPLIED` 的 `CONTINUE` 才能产生新的
> 可执行 Step。未知外部结果进入 `PENDING_RECONCILIATION`，已知前置条件不足进入 `WAITING`；终止不等于
> 删除历史，补偿也不是回写旧 Attempt。预算限制消耗，进展证据决定是否陷入循环，两者不能互相替代。

This final Chinese synthesis was supplied by the Tech Lead at the student's explicit request.

## 15. Today's Takeaway

A reliable Agent is not one that always finds another action. It is one that can truthfully complete, wait,
reconcile, terminate or fail—without losing identity, double-spending budget, accepting stale writes or allowing
model advice to become authority.

Day81's executable artifact validates that control model locally. It deliberately leaves durable checkpointing,
PostgreSQL transactions, queue publication and distributed recovery for later integration work.

## 16. Before Next Lesson Checklist

- [x] State, event, transition and guard roles are explicit.
- [x] Terminal, waiting and reconciliation states are distinct.
- [x] Completion precedes exhaustion when the goal is already verified.
- [x] Unknown outcomes retain original identity and held reservations.
- [x] Hard no-progress loops use `NO_PROGRESS_LOOP_DETECTED`.
- [x] Step, token, cost and context guards are independent.
- [x] Idempotency and fencing are not conflated.
- [x] Pure decision and authoritative apply are separate.
- [x] Twenty Day81 tests and 293 cumulative local tests pass.
- [ ] Durable checkpoints and restart recovery are implemented (Day82).
- [ ] Real PostgreSQL conditional transactions and Outbox publication are tested.
- [ ] Provider, Tool, billing and production integration are tested.

Next: Day82 — Durable Agent Checkpoints, Resume and Recovery.
