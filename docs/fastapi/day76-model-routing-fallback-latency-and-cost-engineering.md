# Day76 — Model Routing, Fallback, Latency and Cost Engineering

## 1. Lesson Metadata

- **Status:** ✅ Completed (classroom scope)
- **Template:** `LESSON_TEMPLATE_v2.md`
- **Version:** v1.0
- **Phase:** 7A — LLM Application Engineering
- **Difficulty:** Intermediate
- **Estimated Time:** 5–6 hours
- **Prerequisites:** Day72 Provider Capability Profile/Adapter; Day73 Prompt Contract and immutable Attempt
  binding; Day74 Output/Tool Contract, Admission and guarded completion; Day75 streaming/cache/batch boundaries
- **Previous:** [Day75 — Streaming, Caching and Batching](day75-streaming-caching-and-batching-for-llm-applications.md)
- **Next:** Day77 — Fake Provider, Contract Tests and LLM Regression Tests
- **Engineering Artifact:** [`projects/ai-agent/`](../../projects/ai-agent/README.md)
- **Evidence:** CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; INTEGRATION_RUNTIME/PRODUCTION NOT RUN

## 2. Learning Objectives

By the end, you can:

1. explain why eligibility precedes routing preference;
2. distinguish Capability Profile, Routing Policy, Model Router and immutable RoutingDecision;
3. constrain a client model/provider selector with server authority;
4. distinguish retry, fallback, reject, disable, repair, compensation and reconciliation;
5. explain why `TIMEOUT_UNKNOWN` blocks blind retry/fallback;
6. name latency measurement objects and boundaries, and interpret p50/p95/p99 honestly;
7. distinguish cost estimate, reservation, reported usage, actual settlement and unknown cost;
8. preserve per-Attempt identity, latency and cost through fallback and late results;
9. contain and recover from a bad routing-policy release;
10. answer routing/recovery trade-off questions in spoken English.

## 3. Why This Matters

A production LLM application may have several Provider/model Profiles. Choosing the cheapest model before
checking its contracts can produce invalid output or unauthorized tools. Treating every failure as retryable
can duplicate an external effect. Treating a timeout as zero cost hides real spend. Treating p95 as a promise
misses the tail that violates customer deadlines.

The engineering goal is not “pick a model.” It is to select and recover an execution path without weakening
the business contract, losing historical evidence, exceeding the Job deadline/budget, or confusing a
Provider response with durable business completion.

## 4. Roadmap Position

```text
Day72 capability + replaceable Adapter
  -> Day73 Prompt Contract + immutable input binding
  -> Day74 Output/Tool validation + guarded completion
  -> Day75 streaming/cache/batch without merged authority
  -> Day76 route/fallback/latency/cost around the same safety chain
  -> Day77 Fake Provider + Contract/Regression Tests
  -> Day78 LLM Application Runtime Capstone
```

Day76 consumes Day75 latency/throughput observations but does not turn cache or metrics into authority. Day77
will pin these decisions deterministically. Day78 will integrate the whole Phase 7A runtime.

## 5. Lesson Map

```text
required contracts and current policy
  -> candidate set
  -> eligibility/compatibility gates
  -> policy preference
  -> immutable RoutingDecision + Attempt binding
  -> classified execution outcome
  -> retry / fallback / reject / disable / reconcile
  -> latency evidence
  -> cost reservation and settlement
  -> guarded completion or reconciliation
```

One scenario evolves throughout: a multi-tenant travel application routes a structured, tool-capable Job
across fictional Profiles A, B, C and D. All values are classroom fixtures, not Provider claims.

## 6. Core Mental Model

```text
Eligibility first; preference second.
New external call = new Attempt.
Unknown execution = reconciliation, not guessing.
Latency needs a boundary.
Cost needs an evidence state.
```

Full chain:

```text
trusted request and current policy
-> candidate eligibility and contract compatibility
-> route selection
-> immutable per-Attempt execution binding
-> Provider dispatch
-> complete candidate
-> Parse / Schema / Semantics
-> current Registry / Authorization / Admission
-> idempotent Tool Execution
-> Outcome Verification
-> guarded completion or reconciliation
-> cost/usage settlement
```

## 7. Main Concepts

### Concept 1: Eligibility before routing preference

#### Tech Lead Question

What must be true before latency or cost may rank a candidate?

#### Student Thinking

The student looked for the non-negotiable boundary rather than starting with a score.

#### Student Answer

> `满足本次 Prompt、Output、Tool 和 Provider Capability Contract`

The student also correctly constrained a client request:

> `只能作为受服务器 Routing Policy 约束的 selector`

#### Tech Lead Review

A candidate model/Profile is one possible execution path. Eligibility proves it may execute this exact Job:
current lifecycle, application authorization and the Prompt, Output, Tool and Capability Contracts all pass.
Routing Policy then expresses server-owned preference among that eligible set. It does not modify Contracts.

Static routing uses a configured order. Policy-driven routing may consider current tenant, task, deadline,
budget, health, latency and reliability evidence. “Dynamic” does not mean unconstrained or model-controlled.

#### Engineering Thinking

Hard gates and preferences answer different questions:

```text
eligibility = may this path run?
preference  = which eligible path should run?
```

Mixing them lets a cheap score compensate for incompatibility. Required facts that are missing, mismatched or
stale fail closed. Capability/pricing/health facts are current and versioned, never permanent claims.

#### Production Example

Profile A is cheap but does not satisfy `research.v1`; Profile C satisfies it. A must be excluded even when a
client selects A. The Router chooses C or rejects if no eligible path remains.

#### Framework Connection

FastAPI request fields may expose an optional selector, but trusted server policy and registries decide the
actual route. The request body is not routing authority.

#### Exercise

Given one incompatible cheap Profile and one compatible slower Profile, first list hard eligibility failures;
only then compare the eligible candidates.

### Concept 2: Immutable route binding and classified fallback

#### Tech Lead Question

If A1 fails and another Provider is selected, may the runtime rewrite A1?

#### Student Thinking

The student initially recognized fallback but treated the path change as part of the old Attempt.

#### Student Answer

> `fallback，继续使用A1`

#### Tech Lead Review

Fallback is correct, but reusing A1 is not. One Attempt is one immutable execution fact. A different
Provider/model/Profile creates A2. A1 keeps its RoutingDecision, binding, dispatch certainty, result, latency
and cost evidence.

```text
retry    = new Attempt, same execution path
fallback = new Attempt, different compatible execution path
```

Both remain subject to current capability, Prompt, Output, Tool, Authorization and Admission checks.
Fallback cannot route around invalid input, incompatibility, lack of authorization or business rejection.

#### Engineering Thinking

Recovery starts with classification:

| Evidence | Action |
|---|---|
| Definitely not accepted and policy permits | retry or compatible fallback as a new Attempt |
| `TIMEOUT_UNKNOWN` | reconciliation; no blind new call |
| Unauthorized/incompatible | reject |
| Authentication/configuration fault | disable path and repair configuration |
| Confirmed internal wrong state | repair |
| Confirmed reversible external consequence | authorized/idempotent compensation |

A circuit breaker is temporary containment of a failing path. It is not proof about an earlier call and does
not settle that Attempt's cost.

#### Production Example

A1 on Profile C returns a rate limit with definitive non-acceptance. Current policy may create A2 on eligible
Profile D if attempt, deadline and budget limits remain. If A1 timed out after possible dispatch, it stays
`PENDING_RECONCILIATION`; no A2 is created merely because the client is waiting.

#### Framework Connection

A queue worker persists Job/Attempt state before dispatch and uses a durable conditional transition. Celery
redelivery or HTTP retry headers do not by themselves prove safe retry of an external model/tool call.

#### Exercise

Classify each case as retry, fallback, reject, disable or reconcile: pre-dispatch socket failure; unauthorized
tool; `TIMEOUT_UNKNOWN`; invalid credentials; definitely-not-accepted rate limit with an eligible target.

### Concept 3: Latency engineering

#### Tech Lead Question

What does “the model latency is eight seconds” actually measure?

#### Student Thinking

The student selected durable completion as the business-relevant boundary, then noticed that p95 cannot
guarantee the remaining 5%.

#### Student Answer

> `应该选择Profile C，使用Durable completion latency`

> `不对，剩余的百分之五要超过7s所以不能判断是否满足`

The student then asked why latency matters in engineering and how batching can improve throughput when items
remain separate.

#### Tech Lead Review

Latency needs an object, start/end boundary and identity:

- queueing latency;
- routing/admission latency;
- Provider time to first token (TTFT);
- Provider time to complete result;
- tool execution latency;
- guarded-completion latency;
- Job end-to-end latency.

p50 is the median; p95/p99 describe increasingly far tails. p95 means 95% of the observed population was at
or below the value—not that this request will be. A timeout is an observation/policy boundary; the deadline is
the remaining Job budget. Timeout does not prove non-execution.

Streaming can reduce perceived latency while durable completion stays unchanged. Cache may reduce work but
still needs current checks. Real batching may share network/protocol/compute overhead and improve items/time,
but it may add queue waiting. A Python list alone proves no throughput gain; each item keeps identity.

#### Engineering Thinking

Optimize only the measured boundary. Never skip validation, authorization, Admission or guarded completion
to improve a latency chart.

#### Production Example

Profile A has a Provider-complete p95 above the policy limit, while C remains within it. C is preferable only
if both measurements use the required boundary, identities and fresh observation windows and C remains fully
contract-compatible.

#### Framework Connection

Observability should correlate tenant-safe Job/Attempt ids across FastAPI ingress, queue, Router, Adapter,
tool execution and Durable Store. Histograms and traces are operational evidence, not durable completion.

#### Exercise

For “the browser saw the first token in 900 ms but the Job completed in 12 s,” name the TTFT boundary and the
end-to-end/durable-completion boundary. Explain why both can be correct.

### Concept 4: Cost engineering and guarded settlement

#### Tech Lead Question

If an Attempt reserved five units but settled at three, what happens—and what if execution is unknown?

#### Student Thinking

The student separated reservation from actual usage and correctly retained unknown cost.

#### Student Answer

> `3单位成本，多预留的部分应该回到总预算中`

> `pending_reconciliation,保留reservation不释放，actual usage = UNKNOWN`

#### Tech Lead Review

```text
estimate    = pre-dispatch projection
reservation = budget held before dispatch
reported    = Provider usage evidence
actual      = accepted, persisted settlement
unknown     = unresolved usage/cost requiring reconciliation
```

These are different facts. Every Attempt binds its pricing revision. Retry and fallback can make one Job pay
for several Attempts. Tenant and Job budgets consider spent cost plus active reservations, not just the last
successful call.

`TIMEOUT_UNKNOWN` cannot be recorded as zero. A cache hit cannot erase another dispatched Attempt's cost. A
batch total cannot be divided equally and recorded as per-item actual unless that allocation is supported by
authoritative evidence.

#### Engineering Thinking

Cost control cannot bypass authorization or business priority. Unknown facts remain explicitly unknown.
Pricing/version mismatches fail closed or reconcile; they are not silently recalculated under today's price.

#### Production Example

A1 reserves five fictional units and later settles at three, releasing two. A fallback A2 costs four more, so
the Job cost is seven—not merely A2's four. If A1 remains unknown, its reservation stays held while A2 is
considered against remaining Job/tenant budget.

#### Framework Connection

A production FastAPI/worker system would persist reservation and settlement with an atomic Durable Store
transition. Provider usage webhooks or billing exports are external evidence consumed by reconciliation, not
automatic truth without identity/version checks.

#### Exercise

A three-item Provider batch reports only nine total units. Record the total, keep each item actual unknown and
send allocation to reconciliation. Explain why `3,3,3` is not an actual fact.

## 8. Common Misconceptions

**Routing means cheapest model wins**

❌ Price may compensate for missing capability.

✅ Compatibility and current authorization are hard gates; preferences apply afterward.

**Client model choice is authoritative**

❌ A request may force any registered Provider.

✅ It is only a selector constrained by server allowlists and policy.

**Fallback reuses the failed Attempt**

❌ Change A1's Provider/model fields.

✅ Preserve A1; create A2 with a new binding.

**Any failure permits fallback**

❌ Switch Providers after unauthorized, incompatible or unknown execution.

✅ Classify first; some failures reject, disable or reconcile.

**p95 is a deadline guarantee**

❌ Every request finishes below p95.

✅ Five percent of observations may exceed it; a request still needs a deadline policy.

**Streaming means the Job completed faster**

❌ First token equals durable completion.

✅ Streaming improves perceived delivery; guarded completion is a later boundary.

**Unknown cost is zero**

❌ No response means no charge.

✅ Possible dispatch means usage/cost remains unknown and reserved pending reconciliation.

## 9. Engineering Trade-offs

| Choice | Improves | Sacrifices / risk | Review question |
|---|---|---|---|
| Static priority | predictability, auditability | slower reaction to current conditions | Are eligibility facts still fresh? |
| Policy-driven routing | tenant/deadline/budget adaptation | policy complexity and stale-signal risk | Are hard gates separated from scores? |
| Fail closed on stale facts | contract/cost safety | lower availability | Is there a bounded refresh/defer path? |
| Automatic fallback | availability for classified failures | amplified latency/cost/calls | Is original non-execution proved? |
| Streaming | perceived latency | more assembly/state complexity | Is completion still guarded? |
| Batching | potential throughput | queue delay and allocation ambiguity | Is improvement measured at a real batch boundary? |
| Conservative reservation | budget safety | temporarily unavailable budget | How are unknowns reconciled? |

“Faster,” “cheaper,” and “Provider success” do not automatically mean a better business result.

## 10. Hands-on Exercises

### Exercise 1: Eligibility-first route

**Question:** Profile A is cheaper but incompatible; Profile C is compatible and within the named p95 budget.
Which may the Router select?

**Think First:** Separate hard gates from preference.

**Starter Artifact:** `src/routing_policy.py`

**Expected Output:** A is excluded with evidence; C may receive the new Attempt binding.

**Explanation:** Cost is never allowed to weaken the Contract.

**Follow-up Question:** What happens if C's pricing evidence is stale? Answer: no eligible candidate; fail
closed, reject/defer/refresh according to policy, and make no Provider call.

### Exercise 2: Recovery classification

**Question:** A1 is `TIMEOUT_UNKNOWN`, while D is cheap and healthy. Create A2?

**Think First:** Is A1 proved not to have executed?

**Starter Artifact:** `src/recovery_cost.py`

**Expected Output:** `RECONCILE`, no new binding, reservation retained.

**Explanation:** D's eligibility cannot remove duplicate-effect and unknown-cost risk from A1.

**Follow-up Question:** How does the answer change with `DEFINITELY_NOT_ACCEPTED`? A classified, compatible
fallback may create A2 if deadline, attempt and budget limits remain.

### Exercise 3: Bad-policy production incident

**Question:** Policy v5 admitted incompatible B, used stale signals, amplified fallback calls and left mixed
effects/costs. Contain and recover it.

**Think First:** Rollback stops new harm; it does not classify history.

**Starter Artifact:** `IncidentRecoveryEvidence`

**Expected Output:**

```text
rollback new planning to v4; stop v5; pause auto-fallback; quarantine B
-> scope Jobs/Attempts by revision and time
-> classify dispatch/outcome/effect/cost per Attempt
-> reconcile unknowns
-> repair internal state; compensate verified external consequences
-> fence late results; settle or retain unknown costs
-> controlled rollout + regression + cross-system verification
```

**Explanation:** Do not bulk retry, delete failed records or write unknown cost as zero.

**Follow-up Question:** Why are rollback and passing tests insufficient? They do not resolve historical
unknown calls, side effects or cost facts.

## 11. Relevant Framework Connections

### FastAPI

Expose constrained selectors, trusted tenant identity and Job status. Do not let request fields become Provider
authority. Return accepted Job/Attempt identities rather than claiming synchronous business completion.

### PostgreSQL / Durable Store

Persist RoutingDecision, Attempt binding, lifecycle transitions, cost reservation/settlement and reconciliation
state atomically. The in-memory dataclasses and locks in this project model shapes, not database durability.

### Queue workers

Enforce deadline/backpressure before dispatch and preserve one Attempt per external call. Redelivery is not
automatically a safe retry. Batch scheduling retains per-item identity and fairness.

### Observability

Use stage-specific latency histograms and correlation identity. Health and latency metrics are current
operational evidence; they are not authorization, business completion or historical Attempt truth.

## 12. AI Backend Connections

- **Model registry:** stores versioned Provider/model/Capability Profiles and lifecycle overlays.
- **LLM Runtime:** composes current contracts, routing, dispatch, validation and guarded completion.
- **Tool calling:** every fallback candidate reruns current Tool Registry/Authorization/Admission.
- **Streaming/cache/batch:** remain Day75 optimizations; none chooses authority or settles another Attempt.
- **Budget control:** reserves before dispatch and settles per Attempt without hiding retry/fallback amplification.
- **Reconciliation:** resolves late outcomes and unknown usage through authoritative Provider/external evidence.
- **Evaluation:** quality may be another eligibility/policy input only when its definition, version and freshness
  are explicit; lower latency/cost is not automatically higher quality.

## 13. English Interview

### Key Vocabulary

`candidate set`, `eligibility`, `routing policy`, `immutable Attempt binding`, `retry`, `fallback`, `deadline`,
`tail latency`, `reservation`, `settlement`, `unknown outcome`, `reconciliation`, `compensation`.

### Beginner

**Question:** What is model routing?

Authentic answer:

> Model routing is a dynamic allocation mechanism that first identifies and excludes models based on criteria
> such as insufficient context, lack of required functionality, non-compliance, or inadequate capability
> levels.

Refinement: routing can be static or dynamic. Prefer “policy-controlled selection process” and “contract
incompatibility.”

Strong answer:

> Model routing first removes candidates that cannot satisfy the current contracts. It then applies a
> server-owned policy to the eligible candidates and stores the selected path in an immutable Attempt binding.

### Intermediate

**Question:** How do retry and fallback differ after an unknown timeout?

Authentic answer:

> A retry involves making a new attempt using the same configuration, whereas a fallback involves making a
> new attempt using a different configuration; the system should enter the `pending_reconciliation` state.

Strong answer:

> Retry uses the same execution path and fallback uses a different compatible path, but both create a new
> Attempt and preserve the old one. If the old call is `TIMEOUT_UNKNOWN`, we do neither blindly; we retain its
> identity and cost reservation and reconcile the external outcome.

### Senior

**Question:** How do you recover from a bad routing policy with stale signals, unknown calls and incomplete
cost evidence?

Strong answer:

> I roll new planning back to the stable policy, stop the bad revision, pause automatic fallback and
> quarantine incompatible profiles. I scope and classify each affected Attempt by dispatch certainty,
> durable outcome, side effects and cost. Unknown calls keep their reservations and reconcile; late results
> cannot overwrite current state. I separate durable repair from external compensation and close the incident
> only after costs, unknowns, guards and controlled-rollout evidence are verified.

Common weak answer: “Switch every failed request to the cheapest healthy model and retry the batch.” It
ignores compatibility, unknown execution, per-Attempt identity, duplicate side effects and cost amplification.

## 14. Mental Model Summary

```text
Candidate Set      = possible execution paths
Eligibility        = hard permission/compatibility gate
Routing Policy     = versioned preference for new Attempts
RoutingDecision    = immutable selection evidence
Retry              = new Attempt on the same path
Fallback           = new Attempt on a different compatible path
TIMEOUT_UNKNOWN    = preserve + reconcile
TTFT               = perceived first-output latency
Durable Completion = verified business-completion latency
p95                = distribution evidence, not a guarantee
Estimate           = projection
Reservation        = held budget
Actual             = settled fact
Unknown Cost       = retained reservation + reconciliation
Rollback           = stop future harm, preserve history
```

## 15. Today's Takeaway

- **Mental model:** eligibility first, preference second, immutable Attempt always.
- **Production risk:** blind fallback after unknown execution can duplicate side effects and hide cost.
- **Trade-off:** dynamic routing can improve fit but increases dependence on fresh, versioned evidence.
- **Framework connection:** Durable Store, not Router metrics, owns Attempt/completion/cost truth.
- **AI Backend connection:** every routed/fallback candidate still follows Day72–Day75 contracts and guards.
- **Interview answer:** retry and fallback differ by execution path; neither may erase an unknown source Attempt.

The final Chinese synthesis in the classroom record was supplied by the teaching assistant at the student's
explicit request (`你帮我总结吧`), not independently authored by the student.

## 16. Before Next Lesson Checklist

- [ ] Can I explain eligibility before routing preference?
- [ ] Can I explain why a client selector is not authority?
- [ ] Can I identify the facts stored in a RoutingDecision and Attempt binding?
- [ ] Can I distinguish retry, fallback, reject, disable, repair, compensation and reconciliation?
- [ ] Can I explain why `TIMEOUT_UNKNOWN` blocks blind recovery?
- [ ] Can I name TTFT, Provider-complete, guarded-completion and end-to-end latency boundaries?
- [ ] Can I explain why p95 is not a guarantee?
- [ ] Can I distinguish estimate, reservation, reported usage, actual and unknown cost?
- [ ] Can I explain fallback/retry cost amplification and batch per-item allocation?
- [ ] Can I contain bad routing policy without rewriting historical Attempts?
- [ ] Can I describe what Day77 must prove with Fake Provider and regression tests?
- [ ] Can I answer the Beginner, Intermediate and Senior questions aloud?

Related material: [Day76 design](../../projects/ai-agent/docs/DAY76_MODEL_ROUTING_FALLBACK_LATENCY_COST.md) ·
[classroom record](../../projects/ai-agent/docs/day76-model-routing-fallback-latency-cost-classroom-draft.md) ·
[FastAPI cheat sheet](../../cheat_sheets/fastapi.md) · [FastAPI interview handbook](../../interview/fastapi.md)
