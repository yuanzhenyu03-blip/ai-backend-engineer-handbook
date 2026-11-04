"""Authorization-preserving Day101 rewrite, fusion and reranking orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from rag_authorized_retriever import (
    InMemoryRetrievalAuthorization,
    RetrievalAuthorizationUnavailable,
)
from rag_chunking_contracts import stable_hash
from rag_multi_query_fusion import (
    MultiQueryCandidate,
    MultiQueryCandidatePool,
    MultiQueryFusionPolicy,
    fuse_multi_query_results,
)
from rag_multi_query_retrieval import (
    Day100VariantRetrievalExecutor,
    MultiQueryRetrievalError,
)
from rag_query_rewrite_contracts import (
    OriginalQueryContract,
    RewriteMode,
    protected_query_digest,
)
from rag_query_rewriter import BoundedQueryRewriter, RewriteError
from rag_reranker_adapter import (
    DeterministicRerankerAdapter,
    RerankerInputBuilder,
    RerankerProviderError,
)
from rag_reranker_contracts import (
    ContentSafeRerankingAudit,
    Day101Outcome,
    Day101Response,
    FinalRerankedHit,
    RerankerContract,
    RerankerEgressPolicy,
    RerankingDegradationPolicy,
    RerankingFailureReason,
    RerankingMode,
    ValidatedRerankResult,
)
from rag_reranking_validator import (
    RerankingValidationError,
    RerankingValidator,
)
from rag_retrieval_contracts import (
    RetrievalRecord,
    RetrievalRequest,
    SelectedRetrievalBundle,
)


@dataclass(frozen=True)
class Day101Eligibility:
    classroom_mode: bool
    production_mode: bool


@dataclass(frozen=True)
class CurrentCandidate:
    candidate: MultiQueryCandidate
    record: RetrievalRecord


@dataclass(frozen=True)
class CurrentnessReport:
    accepted: tuple[CurrentCandidate, ...]
    rejected: tuple[tuple[str, str], ...]
    authorization_scope_fingerprint: str


class Day100CurrentnessOracle:
    """Rechecks current authorization and provenance before protected release."""

    def __init__(
        self,
        *,
        authorization: InMemoryRetrievalAuthorization,
        records: tuple[RetrievalRecord, ...],
    ) -> None:
        self._authorization = authorization
        self._records = {
            record.identity.occurrence_id: record for record in records
        }
        self._provenance = {
            record.identity.occurrence_id: record.identity.provenance_fingerprint
            for record in records
        }

    def change_provenance(self, occurrence_id: str, fingerprint: str) -> None:
        self._provenance[occurrence_id] = fingerprint

    def recheck(
        self,
        *,
        candidates: tuple[MultiQueryCandidate, ...],
        request: RetrievalRequest,
    ) -> CurrentnessReport:
        scope = self._authorization.read(
            tenant_id=request.tenant_id,
            principal_subject=request.principal_subject,
            action=request.action,
            purpose=request.purpose,
        )
        if scope is None:
            raise RetrievalAuthorizationUnavailable(
                "CURRENT_RETRIEVAL_AUTHORIZATION_NOT_FOUND"
            )
        allowed = frozenset(scope.allowed_occurrence_ids)
        accepted: list[CurrentCandidate] = []
        rejected: list[tuple[str, str]] = []
        for candidate in candidates:
            occurrence_id = candidate.identity.occurrence_id
            if occurrence_id not in allowed:
                rejected.append((
                    occurrence_id,
                    RerankingFailureReason.STALE_AUTHORIZATION.value,
                ))
                continue
            record = self._records.get(occurrence_id)
            if (
                record is None
                or record.identity != candidate.identity
                or self._provenance.get(occurrence_id)
                != candidate.identity.provenance_fingerprint
            ):
                rejected.append((
                    occurrence_id,
                    RerankingFailureReason.STALE_PROVENANCE.value,
                ))
                continue
            accepted.append(CurrentCandidate(candidate, record))
        return CurrentnessReport(
            tuple(accepted), tuple(rejected), scope.fingerprint
        )


class ContentSafeRerankingAuditSink:
    def __init__(self) -> None:
        self._events: list[ContentSafeRerankingAudit] = []

    def record(self, event: ContentSafeRerankingAudit) -> None:
        self._events.append(event)

    def events(self) -> tuple[ContentSafeRerankingAudit, ...]:
        return tuple(self._events)


class AuthorizedRerankingOrchestrator:
    def __init__(
        self,
        *,
        selected_bundle: SelectedRetrievalBundle | None,
        eligibility: Day101Eligibility,
        rewriter: BoundedQueryRewriter,
        multi_query: Day100VariantRetrievalExecutor,
        fusion_policy: MultiQueryFusionPolicy,
        currentness: Day100CurrentnessOracle,
        reranker_contract: RerankerContract,
        reranker_egress: RerankerEgressPolicy,
        reranking_degradation: RerankingDegradationPolicy,
        input_builder: RerankerInputBuilder,
        reranker: DeterministicRerankerAdapter,
        validator: RerankingValidator,
        audit: ContentSafeRerankingAuditSink,
        query_digest_secret: bytes,
    ) -> None:
        self.bundle = selected_bundle
        self.eligibility = eligibility
        self.rewriter = rewriter
        self.multi_query = multi_query
        self.fusion_policy = fusion_policy
        self.currentness = currentness
        self.reranker_contract = reranker_contract
        self.reranker_egress = reranker_egress
        self.reranking_degradation = reranking_degradation
        self.input_builder = input_builder
        self.reranker = reranker
        self.validator = validator
        self.audit = audit
        self._secret = query_digest_secret

    def _eligibility_failure(self, request: RetrievalRequest) -> Day101Response | None:
        if self.bundle is None or not self.bundle.selected:
            return Day101Response(
                Day101Outcome.REJECTED,
                RerankingFailureReason.NO_CURRENT_DAY100_BUNDLE.value,
                None,
                None,
            )
        if self.bundle.tenant_id != request.tenant_id:
            return Day101Response(
                Day101Outcome.REJECTED,
                RerankingFailureReason.DAY100_HANDOFF_REJECTED.value,
                None,
                None,
            )
        if self.eligibility.production_mode and not self.bundle.production_eligible:
            return Day101Response(
                Day101Outcome.REJECTED,
                RerankingFailureReason.DAY100_HANDOFF_REJECTED.value,
                None,
                None,
            )
        if (
            self.bundle.fixture_scope == "DAY100_CLASSROOM_ONLY"
            and not self.eligibility.classroom_mode
        ):
            return Day101Response(
                Day101Outcome.REJECTED,
                RerankingFailureReason.DAY100_HANDOFF_REJECTED.value,
                None,
                None,
            )
        return None

    def _original_query(self, request: RetrievalRequest) -> OriginalQueryContract:
        assert self.bundle is not None
        filter_fingerprint = (
            request.client_filter.fingerprint
            if request.client_filter is not None
            else "NO_CLIENT_FILTER"
        )
        return OriginalQueryContract(
            request.operation_id,
            request.tenant_id,
            stable_hash(("PRINCIPAL", request.principal_subject)),
            request.action,
            request.purpose,
            protected_query_digest(
                self._secret, request.tenant_id, request.query_text
            ),
            self.bundle.fingerprint,
            filter_fingerprint,
            request.query_text,
        )

    def _finish(
        self,
        *,
        request: RetrievalRequest,
        original: OriginalQueryContract,
        response: Day101Response,
        rewrite_before: int,
        reranker_before: int,
    ) -> Day101Response:
        response = Day101Response(
            response.outcome,
            response.safe_reason,
            response.rewrite_mode,
            response.reranking_mode,
            response.hits,
            response.rewrite_set_fingerprint,
            response.candidate_pool_digest,
            response.validated_rerank_digest,
            response.release_rejections,
            self.rewriter.provider.calls - rewrite_before,
            self.reranker.calls - reranker_before,
        )
        self.audit.record(ContentSafeRerankingAudit(
            request.operation_id,
            original.query_digest,
            response.rewrite_mode or "NOT_RUN",
            response.candidate_pool_digest or "NOT_RUN",
            response.reranking_mode.value if response.reranking_mode else "NOT_RUN",
            response.outcome.value,
            len(response.hits),
            len(response.release_rejections),
            response.rewrite_provider_calls,
            response.reranker_provider_calls,
        ))
        return response

    def execute(self, request: RetrievalRequest) -> Day101Response:
        rewrite_before = self.rewriter.provider.calls
        reranker_before = self.reranker.calls
        eligibility_failure = self._eligibility_failure(request)
        if eligibility_failure is not None:
            # Eligibility rejection happens before protected query Provider work.
            original = OriginalQueryContract(
                request.operation_id,
                request.tenant_id,
                stable_hash(("PRINCIPAL", request.principal_subject)),
                request.action,
                request.purpose,
                protected_query_digest(
                    self._secret, request.tenant_id, request.query_text
                ),
                self.bundle.fingerprint if self.bundle else "NO_BUNDLE",
                "NO_FILTER_PLAN",
                request.query_text,
            )
            return self._finish(
                request=request,
                original=original,
                response=eligibility_failure,
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )
        original = self._original_query(request)
        try:
            rewrite_set = self.rewriter.rewrite(original)
        except RewriteError as exc:
            return self._finish(
                request=request,
                original=original,
                response=Day101Response(
                    Day101Outcome.UNAVAILABLE,
                    exc.reason.value,
                    None,
                    None,
                ),
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )
        try:
            retrieval = self.multi_query.execute(
                base_request=request, rewrite_set=rewrite_set
            )
            pool = fuse_multi_query_results(retrieval, self.fusion_policy)
        except MultiQueryRetrievalError as exc:
            return self._finish(
                request=request,
                original=original,
                response=Day101Response(
                    Day101Outcome.UNAVAILABLE,
                    str(exc),
                    rewrite_set.mode.value,
                    None,
                    rewrite_set_fingerprint=rewrite_set.fingerprint,
                ),
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )
        if not pool.candidates:
            return self._finish(
                request=request,
                original=original,
                response=Day101Response(
                    Day101Outcome.EMPTY,
                    RerankingFailureReason.EMPTY_AUTHORIZED_RESULT.value,
                    rewrite_set.mode.value,
                    None,
                    rewrite_set_fingerprint=rewrite_set.fingerprint,
                    candidate_pool_digest=pool.digest,
                ),
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )

        try:
            precheck = self.currentness.recheck(
                candidates=pool.candidates, request=request
            )
        except RetrievalAuthorizationUnavailable:
            return self._finish(
                request=request,
                original=original,
                response=Day101Response(
                    Day101Outcome.UNAVAILABLE,
                    RerankingFailureReason.STALE_AUTHORIZATION.value,
                    rewrite_set.mode.value,
                    None,
                    rewrite_set_fingerprint=rewrite_set.fingerprint,
                    candidate_pool_digest=pool.digest,
                ),
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )
        current_pool = MultiQueryCandidatePool(
            pool.rewrite_set_fingerprint,
            pool.fusion_policy_fingerprint,
            tuple(item.candidate for item in precheck.accepted),
            pool.truncated,
        )
        if not current_pool.candidates:
            return self._finish(
                request=request,
                original=original,
                response=Day101Response(
                    Day101Outcome.EMPTY,
                    RerankingFailureReason.EMPTY_AUTHORIZED_RESULT.value,
                    rewrite_set.mode.value,
                    None,
                    rewrite_set_fingerprint=rewrite_set.fingerprint,
                    candidate_pool_digest=current_pool.digest,
                    release_rejections=precheck.rejected,
                ),
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )

        validated: ValidatedRerankResult | None = None
        reranking_mode = RerankingMode.RERANKED_SUCCESS
        rerank_failure = RerankingFailureReason.NONE
        egress_allowed = (
            self.reranker_contract.provider in self.reranker_egress.allowed_providers
            and self.reranker_egress.allow_protected_query_egress
            and self.reranker_egress.allow_protected_candidate_egress
            and self.reranker_egress.policy_version
            == self.reranker_contract.egress_policy_version
        )
        if not egress_allowed:
            rerank_failure = RerankingFailureReason.RERANK_EGRESS_DENIED
            if not self.reranking_degradation.allow_unreranked_on_egress_denied:
                return self._finish(
                    request=request,
                    original=original,
                    response=Day101Response(
                        Day101Outcome.REJECTED,
                        rerank_failure.value,
                        rewrite_set.mode.value,
                        None,
                        rewrite_set_fingerprint=rewrite_set.fingerprint,
                        candidate_pool_digest=current_pool.digest,
                    ),
                    rewrite_before=rewrite_before,
                    reranker_before=reranker_before,
                )
            reranking_mode = RerankingMode.UNRERANKED_FALLBACK
        else:
            rerank_request = self.input_builder.build(
                original_query_digest=original.query_digest,
                protected_query=original.protected_text,
                pool=current_pool,
            )
            try:
                raw = self.reranker.rank(rerank_request)
                validated = self.validator.validate(
                    request=rerank_request,
                    response=raw,
                    contract=self.reranker_contract,
                ).result
            except RerankerProviderError as exc:
                rerank_failure = (
                    RerankingFailureReason.RERANKER_TIMEOUT
                    if "TIMEOUT" in str(exc)
                    else RerankingFailureReason.RERANKER_FAILED
                )
                allowed = (
                    rerank_failure is RerankingFailureReason.RERANKER_TIMEOUT
                    and self.reranking_degradation.allow_unreranked_on_timeout
                ) or (
                    rerank_failure is RerankingFailureReason.RERANKER_FAILED
                    and self.reranking_degradation.allow_unreranked_on_provider_failure
                )
                if not allowed:
                    return self._finish(
                        request=request,
                        original=original,
                        response=Day101Response(
                            Day101Outcome.UNAVAILABLE,
                            rerank_failure.value,
                            rewrite_set.mode.value,
                            None,
                            rewrite_set_fingerprint=rewrite_set.fingerprint,
                            candidate_pool_digest=current_pool.digest,
                        ),
                        rewrite_before=rewrite_before,
                        reranker_before=reranker_before,
                    )
                reranking_mode = RerankingMode.UNRERANKED_FALLBACK
            except RerankingValidationError:
                rerank_failure = RerankingFailureReason.RERANKER_OUTPUT_INVALID
                if not self.reranking_degradation.allow_unreranked_on_invalid_output:
                    return self._finish(
                        request=request,
                        original=original,
                        response=Day101Response(
                            Day101Outcome.REJECTED,
                            rerank_failure.value,
                            rewrite_set.mode.value,
                            None,
                            rewrite_set_fingerprint=rewrite_set.fingerprint,
                            candidate_pool_digest=current_pool.digest,
                        ),
                        rewrite_before=rewrite_before,
                        reranker_before=reranker_before,
                    )
                reranking_mode = RerankingMode.UNRERANKED_FALLBACK

        by_id = {
            item.identity.occurrence_id: item for item in current_pool.candidates
        }
        score_by_id: dict[str, float] = {}
        prior_rank_by_id = {
            item.identity.occurrence_id: rank
            for rank, item in enumerate(current_pool.candidates, start=1)
        }
        if validated is not None:
            ordered = tuple(by_id[item.candidate_id] for item in validated.items)
            score_by_id = {item.candidate_id: item.score for item in validated.items}
            prior_rank_by_id = {
                item.candidate_id: item.prior_fusion_rank for item in validated.items
            }
        else:
            ordered = current_pool.candidates

        try:
            final = self.currentness.recheck(candidates=ordered, request=request)
        except RetrievalAuthorizationUnavailable:
            return self._finish(
                request=request,
                original=original,
                response=Day101Response(
                    Day101Outcome.UNAVAILABLE,
                    RerankingFailureReason.STALE_AUTHORIZATION.value,
                    rewrite_set.mode.value,
                    reranking_mode,
                    rewrite_set_fingerprint=rewrite_set.fingerprint,
                    candidate_pool_digest=current_pool.digest,
                    validated_rerank_digest=validated.digest if validated else None,
                ),
                rewrite_before=rewrite_before,
                reranker_before=reranker_before,
            )
        hits = tuple(
            FinalRerankedHit(
                rank,
                item.candidate.identity,
                item.candidate.source_hit.source_reference,
                score_by_id.get(item.candidate.identity.occurrence_id),
                prior_rank_by_id[item.candidate.identity.occurrence_id],
                item.record.text,
            )
            for rank, item in enumerate(final.accepted, start=1)
        )
        all_rejections = precheck.rejected + final.rejected
        degraded = (
            rewrite_set.mode is not RewriteMode.FULL_REWRITE
            or reranking_mode is RerankingMode.UNRERANKED_FALLBACK
            or bool(retrieval.failed_variants)
            or current_pool.truncated
            or bool(all_rejections)
        )
        if not hits:
            outcome = Day101Outcome.EMPTY
            safe_reason = RerankingFailureReason.EMPTY_AUTHORIZED_RESULT.value
        elif degraded:
            outcome = Day101Outcome.DEGRADED
            safe_reason = (
                rerank_failure.value
                if rerank_failure is not RerankingFailureReason.NONE
                else "DAY101_EXPLICITLY_DEGRADED"
            )
        else:
            outcome = Day101Outcome.FULL
            safe_reason = "FULL_REWRITTEN_RERANKED_SUCCESS"
        return self._finish(
            request=request,
            original=original,
            response=Day101Response(
                outcome,
                safe_reason,
                rewrite_set.mode.value,
                reranking_mode,
                hits,
                rewrite_set.fingerprint,
                current_pool.digest,
                validated.digest if validated else None,
                all_rejections,
            ),
            rewrite_before=rewrite_before,
            reranker_before=reranker_before,
        )
