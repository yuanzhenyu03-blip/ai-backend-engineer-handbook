"""Controlled restart-aware persistence adapter for the Day94 capstone.

This adapter serializes the existing Day93 ``RetryDispatchRecord``; it does
not introduce another operation model or decide any transition.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp_retry_policy import RetryDispatchRecord, RetryDispatchRecordState


class RestartAwareDispatchJournal:
    """Atomic local-file journal used only for controlled restart evidence."""

    def __init__(self, path: Path) -> None:
        if not path.name:
            raise ValueError("journal path must name a file")
        self._path = path

    def save(self, record: RetryDispatchRecord) -> None:
        payload = {
            "operation_id": record.operation_id,
            "idempotency_key": record.idempotency_key,
            "state": record.state.value,
            "version": record.version,
            "attempt_number": record.attempt_number,
            "protocol_request_id": record.protocol_request_id,
            "tenant_id": record.tenant_id,
            "resource_id": record.resource_id,
            "tool_name": record.tool_name,
            "fence_token": record.fence_token,
            "transport_generation": record.transport_generation,
            "external_object_id": record.external_object_id,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self._path)

    def load(self) -> RetryDispatchRecord:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("dispatch journal must contain an object")
        return RetryDispatchRecord(
            operation_id=str(payload["operation_id"]),
            idempotency_key=str(payload["idempotency_key"]),
            state=RetryDispatchRecordState(str(payload["state"])),
            version=int(payload["version"]),
            attempt_number=int(payload["attempt_number"]),
            protocol_request_id=payload["protocol_request_id"],
            tenant_id=self._optional_string(payload.get("tenant_id")),
            resource_id=self._optional_string(payload.get("resource_id")),
            tool_name=self._optional_string(payload.get("tool_name")),
            fence_token=int(payload["fence_token"]),
            transport_generation=(
                int(payload["transport_generation"])
                if payload.get("transport_generation") is not None
                else None
            ),
            external_object_id=self._optional_string(
                payload.get("external_object_id")
            ),
        )

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("optional journal identity must be a string")
        return value
