from __future__ import annotations

import unittest

from examples.day95_rag_ingestion import run_example


class Day95RAGIngestionExampleTests(unittest.TestCase):
    def test_deterministic_example_reaches_only_verified_day96_boundary(self) -> None:
        result = run_example()

        self.assertEqual(result["source_admission"], "ADMITTED")
        self.assertEqual(result["intake"], "CREATED")
        self.assertEqual(result["ingestion"], "SUCCEEDED")
        self.assertEqual(result["document_state"], "ACTIVE")
        self.assertEqual(result["document_version_state"], "ACTIVE")
        self.assertEqual(result["operation_state"], "COMPLETED")
        self.assertEqual(result["day96_chunking_eligibility"], "ELIGIBLE")
        self.assertEqual(result["parser_calls"], 1)
        self.assertEqual(result["committer_calls"], 1)


if __name__ == "__main__":
    unittest.main()
