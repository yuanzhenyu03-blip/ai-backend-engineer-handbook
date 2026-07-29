# Day44 Pydantic v2 API and AI Output Contracts (design + tests)

The Phase 4 typed-boundary artifact for the AI Backend Data Layer. It turns the Day43 static HTTP product
contract into **executable, typed** validation/serialization boundaries — client requests, public responses,
public errors, and untrusted AI Provider output — **without** confusing structural validation with
authorization or durable database truth.

> **Validation status of this document and its code.** The Pydantic models and tests are **REAL Pydantic v2
> runtime code** — see the executed evidence below. But **structural validation is NOT authorization and NOT a
> durable database commit**; the completion target in the tests is an in-memory callback, **not** PostgreSQL.
> **NOT RUN:** FastAPI app/routing/response serialization/exception handlers; authentication and tenant
> authorization; PostgreSQL uniqueness/transaction/commit-before-`202`/rollback/repair; SQLAlchemy/Alembic;
> real Provider SDK/output; Relay/Worker/Redis/Object Storage; integration; production. Those are later
> lessons (Day45-58). Contains **no secrets, real connection strings, or client data.**

Code and tests:
[`day44_pydantic_contracts.py`](day44_pydantic_contracts.py) ·
[`test_day44_pydantic_contracts.py`](test_day44_pydantic_contracts.py)

Related: [Day44 lesson](../../../docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md) ·
[Day43 API contract](day43-ai-job-api-contract.md) ·
[project README](../README.md)

---

## 1. The boundary ladder (each rung proves a different thing)

```text
JSON-valid                 -> the bytes parse as JSON (proves nothing about meaning)
Pydantic-valid structure   -> declared fields/types/ranges/literals/model rules pass
authenticated identity     -> who the caller is (trusted context, not request body)
authorized resource/tenant -> the caller may use THIS upload/Job (a DB ownership query)
application invariants     -> business rules beyond a single model
PostgreSQL constraint + tx -> UNIQUE (tenant_id, idempotency_key) + atomic commit
committed durable truth    -> the only source of business truth
```

Pydantic occupies **one** rung: declared structure. It cannot know an upload belongs to the authenticated
tenant, and it cannot make a commit durable.

---

## 2. Request models (trusted tenant context; discriminated union)

```text
tenant_id is NOT a request-body field -- it comes from trusted authentication context. Accepting a claimed
tenant_id from the body is a cross-tenant authorization risk.
upload_session_id / task_type / (supported) max_tokens = client intent.
job_status = server-owned lifecycle state (rejected from the body).
ConfigDict(extra="forbid") rejects undeclared input (job_status, tenant_id, unexpected_debug) instead of
silently ignoring it.

JobRequest = discriminated union on task_type:
  SummarizeRequest           -> task_type="summarize"; FORBIDS output_schema
  ExtractStructuredRequest   -> task_type="extract_structured"; REQUIRES a non-empty output_schema
```

`max_tokens` is a legitimate product parameter **only when the product supports it**, and then it needs
**strict** integer + bounded-range validation; if the product does not expose it, reject it entirely.

---

## 3. Strict, field-specific aliases

```text
MaxTokens  = Annotated[int,   Field(strict=True, ge=1, le=200000)]   # "2000" is NOT coerced to 2000
Confidence = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]    # "very sure" is rejected
```

Strictness is **deliberate and field-specific** where ambiguity, billing, or audit risk exists. Do **not**
enable global strictness blindly — JSON naturally represents UUIDs and timestamps as strings, so a global
strict flag can reject legitimate values. Compatibility conversion, if required, belongs in an **explicit,
tested adapter**, not implicit core-model guessing.

---

## 4. Provider output is untrusted input

```text
StructuredAIResult (extra="forbid"): summary:str(min1) + confidence:Confidence + citations:list[Citation]
Citation (extra="forbid"): source_id:str(min1) + url matches ^https?://
```

The Provider **cannot own the Job lifecycle**, so `StructuredAIResult` has **no** `job_status`; a
Provider-supplied `job_status` is rejected by `extra="forbid"`. Pydantic validates citation/URL **shape** — it
does **not** prove citations are true, grounded, or trustworthy (that is grounding/source verification, not
validation).

---

## 5. Public response models (allowlisted; status-discriminated)

```text
persistence representation  !=  internal/domain representation  !=  public API representation
Internal fields (lease token, fencing generation, raw Provider metadata, raw Object Storage key, Outbox id,
unreviewed Attempt fields) never become public just because an ORM/database object gained a field.

JobStatusResponse = discriminated union on job_status:
  QueuedJobResponse    -> queued/running: NO result, NO failure
  SucceededJobResponse -> succeeded: result REQUIRED, failure absent
  FailedJobResponse    -> failed: failure REQUIRED, result absent

A single response with many nullable fields permits nonsensical states; discriminated state models make the
illegal combinations unrepresentable.
```

A **failed** Job is a **successfully read resource**: `GET` returns **HTTP 200** + business status `failed`. The
`PublicErrorResponse` envelope (below) is for an HTTP/request failure; a `FailedJobResponse.failure` is
**business** state.

---

## 6. Stable public error envelope

```text
PublicErrorResponse.error:
  code        (stable machine semantics a client may branch on)
  message     (safe public text; do NOT branch on mutable prose)
  field_errors? (optional per-field detail)
  request_id?   (correlation)

HTTP status = the error CLASS; error.code = stable machine semantics.
Never expose SQL, table details, tracebacks, credentials, raw Provider errors, raw storage keys, or
cross-tenant existence.
```

The student's initial `erro, detail` is insufficient: a human-readable detail cannot be branched on by client
programs.

---

## 7. Validation entry points (and the one to never use on untrusted input)

```text
model_validate(obj)        -> validate an untrusted Python object
model_validate_json(raw)   -> validate untrusted raw JSON
model_dump(model)          -> serialize an ALREADY-validated model
model_construct(...)       -> NO validation (skips validators, nested conversion, extra="forbid")
                              -> MUST NOT be used for untrusted client or Provider input
TypeAdapter(Union[...])    -> validate a discriminated union
```

---

## 8. Validation must precede side effects

```text
validate_provider_output_before_completion(raw_provider_json, on_completion):
    result = StructuredAIResult.model_validate_json(raw_provider_json)   # raises BEFORE on_completion
    on_completion(result)                                               # only a validated result completes
    return result
```

The first negative test asserts **both**: a `ValidationError` occurs **and** the completion callback is never
called (an empty completion-calls list). Checking only for an exception is insufficient — a dangerous
implementation could perform the side effect before validating.

---

## 9. Production incident: `model_construct()` marked 37 Jobs succeeded

```text
Scenario: a bad release replaced validation with model_construct() for untrusted Provider output; 37 Jobs were
incorrectly marked succeeded.
Contain : disable the affected Provider-completion path + route traffic away from the bad release; avoid an
          indiscriminate full-system shutdown.
Preserve: release version, job_id, attempt_id, request_id, trace_id, validation evidence, original result
          references, audit history.
Roll back: the faulty APPLICATION RELEASE (restore model_validate/model_validate_json) -- this protects FUTURE
          executions; it does NOT roll back committed database facts.
Regress : add negative tests proving invalid output never reaches completion.
Classify: identify the affected set by release/time/attempt/output evidence; do NOT assume all 37 Jobs have
          identical damage.
Repair  : fix confirmed-invalid durable facts with a reviewed, idempotent, guarded, audited repair; reconcile
          Job/Attempt/Event/Result Artifact.
Never   : blindly return all Jobs to queued, blindly replay paid Provider work, delete audit evidence,
          fabricate valid results, or treat code rollback as database-history rollback.
```

---

## Contract one-screen summary

```text
tenant_id  -> trusted auth context, NOT a body field; extra="forbid" rejects it and other undeclared input
request    -> discriminated union on task_type (summarize forbids / extract_structured requires output_schema)
strict     -> MaxTokens/Confidence strict + bounded; no global strictness; conversions in a tested adapter
provider   -> untrusted input; StructuredAIResult (no job_status); validate SHAPE, not grounding
response   -> allowlisted, status-discriminated (queued/running vs succeeded[result] vs failed[failure]); failed = HTTP 200
error      -> PublicErrorResponse{code,message,field_errors?,request_id?}; HTTP status is the class; never leak internals
entrypoints-> model_validate / model_validate_json for untrusted; model_dump to serialize; NEVER model_construct on untrusted
gate       -> validate BEFORE side effects; test both rejection AND no completion call
boundaries -> JSON-valid -> Pydantic-valid -> authenticated -> authorized -> invariants -> PG constraint+tx -> committed truth
incident   -> contain + preserve evidence + roll back CODE + regress + classify + audited repair; code rollback != DB rollback
```

---

## Run instructions

```text
cd projects/ai-backend-data-layer/api
python3 -m py_compile day44_pydantic_contracts.py test_day44_pydantic_contracts.py
python3 -m pytest -q test_day44_pydantic_contracts.py
```

The tests cover: a valid summarize request; body-level tenant/job_status/debug/output_schema extras rejected;
string `max_tokens` rejected; extract requires a non-empty output schema; a succeeded response requires a
result; a queued response rejects an early result; invalid Provider output raises before the fake completion
callback; and valid Provider output reaches the callback exactly once.

---

## Validation and evidence classification

```text
REAL RUNTIME (executed)  : Pydantic v2 model validation + the 11 pytest cases. Repository evidence below.
                           Classroom environment: Python 3.11.5, Pydantic 2.5.0, pytest 7.4.3 -> 11 passed.
                           Repository re-run: Python 3.10.12, Pydantic 2.5.0, pytest 7.4.3 ->
                             `python3 -m py_compile ...` passed;
                             `python3 -m pytest -q test_day44_pydantic_contracts.py` -> 11 passed.
                           The pinned/tested Pydantic version is 2.5.0; do NOT claim all Pydantic v2 releases
                           were tested.
IN-MEMORY ONLY           : the completion target is an in-memory list callback, NOT PostgreSQL guarded completion.
NOT RUN                  : FastAPI app/routing/response serialization/exception handlers; authentication and
                           tenant authorization; PostgreSQL uniqueness/transaction/commit-before-202/rollback/
                           repair; SQLAlchemy/Alembic; real Provider SDK/output; Relay/Worker/Redis/Object
                           Storage; integration runtime.
PRODUCTION NOT VALIDATED : not deployed; no production accessed.
SECURITY                 : no secrets, credentials, connection strings, or client data; identifiers are placeholders.
SCOPE                    : DI/lifespan/configuration/Provider adapters (Day45), SQLAlchemy mapping (Day46),
                           async sessions/transactions (Day47), real Provider SDK parsing (Day53), and
                           contract/integration/failure-injection tests + observability (Day57-58) are NOT
                           implemented here.
```
