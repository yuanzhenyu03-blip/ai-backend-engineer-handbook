# AI Agent

## Goal

Build a production-style AI agent backend with tool calling, structured inputs, memory boundaries, and testable business logic.

## Learning Objectives

- Design tool interfaces as Python callables.
- Separate agent orchestration from domain services.
- Handle model responses safely.
- Build testable AI backend components.

## Planned Features

- Tool registry
- Tool calling flow
- Structured request and response models
- Conversation boundary design
- Logging and error handling
- Tests for tools and orchestration

## Folder Structure

```text
ai-agent/
├── README.md
├── requirements.txt
├── Dockerfile
├── src/
│   ├── provider_contract.py      # Day72: stable provider-independent surface + Capability Profile + Registry
│   ├── provider_adapters.py      # Day72: concrete Provider A/B adapters + RecordingTransport + dispatch
│   ├── prompt_contracts.py       # Day73: application-owned Prompt Contract + Attempt binding + pre-Provider gate
│   └── output_tool_contracts.py  # Day74: output schema + permissioned tool admission/execution/completion
├── tests/
│   ├── test_provider_adapters.py # Day72: 58 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_prompt_contracts.py  # Day73: 39 deterministic EXECUTED_LOCAL_RUNTIME tests
│   └── test_output_tool_contracts.py # Day74: 34 deterministic EXECUTED_LOCAL_RUNTIME tests
└── docs/                          # Day71–Day74 released designs + classroom records
```

## Progress

Status: Phase 7A in progress (Day74 released — CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; Day71–Day73 released earlier).

Day71 — LLM Application Architecture, Tokens, Context, Sampling and Model Failure Modes — added the
provider-independent LLM Application Runtime foundations for Phase 7A:
[`docs/DAY71_FOUNDATIONS.md`](docs/DAY71_FOUNDATIONS.md) (released static design contract: architecture
boundary, token/context budget, overflow policy, chunk/aggregation contract, provider-independent vs
provider-specific split, sampling policy, layered validation + failure taxonomy, recovery boundary,
Job/Attempt, guarded completion, rollback) and the raw
[`docs/day71-llm-runtime-foundations-classroom-draft.md`](docs/day71-llm-runtime-foundations-classroom-draft.md).
There is no runtime code yet: Day71 is CONCEPTUAL + STATIC; `EXECUTED_LOCAL_RUNTIME`, `INTEGRATION_RUNTIME`
and `PRODUCTION` are NOT RUN, and no real or paid Provider call was made. Provider token counts, context
sizes and sampling behaviour are versioned capabilities, not permanent facts.

Day72 — Provider Capabilities and the Replaceable Provider Adapter — makes Day71's replaceable-Adapter
boundary executable: versioned capability admission before a paid call, a replaceable `ProviderAdapter`
(Protocol + `ProviderRegistry`) that translates Provider-specific requests/responses/failures without weakening
the product contract, immutable per-Attempt execution contracts, and server-owned Profile selection. See
[`docs/DAY72_PROVIDER_ADAPTER.md`](docs/DAY72_PROVIDER_ADAPTER.md) (released design contract) and the raw
[`docs/day72-provider-adapter-classroom-draft.md`](docs/day72-provider-adapter-classroom-draft.md). Code:
`src/provider_contract.py`, `src/provider_adapters.py`, and `tests/test_provider_adapters.py`. Evidence:
CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME — `python3 -m unittest discover -s tests -v` → 58 deterministic
in-process tests OK (Python 3.10.12); `INTEGRATION_RUNTIME` and `PRODUCTION` are NOT RUN (no real SDK/HTTP,
Provider, PostgreSQL, credentials, or paid call). Provider A/B are fictional classroom fixtures; every
capability is a current, versioned fact bound to a Capability Profile revision. The full Fake Provider/LLM
regression suite remains Day77 scope.

Day73 — Prompt Contracts, Prompt Versioning and Compatibility — adds the application-owned prompt boundary
that runs *before* Day72's capability admission: immutable versioned `PromptContractRevision`s + a separate
lifecycle overlay, a durable per-Attempt `AttemptPromptBinding` (revision + renderer + parameter-policy +
application contract + input fingerprint + rendered-message hash), deterministic rendering + audit hashing,
directional structural+semantic compatibility, explicit non-mutating migration, and a fail-closed
`prepare_dispatch` Runtime gate (a binding mismatch stays PLANNED with zero Provider calls; a disabled bound
revision → BLOCKED_PROMPT_DISABLED with zero calls). See
[`docs/DAY73_PROMPT_CONTRACTS.md`](docs/DAY73_PROMPT_CONTRACTS.md) (released design contract) and the raw
[`docs/day73-prompt-contracts-classroom-draft.md`](docs/day73-prompt-contracts-classroom-draft.md). Code:
`src/prompt_contracts.py` and `tests/test_prompt_contracts.py`. Evidence: CONCEPTUAL + STATIC +
EXECUTED_LOCAL_RUNTIME — `python3 -m unittest discover -s tests -v` → 97 deterministic in-process tests OK
(39 Day73 + 58 Day72 regression, Python 3.11.5); `INTEGRATION_RUNTIME` and `PRODUCTION` are NOT RUN (no real
SDK/HTTP, Provider, database-backed store, queue/worker, encryption, or protected-artifact storage). The
`provider_calls` counter models an in-process boundary crossing only.

Day74 — Structured Output, JSON Schema and Function/Tool Calling — adds the application-owned output/tool
boundary after the Day73-bound Provider request: a documented strict JSON Schema subset, exact-version Tool
Registry + lifecycle, trusted-context authorization, tenant-scoped semantics, immutable `AdmittedToolCall`,
in-process idempotency claim + final disable guard, outcome Schema/semantic/identity verification, and guarded
completion/reconciliation. See [`docs/DAY74_OUTPUT_TOOL_CONTRACTS.md`](docs/DAY74_OUTPUT_TOOL_CONTRACTS.md) and
[`docs/day74-output-tool-contracts-classroom-draft.md`](docs/day74-output-tool-contracts-classroom-draft.md).
Code: `src/output_tool_contracts.py`; tests: `tests/test_output_tool_contracts.py`. Evidence: CONCEPTUAL + STATIC
+ EXECUTED_LOCAL_RUNTIME — 34 Day74 tests, 131 total with Day72/Day73 (Python 3.11.5). `INTEGRATION_RUNTIME`,
`PRODUCTION`, and Python 3.12 are NOT RUN. There is no real Provider/SDK/HTTP/database/queue/external tool;
the subset validator is not a full JSON Schema engine, and in-memory locks/counters are not durable or
exactly-once evidence.

Current focus: Day75 — Streaming Responses, Caching and Batching (must preserve Day74's complete validated
output, identity, authorization and guarded-completion boundaries; do not pre-implement it here).

## Future Milestones

- Add tool registry prototype.
- Add agent service layer.
- Add integration tests with mocked model responses.
- Add deployment notes.
