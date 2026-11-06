"""Fail-closed Day102 answer, Claim, Citation and verifier validation."""

from __future__ import annotations

from dataclasses import dataclass

from rag_chunking_contracts import stable_hash
from rag_grounding_contracts import (
    CitationRecord,
    ClaimDecision,
    ClaimDisposition,
    ClaimExtractionResult,
    Day102FailureReason,
    GeneratedAnswer,
    GroundingBundle,
    GroundingContract,
    RawVerificationResult,
    SemanticRelation,
    SourceWindow,
    ValidatedClaim,
    VerificationResult,
)


class GroundingValidationError(RuntimeError):
    def __init__(self, reason: Day102FailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class ClaimValidationReport:
    accepted: tuple[ValidatedClaim, ...]
    rejected: tuple[ClaimDecision, ...]


class GroundingValidator:
    def validate_answer(
        self,
        *,
        answer: GeneratedAnswer,
        expected_attempt_id: str,
        bundle: GroundingBundle,
        contract: GroundingContract,
    ) -> None:
        if (
            answer.attempt_id != expected_attempt_id
            or answer.bundle_digest != bundle.digest
            or answer.generator_contract_fingerprint != contract.fingerprint
        ):
            raise GroundingValidationError(
                Day102FailureReason.GENERATOR_OUTPUT_INVALID
            )

    def validate_claims(
        self,
        *,
        answer: GeneratedAnswer,
        extraction: ClaimExtractionResult,
        bundle: GroundingBundle,
        contract: GroundingContract,
        request_item_ids: frozenset[str],
    ) -> ClaimValidationReport:
        if (
            extraction.attempt_id != answer.attempt_id
            or extraction.answer_digest != answer.answer_digest
            or extraction.extractor_revision != contract.claim_extractor_revision
            or len(extraction.claims) > contract.max_claims
        ):
            raise GroundingValidationError(
                Day102FailureReason.CLAIM_EXTRACTION_INVALID
            )
        claim_ids = tuple(item.claim_id for item in extraction.claims)
        if len(set(claim_ids)) != len(claim_ids):
            raise GroundingValidationError(
                Day102FailureReason.CLAIM_EXTRACTION_INVALID
            )
        windows = {window.window_id: window for window in bundle.windows}
        accepted: list[ValidatedClaim] = []
        rejected: list[ClaimDecision] = []
        prior_end = -1
        for claim in sorted(extraction.claims, key=lambda item: item.answer_start):
            if (
                claim.answer_end > len(answer.answer_text)
                or answer.answer_text[claim.answer_start:claim.answer_end]
                != claim.protected_text
                or claim.answer_start < prior_end
            ):
                raise GroundingValidationError(
                    Day102FailureReason.CLAIM_EXTRACTION_INVALID
                )
            prior_end = claim.answer_end
            if claim.request_item_id not in request_item_ids:
                raise GroundingValidationError(
                    Day102FailureReason.CLAIM_EXTRACTION_INVALID
                )
            if not claim.citation_window_ids:
                rejected.append(ClaimDecision(
                    claim_id=claim.claim_id,
                    request_item_id=claim.request_item_id,
                    protected_text=claim.protected_text,
                    disposition=ClaimDisposition.REJECTED,
                    semantic_relation=None,
                    reason=Day102FailureReason.CITATION_REQUIRED.value,
                ))
                continue
            if any(
                window_id not in windows
                for window_id in claim.citation_window_ids
            ):
                rejected.append(ClaimDecision(
                    claim_id=claim.claim_id,
                    request_item_id=claim.request_item_id,
                    protected_text=claim.protected_text,
                    disposition=ClaimDisposition.REJECTED,
                    semantic_relation=None,
                    reason=Day102FailureReason.CITATION_OUT_OF_BUNDLE.value,
                ))
                continue
            citations = tuple(
                self._citation(claim.claim_id, windows[window_id])
                for window_id in claim.citation_window_ids
            )
            accepted.append(ValidatedClaim(claim, citations))
        return ClaimValidationReport(tuple(accepted), tuple(rejected))

    @staticmethod
    def _citation(claim_id: str, window: SourceWindow) -> CitationRecord:
        citation_id = stable_hash((
            "DAY102_CITATION_V1",
            claim_id,
            window.window_id,
            window.identity.document_version_id,
            window.exact_span,
            window.text_digest,
        ))
        return CitationRecord(
            citation_id=citation_id,
            window_id=window.window_id,
            source_identity=window.identity,
            source_reference=window.source_reference,
            exact_span=window.exact_span,
            evidence_digest=window.text_digest,
        )

    def validate_verification(
        self,
        *,
        raw_results: tuple[RawVerificationResult, ...],
        claims: tuple[ValidatedClaim, ...],
        bundle: GroundingBundle,
        contract: GroundingContract,
        expected_verifier_revision: str,
    ) -> tuple[VerificationResult, ...]:
        expected = {item.claim.claim_id: item for item in claims}
        if (
            len(raw_results) != len(expected)
            or len({item.claim_id for item in raw_results}) != len(raw_results)
            or {item.claim_id for item in raw_results} != set(expected)
        ):
            raise GroundingValidationError(
                Day102FailureReason.VERIFIER_OUTPUT_INVALID
            )
        validated = []
        for raw in raw_results:
            claim = expected[raw.claim_id]
            citation_window_ids = tuple(
                citation.window_id for citation in claim.citations
            )
            if (
                raw.claim_digest != claim.claim.digest
                or raw.bundle_digest != bundle.digest
                or raw.citation_window_ids != citation_window_ids
                or raw.verifier_revision != expected_verifier_revision
                or raw.verification_policy_version
                != contract.verification_policy_version
                or not raw.reason
            ):
                raise GroundingValidationError(
                    Day102FailureReason.VERIFIER_OUTPUT_INVALID
                )
            validated.append(VerificationResult(
                claim_id=raw.claim_id,
                claim_digest=raw.claim_digest,
                bundle_digest=raw.bundle_digest,
                citations=claim.citations,
                verifier_revision=raw.verifier_revision,
                verification_policy_version=raw.verification_policy_version,
                relation=raw.relation,
                reason=raw.reason,
            ))
        return tuple(validated)


def relation_failure_reason(relation: SemanticRelation) -> str:
    if relation is SemanticRelation.CONTRADICTION:
        return Day102FailureReason.CONTRADICTED_CLAIM.value
    if relation is SemanticRelation.UNSUPPORTED:
        return Day102FailureReason.UNSUPPORTED_CLAIM.value
    return Day102FailureReason.NONE.value
