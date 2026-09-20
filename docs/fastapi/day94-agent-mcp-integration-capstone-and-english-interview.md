# Day 94 — Agent + MCP Integration Capstone and English Interview

## 1. Lesson Metadata

- Status: ✅ Completed at guided classroom scope
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Advanced / Phase capstone
- Estimated study time: 6–8 hours
- Prerequisites: Day79–Day93
- Previous lesson: [Day93 — Remote MCP Lifecycle](day93-remote-mcp-lifecycle-timeout-retry-versioning-and-observability.md)
- Next lesson: Day95 — RAG Ingestion Pipeline, Parsing and Document Lifecycle
- Main engineering artifact: [Agent + MCP Capstone](../../projects/ai-agent/docs/DAY94_AGENT_MCP_CAPSTONE.md)
- Runnable example: [Day94 deterministic capstone](../../projects/ai-agent/examples/day94_agent_mcp_capstone.py)
- Validation evidence: [Day94 validation](../../projects/ai-agent/evidence/day94-validation.json)
- Evidence level: `RESTART_RECOVERY_RUNTIME`
- Production readiness: `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After this lesson, the learner can:

- explain why Agent proposal, application authorization, MCP execution and durable commit are different
  authority boundaries;
- compose Tool governance, human approval, authentication, current authorization, exact permits and remote
  preflight without turning one decision into a substitute for another;
- preserve stable operation identity while rotating attempt, request and transport-generation identity;
- design a candidate-result path that requires correlation, protocol validation, application validation and
  the sole Committer;
- recover from timeout, response loss and process restart without replaying a possibly executed Tool;
- distinguish authoritative `NOT_EXECUTED`, eventually consistent `NOT_FOUND` and unresolved `UNKNOWN`;
- defend the placement of the Committer and prove that observability does not become authority;
- run and interpret a deterministic Agent + real MCP SDK capstone;
- identify the evidence still missing before a production-readiness claim;
- answer beginner, intermediate and senior Agent + MCP system-design questions in English.

## 3. Why This Matters

A successful demo usually follows one clean path: the model selects a Tool, the Tool returns a result and the
Agent answers. Production systems fail between those visible steps. A worker may crash after handing a request
to transport. A Client may time out while the remote Tool finishes. An approval may remain recorded while
authorization has been revoked. A late response may belong to an old attempt or transport generation.

If one large orchestrator treats every positive signal as success, it can duplicate side effects, cross tenant
boundaries, accept stale results or tell the Agent that work succeeded before durable state agrees. Day94
solves this team-scale reliability problem by composing the existing boundaries without transferring their
authority.

The cost and security implications are direct:

- blind retry can repeat a paid or irreversible action;
- stale authorization can expose tenant data;
- unbounded recovery can consume capacity indefinitely;
- high-cardinality or credential-bearing telemetry can create cost and privacy incidents;
- framework lock-in can make safety contracts dependent on one library's native state model;
- a false production claim can hide missing distributed-store, identity and failure-drill evidence.

## 4. Roadmap Position

```text
Day79–Day88 Agent Runtime
  loop → Tool governance → state/budgets → durability → human control
       → memory boundary → multi-agent → security → replaceable Framework Adapter
                                      |
                                      v
Day89–Day93 MCP
  protocol → Client → Server → security → remote lifecycle
                                      |
                                      v
Day94 Agent + MCP Integration Capstone
  proposal → authority → dispatch → candidate → commit → recovery
                                      |
                                      v
Day95–Day106 Production RAG
  ingestion → provenance/ACL → retrieval → grounding → evaluation
```

Day94 is the Phase 7B acceptance checkpoint. It reuses Day79's application Controller, Day80's Tool
governance, Day81–Day82 state/durability, Day83 current human control, Day84's non-authoritative memory,
Day85 fencing, Day86 security, Day88's replaceable Adapter and every Day89–Day93 MCP boundary.

Day95 can now add document ingestion without confusing model context, retrieval candidates or vector-index
visibility with durable source truth. The Day94 identity and recovery rules carry directly into eventually
consistent indexing and ingestion recovery.

## 5. Lesson Map

```text
Capstone incident
→ classify proposal, authority and identity
→ compose access gate and preflight
→ persist exact dispatch claim
→ execute through MCP Client/Server Adapters
→ validate candidate and commit once
→ preserve unknown outcome on timeout
→ recover after restart through authority query
→ retry only after committed non-execution
→ produce operator evidence without granting authority
→ defend the design in English
```

## 6. Core Mental Model

```text
Model/Framework output = proposal
Application policy     = authorization
MCP                     = bounded transport and execution observation
Handler result          = candidate
Committer               = sole durable transition authority
```

```text
proposal
→ governance
→ approval + current authorization
→ preflight
→ durable dispatch claim
→ MCP attempt
→ candidate
→ correlation
→ protocol validation
→ output validation
→ transition proposal
→ Committer
→ durable fact
→ verified Agent observation
```

The shortest reusable rule is:

> The Tool executes the action; the Committer establishes the durable business fact.

Unknown outcomes use a different path:

```text
DISPATCH_STARTED + no trusted response
→ PENDING_RECONCILIATION
→ read-only authoritative status query
→ typed observation/proposal
→ Committer or bounded re-query
→ retry policy only after committed PROVEN_NOT_EXECUTED
```

## 7. Main Concepts

### Concept 1: Capstone, end-to-end integration and the Orchestrator

#### Tech Lead Question

Can one Orchestrator own proposal interpretation, authorization, MCP transport, retry, reconciliation and the
durable business write because it sees the complete flow?

#### Student Thinking

The learner initially described the Orchestrator as the component that executes the whole path. Through the
incident sequence, the learner refined this to: “Orchestrator only calls independent components and routes
typed decisions.”

#### Student Answer

“Orchestrator only负责调用独立组件并路由 typed decisions，不能直接提交，还需要经过完整验证。”

#### Tech Lead Review

A **Capstone** is a phase-level integration checkpoint. It solves the problem of proving that earlier
contracts compose. It is not a new Agent Framework or proof of production readiness. Here, the minimal example
is `tenant-a/report-42` moving from Agent proposal to a verified durable observation. In the Research Agent,
Day94 closes Phase 7B before Production RAG begins.

**End-to-end integration** means one testable path crosses all relevant boundaries while preserving each
boundary's contract. It solves local-component success that fails when composed. It is not “put all logic in
one function.” The Day94 happy path uses a controlled proposal, real MCP SDK transport and a sole Committer.

An **Orchestrator** orders calls and routes typed decisions. It solves workflow composition. It is not the
owner of authorization, Tool execution or durable truth. `AgentMCPOrchestrator` receives narrow ports and
cannot turn an invalid candidate into success.

#### Engineering Thinking

Keeping authority in independent components makes negative paths reviewable: losing a dispatch claim creates
zero transport calls; stale correlation creates zero output-validation calls; timeout creates zero Committer
calls. The alternative—a stateful “god orchestrator”—is easier to demo but harder to recover, replace and
audit.

#### Production Example

A report-research workflow receives a valid proposal, but current authorization is revoked between approval
and dispatch. The Orchestrator routes `ACCESS_BLOCKED`; it cannot reuse the approval or call transport.

#### Framework Connection

PydanticAI translates Framework output into an application-owned proposal. It does not receive the MCP
transport or Committer. The same application contract can accept another Framework Adapter.

#### Exercise

Name every interface the Orchestrator may call, then mark which component owns each decision. Reject any
design where “the Orchestrator knows everything” becomes authority.

### Concept 2: Agent intent, Tool proposal, human checkpoint, preflight and exact permit

#### Tech Lead Question

If the model proposes `research.lookup` and a human approved it, why is another authorization check needed?

#### Student Thinking

The learner first combined approval and authorization into one gate, then corrected the model: keep them as
two independent, auditable typed decisions and compose them without letting approval restore a revoked permit.

#### Student Answer

“human approval and current authorization compose an access gate which combines separate typed decisions
before preflight.”

#### Tech Lead Review

**Agent intent** is the application's interpretation of what the Agent is trying to accomplish. It solves the
need to bind a proposed action to a trusted workflow. It is not identity or permission. For example, “collect
evidence for report-42” does not authorize a Tool call. In this Research Agent it becomes trusted application
input for operation preparation.

A **Tool proposal** is an application DTO translated from model/Framework output. It solves structured
communication of a suggested next action. It is not authorization, dispatch or commit. A proposal for an
invisible Tool stops before authority checks.

A **human checkpoint** is a current, exact decision for a consequential action. It solves risk review. It is
not authentication or a permanent permission grant. Approval for one operation/resource/version cannot
authorize another.

**Preflight** is the final read-only composition of current prerequisites before claiming dispatch. It solves
time-of-check and generation drift. It is not dispatch: the atomic claim still comes afterward. It checks
caller intent, deadline, cancellation, state/version/fence, current attempt/generation, protocol/version/
capability, capacity and circuit state.

An **exact permit** is a narrow current-authorization result bound to principal, operation, idempotency key,
tenant, resource and Tool. It solves confused-deputy and cross-tenant expansion. It is not an MCP capability
advertisement. In Day94, approval and the permit must independently match `tenant-a/report-42` and
`research.lookup`.

#### Engineering Thinking

Authentication establishes a minimized principal. Current authorization evaluates that principal against
revocation, scope, membership and exact grants. Approval captures risk acceptance. Preflight composes current
facts immediately before dispatch. Combining them in one boolean would erase why a request stopped and make
stale evidence easier to reuse.

#### Production Example

The manager's approval remains valid, but the user's Tool permit is revoked. The access gate returns blocked;
handler, Tool and Committer counts remain zero.

#### Framework Connection

Framework Tool visibility improves proposal quality, but application Tool governance is authoritative. Native
Framework MCP support may be used only behind the same Client/Server and permit boundaries.

#### Exercise

Classify each input—approval, principal, MCP capability, permit, capacity and circuit—as authority, protocol
compatibility or runtime admission. Explain why none can substitute for the others.

### Concept 3: Operation identity, attempt identity and the dispatch claim

#### Tech Lead Question

Two workers want to retry the same operation. Which identity remains stable, what changes and how many workers
may hand the request to transport?

#### Student Thinking

The learner first included request ID, attempt, fence, version and state inside “operation identity.” The model
then evolved into three categories: stable business identity, fresh attempt identity and mutable concurrency
facts.

#### Student Answer

“operation, idempotency key, tenant, resource and Tool stay unchanged; protocol request ID, attempt and
transport generation are current; state, version and fence change. Only one conditional claim wins.”

#### Tech Lead Review

**Operation identity** names one stable business intent: operation ID, idempotency key, tenant, resource and
Tool. It solves duplicate convergence across attempts and restarts. It is not the MCP request ID. For example,
`op-report-42/idem-report-42` remains stable during every safe retry.

**Attempt identity** names one protocol execution attempt: attempt number, protocol request ID and transport
generation. It solves correlation and stale-response rejection. It is not a new business operation. A retry
increments the attempt and uses a fresh request ID.

A **dispatch claim** is an atomic durable transition that gives one worker permission to perform transport
handoff for one exact attempt. It solves multi-worker races. It is not proof that the remote Tool executed.
The marker includes stable binding plus attempt, generation, state, version and fence before transport begins.

#### Engineering Thinking

The teaching store models `UPDATE ... WHERE state/version/fence ... RETURNING`. The winner receives one row;
the loser receives none and makes zero transport calls. A real distributed store would need the same atomic
property, not merely an in-memory lock.

#### Production Example

Two retry workers evaluate the same operation. Only the current-fence worker changes `READY_FOR_DISPATCH` to
`DISPATCH_STARTED`; a stale worker cannot send or commit.

#### Framework Connection

MCP request IDs remain protocol correlation keys. Framework run IDs and trace IDs may be recorded, but neither
replaces the application operation or durable fence.

#### Exercise

Create a table with “stable,” “fresh per attempt” and “mutable concurrency fact.” Place every Day94 identity
field in exactly one category.

### Concept 4: Candidate result, ProtocolObservation, Committer and durable transition

#### Tech Lead Question

What must happen after a Tool returns a successful MCP result before the Agent may observe business success?

#### Student Thinking

The learner correctly identified “correlation, output validation, Committer,” then refined the sequence to
include SDK-private conversion, ProtocolObservation, protocol validation and an explicit transition proposal.
The learner initially called the Committer “the real executor,” which was corrected.

#### Student Answer

“A returned candidate finds its binding by correlation, becomes a protocol observation, passes protocol and
output validation, then the Committer checks state/version/fence and performs an atomic durable transition.”

#### Tech Lead Review

A **candidate result** is untrusted application content decoded from a bounded MCP response. It solves safe
transport of a possible result. It is not durable success. The controlled Tool may return an external object
reference, but the handler cannot commit it.

A **ProtocolObservation** is an application-owned description of the correlated protocol outcome. It solves
the need to keep SDK types and peer payloads outside application policy. It is not business authority.

The **Committer** is the only application component allowed to establish a durable transition. It solves
stale, duplicate and competing-write races. It is not the Tool executor, authorization service or
Orchestrator. It rechecks exact stable binding, attempt/request/generation, state, version and fence before an
atomic conditional write.

A **durable transition** is the committed application fact produced by that write. It solves restart-safe
business truth. It is not a log line, trace span, metric or successful HTTP response. Only after it exists may
Day94 construct `VerifiedAgentObservation` for the Agent.

#### Engineering Thinking

Correlation runs first. A stale request or generation produces a stale observation and stops before output
validation. A valid candidate can only propose success. Two identical valid proposals may call the Committer,
but the store creates exactly one durable transition; an exact duplicate converges, while conflicting output
is rejected.

#### Production Example

A response from attempt 1 arrives after attempt 2 became current. Its candidate looks valid, but correlation
rejects it. Output-validation and Committer counts are zero.

#### Framework Connection

MCP SDK objects are translated inside private Adapters. The application candidate and observation remain
plain typed DTOs. The Framework receives only the post-commit verified observation.

#### Exercise

For correlation failure, output-validation failure, stale fence and exact duplicate, state the expected Tool,
validation, Committer and durable-transition counts.

### Concept 5: Restart recovery, Recovery Coordinator and eventual consistency

#### Tech Lead Question

After restart, the store contains `DISPATCH_STARTED` but no trusted response. Who may query authority, who may
propose a transition and who may write it?

#### Student Thinking

The learner initially proposed retry-policy processing, then recognized that the existing state still says
`PENDING_RECONCILIATION`. The final model separated read-only recovery, typed proposals and the sole
Committer.

#### Student Answer

“Use a reconciliation query port for authoritative status. The Recovery Coordinator and scheduler produce
typed decisions without replaying the Tool. The Committer alone writes the durable fact.”

#### Tech Lead Review

**Restart recovery** reconstructs work from persisted identity, marker and attempt history after process
loss. It solves memory loss. It is not permission to resend the Tool.

A **Recovery Coordinator** reads the durable marker and arranges the correct recovery path. It solves routing
without absorbing authority. It is not a Tool caller or Committer.

**Operator evidence** is a bounded report that separates telemetry claims, authoritative query observations
and durable facts. It solves diagnosis and escalation. It is not itself authorization or business truth.

An **integration invariant** is a property that must remain true across component boundaries—for example,
“a stale response never reaches output validation” or “reconciliation calls the original Tool zero times.” It
solves the gap left by isolated unit contracts.

A **phase-level acceptance test** executes the representative path and negative boundaries needed to close a
learning phase. It is not one happy-path demo. Day94 uses a real SDK Client, an independent Server process and
a separate restart/recovery process while keeping production dependencies out of scope.

#### Engineering Thinking

`NOT_FOUND` can be an eventually consistent observation: the authority's read view may lag behind a completed
write. It therefore remains pending. `FAILED` records an authoritative failure but does not prove the Tool was
never executed. Only a committed `NOT_EXECUTED` fact may enter independent retry policy.

#### Production Example

The dispatch worker persists its marker, enters the Tool and crashes. A new process reads the marker and
queries status. Tool and Committer counts remain zero during the observation cycle. If status remains unknown,
the scheduler performs bounded re-query or emits an operator alert.

#### Framework Connection

The Python MCP SDK provides transport; it does not provide application recovery authority. OpenTelemetry
helps correlate the old process and new recovery process, but trace data is not an authority input.

#### Exercise

Draw the branches for `SUCCEEDED`, `FAILED`, `NOT_EXECUTED`, `NOT_FOUND` and `UNKNOWN`. Mark exactly where
validation, Committer, retry policy and operator alerting may run.

## 8. Common Misconceptions

### “The Committer is the real executor”

❌ The Committer executes the Tool.

✅ The Tool performs the external action; the Committer establishes the durable application fact.

Why this seems reasonable: both appear near the end of a successful flow.

How to remember: execution changes the outside world; commit changes authoritative application state.

### “Restart should call retry policy”

❌ A new worker may resend because the old process disappeared.

✅ Process death says nothing about remote execution. Recovery queries authority and remains pending until
non-execution is durably proven.

### “`NOT_FOUND` means not executed”

❌ The status record is absent, so retry is safe.

✅ An eventually consistent read can lag a completed write. `NOT_FOUND` remains unresolved unless the
authority contract explicitly proves non-execution.

### “Human approval is enough”

❌ A valid approval authorizes dispatch even after permit revocation.

✅ Approval and current authorization are separate gates; both must remain valid for the exact action.

### “A successful trace proves success”

❌ A trace span can be used as reconciliation or Committer evidence.

✅ Trace, log and metric data are diagnostic. Durable stores and authoritative status services determine
business truth.

### “End-to-end success is production readiness”

❌ One real SDK loopback path proves production deployment.

✅ It proves a controlled integration level. Production identity, distributed storage/controls, telemetry,
load and failure drills remain separate evidence requirements.

## 9. Engineering Trade-offs

### Thin orchestration versus centralized convenience

A thin Orchestrator preserves replaceability, testable call counts and authority separation. A centralized
workflow object may reduce wiring, but it increases coupling and makes stale/negative paths harder to audit.

### Conservative pending state versus aggressive availability

Keeping unknown outcomes pending can delay user-visible completion and require operator work. Blind retry
improves apparent availability but may duplicate irreversible effects. Consequential Tools should prefer
conservative evidence.

### In-memory teaching store versus distributed durable store

The teaching store makes state/version/fence rules deterministic and reviewable. It does not prove database
isolation, failover, multi-region ordering or distributed contention. Production needs a persistent store and
executed concurrent/failure tests.

### SDK-private seam versus weakened application identity

A narrow, version-pinned private seam requires upgrade tests. Letting an SDK mint identity after durable
binding would weaken correlation and retry safety. Day94 preserves the seam and its regression matrix.

### Controlled proposal versus real model Provider

A controlled proposal removes cost and nondeterminism while proving authority boundaries. It does not test
model quality, latency, safety or Provider behavior. Add a real Provider only when those are the claims under
test.

## 10. Hands-on Exercises

### Exercise 1: Classify one returned result

Question: A response has the right operation ID but an old protocol request ID. May output validation run?

Think First: Separate stable identity from current attempt identity.

Starter Artifact: `CapstoneCandidatePipeline`.

Expected Output: `CORRELATION_REJECTED`; output-validation and Committer calls are zero.

Explanation: Stable operation identity is necessary but not sufficient; the result must belong to the current
attempt and generation.

Follow-up Question: What changes if every identity matches but `resource_id` is wrong?

### Exercise 2: Recover a crashed dispatch worker

Question: The marker is `DISPATCH_STARTED`, the Tool may have run and the status query says `NOT_FOUND`.

Think First: Decide whether absence in the current read view proves non-execution.

Starter Artifact: `RestartAwareDispatchJournal` plus `CapstoneRecoveryCoordinator`.

Expected Output: remain pending, schedule a bounded re-query, original Tool calls zero.

Explanation: Eventual consistency makes `NOT_FOUND` ambiguous.

Follow-up Question: What additional authority contract would be required to return `NOT_EXECUTED`?

### Exercise 3: Design the retry claim

Question: Two workers evaluate the same committed `NOT_EXECUTED` fact.

Think First: Identify the exact conditional-update predicates.

Starter Artifact: state, version, fence, operation and attempt fields.

Expected Output: one winner and one loser; the loser makes zero transport calls.

Explanation: Policy eligibility and dispatch ownership are separate decisions.

Follow-up Question: Which fields stay stable for the winner's next attempt?

### Exercise 4: Audit production readiness

Question: The loopback capstone passes. Can the team declare production readiness?

Think First: Group missing evidence into identity/infrastructure, distributed correctness and operations.

Starter Artifact: [Day94 validation](../../projects/ai-agent/evidence/day94-validation.json).

Expected Output: `MORE_EVIDENCE_NEEDED` with a concrete NOT RUN list.

Explanation: Evidence levels describe what actually executed, not architectural confidence.

Follow-up Question: Which failure drill would you run first for a side-effecting production Tool?

## 11. Relevant Framework Connections

### PydanticAI

The selected course Framework remains behind a replaceable Adapter. Its output is translated to
`AgentMCPToolProposal`; it does not own application identity, MCP transport or the Committer. Current native
MCP features cannot bypass the application Client/Server boundaries.

### Python MCP SDK

The pinned `mcp==2.2.0` Client and Server exercise real Streamable HTTP behavior. SDK-private types stay in
Adapters. Application DTOs own correlation, failure evidence, recovery policy and durable transitions.

### Streamable HTTP / ASGI

An independent loopback Server proves process and transport separation. It does not prove production
authentication, deployment, network partitions, load behavior or infrastructure failover.

### OpenTelemetry

Structured logs, metrics and traces support diagnosis. Operation/tenant/resource identifiers remain out of
metric labels; credentials never enter telemetry; no telemetry sink receives the Committer interface.

## 12. AI Backend Connections

The Research Agent uses the capstone to call `research.lookup` for `tenant-a/report-42`. The model's quality is
not the trust boundary. The backend must preserve exact operation and tenant binding even when the model,
Framework, transport or process changes.

The same model applies to RAG ingestion and indexing:

- document parsing or embedding requests are proposals/attempts, not durable source truth;
- an index `NOT_FOUND` may be eventually consistent;
- tenant/ACL authorization must be current at access time;
- retry preserves logical ingestion identity;
- retrieved passages and generated answers are candidates requiring provenance and validation;
- telemetry helps diagnose retrieval but cannot grant access or establish source truth.

## 13. English Interview

### Key Vocabulary

- proposal
- current authorization
- exact permit
- operation identity
- attempt identity
- dispatch claim
- candidate result
- authoritative reconciliation
- sole Committer
- durable transition
- eventual consistency
- production-readiness evidence

### Useful Expressions

- “Model output proposes an action; it does not authorize or commit it.”
- “The Tool executes the action; the Committer establishes the durable business fact.”
- “A timeout proves that the caller stopped waiting, not that the Tool did not execute.”
- “Recovery observes existing facts; it never invents a new operation identity.”
- “Observability helps operators diagnose the system, but it must never become authority.”

### Beginner Question

What is the difference between an Agent proposal and application authorization?

Strong answer: An Agent proposal is an untrusted suggestion translated from model or Framework output.
Application authorization evaluates a current principal and exact operation/tenant/resource/Tool binding. A
proposal can enter governance, but it cannot authorize, dispatch or commit itself.

### Intermediate Question

How do you recover from a possibly executed Tool call?

Strong answer: Preserve the original operation and attempt evidence, keep the operation pending and use a
read-only authoritative status query. Correlate and validate any resolved result before the sole Committer.
Retry is considered only after non-execution is authoritatively established and durably committed.

### Senior Question

Design an Agent + MCP system that survives timeout, reconnect and process restart.

Strong answer: Keep stable application operation/idempotency identity separate from fresh protocol attempts.
Compose governance, approval, current authorization and preflight, then atomically persist the exact dispatch
claim before transport. Keep SDK types in Adapters and handlers candidate-only. Correlate and validate results
before the sole Committer. Timeout after possible dispatch enters reconciliation. Reconnect advances the
generation, and restart reads durable markers and queries authority without replaying the Tool.

### Common Weak Answer

“The model chooses a Tool, MCP executes it, and if the call times out we retry with backoff.”

This omits authorization, operation identity, dispatch ownership, possible execution, result validation,
reconciliation and the Committer.

### Strong Answer

“The model only proposes. The application binds stable identity and composes current policy before an atomic
dispatch claim. MCP returns a candidate, not business success. Correlation and validation produce a transition
proposal, and only the Committer may write durable state. A possibly executed timeout remains pending and is
resolved through read-only authoritative reconciliation. I would still require production identity,
distributed-store, load, telemetry and fault-drill evidence before calling the system production-ready.”

Interview result: `PASS_WITH_LANGUAGE_CORRECTIONS`. The learner's technical model reached the senior design
boundary; remaining improvement is concise English spelling, plurality and consistent authority vocabulary.

## 14. Mental Model Summary

```text
proposal          = suggested action
approval          = human risk decision
authentication    = verified principal
authorization     = current exact permission
preflight         = current prerequisites, no dispatch
dispatch claim    = one exact worker may hand off one attempt
MCP result        = candidate
correlation       = belongs to current attempt/generation
validation        = protocol + application contract
Committer         = sole durable transition authority
timeout           = caller stopped waiting
reconciliation    = read-only authority query, never Tool replay
retry             = only after committed PROVEN_NOT_EXECUTED + current policy
observability     = diagnosis, never authority
```

Identity memory aid:

```text
Stable:  operation + idempotency + tenant + resource + Tool
Fresh:   attempt + protocol request ID + current transport generation
Mutable: state + version + fence
```

## 15. Today's Takeaway

- Most important mental model: proposal, authorization, execution and durable truth are separate boundaries.
- Most important production risk: a lost response can hide a completed side effect; blind retry duplicates it.
- Most important trade-off: conservative pending reconciliation sacrifices immediacy to preserve correctness.
- Most important framework connection: Framework and SDK types remain behind replaceable private Adapters.
- Most important AI Backend connection: RAG ingestion/retrieval must preserve the same identity, permission and
  candidate-versus-truth rules.
- Most important interview answer: “The Tool executes the action; the Committer establishes the durable
  business fact.”

Executed evidence reached `RESTART_RECOVERY_RUNTIME`: 730 dependency-free tests and 31 real-SDK/restart
integration tests passed, 761 total. This is not `PRODUCTION`.

## 16. Before Next Lesson Checklist

- [ ] I can explain proposal versus authorization versus execution versus durable commit.
- [ ] I can explain why approval never replaces authentication or current authorization.
- [ ] I can divide identity into stable, fresh-per-attempt and mutable concurrency fields.
- [ ] I can explain why the dispatch marker must exist before transport handoff.
- [ ] I can trace candidate → correlation → protocol validation → output validation → Committer.
- [ ] I can explain why stale correlation stops before output validation.
- [ ] I can explain timeout, `PENDING_RECONCILIATION` and eventual-consistency `NOT_FOUND`.
- [ ] I can explain why recovery never replays the original Tool.
- [ ] I can explain why committed `PROVEN_NOT_EXECUTED` must precede retry policy.
- [ ] I can prove that telemetry has no authorization, reconciliation or Committer authority.
- [ ] I can run the deterministic capstone and interpret its operator evidence.
- [ ] I can list the remaining production identity, distributed and operational evidence gaps.
- [ ] I can answer the Phase 7B beginner, intermediate and senior questions aloud in English.
- [ ] I am ready to carry these boundaries into Day95 document ingestion and indexing.

Related artifacts:

- [Day94 design](../../projects/ai-agent/docs/DAY94_AGENT_MCP_CAPSTONE.md)
- [Day94 classroom record](../../projects/ai-agent/docs/day94-agent-mcp-capstone-classroom-draft.md)
- [Day94 research evidence](../../projects/ai-agent/research/day94-agent-mcp-capstone-evidence.jsonl)
- [Day94 validation](../../projects/ai-agent/evidence/day94-validation.json)
- [Day95 handoff](../../projects/ai-agent/docs/DAY94_TO_DAY95_HANDOFF.md)
