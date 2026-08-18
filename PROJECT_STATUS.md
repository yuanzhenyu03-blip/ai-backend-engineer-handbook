# Project Status

## Current Phase

Phase 6 — n8n AI Workflow Integration (current phase; Day67–Day69 Completed, Day70 current). Phase 5 — Production Runtime Integration and Browser Tool Engineering is COMPLETE (previous phase): Day60 and Day61 (the Production Integration Gate) are COMPLETE; Day61 was verified against disposable PostgreSQL, Redis/Celery, MinIO and an OTel Collector. Day62 — Playwright Runtime, Locators and Reliable Async Interaction is COMPLETE (EXECUTED_LOCAL_RUNTIME: pure interaction/cleanup logic + a controlled research page over real HTTP loopback + a classroom Chromium run; the real-Chromium test suite is gated on the `playwright` package). Day63 — Browser Authentication, Storage State and Tenant Isolation is COMPLETE (lesson + a pure Session-Gate authorization/claim decision core; EXECUTED_LOCAL_RUNTIME for the pure logic + a controlled loopback account page; the LIVE classroom artifact was CONCEPTUAL_STATIC; real Chromium isolation, real PostgreSQL atomic claim and a credential/secret store are NOT RUN). Day64 — Dynamic Extraction, Network Events and Artifact Evidence is COMPLETE (lesson + a pure Extraction/Artifact decision core; EXECUTED_LOCAL_RUNTIME for the pure logic + a controlled loopback report page; the LIVE classroom artifact was CONCEPTUAL_STATIC; real Playwright extraction, the real Day61 Object Storage HEAD and a real PostgreSQL Artifact-reference transaction are NOT RUN). Day65 — Browser Failure Recovery and Security Boundaries is COMPLETE (lesson + a pure recovery/security decision core; EXECUTED_LOCAL_RUNTIME for the pure logic; the LIVE classroom artifact was CONCEPTUAL_STATIC; real Playwright timeout/reconciliation, trace/screenshot redaction, redirect/DNS/IP enforcement, CAPTCHA handling, and a real Worker/queue are NOT RUN). Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool is COMPLETE (lesson + a pure queue-backed permissioned-worker decision/orchestration core reusing the Day63 fence and Day65 recovery core; EXECUTED_LOCAL_RUNTIME for the pure logic; the LIVE classroom artifact was CONCEPTUAL_STATIC; a real Provider/LLM tool loop, real guarded PostgreSQL concurrent claims, a real Outbox Relay/Broker, real Celery ACK/redelivery, real lease expiry/recovery, real Playwright execution, real Session revocation/cancellation, and real Object Storage publication are NOT RUN). This completes Phase 5. Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries is COMPLETE (Phase 6 begins): a lesson + a `projects/n8n-workflows/` draft-workflow CONFIGURATION RECORD; n8n is permissioned ORCHESTRATION only and FastAPI keeps the Day66 ownership boundaries; a single classroom EXECUTED_LOCAL_RUNTIME proof (invalid-webhook -> HTTP 400, false branch ran, HTTP Request did not); a valid FastAPI path, service auth, durable Task creation, PostgreSQL, queue/Outbox, worker execution, and a published Production URL are NOT RUN / NOT CONFIGURED, and no workflow JSON was exported. Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency is COMPLETE (classroom scope): a lesson + the Day68 Long-running Job Orchestration Contract in `projects/n8n-workflows/`; n8n orchestrates/observes and FastAPI/PostgreSQL keeps durable truth (Day67 boundary unchanged); CONCEPTUAL_STATIC only — the n8n workflow runtime, a valid FastAPI acceptance/status integration, real polling/callback/PostgreSQL/Worker/Provider behaviours, and production are NOT RUN, and no workflow JSON was exported. Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows is COMPLETE (classroom scope): a lesson + the Day69 Risk-based Approval Gate contract in `projects/n8n-workflows/`; risk-based human approval + classified recovery + Secret boundaries + authoritative append-only audit + incident hardening, with the Day67/Day68 boundary unchanged (n8n orchestrates; FastAPI/PostgreSQL owns durable truth); CONCEPTUAL_STATIC only — the n8n workflow runtime, a valid FastAPI approval/publication integration, real approval/callback/PostgreSQL/credential-store/Provider behaviours, and production are NOT RUN, and no workflow JSON was exported. Day70 (n8n + FastAPI + AI Tool Integration Capstone and Interview) is current and directly consumes Day69. Phase 4 (Day43-Day58) remains COMPLETE as classroom scope + deterministic EXECUTED_LOCAL_RUNTIME artifacts.

Previous Phase:
Phase 3 — Backend Foundations (Complete)

---

## Current Lesson

Day70 — n8n + FastAPI + AI Tool Integration Capstone and Interview (Phase 6) — next up.

Most recently released: Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows (Phase 6)

Status:
Day69 is COMPLETE (lesson + n8n-workflows Risk-based Approval Gate contract released; CONCEPTUAL_STATIC); Day70 is the current/next-up lesson.
Day65 turns Day64's trusted-Artifact browser flow into a recoverable, security-bounded capability. The artifact under `projects/fastapi-playwright/` is `src/day65_recovery_security_policy.py` (timeout classification UNKNOWN_OUTCOME vs SAFE_TO_RETRY; unknown-outcome reconciliation by strict Day64 action identity + server audit (terminal completed/imported -> CONFIRMED_COMPLETED may publish; accepted/pending/running -> CONFIRMED_ACCEPTED_OR_IN_FLIGHT: 202 accepted != completed != published, no replay/publish, keep reconciling; only authoritative not_found/never_started -> CONFIRMED_NOT_STARTED may retry); diagnostics policy — private/redacted/access-controlled/retention-bounded/audited only, never logs/model/prompt/public; navigation/redirect SSRF gate by scheme + exact Origin + resolved IP, blocking loopback/private/link-local/cloud-metadata; scoped credential release with no cross-Origin storage-state forwarding; instruction authority -> PROMPT_INJECTION_BLOCKED; CAPTCHA -> HUMAN_VERIFICATION_REQUIRED; bounded retry eligibility + Retry-After-vs-deadline; and incident classification), reusing `day63_session_gate.final_fence` to revalidate before a retry or credential release. The updating agent ran `python3 -m pytest -q tests/test_day65_recovery_security_policy.py` = 20 passed, EXECUTED_LOCAL_RUNTIME. The LIVE classroom session created a decision-contract design only — CONCEPTUAL_STATIC. Core rule: `no observed completion != proven operation failure`; page content is untrusted input, not authorization; a security control is a STOP, not a retry. NOT RUN: real Playwright timeout/reconciliation; real trace/screenshot redaction; real redirect/DNS/IP enforcement; real storage-state/Cookie behaviour; real CAPTCHA handling; a real audit lookup; a real Worker/queue (Day66); integration; production. Day64's `25 passed` is NOT reused as Day65 evidence. No secrets, real credentials, real target URLs, Cookies, tokens, customer data, raw sensitive payloads, screenshots, or CAPTCHA-bypass logic are committed.

(Day59-Day67 and Day68 are complete; Day69 is complete (documentation, CONCEPTUAL_STATIC) and most recently released; Day70 is the current focus (Phase 6). The Production Integration Gate (Day59–61) is COMPLETE. Phase 4 is COMPLETE as classroom scope + deterministic EXECUTED_LOCAL_RUNTIME artifacts (real FastAPI/OpenTelemetry/PostgreSQL/Redis/Celery integration + Provider production NOT RUN).
"Current Lesson" here and in TASKS.md both mean the lesson currently being worked on / next up;
"Last Completed Lesson" is the most recent finished lesson. See CURRICULUM.md and ROADMAP.md.)

---

## Completed

- ✅ Day01 — Python Object Model
- ✅ Day02 — Mutable vs Immutable
- ✅ Day03 — Functions & Parameter Passing
- ✅ Day04 — Scope & LEGB
- ✅ Day05 — Closures
- ✅ Day06 — Decorators
- ✅ Day07 — Iterators & Generators
- ✅ Day08 — Exception Handling
- ✅ Day09 — Modules & Packages
- ✅ Day10 — Type Hints
- ✅ Day11 — Object-Oriented Programming
- ✅ Day12 — Context Managers
- ✅ Day13 — Async Programming
- ✅ Day14 — Mini Project & Backend Architecture
- ✅ Day15 — Git Fundamentals
- ✅ Day16 — Git Branch & Merge
- ✅ Day17 — GitHub Workflow & Collaboration
- ✅ Day18 — Merge Strategy & Code Review
- ✅ Day19 — GitHub Project Management
- ✅ Day20 — CI/CD Foundations
- ✅ Day21 — GitHub Actions Fundamentals
- ✅ Day22 — GitHub Actions Advanced
- ✅ Day23 — Docker Fundamentals
- ✅ Day24 — Docker Compose
- ✅ Day25 — Deployment Foundations
- ✅ Day26 — Kubernetes Foundations
- ✅ Day27 — Kubernetes Workloads
- ✅ Day28 — AI Backend Production Architecture
- ✅ Day29 — PostgreSQL Foundations and Durable Relational State
- ✅ Day30 — SQL Data Manipulation and Query Fundamentals
- ✅ Day31 — Relational Modeling and Data Integrity
- ✅ Day32 — SQL Joins, Aggregation, and Operational Queries
- ✅ Day33 — PostgreSQL Transactions and Atomic State Changes
- ✅ Day34 — Concurrency Control, MVCC, and Worker Claims
- ✅ Day35 — PostgreSQL Indexes and Query Planning
- ✅ Day36 — Schema Evolution and Safe Migrations
- ✅ Day37 — PostgreSQL Production Reliability
- ✅ Day38 — Redis Foundations and Data Structures
- ✅ Day39 — Redis Cache Design and Consistency
- ✅ Day40 — Redis Messaging and Queue Semantics
- ✅ Day41 — Redis Coordination and Production Safety
- ✅ Day42 — Backend Data Design Capstone
- ✅ Day43 — AI Backend Product Contract and FastAPI Request Lifecycle
- ✅ Day44 — Pydantic v2 and Structured AI Input/Output Contracts
- ✅ Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters
- ✅ Day46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model
- ✅ Day47 — Async Sessions, Transactions, Repository and Unit of Work
- ✅ Day48 — Alembic and Safe AI Backend Schema Evolution
- ✅ Day49 — Upload Sessions, Object Storage and Artifact Verification
- ✅ Day50 — Idempotent AI Job API and Transactional Outbox Integration
- ✅ Day51 — Authentication, Password Security and JWT
- ✅ Day52 — Authorization, Tenant Isolation, Quotas and API Security
- ✅ Day53 — OpenAI SDK, Provider Boundaries and Structured Output
- ✅ Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation
- ✅ Day55 — Celery, Worker Execution and Long-running AI Jobs
- ✅ Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure
- ✅ Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection
- ✅ Day58 — Production AI API Capstone, Observability and English Interview (Phase 4 capstone)
- ✅ Day59 — Real FastAPI Runtime, PostgreSQL and Alembic Integration (Phase 5; Production Integration Gate)
- ✅ Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration (Phase 5; Production Integration Gate)

---

## In Progress

None.

---

## Last Completed Lesson

Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration (Phase 5; Production Integration Gate)

Completed Time:
2026-08-10

Main Artifact:
Day60 makes Day50's `job.dispatch_requested` Outbox intent a REAL Redis/Celery Relay + Worker path with durable recovery. Pure standard-library decision core `day60_delivery_recovery_logic.py` (relay publish-before-checkpoint ordering; guarded-claim outcome; duplicate/redelivery/expiry classification; recovery-sweep result; bounded early-ACK repair eligibility + idempotent `repair_id`; readiness gate) with `test_day60_delivery_recovery_logic.py`; a readiness app-factory `day60_runtime_app.py` (`create_app(expected_revision='0012_day60_repair_audit_attestation')` — explicit revision parameter, not hidden module state); `day60_celery_config.py` (late-ACK delivery settings: `task_acks_late=True`, `task_reject_on_worker_lost=True`, prefetch 1); a forward ADDITIVE migration `0009_day60_delivery_runtime` (nullable Relay claim fields `relay_owner`/`relay_token`/`relay_claim_expiry` on `app.outbox_events` + a new `app.job_repair_history` with a deterministic `repair_id` primary key); `requirements-day60.txt`; and the design/runbook. Core rules: the Relay publishes to the Broker FIRST then guarded-checkpoints `published_at` (at-least-once; `published_at IS NULL` = no checkpoint, not "did not execute"); the Worker takes authority via a guarded `UPDATE ... WHERE job_status='queued' RETURNING` + lease token/owner/expiry fencing (a stale Worker cannot commit after a takeover); late ACK is transport, not a business commit; an expired lease + external evidence -> `PENDING_RECONCILIATION` (never a second Provider call), else the sweep atomically `running -> queued` + one `job.redispatch_requested` intent; bounded early-ACK repair rolls back config first, uses an idempotent `repair_id`, and never Celery `.delay()`. PostgreSQL stays the business-state authority.

Validation Boundary:
Day60 provides a REAL Relay/Worker/recovery/repair runtime (`day60_delivery_runtime.py`: `OutboxRelay` with `FOR UPDATE SKIP LOCKED` claim + publish-outside-lock + fenced `published_at` checkpoint; `run_worker_attempt` with a guarded `queued -> running` claim + Attempt/Event + lease-token guarded completion; `recovery_sweep` that recovers only a legitimately expired `running` Job — evidence -> `pending_reconciliation`, else `running -> queued` + audit + one `job.redispatch_requested` intent; `repair_early_ack` that is release-filtered, re-verified, and writes an immutable `job_repair_history` row linked to its ONE redispatch intent, never `.delay()`/`apply_async()`), plus a real Celery app (`day60_celery_app.py`) and Relay/sweeper entrypoints (`day60_relay.py`/`day60_sweeper.py`) — only the Relay publishes (`apply_async`). It uses the EXISTING Day48 lease TRIPLE `lease_owner`/`lease_token`/`lease_expires_at` (constraints `jobs_lease_triple_coherent` + `jobs_running_requires_lease`); the CONTROLLED CORRECTIVE (non-additive, DROP-column) `0011_day60_lease_realign` migration removes the never-written parallel `lease_expiry` that `0010` added (safe only because it was brand-new/unused; NOT a production zero-downtime pattern), and the additive `0012_day60_repair_audit_attestation` migration persists the repair incident window + operator attestations in `job_repair_history`. The repair writes `incident_start`/`incident_end`/`no_conflict_attested`/`deadline_contract_budget_valid_attested` in the repair transaction, and on `IntegrityError` re-reads the committed `repair_id` row to return `already_applied` ONLY for a matching same-repair duplicate, else `repair_failed` (never a faked success). The repository updating agent executed ONLY `py_compile` of the changed Python files and the standard-library `test_day60_delivery_recovery_logic.py` + `test_day60_runtime_schema_contract.py` (34 passed, EXECUTED_LOCAL_RUNTIME pure-logic + static-contract, incl. the recovery-sweep negatives, the shared lease boundary, the bounded `in_time_window` predicate, the release/window/attestation repair rejections, the repair audit-column persistence, the IntegrityError duplicate-vs-`repair_failed` classification, and a static check that the runtime writes the full lease triple and matches `lease_token`). It has NO Docker/PostgreSQL/Redis/Celery, so the real runtime has NOT been executed against a real database + broker — INTEGRATION_RUNTIME NOT RERUN; no integration result is claimed for the current code (see the runbook's Required integration rerun matrix). NOT RUN (later lessons): real Provider HTTP traffic / request IDs / cost, Object Storage Result Artifact, OpenTelemetry tracing/exporter (Day61); real Playwright runtime consuming the queue (Day62); production load, security, zero-downtime migration, production scheduling, and multi-replica deployment. `pytest passed` never auto-upgrades to INTEGRATION_RUNTIME/PRODUCTION. No secrets, local database/broker URLs/passwords, tokens, fixture ids, `.venv`, or container ids are committed.

Completed Work:

- Day61 completed: real disposable PostgreSQL + Redis/Celery + MinIO + OTel Collector success evidence, plus timeout-after-receipt evidence (`pending_reconciliation`, no success Artifact, lease triple cleared); 66 local Day61 tests passed. Real/paid Provider and production-scale validation remain out of scope.
- Day62 completed: first `projects/fastapi-playwright/` artifact (controlled HTTP research page + pure interaction/cleanup logic + async browser task with per-task Context ownership); `pytest -q tests/` = 13 passed, 1 skipped (real-Chromium suite gated on `playwright`), EXECUTED_LOCAL_RUNTIME; the import path is provided by `projects/fastapi-playwright/pytest.ini` (`pythonpath = src`) so the command runs in a clean env with no `sys.path` hack or package install. NOT RUN: live-browser Python cleanup/action-timeout, Day63 auth isolation, Day64 artifact flow, Day65 recovery/security, Day66 queue integration, production.
- Day63 completed: `projects/fastapi-playwright/` Session-Gate authorization/claim decision core + a synthetic loopback account page; `pytest -q tests/test_day63_session_gate.py tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py` = 36 passed, 1 skipped (real-Chromium isolation gated on `playwright`), EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Chromium isolation, real PostgreSQL atomic claim, credential/secret store, Worker/queue (Day66), production. Day62 counts not reused.
- Day64 completed: `projects/fastapi-playwright/` Extraction/Artifact decision core (readiness, strict correlation, schema drift, download/upload counts, HEAD verify, retain/forward-repair, final-fence-controls-publish, rollback classification) + a synthetic report/export page; `pytest -q tests/test_day64_extraction_contract.py tests/test_day64_report_page_http.py` = 25 passed, EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Playwright extraction/network/download-upload, real Object Storage HEAD, real PostgreSQL Artifact-reference tx, Worker/queue (Day66), production. Review fix (v0.1.160): download validation now uses the ACTUAL parsed rows validated against the same TaskContract (DownloadCandidate.parsed_records; no forgeable schema_valid/business_valid booleans; distinct SCHEMA_FIELD_MISSING/TYPE_MISMATCH/VALUE_INVALID/CONTRACT_MISMATCH + BUSINESS_INVALID), so the network JSON and the downloaded artifact are validated independently. Tests 18 -> 25 passed. Review fixes (v0.1.159): export_id can no longer bypass the initial client_request_id match (strict correlate_export + extract_export_id/correlate_followup); the final fence sits at the guarded durable-write boundary (HEAD -> final fence -> guarded txn), so a fence failure commits nothing; the Extraction Contract validates field types/values (FIELD_MISSING/TYPE_MISMATCH/VALUE_INVALID/CONTRACT_MISMATCH); network metadata is an allow-list; and the controlled page is now a genuinely dynamic synthetic SPA for a FUTURE real-Playwright test (still NOT RUN). Tests 16 -> 25 passed. Day63 counts not reused. Async fix (v0.1.157): the real-Chromium tests now use one async event loop (run_task_authorization_async + AsyncTaskDeps) with no nested run_until_complete; 8 async-path pure tests added (28->36 passed). The real-browser suite was ATTEMPTED but Chromium could not be downloaded in the sandbox, so it remains NOT RUN. Review fixes (v0.1.156): the final fence now requires lease_owner==attempt_id + lease_expires_at>now (an old/expired-lease Attempt can never publish); the Cookie allowlist default is the Origin's host-only hostname (not the full Origin string); a published result whose Context cleanup failed is reported INCOMPLETE (TaskCompletion), never SUCCESS; classify_login_persist treats only state-saved+metadata-failed as ORPHAN_INACTIVE and state-not-saved as PERSIST_CONSISTENCY_FAILED; and the gated real-Chromium suite adds popup/unapproved-origin and login-redirect-no-auto-login tests (still NOT RUN).
- Day65 completed: `projects/fastapi-playwright/` recovery/security decision core (`src/day65_recovery_security_policy.py`: timeout -> UNKNOWN_OUTCOME vs SAFE_TO_RETRY; unknown-outcome reconciliation by strict Day64 action identity + server audit (accepted/in-flight != completed: no replay/publish, keep reconciling; only completed/imported may publish; only authoritative not_found/never_started may retry); diagnostics policy private/redacted/access-controlled/retention-bounded/audited only, never logs/model/prompt/public; navigation/redirect SSRF gate by scheme + exact Origin + resolved IP, blocking loopback/private/link-local/cloud-metadata; scoped credential release with no cross-Origin storage-state forwarding; instruction authority -> PROMPT_INJECTION_BLOCKED; CAPTCHA -> HUMAN_VERIFICATION_REQUIRED; bounded retry eligibility + Retry-After-vs-deadline; incident classification), reusing `day63_session_gate.final_fence`; `pytest -q tests/test_day65_recovery_security_policy.py` = 20 passed, EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Playwright timeout/reconciliation, trace/screenshot redaction, redirect/DNS/IP enforcement, storage-state/Cookie behaviour, CAPTCHA handling, audit lookup, Worker/queue (Day66), integration, production. Day64's `25 passed` not reused.
- Day66 completed: `projects/fastapi-playwright/` queue-backed permissioned-worker decision/orchestration core (`src/day66_queue_backed_permissioned_worker.py`: tool-call proposal validation with idempotency bound to a request fingerprint; atomic Task + Permissioned Contract + Outbox acceptance -> 202 + task_id + Relay-after-commit; minimal versioned Queue Envelope carrying identity only, no secrets, unsupported version dead-lettered; guarded claim + lease for ownership; stale-write rejection via the Day63 `final_fence`; commit-before-ACK terminal dedupe; Day65 UNKNOWN_OUTCOME reconciliation hand-off; fenced bounded-retry gate reusing `authorize_retry`; durable cooperative cancellation; safe Tool Result boundary; stale-Worker fence-removal incident classification), reusing the Day63 fence + Day65 recovery core; `pytest -q tests/test_day66_queue_backed_permissioned_worker.py` = 14 passed, EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Provider/LLM tool loop, guarded PostgreSQL concurrent claim, Outbox Relay/Broker duplicate delivery, Celery ACK/redelivery, lease expiry/recovery, Playwright execution, Session revocation/cancellation, Object Storage publication, integration, production. Day65's `20 passed` and earlier evidence not reused.
- Day67 completed: `projects/n8n-workflows/` Day67 draft-workflow CONFIGURATION RECORD (`Day67 - FastAPI Orchestration Boundary`: `Webhook -> Edit Fields -> IF -> HTTP Request | Respond 400`, test path `day67/research-report`, inputs `report_scope`/`request_id`) + the lesson. n8n is permissioned ORCHESTRATION only; FastAPI keeps the Day66 ownership boundaries (a workflow node may ASK FastAPI but never creates/mutates a durable Task, never gets direct DB/queue/worker access); Webhook receipt != durable acceptance (`202 + task_id` only after FastAPI commits); service credential != tenant/user identity; three retry layers (n8n transport / FastAPI idempotency / worker execution); rollback stops orchestration first, compensates via FastAPI, never deletes Task records. Evidence: DOCUMENTATION + one classroom EXECUTED_LOCAL_RUNTIME proof (invalid-webhook -> HTTP 400 with the documented JSON, IF false branch ran, HTTP Request did NOT run, after `$json...` -> `{{ $json... }}` fix). NOT RUN / NOT CONFIGURED: valid FastAPI path, service auth, durable Task creation, PostgreSQL, queue/Outbox, worker execution, published Production URL, production; no exported workflow JSON. HTTP endpoint was an unverified placeholder, auth `None`. Day66's `14 passed` and earlier evidence not reused. No secrets committed.
- Day68 completed (classroom scope): `projects/n8n-workflows/` Day68 Long-running Job Orchestration Contract (Acceptance/Polling/Callback/Incident branches + the six-identity table) + the lesson. Day67 boundary unchanged (n8n orchestrates/observes; FastAPI/PostgreSQL owns durable truth). After `202 + task_id`, an n8n timeout / Poll 503 / missing/duplicate/out-of-order Callback does NOT change business state; acceptance retries reuse the same `request_id` + fingerprint (different meaning -> 409); Polling observes the same `task_id` with bounded backoff/deadline/max-attempts; Callback is AT-LEAST-ONCE (authenticate -> validate -> correlate -> compute/validate event fingerprint -> atomically enforce `event_id` + fingerprint (same event_id+same meaning=idempotent no-op; same event_id+different meaning=integration/security conflict) -> `task_version` (MODELED / NOT IMPLEMENTED) ordering -> legal transition -> idempotent downstream action); correlation_id is an association key, not authentication; incident flow contain -> scope -> classify -> cancel/reconcile/compensate -> verify -> controlled rollout, never deleting durable facts or blindly recreating paid work. Evidence: CONCEPTUAL_STATIC (state-machine/contract review); the final Chinese synthesis was taught directly by the Tech Lead at the student's request. NOT RUN: n8n workflow runtime, valid FastAPI acceptance/status integration, real Polling loop, real Callback reachability/auth/duplicate/replay/mismatch/out-of-order, real PostgreSQL idempotency/version/terminal, real Worker/Provider duplicate-call prevention + cancel/reconcile, production; no exported workflow JSON. Day67's 400 is NOT reused as Day68 evidence. No secrets committed.
- Day69 completed (classroom scope): `projects/n8n-workflows/` Day69 Risk-based Approval Gate contract (Approval Gate + exact binding + lifecycle + classified retry/error matrix + Secret boundary + current-state/append-only audit + smallest-safe-boundary Error Workflow + incident runbook) + the lesson. Day67/Day68 boundary unchanged. Human approval is RISK-BASED (authorized tenant role, not platform staff); validation != permission; a v7 approval cannot authorize v8 (stable task_id/correlation_id/tenant_id; new approval_id/event_id/publication operation_id/idempotency key); n8n timeout != Approval state (PENDING until backend expires_at); HTTP timeout = OUTCOME_UNKNOWN -> same operation_id + key -> query authenticated FastAPI -> classify (429/503|400/422|401 rotate|403|409|terminal|unknown->PENDING_RECONCILIATION); Secrets only in the Credential Store (401 -> rotate, never log the Authorization header); audit = current-state + append-only events committed atomically (not tamper-proof); delivery at-least-once (same event_id+same fingerprint=no-op; +different fingerprint=conflict); incident = contain -> revoke/rotate -> preserve -> scope -> classify -> cancel/reconcile/compensate -> verify -> regression -> controlled rollout (never delete/retro-approve/reverse external effects). Evidence: CONCEPTUAL_STATIC (design review); final Chinese synthesis taught directly by the Tech Lead at the student's request. NOT RUN: n8n runtime, FastAPI approval/publication integration, real approval/callback/approver auth, PostgreSQL Approval schema/migration/audit-events/Outbox, retry/backoff/error workflow, callback duplicate/fingerprint-conflict, credential-store/rotate/redaction, publication/notification target/reconciliation, Worker/Provider/Browser-Tool, rollback/kill-switch/canary, production; no exported workflow JSON. Day67's 400 and Day68's contract not reused. No secrets committed.
- Day60 classroom learning (Relay publish-before-checkpoint; competing-Relay claim/fencing; guarded Worker authority + lease fencing; late ACK vs commit; duplicate/worker-kill/expiry classification; durable recovery sweep; bounded early-ACK repair; never `.delay()`)
- Day60 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; real CN/EN student answers + corrections + Mental Model Evolution preserved)
- Day60 design/runbook + pure decision-core module + stdlib tests (11 passed) + readiness app-factory + Celery delivery-config module + forward additive `0009_day60_delivery_runtime` migration + `requirements-day60.txt`
- Day60 FastAPI cheat sheet append
- Day60 FastAPI interview append (Beginner/Intermediate/Senior real record)
- Day60 project README increment
- Day60 repository status update (Day60 completed, Day61 current)
- Day60 review fix — P0 added a REAL runtime (`day60_delivery_runtime.py`) instead of only pure decision functions; P1 fixed the sweep state gaps (a `queued` Job is never swept; terminal states are no-ops; the sweeper acts only on an expired `running` Job) with counterexample tests; P1 release-filtered the repair set (candidate `actual_release_version` must equal the passed `affected_release_version`) with a different-release rejection test; P1 made the repair->redispatch link DATABASE-enforced (`0010` adds `job_repair_history.redispatch_outbox_event_id` UNIQUE; the `repair_id` PK gives one repair fact, the UNIQUE gives one intent) — concurrency test is a Required integration rerun item (NOT RERUN); P2 unified the lease boundary. Pure-logic tests 11 -> 25 passed.
- Day60 review round 2 fix — P0 unified the runtime to the EXISTING lease triple `lease_owner`/`lease_token`/`lease_expires_at`: `0011_day60_lease_realign` drops the parallel `lease_expiry` that `0010` added; the guarded claim writes all three atomically (satisfies `jobs_lease_triple_coherent` + `jobs_running_requires_lease`) and completion matches `lease_token` (not owner). P0 added a REAL Celery app (`day60_celery_app.py`, acks_late/reject_on_worker_lost/prefetch1 + `execute_job_attempt` task) and Relay/sweeper entrypoints (`day60_relay.py`/`day60_sweeper.py`; only the Relay publishes via `apply_async`). P1 made guarded completion keep Job/Attempt/Event/lease consistent (succeeded + `attempt_count`++ + `Attempt.finished_at` + success Event(attempt_id) + cleared triple in one tx; a lost lease writes nothing and keeps the Attempt open; the sweep preserves the old unfinished Attempt and uses the next attempt_number). P1 bounded the repair set (real incident `[start,end]` window via `in_time_window`, no hardcoded True; `no_conflict`/`deadline_contract_budget_valid` are explicit caller attestations, else conservatively refused). P2 fixed the runbook to upgrade/readiness `0011` and added real Redis/Relay/Worker/sweeper start + fault-injection commands. Tests 18 -> 26 passed (added static runtime-SQL contract checks). INTEGRATION_RUNTIME NOT RERUN.
- Day60 review round 3 fix — P1 persist the repair incident window + operator attestation: `0012_day60_repair_audit_attestation` adds nullable `incident_start`/`incident_end`/`no_conflict_attested`/`deadline_contract_budget_valid_attested` to `job_repair_history`, and `repair_early_ack` writes them in the same repair transaction (no longer merely "recorded in audit"). P1 the `IntegrityError` handler no longer blindly returns `already_applied`: it rolls back, RE-READS the committed `repair_id` row in a fresh transaction, and returns `already_applied` ONLY for a matching same-repair duplicate (job_id/release/reason + linked Outbox), else `repair_failed` — an unrelated UNIQUE/FK failure is never disguised as success (new `classify_repair_integrity` + unit tests + static contract checks). P2 corrected the `0011` wording everywhere: it is a controlled corrective DESTRUCTIVE (drop-column) migration on a never-written teaching column, NOT additive/expand-only/zero-downtime (with future production guidance to keep the column and remove it via a multi-stage migration), and fixed the requirements/runbook test commands to be copy-pasteable and run both Day60 test files. Head/readiness revision -> `0012_day60_repair_audit_attestation`. Tests 26 -> 31 passed. INTEGRATION_RUNTIME NOT RERUN (no Docker/PostgreSQL/Redis/Celery).
- Day60 review round 4 fix — P1 the IntegrityError duplicate check now verifies the LINKED Outbox SEMANTICS, not just a non-null FK: the fresh re-read JOINs `job_repair_history` to `app.outbox_events` and returns `already_applied` ONLY when the linked Outbox row exists, has `job_id` equal to this Job, and `event_type = 'job.redispatch_requested'` (plus the repair job_id/release/reason match); a non-null FK pointing at a foreign or wrong-type Outbox row is `repair_failed`. `RepairFact` gained `linked_outbox_job_matches` + `linked_outbox_is_redispatch`; added pure negative tests (wrong-job link, wrong-event-type link) and a static contract check that the re-read JOINs Outbox and verifies event_type + job identity. P2 fixed the last runbook wording that still called the current head `0011` -> `0012_day60_repair_audit_attestation`. Tests 31 -> 34 passed. INTEGRATION_RUNTIME NOT RERUN.

---

## Superseded — Day59 Last Completed Lesson (archived)

Day59 — Real FastAPI Runtime, PostgreSQL and Alembic Integration (Phase 5; Production Integration Gate)

Completed Time:
2026-08-10

Main Artifact:
Day59 real local FastAPI + PostgreSQL + Alembic acceptance integration. A local-only composition artifact `day59_runtime_app.py` (FastAPI `/livez`, `/readyz` gated on the expected Alembic revision `0008_day59_acceptance`, POST `/v1/jobs` atomic acceptance, tenant-scoped GET `/v1/jobs/{job_id}`) reuses the Day47 async engine/session boundaries; a pure standard-library `day59_acceptance_logic.py` (request fingerprint, idempotency classification, readiness gate) with `test_day59_acceptance_logic.py`; a forward ADDITIVE migration `0008_day59_acceptance` (nullable `app.jobs.request_fingerprint` + SHA-256-shape CHECK + a partial unique index allowing one `job.dispatch_requested` Outbox intent per Job); a controlled ONLINE-only `day48_alembic/env.py` version-table width repair; `requirements-day59.txt`; and the design/runbook. Core rule: `202` = ONE committed acceptance bundle (queued Job + request_fingerprint + one dispatch Outbox intent + Document links) verified from a NEW connection; the HTTP transaction never calls a Broker/Worker/Provider/Object Storage.

Validation Boundary:
Day59 has real local INTEGRATION_RUNTIME evidence executed in a DISPOSABLE local environment during class: Python 3.11 compile; a real Uvicorn process + a real PostgreSQL 16 container; raw Day42 baseline -> Alembic stamp `0001_baseline` -> controlled upgrade through `0008_day59_acceptance`; `/readyz` matching revision (wrong revision -> 503); a valid atomic acceptance (independent fresh-connection query Job=1, dispatch intent=1, Document link=1); exact-key replay returns the original Job; same key + different payload -> 409; an invalid/nonexistent Document -> 422 with an independent Job=0/Outbox=0/link=0 query; and two concurrent same-key requests -> one acceptance + one replay with an independent 1/1/1 query. A prior `alembic_version` width failure and an async SQL parameter-type failure were diagnosed from a fresh connection and fixed before the successful reruns. A Day59 review then CORRECTED the acceptance path (single `session.begin()` + `INSERT ... ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING` create-or-return; real `upload_sessions.session_status='verified'` Document verification; the `Idempotency-Key` header with a 400 on missing/blank; a fingerprint covering ordered `document_ids`; conflict re-read of `job_id`+`request_fingerprint` -> replay vs 409). The integration matrix above was recorded against the ORIGINAL classroom code; **the corrected acceptance path has NOT been re-run against real PostgreSQL — INTEGRATION_RUNTIME NOT RERUN.** The repository updating agent re-ran ONLY `py_compile` of the changed Python files and the standard-library `test_day59_acceptance_logic.py` (12 passed, EXECUTED_LOCAL_RUNTIME pure decision logic incl. fingerprint-covers-ordered-documents and replay-vs-409); it has no Docker/PostgreSQL available. NOT RUN (later lessons): real Redis/Celery broker/Relay/Worker, worker-kill/redelivery (Day60); real Object Storage/presigned/checksum, real HTTP Provider traffic/cost, real OpenTelemetry exporter (Day61); real JWT/JWKS or a production secret manager; production migration lock/load/zero-downtime; multi-replica deployment; load testing; production validation. `pytest passed` never auto-upgrades to INTEGRATION_RUNTIME/PRODUCTION. No secrets, local database URLs/passwords, test tokens, tenant/user fixture values, `.venv`, or container IDs are committed.

Completed Work:

- Day59 classroom learning (acceptance boundary; fresh-connection evidence; real migration diagnosis; readiness vs liveness; idempotency + request fingerprint; Document lifecycle; premature-202 containment and API-vs-schema rollback)
- Day59 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; real short CN/EN student answers + reasonable errors + corrections + Mental Model Evolution preserved; assistant-assisted final Chinese mental model labeled as such)
- Day59 design/runbook + local-only FastAPI composition artifact (`day59_runtime_app.py`) + pure acceptance-logic module (`day59_acceptance_logic.py`) + stdlib tests (`test_day59_acceptance_logic.py`, executed: 9 passed) + forward additive `0008_day59_acceptance` migration + controlled `env.py` version-table repair + `requirements-day59.txt`
- Day59 FastAPI cheat sheet append
- Day59 FastAPI interview append (Beginner/Intermediate/Senior real record)
- Day59 project README increment
- Day59 repository status update (Phase 5 Production Integration Gate opens; Day59 completed, Day60 current)
- Day59 review fix — P0 avoid AsyncSession autobegin-then-`begin()` (one short `session.begin()` with `INSERT ... ON CONFLICT ... DO NOTHING RETURNING` create-or-return, Day43 contract); P0 real Document verification via `app.documents` JOIN `app.upload_sessions` on `session_status='verified'` (there is no `documents.verified_at`), invalid/wrong-tenant -> 422 with a rolled-back Job=0/Outbox=0/link=0; P1 `request_fingerprint` now covers ordered `document_ids` (same key + different Document -> 409); P1 `Idempotency-Key` HTTP header (400 on missing/blank before any write), `document_ids` must be non-empty, strict loopback/test-only tenant seam kept; P1 conflict re-read of `job_id`+`request_fingerprint` (same -> replay, different -> 409, never swallow an unrelated integrity error); `requirements-day59.txt` adds `greenlet` (async bridge) + `psycopg2-binary` (sync Alembic driver) to match the runbook; lesson `Missing/визible signal` typo fixed. Focused pure-logic tests 7 -> 12 passed (EXECUTED_LOCAL_RUNTIME). The corrected acceptance path's real PostgreSQL INTEGRATION_RUNTIME was NOT RERUN by the updating agent.
- Day59 review round 2 fix — P1 Document input ORDER is now a durable fact: `app.job_documents` rows are written with `document_role='input'` and `input_order=1..n` in the client's order (no `set()`/`dict.fromkeys()`); duplicate `document_ids` are rejected `422` before the transaction (no Job/Outbox/links). P1 corrected the runtime-evidence claims — `same key + different Document -> 409` and `concurrent same key + different payload -> one 202/one 409` were NOT executed in class and are moved to a `Required integration rerun matrix (NOT RERUN)` in the design/runbook (not claimed as executed or verified for the current code). Pure-logic tests 10 -> 12 passed. INTEGRATION_RUNTIME still NOT RERUN.

---

## Superseded — Day58 Last Completed Lesson (archived)

Day58 — Production AI API Capstone, Observability and English Interview (Phase 4 capstone)

Completed Time:
2026-08-07

Main Artifact:
Day58 observability capstone (projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md) with a runnable deterministic in-process model (day58_observability_capstone.py; standard-library control flow, imports Day57's EvidenceTier/MatrixRow/RunStatus and Day56's ExecutionCertainty) + test_day58_observability_capstone.py: makes the distributed AI Job execution EXPLAINABLE and AUDITABLE across API -> Outbox Relay -> Worker Attempt -> Provider Adapter -> completion/reconciliation, with the core principle that observability is a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable state — it does NOT replace the durable state machine and does NOT grant permission to retry unknown external work; missing telemetry is an observability GAP, never proof of no execution. Covers the five-identity lifecycle contract (job_id/correlation_id STABLE; attempt_id/trace_id per Attempt; request_id per HTTP request); a safe StructuredEvent contract (safe fields only; rejects raw prompts/responses/secrets/tenant docs; provider.call.timeout observed outcome vs provider.call.suppressed reason=prior_attempt_may_have_executed); a low-cardinality MetricRegistry (Counter provider_call_total, Histogram provider_call_duration_seconds, Gauges provider_calls_in_flight + jobs_pending_reconciliation) that rejects job_id/attempt_id/trace_id labels; trace/span-link modeling (child span shares trace_id; later async Attempt links to the immediate prior trace, not fake nesting); a telemetry-exporter-failure policy (keep core processing, never FAIL an accepted Job, bounded buffer/drop, health metrics telemetry_export_failures_total/telemetry_events_dropped_total/telemetry_export_queue_depth); and the bad-observability-release rollback drill (roll back config not DB facts, bound the affected set by release+window, mark telemetry gaps honestly, keep a marker-backed PENDING_RECONCILIATION Job reconciliation-only, never an ordinary requeue).

Validation Boundary:
Day58 has EXECUTED_LOCAL_RUNTIME evidence only. Executed: python3 -m pytest -q test_day58_observability_capstone.py -> 38 passed (Python 3.10.12, pytest 7.4.3; standard-library control flow, imports Day57 EvidenceTier + Day56 ExecutionCertainty); full projects/ai-backend-data-layer/api/ suite -> 503 passed. This proves the identity/lifecycle rules, the safe structured-event contract, the low-cardinality metric contract, trace/span-link modeling, the telemetry-exporter-failure policy, and the observability-release rollback drill over an in-process deterministic model ONLY. NOT RUN (INTEGRATION_RUNTIME): a real FastAPI runtime + a real OpenTelemetry exporter pipeline; real PostgreSQL/Redis/Celery integration with committed correlation evidence (including redelivery/Worker-kill). NOT RUN (PRODUCTION): real Provider traffic / production observability validation. A reviewable runtime-evidence pack requires the exact command/revision/config/time window, fault point, structured logs/traces/metrics, committed DB queries from a NEW connection, independent Provider call evidence, Worker/Relay/broker lifecycle, actual result, and explicit tier + NOT RUN limits; pytest passed alone is not a reviewable pack. Day57 EvidenceTier/RunStatus, Day56 ExecutionCertainty, and the Day55 provider_dispatch_started_at marker are reused. No secrets, raw prompts, raw Provider responses, or tenant documents are persisted or logged.

Completed Work:

- Day58 classroom learning
- Day58 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim CN/EN student answers + corrections + mental-model evolution preserved; assistant-assisted final Chinese mental model labeled as such)
- Day58 design/runbook + runnable deterministic in-process observability model (standard-library control flow reusing Day57 taxonomy + Day56 vocabulary) + tests (executed: 38 passed; full api suite 503) and project README increment
- Day58 identity/lifecycle, structured-event, metric-cardinality, trace/span-link, telemetry-exporter-failure, and observability-release-rollback scenarios + four-tier evidence matrix (integration + production NOT RUN)
- Day58 FastAPI cheat sheet append
- Day58 FastAPI interview notes append (beginner/intermediate/senior real record)
- Day58 requirements-day58.txt (pytest; imports Day57 + Day56)
- Day58 review (Codex) round 3 fix — StructuredEvent presence flags (`request_id_present`, `dispatch_marker_present`) must be a strict Python `bool` (`type(value) is bool`); non-bool values raise the existing `UnsafeTelemetryError`; added tests. No teaching-spec files changed and NOT expanded into real FastAPI/OpenTelemetry/PostgreSQL/Redis/Celery/Provider integration. Tests 37 -> 38 passed; full api suite 502 -> 503. Committed as cde890c on `main`. Day56/Day57 behavior unchanged.
- Day58 review (Codex) round 2 fixes — P1 an inbound HTTP request is now a SEPARATE HttpRequestContext (new request_id AND new trace_id, NO attempt_id, no silent reuse of a Worker Attempt's trace; explicit parent_trace for legit traceparent), and IdentityLifecycle is strictly the durable Worker Attempt context; P2 the model metric label must come from a FINITE controlled registry (ALLOWED_MODEL_VALUES) or be normalized to a bounded bucket (normalize_model_label) rather than merely matching a regex; P2 StructuredEvent validates every canonical VALUE (bounded id/event_name shapes, provider/model/outcome allowlists, a finite reason enum, secret/overlong rejection) instead of trusting the caller. Tests 28 -> 37 passed; full api suite 502. Day56/Day57 behavior unchanged.
- Day58 review (Codex) fixes — P1-1 classify_observability_recovery no longer treats absence of a dispatch marker/provider_request_id as proof of no execution: an ordinary requeue now requires a POSITIVE Day56 DEFINITELY_NOT_ACCEPTED certainty and Day58 only returns ELIGIBLE_FOR_GUARDED_RECOVERY (hands the Job to Day56's existing guarded recovery), else RECONCILE_ONLY; P1-2 StructuredEvent.extra can no longer override canonical fields (event_name/ids/provider/model/outcome/duration/reason/presence flags) and to_safe_dict never lets extra overwrite a canonical value; P2-1 TelemetryPipeline.recover() drains buffered events (FIFO) to an observable sink and resets queue depth to 0, dropped counter stays accurate; P2-2 MetricRegistry validates label VALUES (provider/outcome allowlist, model shape, length/type) not just names. Tests 21 -> 37 passed; full api suite 502. Completion wording clarified across ROADMAP/PROJECT_STATUS/TASKS (classroom scope + deterministic EXECUTED_LOCAL_RUNTIME artifacts; real FastAPI/OpenTelemetry/PostgreSQL/Redis/Celery integration + Provider production NOT RUN).
- Day58 repository status update (Phase 4 capstone complete)

---

## Superseded — Day57 Last Completed Lesson (archived)

Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection

Completed Time:
2026-08-06

Main Artifact:
Day57 verification harness (projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md) with a runnable deterministic harness (day57_testing_harness.py; standard-library control flow driving the REAL Day56 policy functions + Day53's real pydantic validator) + test_day57_testing_harness.py: turns the Day43–Day56 reliability policies into REPEATABLE EVIDENCE and injects failures, keeping FOUR evidence tiers explicit (conceptual/static; executed local runtime; integration runtime; production) and marking real infrastructure (PostgreSQL/Celery/Redis = integration runtime, real Provider = production) NOT RUN. Harness: a controllable Fake Provider (ControllableFakeProvider — scripted outcomes, cross-call count, an independent ProviderCallLog that survives "Worker loss", request_received/release_response gates via threading.Event so timeout/kill windows are controlled not timed), a FakeClock + DeterministicRandom for reproducible backoff/jitter, an application-owned ProviderAdapter/ProviderOutcome (no SDK leakage; never writes Job/cost), a strict attempt_late_completion late-result contract, and an explicit VALIDATION_MATRIX/not_run_claims() taxonomy. Executed scenarios: bare-429 -> PENDING_RECONCILIATION with call count still ONE + no new rate permit + reservation HELD + reconcile-only redelivery; missing provider_request_id != no execution (Day55 dispatch marker forces RECONCILE); Adapter typed outcome + execution certainty (DEFINITELY_NOT_ACCEPTED may retry, MAY_HAVE_EXECUTED/UNKNOWN reconcile); valid-JSON schema violation = CONTRACT_VIOLATION not success; deterministic backoff with Retry-After as an earliest floor (no wake-all); controlled timeout window with no sleeps; late-result completes only on full identity + strict schema match, terminal CANCELLED rejects a matching result; limiter outage fails closed (DEFER, zero calls, execution_retry unchanged); deadline no-evidence EXPIRED+release vs marker/request PENDING_RECONCILIATION+held; admission 503 dominates 429; guarded idempotent repair under concurrency (unique repair_id -> one Outbox intent, provider-evidence -> RECONCILE_ONLY).

Validation Boundary:
Day57 has EXECUTED LOCAL RUNTIME evidence only. Executed: python3 -m pytest -q test_day57_testing_harness.py -> 23 passed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3; standard-library control flow driving Day56 functions + Day53's real validator); full projects/ai-backend-data-layer/api/ suite -> 465 passed. This proves the deterministic application state machine, Adapter contract, and failure-injection CONTROL FLOW over in-memory doubles ONLY. NOT RUN: real PostgreSQL transaction/rollback/isolation and guarded concurrent terminal transitions (an ORM mock cannot prove committed facts); a real Celery broker + Worker process + redelivery + Worker-kill; a real Redis limiter/circuit outage + restored-capacity no-herd; and any real Provider traffic/rate limits/cost. pytest passed alone is NOT audit-grade runtime evidence (a real run must also preserve the exact command/revision, fault point, committed-DB queries via a new connection, the Fake Provider cross-process call log, and broker/Worker lifecycle evidence). A real job_repair_history table + migration is a FORWARD-ADDITIVE design only, not migrated or tested. Day56 policy functions, Day55 dispatch marker, Day54 durable cancellation, and Day53 strict validation are reused. Day58 owns structured observability (structured logs, job_id/trace_id/attempt_id correlation, metrics, traces, runtime evidence) and the Phase 4 capstone — not implemented here. No secrets, raw prompts, or raw Provider payloads are persisted or logged.

Completed Work:

- Day57 classroom learning
- Day57 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim CN/EN student answers + corrections preserved; assistant-assisted final Chinese mental model labeled as such)
- Day57 design/runbook + runnable deterministic verification harness (standard-library control flow driving Day56 + Day53 validator) + tests (executed: 23 passed; full api suite 465) and project README increment
- Day57 fake-provider/contract-test/failure-injection scenario catalog + four-tier evidence matrix (integration runtime = PostgreSQL/Celery/Redis NOT RUN; production = real Provider NOT RUN)
- Day57 FastAPI cheat sheet append
- Day57 FastAPI interview notes append
- Day57 requirements-day57.txt (pydantic + pytest; drives Day56 + Day53 validator)
- Day57 repository status update

---

## Superseded — Day56 Last Completed Lesson (archived)

Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure

Completed Time:
2026-08-06

Main Artifact:
Day56 admission-to-Provider control plane (projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md) with a runnable provider-neutral in-memory model (day56_provider_resilience.py; standard-library control flow, imports Day54's IntentKind) + test_day56_provider_resilience.py: even a Job holding the Day55 guarded claim still needs fleet capacity, an intact worst-case cost reservation, and a healthy Provider circuit before a paid call. FOUR authorities are distinct (guarded claim = execution authority for ONE Job; rate permit = fleet capacity now via SharedRateLimiter; reservation = tenant affordability via TenantBudgetLedger; circuit = Provider-health containment via CircuitBreaker; a claim is not a permit, a limiter is not the ledger) and FIVE dispatch outcomes are executable via evaluate_dispatch: CALL / DEFER / RECONCILE / TERMINAL / NOOP, with durable terminal/cancellation facts and execution evidence outranking capacity retry. Bounded exponential backoff + FULL jitter with Retry-After as an earliest floor (retry storm != cache avalanche); a no-permit-before-call is a durable DEFER (retry_reason/next_attempt_at/defer_count/deadline, no Worker sleep, zero execution-retry spend, bounded by the business deadline), not FAILED/PENDING_RECONCILIATION; a shared-limiter outage fails CLOSED for new paid calls by default (emergency fail-open only explicit). Cost: reserve the BOUNDED WORST-CASE at acceptance (not remaining balance), settle actual use and release unused money to the tenant ledger (not the limiter), hold the reservation on unknown execution. Backpressure BEFORE the durable Job + Outbox commit (tenant 429 vs system 503, system dominates; never retro-429/503); no silent contract mutation (degradation only if the persisted contract authorizes it, down to a floor). A 429 alone is not proof of no execution: classify_execution_certainty (DEFINITELY_NOT_ACCEPTED vs MAY_HAVE_EXECUTED/UNKNOWN); evidence/marker forces RECONCILE. Circuit CLOSED/OPEN/HALF_OPEN with bounded progressive probes (one success does not release the herd). Deadline expiry releases the reservation only with proof of no execution, else reconcile + hold. Zero-defer incident: rollback config first (future harm only, not a business-fact rollback), bounded evidence-based affected set (preserve expired history, no bulk flip), guarded audited repair via a NEW Outbox dispatch intent for proven-no-execution valid Jobs, Provider-evidence Jobs RECONCILE_ONLY.

Validation Boundary:
Day56 has IN-MEMORY control-flow evidence only. Executed: python3 -m pytest -q test_day56_provider_resilience.py -> 54 passed (Python 3.10.12, pytest 7.4.3; standard-library control flow, imports Day54 IntentKind); full projects/ai-backend-data-layer/api/ suite -> 442 passed. Includes the review-round P1 fixes AND the concurrency P1 fixes (atomic HALF_OPEN probe acquire; atomic guarded repair transaction; atomic tenant budget reservation; atomic CircuitBreaker state; late-probe-success state-machine guard) (Retry-After jitter above the floor; HALF_OPEN probe slot consumed only at CALL; worst-case cost covers input+output with a protected over-reservation policy; guarded idempotent repair). This proves APPLICATION CONTROL FLOW over an in-memory model only. NOT RUN: a real Celery broker/Worker; a real Redis distributed limiter/circuit store; real PostgreSQL transactions/isolation; real Provider traffic/rate limits/costs; load tests; Worker-kill/fault-injection integration; production. Day55/Day53 evidence is NOT inherited as Day56 evidence. Boundary preserved: a guarded claim is not a rate permit; a limiter is not the budget ledger; no-permit-before-call is a durable DEFER; unknown external execution is RECONCILE; backpressure precedes 202; degradation needs a pre-authorized contract. Day57 owns integration + failure injection; Day58 owns observability/runtime evidence — neither is implemented here. Schema honesty: a deferred status, a durable defer record, execution_retry_count vs defer_count, and a tenant cost-reservation ledger are new facts modeled in-memory; the real schema needs a Day48-safe forward additive migration; limiter/circuit state is transient coordination, not durable tenant truth. No real credentials, raw prompts, Document content, raw Provider payloads, or secrets are persisted or logged.

Completed Work:

- Day56 classroom learning
- Day56 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim CN/EN student answers + corrections preserved; assistant-assisted final Chinese Mental Model labeled as such)
- Day56 design/runbook + runnable provider-neutral in-memory model (standard-library control flow + imported Day54 IntentKind) + tests (executed: 31 passed; full api suite 419) and project README increment
- Day56 four-authorities / five-outcomes, bounded-retry+jitter, shared-limiter fail-closed, durable-defer, worst-case-reservation, admission-backpressure, execution-certainty, circuit-progressive-recovery, deadline-expiry, and zero-defer-incident-repair exercises
- Day56 FastAPI cheat sheet append
- Day56 FastAPI interview notes append
- Day56 requirements-day56.txt (pytest; imports Day54 IntentKind)
- Day56 review-round (Codex) P1 fixes — P1-1 compute_next_attempt_at keeps Retry-After as an earliest floor but adds bounded jitter ABOVE it (>= floor, different draws differ, no wake-all); P1-2 a HALF_OPEN probe slot is consumed via allow_probe only at an actual CALL (gate reads has_probe_capacity), so a DEFER (no capacity / limiter outage / missing reservation) never leaks a slot or strands the circuit; P1-3 worst_case_cost = bounded input + output cost (separate unit prices), settle_actual returns SETTLED or OVERAGE_RECONCILE (charge reserved, record cost_overage, RECONCILIATION_PENDING; never overdraw), reserve_worst_case idempotent; P1-4 repair_redispatch is a guarded idempotent atomic decision (stable repair_id -> one Outbox intent even under duplicate/concurrent repair; re-checks affected-set/EXPIRED/cancel/deadline/provider-evidence/budget; preserves audited EXPIRED history; Provider evidence -> RECONCILE_ONLY). Added 12 regression tests; tests 31 -> 43 passed; full api suite 431. Real Celery/Redis/PostgreSQL/Provider/load/fault-injection still NOT RUN.
- Day56 review-round (Codex) concurrency P1 fixes — P1-1 HALF_OPEN probe acquisition is the ATOMIC lock-guarded try_acquire_probe at CALL time (the read-only has_probe_capacity is only a cheap early-out); two racing Workers can never both probe past half_open_max_probes and the loser releases its rate permit and DEFERs (no permit leak). P1-2 repair_redispatch runs the repair-id claim + eligibility rechecks + reservation + audit + status change + single Outbox intent inside ONE lock-guarded critical section, so two concurrent repairs of the same id yield exactly one REDISPATCHED + one ALREADY_APPLIED, one Outbox intent, one reservation. In-memory threading.Lock models the atomic boundary (a real system uses DB row locks / INSERT ... ON CONFLICT / SELECT ... FOR UPDATE, or Redis Lua). Added 2 real concurrency regression tests (threading.Barrier); tests 43 -> 45 passed; full api suite 433. This is IN-MEMORY CONTROL-FLOW concurrency, NOT PostgreSQL isolation / real Redis / Celery / production validation.
- Day56 review-round (Codex) concurrency P1 fix — TenantBudgetLedger now runs every reservation/balance operation (reserve_worst_case, has_reservation, settle_actual, release_reservation, hold_for_reconciliation, available, can_afford) under a ledger-level lock, so the affordability check + balance deduction + reservation write are ONE atomic critical section; two Jobs racing a tenant whose balance covers only one can never both pass the check and overspend, and reserve_worst_case is idempotent per job_id (no double-charge). Existing semantics preserved (reservation is the tenant durable ledger not the limiter; worst-case = bounded input + output; actual>reserved -> protected reconciliation; settle releases unused; deadline expiry releases only with no execution evidence). In-memory lock models the atomic boundary a real PostgreSQL ledger provides (UPDATE ... WHERE available - reserved >= :amt RETURNING / SELECT ... FOR UPDATE). Added 3 concurrency/idempotency regression tests (threading.Barrier); tests 45 -> 48 passed; full api suite 436. In-memory control-flow concurrency only — NOT PostgreSQL isolation / real Redis / Celery / production. The in-memory artifact now exercises concurrency control flow for the rate permit, HALF_OPEN probe, repair idempotency, and budget reservation.
- Day56 review-round (Codex) concurrency P1 fix — CircuitBreaker now guards ALL per-failure-domain state (_state, _fails, _probes_in_flight, _probe_successes) under one threading.RLock, so every read-modify-write is atomic: concurrent record_failure never loses a count (the circuit reliably OPENs at the threshold) and concurrent HALF_OPEN probe success/failure never lose an in-flight decrement or overwrite a state transition. RLock (reentrant) avoids nested-lock deadlock (a locked method may call state()); has_probe_capacity stays a hint, try_acquire_probe stays the authoritative atomic acquire, the probe loser still releases its rate permit and DEFERs, and OPEN/HALF_OPEN/CLOSED progressive recovery is preserved. Added 3 threading.Barrier concurrency-state regression tests; tests 48 -> 51 passed; full api suite 439. In-memory control-flow concurrency only — NOT Redis Lua / PostgreSQL isolation / Celery / production. The in-memory artifact now exercises concurrency control flow for the rate permit, HALF_OPEN probe, repair idempotency, budget reservation, and CircuitBreaker state.
- Day56 review-round (Codex) concurrency P1 fix — CircuitBreaker.record_probe_success now only counts toward progressive recovery (and may CLOSE) when the domain is STILL HALF_OPEN. Because several probes can be in flight, a LATE success returning after another probe already failed and re-OPENed the circuit releases its in-flight slot but does NOT count, does NOT flip the known failure back to CLOSED, and (being uncounted) does NOT carry into the next HALF_OPEN round — a failed probe latches OPEN. RLock atomic boundary kept (no re-entry deadlock); HALF_OPEN-fail-reopens, try_acquire_probe as the sole atomic acquire, and progressive multi-success close preserved. Added 3 regression tests (controlled-order + concurrent); tests 51 -> 54 passed; full api suite 442. In-memory control-flow concurrency only — NOT Redis Lua / PostgreSQL isolation / Celery / production.
- Day56 repository status update

---

## Superseded — Day55 Last Completed Lesson (archived)

Day55 — Celery, Worker Execution and Long-running AI Jobs

Completed Time:
2026-08-05

Main Artifact:
Day55 Celery Worker execution/recovery (projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md) with a runnable provider-neutral in-memory model (day55_celery_worker_execution.py; standard-library delivery/execution/recovery control flow, the guarded completion reusing Day53's pydantic-backed strict validation gate and the Day54 durable-cancellation terminal mapping) + test_day55_celery_worker_execution.py: moves accepted long-running AI Jobs from the Day50 Outbox Relay onto a SUPPORTED Celery broker transport (CeleryBrokerSim models publish/deliver/redeliver-via-visibility-timeout/ack/dead-letter only — NOT the Day40 custom Redis Streams / Consumer Group design, NOT a hand-built Celery replacement) and Celery Workers, with PostgreSQL the single source of business truth. The Outbox Relay publishes the Celery task BEFORE the published checkpoint (crash-between duplicates the publish, absorbed by the guarded claim; checkpoint-first strands a queued Job; ambiguous publish != success). The FIRST duplicate-call gate is an atomic PostgreSQL-owned GUARDED CLAIM (claim_execution: UPDATE ... WHERE status IN ('queued','running') RETURNING): one row = Provider execution authority, zero rows = STOP before the call — a lease is temporary ownership and a fencing token rejects stale durable writes but cannot undo an already-issued Provider request, so neither is the first gate. ClaimStatus routes GRANTED / CONFLICT (another live Worker -> redeliver, don't ACK) / ALREADY_TERMINAL (duplicate -> safe no-op ACK, 0 calls) / RECONCILE_ONLY (PENDING_RECONCILIATION redelivery -> reconcile from existing Attempt evidence, 0 re-calls). Eight identity layers stay distinct; redelivery/new Worker retains the open Attempt + provider_idempotency_key (only an explicit A2 gets a new key); provider_request_id is recorded at Provider-request open. ACK timing: early ACK silently LOSES a delivery on crash; late ACK (default) REDELIVERS and the app absorbs duplicates. Celery ACK/SUCCESS = delivery handled, NOT Job succeeded (GET /jobs/{id} reads the durable JobStore, not the result backend). Provider timeout / Worker OOM -> non-terminal PENDING_RECONCILIATION, reservation retained (unknown usage never 0), NO blind re-call; the long call stays OUTSIDE any DB transaction. Poison is durably classified and never ordinary-requeued: unsupported envelope_version (job.dispatch.v2) is detected BEFORE Job load -> dead-letter + ACK, 0 calls, Job untouched; unsupported persisted execution-contract is detected AFTER Job load -> durable QUARANTINED + ACK, 0 calls (disjoint version spaces); a transient failure retains Attempt/evidence and redelivers for a bounded retry whose backoff DEPTH is Day56. Day54 cancellation preserved: request_cancellation commits a durable intent FIRST, optional Celery revoke is best-effort AFTER (never authority), the cooperative Worker checks the intent at safe points (pre-call -> 0 calls + guarded terminal; final pre-completion -> a durable intent after the last token still prevents succeeded); terminal_for_intent maps user cancel -> CANCELLED, deadline -> EXPIRED; completion vs cancellation is one guarded winner (loser -> 0 rows); a crash after intent is re-observed at-least-once with repeats absorbed. Graceful drain stops new claims, drains in-flight bounded, checkpoints, ACKs and exits (abandoned work redelivers; force-kill != business cancellation). The erroneous early-ACK release incident is contained by rolling the config back FIRST (future harm only, NOT a business-fact rollback), building the affected set from release version + a bounded time window + Worker/Attempt/Event evidence (no bulk flip), and classifying repair from evidence (provider_request_id present -> RECONCILE_ONLY, never blind re-dispatch; no execution evidence -> explicit guarded audited redispatch; a client idempotency key proves acceptance only).

Validation Boundary:
Day55 has IN-MEMORY control-flow evidence only. Executed: python3 -m pytest -q test_day55_celery_worker_execution.py -> 40 passed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3; the delivery/execution/recovery control flow is standard-library only, the guarded completion reuses Day53's pydantic-backed validation gate); full projects/ai-backend-data-layer/api/ suite -> 388 passed. Includes the review-round F1-F5 + P1 regression fixes (lease-expiry-with-evidence -> reconcile-only; post-claim pre-Provider cancellation re-check; provider_request_id event attributed to the real Job; time-window-bounded affected set; published celery_task_id == job_id revoke invariant; P1 conservative pre-dispatch external-call marker so an OOM before recording the request id still reconciles). This proves APPLICATION CONTROL FLOW over an in-memory model only. NOT RUN: a real Celery broker (Redis/RabbitMQ) transport + Worker process; real ACK/redelivery/visibility timeouts; Worker-loss/OOM/redelivery fault injection; real PostgreSQL transactions/isolation; Redis; the real OpenAI SDK/network/Provider. A fake/in-memory test does not prove actual Celery ACK, broker redelivery, Worker-loss, or PostgreSQL behavior. Day53/Day54 evidence is NOT inherited as Day55 evidence. Boundary preserved verbatim: Celery ACK/SUCCESS != Job succeeded; broker redelivery != permission to call the Provider again; Worker identity != durable Attempt identity; Provider timeout/Worker loss != proof of no Provider execution or zero cost; Celery revoke != durable cancellation authority; configuration rollback != business-fact rollback. Day56 retry/backoff/rate-limit/token-cost/backpressure and Day57 integration/failure-injection/recovery verification are not implemented. Schema honesty: the cancelled/expired/pending_reconciliation/quarantined statuses, a durable cancellation/expiry intent table, per-Job open_attempt_id, and per-Attempt provider_idempotency_key/provider_request_id/(schema_name,schema_version) fields are new facts modeled in-memory; the real schema needs a Day48-safe forward additive migration, not implemented here, never a rewrite of published history. Day50 Job/Outbox/Relay, Day53 guarded completion/strict validation, and the Day54 cancellation protocol are reused. No real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.

Completed Work:

- Day55 classroom learning
- Day55 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved; six misconception corrections; assistant-assisted final Chinese Mental Model labeled as such)
- Day55 design/runbook + runnable provider-neutral in-memory model (standard-library delivery/execution/recovery control flow + reused Day53 validation gate + Day54 cancellation mapping) + tests (executed: 27 passed; full api suite 375) and project README increment
- Day55 guarded-claim, identity-layer, ACK-timing, timeout/OOM-reconciliation, poison-vs-transient, envelope-vs-execution-contract, durable-cancellation-in-Celery, Outbox-ordering, graceful-drain, and erroneous-early-ACK-recovery exercises
- Day55 FastAPI cheat sheet append
- Day55 FastAPI interview notes append
- Day55 requirements-day55.txt (pydantic + pytest; guarded completion reuses Day53's validation gate)
- Day55 review-round (Codex) fixes — F1 lease-expiry/redelivery re-claim with Provider evidence -> RECONCILE_ONLY (Job -> PENDING_RECONCILIATION, zero re-calls); F2 post-claim pre-Provider durable cancellation re-check (RUNNING intent -> zero Provider calls + guarded terminal); F3 provider_request_id_recorded attributed to the real parent Job via attempt_id->job_id with attempt_id/provider_request_id/correlation_id evidence; F4 build_affected_set bounded by release + running_since time window + running evidence (out-of-window same-release running Jobs excluded); F5 published invariant celery_task_id == job_id so revoke targets the correct task (durable intent still sole authority). Tests 27 -> 36 passed; full api suite 384. Real Celery broker/Worker, ACK/redelivery/visibility-timeout, Worker-loss/OOM fault injection, real PostgreSQL/Redis, and the real Provider still NOT RUN.
- Day55 review-round (Codex) P1 recovery-gap fix — a conservative durable marker (provider_dispatch_started_at) persisted BEFORE the Provider request leaves the process (order: guarded claim -> marker -> Provider call -> record provider_request_id -> validate/terminal); a redelivery reconciles when the Attempt has EITHER a provider_request_id (strong evidence) OR the marker (conservative evidence), so a Worker OOM after dispatch but before recording the id no longer causes a blind Provider re-call (missing id != not executed); accepted safety-first false positive (marker set, request maybe not sent) -> reconcile, never retry. Tests 36 -> 40 passed; full api suite 388. Real Celery broker/Worker, ACK/redelivery/visibility-timeout, Worker-loss/OOM fault injection, real PostgreSQL/Redis, and the real Provider still NOT RUN.
- Day55 repository status update

---

## Superseded — Day54 Last Completed Lesson (archived)

Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation

Completed Time:
2026-08-04

Main Artifact:
Day54 streaming/lifecycles/cancellation (projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md) with a runnable provider-neutral in-memory model (day54_streaming_disconnects_timeouts_cancellation.py; standard-library control flow, the late-result path reusing Day53's pydantic-backed strict validation gate) + test_day54_streaming_disconnects_timeouts_cancellation.py: separates TWO streaming kinds (transient Provider token streaming vs durable Job progress/event streaming) and THREE independent lifecycles (HTTP client connection / Provider request / durable Job), with the explicit boundary HTTP disconnect != the Provider call necessarily stops != the persisted Job auto-cancels != the accepted business commitment disappears. An SSE disconnect (SubscriptionRegistry) ends ONLY that subscription and never touches the durable JobStore (the Job stays running); a reconnecting browser reads durable state + safe milestone events via reconnect_view, not a Provider token replay, and raw tokens are never default-persisted (Day53 minimization). A Provider timeout is a NON-terminal PENDING_RECONCILIATION (reservation retained, unknown usage never 0, no blind re-call, the 202 not retro-504; the Provider may have raw output but does NOT create the application Result Artifact — only Day53 validation + guarded completion does). Cancellation/deadline is a DURABLE, auditable, cooperative, guarded protocol: the Router (request_cancellation) persists a durable intent FIRST (reason/actor/timestamp/version) and never writes cancelled merely because HTTP arrived; a cooperative Worker (run_worker) observes it — pre-call it does NOT call the Provider (zero Provider calls) and takes a guarded_terminal_transition; mid-stream it best-effort aborts the stream, holds reconciliation_pending (never fabricating remote stop or zero cost) and takes a guarded transition; the terminal fact is DERIVED from the intent kind (terminal_for_intent: user cancel -> CANCELLED, deadline -> EXPIRED) across pre-call/mid-stream/pre-completion/crash re-observation; provider_request_id is persisted at Provider-request open (so a later cancel/timeout is RECONCILE_UNKNOWN_EXTERNAL, not NO_PROVIDER_EXECUTION_EVIDENCE); and a durable intent after the last token but before completion is caught by a final cooperative check that does not write succeeded. Completion and cancellation/expiry each use a guarded terminal write (UPDATE ... WHERE status IN (live) RETURNING) so exactly ONE wins and the loser sees zero rows and reconciles; a late Provider result reuses Day53's identity binding (job_id + attempt_id + correlation_id + provider_request_id, missing == mismatch) + strict validation gate before any Artifact (ingest_late_provider_result); mismatch/missing/not-awaiting/terminal/invalid -> side-effect-free refusal (terminal -> REFUSED_TERMINAL); matched completes at most once; zero Provider calls. A crash after intent persistence is recoverable (scan_open_intents + apply_cancellation re-observe at-least-once, guarded transition absorbs repeats). Integrated exercise: an erroneous disconnect->cancel deployment is contained by rolling the policy back FIRST (future harm only, NOT a business-fact rollback), building the affected set from release version + a bounded time window + stable intent IDs, retaining audit, and classifying recovery from evidence (idempotency key proves acceptance only, not Provider execution; request id + unknown usage -> retain reservation + reconcile, never a blind flip/re-call).

Validation Boundary:
Day54 has IN-MEMORY control-flow evidence only. Executed: python3 -m pytest -q test_day54_streaming_disconnects_timeouts_cancellation.py -> 27 passed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3; streaming/lifecycle/cancellation control flow is standard-library only, the late-result path reuses Day53's pydantic-backed validation gate). This proves APPLICATION CONTROL FLOW over an in-memory model only. NOT RUN: real FastAPI/SSE wire behavior; the real OpenAI SDK/network/Provider token stream; real PostgreSQL transactions/isolation; Redis; Celery. Day53 evidence is NOT inherited as Day54 evidence. Boundary preserved: the three lifecycles are independent; a disconnect ends only a subscription; a timeout is non-terminal reconciliation; cancellation is durable+auditable+cooperative+guarded; Day55 Celery Worker execution and Day56 retry/backoff/backpressure are not implemented. Schema honesty: the cancelled/expired/pending_reconciliation statuses and a durable cancellation/expiry intent table are new facts modeled in-memory; the real schema needs a Day48-safe forward additive migration, not implemented here, never a rewrite of published history. No real credentials, raw prompts, Document content, or raw Provider payloads/tokens are persisted or logged.

Completed Work:

- Day54 classroom learning
- Day54 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved; four correction trajectories; assistant-assisted final Chinese summary labeled as such)
- Day54 design/runbook + runnable provider-neutral in-memory model (standard-library control flow + reused Day53 validation gate) + tests (executed: 27 passed) and project README increment
- Day54 three-lifecycle, two-streaming-kind, reconnection/persistence-trade-off, timeout-reconciliation, durable-cancellation-protocol, completion-vs-cancellation-race, crash-re-observation, late-result-refusal, and erroneous-disconnect-policy recovery exercises
- Day54 FastAPI cheat sheet append
- Day54 FastAPI interview notes append
- Day54 requirements-day54.txt (pydantic + pytest; late-result path reuses Day53's validation gate)
- Day54 repository status update

---

## Superseded — Day53 Last Completed Lesson (archived)

Day53 — OpenAI SDK, Provider Boundaries and Structured Output

Completed Time:
2026-08-04

Main Artifact:
Day53 OpenAI SDK provider boundary + structured output (projects/ai-backend-data-layer/api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md) with a runnable provider-neutral model (day53_openai_provider_structured_output.py) + test_day53_openai_provider_structured_output.py using REAL Pydantic v2 validation + an INJECTED FAKE transport (the real openai SDK is intentionally not a dependency; all SDK objects/exceptions are modeled inside the Adapter): puts an OpenAI-compatible Provider behind an application-owned boundary so SDK behavior, untrusted output, cost evidence, and configuration changes cannot corrupt durable Job facts. OpenAICompatibleAdapter owns ALL SDK objects/exceptions and translates them into a typed ProviderOutcome union (ProviderSuccess/ProviderRefusal/ProviderIncomplete/ProviderTimeout/ProviderAuthenticationError/ProviderRateLimited/ProviderCapabilityError/ProviderTransportError), reuses one lifespan-owned client, enforces effective_max = min(Job cap, ceiling) (5000 wins over 8000; usage reported, no second reservation), and never completes Jobs or writes DBs. A ProviderSuccess payload is UNTRUSTED until a strict Day44 StructuredOutputValidator (extra=forbid) validates it against the Job's bound server-owned versioned SchemaRegistry schema (research_summary.v1/v2; missing citations/forbidden debug_prompt -> CONTRACT_VIOLATION; unknown version -> SCHEMA_NOT_FOUND; a v2 output never silently satisfies a v1 Job), and only then does CompletionService run the ONLY guarded running -> succeeded short UoW (zero rows -> stop, never overwrite) persisting a Result Artifact of the validated domain result + safe metadata ONLY (raw minimization). Business execution success and cost settlement are SEPARATE axes: a valid output can succeed even when usage is UNKNOWN, retaining the Day52 reservation as reconciliation_pending (never zero); refusal/incomplete/timeout/401-403 (disable the Provider config + keep evidence)/429 (downstream Job event + safe Retry-After, not a client 429)/400 (capability/config failure) are classified without fabricating success or cost. Integrated exercise: a rollout to a model lacking research_summary.v1 gives NEW calls a 400, but a legitimate OLD in-flight v1 result (a distinct call) still validates against its PERSISTED execution contract and is accepted via guarded completion — configuration rollback governs NEW calls and is NOT a rollback of durable business facts. The outgoing Provider call is bound to the persisted execution contract (bind_request_to_contract derives model/schema/version/task/profile from the contract; a mismatch is CONTRACT_MISMATCH before any transport call; the token budget is tightened, never enlarged); an ATOMIC pre-call claim creates exactly one in-flight Attempt BEFORE any paid Provider call (only a RUNNING Job with no open Attempt wins; a terminal/pending Job re-execute OR a concurrent caller is PRECALL_BLOCKED with zero transport calls, so two Workers cannot both issue a paid call) and a late result after a timeout is handled by a no-adapter ingest_late_outcome path that validates the persisted Attempt (attempt_id + correlation + provider request id) -> guarded completion (mismatch -> LATE_OUTCOME_REJECTED; any late outcome on a terminal Job -> COMPLETION_NOOP with no fact change) and Path B consumption is concurrency-safe + idempotent (an atomic claim_late_outcome flips the Attempt AWAITING_LATE_OUTCOME -> PROCESSING_LATE_OUTCOME, so at-least-once duplicate/concurrent late deliveries dispatch at most once, then the Attempt is CONSUMED; a recorded provider_request_id must be matched exactly, a missing incoming id is rejected; and the winner's dispatch is one UoW that rolls any partial write back on a dispatch failure before reopening the Attempt), never a second execute_job; a Provider timeout is a NON-terminal PENDING_RECONCILIATION lifecycle (not a terminal FAILED, reservation retained, no auto-retry); every known-usage non-success (validation failure / refusal / incomplete) settles the exact usage via a Day52-compatible record_cost (unknown -> reconciliation_pending), and a config-wide capability 400 fails the Provider config closed while a single-request 400 does not.

Validation Boundary:
Day53 has REAL Pydantic v2 validation + control-flow evidence. Executed: python3 -m pytest -q test_day53_openai_provider_structured_output.py -> 48 passed (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3). This proves the REAL structured-output validation gate + application control flow (Adapter -> Validator -> CompletionService) with an INJECTED FAKE transport ONLY. NOT RUN: the real openai SDK / network / Provider; real PostgreSQL / Redis / Celery Worker; FastAPI wire; integration; production. Day52 evidence is NOT inherited as Day53 evidence. Boundary preserved: SDK types stop at the Adapter; the persisted execution contract governs result acceptance while current Settings governs new calls; Day54 streaming/disconnect/cancellation, Day55 Celery, and Day56 retry/backoff/degradation are not implemented. Schema honesty: the persisted execution-contract facts, Result Artifact shape, and per-Job cost-reconciliation state are modeled in-memory; a real deployment adds any new columns via a Day48-safe forward additive migration, never a rewrite of published history. No real api_key, base_url secret, raw prompt, Document content, or Provider response is persisted or logged.

Completed Work:

- Day53 classroom learning
- Day53 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved; four correction trajectories; assistant-assisted final Chinese Mental Model labeled as such)
- Day53 design/runbook + runnable provider-neutral model + tests (executed: 48 passed) and project README increment
- Day53 SDK-boundary, ProviderOutcome union, Day44 validation gate, server-owned versioned schema, guarded completion, success-vs-cost axes, error classification, and rollout/rollback exercises
- Day53 FastAPI cheat sheet append
- Day53 FastAPI interview notes append
- Day53 requirements-day53.txt (pydantic + pytest; fake transport, no openai dependency)
- Day53 repository status update

---

## Superseded — Day52 Last Completed Lesson (archived)

Day52 — Authorization, Tenant Isolation, Quotas and API Security

Completed Time:
2026-08-04

Main Artifact:
Day52 authorization + tenant isolation + quotas (projects/ai-backend-data-layer/api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md) with a runnable provider-neutral, standard-library-only in-memory model (day52_authorization_tenant_quota_security.py) + test_day52_authorization_tenant_quota_security.py: turns Day51's trusted user_id into current, tenant-scoped, action-specific, cost-aware authority. A client-supplied tenant_id is only a SELECTOR; authority is the server-built AuthorizedTenantContext(user_id, tenant_id, permissions) produced by authorize only after verified identity + active tenant_memberships(user_id, tenant_id, role, status) + the required action (effect-named job.create/job.read_own/job.read_all/job.cancel/job.retry; every failure a generic 403; Membership removal/role downgrade revokes authority per request, so a JWT role claim is not sole long-lived authority). Tenant + owner scoped reads (JobRepository.read_job -> WHERE tenant_id = authorized AND job_id; job.read_own also requires created_by_user_id == authenticated_user_id) return a public 404 on a cross-tenant miss (no existence oracle); FastAPI Dependencies centralize policy but repositories must carry the context (RLS optional defense-in-depth whose tenant context comes from AuthorizedTenantContext, never Header/Body). Three distinct controls: a shared, fail-closed TokenBucketRateLimiter (speed; multi-instance local counters undercount ~4x100=400; outage on a paid path -> 503 not 429; healthy breach -> 429 + Retry-After); a durable PostgreSQL token/cost quota via a guarded UPDATE tenant_budgets SET reserved_tokens = reserved_tokens + :amt WHERE token_limit - used_tokens - reserved_tokens >= :amt RETURNING single winner with Reservation + Job + Outbox committed in ONE transaction (all-or-nothing rollback -> no ghost reservation / unfunded Job) plus reconcile that safely settles actual usage (actual <= reserved records the exact actual and releases the remainder; actual is None holds reconciliation_pending; a negative actual is rejected; actual > reserved returns OVERAGE_RECONCILIATION_REQUIRED keeping the reservation and recording the exact observed usage + reason, never min()-truncating or releasing as settled — a real system reserves total billable cost, not only max_tokens, and Day53's Provider adapter owns estimate/headroom + overage policy) — and reconcile is IDEMPOTENT via a per-job lifecycle status (RESERVED -> {RECONCILIATION_PENDING} -> SETTLED | OVERAGE_RECONCILIATION_REQUIRED): an at-least-once repeat of the same actual is a no-op, a different actual after SETTLED returns RECONCILIATION_CONFLICT (no re-settle, no fake overage), a post-overage plain reconcile stays in overage, and only an explicit settle_overage may change the fact — and it never bypasses the hard quota (it settles the full observed usage only when available stays >= 0 via tenant headroom or a trusted ops-approved granted_extra_tokens credit, else stays in overage; idempotent; the exact usage + credit are retained as audit); and a concurrency limit. Idempotency runs AFTER authorization (admit_job: authorize -> same-command tenant-scoped recovery with no new cost/no rate-limit charge -> rate-limit new commands -> reserve + create): the request fingerprint is COMPUTED SERVER-SIDE (compute_request_fingerprint = SHA-256 of canonical JSON of behavior-relevant fields max_tokens/document_id/task_type, never Python hash(), never client-asserted): same tenant+key+same SERVER fingerprint returns the original Job with no second reservation, any changed behavior-relevant field yields a different fingerprint -> 409 with no new facts, and a removed Membership blocks old-Key recovery (not an authz bypass). Production exercise: an erroneous member -> job.cancel grant is contained by rolling back the bad grant (future traffic only), then a guarded repair_bad_intent targeted by stable intent ID + policy_version invalidates pending bad intents (zero UPDATE ... RETURNING rows -> stop and reconcile; a legitimate later cancel is never overwritten; intents retained as audit evidence, never deleted).

Validation Boundary:
Day52 has IN-MEMORY control-flow evidence only. Executed: python3 -m pytest -q test_day52_authorization_tenant_quota_security.py -> 32 passed (Python 3.10.12, pytest 7.4.3; module + tests are Python-standard-library only). This proves APPLICATION CONTROL FLOW over an in-memory model only. NOT RUN: real PostgreSQL (constraint/transaction/isolation/UPDATE ... RETURNING/RLS/SQLAlchemy/migration); real Redis (distributed limiter atomics/TTL/failover/multi-process); real FastAPI/proxy/browser (Dependency/CORS/cookie/CSRF/Header/routes); Provider/Worker/Outbox transport; integration; production. Day51 evidence is NOT inherited as Day52 evidence. Boundary preserved: authority is the server-built AuthorizedTenantContext; a client tenant_id is never authority; Day53 puts the real Provider behind this boundary, Day54 owns streaming/cancellation, Day55 owns real Celery Workers. Schema honesty: tenant_memberships, tenant_budgets(token_limit/used_tokens/reserved_tokens), per-Job max_tokens, and a cancel-intent audit ledger with policy_version are new facts modeled in-memory; the real schema needs a Day48-safe forward additive migration, not implemented here, never a rewrite of published history. No real JWT, Provider key, password, raw prompt, Document content, or user data is used or logged.

Completed Work:

- Day52 classroom learning
- Day52 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved; four correction trajectories; assistant-assisted final synthesis labeled as such)
- Day52 design/runbook + runnable provider-neutral standard-library-only in-memory model + tests (executed: 32 passed) and project README increment
- Day52 authentication-vs-authorization, Membership/role/action, AuthorizedTenantContext + tenant/owner scope (404 no-oracle), safe API boundary, rate-limit vs quota vs concurrency, guarded reservation + atomic Reservation+Job+Outbox + rollback + reconcile, idempotent recovery, and erroneous-cancel-grant containment/guarded-repair exercises
- Day52 FastAPI cheat sheet append
- Day52 FastAPI interview notes append
- Day52 repository status update

---

## Superseded — Day51 Last Completed Lesson (archived)

Day51 — Authentication, Password Security and JWT

Completed Time:
2026-08-03

Main Artifact:
Day51 authentication (password security + JWT + refresh sessions) (projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md) with a runnable provider-neutral control-flow model (day51_authentication_jwt.py) using REAL crypto — Argon2id via argon2-cffi and asymmetric RS256 JWT via PyJWT + cryptography with EPHEMERAL in-process keys — plus test_day51_authentication_jwt.py and an in-memory user + AuthSession store: adaptive Argon2id password hash/verify with a SECURE production default (library default cost; operators tune to deployment hardware; tests inject weak params only) (hash encodes algo/salt/cost; one generic authenticate failure + decoy verify; needs_rehash upgrade; a fast SHA-256 digest is used only for a high-entropy refresh secret, never a password); minimal non-secret JWT claims (sub/iss/aud/iat/exp/jti; never a password hash/provider key/prompt/Document content/secret/client tenant); a full verification contract (verify_access_token pins RS256, resolves a trusted key by an allowlisted kid, verifies signature + iss + aud + exp + nbf + required sub -> AuthenticatedIdentity(user_id=sub), rejecting alg=none/HS256-confusion/wrong-iss-aud/expired/nbf/missing-sub/tamper); kid allowlist + trusted-source unknown-kid refresh (else reject) + emergency revoke_key that ALSO blocks signing (revoking the current signing key fails closed until a prepared K2 is promoted) + planned K1->K2 overlap then drop_key; a per-device Refresh AuthSession storing only refresh_token_hash with a guarded rotate_refresh modeling UPDATE ... RETURNING (single winner; all-or-nothing rollback keeps A on partial-persistence failure), a bounded one-time grace (GRACE_RETRY recovers the SAME usable replacement token B once from a short-TTL encrypted recovery slot, never A->C) vs REPLAY_DETECTED on ANY used family token (tracked in a per-family used-hash ledger, not just the latest) that revokes and RETAINS the token_family audit evidence and isolates other devices, plus sweep_expired_recovery_material — a minimum-retention cleanup that destroys the recovery ciphertext + grace hash once past retry_grace_expires_at even if the old token never returns (fail-closed on time; used-token ledger + audit retained so post-grace replay stays REPLAY_DETECTED; a real deployment runs it as a reliable scheduled job) — and revoke_session (current device) vs revoke_all_user_sessions (all revoke paths destroy recovery material immediately via a shared _clear_recovery_material helper; the sweep is only the abandoned-token expiry fallback); and a browser cookie/Origin/CSRF decision contract (HttpOnly is not CSRF defense). Authentication establishes a trusted user_id; a client-supplied tenant_id is not authority (Day52).

Validation Boundary:
Day51 has REAL executed crypto + control-flow evidence. Executed: python3 -m pip install -r requirements-day51.txt; python3 -m py_compile day51_authentication_jwt.py test_day51_authentication_jwt.py (passed); python3 -m pytest -q test_day51_authentication_jwt.py -> 37 passed (Python 3.10.12; argon2-cffi 23.1.0, PyJWT 2.8.0, cryptography 48.0.0, pytest 7.4.3, pinned in projects/ai-backend-data-layer/api/requirements-day51.txt). These prove the REAL crypto primitives (Argon2id hashing; RS256 sign/verify) + APPLICATION CONTROL FLOW over an in-memory store only. NOT RUN: real PostgreSQL (UNIQUE/constraint/transaction/isolation or UPDATE ... WHERE ... RETURNING); real FastAPI/browser (cookies/SameSite/Origin/CSRF at the wire); a real JWKS endpoint; integration; production validation. JWE (encrypted JWT) is out of scope — a normal signed JWT is readable. Boundary preserved: authentication establishes WHO the caller is (a verified sub -> user_id); a client-supplied tenant_id is not authority; tenant membership/authorization/quota are Day52; the real Provider is Day53; real Celery/broker delivery is Day55. Day50 evidence is NOT inherited as Day51 evidence. Schema honesty: a password_hash column and the per-device AuthSession table are new facts modeled in-memory; the real schema needs a Day48-safe forward additive migration, not implemented here, never a rewrite of published history. No plaintext passwords, refresh tokens, JWTs, or operational signing keys are committed.

Completed Work:

- Day51 classroom learning
- Day51 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved; assistant-assisted final synthesis labeled as such)
- Day51 design/runbook + runnable provider-neutral real-crypto model + tests (executed: 37 passed) and project README increment
- Day51 password-hash-vs-plaintext, library-verify + generic-failure, readable-JWT + minimal-claims, full-verification-contract, asymmetric-keys + rotation + emergency-revoke, Access-vs-Refresh, guarded-rotation + rollback + grace/replay + family-revoke-with-retained-evidence, and browser/CSRF exercises
- Day51 FastAPI cheat sheet append
- Day51 FastAPI interview notes append
- Day51 repository status update

---

## Superseded — Day50 Last Completed Lesson (archived)

Day50 — Idempotent AI Job API and Transactional Outbox Integration

Completed Time:
2026-08-03

Main Artifact:
Day50 idempotent Job acceptance + transactional Outbox (projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md) with a runnable provider-neutral control-flow model (day50_job_acceptance_outbox.py) using a fake in-memory store + TransportAdapter, plus test_day50_job_acceptance_outbox.py: client Idempotency-Key = identity of one logical command and a request fingerprint = evidence the semantics did not change (the key is not fingerprint material; Document order preserved unless an explicitly unordered contract); UNIQUE(tenant_id, idempotency_key) as the concurrent DB arbiter modeled by upsert_job_on_conflict (INSERT ... ON CONFLICT ... RETURNING) — same key+fingerprint returns the original Job, a changed fingerprint is 409 with no durable facts, a missing key is rejected before writes, and every referenced Document must be Day49-verified + tenant-owned; one short atomic UoW creates the Job + exactly one job.dispatch_requested Outbox intent (mid-transaction failure leaves neither; at-most-one dispatch intent = logical UNIQUE(job_id, event_type)); an Outbox Relay that never publishes inside the DB tx — claim (FOR UPDATE SKIP LOCKED + lease/owner) -> publish OUTSIDE the lock via a small TransportAdapter.publish(envelope) -> fenced checkpoint sets published_at (only a publication checkpoint, not Job success); at-least-once recovery (publish-then-crash-before-checkpoint retains + republishes as a duplicate; transient failure increments attempt_count, stores a redacted error, computes next_attempt_at with bounded exponential backoff + jitter; exhausted -> QUARANTINED retention that never marks the Job failed); relay concurrency via short claim + lease + fencing token (a stale relay cannot checkpoint after takeover) with no DB lock over transport I/O; and a Worker guarded UPDATE ... WHERE job_status='queued' RETURNING claim that absorbs duplicate delivery into a single Provider-eligible winner. No exactly-once is claimed across PostgreSQL + broker + Worker + Provider. Schema honesty: the published schema HAS UNIQUE(tenant_id, idempotency_key) but LACKS a request-fingerprint column, UNIQUE(job_id, event_type), and relay ops columns — all MODELED in-memory; the real schema needs a Day48-safe FORWARD additive migration, not implemented here, never a rewrite of published history.

Validation Boundary:
Day50 has REAL executed FAKE-ADAPTER evidence (application control flow only). Executed: python3 -m pip install -r requirements-day50.txt; python3 -m py_compile day50_job_acceptance_outbox.py test_day50_job_acceptance_outbox.py (passed); python3 -m pytest -q test_day50_job_acceptance_outbox.py -> 29 passed (Python 3.10.12, pytest 7.4.3; the module + tests are Python-standard-library only, pinned in projects/ai-backend-data-layer/api/requirements-day50.txt). These prove APPLICATION CONTROL FLOW against an in-memory fake store + transport only. NOT RUN: real PostgreSQL UNIQUE/constraint/transaction/isolation or INSERT ... ON CONFLICT/FOR UPDATE SKIP LOCKED; a real broker/Celery (ACK/redelivery/poison-task); Worker/Provider runtime; integration; production validation. Boundary preserved: acceptance is idempotent at the API via (tenant_id, idempotency_key); Job+Outbox atomicity is PostgreSQL-local; Relay delivery is at-least-once and published_at is only a checkpoint; duplicate delivery is absorbed by a guarded Worker claim; no exactly-once across PostgreSQL + broker + Worker + Provider. Day49 evidence is NOT inherited as Day50 evidence. Day51 authentication, Day52 authorization/quota, Day53 real Provider, and Day55 real Celery are not implemented.

Completed Work:

- Day50 classroom learning
- Day50 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved)
- Day50 design/runbook + runnable provider-neutral fake-adapter model + tests (executed: 29 passed) and project README increment
- Day50 idempotency-key-vs-fingerprint, DB-arbiter-vs-SELECT-then-INSERT, atomic Job+Outbox, at-least-once relay, unknown-publish recovery, backoff/quarantine, relay lease/fencing, and worker-guarded-claim exercises
- Day50 FastAPI cheat sheet append
- Day50 FastAPI interview notes append
- Day50 repository status update

---

## Superseded — Day49 Last Completed Lesson (archived)

Day49 — Upload Sessions, Object Storage and Artifact Verification

Completed Time:
2026-08-02

Main Artifact:
Day49 verified Object Storage upload boundary (projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md) with a runnable provider-neutral control-flow model (day49_upload_verification.py) using a fake in-memory Object Storage adapter, plus test_day49_upload_verification.py: server-owned deterministic key identity (client key cannot override the persisted key); expected-vs-observed verification that never rewrites the frozen expectation and never accepts an ETag as a SHA-256 (a missing full-object SHA-256 is a hard mismatch); a fail-closed content/security gate with a persistent verification hold (a transient scanner outage moves the session to a modeled `verifying` state with a `verification_hold_until` deadline so cleanup cannot delete a retrying object; unsafe content is quarantined); legal-state + expiry-guarded finalization (INITIATED/FAILED/EXPIRED and cleanup-claimed rows rejected); a create-only + version-history object adapter (exact-version inspect/delete); a MODELED atomic Document+verify Unit of Work (a mid-transaction failure leaves neither fact); server-owned full identity (bucket+key + bound version; completion rejects client-supplied identity; observed bucket/key/version/size/sha256/content-type verified); idempotent Document finalization (external verification outside the DB tx -> short guarded UoW creates exactly one Document via the modeled UNIQUE(documents.upload_session_id) + guarded transition; already-verified retry returns the same Document; a DB commit failure re-inspects the same deterministic object rather than re-uploading); completion-vs-cleanup concurrency with three distinct expiry lifecycles (cleanup_not_before = credential_expiry + clock_skew + safety_buffer, e.g. 12:00 + 2m + 1m = 12:03) and never a DB lock held across storage I/O; multipart unknown-completion recovery (parts are transport progress not a Document; a timed-out Complete inspects the deterministic final object first); output ResultArtifact ordering + crash recovery without re-calling a paid Provider; and tenant provenance modeled by the composite FK (tenant_id, upload_session_id) as distinct from UNIQUE. Schema honesty: the published upload_sessions allowlist has no verifying, so the hold is MODELED in-memory; the real schema needs a Day48-safe FORWARD migration (a verifying status via a branch revision, or a hold/lease table) — not implemented here, never a rewrite of published history.

Validation Boundary:
Day49 has REAL executed FAKE-ADAPTER evidence (application control flow only). Executed: python3 -m pip install -r requirements-day49.txt; python3 -m py_compile day49_upload_verification.py test_day49_upload_verification.py (passed); python3 -m pytest -q test_day49_upload_verification.py -> 44 passed (hardened after Codex review rounds 1-2 — verification lease/fencing, exact-version binding before scan, guarded CAS commit, and credential!=session timing; Python 3.10.12, pytest 7.4.3; the module + tests are Python-standard-library only, pinned in projects/ai-backend-data-layer/api/requirements-day49.txt). These prove APPLICATION CONTROL FLOW against an in-memory fake Object Storage adapter only. NOT RUN: real PostgreSQL FK/constraint runtime (SQLAlchemy metadata inspection proves declaration, not FK behavior); real Object Storage presign/checksum/multipart/versioning semantics (fake adapter tests prove control flow, not storage semantics); FastAPI/scanner integration; production validation. Boundary preserved: upload success is a storage-layer fact, not a verified business fact; the server owns object identity; verification compares a frozen expected contract with trusted observed evidence and never rewrites it; no exactly-once across PostgreSQL and Object Storage; unknown outcomes are reconciled from evidence and a paid Provider is never re-called on recovery. Day48 evidence is NOT inherited as Day49 evidence. Day50 Outbox, Day51 JWT, Day52 authorization, Day55 Celery, and a real Provider are not implemented.

Completed Work:

- Day49 classroom learning
- Day49 lesson document (LESSON_TEMPLATE_v2, exact 16-section order; verbatim Chinese/English student answers preserved)
- Day49 design/runbook + runnable provider-neutral fake-adapter model + tests (executed: 44 passed; hardened after Codex review rounds 1-2) and project README increment
- Day49 storage-success-vs-verified, server-owned identity, presigned-not-one-time, expected-vs-observed, Document-vs-Upload-Session, fail-closed scan, completion-vs-cleanup, multipart-unknown-completion, output-ordering, tenant-provenance, and evidence-level exercises
- Day49 FastAPI cheat sheet append
- Day49 FastAPI interview notes append
- Day49 repository status update

---

## Superseded — Day48 Last Completed Lesson (archived)

Day48 — Alembic and Safe AI Backend Schema Evolution

Completed Time:
2026-07-31

Main Artifact:
Day48 Alembic control plane (projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md) with a runnable Alembic package (day48_alembic/: minimal env.py + gated Expand/Validate/Contract revisions for the Lease evolution of app.jobs), an operational restartable FOR UPDATE SKIP LOCKED backfill (day48_lease_backfill.py, kept off the migration), and static tests (test_day48_alembic.py) — Expand adds nullable Lease columns (no fabricated default) AND additively creates an INDEPENDENT reconciliation queue table app.job_lease_reconciliation (job_id FK, reason, routed_at, resolution_status, UNIQUE(job_id)); a SEPARATE constraint revision adds CHECK ... NOT VALID including the Day36 core jobs_running_requires_lease invariant (a running Job must carry a complete Lease); the operational backfill routes unknown-ownership Jobs via INSERT INTO app.job_lease_reconciliation ... ON CONFLICT DO NOTHING (no app.jobs write, no fabrication) so the AUTOMATIC loop TERMINATES (excluded via NOT EXISTS) and is restart-safe — routing writes only the queue so it is legal after the strict constraint (a marker UPDATE that left the row running+NULL-Lease would be rejected 23514) — but queuing is TRIAGE not RESOLUTION: such a row still violates jobs_running_requires_lease and still counts in unresolved_running_without_lease (the count joins no queue table) (the Day36 remaining_targets / hard VALIDATE precondition, reached only by a trusted Lease backfill or an audited real recovery); env.py resolves the DB URL by -x db_url > env DAY48_ALEMBIC_DATABASE_URL, with the ini placeholder OFFLINE-render only (online fails fast without an external URL); VALIDATE CONSTRAINT is a separate revision; Contract is destructive and gated; a single-head linear revision graph; a minimal control-plane env.py; no long loop in any upgrade(); classify/backfill/reconcile without fabrication; forward-fix vs destructive downgrade; baseline/stamp; autogenerate review; CREATE INDEX CONCURRENTLY non-transactional

Validation Boundary:
Day48 has REAL executed STATIC/OFFLINE evidence. Executed: python3 -m pip install -r requirements-day48.txt; python3 -m py_compile day48_lease_backfill.py test_day48_alembic.py (passed); python3 -m pytest -q test_day48_alembic.py -> 44 passed (incl. jobs_running_requires_lease in Expand+Validate; queuing != resolution — a queue-routed Job still counts in unresolved_running_without_lease; VALIDATE precondition unresolved==0 reached only after a trusted Lease backfill or an audited real recovery ROUTED by classify_unknown_running_recovery (verified 'succeeded' -> Day47 completion UoW, 'failed'/'cancelled' -> guarded terminal-recovery, unknown -> keep reconciliation, 'queued'/'running' -> refused); online-requires-external-URL fail-fast vs offline-placeholder) (Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3, pinned in projects/ai-backend-data-layer/api/requirements-day48.txt); plus an offline python3 -m alembic -c day48_alembic/alembic.ini upgrade 0001_baseline:head --sql that RENDERED the Expand/Validate/Contract DDL with NO database connection. These prove migration TEXT/STRUCTURE + control flow (Alembic revision-graph + migration-source via ScriptDirectory, and fake-session backfill control flow) only. NOT RUN: PostgreSQL runtime behavior (a real NOT VALID/VALIDATE/backfill test would apply the independent Day42 raw SQL, create a legacy violating row, apply Expand, prove the old row survives, prove a new illegal write is rejected, and prove VALIDATE fails until the legacy violation is repaired/reconciled); SQLite/fake-session/`alembic upgrade`-success are NOT PostgreSQL proof, and upgrade success alone does not prove Backfill/Switch/Contract or production safety; FastAPI/Worker drain integration, real Provider, Object Storage, and production migration. Boundary preserved: a migration is a versioned transition across schema+data+every writer; Alembic is a deployment control plane != FastAPI startup != a Day47 request/Job UoW; Day46 metadata is autogenerate input, PostgreSQL/the Day42 raw SQL are authority; after real Lease data/Provider side effects, forward-fix and reconcile, never a destructive downgrade; Outbox intent is not Provider-success proof.

Completed Work:

- Day48 classroom learning
- Day48 lesson document (LESSON_TEMPLATE_v2, v3.2 continuity + Day47->Day48 mental-model evolution)
- Day48 Alembic control-plane design/runbook + runnable Alembic revisions + operational backfill + static tests (executed: 20 passed) + offline `--sql` render, and project README increment
- Day48 migration-is-more-than-DDL, Expand-no-fabricated-default, NOT VALID vs VALIDATE, classify-backfill-vs-reconcile, restartable backfill, Switch gate, Contract vs forward-fix, revision graph/baseline/stamp, control-plane boundary, real-PostgreSQL evidence, and Provider-recovery-evidence exercises
- Day48 FastAPI cheat sheet append
- Day48 FastAPI interview notes append (incl. the "不知道" stamp/new-vs-existing/failure-drill answers and the taught final synthesis)
- Day48 repository status update
---

## Next

- Day55 — Celery, Worker Execution and Long-running AI Jobs (Phase 4 — Production AI API Engineering)

Status:
Planned / Not started

---

## Future Roadmap (Day43 onward, planned; competency-gated, current horizon ~Day130)

The Day43-onward curriculum is planned as a single AI Backend product capability chain that is
competency-gated (completion = passing the Employment Readiness Gate, not reaching a fixed day; current
planning horizon ~Day130) (see `CURRICULUM.md`, `ROADMAP.md`, and Decisions 006/007/008 in `DECISIONS.md`). Phase 4 is listed below as
the **completed foundation/context**; only **Phase 5 onward is Planned / Not started**. No future lesson files
or new project directories were created, and nothing in Phase 5+ has begun.

- Phase 4 — Production AI API Engineering (Day43–Day58) — **Completed** as classroom scope + deterministic in-process `EXECUTED_LOCAL_RUNTIME` artifacts (SQLAlchemy/Alembic, Redis/Outbox/Worker, Object Storage, OpenAI-compatible provider, auth/tenant isolation, tests); real FastAPI/PostgreSQL/Redis-Celery/Object Storage/OpenTelemetry/Provider integration remains **NOT RUN**. Completed foundation/context, not part of the Planned work below.
- Phase 5 — Production Runtime Integration and Browser Tool Engineering (Day59–Day66): Day59–61 real local integration gate (FastAPI + PostgreSQL + Redis/Celery + Object Storage + Provider + OpenTelemetry), then an isolated, recoverable, auditable Playwright browser worker exposed as a permissioned AI tool.
- Phase 6 — n8n AI Workflow Integration (Day67–Day70): workflow integration over correct backends (not a low-code replacement).
- Phase 7A — LLM Application Engineering (Day71–Day78): replaceable Provider adapter + prompt contracts/versioning + structured output/function calling + streaming/caching/batching + model routing/cost + fake-Provider tests.
- Phase 7B — Agent Runtime and MCP Engineering (Day79–Day94): framework-agnostic agent runtime (loop, tools/permissions, state/budgets, durability, human approval, memory boundary, multi-agent, security); Framework/Job-Market Refresh at Day87; framework chosen Day88 behind a replaceable adapter; MCP client/server + auth + tenant isolation + remote lifecycle.
- Phase 7C — Production RAG Engineering (Day95–Day106): ingestion/parsing + chunking + metadata/tenant/ACL/provenance + embeddings/index + hybrid retrieval/filtering + query rewriting/re-ranking + grounding/citations + retrieval/answer evaluation + index migration + RAG security.
- Phase 7D — AI Evaluation, Safety and Operations (Day107–Day116): datasets/golden sets + deterministic and model-based graders + retrieval/answer/trajectory/tool-use evaluation + adversarial/failure-mode evaluation + regression/release gates + AI observability + load/security testing + incident/rollback/repair exercise.
- Phase 8 — Final Employment Capstone (Day117–Day130): thin vertical integration loop, deployment, observability, drills, portfolio, and English system-design/behavioral/resume readiness, reviewed against the Employment Readiness Gate.

Employment-readiness boundary: the curriculum builds core AI Backend capability and portfolio evidence but
does not guarantee a job; target roles are Junior / Developing AI Backend Engineer, AI Startup Backend
Engineer, and Backend Engineer on LLM/RAG/Agent products. Runtime/production evidence is claimed only when
executed and saved.

---

## Learning Progress

Completed Python Foundations:

- Day01 — Object identity, references, function objects, callable objects
- Day02 — Mutable vs immutable objects, copy behavior, hashability
- Day03 — Function parameter passing, call by sharing, mutation vs rebinding
- Day04 — Scope, LEGB, lexical scope, closure basics, late binding
- Day05 — Closures, captured environment, factory functions, late binding fixes
- Day06 — Decorators, wrappers, universal decorators, metadata preservation
- Day07 — Iterables, iterators, generators, lazy evaluation, streaming pipelines
- Day08 — Exception handling, propagation, custom exceptions, exception chaining, root cause analysis
- Day09 — Modules, packages, import execution, module cache, namespaces, import side effects
- Day10 — Type Hints, interface contracts, collection types, Optional, TypeVar, Generic, framework contracts
- Day11 — Object-oriented programming, class and instance, state and behavior, `self`, lookup, inheritance, `super()`, composition
- Day12 — Context managers, resource lifecycle, `with`, `try / finally`, `__enter__`, `__exit__`, `@contextmanager`, deterministic cleanup
- Day13 — Async programming, event loop, coroutine vs task, `await`, `gather()`, cancellation, exception propagation, semaphore, stable throughput
- Day14 — Mini project and backend architecture, layered design, thin router, service layer, browser/LLM/repository layers, dependency injection, stateless services, worker throughput
- Day15 — Git fundamentals, snapshot vs diff, immutable commits, repository vs working directory, staging area, three-tree model, HEAD/branch, detached HEAD, reset modes, reflog
- Day16 — Git branch and merge, branch as movable reference, instant branch creation, HEAD/current branch, fast-forward merge, three-way merge, merge conflict, Git as a DAG
- Day17 — GitHub workflow, protected main, pull requests, CI vs code review, branch protection, stale review, review discussion as knowledge
- Day18 — Merge strategy and code review, history for humans, development vs product history, merge commit / squash / rebase, senior review focus, review the code not the coder
- Day19 — GitHub project management, manage work not only code, Issue as work item, Label as metadata, Milestone as goal, Projects as workflow, Idea-to-Release pipeline
- Day20 — CI/CD foundations, CI as trusted quality process, pipeline (fail fast, fast feedback), quality gate, CD (repeatable delivery), workflow as code, everything as code
- Day21 — GitHub Actions fundamentals, workflow as code, execution model, trigger vs runner, hosted vs self-hosted runner, job as one fresh runner, run/uses/with, checkout, quality gate, FastAPI CI
- Day22 — GitHub Actions advanced, matrix, fail-fast, cache vs artifact, composite action vs reusable workflow, needs/if/continue-on-error, deployment pipeline, immutable digest, environment, concurrency
- Day23 — Docker fundamentals, container as isolated process (namespaces/cgroups), image vs container, image layers vs writable layer, Dockerfile, build vs run, volumes, networks, immutable replacement
- Day24 — Docker Compose, multi-service declaration, started vs ready (depends_on/healthcheck/retry), project/service/image/container, service DNS, network segmentation, volumes, env/secrets/business data, base + dev override, production boundary
- Day25 — Deployment foundations, stable public entry (DNS/Nginx/TLS), reverse proxy, HTTP->HTTPS, trusted proxy context, promote immutable digest, API blue-green + drain + rollback, Expand-Migrate-Contract, worker rollout, serialized deploy identity, AI streaming timeouts, DNS TTL
- Day26 — Kubernetes foundations, desired state vs one-time command, reconciliation control loop, Pod (one or more tightly coupled containers), Deployment (template + replicas, not scheduling), Service (stable label-based discovery), ConfigMap (non-sensitive config, same digest), Secret (Base64 != encryption, not an automatic vault), config/secret env not mutating running processes, health 200 != business success, reconciliation != business correctness, safe partial-outage rollback
- Day27 — Kubernetes workloads, Ingress L7 Host/Path/TLS routing (resource vs controller), HPA updates desired replicas on a scale target (CPU vs queue backlog, upstream limits), Rolling Update (maxSurge/maxUnavailable, strategy vs rollback vs Blue-Green), deleting v2 Pods is not a rollback, StatefulSet stable identity/PVC/headless Service/ordered lifecycle (not replication/HA), Helm templates vs Values vs Release, validation ladder (lint/template/API/runtime), never commit secrets to Values, readiness 200 != business success
- Day28 — AI Backend production architecture, request vs job lifecycle (202 + job_id), state ownership (PostgreSQL truth / Redis deliver / Object Storage bytes / memory transient), Transactional Outbox + at-least-once + idempotent processing, durable checkpoints/leases/idempotency keys (unique constraint/upsert, ACK after durable), presigned multipart upload + Upload Session verification, retry (backoff+jitter+max attempts/deadline+classification+circuit breaker), monitoring (depth vs oldest-age vs throughput), observability (stable job_id correlation, low-cardinality metrics, append-only events), failure containment + compute rollback != data repair (contain/restore/identify/rebuild/verify)
- Day29 — PostgreSQL foundations and durable relational state, write+commit the Job row before 202, server/cluster/database/schema/table/row/column boundaries, psql connects to a database (qualified name vs search_path; public is a default namespace), Job types/defaults (uuid PK gen_random_uuid, text, integer, boolean, timestamptz now(), bounded jsonb), typed columns vs JSONB-only, type vs relationship cardinality, NULL per lifecycle, NOT NULL rejects only NULL (empty/'banana' accepted), DEFAULT VALUES + RETURNING, primary key vs idempotency key, timestamptz as one absolute instant, validation ladder, durability != integrity, code rollback vs guarded data repair
- Day30 — SQL data manipulation and query fundamentals, clause chain SELECT/FROM/WHERE/ORDER BY/LIMIT, explicit columns and a unique ORDER BY tie-breaker, three-valued logic (WHERE keeps only TRUE; IS NULL; why `<> 'timeout'` drops no-error rows), INSERT with database defaults + RETURNING (rows not a count), parameterized SQL and the injection boundary (values only; identifiers need an allowlist; it does not authorize or fix concurrency), WHERE as the modification boundary with current-state guards, zero rows means the transition did not apply, AND/OR precedence in destructive statements, lost-update awareness (database-side increment or expected-old-value guard), and the contain->evidence->identify->reconcile->guarded repair->verify incident order
- Day31 — Relational modeling and data integrity, entities/attributes/relationships and ownership, when a repeated fact becomes its own entity, primary key vs foreign key vs business key, uniqueness SCOPE (UNIQUE(job_id, attempt_number), UNIQUE(tenant_id, idempotency_key) because a retry brings a new job_id), referential actions as retention policy (RESTRICT protects audit/cost evidence; CASCADE erases it), one-to-many FK placement and one-to-one via FK+UNIQUE, many-to-many junction tables carrying relationship attributes, CHECK as the legal-state boundary and what a row CHECK cannot see, normalizing Result Artifacts with derivable provenance, current state vs append-oriented job_events vs durable outbox_events intent, tenant-aware composite foreign keys, integrity vs authorization, and deploying a UNIQUE constraint onto committed duplicates
- Day32 — SQL joins, aggregation and operational queries, defining the result grain before writing the query, choosing INNER vs LEFT JOIN from what a missing row MEANS (a zero-Attempt Job is the backlog, and NULL child columns are evidence), join cardinality and row multiplication (3 Attempts x 4 Events = 12 rows; 0 Attempts + 4 Events = 4 rows, not 0), COUNT(*) counting result rows vs COUNT(child_pk) counting existence, conditional aggregation with FILTER and why moving the condition into WHERE collapses LEFT into INNER, WHERE before grouping vs HAVING after aggregation, MIN/MAX for oldest queued age and the NULL-vs-zero empty-queue distinction, SUM/AVG over incomplete cost as a claim about RECORDED facts (recorded_* naming plus completeness; never COALESCE(SUM(cost),0) on a billing page), CTE pre-aggregation as the structural fix for two independent children (DISTINCT patches counts, not SUM), stage-aware stuck detection using the current Attempt clock with a DISTINCT ON tie-breaker producing classified CANDIDATES not verdicts, half-open [start, end) windows vs BETWEEN double-counting, recorded release provenance beating time correlation for an affected set, and rollback stopping future bad writes without repairing committed rows or undoing published outbox events
- Day33 — PostgreSQL transactions and atomic state changes, BEGIN/COMMIT/ROLLBACK as one business commitment (all related DB facts commit or roll back together; ROLLBACK never undoes a prior COMMIT), the atomic Accept where at acceptance a durable Job is created together with its durable dispatch Outbox intent (a creation-time coupling, not a permanent Job<=>Outbox equivalence; return 202 only after COMMIT; a lost response is resolved by UNIQUE(tenant_id, idempotency_key) lookup), the guarded queued->running Start transition + Attempt + append-only job_started Event committed as one unit, zero affected rows being a NORMAL result the application must gate on (not a transaction failure, unlike a SQL/constraint error) so an ungated continue writes a duplicate Attempt/Event, ACID read from the scenario (Consistency enforces constraints not correct business logic; Isolation deferred to Day34), never holding a transaction across an eight-minute Provider call (two short transactions around an external phase held outside any transaction), the two distinct Provider identifiers (the pre-call recovery anchor derived from attempt_id and durable after Start, vs the Provider-returned provider_request_id persisted only in Complete) and what PostgreSQL can prove (persisted start facts) vs cannot (the external result), the Transactional Outbox lifecycle (durable intent, Relay does not take the row or reset published_at to NULL), published_at NULL vs NOT NULL meanings and the three distinct delivery checkpoints, at-most-once (may lose) vs at-least-once (may duplicate) vs exactly-once not being achieved by disabling retries (practical correctness = at-least-once + stable outbox_event_id + idempotent consumer), the Attempt-finish guard (finished_at IS NULL, never overwriting a finished Attempt's evidence; an already-finished current Attempt is isolated/reconciled, not auto-fixed), Job Events being internal history while Outbox Events are conditional external duties (not every Event needs an Outbox row), external side effects (Provider cost, Object Storage bytes) surviving a database rollback, the unknown outcome of a lost COMMIT response (read stable ids, do not assume rollback), and the transaction pack being a write-path contract that does not protect legacy separate-commit writers
- Day34 — Concurrency control, MVCC and Worker claims, candidate visibility (a SELECT / MVCC snapshot) being distinct from ownership (a transaction-local FOR UPDATE row lock, and across COMMIT a committed lease), FOR UPDATE waiting on a conflict while FOR UPDATE SKIP LOCKED skips locked rows and reserves the next available Job so Workers spread across the queue, the claim transaction reserving a candidate then reusing the unchanged Day33 guarded queued->running write with the affected-row gate and committing before the Provider call, SKIP LOCKED weakening fairness (ORDER BY sorts only available rows; no strict FIFO; starvation possible) mitigated by short claims and monitoring, a released lock not being liveness evidence (committed Job/Attempt/Event persist; blind reclaim duplicates Attempt/Event/Provider cost), a row lock (transaction-local) vs a committed lease (claim_owner/lease_token/lease_expires_at, a Day36 migration and conceptual today), lease expiry being a takeover condition not proof of death with takeover writing a new token while expiry alone invalidates ownership via the time predicate, lease duration derived from heartbeat + observed pause (2 minutes over 30 seconds for 45-second pauses) with the completion guard requiring current token + running + unexpired lease, lease_token (one ownership epoch) being separate from the stable Provider idempotency key (same external operation, derived from attempt_id and actually sent to a supporting Provider), pessimistic FOR UPDATE SKIP LOCKED spreading a high-contention queue vs optimistic guards storming a hot row, MVCC snapshots under Read Committed (100 then 101 is an allowed phantom, new snapshot per statement) vs Repeatable Read/Serializable stable snapshots that may abort with 40001 and do not partition work, and deadlock handling (a reverse-order cycle detected and one victim aborted with 40P01; consistent lock order prevents it; lock_timeout bounds waits with 55P03; the application, not PostgreSQL, retries 40P01/40001 with a finite budget while UNIQUE/idempotency constraints still stop duplicate durable facts)
- Day35 — PostgreSQL indexes and query planning, an index as an ADDITIONAL access structure over the Heap (not a replacement source of truth; FOR UPDATE SKIP LOCKED still visits and locks the real tuple, so an index speeds candidate lookup but not ownership), deriving the index from the real WHERE + ORDER BY + LIMIT rather than a chosen column (the Day34 claim -> Partial Composite (tenant_id, created_at, job_id) WHERE job_status='queued' AND cancel_requested=false; a job_status-only index is weak), B-tree column order as leading equality predicates then range/ORDER BY columns, an index key serving an access path not every selected column (unindexed columns come from the Heap; a Partial Index that omits the target rows cannot answer the query), history being several distinct paths (all-status, dynamic-status shared composite, or fixed-status partials) chosen by measured workload, a UNIQUE constraint already creating a unique B-tree so the idempotency index must not be duplicated, the Outbox Partial (created_at, outbox_event_id) WHERE published_at IS NULL with job_id selected but not a key, why now() cannot define partial membership (membership changes only on a write) so expiry is a query-time range on a stable running predicate (lease columns are Day36), EXPLAIN estimating a plan vs EXPLAIN ANALYZE really executing it (row locks on SELECT FOR UPDATE, real DML changes), a Sequential Scan being a cost-based and possibly optimal plan judged by selectivity/Rows Removed by Filter/latency/buffers not by its name, an estimate-vs-actual divergence being a statistics/data-skew/predicate/parameter-plan investigation before another index, index maintenance where queued->running touches only the claim partial index (history/idempotency keys unchanged), and the keep/rollback decision made on NET SYSTEM benefit (a broad history index that moved history p95 100->80 ms but Job acceptance p99 50->220 ms and cost +14 GB with no Worker/Outbox gain is rolled back), with all Day35 work being DESIGN + EVIDENCE only (NOT RUN) and safe deployment via CREATE INDEX CONCURRENTLY deferred to Day36
- Day36 — Schema evolution and safe migrations, a migration being a VERSIONED STATE TRANSITION across schema + existing data + every deployed application version (a successful ALTER is not a completed migration), why a direct ADD COLUMN ... NOT NULL on a populated table is rejected ATOMICALLY (existing rows have no value) and breaks old code, the Expand phase adding NULLABLE claim_owner/lease_token/lease_expires_at with NO fabricated default (old code ignores, new code tolerates NULL; even a nullable ADD COLUMN is lock-aware), a default being a BUSINESS FACT for every row (is_archived DEFAULT false only if verified; lease_token DEFAULT gen_random_uuid() fabricates an ownership epoch and risks a table rewrite so NULL honestly means no proved Lease ownership), Backfill scope being running-only while status scope does not certify ownership (an unknown running Job is isolated/reconciled, never assigned a fake token, and the backfill never calls the Provider), draining/isolating old Workers before recovery/switch because they bypass the token guard and cause double execution, backfill mechanics being small-batch/short-transaction/idempotent/restartable/observable with the target predicate (job_status='running' AND lease_token IS NULL) repeated in selection and the guarded write so the DURABLE DB state is the checkpoint (not a process counter) and FOR UPDATE SKIP LOCKED for distinct parallel batches, completion evidence being remaining-targets-0 FOR THE RIGHT REASON (every violating running row truly resolved by a trusted backfill or a real recovery, since the exception/isolation queue is triage not resolution and a parked running-without-lease row still counts and still violates the invariant at VALIDATE) plus new-write protection, CHECK ... NOT VALID enforcing new writes IMMEDIATELY while deferring the historical scan to VALIDATE CONSTRAINT (NOT NULL itself cannot be NOT VALID), CREATE INDEX CONCURRENTLY being non-transactional (cannot run inside BEGIN/COMMIT) and possibly leaving an unusable INVALID index (validity separate from net benefit), Switch requiring every writer to guard the token AND the old path to no longer write (a new binary alone is not Switch), Contract removing temporary compatibility only on evidence and an observation period (destructive), and rollback vs forward fix being decided by DURABLE STATE (after real Lease data/Job transitions/Provider/Object Storage effects a DROP COLUMN cannot undo them so forward-fix and reconcile), with all Day36 work being DESIGN + EVIDENCE only (NOT RUN) and live operation deferred to Day37
- Day37 — PostgreSQL production reliability, operating the durable truth after Day36 made the schema deployable: reachable/low-CPU being NOT reliable (a slowing AI Job system at modest CPU can be exhausted pools + an idle-in-transaction session + growing pool waits; API 202, Worker claim/complete, Attempt writes and Outbox checkpoints all depend on bounded capacity), connection pools being finite so total demand is the SUM across every process ((4 API + 12 Worker) * pool 10 = 160) which must stay below a safe connection budget with reserve for migration/monitoring/admin/recovery (a pool max is potential demand, and raising pools moves queuing into PostgreSQL), the eight-minute Provider call staying OUTSIDE the DB transaction across Accept/Claim-Start/External/Complete with the full completion guard (job_status='running' AND current lease_token AND lease_expires_at > now(), not the token alone, since expiry does not change the token) and queued->running in Claim while running->succeeded in Complete, Provider success vs Object Storage Artifact bytes vs committed PostgreSQL success being different facts (reconcile the deterministic Artifact before any second Provider call), Lease expiry being takeover ELIGIBILITY not proof the old Worker did no external work, the layered timeout model (pool acquisition, lock_timeout, statement_timeout, idle_in_transaction_session_timeout, application deadline ordered lock_timeout < statement_timeout < deadline) as failure containment not repair with SKIP LOCKED being claim selection not a timeout, liveness (restart-fixes-local?) vs readiness (safe for new traffic?) vs business success where a shared DB outage drops readiness and backs off rather than failing every liveness (restart storm), MVCC dead tuples where long/idle transactions retain old snapshots and block Vacuum so you stop the source first and tune autovacuum per-table on I/O evidence (never a casual VACUUM FULL), least-privilege runtime identities that cannot DDL plus a credential rotation lifecycle (load new -> verify all switched -> recycle -> revoke old), replication NOT being backup (it copies bad writes) with recovery evidence requiring an isolated restore + PITR + integrity/business checks + measured RPO/RTO (RPO/RTO are recovery objectives not health probes; base backup is the consistent start and WAL is physical redo), monitoring that treats low CPU as proving nothing, a replica-promotion gate (replay position + data-loss estimate + explicit RPO decision + split-brain prevention + reconciliation), managed vs self-operated responsibility, and the integrated 420-vs-300 incident (12*25 + 12*10 = 420 vs max_connections 300) resolved by containing demand and rolling back the pool configuration while reconciling irreversible Provider effects and resizing the DB only on evidence, with all Day37 work being conceptual reasoning + static review only (RUNTIME NOT RUN, PRODUCTION NOT VALIDATED) and PostgreSQL staying the durable source of truth ahead of Day38 Redis
- Day38 — Redis foundations and data structures, Redis as a transient acceleration layer around the durable truth: PostgreSQL app.jobs owns the authoritative Job lifecycle/audit truth, Object Storage owns large bytes, and Redis owns only small, temporary, REBUILDABLE acceleration views + lightweight broker transport, so a missing Redis key (TTL expiry, eviction, restart, RDB/AOF loss) is a cache-miss that falls back to PostgreSQL rather than a failed Job or a duplicate Provider call, a whole Job lifecycle under a 24h TTL is rejected because the record vanishes at hour 25, structures are chosen by access pattern (String scalar/counter via INCR, Hash for named mutable fields where a JSON String would lose concurrent read-modify-write updates, List ordered-with-duplicates, Set unique membership as a VIEW not ownership, Sorted Set unique-plus-score for recent-100 completions), keys are tenant-namespaced and versioned (ai:tenant:{tenant_id}:job-progress:v1:{job_id}) with a new version only for an INCOMPATIBLE change not an additive optional field and logical databases being a namespace not isolation, single-command atomicity (INCR/HINCRBY) not spanning a two-command read-modify-write or an HSET-then-EXPIRE crash window that leaks a permanent key (composition MULTI/EXEC/Lua deferred to Day41), maxmemory/eviction being a CORRECTNESS boundary where only rebuildable keys may be evicted, RDB/AOF shrinking but never closing the loss window and never conferring ownership, broker messages carrying job_id + tenant_id + trace metadata (never truth, never a 300 MB PDF) with 202 still returned after the durable Accept, a Redis outage degrading via a BOUNDED PostgreSQL fallback that protects the database with Day37 budgets, and a missing-TTL incident fixed by a TTL-config rollback + prefix-scoped SCAN/cleanup rather than FLUSHALL, with all Day38 work being DESIGN + EVIDENCE only (RUNTIME NOT RUN, PRODUCTION NOT VALIDATED) and cache consistency/messaging/composition deferred to Day39-41
- Day39 — Redis cache design and consistency, turning the Day38 ownership boundary into an explicit per-endpoint cache consistency contract: PostgreSQL COMMIT is the moment of authority and the Redis cache is a rebuildable projection that may be STALE or ABSENT, so a cache hit is not truth and a cache miss is not a Job failure (a short TTL only BOUNDS staleness, it is not synchronization and can raise PostgreSQL load), cache-aside reads return a hit only when the endpoint tolerates it else read PostgreSQL and best-effort repopulate with a TTL (a cache SET failure never invalidates a correct PostgreSQL response), invalidation is COMMIT-FIRST then delete EVERY affected view (Job-detail AND the tenant recent-completed list) because a pre-commit delete races a reader into re-caching the old running state with a fresh TTL, an incompatible representation change (progress 42 [0-100] -> 0.42 [0-1]) needs a new versioned key v2 while additive optional fields keep the version, a fixed synchronized TTL causes a cache AVALANCHE fixed by TTL JITTER while SINGLE-FLIGHT only protects ONE hot key (one leader rebuilds, followers wait bounded or take an allowed stale value, on leader timeout use bounded retry + backoff + jitter not a full fan-out) and stale-while-revalidate serves a short stale running view for tolerant reads only, GET /progress may fail-OPEN while POST /cancel fails-CLOSED on PostgreSQL authorization + a GUARDED state transition (a cache never authorizes and a PG pre-read is not a substitute, since a job already succeeded cannot be cancelled), a short tenant-scoped NEGATIVE cache absorbs penetration by non-existent IDs but is load protection not a security control and is invalidated on creation, a HIGH hit ratio is not health (a hit can overload a hot key; measure freshness/correctness -> commit->invalidation delay/failure/backlog, cache age, stale-terminal rate, sampled Redis-vs-PostgreSQL agreement), an unknown cache-DEL outcome is recovered via a Transactional Outbox invalidation intent + a retryable idempotent DEL (never redo the Job transition or re-call the Provider, unlike Provider retries which need a stable idempotency key and Artifact reconciliation), and the v2 cache-contract incident is handled by reconciling/retrying invalidation + bounded SWR + protecting PostgreSQL FIRST and rolling back only the Redis v2 cache CONTRACT on proven incompatibility (never committed PostgreSQL Job truth and never Provider work), with all Day39 work being DESIGN + EVIDENCE only (RUNTIME NOT RUN, PRODUCTION NOT VALIDATED) and messaging/composition deferred to Day40-41
- Day40 — Redis messaging and queue semantics, using Redis Lists/Pub-Sub/Streams by their delivery and failure semantics while PostgreSQL stays durable Job truth and idempotency makes redelivery safe: a Redis Stream delivery -- even an XACK -- is TRANSPORT state, not business completion, so a Worker that consumed a message and crashed before XACK leaves the entry PENDING in the Consumer Group PEL (Redis cannot know whether the Provider/DB effect happened) and it must remain recoverable via XCLAIM/XAUTOCLAIM while PostgreSQL Job/Attempt/Event/Outbox/Notification facts + reconciliation decide completion, ACKing before processing is at-most-once (a crash silently loses the Job) so a durable recoverable decision is persisted in PostgreSQL BEFORE XACK giving at-least-once that is made safe by stable per-side-effect idempotency identities + guarded transitions + reconciliation (Redis alone gives NO exactly-once across Redis ACK + PostgreSQL commit + external Provider call), Pub/Sub is live broadcast with no backlog/ACK/PEL/Claim/replay so an offline/crashed subscriber permanently misses a message (loss-tolerant notifications only) while Streams+Consumer Groups give recoverable delivery, within one group a message goes to ONE consumer and dispatch vs completion are DISTINCT committed events at distinct lifecycle points (Accept commits a job-dispatch Outbox intent -> ai:stream:job-dispatch:v1 -> g:job-exec; Complete commits a job.completed Outbox intent -> ai:stream:job-events:v1 -> g:notify-delivery) so a completion email is driven ONLY by a committed job.completed event and never by a dispatch entry (separate groups alone only mean both could receive the same entry), with stream append order being transport order not business-completion order (guarded transitions + idempotency preserve validity), Lists may be persisted but lack native Consumer Group/PEL/ACK/Claim/redelivery so you do NOT hand-build a Celery replacement and Stream payloads carry small references (tenant_id, job_id, event_id, trace) with Object Storage owning bytes and PostgreSQL owning references/provenance, a retry LIMIT is a capacity-containment policy not an error classifier and a fixed immutable payload missing tenant_id is a permanent message-contract failure handled by bounded retry -> durable quarantine/dead-letter -> alert -> repair producer -> controlled replay (ACK the original only after quarantine evidence exists, never silently delete), trimming is a retention/capacity contract that must NEVER remove Pending or recovery/quarantine evidence (it destroys Claim/redelivery/replay), each notification effect (completion/failure/admin) needs its OWN durable delivery identity like job:{job_id}:notification:completion:v1 because a Job Attempt/Event does not prove an email was sent, and the integrated dual-crash recovery is preserve-evidence -> inspect PostgreSQL -> reconcile Provider/email by stable ids -> each group Claims its own Pending -> ACK after the recovered durable decision (never blindly rerun/repeat/delete/trim), with all Day40 work being DESIGN + EVIDENCE only (RUNTIME NOT RUN, PRODUCTION NOT VALIDATED) and coordination/composition/rate-limiting deferred to Day41-42
- Day41 — Redis coordination and production safety, using Redis for NARROW, bounded coordination/protection around the Job API and Worker lifecycle while PostgreSQL Job/Attempt/Event/Outbox stays the durable business authority: the two-Pod admission race (both read count 59, both admit) is missing ATOMICITY not necessarily a lock, so a rate-limit decision is an atomic read -> check limit -> INCR-if-allowed -> TTL -> allow/reject in ONE short Lua step (never GET->check->SET, never INCR-then-DECR compensate whose crash inflates the counter; MULTI/EXEC cannot make a decision from a prior external GET atomic and WATCH+MULTI/EXEC is the optimistic+retry alternative; do not nest MULTI/EXEC in Lua or wrap a single already-atomic command), Redis admission is an ALLOWED ATTEMPT not durable Job success so the counter is NOT compensated after a failed Accept (TTL resets the window; compensation adds a second uncertainty boundary) and the durable acceptance truth is INSERT Job(queued) + INSERT Outbox(dispatch intent) -> COMMIT -> 202 + job_id, algorithms trade off (clock-aligned fixed = cheap but a boundary burst of 60@12:00:59 + 60@12:01:00 = 120, first-write TTL = request-anchored with distinct semantics, sliding = smooth/fair for expensive AI Jobs, token bucket cap 10 refill 1/s permits a burst but rejects an 11th request 0.2s after ten are consumed), API idempotency is a client key + PostgreSQL UNIQUE (tenant_id, idempotency_key) create-or-return (Attempt/Event may not exist yet so they cannot dedup a first POST; a Redis lock only reduces optional duplicate work, the unique constraint is the authority) with API vs Provider vs notification identities kept SEPARATE, a lease (SET NX PX + opaque token, renew while owner, ATOMIC compare-and-delete release since a blind DEL lets old A delete new B's lease) has EXPIRY that permits TAKEOVER but does NOT stop a paused owner or an in-flight Provider call, a fencing generation is a MONOTONIC ownership generation whose correctness must NOT depend on rollback-able Redis so it is advanced and persisted in a PostgreSQL claim/takeover transaction (NEVER a Redis INCR, which a failover could hand out smaller/duplicate) while a UUID lease token is unordered and cannot fence, so the PostgreSQL Job Complete guard requires job_status='running' AND lease_token = current token AND lease_expires_at > now() AND fencing_generation = the current PERSISTED generation (EQUALITY, not >= or >; the generic downstream rule last_accepted_fence < incoming_fence is a separate model) while ordinary Providers still need stable idempotency + Artifact reconciliation, RDB/AOF/async-replication/failover/eviction can lose or reset counters as a TEMPORARY protection-degradation window (a low/missing counter is not 'under limit') so coordination state is isolated from LRU-evictable cache with explicit memory/TTL/eviction/alerts, security is layered (private network necessary-but-insufficient + auth + ACL scoped to the command set and ratelimit:* prefix + TLS + deny FLUSHALL/CONFIG + audit/monitoring) and managed Redis runs infra but does NOT transfer business responsibility, and the integrated failover+lease+Provider incident is contained by failing CLOSED on new expensive admission, NOT mass-restarting Workers (bounded backoff + drain + reconcile), and having Worker B reconcile durable facts + Provider idempotency + Artifact before any call rather than acting on a fresh lease, with all Day41 work being DESIGN + EVIDENCE only (RUNTIME NOT RUN, PRODUCTION NOT VALIDATED) and the integrated capstone deferred to Day42
- Day42 — Backend data design capstone (Phase 3 close), integrating the durable PostgreSQL truth (Day29-Day37) with the transient Redis coordination (Day38-Day41) and the Object Storage artifact boundary into ONE failure-aware ownership/recovery/verification contract for a multi-tenant AI Research and Automation Platform: PostgreSQL is the single source of durable truth (Job/Attempt/Event/Outbox/fencing/references + tenant + idempotency), Object Storage owns large Document/result bytes with PostgreSQL owning their references + verification, and Redis is transient/losable coordination that proves nothing durable; the acceptance contract requires only Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent committed in one transaction before 202 (Attempt/Event/lease/fencing appear at claim/takeover); dispatch is Relay publishing UNPUBLISHED Outbox intents (not a queued scan) with at-least-once DUPLICATE delivery being normal and rejected as a business effect by a guarded queued->running transition (Redis markers optional, never truth); completion is a SHORT guarded transaction (Artifact ref + Attempt finish + running->succeeded + Event) guarded by running + current lease token + unexpired lease + fencing_generation = the current PERSISTED generation, where Artifact existence ALONE is insufficient (verify identity/integrity/ownership + fencing + Provider/result) and an Artifact-first write + PostgreSQL rollback is reconciled not blindly deleted or re-called; degraded modes are scoped by boundary (Redis unhealthy -> fail-closed new expensive admission, a low counter is not quota headroom, no mass restart, bounded backoff + drain; PostgreSQL down -> no new POST /jobs accepts; input Object Storage down / upload unverifiable -> fail-closed THAT admission only, not the whole container); an Upload Session is verified before admission (tenant ownership, verified state, non-expiry, registered key, hash/size, content-type/scan); tenant isolation uses the authenticated tenant predicate + Job ID + composite tenant-aware foreign keys (a globally-unique job_id still leaks if queried alone; a cache key is not authorization); audit is APPEND-only (tombstone Artifact references + append artifact_expired/deleted on retention, never edit history); performance is justified by disposable EXPLAIN ANALYZE evidence (a described method, NOT run) that is NOT production validation; the fencing generation is rolled out durably via Expand->Contract with old Workers drained/upgraded (lease expiry never stops a paused old Worker and old code may bypass the fence); and the integrated failover + paused-Worker + Artifact-reconciliation recovery contains old claims, republishes the durable Outbox intent, reconciles Job/Attempt/Provider idempotency/Artifact, and completes under the guard without ever blindly re-calling the Provider or using Artifact existence as ownership proof, with all Day42 work being DESIGN + EVIDENCE only (RUNTIME NOT RUN, PRODUCTION NOT VALIDATED) and SQLAlchemy/Alembic deferred to Phase 4 (Day43 exposes this contract as the FastAPI AI Job HTTP lifecycle)
- Day43 — AI backend product contract and FastAPI request lifecycle (Phase 4 opens), exposing the Day42 durable data-ownership/failure contract as a precise multi-tenant AI Job HTTP API where an HTTP response is a PROMISE about COMMITTED business state: 202 is returned ONLY after one PostgreSQL transaction commits Job + (tenant_id, idempotency_key) UNIQUE + Outbox dispatch intent (an 'attempt to persist' is insufficient; 202 = a durable async commitment, not completion), 201 is created (not a redirect) and a found GET is 200 with the business status while a client-contract failure is 4xx, a same-key-different-input retry is 409, and a dependency/DB-timeout outage is 5xx (never a fake 404/202); lost-response idempotency uses the (tenant_id, idempotency_key) UNIQUE constraint + atomic create-or-return (NOT SELECT-then-INSERT) to return the original Job with no second Job/Outbox, binding the key to request meaning and keeping API idempotency separate from Provider idempotency; routing resolves method+path BEFORE the handler/DB (404 no route, 405 wrong method) so static routes are declared before dynamic (/jobs/health before /jobs/{job_id}) and validation cannot repair a routing mismatch; GET reads committed truth WHERE tenant_id = trusted_authenticated_tenant AND job_id, returning 404 (not 403) cross-tenant so the API is not an existence oracle (a UUID is not authorization) and allowlisting public fields (no lease/fencing/Provider-metadata/Object-Storage-key/Outbox/Attempt internals); the short HTTP lifecycle is separate from the durable background lifecycle (Relay -> Worker claim -> Provider -> guarded completion) so FastAPI never waits for an 8-minute Provider call and an in-process BackgroundTask is NOT a durable Worker (a deploy/crash loses it; durable execution is Day55); the Relay scans published_at IS NULL and at-least-once DUPLICATE delivery is normal, gated FIRST by the guarded queued->running (1 row winner may create Attempt/Event and call the Provider; 0 rows -> STOP) while lease/fencing protects stale COMPLETION later; Artifact existence is NOT success and cancellation uses POST /jobs/{id}/cancel as a durable audited INTENT (not a destructive DELETE) where cancel-requested != cancellation-completed (terminal mechanics are Day54); and the integrated failure/rollback exercise converges a lost-202 retry to the original Job, lets exactly one guarded-claim winner call the Provider on duplicate dispatch, returns 404 to a cross-tenant read, and (for a bad pre-COMMIT-202 release) rolls back the FAULTY API RELEASE + reconciles committed facts + adds a pre-COMMIT-window regression test rather than fabricating Jobs or replaying Provider work, with all Day43 work being CONCEPTUAL/STATIC CONTRACT REVIEW only (FastAPI / PostgreSQL / Relay-Worker / Redis-Object-Storage-Provider / integration / production runtime NOT RUN) and Pydantic v2 (Day44) / DI-lifespan-adapters (Day45) / SQLAlchemy-Alembic (Day46-48) / durable cancellation (Day54) / Celery (Day55) deferred as future boundaries
- Day44 — Pydantic v2 and structured AI input/output contracts, turning the Day43 static HTTP product contract into EXECUTABLE typed validation/serialization boundaries where the core is a boundary ladder (JSON-valid -> Pydantic-valid structure -> authenticated identity -> authorized resource/tenant -> application invariants -> PostgreSQL constraint + atomic transaction -> committed durable truth) and Pydantic occupies ONE rung (declared structure), not authorization and not a durable commit: client request models put tenant_id in TRUSTED authentication context (never a request-body field, since a claimed body tenant_id is a cross-tenant authorization risk) and use ConfigDict(extra="forbid") to reject undeclared input (a client-supplied job_status, tenant_id, unexpected_debug) instead of silently ignoring it, with max_tokens a REQUIRED strict integer bounded 1..8000 (rejecting "2000", 8001, and a missing value) and the request modeled as a discriminated union on task_type (SummarizeRequest forbids output_schema; ExtractStructuredRequest requires a non-empty, type-restricted output_schema dict[str, Literal["string","number","boolean"]]) with upload_session_id and public job_id as UUIDs (Day31 model) and Citation.url as AnyHttpUrl (a bare "https://" rejected; URL shape != authz != SSRF != grounding) while UNIQUE(tenant_id, idempotency_key) + the transaction stay the concurrency/commit authority (Pydantic cannot detect cross-tenant upload ownership); strict field-specific aliases (MaxTokens, Confidence) reject accidental coercion like "2000"->2000 or "very sure" without enabling global strictness (JSON represents UUIDs/timestamps as strings) and any needed conversion lives in an explicit tested adapter; Provider output is FULLY untrusted input validated as StructuredAIResult (extra="forbid", no Provider-owned job_status) where Pydantic validates citation/URL SHAPE but not grounding/truth; public responses are allowlisted and status-discriminated (queued/running have no result or failure; succeeded requires a result; failed requires a failure) keeping persistence/internal/public representations SEPARATE (lease token, fencing generation, raw Provider metadata, raw Object Storage key, Outbox id, unreviewed Attempt fields never leak) and a failed Job is a successfully READ resource (HTTP 200 + business status failed) distinct from the PublicErrorResponse envelope {code, message, field_errors?, request_id?} whose HTTP status is the error class and which never leaks SQL/tracebacks/credentials/raw Provider errors/cross-tenant existence; untrusted input uses model_validate/model_validate_json (model_dump serializes an already-validated model) and NEVER model_construct (which skips validation/validators/nested conversion/extra="forbid"); validation must precede side effects so validate_provider_output_before_completion raises before the completion callback runs and its negative test asserts BOTH a ValidationError AND completion_calls == [] (test the effect, not just the signal); and the production incident (a bad release used model_construct() and marked 37 Jobs succeeded) is contained by disabling the Provider-completion path and routing away, preserving evidence, rolling back the CODE and restoring model_validate, adding negative regression tests, classifying the affected set by release/time/attempt/output, and performing an idempotent guarded AUDITED repair that reconciles Job/Attempt/Event/Result Artifact (never blindly requeuing, replaying paid Provider work, deleting audit, fabricating results, or treating code rollback as database-history rollback), with Day44 carrying REAL executed Pydantic v2 runtime evidence (the repository artifact was tightened per code review, growing the suite from the classroom's 11 tests to 24 as a shared summary contract (min_length=1, max_length=10_000) was unified across the Provider result and public response; executed here on Python 3.10.12, Pydantic 2.5.0 + pytest 7.4.3 -> 24 passed, deps pinned in api/requirements.txt; completion target is an in-memory callback, not PostgreSQL) while FastAPI/auth/PostgreSQL/SQLAlchemy/real-Provider/Relay-Worker-Redis-Object-Storage/integration/production are NOT RUN and DI/lifespan/adapters (Day45), SQLAlchemy (Day46-48), and the real Provider SDK (Day53) remain future boundaries

- Day45 — Dependency injection, lifespan, configuration and AI provider adapters, composing the Day44 typed contracts into a runnable FastAPI/Worker WITHOUT letting Routers or business services own infrastructure: resource ownership is PER PROCESS (an eight-minute Provider call belongs to a Worker, not an HTTP Router, but "Worker owns it" is not one global client — only processes that actually call the Provider create one, so 8 Worker processes hold 8 independent app-scoped clients in separate memory, and a Provider client owns HTTP connections/pools NOT database connections, which are the Day47 concern); the lifespan owns expensive closeable app/process-scoped resources (validated Settings, an async HTTP client, and a concrete ProviderAdapter) and publishes a Container only after COMPLETE initialization, while Depends() SUPPLIES an already-created dependency (its default cache is request-local, NOT an app-wide or cross-process singleton) so get_provider returns the lifespan-created AIProvider and a stateless JobService is created per request/Job (a yield dependency fits a request-scoped resource like Day47's AsyncSession, not closing a shared app-scoped adapter every request); Settings is the validated secret/config boundary (API key from validated Settings, never Router code and never a Job payload since payloads are persisted/replayed/logged) where SecretStr reduces accidental print/repr/serialization exposure but is NOT memory encryption and does not stop a deliberate get_secret_value() log, and startup FAILS FAST on missing/invalid local configuration (stay not ready, do not claim Jobs) while local Settings validity != external Provider availability and a PAID generation call must NOT be sent on startup to test a key; import time declares types/routes only (no module-scope Settings/client/adapter, which would break tests during import, harm readiness classification, and lose close pairing) and create_app() is the explicit Composition Root receiving Settings + factories, with partial-initialization cleanup closing the already-created HTTP client, publishing NO Container/readiness, and claiming NO Job when adapter init fails (resources released in REVERSE creation order via asynccontextmanager/try-finally/AsyncExitStack); JobService depends on a SMALL AIProvider protocol (not a vendor SDK) with a production OpenAICompatibleAdapter that hides SDK/HTTP/response-extraction and translates vendor exceptions into stable ProviderTimeout/ProviderRateLimited/ProviderAuthentication/ProviderTransport errors and a FakeAIProvider giving deterministic no-network/no-cost tests, and the Worker Service validates raw Provider JSON via Day44 StructuredAIResult.model_validate_json BEFORE any completion (the Router validates client input, not Provider results; Day56 owns retry/backoff/cost/backpressure, not this lesson); test composition uses create_app + a fake factory + FastAPI dependency_overrides configured BEFORE entering TestClient (whose context triggers lifespan startup, and an override alone does not stop a lifespan creating a real resource) asserting the EFFECT (no network, fake used, tracking client OPEN inside / CLOSED after, empty completion on invalid output, no Secret leak) and clearing overrides after; configuration rotation keeps Settings/Container immutable per process and uses controlled process replacement (start + verify NEW Workers ready -> THEN drain OLD to stop new claims -> bounded in-flight window -> close OLD adapter/client -> verify), never draining healthy OLD before NEW is ready and keeping OLD running if the new config is invalid, with graceful shutdown ordering stop-new-claims -> drain in-flight -> close client (never close first) and an interrupted Provider call at a drain deadline NOT blindly requeued (it may have run, cost money, or return later — Day34 lease/fencing, Day40 at-least-once, Day55 recovery govern guarded/audited recovery); and the integrated invalid-Provider-output incident (a new adapter release yields invalid JSON that Day44 validation blocks) is handled by contain (stop the release claiming new Jobs, route to a known-good version) -> preserve (release/settings version but NEVER the Secret, provider/model, job/attempt/request/trace IDs, error category, secure references) -> roll back application code/config only (deploy healthy Worker first; DB history is NOT rolled back) -> classify by release/time/attempt/output (validation-before-completion does not prove the external call never ran) -> idempotent guarded AUDITED recovery reconciling Job/Attempt/Event/Artifact, never blindly requeuing/replaying paid calls, marking raw invalid JSON succeeded, deleting audit, fabricating an Artifact, or writing Secret/prompt/raw output to routine logs; Day45 carries REAL executed local runtime evidence (a minimal FastAPI composition/lifespan + 20 pytest cases with a FAKE no-network Provider, executed on Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3 -> 20 passed, deps pinned in api/requirements-day45.txt; completion target is an in-memory list, not PostgreSQL) while a real Provider SDK/network, PostgreSQL/SQLAlchemy transactions and durable completion, Celery/Redis Worker behavior, and deployment/Secret rotation/drain/production are NOT RUN, and SQLAlchemy mapping (Day46), async sessions/transactions (Day47), Outbox acceptance (Day50), a real Provider SDK (Day53), streaming/cancellation (Day54), Celery (Day55), and retries/backpressure (Day56) remain future boundaries

- Day46 — SQLAlchemy 2.0 mapping for the Day42 data model, a FAITHFUL executable representation of the existing PostgreSQL durable contract that does NOT change ownership, integrity, retention, public boundaries, or schema authority (ORM mapping REPRESENTS the database contract; it does not silently REPLACE it; PostgreSQL is durable authority; Day46 maps it, Day47 drives it transactionally, Day48 evolves it safely): a DeclarativeBase with MetaData(schema="app") pins the exact existing table identity and Mapped[T] = mapped_column(...) declares typed columns (UUID(as_uuid=True), Text, Integer, BigInteger, Boolean, TIMESTAMP(timezone=True), JSONB) where database-GENERATED values are SERVER-side defaults (gen_random_uuid()/now()/'queued'/0/false/'{}'::jsonb), and the mapping preserves the named constraints exactly — jobs_tenant_idempotency_unique UNIQUE(tenant_id, idempotency_key) (one client request per tenant = one Job; Day50 acceptance workflow deferred), jobs_tenant_id_unique candidate key, jobs_status_allowed CHECK (job_status stays TEXT + CHECK, NOT a native enum, which would be Day48 schema evolution), jobs_attempt_count_non_negative, and jobs_succeeded_has_finished_at CHECK (a nullable Mapped[datetime | None] finished_at ALLOWS NULL but does NOT enforce the conditional rule — the CHECK does, and a negative constraint test expects a REJECTED write / IntegrityError, not an empty result); JobAttempt retry ordinal is JOB-scoped via UNIQUE(job_id, attempt_number) (not tenant-scoped, not global — Job B may reuse Attempt 1) with a second candidate key UNIQUE(job_id, attempt_id), and JobEvent proves same-Job provenance with a COMPOSITE FK (job_id, attempt_id) -> job_attempts(job_id, attempt_id) where a NULL attempt_id (MATCH SIMPLE) records a Job-level event and a single Attempt FK would wrongly permit a valid Job plus an unrelated valid Attempt; ON DELETE RESTRICT is preserved on EVERY FK and NO cascade/delete-orphan is introduced (Attempts/Events/Outbox/Artifacts carry audit/recovery value; relationship() is NAVIGATION only, not durable integrity); Pydantic public models and the ORM persistence models remain SEPARATE (never merged/inherited, no tenant/audit/persistence leak) and neither Pydantic nor the ORM classes PROVE PostgreSQL constraint behavior; OutboxEvent is PostgreSQL-owned dispatch INTENT whose published_at IS NULL means the checkpoint is not recorded (NOT proof it was never sent — a crash between publish and checkpoint permits at-least-once redelivery), ResultArtifact stores attempt_id ONLY (job ownership DERIVED through the Attempt, no denormalized job_id without a measured need + a constraint), and UploadSession/ResultArtifact store Object Storage REFERENCES/metadata, never large bytes/signed URLs/credentials; Day46 creates NO global Engine/AsyncSession (mapping metadata needs no production connection; Day47 owns one Engine per process and one AsyncSession per request/Job unit of work), keeps tenant_id an explicit mapped column/FK via a minimal Tenant support stub (no full aggregate/relationship, tenant_id must not disappear as a derived field), and states Document/job_documents as an explicit unimplemented mapping limitation (not a half-built relationship); the wrong-schema failure/reconciliation drill (a release that omitted the app schema wrote three accepted Jobs to public.jobs) rolls back the bad mapping/release to protect FUTURE writes (code rollback != durable-data rollback), preserves and classifies correlation evidence — most importantly WHETHER the client was already responded to — and reconciles the mis-placed rows through an audited, idempotent process, never blindly ignoring/copying/deleting; Day46 carries REAL executed STATIC metadata-contract evidence (20 pytest cases asserting the declared mapping structure against Base.metadata — app-schema identity, typed columns, server defaults, named UNIQUE/CHECK/FK, ON DELETE RESTRICT on every FK, the composite provenance FK, TEXT+CHECK not enum, no cascade delete, ORM/Pydantic separation, the Tenant stub, and the documents/job_documents limitation; executed on Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3 -> 20 passed, deps pinned in api/requirements-day46.txt; NO database connection and NO create_all() were used) while PostgreSQL runtime behavior is NOT RUN (no server available; create_all() success would NOT be schema-compatibility evidence; a real test would apply the independent Day42 raw SQL 001+003 then assert rejected writes), and AsyncSession/transactions/repository/UoW (Day47), Alembic migrations (Day48), Outbox acceptance (Day50), a real Provider SDK (Day53), Celery (Day55), and integration/production remain future boundaries

- Day47 — Async sessions, transactions, repository and unit of work, driving the faithful Day46 mapping through SHORT, isolated async database units of work WITHOUT treating a long external AI-Provider call as transactional database work (PostgreSQL is durable authority; Day46 maps it, Day47 drives it transactionally, Day48 evolves it): the AsyncEngine and async_sessionmaker are PROCESS-scoped (one Engine per process via a lifespan / Worker startup composition root, NOT one per deployment; API and Worker are separate processes each owning their own Engine + connection pool) while the AsyncSession is request/Job-scoped and NEVER global/shared (it carries identity-map + pending-change + transaction context, so concurrent Jobs would pollute each other), so each request or Worker Job gets a FRESH Unit of Work = one isolated AsyncSession + repositories, and the same FACTORY is shared, not the same Session; repositories receive the UoW-injected Session and EXPRESS DB operations but NEVER create Engines/Sessions and NEVER commit or close, while the UnitOfWork owns the one Session, exposes repositories, does EXPLICIT await uow.commit() (chosen over silent auto-commit so a normal branch like a failed/stale claim cannot accidentally commit), rolls back on any exception or uncommitted exit, and ALWAYS closes the Session (close ends the Session and returns its connection to the pool; it is not a rollback and does not dispose the process Engine); the atomic start flow is one short UoW performing a guarded `UPDATE app.jobs SET job_status='running' WHERE job_id=:id AND job_status='queued' RETURNING job_id` (a SINGLE statement, not SELECT-then-UPDATE which races) where one returned row means this Worker claimed the Job and ZERO returned rows is a NORMAL stale/no-op (another Worker already changed the state — create NO Attempt/Event and do not treat it as a retryable DB failure), then creates Attempt 1 with an APPLICATION-generated correlation/idempotency key, `await session.flush()` to obtain the server-generated attempt_id for the dependent job_started Event WITHOUT committing (flush executes SQL in the CURRENT transaction but is not durable and not cross-session visible; commit is), and commits only if all three succeed; an IntegrityError during flush means PostgreSQL correctly REJECTED an illegal write and ABORTED the current transaction (integrity protected, not broken) and requires a rollback before the Session can work normally again, and a commit exception is an UNKNOWN commit outcome (the DB may have committed before the response was lost) so the UoW rolls back/closes local state and recovery reloads durable truth by a stable identifier via a NEW Session (the original Session may still hold stale identity-map objects) rather than blindly replaying the write; the long/paid Provider call runs OUTSIDE any open DB transaction (holding one exhausts connections and cannot make the Provider's execution/charges/network results/side effects roll back with PostgreSQL), the correlation/idempotency key is committed BEFORE the call (a Provider-returned request ID is persisted later as additional evidence but is too late to be the only recovery identity), and completion is a SECOND short guarded UoW that writes the verified Artifact reference + terminal Job state + completion Event together where a zero-row guarded completion is again a NORMAL stale/no-op (do not overwrite/duplicate facts) — guarded completion is CONCURRENCY control (exactly one still-valid running Attempt/Job records terminal facts) and is DISTINCT from the Day46 jobs_succeeded_has_finished_at CHECK, which is a STATE invariant; a definitive non-retryable Provider failure (e.g. 401 / rejected request) becomes failed while a timeout with UNKNOWN remote execution stays a first-class unknown/recovery state that is NEVER blindly requeued or re-called (cost + duplicate side effects, since the first call may already have executed and charged); reads never return a detached ORM object for lazy serialization after UoW close (an unloaded lazy relation needs DB I/O and a detached object raises DetachedInstanceError, or MissingGreenlet in an invalid async context) — instead an allowlisted Day44 Pydantic DTO is built INSIDE the UoW; and the integrated failure/rollback drill (UoW 1 committed running + Attempt-with-correlation-key + job_started; the Provider produced an external Artifact; UoW 2 crashed before the job_succeeded Event and commit) shows PostgreSQL retains ONLY UoW 1 facts (the external Artifact may exist but its DB reference, the succeeded state, and the completion Event do not — code rollback != durable-data rollback != external-side-effect rollback), and restart recovery uses a NEW UoW to inspect Job/Attempt/Event truth, verify Provider/Artifact evidence via correlation/idempotency, then run a NEW guarded completion transaction or preserve unknown state rather than fabricating success or blindly re-calling; Day47 carries REAL executed FAKE-SESSION control-flow evidence (23 pytest cases with a FAKE AsyncSession asserting explicit commit, rollback+close on exception/uncommitted exit, zero-row stale/no-op, flush-before-write, repos never commit, one shared Session per UoW, and a fresh Session per UoW; executed on Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 -> 29 passed, deps pinned in api/requirements-day47.txt) while a mock is NOT database proof: PostgreSQL runtime rollback/transaction behavior is NOT RUN (no server/driver; a real test would apply the independent Day42 raw SQL, force a failure, then prove via a NEW Session that the Job stays queued with no Attempt/Event, and SQLite is NOT PostgreSQL evidence for this app-schema/PostgreSQL-typed contract), and Alembic (Day48), the upload workflow (Day49), idempotent acceptance/Outbox (Day50), a real Provider SDK (Day53), Celery (Day55), and FastAPI/Worker integration/production remain future boundaries

- Day48 — Alembic and safe AI backend schema evolution, making Day36's Expand -> Backfill -> Validate -> Switch -> Contract discipline EXECUTABLE with Alembic over the Day46 mapping and Day47 boundary for a Lease-ownership evolution of app.jobs (a migration is a versioned transition across SCHEMA + HISTORICAL ROWS + EVERY deployed writer, so `alembic upgrade head` success is DDL-on-one-database evidence ONLY, not history/old-Worker/Provider safety; Alembic is a DEPLOYMENT CONTROL PLANE, distinct from FastAPI startup and a Day47 request/Job UoW, and the app must never self-run migrations): the revision chain is SPLIT and linear (0001_baseline -> 0002_expand_lease -> 0003_add_lease_constraints -> 0004_validate_lease -> 0005_contract_legacy, with a FORWARD additive branch 0006_add_reconciliation_polling off 0003 merged back by 0007_merge_reconciliation_polling (single head 0007; every published revision keeps its original parentage — no history rewrite)): a PURE EXPAND (0002) adds nullable lease_owner/lease_token/lease_expires_at with NO fabricated default and NO constraint on app.jobs AND additively creates the INDEPENDENT app.job_lease_reconciliation queue table (triage lives here, never as a marker column on app.jobs) — the OLD/NEW COMPATIBILITY WINDOW where old Writers can still write a running-without-Lease row — then a SEPARATE CONSTRAINT revision (0003) adds jobs_lease_triple_coherent + the Day36 core jobs_running_requires_lease (job_status <> 'running' OR complete Lease), all NOT VALID, ONLY AFTER old Writers are DRAINED/ISOLATED because NOT VALID skips the legacy SCAN but ENFORCES every future INSERT/UPDATE by ANY Writer version (an old Worker writing a running-without-Lease Job is REJECTED — NOT VALID is not 'old Workers unaffected'), with NO Backfill loop / NO Provider call / NO long transaction in any upgrade(); BACKFILL is a SEPARATE operational, restartable step (short tx + FOR UPDATE SKIP LOCKED batches, idempotent predicates, the database state as checkpoint) that fills ONLY running Jobs with Lease NULL AND trusted ownership evidence and sends unknown-running Jobs to reconciliation (never fabricated), classifying queued/terminal = no Lease, trusted-running = backfill, unknown-running = route to the independent reconciliation queue, with Lease EXPIRY correctly identified as a runtime protocol (not a migration-batch claim) and UPDATE...RETURNING as the Day47 guard (not the compatibility mechanism); VALIDATE CONSTRAINT is a SEPARATE revision that proves HISTORY and FAILS until every legacy violation is truly resolved (an exception queue is NOT resolution); SWITCH means EVERY Writer (Workers, recovery, admin/scripts, completion/failure paths) uses the Lease-token protocol and the OLD path can no longer write (not merely a new binary — the student correctly noted it still needs the old-Worker restriction); CONTRACT is destructive and LAST, only after Validate + Switch + evidence + an observation period, dropping the Day42 legacy result_object_key pointer, and once real Lease data or Provider side effects exist the recovery is FORWARD-FIX + reconciliation, NOT a destructive downgrade (a downgrade is not a time machine — dropped bytes/history do not return and a re-run double-executes a paid Provider call); the Alembic specifics are handled (revision/down_revision define the graph + required predecessor with downgrade as the reverse traversal; parallel revisions -> multiple heads -> an Alembic MERGE revision; autogenerate emits a CANDIDATE diff to review for DDL/data/locks/multi-version, with Day46 Base.metadata as INPUT and PostgreSQL as authority; baseline/stamp writes alembic_version and does NO DDL, safe only after a PROVEN exact match, with a new empty DB applying the Day42 raw SQL then stamping then upgrading while an existing matching DB is stamped to baseline then upgrades later revisions; alembic_version is a version DECLARATION, not a schema PROOF; a minimal env.py carries only DB config + Base.metadata + execution and never builds the FastAPI app or shares a business Session; CREATE INDEX CONCURRENTLY is NON-transactional and must not sit in a migration transaction, and a failed concurrent build leaves an invalid index to inspect/repair); the integrated failure drill (Expand deployed, real tokens exist, a faulty token guard, an old Worker may still write, unknown Provider outcomes) stops old claims + faulty paths, prevents bypass Writers, preserves Lease data, drains/isolates old Workers, loads Job/Attempt/Event/correlation evidence in a NEW UoW, verifies Provider/Artifact, runs a new guarded completion only when confirmed else preserves unknown/recovery state, forward-fixes, then Backfills/reconciles, Validates, observes, and Contracts — with Outbox intent explicitly NOT Provider-success proof (dispatch intent only; external results need correlation + Provider/Artifact verification); Day48 carries REAL executed STATIC/OFFLINE evidence (44 pytest cases inspecting the Alembic revision graph + migration source via ScriptDirectory — single head 0005, single head 0007 via branch(0006 off 0003)+merge(0007), published spine 0005->0004->0003->0002->0001 unchanged, Expand nullable/no-default/NOT VALID, Validate separate, Contract destructive+gated, no loop in any upgrade()/downgrade(), minimal env.py — plus fake-session backfill control flow that selects FOR UPDATE SKIP LOCKED, fills known (Lease triple on app.jobs) and routes unknown into the app.job_lease_reconciliation queue (INSERT ON CONFLICT DO NOTHING, no app.jobs write), is idempotent, and calls no Provider; executed on Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3 -> 44 passed, deps pinned in api/requirements-day48.txt) plus an offline `alembic upgrade 0001_baseline:head --sql` that RENDERED the Expand/Validate/Contract DDL with NO database connection, while PostgreSQL runtime is NOT RUN (no server; a real NOT VALID/VALIDATE/backfill test would apply the Day42 raw SQL, create a legacy violating row, prove the old row survives, prove a new illegal write is rejected, and prove VALIDATE fails until repaired; SQLite/fake-session/`alembic upgrade`-success are NOT PostgreSQL proof) and the Day49 upload workflow, Day50 Outbox/Celery delivery, Day53 Provider SDK, Day55 worker runtime, FastAPI/Worker integration, and production migration remain future boundaries

---

## Core Abilities Mastered

- Explain LEGB name lookup.
- Explain lexical scope vs dynamic scope.
- Explain why Python searches names based on where a function is defined.
- Explain why `UnboundLocalError` happens with local rebinding.
- Explain when `global` works and why global request state is dangerous.
- Explain `nonlocal` and nearest enclosing scope.
- Explain mutation vs rebinding in scope problems.
- Define closure as function object plus captured environment.
- Explain late binding and the `i=i` default argument fix.
- Connect scope risks to FastAPI, Playwright, and AI backend systems.
- Explain why a closure can access local variables after the outer function returns.
- Explain captured environment and state preservation.
- Explain why `x = x + 1` raises `UnboundLocalError`, not `NameError`.
- Explain how `nonlocal` enables intentional rebinding in the nearest enclosing scope.
- Explain factory function design and how it separates configuration from business logic.
- Compare closure vs class for backend design.
- Build FastAPI dependency factories, Playwright configuration factories, and AI prompt builders.
- Explain production risks caused by captured mutable state.
- Explain why decorators exist for cross-cutting concerns.
- Explain `@decorator` as `func = decorator(func)`.
- Explain why the wrapper function is the callable that actually runs.
- Build universal decorators with `*args` and `**kwargs`.
- Explain why `functools.wraps` preserves metadata.
- Explain how decorators support logging, timing, retry, authentication, cache, and AI tracing.
- Review decorator production risks such as lost return values, broken metadata, and unsafe logging.
- Explain iterable vs iterator.
- Explain `iter()`, `next()`, and `StopIteration`.
- Explain why `StopIteration` is not replaced by `None`.
- Explain generator lifecycle and one-time consumption.
- Explain why `yield` creates pausable and resumable data flow.
- Compare list comprehension and generator expression.
- Explain `yield from`.
- Connect generators to FastAPI `StreamingResponse`, Playwright pipelines, and AI token streaming.
- Explain `try / except` control flow.
- Catch specific exceptions such as `ZeroDivisionError`.
- Explain why broad `except Exception` can hide bugs.
- Explain exception propagation through the call stack.
- Use `raise` for invalid business rules.
- Design custom exceptions such as `InvalidPromptError`.
- Preserve root cause with `raise ... from ...`.
- Connect exceptions to FastAPI `HTTPException`, Playwright recovery, and AI backend error design.
- Explain import as module execution, not source-code copying.
- Explain module objects and module namespaces.
- Explain how `sys.modules` caches imported modules.
- Explain why modules usually execute only once.
- Explain module vs package.
- Explain `__init__.py` and namespace packages.
- Compare `import module`, `from module import name`, and wildcard imports.
- Explain namespace pollution and why `from module import *` is risky.
- Prefer absolute imports for large backend systems.
- Identify import side effects and their production risks.
- Connect package boundaries to FastAPI, Playwright, and AI backend architecture.
- Explain Type Hints as interface contracts.
- Explain why Type Hints are not runtime checks by default.
- Add parameter and return type hints to backend functions.
- Use `list[T]`, `dict[K, V]`, `tuple`, `set[T]`, `User | None`, `Optional`, and `Union`.
- Explain type inference and when local annotations are unnecessary.
- Explain why empty collections often need explicit types.
- Use `TypeVar` to preserve input-output type relationships.
- Explain why `T -> T` is better than `object -> object`.
- Use `Generic` for reusable wrappers such as `Response[T]`.
- Connect Type Hints to FastAPI request models, response models, `Depends()`, Pydantic, and OpenAPI.
- Connect Type Hints to Playwright `Browser`, `BrowserContext`, `Page`, `Locator`, and storage state.
- Connect Type Hints to AI backend `ChatMessage`, `AgentTask`, `AgentResult`, `ToolResult`, and tool calling.
- Explain OOP as responsibility design, not class decoration.
- Explain object, class, instance, state, and behavior.
- Explain `self` as the current instance object.
- Explain `u1.say_hi()` as `User.say_hi(u1)`.
- Explain class attributes, instance attributes, and shadowing.
- Explain attribute lookup and method lookup.
- Explain inheritance as Is-A.
- Explain method override and why lookup stops after the first match.
- Explain why parent `__init__()` does not run automatically.
- Use `super().__init__()` to initialize parent state.
- Explain basic MRO.
- Explain composition as Has-A.
- Explain why modern backend systems often prefer composition over inheritance.
- Connect OOP to FastAPI application, request, response, dependency, and service objects.
- Connect OOP to Playwright `Browser`, `BrowserContext`, `Page`, and `Locator`.
- Connect OOP to AI backend `ChatService`, `LLMClient`, `PromptBuilder`, `VectorStore`, `UserRepository`, and `RedisCache`.
- Explain a context manager as deterministic resource cleanup, not just `with` syntax.
- Explain the resource lifecycle: Acquire, Use, Release.
- Explain why Release is the step most often skipped on failure.
- Use `try / finally` to guarantee cleanup manually.
- Explain what `with` guarantees over plain assignment.
- Implement `__enter__` and `__exit__` for a custom context manager.
- Explain the three `__exit__` arguments and the meaning of returning `True` vs `False`.
- Write `@contextmanager` generators and explain `yield` vs `return`.
- Explain why `yield` must sit inside `try / finally`.
- Explain why business logic should not own resource management.
- Build FastAPI `yield` dependencies and `asynccontextmanager` lifespan handlers.
- Close Playwright `BrowserContext` per job to avoid leaks.
- Wrap LLM streams, Redis connections, sessions, and locks to prevent AI backend leaks.
- Identify database, file, browser, Redis, stream, and lock leaks.
- Explain that async improves I/O throughput, not CPU speed.
- Explain I/O bound vs CPU bound work.
- Explain blocking vs non-blocking from the Event Loop's perspective.
- Explain the Event Loop as a single-threaded cooperative scheduler.
- Explain coroutine, coroutine object, and why calling a coroutine does not run it.
- Explain the difference between a coroutine and a Task.
- Explain what `await` does to the coroutine and the Event Loop.
- Explain why `asyncio.gather()` returns input order, not completion order.
- Explain the Task lifecycle and cooperative cancellation with `CancelledError`.
- Explain exception propagation and "Task exception was never retrieved".
- Explain why a `Semaphore` protects downstream capacity for stable throughput.
- Use `asyncio.to_thread()` for unavoidable blocking work.
- Connect async to FastAPI request Tasks, Playwright automation, and AI backend concurrency.
- Design a layered AI backend: API, Service, Browser, LLM, Repository, Database.
- Explain the single responsibility of each layer and what it must NOT do.
- Keep FastAPI routers thin and move logic into the Service layer.
- Use dependency injection to build stateless, testable services.
- Treat the Browser and LLM as infrastructure behind interfaces.
- Apply the Repository pattern to hide the database.
- Apply separation of concerns, single responsibility, low coupling, and high cohesion.
- Reason about worker architecture, async vs worker scaling, and horizontal scaling.
- Apply Semaphore, retry, and exponential backoff for downstream limits.
- Design a task-status pattern for long-running jobs.
- Answer backend architecture interview questions with engineering reasoning and trade-offs.
- Explain Git as a project history management system, not a backup tool.
- Explain why Git's core model is a snapshot, not a pure diff.
- Explain why a commit is an immutable snapshot object.
- Distinguish the Repository, Working Directory, and a commit.
- Explain the Staging Area as the blueprint of the next commit.
- Explain the three-tree model and describe commands as tree movement.
- Explain HEAD, branch, and detached HEAD as references.
- Explain `git reset --soft`, `--mixed`, and `--hard` using the three trees.
- Recover a mistaken reset with `git reflog`.
- Connect Git to FastAPI rollback, Playwright test history, and AI prompt versioning.
- Explain why branches exist from the engineering problem they solve.
- Explain that a branch is a movable reference, not a copy.
- Explain why branch creation is nearly instant.
- Explain HEAD and how only the current branch moves on commit.
- Explain fast-forward merge as reference movement.
- Explain three-way merge and why a merge commit has two parents.
- Explain why merge conflicts happen and why Git refuses to guess intent.
- Explain Git history as a Directed Acyclic Graph.
- Connect branching to FastAPI, Playwright, AI backend, agent, and Docker work.
- Explain why pushing directly to `main` is dangerous.
- Explain a Pull Request as Review + CI + Discussion + Audit Trail.
- Explain the split: machines validate rules, humans validate intent.
- Explain why Branch Protection protects `main`.
- Explain why a review goes stale after `main` changes.
- Explain why review discussions are preserved as engineering knowledge.
- Connect the GitHub workflow to FastAPI, Playwright, AI backend, prompt, and Docker work.
- Explain why Git history is designed for humans.
- Distinguish development history from product history.
- Explain merge commit, squash merge, and rebase merge, and when to use each.
- Explain what senior engineers review: architecture, performance, security, maintainability.
- Explain "review the code, not the coder."
- Explain the three goals of review: improve the code, the developer, and the team.
- Connect merge strategy and review to FastAPI, Playwright, AI backend, prompt, and Docker work.
- Explain why software teams manage work, not only code.
- Explain an Issue as a work item enabling collaboration, tracking, prioritization, and ownership.
- Explain a Label as structured metadata for retrieval, workflow, and automation.
- Explain a Milestone as a delivery goal made of many Issues.
- Explain GitHub Projects as workflow management, distinct from task management.
- Explain the hierarchy: Issue (Work), Label (Metadata), Milestone (Goal), Project (Workflow).
- Assemble the complete Idea-to-Release workflow tying Day15-Day19 together.
- Distinguish ownership from blame.
- Explain why CI establishes a trusted quality process.
- Explain a pipeline as ordered stages with fail-fast and fast feedback.
- Explain a quality gate as risk control protecting main, production, team, and users.
- Explain CD in terms of repeatability, consistency, reliability, and scalability.
- Explain Workflow as Code and Everything as Code.
- Assemble the full software delivery lifecycle tying Day15-Day20 together.
- Connect CI/CD to FastAPI, Playwright, AI backend, Docker, and prompt work.
- Explain why a repository defines its own workflow as code.
- Explain the GitHub Actions execution model from event to result.
- Compare GitHub-hosted and self-hosted runners and defend the trade-off.
- Design a multi-job workflow based on runner lifecycle, parallelism, and failure isolation.
- Implement a basic FastAPI CI workflow in YAML.
- Distinguish `on`, `runs-on`, `run`, `uses`, and `with` precisely.
- Connect GitHub Actions to FastAPI CI and AI backend GPU/evaluation workloads.
- Explain a matrix as one job template expanded by variables (not a resource optimization).
- Decide `fail-fast: true` vs `false` from the independent value of remaining combinations.
- Distinguish cache (re-creatable acceleration) from artifact (formal workflow output).
- Compare composite action (reusable steps) with reusable workflow (reusable jobs).
- Separate `needs`, `if`, and `continue-on-error` as distinct control mechanisms.
- Design a build-once/deploy-many pipeline with an immutable image digest.
- Explain production Environment protection and serialized deployment concurrency.
- Explain a container as an isolated process (namespaces + cgroups), not a small VM.
- Distinguish an image (immutable template) from a container (runtime instance).
- Explain image layers, the writable layer, and build-cache ordering.
- Write a Dockerfile and explain FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT.
- Distinguish `docker build` from `docker run`.
- Separate compute lifecycle from data lifecycle using volumes.
- Connect containers over an explicit network using service DNS names, not localhost.
- Apply immutable replacement instead of mutating a running production container.
- Explain why individually runnable containers do not make a reproducible system.
- Distinguish `depends_on`, a healthcheck, and application retry (started != ready).
- Distinguish Project, Service, Image, and Container, and decide rebuild vs recreate.
- Write a declarative Compose model with services, networks, volumes, and secrets.
- Use service DNS names and publish only the necessary host port.
- Design network segmentation for least access.
- Separate ordinary configuration, secrets, and governed business data.
- Split a portable base file from a development override.
- State where Compose fits in production and where a cluster is required.
- Explain the stable public entry (Domain -> DNS -> Nginx :443 -> backend) and keeping the backend port internal.
- Configure an Nginx reverse proxy and trusted proxy headers.
- Explain TLS as confidentiality + integrity + server authentication, and where it terminates.
- Redirect HTTP to HTTPS (308) and explain why it cannot protect an already-sent credential.
- Explain the certificate lifecycle and Nginx master/worker (reload vs restart).
- Promote one CI-verified immutable image digest instead of rebuilding per environment.
- Perform an API blue-green switch with verify, observe, drain, and rollback.
- Apply Expand-Migrate-Contract to a PostgreSQL schema change and roll out a worker compatibly.
- Serialize deployment with a concurrency lock and a least-privilege short-lived identity.
- Configure AI streaming (buffering off, correct timeouts) and reason about DNS TTL propagation.
- Distinguish a one-time command from a declared desired state that is continuously reconciled.
- Explain a Pod as the smallest deployable unit of one or more tightly coupled containers, and when not to co-locate.
- Explain a Deployment as a Pod template plus a replica count with controller replacement, not scheduling.
- Explain a Service as stable label-based discovery for a changing set of Pods.
- Separate non-sensitive runtime config (ConfigMap) from the immutable image and preserve the verified digest.
- Classify sensitive values into a Secret and explain why Base64 is encoding, not encryption.
- Explain why a ConfigMap/Secret change does not mutate an already-running process environment.
- Diagnose a partial AI outage where /health returns 200 but one Pod uses an invalid rotated key.
- Order a safe rollback that preserves healthy Pods and replaces only the faulty Pod.
- Keep Deployment selector, Pod template labels, and Service selector consistent.
- Explain Ingress as L7 Host/Path/TLS routing to Services and the resource-vs-controller split.
- Explain that HPA updates desired replicas on a scale target rather than creating Pods directly.
- Choose a meaningful scaling metric (queue backlog for external-wait workloads, not CPU) and bound it by upstream capacity.
- Perform a Deployment Rolling Update with maxSurge/maxUnavailable and distinguish it from rollback and Blue-Green.
- Explain why deleting v2 Pods is not a rollback and restore a known-good desired revision instead.
- Explain StatefulSet stable identity, per-Pod PVCs, headless Service, and ordered lifecycle — and why it is not database replication/HA.
- Separate Helm templates from environment Values across all objects and name the validation ladder.
- Explain why real Secrets must never live in Helm Values and where release history can leak them.
- Separate the FastAPI request lifecycle from a long-running Celery job lifecycle and return 202 + job_id.
- Assign every job state/byte to PostgreSQL (truth), Redis (deliver/cache), Object Storage (bytes), or memory (transient).
- Explain the database-to-queue crash gap and derive the Transactional Outbox with at-least-once + idempotent processing.
- Design durable checkpoints, atomic claim/lease, and a stable idempotency key enforced by a unique constraint/upsert, ACKing after durable write.
- Design presigned direct multipart upload with an Upload Session and server-side verification.
- Design a bounded, classified provider retry policy with backoff, jitter, and a circuit breaker.
- Choose monitoring signals (queue depth vs oldest-age vs throughput) and stable observability correlation identity (job_id, not job_status).
- Order a failure-containment/rollback/data-repair runbook and explain why compute rollback does not repair persisted data.
- Explain at-least-once delivery, why exactly-once across independent systems is not promised, and how object keys are not authorization.
- Explain why the Job row must be committed before FastAPI returns 202.
- Distinguish PostgreSQL server/cluster/database/schema/table/row/column and what a psql session connects to.
- Distinguish a PostgreSQL Schema (namespace) from a table schema (definition/contract).
- Choose Job model types/defaults and defend UUID vs integer identity with real trade-offs.
- Explain why core facts use typed columns while JSONB stays bounded auxiliary metadata.
- Interpret NULL per field lifecycle and state what NOT NULL does not enforce.
- Distinguish a primary key (row identity) from an idempotency key (request identity).
- Explain timestamptz as one absolute instant rendered in the session time zone.
- Classify conceptual / syntax / runtime / integration / production validation evidence.
- Repair durable-but-wrong rows with a guarded UPDATE and explain why code rollback cannot.
- Write a deterministic SELECT with explicit columns, a filter, a unique tie-breaker, and LIMIT.
- Explain SQL three-valued logic and why WHERE discards both FALSE and UNKNOWN.
- Use IS NULL correctly and include no-error rows explicitly instead of losing them to `<>`.
- Insert with database defaults and return generated facts with RETURNING.
- Explain what parameterized SQL prevents and the three things it does not solve.
- Write guarded state transitions with identity plus current-state predicates.
- Interpret zero returned rows honestly without claiming the row does not exist.
- Correct AND/OR precedence in destructive statements and use RETURNING as evidence.
- Diagnose a lost update and fix it with a database-side increment or an expected-old-value guard.
- Order an incident response: contain, preserve evidence, identify, reconcile, repair, verify.
- Decide when a repeated fact must become its own entity rather than columns or a JSONB array.
- Distinguish primary key (row identity), foreign key (parent), and business key (operation identity).
- Design scoped uniqueness and explain why a global UNIQUE would be wrong.
- Choose a referential action as a lifecycle and evidence-retention decision.
- Place foreign keys correctly for one-to-many and express one-to-one with FK + UNIQUE.
- Model many-to-many with a junction table that carries relationship attributes.
- Enforce same-tenant relationships with tenant-aware composite foreign keys.
- Explain why foreign keys are write-time integrity and never authorization.
- Separate current state, append-oriented history, and durable publication intent.
- Deploy a UNIQUE constraint onto committed duplicates via containment, reconciliation, and guarded repair.

---

## Mini Exercises Completed

- LEGB output prediction exercises
- Lexical scope reasoning exercises
- `UnboundLocalError` explanation exercises
- `global` and `nonlocal` exercises
- Mutation vs rebinding exercises
- Closure counter exercise
- Late binding loop exercise
- FastAPI global request state scenario
- Playwright global page scenario
- AI prompt builder closure scenario
- Closure identification exercises
- Closure memory model exercises
- `nonlocal` output prediction exercises
- Factory function exercises
- `make_multiplier()` implementation
- Counter implementation with state preservation
- `UnboundLocalError` repair exercises
- Closure vs class refactoring exercise
- Late binding output prediction exercises
- Late binding fix with `i=i`
- FastAPI dependency factory exercise
- Playwright timeout factory exercise
- AI prompt builder factory exercise
- Closure engineering thinking exercises
- Decorator output prediction exercises
- Decorator execution order exercises
- Wrapper call flow exercises
- Universal decorator implementation
- Timer decorator exercise
- Logging decorator exercise
- `TypeError` analysis exercise
- `functools.wraps` metadata comparison
- FastAPI route decorator reasoning exercise
- Playwright retry decorator exercise
- AI token logger decorator exercise
- Day06 code review exercises
- Iterable vs iterator classification exercises
- `iter()` and `next()` output prediction exercises
- `StopIteration` reasoning exercises
- Generator lifecycle exercises
- Generator expression exercises
- One-time consumption exercises
- `yield from` exercises
- FastAPI `StreamingResponse` thinking exercise
- Playwright pipeline exercise
- AI token streaming exercise
- Pipeline vs batch exercise
- `try / except` output prediction exercises
- `ZeroDivisionError` precise catch exercise
- Exception propagation call stack exercise
- `raise` and `check_age(age)` exercise
- `InvalidPromptError` custom exception exercise
- Exception chaining exercise
- FastAPI `HTTPException` scenario
- Playwright timeout screenshot and cleanup scenario
- AI backend prompt validation and tool error scenario
- Module vs package classification exercises
- Import output prediction exercises
- `__init__.py` execution order exercise
- `sys.modules` cache reasoning exercise
- Namespace pollution review exercise
- Absolute vs relative import exercise
- Import side effect review exercise
- FastAPI package design exercise
- Playwright module boundary exercise
- AI backend package architecture exercise
- Basic Type Hint exercises
- Return type exercises
- `list[T]` and `dict[K, V]` exercises
- `User | None`, `Optional`, and `Union` exercises
- `TypeVar` identity exercise
- `Generic` response wrapper exercise
- FastAPI request and response model exercise
- FastAPI `Depends()` type contract exercise
- Playwright `Page`, `BrowserContext`, and `Locator` typing exercise
- AI backend `ChatMessage`, `AgentTask`, `AgentResult`, and `Response[T]` exercise
- Object model exercises
- Class vs instance exercises
- State vs behavior exercises
- `self` call transformation exercise
- Class attribute and instance attribute exercises
- Attribute lookup and shadowing exercises
- Inheritance and method override exercises
- `super().__init__()` exercise
- Composition refactoring exercise
- FastAPI service layer design exercise
- Playwright object ownership exercise
- AI backend `ChatService` composition exercise
- `with` file rewrite exercise
- `try / finally` cleanup exercise
- `__enter__` implementation exercise
- `__exit__` implementation exercise
- Exception cleanup output prediction exercise
- `@contextmanager` yield exercise
- FastAPI `yield` dependency exercise
- Blocking vs non-blocking exercise
- Coroutine object output prediction exercise
- Task concurrency exercise
- `await` suspension point exercise
- `gather()` input-order exercise
- Task cancellation cleanup exercise
- Task exception propagation exercise
- Semaphore concurrency limit exercise
- FastAPI async lifecycle exercise
- API layer refactor exercise
- Service layer design exercise
- Browser layer boundary exercise
- Dependency injection wiring exercise
- Repository pattern exercise
- Task status design exercise
- Retry strategy with backoff exercise
- Worker architecture exercise
- System design exercise
- Architecture mock interview exercise
- Python reference review exercise (Git connection)
- Git snapshot checkout experiment
- Staging area experiment
- Reset mode experiment
- Reflog recovery experiment
- Two-branches-one-commit experiment
- Fast-forward merge experiment
- Three-way merge experiment
- Merge conflict create-and-resolve experiment
- Open a pull request exercise
- Trigger CI exercise
- Request changes exercise
- Approve exercise
- Simulate stale review exercise
- Merge pull request exercise
- Merge commit vs squash merge comparison exercise
- Merge strategy selection exercise
- FastAPI endpoint review exercise
- Rewrite a poor review comment exercise
- Convert feature requests into Issues exercise
- Assign and justify Labels exercise
- Group Issues into a Milestone exercise
- Build a Project workflow board exercise
- Why "I tested locally" is insufficient exercise
- Design a CI pipeline exercise
- Explain a quality gate exercise
- Manual deployment vs CD exercise
- Explain workflow as code exercise
- Repository-defined workflow reasoning exercise
- Workflow vs runner exercise
- Hosted vs self-hosted runner design exercise
- Multi-job AI backend workflow design exercise
- Basic FastAPI CI workflow YAML exercise
- Matrix expansion exercise
- fail-fast decision exercise
- Cache vs artifact classification exercise
- Composite action vs reusable workflow exercise
- needs/if/continue-on-error classification exercise
- Deployment reliability review exercise
- Comprehensive advanced workflow design exercise
- Container vs VM exercise
- Image vs container exercise
- Layer/cache exercise
- Dockerfile exercise
- Build vs run exercise
- Volume exercise
- RAG architecture design exercise
- Image optimization exercise
- Minimal FastAPI Dockerfile authoring exercise
- Why-a-reproducible-system exercise
- Started-vs-ready diagnosis exercise
- Project/service/image/container counting exercise
- Rebuild-vs-recreate exercise
- Compose model authoring exercise
- Healthcheck + service_healthy exercise
- Config/secret/business-data classification exercise
- Compose-vs-cluster decision exercise
- Integrated Compose stack build exercise
- Correct-the-reverse-proxy exercise
- HTTP->HTTPS + token question exercise
- Trusted proxy headers exercise
- Promote-a-digest exercise
- Blue-green + drain exercise
- Expand-Migrate-Contract exercise
- Streaming timeouts exercise
- DNS migration exercise
- One-time-startup vs desired-state exercise
- Pod boundary (FastAPI + sidecar) exercise
- Three Pods vs one Deployment exercise
- New-IP failure diagnosis exercise
- Service with label selection exercise
- ConfigMap vs new image exercise
- Secret classification (Base64) exercise
- Health-200-but-401 partial outage diagnosis exercise
- Secret-rotation rollback ordering exercise
- Kubernetes English interview exercise
- Final Kubernetes mental model synthesis exercise
- Service vs Ingress layer exercise
- /chat vs /admin routing ownership exercise
- Initial CPU scaling metric exercise
- Low-CPU growing-backlog HPA diagnosis exercise
- Surge rollout (maxSurge/maxUnavailable) design exercise
- Stalled v2 Readiness prediction exercise
- Blue-Green vs Rolling Update comparison exercise
- Deployment+volume vs StatefulSet exercise
- Three-PVCs-not-three-copies exercise
- Helm templates vs Values separation exercise
- Secrets-not-in-Values exercise
- Helm validation-ladder exercise
- Helm failed-revision recovery exercise
- Kubernetes workloads English interview exercise
- Final Kubernetes workloads mental model synthesis exercise
- Request-vs-worker boundary exercise
- Job state ownership assignment exercise
- DB-first vs queue-first + Transactional Outbox derivation exercise
- Worker crash checkpoint/lease/idempotency recovery exercise
- 500 MB storage choice exercise
- Presigned direct upload + verification/cleanup exercise
- Upload Session vs Job lifecycle separation exercise
- Provider retry (429/503, 20-min outage) design exercise
- Queue depth vs oldest-age vs throughput interpretation exercise
- Cross-component correlation identity exercise
- Failure/rollback/data-repair runbook ordering exercise
- Production architecture English interview exercise
- Final AI Backend production architecture mental model synthesis exercise
- Minimum durable facts before 202 exercise
- PostgreSQL types/defaults selection exercise
- app.jobs not-found diagnosis (database/schema/search_path) exercise
- public vs app namespace exercise
- Typed columns vs JSONB-only comparison exercise
- Nullable lifecycle field interpretation exercise
- Row identity vs request/idempotency identity exercise
- psql session diagnostic checklist exercise
- Validation-level classification exercise
- DEFAULT VALUES + RETURNING default-proof exercise
- timestamptz UTC vs Asia/Shanghai comparison exercise
- queud guarded data repair exercise
- PostgreSQL restart persistence exercise
- PostgreSQL English interview exercise
- Final PostgreSQL durable-state mental model synthesis exercise
- Deterministic oldest-queued SELECT exercise
- Unfinished Jobs IS NULL exercise
- Why NULL rows vanish from `<> 'timeout'` exercise
- INSERT provider_metadata with defaults + RETURNING exercise
- Parameter binding / injection boundary exercise
- Guarded queued->running transition exercise
- Zero-row interpretation exercise
- Guarded DELETE with AND/OR precedence exercise
- attempt_count lost-update exercise
- Guarded running->succeeded exercise
- 842-row accidental UPDATE incident exercise
- SQL data manipulation English interview exercise
- Final SQL manipulation mental model synthesis exercise
- Entity vs columns vs JSONB decision exercise
- Duplicate child insert prediction exercise
- Scoped attempt-number uniqueness exercise
- Referential action defence exercise
- One-to-many FK placement exercise
- Tenant-scoped idempotency uniqueness exercise
- Status allowlist to CHECK exercise
- Succeeded cross-field invariant exercise
- Result Artifact normalization exercise
- attempt_id-only vs redundant job_id exercise
- State vs history vs outbox separation exercise
- Optional one-to-one Upload Session -> Document exercise
- Many-to-many job_documents exercise
- Cross-tenant prevention with composite FKs exercise
- Integrity vs authorization exercise
- Failed UNIQUE deployment incident exercise
- job_attempts DDL authoring exercise
- Constraint SQLSTATE assertion exercise
- Relational modeling English interview exercise
- Final relational modeling mental model synthesis exercise

---

## Last Completed Goal

- [x] Complete Lesson
- [x] Complete Coding Exercises
- [x] Complete Mini Exercises
- [x] Update Handbook
- [x] Update Cheat Sheet
- [x] Update Interview Notes
- [x] Commit
- [x] Push to GitHub

---

## Definition of Done

A training day is complete only if:

✓ Lesson finished

✓ Exercises completed

✓ Repository updated

✓ Git committed

✓ Git pushed

✓ Ready for next lesson

---

## Repository Status

Handbook:
🟢 Healthy

Projects:
🟢 Healthy

Interview Notes:
🟢 Healthy

Cheat Sheets:
🟢 Healthy
