# CHANGELOG.md

All notable changes to this repository will be documented in this file.

This project follows a practical versioning style:

- `v0.x.x` — training system under construction
- `v1.0.0` — first complete AI Backend Engineer Handbook release

---

## v0.1.78 — Day37 PostgreSQL Production Reliability

Date: 2026-07-22

### Added

- Added `docs/postgresql/day37-postgresql-production-reliability.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day36->Day37 mental-model evolution).
- Added `projects/ai-backend-data-layer/runbooks/postgresql-production-reliability.md` — the Day37 operational **runbook / evidence pack** (a new `runbooks/` directory in the data-layer artifact): a connection-capacity worksheet, the three short Job transaction boundaries, timeout / health / monitoring matrices, a long-transaction+Vacuum incident procedure with evidence-based per-table autovacuum review, a least-privilege role matrix + credential-rotation procedure, a backup/PITR/restore drill with RPO/RTO and explicit limitations, a replica-promotion gate, and the integrated 420-vs-300 connection incident. Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**, with no real secrets or connection strings.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day37 increment: a runbook-contents table, the encoded rules, an explicit statement of what the runbook does not do, Day37 known gaps, a new `runbooks/` entry in the structure tree, and a separate Day37 validation matrix.
- Appended a Day37 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day37 Beginner/Intermediate/Senior questions to `interview/postgresql.md`, preserving the student's real answers verbatim — including the opening `不知道`, the `160` arithmetic, the Artifact-vs-success student-initiated question, the `SKIP LOCKED`/timeout mix-ups, the `mcvv`/`trash` MVCC terminology, the Senior `我不知道` on the 420-vs-300 incident, the English answers, and both passes of the final Chinese synthesis (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day37 is the latest PostgreSQL lesson, and pointed the Day36 lesson's Next Lesson at the released Day37 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day37 completed with its released lesson/artifact (Day38 remains Planned).
- Updated `PROJECT_STATUS.md` (Day37 last completed with artifact + validation boundary; Current/Next is Day38 Planned / Not started), `TASKS.md` (completed Day37 blocks, Day37 preparation converted to history, Day38 preparation added), `README.md`, and `AGENTS.md`.

### Learning Notes

- Day37 operates the durable PostgreSQL truth after Day36 made the schema deployable, and its spine is that **a reachable, low-CPU database is not a reliable system**: a slowing AI Job system at modest CPU can be exhausted connection pools, an `idle in transaction` session, and growing pool waits, and API `202` / Worker claim-complete / Attempt writes / Outbox checkpoints all depend on **bounded** capacity. Connection pools are finite, so total demand is the **sum across every process** (`(4 API + 12 Worker) * pool 10 = 160`) that must stay under a **safe connection budget** with reserve for migration/monitoring/admin/recovery — a pool max is potential demand, and raising pools moves queuing into PostgreSQL. The eight-minute Provider call runs **outside** the DB transaction across Accept / Claim-Start / External / Complete (with the current-token completion guard, `queued->running` in Claim and `running->succeeded` in Complete), and Provider success, Object Storage Artifact bytes, and committed PostgreSQL success are different facts — reconcile the deterministic Artifact before any second Provider call. Timeouts **contain** failure (`lock_timeout < statement_timeout < application deadline`; `idle_in_transaction_session_timeout` kills stuck open transactions; `SKIP LOCKED` is claim selection, not a timeout); a shared DB outage drops **readiness** and backs off rather than failing every liveness (restart storm); long/idle transactions retain snapshots and block Vacuum so you stop the source first and tune autovacuum per-table on evidence, never a casual `VACUUM FULL`; runtime identities cannot DDL and credentials rotate load-new -> verify-all -> recycle -> revoke-old; replication is **not** backup (it copies bad writes) and recovery evidence requires an isolated restore + PITR + integrity/business checks + measured RPO/RTO (which are recovery objectives, not health probes); and the 420-vs-300 incident is contained by rolling back the **pool configuration** and reconciling irreversible Provider effects, not by raising `max_connections`.
- The real classroom trajectory is preserved, including the honest starting `不知道`, the student-initiated Artifact-vs-success and transaction-numbering questions, and the terminology corrections (`mcvv` -> MVCC, `trash` -> dead tuples, `legacy snapchat` -> old MVCC snapshot). The two-pass final Chinese synthesis is recorded verbatim, and the correction between passes — that RPO/RTO are recovery objectives, not health probes — is documented as the student's own accepted revision.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day38 lesson exists and Day38 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day37 student quote appears in `Day37_Repository_Update_Input.md`; Markdown fence balance (lesson and runbook); relative-link resolution (including the new `runbooks/` cross-links); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets or connection strings in the runbook or lesson).
- **Day37 has NO runtime evidence — RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.** No PostgreSQL server or disposable cluster was started; no `psql`/SQL/configuration statement, connection pool, lock/timeout/deadlock, idle transaction, Vacuum/autovacuum/`VACUUM FULL`, role/grant/credential/Secret/rotation, Kubernetes probe/drain, base backup/WAL/PITR/isolated restore/integrity or business check, replica lag/promotion/split-brain, or managed service was run, measured, or inspected in class or during the repository update. Every number (`160`, `420`, `300`, the autovacuum settings, any RPO/RTO) is classroom arithmetic/design, not a measured result. Static arithmetic and static reasoning review were completed.
- Scope: no Day38 lesson was created; Redis is mentioned only as a future transient-state boundary; no SQLAlchemy/Alembic or Playwright content was added; the runbook invents no command output, PostgreSQL version, managed-service behaviour, benchmark, plan, restore time, or RPO/RTO achievement; the protected prompt/template files are unchanged; and no real secrets, connection strings, or production data were added.

---

## v0.1.77 — Day36 Fix: exception queue is triage, not migration completion

Date: 2026-07-22

### Fixed

- **The Backfill's exception/isolation queue was framed as if it resolved a Job.** `008` said an unknown legacy running Job is "routed to an exception/isolation queue" without changing its database row — which conflicts with the rest of the phased plan: such a row is still `job_status = 'running' AND lease_token IS NULL`, so it still counts in `remaining_targets` and still violates `jobs_running_requires_lease` at `VALIDATE`. Corrected the framing across `008` (Phase 5 backfill, its progress query, and the completion/verification block), the Day36 lesson (Concepts 5, 9, 10, Exercise 8, Mental Model Summary), the project README (phased-plan Backfill/Validate rows and encoded rules), the cheat sheet, the interview (intermediate backfill-scope and senior `NOT VALID`/`VALIDATE` questions and a weak/strong answer), and `PROJECT_STATUS.md`. The exception queue is now stated as **triage, not resolution**.
- **Made the truthful resolutions and completion/validate preconditions explicit.** An unknown legacy running Job can only: (a) have its Lease completed by a **trusted source**; or (b) be moved by a dedicated recovery / human reconciliation to a **semantically correct state that no longer violates the invariant** (never a fabricated `failed`/status); or (c) stay **unresolved**, in which case the migration is incomplete and `VALIDATE`/Switch/Contract must not run. `remaining_targets = 0` is a completion condition **only** when it is zero for the right reason (every violating running row truly resolved, not merely parked). `VALIDATE CONSTRAINT`'s hard precondition is stated: no violating running row may remain, or `VALIDATE` fails.

### Unchanged (verified)

- No fabricated Lease token; no Provider/Object Storage call inside the Backfill; unknown Jobs are never marked `failed` or any untrue status. The rest of Day36's scope, real student answers, Mental Model, and the conceptual-only validation boundary are unchanged: Day36 remains **NOT RUN** (no PostgreSQL, DDL, backfill, index, or production migration executed).

### Validation

- Static checks actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); SQL static review (the active statements are unchanged — nullable expand, `CHECK ... NOT VALID`, `VALIDATE`; the corrected exception-queue/precondition text is all in comments; `gen_random_uuid`, `CREATE INDEX CONCURRENTLY`, `DROP COLUMN`, `Provider`, `SQLAlchemy`, `Alembic` still comment-only; no fabricated token or `failed` status in active SQL); a consistency check that every Day36 file now describes the exception queue as triage and ties `remaining_targets = 0` / `VALIDATE` to truthful resolution; Markdown fence balance; and relative-link resolution.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No PostgreSQL server, `ALTER`, constraint, index build, `EXPLAIN`, backfill, or migration was run; this round changed only SQL comments and documentation wording.

---

## v0.1.76 — Day36 Schema Evolution and Safe Migrations

Date: 2026-07-22

### Added

- Added `docs/postgresql/day36-schema-evolution-and-safe-migrations.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day35->Day36 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/008_schema_evolution_and_safe_migrations.sql` — a safe-migration **DESIGN** reference pack that evolves the populated Day31/Day34 `app.jobs` into a Lease-aware model: preconditions, a compatibility matrix, and the phased Expand (nullable `claim_owner`/`lease_token`/`lease_expires_at`, no fabricated default) -> compatible code -> drain old Workers -> `CHECK ... NOT VALID` -> bounded idempotent `SKIP LOCKED` recovery/backfill (trusted source only, unknown ownership reconciled, no Provider calls) -> `VALIDATE CONSTRAINT` -> Switch -> Contract. The `NOT NULL` and `DEFAULT gen_random_uuid()` forms are commented **unsafe counter-examples**; the Day35 stale-lease index is a commented non-transactional `CREATE INDEX CONCURRENTLY` step with invalid-index handling; verification queries and rollback-vs-forward-fix boundaries are included.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day36 increment: the phased-plan table, the encoded rules, an explicit statement of what the pack does not contain, an authored (nothing executed) reproduction note, Day36 known gaps, and a separate Day36 validation matrix.
- Appended a Day36 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day36 Beginner/Intermediate/Senior questions to `interview/postgresql.md`, preserving the student's real answers verbatim — including the direct-`NOT NULL`-is-unsafe answer, the default-value reasoning, the running-only-scope and reconcile-unknown answers, the `SKIP LOCKED` and `NOT VALID` answers, the student-initiated backfill-scope question, the English answers, and the final Chinese synthesis (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day36 is the latest PostgreSQL lesson, and pointed the Day35 lesson's Next Lesson at the released Day36 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day36 completed with its released lesson/artifact (Day37 remains Planned).
- Updated `PROJECT_STATUS.md` (Day36 last completed with artifact + validation boundary; Current/Next is Day37 Planned / Not started), `TASKS.md` (completed Day36 blocks, Day36 preparation converted to history, Day37 preparation added), `README.md`, and `AGENTS.md`.

### Learning Notes

- Day36 turns the Day34 conceptual Lease and the Day35 conceptual stale-lease index into a compatible, versioned transition, and its spine is that **a migration is a versioned state transition across schema + existing data + every deployed application version** — a successful `ALTER` is not a completed migration. A direct `ADD COLUMN lease_token uuid NOT NULL` on a populated table is rejected **atomically** (existing rows have no value) and breaks old code, so you **Expand** with nullable columns and **no fabricated default** (old code ignores them, new code tolerates `NULL`; even a nullable `ADD COLUMN` is lock-aware). A default is a **business fact** for every row — `is_archived DEFAULT false` only if verified, `lease_token DEFAULT gen_random_uuid()` never (it fabricates an ownership epoch and risks a table rewrite), and `NULL` honestly means "no proved Lease ownership." **Backfill** is running-only but scope does not certify ownership: a running Job with a trusted source gets an idempotent guarded `UPDATE`, and an unknown one goes to the exception/isolation queue as **triage only** (a parked row still counts in `remaining_targets` and still violates the invariant) until it is truthfully resolved by a trusted backfill or a real recovery — never a fake token/status, and the backfill never calls the Provider. (v0.1.77 sharpened this triage-vs-resolution wording.) Old Workers must be **drained** before recovery/switch because they bypass the token guard and double-execute; the backfill is batched/short-transaction/idempotent/restartable with the target predicate repeated in selection and the guarded write so the **DB state is the checkpoint**, and `FOR UPDATE SKIP LOCKED` takes distinct parallel batches. `CHECK ... NOT VALID` protects **new** writes immediately while deferring the historical scan to `VALIDATE CONSTRAINT`; `CREATE INDEX CONCURRENTLY` is non-transactional (cannot run in `BEGIN/COMMIT`) and can leave an unusable **invalid** index (validity separate from net benefit); **Switch** requires every writer to guard the token and the old path to no longer write; **Contract** is destructive and evidence-gated; and **rollback vs forward fix** is decided by durable state — after real Lease data or external side effects, forward-fix and reconcile.
- The real classroom trajectory is preserved, including the student-initiated question about whether detailed backfill was out of scope (it is Day36 scope, resolved in-lesson), and the corrected reasonings (the `NOT NULL` failure is atomic; the UUID default's real harm is fabricated ownership + rewrite, not recognition; `is_archived` **is** a business fact; `NOT VALID` protects new writes rather than being inactive). Final-synthesis precisions are corrected as Tech Lead commentary, not rewritten into the student's words.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day37 lesson exists and Day37 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day36 student quote appears in `Day36_Repository_Update_Input.md`; Markdown fence balance; relative-link resolution; status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; SQL static review of `008` (balanced parentheses; the only active statements are the nullable `ADD COLUMN` expand, the `CHECK ... NOT VALID` constraint, and `VALIDATE CONSTRAINT`, all referencing existing/added Day31 columns; `gen_random_uuid()`, `NOT NULL DEFAULT`, `CREATE INDEX CONCURRENTLY`, `DROP COLUMN`, `is_archived`, `Provider`, `SQLAlchemy`, and `Alembic` appear only in comment lines); and a secret scan.
- **Day36 has NO runtime evidence — Final artifact PostgreSQL Runtime: NOT RUN.** No PostgreSQL server, `ALTER`, constraint, index build, `EXPLAIN`, backfill, benchmark, Provider/Object Storage integration, production DDL, or rollback command was run in class or during the repository update. The lock/rewrite/rollout behaviours (nullable `ADD COLUMN` still lock-aware; `NOT NULL` rejected atomically; volatile-default rewrite risk; `NOT VALID` vs `VALIDATE` scan; `CREATE INDEX CONCURRENTLY` non-transactional and possibly invalid) are reasoned about, not measured. Application/Worker compatibility, old-Worker drain, token-guard Switch, and disposable-cluster DDL/backfill: NOT RUN. Live operation is Day37; `SQLAlchemy`/`Alembic` are Phase 4; fencing is Day41: NOT RUN.
- Scope: no Day37 lesson was created; no executed DDL, `SQLAlchemy`/`Alembic`, live-operations, or fencing content was added; the artifact does not fabricate a historical owner/token/expiry and gives terminal/queued Jobs no Lease; the protected prompt/template files are unchanged; and no credentials, real connection strings, signed URLs, or production data were added.

---

## v0.1.75 — Day35 Review Fix: mutually-exclusive history candidates + accurate maintenance note

Date: 2026-07-22

### Fixed

- **The two tenant-history index candidates were active `CREATE INDEX` statements.** `007` created both `jobs_tenant_history_idx (tenant_id, created_at DESC, job_id DESC)` and `jobs_tenant_status_history_idx (tenant_id, job_status, created_at DESC, job_id DESC)` if the pack were run — but the lesson says a history index is retained only after representative `EXPLAIN (ANALYZE, BUFFERS)` and net-benefit evidence, and Section 8's worked decision actually rolls a broad history/status index back. Both are now **commented, mutually-exclusive candidates** (2a all-status, 2b dynamic-status, 2c fixed-status partial), with a note that running the pack creates neither and at most one is retained on positive net-benefit evidence. No `IF NOT EXISTS` was added (that would hide the design choice). The claim Partial Composite and the Outbox Partial remain the two active candidate designs (independent access paths on different tables).
- **The queued -> running maintenance note was inconsistent with the active/candidate indexes.** Section 7 previously concluded "the transition touches the claim index only, not the history/idempotency ones," which was wrong given the once-active dynamic-status candidate contains `job_status`. Rewritten in both `007` Section 7 and the lesson (Concept 14) to be accurate and conditional: among the indexes the pack actually creates, `queued -> running` maintains the claim partial index only (the Outbox partial is on another table; the implicit Day31 unique index is unchanged); and **if** a history candidate is ever retained, an all-status `(tenant_id, created_at DESC, job_id DESC)` index would be unchanged while a dynamic-status index whose key includes `job_status` **would be maintained**.
- Synced the project README Day35 increment table so the two history rows are labelled **commented candidates** and marked mutually exclusive, and added an intro line stating the pack's two active designs vs the commented history candidates.

### Unchanged (verified)

- The claim Partial Composite `(tenant_id, created_at, job_id) WHERE job_status = 'queued' AND cancel_requested = false` and the Outbox Partial `(created_at, outbox_event_id) WHERE published_at IS NULL` remain the active candidate designs; no duplicate of the Day31 `UNIQUE (tenant_id, idempotency_key)` unique B-tree; the `lease_expires_at`/`lease_token`/`claim_owner` stale-lease design stays conceptual/commented (no active SQL, no `now()` predicate); no migration, `CREATE INDEX CONCURRENTLY`, `DROP INDEX`, or production deployment step was added (Day36); and **Day35 still has no PostgreSQL runtime, `EXPLAIN`, `EXPLAIN ANALYZE`, benchmark, production DDL, or rollback evidence**.

### Validation

- Static checks actually performed: `git diff --check`; changed-file scope (four files); protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); SQL static review confirming exactly the claim and Outbox Partials are the active `CREATE INDEX` statements, that no two mutually-exclusive history indexes are created by running the pack, balanced parentheses, the lease fields comment-only, and no active `CREATE INDEX CONCURRENTLY`/`ALTER`/`DROP`/`now()`/`EXPLAIN`/`IF NOT EXISTS`; a consistency check that the queued -> running maintenance note matches the active/candidate indexes; Markdown fence balance; and relative-link resolution.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No PostgreSQL server, `EXPLAIN`, `EXPLAIN ANALYZE`, statistics refresh, representative data, benchmark, production DDL, or rollback command was run. This round changed only SQL comments and documentation wording.

---

## v0.1.74 — Day35 PostgreSQL Indexes and Query Planning

Date: 2026-07-22

### Added

- Added `docs/postgresql/day35-postgresql-indexes-and-query-planning.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day34->Day35 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/007_postgresql_indexes_and_query_planning.sql` — an index/`EXPLAIN` **design** reference pack over the Day31/Day34 access paths: the claim Partial Composite `(tenant_id, created_at, job_id) WHERE job_status = 'queued' AND cancel_requested = false`; tenant history candidates (all-status, dynamic-status shared composite, and a fixed-status partial alternative); the Outbox Partial `(created_at, outbox_event_id) WHERE published_at IS NULL`; a deliberate **no-duplicate** note for the Day31 `UNIQUE (tenant_id, idempotency_key)` index; parameterized `EXPLAIN` / `EXPLAIN ANALYZE` templates with honest row-lock/DML side-effect labels; an index-maintenance analysis of `queued -> running`; and a conceptual-only stale-lease design that rejects a `now()` partial predicate.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day35 increment: the index-candidate table, the encoded rules, an explicit statement of what the pack does not contain, an authored (nothing executed) `EXPLAIN` reproduction that flags every plan number as a classroom scenario, Day35 known gaps, and a separate Day35 validation matrix.
- Appended a Day35 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day35 Beginner/Intermediate/Senior questions to `interview/postgresql.md`, preserving the student's real answers verbatim — including the "我不知道加什么索引" starting point, the "event列" history-reason misconception, the Seq-Scan-proves-failure answer, the English answers, and the final Chinese synthesis with its Composite-Index imprecision (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day35 is the latest PostgreSQL lesson, and pointed the Day34 lesson's Next Lesson at the released Day35 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day35 completed with its released lesson/artifact (Day36 remains Planned).
- Updated `PROJECT_STATUS.md` (Day35 last completed with artifact + validation boundary; Current/Next is Day36 Planned / Not started), `TASKS.md` (completed Day35 blocks, Day35 preparation converted to history, Day36 preparation added), `README.md`, and `AGENTS.md`.

### Learning Notes

- Day35 turns the Day34 claim and the Day33 write paths into measured, cost-aware index designs, and its spine is: an index is an **additional access structure over the Heap**, not a replacement source of truth — `FOR UPDATE SKIP LOCKED` still visits and locks the real tuple, so an index speeds candidate lookup but not ownership. Design the index from the **real query shape** (leading equality predicates, then range/`ORDER BY` columns): the claim gets a Partial Composite `(tenant_id, created_at, job_id) WHERE job_status='queued' AND cancel_requested=false`, the Outbox gets a Partial `(created_at, outbox_event_id) WHERE published_at IS NULL` (with `job_id` selected but not a key), and the idempotency lookup gets **nothing new** because the `UNIQUE (tenant_id, idempotency_key)` constraint already created a usable unique B-tree. History is several distinct paths chosen by measured workload, not one default. `now()` cannot define partial membership (membership changes only on a write), so expiry is a query-time range on a stable "running" predicate — and the lease columns are Day36. `EXPLAIN` estimates a plan while `EXPLAIN ANALYZE` really executes it (row locks on `SELECT ... FOR UPDATE`, real DML changes); a Sequential Scan is a cost-based and possibly optimal plan judged by selectivity / `Rows Removed by Filter` / latency / buffers, not by its name; an estimate-vs-actual divergence is a statistics/skew investigation before another index; and the keep/rollback decision is made on **net system benefit** (a broad history index that moved history p95 100->80 ms but Job acceptance p99 50->220 ms and cost +14 GB with no Worker/Outbox gain is rolled back).
- The real classroom trajectory is preserved, including the honest starting uncertainty ("我不知道加什么索引"), the corrected history-index reason (it omits the rows, not "a column is missing"), and the Seq-Scan-proves-failure misconception. Final-synthesis imprecisions (a Composite Index means multiple ordered key columns, not "no restriction"; statistics estimate cost rather than mechanically decide optimization; the decision is net system benefit, not "extra profit") are corrected as Tech Lead commentary, not rewritten into the student's words.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day36 lesson exists and Day36 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day35 student quote appears in `Day35_Repository_Update_Input.md`; Markdown fence balance; relative-link resolution; status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; SQL static review of `007` (balanced parentheses; active `CREATE INDEX` design statements whose keys and partial predicates all reference existing Day31 columns; the claim and Outbox candidates match the required shapes exactly; **no** duplicate index for the unique idempotency constraint; the lease fields `claim_owner`/`lease_token`/`lease_expires_at` appear only in comment lines; no active `CREATE INDEX CONCURRENTLY`/`ALTER`/`DROP`/`now()`/`EXPLAIN`); and a secret scan. (v0.1.75 later commented the two mutually-exclusive tenant-history candidates so they are not created simultaneously.)
- **Day35 has NO runtime evidence — Final artifact PostgreSQL Runtime: NOT RUN.** No PostgreSQL server, `EXPLAIN`, `EXPLAIN ANALYZE`, statistics refresh, representative data, benchmark, production DDL, production load test, or rollback command was run in class or during the repository update. Every plan number quoted (the 8,000,000-row Seq Scan with ~0.2% queued / ~1.6 s / ~7,900,000 `Rows Removed by Filter`, the estimate-1-vs-actual-20,000 case, and the 100->80 / 50->220 / +14 GB broad-index decision) is a classroom scenario for reasoning, not a measured result and not the output of any executed plan or DDL. Application/driver/Celery benchmark and representative-data load: NOT RUN. Safe index deployment (`CREATE INDEX CONCURRENTLY`, DDL-lock windows, rollout/rollback) is Day36: NOT RUN. Production load/performance, RLS/roles, backups, HA, deployment: NOT RUN.
- Scope: no Day36 lesson was created; no `CREATE INDEX CONCURRENTLY`, `ALTER`, `DROP`, migration, ORM, or `now()`-predicate index was added; the conceptual lease columns were not created; the Day35 artifact makes no claim that any plan, benchmark, or DDL was executed; the protected prompt/template files are unchanged; and no credentials, real connection strings, signed URLs, or production data were added.

---

## v0.1.73 — Day34 Review Fix: precise SKIP LOCKED outcome (may return another Job, or zero rows)

Date: 2026-07-22

### Fixed

- **Removed an absolute `SKIP LOCKED` outcome claim.** The v0.1.72 cancel-vs-claim ordering said that when the cancellation transaction currently holds the row lock, `SKIP LOCKED` skips it and the Worker "takes another/a different Job." That overstates the guarantee. `FOR UPDATE SKIP LOCKED` only skips currently-locked rows and keeps scanning for other rows matching the predicate; it **may** return another eligible Job, but if none is available it returns **zero rows** and the Worker backs off. Reworded the second ordering in the `006` SQL comment, the Day34 lesson (Concept 4 ordering block), the project README rules-encoded block, the cheat sheet eligibility paragraph, and the v0.1.72 CHANGELOG bullet to: "SKIP LOCKED skips that row and keeps scanning; it may return another eligible Job, or 0 rows if none is available (then the Worker backs off without waiting)." This is now consistent with the existing zero-row control-flow contract in `006` (0 rows -> no eligible unlocked Job right now -> COMMIT/ROLLBACK and back off -> normal, not an error).

### Scope

- Wording/comment correction only. The `cancel_requested = false` predicate remains in the candidate `SELECT`, the guarded `UPDATE`, the optimistic example, and the conceptual lease claim; the active transaction structure is unchanged; the three cancel-vs-claim orderings remain complete and accurate; the defensive-boundary rationale for the `UPDATE` re-check is unchanged. No cancellation state machine, no invented cancellation `UPDATE`, no new columns/migration (Day36), no index/`EXPLAIN` (Day35), no fencing token (Day41), no ORM/Redis; lease fields stay commented/conceptual; no student answer changed.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope (`006` SQL, the Day34 lesson, the project README, the cheat sheet, and this `CHANGELOG`); protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); a full-repository sweep confirming no file outside this corrective CHANGELOG entry still asserts the Worker "takes another/a different Job" unconditionally; a consistency check that every claim description now says `SKIP LOCKED` may return another eligible Job or zero rows, matching the `006` zero-row control-flow contract; SQL static review (both boundaries still filter `tenant_id` + `job_status = 'queued'` + `cancel_requested = false`; Attempt/Event inserted only after the one-row guarded `UPDATE`; lease fields `claim_owner`/`lease_token`/`lease_expires_at` still comment-only; balanced parentheses and one `BEGIN`/`COMMIT` claim transaction; no `CREATE INDEX`/`EXPLAIN`/`ALTER`); Markdown fence balance; and relative-link resolution.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available, so the corrected `006` was reviewed statically but **not** executed; the `SKIP LOCKED` outcomes were reasoned about, not run. The reduced-schema PostgreSQL 14.18 classroom evidence (three concurrency tests) is unchanged historical evidence and is not reused as proof. Application/driver/Celery multi-Worker, a real cancel-vs-claim race, lease heartbeat/renewal/takeover, Provider idempotency, Object Storage, Redis, and Day35 index plans remain NOT RUN.

---

## v0.1.72 — Day34 Review Fix: correct the cancel-vs-claim concurrency semantics

Date: 2026-07-22

### Fixed

- **Removed an inaccurate lock-semantics claim.** The v0.1.71 documentation said the guarded `UPDATE` re-checks `cancel_requested = false` because "a cancel transaction may commit between the SELECT and UPDATE," and that "the row lock plus the two COMMIT orders decide the winner, and the loser returns zero rows." Both are wrong for this claim transaction: after the `SELECT ... FOR UPDATE SKIP LOCKED` succeeds, the Worker holds the target `app.jobs` row's **exclusive lock** until the claim transaction commits or rolls back, so another transaction **cannot** commit a same-row `cancel_requested` change between the locking `SELECT` and the `UPDATE` — it must wait for the lock. And because the repository does not define the cancellation transaction's guarded `UPDATE`, there is no basis to assert a generic "loser returns zero rows."
- **Unified the correct three-ordering model** across the `006` SQL comment, the Day34 lesson (Concept 4), the project README rules-encoded block, and the cheat sheet claim block:
  - cancellation commits **first** -> the candidate `SELECT`'s eligibility predicate already excludes the Job; it is never claimed;
  - cancellation currently **holds the row lock** (uncommitted) -> `SKIP LOCKED` skips that row and keeps scanning; it may return another eligible Job, or 0 rows if none is available (then the Worker backs off without waiting);
  - the claim **locks first** -> the cancellation transaction waits, the claim finishes `queued -> running` and commits, and the cancellation path then re-evaluates the current state under its **own** guarded policy (which Day34 does not define).
- **Kept the guarded `UPDATE`'s `cancel_requested = false` re-check**, now with the correct rationale: it is a **defensive** final state-transition boundary that carries full eligibility for a direct `UPDATE`, the optimistic path, and any future refactor that splits the `SELECT` from the `UPDATE`. The predicate remains in the candidate `SELECT`, the guarded `UPDATE`, the optimistic example, and the conceptual lease claim.

### Scope

- Wording/comment correction only. The `cancel_requested = false` predicate from v0.1.71 is retained everywhere; no cancellation state machine was designed, no cancellation `UPDATE` SQL was invented, no new columns/migration (Day36), no index/`EXPLAIN` (Day35), no fencing token (Day41), no ORM/Redis. The lease state machine stays commented/conceptual, and no student answer was changed.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope (`006` SQL, the Day34 lesson, the project README, the cheat sheet, and this `CHANGELOG`); protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); SQL static review (the `FOR UPDATE SKIP LOCKED` candidate `SELECT` and the guarded `UPDATE` both still filter `tenant_id` + `job_status = 'queued'` + `cancel_requested = false`; Attempt/Event inserted only after the one-row guarded `UPDATE`; lease fields `claim_owner`/`lease_token`/`lease_expires_at` still comment-only; balanced parentheses and one `BEGIN`/`COMMIT` claim transaction; no `CREATE INDEX`/`EXPLAIN`/`ALTER`); a cross-file contradiction sweep confirming no file still says a same-row cancel can commit between the locking `SELECT` and the `UPDATE` or that "two COMMIT orders decide the winner / the loser returns zero rows"; Markdown fence balance; and relative-link resolution.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available, so the corrected `006` was reviewed statically but **not** executed; the concurrent cancel-vs-claim orderings were reasoned about, not run. The reduced-schema PostgreSQL 14.18 classroom evidence (three concurrency tests) is unchanged historical evidence and is not reused as proof. Application/driver/Celery multi-Worker, a real cancel-vs-claim runtime race, lease heartbeat/renewal/takeover, Provider idempotency, Object Storage, Redis, and Day35 index plans remain NOT RUN.

---

## v0.1.71 — Day34 Review Fix: exclude cancellation-requested Jobs from the claim

Date: 2026-07-22

### Fixed

- **The Worker claim could claim a Job whose cancellation was already committed.** The Day34 `006` claim checked only `tenant_id` and `job_status = 'queued'`, but the Day31 `app.jobs` also carries `cancel_requested boolean NOT NULL DEFAULT false`. A Job with a committed `cancel_requested = true` can still be `job_status = 'queued'` for a moment, so the claim could move it to `running`, write an Attempt and `job_started` Event, and incur an unnecessary Provider cost. Added `AND cancel_requested = false` to **both** database boundaries of the active claim transaction: the `FOR UPDATE SKIP LOCKED` candidate `SELECT` and the guarded `queued -> running` `UPDATE`. The `UPDATE` repeats it as a defensive final state-transition boundary (protecting direct-update, optimistic, and future-refactored paths). Attempt/Event inserts remain gated on the one-row `RETURNING` result. (v0.1.71 stated the rationale imprecisely; v0.1.72 corrects the lock semantics — the `FOR UPDATE SKIP LOCKED` lock prevents a same-row cancel from committing between the locking `SELECT` and the `UPDATE`.) The plain visibility `SELECT`, the optimistic alternative, and the conceptual lease-claim pseudocode were updated to match.
- Synced the claim predicate everywhere it is shown or described so no file contradicts the SQL: the Day34 lesson (Concept 4 gains an "eligibility, not just status" note and the Day35 prep checklist lists `cancel_requested = false`), `projects/ai-backend-data-layer/README.md` (the Part 1 table row, the rules-encoded block, and the reproduction shape), and `cheat_sheets/postgresql.md` (the claim-transaction block). Each states that a committed-cancel queued Job must not be claimed by a new Worker. (The concurrency rationale in that round was imprecise and is corrected in v0.1.72: the `FOR UPDATE SKIP LOCKED` lock prevents a same-row cancel from committing between the locking SELECT and the UPDATE.)

### Scope

- One eligibility predicate only — not a cancellation state machine. No new columns, no `ALTER`/migration (Day36), no `CREATE INDEX`/`EXPLAIN` (Day35), no fencing-token design (Day41), no ORM/Redis. The lease state machine stays commented/conceptual. Real student answers were not touched.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope (four files); protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); SQL static review of `006` (the `FOR UPDATE SKIP LOCKED` candidate `SELECT` and the guarded `UPDATE` both filter `tenant_id` + `job_status = 'queued'` + `cancel_requested = false`; Attempt/Event still inserted only after the one-row guarded `UPDATE`; the lease fields `claim_owner`/`lease_token`/`lease_expires_at` remain in comment lines only; balanced parentheses and one `BEGIN`/`COMMIT` claim transaction; no `CREATE INDEX`/`EXPLAIN`/`ALTER`); a cross-file check that the SQL, lesson, project README, and cheat sheet no longer show a contradictory claim predicate; Markdown fence balance; and relative-link resolution.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available, so the updated `006` claim (including the new `cancel_requested = false` predicates) was reviewed statically but **not** executed. The reduced-schema PostgreSQL 14.18 classroom evidence (three concurrency tests) is unchanged historical evidence and is not reused as proof of the final file. Application/driver/Celery multi-Worker, lease heartbeat/renewal/takeover, Provider idempotency, Object Storage, Redis, and Day35 index plans remain NOT RUN.

---

## v0.1.70 — Day34 Concurrency Control, MVCC, and Worker Claims

Date: 2026-07-22

### Added

- Added `docs/postgresql/day34-concurrency-control-mvcc-and-worker-claims.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day33->Day34 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/006_concurrency_control_mvcc_and_worker_claims.sql` — a concurrency claim pack over the Day31 model. **Active** (Day31 columns only): a `FOR UPDATE SKIP LOCKED` claim transaction that reserves one queued candidate by tenant/status/order, reuses the unchanged Day33 guarded `queued->running` write with explicit affected-row control-flow gates, inserts the Attempt + `job_started` Event on the one-row path, and commits before the Provider call; plus an optimistic alternative and consistent-lock-order / bounded-retry guidance. **Conceptual only** (commented, not runnable): the application lease state machine (`claim_owner`/`lease_token`/`lease_expires_at` claim/renew/takeover/completion), whose columns do not exist in the Day31 schema and are a Day36 migration.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day34 increment: the active-vs-conceptual boundary table, the encoded rules, an explicit statement of what the pack does not claim, an authored (final 006 not executed) reproduction that separates the reduced classroom schema from the Day31 schema, Day34 known gaps, and a separate Day34 validation matrix.
- Appended a Day34 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day34 Beginner/Intermediate/Senior questions to `interview/postgresql.md`, preserving the student's real answers verbatim — including the initial visibility-as-ownership answer, the reversed optimistic-vs-pessimistic choice, the broken-English MVCC/SKIP LOCKED/lease answers, and the final Chinese synthesis with its lease-expiry-vs-token imprecision (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day34 is the latest PostgreSQL lesson, and pointed the Day33 lesson's Next Lesson at the released Day34 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day34 completed with its released lesson/artifact (Day35 remains Planned).
- Updated `PROJECT_STATUS.md` (Day34 last completed with artifact + validation boundary; Current/Next is Day35 Planned / Not started), `TASKS.md` (completed Day34 blocks, Day34 preparation converted to history, Day35 preparation added), `README.md`, and `AGENTS.md`.

### Learning Notes

- Day34 makes the Day33 atomic write safe under many competing Workers, and its spine is **visibility != ownership**: a plain `SELECT` (or MVCC snapshot) shows candidates, ownership is a transaction-local `FOR UPDATE` row lock, and ownership that must survive COMMIT is a **committed lease** (owner + token + expiry). The claim is `FOR UPDATE SKIP LOCKED` (skip locked rows, reserve the next available so Workers spread) wrapped around the **unchanged** Day33 guarded write, committed before the Provider call runs outside any transaction. `SKIP LOCKED` weakens fairness (ORDER BY sorts only available rows; no strict FIFO; starvation possible), a released lock is **not** liveness evidence (committed Job/Attempt/Event persist; blind reclaim duplicates Attempt/Event/Provider cost), and lease expiry is a **takeover condition, not proof of death** — takeover writes a new `lease_token` while expiry alone invalidates ownership through the time predicate, and completion guards current token + running + unexpired lease. The `lease_token` (one ownership epoch) is kept separate from the **stable Provider idempotency key** (same external operation, derived from the durable `attempt_id` and actually sent to a supporting Provider). Under MVCC, Read Committed takes a new snapshot per statement (100 then 101 is an allowed phantom), while Repeatable Read/Serializable keep a stable snapshot that may abort with `40001` and never partition work; a reverse-order deadlock is detected and one victim aborts with `40P01`, a consistent lock order prevents the cycle, `lock_timeout` bounds waits (`55P03`), and the **application** — not PostgreSQL — retries with a finite budget while `UNIQUE`/idempotency constraints still stop duplicate durable facts.
- The real classroom trajectory is preserved, including the two instructive errors: the student first said both Workers that selected the same row had claimed it (visibility mistaken for ownership) and initially chose optimistic concurrency because `SKIP LOCKED` "skips" — which is precisely why pessimistic reservation suits a contended queue. The final-synthesis imprecision (that lease expiry itself voids the token) is corrected as Tech Lead commentary, not rewritten into the student's words.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day35 lesson exists and Day35 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day34 student quote appears in `Day34_Repository_Update_Input.md`; Markdown fence balance; relative-link resolution; status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; SQL static review of `006` (balanced parentheses, one `BEGIN`/`COMMIT` claim transaction, active `FOR UPDATE SKIP LOCKED`, every active INSERT column present in `001` + `003`, the lease fields present only in commented lines, no `CREATE INDEX`/`EXPLAIN`/`ALTER`/`DROP`/migration/ORM/Redis, SQLSTATEs documented); and a secret scan.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available in the repository-update environment, so no statement in `006` was parsed or executed by PostgreSQL. Classroom evidence is reported separately and at its true level: a disposable **PostgreSQL 14.18** cluster on a **reduced** `jobs(job_id text, job_status text, created_at integer)` schema (NOT the Day31 schema, NOT this file) passed three concurrency tests (`FOR UPDATE SKIP LOCKED` returning job-B while job-A was locked; ordinary `FOR UPDATE` cancelled with `55P03` under `lock_timeout`; a reverse-order deadlock aborted with `40P01`). An initial restricted-sandbox `initdb` failed with `shmget: Operation not permitted` (environment evidence, not a SQL failure). That reduced run is **not** reused as proof of the repository file and never ran the Day31 schema, the claim's Attempt/Event inserts, or any lease field. Application/driver/Celery multi-Worker, lease heartbeat/renewal/takeover, stale-token Completion, Provider idempotency, Object Storage, Redis, crash/restart recovery, long-duration fairness, SERIALIZABLE workload: NOT RUN. Day35 index plans and production validation: NOT RUN.
- Scope: no Day35 lesson was created; the lease columns were **not** added and no `ALTER`/migration was written (Day36); no `CREATE INDEX`/`EXPLAIN` (Day35), ORM, or Redis locking was added; no claim that `SKIP LOCKED` gives strict FIFO/complete snapshots/eventual service, that lease expiry proves death or changes its own token or revokes external work or makes a Provider retry safe, that a lease token is a Provider idempotency key, or that PostgreSQL auto-retries `40P01`/`40001`; the protected prompt/template files are unchanged; and no credentials, real connection strings, signed URLs, or production data were added.

---

## v0.1.69 — Day33 Consistency Fixes (Codex re-review)

Date: 2026-07-22

### Fixed

- **`provider_request_id`-as-recovery-anchor residuals purged.** Several Day33 lesson summaries still implied the Provider-returned `provider_request_id` was a recovery/dedup control, contradicting the two-identifier model established in v0.1.68. Corrected AI Backend **Connection 3** (duplicate Provider work), **Mental Model Summary #8**, **Exercise 6** verification, **Today's Takeaway**, and the **Before Next Lesson Checklist**. All now state that the recovery anchor is a **pre-call idempotency / correlation key made durable (`attempt_id`) and actually SENT to the Provider**, valid **only** when the Provider supports idempotency/lookup; the returned `provider_request_id` is a lookup convenience persisted only in Transaction C and can be lost to a crash before it, so it cannot support recovery alone. Tightened Concept 8 and the cheat sheet so durability of `attempt_id` alone is not claimed to guarantee Provider-side recovery.
- **Unconditional-success-Outbox residuals purged.** The final SQL already left `job.succeeded` conditional, but Transaction C's header comment still called the Outbox intent a fixed member of the atomic bundle. Reworded the `005` Transaction C header and its integrated-rollback note to state that Attempt finish, guarded Job succeeded, Result Artifact, and the success Event are the **fixed** members, while the success Outbox intent joins the transaction (and rolls back with it) **only when a concrete downstream integration contract is configured** — otherwise no success Outbox row is created. Reworded lesson **AI Backend Connection 4** to match, and marked the intermediate interview strong answer's Outbox mention as conditional.
- **Recovered two lost v0.1.68 interview edits.** A mid-script failure in the previous round meant two intended interview edits never landed: the completion-rollback Chinese explanation still read `Outbox intent 在回滚后`, and a Weak/Strong answer still read `a durable Job must exist iff a durable Outbox intent exists`. Both are now applied — the rollback note reads "any Outbox row (the `job.succeeded` Outbox is conditional)", and the Weak/Strong answer reads the creation-time coupling rather than a permanent equivalence.

### Consistency

- Full-repository search across all Day33 files for `stable provider_request_id`, `provider_request_id is the recovery anchor`, `Transaction B persists provider_request_id`, `every completion writes an Outbox`, `success Outbox is mandatory`, `Transaction C always includes an Outbox`, an unmarked `Attempt + Job + Artifact + Event + Outbox` bundle, and a permanent `Job exists <=> Outbox row exists`: no remaining occurrences carry the stale meaning; every surviving match is an explicit negation, a creation-time coupling, or an accurately-contextualized historical note (e.g. the reduced classroom run that tested an unconditional Outbox, now flagged as superseded by the conditional final artifact).
- Confirmed the earlier fixes remain intact: the `AND finished_at IS NULL` Attempt-finish guard; zero-row ROLLBACK/stop/isolation; no overwrite of a finished Attempt's evidence; the Job Event vs Outbox Event distinction; the commented-out default `job.succeeded` Outbox; the stable-ids-only payload rule (no bytes, secrets, or signed URLs); the non-attributed Mental Model Evolution; the acceptance-time Job + dispatch Outbox creation-time coupling; and the NOT RUN runtime status.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); LESSON_TEMPLATE_v2 16-section order unchanged; Markdown fence balance; relative-link resolution; SQL static review of `005` (balanced parentheses, three `BEGIN`/`COMMIT` pairs, `finished_at IS NULL` guard present, `job.succeeded` INSERT still commented out, active INSERT columns present in `001` + `003`, no `FOR UPDATE`/`SKIP LOCKED`/`CREATE INDEX`/`EXPLAIN`/`DROP`/`ALTER`/ORM, no schema change); a stale-phrasing contradiction sweep; a quote-provenance check that every Day33 student quote still appears in `Day33_Repository_Update_Input.md` with exactly one `不知道`; status-file consistency; and a secret scan.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available. This round changed only documentation wording and SQL comments (no executable SQL statement changed), so nothing new was executed. The reduced classroom PostgreSQL 14.18 run is unchanged historical evidence and is **not** reused as proof of the final file.
- Scope: wording/comment consistency only. No schema change, no migration, no Day34 concurrency/locks/MVCC/isolation content, no change to any student answer, and no change to the protected prompt/template files.

---

## v0.1.68 — Day33 Review Fixes (Codex)

Date: 2026-07-22

### Fixed

- **Transaction C could overwrite a finished Attempt's evidence.** The Attempt-finish `UPDATE` in `005` located the Attempt by `attempt_id` + `job_id` only, so a second completion could overwrite `finished_at` / `provider_request_id` / `cost_micros` on an already-finished Attempt. Added `AND finished_at IS NULL` as a guard: zero rows now means the Attempt is missing, belongs to another Job, **or is already finished** — ROLLBACK and stop in every case. An already-finished current Attempt on a still-running Job is Day32's `running_with_finished_current_attempt`, which is **isolated and reconciled**, never auto-"fixed" to succeeded by Transaction C. Synced to the lesson (Concept 12), project README (correctness guards + query table + rules), cheat sheet, and interview.
- **Recoverable Provider identity.** Transaction B previously left `provider_request_id` NULL until Transaction C, and the external-phase comment wrongly implied a persisted returned id was the recovery handle — leaving a real failure window (crash after the Provider call but before C loses the returned id). Documented two **distinct** identifiers: the **pre-call** `provider_idempotency_key` / correlation key generated from an already-durable fact (`attempt_id`, committed in Transaction B) and sent to the Provider when it supports idempotency keys — the recovery anchor — versus the Provider-**returned** `provider_request_id`, which does not exist until the call returns and is persisted only in Transaction C. Corrected the false claim that Transaction B persists a returned id. **No schema change** was introduced (`attempt_id` already exists). If the Provider has no idempotency support, the artifact and prose state that PostgreSQL cannot close the unknown-outcome window: such an Attempt is isolated and reconciled, never blindly retried. Synced to the SQL, lesson (Concepts 4 and 8), project README, cheat sheet, and interview.
- **`job.succeeded` Outbox was described as unconditional.** Added and unified the principle: a `job_events` row is **internal business history**, an `app.outbox_events` row is a **pending external integration duty**, and **not every Job Event needs an Outbox Event**. `job.accepted` has a real consumer (dispatch), so Accept keeps coupling the two writes; the completion `job.succeeded` Outbox is now **conditional** — `005` leaves it commented out because this project defines no downstream consumer, and it must be enabled only alongside a concrete notification/webhook/billing/indexing contract. Documented the payload rule everywhere: stable identifiers + minimal references only, no result bytes, no secrets, no short-lived signed URLs; the consumer fetches the authorized result via a stable reference; `outbox_event_id` is the consumer idempotency key; publication is at-least-once and never proves consumer business success. Synced to the SQL comments, lesson (Concept 9), project README, cheat sheet, and interview.
- **Fabricated Mental Model Evolution.** The Day33 lesson presented a synthesized description in quotes as if it were a student's words — `"Day32 queries can see partial or missing related facts, so I can detect and fix coherence gaps."` — which also contradicted Day32's established rule that queries provide repair evidence but never auto-repair. Replaced it with a non-attributed **Starting system limitation** and made the division of labour explicit: Day32 observes / classifies / supplies repair evidence; Day33 prevents partial commits **inside** the database; neither can undo an external side effect (only reconciliation can). No quotation is attributed to the student that the student did not say.

### Consistency

- Reworded the permanent `Job exists <=> Outbox row exists` phrasing to a **creation-time** coupling (create the Job together with its dispatch Outbox intent at acceptance) across the lesson, cheat sheet, project README, `CURRICULUM.md`, and `PROJECT_STATUS.md`, so it no longer overrides Outbox retention. Verified across all Day33 files that: the transaction pack is called a write-path convention/contract and never a schema invariant; no text claims PostgreSQL can prove the Provider succeeded; no text claims the Outbox proves Queue delivery or consumer business success; idempotency is described as preventing duplicate *processing*, not duplicate *publication*; database rollback is never described as reversing Provider cost or Object Storage bytes; and no Day34 concurrency/locks/isolation material was added. Real student answers and the single `不知道` were not altered.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); LESSON_TEMPLATE_v2 16-section order unchanged; Markdown fence balance; relative-link resolution; SQL static review of `005` (balanced parentheses, three `BEGIN`/`COMMIT` pairs, `finished_at IS NULL` guard present, every active INSERT column present in `001` + `003`, `job.succeeded` INSERT commented out, no `FOR UPDATE`/`SKIP LOCKED`/`CREATE INDEX`/`EXPLAIN`/`DROP`/`ALTER`/ORM, no schema change, no credentials); a quote-provenance check that every Day33 student quote still appears in `Day33_Repository_Update_Input.md` and exactly one `不知道` is attributed; a contradiction sweep for the flagged phrasings; status consistency; and a secret scan.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available during this review round, so the new guards (`finished_at IS NULL`, the conditional Outbox, the Provider-identity split) are static-reviewed only. The reduced classroom PostgreSQL 14.18 run (five listed tests) is unchanged historical evidence and is **not** reused as proof of the final file; that run never exercised these review-round guards. Application/Provider/Object Storage/Redis/Celery integration, a real Relay crash/restart, and consumer idempotency: NOT RUN. Day34 concurrency and production validation: NOT RUN.
- Scope: two SQL guards + one conditional-Outbox change + documentation only. No schema change, no migration, no Day34 lesson, no locks/indexes/`EXPLAIN`/ORM added; protected prompt/template files unchanged; no credentials or production data.

---

## v0.1.67 — Day33 PostgreSQL Transactions and Atomic State Changes

Date: 2026-07-22

### Added

- Added `docs/postgresql/day33-postgresql-transactions-and-atomic-state-changes.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day32->Day33 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/005_postgresql_transactions_and_atomic_state_changes.sql` — a driver-bound **transaction reference pack** over the Day31 model: Transaction A (Accept = Job + Outbox publication intent, COMMIT before `202`), Transaction B (Start = guarded `queued -> running` with database-side `attempt_count + 1` + Attempt + append-only `job_started` Event), an external Provider/Object Storage phase held **outside any transaction**, Transaction C (Complete = Attempt finish + guarded `running -> succeeded` with `finished_at` + Result Artifact + `job_succeeded` Event + Outbox intent), and the Relay checkpoint (`published_at IS NULL` -> publish with the same `outbox_event_id` -> `published_at = now()` after ack). Every guarded `UPDATE ... RETURNING` carries an explicit application control-flow contract, and Appendix A gives a runnable pure-SQL zero-row-gate demonstration.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day33 increment: the three-transaction + external-boundary table, the encoded rules, the zero-row control-flow contract, an authored (not executed) reproduction against a disposable cluster, Day33 known gaps, and a separate Day33 validation matrix.
- Appended a Day33 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day33 Beginner/Intermediate/Senior questions to `interview/postgresql.md`, preserving the student's real answers verbatim — including the broken-English interview answers, the `occure same time` and `avoid relay publish twice` misconceptions, and the final synthesis's delivery-label mistake (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day33 is the latest PostgreSQL lesson, and pointed the Day32 lesson's Next Lesson at the released Day33 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day33 completed with its released lesson/artifact (Day34 remains Planned).
- Updated `PROJECT_STATUS.md` (Day33 last completed with artifact + validation boundary; Current/Next is Day34 Planned / Not started), `TASKS.md` (completed Day33 blocks, Day33 preparation converted to history, Day34 preparation added), `README.md`, and `AGENTS.md`.

### Learning Notes

- Day33 turns the Day32 read-side coherence rules into write-side atomic commitments. A transaction is **one business commitment**: `BEGIN`/`COMMIT` makes all related database facts durable together and `ROLLBACK` discards the whole current transaction — but never a **prior** COMMIT, which is why a Job committed without its Outbox row (separate commits) is stuck forever. The Accept invariant is that a durable Job exists **iff** a durable Outbox publication intent exists, and `202 + job_id` is returned only after that COMMIT (a lost response is resolved by `UNIQUE (tenant_id, idempotency_key)` lookup, not the transaction). The Start transition, its Attempt, and its `job_started` Event share one transaction; **zero affected rows is a normal result the application must gate on** (unlike a SQL/constraint error that fails the transaction), or an ungated continue writes a duplicate Attempt/Event. The decisive boundary: PostgreSQL commits/rolls back only its own rows, so the AI Provider call and Object Storage write sit **outside** any transaction, between two short transactions — a long transaction across an eight-minute call pins a connection and may hold locks and an old snapshot, and still cannot undo the external call. A completion rollback discards every database fact but leaves the Provider cost and Object Storage bytes. The Transactional Outbox is durable publication intent (the Relay does not delete the row or reset `published_at` to NULL); `published_at IS NOT NULL` proves only that the Relay recorded a publish, not Queue delivery or consumer success. Delivery is **at-least-once + stable `outbox_event_id` + idempotent consumer** — exactly-once is not achieved by disabling retries (that is at-most-once and can lose messages). A correct pack is a **write-path contract**, not a schema guarantee: legacy separate-commit writers remain unsafe until drained.
- The real classroom record is preserved, including the two unresolved-after-correction mistakes: the final Chinese synthesis said PostgreSQL transactions **control** the external Provider (very likely a missing 「不能」, not silently rewritten) and mislabelled disabling retries as exactly-once. The polished delivery model is recorded as Tech Lead synthesis, not attributed to the student.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day34 lesson exists and Day34 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day33 student quote appears in `Day33_Repository_Update_Input.md`; Markdown fence balance; relative-link resolution; status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; SQL static review of `005` (balanced parentheses, three `BEGIN`/`COMMIT` pairs, every referenced column present in `001` + `003`, guarded `UPDATE ... RETURNING` with control-flow contracts, external phase outside any transaction, no `FOR UPDATE`/`SKIP LOCKED`/`CREATE INDEX`/`EXPLAIN`/`DROP`/`ALTER`/ORM, no exactly-once claim); and a secret scan.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available in the repository-update environment, so no statement in `005` was parsed or executed by PostgreSQL. Classroom evidence is reported separately and at its true level: a disposable **PostgreSQL 14.18** cluster ran a **reduced** validation schema and passed five listed tests (Job + Outbox atomic commit; duplicate Outbox id rolling the Job back; running Job + Attempt + Event coherence; duplicate Artifact key rolling the completion back; the Outbox `published_at` NULL->timestamp checkpoint; final marker `DAY33_REDUCED_RUNTIME_VALIDATION_PASS`). Test 5 validated **only** PostgreSQL's checkpoint, not Redis publication. An earlier restricted-sandbox bootstrap failed at cluster start with `shmget: Operation not permitted` (environment evidence, not a SQL failure). That reduced run is **not** reused as proof of the repository file. Application/FastAPI/driver/Provider/Object Storage/Redis/Celery integration, a real Relay crash/restart, and consumer idempotency: NOT RUN. Day34 concurrency, and production performance/RLS/backups/HA/deployment: NOT RUN.
- Scope: no Day34 lesson was created; no locks, `FOR UPDATE`, `SKIP LOCKED`, MVCC tuning, indexes, `EXPLAIN`, migrations, ORM, or Alembic were added; no exactly-once delivery claim; no claim that `published_at` proves external delivery or that rollback reverses Provider cost or Object Storage bytes; the protected prompt/template files are unchanged; and no credentials, real connection strings, signed URLs, or production data were added.

---

## v0.1.66 — Day32 Second-Round Review Fixes

Date: 2026-07-21

### Fixed

- **Query 4b selected a stale queued Event.** The CTE pre-filtered `WHERE e.to_status = 'queued'` and then took the newest match. For a Job that went `queued @ t1 -> running @ t2 -> failed @ t3` and was then requeued **without** that second queued Event being written, the query returned `t1` — a real row — and presented it as the current queued-stage start, producing a multi-hour age for a Job requeued moments ago. The CTE now selects each Job's **latest Event of any kind** (`SELECT DISTINCT ON (e.job_id) ... ORDER BY e.job_id, e.occurred_at DESC, e.event_id DESC`, with no `to_status` filter) and accepts it as the stage start only when `to_status = 'queued'`. The result set now reports the state of the evidence via `latest_event_at`, `latest_event_to_status`, `queued_since`, `queued_since_source`, `queued_stage_age`, and `event_history_status`, classified as: `recorded_queued_transition` (age is meaningful); `no_event_history_acceptance_fallback` (no Events exist at all, so `jobs.created_at` is used and the age is an explicit **upper bound**); and `event_history_inconsistent` (Events exist and `job_status` is `queued` but the latest Event is not — `queued_since` and `queued_stage_age` are left **NULL**, no older queued Event is substituted, and no precise-looking age is manufactured). `ORDER BY queued_since ASC NULLS FIRST` surfaces the inconsistent rows first. Synced to the project README query table, the Day32 lesson (Concept 5), and the cheat sheet. Event-history completeness is documented throughout as a **write-path convention, not a schema guarantee**, and `event_history_inconsistent` is described as a signal to investigate rather than a verdict about Worker behaviour.
- **Query 1 was documented as a backlog view it is not.** The project README called query 1 "the queue/backlog view", but the SQL filters on `tenant_id` only and therefore returns queued, running, succeeded, failed and cancelled Jobs. The SQL was **not** narrowed — the classroom contract is a Job detail / operational Job-Attempt view, and every lesson reference agrees. Instead the description was corrected in the README table, a `SCOPE:` block was added to the query's header comment, the lesson's query-contract block now states the scope explicitly, and `CURRICULUM.md`'s artifact summary no longer says "queue backlog". All three places state the queue-only variant explicitly as `AND j.job_status = 'queued'`, and the lesson adds the naming discipline: a query filtered on tenant alone must not be labelled a backlog view anywhere it is documented.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check; Markdown fence balance; relative-link resolution; LESSON_TEMPLATE_v2 16-section order unchanged; assertion that the query 4b CTE contains **no** `to_status` pre-filter; assertion that the inconsistent branch yields NULL `queued_since`/`queued_stage_age` and does not reference an older queued Event; assertion that the acceptance fallback is explicitly labelled; assertion that no file still calls query 1 a queue/backlog view; regression checks that the query 8 terminal-status allowlist, the query 6/10 count `COALESCE` fixes, and the NULL cost semantics are unchanged; regression check that the real classroom answers and the single `不知道` are untouched; a check that no runtime-validation claim was broadened; and a secret scan.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available, so the rewritten query 4b has been reviewed statically but **not** executed. No runtime claim anywhere in the repository was broadened by this change; the reduced classroom PostgreSQL 14.18 evidence never covered query 4b and is still not reused as proof of it. Application integration: NOT RUN. Production validation: NOT RUN.
- Scope: two fixes only. No Day33 lesson; no transactions, locks, indexes, `EXPLAIN`, migrations, ORM, or Alembic; no schema change; protected prompt/template files unchanged; no credentials or production data.

---

## v0.1.65 — Day32 Review Fixes

Date: 2026-07-21

### Fixed

- **Fabricated classroom record restored.** The published Day32 lesson attributed to the student several answers that were never given. Verified line by line against `Day32_Repository_Update_Input.md` and corrected: the CTE/two-children design answer was 「选B」, **not** 「不知道」 (the session contains exactly **one** 「不知道」, on conditional aggregation / `FILTER`); the `SUM`/`AVG` answer is 「sum代表总共开销，AVG代表平均开销。NULL不参与平均数的分母，null代表未知，就是根本没有开销」 — which contains its own internal contradiction and is now taught from, rather than replaced by a clean invented quote; the partial-cost-naming answer is 「不能，因为真实的成本不可知」; the running-stage clock answer includes its full reasoning about `created_at` being persistence time rather than claim time; the throughput answer is about `finished_at` vs `created_at`, **not** about half-open windows (that convention was taught, not student-proposed); the provenance answer is about rolling-deployment coexistence, not "use metadata"; and the invented rollback quote is replaced by the two real answers on bulk requeue and unknown external outcomes. The missing `running_without_attempt` answer 「单独标记为异常，因为可能是卡住了」 was added with its correction.
- **Invented final synthesis replaced.** The lesson carried a fabricated Chinese summary presented as the student's own words. It now records the real initial synthesis 「从join的结果来看，使用CTE是最好的方式…」, the two targeted corrections it required, and the real student completion — with the polished engineering model relabelled **"Final Durable Interpretation (Tech Lead synthesis, not a student quote)"**.
- **Misconceptions realigned to the record.** Two invented misconceptions were replaced by the ones actually recorded: "a CTE is best and means one row per Job" and "rolling back causes successful Jobs to be retried", plus the corrected "a `running` Job with no Attempt is simply stuck" coherence-anomaly framing.
- **English interview record restored.** The lesson and `interview/postgresql.md` carried fluent invented answers. The real Beginner/Intermediate/Senior answers are now preserved verbatim, including their grammar, each followed by its correction and the strong spoken answer.
- **Runtime validation claims tightened.** The previous entry claimed the reduced PostgreSQL 14.18 run proved `HAVING` group filtering, `DISTINCT ON` current-Attempt selection, and a half-open window excluding an exact upper-bound row. It proved none of these: the classroom used the greatest `attempt_number` path rather than the artifact's `DISTINCT ON` form, and only a single last-hour succeeded throughput sample ran with no boundary row created or asserted. Conversely, the claim that queries 9 and 10 were entirely uncovered was wrong for query 9 — release provenance **was** covered representatively, which still does not prove the final file. The exact eleven-item PASS list and an explicit not-covered list are now recorded identically in `PROJECT_STATUS.md`, `projects/ai-backend-data-layer/README.md`, `CHANGELOG.md`, `CURRICULUM.md`, and a new validation-ladder block in the lesson (which previously had none).
- **Query 8 terminal scope.** Throughput filtered only on a `finished_at` window, so a non-terminal row with an anomalous `finished_at` could be counted in `terminal_jobs`. Added `AND j.job_status IN ('succeeded', 'failed', 'cancelled')`, making `terminal_jobs = succeeded_jobs + failed_jobs + cancelled_jobs` true by construction. The grain was also mislabelled "one row per terminal status" in the README; it is one summary row.
- **Queued-age lifecycle semantics.** `jobs.created_at` is acceptance time, not current queued-stage entry, so `queued -> running -> failed -> queued` charged the earlier lifecycle to the current wait. Query 4's columns are renamed `oldest_accepted_at` / `accepted_age_of_oldest_currently_queued_job`, and a new **query 4b** derives the true current queued-stage age from `job_events`, labelling its `jobs.created_at` fallback via `queued_since_source`. No schema change and no migration — Day31 already records `to_status` and `occurred_at`. (Query 4b's event selection was corrected in v0.1.66; see that entry.)
- **Zero-Attempt count columns.** `cost_reported_attempts` returned NULL for a zero-Attempt Job in queries 6 and 10, where the true count is 0. Both are now `COALESCE(..., 0)`. `recorded_total_cost_micros` and `recorded_average_cost_micros` remain NULL by design — an unknown cost must never be rendered as zero cost.
- **Project README navigation.** `Current increment` still read Day31; it now reads Day32, the Day32 lesson was added to the Lessons list, and the Query/Grain table was rewritten to match the final SQL (separate 2a/2b detail queries, `DISTINCT ON` located in the stuck query, query 4/4b split, query 8 as one summary row, query 10 as read-only classification).

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check; Markdown fence balance; relative-link resolution; LESSON_TEMPLATE_v2 16-section order; status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, `docs/README.md`; a provenance check asserting every Day32 student quote appears in `Day32_Repository_Update_Input.md`; a check that exactly one 「不知道」 is attributed to the student; SQL static review (balanced parentheses 69/69, 12 statements, every aliased column present in `001` + `003`, a `GRAIN` contract per statement, deterministic `ORDER BY`, terminal-status allowlist present in query 8, count columns `COALESCE`d and cost columns not, no DML/transactions/locks/indexes/`EXPLAIN`/`DROP`, no `SUM(DISTINCT ...)`); and a secret scan.
- **Final artifact PostgreSQL Runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available during this review, so query 4b, the query 8 terminal predicate, and the query 6/10 `COALESCE` changes have been reviewed statically but **not** executed. The reduced classroom evidence is not reused as proof of the final file. Application integration: NOT RUN. Production validation: NOT RUN.
- Scope: no Day33 lesson was created; no transactions, locks, indexes, `EXPLAIN`, migrations, ORM, or Alembic were added; no schema column was added for the queued-stage fix; the protected prompt/template files are unchanged; and no credentials, connection strings, or production data were added.

---

## v0.1.64 — Day32 SQL Joins, Aggregation, and Operational Queries

Date: 2026-07-21

### Added

- Added `docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day31->Day32 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/004_sql_joins_aggregation_and_operational_queries.sql` — a **read-only** operational query pack over the Day31 model: twelve parameterized statements across ten query groups, each declaring an explicit result-grain contract, with a deterministic `ORDER BY` and a `tenant_id` predicate on every tenant-scoped read. Covers Job detail with zero-Attempt Jobs preserved, **separate** Attempt and Event detail queries, conditional aggregation with `FILTER` plus a `HAVING` retry threshold, tenant queue health by acceptance time alongside a `job_events`-derived current queued-stage age, NULL-aware recorded-cost reporting with completeness columns, CTE pre-aggregation across two independent children, stage-aware stuck **candidates** selected with `DISTINCT ON`, terminal-status-restricted half-open throughput windows, release-provenance affected sets, and read-only incident evidence.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day32 increment: the query/grain table, the encoded rules, an explicit statement of what the pack deliberately omits, a scope-honesty note that these queries produce evidence and candidates rather than verdicts, an authored (not executed) `PREPARE`/`EXECUTE` reproduction, Day32 known gaps, and a separate Day32 validation matrix.
- Appended a Day32 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day32 Beginner/Intermediate/Senior questions to `interview/postgresql.md`, preserving the student's real answers verbatim — including both incorrect row-multiplication attempts and the single `不知道` response (conditional aggregation / `FILTER`) (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day32 is the latest PostgreSQL lesson, and pointed the Day31 lesson's Next Lesson at the released Day32 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day32 completed with its released lesson/artifact (Day33 remains Planned).
- Updated `PROJECT_STATUS.md` (Day32 last completed with artifact + validation boundary; Current/Next is Day33 Planned / Not started), `TASKS.md` (completed Day32 blocks, Day32 preparation converted to history, Day33 preparation added), `README.md`, and `AGENTS.md`.

### Learning Notes

- Day32 turns the Day31 model into answers, and its central claim is that **correct constraints do not produce correct answers**: the same legal rows support many result shapes, so the **grain** you choose is the meaning of the answer. Joins are chosen from what a missing row *means* — `INNER JOIN` discards a zero-Attempt Job, which is exactly the backlog operations needs to see. A join returns **combinations**, so two independent one-to-many children multiply (3 Attempts x 4 Events = 12 rows), and a zero-Attempt Job joined to 4 Events returns **4** rows, not 0, because the NULL-extended row matches every Event. `COUNT(*)` counts result rows; `COUNT(child_pk)` counts existence. `FILTER` narrows an aggregate while `WHERE` narrows the input set — moving a child predicate into `WHERE` silently collapses `LEFT` into `INNER`. NULL is **unknown, not zero**, so `SUM`/`AVG` describe recorded facts and `COALESCE(SUM(cost_micros), 0)` converts ignorance into a billing claim. CTE pre-aggregation is the structural fix for multiplication (`DISTINCT` patches counts but not `SUM`). Stuck detection uses the **current Attempt's** clock with a `DISTINCT ON` tie-breaker and emits classified candidates, because a long-running Attempt proves only that no completion was **recorded**. Windows are half-open `[start, end)`, affected sets come from recorded provenance rather than time correlation, and rollback stops future bad writes without repairing committed rows or undoing already-published outbox events.
- Two student misconceptions are preserved verbatim rather than smoothed over: the join answered as "4 rows" and then "0 rows", both rooted in a **sequential-filter** mental model instead of a combination product. Exactly one `不知道` answer was recorded — conditional aggregation / `FILTER` — and that concept was taught directly from it. The two-children design question was answered 「选B」, correctly choosing independent pre-aggregation.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day33 lesson exists and Day33 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; Markdown fence balance; relative-link resolution; status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; SQL static review of `004` (balanced parentheses 61/61, 11 statements, every aliased column present in `001` + `003`, a `GRAIN` contract per statement, a deterministic `ORDER BY` per result-returning query, no DML/transactions/locks/indexes/`EXPLAIN`/`DROP`, no `SUM(DISTINCT ...)`, recorded cost not `COALESCE`-wrapped); and a secret scan.
- **PostgreSQL runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available in the repository-update environment, so no statement in `004` was parsed or executed by PostgreSQL. Classroom evidence is reported separately and at its true level: a disposable **PostgreSQL 14.18** cluster executed a **reduced** Day32 validation schema with representative data and PASSED exactly these checks: LEFT JOIN zero-Attempt placeholder row; `COUNT(*)` vs `COUNT(attempt_id)` for a zero-Attempt Job; 3 Attempts x 4 Events = 12 rows; conditional aggregation 3 total / 2 failed; cost evidence 2 reported / SUM 400 / AVG 200; independent Attempt/Event CTE pre-aggregation; `running_attempt_over_threshold` classification; `running_without_attempt` classification; one succeeded Job in the last-hour throughput window; release-provenance `DISTINCT` affected set; final marker `DAY32_RUNTIME_VALIDATION_PASS`. **Not** executed or proven by that run: `HAVING` group filtering; `DISTINCT ON` selection of the current Attempt — the classroom used the greatest `attempt_number` path, **not** the artifact's `DISTINCT ON` form; a half-open window excluding a row placed exactly on the upper bound — only a single last-hour succeeded throughput sample was run, with no boundary row created or asserted; the explicit terminal-status allowlist; queries 4b, 5 and 10; and execution against the full Day31 `001` + `003` schema. Release provenance **was** covered representatively, which still does not prove the final repository query 9 as written. That reduced evidence is **not** reused as proof of the file in this repository. No cluster was created during the repository update, so no cleanup was required, and no shared or production database was contacted.
- Scope: no Day33 lesson was created; no transactions, locks, indexes, `EXPLAIN`, RLS, ORM, or Alembic were added; no DML was added to the Day32 artifact; no Day29-Day31 classroom answer or artifact behaviour was altered; the protected prompt/template files are unchanged; and no credentials, real connection strings, signed URLs, or production data were added.

---

## v0.1.63 — Day31 Validation Isolation and Connection Target

Date: 2026-07-21

### Changed

- **Test 9 now exercises the constraint it claims to test.** The cross-tenant Upload Session -> Document case reused session `33333333-...`, which the positive path had already consumed. PostgreSQL checks the unique index during the row insert, before the foreign-key trigger fires, so the statement raised `23505 documents_upload_session_unique` instead of the intended `23503`. That escaped Test 9's `foreign_key_violation`-only handler, aborted the script under `ON_ERROR_STOP=1`, and silently skipped Tests 10 and 11. The positive path now creates a third Tenant-A Upload Session (`aaaaaaaa-...`) that is deliberately left **without** a Document, and Test 9 uses it — so `documents_upload_session_same_tenant_fk` is the only rule that can reject the row. Test 10 keeps using `33333333-...` (already has a Document, same tenant) so `documents_upload_session_unique` is the rule under test. Both blocks still catch exactly one condition, raise their own `P0001` if the illegal statement unexpectedly succeeds, and let any other error propagate.
- **Validation commands now target the disposable cluster explicitly.** The apply and validation steps used a bare `psql`, which does not read `DAY29_PGHOST`/`DAY29_PGPORT` and would either fail to connect or silently connect to the operator's default PostgreSQL. They now use the Day29 `day29psql` helper (disposable socket, disposable port, database `ai_backend`, `ON_ERROR_STOP=1`), with the helper definition shown inline, an explicit prerequisite that the Day29 disposable-cluster startup runs first, and a documented fallback requiring host/port/database on every command. The README states that these must never run against a shared, development, or production database.

### Notes

- Validation actually performed: `git diff --check`; changed-file scope (README + CHANGELOG only); protected-file check; Markdown fence balance; relative-link resolution; secret scan; a placeholder scan confirming no unbound `$1`/`$tenantA`-style pseudo-parameters inside any code fence; and a static review of the script's logic — session `aaaaaaaa-...` is created and never consumed by a Document, Test 9 references only that session, Test 10 references the already-consumed session within the same tenant, Tests 1-11 are present and correctly ordered, and all 11 `DO` blocks each declare exactly one exception handler with a matching unexpected-success guard.
- **PostgreSQL runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available, so the disposable cluster was not started, `001` -> `003` was not applied, and Tests 1-11 were not executed. Test 9/10/11 outcomes are therefore **unverified at runtime**; the constraint-ordering reasoning behind this fix is static analysis. No cluster was created, so no cleanup was required, and no shared or production database was contacted. The reduced Day31 classroom evidence is not reused as proof of this corrected script.
- Scope: README and CHANGELOG only. No SQL schema constraint was changed, no Day31 classroom answer was altered, no Day32 lesson was created and Day32 remains Planned, and no transactions, locks, indexes, RLS, ORM, or Alembic were added. The protected prompt/template files are unchanged and no credentials, real connection strings, or production data were added.

---

## v0.1.62 — Day31 Review Fixes

Date: 2026-07-21

### Changed

- **Tenant provenance for Documents.** `app.documents` referenced `tenant_id` and `upload_session_id` with two independent foreign keys, which proved only that each value existed — a Tenant-B Document could claim a Tenant-A Upload Session. The single-column `upload_session_id` foreign key was removed and replaced with a tenant-aware composite foreign key `(tenant_id, upload_session_id) -> app.upload_sessions(tenant_id, upload_session_id) ON DELETE RESTRICT`, backed by the existing `upload_sessions_tenant_id_unique` candidate key. `UNIQUE (upload_session_id)` is retained so one Upload Session still produces at most one Document. Synced to the Day31 lesson (Concept 4), the project README rules table, the cheat sheet, the artifact comments/relationship summary, and the validation matrix, plus a new expected-failure case.
- **Day30 statement pack compatibility.** `003` adds `tenant_id` and `idempotency_key` as `NOT NULL` columns with no default, so the original Day30 `INSERT INTO app.jobs (provider_metadata) ...` and `INSERT INTO app.jobs DEFAULT VALUES ...` fail with `23502 not_null_violation` after `003`. Rather than rewriting the Day30 classroom record, statements 1 and 1b are now explicitly marked **Day29 base schema only**, and a clearly labelled **Day31 compatibility increment** (statement 1c) supplies `tenant_id`, `idempotency_key`, and `provider_metadata` explicitly. The file header and the README statement table, compatibility note, parameter documentation, and validation boundary were updated. The docs state that after Day31 there is **no** legal `DEFAULT VALUES` way to create a Job, because tenant ownership and client request identity cannot be defaulted by the database, and that 1c was **not** taught in the Day30 class.
- **Runnable validation.** The README validation section used driver placeholders (`$1`, `$tenantA`, `$jobA`, `$documentB`) that produce `ERROR: there is no parameter $1` when pasted into `psql`. It is now a copy-paste runnable script using **fixed test UUIDs**, applied with `psql -v ON_ERROR_STOP=1`. Every expected failure is a nested `DO` block that catches **only** its specific condition (`unique_violation`, `check_violation`, `foreign_key_violation`, `not_null_violation`), raises its own `P0001` if the illegal statement unexpectedly succeeds, and lets any other error propagate — so a missing table or typo can never be reported as a pass. No trailing `echo` masks the exit status. All previously listed cases are retained and three were added: cross-tenant Upload Session -> Document, a second Document for one Upload Session, and an assertion that the pre-Day31 Job INSERT is now rejected with `23502`.
- **Phase 3 status.** `CURRICULUM.md` still read `Planned / Ready (not started)` while Day29-Day31 are complete and Day32 is the current lesson; it now reads `In Progress`. Day32 remains `Planned` and no Day32 lesson was created.

### Notes

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check; Markdown fence balance; relative-link resolution; secret scan; a placeholder scan confirming no `$1`/`$tenantA`-style tokens remain in the runnable validation script; SQL static review of DDL dependency order and composite-FK/candidate-key pairing (including the new `documents` -> `upload_sessions` composite key); and status consistency across Curriculum, Roadmap, Project Status, Tasks, README, and AGENTS.
- **PostgreSQL runtime: NOT RUN.** No `psql`, PostgreSQL server, or Docker daemon was available in the repository-update environment, so `001` -> `003`, the positive path, the expected-failure blocks, and the Day31-compatible Job INSERT were **not executed**. The reduced Day31 classroom evidence (PostgreSQL 14.18) is **not** reused as proof of the corrected artifact, and it never covered the cross-tenant Upload Session -> Document case introduced here.
- Scope: no transactions, locks, indexes, RLS, ORM, or Alembic were added; `001_create_jobs.sql` and the Day29/Day30 lesson bodies are unchanged; the protected prompt/template files are unchanged; no credentials, connection strings, signed URLs, or production data were added.

---

## v0.1.61 — Day31 Relational Modeling and Data Integrity

Date: 2026-07-21

### Added

- Added `docs/postgresql/day31-relational-modeling-and-data-integrity.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day30->Day31 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/003_relational_modeling_and_data_integrity.sql` — the relational target schema: `tenants`, `upload_sessions`, `documents`, extended `jobs` (tenant ownership, `UNIQUE (tenant_id, idempotency_key)`, status/counter/terminal CHECKs), `job_attempts`, `job_events`, `outbox_events`, `result_artifacts`, and the tenant-aware `job_documents` junction table, with 23 named constraints and `ON DELETE RESTRICT` on all 11 foreign keys.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day31 increment: apply order, entity/relationship map, the encoded key rules, authored (not executed) positive/negative validation commands with exact SQLSTATEs, Day31 known gaps, and a separate Day31 validation matrix.
- Appended a Day31 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day31 Beginner/Intermediate/Senior questions to `interview/postgresql.md` (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day31 is the latest PostgreSQL lesson, and pointed the Day30 lesson's Next Lesson at the released Day31 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day31 completed with its released lesson/artifact (Day32 remains Planned).
- Updated `PROJECT_STATUS.md` (Day31 last completed with artifact + validation boundary; Current/Next is Day32 Planned / Not started), `TASKS.md` (completed Day31 blocks, Day31 preparation converted to history, Day32 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day31 turns the Day29 durable row and the Day30 guarded statements into a relational model PostgreSQL can enforce: when a repeated fact becomes its own entity; primary key vs foreign key vs business key; the SCOPE of `UNIQUE` (`(job_id, attempt_number)`, and `(tenant_id, idempotency_key)` because a retry produces a NEW `job_id`); referential actions as retention policy (`RESTRICT` protects Provider/cost/audit evidence that `CASCADE` would erase); one-to-many FK placement and optional one-to-one via FK + `UNIQUE`; `CHECK` as the legal-state boundary and what a row CHECK cannot see; normalizing Result Artifacts so `job_id` stays derivable; separating `jobs.job_status`, `job_events`, and `outbox_events`; many-to-many junction tables with their own attributes; tenant-aware composite foreign keys; why foreign keys are write-time integrity and never authorization; and deploying a `UNIQUE` constraint onto committed duplicates.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (a duplicate insert believed to overwrite; `attempt_id` uniqueness assumed to stop duplicate attempt numbers; `CASCADE` chosen because `RESTRICT` blocks deletion; `work_id + job_id` proposed for request identity; the FK placed on the earlier Upload Session; composite FKs believed to block cross-tenant reads; a committed duplicate Job believed to be "rollback-able"; and the raw `job_attempts` DDL whose model was complete while the syntax was not).
- Scope honesty: the artifact is a **target schema for a fresh database**, applied after `001_create_jobs.sql`. Its `ADD COLUMN ... NOT NULL` statements succeed only while `app.jobs` is empty and raise `23502` against existing rows; safe evolution of populated tables is **Day36** and no tenant or idempotency values were invented for historical rows. The legacy `jobs.result_object_key` column is retained, not dropped. No transactions, locking, explicit indexes, RLS, roles, or migrations were added.
- Validation: conceptual/manual review of the complete model and static review of the student DDL were done **in class**, and a **reduced** classroom validation schema was executed on **PostgreSQL 14.18** where selected constraints behaved correctly (duplicate `(job_id, attempt_number)` rejected; non-positive `attempt_number` rejected; missing parent Job rejected; deleting a Job with an Attempt restricted; same-tenant duplicate idempotency key rejected; different-tenant key reuse accepted; invalid `job_status` rejected; cross-tenant Job-Document link rejected; one valid Attempt remained). An earlier attempt failed at cluster start with `shmget: Operation not permitted` — environment evidence, not a SQL result. **The full Day31 artifact in this repository was NOT executed**: no `psql` or PostgreSQL server was available during the repository update, so only a static file review was performed (balanced syntax, 15 statements, valid DDL dependency order after `001`, every composite FK backed by a matching candidate key, `result_artifacts` carrying no `job_id`, all FKs `RESTRICT`, no out-of-scope constructs, no credentials). The reduced classroom test is **not** proof that every table in the final file applies cleanly.
- Day30's validation distinction is preserved unchanged: its manual/static statement review is **not** PostgreSQL runtime evidence. No Day32 lesson was created. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`; no second project or duplicate cheat/interview files were created; no credentials, connection strings, signed URLs, or production data were added.

---

## v0.1.60 — Day30 Review Fixes

Date: 2026-07-20

### Changed

- Fixed a `TASKS.md` Current Sprint contradiction. `Today's Tasks` still listed completed Day29 items plus "Prepare for Day30" while Current Lesson was already Day31; it now points only at the Day31 Preparation block, with a note that Day29/Day30 work lives in the Completed and Preparation-history sections. The "Day30 Preparation (completed)" block no longer carries unchecked items: reviewing the Day29 `app.jobs` schema and project README limitations, previewing the Day30 SQL scope, and keeping Day31 constraints / Day33 transactions / Day34 concurrency / Phase 4 ORM out of scope are recorded as done, matching what the live lesson actually covered. Day30 now appears only in Completed/History, Day31 stays Planned / Not started, and no Day31 lesson was created.
- Corrected result-row vs affected-row terminology. `SELECT` returns **result rows** and does not affect rows; only `INSERT`/`UPDATE`/`DELETE` carry an affected-row contract. In `projects/ai-backend-data-layer/sql/002_job_crud_and_guarded_transitions.sql` the SELECT comments now read "Expected RESULT ROWS" (including a contract line added for statement 3c), the DML comments keep "Expected AFFECTED ROWS", and the file header explains both contracts and restates that `RETURNING` yields rows, never a count. In `projects/ai-backend-data-layer/README.md` the statement table header became "Expected row contract" with each row labelled "result rows" or "affected rows", plus an explicit note that a `SELECT` result count is not evidence of a data change. The SQL business semantics, parameters, and guards were not touched.
- Replaced the absolute "a missing predicate has no undo" claim with the correct transaction boundary. The Day30 lesson and the `interview/postgresql.md` Chinese explanation now state that an erroneous statement can still be rolled back with `ROLLBACK` **before** `COMMIT` (full transaction boundaries remain Day33), that once committed there is **no automatic undo**, and that rolling back application code stops future bad writes without repairing committed rows — only a guarded data repair does. No transaction syntax, artifact, or Day33 material was added.

### Notes

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check; confirmation that no Day31 lesson exists; status consistency (Current Lesson = Day31 Planned / Not started, Last Completed = Day30, no Day30 preparation task remaining in Today's Tasks); terminology checks (no `SELECT` labelled with affected rows; every DML labelled with affected rows; `RETURNING` still defined as rows not a count); rollback-wording checks; Markdown fence balance; relative-link resolution; secret scan; and a re-check that the SQL guards, parameters, statement count, and Day30 scope are unchanged.
- **PostgreSQL was NOT available**, so the SQL was **NOT executed**: no parser/runtime validation, no Python-driver binding, no application integration, and no production validation. Static text/structure review only. No shared or production database was contacted.
- Scope: documentation and terminology only. `001_create_jobs.sql`, Day29 classroom content, and the Day30 student answers are unchanged; no transactions, locks, `CHECK`/`UNIQUE`/foreign keys, indexes, ORM, or migrations were added; `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, the root `README.md`, and `AGENTS.md` needed no changes; the protected prompt/template files are unchanged.

---

## v0.1.59 — Day30 SQL Data Manipulation and Query Fundamentals

Date: 2026-07-20

### Added

- Added `docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day29->Day30 mental-model evolution).
- Added `projects/ai-backend-data-layer/sql/002_job_crud_and_guarded_transitions.sql` — a raw, parameterized SQL operations pack: INSERT with database defaults + `RETURNING`, the deterministic oldest-queued candidate `SELECT`, NULL-aware reads, guarded `queued -> running` and `running -> succeeded` transitions, a database-side `attempt_count` increment, an optimistic expected-value update, and a guarded cleanup `DELETE`. Every statement carries an explicit affected-row contract.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day30 increment (statement table, contracts and boundaries) and a separate Day30 validation matrix.
- Appended a Day30 rapid-reference section and interview phrases to `cheat_sheets/postgresql.md`.
- Appended Day30 Beginner/Intermediate/Senior questions to `interview/postgresql.md` (no duplicate PostgreSQL interview file created).
- Updated `docs/README.md` so Day30 is the latest PostgreSQL lesson, and pointed the Day29 lesson's Next Lesson at the released Day30 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day30 completed with its released lesson/artifact (Day31 remains Planned).
- Updated `PROJECT_STATUS.md` (Day30 last completed with artifact + validation boundary; Current/Next is Day31 Planned / Not started), `TASKS.md` (completed Day30 blocks, Day30 preparation converted to history, Day31 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day30 turns the Day29 durable Job row into precise reads and guarded writes: the clause chain `SELECT -> FROM -> WHERE -> ORDER BY -> LIMIT`; explicit columns and a unique `ORDER BY` tie-breaker for deterministic pages; SQL three-valued logic (`WHERE` keeps only TRUE, so `error_message <> 'timeout'` silently drops every no-error row); `INSERT ... DEFAULT VALUES` / explicit column lists with `RETURNING`; parameterized SQL as the injection boundary; `WHERE` as the modification boundary with current-state guards; zero rows meaning the transition did not apply; `AND`/`OR` precedence in destructive statements; lost-update awareness; and the contain -> preserve evidence -> identify -> reconcile -> guarded repair -> verify incident order after a broad `UPDATE` wrongly failed 842 live Jobs.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (`SELECT *` with no tie-breaker, `status`/`create_at` and double-quoted `queued`, `<>` treated as text-only, `INSERT DEFAULT INTO`, the f-string assumption before parameters were taught, `IS DISTINCT FROM 'queued'` as an inverted transition guard, `RETURNING` mistaken for a count, unparenthesized `AND`/`OR` in `DELETE`, locking proposed first for the lost update, waiting-first incident response, and the blanket restore of all 841 rows).
- Scope honesty: the candidate `SELECT` is explicitly **not** a concurrency-safe claim. The artifact deliberately contains no transactions, locks (`FOR UPDATE`/`SKIP LOCKED`), `CHECK`/`UNIQUE`/foreign keys, indexes, Job Event/Attempt tables, ORM, or migration framework — those are Day31-Day35 and Phase 4. The 842-row incident also documents that exact business-outcome reconstruction may be impossible because the current schema has no Job Event/Attempt history or release/tenant/provenance model.
- Validation: conceptual/manual review of the SQL semantics was completed **in class**; the repository update performed a **static file review only** (balanced parentheses/quotes, 11 statements, every DML carries `RETURNING`, guards use `= 'queued'`/`= 'running'`, the `DELETE` uses `IN (...)`, only `$1`/`$2`/`$3` parameters, no transactions/locks/constraints/indexes/DDL, no credentials) plus Markdown fence balance, relative-link resolution, and a secret scan. **PostgreSQL parser/runtime execution, Python-driver parameter binding, FastAPI/Celery/Object Storage integration, transaction/concurrency runtime tests, and production validation were NOT RUN** — no `psql` or PostgreSQL server was available in the repository-update environment. Day29's PostgreSQL 14.18 classroom evidence applies to `001_create_jobs.sql` only and is **not** relabelled as Day30 runtime evidence.
- No Day31 lesson was created. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`; did not create a second project or duplicate cheat-sheet/interview files; no credentials, connection strings, shared-database commands, or production data were added.

---

## v0.1.58 — Day29 Cleanup Helper Self-Removal

Date: 2026-07-19

### Changed

- `projects/ai-backend-data-layer/README.md`: the cleanup success branch now removes **all four** helper
  functions in one step — `day29psql`, `day29_cleanup_guard`, `day29_report_vars`, and `day29_cleanup`
  itself — instead of leaving `day29_cleanup` behind. Both bash and zsh allow a running function to
  unset its own definition; the in-flight call still completes and returns 0.
- Removed the instruction telling the reader to run `unset -f day29_cleanup` by hand after a successful
  cleanup. The documentation now states that a full success leaves the shell clean with no manual
  follow-up, and the outcome table's column was renamed to "Variables + helpers" with the success row
  marked "all cleared (vars + 4 helpers)".
- Failure behaviour is unchanged and was re-verified: on a guard failure, a stop failure, or a delete
  failure the `DAY29_*` variables **and** all helper functions are preserved so the cluster can be
  inspected and `day29_cleanup` can be re-run, nothing is wrongly deleted, and the exit status stays
  non-zero.

### Notes

- Validation actually performed: `git diff --check`; the README's helper functions were copied verbatim
  into a harness and **executed in bash** (GNU bash 5.1.16) — 27/27 assertions passed, covering the
  self-unset success path (function returns 0 after unsetting itself; all four helpers and all four
  `DAY29_*` variables gone; directory removed) and regressions for the guard-failure, stop-failure, and
  delete-failure branches (variables and helpers preserved, no wrongful delete, non-zero status). The
  mocks only created and removed fresh `day29-pg.XXXXXX` temporary directories.
- **zsh verification: NOT RUN.** zsh is not installed in this environment and cannot be installed
  (no root; `apt-get` lock is not writable and there is no pip package). The self-unset behaviour was
  therefore confirmed in bash only.
- **PostgreSQL was NOT available**, so the schema, the `DO` block, and the full README procedure were
  **NOT executed**. The PostgreSQL 14.18 results remain classroom evidence; the shell mock test is not
  presented as PostgreSQL runtime validation, and no shared or production database was contacted.
- Scope: documentation-only. `sql/001_create_jobs.sql`, the Day29 lesson, student answers,
  `PROJECT_STATUS.md`, `TASKS.md`, `CURRICULUM.md`, and `ROADMAP.md` are unchanged; the NOT NULL, guard,
  stop, and delete control flow is otherwise untouched; no database capability or application code was
  added; no Day30 lesson was created; the protected prompt/template files are unchanged.

---

## v0.1.57 — Day29 Cleanup Control-Flow Fixes

Date: 2026-07-19

### Changed

- `projects/ai-backend-data-layer/README.md`: deletion is now gated on PostgreSQL actually stopping. The
  previous success branch ran `pg_ctl ... stop` and `rm -rf` as sequential commands, and because the
  shell does not abort on a non-zero `pg_ctl` status by default, a failed or timed-out stop could still
  be followed by a recursive delete of a data directory that might still be in use. Cleanup is now a
  `day29_cleanup` function with explicit nested control flow: the identity guard must pass, then
  `pg_ctl -m fast stop` must succeed, then `rm -rf -- "$DAY29_PG_ROOT"` runs and its status **and** the
  path's continued existence are both checked. A stop failure prints `REFUSING delete`, performs no
  delete, and returns non-zero.
- `projects/ai-backend-data-layer/README.md`: the NOT NULL step no longer ends with
  `echo "exit status: $?"`, which returned 0 and masked the real result. `day29psql` is now the last
  command in the block, so the block's exit status *is* the verification result (expected
  `not_null_violation` -> 0; unexpected acceptance, missing table, syntax error, wrong database, or
  connection failure -> non-zero). An outcome table was added, plus guidance to capture `rc=$?` and
  restore it explicitly if the status must be printed — never an unconditional `exit` in an interactive
  shell.
- `projects/ai-backend-data-layer/README.md`: diagnostic variables are cleared **only** on full success.
  Previously `unset DAY29_*` ran unconditionally, contradicting the "inspect the variables" advice. On a
  guard failure, a stop failure, or a delete failure, `day29_report_vars` now prints
  `DAY29_PG_ROOT`/`DAY29_PGDATA`/`DAY29_PGPORT`/`DAY29_PGHOST` and the server-log path, the variables and
  helper functions are preserved, the directory is kept, and cleanup returns non-zero. The success
  message is printed only after the directory is verifiably gone. A branch/outcome table documents all
  four cases.

### Notes

- Validation actually performed: `git diff --check`; the README's `day29_cleanup_guard`,
  `day29_report_vars`, and `day29_cleanup` functions were copied verbatim into a harness and
  **executed in bash with mocked `pg_ctl` and `rm`**, covering all four branches — guard failure (no
  stop, no delete, variables preserved, non-zero), stop failure (no delete, directory preserved,
  variables preserved, `REFUSING delete`, no success message, non-zero), delete failure (no success
  message, variables preserved, non-zero), and full success (success message, directory gone, all four
  variables cleared, exit 0) — 26/26 assertions passed. The mocks only ever created and removed fresh
  `day29-pg.XXXXXX` temporary directories; no real PostgreSQL data directory was touched. Also checked:
  Markdown fenced-block balance, relative-link resolution, restricted file scope, and a secret scan.
- **PostgreSQL was NOT available in this environment**, so the schema, the `DO` block, and the full
  README procedure were **NOT executed**. The PostgreSQL 14.18 results remain classroom evidence and are
  not restated as repository-update or production validation. No shared or production database was
  contacted, and the mock-based control-flow test is not presented as PostgreSQL runtime validation.
- Scope: documentation-only. `sql/001_create_jobs.sql`, the Day29 lesson, student answers,
  `PROJECT_STATUS.md`, `TASKS.md`, `CURRICULUM.md`, and `ROADMAP.md` are unchanged; no database
  constraints, relationship tables, or application code were added; no Day30 lesson was created; the
  protected prompt/template files are unchanged.

---

## v0.1.56 — Day29 Reproduction Safety Fixes

Date: 2026-07-19

### Changed

- Replaced the false-success NOT NULL check in `projects/ai-backend-data-layer/README.md`. The old
  `... || echo "expected failure: NOT NULL works"` reported ANY failure (missing table, syntax error,
  connection refused, wrong database) as a pass. The step now runs a `DO` block whose nested `EXCEPTION`
  handler catches **only** `not_null_violation` (SQLSTATE 23502): the expected violation yields
  `NOTICE: PASS` and exit 0; an unexpectedly successful INSERT raises its own `P0001` exception (not
  caught) so the step fails; any other error propagates and fails. The psql helper is now a shell
  function with `-v ON_ERROR_STOP=1`, so SQL errors produce reliable non-zero exit statuses. The
  documentation states explicitly that this asserts a specific error condition rather than treating any
  non-zero exit as success. No blanket `|| echo` remains in the file.
- Hardened disposable-cluster creation and cleanup. The temporary directory is now created with a
  task-specific fixed prefix (`mktemp -d "${TMPDIR:-/tmp}/day29-pg.XXXXXX"`, a form that works on both
  macOS and Linux). Cleanup is gated by a `day29_cleanup_guard` function that verifies the path's
  identity before anything is stopped or deleted: `DAY29_PG_ROOT` matches the `day29-pg.XXXXXX` prefix;
  it is not `/`, `$HOME`, or the current directory; `DAY29_PGDATA` is exactly `$DAY29_PG_ROOT/data`; and
  `$DAY29_PGDATA/PG_VERSION` exists. `pg_ctl -m fast stop` and `rm -rf -- "$DAY29_PG_ROOT"` run only
  inside the guarded branch; any failed check refuses cleanup with a clear message and deletes nothing.
  The README no longer claims that a non-empty variable plus an existing directory is sufficient proof.

### Notes

- Validation actually performed: `git diff --check`; the extracted `day29_cleanup_guard` function was
  **executed in bash** against 10 adversarial cases (genuine cluster dir allowed; empty variables, `/`,
  `$HOME`, generic `/tmp`, a wrong-prefix real cluster, a `PGDATA` pointing at `/etc`, a right-prefix
  directory without `PG_VERSION`, and a nonexistent directory all refused) — 10/10 as expected; static
  structural checks of the `DO` block (balanced dollar quoting, outer/inner `BEGIN`/`END`, a single
  `WHEN not_null_violation` handler, the unexpected-success `RAISE`); Markdown fenced-block balance;
  relative-link resolution; and a secret scan of the changed files.
- **PostgreSQL and Docker were NOT available in this environment**, so the SQL, the `DO` block, and the
  full README procedure were **NOT executed** here. The PostgreSQL 14.18 results remain classroom
  evidence and are not restated as repository-update or production validation. No shared or production
  database was contacted.
- Scope: documentation-only changes to the reproduction procedure. The Day29 lesson content, student
  answers, and `sql/001_create_jobs.sql` are unchanged; no `CHECK`, business `UNIQUE`, foreign key, or
  relationship table was added; no SQLAlchemy/Alembic/FastAPI/Celery/Redis introduced; no Day30 lesson
  created; `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, and `LESSON_TEMPLATE_v2.md`
  are unchanged.

---

## v0.1.55 — Day29 Review Fixes

Date: 2026-07-19

### Changed

- Fixed the Current Lesson contradiction: `PROJECT_STATUS.md` and `TASKS.md` now show Current Lesson = `Day30 — SQL Data Manipulation and Query Fundamentals` with `Planned / Not started`, matching `README.md`/`AGENTS.md`. The Day29 `Template`/`Completed Time` fields were removed from Current Lesson (they remain under Last Completed Lesson). `TASKS.md` Target lesson now reads "Not created yet — see CURRICULUM.md and ROADMAP.md." Day29 remains only in Completed, Last Completed Lesson, Completed Day29 Tasks, and CHANGELOG history. No Day30 lesson file was created.
- Fixed an inaccurate PostgreSQL session description in `projects/ai-backend-data-layer/README.md` that paired "schema app" with "current_schema public" and re-introduced the "a session connects to a schema" mental model. It now states that the session connected to database `ai_backend`, the target relation was `app.jobs`, `search_path` was `"$user", public`, `current_schema()` returned `public`, and explicit qualification resolved `app.jobs` even though `app` was not in `search_path`.
- Fixed the artifact provenance wording in `TASKS.md`: the data-layer artifact was designed and runtime-validated during the live lesson, then materialized in the repository during the post-class Repository Update (the repository files were not created during class).
- Expanded the reproduction section in `projects/ai-backend-data-layer/README.md` so it now covers every classroom validation: schema apply, `DEFAULT VALUES RETURNING`, session diagnostics, the expected NOT NULL failure, the accepted empty-string/`banana` inserts, the UTC vs Asia/Shanghai identical-epoch check, the guarded `queud` repair with `RETURNING` evidence, and restart persistence. It uses task-specific `DAY29_PG_ROOT`/`DAY29_PGDATA` variables (never a pre-existing `PGDATA`), starts from `projects/ai-backend-data-layer/`, labels the expected-failure step explicitly, guards cleanup to this run's `mktemp` directory only, and states that the commands were authored — not executed — during the repository update.
- Fixed the stale template rule in `docs/README.md`: Day01-Day20 lessons remain valid with the original template, and Day21 and later final lessons must follow `LESSON_TEMPLATE_v2.md`.

### Notes

- Review fixes only: the completed Day29 lesson content, the SQL schema, and the real student answers are unchanged. No `CHECK`/business `UNIQUE`/foreign key/relationship table was added to the Day29 schema, no SQLAlchemy/Alembic was introduced, and no Day30 lesson was created.
- Validation actually performed: `git diff --check`, status-consistency checks, Markdown relative-link resolution, fenced-block balance, and a secret scan of the changed files. **PostgreSQL was NOT available in this repository-update environment**, so the SQL and the reproduction commands were NOT executed here; the PostgreSQL 14.18 results remain classroom evidence and are not restated as repository-update or production validation.
- Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`; historical CHANGELOG entries are unchanged.

---

## v0.1.54 — Day29 PostgreSQL Foundations and Durable Relational State

Date: 2026-07-19

### Added

- Added `docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day28->Day29 mental-model evolution). This is the first Phase 3 lesson and creates the new `docs/postgresql/` topic directory.
- Added `projects/ai-backend-data-layer/` — the first increment of the Production AI Backend Data Layer: `sql/001_create_jobs.sql` (the exact classroom DDL for `app.jobs`) and a README with ownership decisions, reproducible disposable-PostgreSQL commands, a validation matrix, and explicit known gaps.
- Added `cheat_sheets/postgresql.md` (new topic cheat sheet).

### Changed

- Appended Day29 Beginner/Intermediate/Senior questions to the existing `interview/postgresql.md` stub (no duplicate PostgreSQL interview file was created).
- Updated `docs/README.md` to index the new `docs/postgresql/` directory and the Day29 lesson.
- Updated the `docs/devops/day28-ai-backend-production-architecture.md` metadata Next Lesson line to link the released Day29 lesson (the completed Day28 body is unchanged).
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day29 completed with its released lesson/artifact (Day30-Day42 remain Planned).
- Updated `PROJECT_STATUS.md` (Phase 3 In Progress; Day29 completed with artifact + validation boundary; Next = Day30), `TASKS.md` (completed Day29 task blocks, Day29 preparation converted to history, Day30 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day29 turns Day28's conceptual ownership rule into an executable table: the Job row must be written and committed **before** FastAPI returns `202`; the row is a durable business fact and the table definition is its enforceable contract. Covers the PostgreSQL server/cluster/database/schema/table/row/column hierarchy and the `psql` session boundary (a session connects to a database; schema resolves via qualified name or `search_path`; `public` is a default namespace), Job types/defaults (uuid PK `gen_random_uuid()`, text, integer, boolean, `timestamptz` `now()`, bounded jsonb), typed columns vs a JSONB-only document, `NULL` per lifecycle, primary key vs idempotency key, `timestamptz` as one absolute instant, the validation ladder, and guarded data repair.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (the 202-then-row ordering, integer-vs-UUID, `public` as "public information", psql "connecting to a schema", one-to-many treated as a column type, NULL lifecycle wording, the primary-key overclaim, the validation overclaim, and `jsob`). The senior English answer was taught directly after the attempts "client produce idempotency key" and "我忘了".
- Scope honesty: the schema is deliberately minimal. `text NOT NULL` accepted an empty string and `banana` at runtime — CHECK/UNIQUE constraints, business idempotency keys, tenant ownership, Documents/Attempts/Events/Outbox tables, foreign keys, transactions, concurrency control, indexes, migrations, roles, and backup/restore are Day30-Day37 work. SQLAlchemy/Alembic remain Phase 4. Durability is not integrity: a misspelled `queud` row is durable and unclaimable.
- Validation: classroom runtime evidence came from a disposable PostgreSQL 14.18 cluster (DDL acceptance, `gen_random_uuid()`, `DEFAULT VALUES RETURNING`, not-null rejection, empty/`banana` acceptance, timestamptz rendering with identical epoch, a guarded `UPDATE 3` repair with RETURNING evidence, and restart persistence of all 6 rows). **This repository update did NOT re-run the SQL** — no `psql`, PostgreSQL server, or Docker daemon was available in the update environment; only Markdown/link/structure/secret checks and a static SQL review were performed. No FastAPI/Celery/Redis/Object Storage integration, transaction, concurrency, index, migration, backup/restore, replication, load, or production validation was performed or is claimed.
- No credentials, connection strings with secrets, tokens, presigned URLs, or customer data were added; only disposable local paths. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`; did not create `knowledge/`; did not rewrite Day01-Day28 lesson bodies (the Day28 metadata Next Lesson line is the single allowed exception).

---

## v0.1.53 — Phase 3 Status Consistency Fix

Date: 2026-07-19

### Changed

- Unified the active status fields across `README.md`, `AGENTS.md`, `PROJECT_STATUS.md`, and `TASKS.md` so a new teaching session unambiguously knows the next lesson is Day29 (planned, not started) rather than re-reading the completed Day28.
- Current Phase is now `Phase 3 — Backend Foundations (Planned / Ready — not started)` in `README.md`, `AGENTS.md`, `PROJECT_STATUS.md`, and `TASKS.md` (previously Phase 2 in three of them).
- Current Lesson is now `Day29 — PostgreSQL Foundations and Durable Relational State` with `Status: Planned / Not started` in `PROJECT_STATUS.md` and `TASKS.md`; the Day28-only Current Lesson fields (Template/Completed Time) were removed because they already live under Last Completed Lesson.
- `TASKS.md` Target lesson no longer points at a Day28 file for the current lesson; it states the Day29 file is not created yet (see CURRICULUM.md and ROADMAP.md), and Today's Tasks now reflect the planned/not-started Day29 state.
- Last Completed Lesson remains `Day28 — AI Backend Production Architecture`; no adjacent duplicate Phase 3 status line remains in `README.md`/`AGENTS.md`.

### Notes

- Status-only fix: Phase 3 and Day29 are neither In Progress nor Completed. No Day29 lesson was started; no Day29 lesson file, SQL/Redis design, `projects/ai-backend-data-layer/`, or `knowledge/` was created; no runtime validation was performed or claimed. Day29-Day42 remain Planned.
- Verified with `git diff --check` and a status-consistency search. Did not re-design the Phase 3 curriculum or change `CURRICULUM.md`, `ROADMAP.md`, `docs/devops/day28-ai-backend-production-architecture.md`, the protected prompt/template files, `interview/*`, `cheat_sheets/*`, `examples/*`, or `projects/*`. Historical CHANGELOG entries are unchanged.

---

## v0.1.52 — Phase 3 Backend Foundations Curriculum Planning

Date: 2026-07-18

### Changed

- Planned Phase 3 — Backend Foundations as a Day29-Day42 curriculum (planning only; Day28 remains the last completed lesson and no Phase 3 lesson has started).
- Updated `ROADMAP.md`: Phase 3 heading is now `Phase 3 — Backend Foundations (Day29-Day42)` with an objective, a Day29-Day42 `Planned` table, and refined deliverables. Phase 4 receives no day numbers.
- Updated `CURRICULUM.md`: added a Phase 3 section with the exact Day29 scope, previous/next continuity, and a planned Engineering Artifact, plus concise `Planned` Day30-Day42 entries (title + narrow topic list + status). No lesson bodies, classroom exchanges, or student answers were invented.
- Updated `PROJECT_STATUS.md`: Current Phase is Phase 3 (Planned / Ready — not started); Next Lesson is Day29 — PostgreSQL Foundations and Durable Relational State (Planned / Not started); Day28 stays the last completed lesson.
- Updated `TASKS.md`: replaced the generic Phase 3 preparation block with Day29 preparation tasks and added a Phase 3 Day29-Day42 roadmap with every item unchecked/Planned. Completed Day28 history is unchanged.
- Updated `README.md` and `AGENTS.md`: Next is Day29 with its exact title; Phase 3 is planned/ready but not started; Day28 stays last completed. Engineering and teaching rules are unchanged.
- Updated `docs/devops/day28-ai-backend-production-architecture.md`: the metadata Next Lesson now names Day29's exact planned title, linked to `CURRICULUM.md`/`ROADMAP.md` (the Day29 lesson file does not exist yet, so no broken link is created). The completed Day28 body is unchanged.

### Notes

- Planning only: no Phase 3 lesson document, classroom event, student answer, cheat-sheet/interview content, SQL schema, Redis design, `projects/ai-backend-data-layer/` artifact, or runtime validation was created or completed. SQLAlchemy/Alembic remain Phase 4; Phase 4 day numbers and a Day43 title were not invented.
- Validation actually performed: `git diff --check`, Markdown structure/relative-link inspection of the modified files, and a status-consistency search. No PostgreSQL/SQL/Redis/Docker/migration/transaction/concurrency/backup-restore/integration validation was performed or claimed.
- Did not create `docs/.../day29-*.md`, `projects/ai-backend-data-layer/`, or `knowledge/`; did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, `interview/postgresql.md`, `interview/redis.md`, cheat sheets, examples, or projects. Historical CHANGELOG entries are unchanged.

---

## v0.1.51 — Day28 Review Fixes

Date: 2026-07-18

### Changed

- Corrected an impossible exactly-once implication in the Senior interview question. `docs/devops/day28-ai-backend-production-architecture.md` and `interview/devops.md` now ask how to prevent duplicate durable effects and minimize duplicate provider calls under at-least-once delivery, and what risk still remains, instead of asking to "guarantee a document is not embedded/charged twice". The Chinese explanation now states that DB unique constraint + atomic upsert + checkpoint + ACK-after-durable-write prevent duplicate durable side effects, provider idempotency keys reduce duplicate external calls, and a provider call that succeeds before the local checkpoint write can still be repeated and charged — so exactly-once across independent systems is never promised. The student's real answer ("我忘了") and the "taught directly" note are preserved.
- Fixed a component-ownership wording error in the Day28 lesson: "each component ... owns ONE job" is replaced with "each component has ONE clear responsibility in the Job lifecycle", keeping the core model (FastAPI accepts/exposes; Celery executes; Queue/Redis transports; PostgreSQL owns the durable Job truth; Object Storage owns large bytes).
- Distinguished the worker HPA scaling metric from SLO/diagnostic signals in the Day28 lesson: the worker HPA's primary signal is queue backlog (ideally backlog per worker); oldest queued-job age is closer to user waiting/SLO and is for alerting/diagnosis; throughput indicates progress/under-capacity; a single stuck/poison-pill job can inflate oldest age so it must not be an unqualified scale-up trigger; scaling stays bounded by provider rate limits, cost, and maxReplicas.
- Fixed the stale Day27 metadata: the Next Lesson now links directly to the published Day28 lesson (`day28-ai-backend-production-architecture.md`) instead of describing it as planned.

### Notes

- No runtime validation was performed or claimed. Verified with `git diff --check`, Markdown link checks, and a secret scan of the changed files. No FastAPI/Celery/Redis/PostgreSQL/Object Storage/Kubernetes runtime was built or run. Historical CHANGELOG "Planned" records and Day26/Day27 historical future-connection notes are unchanged. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`, and did not change any student's original answer.

---

## v0.1.50 — Day28 AI Backend Production Architecture Documentation

Date: 2026-07-18

### Added

- Added `docs/devops/day28-ai-backend-production-architecture.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day27->Day28 mental-model evolution). This is the Phase 2 closing lesson.
- Added `examples/ai-backend-architecture/README.md`: a conceptual Production AI Backend Architecture Blueprint (responsibility map, request/upload/job flows, state machines, state/data ownership table, delivery/outbox/idempotency boundaries, retry policy, failure/rollback/data-repair matrix, monitoring/observability signals, security boundaries, and validation limitations with a future runtime validation plan).
- Added Day28 review material to `cheat_sheets/devops.md` (replacing the Day28 placeholder).
- Added Day28 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day28 blueprint and `docs/README.md` to correct the stale directory tree.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day28 completed (no invented Day29/Day30 titles).
- Updated `PROJECT_STATUS.md` to mark Day28 completed, close Phase 2 (Day15-Day28), record the conceptual artifact and validation boundary, and set Next to Phase 3 — Backend Foundations.
- Updated `TASKS.md` with completed Day28 tasks, the Phase 2 Roadmap Day28 status, and Phase 3 preparation.
- Updated `README.md` and `AGENTS.md` progress markers (Phase 2 complete; next Phase 3, no invented lesson number).
- Updated `CHANGELOG.md` with the Day28 repository update.

### Notes

- Day28 assembles FastAPI, Celery, Redis, PostgreSQL, Object Storage, Queue, Monitoring, and Observability into one production AI Backend by defining component responsibilities and lifecycle boundaries: HTTP request lifecycle != long-running job lifecycle (return 202 + job_id, process in a Celery worker); PostgreSQL owns the durable Job truth while Redis delivers/accelerates and Object Storage owns the large bytes; the Transactional Outbox makes business state + intent-to-publish atomic but is still at-least-once, so processing must be idempotent (stable key + unique constraint/upsert, ACK after durable write, leases for exclusive ownership); presigned direct multipart upload with a verified Upload Session; bounded classified retries with backoff/jitter/circuit breaker; monitoring by queue depth vs oldest-age vs throughput; observability correlated on a stable job_id with low-cardinality metrics and append-only events; and a contain -> restore -> identify -> rebuild -> verify data-repair runbook, because compute rollback does not repair persisted data.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (PostgreSQL as final-state-only; DB-first alone solving DB/queue consistency; progress preventing duplicate work; job_status as a correlation id; read-then-upsert treated as exactly-once; code rollback treated as complete). The senior English answer was taught directly after the student said "我忘了", and the internally inconsistent final-summary sentence was corrected.
- Scope/security honesty: the Day28 artifact is conceptual architecture documentation. No FastAPI/Celery/Redis/PostgreSQL/Object Storage/vector/Kubernetes/metrics/log/trace system was created or run; no static code/config/schema validation, queue redelivery, provider failure, load, smoke, rollback, or data-repair test was executed. No real secret, credential, presigned URL, or customer document is committed; at-least-once (not exactly-once) is taught, object keys are not authorization, and metric labels stay low-cardinality.
- Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`; did not create the reserved `knowledge/` structure; did not invent Phase 3 day numbers; and did not rewrite Day01-Day27 lesson bodies.

---

## v0.1.49 — Day27 HPA Metric Fix

Date: 2026-07-17

### Changed

- Made the `rag-platform` API HPA metric configuration explicit. Previously `hpa.cpu.enabled: false` kept the HPA but rendered an empty `metrics:`, which `autoscaling/v2` silently treats as a default 80% average-CPU target — so the switch name did not match the behavior.
- Removed the `hpa.cpu.enabled` toggle from `values.yaml` and the `{{- if .Values.hpa.cpu.enabled }}` condition from `templates/hpa.yaml`. When `hpa.enabled` is true the HPA now always renders one explicit CPU `Resource` metric; when `hpa.enabled` is false no HPA is created and the Deployment renders `replicaCount`.
- Updated `validate_chart.py` to assert there is no `hpa.cpu.enabled` toggle, the HPA template has no `.Values.hpa.cpu.enabled` condition, the HPA always renders an explicit CPU metric, a CPU request exists, the Deployment still guards `spec.replicas` with `if not .Values.hpa.enabled`, and the API HPA still carries no queue-backlog/External worker metric.
- Synced `examples/kubernetes/README.md`, `docs/devops/day27-kubernetes-workloads.md`, and `cheat_sheets/devops.md` to state: the Day27 chart supports one API HPA metric (CPU); `hpa.enabled` controls whether the HPA exists; the explicit CPU target is always rendered when enabled; queue backlog belongs to a worker Deployment and remains a Day28 connection.

### Notes

- Validation actually performed: `git diff --check` clean; `validate_chart.py` PASS (22 structural/values checks). `helm` is not installed and no Kubernetes API server is available, so `helm lint`, `helm template`, schema/admission, and all runtime validation were NOT run / NOT verified and no result is claimed.
- Did not rewrite Day01-Day26, did not start or expand Day28, and did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`. Historical CHANGELOG entries are unchanged.

---

## v0.1.48 — Day27 Review Fixes

Date: 2026-07-17

### Changed

- Fixed image rendering in the `rag-platform` chart: replaced split `image.repository` + `image.tag` with a single `image.reference` (and `postgres.image.reference`) so a deploy-time swap to a `repository@sha256:<digest>` reference renders a valid image. Default stays a non-pullable, mutable, unverified `example.invalid` placeholder.
- Fixed HPA vs Deployment replica ownership: the Deployment now omits `spec.replicas` when `hpa.enabled`, so a `helm upgrade` does not reset the HPA-managed replica count; when the HPA is disabled it renders `replicaCount`.
- Fixed the queue-backlog scaling scope: removed the `queueBacklog` External metric and its Values from the API HPA (wiring it to the API would scale the producer, not the consumer). The classroom conclusion is preserved in the lesson/README/cheat sheet/interview — queue backlog/backlog-per-worker must scale the worker Deployment that consumes the queue, needs an external/custom metrics adapter, and arrives with Day28.
- Resolved a `TASKS.md` status contradiction: the stale unchecked "Day27 Preparation — Kubernetes Workloads" block is now recorded as completed history (Day27 = Completed, Day28 = Planned/Next).
- Added real Markdown cross-links from `docs/devops/day27-kubernetes-workloads.md` (previous lesson, engineering artifact, cheat sheet, interview, roadmap/curriculum).
- Corrected imprecise wording: an Ingress resource declares Host/Path/TLS intent while the Ingress Controller implements routing and commonly performs TLS termination.
- Updated `examples/kubernetes/rag-platform/validate_chart.py` to check the single image reference, the HPA-guarded `spec.replicas`, and the absence of a queue-backlog worker metric; its output no longer hardcodes "helm not installed" and instead states "helm lint/template: not run by this validation script".

### Notes

- Validation actually performed: `git diff --check` clean; `validate_chart.py` PASS (19 structural/values checks, including image `.reference`, HPA-guarded replicas, and no queue metric). `helm` is not installed and no Kubernetes API server is available, so `helm lint`, `helm template`, schema/admission, and all runtime validation were NOT run / NOT verified and no result is claimed.
- Did not rewrite Day01-Day26, did not start or expand Day28, and did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`. Historical CHANGELOG entries (including the originally-correct Day27 Planned records) are unchanged.

---

## v0.1.47 — Day27 Kubernetes Workloads Documentation

Date: 2026-07-17

### Added

- Added `docs/devops/day27-kubernetes-workloads.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day26->Day27 mental-model evolution).
- Added the `examples/kubernetes/rag-platform/` teaching-only Helm chart: `Chart.yaml`, base/dev/prod `values*.yaml`, `templates/` (`_helpers.tpl`, configmap, deployment with Rolling Update, service, ingress, `autoscaling/v2` hpa, headless-service, statefulset), and a static-only `validate_chart.py`.
- Added Day27 review material to `cheat_sheets/devops.md`.
- Added Day27 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/kubernetes/README.md` with the Day27 chart layout, validation ladder, prerequisites, and security boundaries.
- Updated `examples/README.md` to index the Day27 Helm chart.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day27 completed (Day28 left Planned).
- Updated `PROJECT_STATUS.md` to mark Day27 completed and set Next to Day28.
- Updated `TASKS.md` with completed Day27 tasks and Day28 preparation.
- Updated `README.md` and `AGENTS.md` progress markers (last completed Day27, next Day28).
- Updated `CHANGELOG.md` with the Day27 repository update.

### Notes

- Day27 extends the Day26 foundation into production workload management: Ingress as L7 Host/Path/TLS routing to Services (resource declares, controller implements); HPA (`autoscaling/v2`) updating desired replicas on a scale target from meaningful pressure (CPU vs queue backlog, bounded by upstream capacity); Deployment Rolling Update with `maxSurge`/`maxUnavailable` distinguished from rollback and Blue-Green; StatefulSet stable identity + per-Pod PVC + headless Service + ordered lifecycle (explicitly NOT database replication/HA); and Helm templates vs Values vs Release with a lint/template/API/runtime validation ladder.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (Rolling Update called a rollback strategy; three PVCs mistaken for three data copies; Helm assumed to auto-roll back; a Blue-Green plan offered for a Rolling Update; HPA described as directly scaling Pods).
- Security/scope honesty: the chart is teaching-only and not deployable as-is. Sensitive values are referenced via `existingSecret` (never inlined in any values file); no real credential, token, certificate, or verified/represented-as-verified image digest is committed; images use the non-pullable `example.invalid` TLD with a mutable `:replace-with-verified-digest` tag. Readiness 200 is not business success; a StatefulSet is not HA; deleting v2 Pods is not a rollback.
- Validation: `validate_chart.py` ran and passed deterministic static checks (Chart/values YAML parse; Deployment selector == Pod template labels == Service selector via a shared helper; HPA `scaleTargetRef` and Ingress backend use the same fullname helper as the Deployment/Service; `networking.k8s.io/v1`, `autoscaling/v2`, `apps/v1`; Rolling Update `maxSurge`/`maxUnavailable`; StatefulSet `volumeClaimTemplates`; headless `clusterIP: None`; CPU HPA has a CPU request; sensitive values referenced not inlined; non-pullable images). `helm` is not installed in this environment, so `helm lint` and `helm template` were NOT run; with no Kubernetes API server, schema/admission and all runtime validation (Ingress/DNS/TLS routing, HPA scaling, Rolling Update, rollback, PVC provisioning, StatefulSet lifecycle, PostgreSQL replication/failover, backups) were NOT performed and no result is claimed.
- Ingress Controller, DNS, load balancer, TLS material, metrics adapters, and PostgreSQL HA/backup are documented as external prerequisites, not implemented. Day28 (FastAPI/Celery/Redis/PostgreSQL/object storage/queue/monitoring/observability) is labeled a future connection. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day26 lesson body.

---

## v0.1.46 — Roadmap Status Consistency Fix

Date: 2026-07-17

### Changed

- Fixed `ROADMAP.md` Phase 1 table: converted it to the same three-column `Status` format as Phase 2 and marked Day01-Day14 all `✅ Completed`, removing the stale `⏳ Day02` current-lesson marker. Topics and order are unchanged. Phase 2 remains Day15-Day26 Completed, Day27 and Day28 Planned. Now consistent with `CURRICULUM.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, and `AGENTS.md`.

---

## v0.1.45 — Day26 Review Fixes

Date: 2026-07-17

### Changed

- Fixed `TASKS.md` status consistency: `Current Phase` is now `Phase 2 — Engineering Foundations`, and the Phase 2 Roadmap marks Day26 Completed (Day27 and Day28 remain Planned), removing the Day26 Planned-vs-Completed contradiction.
- Updated the stale repository entry points: `README.md` now shows Phase 2, last completed Day26, next Day27; `AGENTS.md` Current Progress replaces the outdated "Next Lesson: Mutable vs Immutable" with Phase 2 / Day26 completed / Day27 next (engineering and teaching rules unchanged).
- Corrected the Deployment/scheduler responsibility in `docs/devops/day26-kubernetes-foundations.md`: the Deployment/ReplicaSet controller creates or maintains replacement Pods, and kube-scheduler assigns unscheduled Pods to Nodes (the Deployment does not schedule).
- Replaced the invalid `REPLACE_WITH_*` image strings in `examples/kubernetes/ai-backend-baseline.yaml` with syntactically valid, non-pullable OCI references on the reserved `.invalid` TLD (`example.invalid/acme/rag-api:replace-with-verified-digest`, `example.invalid/acme/log-sidecar:replace-with-verified-digest`); comments state the `:replace-...` tag is mutable, not immutable or verified, and must be swapped for a CI-verified `@sha256` digest before deploy. Synced `examples/kubernetes/README.md`.
- Made static validation reproducible: added `examples/kubernetes/validate_manifest.py` (PyYAML-only) and documented an isolated dependency install; the README now shows the actual PASS output.

### Notes

- Static validation actually run: four YAML documents (ConfigMap/Secret/Deployment/Service); Deployment selector == Pod template labels; Service selector == Pod template labels; `replicas == 3`; Service `targetPort` matches a container named port; the API container references the ConfigMap and the Secret; the logging sidecar does NOT reference the Secret — all PASS.
- No Kubernetes API server was available, so `kubectl` schema/admission validation was NOT completed and no Kubernetes runtime result (Pod Ready, Service DNS, Secret injection, Pod replacement, rollback) is claimed.
- Scope unchanged: Day26 is not rewritten and Day27 is not started. No real secret, key, or verified image digest is committed. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day25 lesson body.

---

## v0.1.44 — Day26 Kubernetes Foundations Documentation

Date: 2026-07-17

### Added

- Added `docs/devops/day26-kubernetes-foundations.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day25->Day26 mental-model evolution).
- Added `examples/kubernetes/ai-backend-baseline.yaml` (ConfigMap `rag-api-config`, Secret template `rag-api-secrets` with placeholders only, Deployment `rag-api` with 3 replicas and a FastAPI + logging-sidecar Pod template, Service `rag-api`).
- Added `examples/kubernetes/README.md` (object model, static-vs-runtime validation, security boundaries, and runtime limitations).
- Added Day26 review material to `cheat_sheets/devops.md`.
- Added Day26 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day26 Kubernetes example.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day26 completed (Day27 left Planned).
- Updated `PROJECT_STATUS.md` to mark Day26 completed and set Next to Day27.
- Updated `TASKS.md` with completed Day26 tasks and Day27 preparation.
- Updated `CHANGELOG.md` with the Day26 repository update.

### Notes

- Day26 moves from one-time container startup and manual deployment operations to declarative desired state and continuous reconciliation: desired state vs a one-time command (observe -> diff -> act), Pod as the smallest deployable unit of one or more tightly coupled containers (Pod != container; co-locate only shared fate), Deployment as a Pod template + replica count that recreates replicas but does not schedule (the scheduler picks the Node), Service as stable label-based discovery for changing Pods, ConfigMap as non-sensitive runtime config that keeps the verified image digest unchanged, and Secret as sensitive data requiring controlled access.
- Preserved the actual classroom record, including the student's Chinese and English answers, the reasonable errors (for example "separate Pods imply manual operation", "Deployment schedules Pods", and Base64 `解密` corrected to `解码`), and all material misconceptions and corrections.
- Security/scope honesty: `stringData` is plaintext in the manifest and holds placeholders only; Base64 is encoding, not encryption; a Secret is not an automatic vault. No real key, password, token, certificate, private endpoint, or verified/represented-as-verified image digest is committed; image fields are `REPLACE_*` placeholders supplied out of band. `replicas: 3` is not three business-ready replicas, and `/health` 200 is not business success.
- Validation: static checks ran (YAML parses as four documents ConfigMap/Secret/Deployment/Service; Deployment selector == Pod template labels == Service selector `app: rag-api`; `replicas == 3`). No Kubernetes API server was available, so `kubectl` client/schema validation was NOT completed and no `kubectl apply`, Pod scheduling, image pull, container startup, ConfigMap/Secret injection, Service DNS/routing, Pod replacement, Secret rotation, business smoke test, or failure/rollback runtime result is claimed. Markdown was checked and links to the example resolve.
- Ingress, Autoscaling, Rolling Update, StatefulSet, and Helm are labeled as Day27 future connections, not taught or validated in Day26. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day25 lesson body.

---

## v0.1.43 — Day25 Deployment Foundations Documentation

Date: 2026-07-16

### Added

- Added `docs/devops/day25-deployment-foundations.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day24->Day25 mental-model evolution).
- Added `examples/deployment/nginx/nginx.conf.example` (reverse proxy + TLS termination, HTTP->HTTPS 308, trusted proxy headers, blue-green `api_v2` upstream, AI streaming location).
- Added `examples/deployment/README.md` (request path, zero-downtime blue-green runbook, rollback, and identity notes).
- Added Day25 review material to `cheat_sheets/devops.md`.
- Added Day25 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day25 deployment example.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day25 completed.
- Updated `PROJECT_STATUS.md` to mark Day25 completed and set Next to Day26.
- Updated `TASKS.md` with completed Day25 tasks and Day26 preparation.
- Updated `CHANGELOG.md` with the Day25 repository update.

### Notes

- Day25 turns one CI-verified immutable image into a safely reachable, observable, reversible production service: stable public entry (Domain/DNS/Nginx :443), reverse proxy (listen/server_name/proxy_pass), TLS as confidentiality + integrity + server authentication (terminating at Nginx), HTTP->HTTPS 308 (and why it cannot protect an already-sent credential), certificate lifecycle and Nginx master/worker (reload vs restart), trusted proxy context (header != identity), promoting the exact immutable digest, API blue-green with verify/switch/observe/drain/rollback, PostgreSQL Expand-Migrate-Contract, compatible worker rollout, serialized deployment with a least-privilege short-lived identity, AI streaming (buffering vs caching, four timeouts, heartbeat), and non-atomic DNS TTL.
- Preserved the actual classroom record, including the student's Chinese and English answers, the imperfect wording (for example the accidental "quantity gate" corrected to "quality gate", and the GitHub Actions `${{ }}` vs Nginx `$variable` confusion), and all material misconceptions and corrections.
- The Nginx artifact is example-only: reserved `example.com` domain, placeholder certificate paths, no committed certificate, private key, secret, credential, or business/medical data. No GitHub Actions expressions are used in Nginx.
- Validation: `nginx` is not available in this environment, so `nginx -t` was NOT run and no successful Nginx validation is claimed; the configuration was reviewed statically. The Markdown was checked, links to the example resolve, and no secrets are present.
- `prompts/teaching-session-prompt.md` already exists in the repository (the separate live-teaching standard) and was left unchanged. Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day24 lesson body.

---

## v0.1.42 — Day24 Review: Portable, Restrictive Local Secret Setup

Date: 2026-07-14

### Changed

- Made the local secret-file setup in `examples/docker/compose/README.md` portable across Bash and zsh and more restrictive: replaced the `read`-with-prompt-option form (which fails in zsh with `read: -p: no coprocess`) with `printf '...' >&2` + `IFS= read -rs`, and added `chmod 700 .secrets` and `umask 077` so secret files are created owner-only (`600`) in a `700` directory.
- Updated the Commands section to reference the portable prompt flow.

### Notes

- Documentation-only fix; no secret value (real or fake) is present, and no course content or Compose YAML changed.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day24 lesson body.

---

## v0.1.41 — Day24 Review Fixes

Date: 2026-07-14

### Changed

- Removed the two placeholder secret values (an example PostgreSQL password and an example OpenAI key) from `examples/docker/compose/README.md`; the secret files are now created via an interactive prompt flow so no password or API-key value is written into the repository.
- Restructured `docs/devops/day24-docker-compose.md` to the exact LESSON_TEMPLATE_v2 16-section order: added an explicit `# Lesson Metadata` section, moved the study-time estimate into it, promoted `Learning Objectives` to a top-level section, and removed the standalone `Estimated Study Time` section (content preserved, only relocated).
- Added a production image contract to `examples/docker/compose/README.md`: `build:` + `rag-app:local` is local/teaching; a full local start needs `docker compose up --build` (or an explicit build) first; in production, `api` and `worker` should reference the same immutable, CI-built/verified image identity (preferably by digest) rather than rebuilding per environment.

### Notes

- Small-scope review fix; no lesson teaching content or classroom record was rewritten.
- No real or fake secrets remain in the repository; `<digest>` is a syntax placeholder, not a secret.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day23 lesson.

---

## v0.1.40 — Day24 Docker Compose Documentation

Date: 2026-07-14

### Added

- Added `docs/devops/day24-docker-compose.md` (LESSON_TEMPLATE_v2; first lesson under Master Prompt v3.2 with an explicit knowledge-continuity chain and a Day23->Day24 mental-model evolution).
- Added a multi-service Compose example: `examples/docker/compose/compose.yaml`, `compose.dev.yaml`, `.env.example`, and `README.md` (FastAPI API + Worker + Redis + PostgreSQL).
- Added Day24 review material to `cheat_sheets/devops.md`.
- Added Day24 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` and `examples/docker/fastapi/README.md` (replaced the Day24 future note with a link to the released lesson/example).
- Added `.secrets/` to `.gitignore` so local Compose secret files are never committed.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day24 completed.
- Updated `PROJECT_STATUS.md` to mark Day24 completed and set Next to Day25.
- Updated `TASKS.md` with completed Day24 tasks and Day25 preparation.
- Updated `CHANGELOG.md` with the Day24 repository update.

### Notes

- Day24 turns Day23's single reproducible container into a version-controlled multi-service system: why Compose exists, started != ready (`depends_on` short vs `condition: service_healthy`, healthchecks, and application retry), Project/Service/Image/Container and rebuild vs recreate, the declarative model and YAML, host ports/service DNS, network segmentation (queue vs database) for least access, volumes and `down --volumes`, environment vs secret vs governed business data, the local development workflow, base + development override, and the Compose production boundary vs Kubernetes.
- Preserved the actual classroom record: the student's Chinese and English answers (including the imperfect final synthesis and the weak English attempts) and all material misconceptions and corrections, plus the YAML-evidence-over-chat-rendering correction.
- Compose example uses the current Compose Specification (no top-level `version:`), publishes only the API host port, uses service DNS, segments networks, mounts a named `postgres_data` volume, and grants role-scoped secrets via files under a git-ignored `.secrets/` directory. No real secrets, `.env` credentials, API keys, passwords, connection strings, customer prompts, or medical data were committed.
- Validation: `docker` is not available in this environment, so the stack was NOT started; the base and development-override Compose YAML were parsed and structurally validated, and the merged model was checked. `docker compose config` / `up` should be run in a real project that provides the Day23 Dockerfile, `requirements.txt`, an `app/` package, and the local secret files.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `AGENTS.md`, `interview/docker.md`, or any Day01-Day23 lesson.

---

## v0.1.39 — Master Prompt v3.2: Curriculum Continuity & Update Standards

Date: 2026-07-13

### Changed

- Upgraded `prompts/master-prompt.md` from v3.1 to v3.2 (add-only; fully compatible with v3.1, no lesson or structure migration):
  - Added a Knowledge Continuity Requirement to the Roadmap Position section: every lesson must show Previous Knowledge -> Current Concept -> Future Production Usage, name the reused mental models and prerequisite lessons, justify its roadmap position, and identify future dependents.
  - Added a Mental Model Evolution rule to the Student Mistakes section: preserve Initial Mental Model -> Reasoning -> Correction -> Final Engineering Mental Model, not only the mistake.
  - Strengthened Relevant Framework Connections with an explicit "Avoid Forced Technology Connections" rule: connect a technology only when technically meaningful, prefer software-engineering/backend/cloud-native/AI-backend scenarios, and label non-substantive links as future connections.
  - Added `PREVIOUS_LESSON_CONNECTION`, `KNOWLEDGE_CHAIN_POSITION`, and `FUTURE_LESSON_CONNECTION` fields to the Daily Input Block so future agents can place a lesson in the full curriculum.
- Updated `prompts/README.md` to reference Master Prompt v3.2.

### Notes

- This is a repository-update-standard improvement, not a content change: no lesson documents, templates, cheat sheets, interview notes, or folder structure were modified.
- Did not modify `LESSON_TEMPLATE_v2.md`, `LESSON_TEMPLATE.md`, `AGENTS.md`, any Day01–Day23 lesson, or the Day23 completion status.
- Affects Day24+ lesson generation: future daily inputs should provide the continuity fields, and every future lesson must document the knowledge chain and mental-model evolution.

---

## v0.1.38 — Day23 Review: Docker Example & Reproducibility Corrections

Date: 2026-07-13

### Changed

- `examples/docker/fastapi/README.md`: the PostgreSQL demo now sets `-e POSTGRES_DB=app` so the created database matches the FastAPI `DATABASE_URL`, with a note that `POSTGRES_*` init variables only apply the first time the data directory is initialized (an existing `pgdata` volume will not auto-create a new database).
- `examples/docker/fastapi/README.md`: made the immutable-replacement flow self-consistent — it now builds and starts `app-v1`, builds `v2`, starts `app-v2` on a different temporary host port, health-checks `app-v2`, notes that traffic switching needs a reverse proxy/load balancer (zero downtime is Day25), and only then removes `app-v1`.
- `examples/docker/fastapi/Dockerfile`: create and `chown` `/app/data` before `USER appuser` so the non-root user can write to a mounted named volume; corrected the base-image comment to describe `python:3.12-slim` as a constrained (mutable) version line, with a digest-pin option for stronger reproducibility.
- `docs/devops/day23-docker-fundamentals.md` and `cheat_sheets/devops.md`: corrected the `python:3.12-slim` description — a constrained version line, not an immutable pin — and added the digest trade-off (reproducibility vs. deliberate security updates), consistent with Day22's immutable-digest principle.

### Notes

- Small-scope review fix; did not rewrite the Day23 chapter or extend into Day24 Docker Compose.
- No real secrets or `.env` credentials were added; `example` remains a throwaway local placeholder and no image digest was invented.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `AGENTS.md`, or the Day23 completion status in `CURRICULUM.md`/`ROADMAP.md`/`PROJECT_STATUS.md`.

---

## v0.1.37 — Day23 Docker Fundamentals Documentation

Date: 2026-07-13

### Added

- Added `docs/devops/day23-docker-fundamentals.md` (LESSON_TEMPLATE_v2).
- Added a production-oriented FastAPI Docker example: `examples/docker/fastapi/Dockerfile`, `examples/docker/fastapi/.dockerignore`, and `examples/docker/fastapi/README.md` (reproducible build/run, named-volume, and user-defined-network commands).
- Added Day23 review material to `cheat_sheets/devops.md`.
- Added Day23 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day23 Docker example.
- Updated `CURRICULUM.md` to mark Day23 completed (released lesson path + v2 template note).
- Updated `ROADMAP.md` to mark Day23 completed.
- Updated `PROJECT_STATUS.md` to mark Day23 completed and set Next to Day24.
- Updated `TASKS.md` with completed Day23 tasks and Day24 preparation.
- Updated `CHANGELOG.md` with the Day23 repository update.

### Notes

- Day23 explains the immutable Docker image behind Day22's "build once, deploy many": why Docker exists, a container as an isolated process (namespaces + cgroups, not a VM), image vs container, image layers vs the per-container writable layer with build-cache ordering, the Dockerfile (FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT as IaC), build vs run, volumes (separating compute from data lifecycle), networks (service DNS, not localhost), and immutable replacement.
- Preserved the actual classroom record, including the student's original Chinese answers and all 12 misconceptions and corrections (image "generates images", rebuild upgrading running containers, build cache vs writable layer, shared image storage, Dockerfile-vs-IaC, startup vs writable layer, `docker run` vs CMD/ENTRYPOINT, ports in the writable layer, writable layer "cannot" store data, network vs filesystem isolation, container communication default, smaller image vs performance).
- Kept Day23 within scope: Container, Image, Layer, Dockerfile, Build, Run, Volume, Network. Production extensions (non-root user, health check, `.dockerignore`, secrets at runtime, immutable replacement) were kept proportional. Docker Compose implementation is deferred to Day24; no Compose syntax was taught.
- Connected the lesson to FastAPI (slim base, stateless app, service DNS), Docker internals, and GitHub Actions (quality gate before build, cache-aware ordering, deploy the same immutable identity). Playwright was mentioned only in passing.
- The Docker example is example-only (no FastAPI app exists in this repo); it contains no real secrets or `.env` credentials, uses a pinned slim base, a non-root user, and a health check, and keeps a narrow build context via `.dockerignore`.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `LESSON_TEMPLATE.md`, `TRAINING_WORKFLOW.md`, or any Day01–Day22 lesson.

---

## v0.1.36 — Day22 Review: Correct Reusable Workflow Invocation Path

Date: 2026-07-11

### Changed

- Corrected the caller example in `examples/github-actions/reusable-fastapi-ci.example.yml`: removed the invalid `owner/repo/examples/github-actions/...@main` path and documented the real two-step usage — copy the file directly into `.github/workflows/reusable-fastapi-ci.yml` in a shared-workflow repository, then call it at the job level as `owner/repo/.github/workflows/reusable-fastapi-ci.yml@<commit-sha>` (prefer a commit SHA over `@main`).
- Synced `docs/devops/day22-github-actions-advanced.md`: the `examples/` reusable-workflow file is a teaching template, callable only after being copied into `.github/workflows/`; clarified that a composite action may live in any directory and is called via a step-level `uses`, while a reusable workflow must live directly under `.github/workflows/` (no subdirectories) and is called via a job-level `uses`.
- Updated `examples/README.md` reusable-workflow entry accordingly.
- Optional hardening: added a `trap cleanup EXIT` container cleanup to the `verify-image` smoke test in `examples/github-actions/github-actions-advanced.example.yml`.
- Updated `TASKS.md` with the review fix.

### Notes

- Small-scope fix limited to the reusable-workflow invocation path (plus one optional cleanup improvement). Did not rewrite the Day22 chapter.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, Day01–Day21 lessons, or the Day22 completion status.
- All example YAML still parses; no credentials are hardcoded.

---

## v0.1.35 — Day22 Review: Image Verification & Workflow Reuse Examples

Date: 2026-07-11

### Added

- Added `examples/github-actions/composite-python-quality/action.yml` — a minimal composite action (`runs.using: composite`, typed inputs, `shell` on every `run` step, no `jobs`/`runs-on`, no hardcoded secrets).
- Added `examples/github-actions/reusable-fastapi-ci.example.yml` — a minimal reusable workflow (`on: workflow_call`, typed inputs, a complete `quality` job, least-privilege permissions), with a caller `jobs.<id>.uses` example in comments.

### Changed

- Reworked `examples/github-actions/github-actions-advanced.example.yml`: the `build` job outputs the immutable image digest; a new `verify-image` job pulls and runs that exact digest and smoke-tests a health endpoint; `deploy` now depends on `build` and `verify-image` and promotes the same digest with no rebuild and no mutable `:latest`.
- Fixed test-report upload to run on failure with `if: always()` and `if-no-files-found: warn`, and switched the test command to also emit `junit.xml` (example; adjust in a real project).
- Synced `docs/devops/day22-github-actions-advanced.md`: added the integrity chain (source tests validate source; image verification validates the built runtime artifact; deployment promotes the exact verified digest), the artifact `if: always()` + `if-no-files-found` note, and references to the new composite and reusable examples.
- Updated `examples/README.md`, and added a minimal note each to `cheat_sheets/devops.md` and `interview/devops.md`.
- Updated `TASKS.md` with the Day22 review fixes.

### Notes

- Small-scope review fix; did not rewrite the Day22 chapter.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, Day01–Day21 lessons, or the Day22 completion status in `CURRICULUM.md`, `ROADMAP.md`, or `PROJECT_STATUS.md`.
- Example workflows remain example-only (not under `.github/workflows/`); all YAML parses, action versions are pinned, and no credentials are hardcoded (only `${{ secrets.* }}`).

---

## v0.1.34 — Day22 GitHub Actions Advanced Documentation

Date: 2026-07-11

### Added

- Added `docs/devops/day22-github-actions-advanced.md` (LESSON_TEMPLATE_v2).
- Added `examples/github-actions/github-actions-advanced.example.yml` (comprehensive advanced CI/CD workflow example).
- Added Day22 review material to `cheat_sheets/devops.md`.
- Added Day22 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day22 example.
- Updated `CURRICULUM.md` to mark Day22 completed (released lesson path + v2 template note).
- Updated `ROADMAP.md` to mark Day22 completed.
- Updated `PROJECT_STATUS.md` to mark Day22 completed and set Next to Day23.
- Updated `TASKS.md` with completed Day22 tasks and Day23 preparation.
- Updated `CHANGELOG.md` with the Day22 repository update.

### Notes

- Day22 extends the basic workflow into a production pipeline: matrix (one job template expanded by variables; does not reduce executions; jobs are isolated), `fail-fast` decision by remaining-combination value, cache (re-creatable acceleration) vs artifact (formal output), composite action (steps) vs reusable workflow (jobs), and the `needs`/`if`/`continue-on-error` control mechanisms.
- Deployment pipeline taught as build once / deploy many: promote one immutable image digest from a container registry (not a rebuild, not a mutable `:latest`), gated by a production Environment with risk-qualified approval and production-only Secrets, serialized with a `concurrency` group and `cancel-in-progress: false`.
- Preserved the actual classroom record, including the student's original wording and all 10 misconceptions and corrections (matrix purpose/environment, fail-fast criterion, composite vs reusable, needs vs artifact, conditional execution, approval ownership, artifact-reuse integrity, `concurrency` shape, Docker digest delivery).
- Corrected terminology in artifacts: `continue-on-error`, `cancel-in-progress`, `concurrency` block, immutable image digest.
- Connected the lesson to FastAPI CI, Docker registry/digest deployment, Playwright cache, and AI backend evaluation-gated releases with production Secrets scoped to the deploy job.
- The example workflow is intentionally NOT under `.github/workflows/` (documentation repository), is valid YAML, pins action versions, and references secrets safely (no hardcoded credentials).
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE.md`, `LESSON_TEMPLATE_v2.md`, `TRAINING_WORKFLOW.md`, or any Day01–Day21 lesson.

---

## v0.1.33 — Add Repository Update Standard (Master Prompt v3.1)

Date: 2026-07-11

### Added

- Added `prompts/master-prompt.md` — the official long-term repository update standard (Claude Code Master Prompt v3.1) for Day21 and all future lessons.

### Changed

- Updated `prompts/README.md` to document the repository update standard and how it pairs with `LESSON_TEMPLATE_v2.md`.

### Notes

- v3.1 aligns with the Day21 review corrections: runner lifecycle language (one runner execution context; hosted fresh/ephemeral vs self-hosted persistent), stronger self-hosted runner security guidance, complete Secrets and Environment Variables coverage, and GitHub Action version pinning (movable tag vs commit SHA).
- No lessons or status files changed; this only adds the standing update standard to the repository.
- Did not modify `LESSON_TEMPLATE.md`, `LESSON_TEMPLATE_v2.md`, `ROADMAP.md`, or `CURRICULUM.md`.

---

## v0.1.32 — Day21 Review Corrections

Date: 2026-07-11

### Changed

- Corrected the universal claim "One Job = One Fresh Runner" in `docs/devops/day21-github-actions-fundamentals.md`: a job is assigned to one runner execution context; GitHub-hosted runners are fresh and ephemeral per job, while self-hosted runners may persist state between jobs unless explicitly made ephemeral or isolated. Updated the core mental model, mappings, concept, misconception, framework connection, mental model summary, takeaway, and checklist consistently.
- Added a new Day21 concept "Secrets and Environment Variables" (required by `CURRICULUM.md`): environment-variable scope at workflow/job/step level, secrets vs environment variables, safe injection with `${{ secrets.NAME }}`, fork-PR secret handling, and a FastAPI/AI backend example. Added a matching common misconception.
- Expanded the self-hosted runner security trade-off: more control does not automatically mean safer. Documented persistent state, untrusted fork PRs, credential leakage, host compromise, and internal blast-radius risks, plus mitigations. Added a security note to the runner concept.
- Clarified action version pinning: `@v4` is a movable major-version tag, while a full commit SHA provides stronger supply-chain immutability. Added guidance in the step concept and the `uses` vs `run` trade-off.

### Notes

- Updated the Day21 lesson, `cheat_sheets/devops.md`, and `interview/devops.md` consistently, and recorded the change here.
- Did not change unrelated files, status files, or other lessons.
- Did not modify the example workflow (`examples/github-actions/fastapi-ci.example.yml`), templates, `ROADMAP.md`, or `CURRICULUM.md`.

---

## v0.1.31 — Day21 GitHub Actions Fundamentals Documentation

Date: 2026-07-10

### Added

- Added `docs/devops/day21-github-actions-fundamentals.md` (first lesson using LESSON_TEMPLATE_v2).
- Added `examples/github-actions/fastapi-ci.example.yml` (example-only FastAPI CI workflow).
- Added `examples/README.md`.
- Added Day21 GitHub Actions review material to `cheat_sheets/devops.md`.
- Added Day21 GitHub Actions interview questions to `interview/devops.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day21 completed (with released lesson path and v2 template note).
- Updated `ROADMAP.md` to mark Day21 completed.
- Updated `PROJECT_STATUS.md` to mark Day21 completed and set Next to Day22.
- Updated `TASKS.md` with completed Day21 tasks and Day22 preparation.
- Updated `CHANGELOG.md` with the Day21 repository update.

### Notes

- Day21 implements the Day20 CI/CD principles with GitHub Actions, taught as engineering thinking: workflow as code, the execution model (Event -> Trigger -> Workflow -> Runner -> Job -> Step -> Result), workflow vs runner, triggers and event-driven cost control, GitHub-hosted vs self-hosted runners (control, not speed), job as one fresh runner, steps with `run`/`uses`/`with`, checkout, and the quality gate before build.
- Preserved the actual classroom misconceptions and corrections: `on` mistaken for the OS, `run` mistaken for a trigger, `uses` mistaken for a shell command, preferring one big job, and Ruff failure not blocking the Docker build.
- Followed LESSON_TEMPLATE_v2: added required Core Mental Model, Common Misconceptions, Engineering Trade-offs, technology-agnostic Hands-on Exercises (YAML artifact), Relevant Framework Connections (not Playwright-forced), first-class AI Backend Connections, and a Mental Model Summary.
- The engineering artifact is a GitHub Actions workflow YAML. The example is intentionally NOT under `.github/workflows/` because this is a documentation repository with no FastAPI app to execute; it is clearly labeled example-only, uses pinned action versions, and references secrets safely (no hardcoded credentials).
- Connected the lesson to FastAPI CI, Docker build stage, and AI backend GPU/self-hosted runners, scheduled evaluation, and prompt regression testing.
- Did not modify `LESSON_TEMPLATE.md`, `LESSON_TEMPLATE_v2.md`, `TRAINING_WORKFLOW.md`, or Day01–Day20 lessons.

---

## v0.1.30 — Lesson Template v2 (Official Standard from Day21)

Date: 2026-07-10

### Added

- Added `LESSON_TEMPLATE_v2.md`, the new official lesson standard starting with Day21.

### Notes

- v2 is built from `LESSON_TEMPLATE.md` and preserves its strengths (WHY before HOW, engineering thinking, roadmap position, lesson map, interview prep, today's takeaway, checklist, ASCII diagrams, trade-offs, production examples).
- New 16-section architecture: Lesson Metadata, Learning Objectives, Why This Matters, Roadmap Position, Lesson Map, Core Mental Model, Main Concepts, Common Misconceptions, Engineering Trade-offs, Hands-on Exercises, Relevant Framework Connections, AI Backend Connections, English Interview, Mental Model Summary, Today's Takeaway, Before Next Lesson Checklist.
- Made the Core Mental Model and Mental Model Summary required sections.
- Required the classroom loop inside Main Concepts (Tech Lead Question -> Student Thinking -> Student Answer -> Tech Lead Review -> Engineering Thinking -> Production Example -> Framework Connection -> Exercise).
- Added required Common Misconceptions (wrong-vs-right) and a dedicated Engineering Trade-offs section.
- Replaced the fixed FastAPI/Playwright sections with a technology-agnostic Relevant Framework Connections section, and made AI Backend Connections a first-class section.
- Made exercises and Learning Objectives artifact-agnostic (Python, YAML, Shell, Dockerfile, Kubernetes manifest, GitHub workflow, infrastructure config, architecture diagram), not Python-only.
- Updated the AI Collaboration model to be future-proof (generic Repository Coding Agent — Claude Code / Codex — instead of hardcoding one).
- Backward compatibility: did not modify `LESSON_TEMPLATE.md` or any Day01–Day20 lesson. Older lessons remain valid and require no migration.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, `CURRICULUM.md`, or existing lessons.

---

## v0.1.29 — Day20 Corrections & Phase 2 Curriculum Upgrade

Date: 2026-07-10

### Changed

- Corrected `docs/devops/day20-ci-cd-foundations.md` to distinguish Continuous Delivery from Continuous Deployment (targeted edits, no rewrite): Delivery keeps an always-ready, production-ready release candidate with optional manual approval, while Deployment releases to production automatically once every required quality gate passes.
- Removed statements implying "CD always deploys automatically"; clarified Delivery = always ready to release, Deployment = actually releasing.
- Updated the delivery lifecycle diagram into a Continuous Delivery version (with optional Manual Approval before Production) and a Continuous Deployment version (Merge -> All Gates Pass -> Automatic Production Deployment).
- Aligned `cheat_sheets/devops.md` and `interview/devops.md` with the Delivery vs Deployment distinction.
- Upgraded `ROADMAP.md` Phase 2 into the official Day15–Day28 roadmap: Git Engineering (Day15-19), DevOps Foundations (Day20-22), Container Engineering (Day23-24), and Production Engineering (Day25-28), with a Software Delivery Lifecycle overview.
- Upgraded `CURRICULUM.md` with Day21–Day28 topics and statuses and a "Why This Curriculum" explanation (WHY before HOW).
- Updated `PROJECT_STATUS.md` Next to Day21 — GitHub Actions Fundamentals.
- Updated `TASKS.md` with Day21 preparation and the Phase 2 Day21–Day28 roadmap.

### Notes

- This is a curriculum alignment update, not a content rewrite. Day15–Day20 lessons were not rewritten.
- `ROADMAP.md` was intentionally updated as part of this official curriculum upgrade.
- Did not modify `TRAINING_WORKFLOW.md` or `LESSON_TEMPLATE.md`.

---

## v0.1.28 — Day20 CI/CD Foundations Documentation

Date: 2026-07-09

### Added

- Added `docs/devops/day20-ci-cd-foundations.md` (new `docs/devops/` folder).
- Added `cheat_sheets/devops.md` (new DevOps cheat sheet).
- Added `interview/devops.md` (new DevOps interview notes).

### Changed

- Updated `CURRICULUM.md` to add Day20 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day20 completed.
- Updated `TASKS.md` with completed Day20 tasks and Day20 review.
- Updated `CHANGELOG.md` with the Day20 repository update.

### Notes

- Day20 teaches CI/CD as replacing trust and manual work with automated process: why "I tested locally" is insufficient, CI as a trusted quality process, a pipeline as a standard workflow with stage dependency, fail-fast, and fast feedback, a quality gate as risk control protecting main/production/team/users, CD as repeatable/consistent/reliable/scalable delivery, Workflow as Code, and Everything as Code.
- Assembled the full software delivery lifecycle connecting Day15-Day20: Idea -> Issue -> Project -> Branch -> Commit -> Pull Request -> CI -> Pipeline -> Quality Gate -> Merge -> CD -> Production.
- Preserved the classroom rhythm and student reasoning across every topic.
- Connected CI/CD to FastAPI, Playwright, AI backend, Docker, and prompt work.
- Added exercises: why local testing is insufficient, design a CI pipeline, explain a quality gate, manual deployment vs CD, and explain workflow as code.
- No `exercises/` directory exists, so Day20 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.27 — Day19 GitHub Project Management Documentation

Date: 2026-07-09

### Added

- Added `docs/github/day19-project-management.md` (new `docs/github/` folder).
- Added Day19 project management material to `cheat_sheets/github.md`.
- Added Day19 project management interview questions to `interview/github.md`.

### Changed

- Updated `CURRICULUM.md` to add Day19 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day19 completed.
- Updated `TASKS.md` with completed Day19 tasks and Day19 review.
- Updated `CHANGELOG.md` with the Day19 repository update.

### Notes

- Day19 teaches GitHub project management as managing work, not clicking UI: why teams manage work not only code, Issue as a work item (collaboration, tracking, prioritization, ownership), Label as structured metadata (retrieval, workflow, automation), Milestone as a product delivery goal, Projects as workflow management, the Issue/Label/Milestone/Project hierarchy, and the complete Idea-to-Release workflow connecting Day15-Day19.
- Preserved the classroom rhythm and student reasoning, including "if work isn't tracked, it doesn't exist" and "ownership is not blame," and related Labels to database indexes, RAG filtering, vector search filtering, and Kubernetes labels.
- Connected project management to FastAPI, Playwright, AI backend, prompt, and Docker work.
- Added exercises: convert feature requests into Issues, assign and justify Labels, group Issues into a Milestone, and build a Project workflow board.
- Deliberately excluded Day20 topics.
- No `exercises/` directory exists, so Day19 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.26 — Day18 Merge Strategy & Code Review Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day18-merge-strategy-and-code-review.md`.
- Added Day18 merge strategy and code review material to `cheat_sheets/github.md`.
- Added Day18 merge strategy and code review interview questions to `interview/github.md`.

### Changed

- Updated `CURRICULUM.md` to add Day18 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day18 completed.
- Updated `TASKS.md` with completed Day18 tasks and Day18 review.
- Updated `CHANGELOG.md` with the Day18 repository update.

### Notes

- Day18 teaches merge strategy and code review as human-facing decisions: Git history is for humans, development history vs product history, merge commit (preserve history), squash merge (product history), rebase merge (linear history), senior review focus (architecture, performance, security, maintainability), "review the code, not the coder," and the three goals (improve the code, the developer, the team).
- Preserved the classroom rhythm and student reasoning across every topic.
- Connected merge strategy and review to FastAPI endpoints, Playwright tests, AI backend prompt and agent changes, and Docker changes.
- Added exercises: compare merge commit vs squash, choose a merge strategy, review a FastAPI endpoint, and rewrite a poor review comment.
- Deliberately excluded Day19 topics.
- No `exercises/` directory exists, so Day18 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.25 — Day17 GitHub Workflow & Collaboration Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day17-github-workflow.md`.
- Added `cheat_sheets/github.md` (new GitHub workflow cheat sheet).
- Added `interview/github.md` (new GitHub workflow interview notes).

### Changed

- Updated `CURRICULUM.md` to add Day17 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day17 completed.
- Updated `TASKS.md` with completed Day17 tasks and Day17 review.
- Updated `CHANGELOG.md` with the Day17 repository update.

### Notes

- Day17 teaches the GitHub collaboration workflow as gates around shared state, not tool clicks: why direct push to main is dangerous, Pull Request as Review + CI + Discussion + Audit Trail, machines validate rules while humans validate intent, Branch Protection, stale reviews, and review discussions as an engineering knowledge base.
- Preserved the classroom rhythm and student reasoning across every topic.
- Included the required workflow mental-model diagram (Developer -> Feature Branch -> Commit -> Push -> Pull Request [CI + Human Review] -> Branch Protection -> Stable main -> Engineering Knowledge Base).
- Connected the workflow to FastAPI endpoints, Playwright tests, AI backend prompt and agent changes, and Docker changes.
- Added pull request lifecycle exercises: open a PR, trigger CI, request changes, approve, simulate a stale review, and merge.
- Deliberately excluded Day18 topics.
- Created dedicated `github.md` cheat sheet and interview files, keeping GitHub collaboration separate from Git internals in `git.md`.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.24 — Day16 Git Branch & Merge Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day16-branch-and-merge.md`.
- Added Day16 Branch & Merge review material to `cheat_sheets/git.md`.
- Added Day16 Branch & Merge interview questions to `interview/git.md`.

### Changed

- Updated `CURRICULUM.md` to add Day16 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day16 completed.
- Updated `TASKS.md` with completed Day16 tasks and Day16 review.
- Updated `CHANGELOG.md` with the Day16 repository update.

### Notes

- Day16 teaches branch and merge as the Git object model in motion, not command memorization: why branches exist, branch as a movable reference, instant branch creation, HEAD and current branch, fast-forward merge as reference movement, three-way merge with a two-parent merge commit, merge conflict as Git refusing to guess intent, and Git history as a Directed Acyclic Graph.
- Preserved the classroom rhythm and student reasoning, including the production/feature/hotfix scenario, the "branch is not a copy" correction, the instant-branch derivation, the fast-forward discovery, and the key sentence "Git does not fail; Git refuses to guess business intent."
- Included the required diagrams (branch as reference, HEAD/current branch before and after commit, fast-forward, two-parent three-way merge, merge conflict, DAG).
- Connected branch and merge to FastAPI feature branches, Playwright test branches, AI backend prompt and agent workflow branches, and Docker changes.
- Deliberately excluded Day17+ topics: GitHub, pull requests, code review, GitHub Flow, rebase, and cherry-pick.
- No `exercises/` directory exists, so Day16 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.23 — Day15 Revision

Date: 2026-07-09

### Changed

- Reframed `docs/git/day15-git-fundamentals.md` to derive the Git object model from the Python object model (Day01-Day02) instead of presenting Git commands.
- Added a new first Main Concept "From Python Object Model to Git Object Model" with a Python-to-Git mapping table and the Git Object diagram (`HEAD -> Branch -> Commit -> Tree -> Blob`).
- Added a reflog derivation chain (Commit -> reference removed -> dangling/unreachable -> HEAD history -> `git reflog`) so the recovery mechanism is derived, not just described.
- Relabeled the classroom "Student Thinking" beats for a clearer Tech Lead Question -> Student Thinking -> Student Answer -> Tech Lead Review rhythm.
- Updated the lesson map and renumbered the concepts to include the object-model derivation.
- Added a `## Mental Model Summary` section to `cheat_sheets/git.md`.
- Added a senior interview question linking Git's object model to Python's object model in `interview/git.md`.
- Updated `PROJECT_STATUS.md` and `TASKS.md` to record the Day15 revision.

### Notes

- Preserved all classroom interaction, student reasoning, and derivations; did not convert the lesson into documentation.
- Did not expand Day16 or later.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.22 — Day15 Git Fundamentals Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day15-git-fundamentals.md` (starts Phase 2 — Engineering Foundations).
- Added `cheat_sheets/git.md` (new Git cheat sheet).
- Added Day15 Git Fundamentals interview questions to `interview/git.md`.

### Changed

- Updated `CURRICULUM.md` to add Phase 2 and mark Day15 as completed.
- Updated `PROJECT_STATUS.md` to start Phase 2 and mark Day15 completed.
- Updated `TASKS.md` with completed Day15 tasks and next Phase 2 preparation.
- Updated `CHANGELOG.md` with the Day15 repository update.

### Notes

- Day15 teaches Git as an engineering system, not command memorization: object model, snapshot vs diff, immutable commits, repository vs working directory, staging area, the three-tree model, HEAD and branch, detached HEAD, reset modes, and reflog.
- Preserved the classroom rhythm and student reasoning, including the IDE-history correction, the snapshot-vs-diff discovery, the immutable-snapshot answer, the staging-area v1/v2 question, the detached HEAD insight, and the reset/reflog corrections.
- Included the required ASCII diagrams (snapshot reuse, working directory to repository flow, HEAD/branch before and after commit, detached HEAD, three-tree model) and the reset soft/mixed/hard table.
- Connected Git to FastAPI rollback and diffing, Playwright locator/test history, and AI backend prompt and configuration versioning.
- Marked Phase 2 as started; did not mark Day16 or later as started.
- No `exercises/` directory exists, so Day15 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.21 — Day14 Review Fix

Date: 2026-07-08

### Added

- Added a concise `## Day14 Interview Review` bullet section to `cheat_sheets/python.md` covering layered architecture, thin router, service layer, browser layer, LLM layer, repository pattern, dependency injection, stateless service, shared mutable state, worker vs async, semaphore, retry, exponential backoff, stable throughput, and horizontal scaling.
- Added four missing Day14 interview questions to `interview/python.md`: why the Browser Layer returns data instead of JSON, what shared mutable state is, async vs worker scaling, and how to design an AI Summary Service.

### Notes

- Did not rewrite the Day14 lesson.
- Did not create duplicate Day14 sections; the new questions extend the existing Day14 interview section and stay grouped by difficulty.
- Verified Day14 lesson section ordering follows `LESSON_TEMPLATE.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.20 — Day14 Mini Project & Backend Architecture Documentation

Date: 2026-07-08

### Added

- Added `docs/python/day14-mini-project.md`.
- Added `cheat_sheets/fastapi.md` (new FastAPI cheat sheet).
- Added Day14 backend architecture review material to `cheat_sheets/python.md`.
- Added Day14 backend architecture interview questions to `interview/python.md`.
- Added Day14 backend architecture interview questions to `interview/fastapi.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day14 as completed and Phase 1 as complete.
- Updated `PROJECT_STATUS.md` to mark Day14 completed and point to Phase 2.
- Updated `TASKS.md` with completed Day14 tasks and Phase 2 preparation tasks.
- Updated `CHANGELOG.md` with the Day14 repository update.

### Notes

- Day14 is an integration lesson, not a Python syntax lesson: it combines Day01–Day13 into a production-shaped, layered AI backend.
- Covered layered architecture (API, Service, Browser, LLM, Repository, Database), each layer's single responsibility and what it must NOT do, thin routers, service orchestration, the browser and LLM as infrastructure behind interfaces, multi-provider architecture, and the repository pattern.
- Covered engineering thinking: separation of concerns, single responsibility, low coupling, high cohesion, dependency injection, stateless services, shared mutable state, interface-first development, and architecture before coding.
- Covered production topics: worker architecture, async vs worker scaling, horizontal scaling, throughput, bottleneck analysis, semaphore, retry, exponential backoff, HTTP 429, and browser/LLM resource management.
- Connected the design to FastAPI request flow with `Depends()`, Playwright browser layer cleanup, and an AI summary service with queue, worker pool, Redis, PostgreSQL, and OpenAI.
- Added a mock interview and 10-level architecture exercises.
- No `exercises/` directory exists, so Day14 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.19 — Day13 Async Programming Documentation

Date: 2026-07-08

### Added

- Added `docs/python/day13-async-programming.md`.
- Added Day13 Async Programming review material to `cheat_sheets/python.md`.
- Added Day13 Async Programming interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day13 as completed and Day14 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day13 as completed and prepare Day14.
- Updated `TASKS.md` with completed Day13 tasks and Day14 preparation tasks.
- Updated `CHANGELOG.md` with the Day13 repository update.

### Notes

- Explained every concept from the Event Loop perspective: what the loop is doing, which Task runs, which is suspended, and why the scheduler switches.
- Covered async motivation (I/O throughput vs CPU), I/O bound vs CPU bound, blocking vs non-blocking (`time.sleep()` vs `asyncio.sleep()`), the Event Loop, coroutine vs coroutine object, Task vs coroutine, `await`, `asyncio.gather()` input-order results, the Task lifecycle, cooperative cancellation and `CancelledError`, exception propagation, and `Semaphore` concurrency control.
- Emphasized stable throughput over maximum concurrency and respecting downstream capacity (OpenAI rate limits, Redis, PostgreSQL pools, GPU, browser memory).
- Connected Day13 concepts to FastAPI async request Tasks and `asyncio.to_thread()`, Playwright async automation with bounded concurrency, and AI backend concurrency with `gather()` and semaphores.
- Documented production risks: blocking the Event Loop, blocking libraries in async code, connection pool exhaustion, too many concurrent OpenAI requests, Redis overload, PostgreSQL connection exhaustion, browser explosion, and memory pressure from excessive Tasks.
- No `exercises/` directory exists, so Day13 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.18 — Day12 Context Managers Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day12-context-managers.md`.
- Added Day12 Context Managers review material to `cheat_sheets/python.md`.
- Added Day12 Context Managers interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day12 as completed and Day13 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day12 as completed and prepare Day13.
- Updated `TASKS.md` with completed Day12 tasks and Day13 preparation tasks.
- Updated `CHANGELOG.md` with the Day12 repository update.

### Notes

- Covered resource lifecycle (Acquire -> Use -> Release), `try / finally`, the `with` statement, `__enter__`, `__exit__`, exception handling in `__exit__`, `@contextmanager`, `yield` vs `return`, and generator pause/resume cleanup.
- Emphasized the principle that business logic should not own resource management.
- Connected Day12 concepts to FastAPI `yield` dependencies and lifespan handlers, Playwright `BrowserContext` cleanup, and AI backend LLM stream, Redis, session, and lock cleanup.
- Documented production risks: database connection leaks, file handle leaks, BrowserContext leaks, Redis connection leaks, LLM stream leaks, and locks not released.
- No `exercises/` directory exists, so Day12 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.17 — Day11 Review Fix

Date: 2026-07-07

### Changed

- Strengthened the Day11 OOP cheat sheet structure in `cheat_sheets/python.md`.
- Added explicit Day11 OOP beginner interview questions for class and instance in `interview/python.md`.
- Added a senior Day11 Dependency Injection interview question in `interview/python.md`.

### Notes

- Did not modify `docs/python/day11-object-oriented-programming.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.16 — Day11 Object-Oriented Programming Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day11-object-oriented-programming.md`.
- Added Day11 Object-Oriented Programming review material to `cheat_sheets/python.md`.
- Added Day11 OOP interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day11 as completed and Day12 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day11 as completed and prepare Day12.
- Updated `TASKS.md` with completed Day11 tasks and Day12 preparation tasks.
- Updated `CHANGELOG.md` with the Day11 repository update.

### Notes

- Covered object, class, instance, state, behavior, `self`, attribute lookup, method lookup, class attributes, instance attributes, inheritance, override, `super()`, MRO, and composition.
- Connected Day11 concepts to FastAPI application/service/dependency objects, Playwright browser/context/page/locator objects, and AI backend service composition.
- No `exercises/` directory exists, so Day11 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.15 — Day10 Type Hints Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day10-type-hints.md`.
- Added Day10 Type Hints review material to `cheat_sheets/python.md`.
- Added Day10 Type Hints interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day10 as completed and Day11 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day10 as completed and prepare Day11.
- Updated `TASKS.md` with completed Day10 tasks and Day11 preparation tasks.
- Updated `CHANGELOG.md` with the Day10 repository update.

### Notes

- Covered Type Hints as interface contracts, runtime behavior, parameter and return types, `list[T]`, `dict[K, V]`, `tuple`, `set[T]`, `User | None`, `Optional`, `Union`, type inference, `TypeVar`, and `Generic`.
- Connected Day10 concepts to FastAPI request models, response models, `Depends()`, Pydantic, OpenAPI, Playwright object types, and AI backend tool/message contracts.
- No `exercises/` directory exists, so Day10 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.14 — Day09 Consistency Fix

Date: 2026-07-07

### Changed

- Fixed `PROJECT_STATUS.md` so the Next section consistently points to Day10.
- Standardized the Day09 import execution flow in `docs/python/day09-modules-packages.md`.
- Standardized the Day09 import execution flow in `cheat_sheets/python.md`.

### Notes

- Did not rewrite Day09.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.13 — Day09 Modules and Packages Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day09-modules-packages.md`.
- Added Day09 module, package, import system, and import side effect review material to `cheat_sheets/python.md`.
- Added Day09 interview questions with overseas AI Backend engineering answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day09 as completed and Day10 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day09 as completed and prepare Day10.
- Updated `TASKS.md` with completed Day09 tasks and Day10 preparation tasks.
- Updated `CHANGELOG.md` with the Day09 repository update.

### Notes

- Covered import execution flow, module objects, module cache with `sys.modules`, module vs package, `__init__.py`, namespace packages, absolute imports, relative imports, namespace pollution, and import side effects.
- Connected Day09 concepts to FastAPI package structure, Playwright worker boundaries, and AI backend package architecture.
- No `exercises/` directory exists, so Day09 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.12 — Day08 Exception Handling Polish

Date: 2026-07-07

### Changed

- Polished the Day08 completion badge in `docs/python/day08-exception-handling.md`.
- Preserved classroom code review examples for `divide(a, b)` and `check_age(age)`.
- Improved Playwright timeout specificity by using `PlaywrightTimeoutError`.
- Added Day08 Tech Lead Advice after Today's Takeaway.
- Added a Day08 system design interview question for AI Backend exception handling.
- Added a cheat sheet note about framework-specific exception classes.

### Notes

- Did not rewrite Day08.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.11 — Day08 Exception Handling Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day08-exception-handling.md`.
- Added Day08 exception handling review material to `cheat_sheets/python.md`.
- Added Day08 interview questions with overseas AI Backend engineering answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day08 as completed and Day09 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day08 as completed and prepare Day09.
- Updated `TASKS.md` with completed Day08 tasks and Day09 preparation tasks.
- Updated `CHANGELOG.md` with the Day08 repository update.

### Notes

- Covered `try / except`, precise exception handling, `ZeroDivisionError`, exception control flow, exception propagation, `raise`, custom exceptions, and exception chaining.
- Added `InvalidPromptError`, `LLMRequestError`, `ToolExecutionError`, and `RateLimitError` error-design examples.
- Connected Day08 concepts to FastAPI `HTTPException`, Playwright timeout recovery, and AI backend failure handling.
- No `exercises/` directory exists, so Day08 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.10 — Day07 Classroom Polish

Date: 2026-07-06

### Changed

- Enhanced `docs/python/day07-iterators-generators.md` with additional classroom reasoning, Tech Lead questions, and production bug examples.
- Enhanced `cheat_sheets/python.md` with a Day07 production risk table.
- Enhanced `interview/python.md` with senior-level Day07 questions about accidental generator consumption and shared state.

### Notes

- Added the principle: Data can be shared, state should not be shared.
- Added production bug examples for `list(generator)`, `sum(generator)`, and LLM stream debugging.
- Strengthened Pipeline vs Batch and AI token streaming explanations.
- Confirmed Day07 remains completed and Day08 remains the current lesson.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.9 — Day07 Iterators and Generators Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day07-iterators-generators.md`.
- Added Day07 iterator, generator, lazy evaluation, and streaming review material to `cheat_sheets/python.md`.
- Added Day07 interview questions with standard answers, follow-up questions, and engineering perspectives to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day07 as completed and Day08 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day07 as completed and prepare Day08.
- Updated `TASKS.md` with completed Day07 tasks and Day08 preparation tasks.
- Updated `CHANGELOG.md` with the Day07 repository update.

### Notes

- Covered Iterable, Iterator, `iter()`, `next()`, `StopIteration`, Generator, `yield`, generator lifecycle, lazy evaluation, generator expression, and `yield from`.
- Covered why `StopIteration` does not return `None`, why iterable and iterator are separated, and why generators are pausable and resumable data-flow models.
- Added streaming connections for FastAPI `StreamingResponse`, Playwright data pipelines, and AI backend token streaming.
- No `exercises/` directory exists, so Day07 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.8 — Day06 Decorators Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day06-decorators.md`.
- Added Day06 decorator review material to `cheat_sheets/python.md`.
- Added Day06 interview questions, Chinese explanations, English answers, and overseas interview answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day06 as completed and Day07 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day06 as completed and prepare Day07.
- Updated `TASKS.md` with completed Day06 tasks and Day07 preparation tasks.
- Updated `CHANGELOG.md` with the Day06 repository update.

### Notes

- Covered decorator motivation, cross-cutting concerns, wrapper functions, universal decorators, and `functools.wraps`.
- Covered metadata preservation for `__name__`, `__doc__`, `__annotations__`, and signature/reflection behavior.
- Added production examples for logging, timing, retry, authentication, cache, token tracking, and AI request tracing.
- Connected Day06 concepts to FastAPI route decorators, Playwright retry decorators, and AI backend observability.
- No `exercises/` directory exists, so Day06 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.7 — Day05 Closures Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day05-closures.md`.
- Added Day05 Closure Engineering Notes to `cheat_sheets/python.md`.
- Added Factory Function, Closure vs Class, and Late Binding review material to `cheat_sheets/python.md`.
- Added Day05 interview questions, Chinese explanations, English answers, overseas backend answers, and follow-up questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day05 as completed and Day06 as the current lesson.
- Adjusted `docs/python/day05-closures.md` so required sections remain in the official template order.
- Updated `PROJECT_STATUS.md` to mark Day05 as completed.
- Updated `TASKS.md` with completed Day05 tasks and Day06 preparation tasks.

### Notes

- Covered Closure as Function Object plus Captured Environment.
- Covered captured environment, state preservation, `nonlocal`, `UnboundLocalError`, factory functions, Closure vs Class, and Late Binding.
- Connected Day05 concepts to FastAPI dependency factories, Playwright configuration factories, and AI prompt builders.
- No `exercises/` directory exists, so Day05 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.6 — Day04 Scope and LEGB Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day04-scope-legb.md`.
- Added Day04 LEGB, scope, closure, and late binding review material to `cheat_sheets/python.md`.
- Added Day04 interview questions and English answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day04 as completed and Day05 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day04 as completed.
- Updated `TASKS.md` with completed Day04 tasks and Day05 preparation tasks.

### Notes

- Covered lexical scope, `global`, `nonlocal`, mutation vs rebinding, closure, and late binding.
- Connected Day04 concepts to FastAPI, Playwright, and AI backend engineering.

---

## v0.1.5 — Day03 Functions and Parameter Passing Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day03-functions-parameter-passing.md`.
- Added Day03 function parameter passing review material to `cheat_sheets/python.md`.
- Added Day03 interview questions and English answers to `interview/python.md`.

### Changed

- Updated `PROJECT_STATUS.md` to mark Day03 as completed.
- Updated `TASKS.md` with completed Day03 tasks and Day04 preparation tasks.

### Notes

- Did not modify `CURRICULUM.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.
- No `exercises/` directory exists, so Day03 exercises are included in the lesson document.

---

## v0.1.4 — Day02 Mutable vs Immutable Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day02-mutable-vs-immutable.md`.
- Added Day02 mutable vs immutable review material to `cheat_sheets/python.md`.
- Added Day02 interview questions to `interview/python.md`.

### Changed

- Updated `PROJECT_STATUS.md` to mark Day02 as completed.
- Updated `TASKS.md` with completed Day02 tasks, review tasks, and Day03 preparation tasks.

### Notes

- Did not modify Day01 technical content.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.3 — Release Candidate Workflow Stabilization

Date: 2026-07-03

### Added

- Added `TRAINING_WORKFLOW.md` as the official training operating manual.
- Added daily learning workflow to `README.md`.
- Added repository lifecycle guidance to `REPOSITORY_GUIDE.md`.
- Added Today's Goal and Definition of Done to `PROJECT_STATUS.md`.

### Changed

- Updated `CURRICULUM.md` into a reusable engineering curriculum format.
- Redesigned `TASKS.md` as the daily execution sprint board.
- Updated repository guidance so future lessons follow one stable workflow.

### Notes

- Day01 technical content was not changed.
- Folder structure was not changed.
- Lesson template was not changed.

---

## v0.1.2 — Repository Cleanup and Structure Alignment

Date: 2026-07-02

### Added

- Added topic-based lesson structure under `docs/`.
- Added project README files for every project directory.
- Added `interview/python.md` as the template for future interview handbooks.
- Added `cheat_sheets/python.md` as the template for future cheat sheets.
- Added `prompts/interview.md`.
- Added `prompts/project.md`.
- Added `REPOSITORY_GUIDE.md`.
- Added `CONTRIBUTING.md`.
- Added assets subdirectories for images, diagrams, architecture, and memory models.

### Changed

- Moved Day 1 final lesson to `docs/python/day01-object-model.md`.
- Updated architecture references to use `docs/<topic>/`.
- Updated Codex prompt to use topic-based lesson paths.
- Updated `PROJECT_STATUS.md` and `TASKS.md` for Day 2 readiness.

### Removed

- Removed duplicated Day 1 course structure outside canonical `docs/` organization.

### Future

- Reserved a future `knowledge/` structure in `TASKS.md` without creating it yet.

---

## v0.1.1 — Project Management Layer

Date: 2026-07-02

### Added

- Added `TASKS.md`.
- Added `ARCHITECTURE.md`.
- Added `CHANGELOG.md`.
- Added `DECISIONS.md`.
- Added `ROADMAP.md`.
- Added `GLOSSARY.md`.

### Next

- Add repository directory skeleton.
- Add first final lesson under `docs/`.

---

## v0.1.0 — Repository Foundation

Date: 2026-07-02

### Added

- Created core repository concept.
- Added `README.md`.
- Added `AGENTS.md`.
- Added `PROJECT_STATUS.md`.
- Added `CURRICULUM.md`.
- Added `CODING_STANDARD.md`.
- Added `LESSON_TEMPLATE.md`.

### Learning Progress

- Completed Day 1 discussion.
- Covered Python Object Model.
- Covered Function Objects.
- Covered Callable Objects.
- Covered References.
- Covered `==` vs `is`.
- Covered Mutable Default Argument bug.
