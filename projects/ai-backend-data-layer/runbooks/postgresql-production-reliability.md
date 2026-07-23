# PostgreSQL Production Reliability Runbook

Day37 operational runbook / evidence pack for the AI Backend Data Layer. It operates the durable PostgreSQL
truth after Day36 made the Lease-aware schema deployable: bounded connections, short transactions, Vacuum
health, least privilege, meaningful health signals, recoverability, monitoring, and failover decisions.

> **Validation status of this whole document.** Every command, number, and threshold below is
> **CONCEPTUAL** and **STATICALLY REVIEWED** only. **RUNTIME NOT RUN. PRODUCTION NOT VALIDATED.** No
> PostgreSQL server, `psql`, configuration, pool, timeout, Vacuum, role, credential, backup, PITR, restore,
> replica, or managed service was executed, measured, or inspected. Numbers (`160`, `420`, `300`, the
> autovacuum settings, any RPO/RTO) are classroom arithmetic and design targets, **not** measured results.
> Do not treat this runbook as an automated executable. Contains **no real secrets or connection strings**.

Related: [Day37 lesson](../../../docs/postgresql/day37-postgresql-production-reliability.md) ·
[project README](../README.md)

---

## 1. Connection-capacity worksheet

A pool limit is an **upper bound on potential demand**, not connections opened immediately. Production
capacity is the **aggregate** across every process, plus reserve.

```text
total API pool demand           = API processes    * per-process pool limit
+ total Worker pool demand      = Worker processes * per-process pool limit
+ migration/monitoring/admin/recovery reserve
------------------------------------------------------------------
  < safe database connection budget   (< max_connections, with margin)
```

Classroom baseline (STATIC arithmetic, not measured):

```text
(4 API processes + 12 Worker processes) * pool limit 10 = 160 possible application connections
```

Rules:

- The database budget must **reserve** connections for migrations, monitoring, administration, recovery, and
  safety margin — do not assign all of `max_connections` to applications.
- Raising pool sizes can **move queuing from the application into PostgreSQL** and increase memory,
  scheduling, CPU, I/O, and cache pressure. More pool is not more capacity.
- Mental model: `global application connection demand < PostgreSQL safe connection budget`.

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no pool configured, saturated, or measured).

---

## 2. The three short Job transaction boundaries

An eight-minute Provider call must **never** hold a PostgreSQL transaction or connection. Provider success,
Object Storage Artifact existence, and committed PostgreSQL business success are **different facts**;
PostgreSQL cannot roll back Provider cost or Object Storage bytes.

```text
Accept:    INSERT queued Job + dispatch Outbox intent  -> COMMIT -> return 202 + job_id
Claim:     reserve eligible queued Job, write Lease, queued -> running,
           create Attempt + job_started Event           -> COMMIT
External:  Provider call + Object Storage Artifact upload OUTSIDE any DB transaction;
           Lease renewal (if needed) uses separate SHORT transactions
Complete:  guard by job_id AND job_status = 'running' AND lease_token = current token AND
           lease_expires_at > now(); finish Attempt, record Result Artifact reference,
           append success Event, running -> succeeded  -> COMMIT
```

- The Complete guard is the **full Day34 condition** — `job_status = 'running'` AND `lease_token` = the
  current token AND `lease_expires_at > now()` — **not the token alone**. Lease expiry does not change
  `lease_token`, so before a takeover the expired Worker's token can still equal the current token; the
  `running` + unexpired-lease predicates are what reject a Worker that has lost ownership.
- `queued -> running` happens in **Claim/Start**, not Accept (Accept only creates `queued`).
- If an Artifact exists but the Complete transaction never committed, the database truthfully still shows
  `running`. Recovery must **reconcile the deterministic Artifact** (by its deterministic key) before
  considering another Provider call — never assume `succeeded` from Artifact existence alone.

Validation: CONCEPTUAL / STATICALLY REVIEWED (matches Day33/Day34/Day36). RUNTIME NOT RUN.

---

## 3. Timeout matrix

Timeout is **failure containment, not root-cause repair.** Every timeout must be observable and routed to a
deliberate action. `SKIP LOCKED` is **candidate selection** for parallel claims, not a timeout.

| Timeout | Scope (what it bounds) | On expiry | Retry rule | Observe |
| --- | --- | --- | --- | --- |
| Pool acquisition timeout | waiting for an **application** connection from the pool | fail fast to the caller | bounded retry or shed load | pool waits, acquisition latency |
| `lock_timeout` | waiting to **acquire a PostgreSQL lock** | statement cancelled (`55P03`) | short bounded retry if safe | lock-wait duration, blockers |
| `statement_timeout` | total **SQL statement** execution time | statement cancelled | investigate slow query; do not blindly retry | slow-query rate, plans |
| `idle_in_transaction_session_timeout` | a transaction **opened then idle** without commit/rollback | session terminated | fix the code path (always commit/rollback) | idle-in-transaction count, oldest txn |
| Application deadline | the overall **business operation** | fail/cancel/degrade the operation according to its semantics | per operation semantics | end-to-end op latency, timeout rate |

Useful ordering: `lock_timeout < statement_timeout < application deadline`.

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no real lock wait/timeout/deadlock executed).

---

## 4. Health matrix

`SELECT 1` proves only that **one simple query can run through one connection** — not pool capacity, lock
freedom, critical Job transactions, disk/WAL health, transaction age, or recovery readiness.

| Signal | Question it answers | Behaviour |
| --- | --- | --- |
| Liveness | would **restarting this instance** likely fix a local failure? | restart only for local, restart-fixable faults |
| Readiness | can this instance **safely receive new traffic** now? | remove from rotation when saturated / dependency-degraded |
| Dependency degradation | is a shared dependency (PostgreSQL) down/saturated? | **drop readiness + bounded backoff/degrade**, do NOT fail every liveness |
| Business-operation check | did a real Accept/Claim/Complete succeed? | the authoritative signal; not identical to a probe |
| Restart-storm prevention | would a shared outage restart everything at once? | a shared PostgreSQL outage must not fail all Pods' liveness simultaneously |

Rule: a shared database outage should normally **remove readiness and trigger bounded backoff/degradation**;
it should not automatically fail every Pod's liveness and cause a simultaneous restart/reconnection storm.

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no probe deployed).

---

## 5. Long-transaction / Vacuum incident procedure

MVCC: an `UPDATE` normally writes a **new row version** so older snapshots still see an older version.
Vacuum can reclaim an old version only after **no active snapshot** can see it. A long or idle-in-transaction
session can retain an old snapshot, possibly retain locks, block cleanup, and grow **dead tuples / table /
index bloat**, amplifying latency, disk, and WAL pressure.

Incident order (root cause first):

```text
1. Identify the transaction: owner, application, query, age, business purpose.
2. If obsolete, cancel or terminate in a CONTROLLED manner (pg_cancel_backend, then pg_terminate_backend).
3. Stop the SOURCE (fix the code path that leaves the transaction open/idle).
4. Allow or trigger cleanup; let autovacuum proceed.
5. Verify transaction-age and dead-tuple trends are recovering.
6. Fix the application boundary so it cannot recur.
```

- Do **not** casually prescribe `VACUUM FULL`: it rewrites the table and takes a strong lock.
- Autovacuum must keep pace with churn. A large, high-update `jobs` table may need **evidence-based
  per-table** tuning rather than disabling autovacuum or globally guessing. Design syntax only (values are
  **not** production recommendations without measurements):

```text
-- DESIGN SYNTAX ONLY — not executed, not a recommendation without measured evidence:
-- ALTER TABLE app.jobs SET (
--   autovacuum_vacuum_scale_factor = 0.02,
--   autovacuum_vacuum_threshold    = 10000
-- );
```

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no Vacuum/autovacuum/dead-tuple behaviour
run, no `VACUUM FULL` run).

---

## 6. Least-privilege role matrix and credential rotation

Runtime DML identities must **not** own arbitrary `ALTER TABLE`, `DROP TABLE`, index creation, or
role-management privileges. Least privilege limits the blast radius of bugs, SQL injection, credential
leaks, and operator error.

| Identity | May do | Must NOT do |
| --- | --- | --- |
| Runtime (API/Worker) | `INSERT`/`UPDATE`/`SELECT` on the Job model; guarded transitions | DDL, `DROP`, index creation, role management |
| Migration | `ALTER`/index build in a controlled window | be held permanently by API processes |
| Monitoring | read stats/activity views | write business data |
| Backup / replication (DB role) | `pg_basebackup` / the replication protocol; only the `REPLICATION` + connection privileges it needs | application DML or DDL |
| WAL archive storage identity | used by the PostgreSQL archiver (`archive_command` / `archive_library`) or the managed service; only write access to the archive store | be an application database account |
| Restore operator / control-plane identity | run restore/PITR in an **isolated** recovery environment; read backup storage, manage the data directory or cloud control-plane recovery | be a production DB role held long-term by API/Workers |

Credential lifecycle: storage alone is **insufficient** — creation, distribution, rotation, revocation, and
audit are all required. Never put credentials in images or Git history; use Kubernetes Secrets, a cloud
Secrets Manager, Vault, or managed short-lived identity.

Rotation procedure:

```text
1. Load the NEW credential alongside the old.
2. Establish NEW connections with it.
3. Verify EVERY instance has switched.
4. Recycle pools in a controlled manner.
5. ONLY THEN revoke the old credential.
```

Diagnostic: existing sessions continuing while **new** authentication fails often indicates an **incomplete
credential rollout**, not total database failure.

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no role/grant/secret/rotation configured).
Contains no real secrets.

---

## 7. Backup / PITR / restore drill

Replication is **not** backup: it improves availability by keeping a near-current copy, but it also **copies
harmful logical changes** (a mistaken `DELETE`/`DROP` replicates). Backup provides **independent historical
recovery material**.

```text
Base backup  = the consistent recovery STARTING POINT.
Archived WAL = ordered PHYSICAL redo changes after that point (not readable SQL history).
PITR         = restore the base backup, replay WAL up to a chosen target BEFORE the bad change.
RPO          = max acceptable DATA-LOSS window   (recovery objective, NOT a health probe).
RTO          = max acceptable RECOVERY duration  (recovery objective, NOT a health probe).
```

Worked PITR target (design example, not executed): to recover from a `10:37` bad delete, choose a target of
`10:36:59` and replay WAL up to just before the change.

A successful backup **job** is only backup evidence. **Recoverability evidence** requires:

```text
1. an ISOLATED restore (never overwrite production to test recovery),
2. PITR to the chosen target,
3. PostgreSQL startup,
4. schema / constraint / key-row integrity checks,
5. business-query validation,
6. measured RPO/RTO,
7. recorded limitations.
```

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN / BACKUP-RESTORE DRILL NOT RUN (no base
backup, WAL archive, PITR, isolated restore, integrity/business check, or RPO/RTO measured).

---

## 8. Monitoring matrix

Low CPU does **not** prove health. Reliability monitoring must cover capacity, waiting, age, growth, and
recovery evidence.

| Area | Signals |
| --- | --- |
| Connections / pool | active / idle / idle-in-transaction, server utilization, pool waits + acquisition latency |
| Queries | latency, timeout rate, slow-query identity + plans (when investigated) |
| Locks | waiters, blockers, deadlocks |
| Transactions / Vacuum | oldest transaction age, dead tuples, autovacuum progress + inability to keep pace |
| Storage / WAL | disk usage/growth, WAL generation, archive failures |
| Replication | lag in bytes/time, replay position |
| Recovery | latest backup evidence, latest **tested** restore, measured RPO/RTO |

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no metric collected).

---

## 9. Replica-promotion gate

A replica ten minutes behind may **exclude acknowledged primary transactions** if promoted. Promotion trades
RTO against RPO.

```text
Gate before promoting:
1. Known replication/replay POSITION.
2. Estimated DATA-LOSS window (how far behind).
3. Explicit RPO DECISION (is that loss acceptable?).
4. SPLIT-BRAIN prevention (old primary must not keep accepting writes).
5. Post-promotion RECONCILIATION plan.

Immediate promotion  -> better RTO, may VIOLATE RPO.
Wait for primary/WAL -> preserves more data, longer outage.
```

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no replica lag/promotion/split-brain run).

---

## 10. Integrated incident: 420 potential connections vs 300 max_connections

```text
Before rollout:  4 API * pool 10 + 12 Worker * pool 10                = 160 possible connections
After bad rollout: 12 API * pool 25 = 300  +  12 Worker * pool 10 = 120  = 420 possible application demand
Configured:      PostgreSQL max_connections = 300
Symptoms:        new connections rejected; readiness failures; Workers still running costly Provider calls.
```

**Wrong** first instinct: raise `max_connections` and avoid restart/rollback because Provider effects cannot
be undone.

**Correct containment:**

```text
1. STOP further scaling / new demand (do not keep growing connection demand).
2. Rate-limit or degrade incoming traffic.
3. Roll back / tighten the API pool configuration via a GRADUAL rollout.
4. PRESERVE / DRAIN Workers with in-flight Provider calls (do not mass-restart -> reconnection storm).
5. Observe recovery: connection pressure, transaction age, lock waits, business-operation recovery.
6. Resize the database ONLY with capacity evidence.
```

The rollback target is the **connection-pool / instance capacity configuration** — *not* the completed
Provider calls. Existing Provider cost and Artifacts are **irreversible external side effects** and must be
**reconciled** (idempotency keys, deterministic Artifact identifiers); configuration rollback does not undo
external effects.

Validation: CONCEPTUAL / STATICALLY REVIEWED. RUNTIME NOT RUN (no pool saturation, restart, or rollback
executed; the `160`/`420`/`300` figures are static arithmetic).

---

## Managed vs self-operated (responsibility boundary)

Managed services may automate infrastructure, patching, availability, backup mechanisms, and scaling per the
provider's contract. The team **still owns** connection budgets, transaction/query behaviour, roles,
credentials, schema, migrations, recovery objectives (RPO/RTO), retention, **restore testing**, business
validation, and incident response. Managed reduces burden but can raise cost, restrictions, and vendor
dependence; self-operation increases control but transfers patching, HA, backup, monitoring, on-call, and
recovery to the team.

---

## Boundary to Day38 (future)

PostgreSQL remains the **durable, recoverable Job source of truth**. Redis (Day38 — Redis Foundations and
Data Structures, and Day39) is transient acceleration / messaging / coordination, judged for correctness
against this authoritative PostgreSQL state. This runbook does not expand Redis.

Validation classification (whole document):

```text
Conceptual classroom validation: COMPLETED
Static reasoning review:          COMPLETED
Artifact syntax/runtime validation: NOT RUN
Disposable PostgreSQL validation:  NOT RUN
Application integration validation: NOT RUN
Backup/restore drill:              NOT RUN
Production validation:             NOT RUN
```
