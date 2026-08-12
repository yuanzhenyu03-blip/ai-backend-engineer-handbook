"""Day61 — minimal OpenTelemetry instrumentation for the external-evidence path.

Provides spans for the Provider HTTP call, the Object Storage upload/HEAD, and the guarded
DB completion, plus a low-cardinality outcome metric. Correlation uses ``job_id`` and
``attempt_id``; a ``provider_request_id`` is emitted ONLY as a non-reversible hash reference
(sensitive/capability-bearing). If ``opentelemetry`` is not installed, everything degrades to
a NO-OP so the runtime and tests work without the SDK.

Telemetry is DIAGNOSTIC, not business truth. A Collector/exporter failure must NOT roll back
a committed Job or trigger a new Provider call: exporter problems surface only as bounded
diagnostics/metrics/logs (``exporter_failure_is_bounded()``), and every span/metric call here
swallows its own exporter errors.

Evidence tier: the no-op path + the label/hash safety are ``EXECUTED_LOCAL_RUNTIME`` (tested).
A REAL OTLP exporter to a running Collector is ``INTEGRATION_RUNTIME`` and is NOT RUN by the
updating agent. No endpoint URL/token is hardcoded (``OTEL_EXPORTER_OTLP_ENDPOINT`` is read by
the SDK from the environment at run time).
"""

from __future__ import annotations

import contextlib
from typing import Iterator, Optional

from day61_provider_artifact_logic import metric_labels_allowed, telemetry_safe_provider_request_ref

try:  # real SDK if present; otherwise a strict no-op
    from opentelemetry import metrics, trace  # type: ignore

    _TRACER = trace.get_tracer("day61")
    _METER = metrics.get_meter("day61")
    _PROVIDER_OPS = _METER.create_counter(
        "day61_provider_operations_total",
        description="Provider operations by provider/outcome/verification_outcome (low cardinality).",
    )
    _OTEL = True
except Exception:  # pragma: no cover - exercised when the SDK is absent
    _TRACER = None
    _PROVIDER_OPS = None
    _OTEL = False


_ALLOWED_METRIC_KEYS = frozenset({"provider", "outcome", "verification_outcome"})


@contextlib.contextmanager
def operation_span(
    name: str, job_id: str, attempt_id: str, provider_request_id: Optional[str] = None
) -> Iterator[None]:
    """A span carrying safe correlation attributes only. NEVER attaches a full
    ``provider_request_id`` — only its hashed reference. Exporter errors are swallowed so a
    telemetry problem cannot break the business path."""
    attrs = {"job_id": job_id, "attempt_id": attempt_id}
    if provider_request_id is not None:
        attrs["provider_request_ref"] = telemetry_safe_provider_request_ref(provider_request_id)
    if not _OTEL:
        yield
        return
    try:
        with _TRACER.start_as_current_span(name) as span:  # type: ignore[union-attr]
            for k, v in attrs.items():
                span.set_attribute(k, v)
            yield
    except Exception:
        # Telemetry must not fail the business operation.
        yield


def record_provider_outcome(provider: str, outcome: str, verification_outcome: str) -> bool:
    """Emit the outcome counter with ONLY low-cardinality labels
    (provider/outcome/verification_outcome). Rejects any high-cardinality label
    (job_id/attempt_id/provider_request_id). Returns False if the labels are unsafe or the
    export failed, but NEVER raises."""
    labels = {"provider": provider, "outcome": outcome, "verification_outcome": verification_outcome}
    if not metric_labels_allowed(labels) or any(k not in _ALLOWED_METRIC_KEYS for k in labels):
        return False
    if not _OTEL:
        return True
    try:
        _PROVIDER_OPS.add(1, labels)  # type: ignore[union-attr]
        return True
    except Exception:
        return False


def exporter_failure_is_bounded() -> bool:
    """A Collector/exporter outage yields bounded diagnostics only; business evidence is
    reconstructable from PostgreSQL + Object Storage + the Provider ledger. It never rolls
    back a committed Job or triggers a duplicate Provider request."""
    return True
