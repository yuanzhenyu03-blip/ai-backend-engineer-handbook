from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

from rag_ingestion_contracts import DocumentVersionIdentity
from rag_source_admission import (
    SourceAdmissionGate,
    SourceAdmissionOutcome,
    SourceAdmissionPolicy,
    SourceUploadCandidate,
)


class Day95RAGSourceAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = SourceAdmissionPolicy(
            maximum_size_bytes=256,
            supported_media_types=(
                "text/plain",
                "text/markdown",
                "text/html",
                "application/pdf",
            ),
        )
        self.gate = SourceAdmissionGate(self.policy)
        self.content = b"# Controlled research note\n"

    def candidate(
        self,
        *,
        content: bytes | None = None,
        filename: str = "note.md",
        declared_media_type: str = "text/markdown",
    ) -> SourceUploadCandidate:
        payload = self.content if content is None else content
        checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
        return SourceUploadCandidate(
            version=DocumentVersionIdentity(
                "tenant-a",
                "report-42",
                "report-42-v2",
            ),
            source_artifact_id="source-report-42-v2",
            original_filename=filename,
            declared_media_type=declared_media_type,
            object_bucket="controlled-ingestion",
            object_key="tenant-a/report-42/report-42-v2/source",
            object_version="object-v2",
            expected_size_bytes=len(payload),
            expected_checksum_sha256=checksum,
            content=payload,
        )

    def test_verified_utf8_markdown_is_admitted_without_parser_calls(self) -> None:
        decision = self.gate.evaluate(self.candidate())

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.ADMITTED)
        self.assertIsNotNone(decision.source_artifact)
        assert decision.source_artifact is not None
        self.assertEqual(
            decision.source_artifact.detected_media_type,
            "text/markdown",
        )
        self.assertEqual(decision.parser_calls, 0)
        self.assertEqual(decision.committer_calls, 0)

    def test_filename_path_is_rejected_even_when_content_is_valid(self) -> None:
        decision = self.gate.evaluate(
            self.candidate(filename="../../report.md")
        )

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.UNSAFE_FILENAME)
        self.assertTrue(decision.quarantine_required)
        self.assertIsNone(decision.source_artifact)

    def test_checksum_mismatch_fails_closed(self) -> None:
        candidate = replace(
            self.candidate(),
            expected_checksum_sha256="sha256:wrong",
        )

        decision = self.gate.evaluate(candidate)

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.CHECKSUM_MISMATCH)
        self.assertTrue(decision.quarantine_required)

    def test_oversized_source_is_not_parsed(self) -> None:
        payload = b"a" * 257
        decision = self.gate.evaluate(self.candidate(content=payload))

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.OVERSIZED_SOURCE)
        self.assertEqual(decision.parser_calls, 0)

    def test_pdf_extension_and_mime_cannot_hide_zip_bytes(self) -> None:
        payload = b"PK\x03\x04archive"
        decision = self.gate.evaluate(
            self.candidate(
                content=payload,
                filename="report.pdf",
                declared_media_type="application/pdf",
            )
        )

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.UNSUPPORTED_ARCHIVE)
        self.assertEqual(decision.detected_media_type, "application/zip")
        self.assertTrue(decision.quarantine_required)

    def test_pdf_signature_with_text_mime_is_mismatch(self) -> None:
        payload = b"%PDF-1.7\ncontrolled"
        decision = self.gate.evaluate(
            self.candidate(content=payload, declared_media_type="text/plain")
        )

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.MEDIA_TYPE_MISMATCH)
        self.assertEqual(decision.detected_media_type, "application/pdf")

    def test_encrypted_pdf_is_quarantined(self) -> None:
        payload = b"%PDF-1.7\n/Encrypt controlled"
        decision = self.gate.evaluate(
            self.candidate(
                content=payload,
                filename="encrypted.pdf",
                declared_media_type="application/pdf",
            )
        )

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.ENCRYPTED_DOCUMENT)
        self.assertTrue(decision.quarantine_required)

    def test_html_disguised_as_plain_text_is_rejected(self) -> None:
        payload = b"<html><body>research</body></html>"
        decision = self.gate.evaluate(
            self.candidate(content=payload, declared_media_type="text/plain")
        )

        self.assertEqual(decision.outcome, SourceAdmissionOutcome.MEDIA_TYPE_MISMATCH)
        self.assertEqual(decision.detected_media_type, "text/html")


if __name__ == "__main__":
    unittest.main()
