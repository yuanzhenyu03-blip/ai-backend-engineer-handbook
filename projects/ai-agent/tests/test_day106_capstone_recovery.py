from __future__ import annotations

from dataclasses import asdict, fields, replace
import unittest

from rag_capstone_contracts import (
    AnswerReleaseRecord,
    CapstoneEvaluationDecision,
    CapstoneRequestBinding,
    CapstoneResult,
    Day101ExecutionReceipt,
    DispatchObservation,
    EndToEndExecutionManifest,
    RecoveryAndIncidentRecord,
    ReleaseCurrentnessSnapshot,
    ResponseIntent,
    ResponseIntentState,
    RetrievalAndContextReceipt,
    SourceToOccurrenceLineage,
)
from rag_capstone_orchestrator import (
    CapstoneComposer,
    CapstoneGateRejected,
    CapstoneIdentityConflict,
    InMemoryReleaseCurrentnessAuthority,
    InMemoryResponseLedger,
    seal_execution,
)
from rag_chunking_contracts import stable_hash
from rag_authorized_retriever import (
    InMemoryRetrievalAuthorization,
    classroom_authorization_revisions,
)
from rag_retrieval_contracts import RetrievalAuthorizationScope


NOW = "2026-11-23T10:00:00+08:00"


def authorization_scope() -> RetrievalAuthorizationScope:
    return RetrievalAuthorizationScope(
        tenant_id="tenant-refund",
        principal_subject="principal-refund-reader",
        action="chunk:retrieve",
        purpose="day100-authorized-hybrid-retrieval",
        revisions=classroom_authorization_revisions(
            policy_revision=1,
            acl_revision=1,
            authorization_epoch=1,
        ),
        allowed_occurrence_ids=("A@v1",),
        decision_id="authorization-P1",
    )


def currentness_snapshot(
    *,
    snapshot_id: str = "release-currentness-P1",
    revision: int = 1,
    eligible_occurrence_ids: tuple[str, ...] = ("A@v1",),
) -> ReleaseCurrentnessSnapshot:
    return ReleaseCurrentnessSnapshot(
        snapshot_id=snapshot_id,
        revision=revision,
        tenant_id="tenant-refund",
        destination="current-chat",
        source_eligible_occurrence_ids=eligible_occurrence_ids,
        quarantined_occurrence_ids=(),
        provenance_revision="PROV-R1",
        tombstone_revision="D1",
        content_security_snapshot_digest=stable_hash(
            ("content-security", revision)
        ),
        security_policy_fingerprint=stable_hash("security-policy"),
        dlp_result="PASS",
        metadata_stripping_result="PASS",
        destination_result="PASS",
        evidence_digests=(stable_hash(("current-release-evidence", revision)),),
    )


def response_ledger_with_authorities() -> tuple[
    InMemoryResponseLedger,
    InMemoryRetrievalAuthorization,
    InMemoryReleaseCurrentnessAuthority,
]:
    authorization = InMemoryRetrievalAuthorization()
    authorization.put(authorization_scope())
    currentness = InMemoryReleaseCurrentnessAuthority()
    currentness.put(currentness_snapshot())
    return (
        InMemoryResponseLedger(
            authorization_authority=authorization,
            release_currentness_authority=currentness,
        ),
        authorization,
        currentness,
    )


def response_ledger() -> InMemoryResponseLedger:
    return response_ledger_with_authorities()[0]


def release_record(
    *,
    record_id: str = "release-record-Q2",
    intent_id: str = "response-intent-Q2",
) -> AnswerReleaseRecord:
    scope = authorization_scope()
    currentness = currentness_snapshot()
    return AnswerReleaseRecord(
        record_id=record_id,
        request_binding_digest=stable_hash("binding-Q2"),
        retrieval_context_receipt_digest=stable_hash("receipt-Q2"),
        model_invocation_id="model-invocation-Q2",
        model_invocation_digest=stable_hash("model-invocation-Q2"),
        answer_candidate_id="answer-candidate-Q2",
        answer_candidate_digest=stable_hash("answer-candidate-Q2"),
        release_evidence_id="release-evidence-Q2",
        release_evidence_digest=stable_hash("release-evidence-Q2"),
        output_release_decision_id="output-release-decision-Q2",
        output_release_decision_digest=stable_hash("output-release-decision-Q2"),
        disclosure_envelope_digest=stable_hash("disclosure-Q2"),
        tenant_id=scope.tenant_id,
        principal_id=scope.principal_subject,
        action=scope.action,
        purpose=scope.purpose,
        current_authorization_scope_fingerprint=scope.fingerprint,
        current_authorization_revision_digest=stable_hash(
            asdict(scope.revisions)
        ),
        release_currentness_snapshot_id=currentness.snapshot_id,
        release_currentness_snapshot_digest=currentness.digest,
        release_currentness_revision=currentness.revision,
        released_occurrence_ids=("A@v1",),
        authorized_destination="current-chat",
        dispatch_idempotency_key="dispatch-key-Q2",
        result="PASS",
        disposition="RELEASE",
        safe_reason_codes=(),
        response_intent_id=intent_id,
        response_dispatch_state=ResponseIntentState.PENDING,
        created_at=NOW,
    )


def second_release_record() -> AnswerReleaseRecord:
    return replace(
        release_record(),
        record_id="release-record-Q2-second",
        request_binding_digest=stable_hash("binding-Q2-second"),
        retrieval_context_receipt_digest=stable_hash("receipt-Q2-second"),
        model_invocation_id="model-invocation-Q2-second",
        model_invocation_digest=stable_hash("model-invocation-Q2-second"),
        answer_candidate_id="answer-candidate-Q2-second",
        answer_candidate_digest=stable_hash("answer-candidate-Q2-second"),
        release_evidence_id="release-evidence-Q2-second",
        release_evidence_digest=stable_hash("release-evidence-Q2-second"),
        output_release_decision_id="output-release-decision-Q2-second",
        output_release_decision_digest=stable_hash(
            "output-release-decision-Q2-second"
        ),
        disclosure_envelope_digest=stable_hash("disclosure-Q2-second"),
        dispatch_idempotency_key="dispatch-key-Q2-second",
        response_intent_id="response-intent-Q2-second",
    )


def blocked_record() -> AnswerReleaseRecord:
    scope = authorization_scope()
    currentness = currentness_snapshot()
    return AnswerReleaseRecord(
        record_id="release-record-old-G2",
        request_binding_digest=stable_hash("binding-old-G2"),
        retrieval_context_receipt_digest=stable_hash("receipt-old-G2"),
        model_invocation_id="model-invocation-old-G2",
        model_invocation_digest=stable_hash("model-invocation-old-G2"),
        answer_candidate_id="answer-candidate-old-G2",
        answer_candidate_digest=stable_hash("answer-candidate-old-G2"),
        release_evidence_id="release-evidence-P2",
        release_evidence_digest=stable_hash("release-evidence-P2"),
        output_release_decision_id="output-release-decision-P2",
        output_release_decision_digest=stable_hash("output-release-decision-P2"),
        disclosure_envelope_digest=stable_hash("disclosure-old-G2"),
        tenant_id=scope.tenant_id,
        principal_id=scope.principal_subject,
        action=scope.action,
        purpose=scope.purpose,
        current_authorization_scope_fingerprint=scope.fingerprint,
        current_authorization_revision_digest=stable_hash(
            asdict(scope.revisions)
        ),
        release_currentness_snapshot_id=currentness.snapshot_id,
        release_currentness_snapshot_digest=currentness.digest,
        release_currentness_revision=currentness.revision,
        released_occurrence_ids=(),
        authorized_destination=None,
        dispatch_idempotency_key=None,
        result="FAIL",
        disposition="BLOCKED",
        safe_reason_codes=("CURRENT_AUTHORIZATION_CHANGED",),
        response_intent_id=None,
        response_dispatch_state=ResponseIntentState.NOT_ATTEMPTED,
        created_at=NOW,
    )


def observation(
    *,
    record_id: str,
    previous_record_id: str | None,
    outcome: DispatchObservation,
    timestamp: str,
    attempt_id: str = "transport-attempt-1",
    provider_message_id: str | None = None,
    intent_id: str = "response-intent-Q2",
    dispatch_key: str = "dispatch-key-Q2",
) -> RecoveryAndIncidentRecord:
    return RecoveryAndIncidentRecord(
        record_id=record_id,
        response_intent_id=intent_id,
        previous_record_id=previous_record_id,
        transport_attempt_id=attempt_id,
        dispatch_idempotency_key=dispatch_key,
        observation=outcome,
        safe_reason_code=f"OBSERVED_{outcome.value}",
        observed_at=timestamp,
        evidence_digests=(stable_hash((record_id, outcome.value)),),
        provider_message_id=provider_message_id,
    )


def lineage() -> SourceToOccurrenceLineage:
    return SourceToOccurrenceLineage(
        lineage_id="lineage-A-v1",
        tenant_id="tenant-refund",
        resource_id="refund-resource-A",
        source_artifact_id="source-A",
        source_version="v1",
        source_artifact_digest=stable_hash("source-A-v1"),
        parsed_artifact_id="parsed-A-v1",
        parsed_artifact_digest=stable_hash("parsed-A-v1"),
        parser_contract_version="parser-v1",
        chunk_set_id="chunk-set-v1",
        chunk_set_digest=stable_hash("chunk-set-v1"),
        chunker_contract_version="chunker-v1",
        occurrence_id="A@v1",
        content_digest=stable_hash("content-A-v1"),
        metadata_digest=stable_hash("metadata-A-v1"),
        metadata_version="metadata-v1",
        provenance_revision="PROV-R1",
        embedding_set_id="embedding-set-v1",
        embedding_record_id="embedding-A-v1",
        embedding_contract_fingerprint=stable_hash("embedding-contract-v1"),
        upstream_evidence_digests=(stable_hash("upstream-evidence"),),
    )


def request_binding() -> CapstoneRequestBinding:
    return CapstoneRequestBinding(
        request_attempt_id="R1",
        request_id="R1",
        principal_id="principal-refund-reader",
        tenant_id="tenant-refund",
        action="chunk:retrieve",
        purpose="day100-authorized-hybrid-retrieval",
        audience="current-user",
        pointer_name="refund-serving",
        generation_id="G2",
        generation_artifact_digest=stable_hash("artifact-G2"),
        generation_manifest_digest=stable_hash("manifest-G2"),
        build_snapshot_fingerprint=stable_hash("BS1"),
        pointer_revision=8,
        read_view_id="read-view-R1",
        read_view_fence=1,
        read_view_digest=stable_hash("read-view-R1"),
        source_snapshot_id="S1",
        authorization_snapshot_id="P1",
        deletion_snapshot_id="D1",
        policy_fingerprint=stable_hash("policy"),
        security_binding_fingerprint=stable_hash("security-binding"),
        retrieval_authorization_revision_digest=stable_hash("auth-revisions"),
        retrieval_authorization_scope_fingerprint=stable_hash("auth-scope"),
        selected_retrieval_bundle_id="refund-serving@G2/r8",
        selected_retrieval_bundle_revision=8,
        selected_retrieval_bundle_fingerprint=stable_hash("retrieval-bundle"),
        created_at=NOW,
    )


def retrieval_receipt(binding: CapstoneRequestBinding) -> RetrievalAndContextReceipt:
    scope = authorization_scope()
    return RetrievalAndContextReceipt(
        receipt_id="receipt-R1",
        request_binding_digest=binding.digest,
        retrieval_operation_id="operation-R1",
        retrieval_request_id="R1",
        day101_execution_receipt_digest=stable_hash("day101-execution-R1"),
        day101_handoff_digest=stable_hash("day101-handoff"),
        prompt_authorization_scope_fingerprint=scope.fingerprint,
        prompt_authorization_revision_digest=stable_hash(
            asdict(scope.revisions)
        ),
        retrieval_bundle_id="bundle-R1",
        retrieval_bundle_digest=stable_hash("bundle-R1"),
        retrieval_security_decision_digest=stable_hash("retrieval-security"),
        bundle_security_decision_digest=stable_hash("bundle-security"),
        exact_occurrence_ids=("A@v1",),
        exact_content_digests=(stable_hash("content-A-v1"),),
        context_manifest_id="context-R1",
        context_manifest_digest=stable_hash("context-R1"),
        context_occurrence_ids=("A@v1",),
        assembled_context_digest=stable_hash("assembled-context-R1"),
        unauthorized_prompt_count=0,
        created_at=NOW,
    )


def response_intent(record: AnswerReleaseRecord) -> ResponseIntent:
    if (
        record.response_intent_id is None
        or record.authorized_destination is None
        or record.dispatch_idempotency_key is None
    ):
        raise ValueError("release record does not own a response intent")
    return ResponseIntent(
        intent_id=record.response_intent_id,
        request_binding_digest=record.request_binding_digest,
        output_release_decision_digest=record.output_release_decision_digest,
        candidate_digest=record.answer_candidate_digest,
        destination=record.authorized_destination,
        dispatch_idempotency_key=record.dispatch_idempotency_key,
        state=ResponseIntentState.PENDING,
        revision=1,
        created_at=record.created_at,
    )


class Day106CapstoneRecoveryTests(unittest.TestCase):
    def test_release_decision_and_intent_commit_atomically_and_replay_exactly(
        self,
    ) -> None:
        ledger = response_ledger()
        record = release_record()

        first = ledger.commit_decision_and_intent(
            release_record=record,
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        replay = ledger.commit_decision_and_intent(
            release_record=record,
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )

        self.assertIsNotNone(first)
        self.assertEqual(first, replay)
        self.assertEqual(first.state, ResponseIntentState.PENDING)
        self.assertIsNone(first.dispatch_at)
        self.assertEqual(first.destination, record.authorized_destination)
        self.assertEqual(
            first.dispatch_idempotency_key,
            record.dispatch_idempotency_key,
        )
        self.assertEqual(
            first.output_release_decision_digest,
            record.output_release_decision_digest,
        )
        self.assertEqual(first.candidate_digest, record.answer_candidate_digest)
        self.assertTrue(record.disclosure_envelope_digest)
        self.assertEqual(ledger.release_records(), (record,))
        self.assertEqual(ledger.recoverable_intents(), (first,))

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "DISPATCH_AUTHORITY_BINDING_CONFLICT",
        ):
            ledger.commit_decision_and_intent(
                release_record=record,
                destination="unauthorized-destination",
                dispatch_idempotency_key="different-key",
            )

    def test_same_release_record_id_with_different_content_is_conflict(self) -> None:
        ledger = response_ledger()
        record = release_record()
        ledger.commit_decision_and_intent(
            release_record=record,
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RELEASE_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT",
        ):
            ledger.commit_decision_and_intent(
                release_record=replace(
                    record,
                    answer_candidate_digest=stable_hash("another-candidate"),
                ),
                destination="current-chat",
                dispatch_idempotency_key="dispatch-key-Q2",
            )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RELEASE_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT",
        ):
            ledger.commit_decision_and_intent(
                release_record=replace(
                    record,
                    disclosure_envelope_digest=stable_hash("other-disclosure"),
                ),
                destination="current-chat",
                dispatch_idempotency_key="dispatch-key-Q2",
            )

    def test_duplicate_decision_ownership_is_rejected_before_dispatch(self) -> None:
        ledger = response_ledger()
        first = release_record()
        ledger.commit_decision_and_intent(
            release_record=first,
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        duplicate_owner = replace(
            first,
            record_id="release-record-Q2-other-owner",
            dispatch_idempotency_key="dispatch-key-Q2-other-owner",
        )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "OUTPUT_RELEASE_DECISION_(ID_)?ALREADY_OWNED",
        ):
            ledger.commit_decision_and_intent(
                release_record=duplicate_owner,
                destination="current-chat",
                dispatch_idempotency_key="dispatch-key-Q2-other-owner",
            )

    def test_duplicate_intent_id_is_rejected_for_a_different_decision(self) -> None:
        ledger = response_ledger()
        first = release_record()
        ledger.commit_decision_and_intent(
            release_record=first,
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        duplicate_intent = replace(
            first,
            record_id="release-record-Q2-different-decision",
            output_release_decision_id="output-release-decision-Q2-new",
            output_release_decision_digest=stable_hash(
                "output-release-decision-Q2-new"
            ),
            dispatch_idempotency_key="dispatch-key-Q2-new",
        )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RESPONSE_INTENT_ID_ALREADY_EXISTS",
        ):
            ledger.commit_decision_and_intent(
                release_record=duplicate_intent,
                destination="current-chat",
                dispatch_idempotency_key="dispatch-key-Q2-new",
            )

    def test_revocation_before_intent_commit_rejects_stale_release(self) -> None:
        ledger, authorization, currentness = response_ledger_with_authorities()
        record = release_record()
        authorization.revoke_occurrence(
            tenant_id=record.tenant_id,
            principal_subject=record.principal_id,
            action=record.action,
            purpose=record.purpose,
            occurrence_id="A@v1",
        )
        currentness.put(
            currentness_snapshot(
                snapshot_id="release-currentness-P2",
                revision=2,
                eligible_occurrence_ids=(),
            )
        )

        with self.assertRaisesRegex(
            CapstoneGateRejected,
            "RELEASE_CURRENTNESS_CHANGED_BEFORE_INTENT_COMMIT",
        ):
            ledger.commit_decision_and_intent(
                release_record=record,
                destination="current-chat",
                dispatch_idempotency_key="dispatch-key-Q2",
            )
        self.assertEqual(ledger.release_records(), ())
        self.assertEqual(ledger.recoverable_intents(), ())

    def test_release_fails_closed_without_bound_currentness_authorities(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            CapstoneGateRejected,
            "CURRENTNESS_AUTHORITIES_NOT_BOUND",
        ):
            InMemoryResponseLedger().commit_decision_and_intent(
                release_record=release_record(),
                destination="current-chat",
                dispatch_idempotency_key="dispatch-key-Q2",
            )

    def test_revocation_before_send_rejects_pending_intent(self) -> None:
        ledger, authorization, currentness = response_ledger_with_authorities()
        record = release_record()
        intent = ledger.commit_decision_and_intent(
            release_record=record,
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        self.assertIsNotNone(intent)
        authorization.revoke_occurrence(
            tenant_id=record.tenant_id,
            principal_subject=record.principal_id,
            action=record.action,
            purpose=record.purpose,
            occurrence_id="A@v1",
        )
        currentness.put(
            currentness_snapshot(
                snapshot_id="release-currentness-P2",
                revision=2,
                eligible_occurrence_ids=(),
            )
        )
        started = observation(
            record_id="dispatch-event-after-revocation",
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )

        with self.assertRaisesRegex(
            CapstoneGateRejected,
            "RELEASE_CURRENTNESS_CHANGED_BEFORE_SEND",
        ):
            ledger.append_observation(started)
        self.assertEqual(ledger.history("response-intent-Q2"), ())

    def test_blocked_decision_has_no_intent_and_dispatch_is_not_attempted(self) -> None:
        ledger = response_ledger()
        record = blocked_record()
        intent = ledger.commit_decision_and_intent(
            release_record=record,
            destination="",
            dispatch_idempotency_key="",
        )

        self.assertIsNone(intent)
        self.assertEqual(ledger.release_records(), (record,))
        self.assertEqual(ledger.recoverable_intents(), ())
        self.assertEqual(
            record.response_dispatch_state,
            ResponseIntentState.NOT_ATTEMPTED,
        )

        with self.assertRaisesRegex(
            CapstoneGateRejected,
            "BLOCKED_DECISION_CANNOT_CREATE_DISPATCH_INTENT",
        ):
            response_ledger().commit_decision_and_intent(
                release_record=record,
                destination="current-chat",
                dispatch_idempotency_key="forbidden-key",
            )

    def test_unknown_requires_reconciliation_before_retry_and_delivery_receipt(
        self,
    ) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        started = observation(
            record_id="dispatch-event-1",
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )
        unknown = observation(
            record_id="dispatch-event-2",
            previous_record_id=started.record_id,
            outcome=DispatchObservation.UNKNOWN,
            timestamp="2026-11-23T10:00:02+08:00",
        )
        not_found = observation(
            record_id="dispatch-event-3",
            previous_record_id=unknown.record_id,
            outcome=DispatchObservation.NOT_FOUND,
            timestamp="2026-11-23T10:00:03+08:00",
        )
        retry_started = observation(
            record_id="dispatch-event-4",
            previous_record_id=not_found.record_id,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:04+08:00",
            attempt_id="transport-attempt-2",
        )
        accepted = observation(
            record_id="dispatch-event-5",
            previous_record_id=retry_started.record_id,
            outcome=DispatchObservation.ACCEPTED,
            timestamp="2026-11-23T10:00:05+08:00",
            attempt_id="transport-attempt-2",
            provider_message_id="provider-message-Q2",
        )
        delivered = observation(
            record_id="dispatch-event-6",
            previous_record_id=accepted.record_id,
            outcome=DispatchObservation.DELIVERED,
            timestamp="2026-11-23T10:00:06+08:00",
            attempt_id="delivery-reconciliation-1",
            provider_message_id="provider-message-Q2",
        )
        duplicate = observation(
            record_id="dispatch-event-7",
            previous_record_id=delivered.record_id,
            outcome=DispatchObservation.DUPLICATE_RECEIPT,
            timestamp="2026-11-23T10:00:07+08:00",
            attempt_id="delivery-reconciliation-2",
            provider_message_id="provider-message-Q2",
        )

        ledger.append_observation(started)
        after_unknown = ledger.append_observation(unknown)
        self.assertEqual(after_unknown.state, ResponseIntentState.DELIVERY_UNKNOWN)
        self.assertIsNone(after_unknown.dispatch_at)
        self.assertEqual(ledger.recoverable_intents(), (after_unknown,))

        after_not_found = ledger.append_observation(not_found)
        self.assertEqual(after_not_found.state, ResponseIntentState.PENDING)
        ledger.append_observation(retry_started)
        after_accepted = ledger.append_observation(accepted)
        self.assertEqual(after_accepted.state, ResponseIntentState.DISPATCHED)
        self.assertEqual(after_accepted.dispatch_at, accepted.observed_at)
        self.assertIsNone(after_accepted.delivered_at)

        after_delivery = ledger.append_observation(delivered)
        self.assertEqual(after_delivery.state, ResponseIntentState.DELIVERED)
        self.assertEqual(after_delivery.delivered_at, delivered.observed_at)
        after_duplicate = ledger.append_observation(duplicate)
        self.assertEqual(after_duplicate.state, ResponseIntentState.DELIVERED)
        self.assertEqual(after_duplicate.delivered_at, delivered.observed_at)
        self.assertEqual(ledger.recoverable_intents(), ())
        self.assertEqual(
            tuple(item.record_id for item in ledger.history("response-intent-Q2")),
            tuple(f"dispatch-event-{index}" for index in range(1, 8)),
        )

    def test_transport_outcome_requires_matching_send_started(self) -> None:
        for outcome in (
            DispatchObservation.UNKNOWN,
            DispatchObservation.ACCEPTED,
        ):
            with self.subTest(outcome=outcome.value):
                ledger = response_ledger()
                ledger.commit_decision_and_intent(
                    release_record=release_record(),
                    destination="current-chat",
                    dispatch_idempotency_key="dispatch-key-Q2",
                )
                outcome_record = observation(
                    record_id=f"outcome-without-send-{outcome.value}",
                    previous_record_id=None,
                    outcome=outcome,
                    timestamp="2026-11-23T10:00:01+08:00",
                    provider_message_id=(
                        "provider-message-without-send"
                        if outcome is DispatchObservation.ACCEPTED
                        else None
                    ),
                )

                with self.assertRaisesRegex(
                    CapstoneGateRejected,
                    "DISPATCH_OUTCOME_REQUIRES_MATCHING_SEND_STARTED",
                ):
                    ledger.append_observation(outcome_record)
                self.assertEqual(ledger.history("response-intent-Q2"), ())

    def test_restore_rejects_dispatch_outcome_without_send_started(self) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        records, intents, _ = ledger.export_state()
        accepted = observation(
            record_id="accepted-without-send",
            previous_record_id=None,
            outcome=DispatchObservation.ACCEPTED,
            timestamp="2026-11-23T10:00:01+08:00",
            provider_message_id="provider-message-without-send",
        )
        forged_final = replace(
            intents[0],
            state=ResponseIntentState.DISPATCHED,
            revision=2,
            dispatch_at=accepted.observed_at,
            provider_message_id=accepted.provider_message_id,
        )

        with self.assertRaisesRegex(
            CapstoneGateRejected,
            "DISPATCH_OUTCOME_REQUIRES_MATCHING_SEND_STARTED",
        ):
            InMemoryResponseLedger.restore(
                (
                    records,
                    (forged_final,),
                    ((forged_final.intent_id, (accepted,)),),
                )
            )

    def test_append_only_history_rejects_fork_and_record_mutation(self) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        started = observation(
            record_id="dispatch-event-1",
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )
        ledger.append_observation(started)

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "APPEND_ONLY_HISTORY_FORK",
        ):
            ledger.append_observation(
                observation(
                    record_id="dispatch-event-fork",
                    previous_record_id=None,
                    outcome=DispatchObservation.UNKNOWN,
                    timestamp="2026-11-23T10:00:02+08:00",
                )
            )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RECOVERY_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT",
        ):
            ledger.append_observation(
                replace(started, safe_reason_code="MUTATED_OLD_HISTORY")
            )

    def test_recovery_record_id_is_owned_globally_during_live_append(self) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        ledger.commit_decision_and_intent(
            release_record=second_release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2-second",
        )
        first = observation(
            record_id="globally-owned-recovery-record",
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )
        second = observation(
            record_id=first.record_id,
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:02+08:00",
            intent_id="response-intent-Q2-second",
            dispatch_key="dispatch-key-Q2-second",
        )
        ledger.append_observation(first)

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RECOVERY_RECORD_ID_ALREADY_OWNED",
        ):
            ledger.append_observation(second)
        self.assertEqual(
            ledger.history("response-intent-Q2-second"),
            (),
        )

    def test_restore_rejects_cross_intent_recovery_record_id_reuse(self) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        ledger.commit_decision_and_intent(
            release_record=second_release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2-second",
        )
        records, intents, _ = ledger.export_state()
        duplicate_id = "cross-intent-recovery-record"
        first = observation(
            record_id=duplicate_id,
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )
        second = observation(
            record_id=duplicate_id,
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:02+08:00",
            intent_id="response-intent-Q2-second",
            dispatch_key="dispatch-key-Q2-second",
        )
        replayed_intents = tuple(replace(item, revision=2) for item in intents)

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RESTORE_RECOVERY_RECORD_ID_ALREADY_OWNED",
        ):
            InMemoryResponseLedger.restore(
                (
                    records,
                    replayed_intents,
                    (
                        ("response-intent-Q2", (first,)),
                        ("response-intent-Q2-second", (second,)),
                    ),
                )
            )

    def test_restart_replays_durable_state_and_rejects_tampered_state(self) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        started = observation(
            record_id="dispatch-event-1",
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )
        unknown = observation(
            record_id="dispatch-event-2",
            previous_record_id=started.record_id,
            outcome=DispatchObservation.UNKNOWN,
            timestamp="2026-11-23T10:00:02+08:00",
        )
        ledger.append_observation(started)
        expected = ledger.append_observation(unknown)

        state = ledger.export_state()
        restored = InMemoryResponseLedger.restore(state)
        self.assertEqual(restored.read_intent(expected.intent_id), expected)
        self.assertEqual(restored.recoverable_intents(), (expected,))

        records, intents, histories = state
        tampered = replace(
            intents[0],
            state=ResponseIntentState.DISPATCHED,
            dispatch_at="2026-11-23T10:00:03+08:00",
            provider_message_id="unproven-message",
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RESTORE_DURABLE_STATE_REPLAY_CONFLICT",
        ):
            InMemoryResponseLedger.restore((records, (tampered,), histories))

        wrong_dispatch_authority = replace(
            intents[0],
            destination="another-destination",
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RESTORE_DECISION_INTENT_BINDING_CONFLICT",
        ):
            InMemoryResponseLedger.restore(
                (records, (wrong_dispatch_authority,), histories)
            )

        duplicate_owner = replace(
            records[0],
            record_id="release-record-Q2-duplicate-owner",
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RESTORE_DUPLICATE_RESPONSE_INTENT_OWNERSHIP",
        ):
            InMemoryResponseLedger.restore(
                (records + (duplicate_owner,), intents, histories)
            )

        second_record = replace(
            records[0],
            record_id="release-record-Q2-second-intent",
            response_intent_id="response-intent-Q2-second",
            dispatch_idempotency_key="dispatch-key-Q2-second",
        )
        second_intent = replace(
            intents[0],
            intent_id="response-intent-Q2-second",
            dispatch_idempotency_key="dispatch-key-Q2-second",
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "OUTPUT_RELEASE_DECISION_(ID_)?ALREADY_OWNED",
        ):
            InMemoryResponseLedger.restore(
                (
                    records + (second_record,),
                    intents + (second_intent,),
                    histories + ((second_intent.intent_id, ()),),
                )
            )

    def test_delivery_receipt_must_bind_the_accepted_provider_message(self) -> None:
        ledger = response_ledger()
        ledger.commit_decision_and_intent(
            release_record=release_record(),
            destination="current-chat",
            dispatch_idempotency_key="dispatch-key-Q2",
        )
        started = observation(
            record_id="dispatch-event-1",
            previous_record_id=None,
            outcome=DispatchObservation.SEND_STARTED,
            timestamp="2026-11-23T10:00:01+08:00",
        )
        accepted = observation(
            record_id="dispatch-event-2",
            previous_record_id=started.record_id,
            outcome=DispatchObservation.ACCEPTED,
            timestamp="2026-11-23T10:00:02+08:00",
            provider_message_id="provider-message-winner",
        )
        ledger.append_observation(started)
        ledger.append_observation(accepted)

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "DELIVERY_RECEIPT_MESSAGE_CONFLICT",
        ):
            ledger.append_observation(
                observation(
                    record_id="dispatch-event-3",
                    previous_record_id=accepted.record_id,
                    outcome=DispatchObservation.DELIVERED,
                    timestamp="2026-11-23T10:00:03+08:00",
                    provider_message_id="provider-message-loser",
                )
            )

    def test_evaluation_precedence_is_fail_then_inconclusive_then_not_run(self) -> None:
        common = dict(
            decision_id="evaluation-day106",
            execution_id="execution-day106",
            external_real_boundary=CapstoneResult.NOT_RUN,
            evidence_level="EXECUTED_LOCAL_RUNTIME",
            production_readiness="MORE_EVIDENCE_NEEDED",
            safe_reason_codes=(),
            evaluated_artifact_digests=(stable_hash("evaluated-artifact"),),
            observed_at=NOW,
        )
        failed = CapstoneComposer.evaluate(
            **common,
            normal_quality=CapstoneResult.FAIL,
            security_defense=CapstoneResult.PASS,
            failure_recovery=CapstoneResult.INCONCLUSIVE,
            evidence_replay=CapstoneResult.NOT_RUN,
            hard_gates=(("unauthorized_prompt_zero", CapstoneResult.PASS),),
        )
        inconclusive = CapstoneComposer.evaluate(
            **common,
            normal_quality=CapstoneResult.PASS,
            security_defense=CapstoneResult.PASS,
            failure_recovery=CapstoneResult.INCONCLUSIVE,
            evidence_replay=CapstoneResult.NOT_RUN,
            hard_gates=(("unauthorized_prompt_zero", CapstoneResult.PASS),),
        )
        not_run = CapstoneComposer.evaluate(
            **common,
            normal_quality=CapstoneResult.PASS,
            security_defense=CapstoneResult.PASS,
            failure_recovery=CapstoneResult.PASS,
            evidence_replay=CapstoneResult.PASS,
            hard_gates=(("unauthorized_prompt_zero", CapstoneResult.NOT_RUN),),
        )

        self.assertEqual(failed.overall_hard_gate, CapstoneResult.FAIL)
        self.assertEqual(
            inconclusive.overall_hard_gate,
            CapstoneResult.INCONCLUSIVE,
        )
        self.assertEqual(not_run.overall_hard_gate, CapstoneResult.NOT_RUN)

    def test_l2_evaluation_cannot_upgrade_external_real_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "external-real PASS"):
            CapstoneEvaluationDecision(
                decision_id="evaluation-day106",
                execution_id="execution-day106",
                normal_quality=CapstoneResult.PASS,
                security_defense=CapstoneResult.PASS,
                failure_recovery=CapstoneResult.PASS,
                evidence_replay=CapstoneResult.PASS,
                external_real_boundary=CapstoneResult.PASS,
                hard_gates=(("unauthorized_prompt_zero", CapstoneResult.PASS),),
                evaluated_artifact_digests=(stable_hash("evaluated-artifact"),),
                overall_hard_gate=CapstoneResult.PASS,
                evidence_level="EXECUTED_LOCAL_RUNTIME",
                production_readiness="MORE_EVIDENCE_NEEDED",
                safe_reason_codes=(),
                observed_at=NOW,
            )

    def test_contract_surface_has_no_protected_payload_fields(self) -> None:
        field_names = {
            item.name
            for contract in (
                SourceToOccurrenceLineage,
                Day101ExecutionReceipt,
                ReleaseCurrentnessSnapshot,
                RetrievalAndContextReceipt,
                AnswerReleaseRecord,
                ResponseIntent,
                RecoveryAndIncidentRecord,
                EndToEndExecutionManifest,
            )
            for item in fields(contract)
        }
        forbidden = {
            "prompt",
            "protected_chunk",
            "answer_text",
            "secret",
            "raw_vector",
            "attack_payload",
        }
        self.assertTrue(field_names.isdisjoint(forbidden))

    def test_lineage_digest_changes_with_exact_content_metadata_or_provenance(
        self,
    ) -> None:
        original = lineage()

        self.assertNotEqual(
            original.digest,
            replace(original, content_digest=stable_hash("new-content")).digest,
        )
        self.assertNotEqual(
            original.digest,
            replace(original, metadata_digest=stable_hash("new-metadata")).digest,
        )
        self.assertNotEqual(
            original.digest,
            replace(original, provenance_revision="PROV-R2").digest,
        )

    def test_execution_seal_rejects_broken_cross_links_and_evaluation_set(
        self,
    ) -> None:
        source_lineage = lineage()
        binding = request_binding()
        receipt = retrieval_receipt(binding)
        release = replace(
            release_record(),
            request_binding_digest=binding.digest,
            retrieval_context_receipt_digest=receipt.digest,
        )
        currentness = currentness_snapshot()
        intent = response_intent(release)
        evaluated = tuple(
            sorted(
                (
                    source_lineage.digest,
                    binding.digest,
                    receipt.digest,
                    release.digest,
                    intent.digest,
                    currentness.digest,
                )
            )
        )
        evaluation = CapstoneComposer.evaluate(
            decision_id="evaluation-seal",
            execution_id="execution-seal",
            normal_quality=CapstoneResult.PASS,
            security_defense=CapstoneResult.PASS,
            failure_recovery=CapstoneResult.PASS,
            evidence_replay=CapstoneResult.NOT_RUN,
            external_real_boundary=CapstoneResult.NOT_RUN,
            hard_gates=(("identity_spine", CapstoneResult.PASS),),
            evaluated_artifact_digests=evaluated,
            evidence_level="EXECUTED_LOCAL_RUNTIME",
            production_readiness="MORE_EVIDENCE_NEEDED",
            safe_reason_codes=(),
            observed_at=NOW,
        )
        manifest = seal_execution(
            execution_id="execution-seal",
            repository_revision="test-revision",
            config_fingerprint=stable_hash("config"),
            runtime_boundary="IN_PROCESS_DETERMINISTIC_ADAPTERS",
            evidence_level="EXECUTED_LOCAL_RUNTIME",
            exact_command="python test",
            started_at=NOW,
            completed_at=NOW,
            lineages=(source_lineage,),
            request_bindings=(binding,),
            retrieval_receipts=(receipt,),
            answer_release_records=(release,),
            response_intents=(intent,),
            recovery_records=(),
            release_currentness_snapshots=(currentness,),
            prerequisite_evidence_digests=(stable_hash("prerequisite"),),
            evaluation=evaluation,
            executed_checks=("identity_spine",),
            not_run=("external-real",),
        )
        self.assertEqual(manifest.evaluation_decision_digest, evaluation.digest)
        self.assertEqual(manifest.lineage_digests, (source_lineage.digest,))
        self.assertEqual(manifest.response_intent_digests, (intent.digest,))

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "SEALED_DECISION_INTENT_BINDING_CONFLICT",
        ):
            seal_execution(
                execution_id="execution-seal",
                repository_revision="test-revision",
                config_fingerprint=stable_hash("config"),
                runtime_boundary="IN_PROCESS_DETERMINISTIC_ADAPTERS",
                evidence_level="EXECUTED_LOCAL_RUNTIME",
                exact_command="python test",
                started_at=NOW,
                completed_at=NOW,
                lineages=(source_lineage,),
                request_bindings=(binding,),
                retrieval_receipts=(receipt,),
                answer_release_records=(release,),
                response_intents=(
                    replace(
                        intent,
                        candidate_digest=stable_hash("foreign-candidate"),
                    ),
                ),
                recovery_records=(),
                release_currentness_snapshots=(currentness,),
                prerequisite_evidence_digests=(stable_hash("prerequisite"),),
                evaluation=evaluation,
                executed_checks=("identity_spine",),
                not_run=("external-real",),
            )

        wrong_dispatch_key = replace(
            observation(
                record_id="sealed-wrong-dispatch-key",
                previous_record_id=None,
                outcome=DispatchObservation.SEND_STARTED,
                timestamp="2026-11-23T10:00:01+08:00",
            ),
            dispatch_idempotency_key="foreign-dispatch-key",
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RECOVERY_DISPATCH_IDEMPOTENCY_KEY_CONFLICT",
        ):
            seal_execution(
                execution_id="execution-seal",
                repository_revision="test-revision",
                config_fingerprint=stable_hash("config"),
                runtime_boundary="IN_PROCESS_DETERMINISTIC_ADAPTERS",
                evidence_level="EXECUTED_LOCAL_RUNTIME",
                exact_command="python test",
                started_at=NOW,
                completed_at=NOW,
                lineages=(source_lineage,),
                request_bindings=(binding,),
                retrieval_receipts=(receipt,),
                answer_release_records=(release,),
                response_intents=(intent,),
                recovery_records=(wrong_dispatch_key,),
                release_currentness_snapshots=(currentness,),
                prerequisite_evidence_digests=(stable_hash("prerequisite"),),
                evaluation=evaluation,
                executed_checks=("identity_spine",),
                not_run=("external-real",),
            )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RECEIPT_REFERENCES_UNKNOWN_REQUEST",
        ):
            seal_execution(
                execution_id="execution-seal",
                repository_revision="test-revision",
                config_fingerprint=stable_hash("config"),
                runtime_boundary="IN_PROCESS_DETERMINISTIC_ADAPTERS",
                evidence_level="EXECUTED_LOCAL_RUNTIME",
                exact_command="python test",
                started_at=NOW,
                completed_at=NOW,
                lineages=(source_lineage,),
                request_bindings=(binding,),
                retrieval_receipts=(
                    replace(receipt, request_binding_digest=stable_hash("unknown")),
                ),
                answer_release_records=(release,),
                response_intents=(intent,),
                recovery_records=(),
                release_currentness_snapshots=(currentness,),
                prerequisite_evidence_digests=(stable_hash("prerequisite"),),
                evaluation=evaluation,
                executed_checks=("identity_spine",),
                not_run=("external-real",),
            )

        other_binding = replace(
            binding,
            request_attempt_id="R2",
            request_id="R2",
            read_view_id="read-view-R2",
            read_view_digest=stable_hash("read-view-R2"),
        )
        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "RELEASE_RECEIPT_REQUEST_BINDING_CONFLICT",
        ):
            seal_execution(
                execution_id="execution-seal",
                repository_revision="test-revision",
                config_fingerprint=stable_hash("config"),
                runtime_boundary="IN_PROCESS_DETERMINISTIC_ADAPTERS",
                evidence_level="EXECUTED_LOCAL_RUNTIME",
                exact_command="python test",
                started_at=NOW,
                completed_at=NOW,
                lineages=(source_lineage,),
                request_bindings=(binding, other_binding),
                retrieval_receipts=(receipt,),
                answer_release_records=(
                    replace(
                        release,
                        request_binding_digest=other_binding.digest,
                    ),
                ),
                response_intents=(intent,),
                recovery_records=(),
                release_currentness_snapshots=(currentness,),
                prerequisite_evidence_digests=(stable_hash("prerequisite"),),
                evaluation=evaluation,
                executed_checks=("identity_spine",),
                not_run=("external-real",),
            )

        with self.assertRaisesRegex(
            CapstoneIdentityConflict,
            "EVALUATION_ARTIFACT_SET_CONFLICT",
        ):
            seal_execution(
                execution_id="execution-seal",
                repository_revision="test-revision",
                config_fingerprint=stable_hash("config"),
                runtime_boundary="IN_PROCESS_DETERMINISTIC_ADAPTERS",
                evidence_level="EXECUTED_LOCAL_RUNTIME",
                exact_command="python test",
                started_at=NOW,
                completed_at=NOW,
                lineages=(source_lineage,),
                request_bindings=(binding,),
                retrieval_receipts=(receipt,),
                answer_release_records=(release,),
                response_intents=(intent,),
                recovery_records=(),
                release_currentness_snapshots=(currentness,),
                prerequisite_evidence_digests=(stable_hash("prerequisite"),),
                evaluation=replace(
                    evaluation,
                    evaluated_artifact_digests=(stable_hash("wrong-set"),),
                ),
                executed_checks=("identity_spine",),
                not_run=("external-real",),
            )


if __name__ == "__main__":
    unittest.main()
