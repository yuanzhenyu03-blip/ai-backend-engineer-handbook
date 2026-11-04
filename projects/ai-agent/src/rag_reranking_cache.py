"""Day101 cache and signed cursor identities bound to rewrite and reranking state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import base64
import hashlib
import hmac
import json

from rag_chunking_contracts import stable_hash
from rag_reranker_contracts import ValidatedRerankResult


@dataclass(frozen=True)
class RerankingCacheKey:
    tenant_id: str
    principal_hash: str
    authorization_scope_fingerprint: str
    selected_bundle_fingerprint: str
    original_query_fingerprint: str
    rewrite_set_fingerprint: str
    multi_query_plan_fingerprint: str
    candidate_pool_digest: str
    reranker_contract_fingerprint: str
    input_windows_digest: str

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RerankingCacheEntry:
    key: RerankingCacheKey
    result: ValidatedRerankResult
    expires_at: int


class InMemoryRerankingCache:
    def __init__(self) -> None:
        self._entries: dict[str, RerankingCacheEntry] = {}

    def put(self, entry: RerankingCacheEntry) -> None:
        self._entries[entry.key.fingerprint] = entry

    def get(self, key: RerankingCacheKey, *, now: int) -> RerankingCacheEntry | None:
        entry = self._entries.get(key.fingerprint)
        if entry is None or entry.expires_at < now:
            return None
        return entry


@dataclass(frozen=True)
class RerankingCursor:
    cursor_version: str
    tenant_id: str
    principal_hash: str
    authorization_scope_fingerprint: str
    selected_bundle_fingerprint: str
    original_query_fingerprint: str
    rewrite_set_fingerprint: str
    candidate_pool_digest: str
    reranker_contract_fingerprint: str
    validated_rerank_digest: str
    offset: int
    expires_at: int


class RerankingCursorError(ValueError):
    pass


class RerankingCursorCodec:
    def __init__(self, secret: bytes) -> None:
        if not secret:
            raise ValueError("cursor signing secret is required")
        self._secret = secret

    def encode(self, cursor: RerankingCursor) -> str:
        payload = json.dumps(
            asdict(cursor), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return self._b64(payload) + "." + self._b64(signature)

    def decode(self, token: str) -> RerankingCursor:
        try:
            payload_part, signature_part = token.split(".", 1)
            payload = self._unb64(payload_part)
            signature = self._unb64(signature_part)
        except Exception as exc:
            raise RerankingCursorError("RERANK_CURSOR_MALFORMED") from exc
        expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise RerankingCursorError("RERANK_CURSOR_SIGNATURE_INVALID")
        try:
            return RerankingCursor(**json.loads(payload.decode("utf-8")))
        except Exception as exc:
            raise RerankingCursorError("RERANK_CURSOR_PAYLOAD_INVALID") from exc

    def validate_current(
        self,
        cursor: RerankingCursor,
        *,
        expected: RerankingCursor,
        now: int,
    ) -> None:
        if cursor.expires_at < now:
            raise RerankingCursorError("RERANK_CURSOR_EXPIRED")
        for field in (
            "cursor_version",
            "tenant_id",
            "principal_hash",
            "authorization_scope_fingerprint",
            "selected_bundle_fingerprint",
            "original_query_fingerprint",
            "rewrite_set_fingerprint",
            "candidate_pool_digest",
            "reranker_contract_fingerprint",
            "validated_rerank_digest",
        ):
            if getattr(cursor, field) != getattr(expected, field):
                raise RerankingCursorError("RERANK_CURSOR_IDENTITY_CHANGED:" + field)

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
