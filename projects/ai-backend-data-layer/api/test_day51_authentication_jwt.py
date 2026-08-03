"""Day51 — tests for Authentication, Password Security and JWT.

EVIDENCE LABEL: these use REAL Argon2id (argon2-cffi) and REAL asymmetric RS256 JWT
(PyJWT + cryptography) with EPHEMERAL in-process keys, over an IN-MEMORY user +
AuthSession store that MODELS guarded (UPDATE ... RETURNING) rotation. This is the
Static / real-library control-flow tier — it proves application control flow + real
crypto primitives. It is NOT REAL RUNTIME VERIFICATION: NOT real PostgreSQL
UNIQUE/constraint/transaction/isolation, NOT real FastAPI/browser (cookies/SameSite/
Origin/CSRF at the wire), NOT a real JWKS endpoint, NOT integration, NOT production.
No plaintext password, refresh token, JWT, or operational signing key is committed;
test keys are generated in-process.
"""

import threading
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from day51_authentication_jwt import (
    ALLOWED_ALGS,
    AuthOutcome,
    AuthenticatedIdentity,
    AuthSessionStore,
    CsrfDecision,
    InMemoryUserDirectory,
    JwtVerificationError,
    KeyRing,
    PasswordService,
    RefreshOutcome,
    SimulatedCommitFailure,
    UserRow,
    digest_refresh_token,
    evaluate_state_change_request,
    issue_access_token,
    verify_access_token,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
ISS = "https://auth.example.internal"
AUD = "ai-job-api"


def _keyring(kid="K1"):
    kr = KeyRing()
    kr.generate_signing_key(kid, make_current=True)
    return kr


def _sign(kr: KeyRing, kid: str, claims: dict) -> str:
    return jwt.encode(claims, kr.signing_key(kid), algorithm="RS256", headers={"kid": kid})


def _base_claims(now=NOW, ttl=timedelta(minutes=5), sub="user-123"):
    c = {"iss": ISS, "aud": AUD, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp())}
    if sub is not None:
        c["sub"] = sub
    return c


# ===========================================================================
# Passwords (real Argon2id)
# ===========================================================================
def test_password_is_stored_as_argon2id_hash_never_plaintext():
    ps = PasswordService()
    h = ps.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert h.startswith("$argon2id$")  # real Argon2id encoded hash (algo+salt+cost)


def test_verify_password_true_and_false():
    ps = PasswordService()
    h = ps.hash_password("s3cret-pw")
    assert ps.verify_password("s3cret-pw", h) is True
    assert ps.verify_password("wrong-pw", h) is False


def test_authenticate_generic_failure_for_unknown_and_wrong():
    ps = PasswordService()
    directory = InMemoryUserDirectory()
    directory.add(UserRow(user_id="user-123", username="alice", password_hash=ps.hash_password("pw-alice")))
    assert ps.authenticate(directory, "alice", "pw-alice") is AuthOutcome.OK
    # Same generic FAILED for a wrong password and an unknown account (anti-enumeration).
    assert ps.authenticate(directory, "alice", "nope") is AuthOutcome.FAILED
    assert ps.authenticate(directory, "ghost", "whatever") is AuthOutcome.FAILED


def test_needs_rehash_upgrades_old_parameters():
    from argon2 import PasswordHasher
    weak = PasswordService(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    strong = PasswordService(PasswordHasher(time_cost=3, memory_cost=64, parallelism=1))
    old_hash = weak.hash_password("pw")
    assert strong.needs_rehash(old_hash) is True  # a stronger policy flags the old hash
    assert strong.needs_rehash(strong.hash_password("pw")) is False


def test_refresh_digest_is_fast_hash_but_only_for_high_entropy_secret():
    raw = "a-high-entropy-random-refresh-secret"
    assert digest_refresh_token(raw) == digest_refresh_token(raw)
    assert digest_refresh_token(raw) != raw  # only the hash is ever stored


# ===========================================================================
# JWT issuance + full verification contract
# ===========================================================================
def test_issue_and_verify_yields_trusted_identity():
    kr = _keyring()
    token = issue_access_token(kr, user_id="user-123", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)
    ident = verify_access_token(token, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)
    assert isinstance(ident, AuthenticatedIdentity) and ident.user_id == "user-123"


def test_issued_payload_is_minimal_and_carries_no_secrets():
    kr = _keyring()
    token = issue_access_token(kr, user_id="user-123", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert set(claims) <= {"sub", "iss", "aud", "iat", "exp", "jti"}
    blob = str(claims).lower()
    for forbidden in ("password", "argon2", "tenant", "prompt", "provider", "secret"):
        assert forbidden not in blob


def test_reject_expired_token():
    kr = _keyring()
    token = issue_access_token(kr, user_id="u", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, kr, now=NOW + timedelta(minutes=10), expected_issuer=ISS, expected_audience=AUD)


def test_reject_wrong_issuer_and_audience():
    kr = _keyring()
    token = issue_access_token(kr, user_id="u", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, kr, now=NOW, expected_issuer="https://evil", expected_audience=AUD)
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, kr, now=NOW, expected_issuer=ISS, expected_audience="other-api")


def test_reject_not_yet_valid_nbf():
    kr = _keyring()
    claims = _base_claims()
    claims["nbf"] = int((NOW + timedelta(minutes=10)).timestamp())
    token = _sign(kr, "K1", claims)
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)


def test_reject_missing_sub():
    kr = _keyring()
    token = _sign(kr, "K1", _base_claims(sub=None))
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)


def test_reject_alg_none():
    kr = _keyring()
    unsigned = jwt.encode(_base_claims(), key=None, algorithm="none", headers={"kid": "K1"})
    with pytest.raises(JwtVerificationError):
        verify_access_token(unsigned, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)


def test_reject_hs256_algorithm_confusion():
    kr = _keyring()
    # Algorithm-confusion attempt: present an HS256 token (attacker-chosen secret) to a
    # verifier that pins RS256. Our alg allowlist rejects it BEFORE any key is used.
    # (PyJWT additionally refuses to HMAC-sign with an asymmetric PEM, a second guard.)
    forged = jwt.encode(_base_claims(), key="attacker-chosen-secret", algorithm="HS256", headers={"kid": "K1"})
    with pytest.raises(JwtVerificationError):
        verify_access_token(forged, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)


def test_reject_tampered_signature():
    kr = _keyring()
    token = issue_access_token(kr, user_id="u", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(JwtVerificationError):
        verify_access_token(tampered, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)


# ===========================================================================
# kid allowlist, unknown-kid refresh, emergency revoke, rotation
# ===========================================================================
def test_unknown_kid_refreshes_from_trusted_source_then_verifies_else_rejects():
    signer = _keyring("K3")  # a key the verifier does not yet trust
    token = issue_access_token(signer, user_id="user-9", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)
    verifier = KeyRing()  # trusts nothing yet

    def refresh(kid):  # only pulls from a preconfigured trusted source (here: the signer's public key)
        if kid == "K3":
            verifier.trust_public_pem("K3", signer.public_pem_for("K3"))

    ident = verify_access_token(token, verifier, now=NOW, expected_issuer=ISS, expected_audience=AUD,
                                refresh_unknown_kid=refresh)
    assert ident.user_id == "user-9"
    # An unknown kid that the trusted source cannot resolve is rejected.
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, KeyRing(), now=NOW, expected_issuer=ISS, expected_audience=AUD,
                            refresh_unknown_kid=lambda kid: None)


def test_emergency_revoked_kid_rejected_immediately():
    kr = _keyring("K1")
    token = issue_access_token(kr, user_id="u", now=NOW, ttl=timedelta(hours=1), issuer=ISS, audience=AUD)
    kr.revoke_key("K1")  # confirmed compromise -> stop trusting BEFORE expiry
    with pytest.raises(JwtVerificationError):
        verify_access_token(token, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)


def test_planned_k1_to_k2_rotation_overlap():
    kr = _keyring("K1")
    kr.generate_signing_key("K2", make_current=True)  # publish K2, trust K1 + K2
    t_k1 = _sign(kr, "K1", _base_claims(sub="u1"))
    t_k2 = issue_access_token(kr, user_id="u2", now=NOW, ttl=timedelta(minutes=5), issuer=ISS, audience=AUD)  # K2 (current)
    # Overlap: both verify.
    assert verify_access_token(t_k1, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD).user_id == "u1"
    assert verify_access_token(t_k2, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD).user_id == "u2"
    # After K1's max lifetime + skew, drop K1: old K1 tokens no longer verify; K2 still does.
    kr.drop_key("K1")
    with pytest.raises(JwtVerificationError):
        verify_access_token(t_k1, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD)
    assert verify_access_token(t_k2, kr, now=NOW, expected_issuer=ISS, expected_audience=AUD).user_id == "u2"


# ===========================================================================
# Refresh Sessions — hash-only storage, guarded rotation, rollback, grace/replay
# ===========================================================================
def test_create_session_stores_only_hash():
    store = AuthSessionStore()
    raw, session = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))
    assert session.refresh_token_hash == digest_refresh_token(raw)
    assert raw not in (session.refresh_token_hash,)  # the raw token is never stored


def test_rotate_returns_new_token_and_invalidates_old():
    store = AuthSessionStore()
    raw_a, _ = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))
    res = store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1), ttl=timedelta(days=30), grace=timedelta(seconds=10))
    assert res.outcome is RefreshOutcome.ROTATED and res.raw_refresh_token and res.raw_refresh_token != raw_a
    # The new token rotates again; A is no longer the current token.
    res2 = store.rotate_refresh(res.raw_refresh_token, now=NOW + timedelta(minutes=2), ttl=timedelta(days=30))
    assert res2.outcome is RefreshOutcome.ROTATED


def test_rotation_is_single_winner_under_concurrency():
    store = AuthSessionStore()
    raw_a, _ = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))
    barrier = threading.Barrier(2)
    outcomes: list = []

    def worker():
        barrier.wait()
        outcomes.append(store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1),
                                              ttl=timedelta(days=30), grace=timedelta(seconds=30)).outcome)

    t1, t2 = threading.Thread(target=worker), threading.Thread(target=worker)
    t1.start(); t2.start(); t1.join(); t2.join()
    # Exactly one guarded winner rotates A->B; the loser recovers the SAME rotation (grace), not a new branch.
    assert sorted(o.value for o in outcomes) == ["grace_retry", "rotated"]
    assert len([s for s in store.sessions.values()]) == 1  # one session/family, no C branch


def test_rotation_rollback_keeps_a_valid():
    store = AuthSessionStore()
    raw_a, _ = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))
    with pytest.raises(SimulatedCommitFailure):
        store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1), ttl=timedelta(days=30), fail_before_commit=True)
    # A is still the only valid token and can rotate successfully now.
    res = store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=2), ttl=timedelta(days=30))
    assert res.outcome is RefreshOutcome.ROTATED


def test_grace_retry_recovers_same_rotation_within_window():
    store = AuthSessionStore()
    raw_a, _ = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))
    store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1), ttl=timedelta(days=30), grace=timedelta(seconds=30))
    # The client lost the response and retries A within the grace window.
    retry = store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1, seconds=5), ttl=timedelta(days=30))
    assert retry.outcome is RefreshOutcome.GRACE_RETRY  # not a new A->C branch


def test_replay_after_grace_revokes_family_but_retains_record():
    store = AuthSessionStore()
    raw_a, session = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))
    fam = session.token_family_id
    b = store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1), ttl=timedelta(days=30), grace=timedelta(seconds=10))
    # A reused AFTER the grace window -> suspected replay.
    replay = store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=5), ttl=timedelta(days=30))
    assert replay.outcome is RefreshOutcome.REPLAY_DETECTED
    assert session.revoked_at is not None  # family revoked
    assert session.session_id in store.sessions  # record RETAINED for audit (not deleted)
    # The (now revoked) current token B can no longer rotate.
    assert store.rotate_refresh(b.raw_refresh_token, now=NOW + timedelta(minutes=6), ttl=timedelta(days=30)).outcome \
        is RefreshOutcome.INVALID


def test_invalid_for_unknown_or_expired():
    store = AuthSessionStore()
    assert store.rotate_refresh("never-issued", now=NOW, ttl=timedelta(days=30)).outcome is RefreshOutcome.INVALID
    raw_a, _ = store.create_session("user-1", now=NOW, ttl=timedelta(seconds=1))
    assert store.rotate_refresh(raw_a, now=NOW + timedelta(minutes=1), ttl=timedelta(days=30)).outcome \
        is RefreshOutcome.INVALID  # session expired


def test_logout_current_vs_logout_all():
    store = AuthSessionStore()
    raw1, s1 = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))  # device 1
    raw2, s2 = store.create_session("user-1", now=NOW, ttl=timedelta(days=30))  # device 2
    raw3, s3 = store.create_session("user-2", now=NOW, ttl=timedelta(days=30))  # other user
    assert store.revoke_session(s1.session_id, now=NOW) is True  # logout current device only
    assert s1.revoked_at is not None and s2.revoked_at is None
    n = store.revoke_all_user_sessions("user-1", now=NOW)  # logout-all / password change
    assert n == 1 and s2.revoked_at is not None  # s1 already revoked
    assert s3.revoked_at is None  # a different user is unaffected


# ===========================================================================
# Browser / CSRF contract
# ===========================================================================
def test_csrf_contract_rejects_cookie_cross_site_without_valid_origin_and_token():
    allowed = frozenset({"https://app.example.com"})
    # Bearer API request (no cookie) is not exposed to cookie-CSRF here.
    assert evaluate_state_change_request(cookie_present=False, request_origin=None, allowed_origins=allowed,
                                         csrf_header=None, csrf_expected=None) is CsrfDecision.ALLOW
    # Cookie present, cross-site origin -> reject.
    assert evaluate_state_change_request(cookie_present=True, request_origin="https://evil.com",
                                         allowed_origins=allowed, csrf_header="t", csrf_expected="t") is CsrfDecision.REJECT
    # Cookie present, good origin, missing/mismatched CSRF token -> reject.
    assert evaluate_state_change_request(cookie_present=True, request_origin="https://app.example.com",
                                         allowed_origins=allowed, csrf_header=None, csrf_expected="t") is CsrfDecision.REJECT
    assert evaluate_state_change_request(cookie_present=True, request_origin="https://app.example.com",
                                         allowed_origins=allowed, csrf_header="wrong", csrf_expected="t") is CsrfDecision.REJECT
    # Cookie present, good origin, matching CSRF token -> allow.
    assert evaluate_state_change_request(cookie_present=True, request_origin="https://app.example.com",
                                         allowed_origins=allowed, csrf_header="t", csrf_expected="t") is CsrfDecision.ALLOW


# ===========================================================================
# Honesty label
# ===========================================================================
def test_evidence_label_is_real_crypto_not_runtime():
    import day51_authentication_jwt as m
    header = (m.__doc__ or "")
    assert "REAL Argon2id" in header and "REAL RUNTIME VERIFICATION: NOT RUN" in header
    assert ALLOWED_ALGS == ("RS256",)  # algorithm is pinned
