"""Read-only unit checks for the Day106 L3B restart runner."""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

from evals import run_day106_l3b_restart_replay as restart
from rag_chunking_contracts import stable_hash


def _identity_rows() -> tuple[tuple[str, str], ...]:
    return tuple(
        (artifact_type, stable_hash((artifact_type, index)))
        for artifact_type, count in restart.EXPECTED_ARTIFACT_COUNTS.items()
        for index in range(count)
    )


def test_durable_state_binds_pointer_security_and_all_identity_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = _identity_rows()

    def rows(_factory: object, query: str, params=()):
        if "FROM day104_l3.active_pointers" in query:
            return (("refund-serving", "G3", 9),)
        if "FROM day105_l3.current_security_snapshots" in query:
            return (("tenant-refund", "P2", 2),)
        if "SELECT artifact_type, identity_digest" in query:
            return tuple(sorted(identities))
        raise AssertionError("unexpected query")

    monkeypatch.setattr(restart, "_query_rows", rows)

    observed = restart._durable_state(object())

    expected = stable_hash((
        "DAY106_L3B_DURABLE_STATE_V1",
        (("refund-serving", "G3", 9),),
        (("tenant-refund", "P2", 2),),
        tuple(sorted(identities)),
    ))
    assert observed["state_digest"] == expected
    assert observed["artifact_counts"] == restart.EXPECTED_ARTIFACT_COUNTS
    assert observed["artifact_identity_count"] == 34


def test_durable_state_rejects_missing_provider_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = tuple(
        item for item in _identity_rows()
        if item[0] != "PROVIDER_RECEIPT"
    ) + tuple(
        item for item in _identity_rows()
        if item[0] == "PROVIDER_RECEIPT"
    )[:-1]

    def rows(_factory: object, query: str, params=()):
        if "FROM day104_l3.active_pointers" in query:
            return (("refund-serving", "G3", 9),)
        if "FROM day105_l3.current_security_snapshots" in query:
            return (("tenant-refund", "P2", 2),)
        return tuple(sorted(identities))

    monkeypatch.setattr(restart, "_query_rows", rows)

    with pytest.raises(AssertionError, match="ARTIFACT_COUNTS"):
        restart._durable_state(object())


def test_provider_summary_rejects_unknown_or_unreceipted_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        restart,
        "_query_one",
        lambda *args, **kwargs: (5, 4, 3, 0, 1, 5, 0, 50, 8, 58),
    )
    monkeypatch.setattr(
        restart,
        "_query_rows",
        lambda *args, **kwargs: ((1,), (2,), (3,), (4,)),
    )

    with pytest.raises(AssertionError, match="PROVIDER_OUTCOME"):
        restart._provider_summary(object())


def test_restart_queries_exclude_cross_tenant_and_unrelated_pointer_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = tuple(sorted(_identity_rows()))
    observed_scopes: set[str] = set()

    def rows(_factory: object, query: str, params=()):
        if "FROM day104_l3.active_pointers" in query:
            assert "WHERE pointer_name = %s" in query
            assert params == ("refund-serving",)
            observed_scopes.add("pointer")
            return (("refund-serving", "G3", 9),)
        if "FROM day105_l3.current_security_snapshots" in query:
            assert "WHERE tenant_id = %s" in query
            assert params == ("tenant-refund",)
            observed_scopes.add("security")
            return (("tenant-refund", "P2", 2),)
        if "SELECT artifact_type, identity_digest" in query:
            assert "WITH scoped_requests AS" in query
            assert "WHERE tenant_id = %s" in query
            assert "AND pointer_name = %s" in query
            assert "scoped_intents AS" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("durable-identities")
            return identities
        if "SELECT receipt.call_ordinal" in query:
            assert "request.tenant_id = %s" in query
            assert "request.pointer_name = %s" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("provider-ordinals")
            return ((1,), (2,), (3,), (4,), (5,))
        raise AssertionError("unexpected rows query")

    def one(_factory: object, query: str, params=()):
        if "coalesce(sum(receipt.input_token_count)" in query:
            assert "WITH scoped_requests AS" in query
            assert "WHERE tenant_id = %s" in query
            assert "AND pointer_name = %s" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("provider-summary")
            return (5, 5, 5, 0, 0, 5, 0, 50, 8, 58)
        if "LEFT JOIN day106_l3.model_invocations" in query:
            assert "request.tenant_id = %s" in query
            assert "request.pointer_name = %s" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("provider-cross-binding")
            return (0,)
        if "receipt.answer_candidate_digest" in query:
            assert "request.tenant_id = %s" in query
            assert "request.pointer_name = %s" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("release-cross-binding")
            return (0,)
        if "sum(receipt.unauthorized_prompt_count)" in query:
            assert "request.tenant_id = %s" in query
            assert "request.pointer_name = %s" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("prompt-summary")
            return (0,)
        if "day106_l3.current_response_states" in query:
            assert "WITH scoped_requests AS" in query
            assert "WHERE tenant_id = %s" in query
            assert "AND pointer_name = %s" in query
            assert "JOIN scoped_intents AS intent" in query
            assert params == ("tenant-refund", "refund-serving")
            observed_scopes.add("decision-dispatch-summary")
            return (5, 4, 1, 1, 4, 4, 0, 0)
        raise AssertionError("unexpected one query")

    monkeypatch.setattr(restart, "_query_rows", rows)
    monkeypatch.setattr(restart, "_query_one", one)

    restart._durable_state(object())
    restart._provider_summary(object())
    restart._cross_binding_summary(object())
    restart._decision_summary(object())

    assert observed_scopes == {
        "pointer",
        "security",
        "durable-identities",
        "provider-summary",
        "provider-ordinals",
        "provider-cross-binding",
        "release-cross-binding",
        "prompt-summary",
        "decision-dispatch-summary",
    }


def test_exclusive_restart_evidence_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "restart.json"
    report = {"status": "PASS"}

    restart._write_exclusive(target, report)

    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        restart._write_exclusive(target, report)


def test_restart_rejects_non_attested_initial_transport(tmp_path: Path) -> None:
    report: dict[str, object] = {
        "schema_version": restart.INTEGRATION_SCHEMA_VERSION,
        "scenario_id": restart.SCENARIO_ID,
        "status": "PASS",
        "external_call_count": 5,
        "transport_boundary": "INJECTED_NON_ATTESTED_TRANSPORT",
        "transport_boundary_digest": stable_hash("fake-transport"),
        "external_model_boundary": "PASS",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "restart_evidence": {
            "status": "PRE_RESTART_SEALED",
            "pre_restart_state_digest": stable_hash("state"),
            "pre_restart_postmaster_started_at": "2026-11-24T00:00:00+00:00",
            "post_restart_state_digest": None,
            "post_restart_postmaster_started_at": None,
        },
    }
    report["report_checksum"] = stable_hash(report)
    path = tmp_path / "fake-initial.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(AssertionError, match="INITIAL_REPORT_SCOPE_MISMATCH"):
        restart._load_initial_report(path)
