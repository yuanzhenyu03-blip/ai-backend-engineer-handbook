# Day78 — LLM Application Runtime Capstone, Checkpoint and English Interview

## 1. Lesson Metadata

- Status: Completed (classroom scope)
- Phase: 7A — LLM Application Engineering
- Date: 2026-08-28
- Version: 1.0
- Difficulty: Intermediate to Senior
- Estimated time: 4–5 hours
- Prerequisites: Day71–Day77
- Previous: Day77 — Fake Provider, Contract Tests and LLM Regression Tests
- Next: Day79 — Framework-agnostic Agent Loop and Control Flow
- Artifact: `projects/ai-agent/`
- Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`

## 2. Learning Objectives

You can now:

1. define the application-owned Runtime responsibility boundary;
2. order Contract resolution, routing, binding, dispatch, validation, Tool
   Admission, execution, outcome verification, completion and cost settlement;
3. preserve immutable Job/Attempt identity across unknown and late execution;
4. build a deterministic Provider-request bridge tied to the Prompt binding;
5. distinguish rollback, repair, compensation and reconciliation;
6. explain idempotency versus fencing;
7. report structured results and honest evidence levels;
8. defend the Phase 7A design in an English interview.

## 3. Why This Matters

Correct components can still form an unsafe system if orchestration changes
their order. A Runtime can route before checking compatibility, apply a new
Prompt default to an old Attempt, trust Provider `SUCCESS`, execute a revoked
tool, accept an unverified outcome, retry an unknown call, or release unknown
cost.

Day78 answers whether Day71–Day77 can form one consistent, runnable, auditable
and recoverable application execution path. It is not a Provider SDK call, an
Agent Loop, or production proof.

## 4. Roadmap Position

```text
Day71 architecture/failures
-> Day72 Capability Profile + Adapter
-> Day73 Prompt Contract + binding
-> Day74 output/tool safety
-> Day75 stream/cache/batch boundaries
-> Day76 routing/recovery/cost
-> Day77 deterministic contract evidence
-> Day78 integrated application Runtime
-> Day79 Agent Loop drives Runtime
-> Day80 governed Agent tools
```

Day79 decides whether to continue, stop or wait. It must not reimplement
Day78's Provider, Prompt, validation, recovery, completion or cost boundaries.
Day80 adds governance without bypassing Day74/Day78 authorization.

## 5. Lesson Map

```text
requirements -> eligibility -> route -> immutable preparation
-> claim/gates -> ProviderOutcome -> candidate validation
-> Tool Admission -> execution -> outcome verification
-> guarded completion/reconciliation -> cost -> evidence
```

## 6. Core Mental Model

```text
Runtime = orchestration order + authoritative lifecycle + recovery evidence
Component = translation / validation / decision
Component != competing state authority
```

```text
Provider SUCCESS != valid result
complete candidate != admitted call
Admission != execution
execution != verified outcome
verified outcome != durable completion
timeout != definitely not executed
```

## 7. Main Concepts

### Concept 1 — Resolve and bind before dispatch

**Tech Lead Question:** Can a cheap route be chosen before requirements are
fixed?

**Student Answer:**

> 先解析并固定本次 Contract requirement，再做 candidate eligibility 和 route selection

**Tech Lead Review:** Correct. Prompt, Output, Tool, parameter and capability
requirements define eligibility. Price and latency rank only eligible paths.
Persist the RoutingDecision, Prompt/Profile bindings and reservation before the
external call. Current defaults govern only new Attempts.

**Engineering Thinking:** A durable claim is a guarded conditional update such
as `UPDATE ... WHERE status='PREPARED' RETURNING ...`; no database transaction
spans Provider I/O.

**Production Example:** A cheaper Adapter without required fencing is excluded,
as is a candidate whose capability evidence is stale.

**Exercise:** Exclude incompatible Profiles before applying cost preference.

### Concept 2 — One authoritative Runtime lifecycle

**Student Answer:**

> 应该由一个统一的 Runtime Attempt lifecycle/store 持有权威状态，而组件只返回验证/决策结果

**Tech Lead Review:** Correct. The Runtime owns Job/Attempt state and ordering.
Prompt, routing, Adapter and Tool components return facts or decisions.

Day78 also resolves the Day73 structured-message to Day72 string-request seam:

> 建立一个应用拥有、确定性且可验证的 message-to-provider-request bridge，并保证发送 payload 与 A1 的 Prompt binding 一致

The bridge canonically preserves role/order and verifies the rendered hash.
Provider-specific wire translation remains inside the Adapter.

**Exercise:** Change one rendered message after binding; dispatch must fail.

### Concept 3 — Every result remains untrusted until its gate passes

For Provider `SUCCESS`, the student required:

> 验证shema、语义、授权、tool admission等

The Provider envelope binds outcome, Job/Attempt/correlation identity, one
candidate source and its hash. A protected reference still needs current
authorization. A complete stream, cache candidate or batch item continues
through current validation and Admission.

Before execution:

> 必须在 Tool Execution 前再次检查当前 lifecycle

After execution:

> 不能，必须验证返回的结果outcome

The capstone calls the real Day74 Admission, executor and
`verify_publish_outcome()`. Only a schema-, semantic- and identity-verified
outcome may try guarded completion against current lifecycle.

**Exercise:** Disable the tool after Admission and prove zero effects.

### Concept 4 — Unknown execution preserves identity

**Student Answer:**

> A1应该进入pending_reconciliation

Unknown dispatch cannot be reopened or replaced. Preserve the original
Attempt, binding and reservation; create no A2. A late result uses the original
binding, but stale, cancelled, superseded or terminal results cannot overwrite
current state.

**Trade-off:** This can delay recovery and hold budget, but prevents duplicate
cost and effects.

**Exercise:** Race two workers, prove one claim winner, then prove an unknown
winner cannot be claimed again.

### Concept 5 — Repair, compensation, idempotency and fencing

The student initially jumped directly to:

> 应该进行compensate

Correction: reconcile and classify facts first. Internal repair preserves
historical meaning. Compensation is a separate external operation only for a
confirmed effect requiring reversal.

The corrected answer was:

> 还是保留 A3 历史并创建独立的 compensation 操作

Compensation has a new identity/key, causal source references, current
authorization, Admission, execution, verification and reconciliation.

Idempotency suppresses duplicate effects. It cannot authorize a stale first
execution. Downstream fencing or an equivalent conditional business write must
reject older tokens. A kill switch alone cannot close the check/send race.

**Exercise:** Resume an old worker after a newer fence exists; downstream must
reject it.

### Concept 6 — Cost is part of Runtime truth

**Student Answer:**

> cost reservation减去usage将剩下的释放到job的总体budget中

Estimate, reservation, reported, actual and unknown are separate facts. Settle
known usage and release only unused reservation. Never write unknown as zero.

The student answered `不知道` about a crash between old reservation release and
replacement creation. The correction was one local transaction, or an
outbox/saga plus idempotent ledger when accounting is external. Reconcile the
original settlement identity; never replay Provider/Tool to repair billing.

**Exercise:** Reserve 10, settle 6 and replay; release 4 exactly once.

### Concept 7 — Structured result and evidence

**Student Answer:**

> 返回带有阶段、状态、Job/Attempt identity、recovery action 和 evidence 的结构化结果

Safe evidence includes stable identities, bound revisions, reason codes,
recovery and evidence level. It excludes prompts, credentials, customer data,
raw payloads and SDK exception text.

The student initially did not know the safe evidence for no route. The class
added Contract/policy revisions, candidate, required/observed capability and
exclusion reason.

## 8. Common Misconceptions

- ❌ Provider success completes the Job.
  ✅ It starts the application validation chain.
- ❌ Admission is permanent authority.
  ✅ Current lifecycle/authorization still governs execution.
- ❌ Timeout authorizes fallback.
  ✅ Unknown execution preserves identity and reconciles.
- ❌ Compensation rewrites history.
  ✅ It is a new causally linked operation.
- ❌ Idempotency excludes stale workers.
  ✅ Fencing excludes stale authority.
- ❌ Passing Fake tests proves production.
  ✅ It proves only the deterministic local boundary exercised.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost/limit |
|---|---|---|
| immutable binding | deterministic audit | policy change needs new Attempt |
| fail closed | protects semantics/security | reduced availability |
| conservative unknown | prevents duplicate effects | delayed recovery |
| separate compensation | preserves truth | extra lifecycle work |
| downstream fencing | rejects stale workers | downstream support required |
| outbox + ledger | eventual cost consistency | reconciliation operations |

## 10. Hands-on Exercises

### Exercise A — Happy path

**Question:** Compose Prompt v3, Profile P2, routing r7, Tool Admission,
verified outcome and guarded completion.

**Think First:** Which facts exist before dispatch?

**Starter Artifact:** `projects/ai-agent/src/application_runtime.py`

**Expected Output:** Structured `COMPLETED` with minimized evidence.

**Explanation:** One store owns state; existing modules keep their decisions.

**Follow-up Question:** Where must a new default be rejected?

### Exercise B — Failure path

**Question:** Run unknown dispatch, revoked Tool, outcome identity mismatch,
unknown compensation and replayed settlement.

**Expected Output:** no blind retry, zero revoked effects, reconciliation under
original identities and one settlement release.

## 11. Relevant Framework Connections

- PostgreSQL should provide guarded transitions and `RETURNING`; not run today.
- Queue workers need durable leases/fencing; no queue/Worker ran.
- Provider SDKs remain behind Adapters; no SDK/HTTP ran.
- External billing needs outbox/saga and idempotency; only an in-process ledger
  ran.
- `threading.RLock` proves deterministic local races, not multi-process safety.

## 12. AI Backend Connections

RAG services, evaluation pipelines and tool-using assistants need this stable
single-execution primitive. Day79 may call it repeatedly and decide whether to
continue, stop or wait, but cannot weaken Prompt, Provider, Tool, recovery,
completion or cost rules.

## 13. English Interview

**Beginner answer:**

> Responsible for the execution order of each component.

Strong answer: “The Runtime coordinates order, enforces lifecycle gates, and
persists authoritative Job/Attempt state.”

**Intermediate answer:**

> Because an audit history is required for review purposes.

Strong answer: “Immutable bindings make execution deterministic, auditable and
semantically stable; new defaults cannot reinterpret old Attempts.”

**Senior answers:**

> Since it is unknown at this point whether an external invocation cost has already been incurred, this is done to avoid a redundant call.

> The results also need to be verified.

> A fence token is also required; an idempotency key only prevents duplicate calls.

These correctly connect unknown execution to duplication risk, execution to
outcome verification, and idempotency to duplicates rather than stale authority.

## 14. Mental Model Summary

The student explicitly asked the teaching assistant to summarize. This is
assistant-authored, not a verbatim student answer:

```text
Bind before dispatch.
Validate every untrusted boundary.
Keep one lifecycle authority.
Preserve identity under uncertainty.
Repair internal truth; compensate external effects separately.
Use idempotency for duplicates and fencing for stale workers.
Settle known cost; reconcile unknown cost.
Claim only the evidence level actually executed.
```

## 15. Today's Takeaway

The capstone is an identity-preserving execution protocol, not “call a model and
parse JSON.” Twenty-two Day78 tests and all 243 cumulative Day72–Day78 tests
passed under Python 3.11.5. This is deterministic `EXECUTED_LOCAL_RUNTIME`, not
real integration or production evidence.

## 16. Before Next Lesson Checklist

- [x] Explain Runtime orchestration versus Provider execution.
- [x] Explain immutable Job/Attempt/Contract binding.
- [x] Order pre-dispatch and post-outcome gates.
- [x] Explain `TIMEOUT_UNKNOWN` and reconciliation.
- [x] Distinguish rollback, repair and compensation.
- [x] Explain idempotency versus fencing.
- [x] Explain known versus unknown cost.
- [x] State the evidence boundary honestly.
- [x] Explain Day78 versus Day79/Day80.
- [x] Answer the three English levels.
