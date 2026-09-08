# Day 88 — Agent Runtime Framework Selection Behind a Replaceable Adapter

> Decision ID: `DAY88-DECISION-001`
> Status: `accepted_for_course_scope`
> Recorded: 2026-09-08T20:36:49+08:00

## Decision

Candidate C, `pydantic-ai-slim==2.41.0`, is accepted for the Day88 course
Adapter. This is not a claim that Candidate C is universally best and it is
not a production framework selection.

The accepted scope is deliberately narrow:

- local learning;
- public course source code on GitHub;
- an application-owned, replaceable Adapter;
- Fake Provider and Fake Tool contract tests;
- Python 3.12;
- the tested dependency snapshot.

Production Provider and Tool integrations, container distribution, bundled
artifacts, internal deployment and production deployment remain excluded or
not evaluated. Production readiness remains `MORE_EVIDENCE_NEEDED`.

## Candidate identity

Day87 did not persist a historical A/B/C mapping. Its old preference for
“Candidate B” therefore remains an unresolved preference and is not mapped
retroactively. Day88 creates a new working map:

| Day88 ID | Framework | Fixed distribution |
| --- | --- | --- |
| Candidate A | LangGraph | `langgraph==1.2.11` |
| Candidate B | OpenAI Agents SDK | `openai-agents==0.22.0` |
| Candidate C | PydanticAI | `pydantic-ai-slim==2.41.0` |

Mapping record: `DAY88-CANDIDATE-MAP-20260908-001`, version `1.0.0`.

## Architecture boundary

```text
framework / model output
        |
        v
framework-private Adapter
        |
        v
strict application ToolProposal DTO
        |
        v
application Committer
  - current grant re-read
  - approval + canonical intent binding
  - policy + fence + deadline + cancellation
  - operation ID + idempotency + reconciliation
        |
        v
production Tool client (not present in framework context)
```

The framework can only propose. It cannot own the operation ID, authorization,
approval, fence, durable business fact or Tool client. Framework checkpoints
may exist only as Adapter-private opaque caches; they are not authoritative
business state.

## Gate result

All three fixed candidates passed the shared Python 3.12 abstraction contract
in the tested Fake Provider/Fake Tool scope. Each candidate ran 15 safety cases,
10 retry/reconciliation cases and one replaceability case. The shared checks
covered strict output validation, current authorization, approval binding,
stale fences, immutable operation identity, duplicate/conflict behavior,
ambiguous Tool results and fenced reconciliation.

The checked-in deterministic application example adds 21 focused regression
tests for the selected boundary. It intentionally contains no Provider network
call or production Tool client.

## Weighted decision

`DAY88-WEIGHTS-001 v0.1` is a post-evidence weight freeze. Hard constraints are
not scored. Its groups total 100:

| Preference group | Weight |
| --- | ---: |
| Adapter implementation and security-assurance cost | 30 |
| Runtime control and testability above the gate minimum | 25 |
| Typed proposal integration | 15 |
| Dependency and runtime footprint | 10 |
| Documentation, stability and maintainability | 10 |
| Learning value and limited job signal | 10 |

Unknown preferences use intervals rather than zero, fail or temporary pass.
Across 12 normalized ±5 group perturbations, Candidate C remained the leader
with zero winner flips. This ranking is robust only within that scoring model,
the fixed versions, evidence snapshots and tested scope.

## Supply-chain boundary

Python 3.12.14 installation, minimal real-framework runtime and `pip check`
passed for all candidates in isolated environments. PyPI and OSV scans returned
no matched advisories for the exact snapshots at retrieval time. This means
“no matches reported,” not “no vulnerabilities exist.”

The license engineering screen passed only for public course source whose users
install dependencies from a registry. The repository does not redistribute
third-party wheels, executables, containers or vendored dependencies. Any scope
change requires a new review.

## Why Candidate C fits this course

The course builds application-owned Provider, Tool, state, authorization,
reconciliation and security contracts before selecting a framework. PydanticAI
fits the existing typed Python/Pydantic learning path while keeping the selected
framework behind a small translation boundary. It does not replace those core
contracts.

LangGraph remains part of the later learning path: foundational RAG stays
framework-neutral, while a later advanced-RAG module can implement branching,
loops, checkpoints and human-in-the-loop through a LangGraph Adapter using the
same application DTOs and tests.

## Review triggers

- framework or dependency-snapshot change;
- distribution-scope change;
- production Provider or Tool integration;
- new vulnerability or license evidence;
- Adapter-boundary regression;
- Python runtime or platform change;
- a new hard constraint or business requirement.

## Day89 handoff

Day89 may proceed to MCP Foundations and Protocol Model. MCP tools/resources
must enter through application-owned contracts; MCP does not receive authority
to bypass the Day80-Day88 authorization, proposal, operation, fence or durable
state boundaries.
