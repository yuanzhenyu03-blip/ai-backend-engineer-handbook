# Day91 MCP Server Engineering — Classroom Record

## Baseline and scope

- Remote `main` was re-read and fixed at `2dd3c86265c6935ec0f70cd118418dcb2406c29b`.
- The original checkout was dirty, so the class used an isolated clean worktree.
- Day90's 21 focused tests passed before Day91 changes.
- Official sources were rechecked for specification `2026-07-28` and SDK `mcp==2.2.0`.
- No production Provider, Tool, remote transport or credentials were used.

## Mental model developed during class

```text
SDK protocol object
→ Server Adapter conversion
→ application-owned request
→ capacity admission
→ handler
→ application admission and narrow injected service
→ candidate/error
→ Adapter wire mapping
```

The learner correctly established that a handler cannot execute a production Tool merely because it is
registered. Capability is discovery evidence; permission is current application evidence.

## Reviewed learner decisions

1. Application-service boundaries perform authorization and semantic validation.
2. A valid Tool response is `PROTOCOL_RESULT`; output rejection is `REJECTED`; durable transition remains false.
3. Anticipated application Tool rejection is a Tool-level `isError=true` result.
4. Unknown methods, unavailable capacity and invalid cursors are Protocol errors.
5. A first inventory page is not a complete inventory.
6. Old inventory permits and cursors become invalid when the inventory revision changes.
7. Cross-tenant Resource requests are rejected before read (`resource_reads=0`).
8. Malicious Resource content is `INDIRECT_PROMPT_INJECTION`; it is discovered after one read and never reaches model context.
9. Malicious Prompt arguments are rejected before rendering (`prompt_renders=0`).
10. Dangerous rendered Prompt text cannot call a Tool or read a Resource (both counters remain zero).
11. Backpressure is applied before handler entry.
12. Shutdown closes admission before draining in-flight handlers.
13. Drain timeout preserves operation ID as `PENDING_RECONCILIATION`; cancellation is not business failure.
14. SDK Context is converted to `ServerToolRequest` before application dispatch.
15. Duplicate application operations cannot execute twice.
16. Different idempotency keys for one operation are `IDENTITY_CONFLICT` and cannot execute.
17. MCP output Schema and application output validation cannot replace each other.
18. Handler output remains a candidate; only the application Committer may perform an optional durable transition.
19. A timeout after possible execution remains unknown and cannot trigger blind retry.

One learner answer was corrected: a Prompt message that says “read a Resource” has not performed a read.
The correct counters are `tool_calls=0`, `resource_reads=0`, while post-render inspection means
`prompt_renders=1`.

## Failure-driven implementation refinements

- The first pagination middleware assumed an SDK model, while the actual SDK middleware boundary supplied an
  already serialized dictionary. The Adapter was corrected and the real stdio suite rerun.
- SDK 2.2.0 rejected `Context` injection for a static Resource. The static registration was removed rather
  than bypassing the application request-conversion boundary. Dynamic Resources remain explicitly listed as
  templates and read through the controlled handler.

## Evidence so far

- Day91 dependency-free boundary/lifecycle/pagination/grader: 25 passed.
- Day91 real SDK separate-process stdio: 15 passed.
- Day91 focused total: 40 passed.
- Day90 focused regression: 21 passed.
- Day89 regression: 21 passed.
- Day88 Adapter regression: 43 passed.
- Cumulative split total: 621 passed.
- Day91 seed: 14/14 passed.
- Deterministic example: passed.
- Final synthesis: instructor-authored first, followed by an independent learner synthesis.
- Independent learner synthesis: `ASSESSED_PASS_WITH_DIRECTIONAL_CORRECTION`.
- Course completion gate: `PASSED`.

## Independent learner synthesis assessment

The learner independently distinguished Tool as a candidate-action interface, Resource as a candidate-data
interface, and Prompt as a candidate-template interface. They also correctly placed backpressure before the
handler; kept schema, semantic, correlation, output and Committer checks between a candidate result and a
durable business transition; and described shutdown as close admission, drain in-flight work, then either
finish cleanly or preserve unresolved operations as `PENDING_RECONCILIATION`.

One directional wording was corrected: on the inbound Server path, the Server Adapter converts MCP/SDK
requests and context into application-owned request DTOs. On the outbound path, it converts application
decisions into MCP protocol results. Application authorization evaluates the inbound application request and
its identity, scope, capability and permit; it does not treat an MCP result as the authorization input.

## Instructor-authored synthesis requested by the learner

The MCP Server is a controlled protocol entrance, not a business authority. The Server Adapter owns SDK
types, request conversion and wire error mapping. Application handlers receive only application-owned DTOs
and narrow injected ports. A Tool is a candidate-action interface, a Resource is a candidate-data interface,
and a Prompt is a candidate-template interface. None of them grants authorization or durable commit power.

Tool requests pass through pre-handler capacity, application admission, an application-issued permit,
idempotency identity, a controlled service and semantic output validation. The returned value is still only a
candidate. Day90 Client correlation and output validation remain in force, and only the application Committer
may perform an optional durable transition.

Resource URIs are not authorization. Cross-tenant requests stop before read; returned content remains
untrusted and indirect prompt injection stops after one read but before model-context assembly. Prompt
arguments are validated before rendering, rendered messages are validated again, and Prompt text cannot
become system policy or automatically call Tools or read Resources.

Tool-level failures are valid protocol results with `isError=true`; capacity, Resource, Prompt and cursor
failures use Protocol errors. Inventory completeness requires every page from one revision. Shutdown closes
new admission first, drains in-flight handlers, and moves unresolved operation identities to
`PENDING_RECONCILIATION` after timeout. Unknown outcome never proves failure and never authorizes blind retry.
