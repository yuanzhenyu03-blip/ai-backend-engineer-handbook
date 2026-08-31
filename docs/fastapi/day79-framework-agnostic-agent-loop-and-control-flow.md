# Day79 — Framework-agnostic Agent Loop and Control Flow

## 1. Lesson Metadata

- Status: Completed (classroom scope)
- Phase: 7B — Agent Runtime and MCP Engineering
- Date: 2026-08-31
- Version: 1.0
- Difficulty: Intermediate to Senior
- Estimated time: 4–5 hours
- Prerequisites: Day71–Day78
- Previous: Day78 — LLM Application Runtime Capstone, Checkpoint and English Interview
- Next: Day80 — Tool Registry, Schema and Permissions
- Artifact: `projects/ai-agent/`
- Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`

## 2. Learning Objectives

You can now:

1. define Agent, Agent Loop, Controller, Goal, Job, Step, Attempt, Action and Observation;
2. separate an untrusted model proposal from the application-owned control decision;
3. decide `CONTINUE`, `COMPLETE`, `WAIT`, `FAIL` or `RECONCILE` from trusted input;
4. distinguish one Day78 execution from the multi-step Agent Job;
5. create deterministic next-step and Attempt identities;
6. prevent duplicate, stale and terminal inputs from creating new side effects;
7. keep framework types behind a replaceable adapter boundary;
8. explain rollback, repair, reconciliation and compensation during an Agent Loop incident.

## 3. Why This Matters

A model can suggest useful work, but it cannot be the authority that advances a business Job. It may say
`COMPLETE` before the Goal is proven, say `CONTINUE` after the Job is terminal, or propose another call while
the previous external outcome is unknown. A safe Agent therefore needs application-owned control.

Day78 safely executes one constrained request. Day79 decides whether and why another constrained request may
exist. It does not rebuild Provider, Prompt, Routing, Tool Admission, execution, verification, reconciliation
or cost logic.

## 4. Roadmap Position

```text
Day71–Day77 independent LLM Runtime boundaries and tests
-> Day78 one integrated, bounded Runtime execution
-> Day79 application-owned Agent Loop and control decision
-> Day80 governed Tool Registry, Schema and Permissions
-> Day81 state machine, termination, loop detection and budgets
-> Day82 durable checkpoint, resume and recovery
```

Day79 opens Phase 7B. Framework refresh and selection remain Day87/Day88, so this lesson imports no Agent
framework and makes no framework recommendation.

## 5. Lesson Map

```text
trusted AgentStepInput
-> pure Controller decision
-> terminal / duplicate / stale guard
-> exactly one newly-created CONTINUE step
-> Day78 Runtime boundary
-> structured RuntimeResult + verified observations
-> repeat, complete, wait, fail or reconcile
```

## 6. Core Mental Model

First-use terminology:

```text
AI Agent = Goal + application-owned Controller + trusted state
           + controlled actions + verified observations

Agent Loop = trusted state -> prepare one step -> Day78 Runtime
             -> interpret result -> control decision
Controller = application component that owns the next control decision
Goal       = desired user outcome
Job        = one traceable execution of the Goal
Step       = one control step used to advance the Job
Attempt    = one concrete Runtime external execution within a Step
Action     = proposed controlled operation
Observation = verified result permitted as control input
```

An LLM, the Day78 Runtime, or a Controller alone is not a complete AI Agent. The student correctly concluded:

> 都不能称为完整AI agent

## 7. Main Concepts

### Concept 1 — The Controller owns control; the Runtime reports execution

The student selected the correct authority:

> 应用拥有的 Agent Controller

For a pending Runtime result, the initial answer was:

> 选择runtime的控制结果

Correction: Runtime status is a trusted execution fact, not the whole Agent control decision. The Controller
interprets `PENDING_RECONCILIATION` and returns `RECONCILE`.

### Concept 2 — Trusted input is separate from model advice

The minimum input identified in class was:

> job_id / current_step_id
> 用户目标
> 当前 Job 是否终止
> 已验证的 observations
> 当前 RuntimeResult
> 等待 reconciliation 的 identity

The implementation also binds `tenant_id` and Runtime `attempt_id`. `model_proposal` is retained as explicitly
untrusted advice. The Controller may disagree with it.

When asked what must be checked before accepting model `CONTINUE`, the student answered:

> 不知道

The required check is whether verified observations already satisfy the Goal. One completed Runtime call does
not mean the Agent Job is complete.

### Concept 3 — Closed control vocabulary

```text
CONTINUE  Goal incomplete; one safe next step may be prepared
COMPLETE  Goal proven by verified observations, or Job already terminal
WAIT      known prerequisite pending; no new Runtime call
FAIL      known non-recoverable result after Runtime recovery options
RECONCILE external execution may exist but is unknown; preserve its identity
```

With only two of three required observations and no third execution, the student first answered:

> external_outcome_unknown

Correction: “not executed” is known non-execution. The Goal is incomplete, so the result is `CONTINUE`. When
the scenario changed to “dispatched, then timed out with unknown outcome,” the correct answer was:

> RECONCILE

For an explicit refusal after Runtime recovery was exhausted, the correct decision was:

> FAIL

### Concept 4 — Deterministic identity and guarded execution

The student correctly described the `CONTINUE` path:

> 创建一个具有新 step_id 的下一步并通过 Day78 Runtime 边界处理

The same control decision delivered twice must resolve to the same next Step:

> 两次都解析到同一个 S2

The implementation derives stable `control_decision_id`, `step_id` and next `attempt_id`. Only a guarded
`CREATED` transition invokes the Runtime. `DUPLICATE_REPLAY`, `NOOP_STALE`, `NOOP_TERMINAL` and non-continue
decisions invoke it zero times.

### Concept 5 — Current authority differs from immutable history

Definitions:

```text
late       arrived later than expected; time alone does not grant or remove authority
stale      based on a control version that is no longer current
superseded explicitly replaced by a newer authorized identity
terminal   Job has ended and cannot be advanced
side effect an externally observable change or cost
```

The student correctly rejected rewriting an old `S1 -> CONTINUE` after `S2 -> COMPLETE` and rejected allowing
an old Worker to advance the terminal Job:

> 不能

The terminal result remains:

> 还是返回 `NOOP_TERMINAL` 并保持 Job 为 `COMPLETE`

The rejected action is not a new business failure. Preserve minimized audit history and create zero effects.

### Concept 6 — Framework-agnostic means application contracts stay authoritative

Framework-agnostic does not mean “no interface” or “never use a framework.” It means application state and
control results do not import framework-owned node, routing or state types.

When LangGraph `Command` first appeared without explanation, the student stopped the lesson:

> 不是，我还有个问题你是否先解释一下什么是LangGraph 的 `Command` 对象？

`Command` is a LangGraph primitive that can combine graph-state `update`, dynamic `goto`, optional parent
`graph` routing and interrupt `resume`. In this architecture it would belong only in a future Framework
Adapter. The application contract remains `AgentStepResult`; a contradictory adapter translation fails
closed. The student's authority rule was correct:

> 应该相信 Controller 的业务决策

### Concept 7 — Pure decision plus injected execution seam

`decide_control()` performs no Provider, Tool, database, framework or clock side effect. An
`AgentRuntimePort` Protocol separates orchestration from execution. Fake/Spy tests prove call counts, while a
composition test uses the real Day78 `prepare_runtime_attempt()` and `build_bound_application_request()`.

The student correctly rejected an all-Fake suite as sufficient and correctly classified real in-process Day78
composition without external infrastructure as:

> EXECUTED_LOCAL_RUNTIME

## 8. Common Misconceptions

- ❌ Runtime completed, therefore the Agent Job is complete. ✅ Goal completion requires verified observations.
- ❌ The model's `goto` or `COMPLETE` controls business state. ✅ Model output is an untrusted proposal; the
  Controller owns control.
- ❌ Not executed and unknown external execution are the same. ✅ Known non-execution may continue; unknown
  dispatch must reconcile.
- ❌ A late result is usable while it is “within a validity period.” ✅ Identity, original binding, validation
  and current authority decide usability.
- ❌ Idempotency makes stale Workers safe. ✅ Stable identity suppresses duplicates; current-state/fencing
  checks reject stale authority.
- ❌ Green unit tests prove durable or production behavior. ✅ They prove only the deterministic boundary
  actually exercised.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost / limitation |
|---|---|---|
| application-owned contract | portable authority | needs an explicit adapter |
| pure deterministic decision | easy side-effect testing | orchestration is a separate layer |
| conservative reconciliation | avoids duplicate effects/cost | holds work and reservation longer |
| immutable identity/history | auditable causality | repair cannot rewrite history |
| stable next-step identity | duplicate suppression | not a fencing substitute |
| fail-closed guards | correctness under uncertainty | may reduce availability |

## 10. Hands-on Exercises

### Exercise A — Decision table

For terminal, pending reconciliation, Runtime rejection, Goal satisfied, known wait and incomplete Goal,
predict the decision before running the table-driven test.

### Exercise B — Duplicate and stale delivery

Apply the same `CONTINUE` twice, then apply `S1` after the store has advanced to `S2`. Prove one Runtime call
for the duplicate case and zero for the stale case.

### Exercise C — Day78 composition

Prepare a Day79 next Step through the real Day78 Prompt selection, routing and bound request builder. Verify
Job, tenant, Attempt and rendered role identity. Do not perform Provider I/O.

### Exercise D — Production failure drill

Given a faulty loop mapping `PENDING_RECONCILIATION -> CONTINUE`, contain the release, bound the affected set,
reconcile the original and accidental Attempts separately, repair internal facts and compensate only confirmed
unwanted external effects.

## 11. Relevant Framework Connections

LangGraph was discussed only to demonstrate the adapter boundary. Its `Command` type must not become the
application's business contract. No framework was installed, imported, selected or run. Framework/job-market
refresh is Day87 and selection is Day88.

## 12. AI Backend Connections

- multi-tenant Research Agent Jobs;
- Day78 Runtime composition;
- model Tool proposal versus authorized execution and verified observation;
- timeout-unknown, late results, duplicate dispatch and cost reservation;
- stale Worker authority and terminal zero-effect guards;
- internal state repair versus separately authorized external compensation.

## 13. English Interview

### Beginner

**Question:** What is an Agent Loop, and what is its core purpose?

**Student answer:**

> It is a workflow control mechanism that guides the next steps of the work.

**Stronger answer:** An Agent Loop is an application-owned control loop that uses trusted state to decide the
next step. It determines whether the agent should continue, complete, wait, fail or reconcile an uncertain
result.

### Intermediate

**Student answer:**

> The model can only offer suggestions; the controller makes the final decision on the next step based on
> verified observations derived from certified runtime results.

**Correction:** Say “structured Runtime result” or “trusted Runtime status.” Runtime results and verified
observations are distinct trusted inputs. Model output remains an untrusted proposal.

### Senior

**Student answer:**

> Immediately terminate agent-loop-v1 while preserving all remaining Job/step/Attempt records; establish a
> bounded set of affected items and then classify them; reconciliation must be performed separately; handle
> internal remediation, while external components require independent compensation.

**Correction:** Disable v1 for new decisions without ambiguously killing in-flight work. Preserve every
record, reconcile each dispatched Attempt under its own identity, and compensate only a confirmed unwanted
external effect. Closure also needs effect, cost and rollout evidence.

## 14. Mental Model Summary

```text
Model output = suggestion
Controller = control authority
Day78 Runtime = one bounded execution authority

unknown -> preserve original identity and reconcile
late -> validate original binding and current authority
stale / superseded / terminal -> preserve evidence, zero control effect
framework -> replaceable translation convenience, never business authority
```

The student's final synthesis was:

> agent loop是一个控制智能体进行下一步工作。Controller是agent工作的控制器 模型给出下一步建议 Day78
> Runtime是一次具体执行 一次 step 要先进过验证最终Controller决定下一步如何执行 unknown进入pending_reconciliation
> late只要在有效期内还是可以继续使用 stale则需要保存审计历史不修改现在的状态 terminal则不进行下一步操作
> framework只是一个框架，无法替代实际业务工作流

Final correction: late-result usability is not time-based. It depends on original Job/Step/Attempt identity,
binding validation and current authority; superseded or terminal results have zero current control effect.

## 15. Today's Takeaway

A safe Agent Loop is not “ask the model what to do next.” It is an application-owned, deterministic control
boundary that turns trusted state into one closed decision, creates at most one causally identified next Step,
and permits only a newly authorized `CONTINUE` to cross the Day78 Runtime boundary.

Evidence: Python 3.11.5, `py_compile`, 8 Day79 tests and 251 cumulative Day72–Day79 tests. The first classroom
module-path unittest command failed because `tests/` is not a package; discovery was the correct command.

## 16. Before Next Lesson Checklist

- [ ] Can I define every first-use Agent term without relying on a framework?
- [ ] Can I explain why Runtime status is not the Controller decision?
- [ ] Can I distinguish known non-execution from unknown external execution?
- [ ] Can I list all five control decisions and zero-effect paths?
- [ ] Can I explain deterministic identity versus stale-authority fencing?
- [ ] Can I keep framework types behind an adapter?
- [ ] Can I state that Tool governance, full budgets/loop detection and durability remain Day80–Day82?
- [ ] Am I ready for Day80 — Tool Registry, Schema and Permissions?
