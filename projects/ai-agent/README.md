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
├── tests/
└── docs/
```

## Progress

Status: Phase 7A foundations in progress (Day71 released — CONCEPTUAL + STATIC only).

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

Current focus: Day72 — Provider Capabilities and the Replaceable Provider Adapter (evolves this same
Artifact; do not pre-implement it here).

## Future Milestones

- Add tool registry prototype.
- Add agent service layer.
- Add integration tests with mocked model responses.
- Add deployment notes.
