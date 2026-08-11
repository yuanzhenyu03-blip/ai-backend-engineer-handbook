# Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration

## 1. Lesson Metadata

```text
Status:        ✅ Completed
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 3–4 hours
Prerequisite:  Day50 transactional Outbox intent, Day55 Worker/lease model, Day59 real
               HTTP -> PostgreSQL acceptance boundary
Next Lesson:   Day61 — Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence
```

Phase 5 Production Integration Gate continues. Day60 is the FIRST real consumer of the
`job.dispatch_requested` Outbox intent Day59 committed: a real Redis/Celery Relay + Worker
path with at-least-once delivery, idempotent execution, Worker-loss recovery, and bounded
repair.

> Evidence honesty (Day60 review round 2): the repository includes a REAL
> Relay/Worker/recovery/repair runtime that uses the EXISTING Day48 lease TRIPLE
> (`lease_owner`/`lease_token`/`lease_expires_at`) — `day60_delivery_runtime.py` plus a real
> Celery app (`day60_celery_app.py`) and the Relay/sweeper entrypoints
> (`day60_relay.py`/`day60_sweeper.py`), the CONTROLLED CORRECTIVE (non-additive, DROP-column)
> `0011_day60_lease_realign` migration that removes the never-written parallel `lease_expiry`
> column 0010 added (safe only because it was brand-new/unused; NOT a production zero-downtime
> pattern), and the additive `0012_day60_repair_audit_attestation` migration that persists the
> repair incident window + operator attestations in `job_repair_history`. The
> repository updating agent re-ran only `py_compile` and the standard-library pure-logic +
> static-contract tests (**34 passed**, `EXECUTED_LOCAL_RUNTIME`). It has NO
> Docker/PostgreSQL/Redis/Celery, so the real runtime has NOT been executed against a real
> database + broker — **INTEGRATION_RUNTIME NOT RERUN**; no integration result is claimed.
> See the design/runbook's Required integration rerun matrix.

---

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain why the Relay publishes to the Broker BEFORE checkpointing `published_at`, and
  what `published_at IS NULL` does and does not prove.
* Design guarded PostgreSQL claims for competing Relays and for Worker authority
  (`FOR UPDATE SKIP LOCKED`, `UPDATE ... WHERE status='queued' RETURNING`).
* Explain lease token/owner/expiry fencing and why a stale Worker cannot commit after a
  takeover.
* Classify duplicate delivery, Worker-kill redelivery, expired lease without evidence, and
  expired lease with Provider evidence.
* Explain why Celery late ACK is transport acknowledgement, not a business commit, and why
  Celery retry / `.delay()` is not recovery authority.
* Design the bounded early-ACK repair eligibility predicate + an idempotent repair id.
* Label evidence honestly (static vs disposable local integration vs NOT RUN).

---

## 3. Why This Matters

A committed intent is worthless if delivery and execution are not crash-safe. In
production a Relay or Worker can die at any instant, the Broker can redeliver, and the same
long-running document/AI Job must never produce a second billable Provider call. Day60 is
where "we wrote the intent" becomes "exactly one authoritative attempt runs, and every
crash has a durable recovery path" — with PostgreSQL, not the Broker, as the source of
truth.

---

## 4. Roadmap Position

```text
Day50 transactional Outbox intent
Day55 Worker/lease model  ·  Day59 real HTTP -> PostgreSQL acceptance (job.dispatch_requested committed)
      |
      v
Day60 real Relay (publish-before-checkpoint) + guarded Worker claim + durable recovery (this lesson)
      |
      v
Day61 Object Storage + Provider HTTP + provider request evidence + tracing + reconciliation
Day62 Playwright runtime consumes the queue lifecycle
      |
      v
Interview readiness: at-least-once, idempotent execution, lease fencing, recovery, repair
```

### Knowledge continuity

Day59 ended at one committed bundle — `Job + fingerprint + document links +
job.dispatch_requested Outbox` — verified from a fresh read, with HTTP never calling the
Broker/Worker/Provider/storage. Day50 defined the transactional intent; Day55 defined the
Worker/lease ideas and the conservative `provider_dispatch_started_at` marker. Day60
connects those durable facts to real Broker delivery and recovery while keeping PostgreSQL
the business-state authority.

---

## 5. Lesson Map

```text
Relay publish-before-checkpoint  ->  competing-Relay claim/fencing  ->  guarded Worker authority + lease
    ->  late ACK vs business commit  ->  duplicate / worker-kill / expiry classification
    ->  durable recovery sweep (running->queued + one redispatch)  ->  bounded early-ACK repair  ->  evidence tiers
```

---

## 6. Core Mental Model

```text
Broker delivery      != execution authority   (PostgreSQL guarded claim is)
Celery ACK           != business-state commit  (late ACK is transport only)
published_at         =  a DELIVERY checkpoint, never proof of execution/success
lease expiry         != a license to retry     (external evidence -> PENDING_RECONCILIATION)
recovery authority   =  PostgreSQL state + a newly committed Outbox intent  (not Celery retry / .delay())
```

Deliver at least once; execute exactly once (guarded); recover only through durable
PostgreSQL facts plus a new committed intent.

---

## 7. Main Concepts

### Concept 1: Relay ordering — publish before checkpoint

Tech Lead Question: The Relay both publishes to the Broker and marks `published_at`. Which
comes first, and why?

Student Thinking / Answer: **"先发布再写"** (publish first, then write).

Tech Lead Review: Correct. The Relay publishes to the Broker FIRST, then guarded-checkpoints
`published_at`. A crash between them leaves an unpublished intent (`published_at IS NULL`),
so retry re-delivers → at-least-once. `published_at` is a delivery checkpoint, NOT proof of
Job execution or success. The student later refined that `published_at=null` is *necessary*
evidence of an absent checkpoint but **not enough alone** to prove whether execution
occurred.

### Concept 2: Competing Relays — claim + fencing, no lock over I/O

Tech Lead Question: Two Relays scan the same unpublished rows. How do they not double-work,
and what must you never do?

Student Thinking / Answer: **"update set returning"** (a guarded claim), and separately
**"update set returning，依靠postgresql"**.

Tech Lead Review: Right authority. Concretely: `SELECT ... FOR UPDATE SKIP LOCKED` +
`relay_owner`/`relay_token`/`relay_claim_expiry` to claim, then a fenced guarded checkpoint
keyed by the token. The rule you must not break: **the database lock is not held across
Broker I/O** — publish outside the lock, checkpoint under the fencing token.

### Concept 3: Worker authority — guarded claim + lease

Tech Lead Question: Celery delivered the task. Is that permission to execute?

Student Thinking / Answer: **"update set returning，依靠postgresql"**; for fencing
**"lease token"**.

Tech Lead Review: Delivery is not authority. The Worker takes authority with
`UPDATE app.jobs SET job_status='running', lease_owner=:w, lease_expiry=:exp WHERE
job_status='queued' RETURNING` — exactly one winner. The **lease token** answer was refined
to **owner/token/expiry plus a matching guarded commit**: the winner creates Attempt/Event
facts and completes the Job only under the matching lease token, so a **stale Worker cannot
commit after a takeover**.

### Concept 4: Late ACK is not a commit

Tech Lead Question: When should Celery ACK, and what does an ACK mean?

Student Thinking / Answer: **"Celery 的 ACK 应该发生在任务处理后"**, and
**"job_status、attempt、event、Result Artifact，并采取读取到事实以后继续ack"**.

Tech Lead Review: Correct on timing — `task_acks_late=True`,
`task_reject_on_worker_lost=True`, prefetch 1, so ACK follows processing and a lost Worker
redelivers. Refinement: **ACK follows the relevant business fact, and Day60 does not yet
produce the Day61 Result Artifact** — ACK is transport acknowledgement, never a
business-state commit.

### Concept 5: Duplicate, Worker-kill, and expiry

Tech Lead Question: A duplicate delivery arrives. What happens?

Student Thinking / Answer: **"结束这次重复投递"** (end this duplicate delivery); and for
external uncertainty **"不能，应该进入pending_reconciliation"**.

Tech Lead Review: Split by case:

```text
duplicate while THIS Worker holds a credibly active lease   -> NOOP (no Provider call, no 2nd claim)
redelivery to a DIFFERENT worker, lease still unexpired      -> DEFER to the durable sweep (worker-loss SUSPECTED)
expired lease + external evidence                            -> RECONCILE_ONLY (PENDING_RECONCILIATION)
expired lease + NO external evidence                         -> the sweeper may redispatch
```

The "healthy duplicate is no-op" answer was correctly narrowed: it is safe only while the
lease is credibly active; Worker loss and external uncertainty must keep a durable later
recovery path.

### Concept 6: Durable recovery sweep

Tech Lead Question: An expired lease with no external evidence — how do you recover?

Student Thinking / Answer (English intermediate): previous Worker/provider evidence leads
to `PENDING_RECONCILIATION`; otherwise the expired-lease scan creates a recovery audit and
a new redispatch Outbox intent in one transaction, then the Relay redispatches.

Tech Lead Review: Exactly. The sweeper atomically moves `running -> queued`, records a
recovery audit event, and writes **exactly one** new `job.redispatch_requested` Outbox
intent; the Relay delivers it. Celery retry is transport behaviour — the student's earlier
idea that "Celery retry is a recovery mechanism" was corrected: **durable recovery authority
is PostgreSQL state plus a newly committed Outbox intent.**

### Concept 7: Bounded early-ACK repair — never `.delay()`

Tech Lead Question: A bad release acked early. How do you repair, and what must repair not
do?

Student Thinking / Answer: **"回滚release，不能对Celery 调用 .delay()"**.

Tech Lead Review: Correct. Contain by rolling back the erroneous configuration FIRST.
Repair does NOT call `.delay()`: it publishes immediately but creates no transactionally
coupled, replayable, auditable business intent. Repair selects a BOUNDED eligible set,
re-verifies it in the repair transaction, records immutable `job_repair_history` (keyed by a
deterministic `repair_id`, so concurrent/duplicate repair applies exactly once), and writes
exactly one new redispatch Outbox intent before commit.

Production Example: an early-ACK config marked messages acknowledged before the Worker
committed business facts. Because ACK is not a commit, the durable Job/Attempt facts are
the truth: roll back the config, bound the affected set by bad version + time window +
`queued` + original checkpointed dispatch + no attempts/evidence + no conflict + valid
deadline/contract/budget + unapplied repair, re-verify, audit, write one durable intent,
commit.

---

## 8. Common Misconceptions

```text
published_at IS NULL
❌ It proves the whole system did not execute the Job.
✅ It proves only that no Relay checkpoint was recorded; execution truth needs Job/Attempt/Event (and Day61 Provider/Result).

Healthy duplicate
❌ A duplicate delivery is always a safe no-op.
✅ Safe only while the existing lease is credibly active; Worker loss / external uncertainty must keep a durable recovery path.

Celery retry
❌ Celery retry is the recovery mechanism.
✅ Celery retry is transport behaviour; durable recovery authority is PostgreSQL state + a newly committed Outbox intent.

Lease duration
❌ It just needs to exceed delivery time.
✅ It must cover the bounded work/renewal model, be observable, and fence stale Workers by token; expiry opens an external-execution uncertainty branch.

Repair via .delay()
❌ Repair can re-publish with Celery .delay().
✅ .delay() publishes immediately but creates no transactionally coupled, replayable, auditable intent; repair writes a durable Outbox intent.
```

---

## 9. Engineering Trade-offs

```text
Publish-before-checkpoint vs checkpoint-first
  + At-least-once: a crash re-delivers; no lost intent.
  - Duplicates are possible -> execution must be idempotent (guarded claim + lease).

Guarded PostgreSQL claim vs trusting Broker delivery
  + Exactly one authoritative attempt; delivery stays at-least-once.
  - Requires durable state transitions and a recovery sweep, not just a queue.

Durable Outbox redispatch vs Celery retry / .delay()
  + Transactional, replayable, auditable recovery bound to business state.
  - More moving parts than a transport retry; but transport retry cannot own business truth.

Late ACK (acks_late) vs early ACK
  + A crashed Worker redelivers; no silent loss.
  - Duplicate processing risk -> mitigated by the guarded claim + lease fencing.
```

---

## 10. Hands-on Exercises

Question: Explain why the Relay publishes before checkpointing.

Think First: what does a crash leave behind in each ordering?

Expected Output: publish-first leaves an unpublished row on crash (retried → at-least-once);
checkpoint-first could mark delivered without delivering (lost message). `published_at` is a
delivery checkpoint only.

---

Question: Design the guarded `UPDATE ... RETURNING` for the Worker claim and the competing
Relay claim.

Expected Output: `UPDATE app.jobs SET job_status='running', lease_owner, lease_expiry WHERE
job_status='queued' RETURNING` (one winner); Relay `SELECT ... FOR UPDATE SKIP LOCKED` +
owner/token/expiry, publish outside the lock, fenced checkpoint under the token.

Follow-up: why must the DB lock not be held across Broker I/O?

---

Question: Classify duplicate delivery, Worker kill, expired lease without evidence, and
expired lease with Provider evidence.

Expected Output: NOOP (healthy own lease) · DEFER to sweep (worker-loss suspected) ·
SWEEP redispatch (expired, no evidence) · RECONCILE_ONLY / `PENDING_RECONCILIATION`
(expired, evidence).

---

Question: Design the bounded early-ACK repair eligibility predicate and an idempotent repair
identifier.

Expected Output: eligible iff bad release + time window + `queued` + original dispatch
checkpointed + no attempts/evidence + no conflict + valid deadline/contract/budget +
not-already-applied; `repair_id = repair:{job_id}:{release_version}:{reason}` as a
`job_repair_history` primary key.

---

## 11. Relevant Framework Connections

* **FastAPI:** Day59 acceptance ends at a committed PostgreSQL intent; HTTP never invokes
  the Broker/Worker. Day60 adds an explicit `create_app(expected_revision=...)` readiness
  factory (the Day59 app pinned `0008` and returns 503 after `0009`; the Day60 app requires
  `0009`).
* **PostgreSQL:** transaction authority, guarded transitions, row claiming
  (`FOR UPDATE SKIP LOCKED`), lease fencing, immutable Attempt/Event/repair audit facts, and
  an atomic redispatch intent.
* **Redis/Celery:** delivery transport only; `task_acks_late=True`,
  `task_reject_on_worker_lost=True`, prefetch 1; Worker-lost redelivery. `apply_async` /
  `.delay()` are Relay concerns, not business repair authority.

---

## 12. AI Backend Connections

Long-running document/AI Jobs can receive duplicate Broker delivery and lose the Worker
process. The same Job must not generate duplicate billable Provider calls. Day60 builds the
durable recovery boundary — an expired lease with external evidence goes to
`PENDING_RECONCILIATION`, never a second call. Day61 adds Provider request IDs, external
reconciliation, Object Storage result facts, and traces on top of this boundary.

---

## 13. English Interview

### Key Vocabulary

```text
transactional Outbox · Relay · publish-before-checkpoint · at-least-once · guarded claim
lease token/expiry/fencing · late ACK · idempotent redelivery · Worker-kill recovery
PENDING_RECONCILIATION · recovery sweep · bounded repair · immutable audit · redispatch intent
```

### Beginner Question

Q: What is the Outbox, and how does the Relay deliver from it?

Strong Answer: "The Outbox is a transactional intent record written in the same transaction
as the Job. The Relay performs delivery by scanning rows where `published_at` is null,
publishing the message to the Broker BEFORE populating `published_at`, which guarantees
at-least-once delivery — if it crashes in between, the row is retried." (Field name is
`published_at`, corrected from `publish_at`.)

### Intermediate Question

Q: A Worker's lease expired and a redelivery arrives. What do you do?

Strong Answer: "If there is previous Worker/Provider evidence that an external call may have
happened, the Job goes to `PENDING_RECONCILIATION` — never a second Provider call.
Otherwise, the expired-lease scan creates a recovery audit event and writes exactly one new
`job.redispatch_requested` Outbox intent in one transaction, and then the Relay
redispatches. Celery retry is transport, not recovery authority."

### Senior Question

Q: A bad release acked early and marked messages done. How do you contain and repair?

Strong Answer: "Roll back the configuration first. Then bound the affected Jobs by the bad
version and time window, `queued` state, the original checkpointed dispatch Outbox, no
attempts or external evidence, no conflict, valid deadline/contract/budget, and unapplied
repair. Re-verify inside the repair transaction, record immutable repair history keyed by a
deterministic repair id, write one new durable Outbox intent, and commit. I never use
Celery `.delay()` for repair — it publishes immediately but creates no transactional,
replayable, auditable business intent."

### Common Weak Answer

"`published_at IS NULL` means the Job never ran, so just re-run it." It proves only that no
Relay checkpoint was recorded; execution truth needs durable Job/Attempt/Event facts, and an
expired lease with external evidence must reconcile, not re-run.

---

## 14. Mental Model Summary

```text
Relay order        = publish to Broker FIRST, then guarded-checkpoint published_at (at-least-once)
published_at       = delivery checkpoint; NULL means "no checkpoint", not "did not execute"
Relay coordination = FOR UPDATE SKIP LOCKED + owner/token/expiry; never hold the lock over Broker I/O
Worker authority   = UPDATE ... WHERE status='queued' RETURNING (one winner) + lease token/owner/expiry
late ACK           = transport acknowledgement, NOT a business-state commit
duplicate/kill/exp = NOOP (healthy lease) / DEFER (worker-loss) / RECONCILE_ONLY (expired+evidence) / SWEEP (expired+none)
recovery           = running->queued + exactly one job.redispatch_requested intent (Celery retry is not authority)
repair             = contain config, bounded eligible set, re-verify, immutable repair_id history, one durable intent; never .delay()
evidence tiers     = CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION
```

### Mental Model Evolution

```text
Start:  "published_at IS NULL proves the Job did not run."
        "A duplicate delivery is always a safe no-op."
        "Celery retry / .delay() is the recovery mechanism."
        "A lease just needs to outlast delivery time."
   |
   v
End:    published_at NULL only means no Relay checkpoint; execution truth is Job/Attempt/Event.
        Duplicate no-op only under a credibly active lease; else keep a durable recovery path.
        Durable recovery = PostgreSQL state + a newly committed Outbox intent, not transport retry.
        Lease = bounded, observable, token-fenced; expiry opens an external-uncertainty branch.
```

---

## 15. Today's Takeaway

* Most important mental model: deliver at least once, execute exactly once (guarded claim +
  lease), recover only through durable PostgreSQL facts + a new committed intent.
* Most important production risk: treating Broker delivery/ACK, or `published_at`, as
  business truth — leading to a duplicate billable Provider call or a fabricated re-run.
* Most important framework/AI connection: an expired lease with external evidence →
  `PENDING_RECONCILIATION`, never a second Provider call.
* Most important interview answer: recovery/repair writes a durable Outbox intent; Celery
  `.delay()` is not repair authority.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain publish-before-checkpoint and what published_at IS NULL proves?
- [ ] Can I write the guarded Worker claim and the competing-Relay claim (and the no-lock-over-I/O rule)?
- [ ] Can I explain lease token/owner/expiry fencing and why a stale Worker cannot commit?
- [ ] Can I classify duplicate / worker-kill / expired-no-evidence / expired-with-evidence?
- [ ] Can I explain why late ACK is not a commit and Celery retry is not recovery authority?
- [ ] Can I design the bounded early-ACK repair predicate + idempotent repair id, and say why not .delay()?
- [ ] Can I state Day60's evidence tiers and its NOT RUN limits (Day61/Day62)?
```

---

Related: [Day60 design & runbook](../../projects/ai-backend-data-layer/api/day60-outbox-redis-celery-broker-and-worker-recovery-integration-design.md) ·
[Day59 lesson](day59-real-fastapi-runtime-postgresql-and-alembic-integration.md) ·
[FastAPI cheat sheet](../../cheat_sheets/fastapi.md) ·
[FastAPI interview](../../interview/fastapi.md)
