from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

from rag_ingestion_committer import (
    InMemoryIngestionLifecycleStore,
    IngestionCommitter,
    IngestionOperationState,
)
from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_ingestion_orchestrator import (
    IngestionOrchestrationOutcome,
    IngestionOrchestrationRequest,
    RAGIngestionOrchestrator,
)
from rag_parser_adapter import ControlledParserAdapter, ParserCapability
from rag_parser_process import IndependentParserProcessTransport


class Day95IndependentParserProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"# Independent parser\n\nSynthetic evidence.\n"
        self.version_identity = DocumentVersionIdentity(
            "tenant-a", "report-42", "report-42-v2"
        )
        self.operation = IngestionOperationIdentity(
            "tenant-a",
            "report-42",
            "report-42-v2",
            "source-report-42-v2",
            "op-ingest-report-42-v2",
            "idem-ingest-report-42-v2",
        )
        self.definition = DocumentVersionDefinition(
            self.version_identity,
            self.operation.source_artifact_id,
            "parser-contract-v1",
            self.operation.operation_id,
        )
        checksum = "sha256:" + hashlib.sha256(self.content).hexdigest()
        self.source = SourceArtifactReference(
            self.version_identity,
            self.operation.source_artifact_id,
            "controlled-ingestion",
            "tenant-a/report-42/report-42-v2/source",
            "object-v2",
            checksum,
            len(self.content),
            "text/markdown",
        )
        self.attempt = ParserAttemptIdentity(
            self.operation.operation_id,
            self.operation.idempotency_key,
            1,
            "parse-request-95-1",
            3,
        )
        self.adapter = ControlledParserAdapter(
            ParserCapability(
                "controlled-text-parser",
                "1.0.0",
                "parser-contract-v1",
                3,
                ("text/markdown",),
                1024,
            )
        )
        self.worker_path = (
            Path(__file__).parent / "fixtures" / "day95_parser_worker.py"
        )

    def run_with(self, *, mode: str, timeout: float):
        store = InMemoryIngestionLifecycleStore()
        committer = IngestionCommitter(store)
        intake = committer.register_intake(
            operation=self.operation,
            version=self.definition,
            source=self.source,
        )
        assert intake.operation is not None
        transport = IndependentParserProcessTransport(
            python_executable=sys.executable,
            worker_path=self.worker_path,
            timeout_seconds=timeout,
            worker_mode=mode,
        )
        result = RAGIngestionOrchestrator(
            store=store,
            adapter=self.adapter,
            transport=transport,
            committer=committer,
        ).run(
            IngestionOrchestrationRequest(
                operation=self.operation,
                version=self.definition,
                source=self.source,
                attempt=self.attempt,
                source_bytes=self.content,
                expected_operation_state=intake.operation.state,
                expected_operation_state_version=intake.operation.state_version,
                expected_operation_fence=intake.operation.fence_token,
                current_authorization=True,
                parser_permit_current=True,
                caller_intent_active=True,
                cancelled=False,
                now=100.0,
                deadline=110.0,
                capacity_admitted=True,
                circuit_allows_request=True,
            )
        )
        return result, store

    def test_independent_process_candidate_is_committed(self) -> None:
        result, store = self.run_with(mode="success", timeout=2.0)

        self.assertEqual(result.outcome, IngestionOrchestrationOutcome.SUCCEEDED)
        self.assertEqual(result.parser_transport_calls, 1)
        self.assertEqual(result.parser_calls, 1)
        self.assertEqual(result.committer_calls, 1)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.COMPLETED,
        )

    def test_timeout_after_possible_parse_stays_pending_without_replay(self) -> None:
        result, store = self.run_with(
            mode="hang_after_parse",
            timeout=0.05,
        )

        self.assertEqual(
            result.outcome,
            IngestionOrchestrationOutcome.PENDING_RECONCILIATION,
        )
        self.assertEqual(result.parser_transport_calls, 1)
        self.assertEqual(result.parser_calls, 0)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PENDING_RECONCILIATION,
        )


if __name__ == "__main__":
    unittest.main()
