from __future__ import annotations

from dataclasses import replace
import unittest

from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    DocumentVersionLifecycleRecord,
    InMemoryIngestionLifecycleStore,
    IngestionActivationGuard,
    IngestionCommitOutcome,
    IngestionCommitter,
    IngestionOperationRecord,
    IngestionOperationState,
)
from rag_ingestion_contracts import (
    CandidateValidationOutcome,
    DocumentHeadSnapshot,
    DocumentHeadState,
    DocumentIdentity,
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParseManifest,
    ParsedCandidateValidator,
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
    sha256_text,
)


class Day95RAGIngestionCommitterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version_identity = DocumentVersionIdentity(
            "tenant-a",
            "report-42",
            "report-42-v2",
        )
        self.operation_identity = IngestionOperationIdentity(
            tenant_id="tenant-a",
            document_id="report-42",
            document_version_id="report-42-v2",
            source_artifact_id="source-report-42-v2",
            operation_id="op-ingest-report-42-v2",
            idempotency_key="idem-ingest-report-42-v2",
        )
        self.attempt = ParserAttemptIdentity(
            operation_id=self.operation_identity.operation_id,
            idempotency_key=self.operation_identity.idempotency_key,
            attempt_number=2,
            parser_request_id="parse-request-95-2",
            parser_generation=3,
        )
        self.definition = DocumentVersionDefinition(
            identity=self.version_identity,
            source_artifact_id=self.operation_identity.source_artifact_id,
            parse_contract_version="parser-contract-v1",
            created_by_operation_id=self.operation_identity.operation_id,
        )
        self.source = SourceArtifactReference(
            version=self.version_identity,
            source_artifact_id=self.operation_identity.source_artifact_id,
            object_bucket="controlled-ingestion",
            object_key="tenant-a/report-42/report-42-v2/source",
            object_version="object-v2",
            checksum_sha256="sha256:source-v2",
            size_bytes=128,
            detected_media_type="application/pdf",
        )
        self.text = "Quarterly research evidence"
        manifest = ParseManifest(
            tenant_id="tenant-a",
            document_id="report-42",
            document_version_id="report-42-v2",
            source_artifact_id="source-report-42-v2",
            source_checksum_sha256=self.source.checksum_sha256,
            operation_id=self.operation_identity.operation_id,
            idempotency_key=self.operation_identity.idempotency_key,
            parser_name="controlled-pdf-parser",
            parser_version="1.0.0",
            parse_contract_version="parser-contract-v1",
            attempt_number=2,
            parser_request_id="parse-request-95-2",
            parser_generation=3,
            output_checksum_sha256=sha256_text(self.text),
            page_count=1,
            section_count=1,
            record_count=1,
        )
        candidate = ParsedDocumentCandidate(
            manifest,
            self.text,
            (self.text,),
        )
        self.decision = ParsedCandidateValidator().evaluate(
            operation=self.operation_identity,
            version=self.definition,
            source=self.source,
            attempt=self.attempt,
            candidate=candidate,
        )
        self.assertEqual(
            self.decision.outcome,
            CandidateValidationOutcome.READY_FOR_COMMIT,
        )

        self.document = DocumentHeadSnapshot(
            identity=DocumentIdentity("tenant-a", "report-42"),
            state=DocumentHeadState.REGISTERED,
            active_version_id=None,
            state_version=0,
            fence_token=0,
        )
        self.version = DocumentVersionLifecycleRecord(
            definition=self.definition,
            state=DocumentVersionLifecycle.REGISTERED,
            parsed_artifact_id=None,
            activation_commit_id=None,
            state_version=0,
            fence_token=0,
        )
        self.operation = IngestionOperationRecord(
            identity=self.operation_identity,
            state=IngestionOperationState.PARSE_DISPATCH_STARTED,
            state_version=1,
            fence_token=1,
            attempt=self.attempt,
        )
        self.guard = IngestionActivationGuard(
            expected_document_state=DocumentHeadState.REGISTERED,
            expected_active_version_id=None,
            expected_document_state_version=0,
            expected_document_fence=0,
            expected_version_state=DocumentVersionLifecycle.REGISTERED,
            expected_version_state_version=0,
            expected_version_fence=0,
            expected_operation_state=(
                IngestionOperationState.PARSE_DISPATCH_STARTED
            ),
            expected_operation_state_version=1,
            expected_operation_fence=1,
        )
        self.store = InMemoryIngestionLifecycleStore()
        self.store.register(
            document=self.document,
            version=self.version,
            operation=self.operation,
        )
        self.committer = IngestionCommitter(self.store)

    def test_activation_commits_all_facts_and_outbox_once(self) -> None:
        result = self.committer.commit(self.decision, guard=self.guard)

        self.assertEqual(result.outcome, IngestionCommitOutcome.COMMITTED)
        self.assertTrue(result.durable_transition)
        self.assertEqual(result.committer_calls, 1)
        self.assertIsNotNone(result.parsed_artifact)
        assert result.parsed_artifact is not None

        document = self.store.read_document(self.document.identity)
        version = self.store.read_version(self.version_identity)
        operation = self.store.read_operation(
            self.operation_identity.operation_id
        )
        self.assertEqual(document.state, DocumentHeadState.ACTIVE)
        self.assertEqual(document.active_version_id, "report-42-v2")
        self.assertEqual(version.state, DocumentVersionLifecycle.ACTIVE)
        self.assertEqual(
            version.parsed_artifact_id,
            result.parsed_artifact.parsed_artifact_id,
        )
        self.assertEqual(operation.state, IngestionOperationState.COMPLETED)
        self.assertIsNotNone(
            self.store.read_parsed_artifact(
                result.parsed_artifact.parsed_artifact_id
            )
        )
        self.assertEqual(len(self.store.outbox_intents()), 1)

    def test_stale_document_fence_publishes_nothing(self) -> None:
        stale_guard = replace(self.guard, expected_document_fence=99)

        result = self.committer.commit(self.decision, guard=stale_guard)

        self.assertEqual(result.outcome, IngestionCommitOutcome.DOCUMENT_STALE)
        self.assertFalse(result.durable_transition)
        assert self.decision.proposal is not None
        artifact_id = self.decision.proposal.parsed_artifact.parsed_artifact_id
        self.assertIsNone(self.store.read_parsed_artifact(artifact_id))
        self.assertEqual(
            self.store.read_document(self.document.identity),
            self.document,
        )
        self.assertEqual(
            self.store.read_version(self.version_identity),
            self.version,
        )
        self.assertEqual(
            self.store.read_operation(self.operation_identity.operation_id),
            self.operation,
        )
        self.assertEqual(self.store.outbox_intents(), ())

    def test_duplicate_commit_is_idempotent_and_emits_no_second_event(self) -> None:
        first = self.committer.commit(self.decision, guard=self.guard)
        second = self.committer.commit(self.decision, guard=self.guard)

        self.assertEqual(first.outcome, IngestionCommitOutcome.COMMITTED)
        self.assertEqual(
            second.outcome,
            IngestionCommitOutcome.ALREADY_COMMITTED,
        )
        self.assertFalse(second.durable_transition)
        self.assertEqual(len(self.store.outbox_intents()), 1)

    def test_non_ready_candidate_cannot_call_durable_transition(self) -> None:
        bad_candidate = replace(
            self.decision.proposal.parsed_artifact.manifest,
            document_version_id="report-42-v1",
        )
        candidate = ParsedDocumentCandidate(
            bad_candidate,
            self.text,
            (self.text,),
        )
        rejected = ParsedCandidateValidator().evaluate(
            operation=self.operation_identity,
            version=self.definition,
            source=self.source,
            attempt=self.attempt,
            candidate=candidate,
        )

        result = self.committer.commit(rejected, guard=self.guard)

        self.assertEqual(result.outcome, IngestionCommitOutcome.NOT_READY)
        self.assertFalse(result.durable_transition)
        self.assertEqual(self.store.outbox_intents(), ())

    def test_quarantine_blocks_version_without_deleting_source_evidence(self) -> None:
        result = self.committer.mark_quarantined(
            identity=self.operation_identity,
            expected_state_version=1,
            expected_fence=1,
        )

        self.assertTrue(result.durable_transition)
        self.assertEqual(
            self.store.read_operation(self.operation_identity.operation_id).state,
            IngestionOperationState.QUARANTINED,
        )
        self.assertEqual(
            self.store.read_version(self.version_identity).state,
            DocumentVersionLifecycle.QUARANTINED,
        )

    def test_tombstone_retains_parsed_artifact(self) -> None:
        activated = self.committer.commit(self.decision, guard=self.guard)
        assert activated.parsed_artifact is not None
        active_document = self.store.read_document(self.document.identity)

        result = self.committer.tombstone_document(
            identity=self.document.identity,
            expected_document_state=DocumentHeadState.ACTIVE,
            expected_document_state_version=active_document.state_version,
            expected_document_fence=active_document.fence_token,
        )

        self.assertEqual(result.outcome, IngestionCommitOutcome.COMMITTED)
        assert result.document is not None
        assert result.version is not None
        self.assertEqual(result.document.state, DocumentHeadState.TOMBSTONED)
        self.assertIsNone(result.document.active_version_id)
        self.assertEqual(
            result.version.state,
            DocumentVersionLifecycle.TOMBSTONED,
        )
        self.assertIsNotNone(
            self.store.read_parsed_artifact(
                activated.parsed_artifact.parsed_artifact_id
            )
        )

    def test_stale_tombstone_guard_changes_nothing(self) -> None:
        activated = self.committer.commit(self.decision, guard=self.guard)
        assert activated.parsed_artifact is not None
        before = self.store.read_document(self.document.identity)

        result = self.committer.tombstone_document(
            identity=self.document.identity,
            expected_document_state=DocumentHeadState.ACTIVE,
            expected_document_state_version=before.state_version,
            expected_document_fence=99,
        )

        self.assertEqual(result.outcome, IngestionCommitOutcome.DOCUMENT_STALE)
        self.assertEqual(self.store.read_document(self.document.identity), before)
        self.assertIsNotNone(
            self.store.read_parsed_artifact(
                activated.parsed_artifact.parsed_artifact_id
            )
        )


if __name__ == "__main__":
    unittest.main()
