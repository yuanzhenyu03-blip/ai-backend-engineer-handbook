from __future__ import annotations

from dataclasses import replace
import inspect
import unittest

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


class Day95RAGIngestionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version_identity = DocumentVersionIdentity(
            tenant_id="tenant-a",
            document_id="report-42",
            document_version_id="report-42-v2",
        )
        self.operation = IngestionOperationIdentity(
            tenant_id="tenant-a",
            document_id="report-42",
            document_version_id="report-42-v2",
            source_artifact_id="source-report-42-v2",
            operation_id="op-ingest-report-42-v2",
            idempotency_key="idem-ingest-report-42-v2",
        )
        self.version = DocumentVersionDefinition(
            identity=self.version_identity,
            source_artifact_id="source-report-42-v2",
            parse_contract_version="parser-contract-v1",
            created_by_operation_id=self.operation.operation_id,
        )
        self.source = SourceArtifactReference(
            version=self.version_identity,
            source_artifact_id="source-report-42-v2",
            object_bucket="controlled-ingestion",
            object_key="tenant-a/report-42/report-42-v2/source",
            object_version="object-v2",
            checksum_sha256="sha256:source-v2",
            size_bytes=128,
            detected_media_type="application/pdf",
        )
        self.attempt = ParserAttemptIdentity(
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            attempt_number=2,
            parser_request_id="parse-request-95-2",
            parser_generation=3,
        )
        self.text = "Quarterly research evidence"

    def manifest(self) -> ParseManifest:
        return ParseManifest(
            tenant_id=self.operation.tenant_id,
            document_id=self.operation.document_id,
            document_version_id=self.operation.document_version_id,
            source_artifact_id=self.operation.source_artifact_id,
            source_checksum_sha256=self.source.checksum_sha256,
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            parser_name="controlled-pdf-parser",
            parser_version="1.0.0",
            parse_contract_version=self.version.parse_contract_version,
            attempt_number=self.attempt.attempt_number,
            parser_request_id=self.attempt.parser_request_id,
            parser_generation=self.attempt.parser_generation,
            output_checksum_sha256=sha256_text(self.text),
            page_count=1,
            section_count=1,
            record_count=1,
        )

    def candidate(self) -> ParsedDocumentCandidate:
        return ParsedDocumentCandidate(
            manifest=self.manifest(),
            canonical_text=self.text,
            sections=(self.text,),
        )

    def evaluate(self, candidate: ParsedDocumentCandidate):
        return ParsedCandidateValidator().evaluate(
            operation=self.operation,
            version=self.version,
            source=self.source,
            attempt=self.attempt,
            candidate=candidate,
        )

    def test_active_pointer_belongs_to_document_head(self) -> None:
        signature = inspect.signature(DocumentVersionDefinition)
        self.assertNotIn("state", signature.parameters)
        self.assertNotIn("active_version_id", signature.parameters)

        head = DocumentHeadSnapshot(
            identity=DocumentIdentity("tenant-a", "report-42"),
            state=DocumentHeadState.ACTIVE,
            active_version_id="report-42-v2",
            state_version=4,
            fence_token=9,
        )
        self.assertEqual(head.active_version_id, "report-42-v2")

    def test_active_head_without_pointer_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "active version pointer"):
            DocumentHeadSnapshot(
                identity=DocumentIdentity("tenant-a", "report-42"),
                state=DocumentHeadState.ACTIVE,
                active_version_id=None,
                state_version=4,
                fence_token=9,
            )

    def test_valid_candidate_only_produces_non_durable_proposal(self) -> None:
        decision = self.evaluate(self.candidate())

        self.assertEqual(
            decision.outcome,
            CandidateValidationOutcome.READY_FOR_COMMIT,
        )
        self.assertIsNotNone(decision.proposal)
        self.assertEqual(decision.correlation_checks, 1)
        self.assertEqual(decision.manifest_validation_calls, 1)
        self.assertEqual(decision.structural_validation_calls, 1)
        self.assertEqual(decision.output_validation_calls, 1)
        self.assertEqual(decision.committer_calls, 0)
        self.assertEqual(decision.durable_transitions, 0)

    def test_wrong_document_version_stops_at_manifest_binding(self) -> None:
        candidate = self.candidate()
        candidate = replace(
            candidate,
            manifest=replace(
                candidate.manifest,
                document_version_id="report-42-v1",
            ),
        )

        decision = self.evaluate(candidate)

        self.assertEqual(
            decision.outcome,
            CandidateValidationOutcome.MANIFEST_BINDING_CONFLICT,
        )
        self.assertEqual(decision.correlation_checks, 1)
        self.assertEqual(decision.manifest_validation_calls, 1)
        self.assertEqual(decision.structural_validation_calls, 0)
        self.assertEqual(decision.committer_calls, 0)
        self.assertIsNone(decision.proposal)

    def test_late_attempt_stops_at_correlation(self) -> None:
        candidate = self.candidate()
        candidate = replace(
            candidate,
            manifest=replace(
                candidate.manifest,
                attempt_number=1,
                parser_request_id="parse-request-95-1",
            ),
        )

        decision = self.evaluate(candidate)

        self.assertEqual(
            decision.outcome,
            CandidateValidationOutcome.CORRELATION_CONFLICT,
        )
        self.assertEqual(decision.correlation_checks, 1)
        self.assertEqual(decision.manifest_validation_calls, 0)
        self.assertEqual(decision.committer_calls, 0)

    def test_source_checksum_conflict_fails_closed(self) -> None:
        candidate = self.candidate()
        candidate = replace(
            candidate,
            manifest=replace(
                candidate.manifest,
                source_checksum_sha256="sha256:other-source",
            ),
        )

        decision = self.evaluate(candidate)

        self.assertEqual(
            decision.outcome,
            CandidateValidationOutcome.SOURCE_CHECKSUM_CONFLICT,
        )
        self.assertEqual(decision.structural_validation_calls, 0)
        self.assertEqual(decision.committer_calls, 0)

    def test_output_checksum_conflict_is_not_accepted(self) -> None:
        candidate = self.candidate()
        candidate = replace(
            candidate,
            manifest=replace(
                candidate.manifest,
                output_checksum_sha256="sha256:wrong-output",
            ),
        )

        decision = self.evaluate(candidate)

        self.assertEqual(
            decision.outcome,
            CandidateValidationOutcome.OUTPUT_CHECKSUM_CONFLICT,
        )
        self.assertEqual(decision.output_validation_calls, 1)
        self.assertEqual(decision.committer_calls, 0)


if __name__ == "__main__":
    unittest.main()
