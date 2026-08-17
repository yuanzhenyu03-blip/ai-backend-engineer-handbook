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

## Progress

Status: Day67 completed (lesson + this configuration record). Next: Day68 — Long-running AI Jobs:
Polling, Callback, Correlation and Idempotency.

## Future Milestones

- Day68: observable, retry-safe FastAPI to n8n boundary (polling/callback contracts, correlation IDs, idempotency).
- Day69: human approval, error workflows, retry control, secret handling, auditability.
- Capture a safe, credential-placeholder workflow JSON export when available.

## Related

- Lesson: [`docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md`](../../docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md)
- Previous backend: [`projects/fastapi-playwright/`](../fastapi-playwright/README.md) (Day66 permissioned worker)
