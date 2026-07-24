# Current Sprint

This file is the daily execution dashboard for the AI Backend Engineer Training Camp.

It should read like a real software team's sprint board.

GitHub is the single source of truth.

---

## Current Phase

Phase 3 — Backend Foundations (In Progress)

---

## Current Lesson

Day40 — Redis Messaging and Queue Semantics

Status:
Planned / Not started

Target lesson:
Not created yet — see CURRICULUM.md and ROADMAP.md.

---

## Today's Tasks

- [ ] Prepare for Day40 — Redis Messaging and Queue Semantics (see the Day40 Preparation block below).

(Day29-Day39 are complete; their work is recorded under the Completed Day** sections and the corresponding
Preparation history blocks.)

---

## Completed Day39 Tasks

- [x] Complete Day39 Redis Cache Design and Consistency classroom learning.
- [x] Generate the Day39 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day38->Day39 mental-model evolution).
- [x] Explain why a cache hit is not truth and a cache miss is not a Job failure, judged against the committed PostgreSQL state.
- [x] Implement cache-aside reads so a cache write failure never invalidates a correct PostgreSQL response.
- [x] Order state changes commit-first, invalidate-after, and explain the pre-commit re-cache race.
- [x] Invalidate every affected view (Job detail and the tenant recent-completed list).
- [x] Decide when a representation change needs a new versioned key vs an additive optional field.
- [x] Apply TTL + jitter for avalanche and explain single-flight (one hot key) vs jitter (synchronized expiry).
- [x] Design hot-key protection with a single-flight leader, bounded followers, backoff+jitter, and SWR for tolerant reads.
- [x] Classify fail-open vs fail-closed and defend the guarded PostgreSQL write for POST /cancel.
- [x] Use short tenant-scoped negative caching against penetration without making it a security decision.
- [x] Measure cache correctness (commit->invalidation delay, cache age, stale-terminal, Redis-vs-PostgreSQL agreement), not just hit ratio.
- [x] Recover an unknown cache-delete outcome with an Outbox intent + idempotent DEL, never redoing a transition or Provider call.
- [x] Choose the correct rollback target (the cache contract) in the v2 incident, never PostgreSQL truth or Provider work.
- [x] Preserve the real student answers, the English interview answers, and the final Chinese synthesis.

---

## Completed Day39 Repository Tasks

- [x] Add `docs/redis/day39-redis-cache-design-and-consistency.md`.
- [x] Add `projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day39 increment (artifact link, components, honest NOT-RUN limits).
- [x] Append the Day39 section to `cheat_sheets/redis.md`.
- [x] Append Day39 questions to `interview/redis.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day39 is now the latest Redis lesson).
- [x] Update the Day38 lesson Next Lesson link to the released Day39 lesson.
- [x] Update `CURRICULUM.md` (Day39 Completed; Day40 remains Planned).
- [x] Update `ROADMAP.md` (Day39 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day39 Interview Tasks

- [x] Add the stale-vs-committed, cache-aside, and invalidation-ordering questions with the student's actual answers.
- [x] Add the affected-view, representation-versioning, TTL/jitter, and stampede/SWR questions.
- [x] Add the fail-open/closed, negative-caching, hot-key/metrics, invalidation-recovery, and v2-incident questions.
- [x] Preserve the three verbatim English answers and add strong model answers.

---

## Completed Day39 Homework

- [x] Complete the stale-vs-committed and invalidation-ordering exercises.
- [x] Complete the cache-aside miss and hot-key stampede/SWR exercises.
- [x] Complete the fail-open/closed table and v2 cache-contract incident exercises.

---

## Completed Day38 Tasks

- [x] Complete Day38 Redis Foundations and Data Structures classroom learning.
- [x] Generate the Day38 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day37->Day38 mental-model evolution).
- [x] State the ownership model (PostgreSQL truth / Object Storage bytes / Redis rebuildable acceleration).
- [x] Fall back to PostgreSQL on a missing progress key; never fail the Job or re-call the Provider.
- [x] Reject a whole Job lifecycle stored in Redis under a TTL.
- [x] Choose String/Hash/List/Set/Sorted Set by access pattern and defend each.
- [x] Explain why a Hash beats a JSON String for concurrent field updates and why HINCRBY is atomic.
- [x] Design the tenant-namespaced, versioned key contract and the incompatible-change versioning rule.
- [x] Distinguish single-command atomicity from a multi-command race and the HSET+EXPIRE crash window.
- [x] Treat maxmemory/eviction as a correctness boundary (only rebuildable keys may be evicted).
- [x] Compare RDB/AOF loss windows and explain neither confers ownership.
- [x] Apply the broker-payload rule (job_id + tenant_id + trace metadata; 202 after the durable Accept).
- [x] Design a bounded Redis-outage fallback that protects PostgreSQL.
- [x] Solve the missing-TTL incident with a config rollback + prefix-scoped cleanup (no FLUSHALL).
- [x] Preserve the real student answers, the English interview answers, and the final Chinese synthesis.

---

## Completed Day38 Repository Tasks

- [x] Add `docs/redis/day38-redis-foundations-and-data-structures.md` (new `docs/redis/` directory).
- [x] Add `projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md` (new `redis/` subdir).
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day38 increment (artifact link, components, honest NOT-RUN limits).
- [x] Add `cheat_sheets/redis.md` (new file) with the Day38 section.
- [x] Append Day38 questions to `interview/redis.md` (existing stub extended; no duplicate file created).
- [x] Update `docs/README.md` (add the `redis/` tree and the Day38 lesson link).
- [x] Update the Day37 lesson Next Lesson link to the released Day38 lesson.
- [x] Update `CURRICULUM.md` (Day38 Completed; Day39 remains Planned).
- [x] Update `ROADMAP.md` (Day38 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day38 Interview Tasks

- [x] Add the ownership/missing-key and Redis-only-lifecycle questions with the student's actual answers.
- [x] Add the Hash-vs-JSON-String, structure-by-access-pattern, and key/versioning questions.
- [x] Add the atomicity, AOF-ownership, outage-fallback, and missing-TTL/FLUSHALL questions.
- [x] Preserve the three verbatim English answers and add model answers/assessments.

---

## Completed Day38 Homework

- [x] Complete the ownership-classification and key-contract/versioning exercises.
- [x] Complete the multi-command race (HINCRBY / HSET+EXPIRE) exercise.
- [x] Complete the bounded-outage-fallback exercise.
- [x] Complete the missing-TTL incident end-to-end exercise.

---

## Completed Day37 Tasks

- [x] Complete Day37 PostgreSQL Production Reliability classroom learning.
- [x] Generate the Day37 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day36->Day37 mental-model evolution).
- [x] Explain why a reachable, low-CPU database is not reliable.
- [x] Size pools by aggregate demand across processes and reserve capacity below the safe budget.
- [x] Place the eight-minute Provider call outside the DB transaction and name the four boundaries.
- [x] Distinguish Provider success, Artifact bytes, and committed PostgreSQL success, and reconcile first.
- [x] Apply the layered timeout model and the lock_timeout < statement_timeout < deadline ordering.
- [x] Separate liveness/readiness/business success and avoid a shared-outage restart storm.
- [x] Explain MVCC dead tuples, stop the long transaction first, and tune autovacuum per-table on evidence.
- [x] Design least-privilege roles and a safe credential-rotation order.
- [x] Explain why replication is not backup and reconstruct base backup + WAL -> PITR.
- [x] State what recoverability evidence requires beyond a successful backup job.
- [x] Make the 420-vs-300 incident decision (contain + roll back pool config; reconcile external effects).
- [x] Preserve the real student answers, student-initiated questions, English answers, two-pass Chinese synthesis, and all corrections.

---

## Completed Day37 Repository Tasks

- [x] Add `docs/postgresql/day37-postgresql-production-reliability.md`.
- [x] Add `projects/ai-backend-data-layer/runbooks/postgresql-production-reliability.md`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day37 increment (runbook link, components, honest NOT-RUN limits).
- [x] Append the Day37 section to `cheat_sheets/postgresql.md`.
- [x] Append Day37 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day37 is now the latest PostgreSQL lesson).
- [x] Update the Day36 lesson Next Lesson link to the released Day37 lesson.
- [x] Update `CURRICULUM.md` (Day37 Completed; Day38 remains Planned).
- [x] Update `ROADMAP.md` (Day37 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day37 Interview Tasks

- [x] Add the beginner connection-pool and aggregate-demand questions with the student's actual answers.
- [x] Add intermediate idle-in-transaction and timeout/readiness questions.
- [x] Add the senior replica-promotion, replication-vs-backup, and 420-vs-300 questions.
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day37 Homework

- [x] Complete the aggregate-pool-demand and reserve-capacity exercises.
- [x] Complete the 8-minute-call placement and Artifact-vs-commit exercises.
- [x] Complete the timeout-selection and readiness/restart-storm exercises.
- [x] Complete the Vacuum-root-cause and least-privilege/rotation exercises.
- [x] Complete the replication-vs-backup, PITR/restore-evidence, and 420-vs-300 exercises.

---

## Completed Day36 Tasks

- [x] Complete Day36 Schema Evolution and Safe Migrations classroom learning.
- [x] Generate the Day36 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day35->Day36 mental-model evolution).
- [x] Define a migration as a versioned state transition across schema, data, and app versions.
- [x] Explain why a direct ADD COLUMN ... NOT NULL is rejected atomically on a populated table.
- [x] Expand with nullable Lease columns and reject a fabricated default.
- [x] Judge defaults as business facts and reject lease_token DEFAULT gen_random_uuid().
- [x] Scope Backfill to running-only and route unknown ownership to reconciliation.
- [x] Explain why old Workers must be drained before recovery and Switch.
- [x] Design an idempotent, restartable, SKIP LOCKED Backfill with a database-backed checkpoint.
- [x] Explain CHECK ... NOT VALID vs VALIDATE CONSTRAINT.
- [x] Explain CREATE INDEX CONCURRENTLY and invalid-index handling.
- [x] Define the Switch precondition and the Contract evidence.
- [x] Decide rollback vs forward fix by durable state and forward-fix the false-takeover case.
- [x] Preserve the real student answers, the student-initiated backfill question, English answers, final Chinese synthesis, and all corrections.

---

## Completed Day36 Repository Tasks

- [x] Add `docs/postgresql/day36-schema-evolution-and-safe-migrations.md`.
- [x] Add `projects/ai-backend-data-layer/sql/008_schema_evolution_and_safe_migrations.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day36 increment, phased plan, compatibility matrix, and honest NOT-RUN limits.
- [x] Append the Day36 section to `cheat_sheets/postgresql.md`.
- [x] Append Day36 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day36 is now the latest PostgreSQL lesson).
- [x] Update the Day35 lesson Next Lesson link to the released Day36 lesson.
- [x] Update `CURRICULUM.md` (Day36 Completed; Day37 remains Planned).
- [x] Update `ROADMAP.md` (Day36 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day36 Interview Tasks

- [x] Add the beginner NOT-NULL-fails and default-as-business-fact questions with the student's actual answers.
- [x] Add intermediate backfill-scope/reconciliation and drain/SKIP-LOCKED questions.
- [x] Add the senior NOT-VALID/VALIDATE, rollback-vs-forward-fix, and switch/contract questions.
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day36 Homework

- [x] Complete the direct-NOT-NULL-failure and default-as-business-fact exercises.
- [x] Complete the backfill-scope/reconciliation and phase-ordering exercises.
- [x] Complete the drain-before-recovery and idempotent-SKIP-LOCKED-backfill exercises.
- [x] Complete the completion-evidence and NOT-VALID/VALIDATE exercises.
- [x] Complete the CONCURRENTLY/invalid-index, forward-fix, and Contract exercises.

---

## Completed Day35 Tasks

- [x] Complete Day35 PostgreSQL Indexes and Query Planning classroom learning.
- [x] Generate the Day35 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day34->Day35 mental-model evolution).
- [x] Derive the claim Partial Composite index from the Day34 predicate and ordering.
- [x] Explain why a job_status-only index is weak and why B-tree order is equality-then-range/order.
- [x] Separate the claim path from all-status/dynamic-status/fixed-status history paths.
- [x] Explain why the UNIQUE (tenant_id, idempotency_key) index must not be duplicated.
- [x] Design the Outbox Partial Index and exclude job_id from the keys.
- [x] Reject a now() Partial predicate and give the stable-predicate + query-time-range design.
- [x] Distinguish EXPLAIN (plan) from EXPLAIN ANALYZE (real execution, locks/DML side effects).
- [x] Judge a Seq Scan as cost-based and treat estimate-vs-actual as a statistics investigation.
- [x] Identify which indexes queued -> running maintains.
- [x] Make the net-benefit keep/rollback decision on the broad-history-index case.
- [x] Preserve the real student answers, English answers, final Chinese synthesis, and all corrections.

---

## Completed Day35 Repository Tasks

- [x] Add `docs/postgresql/day35-postgresql-indexes-and-query-planning.md`.
- [x] Add `projects/ai-backend-data-layer/sql/007_postgresql_indexes_and_query_planning.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day35 increment, index candidates, EXPLAIN evidence plan, and honest NOT-RUN limits.
- [x] Append the Day35 section to `cheat_sheets/postgresql.md`.
- [x] Append Day35 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day35 is now the latest PostgreSQL lesson).
- [x] Update the Day34 lesson Next Lesson link to the released Day35 lesson.
- [x] Update `CURRICULUM.md` (Day35 Completed; Day36 remains Planned).
- [x] Update `ROADMAP.md` (Day35 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day35 Interview Tasks

- [x] Add the beginner claim-index and EXPLAIN questions with the student's actual answers.
- [x] Add intermediate history-path and composite-vs-partial questions.
- [x] Add the senior no-duplicate-unique, now()-rejection, and keep/rollback questions.
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day35 Homework

- [x] Complete the claim-index derivation and job_status-only-weakness exercises.
- [x] Complete the history-path and composite-vs-partial exercises.
- [x] Complete the no-duplicate-unique and Outbox-partial exercises.
- [x] Complete the now()-rejection and EXPLAIN-vs-EXPLAIN-ANALYZE exercises.
- [x] Complete the Seq-Scan-judgement, estimate-vs-actual, maintenance, and keep/rollback exercises.

---

## Completed Day34 Tasks

- [x] Complete Day34 Concurrency Control, MVCC, and Worker Claims classroom learning.
- [x] Generate the Day34 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day33->Day34 mental-model evolution).
- [x] Explain why a candidate SELECT is visibility, not ownership.
- [x] Use FOR UPDATE and FOR UPDATE SKIP LOCKED and build the claim transaction around the Day33 write.
- [x] State what SKIP LOCKED does not guarantee (strict FIFO, complete snapshot, eventual service).
- [x] Explain why a released lock is not liveness evidence and what blind reclaim duplicates.
- [x] Distinguish a transaction-local row lock from a committed lease (owner/token/expiry).
- [x] Treat lease expiry as a takeover condition, with takeover writing a new token and a guarded completion.
- [x] Choose a lease duration from heartbeat + observed pause and justify it against false takeover.
- [x] Keep lease_token separate from a stable Provider idempotency key.
- [x] Read Read Committed vs Repeatable Read/Serializable snapshots and why isolation does not partition work.
- [x] Diagnose a reverse-order deadlock (40P01), prevent it with a consistent lock order, and retry from the app.
- [x] Preserve the real student answers, English answers, final Chinese synthesis, and all corrections.

---

## Completed Day34 Repository Tasks

- [x] Add `docs/postgresql/day34-concurrency-control-mvcc-and-worker-claims.md`.
- [x] Add `projects/ai-backend-data-layer/sql/006_concurrency_control_mvcc_and_worker_claims.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day34 increment, active-vs-conceptual boundary, reproduction, and limitations.
- [x] Append the Day34 section to `cheat_sheets/postgresql.md`.
- [x] Append Day34 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day34 is now the latest PostgreSQL lesson).
- [x] Update the Day33 lesson Next Lesson link to the released Day34 lesson.
- [x] Update `CURRICULUM.md` (Day34 Completed; Day35 remains Planned).
- [x] Update `ROADMAP.md` (Day34 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day34 Interview Tasks

- [x] Add the beginner visibility-vs-claim and SKIP LOCKED questions with the student's actual answers.
- [x] Add intermediate released-lock and Read-Committed-phantom questions.
- [x] Add the senior stale-completion, lease-token-vs-Provider-key, and deadlock questions.
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day34 Homework

- [x] Complete the visibility-vs-claim and FOR UPDATE / SKIP LOCKED exercises.
- [x] Complete the released-lock and lease/heartbeat-policy exercises.
- [x] Complete the stale-owner completion and token-vs-Provider-identity exercises.
- [x] Complete the pessimistic-vs-optimistic and Read-Committed-phantom exercises.
- [x] Complete the deadlock / lock-order and integrated takeover/rollback exercises.

---

## Completed Day33 Tasks

- [x] Complete Day33 PostgreSQL Transactions and Atomic State Changes classroom learning.
- [x] Generate the Day33 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day32->Day33 mental-model evolution).
- [x] Use BEGIN/COMMIT/ROLLBACK as one business-change boundary.
- [x] Make Job + Outbox publication intent atomic and return 202 only after COMMIT.
- [x] Write the guarded queued->running transition + Attempt + job_started Event as one transaction.
- [x] Explain why zero affected rows is a normal result requiring an application gate, not a transaction failure.
- [x] Keep the AI Provider and Object Storage phase outside any open transaction.
- [x] State what PostgreSQL can and cannot prove after Provider success.
- [x] Explain the Transactional Outbox lifecycle and published_at semantics.
- [x] Correct the exactly-once misconception with at-most-once vs at-least-once + idempotent consumer.
- [x] Explain the integrated rollback (external side effects survive) and the lost-COMMIT-response case.
- [x] Explain why the transaction pack is a write-path contract, not a schema guarantee.
- [x] Preserve the real student answers, the delivery-label mistake, and all corrections.

---

## Completed Day33 Repository Tasks

- [x] Add `docs/postgresql/day33-postgresql-transactions-and-atomic-state-changes.md`.
- [x] Add `projects/ai-backend-data-layer/sql/005_postgresql_transactions_and_atomic_state_changes.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day33 increment, transaction boundaries, driver contract, reproduction, and limitations.
- [x] Append the Day33 section to `cheat_sheets/postgresql.md`.
- [x] Append Day33 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day33 is now the latest PostgreSQL lesson).
- [x] Update the Day32 lesson Next Lesson link to the released Day33 lesson.
- [x] Update `CURRICULUM.md` (Day33 Completed; Day34 remains Planned).
- [x] Update `ROADMAP.md` (Day33 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day33 Interview Tasks

- [x] Add the beginner transaction-definition and constraint-rollback questions with the student's actual answers.
- [x] Add intermediate 202-after-COMMIT and no-transaction-across-Provider questions.
- [x] Add the senior zero-row-gate, Relay-crash, and completion-rollback questions.
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day33 Homework

- [x] Complete the Job-without-Outbox and constraint-rollback diagnosis exercises.
- [x] Complete the 202 placement and zero-row-gate exercises.
- [x] Complete the split-the-eight-minute-call and proof-boundary exercises.
- [x] Complete the published_at, delivery-label, and legacy-writer exercises.

---

## Completed Day32 Tasks

- [x] Complete Day32 SQL Joins, Aggregation, and Operational Queries classroom learning.
- [x] Generate the Day32 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day31->Day32 mental-model evolution).
- [x] Define the result grain of a query before writing it.
- [x] Choose INNER vs LEFT JOIN from what a missing row means, and keep zero-Attempt Jobs visible.
- [x] Correct the row-multiplication misconception (3 Attempts x 4 Events = 12 rows; 0 Attempts + 4 Events = 4 rows).
- [x] Distinguish COUNT(*) from COUNT(child_pk) after a LEFT JOIN.
- [x] Learn FILTER conditional aggregation and why moving the condition into WHERE collapses LEFT into INNER.
- [x] Place aggregate thresholds in HAVING and tenant/status predicates in WHERE.
- [x] Report oldest queued age with MIN and distinguish an empty queue (NULL) from missing data.
- [x] Treat SUM/AVG over NULL cost as recorded facts, and reject COALESCE(SUM(cost_micros), 0).
- [x] Apply CTE pre-aggregation to two independent one-to-many children.
- [x] Select the current Attempt deterministically with DISTINCT ON and classify stuck candidates.
- [x] Use half-open [start, end) throughput windows instead of BETWEEN.
- [x] Scope an affected set with recorded release provenance rather than a time window.
- [x] Explain why rollback does not repair committed rows or undo published outbox events.
- [x] Preserve the real student answers and all material misconceptions/corrections.

---

## Completed Day32 Repository Tasks

- [x] Add `docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md`.
- [x] Add `projects/ai-backend-data-layer/sql/004_sql_joins_aggregation_and_operational_queries.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day32 increment, query contracts, validation reproduction, and limitations.
- [x] Append the Day32 section to `cheat_sheets/postgresql.md`.
- [x] Append Day32 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day32 is now the latest PostgreSQL lesson).
- [x] Update the Day31 lesson Next Lesson link to the released Day32 lesson.
- [x] Update `CURRICULUM.md` (Day32 Completed; Day33 remains Planned).
- [x] Update `ROADMAP.md` (Day32 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day32 Interview Tasks

- [x] Add the beginner INNER vs LEFT JOIN and COUNT(*) questions with the student's actual attempts.
- [x] Add intermediate row-multiplication, FILTER-vs-WHERE, and WHERE-vs-HAVING questions.
- [x] Add the senior incomplete-cost, stage-aware stuck, and post-rollback questions.
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day32 Homework

- [x] Complete the zero-Attempt preservation and row-count prediction exercises.
- [x] Complete the FILTER conditional-aggregation exercise.
- [x] Complete the honest cost-reporting exercise with completeness columns.
- [x] Complete the CTE pre-aggregation exercise.
- [x] Complete the stage-aware stuck-candidate exercise with DISTINCT ON.
- [x] Complete the read-only incident-evidence exercise.

---

## Completed Day31 Tasks

- [x] Complete Day31 Relational Modeling and Data Integrity classroom learning.
- [x] Generate the Day31 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day30->Day31 mental-model evolution).
- [x] Decide when a repeated fact becomes its own entity (job_attempts) instead of columns or a JSONB array.
- [x] Distinguish primary key, foreign key, and business key, and design scoped uniqueness.
- [x] Derive UNIQUE (tenant_id, idempotency_key) from the fact that a retry produces a new job_id.
- [x] Choose ON DELETE RESTRICT for audit/cost-bearing children and explain when CASCADE/SET NULL apply.
- [x] Place one-to-many foreign keys correctly and model optional one-to-one with FK + UNIQUE.
- [x] Translate the status allowlist into a CHECK and identify what a row CHECK cannot assert.
- [x] Normalize Result Artifacts to attempt_id and keep job_id derivable.
- [x] Separate jobs.job_status, job_events history, and outbox_events publication intent.
- [x] Model many-to-many Job <-> Document with a junction table carrying relationship attributes.
- [x] Enforce same-tenant relationships with composite foreign keys and distinguish integrity from authorization.
- [x] Work through deploying a UNIQUE constraint onto committed duplicate Jobs.
- [x] Write and correct the minimum app.job_attempts DDL.
- [x] Preserve the real student answers and all material misconceptions/corrections.

---

## Completed Day31 Repository Tasks

- [x] Add `docs/postgresql/day31-relational-modeling-and-data-integrity.md`.
- [x] Add `projects/ai-backend-data-layer/sql/003_relational_modeling_and_data_integrity.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day31 increment, apply order, key rules, validation commands, and a separate Day31 validation matrix.
- [x] Append the Day31 section to `cheat_sheets/postgresql.md`.
- [x] Append Day31 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day31 is now the latest PostgreSQL lesson).
- [x] Update the Day30 lesson Next Lesson link to the released Day31 lesson.
- [x] Update `CURRICULUM.md` (Day31 Completed; Day32 remains Planned).
- [x] Update `ROADMAP.md` (Day31 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day31 Interview Tasks

- [x] Add the beginner primary-key vs foreign-key question with the student's actual attempt and corrections.
- [x] Add intermediate business-key and referential-action questions.
- [x] Add the senior tenant-isolation question (composite FKs vs authorization).
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day31 Homework

- [x] Complete entity-vs-columns and duplicate-child-insert exercises.
- [x] Complete scoped-uniqueness and tenant-idempotency exercises.
- [x] Complete referential-action and FK-placement exercises.
- [x] Complete CHECK allowlist and succeeded-invariant exercises.
- [x] Complete Result Artifact normalization exercises.
- [x] Complete state/history/outbox separation and many-to-many exercises.
- [x] Complete cross-tenant prevention and integrity-vs-authorization exercises.
- [x] Complete the failed UNIQUE deployment incident exercise.
- [x] Complete the job_attempts DDL authoring exercise.

---

### Day40 Preparation — Redis Messaging and Queue Semantics

- [ ] Read the Day40 input when provided.
- [ ] Review `projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md` and hold the boundary that Redis transport/cache does not own durable Job truth.
- [ ] Preview Lists / Pub-Sub / Streams as different messaging models, and durable backlog vs no-replay.
- [ ] Preview Streams consumer groups, pending entries, ack, claim/redelivery, and trimming.
- [ ] Preview ordering scope and consumer concurrency, and at-most-once vs at-least-once (idempotent consumers still required).
- [ ] Keep Redis transactions/Lua and full rate limiting (Day41) and SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day39 Preparation — Redis Cache Design and Consistency (completed)

- [x] Read the Day39 input.
- [x] Reviewed `projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md` and held the boundary that PostgreSQL stays the durable Job source of truth while Redis is rebuildable acceleration.
- [x] Previewed cache-aside read/write, cache key/version and serialization, and TTL selection with jitter.
- [x] Previewed invalidation on durable-state change, stampede/single-flight/stale-while-revalidate, and negative-caching/penetration/hot-key risk.
- [x] Previewed stale cache vs PostgreSQL source of truth and hit-ratio/latency/eviction/memory/correctness metrics.
- [x] Previewed fail-open vs fail-closed by sensitivity.
- [x] Kept Redis transactions/Lua, messaging/Streams, and full rate limiting (Day40-41) and SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day38 Preparation — Redis Foundations and Data Structures (completed)

- [x] Read the Day38 input.
- [x] Reviewed `projects/ai-backend-data-layer/runbooks/postgresql-production-reliability.md` and held the boundary that PostgreSQL stays the durable, recoverable Job source of truth.
- [x] Previewed the Redis server/database/key/value model and single-command atomicity.
- [x] Previewed strings/hashes/lists/sets/sorted sets by access pattern, key naming/versioning/tenant namespace, and TTL/expiration.
- [x] Previewed memory limits and eviction as correctness concerns, and the RDB/AOF overview (Redis is not the Job source of truth).
- [x] Held appropriate Redis uses (ephemeral progress, cache, broker transport, rate-limit counters) vs inappropriate ones (authoritative Job lifecycle, large documents).
- [x] Kept SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day37 Preparation — PostgreSQL Production Reliability (completed)

- [x] Read the Day37 input.
- [x] Reviewed `projects/ai-backend-data-layer/sql/008_schema_evolution_and_safe_migrations.sql` and the DDL-lock/batch/index-build boundaries that became live operational concerns.
- [x] Previewed long transactions and transaction/WAL age, autovacuum/Vacuum, connection pooling and limits, and backup/recovery.
- [x] Previewed slow-query monitoring, lock/connection pressure, and capacity planning as the operational lens on Day34-Day36 designs.
- [x] Kept the safe-migration DESIGN (Day36) vs live operational guardrails (Day37) distinction.
- [x] Kept SQLAlchemy/Alembic (Phase 4) and cross-system fencing tokens (Day41) out of scope.

---

### Day36 Preparation — Schema Evolution and Safe Migrations (completed)

- [x] Read the Day36 input.
- [x] Reviewed `projects/ai-backend-data-layer/sql/007_postgresql_indexes_and_query_planning.sql` and the conceptual lease columns / stale-lease index needing safe deployment.
- [x] Previewed `CREATE INDEX CONCURRENTLY` and DDL-lock-aware procedures.
- [x] Previewed the expand/backfill/validate/switch/contract migration for adding the lease columns (claim_owner, lease_token, lease_expires_at).
- [x] Kept the design (Day35) vs safe rollout (Day36) distinction; Day36 executed no DDL.
- [x] Kept production operations/monitoring (Day37) and SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day35 Preparation — PostgreSQL Indexes and Query Planning (completed)

- [x] Read the Day35 input.
- [x] Reviewed `projects/ai-backend-data-layer/sql/006_concurrency_control_mvcc_and_worker_claims.sql` and the exact claim predicates and ordering (tenant_id, job_status = 'queued', cancel_requested = false, created_at, job_id).
- [x] Previewed the access paths a busy claim hammers: the queued scan and unpublished-Outbox scan (stale-lease deferred to Day36 columns).
- [x] Previewed `EXPLAIN`/`EXPLAIN ANALYZE`, index types, and why an index is chosen by measurement, not guess.
- [x] Kept Day34's correctness settled before Day35's speed; an index cannot fix a wrong claim.
- [x] Kept lease-column migration and safe index deployment (Day36), full operations (Day37), and SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day34 Preparation — Concurrency Control, MVCC, and Worker Claims (completed)

- [x] Read the Day34 input.
- [x] Reviewed `projects/ai-backend-data-layer/sql/005_postgresql_transactions_and_atomic_state_changes.sql` and where the Relay checkpoint defers concurrent claiming.
- [x] Previewed concurrent sessions, MVCC snapshot visibility, and isolation-level anomalies.
- [x] Previewed `SELECT ... FOR UPDATE`, `SKIP LOCKED` worker claiming, and fairness/starvation.
- [x] Previewed DB lock vs application lease, deadlocks, lock ordering, timeout, and retry.
- [x] Kept a lock from being treated as a repair for a wrongly defined Day33 boundary.
- [x] Kept indexes and execution plans (Day35), safe migration (Day36), and SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day33 Preparation — PostgreSQL Transactions and Atomic State Changes (completed)

- [x] Read the Day33 input.
- [x] Reviewed `projects/ai-backend-data-layer/sql/004_sql_joins_aggregation_and_operational_queries.sql` and which evidence each query assumes was written at all.
- [x] Previewed BEGIN/COMMIT/ROLLBACK, ACID from production failures, and the atomic Job + Outbox insert.
- [x] Previewed why a database transaction cannot cover an external provider, Object Storage, or Redis side effect.
- [x] Previewed transaction size and duration, and why one must never stay open during an eight-minute model call.
- [x] Kept concurrency/locks (Day34), indexes and execution plans (Day35), safe migration (Day36), and SQLAlchemy/Alembic (Phase 4) out of scope.

---

### Day32 Preparation — SQL Joins, Aggregation, and Operational Queries (completed)

- [x] Read the Day32 input.
- [x] Reviewed the Day31 relational model and the foreign keys/cardinalities Day32 queries.
- [x] Previewed INNER vs LEFT JOIN and missing-row meaning, join cardinality and row multiplication, COUNT/SUM/MIN/MAX/AVG/GROUP BY/HAVING, conditional aggregation, and CTEs.
- [x] Previewed the operational queries the 842-row incident needed: Job detail, attempts/events, stuck Jobs by stage, oldest queued age, throughput, retry/terminal counts, provenance.
- [x] Kept transactions (Day33), concurrency/locks (Day34), indexes (Day35), safe migration (Day36), and SQLAlchemy/Alembic (Phase 4) out of scope.

---

## Completed Day30 Tasks

- [x] Complete Day30 SQL Data Manipulation and Query Fundamentals classroom learning.
- [x] Generate the Day30 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day29->Day30 mental-model evolution).
- [x] Write the deterministic oldest-queued SELECT with explicit columns and a unique tie-breaker.
- [x] Explain three-valued logic, IS NULL, and why `<> 'timeout'` drops no-error rows.
- [x] Insert with database defaults and return generated facts with RETURNING.
- [x] Explain parameter binding, the injection boundary, and what it does not solve.
- [x] Write guarded queued->running and running->succeeded transitions with current-state predicates.
- [x] Interpret zero returned rows without claiming the Job does not exist.
- [x] Correct AND/OR precedence in the guarded cleanup DELETE.
- [x] Diagnose the attempt_count lost update and compare database-side increment vs optimistic guard.
- [x] Work through the 842-row accidental UPDATE incident and the contain->reconcile->repair order.
- [x] Preserve the real student answers and all material misconceptions/corrections.

---

## Completed Day30 Repository Tasks

- [x] Add `docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md`.
- [x] Add `projects/ai-backend-data-layer/sql/002_job_crud_and_guarded_transitions.sql`.
- [x] Update `projects/ai-backend-data-layer/README.md` with the Day30 increment and validation matrix.
- [x] Append the Day30 section to `cheat_sheets/postgresql.md`.
- [x] Append Day30 questions to `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (Day30 is now the latest PostgreSQL lesson).
- [x] Update the Day29 lesson Next Lesson link to the released Day30 lesson.
- [x] Update `CURRICULUM.md` (Day30 Completed; Day31 remains Planned).
- [x] Update `ROADMAP.md` (Day30 Completed only).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day30 Interview Tasks

- [x] Add the beginner WHERE/affected-rows question with the student's actual attempt and English corrections.
- [x] Add intermediate parameterized-SQL and NULL three-valued-logic questions.
- [x] Add the senior guarded running->succeeded question (zero-row interpretation + concurrency limits).
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day30 Homework

- [x] Complete deterministic SELECT and unfinished-Jobs exercises.
- [x] Complete the `<> 'timeout'` NULL-logic exercise.
- [x] Complete INSERT-with-defaults + RETURNING exercise.
- [x] Complete parameter-boundary exercise.
- [x] Complete guarded transition and zero-row interpretation exercises.
- [x] Complete guarded DELETE precedence exercise.
- [x] Complete attempt_count lost-update exercise.
- [x] Complete the 842-row incident exercise.

---

### Day31 Preparation — Relational Modeling and Data Integrity (completed)

- [x] Read the Day31 input.
- [x] Reviewed the Day30 SQL pack and the guard predicates that Day31 moved into database constraints.
- [x] Previewed entities/relationships, primary vs business keys, `NOT NULL`/`UNIQUE`/`CHECK`/foreign keys, referential actions, and normalization.
- [x] Previewed the Documents / Job Attempts / Job Events / Outbox Events / Result Artifact model the 842-row incident showed was missing.
- [x] Kept transactions (Day33), concurrency/locks (Day34), indexes (Day35), safe migration (Day36), and SQLAlchemy/Alembic (Phase 4) out of scope.

---

## Completed Day29 Tasks

- [x] Complete Day29 PostgreSQL Foundations and Durable Relational State classroom learning.
- [x] Generate the Day29 lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day28->Day29 mental-model evolution).
- [x] Derive the minimum durable facts (job_id, job_status, created_at) and the write-before-202 ordering.
- [x] Explain the PostgreSQL hierarchy and that a psql session connects to a database, not a schema.
- [x] Distinguish PostgreSQL Schema (namespace) from table schema (definition), and public from app.
- [x] Choose Job types/defaults (uuid/text/integer/boolean/timestamptz/bounded jsonb) and defend UUID vs integer.
- [x] Compare typed columns with a JSONB-only Job document; separate type from relationship cardinality.
- [x] Interpret NULL per lifecycle and show that NOT NULL accepts empty string and arbitrary text.
- [x] Prove database-generated defaults with DEFAULT VALUES + RETURNING.
- [x] Distinguish primary key (row identity) from idempotency key (request identity).
- [x] Verify timestamptz as one absolute instant across UTC and Asia/Shanghai.
- [x] Classify conceptual / syntax / runtime / integration / production validation evidence.
- [x] Run the queud guarded data-repair drill and the restart-persistence check.
- [x] Preserve the real student answers and all material misconceptions/corrections.

---

## Completed Day29 Repository Tasks

- [x] Add `docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md`.
- [x] Add `projects/ai-backend-data-layer/README.md` and `sql/001_create_jobs.sql`.
- [x] Add `cheat_sheets/postgresql.md`.
- [x] Append Day29 questions to the existing `interview/postgresql.md` (no duplicate file created).
- [x] Update `docs/README.md` (add the postgresql/ topic directory).
- [x] Update the Day28 lesson metadata Next Lesson link to the released Day29 lesson.
- [x] Update `CURRICULUM.md` (Day29 Completed + released lesson/artifact).
- [x] Update `ROADMAP.md` (Day29 Completed; Day30-Day42 remain Planned).
- [x] Update `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `CHANGELOG.md`.

---

## Completed Day29 Interview Tasks

- [x] Add the beginner persist-before-202 question with the student's actual attempt and correction.
- [x] Add intermediate primary-key-vs-idempotency-key and NOT NULL questions.
- [x] Add the senior lost-202 retry question (attempts "client produce idempotency key" and "我忘了"; answer taught directly).
- [x] Add Chinese explanations and weak-vs-strong answers.

---

## Completed Day29 Homework

- [x] Complete minimum-durable-facts and types/defaults exercises.
- [x] Complete app.jobs not-found diagnosis and public-vs-app exercises.
- [x] Complete typed-columns-vs-JSONB and nullable-lifecycle exercises.
- [x] Complete row-identity-vs-request-identity exercise.
- [x] Complete DEFAULT VALUES + RETURNING and timestamptz comparison exercises.
- [x] Complete the queud guarded repair and restart persistence exercises.

---

### Day30 Preparation — SQL Data Manipulation and Query Fundamentals (completed)

- [x] Read the Day30 input.
- [x] Reviewed the Day29 `app.jobs` schema and the project README limitations.
- [x] Previewed SELECT/FROM/WHERE/ORDER BY/LIMIT, INSERT/UPDATE/DELETE/RETURNING, NULL three-valued logic, parameterized SQL, deterministic ordering, and guarded status transitions.
- [x] Kept CHECK/UNIQUE/foreign keys and relationships as Day31 scope, transactions as Day33, concurrency/locks as Day34, and SQLAlchemy/Alembic as Phase 4.

---

## Completed Day28 Tasks

- [x] Complete Day28 AI Backend Production Architecture classroom learning.
- [x] Generate Day28 handbook lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day27->Day28 mental-model evolution).
- [x] Separate the FastAPI request lifecycle from the long-running Celery job lifecycle (202 + job_id).
- [x] Assign job state/bytes to PostgreSQL (truth), Redis (deliver/cache), Object Storage (bytes), memory (transient).
- [x] Derive the Transactional Outbox and at-least-once + idempotent processing.
- [x] Design durable checkpoints, atomic lease, idempotency key (unique constraint/upsert), ACK after durable write.
- [x] Design presigned direct multipart upload with an Upload Session and server-side verification.
- [x] Design a bounded, classified retry policy with backoff, jitter, and a circuit breaker.
- [x] Choose monitoring signals (depth/oldest-age/throughput) and stable observability correlation (job_id).
- [x] Order the failure-containment/rollback/data-repair runbook (compute rollback != data repair).
- [x] Preserve the real student answers and all material misconceptions/corrections.
- [x] Add the conceptual Production AI Backend Architecture Blueprint artifact.

---

## Completed Day28 Repository Tasks

- [x] Add `docs/devops/day28-ai-backend-production-architecture.md`.
- [x] Add `examples/ai-backend-architecture/README.md` (blueprint).
- [x] Update `examples/README.md` and `docs/README.md`.
- [x] Update `cheat_sheets/devops.md` (replace the Day28 placeholder).
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md` (Day28 completed; Phase 2 closed; next Phase 3).
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day28 Completed).
- [x] Update `ROADMAP.md` (Day28 Completed; no invented Day29/Day30).
- [x] Update `README.md` and `AGENTS.md` progress markers (Phase 3 next, no invented lesson).

---

## Completed Day28 Interview Tasks

- [x] Add beginner request-vs-worker question (with the student's actual weak answer + corrections).
- [x] Add intermediate state-ownership and DB->queue-consistency questions.
- [x] Add senior at-least-once/idempotency question (student said "我忘了"; senior answer taught directly).
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day28 Homework

- [x] Complete request-vs-worker and state-ownership exercises.
- [x] Complete DB-first-vs-queue-first + Outbox and checkpoint/lease/idempotency exercises.
- [x] Complete storage-choice and presigned-upload/verification exercises.
- [x] Complete Upload-Session-vs-Job and retry-policy exercises.
- [x] Complete queue-signals and correlation-identity exercises.
- [x] Complete failure/rollback/data-repair runbook exercise.

---

### Day29 Preparation — PostgreSQL Foundations and Durable Relational State (completed)

- [x] Read the Day29 input.
- [x] Re-read the Day28 lesson and the `examples/ai-backend-architecture/` blueprint (durable Job ownership).
- [x] Inspected the Day29 scope: durable relational state, core PostgreSQL types, primary key/identity, a minimal `jobs` table for `202 + job_id`.
- [x] Used a disposable local PostgreSQL 14.18 environment during the lesson and kept validation levels honest.
- [x] Previewed PostgreSQL, SQL, Redis, and Database Design as the Phase 3 scope; SQLAlchemy/Alembic remain Phase 4.
- [x] Day29 delivered. The data-layer artifact was designed and runtime-validated during the live lesson,
      then materialized in the repository during the post-class Repository Update. `knowledge/` still not created.

---

### Phase 3 Roadmap (Day29-Day42) — Backend Foundations

- [x] Day29 — PostgreSQL Foundations and Durable Relational State (Completed).
- [x] Day30 — SQL Data Manipulation and Query Fundamentals (Completed).
- [x] Day31 — Relational Modeling and Data Integrity (Completed).
- [x] Day32 — SQL Joins, Aggregation, and Operational Queries (Completed).
- [x] Day33 — PostgreSQL Transactions and Atomic State Changes (Completed).
- [x] Day34 — Concurrency Control, MVCC, and Worker Claims (Completed).
- [x] Day35 — PostgreSQL Indexes and Query Planning (Completed).
- [x] Day36 — Schema Evolution and Safe Migrations (Completed).
- [x] Day37 — PostgreSQL Production Reliability (Completed).
- [ ] Day38 — Redis Foundations and Data Structures (Planned).
- [ ] Day39 — Redis Cache Design and Consistency (Planned).
- [ ] Day40 — Redis Messaging and Queue Semantics (Planned).
- [ ] Day41 — Redis Coordination and Production Safety (Planned).
- [ ] Day42 — Backend Data Design Capstone (Planned).

---

## Completed Day27 Tasks

- [x] Complete Day27 Kubernetes Workloads classroom learning.
- [x] Generate Day27 handbook lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day26->Day27 mental-model evolution).
- [x] Explain Ingress as L7 Host/Path/TLS routing and the Ingress resource vs Ingress Controller split.
- [x] Explain that HPA updates desired replicas on a scale target (not creating Pods directly).
- [x] Explain CPU-vs-queue-backlog scaling and upstream capacity/429/cost limits.
- [x] Explain Rolling Update maxSurge/maxUnavailable and distinguish strategy, rollback, and Blue-Green.
- [x] Explain why deleting v2 Pods is not a rollback.
- [x] Explain StatefulSet stable identity/PVC/headless Service/ordered lifecycle and why it is not database HA.
- [x] Explain Helm templates vs Values vs Release and the lint/template/API/runtime validation ladder.
- [x] Explain why real Secrets must never be committed to Helm Values.
- [x] Preserve the real student answers and all material misconceptions/corrections.
- [x] Add the rag-platform Helm chart and static-only validation helper.

---

## Completed Day27 Repository Tasks

- [x] Add `docs/devops/day27-kubernetes-workloads.md`.
- [x] Add the `examples/kubernetes/rag-platform/` Helm chart (Chart.yaml, values*.yaml, templates, validate_chart.py).
- [x] Update `examples/kubernetes/README.md` (Day27 chart usage, validation layers, prerequisites, security).
- [x] Update `examples/README.md`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day27 Completed).
- [x] Update `ROADMAP.md` (Day27 Completed, Day28 left Planned).
- [x] Update `README.md` and `AGENTS.md` progress markers.

---

## Completed Day27 Interview Tasks

- [x] Add beginner Service-vs-Ingress question (with the student's actual weak answer + technical/English corrections).
- [x] Add intermediate HPA-metric and Rolling-Update-vs-rollback-vs-Blue-Green questions.
- [x] Add senior safe-release/business-failure/rollback question.
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day27 Homework

- [x] Complete Service-vs-Ingress and /chat-vs-/admin routing exercises.
- [x] Complete initial-CPU-metric and low-CPU-backlog HPA exercises.
- [x] Complete surge-rollout and stalled-Readiness exercises.
- [x] Complete Blue-Green-vs-Rolling-Update exercise.
- [x] Complete Deployment+volume-vs-StatefulSet and three-PVCs exercises.
- [x] Complete Helm templates-vs-Values, secrets-not-in-Values, and validation-ladder exercises.
- [x] Complete Helm failed-revision recovery exercise.

---

### Day28 Preparation — AI Backend Production Architecture

- [ ] Read Day28 input when provided.
- [ ] Preview assembling FastAPI, Celery, Redis, PostgreSQL, object storage, queues, monitoring, and observability.
- [ ] Connect Day27 Ingress/HPA/Rolling Update/StatefulSet/Helm to the Day28 production architecture.
- [ ] Keep Day28 topics labeled as future connections until Day28 is the current lesson.

---

## Completed Day26 Tasks

- [x] Complete Day26 Kubernetes Foundations classroom learning.
- [x] Generate Day26 handbook lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + Day25->Day26 mental-model evolution).
- [x] Explain desired state vs a one-time command and the reconciliation control loop.
- [x] Explain a Pod as one or more tightly coupled containers (Pod != container) and the co-location boundary.
- [x] Explain a Deployment as a Pod template + replica count that recreates replicas but does not schedule.
- [x] Explain a Service as stable label-based discovery for changing Pods.
- [x] Explain ConfigMap (non-sensitive config, same digest) and why storing != delivering != behavior change.
- [x] Explain Secret (Base64 != encryption; not an automatic vault; least privilege needs RBAC/isolation/rotation).
- [x] Explain why a ConfigMap/Secret change does not mutate an already-running process environment.
- [x] Explain the health-200-but-401 partial outage and the safe rollback order.
- [x] Keep Deployment selector, Pod template labels, and Service selector consistent.
- [x] Preserve the real student answers and all material misconceptions/corrections.
- [x] Add the Kubernetes baseline manifest and validation README artifacts.

---

## Completed Day26 Repository Tasks

- [x] Add `docs/devops/day26-kubernetes-foundations.md`.
- [x] Add `examples/kubernetes/ai-backend-baseline.yaml` and `examples/kubernetes/README.md`.
- [x] Update `examples/README.md`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day26 Completed).
- [x] Update `ROADMAP.md` (Day26 Completed, Day27 left Planned).

---

## Completed Day26 Interview Tasks

- [x] Add beginner Pod-vs-container question (with the student's actual weak answer + technical/English corrections).
- [x] Add intermediate Deployment+Service and image/ConfigMap/Secret questions.
- [x] Add senior Secret-rotation rollback question (health 200 != business success).
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day26 Homework

- [x] Complete one-time-startup vs desired-state exercise.
- [x] Complete Pod boundary (FastAPI + sidecar) exercise.
- [x] Complete three Pods vs one Deployment exercise.
- [x] Complete new-IP failure diagnosis exercise.
- [x] Complete Service with label selection exercise.
- [x] Complete ConfigMap vs new image exercise.
- [x] Complete Secret classification (Base64) exercise.
- [x] Complete health-200-but-401 partial outage diagnosis exercise.
- [x] Complete Secret-rotation rollback ordering exercise.

---

## Completed Day26 Review Fixes

- [x] Fix `TASKS.md` Current Phase (Phase 2) and the Phase 2 Roadmap Day26 Planned-vs-Completed contradiction.
- [x] Update `README.md` entry info (Phase 2, last completed Day26, next Day27).
- [x] Update `AGENTS.md` Current Progress (Phase 2 / Day26 completed / Day27 next); keep rules and teaching style unchanged.
- [x] Correct the Deployment/scheduler responsibility in the Day26 lesson (controller creates; kube-scheduler places).
- [x] Replace invalid image strings with valid non-pullable OCI placeholders and sync the README/lesson.
- [x] Add `examples/kubernetes/validate_manifest.py` and make the static validation reproducible with a dependency note.
- [x] Record the Day26 review fixes in `CHANGELOG.md` (v0.1.45).

---

### Day27 Preparation — Kubernetes Workloads (completed)

- [x] Read Day27 input.
- [x] Previewed Ingress (public entry), Autoscaling, Rolling Update, StatefulSet, and Helm as the Day27 scope.
- [x] Connected Day26 Pod/Deployment/Service/ConfigMap/Secret to Day27 workload patterns.
- [x] Day27 delivered; topics are now the completed current lesson (see Completed Day27 Tasks above).

---

## Completed Day25 Tasks

- [x] Complete Day25 Deployment Foundations classroom learning.
- [x] Generate Day25 handbook lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + mental-model evolution).
- [x] Explain the stable public entry (DNS -> Nginx :443 -> backend) and internal backend port.
- [x] Explain the Nginx reverse proxy (listen/server_name/proxy_pass) and trusted proxy headers.
- [x] Explain TLS (confidentiality + integrity + server authentication) and termination.
- [x] Explain HTTP->HTTPS 308 and why redirect cannot protect an already-sent credential.
- [x] Explain the certificate lifecycle and Nginx master/worker (reload vs restart).
- [x] Explain build-once and promoting the exact immutable digest.
- [x] Explain API blue-green with verify, switch, observe, drain, and rollback.
- [x] Explain PostgreSQL Expand-Migrate-Contract and compatible worker rollout.
- [x] Explain serialized deployment and least-privilege short-lived identity.
- [x] Explain AI streaming (buffering vs caching, timeouts) and DNS TTL propagation.
- [x] Preserve the real student answers and all material misconceptions/corrections.
- [x] Add the Nginx example and deployment runbook artifacts.

---

## Completed Day25 Repository Tasks

- [x] Add `docs/devops/day25-deployment-foundations.md`.
- [x] Add `examples/deployment/nginx/nginx.conf.example` and `examples/deployment/README.md`.
- [x] Update `examples/README.md`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day25 Completed).
- [x] Update `ROADMAP.md` (Day25 Completed).
- [x] Left `prompts/teaching-session-prompt.md` unchanged (already present in the repository).

---

## Completed Day25 Interview Tasks

- [x] Add beginner reverse-proxy question (with the student's actual weak answer + correction).
- [x] Add intermediate blue-green and promote-vs-rebuild questions.
- [x] Add senior API/worker/PostgreSQL and DNS-TTL questions.
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day25 Homework

- [x] Complete correct-the-reverse-proxy exercise.
- [x] Complete HTTP->HTTPS + token question exercise.
- [x] Complete trusted proxy headers exercise.
- [x] Complete promote-a-digest exercise.
- [x] Complete blue-green + drain exercise.
- [x] Complete Expand-Migrate-Contract exercise.
- [x] Complete streaming timeouts exercise.
- [x] Complete DNS migration exercise.

---

## Completed Day24 Tasks

- [x] Complete Day24 Docker Compose classroom learning.
- [x] Generate Day24 handbook lesson using LESSON_TEMPLATE_v2 (v3.2 continuity + mental-model evolution).
- [x] Explain why individually runnable containers do not make a reproducible system.
- [x] Explain started != ready: depends_on, healthcheck, and application retry.
- [x] Distinguish Project, Service, Image, and Container; rebuild vs recreate.
- [x] Explain the declarative model and Compose YAML (no obsolete `version:`).
- [x] Explain host ports, service DNS, and publishing only the API port.
- [x] Explain network segmentation (queue/database) and least access.
- [x] Explain volumes, `down` vs `down --volumes`, and persistence != backup.
- [x] Separate environment configuration, secrets, and governed business data.
- [x] Explain the local development workflow command mappings.
- [x] Explain base + development override and the Compose production boundary.
- [x] Preserve the real student answers and all material misconceptions/corrections.
- [x] Add the multi-service Compose example artifact.

---

## Completed Day24 Repository Tasks

- [x] Add `docs/devops/day24-docker-compose.md`.
- [x] Add `examples/docker/compose/compose.yaml`, `compose.dev.yaml`, `.env.example`, and `README.md`.
- [x] Update `examples/README.md` and `examples/docker/fastapi/README.md` (Day24 link).
- [x] Add `.secrets/` to `.gitignore`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day24 Completed).
- [x] Update `ROADMAP.md` (Day24 Completed).

---

## Completed Day24 Interview Tasks

- [x] Add beginner Compose-vs-manual question (with the student's actual weak answer + correction).
- [x] Add intermediate depends_on/healthcheck/retry and rebuild-vs-recreate questions.
- [x] Add senior Compose-vs-Kubernetes and secrets/business-data questions.
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day24 Homework

- [x] Complete why-a-reproducible-system exercise.
- [x] Complete started-vs-ready diagnosis exercise.
- [x] Complete project/service/image/container counting exercise.
- [x] Complete rebuild-vs-recreate exercise.
- [x] Complete Compose model authoring exercise.
- [x] Complete healthcheck + service_healthy exercise.
- [x] Complete config/secret/business-data classification exercise.
- [x] Complete Compose-vs-cluster decision exercise.
- [x] Complete integrated Compose stack build exercise.

---

## Completed Day23 Tasks

- [x] Complete Day23 Docker Fundamentals classroom learning.
- [x] Generate Day23 handbook lesson using LESSON_TEMPLATE_v2.
- [x] Explain why Docker exists (freeze the runtime; continue Day22 build-once).
- [x] Explain a container as an isolated process (namespaces + cgroups), not a VM.
- [x] Distinguish image (immutable template) from container (runtime instance).
- [x] Explain image layers, the writable layer, and build-cache ordering.
- [x] Explain the Dockerfile (FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT) as IaC.
- [x] Distinguish `docker build` from `docker run`.
- [x] Explain volumes and separating compute lifecycle from data lifecycle.
- [x] Explain networks, service DNS names, and why localhost is the current container.
- [x] Explain immutable replacement instead of mutating a running container.
- [x] Preserve the actual student answers and all 12 misconceptions/corrections.
- [x] Add the FastAPI Docker example artifact (Dockerfile, .dockerignore, README).

---

## Completed Day23 Repository Tasks

- [x] Add `docs/devops/day23-docker-fundamentals.md`.
- [x] Add `examples/docker/fastapi/Dockerfile`, `.dockerignore`, and `README.md`.
- [x] Update `examples/README.md`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day23 Completed).
- [x] Update `ROADMAP.md` (Day23 Completed).

---

## Completed Day23 Interview Tasks

- [x] Add beginner container and image-vs-container questions.
- [x] Add intermediate build-vs-run and layer/cache questions.
- [x] Add senior immutable-replacement and network/state questions.
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day23 Homework

- [x] Complete container vs VM exercise.
- [x] Complete image vs container exercise.
- [x] Complete layer/cache exercise.
- [x] Complete Dockerfile exercise.
- [x] Complete build vs run exercise.
- [x] Complete volume exercise.
- [x] Complete RAG architecture design exercise.
- [x] Complete image optimization exercise.
- [x] Complete minimal FastAPI Dockerfile authoring exercise.

---

## Completed Day22 Tasks

- [x] Complete Day22 GitHub Actions Advanced classroom learning.
- [x] Generate Day22 handbook lesson using LESSON_TEMPLATE_v2.
- [x] Explain matrix as one job template expanded by variables (not a resource optimization).
- [x] Explain `fail-fast` decision by the independent value of remaining combinations.
- [x] Distinguish cache (re-creatable acceleration) from artifact (formal output).
- [x] Compare composite action (steps) with reusable workflow (jobs).
- [x] Separate `needs`, `if`, and `continue-on-error` as distinct mechanisms.
- [x] Explain the deployment pipeline: build once, deploy many, immutable digest.
- [x] Explain production Environment protection and serialized concurrency.
- [x] Preserve the 10 classroom misconceptions and corrections.
- [x] Add Engineering Trade-offs, Mental Model Summary, and AI backend connections.
- [x] Add the comprehensive advanced workflow example.

---

## Completed Day22 Repository Tasks

- [x] Add `docs/devops/day22-github-actions-advanced.md`.
- [x] Add `examples/github-actions/github-actions-advanced.example.yml`.
- [x] Update `examples/README.md`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day22 Completed).
- [x] Update `ROADMAP.md` (Day22 Completed).

---

## Completed Day22 Review Fixes

- [x] Add a `verify-image` job that pulls and runs the exact immutable digest and smoke-tests it before deploy.
- [x] Make `deploy` depend on `build` and `verify-image` and reuse the same digest (no rebuild, no `:latest`).
- [x] Upload test reports with `if: always()` and `if-no-files-found: warn`.
- [x] Add `examples/github-actions/composite-python-quality/action.yml` (composite action).
- [x] Add `examples/github-actions/reusable-fastapi-ci.example.yml` (reusable workflow).
- [x] Sync the Day22 lesson, cheat sheet, interview notes, and examples index.
- [x] Correct the reusable-workflow invocation path (copy to `.github/workflows/`, job-level `uses`, commit SHA).
- [x] Add a container cleanup trap to the verify-image smoke test.

---

## Completed Day22 Interview Tasks

- [x] Add beginner matrix question.
- [x] Add intermediate cache-vs-artifact, composite-vs-reusable, and conditions questions.
- [x] Add senior deployment reliability and fail-fast/concurrency questions.
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day22 Homework

- [x] Complete matrix expansion exercise.
- [x] Complete fail-fast decision exercise.
- [x] Complete cache-or-artifact classification exercise.
- [x] Complete composite-vs-reusable exercise.
- [x] Complete needs/if/continue-on-error classification exercise.
- [x] Complete deployment reliability review exercise.
- [x] Complete comprehensive advanced workflow design exercise.

---

## Completed Day21 Tasks

- [x] Complete Day21 GitHub Actions Fundamentals classroom learning.
- [x] Generate Day21 handbook lesson using LESSON_TEMPLATE_v2.
- [x] Explain workflow as code and Convention over Configuration.
- [x] Add the execution model: Event -> Trigger -> Workflow -> Runner -> Job -> Step -> Result.
- [x] Explain workflow vs runner (description vs execution).
- [x] Explain the trigger (`on`) and event-driven cost control.
- [x] Compare GitHub-hosted and self-hosted runners (control, not speed).
- [x] Explain job as one fresh runner and job design principles.
- [x] Explain step, `run`, `uses`, and `with`.
- [x] Explain checkout and workspace initialization.
- [x] Explain the quality gate and FastAPI CI flow.
- [x] Add Common Misconceptions (on=OS, run=trigger, uses=shell, one-job, ruff blocks build).
- [x] Add Engineering Trade-offs and Mental Model Summary sections.
- [x] Add FastAPI, Docker, and GitHub Actions framework connections.
- [x] Add AI backend connections (GPU self-hosted runners, scheduled evaluation, prompt regression).
- [x] Add English interview section with weak vs strong answers.

---

## Completed Day21 Repository Tasks

- [x] Add `docs/devops/day21-github-actions-fundamentals.md`.
- [x] Add `examples/github-actions/fastapi-ci.example.yml` (example-only workflow).
- [x] Add `examples/README.md`.
- [x] Update `cheat_sheets/devops.md`.
- [x] Update `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md` (Day21 Completed).
- [x] Update `ROADMAP.md` (Day21 Completed).

---

## Completed Day21 Interview Tasks

- [x] Add beginner workflow and on-vs-runs-on questions.
- [x] Add intermediate runner and run/uses/with questions.
- [x] Add senior multi-job design and quality-gate questions.
- [x] Add Chinese explanations, English answers, and weak-vs-strong answers.

---

## Completed Day21 Homework

- [x] Complete repository-defined workflow reasoning exercise.
- [x] Complete workflow vs runner exercise.
- [x] Complete hosted vs self-hosted runner design exercise.
- [x] Complete multi-job AI backend workflow design exercise.
- [x] Complete basic FastAPI CI workflow YAML exercise.

---

## Completed Day20 Tasks

- [x] Complete Day20 CI/CD Foundations classroom learning.
- [x] Generate Day20 handbook lesson.
- [x] Explain why "I tested locally" is insufficient.
- [x] Explain CI as a trusted quality process.
- [x] Explain pipeline: standard workflow, stage dependency, fail fast, fast feedback.
- [x] Explain quality gate protecting main, production, team, and users.
- [x] Explain CD: repeatability, consistency, reliability, scalability.
- [x] Explain Workflow as Code and Everything as Code.
- [x] Build the full delivery lifecycle connecting Day15-Day20.
- [x] Add FastAPI, Playwright, AI backend, Docker, and prompt connections.
- [x] Add exercises and interview review.
- [x] Keep later topics out of scope.

---

## Completed Day20 Repository Tasks

- [x] Add `docs/devops/day20-ci-cd-foundations.md`.
- [x] Add `cheat_sheets/devops.md`.
- [x] Add `interview/devops.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day20 Interview Tasks

- [x] Add beginner CI and pipeline questions.
- [x] Add intermediate quality-gate and CI-vs-CD questions.
- [x] Add senior workflow-as-code, everything-as-code, and lifecycle questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day20 Homework

- [x] Complete why-local-testing-is-insufficient exercise.
- [x] Complete design-a-CI-pipeline exercise.
- [x] Complete explain-a-quality-gate exercise.
- [x] Complete manual-deploy-vs-CD exercise.
- [x] Complete explain-workflow-as-code exercise.

---

## Completed Day19 Tasks

- [x] Complete Day19 GitHub Project Management classroom learning.
- [x] Generate Day19 handbook lesson.
- [x] Explain why teams manage work, not only code.
- [x] Explain Issue as a work item (collaboration, tracking, prioritization, ownership).
- [x] Add "if work isn't tracked, it doesn't exist" and ownership != blame.
- [x] Explain Label as structured metadata (retrieval, workflow, automation).
- [x] Relate Labels to database indexes, RAG filtering, vector search, and Kubernetes labels.
- [x] Explain Milestone as a product delivery goal.
- [x] Explain Projects as workflow management (where work is, not just what).
- [x] Add the engineering hierarchy: Issue, Label, Milestone, Project.
- [x] Build the complete Idea-to-Release workflow connecting Day15-Day19.
- [x] Add FastAPI, Playwright, AI backend, prompt, and Docker connections.
- [x] Add exercises and interview review.
- [x] Keep Day20 topics out of scope.

---

## Completed Day19 Repository Tasks

- [x] Add `docs/github/day19-project-management.md`.
- [x] Update `cheat_sheets/github.md`.
- [x] Update `interview/github.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day19 Interview Tasks

- [x] Add beginner Issue and Label questions.
- [x] Add intermediate Issue-vs-Milestone and Projects questions.
- [x] Add senior Issue-vs-Project, ownership-vs-blame, and full-workflow questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day19 Homework

- [x] Complete convert-requests-into-Issues exercise.
- [x] Complete assign-and-justify-Labels exercise.
- [x] Complete group-Issues-into-a-Milestone exercise.
- [x] Complete build-a-Project-board exercise.

---

## Completed Day18 Tasks

- [x] Complete Day18 Merge Strategy & Code Review classroom learning.
- [x] Generate Day18 handbook lesson.
- [x] Explain that Git history is designed for humans.
- [x] Explain development history vs product history.
- [x] Explain merge commit (preserve full history).
- [x] Explain squash merge (one product commit).
- [x] Explain rebase merge (linear history, rewrites identity).
- [x] Explain senior review focus: architecture, performance, security, maintainability.
- [x] Explain review the code, not the coder.
- [x] Explain the three review goals: improve code, developer, and team.
- [x] Add FastAPI, Playwright, AI backend, prompt, and Docker connections.
- [x] Add merge and review exercises and interview review.
- [x] Keep Day19 topics out of scope.

---

## Completed Day18 Repository Tasks

- [x] Add `docs/git/day18-merge-strategy-and-code-review.md`.
- [x] Update `cheat_sheets/github.md`.
- [x] Update `interview/github.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day18 Interview Tasks

- [x] Add beginner history and development-vs-product questions.
- [x] Add intermediate merge-strategy questions.
- [x] Add senior rebase, senior-review-focus, and review-the-code questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day18 Homework

- [x] Complete merge commit vs squash comparison exercise.
- [x] Complete merge strategy selection exercise.
- [x] Complete FastAPI endpoint review exercise.
- [x] Complete rewrite-a-poor-review-comment exercise.

---

## Completed Day17 Tasks

- [x] Complete Day17 GitHub Workflow classroom learning.
- [x] Generate Day17 handbook lesson.
- [x] Explain why direct push to main is dangerous.
- [x] Define Pull Request as Review + CI + Discussion + Audit Trail.
- [x] Explain machines validate rules, humans validate intent.
- [x] Explain Branch Protection and why it protects main.
- [x] Explain stale review after main changes.
- [x] Explain review discussion as engineering knowledge.
- [x] Add the workflow mental-model diagram.
- [x] Add FastAPI, Playwright, AI backend, prompt, and Docker connections.
- [x] Add pull request lifecycle exercises and interview review.
- [x] Keep Day18 topics out of scope.

---

## Completed Day17 Repository Tasks

- [x] Add `docs/git/day17-github-workflow.md`.
- [x] Add `cheat_sheets/github.md`.
- [x] Add `interview/github.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day17 Interview Tasks

- [x] Add beginner direct-push and pull-request questions.
- [x] Add intermediate CI-vs-review and branch-protection questions.
- [x] Add senior stale-review, review-discussion, and full-workflow questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day17 Homework

- [x] Complete open a pull request exercise.
- [x] Complete trigger CI exercise.
- [x] Complete request changes exercise.
- [x] Complete approve exercise.
- [x] Complete simulate stale review exercise.
- [x] Complete merge exercise.

---

## Completed Day16 Tasks

- [x] Complete Day16 Git Branch & Merge classroom learning.
- [x] Generate Day16 handbook lesson.
- [x] Derive why branches exist from the production/feature/hotfix scenario.
- [x] Add branch as a movable reference (not a copy) with the reference diagram.
- [x] Add why branch creation is instant.
- [x] Add HEAD and current branch with before/after commit diagrams.
- [x] Add fast-forward merge as reference movement.
- [x] Add three-way merge with a two-parent merge commit diagram.
- [x] Add merge conflict: Git refuses to guess business intent.
- [x] Add Git history as a Directed Acyclic Graph.
- [x] Add FastAPI, Playwright, AI backend, agent, and Docker connections.
- [x] Add classroom exercises and interview review.
- [x] Keep Day17 topics (GitHub, PR, rebase, cherry-pick) out of scope.

---

## Completed Day16 Repository Tasks

- [x] Add `docs/git/day16-branch-and-merge.md`.
- [x] Update `cheat_sheets/git.md`.
- [x] Update `interview/git.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day16 Interview Tasks

- [x] Add beginner branch-weight question.
- [x] Add intermediate fast-forward and three-way merge questions.
- [x] Add senior conflict, auto-choice, and DAG questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day16 Homework

- [x] Complete two-branches-one-commit exercise.
- [x] Complete fast-forward merge exercise.
- [x] Complete three-way merge exercise.
- [x] Complete merge conflict create-and-resolve exercise.

---

## Completed Day15 Tasks

- [x] Complete Day15 Git Fundamentals classroom learning.
- [x] Generate Day15 handbook lesson.
- [x] Add Phase 2 context: Git as project history management.
- [x] Add snapshot vs diff with reused references.
- [x] Add commit as an immutable snapshot object.
- [x] Add repository vs working directory vs commit.
- [x] Add staging area / index as the next commit blueprint.
- [x] Add the three-tree model and commands as tree movement.
- [x] Add HEAD and branch as references with before/after diagrams.
- [x] Add detached HEAD reasoning and interview answer.
- [x] Add `git reset` soft/mixed/hard table and use cases.
- [x] Add `git reflog` recovery workflow.
- [x] Add FastAPI, Playwright, and AI backend connections.
- [x] Add classroom exercises and interview review.

---

## Completed Day15 Repository Tasks

- [x] Add `docs/git/day15-git-fundamentals.md`.
- [x] Add `cheat_sheets/git.md`.
- [x] Update `interview/git.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day15 Interview Tasks

- [x] Add beginner Git questions.
- [x] Add intermediate three-tree and detached HEAD questions.
- [x] Add senior immutability, reset, reflog, and rollback questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day15 Revision Tasks

- [x] Add "From Python Object Model to Git Object Model" concept with the Git Object diagram (HEAD -> Branch -> Commit -> Tree -> Blob).
- [x] Add the Python-to-Git mapping table.
- [x] Add the reflog derivation chain (Commit -> Reference -> Dangling -> HEAD History -> reflog).
- [x] Relabel the classroom Student Thinking beats.
- [x] Add `## Mental Model Summary` to `cheat_sheets/git.md`.
- [x] Add the Git-vs-Python object model interview question to `interview/git.md`.

---

## Completed Day15 Homework

- [x] Complete Python reference review exercise.
- [x] Complete Git snapshot checkout experiment.
- [x] Complete staging area experiment.
- [x] Complete reset mode experiment.
- [x] Complete reflog recovery experiment.

---

## Completed Day14 Tasks

- [x] Complete Day14 classroom learning.
- [x] Generate Day14 handbook lesson.
- [x] Add layered architecture: API, Service, Browser, LLM, Repository, Database.
- [x] Add each layer's single responsibility and what it must NOT do.
- [x] Add thin router and `main.py` responsibility.
- [x] Add service layer orchestration, dependency injection, and stateless design.
- [x] Add browser layer as infrastructure returning data.
- [x] Add LLM layer interface and multi-provider architecture.
- [x] Add repository pattern and database abstraction.
- [x] Add engineering thinking: SoC, SRP, low coupling, high cohesion, interface-first.
- [x] Add production topics: workers, async vs worker, throughput, bottleneck, retry, backoff.
- [x] Add FastAPI request flow connections.
- [x] Add Playwright browser layer connections.
- [x] Add AI backend connections: summary service, queue, worker pool, Redis, PostgreSQL, OpenAI.
- [x] Add mock interview sections.
- [x] Add 10-level architecture exercises.
- [x] Add interview questions and review checklist.

---

## Completed Day14 Repository Tasks

- [x] Add `docs/python/day14-mini-project.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Add `cheat_sheets/fastapi.md`.
- [x] Update `interview/python.md`.
- [x] Update `interview/fastapi.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day14 Interview Tasks

- [x] Add beginner architecture questions.
- [x] Add intermediate router, repository, and interface questions.
- [x] Add senior scaling, responsiveness, and trade-off questions.
- [x] Add FastAPI architecture interview questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day14 Homework

- [x] Complete API layer refactor exercise.
- [x] Complete service layer design exercise.
- [x] Complete browser layer boundary exercise.
- [x] Complete dependency injection wiring exercise.
- [x] Complete repository pattern exercise.
- [x] Complete task status design exercise.
- [x] Complete retry strategy exercise.
- [x] Complete worker architecture exercise.
- [x] Complete system design exercise.
- [x] Complete architecture mock interview exercise.

---

## Completed Day13 Tasks

- [x] Complete Day13 classroom learning.
- [x] Generate Day13 handbook lesson.
- [x] Add async motivation: I/O throughput, not CPU speed.
- [x] Add I/O bound vs CPU bound discussion.
- [x] Add blocking vs non-blocking with `time.sleep()` vs `asyncio.sleep()`.
- [x] Add Event Loop single-thread cooperative scheduling with ASCII diagram.
- [x] Add coroutine, coroutine object, and execution plan discussion.
- [x] Add coroutine vs Task and `create_task`.
- [x] Add `await` suspend/resume and Event Loop release.
- [x] Add `asyncio.gather()` concurrency and input-order results.
- [x] Add Task lifecycle: Pending -> Running -> Suspend -> Resume -> Done -> Cancelled.
- [x] Add cooperative cancellation and `CancelledError`.
- [x] Add exception propagation and "Task exception was never retrieved".
- [x] Add `Semaphore` and downstream capacity with ASCII diagram.
- [x] Add engineering thinking: stable throughput vs maximum concurrency.
- [x] Add production risks: blocking loop, pool exhaustion, 429s, browser explosion.
- [x] Add FastAPI, Playwright, and AI backend connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day13 Repository Tasks

- [x] Update `docs/python/day13-async-programming.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day13 Interview Tasks

- [x] Add beginner async questions.
- [x] Add intermediate Event Loop, Task, gather, and cancellation questions.
- [x] Add senior throughput, scheduling, semaphore, and concurrency-control questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day13 Homework

- [x] Complete blocking vs non-blocking exercise.
- [x] Complete coroutine object exercise.
- [x] Complete Task concurrency exercise.
- [x] Complete `await` suspension exercise.
- [x] Complete `gather()` input-order exercise.
- [x] Complete Task cancellation exercise.
- [x] Complete exception propagation exercise.
- [x] Complete Semaphore concurrency exercise.
- [x] Complete FastAPI async lifecycle exercise.

---

## Completed Day12 Tasks

- [x] Complete Day12 classroom learning.
- [x] Generate Day12 handbook lesson.
- [x] Add Context Managers as deterministic resource cleanup.
- [x] Add resource lifecycle: Acquire -> Use -> Release.
- [x] Add `try / finally` cleanup guarantee.
- [x] Add `with` statement and its equivalence to `try / finally`.
- [x] Add `__enter__` and `__exit__` protocol.
- [x] Add `__exit__` exception arguments and return value rule.
- [x] Add `@contextmanager` and `yield` vs `return`.
- [x] Add generator pause/resume cleanup model.
- [x] Add "business logic should not own resource management" principle.
- [x] Add production risks and resource leak table.
- [x] Add FastAPI `yield` dependency and lifespan connections.
- [x] Add Playwright `BrowserContext` cleanup connections.
- [x] Add AI backend LLM stream, Redis, session, and lock cleanup connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day12 Repository Tasks

- [x] Update `docs/python/day12-context-managers.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day12 Interview Tasks

- [x] Add beginner context manager questions.
- [x] Add intermediate resource lifecycle and `yield` vs `return` questions.
- [x] Add senior production cleanup questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day12 Homework

- [x] Complete `with` file rewrite exercise.
- [x] Complete `try / finally` cleanup exercise.
- [x] Complete `__enter__` implementation exercise.
- [x] Complete `__exit__` implementation exercise.
- [x] Complete exception cleanup output prediction exercise.
- [x] Complete `@contextmanager` yield exercise.
- [x] Complete FastAPI `yield` dependency exercise.

---

## Completed Day11 Tasks

- [x] Complete Day11 classroom learning.
- [x] Generate Day11 handbook lesson.
- [x] Add OOP as responsibility design.
- [x] Add unified object model review.
- [x] Add object, class, instance, state, and behavior.
- [x] Add `self` and `u1.say_hi()` to `User.say_hi(u1)` reasoning.
- [x] Add class object vs instance object discussion.
- [x] Add attribute lookup and method lookup.
- [x] Add class attribute vs instance attribute.
- [x] Add shadowing with `u1.company = "Google"`.
- [x] Add inheritance, override, and method lookup discussion.
- [x] Add `Browser -> Chromium -> launch()` classroom case.
- [x] Add `super().__init__()` call stack reasoning.
- [x] Add MRO introduction.
- [x] Add composition, Is-A vs Has-A, and dependency injection.
- [x] Add `ChatService` composition example.
- [x] Add FastAPI, Playwright, and AI backend connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day11 Repository Tasks

- [x] Update `docs/python/day11-object-oriented-programming.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day11 Interview Tasks

- [x] Add beginner OOP questions.
- [x] Add intermediate OOP questions.
- [x] Add senior OOP design questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day11 Homework

- [x] Complete object model exercise.
- [x] Complete class vs instance exercise.
- [x] Complete state vs behavior exercise.
- [x] Complete `self` exercise.
- [x] Complete class attribute exercise.
- [x] Complete instance attribute and shadowing exercise.
- [x] Complete inheritance exercise.
- [x] Complete method override exercise.
- [x] Complete `super().__init__()` exercise.
- [x] Complete composition exercise.
- [x] Complete FastAPI service layer design exercise.
- [x] Complete Playwright object ownership exercise.
- [x] Complete AI backend `ChatService` composition exercise.

---

## Completed Day10 Tasks

- [x] Complete Day10 classroom learning.
- [x] Generate Day10 handbook lesson.
- [x] Add Type Hints as interface contracts.
- [x] Add runtime behavior discussion.
- [x] Add parameter and return type hints.
- [x] Add `list[T]`, `dict[K, V]`, `tuple`, and `set[T]`.
- [x] Add `User | None`, `Optional`, and `Union`.
- [x] Add type inference discussion.
- [x] Add empty collection typing discussion.
- [x] Add `TypeVar` and `Generic`.
- [x] Add `identity(T) -> T` reasoning.
- [x] Add FastAPI request model, response model, `Depends()`, Pydantic, and OpenAPI connections.
- [x] Add Playwright `Browser`, `BrowserContext`, `Page`, `Locator`, and storage state connections.
- [x] Add AI backend `ChatMessage`, `AgentTask`, `AgentResult`, `Response[T]`, and tool calling connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day10 Repository Tasks

- [x] Update `docs/python/day10-type-hints.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day10 Interview Tasks

- [x] Add beginner Type Hint questions.
- [x] Add intermediate Type Hint questions.
- [x] Add senior Type Hint questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add production cases and follow-up questions.

---

## Completed Day10 Homework

- [x] Complete basic Type Hint exercises.
- [x] Complete return type exercises.
- [x] Complete `list[T]` exercise.
- [x] Complete `dict[K, V]` exercise.
- [x] Complete `User | None` exercise.
- [x] Complete `Union` exercise.
- [x] Complete `TypeVar` identity exercise.
- [x] Complete `Generic` response wrapper exercise.
- [x] Complete FastAPI request and response model exercise.
- [x] Complete Playwright object type exercise.
- [x] Complete AI backend message and response type exercise.

---

## Completed Day09 Tasks

- [x] Complete Day09 classroom learning.
- [x] Generate Day09 handbook lesson.
- [x] Add module mental model.
- [x] Add import execution flow.
- [x] Add `sys.modules` module cache discussion.
- [x] Add module vs package reasoning.
- [x] Add `__init__.py` and namespace package discussion.
- [x] Add namespace and import style analysis.
- [x] Add absolute vs relative import discussion.
- [x] Add import side effects and production risks.
- [x] Add FastAPI package structure connections.
- [x] Add Playwright module boundary connections.
- [x] Add AI backend package architecture connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day09 Repository Tasks

- [x] Update `docs/python/day09-modules-packages.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.

---

## Completed Day09 Interview Tasks

- [x] Add beginner module and package questions.
- [x] Add intermediate import execution questions.
- [x] Add senior import mechanism questions.
- [x] Add English standard answers.
- [x] Add overseas AI Backend engineering perspectives.

---

## Completed Day09 Homework

- [x] Complete Module vs Package classification exercise.
- [x] Complete import output prediction exercise.
- [x] Complete `sys.modules` reasoning exercise.
- [x] Complete `__init__.py` execution order exercise.
- [x] Complete namespace pollution review exercise.
- [x] Complete absolute vs relative import exercise.
- [x] Complete import side effect review exercise.
- [x] Complete FastAPI package design exercise.
- [x] Complete Playwright module boundary exercise.
- [x] Complete AI backend package architecture exercise.

---

## Completed Day08 Tasks

- [x] Complete Day08 classroom learning.
- [x] Generate Day08 handbook lesson.
- [x] Add `try / except` basics.
- [x] Add precise `ZeroDivisionError` handling.
- [x] Add exception control flow discussion.
- [x] Add exception propagation call stack reasoning.
- [x] Add `raise` for business rules.
- [x] Add return `None` vs raise discussion.
- [x] Add custom exception examples.
- [x] Add `InvalidPromptError`.
- [x] Add exception chaining with `raise ... from ...`.
- [x] Add traceback and root cause discussion.
- [x] Add FastAPI `HTTPException` connections.
- [x] Add Playwright automation failure handling.
- [x] Add AI backend exception design.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day08 Repository Tasks

- [x] Update `docs/python/day08-exception-handling.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.
- [x] Commit changes.
- [x] Push to GitHub.

---

## Completed Day08 Interview Tasks

- [x] Add beginner exception questions.
- [x] Add intermediate exception questions.
- [x] Add senior exception questions.
- [x] Add English standard answers.
- [x] Add overseas AI Backend engineering perspectives.

---

## Completed Day08 Homework

- [x] Complete `try / except` output prediction.
- [x] Complete `ZeroDivisionError` precise catch exercise.
- [x] Complete exception propagation call stack exercise.
- [x] Complete `raise` exercise.
- [x] Complete `check_age(age)` exercise.
- [x] Complete `InvalidPromptError` custom exception exercise.
- [x] Complete `raise ... from ...` exception chain exercise.
- [x] Complete FastAPI `HTTPException` scenario.
- [x] Complete Playwright timeout screenshot and cleanup scenario.
- [x] Complete AI backend prompt validator and tool error scenario.

---

## Completed Day07 Tasks

- [x] Complete Day07 classroom learning.
- [x] Generate Day07 handbook lesson.
- [x] Add Iterable and Iterator explanations.
- [x] Add `iter()` and `next()` protocol discussion.
- [x] Add `StopIteration` reasoning.
- [x] Add Generator and `yield` mental model.
- [x] Add `yield` vs `return`.
- [x] Add Generator Lifecycle.
- [x] Add Lazy Evaluation.
- [x] Add Generator Expression.
- [x] Add List Comprehension vs Generator Expression.
- [x] Add one-time generator consumption discussion.
- [x] Add `yield from`.
- [x] Add Pipeline vs Batch discussion.
- [x] Add FastAPI `StreamingResponse` connections.
- [x] Add Playwright data pipeline connections.
- [x] Add AI backend token streaming connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day07 Repository Tasks

- [x] Update `docs/python/day07-iterators-generators.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Update `CURRICULUM.md`.
- [x] Commit changes.
- [x] Push to GitHub.

---

## Completed Day07 Interview Tasks

- [x] Add beginner iterator/generator questions.
- [x] Add intermediate iterator/generator questions.
- [x] Add senior iterator/generator questions.
- [x] Add standard answers.
- [x] Add follow-up questions.
- [x] Add engineering perspectives.

---

## Completed Day07 Homework

- [x] Complete Iterable vs Iterator classification exercises.
- [x] Complete output prediction exercises.
- [x] Complete `iter()` and `next()` exercises.
- [x] Complete `StopIteration` reasoning exercises.
- [x] Complete Generator lifecycle exercises.
- [x] Complete Generator Expression exercises.
- [x] Complete one-time consumption exercises.
- [x] Complete `yield from` exercises.
- [x] Complete FastAPI `StreamingResponse` thinking exercise.
- [x] Complete Playwright pipeline exercise.
- [x] Complete AI token streaming exercise.
- [x] Complete Pipeline vs Batch exercise.

---

## Completed Day06 Tasks

- [x] Complete Day06 classroom learning.
- [x] Generate Day06 handbook lesson.
- [x] Add why decorators matter.
- [x] Add cross-cutting concerns discussion.
- [x] Add decorator mental model.
- [x] Add `@decorator` and `func = decorator(func)` equivalence.
- [x] Add wrapper function call flow.
- [x] Add universal decorator template.
- [x] Add `*args` and `**kwargs` parameter forwarding.
- [x] Add `functools.wraps` metadata preservation.
- [x] Add production examples for logging, timing, retry, auth, cache, and AI tracing.
- [x] Add FastAPI connections.
- [x] Add Playwright connections.
- [x] Add AI backend connections.
- [x] Add code review discussion.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day06 Repository Tasks

- [x] Update `docs/python/day06-decorators.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Commit changes.
- [x] Push to GitHub.

---

## Completed Day06 Interview Tasks

- [x] Add beginner decorator questions.
- [x] Add intermediate decorator questions.
- [x] Add senior decorator questions.
- [x] Add Chinese explanations.
- [x] Add English standard answers.
- [x] Add overseas interview expressions.

---

## Completed Day06 Homework

- [x] Complete decorator output prediction exercises.
- [x] Complete decorator execution order exercises.
- [x] Complete wrapper call flow exercises.
- [x] Complete timer decorator exercise.
- [x] Complete logging decorator exercise.
- [x] Complete argument forwarding exercise.
- [x] Complete return value forwarding exercise.
- [x] Complete `TypeError` analysis exercise.
- [x] Complete `functools.wraps` metadata comparison.
- [x] Complete FastAPI route decorator reasoning exercise.
- [x] Complete Playwright retry decorator exercise.
- [x] Complete AI token logger decorator exercise.

---

## Completed Day05 Tasks

- [x] Complete Day05 classroom learning.
- [x] Generate Day05 handbook lesson.
- [x] Add Closure as Function Object plus Captured Environment.
- [x] Add closure memory model and state preservation.
- [x] Add `nonlocal` explanation and `UnboundLocalError` reasoning.
- [x] Add Factory Function design discussion.
- [x] Add Closure vs Class comparison.
- [x] Add Late Binding and `i=i` fix.
- [x] Add FastAPI dependency factory connections.
- [x] Add Playwright configuration factory connections.
- [x] Add AI prompt builder factory connections.
- [x] Add interview questions.
- [x] Add homework and review checklist.

---

## Completed Day05 Repository Tasks

- [x] Update `docs/python/day05-closures.md`.
- [x] Update `cheat_sheets/python.md`.
- [x] Update `interview/python.md`.
- [x] Update `PROJECT_STATUS.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.
- [x] Commit changes.
- [x] Push to GitHub.

---

## Completed Day05 Interview Tasks

- [x] Add closure definition questions.
- [x] Add captured environment questions.
- [x] Add `nonlocal` questions.
- [x] Add Factory Function questions.
- [x] Add Closure vs Class questions.
- [x] Add Late Binding questions.
- [x] Add FastAPI, Playwright, and AI backend scenarios.
- [x] Add English interview answers.

---

## Completed Day05 Homework

- [x] Complete closure identification exercises.
- [x] Complete closure memory model exercises.
- [x] Complete `nonlocal` output prediction exercises.
- [x] Complete `UnboundLocalError` repair exercises.
- [x] Complete Factory Function exercises.
- [x] Complete `make_multiplier()` exercise.
- [x] Complete counter implementation exercise.
- [x] Complete Closure vs Class refactoring exercise.
- [x] Complete Late Binding output prediction exercise.
- [x] Complete Late Binding fix with `i=i`.
- [x] Complete FastAPI dependency factory exercise.
- [x] Complete Playwright timeout factory exercise.
- [x] Complete AI prompt builder factory exercise.

---

## Blocked

None.

---

## Future Backlog

### Day05 Review

- [ ] Explain Closure as Function Object plus Captured Environment.
- [ ] Draw the closure memory model from memory.
- [ ] Rebuild `make_counter()` from memory.
- [ ] Explain why the outer function has returned but captured state still exists.
- [ ] Explain why `x = x + 1` raises `UnboundLocalError`.
- [ ] Explain how `nonlocal` changes rebinding behavior.
- [ ] Build `make_multiplier()` from memory.
- [ ] Explain Closure vs Class trade-offs.
- [ ] Explain Late Binding and the `i=i` fix.
- [ ] Write one FastAPI dependency factory from memory.
- [ ] Write one Playwright timeout factory from memory.
- [ ] Write one AI prompt builder factory from memory.

### Day06 Preparation

- [ ] Review function objects.
- [ ] Review closures.
- [ ] Review factory functions.
- [ ] Review functions passed as arguments.
- [ ] Review functions returned from functions.
- [ ] Prepare questions about wrapper functions.
- [ ] Prepare examples for backend decorators.

### Day06 Review

- [ ] Explain why decorators exist.
- [ ] Explain cross-cutting concerns.
- [ ] Explain `@decorator` as `func = decorator(func)`.
- [ ] Draw the wrapper call flow from memory.
- [ ] Explain why `wrapper()` can raise `TypeError`.
- [ ] Write a universal decorator from memory.
- [ ] Explain why production decorators use `functools.wraps`.
- [ ] Compare metadata with and without `wraps`.
- [ ] Explain why FastAPI depends on metadata.
- [ ] Write one Playwright retry decorator from memory.
- [ ] Write one AI token logger decorator from memory.

### Day07 Preparation

- [ ] Review `for` loops.
- [ ] Review function return values.
- [ ] Review lazy evaluation motivation.
- [ ] Prepare questions about iterator protocol.
- [ ] Prepare examples for streaming data and pagination.

### Day07 Review

- [ ] Explain iterable vs iterator.
- [ ] Explain `iter()` and `next()`.
- [ ] Explain why Python uses `StopIteration`.
- [ ] Explain why iterable and iterator are separated.
- [ ] Draw generator lifecycle from memory.
- [ ] Explain why generators can only be consumed once.
- [ ] Compare list comprehension and generator expression.
- [ ] Explain `yield from`.
- [ ] Explain Pipeline vs Batch.
- [ ] Explain FastAPI `StreamingResponse` with generator language.
- [ ] Explain AI token streaming with generator language.

### Day08 Preparation

- [ ] Review `StopIteration`.
- [ ] Review `TypeError` and `UnboundLocalError` from previous lessons.
- [ ] Prepare questions about expected vs unexpected exceptions.
- [ ] Prepare examples for FastAPI error handling.
- [ ] Prepare examples for Playwright retry and recovery.

### Day08 Review

- [ ] Explain `try / except` control flow.
- [ ] Explain why `except Exception` is risky.
- [ ] Explain exception propagation.
- [ ] Explain return `None` vs raise.
- [ ] Implement `check_age(age)`.
- [ ] Implement `InvalidPromptError`.
- [ ] Explain `raise ... from ...`.
- [ ] Read a traceback for root cause.
- [ ] Explain FastAPI `HTTPException`.
- [ ] Explain Playwright recoverable vs non-recoverable errors.
- [ ] Explain AI backend `LLMRequestError` and `ToolExecutionError`.

### Day09 Preparation

- [x] Review Python file imports.
- [x] Review `__init__.py`.
- [x] Prepare questions about package boundaries.
- [x] Prepare examples for FastAPI app structure.
- [x] Prepare examples for AI backend module organization.

### Day09 Review

- [ ] Explain import as execution, not copy-paste.
- [ ] Explain module objects and namespaces.
- [ ] Explain `sys.modules`.
- [ ] Explain module vs package.
- [ ] Explain `__init__.py` and namespace packages.
- [ ] Compare `import module` and `from module import name`.
- [ ] Explain why wildcard imports are risky.
- [ ] Explain absolute vs relative imports.
- [ ] Identify import side effects.
- [ ] Design a FastAPI package boundary.
- [ ] Design a Playwright worker module boundary.
- [ ] Design an AI backend package structure.

### Day10 Preparation

- [x] Review function signatures.
- [x] Review public function boundaries.
- [x] Prepare examples for `list[str]`, `dict[str, Any]`, and `Optional`-style thinking.
- [x] Prepare FastAPI examples where type hints affect request and response design.
- [x] Prepare AI backend examples where types document tool contracts.

### Day10 Review

- [ ] Explain Type Hints as interface contracts.
- [ ] Explain why Type Hints are not runtime checks by default.
- [ ] Type parameters and return values.
- [ ] Explain `list[T]` vs `list`.
- [ ] Explain `dict[K, V]`.
- [ ] Explain `User | None`, `Optional`, and `Union`.
- [ ] Explain type inference.
- [ ] Explain why empty collections often need annotations.
- [ ] Explain `TypeVar` and `Generic`.
- [ ] Explain why `T -> T` is better than `object -> object`.
- [ ] Explain how FastAPI uses Type Hints.
- [ ] Explain Playwright object type boundaries.
- [ ] Explain AI backend message and tool contracts.

### Day11 Preparation

- [x] Review Day01 object model.
- [x] Review references and mutability.
- [x] Prepare questions about class vs instance.
- [x] Prepare examples for service classes.
- [x] Prepare examples for Playwright page objects.
- [x] Prepare examples for AI agent classes.

### Day11 Review

- [ ] Explain OOP as responsibility design.
- [ ] Explain object, class, and instance.
- [ ] Explain state and behavior.
- [ ] Explain `self`.
- [ ] Explain why `u1.say_hi()` becomes `User.say_hi(u1)`.
- [ ] Explain class attribute vs instance attribute.
- [ ] Explain attribute lookup.
- [ ] Explain method lookup.
- [ ] Explain inheritance and override.
- [ ] Explain `super().__init__()`.
- [ ] Explain basic MRO.
- [ ] Explain composition.
- [ ] Explain Is-A vs Has-A.
- [ ] Explain why FastAPI prefers composition.
- [ ] Explain Playwright shared behavior and isolated state.
- [ ] Explain AI backend `ChatService` composition.

### Day12 Preparation

- [x] Review object lifecycle.
- [x] Review exception handling.
- [x] Prepare questions about setup and cleanup.
- [x] Prepare examples for file handling.
- [x] Prepare examples for database session cleanup.
- [x] Prepare examples for Playwright context cleanup.
- [x] Prepare examples for AI backend resource cleanup.

### Day12 Review

- [ ] Explain the resource lifecycle: Acquire -> Use -> Release.
- [ ] Explain why Release is the dangerous step.
- [ ] Explain how `try / finally` guarantees cleanup.
- [ ] Explain what `with` guarantees.
- [ ] Explain `__enter__` and `__exit__`.
- [ ] Explain the three `__exit__` arguments.
- [ ] Explain returning `True` vs `False` from `__exit__`.
- [ ] Explain why `@contextmanager` uses `yield`.
- [ ] Explain why `yield` must sit inside `try / finally`.
- [ ] Explain why business logic should not own resource management.
- [ ] Write a FastAPI `yield` dependency from memory.
- [ ] Explain Playwright `BrowserContext` cleanup.
- [ ] Explain AI backend LLM stream and lock cleanup.

### Day13 Preparation

- [x] Review generators, pause, and resume.
- [x] Review context manager cleanup.
- [x] Prepare questions about blocking vs non-blocking work.
- [x] Prepare examples for `async` and `await`.
- [x] Prepare examples for FastAPI async routes.
- [x] Prepare examples for Playwright async API.
- [x] Prepare examples for AI backend concurrency.

### Day13 Review

- [ ] Explain why async helps I/O but not CPU work.
- [ ] Explain blocking vs non-blocking from the Event Loop's view.
- [ ] Explain why one blocking call freezes the loop.
- [ ] Explain what the Event Loop does during `await`.
- [ ] Explain why calling a coroutine does not run it.
- [ ] Explain coroutine vs Task.
- [ ] Explain the three effects of `await`.
- [ ] Explain why `gather()` returns input order.
- [ ] Draw the Task lifecycle from memory.
- [ ] Explain cooperative cancellation and `CancelledError`.
- [ ] Explain when a Task's exception is raised.
- [ ] Explain why unlimited `gather()` is dangerous.
- [ ] Explain how a `Semaphore` gives stable throughput.
- [ ] Explain the FastAPI async request lifecycle.

### Day14 Preparation

- [x] Review Day01-Day13 core concepts.
- [x] Prepare a small async FastAPI project scope.
- [x] Prepare mock interview questions across all foundation topics.
- [x] Prepare production discussion prompts for the mock interview.

### Day14 Review

- [ ] Name each layer and its single responsibility.
- [ ] State what each layer must NOT do.
- [ ] Explain why routers stay thin.
- [ ] Explain why the service avoids HTTP and SQL.
- [ ] Explain why the browser layer returns data, not models.
- [ ] Explain why the LLM sits behind an interface.
- [ ] Explain the repository pattern.
- [ ] Explain dependency injection and stateless services.
- [ ] Explain async vs worker scaling.
- [ ] Explain semaphore, retry, and backoff together.
- [ ] Explain the task-status pattern for long jobs.
- [ ] Explain one architectural trade-off.

### Phase 2 Preparation (Git, Linux, Docker)

- [x] Review Git basics and workflow.
- [ ] Review Linux command-line fundamentals.
- [ ] Prepare Docker and Docker Compose learning goals.
- [ ] Plan how the mini project will be containerized.

### Day15 Review

- [ ] Explain why Git uses snapshots, not pure diffs.
- [ ] Explain why commits are immutable.
- [ ] Explain repository vs working directory.
- [ ] Explain why commit builds from the Index.
- [ ] Draw the three-tree model from memory.
- [ ] Explain HEAD vs branch.
- [ ] Explain detached HEAD.
- [ ] Fill in the reset soft/mixed/hard table.
- [ ] Explain which reset mode can lose uncommitted work.
- [ ] Recover a mistaken reset with reflog.

### Day16 Review

- [ ] Explain the engineering problem branches solve.
- [ ] Explain why a branch is a movable reference, not a copy.
- [ ] Explain why branch creation is instant.
- [ ] Explain HEAD and what moves on commit.
- [ ] Explain fast-forward merge.
- [ ] Explain three-way merge and the two-parent merge commit.
- [ ] Explain why merge conflicts happen and why Git refuses to guess.
- [ ] Explain Git history as a DAG.

### Day17 Review

- [ ] Explain why a direct push to main is dangerous.
- [ ] Explain the four parts of a Pull Request.
- [ ] Explain CI (rules) vs code review (intent).
- [ ] Explain what Branch Protection enforces.
- [ ] Explain what a stale review is and why it happens.
- [ ] Explain why review discussions are preserved.

### Day18 Review

- [ ] Explain why Git history is for humans.
- [ ] Explain development history vs product history.
- [ ] Explain merge commit, squash, and rebase and when to use each.
- [ ] Explain what senior reviewers focus on.
- [ ] Explain review the code, not the coder.
- [ ] Explain the three goals of review.

### Day19 Review

- [ ] Explain why teams manage work, not only code.
- [ ] Explain Issue as a work item and its four purposes.
- [ ] Explain ownership vs blame.
- [ ] Explain Label as metadata for retrieval, workflow, and automation.
- [ ] Explain Milestone as a delivery goal.
- [ ] Explain Projects as workflow management.
- [ ] State the hierarchy: Issue, Label, Milestone, Project.
- [ ] Trace the Idea-to-Release workflow.

### Day20 Review

- [ ] Explain why "I tested locally" is not enough.
- [ ] Explain what CI establishes.
- [ ] Explain the four properties of a pipeline.
- [ ] Explain what a quality gate protects.
- [ ] Explain the four properties of CD.
- [ ] Explain CI vs CD.
- [ ] Explain Workflow as Code and Everything as Code.
- [ ] Trace the full Idea-to-Production lifecycle.

### Day26 Preparation — Kubernetes Foundations

- [x] Review Day25 deployment foundations (blue-green, drain, rollback, immutable digest).
- [ ] Prepare questions about Pods, Deployments, and Services.
- [ ] Prepare questions about ConfigMaps and Secrets.
- [ ] Prepare questions about desired-state reconciliation vs manual blue-green.

### Day25 Review

- [ ] Why keep the backend port internal, and what is the stable public path?
- [ ] What do listen / server_name / proxy_pass mean?
- [ ] What are the three properties of TLS, and where does it terminate?
- [ ] Why can a 308 redirect not protect an already-sent token?
- [ ] What does an expired certificate break, and how do you reload Nginx safely?
- [ ] Why promote the exact digest instead of rebuilding per environment?
- [ ] Order a blue-green deploy with verify/switch/observe/drain/rollback.
- [ ] Why is Expand-Migrate-Contract used for PostgreSQL, not blue-green?
- [ ] Why is DNS TTL not an atomic switch?

### Day24 Review

- [ ] Why do individually runnable containers not make a reproducible system?
- [ ] `depends_on` vs healthcheck vs application retry?
- [ ] Project vs Service vs Image vs Container; rebuild vs recreate?
- [ ] Why publish only the API port and use service DNS internally?
- [ ] Why segment networks, and what can it NOT replace?
- [ ] What does `down` keep vs `down --volumes`?
- [ ] Environment variable vs secret vs governed business data?
- [ ] Where does Compose fit in production, and where is a cluster required?

### Day23 Review

- [ ] Why is a container an isolated process, not a small VM?
- [ ] Image vs container, and does a rebuild upgrade running containers?
- [ ] Image layer vs writable layer, and cache ordering?
- [ ] What do FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT do?
- [ ] Why is build separate from run?
- [ ] Why does durable state belong in a volume, not the writable layer?
- [ ] Why does localhost not reach another container?
- [ ] Why rebuild and replace instead of editing a running container?

### Day22 Review

- [ ] Why does a matrix not normally reduce executions?
- [ ] How do you decide `fail-fast: true` vs `false`?
- [ ] Cache vs artifact, and what happens on a cache miss?
- [ ] Composite action vs reusable workflow?
- [ ] `needs` vs `if` vs `continue-on-error`?
- [ ] Why build once and deploy an immutable digest, not `:latest`?
- [ ] Why serialize production with `cancel-in-progress: false`?

### Day21 Review

- [ ] Draw the Event -> Trigger -> Workflow -> Runner -> Job -> Step -> Result model.
- [ ] Explain `on` vs `runs-on`.
- [ ] Explain `run` vs `uses` vs `with`.
- [ ] Explain why checkout is first.
- [ ] Explain one job = one fresh runner and when to split jobs.
- [ ] Explain why build waits for the quality gate.
- [ ] Explain GitHub-hosted vs self-hosted runner trade-off.

### Phase 2 Roadmap (Day21-Day28)

- [x] Day21 — GitHub Actions Fundamentals (Completed).
- [x] Day22 — GitHub Actions Advanced (Completed).
- [x] Day23 — Docker Fundamentals (Completed).
- [x] Day24 — Docker Compose (Completed).
- [x] Day25 — Deployment Foundations (Completed).
- [x] Day26 — Kubernetes Foundations (Completed).
- [x] Day27 — Kubernetes Workloads (Completed).
- [x] Day28 — AI Backend Production Architecture (Completed).

### Future Knowledge Base TODO

Do not create this structure yet.

Reserved future structure:

```text
knowledge/
├── python/
├── fastapi/
├── playwright/
├── docker/
├── redis/
├── postgres/
└── linux/
```

Purpose:

- Store future reference material.
- Keep reference material separate from lessons.
- Avoid duplicating `docs/` lesson content.

---

## Completed

- [x] Create repository.
- [x] Add repository management files.
- [x] Create directory skeleton.
- [x] Remove duplicated course structure.
- [x] Add README files for every project directory.
- [x] Populate `interview/python.md` as the interview template.
- [x] Add `cheat_sheets/python.md`.
- [x] Add reusable prompts.
- [x] Improve assets folder structure.
- [x] Add `REPOSITORY_GUIDE.md`.
- [x] Add `CONTRIBUTING.md`.
- [x] Release Day01 — Python Object Model.
- [x] Mark Day01 as the Gold Standard lesson.
- [x] Complete Day02 — Mutable vs Immutable.
- [x] Complete Day03 — Functions & Parameter Passing.
- [x] Complete Day04 — Scope & LEGB.
- [x] Complete Day05 — Closures.
- [x] Complete Day06 — Decorators.
- [x] Complete Day07 — Iterators & Generators.
- [x] Complete Day08 — Exception Handling.
- [x] Complete Day09 — Modules & Packages.
- [x] Complete Day10 — Type Hints.
- [x] Complete Day11 — Object-Oriented Programming.
- [x] Complete Day12 — Context Managers.
- [x] Complete Day13 — Async Programming.
- [x] Complete Day14 — Mini Project & Backend Architecture.
- [x] Complete Phase 1 — Python Foundations.
- [x] Complete Day15 — Git Fundamentals (Phase 2 started).
- [x] Complete Day16 — Git Branch & Merge.
- [x] Complete Day17 — GitHub Workflow & Collaboration.
- [x] Complete Day18 — Merge Strategy & Code Review.
- [x] Complete Day19 — GitHub Project Management.
- [x] Complete Day20 — CI/CD Foundations.
- [x] Complete Day21 — GitHub Actions Fundamentals.
- [x] Complete Day22 — GitHub Actions Advanced.
- [x] Complete Day23 — Docker Fundamentals.
- [x] Complete Day24 — Docker Compose.
- [x] Complete Day25 — Deployment Foundations.
- [x] Complete Day26 — Kubernetes Foundations.
- [x] Complete Day27 — Kubernetes Workloads.
- [x] Complete Day28 — AI Backend Production Architecture.
- [x] Complete Phase 2 — Engineering Foundations (Day15-Day28).
