# Repository Update Report

## Lesson

Day: Day94

Title: Agent + MCP Integration Capstone and English Interview

Status: Completed at guided classroom scope; Phase 7B complete;
`RESTART_RECOVERY_RUNTIME`; production readiness `MORE_EVIDENCE_NEEDED`

## Files Added

- `docs/fastapi/day94-agent-mcp-integration-capstone-and-english-interview.md`
- `projects/ai-agent/src/agent_mcp_capstone.py`
- `projects/ai-agent/src/agent_mcp_orchestrator.py`
- `projects/ai-agent/src/agent_mcp_recovery.py`
- `projects/ai-agent/src/pydantic_ai_capstone_adapter.py`
- `projects/ai-agent/tests/test_day94_agent_mcp_capstone.py`
- `projects/ai-agent/tests/test_day94_agent_mcp_sdk_integration.py`
- `projects/ai-agent/tests/test_day94_restart_recovery_integration.py`
- `projects/ai-agent/tests/test_day94_seed_grader.py`
- `projects/ai-agent/tests/fixtures/day94_restart_worker.py`
- `projects/ai-agent/evals/day94_agent_mcp_capstone_seed.jsonl`
- `projects/ai-agent/evals/run_day94_seed_eval.py`
- `projects/ai-agent/examples/day94_agent_mcp_capstone.py`
- `projects/ai-agent/research/day94-agent-mcp-capstone-evidence.jsonl`
- `projects/ai-agent/evidence/day94-validation.json`
- `projects/ai-agent/docs/DAY94_AGENT_MCP_CAPSTONE.md`
- `projects/ai-agent/docs/day94-agent-mcp-capstone-classroom-draft.md`
- `projects/ai-agent/docs/DAY94_TO_DAY95_HANDOFF.md`
- `projects/ai-agent/docs/DAY94_REPOSITORY_UPDATE_REPORT.md`

## Files Updated

- `projects/ai-agent/src/mcp_authorization.py`
- `projects/ai-agent/src/mcp_retry_policy.py`
- `README.md`
- `projects/ai-agent/README.md`
- `cheat_sheets/fastapi.md`
- `interview/fastapi.md`
- `CURRICULUM.md`
- `ROADMAP.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

`DECISIONS.md` was intentionally unchanged: Day94 composes Decisions 009–014 and did not introduce a new
long-lived architectural choice.

## Main Classroom Content Preserved

- model/Framework output is a proposal, never authorization or durable success;
- approval and current authorization remain separate typed decisions;
- operation/idempotency/tenant/resource/Tool identity stays stable across attempts;
- attempt/request/generation identity stays distinct from state/version/fence concurrency facts;
- an exact durable dispatch marker precedes transport handoff;
- candidate result requires correlation, protocol validation, output validation and the sole Committer;
- timeout, cancellation and process death do not prove non-execution;
- recovery queries authority without replaying the original Tool;
- eventual-consistency `NOT_FOUND` remains pending;
- only committed authoritative non-execution may reach retry policy;
- telemetry diagnoses but never becomes authority.

## Main Misconceptions Corrected

- the Committer is not the Tool executor; it is the sole durable transition authority;
- restart does not go directly to retry policy;
- authoritative success still requires binding and validation before commit;
- Server handler and controlled Tool are distinct; the handler still returns only a candidate;
- approval cannot replace authentication or a revoked current permit;
- trace data is historical diagnostic context, not business evidence;
- end-to-end controlled success is not production readiness.

## Engineering Artifacts Produced

- application-owned proposal and stable-operation identity boundaries;
- access gate composing human and current-authorization decisions;
- current deadline/version/capability/capacity/circuit preflight;
- atomic exact-attempt dispatch claim;
- thin typed-decision Orchestrator;
- explicit candidate correlation/protocol/output pipeline;
- sole Committer with binding/attempt/state/version/fence checks;
- restart-aware journal and read-only recovery coordination;
- reconciliation and committed-non-execution retry composition;
- credential-safe operator evidence report;
- deterministic capstone example and 16-case invariant seed;
- independent Streamable HTTP and separate restart/recovery runtime tests.

## Framework Connections Added

- PydanticAI-private output translation into an application-owned proposal;
- real Python MCP SDK 2.2.0 Client/Server transport behind private Adapters;
- generation-scoped Streamable HTTP correlation;
- OpenTelemetry diagnostic boundary without Committer authority.

## AI Backend Connections Added

- safe Research Agent Tool execution for `tenant-a/report-42`;
- duplicate-side-effect prevention after timeout/restart;
- current tenant/Tool authorization before every new dispatch;
- operator-visible unknown-outcome recovery;
- Day95 ingestion/indexing handoff preserving identity, ACL and eventual-consistency rules.

## Interview Material Added

- beginner proposal/authorization, candidate/durable-success and timeout questions;
- intermediate retry identity, approval/current-authorization and recovery questions;
- senior end-to-end design, Committer placement, non-authoritative observability and production-readiness
  questions;
- actual weak-to-strong learner progression and language corrections;
- Phase 7B result: `PASS_WITH_LANGUAGE_CORRECTIONS`.

## Validation Performed

- Markdown: formal lesson contains all 16 required sections in order; changed relative links resolved.
- YAML: no YAML artifact changed.
- Code: compileall passed; 730 dependency-free tests plus 31 real-SDK/restart integration tests passed,
  761 total.
- Seeds: Day83 26/26, Day84 16/16, Day85 18/18, Day86 25/25, Day89 16/16, Day90 13/13,
  Day91 14/14, Day92 16/16, Day93 16/16 and Day94 16/16 passed.
- Runtime: real SDK Client plus independent Streamable HTTP Server covered success/timeout; separate dispatch
  and recovery processes covered restart without replay.
- JSON/JSONL: all repository AI-Agent data files parsed.
- Links: changed Markdown relative-link targets resolved.
- Secrets: private-key/API-key/Bearer-token pattern scan returned no matches.
- Git: `git diff --check` and new-file trailing-whitespace scan passed.

## Remaining TODO

- production Authorization Server/OIDC and JWKS lifecycle;
- authenticated production remote MCP deployment;
- persistent distributed operation/retry/reconciliation store;
- distributed rate limiting, capacity admission and circuit breakers;
- production telemetry backend and alert delivery;
- load, soak and backpressure testing;
- network-partition, process-crash and deployment-failure drills;
- production Tools, customer data and real Provider validation;
- Day95 Production RAG ingestion and document lifecycle.

## Suggested Commit Message

`feat(day94): add Agent MCP integration capstone`
