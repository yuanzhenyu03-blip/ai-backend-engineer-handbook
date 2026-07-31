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
    apply_lease_evidence,
    run_backfill,
    select_backfill_batch,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_DIR = os.path.join(HERE, "day48_alembic")
VERSIONS_DIR = os.path.join(ALEMBIC_DIR, "versions")

EXPECTED_CHAIN = [
    "0004_contract_legacy",
    "0003_validate_lease",
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
    assert heads == ["0004_contract_legacy"], f"expected one head, got {heads}"
    walked = [rev.revision for rev in script.walk_revisions()]
    assert walked == EXPECTED_CHAIN
    assert script.get_revision("0001_baseline").down_revision is None


# 2. EXPAND adds nullable Lease columns with NO fabricated default and a
#    CHECK ... NOT VALID, and does NOT validate here.
def test_expand_is_nullable_no_default_and_not_valid():
    src = _revision_source("0002_expand_lease.py")
    assert "ADD COLUMN lease_owner text" in src
    assert "ADD COLUMN lease_token uuid" in src
    assert "ADD COLUMN lease_expires_at timestamptz" in src
    assert "DEFAULT" not in src  # no fabricated server default on the new nullable columns
    assert "NOT VALID" in src
    assert "VALIDATE CONSTRAINT jobs_lease_triple_coherent" not in src  # the VALIDATE op lives only in 0003
    # No long Backfill/reconciliation loop inside the migration.
    assert not _function_body_has_loop(src, "upgrade")


# 3. VALIDATE is a separate revision that validates the constraint.
def test_validate_is_separate_and_validates():
    src = _revision_source("0003_validate_lease.py")
    assert "VALIDATE CONSTRAINT jobs_lease_triple_coherent" in src
    assert 'down_revision = "0002_expand_lease"' in src
    assert not _function_body_has_loop(src, "upgrade")


# 4. CONTRACT is destructive (drops the Day42 legacy column) and separately gated.
def test_contract_is_destructive_and_separate():
    src = _revision_source("0004_contract_legacy.py")
    assert 'op.drop_column("jobs", "result_object_key", schema="app")' in src
    assert 'down_revision = "0003_validate_lease"' in src
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
    assert params["batch_size"] == 100


# 8. run_backfill fills known-ownership Jobs and SKIPS unknown ones (no fabrication).
def test_backfill_fills_known_and_skips_unknown_for_reconciliation():
    # batch 1 returns two jobs; batch 2 is empty (checkpoint reached).
    sess = FakeAsyncSession(
        execute_rows=[
            [(JOB_A,), (JOB_B,)],  # select batch
            [(JOB_A,)],            # apply evidence for JOB_A -> 1 row
            [],                    # select batch 2 -> empty
        ]
    )

    class Source:
        async def prove(self, job_id):
            return _evidence(job_id) if job_id == JOB_A else None  # JOB_B unknown

    report = asyncio.run(run_backfill(lambda: sess, Source(), batch_size=100))
    assert isinstance(report, BackfillReport)
    assert report.backfilled == 1          # only JOB_A had trusted evidence
    assert report.skipped_unknown == 1     # JOB_B -> reconciliation, not fabricated
    assert sess.calls.count("commit") == 1  # one batch committed
    # The apply used a guarded, idempotent UPDATE (running + unowned + RETURNING).
    apply_sql = sess.executed[1][0]
    assert "job_status = 'running' AND lease_owner IS NULL" in apply_sql
    assert "RETURNING job_id" in apply_sql


# 9. apply_lease_evidence is idempotent/restartable: an already-owned row -> 0 rows.
def test_apply_lease_evidence_is_idempotent():
    first = FakeAsyncSession(execute_rows=[[(JOB_A,)]])   # newly owned -> 1 row
    assert asyncio.run(apply_lease_evidence(first, _evidence(JOB_A))) == 1
    again = FakeAsyncSession(execute_rows=[[]])            # already owned -> 0 rows
    assert asyncio.run(apply_lease_evidence(again, _evidence(JOB_A))) == 0


# 10. The backfill performs NO Provider call (no provider seam exists in its module).
def test_backfill_module_calls_no_provider():
    import day48_lease_backfill as m
    src = open(m.__file__).read()
    assert "provider" not in src.lower().replace("no provider", "").replace("calls no provider", "")
