# CHANGELOG.md

All notable changes to this repository will be documented in this file.

This project follows a practical versioning style:

- `v0.x.x` — training system under construction
- `v1.0.0` — first complete AI Backend Engineer Handbook release

---

## v0.1.95 — Day48 Alembic and Safe AI Backend Schema Evolution

Date: 2026-07-31

### Review fix (2026-07-31)

- **Finding 1 — Backfill could loop forever on unknown ownership.** An unknown-ownership running Job stayed `lease_owner IS NULL`, so it re-matched the candidate query every batch and the default `max_batches=None` never terminated. Fix: the Expand revision (`0002_expand_lease`) now also adds a **nullable `lease_backfill_state` reconciliation marker** (no fabricated default, plus a `CHECK ... NOT VALID` restricting it to `'reconcile'`), the backfill candidate query excludes routed rows (`AND lease_backfill_state IS NULL`), and `day48_lease_backfill.py` gains `route_to_reconciliation()` — a guarded, idempotent `UPDATE ... SET lease_backfill_state='reconcile' WHERE running AND lease_owner IS NULL AND lease_backfill_state IS NULL RETURNING` that **persists** the unknown state **without fabricating any Lease owner/token/expiry**. Because a proved Job gets `lease_owner` and an unknown Job gets the marker, every selected Job leaves the candidate set, so the loop **terminates** and a **restart** never re-selects it (the database state is the durable checkpoint). The report field was renamed `skipped_unknown` -> `routed_to_reconciliation`.
- **Finding 2 — DB URL override claim now matches the implementation.** `alembic.ini` claimed a `-x db_url=` / env-var override but `env.py` only read `sqlalchemy.url`. Fix: `env.py` now resolves the URL by explicit priority — **`alembic -x db_url=<url>` > env `DAY48_ALEMBIC_DATABASE_URL` > `alembic.ini` `sqlalchemy.url`** (a non-credential offline-render placeholder, documented as such and never a production connection). `env.py` is now import-safe (its migration block is skipped outside an Alembic run) so the pure `resolve_database_url()` is unit-testable, and the offline `--sql` render still works and still never connects.
- These fixes grew the static/offline suite from 10 to **16** (`pytest -q test_day48_alembic.py` -> 16 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade --sql` still renders the Expand/Validate/Contract DDL. New tests cover: backfill termination when all candidates are unknown; unknown Jobs persisted to reconciliation without fabrication; restart does not re-select a routed Job; known-evidence Jobs still backfill; `route_to_reconciliation` idempotency; and the `-x db_url` > env > ini resolution priority with the placeholder documented offline-only. **PostgreSQL runtime remains NOT RUN** (static/offline + fake-session control flow are not PostgreSQL evidence).

### Review fix — round 2 (2026-07-31)

- **Finding 1 — the reconcile marker must not bypass the running-requires-Lease invariant.** The prior fix stopped the infinite loop but left a gap: with only the triple-coherence CHECK, a `running` Job with a NULL Lease and `lease_backfill_state='reconcile'` looked "handled." It is not. The Expand revision now also adds the **Day36 core** `CHECK (job_status <> 'running' OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)) NOT VALID` (`jobs_running_requires_lease`, Day48 field names), and the Validate revision now `VALIDATE`s it too. Reconciliation is **triage, not resolution**: the backfill now distinguishes **automatic candidates** (running + `lease_owner IS NULL` + `lease_backfill_state IS NULL` — what the auto-loop may fill, so it terminates) from **`unresolved_running_without_lease`** (ALL running rows with a NULL Lease, **including** reconcile-marked ones — the Day36 `remaining_targets`), exposed on `BackfillReport` via `count_unresolved_running_without_lease()`. Routing to `'reconcile'` no longer reduces that count, so it is never a reason to run VALIDATE/Switch/Contract. A trusted Lease backfill now also clears the marker (`apply_lease_evidence` sets `lease_backfill_state = NULL`), and an audited real recovery (`resolve_by_verified_terminal_state`) sets a Job's TRUE verified terminal state (never a fabricated `'failed'`, and never `'running'`) — the only two ways `remaining_targets` reaches 0.
- **Finding 2 — online must not fall back to the offline placeholder URL.** `resolve_database_url(...)` now takes `allow_placeholder`: **offline** mode may use the `alembic.ini` non-credential placeholder, but **online** mode requires a real external URL (`-x db_url=...` or `DAY48_ALEMBIC_DATABASE_URL`) and **fails fast** with a no-credential message otherwise — the placeholder is never an online connection fallback. Priority `-x db_url` > `DAY48_ALEMBIC_DATABASE_URL` is preserved; offline `--sql` still renders and never connects.
- These fixes grew the static/offline suite from 16 to **20** (`pytest -q test_day48_alembic.py` -> 20 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade --sql` still renders the Expand/Validate/Contract DDL (now including `jobs_running_requires_lease`). New/updated tests cover: `jobs_running_requires_lease` present in Expand and validated in 0003; the unresolved count includes reconcile-marked rows; reconcile is not resolution (a routed Job stays unresolved after restart); a trusted backfill resolves and clears the marker; an audited terminal-state recovery (rejecting `'running'`); the VALIDATE precondition (`unresolved==0`) is reached only after real resolution; and the online-requires-external-URL fail-fast vs offline-placeholder-allowed resolution. **PostgreSQL runtime remains NOT RUN** — static/offline + fake-session control flow are not PostgreSQL evidence.

### Review fix — round 3 (2026-07-31)

- **Finding 1 — a pure Expand and the strict Lease constraints must not share one revision.** `CHECK ... NOT VALID` skips the one-time scan of legacy rows but fully enforces the rule on EVERY future INSERT/UPDATE, so an OLD Worker updating a still-`running` Job with a NULL Lease would be rejected — "old Workers coexist with Expand" was therefore false while the constraint lived in Expand. The revision chain is now split and linear: `0001_baseline` -> **`0002_expand_lease` (nullable columns ONLY, the OLD/NEW compatibility window)** -> **`0003_add_lease_constraints` (adds `jobs_lease_triple_coherent` + `jobs_running_requires_lease` + `jobs_lease_backfill_state_allowed`, all `NOT VALID`, with an explicit precondition that OLD Writers are drained/isolated first)** -> `0004_validate_lease` (VALIDATEs both) -> `0005_contract_legacy`. Single head `0005_contract_legacy`. Docs no longer describe `NOT VALID` as "old Writers unaffected".
- **Finding 2 — an unknown Provider outcome must not be requeued or bare-flipped.** The dangerous generic `resolve_by_verified_terminal_state()` (which accepted `'queued'` — a requeue that cleared the unresolved count without proving the Provider ran — and could bare-`UPDATE job_status='succeeded'` without `finished_at`/Artifact/Event) is **removed**. It is replaced by a non-mutating router `classify_unknown_running_recovery()` -> `RecoveryBoundary`: `None`/unverified -> `KEEP_UNKNOWN` (stay unknown/reconciliation; never requeue, never blind Provider retry); `'succeeded'` -> `COMPLETION_UOW` (the Day47 guarded completion UoW that commits `finished_at` + ResultArtifact + `job_succeeded` Event together); `'failed'`/`'cancelled'` -> `GUARDED_TERMINAL_RECOVERY`; `'queued'`/`'running'`/any other status -> `UnsafeRecoveryError`. Day48 classifies and ROUTES; it performs no status mutation, so it cannot bypass the Day47 completion contract or the guarded terminal-recovery/audit requirements.
- These fixes grew the static/offline suite from 20 to **22** (`pytest -q test_day48_alembic.py` -> 22 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade --sql` still renders the now-5-revision Expand/Constraints/Validate/Contract DDL. New/updated tests cover: the pure Expand has NO constraint (columns only); the separate constraint revision adds the CHECKs and documents the drain/isolate precondition; the graph stays single-head and linear; a `'queued'` requeue is refused; a verified `'succeeded'` routes to the Day47 completion UoW (no bare flip); an unknown outcome stays reconciliation; the router issues no SQL and the bare mutator is gone. **PostgreSQL runtime remains NOT RUN** — static/offline + fake-session control flow are not PostgreSQL evidence.

### Review fix — round 4 (2026-07-31)

- **Finding 1 (blocking) — reconciliation triage cannot live on `app.jobs` once the strict Lease constraint is enforced.** After `0003_add_lease_constraints`, `jobs_running_requires_lease` rejects **any** `UPDATE` that leaves a row `running` with a NULL Lease (PostgreSQL `23514`). The round-1/2 design routed unknown-ownership Jobs by setting a `lease_backfill_state='reconcile'` marker column on `app.jobs` — an `UPDATE` that leaves the row `running` with a NULL Lease — so real PostgreSQL would reject `route_to_reconciliation()` after the constraint is live. The fake-session tests never enforce the CHECK, so they hid the bug. Fix: triage now lives in an **independent** table. `0002_expand_lease` additively `CREATE`s `app.job_lease_reconciliation` (`reconciliation_id` uuid PK, `job_id` uuid NOT NULL FK -> `app.jobs(job_id)` `ON DELETE RESTRICT`, `reason` text, `routed_at` timestamptz, `resolution_status` text, `resolved_at` timestamptz, `UNIQUE(job_id)`, named CHECKs on `reason`/`resolution_status`) and **no longer** adds the `lease_backfill_state` column; `0003` **no longer** adds `jobs_lease_backfill_state_allowed`.
- **`day48_lease_backfill.py`** now uses the queue table: `route_to_reconciliation()` is `INSERT INTO app.job_lease_reconciliation (job_id, reason) VALUES (:job_id,'unknown_ownership') ON CONFLICT (job_id) DO NOTHING RETURNING reconciliation_id` — it **never touches `app.jobs`** (so it is legal after the strict constraint) and fabricates no Lease field; the automatic candidate query excludes routed Jobs via `NOT EXISTS (SELECT 1 FROM app.job_lease_reconciliation r WHERE r.job_id=j.job_id)` (so the loop still terminates and a restart never re-selects); `apply_lease_evidence()` now sets **only** the Lease triple on `app.jobs` (single responsibility — no marker to clear); a new `close_reconciliation_record()` is the separate audited step that marks a queue row `'resolved'` after the Job is truthfully resolved (queue-only, never `app.jobs`). `count_unresolved_running_without_lease()` is unchanged: it counts **all** running `app.jobs` rows with a NULL Lease **including** queue-routed ones (it joins no queue table), so queuing remains **triage, not resolution** and `unresolved==0` is still reached only by (a) a trusted Lease backfill or (b) an audited real recovery routed by `classify_unknown_running_recovery`.
- Ordering preserved: Pure Expand (columns + the additive queue table) -> new code tolerates NULL -> old Writers drained/isolated -> strict `NOT VALID` constraints (`0003`) -> Backfill / independent reconciliation routing -> Validate (`0004`) -> Switch -> Contract (`0005`). Independent routing is safe **after** the strict constraints precisely because it never modifies a violating `app.jobs` row.
- These fixes grew the static/offline suite from 22 to **24** (`pytest -q test_day48_alembic.py` -> 24 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade 0001_baseline:head --sql` still renders the DDL (now `CREATE TABLE app.job_lease_reconciliation` in Expand, and no `jobs_lease_backfill_state_allowed`). New/updated tests cover: Expand creates the queue table and adds no marker column; routing `INSERT`s into the queue with `ON CONFLICT DO NOTHING` and issues **no** `app.jobs` write (the round-4 safety property); `apply_lease_evidence` writes only `app.jobs`; a routed Job is excluded from re-selection via `NOT EXISTS` yet still counts in `unresolved_running_without_lease`; `close_reconciliation_record` is queue-only and idempotent; and a structural check that no backfill statement issues a violating `app.jobs` UPDATE. **PostgreSQL runtime remains NOT RUN** — static/offline + fake-session control flow are not PostgreSQL evidence, and in particular do not prove PostgreSQL would accept these statements under the live constraint.

### Review fix — round 5 (2026-07-31)

- **Finding 1 (P1) — a queued Job had no real resolution path.** `select_backfill_batch()` permanently excludes routed Jobs via `NOT EXISTS (... app.job_lease_reconciliation ...)`, yet `test_validate_precondition_reached_only_after_real_resolution` assumed the *same* Job could later be re-selected by `run_backfill()` and given a trusted Lease — inconsistent with real PostgreSQL SQL (once a queue row exists the Job is no longer an automatic candidate). Fix: a **dedicated, auditable, restartable** resolution path. `day48_lease_backfill.py` gains `select_open_reconciliation_batch()` (`SELECT r.job_id FROM app.job_lease_reconciliation r JOIN app.jobs j ON j.job_id=r.job_id WHERE r.resolution_status='open' AND j.job_status='running' AND j.lease_owner IS NULL ORDER BY r.routed_at FOR UPDATE OF r SKIP LOCKED LIMIT :n`) and `run_reconciliation_resolution()` which, for each open record, in **one short transaction**: (1) runs the guarded `UPDATE app.jobs` that writes the full Lease triple (`apply_lease_evidence`), and (2) marks the queue record `resolved` + `resolved_at` (`close_reconciliation_record`) **only if that UPDATE actually affected the row**. No trusted evidence → the record stays `open` (no fabricated Lease, no requeue, no bare status flip, no Provider). A 0-row guarded UPDATE (the Job no longer matches running + unowned) does **not** close the record on that pass — closing is gated on this UoW's own successful write, keeping the pass idempotent and restart-safe (short tx, `FOR UPDATE ... SKIP LOCKED`). `run_backfill()` now handles **automatic candidates only** and no longer pretends it will re-select an open record. `count_unresolved_running_without_lease()` is unchanged: it still counts **all** running `app.jobs` rows with a NULL Lease (including open records), so `unresolved` reaches 0 — the gate before VALIDATE/Switch/Contract — only after a real Lease write.
- **Finding 2 (P2) — Contract docstring revision number.** `0005_contract_legacy.py` said "Validate (0003) succeeded"; corrected to "Validate (0004) succeeded" to match the split revision chain.
- Residual "marker" phrasing in the backfill docstrings/comments was corrected to the independent-queue vocabulary (the two remaining "marker" mentions are the intentional *why a marker column is wrong* explanation).
- These fixes grew the static/offline suite from 24 to **30** (`pytest -q test_day48_alembic.py` -> 30 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade 0001_baseline:head --sql` still renders the DDL. New/updated tests cover: the automatic query never re-selects a queued Job while the dedicated selector locks OPEN records with `FOR UPDATE OF r SKIP LOCKED`; later evidence writes the Lease **then** closes the record (order + one commit); no evidence leaves the record open (no UPDATE, no close); a re-run is a clean no-op; a 0-row guarded UPDATE does not close the record; the path calls no Provider and never bare-flips a status; and the VALIDATE-precondition test now routes via `run_backfill` but resolves via `run_reconciliation_resolution`, matching real SQL. **PostgreSQL runtime remains NOT RUN** — static/offline + fake-session control flow are not PostgreSQL evidence and do not prove PostgreSQL would accept these statements under the live constraint.

### Review fix — round 6 (2026-07-31)

- **Finding 1 — `run_reconciliation_resolution()` looped forever on an unprovable open record.** With `max_batches=None`, a `resolution_status='open'` record whose `evidence_source.prove()` returned `None` was only counted (`still_open += 1`) and committed unchanged, so `select_open_reconciliation_batch()` re-selected the same record on the next pass — an infinite loop in real PostgreSQL that the fake-session tests hid by returning an empty next batch. Fix: **reconciliation polling with a persisted backoff** (explicitly NOT Job retry and NOT Provider retry). `0002_expand_lease` adds three columns to `app.job_lease_reconciliation`: `next_attempt_at timestamptz NOT NULL DEFAULT now()`, `last_checked_at timestamptz`, `check_attempts integer NOT NULL DEFAULT 0` (+ `CHECK (check_attempts >= 0)`). `select_open_reconciliation_batch()` now returns only **due** records (`AND r.next_attempt_at <= now()`, `ORDER BY r.next_attempt_at`). A new `defer_reconciliation_record()` is a **queue-only**, short, guarded, audited `UPDATE` that bumps `check_attempts` + `last_checked_at` and pushes `next_attempt_at = now() + make_interval(secs => LEAST(:base * power(2, check_attempts), :max))` (base 60s, doubling, cap 3600s) — it never fabricates a Lease, never requeues, never touches `app.jobs`/`job_status`, and calls no Provider. When a resolver finds no evidence it calls `defer_reconciliation_record()`, so the record becomes not-due and is not re-selected in the loop; `run_reconciliation_resolution()` therefore **terminates** on the **due-filter + forward backoff**, not on a mocked empty batch. When trusted evidence appears later the path is unchanged: in one short tx, guarded `UPDATE app.jobs` writes the Lease triple, and only if it affected the row is the record closed. `count_unresolved_running_without_lease()` is unchanged — an open (deferred) record still counts as a remaining target, so `unresolved==0` (the VALIDATE/Switch/Contract gate) still requires a real Lease write.
- These fixes grew the static/offline suite from 30 to **33** (`pytest -q test_day48_alembic.py` -> 33 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade 0001_baseline:head --sql` still renders the DDL (now the queue table carries `next_attempt_at`/`last_checked_at`/`check_attempts`). New/updated tests cover: the selector filters on `next_attempt_at <= now()`; a no-evidence check defers with a queue-only backoff UPDATE (future `next_attempt_at`, `check_attempts+1`, still `open`, no `app.jobs` write); `run_reconciliation_resolution(max_batches=None)` deferring a record exactly once and then terminating because it is no longer due (a fake that MODELS the SQL due-filter, not a fake-empty-batch termination claim); and a structural assertion that termination rests on both the due-filter and the forward backoff. **PostgreSQL runtime remains NOT RUN** — these are static/fake-session control-flow checks, not proof that PostgreSQL evaluates `now()` / `make_interval` / the due-filter as modeled.

### Review fix — round 7 (2026-07-31)

- **Finding 1 — revision immutability: the reconciliation polling/backoff columns were edited into an already-published revision.** Round 6 added `next_attempt_at` / `last_checked_at` / `check_attempts` directly to `0002_expand_lease` (where `app.job_lease_reconciliation` is created). An applied Alembic revision is immutable: editing `0002` would not add those columns to any database that already ran `0002` (or `0003`), and `run_reconciliation_resolution()` would then fail at runtime on an undefined column. Fix (default safe path — we do NOT assume `0002` was never applied): `0002` is restored to its published form (queue table WITHOUT the polling columns), and a NEW **additive** revision `0003b_add_reconciliation_polling` adds them forward with `ALTER TABLE app.job_lease_reconciliation ADD COLUMN ...` (`next_attempt_at timestamptz NOT NULL DEFAULT now()`, `last_checked_at timestamptz`, `check_attempts integer NOT NULL DEFAULT 0`, `CHECK (check_attempts >= 0)`) plus a partial due-index `ix_job_lease_reconciliation_due ON (next_attempt_at) WHERE resolution_status='open'`. The `NOT NULL DEFAULT now()` DDL default gives every existing open row an immediately-due `next_attempt_at` — a real initial value from `ADD COLUMN`, not a fabricated Lease/owner/terminal/Provider outcome and not a separate data-backfill loop (none lives in the `upgrade()`).
- **Revision graph / rollout.** `0002` and `0003` are treated as possibly-applied (immutable); `0004`/`0005` are not applied on any real DB (you cannot VALIDATE before Backfill, and Backfill needs `0003b`'s columns), so `0004_validate_lease.down_revision` is safely rewired `0003_add_lease_constraints` -> `0003b_add_reconciliation_polling`. Chain stays single-head + linear: `0001 -> 0002 -> 0003 -> 0003b -> 0004 -> 0005` (no second head, no merge). `0003b` is placed after `0003` and before `0004` so the resolver has its columns during the Backfill phase without needing VALIDATE first, and it only touches the independent queue table (never `app.jobs`). The runbook adds the three upgrade paths (new DB; DB already at Expand/strict-constraint; deploy `0003b` before starting the resolver) and how to confirm `alembic_version` / schema columns / the revision graph in real PostgreSQL.
- These fixes grew the static/offline suite from 33 to **37** (`pytest -q test_day48_alembic.py` -> 37 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade 0001_baseline:head --sql` still renders the DDL (now the queue table is created bare in `0002` and the polling columns + due-index are added in `0003b`). New/updated tests: EXPECTED_CHAIN includes `0003b` (single head, linear); `0002` no longer contains the polling DDL; `0003b` is ADD COLUMN only (no CREATE TABLE, no `ALTER TABLE app.jobs`, all three columns + CHECK + partial index, `down_revision=0003`); `0004` follows `0003b`; the resolver's column names match the `0003b` DDL and are absent from `0002`; and an explicit honesty assertion. **PostgreSQL runtime remains NOT RUN** — static/fake-session checks are not proof that PostgreSQL applied `0003b`, evaluated `now()`/`make_interval`, or used the partial index.

### Review fix — round 8 (2026-07-31)

- **Finding 1 — the rollout path did not cover databases already at 0004 or 0005.** Round 7 inserted `0003b_add_reconciliation_polling` and rewrote `0004_validate_lease.down_revision` to point at it. That is only correct if `0004`/`0005` were never applied — which the repository cannot prove. If a real database is recorded at `0004` or `0005`, rewriting a historical `down_revision` does NOT make Alembic go back and run the inserted revision, so the polling columns would never be added and `run_reconciliation_resolution()` would fail on undefined columns. Fix (append-only, no history rewrite): `0003b` is removed and `0004_validate_lease.down_revision` is restored to `0003_add_lease_constraints`. The polling columns are added by a FORWARD, additive **branch** revision `0006_add_reconciliation_polling` (`down_revision = 0003_add_lease_constraints`; `ALTER TABLE app.job_lease_reconciliation ADD COLUMN next_attempt_at/last_checked_at/check_attempts` + `CHECK (check_attempts >= 0)` + the partial due-index — identical DDL to before), and a no-DDL **merge** revision `0007_merge_reconciliation_polling` (`down_revision = (0005_contract_legacy, 0006_add_reconciliation_polling)`) restores a single head. Every published revision (`0002`/`0003`/`0004`/`0005`) keeps its ORIGINAL parentage.
- **Why a branch + merge (not a linear append after 0005).** The reconciliation resolver runs during the Backfill phase, BEFORE Validate (`0004`). A pure linear append after `0005` would force a database still at `0003` to run Validate + Contract before it could obtain the polling columns — the exact ordering bug to avoid (and Validate would correctly fail while running-without-Lease rows remain). Branching `0006` off `0003` lets a `0003`-stage database reach the polling schema WITHOUT Validate/Contract; databases already at `0004`/`0005` can also apply `0006` (their applied set already contains `0003`). The runbook adds a four-state **upgrade matrix** (new DB; `0003`; `0004`; `0005`), a WARNING against a blind `upgrade head` on a `0003` DB, the runtime-deployment order (resolver only after `0006`), and the `alembic_version` / `information_schema.columns` / `alembic heads`/`history` checks for real PostgreSQL.
- These fixes moved the static/offline suite from 37 to **40** (`pytest -q test_day48_alembic.py` -> 40 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3) and the offline `alembic upgrade 0001_baseline:head --sql` still renders the DDL (now via the `0006` branch + `0007` merge). New/updated tests: single head `0007` with `0006` branching off `0003` and the merge naming both tips; every published revision keeps its original parent (no history rewrite); the `0006` branch is reachable from `0003` WITHOUT `0004`/`0005` in its ancestry; the merge performs no DDL; the resolver's columns match the `0006` DDL; and the forward revision is reachable from the previously-published head `0005`. **PostgreSQL runtime remains NOT RUN** — static/fake-session checks are not proof that PostgreSQL applies the branch/merge or evaluates the DDL as modeled.

### Added

- Added `docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day47->Day48 mental-model evolution; verbatim student answers preserved, including the "不知道" (stamp / new-vs-existing database / failure drill) and the taught final synthesis the student requested via "你帮我回答吧").
- Added the Day48 engineering artifact inside the existing project (no new project directory): `projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md` plus a **runnable, executed** Alembic control plane `projects/ai-backend-data-layer/api/day48_alembic/` (a minimal `env.py` + `script.py.mako` + a linear `0001_baseline`/`0002_expand_lease` (columns only)/`0003_add_lease_constraints`/`0004_validate_lease`/`0005_contract_legacy` chain for the Lease evolution of `app.jobs`), an operational restartable backfill `projects/ai-backend-data-layer/api/day48_lease_backfill.py` (`FOR UPDATE SKIP LOCKED`, kept OFF the migration), and static tests `projects/ai-backend-data-layer/api/test_day48_alembic.py`.
- Added scoped pinned dependencies `projects/ai-backend-data-layer/api/requirements-day48.txt` (alembic==1.13.1, sqlalchemy[asyncio]==2.0.29, pytest==7.4.3, psycopg2-binary for offline DDL rendering).

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day48 increment (contents table, run/render instructions, what-it-does-not-do, a Day48 evidence matrix showing the executed static/offline evidence and the PostgreSQL-runtime NOT-RUN boundary, and new `api/` entries); demoted Day47 to the prior increment.
- Appended a Day48 quick-reference to `cheat_sheets/fastapi.md` (Expand/Backfill/Validate, Switch/Contract/graph/evidence, weak-vs-strong) and Day48 questions to `interview/fastapi.md` (with the student's verbatim answers and the taught model answers).
- Updated `docs/README.md` (Day48 is the latest FastAPI lesson), and pointed the Day47 lesson's Next Lesson at the released Day48 lesson.
- Updated `CURRICULUM.md` (Day48 marked Completed with its released lesson/artifact/tests and honest static-offline-vs-NOT-RUN limits; Phase 4 In Progress; Day49-Day100 remain Planned) and `ROADMAP.md` (Day48 Completed).
- Updated `PROJECT_STATUS.md` (Day48 last completed with artifact + validation boundary; Current/Next = Day49 Planned; Day48 learning-progress narrative) and `TASKS.md` (completed Day48 blocks, Day48 preparation converted to history, Day49 preparation added; Current Phase marker set to Day48 completed) and `AGENTS.md`.

### Notes

- Day48 makes Day36's **Expand -> Backfill -> Validate -> Switch -> Contract** discipline **executable with Alembic** over the Day46 mapping and Day47 boundary, for a Lease-ownership evolution of `app.jobs`. A migration is a **versioned transition across schema + historical rows + every deployed writer**, so `alembic upgrade head` success is **DDL-on-one-database evidence only**. **Expand** adds the Lease columns **nullable with no fabricated default** (NULL = no proved ownership; historical Lease is never fabricated) plus a coherence `CHECK ... NOT VALID` that protects **future** writes while tolerating legacy rows, deployed first so old Workers coexist, with **no** Backfill loop / Provider call / long transaction in `upgrade()`. **Backfill** is a **separate operational, restartable** step (short tx + `FOR UPDATE SKIP LOCKED`, idempotent, DB state = checkpoint) filling only running Jobs with trusted ownership and sending unknowns to reconciliation; queued/terminal get no Lease. **`VALIDATE CONSTRAINT`** is a **separate** revision that proves history and fails until legacy violations are truly resolved. **Switch** means every Writer uses the token protocol and the old path can no longer write (not merely a new binary). **Contract** is destructive and last, after evidence and an observation period; once real Lease data or Provider side effects exist the recovery is **forward-fix + reconciliation, not a destructive downgrade**. Alembic is a **deployment control plane** (minimal `env.py`, no FastAPI startup migration, no Day47 UoW); `revision`/`down_revision` define the graph; parallel revisions need a **merge** revision; **`stamp`** writes `alembic_version` and does no DDL; `autogenerate` is a candidate diff to review; and `CREATE INDEX CONCURRENTLY` is non-transactional. Provider/Object Storage are outside DB transactions and the **Outbox row is dispatch intent, not Provider-success proof** (Day50/Day55 future).

### Validation

- **Day48 has REAL executed STATIC/OFFLINE evidence.** Dependencies are pinned in `projects/ai-backend-data-layer/api/requirements-day48.txt`. Executed: `python3 -m pip install -r requirements-day48.txt`; `python3 -m py_compile day48_lease_backfill.py test_day48_alembic.py` passed; `python3 -m pytest -q test_day48_alembic.py` -> **22 passed** (Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3); and `python3 -m alembic -c day48_alembic/alembic.ini upgrade 0001_baseline:head --sql` **rendered** the Expand/Validate/Contract DDL with **no database connection**. The tests inspect the Alembic revision graph + migration source via `ScriptDirectory` (single head `0005_contract_legacy`; linear `0005->0004->0003->0002->0001->None`; pure Expand (columns only) with the strict constraints in a separate revision; Validate separate; Contract destructive+gated; no loop in any `upgrade()`/`downgrade()`; minimal `env.py`) and exercise the fake-session backfill control flow (`FOR UPDATE SKIP LOCKED`; fills known, skips unknown for reconciliation; idempotent guarded write; no Provider). These prove migration **text/structure + control flow**, NOT database behavior.
- **PostgreSQL runtime is NOT RUN.** No PostgreSQL server was available. A real runtime test would apply the independent Day42 raw SQL (`sql/001_create_jobs.sql` + `sql/003_relational_modeling_and_data_integrity.sql`) to a disposable PostgreSQL, create a legacy row that violates the future rule, apply Expand, prove the old row survives, prove a new illegal write is rejected, and prove `VALIDATE` fails until the legacy violation is repaired/reconciled. **SQLite, fake sessions, and static/offline checks are NOT PostgreSQL proof**, and `alembic upgrade` success alone does not prove Backfill, Switch, Contract, or production safety. FastAPI/Worker drain integration, real Provider, Object Storage, and production migration are all **NOT RUN**.
- Other validation performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day49+ lesson exists and Day49-Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order/heading check; Markdown fence balance; relative-link resolution (new `api/` artifact links and the Day47->Day48 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, credentials, or database URLs — the `alembic.ini` URL is a non-credential placeholder used only for offline SQL rendering). The student answers were transcribed verbatim from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- Scope: the Day49 upload workflow, Day50 real Outbox/Celery delivery, Day53 Provider SDK, and Day55 worker runtime are named only as future connections; no real Provider/Object-Storage/FastAPI/Worker-drain/production evidence was fabricated; the Lease scenario reuses the Day46 mapping without redefining schema authority; no migration runs on FastAPI startup, no Provider is called in Backfill, and no long Backfill loop lives in `upgrade()`; the protected prompt/template files are unchanged; no new project directory was created; and Day49-Day100 curriculum planning was not altered.

---

## v0.1.94 — Day47 Async Sessions, Transactions, Repository and Unit of Work

Date: 2026-07-31

### Review fix (2026-07-31)

- **Completion is now the Day33 atomic pack (one commit).** `complete_job()` previously updated only the Job and appended `job_succeeded`. It now performs, in ONE UoW/commit: a guarded finish of the Attempt (`UPDATE app.job_attempts SET finished_at=now() WHERE attempt_id AND job_id AND finished_at IS NULL RETURNING` — zero rows = rollback/stale-no-op, never overwriting a finished Attempt), the guarded `running -> succeeded` Job transition (zero rows = rollback, no Artifact/Event), a Day46 `ResultArtifact` durable reference (Object Storage `object_key`, never bytes), and the `job_succeeded` Event. Any zero-row guard or any failed step (Artifact/Event) rolls the WHOLE UoW back — no partial PostgreSQL durable state — and the external Artifact bytes remain outside the transaction (a DB rollback does not delete the external object). New repositories: `AttemptRepository.finish()` (guarded) and `ArtifactRepository.create()`; the UoW now exposes `uow.artifacts`.
- **Correlation-key API de-misleading.** `AttemptRepository.create(..., correlation_key=...)` accepted a key it never persisted. Day46 defines no correlation column on `JobAttempt`, so the parameter and its misleading docstring were removed; the application-generated correlation/idempotency key is written by the higher-level start flow into the `job_started` Event metadata in the same UoW (no new Day46 column/migration invented).
- These fixes grew the fake-session suite from 13 to **17** (`pytest -q test_day47_async_uow.py` -> 17 passed; Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3). New/updated tests cover: the full completion pack in one commit; a stale/already-finished Attempt (no Job success/Artifact/Event, rollback+close); a stale Job (no Artifact/Event, rollback+close); an Artifact insert failure and a success-Event append failure (rollback+close, no commit); and the correlation key living in the `job_started` Event metadata. These remain FAKE-SESSION control-flow tests — **PostgreSQL runtime is still NOT RUN** (a mock is not database proof; SQLite is not PostgreSQL evidence).

### Review fix — tenant predicate + Provider evidence (2026-07-31)

- **Tenant ownership predicate on every `app.jobs` guard.** `guarded_claim`, `guarded_complete`, and `mark_failed` now take an explicit `tenant_id` and add `AND tenant_id = :tenant_id` to the guarded `UPDATE`. `start_job(..., tenant_id=...)` and `complete_job(..., tenant_id=...)` pass it from the orchestration — `tenant_id` is trusted durable-ownership context (Day42/Day46), NOT derived from the job_id, and a job_id alone is not an authorization boundary. A wrong tenant matches 0 rows: the claim is a stale/no-op, and a wrong-tenant completion rolls back with NO ResultArtifact and NO success Event. This is the existing durable tenant predicate only — NOT Day52 authentication/authorization.
- **Provider evidence in the completion pack.** `AttemptRepository.finish()` now records `provider_request_id` and `cost_micros` alongside `finished_at` in the SAME guarded statement (guard `attempt_id AND job_id AND finished_at IS NULL` preserved), and `complete_job()` accepts optional `provider_request_id`/`cost_micros`. Either may be `None` when unknown (written as NULL — a None does NOT assert a verified value). The completion atomic pack is now: guarded Attempt finish (with Provider evidence) -> tenant-scoped guarded Job transition -> ResultArtifact reference -> `job_succeeded` Event -> one commit. `FakeProvider` gained optional `provider_request_id`/`cost_micros` fields (no network I/O; not a real SDK).
- These fixes grew the fake-session suite from 17 to **23** (`pytest -q test_day47_async_uow.py` -> 23 passed; Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3). New/updated tests assert every Job mutation binds `tenant_id` (distinct from job_id), a wrong-tenant claim is a stale/no-op, a wrong-tenant completion writes no Artifact/Event and rolls back, and completion binds `provider_request_id`/`cost_micros` into the guarded Attempt finish (and None when unknown). Still FAKE-SESSION control-flow only — **PostgreSQL runtime, real Provider, integration, and production are NOT RUN.**

### Added

- Added `docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day46->Day47 mental-model evolution; verbatim student answers preserved, including the three English "不知道" answers and every classroom correction).
- Added the Day47 engineering artifact inside the existing project (no new project directory): `projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md` plus **runnable, executed** code `projects/ai-backend-data-layer/api/day47_async_uow.py` and fake-session tests `projects/ai-backend-data-layer/api/test_day47_async_uow.py` — process-scoped `create_engine`/`create_session_factory` helpers, `JobRepository`/`AttemptRepository`/`EventRepository`, a `UnitOfWork` with explicit commit/rollback/close, the guarded `UPDATE ... WHERE job_status='queued' RETURNING` claim (zero-row stale/no-op), `flush`-before-dependent-write, `start_job`/`complete_job` short guarded UoWs, and a `FakeProvider` seam with `ProviderUnknownOutcome`. It reuses the Day46 mapping (`day46_orm_mapping`) and defines no global Session, no repository-owned commit, and no Provider call inside a DB transaction.
- Added scoped pinned dependencies `projects/ai-backend-data-layer/api/requirements-day47.txt` (sqlalchemy[asyncio]==2.0.29, pytest==7.4.3) for the recorded repository fake-session test evidence.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day47 increment (contents table, run instructions, what-it-does-not-do, a Day47 evidence matrix showing the executed fake-session evidence and the PostgreSQL-runtime NOT-RUN boundary, and new `api/` code/test/requirements entries); demoted Day46 to the prior increment.
- Appended a Day47 quick-reference to `cheat_sheets/fastapi.md` (scope/ownership, repository/UoW/lifecycle, guarded claim/completion/Provider boundary, reads/evidence, weak-vs-strong) and Day47 questions to `interview/fastapi.md` (with the student's verbatim answers and strong spoken answers).
- Updated `docs/README.md` (Day47 is the latest FastAPI lesson), and pointed the Day46 lesson's Next Lesson at the released Day47 lesson.
- Updated `CURRICULUM.md` (Day47 marked Completed with its released lesson/artifact/tests and honest fake-session-vs-NOT-RUN limits; Phase 4 In Progress; Day48-Day100 remain Planned) and `ROADMAP.md` (Day47 Completed).
- Updated `PROJECT_STATUS.md` (Day47 last completed with artifact + validation boundary; Current/Next = Day48 Planned; Day47 learning-progress narrative) and `TASKS.md` (completed Day47 blocks, Day47 preparation converted to history, Day48 preparation added; Current Phase marker set to Day47 completed) and `AGENTS.md`.

### Notes

- Day47 drives the faithful Day46 mapping through SHORT, isolated async database units of work — PostgreSQL stays the durable authority (**Day46 maps it, Day47 drives it transactionally, Day48 evolves it**). The `AsyncEngine` and `async_sessionmaker` are **process-scoped** (one Engine per process via a lifespan / Worker startup composition root, not one per deployment); the `AsyncSession` is **request/Job-scoped** and never global/shared (it carries identity-map/pending/transaction state), so each request or Job gets a **fresh Unit of Work = one isolated Session + repositories**, and the **factory** is shared, not the Session. Repositories express DB operations on the UoW-injected Session and never commit/close; the **UoW** owns the one Session, does **explicit** `await uow.commit()` (no silent auto-commit, so a stale/failed branch cannot accidentally commit), rolls back on exception/uncommitted exit, and always closes. The atomic start is one short UoW: a guarded `UPDATE ... WHERE job_status='queued' RETURNING` (a single statement, not SELECT-then-UPDATE) where **one row = claimed and zero rows = a normal stale/no-op** (create no Attempt/Event, not a retryable DB error), then Attempt 1 with an **application-generated correlation/idempotency key**, `flush` for the server-generated id to write the dependent `job_started` Event without committing, and a single commit. `flush` executes SQL in the current transaction but is not durable or cross-session visible; an `IntegrityError` aborts the transaction (integrity protected, not broken) and needs a rollback; a **commit exception is an unknown outcome** (roll back/close, reload by stable id via a new Session, do not replay). The long/paid **Provider call runs outside any DB transaction** (the DB cannot roll back its execution/charges/side effects), the correlation key is committed **before** it, and completion is a **second short guarded UoW**; guarded completion is concurrency control (one still-valid running writer), distinct from the Day46 `jobs_succeeded_has_finished_at` CHECK (a state invariant). A definitive failure becomes `failed`; a timeout with unknown remote outcome is a **first-class recovery state**, never blindly requeued. Reads build an allowlisted Day44 Pydantic DTO **inside** the UoW (a detached ORM object would raise `DetachedInstanceError` on lazy load). The integrated drill shows code rollback is not durable-data or external-side-effect rollback.

### Validation

- **Day47 has REAL executed FAKE-SESSION control-flow evidence.** Dependencies are pinned in `projects/ai-backend-data-layer/api/requirements-day47.txt` (sqlalchemy[asyncio]==2.0.29, pytest==7.4.3). Executed: `python3 -m pip install -r requirements-day47.txt`; `python3 -m py_compile day47_async_uow.py test_day47_async_uow.py` passed; `python3 -m pytest -q test_day47_async_uow.py` -> **23 passed** (Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3). The 23 tests verify UoW/repository **control flow** with a FAKE AsyncSession (explicit commit, rollback+close on exception/uncommitted exit, zero-row stale/no-op claim and completion, flush-before-dependent-write, repositories never commit, one shared Session per UoW, a fresh Session per UoW, commit-exception rollback+close, Provider unknown-outcome propagation, guarded mark_failed). **A mock is NOT database proof.**
- **PostgreSQL runtime is NOT RUN.** No PostgreSQL server / async driver was available. A real runtime test would apply the independent Day42 raw SQL (`sql/001_create_jobs.sql` + `sql/003_relational_modeling_and_data_integrity.sql`) to a disposable PostgreSQL, force a failing UoW, then open a **new** verification Session and assert the Job remains queued with no Attempt/Event. **SQLite is NOT PostgreSQL evidence** for this app-schema/PostgreSQL-typed contract. FastAPI/Worker integration, concurrent Workers, real Provider SDK/network, Object Storage, and production are all **NOT RUN**.
- Other validation performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day48+ lesson exists and Day48-Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order/heading check; Markdown fence balance; relative-link resolution (new `api/` code/test cross-links, the Day42 SQL link, and the Day46->Day47 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, database URLs, provider keys, signed URLs, or customer data). The student answers were transcribed verbatim from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- Scope: Alembic migrations (Day48), the upload workflow (Day49), idempotent acceptance/Outbox (Day50), real Provider SDK (Day53), Celery (Day55), and FastAPI/Worker integration/production are named only as future connections; no real Provider/Object-Storage/FastAPI/Worker-concurrent/production evidence was fabricated; the Day46 mapping is reused without schema redefinition, `create_all()`-as-compatibility, TEXT+CHECK->enum change, or a destructive cascade; the protected prompt/template files are unchanged; no new project directory was created; and Day48-Day100 curriculum planning was not altered.

---

## v0.1.93 — Day46 SQLAlchemy 2.0 Mapping for the Day42 Data Model

Date: 2026-07-30

### Review fix (2026-07-30)

- **ORM delete semantics (parent -> child):** the parent-side navigation relationships (`Job.attempts`, `Job.events`, `Job.outbox_events`, `JobAttempt.result_artifacts`) now set `passive_deletes="all"`. Without it, a future ORM parent delete would try to emit a pre-delete `UPDATE` setting each loaded child's foreign key to `NULL` before deleting the parent — but those child FKs are `NOT NULL`, and that behavior moves the decision out of the database. `passive_deletes="all"` makes the ORM emit **no** pre-delete UPDATE/DELETE on children, so PostgreSQL's `ON DELETE RESTRICT` stays the **final** delete decision and rejects the parent delete. This is **not** a cascade — no `delete`/`delete-orphan` was added (cascade stays `save-update, merge`), the Day42 raw SQL is unchanged, and no Engine/Session/transaction/migration was introduced. A new static test asserts `passive_deletes == "all"` and the absence of any delete cascade on those four relationships, growing the suite from 19 to **20** (`pytest -q test_day46_orm_mapping.py` -> 20 passed; Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3). PostgreSQL runtime remains **NOT RUN** (the RESTRICT rejection itself is a database behavior, still not executed here).

### Added

- Added `docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day45->Day46 mental-model evolution; verbatim student answers preserved, including the "不知道" responses and the initial new-authority/Attempt-uniqueness/single-FK/global-session/CHECK-test misconceptions).
- Added the Day46 engineering artifact inside the existing project (no new project directory): `projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md` plus **runnable, executed** code `projects/ai-backend-data-layer/api/day46_orm_mapping.py` and static tests `projects/ai-backend-data-layer/api/test_day46_orm_mapping.py` — a faithful SQLAlchemy 2.0 typed declarative mapping (`DeclarativeBase` + `MetaData(schema="app")`, `Mapped[T] = mapped_column(...)`, PostgreSQL `UUID`/`JSONB`, server-side defaults) of the Day42 `app`-schema durable contract: Job, JobAttempt, JobEvent, OutboxEvent, UploadSession, ResultArtifact, plus a minimal Tenant support stub, preserving named UNIQUE/CHECK/FK constraints, ON DELETE RESTRICT, TEXT+CHECK status (not a native enum), Job-scoped attempt uniqueness, and the same-Job composite provenance FK, with `relationship()` as navigation only and Pydantic public models kept separate.
- Added scoped pinned dependencies `projects/ai-backend-data-layer/api/requirements-day46.txt` (sqlalchemy==2.0.29, pytest==7.4.3) for the recorded repository static test evidence.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day46 increment (contents table, run instructions, what-it-does-not-do, a Day46 evidence matrix showing the executed static metadata evidence and the PostgreSQL-runtime NOT-RUN boundary, and new `api/` code/test/requirements entries); demoted Day45 to the prior increment.
- Appended a Day46 quick-reference to `cheat_sheets/fastapi.md` (authority-vs-mapping, typed declarative mapping, constraints/integrity, boundaries/scope/evidence, weak-vs-strong) and Day46 questions to `interview/fastapi.md` (with the student's verbatim answers and strong spoken answers).
- Updated `docs/README.md` (Day46 is the latest FastAPI lesson), and pointed the Day45 lesson's Next Lesson at the released Day46 lesson.
- Updated `CURRICULUM.md` (Day46 marked Completed with its released lesson/artifact/tests and honest static-vs-NOT-RUN limits; Phase 4 In Progress; Day47-Day100 remain Planned) and `ROADMAP.md` (Day46 Completed).
- Updated `PROJECT_STATUS.md` (Day46 last completed with artifact + validation boundary; Current/Next = Day47 Planned; Day46 learning-progress narrative) and `TASKS.md` (completed Day46 blocks, Day46 preparation converted to history, Day47 preparation added; the Current Phase marker set to Day46 completed) and `AGENTS.md`.

### Notes

- Day46 is a **faithful executable mapping** of the existing Day42 PostgreSQL durable contract — **the ORM mapping represents the database contract; it does not silently replace it**. PostgreSQL stays the durable authority; **Day46 maps it, Day47 drives it transactionally, Day48 evolves it safely.** A `DeclarativeBase` with `MetaData(schema="app")` pins the exact existing table identity; `Mapped[T] = mapped_column(...)` declares typed columns; database-generated values are **server-side** defaults (`gen_random_uuid()`/`now()`/`'queued'`/`0`/`false`/`'{}'::jsonb`). The mapping preserves the named constraints exactly — `jobs_tenant_idempotency_unique` `UNIQUE(tenant_id, idempotency_key)` (Day50 acceptance workflow deferred), `jobs_status_allowed` CHECK (status stays **TEXT + CHECK**, not a native enum, which would be Day48 evolution), and `jobs_succeeded_has_finished_at` CHECK (a nullable `Mapped[datetime | None]` allows NULL but does **not** enforce the conditional rule — the CHECK does, and a negative constraint test expects a **rejected write / IntegrityError**, not an empty result). JobAttempt retry ordinal is **Job-scoped** via `UNIQUE(job_id, attempt_number)` (not tenant-scoped, not global — Job B may reuse Attempt 1), and JobEvent proves same-Job provenance via a **composite FK** `(job_id, attempt_id)` where a NULL `attempt_id` records a Job-level event. `ON DELETE RESTRICT` is preserved on every FK and **no** cascade/delete-orphan is introduced (audit/recovery evidence must survive; `relationship()` is navigation only). Pydantic public models and the ORM persistence models remain **separate** and neither proves PostgreSQL constraint behavior. OutboxEvent is PostgreSQL-owned dispatch intent (`published_at IS NULL` = checkpoint not recorded, not "never sent" — at-least-once), ResultArtifact stores `attempt_id` only (ownership derived through the Attempt), and UploadSession/ResultArtifact store Object Storage **references**, not bytes. Day46 creates **no** global Engine/AsyncSession (Day47 owns one Engine per process and one session per request/Job), keeps `tenant_id` an explicit mapped column/FK via a minimal Tenant stub, and states Document/`job_documents` as an explicit unimplemented limitation. The wrong-schema failure/reconciliation drill rolls back the bad mapping/release for future writes (code rollback **!=** durable-data rollback), preserves/classifies correlation evidence (most importantly whether the client was already responded to), and reconciles the mis-placed rows through an audited, idempotent process.

### Validation

- **Day46 has REAL executed STATIC metadata-contract evidence.** Dependencies are pinned in `projects/ai-backend-data-layer/api/requirements-day46.txt` (sqlalchemy==2.0.29, pytest==7.4.3). Executed: `python3 -m pip install -r requirements-day46.txt`; `python3 -m py_compile day46_orm_mapping.py test_day46_orm_mapping.py` passed; `python3 -m pytest -q test_day46_orm_mapping.py` -> **20 passed** (Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3). The 20 tests assert the **declared mapping STRUCTURE** against `Base.metadata` (app-schema identity, typed columns, server defaults, named UNIQUE/CHECK/FK constraints, ON DELETE RESTRICT on every FK, the composite provenance FK, TEXT+CHECK not enum, no cascade delete, ORM/Pydantic separation, the Tenant stub, and the documents/job_documents limitation). **NO database connection and NO `create_all()` were used.**
- **PostgreSQL runtime is NOT RUN.** No PostgreSQL server was available in this environment. A real runtime test would first apply the independent Day42 raw SQL (`sql/001_create_jobs.sql` + `sql/003_relational_modeling_and_data_integrity.sql`) to a fresh database, then assert actual behavior — a rejected duplicate `(tenant_id, idempotency_key)`, a rejected succeeded Job without `finished_at`, an accepted Job B reusing `attempt_number = 1` — i.e. a **rejected write**, not an empty result. `create_all()` success would **not** be schema-compatibility evidence. AsyncSession/transactions/repository/UoW (Day47), Alembic migrations (Day48), Celery/Provider/Object-Storage runtime, integration, and production are all **NOT RUN**.
- Other validation performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day47+ lesson exists and Day47-Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order/heading check; Markdown fence balance; relative-link resolution (new `api/` code/test cross-links, the Day42 SQL links, and the Day45->Day46 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, credentialed URLs, or large bytes). The student answers were transcribed verbatim (typos preserved) from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- Scope: AsyncSession/transactions/repository/UoW (Day47), Alembic migrations (Day48), Outbox acceptance (Day50), real Provider SDK (Day53), Celery (Day55), and retries/rate-limits/cost/backpressure (Day56) are named only as future connections; no native-enum change, session/transaction, migration, Celery transport, real Provider call, Object Storage runtime, or public API endpoint was implemented; Document/job_documents remain an explicit unimplemented mapping limitation; the protected prompt/template files are unchanged; no new project directory was created; and Day47-Day100 curriculum planning was not altered.

---

## v0.1.92 — Day45 Dependency Injection, Lifespan, Configuration and AI Provider Adapters

Date: 2026-07-29

### Review fixes (2026-07-30)

- **Safe logging:** `Settings.safe_log_fields()` no longer emits `provider_base_url` (which can carry userinfo, an internal host/port, or a private endpoint path). It now emits only allowlisted, non-sensitive labels — `provider_name`, `provider_model`, `request_timeout_s`, `settings_version` — with the API key redacted; a new test asserts sensitive base-URL parts never appear in the log fields.
- **HTTP route anti-pattern:** the HTTP route no longer runs a Provider generation. `GET /provider/status` only resolves the Provider via `Depends` (short boundary); the actual Provider call + Day44 validation + illustrative completion moved into an explicit worker-style `WorkerJobRunner` harness, so the example never implies a FastAPI Router executes a long Provider Job.
- **Adapter error translation:** `OpenAICompatibleAdapter` now actually maps timeout/429/401-403/connection faults to stable `Provider*` errors over an injected transport (no real network), matching the documentation; with no transport injected it raises `NotImplementedError` (the real SDK/network is Day53).
- **Override test:** the dependency-override test now verifies behavior changes under the override and that clearing it restores the original lifespan wiring in a fresh lifecycle (not merely an empty override dict).
- **Cancellation safety (P1):** `OpenAICompatibleAdapter.generate()` now catches `asyncio.CancelledError` first and re-raises it unchanged (only genuine `Exception` vendor/transport faults are classified). In Python 3.10 `CancelledError` subclasses `BaseException`, so the previous `except BaseException` wrongly translated a cooperative Worker drain/shutdown cancellation into `ProviderTransport`, corrupting cancellation semantics and risking spurious failure handling/retries. A new deterministic no-network test asserts an injected transport raising `asyncio.CancelledError` propagates unchanged (not a `Provider*` error).
- These fixes grew the executed suite from 12 to **20 tests** (`pytest -q test_day45_composition.py` -> 20 passed; Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3). NOT RUN is unchanged: real Provider/network/SDK, PostgreSQL/SQLAlchemy, Celery/Redis, deployment/Secret rotation/drain/production; Day46/47/53/55/56 remain future scope.

### Added

- Added `docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day44->Day45 mental-model evolution; verbatim student answers preserved, including the "不知道" responses).
- Added the Day45 engineering artifact inside the existing project (no new project directory): `projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md` plus **runnable, executed** code `projects/ai-backend-data-layer/api/day45_composition.py` and tests `projects/ai-backend-data-layer/api/test_day45_composition.py` — validated secret-aware `Settings` (with `SecretStr`), a small `AIProvider` protocol, a production `OpenAICompatibleAdapter` + `FakeAIProvider` seam with stable `ProviderError` types, `create_app` + a lifespan `Container` (Settings + async HTTP client + ProviderAdapter) that closes in reverse order, `get_provider`, a stateless per-request `JobService`, a worker-style `WorkerJobRunner` (the Provider call + Day44 `StructuredAIResult.model_validate_json` validation + illustrative in-memory completion run off the HTTP path; a short `GET /provider/status` route only resolves the Provider via `Depends`), an `OpenAICompatibleAdapter` that translates timeout/429/401-403/connection faults to stable `Provider*` errors over an injected transport (no real network; `NotImplementedError` without one — real SDK is Day53), and `Settings.safe_log_fields()` that emits only allowlisted non-sensitive labels (never the `provider_base_url`).
- Added scoped pinned dependencies `projects/ai-backend-data-layer/api/requirements-day45.txt` (pydantic==2.5.0, pytest==7.4.3, fastapi==0.110.0, httpx==0.27.0) for the recorded repository test evidence.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day45 increment (contents table, run instructions, what-it-does-not-do, a Day45 validation matrix showing the executed local fake-runtime evidence, and new `api/` code/test/requirements entries); demoted Day44 to the prior increment.
- Appended a Day45 quick-reference to `cheat_sheets/fastapi.md` (ownership/scopes, Settings/secrets, lifespan/partial-init/adapter seam, test composition/rotation/drain, weak-vs-strong) and Day45 questions to `interview/fastapi.md` (with the student's verbatim "不知道" answers and the strong spoken answers).
- Updated `docs/README.md` (Day45 is the latest FastAPI lesson), and pointed the Day44 lesson's Next Lesson at the released Day45 lesson.
- Updated `CURRICULUM.md` (Day45 marked Completed with its released lesson/artifact/tests and honest RUN-vs-NOT-RUN limits; Phase 4 In Progress; Day46-Day100 remain Planned with the per-day connections unchanged) and `ROADMAP.md` (Day45 Completed).
- Updated `PROJECT_STATUS.md` (Day45 last completed with artifact + validation boundary; Current/Next = Day46 Planned; Day45 learning-progress narrative) and `TASKS.md` (completed Day45 blocks, Day45 preparation converted to history, Day46 preparation added; the Current Phase marker corrected to Day45 completed).

### Notes

- Day45 is the **composition boundary** that makes Day44's typed contracts runnable without letting Routers or business services own infrastructure. Resource ownership is **per-process**: only processes that call the Provider create a client (8 Worker processes hold 8 independent app-scoped clients; a Provider client owns HTTP connections/pools, not database connections, which are Day47). The **lifespan** owns expensive closeable app/process-scoped resources (validated `Settings`, an async HTTP client, and a concrete `ProviderAdapter`) and publishes a `Container` only after complete initialization, while `Depends()` **supplies** an already-created dependency (its default cache is request-local, not a cross-process singleton) so `get_provider` returns the lifespan-created `AIProvider` and a stateless `JobService` is created per request/Job. `Settings` is the validated secret/config boundary (the API key comes from validated Settings, never Router code and never a Job payload), where `SecretStr` reduces accidental display but is **not** memory encryption; startup **fails fast** on invalid local configuration (stay not ready, do not claim Jobs), local Settings validity **!=** external Provider availability, and a **paid** generation call must not be sent on startup to test a key. Import time declares types/routes only; `create_app()` is the explicit Composition Root; partial-initialization cleanup closes the already-created HTTP client, publishes no `Container`/readiness, and claims no Job (reverse-order close). `JobService` depends on a **small** `AIProvider` protocol (not a vendor SDK); the `OpenAICompatibleAdapter` translates vendor faults into stable `ProviderTimeout`/`ProviderRateLimited`/`ProviderAuthentication`/`ProviderTransport` errors — in Day45 demonstrated and tested over an **injected transport** with no real network (raising `NotImplementedError` when none is wired; the real SDK is Day53) — and a `FakeAIProvider` gives no-network/no-cost tests. HTTP acceptance stays short (the route only resolves the Provider via `Depends`); the (possibly long) Provider call runs in a **worker-style harness**, and the Worker Service validates raw Provider JSON via Day44 **before** any completion. `safe_log_fields()` logs only allowlisted non-sensitive labels and **never** the `provider_base_url` (which can carry userinfo/internal host/port/private endpoint path). Configuration rotation keeps Settings/Container immutable per process and uses controlled process replacement (start + verify new Workers ready -> then drain old -> bounded in-flight window -> close old -> verify), never draining healthy old before new is ready; graceful shutdown order is stop-new-claims -> drain -> close (never close first); an interrupted Provider call is not blindly requeued; and code/config rollback protects future executions while committed facts and interrupted calls need a separate idempotent, guarded, audited repair — code/config rollback **!=** database-history rollback.

### Validation

- **Day45 has REAL executed local runtime evidence with a FAKE no-network Provider.** Dependencies are pinned in `projects/ai-backend-data-layer/api/requirements-day45.txt` (pydantic==2.5.0, pytest==7.4.3, fastapi==0.110.0, httpx==0.27.0). Executed: `python3 -m pip install -r requirements-day45.txt`; `python3 -m py_compile day45_composition.py test_day45_composition.py` passed; `python3 -m pytest -q test_day45_composition.py` -> **20 passed** (Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3). Day44's suite still passes (`pytest -q test_day44_pydantic_contracts.py` -> 24 passed) under the same clean install.
- The completion target in the tests is an **in-memory list on `app.state`, NOT PostgreSQL**. **NOT RUN:** real Provider authentication/network/SDK compatibility; PostgreSQL/SQLAlchemy transactions and durable completion; Celery/Redis Worker behavior; deployment, Secret rotation, drain/recovery, or production validation. Boundary preserved: Pydantic/local-config validation != authentication != authorization != application invariants != PostgreSQL commit; local Settings validity != external Provider availability; `SecretStr` != encryption; code/config rollback != durable-fact repair.
- Other validation performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day46+ lesson exists and Day46-Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order/heading check; Markdown fence balance; relative-link resolution (new `api/` code/test cross-links and the Day44->Day45 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, and `docs/README.md`; and a secret scan (no real secrets, API keys, connection strings, or client data; the test uses an obviously-fake `sk-fake-...` placeholder that is asserted to be redacted/absent). The student answers were transcribed verbatim (typos preserved) from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- Scope: SQLAlchemy mapping (Day46), async sessions/transactions/unit-of-work (Day47), Outbox acceptance (Day50), a real Provider SDK (Day53), streaming/cancellation (Day54), Celery (Day55), and retries/rate-limits/cost/backpressure (Day56) are named only as future connections; the protected prompt/template files are unchanged; no new project directory was created; and Day46-Day100 curriculum planning was not altered.

---

## v0.1.91 — Day44 Pydantic v2 and Structured AI Input/Output Contracts

Date: 2026-07-26

### Added

- Added `docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day43->Day44 mental-model evolution).
- Added the Day44 engineering artifact inside the existing project (no new project directory): `projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md` plus **runnable, executed** code `projects/ai-backend-data-layer/api/day44_pydantic_contracts.py` and tests `projects/ai-backend-data-layer/api/test_day44_pydantic_contracts.py` — the boundary ladder (JSON-valid -> Pydantic-valid -> authenticated -> authorized -> app invariants -> PostgreSQL constraint + tx -> committed truth), the request discriminated union (summarize/extract_structured), strict `MaxTokens`/`Confidence` aliases, the untrusted-Provider `StructuredAIResult`, status-discriminated public responses, the public error envelope, the `validate_provider_output_before_completion` gate, and the 37-Job `model_construct()` incident runbook.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day44 increment (contents table, run instructions, what-it-does-not-do, known gaps, new `api/` code/test structure entries, and a Day44 validation matrix showing the executed Pydantic runtime evidence); demoted Day43 to the prior increment.
- Appended a Day44 quick-reference to `cheat_sheets/fastapi.md` (boundary ladder, request models, strict types/Provider output, responses/error envelope, entry points/gate/incident, weak-vs-strong) and Day44 questions to `interview/fastapi.md` (with the student's verbatim answers, the final Chinese synthesis, and the three English stages).
- Updated `docs/README.md` (Day44 is the latest FastAPI lesson), and pointed the Day43 lesson's Next Lesson at the released Day44 lesson.
- Updated `CURRICULUM.md` (Day44 marked Completed with its released lesson/artifact/tests and honest RUN-vs-NOT-RUN limits; Phase 4 In Progress; Day45-Day100 remain Planned with topics and the 58 per-day connections unchanged) and `ROADMAP.md` (Day44 Completed).
- Updated `PROJECT_STATUS.md` (Day44 last completed with artifact + validation boundary; Current/Next = Day45 Planned), `TASKS.md` (completed Day44 blocks, Day44 preparation converted to history, Day45 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day44 makes the Day43 contract executable, and its spine is a **boundary ladder** where Pydantic occupies exactly one rung — declared structure — and does **not** prove authorization or a durable commit: JSON-valid -> Pydantic-valid -> authenticated -> authorized -> application invariants -> PostgreSQL constraint + atomic transaction -> committed durable truth. Client request models put `tenant_id` in trusted authentication context (never a request-body field, since a claimed body tenant_id is a cross-tenant authorization risk) and use `extra="forbid"` to reject undeclared input (a client-supplied `job_status`, `tenant_id`, or `unexpected_debug`); `max_tokens` is a required strict integer bounded `1..8000` (rejecting `"2000"`, `8001`, and a missing value); and the request is a discriminated union on `task_type` (summarize forbids `output_schema`; extract_structured requires a non-empty, type-restricted `output_schema`), with `upload_session_id`/public `job_id` as UUIDs (Day31) and `Citation.url` as `AnyHttpUrl` while `UNIQUE (tenant_id, idempotency_key)` + the transaction stay the concurrency/commit authority (Pydantic cannot detect cross-tenant upload ownership). Strict field-specific aliases (`MaxTokens`, `Confidence`) reject accidental coercion (`"2000"`, `"very sure"`) without enabling global strictness (JSON represents UUIDs/timestamps as strings), with any needed conversion in an explicit tested adapter. Provider output is fully untrusted input validated as `StructuredAIResult` (no Provider-owned `job_status`), where Pydantic validates citation/URL shape but not grounding/truth. Public responses are allowlisted and status-discriminated (queued/running have no result/failure; succeeded requires a result; failed requires a failure) keeping persistence/internal/public representations separate, and a failed Job is a successfully read resource (HTTP 200 + status `failed`) distinct from the `PublicErrorResponse` envelope. Untrusted input uses `model_validate`/`model_validate_json` (never `model_construct`); validation precedes side effects so the gate raises before completion and the negative test asserts both a `ValidationError` and no completion call; and the 37-Job `model_construct()` incident is contained by rolling back the code (restoring validation) for future traffic and reconciling committed facts with an idempotent audited repair — code rollback is not database-history rollback.

### Validation

- **Day44 has REAL executed runtime evidence.** The runnable artifact was tightened per code review (a restricted `output_schema` type map, UUID `upload_session_id`/`job_id`, an `AnyHttpUrl` citation, and a strict required `MaxTokens` bounded `1..8000`, and a shared summary contract `min_length=1`/`max_length=10_000` that `PublicResult` reuses from `StructuredAIResult` so a succeeded response cannot return an empty or oversized summary), which grew the suite from the classroom's 11 tests to **24**. Dependencies are pinned in `projects/ai-backend-data-layer/api/requirements.txt` (pydantic==2.5.0, pytest==7.4.3). Executed: `python3 -m pip install -r requirements.txt`; `python3 -m py_compile day44_pydantic_contracts.py test_day44_pydantic_contracts.py` passed; `python3 -m pytest -q test_day44_pydantic_contracts.py` -> **24 passed** (Python 3.10.12, Pydantic 2.5.0, pytest 7.4.3). The tested/pinned Pydantic version is 2.5.0 — not all Pydantic v2 releases were tested.
- The completion target in the tests is an **in-memory list callback, NOT PostgreSQL**. **NOT RUN:** FastAPI app/routing/response serialization/exception handlers; authentication and tenant authorization; PostgreSQL uniqueness/transaction/commit-before-202/rollback/repair; SQLAlchemy/Alembic; real Provider SDK/output; Relay/Worker/Redis/Object Storage; integration runtime; production validation.
- Other validation performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day45+ lesson exists and Day45-Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order and heading check; Markdown fence balance; relative-link resolution (new `api/` code/test cross-links and the Day43->Day44 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, or client data). The student answers were transcribed verbatim (typos preserved) from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- Scope: DI/lifespan/configuration/Provider adapters (Day45), SQLAlchemy mapping (Day46), async sessions/transactions (Day47), real Provider SDK parsing (Day53), and contract/integration/failure-injection tests + observability (Day57-58) are named only as future connections; the protected prompt/template files are unchanged; no new project directory was created; and Day45-Day100 curriculum planning was not altered.

---

## v0.1.90 — Day43 AI Backend Product Contract and FastAPI Request Lifecycle (Phase 4 opens)

Date: 2026-07-26

### Added

- Added `docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day42->Day43 mental-model evolution). This is the first Phase 4 lesson.
- Added `projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md` — the Day43 **AI Job API contract** exposing the Day42 durable data-ownership/failure model as a multi-tenant HTTP API: the commit-before-`202` acceptance boundary, the route/method/error/status matrix, the idempotency decision table (unique constraint + atomic create-or-return), tenant isolation at the read boundary (cross-tenant `404`, no existence oracle, allowlisted fields), the HTTP-vs-durable lifecycle boundary + the guarded-claim duplicate gate, the cancellation-intent boundary, and the integrated failure/rollback exercise. It reuses the existing Phase 3 data-layer project (a new `api/` subdirectory; **no new project directory**). Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**; no real secrets, connection strings, or client data.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day43 API-contract increment (contents table, encoded rules, what-it-does-not-do, known gaps, a new `api/` structure entry, and a Day43 validation matrix); noted the Phase 3 project is reused by Phase 4; demoted Day42 to the prior increment.
- Appended a Day43 quick-reference to `cheat_sheets/fastapi.md` (status/error matrix, idempotency, routing/tenant read, lifecycle/duplicate/cancel, weak-vs-strong) and Day43 questions to `interview/fastapi.md` (with the student's verbatim answers, the final Chinese synthesis, and the three English stages).
- Updated `docs/README.md` (added the `fastapi/` Phase 4 folder and the Day43 lesson as the latest), and pointed the Day42 lesson's Next Lesson at the released Day43 lesson.
- Updated `CURRICULUM.md` (Day43 marked Completed with its released lesson/artifact and honest NOT-RUN limits; Phase 4 marked In Progress; Day44–Day100 remain Planned with topics and the 58 per-day connections unchanged) and `ROADMAP.md` (Day43 Completed).
- Updated `PROJECT_STATUS.md` (Day43 last completed with artifact + validation boundary; Current Phase is now Phase 4 In Progress; Current/Next = Day44 Planned), `TASKS.md` (completed Day43 blocks, Day43 preparation converted to history, Day44 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day43 opens Phase 4 by exposing the Day42 durable contract as an HTTP API, and its spine is that **an HTTP response is a promise about committed business state**: `202` is returned only after one PostgreSQL transaction commits Job + `(tenant_id, idempotency_key)` uniqueness + the Outbox dispatch intent (an "attempt to persist" is insufficient; `202` = a durable async commitment, not completion); `201` is created (not a redirect) and a found `GET` is `200` with the business status, while a client-contract failure is `4xx`, a same-key-different-input retry is `409`, and a dependency/DB-timeout outage is `5xx` (never a fake `404`/`202`); lost-response idempotency uses the unique constraint + atomic create-or-return (not `SELECT`-then-`INSERT`) to return the original Job with no second Job/Outbox, binding the key to request meaning and keeping API idempotency separate from Provider idempotency; routing resolves method+path before the handler/DB (`404` no route, `405` wrong method) so static routes precede dynamic ones and validation cannot repair a routing mismatch; `GET` reads committed truth filtered by tenant + Job ID, returning `404` (not `403`) cross-tenant so the API is not an existence oracle (a UUID is not authorization) and allowlisting public fields; the short HTTP lifecycle is separate from the durable background lifecycle (Relay -> Worker claim -> Provider -> guarded completion) so FastAPI never waits for an 8-minute Provider call and an in-process Background Task is not a durable Worker (Day55); at-least-once duplicate delivery is normal and gated first by the guarded `queued -> running` (1 row winner / 0 rows stop) while lease/fencing protects a stale completion later; Artifact existence is not success and cancellation is a durable audited intent via `POST /cancel` (whose semantics express "requested, terminal outcome pending" rather than `DELETE`'s "remove the resource") where `cancel requested != completed` (Day54); and the integrated failure/rollback exercise converges a lost-`202` retry, gates duplicate dispatch to one winner, returns `404` cross-tenant, and (for a bad pre-`COMMIT`-`202` release) rolls back the faulty API release and reconciles committed facts rather than fabricating Jobs or replaying Provider work.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day44+ lesson exists and Day44–Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order and heading check; Markdown fence balance (lesson and artifact); relative-link resolution (new `api/` cross-links and the Day42->Day43 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, or client data). The student answers were transcribed verbatim (typos preserved) from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- **Day43 has NO runtime evidence.** FastAPI runtime: NOT RUN. PostgreSQL runtime: NOT RUN. Relay/Worker runtime: NOT RUN. Redis/Object Storage/Provider runtime: NOT RUN. Integration and production validation: NOT RUN. No FastAPI app/route, PostgreSQL query/commit, Relay/Worker, Provider call, Object Storage access, or migration was executed; routes/status codes/payloads are static contract examples.
- Scope: no runnable FastAPI application was created (the classroom executed nothing, so none is claimed); Pydantic v2 (Day44), DI/lifespan/provider adapters (Day45), SQLAlchemy/Alembic (Day46-48), the durable cancellation protocol (Day54), and Celery (Day55) are named only as future connections; the protected prompt/template files are unchanged; no new project directory was created (the contract lives in the existing `projects/ai-backend-data-layer/`); and Day44–Day100 curriculum planning was not altered.

---

## v0.1.89 — Day42 Backend Data Design Capstone (Phase 3 close)

Date: 2026-07-26

### Added

- Added `docs/redis/day42-backend-data-design-capstone.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day41->Day42 mental-model evolution). This is the Phase 3 capstone.
- Added `projects/ai-backend-data-layer/capstone-backend-data-design.md` — the Day42 **capstone design / evidence pack** integrating Day29-Day41 (PostgreSQL + Redis + Object Storage) into one ownership/recovery/verification contract: the ownership/lifecycle map, the acceptance contract (durable-at-202), dispatch + at-least-once duplicate handling, the short guarded completion transaction + Artifact reconciliation, the failure/degraded matrix, the Upload Session verification contract, tenant isolation + append-only audit + tombstoned retention, the disposable `EXPLAIN ANALYZE` performance-evidence method, the fencing-generation Expand->Contract migration, and the integrated failover/paused-Worker/Artifact recovery runbook. Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**; no real secrets, connection strings, or client data.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day42 capstone increment (contents table, encoded rules, what-it-does-not-do, known gaps, a new `capstone-backend-data-design.md` root-level structure entry, and a Day42 validation matrix); demoted Day41 to the prior increment.
- Added a Day42 cross-boundary quick-reference to `cheat_sheets/redis.md` and a discoverability cross-reference in `cheat_sheets/postgresql.md` (no mechanical duplication).
- Added the Day42 phase-capstone system-design interview material to `interview/redis.md` (Beginner/Intermediate/Senior with the student's verbatim answers and the final Chinese synthesis) and a discoverability cross-reference in `interview/postgresql.md`.
- Updated `docs/README.md` (Day42 is the Phase 3 capstone / latest Redis-folder lesson), and pointed the Day41 lesson's Next Lesson at the released Day42 lesson.
- Updated `CURRICULUM.md` (Day42 Completed; Phase 3 marked Complete; Day43 remains Planned) and `ROADMAP.md` (Day42 Completed). Day43–Day100 planning, topics, and the 58 per-day connections are unchanged.
- Updated `PROJECT_STATUS.md` (Day42 last completed with artifact + validation boundary; Current Phase is now Phase 4 with Current/Next = Day43 Planned; Phase 3 marked Complete), `TASKS.md` (completed Day42 blocks, Day42 preparation converted to history, the Day43 gate marked satisfied), `README.md`, and `AGENTS.md`.

### Notes

- Day42 integrates the whole Phase 3 arc over one evolving multi-tenant AI Research and Automation Platform scenario, and its spine is that **PostgreSQL is the single source of durable truth, Object Storage owns verified bytes, and Redis coordinates but is losable**: what is durable at `202` is only Job + `(tenant_id, idempotency_key)` uniqueness + the Outbox intent; dispatch publishes unpublished Outbox intents and at-least-once duplicate delivery is normal (rejected as a business effect by a guarded `queued -> running`, not by a Redis marker); completion is a short guarded transaction guarded by `running` + current lease token + unexpired lease + `fencing_generation` = the current persisted generation, and Artifact existence alone is never success; degraded modes are scoped by boundary (Redis unhealthy = fail-closed new expensive admission; PostgreSQL down = no new accepts; input Object Storage down = fail-closed that admission only); tenant isolation uses the authenticated predicate + composite tenant-aware foreign keys; audit is append-only with tombstoned Artifact retention; performance is justified by disposable `EXPLAIN ANALYZE` evidence that is not production validation; the fencing generation is rolled out durably via Expand->Contract with old Workers drained/upgraded; and integrated recovery reconciles Job/Attempt/Provider idempotency/Artifact under a universally-honored guard, never blindly re-calling the Provider and never using Artifact existence as ownership proof. This closes Phase 3; Phase 4 (FastAPI) begins at Day43.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day43+ lesson exists and Day43–Day100 remain Planned; LESSON_TEMPLATE_v2 16-section order and heading check; Markdown fence balance (lesson and artifact); relative-link resolution (new capstone cross-links and the Day41->Day42 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, or client data). The student answers were transcribed verbatim (typos preserved) from the teaching-session handoff input, which is not a committed repository artifact; that transcription was checked during authoring but is not repository-reproducible, so it is not listed as a repository validation step.
- **Day42 has NO runtime evidence — RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.** No PostgreSQL, Redis, Object Storage, Provider, Celery/Relay/Worker, or FastAPI command was run; no migration and no `EXPLAIN ANALYZE` were executed; no failover/load/security/data-repair test was performed. `EXPLAIN ANALYZE` and disposable measurement are a described future method only.
- Scope: no runnable rate limiter, real Worker, real Object Storage integration, real schema change, real queue, real Provider call, or runtime test is claimed; SQLAlchemy/Alembic are named only as Phase 4 future connections; the protected prompt/template files are unchanged; no new project directory was created (the capstone artifact lives inside the existing `projects/ai-backend-data-layer/`); and Day43–Day100 curriculum planning was not altered.

---

## v0.1.88 — Curriculum Planning: preserve future lesson implementation boundaries (Day50/54/91/94/95)

Date: 2026-07-26

### Changed

- Recorded confirmed implementation boundaries for Day50, Day54, Day91, Day94, and Day95 so a future teaching chat (lacking current context) does not mis-scope, over-implement, or over-claim validation. This is a small planning correction, not a redesign of Day43–Day100: no Day Topic changed, no phase order changed, no future lesson or project code was created, and every day remains `Planned`.
- `CURRICULUM.md`: added a "Future Lesson Implementation Boundaries" section and a one-line `Implementation boundary:` pointer on the Day50, Day54, Day91, Day94, and Day95 bullets. The recorded boundaries:
  - **Day50 (Transactional Outbox scope).** Day50 completes Job + Outbox in one PostgreSQL transaction, the Outbox Relay contract, the transport-adapter boundary, executable tests against a fake/in-memory transport, and idempotent dispatch intent + failure retention. A fake/in-memory transport test MAY be a real runtime test but does NOT mean a real broker, Celery worker, or production delivery chain is validated. Day50 must not claim Celery runtime is done, must not treat the Day40 custom Redis Streams / Consumer Group as Celery's internal implementation, must not hand-build a Celery replacement, and must not claim exactly-once across PostgreSQL + broker + worker. Day55 (not Day50) completes the Celery broker transport, worker, ACK timing, redelivery, idempotent processing, poison-task handling, and recovery validation.
  - **Day54 (streaming and lifecycles).** Distinguish token streaming of a synchronous Provider call from progress/event streaming of an already-persisted background Job, and distinguish the HTTP client connection, Provider request, and durable background Job lifecycles. State that an HTTP client disconnect does not necessarily stop the Provider call, does not auto-cancel an already-persisted background Job, and does not erase an accepted business commitment; background-Job cancellation goes through an explicit durable/auditable/guarded/cooperative cancellation protocol.
  - **Day94 (thin vertical integration).** Day94 integrates already-built Phase 5–7 components (Agent, RAG, MCP, Playwright, n8n) along one bounded but complete vertical user path with preserved correlation IDs, clear component-failure states/recovery, and traceable result/citation/Artifact/audit evidence — clearly distinguishing mock / static / local runtime / integration runtime / production validation. It does not re-implement completed components or chase five disconnected demos.
  - **Day95 (representative drills).** Day95 covers failure recovery, load, security, and data repair with a limited, representative drill set (not exhaustive enumeration), saving injection condition, expected behavior, actual command/test, evidence, recovery/data-repair steps, unvalidated limitations, and the validation class; a limited scope must not be described as comprehensive production validation.
  - **Day91 (Final Capstone README timing).** `projects/final-capstone/README.md` stays a placeholder until Day91; when Day91 confirms product requirements/architecture/scope it must simultaneously update that README into the real entry point (scope, run instructions, validation evidence, limitations). Before Day91 it must not be treated as complete implementation evidence.
- `ROADMAP.md`: added brief cross-references from Phase 4 (Day50/Day54) and Phase 8 (Day91/Day94/Day95) to the `CURRICULUM.md` "Future Lesson Implementation Boundaries" section; the Day43–Day100 tables (days and Topics) are unchanged.

### Notes

- These boundaries operationalize the existing Decision 006 (runtime evidence/evaluation/portfolio as completion conditions; testing/observability continuous from Day43); `DECISIONS.md` was therefore not modified. `PROJECT_STATUS.md` and `TASKS.md` were not modified (no contradiction). The `projects/final-capstone/README.md` placeholder was intentionally left unchanged.

### Validation

- Protected files unchanged: `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`. No new Master Prompt.
- Status preserved: Day01–Day41 Completed; Day42 Planned / Not started and still the Current Lesson; Last Completed Lesson still Day41; Day43–Day100 all Planned. Day43–Day100 remain 58 continuous days with unchanged Topics and the 58 existing `Connection:` lines intact.
- Consistency: `CURRICULUM.md` and `ROADMAP.md` Day43–Day100 days/topics identical (no gaps/duplicates/overlaps). No future lesson files, no new project directories, no project code or student answers changed.
- Static checks: `git diff --check`; Markdown fence balance; internal relative-link resolution; secret scan (no real secrets/keys/tokens/connection strings/client data). Planning-only change; no runtime or production validation was executed or claimed.

---

## v0.1.87 — Curriculum Review Fixes: Day55 Celery boundary; per-day Connections; continuous test/observability

Date: 2026-07-26

### Fixed

- **Day55 Celery transport boundary.** `CURRICULUM.md` Day55 scope said "Celery workers over the Day40 transport," which could be misread as Celery consuming the Day40 custom Redis Streams / Consumer Group. Rewrote the Day55 scope to state that Day55 **reuses the Day40 delivery-semantics mental model** (at-least-once delivery, redelivery, ACK timing, idempotency, poison-message handling) while running long-running Provider work on a **supported Celery broker transport**, and that Celery's broker implementation is **not** equated with the Day40 custom Streams design and **no** Celery replacement is hand-built. Day55 Topic is unchanged. Synced a concise Day55 note into the `ROADMAP.md` Phase 4 objective (table rows unchanged).
- **Per-day Knowledge Connection for Day43–Day100.** The previous entry claimed every future day had a knowledge connection, but `CURRICULUM.md` only carried phase-level connections. Added a compact `Connection:` line to each of the 58 future days (previous capability → current missing capability → next lesson usage): Day43 inherits Day42; Day44 inherits Day43 and connects Day45; each phase's first day connects the previous phase's capstone; each phase's last day connects the next phase; Day100 connects the final portfolio and job application (no fictional Day101). Connections are short and do not pre-expand future lessons. `ROADMAP.md` stays a concise table with day/topic identical to `CURRICULUM.md`.
- **Testing and observability are continuous from Day43.** Added a "Cross-cutting Engineering Discipline (Day43–Day100)" section to `CURRICULUM.md` stating that baseline tests, structured logging, correlation IDs (`job_id`/`trace_id`/`attempt_id`), and validation evidence begin on Day43 and evolve with every Engineering Artifact; that Day57 advances an existing test suite (fake/deterministic provider, contract, integration, failure-injection, recovery) rather than being the first testing lesson; that Day58 integrates and verifies existing observability (structured logs, correlation, metrics, traces, runtime evidence) rather than being the first observability lesson; and that every implementation day adds proportionate tests/evidence with no phase postponing correctness to its capstone. Synced this principle into the `ROADMAP.md` employment-readiness paragraph and added one sentence to `DECISIONS.md` Decision 006 (Decision 006 not otherwise rewritten).

### Validation

- Protected files unchanged: `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`. No new Master Prompt.
- Status preserved: Day01–Day41 Completed; Day42 Planned / Not started and still the Current Lesson; Last Completed Lesson still Day41; Day43–Day100 all Planned. No Day42/future lesson files created, no new project directories, no project code or student answers changed.
- Consistency: `CURRICULUM.md` and `ROADMAP.md` list identical Day43–Day100 days and topics (verified, no gaps/duplicates/overlaps); 58 per-day Connections present.
- Static checks: `git diff --check`; Markdown fence balance; internal relative-link resolution; secret scan (no real secrets/keys/tokens/connection strings/client data). Planning-only change; no runtime or production validation was executed or claimed.

---

## v0.1.86 — Curriculum Planning: Day43–Day100 AI Backend Product Thread (Phases 4–8)

Date: 2026-07-26

### Changed

- Planned the Day43–Day100 curriculum ahead of Day42 as a single AI Backend product capability chain (a **Multi-tenant AI Research and Automation Platform**), not a set of unrelated framework tutorials. This change updates planning, decisions, status, and navigation only — it does **not** start Day42, generate any future lesson, implement any future project, or mark any future course as started/completed.
- `CURRICULUM.md`: added Phase 4 (Day43–Day58, Production AI API Engineering), Phase 5 (Day59–Day68, Playwright Browser Automation and Agent Tools), Phase 6 (Day69–Day74, n8n AI Workflow Orchestration), Phase 7 (Day75–Day90, AI Agent/RAG/MCP/Evaluation), and Phase 8 (Day91–Day100, Final Capstone, Portfolio and Overseas Interview). Each future day has a Topic, a concise scope, `Status: Planned`, and a knowledge connection; each phase has an objective, deliverable, and validation requirement. Also added an employment-readiness boundary and a cross-cutting employment-training thread. Day01–Day42 content and statuses are unchanged; Day42 remains Planned.
- `ROADMAP.md`: replaced the skeletal Phase 4–8 sections with full Day43–Day100 phase tables (all `Planned`), the complete Day42→Day100 knowledge chain, phase deliverables, and the employment-readiness boundary — kept fully consistent with `CURRICULUM.md` (day numbers and topics verified identical, no gaps/duplicates/overlaps).
- `DECISIONS.md`: added **Decision 006 — AI Backend Product Thread Across Day43–Day100** (Accepted): why not isolated framework tutorials; FastAPI/Playwright core and n8n as integration layer (extending Decision 004); AI in scope from Phase 4; runtime evidence/evaluation/portfolio as completion conditions; employment readiness (not an offer guarantee, not Senior/Staff). Existing decisions 001–005 unchanged.
- `PROJECT_STATUS.md`: added a "Future Roadmap (Day43–Day100 planned)" section; Current Lesson stays Day42 (Planned / Not started) and Last Completed Lesson stays Day41. Nothing future marked started/completed.
- `TASKS.md`: recorded "Future Curriculum Planning (Day43–Day100) completed", kept the Day42 Preparation block, and added a Day43 Preparation block explicitly gated to start only after the Day42 Repository Update is complete. No historical tasks deleted.
- `README.md` and `AGENTS.md`: kept Current Lesson = Day42 and concisely noted the planned Phase 4–8 future direction and the overseas AI Backend Engineer goal, without duplicating the full curriculum.

### Notes

- FastAPI and Playwright are the core engineering skills; n8n is an integration layer that does not replace backend correctness (durable truth stays in PostgreSQL). AI enters the unified scenario from Phase 4 rather than only at the end. The existing project directories (`fastapi-todo`, `fastapi-auth`, `fastapi-playwright`, `playwright-login`, `playwright-scraper`, `n8n-workflows`, `ai-agent`, `final-capstone`, `ai-backend-data-layer`) are reused; **no new project directories were created**.
- Employment-readiness is stated honestly: the curriculum builds core capability and portfolio evidence but does not guarantee a job, and 100 days is not equivalent to years of production experience or to Senior/Staff level. Target roles: Junior / Developing AI Backend Engineer, AI Startup Backend Engineer, Backend Engineer on LLM/RAG/Agent products.

### Validation

- Protected files unchanged: `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`. No new Master Prompt was created.
- Consistency verified: Day01–Day41 remain Completed and Day42 remains Planned / Not started across the status files; Current Lesson is still Day42; every Day43–Day100 entry is `Planned`; `CURRICULUM.md` and `ROADMAP.md` list identical days and topics with continuous, non-overlapping, non-duplicated numbering; no future lesson files were created; and no new project directories were created.
- Static checks: `git diff --check`; Markdown fence balance; internal relative-link resolution; and a secret scan (no real secrets, API keys, tokens, connection strings, or client data added).
- This is a **planning-only** change. No lesson was taught, no future course was started, and nothing runtime/production was executed or validated.

---

## v0.1.85 — Day41 Review Fixes: durable fencing generation + unambiguous completion guard; date

Date: 2026-07-26

### Fixed

- **Fencing generation is durable, and the Job Complete guard is unambiguous.** Day41 simultaneously said Redis state can be lost/rolled back on eviction/failover, that Redis is used for lease/coordination, and that a fencing generation prevents stale-owner writes — but it did not pin down where the fencing generation is allocated, and several places wrote the guard as the ambiguous `current/greater generation`. That is a correctness hole: if the generation were allocated by a rollback-able Redis `INCR`, a failover could hand a new owner a smaller or duplicate generation and the downstream could no longer reliably reject an old owner's stale write. Corrected the engineering model across the lesson, artifact, cheat sheet, interview, project README, `PROJECT_STATUS.md`, `TASKS.md`, and this changelog: the **fencing generation is advanced and persisted in a PostgreSQL durable claim/takeover transaction** (never a Redis `INCR`); the short Redis **lease** remains losable coordination; and the **Job Complete** predicate is `job_status = 'running'` AND `lease_token` = the current worker lease token AND `lease_expires_at > now()` AND **`fencing_generation` = the current persisted fencing generation** (**equality**, not `>=` and not `>`). The **generalized** downstream rule `last_accepted_fence < incoming_fence` (accept then persist `incoming_fence`) is documented **separately** and explicitly not mixed into the Job completion predicate. All ambiguous `current/greater generation` phrasings were removed, and "fencing acquisition" is no longer listed among losable Redis coordination. Providers still do not compare the fencing generation, so stable Provider idempotency keys + deterministic Artifact reconciliation remain required. Student answers were preserved verbatim; only Tech Lead Review / Mental Model / Artifact / cheat-sheet / interview strong-answer / status summaries were corrected. No schema was invented and no SQL was executed.
- **Day41 completion date.** Corrected the Day41 completion date to `2026-07-26` in `CHANGELOG.md` (the v0.1.84 entry) and `PROJECT_STATUS.md` (Completed Time). Day40-and-earlier dates were not changed.

### Validation

- Static checks actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); a full-repository Day41 fencing search confirming the Redis lease is not described as a durable fencing source, that Claim/takeover advances/persists the generation in a PostgreSQL durable ownership transaction, that Job Complete requires running + current lease token + unexpired lease + equality with the current persisted fencing generation, that `last_accepted_fence < incoming_fence` appears only as a separate generic downstream model, and that no `current/greater generation` phrasing remains; a check that the Day41 date is `2026-07-26` in both files; Markdown fence balance; relative-link resolution; and a secret scan.
- **Runtime NOT RUN; FAILOVER/EVICTION/SECURITY DRILL NOT RUN; PRODUCTION NOT VALIDATED.** This round changed only wording/engineering semantics; no Redis, Lua, failover, eviction, ACL/TLS, PostgreSQL, Provider, Object Storage, or production validation was executed.

---

## v0.1.84 — Day41 Redis Coordination and Production Safety

Date: 2026-07-26

### Added

- Added `docs/redis/day41-redis-coordination-and-production-safety.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day40->Day41 mental-model evolution).
- Added `projects/ai-backend-data-layer/redis/redis-coordination-and-production-safety-design.md` — the Day41 **coordination and production-safety design / evidence pack**: the atomic rate-limit admission contract, the algorithm decision table (fixed/first-write-TTL/sliding/token-bucket), the API idempotency boundary, the lease safety model (acquire/token/expiry/renew/atomic compare-and-delete release + paused-owner timeline), the fencing model, the PostgreSQL completion guard (running + current lease token + unexpired lease + fencing_generation = the current persisted generation, advanced/persisted in a PostgreSQL claim/takeover tx, extending Day34/Day37), the Redis loss/capacity matrix (RDB/AOF/replication/failover/eviction), the security matrix (network/auth/ACL/TLS/dangerous-command), and the integrated failure runbook. Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**; Redis is **not** promoted to business truth and **no** exactly-once is claimed; no real secrets, connection strings, certificates, or client data.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day41 increment: a design-contents table, the encoded rules, an explicit statement of what the design does not do, Day41 known gaps, a new `redis-coordination-and-production-safety-design.md` entry in the structure tree, and a separate Day41 validation matrix.
- Appended a Day41 rapid-reference section (atomic admission, admission-vs-success/API idempotency, algorithms, lease/safe-release/fencing, loss/capacity/security/outage, weak-vs-strong answers) to `cheat_sheets/redis.md`.
- Appended Day41 questions to `interview/redis.md`, preserving the student's real answers verbatim — including `缺少并发控制的锁`, `先判断是否大于60，如果大于60计数-1返回拒绝`, `不需要回退。而且每分钟60次还设置了TTL...`, `不会允许，因为12:01:59才会刷新...`, `我更倾向于滑动窗口`, `令牌桶`/`无法请求`, `根据数据库持久化事实attempt、event、outbox intent来判断`, `需要，因为redis锁可以保护多个请求的并发`, `不能`, `会导致下一个work再次进入到A的业务内`, `不能，锁本身只能保证下一个work不会执行当前work中的任务...`, `因为下游的provider不能区分lease_token的区别`, `通过比较fencing token...`, `不说明，应该是为了防止在这期间无限制调用`, `可能多放行一部分请求...`, `因为复制的是之前的的限流计数`, `应该分开放在不同实例...`, `不能`/`不能，对待高风险命令应该严格限制...`/`不能,因为实际业务还是需要自运维进行配置`, `fail-closed，因为主要是post一类的请求...`, the failover/mass-restart/monitoring answers, and the three verbatim Beginner/Intermediate/Senior English answers (no duplicate Redis interview file created).
- Updated `docs/README.md` (Day41 is now the latest Redis lesson), and pointed the Day40 lesson's Next Lesson at the released Day41 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day41 completed with its released lesson/artifact (Day42 remains Planned).
- Updated `PROJECT_STATUS.md` (Day41 last completed with artifact + validation boundary; Current/Next is Day42 Planned / Not started), `TASKS.md` (completed Day41 blocks, Day41 preparation converted to history, Day42 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day41 uses Redis for **narrow, explicitly bounded coordination and protection** around the Job API and Worker lifecycle while **PostgreSQL Job/Attempt/Event/Outbox stays the durable business authority**, and its spine is that **Redis coordinates/protects but is not truth**: the two-Pod admission race (both read 59, both admit) is missing **atomicity**, not necessarily a lock, so a rate-limit decision is an atomic `read -> check limit -> INCR-if-allowed -> TTL -> allow/reject` in one short **Lua** step (never `GET->check->SET`; never `INCR`-then-`DECR` compensate, whose crash inflates the counter; `MULTI/EXEC` cannot make a decision from a prior external `GET` atomic and `WATCH+MULTI/EXEC` is the optimistic-with-retry alternative; don't nest `MULTI/EXEC` in Lua or wrap a single already-atomic command). **Redis admission is an allowed attempt, not durable Job success**, so the counter is not compensated after a failed Accept (the TTL resets the window; compensation adds a second uncertainty boundary), and the durable acceptance truth is `INSERT Job(queued) + INSERT Outbox(dispatch intent) -> COMMIT -> 202 + job_id`. Algorithms trade off (clock-aligned fixed = cheap but a **boundary burst** of 60 at `12:00:59` + 60 at `12:01:00` = 120; first-write TTL = request-anchored with distinct semantics; sliding = smooth/fair for expensive AI Jobs; token bucket capacity 10 refill 1/s permits a burst but rejects an 11th request 0.2s after ten are consumed). API idempotency is a **client key + PostgreSQL UNIQUE `(tenant_id, idempotency_key)`** create-or-return (Attempt/Event may not exist yet, so they can't dedup a first POST; a Redis lock only reduces optional duplicate work, the unique constraint is the authority), with **API, Provider, and notification identities kept separate**. A **lease** (`SET NX PX` + opaque token, renew while owner, **atomic compare-and-delete** release because a blind `DEL` lets old A delete new B's lease) has **expiry that permits takeover but does not stop a paused owner or an in-flight Provider call**; a **fencing generation** is a **monotonic** ownership generation whose correctness must **not** depend on rollback-able Redis, so it is advanced and **persisted in a PostgreSQL claim/takeover transaction** (never a Redis `INCR`, which a failover could hand out smaller or duplicate) while a UUID lease token is unordered and cannot fence, so the PostgreSQL **Job Complete guard** requires `job_status = 'running'` AND `lease_token` = the current token AND `lease_expires_at > now()` AND `fencing_generation` = the current **persisted** generation (**equality**, not `>=` or `>`; the generic downstream rule `last_accepted_fence < incoming_fence` is a separate model) while ordinary Providers still need stable idempotency + Artifact reconciliation. **RDB/AOF/async-replication/failover/eviction can lose or reset counters** as a temporary **protection-degradation** window (a low/missing counter is not "under limit"), so coordination state is **isolated** from LRU-evictable cache; **security** is layered (private network necessary-but-insufficient + auth + ACL scoped to the command set and `ratelimit:*` prefix + TLS + deny `FLUSHALL`/`CONFIG` + audit/monitoring) and **managed Redis runs infrastructure but does not transfer business responsibility**; and the integrated failover+lease+Provider incident is contained by **failing closed** on new expensive admission, **not mass-restarting** Workers (bounded backoff + drain + reconcile), with Worker B reconciling durable facts + Provider idempotency + Artifact before any call rather than acting on a fresh lease.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day42 lesson exists and Day42 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day41 verbatim student quote (Chinese answers + the three English answers) appears in `Day41_Repository_Update_Input.md`; Markdown fence balance (lesson and artifact); relative-link resolution (including the new `redis-coordination-and-production-safety-design.md` cross-links and the Day40->Day41 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, certificates, or client data in the lesson, artifact, cheat sheet, or interview).
- **Day41 has NO runtime evidence — RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.** No Redis server, Sentinel, Cluster, managed Redis, `redis-cli`, Lua, `MULTI/EXEC`, `WATCH`, ACL, TLS, persistence, eviction, failover, rate limiter, FastAPI endpoint, PostgreSQL Job/Attempt/Event/Outbox/lease/fencing SQL, Provider, Object Storage, or Worker drain/handoff was run, measured, or inspected in class or during the repository update. Every number (60/min, 30s, capacity 10, refill 1/s) is a static design example. **Redis is not promoted to business truth and no exactly-once is claimed.** Static reasoning review of every boundary was completed.
- Scope: no Day42 lesson was created; the integrated data-ownership/failure/recovery/verification capstone is mentioned only as a future Day42 boundary; no SQLAlchemy/Alembic or Playwright content was added; the artifact invents no command output, Redis version, benchmark, latency, throughput, or data-loss measurement; the protected prompt/template files are unchanged; and no real secrets, connection strings, certificates, or client data were added.

---

## v0.1.83 — Day40 Review Fixes: dispatch/completion event semantics; conditioned durable-backlog wording

Date: 2026-07-25

### Fixed

- **Dispatch vs completion event lifecycle.** The Day40 artifact and lesson placed both `g:job-exec` and `g:notify-delivery` on the single stream `ai:stream:job-dispatch:v1`, which wrongly implied the notification Consumer could derive "Job completed, send completion email" from a **dispatch** entry — but a `job-dispatch` event is emitted at **Accept**, when the Job is not finished, and separate Consumer Groups only solve "two groups can each receive the same entry." Corrected to an explicit, Outbox-driven lifecycle: the **Accept** transaction commits a `job-dispatch` Outbox intent → Relay → `ai:stream:job-dispatch:v1` → `g:job-exec`; the **Complete** transaction commits a `job.completed` Outbox intent → Relay → `ai:stream:job-events:v1` (or one shared event stream with an explicit `event_type`) → `g:notify-delivery`. The completion email is now driven **only** by a committed `job.completed` Outbox/Event, never by an accept/dispatch entry; events still carry small references only (`tenant_id`, `job_id`, `event_id`, `event_type`, `trace_id`), PostgreSQL committed Outbox/Event remains the event source, a Redis delivery is still not business truth, and Provider/email keep their own stable idempotency identities. Updated the lesson (Objective 4, Lesson Map, Core Mental Model, Concept 4 review, Concept 8 review, Exercise 7, the "one group as broadcast" misconception, Mental Model Summary), the artifact (payload contract §3, topology §4, recovery matrix §10, decision summary), the project README (contents table + encoded rules), the cheat sheet, the interview (Q12, Q13), `PROJECT_STATUS.md`, and `TASKS.md`. Student answers were preserved verbatim; the architecture semantics were corrected only in Tech Lead Review / Mental Model / artifact / summaries — the student's "用数据库中持久化的事实拦住" instinct is now shown to be exactly the committed-`job.completed`-gates-the-email rule.
- **Absolute "Durable backlog = yes" wording.** The List/Pub-Sub/Streams decision table asserted an unconditional `Durable backlog = yes` for List and Streams, inconsistent with the Day38 Redis RDB/AOF, replication, and failover loss-window boundary. Reworded to **"Retained backlog, subject to configured Redis persistence and replication/failover loss windows,"** with an explicit note that Redis Streams/Lists may retain transport entries and persistence reduces loss windows but does **not** make Redis durable business truth — **PostgreSQL remains the authoritative durable Job/Attempt/Event/Outbox/Notification truth.** Applied in the artifact decision table, the cheat sheet decision table, the project README contents table + encoded rules, and the lesson's English-interview model answer (Pub/Sub genuinely has **no** backlog, which is left unchanged).

### Validation

- Static checks actually performed: `git diff --check`; changed-file scope; a repository search confirming `g:notify-delivery` no longer consumes `ai:stream:job-dispatch:v1` with completion semantics and that the completion notification is driven only by a committed `job.completed` Outbox/Event; a search confirming no unconditional `Durable backlog = yes` / "durable backlog + " wording remains for List/Streams; confirmation that Day40 still states Redis transport is not business truth, Redis provides no exactly-once across ACK + PostgreSQL commit + Provider, and no Celery replacement is built; Day41 still Planned with no Day41 lesson; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); Markdown fence balance; and relative-link resolution.
- **Runtime NOT RUN; INTEGRATION NOT RUN; PRODUCTION NOT VALIDATED.** This round changed only wording/architecture semantics; no Redis, Stream, Consumer Group, `XACK`, Claim, trim, Pub/Sub, PostgreSQL, Celery, Provider, or email was executed.

---

## v0.1.82 — Day40 Redis Messaging and Queue Semantics

Date: 2026-07-25

### Added

- Added `docs/redis/day40-redis-messaging-and-queue-semantics.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day39->Day40 mental-model evolution).
- Added `projects/ai-backend-data-layer/redis/redis-messaging-and-queue-semantics-design.md` — the Day40 **messaging and queue semantics design / evidence pack**: the List/Pub-Sub/Streams decision table, the small Stream payload contract, the event lifecycle and Consumer Group topology (Accept -> job-dispatch stream -> g:job-exec; Complete -> job.completed events stream -> g:notify-delivery), the PEL/ACK/Claim/redelivery lifecycle, the delivery-vs-durable-completion boundary, per-side-effect idempotency/reconciliation, the retry classification and quarantine/dead-letter boundary, the safe trim/retention contract, and the integrated failure/recovery matrix. Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**; Redis is **not** claimed to provide exactly-once and **no** Celery replacement is built; no real secrets, connection strings, or tenant data.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day40 increment: a design-contents table, the encoded rules, an explicit statement of what the design does not do, Day40 known gaps, a new `redis-messaging-and-queue-semantics-design.md` entry in the structure tree, and a separate Day40 validation matrix.
- Appended a Day40 rapid-reference section (List/Pub-Sub/Streams, lifecycle/delivery semantics, groups/ordering/payload, poison/trim/notifications, dual-crash recovery, weak-vs-strong answers) to `cheat_sheets/redis.md`.
- Appended Day40 questions to `interview/redis.md`, preserving the student's real answers verbatim — including the crash-before-ACK `视为已处理...` answer, the `检查postgresql...` reconcile answer, the Pub/Sub `因为pub/sub只是做广播...` answer, the early-ACK `立刻XACK...at-most-once` answer, the delayed-ACK `因为重投...` answer, the ordering `不能保障` answer, the poison `会造成redis一直处于重试状态...先contain，再删除` answer, the retry-limit `不能，因为有一个重试上限` and `瞬时错误...` answers, the trim `破坏重放能力` answer, the Lists `list缺少streams持久化保存信息的机制` answer, the payload `object storage保存大文档...` answer, the group `会发生一个work已经发送用户通知的服务...` answer, and the notification `根据数据库持久化attempt与event...` answer (no duplicate Redis interview file created).
- Updated `docs/README.md` (Day40 is now the latest Redis lesson), and pointed the Day39 lesson's Next Lesson at the released Day40 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day40 completed with its released lesson/artifact (Day41 remains Planned).
- Updated `PROJECT_STATUS.md` (Day40 last completed with artifact + validation boundary; Current/Next is Day41 Planned / Not started), `TASKS.md` (completed Day40 blocks, Day40 preparation converted to history, Day41 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day40 uses Redis Lists, Pub/Sub, and Streams by their **delivery and failure semantics** while PostgreSQL stays durable Job truth and idempotency makes redelivery safe, and its spine is that **a Redis Stream delivery — even an `XACK` — is transport state, not business completion**: a Worker that consumed a message and crashed before `XACK` leaves the entry **Pending** in the Consumer Group PEL (Redis cannot know whether the Provider/DB effect happened) and it must stay recoverable via `XCLAIM`/`XAUTOCLAIM`, while PostgreSQL Job/Attempt/Event/Outbox/Notification records plus reconciliation decide completion. ACKing before processing is **at-most-once** (a crash silently loses the Job), so a durable recoverable decision is persisted in PostgreSQL **before** `XACK`, giving **at-least-once** that is made safe by stable per-side-effect idempotency identities + guarded transitions + reconciliation (**Redis alone gives no exactly-once** across Redis ACK + PostgreSQL commit + external Provider call). **Pub/Sub** is live broadcast with no backlog/ACK/PEL/Claim/replay, so an offline/crashed subscriber permanently misses a message (loss-tolerant notifications only), while **Streams + Consumer Groups** give recoverable delivery; within one group a message goes to **one** consumer, so independently interested effects (Job execution vs notification delivery) need **separate** groups each with its own PEL/ACK/Claim, and stream append order is transport order, not business-completion order (guarded transitions + idempotency preserve validity). **Lists** may be persisted but lack native Consumer Group/PEL/ACK/Claim/redelivery, so no Celery replacement is hand-built, and Stream payloads carry **small references** (`tenant_id`, `job_id`, `event_id`, trace) with Object Storage owning bytes and PostgreSQL owning references/provenance. A retry **limit** is a capacity-containment policy, not an error classifier, and a fixed immutable payload missing `tenant_id` is a **permanent message-contract failure** handled by bounded retry -> durable quarantine/dead-letter -> alert -> repair producer -> controlled replay (ACK the original only after quarantine evidence exists, never silently delete); **trimming** is a retention/capacity contract that must never remove Pending or recovery/quarantine evidence (it destroys Claim/redelivery/replay); each notification effect (completion/failure/admin) needs its **own** durable delivery identity (e.g. `job:{job_id}:notification:completion:v1`) because a Job Attempt/Event does not prove an email was sent; and the integrated dual-crash recovery is preserve-evidence -> inspect PostgreSQL -> reconcile Provider/email by stable ids -> each group Claims its own Pending -> ACK after the recovered durable decision (never blindly rerun/repeat/delete/trim).

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day41 lesson exists and Day41 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day40 verbatim student quote appears in `Day40_Repository_Update_Input.md`; Markdown fence balance (lesson and artifact); relative-link resolution (including the new `redis-messaging-and-queue-semantics-design.md` cross-links and the Day39->Day40 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, or tenant data in the lesson, artifact, cheat sheet, or interview).
- **Day40 has NO runtime evidence — RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.** No Redis server, `redis-cli`, Stream, Consumer Group, PEL, `XACK`, `XCLAIM`/`XAUTOCLAIM`, trim, Pub/Sub, List, or PostgreSQL/Celery/Worker/Provider/email/Object Storage integration was run, measured, or inspected in class or during the repository update. **Redis is not claimed to provide exactly-once processing**, and **no Celery replacement was built**. Static reasoning review of every semantic boundary was completed.
- Scope: no Day41 lesson was created; atomic composition, coordination, locks/leases + fencing, and full rate limiting are mentioned only as future Day41 boundaries; no SQLAlchemy/Alembic or Playwright content was added; the artifact invents no command output, Redis version, throughput, or redelivery figure; the protected prompt/template files are unchanged; and no real secrets, connection strings, tenant identifiers, or production data were added.

---

## v0.1.81 — Day39 Redis Cache Design and Consistency

Date: 2026-07-24

### Added

- Added `docs/redis/day39-redis-cache-design-and-consistency.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day38->Day39 mental-model evolution).
- Added `projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md` — the Day39 **cache consistency design / evidence pack**: the per-endpoint cache-aside/invalidation contracts, commit-before-invalidate ordering with the pre-commit re-cache race, cache key versioning, TTL and jitter, stampede/single-flight/stale-while-revalidate, a fail-open vs fail-closed table, negative caching, correctness metrics, Outbox invalidation recovery, and the v2 cache-contract incident. Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**, with no real secrets, connection strings, or tenant data.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day39 increment: a design-contents table, the encoded rules, an explicit statement of what the design does not do, Day39 known gaps, a new `redis-cache-consistency-design.md` entry in the structure tree, and a separate Day39 validation matrix.
- Appended a Day39 rapid-reference section (cache-aside, invalidation ordering, TTL/jitter, stampede/SWR, fail-open/closed, negative caching, metrics, recovery, weak-vs-strong answers) to `cheat_sheets/redis.md`.
- Appended Day39 questions to `interview/redis.md`, preserving the student's real answers verbatim — including the stale-vs-committed `API应该以postgresql持久化状态为准...` answer, `提交后删除`, the cache-aside miss answer, the stampede/`缓存雪崩` answer, `先立刻返回旧的running`, the `不能，POST /jobs/{job_id}/cancel有的job已经success` cancel answer, `先更新A再，更新B`, `因为会造成兼容性问题`, the negative-caching `负载攻击` answer, the `miss ratio` answer, `最危险的操作动作是直接重新提交。手动删除`, the initial `先回滚到V1版本` and the corrected `Redis v2 cache contract` answer, and the three English answers (no duplicate Redis interview file created).
- Updated `docs/README.md` (Day39 is now the latest Redis lesson), and pointed the Day38 lesson's Next Lesson at the released Day39 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day39 completed with its released lesson/artifact (Day40 remains Planned).
- Updated `PROJECT_STATUS.md` (Day39 last completed with artifact + validation boundary; Current/Next is Day40 Planned / Not started), `TASKS.md` (completed Day39 blocks, Day39 preparation converted to history, Day40 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day39 turns the Day38 ownership boundary into an explicit **per-endpoint cache consistency contract**, and its spine is that **a PostgreSQL COMMIT is the moment of authority while the Redis cache is a rebuildable projection that may be stale or absent**: a cache hit is not truth and a cache miss is not a Job failure, and a short TTL only **bounds** staleness (it is not synchronization and can raise PostgreSQL load). Cache-aside reads return a hit only when the endpoint tolerates it, else read PostgreSQL and best-effort repopulate with a TTL (a cache `SET` failure never invalidates a correct response). Invalidation is **commit-first**, then delete **every** affected view (Job-detail **and** the tenant recent-completed list), because a pre-commit delete races a reader into re-caching the old `running` state with a fresh TTL. An incompatible representation change (`progress` `42` [0-100] -> `0.42` [0-1]) needs a new versioned key (`v2`) while additive optional fields keep the version. A fixed synchronized TTL causes a **cache avalanche** fixed by **TTL jitter**, while **single-flight** protects only **one** hot key (one leader rebuilds; followers wait within a bounded deadline or take an allowed stale value; on leader timeout use bounded retry + backoff + jitter, not a full fan-out), and **stale-while-revalidate** serves a short stale `running` view for tolerant reads only. `GET /progress` may **fail open** while `POST /cancel` **fails closed** on PostgreSQL authorization + a **guarded** state transition (a cache never authorizes, and a Job already `succeeded` cannot be cancelled). A short tenant-scoped **negative cache** absorbs penetration by non-existent IDs but is load protection, not a security control, and is invalidated on creation. A **high hit ratio is not health** (a hit can overload a hot key; measure freshness/correctness — commit->invalidation delay, cache age, stale-terminal rate, sampled Redis-vs-PostgreSQL agreement). An unknown cache-`DEL` outcome is recovered via a **Transactional Outbox** invalidation intent + a retryable **idempotent `DEL`** (never redo the Job transition or re-call the Provider), and the **v2 cache-contract incident** is handled by reconciling/retrying invalidation + bounded SWR + protecting PostgreSQL **first**, rolling back only the Redis v2 cache **contract** on proven incompatibility — never committed PostgreSQL Job truth and never Provider work.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day40 lesson exists and Day40 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day39 student quote appears in `Day39_Repository_Update_Input.md`; Markdown fence balance (lesson and artifact); relative-link resolution (including the new `redis-cache-consistency-design.md` cross-links and the Day38->Day39 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, or tenant data in the lesson, artifact, cheat sheet, or interview).
- **Day39 has NO runtime evidence — RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.** No Redis server, `redis-cli`, cache API, PostgreSQL integration, Outbox Relay, Worker, Provider, Object Storage, benchmark, cache stampede, eviction, hot key, TTL, or jitter was run, measured, or inspected in class or during the repository update. Numbers (10s, 50,000, TTL/jitter ranges) are illustrative, not measured. Static reasoning review of every contract was completed.
- Scope: no Day40 lesson was created; messaging/Streams/Pub-Sub, atomic composition, and full rate limiting are mentioned only as future Day40-41 boundaries; no SQLAlchemy/Alembic or Playwright content was added; the artifact invents no command output, Redis version, hit ratio, latency, or eviction figure; the protected prompt/template files are unchanged; and no real secrets, connection strings, tenant identifiers, or production data were added.

---

## v0.1.80 — Day38 Redis Foundations and Data Structures

Date: 2026-07-24

### Added

- Added `docs/redis/day38-redis-foundations-and-data-structures.md` (LESSON_TEMPLATE_v2, all 16 sections in order; Master Prompt v3.2 knowledge-continuity chain and a Day37->Day38 mental-model evolution). New `docs/redis/` directory.
- Added `projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md` — the Day38 Redis **acceleration-layer design / evidence pack** (a new `redis/` subdirectory in the data-layer artifact): the ownership model (PostgreSQL truth / Object Storage bytes / Redis rebuildable acceleration), a tenant-scoped versioned key contract, a data-structure decision table, TTL and multi-command boundaries, memory/eviction as a correctness concern, RDB/AOF loss windows, Redis-outage degradation, and the missing-TTL incident with prefix-scoped recovery. Every section is labelled **CONCEPTUAL / STATICALLY REVIEWED / RUNTIME NOT RUN / PRODUCTION NOT VALIDATED**, with no real secrets, connection strings, or tenant data.
- Added `cheat_sheets/redis.md` (new file) with the Day38 rapid-reference section and weak-vs-strong answers.

### Changed

- Updated `projects/ai-backend-data-layer/README.md` with the Day38 increment: a design-contents table, the encoded rules, an explicit statement of what the design does not do, Day38 known gaps, a new `redis/` entry in the structure tree, and a separate Day38 validation matrix.
- Appended Day38 Beginner-through-Senior questions to `interview/redis.md`, preserving the student's real answers verbatim — including the missing-key `回PostgreSQL 查询...` answer, the hour-25 TTL answer, the Sorted Set / Set / List reasoning, the tenant-namespace and versioning answers, the `HSET`+`EXPIRE` and two-Worker atomicity answers, the three English answers, and the bounded-fallback answer (the existing Redis interview stub was extended; no duplicate file created).
- Updated `docs/README.md` (added the `redis/` tree and the Day38 lesson as the latest lesson), and pointed the Day37 lesson's Next Lesson at the released Day38 lesson.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day38 completed with its released lesson/artifact (Day39 remains Planned).
- Updated `PROJECT_STATUS.md` (Day38 last completed with artifact + validation boundary; Current/Next is Day39 Planned / Not started), `TASKS.md` (completed Day38 blocks, Day38 preparation converted to history, Day39 preparation added), `README.md`, and `AGENTS.md`.

### Notes

- Day38 adds Redis as **transient acceleration** around the durable PostgreSQL truth, and its spine is that **a missing Redis key is not missing Job truth**: PostgreSQL `app.jobs` owns the authoritative Job lifecycle/audit truth, Object Storage owns large bytes, and Redis owns only small, temporary, **rebuildable** acceleration views plus lightweight broker transport. So an evicted progress key (TTL expiry, `maxmemory` eviction, restart, or RDB/AOF loss) triggers a **controlled PostgreSQL fallback** — never a Job-failed verdict and never a blind Provider re-call — and a whole Job lifecycle under a 24h TTL is rejected because the record simply vanishes at hour 25. Structures are chosen by **access pattern** (String scalar/counter via `INCR`; Hash for named mutable fields, where a JSON String would lose concurrent read-modify-write updates; List ordered-with-duplicates; Set unique membership as a **view**, not ownership; Sorted Set unique-plus-score for recent-100 completions), keys are **tenant-namespaced and versioned** (`ai:tenant:{tenant_id}:job-progress:v1:{job_id}`) with a new version only for an **incompatible** change (not an additive optional field) and logical databases being a namespace, **not** isolation. A **single command is atomic** but a two-command read-modify-write is not, and `HSET` then `EXPIRE` can crash into a permanent key (composition — `MULTI`/`EXEC`, Lua — is Day41); `maxmemory`/eviction is a **correctness** boundary where only rebuildable keys may be evicted; RDB/AOF shrink but never close the loss window and never confer ownership; broker messages carry `job_id` + `tenant_id` + trace metadata (never truth, never a 300 MB PDF) with `202` still returned after the durable Accept; a Redis outage degrades via a **bounded** PostgreSQL fallback that protects the database; and the missing-TTL incident is fixed by a **TTL-config rollback + prefix-scoped `SCAN`/cleanup**, never `FLUSHALL`.

### Validation

- Validation actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); confirmation that no Day39 lesson exists and Day39 remains Planned; LESSON_TEMPLATE_v2 16-section order and heading check; a provenance check asserting every Day38 student quote appears in `Day38_Repository_Update_Input.md`; Markdown fence balance (lesson and artifact); relative-link resolution (including the new `redis/` cross-links and the Day37->Day38 Next Lesson link); status consistency across `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, `AGENTS.md`, and `docs/README.md`; and a secret scan (no real secrets, connection strings, or tenant data in the lesson, artifact, cheat sheet, or interview).
- **Day38 has NO runtime evidence — RUNTIME NOT RUN; PRODUCTION NOT VALIDATED.** No Redis server, `redis-cli`, configuration, key/command, RDB/AOF file, cluster, memory/eviction event, workload, benchmark, or application/Worker/Provider/Object Storage integration was run, measured, or inspected in class or during the repository update. Any figure reused from Day37 is a placeholder, not a measurement. Static reasoning review of every boundary was completed.
- Scope: no Day39 lesson was created; cache consistency, messaging/Streams/Pub-Sub, atomic composition, and full rate limiting are mentioned only as future Day39-41 boundaries; no SQLAlchemy/Alembic or Playwright content was added; the artifact invents no command output, Redis version, benchmark, latency, or memory figure; the protected prompt/template files are unchanged; and no real secrets, connection strings, tenant identifiers, or production data were added.

---

## v0.1.79 — Day37 Review Fixes: completion guard, backup identities, date, timeout wording

Date: 2026-07-23

### Fixed

- **Completion Lease guard was simplified to token-only.** Several Day37 places described the Complete transaction guard as `job_id + current lease_token`, which conflicts with the Day34 ownership model: lease expiry does not change `lease_token`, so before a takeover an expired Worker's token can still equal the current token, and a token-only check would let a Worker that has lost ownership commit `succeeded`. Corrected every Day37 statement to the full guard — `job_id` AND `job_status = 'running'` AND `lease_token` = the current token AND `lease_expires_at > now()` — in the lesson (Objective 3, the transaction-boundary block, Concept 4 review, Mental Model Summary), the runbook (transaction boundaries + an explicit note on why the token alone is unsafe), the cheat sheet, the project README, `PROJECT_STATUS.md`, and this changelog's v0.1.78 note. The student's verbatim classroom answer (which mentions `job_id + lease_token`) was left unchanged; the technical condition is added only in Tech Lead Review / Mental Model / artifact / status summaries.
- **Backup/restore identity boundary.** The runbook's least-privilege role matrix lumped base backup, WAL archive, and restore into one `Backup/restore` role. Split into three least-privilege identities: a **backup/replication database role** (`pg_basebackup`/replication only, no application DML/DDL), a **WAL-archive storage identity** (archiver `archive_command`/`archive_library` or managed service, write-only to the archive store, not an application account), and a **restore operator/control-plane identity** (restore/PITR in an isolated recovery environment; not a production DB role held long-term by API/Workers). The least-privilege summaries in the lesson, cheat sheet, and project README were synced. Kept conceptual — no production commands added.
- **Day37 date.** Corrected the Day37 completion date to `2026-07-23` in `CHANGELOG.md` (the v0.1.78 entry) and `PROJECT_STATUS.md` (Completed Time). Historical Day36-and-earlier dates were not changed.
- **Timeout-matrix wording.** The runbook's application-deadline action `fail/deprecate the operation` used `deprecate`, which is not a runtime timeout action. Changed to `fail/cancel/degrade the operation according to its semantics`.

### Validation

- Static checks actually performed: `git diff --check`; changed-file scope; protected-file check (`prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md` unchanged); a full-repository Completion-guard consistency search confirming both Day34 and Day37 express **current token + `running` + unexpired lease** and that no Day37 text still describes a Job completing on the current token alone (the only remaining `job_id + lease_token` mention is the preserved student quote); a check that the Day37 date is `2026-07-23` in both `CHANGELOG.md` and `PROJECT_STATUS.md`; Markdown fence balance; relative-link resolution; a secret scan (no real secrets, passwords, or connection strings); and confirmation that Day38 remains Planned with no Day38 lesson created.
- **Runtime NOT RUN; Backup/restore drill NOT RUN; Production NOT VALIDATED.** This round changed only wording; no PostgreSQL, connection pool, Vacuum, PITR, failover, or production validation was executed.

---

## v0.1.78 — Day37 PostgreSQL Production Reliability

Date: 2026-07-23

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

- Day37 operates the durable PostgreSQL truth after Day36 made the schema deployable, and its spine is that **a reachable, low-CPU database is not a reliable system**: a slowing AI Job system at modest CPU can be exhausted connection pools, an `idle in transaction` session, and growing pool waits, and API `202` / Worker claim-complete / Attempt writes / Outbox checkpoints all depend on **bounded** capacity. Connection pools are finite, so total demand is the **sum across every process** (`(4 API + 12 Worker) * pool 10 = 160`) that must stay under a **safe connection budget** with reserve for migration/monitoring/admin/recovery — a pool max is potential demand, and raising pools moves queuing into PostgreSQL. The eight-minute Provider call runs **outside** the DB transaction across Accept / Claim-Start / External / Complete (with the full completion guard `job_status = 'running'` AND current `lease_token` AND `lease_expires_at > now()` — not the token alone, since expiry does not change the token — `queued->running` in Claim and `running->succeeded` in Complete), and Provider success, Object Storage Artifact bytes, and committed PostgreSQL success are different facts — reconcile the deterministic Artifact before any second Provider call. Timeouts **contain** failure (`lock_timeout < statement_timeout < application deadline`; `idle_in_transaction_session_timeout` kills stuck open transactions; `SKIP LOCKED` is claim selection, not a timeout); a shared DB outage drops **readiness** and backs off rather than failing every liveness (restart storm); long/idle transactions retain snapshots and block Vacuum so you stop the source first and tune autovacuum per-table on evidence, never a casual `VACUUM FULL`; runtime identities cannot DDL and credentials rotate load-new -> verify-all -> recycle -> revoke-old; replication is **not** backup (it copies bad writes) and recovery evidence requires an isolated restore + PITR + integrity/business checks + measured RPO/RTO (which are recovery objectives, not health probes); and the 420-vs-300 incident is contained by rolling back the **pool configuration** and reconciling irreversible Provider effects, not by raising `max_connections`.
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
