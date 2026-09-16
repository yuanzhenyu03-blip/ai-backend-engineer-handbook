# Day93 MCP Remote Lifecycle Engineering

## Scope and evidence level

Day93 adds a remote lifecycle boundary around the Day92 security gate and the Day91 handler. It owns
deadline propagation, transport failure classification, cancellation facts, bounded retry policy,
generation-scoped correlation, version/capability gates, reconciliation scheduling and safe
observability. It does not move durable business authority into the transport, handler, retry policy,
logs, metrics or traces.

The implemented path has deterministic unit/in-process coverage and a controlled remote runtime using
an independent loopback Streamable HTTP process with the real Python MCP SDK. This is not production
evidence. Production OAuth/JWKS, durable stores, distributed coordination, monitoring, load testing and
failure drills remain `NOT_RUN`; therefore `production_readiness = MORE_EVIDENCE_NEEDED`.

## Stable architecture

```text
remote MCP Client
→ edge transport protection
→ one absolute deadline / bounded phase timeout
→ Day92 authentication and current exact authorization
→ capacity admission
→ durable dispatch marker
→ transport
→ Day91 handler and controlled service
→ candidate response or unknown outcome
→ generation + request correlation
→ output validation
→ reconciliation or Committer
```

The horizontal observability plane contains credential-safe structured logs, bounded metrics and
diagnostic trace correlation. It explains a decision; it never supplies authorization or execution
evidence.

## Failure evidence is not retry policy

`FailureEvidence` records immutable application facts for one attempt:

- stable `operation_id` and `idempotency_key`;
- per-attempt `protocol_request_id` and `attempt_number`;
- failure phase and normalized kind;
- `dispatch_certainty`;
- independent `execution_certainty`;
- trusted evidence source.

The adapter converts SDK/private exceptions into this DTO. Core policy has no dependency on HTTP,
SDK exceptions or response bodies. An exception name cannot prove non-execution.

| Observed fact | Dispatch certainty | Execution certainty | Immediate state |
| --- | --- | --- | --- |
| local connect failure before transport handoff | `PROVEN_NOT_SENT` | `PROVEN_NOT_EXECUTED` | pre-dispatch failure |
| verified controlled server rejection before handler | `PROVEN_SENT` | `PROVEN_NOT_EXECUTED` | rejected before execution |
| read timeout or connection loss after handoff | `POSSIBLY_SENT` | `POSSIBLY_EXECUTED` | pending reconciliation |
| cancellation after possible dispatch | sent/possible | `POSSIBLY_EXECUTED` | pending reconciliation |
| authoritative reconciliation result | original fact preserved | proven result | Committer proposal |

Timeout proves only that the caller stopped waiting. Even when cancellation reaches a remote task, it
does not prove rollback or that a side effect did not already occur.

## Deadline and cancellation

`DeadlineBudget` carries one absolute parent deadline. Each phase receives the smaller of its configured
timeout and the remaining parent budget; cleanup reserve is never lent to the read phase. A downstream
component cannot restart an eight-second budget.

Cancellation stops new local work and requests remote cancellation when supported. Before-dispatch
cancellation proves non-execution. After-dispatch cancellation preserves unknown execution and routes the
operation to reconciliation. It never rewrites execution history.

## Bounded retry

`BoundedRetryPolicy` is pure: it consumes facts and returns a decision, but cannot dispatch or commit.
Eligibility requires all of the following:

- execution is proven not to have occurred;
- the normalized failure kind is retryable;
- caller intent is still active;
- retry budget and the original deadline have room;
- authorization is current;
- capacity and circuit gates admit the attempt.

Backoff is exponential and capped. Jitter is deterministic from application identity and attempt number,
which makes tests reproducible while spreading retries. After waiting, all volatile gates are checked
again. A conditional durable transition from `READY_FOR_RETRY` to `DISPATCH_STARTED` is performed before
transport handoff; only the winning worker may dispatch. Owner loss after that marker remains
`POSSIBLY_EXECUTED`.

An approved retry preserves `operation_id` and `idempotency_key`, increments `attempt_number`, and creates
a fresh `protocol_request_id`. It cannot use a new application identity to bypass duplicate/conflict
checks.

## Reconciliation

Reconciliation receives only a read-only authoritative status port; it has no original Tool execution
port. `NOT_FOUND` and `UNKNOWN` remain pending because absence may reflect eventual consistency. A bounded
schedule applies deterministic backoff, query count and deadline. Exhaustion emits one operational alert
and retains the unknown state.

The reconciliation Committer validates the full operation/tenant/resource binding, current pending state
and expected version before one atomic transition. Business outcome and compliance outcome are separate
facts. A committed authoritative `NOT_EXECUTED` fact may become input to the independent retry policy; it
does not itself dispatch a retry.

Late responses follow the same rule: correlation, binding, protocol schema and application output are
validated before a proposal exists, and the proposal still cannot commit by itself.

## Reconnect, versioning and security

Remote correlation is keyed by `(transport_generation, protocol_request_id)`. Reconnect creates a new
generation; a late response from an old generation cannot call the controlled service or Committer.

Protocol negotiation is generation-scoped. No common version is rejected before handler entry with
`-32022` and the server-supported versions. A lower common version requires fresh preflight and current
authorization. Capability downgrade cannot reuse a permit containing a capability absent from the new
generation.

Known cached signing keys may be used according to cache policy. An unknown key triggers refresh. If that
trusted dependency is unavailable, the request fails closed with `503`; no old principal or permit is
invented, and handler/service call counts remain zero.

Global load shedding may run before authentication but can use only trusted edge/transport facts. Tenant
priority and quota run only after authentication and exact authorization. A payload tenant never grants
capacity priority. Local circuit rejection is `PROVEN_NOT_SENT`; a verified controlled server circuit
rejection is `PROVEN_SENT + PROVEN_NOT_EXECUTED`.

## Observability

Structured lifecycle logs use a keyed HMAC operation reference and a closed typed schema. They cannot
carry bearer tokens, Authorization headers or signing keys. Metrics use bounded labels such as phase,
failure kind, certainty, outcome and transport; operation, protocol, trace, tenant and resource identities
are rejected as labels. Trace IDs are diagnostic correlation only and explicitly cannot become authority
evidence.

## Graceful shutdown

Shutdown first closes admission, then drains admitted work. At drain timeout, remaining handler tasks are
cancelled and their operation identities are preserved as `PENDING_RECONCILIATION`. No result is invented
and `committer_calls = 0`.

## Verification inventory

- deterministic lifecycle, retry, reconciliation, versioning, JWKS, protection and observability tests;
- real Python SDK Streamable HTTP success and read-timeout paths against an independent loopback process;
- [16-case Day93 seed](../evals/day93_mcp_remote_lifecycle_seed.jsonl),
  [seed runner](../evals/run_day93_seed_eval.py) and
  [deterministic example](../examples/day93_mcp_remote_lifecycle.py);
- Day88–Day92 regressions and prior seed suites;
- JSON/JSONL parsing, compile, whitespace and sensitive-data checks.

The controlled read-timeout experiment observed that the client abandoned the request while the
already-entered Tool coroutine completed. That result is the concrete reason a read timeout maps to
`POSSIBLY_EXECUTED`, not to a retry command.

The next composition boundary is recorded in the [Day94 handoff](DAY93_TO_DAY94_HANDOFF.md).

## References

- [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [MCP transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [MCP lifecycle](https://modelcontextprotocol.io/specification/2026-07-28/basic/lifecycle)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
