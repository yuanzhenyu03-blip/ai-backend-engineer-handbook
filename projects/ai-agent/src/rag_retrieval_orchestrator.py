"""Day100 authorization-first hybrid-retrieval orchestration."""

from __future__ import annotations

from dataclasses import replace
import threading
from typing import Callable

from rag_authorized_retriever import (
    GuardedRetrievalReleaser,
    InMemoryRetrievalAuthorization,
    RetrievalAuthorizationUnavailable,
)
from rag_dense_retrieval import DenseRetrievalError, ExactDenseRetrievalAdapter
from rag_hybrid_fusion import reciprocal_rank_fusion
from rag_lexical_retrieval import (
    LexicalRetrievalAdapter,
    LexicalRetrievalError,
)
from rag_query_encoder import QueryEncoderAdapter, QueryEncodingError
from rag_retrieval_cache import (
    CursorValidationError,
    InMemoryRetrievalCache,
    RetrievalCacheEntry,
    RetrievalCacheKey,
    RetrievalCursor,
    RetrievalCursorCodec,
)
from rag_retrieval_contracts import (
    AuthorizedRetrievalHit,
    BranchCandidate,
    ContentSafeRetrievalAudit,
    DegradationReason,
    RetrievalBranch,
    RetrievalOutcome,
    RetrievalRequest,
    RetrievalResponse,
    FusedCandidate,
    SelectedRetrievalBundle,
    RETRIEVAL_ACTION,
    RETRIEVAL_PURPOSE,
)
from rag_retrieval_filters import (
    FilterExpression,
    FilterPlan,
    FilterPlanner,
    UnsupportedFilter,
    matches_filter,
)
from rag_retrieval_validator import (
    InMemoryRetrievalBundleAuthority,
    RetrievalCandidateValidator,
)


class ContentSafeRetrievalAuditSink:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[ContentSafeRetrievalAudit] = []

    def record(self, event: ContentSafeRetrievalAudit) -> None:
        with self._lock:
            self._events.append(event)

    def events(self) -> tuple[ContentSafeRetrievalAudit, ...]:
        with self._lock:
            return tuple(self._events)


class AuthorizedHybridRetriever:
    def __init__(
        self,
        *,
        bundles: InMemoryRetrievalBundleAuthority,
        authorization: InMemoryRetrievalAuthorization,
        filter_planner: FilterPlanner,
        query_encoder: QueryEncoderAdapter,
        lexical: LexicalRetrievalAdapter,
        dense: ExactDenseRetrievalAdapter,
        validator: RetrievalCandidateValidator,
        releaser: GuardedRetrievalReleaser,
        cache: InMemoryRetrievalCache,
        cursors: RetrievalCursorCodec,
        audit: ContentSafeRetrievalAuditSink,
        clock: Callable[[], int],
        classroom_mode: bool,
    ) -> None:
        self._bundles = bundles
        self._authorization = authorization
        self._filter_planner = filter_planner
        self._query_encoder = query_encoder
        self._lexical = lexical
        self._dense = dense
        self._validator = validator
        self._releaser = releaser
        self._cache = cache
        self._cursors = cursors
        self._audit = audit
        self._clock = clock
        self._classroom_mode = classroom_mode

    def retrieve(
        self,
        request: RetrievalRequest,
        *,
        cursor_token: str | None = None,
        system_excluded_occurrence_ids: tuple[str, ...] = (),
    ) -> RetrievalResponse:
        provider_before = self._query_encoder.calls
        database_before = (
            self._lexical.database_calls + self._dense.database_calls
        )
        bundle = self._bundles.read_selected(request.tenant_id)
        if bundle is None:
            return self._finish(
                request,
                None,
                None,
                None,
                RetrievalResponse(
                    RetrievalOutcome.REJECTED,
                    "NO_CURRENT_SELECTED_RETRIEVAL_BUNDLE",
                    request.operation_id,
                    None,
                    None,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )
        if request.client_generation_id is not None:
            return self._finish(
                request,
                bundle,
                None,
                None,
                RetrievalResponse(
                    RetrievalOutcome.REJECTED,
                    "CLIENT_GENERATION_OVERRIDE_FORBIDDEN",
                    request.operation_id,
                    bundle.bundle_id,
                    None,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )
        compatibility_error = self._validate_request(request, bundle)
        if compatibility_error is not None:
            return self._finish(
                request,
                bundle,
                None,
                None,
                RetrievalResponse(
                    RetrievalOutcome.REJECTED,
                    compatibility_error,
                    request.operation_id,
                    bundle.bundle_id,
                    None,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )
        try:
            scope = self._authorization.read(
                tenant_id=request.tenant_id,
                principal_subject=request.principal_subject,
                action=request.action,
                purpose=request.purpose,
            )
        except RetrievalAuthorizationUnavailable:
            return self._finish(
                request,
                bundle,
                None,
                None,
                RetrievalResponse(
                    RetrievalOutcome.UNAVAILABLE,
                    "AUTHORIZATION_STATE_UNAVAILABLE",
                    request.operation_id,
                    bundle.bundle_id,
                    None,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )
        if scope is None or not scope.allowed_occurrence_ids:
            return self._finish(
                request,
                bundle,
                scope,
                None,
                RetrievalResponse(
                    RetrievalOutcome.AUTHORIZATION_DENIED,
                    "CURRENT_RETRIEVAL_GRANT_NOT_ALLOWED",
                    request.operation_id,
                    bundle.bundle_id,
                    scope.decision_id if scope else None,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )
        if request.client_filter is not None and not isinstance(
            request.client_filter, FilterExpression
        ):
            return self._finish(
                request,
                bundle,
                scope,
                None,
                RetrievalResponse(
                    RetrievalOutcome.REJECTED,
                    "CLIENT_FILTER_AST_REQUIRED",
                    request.operation_id,
                    bundle.bundle_id,
                    scope.decision_id,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )
        try:
            plan = self._filter_planner.plan(
                scope=scope,
                client_filter=request.client_filter,
                system_excluded_occurrence_ids=system_excluded_occurrence_ids,
            )
        except UnsupportedFilter as exc:
            return self._finish(
                request,
                bundle,
                scope,
                None,
                RetrievalResponse(
                    RetrievalOutcome.REJECTED,
                    str(exc),
                    request.operation_id,
                    bundle.bundle_id,
                    scope.decision_id,
                    requested_top_k=request.top_k,
                ),
                provider_before,
                database_before,
            )

        offsets = [0, 0]
        if cursor_token is not None:
            try:
                cursor = self._cursors.decode(cursor_token)
                self._cursors.validate_current(
                    cursor,
                    bundle=bundle,
                    scope=scope,
                    principal_hash=self._cursors.principal_hash(
                        request.principal_subject
                    ),
                    query_hash=request.query_hash,
                    filter_plan_fingerprint=plan.fingerprint,
                    now=self._clock(),
                )
                offsets = [cursor.lexical_offset, cursor.dense_offset]
            except CursorValidationError as exc:
                return self._finish(
                    request,
                    bundle,
                    scope,
                    plan,
                    RetrievalResponse(
                        RetrievalOutcome.REJECTED,
                        str(exc),
                        request.operation_id,
                        bundle.bundle_id,
                        scope.decision_id,
                        requested_top_k=request.top_k,
                    ),
                    provider_before,
                    database_before,
                )

        cache_key = self._cache_key(request, bundle, scope, plan)
        cached = self._cache.get(cache_key, now=self._clock())
        if cached is not None and cursor_token is None:
            try:
                release = self._releaser.release(
                    candidates=cached.candidates,
                    initial_scope=scope,
                    limit=request.top_k,
                )
            except RetrievalAuthorizationUnavailable:
                release = None
            if release is not None:
                outcome = (
                    RetrievalOutcome.FULL
                    if release.hits else RetrievalOutcome.EMPTY
                )
                return self._finish(
                    request,
                    bundle,
                    release.current_scope,
                    plan,
                    RetrievalResponse(
                        outcome,
                        "CURRENT_AUTHORIZATION_RECHECKED_CACHE_HIT",
                        request.operation_id,
                        bundle.bundle_id,
                        release.current_scope.decision_id,
                        release.hits,
                        (RetrievalBranch.LEXICAL, RetrievalBranch.DENSE),
                        requested_top_k=request.top_k,
                    ),
                    provider_before,
                    database_before,
                )

        encoded_query = None
        missing: list[RetrievalBranch] = []
        degradation = DegradationReason.NONE
        try:
            encoded_query = self._query_encoder.encode(
                query_text=request.query_text,
                expected_contract_fingerprint=bundle.query_encoder.fingerprint,
            )
        except QueryEncodingError as exc:
            if not bundle.retrieval_policy.allow_lexical_only:
                outcome = (
                    RetrievalOutcome.REJECTED
                    if not exc.provider_called else RetrievalOutcome.UNAVAILABLE
                )
                return self._finish(
                    request,
                    bundle,
                    scope,
                    plan,
                    RetrievalResponse(
                        outcome,
                        exc.reason,
                        request.operation_id,
                        bundle.bundle_id,
                        scope.decision_id,
                        requested_top_k=request.top_k,
                    ),
                    provider_before,
                    database_before,
                )
            missing.append(RetrievalBranch.DENSE)
            degradation = (
                DegradationReason.DENSE_EGRESS_DENIED
                if "EGRESS" in exc.reason or "SENSITIVITY" in exc.reason
                else DegradationReason.DENSE_BRANCH_FAILED
            )

        accumulated: list[BranchCandidate] = []
        candidates_examined = 0
        refill_rounds = 0
        started_ms = self._clock() * 1000
        exhausted = False
        final_hits: tuple[AuthorizedRetrievalHit, ...] = ()
        final_fused: tuple[FusedCandidate, ...] = ()
        completed: set[RetrievalBranch] = set()
        while refill_rounds < bundle.retrieval_policy.max_refill_rounds:
            if (
                self._clock() * 1000 - started_ms
                >= bundle.retrieval_policy.deadline_ms
            ):
                degradation = DegradationReason.DEADLINE_EXHAUSTED
                break
            if candidates_examined >= bundle.retrieval_policy.max_candidate_budget:
                degradation = DegradationReason.REFILL_BUDGET_EXHAUSTED
                break
            refill_rounds += 1
            round_candidates: list[BranchCandidate] = []
            lexical_counts: list[int] = []
            dense_counts: list[int] = []
            for provider_filter in plan.provider_queries:
                try:
                    page = self._lexical.search(
                        query_text=request.query_text,
                        bundle=bundle,
                        scope=scope,
                        business_filter=provider_filter,
                        system_excluded_occurrence_ids=(
                            plan.system_excluded_occurrence_ids
                        ),
                        offset=offsets[0],
                        limit=bundle.fusion_policy.candidate_depth,
                    )
                    lexical_counts.append(len(page))
                    round_candidates.extend(page)
                    completed.add(RetrievalBranch.LEXICAL)
                except LexicalRetrievalError:
                    if not bundle.retrieval_policy.allow_dense_only:
                        return self._finish(
                            request,
                            bundle,
                            scope,
                            plan,
                            RetrievalResponse(
                                RetrievalOutcome.UNAVAILABLE,
                                "LEXICAL_BRANCH_FAILED",
                                request.operation_id,
                                bundle.bundle_id,
                                scope.decision_id,
                                requested_top_k=request.top_k,
                            ),
                            provider_before,
                            database_before,
                        )
                    if RetrievalBranch.LEXICAL not in missing:
                        missing.append(RetrievalBranch.LEXICAL)
                    degradation = DegradationReason.LEXICAL_BRANCH_FAILED
                if encoded_query is not None:
                    try:
                        page = self._dense.search(
                            encoded_query=encoded_query,
                            bundle=bundle,
                            scope=scope,
                            business_filter=provider_filter,
                            system_excluded_occurrence_ids=(
                                plan.system_excluded_occurrence_ids
                            ),
                            offset=offsets[1],
                            limit=bundle.fusion_policy.candidate_depth,
                        )
                        dense_counts.append(len(page))
                        round_candidates.extend(page)
                        completed.add(RetrievalBranch.DENSE)
                    except DenseRetrievalError:
                        if not bundle.retrieval_policy.allow_lexical_only:
                            return self._finish(
                                request,
                                bundle,
                                scope,
                                plan,
                                RetrievalResponse(
                                    RetrievalOutcome.UNAVAILABLE,
                                    "DENSE_BRANCH_FAILED",
                                    request.operation_id,
                                    bundle.bundle_id,
                                    scope.decision_id,
                                    requested_top_k=request.top_k,
                                ),
                                provider_before,
                                database_before,
                            )
                        if RetrievalBranch.DENSE not in missing:
                            missing.append(RetrievalBranch.DENSE)
                        encoded_query = None
                        degradation = DegradationReason.DENSE_BRANCH_FAILED
            offsets[0] += bundle.fusion_policy.candidate_depth
            if encoded_query is not None:
                offsets[1] += bundle.fusion_policy.candidate_depth
            remaining_budget = (
                bundle.retrieval_policy.max_candidate_budget
                - candidates_examined
            )
            budget_truncated = len(round_candidates) > remaining_budget
            if budget_truncated:
                round_candidates = round_candidates[:remaining_budget]
                degradation = DegradationReason.REFILL_BUDGET_EXHAUSTED
            candidates_examined += len(round_candidates)
            accumulated.extend(round_candidates)
            normalized = self._normalize_branch_ranks(accumulated)
            validation = self._validator.validate(
                candidates=normalized,
                bundle=bundle,
                scope=scope,
            )
            accepted = validation.accepted
            if plan.application_post_filter is not None:
                accepted = tuple(
                    candidate for candidate in accepted
                    if matches_filter(
                        plan.application_post_filter,
                        candidate.metadata_dict,
                    )
                )
            final_fused = reciprocal_rank_fusion(
                accepted, policy=bundle.fusion_policy
            )
            try:
                release = self._releaser.release(
                    candidates=final_fused,
                    initial_scope=scope,
                    limit=request.top_k,
                )
            except RetrievalAuthorizationUnavailable:
                return self._finish(
                    request,
                    bundle,
                    scope,
                    plan,
                    RetrievalResponse(
                        RetrievalOutcome.UNAVAILABLE,
                        "FINAL_AUTHORIZATION_STATE_UNAVAILABLE",
                        request.operation_id,
                        bundle.bundle_id,
                        scope.decision_id,
                        requested_top_k=request.top_k,
                    ),
                    provider_before,
                    database_before,
                )
            final_hits = release.hits
            scope = release.current_scope
            if len(final_hits) >= request.top_k:
                break
            if budget_truncated:
                break
            expected = bundle.fusion_policy.candidate_depth
            lexical_exhausted = bool(lexical_counts) and all(
                count < expected for count in lexical_counts
            )
            dense_exhausted = (
                encoded_query is None
                or (bool(dense_counts) and all(count < expected for count in dense_counts))
            )
            exhausted = lexical_exhausted and dense_exhausted
            if exhausted:
                break
        else:
            degradation = DegradationReason.REFILL_BUDGET_EXHAUSTED

        if (
            len(final_hits) < request.top_k
            and not exhausted
            and degradation is DegradationReason.NONE
        ):
            degradation = DegradationReason.REFILL_BUDGET_EXHAUSTED
        if not completed:
            return self._finish(
                request,
                bundle,
                scope,
                plan,
                RetrievalResponse(
                    RetrievalOutcome.UNAVAILABLE,
                    "NO_RETRIEVAL_BRANCH_COMPLETED",
                    request.operation_id,
                    bundle.bundle_id,
                    scope.decision_id,
                    completed_branches=(),
                    missing_branches=tuple(sorted(
                        set(missing), key=lambda item: item.value
                    )),
                    requested_top_k=request.top_k,
                    candidates_examined=candidates_examined,
                    refill_rounds=refill_rounds,
                ),
                provider_before,
                database_before,
            )
        if missing or degradation is not DegradationReason.NONE:
            outcome = RetrievalOutcome.PARTIAL
        elif final_hits:
            outcome = RetrievalOutcome.FULL
        else:
            outcome = RetrievalOutcome.EMPTY

        cursor = RetrievalCursor(
            cursor_version="day100-cursor-v1",
            operation_id=request.operation_id,
            tenant_id=request.tenant_id,
            principal_hash=self._cursors.principal_hash(request.principal_subject),
            authorization_scope_fingerprint=scope.fingerprint,
            bundle_fingerprint=bundle.fingerprint,
            generation_id=bundle.generation_id,
            query_hash=request.query_hash,
            filter_plan_fingerprint=plan.fingerprint,
            retrieval_policy_fingerprint=bundle.retrieval_policy.fingerprint,
            fusion_policy_fingerprint=bundle.fusion_policy.fingerprint,
            lexical_offset=offsets[0],
            dense_offset=offsets[1],
            expires_at=self._clock() + 300,
        )
        cursor_token = self._cursors.encode(cursor)
        if outcome is RetrievalOutcome.FULL:
            self._cache.put(RetrievalCacheEntry(
                cache_key,
                final_fused,
                self._clock() + 60,
            ))
        return self._finish(
            request,
            bundle,
            scope,
            plan,
            RetrievalResponse(
                outcome,
                (
                    "AUTHORIZED_HYBRID_RETRIEVAL_COMPLETED"
                    if outcome is RetrievalOutcome.FULL
                    else "AUTHORIZED_RETRIEVAL_EXPLICITLY_CLASSIFIED"
                ),
                request.operation_id,
                bundle.bundle_id,
                scope.decision_id,
                final_hits,
                tuple(sorted(completed, key=lambda item: item.value)),
                tuple(sorted(set(missing), key=lambda item: item.value)),
                degradation,
                request.top_k,
                candidates_examined,
                refill_rounds,
                cursor=cursor_token,
            ),
            provider_before,
            database_before,
        )

    def _validate_request(
        self,
        request: RetrievalRequest,
        bundle: SelectedRetrievalBundle,
    ) -> str | None:
        if request.action != RETRIEVAL_ACTION or request.purpose != RETRIEVAL_PURPOSE:
            return "RETRIEVAL_ACTION_OR_PURPOSE_MISMATCH"
        if request.top_k > bundle.retrieval_policy.max_top_k:
            return "REQUESTED_TOP_K_EXCEEDS_POLICY"
        if (
            request.query_encoder_contract_fingerprint is not None
            and request.query_encoder_contract_fingerprint
            != bundle.query_encoder.fingerprint
        ):
            return "QUERY_ENCODER_CONTRACT_MISMATCH"
        if bundle.fixture_scope == "DAY100_CLASSROOM_ONLY" and not self._classroom_mode:
            return "SYNTHETIC_BUNDLE_FORBIDDEN_OUTSIDE_CLASSROOM"
        if not bundle.production_eligible and bundle.fixture_scope != "DAY100_CLASSROOM_ONLY":
            return "SELECTED_BUNDLE_NOT_PRODUCTION_ELIGIBLE"
        return None

    def _cache_key(self, request, bundle, scope, plan) -> RetrievalCacheKey:
        return RetrievalCacheKey(
            request.tenant_id,
            self._cursors.principal_hash(request.principal_subject),
            request.action,
            request.purpose,
            scope.fingerprint,
            bundle.fingerprint,
            bundle.generation_id,
            request.query_hash,
            plan.fingerprint,
            bundle.retrieval_policy.fingerprint,
            bundle.fusion_policy.fingerprint,
            "FULL",
        )

    @staticmethod
    def _normalize_branch_ranks(
        candidates: list[BranchCandidate],
    ) -> tuple[BranchCandidate, ...]:
        best: dict[tuple[RetrievalBranch, str], BranchCandidate] = {}
        for candidate in candidates:
            key = (candidate.branch, candidate.identity.key)
            current = best.get(key)
            if current is None or candidate.raw_score > current.raw_score:
                best[key] = candidate
        normalized: list[BranchCandidate] = []
        for branch in RetrievalBranch:
            values = [item for (candidate_branch, _), item in best.items()
                      if candidate_branch is branch]
            values.sort(key=lambda item: (-item.raw_score, item.identity.occurrence_id))
            normalized.extend(
                replace(item, branch_rank=index + 1)
                for index, item in enumerate(values)
            )
        return tuple(normalized)

    def _finish(
        self,
        request: RetrievalRequest,
        bundle: SelectedRetrievalBundle | None,
        scope,
        plan: FilterPlan | None,
        response: RetrievalResponse,
        provider_before: int,
        database_before: int,
    ) -> RetrievalResponse:
        provider_calls = self._query_encoder.calls - provider_before
        database_calls = (
            self._lexical.database_calls + self._dense.database_calls
            - database_before
        )
        response = replace(
            response,
            provider_calls=provider_calls,
            database_calls=database_calls,
        )
        self._audit.record(ContentSafeRetrievalAudit(
            operation_id=request.operation_id,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            principal_hash=self._cursors.principal_hash(request.principal_subject),
            query_hash=request.query_hash,
            selected_bundle_id=bundle.bundle_id if bundle else None,
            selected_generation_id=bundle.generation_id if bundle else None,
            client_generation_hint=request.client_generation_id,
            client_generation_authoritative=False,
            authorization_scope_fingerprint=(scope.fingerprint if scope else None),
            filter_plan_fingerprint=(plan.fingerprint if plan else None),
            outcome=response.outcome.value,
            reason=response.safe_reason,
            completed_branches=tuple(item.value for item in response.completed_branches),
            missing_branches=tuple(item.value for item in response.missing_branches),
            candidates_examined=response.candidates_examined,
            returned_count=len(response.hits),
            provider_calls=provider_calls,
            database_calls=database_calls,
        ))
        return response
