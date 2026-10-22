from __future__ import annotations

from dataclasses import replace
import unittest

from examples.day97_authorized_chunk_access import build_fixture
from rag_ingestion_contracts import DocumentIdentity
from rag_provenance import ProvenanceOutcome


class Day97ProvenanceTests(unittest.TestCase):
    def test_current_selected_chunk_set_has_complete_lineage(self) -> None:
        fixture = build_fixture()
        result = fixture.provenance.evaluate(
            document=DocumentIdentity("tenant-a", "report-42")
        )
        self.assertTrue(result.valid, result.safe_reason)
        assert result.binding is not None
        self.assertEqual(result.binding.chunk_set_id, fixture.resource.chunk_set_id)
        self.assertEqual(len(result.records), len(fixture.chunk_ids))

    def test_guessed_or_wrong_selected_set_is_not_current(self) -> None:
        fixture = build_fixture()
        result = fixture.provenance.evaluate(
            document=DocumentIdentity("tenant-a", "report-42"),
            expected_chunk_set_id="chunk-set:guessed",
        )
        self.assertEqual(result.outcome, ProvenanceOutcome.NOT_CURRENT)
        self.assertIsNone(result.chunk_set)

    def test_missing_source_artifact_fails_closed(self) -> None:
        fixture = build_fixture()
        chunk_set = fixture.chunks.read_chunk_set(fixture.resource.chunk_set_id)
        assert chunk_set is not None
        with fixture.day95._lock:
            fixture.day95._source_artifacts.pop(
                chunk_set.operation.source_artifact_id
            )
        result = fixture.provenance.evaluate(
            document=DocumentIdentity("tenant-a", "report-42")
        )
        self.assertEqual(result.outcome, ProvenanceOutcome.LINEAGE_INCOMPLETE)

    def test_parsed_checksum_mismatch_fails_closed(self) -> None:
        fixture = build_fixture()
        chunk_set = fixture.chunks.read_chunk_set(fixture.resource.chunk_set_id)
        assert chunk_set is not None
        parsed_id = chunk_set.operation.parsed_artifact_id
        with fixture.day95._lock:
            parsed = fixture.day95._parsed_artifacts[parsed_id]
            fixture.day95._parsed_artifacts[parsed_id] = replace(
                parsed,
                output_checksum_sha256="sha256:corrupted",
            )
        result = fixture.provenance.evaluate(
            document=DocumentIdentity("tenant-a", "report-42")
        )
        self.assertEqual(result.outcome, ProvenanceOutcome.CHECKSUM_MISMATCH)

    def test_repeated_text_keeps_distinct_occurrences(self) -> None:
        fixture = build_fixture(
            "same text\nsame text",
            soft_target_tokens=2,
            hard_max_tokens=2,
        )
        result = fixture.provenance.evaluate(
            document=DocumentIdentity("tenant-a", "report-42")
        )
        self.assertTrue(result.valid, result.safe_reason)
        by_hash: dict[str, list[object]] = {}
        for record in result.records:
            by_hash.setdefault(record.chunk_content_hash, []).append(record)
        repeated = next(items for items in by_hash.values() if len(items) == 2)
        self.assertNotEqual(repeated[0].chunk_id, repeated[1].chunk_id)
        self.assertNotEqual(
            repeated[0].source_segments,
            repeated[1].source_segments,
        )


if __name__ == "__main__":
    unittest.main()
