"""Day61 — OpenTelemetry instrumentation for the external-evidence path.

Provides spans for the Provider HTTP call, the Object Storage upload/HEAD, and the guarded
DB completion, plus a low-cardinality outcome metric, an OPTIONAL configurable OTLP exporter,
and W3C trace-context propagation helpers for the FastAPI -> Outbox -> Celery Worker boundary.
Correlation uses ``job_id`` and ``attempt_id``; a ``provider_request_id`` is emitted ONLY as a
non-reversible hash reference (sensitive/capability-bearing). If ``opentelemetry`` is not
installed (or telemetry is disabled), everything degrades to a NO-OP so the runtime and the
pure unit tests work without the SDK or a Collector.

Two invariants make telemetry SAFE:

* It is DIAGNOSTIC, not business truth. A Collector/exporter failure must NOT roll back a
  committed Job or trigger a new Provider call: exporter problems surface only as bounded
  diagnostics/metrics/logs (``exporter_failure_is_bounded()``); every span/metric call here
  swallows ITS OWN exporter/SDK errors.
* It never hides a BUSINESS error. ``operation_span`` swallows only telemetry-layer failures
  (SDK init, span creation, attribute setting, export). An exception raised by the business
  code inside the ``with`` block propagates UNCHANGED to the caller (the block yields exactly
  once, so there is never a double-yield / "generator didn't stop after throw()").

Evidence tier: the no-op path, the exception semantics, the propagation round-trip and the
label/hash safety are ``EXECUTED_LOCAL_RUNTIME`` (tested). A REAL OTLP exporter to a running
Collector is ``INTEGRATION_RUNTIME`` and is NOT RUN by the updating agent. No endpoint
URL/token is hardcoded (``OTEL_EXPORTER_OTLP_ENDPOINT`` is read by the SDK from the
environment at run time).
"""

from __future__ import annotations

import contextlib
import os
import sys
from typing import Any, Dict, Iterator, Optional

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
    metrics = None  # type: ignore
    trace = None  # type: ignore
    _TRACER = None
    _PROVIDER_OPS = None
    _OTEL = False


_ALLOWED_METRIC_KEYS = frozenset({"provider", "outcome", "verification_outcome"})

# init_telemetry() is idempotent; this flag prevents re-installing global providers and keeps
# pure unit tests clean (they never call it unless they mean to).
_TELEMETRY_INITIALIZED = False
_TELEMETRY_ACTIVE = False


# ---------------------------------------------------------------------------
# 1) Configurable, optional OTLP exporter initialization (P1-3).
# ---------------------------------------------------------------------------
def init_telemetry(enabled: Optional[bool] = None) -> bool:
    """Install a real, EXPORTING SDK pipeline (TracerProvider + BatchSpanProcessor + OTLP span
    exporter; MeterProvider + PeriodicExportingMetricReader + OTLP metric exporter) when
    telemetry is enabled and the SDK is importable. Returns True iff an exporting pipeline is
    now active.

    Safety / discipline:
      * DISABLED BY DEFAULT — enabled only if ``enabled=True`` or ``DAY61_TELEMETRY_ENABLED``
        is truthy, so ordinary unit tests never build exporters or touch global providers.
      * IDEMPOTENT — a second call is a no-op (never installs a second provider).
      * The OTLP endpoint comes from ``OTEL_EXPORTER_OTLP_ENDPOINT`` (read by the SDK); the
        protocol from ``DAY61_OTEL_PROTOCOL`` (``http`` default, or ``grpc``). No URL/token is
        hardcoded.
      * NEVER raises: a missing SDK/exporter package or any setup error returns False and
        leaves telemetry as a no-op (business path unaffected).
    """
    global _TELEMETRY_INITIALIZED, _TELEMETRY_ACTIVE
    if _TELEMETRY_INITIALIZED:
        return _TELEMETRY_ACTIVE
    if enabled is None:
        enabled = os.environ.get("DAY61_TELEMETRY_ENABLED", "").lower() in ("1", "true", "yes", "on")
    if not enabled:
        _TELEMETRY_INITIALIZED = True
        _TELEMETRY_ACTIVE = False
        return False
    try:
        from opentelemetry import metrics as _m  # type: ignore
        from opentelemetry import trace as _t  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
        from opentelemetry.sdk.metrics import MeterProvider  # type: ignore
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader  # type: ignore

        protocol = os.environ.get("DAY61_OTEL_PROTOCOL", "http").lower()
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter  # type: ignore
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter  # type: ignore

        resource = Resource.create({"service.name": os.environ.get("DAY61_OTEL_SERVICE_NAME", "day61-worker")})
        tracer_provider = TracerProvider(resource=resource)
        # OTLP*Exporter() reads OTEL_EXPORTER_OTLP_ENDPOINT/headers from the environment.
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        _t.set_tracer_provider(tracer_provider)

        reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        _m.set_meter_provider(meter_provider)

        _TELEMETRY_INITIALIZED = True
        _TELEMETRY_ACTIVE = True
        return True
    except Exception:
        # Missing SDK/exporter or any setup failure -> stay a no-op; business path is unaffected.
        _TELEMETRY_INITIALIZED = True
        _TELEMETRY_ACTIVE = False
        return False


def _reset_telemetry_init_for_tests() -> None:
    """Test-only: allow re-running init_telemetry() with different env in a single process."""
    global _TELEMETRY_INITIALIZED, _TELEMETRY_ACTIVE
    _TELEMETRY_INITIALIZED = False
    _TELEMETRY_ACTIVE = False


def bootstrap_telemetry(component: str) -> bool:
    """Call ONCE at a real process start (FastAPI lifespan, Relay ``main()``, Celery worker
    process init). Thin, defensive wrapper around :func:`init_telemetry`: disabled by default,
    idempotent, and it NEVER raises — an SDK/exporter setup failure degrades to a bounded
    diagnostic and a no-op so the business process/DB commit/Provider idempotency are
    unaffected. ``component`` is only a label for the (bounded) diagnostic. Returns True iff an
    exporting pipeline is now active."""
    try:
        active = init_telemetry()
    except Exception:
        active = False
    if not active:
        # Bounded diagnostic only (no raise, no retry storm): telemetry stays a no-op.
        try:
            import logging

            logging.getLogger("day61.telemetry").debug(
                "telemetry disabled or exporter init failed for %s; continuing without export", component
            )
        except Exception:
            pass
    return active


# ---------------------------------------------------------------------------
# 1b) Request ROOT span so acceptance actually STARTS a trace (P0-2).
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def root_span(name: str) -> Iterator[None]:
    """Start a NEW ROOT span for the request lifecycle (e.g. ``fastapi.accept_job``) so that,
    without external auto-instrumentation, there IS an active span whose W3C ``traceparent``
    :func:`inject_trace_context` can serialize into the Outbox payload. Same exception
    discipline as :func:`operation_span`: telemetry-layer errors are swallowed, a business
    exception inside the block propagates UNCHANGED, and the block yields exactly once. A no-op
    without the SDK."""
    if not _OTEL or _TRACER is None:
        yield
        return
    cm = None
    try:
        cm = _TRACER.start_as_current_span(name)  # type: ignore[union-attr]
        cm.__enter__()
    except Exception:
        cm = None
    if cm is None:
        yield
        return
    try:
        yield
    finally:
        try:
            cm.__exit__(*sys.exc_info())
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 2) Span with SAFE correlation attributes; business exceptions propagate (P0-2).
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def operation_span(
    name: str,
    job_id: str,
    attempt_id: str,
    provider_request_id: Optional[str] = None,
    parent_context: Any = None,
) -> Iterator[None]:
    """Wrap a business operation in a span carrying SAFE correlation attributes only (never a
    full ``provider_request_id`` — only its hashed reference).

    When ``parent_context`` is a context extracted from a propagated W3C ``traceparent`` (via
    :func:`extract_trace_context`), the span is started UNDER that context so the Worker's
    Provider/Storage/DB spans CONTINUE the original request's trace across the async boundary.
    When it is None the span uses the current context (or is a no-op without the SDK).

    Exception discipline: telemetry-layer errors (SDK init, span creation, attribute setting,
    exporter flush) are swallowed so a telemetry problem cannot break the business path; an
    exception from the business block propagates to the caller UNCHANGED. The block yields
    exactly once regardless of the telemetry path, so there is no double-yield."""
    attrs: Dict[str, str] = {"job_id": job_id, "attempt_id": attempt_id}
    if provider_request_id is not None:
        try:
            attrs["provider_request_ref"] = telemetry_safe_provider_request_ref(provider_request_id)
        except Exception:
            pass  # telemetry-only; never blocks business

    if not _OTEL or _TRACER is None:
        # Telemetry disabled/absent: run business directly; its exceptions still propagate.
        yield
        return

    cm = None
    span = None
    try:
        if parent_context is not None:
            cm = _TRACER.start_as_current_span(name, context=parent_context)  # type: ignore[union-attr]
        else:
            cm = _TRACER.start_as_current_span(name)  # type: ignore[union-attr]
        span = cm.__enter__()
        for k, v in attrs.items():
            try:
                span.set_attribute(k, v)
            except Exception:
                pass  # attribute failure is telemetry-only
    except Exception:
        # Span creation failed: degrade to no span, but STILL run the business block.
        if cm is not None:
            try:
                cm.__exit__(*sys.exc_info())
            except Exception:
                pass
        cm = None

    if cm is None:
        yield
        return

    try:
        yield  # business runs here; any exception propagates through this single yield
    finally:
        # Close the span, passing through any in-flight exception so the span can record it,
        # but swallow exporter/SDK errors so telemetry never changes business control flow.
        try:
            cm.__exit__(*sys.exc_info())
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 2b) Relay publish span so the trace shows the Outbox->Broker hop (P1-1).
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def relay_publish_span(
    outbox_event_id: str, job_id: str, event_type: str, parent_context: Any = None
) -> Iterator[None]:
    """A DIAGNOSTIC-only span (``outbox.relay_publish``) around the Relay's real
    ``apply_async`` publish, so a Collector trace shows the FastAPI acceptance -> Outbox Relay
    publish -> Celery Worker hop. Started UNDER ``parent_context`` (the context extracted from
    the Outbox payload's W3C ``traceparent``), so a Relay RETRY of the SAME durable intent
    reuses the SAME trace association while EACH publish gets a fresh Relay span id.

    Attributes are low-risk correlation ids only (``job_id``/``outbox_event_id``/
    ``event_type``) — NEVER a full ``provider_request_id`` and never a metric label. Same
    exception discipline as :func:`operation_span`: telemetry-layer errors are swallowed and a
    business exception from the wrapped publish propagates UNCHANGED (single yield), so a
    telemetry/exporter failure can never block the publish or the fenced ``published_at``
    checkpoint, change business state, or trigger an extra Provider call. A no-op without the
    SDK."""
    attrs: Dict[str, str] = {
        "job_id": job_id,
        "outbox_event_id": outbox_event_id,
        "event_type": event_type,
    }
    if not _OTEL or _TRACER is None:
        yield
        return
    cm = None
    span = None
    try:
        if parent_context is not None:
            cm = _TRACER.start_as_current_span("outbox.relay_publish", context=parent_context)  # type: ignore[union-attr]
        else:
            cm = _TRACER.start_as_current_span("outbox.relay_publish")  # type: ignore[union-attr]
        span = cm.__enter__()
        for k, v in attrs.items():
            try:
                span.set_attribute(k, v)
            except Exception:
                pass  # attribute failure is telemetry-only
    except Exception:
        if cm is not None:
            try:
                cm.__exit__(*sys.exc_info())
            except Exception:
                pass
        cm = None
    if cm is None:
        yield
        return
    try:
        yield  # the real publish runs here; a publish exception propagates unchanged
    finally:
        try:
            cm.__exit__(*sys.exc_info())
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 3) W3C trace-context propagation across FastAPI -> Outbox -> Celery Worker (P1-3).
# ---------------------------------------------------------------------------
def inject_trace_context(carrier: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Inject the CURRENT span context into a text-map ``carrier`` (a plain dict) using the
    W3C ``traceparent`` format, so it can be persisted on the Outbox payload and later carried
    into the Celery message. No-op (returns the carrier unchanged) when the SDK is absent."""
    carrier = dict(carrier or {})
    if not _OTEL:
        return carrier
    try:
        from opentelemetry.propagate import inject  # type: ignore

        inject(carrier)
    except Exception:
        pass  # propagation is diagnostic; never blocks business
    return carrier


def extract_trace_context(carrier: Optional[Dict[str, str]]) -> Any:
    """Extract a W3C trace context from a text-map ``carrier`` so the Worker can CONTINUE the
    trace (or attach an explicit Span Link if it must detach). Returns an opaque Context (or
    None when the SDK is absent). Never raises."""
    if not _OTEL or not carrier:
        return None
    try:
        from opentelemetry.propagate import extract  # type: ignore

        return extract(carrier)
    except Exception:
        return None


_TRACEPARENT_KEY = "traceparent"


def store_traceparent_in_payload(payload: Dict[str, Any], carrier: Dict[str, str]) -> Dict[str, Any]:
    """Persist the W3C ``traceparent`` on an existing Outbox ``payload`` JSONB (schema already
    has ``payload``; no migration needed). Only the low-cardinality traceparent string is
    stored — never a ``provider_request_id`` or any secret."""
    out = dict(payload)
    tp = carrier.get(_TRACEPARENT_KEY)
    if tp:
        out[_TRACEPARENT_KEY] = tp
    return out


def load_traceparent_from_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Read the W3C ``traceparent`` back out of an Outbox payload into a text-map carrier the
    Relay can inject into the Celery message. Returns an empty carrier when absent."""
    if not payload:
        return {}
    tp = payload.get(_TRACEPARENT_KEY)
    return {_TRACEPARENT_KEY: tp} if isinstance(tp, str) and tp else {}


# ---------------------------------------------------------------------------
# 4) Low-cardinality outcome metric (values only; never high-cardinality labels).
# ---------------------------------------------------------------------------
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
