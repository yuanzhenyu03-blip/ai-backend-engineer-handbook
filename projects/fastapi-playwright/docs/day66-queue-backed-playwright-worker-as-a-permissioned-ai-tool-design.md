# Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool (design / runbook)

Artifact for `docs/fastapi/day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool.md`. This is the
pure decision/orchestration core `src/day66_queue_backed_permissioned_worker.py` plus its tests — no real
Provider/LLM, PostgreSQL, Redis/Celery, Outbox Relay, Playwright, or Object Storage. It REUSES the Day63
final fence and the Day65 recovery/retry core instead of re-implementing security rules.

## Permissioned Queue-backed Browser Task Contract v1.0

```text
LLM tool-call proposal (UNTRUSTED request input)
  -> Backend authorization + request-fingerprint/idempotency validation
  -> atomic Browser Task + Permissioned Contract + Outbox commit (ONE transaction)
  -> 202 Accepted + task_id
  -> Relay emits a minimal versioned Queue Envelope (identity only, no secrets)
  -> Worker loads current durable state from PostgreSQL + credentials from a protected Session Store
  -> guarded claim (attempt_id + lease owner/token/expiry)  [exactly one winner]
  -> final fence / cancellation / current policy checks
  -> protected Session load + isolated Playwright execution
  -> Day65 reconciliation or bounded retry when needed
  -> guarded terminal commit + safe Tool Result / protected Artifact reference
  -> ACK after the durable result
```

## Rules enforced

- An LLM `browser.export_report` tool call is UNTRUSTED request input. `idempotency_key` identifies one
  intent ONLY bound to a request fingerprint (tenant + operation + exact Origin + report scope); same key +
  different fingerprint is rejected; same key + same fingerprint is an idempotent replay. User approval is
  necessary but NOT sufficient — backend policy is the enforceable authority.
- A tool call is a PROPOSAL (Provider response = step 3); validation is next; durable acceptance happens
  ONLY at the committed transaction (`becomes_durable_task_at(DURABLY_ACCEPTED)`).
- Browser Task + Permissioned Tool Contract + Outbox dispatch intent commit in ONE transaction or roll back
  together; only a full commit returns `202 + task_id`. Dispatch is emitted by an INDEPENDENT Outbox Relay
  AFTER commit — never a direct in-request broker publish (which can be lost after commit before send).
- The Queue Envelope carries identity only (`envelope_version`, `event_id`, `task_id`, `trace_id`,
  `event_type`). NEVER Cookies, storage state, Authorization, Provider keys, raw diagnostics, raw page
  data, or executable capabilities. An unsupported version is durably dead-lettered and ACKed WITHOUT
  loading a Job/credentials/Playwright. Queue payload fields are NEVER authorization — fresh
  DB/policy/session checks are always required because a message may outlive revocation/cancellation/policy
  or a lease change.
- A queue message is a NOTIFICATION; a guarded PostgreSQL `UPDATE ... RETURNING` claim (attempt_id + lease
  owner/token/expiry) grants temporary EXECUTION AUTHORITY to exactly one Worker. A terminal task is never
  re-executed; an unexpired foreign lease blocks a claim.
- A terminal `succeeded` write / Artifact publication is allowed ONLY under the current Day63 final fence
  (active + session-expiry + lease_owner==attempt + lease_token + unexpired lease + version). A stale
  Worker whose token/version was superseded or whose lease expired can NEVER publish — valid bytes are not
  a trusted Artifact.
- Commit the durable result BEFORE ACK. A redelivered Worker that reads a terminal state does NOT re-run
  Playwright; it ACKs the duplicate and does NOT return a result to the Broker. A RUNNING task with an
  expired lease goes to Day65 UNKNOWN_OUTCOME reconciliation, not a blind re-run.
- Lease expiry = loss of authority, NOT proof the external action did not happen. Recovery hands off to the
  Day65 outcomes: `CONFIRMED_COMPLETED` publishes only under the current fence; `ACCEPTED_OR_IN_FLIGHT`
  keeps reconciling (no replay); `CONFIRMED_NOT_STARTED` may enter the bounded-retry gate; `STILL_UNKNOWN`
  is retained/investigated. A retry is a NEW auditable Attempt (new attempt_id + lease token), never an
  in-process loop or reuse of the old lease; the gate is the Day65 fenced `authorize_retry`.
- Cancellation/revocation are durable and cooperative: record `cancellation_requested` (not immediate
  `cancelled`) when an external effect may have begun; check durable truth before the claim and revalidate
  the final fence before credential load, before each critical action, and before publication. The
  cancellation request and the external outcome are separate auditable facts.
- `202 Accepted + task_id`; `accepted != running != succeeded != published Artifact`. The Tool Result to
  the Provider/LLM is a tenant-authorized, verified, safe summary + a protected Artifact REFERENCE only —
  never raw CSV/trace/Cookie/storage-state/headers/DOM/network/diagnostics.
- Identity: `task_id` is stable across attempts; `attempt_id` changes per attempt; `lease_token` fences one
  authority grant; `outbox_event_id` is dispatch intent; `trace_id` links observability. Audit events carry
  identity + state transition + policy/contract version + classification + timestamp — never credentials or
  raw sensitive content.
- Incident (stale-Worker fence removal): `contain -> scope -> classify -> repair -> controlled rollout`;
  roll back the faulty WORKER RELEASE (not merely config), pause risky claims/Attempts, quarantine any
  stale-published Artifact (never trust/return it to the LLM), reconcile, restore the fencing predicate,
  add concurrent A/B regression tests, and roll out under monitoring.

## Run

```bash
cd projects/fastapi-playwright
python3 -m pip install pytest==7.4.3
python3 -m pytest -q tests/test_day66_queue_backed_permissioned_worker.py
# -> 14 passed: pure decision-core rules. No Provider/LLM, PostgreSQL, Redis/Celery, Outbox Relay,
#    Playwright, or Object Storage is involved.
```

## Validation matrix (evidence tiers)

```text
[CONCEPTUAL_STATIC]      The LIVE CLASSROOM produced the architecture, state machine, failure analysis,
                         rollback plan, and permissioned Tool Contract only — no Day66 source, tests,
                         PostgreSQL, Redis/Celery, Outbox Relay, queue redelivery, Playwright, Session
                         Store, Object Storage, Provider call, integration, or production ran in class.
[EXECUTED_LOCAL_RUNTIME] Run by the updating agent: py_compile + the pure decision core
                         (proposal/acceptance/envelope/claim/fence/dedupe/recovery/retry/cancellation/
                         result/audit/incident) = 14 passed.
[NOT RUN]                Real Provider/LLM tool loop; real guarded PostgreSQL concurrent claim; real Outbox
                         Relay/Broker duplicate delivery; real Celery ACK/redelivery; real lease
                         expiry/recovery; real Playwright BrowserContext execution; real Session
                         revocation/cancellation; real Object Storage Artifact publication; integration.
[PRODUCTION]             NOT RUN.
```

Day65's `20 passed` and prior Day59–Day61 evidence are NOT reused as Day66 validation. No secrets, real
credentials, real URLs, Cookies, storage state, Authorization headers, Provider keys, customer data, raw
traces/screenshots/DOM/network payloads, or real Provider calls are committed.
