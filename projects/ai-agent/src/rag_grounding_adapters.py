"""Deterministic Day102 generator, claim extractor and verifier adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_grounding_contracts import (
    ClaimExtractionResult,
    Day102FailureReason,
    ExtractedClaim,
    GeneratedAnswer,
    GroundingBundle,
    GroundingContract,
    RawVerificationResult,
    SemanticRelation,
    ValidatedClaim,
)


class AdapterMode(str, Enum):
    NORMAL = "NORMAL"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class GroundingProviderError(RuntimeError):
    def __init__(self, reason: Day102FailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class GroundingVerificationError(RuntimeError):
    def __init__(self, reason: Day102FailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class DeterministicAnswerProvider:
    """Structured fake. It proves integration behavior, not answer quality."""

    def __init__(
        self,
        *,
        answer_text: str,
        mode: AdapterMode = AdapterMode.NORMAL,
        response_override: GeneratedAnswer | None = None,
    ) -> None:
        self.answer_text = answer_text
        self.mode = mode
        self.response_override = response_override
        self.calls = 0

    def generate(
        self,
        *,
        attempt_id: str,
        bundle: GroundingBundle,
        contract: GroundingContract,
    ) -> GeneratedAnswer:
        self.calls += 1
        if self.mode is AdapterMode.TIMEOUT:
            raise GroundingProviderError(Day102FailureReason.GENERATOR_TIMEOUT)
        if self.mode is AdapterMode.FAILED:
            raise GroundingProviderError(Day102FailureReason.GENERATOR_FAILED)
        if self.response_override is not None:
            return self.response_override
        return GeneratedAnswer(
            attempt_id=attempt_id,
            bundle_digest=bundle.digest,
            generator_contract_fingerprint=contract.fingerprint,
            answer_text=self.answer_text,
        )


@dataclass(frozen=True)
class ClaimTemplate:
    claim_id: str
    request_item_id: str
    protected_text: str
    citation_occurrence_ids: tuple[str, ...]


class DeterministicClaimExtractor:
    """Application adapter for structured Claim/Citation proposals."""

    def __init__(
        self,
        *,
        revision: str,
        templates: tuple[ClaimTemplate, ...],
        response_override: ClaimExtractionResult | None = None,
    ) -> None:
        if not revision:
            raise ValueError("claim extractor revision is required")
        self.revision = revision
        self.templates = templates
        self.response_override = response_override

    def extract(
        self,
        *,
        answer: GeneratedAnswer,
        bundle: GroundingBundle,
    ) -> ClaimExtractionResult:
        if self.response_override is not None:
            return self.response_override
        window_by_occurrence = {
            window.identity.occurrence_id: window.window_id
            for window in bundle.windows
        }
        claims: list[ExtractedClaim] = []
        for template in self.templates:
            start = answer.answer_text.find(template.protected_text)
            if start < 0:
                raise GroundingProviderError(
                    Day102FailureReason.CLAIM_EXTRACTION_INVALID
                )
            end = start + len(template.protected_text)
            citation_window_ids = tuple(
                window_by_occurrence.get(
                    occurrence_id,
                    "OUT_OF_BUNDLE:" + occurrence_id,
                )
                for occurrence_id in template.citation_occurrence_ids
            )
            claims.append(ExtractedClaim(
                claim_id=template.claim_id,
                request_item_id=template.request_item_id,
                answer_start=start,
                answer_end=end,
                protected_text=template.protected_text,
                citation_window_ids=citation_window_ids,
            ))
        return ClaimExtractionResult(
            attempt_id=answer.attempt_id,
            answer_digest=answer.answer_digest,
            extractor_revision=self.revision,
            claims=tuple(claims),
        )


class DeterministicEvidenceVerifier:
    """Independent fake relation provider with explicit immutable revision."""

    def __init__(
        self,
        *,
        revision: str,
        relations_by_claim_id: dict[str, SemanticRelation],
        reasons_by_claim_id: dict[str, str] | None = None,
        mode: AdapterMode = AdapterMode.NORMAL,
        response_override: tuple[RawVerificationResult, ...] | None = None,
    ) -> None:
        if not revision:
            raise ValueError("verifier revision is required")
        self.revision = revision
        self.relations_by_claim_id = dict(relations_by_claim_id)
        self.reasons_by_claim_id = dict(reasons_by_claim_id or {})
        self.mode = mode
        self.response_override = response_override
        self.calls = 0

    def verify(
        self,
        *,
        claims: tuple[ValidatedClaim, ...],
        bundle: GroundingBundle,
        contract: GroundingContract,
    ) -> tuple[RawVerificationResult, ...]:
        self.calls += 1
        if self.mode is AdapterMode.TIMEOUT:
            raise GroundingVerificationError(
                Day102FailureReason.VERIFIER_TIMEOUT
            )
        if self.mode is AdapterMode.FAILED:
            raise GroundingVerificationError(
                Day102FailureReason.VERIFIER_FAILED
            )
        if self.response_override is not None:
            return self.response_override
        results = []
        for item in claims:
            relation = self.relations_by_claim_id.get(
                item.claim.claim_id, SemanticRelation.UNSUPPORTED
            )
            results.append(RawVerificationResult(
                claim_id=item.claim.claim_id,
                claim_digest=item.claim.digest,
                bundle_digest=bundle.digest,
                citation_window_ids=tuple(
                    citation.window_id for citation in item.citations
                ),
                verifier_revision=self.revision,
                verification_policy_version=(
                    contract.verification_policy_version
                ),
                relation=relation,
                reason=self.reasons_by_claim_id.get(
                    item.claim.claim_id, relation.value
                ),
            ))
        return tuple(results)
