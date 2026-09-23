from __future__ import annotations

import hashlib
import unittest

from rag_ingestion_committer import (
    InMemoryIngestionLifecycleStore,
    IngestionCommitter,
    IngestionIntakeOutcome,
)
from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    SourceArtifactReference,
)


class Day95RAGDocumentIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryIngestionLifecycleStore()
        self.committer = IngestionCommitter(self.store)

    @staticmethod
    def intake(
        *,
        tenant: str = "tenant-a",
        document: str = "report-42",
        version: str = "report-42-v2",
        source_id: str = "source-report-42-v2",
        operation_id: str = "op-ingest-report-42-v2",
        idempotency_key: str = "idem-ingest-report-42-v2",
        content: bytes = b"stable report bytes",
        contract: str = "parser-contract-v1",
    ) -> tuple[
        IngestionOperationIdentity,
        DocumentVersionDefinition,
        SourceArtifactReference,
    ]:
        version_identity = DocumentVersionIdentity(tenant, document, version)
        operation = IngestionOperationIdentity(
            tenant,
            document,
            version,
            source_id,
            operation_id,
            idempotency_key,
        )
        definition = DocumentVersionDefinition(
            version_identity,
            source_id,
            contract,
            operation_id,
        )
        checksum = "sha256:" + hashlib.sha256(content).hexdigest()
        source = SourceArtifactReference(
            version_identity,
            source_id,
            "controlled-ingestion",
            f"{tenant}/{document}/{version}/source",
            f"object-{version}",
            checksum,
            len(content),
            "text/plain",
        )
        return operation, definition, source

    def register(self, **overrides):
        operation, version, source = self.intake(**overrides)
        return self.committer.register_intake(
            operation=operation,
            version=version,
            source=source,
        )

    def test_first_intake_establishes_stable_identity(self) -> None:
        result = self.register()

        self.assertEqual(result.outcome, IngestionIntakeOutcome.CREATED)
        self.assertTrue(result.durable_transition)
        assert result.document is not None
        assert result.version is not None
        assert result.operation is not None
        self.assertEqual(result.document.identity.document_id, "report-42")
        self.assertEqual(
            result.version.definition.identity.document_version_id,
            "report-42-v2",
        )
        self.assertEqual(
            result.operation.identity.operation_id,
            "op-ingest-report-42-v2",
        )

    def test_exact_duplicate_reuses_original_operation_and_version(self) -> None:
        first = self.register()
        duplicate = self.register()

        self.assertEqual(duplicate.outcome, IngestionIntakeOutcome.EXACT_DUPLICATE)
        self.assertFalse(duplicate.durable_transition)
        self.assertEqual(duplicate.operation, first.operation)
        self.assertEqual(duplicate.version, first.version)
        self.assertEqual(duplicate.source, first.source)

    def test_same_operation_with_different_source_identity_is_conflict(self) -> None:
        self.register()
        conflict = self.register(
            source_id="source-report-42-replacement",
            content=b"changed report bytes",
        )

        self.assertEqual(conflict.outcome, IngestionIntakeOutcome.IDENTITY_CONFLICT)
        self.assertFalse(conflict.durable_transition)
        self.assertEqual(
            self.store.read_operation(
                "op-ingest-report-42-v2"
            ).identity.source_artifact_id,
            "source-report-42-v2",
        )

    def test_changed_content_requires_new_immutable_version_and_operation(self) -> None:
        first = self.register()
        changed = self.register(
            version="report-42-v3",
            source_id="source-report-42-v3",
            operation_id="op-ingest-report-42-v3",
            idempotency_key="idem-ingest-report-42-v3",
            content=b"changed report bytes",
        )

        self.assertEqual(
            changed.outcome,
            IngestionIntakeOutcome.NEW_IMMUTABLE_VERSION,
        )
        assert first.version is not None
        assert changed.version is not None
        self.assertNotEqual(
            changed.version.definition.identity.document_version_id,
            first.version.definition.identity.document_version_id,
        )
        self.assertEqual(
            self.store.read_version(first.version.definition.identity),
            first.version,
        )

    def test_same_fingerprint_with_fresh_ids_converges_to_original(self) -> None:
        first = self.register()
        duplicate = self.register(
            version="report-42-v3",
            source_id="source-report-42-v3",
            operation_id="op-ingest-report-42-v3",
            idempotency_key="idem-ingest-report-42-v3",
        )

        self.assertEqual(duplicate.outcome, IngestionIntakeOutcome.EXACT_DUPLICATE)
        self.assertEqual(duplicate.operation, first.operation)
        with self.assertRaises(KeyError):
            self.store.read_operation("op-ingest-report-42-v3")

    def test_contract_change_creates_version_for_same_bytes(self) -> None:
        self.register()
        reparsed = self.register(
            version="report-42-v3",
            source_id="source-report-42-v3",
            operation_id="op-ingest-report-42-v3",
            idempotency_key="idem-ingest-report-42-v3",
            contract="parser-contract-v2",
        )

        self.assertEqual(
            reparsed.outcome,
            IngestionIntakeOutcome.NEW_IMMUTABLE_VERSION,
        )

    def test_equal_bytes_do_not_deduplicate_across_tenant_boundary(self) -> None:
        tenant_a = self.register()
        tenant_b = self.register(
            tenant="tenant-b",
            version="report-42-v2",
            source_id="source-tenant-b-report-42-v2",
            operation_id="op-tenant-b-report-42-v2",
            idempotency_key="idem-tenant-b-report-42-v2",
        )

        self.assertEqual(tenant_a.outcome, IngestionIntakeOutcome.CREATED)
        self.assertEqual(tenant_b.outcome, IngestionIntakeOutcome.CREATED)
        self.assertNotEqual(tenant_a.operation, tenant_b.operation)


if __name__ == "__main__":
    unittest.main()
