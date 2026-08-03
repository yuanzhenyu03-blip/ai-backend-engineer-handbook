# Day50 — Idempotent AI Job Acceptance and Transactional Outbox (Design + Runbook)

Engineering artifact for `docs/fastapi/day50-idempotent-ai-job-api-and-transactional-outbox-integration.md`.
Runnable control-flow model: [`day50_job_acceptance_outbox.py`](day50_job_acceptance_outbox.py); tests:
[`test_day50_job_acceptance_outbox.py`](test_day50_job_acceptance_outbox.py); deps:
[`requirements-day50.txt`](requirements-day50.txt).

Continues the existing `projects/ai-backend-data-layer/` artifact. Reuses Day47 short UoW + guarded transitions,
Day33 Job+Outbox atomicity, Day34 `FOR UPDATE SKIP LOCKED`/short-claim + lease, Day41 fencing-token reasoning, and
Day49 verified, tenant-owned Documents (the only accepted Job inputs) + reconciliation of unknown external outcomes.

---

## 0. Evidence label (read first)

```text
CONCEPTUAL / CLASSROOM DESIGN : COMPLETED
STATIC DAY50 FILE CHECKS      : RUN (py_compile of module + tests)
FAKE TRANSPORT/STORE RUNTIME  : RUN (in-memory adapter + store; application control flow only)
POSTGRESQL RUNTIME            : NOT RUN (no server/driver; no UNIQUE/tx/isolation/ON CONFLICT/SKIP LOCKED proof)
BROKER / CELERY RUNTIME       : NOT RUN (no ACK/redelivery/poison-task/Worker runtime)
REAL PROVIDER / INTEGRATION   : NOT RUN
PRODUCTION VALIDATION         : NOT RUN
```

The fake store + transport prove APPLICATION CONTROL FLOW only. Three distinct claims are kept separate throughout:
**Conceptual Artifact**, **Static/Fake-adapter Verification** (what ran), and **Real Runtime Verification** (NOT
RUN). Day49 evidence is not inherited as Day50 evidence.

Executed: `python3 -m pytest -q test_day50_job_acceptance_outbox.py` -> **29 passed**
(Python 3.10.12, pytest 7.4.3; the module + tests are Python-standard-library only).

---

## 1. Core mental model

```text
Idempotency-Key = identity of one logical client command
fingerprint     = evidence the command semantics did not change (the key is NOT fingerprint material)
UNIQUE(tenant_id, idempotency_key) = the DATABASE arbitrates concurrent acceptance (not app SELECT-then-INSERT)

verified Document (Day49)
-> validate request (key present; every Document verified + tenant-owned)
-> ONE short UoW: Job + exactly ONE job.dispatch_requested Outbox intent
-> commit together or roll back together   (never a 202 for a Job with no dispatch intent)

Outbox = durable obligation to ATTEMPT dispatch
Relay  = at-least-once delivery; published_at is a publication checkpoint, NOT Job success
unknown publish result = retain evidence and retry (duplicates OK), never delete or guess

duplicate Queue message -> Worker guarded queued->running claim -> only one owner may call the Provider
short Relay claim + lease + fencing token -> no long DB lock over transport I/O;
    a stale Relay cannot overwrite a newer owner's checkpoint

No exactly-once across PostgreSQL + broker + Worker + Provider. Use durable identity, guarded transitions,
idempotent recovery, and evidence retention instead.
```

---

## 2. API idempotency contract (`POST /jobs`)

- **Key present** — a missing/blank `Idempotency-Key` is rejected BEFORE any DB write (`accept_job` ->
  `MISSING_IDEMPOTENCY_KEY`). A server-generated unknown key cannot make an ambiguous retry safe; the client creates
  and reuses one key per logical command.
- **Same key + same fingerprint** -> return the original Job; create no second Job or dispatch intent
  (`RETURNED_EXISTING`).
- **Same key + changed business semantics** -> 409 `CONFLICT`, no Job and no Outbox row.
- **Key vs fingerprint** — the key is the identity of a logical command; the fingerprint is server evidence that the
  key was not reused for a *different* command. `compute_request_fingerprint` covers every behavior-changing
  normalized field (verified Document/Artifact references, prompt/instruction, model/execution profile, output
  contract, token/quality options, API version). Document ordering is canonicalized ONLY for an explicitly unordered
  product contract (`unordered_documents=True`); otherwise order is preserved because it can change model semantics.
- **Retention is a retry contract** — idempotency evidence lives for an explicit window; a late retry after it
  expires must never be silently treated as a new command. A safe client rule is a fresh, never-reused random key
  per logical command.

The database is the concurrent arbiter: `UNIQUE(tenant_id, idempotency_key)` (already in the published schema) plus
an atomic insert/conflict path (`INSERT ... ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING`, modeled
by `upsert_job_on_conflict`). The conflict decision AND the create happen INSIDE one critical section
(`self._accept_lock` in the fake store), so two concurrent requests that both read absence cannot both create: the
first wins and creates the Job + dispatch intent, the second observes the conflict inside the atomic op and returns
the existing Job WITHOUT creating anything. A plain existence read outside that op is only a fast path (it does not
decide creation). `SELECT`-then-`INSERT` is wrong because BOTH concurrent requests see absence and create
duplicates; the arbitration must live in the single atomic op (proven by the forced-interleaving concurrency test).

---

## 3. Acceptance UoW (atomic Job + one dispatch intent)

```text
validate Idempotency-Key format -> compute request fingerprint
-> if a Job already exists for (tenant_id, idempotency_key):        # idempotent fast path
     same fingerprint  -> RETURNED_EXISTING (original Job; DO NOT re-run Document admission)
     different         -> 409 CONFLICT (no durable facts)
-> only for a NEW command: validate Documents verified + tenant-owned  # mutable admission check
-> upsert_job_on_conflict (modeled INSERT ... ON CONFLICT (tenant_id, idempotency_key)):
     build Job(queued) + one job.dispatch_requested OutboxRow  (BEFORE any mutation)
     commit BOTH together  (fail_before_commit -> raise -> NEITHER persists)
     if a concurrent winner already inserted -> return the existing Job (created=False) -> arbitrate by fingerprint
-> at-most-one dispatch intent per Job: logical UNIQUE(job_id, event_type='job.dispatch_requested')
```

ORDER matters (P1-3): the same-key fast path runs BEFORE the mutable Document admission check, so an exact retry of
an already-accepted command returns the original Job even if a referenced Document later became unavailable; the
verified + tenant-owned Document check runs only for a NEW command. Never return 202 for a Job with no durable
dispatch intent. The API UoW NEVER calls the broker/transport inside its DB transaction.

---

## 4. Transport + Relay boundary

- After commit, the Relay consumes durable unpublished Outbox intent through a small
  `TransportAdapter.publish(envelope)` seam (`InMemoryTransport` / `FailingTransport` /
  `CrashAfterPublishTransport` in tests).
- The **envelope is small and stable**: `outbox_event_id`, `event_type`, `job_id`, and a correlation/trace id. The
  Queue is not Job truth; the Worker re-reads the Job by `job_id`. Do NOT copy Prompt, sensitive content, or mutable
  Document details into the message.
- `published_at` is ONLY the Relay publication checkpoint. It does NOT prove Worker claim, Provider call, or Job
  success.
- `run_relay_once`: **claim** DUE unpublished intents in a short tx (`claim_outbox_batch`, modeling `FOR UPDATE SKIP
  LOCKED` + a lease owner/hold) -> **publish OUTSIDE any DB lock** -> **fenced checkpoint**
  (`checkpoint_published_if_owner`). No DB lock is held across transport I/O (long uncertain external I/O would
  expand the transaction, block Relay progress, cause lock waits/timeouts, harm availability, and still cannot make
  a cross-system transaction).

---

## 5. Failure + recovery

- **Publish succeeds but Relay crashes before `published_at`** — outcome unknown; leave `published_at IS NULL`,
  let the lease expire, and republish on a later pass. This is at-least-once and intentionally permits duplicate
  messages so an accepted Job is not lost (`CrashAfterPublishTransport` -> `crashed_before_checkpoint`).
- **Temporary transport failure** — keep the event, increment `attempt_count`, store a **redacted** error, compute
  `next_attempt_at` via bounded exponential backoff with jitter (`compute_next_attempt`), release the lease, and
  retry later. A pass before `next_attempt_at` claims nothing.
- **Permanent/exhausted** — retain the original intent + evidence in a visible `QUARANTINED` recovery state; alert,
  fix, controlled-replay. Never delete it silently, and never mark the Job `failed` merely because dispatch has not
  completed. Job failure is a guarded business-execution terminal state; a quarantined Outbox means an accepted Job
  still needs operational recovery.

Retain after a timeout: event identity/payload/reference, `published_at=NULL`, incremented attempt count, redacted
last error, and next retry time — do not delete or claim success.

---

## 6. Concurrency boundaries (four distinct layers)

```text
acceptance  : UNIQUE(tenant_id, idempotency_key)         -> one Job per logical command
dispatch    : UNIQUE(job_id, 'job.dispatch_requested')   -> at most one dispatch intent per Job
relay       : short claim + lease owner + fencing token  -> one publisher; stale relay cannot checkpoint
worker      : guarded UPDATE ... WHERE job_status='queued' RETURNING -> one executor may call the Provider
provider    : stable provider correlation/idempotency + evidence reconciliation (Day53; recorded, not implemented)
```

`worker_claim` returns True for exactly one winner; duplicate deliveries get False (zero rows) and MUST NOT call the
Provider. A fencing token guards Relay checkpoint AND failure-recording writes: both
`checkpoint_published_if_owner` and `record_transport_failure` require a LIVE lease — the owner token must match AND
`now < relay_hold_until` — so a Relay whose lease merely EXPIRED (even before a new owner takes over) is rejected
with `FencingError` and can never write `published_at` or retry state (P1-2).

---

## 6b. Review round 1 fixes (P1)

- **P1-1 (atomic acceptance arbitration):** the conflict decision + create are one atomic op
  (`upsert_job_on_conflict` under `self._accept_lock`); a plain existence read is only a fast path. Two concurrent
  same-key requests yield exactly one `CREATED` and one `RETURNED_EXISTING` (1 Job, 1 dispatch intent) — proven by a
  forced-interleaving thread test.
- **P1-2 (relay lease expiry):** `checkpoint_published_if_owner` and `record_transport_failure` require a LIVE lease
  (owner match AND not expired); an expired Relay is fenced even before a new owner takes over, so `published_at`
  stays NULL.
- **P1-3 (idempotent retry ordering):** the same-key fast path (return the original Job on a matching fingerprint,
  409 on a changed one) runs BEFORE the mutable Document admission check; the verified + tenant-owned Document check
  runs only for a NEW command.

---

## 7. Schema honesty

The published schema HAS `UNIQUE(tenant_id, idempotency_key)` on `app.jobs` (the real acceptance arbiter) and
`app.outbox_events(event_type, payload, published_at)`. It does NOT yet have: a request-fingerprint column on
`jobs`, a logical `UNIQUE(job_id, event_type)` on `outbox_events`, or Relay operational columns (`attempt_count`,
`last_error`, `next_attempt_at`, a dispatch/quarantine state, and a relay owner/lease/fencing token). Those are
**modeled in-memory** here. In the REAL schema they require a **Day48-safe FORWARD additive migration** (new
nullable columns + a partial/logical unique index, via a branch revision) — NOT implemented here, and no published
Alembic revision is rewritten. This artifact makes no real PostgreSQL/broker/Worker/Provider runtime claim.

---

## 8. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| Static file checks | RUN | `py_compile` module + tests |
| Fake store + transport runtime | RUN | in-memory adapter, 29 pytest cases (control flow only) |
| Acceptance idempotency + fingerprint conflict | MODELED (RUN) | `UNIQUE(tenant,key)` dict + fingerprint compare; lost-202, 409, key!=fingerprint tests |
| Atomic concurrent acceptance arbitration (P1-1) | MODELED (RUN) | `upsert_job_on_conflict` under a lock; forced-interleaving THREAD test -> one CREATED + one RETURNED_EXISTING, 1 Job, 1 intent |
| Atomic Job + one dispatch intent | MODELED (RUN) | `upsert_job_on_conflict` all-or-nothing + mid-tx failure test; `UNIQUE(job_id,event_type)` |
| Idempotent retry vs mutable Document admission (P1-3) | MODELED (RUN) | exact retry returns the original Job after a Document becomes unavailable; a new key is still rejected |
| At-least-once relay + retention/backoff/quarantine | MODELED (RUN) | timeout retains + attempt/error/next_attempt; crash-before-checkpoint redelivers; quarantine keeps Job queued |
| Relay claim/lease/fencing (SKIP LOCKED) (P1-2) | MODELED (RUN) | `claim_outbox_batch` skip-locked; EXPIRED-lease checkpoint/failure -> `FencingError`, `published_at` stays NULL; takeover fencing; no publish inside claim |
| Worker guarded claim (duplicate absorption) | MODELED (RUN) | one `RETURNING` winner, others zero rows |
| Real PostgreSQL UNIQUE/tx/isolation/ON CONFLICT/SKIP LOCKED | NOT RUN | needs a server + async driver + Day42 raw SQL + a Day48-safe additive migration |
| Real broker/Celery (ACK/redelivery/poison) + Worker/Provider runtime | NOT RUN | Day55 / Day53 scope |
| Integration + production | NOT RUN | — |

`Fake control-flow tests prove application control flow, not PostgreSQL constraints/transactions/isolation, real
broker/Celery semantics, Worker ACK/redelivery, or real Provider behavior.`

---

## 9. Boundaries preserved (not implemented here)

No exactly-once across PostgreSQL + broker + Worker + Provider. Day51 authentication (who may submit); Day52
authorization/tenant isolation/quotas (derive/enforce the tenant, not a client-supplied one); Day53 real Provider;
Day55 supported Celery broker transport + ACK/redelivery/poison-task + real Worker recovery. This artifact does not
implement or claim any of them, uses no real broker/Redis Streams/Celery/Provider, and is not a Celery replacement.
