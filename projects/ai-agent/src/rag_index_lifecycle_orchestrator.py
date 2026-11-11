"""Thin Day104 build, Provider seal and authoritative read-back flow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import threading

from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_committer import (
    GenerationBuildRecord,
    IndexLifecycleCommitter,
    ProviderSealRecord,
    RegistrationOutcome,
)
from rag_index_lifecycle_contracts import (
    BuildSnapshot,
    EvaluationRuler,
    GenerationManifest,
    ManifestFacts,
    ValidationDecision,
    ValidationRecord,
)


@dataclass(frozen=True, order=True)
class IndexedOccurrence:
    occurrence_id: str
    content_digest: str
    metadata_digest: str
    provenance_digest: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.occurrence_id,
                self.content_digest,
                self.metadata_digest,
                self.provenance_digest,
            )
        ):
            raise ValueError("complete content-safe occurrence facts are required")


def manifest_facts(
    occurrences: tuple[IndexedOccurrence, ...],
) -> ManifestFacts:
    ordered = tuple(sorted(occurrences, key=lambda item: item.occurrence_id))
    if len({item.occurrence_id for item in ordered}) != len(ordered):
        raise ValueError("occurrence IDs must be unique")
    return ManifestFacts(
        occurrence_ids=tuple(item.occurrence_id for item in ordered),
        content_digest=stable_hash(
            tuple((item.occurrence_id, item.content_digest) for item in ordered)
        ),
        metadata_digest=stable_hash(
            tuple((item.occurrence_id, item.metadata_digest) for item in ordered)
        ),
        provenance_digest=stable_hash(
            tuple((item.occurrence_id, item.provenance_digest) for item in ordered)
        ),
    )


class ProviderWriteOutcome(str, Enum):
    WRITTEN = "WRITTEN"
    EXACT_REPLAY = "EXACT_REPLAY"
    STALE_FENCE = "STALE_FENCE"
    SEALED = "SEALED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class BuildValidationOutcome(str, Enum):
    VALIDATING = "VALIDATING"
    REJECTED = "REJECTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True)
class ProviderWriteResult:
    outcome: ProviderWriteOutcome
    safe_reason: str
    checkpoint: str | None = None


@dataclass(frozen=True)
class _ProviderGeneration:
    generation_id: str
    namespace: str
    occurrences: tuple[IndexedOccurrence, ...]
    fence: int
    checkpoint: str
    sealed: bool


@dataclass(frozen=True)
class BuildValidationResult:
    outcome: BuildValidationOutcome
    safe_reason: str
    manifest: GenerationManifest | None = None
    validation: ValidationRecord | None = None
    seal: ProviderSealRecord | None = None


class DeterministicSealedIndexProvider:
    """Process-local Provider fake with immutable sealed namespaces."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generations: dict[str, _ProviderGeneration] = {}
        self._namespace_bindings: dict[str, str] = {}

    def replace_generation(
        self,
        *,
        generation_id: str,
        namespace: str,
        occurrences: tuple[IndexedOccurrence, ...],
        fence: int,
    ) -> ProviderWriteResult:
        if not generation_id or not namespace or fence <= 0:
            raise ValueError("generation, namespace and positive fence are required")
        canonical = tuple(sorted(occurrences, key=lambda item: item.occurrence_id))
        manifest_facts(canonical)
        with self._lock:
            current = self._generations.get(generation_id)
            namespace_generation = self._namespace_bindings.get(namespace)
            if (
                namespace_generation is not None
                and namespace_generation != generation_id
            ):
                return ProviderWriteResult(
                    ProviderWriteOutcome.IDENTITY_CONFLICT,
                    "PHYSICAL_NAMESPACE_ALREADY_BOUND_TO_OTHER_GENERATION",
                )
            if current is not None and current.namespace != namespace:
                return ProviderWriteResult(
                    ProviderWriteOutcome.IDENTITY_CONFLICT,
                    "GENERATION_ALREADY_BOUND_TO_OTHER_PHYSICAL_NAMESPACE",
                    current.checkpoint,
                )
            if current is not None and current.sealed:
                return ProviderWriteResult(
                    ProviderWriteOutcome.SEALED,
                    "SEALED_GENERATION_REJECTS_ALL_WRITES",
                    current.checkpoint,
                )
            if current is not None and fence < current.fence:
                return ProviderWriteResult(
                    ProviderWriteOutcome.STALE_FENCE,
                    "PROVIDER_WRITE_FENCE_NOT_CURRENT",
                    current.checkpoint,
                )
            if current is not None and fence == current.fence:
                if current.namespace == namespace and current.occurrences == canonical:
                    return ProviderWriteResult(
                        ProviderWriteOutcome.EXACT_REPLAY,
                        "EXACT_PROVIDER_WRITE_REPLAY_CONVERGED",
                        current.checkpoint,
                    )
                return ProviderWriteResult(
                    ProviderWriteOutcome.IDENTITY_CONFLICT,
                    "PROVIDER_FENCE_ALREADY_BOUND_TO_OTHER_CONTENT",
                    current.checkpoint,
                )
            checkpoint = stable_hash(
                (
                    "DAY104_PROVIDER_CHECKPOINT",
                    generation_id,
                    namespace,
                    fence,
                    tuple(asdict(item) for item in canonical),
                )
            )
            self._generations[generation_id] = _ProviderGeneration(
                generation_id,
                namespace,
                canonical,
                fence,
                checkpoint,
                False,
            )
            self._namespace_bindings[namespace] = generation_id
            return ProviderWriteResult(
                ProviderWriteOutcome.WRITTEN,
                "PROVIDER_GENERATION_REPLACED_OFF_ACTIVE_PATH",
                checkpoint,
            )

    def seal(
        self,
        *,
        generation_id: str,
        expected_checkpoint: str,
        expected_fence: int,
    ) -> ProviderSealRecord | None:
        with self._lock:
            current = self._generations.get(generation_id)
            if current is None:
                return None
            if (
                current.checkpoint != expected_checkpoint
                or current.fence != expected_fence
            ):
                return None
            if not current.sealed:
                current = _ProviderGeneration(
                    current.generation_id,
                    current.namespace,
                    current.occurrences,
                    current.fence,
                    current.checkpoint,
                    True,
                )
                self._generations[generation_id] = current
            return ProviderSealRecord(
                current.generation_id,
                current.namespace,
                current.checkpoint,
                current.fence,
            )

    def readback(
        self, generation_id: str
    ) -> tuple[tuple[IndexedOccurrence, ...], ProviderSealRecord] | None:
        with self._lock:
            current = self._generations.get(generation_id)
            if current is None or not current.sealed:
                return None
            return current.occurrences, ProviderSealRecord(
                current.generation_id,
                current.namespace,
                current.checkpoint,
                current.fence,
            )


class IndexLifecycleOrchestrator:
    def __init__(
        self,
        *,
        provider: DeterministicSealedIndexProvider,
        committer: IndexLifecycleCommitter,
    ) -> None:
        self._provider = provider
        self._committer = committer

    def build_and_validate(
        self,
        *,
        generation_id: str,
        build_snapshot: BuildSnapshot,
        evaluation_ruler: EvaluationRuler,
        expected_occurrences: tuple[IndexedOccurrence, ...],
        physical_namespace: str,
        provider_write_fence: int,
        validation_id: str,
        validator_version: str,
        observed_at: str,
        expected_absent_occurrence_ids: tuple[str, ...] = (),
        provider_occurrences: tuple[IndexedOccurrence, ...] | None = None,
    ) -> BuildValidationResult:
        expected = manifest_facts(expected_occurrences)
        actual_write = (
            expected_occurrences
            if provider_occurrences is None
            else provider_occurrences
        )
        write = self._provider.replace_generation(
            generation_id=generation_id,
            namespace=physical_namespace,
            occurrences=actual_write,
            fence=provider_write_fence,
        )
        if write.outcome is ProviderWriteOutcome.SEALED:
            sealed_readback = self._provider.readback(generation_id)
            canonical_write = tuple(
                sorted(
                    actual_write,
                    key=lambda item: item.occurrence_id,
                )
            )
            if sealed_readback is None or sealed_readback[0] != canonical_write:
                return BuildValidationResult(
                    BuildValidationOutcome.REJECTED,
                    "SEALED_GENERATION_CONTENT_CONFLICT",
                )
            seal = sealed_readback[1]
            if (
                seal.physical_namespace != physical_namespace
                or seal.provider_write_fence != provider_write_fence
            ):
                return BuildValidationResult(
                    BuildValidationOutcome.REJECTED,
                    "SEALED_GENERATION_IDENTITY_CONFLICT",
                )
            readback = sealed_readback
        elif (
            write.outcome
            not in {
                ProviderWriteOutcome.WRITTEN,
                ProviderWriteOutcome.EXACT_REPLAY,
            }
            or write.checkpoint is None
        ):
            return BuildValidationResult(
                BuildValidationOutcome.REJECTED,
                write.safe_reason,
            )
        else:
            sealed = self._provider.seal(
                generation_id=generation_id,
                expected_checkpoint=write.checkpoint,
                expected_fence=provider_write_fence,
            )
            if sealed is None:
                return BuildValidationResult(
                    BuildValidationOutcome.REJECTED,
                    "PROVIDER_SEAL_CAS_MISMATCH",
                )
            seal = sealed
            provider_readback = self._provider.readback(generation_id)
            if provider_readback is None:
                return BuildValidationResult(
                    BuildValidationOutcome.REJECTED,
                    "SEALED_PROVIDER_READBACK_NOT_FOUND",
                )
            readback = provider_readback
        observed, observed_seal = readback
        actual = manifest_facts(observed)
        manifest = GenerationManifest(
            expected=expected,
            actual=actual,
            expected_absent_occurrence_ids=expected_absent_occurrence_ids,
        )
        decision = (
            ValidationDecision.PASS
            if manifest.integrity_matches and observed_seal == seal
            else ValidationDecision.FAIL
        )
        validation = ValidationRecord(
            validation_id=validation_id,
            generation_id=generation_id,
            build_snapshot_fingerprint=build_snapshot.fingerprint,
            expected_manifest_digest=expected.fingerprint,
            actual_manifest_digest=actual.fingerprint,
            physical_namespace=physical_namespace,
            provider_checkpoint=observed_seal.provider_checkpoint,
            provider_write_fence=observed_seal.provider_write_fence,
            validator_version=validator_version,
            decision=decision,
            observed_at=observed_at,
        )
        build = GenerationBuildRecord(
            generation_id=generation_id,
            build_snapshot=build_snapshot,
            evaluation_ruler=evaluation_ruler,
            expected_manifest_fingerprint=expected.fingerprint,
            physical_namespace=physical_namespace,
        )
        registered = self._committer.register_validating_candidate(
            build=build,
            manifest=manifest,
            seal=seal,
            validation=validation,
        )
        if registered.outcome is RegistrationOutcome.IDENTITY_CONFLICT:
            return BuildValidationResult(
                BuildValidationOutcome.IDENTITY_CONFLICT,
                registered.safe_reason,
                manifest,
                validation,
                seal,
            )
        return BuildValidationResult(
            BuildValidationOutcome.VALIDATING,
            "SEALED_GENERATION_READBACK_RECORDED_FOR_RELEASE_GATES",
            manifest,
            validation,
            seal,
        )
