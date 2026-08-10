"""Day59 — EXECUTED_LOCAL_RUNTIME unit tests for the pure acceptance logic.

Scope: standard-library control flow ONLY (no DB, no web server, no Docker). These
tests prove the Day59 DECISION rules (fingerprint shape/determinism, idempotency
classification, readiness gate). They do NOT prove real PostgreSQL UNIQUE / partial
unique index / transaction behavior, which is INTEGRATION_RUNTIME (see the runbook).
"""

from day59_acceptance_logic import (
    FINGERPRINT_RE,
    IdempotencyDecision,
    Readiness,
    classify_idempotency,
    compute_request_fingerprint,
    evaluate_readiness,
)


def test_fingerprint_is_sha256_shaped_and_matches_migration_check():
    fp = compute_request_fingerprint("t1", "k1", {"prompt_ref": "doc-1"})
    assert FINGERPRINT_RE.match(fp), fp


def test_fingerprint_is_deterministic_and_key_order_independent():
    a = compute_request_fingerprint("t1", "k1", {"a": 1, "b": 2})
    b = compute_request_fingerprint("t1", "k1", {"b": 2, "a": 1})
    assert a == b


def test_fingerprint_changes_with_logical_input():
    a = compute_request_fingerprint("t1", "k1", {"doc": "d1"})
    b = compute_request_fingerprint("t1", "k1", {"doc": "d2"})
    assert a != b


def test_exact_retry_returns_original():
    fp = compute_request_fingerprint("t1", "k1", {"doc": "d1"})
    assert classify_idempotency(fp, fp) is IdempotencyDecision.RETURN_ORIGINAL


def test_same_key_different_payload_conflicts():
    old = compute_request_fingerprint("t1", "k1", {"doc": "d1"})
    new = compute_request_fingerprint("t1", "k1", {"doc": "d2"})
    assert classify_idempotency(old, new) is IdempotencyDecision.CONFLICT_409


def test_fresh_key_accepts_new():
    fp = compute_request_fingerprint("t1", "k2", {"doc": "d1"})
    assert classify_idempotency(None, fp) is IdempotencyDecision.ACCEPT_NEW


def test_readiness_requires_db_and_matching_revision():
    ok = evaluate_readiness(True, "0008_day59_acceptance", "0008_day59_acceptance")
    assert ok.state is Readiness.READY
    down = evaluate_readiness(False, "0008_day59_acceptance", "0008_day59_acceptance")
    assert down.state is Readiness.NOT_READY and down.reason == "database_unreachable"
    stale = evaluate_readiness(True, "0007_merge_reconciliation_polling", "0008_day59_acceptance")
    assert stale.state is Readiness.NOT_READY and stale.reason.startswith("revision_mismatch")
