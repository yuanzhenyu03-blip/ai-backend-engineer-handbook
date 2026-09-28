"""Synthetic active Day95 fixture shared by Day96 examples and tests."""

from __future__ import annotations

from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    DocumentVersionLifecycleRecord,
    InMemoryIngestionLifecycleStore,
    IngestionActivationGuard,
    IngestionCommitOutcome,
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
    ParseManifest,
    ParsedArtifactDefinition,
    ParsedCandidateValidator,
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
    sha256_text,
)


def active_day95_store(text: str) -> tuple[
    InMemoryIngestionLifecycleStore, ParsedArtifactDefinition
]:
    version_identity = DocumentVersionIdentity(
        "tenant-a", "report-42", "report-42-v2"
    )
    operation = IngestionOperationIdentity(
        "tenant-a",
        "report-42",
        "report-42-v2",
        "source-report-42-v2",
        "op-ingest-report-42-v2",
        "idem-ingest-report-42-v2",
    )
    attempt = ParserAttemptIdentity(
        operation.operation_id,
        operation.idempotency_key,
        1,
        "parser-request-1",
        1,
    )
    definition = DocumentVersionDefinition(
        version_identity,
        operation.source_artifact_id,
        "parser-contract-v1",
        operation.operation_id,
    )
    source = SourceArtifactReference(
        version_identity,
        operation.source_artifact_id,
        "controlled-fixtures",
        "synthetic/report-42-v2",
        "object-v2",
        "sha256:synthetic-source",
        max(len(text.encode("utf-8")), 1),
        "text/markdown",
    )
    manifest = ParseManifest(
        "tenant-a",
        "report-42",
        "report-42-v2",
        source.source_artifact_id,
        source.checksum_sha256,
        operation.operation_id,
        operation.idempotency_key,
        "synthetic-parser",
        "1.0.0",
        "parser-contract-v1",
        1,
        attempt.parser_request_id,
        1,
        sha256_text(text),
        1,
        1,
        1,
    )
    decision = ParsedCandidateValidator().evaluate(
        operation=operation,
        version=definition,
        source=source,
        attempt=attempt,
        candidate=ParsedDocumentCandidate(manifest, text, (text,)),
    )
    if decision.proposal is None:
        raise AssertionError(decision.safe_reason)
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
            definition,
            DocumentVersionLifecycle.REGISTERED,
            None,
            None,
            0,
            0,
        ),
        operation=IngestionOperationRecord(
            operation,
            IngestionOperationState.PARSE_DISPATCH_STARTED,
            1,
            1,
            attempt,
        ),
    )
    with store._lock:
        store._source_artifacts[source.source_artifact_id] = source
    result = IngestionCommitter(store).commit(
        decision,
        guard=IngestionActivationGuard(
            DocumentHeadState.REGISTERED,
            None,
            0,
            0,
            DocumentVersionLifecycle.REGISTERED,
            0,
            0,
            IngestionOperationState.PARSE_DISPATCH_STARTED,
            1,
            1,
        ),
    )
    if result.outcome is not IngestionCommitOutcome.COMMITTED:
        raise AssertionError(result.safe_reason)
    assert result.parsed_artifact is not None
    return store, result.parsed_artifact
