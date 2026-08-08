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
  * IdentityLifecycle          — the five identities and their stability rules (job_id /
                                 correlation_id stable; attempt_id + trace_id per execution; request_id
                                 per HTTP request).
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

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Reuse Day57's evidence taxonomy (four tiers) and Day56's execution-certainty vocabulary.
from day57_testing_harness import EvidenceTier, MatrixRow, RunStatus
from day56_provider_resilience import ExecutionCertainty


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ===========================================================================
# 1. Identity + lifecycle contract (five distinct identities)
# ===========================================================================
@dataclass
class IdentityLifecycle:
    """The identity bundle for a Job's execution chain. `job_id` and `correlation_id` are STABLE
    across retries (business continuity); a new durable Attempt gets a NEW `attempt_id` and normally
    a NEW `trace_id`; each HTTP request gets a NEW `request_id`. `trace_id` is one distributed trace,
    NOT business truth."""
    job_id: str                       # durable business identity (stable)
    correlation_id: str               # stable business-chain association (stable)
    attempt_id: str                   # one concrete execution attempt (per Attempt)
    trace_id: str                     # one distributed execution trace (per Attempt, normally)
    request_id: Optional[str] = None  # one short-lived HTTP request identity (per request)

    def new_http_request(self) -> "IdentityLifecycle":
        """A new HTTP request: only request_id changes; everything else is unchanged."""
        return IdentityLifecycle(job_id=self.job_id, correlation_id=self.correlation_id,
                                 attempt_id=self.attempt_id, trace_id=self.trace_id,
                                 request_id=_new_id("req"))

    def new_attempt(self) -> "IdentityLifecycle":
        """A new durable Attempt: job_id + correlation_id STAY; a new attempt_id and (normally) a new
        trace_id are minted; request_id is cleared (an Attempt is not an HTTP request)."""
        return IdentityLifecycle(job_id=self.job_id, correlation_id=self.correlation_id,
                                 attempt_id=_new_id("att"), trace_id=_new_id("trace"),
                                 request_id=None)


def start_job_chain(job_id: Optional[str] = None) -> IdentityLifecycle:
    job_id = job_id or _new_id("job")
    return IdentityLifecycle(job_id=job_id, correlation_id=_new_id("cor"),
                             attempt_id=_new_id("att"), trace_id=_new_id("trace"),
                             request_id=_new_id("req"))


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
        unknown = set(self.extra) - SAFE_EVENT_FIELDS
        if unknown:
            raise UnsafeTelemetryError(f"unrecognized event fields (must be explicitly safe): {sorted(unknown)}")

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
        d.update(self.extra)
        return d


def emit_provider_call_timeout(ident: IdentityLifecycle, *, provider: str, model: str,
                               duration_ms: int, dispatch_marker_present: bool) -> StructuredEvent:
    """`provider.call.timeout` = the application's OBSERVED timeout/unknown outcome. It is NOT proof
    the Provider did not execute."""
    return StructuredEvent(event_name="provider.call.timeout", job_id=ident.job_id,
                           correlation_id=ident.correlation_id, attempt_id=ident.attempt_id,
                           trace_id=ident.trace_id, provider=provider, model=model,
                           outcome="timeout", duration_ms=duration_ms,
                           request_id_present=ident.request_id is not None,
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


class HighCardinalityLabelError(ValueError):
    """Raised when a metric is declared with a per-Job/per-Attempt/per-trace label."""


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

    def export(self, event: StructuredEvent) -> None:
        if self.exporter_up:
            return                          # exported successfully (modeled as a no-op sink)
        # Exporter down: buffer up to the bound, else drop. NEVER raise into core processing.
        self.metrics.inc(TELEMETRY_EXPORT_FAILURES_TOTAL)
        if len(self._buffer) < self.buffer_bound:
            self._buffer.append(event)
        else:
            self.metrics.inc(TELEMETRY_EVENTS_DROPPED_TOTAL)
        self.metrics.set_gauge(TELEMETRY_EXPORT_QUEUE_DEPTH, float(len(self._buffer)))

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
    """A durable Job fact snapshot (PostgreSQL is the source of truth), plus a telemetry-gap flag."""
    job_id: str
    status: str
    dispatch_marker_present: bool
    provider_request_id: Optional[str]
    release_version: str
    accepted_at_index: int                 # stands in for a durable acceptance timestamp/order
    telemetry_complete: bool = True


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
    RECONCILE_ONLY = "reconcile_only"      # dispatch marker / evidence -> never an ordinary requeue
    REQUEUE_ORDINARY = "requeue_ordinary"  # only proven-no-execution Jobs (no marker, no request id)


def classify_observability_recovery(job: ObservedJob) -> ObservabilityRecoveryAction:
    """A PENDING_RECONCILIATION Job whose telemetry is incomplete but whose DATABASE has a dispatch
    marker remains reconciliation-only — it must NOT be requeued for an ordinary Provider call. The
    observability gap does not change durable safety."""
    if job.dispatch_marker_present or job.provider_request_id is not None:
        return ObservabilityRecoveryAction.RECONCILE_ONLY
    if job.status == "pending_reconciliation":
        return ObservabilityRecoveryAction.RECONCILE_ONLY
    return ObservabilityRecoveryAction.REQUEUE_ORDINARY


# ===========================================================================
# 7. Day58 validation matrix (four tiers; integration + production NOT RUN)
# ===========================================================================
VALIDATION_MATRIX_DAY58: tuple[MatrixRow, ...] = (
    MatrixRow("Identity/lifecycle stability rules (job_id/correlation_id stable; attempt_id/trace_id per attempt; request_id per request)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "pytest over in-process identity model"),
    MatrixRow("Structured event safe-field contract (no raw prompts/responses/secrets; suppressed reason)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "StructuredEvent validation tests"),
    MatrixRow("Low-cardinality metric label contract (Counter/Gauge/Histogram; reject job_id/attempt_id/trace_id labels)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "MetricSpec / MetricRegistry tests"),
    MatrixRow("Trace/span-link modeling (child span shares trace; async link to immediate prior)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "Span / link tests"),
    MatrixRow("Telemetry exporter outage does not FAIL a Job or authorize retry; health metrics",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "TelemetryPipeline tests"),
    MatrixRow("Observability-release rollback: config only, not DB facts; marker-backed job stays reconcile-only",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "rollback drill tests"),
    MatrixRow("Real FastAPI runtime + real OpenTelemetry exporter pipeline",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs a real FastAPI app + OTel collector"),
    MatrixRow("Real PostgreSQL/Redis/Celery integration with committed correlation evidence",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs real disposable PostgreSQL/Redis/broker + Worker"),
    MatrixRow("Real Provider traffic / production observability validation",
              EvidenceTier.PRODUCTION, RunStatus.NOT_RUN, "no production Provider credentials authorized"),
)


def day58_not_run_claims() -> list[str]:
    return [r.claim for r in VALIDATION_MATRIX_DAY58 if r.run_status is RunStatus.NOT_RUN]
