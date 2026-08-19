# n8n Interview

## Purpose

Interview questions and model answers for workflow automation with n8n.

## Sections

- Workflow Design
- Triggers
- Nodes
- Webhooks
- Error Handling
- AI Automation
- Production Operations

---

## Phase 6 — n8n + FastAPI AI Workflow Integration (Day67–Day70)

Boundary (the through-line of Phase 6): n8n is **permissioned orchestration only** — triggers, mapping,
waiting, branching, authenticated HTTP calls, Error Workflow, version rollback; its execution history is
orchestration evidence, never authoritative business truth. **FastAPI** authenticates/authorizes and
enforces legal state transitions and idempotency; **PostgreSQL** owns durable Task/Approval/Publication
truth. Do not assign authentication to PostgreSQL, and never give n8n direct DB/queue/Worker access.

### Beginner

Q: When may an n8n workflow return `202 + task_id`?
A: Only after FastAPI durably commits the acceptance bundle. Receiving a webhook is not acceptance; if n8n
fails before the commit it returns a failure (e.g. 502/503) or lets the caller retry — it never invents a
`task_id`.

Q: Test URL vs Production URL?
A: A Test URL exists only while manually listening for a test event (a debug lifecycle); a Production URL
needs a published/activated workflow. Neither means durable backend acceptance.

### Intermediate

Q: An n8n execution times out while observing a long Task. Did the Task fail?
A: No. `n8n execution timeout != durable Task failure`. Poll the SAME `task_id` with bounded backoff and an
observation deadline; a new execution may resume observation but must not issue a new business command or
mutate state.

Q: The same completion Callback is delivered twice; then a callback reuses `event_id` with a different
fingerprint.
A: At-least-once delivery: same `event_id` + same fingerprint = idempotent no-op (one business event, many
receipts); same `event_id` + different fingerprint = integration/security conflict, no action. `correlation_id`
is an association key, not authentication.

### Senior

Q: A bad workflow release duplicated Approvals/Publications and leaked an `Authorization` header. What first?
A: Contain first — deactivate the workflow, stop Error-Workflow replay, activate the backend publication kill
switch, and immediately revoke/rotate the leaked credential (verify the old one is rejected). Then preserve
evidence, scope the affected set with stable IDs and a padded window, and classify: published-without-approval
→ preserve SUCCEEDED + policy-violation record + compensate; provably-unstarted → FastAPI durable
cancellation; Provider-dispatched unknown → PENDING_RECONCILIATION. Verify, add regression coverage, and
canary. Rollback stops future harm; it does not undo committed facts or external effects, and history is
never deleted.

### Evidence honesty (Day70 capstone)

The class ran a bounded real `n8n -> FastAPI -> PostgreSQL` **acceptance** slice (202 + idempotent redelivery
+ new-connection DB check + 400 on invalid input) → `INTEGRATION_RUNTIME` for the acceptance boundary only.
The pure decision-model tests are `EXECUTED_LOCAL_RUNTIME`. Polling, Callback, Approval, Publication, Error
Workflow, Worker/Provider/Browser Tool, and the rollback exercise stay **NOT RUN**. A green test suite or one
integration run is not cumulative integration and is not production.

See `interview/fastapi.md` (Day67–Day70) for the full Beginner/Intermediate/Senior answers and corrections;
this file keeps the n8n-focused summary without duplicating that material.
