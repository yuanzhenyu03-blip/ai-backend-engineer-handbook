"""Day58 — Production AI API Capstone, Observability and English Interview.

Phase 4 capstone. Day43-Day56 built the FastAPI AI Job backend and its durable/recovery rules;
Day57 tested those rules under deterministic failures. Day58 makes the distributed execution
EXPLAINABLE and AUDITABLE: events correlate across API -> Outbox Relay -> Worker Attempt -> Provider
Adapter -> completion/reconciliation, metrics detect fleet trends, traces show causal paths — while
PostgreSQL remains the source of business truth.

CORE PRINCIPLE (kept everywhere):
    Observability is a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable
    state. It does NOT replace the durable state machine and does NOT grant permission to retry
    unknown external work. Missing telemetry is an observability GAP, never proof of no execution.

WHAT THIS MODULE PROVIDES (in-process deterministic model):
  * IdentityLifecycle          — a durable Worker Attempt context (job_id / correlation_id STABLE;
                                 attempt_id + trace_id per Attempt). An HTTP request is a SEPARATE
                                 `HttpRequestContext` (job_id / correlation_id + a per-request
                                 request_id + a per-request trace_id; NO attempt_id).
  * StructuredEvent + emit_*   — safe structured events (event_name, job_id, correlation_id,
                                 attempt_id, trace_id, provider, model, outcome, bounded duration,
                                 request-id presence, dispatch-marker presence). NEVER raw
                                 prompts/responses/keys/secrets.
  * MetricRegistry             — Counter / Gauge / Histogram with a LOW-CARDINALITY label contract
                                 that REJECTS job_id / attempt_id / trace_id as labels.
  * TraceModel / SpanLink      — separate async traces; a Provider Adapter call is a child span of the
                                 current Attempt trace; later async work uses a Span Link to the
                                 immediate preceding causal trace (not fake synchronous nesting).
  * TelemetryPipeline          — exporter-failure policy: never turn an accepted Job into FAILED, keep
                                 core processing, bounded buffering/degradation, expose health metrics.
  * observability rollback drill — roll back the bad observability release/config, never DB facts;
                                 bound the affected set by release + window; mark telemetry gaps; a
                                 marker-backed PENDING_RECONCILIATION Job stays reconciliation-only.

EVIDENCE TIERS (reused from Day57): CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME /
PRODUCTION. This module + its tests are EXECUTED_LOCAL_RUNTIME (in-process deterministic doubles).
Real FastAPI runtime, a real OpenTelemetry exporter, real PostgreSQL/Redis/Celery integration, and
real Provider traffic are NOT RUN here (see VALIDATION_MATRIX_DAY58 / day58_not_run_claims).

SECURITY: no secrets, no raw prompts, no raw Provider responses, no tenant documents. Events carry
only safe identifiers and bounded, low-cardinality fields.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Reuse Day57's evidence taxonomy (four tiers) and Day56's execution-certainty vocabulary.
from day57_testing_harness import EvidenceTier, MatrixRow, RunStatus
from day56_provider_resilience import ExecutionCertainty, can_ordinary_retry


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ===========================================================================
# 1. Identity + lifecycle contract (five distinct identities)
# ===========================================================================
@dataclass
class IdentityLifecycle:
    """A durable WORKER ATTEMPT context — one concrete execution attempt. `job_id` and
    `correlation_id` are STABLE across retries (business continuity); a new durable Attempt gets a NEW
    `attempt_id` and normally a NEW `trace_id`. This is NOT an HTTP request: it has no `request_id`.
    An inbound HTTP request is a separate `HttpRequestContext` (see `http_request()` /
    `start_http_request`)."""
    job_id: str                       # durable business identity (stable)
    correlation_id: str               # stable business-chain association (stable)
    attempt_id: str                   # one concrete Worker execution attempt (per Attempt)
    trace_id: str                     # one distributed execution trace (per Attempt, normally)

    def new_attempt(self) -> "IdentityLifecycle":
        """A new durable Attempt: job_id + correlation_id STAY; a new attempt_id and (normally) a new
        trace_id are minted. An Attempt is not an HTTP request."""
        return IdentityLifecycle(job_id=self.job_id, correlation_id=self.correlation_id,
                                 attempt_id=_new_id("att"), trace_id=_new_id("trace"))

    def http_request(self, *, parent_trace: "Optional[SpanContext]" = None) -> "HttpRequestContext":
        """An inbound HTTP request against THIS Job (e.g. a status/poll). It shares job_id +
        correlation_id but gets a NEW request_id and a NEW trace_id, and carries NO attempt_id — it
        does NOT masquerade as this (or any) Worker Attempt. To legitimately continue a distributed
        trace, pass an explicit `parent_trace` (traceparent); an old Worker trace is NEVER silently
        reused."""
        return HttpRequestContext(job_id=self.job_id, correlation_id=self.correlation_id,
                                  request_id=_new_id("req"), trace_id=_new_id("trace"),
                                  parent_trace=parent_trace)


@dataclass
class HttpRequestContext:
    """ONE inbound HTTP request against a Job (e.g. a status/poll). `job_id` + `correlation_id` bridge
    business continuity; `request_id` and `trace_id` are per-request. It has NO `attempt_id` — an HTTP
    request is not a durable Worker execution. `parent_trace`, when present, is an EXPLICIT traceparent
    to link to (never a silent reuse of an old Worker trace)."""
    job_id: str
    correlation_id: str
    request_id: str
    trace_id: str
    parent_trace: "Optional[SpanContext]" = None


def start_job_chain(job_id: Optional[str] = None) -> IdentityLifecycle:
    """Start a Worker Attempt context (the first durable Attempt of a Job)."""
    job_id = job_id or _new_id("job")
    return IdentityLifecycle(job_id=job_id, correlation_id=_new_id("cor"),
                             attempt_id=_new_id("att"), trace_id=_new_id("trace"))


def start_http_request(job_id: Optional[str] = None, correlation_id: Optional[str] = None, *,
                       parent_trace: "Optional[SpanContext]" = None) -> "HttpRequestContext":
    """Start an inbound HTTP request context (e.g. a status/poll for an existing Job). A fresh
    request_id and trace_id are minted; there is NO attempt_id."""
    return HttpRequestContext(job_id=job_id or _new_id("job"),
                              correlation_id=correlation_id or _new_id("cor"),
                              request_id=_new_id("req"), trace_id=_new_id("trace"),
                              parent_trace=parent_trace)


# ===========================================================================
# 2. Structured event contract (safe fields only)
# ===========================================================================
# Fields that may NEVER be logged/exported (tenant data / secrets).
FORBIDDEN_EVENT_FIELDS = frozenset(
    {"prompt", "raw_prompt", "provider_response", "raw_response", "api_key", "secret",
     "authorization", "document", "tenant_document", "messages", "completion_text"}
)
# Safe fields that MAY appear on a structured event.
SAFE_EVENT_FIELDS = frozenset(
    {"event_name", "job_id", "correlation_id", "attempt_id", "trace_id", "provider", "model",
     "outcome", "duration_ms", "request_id_present", "dispatch_marker_present", "reason"}
)
# CANONICAL fields are the event's own declared fields; `extra` may NEVER shadow them (that would
# corrupt audit correlation). Legitimate extension keys must be added deliberately to the allowlist
# below (empty by default), so `extra` can only ever carry EXPLICITLY-allowed safe extension fields.
CANONICAL_EVENT_FIELDS = frozenset(SAFE_EVENT_FIELDS)
SAFE_EXTENSION_FIELDS = frozenset()

# --- Canonical VALUE contracts: safety cannot rely on the caller's discipline, so every canonical
# value is type/length/format/allowlist-checked. `reason` is a finite enum (never free text like a
# raw prompt). Bounded shapes + allowlists also reject secret-like / payload values. ---
EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(\.[a-z0-9_]+)*$")   # e.g. provider.call.timeout
ID_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,127}$")  # ids: bounded, no spaces/newlines
MAX_EVENT_NAME_LEN = 64
MAX_DURATION_MS = 24 * 60 * 60 * 1000                                 # 24h upper bound (bounded)
ALLOWED_EVENT_REASONS = frozenset({"prior_attempt_may_have_executed"})  # finite enum, NOT free text
# Reject obvious secret / bearer / key material appearing in ANY canonical string value.
_SECRETISH = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|BEGIN [A-Z ]*PRIVATE KEY|bearer\s+\S|authorization|password\s*[:=]|\bxox[bp]-)",
    re.IGNORECASE)


def _reject_if_secretish(field: str, value: str) -> None:
    if "\n" in value or "\r" in value:
        raise UnsafeTelemetryError(f"canonical field {field!r} must not contain newlines")
    if _SECRETISH.search(value):
        raise UnsafeTelemetryError(f"canonical field {field!r} looks like a secret/credential/payload")


class UnsafeTelemetryError(ValueError):
    """Raised when a structured event would carry a forbidden raw/secret field."""


@dataclass
class StructuredEvent:
    event_name: str
    job_id: str
    correlation_id: str
    attempt_id: str
    trace_id: str
    provider: Optional[str] = None
    model: Optional[str] = None
    outcome: Optional[str] = None
    duration_ms: Optional[int] = None
    request_id_present: bool = False        # PRESENCE only, never the raw request id value in metrics
    dispatch_marker_present: bool = False
    reason: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        bad = set(self.extra) & FORBIDDEN_EVENT_FIELDS
        if bad:
            raise UnsafeTelemetryError(f"forbidden raw/secret fields in event: {sorted(bad)}")
        # `extra` may NOT override any canonical event field (event_name, ids, provider/model/outcome,
        # duration, reason, presence flags) — that would break audit correlation.
        collide = set(self.extra) & CANONICAL_EVENT_FIELDS
        if collide:
            raise UnsafeTelemetryError(f"extra may not override canonical event fields: {sorted(collide)}")
        # Anything else must be an EXPLICITLY-allowed safe extension key.
        unknown = set(self.extra) - SAFE_EXTENSION_FIELDS
        if unknown:
            raise UnsafeTelemetryError(f"extra may only contain explicitly-allowed safe extension fields: {sorted(unknown)}")
        self._validate_canonical_values()

    def _validate_canonical_values(self) -> None:
        """Validate every CANONICAL field's VALUE (type / length / format / controlled set). Safety
        must NOT rely on the caller choosing not to pass a raw prompt or secret."""
        # event_name: bounded lowercase dotted shape.
        if not (isinstance(self.event_name, str) and len(self.event_name) <= MAX_EVENT_NAME_LEN
                and EVENT_NAME_PATTERN.match(self.event_name)):
            raise UnsafeTelemetryError(f"invalid event_name {self.event_name!r}")
        # ids: bounded, no spaces/newlines, not secret-like.
        for name in ("job_id", "correlation_id", "attempt_id", "trace_id"):
            v = getattr(self, name)
            if not (isinstance(v, str) and ID_VALUE_PATTERN.match(v)):
                raise UnsafeTelemetryError(f"invalid {name} value (bounded id required): {v!r}")
            _reject_if_secretish(name, v)
        # provider / model / outcome: from the controlled allowlists (values, not free text).
        if self.provider is not None:
            _reject_if_secretish("provider", str(self.provider))
            if self.provider not in ALLOWED_PROVIDER_VALUES:
                raise UnsafeTelemetryError(f"provider {self.provider!r} is not in the controlled allowlist")
        if self.model is not None:
            _reject_if_secretish("model", str(self.model))
            if self.model not in ALLOWED_MODEL_VALUES and self.model != MODEL_OTHER_BUCKET:
                raise UnsafeTelemetryError(
                    f"model {self.model!r} is not in the controlled registry (normalize via normalize_model_label)")
        if self.outcome is not None and self.outcome not in ALLOWED_OUTCOME_VALUES:
            raise UnsafeTelemetryError(f"outcome {self.outcome!r} is not in the controlled allowlist")
        # duration_ms: non-negative bounded int.
        if self.duration_ms is not None:
            if not isinstance(self.duration_ms, int) or isinstance(self.duration_ms, bool) \
                    or not (0 <= self.duration_ms <= MAX_DURATION_MS):
                raise UnsafeTelemetryError(f"duration_ms must be an int in [0, {MAX_DURATION_MS}]: {self.duration_ms!r}")
        # reason: a FINITE enum, never free text (a raw prompt would be rejected here).
        if self.reason is not None and self.reason not in ALLOWED_EVENT_REASONS:
            raise UnsafeTelemetryError(
                f"reason must be one of the finite allowlist {sorted(ALLOWED_EVENT_REASONS)}, not free text")
        # presence flags: STRICT bool (never a string / 0 / 1 / None / other truthy-falsy value), so
        # the emitted structured log preserves exact audit semantics.
        for name in ("request_id_present", "dispatch_marker_present"):
            v = getattr(self, name)
            if type(v) is not bool:
                raise UnsafeTelemetryError(f"{name} must be a strict bool (True/False), got {type(v).__name__}")

    def to_safe_dict(self) -> dict:
        d = {"event_name": self.event_name, "job_id": self.job_id,
             "correlation_id": self.correlation_id, "attempt_id": self.attempt_id,
             "trace_id": self.trace_id}
        for k in ("provider", "model", "outcome", "duration_ms", "reason"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        d["request_id_present"] = self.request_id_present
        d["dispatch_marker_present"] = self.dispatch_marker_present
        # `extra` is validated to be disjoint from canonical fields, so it can never overwrite a
        # canonical id/name; add only the (allowlisted) extension keys.
        for k, v in self.extra.items():
            if k not in d:
                d[k] = v
        return d


def emit_provider_call_timeout(ident: IdentityLifecycle, *, provider: str, model: str,
                               duration_ms: int, dispatch_marker_present: bool) -> StructuredEvent:
    """`provider.call.timeout` = the application's OBSERVED timeout/unknown outcome. It is NOT proof
    the Provider did not execute."""
    return StructuredEvent(event_name="provider.call.timeout", job_id=ident.job_id,
                           correlation_id=ident.correlation_id, attempt_id=ident.attempt_id,
                           trace_id=ident.trace_id, provider=provider, model=model,
                           outcome="timeout", duration_ms=duration_ms,
                           request_id_present=False,   # a Worker Attempt event is not an HTTP request
                           dispatch_marker_present=dispatch_marker_present)


def emit_provider_call_suppressed(ident: IdentityLifecycle, *, provider: str,
                                  model: str) -> StructuredEvent:
    """`provider.call.suppressed` = a later reconciliation Attempt refused to call the Provider
    because prior durable evidence forbids it. Reason is `prior_attempt_may_have_executed`."""
    return StructuredEvent(event_name="provider.call.suppressed", job_id=ident.job_id,
                           correlation_id=ident.correlation_id, attempt_id=ident.attempt_id,
                           trace_id=ident.trace_id, provider=provider, model=model,
                           outcome="suppressed", dispatch_marker_present=True,
                           reason="prior_attempt_may_have_executed")


# ===========================================================================
# 3. Metric contract + low-cardinality label validation
# ===========================================================================
class MetricType(str, Enum):
    COUNTER = "counter"        # cumulative; query its RATE, not the raw total
    GAUGE = "gauge"            # current value; rises and falls
    HISTOGRAM = "histogram"    # distribution / tail latency, not just an average


# Labels that would explode cardinality — they belong in logs/traces, never on a metric.
HIGH_CARDINALITY_LABELS = frozenset({"job_id", "attempt_id", "trace_id", "request_id", "correlation_id"})

# Low cardinality depends on label NAMES *and* VALUES: even provider/model/outcome must come from
# controlled config, not unbounded user input. These allowlists/shape rules are illustrative
# controlled configuration (NOT credentials or a vendor policy) and bound the value space.
ALLOWED_PROVIDER_VALUES = frozenset({"openai", "anthropic", "azure_openai", "fake"})
ALLOWED_OUTCOME_VALUES = frozenset(
    {"ok", "timeout", "rate_limited", "server_error", "suppressed", "invalid", "cancelled",
     "definitely_not_accepted", "may_have_executed", "unknown"})
# `model` must come from a FINITE controlled registry (a configuration snapshot), not merely match a
# regex — an unbounded number of regex-valid model strings would still explode cardinality. Unknown /
# user-supplied model aliases are normalized to a single bounded bucket via `normalize_model_label`.
# These are illustrative controlled config values, NOT credentials or account data.
ALLOWED_MODEL_VALUES = frozenset(
    {"gpt-x", "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3", "o4-mini",
     "claude-3-5-sonnet", "claude-3-5-haiku", "fake-model"})
MODEL_OTHER_BUCKET = "__other__"                                # bounded bucket for unknown models
MODEL_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")   # secondary shape guard
MAX_LABEL_VALUE_LEN = 64


def normalize_model_label(model: str) -> str:
    """Map a possibly-unbounded model value to a bounded label: return it only if it is in the
    controlled `ALLOWED_MODEL_VALUES` registry, otherwise the single `MODEL_OTHER_BUCKET`. Trade-off:
    unknown/user-defined model aliases lose per-model granularity in metrics (they aggregate into one
    bucket) in exchange for a guaranteed-bounded time series. Use this BEFORE labeling a metric when
    the model value may come from uncontrolled input."""
    return model if model in ALLOWED_MODEL_VALUES else MODEL_OTHER_BUCKET


class HighCardinalityLabelError(ValueError):
    """Raised when a metric is declared with a per-Job/per-Attempt/per-trace label."""


class LabelValueError(ValueError):
    """Raised when a label VALUE is not from the controlled allowlist / shape (would risk high
    cardinality or unbounded input)."""


def validate_label_values(labels: dict) -> None:
    for k, v in labels.items():
        if not isinstance(v, str):
            raise LabelValueError(f"label {k!r} value must be a string, got {type(v).__name__}")
        if not (0 < len(v) <= MAX_LABEL_VALUE_LEN):
            raise LabelValueError(f"label {k!r} value length must be 1..{MAX_LABEL_VALUE_LEN}: {v!r}")
        if k == "provider" and v not in ALLOWED_PROVIDER_VALUES:
            raise LabelValueError(f"provider {v!r} is not in the controlled allowlist {sorted(ALLOWED_PROVIDER_VALUES)}")
        if k == "outcome" and v not in ALLOWED_OUTCOME_VALUES:
            raise LabelValueError(f"outcome {v!r} is not in the controlled allowlist")
        if k == "model" and v not in ALLOWED_MODEL_VALUES and v != MODEL_OTHER_BUCKET:
            raise LabelValueError(
                f"model {v!r} is not in the controlled registry {sorted(ALLOWED_MODEL_VALUES)} "
                f"(normalize unknown models to {MODEL_OTHER_BUCKET!r} via normalize_model_label first)")


@dataclass
class MetricSpec:
    name: str
    mtype: MetricType
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        bad = set(self.labels) & HIGH_CARDINALITY_LABELS
        if bad:
            raise HighCardinalityLabelError(
                f"metric {self.name!r} must not use high-cardinality labels {sorted(bad)}; "
                f"put job_id/attempt_id/trace_id in logs/traces instead")


# The Day58 metric contract (all low-cardinality: provider/model/outcome only).
PROVIDER_CALL_TOTAL = MetricSpec("provider_call_total", MetricType.COUNTER, ("provider", "model", "outcome"))
PROVIDER_CALL_DURATION_SECONDS = MetricSpec("provider_call_duration_seconds", MetricType.HISTOGRAM, ("provider", "model"))
PROVIDER_CALLS_IN_FLIGHT = MetricSpec("provider_calls_in_flight", MetricType.GAUGE, ("provider", "model"))
JOBS_PENDING_RECONCILIATION = MetricSpec("jobs_pending_reconciliation", MetricType.GAUGE, ("provider", "model"))
TELEMETRY_EXPORT_FAILURES_TOTAL = MetricSpec("telemetry_export_failures_total", MetricType.COUNTER, ())
TELEMETRY_EVENTS_DROPPED_TOTAL = MetricSpec("telemetry_events_dropped_total", MetricType.COUNTER, ())
TELEMETRY_EXPORT_QUEUE_DEPTH = MetricSpec("telemetry_export_queue_depth", MetricType.GAUGE, ())


class MetricRegistry:
    """A tiny in-process metric store enforcing the low-cardinality label contract."""

    def __init__(self) -> None:
        self._counters: dict[tuple, float] = {}
        self._gauges: dict[tuple, float] = {}
        self._histograms: dict[tuple, list] = {}

    @staticmethod
    def _key(spec: MetricSpec, labels: dict) -> tuple:
        missing = set(spec.labels) - set(labels)
        extra = set(labels) - set(spec.labels)
        if missing or extra:
            raise ValueError(f"{spec.name}: label set must be exactly {spec.labels}")
        validate_label_values(labels)          # low cardinality also requires controlled VALUES
        return (spec.name,) + tuple(labels[k] for k in spec.labels)

    def inc(self, spec: MetricSpec, labels: Optional[dict] = None, amount: float = 1.0) -> None:
        assert spec.mtype is MetricType.COUNTER
        k = self._key(spec, labels or {})
        self._counters[k] = self._counters.get(k, 0.0) + amount

    def set_gauge(self, spec: MetricSpec, value: float, labels: Optional[dict] = None) -> None:
        assert spec.mtype is MetricType.GAUGE
        self._gauges[self._key(spec, labels or {})] = value

    def observe(self, spec: MetricSpec, value: float, labels: Optional[dict] = None) -> None:
        assert spec.mtype is MetricType.HISTOGRAM
        self._histograms.setdefault(self._key(spec, labels or {}), []).append(value)

    def counter_value(self, spec: MetricSpec, labels: Optional[dict] = None) -> float:
        return self._counters.get(self._key(spec, labels or {}), 0.0)

    def gauge_value(self, spec: MetricSpec, labels: Optional[dict] = None) -> float:
        return self._gauges.get(self._key(spec, labels or {}), 0.0)

    def histogram_values(self, spec: MetricSpec, labels: Optional[dict] = None) -> list:
        return list(self._histograms.get(self._key(spec, labels or {}), []))


# ===========================================================================
# 4. Trace model + span links (async causality)
# ===========================================================================
@dataclass(frozen=True)
class SpanContext:
    trace_id: str
    span_id: str


@dataclass
class Span:
    name: str
    context: SpanContext
    parent_span_id: Optional[str] = None       # a child span shares the parent's trace_id
    links: tuple[SpanContext, ...] = ()          # causal association WITHOUT synchronous nesting


def start_trace(name: str, *, trace_id: Optional[str] = None) -> Span:
    tid = trace_id or _new_id("trace")
    return Span(name=name, context=SpanContext(tid, _new_id("span")))


def child_span(parent: Span, name: str) -> Span:
    """A child span (e.g. a Provider Adapter call) shares the parent Attempt's trace_id."""
    return Span(name=name, context=SpanContext(parent.context.trace_id, _new_id("span")),
                parent_span_id=parent.context.span_id)


def linked_trace(name: str, *, prior: Span) -> Span:
    """A LATER asynchronous Attempt: a NEW trace that LINKS to the immediate preceding causal trace
    (not a child of an already-ended span). Link only the immediate prior by default — job_id +
    correlation_id carry stable end-to-end business continuity; do NOT fan out to every historical
    trace."""
    return Span(name=name, context=SpanContext(_new_id("trace"), _new_id("span")),
                links=(prior.context,))


# ===========================================================================
# 5. Telemetry pipeline + exporter-failure policy
# ===========================================================================
class TelemetryHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"      # exporter failing; buffering/dropping, core processing continues


class TelemetryPipeline:
    """Bounded-buffer telemetry export. If the exporter is DOWN, core Job processing MUST continue
    and no accepted Job may become FAILED; events are buffered up to a bound then dropped, and health
    is exposed via metrics (`telemetry_export_failures_total`, `telemetry_events_dropped_total`,
    `telemetry_export_queue_depth`)."""

    def __init__(self, metrics: MetricRegistry, *, buffer_bound: int = 3) -> None:
        self.metrics = metrics
        self.buffer_bound = buffer_bound
        self.exporter_up = True
        self._buffer: list[StructuredEvent] = []
        self.exported: list[StructuredEvent] = []   # observable sink: events actually exported

    def export(self, event: StructuredEvent) -> None:
        if self.exporter_up:
            self.exported.append(event)     # recorded to the sink so "exported" is verifiable
            return
        # Exporter down: buffer up to the bound, else drop. NEVER raise into core processing.
        self.metrics.inc(TELEMETRY_EXPORT_FAILURES_TOTAL)
        if len(self._buffer) < self.buffer_bound:
            self._buffer.append(event)
        else:
            self.metrics.inc(TELEMETRY_EVENTS_DROPPED_TOTAL)
        self.metrics.set_gauge(TELEMETRY_EXPORT_QUEUE_DEPTH, float(len(self._buffer)))

    def recover(self) -> int:
        """Exporter RECOVERED: mark it up and DRAIN the buffered events to the sink in FIFO order,
        then reset the queue-depth gauge to 0. Returns the number of events drained. Events already
        DROPPED during the outage are gone (the dropped counter stays accurate); a still-down
        exporter keeps buffering — only `recover()` drains. This is a minimal, deterministic flush,
        NOT a real OpenTelemetry exporter (INTEGRATION_RUNTIME, NOT RUN)."""
        self.exporter_up = True
        drained = 0
        while self._buffer:
            self.exported.append(self._buffer.pop(0))
            drained += 1
        self.metrics.set_gauge(TELEMETRY_EXPORT_QUEUE_DEPTH, 0.0)
        return drained

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    def health(self) -> TelemetryHealth:
        return TelemetryHealth.HEALTHY if self.exporter_up else TelemetryHealth.DEGRADED


@dataclass
class JobProcessingResult:
    job_status: str                 # the durable business status is UNAFFECTED by telemetry health
    telemetry_health: TelemetryHealth
    events_dropped: int


def process_job_with_telemetry(pipeline: TelemetryPipeline, ident: IdentityLifecycle, *,
                               events: list[StructuredEvent], durable_status: str) -> JobProcessingResult:
    """Core processing emits events THROUGH the pipeline but never lets an exporter outage change the
    durable business status or trigger an unsafe retry."""
    for e in events:
        pipeline.export(e)          # may buffer/drop under outage; never raises
    return JobProcessingResult(job_status=durable_status, telemetry_health=pipeline.health(),
                               events_dropped=int(pipeline.metrics.counter_value(TELEMETRY_EVENTS_DROPPED_TOTAL)))


# ===========================================================================
# 6. Observability-release rollback drill (config, not DB facts)
# ===========================================================================
@dataclass
class ObservabilityRelease:
    """A bad observability release removed attempt_id from Worker logs and added job_id to
    `provider_call_total` labels (high cardinality). Rolling it back stops FURTHER correlation loss
    and cardinality damage; it does NOT (and must not) touch durable Job facts."""
    version: str
    logs_include_attempt_id: bool
    provider_call_total_has_job_id_label: bool

    def rollback(self) -> None:
        self.logs_include_attempt_id = True
        self.provider_call_total_has_job_id_label = False


@dataclass
class ObservedJob:
    """A durable Job fact snapshot (PostgreSQL is the source of truth), plus a telemetry-gap flag.

    `execution_certainty` is the durable, Adapter-owned classification of the prior attempt's outcome
    (Day56 `ExecutionCertainty`). Absence of a marker/request id is NOT proof of no execution — only a
    POSITIVE `DEFINITELY_NOT_ACCEPTED` may leave the reconciliation-only path (see
    `classify_observability_recovery`)."""
    job_id: str
    status: str
    dispatch_marker_present: bool
    provider_request_id: Optional[str]
    release_version: str
    accepted_at_index: int                 # stands in for a durable acceptance timestamp/order
    telemetry_complete: bool = True
    execution_certainty: Optional[ExecutionCertainty] = None


def build_observability_affected_set(jobs: list[ObservedJob], *, release_version: str,
                                     window_start: int, window_end: int) -> list[str]:
    """Bound the affected set by release version + time window; reconstruct affected Jobs from durable
    facts. Telemetry gaps are marked (see `mark_telemetry_gaps`), never fabricated."""
    return [j.job_id for j in jobs
            if j.release_version == release_version and window_start <= j.accepted_at_index <= window_end]


def mark_telemetry_gaps(jobs: list[ObservedJob], affected: list[str]) -> dict[str, bool]:
    """Return {job_id: telemetry_gap_present}. A gap is a fact to record honestly, not to fill in."""
    idx = {j.job_id: j for j in jobs}
    return {jid: (not idx[jid].telemetry_complete) for jid in affected}


class ObservabilityRecoveryAction(str, Enum):
    RECONCILE_ONLY = "reconcile_only"                     # any evidence/uncertainty -> never a requeue
    ELIGIBLE_FOR_GUARDED_RECOVERY = "eligible_for_guarded_recovery"  # POSITIVE not-accepted; hand to Day56


def classify_observability_recovery(job: ObservedJob) -> ObservabilityRecoveryAction:
    """Classify what recovery an observability-incident Job may undergo — reusing Day56 execution
    certainty, NEVER inferring "no execution" from ABSENCE of evidence.

    * ANY external-execution evidence (a dispatch marker or a `provider_request_id`) -> RECONCILE_ONLY.
    * A durable `pending_reconciliation` status is itself unknown external execution -> RECONCILE_ONLY.
    * Absence of a marker/request id is NOT proof of no execution (Day57). An ordinary requeue is
      permitted ONLY with a POSITIVE `DEFINITELY_NOT_ACCEPTED` execution certainty from the Adapter —
      and even then Day58 does NOT itself requeue: it returns ELIGIBLE_FOR_GUARDED_RECOVERY, meaning
      the Job may enter Day56's EXISTING guarded recovery path, which re-checks contract / deadline /
      budget / cancellation eligibility before any dispatch. This lightweight model does not own those
      Day56 eligibility facts and does not fabricate a new business state machine.
    * UNKNOWN / MAY_HAVE_EXECUTED / missing certainty -> RECONCILE_ONLY (conservative default)."""
    if job.dispatch_marker_present or job.provider_request_id is not None:
        return ObservabilityRecoveryAction.RECONCILE_ONLY
    if job.status == "pending_reconciliation":
        return ObservabilityRecoveryAction.RECONCILE_ONLY
    if (job.execution_certainty is ExecutionCertainty.DEFINITELY_NOT_ACCEPTED
            and can_ordinary_retry(job.execution_certainty)):
        return ObservabilityRecoveryAction.ELIGIBLE_FOR_GUARDED_RECOVERY
    return ObservabilityRecoveryAction.RECONCILE_ONLY


# ===========================================================================
# 7. Day58 validation matrix (four tiers; integration + production NOT RUN)
# ===========================================================================
VALIDATION_MATRIX_DAY58: tuple[MatrixRow, ...] = (
    MatrixRow("Identity/lifecycle: Worker Attempt context (attempt_id/trace_id) vs a SEPARATE HTTP request context (request_id/trace_id, no attempt_id, no silent trace reuse)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "IdentityLifecycle / HttpRequestContext tests"),
    MatrixRow("Structured event contract validates canonical VALUES (id shape, provider/model/outcome allowlists, finite reason enum, secret rejection), not just field names",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "StructuredEvent value-validation tests"),
    MatrixRow("Low-cardinality metric contract: reject high-cardinality label NAMES and uncontrolled VALUES; model must be from a FINITE registry (or normalized to a bounded bucket)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "MetricRegistry / validate_label_values / normalize_model_label tests"),
    MatrixRow("Trace/span-link modeling (child span shares trace; async link to immediate prior)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "Span / link tests"),
    MatrixRow("Telemetry exporter outage does not FAIL a Job or authorize retry; recovery drains the buffer + resets queue depth",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "TelemetryPipeline outage + recover() tests"),
    MatrixRow("Observability-release rollback: config only, not DB facts; absence of evidence stays reconcile-only, only POSITIVE DEFINITELY_NOT_ACCEPTED is eligible for Day56 guarded recovery",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "rollback + recovery-classification tests"),
    MatrixRow("Real FastAPI runtime + real OpenTelemetry exporter pipeline",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs a real FastAPI app + OTel collector"),
    MatrixRow("Real PostgreSQL/Redis/Celery integration with committed correlation evidence",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs real disposable PostgreSQL/Redis/broker + Worker"),
    MatrixRow("Real Provider traffic / production observability validation",
              EvidenceTier.PRODUCTION, RunStatus.NOT_RUN, "no production Provider credentials authorized"),
)


def day58_not_run_claims() -> list[str]:
    return [r.claim for r in VALIDATION_MATRIX_DAY58 if r.run_status is RunStatus.NOT_RUN]
