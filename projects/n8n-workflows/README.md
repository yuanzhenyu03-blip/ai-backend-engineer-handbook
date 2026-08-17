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
  -> Edit Fields (map report_scope, request_id)
  -> IF ({{ $json... }} both present?)
       true  -> HTTP Request (POST placeholder) -> Respond to Webhook (202 JSON)
       false -> Respond to Webhook (400 JSON)
```

- Allowed inputs: `report_scope`, `request_id`.
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
  Wait (bounded interval/backoff) -> GET same task_id -> authoritative-state Switch
    -> terminal result  OR  continue observation  OR  reconciliation (on observation deadline)

Callback branch (AT-LEAST-ONCE; never claim exactly-once):
  authenticate -> validate schema -> match task_id + correlation_id -> dedupe stable event_id
    -> task_version ordering (reject stale/conflicting) -> verify legal transition
    -> optional authoritative FastAPI confirmation -> ONE idempotent downstream action

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
event_id                              : stable callback event identity, for dedupe
task_version                          : monotonic ordering / conflict evidence
trace_id / poll-attempt identity      : one concrete execution attempt; may change
```

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

## Progress

Status: Day68 completed (classroom scope) — lesson + the Long-running Job Orchestration Contract above
(CONCEPTUAL_STATIC; no runtime; no exported JSON). Day67 completed earlier. Next: Day69 — Human Approval,
Retry, Secrets, Audit and Error Workflows.

## Future Milestones

- Day69: human approval, error workflows, retry control, secret handling, auditability (built on Day68's
  stable task_id/request_id/correlation_id/event_id/version contract).
- Day70: n8n + FastAPI + AI Tool integration capstone.
- Capture a safe, credential-placeholder workflow JSON export when available.

## Related

- Day68 lesson: [`docs/fastapi/day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md`](../../docs/fastapi/day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md)
- Day67 lesson: [`docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md`](../../docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md)
- Previous backend: [`projects/fastapi-playwright/`](../fastapi-playwright/README.md) (Day66 permissioned worker)
