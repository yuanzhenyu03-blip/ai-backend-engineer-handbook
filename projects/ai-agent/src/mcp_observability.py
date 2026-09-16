"""Credential-safe, non-authoritative Day93 MCP observability primitives."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Mapping

from mcp_remote_lifecycle import FailureEvidence


@dataclass(frozen=True)
class OperationRefEncoder:
    """Create a stable pseudonymous correlation ref using an application key."""

    key: bytes

    def __post_init__(self) -> None:
        if len(self.key) < 16:
            raise ValueError("operation reference key must be at least 16 bytes")

    def encode(self, operation_id: str) -> str:
        if not operation_id:
            raise ValueError("operation_id must not be empty")
        digest = hmac.new(
            self.key,
            operation_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"opref-{digest[:20]}"


@dataclass(frozen=True)
class SafeLifecycleLog:
    event: str
    operation_ref: str
    phase: str
    failure_kind: str
    dispatch_certainty: str
    execution_certainty: str
    attempt_number: int
    transport_generation: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "event": self.event,
                "operation_ref": self.operation_ref,
                "phase": self.phase,
                "failure_kind": self.failure_kind,
                "dispatch_certainty": self.dispatch_certainty,
                "execution_certainty": self.execution_certainty,
                "attempt_number": self.attempt_number,
                "transport_generation": self.transport_generation,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def lifecycle_failure_log(
    evidence: FailureEvidence,
    *,
    encoder: OperationRefEncoder,
    transport_generation: int,
) -> SafeLifecycleLog:
    """Build from typed evidence; raw credentials cannot enter this schema."""

    if transport_generation < 1:
        raise ValueError("transport_generation must be positive")
    return SafeLifecycleLog(
        event="mcp_remote_failure",
        operation_ref=encoder.encode(evidence.operation_id),
        phase=evidence.phase.value,
        failure_kind=evidence.kind.value,
        dispatch_certainty=evidence.dispatch_certainty.value,
        execution_certainty=evidence.execution_certainty.value,
        attempt_number=evidence.attempt_number,
        transport_generation=transport_generation,
    )


class BoundedMetricRecorder:
    """Accept only known low-cardinality metric dimensions."""

    ALLOWED_LABELS = frozenset(
        {
            "phase",
            "failure_kind",
            "dispatch_certainty",
            "execution_certainty",
            "outcome",
            "transport",
        }
    )
    FORBIDDEN_LABELS = frozenset(
        {
            "operation_id",
            "operation_ref",
            "idempotency_key",
            "protocol_request_id",
            "trace_id",
            "tenant_id",
            "resource_id",
            "resource_uri",
            "authorization",
            "token",
        }
    )

    def __init__(self) -> None:
        self._counts: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def increment(self, name: str, labels: Mapping[str, str]) -> None:
        keys = frozenset(label.lower() for label in labels)
        forbidden = keys & self.FORBIDDEN_LABELS
        if forbidden:
            raise ValueError(
                "high-cardinality or sensitive metric labels: "
                + ", ".join(sorted(forbidden))
            )
        unknown = keys - self.ALLOWED_LABELS
        if unknown:
            raise ValueError("unbounded metric labels: " + ", ".join(sorted(unknown)))
        key = (name, tuple(sorted(labels.items())))
        self._counts[key] = self._counts.get(key, 0) + 1

    def value(self, name: str, labels: Mapping[str, str]) -> int:
        return self._counts.get((name, tuple(sorted(labels.items()))), 0)


@dataclass(frozen=True)
class SafeTraceCorrelation:
    """Diagnostic correlation only; never an authorization input."""

    trace_id: str
    operation_ref: str
    transport_generation: int
    authority_evidence: bool = False

    def __post_init__(self) -> None:
        if not self.trace_id or not self.operation_ref:
            raise ValueError("trace correlation must be complete")
        if self.transport_generation < 1:
            raise ValueError("transport_generation must be positive")
        if self.authority_evidence:
            raise ValueError("trace data cannot become authority evidence")
