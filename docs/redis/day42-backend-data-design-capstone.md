# Lesson 42 — Backend Data Design Capstone

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 8-9 hours

Prerequisite: Day41 — Redis Coordination and Production Safety

Previous Lesson: [Day41 — Redis Coordination and Production Safety](day41-redis-coordination-and-production-safety.md)

Next Lesson: Day43 — AI Backend Product Contract and FastAPI Request Lifecycle (planned — Phase 4; see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day43 lesson file does not exist yet)

Engineering Artifact: The Day42 Backend Data Design Capstone (`projects/ai-backend-data-layer/capstone-backend-data-design.md`) — the integrated ownership/lifecycle map, acceptance contract, dispatch/duplicate handling, completion + Artifact reconciliation, failure/degraded matrix, upload contract, tenant isolation/audit/retention model, performance-evidence method, fencing-generation migration, and integrated recovery runbook, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

PostgreSQL Cheat Sheet: [cheat_sheets/postgresql.md](../../cheat_sheets/postgresql.md)

Redis Cheat Sheet: [cheat_sheets/redis.md](../../cheat_sheets/redis.md)

PostgreSQL Interview: [interview/postgresql.md](../../interview/postgresql.md)

Redis Interview: [interview/redis.md](../../interview/redis.md)

Estimated Study Time:

```text
Reading: 160-190 minutes
Exercises: 110-140 minutes
Hands-on integrated ownership/failure/recovery design: 110-140 minutes
Review: 30-45 minutes

Total: 8-9 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. State the integrated ownership map — PostgreSQL durable truth, Object Storage large bytes, Redis transient/losable coordination — and place Upload Session, Document, Job, Attempt, Event, Outbox, Result Artifact, cache, messages, and counters on it.
2. Define the acceptance contract: what must be durable at `202` (Job + `(tenant_id, idempotency_key)` uniqueness + Outbox intent) and what need not exist yet (Attempt, Event, lease token, fencing generation).
3. Drive dispatch from unpublished Outbox intents, and treat at-least-once duplicate delivery as normal, rejecting duplicate business effect with a PostgreSQL guarded transition rather than a Redis marker.
4. Design a short guarded completion transaction and reconcile an Artifact-first write, verifying identity/integrity, current ownership + fencing equality, and Provider/result evidence before completing.
5. Choose degraded behaviour for Redis, PostgreSQL, and Object Storage failures, failing closed only on the affected admission path without stopping unrelated healthy capability.
6. Verify an Upload Session before Job admission (tenant ownership, verified state, non-expiry, registered key, hash/size, content-type/scanning).
7. Design tenant-safe reads and relationships (authenticated tenant predicate + composite tenant-aware foreign keys) and an immutable audit/retention trail (append-only Events, tombstoned Artifact references).
8. Distinguish conceptual design, static review, disposable `EXPLAIN ANALYZE` evidence, and production validation, and describe the performance-evidence method without claiming a run.
9. Plan the `current_fencing_generation` rollout with Expand→Contract, draining/upgrading old Workers rather than shortening a lease to force takeover.
10. Solve the integrated Redis-failover + paused-Worker + Artifact-reconciliation recovery scenario without blindly re-calling the Provider or using Artifact existence as ownership proof.
11. Answer Beginner/Intermediate/Senior English system-design interview questions on the integrated data model.

---

# Why This Matters

This is the Phase 3 capstone: the day the durable PostgreSQL truth (Day29-Day37) and the transient Redis
coordination (Day38-Day41) stop being separate lessons and become **one** failure-aware contract. The
platform is concrete — a multi-tenant AI Research and Automation Platform where a tenant uploads a Document
and submits `POST /jobs`, PostgreSQL accepts Job + Outbox before `202`, a Relay publishes a dispatch intent,
Workers claim and call an expensive Provider, large results land in Object Storage, and PostgreSQL records the
final state. Every earlier failure mode reappears at once: Redis message loss, duplicate Relay publication, a
paused Worker A and a takeover Worker B, Artifact-first completion, a PostgreSQL outage, an Object Storage
outage, tenant isolation, retention, performance evidence, and a fencing-generation rollout.

The reason this matters is that a real AI backend fails on the seams between systems, not inside any one of
them. A cache miss is fine; treating a missing Redis counter as proof of quota headroom is a cost incident. A
duplicate delivery is fine; treating it as an error instead of guarding the state transition duplicates an
expensive model call. An Artifact in Object Storage is fine; treating its existence as "the Job succeeded" ships
an unverified result. The capstone's job is to make the boundaries explicit: what is durable at acceptance, who
may complete a Job, how each subsystem degrades, how tenants stay isolated, how audit stays immutable, and how
recovery reconciles rather than guesses.

Everything here is conceptual design and static reasoning over one evolving scenario. Nothing was executed —
no PostgreSQL, Redis, Object Storage, Provider, Celery/Relay/Worker, FastAPI, migration, `EXPLAIN ANALYZE`, or
failover/load/security test — and the artifact is labelled that way. SQLAlchemy and Alembic are Phase 4 and are
only named as future connections.

---

# Roadmap Position

```text
Day29-Day37 durable PostgreSQL facts, SQL, transactions, concurrency, indexes, safe migration, reliability
Day38-Day41 Redis cache, messaging, rate limits, leases, fencing, operational safety
Day42 the Phase 3 CAPSTONE: integrate all boundaries into one ownership/recovery/verification contract  <-- you are here
Day43+ Phase 4 turns this contract into a runnable FastAPI AI backend (SQLAlchemy/Alembic later)
```

Knowledge continuity:

```text
Previous knowledge
  Day33 Accept transaction + Outbox; Day34 guarded claim + lease ownership; Day36 Expand->Contract migration;
  Day37 reliability/degraded modes; Day39 cache consistency; Day40 delivery semantics; Day41 fencing + guard
        |
        v
Current lesson
  one integrated ownership/lifecycle map + acceptance contract + dispatch/duplicate + completion/Artifact
  reconciliation + failure/degraded matrix + tenant/audit/retention + performance-evidence method + fencing
  migration + integrated recovery
        |
        v
Future production usage
  Day43 exposes this contract as the FastAPI AI Job HTTP lifecycle; Day44 typed Pydantic contracts; Day46-48
  map/persist/evolve THIS model with SQLAlchemy/Alembic WITHOUT changing ownership
```

Mental models reused by name: the Day33 Accept transaction + Transactional Outbox, the Day34 guarded
`queued -> running` claim and lease ownership, the Day36 Expand→Backfill→Validate→Switch→Contract migration,
the Day37 bounded degraded modes, the Day39 cache-vs-truth boundary, the Day40 at-least-once delivery, and the
Day41 durable fencing generation + completion guard.

---

# Lesson Map

```text
1. Ownership + acceptance      -> what PostgreSQL/Object Storage/Redis own; what is durable at 202
2. Dispatch + duplicate        -> Outbox-driven publish; at-least-once duplicates; guarded transition
3. Completion + Artifact        -> short guarded tx; verify identity + ownership/fencing + result
4. Failure priority + degraded  -> Redis / PostgreSQL / Object Storage failures, scoped fail-closed
5. Upload/document contract     -> verify session before admission
6. Tenant isolation + audit + retention -> tenant predicate + composite FKs; append-only; tombstones
7. Performance + migration      -> disposable EXPLAIN ANALYZE method; fencing Expand->Contract
8. Integrated recovery          -> failover + paused Worker + Artifact reconciliation
```

---

# Core Mental Model

```text
PostgreSQL = the SINGLE SOURCE OF DURABLE TRUTH (Job/Attempt/Event/Outbox/fencing/references + tenant + idempotency).
Object Storage = large Document/result BYTES (deterministic keys); PostgreSQL owns their references + verification.
Redis = TRANSIENT coordination/acceleration (cache/messages/counters/leases); LOSABLE; never proof of anything durable.

Durable at 202 = Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent. (Attempt/Event/lease/fencing come later.)
Dispatch = publish UNPUBLISHED Outbox intents; at-least-once DUPLICATES are normal; a guarded transition (one
queued->running) rejects duplicate business effect; Redis markers are optional, never truth.
Completion = a SHORT guarded tx (Artifact ref + Attempt finish + running->succeeded + Event) guarded by
running + current lease token + unexpired lease + fencing_generation = current persisted generation (EQUALITY);
Artifact existence alone is NOT success.
Degrade by boundary = Redis unhealthy -> fail-closed new expensive admission; PostgreSQL down -> no new accepts;
input Object Storage down -> fail-closed THAT admission only, not unrelated healthy endpoints.
Tenant safety = authenticated tenant predicate + composite tenant-aware FKs; a cache key is not authorization.
Recovery = contain + reconcile (Job/Attempt/Provider idempotency/Artifact) + guarded completion; never blind
re-call, never Artifact-as-ownership.
```

---

# Main Concepts

## Concept 1: Ownership and what is durable at acceptance

### Tech Lead Question

A tenant uploads a Document and submits `POST /jobs`. What does PostgreSQL own, and which durable facts must
exist before you return `202`?

### Student Thinking

The student listed the durable PostgreSQL-owned facts from the whole Phase 3 arc.

### Student Answer

> "Postgresql持有attempt、event、outbox intent、stable idepmotency key、fencing token"

### Tech Lead Review

Right list of durable, PostgreSQL-owned facts — Attempt, Event, Outbox intent, the stable idempotency key, and
the fencing generation are all PostgreSQL's. The refinement is *timing*: at `202` the **required** anchor is
only the committed **Job** + the `(tenant_id, idempotency_key)` **uniqueness** + the **Outbox dispatch intent**.
Attempt, Event, lease token, and fencing generation **need not exist yet** — they appear when a Worker claims or
a takeover happens. Object Storage owns the large Document/result bytes; PostgreSQL owns their durable
references and verification metadata; and Redis messages/cache/counters/leases are losable and cannot prove a
Job was accepted.

### Engineering Thinking

Separate "durable at acceptance" from "durable over the lifecycle." Over-requiring facts at `202` (like a
fencing token) invents preconditions that do not exist until execution.

## Concept 2: Dispatch is driven by the Outbox, not the queue state

### Tech Lead Question

How does a dispatch message get onto the queue after acceptance?

### Student Answer

> "outbox intent通过relay进行扫描"

### Tech Lead Review

Correct. The **Relay** scans **unpublished** Outbox intents (`published_at IS NULL`), publishes them to the
queue, and then checkpoints the publication. The boundary to hold: do **not** scan all `queued` Jobs — `queued`
is a **business state**, not a durable statement that a dispatch message must be emitted now. The Outbox intent
is the durable "please dispatch this" record; the Job status is not.

### Engineering Thinking

Drive side effects from an explicit durable intent, not from inferring intent off business status. That is what
makes redelivery and recovery well-defined.

## Concept 3: Duplicate delivery is normal; guard the state transition

### Tech Lead Question

The Relay crashed after publishing but before checkpointing, so the message is delivered twice. Is a duplicate
delivery an error?

### Student Thinking

The student first treated a duplicate as something to reject, then anchored duplicate-prevention in PostgreSQL.

### Student Answer

> "重复投递应该使用拒绝"

> "依赖 PostgreSQL 的 guarded 状态转换，redis不是持久化数据事实"

### Tech Lead Review

The second answer is the correct model and it corrects the first. Relay re-publication after an uncertain
checkpoint is **expected at-least-once** behaviour — you do **not** treat the *delivery* as an error. Instead
you let delivery repeat and reject the duplicate **business effect** with a **PostgreSQL guarded state
transition** (only one `queued -> running` succeeds) plus idempotency. Redis "processed" markers are optional
optimizations, **never** final truth (the student's "redis不是持久化数据事实").

### Engineering Thinking

At-least-once transport + idempotent guarded writes is the durable pattern; "reject duplicate delivery" pushes
correctness into a losable layer that cannot guarantee it.

## Concept 4: Completion and Artifact reconciliation

### Tech Lead Question

The Provider returned a large result written to Object Storage. What do you commit to complete the Job, and is
the Artifact's existence enough to mark it `succeeded`?

### Student Thinking

The student proposed committing the object result key, then offered "Attempt finished" as completion evidence,
and reasoned that reconciliation uses the idempotency key against the Provider.

### Student Answer

> "应该与obeject result key一起提交"

> "应该根据idepmotency key在provider查询结果reconcile artifact"

> (is Artifact existence alone enough?) "不能"

> (proposed pre-existing completion evidence) "attempt finished"

### Tech Lead Review

The committing instinct is right and "不能" is the key insight. The Result Artifact reference **is** committed —
but as part of a **short guarded completion transaction** that also finishes the current Attempt, transitions
`running -> succeeded`, appends a `job_succeeded` Event, and creates a notification Outbox intent if needed. So
"Attempt finished" is **written in** that transaction, not a **precondition** proof. Artifact existence alone is
**insufficient**: before completing, verify Artifact **identity/integrity/Job-Attempt ownership**, **current
PostgreSQL ownership** (running + current lease token + unexpired lease + **equality** with the current persisted
fencing generation), and **Provider/result evidence** (the student's idempotency-key reconciliation). If the
Object Storage write succeeded but the PostgreSQL completion rolled back, do **not** blindly delete the Artifact
or re-call the Provider — the current valid owner reconciles deterministic Artifact metadata + Provider
idempotency/result evidence, then retries only the short guarded completion when appropriate.

### Engineering Thinking

Completion is a verified, guarded, atomic commit — not the observation that a file exists. Separate "the model
produced bytes" from "the business committed success."

## Concept 5: Degraded mode — PostgreSQL unavailable

### Tech Lead Question

PostgreSQL is unavailable. Do you keep accepting `POST /jobs`?

### Student Answer

> "不能，因为postgresql的持久化事实是唯一事实来源"

> "contain现有结果拒绝新的job admission，等待数据库恢复后，再运行原子事务提交数据库"

### Tech Lead Review

Correct. New `POST /jobs` cannot be accepted, because Job acceptance, the `(tenant_id, idempotency_key)`
uniqueness, and the Outbox intent must **atomically commit** in PostgreSQL — and that is impossible while it is
down. The right posture is exactly the student's: **contain** already-created external result/Artifact
evidence, **fail closed** on new admission, and after PostgreSQL recovers, reconcile and run the short atomic
transaction. Do not fabricate acceptance in a losable store to "keep serving."

### Engineering Thinking

Acceptance atomicity lives only where the durable truth lives. If that store is down, honest fail-closed +
later reconciliation beats a fake acceptance you cannot make durable.

## Concept 6: Degraded mode — Object Storage / Upload verification

### Tech Lead Question

The input Object Storage is unavailable (or an Upload Session cannot be verified). Do you stop the container?
And what must you verify about an upload before accepting a Job?

### Student Thinking

The student first proposed stopping the container from accepting new Jobs, and listed the upload facts to check.

### Student Answer

> "不能接受，应该container停止接收新的job admission。"

> "upload document key,hash"

### Tech Lead Review

The "don't accept a Job with an unverified input" instinct is right, but scope it: **fail closed only the Job
admission path** that requires a verified Object Storage input — do **not** stop unrelated healthy endpoints or
the whole container merely because this one path is unavailable. On the upload contract, "key, hash" is the
start; before accepting a Job that references an `upload_session_id`, verify **all** of: authenticated tenant
ownership, completed/verified state, non-expiry, a registered Object Storage key, expected/verified hash + size,
and the relevant content-type/scanning policy.

### Engineering Thinking

Scope a failure to the capability it actually breaks. Fail-closed is about the affected admission path, not a
blunt whole-service stop.

## Concept 7: Tenant isolation

### Tech Lead Question

Is filtering a read by `job_id` alone safe? What must every tenant-scoped read and relationship include?

### Student Thinking

The student required tenant identity in reads, flagged the `job_id`-only leak, and proposed composite
uniqueness for the mapping.

### Student Answer

> "必须包含租户id"

> "不安全，一个job_id可能有多个租户"

> "使用unique约束job_id,tenant_id,document_id为唯一组合"

### Tech Lead Review

Right conclusions, with one precision on the reasoning. Job IDs **can** be globally unique — the leak is not
that one `job_id` belongs to many tenants; it is that if Tenant A **learns** Tenant B's UUID and the query
filters by `job_id` alone, B's data leaks. So always use the **authenticated tenant predicate plus** the Job ID.
And unique **association** alone does not prevent a cross-tenant link — **composite tenant-aware foreign keys**
do: a mapping like `job_documents(tenant_id, job_id, document_id)` must reference **both** the `(tenant_id,
job_id)` and `(tenant_id, document_id)` parent boundaries, so a Tenant A Job cannot link a Tenant B Document. A
cache key such as `job-summary:{tenant_id}:{job_id}:v1` includes tenant identity but **is not** authorization.

### Engineering Thinking

Isolation is enforced by the authenticated predicate and tenant-aware constraints, not by the secrecy or
uniqueness of an ID.

## Concept 8: Immutable audit and retention

### Tech Lead Question

A manual repair changes a Job. What else do you touch, and at Artifact retention expiry do you edit the audit
Event?

### Student Thinking

The student noted repair also touches Event/Attempt, and initially proposed editing the audit Event to record
the reason/evidence.

### Student Answer

> "以及event、attempt表"

> "job、Result Artifact reference应该作为保留，审计 Event应该进行修改将原因与证据发进去"

### Tech Lead Review

Correct that repair must not mutate only `jobs` — update the relevant **Attempt** if appropriate and record the
change. The correction is on immutability: an append-only history is **never edited**. Instead of modifying an
audit Event, **append** a new immutable audit/Event record (tenant, Job/Attempt, actor/system, action, reason,
time, incident/repair reference, correlation/evidence). At Artifact retention expiry, delete the Object Storage
bytes per policy but **retain a tombstoned/expired Artifact reference** (key/checksum/created/deleted/policy),
and **append** a new `artifact_expired` / `artifact_deleted` Event with reason and evidence — never edit the
existing history.

### Engineering Thinking

Audit trustworthiness comes from append-only immutability. "Edit the event to add the reason" quietly destroys
the very evidence an audit exists to preserve.

## Concept 9: Performance evidence vs production validation

### Tech Lead Question

You think a query needs an index. How do you justify it, and is that justification production validation?

### Student Answer

> "在隔离环境使用explan analyze"

> (is that production validation?) "不能，因为还需要真实环境迁移后测试"

### Tech Lead Review

Correct on both. Do not claim an index from intuition — in a **disposable isolated environment** collect
representative schema/index/data distribution/query parameters, run `EXPLAIN ANALYZE`, compare actual vs
estimated rows, timing, and (where useful) buffers, before vs after the index. And the student's "不能" is the
honesty boundary: that is **disposable runtime evidence**, **not** production validation — real production
deployment and telemetry are a separate, later step. In this capstone `EXPLAIN ANALYZE` is described as a
**method only**; it was **not run**.

### Engineering Thinking

Evidence has tiers: static reasoning, disposable measurement, and production telemetry. Naming the tier
honestly is part of the engineering, not a footnote.

## Concept 10: Fencing-generation migration with old Workers

### Tech Lead Question

You are adding `current_fencing_generation`. How do you roll it out, and can you shorten the lease to force old
Workers to hand over?

### Student Thinking

The student described a nullable-first compatible rollout, then proposed shortening the lease and giving the old
Worker a lower/equal generation so the downstream rejects it.

### Student Answer

> "先nullable新字段保持新旧版本兼容性，切换traffic让新的job都带上这个字段，对还在运行的旧work brain"

> "lease token的过期时间短，让新worker可以接管。之后新worker获得fencing generation，然后给旧work一个小于或等于新work的generation，下游就会拒绝旧work"

> "提交原子事务写入数据库"

### Tech Lead Review

The Expand-first, nullable, compatible-deploy instinct is right: add the column nullable, let new code tolerate
`NULL` during rollout, have claim/takeover write a **strictly greater** durable generation, and validate all
relevant running Jobs and completion paths **before** enforcing the new guard (Day36 Expand→Backfill→Validate→
Switch→Contract). The correction is on the takeover reasoning: **shortening a lease does not stop a paused old
Worker**, and old **code** may bypass the fence entirely — so a stale old Worker can still write a stale
completion. You must **drain/upgrade** the legacy claim/completion paths, or **enforce the PostgreSQL guard on
every durable completion path**; a fence only protects writes that actually verify it. Provider effects still
rely on idempotency and reconciliation, not on the fence.

### Engineering Thinking

A guard protects only the code paths that check it. Migration safety is about draining/upgrading the writers,
not about hoping expiry or a smaller number silences an old binary.

## Concept 11: Integrated failover + paused-Worker + Artifact recovery

### Tech Lead Question

PostgreSQL committed Job + Outbox and returned `202`. A Redis failover lost some counters/messages; old Worker A
called the Provider and paused; its lease expired; Worker B took over with a larger durable fencing generation
and found a deterministic Artifact. Contain it.

### Student Answer

> "contain先停止旧work接新的job admission，对旧的在运行的work进行brain，确认旧work无法再按照旧路径写入， B先对账 Job / Attempt / Provider idempotency / Artifact，再决定是否调用 Provider 或提交完成事务绝对不能重新调用proveider,绝对不能把artifact存在替代ownership的检查。"

### Tech Lead Review

This is the whole lesson in one answer, and it is correct. Contain old Worker A's claims and **ensure the legacy
completion path cannot bypass the new guard**; do **not** mass-restart Workers (that interrupts in-flight
external work); the Relay republishes the durable Outbox intent to recover the lost Redis message; and Worker B
**reconciles Job / Attempt / Provider idempotency / Artifact** before deciding whether to call the Provider or
commit completion. The two absolutes the student states are exactly the capstone's: **never** blindly re-call
the Provider merely because B holds a fresh lease, and **never** use Artifact existence as a substitute for
ownership + result verification. Then either perform the guarded atomic completion or let only the current owner
decide a verified next Provider action.

### Engineering Thinking

Recovery is reconcile-then-act against durable truth, with a guard that every completion path honors. A fresh
lease is permission to *reconcile*, not permission to *repeat expensive effects*.

---

# Common Misconceptions

Facts required at acceptance

❌ "Attempt, Event, and a fencing token must exist to prove a `202`-accepted Job."
✅ At `202` the anchor is committed Job + `(tenant_id, idempotency_key)` uniqueness + Outbox intent. Attempt,
Event, lease token, and fencing generation may not exist until claim/takeover.

Why beginners think this: those facts are durable and matter to later recovery.
How to remember: acceptance facts ≠ lifecycle facts.

Duplicate delivery

❌ "Duplicate delivery is an error to reject."
✅ At-least-once re-publication is normal; let delivery repeat and reject the duplicate business effect with a
PostgreSQL guarded transition + idempotency.

Why beginners think this: "duplicate" sounds like a bug.
How to remember: guard the effect, not the delivery.

Artifact existence

❌ "The result Artifact exists in Object Storage, so the Job succeeded."
✅ Artifact existence is insufficient; completion is a short guarded transaction after verifying identity/
integrity, current ownership + fencing equality, and Provider/result evidence.

Why beginners think this: the bytes are right there.
How to remember: bytes produced ≠ business committed.

Tenant leak

❌ "A globally unique `job_id` is safe to query by itself."
✅ If another tenant learns the UUID and the query filters by `job_id` alone, data leaks. Use the authenticated
tenant predicate + Job ID, and composite tenant-aware foreign keys.

Why beginners think this: uniqueness feels like isolation.
How to remember: unique ≠ authorized.

Audit edits

❌ "At Artifact expiry, edit the audit Event to record the reason."
✅ Append-only history is never edited. Tombstone the Artifact reference and append a new expiry/deletion Event
with evidence.

Why beginners think this: editing keeps one tidy record.
How to remember: append, never edit.

Fencing migration

❌ "Shorten the lease and give the old Worker a smaller generation so the downstream rejects it."
✅ Expiry never stops a paused old Worker and old code may bypass the fence. Drain/upgrade old Workers or
enforce the guard on every completion path; a fence protects only writers that verify it.

Why beginners think this: expiry + a smaller number feels like control.
How to remember: a guard only guards the code that checks it.

Failure scope

❌ "Object Storage is down, so stop the container."
✅ Fail closed only the admission path that needs the verified input; keep unrelated healthy capability running.

Why beginners think this: stopping everything feels safe.
How to remember: scope the failure to what it actually breaks.

Validation claims

❌ "`EXPLAIN ANALYZE` in an isolated environment proves production performance."
✅ It is disposable runtime evidence, not production validation; representative data, before/after, and later
production telemetry are separate tiers.

Why beginners think this: a real plan looks authoritative.
How to remember: disposable measurement ≠ production validation.

---

# Engineering Trade-offs

## Redis processed-marker vs PostgreSQL guarded transition

A Redis "processed" marker is fast and cheap but losable, so it cannot be the authority for "did this Job
already run." A PostgreSQL guarded transition is the durable authority at the cost of a database write. Use the
guarded transition for correctness; a Redis marker only as an optional optimization in front of it.

## Fail-closed vs fail-open on a dependency outage

Failing closed on new expensive admission (Redis unhealthy, PostgreSQL down, unverifiable input) protects cost
and correctness but rejects some legitimate traffic; failing open preserves availability but can double-charge
or accept unverified inputs. For expensive, state-changing admission, fail closed and scope it to the affected
path.

## Verify-before-complete vs trust-the-Artifact

Verifying identity/integrity/ownership/result before completion costs extra reads and reconciliation but
prevents shipping an unverified or stale result; trusting Artifact existence is simpler but unsafe under
takeover and rollback. Always verify before the guarded completion.

## Composite tenant-aware FKs vs single-column keys

Composite tenant-aware foreign keys make cross-tenant links structurally impossible at the cost of wider keys
and more careful schema design; single-column keys are simpler but allow a Tenant A → Tenant B link if
application checks slip. For multi-tenant data, pay for the composite keys.

## Disposable measurement vs production telemetry

Disposable `EXPLAIN ANALYZE` is fast, safe, and reproducible but not representative of production scale/
contention; production telemetry is authoritative but slower and riskier to gather. Use disposable evidence to
justify a design and defer the production claim until you have real telemetry.

## Drain/upgrade vs enforce-guard-everywhere for migration

Draining/upgrading old Workers removes the stale-writer risk at the cost of a rollout window; enforcing the
guard on every completion path protects even a lingering old writer but requires touching every path. Do both
where you can; never rely on lease expiry or a smaller generation to stop old code.

---

# Hands-on Exercises

Design/paper only over the one evolving multi-tenant AI Job scenario. Nothing here was executed — no
PostgreSQL, Redis, Object Storage, Provider, Celery/Relay/Worker, FastAPI, migration, or `EXPLAIN ANALYZE`;
every key/ID/threshold is a static design example.

### Exercise 1: Reconstruct durable acceptance after Redis loss

Question: after a Redis loss, what is the minimal durable anchor proving a Job was accepted?

Expected Output: Job + `(tenant_id, idempotency_key)` uniqueness + Outbox dispatch intent, committed in one
PostgreSQL transaction before `202`; Redis holds nothing that proves acceptance.

Explanation: acceptance truth is durable and PostgreSQL-only.

Follow-up: which facts (Attempt/Event/lease/fencing) are legitimately absent at this point?

### Exercise 2: Relay duplicate publication

Question: the Relay crashed after publish, before checkpoint. What prevents duplicate business work?

Expected Output: accept the duplicate delivery as normal at-least-once; a PostgreSQL guarded `queued -> running`
(one winner) + idempotency rejects the duplicate effect; a Redis processed marker is optional, not truth.

Explanation: guard the effect, not the delivery.

Follow-up: why is a Redis marker unsafe as the authority?

### Exercise 3: Completion after Artifact-first write and rollback

Question: Object Storage write succeeded but the PostgreSQL completion rolled back. What do you do?

Expected Output: do not delete the Artifact or re-call the Provider; the current valid owner reconciles
deterministic Artifact metadata + Provider idempotency/result, then retries only the short guarded completion
(Artifact ref + Attempt finish + `running->succeeded` + Event) under the ownership + fencing-equality guard.

Explanation: completion is verified/guarded/atomic; Artifact existence is not success.

Follow-up: list the three verification classes required before completing.

### Exercise 4: Degraded modes for Redis / PostgreSQL / Object Storage

Question: give the behaviour for each dependency being unavailable.

Expected Output: Redis unhealthy → fail-closed new expensive admission, no counter-as-headroom, no mass restart,
bounded backoff, drain in-flight; PostgreSQL down → no new accepts, preserve external evidence, reconcile after
recovery; input Object Storage down / unverifiable upload → fail-closed that admission only, not unrelated
endpoints.

Explanation: degrade by boundary; scope the fail-closed.

Follow-up: why can't a missing Redis counter be read as quota headroom?

### Exercise 5: Tenant-safe reads, relationships, and immutable audit/retention

Question: design a tenant-safe read + `job_documents` mapping + a repair/retention audit trail.

Expected Output: authenticated tenant predicate + Job ID on every read; `job_documents(tenant_id, job_id,
document_id)` with composite tenant-aware FKs to both parents; repair updates Job/Attempt and appends an
immutable audit Event; retention tombstones the Artifact reference and appends `artifact_expired/deleted`.

Explanation: isolation via predicate + composite FKs; audit via append-only.

Follow-up: why is a globally unique `job_id` still unsafe to query alone?

### Exercise 6: Disposable `EXPLAIN ANALYZE` evidence vs production validation

Question: justify a proposed index and classify the evidence.

Expected Output: disposable isolated environment with representative data/params, `EXPLAIN ANALYZE`, actual vs
estimated rows, timing/buffers, before/after — labelled disposable runtime evidence, not production validation.

Explanation: name the evidence tier honestly.

Follow-up: what additional evidence would a production claim require?

### Exercise 7: Fencing-generation Expand→Contract migration

Question: roll out `current_fencing_generation` with old Workers still running.

Expected Output: Expand (nullable) → compatible deploy (tolerate NULL) → backfill → validate all running Jobs/
completion paths → switch (claim/takeover writes a strictly greater generation; guard enforced) → contract;
drain/upgrade old Workers or enforce the guard on every completion path — do not shorten the lease to "force"
takeover.

Explanation: a guard protects only paths that verify it.

Follow-up: why does lease expiry not stop a paused old Worker?

### Exercise 8: Integrated failover + paused Worker + Artifact reconciliation

Question: solve the full incident (failover lost messages; A paused mid-Provider; lease expired; B took over
with a larger generation and found an Artifact).

Expected Output: contain A's claims and close the legacy-guard-bypass; no mass restart; Relay republishes the
Outbox intent; B reconciles Job/Attempt/Provider idempotency/Artifact; then guarded atomic completion or a
current-owner-only verified next action; never blind re-call, never Artifact-as-ownership. Maps to the
artifact's recovery runbook.

Explanation: reconcile-then-act against durable truth under a universally-honored guard.

Follow-up: what are the two absolutes this scenario must never violate?

---

# Relevant Framework Connections

## PostgreSQL

PostgreSQL is the integrated durable authority: the Accept transaction (Job + idempotency uniqueness + Outbox),
the guarded `queued -> running` claim and `running -> succeeded` completion, the durable fencing generation,
tenant-aware composite foreign keys, append-only Events, and the `EXPLAIN ANALYZE` evidence method. Watch that
acceptance and completion atomicity, and all tenant isolation, live here and nowhere losable.

## Redis

Redis provides the transient cache, queue delivery, rate-limit counters, and short leases from Day38-Day41 —
all losable on eviction/failover and never business truth. Watch that a Redis marker/counter/lease is never
treated as acceptance, completion, quota headroom, or a stop signal for external work.

## Relay / queue / Celery worker boundary

The Relay publishes unpublished Outbox intents at-least-once; Workers claim with a guarded transition and drain
rather than mass-restart during an incident. Watch that dispatch is Outbox-driven (not `queued`-scan) and that
duplicate delivery is expected, not an error. (A supported Celery broker transport is Day55; Day42 does not
build one.)

## Object Storage

Object Storage owns large Document/result bytes by deterministic key; PostgreSQL owns references + hash/size/
verification and tombstoned retention records. Watch that Artifact existence is verified (identity/integrity/
ownership) before completion and never treated as success on its own.

## FastAPI (future connection only)

Day43 exposes this Day42 ownership/failure contract as the FastAPI AI Job HTTP lifecycle; Day44 adds typed
Pydantic v2 contracts; Day46-48 map/persist/evolve this model with SQLAlchemy/Alembic without changing
ownership. Day42 implements none of this — it is named as the next boundary only.

---

# AI Backend Connections

## Multi-tenant expensive Job admission

Expensive AI Job admission is protected by the acceptance contract and per-tenant limits; failing closed when a
dependency is unhealthy protects duplicate model cost and every other tenant's capacity, while the durable facts
still permit later recovery.

## Long-running Provider calls that outlive a lease

An eight-minute Provider call can outlive a Redis lease, so a paused Worker's call may still be in flight at
takeover. Stable Provider idempotency + deterministic Artifact reconciliation (not the lease, not Artifact
existence) prevent a duplicate external effect, and the PostgreSQL fencing-equality guard rejects a stale
completion.

## Tenant data isolation for documents, summaries, and artifacts

Uploaded Documents, Job summaries (cache), and generated binary Artifacts are all tenant-scoped: the
authenticated tenant predicate, composite tenant-aware foreign keys, and tenant-prefixed cache keys keep one
tenant's research data from leaking to another.

## Failure containment protects capacity and cost

Containment (fail-closed admission, bounded backoff, drain not restart) protects capacity and model cost during
an incident, while PostgreSQL's durable Job/Attempt/Event/Outbox facts and Object-Storage Artifact evidence make
principled recovery possible afterward.

---
# English Interview

## Key Vocabulary

durable source of truth, acceptance transaction, idempotency uniqueness, Transactional Outbox, at-least-once
delivery, guarded state transition, lease, fencing generation, completion guard, Artifact reconciliation,
degraded mode / fail closed, tenant isolation, composite foreign key, append-only audit, tombstone, retention,
`EXPLAIN ANALYZE`, disposable runtime evidence vs production validation.

## Useful Expressions

"PostgreSQL is the single source of durable truth; Redis coordinates and is losable." · "At `202` I need Job +
idempotency uniqueness + Outbox intent." · "Duplicate delivery is normal; I guard the state transition." ·
"Artifact existence is not success." · "Fail closed on the affected admission path, not the whole service."

## Beginner Question — What owns durable truth in this system, and what is Redis for?

Strong answer:

> "PostgreSQL owns the durable business truth: Job identity and status, tenant ownership, the API idempotency
> uniqueness, the Outbox intent, the Attempt and Event history, the fencing generation, and the references to
> Object Storage artifacts. Object Storage holds the large document and result bytes. Redis is transient
> coordination — cache, queue messages, rate-limit counters, and short leases — and it can be lost on eviction
> or failover, so it never proves that a Job was accepted or completed."

## Intermediate Question — After a Redis failover loses messages and counters, how do you keep the Job pipeline correct?

Strong answer:

> "A Redis message loss is recovered because dispatch is driven by the durable Outbox: the Relay re-publishes
> unpublished intents, and at-least-once duplicate delivery is expected. Workers reject duplicate business work
> with a PostgreSQL guarded `queued -> running` transition plus idempotency, not a Redis marker. For the lost
> rate-limit counters I fail closed on new expensive admission rather than treating a low counter as headroom, I
> don't mass-restart Workers, and I use bounded backoff while draining in-flight external work. Nothing about
> the failover changes the durable truth in PostgreSQL."

## Senior Question — Walk through completing a Job when Worker A paused mid-Provider-call, its lease expired, and Worker B took over and found the result Artifact.

Strong answer:

> "A fresh lease is permission to reconcile, not to repeat expensive work. B must not call the Provider just
> because it holds a new lease, and it must not treat the Artifact's existence as proof of success. B reconciles
> the durable facts — Job, Attempt, Event, Outbox, the stable Provider idempotency key — and verifies the
> deterministic Artifact's identity, integrity, and Job/Attempt ownership. Completion is a short guarded
> transaction: record the Artifact reference, finish the Attempt, transition `running -> succeeded`, append the
> Event, guarded by `running` + the current lease token + an unexpired lease + equality with the current
> persisted fencing generation. Because claim/takeover wrote a strictly greater generation, A's stale completion
> fails the equality guard. I'd also make sure the legacy completion path can't bypass the guard, by draining or
> upgrading old Workers — a fence only protects writers that verify it. Provider duplicate effects stay handled
> by idempotency and reconciliation, and all of this is conceptual design: RUNTIME NOT RUN, PRODUCTION NOT
> VALIDATED."

## Common Weak Answer

"Redis holds the queue and a processed flag, so if the Artifact is in storage and B has the lease, mark the Job
succeeded and move on."

## Strong Answer

"Redis is losable coordination, not truth; a processed flag and a lease prove nothing durable. Success is a
guarded PostgreSQL completion after verifying Artifact identity/integrity/ownership, current ownership + fencing
equality, and Provider/result evidence. Acceptance and completion atomicity, tenant isolation, and audit all
live in PostgreSQL; Object Storage holds bytes; Redis only accelerates and coordinates."

---

# Mental Model Summary

```text
1.  PostgreSQL = single source of durable truth; Object Storage = large bytes; Redis = transient, losable coordination.
2.  Durable at 202 = Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent; Attempt/Event/lease/fencing come later.
3.  Dispatch = publish UNPUBLISHED Outbox intents; do not scan `queued`; at-least-once duplicates are normal.
4.  Reject duplicate EFFECT with a PostgreSQL guarded transition (one queued->running); Redis markers are optional.
5.  Completion = a SHORT guarded tx (Artifact ref + Attempt finish + running->succeeded + Event).
6.  Completion guard = running + current lease token + unexpired lease + fencing_generation = current PERSISTED generation.
7.  Artifact existence is NOT success; verify identity/integrity/ownership + fencing + Provider/result first.
8.  Artifact-first write + PostgreSQL rollback -> reconcile, do NOT delete or re-call; retry only the guarded completion.
9.  Degrade by boundary: Redis unhealthy -> fail-closed admission; PostgreSQL down -> no new accepts; input Object Storage down -> fail-closed THAT admission only.
10. A missing/low Redis counter is NOT quota headroom; do not mass-restart Workers; bounded backoff + drain.
11. Verify an Upload Session (tenant ownership, verified state, non-expiry, key, hash/size, content-type) before admission.
12. Tenant safety = authenticated tenant predicate + Job ID + composite tenant-aware FKs; a cache key is not authorization.
13. Audit is append-only: tombstone Artifact references, append artifact_expired/deleted; never edit history.
14. EXPLAIN ANALYZE in a disposable environment = evidence method, NOT production validation (and NOT run here).
15. Fencing generation is durable in PostgreSQL via Expand->Contract; drain/upgrade old Workers; expiry != a stop.
16. Recovery = contain + reconcile (Job/Attempt/Provider idempotency/Artifact) + guarded completion; never blind re-call, never Artifact-as-ownership.

Starting model -> reasoning -> correction -> final model:
Initial: Attempt/Event/fencing are required to prove a 202 Job; duplicate delivery should be rejected; the
Artifact (or "Attempt finished") proves completion; a job_id-only query is fine if the id is unique; edit the
audit Event at expiry; shorten the lease and hand the old Worker a smaller generation; an Object Storage outage
means stop the container.
Reasoning: the student consistently anchored truth in PostgreSQL, protected it from losable Redis, and reasoned
about idempotency and reconciliation.
Correction: acceptance facts are only Job + idempotency + Outbox; duplicate delivery is normal and guarded, not
rejected; completion is a verified guarded transaction and Artifact existence is insufficient; use the
authenticated tenant predicate + composite FKs; append audit, never edit; drain/upgrade old Workers and enforce
the guard universally because expiry can't stop old code; fail closed only the affected admission path.
Final: one integrated contract where PostgreSQL owns durable truth and atomicity, Object Storage owns verified
bytes, Redis coordinates but is losable, every completion is guarded and fenced, tenants are isolated by
predicate and composite keys, audit is append-only, and recovery reconciles durable facts rather than trusting
transient state or Artifact presence.
```

---

# Today's Takeaway

The capstone is one sentence stretched across a system: PostgreSQL is the single source of durable truth,
Object Storage owns verified bytes, and Redis coordinates but is losable — so acceptance, completion, tenant
isolation, and audit are all decided by guarded, verified, append-only PostgreSQL facts, and every failure
degrades by boundary and recovers by reconciliation.

Most important mental model: PostgreSQL durable truth vs Redis losable coordination vs Object Storage bytes.
Most important production risk: treating a Redis marker/counter/lease or an Artifact's existence as durable
proof (double model cost, unverified or stale completion, cross-tenant leak). Most important trade-off:
fail-closed-by-boundary vs fail-open. Most important connection: Day43 exposes this contract as the FastAPI AI
Job lifecycle. Most important interview answer: a fresh lease is permission to reconcile, not to repeat
expensive work.

Validation status: this lesson is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT
VALIDATED. No PostgreSQL, Redis, Object Storage, Provider, Celery/Relay/Worker, FastAPI, migration, or
`EXPLAIN ANALYZE` was executed; no failover/load/security/data-repair test was run. `EXPLAIN ANALYZE` is a
described future method only. SQLAlchemy/Alembic are Phase 4 future connections. This closes Phase 3.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I state the ownership map (PostgreSQL truth / Object Storage bytes / Redis losable coordination) and place every entity on it?
- [ ] Can I say exactly what is durable at `202` and what is not?
- [ ] Can I explain why at-least-once duplicate delivery is normal and how a guarded transition rejects the duplicate effect?
- [ ] Can I design the short guarded completion transaction and its verification (identity/integrity/ownership + fencing equality + result)?
- [ ] Can I explain why Artifact existence is not success and what to do on an Artifact-first write + rollback?
- [ ] Can I give the degraded behaviour for Redis, PostgreSQL, and Object Storage failures, scoped to the affected path?
- [ ] Can I verify an Upload Session before admission?
- [ ] Can I design tenant-safe reads (predicate + Job ID) and composite tenant-aware foreign keys?
- [ ] Can I keep audit append-only and tombstone Artifact references on retention expiry?
- [ ] Can I describe the disposable `EXPLAIN ANALYZE` evidence method and why it is not production validation?
- [ ] Can I roll out the fencing generation with Expand->Contract and explain why draining/upgrading old Workers is required?
- [ ] Can I solve the integrated failover + paused-Worker + Artifact reconciliation without blind re-call or Artifact-as-ownership?
- [ ] Can I answer the Beginner/Intermediate/Senior English system-design questions on this model?
```

Preparation for Day43 (Phase 4 — AI Backend Product Contract and FastAPI Request Lifecycle): review this
capstone's ownership and failure contracts and the `capstone-backend-data-design.md` artifact, then preview how
the same contract becomes an HTTP product contract and FastAPI request/response lifecycle. SQLAlchemy/Alembic
remain Phase 4 (Day46-48) and are not implemented before then.

---

Engineering Artifact: [projects/ai-backend-data-layer/capstone-backend-data-design.md](../../projects/ai-backend-data-layer/capstone-backend-data-design.md)
