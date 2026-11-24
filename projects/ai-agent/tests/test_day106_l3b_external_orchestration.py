"""Fake-only checks for the Day106 L3B combined runner schedule."""

from __future__ import annotations

import json
import inspect
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import evals.run_day106_l3b_external_integration as runner
from evals.run_day106_l3b_external_integration import (
    EXPECTED_EXTERNAL_CALLS,
    EXPECTED_ZERO_CALL_GATES,
    ExternalCallAccounting,
    _g2_specs,
    _g3_q2_spec,
    _g3_zero_call_specs,
    _bound_candidate_digest,
    _write_exclusive,
    run_fake_dry_run,
)
from rag_chunking_contracts import stable_hash
from rag_openai_responses_adapter import (
    OpenAIResponsesHTTPResponse,
    OpenAIResponsesRequest,
)


class CountingFakeTransport:
    def __init__(self) -> None:
        self.requests: list[OpenAIResponsesRequest] = []

    def send(
        self,
        request: OpenAIResponsesRequest,
    ) -> OpenAIResponsesHTTPResponse:
        self.requests.append(request)
        return OpenAIResponsesHTTPResponse(200, b"{}")


def test_fake_dry_run_uses_exact_five_calls_and_zero_call_gates() -> None:
    transport = CountingFakeTransport()

    report = run_fake_dry_run(transport)

    assert report["status"] == "PASS"
    assert report["evidence_level"] == "DETERMINISTIC_FAKE_TRANSPORT_ONLY"
    assert report["external_call_count"] == 5
    assert tuple(report["external_call_labels"]) == EXPECTED_EXTERNAL_CALLS
    assert set(report["zero_call_gates"]) == set(EXPECTED_ZERO_CALL_GATES)
    assert len(transport.requests) == 5
    assert all(
        request.max_output_tokens == 64
        and request.payload()["store"] is False
        and request.payload()["reasoning"] == {"effort": "low"}
        and "tools" not in request.payload()
        for request in transport.requests
    )
    unsigned = {
        key: value for key, value in report.items()
        if key != "report_checksum"
    }
    assert report["report_checksum"] == stable_hash(unsigned)
    serialized = json.dumps(report, sort_keys=True)
    assert "SYNTHETIC_DRY_RUN" not in serialized


def test_query_plan_has_four_pre_p2_calls_and_one_post_p2_call() -> None:
    g2 = _g2_specs()
    g3 = _g3_q2_spec()
    zero = _g3_zero_call_specs()

    assert tuple(item.label for item in g2) == EXPECTED_EXTERNAL_CALLS[:4]
    assert g3.label == EXPECTED_EXTERNAL_CALLS[4]
    assert sum(item.release_immediately for item in g2) == 3
    assert not g2[-1].release_immediately
    assert tuple(item.label for item in zero) == EXPECTED_ZERO_CALL_GATES[1:]
    assert all(item.generation_id == "G3" for item in zero)


def test_zero_call_accounting_rejects_any_provider_delta() -> None:
    accounting = ExternalCallAccounting.empty()

    with pytest.raises(AssertionError, match="ZERO_CALL_GATE_CALLED_PROVIDER"):
        accounting.record_zero_call_gate(
            "G3_P2_Q1_REQUIRED_A_UNAVAILABLE",
            4,
            5,
        )


def test_exclusive_report_write_refuses_overwrite(tmp_path) -> None:
    target = tmp_path / "day106-l3b-report.json"
    report = run_fake_dry_run(CountingFakeTransport())

    _write_exclusive(target, report)

    assert json.loads(target.read_text(encoding="utf-8")) == report
    with pytest.raises(FileExistsError):
        _write_exclusive(target, report)


def test_failure_recovery_marks_unreceipted_attempt_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_queries: list[tuple[str, tuple[object, ...]]] = []

    def fake_query_one(factory, query, params=()):
        observed_queries.append((query, params))
        return (5, 4, 3, 0, 1, 5)

    monkeypatch.setattr(
        runner,
        "psycopg2_connection_factory",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        runner,
        "_query_one",
        fake_query_one,
    )
    identity_rows = [
        ("PROVIDER_ATTEMPT", stable_hash(("attempt", index)))
        for index in range(5)
    ] + [
        ("PROVIDER_RECEIPT", stable_hash(("receipt", index)))
        for index in range(4)
    ]
    def fake_query_rows(factory, query, params=()):
        observed_queries.append((query, params))
        return sorted(identity_rows)

    monkeypatch.setattr(runner, "_query_rows", fake_query_rows)

    progress = runner._recover_provider_progress("redacted-database-url")

    assert progress["attempt_count"] == 5
    assert progress["receipt_count"] == 4
    assert progress["unreceipted_attempt_count"] == 1
    assert progress["latest_call_ordinal"] == 5
    assert len(progress["attempt_identity_digests"]) == 5
    assert len(progress["receipt_identity_digests"]) == 4
    assert str(progress["durable_progress_digest"]).startswith("sha256:")
    assert progress["provider_outcome_state"] == "UNKNOWN"
    assert progress["reconciliation_required"] is True
    assert progress["blind_retry_allowed"] is False
    assert len(observed_queries) == 2
    assert all(
        params == (runner.TENANT_ID, "refund-serving")
        for _, params in observed_queries
    )
    assert all("tenant_requests" in query for query, _ in observed_queries)


def test_existing_report_path_blocks_before_transport(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "existing.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(runner.INTEGRATION_FLAG, "1")
    monkeypatch.setenv(runner.REAL_PROVIDER_FLAG, "1")
    monkeypatch.setenv(runner.DATABASE_URL_ENV, "redacted-database-url")
    monkeypatch.setattr(
        runner,
        "UrllibOpenAIResponsesTransport",
        lambda: (_ for _ in ()).throw(
            AssertionError("transport must not initialize")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", "--report-path", str(target)],
    )

    result = runner.main()

    assert result == 2
    output = json.loads(capsys.readouterr().out)
    assert output["safe_reason"] == "DAY106_L3B_REPORT_PATH_ALREADY_EXISTS"
    assert output["external_call_count"] == 0


def test_success_artifact_identity_covers_complete_replay_contract() -> None:
    digests = runner._artifact_digests()

    assert set(digests) == {
        "integration_runner",
        "evidence_schema",
        "database_schema",
        "capstone_repository",
        "compose",
        "openai_adapter",
        "production_capstone",
        "capstone_support",
        "grounding_adapters",
        "grounding_orchestrator",
        "day105_integration_runner",
        "day106_l3a_integration_runner",
        "restart_runner",
        "evidence_replay_runner",
        "base_commit",
    }
    assert len(digests["base_commit"]) == 40
    assert all(
        value.startswith("sha256:") and len(value) == 71
        for key, value in digests.items()
        if key != "base_commit"
    )


def test_pre_restart_state_aggregates_stable_durable_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {
        "ANSWER_RELEASE": 5,
        "DISPATCH_RECORD": 0,
        "DISPATCH_WINNER": 0,
        "MODEL_INVOCATION": 5,
        "PROVIDER_ATTEMPT": 5,
        "PROVIDER_RECEIPT": 5,
        "REQUEST_BINDING": 5,
        "RESPONSE_INTENT": 4,
        "RETRIEVAL_CONTEXT_RECEIPT": 5,
    }
    rows = sorted(
        (
            artifact_type,
            stable_hash((artifact_type, index)),
        )
        for artifact_type, count in counts.items()
        for index in range(count)
    )
    monkeypatch.setattr(
        runner,
        "_query_one",
        lambda *args, **kwargs: (
            datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc),
        ),
    )
    pointer_rows = [("refund-serving", "G3", 9)]
    security_rows = [("tenant-refund", "P2", 2)]

    def fake_query_rows(factory, query, params=()):
        if "day104_l3.active_pointers" in query:
            assert "WHERE pointer_name = %s" in query
            assert params == ("refund-serving",)
            return pointer_rows
        if "day105_l3.current_security_snapshots" in query:
            assert "WHERE tenant_id = %s" in query
            assert params == (runner.TENANT_ID,)
            return security_rows
        assert "WITH tenant_requests AS" in query
        assert "JOIN tenant_intents AS intent" in query
        assert params == (runner.TENANT_ID, "refund-serving")
        return rows

    monkeypatch.setattr(runner, "_query_rows", fake_query_rows)

    state = runner._durable_pre_restart_state(object())

    assert state["pre_restart_postmaster_started_at"] == (
        "2026-11-24T10:00:00+00:00"
    )
    assert state["pre_restart_state_digest"] == stable_hash((
        "DAY106_L3B_DURABLE_STATE_V1",
        tuple(pointer_rows),
        tuple(security_rows),
        tuple(rows),
    ))
    assert state["artifact_counts"] == counts
    assert state["artifact_identity_count"] == 34


def test_provider_answer_candidate_digest_drift_fails_before_receipt() -> None:
    observation = SimpleNamespace(
        outcome="SUCCEEDED",
        answer_digest=stable_hash("provider-answer"),
    )
    prepared = SimpleNamespace(candidate=SimpleNamespace(
        answer_digest=stable_hash("different-candidate-answer"),
        digest=stable_hash("candidate-record"),
    ))

    with pytest.raises(
        AssertionError,
        match="PROVIDER_ANSWER_CANDIDATE_DIGEST_DRIFT",
    ):
        _bound_candidate_digest(observation, prepared)


def test_integration_failure_writes_unique_fail_closed_progress_report(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "failed-run.json"
    progress = {
        "attempt_count": 2,
        "receipt_count": 1,
        "unreceipted_attempt_count": 1,
        "latest_call_ordinal": 2,
        "provider_outcome_state": "UNKNOWN",
        "reconciliation_required": True,
        "blind_retry_allowed": False,
    }
    monkeypatch.setenv(runner.INTEGRATION_FLAG, "1")
    monkeypatch.setenv(runner.REAL_PROVIDER_FLAG, "1")
    monkeypatch.setenv(runner.DATABASE_URL_ENV, "redacted-database-url")
    monkeypatch.setattr(
        runner,
        "run_real_integration",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic safe failure")
        ),
    )
    monkeypatch.setattr(
        runner,
        "_recover_provider_progress",
        lambda database_url: progress,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", "--report-path", str(target)],
    )

    result = runner.main()

    assert result == 1
    saved = json.loads(target.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert saved == printed
    assert saved["status"] == "FAIL_CLOSED"
    assert saved["external_real_boundary"] == "INCONCLUSIVE"
    assert saved["blind_retry_allowed"] is False
    assert saved["durable_provider_progress"] == progress


def test_only_internal_real_entrypoint_can_attest_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")

    real = runner.UrllibOpenAIResponsesTransport()
    real_scope = runner._attested_real_transport_evidence_scope(real)
    injected_scope = runner._injected_transport_evidence_scope()

    assert real_scope.real_external_transport_attested is True
    assert real_scope.transport_boundary == runner.REAL_TRANSPORT_BOUNDARY
    assert real_scope.external_model_boundary == "PASS"
    assert injected_scope.real_external_transport_attested is False
    assert injected_scope.schema_version == runner.FAKE_SCHEMA_VERSION
    assert injected_scope.scenario_id == runner.FAKE_SCENARIO_ID
    assert injected_scope.transport_boundary == runner.FAKE_TRANSPORT_BOUNDARY
    assert injected_scope.external_model_boundary == "NOT_RUN"
    assert "transport" not in inspect.signature(
        runner.run_real_integration
    ).parameters


def test_real_transport_instance_send_override_cannot_be_attested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    transport = runner.UrllibOpenAIResponsesTransport()
    transport.send = lambda request: OpenAIResponsesHTTPResponse(  # type: ignore[method-assign]
        200,
        b"{}",
    )

    with pytest.raises(
        RuntimeError,
        match="REAL_TRANSPORT_INSTANCE_OVERRIDE",
    ):
        runner._attested_real_transport_evidence_scope(transport)


def test_caller_supplied_exact_real_transport_is_still_fake_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    transport = runner.UrllibOpenAIResponsesTransport()
    captured: dict[str, object] = {}

    def capture(database_url, *, transport, evidence_scope):
        captured["scope"] = evidence_scope
        return {"external_model_boundary": evidence_scope.external_model_boundary}

    monkeypatch.setattr(runner, "_execute_integration", capture)

    report = runner.run_integration(
        "redacted-database-url",
        transport=transport,
    )

    scope = captured["scope"]
    assert scope.real_external_transport_attested is False
    assert scope.transport_boundary == runner.FAKE_TRANSPORT_BOUNDARY
    assert report["external_model_boundary"] == "NOT_RUN"


def test_injected_transport_full_chain_report_cannot_claim_external_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAccounting:
        def __init__(self) -> None:
            self.zero_call_gates: list[str] = []

        def record_zero_call_gate(
            self,
            label: str,
            before: int,
            after: int,
        ) -> None:
            assert before == after
            self.zero_call_gates.append(label)

        def validate(self, observed_calls: int) -> None:
            assert observed_calls == 5

    class FakeScenario:
        def __init__(self, transport) -> None:
            self.budget = SimpleNamespace(used=4)
            self.accounting = FakeAccounting()
            self.executions = {
                label: label for label in EXPECTED_EXTERNAL_CALLS
            }

        def _repositories(self):
            return (
                object(),
                object(),
                object(),
                datetime(2026, 11, 24, tzinfo=timezone.utc),
            )

        def block_pending_after_p2(self, **kwargs):
            return SimpleNamespace(record=SimpleNamespace(
                disposition="BLOCKED",
                safe_reason_codes=("AUTHORIZATION_REVOKED",),
                response_dispatch_state=SimpleNamespace(
                    value="NOT_ATTEMPTED"
                ),
            ))

        def execute_zero_call_probe(self, *, spec, **kwargs):
            self.accounting.record_zero_call_gate(
                spec.label,
                self.budget.used,
                self.budget.used,
            )

        def execute_external_query(self, **kwargs):
            self.budget.used = 5

    def execution_summary(label: str) -> dict[str, object]:
        return {
            "label": label,
            "provider_receipt_digest": stable_hash(("receipt", label)),
            "output_token_count": 1,
        }

    monkeypatch.setenv(runner.INTEGRATION_FLAG, "1")
    monkeypatch.setattr(runner, "ExternalScenario", FakeScenario)
    monkeypatch.setattr(
        runner,
        "_run_day105_same_execution",
        lambda database_url, scenario: {
            "status": "PASS",
            "report_checksum": stable_hash("day105"),
        },
    )
    monkeypatch.setattr(
        runner,
        "PostgresRagSecurityRepository",
        lambda *args, **kwargs: SimpleNamespace(
            current_security_snapshot=lambda tenant: SimpleNamespace(
                snapshot_id="P2",
                revision=2,
            )
        ),
    )
    monkeypatch.setattr(runner, "_execution_summary", execution_summary)
    monkeypatch.setattr(
        runner,
        "_query_one",
        lambda *args, **kwargs: (5, 5, 1, 5),
    )
    monkeypatch.setattr(
        runner,
        "_durable_pre_restart_state",
        lambda factory: {
            "pre_restart_postmaster_started_at": (
                "2026-11-24T00:00:00+00:00"
            ),
            "pre_restart_state_digest": stable_hash("state"),
            "artifact_counts": {},
            "artifact_identity_count": 34,
        },
    )
    monkeypatch.setattr(
        runner,
        "_artifact_digests",
        lambda: {"synthetic_test_only": stable_hash("artifact")},
    )

    report = runner.run_integration(
        "redacted-database-url",
        transport=CountingFakeTransport(),
    )

    assert report["status"] == "PASS"
    assert report["schema_version"] == runner.FAKE_SCHEMA_VERSION
    assert report["scenario_id"] == runner.FAKE_SCENARIO_ID
    assert report["evidence_level"] == runner.FAKE_EVIDENCE_LEVEL
    assert report["transport_boundary"] == runner.FAKE_TRANSPORT_BOUNDARY
    assert report["transport_boundary_digest"] == (
        runner.FAKE_TRANSPORT_BOUNDARY_DIGEST
    )
    assert report["external_model_boundary"] == "NOT_RUN"
    assert str(report["run_id"]).startswith("day106-l3b-fake-")
