# Day 90 — MCP Client Engineering

## 1. Lesson Metadata

- Status: ✅ Completed (guided classroom scope)
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Advanced
- Estimated study time: 5–6 hours
- Prerequisite: Day89 — MCP Foundations and Protocol Model
- Next lesson: Day91 — MCP Server Engineering: Resources, Tools and Prompts Responsibility Boundaries
- Engineering artifact: dependency-free wire Client, version-pinned SDK-private Adapter, controlled stdio integration, seed eval and Day91 handoff
- Evidence: `INTEGRATION_RUNTIME`; production readiness `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After completing this lesson, you should be able to:

1. explain Client, Client Adapter, Codec and Transport responsibilities;
2. preserve application DTOs while isolating SDK-private types;
3. persist request binding and dispatch evidence before a side-effecting send;
4. distinguish protocol, binding, output-validation and business states;
5. handle duplicate, conflict, malformed, cancelled and unknown outcomes without unsafe replay;
6. validate Resource metadata before reading and treat Prompt/Resource content as untrusted;
7. own Client startup, inventory, invalidation and shutdown boundaries;
8. defend the evidence level and remaining production gaps in an English interview.

## 3. Why This Matters

Replacing Fake Transport with a real Client creates a crash window. A request may reach a Server while the
Client loses the response. If the application binds identity after sending, trusts SDK-generated IDs, retries a
side effect immediately, or lets an SDK result bypass output validation, it can duplicate work or commit data to
the wrong operation.

Day90 makes the wire real without giving the SDK authority over application identity, tenant policy or durable
state. That seam is what lets a team upgrade an SDK and later add a production Server without rewriting the
Research Agent core.

## 4. Roadmap Position

```text
Day88 replaceable Framework Adapter → application ToolProposal only
        ↓
Day89 SDK-independent MCP DTO, binding, correlation and observation
        ↓
Day90 real MCP Client + controlled separate-process SDK Server evidence
        ↓
Day91 Server responsibility boundaries
        ↓
Day92 auth/tenant isolation → Day93 remote lifecycle → Day94 capstone
```

Day90 does not implement production auth, production Tools, a remote lifecycle platform or model integration.

## 5. Lesson Map

```text
responsibility boundary
→ wire encoding and SDK isolation
→ pre-dispatch binding
→ real stdio integration
→ correlation and result classification
→ Resource/Prompt boundaries
→ inventory invalidation and lifecycle
→ evidence honesty
```

## 6. Core Mental Model

```text
Application operation
→ current policy/capability/preflight checks
→ local MCPRequestBinding
→ dispatch marker
→ Client Adapter / Transport
→ MCPResponseDTO
→ local correlation
→ ProtocolObservation
→ application output validation
→ Committer
→ optional durable transition
```

The Client proves protocol exchange. It does not prove that returned content is authorized or that a business
operation succeeded.

## 7. Main Concepts

### Concept 1: Client boundary and SDK-private types

#### Tech Lead Question

Should the application use the SDK response object directly when the SDK parses it successfully?

#### Student Thinking

The learner identified that doing so breaks the Client Adapter boundary and bypasses the rule that SDK
responses must be converted inside the Adapter.

#### Student Answer

“破坏了 Client Adapter 的应用边界，绕过了 SDK 的响应只能在 Adapter 的限制。”

#### Tech Lead Review

Correct. `MCPRequestDTO`, `MCPResponseDTO`, binding and observation remain application-owned. The Adapter owns
SDK lifecycle, protocol stamping, transport and conversion. Pydantic/SDK types never reach application core.

#### Engineering Thinking

The official Python SDK 2.2.0 supports MCP `2026-07-28`, but its high-level `call_tool()` does not accept the
already-persisted request ID. Day90 therefore uses a narrowly version-pinned SDK-private dispatcher seam while
retaining a dependency-free codec path. This sacrifices some upgrade convenience to preserve crash-safe
identity ordering.

#### Production Example

`op-report-42` is bound locally to `request-8`; the Server sees `request-8`, while `op-report-42` never appears
on the wire.

#### Framework Connection

The Day88 Framework Adapter still emits `ToolProposal` only. It never owns this Client or its transport.

#### Exercise

Upgrade the SDK in an isolated environment and prove that caller-supplied IDs still reach a controlled Server
before changing the production pin.

### Concept 2: Binding, dispatch marker and unknown outcome

#### Tech Lead Question

What happens when a request is sent and the connection fails before a response arrives?

#### Student Thinking

The learner immediately rejected a durable success and immediate retry, then refined the model by requiring a
dispatch marker to be persisted before the actual send.

#### Student Answer

“Unknown outcome；不立即重试避免二次副作用。应在真正发送请求前持久记录 dispatch marker。”

#### Tech Lead Review

Correct. Possible send becomes `OUTCOME_UNKNOWN`; the binding becomes `PENDING_RECONCILIATION`. A proven
not-sent attempt may become `ABORTED_PRE_DISPATCH`, but post-send cancellation or timeout never can.

#### Engineering Thinking

One application operation may have several immutable protocol attempts. Safe retry keeps
`application_operation_id` and Tool `idempotency_key`, creates a new `protocol_request_id`, and preserves old
bindings.

#### Production Example

The Client writes a report-publication request, loses stdio, and cannot tell whether the Tool created the
external report. Reconciliation queries authoritative evidence instead of replaying the Tool.

#### Framework Connection

Model-generated retry intent is only a new proposal; it cannot override pending reconciliation.

#### Exercise

Classify cancellation before dispatch, cancellation after dispatch, and timeout after possible send.

### Concept 3: Correlation and the four state layers

#### Tech Lead Question

Does `ProtocolObservation(PROTOCOL_RESULT)` authorize a business success?

#### Student Thinking

The learner required output validation and a Committer. During a combined scenario, the learner initially put
`INDIRECT_PROMPT_INJECTION` into `BindingStatus`, exposing a useful state-layer confusion.

#### Student Answer

Final model: protocol result and completed binding can coexist with rejected output and no business success.

#### Tech Lead Review

The four layers answer different questions:

```text
ProtocolOutcome          = what happened at the MCP message layer?
BindingStatus            = did this protocol attempt reach a terminal response?
OutputValidationOutcome  = may the application accept the content?
Application status       = may the business operation transition?
```

A matching JSON-RPC error is `PROTOCOL_ERROR` plus `COMPLETED`. A matching Tool result with `isError=true` is
`PROTOCOL_RESULT` plus `COMPLETED`, but it cannot enter the success Committer.

#### Engineering Thinking

Unknown IDs stop at correlation. Identical repeats are `DUPLICATE`; different payloads for one request ID are
`CONFLICT`. Conflict content is never “picked” by output validation.

#### Production Example

Two different report IDs arrive for `request-8`. The binding becomes conflict evidence and neither report is
published.

#### Framework Connection

The Provider or framework cannot select the “better-looking” conflicting result; application correlation is
authoritative.

#### Exercise

Build a table for JSON-RPC error, Tool-level error, unknown outcome, duplicate and conflict.

### Concept 4: Tool inventory and preflight

#### Tech Lead Question

Can a DTO claim `tools` capability and cause the Adapter to send a Tool absent from `tools/list`?

#### Student Thinking

The learner rejected caller-provided capability authority and required checks before a protocol attempt forms.

#### Student Answer

“不可以。”

#### Tech Lead Review

Capability says the Server supports the Tool protocol family; inventory says which Tools currently exist.
Day90 obtains both from the current SDK connection, validates Tool input schema and issues a request-bound
preflight permit. When the lifecycle handler receives `tools/list_changed`, it explicitly invalidates old
permits by changing the inventory generation. Automatic notification subscription was not run in Day90.

#### Engineering Thinking

The preflight permit contains a generation and request fingerprint. It is not business authorization. Tenant,
grant and operation checks stay outside the Adapter.

#### Production Example

`research.lookup` disappears after preflight. The old permit fails before transport write; an already-created
binding ends as `ABORTED_PRE_DISPATCH`, not reconciliation.

#### Framework Connection

The model may name a Tool, but the application and Client evidence decide whether a protocol attempt may form.

#### Exercise

Change one Tool argument after preflight and verify that the permit no longer matches.

### Concept 5: Resource and Prompt data flow

#### Tech Lead Question

Does a successful Tool result authorize automatic Resource dereference, and can an MCP Prompt become system
policy?

#### Student Thinking

The learner consistently kept separate boundaries for Tool, Resource, Prompt and the model Provider.

#### Student Answer

No. Resource scope is checked independently; Prompt content remains external input.

#### Tech Lead Review

Resource metadata is admitted before `resources/read`. Content is checked again after the read. A rejected
post-read body still records `resource_reads=1`; rejection cannot rewrite an effect that already occurred.
Current MCP Prompt roles are `user` and `assistant`; an invalid `system` role fails schema validation, and even
valid Prompt messages cannot override application policy.

#### Engineering Thinking

The model does not directly connect to MCP. The Research Agent mediates model API and MCP Client:

```text
Tool     = model may propose an action
Resource = application may supply validated reference data
Prompt   = application may use a validated task template
```

#### Production Example

A tenant-a Tool returns a tenant-b Resource URI. The application rejects before read with
`resource_reads=0`. A valid tenant-a Resource whose body contains instruction injection is rejected after read
with `resource_reads=1`.

#### Framework Connection

Model Provider integration is a separate boundary and was not required to prove Day90 MCP integration.

#### Exercise

Draw the Tool, Resource and Prompt paths and label where model input is created.

### Concept 6: Client lifecycle and evidence level

#### Tech Lead Question

What order should shutdown use, and what does a separate local stdio Server prove?

#### Student Thinking

The learner ordered shutdown correctly and initially over-promoted the final evidence to production readiness
before correcting the label.

#### Student Answer

Final answer: stop new requests, handle in-flight work, close Client; evidence is `INTEGRATION_RUNTIME` and
readiness is `MORE_EVIDENCE_NEEDED`.

#### Tech Lead Review

During drain, responses continue through correlation, output validation and Committer. Requests still unknown
at the deadline enter reconciliation. The controlled Server is a separate process and exercises the real SDK
stdio transport, so it is integration runtime evidence—not production.

#### Engineering Thinking

Production still needs real auth, production Tool behavior, deployment transport, monitoring, load/backpressure
and failure drills. Test volume cannot promote an evidence class.

#### Production Example

Shutdown receives a valid in-flight response and completes it; another request has only a dispatch marker and
becomes pending reconciliation before the Client closes.

#### Framework Connection

The application runtime owns full drain because Adapter completion precedes output validation and business
commit.

#### Exercise

Write a shutdown matrix for pre-dispatch, in-flight matched, in-flight unknown and already-completed attempts.

## 8. Common Misconceptions

### SDK parse success means application acceptance

❌ Pass the SDK object directly to business code.

✅ Convert inside the Adapter, correlate locally, then run application validation.

Why beginners think this: typed SDK objects look trustworthy.

How to remember: schema-valid is not tenant-authorized.

### Capability means a named Tool exists

❌ `tools` capability proves `research.lookup` is callable.

✅ Capability covers a method family; inventory and input schema cover a concrete Tool.

### Completed binding means successful operation

❌ `BindingStatus.COMPLETED` means business success.

✅ It only means the protocol attempt received a terminal response.

### Cancellation proves no effect

❌ A cancellation signal permits pre-dispatch abort.

✅ After dispatch begins, cancellation without authoritative result remains unknown.

### Local integration is production

❌ Real SDK plus local Server is production-ready.

✅ It is `INTEGRATION_RUNTIME`; production evidence remains missing.

## 9. Engineering Trade-offs

### High-level SDK API versus SDK-private seam

- High-level API: easier upgrades and supported surface, but SDK 2.2.0 mints an ID unknown before dispatch.
- Version-pinned private seam: preserves binding order and exact ID, but creates upgrade/test maintenance.
- Decision: preserve the Day89 contract and pin `mcp==2.2.0`; never silently weaken identity ordering.

### Dependency-free codec versus SDK-only implementation

- Codec: deterministic, easy failure injection, current wire contract visible.
- SDK: real lifecycle and transport behavior.
- Decision: keep both; use the codec for contract tests and SDK for integration evidence.

### Inventory cache versus list on every call

- Cached inventory reduces latency but requires invalidation and generation-bound permits.
- Per-call listing is fresher but increases latency and Server load.
- Day90 models explicit invalidation; Day93 owns production lifecycle hardening.

## 10. Hands-on Exercises

### Exercise 1: Preserve identity before dispatch

Question: implement a Client exchange that accepts an already-persisted binding.

Think First: which IDs remain stable across retry?

Starter Artifact: `projects/ai-agent/src/mcp_client.py`.

Expected Output: mismatched binding stops before transport.

Explanation: correlation authority must exist before possible side effects.

Follow-up Question: what durable marker closes the crash window immediately before send?

### Exercise 2: Test unknown outcome

Question: inject a transport timeout after possible send.

Think First: does timeout prove failure?

Starter Artifact: `projects/ai-agent/src/mcp_client_transport.py`.

Expected Output: `OUTCOME_UNKNOWN`, no durable transition.

Explanation: uncertain side effects require reconciliation.

Follow-up Question: when is a new protocol request ID safe?

### Exercise 3: Defend a production claim

Question: classify real SDK + separate local stdio Server evidence.

Think First: which production dependencies actually ran?

Starter Artifact: `projects/ai-agent/evidence/day90-validation.json`.

Expected Output: `INTEGRATION_RUNTIME` / `MORE_EVIDENCE_NEEDED`.

Explanation: evidence scope is environmental, not a test-count score.

Follow-up Question: what must Day92 and Day93 add?

## 11. Relevant Framework Connections

The official Python MCP SDK 2.2.0 is used only inside `mcp_sdk_private_adapter.py`. Its `Client`, stdio
transport, result models and dispatcher do not enter application contracts. PydanticAI remains a Day88
Framework Adapter that emits `ToolProposal`; no LangGraph runtime or model Provider integration was added.

## 12. AI Backend Connections

An AI backend often sits between a model and external systems. The model may propose a Tool, but the backend
owns permission, identity, side-effect safety and output trust. MCP Resources become untrusted model context;
MCP Prompts become application-controlled templates; Tool errors may be safely summarized back to the model
for replanning, but unknown outcomes must not be misreported as failures.

## 13. English Interview

### Key Vocabulary

`client adapter`, `request binding`, `dispatch marker`, `correlation`, `unknown outcome`, `reconciliation`,
`protocol observation`, `output validation`, `graceful shutdown`.

### Useful Expressions

- “The protocol request ID identifies one attempt; the operation ID identifies one business intent.”
- “SDK validation proves shape, not application authorization.”
- “A post-dispatch timeout is an unknown outcome, not a retry signal.”

### Beginner Question

Why isolate SDK types?

They are infrastructure details. Converting them inside a private Adapter keeps application contracts stable.

### Intermediate Question

How do you correlate a response after a retry?

Use a durable local binding per protocol attempt. Preserve the operation ID and idempotency key, and create a
new request ID only for a separately authorized retry.

### Senior Question

How do you prevent duplicate side effects after a Client timeout?

Persist binding and dispatch evidence before send, classify possible-send failures as unknown, suspend automatic
side effects, reconcile against authoritative downstream evidence, and let a Committer apply an idempotent
state transition.

### Common Weak Answer

“The SDK retries the request and returns the result.”

### Strong Answer

“I do not delegate business idempotency to an opaque SDK retry. The application owns operation identity,
binding, dispatch certainty, reconciliation and the final commit.”

## 14. Mental Model Summary

```text
Client Adapter          = SDK/wire isolation and conversion
protocol_request_id     = one MCP attempt
application_operation_id= one business intent
dispatch marker         = possible boundary crossing recorded before send
PROTOCOL_RESULT         != accepted output
COMPLETED binding       != successful operation
post-send uncertainty   = PENDING_RECONCILIATION
Resource URI            != read permission
MCP Prompt              != application policy
INTEGRATION_RUNTIME     != PRODUCTION
```

## 15. Today's Takeaway

The most important rule is ordering: establish application identity and dispatch evidence before a request can
cross the transport, then convert and correlate every response before content or durable state is touched. The
private SDK seam costs maintenance, but silently weakening this order would cost correctness. In AI backends,
the model, MCP peer and SDK are all outside the final business-trust boundary.

## 16. Before Next Lesson Checklist

- [ ] I can distinguish Client, Adapter, Codec and Transport.
- [ ] I can explain why binding must precede dispatch.
- [ ] I can classify protocol error, Tool-level error and unknown outcome.
- [ ] I can keep ProtocolOutcome, BindingStatus and OutputValidationOutcome separate.
- [ ] I can explain Resource pre-read and post-read validation.
- [ ] I can explain why MCP Prompt cannot become system policy.
- [ ] I can describe Client startup, inventory invalidation, drain and close.
- [ ] I can defend the SDK-private seam trade-off.
- [ ] I can state the honest evidence and production gaps.
- [ ] I can answer the senior interview question aloud.
