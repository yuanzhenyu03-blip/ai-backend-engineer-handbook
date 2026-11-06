"""Day102 cache identities bound to authority, bundle and verification state."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from rag_chunking_contracts import stable_hash
from rag_grounding_contracts import Day102Outcome, Day102Response


@dataclass(frozen=True)
class GroundingCacheKey:
    tenant_id: str
    principal_fingerprint: str
    action: str
    purpose: str
    authorization_scope_fingerprint: str
    original_query_digest: str
    request_items_digest: str
    day101_handoff_digest: str
    grounding_bundle_digest: str
    grounding_contract_fingerprint: str
    generator_revision: str
    verifier_revision: str
    verification_policy_version: str

    def __post_init__(self) -> None:
        if not all(asdict(self).values()):
            raise ValueError("complete Day102 cache identity is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


class GroundingResponseCache:
    """Exact-identity classroom cache; callers still recheck current release."""

    def __init__(self) -> None:
        self._values: dict[str, Day102Response] = {}

    def put(self, key: GroundingCacheKey, response: Day102Response) -> None:
        if response.outcome not in {
            Day102Outcome.FULL,
            Day102Outcome.DEGRADED,
            Day102Outcome.PARTIAL,
        } or not response.released_claims:
            raise ValueError("only responses with released Claims are cacheable")
        if response.bundle_digest != key.grounding_bundle_digest:
            raise ValueError("cache key and response Bundle must match")
        self._values[key.fingerprint] = response

    def get(
        self,
        key: GroundingCacheKey,
        *,
        current_authorization_scope_fingerprint: str,
    ) -> Day102Response | None:
        if (
            current_authorization_scope_fingerprint
            != key.authorization_scope_fingerprint
        ):
            return None
        return self._values.get(key.fingerprint)
