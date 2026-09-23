"""Independent-process transport for the controlled Day95 parser Adapter."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess

from rag_ingestion_contracts import (
    DocumentVersionDefinition,
    IngestionOperationIdentity,
    ParseManifest,
    ParsedDocumentCandidate,
    ParserAttemptIdentity,
    SourceArtifactReference,
)
from rag_ingestion_orchestrator import ParserOutcomeUnknown
from rag_parser_adapter import ParserAdapterOutcome, ParserAdapterResult


class IndependentParserProcessTransport:
    """Run a synthetic parser worker without granting it durable authority."""

    def __init__(
        self,
        *,
        python_executable: str,
        worker_path: Path,
        timeout_seconds: float,
        maximum_response_bytes: int = 1_000_000,
        worker_mode: str = "success",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("parser process timeout must be positive")
        if maximum_response_bytes <= 0:
            raise ValueError("parser response budget must be positive")
        if worker_mode not in {"success", "hang_after_parse"}:
            raise ValueError("unsupported controlled parser worker mode")
        self._python_executable = python_executable
        self._worker_path = worker_path
        self._timeout_seconds = timeout_seconds
        self._maximum_response_bytes = maximum_response_bytes
        self._worker_mode = worker_mode

    def execute(
        self,
        *,
        operation: IngestionOperationIdentity,
        version: DocumentVersionDefinition,
        source: SourceArtifactReference,
        attempt: ParserAttemptIdentity,
        source_bytes: bytes,
    ) -> ParserAdapterResult:
        payload = {
            "mode": self._worker_mode,
            "operation": operation.__dict__,
            "version": {
                "identity": version.identity.__dict__,
                "source_artifact_id": version.source_artifact_id,
                "parse_contract_version": version.parse_contract_version,
                "created_by_operation_id": version.created_by_operation_id,
            },
            "source": {
                "version": source.version.__dict__,
                "source_artifact_id": source.source_artifact_id,
                "object_bucket": source.object_bucket,
                "object_key": source.object_key,
                "object_version": source.object_version,
                "checksum_sha256": source.checksum_sha256,
                "size_bytes": source.size_bytes,
                "detected_media_type": source.detected_media_type,
            },
            "attempt": attempt.__dict__,
            "source_base64": base64.b64encode(source_bytes).decode("ascii"),
        }
        try:
            completed = subprocess.run(
                [self._python_executable, str(self._worker_path)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ParserOutcomeUnknown(
                "INDEPENDENT_PARSER_RESPONSE_TIMEOUT",
            ) from exc
        if completed.returncode != 0:
            return ParserAdapterResult(
                ParserAdapterOutcome.PARSER_FAILED,
                "INDEPENDENT_PARSER_PROCESS_FAILED",
                parser_calls=1,
            )
        encoded = completed.stdout.encode("utf-8")
        if len(encoded) > self._maximum_response_bytes:
            return ParserAdapterResult(
                ParserAdapterOutcome.PARSER_FAILED,
                "INDEPENDENT_PARSER_RESPONSE_EXCEEDS_BUDGET",
                parser_calls=1,
            )
        try:
            result = json.loads(completed.stdout)
            outcome = ParserAdapterOutcome(result["outcome"])
            if outcome is not ParserAdapterOutcome.CANDIDATE:
                return ParserAdapterResult(
                    outcome,
                    str(result["safe_reason"]),
                    parser_calls=int(result["parser_calls"]),
                )
            manifest_payload = result["candidate"]["manifest"]
            manifest = ParseManifest(
                **{
                    **manifest_payload,
                    "warnings": tuple(manifest_payload.get("warnings", ())),
                    "errors": tuple(manifest_payload.get("errors", ())),
                }
            )
            candidate = ParsedDocumentCandidate(
                manifest=manifest,
                canonical_text=str(result["candidate"]["canonical_text"]),
                sections=tuple(result["candidate"]["sections"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return ParserAdapterResult(
                ParserAdapterOutcome.PARSER_FAILED,
                "INDEPENDENT_PARSER_RESPONSE_INVALID",
                parser_calls=1,
            )
        return ParserAdapterResult(
            ParserAdapterOutcome.CANDIDATE,
            "INDEPENDENT_PARSER_RETURNED_APPLICATION_CANDIDATE",
            candidate=candidate,
            parser_calls=int(result["parser_calls"]),
        )
