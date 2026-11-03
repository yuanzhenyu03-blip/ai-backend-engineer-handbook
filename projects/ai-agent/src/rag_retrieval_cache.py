"""Day100 derived cache and signed cursor bindings."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import threading

from rag_chunking_contracts import stable_hash
from rag_retrieval_contracts import (
    FusedCandidate,
    RetrievalAuthorizationScope,
    SelectedRetrievalBundle,
)


@dataclass(frozen=True)
class RetrievalCacheKey:
    tenant_id: str
    principal_hash: str
    action: str
    purpose: str
    authorization_scope_fingerprint: str
    bundle_fingerprint: str
    generation_id: str
    query_hash: str
    filter_plan_fingerprint: str
    retrieval_policy_fingerprint: str
    fusion_policy_fingerprint: str
    degradation_mode: str

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RetrievalCacheEntry:
    key: RetrievalCacheKey
    candidates: tuple[FusedCandidate, ...]
    expires_at: int


class InMemoryRetrievalCache:
    """Caches derived candidate identities, never protected text."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, RetrievalCacheEntry] = {}

    def put(self, entry: RetrievalCacheEntry) -> None:
        with self._lock:
            self._entries[entry.key.fingerprint] = entry

    def get(self, key: RetrievalCacheKey, *, now: int) -> RetrievalCacheEntry | None:
        with self._lock:
            entry = self._entries.get(key.fingerprint)
            if entry is None or entry.expires_at <= now:
                return None
            if entry.key != key:
                return None
            return entry


@dataclass(frozen=True)
class RetrievalCursor:
    cursor_version: str
    operation_id: str
    tenant_id: str
    principal_hash: str
    authorization_scope_fingerprint: str
    bundle_fingerprint: str
    generation_id: str
    query_hash: str
    filter_plan_fingerprint: str
    retrieval_policy_fingerprint: str
    fusion_policy_fingerprint: str
    lexical_offset: int
    dense_offset: int
    expires_at: int


class CursorValidationError(ValueError):
    pass


class RetrievalCursorCodec:
    def __init__(self, secret: bytes) -> None:
        if len(secret) < 16:
            raise ValueError("cursor signing key must be at least 16 bytes")
        self._secret = secret

    def encode(self, cursor: RetrievalCursor) -> str:
        payload = json.dumps(
            asdict(cursor), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return self._b64(payload) + "." + self._b64(signature)

    def decode(self, token: str) -> RetrievalCursor:
        try:
            payload_token, signature_token = token.split(".", 1)
            payload = self._unb64(payload_token)
            signature = self._unb64(signature_token)
            if (
                self._b64(payload) != payload_token
                or self._b64(signature) != signature_token
            ):
                raise CursorValidationError("CURSOR_ENCODING_NON_CANONICAL")
            expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise CursorValidationError("CURSOR_SIGNATURE_INVALID")
            values = json.loads(payload.decode("utf-8"))
            return RetrievalCursor(**values)
        except CursorValidationError:
            raise
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CursorValidationError("CURSOR_MALFORMED") from exc

    def validate_current(
        self,
        cursor: RetrievalCursor,
        *,
        bundle: SelectedRetrievalBundle,
        scope: RetrievalAuthorizationScope,
        principal_hash: str,
        query_hash: str,
        filter_plan_fingerprint: str,
        now: int,
    ) -> None:
        if cursor.expires_at <= now:
            raise CursorValidationError("CURSOR_EXPIRED")
        if cursor.tenant_id != bundle.tenant_id or cursor.principal_hash != principal_hash:
            raise CursorValidationError("CURSOR_PRINCIPAL_OR_TENANT_MISMATCH")
        if cursor.bundle_fingerprint != bundle.fingerprint:
            raise CursorValidationError("CURSOR_SELECTED_BUNDLE_CHANGED")
        if cursor.generation_id != bundle.generation_id:
            raise CursorValidationError("CURSOR_GENERATION_CHANGED")
        if cursor.authorization_scope_fingerprint != scope.fingerprint:
            raise CursorValidationError("CURSOR_AUTHORIZATION_CHANGED")
        if cursor.query_hash != query_hash:
            raise CursorValidationError("CURSOR_QUERY_CHANGED")
        if cursor.filter_plan_fingerprint != filter_plan_fingerprint:
            raise CursorValidationError("CURSOR_FILTER_CHANGED")
        if (
            cursor.retrieval_policy_fingerprint
            != bundle.retrieval_policy.fingerprint
            or cursor.fusion_policy_fingerprint != bundle.fusion_policy.fingerprint
        ):
            raise CursorValidationError("CURSOR_POLICY_CHANGED")

    @staticmethod
    def principal_hash(principal_subject: str) -> str:
        return stable_hash(("PRINCIPAL", principal_subject))

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
