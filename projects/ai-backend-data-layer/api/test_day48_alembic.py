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
    RecoveryBoundary,
    UnsafeRecoveryError,
    apply_lease_evidence,
    classify_unknown_running_recovery,
    count_unresolved_running_without_lease,
    route_to_reconciliation,
    run_backfill,
    select_backfill_batch,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_DIR = os.path.join(HERE, "day48_alembic")
VERSIONS_DIR = os.path.join(ALEMBIC_DIR, "versions")

EXPECTED_CHAIN = [
    "0005_contract_legacy",
    "0004_validate_lease",
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
    assert "ADD COLUMN lease_backfill_state text" in src  # persistent reconciliation marker (nullable)
    assert "DEFAULT" not in src  # no fabricated server default on the new nullable columns
    # The strict Lease constraints must NOT be added in the pure Expand — they
    # belong to the separate constraint revision so old Writers can coexist during
    # Expand. (Assert on the DDL: no ADD CONSTRAINT statement is emitted here.)
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
    # running-without-Lease row remains (reconcile-marked rows included).
    assert "VALIDATE CONSTRAINT jobs_running_requires_lease" in src
    assert 'down_revision = "0003_add_lease_constraints"' in src
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
    assert "lease_backfill_state IS NULL" in sql  # excludes reconciliation-routed Jobs -> terminates
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
    # The apply used a guarded, idempotent UPDATE and cleared the reconcile marker.
    apply_sql = sess.executed[1][0]
    assert "job_status = 'running' AND lease_owner IS NULL" in apply_sql
    assert "lease_backfill_state = NULL" in apply_sql  # resolution clears any triage marker
    assert "RETURNING job_id" in apply_sql
    # The route persisted lease_backfill_state='reconcile' WITHOUT any lease field.
    route_sql = sess.executed[2][0]
    assert "SET lease_backfill_state = 'reconcile'" in route_sql
    assert "lease_owner" not in route_sql.split("WHERE")[0]  # no lease_owner in SET
    assert "lease_token" not in route_sql and "lease_expires_at" not in route_sql
    # The final count query includes reconcile-marked rows (no state filter).
    count_sql = sess.executed[4][0]
    assert "job_status = 'running' AND lease_owner IS NULL" in count_sql
    assert "lease_backfill_state" not in count_sql


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


# 12. Finding 1 — RESTART SAFETY: a Job already routed to reconciliation is no
#     longer a candidate (the query excludes lease_backfill_state IS NOT NULL), so
#     a re-run does not re-select it and cannot loop forever.
def test_backfill_does_not_reselect_reconciled_job_on_restart():
    # Simulate a restart where the previously-routed JOB_B is no longer returned by
    # the candidate query (its lease_backfill_state is now 'reconcile').
    sess = FakeAsyncSession(execute_rows=[[], [(1,)]])  # no auto candidates; 1 still unresolved

    class NoEvidence:
        async def prove(self, job_id):
            return None

    report = asyncio.run(run_backfill(lambda: sess, NoEvidence(), batch_size=100))
    assert report.routed_to_reconciliation == 0
    assert report.backfilled == 0
    # The automatic candidate query excludes reconciliation-routed rows (no re-select)...
    select_sql = sess.executed[0][0]
    assert "lease_backfill_state IS NULL" in select_sql
    # ...but the previously-routed Job is STILL an unresolved running-without-Lease
    # target -> reconcile is triage, NOT resolution; VALIDATE precondition unmet.
    assert report.unresolved_running_without_lease == 1


# 13. Finding 1 — route_to_reconciliation is idempotent/guarded and NEVER fabricates
#     a Lease field; an already-routed row -> 0 rows.
def test_route_to_reconciliation_is_idempotent_and_no_fabrication():
    first = FakeAsyncSession(execute_rows=[[(JOB_A,)]])   # newly routed -> 1 row
    assert asyncio.run(route_to_reconciliation(first, JOB_A)) == 1
    sql = first.executed[0][0]
    assert "job_status = 'running' AND lease_owner IS NULL" in sql  # guarded
    assert "lease_backfill_state IS NULL" in sql                     # not-yet-routed guard
    assert "RETURNING job_id" in sql
    for leaked in ("lease_owner =", "lease_token =", "lease_expires_at ="):
        assert leaked not in sql  # no Lease owner/token/expiry fabricated
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


# 17. R2 Finding 1 — count_unresolved_running_without_lease INCLUDES reconcile-marked
#     rows (no lease_backfill_state filter): being queued is not being resolved.
def test_unresolved_count_includes_reconcile_marked_rows():
    sess = FakeAsyncSession(execute_rows=[[(3,)]])
    n = asyncio.run(count_unresolved_running_without_lease(sess))
    assert n == 3
    sql = sess.executed[0][0]
    assert "count(*)" in sql
    assert "job_status = 'running' AND lease_owner IS NULL" in sql
    assert "lease_backfill_state" not in sql  # reconcile-marked rows are counted too


# 18. R2 Finding 1 — a TRUSTED Lease backfill (resolution a) resolves even a
#     reconcile-parked row: it sets the Lease AND clears the marker, so the row is
#     no longer a running-without-Lease target.
def test_trusted_backfill_resolves_and_clears_marker():
    sess = FakeAsyncSession(execute_rows=[[(JOB_A,)]])  # 1 row updated
    assert asyncio.run(apply_lease_evidence(sess, _evidence(JOB_A))) == 1
    sql = sess.executed[0][0]
    assert "SET lease_owner = :lease_owner" in sql
    assert "lease_backfill_state = NULL" in sql  # marker cleared on resolution
    assert "job_status = 'running' AND lease_owner IS NULL" in sql  # guarded


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


# 20. R2 Finding 1 — VALIDATE precondition is unresolved==0: after a trusted backfill
#     resolves the last parked row, the unresolved count reaches 0 (only THEN may the
#     migration VALIDATE/Switch/Contract). Reaching 0 by routing alone is impossible.
def test_validate_precondition_reached_only_after_real_resolution():
    # Round 1: one unknown Job is routed; unresolved stays 1 (not compliant).
    routed = FakeAsyncSession(execute_rows=[[(JOB_A,)], [(JOB_A,)], [], [(1,)]])

    class NoEvidence:
        async def prove(self, job_id):
            return None

    r1 = asyncio.run(run_backfill(lambda: routed, NoEvidence(), batch_size=100))
    assert r1.routed_to_reconciliation == 1
    assert r1.unresolved_running_without_lease == 1  # queued != resolved

    # Round 2: a trusted source now proves JOB_A; it is backfilled and unresolved -> 0.
    resolved = FakeAsyncSession(execute_rows=[[(JOB_A,)], [(JOB_A,)], [], [(0,)]])

    class KnownNow:
        async def prove(self, job_id):
            return _evidence(job_id)

    r2 = asyncio.run(run_backfill(lambda: resolved, KnownNow(), batch_size=100))
    assert r2.backfilled == 1
    assert r2.unresolved_running_without_lease == 0  # NOW the VALIDATE precondition holds
