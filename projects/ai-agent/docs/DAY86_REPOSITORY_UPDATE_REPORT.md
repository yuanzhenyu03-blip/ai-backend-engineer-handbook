# Day86 Repository Update Report

## Lesson

- Day: 86
- Title: Agent Security: Prompt Injection, Tool Abuse, Data Exfiltration and Sandboxing
- Status: completed at guided classroom scope
- Evidence: conceptual + static + `EXECUTED_LOCAL_RUNTIME`
- Assessment: final synthesis instructor-authored; independent synthesis `NOT ASSESSED`

## Files Added

- `docs/fastapi/day86-agent-security-prompt-injection-tool-abuse-data-exfiltration-and-sandboxing.md`
- `projects/ai-agent/src/agent_security.py`
- `projects/ai-agent/tests/test_day86_agent_security.py`
- `projects/ai-agent/tests/test_day86_seed_grader.py`
- `projects/ai-agent/evals/day86_agent_security_seed.jsonl`
- `projects/ai-agent/evals/run_day86_seed_eval.py`
- `projects/ai-agent/examples/day86_agent_security_boundary.py`
- `projects/ai-agent/docs/DAY86_AGENT_SECURITY_BOUNDARIES.md`
- `projects/ai-agent/docs/day86-agent-security-classroom-draft.md`
- `projects/ai-agent/evidence/day86-validation.json`
- `projects/ai-agent/evidence/day86-repository-validation.json`
- `projects/ai-agent/docs/DAY86_REPOSITORY_UPDATE_REPORT.md`

## Files Updated

- `README.md`
- `AGENTS.md`
- `projects/ai-agent/README.md`
- `cheat_sheets/fastapi.md`
- `interview/fastapi.md`
- `CURRICULUM.md`
- `ROADMAP.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

## Main Classroom Content Preserved

- External content is untrusted data and cannot self-promote into instruction authority.
- Direct/indirect injection signals, delimiters and model self-checks do not replace authorization.
- Tool visibility, schema validity, security `ALLOW`, dispatch and verified outcome are separate facts.
- The original caller's current delegated grant prevents privileged confused-deputy execution.
- Every Egress sink independently checks tenant, purpose, audience, destination and allowed fields.
- Raw credentials stay outside the model and are resolved from controlled references after authorization.
- Sandbox confinement does not create business permission, output trust or zero-effect proof.
- Post-dispatch unknowns reconcile through the original identity and keep reservations held.
- Bad-policy containment, credential response, compensation and append-only audit are separate lifecycles.

## Main Misconceptions Corrected

- “Illegal input” was refined into useful but untrusted content with provenance and an injection signal.
- Schema validation was separated from semantic tenant/resource/authority validation.
- Tool success was separated from independently verified external outcome.
- Cleanup failure leaves security completion `INCOMPLETE` even when Tool work succeeds.
- An owner and deadline manage an unknown incident outcome but do not resolve it for closure.
- Fake test evidence was bounded away from real Provider, Tool, Sandbox and production claims.

## Engineering Artifacts Produced

- Deterministic application-owned security admission core.
- Fake Tool, Egress and Sandbox effect ports.
- Result verification, operation-conflict, fan-in and incident decision models.
- 28 behavior tests, 3 grader tests, 25 versioned seed cases and one deterministic scenario.

## Framework Connections Added

- Framework Tool discovery and routing remain non-authoritative candidate mechanisms.
- Application ports preserve Day86 security contracts for the Day87 refresh and Day88 replaceable adapter.
- MCP is identified only as a future boundary beginning on Day89; no framework was preselected.

## AI Backend Connections Added

- Provider/Tool adapters as current admission and Egress enforcement points.
- Controlled credential resolution outside model-visible context.
- Future durable evidence in PostgreSQL and stale-worker protection through Day85 fences.
- Separate disclosure policies for Provider, log, Artifact and recipient sinks.
- Sandbox confinement, reconciliation and bad-policy incident response.

## Interview Material Added

- Beginner prompt-injection and trust-boundary questions.
- Intermediate Tool authorization and credential-reference questions.
- Senior reconciliation, incident containment and outside-the-model enforcement questions.
- Actual learner answers, corrections, weak-answer boundary and concise strong answers.

## Validation Performed

- Markdown: 16/16 lesson sections; relative Day86 link targets checked.
- JSON: validation evidence parsed; seed JSONL executed successfully.
- Code: Python 3.11.5 syntax PASS; 31/31 Day86 and 474/474 cumulative tests PASS.
- Seeds: Day83 26/26, Day84 16/16, Day85 18/18 and Day86 25/25 PASS.
- Example: deterministic scenario PASS.
- Whitespace: tracked diff and new-file trailing-whitespace checks PASS.
- Secrets: credential-pattern scan PASS.

## Remaining TODO

- Independently assess the learner's final synthesis and seed expectations other than the explicitly reviewed AS16 case.
- Run Python 3.12 compatibility when that runtime is available.
- Add authorized integration evidence for a real Provider, Tool, Egress boundary, OS/container Sandbox,
  Secret manager, PostgreSQL, Outbox Relay/Broker and multi-process Workers.
- Run Day87's current framework/job-market refresh before selecting Day88's adapter target.

## Suggested Commit Message

`feat(day86): add agent security admission and containment boundaries`
