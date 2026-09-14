"""SDK-independent Day91 MCP Server lifecycle and drain state machine."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Protocol


class ServerLifecycleState(str, Enum):
    """Whether the Server may admit work or is shutting down."""

    ACCEPTING = "ACCEPTING"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class RequestAdmissionOutcome(str, Enum):
    """Lifecycle admission result before a handler starts."""

    ADMITTED = "ADMITTED"
    SHUTDOWN_REJECTED = "SHUTDOWN_REJECTED"


class DrainOutcome(str, Enum):
    """Result of the bounded drain phase."""

    CLEAN = "CLEAN"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"


class InFlightCancellationPort(Protocol):
    """Cancel one still-running handler task after drain timeout."""

    def cancel(self, operation_id: str) -> None: ...


class ReconciliationPort(Protocol):
    """Persist outcome-unknown application identity for later repair."""

    def mark_pending(self, operation_id: str) -> None: ...


@dataclass(frozen=True)
class RequestAdmissionDecision:
    outcome: RequestAdmissionOutcome
    operation_id: str


@dataclass(frozen=True)
class DrainReport:
    outcome: DrainOutcome
    pending_operation_ids: tuple[str, ...]


class MCPServerLifecycle:
    """Stop admission first, then drain or reconcile remaining operations."""

    def __init__(
        self,
        cancellation: InFlightCancellationPort,
        reconciliation: ReconciliationPort,
    ) -> None:
        self._cancellation = cancellation
        self._reconciliation = reconciliation
        self._state = ServerLifecycleState.ACCEPTING
        self._in_flight: set[str] = set()
        self._pending_reconciliation: set[str] = set()
        self._lock = Lock()

    @property
    def state(self) -> ServerLifecycleState:
        with self._lock:
            return self._state

    @property
    def in_flight_operation_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._in_flight))

    def begin_request(self, operation_id: str) -> RequestAdmissionDecision:
        """Register identity before handler entry, only while accepting."""

        with self._lock:
            if self._state is not ServerLifecycleState.ACCEPTING:
                return RequestAdmissionDecision(
                    RequestAdmissionOutcome.SHUTDOWN_REJECTED,
                    operation_id,
                )
            if operation_id in self._in_flight:
                raise ValueError("operation is already in flight")
            self._in_flight.add(operation_id)
            return RequestAdmissionDecision(
                RequestAdmissionOutcome.ADMITTED,
                operation_id,
            )

    def complete_request(self, operation_id: str) -> bool:
        """Finish a known in-flight request; never erase reconciliation state."""

        with self._lock:
            if operation_id in self._pending_reconciliation:
                return False
            if operation_id not in self._in_flight:
                return False
            self._in_flight.remove(operation_id)
            return True

    def start_shutdown(self) -> None:
        """Atomically close admission before waiting for current handlers."""

        with self._lock:
            if self._state is ServerLifecycleState.ACCEPTING:
                self._state = ServerLifecycleState.DRAINING

    def finish_clean_drain(self) -> DrainReport:
        """Stop after all admitted handlers have completed."""

        with self._lock:
            if self._state is not ServerLifecycleState.DRAINING:
                raise ValueError("Server is not draining")
            if self._in_flight:
                raise ValueError("cannot finish a clean drain with in-flight work")
            self._state = ServerLifecycleState.STOPPED
            return DrainReport(DrainOutcome.CLEAN, ())

    def expire_drain_timeout(self) -> DrainReport:
        """Cancel remaining tasks and preserve their identities for repair."""

        with self._lock:
            if self._state is not ServerLifecycleState.DRAINING:
                raise ValueError("Server is not draining")
            pending = tuple(sorted(self._in_flight))
            self._pending_reconciliation.update(pending)
            self._state = ServerLifecycleState.STOPPED

        # External ports are called outside the lock.  The identities were
        # already atomically frozen as pending reconciliation above.
        for operation_id in pending:
            self._cancellation.cancel(operation_id)
            self._reconciliation.mark_pending(operation_id)

        outcome = (
            DrainOutcome.PENDING_RECONCILIATION
            if pending
            else DrainOutcome.CLEAN
        )
        return DrainReport(outcome, pending)
