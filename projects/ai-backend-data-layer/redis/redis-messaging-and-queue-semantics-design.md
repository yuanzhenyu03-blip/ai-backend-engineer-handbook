# Redis Messaging and Queue Semantics Design

Day40 design artifact for the AI Backend Data Layer. It defines how Redis **Lists**, **Pub/Sub**, and
**Streams** are used according to their delivery and failure semantics for recoverable Job dispatch and
notification delivery — while PostgreSQL stays the durable Job truth and idempotency makes redelivery safe.

> **Validation status of this whole document.** Everything below is **CONCEPTUAL / STATICALLY REVIEWED**
> only. **RUNTIME NOT RUN. PRODUCTION NOT VALIDATED.** No Redis server, `redis-cli`, Stream, Consumer Group,
> PEL, `XACK`, `XCLAIM`/`XAUTOCLAIM`, `XADD`/`XREADGROUP`, trim, Pub/Sub, List, PostgreSQL, Celery, Worker,
> Provider, email Provider, or Object Storage integration was run or measured. Stream names, group names, and
> payload shapes are **static design examples**, not measured results or production recommendations. This is
> **not** a Celery replacement and does not claim Redis provides exactly-once processing. Contains **no
> secrets or real connection strings**.

Related: [Day40 lesson](../../../docs/redis/day40-redis-messaging-and-queue-semantics.md) ·
[Day39 cache consistency design](redis-cache-consistency-design.md) ·
[Day38 acceleration-layer design](redis-acceleration-layer-design.md) ·
[project README](../README.md)

---

## 1. Ownership recap (the boundary Day40 builds on)

```text
PostgreSQL = AUTHORITATIVE Job/Attempt/Event/Outbox/Notification-Delivery truth (a COMMIT is authority).
Object Storage = large bytes (300 MB PDFs, result Artifacts). Stream messages carry REFERENCES, never bytes.
Redis Streams = RECOVERABLE transport for background work. A delivery is NOT proof of a completed Job.

A Redis Stream delivery, and even an XACK, is transport state -- not business truth. Business completion is
decided by PostgreSQL Job/Attempt/Event/Outbox/Notification records plus Provider/email reconciliation.
```

---

## 2. List vs Pub/Sub vs Streams (decision table)

| Model | Retained backlog (see note *) | Per-consumer ownership / PEL | ACK | Claim / redelivery | Replay | Use for | Not for |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **List** (`LPUSH`/`BRPOP`) | retained if Redis-persisted * | no | no | no | no | a simple in-order queue where loss/redelivery handling is built elsewhere | recoverable Job dispatch needing ownership + redelivery |
| **Pub/Sub** | **no** | no | no | no | **no** | loss-tolerant **live** notifications (a dashboard tick) | recoverable Job dispatch; an offline/crashed subscriber permanently misses the message |
| **Streams + Consumer Groups** | retained * | **yes (PEL per group)** | **yes (`XACK`)** | **yes (`XCLAIM`/`XAUTOCLAIM`)** | yes | recoverable background Job dispatch and notification delivery | as a substitute for durable business truth (that is PostgreSQL) |

```text
* Retained backlog is SUBJECT TO configured Redis persistence (RDB/AOF) and replication/failover loss windows
  (Day38). Redis Streams / Lists may RETAIN transport entries, and persistence REDUCES loss windows, but it
  does NOT make Redis durable business truth. PostgreSQL remains the AUTHORITATIVE durable Job / Attempt /
  Event / Outbox / Notification truth.
Key gap of a List vs a Stream: a List may be PERSISTED, but it lacks native Consumer Group ownership, a PEL,
ACK, Claim, and redelivery lifecycle. Persistence is not a consumer recovery lifecycle.
Pub/Sub is live broadcast with NO backlog/ACK/PEL/Claim/replay -- only for loss-tolerant live notifications.
```

---

## 3. Small Stream payload contract (Outbox-published)

Each Stream entry is published by the **Relay** from a **committed PostgreSQL Outbox intent** (Day33). The
event's meaning comes from the committed transaction that produced it, not from the Stream:

```text
# Accept transaction commits (Job queued + job-dispatch Outbox intent); the Relay then publishes:
XADD ai:stream:job-dispatch:v1 * \
     tenant_id {tenant_id}  job_id {job_id}  event_id {event_id}  event_type job.dispatch  trace {trace_id}   # STATIC example only

# Complete transaction commits (Job running -> succeeded + job.completed Outbox intent); the Relay then publishes:
XADD ai:stream:job-events:v1 * \
     tenant_id {tenant_id}  job_id {job_id}  event_id {event_id}  event_type job.completed  trace {trace_id}   # STATIC example only

Payload = small REFERENCES only: tenant_id, job_id, event_id, event_type, trace metadata.
The Worker/Consumer loads Job/Attempt metadata from PostgreSQL and large bytes (300 MB PDF, result Artifact)
from Object Storage BY REFERENCE. PostgreSQL owns durable artifact references/provenance and is the event
SOURCE (committed Outbox / Event); a Redis delivery is not business truth.
Never put a large document or result bytes in a Stream payload (memory, replication, and redelivery cost).
```

---

## 4. Event lifecycle and Consumer Group topology (distinct events, not just distinct groups)

Dispatch and completion are **different committed events at different points in the Job lifecycle**. A
`job-dispatch` event is emitted at **Accept** (the Job is not finished), so a completion email must **not** be
derived from it. Separate Consumer Groups only solve "two groups can each receive the same Stream entry"; they
do **not** turn a dispatch entry into a completion event.

```text
Accept Transaction (Day33 Outbox)
  Job queued + job-dispatch Outbox intent committed
  -> Relay publishes a small dispatch reference
  -> ai:stream:job-dispatch:v1
       └── Group  g:job-exec        (Worker executes / reconciles Provider work)        -> own PEL / ACK / Claim

Complete Transaction (Day33 Outbox)
  Job running -> succeeded committed + job.completed Outbox intent committed
  -> Relay publishes a small completed-event reference
  -> ai:stream:job-events:v1
       └── Group  g:notify-delivery (Notification Consumer reconciles / sends completion email) -> own PEL / ACK / Claim

Within ONE group a message goes to ONE consumer (competing consumers), NOT broadcast to all.
The completion email is driven ONLY by a committed job.completed Outbox/Event -- NEVER by an accept/dispatch
entry. The event SOURCE is the PostgreSQL committed Outbox/Event; a Redis delivery is not business truth.

Alternative (one shared event stream): ai:stream:job-events:v1 carrying an explicit event_type, where the
notification Consumer processes ONLY committed job.completed events and IGNORES accept/dispatch events. Same
rules apply: small references only; PostgreSQL Outbox/Event is the source; Provider and email each use their
own stable idempotency identity.
```

---

## 5. PEL / ACK / Claim / redelivery lifecycle

```text
XREADGROUP -> entry enters the group's Pending Entries List (PEL) for the consumer that read it
process   -> persist a durable, recoverable processing decision in PostgreSQL FIRST
XACK      -> closes delivery responsibility for THIS group only (not business truth, not other groups)

Crash BEFORE XACK:
  the entry stays PENDING in the PEL. Redis CANNOT know whether the business effect happened.
  it must remain recoverable: another consumer XCLAIM/XAUTOCLAIM takes it after an idle timeout,
  reconciles durable state, then XACKs only after the recovered durable decision.

At-most-once  = XACK (or remove PEL) BEFORE processing -> a crash silently LOSES the Job. Rejected here.
At-least-once = process + persist, THEN XACK -> a crash may REDELIVER -> safe ONLY with idempotency.
Redis alone CANNOT give exactly-once across (Redis ACK + PostgreSQL commit + external Provider call).
```

---

## 6. Delivery vs durable business-completion boundary

```text
XACK confirms TRANSPORT delivery for one group. It does NOT prove:
  - the Provider call completed
  - PostgreSQL committed the Job/Attempt/Event
  - the email was actually sent

The Provider can succeed BEFORE PostgreSQL persistence or before XACK, so redelivery can repeat the message.
Business completion is decided by PostgreSQL guarded state transitions + stable idempotency identities +
reconciliation of Provider/email outcomes -- never by the presence or absence of a Redis delivery.
```

---

## 7. Per-side-effect idempotency and reconciliation

```text
One job_id is NOT a sufficient idempotency key: completion, failure, and admin-alert notifications are
SEPARATE side effects. Use a DELIVERY-SPECIFIC key per effect, e.g.:

  Provider call        : stable Attempt/Provider idempotency identity (derived from attempt_id)
  completion email     : job:{job_id}:notification:completion:v1
  failure email        : job:{job_id}:notification:failure:v1
  admin alert          : job:{job_id}:notification:admin-alert:v1

Before repeating any external side effect after redelivery: inspect durable state (Attempt/Event/Notification
Delivery) + the stable idempotency evidence, reconcile the real outcome, and only then decide. A Job Attempt/
Event alone does NOT prove an email was delivered -- notification delivery needs its OWN durable record.
```

---

## 8. Poison messages: retry classification and quarantine boundary

```text
Bounded retry is for PLAUSIBLY TRANSIENT failure -- it is NOT proof of a permanent root cause, and a retry
LIMIT is a capacity-containment policy, not an error classifier.

A fixed, immutable payload missing required tenant_id is a PERMANENT message-CONTRACT failure: retrying the
identical message can never repair it.

Correct path:
  bounded retry
    -> durable QUARANTINE / dead-letter evidence (record the poison message + failure evidence)
    -> ALERT
    -> repair the PRODUCER / message contract
    -> controlled REPLAY of a CORRECTED message
  ACK the original ONLY after durable quarantine evidence exists. NEVER silently delete a failed Job message.
```

---

## 9. Safe trim / retention contract

```text
Trimming (XTRIM / MAXLEN) is a CAPACITY / RETENTION policy, not blind deletion under memory pressure.
NEVER trim:
  - pending (unacknowledged) entries still in a group's PEL
  - recovery / quarantine / dead-letter evidence
before the Consumer Group, retry, and retention contracts permit it.
Unsafe trim DESTROYS Claim / redelivery / replay capability -- it deletes recovery evidence.
```

---

## 10. Integrated failure / recovery matrix

Scenario: the Job Worker and the notification Consumer both crash **after** their external calls but **before**
`XACK`; both messages remain Pending. An operator proposes aggressive Stream trimming and re-sending every Job.

| Step | Action | Why |
| --- | --- | --- |
| 1 | **Preserve evidence** | do not trim Pending entries or quarantine/recovery evidence |
| 2 | **Inspect PostgreSQL** | Job / Attempt / Event / Outbox / Notification-Delivery facts decide what really happened |
| 3 | **Reconcile external outcomes** | use stable ids to check Provider and email results before repeating them |
| 4 | **Each group Claims its own Pending** | `g:job-exec` (on `ai:stream:job-dispatch:v1`) and `g:notify-delivery` (on the `job.completed` events stream) recover independently via their own PEL |
| 5 | **ACK only after the recovered durable decision** | `XACK` closes transport responsibility once the durable truth is established |

```text
Explicitly DO NOT: blindly rerun all Jobs; blindly repeat Provider/email calls; silently delete messages;
aggressively Trim Pending recovery evidence.
```

---

## Messaging decision summary (one screen)

```text
model        -> List (simple queue, no recovery lifecycle) / Pub-Sub (live, lossy) / Streams+Groups (recoverable)
payload      -> small references (tenant_id, job_id, event_id, trace); bytes in Object Storage, refs in PostgreSQL
topology     -> distinct lifecycle events on distinct streams (Accept->job-dispatch->g:job-exec;
                Complete->job.completed events->g:notify-delivery); within a group one message -> one consumer;
                completion email driven ONLY by a committed job.completed event, never by a dispatch entry
lifecycle    -> XREADGROUP -> PEL -> persist durable decision -> XACK (this group only)
crash pre-ACK-> entry stays Pending -> XCLAIM/XAUTOCLAIM -> reconcile durable state -> XACK
delivery     -> at-least-once + idempotency; NO exactly-once across ACK + commit + Provider
idempotency  -> per-side-effect key (completion/failure/admin distinct); job_id alone is insufficient
poison       -> bounded retry -> durable quarantine -> alert -> fix producer -> controlled replay; never silent delete
trim         -> retention policy; never trim Pending / recovery / quarantine evidence
recovery     -> preserve evidence -> inspect PostgreSQL -> reconcile -> per-group Claim -> ACK after durable decision
```

---

## Future boundaries (not designed here)

```text
Day41  atomic composition (MULTI/EXEC, Lua), coordination, locks/leases + fencing, full rate-limiting
Day42  integrated data ownership + failure + recovery/verification (PostgreSQL + Redis + Object Storage)
Phase 4  SQLAlchemy / Alembic; a production broker (e.g. Celery) is used as a broker, not hand-rebuilt here
```

---

## Validation and evidence classification

```text
CONCEPTUAL / DESIGN     : the List/Pub-Sub/Streams decision table, payload contract, group topology,
                          PEL/ACK/Claim lifecycle, delivery-vs-completion boundary, per-side-effect
                          idempotency, retry/quarantine path, trim/retention contract, and recovery matrix
                          are design decisions and stated invariants.
STATICALLY REVIEWED     : the XADD/XREADGROUP/XACK/XCLAIM/XTRIM examples are read for shape and naming only.
RUNTIME NOT RUN         : no Redis, redis-cli, Stream, Consumer Group, PEL, XACK, XCLAIM/XAUTOCLAIM, trim,
                          Pub/Sub, or List was executed or measured.
INTEGRATION NOT RUN     : no PostgreSQL, Celery, Worker, Provider, email Provider, or Object Storage
                          integration; no Claim/ACK/redelivery/Trim runtime.
PRODUCTION NOT VALIDATED: not deployed; no production message loss, redelivery, poison message, or trim
                          incident observed.
SECURITY                : no secrets, credentials, connection strings, tenant identifiers, or production data;
                          all identifiers are placeholders.
NOT CLAIMED             : Redis does NOT provide exactly-once business processing; this is NOT a Celery
                          replacement.
```
