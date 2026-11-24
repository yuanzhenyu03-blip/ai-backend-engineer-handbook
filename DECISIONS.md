# DECISIONS.md

# Decision Log

This file records important technical and curriculum decisions.

These decisions help Codex, ChatGPT, and future contributors understand why the project is designed this way.

---

## Decision 001 — GitHub as the Single Source of Truth

Status: Accepted

Date: 2026-07-02

### Context

Chat is useful for teaching and discussion, but Codex cannot reliably continue from chat history.

### Decision

All final lessons, project files, prompts, standards, and status documents must live in GitHub.

### Consequence

- Chat becomes discussion material.
- GitHub becomes the source of truth.
- Codex can continue work by reading repository files.

---

## Decision 002 — Notion as Reading Layer, Not Source of Truth

Status: Accepted

Date: 2026-07-02

### Context

Notion is good for reading and review, but code assistants work better with GitHub repositories.

### Decision

Use Notion as the learning dashboard and reading layer.

Use GitHub for all canonical content.

---

## Decision 003 — Python Design Before FastAPI

Status: Accepted

Date: 2026-07-02

### Context

The student already understands basic Python syntax but needs deeper engineering thinking.

### Decision

Teach Python design topics first:

- Object Model
- References
- Mutable vs Immutable
- Generator
- Decorator
- Context Manager
- Async/Await

### Consequence

FastAPI and Playwright will be easier to understand later because their design relies heavily on Python's object model.

---

## Decision 004 — FastAPI + Playwright as Core, n8n as Integration Layer

Status: Accepted

Date: 2026-07-02

### Context

n8n is useful for automation workflows, but overseas engineering jobs still require coding ability.

### Decision

Use FastAPI and Playwright as core engineering skills.

Use n8n later as an orchestration and workflow layer.

---

## Decision 005 — Every Lesson Must Connect Theory, Enterprise Practice, and Interview

Status: Accepted

Date: 2026-07-02

### Decision

Every lesson must include:

- Theory
- Memory Model
- Engineering Thinking
- Enterprise Practice
- Interview Questions
- Tech Lead Review
- CTO Thinking
- Cheat Sheet

### Consequence

The project is not a tutorial. It is an interview-ready engineering handbook.

---

## Decision 006 — AI Backend Product Thread Across Day43–Day100

Status: Accepted

Date: 2026-07-26

### Context

After Day42 closes the Phase 3 data-ownership and failure model, the remaining curriculum (Day43–Day100)
could easily degrade into a set of unrelated framework tutorials (FastAPI, then Playwright, then n8n, then
"AI" bolted on at the end). That would not produce an employable AI Backend Engineer or a coherent,
demonstrable portfolio.

### Decision

Day43–Day100 is planned as a single continuous **AI Backend product capability chain**, not isolated
framework tutorials. All phases build one unified production scenario — a **Multi-tenant AI Research and
Automation Platform** — reusing the existing project directories rather than creating new ones.

The capability chain is:

```text
Day42 Data Ownership and Failure Contracts
    -> FastAPI Production AI API (Phase 4)
    -> Playwright Browser Automation / Agent Tool (Phase 5)
    -> n8n Workflow Integration (Phase 6)
    -> AI Agent + Tool Calling + MCP + RAG + Memory + Evaluation (Phase 7)
    -> Final Production Capstone (Phase 8)
    -> Portfolio + Overseas Interview
```

Specific decisions:

- **Not isolated framework tutorials.** Every phase extends the same runnable backend and the same durable
  data-ownership model, so capability compounds instead of resetting each phase.
- **FastAPI and Playwright are core engineering skills; n8n is an integration layer.** This continues
  Decision 004. n8n orchestrates correct backends; it never replaces backend code or backend correctness,
  and durable truth stays in PostgreSQL.
- **AI enters the scenario from Phase 4, not only at the end.** From Phase 4 onward every phase is framed
  around a real AI backend scenario (AI Job API, provider boundaries, streaming, agent tools, RAG, MCP,
  evaluation), rather than deferring all AI to the final days.
- **Runtime evidence, evaluation, and portfolio are completion conditions.** A phase or capstone is complete
  only with real, saved evidence: runnable code, tests, runtime traces, evaluation datasets/reports, and
  failure/recovery drills. Conceptual/static review is distinguished from executed runtime/production
  validation, and production-grade claims require executed, recorded evidence.
- **Testing and observability are continuous engineering disciplines from Day43, not end-of-phase add-ons.**
  Baseline tests, structured logging, and correlation IDs begin on Day43 and evolve with every Engineering
  Artifact; every implementation day adds proportionate tests and validation evidence.
- **The goal is employment readiness, not an offer guarantee.** The curriculum targets Junior / Developing
  AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent products. It does
  not guarantee a job, and 100 days is not equivalent to years of production experience or to Senior/Staff
  level.

### Consequence

Day43–Day100 in `CURRICULUM.md` and `ROADMAP.md` are planned as phases of one product thread with explicit
deliverables and validation requirements. Future days remain `Planned` and are not expanded into full
lessons until they become the current lesson; no future lesson files or new project directories are created
by this planning decision.

---

## Decision 007 — Rebalance Day59–Day90 After the Phase 4 Evidence Audit

Status: Accepted

Date: 2026-08-08

### Context

Phase 4 (Day43–Day58) delivered the AI Job backend as deterministic, in-process EXECUTED_LOCAL_RUNTIME
models with real tests, but every real runtime integration — a real FastAPI process, real PostgreSQL/Alembic,
a real Redis/Celery broker and Worker, real Object Storage, the real Provider adapter, and a real
OpenTelemetry exporter — was honestly recorded as NOT RUN. The previous Day59–Day90 plan spent 10 days on
Playwright and 6 on n8n before ever running the backend for real, and compressed Agent/RAG/MCP/Evaluation —
the actual target-role skills — into 16 days.

### Evidence gap

The backend's correctness was proven only as in-process control flow. No committed-DB evidence from a real
connection, no real broker redelivery/Worker-kill recovery, no real storage/provider/telemetry end-to-end
trace existed. Building browser automation and workflow layers on top of an unintegrated backend would stack
new capability on unproven runtime foundations.

### Options considered

1. Keep the old plan (10 days Playwright, 6 days n8n, 16 days Agent) and defer real integration to the final
   capstone. Rejected: postpones correctness and over-claims a "production" capstone at the end.
2. Delete Playwright/n8n. Rejected: browser automation and workflow orchestration are real, employable
   backend-adjacent skills and part of the product thread.
3. Insert a real integration gate first, compress Playwright and n8n to their essentials, and expand
   Agent/RAG/MCP/Evaluation. Chosen.

### Decision

Rebalance Day59–Day90 into: Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–66,
with Day59–61 a **Production Integration Gate** that inherits the Phase 4 models/tests and executes the
previously NOT-RUN real local integration); Phase 6 — n8n AI Workflow Integration (Day67–70); Phase 7 — AI
Agent, RAG, MCP and Evaluation Engineering (Day71–90). Phase 8 (Day91–100) is unchanged. Phase 4 still ends
at Day58; Day59–61 are NOT retconned into Phase 4.

### Why Playwright is retained but compressed (10 -> 5 days)

Playwright stays as a real, isolated, recoverable, permissioned browser tool (Day62–66), but the object-model
and interaction material is compressed to five days because the durable job-lifecycle, isolation, security,
and evidence disciplines it needs are already established in Phases 3–4 and reused rather than re-taught.

### Why n8n is compressed (6 -> 4 days)

n8n is an integration/orchestration layer over correct backends, not backend correctness itself. Four days
(Day67–70) cover the workflow model, long-job polling/callback/idempotency, human approval/retry/secrets/
audit, and a capstone — enough to orchestrate the now-real backend without inflating a low-code layer.

### Why Agent/RAG/MCP/Evaluation is expanded (16 -> 20 days)

These are the actual target-role skills (LLM/RAG/Agent product backend). Twenty days (Day71–90) give proper
room to prompt contracts, a framework-agnostic agent loop, MCP client/server and security, RAG ingestion/
embeddings/retrieval/grounding, memory and business-state boundaries, agent security, durability, multi-agent
orchestration, and automated evaluation with runtime traces.

### Why the Day59–61 gate was added

It converts Phase 4's honest NOT-RUN integration boundaries into real local INTEGRATION_RUNTIME evidence
before any new capability is layered on top, so browser, workflow, and agent work all run on a backend that
has actually executed against real infrastructure.

### Framework selection deferred to Day75

The agent runtime framework (LangGraph / OpenAI Agents SDK / PydanticAI) is deliberately NOT locked now.
Day74 builds a framework-agnostic minimal agent loop; Day75 compares the options and records the choice as a
future Decision, behind a replaceable adapter, keeping the Domain/Tool/Memory/Job/Provider contracts
framework-agnostic.

### Consequence

- `CURRICULUM.md` and `ROADMAP.md` Day59–90 are re-scoped with the new phase boundaries, topics, and
  connections; Day43–58 and Day91–100 are unchanged; the existing Future Lesson Implementation Boundaries are
  preserved.
- Future days remain `Planned`. This decision creates no future lesson files, no new project directories, and
  no Day59+ code; existing project directories are reused.
- No production validation is executed or claimed by this planning decision.

### Validation honesty

This is a curriculum-planning and status decision only. Day59–61 will produce EXECUTED local
INTEGRATION_RUNTIME evidence when actually run and saved; it is not PRODUCTION validation. The deterministic
Day43–58 tests remain EXECUTED_LOCAL_RUNTIME evidence and are not relabeled as integration or production
evidence.

---

## Decision 008 — AI Backend Employment Track: Competency-Gated Completion, Not a Fixed 100-Day Cap

Status: Accepted

Date: 2026-08-08

### Context

The curriculum was planned as a fixed 100-day arc ending at Day100. As the AI core took shape (LLM
application, agent runtime, MCP, production RAG, evaluation, AI safety and operations), a fixed Day100
endpoint forced these — the actual target-role skills — into a compressed 20-day window. Keeping a tidy final
number would mean under-teaching the exact capabilities employers ask for.

### Decision

Convert the post-Day70 curriculum into an **AI Backend Employment Track** whose completion condition is
passing the **Employment Readiness Gate**, not reaching a fixed day. Lesson numbers are planning coordinates,
not a promise that the course ends at a fixed number. The current planning horizon is ~Day130 (Phase 7A LLM
Application Day71–78; Phase 7B Agent Runtime and MCP Day79–94; Phase 7C Production RAG Day95–106; Phase 7D AI
Evaluation/Safety/Operations Day107–116; Phase 8 Final Employment Capstone Day117–130), but Day130 is a
planning coordinate, not a permanent cap: if the Gate is not yet met, Planned lessons may be added, split,
merged, or renumbered based on real job requirements, AI-ecosystem changes, learner weak points, and
project/interview feedback.

### Why remove the fixed 100-day cap

A day-count target optimizes for a tidy number; an employment-readiness target optimizes for demonstrable
capability. The endpoint that matters for the learner is a portfolio and job applications, not Day100.

### Why expand the AI mainline

LLM application, agent runtime, MCP, production RAG, and AI evaluation/safety/operations are the concrete
Junior/Developing AI Backend Engineer skills. They need real room (≈46 planned days across Phases 7A–7D)
rather than a compressed 20-day block, so each is a runnable, tested, evaluated subsystem instead of a survey.

### Why competency-gated / employment-gated completion

Completion is defined by the Employment Readiness Gate: a real deployable AI backend; real
FastAPI/PostgreSQL/Redis-Celery/Object Storage integration evidence; an agent runtime with explicit
state/termination/permission/checkpoint/recovery; a run MCP client/server; a production RAG with
ACL/citations/retrieval evaluation; tool permissions and prompt-injection defenses; evaluation
datasets/graders/release gate; AI latency/cost/quality evidence; observability/failure/rollback/repair
evidence; a reproducible README; Python/SQL and system-design interview capability; English project and
behavioral stories; portfolio/resume evidence; and real job applications with feedback feeding back into
Planned lessons. Trial applications may begin once the Phase 7B Agent + MCP evidence exists — the learner need
not wait for the Final Capstone to touch the market.

### Why the framework choice is deferred to a refresh checkpoint

The agent-runtime ecosystem moves quickly. The stable Agent Runtime contracts (loop, tool contracts, state,
budgets, durability, security) are taught and implemented first (Day79–86); a **Framework / Job-Market
Refresh** runs at **Day87**; the framework is chosen at **Day88** based on then-current ecosystem and job
evidence and implemented behind a **replaceable adapter**. LangGraph remains a candidate at the refresh but is
NOT written as the permanent, only answer. The framework is replaceable infrastructure, not the business
model. (This continues Decision 007's Day75 framework-deferral intent under the new numbering.)

### What stays fixed

- Day01–Day58 remain Completed; their Topics, order, teaching content, and completion facts are unchanged.
- Day59 remains the current / next lesson; Day58 remains the Last Completed Lesson.
- Day59–Day70 Topics, order, scope, and phase responsibilities are unchanged (Day59–61 Production Integration
  Gate; Day62–66 Playwright permissioned queue-backed browser tool; Day67–70 n8n workflow/orchestration).
- PostgreSQL continues to hold durable business truth; the four-tier evidence taxonomy
  (`CONCEPTUAL_STATIC` / `EXECUTED_LOCAL_RUNTIME` / `INTEGRATION_RUNTIME` / `PRODUCTION`) is unchanged; an
  in-process fake/mock/double is never `INTEGRATION_RUNTIME`; a real/paid Provider runs only under explicit
  user authorization and otherwise stays NOT RUN.
- Day58 canonical tests remain 38 passed / full API suite 503 passed.

### Consequence

- `CURRICULUM.md` and `ROADMAP.md` re-scope Day71+ into Phases 7A–7D and Phase 8 (horizon ~Day130), add a
  Planning Horizon and Completion Model note and an Employment Readiness Gate, and migrate the Future Lesson
  Implementation Boundaries from Day91/94/95 to Day117/123/125. Day01–58 and Day59–70 are unchanged.
- Future days remain `Planned`. No future lesson files, project directories, or Day59+ code are created; no
  Day59+ runtime/test/provider/deployment is executed or claimed.
- Decisions 006 and 007 are unchanged historical text; this is the next-numbered Decision.

### Validation honesty

This is a curriculum-planning and status change only. No integration, provider, or production run was
executed. The curriculum improves job competitiveness but does not promise an offer; target roles are Junior /
Developing AI Backend Engineer, AI Startup Backend Engineer, and Backend Engineer on LLM/RAG/Agent products;
completion is not fabricated as Senior/Staff production experience.

---

## Decision 009 — PydanticAI Behind the Replaceable Day88 Course Adapter

Status: Accepted for course scope

Date: 2026-09-08

### Context

Day79–Day86 established application-owned Agent contracts before a framework was chosen. Day87 refreshed
framework and job-market evidence but did not persist an A/B/C mapping and did not select a framework. Day88
created a new versioned mapping and ran comparable, fixed-version Adapter safety and retry/reconciliation
spikes for LangGraph, OpenAI Agents SDK and PydanticAI.

### Decision

Accept Candidate C, `pydantic-ai-slim==2.41.0`, behind an application-owned replaceable Adapter for the
bounded Day88 course scope: local learning, public course source on GitHub, Fake Provider, Fake Tool,
Python 3.12 and the tested dependency snapshot.

The old Day87 “Candidate B” preference remains unresolved and is not retroactively mapped. The Day88 map is
new evidence: A = `langgraph==1.2.11`, B = `openai-agents==0.22.0`, C =
`pydantic-ai-slim==2.41.0`.

### Why

All candidates passed the hard-constraint gate in the tested abstraction scope. Candidate C then remained
the robust leader under the post-evidence-frozen `DAY88-WEIGHTS-001 v0.1` across 12 normalized sensitivity
scenarios with zero winner flips. It fits the course's typed Python/Pydantic path while keeping Provider,
Tool, authorization, approval, operation, fence and durable-state contracts application-owned.

### Consequences

- Framework output is only a `ToolProposal`; it is never execution authority.
- The production Tool client cannot enter framework context.
- Framework-native types and checkpoints stay Adapter-private and non-authoritative.
- Production Provider/Tool integration, containers, bundled artifacts, internal deployment and production
  deployment are not approved by this Decision.
- LangGraph remains planned for later advanced RAG and complex orchestration behind the same contract.
- Day89 may begin MCP Foundations without weakening Day80–Day88 boundaries.

### Review triggers

Review this Decision when the framework or dependency snapshot changes, distribution scope changes, a
production Provider or Tool is introduced, license/vulnerability evidence changes, the Adapter boundary
regresses, Python/platform changes, or a new hard constraint appears.

### Validation honesty

Evidence includes Python 3.12 minimal real-framework paths and comparable Fake Provider/Fake Tool contract
tests. It does not prove production network, SDK retry, production Tool idempotency/reconciliation or
deployment behavior. Production selection is false and readiness is `MORE_EVIDENCE_NEEDED`.

---

## Decision 010 — Add a Contract-level LangGraph Adapter as Replaceability Evidence

Status: Accepted for Day88 course scope

Date: 2026-09-09

### Context

Decision 009 selected PydanticAI as the default course Adapter, but the checked-in Day88 safety and
retry/reconciliation matrix exercised only that real Adapter; a one-case Fake Adapter made replaceability
mostly a design assertion. LangGraph also has materially stronger keyword visibility in the bounded Day87
job sample, while the application-owned boundary permits more than one private translation implementation.

### Decision

Amend and extend Decision 009 without replacing it. Keep `pydantic-ai-slim@2.41.0` as the default course
Adapter and add `langgraph@1.2.11` as a second, contract-level translation Adapter. Both implementations must
convert their distinct untrusted input shapes to the same application `ToolProposal`, hold no Tool client,
and pass the same Day88 failure matrix.

The LangGraph Adapter models the documented `tools` node and `name` / `args` / `id` / `type` ToolCall
envelope. It imports and executes neither LangGraph nor LangChain. This is translation-boundary
replaceability evidence, not verified LangGraph integration or runtime support.

### Consequences

- PydanticAI remains the default; Decision 009 remains accepted and is not revoked.
- The same application authorization, approval, operation, fence, retry/reconciliation and durable-state
  contracts govern either Adapter.
- Day88 remains completed. No lesson was added, renumbered or reopened; Day89 remains next.
- No dependency or lockfile is added.
- Production selection remains false and readiness remains `MORE_EVIDENCE_NEEDED`.

### Validation honesty

The evidence tier is `EXECUTED_LOCAL_RUNTIME` for dependency-free contract tests using a Fake Tool. No
LangGraph package, Provider, production Tool, network, integration environment or production environment was
executed. `INTEGRATION_RUNTIME` and `PRODUCTION` remain `NOT RUN` for both Adapters.

---

## Decision 011 — Preserve Pre-bound MCP Identity Through a Version-pinned SDK-private Seam

Status: Accepted for Day90 course scope

Date: 2026-09-11

### Context

Day89 requires a durable local request-to-operation binding before a side-effecting dispatch. The public
high-level API in Python MCP SDK 2.2.0 creates its own request ID inside the call, so using it directly would
move identity creation after the application's durable-binding boundary.

### Decision

Keep Day89 application DTOs and ordering unchanged. Pin `mcp==2.2.0` and isolate a narrow private Adapter seam
that passes the already-bound request ID to the SDK dispatcher. SDK types stay inside the Adapter. Retain a
dependency-free codec/transport implementation for deterministic contract and failure injection tests.

The Adapter may issue an inventory-generation/request-fingerprint `MCPAttemptPreflightPermit`; the name is
deliberately not “authorization” because the permit proves only protocol readiness. Tenant, grant, approval,
operation and business authorization remain application-owned.

### Consequences

- Every SDK upgrade must rerun the exact-ID separate-process integration proof.
- Private SDK coupling is explicit technical debt; it may not be hidden by weakening pre-dispatch binding.
- Lifecycle notification handling must explicitly invalidate old permits before inventory refresh.
- A controlled local stdio Server proves `INTEGRATION_RUNTIME`, not remote or production readiness.
- Day91 may replace the fixture with bounded Server-owned handlers without changing application contracts.

### Validation honesty

Python 3.11.5 and `mcp==2.2.0` executed against a controlled separate-process stdio Server. Production auth,
production Tools, remote transport, monitoring, load/backpressure and production failure drills were NOT RUN.
Production readiness remains `MORE_EVIDENCE_NEEDED`.

## Decision 012 — Keep MCP Server Handlers Candidate-only Behind Application-owned Admission

Status: Accepted for Day91 course scope

Date: 2026-09-14

### Context

Day90 proved a real MCP Client boundary against a controlled Server fixture. Turning that fixture into a
Server implementation risks letting SDK registration, Resource URIs, Prompt text or handler return values
bypass application identity, admission, output validation and the durable Committer.

### Decision

Confine Server SDK types and wire mapping to `mcp_server_adapter.py`. Convert inbound requests to
application-owned DTOs, apply backpressure before handler entry, and inject only narrow controlled service
ports at startup. Tool handlers return candidates or Tool-level errors; Resource handlers authorize before
read and validate content after read; Prompt handlers validate before and after pure rendering. Signed Tool
inventory cursors bind pagination to one revision. Shutdown closes admission, drains in-flight work and
preserves uncertain operation IDs for reconciliation.

### Consequences

- Capability, inventory and Schema evidence do not grant application authorization.
- Handlers cannot commit durable business state because they receive no Committer or durable-store authority.
- SDK upgrades must rerun the separate-process Tool/Resource/Prompt and pagination proofs.
- In-memory idempotency/lifecycle controls are teaching evidence, not production durability.
- Day92 may add trusted identity and tenant authorization without moving those responsibilities into handlers.

### Validation honesty

Python 3.11.5 and `mcp==2.2.0` ran a real SDK Client and Server in separate local processes over stdio.
Production auth, production Tools, durable idempotency/reconciliation stores, remote deployment, monitoring,
load tests and failure drills were NOT RUN. Evidence is `INTEGRATION_RUNTIME`; readiness remains
`MORE_EVIDENCE_NEEDED`.

## Decision 013 — Establish MCP Identity Before Current Application Authorization

Status: Accepted for Day92 course scope

Date: 2026-09-16

### Context

Day91 exposes bounded Tool, Resource and Prompt handlers, but protocol capability, request payload, Resource
URI and Prompt text cannot establish caller identity or tenant authority. HTTP and stdio also have different
trust boundaries: remote HTTP carries a per-request credential, while stdio is normally created by a trusted
Launcher and process context.

### Decision

Keep raw HTTP credentials and transport-private auth details inside `mcp_security_adapter.py`. Validate the
trusted signing key, signature, issuer, audience, expiration/not-before and subject before constructing a
minimized application-owned principal. For stdio, accept identity only from the trusted Launcher context.

Use current application facts for revocation, required scope, tenant membership and exact Tool/Resource/Prompt
grants. Issue narrow principal-bound permits before Day91 capacity and handlers. Request payload, URI, Prompt,
signed role text and MCP capability negotiation cannot expand authority. Bind authorized Tool operations to
issuer, subject, operation ID, idempotency key, tenant and Tool.

### Consequences

- Missing/invalid identity stops before authorization; explicit denial stops before capacity/handler/service.
- Cross-tenant and nonexistent Resource denial share a safe external message.
- Cheap identity-independent edge limits may run before authentication; application quota/capacity does not.
- Pre-dispatch failure may retry the original operation identity; possible execution requires reconciliation.
- Day91 handlers remain candidate-only and cannot receive raw credentials or a durable Committer.
- Day93 must add remote lifecycle and observability without weakening these boundaries.

### Validation honesty

Python 3.11.5 ran 35 focused Day92 tests, 16/16 seed cases and 656 combined repository tests. Day91's real
separate-process stdio SDK integration remains the transport evidence; Day92 adds deterministic and composed
local security runtime evidence. Real Authorization Server/JWKS, authenticated remote HTTP, durable stores,
distributed rate limiting, monitoring, load tests and failure drills were NOT RUN. Evidence remains
`INTEGRATION_RUNTIME`; production readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 014 — Separate Remote Failure Evidence from Retry and Reconciliation Authority

Status: Accepted for Day93 course scope

Date: 2026-09-16

### Context

Day92 established trusted identity and current exact authorization, but a remote MCP timeout still cannot say
whether transport handoff or controlled-service execution occurred. Retrying from exception type alone can
duplicate external side effects. Reconnect, version changes, cancellation and late responses add further stale
or ambiguous observations.

### Decision

Convert SDK/private transport outcomes into immutable application-owned `FailureEvidence` with separate
dispatch and execution certainty. A durable dispatch marker is written before transport handoff. Retry policy
is pure and bounded; it requires proven non-execution plus current caller intent, deadline, retry budget,
authorization, capacity and circuit admission. A retry preserves operation/idempotency identity and creates a
fresh protocol request ID and attempt number.

Possibly executed operations enter `PENDING_RECONCILIATION`. Reconciliation receives only a read-only
authoritative status port and cannot execute the original Tool. Its proposals still require the sole Committer
to validate complete binding, pending state and version. Correlation and protocol negotiation are scoped to a
transport generation; downgrade requires fresh preflight and cannot expand permission. Logs, metrics and
traces remain diagnostic and never become authority evidence.

### Consequences

- Timeout and post-dispatch cancellation preserve unknown execution instead of authorizing retry.
- Backoff/jitter limit traffic but cannot make an unsafe retry safe.
- Conditional `READY_FOR_RETRY → DISPATCH_STARTED` ownership allows only one worker to dispatch.
- A trusted controlled pre-handler rejection may prove sent-but-not-executed; unverified response text cannot.
- Unknown reconciliation remains pending and alerts after bounded observation; it is never automatically replayed.
- Unknown-key JWKS refresh outage returns 503 without inventing an old principal or permit.
- Safe observability uses bounded metric dimensions and credential-free pseudonymous log correlation.
- Day94 must compose these contracts through the Agent runtime without moving Committer authority.

### Validation honesty

Python 3.11.5 and `mcp==2.2.0` ran 62 Day93 tests, including two independent-process loopback Streamable HTTP
tests. The read-timeout path observed the already-entered Tool complete after the Client abandoned its wait.
The complete repository validation ran 691 dependency-free plus 28 real-SDK integration tests (719 total),
and the 16/16 Day93 seed passed. This is `CONTROLLED_REMOTE_RUNTIME`, not production. Production Authorization
Server/JWKS, authenticated deployment, durable distributed stores, rate limiting, telemetry, load tests and
failure drills remain NOT RUN; readiness is `MORE_EVIDENCE_NEEDED`.

---

## Decision 015 — Separate Immutable RAG Lineage from Mutable Authorization and Enforce at the Content Exit

Status: Accepted for Day97 course scope

Date: 2026-10-22

### Context

Day95 and Day96 establish immutable current content facts, but an active DocumentVersion and selected ChunkSet
do not authorize a principal to read protected text. Tenant equality, Outbox delivery, metadata, content hashes,
database credentials and future vector filters can all be present without an exact current grant. Authorization
can also change after a decision but before content release.

### Decision

Keep immutable source/parse/chunk provenance separate from mutable tenant membership, ACL/policy revisions and
per-resource `authorization_epoch`. Source-declared metadata remains descriptive and cannot create owner,
membership, role, grant or ACL authority. Metadata contract changes append immutable snapshots; ACL changes do
not re-ingest or re-chunk.

Use application-owned PAP/PIP/PDP/PermitIssuer/PEP responsibilities. PIP rereads current facts; PDP applies
default deny and applicable explicit-deny precedence; authorization outage remains `INDETERMINATE`; PermitIssuer
signs only complete ALLOW into a short exact context-bound permit; the PEP revalidates signature, subject,
tenant, action, audience, purpose, expiry, all revisions/epoch, active version, selected pointer and document
fence immediately before `GuardedChunkReader` releases minimal text. Revocation advances ACL revision and epoch.

Cache only bounded decision evidence under a key containing principal, tenant, resource, action and all relevant
current revisions. Never cache a permanent authority or reusable permit. Treat RLS and vector filters as defense
in depth, not replacements for final application enforcement.

### Consequences

- Same-tenant membership without an applicable grant is denied.
- Service principals require an exact service action such as `chunk:read_for_embedding`.
- Stale, expired, replayed, tampered or revision-mismatched permits release zero content.
- Unauthorized and nonexistent resources share a safe external response; internal evidence remains protected.
- Repeated text retains separate tenant/provenance/deletion occurrences even when bytes or hashes match.
- Day98 receives protected, provenance-preserving authorized input and may not weaken Day97.
- The extra current-state checks add latency and require production revocation/freshness engineering.

### Validation honesty

Python 3.11 executed the deterministic in-process Day97 implementation, 36 focused tests, 24/24 seed and the
authorized-read example; Python 3.12.15 CI passed 882/882 complete tests and every seed evaluator. This proves
application control flow and selected semantics only. HMAC does not prove
production key custody/rotation; in-memory locks do not prove distributed transaction, multi-process fencing,
cache consistency, crash recovery or revocation latency. Production OIDC, policy deployment, RLS, vector store,
telemetry/load/failure drills and production traffic were NOT RUN. Evidence is `EXECUTED_LOCAL_RUNTIME` and
readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 016 — Version the Complete Embedding Space and Publish Only Atomic Authorized Sets

Status: Accepted for Day98 course scope

Date: 2026-10-26

### Context

Embedding vectors have no stable meaning without the exact model, tokenizer, preprocessing, input role,
numeric and normalization contracts that produced them. Provider responses can be partial, reordered,
mis-correlated or numerically invalid. Authorization and selected provenance can also change while a Provider
request is in flight. Persisting per-batch successes or retrying an uncertain dispatch can create mixed,
duplicated or unauthorized durable state.

### Decision

Apply non-negotiable eligibility gates before frozen weighted preferences. Bind model and tokenizer immutable
revisions, preprocessing, document role/prefix, actual-token hard maximum with overflow `REJECT`, dimensions,
numeric type, normalization, API/schema, batch limits and egress policy in one immutable EmbeddingContract.
Any semantic contract change creates a new EmbeddingSet; equal dimensions never imply compatibility.

Accept only the exact Day97 `chunk:read_for_embedding` handoff. Preserve stable operation identity separately
from fresh attempt/request identity. Treat every Provider response as a candidate and require complete unique
item correlation plus structural/numeric validation. Reject the whole operation on any invalid item. Preserve
post-dispatch timeout as `UNKNOWN`; retry only after proven non-execution or authoritative reconciliation.

Immediately before commit, reread current permit expiry, membership and every authorization revision/epoch,
plus Day95/Day96 current provenance, selection revision and document fence. Give only the EmbeddingCommitter
authority to atomically create immutable EmbeddingRecords and homogeneous EmbeddingSet, move the current
pointer under CAS, and insert an Outbox intent. Retain old sets. ACL-only changes do not re-embed unchanged
content, although they invalidate stale in-flight authorization and govern later retrieval.

### Consequences

- Silent truncation is forbidden; an oversized committed Chunk returns to Day96 for a new versioned set.
- Response order is insufficient unless an adapter proves an exact complete mapping to stable Chunk IDs.
- No partial batch/set publication occurs, even when earlier Provider batches succeeded.
- Exact replay converges; same stable identity with a different vector manifest is a conflict.
- Vectors remain protected data and are excluded from ordinary logs, metrics and evidence reports.
- Day99 receives immutable set metadata/storage references, not retrieval permission.
- Additional storage, current-state reads, recomputation after partial failure and explicit model migrations are
  accepted costs.

### Validation honesty

The deterministic fake workflow, 23 focused tests, 17/17 seed and Day97 regression ran locally on Python
3.12.14. Static official evidence compared three candidates and provisionally selected an exact BGE-M3
revision, but no real weights/Provider or frozen local retrieval-quality corpus ran. The in-memory lock does not
prove a distributed transaction, fencing, crash recovery or Outbox delivery. Evidence is
`EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; production readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 017 — Exact Reference Before ANN and Immutable Fenced Vector Generations

Status: Accepted for Day99 course scope

Date: 2026-10-31

### Context

Vector Providers expose different metric operators, score directions, index parameters, ACK semantics and
filter behavior. A successful request does not prove complete query-visible content. In-place rebuilds,
Provider aliases, stale workers and mixed EmbeddingSets can make retrieval irreproducible or unsafe.

### Decision

Keep physical `VectorIndexContract` separate from query-time `RetrievalPolicyRevision`. Start with an
application-owned Exact/Flat reference and typed score Adapter. Bind every physical generation to one current,
homogeneous Day98 EmbeddingSet, immutable Provider engine revision, metric, build parameters, point identity,
payload schema and canonical content manifest.

Build copy-on-write shadow generations. Treat Provider ACK as weaker than readback; require point/vector/payload
digest equality, checkpoint and exact-query parity before sealing. Use stable logical operation identity, fresh
attempts and Committer-generated monotonic fences. A post-write timeout remains `UNKNOWN` and blocks blind retry
until reconciliation. Only the Committer may seal generation plus Outbox or atomically select bundle plus
Outbox under CAS. Provider alias is derived state.

### Consequences

- HNSW `m`/`ef_construction` and IVFFlat `lists` require a new physical generation.
- `ef_search`, `probes`, `top_k` and threshold require a new policy revision, not necessarily a rebuild.
- Provider-private distances never leak into application threshold semantics.
- ACK-only, partial, changed-vector/payload or wrong-order state is rejected.
- ACL-only changes do not rebuild unchanged vectors; query authorization remains authoritative later.
- A sealed generation can remain non-serving when any hard gate is `NOT_RUN`, `UNKNOWN`, `FAIL` or `STALE`.

### Validation honesty

Official static research retains pgvector, Qdrant and Pinecone. The deterministic fake, 256-vector Exact/Flat
corpus, simulated ANN proposal, 37 focused tests, 8/8 seed and example execute application control flow; the
Python 3.12 CI gate also passes.
The fake tenant filter is not production authorization evidence. Real vector Provider and real ANN recall,
capacity/latency, distributed fencing, backup/restore, deletion propagation and traffic are NOT RUN. Evidence
is `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; readiness is `MORE_EVIDENCE_NEEDED`.

---

## Decision 018 — Authorize Before Retrieval and Fuse Only Version-bound Validated Candidates

Status: Accepted for Day100 course scope

Date: 2026-11-03

### Context

A sealed Day99 vector generation may be immutable without being selected or production-ready. Hybrid search
adds lexical and dense branches whose raw scores use different scales, while Provider filter capabilities may
not preserve the application's complete business-filter semantics. Authorization, selected generation and
provenance can also change between request admission and content release.

### Decision

Require one exact current application-selected retrieval bundle before query encoding or database work. Bind
that bundle to vector, embedding, chunk and lexical generations plus query-encoder, filter-schema, retrieval
and fusion policy fingerprints. Current authorization derives the searchable occurrence scope; a validated
client/business filter and system exclusions may only narrow that scope.

Keep filter meaning in an application-owned typed AST. A database may execute a direct pre-filter, exact split
branches, or an authorization pre-filter followed by bounded application post-filtering, but unsupported
semantics are never silently removed. Rank lexical and dense branches independently and fuse validated,
version-bound candidates with deterministic weighted RRF. Deduplicate by occurrence identity, not content
hash. Immediately before release, reread current authorization, selected generation and provenance through a
guarded reader. Bounded refill, degradation, cursor and cache reuse must never relax authority.

### Consequences

- Missing or mismatched selected bundle fails closed with zero encoder and database calls.
- Query egress must pass its frozen policy; there is no automatic encoder fallback.
- BM25 and dense raw scores are never added directly.
- A stale/cross-generation candidate is rejected before fusion; a revoked candidate is rejected before release.
- Lexical-only or dense-only results are `PARTIAL` only under an explicit selected degradation policy.
- A cursor becomes invalid after authorization, query, filter, bundle or policy identity changes.
- Candidate caches exclude protected text and always pass through current reauthorization.
- More current-state reads and bounded overfetch are accepted costs for authorization and reproducibility.

### Validation honesty

The real saved Day99 generation is `SEALED` but unselected, so it proves only the negative zero-call handoff.
An isolated `DAY100_CLASSROOM_ONLY`, `production_eligible=false` fixture, dependency-free BM25, Exact cosine,
filter oracle, weighted RRF, signed cursor/cache controls, 64 focused tests, 8/8 seed and 1006/1006 local
regressions exercise application control flow. Real query Provider, PostgreSQL/pgvector/FTS, Qdrant/Pinecone,
ANN recall, latency/capacity, backup/restore/failover and production traffic are `NOT_RUN`. Evidence is
`EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; readiness remains `MORE_EVIDENCE_NEEDED`.

## Decision 019 — Rewrites May Change Retrieval Expression; Rerankers May Reorder, Never Authorize

Status: Accepted for Day101 course scope

Date: 2026-11-04

### Context

Query variants can improve recall, but they can also drift in meaning or accidentally bypass the exact
selected-bundle, filter and authorization boundary established by Day100. Multi-query retrieval produces
duplicate occurrences with different branch ranks. External rerankers can return malformed, partial,
duplicated, stale or wrong-pool identities, and their scores say nothing about current authorization or
provenance.

### Decision

A rewrite may change only the protected query expression. Tenant, principal, action, purpose, client filter,
selected bundle and authorization rules remain immutable. Validate one bounded approved rewrite set and send
every variant through the unchanged Day100 `AuthorizedHybridRetriever.retrieve` entry point. Deduplicate by
occurrence identity while retaining every variant/branch rank, then apply deterministic cross-variant fusion.

Treat reranker output as an untrusted candidate ordering. Bind each request to an explicit candidate map,
candidate-pool digest, immutable model/tokenizer/input-window/truncation contract, output mode, score semantics,
attempt identity and egress policy. An Adapter maps Provider output and a Validator rejects duplicate, missing,
unknown, malformed or mismatched results. A reranker may only reorder or select a subset allowed by its
contract; it may never add candidates, authorize content or serve as source evidence. Recheck current
authorization and provenance before protected reranker egress and again before guarded release.

### Consequences

- Missing or ineligible Day100 handoff fails before rewrite, database or reranker side effects.
- Semantic drift is rejected; controlled decomposition requires an explicit domain contract and validator.
- Duplicate occurrences consume one candidate slot while preserving all branch-rank evidence.
- Invalid Provider output fails closed unless a selected policy explicitly permits unreranked fallback.
- Scores never compensate for revoked authorization or changed provenance.
- Cache and cursor identities include authority, bundle, query, rewrite set, pool, model and input windows.
- Latency and cost increase with variant count and pointwise candidate scoring, so every dimension is bounded.

### Validation honesty

The deterministic fake, 56 focused tests, 10/10 seed, example and saved evidence replay exercise bounded
control flow, stable identities, validation, fallback and safety invariants. The real Day100 state still has no
production-selected bundle and proves only the zero-call negative path. Real rewrite/reranker models,
baseline/labeled quality, protected egress, database/ANN, latency/capacity/cost/error rates and production are
`NOT_RUN`. Evidence is `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; readiness remains
`MORE_EVIDENCE_NEEDED`.

---

## Decision 020 — Ground Only from Immutable Bundles; Release Only Independently Verified Claims

Status: Accepted for Day102 course scope

Date: 2026-11-06

### Context

A top-ranked authorized candidate is still only a candidate. Provider prose can invent facts, attach valid-looking
but unrelated citations, cite a source outside the supplied context, or become stale after authorization,
provenance or source-version changes. A structurally valid citation proves neither semantic support nor permission
to release the resulting Claim.

### Decision

Admit only a trusted final Day101 handoff bound to the original Query, authorization scope and validated ordered
candidate identity. Recheck current authorization, provenance and superseded-source state, then freeze only exact,
bounded source windows into an immutable `GroundingBundle`. A citation may target only a source identity, version
and exact span present in that Bundle.

Treat generated prose, extracted Claims and verifier output as untrusted. Bind each atomic Claim to its exact answer
span, request item and cited evidence. Validate identities and Bundle membership structurally, then verify semantic
support, contradiction and source currentness independently. Recheck currentness immediately before release.
Reassemble the user-visible answer only from released Claims; never return raw Provider prose. Keep rejected Claims
separate from unanswered request items and explicit Abstention. Preserve Day101, generator and verifier degradation
history independently, and bind cache identity to both current authority and the complete Bundle/Claim/Citation/
verification contract.

### Consequences

- Rank and reranker score remain retrieval evidence, never answer evidence.
- A valid source pointer with an unsupported Claim is rejected.
- Source revocation, provenance change or supersession invalidates release even after semantic support passed.
- One failed Claim need not erase independently supported Claims; Request Coverage records the partial answer.
- Missing evidence creates Abstention for the request item; it is not rewritten as a verifier rejection.
- Generator and verifier egress each require their own current policy decision.
- More identity records, current-state reads and verification calls are accepted costs for auditability and safety.

### Validation honesty

The deterministic generator, Claim extractor and verifier, 44 focused tests, 10/10 seed, refund-policy example,
saved evidence replay and 1106/1106 local regressions exercise control flow, exact identity correlation, partial
release, fallback recording and safety invariants. They do not prove real generation, extraction or entailment
quality. Real generator, NLI/LLM verifier, protected egress, independently labeled evaluation, database/ANN,
latency/capacity/cost/error rates and production traffic are `NOT_RUN`. Evidence is
`EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 021 — Evaluate Predictions Against Independent Labels; Keep Hard Gates Non-compensable

Status: Accepted for Day103 course scope

Date: 2026-11-09

### Context

Day102 Verification results are produced by the system that Day103 must evaluate. Reusing them as labels would
let the system grade itself. Average metrics can also hide multi-facet regressions, missing request items,
superseded-source release and evaluator failures.

### Decision

Freeze an `EvaluationDatasetIdentity` that binds the Query set, source and authorization-policy snapshots,
labeling policy, independent annotator/review/adjudication revision, split and protected-data policy. Store
relevance, request-item and Citation-support labels separately from system Predictions. Preserve Day101 ranking
and Day102 Claim/Citation/Verification output as Prediction evidence only.

Compute Retrieval, Answer, Citation, Request Coverage and Abstention measurements independently. Aggregate
overall metrics and critical slices, but enforce unauthorized/unknown/superseded release and required Request
Coverage as non-compensable hard gates. `FAIL` means observed evidence violates a gate or threshold;
`INCONCLUSIVE` means an attempted run lacks sufficient valid evidence; `NOT_RUN` identifies an evaluation that
did not execute. The Evaluation Orchestrator emits evidence and a regression decision but never owns deployment.

Baseline and Candidate comparisons require identical dataset, labels, source/authorization snapshots,
evaluator, metric, slice and threshold identities. System and Prediction identities are expected to differ.

### Consequences

- A Day102 `SUPPORTED` relation can disagree with independent Ground Truth and remain measurable.
- B may support the old “30 days” Claim semantically while remaining a current-policy negative and release gate failure.
- An evaluator never repairs ranking, answer or Citation output before scoring.
- High Citation Precision cannot compensate for missing Citation or Request Coverage.
- Overall metric PASS cannot compensate for a critical slice or hard-gate failure.
- Evaluator timeout never defaults to PASS or a fabricated score.
- Reports keep protected Query, Claim, Evidence and Provider payloads out of ordinary evidence.
- More identity and label governance is accepted to obtain reproducible, auditable comparisons.

### Validation honesty

The fixed synthetic refund dataset, deterministic outputs, 27 focused tests, 10/10 seed, 1133/1133 complete
regressions, example, all 19 seed evaluators and all four saved replays exercise metric formulas, identity
correlation, slice/gate decisions, timeout semantics and content-safe reports on the local Python 3.11.5
fallback. Python 3.12 CI is NOT RUN. These checks do not prove real retrieval, generation, entailment, Citation,
Abstention or judge quality. Real independent human-label runtime, calibrated LLM judge, protected egress,
latency/capacity/cost/error rates and production traffic are `NOT_RUN`. Evidence is
`EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`; readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 022 — Keep Generations Immutable; Activate Through an Application-owned Versioned Pointer

Status: Accepted for Day104 guided classroom scope

Date: 2026-11-11

### Context

An index is a rebuildable view of durable source, authorization, embedding, schema, watermark and deletion
state. In-place mutation of the active index can expose partially rebuilt data, make rollback impossible and let
one request observe two incompatible corpora. Counts alone cannot detect equal-count substitution, metadata or
provenance drift, or resurrection of a tombstoned occurrence. Provider aliases are useful projections, but they
do not own application truth.

### Decision

Freeze a `BuildSnapshot` before each build. Bind it to source (`S`), authorization (`P`), embedding (`E`),
index schema (`IS`), watermark (`W`) and deletion snapshot (`D`) identities and digests. Build a new immutable
Generation off the active path, seal its physical namespace, and let an independent validator read it back.
Require exact occurrence IDs plus count, content, metadata and provenance digests. Reuse the fixed Day103 ruler
for same-corpus migration and persist its dataset/evaluator/policy fingerprint in the build and artifact; a
changed business truth requires a new snapshot, labels and baseline.

Only the application-owned Committer may mark the candidate `READY` and conditionally move the versioned active
pointer. It must recheck the current Build Snapshot, Manifest, provider checkpoint/fence, Validation record and
exact Day103 Evaluation evidence digest in the same protected decision. Activation also requires an independently
issued current Committer lease/fencing token. Pointer, target `ACTIVE`, previous `DRAINING`,
Activation record and Outbox intent change atomically in the durable design. A provider alias is reconciled from
that database truth. Each request atomically acquires a leased, fenced ReadView pinned to one pointer revision and
Generation. Retirement waits for the durable ReadView ledger to drain and for the retention gate.

Deletion begins with an application-owned Tombstone, deletion intent, durable verification policy and Outbox
event. Future rebuilds freeze the deletion snapshot. Logical release, serving-index absence and physical purge
remain separate evidence scopes whose accepted records bind a trusted validator, pointer revision, exact
servable-Generation set and Tombstone set.
Rollback to a draining Generation is allowed only when its complete frozen identity is still current; otherwise
the safe response is to keep release closed and roll forward.

### Consequences

- A successful build, Provider write or alias update is never sufficient release evidence.
- `INCONCLUSIVE` quality evidence keeps the candidate in `VALIDATING`; observed integrity or quality failure
  moves it to `FAILED`.
- Same operation identity plus the same payload converges; a changed payload is an identity conflict.
- Fencing rejects late workers, and CAS plus pointer revisions prevent concurrent successors and ABA ambiguity.
- Old requests continue on their pinned Generation while new requests pin the new active Generation.
- Tombstones prevent rebuild resurrection; physical erasure still requires separate evidence.
- More immutable artifacts, version rows, current-state reads and reconciliation work are accepted in exchange
  for auditability, safe concurrency and explicit recovery.

### Validation honesty

The Day104 implementation uses process-local locks and a deterministic sealed Provider fake. Focused tests,
seed cases, a deterministic example and content-safe replay exercise identity, state-machine, Manifest,
idempotency, fencing, CAS, ReadView, drain, deletion and evidence-boundary mechanics. They do not prove real
PostgreSQL transaction isolation, vector-store alias atomicity, distributed leases, crash recovery, delete
visibility, ANN behavior, physical erasure, zero downtime, capacity, latency, cost or production safety. Those
Level 3 and Level 4 gates remain `NOT_RUN`; readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 023 — Keep Retrieved Content Data-only; Release Through Application-owned Security Gates

Status: Accepted for Day105 guided classroom scope

Date: 2026-11-15

### Context

Day104 can prove that an occurrence belongs to the exact sealed Generation, is not tombstoned and is currently
authorized. It cannot prove that natural-language content is benign or entitled to change task, Tool,
destination or disclosure policy. Per-document detectors can miss indirect or cross-document attacks, and a
correct answer may still leak through citations, metadata, cache, logs or external egress.

### Decision

Treat every ordinary retrieved occurrence as untrusted data, regardless of provenance. Trusted instructions
enter only through an independent application-owned, authenticated and versioned control path. Bind ingestion
and request decisions to exact content/provenance identities, current authorization and deletion/security state,
parser/scanner/detector and policy versions. A request uses one Generation, ReadView and security revision.

Filter unauthorized or quarantined occurrences before model context; freeze exact allowed Retrieval Bundles
and Context Assembly Manifests; analyze bundle-level composition; and serialize retrieved content explicitly as
data. The application creates the Model Invocation and Disclosure Envelopes. The model emits only an
AnswerCandidate. An independent Output Release Gate checks grounding, exact citations, current authorization,
DLP, metadata, audience, destination and disclosure budget.

Normalize evidence as `PASS`, `FAIL`, `INCONCLUSIVE` or `NOT_RUN`; keep operational dispositions separate.
Any critical observed violation makes the overall result `FAIL`, while missing critical evidence fails closed.
Normal Q1/Q2/Q3 gates remain non-compensable so reject-all cannot pass.

On poison discovery, revoke/quarantine at serving time before updating durable truth and building a new
immutable Generation. Preserve append-only incident evidence. Actual disclosure additionally requires rotation,
impact analysis, notification/remediation where required and observation; rebuilding cannot retract leaked data.

### Consequences

- Provenance authenticity never grants instruction authority.
- Detector false negatives do not remove authorization, context-isolation or output-release gates.
- Authorized-but-malicious X and benign-but-unauthorized T are tested independently.
- Citation, cache, log, telemetry and response are separate egress sinks.
- Cache and rollback eligibility bind current security and disclosure identities.
- More versioned records, invalidation and fail-closed availability costs are accepted for auditability.
- L2 deterministic evidence cannot be generalized to real detector/model/DLP behavior or production safety.

### Validation honesty

The Day105 L2 implementation uses deterministic fixtures and fakes. It may prove contract, identity,
state-transition, failure and replay mechanics only. Real scanners, DLP, model Providers, policy services,
PostgreSQL/pgvector retrieval, distributed revocation, production egress, red-team, load/soak, canary traffic and
incident operations remain `NOT_RUN`. Production readiness remains `MORE_EVIDENCE_NEEDED`.

---

## Decision 024 — Compose the RAG Capstone Through Exact Identity and Application-owned Release Authority

Status: Accepted for Day106 guided classroom scope

Date: 2026-11-23

### Context

Day95–Day105 already own ingestion, ChunkSet and EmbeddingSet selection, immutable Generation lifecycle,
retrieval, context security, grounding, citations and release gates. A capstone that copies those stores or
reconstructs their identities creates a second authority and permits results from different executions to be
mixed. A model, Retriever, vector database or Provider cannot decide serving authority, disclosure or delivery
truth because none owns the complete durable business state.

### Decision

Day106 adds a thin application-owned composition layer. One request attempt binds its principal, tenant,
purpose, selected Generation/Manifest, pointer revision, fenced ReadView, exact occurrence identities and
content-safe digests. It then binds the Day101 retrieval result to the Day105 Retrieval Security Decision,
Retrieval Bundle and Context Assembly Manifest before any occurrence enters a Prompt. The Day102 generation,
grounding and exact-Citation results produce an `AnswerCandidate`, never release authority.

Current authorization, source/provenance eligibility, Tombstone/quarantine state, grounding/Citations, DLP,
destination and disclosure scope are rechecked before an append-only `OutputReleaseDecision`. The application
keeps authorization and release-currentness revisions stable across the local decision/intent commit and checks
them again before a new send. One decision owns at most one separately bound durable Response Intent. Delivery
receipts extend downstream outcome without rewriting
the Candidate or release decision. `UNKNOWN` transport outcomes enter reconciliation; idempotency conflicts
fail closed; a retry either preserves the exact logical invocation and key with a new transport attempt or
creates a new request attempt when upstream identity changes.

Historical ReadViews and evidence remain valid descriptions of what ran, but never freeze permission. A
revocation takes effect immediately. Rebuild creates a new immutable Generation, and activation or rollback is
a new forward compare-and-set transition after validation against current facts. Offline replay verifies saved
artifact integrity and internal binding only; it cannot prove that the original policy was lawful, that an
external side effect occurred, or that production is ready.

### Consequences

- Day106 composes Day95–Day105 artifacts; it does not create replacement source, ChunkSet, EmbeddingSet or
  serving-pointer authorities.
- Request, retrieval, context, model, candidate, decision, intent and delivery identities remain explicit and
  append-only.
- Unauthorized occurrences entering the Prompt must remain zero; post-generation filtering cannot compensate.
- Candidate changes require a new identity/digest and fresh candidate-bound receipts and release gates.
- Durable decision, dispatch and delivery evidence remain separate so crash recovery cannot infer an external
  outcome from memory or a prewritten timestamp.
- Normal quality and non-compensable security gates both matter; reject-all is not a quality PASS.

### Validation honesty

The bounded Day106 implementation is deterministic Level 2 composition. Local fallback execution uses CPython
3.11.5; the repository's canonical CPython 3.12 validation is `NOT_RUN`. Day95–Day99 authority stores are
represented by aligned fixture lineage rather than rerun in this checkpoint. Recovery evidence proves
deterministic same-process state rehydration, not a real process restart. Docker/PostgreSQL/pgvector, real
external model/detector/DLP/Provider calls, distributed storage, production IAM/egress, load/soak, canary and
production are `NOT_RUN`. Production readiness remains `MORE_EVIDENCE_NEEDED`, and no commit, PR or merge is
part of this decision record.

### Append-only L3 validation amendment — 2026-11-24

The preceding Level 2 boundary remains the historical truth for the original decision. A later, separately
sealed Day106 checkpoint now adds bounded local Level 3 evidence on CPython 3.11.5:

- L3A executed real local PostgreSQL 16.15/pgvector 0.8.7 transactions, CAS and restart read-back with
  deterministic model/security adapters, followed by content-safe offline replay.
- L3B executed exactly five bounded real model calls (`max_output_tokens=64`; observed output `89/320`) through
  the attested external transport. The same database execution produced four `RELEASE` decisions and one
  P2-revoked `BLOCKED / NOT_ATTEMPTED` decision; unauthorized occurrences entering Prompt remained zero and no
  response was dispatched or delivered.
- A real database-container restart preserved the exact durable state, and independent offline replay verified
  artifact digests, cross-bindings, call/token budgets and the append-only report chain.

This amendment does not upgrade the unexecuted boundaries. Canonical CPython 3.12, external DLP,
production IAM/RLS/TLS/egress, HA/restore, physical purge, load/soak, canary and production remain `NOT_RUN`;
production readiness remains `MORE_EVIDENCE_NEEDED`. The teacher-provided English response remains
`TAUGHT_NOT_VERIFIED`, so Day106 overall PASS is not claimed. No push, CI, pull request or merge is claimed by
this local L3 checkpoint.

---

## Decision 025 — Reframe Planned Day107–Day130 Around ProofOps and Ticket-first Delivery

Status: Accepted for Planned curriculum scope

Date: 2026-11-24

### Context

Day01–Day106 have completed their recorded classroom and evidence scopes. Day106 is the latest completed
lesson, while Day107–Day130 remain Planned. The Day106 teacher-provided final English response remains
`TAUGHT_NOT_VERIFIED`, so Day106 overall PASS is not claimed.

The previous plan separated Day107–Day116 Evaluation/Safety/Operations from a generic Day117–Day130 final
Capstone. That order risks evaluating disconnected deterministic exercises first and reconnecting the real
product later. It also risks forcing every previously learned technology into one deployment even when the
product does not require it.

The employment objective is to maximize credible coverage for mainland-China and overseas AI Backend,
Applied AI, Agent Platform and AIOps roles. The remaining curriculum therefore needs one bounded product,
runnable evidence, independent learner ownership, production-style failure reasoning and a portfolio story
that can be defended in Chinese and English.

Decision 008 permits Planned lessons to be added, split, merged or renumbered according to job requirements,
ecosystem changes, learner weaknesses and interview feedback. Completed Day01–Day106 lessons, Decisions
001–024, sealed Artifacts and historical evidence remain unchanged.

### Decision

#### Freeze the flagship product

The only Day107–Day130 flagship product is **ProofOps — Evidence-Grounded Incident Resolution Agent**. It has
two explicit layers:

- `src/runtime/`: domain-independent Bounded Agent Runtime;
- `src/domains/incident/`: incident investigation and controlled-remediation domain package.

The Runtime owns bounded Plan → Act → Observe → Replan/Finish control, durable Jobs, checkpoints, resume,
budgets, Tool eligibility, current authorization, HumanApproval binding, idempotency, UNKNOWN reconciliation,
OpenTelemetry correlation and trajectory evaluation. The incident package owns incident schemas, synthetic
fixtures, runbook/telemetry/deployment adapters, hypotheses, remediation candidates, recovery verification and
postmortems.

The application remains the authority for authentication, authorization, durable business truth, budgets,
Tool admission, approval validation, action decisions, dispatch, reconciliation and final state. The model,
Retriever, MCP Server and Provider contribute bounded candidates or observations; they do not own authority.

#### Use a separate future product repository

ProofOps will be implemented in a separate clean repository named `proofops`, using Python 3.12+,
`pyproject.toml`, `uv`, Ruff, mypy, Async FastAPI, SQLAlchemy 2.0 Async, asyncpg, Alembic,
PostgreSQL/pgvector, one real Streamable-HTTP MCP Server, root `compose.yaml` and OpenTelemetry.

This planning decision does not create that repository, code, Docker services, credentials or future lesson
documents. Repository creation requires a later explicit implementation authorization. The handbook remains
the curriculum, mastery and historical-evidence source of truth. The ProofOps repository will hold daily
Tickets, PRs, ADRs, executable tests and product evidence.

#### Freeze product scope

ProofOps is limited to five public capabilities:

1. `retrieve_runbook`;
2. `query_telemetry`;
3. `get_deployment_diff`;
4. `execute_approved_remediation`;
5. `verify_recovery`.

The first, second, third and fifth capabilities are read-only. `execute_approved_remediation` is the only write
capability and may execute only an allowlisted action in an isolated lab. Human approval is necessary but not
sufficient: current authorization, exact candidate/action/environment/policy binding, expiry, idempotency,
durable Decision/Intent, dispatch receipt, UNKNOWN reconciliation and recovery verification remain
application-owned.

ProofOps is limited to four scenario families:

1. bad deployment causing a P95 latency regression;
2. Worker crash/Tool timeout plus lost remediation receipt and UNKNOWN reconciliation;
3. malicious Runbook injection, cross-tenant telemetry and mid-run authorization revocation;
4. noisy alert with no justified remediation and `false_remediation_rate = 0`.

`query_telemetry` is a typed read capability, not arbitrary SQL. `verify_recovery` verifies an exact,
application-defined SLO window; it does not accept model self-reporting as recovery evidence.

#### Freeze Provider strategy

Use one replaceable real OpenAI ProviderAdapter and one deterministic ReplayProvider for zero-cost CI and
failure injection. Do not require a second Provider. Concrete model IDs are selected at execution time and
bound through versioned light/standard Capability Profiles. Eligibility and compatibility precede
cost/latency/quality preference.

Any real Provider run requires separate user authorization plus strict call, token, time and cost caps.
Replay/L2 and external-real results are reported separately. Evidence must not retain API keys, complete
Prompts or raw responses.

#### Remove forced integrations

The ProofOps mainline does not include Playwright, n8n, multi-agent orchestration, a complex dashboard,
autonomous production repair, a finance/second-domain package or infrastructure introduced only for résumé
keywords. A minimal four-area Web approval/view page or CLI is sufficient. Phase 5/6 Playwright and n8n
evidence remains historical capability evidence and is not forced into ProofOps.

A second domain is moved to a Post-Day130 Optional Backlog. Runtime portability inside Day107–Day130 is shown
through stable runtime/domain interfaces, contract tests and replaceable adapters, not by building a second
product.

#### Treat Day numbers as milestone coordinates

Day107–Day130 contains 24 milestone coordinates. The intended eight-week schedule contains approximately 40
working days: 24 milestone/Ticket coordinates plus approximately 16 implementation-buffer, failure-debugging,
independent-retest, Python/SQL, English, application and recovery days. A heavy Day may span 1–3 calendar days
and multiple Tickets. Reaching the next Day number requires its DoD; calendar passage never creates completion.

#### Switch to Ticket-first, Micro-Socratic delivery

From Day107 onward, delivery uses `Ticket + PR + DoD + runnable evidence + independent explanation`.

- Type A covers knowledge not yet independently mastered. Begin with a 20–30 minute micro-Socratic lesson and
  2–3 critical boundary questions, then implement, review and complete a three-minute English explanation.
- Type B covers integration of independently mastered knowledge. Begin directly from the Ticket DoD and run a
  5–10 minute prior-knowledge check during review.
- A Type B Ticket automatically becomes Type A when the learner cannot explain or debug its critical seam.

Every Ticket contains Goal, Acceptance Criteria/DoD, Non-goals, Learner Ownership, Review & Interview Check and
Evidence Boundary. The learner must personally implement or debug a named critical portion. AI-generated code
cannot count as independent mastery until the learner explains the diff, failure path, alternatives and
observed evidence.

The ProofOps repository keeps concise README, ADR, threat/evaluation matrices, Tickets, PRs, evidence and
Postmortems. It does not create a 16-section lesson document for every engineering Ticket. The handbook updates
canonical status at checkpoints rather than duplicating every daily implementation record across large files.

#### Replace the Planned Day107–Day130 sequence

Phase 7D — ProofOps Core Runtime and Bounded Incident Resolution (Day107–Day113):

- Day107 — Scope Freeze, Threat Model, Two-layer Architecture and Async DB/pgvector Skeleton;
- Day108 — V0 Part 1: real Streamable-HTTP MCP Server, three read Tools and real embedding/pgvector retrieval;
- Day109 — V0 Part 2: bounded state machine, real ProviderAdapter plus ReplayProvider, evidence-grounded
  investigation and noisy-alert abstention;
- Day110 — V1: Async FastAPI `202` Job API, PostgreSQL `SKIP LOCKED` Worker, Lease/Fence, checkpoints and
  Worker-crash resume;
- Day111 — V2: exact HumanApproval, controlled remediation, recovery verification, idempotency, UNKNOWN
  reconciliation and minimal approval UI;
- Day112 — async SSE, disconnect/cancellation propagation and bounded Linux/Docker/network troubleshooting;
- Day113 — no-AI independent coding verification, runnable V0–V2 checkpoint and résumé/JD calibration.

Phase 7E — Evaluation, Safety and Operations on ProofOps (Day114–Day123):

- Day114 — versioned evaluation dataset and Golden-set governance;
- Day115 — reusable deterministic graders for schema, ACL, Citations, Tool arguments, security and normal
  quality;
- Day116 — calibrated model-based graders with frozen judge profile, bias, disagreement, abstention and
  human/deterministic agreement;
- Day117 — real-model retrieval and diagnosis evaluation integration checkpoint;
- Day118 — trajectory and Tool-use evaluation, repeated-run capability versus regression, observed
  success-at-least-once@k and all-k-pass consistency;
- Day119 — adversarial/failure-mode harness for malicious Runbooks, cross-tenant access, revocation and Tool
  timeout;
- Day120 — Prompt/model/Tool/index regression and machine-enforced GitHub Actions release gates;
- Day121 — OTel Collector, versioned light/standard routing evidence, TTFT/P95, cost per success and safe
  telemetry;
- Day122 — bounded async load testing, backpressure and HTTP security execution;
- Day123 — executable rollback/data-repair GameDay, append-only Postmortem and phase English interview.

Phase 8 — Cloud Integration, Operations and Employment Readiness (Day124–Day130):

- Day124 — bounded cloud deployment part 1: managed PostgreSQL/pgvector, secret management, container release
  and HTTPS;
- Day125 — bounded cloud deployment part 2: production-style configuration, health checks, SLI/SLO validation
  and public smoke run;
- Day126 — live observability dashboard, operational Runbook and per-investigation cost/quality checkpoint;
- Day127 — Runtime/domain interface contract proof, reproducibility audit, English README, architecture diagram,
  three-minute demo and portfolio repair;
- Day128 — AI Backend system-design plus timed Python/SQL mock interview;
- Day129 — English project story, Behavioral STAR bank, résumé and application iteration;
- Day130 — final mock interview, portfolio audit and 15-point Employment Readiness Gate review.

Runnable checkpoints are Day113, Day117, Day120, Day123, Day126 and Day130.

#### Define evaluation and statistics boundaries

Golden-set evidence records a versioned Manifest, provenance, train/development/blind-test split, critical
slices, label review/change control and anti-leakage checks. IAA or κ may be claimed only when at least two
independent human annotators actually participate. A model is not a second human annotator. Without that
evidence, IAA is `NOT_RUN`; label review may still be reported.

Judge evaluation freezes Prompt, model, configuration and rubric; measures agreement/error slices against
independent labels; supports abstention/`INCONCLUSIVE`; and never independently approves a security hard gate
or release.

Repeated-run metrics record every run identity, seed/configuration, attempt count, success definition and
failure taxonomy. Agent runs are not assumed independent. Security invariants require zero violations across
all runs and cannot be compensated by `pass@k`.

#### Keep parallel job preparation active

From Week 1, reserve one hour of timed Python/SQL work and thirty minutes of English explanation/interview-bank
work per working day. Continue system-design and behavioral-story development. Decision 008 already permits
honest limited applications based on completed evidence, so applications do not have to wait for V2. Day113
expands ProofOps-targeted applications only if the runnable checkpoint, README, CI and evidence actually pass.

Future notes move into focused topic files such as `interview/system-design.md`, `interview/behavioral.md`,
`interview/english.md` and `interview/linux.md`. Do not continue appending unrelated material to the oversized
FastAPI cheat-sheet/interview files.

#### Preserve evidence and history

The evidence taxonomy remains `CONCEPTUAL_STATIC`, `EXECUTED_LOCAL_RUNTIME`, `INTEGRATION_RUNTIME` and
`PRODUCTION`. Static documents do not prove a runtime. A deterministic ReplayProvider does not prove a real
Provider. A local Docker run does not prove cloud behavior. A public cloud smoke test does not prove
production.

The public environment disables or isolates remediation unless its exact safe action boundary is separately
authorized and verified. Cloud cost and lifetime are bounded. Production IAM, HA/restore, sustained load/soak,
canary, real operational traffic and incident evidence remain required before any `PRODUCTION` claim.

Day01–Day106, Decisions 001–024, sealed evidence, historical append-only records and Day106
`TAUGHT_NOT_VERIFIED` remain unchanged. The learner will complete the separate Day106 English verification
before beginning Day107; until it actually passes, the existing Day106 status remains unchanged.

### Employment Readiness Gate amendment

The future Gate no longer mandates Redis/Celery/Object Storage merely as technology keywords. It requires
actual evidence for:

1. a runnable ProofOps product;
2. Async FastAPI and PostgreSQL/pgvector;
3. bounded Agent state, budgets, checkpoint/resume/cancellation and recovery;
4. one real Streamable-HTTP MCP integration without transferring authority to MCP;
5. ACL-aware retrieval and exact evidence;
6. application-owned security and currentness;
7. exact HumanApproval plus isolated idempotent remediation;
8. UNKNOWN reconciliation and recovery verification;
9. deterministic, trajectory, adversarial and calibrated-Judge evaluation;
10. machine-enforced release gates;
11. latency, concurrency, cost and quality measurements;
12. OpenTelemetry and operational evidence;
13. reproducible local and bounded cloud execution;
14. Python/SQL, system-design, English and behavioral interview capability;
15. portfolio, résumé and real application feedback.

Optional infrastructure may be added only when an observed requirement justifies it.

### Consequences

- Only Planned Day107–Day130 scope is superseded.
- Phase 7D becomes Day107–Day113, Phase 7E becomes Day114–Day123 and Phase 8 becomes Day124–Day130.
- Runnable checkpoints become Day113, Day117, Day120, Day123, Day126 and Day130.
- Day107 remains `Planned / not started`.
- No Day107+ lesson, code, repository, Docker service or evidence is created by this decision.
- The handbook remains the historical source of truth; future daily implementation records live in ProofOps.
- The optional second-domain idea moves beyond Day130.
- `docs/README.md` navigation cleanup and the Day61 historical wording issue are separate maintenance work and
  are not part of this decision or its planning change.

### Validation honesty

This Decision is a `CONCEPTUAL_STATIC` curriculum-planning change only. It does not prove Day107 mastery,
ProofOps repository/code existence, Python 3.12/uv/Async FastAPI/PostgreSQL/MCP execution, a real Provider call,
Docker/cloud deployment, evaluation, load, security, GameDay, portfolio, employment or production readiness.
All Day107–Day130 implementation, integration and production results remain `NOT_RUN`.
