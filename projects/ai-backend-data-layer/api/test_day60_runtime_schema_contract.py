"""Day60 — static contract checks on the real runtime SQL (no DB, no imports).

These read the runtime SOURCE as text and assert it uses the EXISTING Day48 lease TRIPLE
(``lease_owner`` / ``lease_token`` / ``lease_expires_at``) and NOT the parallel
``lease_expiry`` column that 0011 removes. This is a cheap regression guard for the exact
review defect; it is EXECUTED_LOCAL_RUNTIME (a source contract check), NOT PostgreSQL
integration evidence.
"""

import pathlib

_SRC = (pathlib.Path(__file__).parent / "day60_delivery_runtime.py").read_text()


def test_guarded_claim_writes_full_lease_triple():
    # The claim must set all three lease columns atomically (triple coherence + running-requires-lease).
    assert "job_status='running'" in _SRC
    assert "lease_owner=:owner" in _SRC
    assert "lease_token=:token" in _SRC
    assert "lease_expires_at=:exp" in _SRC


def test_completion_matches_lease_token_not_owner():
    assert "AND lease_token=:token RETURNING job_id" in _SRC


def test_runtime_does_not_use_parallel_lease_expiry_column():
    # 0011 drops app.jobs.lease_expiry; the runtime must not reference it.
    assert "lease_expiry" not in _SRC


def test_completion_clears_full_lease_triple_and_counts_attempt():
    assert "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL" in _SRC
    assert "attempt_count=attempt_count+1" in _SRC


def test_runtime_never_imports_or_calls_the_celery_task():
    # The runtime publishes ONLY through an injected callable (OutboxRelay.self._publish);
    # it must not import the Celery task or publish directly. The real apply_async call lives
    # in day60_relay.py (the ONLY publisher). Ignore docstrings by scanning executable lines.
    code_lines = [ln for ln in _SRC.splitlines()
                  if not ln.strip().startswith("#") and not ln.strip().startswith("*")]
    code = "\n".join(code_lines)
    assert "self._publish(" in _SRC                 # injected publisher only
    assert "from day60_celery_app import" not in code
    assert "execute_job_attempt" not in code
