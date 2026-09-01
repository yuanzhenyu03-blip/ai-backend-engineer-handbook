# Day80 — Tool Registry, Tool Schema and Permission Model

## 1. Lesson Metadata

- Status: Completed (classroom scope)
- Phase: 7B — Agent Runtime and MCP Engineering
- Date: 2026-09-01
- Version: 1.0
- Difficulty: Intermediate to Senior
- Estimated time: 4–5 hours
- Prerequisites: Day66, Day74, Day78 and Day79
- Previous: Day79 — Framework-agnostic Agent Loop and Control Flow
- Next: Day81 — Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets
- Artifact: `projects/ai-agent/`
- Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`

## 2. Learning Objectives

You can now:

1. distinguish registered, visible, authorized, admitted, executed and verified Tools;
2. build a context-scoped Tool Capability Snapshot before a model call;
3. narrow a base Schema without treating Schema as Authorization;
4. bind a candidate to tenant, user, role, Job, Step, Tool version and Schema hash;
5. recheck current trusted Permission and Registry facts before Admission;
6. compose tenant/user/Job/Step policy layers conservatively;
7. reuse Day74 generic Tool and Day66 browser-specific boundaries;
8. keep Framework translation outside business authority;
9. distinguish durable acceptance from a verified Safe Tool Result;
10. defend rollback and reconciliation behavior in an interview.

## 3. Why This Matters

An Agent becomes dangerous when “the framework knows this function” is treated as “the current user may run
it.” A Tool may be globally registered but forbidden for one tenant, disabled during a rollout, or revoked
between the model request and the actual invocation. Its Schema may be valid while its Origin, session or
approval is forbidden.

Day79 gave the application control of the next Step. Day80 gives it a governed Tool surface. Pre-model
filtering reduces token cost and attack surface, but it cannot replace invocation-time Authorization.

## 4. Roadmap Position

```text
Day74 Tool Contract
  -> Day78 bounded Runtime execution
  -> Day79 application-owned Controller
  -> Day80 Agent Tool Registry / Schema / Permission governance
  -> Day81 state machine / termination / loop detection / budgets
  -> Day82 durable checkpoint / resume / recovery
```

Day74 already owns Parse, strict Schema, exact Registry resolution, trusted Authorization, semantics,
Admission, idempotent execution, Outcome Verification and guarded completion. Day80 adds Agent-facing
visibility and current-permission governance without rebuilding those stages. Day81 and Day82 remain future
scope.

## 5. Lesson Map

```text
Registry + trusted current context
-> permission composition + Schema projection
-> immutable Tool Capability Snapshot
-> Framework translation
-> untrusted model candidate
-> exact Snapshot/context/version/Schema binding
-> current Registry + Permission recheck
-> Day74 generic Admission
-> Day66 Tool-specific Admission
-> Day78 bounded execution + Outcome Verification
-> Safe Tool Result -> Day79 Controller
```

## 6. Core Mental Model

```text
Registered
  != Visible
  != Authorized now
  != Admitted
  != Executed
  != Outcome Verified
  != Agent Goal Completed
```

- Registry: application-owned exact Tool identity, Schema and lifecycle directory.
- Schema: candidate structure; never permission.
- Permission Model: current authority for tenant/user/Job/Step.
- Capability Snapshot: immutable Tools the model may suggest for one context.
- Framework Adapter: translation only; it cannot expand authority.
- Safe Tool Result: minimal verified result permitted as an Agent observation.

## 7. Main Concepts

### Concept 1 — Registry presence is not visibility

#### Tech Lead Question

A Tool is globally registered and Schema-valid but not permitted for the current context. Show it to the model?

#### Student Thinking

The student immediately separated the global catalog from the current model surface.

#### Student Answer

> 应该在发送给模型之前就被过滤掉

#### Tech Lead Review

Correct. Day80 resolves each exact `name@version` through Day74 `ToolRegistry`. Ungranted, unknown or disabled
Tools are omitted. Duplicate Agent catalog identities are rejected rather than merged silently.

#### Engineering Thinking

Filtering improves least-capability exposure and model accuracy, but facts may change during model latency, so
the invocation must still be rechecked.

#### Production Example

`browser.export_report@v1` is registered platform-wide but visible only to an authorized publisher for the
current tenant, Job and Step.

#### Framework Connection

An OpenAI SDK, LangChain, LangGraph or MCP adapter may serialize only the application Snapshot.

#### Exercise

Predict visibility and audit reasons for active/granted, active/ungranted and disabled/granted Tools.

### Concept 2 — Schema projection is not Authorization

#### Tech Lead Question

If `target_origin` is narrowed to one enum value, is the Origin authorized?

#### Student Thinking

The student retained both Agent Permission and the existing browser-specific security boundary.

#### Student Answer

> 需要 Permission Model 和 Day66 server-authorized contract 再检查一次 Origin

#### Tech Lead Review

Correct. Projection deep-copies the Day74 base Schema and may only narrow an existing string property. It
cannot add a property, widen a base enum or mutate the base Schema. Base and projected hashes are retained.

#### Engineering Thinking

Projection guides the model and reduces invalid candidates, but adds version/hash management and never grants
authority.

#### Production Example

The model sees one Origin; Day66 still checks exact tenant, Origin, report scope, session, approval and
fingerprint.

#### Framework Connection

The Framework receives projected Schema JSON but cannot widen it.

#### Exercise

Attempt to project `admin_override` and explain why the application rejects the configuration.

### Concept 3 — Invocation needs current authority

#### Tech Lead Question

Permission is revoked after Snapshot S1 but before Admission. Can S1 authorize the candidate?

#### Student Thinking

The student recognized the time-of-check/time-of-use boundary and required current trusted facts.

#### Student Answer

> 必须使用调用时的最新可信权限事实重新检查

#### Tech Lead Review

Correct. Bind Snapshot, tenant, user, role, Job, Step, exact Tool version and projected Schema hash. Current
revocation, disable, catalog removal, role change or Schema drift blocks progress. Active v2 cannot replace a
disabled v1; the student correctly said:

> 必须拒绝当前候选

#### Engineering Thinking

Immutable binding improves audit causality but forbids convenient in-place upgrades. A new Step may select v2;
the old candidate cannot be rewritten.

#### Production Example

A tenant admin revokes export permission while the Provider is generating. The candidate is retained for
minimized audit and creates zero Tool calls.

#### Framework Connection

A Framework retaining an old function object does not retain application permission.

#### Exercise

Grant v1 and v2, disable bound v1, and prove the failure is lifecycle—not permission or version substitution.

### Concept 4 — Permission unknown is phase-sensitive

#### Tech Lead Question

What happens when one policy layer denies, or a required layer is unavailable before execution?

#### Student Thinking

The student correctly rejected a deny but initially used a post-dispatch recovery state before dispatch.

#### Student Answer

> 应该拒绝，应该进入pending_reconciliation

#### Tech Lead Review

`DENY` was correct. Pre-execution `UNKNOWN` was corrected:

```text
any authoritative DENY -> DENIED -> zero calls
all required ALLOW     -> continue governance
pre-execution UNKNOWN  -> POLICY_UNAVAILABLE -> WAIT/fail closed
```

`PENDING_RECONCILIATION` requires possible external execution. With no Admission or dispatch, the student then
correctly chose:

> `WAIT`,等待tenant 授权正确

The exact condition is a current verifiable policy result, not necessarily new human approval.

#### Engineering Thinking

Deny-overrides protects narrow safety rules but can reduce availability during a policy outage.

#### Production Example

Tenant/user/Job allow export but Step denies it: reject. User-policy timeout before Admission: create no task.

#### Framework Connection

Framework retry middleware cannot retry the Tool independently while application Policy is unavailable.

#### Exercise

Write the ALLOW/DENY/UNKNOWN decision table and Tool-call count.

### Concept 5 — Day80 delegates Admission and execution

#### Tech Lead Question

Should Day80 reimplement the Day66 permissioned browser checks?

#### Student Thinking

The student recognized that new governance must compose the already released public contracts.

#### Student Answer

> 交给已有的 Day66 permissioned browser tool 边界

#### Tech Lead Review

Correct. Day80 rechecks governance and reuses Day74 Schema validation, then returns only
`READY_FOR_BACKEND_ADMISSION`. Day74 owns generic Admission/execution/outcome boundaries. Day66 owns browser
operation, tenant, Origin, scope, session, approval, fingerprint, Task/Contract/Outbox, claim/lease/fence and
recovery.

#### Engineering Thinking

Composition keeps one owner per invariant and avoids two security implementations drifting apart. Its cost is
more explicit structured boundaries.

#### Production Example

Day80 prepares an export candidate; Day66 rejects it because server approval is revoked. Browser calls: zero.

#### Framework Connection

The Framework may transport the candidate but cannot flatten all decisions into one “valid Tool” boolean.

#### Exercise

Trace a candidate that passes projected Schema but fails Day66 approval.

### Concept 6 — Accepted is not completed; Framework is not authority

#### Tech Lead Question

Can `202 Accepted + task_id` become a successful Agent observation? Can Framework discovery add another Tool?

#### Student Thinking

The student rejected both the lifecycle shortcut and the authority expansion.

#### Student Answer

> 不能

#### Tech Lead Review

Correct. `ACCEPTED` yields `WAIT_FOR_TERMINAL_RESULT`. An unverified terminal payload is blocked. Only a
backend-verified minimal `SafeToolResult` may become an Agent observation. A Framework receives exactly the
application Snapshot; decoration, plugin discovery or reflection grants nothing.

#### Engineering Thinking

Result minimization reduces leakage of raw pages, credentials and internal errors. Restricting Framework
discovery reduces convenience but preserves application authority.

#### Production Example

Day66 atomically accepts a task. The Controller waits until guarded terminal completion and Outcome
Verification, then sees only safe operation identity and result code.

#### Framework Connection

`FrameworkToolSpec` is derived exclusively from visible Snapshot entries.

#### Exercise

Classify ACCEPTED, unverified terminal and verified terminal signals as Agent-visible or blocked.

## 8. Common Misconceptions

- ❌ Registry means authorized. ✅ Registry establishes known identity and contract only.
- ❌ Valid/narrowed Schema proves permission. ✅ Schema constrains data; current policy authorizes.
- ❌ Old Snapshot remains authority. ✅ It remains audit evidence; invocation uses current facts.
- ❌ Active v2 may replace disabled v1. ✅ Exact bound version is rejected.
- ❌ Any unknown means reconciliation. ✅ Pre-execution unknown waits/fails closed; possible external execution
  unknown reconciles.
- ❌ Controller grants permission. ✅ Policy authorities supply facts; Controller owns control flow.
- ❌ `202 Accepted` means success. ✅ It means durable acceptance only.
- ❌ Framework discovery is Registry authority. ✅ Frameworks translate application decisions.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost / limitation |
|---|---|---|
| pre-model filtering | smaller attack surface and token cost | still needs current recheck |
| immutable Snapshot/binding | deterministic audit and replay | more identities; no in-place upgrade |
| Schema projection | least-capability guidance | projection/hash complexity |
| deny-overrides | narrow safety rule survives broad allow | policy faults reduce availability |
| exact version rejection | prevents semantic substitution | safe upgrade needs new Step/candidate |
| boundary composition | one owner per invariant | more explicit decisions |
| minimal Safe Tool Result | reduces data leakage | backend-specific projection work |
| Framework translation only | portability and authority | less auto-discovery convenience |

A Tech Lead should reject a design that merges visibility, Authorization, Admission and execution into one
boolean or constructs trusted context from model arguments.

## 10. Hands-on Exercises

### Exercise A — Capability Snapshot

Question: Build a Snapshot containing active/granted, active/ungranted and disabled/granted Tools.

Think First: Which facts come from Registry and which from Permission?

Starter Artifact: `src/tool_governance.py`.

Expected Output: One visible Tool plus deterministic reasons for the other two.

Explanation: Visibility is an intersection, not a global registration lookup.

Follow-up Question: Why is the invocation still rechecked?

### Exercise B — Schema drift

Question: Narrow an Origin, then change the permitted Origin after the model call.

Think First: Is old candidate syntax current authority?

Starter Artifact: `ArgumentEnumConstraint` and `BoundToolInvocation`.

Expected Output: `SCHEMA_BINDING_MISMATCH`, zero backend calls.

Explanation: The candidate remains bound to its original projected contract.

Follow-up Question: Would an active v2 change the old v1 result?

### Exercise C — Day66 composition

Question: Prepare a browser candidate through Day80, then revoke Day66 server approval.

Think First: Which layer owns approval?

Starter Artifact: `prepare_candidate_for_backend_admission()` and `validate_tool_proposal()`.

Expected Output: Day80 ready; Day66 `REJECT_UNAPPROVED`; zero browser calls.

Explanation: Upstream readiness cannot override downstream authority.

Follow-up Question: What evidence level does this pure-function composition establish?

### Exercise D — Production failure and rollback

Question: A bad Policy exposes `browser.delete_report@v1`. Classify one old pre-dispatch candidate and one
request dispatched before timeout.

Think First: Which may already have an external effect?

Starter Artifact: immutable Snapshot/binding and Day78 reconciliation contract.

Expected Output:

- pre-dispatch: preserve audit, reject under current facts, zero calls, no reconciliation;
- dispatched timeout: preserve original identity, `PENDING_RECONCILIATION`, no replacement call.

Explanation: Rollback stops future harm; it does not rewrite history or prove non-execution.

Follow-up Question: What verified evidence is required before compensation?

## 11. Relevant Framework Connections

A Framework can serialize an application-provided Tool definition and deserialize a candidate. It cannot add
auto-discovered Tools, derive tenant/user/Job/Step from model arguments, treat Schema as Authorization, select
another bound version or turn acceptance into completion.

No Agent Framework was installed, selected or executed. Day87 refreshes Framework/job-market knowledge and
Day88 selects a replaceable Framework behind the application contract.

## 12. AI Backend Connections

- multi-tenant Agent Tool surfaces and least-capability model requests;
- permission revocation during Provider latency;
- exact Tool/version/Schema binding;
- server-owned browser approval and scoped session boundaries;
- asynchronous Tool acceptance and safe observation projection;
- rollback without history rewriting;
- unknown external effects, idempotency and reconciliation.

Model content, Tool arguments and Framework metadata remain untrusted. Trusted authority comes from
application-owned current state.

## 13. English Interview

### Key Vocabulary

`tool registry`, `capability snapshot`, `schema projection`, `permission model`, `current-fact recheck`,
`admission`, `exact version binding`, `fail closed`, `safe tool result`, `reconciliation`.

### Useful Expressions

- “Registration establishes identity, not permission.”
- “Schema validation is necessary but not sufficient for authorization.”
- “The framework translates application decisions; it does not own business authority.”
- “We recheck current trusted facts immediately before Admission.”
- “Accepted is not completed, and unknown execution preserves the original identity.”

### Beginner Question

**Question:** What is the difference between registered, visible and authorized?

**Actual student answer:**

> A tool being registered does not mean the model is visible. Model visibility merely indicates that the tool
> is a candidate, not that it is authorized; the model only becomes usable after authorization is granted.

**Correction:** Authorization still does not mean admitted, executed or successful.

### Intermediate Question

**Question:** Permission is revoked after the model saw the Tool. What happens, and who owns the decision?

**Actual student answer:**

> The application should reject the request, and the controller makes the decision.

**Correction:** Reject is correct. The Permission Model is the policy authority; Day80 applies it, and the
Day79 Controller consumes the structured result for control flow.

### Senior Question

**Question:** How would you design `prepare_tool_call` without duplicating Day74 or Day66?

**Actual student answer:**

> Day 80: Control model visibility tools and re-examine candidates using the latest, authoritative permission
> facts. Day 74: Responsible for the general schema, authorization, admission, execution, and result
> verification. Day 66: Responsible for browser-specific aspects—Origin, session, approval, fingerprint, and
> persistence execution boundaries. Day 80 must not duplicate or overlook the checks performed on Day 66.

**Strong answer:** Accept an untrusted candidate plus immutable original Snapshot/binding and trusted current
tenant/user/role/Job/Step, Registry and Policy facts. Return a structured block or readiness to enter existing
Admission. Delegate generic contracts to Day74, browser-specific Admission to Day66, bounded execution/outcome
to Day78 and control flow to Day79.

### Common Weak Answer

“The JSON Schema is valid, so the framework can call the function.”

### Strong Answer

“Schema only validates candidate structure. The application limits model visibility, binds the candidate and
rechecks current permission/lifecycle. Passing Day80 only allows entry to existing Admission; it does not
authorize execution.”

## 14. Mental Model Summary

```text
Registry = exact Tool identity + base Schema + lifecycle
Snapshot = context-scoped visibility + projected Schema + audit identity
Schema = data constraint, never Authorization
Policy = trusted current tenant/user/Job/Step facts
Binding = Snapshot + context + exact version + Schema hash
Framework = translation, never permission
Day74 = generic Tool Contract and guarded lifecycle
Day66 = browser-specific permission/security/durability
Day78 = one bounded execution and Outcome Verification
Day79 = application control decision

pre-execution policy unknown -> zero calls, WAIT/fail closed
possible external execution unknown -> preserve identity, RECONCILE
202 Accepted -> work exists, not completed
verified Safe Tool Result -> may become an Agent observation
```

The student asked the instructor to supply the final Chinese synthesis. The classroom record labels it as
instructor-supplied rather than misattributing it as a student-authored answer.

## 15. Today's Takeaway

Day80 turns a global Tool inventory into a least-capability, context-bound Agent surface without confusing
visibility with authority. Recheck current trusted Permission and Registry facts, then delegate to existing
generic and Tool-specific Admission boundaries.

The key trade-off is that immutable exact bindings and fail-closed policy reduce availability and upgrade
convenience in exchange for causality, tenant isolation and external-side-effect safety.

Evidence: Python 3.11.5-compatible `python3.11`; 22 Day80 tests and 273 cumulative deterministic tests passed.
Two composition tests call the actual local Day66 pure validation boundary, but no real browser or external
integration ran.

## 16. Before Next Lesson Checklist

- [ ] Can I explain every `!=` in Registered → Goal Completed?
- [ ] Can I distinguish base Schema, projected Schema and Authorization?
- [ ] Can I explain why an old Snapshot is audit evidence, not fresh authority?
- [ ] Can I compose tenant/user/Job/Step ALLOW/DENY/UNKNOWN?
- [ ] Can I explain why Framework discovery cannot expand the Tool surface?
- [ ] Can I place Day80 before Day74/Day66 Admission and Day78 execution?
- [ ] Can I distinguish `202 Accepted`, Safe Tool Result and Goal completion?
- [ ] Can I distinguish pre-execution policy outage from post-dispatch unknown outcome?
- [ ] Can I execute and explain the rollback exercise?
- [ ] Am I ready for Day81 state machine, termination, loop detection and budgets?
