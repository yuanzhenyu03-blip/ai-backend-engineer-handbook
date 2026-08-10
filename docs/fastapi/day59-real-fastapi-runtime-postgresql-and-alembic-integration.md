# Day59 — Real FastAPI Runtime, PostgreSQL and Alembic Integration

## 1. Lesson Metadata

```text
Status:        ✅ Completed
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 3–4 hours
Prerequisite:  Day43 acceptance contract, Day46 ORM mapping, Day47 async Unit of Work,
               Day48 Alembic safe evolution, Day49 Document verification, Day50 idempotent
               Job + Outbox, Day51/Day52 authentication + tenant authorization
Next Lesson:   Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration
```

Phase 5 opens the **Production Integration Gate** (Day59–61). Day59 is the first lesson
in the whole track that runs the Day43–Day58 API contract as **real local
INTEGRATION_RUNTIME** — a real FastAPI/Uvicorn process, a real PostgreSQL, real Alembic
migrations — rather than a deterministic in-process model.

> Evidence honesty (Day59 review fix): the acceptance path was corrected after class
> (single `session.begin()` + `INSERT ... ON CONFLICT` create-or-return; real
> `upload_sessions.session_status='verified'` Document verification; the `Idempotency-Key`
> header; a fingerprint that covers ordered `document_ids`; conflict re-read). The
> repository updating agent re-ran only `py_compile` and the standard-library pure-logic
> tests (**10 passed**, `EXECUTED_LOCAL_RUNTIME`). The real Uvicorn + PostgreSQL + Alembic
> **INTEGRATION_RUNTIME for the corrected code was NOT re-run** by the updating agent and
> is not claimed as verified for the current code — see the design/runbook.

---

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain why only a committed acceptance bundle — not a `202`, a log, or a live
  `Session` — proves a Job was accepted.
* Explain why committed-state evidence must be read from a NEW database connection.
* Run the raw Day42 baseline → Alembic stamp → controlled upgrade discipline and
  diagnose real migration failures from a fresh connection.
* Distinguish liveness from readiness, and gate readiness on the expected Alembic
  revision.
* Implement idempotent Job acceptance with a tenant + idempotency key + request
  fingerprint, atomic Job + Document links + one dispatch Outbox intent.
* Contain a premature-`202` release and choose API-vs-schema rollback safely.
* Label evidence honestly across `CONCEPTUAL_STATIC` / `EXECUTED_LOCAL_RUNTIME` /
  `INTEGRATION_RUNTIME` / `PRODUCTION` and state NOT RUN limits.

---

## 3. Why This Matters

Every prior Phase 4 lesson was deterministic in-process control flow. That proves the
rules but not that the system actually runs against real infrastructure. In production
the expensive failures live exactly at the seams Day59 exercises: a route that returns
`202` before the transaction commits; a migration that "succeeded" in the logs but
rolled back; a readiness probe that reports healthy on the wrong schema; an idempotency
key that silently accepts a second, different request. Day59 converts the honest Day58
"integration NOT RUN" boundary into bounded, reviewable local integration evidence — and
teaches the discipline of proving it from an independent connection, not from the code
that wrote it.

---

## 4. Roadmap Position

```text
Day58 deterministic observability (EXECUTED_LOCAL_RUNTIME; integration NOT RUN)
      |
      v
Day59 real FastAPI + PostgreSQL + Alembic acceptance integration (this lesson)
      |
      v
Day60 real Redis/Celery Relay + Worker consume the dispatch Outbox intent
Day61 real Object Storage + HTTP Provider adapter + OpenTelemetry end-to-end
      |
      v
Interview readiness: acceptance boundary, idempotency, migration diagnosis, rollback
```

### Knowledge continuity

Day58 established that durable PostgreSQL facts decide execution/recovery while
observability only explains them, and that missing telemetry never authorizes a retry.
Day43 supplied commit-before-`202` and idempotency; Day46 the schema mapping; Day47 the
async Session/Unit-of-Work; Day48 Alembic safe evolution; Day49 Document verification;
Day50 the idempotent Job + transactional Outbox intent; Day51–52 authentication and
tenant authorization. Day59 is the first real local gate joining those boundaries —
without yet claiming a real broker, Worker, Object Storage, Provider, OpenTelemetry
exporter, or production identity system.

---

## 5. Lesson Map

```text
Acceptance boundary  ->  fresh-connection evidence  ->  real migration diagnosis
     ->  readiness vs liveness  ->  idempotency + request fingerprint
     ->  Document lifecycle  ->  premature-202 containment & rollback  ->  evidence tiers
```

---

## 6. Core Mental Model

```text
202 Accepted  ==  ONE committed transaction, verified from a NEW connection
              ==  queued Job + request_fingerprint + one job.dispatch_requested Outbox intent + Document link(s)

A log / a Session / an HTTP response  !=  proof of acceptance
Missing/visible signal                !=  durable fact
```

Acceptance is a committed database fact you can re-read from another connection — nothing
else. Everything in this lesson builds on that single model.

---

## 7. Main Concepts

### Concept 1: What actually proves acceptance

Tech Lead Question: Does a `202` response (or a log line, or a reservation) prove the Job
was accepted?

Student Thinking / Answer: **"不是"** (no). The student then proposed to "检查 reservation、
outbox intent 是否存在" (check whether a reservation and Outbox intent exist).

Tech Lead Review: Correct that a `202`/log is not proof. Refined: a **reservation** is a
later Worker/Provider-lifecycle fact, not a Day59 admission fact. Day59 acceptance is
proven by the committed **Job + one `job.dispatch_requested` Outbox intent + Document
links**. A reservation is not an admission.

Engineering Thinking: define acceptance as a single committed bundle, then make every
downstream decision from that bundle.

### Concept 2: Why a fresh connection

Tech Lead Question: You just wrote the rows in the request `Session`. Why not read them
back from the same `Session` to prove acceptance?

Student Thinking / Answer: **"因为可能会读到内存 session"** — a Session can serve rows from
its identity map / open transaction that are not yet committed.

Tech Lead Review: Exactly. Transaction visibility and the identity map can mask reality.
Committed-state evidence must come from an **independent** connection (a separate `psql`
or a new engine connection), so you are reading what actually committed, not what your
own uncommitted transaction can see.

### Concept 3: Real migration diagnosis (three real failures)

Tech Lead Question: You pointed Alembic at a blank database on Python 3.9 and it failed.
What do you record?

Student Thinking / Answer: **"记录具体错误"** (record the specific error).

Tech Lead Review: Necessary but not sufficient. Refined to: preserve the precise error
AND inspect the **final committed revision/schema from a new connection**, because a
failed migration transaction may have rolled back. Three real failures were diagnosed in
order:

```text
1. Python 3.9 import failed — existing ORM uses 3.10+ PEP 604 `X | Y` unions.
   Fix: run the integration on Python 3.11; repository guidance now requires 3.10+.
2. Blank DB could not upgrade — the Day48 contract needs the raw Day42 baseline first,
   then an Alembic STAMP at 0001_baseline (a stamp declares an already-existing verified
   schema version; the student correctly defined "bare stamp").
3. Upgrade rolled back — alembic_version.version_num (varchar(32)) could not store the
   33-char revision 0007_merge_reconciliation_polling. Diagnosed from a fresh connection:
   the transaction rolled back and the version stayed 0001_baseline.
```

Fix for (3): a controlled, auditable ONLINE-only repair in `day48_alembic/env.py` widens
`alembic_version.version_num` to `varchar(128)` **only when it exists and is too small**.
It never runs in FastAPI and never touches application data. The student correctly chose
a controlled/auditable version-table repair over editing published revisions.

### Concept 4: Readiness vs liveness

Tech Lead Question: The database is down. What status does the request return, and what
does the health probe return?

Student Thinking / Answer: first **"version"** as the readiness target (incomplete), and
**"500"** for a database failure.

Tech Lead Review: Corrected. Readiness (`/readyz`) = database reachable AND schema at the
**expected Alembic revision**; a ready process on the wrong revision must be `503`, not
silent acceptance. The student refined it well: **"还要验证 alembic_version 与应用预期
revision 兼容"** (also verify `alembic_version` is compatible with the app's expected
revision). A database failure is a readiness `503` (and request-specific errors), not a
blanket `500`.

### Concept 5: Idempotency key vs durable job_id, and the fingerprint

Tech Lead Question: Is the idempotency key the accepted fact?

Student Thinking / Answer: first treated **"idempotency_key"** as the HTTP/DB correlation
identity; gave **"unique(idempotency key, tenant_id)"** as the mechanism.

Tech Lead Review: The unique constraint is the correct **mechanism**. Refined: the
durable **`job_id`** is the accepted fact; the idempotency key is the **command
deduplication key**. `UNIQUE(tenant_id, idempotency_key)` physically dedups; the
persisted **`request_fingerprint`** (SHA-256 of the behavior-relevant command:
ordered `document_ids` + normalized `business_input`; the Idempotency-Key is the dedup
key and is NOT part of the fingerprint — Day50 contract) distinguishes an exact retry from the same key reused for a
different logical request — because it covers the documents, the same key pointing at a
different Document is a `409`, not a replay.
Same tenant/key/fingerprint → return the first Job (student correctly said the same key
should return the first Job). Same key, different fingerprint → `409`.

### Concept 6: Document lifecycle — verified ≠ future availability

Tech Lead Question: On an exact retry, should you revalidate the current Document?

Student Thinking / Answer: initially **yes, revalidate**; corrected to: exact retry
returns the original Job; a new logical submission uses a new key. The student also
correctly said an original Job **cannot be retargeted** to a later-uploaded Document.

Tech Lead Review: Idempotency state is checked BEFORE revalidating mutable Document
state. A verified Document means acceptance-time metadata/provenance + object
verification succeeded — it does NOT promise future Object Storage readability. A later
Worker handles unavailable bytes via an explicit recovery/failure path and never
silently replaces a paid/auditable Job input. New input = new upload/verification, new
key, new Job.

### Concept 7: Premature-202 containment and rollback

Tech Lead Question: A faulty release sent `202` before commit and then crashed. What do
you do?

Student Thinking / Answer: correctly chose to **stop further unreliable Job acceptance
and retain request logs**; expanded to preserve durable + release evidence and roll back
the API (not automatically the schema).

Tech Lead Review: No background process may fabricate a Job or claim the old request
succeeded. Withdraw/circuit-break the faulty API release; preserve
deployment/version/time-window/request/trace/authenticated-tenant/idempotency/exception/
commit-or-rollback evidence; keep existing durable Job and Outbox facts. On an explicit
later retry with the same key: return the committed Job if it exists; if none exists,
run a NEW atomic acceptance — but never call that a replay of a prior success. Because
`0008` is additive, an API rollback is normally safer than an immediate Alembic
downgrade. The student gave the correct answer on savepoints: a savepoint rolls back a
failed INSERT where appropriate, but the broader acceptance boundary must still keep
Job/links/Outbox atomic; a failed transaction cannot safely continue querying as normal.

Production Example: a bad deploy returns `202` then OOM-kills mid-request. Because the
transaction never committed, there is no Job and no Outbox intent — the correct state.
The fix is to contain the release and let clients retry with the same key, not to invent
a Job to "match" the `202` the client saw.

Framework Connection: FastAPI returns the response only after the handler returns; the
acceptance transaction must commit *before* the handler returns `202`, never after.

---

## 8. Common Misconceptions

```text
Acceptance proof
❌ A visible 202 / log / reservation is sufficient.
✅ Only the committed Job + Outbox intent + Document links decide Day59 acceptance; a reservation is not an admission fact.

Session as evidence
❌ A live Session can prove the transaction committed.
✅ Identity-map/transaction visibility can mask reality; read committed state from a fresh connection.

Exact retry
❌ An exact retry should revalidate the current Document.
✅ It returns the original command result; current object availability belongs to execution, not replayed acceptance.

Verified Document
❌ Verified means its Upload Session (or the object) will stay readable.
✅ Verified proves acceptance-time provenance/verification only; future Object Storage readability is not guaranteed.

Premature response
❌ If no Job exists after a premature 202, the server may invent one.
✅ Never fabricate success; an explicit retry may run a NEW atomic acceptance only when no committed fact exists.

Migration failure
❌ A migration failure is resolved by recording its exception.
✅ Preserve the exact error AND inspect the actual committed revision/schema from a new connection; the transaction may have rolled back.
```

---

## 9. Engineering Trade-offs

```text
Additive expand (nullable column + later NOT NULL) vs in-place NOT NULL
  + Legacy rows stay valid; API rollback is safe; no long lock.
  - Two-step: a later human-reviewed contract step is still required.

API rollback vs immediate Alembic downgrade
  + 0008 is additive, so withdrawing the API is lower-risk than a live downgrade.
  - A schema repair, if truly needed, is a later FORWARD migration, not a rushed downgrade.

Controlled env.py version-table repair vs editing published revisions
  + Preserves revision immutability and history; auditable, online-only, data-safe.
  - Adds control-plane logic to env.py that must stay narrowly scoped.

Local integration-test identity seam vs full Day51/52 identity
  + Exercises acceptance without standing up production identity.
  - Forbidden in production: a client that names its own tenant breaks isolation.

Disposable --rm container vs named volume / external DB
  + Clean, reproducible, zero residue for a teaching exercise.
  - Data is deleted on stop; never use --rm for anything you must keep.
```

---

## 10. Hands-on Exercises

Question: Diagnose the three real blockers before proceeding.

Think First: which failures are environment, which are contract, which are Alembic
internals?

Starter Artifact: Python 3.9 import error; blank-DB upgrade error; version-table width
error.

Expected Output: run on Python 3.11; establish raw Day42 baseline → stamp
`0001_baseline` → controlled upgrade; widen `alembic_version.version_num`; verify final
revision/schema from a fresh connection.

Explanation: each failure is diagnosed from committed state, not from the failing
process's own logs alone.

Follow-up Question: why is the stamp required before the first upgrade?

---

Question: POST a valid local test Job, then prove acceptance independently.

Think First: where is the truth?

Starter Artifact: `POST /v1/jobs` with an idempotency key and a verified Document id.

Expected Output (independently queried): Job=1, `request_fingerprint` present, dispatch
Outbox intent=1, Document link=1.

Explanation: verification comes from a NEW connection, not the request Session.

Follow-up Question: retry the same key/payload (same Job) and reuse the key with a
different payload (`409`).

---

Question: Submit an unverified/nonexistent Document with a fresh key.

Expected Output: `422`, and an independent query shows Job=0, Outbox=0, link=0.

Follow-up Question: send two concurrent same-key/same-payload requests. Actual result:
one response was the first acceptance and one was a replay; independent counts were
Job=1, dispatch intent=1, Document link=1.

---

Question: Reason through premature-`202` containment and verified-Document vs later
object availability.

Expected Output: contain the release, preserve evidence, query committed facts, do not
fabricate a Job, and do not retarget an accepted Job to a new Document.

---

## 11. Relevant Framework Connections

* **FastAPI:** route response contracts, the `202` boundary, `400/401/409/422/503`
  behavior, lifespan engine disposal, the liveness/readiness split, and a test-only
  dependency seam. The response is returned only after the transaction commits.
* **SQLAlchemy async:** the existing Day47 async engine + session factory, a
  request-scoped async session, an explicit short `session.begin()` transaction, and the
  rule that a Session is never reused as proof of a commit.
* **Alembic / PostgreSQL:** raw baseline + stamp discipline, a controlled version-table
  width repair, an additive migration, a revision readiness gate, unique/partial-index
  enforcement, and fresh-connection inspection.
* **Docker:** a disposable local PostgreSQL is an execution mechanism, not a schema
  version or an evidence label. `--rm` deletes its writable-layer data at stop; it was
  chosen deliberately for disposable local integration, not persistence. `docker stop`
  does not universally delete data — named volumes and external databases persist.

---

## 12. AI Backend Connections

* AI Job admission must create a durable Job + dispatch intent BEFORE any eventual
  Worker/Broker/Provider work — never a fire-and-forget provider call from the request.
* Job input bytes belong in Object Storage; PostgreSQL owns the Document
  reference/provenance and acceptance facts; the Outbox carries small intent, not large
  files.
* A real future Worker must distinguish an accepted input reference from later byte
  availability and must never silently replace a paid/auditable Job input.
* Day60 (Relay/Worker) and Day61 (Object Storage/Provider/OpenTelemetry) consume these
  Day59 boundaries rather than collapsing them into the HTTP request.

---

## 13. English Interview

### Key Vocabulary

```text
acceptance boundary · commit-before-202 · idempotency key · request fingerprint
Outbox intent · Alembic stamp · expand/contract migration · readiness vs liveness
committed-state evidence · fresh connection · disposable environment
```

### Beginner Question

Q: What is the difference between a verified Document and object availability at Worker
execution?

Strong Answer: "Verified means that at acceptance time the Document's metadata and
provenance were checked and the object was verified, so we accepted the Job referencing
it. It does not guarantee the object is still readable later. When a Worker runs, the
bytes may be unavailable; the Worker handles that through an explicit recovery or failure
path. It must not retarget the Job to a newly uploaded Document — new input means a new
upload, a new idempotency key, and a new Job."

### Intermediate Question

Q: A client retries with the exact same idempotency key. What must the API do?

Strong Answer: "Return the original accepted Job without revalidating later mutable input
or storage state. Idempotency is checked from durable facts before touching mutable
Document state, so an exact retry is deterministic even if the referenced object later
became unavailable. Same key with a different request fingerprint is a conflict — `409` —
because the same command key is being reused for a different logical request."

### Senior Question

Q: A faulty release returned `202` before committing and then crashed. How do you
respond?

Strong Answer: "Contain first: withdraw or circuit-break the faulty API release so it
stops accepting traffic. Preserve evidence — deployment version, time window, request and
trace ids, authenticated tenant, idempotency key, the exception, and whether the
transaction committed or rolled back. Then query committed facts from a fresh connection:
if the Job and Outbox intent exist, the request actually succeeded; if not, nothing was
accepted and no background process may fabricate one. On an explicit later retry with the
same key, return the committed Job if it exists, otherwise run a new atomic acceptance —
but never call that a replay of a prior success. Because the Day59 migration is additive,
an API rollback is safer than an immediate schema downgrade."

### Common Weak Answer

"The client saw a `202`, so the Job exists — I'll create it to match." This fabricates
success and corrupts the audit trail.

---

## 14. Mental Model Summary

```text
202 Accepted        = one committed transaction (Job + fingerprint + one dispatch Outbox intent + Document links)
proof of acceptance = read committed state from a NEW connection, never a live Session
job_id              = the durable accepted fact; idempotency_key = the command dedup key
request_fingerprint = SHA-256(ordered document_ids + business_input); Idempotency-Key = dedup key, NOT in fingerprint (Day50); exact retry -> original Job; different payload OR document -> 409
readiness           = DB reachable AND schema at the expected Alembic revision (else 503)
migrations          = raw baseline -> stamp -> controlled upgrade; diagnose from committed state
0008                = additive expand; API rollback safer than immediate downgrade
verified Document   = acceptance-time provenance only; NOT future object availability
identity seam       = local test-only, loopback-only; NEVER a production tenant authority
evidence tiers      = CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION
```

### Mental Model Evolution

```text
Start:  "A 202 / log / reservation shows the Job was accepted."
        "The Session can prove the transaction."
        "An exact retry should revalidate the Document."
        "A DB failure is a 500; readiness is just 'version'."
        "Record the migration exception and move on."
   |
   v
End:    Acceptance is ONE committed bundle, verified from a fresh connection.
        job_id is the fact; the key is dedup; the fingerprint separates retry from reuse.
        Readiness = DB up AND expected Alembic revision, else 503.
        Migrations: raw baseline -> stamp -> controlled upgrade, diagnosed from committed state.
        Never fabricate a Job; contain the release and prefer additive/forward repair.
```

Assistant-assisted final Chinese mental model (confirmed by the student):

```text
Day59 的“接受”只有一个真相：一次提交成功、并且能从一个新连接独立读到的事务
（queued Job + request_fingerprint + 恰好一个 job.dispatch_requested Outbox intent + Document 链接）。
202、日志、内存 Session、reservation 都不是接受的证据。
job_id 才是被接受的事实，idempotency_key（走 Idempotency-Key header）只是命令去重键，request_fingerprint（覆盖 tenant + key + 有序 document_ids + business_input）用来区分
“完全相同的重试”和“同一个 key 换了不同请求”。
readiness = 数据库可达 且 schema 处于期望的 Alembic revision，否则 503（不是 500）。
迁移顺序是：原始 Day42 baseline -> Alembic stamp -> 受控 upgrade，失败要从新连接查真实 revision。
0008 是可加的（additive），所以回滚 API 通常比立即 downgrade 更安全。
verified 只代表接受时的来源核验，不保证以后对象还能读到。
本地身份头只是受控的集成测试缝隙，绝不能当作生产租户权限。
```

---

## 15. Today's Takeaway

* Most important mental model: `202` equals one committed, independently verifiable
  acceptance bundle — nothing visible is a durable fact.
* Most important production risk: returning `202` before commit (or reading proof from
  the writing Session) fabricates acceptance; contain the release and verify from a fresh
  connection.
* Most important framework/AI connection: admission persists a durable Job + one dispatch
  Outbox intent before any Worker/Broker/Provider work; the Outbox carries intent, not
  bytes.
* Most important interview answer: an exact idempotent retry returns the original Job
  without revalidating later mutable input or storage state.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain why a 202/log/Session does not prove acceptance, and what does?
- [ ] Can I explain why committed-state evidence needs a fresh connection?
- [ ] Can I run raw baseline -> stamp -> controlled upgrade and diagnose failures from committed state?
- [ ] Can I explain readiness vs liveness and the expected-revision gate?
- [ ] Can I explain job_id vs idempotency key vs request fingerprint (retry vs 409)?
- [ ] Can I explain verified Document vs future object availability?
- [ ] Can I contain a premature-202 release and choose API-vs-schema rollback?
- [ ] Can I state Day59's evidence tiers and its NOT RUN limits (Day60/Day61)?
```

---

Related: [Day59 design & runbook](../../projects/ai-backend-data-layer/api/day59-real-fastapi-runtime-postgresql-and-alembic-integration-design.md) ·
[FastAPI cheat sheet](../../cheat_sheets/fastapi.md) ·
[FastAPI interview](../../interview/fastapi.md)
