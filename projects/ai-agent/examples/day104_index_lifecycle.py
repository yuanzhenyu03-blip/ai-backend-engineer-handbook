"""Executable Day104 immutable-generation migration fixture."""

from __future__ import annotations

import json

from rag_chunking_contracts import stable_hash
from rag_index_deletion_ledger import (
    DeletionLedgerCommitter,
    InMemoryDeletionLedger,
)
from rag_index_lifecycle_committer import (
    IndexLifecycleCommitter,
    InMemoryIndexLifecycleStore,
    ReadyOutcome,
)
from rag_index_lifecycle_contracts import (
    ActivePointer,
    BuildSnapshot,
    DeletionEvidence,
    DeletionEvidenceScope,
    DeletionIntent,
    DeletionState,
    EvaluationDecision,
    EvaluationEvidence,
    EvaluationRuler,
    EvidenceStatus,
    ImmutableBinding,
)
from rag_index_lifecycle_orchestrator import (
    DeterministicSealedIndexProvider,
    IndexLifecycleOrchestrator,
    IndexedOccurrence,
)
from rag_index_read_views import IndexReadViewManager


SCOPE = "refund-rag"
POINTER = "refund-rag-active"


def _binding(identity: str) -> ImmutableBinding:
    return ImmutableBinding(identity, stable_hash(("DAY104_BINDING", identity)))


def _occurrence(occurrence_id: str, value: str) -> IndexedOccurrence:
    return IndexedOccurrence(
        occurrence_id=occurrence_id,
        content_digest=stable_hash(("CONTENT", value)),
        metadata_digest=stable_hash(("METADATA", occurrence_id, "current")),
        provenance_digest=stable_hash(("PROVENANCE", occurrence_id)),
    )


def _evaluation(
    *,
    evidence_id: str,
    generation_id: str,
    snapshot: BuildSnapshot,
    manifest_digest: str,
    ruler: EvaluationRuler,
) -> EvaluationEvidence:
    return EvaluationEvidence(
        evidence_id=evidence_id,
        generation_id=generation_id,
        build_snapshot_fingerprint=snapshot.fingerprint,
        manifest_digest=manifest_digest,
        dataset_fingerprint=ruler.dataset_fingerprint,
        evaluator_fingerprint=ruler.evaluator_fingerprint,
        policy_fingerprint=ruler.policy_fingerprint,
        evaluation_report_checksum=stable_hash(
            (
                "DAY104_EVALUATION_REPORT",
                generation_id,
                manifest_digest,
            )
        ),
        evidence_level="EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE",
        decision=EvaluationDecision.PASS,
        observed_at="2026-11-11T01:03:00+08:00",
    )


def run_example() -> dict[str, object]:
    deletion_store = InMemoryDeletionLedger()
    deletion = DeletionLedgerCommitter(deletion_store)
    delete_result = deletion.accept(
        DeletionIntent(
            deletion_id="delete-B-v1",
            operation_id="op-delete-B-v1",
            idempotency_key="idem-delete-B-v1",
            scope_id=SCOPE,
            occurrence_id="B@v1",
            source_version="B@v1",
            intent_digest=stable_hash(("DELETE", SCOPE, "B@v1")),
            verification_policy_id="day104-delete-policy-v1",
            required_evidence_scopes=(
                DeletionEvidenceScope.LOGICAL_RELEASE,
                DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
            ),
            state=DeletionState.ACCEPTED,
            accepted_at="2026-11-11T01:00:00+08:00",
        )
    )
    assert delete_result.snapshot is not None
    deletion_snapshot = delete_result.snapshot

    snapshot = BuildSnapshot(
        build_snapshot_id="BS1",
        scope_id=SCOPE,
        source_snapshot=_binding("S1"),
        authorization_snapshot=_binding("P1"),
        embedding_contract=_binding("E1"),
        index_schema=_binding("IS1"),
        source_watermark="W1",
        deletion_snapshot=ImmutableBinding(
            deletion_snapshot.deletion_snapshot_id,
            deletion_snapshot.fingerprint,
        ),
    )
    ruler = EvaluationRuler(
        dataset_fingerprint=stable_hash("day104-refund-L1"),
        evaluator_fingerprint=stable_hash("day103-evaluator-v1"),
        policy_fingerprint=stable_hash("day103-release-policy-v1"),
    )
    occurrences = (
        _occurrence("A@v1", "14-day refund window"),
        _occurrence("C@v1", "online customer service"),
    )

    store = InMemoryIndexLifecycleStore()
    store.set_current_build_snapshot(snapshot)
    committer = IndexLifecycleCommitter(store)
    provider = DeterministicSealedIndexProvider()
    orchestrator = IndexLifecycleOrchestrator(
        provider=provider,
        committer=committer,
    )

    ready_results = {}
    for generation_id, fence in (("G1", 1), ("G2", 2)):
        validation = orchestrator.build_and_validate(
            generation_id=generation_id,
            build_snapshot=snapshot,
            evaluation_ruler=ruler,
            expected_occurrences=occurrences,
            expected_absent_occurrence_ids=("B@v1",),
            physical_namespace=f"refund/{generation_id}",
            provider_write_fence=fence,
            validation_id=f"validation-{generation_id}",
            validator_version="day104-validator-v1",
            observed_at="2026-11-11T01:02:00+08:00",
        )
        assert validation.manifest is not None
        evaluation = _evaluation(
            evidence_id=f"evaluation-{generation_id}",
            generation_id=generation_id,
            snapshot=snapshot,
            manifest_digest=validation.manifest.digest,
            ruler=ruler,
        )
        committer.record_evaluation(evaluation)
        ready = committer.mark_ready(
            generation_id=generation_id,
            expected_state_version=1,
            validation_record_id=f"validation-{generation_id}",
            evaluation_evidence_id=f"evaluation-{generation_id}",
        )
        assert ready.outcome is ReadyOutcome.READY
        ready_results[generation_id] = ready

    store.seed_active_pointer(
        pointer=ActivePointer(POINTER, "G1", 7),
        provider_alias_generation_id="G1",
    )
    activation_lease = store.issue_activation_lease(
        pointer_name=POINTER,
        committer_id="committer-1",
        issued_at="2026-11-11T01:03:30+08:00",
    )
    views = IndexReadViewManager(store)
    old_view = views.acquire(
        view_id="read-view-old-G1",
        pointer_name=POINTER,
        expected_generation_id="G1",
        expected_pointer_revision=7,
        owner_id="request-old",
        now="2026-11-11T01:04:00+08:00",
        lease_expires_at="2026-11-11T01:14:00+08:00",
    )
    assert old_view.view is not None

    activated = committer.activate(
        activation_id="activate-G2",
        pointer_name=POINTER,
        target_generation_id="G2",
        expected_generation_id="G1",
        expected_revision=7,
        committer_id="committer-1",
        committer_fence=activation_lease.fencing_token,
        committed_at="2026-11-11T01:05:00+08:00",
        previous_retire_after="2026-11-11T01:20:00+08:00",
    )
    pointer_events = tuple(
        item
        for item in store.outbox_events()
        if item.event_type == "INDEX_POINTER_CHANGED"
    )
    pointer_event = pointer_events[0]
    committer.project_provider_alias(pointer_event.event_id, acknowledge=False)
    projected = committer.project_provider_alias(pointer_event.event_id)

    views.release(
        view_id=old_view.view.view_id,
        expected_fence=old_view.view.fencing_token,
        released_at="2026-11-11T01:10:00+08:00",
    )
    g1_before_retire = store.read_lifecycle("G1")
    assert g1_before_retire is not None
    retired = views.retire(
        generation_id="G1",
        expected_state_version=g1_before_retire.state_version,
        now="2026-11-11T01:21:00+08:00",
    )

    for evidence in (
        DeletionEvidence(
            evidence_id="delete-B-logical-release",
            deletion_snapshot_id=deletion_snapshot.deletion_snapshot_id,
            verification_policy_id="day104-delete-policy-v1",
            validator_id="day104-deletion-validator",
            validator_version="v1",
            scope=DeletionEvidenceScope.LOGICAL_RELEASE,
            status=EvidenceStatus.PASS,
            pointer_name=POINTER,
            pointer_revision=8,
            generation_ids=("G2",),
            tombstoned_occurrence_ids=("B@v1",),
            readback_digest=stable_hash("B blocked at release"),
            observed_at="2026-11-11T01:22:00+08:00",
        ),
        DeletionEvidence(
            evidence_id="delete-B-serving-absence",
            deletion_snapshot_id=deletion_snapshot.deletion_snapshot_id,
            verification_policy_id="day104-delete-policy-v1",
            validator_id="day104-deletion-validator",
            validator_version="v1",
            scope=DeletionEvidenceScope.SERVING_INDEX_ABSENCE,
            status=EvidenceStatus.PASS,
            pointer_name=POINTER,
            pointer_revision=8,
            generation_ids=("G2",),
            tombstoned_occurrence_ids=("B@v1",),
            readback_digest=stable_hash("B absent from serving generations"),
            observed_at="2026-11-11T01:22:00+08:00",
        ),
        DeletionEvidence(
            evidence_id="delete-B-physical-purge",
            deletion_snapshot_id=deletion_snapshot.deletion_snapshot_id,
            verification_policy_id="day104-delete-policy-v1",
            validator_id="day104-deletion-validator",
            validator_version="v1",
            scope=DeletionEvidenceScope.PHYSICAL_PURGE,
            status=EvidenceStatus.NOT_RUN,
            pointer_name=POINTER,
            pointer_revision=8,
            generation_ids=(),
            tombstoned_occurrence_ids=("B@v1",),
            readback_digest=stable_hash("physical purge not run"),
            observed_at="2026-11-11T01:22:00+08:00",
        ),
    ):
        deletion.record_evidence(evidence)
    deletion.mark_dispatched("delete-B-v1")
    verified = deletion.verify(
        deletion_id="delete-B-v1",
    )
    old_lifecycle = store.read_lifecycle("G1")
    assert old_lifecycle is not None
    active_lifecycle = store.read_lifecycle("G2")
    assert active_lifecycle is not None
    closed_view = store.read_read_view(old_view.view.view_id)
    assert closed_view is not None
    activation_record = activated.activation
    assert activation_record is not None
    verified_intent = verified.intent
    assert verified_intent is not None
    generation_evidence: dict[str, object] = {}
    for generation_id, ready in sorted(ready_results.items()):
        artifact = ready.artifact
        assert artifact is not None
        generation_evidence[generation_id] = {
            "artifact_fingerprint": artifact.fingerprint,
            "manifest_digest": artifact.manifest_digest,
            "evaluation_ruler_fingerprint": (artifact.evaluation_ruler_fingerprint),
            "validation_record_digest": artifact.validation_record_digest,
            "evaluation_evidence_digest": artifact.evaluation_evidence_digest,
            "evaluation_report_digest": artifact.evaluation_report_digest,
            "physical_namespace": artifact.physical_namespace,
        }

    return {
        "evidence_level": "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE",
        "fixture_production_eligible": False,
        "build_snapshot": {
            "fingerprint": snapshot.fingerprint,
            "source_snapshot": snapshot.source_snapshot.identity,
            "authorization_snapshot": (snapshot.authorization_snapshot.identity),
            "embedding_contract": snapshot.embedding_contract.identity,
            "index_schema": snapshot.index_schema.identity,
            "source_watermark": snapshot.source_watermark,
            "deletion_snapshot": snapshot.deletion_snapshot.identity,
            "deletion_snapshot_digest": snapshot.deletion_snapshot.digest,
        },
        "build_snapshot_fingerprint": snapshot.fingerprint,
        "evaluation_ruler_fingerprint": ruler.fingerprint,
        "ready_generations": tuple(sorted(ready_results)),
        "generation_evidence": generation_evidence,
        "activation_outcome": activated.outcome.value,
        "active_pointer": {
            "generation_id": activated.pointer.generation_id,
            "revision": activated.pointer.revision,
        }
        if activated.pointer is not None
        else None,
        "provider_alias": store.read_provider_alias(POINTER),
        "alias_projection_outcome": projected.outcome.value,
        "activation_record": {
            "activation_id": activation_record.activation_id,
            "digest": activation_record.digest,
            "from_revision": activation_record.from_revision,
            "to_revision": activation_record.to_revision,
            "committer_fence": activation_record.committer_fence,
        },
        "read_view": {
            "generation_id": closed_view.generation_id,
            "pointer_revision": closed_view.pointer_revision,
            "final_status": closed_view.status.value,
            "final_fencing_token": closed_view.fencing_token,
        },
        "old_generation_state": old_lifecycle.state.value,
        "active_generation_state": active_lifecycle.state.value,
        "retirement_outcome": retired.outcome.value,
        "deletion_outcome": verified.outcome.value,
        "deletion_verification": {
            "policy_id": verified_intent.verification_policy_id,
            "required_scopes": tuple(
                scope.value for scope in verified_intent.required_evidence_scopes
            ),
            "snapshot_id": verified_intent.verified_deletion_snapshot_id,
            "evidence_ids": verified_intent.verified_evidence_ids,
            "evidence_digest": verified_intent.verified_evidence_digest,
        },
        "physical_purge": "NOT_RUN",
        "raw_content_logged": False,
        "raw_vectors_logged": False,
        "real_database": "NOT_RUN",
        "real_vector_provider": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
