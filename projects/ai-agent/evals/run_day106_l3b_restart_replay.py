"""Fresh-process restart readback for the Day106 L3B external-model run.

This runner is deliberately read-only.  It never installs schemas, resets the
database, constructs a Provider transport, or reads ``OPENAI_API_KEY``.  It
compares the post-restart durable identities with the state sealed by the L3B
integration report and emits only content-safe identities, digests, counts,
states, and timestamps.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    psycopg2_connection_factory,
)


SCHEMA_VERSION = "day106-l3b-restart-replay.v1"
INTEGRATION_SCHEMA_VERSION = "day106-l3b-external-evidence.v1"
SCENARIO_ID = "day106-production-rag-db-external-provider-l3b-v1"
INTEGRATION_FLAG = "DAY106_L3B_INTEGRATION"
DATABASE_URL_ENV = "DAY106_L3_DATABASE_URL"
REAL_TRANSPORT_BOUNDARY = "REAL_URLLIB_OPENAI_RESPONSES_HTTPS"
REAL_TRANSPORT_BOUNDARY_DIGEST = stable_hash((
    "DAY106_L3B_TRANSPORT_BOUNDARY_V1",
    "UrllibOpenAIResponsesTransport",
    "https://api.openai.com/v1/responses",
    "stdlib-urllib",
    "NO_RETRY",
))
EXPECTED_ARTIFACT_COUNTS = {
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


def _query_one(
    factory: ConnectionFactory,
    query: str,
    params: tuple[object, ...] = (),
) -> Sequence[Any] | None:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def _query_rows(
    factory: ConnectionFactory,
    query: str,
    params: tuple[object, ...] = (),
) -> tuple[tuple[Any, ...], ...]:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        return tuple(tuple(row) for row in cursor.fetchall())
    finally:
        cursor.close()
        connection.close()


def _isoformat(value: object, reason: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AssertionError(reason)
    return value.isoformat()


def _validate_checksum(report: dict[str, object], reason: str) -> str:
    saved = report.get("report_checksum")
    if not isinstance(saved, str):
        raise AssertionError(f"{reason}_CHECKSUM_MISSING")
    unsigned = dict(report)
    unsigned.pop("report_checksum", None)
    if stable_hash(unsigned) != saved:
        raise AssertionError(f"{reason}_CHECKSUM_MISMATCH")
    return saved


def _load_initial_report(path: Path) -> tuple[dict[str, object], str]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise AssertionError("INITIAL_REPORT_MUST_BE_OBJECT")
    checksum = _validate_checksum(report, "INITIAL_REPORT")
    if (
        report.get("schema_version") != INTEGRATION_SCHEMA_VERSION
        or report.get("scenario_id") != SCENARIO_ID
        or report.get("status") != "PASS"
        or report.get("external_call_count") != 5
        or report.get("transport_boundary") != REAL_TRANSPORT_BOUNDARY
        or report.get("transport_boundary_digest")
        != REAL_TRANSPORT_BOUNDARY_DIGEST
        or report.get("external_model_boundary") != "PASS"
        or report.get("production_readiness") != "MORE_EVIDENCE_NEEDED"
    ):
        raise AssertionError("INITIAL_REPORT_SCOPE_MISMATCH")
    restart = report.get("restart_evidence")
    if not isinstance(restart, dict):
        raise AssertionError("INITIAL_RESTART_EVIDENCE_MISSING")
    if (
        restart.get("status") != "PRE_RESTART_SEALED"
        or not isinstance(restart.get("pre_restart_state_digest"), str)
        or not isinstance(
            restart.get("pre_restart_postmaster_started_at"), str
        )
        or restart.get("post_restart_state_digest") is not None
        or restart.get("post_restart_postmaster_started_at") is not None
    ):
        raise AssertionError("INITIAL_RESTART_SEAL_INVALID")
    return report, checksum


def _durable_state(factory: ConnectionFactory) -> dict[str, object]:
    pointer_rows = _query_rows(
        factory,
        """
        SELECT pointer_name, generation_id, revision
        FROM day104_l3.active_pointers
        WHERE pointer_name = %s
        ORDER BY pointer_name
        """,
        ("refund-serving",),
    )
    security_rows = _query_rows(
        factory,
        """
        SELECT tenant_id, snapshot_id, revision
        FROM day105_l3.current_security_snapshots
        WHERE tenant_id = %s
        ORDER BY tenant_id
        """,
        ("tenant-refund",),
    )
    identity_rows = _query_rows(
        factory,
        """
        WITH scoped_requests AS (
          SELECT identity_digest
          FROM day106_l3.request_bindings
          WHERE tenant_id = %s
            AND pointer_name = %s
        ), scoped_intents AS (
          SELECT intent.intent_id
          FROM day106_l3.response_intents AS intent
          JOIN scoped_requests AS request
            ON request.identity_digest = intent.request_binding_digest
        )
        SELECT artifact_type, identity_digest
        FROM (
          SELECT 'REQUEST_BINDING' AS artifact_type, binding.identity_digest
            FROM day106_l3.request_bindings AS binding
            JOIN scoped_requests AS request
              ON request.identity_digest = binding.identity_digest
          UNION ALL
          SELECT 'RETRIEVAL_CONTEXT_RECEIPT', receipt.identity_digest
            FROM day106_l3.retrieval_context_receipts AS receipt
            JOIN scoped_requests AS request
              ON request.identity_digest = receipt.request_binding_digest
          UNION ALL
          SELECT 'MODEL_INVOCATION', invocation.identity_digest
            FROM day106_l3.model_invocations AS invocation
            JOIN scoped_requests AS request
              ON request.identity_digest = invocation.request_binding_digest
          UNION ALL
          SELECT 'PROVIDER_ATTEMPT', attempt.identity_digest
            FROM day106_l3.provider_call_attempts AS attempt
            JOIN scoped_requests AS request
              ON request.identity_digest = attempt.request_binding_digest
          UNION ALL
          SELECT 'PROVIDER_RECEIPT', receipt.identity_digest
            FROM day106_l3.provider_call_receipts AS receipt
            JOIN scoped_requests AS request
              ON request.identity_digest = receipt.request_binding_digest
          UNION ALL
          SELECT 'ANSWER_RELEASE', release_record.identity_digest
            FROM day106_l3.answer_release_records AS release_record
            JOIN scoped_requests AS request
              ON request.identity_digest = release_record.request_binding_digest
          UNION ALL
          SELECT 'RESPONSE_INTENT', intent.identity_digest
            FROM day106_l3.response_intents AS intent
            JOIN scoped_intents AS scoped
              ON scoped.intent_id = intent.intent_id
          UNION ALL
          SELECT 'DISPATCH_WINNER', winner.identity_digest
            FROM day106_l3.dispatch_winners AS winner
            JOIN scoped_intents AS intent
              ON intent.intent_id = winner.response_intent_id
          UNION ALL
          SELECT 'DISPATCH_RECORD', record.identity_digest
            FROM day106_l3.dispatch_recovery_delivery_records AS record
            JOIN scoped_intents AS intent
              ON intent.intent_id = record.response_intent_id
        ) AS durable
        ORDER BY artifact_type, identity_digest
        """,
        ("tenant-refund", "refund-serving"),
    )
    pointer = tuple(
        (str(name), str(generation), int(revision))
        for name, generation, revision in pointer_rows
    )
    security = tuple(
        (str(tenant), str(snapshot), int(revision))
        for tenant, snapshot, revision in security_rows
    )
    identities = tuple(
        (str(artifact_type), str(identity_digest))
        for artifact_type, identity_digest in identity_rows
    )
    counts = dict(EXPECTED_ARTIFACT_COUNTS)
    for key in counts:
        counts[key] = sum(1 for name, _ in identities if name == key)
    if counts != EXPECTED_ARTIFACT_COUNTS:
        raise AssertionError("RESTART_ARTIFACT_COUNTS_MISMATCH")
    if pointer != (("refund-serving", "G3", 9),):
        raise AssertionError("RESTART_POINTER_MISMATCH")
    if security != (("tenant-refund", "P2", 2),):
        raise AssertionError("RESTART_SECURITY_SNAPSHOT_MISMATCH")
    return {
        "state_digest": stable_hash((
            "DAY106_L3B_DURABLE_STATE_V1",
            pointer,
            security,
            identities,
        )),
        "artifact_counts": counts,
        "artifact_identity_count": len(identities),
    }


def _provider_summary(factory: ConnectionFactory) -> dict[str, object]:
    row = _query_one(
        factory,
        """
        WITH scoped_requests AS (
          SELECT identity_digest
          FROM day106_l3.request_bindings
          WHERE tenant_id = %s
            AND pointer_name = %s
        )
        SELECT
          (SELECT count(*) FROM day106_l3.provider_call_attempts AS attempt
             JOIN scoped_requests AS request
               ON request.identity_digest = attempt.request_binding_digest),
          (SELECT count(*) FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest),
          (SELECT count(*) FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest
             WHERE receipt.status = 'SUCCEEDED'),
          (SELECT count(*) FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest
             WHERE receipt.status = 'FAILED'),
          (SELECT count(*) FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest
             WHERE receipt.status = 'UNKNOWN'),
          (SELECT count(*) FROM day106_l3.model_invocations AS invocation
             JOIN scoped_requests AS request
               ON request.identity_digest = invocation.request_binding_digest
             WHERE invocation.provider_mode = 'EXTERNAL'),
          (SELECT count(*) FROM day106_l3.model_invocations AS invocation
             JOIN scoped_requests AS request
               ON request.identity_digest = invocation.request_binding_digest
             WHERE invocation.provider_mode <> 'EXTERNAL'),
          (SELECT coalesce(sum(receipt.input_token_count), 0)
             FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest),
          (SELECT coalesce(sum(receipt.output_token_count), 0)
             FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest),
          (SELECT coalesce(sum(receipt.total_token_count), 0)
             FROM day106_l3.provider_call_receipts AS receipt
             JOIN scoped_requests AS request
               ON request.identity_digest = receipt.request_binding_digest)
        """,
        ("tenant-refund", "refund-serving"),
    )
    if row is None:
        raise AssertionError("RESTART_PROVIDER_SUMMARY_MISSING")
    ordinals = tuple(
        int(item[0])
        for item in _query_rows(
            factory,
            """
            SELECT receipt.call_ordinal
            FROM day106_l3.provider_call_receipts AS receipt
            JOIN day106_l3.request_bindings AS request
              ON request.identity_digest = receipt.request_binding_digest
            WHERE request.tenant_id = %s
              AND request.pointer_name = %s
            ORDER BY receipt.call_ordinal, receipt.receipt_id
            """,
            ("tenant-refund", "refund-serving"),
        )
    )
    values = tuple(int(value) for value in row)
    if values[:7] != (5, 5, 5, 0, 0, 5, 0):
        raise AssertionError("RESTART_PROVIDER_OUTCOME_MISMATCH")
    if ordinals != (1, 2, 3, 4, 5):
        raise AssertionError("RESTART_PROVIDER_ORDINAL_MISMATCH")
    if values[8] > 320 or values[9] != values[7] + values[8]:
        raise AssertionError("RESTART_PROVIDER_TOKEN_BUDGET_MISMATCH")
    return {
        "attempt_count": values[0],
        "receipt_count": values[1],
        "succeeded_receipt_count": values[2],
        "failed_receipt_count": values[3],
        "unknown_receipt_count": values[4],
        "unreceipted_attempt_count": values[0] - values[1],
        "external_model_invocation_count": values[5],
        "other_model_invocation_count": values[6],
        "call_ordinals": list(ordinals),
        "input_token_count": values[7],
        "output_token_count": values[8],
        "total_token_count": values[9],
        "reconciliation_required": False,
        "blind_retry_allowed": False,
    }


def _cross_binding_summary(factory: ConnectionFactory) -> dict[str, int]:
    provider = _query_one(
        factory,
        """
        SELECT count(*)
        FROM day106_l3.provider_call_attempts AS attempt
        JOIN day106_l3.request_bindings AS request
          ON request.identity_digest = attempt.request_binding_digest
        LEFT JOIN day106_l3.model_invocations AS invocation
          ON invocation.model_invocation_id = attempt.model_invocation_id
         AND invocation.model_invocation_digest = attempt.model_invocation_digest
         AND invocation.request_binding_digest = attempt.request_binding_digest
         AND invocation.retrieval_context_receipt_digest =
             attempt.retrieval_context_receipt_digest
        LEFT JOIN day106_l3.provider_call_receipts AS receipt
          ON receipt.provider_attempt_id = attempt.attempt_id
         AND receipt.model_invocation_id = attempt.model_invocation_id
         AND receipt.model_invocation_digest = attempt.model_invocation_digest
         AND receipt.request_binding_digest = attempt.request_binding_digest
         AND receipt.retrieval_context_receipt_digest =
             attempt.retrieval_context_receipt_digest
         AND receipt.call_ordinal = attempt.call_ordinal
        WHERE request.tenant_id = %s
          AND request.pointer_name = %s
          AND (invocation.model_invocation_id IS NULL
               OR receipt.receipt_id IS NULL)
        """,
        ("tenant-refund", "refund-serving"),
    )
    release = _query_one(
        factory,
        """
        SELECT count(*)
        FROM day106_l3.answer_release_records AS release_record
        JOIN day106_l3.request_bindings AS request
          ON request.identity_digest = release_record.request_binding_digest
        JOIN day106_l3.model_invocations AS invocation
          ON invocation.model_invocation_id = release_record.model_invocation_id
         AND invocation.model_invocation_digest = release_record.model_invocation_digest
        LEFT JOIN day106_l3.provider_call_receipts AS receipt
          ON receipt.request_binding_digest = release_record.request_binding_digest
         AND receipt.retrieval_context_receipt_digest =
             release_record.retrieval_context_receipt_digest
         AND receipt.model_invocation_id = release_record.model_invocation_id
         AND receipt.model_invocation_digest = release_record.model_invocation_digest
         AND receipt.answer_candidate_digest = release_record.answer_candidate_digest
         AND receipt.status = 'SUCCEEDED'
        WHERE request.tenant_id = %s
          AND request.pointer_name = %s
          AND invocation.provider_mode = 'EXTERNAL'
          AND release_record.result = 'PASS'
          AND release_record.disposition = 'RELEASE'
          AND receipt.receipt_id IS NULL
        """,
        ("tenant-refund", "refund-serving"),
    )
    unauthorized = _query_one(
        factory,
        """
        SELECT coalesce(sum(receipt.unauthorized_prompt_count), 0)
        FROM day106_l3.retrieval_context_receipts AS receipt
        JOIN day106_l3.request_bindings AS request
          ON request.identity_digest = receipt.request_binding_digest
        WHERE request.tenant_id = %s
          AND request.pointer_name = %s
        """,
        ("tenant-refund", "refund-serving"),
    )
    if provider is None or release is None or unauthorized is None:
        raise AssertionError("RESTART_CROSS_BINDING_SUMMARY_MISSING")
    summary = {
        "provider_cross_binding_mismatch_count": int(provider[0]),
        "release_provider_binding_mismatch_count": int(release[0]),
        "unauthorized_prompt_count": int(unauthorized[0]),
    }
    if any(summary.values()):
        raise AssertionError("RESTART_CROSS_BINDING_MISMATCH")
    return summary


def _decision_summary(factory: ConnectionFactory) -> dict[str, object]:
    row = _query_one(
        factory,
        """
        WITH scoped_requests AS (
          SELECT identity_digest
          FROM day106_l3.request_bindings
          WHERE tenant_id = %s
            AND pointer_name = %s
        ), scoped_intents AS (
          SELECT intent.intent_id
          FROM day106_l3.response_intents AS intent
          JOIN scoped_requests AS request
            ON request.identity_digest = intent.request_binding_digest
        )
        SELECT count(*),
               count(*) FILTER (WHERE release_record.disposition = 'RELEASE'),
               count(*) FILTER (WHERE release_record.disposition = 'BLOCKED'),
               count(*) FILTER (
                   WHERE release_record.response_dispatch_state = 'NOT_ATTEMPTED'
               ),
               (SELECT count(*) FROM scoped_intents),
               (SELECT count(*)
                  FROM day106_l3.current_response_states AS state
                  JOIN scoped_intents AS intent
                    ON intent.intent_id = state.intent_id
                 WHERE state.state = 'PENDING'),
               (SELECT count(*)
                  FROM day106_l3.dispatch_winners AS winner
                  JOIN scoped_intents AS intent
                    ON intent.intent_id = winner.response_intent_id),
               (SELECT count(*)
                  FROM day106_l3.dispatch_recovery_delivery_records AS record
                  JOIN scoped_intents AS intent
                    ON intent.intent_id = record.response_intent_id)
        FROM day106_l3.answer_release_records AS release_record
        JOIN scoped_requests AS request
          ON request.identity_digest = release_record.request_binding_digest
        """,
        ("tenant-refund", "refund-serving"),
    )
    if row is None:
        raise AssertionError("RESTART_DECISION_SUMMARY_MISSING")
    values = tuple(int(value) for value in row)
    if values != (5, 4, 1, 1, 4, 4, 0, 0):
        raise AssertionError("RESTART_DECISION_STATE_MISMATCH")
    return {
        "decision_count": values[0],
        "released_count": values[1],
        "blocked_count": values[2],
        "not_attempted_count": values[3],
        "response_intent_count": values[4],
        "pending_response_state_count": values[5],
        "dispatch_winner_count": values[6],
        "dispatch_record_count": values[7],
    }


def run_restart_replay(
    database_url: str,
    initial_report: dict[str, object],
    initial_checksum: str,
) -> dict[str, object]:
    if os.environ.get(INTEGRATION_FLAG) != "1":
        raise RuntimeError("DAY106_L3B_INTEGRATION_FLAG_REQUIRED")
    if not database_url.strip():
        raise ValueError("DAY106_L3_DATABASE_URL_REQUIRED")

    started = datetime.now(timezone.utc)
    factory = psycopg2_connection_factory(
        database_url,
        application_name="day106-l3b-fresh-process-restart-replay",
    )
    environment = _query_one(
        factory,
        """
        SELECT current_database(), current_setting('server_version'),
               (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
               pg_postmaster_start_time()
        """,
    )
    if (
        environment is None
        or environment[0] != "day106_l3"
        or environment[2] is None
    ):
        raise AssertionError("RESTART_DATABASE_IDENTITY_MISMATCH")
    postmaster = _isoformat(environment[3], "RESTART_POSTMASTER_INVALID")
    initial_restart = initial_report["restart_evidence"]
    if not isinstance(initial_restart, dict):
        raise AssertionError("INITIAL_RESTART_EVIDENCE_MISSING")
    if postmaster == initial_restart["pre_restart_postmaster_started_at"]:
        raise AssertionError("DATABASE_CONTAINER_DID_NOT_RESTART")

    durable = _durable_state(factory)
    if durable["state_digest"] != initial_restart["pre_restart_state_digest"]:
        raise AssertionError("RESTART_DURABLE_STATE_CHANGED")
    provider = _provider_summary(factory)
    cross_binding = _cross_binding_summary(factory)
    decisions = _decision_summary(factory)
    completed = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "run_id": "day106-l3b-restart-" + stable_hash((
            started.isoformat(),
            durable["state_digest"],
        ))[7:23],
        "status": "PASS",
        "source_integration_report_checksum": initial_checksum,
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "postmaster_started_at": postmaster,
        "database_identity_digest": stable_hash((
            "day106_l3",
            str(environment[1]),
            str(environment[2]),
        )),
        "generation_id": "G3",
        "pointer_revision": 9,
        "authorization_snapshot_id": "P2",
        "authorization_revision": 2,
        "durable_state_digest": durable["state_digest"],
        "artifact_counts": durable["artifact_counts"],
        "artifact_identity_count": durable["artifact_identity_count"],
        "provider_summary": provider,
        "cross_binding_summary": cross_binding,
        "decision_summary": decisions,
        "schemas_reinstalled": False,
        "schemas_reset": False,
        "external_provider_called": False,
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "raw_provider_response_logged": False,
        "raw_provider_response_id_logged": False,
        "raw_secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _fail_closed(reason: str, error_type: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL_CLOSED",
        "safe_reason": reason,
        "external_provider_called": False,
        "blind_retry_allowed": False,
        "raw_content_logged": False,
        "raw_secret_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    if error_type is not None:
        payload["error_type"] = error_type
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _write_exclusive(path: Path, report: dict[str, object]) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-report", required=True, type=Path)
    parser.add_argument("--report-path", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.report_path.exists():
        print(json.dumps(
            _fail_closed("DAY106_L3B_RESTART_REPORT_ALREADY_EXISTS"),
            indent=2,
            sort_keys=True,
        ))
        return 2
    try:
        initial, checksum = _load_initial_report(arguments.integration_report)
        report = run_restart_replay(
            os.environ.get(DATABASE_URL_ENV, ""),
            initial,
            checksum,
        )
        _write_exclusive(arguments.report_path, report)
    except Exception as exc:
        print(json.dumps(
            _fail_closed(
                "DAY106_L3B_RESTART_REPLAY_FAILED",
                type(exc).__name__,
            ),
            indent=2,
            sort_keys=True,
        ))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
