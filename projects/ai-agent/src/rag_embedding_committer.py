"""Sole Day98 writer for immutable records, sets, pointer and Outbox intent."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading
from typing import Callable

from rag_acl_contracts import (
    AccessEffect,
    AuthorizationRevisionVector,
    AuthorizationStateUnavailable,
    InMemoryAuthorizationStateStore,
    ResourceRef,
)
from rag_authorized_chunk_reader import AuthorizedEmbeddingInput
from rag_chunking_contracts import stable_hash
from rag_embedding_contracts import (
    EmbeddingAttemptIdentity,
    EmbeddingContract,
    EmbeddingOperationIdentity,
    EmbeddingOutboxIntent,
    EmbeddingRecord,
    EmbeddingSelection,
    EmbeddingSet,
    ValidatedEmbeddingBatch,
    vector_manifest_checksum,
)
from rag_ingestion_contracts import DocumentIdentity
from rag_provenance import CurrentRAGProvenanceValidator


class EmbeddingCommitOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    NOT_READY = "NOT_READY"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    STALE_AUTHORIZATION = "STALE_AUTHORIZATION"
    STALE_PROVENANCE = "STALE_PROVENANCE"
    STALE_SELECTION = "STALE_SELECTION"
    STALE_CONTRACT = "STALE_CONTRACT"


class OutboxHintOutcome(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class EmbeddingClaim:
    operation: EmbeddingOperationIdentity
    attempt: EmbeddingAttemptIdentity
    revision: int
    fence: int


@dataclass(frozen=True)
class EmbeddingCommitResult:
    outcome: EmbeddingCommitOutcome
    safe_reason: str
    embedding_set: EmbeddingSet | None = None
    selection: EmbeddingSelection | None = None
    durable_transition: bool = False


class InMemoryEmbeddingStore:
    """Process-local teaching store; not a distributed transaction proof."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: dict[str, EmbeddingOperationIdentity] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._claims: dict[str, EmbeddingClaim] = {}
        self._sets: dict[str, EmbeddingSet] = {}
        self._result_keys: dict[str, str] = {}
        self._selections: dict[tuple[str, str, str], EmbeddingSelection] = {}
        self._outbox: dict[str, EmbeddingOutboxIntent] = {}
        self._contract_selections: dict[str, tuple[str, int]] = {}

    def select_contract(self, tenant_id: str, fingerprint: str) -> int:
        """Select one current tenant contract and advance only on change."""

        if not tenant_id or not fingerprint:
            raise ValueError("tenant and contract fingerprint are required")
        with self._lock:
            current = self._contract_selections.get(tenant_id)
            if current is not None and current[0] == fingerprint:
                return current[1]
            revision = 1 if current is None else current[1] + 1
            self._contract_selections[tenant_id] = (fingerprint, revision)
            return revision

    def read_contract_selection(self, tenant_id: str) -> tuple[str, int] | None:
        with self._lock:
            return self._contract_selections.get(tenant_id)

    def read_set(self, embedding_set_id: str) -> EmbeddingSet | None:
        with self._lock:
            return self._sets.get(embedding_set_id)

    def read_selection(
        self, tenant_id: str, document_id: str, chunk_set_id: str
    ) -> EmbeddingSelection | None:
        with self._lock:
            return self._selections.get((tenant_id, document_id, chunk_set_id))

    def outbox_intents(self) -> tuple[EmbeddingOutboxIntent, ...]:
        with self._lock:
            return tuple(self._outbox.values())

    def mark_outbox_dispatched(self, event_id: str) -> bool:
        with self._lock:
            current = self._outbox.get(event_id)
            if current is None:
                return False
            self._outbox[event_id] = replace(current, state="DISPATCHED")
            return True

    def classify_outbox_hint(self, event_id: str) -> OutboxHintOutcome:
        """Delivery is a hint; it can never roll the current pointer backward."""

        with self._lock:
            intent = self._outbox.get(event_id)
            if intent is None:
                return OutboxHintOutcome.NOT_FOUND
            current = self._selections.get((
                intent.tenant_id,
                intent.document_id,
                intent.chunk_set_id,
            ))
            if (
                current is not None
                and current.embedding_set_id == intent.embedding_set_id
                and current.revision == intent.selection_revision
            ):
                return OutboxHintOutcome.CURRENT
            return OutboxHintOutcome.STALE


class EmbeddingCommitter:
    def __init__(
        self,
        *,
        store: InMemoryEmbeddingStore,
        authorization: InMemoryAuthorizationStateStore,
        provenance: CurrentRAGProvenanceValidator,
        clock: Callable[[], int],
    ) -> None:
        self._store = store
        self._authorization = authorization
        self._provenance = provenance
        self._clock = clock

    def claim(
        self,
        operation: EmbeddingOperationIdentity,
        attempt: EmbeddingAttemptIdentity,
    ) -> EmbeddingClaim | None:
        if attempt.operation_id != operation.operation_id:
            return None
        store = self._store
        with store._lock:
            previous_operation = store._operations.get(operation.operation_id)
            idem_key = (operation.tenant_id, operation.idempotency_key)
            prior_id = store._idempotency.get(idem_key)
            if previous_operation is not None and previous_operation != operation:
                return None
            if prior_id not in (None, operation.operation_id):
                return None
            previous = store._claims.get(operation.operation_id)
            if previous is None:
                if attempt.attempt_number != 1 or attempt.generation != 1:
                    return None
            elif attempt != previous.attempt and (
                attempt.attempt_number != previous.attempt.attempt_number + 1
                or attempt.generation != previous.attempt.generation + 1
                or attempt.request_id == previous.attempt.request_id
            ):
                return None
            if previous is not None and attempt == previous.attempt:
                return previous
            claim = EmbeddingClaim(
                operation,
                attempt,
                1 if previous is None else previous.revision + 1,
                1 if previous is None else previous.fence + 1,
            )
            store._operations[operation.operation_id] = operation
            store._idempotency[idem_key] = operation.operation_id
            store._claims[operation.operation_id] = claim
            return claim

    def persist(
        self,
        *,
        claim: EmbeddingClaim,
        handoff: AuthorizedEmbeddingInput,
        contract: EmbeddingContract,
        batches: tuple[ValidatedEmbeddingBatch, ...],
        expected_selected_id: str | None,
        expected_selection_revision: int,
    ) -> EmbeddingCommitResult:
        if not batches:
            return EmbeddingCommitResult(
                EmbeddingCommitOutcome.NOT_READY, "NO_VALIDATED_BATCHES"
            )
        store = self._store
        # One process-local critical section models one durable transaction.
        with store._lock:
            if store._claims.get(claim.operation.operation_id) != claim:
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.STALE_ATTEMPT,
                    "EMBEDDING_ATTEMPT_FENCE_STALE",
                )
            if not self._bindings_match(
                claim.operation, handoff, contract
            ):
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.IDENTITY_CONFLICT,
                    "OPERATION_HANDOFF_OR_CONTRACT_BINDING_MISMATCH",
                )
            if store._contract_selections.get(claim.operation.tenant_id) != (
                claim.operation.contract_fingerprint,
                claim.operation.contract_selection_revision,
            ):
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.STALE_CONTRACT,
                    "SELECTED_EMBEDDING_CONTRACT_CHANGED",
                )
            auth_error = self._authorization_error(handoff)
            if auth_error is not None:
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.STALE_AUTHORIZATION, auth_error
                )
            provenance_error = self._provenance_error(handoff, claim.operation)
            if provenance_error is not None:
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.STALE_PROVENANCE,
                    provenance_error,
                )

            by_id: dict[str, tuple[float, ...]] = {}
            for validated in batches:
                for item in validated.candidate.items:
                    if item.item_id in by_id:
                        return EmbeddingCommitResult(
                            EmbeddingCommitOutcome.NOT_READY,
                            "DUPLICATE_ITEM_ACROSS_BATCHES",
                        )
                    by_id[item.item_id] = item.vector
            if set(by_id) != set(claim.operation.authorized_chunk_ids):
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.NOT_READY,
                    "WHOLE_OPERATION_ITEM_SET_MISMATCH",
                )
            ordered_vectors = tuple(
                by_id[chunk_id]
                for chunk_id in claim.operation.authorized_chunk_ids
            )
            manifest = vector_manifest_checksum(
                chunk_ids=claim.operation.authorized_chunk_ids,
                vectors=ordered_vectors,
                contract_fingerprint=contract.fingerprint,
            )
            prior_set_id = store._result_keys.get(
                claim.operation.stable_result_key
            )
            if prior_set_id is not None:
                prior = store._sets[prior_set_id]
                if prior.manifest_checksum != manifest:
                    return EmbeddingCommitResult(
                        EmbeddingCommitOutcome.IDENTITY_CONFLICT,
                        "SAME_RESULT_IDENTITY_HAS_DIFFERENT_VECTOR_MANIFEST",
                    )
                selection = store._selections.get((
                    claim.operation.tenant_id,
                    claim.operation.document_id,
                    claim.operation.chunk_set_id,
                ))
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.ALREADY_COMMITTED,
                    "EXACT_EMBEDDING_SET_ALREADY_COMMITTED",
                    prior,
                    selection,
                )

            key = (
                claim.operation.tenant_id,
                claim.operation.document_id,
                claim.operation.chunk_set_id,
            )
            previous = store._selections.get(key)
            actual_id = None if previous is None else previous.embedding_set_id
            actual_revision = 0 if previous is None else previous.revision
            if (
                actual_id != expected_selected_id
                or actual_revision != expected_selection_revision
            ):
                return EmbeddingCommitResult(
                    EmbeddingCommitOutcome.STALE_SELECTION,
                    "EMBEDDING_SELECTION_BASELINE_CHANGED",
                    selection=previous,
                )
            embedding_set_id = "embedding-set:" + claim.operation.stable_result_key.removeprefix("sha256:")
            views = {chunk.chunk_id: chunk for chunk in handoff.chunks}
            records = tuple(EmbeddingRecord(
                embedding_id="embedding:" + stable_hash((
                    embedding_set_id, ordinal, chunk_id
                )).removeprefix("sha256:"),
                embedding_set_id=embedding_set_id,
                tenant_id=claim.operation.tenant_id,
                chunk_id=chunk_id,
                ordinal=ordinal,
                content_hash=views[chunk_id].content_hash,
                source_segments=views[chunk_id].source_segments,
                contract_fingerprint=contract.fingerprint,
                vector=by_id[chunk_id],
            ) for ordinal, chunk_id in enumerate(
                claim.operation.authorized_chunk_ids
            ))
            embedding_set = EmbeddingSet(
                embedding_set_id,
                claim.operation,
                contract,
                records,
                manifest,
            )
            selection = EmbeddingSelection(
                claim.operation.tenant_id,
                claim.operation.document_id,
                claim.operation.chunk_set_id,
                embedding_set_id,
                actual_revision + 1,
            )
            event_id = stable_hash((key, selection.revision, embedding_set_id))
            outbox = EmbeddingOutboxIntent(
                event_id,
                selection.tenant_id,
                selection.document_id,
                selection.chunk_set_id,
                selection.embedding_set_id,
                selection.revision,
            )
            # These writes are intentionally adjacent under the sole lock.
            store._sets[embedding_set_id] = embedding_set
            store._result_keys[claim.operation.stable_result_key] = embedding_set_id
            store._selections[key] = selection
            store._outbox[event_id] = outbox
            return EmbeddingCommitResult(
                EmbeddingCommitOutcome.COMMITTED,
                "IMMUTABLE_EMBEDDING_SET_SELECTED_WITH_OUTBOX",
                embedding_set,
                selection,
                durable_transition=True,
            )

    def _authorization_error(
        self, handoff: AuthorizedEmbeddingInput
    ) -> str | None:
        if handoff.action != "chunk:read_for_embedding":
            return "EXACT_EMBEDDING_ACTION_REQUIRED"
        if handoff.permit_expires_at <= self._clock():
            return "PERMIT_EXPIRED_BEFORE_COMMIT"
        try:
            membership = self._authorization.read_membership(
                handoff.tenant_id, handoff.principal_subject
            )
            policy = self._authorization.read_policy(
                handoff.tenant_id, handoff.document_id
            )
        except AuthorizationStateUnavailable:
            return "AUTHORIZATION_STATE_UNAVAILABLE"
        if membership is None or policy is None or not membership.active:
            return "CURRENT_AUTHORIZATION_NOT_ACCESSIBLE"
        current = AuthorizationRevisionVector(
            policy.policy_revision,
            policy.acl_revision,
            membership.revision,
            policy.role_version,
            policy.action_catalog_version,
            policy.authorization_epoch,
        )
        if current != handoff.authorization_revisions:
            return "AUTHORIZATION_REVISIONS_CHANGED"
        resource = ResourceRef.chunk_set(
            handoff.tenant_id,
            handoff.document_id,
            handoff.document_version_id,
            handoff.chunk_set_id,
        )
        applicable = tuple(
            entry for entry in policy.entries
            if entry.principal_subject == handoff.principal_subject
            and entry.action == handoff.action
            and entry.resource.is_ancestor_of(resource)
        )
        if (
            handoff.action not in policy.supported_actions
            or any(entry.effect is AccessEffect.DENY for entry in applicable)
            or not any(entry.effect is AccessEffect.ALLOW for entry in applicable)
        ):
            return "CURRENT_EXACT_EMBEDDING_GRANT_NOT_ALLOWED"
        return None

    @staticmethod
    def _bindings_match(
        operation: EmbeddingOperationIdentity,
        handoff: AuthorizedEmbeddingInput,
        contract: EmbeddingContract,
    ) -> bool:
        return (
            operation.tenant_id == handoff.tenant_id
            and operation.principal_subject == handoff.principal_subject
            and operation.authorization_decision_id
            == handoff.authorization_decision_id
            and operation.authorization_revisions
            == handoff.authorization_revisions
            and operation.document_id == handoff.document_id
            and operation.document_version_id == handoff.document_version_id
            and operation.chunk_set_id == handoff.chunk_set_id
            and operation.authorized_chunk_ids == handoff.authorized_chunk_ids
            and operation.selection_revision == handoff.selection_revision
            and operation.document_state_version
            == handoff.document_state_version
            and operation.document_fence == handoff.document_fence
            and operation.contract_fingerprint == contract.fingerprint
        )

    def _provenance_error(
        self,
        handoff: AuthorizedEmbeddingInput,
        operation: EmbeddingOperationIdentity,
    ) -> str | None:
        current = self._provenance.evaluate(
            document=DocumentIdentity(handoff.tenant_id, handoff.document_id),
            expected_chunk_set_id=handoff.chunk_set_id,
        )
        if not current.valid or current.binding is None:
            return "CURRENT_PROVENANCE_NOT_VALID"
        binding = current.binding
        if (
            binding.version.document_version_id != handoff.document_version_id
            or binding.chunk_set_id != handoff.chunk_set_id
            or not set(handoff.authorized_chunk_ids).issubset(binding.chunk_ids)
            or operation.authorized_chunk_ids != handoff.authorized_chunk_ids
            or binding.selection_revision != handoff.selection_revision
            or binding.document_state_version != handoff.document_state_version
            or binding.document_fence != handoff.document_fence
            or operation.contract_fingerprint == ""
        ):
            return "CURRENT_PROVENANCE_OR_FENCE_CHANGED"
        return None
