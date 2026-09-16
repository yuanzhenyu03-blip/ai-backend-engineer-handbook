"""Generation-scoped Day93 correlation for reconnecting MCP transports."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock


@dataclass(frozen=True)
class RemoteRequestKey:
    transport_generation: int
    protocol_request_id: str | int

    def __post_init__(self) -> None:
        if self.transport_generation < 1:
            raise ValueError("transport_generation must be positive")


@dataclass(frozen=True)
class RemoteRequestBinding:
    key: RemoteRequestKey
    operation_id: str
    idempotency_key: str
    attempt_number: int

    def __post_init__(self) -> None:
        if not self.operation_id or not self.idempotency_key:
            raise ValueError("application identity must be complete")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be positive")


class RemoteResponseCorrelationOutcome(str, Enum):
    MATCHED = "MATCHED"
    STALE_GENERATION = "STALE_GENERATION"
    UNKNOWN_REQUEST = "UNKNOWN_REQUEST"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"


@dataclass(frozen=True)
class RemoteResponseCorrelation:
    outcome: RemoteResponseCorrelationOutcome
    binding: RemoteRequestBinding | None = None
    committer_calls: int = 0
    controlled_service_calls: int = 0


class RemoteCorrelationRegistry:
    """Bind responses to one transport generation and one application attempt."""

    def __init__(self) -> None:
        self._current_generation = 0
        self._bindings: dict[RemoteRequestKey, RemoteRequestBinding] = {}
        self._completed: set[RemoteRequestKey] = set()
        self._lock = Lock()

    @property
    def current_generation(self) -> int:
        with self._lock:
            return self._current_generation

    def begin_generation(self) -> int:
        """Start a fresh transport epoch; old bindings remain audit evidence."""

        with self._lock:
            self._current_generation += 1
            return self._current_generation

    def bind(self, binding: RemoteRequestBinding) -> None:
        with self._lock:
            if binding.key.transport_generation != self._current_generation:
                raise ValueError("request must bind to the current generation")
            if binding.key in self._bindings:
                raise ValueError("request key is already bound")
            self._bindings[binding.key] = binding

    def correlate_response(
        self,
        key: RemoteRequestKey,
    ) -> RemoteResponseCorrelation:
        """Validate correlation only; a separate Committer owns facts."""

        with self._lock:
            if key.transport_generation != self._current_generation:
                return RemoteResponseCorrelation(
                    RemoteResponseCorrelationOutcome.STALE_GENERATION,
                    self._bindings.get(key),
                )
            binding = self._bindings.get(key)
            if binding is None:
                return RemoteResponseCorrelation(
                    RemoteResponseCorrelationOutcome.UNKNOWN_REQUEST
                )
            if key in self._completed:
                return RemoteResponseCorrelation(
                    RemoteResponseCorrelationOutcome.ALREADY_COMPLETED,
                    binding,
                )
            self._completed.add(key)
            return RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                binding,
            )
