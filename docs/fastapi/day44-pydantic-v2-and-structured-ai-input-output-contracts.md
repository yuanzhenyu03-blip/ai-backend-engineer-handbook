# Lesson 44 — Pydantic v2 and Structured AI Input/Output Contracts

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day43 — AI Backend Product Contract and FastAPI Request Lifecycle

Previous Lesson: [Day43 — AI Backend Product Contract and FastAPI Request Lifecycle](day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md)

Next Lesson: [Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters](day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md)

Phase: Phase 4 — Production AI API Engineering

Engineering Artifact: The Day44 Pydantic v2 contracts (`projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md`) with runnable code [`day44_pydantic_contracts.py`](../../projects/ai-backend-data-layer/api/day44_pydantic_contracts.py) and tests [`test_day44_pydantic_contracts.py`](../../projects/ai-backend-data-layer/api/test_day44_pydantic_contracts.py) — strict `MaxTokens`/`Confidence`, the request discriminated union, `Citation`/`StructuredAIResult`, status-discriminated public responses, the public error envelope, and the `validate_provider_output_before_completion` gate. Real Pydantic v2 tests were executed (24 passed; Pydantic 2.5.0, pytest 7.4.3); FastAPI/PostgreSQL/Provider/integration/production NOT RUN — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

FastAPI Cheat Sheet: [cheat_sheets/fastapi.md](../../cheat_sheets/fastapi.md)

FastAPI Interview: [interview/fastapi.md](../../interview/fastapi.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises + running the tests: 110-140 minutes
Hands-on model/validation design: 90-120 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Distinguish JSON-valid, Pydantic-valid, authenticated, authorized, and committed-durable-truth as five separate boundaries, and place Pydantic on exactly one of them.
2. Design request models where `tenant_id` is trusted authentication context (not a body field) and `extra="forbid"` rejects undeclared input, including a client-supplied `job_status`.
3. Explain why Pydantic cannot detect cross-tenant upload ownership, and keep the `(tenant_id, idempotency_key)` uniqueness constraint as the concurrency authority.
4. Separate persistence, internal, and public API representations, and design a minimal allowlisted `JobStatusResponse`.
5. Design a stable public error envelope (`error.code`/`message`/`field_errors?`/`request_id?`) and explain why a human-readable detail is insufficient for client branching.
6. Treat Provider output as fully untrusted input, validate it as `StructuredAIResult`, and explain why citation-shape validation is not grounding.
7. Choose deliberate, field-specific strict types (`max_tokens`, `confidence`) instead of global strictness or implicit coercion.
8. Encode cross-field invariants with an after-model validator or a discriminated union, and encode legal response states with a status-discriminated union.
9. Distinguish `model_validate`, `model_validate_json`, `model_dump`, and `model_construct`, and never use `model_construct` on untrusted input.
10. Write a negative test that asserts both a `ValidationError` and the absence of the completion side effect.
11. Contain, roll back, classify, repair, and verify a `model_construct()` production incident without treating code rollback as database rollback.

---

# Why This Matters

Day43 wrote the AI Job HTTP product contract in prose; Day44 makes it **executable**. The central risk this
lesson removes is the quiet assumption that "the JSON parsed" means "the request is safe." A syntactically
valid JSON object can carry the wrong fields, the wrong types, a **claimed** tenant ID, client-controlled
lifecycle state, or undeclared debug input — and every one of those is an attack or a bug waiting for an
endpoint that trusts structure it never declared.

The scenario stays concrete. A production payload arrives with `tenant_id`, `upload_session_id`, `task_type`,
`max_tokens` as a **string**, a client-supplied `job_status`, and an `unexpected_debug` field. Accept the
`tenant_id` from the body and you have a cross-tenant authorization hole; coerce `"2000"` into `2000` and you
silently change a billing-sensitive parameter; ignore the extra fields and you let clients expand your contract
without review. Then the Provider — also untrusted — returns legal JSON with `confidence: "very sure"`,
citations as one string, and its own `job_status: succeeded`, and if you skip validation with
`model_construct()` you let an external model mark a Job succeeded. That exact mistake is the day's incident: a
bad release using `model_construct()` marked 37 Jobs succeeded.

So Day44 draws four boundaries as **types**: client request, public response, public error, and Provider output —
and keeps each honest about what it proves. Pydantic proves declared structure; it does not prove tenant
authorization or a database commit. That separation is the whole lesson.

Unusually, Day44 has **real runtime evidence**: the Pydantic v2 models and 24 pytest cases were executed
— the repository artifact (tightened per code review: a restricted `output_schema`, UUID `upload_session_id`/
`job_id`, an `AnyHttpUrl` citation, a strict required `MaxTokens` bounded `1..8000`, and a shared summary contract (`min_length=1`, `max_length=10_000`) that the public result reuses) has **24 pytest cases**
that were executed here on Python 3.10.12 / Pydantic 2.5.0 / pytest 7.4.3 → **24 passed** (the classroom's
earlier artifact had 11 tests). But the completion target is an **in-memory callback, not
PostgreSQL** — and FastAPI, authentication/authorization, PostgreSQL, SQLAlchemy/Alembic, a real Provider SDK,
Relay/Worker/Redis/Object Storage, integration, and production are all **NOT RUN**. Those are later lessons.

---

# Roadmap Position

```text
Day42 durable data ownership + failure contract
Day43 HTTP product contract + request lifecycle
Day44 executable Pydantic v2 boundary contracts   <-- you are here
Day45 DI, lifespan, configuration, Provider adapters
Day46 SQLAlchemy 2.0 persistence mapping (no ORM/public-model merge)
```

Knowledge continuity:

```text
Previous knowledge
  Day43 commit-before-202, trusted tenant context, public-field allowlist, idempotency, durable-background
        lifecycle, rollback -- all stated in prose (Pydantic deferred to Day44)
        |
        v
Current lesson
  encode the Day43 public contract as TYPES and validation rules: request/response/error models + untrusted
  Provider output + the boundary ladder + validation-before-side-effects, with real Pydantic tests
        |
        v
Future production usage
  Day45 wires these models through DI + a Provider-adapter seam; Day46 maps durable state with SQLAlchemy
  WITHOUT merging ORM and public Pydantic models; Day47 real async sessions/transactions; Day53 real Provider
  SDK parsing; Day57 contract/integration/failure-injection tests; Day58 runtime observability
```

Day44 does **not** change data ownership — it encodes the Day43 public contract as types. It does not implement
Day45 DI/lifespan/configuration, Day46 SQLAlchemy, Day47 transactions, Day53 real Provider integration, or later
production validation.

---

# Lesson Map

```text
1. JSON-valid != contract-valid   -> parsing proves bytes; validation proves declared structure
2. Trusted tenant vs request data  -> tenant_id is auth context; extra="forbid"; job_status is server-owned
3. Structure vs authz vs truth      -> Pydantic can't see ownership; the DB constraint + tx is the authority
4. Separate request/response models -> allowlisted JobStatusResponse; not the database image
5. Stable public error shape        -> code/message/field_errors?/request_id?; don't branch on prose
6. Provider output is untrusted      -> StructuredAIResult; shape != grounding; no Provider-owned job_status
7. Strict, field-specific types      -> MaxTokens/Confidence strict; no global strictness; adapters for conversion
8. Cross-field + response invariants  -> after-validator / discriminated unions; legal states only
9. Validation entry points           -> model_validate(_json) for untrusted; never model_construct
10. Validate before side effects       -> assert rejection AND no completion call
11. model_construct() incident          -> contain / roll back code / classify / audited repair / verify
```

---

# Core Mental Model

```text
JSON-valid -> Pydantic-valid structure -> authenticated identity -> authorized resource/tenant ->
application invariants -> PostgreSQL constraint + atomic transaction -> committed durable business truth.

Pydantic occupies ONE rung: declared structure. It cannot know an upload belongs to the authenticated tenant,
and it cannot make a commit durable.

request  = discriminated union on task_type; tenant_id is TRUSTED CONTEXT not a body field; extra="forbid".
provider = fully untrusted input -> validate as StructuredAIResult (NO Provider-owned job_status); shape != grounding.
response = allowlisted + status-discriminated (queued/running have no result; succeeded needs result; failed needs failure);
           a failed Job is a successfully READ resource -> HTTP 200 + status "failed".
error    = PublicErrorResponse{code,message,field_errors?,request_id?}; HTTP status = the class; never leak internals.
entry    = model_validate / model_validate_json validate untrusted; model_dump serializes validated; model_construct SKIPS
           validation and must NEVER touch untrusted input.
gate     = validate BEFORE side effects; a negative test asserts BOTH a ValidationError AND no completion call.
incident = roll back the CODE for future traffic; reconcile committed facts separately (code rollback != DB rollback).
```

---

# Main Concepts

## Concept 1: JSON parsing is not contract validation (and tenant is not a body field)

### Tech Lead Question

A production payload has `tenant_id`, `upload_session_id`, `task_type`, `max_tokens` as a string, a
client-supplied `job_status`, and `unexpected_debug`. Which client fields do you allow?

### Student Thinking

The student sorted the fields into allowed vs rejected and immediately connected acceptance to the
tenant-scoped idempotency uniqueness from Day43.

### Student Answer

> "我会允许tenant_id、upload_session_id，task_type，拒绝max_token、job_status、unexpected_debug,commit-before-202 事务，需要唯一性约束unique(tenant_id,idepmotency  key)缺少稳定的幂等键"

### Tech Lead Review

Strong instincts — rejecting `job_status` and `unexpected_debug`, tying acceptance to
`UNIQUE (tenant_id, idempotency_key)`, and noticing the payload lacks a stable idempotency key are all correct.
Two corrections. First, **`tenant_id` must not be accepted from the request body** — it comes from **trusted
authentication context**; a claimed tenant ID in the body is a cross-tenant authorization risk. Second,
**`max_tokens` need not be rejected outright**: it can be a legitimate product parameter **when the product
supports it**, but then it needs **strict** integer + bounded-range validation; if the product does not expose
it, reject it entirely. JSON parsing proves only that the bytes are valid JSON; Pydantic validation proves only
that declared structure, types, ranges, literals, and model rules pass. Use `extra="forbid"` so undeclared
input is **rejected**, not silently ignored — and the stable idempotency key can arrive as an **HTTP header**,
whose shape Pydantic may validate while `UNIQUE (tenant_id, idempotency_key)` stays the concurrency authority.

### Engineering Thinking

Validation is about what you **declared**, not what parsed. Identity (tenant) is established by authentication,
never by a value the client can type into a body.

## Concept 2: Pydantic cannot detect cross-tenant upload ownership

### Tech Lead Question

Can a Pydantic model tell you that an `upload_session_id` belongs to the authenticated tenant?

### Student Answer

> "不能发现"

### Tech Lead Review

Correct. Pydantic validates **structure**; it has no idea whether an upload belongs to the caller. That is an
**authorization** question answered by the application boundary, which must query using **both** the trusted
tenant ID and the upload-session ID and verify a usable state **before** acceptance. Structural validity,
authorization, and durable truth are three different rungs: Pydantic checks the first, an authorization query
the second, and a PostgreSQL constraint + transaction the third.

### Engineering Thinking

A model that passes tells you the request is well-formed, not that the caller may do what it asks. Never let a
green validation stand in for an ownership check.

## Concept 3: Separate request and public response models

### Tech Lead Question

For `GET /jobs/{job_id}`, do you return the database image? What is the minimal public response?

### Student Thinking

The student chose an independent response model rather than serializing the database row.

### Student Answer

> "返回job_id、job_status。建立独立的 JobStatusResponse，避免直接返回数据库映像"

### Tech Lead Review

Exactly the right move. The minimal public response is `job_id` + `job_status`, expressed by an **independent
`JobStatusResponse`** — not the database image. This keeps three representations separate: **persistence**,
**internal/domain**, and **public API**. Internal fields — lease token, fencing generation, raw Provider
metadata, raw Object Storage key, Outbox ID, unreviewed Attempt fields — must **never** become public merely
because an ORM/database object gained a field. An allowlisted response model is the firewall between schema
evolution and your public contract.

### Engineering Thinking

Returning the database image couples your public API to your storage schema; a dedicated response model lets
each evolve without leaking or breaking the other.

## Concept 4: A stable public error shape

### Tech Lead Question

What does the public error body look like?

### Student Thinking

The student's first proposal was a minimal error/detail pair.

### Student Answer

> "erro,detail"

### Tech Lead Review

A human-readable `detail` is **insufficient** for a client program to branch on. The stable public envelope is
`error.code` (stable machine semantics a client may branch on), `error.message` (safe public text), optional
`field_errors`, and an optional `request_id` for correlation. The **HTTP status** remains the error **class**;
`error.code` carries the stable machine meaning. And never expose SQL, table details, tracebacks, credentials,
raw Provider errors, raw storage keys, or cross-tenant existence.

### Engineering Thinking

Clients automate against **codes**, not prose. Mutable human text is for humans; a stable code is the API
contract a program depends on.

## Concept 5: Provider output is untrusted input, not just untrusted status

### Tech Lead Question

A Provider returns legal JSON with `confidence: "very sure"`, citations as one string, and `job_status:
succeeded`. What is wrong?

### Student Thinking

The student spotted the Provider-controlled `job_status` and rejected it.

### Student Answer

> "里面包含了job_status，不能"

### Tech Lead Review

Right that the Provider **cannot** set `job_status` — the Provider does not own the durable Job lifecycle. But
the problem is bigger: the output also has an **invalid `confidence`** (`"very sure"` is not a `[0,1]` float)
and an **invalid citations shape** (one string, not a list of citation objects). **Provider output is fully
untrusted input**, not just untrusted lifecycle state. Parse and validate it as a `StructuredAIResult`
(`extra="forbid"`, so a Provider-supplied `job_status` is rejected), and only then may application code perform
**guarded completion** after its other checks. And a limit to keep honest: Pydantic can validate citation
**structure** and URL **shape** (the artifact uses `AnyHttpUrl`, which requires a scheme **and** a host, so a
bare `https://` is rejected) — but URL-shape validation is **not** source authorization, **not** SSRF
protection, and **not** grounding/source verification; it cannot prove the citations are **true, grounded, or
trustworthy**.

### Engineering Thinking

An external model is an untrusted client. Validate its whole output, and never confuse "the citations are
well-formed" with "the citations are real."

## Concept 6: Strict, deliberate, field-specific validation

### Tech Lead Question

For `max_tokens` and `confidence`, strict types or coercive ones?

### Student Answer

> "严格类型"

### Tech Lead Review

Correct — strict types for these. The lesson rejects accidental conversion such as `"2000"` → `2000`, because
`max_tokens` is billing-sensitive and a silent coercion is a silent cost/audit change. But strictness should be
**deliberate and field-specific** where ambiguity, billing, or audit risk exists — do **not** flip on **global**
strictness without considering values that JSON naturally represents as strings (UUIDs, timestamps). If
compatibility conversion is genuinely required, it belongs in an **explicit, tested adapter**, not implicit
core-model guessing. In the Day44 artifact the concrete contract is fixed: `MaxTokens = Annotated[StrictInt,
Field(ge=1, le=8_000)]`, **required** — so `"2000"` (a string) is rejected, `8001` (out of range) is rejected,
and a missing value is rejected. `Confidence` is a strict `[0,1]` float.

### Engineering Thinking

Strictness is a scalpel, not a switch. Be strict exactly where a wrong-but-coercible value is dangerous, and
make any needed conversion explicit and tested.

## Concept 7: Cross-field invariants and discriminated unions

### Tech Lead Question

`extract_structured` requires `output_schema`; `summarize` forbids it. How do you encode that, and how do you
verify summarize rejects `output_schema`?

### Student Thinking

The student did not know the Pydantic mechanism for the conditional rule and received direct teaching, then
reasoned about the summarize case.

### Student Answer

> (cross-field mechanism) "不知道"

> (verify summarize rejects `output_schema`) "task_type是summarize里面没有output_schema"

### Tech Lead Review

"I don't know" is an honest start, and the second answer is the right observation. Two mechanisms fit. For a
small invariant on one model, `model_validator(mode="after")` validates a completed model. But when task types
represent **genuinely different product contracts**, prefer a **discriminated union**: `task_type` selects
`SummarizeRequest` or `ExtractStructuredRequest`, and `extra="forbid"` rejects invalid combinations. Concretely
— `SummarizeRequest` simply does not declare `output_schema`, so `extra="forbid"` rejects it if supplied; and
`ExtractStructuredRequest` **requires** a non-empty `output_schema`. In the artifact that `output_schema` is a
**restricted, closed type map** — `dict[str, Literal["string", "number", "boolean"]]` with `min_length=1` — so
`{"company": 1}` (a non-type value) and `{"company": "integer"}` (an unsupported type name) are rejected, and
`{}` is rejected as empty. This is deliberately **not** a full JSON Schema engine (out of Day44 scope). Request
identifiers use the Day31 durable model: `upload_session_id` is a **UUID** (and public `job_id`s are UUIDs), so
a malformed `"u1"` is rejected at the boundary. That is exactly what the runnable artifact and its tests do.

### Engineering Thinking

Model distinct product variants as distinct types, not as one model with nullable fields and hand-written
`if`s. A discriminated union makes the illegal combinations unrepresentable and generates a clearer schema.

## Concept 8: Response state invariants

### Tech Lead Question

Should one response model with many nullable fields represent every Job state?

### Student Thinking

The student correctly preferred different models, but initially stated that a queued Job should require a
result.

### Student Answer

> "建立不同模型。success强制erro不存在，queued强制result存在。fail强制error存在"

### Tech Lead Review

Preferring different models is right — one model with many nullable fields permits **nonsensical** states. The
correction is the queued case: **queued/running must NOT contain a terminal result** (or a failure);
**succeeded requires a validated result** (failure absent); **failed requires a public business-failure
object** (result absent). So the student's "queued 强制 result 存在" is inverted — queued forbids a result. Encode
this as a **status-discriminated union** so each state has only its legal fields. And note: a **failed Job is a
successfully read resource** — `GET` returns **HTTP 200** + business status `failed`; the `PublicErrorResponse`
envelope is for an HTTP/request failure, while a `FailedJobResponse.failure` is **business** state.

### Engineering Thinking

Make illegal states unrepresentable. If "queued with a result" cannot be constructed, no bug can ever emit it.

## Concept 9: Validation entry points — never `model_construct()` on untrusted input

### Tech Lead Question

Which entry point validates untrusted input, and what does `model_construct()` do?

### Student Thinking

The student did not initially know `model_construct()` semantics, then correctly chose the validating entry
point.

### Student Answer

> (`model_construct()` behaviour) "不知道"

> (correct entry point) "model_validate()，因为可以进行验证，model_construct会跳过验证环节"

### Tech Lead Review

Correct: `model_construct()` **bypasses** validation, validators, normal nested conversion, and
`extra="forbid"` — so it must **never** touch untrusted client or Provider input. Use `model_validate()` for an
untrusted Python object and `model_validate_json()` for untrusted raw JSON; `model_dump()` serializes an
**already-validated** model; and `TypeAdapter` validates a discriminated union. The student's reasoning —
`model_construct` skips the validation step — is exactly why it is dangerous at a boundary.

### Engineering Thinking

`model_construct()` is a trusted-data/performance tool, not a boundary tool. At an untrusted boundary, skipping
validation is skipping the contract.

## Concept 10: Validation must precede side effects (and the negative test proves it)

### Tech Lead Question

Design the first negative test for invalid Provider output. Why is asserting a `ValidationError` not enough?

### Student Thinking

The student did not initially know the negative-test design, but reasoned clearly about what an empty
completion-call list proves.

### Student Answer

> (first negative test design) "不知道"

> (why assert no completion call) "最终结果检查completion_calls如果发现没有数据就说明确实拦截了，如果有数据就说明拦截失效了"

### Tech Lead Review

The reasoning is exactly right and is the heart of the test. The first negative test feeds **invalid Provider
output** (wrong types + an extra `job_status`) and asserts **both**: that a `ValidationError` occurs **and**
that the completion callback was **never called** (the `completion_calls` list is empty). Checking only for an
exception is insufficient, because a **dangerous implementation might perform the side effect before
validating** — the empty list is what proves the guard actually blocked the fake result. The runnable artifact's
`validate_provider_output_before_completion()` validates first and calls the callback only on success, and the
test asserts the empty list.

### Engineering Thinking

Test the *effect*, not just the *signal*. "It raised" does not prove "it did nothing dangerous first"; the
absence of the side effect does.

## Concept 11: The `model_construct()` production incident

### Tech Lead Question

A bad release used `model_construct()` for untrusted Provider output and 37 Jobs were marked `succeeded`.
Contain, roll back, repair, and prevent recurrence.

### Student Thinking

The student produced a strong containment/evidence/reconciliation direction, with one belief to sharpen (that
database records can never be modified).

### Student Answer

> "不能直接修改数据库记录，先暂停provider继续使用model_construct继续让provider非法输出，回滚版本，可控范围内，根据请求ID与其他数据库事实对37job进行筛选，将非法注入的succeeded的job，进行修复"

### Tech Lead Review

The containment shape is right: **disable the affected Provider-completion path**, route traffic away from the
bad release, **roll back the faulty application release** (restore `model_validate()`/`model_validate_json()`),
and **classify** the 37 Jobs by request ID and other durable facts rather than assuming identical damage. The
belief to correct: "cannot directly modify database records" is too absolute — **unreviewed ad hoc** changes are
forbidden, but incorrect **committed** facts may require an explicit, **idempotent, guarded, audited** data-repair
operation. Also preserve evidence (release version, job/attempt/request/trace IDs, validation failures,
original result references, audit history), add **negative regression tests** proving invalid output never
reaches completion, reconcile **Job/Attempt/Event/Result Artifact**, and **never** blindly return all Jobs to
queued, blindly replay paid Provider work, delete audit evidence, fabricate valid results, or treat **code
rollback as database-history rollback**.

### Engineering Thinking

Code rollback protects **future** executions; audited reconciliation repairs **already-committed** facts. They
are separate operations, and conflating them either leaves bad data in place or destroys the evidence you need
to fix it.

## Concept 12: The final synthesis

### Tech Lead Question

Put it together: what does Pydantic prove, and what does it not?

### Student Answer

Final Chinese mental model (student):

> "Pydantic能检查客户端输入，也可以验证公开响应和 Provider 输出，只是结构验证，不负责证明租户授权或数据库提交。客户端请求以及Provider 输出可以通过Pydantic经过验证，授权是可以确认job属于哪个租户，数据库事务在经过Pydantic验证后可以做原子事务提交。当出现事故时，回滚Pydantic版本不能保证数据库事实也回滚"

### Tech Lead Review

This is the lesson. Pydantic validates client input, public responses, and Provider output — **structure
only**; it does **not** prove tenant authorization or a database commit. Authorization determines
resource/tenant permission; the database transaction creates durable atomic truth **after** validation; and
rolling back the Pydantic/application code does **not** roll back committed database facts. The full ladder:
JSON-valid → Pydantic-valid → authenticated → authorized → application invariants → PostgreSQL constraint +
atomic transaction → committed durable truth.

### Engineering Thinking

Each boundary earns exactly one guarantee. Keeping them separate is what lets you reason about — and safely
recover from — a failure at any single rung.

---

# Common Misconceptions

Client-supplied tenant ID

❌ "Accept `tenant_id` from the request body."
✅ Tenant ID comes from trusted authentication context; a claimed tenant ID in the body is a cross-tenant
authorization risk. Pydantic validates request intent; authentication supplies identity; authorization
verifies ownership.

Why beginners think this: the tenant is "part of the request."
How to remember: identity is authenticated, not typed into a body.

Reject `max_tokens` entirely

❌ "`max_tokens` is client-controlled, so reject it."
✅ It can be a legitimate product parameter when supported — with strict integer + bounded-range validation. If
the product does not expose it, reject it entirely.

Why beginners think this: any numeric knob feels risky.
How to remember: support it strictly, or reject it — not "reject because numeric."

Error = `erro, detail`

❌ "A generic error/detail pair is enough."
✅ Add a stable machine `code`, a safe `message`, optional `field_errors`, and a `request_id`. Clients must not
branch on mutable prose.

Why beginners think this: a message "explains" the error.
How to remember: programs branch on codes, humans read messages.

Provider problem is only `job_status`

❌ "The only issue is the Provider setting `job_status`."
✅ Provider output is fully untrusted: it also had an invalid `confidence` and citations shape. Validate the
whole `StructuredAIResult`.

Why beginners think this: the lifecycle field is the scary one.
How to remember: an external model is an untrusted client, top to bottom.

Queued requires a result

❌ "A queued Job should include its result."
✅ Queued/running must have no terminal result or failure; succeeded requires a result; failed requires a
failure. Encode with a status-discriminated union.

Why beginners think this: one model with nullable fields blurs the states.
How to remember: make illegal states unrepresentable.

`model_construct()` is fine

❌ "Use `model_construct()` for speed on untrusted input."
✅ It bypasses validation, validators, nested conversion, and `extra="forbid"`. Untrusted input must use
`model_validate()` / `model_validate_json()`.

Why beginners think this: it "builds the model."
How to remember: construct = trusted only; validate = untrusted.

A negative test only checks the exception

❌ "Assert a `ValidationError` and you're done."
✅ Also assert the completion side effect did not happen — a dangerous impl could complete before validating.

Why beginners think this: the error is the visible outcome.
How to remember: test the effect (no completion), not only the signal.

Code rollback rolls back the database

❌ "Roll back the release and the 37 bad Jobs are fixed."
✅ Code rollback protects future executions; committed facts need a separate idempotent, guarded, audited
repair. Code rollback ≠ database-history rollback.

Why beginners think this: rollback sounds total.
How to remember: roll back code for the future; reconcile facts for the past.

Authentication = authorization

❌ "Authorized data is authentic because the server authenticated it."
✅ Authentication proves identity; authorization checks permission and tenant/resource ownership. They are
different boundaries.

Why beginners think this: both gate the request.
How to remember: who you are ≠ what you may do.

---

# Engineering Trade-offs

## Strict types vs compatibility

Strict types expose client/Provider drift early but reject legacy string encodings; a deliberate, tested
adapter is preferable to implicit coercion. Be strict where billing/audit/ambiguity risk exists; convert
explicitly elsewhere.

## `extra="forbid"` vs forward tolerance

`extra="forbid"` blocks silent contract expansion and injection but requires explicit versioning/rollout for
new client fields; forward tolerance is convenient but lets clients grow your contract unreviewed. For a
security boundary, forbid and version deliberately.

## One nullable response model vs discriminated state models

One model is shorter but permits invalid state combinations; discriminated state models cost more code but give
stronger runtime and generated-schema guarantees. For public Job states, pay for the discriminated models.

## `model_validator` vs discriminated union

An after-model validator suits a small same-model invariant; a discriminated union suits distinct product
variants and produces clearer schemas. Match the tool to whether the variants are one contract or many.

## Separate API and persistence models vs one shared model

Separate models cost mapping maintenance but prevent ORM evolution from leaking internal fields or breaking
public compatibility; one shared model is less code but couples storage to the public contract. Keep them
separate (Day46 maps them without merging).

## Validation performance vs `model_construct()`

Skipping validation is unacceptable for untrusted boundaries; do not use an unmeasured optimization to remove a
correctness control. Reserve `model_construct()` for trusted, hot, already-validated internal paths.

---

# Hands-on Exercises

These exercises map to the runnable artifact and its tests, which **were executed** (Pydantic 2.5.0, pytest 7.4.3
→ **24 passed**; install via `requirements.txt`). The completion target is an in-memory callback, **not**
PostgreSQL; FastAPI, authentication/
authorization, PostgreSQL, SQLAlchemy, a real Provider SDK, and integration are **NOT RUN**.

Run the tests:

```text
cd projects/ai-backend-data-layer/api
python3 -m py_compile day44_pydantic_contracts.py test_day44_pydantic_contracts.py
python3 -m pytest -q test_day44_pydantic_contracts.py
```

### Exercise 1: Classify the client fields

Question: for `tenant_id`, `upload_session_id`, `task_type`, `max_tokens`, `job_status`, `unexpected_debug`,
mark allowed / server-owned / trusted-context / rejected.

Expected Output: `tenant_id` = trusted auth context (not a body field); `upload_session_id`/`task_type` =
allowed client intent; `max_tokens` = required, strict int, bounded `1..8000` (reject `"2000"`, `8001`, and a missing value); `job_status` =
server-owned (rejected from body); `unexpected_debug` = rejected by `extra="forbid"`.

Follow-up: why is accepting a body `tenant_id` a cross-tenant risk?

### Exercise 2: Why Pydantic can't detect cross-tenant ownership

Question: explain, in one sentence, why a green validation does not prove upload ownership.

Expected Output: Pydantic validates declared structure only; ownership is an authorization query using the
trusted tenant ID + upload-session ID against durable state.

Follow-up: which rung owns idempotency uniqueness? (The PostgreSQL constraint + transaction.)

### Exercise 3: Minimal public `JobStatusResponse`

Question: design the minimal allowlisted response and say what must never appear.

Expected Output: `job_id` + `job_status`; never lease token, fencing generation, raw Provider metadata, raw
Object Storage key, Outbox ID, or unreviewed Attempt fields.

Follow-up: why not return the database image?

### Exercise 4: Stable public error envelope

Question: design the error body.

Expected Output: `error.code` (stable machine semantics), `error.message` (safe text), optional `field_errors`,
optional `request_id`; HTTP status is the class; never leak SQL/tracebacks/credentials/raw Provider errors/
cross-tenant existence.

Follow-up: why is a human-readable `detail` insufficient?

### Exercise 5: Diagnose invalid Provider JSON

Question: `{"confidence": "very sure", "citations": "one-source", "job_status": "succeeded", ...}` is valid
JSON. What fails contract validation?

Expected Output: Provider-owned `job_status` (rejected), non-`[0,1]`-float `confidence`, and citations shape
(string, not a list of citation objects). Provider output is fully untrusted.

Follow-up: does a valid citation URL prove the citation is true? (No — shape is not grounding.)

### Exercise 6: Strict vs coercive for `max_tokens` and `confidence`

Question: choose and justify.

Expected Output: strict for both; reject `"2000"` → `2000` (billing/audit) and `"very sure"`; no global
strictness; conversions in a tested adapter.

Follow-up: which JSON-as-string values would global strictness wrongly reject? (UUIDs, timestamps.)

### Exercise 7: Encode the `output_schema` rule

Question: `extract_structured` requires `output_schema`; `summarize` forbids it. Encode it.

Expected Output: a discriminated union on `task_type` — `SummarizeRequest` omits `output_schema` (`extra="forbid"`
rejects it) and `ExtractStructuredRequest` requires a non-empty one; or an after-model validator for a small
invariant.

Follow-up: verify summarize rejects `output_schema` in a test.

### Exercise 8: Status-discriminated response states

Question: encode queued/running/succeeded/failed.

Expected Output: queued/running have no result/failure; succeeded requires a result; failed requires a failure;
a failed Job is a successfully read resource (HTTP 200 + status `failed`).

Follow-up: how is `FailedJobResponse.failure` different from `PublicErrorResponse`?

### Exercise 9: Validation entry points

Question: distinguish `model_validate`, `model_validate_json`, `model_dump`, `model_construct`.

Expected Output: validate untrusted object / validate untrusted JSON / serialize a validated model / **skip
validation** (trusted only, never untrusted).

Follow-up: why is `model_construct` dangerous at a boundary?

### Exercise 10: Negative test that blocks the side effect

Question: design the first negative Provider-output test.

Expected Output: assert a `ValidationError` **and** that the completion callback was never called (empty
`completion_calls`). Maps to `test_invalid_provider_output_blocks_completion`.

Follow-up: why isn't asserting the exception alone enough?

### Exercise 11: The 37-Job `model_construct()` incident

Question: contain, roll back, classify, repair, verify.

Expected Output: disable the Provider-completion path + route away from the bad release; preserve evidence;
roll back the release and restore validation; add negative regression tests; classify by release/time/attempt/
output; idempotent audited repair; reconcile Job/Attempt/Event/Result Artifact; never blindly requeue, replay
paid work, delete audit, fabricate results, or treat code rollback as DB rollback. Maps to the artifact's
incident section.

Follow-up: why is code rollback not database rollback?

---

# Relevant Framework Connections

## Pydantic v2

The lesson's core: `BaseModel`, `ConfigDict(extra="forbid")`, `Field` (strict + bounds), `Literal`,
discriminated unions, `model_validator(mode="after")`, `TypeAdapter`, `model_validate`, `model_validate_json`,
`model_construct`, and `model_dump`. Watch that untrusted input uses a validating entry point, that variants are
modeled as discriminated unions, and that strictness is deliberate and field-specific.

## FastAPI

FastAPI is where these models become request validation, public response allowlists, and HTTP error shapes, and
where a **successfully read failed Job** (`200` + status `failed`) is distinguished from an HTTP failure. No
FastAPI app or HTTP runtime was executed in Day44 — DI/lifespan wiring is Day45.

## PostgreSQL

PostgreSQL remains the authority for tenant-scoped idempotency uniqueness, the durable commit, and the audited
repair of committed facts — none of which Pydantic can provide. No PostgreSQL runtime was executed; SQLAlchemy
mapping is Day46 and must not merge ORM models with public Pydantic models.

---

# AI Backend Connections

## Provider output is untrusted external data

Even legal JSON from a Provider is untrusted: validate the whole `StructuredAIResult` before any result
persistence or guarded completion, and reject a Provider-owned `job_status` — the Provider cannot own the Job
lifecycle.

## Strict token/confidence contracts prevent silent drift

Strict `max_tokens` and `confidence` contracts stop silent cost and audit drift (a coerced `"2000"` or a
free-text `"very sure"` would quietly corrupt billing/quality signals). Structured output must validate before
persistence and completion.

## Citation shape is not grounding

Validating citation structure and URL shape is **not** source verification or grounding — a well-formed
citation can still be fabricated. Grounding/verification is a separate concern (later lessons).

## Invalid output must not create a succeeded Job

The whole incident exists because an unvalidated Provider result marked Jobs succeeded. Validation-before-side-
effects, and negative tests that assert no completion on invalid output, are what prevent an external model from
writing false success — and recovery must avoid blind replay of paid Provider calls.

---
# English Interview

## Key Vocabulary

Pydantic v2, `BaseModel`, `ConfigDict(extra="forbid")`, `Field` (strict/bounds), `Literal`, discriminated
union, `model_validator`, `TypeAdapter`, `model_validate`, `model_validate_json`, `model_dump`,
`model_construct`, structural validation, authentication vs authorization, committed durable truth, public
error envelope, validation-before-side-effects, negative test.

## Useful Expressions

"Pydantic validates structure, not authorization or a database commit." · "Tenant ID is trusted context, not a
body field." · "Provider output is untrusted input." · "Never `model_construct()` untrusted input." · "Test the
effect, not just the exception." · "Code rollback is not database rollback."

## Beginner Question — What is the purpose of a Pydantic model at an API boundary?

Student answer (verbatim):

> "the purpose is check client illegal enter"

Strong spoken answer:

> "The purpose of a Pydantic model is to validate and serialize data at a system boundary. It ensures that
> request, response, and provider data follow the declared types and constraints before the application uses
> them. However, it does not replace authorization or database constraints."

Assessment: the student had the core idea (check client input); the strong answer adds serialization, the
response/provider boundaries, and the "does not replace authorization or DB constraints" limit.

## Intermediate Question — Difference between syntactically valid JSON, Pydantic-valid data, authorized data, and committed business state?

Student answer (verbatim):

> "valid JSON is not equal Pydantic-valid data,Pydantic-valid data follow the declared types and constraints.committed business state is the durable database truth.authorized data is authentic by server authentic"

Strong spoken answer:

> "Syntactically valid JSON only means the payload can be parsed. Pydantic-valid data also follows the declared
> types, constraints, and model structure. Authorized data has passed identity and permission checks, such as
> verifying that an upload belongs to the authenticated tenant. Committed business state is durable database
> truth created by a successful transaction. These are four separate boundaries."

Assessment: the JSON/Pydantic/committed distinctions are right; the correction is on authorization —
authentication proves *identity*, authorization checks *permission and tenant/resource ownership* (the
student's "authentic by server authentic" conflates the two).

## Senior Question — A bad release uses `model_construct()` for untrusted Provider output and 37 Jobs are marked succeeded. Contain, roll back, repair, prevent recurrence.

Student answer (verbatim):

> "contain influenced version provider completion path,preserve release_version\job_id\attemp_id\request_id\trace_id,and cheack failure,don't delete wrong result and audit history.recovery model_validate()/model_validate_json(),add test to check new version stop  completion callback.Identify affected set classify illegal construct result then repair these result.verify Job、Attempt、Event、Result Artifact make sure public illegal succeeded."

Strong spoken answer:

> "First, I would contain the incident by disabling the affected provider-completion path and routing traffic
> away from the faulty release. I would preserve evidence such as the release version, job ID, attempt ID,
> request ID, trace ID, validation failures, and original result references. Then I would roll back the
> application release, restore `model_validate()` or `model_validate_json()`, and add a negative test proving
> that invalid output never reaches the completion callback. Next, I would identify and classify the affected
> Jobs using the release window, attempt records, and output shape. I would repair only confirmed invalid
> records through an idempotent and audited repair process, without deleting history or blindly replaying paid
> Provider calls. Finally, I would reconcile the Job, Attempt, Event, and Result Artifact records and verify
> that invalid succeeded results are no longer exposed."

Assessment: the student covered containment, evidence preservation, restoring validation, a regression test,
classification, repair, and reconciliation — a strong end-to-end direction; the strong answer tightens the
idempotent/audited repair and the "no blind replay of paid Provider calls" boundary.

## Common Weak Answer

"Pydantic checks the JSON, so if the model validates, the request is authorized and safe to commit."

## Strong Answer

"Pydantic only proves declared structure. Authentication proves identity, authorization proves tenant/resource
permission, and a PostgreSQL constraint + transaction creates committed durable truth — four separate
boundaries. Untrusted client and Provider input use `model_validate`/`model_validate_json` (never
`model_construct`), Provider output is validated before any completion, and a negative test asserts both the
`ValidationError` and that no completion side effect ran."

---

# Mental Model Summary

```text
1.  Boundary ladder: JSON-valid -> Pydantic-valid -> authenticated -> authorized -> app invariants -> PG constraint+tx -> committed truth.
2.  Pydantic proves ONE rung (declared structure); not authorization, not a durable commit.
3.  tenant_id is trusted auth context, NOT a request-body field; extra="forbid" rejects it and other undeclared input.
4.  job_status is server-owned lifecycle state; reject it from the body and from Provider output.
5.  Pydantic cannot detect cross-tenant upload ownership; an authorization query (tenant + upload id) does.
6.  UNIQUE (tenant_id, idempotency_key) + the transaction stay the concurrency/commit authority.
7.  Persistence / internal / public representations are SEPARATE; allowlist the public response.
8.  Public error = code + message + field_errors? + request_id?; HTTP status is the class; never leak internals or prose-to-branch-on.
9.  Provider output is fully untrusted; validate StructuredAIResult; shape validation != grounding.
10. Strict types are deliberate + field-specific (MaxTokens/Confidence); no global strictness; conversions in a tested adapter.
11. Cross-field/variant rules: model_validator(after) or a discriminated union; make illegal combinations unrepresentable.
12. Response states are a status-discriminated union; a failed Job is a successfully READ resource (HTTP 200 + status "failed").
13. Untrusted input uses model_validate / model_validate_json; model_dump serializes validated; NEVER model_construct on untrusted.
14. Validate BEFORE side effects; a negative test asserts a ValidationError AND that the completion callback never ran.
15. model_construct() incident: roll back CODE for future traffic; classify + idempotent audited repair for committed facts; code rollback != DB rollback.

Starting model -> reasoning -> correction -> final model:
Initial: tenant_id can be a client field; Pydantic mainly checks illegal client entry; error = error/detail;
the Provider problem is mainly job_status; queued may require a result; cross-field validation, model_construct,
and negative side-effect tests were unknown; code rollback and DB repair were not separated.
Reasoning: the student tied acceptance to tenant-scoped idempotency uniqueness, saw Pydantic cannot discover DB
ownership, chose a separate public response, chose strict types for cost-sensitive input, rejected a
Provider-set status, chose model_validate over model_construct, and knew an empty completion list proves the
fake effect was blocked.
Correction: move tenant identity into trusted auth context; separate JSON parsing / Pydantic validation /
authorization / durable commit; encode variants and states with discriminated unions; validate all Provider
output before completion; assert rejection AND no side effect; roll back code for future traffic and reconcile
committed facts separately.
Final: JSON-valid -> Pydantic-valid -> authenticated -> authorized -> invariants -> PostgreSQL constraint + tx
-> committed durable truth; Provider raw output -> model_validate_json -> StructuredAIResult -> application
checks -> result persistence -> guarded completion -> succeeded. Code rollback protects future executions;
audited reconciliation repairs already-committed facts.
```

---

# Today's Takeaway

Pydantic makes the Day43 contract executable, but it earns exactly one guarantee: declared structure. Keep the
five boundaries separate — JSON-valid, Pydantic-valid, authenticated, authorized, committed — put `tenant_id` in
trusted context, treat Provider output as fully untrusted, model variants and response states as discriminated
unions, never `model_construct()` untrusted input, validate before side effects, and remember that rolling back
code protects the future while committed facts need a separate audited repair.

Most important mental model: the boundary ladder — Pydantic proves structure, not authorization or a commit.
Most important production risk: `model_construct()` (or any skipped validation) letting an external model write
a false `succeeded`. Most important trade-off: strict/`extra="forbid"` vs forward tolerance. Most important
connection: Day45 wires these models through DI and a Provider-adapter seam. Most important interview answer:
JSON-valid, Pydantic-valid, authorized, and committed are four separate boundaries.

Validation status: the Pydantic v2 models and **24 pytest cases** are **real executed runtime evidence** —
executed here on Python 3.10.12 / Pydantic 2.5.0 / pytest 7.4.3 (pinned in `requirements.txt`) → **24 passed**
(the classroom's earlier artifact had 11 tests before the review tightening); but the
completion target is an **in-memory callback, not PostgreSQL**. FastAPI app/routing/serialization/exception
handlers, authentication/authorization, PostgreSQL uniqueness/transaction/commit/rollback/repair,
SQLAlchemy/Alembic, real Provider SDK, Relay/Worker/Redis/Object Storage, integration, and production are **NOT
RUN**. The tested Pydantic version is 2.5.0; not all Pydantic v2 releases were tested.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I name the five boundaries (JSON-valid / Pydantic-valid / authenticated / authorized / committed) and place Pydantic on one?
- [ ] Can I explain why `tenant_id` is trusted context and design a request model with `extra="forbid"`?
- [ ] Can I explain why Pydantic cannot detect cross-tenant upload ownership?
- [ ] Can I design a minimal allowlisted `JobStatusResponse` and say what must never leak?
- [ ] Can I design a stable public error envelope and say why a human `detail` is insufficient?
- [ ] Can I explain why Provider output is fully untrusted and validate it as `StructuredAIResult`?
- [ ] Can I choose deliberate, field-specific strict types and reject global strictness?
- [ ] Can I encode the `output_schema` rule with a discriminated union and the response states as a status union?
- [ ] Can I distinguish `model_validate` / `model_validate_json` / `model_dump` / `model_construct` and never construct untrusted input?
- [ ] Can I write a negative test that asserts both a `ValidationError` and no completion side effect?
- [ ] Can I run the artifact tests (`pytest -q test_day44_pydantic_contracts.py`) and read the 11-passed evidence honestly?
- [ ] Can I contain/roll back/classify/repair/verify the 37-Job `model_construct()` incident without treating code rollback as DB rollback?
```

Preparation for Day45 (Dependency Injection, Lifespan, Configuration and AI Provider Adapters): review these
Day44 models and the `api/day44-pydantic-contracts-design.md` artifact, then preview how they are wired through
FastAPI dependency injection, an application lifespan, a settings/secrets boundary, and a Provider-adapter seam.
SQLAlchemy/Alembic (Day46-48) and a real Provider SDK (Day53) remain later boundaries.

---

Engineering Artifact: [projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md](../../projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md) · Code: [`day44_pydantic_contracts.py`](../../projects/ai-backend-data-layer/api/day44_pydantic_contracts.py) · Tests: [`test_day44_pydantic_contracts.py`](../../projects/ai-backend-data-layer/api/test_day44_pydantic_contracts.py)
