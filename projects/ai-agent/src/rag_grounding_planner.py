"""Day102 currentness rechecks and immutable Grounding Bundle planning."""

from __future__ import annotations

from dataclasses import dataclass

from rag_authorized_retriever import (
    InMemoryRetrievalAuthorization,
    RetrievalAuthorizationUnavailable,
)
from rag_chunking_contracts import stable_hash
from rag_grounding_contracts import (
    Day102FailureReason,
    GroundingBundle,
    GroundingContract,
    GroundingRequest,
    SourceWindow,
)
from rag_reranker_contracts import Day101Response, FinalRerankedHit
from rag_retrieval_contracts import CandidateIdentity, RetrievalRecord


class GroundingPlanError(RuntimeError):
    def __init__(self, reason: Day102FailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class CurrentGroundingSources:
    accepted_occurrence_ids: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    authorization_scope_fingerprint: str


class GroundingCurrentnessOracle:
    """Recheck current source authority without trusting cached Day101 state."""

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
        self._superseded: set[str] = set()

    def change_provenance(self, occurrence_id: str, fingerprint: str) -> None:
        self._provenance[occurrence_id] = fingerprint

    def mark_superseded(self, occurrence_id: str) -> None:
        self._superseded.add(occurrence_id)

    def recheck_identities(
        self,
        *,
        identities: tuple[CandidateIdentity, ...],
        request: GroundingRequest,
    ) -> CurrentGroundingSources:
        scope = self._authorization.read(
            tenant_id=request.tenant_id,
            principal_subject=request.principal_subject,
            action=request.action,
            purpose=request.purpose,
        )
        if scope is None:
            raise RetrievalAuthorizationUnavailable(
                "CURRENT_GROUNDING_AUTHORIZATION_NOT_FOUND"
            )
        allowed = frozenset(scope.allowed_occurrence_ids)
        accepted: list[str] = []
        rejected: list[tuple[str, str]] = []
        for identity in identities:
            occurrence_id = identity.occurrence_id
            if occurrence_id not in allowed:
                rejected.append((
                    occurrence_id,
                    Day102FailureReason.STALE_AUTHORIZATION.value,
                ))
                continue
            if occurrence_id in self._superseded:
                rejected.append((
                    occurrence_id,
                    Day102FailureReason.SUPERSEDED_SOURCE.value,
                ))
                continue
            record = self._records.get(occurrence_id)
            if (
                record is None
                or record.identity != identity
                or self._provenance.get(occurrence_id)
                != identity.provenance_fingerprint
            ):
                rejected.append((
                    occurrence_id,
                    Day102FailureReason.STALE_PROVENANCE.value,
                ))
                continue
            accepted.append(occurrence_id)
        return CurrentGroundingSources(
            tuple(accepted), tuple(rejected), scope.fingerprint
        )

    def records_for(
        self, occurrence_ids: tuple[str, ...]
    ) -> tuple[RetrievalRecord, ...]:
        records = []
        for occurrence_id in occurrence_ids:
            record = self._records.get(occurrence_id)
            if record is None:
                raise GroundingPlanError(
                    Day102FailureReason.GROUNDING_PLAN_INVALID
                )
            records.append(record)
        return tuple(records)


class DeterministicContextSelector:
    """Application-owned fixture selector, never a Provider authority."""

    def __init__(self, selected_occurrence_ids: tuple[str, ...]) -> None:
        if len(set(selected_occurrence_ids)) != len(selected_occurrence_ids):
            raise ValueError("selected grounding occurrence IDs must be unique")
        self._selected = selected_occurrence_ids

    def select(
        self,
        *,
        request: GroundingRequest,
        hits: tuple[FinalRerankedHit, ...],
        limit: int,
    ) -> tuple[str, ...]:
        del request
        if self._selected:
            return self._selected[:limit]
        return tuple(hit.identity.occurrence_id for hit in hits[:limit])


class GroundingContextPlanner:
    def __init__(
        self,
        *,
        contract: GroundingContract,
        selector: DeterministicContextSelector,
    ) -> None:
        self.contract = contract
        self.selector = selector

    def plan(
        self,
        *,
        request: GroundingRequest,
        response: Day101Response,
        current_hits: tuple[FinalRerankedHit, ...],
        authorization_scope_fingerprint: str,
    ) -> GroundingBundle:
        selected_ids = self.selector.select(
            request=request,
            hits=current_hits,
            limit=self.contract.max_source_windows,
        )
        if not selected_ids or len(set(selected_ids)) != len(selected_ids):
            raise GroundingPlanError(Day102FailureReason.GROUNDING_PLAN_INVALID)
        by_id = {hit.identity.occurrence_id: hit for hit in current_hits}
        if any(occurrence_id not in by_id for occurrence_id in selected_ids):
            raise GroundingPlanError(Day102FailureReason.GROUNDING_PLAN_INVALID)
        windows: list[SourceWindow] = []
        total_chars = 0
        for occurrence_id in selected_ids:
            hit = by_id[occurrence_id]
            if len(hit.text) > self.contract.max_chars_per_window:
                # The reference fails closed instead of cutting qualifiers or
                # exception clauses at an unsafe character boundary.
                raise GroundingPlanError(
                    Day102FailureReason.GROUNDING_PLAN_INVALID
                )
            total_chars += len(hit.text)
            if total_chars > self.contract.max_total_source_chars:
                raise GroundingPlanError(
                    Day102FailureReason.GROUNDING_PLAN_INVALID
                )
            text_digest = stable_hash(hit.text)
            window_id = stable_hash((
                "DAY102_SOURCE_WINDOW_V1",
                hit.identity.occurrence_id,
                hit.identity.document_version_id,
                hit.source_reference,
                self.contract.source_window_policy_version,
                text_digest,
            ))
            windows.append(SourceWindow(
                window_id=window_id,
                identity=hit.identity,
                source_reference=hit.source_reference,
                exact_span=hit.source_reference,
                day101_rank=hit.rank,
                window_policy_version=(
                    self.contract.source_window_policy_version
                ),
                text_digest=text_digest,
                protected_text=hit.text,
            ))
        if response.original_query_digest is None:
            raise GroundingPlanError(
                Day102FailureReason.INVALID_DAY101_HANDOFF
            )
        request_items_digest = stable_hash(tuple((
            item.item_id,
            item.safe_label,
            stable_hash(item.protected_text),
        ) for item in request.request_items))
        return GroundingBundle(
            operation_id=request.operation_id,
            original_query_digest=response.original_query_digest,
            request_items_digest=request_items_digest,
            day101_handoff_digest=request.day101_handoff_digest,
            authorization_scope_fingerprint=authorization_scope_fingerprint,
            contract_fingerprint=self.contract.fingerprint,
            upstream_outcome=response.outcome.value,
            upstream_reranking_mode=(
                response.reranking_mode.value
                if response.reranking_mode is not None
                else "NOT_RUN"
            ),
            upstream_safe_reason=response.safe_reason,
            windows=tuple(windows),
        )
