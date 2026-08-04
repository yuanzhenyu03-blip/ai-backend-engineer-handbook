# Day53 — OpenAI SDK, Provider Boundaries and Structured Output

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day52 — Authorization, Tenant Isolation, Quotas and API Security
Previous Lesson: Day52 — Authorization, Tenant Isolation, Quotas and API Security
Next Lesson: Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation
Engineering Artifact: projects/ai-backend-data-layer/api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md
  + runnable day53_openai_provider_structured_output.py + test_day53_openai_provider_structured_output.py (real Pydantic v2 + fake transport; 45 passed)
```

Main engineering artifact: a provider-neutral Provider boundary (fake injected transport) with a REAL Pydantic v2
structured-output gate, plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Locate** the SDK boundary at the Adapter (not the Repository/database) and keep SDK types from leaking inward.
- **Design** an application-owned `AIProvider.generate(request) -> ProviderOutcome` union that hides SDK responses and
  vendor exceptions.
- **Implement** a strict Day44 structured-output validation gate that runs before any side effect.
- **Bind** `task_type` to a server-owned, versioned schema and reject cross-version satisfaction.
- **Apply** the guarded `running -> succeeded` completion and stop on a zero-row result.
- **Separate** business execution success from cost settlement (a valid result can succeed with unknown usage).
- **Classify** refusal, incomplete, timeout, 401/403, 429, and capability failures without fabricating success or zero
  cost.
- **Diagnose** an erroneous model rollout: configuration rollback is not a rollback of durable business facts.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day52 accepted an authorized, budget-reserved Job — but nothing had called a real Provider yet. The moment you do,
three things try to corrupt your durable facts: the SDK (its response and exception types leak vendor coupling
everywhere they touch), the model output (untrusted JSON that may be missing required fields or carry forbidden debug
fields), and configuration (a rollout that changes the default model, or a rotated key). If SDK types reach the
Repository, every layer depends on a vendor. If unvalidated output reaches completion, you persist garbage as a
business fact. If a config rollback is treated as a business rollback, you destroy a legitimately-earned result. Day53
builds the application-owned Provider boundary — a typed outcome union, a strict validation gate, guarded completion,
honest cost/outcome truth, and safe error classification — so none of that can happen.

---

## 4. Roadmap Position

```text
Day44 structured contracts (validate before side effects)
        |
Day45 Adapter seam + lifespan-owned Settings/SDK client
        |
Day52 authorized, funded Job
        |
        v
Day53 OpenAI-compatible Adapter + structured-output boundary   <-- you are here
        |
        v
Day54 streaming/disconnect/timeout/cancellation -> Day55 Celery Worker execution -> Day56 retry/backoff/backpressure
```

### Knowledge Continuity

```text
Previous Knowledge
  Day44 strict validation before side effects; Day45 lifespan-owned Settings/SDK client + Adapter seam;
  Day47/Day50 short guarded completion transactions; Day52 authorized, reserved Job + usage reconciliation
        |
        v
Current Lesson Concept
  SDK types stop at OpenAICompatibleAdapter; typed ProviderOutcome union; Day44 gate before completion;
  server-owned versioned schema; guarded running->succeeded; success vs cost axes; safe error classification;
  config rollback != business rollback
        |
        v
Future Production Usage
  Day54 distinguishes HTTP/Provider/Job lifecycles (disconnect != cancellation); Day55 runs it in Celery Workers
  without bypassing Day52/Day53; Day56 owns retry/backoff/degradation/backpressure
```

Day53 does not implement Day54 streaming/cancellation, Day55 Celery, or Day56 retry/backoff — and does not claim the
real `openai` SDK, network, PostgreSQL, Redis, or production.

---

## 5. Lesson Map

```text
SDK boundary at the Adapter (not the DB) -> AIProvider.generate -> typed ProviderOutcome union
  -> ProviderSuccess payload is UNTRUSTED -> Day44 strict validation (extra=forbid, required fields)
  -> server-owned versioned schema (task_type -> vN; no cross-version satisfaction)
  -> valid -> guarded running->succeeded (zero rows -> stop) -> Result Artifact (validated + safe metadata only)
  -> success vs cost axes: valid output may succeed with UNKNOWN usage (retain reservation, reconciliation_pending)
  -> classify refusal/incomplete/timeout/401-403/429/400 (no fake success, no zero cost)
  -> lifespan-owned client reused; Job cap (5000) wins over adapter default (8000); usage reported, not re-reserved
  -> raw minimization (no prompt/secret/raw payload persisted); config rollback != business-fact rollback
```

---

## 6. Core Mental Model

```text
Provider boundary  = an application-owned interface (AIProvider.generate -> ProviderOutcome), NOT "the data business
                     logic needs from the response". SDK objects/exceptions live ONLY inside the Adapter.
ProviderSuccess    = UNTRUSTED payload until the Day44 gate validates it against the Job's bound server-owned schema.
Completion         = the ONLY owner of guarded running->succeeded + the durable Result Artifact/usage/Event UoW.
Two axes           = business execution success (valid output) and cost settlement (usage known/unknown) are separate.
Config vs facts    = current Settings governs NEW calls; the persisted execution contract governs result acceptance.
```

---

## 7. Main Concepts

## Concept 1: Where is the SDK boundary?

### Tech Lead Question

An OpenAI-compatible SDK returns response objects and raises vendor exceptions. Which layer is allowed to see those
types?

### Student Thinking

The student reasoned about what must NOT depend on the SDK and pointed at persistence first.

### Student Answer

"数据库层" — correctly identifying that the database must not depend on the SDK, then refined to the Adapter boundary
before the Repository.

### Tech Lead Review

Right instinct, wrong layer for the boundary. The Repository is the data-access layer, but SDK request/response/
exception types must stop EARLIER, inside `OpenAICompatibleAdapter`. The Adapter translates SDK responses and vendor
exceptions into an application `ProviderOutcome`; it never completes Jobs or writes databases. Everything inward of the
Adapter is vendor-neutral.

### Engineering Thinking

A boundary that leaks vendor types couples every layer to one Provider; a translating Adapter lets you swap Providers
and test with a fake transport.

### Framework Connection

`OpenAICompatibleAdapter.generate(request) -> ProviderOutcome`; all SDK objects/exceptions stay inside.

---

## Concept 2: Who owns completion, and what does a zero-row guard mean?

### Tech Lead Question

A Provider returns a successful result. Which component receives it, and what happens if the guarded completion
updates zero rows?

### Student Answer

"是应返回给 Completion Service"; and on a guarded zero-row completion, "应该停止向下处理".

### Tech Lead Review

Correct on both. Only the Completion Service may run the guarded `running -> succeeded`, persist the validated Result
Artifact/usage/Event, and commit a short UoW. A zero-row result means STOP — it can mean duplicate, stale execution,
cancellation, retry, or changed facts. Inspect durable state and reconcile; never overwrite. And because the Provider
call is a PAID side effect, eligibility is claimed BEFORE it: `execute_job` ATOMICALLY claims execution rights (creating one IN_FLIGHT `Attempt`) before any call — only a RUNNING
Job with no open Attempt wins; a terminal/pending Job or a concurrent caller is `PRECALL_BLOCKED` with zero transport
calls, so neither a terminal Job nor two concurrent Workers can issue a duplicate paid call.

### Engineering Thinking

Centralizing the guarded transition + UoW in one owner is what makes duplicate delivery and retries safe.

### Framework Connection

`CompletionService.complete_success` -> `COMPLETED` / `NOOP_ZERO_ROWS`; Day47 short UoW.

---

## Concept 3: A provider-neutral outcome contract

### Tech Lead Question

Should the layers above the Adapter consume the SDK response type or something you define?

### Student Answer

"由我们定义的 ProviderResult".

### Tech Lead Review

Correct. Evolve it into a typed `ProviderOutcome` union: `ProviderSuccess`, `ProviderRefusal`, `ProviderIncomplete`,
`ProviderTimeout`, `ProviderAuthenticationError`, `ProviderRateLimited`, `ProviderCapabilityError`,
`ProviderTransportError`. `ProviderSuccess`'s payload stays UNTRUSTED until validation. Never leak raw SDK types, raw
prompts, debug fields, or secrets inward.

### Framework Connection

The `ProviderOutcome` dataclasses; the Adapter maps each SDK exception to exactly one case.

---

## Concept 4: Structured-output parsing vs validation

### Tech Lead Question

The Provider returns valid JSON, but it has an unexpected `debug_prompt` and is missing the required `citations`. Can
it be accepted?

### Student Answer

"不能，必须要经过实际业务验证"; and the invalid-output test "不会继续调用完成流程".

### Tech Lead Review

Correct. It may exist as an untrusted payload but MUST fail the application `StructuredAIResult` contract — a strict
schema (`extra="forbid"`) rejects the forbidden extra and the missing required field. Invalid output NEVER calls the
Completion Service: no success transition, Result Artifact, Event, or success write. SDK/Pydantic parsing does not
replace Day44's validation gate. Citation shape is not citation grounding — grounding is not taught here.

### Framework Connection

`StructuredOutputValidator.validate` -> `VALID` / `CONTRACT_VIOLATION` / `SCHEMA_NOT_FOUND`; real Pydantic v2.

---

## Concept 5: Server-owned, versioned schema

### Tech Lead Question

How is the output schema chosen, and can a v2 output satisfy a Job contracted as v1?

### Student Answer

"由服务端根据 task_type 选择受版本控制的 Schema"; and "不能" accept v2 as v1.

### Tech Lead Review

Correct. A Job binds a schema name+version at acceptance from a server-owned `SchemaRegistry`. A v2 output must not
silently satisfy a v1 Job; there is no implicit truncation, downgrade, or guessed mapping (an unknown version is
`SCHEMA_NOT_FOUND`). Day44's `output_schema` must not mean arbitrary client JSON Schema is forwarded to a Provider —
constrain it to server-approved families/versions.

### Framework Connection

`SchemaRegistry.model_for((name, version))`; the persisted execution contract governs acceptance.

---

## Concept 6: Settings, credentials, and the per-Job output bound

### Tech Lead Question

Where do `api_key`, `base_url`, model policy, and the effective output cap come from — request input or Settings?

### Student Answer

"由 Day45 的受验证 Settings 与 Adapter 控制，因为客户端可以进行修改"; `generate(request: ProviderRequest)` carries Job/
Schema/version/budget/audit; and the effective output bound is "5000".

### Tech Lead Review

Correct. Day45 validated Settings + Adapter own credentials and model policy; clients can modify inputs, so those
never come from payloads. Persist only NON-secret execution-contract facts (provider profile/policy version, approved
model, schema name/version, task type, max-output bound, correlation IDs). The Job-controlled 5,000 cap wins over an
8,000 Adapter default — `effective_max = min(Job cap, ceiling)`, never enlarging the per-Job limit — and the Adapter
only REPORTS usage; it does not create a second reservation. Retrieve current credentials when execution begins; never
persist old credentials. And the outgoing call is BOUND to the persisted execution contract: `execute_job` loads the
Job + `ExecutionContract` first and derives the model/schema/version/task/profile from it — a caller cannot pick them;
an inconsistent request is safely rejected (`CONTRACT_MISMATCH`) BEFORE any transport call, and the token budget is
tightened, never enlarged.

### Framework Connection

`ProviderConfig` (validated Settings), `OpenAICompatibleAdapter` cap enforcement, one lifespan-owned client.

---

## Concept 7: Cost and outcome truth (two axes)

### Tech Lead Question

If the Provider times out and usage is unknown, can the Job still succeed? Can you record usage as zero?

### Student Answer

"只报告实际 usage 给已有的 Day52 预留/对账流程"; and "不能" report timeout usage as zero.

### Tech Lead Review

Correct on cost. And an important correction: business execution success and cost settlement are SEPARATE state axes. A
valid structured output can make the Job business status `succeeded` even when usage is UNKNOWN — retain the
reservation and hold a cost `reconciliation_pending` state; never represent unknown usage as zero. Overages remain
controlled reconciliation (Day52), never a `min()` truncation. A timeout, by contrast, is a non-terminal outcome with unknown
execution and usage (see Concept 8). Separately: an invalid, refused, or incomplete result does NOT mean the Provider
did not charge — every non-success Outcome carrying KNOWN usage retains the exact usage and settles it through a
Day52-compatible path (known -> settled; unknown -> reconciliation-pending), and a refusal's usage is never dropped.

### Framework Connection

`CostState.SETTLED` vs `RECONCILIATION_PENDING`; Day52 reservation reused, no zero-cost fabrication.

---

## Concept 8: Error semantics and the rollout/rollback exercise

### Tech Lead Question

A rollout switches the default model to one that doesn't support `research_summary.v1`. New calls 400; an old
in-flight call later returns a valid v1 result; another times out. What do you do?

### Student Thinking

The student first read the 400 and the valid result as the same call, then separated them by time/worker.

### Student Answer

Classify 401/403 as "配置/认证故障并阻止新的 Provider 调用"; record Provider 429 as downstream rate limiting for the
Job; do not persist the raw Provider response ("不应该"); reuse the lifespan client per process. Rollout plan: stop new
calls on the bad config, mark 400 Attempts as capability/config failures with audit IDs, roll back to a validated
config, accept a legitimate old in-flight v1 result via guarded completion, and hold reconciliation-pending for the
timed-out Job.

### Tech Lead Review

All correct, with one correction: a single unsupported-output request cannot BOTH 400 and return a valid result — the
valid result belongs to a distinct pre-rollout / old-worker call. A timeout is NOT written as a terminal `FAILED`: whether the Provider ran and what it cost are unknown, so the Job
moves to a non-terminal `PENDING_RECONCILIATION` lifecycle (reservation retained, no auto-retry) and a later
contract-matching legitimate result is accepted via the LATE-OUTCOME INGESTION path (`ingest_late_outcome`, which
locates the persisted `Attempt` and validates attempt_id + correlation + provider request id against it, then runs
guarded completion WITHOUT calling the Adapter) — NOT by calling `execute_job` again (that would issue a second paid
Provider call). Any late outcome on a terminal Job is a guarded no-op that never rewrites facts. Because real callbacks are
at-least-once, ingestion is also CONCURRENCY-SAFE + IDEMPOTENT: an atomic `claim_late_outcome` flips the Attempt
`AWAITING_LATE_OUTCOME -> PROCESSING_LATE_OUTCOME` under a lock, so of two concurrent or duplicate deliveries exactly
one dispatches (one Event, one cost record, settled once) and the other is a `COMPLETION_NOOP`; the Attempt ends
`CONSUMED`. 401/403 stops new calls with
that config and preserves evidence (not a user-input error). A 400 that means the current model/profile cannot honor
the controlled schema is CONFIG-WIDE and fails the config closed (a single-request 400 does not). 429 after a durable
202 is a downstream Job/Attempt event, not a retroactive client 429 (keep safe `Retry-After`; Day56 owns retry). The core rule: **configuration rollback is not a
business-fact rollback** — a result that satisfies its persisted contract is still accepted.

### Framework Connection

`ProviderConfig.disable`; `execute_job` classification; guarded completion against the persisted contract.

---

## 8. Common Misconceptions

The correction trajectories from class (initial model -> reasoning -> correction -> durable model):

1. **"Unknown usage means the Job cannot succeed."** Not releasing the reservation was right, but a valid business
   output may still succeed — business execution state and cost-settlement state are separate axes. Test: is the output
   valid? If yes, succeed and hold cost `reconciliation_pending`.

2. **"A fake test proves only the Adapter."** A composed fake-transport test proves the local Adapter -> Validator ->
   Completion control flow WHEN those components truly run — it does not prove the real Provider, network, PostgreSQL,
   Redis, Worker, integration, or production.

3. **"The 400 rollout and the valid in-flight result are the same call."** They are separate calls / time boundaries;
   retain a valid pre-rollout or old-worker result when it matches its persisted Job contract.

4. **Terminology.** `Provider boundary` is an application-owned interface, not "the data business logic needs from the
   response." Say `fail validation`, not "fail verification." Say `new Job claims` / `new calls`, not "new
   declarations."

> The final Chinese Mental Model summary produced in class was **assistant-assisted** at the student's explicit
> request; it is labeled as such and not presented as independently authored student prose.

---

## 9. Engineering Trade-offs

- **Where to place the boundary.** Deeper (Repository) is fewer layers but couples the DB to a vendor; at the Adapter
  it adds a translation layer but keeps everything inward vendor-neutral and testable. Chosen: Adapter.
- **SDK/Pydantic parsing vs an application validation gate.** SDK-side parsing is convenient but is not your business
  contract; a strict application model owns required/forbidden fields and business checks. Chosen: application gate.
- **Reuse business success for unknown usage vs block it.** Blocking is simpler but wrong — it discards a valid result
  over a cost-metadata gap. Chosen: succeed the business fact, hold cost reconciliation.
- **Persist raw Provider responses vs minimize.** Raw storage helps forensics but leaks prompts/secrets and bloats
  Artifacts. Chosen: persist validated domain result + safe metadata; any raw store is a separate, governed system.
- **Client model selection vs server allowlist.** Free-form model IDs are flexible but unsafe; a constrained selector
  mapped server-side to an allowlisted model is safe. Chosen: server allowlist.

---

## 10. Hands-on Exercises

1. Locate the SDK boundary (Adapter, not Repository/database).
2. Decide Completion Service ownership and guarded zero-row behavior.
3. Classify valid JSON with missing fields / forbidden extras.
4. Bind `task_type` to a versioned server-owned schema and reject cross-version satisfaction.
5. Select the per-Job 5,000 output cap instead of an 8,000 default.
6. Distinguish a Provider 429 from the original API admission 429.
7. Solve the erroneous model rollout, valid in-flight result, and timeout/unknown-usage reconciliation.
8. Complete Beginner, Intermediate, and Senior English interview answers.

Run the model:

```bash
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day53.txt   # pydantic==2.5.0, pytest==7.4.3
python3 -m pytest -q test_day53_openai_provider_structured_output.py   # 45 passed
```

---

## 11. Relevant Framework Connections

- **FastAPI**: Router/Dependency admission is separate from background execution; the original 202 cannot become a
  later Provider 429.
- **Pydantic v2 / Day44**: strict structured-output validation before side effects; forbidden extra fields and missing
  required fields fail.
- **Day45 lifespan/Settings**: a process-scoped SDK client, validated Settings, secret-safe configuration, and a
  rotation/drain boundary.
- **PostgreSQL / SQLAlchemy / Day47 UoW**: a guarded state transition and a short durable completion transaction.
- **Day52**: authorization, durable reservation, actual-usage reconciliation, and no zero-cost fabrication.

---

## 12. AI Backend Connections

- A multi-tenant research Job with structured `summary`, `citations`, and `confidence`.
- Provider cost evidence, unknown-usage retention, and overage honesty.
- Provider refusal / incomplete / error classification.
- Schema-version compatibility and Result Artifact meaning.
- Configuration rollout rollback versus durable business facts.

---

## 13. English Interview

Key vocabulary: Provider boundary, Adapter, application-owned interface, ProviderOutcome union, structured output,
strict validation, `extra="forbid"`, server-owned schema registry, schema version binding, guarded completion,
zero-row stop, execution contract, business success vs cost settlement, unknown usage, reconciliation-pending,
refusal/incomplete/timeout classification, Provider 429 vs API 429, raw-data minimization, configuration rollback vs
business-fact rollback.

### Beginner — what is a Provider boundary?

Strong answer: "A Provider boundary is an application-owned interface — for example `AIProvider.generate(request) ->
ProviderOutcome` — that hides the vendor SDK. The Adapter behind it owns all SDK response and exception types and
translates them into my own outcome types, so the rest of the system never depends on a specific Provider."

### Intermediate — the Provider returns valid JSON missing a required field

Strong answer: "It parses but must fail validation. I validate the untrusted payload against the Job's bound
server-owned schema with a strict model that forbids extra fields and requires the mandatory ones. If it fails, I never
call the Completion Service — no success transition, Result Artifact, or Event — and I record a classified validation
failure with field locations only, no raw payload."

### Senior — a Provider times out with unknown usage; can the Job succeed, and how is cost handled?

Strong answer: "Business execution success and cost settlement are separate axes. A timeout is a NON-terminal
reconciliation outcome (not a definite FAILED, so a matching late result can still be accepted), but the key case is a
valid result with unknown usage: the Job can succeed on the business axis
while I keep the reservation and hold a cost reconciliation-pending state — I never record unknown usage as zero. Only
the guarded `running -> succeeded` transition, owned by the Completion Service, writes the validated Result Artifact;
if it updates zero rows I stop and reconcile. And a later configuration rollback of the model does not roll back that
durable business fact."

---

## 14. Mental Model Summary

```text
SDK response/exception --Adapter--> ProviderOutcome union (SDK types stop here)
        |
        v
ProviderSuccess.payload (UNTRUSTED) --Day44 strict gate against the Job's bound server-owned schema-->
        |                                          |
     VALID                                    CONTRACT_VIOLATION / SCHEMA_NOT_FOUND
        |                                          |
   guarded running->succeeded (zero rows -> stop)   record classified failure; NO completion
        |
        v
Result Artifact = validated domain result + safe metadata only (no prompt/secret/raw payload)
Cost axis: usage known -> SETTLED (success OR known-usage failure) ; usage unknown -> RECONCILIATION_PENDING (retain reservation, never zero)
Pre-call gate: only a RUNNING Job may START a paid call (terminal/pending -> PRECALL_BLOCKED, 0 transport calls)
Timeout: PENDING_RECONCILIATION (non-terminal) ; a matching late result completes via ingest_late_outcome (NO new call), never a 2nd execute_job
Call is bound to the persisted contract (model/schema/version/task/profile/max)
Config rollback governs NEW calls; the persisted execution contract governs result acceptance (facts are not rolled back)
```

---

## 15. Today's Takeaway

The Provider is untrusted at three levels — its SDK types, its output, and its configuration — and Day53 puts an
application-owned boundary in front of all three. The Adapter translates SDK responses and vendor exceptions into a
typed `ProviderOutcome`; a strict Day44 gate validates the untrusted payload against the Job's bound server-owned
schema before any side effect; only the Completion Service runs the guarded `running -> succeeded`; a valid result can
succeed even when usage is unknown (retain the reservation, reconcile the cost); and a configuration rollback never
rolls back a durable business fact.

---

## 16. Before Next Lesson Checklist

- [ ] I can place the SDK boundary at the Adapter and keep SDK types out of the business/DB layers.
- [ ] I can design a typed `ProviderOutcome` union and classify every non-success case.
- [ ] I can write a strict Day44 validation gate that runs before completion and never leaks the raw payload.
- [ ] I can bind `task_type` to a versioned server-owned schema and reject cross-version satisfaction.
- [ ] I can separate business success from cost settlement and hold reconciliation-pending on unknown usage.
- [ ] I can enforce the per-Job output cap and reuse one lifespan-owned client.
- [ ] I can explain why a configuration rollback is not a business-fact rollback.
- [ ] Next: Day54 distinguishes HTTP connection, Provider request, and Job lifecycles — a disconnect is not
  cancellation.
