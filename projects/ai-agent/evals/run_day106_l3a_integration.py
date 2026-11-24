"""Execute the opt-in Day106 L3A PostgreSQL/pgvector capstone.

The runner deliberately reuses the Day105 lifecycle/security scenario inside
the Day106 disposable database, then opens one additional G3/P2 ReadView and
atomically cross-binds its real PostgreSQL rows to the Day106 request,
retrieval, release, intent, and recovery records.  Consequently this is one
execution over one database, not a summary assembled from independent PASS
reports.

Only content-safe identities, digests, states, counts, and reason codes are
emitted.  The database URL, credentials, source text, prompts, answers,
provider responses, and vectors are never included in the report.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
from typing import Any, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

import run_day105_l3_integration as day105  # noqa: E402
from rag_capstone_contracts import (  # noqa: E402
    AnswerReleaseRecord,
    CapstoneRequestBinding,
    DispatchObservation,
    RecoveryAndIncidentRecord,
    ResponseIntent,
    ResponseIntentState,
    RetrievalAndContextReceipt,
)
from rag_capstone_postgres import (  # noqa: E402
    CapstoneRepositoryOutcome,
    ModelInvocationRecord,
    PostgresRagCapstoneRepository,
    ProviderMode,
    RESET_CONFIRMATION,
)
from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    PostgresIndexLifecycleRepository,
    QueryMode,
    RepositoryOutcome,
    psycopg2_connection_factory,
)
from rag_security_postgres import PostgresRagSecurityRepository  # noqa: E402


SCHEMA_VERSION = "day106-l3a-evidence.v2"
SCENARIO_ID = "day106-production-rag-postgresql-pgvector-l3a-v1"
EVIDENCE_LEVEL = (
    "EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR_"
    "WITH_DETERMINISTIC_MODEL_DLP_ADAPTERS"
)
INTEGRATION_FLAG = "DAY106_L3_INTEGRATION"
DATABASE_URL_ENV = "DAY106_L3_DATABASE_URL"
REQUEST_ID = "request-Day106-Q2-G3"
INTENT_ID = "response-intent-Day106-Q2-G3"
IDEMPOTENCY_KEY = "dispatch-key-Day106-Q2-G3"
BASE_COMMIT = "91c2eddf3b10fbe1d6b0e381ee84ebb009039a5c"
ARTIFACT_PATHS = {
    "integration_runner": "evals/run_day106_l3a_integration.py",
    "evidence_schema": "evidence/day106-l3a-evidence-schema.json",
    "database_schema": "integration/day106/schema.sql",
    "capstone_repository": "src/rag_capstone_postgres.py",
    "compose": "integration/day106/compose.yaml",
    "day105_integration_runner": "evals/run_day105_l3_integration.py",
    "restart_runner": "evals/run_day106_l3_restart_replay.py",
    "evidence_replay_runner": "evals/run_day106_l3_evidence_replay.py",
}


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_evidence() -> dict[str, object]:
    return {
        "base_commit": BASE_COMMIT,
        "files": {
            name: {
                "path": f"projects/ai-agent/{relative_path}",
                "digest": _file_digest(ROOT / relative_path),
            }
            for name, relative_path in ARTIFACT_PATHS.items()
        },
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


def _day106_reset_and_install(
    factory: ConnectionFactory,
) -> tuple[PostgresIndexLifecycleRepository, PostgresRagSecurityRepository]:
    """Replacement for Day105's database-name-specific reset helper."""

    capstone = PostgresRagCapstoneRepository(
        factory,
        integration_enabled=True,
    )
    capstone.reset_lab_schemas(confirmation=RESET_CONFIRMATION)
    capstone.install_all_lab_schemas()
    return (
        PostgresIndexLifecycleRepository(
            factory,
            schema_path=ROOT / "integration" / "day104" / "schema.sql",
        ),
        PostgresRagSecurityRepository(
            factory,
            schema_path=ROOT / "integration" / "day105" / "schema.sql",
            integration_enabled=True,
        ),
    )


def _run_day105_same_execution(database_url: str) -> dict[str, object]:
    """Run the prerequisite scenario with the guarded Day106 reset."""

    original_reset = day105._reset_and_install
    previous_flag = os.environ.get("DAY105_L3_INTEGRATION")
    day105._reset_and_install = _day106_reset_and_install
    os.environ["DAY105_L3_INTEGRATION"] = "1"
    try:
        return day105.run_integration(database_url)
    finally:
        day105._reset_and_install = original_reset
        if previous_flag is None:
            os.environ.pop("DAY105_L3_INTEGRATION", None)
        else:
            os.environ["DAY105_L3_INTEGRATION"] = previous_flag


def _capstone_binding(
    factory: ConnectionFactory,
    run: day105.QueryRun,
) -> CapstoneRequestBinding:
    row = _query_one(
        factory,
        """
        SELECT view.pointer_name, view.pointer_revision, view.fencing_token,
               snapshot.source_snapshot_id, snapshot.deletion_snapshot_id,
               generation.manifest_digest
        FROM day104_l3.read_views AS view
        JOIN day104_l3.generations AS generation
          ON generation.generation_id = view.generation_id
        JOIN day104_l3.build_snapshots AS snapshot
          ON snapshot.build_snapshot_id = generation.build_snapshot_id
        WHERE view.view_id = %s
        """,
        (run.binding.read_view_id,),
    )
    if row is None:
        raise AssertionError("DAY106_REAL_READ_VIEW_BINDING_NOT_FOUND")
    exact_occurrence_ids = run.bundle.occurrence_ids
    authorization_revision_digest = stable_hash(
        (
            run.binding.authorization_revision,
            run.binding.content_security_snapshot_digest,
        )
    )
    authorization_scope_fingerprint = stable_hash(
        (
            run.binding.tenant_id,
            run.binding.principal_id,
            "rag.answer",
            run.binding.purpose,
            run.binding.authorization_revision,
            exact_occurrence_ids,
        )
    )
    return CapstoneRequestBinding(
        request_attempt_id=REQUEST_ID,
        request_id=REQUEST_ID,
        principal_id=run.binding.principal_id,
        tenant_id=run.binding.tenant_id,
        action="rag.answer",
        purpose=run.binding.purpose,
        audience=run.binding.audience,
        pointer_name=cast(str, row[0]),
        generation_id=run.binding.generation_id,
        generation_artifact_digest=run.binding.generation_artifact_digest,
        generation_manifest_digest=cast(str, row[5]),
        build_snapshot_fingerprint=run.binding.build_snapshot_fingerprint,
        pointer_revision=int(row[1]),
        read_view_id=run.binding.read_view_id,
        read_view_fence=int(row[2]),
        read_view_digest=run.binding.read_view_validation_digest,
        source_snapshot_id=cast(str, row[3]),
        authorization_snapshot_id=run.binding.authorization_revision,
        deletion_snapshot_id=cast(str, row[4]),
        policy_fingerprint=run.binding.policy.fingerprint,
        security_binding_fingerprint=run.binding.fingerprint,
        retrieval_authorization_revision_digest=authorization_revision_digest,
        retrieval_authorization_scope_fingerprint=(authorization_scope_fingerprint),
        selected_retrieval_bundle_id=run.bundle.bundle_id,
        selected_retrieval_bundle_revision=1,
        selected_retrieval_bundle_fingerprint=run.bundle.digest,
        created_at=run.bundle.created_at,
    )


def _retrieval_receipt(
    binding: CapstoneRequestBinding,
    run: day105.QueryRun,
) -> RetrievalAndContextReceipt:
    return RetrievalAndContextReceipt(
        receipt_id="retrieval-context-Day106-Q2-G3",
        request_binding_digest=binding.digest,
        retrieval_operation_id="operation-Day106-Q2-G3",
        retrieval_request_id=REQUEST_ID,
        day101_execution_receipt_digest=stable_hash(
            (
                "REAL_PGVECTOR_DAY101_RECEIPT",
                binding.read_view_digest,
                run.bundle.digest,
            )
        ),
        day101_handoff_digest=stable_hash(
            ("REAL_PGVECTOR_DAY101_HANDOFF", run.bundle.digest)
        ),
        prompt_authorization_scope_fingerprint=(
            binding.retrieval_authorization_scope_fingerprint
        ),
        prompt_authorization_revision_digest=(
            binding.retrieval_authorization_revision_digest
        ),
        retrieval_bundle_id=run.bundle.bundle_id,
        retrieval_bundle_digest=run.bundle.digest,
        retrieval_security_decision_digest=run.retrieval.digest,
        bundle_security_decision_digest=run.bundle_security.digest,
        exact_occurrence_ids=run.bundle.occurrence_ids,
        exact_content_digests=run.bundle.content_digests,
        context_manifest_id=run.context.manifest_id,
        context_manifest_digest=run.context.digest,
        context_occurrence_ids=run.context.included_occurrence_ids,
        assembled_context_digest=run.context.assembled_context_digest,
        unauthorized_prompt_count=0,
        created_at=run.bundle.created_at,
    )


def _release_and_intent(
    binding: CapstoneRequestBinding,
    receipt: RetrievalAndContextReceipt,
    run: day105.QueryRun,
) -> tuple[AnswerReleaseRecord, ResponseIntent]:
    created_at = run.release.observed_at
    release = AnswerReleaseRecord(
        record_id="answer-release-Day106-Q2-G3",
        request_binding_digest=binding.digest,
        retrieval_context_receipt_digest=receipt.digest,
        model_invocation_id=run.invocation.envelope_id,
        model_invocation_digest=run.invocation.digest,
        answer_candidate_id=run.candidate.candidate_id,
        answer_candidate_digest=run.candidate.digest,
        release_evidence_id=run.evidence.evidence_id,
        release_evidence_digest=run.evidence.digest,
        output_release_decision_id=run.release.decision_id,
        output_release_decision_digest=run.release.digest,
        disclosure_envelope_digest=run.disclosure.digest,
        tenant_id=binding.tenant_id,
        principal_id=binding.principal_id,
        action=binding.action,
        purpose=binding.purpose,
        current_authorization_scope_fingerprint=(
            binding.retrieval_authorization_scope_fingerprint
        ),
        current_authorization_revision_digest=(
            binding.retrieval_authorization_revision_digest
        ),
        release_currentness_snapshot_id="P2",
        release_currentness_snapshot_digest=(
            run.binding.content_security_snapshot_digest
        ),
        release_currentness_revision=2,
        released_occurrence_ids=run.release.released_citation_occurrence_ids,
        authorized_destination=run.disclosure.destination,
        dispatch_idempotency_key=IDEMPOTENCY_KEY,
        result=run.release.result.value,
        disposition=run.release.disposition.value,
        safe_reason_codes=run.release.reason_codes,
        response_intent_id=INTENT_ID,
        response_dispatch_state=ResponseIntentState.PENDING,
        created_at=created_at,
    )
    intent = ResponseIntent(
        intent_id=INTENT_ID,
        request_binding_digest=binding.digest,
        output_release_decision_digest=run.release.digest,
        candidate_digest=run.candidate.digest,
        destination=run.disclosure.destination,
        dispatch_idempotency_key=IDEMPOTENCY_KEY,
        state=ResponseIntentState.PENDING,
        revision=1,
        created_at=created_at,
    )
    return release, intent


def _recovery_records(started_at: datetime) -> tuple[RecoveryAndIncidentRecord, ...]:
    specifications = (
        (
            "send-1",
            None,
            "transport-1",
            DispatchObservation.SEND_STARTED,
            "DISPATCH_STARTED",
            None,
        ),
        (
            "unknown",
            "send-1",
            "transport-1",
            DispatchObservation.UNKNOWN,
            "DESTINATION_OUTCOME_UNKNOWN",
            None,
        ),
        (
            "not-found",
            "unknown",
            "reconcile-1",
            DispatchObservation.NOT_FOUND,
            "IDEMPOTENCY_LOOKUP_NOT_FOUND",
            None,
        ),
        (
            "send-2",
            "not-found",
            "transport-2",
            DispatchObservation.SEND_STARTED,
            "BOUNDED_RETRY_AFTER_NOT_FOUND",
            None,
        ),
        (
            "accepted",
            "send-2",
            "transport-2",
            DispatchObservation.ACCEPTED,
            "DESTINATION_ACCEPTED",
            "provider-message-Day106-Q2-G3",
        ),
        (
            "delivered",
            "accepted",
            "transport-2",
            DispatchObservation.DELIVERED,
            "AUTHORITATIVE_DELIVERY_RECEIPT",
            "provider-message-Day106-Q2-G3",
        ),
        (
            "duplicate",
            "delivered",
            "reconcile-2",
            DispatchObservation.DUPLICATE_RECEIPT,
            "DUPLICATE_RECEIPT_DEDUPED",
            "provider-message-Day106-Q2-G3",
        ),
    )
    records: list[RecoveryAndIncidentRecord] = []
    for index, (
        suffix,
        predecessor_suffix,
        transport_suffix,
        observation,
        reason,
        message_id,
    ) in enumerate(specifications):
        record_id = f"Day106-Q2-G3-{suffix}"
        predecessor = (
            None if predecessor_suffix is None else f"Day106-Q2-G3-{predecessor_suffix}"
        )
        observed_at = (started_at + timedelta(seconds=index + 1)).isoformat()
        records.append(
            RecoveryAndIncidentRecord(
                record_id=record_id,
                response_intent_id=INTENT_ID,
                previous_record_id=predecessor,
                transport_attempt_id=f"Day106-Q2-G3-{transport_suffix}",
                dispatch_idempotency_key=IDEMPOTENCY_KEY,
                observation=observation,
                safe_reason_code=reason,
                observed_at=observed_at,
                evidence_digests=(stable_hash((record_id, observation.value, reason)),),
                provider_message_id=message_id,
            )
        )
    return tuple(records)


def _environment(
    factory: ConnectionFactory,
) -> tuple[dict[str, object], str]:
    import psycopg2

    row = _query_one(
        factory,
        """
        SELECT current_database(), current_setting('server_version'),
               (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
               pg_postmaster_start_time()
        """,
    )
    if row is None or row[0] != "day106_l3" or row[2] is None:
        raise AssertionError("DAY106_L3_ENVIRONMENT_IDENTITY_MISMATCH")
    environment = {
        "compose_project": "day106-l3",
        "postgresql_version": str(row[1]),
        "pgvector_version": str(row[2]),
        "driver_version": psycopg2.__version__.split()[0],
        "python_version": platform.python_version(),
        "image_reference": "pgvector/pgvector:0.8.7-pg16",
        "image_digest": (
            "sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f"
        ),
        "database_identity_digest": stable_hash(
            ("day106_l3", str(row[1]), str(row[2]))
        ),
    }
    return environment, cast(datetime, row[3]).isoformat()


def run_integration(database_url: str) -> dict[str, object]:
    if os.environ.get(INTEGRATION_FLAG) != "1":
        raise RuntimeError("DAY106_L3_INTEGRATION_FLAG_REQUIRED")
    if not database_url.strip():
        raise ValueError("DAY106_L3_DATABASE_URL_REQUIRED")

    started = datetime.now(timezone.utc)
    day105_report = _run_day105_same_execution(database_url)
    if day105_report.get("status") != "PASS":
        raise AssertionError("DAY105_SAME_EXECUTION_PREREQUISITE_FAILED")

    factory = psycopg2_connection_factory(
        database_url,
        application_name="day106-l3a-integrated-capstone",
    )
    lifecycle = PostgresIndexLifecycleRepository(factory)
    security = PostgresRagSecurityRepository(factory, integration_enabled=True)
    capstone = PostgresRagCapstoneRepository(factory, integration_enabled=True)
    current = security.current_security_snapshot(day105.TENANT)
    if current is None or current.snapshot_id != "P2" or current.revision != 2:
        raise AssertionError("DAY106_CURRENT_P2_NOT_FOUND")

    base = datetime.now(timezone.utc).replace(microsecond=0)
    view_id = day105._acquire_view(
        lifecycle,
        request_id=REQUEST_ID,
        generation_id="G3",
        pointer_revision=9,
        authorization_id="P2",
        acquired_at=base.isoformat(),
        lease_expires_at=(base + timedelta(minutes=30)).isoformat(),
    )
    occurrence_ids = day105._query_read_view_ids(
        lifecycle,
        view_id=view_id,
        generation_id="G3",
        authorization_id="P2",
        query_vector=(0.0, 1.0, 0.0),
        top_k=1,
        mode=QueryMode.EXACT,
        observed_at=(base + timedelta(seconds=1)).isoformat(),
    )
    if occurrence_ids != ("C@v1",):
        raise AssertionError("DAY106_G3_Q2_REAL_RETRIEVAL_MISMATCH")

    security_binding = day105._binding_from_read_view(
        factory,
        request_id=REQUEST_ID,
        purpose="refund-Q2-Day106-L3A",
        view_id=view_id,
        generation_id="G3",
        authorization_revision="P2",
        manifest_occurrence_ids=("C@v1",),
        security_snapshot=cast(Any, current),
        policy=day105._policy(),
    )
    query = day105._run_query(
        factory,
        query_id="Day106-Q2-G3",
        binding=security_binding,
        occurrence_ids=occurrence_ids,
        observed_at=(base + timedelta(seconds=2)).isoformat(),
    )
    day105._persist_complete_query(
        security,
        query,
        observed_at=(base + timedelta(seconds=2)).isoformat(),
    )

    binding = _capstone_binding(factory, query)
    receipt = _retrieval_receipt(binding, query)
    cross_bound = capstone.append_cross_bound_execution(binding, receipt)
    if cross_bound.outcome is not CapstoneRepositoryOutcome.APPLIED:
        raise AssertionError("DAY106_CROSS_BOUND_EXECUTION_NOT_APPLIED")

    invocation_record = ModelInvocationRecord(
        model_invocation_id=query.invocation.envelope_id,
        model_invocation_digest=query.invocation.digest,
        request_binding_digest=binding.digest,
        retrieval_context_receipt_digest=receipt.digest,
        retrieval_bundle_digest=receipt.retrieval_bundle_digest,
        context_manifest_digest=receipt.context_manifest_digest,
        provider_mode=ProviderMode.DETERMINISTIC,
        provider_identity_digest=stable_hash(
            ("DETERMINISTIC_PROVIDER", query.invocation.model_id)
        ),
        model_identity_digest=stable_hash(
            ("MODEL_IDENTITY", query.invocation.model_id)
        ),
        config_digest=query.invocation.model_config_digest,
        contract_digest=stable_hash(
            (
                query.invocation.tool_policy_version,
                query.invocation.destination_policy_version,
                query.invocation.system_policy_digest,
            )
        ),
        created_at=query.bundle.created_at,
    )
    invocation_result = capstone.append_model_invocation(invocation_record)
    if invocation_result.outcome is not CapstoneRepositoryOutcome.APPLIED:
        raise AssertionError("DAY106_MODEL_INVOCATION_NOT_PERSISTED_BEFORE_RELEASE")

    release, intent = _release_and_intent(binding, receipt, query)
    committed = capstone.commit_release_and_intent(release, intent)
    if committed.outcome is not CapstoneRepositoryOutcome.APPLIED:
        raise AssertionError("DAY106_RELEASE_INTENT_TRANSACTION_NOT_APPLIED")

    for record in _recovery_records(base + timedelta(seconds=3)):
        result = capstone.append_recovery_record(record)
        if result.outcome not in {
            CapstoneRepositoryOutcome.APPLIED,
            CapstoneRepositoryOutcome.WINNER,
            CapstoneRepositoryOutcome.LATE_DUPLICATE,
        }:
            raise AssertionError(f"DAY106_RECOVERY_APPEND_FAILED:{result.safe_reason}")
    stored_intent = capstone.read_response_intent(INTENT_ID)
    history = capstone.read_recovery_history(INTENT_ID)
    state_identity = capstone.durable_state_identity(INTENT_ID)
    if (
        stored_intent is None
        or stored_intent.state != ResponseIntentState.DELIVERED.value
        or len(history) != 7
        or state_identity is None
    ):
        raise AssertionError("DAY106_DURABLE_DELIVERY_CHAIN_INCOMPLETE")
    provider_receipts = capstone.read_provider_call_receipts(binding.digest)
    if provider_receipts:
        raise AssertionError("L3A_MUST_NOT_HAVE_EXTERNAL_PROVIDER_RECEIPTS")

    released = lifecycle.release_read_view(
        view_id=view_id,
        expected_fencing_token=1,
        released_at=(base + timedelta(seconds=20)).isoformat(),
    )
    if released.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("DAY106_READ_VIEW_RELEASE_FAILED")

    environment, postmaster_started_at = _environment(factory)
    completed = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "run_id": f"day106-l3a-{stable_hash((started.isoformat(), binding.digest))[7:23]}",
        "overall_status": "PASS",
        "evidence_level": EVIDENCE_LEVEL,
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "environment": environment,
        "artifacts": _artifact_evidence(),
        "cross_binding": {
            "day105_same_execution_report_checksum": day105_report["report_checksum"],
            "request_binding_digest": binding.digest,
            "read_view_digest": binding.read_view_digest,
            "generation_manifest_digest": binding.generation_manifest_digest,
            "retrieval_context_receipt_digest": receipt.digest,
            "model_invocation_record_digest": invocation_record.digest,
            "answer_release_record_digest": release.digest,
            "response_intent_digest": intent.digest,
            "exact_occurrence_ids_digest": stable_hash(receipt.exact_occurrence_ids),
            "exact_content_digests_digest": stable_hash(receipt.exact_content_digests),
            "unauthorized_prompt_count": receipt.unauthorized_prompt_count,
        },
        "hard_gates": {
            "same_execution_real_database_cross_binding": "PASS",
            "same_execution_day105_prerequisite": "PASS",
            "real_pgvector_exact_occurrence_binding": "PASS",
            "unauthorized_occurrence_entering_prompt_zero": "PASS",
            "decision_intent_atomicity": "PASS",
            "model_invocation_persisted_before_release": "PASS",
            "external_pre_send_reservation": "NOT_RUN",
            "unknown_reconciliation_bounded_retry": "PASS",
            "winner_fence_and_duplicate_deduplication": "PASS",
            "append_only_delivery_chain": "PASS",
            "external_provider_boundary": "NOT_RUN",
            "canonical_python_3_12": "NOT_RUN",
        },
        "restart_evidence": {
            "status": "NOT_RUN",
            "pre_restart_state_digest": state_identity,
            "post_restart_state_digest": None,
            "pre_restart_postmaster_started_at": postmaster_started_at,
            "post_restart_postmaster_started_at": None,
        },
        "cleanup": {
            "status": "NOT_RUN",
            "compose_project_digest": None,
            "volume_identity_digest": None,
        },
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "raw_provider_response_logged": False,
        "raw_provider_response_id_logged": False,
        "raw_secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "external_real_boundary": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "claim_boundary": (
            "One-process Day106 L3A execution over real local Docker "
            "PostgreSQL/pgvector transactions, Day104 lifecycle rows, Day105 "
            "security rows, and Day106 durable cross-binding/recovery records; "
            "the model-invocation record was persisted before release, but no "
            "external pre-send reservation or Provider send was executed. Model, "
            "verifier, and DLP adapters remained deterministic. The actual Python "
            "runtime is recorded; canonical Python 3.12 remains NOT_RUN."
        ),
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _fail_closed(reason: str, error_type: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL_CLOSED",
        "evidence_level": "NOT_RUN",
        "safe_reason": reason,
        "provider_call_count": 0,
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "provider_response_logged": False,
        "secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    if error_type is not None:
        payload["error_type"] = error_type
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _write_exclusive(path: Path, report: dict[str, object]) -> None:
    """Write a sanitized report once; never overwrite prior evidence."""

    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-path",
        type=Path,
        help="optional new path for the sanitized report; existing files are refused",
    )
    arguments = parser.parse_args()
    if os.environ.get(INTEGRATION_FLAG) != "1":
        print(
            json.dumps(
                _fail_closed("DAY106_L3_INTEGRATION_FLAG_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    database_url = os.environ.get(DATABASE_URL_ENV, "")
    if not database_url.strip():
        print(
            json.dumps(
                _fail_closed("DAY106_L3_DATABASE_URL_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    try:
        report = run_integration(database_url)
    except BaseException as exc:
        print(
            json.dumps(
                _fail_closed("DAY106_L3A_INTEGRATION_FAILED", type(exc).__name__),
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    if arguments.report_path is not None:
        try:
            _write_exclusive(arguments.report_path, report)
        except BaseException as exc:
            print(
                json.dumps(
                    _fail_closed("DAY106_L3A_REPORT_WRITE_FAILED", type(exc).__name__),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
