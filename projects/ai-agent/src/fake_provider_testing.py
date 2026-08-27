"""Day77 deterministic Fake Provider and regression-evidence helpers.

The helpers in this module make Provider timing, responses, failures, and call
evidence controllable without a real SDK, network, Provider, database, queue,
Worker, tool, or billing system.

Two boundaries are intentionally separate:

* ``ControlledFakeTransport`` sits behind a real Day72 Adapter so shared
  Contract Tests exercise Provider-specific translation.
* ``BehaviorGolden`` is an independently-authored expectation.  The Runtime
  produces a ``BehaviorObservation``; production code never generates or
  auto-accepts its own golden result.

The independent call log stores only allowlisted identity/evidence fields.  It
does not retain raw prompts, Provider payloads, SDK error messages, secrets, or
credentials.  Independence is in-process only: it models evidence surviving a
simulated Worker object loss, not a real process crash or durable service.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple


class FakeClock:
    """Explicit integer-millisecond clock for deterministic deadline tests."""

    def __init__(self, initial_ms: int = 0) -> None:
        if initial_ms < 0:
            raise ValueError("initial_ms must be non-negative")
        self._now_ms = initial_ms
        self._lock = threading.RLock()

    def now_ms(self) -> int:
        with self._lock:
            return self._now_ms

    def advance_ms(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("FakeClock cannot move backwards")
        with self._lock:
            self._now_ms += amount
            return self._now_ms


@dataclass(frozen=True)
class ProviderCallEvidence:
    """Minimized evidence for one attempted Provider-boundary send."""

    sequence: int
    provider_label: str
    model: str
    correlation_id: str


class IndependentProviderCallLog:
    """Thread-safe, append-only in-process call evidence.

    The log is injected separately from a simulated Worker or Adapter object,
    so deleting those objects does not delete the recorded send evidence.
    """

    def __init__(self) -> None:
        self._records: list[ProviderCallEvidence] = []
        self._lock = threading.RLock()

    def record(
        self,
        *,
        provider_label: str,
        wire_request: Mapping[str, object],
    ) -> ProviderCallEvidence:
        model = wire_request.get("model", wire_request.get("modelId", ""))
        correlation = wire_request.get(
            "trace", wire_request.get("correlationId", "")
        )
        with self._lock:
            evidence = ProviderCallEvidence(
                sequence=len(self._records) + 1,
                provider_label=provider_label,
                model=model if isinstance(model, str) else "",
                correlation_id=(
                    correlation if isinstance(correlation, str) else ""
                ),
            )
            self._records.append(evidence)
        return evidence

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def records(self) -> Tuple[ProviderCallEvidence, ...]:
        with self._lock:
            return tuple(self._records)


@dataclass(frozen=True)
class ScriptedExchange:
    """Exactly one Provider-specific response or exception."""

    response: Optional[Mapping[str, object]] = None
    error: Optional[BaseException] = None

    def __post_init__(self) -> None:
        if self.response is not None and self.error is not None:
            raise ValueError("a scripted exchange cannot contain both response and error")


class ControlledFakeTransport:
    """Deterministic Provider-side transport double behind a real Adapter.

    Every call is recorded before the response gate.  ``request_received``
    lets a test prove that the Provider boundary saw a send.  When
    ``auto_release`` is false, the test controls ``release_response`` to open
    the exact timeout/Worker-loss/late-result window without a behavioral
    sleep.  The bounded wait is only a deadlock guard for a broken test.
    """

    def __init__(
        self,
        *,
        provider_label: str,
        exchanges: Tuple[ScriptedExchange, ...],
        call_log: Optional[IndependentProviderCallLog] = None,
        auto_release: bool = True,
        deadlock_guard_seconds: float = 5.0,
    ) -> None:
        if not exchanges:
            raise ValueError("at least one scripted exchange is required")
        if deadlock_guard_seconds <= 0:
            raise ValueError("deadlock_guard_seconds must be positive")
        self._provider_label = provider_label
        self._exchanges = exchanges
        self._call_log = call_log or IndependentProviderCallLog()
        self._deadlock_guard_seconds = deadlock_guard_seconds
        self._next_exchange = 0
        self._lock = threading.RLock()
        self.request_received = threading.Event()
        self.release_response = threading.Event()
        if auto_release:
            self.release_response.set()

    @property
    def call_log(self) -> IndependentProviderCallLog:
        return self._call_log

    @property
    def call_count(self) -> int:
        return self._call_log.count

    def send(self, wire_request: Mapping[str, object]) -> Mapping[str, object]:
        with self._lock:
            if self._next_exchange >= len(self._exchanges):
                raise AssertionError("Fake Provider received an unscripted extra call")
            exchange = self._exchanges[self._next_exchange]
            self._next_exchange += 1
            self._call_log.record(
                provider_label=self._provider_label,
                wire_request=wire_request,
            )
            self.request_received.set()

        if not self.release_response.wait(self._deadlock_guard_seconds):
            raise RuntimeError("controlled Fake Provider response was not released")
        if exchange.error is not None:
            raise exchange.error
        return dict(exchange.response or {})


@dataclass(frozen=True)
class BehaviorGolden:
    """Independent, versioned semantic expectation for one regression case."""

    case_id: str
    contract_revision: str
    policy_revision: str
    provider_outcome: str
    recovery_action: str
    job_status: str
    provider_call_count: int
    tool_effect_count: int
    new_attempt_created: bool
    cost_status: str


@dataclass(frozen=True)
class BehaviorObservation:
    """Actual facts observed after exercising real Runtime seams."""

    provider_outcome: str
    recovery_action: str
    job_status: str
    provider_call_count: int
    tool_effect_count: int
    new_attempt_created: bool
    cost_status: str


def golden_mismatches(
    golden: BehaviorGolden,
    actual: BehaviorObservation,
) -> Tuple[str, ...]:
    """Return stable field names whose actual behavior differs from golden."""

    checks = (
        ("provider_outcome", golden.provider_outcome, actual.provider_outcome),
        ("recovery_action", golden.recovery_action, actual.recovery_action),
        ("job_status", golden.job_status, actual.job_status),
        (
            "provider_call_count",
            golden.provider_call_count,
            actual.provider_call_count,
        ),
        ("tool_effect_count", golden.tool_effect_count, actual.tool_effect_count),
        (
            "new_attempt_created",
            golden.new_attempt_created,
            actual.new_attempt_created,
        ),
        ("cost_status", golden.cost_status, actual.cost_status),
    )
    return tuple(name for name, expected, observed in checks if expected != observed)
