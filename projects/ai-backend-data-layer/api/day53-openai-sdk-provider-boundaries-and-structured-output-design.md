# Day53 — OpenAI SDK, Provider Boundaries and Structured Output (Design + Runbook)

Put an OpenAI-compatible Provider behind an APPLICATION-OWNED boundary so SDK behavior, untrusted outputs, cost
evidence, and configuration changes cannot corrupt durable AI Job facts. Day52 accepted an authorized, budget-reserved
Job; Day53 executes it against a Provider without leaking SDK types, secrets, or unvalidated output into the business
layer.

Runnable model: [`day53_openai_provider_structured_output.py`](day53_openai_provider_structured_output.py) +
[`test_day53_openai_provider_structured_output.py`](test_day53_openai_provider_structured_output.py).

---

## 0. Evidence label (read first)

```text
CONCEPTUAL DESIGN                                     : COMPLETED (this runbook + lesson)
LOCAL CONTROL-FLOW + REAL PYDANTIC v2 VALIDATION      : RUN (pytest; injected FAKE transport)
Real `openai` SDK / real network / real Provider      : NOT RUN
Real PostgreSQL / Redis / Celery Worker               : NOT RUN
Real FastAPI wire / integration / production          : NOT RUN
Day54 streaming/disconnect/cancellation, Day55 Celery, Day56 retry/backoff/degradation : NOT IMPLEMENTED
```

Executed: `python3 -m pytest -q test_day53_openai_provider_structured_output.py` -> **36 passed**
(Python 3.10.12, pydantic 2.5.0, pytest 7.4.3). The suite proves the REAL Pydantic v2 validation gate + application
control flow (Adapter -> Validator -> CompletionService) with an injected fake transport. It does NOT prove the real
`openai` SDK, network, Provider, PostgreSQL, Redis, Celery, FastAPI wire, integration, or production. The classroom
itself was a conceptual/static design review; this evidence is the coding agent's executed run.

SECURITY: no real `api_key`, `base_url` secret, raw prompt, Document content, or Provider response is persisted or
logged. `ProviderRequest.prompt` is transport input for the Adapter only.

---

## 1. Layering — SDK types stop at the Adapter

```text
Router/Dependency -> Application Service -> AIProvider.generate(request) ->
  OpenAICompatibleAdapter  (owns ALL SDK objects + vendor exceptions)
    -> ProviderOutcome (application union) -> StructuredOutputValidator (Day44, server-owned versioned schema)
    -> CompletionService (guarded running->succeeded, short UoW) -> Repository -> PostgreSQL
```

The initial student answer put the SDK boundary at the "database layer". Correction: the Repository is the
data-access layer, but SDK request/response/exception types must stop EARLIER — inside `OpenAICompatibleAdapter`. The
Adapter translates SDK responses and vendor exceptions; it does NOT complete Jobs or write databases.

---

## 2. Provider-neutral contract (`ProviderOutcome` union)

- `AIProvider.generate(request: ProviderRequest) -> ProviderOutcome` is application-owned. No raw SDK type, prompt,
  debug field, or secret escapes as an SDK object.
- `ProviderOutcome` is a typed union: `ProviderSuccess(raw_payload, usage)`, `ProviderRefusal`, `ProviderIncomplete`,
  `ProviderTimeout`, `ProviderAuthenticationError`, `ProviderRateLimited`, `ProviderCapabilityError`,
  `ProviderTransportError`.
- `ProviderSuccess.raw_payload` is UNTRUSTED until application validation. `Usage.total_tokens is None` means EXPLICIT
  UNKNOWN — never coerced to zero.

---

## 3. Structured-output parsing and validation (Day44 gate)

- Valid JSON with an unexpected `debug_prompt` and a missing required `citations` can exist as an untrusted Provider
  payload but MUST fail the application `StructuredAIResult` contract. Strict schema (`extra="forbid"`) rejects missing
  required fields and forbidden extra fields.
- Invalid output NEVER calls the CompletionService: no success transition, Result Artifact, Event, or success write.
  The validation classification carries field LOCATIONS only, never values or the raw payload.
- SDK/Pydantic parsing support does not replace Day44's application-owned validation gate, business checks, guarded
  completion, or audit/cost boundaries. Citation SHAPE is not citation grounding — grounding is not claimed here.

---

## 4. Server-owned, versioned schema registry

- `task_type` -> a server-owned, versioned `SchemaRegistry` (`research_summary.v1`, `research_summary.v2`). A Job binds
  a schema name+version at acceptance; the PERSISTED execution contract governs result acceptance.
- A `v2` output must NOT silently satisfy a Job contracted as `v1` (and vice versa). No implicit truncation, downgrade,
  or guessed schema mapping; an unknown version is `SCHEMA_NOT_FOUND`, not a guessed downgrade. A real cross-version
  change would need an explicit versioned, tested, audited migration.
- Day44's `ExtractStructuredRequest.output_schema` must NOT mean arbitrary client JSON Schema is forwarded to a
  Provider — constrain it to server-approved schema families/versions (or a validated product subset).

---

## 5. Settings, credentials, and resource bounds (Day45)

- Day45 validated Settings + Adapter own `api_key`, `base_url`, and model policy — clients can modify inputs, so these
  never come from request payloads. API keys, base URLs, full Settings, and arbitrary model IDs must not enter Job
  requests, persistence, Outbox, or logs. If a product supports model selection, client input is only a constrained
  selector mapped server-side to an allowlisted model.
- Persist NON-secret execution-contract facts: provider profile/policy version, approved model identifier, schema
  name/version, task type, max-output bound, correlation IDs.
- Retrieve current credentials from validated Settings when execution BEGINS; never persist old credentials. Current
  Settings governs NEW calls; the persisted Job execution contract governs in-flight result acceptance.
- The Job-controlled 5,000 output cap wins over an 8,000 Adapter default: `effective_max = min(Job cap, adapter/model
  ceiling)`. The Adapter NEVER enlarges the per-Job limit and only REPORTS usage — it does not create a second
  reservation (Day52 already reserved).
- **The outgoing Provider call is bound to the PERSISTED execution contract, not the caller.** `execute_job` loads the
  Job + its `ExecutionContract` FIRST and `bind_request_to_contract` derives the model, schema, schema version, task
  type, and provider profile from the contract (a caller cannot pick them). Any inconsistency on an authoritative
  field is a pre-call SAFE REJECTION (`CONTRACT_MISMATCH`) — no transport/network call is made. The token budget is
  SAFELY TIGHTENED to `min(request, contract bound, model/server hard cap)`, never enlarged.

---

## 5A. Two paths: pre-call execution gate vs late-outcome ingestion

The external Provider call is a paid side effect, so eligibility is claimed BEFORE it — not after. `execute_job`
follows the order: **claim execution eligibility -> (only then) make the Provider call -> process the result ->
guarded completion.**

```text
PATH A — start a NEW authorized Provider call: execute_job(request)
  provider_config.disabled                 -> BLOCKED_CONFIG_DISABLED (no call)
  pre-call gate: is_claimable_for_new_call -> only a RUNNING Job may start a call
    SUCCEEDED / FAILED                      -> PRECALL_BLOCKED (terminal); transport calls == 0
    PENDING_RECONCILIATION                  -> PRECALL_BLOCKED (awaiting a late result, NOT a retriable new call); calls == 0
  bind_request_to_contract mismatch         -> CONTRACT_MISMATCH; transport calls == 0
  -> adapter.generate(bound)  (reached ONLY after the gate + binding)  -> _dispatch_outcome -> guarded completion

PATH B — ingest an ALREADY-ISSUED late outcome: ingest_late_outcome(outcome, job_id, correlation_id, ...)
  NO adapter/transport call is made (no new paid Provider call).
  validate job_id + correlation_id (and provider_request_id when supplied) against the PERSISTED contract:
    mismatch -> LATE_OUTCOME_REJECTED (no completion, no overwrite, no transport)
    match    -> _dispatch_outcome -> guarded completion (a terminal Job -> COMPLETION_NOOP, no fact overwrite)
```

The correct handling of a result that arrives after a timeout is PATH B (a callback-like ingestion of the outcome
that the earlier request eventually produced), never a second `execute_job` (which would call the Provider again and
incur a second charge). Day54 owns the real callback/streaming/cancellation protocol; `ingest_late_outcome` is the
minimal, explicit in-memory boundary for Day53.

---

## 6. Cost and outcome truth (two separate axes)

- Day52 reserves budget before Job + Outbox acceptance. Day53's Adapter reports actual usage OR explicit unknown.
- **Business execution success and cost settlement are SEPARATE state axes.** A valid structured output can make the
  Job business status `succeeded` even when usage is UNKNOWN — retain the reservation and hold a cost
  `reconciliation_pending` state (never represent unknown usage as zero).
- **Invalid/refused/incomplete output does NOT mean the Provider did not charge.** Every non-success Outcome that
  carries KNOWN usage retains the EXACT usage and is settled/reconciled through a Day52-compatible path
  (`record_cost`): known usage -> `SETTLED` (exact `settled_tokens`), unknown usage -> `RECONCILIATION_PENDING`
  (reservation retained, never released, never fabricated as zero). `ProviderRefusal` carries usage and never drops
  it. There is still NO success Result Artifact on these paths.
- Overages remain controlled reconciliation (Day52's `settle_overage`, never a `min()` truncation). Day53 never
  fabricates zero cost.

```text
CostState: RESERVED -> SETTLED (usage known, success OR known-usage failure)  |  RECONCILIATION_PENDING (usage unknown; reservation retained)
JobStatus: RUNNING -> SUCCEEDED (valid output, guarded)  |  FAILED (definite non-success: validation/refusal/incomplete)
                    -> PENDING_RECONCILIATION (timeout: unknown execution/usage; NOT terminal; a matching late result may still complete)
Pre-call:  execute_job GATES on eligibility (only RUNNING may start a paid call; SUCCEEDED/FAILED/PENDING_RECONCILIATION
           -> PRECALL_BLOCKED, 0 transport calls) then binds to the contract (mismatch -> CONTRACT_MISMATCH, no call)
Late result: ingest_late_outcome(outcome, correlation) accepts an already-issued outcome WITHOUT any Adapter/transport call
```

---

## 7. Error semantics

- A Provider TIMEOUT means whether the Provider ran, its result, and its usage are all UNKNOWN. It does NOT write a
  definite terminal `FAILED` (that would block a legitimate late result and invite an unprotected re-run). It moves the
  Job to a non-terminal `PENDING_RECONCILIATION` lifecycle, retains the reservation (`reconciliation_pending`, never
  zero, never auto-released), records safe correlation evidence, and triggers NO Day56 retry. A later contract-matching
  legitimate result is accepted via the LATE-OUTCOME INGESTION path (`ingest_late_outcome`, section 5A) — NOT by calling
  `execute_job` again (that would issue a second paid Provider call). Guarded completion accepts a `RUNNING` OR
  `PENDING_RECONCILIATION` job; a terminal `SUCCEEDED`/`FAILED` job still yields zero rows.
- Provider REFUSAL is a classified non-success outcome, not an empty success.
- Provider 401/403 is a configuration/authentication failure: STOP new calls using the affected Provider
  configuration (`ProviderConfig.disable`) and preserve safe operational evidence. It is NOT a user-input error.
- Provider 429 after a durable 202 is a downstream Job/Attempt event, NOT a retroactive HTTP 429 for the original
  client. Preserve safe `Retry-After`/request metadata if supplied; Day56 owns retry/backoff policy.
- A 400 unsupported model/schema is a capability/configuration failure, not user input error. Distinguish a
  CONFIG-WIDE capability failure (`ProviderCapabilityError.config_scope=True` — this model/profile cannot honor the
  controlled schema) from a single-request 400: a config-wide failure fails the `ProviderConfig` CLOSED
  (`disable`) so no further NEW call uses it, while a single-request 400 does NOT close the config. Both keep safe
  schema/model/profile/correlation + request-id evidence; neither invalidates an already-issued in-flight result that
  satisfies its persisted contract.
- Reuse a lifespan-owned SDK client per process; do not create a client per `generate()` call. Drain before close. No
  cross-process singleton behavior is claimed.

---

## 8. Raw-data minimization

- Do NOT default-persist raw Provider responses into Result Artifacts. Persist the validated domain result, schema
  name/version, safe Provider metadata (approved model, provider profile version, provider request ID), safe failure
  classification, correlation IDs, and actual-usage/reconciliation state.
- Any future forensic raw-evidence store needs explicit minimization, redaction, access control, retention, and
  audit; it is not part of the normal Artifact.

---

## 9. Integrated rollout/rollback exercise — configuration rollback != business-fact rollback

Scenario: a rollout changes the default model to one that does not support `research_summary.v1`; NEW calls get 400,
an OLD in-flight call later returns a valid v1 result, and another times out with unknown usage.

- Stop new calls using the erroneous Provider/model configuration (disable the config).
- Mark 400 Attempts as Provider capability/configuration failures; retain `job_id`, `attempt_id`, schema version,
  Provider request ID, and safe classification.
- Roll back to a validated model configuration and verify readiness before resuming.
- Validate a legitimate OLD in-flight v1 result against THAT Job's persisted execution contract and accept it only
  through guarded completion.
- For timed-out Jobs, inspect persisted facts + Provider correlation; retain the reservation and hold
  `reconciliation_pending` when usage is unknown.

Correction: a single unsupported-structured-output request cannot BOTH return 400 AND a valid result — the valid
result belongs to a distinct pre-rollout / old-worker in-flight request. **Configuration rollback affects future
calls; it does not invalidate an already-issued call that satisfies its persisted contract, and it is not a rollback
of durable business facts.**

---

## 10. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| SDK types stay inside the Adapter; typed ProviderOutcome union | RUN (in-memory) | `OpenAICompatibleAdapter.generate`; each fake SDK error -> a union case |
| Pre-call execution gate before any paid call | RUN (in-memory) | terminal/pending Job re-execute -> PRECALL_BLOCKED, transport calls == 0 (no second paid call) |
| Provider call bound to the persisted contract (no trusted caller input) | RUN (in-memory) | `bind_request_to_contract`; tampered model/schema/version -> CONTRACT_MISMATCH, 0 transport calls; max tightened never enlarged |
| Late-outcome ingestion (no adapter call): matching completes, mismatch rejected, terminal no-op | RUN (in-memory) | `ingest_late_outcome`; correlation-matched success completes; wrong correlation -> LATE_OUTCOME_REJECTED; terminal -> COMPLETION_NOOP; 0 transport calls |
| One lifespan-owned client reused; Job cap wins (5000 vs 8000) | RUN (in-memory) | transport call count + `last_max_tokens` |
| REAL strict structured validation before side effects | RUN (real Pydantic v2) | missing `citations` / forbidden `debug_prompt` -> CONTRACT_VIOLATION |
| Invalid output never calls completion | RUN (in-memory) | no success transition / Artifact / Event on invalid |
| Valid output completes once; guarded zero-row stops | RUN (in-memory) | one `job.succeeded`; second attempt -> NOOP_ZERO_ROWS, no overwrite |
| Success with unknown usage: succeed + reconciliation_pending | RUN (in-memory) | separate business/cost axes; usage None retained, not zero |
| Known-usage non-success settles exact usage; refusal usage not dropped | RUN (in-memory) | `record_cost` on validation-fail/incomplete/refusal; known -> SETTLED, unknown -> reconciliation_pending |
| Timeout is non-terminal; a matching late result completes via INGESTION | RUN (in-memory) | PENDING_RECONCILIATION (not FAILED); reservation retained; late result accepted by `ingest_late_outcome` with 0 new transport calls |
| Config-wide capability 400 fails the config closed; single 400 does not | RUN (in-memory) | `config_scope` disables ProviderConfig + blocks next call before transport; single-request 400 keeps it enabled |
| Refusal / incomplete / timeout / auth / 429 / capability classification | RUN (in-memory) | ExecutionDecision per outcome; auth disables config; 429 keeps Retry-After |
| Server-owned versioned schema binding (no cross-version satisfaction) | RUN (real Pydantic v2) | v2 payload fails v1 Job; unknown version -> SCHEMA_NOT_FOUND |
| Raw minimization: no prompt/secret/raw fields persisted or logged | RUN (in-memory) | serialized artifact+events exclude prompt/api_key/debug_prompt |
| Config rollback != business rollback | RUN (in-memory) | bad-model 400 for new calls; valid old in-flight v1 still accepted |
| Real `openai` SDK / network / Provider | NOT RUN | fake injected transport; no real key or paid call |
| Real PostgreSQL / Redis / Celery / FastAPI wire / integration / production | NOT RUN | in-memory model only |

`In-memory control-flow + real Pydantic validation do not prove the real openai SDK, network, Provider, PostgreSQL
transactions/isolation, Redis, Celery Worker execution, FastAPI wire behavior, integration, or production.`

---

## 11. Schema honesty

The persisted execution-contract facts (`schema_name/version`, `approved_model`, `provider_profile_version`,
`task_type`, `max_output_bound`, `correlation_id`), the Result Artifact shape, and the per-Job cost-reconciliation
state are MODELED in-memory here. A real deployment adds any new columns via a Day48-safe FORWARD additive migration
(never a rewrite of published history). The Day52 reservation/reconciliation is reused, not re-implemented.

---

## 12. Boundaries preserved (not implemented here)

Day54 consumes this Provider-call boundary but distinguishes HTTP connection, Provider request, and durable Job
lifecycles (a client disconnect is not cancellation). Day55 runs long Provider work in Celery Workers without
bypassing Day52 authorization/quota/audit/idempotency or Day53 output validation. Day56 owns retry/backoff,
degradation, and backpressure. None of these are implemented or claimed in Day53.
