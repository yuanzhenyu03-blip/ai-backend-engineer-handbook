# n8n Workflows

## Goal

Build production-minded n8n workflow examples that orchestrate a FastAPI-owned durable task system —
without moving authorization, durable acceptance, idempotency, recovery, or audit out of the backend.

## Ownership Boundary (Day67)

```text
n8n     = permissioned ORCHESTRATION only: triggers, mapping, branching, HTTP calls, version rollback.
          It has NO authority to create/mutate a durable Browser Task and NO direct DB/queue/worker access.
FastAPI = the trusted business + security boundary: authentication/authorization, durable Task acceptance,
          the idempotency record, and reconciliation/cancellation/compensation APIs.

n8n asks FastAPI over authenticated HTTP; FastAPI's transaction decides what durably happens.
Webhook receipt != durable acceptance  ·  Test URL != Production URL != backend acceptance
service identity != tenant/user identity != action authorization
```

## Day67 Artifact — draft workflow configuration record

Day67 configured a local n8n **draft** workflow (not published/activated): `Day67 - FastAPI Orchestration
Boundary`.

```text
Webhook (test path: day67/research-report)
  -> Edit Fields (map report_scope, request_id, document_id)
  -> IF ({{ $json... }} both present?)
       true  -> HTTP Request (POST placeholder) -> Respond to Webhook (202 JSON)
       false -> Respond to Webhook (400 JSON)
```

- Allowed inputs: `report_scope`, `request_id`, `document_id` (the IF node requires all three non-empty).
- FastAPI request body: `{ "document_ids": [document_id], "business_input": { "report_scope": ... } }` so
  `report_scope` enters the Day59 request fingerprint (a changed `report_scope` is a different fingerprint,
  i.e. 409, not a replay).
- Two independent auth boundaries: inbound caller -> n8n (Webhook `headerAuth`, a Credential Store reference,
  NOT RUN / NOT CONFIGURED at run time) and n8n -> FastAPI (HTTP `httpHeaderAuth`, a Credential Store
  reference).
- Invalid response body: `{ "error": "invalid_request", "message": "report_scope and request_id are required" }`.
- Intended success body: `{ "status": "accepted", "task_id": "..." }` (INTENDED — never executed).
- HTTP endpoint (unverified local **placeholder**): `http://host.docker.internal:8000/api/v1/browser-tasks`.
- HTTP authentication: intentionally `None` — no real credential, secret, or production endpoint was configured.

**No exported workflow JSON was captured into this repository**, so there is no importable/runnable file
yet. This README documents the actual configured flow and its verification limits only. If an exact export
is later supplied from local n8n, add it under this project's convention and document its credential
placeholders safely (never real secrets).

## Validation Matrix (evidence tiers)

```text
[CONCEPTUAL_STATIC]      The responsibility-boundary architecture and the drawn workflow design.
[STATIC CONFIG REVIEW]   The node-by-node n8n configuration inspected in the editor (a configured-looking
                         node is NOT runtime proof).
[EXECUTED_LOCAL_RUNTIME] ONE thing ran in class: a real local invalid-webhook test (missing request_id /
                         empty report_scope) returned HTTP 400 with the documented JSON; the IF false branch
                         + its Respond to Webhook node ran; the HTTP Request node did NOT run. An earlier
                         attempt first misrouted a malformed request and returned an empty 200 (an $json...
                         expression did not evaluate); fixed by using explicit {{ $json... }} expressions.
[NOT RUN / NOT CONFIGURED] A valid FastAPI success path; service authentication; durable Task creation;
                         PostgreSQL persistence; queue/Outbox dispatch; browser-worker execution; a published
                         Production URL; production readiness.
```

## Day68 Contract — Long-running Job Orchestration Contract (CONCEPTUAL_STATIC)

Day68 evolves the same project (no parallel structure, no exported JSON) with the observation/delivery
contract for long-running AI Tasks. n8n orchestrates and observes; FastAPI/PostgreSQL owns durable truth.

```text
Acceptance:
  stable business request_id + request fingerprint -> FastAPI durable commit -> 202 + task_id + correlation_id

Polling branch (observation of an EXISTING task; retrying a poll != retrying the job):
  Wait (bounded interval/backoff) -> GET /api/v1/browser-tasks/{task_id} (same task_id)
    -> Switch on the Day66 TaskState:
         ACCEPTED / RUNNING             -> backoff -> poll the same task_id
         CANCELLATION_REQUESTED         -> keep observing until terminal (or reconcile); no replacement
         SUCCEEDED                      -> consume verified artifact_ref
         FAILED / CANCELLED             -> terminal
         timeout/429/503/invalid        -> retain task_id; retry observation or reconcile (on deadline)
  (CONCEPTUAL CONTRACT: the status route + TaskState switch are design only -- ROUTE NOT IMPLEMENTED,
   RUNTIME NOT RUN. The Day66 `TaskState` is a pure decision-core enum, not a live HTTP status route; this
   contract uses ONLY the Browser Task state names, never a second generic queued/expired vocabulary.)

Callback branch (AT-LEAST-ONCE; no exactly-once delivery or exactly-once cross-system effect claim):
  authenticate -> validate schema -> match task_id + correlation_id
    -> compute/validate event fingerprint
    -> atomically enforce event_id + fingerprint:
         same event_id + same meaning      -> idempotent no-op
         same event_id + different meaning  -> integration/security CONFLICT (do not act; investigate)
    -> task_version ordering (reject stale/conflicting) -> verify legal transition
    -> authoritative FastAPI confirmation when required
    -> ONE idempotent downstream action at a boundary that durably enforces the idempotency key
       (duplicate-safe idempotent logical outcome; external targets enforce their own key or are reconciled)

Event fingerprint covers only safe, stable business meaning (NO Secrets, raw Provider payloads, or
sensitive data): event_type + task_id + correlation_id + task_version + artifact_ref / result identity.

Incident branch:
  deactivate/rollback workflow -> preserve evidence -> bound affected set
    -> classify Task/Attempt/Provider/Artifact evidence -> cancel/reconcile/compensate through FastAPI
    -> verify -> regression checks -> controlled rollout
```

Identity table:

```text
business request_id / idempotency key : one logical acceptance command; stable across lost-response retries
task_id                               : durable backend Task identity
correlation_id                        : stable business-chain association (NOT authentication/authorization)
event_id                              : stable callback event identity; deduped AND bound to an event fingerprint
task_version                          : monotonic ordering / conflict evidence -- MODELED / NOT IMPLEMENTED
trace_id / poll-attempt identity      : one concrete execution attempt; may change
```

`task_version` is **MODELED / NOT IMPLEMENTED**: it is not in the Day66 Task model or any published durable
schema, and neither FastAPI, PostgreSQL, nor the Callback currently provides it. A real run first needs an
API-response/callback contract field, a durable monotonic version (or authoritative event sequence), a
Day48-style forward-safe additive migration where applicable, atomic version increment/read semantics, and
legal-transition enforcement.

Evidence limits (Day68):

```text
[CONCEPTUAL_STATIC]  The state-machine/contract design; reviewed interactively in class.
[NOT RUN]            Day68 n8n workflow runtime; valid FastAPI acceptance/status integration; a real Polling
                     loop (Wait/Switch, 503/backoff, deadline); real Callback reachability/auth/duplicate/
                     ack-loss/replay/correlation-mismatch/out-of-order; real PostgreSQL idempotency/version/
                     terminal enforcement; real Worker/Provider duplicate-call prevention + cancellation/
                     reconciliation; production. No Day68 importable/exported n8n JSON was created or captured.
                     Day67's invalid-input local 400 is NOT reused as Day68 evidence.
```

## Day69 Contract — Risk-based Approval Gate & workflow hardening (CONCEPTUAL_STATIC)

Day69 evolves the same project (no parallel structure, no exported JSON) with risk-based human approval,
classified recovery, Secret boundaries, authoritative audit, and incident hardening on top of the Day68
contract. The Day67/Day68 boundary is unchanged: n8n orchestrates; FastAPI/PostgreSQL owns durable truth,
authorization, idempotency, recovery, and audit.

```text
Approval Gate (risk-based; NOT every AI output):
  Validation evidence -> policy(risk/irreversibility/impact/tenant) ->
    low-risk reversible  -> auto-authorize under durable tenant pre-authorization policy
    high-risk irreversible -> durable Approval Request -> tenant approver decides ->
                              FastAPI verifies identity/role/scope/policy/object/version/expiry -> persist

Approval binding (a v7 approval can NEVER authorize v8):
  approval_id + tenant_id + task_id + artifact_id/artifact_version + action + status +
  requested_by + required role/policy version + decided_by + decided_at + expires_at
  stable across the chain: task_id, correlation_id, tenant_id
  NEW for changed content/action: approval_id, event_id, publication operation_id, publication idempotency key

Approval lifecycle (independent of the n8n execution lifecycle):
  PENDING -> APPROVED | REJECTED | EXPIRED | CANCELLED
  n8n Wait timeout != state change; PENDING holds until the backend-owned expires_at; a late approve on an
  EXPIRED approval is rejected + audited.

Classified retry/recovery (timeout = OUTCOME_UNKNOWN, not failure; keep operation_id + idempotency key):
  status: SUCCEEDED=no republish | PROCESSING=observe | FAILED_TERMINAL=no blind retry |
          PENDING_RECONCILIATION=reconcile | NOT_FOUND=ambiguous, do NOT immediately reissue
  errors: 429/503 -> backoff+jitter+Retry-After | write timeout -> query/reconcile first |
          400/422 -> fix, no auto-retry | 401 -> stop + classify (rotate only if expiry/compromise/revocation/invalid; else fix config) | 403 -> stop + investigate |
          409 idempotency-meaning conflict -> stop + investigate |
          rejected/expired approval -> business terminal | unknown external outcome -> PENDING_RECONCILIATION
  NOT_FOUND is ambiguous (wrong identity/routing, retention window passed, expired idempotency record,
  store-vs-provider inconsistency, or still-unknown execution): verify task_id/correlation_id/tenant_id/
  operation_id + audit/DB/logs/provider evidence + routing/retention boundaries; reissue with the SAME
  idempotency key ONLY when the backend proves NEVER_ACCEPTED/NOT_STARTED AND the idempotency retention
  contract is still valid; otherwise PENDING_RECONCILIATION or coordinated human handling. same idempotency
  key != unconditional proof of safety (an expired record can still cause a duplicate publish / extra cost).
  401 is not automatically rotate: classify first — rotate/refresh only when expiration/compromise/
  revocation/invalid is established; fix configuration for audience/issuer/auth-scheme/missing-header/
  wrong-endpoint/clock-skew; then verify and perform a controlled retry.

Secrets: workflow artifact = credential reference; Credential Store/Secret Manager = real secret; runtime
  = controlled injection; logs/audit/export/evidence-pack = NEVER a Token/Authorization header/API key/
  cookie/private key/raw Provider payload/tenant-sensitive content. 401 -> stop + classify (rotate only when
  expiry/compromise/revocation/invalid is established; else fix config), revalidate, verify, then controlled
  retry on the same operation_id (in the Day69 scenario the credential expired, so rotation is the
  scenario-specific recovery — not the universal response to every 401).

Audit: approvals (current state) + append-only approval_events (business transition history) committed
  ATOMICALLY; callback receipts = delivery evidence; logs/traces = diagnosis; n8n history != authoritative
  audit. Append-only is NOT automatically tamper-proof (needs perms/retention/monitoring/backup).
  Delivery is AT-LEAST-ONCE (no exactly-once claim): same event_id + same fingerprint = duplicate-safe no-op
  (one business event, many receipts); same event_id + different fingerprint = integration/security conflict,
  no action.

Error Workflow: resume the SMALLEST safe operation boundary (workflow retry != business operation retry);
  completed Task/Approval/Publication are facts, not steps to redo.

Incident: contain -> revoke/rotate -> preserve evidence -> scope -> classify ->
  cancel/reconcile/compensate -> verify -> regression checks -> controlled rollout.
  Rollback stops future harm only; never delete/bulk-cancel/retro-approve/overwrite history/reuse a
  compromised credential/infer terminal state from n8n history.
```

Evidence limits (Day69):

```text
[CONCEPTUAL_STATIC]  Interactive scenario-driven design review; Approval/identity/retry/audit/error/incident
                     reasoning; conceptual state machines and recovery matrices; English interview review.
[NOT RUN]            Day69 n8n workflow runtime; valid authenticated FastAPI acceptance/approval/publication
                     integration; real Approval UI/Form/Slack/email callback; real approver auth/authz/tenant
                     checks; real PostgreSQL Approval schema/migration/constraints/transactions/audit-events/
                     Outbox; real retry/backoff/error workflow; real callback duplicate/ACK-loss/fingerprint
                     conflict; real credential-store integration/revoke/rotate/log-redaction/access-review;
                     real publication/notification target or external reconciliation; real Worker/Provider/
                     Browser-Tool execution; real rollback/kill-switch/canary rollout; production. No exported
                     Day69 n8n JSON. Day67's 400 and Day68's contract are NOT reused as Day69 evidence.
```

## Day70 — Phase 6 Integration Capstone (mixed evidence tiers)

Day70 integrates Day67–Day69 into one failure-aware cumulative path and runs the maximum feasible real
`n8n -> FastAPI -> PostgreSQL` acceptance slice. Artifacts in this directory:

- `DAY70_CAPSTONE.md` — cumulative path, responsibility boundary, evidence matrix, actual commands/results,
  rollback exercise, and final Mental Model.
- `day70_capstone.py` — a standalone deterministic decision model (acceptance recovery, event dedupe/
  conflict, exact Approval binding, Publication recovery, credential classification, incident Task
  classification, polling boundary).
- `test_day70_capstone.py` — 18 deterministic tests (the classroom's 14 pre-fix tests are superseded; the
  four added areas are the full Approval authorization binding, the workflow body contract, the three-field
  IF validation, the inbound-auth reference, and the Day59 report_scope fingerprint).
- `day70_minimal_acceptance_workflow.json` — Secret-free importable Workflow SOURCE (`Day70 - FastAPI
  Durable Acceptance Gate`: Webhook `day70/research-report` -> validate `report_scope`+`request_id`+
  `document_id` -> IF (all three present) -> POST FastAPI Day59 `/v1/jobs` with body
  `{document_ids:[document_id], business_input:{report_scope}}` and an `Idempotency-Key` -> Respond 202 |
  400). Two independent auth boundaries — inbound Webhook `headerAuth` (caller -> n8n) and outbound HTTP
  `httpHeaderAuth` (n8n -> FastAPI) — both Credential Store references by name only; the base URL is an env
  placeholder. It is the importable SOURCE, not a captured post-run export. The inbound Webhook
  authentication is a source reference only and was NOT RUN / NOT CONFIGURED at run time.

Cumulative path:

```text
Authenticated-service trigger (two independent auth boundaries; inbound caller -> n8n auth NOT RUN)
-> map/validate report_scope+request_id+document_id -> FastAPI durable acceptance -> honest 202 + stable Task id
-> observe the same durable Task -> permissioned execution boundary -> verified protected Artifact reference
-> durable exact-version Approval -> idempotent Publication -> correlated audit + terminal result
```

Evidence matrix:

```text
EXECUTED_LOCAL_RUNTIME  day70_capstone.py + workflow static contract via test_day70_capstone.py:
                          classroom Python 3.11.5 -> 14 passed (pre-fix suite, SUPERSEDED); first attempt
                          Python 3.9.6 -> pytest missing -> NOT RUN (skip, not failure); updating agent
                          Python 3.10.12 -> 18 passed (the FIXED suite); the affected Day59 fingerprint test
                          also re-run -> 12 passed; repo-standard Python 3.12 -> NOT RUN. Real n8n inspection
                          alone (n8n 2.25.6; /healthz 200) is EXECUTED_LOCAL_RUNTIME, not cumulative
                          integration.
INTEGRATION_RUNTIME     (in class; NOT re-run by the updating agent) bounded real authenticated
                          n8n -> FastAPI/Uvicorn -> PostgreSQL SERVICE-call ACCEPTANCE slice, for the PRE-FIX
                          workflow (top-level report_scope; no inbound Webhook auth):
                          POST /webhook/day70/research-report -> 202 + stable Task id; exact redelivery ->
                          same id + idempotency_replayed=true; new-connection DB: jobs=1, outbox=1,
                          document_links=1, fingerprint length 64, state queued; invalid input -> 400, zero
                          Jobs. Proves the acceptance boundary ONLY; it does NOT prove inbound caller -> n8n
                          auth and is NOT evidence for the FIXED workflow. The FIXED workflow's real
                          integration is NOT RERUN; the different-report_scope 409 path is proven only by the
                          Day59 fingerprint contract test, NOT by an integration run.
CONCEPTUAL_STATIC/NOT RUN budget reservation in the acceptance tx; FastAPI-persisted/returned correlation_id
                          + propagation; real Polling/Callback/Approval/Publication/Error-Workflow runtime;
                          real Worker/Outbox-Relay/broker/Browser-Tool/Provider execution; verified Artifact
                          generation; real credential revoke/rotation/exposure review (only controlled local
                          Credential Store injection ran); rollback/kill-switch/canary incident exercise;
                          production. No real/paid Provider call; no production credentials/customer data;
                          no captured n8n post-run export.
```

A green test suite or a single acceptance run is not cumulative integration and is not production. Day59–
Day69 evidence is a named prerequisite, not Day70 validation.

Run the decision model:

```bash
cd projects/n8n-workflows
python3 -m pytest -q test_day70_capstone.py
```

## Progress

Status: Day70 completed — Phase 6 integration capstone. Day67–Day69 completed earlier. Phase 6 is COMPLETE.
A bounded, authenticated real n8n -> FastAPI -> PostgreSQL SERVICE-call acceptance + idempotent redelivery
reached INTEGRATION_RUNTIME for the PRE-FIX workflow only (it did not prove inbound caller -> n8n auth and is
not evidence for the FIXED workflow, which is NOT RERUN); the decision model + workflow static contract are
EXECUTED_LOCAL_RUNTIME (18 passed); the rest of the cumulative path is CONCEPTUAL_STATIC / NOT RUN. Next: Day71 — LLM Application Engineering (Phase 7A; a PHASE TRANSITION built
on Day53–Day61, not an n8n dependency).

## Future Milestones

- Day71 begins Phase 7A (LLM Application Engineering) as a PHASE TRANSITION built on Day53–Day61 — not a
  technical dependency on Day69/Day70/n8n.
- Day70 NOT RUN backlog toward production: budget reservation; correlation_id persist/propagate; real
  Polling/Callback/Approval/Publication/Error-Workflow runtime; Worker/Outbox/Provider/Browser-Tool
  participation; verified Artifact; real credential rotation/exposure review; rollback/kill-switch/canary;
  Python 3.12; a captured n8n post-run export.

## Related

- Day70 lesson: [`docs/fastapi/day70-n8n-fastapi-ai-tool-integration-capstone-and-interview.md`](../../docs/fastapi/day70-n8n-fastapi-ai-tool-integration-capstone-and-interview.md)
- Day70 capstone: [`DAY70_CAPSTONE.md`](DAY70_CAPSTONE.md)
- Day69 lesson: [`docs/fastapi/day69-human-approval-retry-secrets-audit-and-error-workflows.md`](../../docs/fastapi/day69-human-approval-retry-secrets-audit-and-error-workflows.md)
- Day68 lesson: [`docs/fastapi/day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md`](../../docs/fastapi/day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md)
- Day67 lesson: [`docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md`](../../docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md)
- Previous backend: [`projects/fastapi-playwright/`](../fastapi-playwright/README.md) (Day66 permissioned worker)
