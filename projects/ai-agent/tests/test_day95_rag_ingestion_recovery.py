from __future__ import annotations

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
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_ingestion_recovery import (
    AuthoritativeParseEvidence,
    AuthoritativeParseStatus,
    IngestionRecoveryCoordinator,
    IngestionRecoveryOutcome,
    IngestionRecoveryPolicy,
    SequenceAuthoritativeParsedArtifactRegistry,
)
from rag_parser_adapter import (
    ControlledParserAdapter,
    ParserCapability,
)


class Day95RAGIngestionRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = b"# Research\n\nRecovered evidence\n"
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
        self.attempt = ParserAttemptIdentity(
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            attempt_number=2,
            parser_request_id="parse-request-95-2",
            parser_generation=3,
        )
        self.definition = DocumentVersionDefinition(
            identity=self.version_identity,
            source_artifact_id=self.operation.source_artifact_id,
            parse_contract_version="parser-contract-v1",
            created_by_operation_id=self.operation.operation_id,
        )
        checksum = "sha256:" + hashlib.sha256(self.content).hexdigest()
        self.source = SourceArtifactReference(
            version=self.version_identity,
            source_artifact_id=self.operation.source_artifact_id,
            object_bucket="controlled-ingestion",
            object_key="tenant-a/report-42/report-42-v2/source",
            object_version="object-v2",
            checksum_sha256=checksum,
            size_bytes=len(self.content),
            detected_media_type="text/markdown",
        )
        adapter = ControlledParserAdapter(
            ParserCapability(
                parser_name="controlled-text-parser",
                parser_version="1.0.0",
                parse_contract_version="parser-contract-v1",
                parser_generation=3,
                supported_media_types=("text/markdown",),
                maximum_input_bytes=1024,
            )
        )
        pre_crash = adapter.parse(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            attempt=self.attempt,
            source_bytes=self.content,
        )
        assert pre_crash.candidate is not None
        self.candidate = pre_crash.candidate

    def evidence(
        self,
        status: AuthoritativeParseStatus,
    ) -> AuthoritativeParseEvidence:
        return AuthoritativeParseEvidence(
            status=status,
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            attempt_number=self.attempt.attempt_number,
            parser_request_id=self.attempt.parser_request_id,
            parser_generation=self.attempt.parser_generation,
            candidate=(
                self.candidate
                if status is AuthoritativeParseStatus.SUCCEEDED
                else None
            ),
        )

    def store(self) -> InMemoryIngestionLifecycleStore:
        store = InMemoryIngestionLifecycleStore()
        store.register(
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
                self.operation,
                IngestionOperationState.PENDING_RECONCILIATION,
                2,
                2,
                self.attempt,
            ),
        )
        return store

    def coordinator(self, store, registry, maximum_queries=3):
        return IngestionRecoveryCoordinator(
            store=store,
            registry=registry,
            committer=IngestionCommitter(store),
            policy=IngestionRecoveryPolicy(maximum_queries),
        )

    def test_not_found_then_success_never_replays_parser_and_commits_once(self) -> None:
        store = self.store()
        registry = SequenceAuthoritativeParsedArtifactRegistry(
            (
                self.evidence(AuthoritativeParseStatus.NOT_FOUND),
                self.evidence(AuthoritativeParseStatus.SUCCEEDED),
            )
        )
        coordinator = self.coordinator(store, registry)

        first = coordinator.recover(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            query_number=1,
        )
        second = coordinator.recover(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            query_number=2,
        )

        self.assertEqual(first.outcome, IngestionRecoveryOutcome.PENDING_RECONCILIATION)
        self.assertTrue(first.requery_scheduled)
        self.assertEqual(second.outcome, IngestionRecoveryOutcome.SUCCEEDED)
        self.assertEqual(first.parser_calls + second.parser_calls, 0)
        self.assertEqual(
            first.parser_transport_calls + second.parser_transport_calls,
            0,
        )
        self.assertEqual(registry.queries, 2)
        self.assertEqual(second.candidate_validation_calls, 1)
        self.assertEqual(second.committer_calls, 1)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.COMPLETED,
        )
        self.assertEqual(
            store.read_document(self.version_identity.document).active_version_id,
            "report-42-v2",
        )

    def test_unknown_at_query_budget_alerts_without_retry(self) -> None:
        store = self.store()
        registry = SequenceAuthoritativeParsedArtifactRegistry(
            (self.evidence(AuthoritativeParseStatus.UNKNOWN),)
        )

        result = self.coordinator(store, registry, maximum_queries=2).recover(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            query_number=2,
        )

        self.assertEqual(
            result.outcome,
            IngestionRecoveryOutcome.PENDING_RECONCILIATION,
        )
        self.assertFalse(result.requery_scheduled)
        self.assertTrue(result.operator_alert_required)
        self.assertEqual(result.parser_calls, 0)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PENDING_RECONCILIATION,
        )

    def test_authoritative_failure_is_persisted_without_retry(self) -> None:
        store = self.store()
        registry = SequenceAuthoritativeParsedArtifactRegistry(
            (self.evidence(AuthoritativeParseStatus.FAILED),)
        )

        result = self.coordinator(store, registry).recover(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            query_number=1,
        )

        self.assertEqual(result.outcome, IngestionRecoveryOutcome.FAILED_CONFIRMED)
        self.assertEqual(result.parser_calls, 0)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.FAILED,
        )

    def test_not_executed_is_persisted_but_does_not_retry(self) -> None:
        store = self.store()
        registry = SequenceAuthoritativeParsedArtifactRegistry(
            (self.evidence(AuthoritativeParseStatus.NOT_EXECUTED),)
        )

        result = self.coordinator(store, registry).recover(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            query_number=1,
        )

        self.assertEqual(
            result.outcome,
            IngestionRecoveryOutcome.NOT_EXECUTED_CONFIRMED,
        )
        self.assertEqual(result.parser_calls, 0)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PROVEN_NOT_EXECUTED,
        )

    def test_wrong_authoritative_attempt_binding_alerts_and_stays_pending(self) -> None:
        store = self.store()
        evidence = AuthoritativeParseEvidence(
            status=AuthoritativeParseStatus.NOT_FOUND,
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            attempt_number=1,
            parser_request_id="parse-request-95-1",
            parser_generation=3,
        )
        registry = SequenceAuthoritativeParsedArtifactRegistry((evidence,))

        result = self.coordinator(store, registry).recover(
            operation=self.operation,
            version=self.definition,
            source=self.source,
            query_number=1,
        )

        self.assertEqual(
            result.outcome,
            IngestionRecoveryOutcome.AUTHORITY_BINDING_CONFLICT,
        )
        self.assertTrue(result.operator_alert_required)
        self.assertEqual(
            store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PENDING_RECONCILIATION,
        )


if __name__ == "__main__":
    unittest.main()
