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
│   └── provider_adapters.py      # Day72: concrete Provider A/B adapters + RecordingTransport + dispatch
├── tests/
│   └── test_provider_adapters.py # Day72: 21 deterministic EXECUTED_LOCAL_RUNTIME tests
└── docs/                          # Day71 foundations + Day72 provider-adapter design + classroom drafts
```

## Progress

Status: Phase 7A in progress (Day72 released — CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; Day71 released earlier).

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
CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME — `python3 -m unittest discover -s tests -v` → 21 deterministic
in-process tests OK (Python 3.10.12); `INTEGRATION_RUNTIME` and `PRODUCTION` are NOT RUN (no real SDK/HTTP,
Provider, PostgreSQL, credentials, or paid call). Provider A/B are fictional classroom fixtures; every
capability is a current, versioned fact bound to a Capability Profile revision. The full Fake Provider/LLM
regression suite remains Day77 scope.

Current focus: Day73 — Prompt Contracts, Prompt Versioning and Compatibility (evolves this same Artifact on
the stable Provider surface; do not pre-implement it here).

## Future Milestones

- Add tool registry prototype.
- Add agent service layer.
- Add integration tests with mocked model responses.
- Add deployment notes.
