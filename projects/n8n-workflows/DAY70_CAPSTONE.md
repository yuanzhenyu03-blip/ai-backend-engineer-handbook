# Day70 — Phase 6 Integration Capstone

n8n + FastAPI + AI Tool integration capstone: one failure-aware cumulative path, the maximum feasible real
`n8n -> FastAPI -> PostgreSQL` acceptance slice, strict runtime-evidence boundaries, the Phase 6 rollback
exercise, and the phase interview. **n8n owns permissioned orchestration, not durable truth.**

## Cumulative path

```text
Authenticated-service trigger boundary (two independent auth boundaries: inbound caller -> n8n, and
   n8n -> FastAPI; inbound Webhook auth is a Credential Store reference, NOT RUN / NOT CONFIGURED at run time)
-> map and validate report_scope + request_id + document_id
-> FastAPI durable acceptance
-> honest 202 + stable Task identity
-> observe the same durable Task
-> permissioned execution boundary
-> verified protected Artifact reference
-> durable exact-version Approval
-> idempotent Publication
-> correlated audit and terminal result
```

## Responsibility boundary (unchanged from Day67–Day69)

```text
n8n     = permissioned ORCHESTRATION: triggers, mapping, waiting, branching, authenticated HTTP calls,
          Error Workflow, version deactivation/rollback, execution history as ORCHESTRATION evidence only.
FastAPI = authentication/authorization, tenant isolation, guarded legal transitions, idempotency,
          Approval/Publication decisions, cancellation/reconciliation/compensation.
PostgreSQL = durable business truth: Task/Approval/Publication state, request fingerprint, append-only audit.
```

`202` is honest only after the acceptance bundle commits. After `202`, observe the SAME Task identity; an
observation failure or a disappearing n8n execution never mutates or replaces the durable Task. Validation
is evidence, not permission; a high-risk action needs an authorized Approval for the exact Artifact version
and action. `correlation_id` is an association key — not authentication, authorization, idempotency, or Task
truth.

## Engineering artifacts (this directory)

- `day70_capstone.py` — a standalone, deterministic decision model for the six capstone areas (acceptance
  recovery, event dedupe/conflict, exact Approval binding, Publication recovery, credential classification,
  incident Task classification) + the polling/observation boundary.
- `test_day70_capstone.py` — 21 deterministic tests (the classroom's 14 pre-fix tests are superseded). The
  four added areas: complete Approval authorization binding (full expected-authorization context + one
  negative per mismatched field), the workflow request-body contract (`document_ids` + `business_input.report_scope`),
  the IF validation of `report_scope`/`request_id`/`document_id`, the inbound-Webhook-auth reference, and the
  Day59 fingerprint proof that a changed `report_scope` is a different fingerprint (409, not a replay).
- `day70_minimal_acceptance_workflow.json` — the **importable Workflow source** for
  `Day70 - FastAPI Durable Acceptance Gate` (Webhook `day70/research-report` -> validate
  `report_scope`+`request_id`+`document_id` -> IF (all three present) -> POST the FastAPI Day59 `/v1/jobs`
  acceptance route with body `{"document_ids":[document_id], "business_input":{"report_scope":...}}` and an
  `Idempotency-Key` -> Respond 202 | Respond 400). **Two independent auth boundaries**: the inbound Webhook
  (caller -> n8n) uses `headerAuth` and the outbound HTTP Request (n8n -> FastAPI) uses `httpHeaderAuth` —
  both are Credential Store **references by name only**, the base URL is an environment placeholder, and no
  token/URL/tenant value is stored. **This is the importable source, not a captured post-run export** — an
  attempted post-run n8n export could not be captured because desktop execution approval was unavailable.
  The inbound Webhook authentication (external caller -> n8n) is a source reference only; it was **NOT RUN /
  NOT CONFIGURED at run time** and the class run did not prove caller -> n8n authentication.
- `DAY70_CAPSTONE.md` — this file.

## Evidence matrix (canonical four tiers)

```text
CONCEPTUAL_STATIC
  - architecture reasoning (responsibility/failure boundaries, rollback plan, final Mental Model)
  - static configuration review (n8n node-by-node inspection; a configured-looking node is not runtime proof)

EXECUTED_LOCAL_RUNTIME
  - the pure Python decision model + the workflow static contract, driven by the deterministic tests.
    Classroom run (pre-fix):  /Users/.../anaconda3/bin/python3.11 -m pytest -q test_day70_capstone.py
                              -> Python 3.11.5 -> 14 passed in 0.01s  (SUPERSEDED: the 14-test pre-fix suite,
                              before the Approval-binding / request-body / IF / inbound-auth fixes)
    First classroom attempt:  python3 -m pytest ...  -> Python 3.9.6 -> "No module named pytest"
                              -> NOT RUN (a missing-dependency skip, not a test failure)
    Updating-agent re-run:    python3 -m pytest -q test_day70_capstone.py -> Python 3.10.12 -> 21 passed
                              (the FIXED 21-test suite; the affected Day59 fingerprint test also re-run
                              -> python3 -m pytest -q test_day59_acceptance_logic.py -> 12 passed)
    Repository-standard Python 3.12 execution: NOT RUN.
  - a real n8n inspection alone (n8n 2.25.6; GET /healthz -> 200 {"status":"ok"}; the Day67 workflow is a
    six-node inactive/unpublished draft targeting /api/v1/browser-tasks with auth none). Inspection alone is
    EXECUTED_LOCAL_RUNTIME, NOT cumulative integration.

INTEGRATION_RUNTIME  (performed in class against disposable local infra; NOT re-run by the updating agent)
  Backend acceptance gate:
    - disposable PostgreSQL 16 on an isolated host port; raw Day42 001 + 003 baseline;
      Alembic stamp 0001_baseline -> upgrade to 0008_day59_acceptance; a NEW connection verified the
      revision and the lease/fingerprint columns; seeded a local tenant + verified Upload Session + verified
      Document; real Uvicorn/FastAPI against PostgreSQL.
    - from the n8n container, /readyz -> 200 with revision 0008_day59_acceptance.
    - a bounded container HTTP client POST -> 202; an exact replay -> the same Job with
      idempotency_replayed=true.
    - new-connection PostgreSQL evidence: queued Job, 64-character fingerprint, one Outbox dispatch intent,
      one Document link.
  Real n8n Workflow acceptance gate (the PRE-FIX workflow: top-level `report_scope`+`document_ids`, and no
  inbound Webhook authentication — this is an authenticated n8n -> FastAPI SERVICE call, NOT proof of
  external caller -> n8n authentication):
    - imported a runtime-only local test identity into the n8n Credential Store (the n8n -> FastAPI service
      credential); the temporary plaintext import file was deleted immediately.
    - imported + published "Day70 - FastAPI Durable Acceptance Gate"; restarted n8n so the production Webhook
      was active. The inbound Webhook authentication (external caller -> n8n) was NOT configured and NOT
      exercised in this run.
    - POST /webhook/day70/research-report -> HTTP 202, a Task/Job id (a UUID; not committed here),
      idempotency_replayed=false.
    - exact Webhook redelivery -> HTTP 202, the SAME Task/Job id, idempotency_replayed=true.
    - a new DB connection: jobs=1, outbox=1, document_links=1, fingerprint length 64, state queued.
    - invalid input -> HTTP 400; a new DB query found zero Jobs for that request identity.
  This is bounded real, authenticated **n8n -> FastAPI/Uvicorn -> PostgreSQL SERVICE-call** INTEGRATION_RUNTIME
  evidence for the ACCEPTANCE slice of the PRE-FIX workflow only. It does NOT upgrade the rest of the
  capstone, it does NOT prove inbound caller -> n8n authentication, and it is NOT evidence for the FIXED
  workflow. The FIXED workflow (report_scope inside `business_input`, three-field IF validation, inbound
  `headerAuth` reference) has NOT been re-run: its real n8n -> FastAPI -> PostgreSQL integration is
  **NOT RERUN**, and the "different `report_scope` -> different fingerprint -> 409, not a replay" behaviour
  is proven only by the Day59 fingerprint contract test (CONCEPTUAL_STATIC), not by an integration run.

PRODUCTION
  - NOT RUN. No production, load, multi-replica, production secrets, or production traffic. No real or paid
    Provider call. No production credentials or customer data were used or committed.
```

## NOT RUN (remaining cumulative path)

Budget reservation in the acceptance transaction; FastAPI-persisted/returned `correlation_id` and its
end-to-end propagation; real n8n Wait/GET bounded Polling; Callback reachability/auth/duplicate/ACK-loss/
replay/ordering/fingerprint-conflict runtime; real Worker/Outbox-Relay/broker participation in this path;
permissioned Browser Tool/Playwright execution; verified Artifact generation/lookup; real Approval schema/
migration/UI/callback/tenant-role authorization + atomic Approval audit; real Publication target + operation
idempotency + external reconciliation; real Error Workflow smallest-boundary resume; real credential
revoke/rotation/recovery + exposure review (only controlled local Credential Store injection was run); real
rollback/deactivation/kill-switch/canary incident exercise; Python 3.12 execution; a captured n8n post-run
export; inbound Webhook authentication (external caller -> n8n) — configured as a Credential Store reference
in source only, **NOT RUN / NOT CONFIGURED at run time**; a real re-run of the FIXED workflow end-to-end
(**NOT RERUN**); a real integration run of the different-`report_scope` 409 path.

## Production failure / rollback exercise (CONCEPTUAL_STATIC — not run against the real environment)

Scenario: a bad n8n release duplicated Approvals and Publications; some Tasks published successfully; some
Provider outcomes were unknown; an `Authorization` header leaked into execution logs.

```text
contain
-> stop Error-Workflow replay + activate backend publication kill switch
-> immediately REVOKE/ROTATE the exposed Credential (not merely replace configuration); verify the old one
   is rejected; do not resume traffic yet
-> preserve restricted evidence
-> scope the affected set: padded time window + in-flight executions; join
     workflow/release/execution -> tenant/request/task/correlation -> Attempt/Provider-request ->
     Approval/event -> Artifact/version -> Publication operation/idempotency/external-receipt.
     The credential exposure window is separate: first-possible-exposure -> revocation.
-> classify each durable Task:
     published without Approval -> preserve SUCCEEDED + record policy violation + compensate
                                   (never rewrite as failure, never retro-approve)
     provably unstarted (no claim/dispatch/artifact) -> guarded FastAPI durable cancellation
                                   (0 rows affected -> facts moved -> stop + reclassify)
     Provider-dispatched, outcome unknown -> PENDING_RECONCILIATION (cancel may strand a charge; retry may
                                   double cost)
-> when n8n history says "Publication failed" but a strictly-matching external receipt proves success:
     record Publication SUCCEEDED + record the acknowledgement/orchestration failure separately
-> verify (bad workflow/replay stopped, kill switch effective, old credential rejected, every durable/
   external fact + cancel/reconcile/compensate result confirmed)
-> regression coverage (invalid input, acceptance redelivery, Callback duplicate/conflict, exact-version
   Approval, unknown Publication, error classification, Secret redaction, smallest-boundary recovery)
-> controlled rollout: synthetic -> test tenant -> canary tenant -> allowlist -> gradual expansion
-> stop on: any Approval bypass, duplicate Publication, event conflict, Provider-call amplification,
   authentication spike, reconciliation growth, identity mismatch, audit gap, or Secret exposure.
```

Rollback stops future harm; it does not undo committed facts or external effects.

## Final Mental Model

```text
n8n owns permissioned orchestration, not durable truth. FastAPI/PostgreSQL owns authentication/authorization,
tenant isolation, durable Task/Approval/Publication state, idempotency, legal transitions, recovery and
authoritative audit.
202 is honest only after the acceptance bundle commits; after 202 observe the same Task identity.
Browser/Worker output becomes usable through a verified protected Artifact; validation is evidence, not
permission; high-risk action needs an authorized Approval for the exact Artifact version and action.
Retry is classified recovery: preserve identity, query authoritative evidence, retry only when proven safe,
otherwise reconcile. Same event_id + same fingerprint = no-op; same event_id + different fingerprint =
conflict.
Rollback stops future harm; cancellation handles proven-safe work; reconciliation resolves unknown outcomes;
compensation addresses completed effects; audit preserves history.
Actual Day70 evidence is bounded: an authenticated real n8n -> FastAPI -> PostgreSQL SERVICE-call acceptance
and idempotent redelivery reached INTEGRATION_RUNTIME for the PRE-FIX workflow only. That run did not prove
inbound caller -> n8n authentication, and it is not evidence for the FIXED workflow (which is NOT RERUN). The
remaining components stay explicitly NOT RUN.
Day70 closes Phase 6. Day71 is a PHASE TRANSITION whose main technical foundations are Day53–Day61; n8n is
not an LLM Runtime prerequisite.
```

## Related

- Lesson: [`docs/fastapi/day70-n8n-fastapi-ai-tool-integration-capstone-and-interview.md`](../../docs/fastapi/day70-n8n-fastapi-ai-tool-integration-capstone-and-interview.md)
- Project README: [`README.md`](README.md)
- FastAPI Day59 acceptance backend: [`projects/ai-backend-data-layer/api/day59_runtime_app.py`](../ai-backend-data-layer/api/day59_runtime_app.py)
