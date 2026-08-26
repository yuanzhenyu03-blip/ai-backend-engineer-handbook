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
│   ├── output_tool_contracts.py  # Day74: output schema + permissioned tool admission/execution/completion
│   ├── streaming_cache_batching.py # Day75: complete streaming + safe cache reuse + per-item batching
│   ├── routing_policy.py          # Day76: eligibility-first route selection + immutable decision evidence
│   └── recovery_cost.py           # Day76: classified fallback + cost reservation/settlement/reconciliation
├── tests/
│   ├── test_provider_adapters.py # Day72: 58 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_prompt_contracts.py  # Day73: 39 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_output_tool_contracts.py # Day74: 34 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_streaming_cache_batching.py # Day75: 41 deterministic boundary tests
│   └── test_day76_routing_recovery.py # Day76: deterministic routing/recovery/cost boundary tests
└── docs/                          # Day71–Day76 released designs + classroom records
```

## Progress

Status: Phase 7A in progress (Day76 released — CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; Day71–Day75 released earlier).

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

Day75 — Streaming, Caching and Batching for LLM Applications — adds exact identity/sequence/buffer/completion
stream assembly, versioned tenant/auth-aware response caching with TTL/resource-version/current-auth checks,
cached-candidate re-admission through Day74, and compatible bounded/fair batching with per-item pre-dispatch
fences, exact result mapping and retry/reject/reconcile recovery. See
[`docs/DAY75_STREAMING_CACHING_BATCHING.md`](docs/DAY75_STREAMING_CACHING_BATCHING.md) and
[`docs/day75-streaming-caching-batching-classroom-draft.md`](docs/day75-streaming-caching-batching-classroom-draft.md).
Code: `src/streaming_cache_batching.py`; tests: `tests/test_streaming_cache_batching.py`. Evidence: CONCEPTUAL
+ STATIC + EXECUTED_LOCAL_RUNTIME — 41 Day75 deterministic in-process tests; 172 cumulative with 131
Day72–Day74 regression tests (Python 3.11.5). No real Provider/SSE/HTTP/Redis/PostgreSQL/queue/Worker/external tool;
INTEGRATION_RUNTIME and PRODUCTION are NOT RUN.

Day76 — Model Routing, Fallback, Latency and Cost Engineering — adds eligibility-first selection over Day72
Capability Profiles, a server-owned/versioned Routing Policy, immutable per-Attempt RoutingDecision evidence,
classified retry/fallback/reject/disable/reconcile decisions, explicit latency boundaries and guarded cost
estimate/reservation/actual/unknown settlement. See
[`docs/DAY76_MODEL_ROUTING_FALLBACK_LATENCY_COST.md`](docs/DAY76_MODEL_ROUTING_FALLBACK_LATENCY_COST.md) and
[`docs/day76-model-routing-fallback-latency-cost-classroom-draft.md`](docs/day76-model-routing-fallback-latency-cost-classroom-draft.md).
Code: `src/routing_policy.py`, `src/recovery_cost.py`; tests: `tests/test_day76_routing_recovery.py`. Evidence is
CONCEPTUAL + STATIC + deterministic EXECUTED_LOCAL_RUNTIME with all Day72–Day75 regressions. There is no real
Provider, HTTP/SSE, database, queue/Worker, external tool, live health/pricing/latency service, credential,
customer data or production traffic; INTEGRATION_RUNTIME and PRODUCTION are NOT RUN.

Current focus: Day77 — Fake Provider, Contract Tests and LLM Regression Tests. Day76 does not pre-implement
that full suite.

## Future Milestones

- Add tool registry prototype.
- Add agent service layer.
- Add integration tests with mocked model responses.
- Add deployment notes.
