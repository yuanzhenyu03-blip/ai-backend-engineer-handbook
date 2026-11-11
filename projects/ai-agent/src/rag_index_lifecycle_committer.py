"""Deterministic Day104 index-generation lifecycle control plane.

This module models database transactions with one process-local lock.  It is
useful evidence for state-machine, CAS, fencing and idempotency mechanics; it
is deliberately not evidence of PostgreSQL isolation or distributed
durability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading

from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_contracts import (
    ActivationDecision,
    ActivationLease,
    ActivationRecord,
    ActivePointer,
    BuildSnapshot,
    EvaluationDecision,
    EvaluationEvidence,
    EvaluationRuler,
    GenerationArtifact,
    GenerationLifecycle,
    GenerationManifest,
    GenerationState,
    MessageState,
    OutboxEvent,
    ReadView,
    ValidationDecision,
    ValidationRecord,
)


class RegistrationOutcome(str, Enum):
    REGISTERED = "REGISTERED"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class ReadyOutcome(str, Enum):
    READY = "READY"
    ALREADY_READY = "ALREADY_READY"
    NOT_FOUND = "NOT_FOUND"
    STALE_STATE = "STALE_STATE"
    STALE_BUILD_SNAPSHOT = "STALE_BUILD_SNAPSHOT"
    STALE_READBACK = "STALE_READBACK"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    EVIDENCE_INCONCLUSIVE = "EVIDENCE_INCONCLUSIVE"
    EVIDENCE_BINDING_CONFLICT = "EVIDENCE_BINDING_CONFLICT"


class ActivationOutcome(str, Enum):
    ACTIVATED = "ACTIVATED"
    ALREADY_ACTIVATED = "ALREADY_ACTIVATED"
    NOT_FOUND = "NOT_FOUND"
    NOT_READY = "NOT_READY"
    STALE_POINTER = "STALE_POINTER"
    STALE_FENCE = "STALE_FENCE"
    STALE_BUILD_SNAPSHOT = "STALE_BUILD_SNAPSHOT"
    UNIQUE_SUCCESSOR_CONFLICT = "UNIQUE_SUCCESSOR_CONFLICT"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class AliasProjectionOutcome(str, Enum):
    APPLIED = "APPLIED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    STALE_EVENT = "STALE_EVENT"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class GenerationBuildRecord:
    """Immutable build inputs retained before release evidence exists."""

    generation_id: str
    build_snapshot: BuildSnapshot
    evaluation_ruler: EvaluationRuler
    expected_manifest_fingerprint: str
    physical_namespace: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.generation_id,
                self.expected_manifest_fingerprint,
                self.physical_namespace,
            )
        ):
            raise ValueError("complete generation build identity is required")

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            (
                self.generation_id,
                self.build_snapshot.fingerprint,
                self.evaluation_ruler.fingerprint,
                self.expected_manifest_fingerprint,
                self.physical_namespace,
            )
        )


@dataclass(frozen=True)
class ProviderSealRecord:
    generation_id: str
    physical_namespace: str
    provider_checkpoint: str
    provider_write_fence: int

    def __post_init__(self) -> None:
        if not all(
            (
                self.generation_id,
                self.physical_namespace,
                self.provider_checkpoint,
            )
        ):
            raise ValueError("complete Provider seal identity is required")
        if self.provider_write_fence <= 0:
            raise ValueError("Provider seal fence must be positive")


@dataclass(frozen=True)
class LifecycleTransitionRecord:
    generation_id: str
    from_state: GenerationState
    to_state: GenerationState
    from_state_version: int
    to_state_version: int
    reason: str


@dataclass(frozen=True)
class RegistrationResult:
    outcome: RegistrationOutcome
    safe_reason: str
    lifecycle: GenerationLifecycle | None = None


@dataclass(frozen=True)
class ReadyResult:
    outcome: ReadyOutcome
    safe_reason: str
    lifecycle: GenerationLifecycle | None = None
    artifact: GenerationArtifact | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class ActivationResult:
    outcome: ActivationOutcome
    safe_reason: str
    pointer: ActivePointer | None = None
    activation: ActivationRecord | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class AliasProjectionResult:
    outcome: AliasProjectionOutcome
    safe_reason: str
    generation_id: str | None = None


class InMemoryIndexLifecycleStore:
    """One-process teaching store; never distributed-durability evidence."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._current_snapshots: dict[str, BuildSnapshot] = {}
        self._builds: dict[str, GenerationBuildRecord] = {}
        self._manifests: dict[str, GenerationManifest] = {}
        self._seals: dict[str, ProviderSealRecord] = {}
        self._artifacts: dict[str, GenerationArtifact] = {}
        self._lifecycles: dict[str, GenerationLifecycle] = {}
        self._validations: dict[str, ValidationRecord] = {}
        self._evaluations: dict[str, EvaluationEvidence] = {}
        self._pointers: dict[str, ActivePointer] = {}
        self._activation_records: dict[str, ActivationRecord] = {}
        self._activation_from: dict[tuple[str, int], str] = {}
        self._activation_to: dict[tuple[str, int], str] = {}
        self._activation_leases: dict[str, ActivationLease] = {}
        self._activation_fence_counters: dict[str, int] = {}
        self._transitions: list[LifecycleTransitionRecord] = []
        self._outbox: dict[str, OutboxEvent] = {}
        self._provider_aliases: dict[str, str] = {}
        self._read_views: dict[str, ReadView] = {}
        self._reader_reconciliations: list[tuple[str, int, int, str]] = []

    def set_current_build_snapshot(self, snapshot: BuildSnapshot) -> None:
        with self._lock:
            self._current_snapshots[snapshot.scope_id] = snapshot

    def read_current_build_snapshot(self, scope_id: str) -> BuildSnapshot | None:
        with self._lock:
            return self._current_snapshots.get(scope_id)

    def read_build(self, generation_id: str) -> GenerationBuildRecord | None:
        with self._lock:
            return self._builds.get(generation_id)

    def read_manifest(self, generation_id: str) -> GenerationManifest | None:
        with self._lock:
            return self._manifests.get(generation_id)

    def read_artifact(self, generation_id: str) -> GenerationArtifact | None:
        with self._lock:
            return self._artifacts.get(generation_id)

    def read_lifecycle(self, generation_id: str) -> GenerationLifecycle | None:
        with self._lock:
            return self._lifecycles.get(generation_id)

    def read_pointer(self, pointer_name: str) -> ActivePointer | None:
        with self._lock:
            return self._pointers.get(pointer_name)

    def read_activation(self, activation_id: str) -> ActivationRecord | None:
        with self._lock:
            return self._activation_records.get(activation_id)

    def read_activation_lease(self, pointer_name: str) -> ActivationLease | None:
        with self._lock:
            return self._activation_leases.get(pointer_name)

    def issue_activation_lease(
        self,
        *,
        pointer_name: str,
        committer_id: str,
        issued_at: str,
    ) -> ActivationLease:
        """Issue the first activation token for an existing pointer."""

        with self._lock:
            if pointer_name not in self._pointers:
                raise ValueError("activation pointer does not exist")
            if pointer_name in self._activation_leases:
                raise ValueError(
                    "activation lease already exists; rotate it explicitly"
                )
            return self._replace_activation_lease(
                pointer_name=pointer_name,
                committer_id=committer_id,
                issued_at=issued_at,
            )

    def rotate_activation_lease(
        self,
        *,
        pointer_name: str,
        expected_fencing_token: int,
        committer_id: str,
        issued_at: str,
    ) -> ActivationLease:
        """CAS-rotate authority so every previously issued token is stale."""

        with self._lock:
            current = self._activation_leases.get(pointer_name)
            if current is None:
                raise ValueError("activation lease does not exist")
            if current.fencing_token != expected_fencing_token:
                raise ValueError("activation lease fencing token changed")
            return self._replace_activation_lease(
                pointer_name=pointer_name,
                committer_id=committer_id,
                issued_at=issued_at,
            )

    def _replace_activation_lease(
        self,
        *,
        pointer_name: str,
        committer_id: str,
        issued_at: str,
    ) -> ActivationLease:
        next_token = self._activation_fence_counters.get(pointer_name, 0) + 1
        lease = ActivationLease(
            pointer_name=pointer_name,
            committer_id=committer_id,
            fencing_token=next_token,
            issued_at=issued_at,
        )
        self._activation_fence_counters[pointer_name] = next_token
        self._activation_leases[pointer_name] = lease
        return lease

    def activation_records(self) -> tuple[ActivationRecord, ...]:
        with self._lock:
            return tuple(self._activation_records.values())

    def lifecycle_transitions(self) -> tuple[LifecycleTransitionRecord, ...]:
        with self._lock:
            return tuple(self._transitions)

    def outbox_events(self) -> tuple[OutboxEvent, ...]:
        with self._lock:
            return tuple(self._outbox.values())

    def read_outbox(self, event_id: str) -> OutboxEvent | None:
        with self._lock:
            return self._outbox.get(event_id)

    def read_provider_alias(self, pointer_name: str) -> str | None:
        with self._lock:
            return self._provider_aliases.get(pointer_name)

    def read_read_view(self, view_id: str) -> ReadView | None:
        with self._lock:
            return self._read_views.get(view_id)

    def read_views(self) -> tuple[ReadView, ...]:
        with self._lock:
            return tuple(self._read_views.values())

    def reader_reconciliations(self) -> tuple[tuple[str, int, int, str], ...]:
        with self._lock:
            return tuple(self._reader_reconciliations)

    def seed_active_pointer(
        self,
        *,
        pointer: ActivePointer,
        provider_alias_generation_id: str | None = None,
    ) -> None:
        """Seed an already-proven baseline for deterministic migration tests."""

        with self._lock:
            lifecycle = self._lifecycles.get(pointer.generation_id)
            if lifecycle is None or lifecycle.state is not GenerationState.READY:
                raise ValueError("only a READY generation may seed an active pointer")
            if pointer.pointer_name in self._pointers:
                raise ValueError("active pointer already exists")
            self._lifecycles[pointer.generation_id] = replace(
                lifecycle,
                state=GenerationState.ACTIVE,
                state_version=lifecycle.state_version + 1,
                transition_fence=lifecycle.transition_fence + 1,
            )
            self._pointers[pointer.pointer_name] = pointer
            self._activation_fence_counters[pointer.pointer_name] = 0
            if provider_alias_generation_id is not None:
                self._provider_aliases[
                    pointer.pointer_name
                ] = provider_alias_generation_id


class IndexLifecycleCommitter:
    def __init__(self, store: InMemoryIndexLifecycleStore) -> None:
        self._store = store

    def register_validating_candidate(
        self,
        *,
        build: GenerationBuildRecord,
        manifest: GenerationManifest,
        seal: ProviderSealRecord,
        validation: ValidationRecord,
    ) -> RegistrationResult:
        store = self._store
        generation_id = build.generation_id
        with store._lock:
            bound_validation = store._validations.get(validation.validation_id)
            if bound_validation is not None and bound_validation != validation:
                return RegistrationResult(
                    RegistrationOutcome.IDENTITY_CONFLICT,
                    "VALIDATION_ID_ALREADY_BOUND_TO_OTHER_EVIDENCE",
                    store._lifecycles.get(generation_id),
                )
            existing = store._builds.get(generation_id)
            if existing is not None:
                exact = (
                    existing == build
                    and store._manifests[generation_id] == manifest
                    and store._seals[generation_id] == seal
                )
                if exact:
                    binding_error = self._candidate_binding_error(
                        build=build,
                        manifest=manifest,
                        seal=seal,
                        validation=validation,
                    )
                    if binding_error is not None:
                        return RegistrationResult(
                            RegistrationOutcome.IDENTITY_CONFLICT,
                            binding_error,
                            store._lifecycles[generation_id],
                        )
                    store._validations.setdefault(
                        validation.validation_id,
                        validation,
                    )
                    return RegistrationResult(
                        RegistrationOutcome.ALREADY_REGISTERED,
                        "CANDIDATE_REPLAY_CONVERGED_AND_EVIDENCE_RECORDED",
                        store._lifecycles[generation_id],
                    )
                return RegistrationResult(
                    RegistrationOutcome.IDENTITY_CONFLICT,
                    "GENERATION_IDENTITY_ALREADY_BOUND_TO_OTHER_CONTENT",
                    store._lifecycles[generation_id],
                )
            binding_error = self._candidate_binding_error(
                build=build,
                manifest=manifest,
                seal=seal,
                validation=validation,
            )
            if binding_error is not None:
                return RegistrationResult(
                    RegistrationOutcome.IDENTITY_CONFLICT,
                    binding_error,
                )
            lifecycle = GenerationLifecycle(
                generation_id=generation_id,
                state=GenerationState.VALIDATING,
                state_version=1,
                transition_fence=seal.provider_write_fence,
            )
            store._builds[generation_id] = build
            store._manifests[generation_id] = manifest
            store._seals[generation_id] = seal
            store._validations[validation.validation_id] = validation
            store._lifecycles[generation_id] = lifecycle
            store._transitions.append(
                LifecycleTransitionRecord(
                    generation_id,
                    GenerationState.BUILDING,
                    GenerationState.VALIDATING,
                    0,
                    1,
                    "PROVIDER_SEALED_AND_READBACK_RECORDED",
                )
            )
            return RegistrationResult(
                RegistrationOutcome.REGISTERED,
                "VALIDATING_CANDIDATE_RECORDED",
                lifecycle,
            )

    def record_evaluation(self, evidence: EvaluationEvidence) -> RegistrationOutcome:
        store = self._store
        with store._lock:
            existing = store._evaluations.get(evidence.evidence_id)
            if existing is not None:
                return (
                    RegistrationOutcome.ALREADY_REGISTERED
                    if existing == evidence
                    else RegistrationOutcome.IDENTITY_CONFLICT
                )
            build = store._builds.get(evidence.generation_id)
            manifest = store._manifests.get(evidence.generation_id)
            if (
                build is None
                or manifest is None
                or evidence.build_snapshot_fingerprint
                != build.build_snapshot.fingerprint
                or evidence.manifest_digest != manifest.digest
                or evidence.dataset_fingerprint
                != build.evaluation_ruler.dataset_fingerprint
                or evidence.evaluator_fingerprint
                != build.evaluation_ruler.evaluator_fingerprint
                or evidence.policy_fingerprint
                != build.evaluation_ruler.policy_fingerprint
            ):
                return RegistrationOutcome.IDENTITY_CONFLICT
            store._evaluations[evidence.evidence_id] = evidence
            return RegistrationOutcome.REGISTERED

    def mark_ready(
        self,
        *,
        generation_id: str,
        expected_state_version: int,
        validation_record_id: str,
        evaluation_evidence_id: str,
    ) -> ReadyResult:
        store = self._store
        with store._lock:
            lifecycle = store._lifecycles.get(generation_id)
            build = store._builds.get(generation_id)
            manifest = store._manifests.get(generation_id)
            seal = store._seals.get(generation_id)
            validation = store._validations.get(validation_record_id)
            evaluation = store._evaluations.get(evaluation_evidence_id)
            if lifecycle is None or build is None or manifest is None:
                return ReadyResult(ReadyOutcome.NOT_FOUND, "GENERATION_NOT_FOUND")
            if lifecycle.state is not GenerationState.READY and (
                lifecycle.state is not GenerationState.VALIDATING
                or lifecycle.state_version != expected_state_version
            ):
                return ReadyResult(
                    ReadyOutcome.STALE_STATE,
                    "GENERATION_STATE_OR_VERSION_CHANGED",
                    lifecycle,
                )
            current = store._current_snapshots.get(build.build_snapshot.scope_id)
            if current is None or current.fingerprint != (
                build.build_snapshot.fingerprint
            ):
                return ReadyResult(
                    ReadyOutcome.STALE_BUILD_SNAPSHOT,
                    "CURRENT_BUILD_INPUTS_CHANGED",
                    lifecycle,
                )
            if validation is None or evaluation is None or seal is None:
                return ReadyResult(
                    ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
                    "REQUIRED_RELEASE_EVIDENCE_NOT_FOUND",
                    lifecycle,
                )
            candidate_error = self._candidate_binding_error(
                build=build,
                manifest=manifest,
                seal=seal,
                validation=validation,
            )
            if candidate_error is not None:
                return ReadyResult(
                    ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
                    candidate_error,
                    lifecycle,
                )
            evidence_error = self._ready_evidence_error(
                build=build,
                manifest=manifest,
                seal=seal,
                validation=validation,
                evaluation=evaluation,
            )
            artifact = GenerationArtifact(
                generation_id=generation_id,
                scope_id=build.build_snapshot.scope_id,
                build_snapshot_fingerprint=build.build_snapshot.fingerprint,
                manifest_digest=manifest.digest,
                evaluation_ruler_fingerprint=(build.evaluation_ruler.fingerprint),
                validation_record_digest=validation.digest,
                evaluation_evidence_digest=evaluation.digest,
                evaluation_report_digest=(evaluation.evaluation_report_checksum),
                physical_namespace=build.physical_namespace,
            )
            if lifecycle.state is GenerationState.READY:
                if evidence_error is not None:
                    outcome, reason = evidence_error
                    return ReadyResult(outcome, reason, lifecycle)
                stored_artifact = store._artifacts.get(generation_id)
                if stored_artifact != artifact:
                    return ReadyResult(
                        ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
                        "READY_ARTIFACT_BINDINGS_CHANGED",
                        lifecycle,
                        stored_artifact,
                    )
                return ReadyResult(
                    ReadyOutcome.ALREADY_READY,
                    "EXACT_READY_REPLAY_CONVERGED",
                    lifecycle,
                    stored_artifact,
                )
            if evidence_error is not None:
                outcome, reason = evidence_error
                if outcome in {
                    ReadyOutcome.EVALUATION_FAILED,
                    ReadyOutcome.INTEGRITY_FAILED,
                }:
                    failed = self._transition(
                        lifecycle,
                        GenerationState.FAILED,
                        "OBSERVED_RELEASE_GATE_FAILURE",
                    )
                    store._lifecycles[generation_id] = failed
                    return ReadyResult(
                        outcome,
                        reason,
                        failed,
                        durable_transition=True,
                    )
                return ReadyResult(outcome, reason, lifecycle)
            ready = self._transition(
                lifecycle,
                GenerationState.READY,
                "ALL_INTEGRITY_QUALITY_AND_FRESHNESS_GATES_PASSED",
            )
            store._artifacts[generation_id] = artifact
            store._lifecycles[generation_id] = ready
            return ReadyResult(
                ReadyOutcome.READY,
                "GENERATION_READY",
                ready,
                artifact,
                durable_transition=True,
            )

    def activate(
        self,
        *,
        activation_id: str,
        pointer_name: str,
        target_generation_id: str,
        expected_generation_id: str,
        expected_revision: int,
        committer_id: str,
        committer_fence: int,
        committed_at: str,
        previous_retire_after: str | None = None,
    ) -> ActivationResult:
        store = self._store
        with store._lock:
            prior = store._activation_records.get(activation_id)
            if prior is not None:
                if (
                    prior.pointer_name == pointer_name
                    and prior.target_generation_id == target_generation_id
                    and prior.expected_generation_id == expected_generation_id
                    and prior.from_revision == expected_revision
                    and prior.committer_id == committer_id
                    and prior.committer_fence == committer_fence
                    and prior.committed_at == committed_at
                    and prior.previous_retire_after == previous_retire_after
                ):
                    return ActivationResult(
                        ActivationOutcome.ALREADY_ACTIVATED,
                        "EXACT_ACTIVATION_REPLAY_CONVERGED",
                        store._pointers.get(pointer_name),
                        prior,
                    )
                return ActivationResult(
                    ActivationOutcome.IDENTITY_CONFLICT,
                    "ACTIVATION_ID_ALREADY_BOUND_TO_OTHER_INPUT",
                    store._pointers.get(pointer_name),
                    prior,
                )
            pointer = store._pointers.get(pointer_name)
            target = store._lifecycles.get(target_generation_id)
            artifact = store._artifacts.get(target_generation_id)
            build = store._builds.get(target_generation_id)
            if pointer is None or target is None or artifact is None or build is None:
                return ActivationResult(
                    ActivationOutcome.NOT_FOUND,
                    "POINTER_OR_TARGET_NOT_FOUND",
                    pointer,
                )
            current_lease = store._activation_leases.get(pointer_name)
            if (
                current_lease is None
                or current_lease.committer_id != committer_id
                or current_lease.fencing_token != committer_fence
            ):
                return ActivationResult(
                    ActivationOutcome.STALE_FENCE,
                    "ACTIVATION_LEASE_OR_FENCE_NOT_CURRENT",
                    pointer,
                )
            if (
                pointer.generation_id != expected_generation_id
                or pointer.revision != expected_revision
            ):
                return ActivationResult(
                    ActivationOutcome.STALE_POINTER,
                    "ACTIVE_POINTER_CAS_MISMATCH",
                    pointer,
                )
            if target.state not in {
                GenerationState.READY,
                GenerationState.DRAINING,
            }:
                return ActivationResult(
                    ActivationOutcome.NOT_READY,
                    "TARGET_NOT_READY_OR_ROLLBACK_ELIGIBLE",
                    pointer,
                )
            current_snapshot = store._current_snapshots.get(artifact.scope_id)
            if (
                current_snapshot is None
                or current_snapshot.fingerprint != artifact.build_snapshot_fingerprint
            ):
                return ActivationResult(
                    ActivationOutcome.STALE_BUILD_SNAPSHOT,
                    "TARGET_BUILD_INPUTS_ARE_NOT_CURRENT",
                    pointer,
                )
            from_key = (pointer_name, expected_revision)
            to_key = (pointer_name, expected_revision + 1)
            if from_key in store._activation_from or to_key in store._activation_to:
                return ActivationResult(
                    ActivationOutcome.UNIQUE_SUCCESSOR_CONFLICT,
                    "POINTER_REVISION_ALREADY_HAS_A_SUCCESSOR",
                    pointer,
                )
            previous = store._lifecycles.get(expected_generation_id)
            if previous is None or previous.state is not GenerationState.ACTIVE:
                return ActivationResult(
                    ActivationOutcome.STALE_POINTER,
                    "POINTER_DOES_NOT_BIND_AN_ACTIVE_GENERATION",
                    pointer,
                )
            next_pointer = ActivePointer(
                pointer_name,
                target_generation_id,
                expected_revision + 1,
            )
            activation = ActivationRecord(
                activation_id=activation_id,
                pointer_name=pointer_name,
                expected_generation_id=expected_generation_id,
                target_generation_id=target_generation_id,
                from_revision=expected_revision,
                to_revision=expected_revision + 1,
                build_snapshot_fingerprint=artifact.build_snapshot_fingerprint,
                manifest_digest=artifact.manifest_digest,
                evaluation_report_checksum=artifact.evaluation_report_digest,
                committer_id=committer_id,
                committer_fence=committer_fence,
                decision=ActivationDecision.APPLIED,
                committed_at=committed_at,
                previous_retire_after=previous_retire_after,
            )
            activated = self._transition(
                target,
                GenerationState.ACTIVE,
                "POINTER_CAS_SELECTED_GENERATION",
            )
            draining = self._transition(
                previous,
                GenerationState.DRAINING,
                "POINTER_CAS_DRAINED_PREVIOUS_GENERATION",
            )
            draining = replace(
                draining,
                retire_after=previous_retire_after,
            )
            event_id = stable_hash(
                (
                    "INDEX_POINTER_CHANGED",
                    pointer_name,
                    next_pointer.revision,
                    target_generation_id,
                    activation.digest,
                )
            )
            event = OutboxEvent(
                event_id=event_id,
                event_type="INDEX_POINTER_CHANGED",
                aggregate_id=pointer_name,
                aggregate_revision=next_pointer.revision,
                payload_digest=stable_hash(
                    (
                        target_generation_id,
                        next_pointer.revision,
                        activation.digest,
                    )
                ),
            )
            store._lifecycles[target_generation_id] = activated
            store._lifecycles[expected_generation_id] = draining
            store._pointers[pointer_name] = next_pointer
            store._activation_records[activation_id] = activation
            store._activation_from[from_key] = activation_id
            store._activation_to[to_key] = activation_id
            store._outbox[event_id] = event
            return ActivationResult(
                ActivationOutcome.ACTIVATED,
                "POINTER_STATES_ACTIVATION_RECORD_AND_OUTBOX_COMMITTED",
                next_pointer,
                activation,
                durable_transition=True,
            )

    def project_provider_alias(
        self,
        event_id: str,
        *,
        acknowledge: bool = True,
    ) -> AliasProjectionResult:
        store = self._store
        with store._lock:
            event = store._outbox.get(event_id)
            if event is None:
                return AliasProjectionResult(
                    AliasProjectionOutcome.NOT_FOUND,
                    "OUTBOX_EVENT_NOT_FOUND",
                )
            pointer = store._pointers.get(event.aggregate_id)
            if pointer is None or event.event_type != "INDEX_POINTER_CHANGED":
                return AliasProjectionResult(
                    AliasProjectionOutcome.STALE_EVENT,
                    "OUTBOX_EVENT_CANNOT_RESOLVE_CURRENT_POINTER_TRUTH",
                )
            stale_wakeup = pointer.revision != event.aggregate_revision
            previous_alias = store._provider_aliases.get(pointer.pointer_name)
            store._provider_aliases[pointer.pointer_name] = pointer.generation_id
            if acknowledge:
                store._outbox[event_id] = replace(
                    event,
                    state=MessageState.DISPATCHED,
                )
            return AliasProjectionResult(
                (
                    AliasProjectionOutcome.ALREADY_APPLIED
                    if previous_alias == pointer.generation_id
                    else AliasProjectionOutcome.APPLIED
                ),
                (
                    "STALE_EVENT_RECONCILED_TO_CURRENT_DATABASE_POINTER"
                    if stale_wakeup
                    else "PROVIDER_ALIAS_MATCHED_CURRENT_DATABASE_POINTER"
                ),
                pointer.generation_id,
            )

    @staticmethod
    def _candidate_binding_error(
        *,
        build: GenerationBuildRecord,
        manifest: GenerationManifest,
        seal: ProviderSealRecord,
        validation: ValidationRecord,
    ) -> str | None:
        expected = manifest.expected.fingerprint
        actual = manifest.actual.fingerprint
        if build.expected_manifest_fingerprint != expected:
            return "BUILD_EXPECTED_MANIFEST_BINDING_MISMATCH"
        if (
            seal.generation_id != build.generation_id
            or seal.physical_namespace != build.physical_namespace
        ):
            return "PROVIDER_SEAL_GENERATION_BINDING_MISMATCH"
        if (
            validation.generation_id != build.generation_id
            or validation.build_snapshot_fingerprint != build.build_snapshot.fingerprint
            or validation.expected_manifest_digest != expected
            or validation.actual_manifest_digest != actual
            or validation.physical_namespace != build.physical_namespace
        ):
            return "VALIDATION_RECORD_BINDING_MISMATCH"
        return None

    @staticmethod
    def _ready_evidence_error(
        *,
        build: GenerationBuildRecord,
        manifest: GenerationManifest,
        seal: ProviderSealRecord,
        validation: ValidationRecord,
        evaluation: EvaluationEvidence,
    ) -> tuple[ReadyOutcome, str] | None:
        if validation.decision is ValidationDecision.STALE:
            return ReadyOutcome.STALE_READBACK, "VALIDATION_READBACK_IS_STALE"
        if validation.decision is ValidationDecision.FAIL:
            return ReadyOutcome.INTEGRITY_FAILED, "VALIDATION_FAILED"
        if not manifest.integrity_matches:
            return ReadyOutcome.INTEGRITY_FAILED, "MANIFEST_INTEGRITY_MISMATCH"
        if (
            validation.generation_id != build.generation_id
            or validation.build_snapshot_fingerprint != build.build_snapshot.fingerprint
            or validation.expected_manifest_digest != manifest.expected.fingerprint
            or validation.actual_manifest_digest != manifest.actual.fingerprint
        ):
            return (
                ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
                "VALIDATION_BINDINGS_DO_NOT_MATCH_CANDIDATE",
            )
        if (
            validation.physical_namespace != seal.physical_namespace
            or validation.provider_checkpoint != seal.provider_checkpoint
            or validation.provider_write_fence != seal.provider_write_fence
        ):
            return ReadyOutcome.STALE_READBACK, "PROVIDER_SEAL_CHANGED"
        if (
            evaluation.generation_id != build.generation_id
            or evaluation.build_snapshot_fingerprint != build.build_snapshot.fingerprint
            or evaluation.manifest_digest != manifest.digest
            or evaluation.dataset_fingerprint
            != build.evaluation_ruler.dataset_fingerprint
            or evaluation.evaluator_fingerprint
            != build.evaluation_ruler.evaluator_fingerprint
            or evaluation.policy_fingerprint
            != build.evaluation_ruler.policy_fingerprint
        ):
            return (
                ReadyOutcome.EVIDENCE_BINDING_CONFLICT,
                "EVALUATION_BINDINGS_DO_NOT_MATCH_CANDIDATE",
            )
        if evaluation.decision is EvaluationDecision.FAIL:
            return ReadyOutcome.EVALUATION_FAILED, "QUALITY_GATES_FAILED"
        if evaluation.decision is EvaluationDecision.INCONCLUSIVE:
            return (
                ReadyOutcome.EVIDENCE_INCONCLUSIVE,
                "QUALITY_EVIDENCE_INCONCLUSIVE",
            )
        return None

    def _transition(
        self,
        current: GenerationLifecycle,
        target: GenerationState,
        reason: str,
    ) -> GenerationLifecycle:
        next_lifecycle = replace(
            current,
            state=target,
            state_version=current.state_version + 1,
            transition_fence=current.transition_fence + 1,
        )
        self._store._transitions.append(
            LifecycleTransitionRecord(
                current.generation_id,
                current.state,
                target,
                current.state_version,
                next_lifecycle.state_version,
                reason,
            )
        )
        return next_lifecycle
