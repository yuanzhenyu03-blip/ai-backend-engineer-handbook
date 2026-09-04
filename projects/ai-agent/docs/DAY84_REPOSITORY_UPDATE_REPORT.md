# Repository Update Report

## Lesson

Day: 84

Title: Conversation Memory vs Durable Business-state Boundaries

Status: Complete at guided classroom scope. Final synthesis was instructor-authored
at the student's request; independent final synthesis is `NOT ASSESSED`.

The repository-update baseline and freshly fetched remote `main` were both
`e38ee35607c09340929e70331807a54a7717dd6d`. Work was performed in the independent
clone `/Users/yuanzhenyu/Documents/AI backend for codex/day84-classroom`; the older
working repository with user changes was not modified. The standalone
`Day84_Repository_Update_Input.md` is preserved outside the repository clone.

## Files Added

- `docs/fastapi/day84-conversation-memory-vs-durable-business-state-boundaries.md`
- `projects/ai-agent/src/context_memory.py`
- `projects/ai-agent/tests/test_day84_context_memory.py`
- `projects/ai-agent/tests/test_day84_seed_grader.py`
- `projects/ai-agent/evals/day84_context_memory_seed.jsonl`
- `projects/ai-agent/evals/run_day84_seed_eval.py`
- `projects/ai-agent/examples/day84_context_memory_boundary.py`
- `projects/ai-agent/docs/DAY84_CONVERSATION_MEMORY_BUSINESS_STATE_BOUNDARIES.md`
- `projects/ai-agent/docs/day84-context-memory-classroom-draft.md`
- `projects/ai-agent/docs/DAY84_REPOSITORY_UPDATE_REPORT.md`
- `projects/ai-agent/evidence/day84-validation.json`
- `projects/ai-agent/evidence/day84-repository-validation.json`
- `projects/ai-agent/evidence/day84-repository-checks.json`

## Files Updated

- `AGENTS.md`
- `CHANGELOG.md`
- `CURRICULUM.md`
- `PROJECT_STATUS.md`
- `README.md`
- `ROADMAP.md`
- `TASKS.md`
- `cheat_sheets/fastapi.md`
- `docs/README.md`
- `docs/fastapi/day83-human-approval-interrupt-and-escalation-boundaries.md`
- `interview/fastapi.md`
- `projects/ai-agent/README.md`

Protected master/teaching prompts and `LESSON_TEMPLATE_v2.md` are unchanged.

## Main Classroom Content Preserved

- Conversation history, working context, summary, persistent memory, durable
  business state and Checkpoint are separated by writer, validation, scope,
  lifecycle and authority rather than storage medium.
- Memory selection checks current exact scope, access, source version/availability,
  expiry and revocation before model or summarizer input.
- Context assembly records roles, trust, provenance, selected/omitted sources,
  versions, policy and capacity without granting execution.
- Validated Tool results become bounded structured views that retain completeness,
  warnings, counts, cursor, source reference and original operation identity.
- Compaction is a lossy candidate publication guarded by source span/fingerprint,
  summary revision CAS and candidate idempotency.
- Rehydration uses the summary for continuity, then reloads current business facts
  and reuses the Day83 guarded human-control decision.
- Unknown external outcomes retain original identity and held reservation for
  reconciliation; A1/A2/A3 accounting and compensation remain distinct.
- Faulty-policy containment, affected-set provenance and incident closure evidence
  are preserved with student/instructor attribution.

## Main Misconceptions Corrected

- A durable memory row is not automatically a durable business fact.
- Conversation memory is not necessarily unverified, but even verified context does
  not carry business execution authority.
- An empty bounded excerpt does not prove an empty source result.
- A context manifest is trace evidence, not an Approval or dispatch permit.
- Structural summary validation and deterministic Fake cases do not prove general
  LLM semantic fidelity.
- Compaction reduces representation size; it does not reset or settle Job budget.
- A response loss does not establish failure or make blind replay safe.
- Passing tests for repaired code alone does not close earlier affected Jobs.

## Engineering Artifacts Produced

The continuing `projects/ai-agent/` Artifact now contains an application-owned local
context/memory boundary, 30 focused behavior tests, 3 seed-grader tests, 16 version-1
seed cases and a deterministic example. It composes with the existing Day81
`ContextBudget`, Day82 durable identities and Day83 human-control decision.

In-memory locks/stores are not PostgreSQL durability. The Fake UTF-8 estimator is not
a Provider tokenizer. The Fake summarizer proves deterministic application behavior,
not real model quality. The typed `ValidatedToolResult` represents the Day74
validation precondition rather than reimplementing its parsing boundary.

## Framework Connections Added

PostgreSQL conditional transactions, protected Object Storage references,
Outbox/Relay/Queue/Worker dispatch and Provider context/usage interfaces are explained
as conceptual production connections. None was run for Day84.

## AI Backend Connections Added

The lesson connects bounded Provider inputs, Prompt Contract roles and versions,
Tool contract completeness, lossy summarization, current Agent Job rehydration,
human-control authority, reconciliation and reservation settlement without allowing
model text to mutate the control plane.

## Interview Material Added

Beginner, Intermediate and Senior material covers memory versus durable state,
rehydration after compaction and lost Provider responses. The student's concise
answers and their limits remain visible. The instructor-authored final synthesis is
not reported as independent performance.

## Validation Performed

- Code: `py_compile` passed; 33 Day84 and 411 cumulative deterministic tests passed
  on Python 3.11.5.
- Seeds: Day83 regression 26/26; Day84 version-1 16/16.
- Example: passed with zero Provider and external-Tool calls.
- Markdown: 16/16 required lesson headings and balanced fences checked; no full
  Markdown renderer/linter.
- Links: local target files checked; fragments and external URLs not validated.
- Secrets: narrow likely-credential scan found no credential values. An existing
  `api_key: SecretStr` type annotation was reviewed as a false positive.
- Integrity: six executable/seed hashes match classroom evidence.
- Protected files: master prompt, teaching prompt and lesson template byte-identical
  to the base commit.
- Whitespace: `git diff --check` passed.
- YAML: N/A; Day84 adds or modifies no YAML.

The classroom record retains three corrected non-business failures: the first
unittest path used a non-package import; a concise rerun selected system Python 3.9
without `PYTHONPATH`; and the first Day84 seed runner ordered a general warning branch
before the specific empty-excerpt decision (15/16, then 16/16 after runner correction,
with expected facts unchanged). Repository checking also retains the first shell
backtick parsing error. These failures do not count as passing tests.

## Remaining TODO

- Independently assess the Day84 final synthesis and review seed expectations before
  treating them as a release gate.
- Validate on repository-standard Python 3.12.
- Run a real tokenizer/summarizer/Provider only with explicit bounded authorization.
- Verify real PostgreSQL/Memory DB, Object Storage, authenticated callback,
  Relay/Queue/Worker, billing/compensation and production behavior.
- Begin Day85 only when requested.

## Suggested Commit Message

`feat(day84): add context memory and durable state boundaries`
