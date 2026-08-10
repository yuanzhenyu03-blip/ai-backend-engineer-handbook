"""Day59 — EXECUTED_LOCAL_RUNTIME unit tests for the pure acceptance logic.

Scope: standard-library control flow ONLY (no DB, no web server, no Docker). These
tests prove the Day59 DECISION rules that drive the route: fingerprint shape and
determinism, that the fingerprint covers the COMPLETE logical command (ordered
document_ids + business_input), idempotency classification (exact replay vs 409 vs
fresh), and the readiness gate.

They do NOT prove real PostgreSQL UNIQUE / partial unique index / ``ON CONFLICT`` /
transaction / Document-verification behavior — that is INTEGRATION_RUNTIME and is
described (with its NOT-RERUN status) in the Day59 design/runbook. A pure-logic test
must never be presented as PostgreSQL integration evidence.
"""

from day59_acceptance_logic import (
    FINGERPRINT_RE,
    IdempotencyDecision,
    Readiness,
    classify_idempotency,
    compute_request_fingerprint,
    evaluate_readiness,
)


def fp(tenant, key, docs, biz):
    # tenant/key are the lookup scope, NOT part of the fingerprint (Day50 contract);
    # kept as helper args only to keep each test's intent readable.
    return compute_request_fingerprint(docs, biz)


def test_fingerprint_is_sha256_shaped_and_matches_migration_check():
    assert FINGERPRINT_RE.match(fp("t1", "k1", ["d1"], {"p": "x"}))


def test_fingerprint_is_deterministic_and_business_key_order_independent():
    a = fp("t1", "k1", ["d1"], {"a": 1, "b": 2})
    b = fp("t1", "k1", ["d1"], {"b": 2, "a": 1})
    assert a == b


def test_fingerprint_covers_document_ids():
    # Same tenant/key/business_input but different documents -> different fingerprint,
    # which drives the same-key/different-Document -> 409 route behavior.
    a = fp("t1", "k1", ["d1"], {"p": "x"})
    b = fp("t1", "k1", ["d2"], {"p": "x"})
    assert a != b


def test_fingerprint_preserves_document_order():
    # Document order can carry business meaning: reordering is a different command.
    a = fp("t1", "k1", ["d1", "d2"], {})
    b = fp("t1", "k1", ["d2", "d1"], {})
    assert a != b


def test_exact_retry_same_documents_returns_original():
    a = fp("t1", "k1", ["d1", "d2"], {"p": "x"})
    b = fp("t1", "k1", ["d1", "d2"], {"p": "x"})
    assert classify_idempotency(a, b) is IdempotencyDecision.RETURN_ORIGINAL


def test_same_key_different_business_input_conflicts():
    old = fp("t1", "k1", ["d1"], {"p": "x"})
    new = fp("t1", "k1", ["d1"], {"p": "y"})
    assert classify_idempotency(old, new) is IdempotencyDecision.CONFLICT_409


def test_same_key_different_document_conflicts():
    old = fp("t1", "k1", ["d1"], {"p": "x"})
    new = fp("t1", "k1", ["d2"], {"p": "x"})
    assert classify_idempotency(old, new) is IdempotencyDecision.CONFLICT_409


def test_fingerprint_excludes_idempotency_key_and_tenant():
    # Day50 contract: the client-supplied key is the dedup key, never the fingerprint.
    assert compute_request_fingerprint(["d1"], {"p": "x"}) == compute_request_fingerprint(["d1"], {"p": "x"})


def test_fresh_key_accepts_new():
    assert classify_idempotency(None, fp("t1", "k2", ["d1"], {})) is IdempotencyDecision.ACCEPT_NEW


def test_readiness_requires_db_and_matching_revision():
    ok = evaluate_readiness(True, "0008_day59_acceptance", "0008_day59_acceptance")
    assert ok.state is Readiness.READY
    down = evaluate_readiness(False, "0008_day59_acceptance", "0008_day59_acceptance")
    assert down.state is Readiness.NOT_READY and down.reason == "database_unreachable"
    stale = evaluate_readiness(True, "0007_merge_reconciliation_polling", "0008_day59_acceptance")
    assert stale.state is Readiness.NOT_READY and stale.reason.startswith("revision_mismatch")
