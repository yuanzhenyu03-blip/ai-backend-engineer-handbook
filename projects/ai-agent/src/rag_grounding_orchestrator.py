"""Authorization-preserving Day102 grounding and guarded answer release."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from rag_authorized_retriever import RetrievalAuthorizationUnavailable
from rag_chunking_contracts import stable_hash
from rag_grounding_adapters import (
    DeterministicAnswerProvider,
    DeterministicClaimExtractor,
    DeterministicEvidenceVerifier,
    GroundingProviderError,
    GroundingVerificationError,
)
from rag_grounding_contracts import (
    ClaimDecision,
    ClaimDisposition,
    ContentSafeGroundingAudit,
    Day102FailureReason,
    Day102Outcome,
    Day102Response,
    GeneratorEgressPolicy,
    GeneratorMode,
    GeneratedAnswer,
    GroundingBundle,
    GroundingContract,
    GroundingDegradationPolicy,
    GroundingRequest,
    RequestCoverage,
    RequestItemStatus,
    RawVerificationResult,
    SemanticRelation,
    ValidatedClaim,
    VerificationMode,
    VerifierEgressPolicy,
)
from rag_grounding_planner import (
    GroundingContextPlanner,
    GroundingCurrentnessOracle,
    GroundingPlanError,
)
from rag_grounding_validator import (
    GroundingValidationError,
    GroundingValidator,
    relation_failure_reason,
)
from rag_query_rewrite_contracts import protected_query_digest
from rag_reranker_contracts import Day101Outcome


class ContentSafeGroundingAuditSink:
    def __init__(self) -> None:
        self._events: list[ContentSafeGroundingAudit] = []

    def record(self, event: ContentSafeGroundingAudit) -> None:
        self._events.append(event)

    def events(self) -> tuple[ContentSafeGroundingAudit, ...]:
        return tuple(self._events)


class AuthorizedGroundingOrchestrator:
    def __init__(
        self,
        *,
        contract: GroundingContract,
        degradation: GroundingDegradationPolicy,
        generator_egress: GeneratorEgressPolicy,
        verifier_egress: VerifierEgressPolicy,
        currentness: GroundingCurrentnessOracle,
        planner: GroundingContextPlanner,
        generator: DeterministicAnswerProvider,
        fallback_generator: DeterministicAnswerProvider | None,
        extractor: DeterministicClaimExtractor,
        verifier: DeterministicEvidenceVerifier,
        fallback_verifier: DeterministicEvidenceVerifier | None,
        validator: GroundingValidator,
        audit: ContentSafeGroundingAuditSink,
        query_digest_secret: bytes,
    ) -> None:
        if verifier.revision != contract.verifier_revision:
            raise ValueError("primary verifier revision must match contract")
        self.contract = contract
        self.degradation = degradation
        self.generator_egress = generator_egress
        self.verifier_egress = verifier_egress
        self.currentness = currentness
        self.planner = planner
        self.generator = generator
        self.fallback_generator = fallback_generator
        self.extractor = extractor
        self.verifier = verifier
        self.fallback_verifier = fallback_verifier
        self.validator = validator
        self.audit = audit
        self._secret = query_digest_secret

    def _generator_calls(self) -> int:
        return self.generator.calls + (
            self.fallback_generator.calls if self.fallback_generator else 0
        )

    def _verifier_calls(self) -> int:
        return self.verifier.calls + (
            self.fallback_verifier.calls if self.fallback_verifier else 0
        )

    def _finish(
        self,
        *,
        request: GroundingRequest,
        response: Day102Response,
        bundle: GroundingBundle | None = None,
    ) -> Day102Response:
        response = replace(
            response,
            generator_calls=self._generator_calls(),
            verifier_calls=self._verifier_calls(),
        )
        query_digest = protected_query_digest(
            self._secret, request.tenant_id, request.original_query
        )
        self.audit.record(ContentSafeGroundingAudit(
            operation_id=request.operation_id,
            original_query_digest=query_digest,
            day101_handoff_digest=request.day101_handoff_digest,
            bundle_digest=bundle.digest if bundle else "NOT_CREATED",
            upstream_outcome=(
                response.upstream_outcome or "NOT_ACCEPTED"
            ),
            generator_mode=response.generator_mode.value,
            verification_mode=response.verification_mode.value,
            outcome=response.outcome.value,
            released_claim_count=len(response.released_claims),
            rejected_claim_count=len(response.rejected_claims),
            abstained_request_item_count=sum(
                item.status is RequestItemStatus.ABSTAINED
                for item in response.request_coverage
            ),
            source_rejection_count=len(response.source_rejections),
            generator_calls=response.generator_calls,
            verifier_calls=response.verifier_calls,
        ))
        return response

    def _empty_response(
        self,
        *,
        request: GroundingRequest,
        outcome: Day102Outcome,
        reason: str,
        bundle: GroundingBundle | None = None,
        generator_mode: GeneratorMode = GeneratorMode.NOT_RUN,
        verification_mode: VerificationMode = VerificationMode.NOT_RUN,
        rejected_claims: tuple[ClaimDecision, ...] = (),
        coverage: tuple[RequestCoverage, ...] = (),
        source_rejections: tuple[tuple[str, str], ...] = (),
    ) -> Day102Response:
        upstream = request.day101_response
        return self._finish(
            request=request,
            bundle=bundle,
            response=Day102Response(
                outcome=outcome,
                safe_reason=reason,
                answer_text="",
                bundle_digest=bundle.digest if bundle else None,
                upstream_outcome=upstream.outcome.value,
                upstream_reranking_mode=(
                    upstream.reranking_mode.value
                    if upstream.reranking_mode else None
                ),
                upstream_safe_reason=upstream.safe_reason,
                generator_mode=generator_mode,
                verification_mode=verification_mode,
                rejected_claims=rejected_claims,
                request_coverage=coverage,
                source_rejections=source_rejections,
            ),
        )

    def _validate_handoff(self, request: GroundingRequest) -> str | None:
        response = request.day101_response
        if (
            response.handoff_digest is None
            or response.handoff_digest != request.day101_handoff_digest
            or response.original_query_digest
            != protected_query_digest(
                self._secret, request.tenant_id, request.original_query
            )
            or response.authorization_scope_fingerprint is None
            or not response.hits
            or tuple(hit.rank for hit in response.hits)
            != tuple(range(1, len(response.hits) + 1))
            or len({hit.identity.occurrence_id for hit in response.hits})
            != len(response.hits)
            or any(
                hit.identity.tenant_id != request.tenant_id
                or stable_hash(hit.text) != hit.identity.content_hash
                for hit in response.hits
            )
        ):
            return Day102FailureReason.INVALID_DAY101_HANDOFF.value
        if response.outcome is Day101Outcome.FULL:
            return None
        if (
            response.outcome is Day101Outcome.DEGRADED
            and self.degradation.allow_degraded_day101_handoff
        ):
            return None
        return Day102FailureReason.UPSTREAM_OUTCOME_NOT_ALLOWED.value

    def _egress_failure(self) -> str | None:
        if (
            self.generator_egress.policy_version
            != self.contract.egress_policy_version
            or self.contract.generator_provider
            not in self.generator_egress.allowed_providers
            or not self.generator_egress.allow_protected_query_egress
            or not self.generator_egress.allow_protected_source_egress
        ):
            return Day102FailureReason.GENERATOR_EGRESS_DENIED.value
        if (
            self.contract.verifier_provider
            not in self.verifier_egress.allowed_providers
            or not self.verifier_egress.allow_protected_claim_egress
            or not self.verifier_egress.allow_protected_source_egress
        ):
            return Day102FailureReason.VERIFIER_EGRESS_DENIED.value
        return None

    def _run_generator(
        self, *, attempt_id: str, bundle: GroundingBundle
    ) -> tuple[GeneratedAnswer, GeneratorMode, str]:
        try:
            answer = self.generator.generate(
                attempt_id=attempt_id,
                bundle=bundle,
                contract=self.contract,
            )
            return answer, GeneratorMode.PRIMARY, Day102FailureReason.NONE.value
        except GroundingProviderError as exc:
            allow = (
                exc.reason is Day102FailureReason.GENERATOR_TIMEOUT
                and self.degradation.allow_generator_fallback_on_timeout
            ) or (
                exc.reason is Day102FailureReason.GENERATOR_FAILED
                and self.degradation.allow_generator_fallback_on_failure
            )
            if not allow or self.fallback_generator is None:
                raise
            answer = self.fallback_generator.generate(
                attempt_id=attempt_id,
                bundle=bundle,
                contract=self.contract,
            )
            return answer, GeneratorMode.FALLBACK, exc.reason.value

    def _run_verifier(
        self,
        *,
        claims: tuple[ValidatedClaim, ...],
        bundle: GroundingBundle,
    ) -> tuple[
        tuple[RawVerificationResult, ...], VerificationMode, str, str
    ]:
        try:
            results = self.verifier.verify(
                claims=claims,
                bundle=bundle,
                contract=self.contract,
            )
            return (
                results,
                VerificationMode.PRIMARY,
                self.verifier.revision,
                Day102FailureReason.NONE.value,
            )
        except GroundingVerificationError as exc:
            allow = (
                exc.reason is Day102FailureReason.VERIFIER_TIMEOUT
                and self.degradation.allow_verifier_fallback_on_timeout
            ) or (
                exc.reason is Day102FailureReason.VERIFIER_FAILED
                and self.degradation.allow_verifier_fallback_on_failure
            )
            if not allow or self.fallback_verifier is None:
                raise
            results = self.fallback_verifier.verify(
                claims=claims,
                bundle=bundle,
                contract=self.contract,
            )
            return (
                results,
                VerificationMode.FALLBACK,
                self.fallback_verifier.revision,
                exc.reason.value,
            )

    def execute(self, request: GroundingRequest) -> Day102Response:
        handoff_failure = self._validate_handoff(request)
        if handoff_failure is not None:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.REJECTED,
                reason=handoff_failure,
            )
        response = request.day101_response
        try:
            precheck = self.currentness.recheck_identities(
                identities=tuple(hit.identity for hit in response.hits),
                request=request,
            )
        except RetrievalAuthorizationUnavailable:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.UNAVAILABLE,
                reason=Day102FailureReason.STALE_AUTHORIZATION.value,
            )
        accepted = frozenset(precheck.accepted_occurrence_ids)
        current_hits = tuple(
            hit for hit in response.hits
            if hit.identity.occurrence_id in accepted
        )
        if not current_hits:
            coverage = tuple(RequestCoverage(
                item.item_id,
                RequestItemStatus.ABSTAINED,
                (),
                Day102FailureReason.REQUEST_ITEM_UNANSWERED.value,
            ) for item in request.request_items)
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.ABSTAINED,
                reason=Day102FailureReason.NO_CURRENT_GROUNDING_SOURCES.value,
                coverage=coverage,
                source_rejections=precheck.rejected,
            )
        try:
            bundle = self.planner.plan(
                request=request,
                response=response,
                current_hits=current_hits,
                authorization_scope_fingerprint=(
                    precheck.authorization_scope_fingerprint
                ),
            )
        except GroundingPlanError as exc:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.REJECTED,
                reason=exc.reason.value,
                source_rejections=precheck.rejected,
            )
        egress_failure = self._egress_failure()
        if egress_failure is not None:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.REJECTED,
                reason=egress_failure,
                bundle=bundle,
                source_rejections=precheck.rejected,
            )
        attempt_id = stable_hash((
            "DAY102_GENERATION_ATTEMPT_V1",
            request.operation_id,
            bundle.digest,
        ))
        try:
            answer, generator_mode, generator_reason = self._run_generator(
                attempt_id=attempt_id, bundle=bundle
            )
        except GroundingProviderError as exc:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.UNAVAILABLE,
                reason=exc.reason.value,
                bundle=bundle,
                source_rejections=precheck.rejected,
            )
        try:
            self.validator.validate_answer(
                answer=answer,
                expected_attempt_id=attempt_id,
                bundle=bundle,
                contract=self.contract,
            )
            extraction = self.extractor.extract(answer=answer, bundle=bundle)
            claim_report = self.validator.validate_claims(
                answer=answer,
                extraction=extraction,
                bundle=bundle,
                contract=self.contract,
                request_item_ids=frozenset(
                    item.item_id for item in request.request_items
                ),
            )
        except (GroundingProviderError, GroundingValidationError) as exc:
            reason = (
                exc.reason.value
                if hasattr(exc, "reason")
                else Day102FailureReason.GENERATOR_OUTPUT_INVALID.value
            )
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.REJECTED,
                reason=reason,
                bundle=bundle,
                generator_mode=generator_mode,
                source_rejections=precheck.rejected,
            )
        if not claim_report.accepted:
            coverage = self._coverage(
                request=request,
                released=(),
            )
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.ABSTAINED,
                reason=Day102FailureReason.REQUEST_ITEM_UNANSWERED.value,
                bundle=bundle,
                generator_mode=generator_mode,
                rejected_claims=claim_report.rejected,
                coverage=coverage,
                source_rejections=precheck.rejected,
            )
        try:
            raw_verification, verification_mode, verifier_revision, verifier_reason = (
                self._run_verifier(
                    claims=claim_report.accepted,
                    bundle=bundle,
                )
            )
            verification = self.validator.validate_verification(
                raw_results=raw_verification,
                claims=claim_report.accepted,
                bundle=bundle,
                contract=self.contract,
                expected_verifier_revision=verifier_revision,
            )
        except GroundingVerificationError as exc:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.UNAVAILABLE,
                reason=exc.reason.value,
                bundle=bundle,
                generator_mode=generator_mode,
                verification_mode=VerificationMode.NOT_RUN,
                rejected_claims=claim_report.rejected,
                source_rejections=precheck.rejected,
            )
        except GroundingValidationError as exc:
            return self._empty_response(
                request=request,
                outcome=Day102Outcome.REJECTED,
                reason=exc.reason.value,
                bundle=bundle,
                generator_mode=generator_mode,
                verification_mode=verification_mode,
                rejected_claims=claim_report.rejected,
                source_rejections=precheck.rejected,
            )
        claims_by_id = {
            item.claim.claim_id: item for item in claim_report.accepted
        }
        released_candidates = []
        rejected = list(claim_report.rejected)
        for result in verification:
            item = claims_by_id[result.claim_id]
            if result.relation is SemanticRelation.SUPPORTED:
                released_candidates.append((item, result))
                continue
            rejected.append(ClaimDecision(
                claim_id=item.claim.claim_id,
                request_item_id=item.claim.request_item_id,
                protected_text=item.claim.protected_text,
                disposition=ClaimDisposition.REJECTED,
                semantic_relation=result.relation,
                reason=relation_failure_reason(result.relation),
                citations=result.citations,
                verification_digest=result.digest,
            ))
        released: list[ClaimDecision] = []
        final_source_rejections: list[tuple[str, str]] = list(precheck.rejected)
        if released_candidates:
            final_identities = tuple({
                citation.source_identity.occurrence_id: citation.source_identity
                for _, result in released_candidates
                for citation in result.citations
            }.values())
            try:
                final_check = self.currentness.recheck_identities(
                    identities=final_identities,
                    request=request,
                )
            except RetrievalAuthorizationUnavailable:
                return self._empty_response(
                    request=request,
                    outcome=Day102Outcome.UNAVAILABLE,
                    reason=Day102FailureReason.STALE_AUTHORIZATION.value,
                    bundle=bundle,
                    generator_mode=generator_mode,
                    verification_mode=verification_mode,
                    rejected_claims=tuple(rejected),
                    source_rejections=tuple(final_source_rejections),
                )
            final_source_rejections.extend(final_check.rejected)
            accepted_final = frozenset(final_check.accepted_occurrence_ids)
            rejection_by_id = dict(final_check.rejected)
            for item, result in released_candidates:
                cited_ids = {
                    citation.source_identity.occurrence_id
                    for citation in result.citations
                }
                stale = sorted(cited_ids - accepted_final)
                if stale:
                    rejected.append(ClaimDecision(
                        claim_id=item.claim.claim_id,
                        request_item_id=item.claim.request_item_id,
                        protected_text=item.claim.protected_text,
                        disposition=ClaimDisposition.REJECTED,
                        semantic_relation=result.relation,
                        reason=rejection_by_id[stale[0]],
                        citations=result.citations,
                        verification_digest=result.digest,
                    ))
                    continue
                released.append(ClaimDecision(
                    claim_id=item.claim.claim_id,
                    request_item_id=item.claim.request_item_id,
                    protected_text=item.claim.protected_text,
                    disposition=ClaimDisposition.RELEASED,
                    semantic_relation=result.relation,
                    reason=Day102FailureReason.NONE.value,
                    citations=result.citations,
                    verification_digest=result.digest,
                ))
        coverage = self._coverage(request=request, released=tuple(released))
        answer_text = self._assemble_answer(
            request=request,
            released=tuple(released),
            coverage=coverage,
            claims_by_id=claims_by_id,
        )
        abstained = any(
            item.status is RequestItemStatus.ABSTAINED for item in coverage
        )
        degraded = (
            response.outcome is Day101Outcome.DEGRADED
            or generator_mode is GeneratorMode.FALLBACK
            or verification_mode is VerificationMode.FALLBACK
            or bool(final_source_rejections)
            or generator_reason != Day102FailureReason.NONE.value
            or verifier_reason != Day102FailureReason.NONE.value
        )
        if not released:
            outcome = Day102Outcome.ABSTAINED
            safe_reason = Day102FailureReason.REQUEST_ITEM_UNANSWERED.value
        elif abstained or rejected:
            outcome = Day102Outcome.PARTIAL
            safe_reason = "PARTIAL_VERIFIED_ANSWER"
        elif degraded:
            outcome = Day102Outcome.DEGRADED
            safe_reason = "VERIFIED_WITH_EXPLICIT_DEGRADATION"
        else:
            outcome = Day102Outcome.FULL
            safe_reason = "FULLY_VERIFIED_GROUNDED_ANSWER"
        return self._finish(
            request=request,
            bundle=bundle,
            response=Day102Response(
                outcome=outcome,
                safe_reason=safe_reason,
                answer_text=answer_text,
                bundle_digest=bundle.digest,
                upstream_outcome=response.outcome.value,
                upstream_reranking_mode=(
                    response.reranking_mode.value
                    if response.reranking_mode else None
                ),
                upstream_safe_reason=response.safe_reason,
                generator_mode=generator_mode,
                verification_mode=verification_mode,
                released_claims=tuple(released),
                rejected_claims=tuple(rejected),
                request_coverage=coverage,
                source_rejections=tuple(dict.fromkeys(final_source_rejections)),
            ),
        )

    @staticmethod
    def _coverage(
        *,
        request: GroundingRequest,
        released: tuple[ClaimDecision, ...],
    ) -> tuple[RequestCoverage, ...]:
        by_item: dict[str, list[str]] = {
            item.item_id: [] for item in request.request_items
        }
        for claim in released:
            by_item[claim.request_item_id].append(claim.claim_id)
        return tuple(RequestCoverage(
            request_item_id=item.item_id,
            status=(
                RequestItemStatus.ANSWERED
                if by_item[item.item_id]
                else RequestItemStatus.ABSTAINED
            ),
            released_claim_ids=tuple(by_item[item.item_id]),
            reason=(
                Day102FailureReason.NONE.value
                if by_item[item.item_id]
                else Day102FailureReason.REQUEST_ITEM_UNANSWERED.value
            ),
        ) for item in request.request_items)

    @staticmethod
    def _assemble_answer(
        *,
        request: GroundingRequest,
        released: tuple[ClaimDecision, ...],
        coverage: tuple[RequestCoverage, ...],
        claims_by_id: Mapping[str, ValidatedClaim],
    ) -> str:
        order = {
            claim_id: item.claim.answer_start
            for claim_id, item in claims_by_id.items()
        }
        parts = [
            item.protected_text
            for item in sorted(released, key=lambda claim: order[claim.claim_id])
        ]
        labels = {item.item_id: item.safe_label for item in request.request_items}
        for item in coverage:
            if item.status is RequestItemStatus.ABSTAINED:
                parts.append(
                    "Unable to verify " + labels[item.request_item_id]
                    + " from current sources."
                )
        return " ".join(parts)
