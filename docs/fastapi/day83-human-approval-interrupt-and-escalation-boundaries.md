# Day83 — Human Approval, Interrupt and Escalation Boundaries

## 1. Lesson Metadata

- Status: Completed at guided classroom scope; publication revision is tracked in Git history.
- Phase: 7B — Agent Runtime and MCP Engineering.
- Date: 2026-09-03.
- Version: 1.0.
- Difficulty: Intermediate to Senior boundary reasoning.
- Estimated study time: 4–5 hours (review estimate, not measured classroom duration).
- Prerequisites: Day74, Day78, Day79, Day80, Day81 and Day82.
- Previous: [Day82 — Durable Agent Jobs](day82-durable-agent-jobs-checkpoint-resume-and-recovery.md).
- Next: Day84 — Conversation Memory vs Durable Business-state Boundaries (planned; see [curriculum](../../CURRICULUM.md)).
- Artifact: [evolving ai-agent project](../../projects/ai-agent/README.md).
- Evidence: CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; Python3.11.5,53 focused/378 cumulative tests,
  26/26 seed scenarios and mandatory runnable checkpoint PASS. Python3.12 and real integrations NOT RUN.
- Assessment provenance: 17 guided English answers/reviews. Final Chinese synthesis was instructor-authored
  at the student's request; independent final synthesis NOT ASSESSED. Completion is not production readiness.

## 2. Learning Objectives

Practice explaining who owns approval authority; bind consent to exact actions; distinguish identity,
permission and approval; reject stale/conflicting callbacks; reason about transaction/dispatch race windows;
classify interrupts and unknown usage; design permissioned, bounded escalation; run the evolving Artifact;
and defend the local evidence boundary in English. These are learning targets, not a claim of independently
demonstrated mastery of every field.

## 3. Why This Matters

A Research Agent can publish the wrong report twice even though a human clicked Approve once. Between that
click and dispatch, permissions can change, the report can be edited, a Worker can lose its lease, or a
timeout can hide a successful external action. A stop button alone cannot undo publication or prove zero cost.
Team ownership and audit trails matter because unresolved work survives the original Worker or operator.

Human control therefore belongs in the same guarded application lifecycle as execution and accounting.
It adds review latency and operational ownership, but prevents a model statement or stale human decision
from silently authorizing an irreversible action.

## 4. Roadmap Position

Day82 established original-identity recovery and committed execution facts. Day83 introduces human intent
without weakening Day74 admission, Day78 Runtime, Day79 Controller, Day80 governance or Day81 state/budgets.

```text
Day78 Runtime -> Day79 loop -> Day80 governance -> Day81 state/budgets
-> Day82 durable recovery -> Day83 human control
-> Day84 memory versus business truth -> Day85 coordination -> Day86 security
```

Day84 will explain why remembered conversational consent remains context, not an authoritative approval
or Checkpoint. No framework has been selected; that decision remains behind the planned Day87/Day88 gates.

## 5. Lesson Map

Risk -> exact request/decision -> lifecycle/current authorization -> atomic apply/Outbox -> dispatch guard
-> interrupt windows -> late-result evidence -> bounded recovery/ownership -> mixed rollback -> local eval.

## 6. Core Mental Model

```text
human input != effective approval != execution intent != verified external outcome

trusted facts -> pure candidate -> guarded conditional apply
-> state + control records + Checkpoint + Reservation + Audit + Outbox
-> consumer claim + execution-time guards -> admitted external boundary
```

The diagram is the production contract. This Artifact implements an in-memory local model, not a durable
database or atomic network send. Approval is necessary when policy requires it, but never sufficient alone.

## 7. Main Concepts

### Concept 1 — Approval authority and exact scope

#### Tech Lead Question

The model says the user approved publication. Who can establish that fact?

#### Student Thinking

The answer identifies application ownership; it does not independently enumerate the validation schema.

#### Student Answer

> 应用拥有的 durable control boundary 来认定

#### Tech Lead Review

Human approval is an authorized person's consent to a specific high-risk action. An Approval Request asks for that decision; an Approval Decision records one person's response. The application authenticates the actor, checks tenant/role and separation of duties, validates the exact request/action and persists accepted facts. Model text, UI clicks and callback correlation alone are not authority. Public read and irreversible publication can have different risk policies; low risk still needs ordinary authorization.

#### Engineering Thinking

Bind tenant, Job, Step, Attempt/planned operation, Tool/version, normalized arguments, Artifact/version, requester and policy/version. Separate request, decision and dispatch identities. Exact binding prevents consent for report v7 from silently authorizing v8.

#### Production Example

A Research Agent reads public material without this publication approval, but publishing report-7 v7 requires the eligible tenant approver.

#### Framework Connection

Authenticated API ingress would derive actor/tenant facts server-side; this project injects trusted fixtures, not a live auth service.

#### Exercise

Change the artifact version while retaining the approval: execution must be refused and new approval requested.

### Concept 2 — Lifecycle and current authorization

#### Tech Lead Question

If yesterday's approval is valid but today's permission is revoked, may dispatch proceed?

#### Student Thinking

The student consistently refused expired, wrong-tenant and revoked-permission execution; English later mixed authentication and authorization.

#### Student Answer

> 不能

#### Tech Lead Review

Authentication asks who the actor is; authorization asks what the actor may do now; approval asks whether this exact high-risk action was consented to. Business validation and Tool admission are additional checks. Approval does not override any of them. NOT_REQUIRED, PENDING, APPROVED, REJECTED, EXPIRED, REVOKED, SUPERSEDED, CANCELLED and CONFLICT are distinct control classifications. An unanswered deadline is overdue, not a fabricated REJECTED decision. A conflict is evidence, not permission to overwrite the original decision.

#### Engineering Thinking

Recheck expiry, current permissions, tool enablement, lifecycle, budget and fencing at apply and dispatch. High risk cannot silently become NOT_REQUIRED. Supersession retains old history and uses new identities; this fixture does not implement a real successor-request API.

#### Production Example

A disabled bound Tool v1 blocks dispatch; active v2 is not an automatic substitute. An approved callback arriving after request cancellation is rejected with callback evidence.

#### Framework Connection

Policy service unavailable before dispatch means known control blockage, not proof that a remote action ran. Bound the wait and escalate with root reason APPROVAL_POLICY_UNAVAILABLE and trigger POLICY_WAIT_DEADLINE_EXCEEDED.

#### Exercise

Distinguish a tool being disabled from a request being cancelled; neither should silently rewrite a prior approval decision.

### Concept 3 — Atomic commit, replay and dispatch race

#### Tech Lead Question

The process crashes after the Outbox Intent committed but before publication. What does recovery do?

#### Student Thinking

The student preserved the original intent, then independently named an atomic idempotent claim.

#### Student Answer

> 恢复进程应该继续发布已提交的原 Outbox Intent

#### Tech Lead Review

A candidate is a proposed decision, not authority to call a Tool. Production design commits related state, Approval/control facts, Checkpoint, Reservation, Audit and Outbox under a conditional transaction. Before commit, a prior validation is insufficient. After commit, recover the original intent, not a new business operation. Identical callbacks return stored results without repeated business effects; conflicting decisions are rejected/audited and may create escalation without overwriting the first decision.

#### Engineering Thinking

The conditional boundary checks expected snapshot, identity, lifecycle, version and fence. A losing candidate rereads committed facts after a failed conditional apply. Dispatch has a separate atomic consumer claim and current-fact recheck. At-least-once transport and an in-memory claim do not guarantee external exactly-once effects.

#### Production Example

Two consumers receive one publication event; only one local claimant invokes the fixture effect. If a claim or remote result becomes uncertain, do not infer no effect or blindly create A2.

#### Framework Connection

A PostgreSQL transaction/unique constraint would implement durable coordination. Here RLock plus a single snapshot swap models local atomicity; no SQL, real Relay or broker ran.

#### Exercise

Change authorization between plan/apply and again between intent commit/dispatch; both paths must block.

### Concept 4 — Interrupt, cooperative cancellation and stale workers

#### Tech Lead Question

Does stopping a Worker prove an already-dispatched external action stopped?

#### Student Thinking

The student recognized uncertainty; a later English answer still needed correction that lease expiry removes authority, not physical execution capability.

#### Student Answer

> 不能保证立即停止

#### Tech Lead Review

An interrupt is an application-controlled request to stop further work. Cooperative cancellation means the Worker observes and obeys it at checkpoints; it is not a remote kill guarantee. Pre-dispatch cancellation blocks the call and releases only proven-unused reservation. Post-dispatch, use verified evidence if available; otherwise retain original identity in PENDING_RECONCILIATION. Interrupt accepted, cancellation observed, Worker stopped and external effect absent are separate facts.

#### Engineering Thinking

A fence is an execution generation checked on writes: old generations cannot mutate current business truth. Preserve a stale Worker's late result with original Attempt/operation identity; the current authorized recovery path must verify it. Claim-before-call is conservative: uncertainty in that gap is not absence proof.

#### Production Example

W1 fence8 loses ownership; its success arrives after revocation. Save evidence but do not restore W1's write authority or reopen a terminal Job.

#### Framework Connection

Queue/Worker cancellation and external tools have separate lifecycles. Local tests cover observation and stale-write refusal, not cross-process stop propagation.

#### Exercise

Run both interrupt windows and compare call count, state, fence, evidence and held/released units.

### Concept 5 — Bounded recovery and accountable escalation

#### Tech Lead Question

When automated recovery is exhausted, what should happen to unresolved work?

#### Student Thinking

The student identified durable ownership; deadlines, alerts and fallback were then made explicit through follow-up.

#### Student Answer

> 将未解决事项持久化交给有权限的负责人

#### Tech Lead Review

Escalation is a controlled handoff of an unresolved issue to an authorized owner. Persist root reason, trigger, priority, original identities, evidence, owner, handling deadline and alert state. Recovery has time and attempt limits that must survive continuation. On exhaustion stop automatic queries/retries, keep unknown reservations held and create a handoff. An alert or acknowledgement is not resolution.

#### Engineering Thinking

If the owner is unavailable or overdue, record it and route to a designated authorized fallback with a new deadline and alert. No authorized recipient means unroutable and blocked, not permission to proceed. Approval rejection must not become retry-until-approved.

#### Production Example

Three synthetic query intents consume the allowance; the next recovery step creates an escalation with held6000 and operations ownership. The alert remains PENDING; no actual query or notification was sent.

#### Framework Connection

The Day82 recovery core is reused. Real notification delivery, acknowledgement, closure and post-deadline routing workers remain future integration, not implemented by the local alert record.

#### Exercise

Distinguish policy-wait timeout, approval-response timeout and external recovery exhaustion without discarding the original cause.

### Concept 6 — Mixed rollback and reservation continuation

#### Tech Lead Question

For A1 never dispatched, A2 verified1800/6000 and A3 unknown, how do reservations change?

#### Student Thinking

The initial Chinese classification was correct; the later English answer combined A1 and A2 ambiguously and was corrected again.

#### Student Answer

> release、settle、held

#### Tech Lead Review

A1 releases6000 when non-execution/zero use is proven. A2 settles1800 and releases4200, never releases6000 first. A3 keeps6000 HELD and reconciles the original identity. A completed Job and unresolved accounting have distinct lifecycles: do not reopen the Job to reconcile costs. Verified settlement can proceed after query exhaustion without resetting the query allowance.

#### Engineering Thinking

Quarantine old V7 and stop new work, retain the full impact set and audit history, constrain stale workers/duplicate messages and classify each Attempt. Compensation for a verified unwanted publication is a new operation with its own applicable approval; rollback does not undo external effects. Ownership alone does not satisfy incident closure criteria.

#### Production Example

The impact set links tenant/Job/Step/Attempt with approval, policy, Checkpoint, Outbox, operation, reservation, lease/fence and late evidence. Controlled rollout needs stop conditions and evidence, not just a green test.

#### Framework Connection

The local Day82 accounting seam assumes one units reservation per Attempt and rejects ambiguous settlement. Real billing and compensation are NOT RUN.

#### Exercise

Explain why restoring old code and assigning owners are insufficient, by themselves, to close the incident.

### Concept 7 — Seed evaluation and evidence honesty

#### Tech Lead Question

A safety eval fails because an unapproved action is allowed. Change the expected result or fix the implementation?

#### Student Thinking

The student defended the expectation and asked the instructor to explain first-use terminology; this teaching correction is preserved.

#### Student Answer

> 修正实现并保留原预期，我觉得根据之前提示词约束需要解释一下第一次出现的名词比如：eval

#### Tech Lead Review

An eval is a check of behavior against expected facts. A seed eval is the initial small versioned set of scenarios, not a complete evaluation platform. A deterministic grader uses fixed comparison rules rather than a model judge. Here it invokes the actual local Day83 boundary, compares five decision fields, required evidence and forbidden effects. It rejects unknown enums/fixture fields rather than weakening expectations.

#### Engineering Thinking

The 26 version1 expectations were authored before the first run and not changed to fit outputs. Some edge cases are assistant-authored and still need independent human review before a release gate. The three grader unit tests are distinct from the 26 eval scenarios.

#### Production Example

The original fixture missed Day74's required warnings field; adding warnings: [] repaired the fixture without changing expected VERIFIED. A second fixture reused gate-1, was correctly blocked, and was repaired with a new command identity.

#### Framework Connection

All effects use existing in-process Day74/78 seams. Local success is EXECUTED_LOCAL_RUNTIME, not permission to make a real Provider call or evidence of production safety.

#### Exercise

Run the frozen seed suite and verify both a deliberately wrong reservation action and forbidden-effect output fail the grader.

## 8. Common Misconceptions

| Topic | Incorrect or incomplete view | Correct model / quick check |
|---|---|---|
| Authentication | Successful login grants execution permission | Identity, current permission and exact approval are separate checks. |
| Approval | APPROVED means dispatch is always allowed | Recheck expiry, binding, current authorization, Tool, state and fence. |
| Callback conflict | Inspect execution evidence and overwrite a decision | Compare approval identities/content; reject conflict, retain original and audit. |
| Interrupt | Post-dispatch always means unknown | Classify actual trusted evidence; unknown alone enters reconciliation. |
| Lease expiry | The external action must have stopped | Authority expired, but external effects may continue. |
| Reservation | Release6000 and then settle1800 | Settle1800, release4200; treat A1 and A2 separately. |
| Escalation | Send an alert and consider the issue solved | Authorized ownership, deadline and verified closure are separate facts. |
| Evaluation | Change expected output to match implementation | Preserve safety requirements and fix the defect. |
| Evidence | Green local tests authorize a real call | Evidence and authority are independent. |

These confusions are plausible because UI status, English terms and one process's observation can look like
business truth. The remedy is to name the exact actor, operation, current permission, committed fact and
external evidence rather than infer them from a label. The full record preserves where the student's actual
answers were already correct versus where the instructor supplied additional reasoning.

## 9. Engineering Trade-offs

| Choice | Improvement | Cost / alternative / review question |
|---|---|---|
| Risk-based versus approve-every-step | Human attention stays on consequential work | Policy must be current and fail closed; use stricter review where risk requires it. |
| Exact bindings versus broad reusable consent | Prevents semantic/privilege drift | Changes require new approval; review which inputs define the action. |
| Atomic Outbox versus direct call during apply | Preserves intent across commit/publication gaps | Adds delivery/reconciliation complexity; cannot make network effects exactly-once. |
| Conservative held reservation versus premature release | Avoids duplicated spend and false zero cost | Capacity remains tied up; bound recovery and ensure accountable ownership. |
| Cooperative stop versus claiming instant termination | Honest control over future work | Already-sent work needs evidence/reconciliation; provider cancellation contracts vary. |
| In-memory deterministic model versus real DB test | Fast reproducible boundary checks | No durability proof; production adoption needs real concurrency/crash tests. |

## 10. Hands-on Exercises

### Exercise 1 — Approval race

Question: Can a previously allowed candidate dispatch after expiry, permission revocation or Tool disablement?

Think First: Identify the separate plan, apply and dispatch windows.

Starter Artifact: [control tests](../../projects/ai-agent/tests/test_day83_human_control.py).

Expected Output: Block stale execution; identical callback has no repeated business effects; conflict preserves
the original decision and audit. Two local consumers produce one local effect.

Explanation: Conditional apply and current dispatch guards are both needed. A claim cannot prove an unknown
external operation never ran.

Follow-up Question: Why must recovery publish the original committed intent rather than create another?

### Exercise 2 — Interrupt

Question: How do pre-dispatch and post-claim unknown outcomes differ?

Think First: Interrupt accepted, cancellation observed and external effect absent are not equivalent.

Starter Artifact: [checkpoint example](../../projects/ai-agent/examples/day83_human_control_checkpoint.py).

Expected Output: Before dispatch: zero call/release6000. After possible dispatch: original identity/held6000,
PENDING_RECONCILIATION, advanced fence, late result retained without authoritative write.

Explanation: The example is synthetic and in-process; it does not kill a real Worker or undo a remote effect.

Follow-up Question: Can a stale successful result still help the current owner reconcile?

### Exercise 3 — Escalation

Question: What happens after bounded recovery or an owner deadline?

Think First: Separate root reason, escalation trigger, owner and resolution evidence.

Starter Artifact: [scenario fixtures](../../projects/ai-agent/src/human_control_scenarios.py).

Expected Output: Three query intents, then exhaustion escalation with original identity, held6000, authorized
owner and synthetic deadline2000; alert PENDING. No actual query or alert delivery occurs.

Explanation: Count/deadline state is continued rather than reset. Owner fallback is permission checked.
Actual notification/closure and scheduled owner-timeout handling remain integration work.

Follow-up Question: Why does policy unavailability before a call not mean TIMEOUT_UNKNOWN?

### Exercise 4 — Failure and rollback

Question: Does stopping V7's new work close the incident?

Think First: Inventory affected identities and classify A1/A2/A3 independently.

Starter Artifact: [seed cases](../../projects/ai-agent/evals/day83_human_control_seed.jsonl), including HC19.

Expected Output: A1 release6000; A2 settle1800/release4200; A3 held6000. Compensation uses a new approved
operation. Late workers/duplicates remain constrained; unresolved outcomes have owners and deadlines.

Explanation: Containment is not resolution; restoring code does not undo effects or settle unknown usage.

Follow-up Question: Which explicit closure and controlled-rollout criteria are still unmet?

### Mandatory runnable checkpoint and seed eval

From `projects/ai-agent`:

```sh
PYTHONPATH=src python3.11 -m unittest discover -s tests -p 'test_day83*.py' -v
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
PYTHONPATH=src python3.11 evals/run_day83_seed_eval.py
PYTHONPATH=src python3.11 examples/day83_human_control_checkpoint.py
```

Actual classroom interpreter: Python3.11.5 at the absolute path in
[historical command evidence](../../projects/ai-agent/evidence/day83-validation.json).
See [repository-update validation](../../projects/ai-agent/evidence/day83-repository-validation.json)
for fresh results in this checkout. Python3.12 remains NOT RUN unless that evidence explicitly says otherwise.

The checkpoint composes the existing Day74/78/79/80/81/82 code. The local Tool simulator runs once on the
valid path; real Provider/Tool calls remain zero. Seed eval:26 cases,version1,26 PASS; 50 control tests and
3 grader tests total53, cumulative378. Seed scenarios are distinct from unit-test counts.

Actual failures preserved: missing required `warnings` caused SCHEMA_INVALID instead of VERIFIED (fixture
fixed without changing expected); reuse of command `gate-1` was rejected, causing scenario StopIteration
(fixed with new command identity and regression). Injected precommit failure asserts unchanged snapshot.
Environment clone recovery is not an application crash-recovery test. Full details remain in the design/record.

## 11. Relevant Framework Connections

PostgreSQL would own conditional transactional state, decision identities, audit and Outbox. An authenticated
API would derive principals and tenant-scoped policy facts, never trust caller-provided permission flags.
A queue/Worker must combine at-least-once delivery, atomic claim, fence checks and cooperative cancellation.
Share immutable operation identities across these layers; isolate credentials, tenant authority and mutable
execution ownership. Review stale writes, duplicate effects and evidence gaps.

Only local Python seams ran. PostgreSQL, FastAPI callback ingress, real queues/Workers, notifications and
framework adapters are conceptual connections, not verified integrations.

## 12. AI Backend Connections

A model may recommend publication or compensation but cannot approve its own high-risk action. Provider
success is only evidence to validate, not automatic business completion. Unknown Tool effects and usage keep
original identity and held capacity while authorized recovery classifies them. These boundaries prevent
tool abuse, duplicated paid calls and conversational memory masquerading as permission.

The optional real Provider gate is NOT RUN. A future gate requires immediate explicit authorization,
an existing adapter, non-sensitive synthetic input, exact provider/model/profile/API version, at most one
successful call, timeout and tiny token/cost budget, no automatic retry, redacted evidence and original
Attempt handling on timeout. It must produce no real external business Tool effect. Credentials belong in
environment/Secret Store, not chat or logs. This local checkpoint does not authorize that gate.

## 13. English Interview

Vocabulary: approval (审批), authorization (权限), authentication (身份认证), interrupt (中断请求),
escalation (升级交接), idempotent claim (幂等执行认领), fence (旧写入隔离代际), reconciliation (核实对账).

Useful expressions: “Approval does not replace…”; “The result remains unknown…”;
“Preserve the original identity…”; “This evidence proves only…”.

### Beginner

Question: What is human approval?

Actual student: “Manual iteration is a candidate decision for an iteration generated when facing high-risk execution.”

Review: Use human approval, not manual iteration. Define exact, time-limited consent and application validation.

Strong answer: Human approval is a time-limited decision made by an authorized person to permit a specific
high-risk action. The application validates and records it; current execution checks still apply.

### Intermediate

Question: Approval versus authorization?

Actual student: “Approval is a high-risk decision made at the human level; upon authorization and successful authentication, the application is granted limited execution privileges.”

Review: Identity is not permission; consent does not automatically grant either. Lead with the distinction.

Strong answer: Approval records an authorized person's consent to a specific action. Authorization determines
whether the actor may currently perform it. Valid approval cannot replace execution-time authorization.

### Senior

Question: A Worker loses its lease and later reports success. What should happen?

Actual student: “Expired worker tasks cannot continue execution, but the execution process can be retained as evidence for subsequent auditing.”

Review: Lease expiry removes authoritative write rights, not the physical ability of remote work to continue.

Strong answer: Reject the stale Worker's state update, but preserve its late result under the original
Attempt and operation identities. The current authorized recovery process can verify it for reconciliation.

Common weak answer (instructor example): “It was approved and the Worker stopped, so we can release the budget.”
This confuses consent, current authority and external evidence.

All17 actual English answers and individual corrections, including incident scope and bounded Provider
evidence, are in the [classroom record](../../projects/ai-agent/docs/day83-human-control-classroom-draft.md).
Do not turn guided feedback into invented independent student answers.

## 14. Mental Model Summary

Day82: committed execution facts govern recovery.
Day83: human intent becomes scoped validated facts, but current guards still govern execution.

Instructor-authored final Chinese summary, requested by the student with “你帮我总结吧” and acknowledged
with “好的”; not an independent student synthesis:

人批准具体动作，应用掌握执行权；中断不等于外部停止，未知不等于失败，升级不等于问题已解决。
精确审批、当前权限、受保护提交和派发检查缺一不可。未知保持原身份与 HELD；确认用量才结算。
恢复耗尽有界停止并交接负责人、证据、期限与告警；补偿是新操作，需独立审批。

## 15. Today's Takeaway

Human control is a scoped application protocol, not a UI label or model sentence. The hardest boundary
is after dispatch: lost ownership, interruption and missing responses do not erase effects. Keep facts
honest, recovery bounded and ownership explicit. Local tests support that model without proving production
durability. Independent final synthesis and real integrations remain unassessed/unrun.

## 16. Before Next Lesson Checklist

- [x] Guided classroom coverage of approval, lifecycle, interrupt and escalation recorded.
- [x] Approval race, interrupt, escalation and mixed rollback exercises preserved.
- [x] Evolving Artifact checkpoint and26 seed cases executed locally.
- [x] 17 English interview answers/reviews preserved with student/instructor attribution.
- [ ] Independently explain the full lifecycle in Chinese without instructor synthesis.
- [ ] Independently review all seed expected facts before treating them as a release gate.
- [ ] Validate on repository-standard Python3.12.
- [ ] Verify real authenticated callback, PostgreSQL transaction, Relay/Queue/Worker and external effects.
- [ ] Start Day84 memory versus durable business-state boundaries.

Related: [design](../../projects/ai-agent/docs/DAY83_HUMAN_APPROVAL_INTERRUPT_ESCALATION.md),
[cheat sheet](../../cheat_sheets/fastapi.md#day83--human-approval-interrupt-and-escalation-boundaries-phase-7b),
[interview handbook](../../interview/fastapi.md#day83--human-approval-interrupt-and-escalation-boundaries-phase-7b).
