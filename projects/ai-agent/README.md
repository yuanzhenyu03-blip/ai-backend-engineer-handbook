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
│   ├── recovery_cost.py           # Day76: classified fallback + cost reservation/settlement/reconciliation
│   ├── fake_provider_testing.py   # Day77: FakeClock + controlled transport + independent golden evidence
│   ├── application_runtime.py     # Day78: integrated orchestration and lifecycle checkpoint
│   ├── agent_loop.py              # Day79: application-owned deterministic Agent control loop
│   ├── tool_governance.py         # Day80: Tool visibility/schema/permission governance
│   ├── agent_state_machine.py     # Day81: state, termination, loop/fence/budget guards
│   ├── durable_agent_jobs.py      # Day82: checkpoint validation + classified durable recovery
│   ├── human_control.py           # Day83: approval/interrupt/escalation conditional boundary
│   └── human_control_scenarios.py # Day83: fixtures composing existing runtime seams
├── tests/
│   ├── test_provider_adapters.py # Day72: 58 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_prompt_contracts.py  # Day73: 39 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_output_tool_contracts.py # Day74: 34 deterministic EXECUTED_LOCAL_RUNTIME tests
│   ├── test_streaming_cache_batching.py # Day75: 41 deterministic boundary tests
│   ├── test_day76_routing_recovery.py # Day76: deterministic routing/recovery/cost boundary tests
│   ├── test_day77_fake_provider_contract_regression.py # Day77: shared contracts + semantic regressions
│   ├── test_day78_application_runtime.py # Day78: integrated Runtime checkpoint
│   ├── test_day79_agent_loop.py   # Day79: decisions, replay guards + Day78 composition
│   ├── test_day80_tool_governance.py # Day80: governed visibility, binding + boundary reuse
│   ├── test_day81_agent_state_machine.py # Day81: transitions, reservations + stale fences
│   ├── test_day82_durable_agent_jobs.py # Day82: resume/retry/reconcile/outbox/fence cases
│   ├── test_day83_human_control.py # Day83: 50 human-control tests
│   └── test_day83_seed_grader.py  # Day83: 3 grader tests
├── evals/                        # Day83: 26 version-1 seed cases + deterministic runner
├── examples/                     # Day83: cumulative runnable checkpoint
├── evidence/                     # Day83: historical and repository-update run records
└── docs/                         # Day71–Day83 designs + classroom records
```

## Progress

Status: Phase 7A complete; Phase 7B in progress at classroom scope (Day71–Day83 documented; deterministic
`EXECUTED_LOCAL_RUNTIME` from Day72 onward).

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

Day77 — Fake Provider, Contract Tests and LLM Regression Tests — adds a deterministic Fake transport behind
both real Day72 Adapters, a separately injected minimized call log, an explicit response gate, `FakeClock`,
one shared stable-`ProviderOutcome` Contract Test suite and semantic regressions across Day73–Day76. See
[`docs/DAY77_FAKE_PROVIDER_CONTRACT_REGRESSION_TESTS.md`](docs/DAY77_FAKE_PROVIDER_CONTRACT_REGRESSION_TESTS.md)
and [`docs/day77-fake-provider-contract-tests-llm-regression-classroom-draft.md`](docs/day77-fake-provider-contract-tests-llm-regression-classroom-draft.md).
Code: `src/fake_provider_testing.py`; tests: `tests/test_day77_fake_provider_contract_regression.py`.
Evidence: 31 Day77 deterministic tests, 221 cumulative Day72–Day77 tests (Python 3.11.5). No real SDK,
HTTP, Provider, database, queue/Worker, external tool or billing system; INTEGRATION_RUNTIME and PRODUCTION
are NOT RUN. Provider A/B and v6 are fictional fixtures; the independent call log is in-process evidence,
not crash-durable infrastructure.

Day78 — LLM Application Runtime Capstone, Checkpoint and English Interview — composes the existing public
seams into an application-owned orchestration boundary. See
[`docs/DAY78_LLM_APPLICATION_RUNTIME_CAPSTONE.md`](docs/DAY78_LLM_APPLICATION_RUNTIME_CAPSTONE.md) and the
[`classroom record`](docs/day78-llm-application-runtime-capstone-classroom-draft.md). Code:
`src/application_runtime.py`; tests: `tests/test_day78_application_runtime.py`. Evidence: 22 Day78 tests and
243 cumulative Day72–Day78 deterministic tests (Python 3.11.5). Real Provider/HTTP/database/queue/Worker,
durable fencing, protected candidate storage, external tool/compensation, billing, integration runtime and
production are NOT RUN. Day79 may drive this stable Runtime but must not reimplement its boundaries.

Day79 — Framework-agnostic Agent Loop and Control Flow — adds an application-owned Controller above Day78:
a pure `CONTINUE`/`COMPLETE`/`WAIT`/`FAIL`/`RECONCILE` decision, deterministic causal identities,
terminal/duplicate/stale guards, an injected Runtime port and a real in-process Day78 preparation bridge. See
[`docs/DAY79_FRAMEWORK_AGNOSTIC_AGENT_LOOP.md`](docs/DAY79_FRAMEWORK_AGNOSTIC_AGENT_LOOP.md) and the
[`classroom record`](docs/day79-framework-agnostic-agent-loop-control-flow-classroom-draft.md). Code:
`src/agent_loop.py`; tests: `tests/test_day79_agent_loop.py`. Evidence: 8 Day79 / 251 cumulative deterministic
tests on Python 3.11.5. The
count-based Goal fixture is not a production semantic evaluator. Durable state/fencing, real Provider/Tool/
framework, Day80 Tool governance, Day81 budgets/loop detection, Day82 durability, integration runtime and
production are NOT RUN.

Day80 — Tool Registry, Tool Schema and Permission Model — adds an application-owned Tool governance layer
between Day79 planning and existing Day74/Day66/Day78 boundaries: deterministic context-scoped capability
Snapshots, permission-narrowed Schema projection, exact candidate binding, current Registry/Permission
recheck, deny-overrides policy composition, Snapshot-only Framework translation and a Safe Tool Result gate.
See [`docs/DAY80_TOOL_REGISTRY_SCHEMA_PERMISSION_MODEL.md`](docs/DAY80_TOOL_REGISTRY_SCHEMA_PERMISSION_MODEL.md)
and the [`classroom record`](docs/day80-tool-registry-schema-permission-model-classroom-draft.md). Code:
`src/tool_governance.py`; tests: `tests/test_day80_tool_governance.py`. Evidence: 22 Day80 / 273 cumulative
deterministic tests on Python 3.11.5-compatible `python3.11`. The Day66 composition calls its real local pure
validation boundary, not a browser integration. Real Provider/Framework/HTTP/PostgreSQL/queue/Worker/
Playwright, Day82 durability, integration runtime and production are NOT RUN.

Day81 — Agent State Machine, Termination, Loop Detection and Step/Token/Cost Budgets — adds explicit
application-owned lifecycle and ordered guards above Day79/Day80. A pure decision returns a structured candidate;
the in-memory authoritative boundary conditionally checks Job/Step/Attempt, state and fence, then applies state and
Step/token/cost reservations once. `WAITING` remains distinct from `PENDING_RECONCILIATION`; unknown external
outcomes keep original identity and held capacity; verified hard loops use `NO_PROGRESS_LOOP_DETECTED`; completion
has priority over exhaustion once the Goal is verified. See
[`docs/DAY81_AGENT_STATE_MACHINE_TERMINATION_LOOP_BUDGETS.md`](docs/DAY81_AGENT_STATE_MACHINE_TERMINATION_LOOP_BUDGETS.md)
and the [`classroom record`](docs/day81-agent-state-machine-classroom-draft.md). Code:
`src/agent_state_machine.py`; tests: `tests/test_day81_agent_state_machine.py`. Evidence: 20 Day81 / 293
cumulative deterministic tests on Python 3.11.5. Python 3.12, real PostgreSQL conditional transactions,
Outbox/queue, Provider/Tool/billing/distributed worker, integration runtime and production are NOT RUN.

Day82 — Durable Agent Jobs, Checkpoint, Resume and Recovery — turns Day81's bounded in-process lifecycle into
an explicit durable recovery contract. A Checkpoint binds Job/Step/Attempt, state version, fence token and
immutable execution bindings; a new Worker must reread and validate those facts before acting. Resume keeps the
original Attempt, retry creates a new identity only after classification and current authorization, and unknown
external execution keeps the original operation and reservation in `PENDING_RECONCILIATION`. The modeled
authoritative apply records checkpoint, reservation change, audit evidence and Outbox intent together; an
independent dispatcher rescans unpublished intents and consumers deduplicate at-least-once delivery. Lease
takeover advances the fence, so stale results cannot mutate current state but remain evidence. See
[`docs/DAY82_DURABLE_AGENT_JOBS_CHECKPOINT_RESUME_RECOVERY.md`](docs/DAY82_DURABLE_AGENT_JOBS_CHECKPOINT_RESUME_RECOVERY.md)
and the [`classroom record`](docs/day82-durable-agent-jobs-classroom-draft.md). Code:
`src/durable_agent_jobs.py`; tests: `tests/test_day82_durable_agent_jobs.py`. Evidence: 32 Day82 / 325 cumulative
deterministic tests on Python 3.11.5. Python 3.12, real PostgreSQL transactions, real Outbox Relay/Broker/Worker,
process crash/restart, multi-process fencing, Provider/Tool/billing integration and production are NOT RUN.

## Day83 — Human control and mandatory runnable checkpoint

The [Day83 lesson](../../docs/fastapi/day83-human-approval-interrupt-and-escalation-boundaries.md) adds exact,
time-limited human approval within current authorization, guarded local apply/Outbox, separate dispatch
claim, interrupt/fence/late evidence and bounded escalation. It reuses the existing Day74/78/79/80/81/82 seams,
not a separate demo. See the [design](docs/DAY83_HUMAN_APPROVAL_INTERRUPT_ESCALATION.md),
[actual classroom record](docs/day83-human-control-classroom-draft.md) and
[repository validation](evidence/day83-repository-validation.json).

From this directory, using the classroom's Python3.11 interpreter:

```sh
PYTHONPATH=src python3.11 -m unittest discover -s tests -p 'test_day83*.py' -v
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
PYTHONPATH=src python3.11 evals/run_day83_seed_eval.py
PYTHONPATH=src python3.11 examples/day83_human_control_checkpoint.py
```

Python3.11.5:53 focused tests (50 control +3 grader),378 cumulative tests,26/26 version-1 seed scenarios and
checkpoint PASS. [Historical exact commands/hashes](evidence/day83-validation.json) are retained separately
from update-time reruns. The seed runner compares structured decisions/evidence/forbidden effects, not LLM
quality; independently reviewing every expected fact remains a release obligation.

Only local synthetic services and Tool effects ran. The store is RLock/snapshot-based, trusted facts are
fixtures, initial approval requests are seeded and escalation alerts are intents. Python3.12, real auth/UI/
callback, PostgreSQL transaction/restart persistence, Relay/Queue/Worker/cross-process fencing, Provider,
external Tool/billing/compensation and alert delivery remain NOT RUN. The real Provider gate is optional,
NOT RUN, and requires immediate explicit authorization before a bounded call.

Teaching is complete at guided classroom scope. The final Chinese summary was instructor-authored at the
student's request; independent synthesis was not assessed. Day84 is next, not started.

## Future Milestones

- Add Day84 conversation memory versus durable business-state boundaries without treating remembered consent as authority.
- Independently assess Day83 final synthesis and review seed expectations before a release gate.
- Validate Python3.12 and real auth/DB/queue/Worker integration; the optional real Provider gate remains NOT RUN.
- Add integration tests with mocked model responses.
- Add deployment notes.
