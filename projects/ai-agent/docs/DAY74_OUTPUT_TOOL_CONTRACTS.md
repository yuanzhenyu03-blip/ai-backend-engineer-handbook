# Day74 — Output Contracts and Permissioned Tool Calling (Phase 7A)

> Evidence tier — Day74 is **CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME**: 34 deterministic Day74
> in-process tests, with the Day72/Day73 suites still passing (131 total, Python 3.11.5). `INTEGRATION_RUNTIME`
> and `PRODUCTION` are **NOT RUN**. There is no real Provider/SDK/HTTP/database/queue/tool side effect. The
> schema validator is a documented teaching subset, not a standards-compliant JSON Schema engine.

## Scope

Day73 settled the versioned input boundary before Provider dispatch. Day74 owns the other side: parse an
untrusted Provider candidate, validate its output/tool contract, authorize it using trusted application
context, admit exactly one server-normalized command, execute behind an idempotency boundary, verify the
untrusted tool outcome, and allow only a current verified result to complete durable business state.

## Files

```text
projects/ai-agent/
├── src/output_tool_contracts.py        # schema subset, Registry, Admission, Executor, verification, completion
├── tests/test_output_tool_contracts.py # 34 deterministic Day74 tests
└── docs/
    ├── DAY74_OUTPUT_TOOL_CONTRACTS.md
    └── day74-output-tool-contracts-classroom-draft.md
```

## 1. Core boundary

```text
Day73 immutable Prompt/Attempt binding
        |
        v
Provider Response (untrusted candidate)
        -> Parse
        -> Schema Validation
        -> Tool Registry resolution
        -> Application Authorization
        -> tenant-scoped Semantic Validation
        -> Tool Admission
        -> immutable AdmittedToolCall
        -> lifecycle guard + idempotency claim
        -> Tool Execution
        -> Outcome Schema/Semantic/Identity Verification
        -> VERIFIED candidate
        -> Durable guarded completion / reconciliation
```

The conceptual layers stay distinct even when secure implementation order changes. This Artifact performs
coarse server-side authorization before querying tenant-scoped report state, avoiding a cross-tenant resource
existence oracle.

## 2. JSON and the controlled schema subset

`json.loads` turns text into a Python value. It does not make the value trusted. The Day74 validator supports
only the keywords exercised in class:

- `type`
- `properties`
- `required`
- `enum`
- `minimum` / `maximum`
- `minLength` / `maxLength`
- `items`
- `additionalProperties`

An unsupported keyword raises `ValueError` instead of being silently ignored. `bool` is not accepted as an
integer/number even though Python's `bool` subclasses `int`. Recursive object and array validation reports
deterministic paths. This is **not** a full JSON Schema draft implementation and does not prove Provider-native
Structured Output behaviour.

Three contracts are explicit:

- `TOOL_CALL_ENVELOPE_SCHEMA`: candidate kind, call identity, exact tool name/version and arguments.
- `PUBLISH_REPORT_V1_ARGUMENTS_SCHEMA`: strict `tenant_id` + `report_id`, no `force` or unknown field.
- `PUBLISH_REPORT_V1_OUTCOME_SCHEMA`: operation identity, published flag, nested report identity/version,
  bounded string warnings and optional bounded error.

Passing Schema proves only shape. It proves neither semantic consistency, tenant ownership, authorization,
tool admission, execution, nor business completion.

## 3. Tool Definition, Registry and lifecycle

`ToolDefinition` declares an application-owned exact `(name, version, arguments_schema)` fact. It is not an
execution capability. `ToolRegistry` rejects duplicate definitions, distinguishes unknown tool from known
name/incompatible version, and maintains an operational lifecycle overlay. Unknown or disabled versions fail
closed.

A disable has two containment points:

1. before Admission: `TOOL_DISABLED`, no `AdmittedToolCall`;
2. after Admission but before execution: Executor final guard returns `REJECTED_DISABLED`, no simulated effect.

The in-process `active_execution_guard` serializes this test model. A production service must not hold a
process lock or database transaction across a long external HTTP call. It needs a durable conditional claim,
lifecycle epoch/fencing design, and external idempotency where supported.

## 4. Authorization and semantic validation

`AuthContext` is trusted server context. Model arguments are not identity evidence. Admission rejects:

- a model `tenant_id` that differs from `AuthContext.tenant_id`;
- a role other than `publisher`;
- a missing or non-draft report under the already-authorized tenant.

Missing and non-publishable reports return the same safe reason, `REPORT_NOT_PUBLISHABLE`. Prompt text, valid
JSON, a valid Schema, or model confidence can never expand authority.

## 5. Admission and immutable command

`admit_tool_call` performs no tool execution. A successful decision contains a frozen `AdmittedToolCall` with:

- `attempt_id`, `job_id`, `tool_call_id`;
- exact `tool_name` and `tool_version`;
- server-owned `tenant_id`;
- server-resolved `report_id` and expected report version;
- a server-generated SHA-256 idempotency key over logical publish identity.

The Executor accepts only this type. It never accepts the Provider's raw Python `dict`. Re-prompting or retrying
does not mutate the rejected candidate; policy must create a new explicit Attempt.

## 6. Execution and idempotency

`InMemoryToolExecutor` uses a lock-protected operation map as an atomic-claim model. Sequential and eight-worker
concurrent duplicates produce one simulated effect; later calls return `DUPLICATE_SUPPRESSED` with the original
operation ID.

This proves deterministic in-process behavior only. Production needs a durable unique constraint or conditional
`UPDATE ... WHERE ... RETURNING`, cross-process ownership/lease rules, and reconciliation. An external service
may already have accepted a request when the local transaction rolls back; local rollback is not external undo.

## 7. Outcome Verification and guarded completion

`verify_publish_outcome` is pure: it parses and validates the candidate outcome, rejects contradictory
`published=true` plus `error`, and binds `operation_id`, `report_id`, and report version to the admitted call.
It returns `OutcomeDecision(VERIFIED, ...)`; it does not write `SUCCEEDED`.

`InMemoryDurableStore.guarded_complete` separately checks:

- current job identity;
- current Attempt and tool-call identity;
- nonterminal state;
- verified outcome.

Only then is `SUCCEEDED` committed. Superseded results are `NOOP_STALE`; cancelled/already-completed results are
`NOOP_TERMINAL`; unverified candidates are rejected. A fully matching late result may complete a job that is
still `PENDING_RECONCILIATION`.

## 8. Timeout unknown and incident recovery

Dispatch followed by timeout is not a known failure. `mark_timeout_unknown` moves the matching nonterminal job
to `PENDING_RECONCILIATION`. Blind retry risks duplicate publication.

Recovery uses durable and authoritative evidence:

- dispatch marker and Provider request ID for correlation only;
- operation/idempotency claim and tool-call state;
- authoritative external report version/status and audit evidence.

Incident actions are distinct:

- **reject** — refuse a candidate at a boundary;
- **re-prompt** — create a new policy-controlled Attempt;
- **disable/rollback** — stop new harm without rewriting historical bindings;
- **repair** — correct internal durable facts through explicit transitions;
- **compensation** — a new authorized, idempotent operation countering a confirmed reversible effect;
- **reconciliation** — recover truth when the execution result is unknown.

Original execution and incident evidence remain append-only/auditable.

## 9. Bad-v2 containment exercise

A defective `publish_report@v2` accepted `force: true` and bypassed the already-published guard:

| Attempt | Durable evidence | Action |
|---|---|---|
| A1 | v2-bound, not admitted | block; create a new safe Attempt only if policy requires the work |
| A2 | v2 admitted, not executed | final kill switch rejects with zero effect |
| A3 | duplicate publish confirmed | controlled repair/compensation if reversible; preserve evidence |
| A4 | dispatched, timeout unknown | `PENDING_RECONCILIATION`; no blind retry |
| A5 | safely v1-bound, in flight | continue under v1; do not bulk rewrite/cancel |

Disable is containment, not proof of full recovery. Close the incident only after each affected Attempt has a
known terminal outcome or an explicit continuing recovery state and any compensation is verified.

## 10. Responsibility map

| Owner | Responsibility | Must not do |
|---|---|---|
| Prompt Contract (Day73) | version application messages/variables/guarantees | authorize a tool side effect |
| Output Contract | constrain candidate structure | claim semantics or permission |
| Provider Adapter (Day72) | Provider-specific translation/failure normalization | execute application tools |
| LLM Runtime | Attempt binding and candidate-processing flow | treat Provider SUCCESS as business truth |
| Tool Registry | exact allowed identity/version/lifecycle | trust a model-selected unknown version |
| Application Authorization | trusted tenant/user/role/ownership | derive authority from arguments |
| Tool Admission Gate | allow one validated candidate invocation | pass raw model data to Executor |
| Tool Executor | execute an admitted command behind claim/fence | decide final Job success alone |
| Outcome Verifier | produce a verified candidate | mutate durable completion state |
| Durable Store | guarded completion/reconciliation truth | accept stale/terminal/unverified results |

## 11. Validation status

| Tier | Status | Evidence |
|---|---|---|
| `CONCEPTUAL` | Completed | progressive JSON/schema/tool boundary, responsibility map, A1–A5 incident exercise, interviews |
| `STATIC` | `PASS` | `py_compile` for 4 modules + 3 test files; `mypy` reports no issues in 7 files |
| `EXECUTED_LOCAL_RUNTIME` | `PASS` | `python3.11 -m unittest discover -s tests -v` -> 131 OK: 34 Day74 + 39 Day73 + 58 Day72, Python 3.11.5 |
| Python 3.12 | `NOT RUN` | no `python3.12` executable was available in the update environment |
| `INTEGRATION_RUNTIME` | `NOT RUN` | no real SDK/HTTP/Provider/database/queue/tool/reconciliation |
| `PRODUCTION` | `NOT RUN` | no credentials/customer data/sensitive prompt/production traffic |

Run:

```bash
cd projects/ai-agent
python3 -m unittest discover -s tests -v
```

## Related

- Lesson: [`docs/fastapi/day74-structured-output-json-schema-and-function-tool-calling.md`](../../../docs/fastapi/day74-structured-output-json-schema-and-function-tool-calling.md)
- Classroom record: [`day74-output-tool-contracts-classroom-draft.md`](day74-output-tool-contracts-classroom-draft.md)
- Day73 design: [`DAY73_PROMPT_CONTRACTS.md`](DAY73_PROMPT_CONTRACTS.md)
- Day72 design: [`DAY72_PROVIDER_ADAPTER.md`](DAY72_PROVIDER_ADAPTER.md)
