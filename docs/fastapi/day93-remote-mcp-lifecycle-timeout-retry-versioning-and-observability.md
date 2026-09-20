# Day 93 — Remote MCP Lifecycle: Timeout, Retry, Versioning and Observability

## 1. Lesson Metadata

- Status: ✅ Completed (guided classroom scope)
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Advanced
- Estimated study time: 8–9 hours
- Prerequisite: Day92 — MCP Authentication, Authorization and Tenant Isolation
- Previous lesson: [Day92](day92-mcp-authentication-authorization-and-tenant-isolation.md)
- Next lesson: Day94 — Agent + MCP Integration Capstone and English Interview
- Engineering artifact: application-owned remote failure evidence, bounded retry/reconciliation policies,
  generation-scoped correlation/version gates, safe observability, controlled Streamable HTTP fixture,
  62 focused tests, 16-case seed and deterministic example
- Evidence: `CONTROLLED_REMOTE_RUNTIME`; production readiness `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After completing this lesson, you should be able to:

1. distinguish an absolute deadline, a phase timeout and the remaining timeout budget;
2. explain why timeout and cancellation do not prove remote non-execution;
3. record dispatch certainty independently from execution certainty;
4. convert SDK/private failures into application-owned `FailureEvidence` before policy sees them;
5. decide retry eligibility from trusted non-execution evidence and current policy;
6. preserve operation/idempotency identity while creating a fresh protocol attempt identity;
7. implement bounded exponential backoff, deterministic jitter and a retry budget;
8. use a durable conditional transition so only one worker may dispatch a retry;
9. reconcile possibly executed operations without replaying the original Tool;
10. reject stale reconnect responses and capability/version downgrades;
11. fail closed when an unknown JWKS key cannot be refreshed;
12. separate global load shedding, authorized tenant capacity and circuit-breaker evidence;
13. design credential-safe logs, bounded metrics and non-authoritative traces;
14. explain controlled-runtime evidence and the remaining production gaps in English.

## 3. Why This Matters

A Client calls `research.lookup`, waits, and receives a read timeout. The tempting implementation catches the
exception and retries. That can execute the same external side effect twice: the first request may have reached
the handler and completed after the Client stopped waiting.

Remote systems split one apparent “request” into several independent timelines: caller deadline, transport
handoff, Server admission, controlled-service execution, response delivery and durable application commit.
Collapsing them into `success/failed` creates duplicate writes, lost results, retry storms, stale-response
commits and false operational confidence.

Day93 makes uncertainty explicit. The application records what it can prove, preserves unknown outcomes, and
lets a separate policy decide what may happen next. This is the lifecycle foundation Day94 needs before an
Agent may safely orchestrate MCP capabilities.

## 4. Roadmap Position

```text
Day89 application DTO / binding / correlation
        ↓
Day90 controlled Client + SDK-private conversion
        ↓
Day91 candidate-only Server handlers
        ↓
Day92 principal + current exact authorization
        ↓
Day93 remote lifecycle evidence + recovery + observability
        ↓
Day94 complete Agent + MCP capstone
```

Day93 reuses Day81–Day83 deadline, identity, conditional-apply and reconciliation thinking; Day89–Day90
protocol correlation; Day91 candidate-only handlers; and Day92 current permits. Day94 must propagate these
same contracts through the complete Agent loop rather than rebuilding authority inside a framework.

## 5. Lesson Map

```text
absolute deadline
→ phase timeout and cancellation
→ dispatch/execution evidence
→ retry policy or reconciliation
→ reconnect/version/capability gates
→ JWKS/capacity/circuit protection
→ safe logs/metrics/traces
→ controlled remote evidence and production gaps
```

## 6. Core Mental Model

```text
timeout = caller stopped waiting
timeout != remote operation did not execute

FailureEvidence = facts about one attempt
RetryPolicy     = current decision over those facts
Reconciliation = read-only search for authoritative result evidence
Committer      = sole durable transition authority
```

The decision split is:

```text
PROVEN_NOT_EXECUTED
        → independent bounded retry policy

POSSIBLY_EXECUTED
        → PENDING_RECONCILIATION
        → authority query
        → Committer proposal or operational alert
```

## 7. Main Concepts

### Concept 1: Deadline, timeout and cancellation describe different control boundaries

#### Tech Lead Question

If an operation has eight seconds total, may a downstream read phase start a new eight-second timer? Does a
cancelled remote task prove that no external side effect occurred?

#### Student Thinking

The learner correctly rejected resetting the total time and said the operation could receive at most eight
seconds. In the final synthesis, timeout was initially described as the budget itself and cancellation as only
a post-send action. The distinction needed one final terminology correction.

#### Student Answer

“调用最多可以获得 8 秒总时间，不能重置时间。” Later: “已经执行的外部副作用无法取消，只能
reconciliation。”

#### Tech Lead Review

An absolute deadline is the final end time. A phase timeout is the maximum wait for one phase. The timeout
budget is the remaining usable portion of the parent deadline. Every child receives the smaller value:

```text
stage_timeout = min(configured_phase_timeout, deadline - now - cleanup_reserve)
```

Cancellation may happen before or after dispatch. Before dispatch it can prove non-execution. After possible
dispatch it only asks future work to stop; even a cancellation acknowledgement is not rollback evidence.

#### Engineering Thinking

One absolute clock prevents timeout amplification. Cancellation is a control signal, not a history rewrite.
External effects may cross the boundary before the cancellation is observed.

#### Production Example

The controlled Streamable HTTP test timed out the Client after the Tool coroutine entered. The Client abandoned
the POST, but the Tool completed. This directly disproves “read timeout means handler did not run.”

#### Framework Connection

Python MCP SDK timeout/cancellation mechanics remain inside the Adapter. `DeadlineBudget` and the resulting
application evidence remain SDK-independent.

#### Exercise

For deadline `108.0`, current time `103.0`, configured read timeout `30.0` and cleanup reserve `0.5`, compute
the stage timeout and explain why it cannot be 30 seconds.

### Concept 2: Dispatch certainty and execution certainty are independent evidence

#### Tech Lead Question

Does a transport error prove the handler or controlled service did not run? What must be recorded before
handing the request to transport?

#### Student Thinking

The learner immediately rejected “exception means no execution” and required a dispatch marker before
transport. The final summary briefly called dispatch certainty an “intent to dispatch”; review corrected it to
evidence about actual transport handoff.

#### Student Answer

“不能，不能证明 handler 或 controlled service 没运行。应该在把请求交给 transport 之前记录。”

#### Tech Lead Review

`dispatch_certainty` records evidence about transport handoff:

- `PROVEN_NOT_SENT`;
- `POSSIBLY_SENT`;
- `PROVEN_SENT`.

`execution_certainty` separately records evidence about business execution:

- `PROVEN_NOT_EXECUTED`;
- `POSSIBLY_EXECUTED`;
- `PROVEN_EXECUTED`.

A verified Server pre-handler rejection can be `PROVEN_SENT + PROVEN_NOT_EXECUTED`. A local circuit rejection
can be `PROVEN_NOT_SENT + PROVEN_NOT_EXECUTED`. A read timeout is normally
`POSSIBLY_SENT + POSSIBLY_EXECUTED`.

#### Engineering Thinking

Dispatch and execution are separate because a request may reach a trusted Server but stop before the handler.
Conversely, a connection can fail after the service executes but before the response returns.

#### Production Example

An authenticated controlled Server returns a locally configured `CAPACITY_REJECTED` before handler entry.
The application may trust its own contract. An arbitrary peer returning the same text cannot self-prove
non-execution.

#### Framework Connection

The Adapter converts SDK exceptions and verified transport facts into application-owned `FailureEvidence`.
Core recovery code never imports HTTP or SDK exception classes.

#### Exercise

Classify a local connect failure, a verified Server circuit rejection and a read timeout using both certainty
dimensions.

### Concept 3: Retry is a bounded policy, not an exception handler

#### Tech Lead Question

May `PENDING_RECONCILIATION` retry automatically? Which identifiers stay stable, and how do two workers avoid
dispatching the same retry?

#### Student Thinking

The learner consistently rejected automatic retry and identified operation ID, idempotency key and a durable
pre-transport marker. They also recognized retry amplification and herd behavior, leading to budget, backoff
and jitter.

#### Student Answer

“不应该，需要根据 policy 判断是否需要进行重试。” “`operation_id`、`idempotency_key` 保持不变，
`protocol_request_id` 和 `attempt_number` 更新。”

#### Tech Lead Review

Retry eligibility requires proven non-execution plus active caller intent, remaining retry/deadline budget,
current authorization, admitted capacity and a closed circuit. Backoff is exponential and capped; deterministic
jitter spreads operations while keeping tests reproducible.

After waiting, volatile gates are checked again. A durable conditional update changes
`READY_FOR_RETRY → DISPATCH_STARTED` before transport handoff. Only the worker receiving the updated row may
dispatch. If that owner crashes after the marker, execution is unknown rather than rewritten as not sent.

#### Engineering Thinking

Stable operation/idempotency identity preserves duplicate protection. Fresh protocol request identity makes
attempt correlation unambiguous. The policy remains unable to call the Committer or transport.

#### Production Example

Two workers wake for the same retry. `UPDATE ... WHERE state='READY_FOR_RETRY' AND version=? RETURNING ...`
returns one row to only one worker; the loser performs zero transport calls.

#### Framework Connection

The implementation uses an in-memory teaching equivalent of conditional `UPDATE ... RETURNING`. Day94 or a
production deployment must replace it with a durable store without changing the contract.

#### Exercise

Explain why changing `operation_id` after a timeout is more dangerous than reusing it, even if the new request
has a fresh protocol request ID.

### Concept 4: Reconciliation observes authority; it never replays the Tool

#### Tech Lead Question

What may reconciliation do after possible execution? What happens when authority says `NOT_FOUND`, remains
unknown, or proves `NOT_EXECUTED`?

#### Student Thinking

The learner repeatedly rejected replay and restricted reconciliation to authoritative status/external-result
evidence. They correctly required “not executed” to converge as a fact before retry policy runs.

#### Student Answer

“只查询权威状态/外部结果证据。” “应先把‘未执行’作为事实收敛，再交给独立 retry policy。”

#### Tech Lead Review

The scheduler receives a read-only authority port and no Tool execution port. `NOT_FOUND` is not proof of
non-execution under eventual consistency. Unknown remains pending; bounded query/deadline exhaustion emits one
operational alert without changing the business fact.

Resolved evidence becomes a proposal. The Committer validates operation, idempotency, tenant, resource, state
and version before one atomic transition. Business outcome and compliance outcome are recorded separately.
Only committed authoritative `NOT_EXECUTED` may become new input to retry policy.

Late responses follow the same path: generation/request correlation, full binding, protocol schema and
application output validation create only a proposal.

#### Engineering Thinking

Observation and mutation require different authority. Keeping Tool execution out of reconciliation makes blind
replay structurally impossible.

#### Production Example

An external research job status endpoint returns `UNKNOWN` until the observation budget expires. The operation
stays `PENDING_RECONCILIATION`; an alert carries a safe operation reference, and no original Tool call occurs.

#### Framework Connection

The MCP handler, reconciliation scheduler and retry policy each lack a Committer. Dependency injection makes
the absence of authority reviewable.

#### Exercise

Design the minimum read-only status response that can prove `NOT_EXECUTED` for one complete application
binding.

### Concept 5: Reconnect and version negotiation create new generations, not new authority

#### Tech Lead Question

Can a late response from an old connection complete a new request? Can a lower common protocol version reuse
an old permit with more capabilities?

#### Student Thinking

The learner rejected both shortcuts and required rejection before handler entry when no version is compatible.

#### Student Answer

“在 handler 前拒绝，提供 version incompatible。” “不能。”

#### Tech Lead Review

Correlation uses `(transport_generation, protocol_request_id)`. Reconnect increments the generation; old
responses remain audit evidence but cannot call the controlled service or Committer.

Version negotiation is generation-scoped. No common version returns `-32022` with supported versions and zero
handler/service calls. A lower common version requires fresh preflight and current authorization. Capability
downgrade cannot reuse a permit for a capability absent from the new generation.

#### Engineering Thinking

Protocol compatibility describes what peers can speak, not what a caller may do. Reconnect cannot bypass
duplicate, conflict, tenant or authorization bindings.

#### Production Example

Generation 1 supported Tools. After deployment, generation 2 supports only Resources. A generation-1 Tool
permit is stale and cannot authorize `tools/call` on generation 2.

#### Framework Connection

MCP version and capability data are converted into application preflight facts. They never enter business
authorization as grants.

#### Exercise

Explain why matching `protocol_request_id` alone is insufficient after reconnect.

### Concept 6: JWKS, load shedding and circuit breakers fail at different boundaries

#### Tech Lead Question

What should happen when a token uses an unknown key and JWKS refresh is unavailable? Where may global and
tenant-specific load shedding run?

#### Student Thinking

The learner chose `503`, rejected reuse of an old principal/permit, and separated cheap global shedding from
tenant priority based on current authorization.

#### Student Answer

“不能，应向 Client 返回 503。” “全局 load shedding 可以在低价基础设施前，按 tenant 分配优先级/配额
可以在 authorization。”

#### Tech Lead Review

A known cached key may remain valid under cache policy. An unknown key requires refresh. Refresh outage is an
authentication-dependency failure: return `503`, create no principal, reuse no permit, and call handler/service
zero times. Successful refresh with the key still absent is invalid identity (`401`).

Global pre-auth shedding may use trusted edge facts only. Tenant quota or priority requires an authenticated
principal and exact permit. Payload tenant text cannot claim priority. Local versus verified remote circuit
rejection also produces different dispatch evidence.

#### Engineering Thinking

Unavailable trust infrastructure must not manufacture trust. Early protection is cheap only when it avoids
identity-dependent policy.

#### Production Example

A burst claims `tenant=vip` in every body. The edge ignores that field. Only requests that establish identity
and receive a tenant-bound permit reach tenant capacity admission.

#### Framework Connection

The classroom JWKS refresh port and protection policies are deterministic seams, not production identity or
distributed-rate-limit implementations.

#### Exercise

Compare status, calls and evidence for unknown-key refresh outage, unknown key after successful refresh, local
circuit open and controlled Server circuit open.

### Concept 7: Observability explains decisions but never becomes authority

#### Tech Lead Question

May operation ID, tenant, trace ID or Resource URI be metric labels? May a trace prove business execution?

#### Student Thinking

The learner rejected both proposals and selected convergent fields for metric labels. They treated trace as an
auxiliary query mechanism only.

#### Student Answer

“不适合，要选择可收敛的字段作为 metric labels。” “trace 只是作为辅助查询，不参与业务 evidence。”

#### Tech Lead Review

Structured logs use a keyed HMAC operation reference and a closed schema. Metrics accept bounded dimensions
such as phase, failure kind, certainty, outcome and transport. Operation, idempotency, request, trace, tenant
and resource identifiers are rejected as labels. Trace correlation is diagnostic and explicitly cannot become
authorization or execution evidence.

#### Engineering Thinking

High-cardinality labels increase cost and can destabilize telemetry. Raw credentials and business identities
increase security/privacy risk. Observability must report the authority decision without becoming the decision.

#### Production Example

An operator follows `operation_ref` from a lifecycle log into a trace, then queries the authoritative operation
store. The trace helps locate evidence; only the store can resolve the business state.

#### Framework Connection

OpenTelemetry may carry trace context, but application code still validates operation binding and authoritative
state independently.

#### Exercise

Classify ten proposed fields as structured-log-only, bounded metric label, trace correlation, authority evidence
or prohibited credential.

## 8. Common Misconceptions

### Timeout means the handler did not run

❌ A read timeout proves non-execution.

✅ It proves only that the caller stopped waiting; execution may already have happened.

Why beginners think this: one local exception appears to summarize the remote system.

How to remember: “wait ended” and “work never started” are different facts.

### Cancellation is rollback

❌ A remote cancelled task erases prior effects.

✅ Cancellation asks future work to stop; historical effects and commits remain.

Why beginners think this: language runtimes present cancellation as task termination.

How to remember: control signals travel forward; they do not rewrite history.

### Dispatch certainty is intent

❌ A dispatch marker records what the caller wanted to do.

✅ It records the strongest trusted evidence about whether transport handoff may have occurred.

### Any `503` proves pre-handler rejection

❌ A peer can put `CAPACITY_REJECTED` in a response body and become retry-safe.

✅ Only a verified identity plus a locally controlled error contract can prove that classification.

### Reconciliation is delayed retry

❌ A reconciliation worker may call the original Tool.

✅ It receives only a read-only authoritative query port.

### Trace is business evidence

❌ A completed span proves the external side effect and authorizes commit.

✅ Trace data is diagnostic; the Committer requires application-owned authoritative evidence.

## 9. Engineering Trade-offs

### Conservative uncertainty versus aggressive availability

Recording `POSSIBLY_EXECUTED` reduces automatic recovery and may require operator attention, but prevents
duplicate side effects. Aggressive retry improves apparent availability only when downstream idempotency is
strong and non-execution evidence is reliable.

### Deterministic versus random jitter

Deterministic jitter is reproducible and spreads operations by identity. Cryptographically random jitter can
spread repeated patterns further, but complicates deterministic testing and replay analysis.

### Local teaching stores versus durable distributed stores

In-memory CAS demonstrates ownership and state transitions cheaply. It provides no crash durability or
multi-process coordination. Production requires transactional durable state while preserving the same API
contract.

### Rich metric labels versus bounded telemetry

Identity labels simplify one-off querying but create cost, privacy and stability risk. Use bounded metrics for
aggregation and safe logs/traces for targeted investigation.

### SDK-private seam versus weakened identity ordering

The pinned private dispatcher keeps the application’s pre-bound request identity and timeout semantics, at the
cost of upgrade coupling. The alternative—letting a high-level SDK silently create identity later—would weaken
the durable ordering contract.

## 10. Hands-on Exercises

### Exercise 1: Classify one timeout

Question: A read timeout occurs after transport handoff. What are the two certainty values and next state?

Think First: Separate the caller’s wait from remote execution.

Starter Artifact: `mcp_remote_lifecycle.py`.

Expected Output: `POSSIBLY_SENT`, `POSSIBLY_EXECUTED`, `PENDING_RECONCILIATION`, zero Committer calls.

Explanation: The exception cannot prove non-execution.

Follow-up Question: What extra trusted evidence could prove a pre-handler rejection?

### Exercise 2: Plan a safe retry

Question: Create attempt 2 after proven non-execution.

Think First: Which identities represent the operation and which represent one protocol attempt?

Starter Artifact: `mcp_retry_policy.py`.

Expected Output: same operation/idempotency identity, fresh protocol request ID, attempt number 2, bounded
delay and fresh gates.

Explanation: Identity continuity prevents duplicate/conflict bypass.

Follow-up Question: What durable state must exist before transport handoff?

### Exercise 3: Resolve an unknown outcome

Question: Authority proves `NOT_EXECUTED`; may the scheduler immediately dispatch?

Think First: Observation, durable fact and policy are separate stages.

Starter Artifact: `mcp_reconciliation.py`.

Expected Output: Committer first records `NOT_EXECUTED`; independent retry policy then decides eligibility.

Explanation: Reconciliation never owns Tool execution.

Follow-up Question: What happens if caller intent ended during reconciliation?

### Exercise 4: Review a telemetry design

Question: Reject unsafe/high-cardinality fields and retain useful bounded dimensions.

Think First: Metrics aggregate; logs and traces correlate.

Starter Artifact: `mcp_observability.py`.

Expected Output: metrics keep phase/kind/certainty/outcome/transport; identities and credentials are rejected.

Explanation: Observability remains diagnostic and cost-bounded.

Follow-up Question: Where should an operator retrieve authoritative business state?

Run the artifacts:

```bash
PYTHONPATH=projects/ai-agent/src python projects/ai-agent/evals/run_day93_seed_eval.py
PYTHONPATH=projects/ai-agent/src python projects/ai-agent/examples/day93_mcp_remote_lifecycle.py
```

## 11. Relevant Framework Connections

### Python MCP SDK

The real `mcp==2.2.0` SDK supplies Streamable HTTP mechanics, cancellation and its dispatcher. The Adapter pins
the version, forwards the configured read timeout into the private dispatcher call, maps failures into
application evidence and prevents SDK types from crossing the boundary.

### Streamable HTTP / ASGI

An independent loopback Server process supplies controlled remote-runtime evidence. It proves socket/process/
SDK behavior in a test environment, not authenticated production deployment.

### OpenTelemetry

Trace context can join Client, transport, Server and reconciliation diagnostics. It cannot supply identity,
authorization, execution certainty or durable commit authority.

No unrelated framework is forced into this lesson. Durable PostgreSQL coordination and distributed rate
limiting are future production connections, not executed Day93 evidence.

## 12. AI Backend Connections

Tool-calling agents frequently interact with remote systems whose side effects outlive the model turn. If the
Agent treats every timeout as retryable, it can create duplicate reports, jobs, purchases or notifications.

The safe Agent flow is:

```text
Agent intent
→ stable application operation identity
→ current exact Tool permit
→ bounded remote attempt
→ candidate result or unknown outcome
→ validation / reconciliation
→ sole Committer
```

This boundary also limits retry storms during provider or Tool outages, prevents model-supplied tenant text
from claiming capacity, and gives operators useful telemetry without leaking prompts, credentials or customer
identifiers into metric labels.

## 13. English Interview

### Key Vocabulary

- absolute deadline
- timeout budget
- dispatch certainty
- execution certainty
- pre-dispatch proof
- unknown outcome
- bounded retry
- exponential backoff
- jitter
- reconciliation
- generation-scoped correlation
- capability downgrade
- high-cardinality label
- credential-safe logging

### Useful Expressions

- “A timeout proves that the caller stopped waiting, not that the operation did not execute.”
- “I normalize transport failures into application-owned evidence before applying retry policy.”
- “A retry preserves operation identity but creates a fresh protocol attempt identity.”
- “Reconciliation can query authority, but it cannot replay the original Tool.”
- “Observability explains authority decisions; it does not grant authority.”

### Beginner Question

What is the difference between a deadline and a timeout?

**Strong answer:** A deadline is the absolute end time for the whole operation. A timeout bounds one wait or
phase and must fit inside the remaining deadline budget.

### Intermediate Question

When is an MCP retry safe?

**Strong answer:** Only after trusted evidence proves the business operation did not execute, and current
policy still allows another attempt. I preserve operation and idempotency identities, use a new request ID and
attempt number, apply bounded backoff/jitter, and recheck deadline, caller intent, authorization and capacity.

### Senior Question

How would you recover from a read timeout without duplicating a side effect?

**Strong answer:** I record the attempt as possibly sent and possibly executed, keep the operation pending,
and query an authoritative status/result interface. Reconciliation cannot execute the Tool. A separate
Committer validates the complete binding and version before durable transition. Only a committed
`NOT_EXECUTED` fact may be passed to the independent retry policy.

### Common Weak Answer

“Catch the timeout and retry with exponential backoff.”

This omits execution uncertainty, stable operation identity, current authorization, single-worker dispatch,
reconciliation and the Committer boundary.

### Strong Answer

“Backoff controls load; it does not make an unsafe retry safe. Eligibility comes from execution evidence and
current policy. If execution is possible, I reconcile rather than replay.”

## 14. Mental Model Summary

```text
Deadline             = absolute operation end time
Timeout              = bound for one wait/phase
Timeout budget       = remaining usable parent time
Cancellation         = request to stop future work, not rollback
Dispatch certainty   = evidence about transport handoff
Execution certainty  = evidence about business execution
FailureEvidence      = immutable attempt facts
Retry policy         = bounded current decision after proven non-execution
Reconciliation       = read-only authoritative observation
Committer            = sole durable transition authority
Reconnect            = new transport generation
Capability           = protocol support, not authorization
Logs/metrics/traces  = diagnostics, not authority
```

## 15. Today's Takeaway

- Most important mental model: failure evidence and retry policy are separate artifacts.
- Most important production risk: a read timeout followed by blind retry can duplicate an external effect.
- Most important trade-off: conservative unknown states reduce automation but preserve correctness.
- Most important framework connection: SDK failures stop at the Adapter as application-owned evidence.
- Most important AI Backend connection: an Agent may propose work, but remote uncertainty still flows through
  correlation, reconciliation and the sole Committer.
- Most important interview answer: “Backoff controls retry traffic; only non-execution evidence makes retry
  eligible.”

## 16. Before Next Lesson Checklist

- [ ] I can distinguish deadline, phase timeout and timeout budget.
- [ ] I can explain cancellation before and after dispatch.
- [ ] I can classify dispatch certainty independently from execution certainty.
- [ ] I can explain why exception type alone is insufficient retry evidence.
- [ ] I can preserve operation/idempotency identity across attempts.
- [ ] I can design bounded retry with backoff, jitter and a single-worker dispatch claim.
- [ ] I can explain why reconciliation has no Tool execution port.
- [ ] I can reject stale reconnect responses and stale downgraded permits.
- [ ] I can separate global shedding from authorized tenant capacity.
- [ ] I can choose safe log fields and bounded metric labels.
- [ ] I can run the Day93 seed, example and focused tests.
- [ ] I can state why controlled Streamable HTTP evidence is not production readiness.
- [ ] I can answer the senior interview question aloud.

Related artifacts:

- [Engineering design](../../projects/ai-agent/docs/DAY93_MCP_REMOTE_LIFECYCLE.md)
- [Classroom record](../../projects/ai-agent/docs/day93-mcp-remote-lifecycle-classroom-draft.md)
- [Validation evidence](../../projects/ai-agent/evidence/day93-validation.json)
- [Deterministic example](../../projects/ai-agent/examples/day93_mcp_remote_lifecycle.py)
- [Day94 handoff](../../projects/ai-agent/docs/DAY93_TO_DAY94_HANDOFF.md)
- [Day94 integration capstone](day94-agent-mcp-integration-capstone-and-english-interview.md)
