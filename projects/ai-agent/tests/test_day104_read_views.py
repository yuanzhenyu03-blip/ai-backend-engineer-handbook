from __future__ import annotations

from dataclasses import replace
import unittest

from rag_index_lifecycle_committer import (
    InMemoryIndexLifecycleStore,
    IndexLifecycleCommitter,
    ReadyOutcome,
    RegistrationOutcome,
)
from rag_index_lifecycle_contracts import (
    ActivePointer,
    BuildSnapshot,
    EvaluationDecision,
    EvaluationEvidence,
    EvaluationRuler,
    GenerationLifecycle,
    GenerationState,
    ImmutableBinding,
    ReadViewStatus,
)
from rag_index_lifecycle_orchestrator import (
    BuildValidationOutcome,
    DeterministicSealedIndexProvider,
    IndexedOccurrence,
    IndexLifecycleOrchestrator,
)
from rag_index_read_views import (
    IndexReadViewManager,
    ReadViewOutcome,
    RetirementOutcome,
)


NOW = "2026-11-11T00:00:00Z"
FUTURE = "2026-11-11T00:05:00Z"
LATER = "2026-11-11T00:10:00Z"
PAST = "2026-11-10T23:59:00Z"


def _binding(identity: str) -> ImmutableBinding:
    return ImmutableBinding(identity, f"sha256:{identity}")


def _snapshot() -> BuildSnapshot:
    return BuildSnapshot(
        build_snapshot_id="BS2",
        scope_id="refund-rag",
        source_snapshot=_binding("S1"),
        authorization_snapshot=_binding("P1"),
        embedding_contract=_binding("E1"),
        index_schema=_binding("IS1"),
        source_watermark="W1",
        deletion_snapshot=_binding("D1"),
    )


def _ruler() -> EvaluationRuler:
    return EvaluationRuler(
        dataset_fingerprint="sha256:dataset",
        evaluator_fingerprint="sha256:evaluator",
        policy_fingerprint="sha256:policy",
    )


def _active_fixture() -> (
    tuple[
        InMemoryIndexLifecycleStore,
        IndexReadViewManager,
    ]
):
    store = InMemoryIndexLifecycleStore()
    committer = IndexLifecycleCommitter(store)
    snapshot = _snapshot()
    ruler = _ruler()
    store.set_current_build_snapshot(snapshot)
    orchestrator = IndexLifecycleOrchestrator(
        provider=DeterministicSealedIndexProvider(),
        committer=committer,
    )
    result = orchestrator.build_and_validate(
        generation_id="G2",
        build_snapshot=snapshot,
        evaluation_ruler=ruler,
        expected_occurrences=(
            IndexedOccurrence(
                "A@v1",
                "sha256:a-content",
                "sha256:a-metadata",
                "sha256:a-provenance",
            ),
            IndexedOccurrence(
                "C@v1",
                "sha256:c-content",
                "sha256:c-metadata",
                "sha256:c-provenance",
            ),
        ),
        physical_namespace="refund-g2",
        provider_write_fence=11,
        validation_id="V2",
        validator_version="validator-v1",
        observed_at=NOW,
        expected_absent_occurrence_ids=("B@v1",),
    )
    if result.outcome is not BuildValidationOutcome.VALIDATING:
        raise AssertionError(result.safe_reason)
    if result.manifest is None:
        raise AssertionError("fixture manifest is required")
    evidence = EvaluationEvidence(
        evidence_id="R2",
        generation_id="G2",
        build_snapshot_fingerprint=snapshot.fingerprint,
        manifest_digest=result.manifest.digest,
        dataset_fingerprint=ruler.dataset_fingerprint,
        evaluator_fingerprint=ruler.evaluator_fingerprint,
        policy_fingerprint=ruler.policy_fingerprint,
        evaluation_report_checksum="sha256:R2",
        evidence_level="DETERMINISTIC_FAKE",
        decision=EvaluationDecision.PASS,
        observed_at=NOW,
    )
    if committer.record_evaluation(evidence) is not RegistrationOutcome.REGISTERED:
        raise AssertionError("fixture evaluation did not register")
    ready = committer.mark_ready(
        generation_id="G2",
        expected_state_version=1,
        validation_record_id="V2",
        evaluation_evidence_id="R2",
    )
    if ready.outcome is not ReadyOutcome.READY:
        raise AssertionError(ready.safe_reason)
    store.seed_active_pointer(
        pointer=ActivePointer("refund-rag-active", "G2", 8),
        provider_alias_generation_id="G2",
    )
    return store, IndexReadViewManager(store)


def _acquire(manager: IndexReadViewManager, view_id: str = "RV-1"):
    return manager.acquire(
        view_id=view_id,
        pointer_name="refund-rag-active",
        expected_generation_id="G2",
        expected_pointer_revision=8,
        owner_id=f"owner:{view_id}",
        now=NOW,
        lease_expires_at=FUTURE,
    )


def _set_draining(
    store: InMemoryIndexLifecycleStore,
    *,
    retire_after: str = PAST,
    active_readers: int | None = None,
) -> None:
    current = store.read_lifecycle("G2")
    if current is None:
        raise AssertionError("fixture lifecycle is required")
    readers = current.active_readers if active_readers is None else active_readers
    store._lifecycles["G2"] = replace(
        current,
        state=GenerationState.DRAINING,
        state_version=current.state_version + 1,
        transition_fence=current.transition_fence + 1,
        active_readers=readers,
        retire_after=retire_after,
    )


def _lifecycle(store: InMemoryIndexLifecycleStore) -> GenerationLifecycle:
    lifecycle = store.read_lifecycle("G2")
    if lifecycle is None:
        raise AssertionError("fixture lifecycle is required")
    return lifecycle


class Day104ReadViewTests(unittest.TestCase):
    def test_acquire_atomically_creates_view_and_increments_reader(self) -> None:
        store, manager = _active_fixture()
        result = _acquire(manager)
        self.assertIs(result.outcome, ReadViewOutcome.ACQUIRED)
        self.assertTrue(result.durable_transition)
        self.assertIsNotNone(store.read_read_view("RV-1"))
        self.assertEqual(_lifecycle(store).active_readers, 1)

        replay = _acquire(manager)
        self.assertIs(replay.outcome, ReadViewOutcome.ALREADY_ACQUIRED)
        self.assertEqual(_lifecycle(store).active_readers, 1)

    def test_stale_pointer_creates_no_view_or_reader(self) -> None:
        store, manager = _active_fixture()
        result = manager.acquire(
            view_id="RV-stale",
            pointer_name="refund-rag-active",
            expected_generation_id="G2",
            expected_pointer_revision=7,
            owner_id="owner:stale",
            now=NOW,
            lease_expires_at=FUTURE,
        )
        self.assertIs(result.outcome, ReadViewOutcome.STALE_POINTER)
        self.assertIsNone(store.read_read_view("RV-stale"))
        self.assertEqual(_lifecycle(store).active_readers, 0)

    def test_draining_generation_rejects_new_read_view(self) -> None:
        store, manager = _active_fixture()
        _set_draining(store)
        result = _acquire(manager)
        self.assertIs(result.outcome, ReadViewOutcome.NOT_ACTIVE)
        self.assertIsNone(store.read_read_view("RV-1"))

    def test_release_decrements_reader_exactly_once(self) -> None:
        store, manager = _active_fixture()
        _acquire(manager)
        released = manager.release(
            view_id="RV-1",
            expected_fence=1,
            released_at="2026-11-11T00:01:00Z",
        )
        self.assertIs(released.outcome, ReadViewOutcome.CLOSED)
        self.assertEqual(_lifecycle(store).active_readers, 0)

        stale_retry = manager.release(
            view_id="RV-1",
            expected_fence=1,
            released_at="2026-11-11T00:02:00Z",
        )
        self.assertIs(stale_retry.outcome, ReadViewOutcome.STALE_FENCE)
        self.assertEqual(_lifecycle(store).active_readers, 0)

    def test_heartbeat_extends_only_a_current_open_lease(self) -> None:
        _, manager = _active_fixture()
        _acquire(manager)
        heartbeat = manager.heartbeat(
            view_id="RV-1",
            expected_fence=1,
            now="2026-11-11T00:01:00Z",
            lease_expires_at=LATER,
        )
        self.assertIs(heartbeat.outcome, ReadViewOutcome.HEARTBEAT)
        view = heartbeat.view
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.lease_expires_at, LATER)

    def test_reaper_expires_and_decrements_each_view_once(self) -> None:
        store, manager = _active_fixture()
        _acquire(manager)
        expired = manager.reap_expired(now=LATER)
        self.assertEqual(len(expired), 1)
        self.assertIs(expired[0].status, ReadViewStatus.EXPIRED)
        self.assertEqual(expired[0].fencing_token, 2)
        self.assertEqual(_lifecycle(store).active_readers, 0)

        self.assertEqual(manager.reap_expired(now=LATER), ())
        self.assertEqual(_lifecycle(store).active_readers, 0)

    def test_late_release_after_reaper_is_fenced(self) -> None:
        store, manager = _active_fixture()
        _acquire(manager)
        manager.reap_expired(now=LATER)
        late = manager.release(
            view_id="RV-1",
            expected_fence=1,
            released_at=LATER,
        )
        self.assertIs(late.outcome, ReadViewOutcome.STALE_FENCE)
        self.assertEqual(_lifecycle(store).active_readers, 0)

    def test_counter_ledger_mismatch_blocks_retirement(self) -> None:
        store, manager = _active_fixture()
        _acquire(manager)
        _set_draining(store, active_readers=0)
        lifecycle = _lifecycle(store)
        result = manager.retire(
            generation_id="G2",
            expected_state_version=lifecycle.state_version,
            now=NOW,
        )
        self.assertIs(result.outcome, RetirementOutcome.LEDGER_MISMATCH)
        self.assertIs(_lifecycle(store).state, GenerationState.DRAINING)

    def test_reconciliation_repairs_counter_from_open_lease_ledger(self) -> None:
        store, manager = _active_fixture()
        _acquire(manager)
        _set_draining(store, active_readers=0)
        count = manager.reconcile_reader_count(
            generation_id="G2",
            now=NOW,
            reason="READ_VIEW_LEDGER_MISMATCH",
        )
        self.assertEqual(count, 1)
        self.assertEqual(_lifecycle(store).active_readers, 1)
        self.assertEqual(
            store.reader_reconciliations(),
            (("G2", 0, 1, "READ_VIEW_LEDGER_MISMATCH"),),
        )

    def test_reconciliation_audits_ledger_repair_when_count_already_matches(
        self,
    ) -> None:
        store, manager = _active_fixture()
        _acquire(manager)
        _set_draining(store, active_readers=0)
        before = _lifecycle(store)

        count = manager.reconcile_reader_count(
            generation_id="G2",
            now=LATER,
            reason="EXPIRED_OPEN_VIEW_WITH_MATCHING_ZERO_COUNTER",
        )

        self.assertEqual(count, 0)
        repaired = store.read_read_view("RV-1")
        self.assertIsNotNone(repaired)
        assert repaired is not None
        self.assertIs(repaired.status, ReadViewStatus.EXPIRED)
        self.assertEqual(repaired.fencing_token, 2)
        self.assertEqual(_lifecycle(store).state_version, before.state_version + 1)
        self.assertEqual(
            store.reader_reconciliations(),
            (
                (
                    "G2",
                    0,
                    0,
                    "EXPIRED_OPEN_VIEW_WITH_MATCHING_ZERO_COUNTER",
                ),
            ),
        )

    def test_retirement_waits_for_retention_window(self) -> None:
        store, manager = _active_fixture()
        _set_draining(store, retire_after=LATER)
        lifecycle = _lifecycle(store)
        result = manager.retire(
            generation_id="G2",
            expected_state_version=lifecycle.state_version,
            now=NOW,
        )
        self.assertIs(result.outcome, RetirementOutcome.RETENTION_NOT_MET)

    def test_drained_generation_retires_without_claiming_physical_purge(self) -> None:
        store, manager = _active_fixture()
        _set_draining(store, retire_after=PAST)
        lifecycle = _lifecycle(store)
        result = manager.retire(
            generation_id="G2",
            expected_state_version=lifecycle.state_version,
            now=NOW,
        )
        self.assertIs(result.outcome, RetirementOutcome.RETIRED)
        self.assertTrue(result.durable_transition)
        retired = _lifecycle(store)
        self.assertIs(retired.state, GenerationState.RETIRED)
        self.assertEqual(retired.active_readers, 0)


if __name__ == "__main__":
    unittest.main()
