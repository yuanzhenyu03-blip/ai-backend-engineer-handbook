from __future__ import annotations

from dataclasses import replace
import unittest

from rag_document_lifecycle import (
    ChunkingEligibilityOutcome,
    evaluate_day96_chunking_eligibility,
)
from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    DocumentVersionLifecycleRecord,
    IngestionOperationRecord,
    IngestionOperationState,
)
from rag_ingestion_contracts import (
    DocumentHeadSnapshot,
    DocumentHeadState,
    DocumentIdentity,
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParserAttemptIdentity,
)


class Day95RAGDocumentLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        version_identity = DocumentVersionIdentity(
            "tenant-a", "report-42", "report-42-v2"
        )
        operation_identity = IngestionOperationIdentity(
            "tenant-a",
            "report-42",
            "report-42-v2",
            "source-report-42-v2",
            "op-ingest-report-42-v2",
            "idem-ingest-report-42-v2",
        )
        self.document = DocumentHeadSnapshot(
            DocumentIdentity("tenant-a", "report-42"),
            DocumentHeadState.ACTIVE,
            "report-42-v2",
            1,
            1,
        )
        self.version = DocumentVersionLifecycleRecord(
            DocumentVersionDefinition(
                version_identity,
                "source-report-42-v2",
                "parser-contract-v1",
                "op-ingest-report-42-v2",
            ),
            DocumentVersionLifecycle.ACTIVE,
            "parsed-report-42-v2",
            "activate:op-ingest-report-42-v2:1",
            1,
            1,
        )
        self.operation = IngestionOperationRecord(
            operation_identity,
            IngestionOperationState.COMPLETED,
            2,
            2,
            ParserAttemptIdentity(
                "op-ingest-report-42-v2",
                "idem-ingest-report-42-v2",
                2,
                "parse-request-95-2",
                3,
            ),
        )

    def evaluate(self, *, document=None, version=None, operation=None):
        return evaluate_day96_chunking_eligibility(
            document=document or self.document,
            version=version or self.version,
            operation=operation or self.operation,
        )

    def test_only_active_committed_version_is_day96_eligible(self) -> None:
        decision = self.evaluate()

        self.assertTrue(decision.eligible)
        self.assertEqual(
            decision.outcome,
            ChunkingEligibilityOutcome.ELIGIBLE,
        )
        self.assertEqual(decision.parsed_artifact_id, "parsed-report-42-v2")
        self.assertEqual(decision.durable_transitions, 0)

    def test_superseded_version_is_auditable_not_chunking_input(self) -> None:
        superseded = replace(
            self.version,
            state=DocumentVersionLifecycle.SUPERSEDED,
            state_version=2,
            fence_token=2,
        )

        decision = self.evaluate(version=superseded)

        self.assertEqual(
            decision.outcome,
            ChunkingEligibilityOutcome.VERSION_NOT_ACTIVE,
        )
        self.assertEqual(superseded.parsed_artifact_id, "parsed-report-42-v2")

    def test_tombstoned_document_is_not_chunking_input(self) -> None:
        tombstoned_document = replace(
            self.document,
            state=DocumentHeadState.TOMBSTONED,
            active_version_id=None,
        )
        tombstoned_version = replace(
            self.version,
            state=DocumentVersionLifecycle.TOMBSTONED,
        )

        decision = self.evaluate(
            document=tombstoned_document,
            version=tombstoned_version,
        )

        self.assertEqual(
            decision.outcome,
            ChunkingEligibilityOutcome.DOCUMENT_NOT_ACTIVE,
        )
        self.assertEqual(
            tombstoned_version.parsed_artifact_id,
            "parsed-report-42-v2",
        )

    def test_completed_operation_alone_cannot_bypass_active_pointer(self) -> None:
        wrong_pointer = replace(
            self.document,
            active_version_id="report-42-v3",
        )

        decision = self.evaluate(document=wrong_pointer)

        self.assertEqual(
            decision.outcome,
            ChunkingEligibilityOutcome.ACTIVE_POINTER_MISMATCH,
        )


if __name__ == "__main__":
    unittest.main()
