# Day92 Classroom Record — MCP Security Boundary

This record preserves the guided classroom reasoning that produced the Day92 implementation. It is not a
replacement for the released lesson.

## Starting production scenario

```text
operation_id = op-report-42
requested_tenant_id = tenant-a
tool = research.lookup
resource = research://tenant-a/report-42
prompt = summarize-research
```

The first request carried `user_id=admin-user` in Tool arguments. The learner rejected payload identity and
kept the verified ordinary-user principal authoritative. Tenant mismatch, wrong audience, insufficient scope,
expired token, invalid signature and missing subject all stopped before handler/service execution.

## Mental-model evolution

### Transport

Initial uncertainty: stdio and HTTP sounded like two pieces of the same transport path.

Correction:

```text
transport abstraction
├── stdio: trusted Launcher / process context
└── HTTP: per-request Bearer token validation
```

Final learner model: “stdio 的可信身份来源是可信 Launcher/进程上下文，HTTP 是每请求 token validation。”

### Authentication outcome precision

The learner consistently chose the correct safe effect boundary but initially used informal names:

- `waiting_nbf` → `NOT_YET_VALID`;
- `wrong_sign` → `INVALID_SIGNATURE`;
- “missing authentication” for a token missing `sub` → `MISSING_SUBJECT`.

The durable model is to identify the exact validation stage without exposing raw credentials.

### Authorization and tenant isolation

The learner correctly concluded:

- audience mismatch, scope denial and tenant mismatch call handler/service zero times;
- signed `role=admin` cannot replace exact scope, membership and Tool grant;
- Resource URI is a target, not membership evidence;
- Prompt arguments cannot expand authority or trigger Tool/Resource calls;
- a machine principal cannot inherit a human principal's tenant membership;
- current membership revocation applies even while a stdio process remains alive.

### Capability, capacity and edge protection

The learner briefly answered with “capability admission” when discussing post-auth rate limiting. Review
separated:

```text
capability = protocol feature support
authorization = exact permission
capacity = runtime execution availability
```

Cheap body/source protection may run before authentication. Principal/tenant quota and application capacity
run after authentication and authorization.

### HTTP failure semantics

The learner correctly mapped invalid identity to 401 and explicit permission denial to 403. They first chose
403 for authorization-service outage; review corrected this classroom policy to 503 because the authorization
decision could not complete. The path still fails closed with zero downstream calls and a generic body.

### Operation identity and retry

The learner identified the same operation under a different principal as `IDENTITY_CONFLICT`. They also
distinguished:

```text
proven pre-dispatch failure → retry original operation ID + idempotency key
possible service execution → PENDING_RECONCILIATION; no blind retry
```

The key final statement was: retry safety depends on whether the system can prove the request did not cross a
possible side-effect boundary, not on the HTTP status code alone.

### Candidate and Committer

On the positive path the learner counted authentication, authorization, handler and service once each, while
keeping Committer calls at zero. Their independent synthesis correctly retained:

```text
Server candidate
→ Client correlation
→ ProtocolObservation
→ output validation
→ Committer
→ optional durable transition
```

## Final independent synthesis assessment

The learner independently explained HTTP/stdin identity, Authentication/Authorization/Tenant Isolation,
untrusted payload/URI/Prompt/capability data, safe retry versus reconciliation and the no-Committer handler
boundary. Assessment: pass with minor terminology corrections — the HTTP identity source is a successfully
verified Bearer token, and payload/URI/Prompt/capability values are not all identity claims.

## Classroom evidence

- Day92 focused tests: 35/35;
- Day92 seed: 16/16;
- combined dependency-free and SDK integration tests: 656/656;
- deterministic example, compile, JSON/JSONL and diff checks: PASS;
- real Authorization Server/JWKS and remote authenticated HTTP deployment: NOT RUN;
- production readiness: `MORE_EVIDENCE_NEEDED`.
