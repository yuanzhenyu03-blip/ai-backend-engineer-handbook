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


def test_repair_persists_incident_window_and_attestation_columns():
    # The audit row must actually store the operator's bounded-eligibility decision.
    for col in ("incident_start", "incident_end", "no_conflict_attested",
                "deadline_contract_budget_valid_attested"):
        assert col in _SRC, col
    assert ":istart" in _SRC and ":iend" in _SRC
    assert ":nca" in _SRC and ":dcbva" in _SRC


def test_repair_integrity_does_not_blindly_return_already_applied():
    # After IntegrityError the runtime must RE-READ and classify, not fake success.
    assert "classify_repair_integrity(" in _SRC
    # the old blind handler must be gone
    assert "-> exactly-once." not in _SRC


def test_repair_integrity_reread_joins_outbox_and_verifies_semantics():
    # The re-read must JOIN outbox_events and verify the linked intent's job + event_type,
    # not merely that the FK is non-null.
    assert "LEFT JOIN app.outbox_events o" in _SRC
    assert "ON o.outbox_event_id = h.redispatch_outbox_event_id" in _SRC
    assert "o.event_type" in _SRC and "o.job_id" in _SRC
    assert "linked_outbox_job_matches=" in _SRC
    assert "linked_outbox_is_redispatch=" in _SRC
    assert "== REDISPATCH_EVENT_TYPE" in _SRC
