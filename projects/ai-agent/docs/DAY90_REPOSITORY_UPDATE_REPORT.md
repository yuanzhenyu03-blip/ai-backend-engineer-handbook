# Repository Update Report

## Lesson

- Day: Day90
- Title: MCP Client Engineering
- Status: Completed at guided classroom scope
- Execution evidence: `INTEGRATION_RUNTIME`
- Production readiness: `MORE_EVIDENCE_NEEDED`

## Files Added

- `docs/fastapi/day90-mcp-client-engineering.md`
- `projects/ai-agent/src/mcp_client_codec.py`
- `projects/ai-agent/src/mcp_client_transport.py`
- `projects/ai-agent/src/mcp_client.py`
- `projects/ai-agent/src/mcp_sdk_private_adapter.py`
- `projects/ai-agent/tests/fixtures/day90_mcp_stdio_server.py`
- `projects/ai-agent/tests/test_day90_mcp_client.py`
- `projects/ai-agent/tests/test_day90_mcp_sdk_integration.py`
- `projects/ai-agent/tests/test_day90_seed_grader.py`
- `projects/ai-agent/evals/day90_mcp_client_seed.jsonl`
- `projects/ai-agent/evals/run_day90_seed_eval.py`
- `projects/ai-agent/examples/day90_mcp_client_boundary.py`
- `projects/ai-agent/requirements-day90.txt`
- `projects/ai-agent/research/day90-mcp-client-evidence.jsonl`
- `projects/ai-agent/evidence/day90-validation.json`
- `projects/ai-agent/docs/DAY90_MCP_CLIENT_ENGINEERING.md`
- `projects/ai-agent/docs/day90-mcp-client-classroom-draft.md`
- `projects/ai-agent/docs/DAY90_TO_DAY91_HANDOFF.md`
- `projects/ai-agent/docs/DAY90_REPOSITORY_UPDATE_REPORT.md`

## Files Updated

- `projects/ai-agent/src/mcp_protocol_model.py`
- `.gitignore`, `AGENTS.md`, `README.md`, `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`,
  `CHANGELOG.md`, `DECISIONS.md`
- `projects/ai-agent/README.md`
- `cheat_sheets/fastapi.md`
- `interview/fastapi.md`

## Main Classroom Content Preserved

- Persist binding and dispatch evidence before actual send.
- Preserve operation ID and Tool idempotency key across a safe retry; mint a new protocol request ID.
- Possible-send failure is unknown outcome and pending reconciliation, not automatic retry.
- SDK objects stop inside the Client Adapter; correlation, output validation and Committer remain separate.
- Tool, Resource and Prompt share MCP transport while keeping different application/model boundaries.
- Preflight permits prove protocol readiness, not JWT, tenant or business authorization.

## Main Misconceptions Corrected

- A completed binding is not a successful business operation.
- `isError=true` is a Tool-level error inside a protocol result, not a JSON-RPC protocol error.
- Capability does not prove a named Tool exists; inventory and input Schema are separate evidence.
- A post-read rejection still records the Resource read that actually occurred.
- A local real-SDK integration is not production readiness.
- The first 12/13 seed run exposed a grader exception-order bug; the corrected rerun passed 13/13.

## Validation Performed

- Python 3.11.5; Python 3.12 unavailable.
- 8 dependency-free Client tests, 10 SDK integration tests and 3 grader tests passed: 21 Day90 total.
- 571 non-SDK repository tests plus 10 isolated-SDK tests passed: 581 combined.
- Day88 43/43 and Day89 21/21 regressions passed.
- Available Day83, Day84, Day85, Day86, Day89 and Day90 seed suites passed; Day87/Day88 runners are absent.
- Deterministic example, compile, JSON/JSONL parse and whitespace checks passed.

## Evidence Boundary

The real SDK Client and controlled Server ran in separate local processes over stdio. Production auth,
production Tools, remote HTTP, production persistence, monitoring, load/backpressure, failure drills and the
model Provider were not run. Evidence is `INTEGRATION_RUNTIME`; readiness is `MORE_EVIDENCE_NEEDED`.

## Remaining TODO

- Day91: implement MCP Server responsibility boundaries beyond the controlled test fixture.
- Day92: add real authentication, authorization and tenant isolation evidence.
- Day93: add remote lifecycle, observability, backpressure and failure-drill evidence.

## Suggested Commit Message

`feat(day90): add MCP client integration boundary`
