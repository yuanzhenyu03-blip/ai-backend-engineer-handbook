"""Sole Day99 generation and activation Committer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading

from rag_chunking_contracts import stable_hash
from rag_embedding_committer import InMemoryEmbeddingStore
from rag_vector_contracts import (
    GenerationState,
    ProductionReadiness,
    RetrievalPolicyRevision,
    SelectedVectorBundle,
    VectorBuildAttempt,
    VectorBuildOperation,
    VectorGeneration,
    VectorIndexContract,
    VectorOutboxIntent,
)
from rag_vector_index_authorization import (
    AuthorizedIndexBuildInput,
    IndexBuildAuthorizationGuard,
)


class VectorCommitOutcome(str, Enum):
    SEALED = "SEALED"
    ALREADY_SEALED = "ALREADY_SEALED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    NOT_READY = "NOT_READY"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    STALE_EMBEDDING_SELECTION = "STALE_EMBEDDING_SELECTION"
    STALE_AUTHORIZATION = "STALE_AUTHORIZATION"
    STALE_CONTRACT = "STALE_CONTRACT"


class ActivationOutcome(str, Enum):
    ACTIVATED = "ACTIVATED"
    ALREADY_ACTIVATED = "ALREADY_ACTIVATED"
    NOT_READY = "NOT_READY"
    STALE_SELECTION = "STALE_SELECTION"
    STALE_FENCE = "STALE_FENCE"
    NOT_FOUND = "NOT_FOUND"


class VectorOutboxHintOutcome(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class VectorBuildClaim:
    operation: VectorBuildOperation
    attempt: VectorBuildAttempt
    revision: int
    fence: int


@dataclass(frozen=True)
class VectorCommitResult:
    outcome: VectorCommitOutcome
    safe_reason: str
    generation: VectorGeneration | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class ActivationResult:
    outcome: ActivationOutcome
    safe_reason: str
    selected_bundle: SelectedVectorBundle | None = None
    durable_transition: bool = False


class InMemoryVectorControlPlane:
    """Process-local teaching state; not distributed durability evidence."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: dict[str, VectorBuildOperation] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._claims: dict[str, VectorBuildClaim] = {}
        self._result_fences: dict[str, int] = {}
        self._unknown_operations: set[str] = set()
        self._generations: dict[str, VectorGeneration] = {}
        self._result_keys: dict[str, str] = {}
        self._selected: dict[str, SelectedVectorBundle] = {}
        self._activation_fences: dict[str, int] = {}
        self._outbox: dict[str, VectorOutboxIntent] = {}
        self._contract_selections: dict[str, tuple[str, int]] = {}

    def select_contract(self, tenant_id: str, fingerprint: str) -> int:
        if not tenant_id or not fingerprint:
            raise ValueError("tenant and index contract fingerprint are required")
        with self._lock:
            current = self._contract_selections.get(tenant_id)
            if current is not None and current[0] == fingerprint:
                return current[1]
            revision = 1 if current is None else current[1] + 1
            self._contract_selections[tenant_id] = (fingerprint, revision)
            return revision

    def read_contract_selection(
        self, tenant_id: str
    ) -> tuple[str, int] | None:
        with self._lock:
            return self._contract_selections.get(tenant_id)

    def read_generation(self, generation_id: str) -> VectorGeneration | None:
        with self._lock:
            return self._generations.get(generation_id)

    def generations(self) -> tuple[VectorGeneration, ...]:
        with self._lock:
            return tuple(self._generations.values())

    def read_selected_bundle(
        self, tenant_id: str
    ) -> SelectedVectorBundle | None:
        with self._lock:
            return self._selected.get(tenant_id)

    def outbox_intents(self) -> tuple[VectorOutboxIntent, ...]:
        with self._lock:
            return tuple(self._outbox.values())

    def mark_outbox_dispatched(self, event_id: str) -> bool:
        with self._lock:
            current = self._outbox.get(event_id)
            if current is None:
                return False
            self._outbox[event_id] = replace(current, state="DISPATCHED")
            return True

    def classify_outbox_hint(
        self, event_id: str
    ) -> VectorOutboxHintOutcome:
        """A delivery hint is classified against current application truth."""

        with self._lock:
            intent = self._outbox.get(event_id)
            if intent is None:
                return VectorOutboxHintOutcome.NOT_FOUND
            if intent.event_type == "VECTOR_GENERATION_SEALED":
                return (
                    VectorOutboxHintOutcome.CURRENT
                    if intent.generation_id in self._generations
                    else VectorOutboxHintOutcome.STALE
                )
            current = self._selected.get(intent.tenant_id)
            if (
                current is not None
                and current.generation_id == intent.generation_id
                and current.revision == intent.revision
            ):
                return VectorOutboxHintOutcome.CURRENT
            return VectorOutboxHintOutcome.STALE


class VectorGenerationCommitter:
    def __init__(
        self,
        *,
        store: InMemoryVectorControlPlane,
        embeddings: InMemoryEmbeddingStore,
        authorization_guard: IndexBuildAuthorizationGuard,
    ) -> None:
        self._store = store
        self._embeddings = embeddings
        self._authorization_guard = authorization_guard

    def claim(
        self,
        operation: VectorBuildOperation,
        attempt: VectorBuildAttempt,
    ) -> VectorBuildClaim | None:
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
            if previous is not None and attempt == previous.attempt:
                return previous
            if operation.operation_id in store._unknown_operations:
                return None
            if previous is None:
                if attempt.attempt_number != 1:
                    return None
            elif (
                attempt.attempt_number != previous.attempt.attempt_number + 1
                or attempt.request_id == previous.attempt.request_id
            ):
                return None
            result_key = operation.stable_result_key
            next_fence = store._result_fences.get(result_key, 0) + 1
            claim = VectorBuildClaim(
                operation,
                attempt,
                1 if previous is None else previous.revision + 1,
                next_fence,
            )
            store._operations[operation.operation_id] = operation
            store._idempotency[idem_key] = operation.operation_id
            store._claims[operation.operation_id] = claim
            store._result_fences[result_key] = next_fence
            return claim

    def mark_unknown(self, claim: VectorBuildClaim) -> None:
        store = self._store
        with store._lock:
            if store._claims.get(claim.operation.operation_id) == claim:
                store._unknown_operations.add(claim.operation.operation_id)

    def persist(
        self,
        *,
        claim: VectorBuildClaim,
        contract: VectorIndexContract,
        generation: VectorGeneration,
        authorization: AuthorizedIndexBuildInput,
    ) -> VectorCommitResult:
        store = self._store
        with store._lock:
            if store._claims.get(claim.operation.operation_id) != claim:
                return VectorCommitResult(
                    VectorCommitOutcome.STALE_ATTEMPT,
                    "VECTOR_BUILD_FENCE_STALE",
                )
            if claim.operation != generation.operation:
                return VectorCommitResult(
                    VectorCommitOutcome.IDENTITY_CONFLICT,
                    "GENERATION_OPERATION_BINDING_MISMATCH",
                )
            if contract != generation.contract:
                return VectorCommitResult(
                    VectorCommitOutcome.IDENTITY_CONFLICT,
                    "GENERATION_CONTRACT_BINDING_MISMATCH",
                )
            authorization_error = self._authorization_guard.check(
                authorization, contract
            )
            if authorization_error is not None:
                if authorization_error == "CURRENT_VECTOR_INDEX_CONTRACT_CHANGED":
                    outcome = VectorCommitOutcome.STALE_CONTRACT
                elif authorization_error == (
                    "CURRENT_INDEX_BUILD_EMBEDDING_SET_CHANGED"
                ):
                    outcome = VectorCommitOutcome.STALE_EMBEDDING_SELECTION
                else:
                    outcome = VectorCommitOutcome.STALE_AUTHORIZATION
                return VectorCommitResult(outcome, authorization_error)
            if not self._current_embedding_matches(claim.operation, contract):
                return VectorCommitResult(
                    VectorCommitOutcome.STALE_EMBEDDING_SELECTION,
                    "CURRENT_EMBEDDING_SELECTION_CHANGED",
                )
            result_key = claim.operation.stable_result_key
            existing_id = store._result_keys.get(result_key)
            if existing_id is not None:
                existing = store._generations[existing_id]
                if self._equivalent_generation(existing, generation):
                    store._unknown_operations.discard(
                        claim.operation.operation_id
                    )
                    return VectorCommitResult(
                        VectorCommitOutcome.ALREADY_SEALED,
                        "EXACT_GENERATION_REPLAY_CONVERGED",
                        existing,
                    )
                return VectorCommitResult(
                    VectorCommitOutcome.IDENTITY_CONFLICT,
                    "STABLE_GENERATION_IDENTITY_CONTENT_CONFLICT",
                )
            if not generation.provider_checkpoint:
                return VectorCommitResult(
                    VectorCommitOutcome.NOT_READY,
                    "PROVIDER_READBACK_CHECKPOINT_REQUIRED",
                )
            store._generations[generation.generation_id] = generation
            store._result_keys[result_key] = generation.generation_id
            event_id = stable_hash((
                "VECTOR_GENERATION_SEALED",
                generation.generation_id,
                generation.manifest.point_count,
                generation.manifest.point_ids_digest,
                generation.manifest.vector_digest,
                generation.manifest.payload_digest,
                generation.manifest.embedding_set_id,
                generation.manifest.contract_fingerprint,
            ))
            store._outbox[event_id] = VectorOutboxIntent(
                event_id,
                "VECTOR_GENERATION_SEALED",
                claim.operation.tenant_id,
                generation.generation_id,
                1,
            )
            store._unknown_operations.discard(claim.operation.operation_id)
            return VectorCommitResult(
                VectorCommitOutcome.SEALED,
                "IMMUTABLE_VECTOR_GENERATION_SEALED_WITH_OUTBOX",
                generation,
                durable_transition=True,
            )

    def activate(
        self,
        *,
        generation_id: str,
        policy: RetrievalPolicyRevision,
        expected_generation_id: str | None,
        expected_revision: int,
        activation_fence: int,
    ) -> ActivationResult:
        store = self._store
        with store._lock:
            generation = store._generations.get(generation_id)
            if generation is None:
                return ActivationResult(
                    ActivationOutcome.NOT_FOUND, "GENERATION_NOT_FOUND"
                )
            tenant_id = generation.operation.tenant_id
            previous_fence = store._activation_fences.get(tenant_id, 0)
            current = store._selected.get(tenant_id)
            if (
                current is not None
                and current.generation_id == generation_id
                and current.retrieval_policy_fingerprint == policy.fingerprint
                and activation_fence == previous_fence
            ):
                return ActivationResult(
                    ActivationOutcome.ALREADY_ACTIVATED,
                    "EXACT_ACTIVATION_REPLAY_CONVERGED",
                    current,
                )
            if activation_fence <= previous_fence:
                return ActivationResult(
                    ActivationOutcome.STALE_FENCE,
                    "ACTIVATION_FENCE_NOT_CURRENT",
                )
            actual_id = None if current is None else current.generation_id
            actual_revision = 0 if current is None else current.revision
            if (
                actual_id != expected_generation_id
                or actual_revision != expected_revision
            ):
                return ActivationResult(
                    ActivationOutcome.STALE_SELECTION,
                    "SELECTED_BUNDLE_CAS_MISMATCH",
                    current,
                )
            if (
                generation.evidence.readiness
                is not ProductionReadiness.PRODUCTION_READY
                or not generation.contract.accepts_policy(policy)
            ):
                return ActivationResult(
                    ActivationOutcome.NOT_READY,
                    "GENERATION_OR_POLICY_HARD_GATES_NOT_READY",
                    current,
                )
            bundle = SelectedVectorBundle(
                tenant_id,
                generation_id,
                generation.contract.fingerprint,
                policy.fingerprint,
                actual_revision + 1,
            )
            event_id = stable_hash((
                "VECTOR_BUNDLE_SELECTED",
                tenant_id,
                bundle.revision,
                generation_id,
                policy.fingerprint,
            ))
            store._selected[tenant_id] = bundle
            store._activation_fences[tenant_id] = activation_fence
            store._generations[generation_id] = replace(
                generation,
                state=GenerationState.ACTIVATED,
            )
            store._outbox[event_id] = VectorOutboxIntent(
                event_id,
                "VECTOR_BUNDLE_SELECTED",
                tenant_id,
                generation_id,
                bundle.revision,
            )
            return ActivationResult(
                ActivationOutcome.ACTIVATED,
                "SELECTED_BUNDLE_AND_OUTBOX_COMMITTED_ATOMICALLY",
                bundle,
                durable_transition=True,
            )

    def _current_embedding_matches(
        self,
        operation: VectorBuildOperation,
        contract: VectorIndexContract,
    ) -> bool:
        selection = self._embeddings.read_selection(
            operation.tenant_id,
            operation.document_id,
            operation.chunk_set_id,
        )
        embedding_set = self._embeddings.read_set(operation.embedding_set_id)
        return (
            selection is not None
            and selection.embedding_set_id == operation.embedding_set_id
            and selection.revision == operation.embedding_selection_revision
            and embedding_set is not None
            and contract.accepts(embedding_set)
        )

    @staticmethod
    def _equivalent_generation(
        left: VectorGeneration,
        right: VectorGeneration,
    ) -> bool:
        """Ignore competing operation metadata for one stable physical result."""

        return (
            left.generation_id == right.generation_id
            and left.contract == right.contract
            and left.manifest == right.manifest
            and bool(left.provider_checkpoint)
            and bool(right.provider_checkpoint)
            and left.evidence == right.evidence
            and left.state == right.state
        )
