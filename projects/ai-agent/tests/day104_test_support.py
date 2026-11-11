"""Deterministic fixtures for Day104 index lifecycle tests."""

from __future__ import annotations

from dataclasses import dataclass

from rag_index_lifecycle_committer import (
    GenerationBuildRecord,
    InMemoryIndexLifecycleStore,
    IndexLifecycleCommitter,
    ProviderSealRecord,
)
from rag_index_lifecycle_contracts import (
    BuildSnapshot,
    EvaluationDecision,
    EvaluationEvidence,
    EvaluationRuler,
    GenerationManifest,
    ImmutableBinding,
    ManifestFacts,
    ValidationDecision,
    ValidationRecord,
)


def classroom_evaluation_ruler() -> EvaluationRuler:
    return EvaluationRuler(
        dataset_fingerprint="sha256:dataset-L1",
        evaluator_fingerprint="sha256:evaluator-v1",
        policy_fingerprint="sha256:release-policy-v1",
    )


def classroom_build_snapshot(
    *,
    snapshot_id: str = "BS1",
    source: str = "S1",
    authorization: str = "P1",
    embedding: str = "E1",
    index_schema: str = "IS1",
    watermark: str = "W1",
    deletion: str = "D1",
) -> BuildSnapshot:
    return BuildSnapshot(
        build_snapshot_id=snapshot_id,
        scope_id="refund-rag",
        source_snapshot=ImmutableBinding(source, f"sha256:{source}"),
        authorization_snapshot=ImmutableBinding(
            authorization,
            f"sha256:{authorization}",
        ),
        embedding_contract=ImmutableBinding(
            embedding,
            f"sha256:{embedding}",
        ),
        index_schema=ImmutableBinding(
            index_schema,
            f"sha256:{index_schema}",
        ),
        source_watermark=watermark,
        deletion_snapshot=ImmutableBinding(
            deletion,
            f"sha256:{deletion}",
        ),
    )


def matching_manifest(
    *,
    occurrence_ids: tuple[str, ...] = ("A@v1", "C@v1"),
    revision: str = "v1",
) -> GenerationManifest:
    facts = ManifestFacts(
        occurrence_ids=occurrence_ids,
        content_digest=f"sha256:content-{revision}",
        metadata_digest=f"sha256:metadata-{revision}",
        provenance_digest=f"sha256:provenance-{revision}",
    )
    return GenerationManifest(
        expected=facts,
        actual=facts,
        expected_absent_occurrence_ids=("B@v1",),
    )


@dataclass(frozen=True)
class CandidateEvidence:
    build: GenerationBuildRecord
    manifest: GenerationManifest
    seal: ProviderSealRecord
    validation: ValidationRecord
    evaluation: EvaluationEvidence


@dataclass(frozen=True)
class Day104Fixture:
    store: InMemoryIndexLifecycleStore
    committer: IndexLifecycleCommitter
    snapshot: BuildSnapshot
    evaluation_ruler: EvaluationRuler


def build_day104_fixture(
    snapshot: BuildSnapshot | None = None,
    evaluation_ruler: EvaluationRuler | None = None,
) -> Day104Fixture:
    frozen = snapshot or classroom_build_snapshot()
    ruler = evaluation_ruler or classroom_evaluation_ruler()
    store = InMemoryIndexLifecycleStore()
    store.set_current_build_snapshot(frozen)
    return Day104Fixture(
        store,
        IndexLifecycleCommitter(store),
        frozen,
        ruler,
    )


def candidate_evidence(
    fixture: Day104Fixture,
    generation_id: str,
    *,
    snapshot: BuildSnapshot | None = None,
    evaluation_decision: EvaluationDecision = EvaluationDecision.PASS,
    evidence_id: str | None = None,
    provider_checkpoint: str | None = None,
    validation_checkpoint: str | None = None,
    validation_decision: ValidationDecision = ValidationDecision.PASS,
    manifest: GenerationManifest | None = None,
    evaluation_ruler: EvaluationRuler | None = None,
    observed_evaluation_ruler: EvaluationRuler | None = None,
) -> CandidateEvidence:
    bound_snapshot = snapshot or fixture.snapshot
    bound_manifest = manifest or matching_manifest()
    frozen_ruler = evaluation_ruler or fixture.evaluation_ruler
    observed_ruler = observed_evaluation_ruler or frozen_ruler
    namespace = f"refund-rag/{generation_id}"
    checkpoint = provider_checkpoint or f"checkpoint:{generation_id}"
    build = GenerationBuildRecord(
        generation_id=generation_id,
        build_snapshot=bound_snapshot,
        evaluation_ruler=frozen_ruler,
        expected_manifest_fingerprint=(bound_manifest.expected.fingerprint),
        physical_namespace=namespace,
    )
    seal = ProviderSealRecord(
        generation_id=generation_id,
        physical_namespace=namespace,
        provider_checkpoint=checkpoint,
        provider_write_fence=7,
    )
    validation = ValidationRecord(
        validation_id=f"validation:{generation_id}",
        generation_id=generation_id,
        build_snapshot_fingerprint=bound_snapshot.fingerprint,
        expected_manifest_digest=bound_manifest.expected.fingerprint,
        actual_manifest_digest=bound_manifest.actual.fingerprint,
        physical_namespace=namespace,
        provider_checkpoint=validation_checkpoint or checkpoint,
        provider_write_fence=7,
        validator_version="day104-validator-v1",
        decision=validation_decision,
        observed_at="2026-11-11T00:00:00Z",
    )
    evaluation = EvaluationEvidence(
        evidence_id=evidence_id or f"evaluation:{generation_id}",
        generation_id=generation_id,
        build_snapshot_fingerprint=bound_snapshot.fingerprint,
        manifest_digest=bound_manifest.digest,
        dataset_fingerprint=observed_ruler.dataset_fingerprint,
        evaluator_fingerprint=observed_ruler.evaluator_fingerprint,
        policy_fingerprint=observed_ruler.policy_fingerprint,
        evaluation_report_checksum=(
            f"sha256:report-{generation_id}-{evaluation_decision.value}"
        ),
        evidence_level="EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE",
        decision=evaluation_decision,
        observed_at="2026-11-11T00:01:00Z",
    )
    return CandidateEvidence(
        build,
        bound_manifest,
        seal,
        validation,
        evaluation,
    )


def register_candidate(
    fixture: Day104Fixture,
    candidate: CandidateEvidence,
) -> None:
    result = fixture.committer.register_validating_candidate(
        build=candidate.build,
        manifest=candidate.manifest,
        seal=candidate.seal,
        validation=candidate.validation,
    )
    if result.outcome.value not in {"REGISTERED", "ALREADY_REGISTERED"}:
        raise AssertionError(result)
    evaluation = fixture.committer.record_evaluation(candidate.evaluation)
    if evaluation.value not in {"REGISTERED", "ALREADY_REGISTERED"}:
        raise AssertionError(evaluation)


def make_ready(
    fixture: Day104Fixture,
    generation_id: str,
    *,
    snapshot: BuildSnapshot | None = None,
    manifest: GenerationManifest | None = None,
) -> CandidateEvidence:
    candidate = candidate_evidence(
        fixture,
        generation_id,
        snapshot=snapshot,
        manifest=manifest,
    )
    register_candidate(fixture, candidate)
    result = fixture.committer.mark_ready(
        generation_id=generation_id,
        expected_state_version=1,
        validation_record_id=candidate.validation.validation_id,
        evaluation_evidence_id=candidate.evaluation.evidence_id,
    )
    if result.outcome.value != "READY":
        raise AssertionError(result)
    return candidate
