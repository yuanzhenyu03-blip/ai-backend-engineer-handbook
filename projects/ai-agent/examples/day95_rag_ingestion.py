"""Deterministic Day95 ingestion example; no model or network is used."""

from __future__ import annotations

import hashlib
import json

from rag_document_lifecycle import evaluate_day96_chunking_eligibility
from rag_ingestion_committer import InMemoryIngestionLifecycleStore, IngestionCommitter
from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParserAttemptIdentity,
)
from rag_ingestion_orchestrator import (
    IngestionOrchestrationRequest,
    LocalControlledParserTransport,
    RAGIngestionOrchestrator,
)
from rag_parser_adapter import ControlledParserAdapter, ParserCapability
from rag_source_admission import (
    SourceAdmissionGate,
    SourceAdmissionPolicy,
    SourceUploadCandidate,
)


def run_example() -> dict[str, object]:
    content = b"# Research report\n\nControlled synthetic evidence.\n"
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
    definition = DocumentVersionDefinition(
        version_identity,
        operation.source_artifact_id,
        "parser-contract-v1",
        operation.operation_id,
    )
    checksum = "sha256:" + hashlib.sha256(content).hexdigest()
    admission = SourceAdmissionGate(
        SourceAdmissionPolicy(1024, ("text/markdown",))
    ).evaluate(
        SourceUploadCandidate(
            version_identity,
            operation.source_artifact_id,
            "report-42.md",
            "text/markdown",
            "controlled-ingestion",
            "tenant-a/report-42/report-42-v2/source",
            "object-v2",
            len(content),
            checksum,
            content,
        )
    )
    if admission.source_artifact is None:
        raise RuntimeError(admission.safe_reason)

    store = InMemoryIngestionLifecycleStore()
    committer = IngestionCommitter(store)
    intake = committer.register_intake(
        operation=operation,
        version=definition,
        source=admission.source_artifact,
    )
    if intake.operation is None:
        raise RuntimeError(intake.safe_reason)

    attempt = ParserAttemptIdentity(
        operation.operation_id,
        operation.idempotency_key,
        1,
        "parse-request-95-1",
        3,
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
    result = RAGIngestionOrchestrator(
        store=store,
        adapter=adapter,
        transport=LocalControlledParserTransport(adapter),
        committer=committer,
    ).run(
        IngestionOrchestrationRequest(
            operation=operation,
            version=definition,
            source=admission.source_artifact,
            attempt=attempt,
            source_bytes=content,
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
    document = store.read_document(version_identity.document)
    version = store.read_version(version_identity)
    completed_operation = store.read_operation(operation.operation_id)
    chunking = evaluate_day96_chunking_eligibility(
        document=document,
        version=version,
        operation=completed_operation,
    )
    return {
        "source_admission": admission.outcome.value,
        "intake": intake.outcome.value,
        "ingestion": result.outcome.value,
        "document_state": document.state.value,
        "document_version_state": version.state.value,
        "operation_state": completed_operation.state.value,
        "active_version_id": document.active_version_id,
        "day96_chunking_eligibility": chunking.outcome.value,
        "parser_calls": result.parser_calls,
        "committer_calls": result.committer_calls,
        "durable_transitions": result.durable_transitions + 1,
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
