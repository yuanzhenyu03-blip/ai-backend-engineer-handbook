# Day94 Agent + MCP Integration Capstone

## Status

- Classroom baseline: `67bd43e187e076292b0163d4ad07ca9cc3fc125e`
- Evidence level: `RESTART_RECOVERY_RUNTIME`
- Production readiness: `MORE_EVIDENCE_NEEDED`
- Provider policy: deterministic controlled proposal; no paid Provider call required

Day94 composes the Day79–Day88 Agent runtime boundary with the Day89–Day93 MCP
protocol, Client, Server, security and remote-lifecycle boundaries. It demonstrates a
complete controlled path; it does not make the system production-ready.

## One-sentence invariant

Model or Framework output proposes an action; application policy authorizes an exact
action; MCP transports a bounded request; only the application-owned Committer may
turn a correlated and validated result into a durable business fact.

## End-to-end path

```text
user request
→ input validation
→ model/framework proposal                    # untrusted suggestion
→ application Tool governance                 # visible and registered Tool
→ application-owned operation identity
→ human approval decision                      # separate typed decision
→ authentication and current authorization     # separate typed decision
→ exact tenant/resource/Tool permit
→ deadline/caller-intent/version/capability/capacity/circuit preflight
→ atomic durable DISPATCH_STARTED claim
→ application DTO → MCP Client private Adapter
→ remote Streamable HTTP transport
→ MCP Server private Adapter → application DTO
→ authentication → exact authorization
→ candidate-only handler → controlled Tool
→ candidate result
→ current attempt/generation correlation
→ ProtocolObservation and protocol validation
→ application output validation
→ success transition proposal
→ sole Committer rechecks binding/state/version/fence/attempt
→ atomic conditional durable transition
→ VerifiedAgentObservation
→ Agent continuation or terminal response
```

The Agent never receives durable success from the candidate result itself. A
`VerifiedAgentObservation` exists only after the Committer has established the
durable fact.

## Identity and concurrency model

Stable across retries:

- `operation_id`
- `idempotency_key`
- `tenant_id`
- `resource_id`
- `tool_name`

Fresh or current for each attempt:

- incremented `attempt_number`
- fresh `protocol_request_id`
- current `transport_generation`

Mutable durable concurrency facts:

- `state`
- `version`
- `fence`

An exact duplicate converges to the existing operation. Reuse of an operation ID
with a different tenant, resource, Tool or idempotency binding is an identity
conflict and stops before handler, Tool and Committer execution.

## Access gate and preflight

Human approval and current authorization remain independent, auditable typed
decisions. Approval does not authenticate a caller and cannot restore a revoked
permit. Authentication creates a principal; current authorization grants or denies
an exact tenant/resource/Tool action.

Preflight rejects expired caller intent, cancellation, exhausted deadline, stale
state/version/fence, attempt-generation mismatch, incompatible protocol version,
missing capability, stale permit, rejected tenant capacity or open circuit. Passing
preflight does not dispatch. Only the atomic dispatch claim winner may hand the
request to transport.

## Happy path

The Server handler is candidate-only. It may invoke the controlled Tool but cannot
write durable application success. On the return path:

1. Correlation proves that the response belongs to the current operation attempt,
   request ID and transport generation.
2. Protocol validation produces a valid `ProtocolObservation`.
3. Application output validation checks the exact tenant/resource/Tool binding and
   required output fields.
4. The pipeline produces a transition proposal, not a durable fact.
5. The Committer rechecks stable binding, current attempt, state, version and fence,
   then performs one atomic conditional write.

A stale or late response stops at correlation. It does not reach output validation
or the Committer.

## Timeout and restart recovery

A read timeout proves only that the caller stopped waiting. If transport handoff may
have occurred, execution remains `POSSIBLY_EXECUTED` and the operation remains
`PENDING_RECONCILIATION`.

```text
persisted DISPATCH_STARTED marker
→ process crashes or loses response
→ new process reads stable identity and attempt history
→ Recovery Coordinator proposes RECONCILIATION_REQUIRED
→ Reconciliation Scheduler performs a read-only authority query
→ authoritative status result
   ├─ SUCCEEDED     → binding/correlation/validation → Committer
   ├─ FAILED        → Committer records failure and evidence
   ├─ NOT_EXECUTED  → Committer first records PROVEN_NOT_EXECUTED
   │                  → independent retry policy may evaluate a new attempt
   ├─ NOT_FOUND     → remain pending; bounded wait/re-query
   └─ UNKNOWN       → remain pending; bounded re-query or operator alert
```

The Recovery Coordinator and Reconciliation Scheduler never replay the original
Tool and never own the Committer. `NOT_FOUND` can be an eventual-consistency
observation: the authority queried may not yet expose a write that has already
happened. It is therefore not proof of non-execution.

Only committed `PROVEN_NOT_EXECUTED` evidence may reach the independent retry policy.
The policy then evaluates current caller intent, deadline, retry budget,
authorization, capacity and circuit state. A retry preserves stable identity,
creates a fresh attempt/request identity, uses the current generation, reruns access
and preflight checks, and persists a new dispatch marker before transport handoff.

## Observability boundary

- structured logs describe bounded events without credentials;
- metrics describe low-cardinality trends;
- traces correlate execution paths;
- the durable store and authoritative status service establish business facts.

Telemetry has no Committer write interface and is not an input to authorization,
reconciliation truth or durable transition decisions. Missing, duplicated or delayed
telemetry must not change a business outcome.

## Executed evidence

- dependency-free unit/integration suite covers proposal, access, preflight, claim,
  candidate, Committer, reconciliation, retry, shutdown and operator evidence;
- real Python MCP SDK Client plus independent loopback Streamable HTTP Server covers
  verified success and a read-timeout after Tool entry;
- an independent dispatch worker is terminated after it persists the marker and
  enters the Tool; a separate recovery worker queries authority without replay;
- deterministic example and sixteen invariant seed cases run without a model
  Provider API.

## Why no real model Provider is required

Day94 evaluates authority and lifecycle boundaries, not model quality. A controlled
proposal exercises the same application-owned proposal DTO and cannot bypass Tool
governance, approval, authorization, preflight, transport, validation or the
Committer. A production deployment that depends on a real Provider still needs
Provider-specific reliability, cost, privacy and safety evidence.

## Production gaps

The following remain not run:

- production Authorization Server/OIDC and JWKS rotation/outage lifecycle;
- authenticated production remote MCP deployment;
- persistent distributed operation/retry/reconciliation store;
- distributed rate limiting, capacity admission and circuit breaking;
- production telemetry backend and alert delivery;
- load, soak and backpressure testing;
- production network-partition, process-crash and deployment-failure drills;
- production Tool, customer data and real Provider validation;
- production SLOs, runbooks, rollback and incident-response exercises.

End-to-end controlled success is not production readiness.
