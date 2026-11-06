from __future__ import annotations

from examples.day102_grounding_citations import Day102Fixture
from rag_chunking_contracts import stable_hash
from rag_grounding_cache import GroundingCacheKey


def revoke(fixture: Day102Fixture, occurrence_id: str) -> None:
    request = fixture.request
    fixture.authorization.revoke_occurrence(
        tenant_id=request.tenant_id,
        principal_subject=request.principal_subject,
        action=request.action,
        purpose=request.purpose,
        occurrence_id=occurrence_id,
    )


def cache_key(fixture: Day102Fixture, bundle_digest: str) -> GroundingCacheKey:
    contract = fixture.pipeline.contract
    return GroundingCacheKey(
        tenant_id=fixture.request.tenant_id,
        principal_fingerprint=stable_hash((
            "PRINCIPAL", fixture.request.principal_subject
        )),
        action=fixture.request.action,
        purpose=fixture.request.purpose,
        authorization_scope_fingerprint=fixture.scope.fingerprint,
        original_query_digest=(
            fixture.day101_response.original_query_digest or "MISSING"
        ),
        request_items_digest=stable_hash(tuple((
            item.item_id,
            item.safe_label,
            stable_hash(item.protected_text),
        ) for item in fixture.request.request_items)),
        day101_handoff_digest=fixture.request.day101_handoff_digest,
        grounding_bundle_digest=bundle_digest,
        grounding_contract_fingerprint=contract.fingerprint,
        generator_revision=contract.immutable_generator_revision,
        verifier_revision=contract.verifier_revision,
        verification_policy_version=contract.verification_policy_version,
    )
