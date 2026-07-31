"""Day48 — STATIC Alembic + FAKE-SESSION backfill tests.

EVIDENCE LABELS (read carefully):
  * The Alembic tests are STATIC/OFFLINE: they inspect the revision graph and the
    migration source with Alembic's own ``ScriptDirectory`` (no database, no
    connection). They prove the graph is single-head and linear and that each
    phase (Expand / Validate / Contract) contains the required operations — NOT
    that any migration applied successfully to PostgreSQL.
  * The backfill tests use a FAKE async session and prove CONTROL FLOW only.
  * NONE of this is PostgreSQL runtime evidence. A real ``NOT VALID`` / ``VALIDATE``
    / backfill test needs a disposable PostgreSQL (see the lesson/runbook). SQLite,
    fake sessions, and static checks are NOT PostgreSQL proof, and
    ``alembic upgrade`` success alone does not prove Backfill/Switch/Contract or
    production safety. Executed with pytest via asyncio.run.
"""

import ast
import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from day48_lease_backfill import (
    BackfillReport,
    LeaseEvidence,
    ReconciliationResolutionReport,
    RecoveryBoundary,
    UnsafeRecoveryError,
    apply_lease_evidence,
    classify_unknown_running_recovery,
    close_reconciliation_record,
    count_unresolved_running_without_lease,
    defer_reconciliation_record,
    route_to_reconciliation,
    run_backfill,
    run_reconciliation_resolution,
    select_backfill_batch,
    select_open_reconciliation_batch,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_DIR = os.path.join(HERE, "day48_alembic")
VERSIONS_DIR = os.path.join(ALEMBIC_DIR, "versions")

EXPECTED_CHAIN = [
    "0005_contract_legacy",
    "0004_validate_lease",
    "0003b_add_reconciliation_polling",
    "0003_add_lease_constraints",
    "0002_expand_lease",
    "0001_baseline",
]


def _script() -> ScriptDirectory:
    cfg = Config(os.path.join(ALEMBIC_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    return ScriptDirectory.from_config(cfg)


def _revision_source(revision_file: str) -> str:
    with open(os.path.join(VERSIONS_DIR, revision_file)) as fh:
        return fh.read()


def _function_body_has_loop(source: str, func_name: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for inner in ast.walk(node):
                if isinstance(inner, (ast.For, ast.While, ast.AsyncFor)):
                    return True
    return False


# 1. The revision graph is a SINGLE head and a linear chain 0004->...->0001->None.
def test_revision_graph_is_single_head_and_linear():
    script = _script()
    heads = script.get_heads()
    assert heads == ["0005_contract_legacy"], f"expected one head, got {heads}"
    walked = [rev.revision for rev in script.walk_revisions()]
    assert walked == EXPECTED_CHAIN
    assert script.get_revision("0001_baseline").down_revision is None


# 2. PURE EXPAND: nullable columns with NO fabricated default AND NO Lease
#    constraint — the OLD/NEW compatibility window (old Writers can still write a
#    running-without-Lease row while only Expand is applied).
def test_expand_is_columns_only_no_constraints():
    src = _revision_source("0002_expand_lease.py")
    assert "ADD COLUMN lease_owner text" in src
    assert "ADD COLUMN lease_token uuid" in src
    assert "ADD COLUMN lease_expires_at timestamptz" in src
    # Reconciliation triage is a SEPARATE, independent table — NOT a marker column
    # on app.jobs (a marker UPDATE that left the row running+NULL-Lease would be
    # rejected by 0003's jobs_running_requires_lease). Expand creates that table.
    assert "lease_backfill_state" not in src  # the app.jobs marker column is gone
    assert "CREATE TABLE app.job_lease_reconciliation" in src
    # Revision IMMUTABILITY: the reconciliation POLLING/BACKOFF columns are NOT part
    # of this published revision (a DB that already ran 0002 would not get them by an
    # edit here); they are added forward by 0003b_add_reconciliation_polling.
    assert "next_attempt_at" not in src
    assert "last_checked_at" not in src
    assert "check_attempts" not in src
    # FK to the parent Job with Day42's ON DELETE RESTRICT. The DDL is built from
    # adjacent Python string literals, so drop quotes + collapse whitespace first.
    import re
    flat = re.sub(r"\s+", " ", src.replace('"', " "))
    assert "job_id uuid NOT NULL REFERENCES app.jobs(job_id) ON DELETE RESTRICT" in flat
    assert "UNIQUE (job_id)" in flat  # one triage row per Job -> idempotent routing
    # The strict Lease constraints on app.jobs must NOT be added in the pure Expand —
    # they belong to the separate constraint revision so old Writers can coexist
    # during Expand. (No ALTER TABLE app.jobs ... ADD CONSTRAINT is emitted here.)
    assert "ADD CONSTRAINT" not in src
    assert "VALIDATE CONSTRAINT" not in src
    assert not _function_body_has_loop(src, "upgrade")


# 2b. The CONSTRAINT revision is SEPARATE from Expand, adds the coherence +
#     running-requires-Lease CHECKs (NOT VALID), and documents the drain/isolate
#     precondition (NOT VALID protects every future write, any Writer version).
def test_constraint_revision_is_separate_and_gated():
    src = _revision_source("0003_add_lease_constraints.py")
    assert 'down_revision = "0002_expand_lease"' in src
    assert "jobs_lease_triple_coherent" in src
    assert "jobs_running_requires_lease" in src
    assert "job_status <> 'running'" in src
    assert "NOT VALID" in src
    assert "VALIDATE CONSTRAINT" not in src  # validation is the separate 0004 revision
    # Precondition: OLD Writers must be drained/isolated before this revision.
    low = src.lower()
    assert "drain" in low and ("isolate" in low or "isolated" in low)
    assert "every future" in low or "every future insert/update" in low
    assert not _function_body_has_loop(src, "upgrade")


# 3. VALIDATE is a separate revision that validates BOTH constraints.
def test_validate_is_separate_and_validates():
    src = _revision_source("0004_validate_lease.py")
    assert "VALIDATE CONSTRAINT jobs_lease_triple_coherent" in src
    # The Day36 core invariant is proven over history too — VALIDATE fails while any
    # running-without-Lease row remains (queue-routed rows included).
    assert "VALIDATE CONSTRAINT jobs_running_requires_lease" in src
    assert 'down_revision = "0003b_add_reconciliation_polling"' in src
    assert not _function_body_has_loop(src, "upgrade")


# 4. CONTRACT is destructive (drops the Day42 legacy column) and separately gated.
def test_contract_is_destructive_and_separate():
    src = _revision_source("0005_contract_legacy.py")
    assert 'op.drop_column("jobs", "result_object_key", schema="app")' in src
    assert 'down_revision = "0004_validate_lease"' in src
    # Preconditions must be spelled out (Alembic cannot check them).
    assert "observation period" in src.lower()
    assert "forward-fix" in src.lower()


# 5. No migration upgrade()/downgrade() contains a long loop (no Backfill loops).
def test_no_long_loops_in_any_migration_upgrade():
    for f in os.listdir(VERSIONS_DIR):
        if not f.endswith(".py"):
            continue
        src = _revision_source(f)
        assert not _function_body_has_loop(src, "upgrade"), f"{f} upgrade() has a loop"
        assert not _function_body_has_loop(src, "downgrade"), f"{f} downgrade() has a loop"


# 6. env.py stays a minimal control plane: no FastAPI app and no Day47 UoW import.
def test_env_py_is_minimal_control_plane():
    with open(os.path.join(ALEMBIC_DIR, "env.py")) as fh:
        env = fh.read()
    assert "import fastapi" not in env and "from fastapi" not in env
    assert "FastAPI(" not in env
    assert "day47_async_uow" not in env  # no request/Job UoW in the control plane


# --- Backfill: FAKE-SESSION control flow only (NOT PostgreSQL evidence) --------

JOB_A = uuid.UUID("3b2f1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
JOB_B = uuid.UUID("7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d")


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeAsyncSession:
    def __init__(self, execute_rows=None):
        self._execute_rows = list(execute_rows) if execute_rows is not None else None
        self.executed = []
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.calls.append("close")

    async def execute(self, stmt, params=None):
        self.calls.append("execute")
        self.executed.append((str(stmt), dict(params or {})))
        rows = self._execute_rows.pop(0) if self._execute_rows is not None else []
        return FakeResult(rows)

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")


def _evidence(job_id):
    return LeaseEvidence(
        job_id=job_id,
        lease_owner="worker-7",
        lease_token=uuid.uuid4(),
        lease_expires_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )


# 7. The batch selection locks with FOR UPDATE SKIP LOCKED and only running+unowned.
def test_backfill_batch_uses_skip_locked_and_running_unowned():
    sess = FakeAsyncSession(execute_rows=[[(JOB_A,), (JOB_B,)]])
    ids = asyncio.run(select_backfill_batch(sess, batch_size=100))
    assert ids == [JOB_A, JOB_B]
    sql, params = sess.executed[0]
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "job_status = 'running'" in sql and "lease_owner IS NULL" in sql
    # Routed Jobs are excluded via the INDEPENDENT queue table (NOT a marker column),
    # which is what makes the automatic loop terminate + be restart-safe.
    assert "NOT EXISTS" in sql
    assert "app.job_lease_reconciliation" in sql
    assert "lease_backfill_state" not in sql
    assert params["batch_size"] == 100


# 8. run_backfill fills known-ownership Jobs and ROUTES unknown ones to a
#    PERSISTENT reconciliation marker (no fabrication).
def test_backfill_fills_known_and_routes_unknown_for_reconciliation():
    # batch 1: [JOB_A known, JOB_B unknown] -> apply JOB_A, route JOB_B; batch 2 empty.
    sess = FakeAsyncSession(
        execute_rows=[
            [(JOB_A,), (JOB_B,)],  # select batch 1
            [(JOB_A,)],            # apply evidence for JOB_A -> 1 row (marker cleared)
            [(JOB_B,)],            # route JOB_B to reconciliation -> 1 row
            [],                    # select batch 2 -> empty (automatic loop terminates)
            [(1,)],                # final unresolved count -> JOB_B still unresolved
        ]
    )

    class Source:
        async def prove(self, job_id):
            return _evidence(job_id) if job_id == JOB_A else None  # JOB_B unknown

    report = asyncio.run(run_backfill(lambda: sess, Source(), batch_size=100))
    assert isinstance(report, BackfillReport)
    assert report.backfilled == 1                 # only JOB_A had trusted evidence
    assert report.routed_to_reconciliation == 1   # JOB_B persistently routed, not fabricated
    # Reconcile is TRIAGE, not RESOLUTION: JOB_B STILL counts as unresolved.
    assert report.unresolved_running_without_lease == 1
    assert sess.calls.count("commit") == 1        # one batch committed
    # The apply used a guarded, idempotent UPDATE on app.jobs and set ONLY the Lease
    # triple (single responsibility — it does NOT touch the reconciliation queue).
    apply_sql = sess.executed[1][0]
    assert "UPDATE app.jobs" in apply_sql
    assert "job_status = 'running' AND lease_owner IS NULL" in apply_sql
    assert "lease_backfill_state" not in apply_sql
    assert "job_lease_reconciliation" not in apply_sql
    assert "RETURNING job_id" in apply_sql
    # The route INSERTed into the INDEPENDENT queue table WITHOUT touching app.jobs
    # and WITHOUT fabricating any Lease field — CRITICAL so it is legal after the
    # strict jobs_running_requires_lease constraint (no violating app.jobs UPDATE).
    route_sql = sess.executed[2][0]
    assert "INSERT INTO app.job_lease_reconciliation" in route_sql
    assert "ON CONFLICT (job_id) DO NOTHING" in route_sql
    assert "UPDATE app.jobs" not in route_sql
    assert "app.jobs" not in route_sql  # routing performs NO write against the business row
    for leaked in ("lease_owner", "lease_token", "lease_expires_at"):
        assert leaked not in route_sql  # no Lease owner/token/expiry fabricated
    # The final count query targets app.jobs and includes routed rows (no queue join).
    count_sql = sess.executed[4][0]
    assert "job_status = 'running' AND lease_owner IS NULL" in count_sql
    assert "lease_backfill_state" not in count_sql
    assert "job_lease_reconciliation" not in count_sql


# 9. apply_lease_evidence is idempotent/restartable: an already-owned row -> 0 rows.
def test_apply_lease_evidence_is_idempotent():
    first = FakeAsyncSession(execute_rows=[[(JOB_A,)]])   # newly owned -> 1 row
    assert asyncio.run(apply_lease_evidence(first, _evidence(JOB_A))) == 1
    again = FakeAsyncSession(execute_rows=[[]])            # already owned -> 0 rows
    assert asyncio.run(apply_lease_evidence(again, _evidence(JOB_A))) == 0


# 10. The backfill performs NO Provider call: it imports no Provider seam and makes
#     no generate/run call (prose reminders like "never re-call the Provider" are OK).
def test_backfill_module_calls_no_provider():
    import day48_lease_backfill as m
    src = open(m.__file__).read()
    assert "AIProvider" not in src        # no Provider interface imported/used
    assert "FakeProvider" not in src      # no Provider double
    assert ".generate(" not in src        # no Provider generate() call
    assert "day45_composition" not in src # no Provider seam import


# 11. Finding 1 — TERMINATION: when EVERY candidate lacks trusted evidence, the
#     backfill routes them all to reconciliation and STOPS (no infinite loop),
#     even with the default max_batches=None.
def test_backfill_terminates_when_all_candidates_unknown():
    # batch 1: two unknown jobs -> both routed; batch 2 empty -> stop.
    sess = FakeAsyncSession(
        execute_rows=[
            [(JOB_A,), (JOB_B,)],  # select batch 1
            [(JOB_A,)],            # route JOB_A -> 1 row
            [(JOB_B,)],            # route JOB_B -> 1 row
            [],                    # select batch 2 -> empty (automatic loop terminates)
            [(2,)],                # final unresolved count -> both still unresolved
        ]
    )

    class NoEvidence:
        async def prove(self, job_id):
            return None  # nothing is provable

    report = asyncio.run(run_backfill(lambda: sess, NoEvidence(), batch_size=100))  # max_batches=None
    assert report.backfilled == 0
    assert report.routed_to_reconciliation == 2
    # The automatic loop STOPPED but the migration is INCOMPLETE: both remain unresolved.
    assert report.unresolved_running_without_lease == 2
    assert sess.calls.count("execute") == 5  # 2 selects + 2 routes + 1 final count


# 12. Finding 1 — RESTART SAFETY: a Job already routed to the reconciliation queue
#     is no longer a candidate (the NOT EXISTS join against
#     app.job_lease_reconciliation excludes it), so a re-run does not re-select it
#     and cannot loop forever.
def test_backfill_does_not_reselect_reconciled_job_on_restart():
    # Simulate a restart where the previously-routed JOB_B is no longer returned by
    # the candidate query (a row for it already exists in the reconciliation queue).
    sess = FakeAsyncSession(execute_rows=[[], [(1,)]])  # no auto candidates; 1 still unresolved

    class NoEvidence:
        async def prove(self, job_id):
            return None

    report = asyncio.run(run_backfill(lambda: sess, NoEvidence(), batch_size=100))
    assert report.routed_to_reconciliation == 0
    assert report.backfilled == 0
    # The automatic candidate query excludes queued Jobs via NOT EXISTS (no re-select)...
    select_sql = sess.executed[0][0]
    assert "NOT EXISTS" in select_sql and "app.job_lease_reconciliation" in select_sql
    # ...but the previously-routed Job is STILL an unresolved running-without-Lease
    # target -> queuing is triage, NOT resolution; VALIDATE precondition unmet.
    assert report.unresolved_running_without_lease == 1


# 13. Finding 1 (round 4) — route_to_reconciliation writes ONLY the independent
#     queue table (NEVER app.jobs, so it is legal after the strict constraint), is
#     idempotent via ON CONFLICT DO NOTHING, and fabricates NO Lease field.
def test_route_to_reconciliation_writes_queue_only_and_no_fabrication():
    first = FakeAsyncSession(execute_rows=[[(uuid.uuid4(),)]])   # newly routed -> 1 row
    assert asyncio.run(route_to_reconciliation(first, JOB_A)) == 1
    sql, params = first.executed[0]
    # It writes the queue, not the business row — the key round-4 safety property.
    assert "INSERT INTO app.job_lease_reconciliation" in sql
    assert "UPDATE app.jobs" not in sql
    assert "app.jobs" not in sql  # no write against the running+NULL-Lease row
    assert "ON CONFLICT (job_id) DO NOTHING" in sql  # idempotent / restart-safe
    assert "RETURNING reconciliation_id" in sql
    assert params["job_id"] == JOB_A
    for leaked in ("lease_owner", "lease_token", "lease_expires_at"):
        assert leaked not in sql  # no Lease owner/token/expiry fabricated
    # Re-routing the same Job is a no-op (0 rows) -> restart-safe.
    again = FakeAsyncSession(execute_rows=[[]])
    assert asyncio.run(route_to_reconciliation(again, JOB_A)) == 0
    again = FakeAsyncSession(execute_rows=[[]])            # already routed -> 0 rows
    assert asyncio.run(route_to_reconciliation(again, JOB_A)) == 0


# --- Finding 2: database URL override resolution (static, no DB) ---------------

def _load_env_module():
    """Import env.py by file path. It is import-safe (its migration block is
    skipped outside an Alembic run), so `resolve_database_url` is unit-testable."""
    import importlib.util

    path = os.path.join(ALEMBIC_DIR, "env.py")
    spec = importlib.util.spec_from_file_location("day48_env_undertest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 14. Finding 2 — priority is -x db_url > env var; the ini placeholder is used ONLY
#     in offline mode (allow_placeholder=True), never as an online fallback.
def test_database_url_override_priority_and_offline_placeholder():
    env = _load_env_module()
    resolve = env.resolve_database_url
    x = {"db_url": "postgresql://h/from_xarg"}
    e = {"DAY48_ALEMBIC_DATABASE_URL": "postgresql://h/from_env"}
    ini = "postgresql://localhost/appdb_placeholder"
    # -x wins over env in BOTH modes.
    assert resolve(x, e, ini, allow_placeholder=True) == "postgresql://h/from_xarg"
    assert resolve(x, e, ini, allow_placeholder=False) == "postgresql://h/from_xarg"
    # env var is the online fallback (no -x), in both modes.
    assert resolve({}, e, ini, allow_placeholder=False) == "postgresql://h/from_env"
    assert resolve({}, e, ini, allow_placeholder=True) == "postgresql://h/from_env"
    # OFFLINE with no external URL -> the ini placeholder is allowed.
    assert resolve({}, {}, ini, allow_placeholder=True) == ini


# 15. Finding 2 — ONLINE with no external URL FAILS FAST (never the ini placeholder).
def test_online_requires_external_url_no_placeholder_fallback():
    env = _load_env_module()
    ini = "postgresql://localhost/appdb_placeholder"
    with pytest.raises(RuntimeError):
        env.resolve_database_url({}, {}, ini, allow_placeholder=False)  # online, no -x/env
    with pytest.raises(RuntimeError):
        env.resolve_database_url({}, {}, None, allow_placeholder=True)   # offline, but no url at all


# 16. Finding 2 — env.py and alembic.ini document the placeholder as OFFLINE-only
#     (not a production connection) and name the env-var override.
def test_url_config_docs_are_consistent():
    with open(os.path.join(ALEMBIC_DIR, "env.py")) as fh:
        env_src = fh.read()
    with open(os.path.join(ALEMBIC_DIR, "alembic.ini")) as fh:
        ini_src = fh.read()
    # env.py actually reads the -x argument and the env var.
    assert "get_x_argument" in env_src and "db_url" in env_src
    assert "DAY48_ALEMBIC_DATABASE_URL" in env_src
    # Both files name the env var and describe the ini URL as an offline placeholder.
    assert "DAY48_ALEMBIC_DATABASE_URL" in ini_src
    assert "placeholder" in ini_src.lower() and "offline" in ini_src.lower()
    assert "not a production" in ini_src.lower()
    # Both files state the placeholder is NOT an online connection fallback.
    assert "not an online connection fallback" in ini_src.lower()
    assert "never an online connection fallback" in env_src.lower() or "fails fast" in env_src.lower()


# 17. R2 Finding 1 — count_unresolved_running_without_lease counts EVERY running
#     app.jobs row with a NULL Lease, INCLUDING Jobs routed to the reconciliation
#     queue (routing does not change app.jobs, so being queued is not being resolved).
def test_unresolved_count_includes_reconciliation_routed_rows():
    sess = FakeAsyncSession(execute_rows=[[(3,)]])
    n = asyncio.run(count_unresolved_running_without_lease(sess))
    assert n == 3
    sql = sess.executed[0][0]
    assert "count(*)" in sql
    assert "FROM app.jobs" in sql
    assert "job_status = 'running' AND lease_owner IS NULL" in sql
    # It does NOT subtract queued Jobs — no join/anti-join against the queue table.
    assert "job_lease_reconciliation" not in sql
    assert "lease_backfill_state" not in sql


# 18. R2 Finding 1 — a TRUSTED Lease backfill (resolution a) resolves even a
#     reconciliation-routed row: it sets the Lease triple on app.jobs, so the row
#     satisfies jobs_running_requires_lease and is no longer an unresolved target.
#     Closing the queue record is a SEPARATE audited step (single responsibility).
def test_trusted_backfill_resolves_running_without_lease():
    sess = FakeAsyncSession(execute_rows=[[(JOB_A,)]])  # 1 row updated
    assert asyncio.run(apply_lease_evidence(sess, _evidence(JOB_A))) == 1
    sql = sess.executed[0][0]
    assert "UPDATE app.jobs" in sql
    assert "SET lease_owner = :lease_owner" in sql
    assert "job_status = 'running' AND lease_owner IS NULL" in sql  # guarded
    # It writes ONLY app.jobs: no marker column, no queue write in the same statement.
    assert "lease_backfill_state" not in sql
    assert "job_lease_reconciliation" not in sql


# 19. R3 Finding 2 — recovery ROUTING (no DB mutation). An unknown outcome stays
#     unknown; verified succeeded -> Day47 completion UoW; failed/cancelled ->
#     guarded terminal-recovery; a requeue ('queued') / 'running' / bad status is
#     REFUSED. This function performs NO bare status UPDATE.
def test_unknown_outcome_recovery_routing_and_refusals():
    # Unknown outcome -> keep unknown / reconciliation (never requeue, never retry).
    assert classify_unknown_running_recovery(None) is RecoveryBoundary.KEEP_UNKNOWN
    # Verified success needs the Day47 guarded completion UoW (finished_at+Artifact+Event).
    assert classify_unknown_running_recovery("succeeded") is RecoveryBoundary.COMPLETION_UOW
    # Verified failure/cancellation needs the guarded terminal-recovery path.
    assert classify_unknown_running_recovery("failed") is RecoveryBoundary.GUARDED_TERMINAL_RECOVERY
    assert classify_unknown_running_recovery("cancelled") is RecoveryBoundary.GUARDED_TERMINAL_RECOVERY
    # A requeue of an unknown Job is FORBIDDEN (clears the count without proof).
    with pytest.raises(UnsafeRecoveryError):
        classify_unknown_running_recovery("queued")
    # 'running' and any non-terminal / unexpected status are refused too.
    with pytest.raises(UnsafeRecoveryError):
        classify_unknown_running_recovery("running")
    with pytest.raises(UnsafeRecoveryError):
        classify_unknown_running_recovery("banana")


# 19b. R3 Finding 2 — the router is a pure classifier: importing/using it touches NO
#      session and issues NO SQL (no bare status flip that could bypass Day47 facts).
def test_recovery_routing_issues_no_sql():
    # A fresh fake session must remain untouched by classification.
    sess = FakeAsyncSession()
    classify_unknown_running_recovery("succeeded")
    classify_unknown_running_recovery(None)
    assert sess.executed == [] and sess.calls == []
    # And the dangerous bare-mutation helper no longer exists.
    import day48_lease_backfill as m
    assert not hasattr(m, "resolve_by_verified_terminal_state")


# 20. R2 Finding 1 / R5 Finding 1 — VALIDATE precondition is unresolved==0. A routed
#     Job is NOT re-selected by the AUTOMATIC loop (matching real SQL); it is resolved
#     later by the DEDICATED reconciliation-resolution path, and ONLY a real Lease
#     write drives unresolved -> 0 (only THEN may the migration VALIDATE/Switch/Contract).
def test_validate_precondition_reached_only_after_real_resolution():
    # Round 1: one unknown Job is routed by the AUTOMATIC loop; unresolved stays 1.
    #   selects [(JOB_A)], route -> [(rec_id)], select [] (stop), final count -> [(1)].
    routed = FakeAsyncSession(execute_rows=[[(JOB_A,)], [(uuid.uuid4(),)], [], [(1,)]])

    class NoEvidence:
        async def prove(self, job_id):
            return None

    r1 = asyncio.run(run_backfill(lambda: routed, NoEvidence(), batch_size=100))
    assert r1.routed_to_reconciliation == 1
    assert r1.unresolved_running_without_lease == 1  # queued != resolved

    # Round 2 (WRONG path): the AUTOMATIC loop can NEVER resolve a queued Job — its
    # candidate query excludes queued Jobs, so a re-run selects nothing and does
    # nothing, exactly as real SQL behaves. This is why a dedicated path is required.
    auto_again = FakeAsyncSession(execute_rows=[[], [(1,)]])  # empty select; still 1 unresolved

    class KnownNow:
        async def prove(self, job_id):
            return _evidence(job_id)

    r_auto = asyncio.run(run_backfill(lambda: auto_again, KnownNow(), batch_size=100))
    assert r_auto.backfilled == 0
    assert r_auto.unresolved_running_without_lease == 1  # automatic loop cannot touch a routed Job

    # Round 2 (RIGHT path): the dedicated resolution path selects the OPEN record,
    #   writes the Lease (apply -> [(JOB_A)]), closes the record (close -> [(rec_id)]),
    #   next select [] (stop), final count -> [(0)].
    resolve = FakeAsyncSession(
        execute_rows=[[(JOB_A,)], [(JOB_A,)], [(uuid.uuid4(),)], [], [(0,)]]
    )
    r2 = asyncio.run(
        run_reconciliation_resolution(lambda: resolve, KnownNow(), batch_size=100)
    )
    assert isinstance(r2, ReconciliationResolutionReport)
    assert r2.resolved == 1
    assert r2.still_open == 0
    assert r2.unresolved_running_without_lease == 0  # NOW the VALIDATE precondition holds
    # The Lease UPDATE ran on app.jobs; the record close ran on the queue, same tx.
    apply_sql = resolve.executed[1][0]
    close_sql = resolve.executed[2][0]
    assert "UPDATE app.jobs" in apply_sql and "SET lease_owner" in apply_sql
    assert "UPDATE app.job_lease_reconciliation" in close_sql
    assert resolve.calls.count("commit") == 1  # one batch committed


# 21. Finding 1 (round 4) — close_reconciliation_record is the SEPARATE audit step
#     that marks a queue row 'resolved' AFTER the Job is truthfully resolved. It
#     touches ONLY the queue table (never app.jobs) and is idempotent.
def test_close_reconciliation_record_is_audit_only_and_idempotent():
    sess = FakeAsyncSession(execute_rows=[[(uuid.uuid4(),)]])  # 1 open record closed
    assert asyncio.run(close_reconciliation_record(sess, JOB_A)) == 1
    sql, params = sess.executed[0]
    assert "UPDATE app.job_lease_reconciliation" in sql
    assert "resolution_status = 'resolved'" in sql
    assert "resolution_status = 'open'" in sql  # guarded: only closes an OPEN record
    assert "app.jobs" not in sql                # NEVER mutates the business row
    assert params["job_id"] == JOB_A
    # Already-closed / absent record -> 0 rows (idempotent).
    again = FakeAsyncSession(execute_rows=[[]])
    assert asyncio.run(close_reconciliation_record(again, JOB_A)) == 0


# 22. Finding 1 (round 4) — the ordering invariant this fix depends on: routing runs
#     AFTER the strict 0003 constraint, and it is legal ONLY because NO backfill
#     statement issues a violating UPDATE on app.jobs (which would set/keep the row
#     running with a NULL Lease and be rejected). Assert it structurally across the
#     whole backfill module: no UPDATE app.jobs anywhere sets a reconcile marker.
def test_no_backfill_statement_issues_a_violating_app_jobs_update():
    import day48_lease_backfill as m
    src = open(m.__file__).read()
    # The only UPDATE app.jobs is apply_lease_evidence, which SETS the Lease triple
    # (making the row compliant) — never a marker that leaves it running+NULL-Lease.
    assert "lease_backfill_state" not in src
    assert "SET lease_backfill_state" not in src
    # Routing and closing target the independent queue table, not app.jobs.
    assert "INSERT INTO app.job_lease_reconciliation" in src
    assert "UPDATE app.job_lease_reconciliation" in src
    # Fake-session control-flow tests above are NOT PostgreSQL proof that the
    # strict constraint would accept these statements — see the module docstring.


# --- R5 Finding 1: the DEDICATED reconciliation-resolution path -----------------
# These remain FAKE-SESSION control-flow tests: they assert the SQL shape and the
# ordering (Lease write must precede the record close), NOT that PostgreSQL would run
# them. A real run needs PostgreSQL + the 0002/0003 revisions applied.

# 23. The AUTOMATIC candidate query never re-selects a queued Job (matching real SQL:
#     once a queue row exists the Job is excluded), and the DEDICATED resolution
#     selector is the ONLY one that revisits an OPEN record — locking with
#     FOR UPDATE ... SKIP LOCKED and requiring the Job still running + unowned.
def test_open_reconciliation_record_selected_only_by_resolution_path():
    # Automatic selector: excludes queued Jobs via NOT EXISTS against the queue.
    auto = FakeAsyncSession(execute_rows=[[]])
    asyncio.run(select_backfill_batch(auto, batch_size=50))
    auto_sql = auto.executed[0][0]
    assert "NOT EXISTS" in auto_sql and "app.job_lease_reconciliation" in auto_sql
    # Resolution selector: OPEN records whose Job is still running + unowned, locked.
    res = FakeAsyncSession(execute_rows=[[(JOB_A,)]])
    ids = asyncio.run(select_open_reconciliation_batch(res, batch_size=50))
    assert ids == [JOB_A]
    res_sql, params = res.executed[0]
    assert "FROM app.job_lease_reconciliation r" in res_sql
    assert "JOIN app.jobs j ON j.job_id = r.job_id" in res_sql
    assert "r.resolution_status = 'open'" in res_sql
    assert "r.next_attempt_at <= now()" in res_sql  # only DUE records (backoff gate)
    assert "j.job_status = 'running' AND j.lease_owner IS NULL" in res_sql
    assert "FOR UPDATE OF r SKIP LOCKED" in res_sql
    assert params["batch_size"] == 50


# 24. When trusted evidence appears LATER, the dedicated path writes the Lease AND
#     closes the record — in that order, in one short tx (one commit per batch).
def test_reconciliation_resolution_writes_lease_then_closes_record():
    # select [(JOB_A)] -> apply [(JOB_A)] -> close [(rec_id)] -> select [] -> count [(0)].
    sess = FakeAsyncSession(
        execute_rows=[[(JOB_A,)], [(JOB_A,)], [(uuid.uuid4(),)], [], [(0,)]]
    )

    class KnownNow:
        async def prove(self, job_id):
            return _evidence(job_id)

    report = asyncio.run(
        run_reconciliation_resolution(lambda: sess, KnownNow(), batch_size=100)
    )
    assert report.resolved == 1 and report.still_open == 0
    assert report.unresolved_running_without_lease == 0
    # Order: the guarded app.jobs UPDATE comes BEFORE the queue-record close.
    assert "UPDATE app.jobs" in sess.executed[1][0]
    assert "UPDATE app.job_lease_reconciliation" in sess.executed[2][0]
    assert sess.calls.index("commit") > sess.calls.index("execute")


# 25. With NO trusted evidence, an OPEN record stays OPEN but is DEFERRED with a
#     queue-only backoff: no Lease fabricated, no requeue, no app.jobs write, no
#     Provider — and the record is NOT closed (resolution_status stays 'open').
def test_reconciliation_resolution_defers_open_record_without_evidence():
    # select [(JOB_A)] -> defer [(rec_id)] -> select [] -> count [(1)].
    sess = FakeAsyncSession(execute_rows=[[(JOB_A,)], [(uuid.uuid4(),)], [], [(1,)]])

    class NoEvidence:
        async def prove(self, job_id):
            return None

    report = asyncio.run(
        run_reconciliation_resolution(lambda: sess, NoEvidence(), batch_size=100)
    )
    assert report.resolved == 0 and report.still_open == 1
    assert report.unresolved_running_without_lease == 1  # still a remaining_target
    # The only write is the queue-only DEFER: it pushes next_attempt_at forward and
    # bumps check_attempts; it never touches app.jobs and never closes the record.
    defer_sql = sess.executed[1][0]
    assert "UPDATE app.job_lease_reconciliation" in defer_sql
    assert "next_attempt_at = now() + make_interval" in defer_sql
    assert "check_attempts = check_attempts + 1" in defer_sql
    assert "resolution_status = 'resolved'" not in defer_sql  # NOT closed
    assert "resolution_status = 'open'" in defer_sql          # guarded on open
    for sql, _ in sess.executed:
        assert "UPDATE app.jobs" not in sql


# 26. Idempotent / restartable: an ALREADY-resolved record (or an already-owned Job)
#     is not re-selected (the selector filters resolved records + owned Jobs), so a
#     re-run is a clean no-op that resolves nothing and stays at unresolved == 0.
def test_reconciliation_resolution_rerun_is_noop():
    sess = FakeAsyncSession(execute_rows=[[], [(0,)]])  # nothing open+running+unowned

    class KnownNow:
        async def prove(self, job_id):
            return _evidence(job_id)

    report = asyncio.run(
        run_reconciliation_resolution(lambda: sess, KnownNow(), batch_size=100)
    )
    assert report.resolved == 0 and report.still_open == 0
    assert report.unresolved_running_without_lease == 0


# 27. If the guarded app.jobs UPDATE affects 0 rows (the Job no longer matches
#     running + unowned — e.g. concurrently resolved), THIS pass must NOT close the
#     record on its own behalf: closing is gated on this UoW's own successful write.
def test_reconciliation_resolution_does_not_close_when_update_affects_zero_rows():
    # select [(JOB_A)] -> apply [] (0 rows) -> (NO close) -> select [] -> count [(1)].
    sess = FakeAsyncSession(execute_rows=[[(JOB_A,)], [], [], [(1,)]])

    class KnownNow:
        async def prove(self, job_id):
            return _evidence(job_id)

    report = asyncio.run(
        run_reconciliation_resolution(lambda: sess, KnownNow(), batch_size=100)
    )
    assert report.resolved == 0 and report.still_open == 1
    # The apply UPDATE ran but affected 0 rows; NO close statement was issued.
    assert "UPDATE app.jobs" in sess.executed[1][0]
    assert all("UPDATE app.job_lease_reconciliation" not in sql for sql, _ in sess.executed)
    assert report.unresolved_running_without_lease == 1


# 28. The resolution path calls NO Provider and never fabricates/ requeues/ bare-flips.
def test_reconciliation_resolution_no_provider_no_fabrication():
    import day48_lease_backfill as m
    src = open(m.__file__).read()
    assert ".generate(" not in src and "AIProvider" not in src
    # close only ever moves 'open' -> 'resolved'; never sets a Lease or a Job status.
    assert "resolution_status = 'resolved'" in src
    assert "SET job_status" not in src  # no bare status flip anywhere in the module


# --- R6 Finding 1: reconciliation POLLING/BACKOFF (not Job/Provider retry) -------
# Still FAKE-SESSION / static control-flow evidence, NOT PostgreSQL runtime proof.

# 29. defer_reconciliation_record is a QUEUE-ONLY, guarded, audited backoff write: it
#     bumps check_attempts + last_checked_at and pushes next_attempt_at forward by an
#     exponential capped interval — never touching app.jobs, never closing the record,
#     never fabricating a Lease / requeuing / flipping a status / calling a Provider.
def test_defer_reconciliation_record_is_queue_only_backoff():
    sess = FakeAsyncSession(execute_rows=[[(uuid.uuid4(),)]])  # 1 open record deferred
    n = asyncio.run(defer_reconciliation_record(sess, JOB_A))
    assert n == 1
    sql, params = sess.executed[0]
    assert "UPDATE app.job_lease_reconciliation" in sql
    assert "check_attempts = check_attempts + 1" in sql
    assert "last_checked_at = now()" in sql
    assert "next_attempt_at = now() + make_interval" in sql  # pushed into the FUTURE
    assert "LEAST(" in sql                                    # capped exponential backoff
    assert "WHERE job_id = :job_id AND resolution_status = 'open'" in sql  # guarded
    assert "app.jobs" not in sql                             # queue-only, no business row
    assert "resolution_status = 'resolved'" not in sql       # NOT a close
    assert params["job_id"] == JOB_A
    assert params["base_backoff_seconds"] >= 1 and params["max_backoff_seconds"] >= params["base_backoff_seconds"]


# 30. TERMINATION without an evidence: run_reconciliation_resolution(max_batches=None)
#     must NOT reprocess the same OPEN record forever. Termination rests on the
#     due-filter (next_attempt_at <= now()) PLUS the forward backoff written by defer
#     — NOT on a fake session arbitrarily returning an empty batch. This fake MODELS
#     real SQL: the record is "due" until a defer pushes next_attempt_at past now(),
#     after which the selector no longer returns it.
def test_reconciliation_resolution_terminates_via_due_filter_and_backoff():
    state = {"due": True, "defers": 0}

    class DueModelingSession:
        def __init__(self):
            self.executed = []
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            self.calls.append("close")

        async def execute(self, stmt, params=None):
            sql = str(stmt)
            self.executed.append((sql, dict(params or {})))
            self.calls.append("execute")
            if "SELECT r.job_id" in sql and "FROM app.job_lease_reconciliation r" in sql:
                # Selector returns the record ONLY while it is due (models the SQL
                # predicate next_attempt_at <= now()).
                return FakeResult([(JOB_A,)] if state["due"] else [])
            if "check_attempts = check_attempts + 1" in sql:
                # A defer pushes next_attempt_at into the future -> no longer due.
                state["due"] = False
                state["defers"] += 1
                return FakeResult([(uuid.uuid4(),)])
            if "count(*)" in sql:
                return FakeResult([(1,)])
            return FakeResult([])

        async def commit(self):
            self.calls.append("commit")

        async def rollback(self):
            self.calls.append("rollback")

    class NoEvidence:
        async def prove(self, job_id):
            return None

    report = asyncio.run(
        run_reconciliation_resolution(
            lambda: DueModelingSession(), NoEvidence(), batch_size=100, max_batches=None
        )
    )
    # The record was deferred EXACTLY once and then not re-selected — the loop ended
    # because the defer made it not-due, NOT because of an arbitrary empty fake batch.
    assert state["defers"] == 1
    assert report.still_open == 1
    assert report.unresolved_running_without_lease == 1


# 31. DUE-FILTER + BACKOFF are what guarantee termination — assert BOTH facts on the
#     module source so the argument does not rest on any single mocked batch.
def test_termination_rests_on_due_filter_plus_forward_backoff():
    import day48_lease_backfill as m
    src = open(m.__file__).read()
    # (a) the resolver selects ONLY due records ...
    assert "r.next_attempt_at <= now()" in src
    # (b) ... and a fruitless check pushes next_attempt_at into the FUTURE.
    assert "next_attempt_at = now() + make_interval" in src
    # This is reconciliation POLLING, explicitly NOT Job retry or Provider retry.
    assert "POLLING" in src and "NOT Job retry" in src
    assert ".generate(" not in src  # never a Provider retry


# --- R7: reconciliation polling columns live in a SEPARATE additive revision ------
# (revision immutability: 0002 may already be applied, so the columns are added
#  forward). Still FAKE-SESSION / static evidence, NOT PostgreSQL runtime proof.

# 32. The additive polling revision is ADD COLUMN only (never CREATE TABLE / never a
#     table rewrite of app.jobs), sits AFTER 0003 and BEFORE 0004, and carries all
#     three required columns + the nonneg CHECK + the partial due-index.
def test_reconciliation_polling_is_a_separate_additive_revision():
    src = _revision_source("0003b_add_reconciliation_polling.py")
    assert 'revision = "0003b_add_reconciliation_polling"' in src
    assert 'down_revision = "0003_add_lease_constraints"' in src  # after strict constraints
    # Additive columns on the INDEPENDENT queue table (not app.jobs, not a rewrite).
    assert "ALTER TABLE app.job_lease_reconciliation" in src
    assert "ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now()" in src
    assert "ADD COLUMN last_checked_at timestamptz" in src
    assert "ADD COLUMN check_attempts  integer NOT NULL DEFAULT 0" in src
    assert "CHECK (check_attempts >= 0)" in src
    # A partial index matching the resolver's due-scan.
    assert "CREATE INDEX" in src and "ix_job_lease_reconciliation_due" in src
    assert "WHERE resolution_status = 'open'" in src
    # It must NOT create the table (that is 0002's job) and must NOT ALTER app.jobs.
    assert "CREATE TABLE" not in src
    assert "ALTER TABLE app.jobs" not in src
    # No long data-backfill loop lives in the migration upgrade().
    assert not _function_body_has_loop(src, "upgrade")


# 33. Validate is rewired onto the new revision (unapplied later revisions may safely
#     change down_revision); the chain stays single-head + linear (asserted broadly
#     by test_revision_graph_is_single_head_and_linear via EXPECTED_CHAIN).
def test_validate_revision_follows_the_polling_revision():
    src = _revision_source("0004_validate_lease.py")
    assert 'down_revision = "0003b_add_reconciliation_polling"' in src


# 34. The resolver's SQL fields MATCH the migration DDL: every reconciliation column
#     the runtime reads/writes (next_attempt_at, last_checked_at, check_attempts) is
#     actually created by 0003b — so the resolver cannot reference a missing column.
def test_resolver_fields_match_migration_ddl():
    import day48_lease_backfill as m
    code = open(m.__file__).read()
    ddl = _revision_source("0003b_add_reconciliation_polling.py")
    for col in ("next_attempt_at", "last_checked_at", "check_attempts"):
        assert col in code, f"resolver never uses {col}"
        assert col in ddl, f"migration never creates {col}"
    # The columns are NOT (re)defined by the historical CREATE TABLE in 0002.
    expand = _revision_source("0002_expand_lease.py")
    for col in ("next_attempt_at", "last_checked_at", "check_attempts"):
        assert col not in expand


# 35. HONESTY: every check above is static source / fake-session control flow. It
#     proves the revision GRAPH and DDL/resolver column agreement, NOT that
#     PostgreSQL applied 0003b, evaluated now()/make_interval, or that the partial
#     index is used — that requires a real PostgreSQL run (see the runbook).
def test_polling_revision_evidence_is_static_not_postgres_runtime():
    import day48_lease_backfill as m
    src = open(m.__file__).read()
    assert "NOT PostgreSQL proof" in src  # the module states its evidence boundary
