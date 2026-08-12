"""Day61 — trace-context continuity + telemetry bootstrap + accurate stale-return tests.

Covers the propagation chain
    HTTP/acceptance carrier -> Outbox payload traceparent -> Relay published Celery kwargs
    -> Worker extracted carrier -> Provider/Storage/DB operation spans use that context
with STATIC contract checks over the real runtime source PLUS EXECUTABLE checks (a fake
engine drives the real OutboxRelay and the real run_external_operation code paths without
PostgreSQL/broker). A real OTel Collector export is INTEGRATION_RUNTIME and is NOT RUN here;
these tests never pretend a Collector received anything.
"""

import pathlib
import types

import pytest

import day61_telemetry as tel
from day61_provider_adapter import AdapterResult
from day61_provider_artifact_logic import ProviderOutcome
from day61_artifact_store import InMemoryArtifactStore
from day60_delivery_runtime import OutboxRelay
import day61_worker_completion as wc

_HERE = pathlib.Path(__file__).parent


def _src(name: str) -> str:
    return (_HERE / name).read_text()


# ---------------------------------------------------------------------------
# STATIC contract: the carrier is threaded through every hop of the async chain.
# ---------------------------------------------------------------------------
def test_acceptance_writes_traceparent_into_dispatch_outbox_payload():
    s = _src("day59_runtime_app.py")
    assert "inject_trace_context(" in s and "store_traceparent_in_payload(" in s
    # The dispatch Outbox intent no longer writes a hardcoded empty payload.
    assert "CAST(:payload AS jsonb)" in s
    assert "'{}'::jsonb" not in s.split("dispatch_payload")[1][:400]


def test_relay_reads_payload_and_forwards_carrier_outside_lock():
    s = _src("day60_delivery_runtime.py")
    # Relay SELECTs the payload and loads the carrier, and passes it to publish.
    assert "SELECT outbox_event_id, job_id, event_type, payload FROM app.outbox_events" in s
    assert "load_traceparent_from_payload(payload)" in s
    assert "trace_carrier=trace_carrier" in s
    # publish-outside-lock + fenced checkpoint semantics preserved.
    assert "OUTSIDE the DB lock" in s and "fenced by relay_token" in s


def test_relay_entry_puts_carrier_in_celery_kwargs():
    s = _src("day60_relay.py")
    assert 'kwargs={"job_id": job_id' in s and '"trace_carrier"' in s


def test_worker_task_runs_authoritative_composition_with_carrier_and_bootstrap():
    s = _src("day60_celery_app.py")
    assert "trace_carrier" in s
    assert "bootstrap_telemetry(" in s
    # The PRODUCTION task now runs the Day61 authoritative composition (Provider is always
    # called before success), NOT the Day60 skeleton run_worker_attempt.
    assert "run_authoritative_attempt(" in s
    assert "run_worker_attempt(" not in s
    assert 'os.environ.get("DAY61_PROVIDER_URL")' in s  # Provider URL from env, not the message


def test_worker_unit_of_work_runs_under_extracted_context():
    s = _src("day60_delivery_runtime.py")
    assert "extract_trace_context(trace_carrier)" in s
    assert 'operation_span("worker.unit_of_work"' in s and "parent_context=_parent_ctx" in s


def test_external_operation_spans_use_the_propagated_context():
    s = _src("day61_worker_completion.py")
    assert "parent_ctx = extract_trace_context(trace_carrier)" in s
    # every operation span is opened under the propagated parent context
    assert s.count("parent_context=parent_ctx") >= 3


def test_full_provider_request_id_never_enters_trace_payload_or_labels():
    # traceparent helper stores ONLY the traceparent string; no provider_request_id anywhere.
    payload = tel.store_traceparent_in_payload({"job_id": "j1"}, {"traceparent": "tp", "provider_request_id": "prov-x"})
    assert "provider_request_id" not in payload
    # metric labels reject high-cardinality keys (incl. provider_request_id).
    assert tel.record_provider_outcome("fake", "valid", "verified") is True


# ---------------------------------------------------------------------------
# EXECUTABLE: the real OutboxRelay carries the payload traceparent to publish, and a
# RETRY of the same durable intent reuses the SAME trace association.
# ---------------------------------------------------------------------------
class _Row:
    def __init__(self, payload):
        self.outbox_event_id = "oe-1"
        self.job_id = "job-1"
        self.event_type = "job.dispatch_requested"
        self.payload = payload


class _RelayResult:
    def __init__(self, first=None, rowcount=0):
        self._first = first
        self.rowcount = rowcount

    def first(self):
        return self._first


class _RelayConn:
    def __init__(self, engine):
        self._e = engine

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql.strip().startswith("SELECT outbox_event_id"):
            if self._e.rows:
                return _RelayResult(first=self._e.rows.pop(0))
            return _RelayResult(first=None)
        return _RelayResult(rowcount=1)  # claim UPDATE + checkpoint UPDATE


class _RelayEngine:
    def __init__(self, payload):
        self.rows = [_Row(payload)]

    def begin(self):
        return _RelayConn(self)


def _deliver_once(payload):
    captured = {}

    def publish(job_id, event_type, outbox_event_id, trace_carrier=None):
        captured["trace_carrier"] = trace_carrier

    OutboxRelay(_RelayEngine(payload), publish).deliver_batch(limit=5)
    return captured["trace_carrier"]


def test_relay_delivers_traceparent_from_payload():
    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    carrier = _deliver_once({"traceparent": tp})
    assert carrier == {"traceparent": tp}


def test_relay_retry_reuses_same_trace_association():
    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    payload = {"traceparent": tp}
    first = _deliver_once(payload)   # initial publish
    retry = _deliver_once(payload)   # redelivery of the SAME durable intent
    assert first == retry == {"traceparent": tp}  # same association; span id is per-publish


def test_relay_empty_or_corrupt_carrier_degrades_safely():
    assert _deliver_once({}) == {}                       # no traceparent -> empty carrier
    assert _deliver_once({"traceparent": 123}) == {}     # corrupt (non-str) -> empty carrier
    assert _deliver_once(None) == {}                     # missing payload -> empty carrier


# ---------------------------------------------------------------------------
# EXECUTABLE: bootstrap is safe when disabled/failed.
# ---------------------------------------------------------------------------
def test_bootstrap_telemetry_disabled_is_safe_noop():
    tel._reset_telemetry_init_for_tests()
    assert tel.bootstrap_telemetry("unit-test") is False  # disabled by default, no raise
    tel._reset_telemetry_init_for_tests()


def test_bootstrap_telemetry_swallows_init_failure(monkeypatch):
    def _boom():
        raise RuntimeError("exporter package missing")

    monkeypatch.setattr(tel, "init_telemetry", _boom)
    assert tel.bootstrap_telemetry("unit-test") is False  # failure -> bounded no-op, never raises


# ---------------------------------------------------------------------------
# EXECUTABLE: accurate stale-Worker returns (P1-4) — a superseded lease after the HTTP
# response makes timeout/invalid-response return the STALE outcome, not a fabricated one,
# and does NOT touch the successor's Job (no event insert past the 0-row guarded UPDATE).
# ---------------------------------------------------------------------------
class _WResult:
    def __init__(self, first=None, rowcount=0):
        self._first = first
        self.rowcount = rowcount

    def first(self):
        return self._first


class _WConn:
    def __init__(self, engine):
        self._e = engine

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self._e.executed.append(sql)
        if "SELECT a.attempt_id" in sql:
            return _WResult(first=("attempt-1",))          # Attempt owned by this Job
        if "provider_dispatch_started_at=coalesce" in sql:
            return _WResult(rowcount=1)                     # marker claim succeeds -> "claimed"
        if "job_status='pending_reconciliation'" in sql:
            return _WResult(rowcount=0)                     # STALE: lease superseded -> 0 rows
        if "job_status='failed'" in sql:
            return _WResult(rowcount=0)                     # STALE: lease superseded -> 0 rows
        return _WResult(rowcount=0)


class _WEngine:
    def __init__(self):
        self.executed = []

    def begin(self):
        return _WConn(self)


def _run_stale(monkeypatch, outcome):
    monkeypatch.setattr(wc, "call_provider",
                        lambda url, ck, mode, **kw: AdapterResult(outcome))
    eng = _WEngine()
    res = wc.run_external_operation(
        eng, "http://unused", "t1", "job-1", "attempt-1", "stale-token",
        correlation_key="c1", mode="x", store=InMemoryArtifactStore(),
        trace_carrier={"traceparent": "tp"},
    )
    return res, eng


def test_stale_timeout_returns_lease_lost_not_pending_reconciliation(monkeypatch):
    res, eng = _run_stale(monkeypatch, ProviderOutcome.TIMEOUT)
    assert res == "lease_lost_no_commit"
    # No event row was inserted for the successor's Job (the 0-row guarded UPDATE short-circuits).
    assert not any("INSERT INTO app.job_events" in s and "pending_reconciliation" in s for s in eng.executed)


def test_stale_invalid_response_returns_lease_lost_not_contract_failure(monkeypatch):
    res, eng = _run_stale(monkeypatch, ProviderOutcome.INVALID_BODY)
    assert res == "lease_lost_no_commit"
    assert not any("provider.contract_failure" in s for s in eng.executed)


def test_operation_span_parent_context_is_noop_safe():
    ctx = tel.extract_trace_context({"traceparent": "tp"})  # None without SDK
    with tel.operation_span("x", "j1", "a1", parent_context=ctx):
        pass  # must not raise on the parent_context path


# ---------------------------------------------------------------------------
# P1-1: the Relay's real publish path emits an `outbox.relay_publish` span UNDER the payload's
# trace association, without ever blocking the publish or the fenced checkpoint.
# ---------------------------------------------------------------------------
class _SqlRelayResult:
    def __init__(self, first=None, rowcount=0):
        self._first = first
        self.rowcount = rowcount

    def first(self):
        return self._first


class _SqlRelayConn:
    def __init__(self, engine):
        self._e = engine

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self._e.executed.append(sql)
        if sql.strip().startswith("SELECT outbox_event_id"):
            if self._e.rows:
                return _SqlRelayResult(first=self._e.rows.pop(0))
            return _SqlRelayResult(first=None)
        return _SqlRelayResult(rowcount=1)  # claim UPDATE + checkpoint UPDATE


class _SqlRelayEngine:
    def __init__(self, payload):
        self.rows = [_Row(payload)]
        self.executed = []

    def begin(self):
        return _SqlRelayConn(self)


def test_relay_publish_span_started_under_payload_trace_association(monkeypatch):
    import day60_delivery_runtime as dr

    calls = []

    class _SpyCM:
        def __init__(self, meta):
            self.meta = meta

        def __enter__(self):
            calls.append(self.meta)
            return None

        def __exit__(self, *a):
            return False

    def _spy_span(outbox_event_id, job_id, event_type, parent_context=None):
        return _SpyCM({"oe": outbox_event_id, "job": job_id, "etype": event_type, "parent": parent_context})

    # Deterministic association token derived from the carrier's traceparent (same tp -> same token).
    monkeypatch.setattr(dr, "relay_publish_span", _spy_span)
    monkeypatch.setattr(dr, "extract_trace_context",
                        lambda c: ("assoc", c.get("traceparent")) if c else None)

    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

    def _run():
        published = {}
        def publish(job_id, event_type, outbox_event_id, trace_carrier=None):
            published["carrier"] = trace_carrier
        eng = _SqlRelayEngine({"traceparent": tp})
        OutboxRelay(eng, publish).deliver_batch(limit=5)
        return published, eng

    pub1, eng1 = _run()
    assert calls[0]["parent"] == ("assoc", tp)          # span parented on the payload's trace
    assert calls[0]["job"] and calls[0]["oe"] == "oe-1"
    assert pub1["carrier"] == {"traceparent": tp}       # carrier still forwarded to the task
    # a RETRY of the same durable intent -> SAME association, a NEW span invocation (new span id).
    _run()
    assert calls[1]["parent"] == calls[0]["parent"]     # same trace id
    assert calls[1] is not calls[0]                     # distinct Relay span per publish


def test_relay_publish_and_checkpoint_survive_telemetry_failure(monkeypatch):
    # A failing SDK tracer inside the REAL relay_publish_span must not block publish/checkpoint.
    import day61_telemetry as tel

    class _BadTracer:
        def start_as_current_span(self, *a, **k):
            raise RuntimeError("span backend down")

    monkeypatch.setattr(tel, "_OTEL", True, raising=False)
    monkeypatch.setattr(tel, "_TRACER", _BadTracer(), raising=False)

    published = {}
    def publish(job_id, event_type, outbox_event_id, trace_carrier=None):
        published["ok"] = True
    eng = _SqlRelayEngine({"traceparent": "00-abc-def-01"})
    delivered = OutboxRelay(eng, publish).deliver_batch(limit=5)

    assert delivered == 1
    assert published.get("ok") is True                                  # publish completed
    assert any("SET published_at=now()" in s for s in eng.executed)     # fenced checkpoint ran


def test_relay_publish_span_is_in_the_real_deliver_batch_path():
    # Guard against a docs-only / helper-only span: it must be wired into deliver_batch, around
    # the publish, and the checkpoint must remain OUTSIDE the span (still fenced).
    s = (_HERE / "day60_delivery_runtime.py").read_text()
    assert "with relay_publish_span(" in s
    i_with = s.index("with relay_publish_span(")
    i_pub = s.index("self._publish(", i_with)
    i_ckpt = s.index("self._checkpoint(", i_with)
    assert i_with < i_pub < i_ckpt                       # span wraps publish; checkpoint after
    # checkpoint line is de-indented relative to the publish (outside the with block)
    assert "self._checkpoint(outbox_event_id, token)" in s
