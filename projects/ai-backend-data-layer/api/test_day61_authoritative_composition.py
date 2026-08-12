"""Day61 — the authoritative-attempt composition + FastAPI root-span tests.

Proves (statically over the real source AND executably with fakes) that:
  * an accepted Job reaches Day61's ``run_external_operation`` through the REAL Celery
    composition — there is NO "no Provider, straight to succeeded" production path;
  * ``run_external_operation``'s non-success outcomes (pending_reconciliation / contract_failure
    / lease_lost_no_commit / ...) are returned VERBATIM, never rewritten to succeeded;
  * tenant + the stable correlation key come from PostgreSQL durable facts (not the message);
  * acceptance establishes a ``fastapi.accept_job`` ROOT span so the injected traceparent is
    written into the Outbox payload in the SAME transaction.

EXECUTED_LOCAL_RUNTIME (pure/static/fake-driven). The full PostgreSQL + Redis/Celery + MinIO +
OTel-Collector run is INTEGRATION_RUNTIME and is NOT RUN here.
"""

import pathlib

import pytest

import day61_telemetry as tel
import day61_worker_runtime as rt

_HERE = pathlib.Path(__file__).parent


def _src(name: str) -> str:
    return (_HERE / name).read_text()


# ---------------------------------------------------------------------------
# STATIC: the production Worker path calls run_external_operation via the composition.
# ---------------------------------------------------------------------------
def test_celery_task_calls_composition_not_skeleton():
    s = _src("day60_celery_app.py")
    assert "run_authoritative_attempt(" in s
    assert "run_worker_attempt(" not in s  # the Day60 empty-success skeleton is NOT the task


def test_composition_claims_then_calls_external_operation():
    s = _src("day61_worker_runtime.py")
    assert "from day60_delivery_runtime import claim_and_start_attempt" in s
    assert "from day61_worker_completion import run_external_operation" in s
    # claim precedes the external operation; tenant comes from durable facts (app.jobs).
    assert s.index("claim_and_start_attempt(") < s.index("run_external_operation(")
    assert "SELECT tenant_id, request_fingerprint FROM app.jobs" in s


def test_day60_skeleton_still_exists_but_is_not_the_production_path():
    s = _src("day60_delivery_runtime.py")
    assert "def claim_and_start_attempt(" in s          # shared claim extracted
    assert "def run_worker_attempt(" in s               # Day60 teaching skeleton preserved
    # Day60 semantics preserved: full lease triple cleared + attempt counted on completion.
    assert "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL" in s
    assert "attempt_count=attempt_count+1" in s


# ---------------------------------------------------------------------------
# EXECUTABLE: the composition routes into run_external_operation and returns its outcome
# verbatim, using tenant + correlation key from durable facts and the claim's lease token.
# ---------------------------------------------------------------------------
class _Facts:
    def __init__(self, tenant_id="t1", fp="fp-abc"):
        self.tenant_id = tenant_id
        self.request_fingerprint = fp


class _Res:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Conn:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        return _Res(self._row)


class _Eng:
    def __init__(self, row):
        self._row = row

    def begin(self):
        return _Conn(self._row)


def _spy(captured, outcome):
    def run_external_operation(engine, provider_url, tenant_id, job_id, attempt_id, lease_token,
                               correlation_key, mode="success", store=None, provider_name="fake",
                               trace_carrier=None):
        captured.update(tenant_id=tenant_id, job_id=job_id, attempt_id=attempt_id,
                        lease_token=lease_token, correlation_key=correlation_key,
                        provider_url=provider_url, trace_carrier=trace_carrier, called=True)
        return outcome

    return run_external_operation


@pytest.mark.parametrize("outcome", [
    "succeeded", "pending_reconciliation", "contract_failure", "lease_lost_no_commit",
    "provider_request_id_conflict", "artifact_conflict", "artifact_unverified",
])
def test_composition_returns_external_outcome_verbatim(monkeypatch, outcome):
    captured = {}
    monkeypatch.setattr(rt, "claim_and_start_attempt", lambda e, j, w: ("tok-1", "att-1"))
    monkeypatch.setattr(rt, "run_external_operation", _spy(captured, outcome))
    out = rt.run_authoritative_attempt(
        _Eng(_Facts()), "job-1", "worker-1",
        provider_url="http://127.0.0.1:0/fake", trace_carrier={"traceparent": "tp"},
    )
    assert out == outcome                                   # never rewritten (esp. not -> succeeded)
    assert captured["called"] is True                       # Provider path WAS entered
    assert captured["tenant_id"] == "t1"                    # tenant from durable PG facts
    assert captured["lease_token"] == "tok-1"               # claim's lease token fences the op
    assert captured["correlation_key"] == "corr:t1:job-1:att-1"   # derived from durable facts
    assert captured["provider_url"] == "http://127.0.0.1:0/fake"  # from env/caller, not message


def test_not_claimed_never_calls_provider(monkeypatch):
    captured = {}
    monkeypatch.setattr(rt, "claim_and_start_attempt", lambda e, j, w: None)
    monkeypatch.setattr(rt, "run_external_operation", _spy(captured, "succeeded"))
    out = rt.run_authoritative_attempt(_Eng(_Facts()), "job-1", "w1", provider_url="http://x")
    assert out == "not_claimed"
    assert "called" not in captured                         # no Provider call on a lost claim


def test_missing_job_facts_never_succeeds(monkeypatch):
    captured = {}
    monkeypatch.setattr(rt, "claim_and_start_attempt", lambda e, j, w: ("tok-1", "att-1"))
    monkeypatch.setattr(rt, "run_external_operation", _spy(captured, "succeeded"))
    out = rt.run_authoritative_attempt(_Eng(None), "job-1", "w1", provider_url="http://x")
    assert out == "job_facts_missing"                       # non-success; sweeper recovers
    assert "called" not in captured                         # no Provider call without facts


# ---------------------------------------------------------------------------
# STATIC + EXECUTABLE: acceptance establishes a ROOT span so a traceparent can be emitted.
# ---------------------------------------------------------------------------
def test_acceptance_wraps_uow_in_fastapi_root_span():
    s = _src("day59_runtime_app.py")
    assert 'root_span("fastapi.accept_job")' in s
    # inject + Outbox write happen INSIDE the root span (so the traceparent is a real child).
    i_span = s.index('root_span("fastapi.accept_job")')
    assert s.index("inject_trace_context({})", i_span) > i_span
    assert s.index("INSERT INTO app.outbox_events", i_span) > i_span


def test_acceptance_readiness_requires_the_day60_schema_head_used_by_day61_worker():
    s = _src("day59_runtime_app.py")
    assert 'EXPECTED_ALEMBIC_REVISION = "0012_day60_repair_audit_attestation"' in s


class _FakeSpanCM:
    def __init__(self, log):
        self._log = log

    def __enter__(self):
        self._log.append("enter")
        return object()

    def __exit__(self, *exc):
        self._log.append("exit")
        return False


class _FakeTracer:
    def __init__(self, log):
        self._log = log

    def start_as_current_span(self, name, **kw):
        self._log.append(("start", name))
        return _FakeSpanCM(self._log)


def test_root_span_starts_a_span_when_sdk_present(monkeypatch):
    log = []
    monkeypatch.setattr(tel, "_OTEL", True, raising=False)
    monkeypatch.setattr(tel, "_TRACER", _FakeTracer(log), raising=False)
    with tel.root_span("fastapi.accept_job"):
        ran = True
    assert ran is True
    assert ("start", "fastapi.accept_job") in log and "enter" in log and "exit" in log


def test_root_span_noop_without_sdk_and_propagates_business_exception():
    with tel.root_span("fastapi.accept_job"):
        pass  # no SDK -> no raise
    with pytest.raises(ValueError):
        with tel.root_span("fastapi.accept_job"):
            raise ValueError("business error propagates")


def test_traceparent_string_is_preserved_acceptance_to_worker():
    # The trace ID travels as the traceparent STRING: acceptance stores it on the payload, the
    # Relay loads the same string, and the Worker would extract that same context (same trace id;
    # span id differs per hop). Pure data-level proof (no SDK needed).
    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    payload = tel.store_traceparent_in_payload({"job_id": "j1"}, {"traceparent": tp})
    relay_carrier = tel.load_traceparent_from_payload(payload)
    assert relay_carrier == {"traceparent": tp}            # same association preserved end-to-end
