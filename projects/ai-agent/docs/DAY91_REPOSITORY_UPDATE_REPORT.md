# Repository Update Report

## Lesson

- Day: Day91
- Title: MCP Server Engineering: Resources, Tools and Prompts Responsibility Boundaries
- Status: Completed at guided classroom scope
- Execution evidence: `INTEGRATION_RUNTIME`
- Production readiness: `MORE_EVIDENCE_NEEDED`

## Files Added

- `docs/fastapi/day91-mcp-server-engineering-resources-tools-and-prompts-responsibility-boundaries.md`
- `projects/ai-agent/src/mcp_server.py`
- `projects/ai-agent/src/mcp_server_adapter.py`
- `projects/ai-agent/src/mcp_server_handlers.py`
- `projects/ai-agent/src/mcp_server_inventory.py`
- `projects/ai-agent/src/mcp_server_lifecycle.py`
- `projects/ai-agent/tests/fixtures/day91_mcp_stdio_server.py`
- `projects/ai-agent/tests/test_day91_mcp_server.py`
- `projects/ai-agent/tests/test_day91_mcp_server_inventory.py`
- `projects/ai-agent/tests/test_day91_mcp_server_lifecycle.py`
- `projects/ai-agent/tests/test_day91_mcp_server_sdk_integration.py`
- `projects/ai-agent/tests/test_day91_seed_grader.py`
- `projects/ai-agent/evals/day91_mcp_server_seed.jsonl`
- `projects/ai-agent/evals/run_day91_seed_eval.py`
- `projects/ai-agent/examples/day91_mcp_server_boundary.py`
- `projects/ai-agent/requirements-day91.txt`
- `projects/ai-agent/research/day91-mcp-server-evidence.jsonl`
- `projects/ai-agent/evidence/day91-validation.json`
- `projects/ai-agent/docs/DAY91_MCP_SERVER_ENGINEERING.md`
- `projects/ai-agent/docs/day91-mcp-server-classroom-draft.md`
- `projects/ai-agent/docs/DAY91_TO_DAY92_HANDOFF.md`
- `projects/ai-agent/docs/DAY91_REPOSITORY_UPDATE_REPORT.md`

## Files Updated

- `AGENTS.md`, `README.md`, `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `CHANGELOG.md`,
  `DECISIONS.md`
- `projects/ai-agent/README.md`
- `cheat_sheets/fastapi.md`
- `interview/fastapi.md`

## Main Classroom Content Preserved

- Tool is a candidate-action interface, Resource is a candidate-data interface and Prompt is a
  candidate-template interface.
- The Server Adapter converts inbound SDK requests to application-owned DTOs and maps outbound application
  decisions to MCP wire results.
- Capability, URI and Prompt text do not grant application authorization, Resource scope or system policy.
- Backpressure runs before handler entry; shutdown closes admission before draining in-flight handlers.
- Unknown outcomes preserve operation identity as `PENDING_RECONCILIATION`; they never authorize blind retry.
- Handler output remains a candidate. Day90 Client correlation, output validation and the application Committer
  remain mandatory.

## Main Misconceptions Corrected

- A Prompt message that asks to read a Resource has performed no read: render count may be one while Tool and
  Resource-call counters remain zero.
- The inbound Adapter converts MCP/SDK requests into application DTOs; conversion from application decision to
  MCP result is the outbound direction.
- `isError=true` is a Tool-level error inside a protocol result, not a JSON-RPC Protocol error.
- Cancelling a runtime task after possible execution does not prove business failure.
- The first Tool-list page is not a complete inventory, and pages from different revisions cannot be merged.

## Engineering Artifacts Produced

- Application-owned Server request/decision DTOs and three bounded handler families.
- Narrow dependency-injected service ports with no Committer or durable-store authority.
- Signed HMAC Tool-list cursors bound to a complete inventory revision.
- Capacity gate, lifecycle state machine, bounded drain and reconciliation preservation.
- Controlled separate-process stdio fixture for Tool, Resource, Prompt, pagination and error behavior.
- Deterministic seed grader, example, official-source evidence and validation record.

## Framework Connections Added

- Python MCP SDK 2.2.0 Server registration, Context, stdio and wire-result behavior behind a private Adapter.
- Pydantic input/output Schema as a structural contract that does not replace application validation.
- Application service-layer dependency injection as an explicit least-authority boundary.

## AI Backend Connections Added

- Model proposals, MCP Tool candidates and durable business transitions remain separate layers.
- Resource content is untrusted and indirect prompt injection stops before model-context assembly.
- MCP Prompts are untrusted candidate messages, not system policy or automatic execution.
- Pre-handler backpressure and reconciliation control cost, duplicate effects and deployment risk.

## Interview Material Added

- Beginner Tool/Resource/Prompt responsibility comparison.
- Intermediate Adapter-direction and error-taxonomy questions.
- Senior graceful-drain, unknown-outcome and evidence-boundary questions.
- Weak versus strong answer showing missing application authorization and Committer controls.

## Validation Performed

- Markdown: required 16 lesson sections and repository links checked.
- YAML: no Day91 YAML artifact added.
- Code: Python 3.11.5; 40 Day91 focused tests and 621 cumulative tests passed.
- Seeds: Day91 14/14 and available Day83–Day91 suites passed.
- Runtime: pinned SDK Client and Server ran in separate local processes over stdio.
- Syntax/data: compile, JSON/JSONL parsing and deterministic example passed.
- Repository: `git diff --check` passed; no credential or production data was added.

## Remaining TODO

- Day92: add real authentication, authorization and tenant-isolation evidence.
- Day93: add durable remote lifecycle, monitoring, load/backpressure and failure-drill evidence.
- Replace in-memory idempotency and reconciliation teaching stores before production use.
- Validate on Python 3.12+ when available.

## Suggested Commit Message

`feat(day91): add MCP server responsibility boundaries`
