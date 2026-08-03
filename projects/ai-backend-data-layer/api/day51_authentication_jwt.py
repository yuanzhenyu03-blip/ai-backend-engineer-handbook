"""Day51 — Authentication, Password Security and JWT (establish a trusted caller identity).

EVIDENCE LABEL (three distinct claims — do not conflate them):
  * CONCEPTUAL ARTIFACT: the auth boundary described here and in the design doc.
  * STATIC / REAL-LIBRARY CONTROL-FLOW VERIFICATION: what the pytest suite executes —
    REAL Argon2id password hashing (argon2-cffi) and REAL asymmetric RS256 JWT
    issuance/verification (PyJWT + cryptography) with EPHEMERAL keys generated at
    runtime, over an IN-MEMORY user + AuthSession store that MODELS the durable
    facts + guarded (UPDATE ... RETURNING) rotation. This proves application control
    flow + real crypto primitives; it is NOT a database/HTTP runtime.
  * REAL RUNTIME VERIFICATION: NOT RUN here — no real PostgreSQL
    (UNIQUE/constraint/transaction/isolation, `UPDATE ... WHERE ... RETURNING`), no
    real FastAPI/browser (cookies, SameSite, Origin, CSRF at the wire), no real JWKS
    endpoint, no integration, no production.

SECURITY: no plaintext password, refresh token, JWT, Provider key, real/operational
signing key, signed URL, database URL, or user data is committed. Test signing keys
are generated in-process and never written to disk. Raw credentials / JWT payloads
are never logged.

Boundary: Day51 authenticates WHO the caller is (a verified `sub` -> user_id). It does
NOT decide what the user may do: tenant membership, authorization, quota, and
rate-limit are Day52; a client-supplied `tenant_id` is untrusted input, not authority.
Day53 owns the real Provider; Day55 owns real Celery/broker delivery. A normal signed
JWT is READABLE (integrity/authenticity, not confidentiality) unless JWE is
deliberately designed — JWE is out of scope here.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional, Protocol

import jwt  # PyJWT
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ===========================================================================
# 1. Passwords — adaptive one-way hash only (real Argon2id)
# ===========================================================================
class AuthOutcome(str, Enum):
    OK = "ok"
    FAILED = "failed"  # ONE generic failure for unknown account AND wrong password


@dataclass(frozen=True)
class UserRow:
    user_id: str
    username: str
    password_hash: str  # Argon2id encoded hash (algo+salt+cost); NEVER plaintext


class UserDirectory(Protocol):
    def find_by_username(self, username: str) -> Optional[UserRow]: ...


class InMemoryUserDirectory:
    def __init__(self) -> None:
        self._by_username: dict[str, UserRow] = {}

    def add(self, row: UserRow) -> None:
        self._by_username[row.username] = row

    def find_by_username(self, username: str) -> Optional[UserRow]:
        return self._by_username.get(username)


class PasswordService:
    """Real Argon2id password hashing. ``verify`` delegates to the library because the
    stored hash encodes the algorithm, salt and cost; never re-hash-and-compare
    strings manually. A cryptographically random *refresh* secret may use a fast
    digest (see ``digest_refresh_token``) — that rule does NOT generalize to
    user-chosen passwords, which must use this slow adaptive scheme."""

    def __init__(self, hasher: Optional[PasswordHasher] = None) -> None:
        # Small params keep tests fast; production uses higher cost. Still real Argon2id.
        self._ph = hasher or PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
        # A fixed decoy hash so an unknown-user login still spends verify time
        # (reduces account-enumeration via timing). Never a real user's hash.
        self._decoy = self._ph.hash("decoy-not-a-real-password")

    def hash_password(self, password: str) -> str:
        return self._ph.hash(password)

    def verify_password(self, candidate: str, stored_hash: str) -> bool:
        try:
            self._ph.verify(stored_hash, candidate)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        return self._ph.check_needs_rehash(stored_hash)

    def authenticate(self, directory: UserDirectory, username: str, candidate: str) -> AuthOutcome:
        """Return ONE generic failure for an unknown account and a wrong password."""
        user = directory.find_by_username(username)
        if user is None:
            self.verify_password(candidate, self._decoy)  # equalize timing; result ignored
            return AuthOutcome.FAILED
        return AuthOutcome.OK if self.verify_password(candidate, user.password_hash) else AuthOutcome.FAILED


def digest_refresh_token(raw_token: str) -> str:
    """A FAST SHA-256 digest is acceptable for a HIGH-ENTROPY random refresh secret
    (it is not enumerable). Do NOT use this for user passwords."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ===========================================================================
# 2. JWT — asymmetric RS256, full verification contract, kid allowlist, rotation
# ===========================================================================
@dataclass(frozen=True)
class AuthenticatedIdentity:
    """The ONLY trusted output of verification: a verified subject -> user_id. A
    request-body tenant_id is NOT here — Day52 owns tenant authority."""

    user_id: str
    token_id: Optional[str] = None


class JwtVerificationError(Exception):
    pass


class KeyRing:
    """Auth Service protects private signing keys; verifiers hold PUBLIC keys only,
    addressed by an allowlisted ``kid`` (never a URL/file/lookup instruction). Supports
    planned K1->K2 overlap and emergency revocation."""

    def __init__(self) -> None:
        self._private: dict[str, rsa.RSAPrivateKey] = {}  # Auth Service ONLY
        self._public_pem: dict[str, bytes] = {}  # verifiers' trusted set (allowlist)
        self._revoked: set[str] = set()
        self._current_kid: Optional[str] = None

    def generate_signing_key(self, kid: str, *, make_current: bool = True) -> None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._private[kid] = key
        self._public_pem[kid] = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if make_current:
            self._current_kid = kid

    def trust_public_pem(self, kid: str, public_pem: bytes) -> None:
        self._public_pem[kid] = public_pem

    def current_signing_kid(self) -> str:
        if self._current_kid is None:
            raise JwtVerificationError("no signing key configured")
        return self._current_kid

    def set_current_signing_kid(self, kid: str) -> None:
        if kid not in self._private:
            raise JwtVerificationError("cannot sign with a key we do not hold privately")
        self._current_kid = kid

    def signing_key(self, kid: str) -> rsa.RSAPrivateKey:
        return self._private[kid]

    def public_pem_for(self, kid: str) -> Optional[bytes]:
        """Trusted public key for a kid, or None if unknown OR revoked. Emergency
        revocation makes a compromised key immediately untrusted, before expiry."""
        if kid in self._revoked:
            return None
        return self._public_pem.get(kid)

    def revoke_key(self, kid: str) -> None:
        self._revoked.add(kid)

    def drop_key(self, kid: str) -> None:
        self._public_pem.pop(kid, None)
        self._private.pop(kid, None)


ALLOWED_ALGS = ("RS256",)  # pinned; alg=none / HS256-confusion are rejected


def issue_access_token(
    keyring: KeyRing,
    *,
    user_id: str,
    now: datetime,
    ttl: timedelta,
    issuer: str,
    audience: str,
    kid: Optional[str] = None,
) -> str:
    """Sign a minimal Access Token with the Auth Service private key. Payload holds
    ONLY non-secret stable claims (sub/iss/aud/iat/exp/jti). Never a password hash,
    Provider key, prompt, Document content, secret, or client-asserted tenant."""
    signing_kid = kid or keyring.current_signing_kid()
    claims = {
        "sub": user_id,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, keyring.signing_key(signing_kid), algorithm="RS256",
                      headers={"kid": signing_kid})


def verify_access_token(
    token: str,
    keyring: KeyRing,
    *,
    now: datetime,
    expected_issuer: str,
    expected_audience: str,
    leeway: timedelta = timedelta(seconds=60),
    refresh_unknown_kid: Optional[Callable[[str], None]] = None,
) -> AuthenticatedIdentity:
    """FULL verification contract (not a decode): pin the algorithm, resolve a TRUSTED
    public key by allowlisted kid (an unknown kid may trigger one refresh from a
    trusted source, then reject), verify signature + issuer + audience + exp + nbf, and
    require sub. Returns the trusted identity. Any failure raises JwtVerificationError
    and yields NO identity."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise JwtVerificationError(f"unreadable header: {exc}") from exc
    if header.get("alg") not in ALLOWED_ALGS:
        raise JwtVerificationError(f"algorithm {header.get('alg')!r} not allowed")
    kid = header.get("kid")
    if not kid:
        raise JwtVerificationError("missing kid")

    public_pem = keyring.public_pem_for(kid)
    if public_pem is None and refresh_unknown_kid is not None:
        refresh_unknown_kid(kid)  # refresh ONLY from a preconfigured trusted source
        public_pem = keyring.public_pem_for(kid)
    if public_pem is None:
        raise JwtVerificationError(f"kid {kid!r} is not trusted (unknown or revoked)")

    try:
        claims = jwt.decode(
            token, public_pem, algorithms=list(ALLOWED_ALGS),
            audience=expected_audience, issuer=expected_issuer,
            # Signature + issuer + audience + required-claims are verified by PyJWT;
            # exp/nbf/iat are checked below against the INJECTED ``now`` for deterministic
            # tests (PyJWT would otherwise use real wall-clock time).
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_signature": True, "verify_exp": False,
                "verify_nbf": False, "verify_iat": False,
            },
        )
    except jwt.PyJWTError as exc:
        raise JwtVerificationError(f"verification failed: {exc}") from exc

    # PyJWT checks exp with leeway; enforce our own clock for determinism/nbf too.
    exp = claims.get("exp")
    if exp is not None and now.timestamp() > exp + leeway.total_seconds():
        raise JwtVerificationError("token expired")
    nbf = claims.get("nbf")
    if nbf is not None and now.timestamp() + leeway.total_seconds() < nbf:
        raise JwtVerificationError("token not yet valid")
    sub = claims.get("sub")
    if not sub:
        raise JwtVerificationError("missing sub")
    return AuthenticatedIdentity(user_id=sub, token_id=claims.get("jti"))


# ===========================================================================
# 3. Refresh Sessions — per-device, hash-only, guarded rotation + grace/replay
# ===========================================================================
class RefreshOutcome(str, Enum):
    ROTATED = "rotated"  # single guarded winner: A -> B
    GRACE_RETRY = "grace_retry"  # a lost-response retry recovered the SAME rotation (not A->C)
    REPLAY_DETECTED = "replay_detected"  # used token after grace -> reject + revoke family (retained)
    INVALID = "invalid"  # unknown/expired/revoked -> zero rows, issue nothing


@dataclass
class AuthSession:
    session_id: uuid.UUID
    user_id: str
    token_family_id: uuid.UUID
    refresh_token_hash: str
    created_at: datetime
    expires_at: datetime
    last_rotated_at: datetime
    rotation_counter: int = 0
    revoked_at: Optional[datetime] = None
    # bounded one-time grace recovery for a lost refresh response
    previous_refresh_token_hash: Optional[str] = None
    previous_used_at: Optional[datetime] = None
    retry_grace_expires_at: Optional[datetime] = None
    grace_result_token_hash: Optional[str] = None  # the SAME B produced by the winning rotation


@dataclass
class RefreshResult:
    outcome: RefreshOutcome
    raw_refresh_token: Optional[str] = None  # returned to the client ONLY on rotate/grace
    session: Optional[AuthSession] = None
    reason: str = ""


class SimulatedCommitFailure(Exception):
    """Injected to prove the rotation UoW is all-or-nothing in the model."""


class AuthSessionStore:
    """Models the durable per-device AuthSession table + a guarded rotation transaction
    (`UPDATE ... WHERE current_hash + active + not-expired RETURNING`). The store keeps
    ONLY refresh-token HASHES, never raw tokens. Real PostgreSQL isolation is NOT
    exercised — a lock models the single-winner arbitration."""

    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, AuthSession] = {}
        self._by_current_hash: dict[str, uuid.UUID] = {}
        self._lock = threading.Lock()

    def create_session(
        self, user_id: str, *, now: datetime, ttl: timedelta, grace: timedelta = timedelta(seconds=10),
    ) -> tuple[str, AuthSession]:
        raw = secrets.token_urlsafe(32)  # high-entropy random secret; client holds the raw
        session = AuthSession(
            session_id=uuid.uuid4(), user_id=user_id, token_family_id=uuid.uuid4(),
            refresh_token_hash=digest_refresh_token(raw), created_at=now, expires_at=now + ttl,
            last_rotated_at=now,
        )
        self._default_grace = grace
        self.sessions[session.session_id] = session
        self._by_current_hash[session.refresh_token_hash] = session.session_id
        return raw, session

    def rotate_refresh(
        self, raw_token: str, *, now: datetime, ttl: timedelta,
        grace: timedelta = timedelta(seconds=10), fail_before_commit: bool = False,
    ) -> RefreshResult:
        """Guarded atomic rotation. Inside ONE critical section (models a short DB tx
        with `UPDATE ... WHERE refresh_token_hash=? AND revoked_at IS NULL AND
        expires_at>now RETURNING`):
          * current-hash match on an active, unexpired session -> the SOLE winner:
            store the new hash + rotation metadata, set previous_* + retry grace, all
            together (a failure before commit rolls back and keeps A valid);
          * a previous-hash match within the grace window -> GRACE_RETRY recovering the
            SAME B (never branching A into a new C);
          * a previous-hash match AFTER grace, or any used/revoked family token ->
            REPLAY_DETECTED: revoke + RETAIN the family (audit evidence), issue nothing;
          * unknown/expired/revoked -> INVALID (zero rows), issue nothing."""
        h = digest_refresh_token(raw_token)
        with self._lock:
            sid = self._by_current_hash.get(h)
            if sid is not None:
                session = self.sessions[sid]
                if session.revoked_at is not None or now >= session.expires_at:
                    return RefreshResult(RefreshOutcome.INVALID, reason="revoked or expired")
                new_raw = secrets.token_urlsafe(32)
                new_hash = digest_refresh_token(new_raw)
                if fail_before_commit:
                    # Nothing mutated yet -> rollback keeps A as the only valid token.
                    raise SimulatedCommitFailure("injected failure before commit")
                # --- single logical commit: all rotation facts together ---
                session.previous_refresh_token_hash = session.refresh_token_hash
                session.previous_used_at = now
                session.retry_grace_expires_at = now + grace
                session.grace_result_token_hash = new_hash
                del self._by_current_hash[session.refresh_token_hash]
                session.refresh_token_hash = new_hash
                session.last_rotated_at = now
                session.rotation_counter += 1
                session.expires_at = now + ttl
                self._by_current_hash[new_hash] = sid
                return RefreshResult(RefreshOutcome.ROTATED, raw_refresh_token=new_raw, session=session)

            # Not a current token: is it a previous token (grace or replay)?
            for session in self.sessions.values():
                if session.previous_refresh_token_hash == h:
                    if (
                        session.retry_grace_expires_at is not None
                        and now < session.retry_grace_expires_at
                        and session.revoked_at is None
                    ):
                        # Lost-response retry: recover the SAME rotation result.
                        return RefreshResult(
                            RefreshOutcome.GRACE_RETRY,
                            raw_refresh_token=None,  # the raw B was returned once; recovery is idempotent
                            session=session, reason="grace retry recovered the same rotation",
                        )
                    # Used token after grace (or revoked) -> suspected replay.
                    self._revoke_family_locked(session.token_family_id, now)
                    return RefreshResult(RefreshOutcome.REPLAY_DETECTED, session=session,
                                         reason="used refresh token after grace")
            return RefreshResult(RefreshOutcome.INVALID, reason="unknown refresh token")

    def revoke_session(self, session_id: uuid.UUID, *, now: datetime) -> bool:
        """Normal /logout: revoke ONLY the current per-device session."""
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None or session.revoked_at is not None:
                return False
            session.revoked_at = now
            self._by_current_hash.pop(session.refresh_token_hash, None)
            return True

    def revoke_family(self, token_family_id: uuid.UUID, *, now: datetime) -> int:
        with self._lock:
            return self._revoke_family_locked(token_family_id, now)

    def revoke_all_user_sessions(self, user_id: str, *, now: datetime) -> int:
        """logout-all / password change / key compromise: revoke every device family."""
        with self._lock:
            count = 0
            for session in self.sessions.values():
                if session.user_id == user_id and session.revoked_at is None:
                    session.revoked_at = now
                    self._by_current_hash.pop(session.refresh_token_hash, None)
                    count += 1
            return count

    def _revoke_family_locked(self, token_family_id: uuid.UUID, now: datetime) -> int:
        count = 0
        for session in self.sessions.values():
            if session.token_family_id == token_family_id and session.revoked_at is None:
                session.revoked_at = now
                # Clear recovery material but RETAIN the record for audit evidence.
                session.grace_result_token_hash = None
                self._by_current_hash.pop(session.refresh_token_hash, None)
                count += 1
        return count  # the family record is retained, not deleted


# ===========================================================================
# 4. Browser / CSRF contract (cookie-authenticated state-changing endpoints)
# ===========================================================================
class CsrfDecision(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"


def evaluate_state_change_request(
    *,
    cookie_present: bool,
    request_origin: Optional[str],
    allowed_origins: frozenset[str],
    csrf_header: Optional[str],
    csrf_expected: Optional[str],
) -> CsrfDecision:
    """Contract for a cookie-authenticated state-changing request. HttpOnly stops
    JavaScript reads but NOT automatic cookie attachment, so it is NOT CSRF defense:
    require BOTH a same/allowed Origin AND a matching CSRF token (double-submit /
    custom header). A cookie-only cross-site request lacking valid Origin/CSRF is
    rejected. (This models the decision; real header/cookie handling is FastAPI/browser
    runtime, NOT exercised here.)"""
    if not cookie_present:
        return CsrfDecision.ALLOW  # e.g. a Bearer-token API request, not cookie-CSRF-exposed
    if request_origin is None or request_origin not in allowed_origins:
        return CsrfDecision.REJECT
    if not csrf_header or csrf_expected is None or not hmac.compare_digest(csrf_header, csrf_expected):
        return CsrfDecision.REJECT
    return CsrfDecision.ALLOW
