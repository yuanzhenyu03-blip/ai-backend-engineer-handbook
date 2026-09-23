from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    DocumentVersionLifecycleRecord,
    InMemoryIngestionLifecycleStore,
    IngestionCommitter,
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
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_ingestion_orchestrator import (
    IngestionOrchestrationOutcome,
    IngestionOrchestrationRequest,
    LocalControlledParserTransport,
    ParserOutcomeUnknown,
    RAGIngestionOrchestrator,
)
from rag_parser_adapter import (
    ControlledParserAdapter,
    ParserAdapterOutcome,
    ParserAdapterResult,
    ParserCapability,
)


class _MarkerAssertingTransport:
    def __init__(
        self,
        store: InMemoryIngestionLifecycleStore,
        inner: LocalControlledParserTransport,
    ) -> None:
        self.store = store
        self.inner = inner
        self.calls = 0

    def execute(self, **kwargs) -> ParserAdapterResult:
        self.calls += 1
        operation = kwargs["operation"]
        persisted = self.store.read_operation(operation.operation_id)
        if persisted.state is not IngestionOperationState.PARSE_DISPATCH_STARTED:
            raise AssertionError("parser called before durable dispatch marker")
        return self.inner.execute(**kwargs)


class _UnknownTransport:
    calls = 0

    def execute(self, **kwargs) -> ParserAdapterResult:
        del kwargs
        self.calls += 1
        raise ParserOutcomeUnknown("PARSER_RESPONSE_LOST")


class _WrongVersionCandidateTransport:
    def __init__(self, inner: LocalControlledParserTransport) -> None:
        self.inner = inner

    def execute(self, **kwargs) -> ParserAdapterResult:
        result = self.inner.execute(**kwargs)
        assert result.candidate is not None
        manifest = replace(
            result.candidate.manifest,
            document_version_id="report-42-v1",
        )
        candidate = ParsedDocumentCandidate(
            manifest,
            result.candidate.canonical_text,
            result.candidate.sections,
        )
        return ParserAdapterResult(
            ParserAdapterOutcome.CANDIDATE,
            "CONTROLLED_WRONG_VERSION_CANDIDATE",
            candidate=candidate,
            parser_calls=1,
        )


class Day95RAGIngestionOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"# Research\n\nControlled evidence\n"
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
        checksum = "sha256:" + hashlib.sha256(self.content).hexdigest()
        self.source = SourceArtifactReference(
            version=self.version_identity,
            source_artifact_id=self.operation_identity.source_artifact_id,
            object_bucket="controlled-ingestion",
            object_key="tenant-a/report-42/report-42-v2/source",
            object_version="object-v2",
            checksum_sha256=checksum,
            size_bytes=len(self.content),
            detected_media_type="text/markdown",
        )
        self.adapter = ControlledParserAdapter(
            ParserCapability(
                parser_name="controlled-text-parser",
                parser_version="1.0.0",
                parse_contract_version="parser-contract-v1",
                parser_generation=3,
                supported_media_types=(
                    "text/plain",
                    "text/markdown",
                    "text/html",
                ),
                maximum_input_bytes=1024,
            )
        )
        self.store = InMemoryIngestionLifecycleStore()
        self.store.register(
            document=DocumentHeadSnapshot(
                DocumentIdentity("tenant-a", "report-42"),
                DocumentHeadState.REGISTERED,
                None,
                0,
                0,
            ),
            version=DocumentVersionLifecycleRecord(
                self.definition,
                DocumentVersionLifecycle.REGISTERED,
                None,
                None,
                0,
                0,
            ),
            operation=IngestionOperationRecord(
                self.operation_identity,
                IngestionOperationState.READY_FOR_DISPATCH,
                0,
                0,
                None,
            ),
        )
        self.committer = IngestionCommitter(self.store)

    def request(self, **overrides) -> IngestionOrchestrationRequest:
        values = {
            "operation": self.operation_identity,
            "version": self.definition,
            "source": self.source,
            "attempt": self.attempt,
            "source_bytes": self.content,
            "expected_operation_state": IngestionOperationState.READY_FOR_DISPATCH,
            "expected_operation_state_version": 0,
            "expected_operation_fence": 0,
            "current_authorization": True,
            "parser_permit_current": True,
            "caller_intent_active": True,
            "cancelled": False,
            "now": 10.0,
            "deadline": 20.0,
            "capacity_admitted": True,
            "circuit_allows_request": True,
        }
        values.update(overrides)
        return IngestionOrchestrationRequest(**values)

    def orchestrator(self, transport) -> RAGIngestionOrchestrator:
        return RAGIngestionOrchestrator(
            store=self.store,
            adapter=self.adapter,
            transport=transport,
            committer=self.committer,
        )

    def test_happy_path_persists_marker_before_parser_and_commits_once(self) -> None:
        transport = _MarkerAssertingTransport(
            self.store,
            LocalControlledParserTransport(self.adapter),
        )

        result = self.orchestrator(transport).run(self.request())

        self.assertEqual(result.outcome, IngestionOrchestrationOutcome.SUCCEEDED)
        self.assertEqual(transport.calls, 1)
        self.assertEqual(result.parser_calls, 1)
        self.assertEqual(result.candidate_validation_calls, 1)
        self.assertEqual(result.committer_calls, 1)
        self.assertEqual(result.durable_transitions, 2)
        self.assertIsNotNone(result.verified_observation)
        self.assertEqual(
            self.store.read_operation(self.operation_identity.operation_id).state,
            IngestionOperationState.COMPLETED,
        )

    def test_current_authorization_blocks_before_claim_and_parser(self) -> None:
        transport = _MarkerAssertingTransport(
            self.store,
            LocalControlledParserTransport(self.adapter),
        )

        result = self.orchestrator(transport).run(
            self.request(current_authorization=False)
        )

        self.assertEqual(
            result.outcome,
            IngestionOrchestrationOutcome.PREFLIGHT_BLOCKED,
        )
        self.assertEqual(transport.calls, 0)
        self.assertEqual(
            self.store.read_operation(self.operation_identity.operation_id).state,
            IngestionOperationState.READY_FOR_DISPATCH,
        )

    def test_losing_dispatch_claim_never_calls_parser(self) -> None:
        first_claim = self.store.claim_parse_dispatch(
            identity=self.operation_identity,
            attempt=self.attempt,
            expected_state=IngestionOperationState.READY_FOR_DISPATCH,
            expected_state_version=0,
            expected_fence=0,
        )
        self.assertTrue(first_claim.claimed)
        transport = _MarkerAssertingTransport(
            self.store,
            LocalControlledParserTransport(self.adapter),
        )

        result = self.orchestrator(transport).run(self.request())

        self.assertEqual(
            result.outcome,
            IngestionOrchestrationOutcome.DISPATCH_CLAIM_BLOCKED,
        )
        self.assertEqual(transport.calls, 0)

    def test_response_loss_becomes_pending_without_parser_replay(self) -> None:
        transport = _UnknownTransport()

        result = self.orchestrator(transport).run(self.request())

        self.assertEqual(
            result.outcome,
            IngestionOrchestrationOutcome.PENDING_RECONCILIATION,
        )
        self.assertEqual(transport.calls, 1)
        self.assertEqual(
            self.store.read_operation(self.operation_identity.operation_id).state,
            IngestionOperationState.PENDING_RECONCILIATION,
        )
        document = self.store.read_document(self.version_identity.document)
        self.assertEqual(document.state, DocumentHeadState.REGISTERED)
        self.assertIsNone(document.active_version_id)

    def test_wrong_version_candidate_is_quarantined_before_activation(self) -> None:
        transport = _WrongVersionCandidateTransport(
            LocalControlledParserTransport(self.adapter)
        )

        result = self.orchestrator(transport).run(self.request())

        self.assertEqual(
            result.outcome,
            IngestionOrchestrationOutcome.CANDIDATE_REJECTED,
        )
        self.assertEqual(
            self.store.read_operation(self.operation_identity.operation_id).state,
            IngestionOperationState.QUARANTINED,
        )
        self.assertEqual(
            self.store.read_version(self.version_identity).state,
            DocumentVersionLifecycle.QUARANTINED,
        )
        self.assertIsNone(
            self.store.read_document(self.version_identity.document).active_version_id
        )


if __name__ == "__main__":
    unittest.main()
