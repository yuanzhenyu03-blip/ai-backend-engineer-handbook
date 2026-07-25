# Lesson 40 — Redis Messaging and Queue Semantics

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day39 — Redis Cache Design and Consistency

Previous Lesson: [Day39 — Redis Cache Design and Consistency](day39-redis-cache-design-and-consistency.md)

Next Lesson: Day41 — Redis Coordination and Production Safety (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day41 lesson file does not exist yet)

Engineering Artifact: The Day40 Redis messaging and queue semantics design (`projects/ai-backend-data-layer/redis/redis-messaging-and-queue-semantics-design.md`) — the List/Pub-Sub/Streams decision table, small Stream payload contract, Consumer Group topology, PEL/ACK/Claim/redelivery lifecycle, the delivery-vs-durable-completion boundary, per-side-effect idempotency, retry/quarantine/dead-letter path, safe trim/retention contract, and the integrated failure/recovery matrix, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

Redis Cheat Sheet: [cheat_sheets/redis.md](../../cheat_sheets/redis.md)

Redis Interview: [interview/redis.md](../../interview/redis.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on Stream/Group topology + recovery-matrix design: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why an unacknowledged (Pending) Stream delivery is not proof of a completed Job, and which PostgreSQL facts decide business completion.
2. Compare at-most-once (early ACK) and at-least-once (delayed ACK) delivery, and defend persisting a durable processing decision before `XACK`.
3. Choose between Lists, Pub/Sub, and Streams by their delivery and failure semantics, and reject Pub/Sub for recoverable Job dispatch.
4. Design the event/group topology so distinct lifecycle events drive distinct effects — Accept commits a job-dispatch Outbox intent to `g:job-exec`, Complete commits a job.completed Outbox intent to `g:notify-delivery` — each group with an independent PEL/ACK/Claim lifecycle, and a completion email is never derived from a dispatch entry.
5. Explain why concurrent consumers do not guarantee business-effect completion order, and how PostgreSQL guarded transitions + idempotency preserve validity.
6. Keep Stream payloads to small references and keep large bytes in Object Storage with durable references/provenance in PostgreSQL.
7. Classify a poison message correctly (transient vs permanent message-contract failure) and design bounded retry → quarantine/dead-letter → alert → repair → controlled replay.
8. Define a safe trim/retention contract that never destroys Pending or recovery/quarantine evidence.
9. Give each notification side effect (completion/failure/admin) its own durable delivery identity rather than reusing `job_id`.
10. Recover dual consumer crashes after external calls but before `XACK` using evidence preservation, PostgreSQL inspection, reconciliation, per-group Claim, and ACK-after-durable-decision.
11. State honestly that Redis alone cannot provide exactly-once processing across Redis ACK, PostgreSQL commit, and an external Provider call.

---

# Why This Matters

Day39 made the cache safe around a PostgreSQL truth. Day40 moves to the transport that *dispatches* the work,
and the opening scene is the one that breaks naive queue code: a Worker consumed a Stream message, may have
already executed the business work, and crashed **before** `XACK`. Redis now holds the entry as Pending — and
critically, Redis cannot know whether the Provider call or the database write actually happened. Treat that
Pending entry as "done" and you silently lose Jobs; blindly re-run it and you pay for a duplicate model call or
send a second email.

The production stakes are money and trust. An eight-minute Provider call is expensive and side-effectful, so a
redelivered message must never blindly repeat it. A completion email is a separate effect from the Job itself,
so "the Job finished" is not "the email was sent." A poison message missing a required field will never heal by
retrying the identical payload, and an operator who "just trims the stream and re-sends everything" under memory
pressure can delete the exact recovery evidence needed to reconcile. Get the semantics wrong and you get lost
work, duplicated side effects, or destroyed recovery paths.

So the lesson is about matching Redis messaging primitives to their real delivery and failure semantics — Lists,
Pub/Sub, and Streams are not interchangeable — and about keeping PostgreSQL as the arbiter of business
completion while idempotency makes at-least-once redelivery safe. Redis is recoverable transport, not exactly-
once truth, and this lesson does not hand-build a Celery replacement.

Everything here is design and reasoning. Nothing was executed — no Redis, Streams, Consumer Groups, `XACK`,
Claim, trim, PostgreSQL, Celery, Provider, or email integration — and the artifact is labelled that way.

---

# Roadmap Position

```text
Day38 Redis as bounded rebuildable acceleration     Day39 cache consistency around the durable truth
Day40 recoverable message delivery (Lists / Pub-Sub / Streams)   <-- you are here
Day41 atomic composition, coordination, locks/leases + fencing, full rate limiting
Day42 the integrated data ownership + failure + recovery model
```

Knowledge continuity:

```text
Previous knowledge
  Day33/34 guarded transitions + stable idempotency identities (safe repeated side effects)
  Phase 3 Transactional Outbox + at-least-once + idempotent processing (Day28 architecture)
  Day39 PostgreSQL commit is authority; Redis is a projection that may be stale/absent
        |
        v
Current lesson
  Lists vs Pub/Sub vs Streams; Consumer Groups + PEL/ACK/Claim/redelivery; delivery != completion;
  per-side-effect idempotency; poison-message quarantine; safe trim; dual-crash recovery
        |
        v
Future production usage
  Day41 reuses "Redis transport != durable business truth" for atomic composition, rate limits, locks/leases,
        and fencing boundaries
  Day42 integrates PostgreSQL Job/Attempt/Event/Outbox facts, Redis cache/messages, Object Storage bytes,
        Worker recovery, degraded modes, reconciliation, and validation limits
```

Mental models reused by name: the Day33/34 guarded state transition and stable Provider idempotency identity
(now protecting against redelivered messages), the Phase 3 Transactional Outbox and at-least-once + idempotent
consumer model, and the Day39 "PostgreSQL commit is authority; Redis is a projection" boundary (now applied to
transport, not cache).

---

# Lesson Map

```text
1. Crash before ACK          -> a Pending entry is not proof of completion; PostgreSQL decides
2. At-least-once + idempotency-> persist a durable decision BEFORE XACK; early ACK = at-most-once loss
3. Pub/Sub vs Streams         -> Pub/Sub has no backlog/replay; Streams+Groups are recoverable
4. Events + Groups + ordering -> dispatch vs job.completed events; one message -> one consumer; transport order != completion order
5. Lists / payloads / Celery  -> Lists lack the recovery lifecycle; small references; don't rebuild Celery
6. Poison messages + retry    -> bounded retry -> quarantine -> alert -> repair -> controlled replay
7. Safe trim                  -> retention policy; never trim Pending / recovery evidence
8. Notification side effects  -> per-effect delivery identity; job_id alone is insufficient
9. Dual-crash recovery        -> preserve evidence -> inspect PG -> reconcile -> per-group Claim -> ACK
```

---

# Core Mental Model

```text
PostgreSQL = AUTHORITATIVE Job/Attempt/Event/Outbox/Notification-Delivery truth (a COMMIT is authority).
Redis Streams = RECOVERABLE transport. A delivery -- even an XACK -- is transport state, NOT business truth.

XREADGROUP -> entry in the group's PEL -> persist a durable processing decision in PostgreSQL -> XACK
XACK closes delivery responsibility for ONE group; it does not prove Provider/DB/email completion.
Crash BEFORE XACK -> entry stays PENDING -> XCLAIM/XAUTOCLAIM -> reconcile durable state -> XACK after decision.

at-most-once  = ACK before processing -> a crash silently LOSES the Job          (rejected)
at-least-once = process + persist, THEN ACK -> may REDELIVER -> safe with idempotency  (chosen)
Redis alone CANNOT give exactly-once across (Redis ACK + PostgreSQL commit + external Provider call).

one group -> one consumer per message (competing consumers); distinct lifecycle events -> distinct streams/groups
(Accept -> job-dispatch -> g:job-exec; Complete -> job.completed events -> g:notify-delivery). A completion
email is driven ONLY by a committed job.completed Outbox/Event, never by a dispatch entry.
payload = small references (tenant_id, job_id, event_id, trace); bytes in Object Storage, refs in PostgreSQL.
poison message -> bounded retry -> durable quarantine -> alert -> repair producer -> controlled replay.
trim = retention policy; NEVER trim Pending or recovery/quarantine evidence.
```

---

# Main Concepts

## Concept 1: A crash before ACK is not proof of completion

### Tech Lead Question

A Worker read a Stream message, may have done the business work, and crashed before `XACK`. Is the Job done?

### Student Thinking

The student reasoned from the transport state: no ACK means the task is still in the queue — while noticing the
work may actually have finished.

### Student Answer

> "视为已处理，因为没有ACK确认，任务还在queue中。但是实际上已经处理结束了"

### Tech Lead Review

The tension the student spotted is exactly the point, but the conclusion needs correcting: Redis does **not**
know whether the business effect completed. The entry is **Pending** in the Consumer Group's PEL and must
remain **recoverable** through Claim/redelivery. Whether the Job is actually done is decided by **PostgreSQL**
Job/Attempt/Event/Outbox/side-effect delivery records plus Provider reconciliation — not by the presence or
absence of an ACK. `XACK` closes delivery responsibility for one Consumer Group; it does not create business
truth. So the safe read is "unknown until reconciled," not "already processed."

### Engineering Thinking

Transport state answers "did the message get delivered/acknowledged," never "did the business effect happen."
Keep the entry recoverable and let the durable store arbitrate.

## Concept 2: At-least-once delivery and idempotent side effects

### Tech Lead Question

Should you `XACK` immediately when you receive the message, or after processing? What does each cost you?

### Student Thinking

The student traced what early ACK does to the PEL and connected delayed ACK to controlled, idempotent
redelivery.

### Student Answer

> "立刻XACK,redis内部就会删除work的PEL，这个时候崩溃了这条PEL就找不到了，就不会再有work执行这个job，属于at-most-once"

> "因为重投可以通过持久化状态结合幂等键进行可控投递，而提前ACK意味PEL提前被redis内部移除。如果这个时候PostgreSQL的状态也没有写入，就代表这条数据库的状态再也不会更新"

### Tech Lead Review

Both correct. ACKing **before** processing removes the group's recovery path (the PEL entry) and gives
**at-most-once** behaviour — a crash silently loses the Job. The right shape is to persist a **durable,
recoverable processing decision in PostgreSQL first**, then `XACK`, giving **at-least-once** delivery. Because
the Provider can succeed **before** PostgreSQL persistence or ACK, redelivery can repeat the message, so
duplicate side effects are prevented by **stable Attempt/Provider idempotency identities** plus **PostgreSQL
guarded state transitions** and **reconciliation** — not by Redis. The honest boundary: Redis alone cannot
provide exactly-once across Redis ACK, the PostgreSQL commit, and the external Provider call.

### Engineering Thinking

Prefer safe redelivery over silent loss: at-least-once + idempotency is recoverable; at-most-once is not.
Exactly-once is a property you engineer with durable state and idempotency, not a Redis feature.

## Concept 3: Pub/Sub versus Streams

### Tech Lead Question

Could you dispatch background Jobs over Pub/Sub instead of Streams?

### Student Thinking

The student reasoned about what happens to a subscriber that is offline or crashes when a message is published.

### Student Answer

> "因为pub/sub只是做广播。并不负责对方是否收到，如果sub在pub发送消息之后，崩溃了没有收到消息，重新上线之后也不会找回pub发送的消息"

### Tech Lead Review

Correct. Pub/Sub is **live broadcast** with **no** durable backlog, ACK, PEL, Claim, or replay — a subscriber
that is offline or crashes when a message is published **permanently misses** it. That makes Pub/Sub suitable
only for **loss-tolerant live notifications** (a dashboard tick), never for recoverable Job dispatch. **Streams
Consumer Groups** provide the recoverable delivery background work needs.

### Engineering Thinking

Choose the primitive by its failure semantics: if a missed message must be recoverable, Pub/Sub is disqualified
before any other consideration.

## Concept 4: Consumer Groups and ordering

### Tech Lead Question

Two things care about a Job event — the executor and the notifier. Put them in one group? And does Stream order
guarantee the order business effects complete?

### Student Thinking

On grouping, the student saw the hazard of one service racing ahead of another and reached for the database as
the guard. On ordering, the student answered directly that it cannot be guaranteed.

### Student Answer

> "会发生一个work已经发送用户通知的服务，而执行 Job 的 Worker还在处理。应该用数据库中持久化的事实拦住。"

> "不能保障"

### Tech Lead Review

The ordering answer is correct: Stream append order is **transport** order, and concurrent consumers do **not**
guarantee business-effect completion order — **PostgreSQL guarded state transitions** and **idempotency**
preserve business validity under concurrent/out-of-order processing. The student's grouping instinct — that a
notifier could fire while the executor is still working, and that the database's committed fact must gate it —
is exactly right, and it points past a common half-fix. Separate Consumer Groups only solve "two groups can
each **receive** the same Stream entry"; within **one** group a message goes to **one** consumer (competing
consumers). But separate groups do **not** turn a **dispatch** entry into a **completion** event: a
`job-dispatch` event is emitted at **Accept**, when the Job is not finished, so a completion email must never be
derived from it. The correct structure is distinct **committed events at distinct lifecycle points**, published
by the Relay from PostgreSQL Outbox intents (Day33): the **Accept** transaction commits a `job-dispatch` intent
→ `ai:stream:job-dispatch:v1` → `g:job-exec`; the **Complete** transaction commits a `job.completed` intent →
`ai:stream:job-events:v1` (or one shared event stream with an explicit `event_type`) → `g:notify-delivery`. The
completion notification is driven **only** by a committed `job.completed` Outbox/Event — the student's "用数据库
中持久化的事实拦住" — never by an accept/dispatch entry. A Redis delivery is still not business truth, and
Provider and email each keep their own stable idempotency identity.

### Engineering Thinking

Separate groups for separate effects; rely on guarded transitions and idempotency for correctness, not on
message arrival order.

## Concept 5: Lists, Stream payloads, and the Celery boundary

### Tech Lead Question

Why not build the queue from raw Lists? And what belongs in a Stream message when a Job produces a 300 MB PDF?

### Student Thinking

The student identified the missing lifecycle in Lists and the memory cost of large payloads.

### Student Answer

> "list缺少streams持久化保存信息的机制"

> "object storage保存大文档，stream保存大文档会造成内存压力增大"

### Tech Lead Review

Right on both, with one precision. Lists **can** be Redis-persisted; their real gap versus Streams is native
**Consumer Group ownership, PEL, ACK, Claim, and redelivery** semantics — persistence is not a consumer
recovery lifecycle. So do **not** hand-build a Celery replacement from raw Lists/Streams. On payloads: keep
Stream messages to **small references** (`tenant_id`, `job_id`, `event_id`, trace metadata); **Object Storage**
owns the 300 MB PDFs and result bytes, and **PostgreSQL** owns the durable artifact references/provenance. Large
payloads in messages inflate memory, replication, and redelivery cost.

### Engineering Thinking

Use Streams for the recovery lifecycle Lists lack, keep messages tiny and reference-only, and use a real broker
(Celery) as a broker rather than reimplementing one.

## Concept 6: Poison messages and retry classification

### Tech Lead Question

A message keeps failing. When do you stop retrying, and is a retry limit proof the error is permanent? What
about a fixed payload that is missing a required `tenant_id`?

### Student Thinking

The student saw the cost of endless retries (held connections) and reached for "contain first," treated the
retry limit as a stopping signal, and initially read the missing-field failure as transient.

### Student Answer

> "会造成redis一直处于重试状态，一直占用连接。我觉得应该先contain，再删除"

> "不能，因为有一个重试上限"

> "瞬时错误，我会修复后重试"

### Tech Lead Review

The instinct to **contain** before acting is right, but the details need correcting. Bounded retry is for
**plausibly transient** failure; a retry **limit** is a capacity/containment policy, **not** proof of a
permanent root cause, and it is **not** an error classifier. A fixed, immutable payload missing required
`tenant_id` is normally a **permanent message-contract failure**: retrying the identical message can never
repair it. The correct path is bounded retry → **durable quarantine/dead-letter evidence** → **alert** →
repair the **producer/contract** → **controlled replay** of a corrected message. And "then delete" must become
"ACK the original **only after durable quarantine evidence exists**" — never silently delete a failed Job
message.

### Engineering Thinking

Classify by error evidence and message-contract semantics, not by retry count. Containment means durable
quarantine + alert, not deletion.

## Concept 7: Safe trimming

### Tech Lead Question

Memory is under pressure. Can you just trim the Stream to reclaim it?

### Student Thinking

The student named the consequence of an unsafe trim directly.

### Student Answer

> "破坏重放能力"

### Tech Lead Review

Correct — an unsafe trim **destroys Claim/redelivery/replay** capability. Trimming (`XTRIM`/`MAXLEN`) is a
**capacity/retention policy**, not blind deletion under memory pressure. Never trim **pending** messages or
**recovery/quarantine** evidence before the Consumer Group, retry, and retention contracts permit it —
trimming those deletes exactly the evidence recovery depends on.

### Engineering Thinking

Retention is a contract, not a memory-pressure reflex. Protect Pending and recovery evidence until their
retention terms allow removal.

## Concept 8: Notification side effects need their own delivery identity

### Tech Lead Question

Job completion fires a completion email. Can you decide "already sent?" from the Job's Attempt/Event plus one
`job_id` idempotency key?

### Student Thinking

The student proposed checking durable Attempt/Event plus an idempotency key to decide whether the email was
already sent.

### Student Answer

> "根据数据库持久化attempt与event结合幂等键判断是否已经发送邮件"

### Tech Lead Review

Checking durable state before repeating a side effect is the right reflex, but a Job **Attempt/Event does not
prove an email was delivered** — notification delivery needs its **own** durable delivery identity/record. And
one `job_id` cannot be the only idempotency key, because completion, failure, and admin-alert notifications are
**separate** effects. Use a **delivery-specific** key per effect, for example
`job:{job_id}:notification:completion:v1`. The completion notification is triggered only by a committed
`job.completed` event (published by the Relay from the Complete transaction's Outbox intent, consumed by
`g:notify-delivery` on the events stream) — not by the accept/dispatch entry — so "Job completion does not
prove email delivery" is enforced structurally: the email has its own committed trigger and its own delivery
fact.

### Engineering Thinking

Every distinct side effect gets its own durable delivery record and idempotency key. Reusing `job_id` collapses
independent effects into one and hides missed or duplicated deliveries.

## Concept 9: Integrated dual-crash recovery

### Tech Lead Question

The Job Worker and the notification Consumer both crashed after their external calls but before `XACK`; both
messages are Pending. An operator wants to aggressively trim the Stream and re-send every Job. What do you do?

### Student Thinking

This is the integrated exercise; it combines the crash-before-ACK, idempotency, per-group Claim, and safe-trim
reasoning from the whole lesson.

### Student Answer

The student's per-part answers above compose the recovery: inspect PostgreSQL Attempt/Event with idempotency
keys before re-calling the Provider, contain rather than delete, and preserve replay capability rather than
trim it away.

### Tech Lead Review

The recovery sequence: **preserve evidence** (do not trim Pending or quarantine/recovery evidence); **inspect
PostgreSQL** Job/Attempt/Event/Outbox/Notification-Delivery facts; **reconcile** Provider and email outcomes
using stable ids; each **group Claims its own Pending** entries independently; and **ACK only after** the
recovered durable decision. Explicitly do **not** blindly rerun all Jobs, blindly repeat Provider/email calls,
silently delete messages, or aggressively trim Pending recovery evidence. The operator's "trim and re-send
everything" is precisely the destructive move to refuse.

### Engineering Thinking

Recovery is evidence-first: reconcile durable truth, let each group recover its own Pending, and ACK once the
durable decision is known — never mass-rerun or mass-trim.

---

# Common Misconceptions

Unacknowledged delivery

❌ "No ACK means the task hasn't run, so it's safe to re-run; an ACK means the business is done."
✅ A Pending entry proves neither. Redis transport state cannot prove Provider/Job completion; PostgreSQL and
reconciliation can. `XACK` closes transport responsibility for one group, not a business transaction.

Why beginners think this: ACK feels like "committed."
How to remember: ACK is transport confirmation, not business truth.

ACK timing

❌ "ACK as soon as you receive the message so it isn't redelivered."
✅ Early ACK removes the PEL recovery path and gives at-most-once (a crash loses the Job). Persist a durable,
recoverable processing decision first, then `XACK`.

Why beginners think this: early ACK looks like it avoids duplicates.
How to remember: never `XACK` before a durable, recoverable decision.

Retry count as a classifier

❌ "It hit the retry limit, so the error is permanent" / "it failed, so it's transient — just retry."
✅ A retry limit is a capacity-containment policy, not an error classifier. Classify by error evidence and
message-contract semantics.

Why beginners think this: the counter is the most visible signal.
How to remember: bounded retries protect capacity; evidence classifies the error.

Self-healing bad payloads

❌ "Retrying the message enough times will fix it."
✅ A fixed immutable payload missing a required field is a permanent contract failure. Quarantine, repair the
producer/contract, and controlled-replay a corrected message.

Why beginners think this: retries fix transient faults, so "more retries" feels stronger.
How to remember: you can't retry your way out of a bad contract.

Lists as a queue

❌ "A persisted List is basically a durable work queue."
✅ List persistence is not a consumer recovery lifecycle. Streams add Consumer Group, PEL, ACK, Claim, and
redelivery; don't hand-build a Celery replacement from raw Lists.

Why beginners think this: a List survives a restart, so it looks durable enough.
How to remember: persistence ≠ recovery lifecycle.

One group as broadcast

❌ "Put every consumer in one group and they all get the message."
✅ Within one group a message goes to one consumer. Independently interested effects need their own groups, and
distinct lifecycle effects (dispatch vs completion) are driven by distinct committed events — a completion email
comes from a committed job.completed event, never from a dispatch entry.

Why beginners think this: "group" sounds like "everyone in the group."
How to remember: one group = competing consumers; separate effects = separate groups.

Trim as cleanup

❌ "Under memory pressure, trim the Stream."
✅ Trim is a retention/capacity contract. Never trim Pending or recovery/quarantine evidence before its
retention contract permits — it destroys Claim/redelivery/replay.

Why beginners think this: trimming is the obvious way to reclaim memory.
How to remember: trimming Pending deletes your recovery evidence.

One idempotency key for everything

❌ "Use `job_id` as the idempotency key for completion, failure, and admin emails."
✅ They are separate side effects; each needs its own delivery identity (e.g.
`job:{job_id}:notification:completion:v1`). Job completion does not prove email delivery.

Why beginners think this: one Job feels like one thing.
How to remember: one effect, one delivery identity.

Exactly-once from Redis

❌ "Streams give exactly-once processing."
✅ Redis alone cannot provide exactly-once across Redis ACK, PostgreSQL commit, and an external Provider call.
Use at-least-once + idempotency + reconciliation.

Why beginners think this: ACK + no redelivery looks like exactly-once.
How to remember: exactly-once is engineered with durable state + idempotency, not provided by Redis.

---

# Engineering Trade-offs

## At-most-once vs at-least-once

At-most-once (ACK before processing) never redelivers but silently loses work on a crash. At-least-once
(persist, then ACK) may redeliver but loses nothing, and redelivery is made safe with idempotency. For Job
dispatch, at-least-once + idempotency is the correct default; at-most-once is acceptable only for genuinely
loss-tolerant signals.

## Pub/Sub vs Streams

Pub/Sub is cheap live broadcast with no backlog, ACK, or replay — great for loss-tolerant notifications and
useless for recoverable dispatch. Streams add per-group PEL/ACK/Claim/redelivery at higher complexity and
memory cost. Choose by whether a missed message must be recoverable.

## Lists vs Streams for a queue

A List is a simple, low-overhead FIFO but has no ownership, PEL, ACK, or redelivery. A Stream Consumer Group
provides the full recovery lifecycle at more moving parts. Use a List only when loss/redelivery is handled
elsewhere; use Streams when the consumer must recover in-flight work.

## Build on Redis primitives vs use a broker (Celery)

Raw Streams give you control and a small dependency surface but require you to build retry, quarantine,
dead-letter, and reconciliation yourself. A broker like Celery provides those but adds its own operational
surface. This lesson teaches the semantics on Streams; it does not hand-build a Celery replacement, and a
production system should use a real broker as a broker.

## Bounded retry vs immediate quarantine

More retries recover more transient faults but hold capacity and delay detection of permanent failures.
Immediate quarantine frees capacity and surfaces the problem faster but can quarantine a merely-transient
blip. Bound the retries for transient faults, and quarantine (with durable evidence + alert) once the error
evidence or a contract failure says retrying is futile.

## Aggressive trim vs retention contract

Aggressive trimming reclaims memory immediately but can delete Pending and recovery evidence, destroying
replay. A retention contract keeps recovery evidence until it is safe to remove, at the cost of holding more
data. Never let memory pressure override the recovery contract; size retention deliberately.

## Per-effect idempotency keys vs one job_id

One `job_id` key is simpler but conflates completion, failure, and admin notifications and hides missed or
duplicated deliveries. Per-effect delivery identities cost a little more bookkeeping and make each side
effect independently idempotent and observable. Use per-effect identities for anything with real-world side
effects.

---

# Hands-on Exercises

Design/paper only. Nothing here was executed against a live Redis, PostgreSQL, Celery, Provider, or email
Provider; treat every snippet as a design artifact.

### Exercise 1: Diagnose a crash after delivery but before ACK

Question: a Worker read a message, may have called the Provider, and crashed before `XACK`. What is the state
and what decides completion?

Think First: what does Redis know, and what does it not know?

Expected Output: the entry is Pending in the group's PEL and must remain recoverable; PostgreSQL Job/Attempt/
Event/Outbox + Provider reconciliation decide completion — not the missing ACK.

Explanation: transport state cannot prove a business effect.

Follow-up Question: which command recovers the Pending entry, and when do you finally `XACK`?

### Exercise 2: Pub/Sub vs Streams for recoverable dispatch

Question: could Pub/Sub dispatch these Jobs? Justify.

Expected Output: no — Pub/Sub has no backlog/ACK/PEL/Claim/replay, so an offline/crashed subscriber
permanently misses the message; use Streams Consumer Groups.

Explanation: recoverability disqualifies Pub/Sub before anything else.

Follow-up Question: what is Pub/Sub actually appropriate for here?

### Exercise 3: Early-ACK loss vs delayed-ACK redelivery

Question: contrast ACK-before-processing with persist-then-ACK on a timeline through a crash.

Expected Output:

```text
EARLY ACK:  XACK -> PEL removed -> crash -> no recovery path -> Job silently LOST (at-most-once)
DELAYED:    process + persist durable decision -> XACK -> crash before ACK -> Pending -> Claim -> reconcile (at-least-once)
```

Explanation: at-least-once + idempotency is recoverable; at-most-once is not.

Follow-up Question: what makes the redelivered message safe to process again?

### Exercise 4: Why concurrent consumers don't guarantee completion order

Question: two consumers process appended messages concurrently. Does append order equal business-completion
order?

Expected Output: no — append order is transport order; concurrent processing completes out of order. PostgreSQL
guarded transitions + idempotency preserve validity.

Explanation: correctness comes from guarded writes, not arrival order.

Follow-up Question: where does a guarded transition reject an out-of-order effect?

### Exercise 5: Poison-message retry → quarantine → replay (design judgment)

Question: a fixed payload missing `tenant_id` keeps failing. Design the handling.

Expected Output: bounded retry → durable quarantine/dead-letter evidence → alert → repair producer/contract →
controlled replay of a corrected message; `XACK` the original only after durable quarantine evidence exists;
never silently delete.

Explanation: a bad immutable contract cannot be retried into success.

Follow-up Question: why is the retry limit not proof the error is permanent?

### Exercise 6: Recovery capability destroyed by unsafe trimming

Question: name what an aggressive `XTRIM` under memory pressure can destroy.

Expected Output: Pending entries and recovery/quarantine evidence — i.e. Claim/redelivery/replay capability.

Explanation: trim is a retention contract, not memory cleanup.

Follow-up Question: what must the retention contract protect before a trim is allowed?

### Exercise 7: Dispatch vs completion event topology

Question: design the event/group topology so Job execution runs at dispatch and completion emails fire only when
the Job actually completes.

Expected Output: the Accept transaction commits a `job-dispatch` Outbox intent → Relay → `ai:stream:job-dispatch:v1`
→ `g:job-exec`; the Complete transaction commits a `job.completed` Outbox intent → Relay → `ai:stream:job-events:v1`
(or one shared event stream with an explicit `event_type`) → `g:notify-delivery`; each group has its own
PEL/ACK/Claim and one message → one consumer within a group.

Explanation: separate groups only mean both could receive the same entry; a completion email must be driven by a
committed `job.completed` event, never by a dispatch entry.

Follow-up Question: why can't `g:notify-delivery` just read the dispatch stream and send the email?

### Exercise 8: Recover dual consumer crashes after external calls but before ACK (reusable artifact)

Question: both the Job Worker and notification Consumer crashed post-external-call, pre-`XACK`; both Pending. An
operator wants to trim and re-send everything. Give the recovery sequence.

Expected Output: preserve evidence → inspect PostgreSQL Job/Attempt/Event/Outbox/Notification-Delivery →
reconcile Provider/email by stable ids → each group Claims its own Pending → ACK after the recovered durable
decision. Do not blindly rerun/repeat/delete/trim. This maps to the artifact's failure/recovery matrix.

Explanation: evidence-first recovery, per-group Claim, ACK after durable decision.

Follow-up Question: which four actions are explicitly forbidden?

---

# Relevant Framework Connections

## PostgreSQL

PostgreSQL holds the Job/Attempt/Event/Outbox/Notification-Delivery facts and the guarded transitions that
decide business completion. Watch that a message is `XACK`ed only after a durable, recoverable decision is
persisted, and that redelivery reconciles against durable state rather than repeating side effects.

## Redis (Streams / Consumer Groups / Pub-Sub / Lists)

Redis provides the transport primitives — Streams with per-group PEL/ACK/Claim/redelivery and trimming,
Pub/Sub for live broadcast, and Lists for simple queues. Watch that Pub/Sub is never used for recoverable
dispatch, that trims never remove Pending/recovery evidence, and that no code treats a delivery or ACK as
business truth.

## Worker / Celery boundary

The Worker consumes Stream messages and drives the Job, but the lesson stops at understanding the transport
semantics — it does **not** hand-build a Celery replacement from raw Lists/Streams. A production system uses a
real broker as a broker; watch for teams reinventing retry/dead-letter/reconciliation badly.

## Provider and email Provider

External Providers (model calls, email) are expensive and side-effectful, so each needs a stable, per-side-
effect idempotency identity and reconciliation. Watch that a redelivered message never blindly repeats a
Provider or email call, and that completion, failure, and admin notifications carry distinct delivery
identities.

## Object Storage

Object Storage owns the large bytes (300 MB PDFs, result Artifacts); Stream messages carry only references and
PostgreSQL owns the durable references/provenance. Watch for large payloads leaking into messages and inflating
memory/replication/redelivery cost.

---

# AI Backend Connections

## Long-running AI Job dispatch

Model Jobs are dispatched with small Stream payloads carrying tenant/Job/event references; the Worker loads
metadata from PostgreSQL and bytes from Object Storage. A Pending message after a crash means "reconcile,"
never "silently lost" or "blindly re-run" — the eight-minute model call is too expensive to repeat blindly.

## Expensive Provider calls under redelivery

Because at-least-once delivery can redeliver, an expensive model Provider call must be guarded by a stable
idempotency identity + PostgreSQL reconciliation so a redelivered message does not pay twice. This is the
Day33/34 idempotency contract applied to transport redelivery.

## Separate notification effects

Completion, failure, and admin-alert notifications are separate side effects with separate delivery identities
(e.g. `job:{job_id}:notification:completion:v1`). "The Job succeeded" never implies "the completion email was
delivered" — the email has its own durable delivery record.

## Large artifacts stay in Object Storage

Generated PDFs and result Artifacts remain in Object Storage with durable references/provenance in PostgreSQL;
the Stream carries references only. Putting result bytes in a message is a Day38/Day40 anti-pattern (memory,
replication, and redelivery cost).

---

# English Interview

## Key Vocabulary

Stream, Consumer Group, Pending Entries List (PEL), `XADD` / `XREADGROUP` / `XACK` / `XCLAIM` / `XAUTOCLAIM` /
`XTRIM`, Pub/Sub, List, at-most-once, at-least-once, exactly-once, idempotent consumer, redelivery, poison
message, dead-letter / quarantine, trimming / retention, delivery identity, reconciliation.

## Useful Expressions

"A delivery is not proof of completion." · "Persist a durable decision, then `XACK`." · "At-least-once plus
idempotency, never exactly-once from Redis." · "One group, one consumer per message; separate effects, separate
groups." · "You can't retry your way out of a bad message contract."

## Beginner Question — What is the difference between Redis Pub/Sub and Streams?

Strong answer:

> "Pub/Sub is live broadcast with no durable backlog, ACK, or replay, so a subscriber that is offline or
> crashes when a message is published permanently misses it — it is only for loss-tolerant live notifications.
> Redis Streams with Consumer Groups retain a backlog (subject to configured persistence and failover loss
> windows) and a per-group Pending Entries List with ACK and
> Claim, so a crashed consumer's message stays recoverable. For recoverable background Job dispatch I use
> Streams, not Pub/Sub."

## Intermediate Question — A Worker crashes after calling the Provider but before `XACK`. What happens, and how do you avoid losing or duplicating work?

Strong answer:

> "The entry stays Pending in the group's PEL, and Redis cannot know whether the Provider call or the database
> write happened. I never ACK before processing, because that would be at-most-once and a crash would silently
> lose the Job. Instead I persist a durable, recoverable decision in PostgreSQL, then `XACK` — at-least-once.
> Another consumer can `XCLAIM` the Pending entry, reconcile against PostgreSQL Attempt/Event using a stable
> idempotency key, and only then decide whether to repeat the side effect. Redis alone can't give exactly-once
> across ACK, the database commit, and the Provider call."

## Senior Question — Design safe handling for poison messages and Stream retention in a Job pipeline.

Strong answer:

> "Bounded retry only for plausibly transient failures — the retry limit is a capacity policy, not proof the
> error is permanent, and not an error classifier. A fixed payload missing a required field is a permanent
> contract failure, so I move it to durable quarantine/dead-letter with failure evidence, alert, repair the
> producer or contract, and controlled-replay a corrected message; I `XACK` the original only after quarantine
> evidence exists and never silently delete it. For retention, trimming is a capacity/retention contract, not
> memory cleanup: I never trim Pending entries or recovery/quarantine evidence before the group, retry, and
> retention contracts allow it, because that destroys Claim, redelivery, and replay. And each notification
> effect — completion, failure, admin — gets its own delivery identity, because a Job Attempt/Event does not
> prove an email was sent."

## Common Weak Answer

"Redis Streams give exactly-once delivery, so ACK the message and you're done; if memory is tight, trim the
stream."

## Strong Answer

"Redis gives at-least-once with Consumer Groups, not exactly-once — exactly-once across ACK, the PostgreSQL
commit, and an external Provider call is engineered with durable state, guarded transitions, and per-side-
effect idempotency. I `XACK` only after a durable decision, recover Pending entries with Claim and
reconciliation, quarantine poison messages instead of deleting them, and treat trimming as a retention
contract that must never remove Pending or recovery evidence."

---

# Mental Model Summary

```text
1.  PostgreSQL = authoritative Job/Attempt/Event/Outbox/Notification truth; a COMMIT is authority.
2.  A Redis Stream delivery -- even an XACK -- is transport state, NOT business completion.
3.  Crash before XACK -> entry stays Pending in the PEL -> must remain recoverable via Claim/redelivery.
4.  Persist a durable, recoverable decision BEFORE XACK. Early ACK = at-most-once = silent loss.
5.  At-least-once + idempotency is the default; Redis alone gives NO exactly-once across ACK+commit+Provider.
6.  Pub/Sub = live broadcast, no backlog/ACK/PEL/Claim/replay -> only loss-tolerant notifications.
7.  Streams + Consumer Groups = recoverable delivery for background work.
8.  One group -> one consumer per message; distinct lifecycle events -> distinct streams/groups (Accept ->
    job-dispatch -> g:job-exec; Complete -> job.completed -> g:notify-delivery); completion email is driven
    ONLY by a committed job.completed event, never by a dispatch entry.
9.  Stream append order = transport order; concurrent consumers do NOT guarantee completion order.
10. Lists may persist but lack Consumer Group / PEL / ACK / Claim / redelivery; don't hand-build Celery.
11. Payloads are small references; Object Storage owns bytes, PostgreSQL owns references/provenance.
12. Retry limit = capacity policy, NOT an error classifier; a bad immutable contract cannot self-heal.
13. Poison path: bounded retry -> durable quarantine/dead-letter -> alert -> repair producer -> controlled replay.
14. Trim = retention contract; NEVER trim Pending or recovery/quarantine evidence.
15. Each side effect (completion/failure/admin) needs its OWN delivery identity; job_id alone is insufficient.
16. Dual-crash recovery: preserve evidence -> inspect PostgreSQL -> reconcile -> per-group Claim -> ACK after decision.

Starting model -> reasoning -> correction -> final model:
Initial: no ACK means the task is still queued (and might be re-run); an ACK means it is done; retry until it works.
Reasoning: the student saw that unacknowledged work may actually have completed, that early ACK removes the PEL
recovery path, that Pub/Sub cannot recover an offline subscriber, and that unsafe trim breaks replay.
Correction: transport state is not business truth; ACK closes delivery for one group, not the business; a retry
limit is containment, not classification; a bad contract cannot be retried into success; distinct lifecycle
events drive distinct effects on distinct streams/groups (a completion email comes from a committed
job.completed event, never a dispatch entry), each with its own delivery identity.
Final: PostgreSQL decides completion; Redis Streams provide recoverable at-least-once transport; idempotency +
guarded transitions + reconciliation make redelivery safe; poison messages are quarantined and replayed after
repair; trimming respects a retention contract; Redis alone never provides exactly-once.
```

---

# Today's Takeaway

Redis messaging is recoverable transport, not business truth. Use Streams with Consumer Groups for recoverable
Job dispatch, persist a durable decision before you `XACK`, and make at-least-once redelivery safe with stable
per-side-effect idempotency and PostgreSQL reconciliation — never claim exactly-once from Redis and never
hand-build a Celery replacement.

Most important mental model: a delivery (or ACK) is transport state; PostgreSQL decides business completion.
Most important production risk: early ACK losing a Job, a blindly-repeated Provider/email call after
redelivery, or an aggressive trim destroying recovery evidence. Most important trade-off: at-most-once loss vs
at-least-once redelivery (choose at-least-once + idempotency). Most important connection: a redelivered message
must reconcile against durable state before repeating an expensive Provider call. Most important interview
answer: persist a durable, recoverable decision before `XACK`, and recover Pending entries with Claim +
reconciliation.

Validation status: this lesson is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT
VALIDATED. No Redis, Streams, Consumer Groups, `XACK`, Claim, trim, Pub/Sub, PostgreSQL, Celery, Provider, or
email integration was executed. Atomic composition/coordination/locks-leases/rate limiting (Day41) and the
integrated model (Day42) are future boundaries.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain the core mental model — a delivery/ACK is transport state, PostgreSQL decides completion — in plain English?
- [ ] Can I explain why an unacknowledged (Pending) entry is not proof the Job ran or was lost?
- [ ] Can I identify the at-most-once vs at-least-once trade-off and why I persist a durable decision before XACK?
- [ ] Can I say why Pub/Sub cannot do recoverable Job dispatch and Streams+Groups can?
- [ ] Can I design distinct Consumer Groups for Job execution and notification delivery?
- [ ] Can I classify a poison message and design retry -> quarantine -> alert -> repair -> controlled replay?
- [ ] Can I state why trimming Pending/recovery evidence destroys Claim/redelivery/replay?
- [ ] Can I give each notification effect its own delivery identity instead of reusing job_id?
- [ ] Can I recover dual consumer crashes with evidence preservation, PostgreSQL inspection, reconciliation, per-group Claim, and ACK-after-decision?
- [ ] Can I explain, in English, why Redis alone cannot provide exactly-once across ACK, commit, and Provider?
```

Preparation for Day41 (Redis Coordination and Production Safety): review this lesson's transport-vs-truth
boundary and the `redis/redis-messaging-and-queue-semantics-design.md` artifact, then preview atomic command vs
multi-command race, transactions/Lua only where atomic composition is required, rate-limit algorithms, and
lock vs lease with an ownership/fencing token. Keep SQLAlchemy/Alembic (Phase 4) out of scope.

---

Engineering Artifact: [projects/ai-backend-data-layer/redis/redis-messaging-and-queue-semantics-design.md](../../projects/ai-backend-data-layer/redis/redis-messaging-and-queue-semantics-design.md)
