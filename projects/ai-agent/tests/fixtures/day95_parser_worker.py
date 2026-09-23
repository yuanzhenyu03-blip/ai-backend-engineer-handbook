"""Synthetic independent parser worker used only by Day95 runtime tests."""

from __future__ import annotations

import base64
from dataclasses import asdict
import json
import sys
import time

from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_parser_adapter import ControlledParserAdapter, ParserCapability


def main() -> None:
    payload = json.load(sys.stdin)
    operation = IngestionOperationIdentity(**payload["operation"])
    version_identity = DocumentVersionIdentity(**payload["version"]["identity"])
    version = DocumentVersionDefinition(
        identity=version_identity,
        source_artifact_id=payload["version"]["source_artifact_id"],
        parse_contract_version=payload["version"]["parse_contract_version"],
        created_by_operation_id=payload["version"]["created_by_operation_id"],
    )
    source = SourceArtifactReference(
        version=DocumentVersionIdentity(**payload["source"]["version"]),
        source_artifact_id=payload["source"]["source_artifact_id"],
        object_bucket=payload["source"]["object_bucket"],
        object_key=payload["source"]["object_key"],
        object_version=payload["source"]["object_version"],
        checksum_sha256=payload["source"]["checksum_sha256"],
        size_bytes=payload["source"]["size_bytes"],
        detected_media_type=payload["source"]["detected_media_type"],
    )
    attempt = ParserAttemptIdentity(**payload["attempt"])
    adapter = ControlledParserAdapter(
        ParserCapability(
            parser_name="controlled-text-parser",
            parser_version="1.0.0",
            parse_contract_version=version.parse_contract_version,
            parser_generation=attempt.parser_generation,
            supported_media_types=("text/plain", "text/markdown", "text/html"),
            maximum_input_bytes=1024 * 1024,
        )
    )
    result = adapter.parse(
        operation=operation,
        version=version,
        source=source,
        attempt=attempt,
        source_bytes=base64.b64decode(payload["source_base64"], validate=True),
    )
    if payload["mode"] == "hang_after_parse":
        time.sleep(5)
    response: dict[str, object] = {
        "outcome": result.outcome.value,
        "safe_reason": result.safe_reason,
        "parser_calls": result.parser_calls,
    }
    if result.candidate is not None:
        response["candidate"] = {
            "manifest": asdict(result.candidate.manifest),
            "canonical_text": result.candidate.canonical_text,
            "sections": result.candidate.sections,
        }
    json.dump(response, sys.stdout)


if __name__ == "__main__":
    main()
