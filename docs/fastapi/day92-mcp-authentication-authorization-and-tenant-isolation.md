# Day 92 — MCP Authentication, Authorization and Tenant Isolation

## 1. Lesson Metadata

- Status: ✅ Completed (guided classroom scope)
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Advanced
- Estimated study time: 7–8 hours
- Prerequisite: Day91 — MCP Server Engineering: Resources, Tools and Prompts Responsibility Boundaries
- Previous lesson: [Day91](day91-mcp-server-engineering-resources-tools-and-prompts-responsibility-boundaries.md)
- Next lesson: [Day93 — Remote MCP Lifecycle](day93-remote-mcp-lifecycle-timeout-retry-versioning-and-observability.md)
- Engineering artifact: application-owned principal and authorization DTOs, HTTP/stdin security adapters,
  deterministic token verifier, tenant-bound permits, composed security tests, seed eval and Day93 handoff
- Evidence: `INTEGRATION_RUNTIME`; production readiness `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After completing this lesson, you should be able to:

1. explain Authentication, Authorization and Tenant Isolation in plain language;
2. compare HTTP Bearer identity with stdio trusted-Launcher identity;
3. validate signature, issuer, audience, subject, expiration, not-before and trusted key identity;
4. explain why a valid token does not grant every Tool, Resource or Prompt permission;
5. keep raw credentials and SDK/private auth types outside application handlers;
6. issue principal-, operation-, tenant- and capability-bound permits from current authorization facts;
7. prevent payload, URI, Prompt and capability negotiation from expanding authority;
8. apply revocation, key rotation, fail-closed behavior and enumeration resistance;
9. order cheap edge protection, authentication, authorization, capacity and handler execution correctly;
10. distinguish safe pre-dispatch retry from unknown-outcome reconciliation;
11. preserve the Day91 candidate-result and no-Committer handler boundary;
12. defend the design and its evidence limitations in an English interview.

## 3. Why This Matters

An MCP request can be syntactically valid and still be dangerous. A caller may put `user_id=admin-user` in
Tool arguments, request a URI under another tenant, provide an expired token with convincing claims, or render
a Prompt that asks the model to act as an administrator. None of those facts proves current authority.

In production, a weak security boundary creates cross-tenant data exposure, confused-deputy execution,
credential leakage, resource enumeration, duplicate side effects and false durable success. Day92 places a
trusted identity and authorization boundary before the Day91 Server Adapter and handler admission while
preserving Day89–Day91 operation identity, correlation, output validation and reconciliation contracts.

The lesson also avoids a common operational mistake: treating every security failure alike. Missing identity,
explicit denial, authorization-infrastructure failure, capacity exhaustion and unknown external outcome need
different handling even though all must prevent unauthorized durable change.

## 4. Roadmap Position

```text
Day89 application DTOs, binding, correlation and observation
        ↓
Day90 controlled Client and SDK-private conversion
        ↓
Day91 bounded Server Tool / Resource / Prompt handlers
        ↓
Day92 trusted identity + current authorization + tenant isolation
        ↓
Day93 remote timeout / retry / versioning / observability
        ↓
Day94 Agent + MCP capstone
```

Day92 reuses Day51/Day52 authentication and authorization ideas, Day80 Tool permission, Day81–Day83 operation
identity and reconciliation, Day86 untrusted-content thinking, and Day89–Day91 MCP boundaries. Day93 depends on
Day92's precise distinction between proven pre-dispatch failure and possible execution.

## 5. Lesson Map

```text
transport identity source
→ token / launch-context validation
→ minimized AuthenticatedPrincipal
→ current revocation and membership
→ exact Tool / Resource / Prompt permit
→ edge and application capacity order
→ Day91 handler and candidate result
→ safe retry or reconciliation
→ evidence and production limits
```

## 6. Core Mental Model

```text
Authentication = Who is this caller?
Authorization  = May this caller perform this exact operation now?
Tenant isolation = Which tenant boundary may this operation cross? Usually only one.
```

The complete trust flow is:

```text
cheap identity-independent edge protection
→ HTTP Bearer verification OR stdio trusted Launcher context
→ AuthenticatedPrincipal
→ current revocation + scope + tenant membership + exact grant
→ narrow permit
→ application capacity
→ Day91 handler
→ controlled service
→ candidate result
→ correlation + observation + output validation
→ Committer
```

Remember three inequalities:

```text
client payload identity != authenticated principal
valid token             != permission for every capability
MCP capability          != application authorization
```

## 7. Main Concepts

### Concept 1: HTTP and stdio use different trusted identity sources

#### Tech Lead Question

Are stdio and HTTP the same transport, and should both authenticate each request with a Bearer token?

#### Student Thinking

The learner initially treated `transport` as one mechanism that “uses stdio and HTTP to transmit.” After a
process diagram, they separated the transport abstraction from its alternative implementations and identified
different trust boundaries.

#### Student Answer

“stdio 的可信身份来源是可信 Launcher/进程上下文，HTTP 是每请求 token validation。”

#### Tech Lead Review

Correct. HTTP receives requests from a remote network boundary, so each request extracts and verifies a Bearer
credential. stdio normally connects a trusted parent Launcher to a child process through local pipes. It does
not turn command arguments or MCP payload fields into credentials.

```text
HTTP Client ── Authorization: Bearer ... ──> HTTP MCP endpoint

Trusted Launcher ── starts process + owns pipes ──> stdio MCP Server
```

An HTTP principal requires token expiration. A stdio principal may use process lifetime rather than token
expiration, but every operation still checks current revocation, membership and grants.

#### Engineering Thinking

Forcing one identity mechanism onto both transports hides the real trust boundary. Conversely, “local process”
must not mean “trust every argument.” The Launcher, OS permissions, executable path, environment construction
and pipe ownership form the stdio authentication boundary.

#### Production Example

A local IDE launches a controlled MCP Server over stdio with a minimized machine principal. A remote research
service exposes Streamable HTTP and validates a Bearer token for every request.

#### Framework Connection

The Python MCP SDK owns transport mechanics. `mcp_security_adapter.py` owns transport-specific credential or
Launcher conversion. Application authorization receives only `AuthenticatedPrincipal`.

#### Exercise

Draw the process and network boundaries for an IDE-launched stdio Server and a remote HTTP Server. Mark where
raw credentials may appear and where they must disappear.

### Concept 2: Token validation establishes a minimized principal

#### Tech Lead Question

Can the Server trust token claims after merely decoding a JWT-shaped string?

#### Student Thinking

The learner correctly rejected invalid signatures and future `nbf` tokens, but initially named the outcomes
`wrong_sign` and `waiting_nbf`. They also first called a token missing `sub` “missing authentication.”

#### Student Answer

“不能……handler 和 service 各调用 0 次。”

#### Tech Lead Review

The effect boundary was correct. The precise outcomes are:

| Condition | Outcome |
| --- | --- |
| no credential | `MISSING_CREDENTIAL` |
| structurally invalid token | `MALFORMED_CREDENTIAL` |
| bad signature | `INVALID_SIGNATURE` |
| future not-before | `NOT_YET_VALID` |
| expired token | `EXPIRED` |
| wrong issuer | `WRONG_ISSUER` |
| wrong audience | `WRONG_AUDIENCE` |
| no subject | `MISSING_SUBJECT` |
| unknown trusted key ID | `UNKNOWN_SIGNING_KEY` |

Only a successful validation creates a minimized principal. Raw token bytes, request-provided keys and
unneeded claims never enter handlers.

#### Engineering Thinking

Signature proves integrity under one key; it does not prove the correct issuer, recipient, time window or
subject. A signed `role=admin` claim is still only policy input. The application must explicitly map verified
claims to permissions instead of treating string values as universal authority.

#### Production Example

During rotation, trusted JWKS contains `K-old` and `K-new`, so valid tokens signed by either key pass. After
`K-old` leaves the trusted set, even an unexpired old token fails closed. A `jwk` embedded by the token cannot
reintroduce the removed key.

#### Framework Connection

The classroom HMAC verifier makes negative paths deterministic. A production deployment must use a standard
JWT/JWKS library and the configured issuer's key endpoint, refresh/cache policy and algorithms.

#### Exercise

Given tokens with a bad audience, missing subject and removed signing key, predict the exact outcome and prove
that authorization, handler and service calls remain zero.

### Concept 3: Authorization uses current facts and exact permits

#### Tech Lead Question

If a valid principal has a signed `role=admin`, may it call `research.lookup` without the required scope and
current Tool grant?

#### Student Thinking

The learner consistently separated identity from permission and rejected the idea that admin-like payload or
token text could replace current application facts.

#### Student Answer

“不能，handler 和 controlled service 应各调用 0 次。”

#### Tech Lead Review

Correct. The authorization equation is:

```text
not currently revoked
AND required scope
AND current tenant membership
AND exact Tool / Resource / Prompt grant
= narrow permit
```

The permit binds issuer, subject and the exact target. Tool permits also bind application operation ID,
idempotency key, tenant and Tool. A token is not an authorization database snapshot.

#### Engineering Thinking

Current facts support revocation and membership changes before token expiry. If the authorization service is
unavailable, the Server fails closed with `AUTHORIZATION_UNAVAILABLE`; it does not treat “cannot check” as
“allowed.” Internally the reason stays auditable, while the external message remains non-sensitive.

#### Production Example

A `research-worker` Client Credentials principal has the right scope but no `tenant-a` membership. It cannot
inherit `ordinary-user` membership from the same application or client ID. The machine needs its own grant.

#### Framework Connection

Application authorization is a port injected into the security boundary. SDK token types, a database client
or policy-engine response do not leak into Day91 handlers.

#### Exercise

Design the smallest permit needed for one Tool call. Reject fields that are useful for logging but unnecessary
for executing the bounded operation.

### Concept 4: Tenant, URI, Prompt and capability are not authority

#### Tech Lead Question

Can `research://tenant-b/report-42`, a Prompt argument `role=admin`, or a negotiated `tools` capability grant
the requested permission?

#### Student Thinking

The learner correctly identified cross-tenant leakage and Prompt privilege escalation, then briefly confused
capability admission with capacity admission. The final model separated protocol support, permission and
runtime capacity.

#### Student Answer

“不能……各调用 0 次。”

#### Tech Lead Review

Correct. These fields describe different things:

```text
URI / tenant_id  = requested target
Prompt arguments = requested rendering data
MCP capability   = protocol feature support
Authorization    = permission for an exact current operation
Capacity         = runtime ability to execute it now
```

A cross-tenant Resource stops before read. A Prompt privilege argument stops before render. A rendered Prompt
is only candidate text and cannot automatically trigger Tool or Resource calls.

#### Engineering Thinking

Cross-tenant denial and nonexistent Resource should share a safe external message such as “Resource is
unavailable.” Different external messages would reveal whether another tenant's resource exists. Internal
audit classifications may remain precise.

#### Production Example

An authenticated `tenant-a` user guesses `research://tenant-b/report-42`. The URI parser identifies the target;
current membership rejects it. The reader receives no permit and is called zero times.

#### Framework Connection

MCP capability negotiation and inventory support discovery and compatibility. They never replace application
authorization. Prompt rendering remains behind Day91 pre-render and post-render safety checks.

#### Exercise

Create one safe external Resource error for both “not found” and “cross-tenant,” while retaining distinct
internal audit outcomes.

### Concept 5: Operation identity prevents replay and confused-deputy execution

#### Tech Lead Question

If `ordinary-user` owns `op-report-42`, may an authorized `admin-user` reuse that operation ID?

#### Student Thinking

The learner recognized that admin permission for a new operation does not transfer ownership of an existing
operation.

#### Student Answer

“identity conflict.”

#### Tech Lead Review

Correct.

```text
same operation + same complete binding      = DUPLICATE
same operation + different principal/target = IDENTITY_CONFLICT
```

Both stop before handler/service execution. The Server's own powerful credential cannot expand the caller's
permit; a controlled service receives only the exact application permit.

#### Engineering Thinking

Binding operation identity to issuer, subject, idempotency key, tenant and Tool prevents one caller from
hijacking another caller's long-running or retried work. New privilege does not rewrite historical identity.

#### Production Example

An internal service credential can technically query every tenant database. The application permit still
restricts one call to `ordinary-user`, `tenant-a`, `research.lookup` and `op-report-42`.

#### Framework Connection

Day92 authorization binding complements Day91 handler idempotency and Day89 Client-side request-to-operation
binding. Each layer owns a different identity boundary.

#### Exercise

Compare a duplicate request, an identity conflict and a new authorized operation. State the handler/service
counts for each.

### Concept 6: Failure position controls HTTP response, capacity and retry

#### Tech Lead Question

Should every limit wait until after authentication, and should every failure retry based only on its HTTP
status code?

#### Student Thinking

The learner first placed authentication before application capacity, then correctly refined the model: cheap
identity-independent edge protections may run earlier. They also chose 403 for an authorization-service outage
before correcting it to 503.

#### Student Answer

“系统能否证明请求没有越过可能产生副作用的执行边界。”

#### Tech Lead Review

That is the durable rule. The order is:

```text
body size / connection / source-bucket limits
→ authentication
→ authorization
→ principal/tenant quota
→ application capacity
→ handler
```

Security HTTP mapping:

| Result | Typical HTTP status |
| --- | ---: |
| invalid/missing identity | 401 |
| authenticated but explicitly denied | 403 |
| authorization dependency unavailable | 503 |

Later MCP capacity and business outcomes remain owned by the protocol/application layer.

#### Engineering Thinking

Retry depends on execution evidence, not status alone. Authentication, authorization and capacity rejection
before handler prove zero controlled-service calls; after recovery the Client may reuse the original operation
ID and idempotency key. A timeout after possible service execution becomes `PENDING_RECONCILIATION` and must
not create a new identity for blind retry.

#### Production Example

An authorization store returns 503 before permit creation. The same caller safely retries the same operation
after recovery. A downstream Tool times out after accepting work; the operation stays pending until evidence
confirms the result.

#### Framework Connection

An edge gateway may enforce body/IP limits. The application security boundary owns principal-aware quota and
authorization; the Day91 coordinator owns application capacity.

#### Exercise

Classify five failures as safe retry or reconciliation. For every safe retry, require reuse of the original
operation ID and idempotency key.

### Concept 7: Handler returns a candidate; Committer owns durable truth

#### Tech Lead Question

On the fully authorized positive path, may the Server handler commit durable business state directly?

#### Student Thinking

The learner carried the Day89–Day91 model forward and correctly counted authentication, authorization,
handler and controlled service once each while keeping durable transitions at zero.

#### Student Answer

“分别调用 1 次，Server handler 不可以直接调用 Committer。”

#### Tech Lead Review

Correct. The positive path is:

```text
authentication 1
→ authorization 1
→ capacity 1
→ handler 1
→ controlled service 1
→ candidate result
→ durable transition 0
```

The Client still converts, correlates and produces a `ProtocolObservation`; application output validation then
decides whether a separate Committer may apply a durable transition.

#### Engineering Thinking

Removing the Committer port from the handler makes the authority boundary structural rather than conventional.
An SDK callback cannot accidentally treat a protocol result as durable business truth.

#### Production Example

The Server returns candidate research documents. The Client correlates them to the intended operation, checks
tenant/provenance/policy and only then proposes a durable report update.

#### Framework Connection

The Python MCP SDK remains in the Adapter. The application owns DTOs, permits, observations, validation and
the final Committer.

#### Exercise

Review a dependency graph and remove every path from an MCP handler to a durable store or Committer. Retain a
narrow controlled service and candidate result.

## 8. Common Misconceptions

### “Transport means stdio followed by HTTP”

❌ stdio and HTTP are sequential layers of one MCP connection.
✅ They are alternative transport implementations with different identity sources.

Why it seemed reasonable: both move MCP messages.
How to remember: transport is the interface; stdio and HTTP are implementations.

### “A decoded or signed token is fully authorized”

❌ Signature or successful decoding grants Tool access.
✅ Full token validation establishes identity; current application policy grants one operation.

### “`client_id` can replace missing `sub`”

❌ The OAuth client is automatically the represented principal.
✅ `client_id` identifies the client; `sub` identifies the represented subject for this model.

### “URI tenant and Prompt role are authorization evidence”

❌ Requested target fields prove membership or role.
✅ They are untrusted request data evaluated against current authorization facts.

### “Capability admission means capacity admission”

❌ Supporting `tools` proves permission or available runtime capacity.
✅ Capability, authorization and capacity answer three separate questions.

### “503 authorization outage should be 403”

❌ The system has explicitly decided the caller lacks permission.
✅ The authorization decision could not complete; fail closed and report dependency unavailability safely.

### “Any timeout can retry with a new operation ID”

❌ A new identity makes a retry safer.
✅ It can bypass dedupe. Unknown execution requires reconciliation under the original identity.

## 9. Engineering Trade-offs

### Per-request HTTP validation versus trusted stdio process identity

- HTTP handles remote callers and needs per-request credentials, expiry and audience checks.
- stdio avoids inventing a local token protocol but shifts trust to Launcher/OS/process controls.
- Neither is universally safer; deployment boundaries decide the correct mechanism.

### Key rotation overlap

- Longer overlap reduces accidental client outages.
- Shorter overlap reduces the useful lifetime of a compromised old key.
- Production policy must coordinate token lifetime, JWKS cache refresh and emergency revocation.

### Current authorization lookup versus cached facts

- Current lookup improves revocation freshness and tenant correctness.
- Caching improves latency and availability but introduces a bounded stale-permission window.
- A team must define freshness, outage and fail-closed policy explicitly.

### 403 versus 503 on authorization dependency failure

- 403 hides infrastructure detail but incorrectly claims a completed denial.
- 503 communicates retryable service failure but must use a generic body that reveals no tenant/resource facts.
- Day92 chooses 503 for unavailable authorization infrastructure.

### Pre-auth edge protection versus information exposure

- Cheap body/source controls protect authentication infrastructure from trivial exhaustion.
- Principal/tenant quotas before authentication would trust spoofable data and leak application state.
- Keep only identity-independent controls at the edge.

## 10. Hands-on Exercises

### Exercise 1: Classify authentication failures

Question: classify missing header, malformed two-segment token, bad signature, wrong audience and missing
subject.

Think First: ask whether a credential exists, whether its structure is parseable and which validation stage
failed.

Starter Artifact: `projects/ai-agent/src/mcp_auth.py`.

Expected Output: one precise `AuthenticationOutcome`, no principal and zero authorization/handler/service
calls for every rejected case.

Explanation: precise internal taxonomy improves auditability without exposing sensitive details externally.

Follow-up Question: which cases normally map to HTTP 401?

### Exercise 2: Design an exact authorization permit

Question: authorize `ordinary-user` to call `research.lookup` for `tenant-a` and `op-report-42`.

Think First: distinguish request target from trusted membership and operation identity.

Starter Artifact: `projects/ai-agent/src/mcp_authorization.py`.

Expected Output: a permit bound to issuer, subject, operation ID, idempotency key, tenant and Tool.

Explanation: downstream service credentials cannot expand this permit.

Follow-up Question: what changes for a read-only Resource or render-only Prompt permit?

### Exercise 3: Decide retry versus reconciliation

Question: compare authorization-store outage before permit creation with timeout after possible service
execution.

Think First: can the system prove the controlled service was not called?

Starter Artifact: `projects/ai-agent/tests/test_day92_mcp_security_integration.py`.

Expected Output: safe retry with original identity for the first case; `PENDING_RECONCILIATION` for the second.

Explanation: failure position, not status text, determines side-effect safety.

Follow-up Question: why is a new operation ID dangerous after unknown execution?

## 11. Relevant Framework Connections

### MCP Python SDK

The SDK owns transport and protocol types. The security Adapter translates those inputs into application-owned
principal and request values. SDK auth types and raw credentials must not cross into handlers.

### OAuth 2.0 / JWT / JWKS

OAuth separates Client, Authorization Server and Resource Server responsibilities. JWT/JWKS can carry and
verify identity claims, but the application still owns current authorization and tenant membership. The
classroom HMAC verifier is a deterministic seam, not a production identity platform.

### Edge gateways and application capacity

An ingress or API gateway may apply body, connection and source-bucket controls before authentication. The
application applies principal/tenant quotas and Day91 capacity after security admission.

FastAPI, Playwright, Docker and unrelated frameworks are not forced into this lesson because they were not
needed to prove the MCP security contract.

## 12. AI Backend Connections

AI agents amplify confused-deputy risk because models can propose Tools, URI references and Prompt arguments.
The model does not own identity or permission. An AI Backend should mediate every proposal through current
application policy and exact permits.

For RAG and research agents:

- Resource URIs are references, not tenant evidence;
- retrieved content is still untrusted model context;
- Prompts are candidate templates, not system policy;
- machine principals require their own tenant grants;
- Server credentials cannot expand caller authority;
- candidate Tool output still needs correlation, provenance and policy validation;
- unknown external execution enters reconciliation rather than blind model-driven retry.

These controls reduce cross-tenant disclosure, prompt-driven privilege escalation and duplicated Tool side
effects without pretending that authentication alone solves AI safety.

## 13. English Interview

### Key Vocabulary

- authenticated principal
- Resource Server
- Authorization Server
- Bearer token
- issuer / audience / subject
- scope and grant
- tenant membership
- least privilege
- fail closed
- confused deputy
- enumeration resistance
- revocation and key rotation
- pending reconciliation

### Useful Expressions

- “Authentication establishes a verified principal; authorization evaluates an exact current operation.”
- “Client-provided tenant identifiers are request targets, not membership evidence.”
- “A valid token does not grant every MCP capability.”
- “Retry safety depends on proof that execution did not cross the side-effect boundary.”

### Beginner Question

What is the difference between authentication and authorization?

Strong answer: Authentication verifies who the caller is and creates a minimized principal. Authorization
checks current scope, tenant membership and exact capability permission for one operation.

### Intermediate Question

Why should an MCP handler not validate the raw Bearer token itself?

Strong answer: Credential parsing and SDK/private auth types belong at the transport Adapter. Central validation
prevents inconsistent policy and credential leakage; handlers receive only a sanitized principal-bound permit.

### Senior Question

How would you design tenant isolation and retry safety for a remote MCP Tool?

Strong answer: Validate issuer, audience, signature, time and subject; load current revocation/membership/grants;
issue an exact principal/operation/tenant/Tool permit; apply capacity before the handler; bind idempotency; and
retry only when pre-dispatch failure is proven. Possible execution becomes pending reconciliation.

### Common Weak Answer

“The JWT is valid, so the user can call the Tool.”

Why weak: it omits current grants, tenant membership, operation binding, revocation, side-effect safety and the
candidate-result/Committer boundary.

## 14. Mental Model Summary

```text
HTTP identity   = verified per-request Bearer token
stdio identity  = trusted Launcher/process context
Principal       = minimized verified identity facts
Authorization   = current scope + membership + exact grant
Tenant ID / URI = requested target, never membership proof
Capability      = protocol support, never permission
Permit          = exact least authority for one target
Duplicate       = same operation binding; no re-execution
Identity conflict = same operation, different binding; reject
Pre-dispatch failure = retry original identity after correction/recovery
Possible execution  = PENDING_RECONCILIATION
Handler         = candidate result authority only
Committer       = optional durable transition authority
```

## 15. Today's Takeaway

The most important model is that security is a chain of independently necessary proofs. A verified identity is
not permission; a requested tenant is not membership; a supported capability is not authorization; a Server
candidate is not durable success.

The largest production risk is confused-deputy cross-tenant execution hidden behind a valid token or powerful
Server credential. Exact permits, current facts and operation binding control that risk. The largest operational
trade-off is freshness versus availability: revocation and JWKS caches need explicit bounded policy rather than
silent fail-open behavior.

For interviews: explain the boundary in order, state zero downstream calls on rejection, and distinguish safe
pre-dispatch retry from unknown-outcome reconciliation.

## 16. Before Next Lesson Checklist

- [ ] I can explain HTTP versus stdio trusted identity sources.
- [ ] I can distinguish Authentication, Authorization and Tenant Isolation.
- [ ] I can name signature, issuer, audience, subject, expiration and not-before checks.
- [ ] I can explain why a valid token does not grant every Tool, Resource or Prompt.
- [ ] I can explain why payload tenant, URI, Prompt and capability are not authorization evidence.
- [ ] I can describe revocation, key rotation and fail-closed behavior.
- [ ] I can separate pre-auth edge protection from post-auth application capacity.
- [ ] I can classify 401, 403 and 503 security outcomes.
- [ ] I can distinguish duplicate, identity conflict and unknown outcome.
- [ ] I can decide safe retry versus reconciliation from side-effect evidence.
- [ ] I can explain why the handler cannot call the Committer.
- [ ] I can run the Day92 tests, seed eval and deterministic example.
- [ ] I can state what remains NOT RUN before production.
