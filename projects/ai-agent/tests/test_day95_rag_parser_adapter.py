from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import unittest

from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_parser_adapter import (
    ControlledParserAdapter,
    ParserAdapterOutcome,
    ParserAdapterResult,
    ParserCapability,
    ParserPreflightOutcome,
)


class Day95RAGParserAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"# Research\r\n\r\nControlled evidence  \r\n"
        self.version_identity = DocumentVersionIdentity(
            "tenant-a",
            "report-42",
            "report-42-v2",
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
            source_artifact_id=self.operation.source_artifact_id,
            parse_contract_version="parser-contract-v1",
            created_by_operation_id=self.operation.operation_id,
        )
        self.attempt = ParserAttemptIdentity(
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            attempt_number=2,
            parser_request_id="parse-request-95-2",
            parser_generation=3,
        )
        self.source = self.source_for(self.content, "text/markdown")
        self.capability = ParserCapability(
            parser_name="controlled-text-parser",
            parser_version="1.0.0",
            parse_contract_version="parser-contract-v1",
            parser_generation=3,
            supported_media_types=("text/plain", "text/markdown", "text/html"),
            maximum_input_bytes=1024,
        )
        self.adapter = ControlledParserAdapter(self.capability)

    def source_for(
        self,
        content: bytes,
        media_type: str,
    ) -> SourceArtifactReference:
        checksum = "sha256:" + hashlib.sha256(content).hexdigest()
        return SourceArtifactReference(
            version=self.version_identity,
            source_artifact_id=self.operation.source_artifact_id,
            object_bucket="controlled-ingestion",
            object_key="tenant-a/report-42/report-42-v2/source",
            object_version="object-v2",
            checksum_sha256=checksum,
            size_bytes=len(content),
            detected_media_type=media_type,
        )

    def parse(self, *, source_bytes: bytes | None = None):
        return self.adapter.parse(
            operation=self.operation,
            version=self.version,
            source=self.source,
            attempt=self.attempt,
            source_bytes=self.content if source_bytes is None else source_bytes,
        )

    def test_markdown_private_output_becomes_application_candidate(self) -> None:
        result = self.parse()

        self.assertEqual(result.outcome, ParserAdapterOutcome.CANDIDATE)
        self.assertIsInstance(result.candidate, ParsedDocumentCandidate)
        assert result.candidate is not None
        self.assertEqual(
            result.candidate.canonical_text,
            "# Research\n\nControlled evidence",
        )
        self.assertEqual(result.candidate.manifest.attempt_number, 2)
        self.assertEqual(result.parser_calls, 1)
        self.assertEqual(result.committer_calls, 0)
        self.assertEqual(result.durable_transitions, 0)

    def test_adapter_public_return_type_contains_no_private_parser_type(self) -> None:
        signature = inspect.signature(ControlledParserAdapter.parse)
        self.assertEqual(signature.return_annotation, "ParserAdapterResult")
        self.assertNotIn("_PrivateParserOutput", ParserAdapterResult.__annotations__)

    def test_stale_parser_generation_stops_before_parser_call(self) -> None:
        attempt = replace(self.attempt, parser_generation=2)

        preflight = self.adapter.preflight(
            operation=self.operation,
            version=self.version,
            source=self.source,
            attempt=attempt,
        )
        result = self.adapter.parse(
            operation=self.operation,
            version=self.version,
            source=self.source,
            attempt=attempt,
            source_bytes=self.content,
        )

        self.assertEqual(
            preflight.outcome,
            ParserPreflightOutcome.GENERATION_MISMATCH,
        )
        self.assertEqual(result.outcome, ParserAdapterOutcome.PREFLIGHT_BLOCKED)
        self.assertEqual(result.parser_calls, 0)

    def test_pdf_is_not_silently_sent_to_text_parser(self) -> None:
        payload = b"%PDF-1.7\ncontrolled"
        source = self.source_for(payload, "application/pdf")

        result = self.adapter.parse(
            operation=self.operation,
            version=self.version,
            source=source,
            attempt=self.attempt,
            source_bytes=payload,
        )

        self.assertEqual(result.outcome, ParserAdapterOutcome.PREFLIGHT_BLOCKED)
        self.assertEqual(result.parser_calls, 0)

    def test_changed_bytes_after_admission_stop_before_parser(self) -> None:
        result = self.parse(source_bytes=b"changed")

        self.assertEqual(result.outcome, ParserAdapterOutcome.SOURCE_BYTES_CHANGED)
        self.assertEqual(result.parser_calls, 0)

    def test_html_parser_private_structure_does_not_escape_adapter(self) -> None:
        payload = (
            b"<html><body><h1>Research</h1>"
            b"<script>steal()</script><p>Evidence</p></body></html>"
        )
        source = self.source_for(payload, "text/html")

        result = self.adapter.parse(
            operation=self.operation,
            version=self.version,
            source=source,
            attempt=self.attempt,
            source_bytes=payload,
        )

        self.assertEqual(result.outcome, ParserAdapterOutcome.CANDIDATE)
        assert result.candidate is not None
        self.assertEqual(result.candidate.canonical_text, "Research\nEvidence")
        self.assertNotIn("steal", result.candidate.canonical_text)


if __name__ == "__main__":
    unittest.main()
