"""Run the opt-in Day106 L3B database + external-provider scenario.

The runner extends one Day105 PostgreSQL/pgvector execution rather than
combining independent PASS reports.  Four G2/P1 provider calls execute from a
hook immediately after the real Day105 normal-query matrix and before P2.  The
same database then advances to P2/G3; the old pending candidate is blocked,
explicit G3 Q1/Q3 probes make zero provider calls, and G3/P2 Q2 makes the
fifth and final call.

Only identities, digests, counts, states, and safe reason codes are emitted.
Raw prompts, source text, answers, provider responses/IDs, vectors, secrets,
and database URLs are deliberately absent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

import run_day105_l3_integration as day105  # noqa: E402
import run_day106_l3a_integration as day106_l3a  # noqa: E402
from examples.day106_capstone_support import (  # noqa: E402
    CanonicalClaim,
    TENANT_ID,
    application_channel_claim,
    build_canonical_day101_fixture,
    execute_day101_query,
    refund_window_claim,
)
from examples.day106_production_rag_capstone import (  # noqa: E402
    BoundAttempt,
    DecidedQuery,
    ExternalGroundingRuntime,
    GroundingProviderBuildContext,
    PreparedQuery,
    ProviderInvocationReservation,
    _decide_query,
    _lineages,
    _load_prerequisite_evidence,
    _prepare_query,
)
from rag_capstone_contracts import (  # noqa: E402
    CapstoneRequestBinding,
    ReleaseCurrentnessSnapshot,
    ResponseIntent,
    ResponseIntentState,
)
from rag_capstone_orchestrator import (  # noqa: E402
    InMemoryReleaseCurrentnessAuthority,
)
from rag_authorized_retriever import (  # noqa: E402
    classroom_authorization_revisions,
)
from rag_capstone_postgres import (  # noqa: E402
    CapstoneRepositoryOutcome,
    ModelInvocationRecord,
    PostgresRagCapstoneRepository,
    ProviderCallAttempt,
    ProviderCallReceipt,
    ProviderCallStatus,
    ProviderMode,
)
from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_orchestrator import (  # noqa: E402
    IndexedOccurrence,
    manifest_facts,
)
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    PgVectorPoint,
    PostgresIndexLifecycleRepository,
    QueryMode,
    RepositoryOutcome,
    SourceOccurrenceRecord,
    psycopg2_connection_factory,
)
from rag_openai_responses_adapter import (  # noqa: E402
    MAX_OUTPUT_TOKENS,
    OPENAI_REASONING_EFFORT,
    OPENAI_RESPONSES_ENDPOINT,
    OPENAI_RESPONSES_MODEL,
    OpenAIInvocationBinding,
    OpenAIProviderObservation,
    OpenAIResponsesAnswerProvider,
    OpenAIResponsesRequest,
    OpenAIResponsesTransport,
    ProviderCallBudget,
    UrllibOpenAIResponsesTransport,
    day106_openai_grounding_contract,
    openai_model_config_digest,
    provider_request_idempotency_digest,
)
from rag_retrieval_contracts import (  # noqa: E402
    RETRIEVAL_ACTION,
    RETRIEVAL_PURPOSE,
)
from rag_security_contracts import (  # noqa: E402
    RequestSecurityBinding,
    SecurityPolicyIdentity,
    manifest_entry_digest,
)
from rag_security_postgres import (  # noqa: E402
    PostgresRagSecurityRepository,
    SecuritySnapshot,
)


SCHEMA_VERSION = "day106-l3b-external-evidence.v1"
SCENARIO_ID = "day106-production-rag-db-external-provider-l3b-v1"
EVIDENCE_LEVEL = (
    "EXECUTED_LOCAL_POSTGRESQL_PGVECTOR_AND_EXTERNAL_MODEL_BOUNDARY"
)
FAKE_SCHEMA_VERSION = "day106-l3b-deterministic-full-chain.v1"
FAKE_SCENARIO_ID = SCENARIO_ID + "-fake-transport"
FAKE_EVIDENCE_LEVEL = (
    "DETERMINISTIC_FAKE_TRANSPORT_WITH_LOCAL_POSTGRESQL_PGVECTOR"
)
REAL_TRANSPORT_BOUNDARY = "REAL_URLLIB_OPENAI_RESPONSES_HTTPS"
FAKE_TRANSPORT_BOUNDARY = "INJECTED_NON_ATTESTED_TRANSPORT"
REAL_TRANSPORT_BOUNDARY_DIGEST = stable_hash((
    "DAY106_L3B_TRANSPORT_BOUNDARY_V1",
    "UrllibOpenAIResponsesTransport",
    OPENAI_RESPONSES_ENDPOINT,
    "stdlib-urllib",
    "NO_RETRY",
))
FAKE_TRANSPORT_BOUNDARY_DIGEST = stable_hash((
    "DAY106_L3B_TRANSPORT_BOUNDARY_V1",
    FAKE_TRANSPORT_BOUNDARY,
    "NO_EXTERNAL_REAL_CLAIM",
))
_ATTESTED_REAL_TRANSPORT_CLASS = UrllibOpenAIResponsesTransport
_ATTESTED_REAL_TRANSPORT_SEND = UrllibOpenAIResponsesTransport.send
INTEGRATION_FLAG = "DAY106_L3B_INTEGRATION"
REAL_PROVIDER_FLAG = "DAY106_L3B_REAL_PROVIDER"
DATABASE_URL_ENV = "DAY106_L3_DATABASE_URL"
EXPECTED_EXTERNAL_CALLS = (
    "G2_P1_Q1",
    "G2_P1_Q2",
    "G2_P1_Q3",
    "G2_P1_Q3_PENDING",
    "G3_P2_Q2",
)
EXPECTED_ZERO_CALL_GATES = (
    "DAY105_SECURITY_NEGATIVE_CONTROLS",
    "G3_P2_Q1_REQUIRED_A_UNAVAILABLE",
    "G3_P2_Q3_REQUIRED_A_UNAVAILABLE",
)
EXPECTED_DURABLE_ARTIFACT_COUNTS = {
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
ARTIFACT_PATHS = {
    "integration_runner": Path(__file__),
    "evidence_schema": ROOT / "evidence" / "day106-l3b-evidence-schema.json",
    "database_schema": ROOT / "integration" / "day106" / "schema.sql",
    "capstone_repository": ROOT / "src" / "rag_capstone_postgres.py",
    "compose": ROOT / "integration" / "day106" / "compose.yaml",
    "openai_adapter": ROOT / "src" / "rag_openai_responses_adapter.py",
    "production_capstone": ROOT / "examples" / "day106_production_rag_capstone.py",
    "capstone_support": ROOT / "examples" / "day106_capstone_support.py",
    "grounding_adapters": ROOT / "src" / "rag_grounding_adapters.py",
    "grounding_orchestrator": ROOT / "src" / "rag_grounding_orchestrator.py",
    "day105_integration_runner": ROOT / "evals" / "run_day105_l3_integration.py",
    "day106_l3a_integration_runner": (
        ROOT / "evals" / "run_day106_l3a_integration.py"
    ),
    "restart_runner": ROOT / "evals" / "run_day106_l3b_restart_replay.py",
    "evidence_replay_runner": ROOT / "evals" / "run_day106_l3b_evidence_replay.py",
}


@dataclass(frozen=True)
class ExternalQuerySpec:
    label: str
    query_id: str
    query_text: str
    claims: tuple[CanonicalClaim, ...]
    generation_id: str
    pointer_revision: int
    authorization_snapshot_id: str
    authorization_revision: int
    manifest_occurrence_ids: tuple[str, ...]
    query_vector: tuple[float, ...]
    top_k: int
    expected_occurrence_ids: tuple[str, ...]
    release_immediately: bool


@dataclass
class ExternalCallAccounting:
    """Shared call/zero-call ledger used by real and fake orchestration."""

    call_labels: list[str]
    zero_call_gates: list[str]

    @classmethod
    def empty(cls) -> ExternalCallAccounting:
        return cls([], [])

    def record_call(self, label: str, before: int, after: int) -> None:
        if label not in EXPECTED_EXTERNAL_CALLS:
            raise AssertionError(f"UNEXPECTED_EXTERNAL_CALL_LABEL:{label}")
        if after != before + 1:
            raise AssertionError(f"EXTERNAL_CALL_DELTA_INVALID:{label}")
        if label in self.call_labels:
            raise AssertionError(f"EXTERNAL_CALL_LABEL_REUSED:{label}")
        self.call_labels.append(label)

    def record_zero_call_gate(self, label: str, before: int, after: int) -> None:
        if label not in EXPECTED_ZERO_CALL_GATES:
            raise AssertionError(f"UNEXPECTED_ZERO_CALL_GATE:{label}")
        if after != before:
            raise AssertionError(f"ZERO_CALL_GATE_CALLED_PROVIDER:{label}")
        if label in self.zero_call_gates:
            raise AssertionError(f"ZERO_CALL_GATE_REUSED:{label}")
        self.zero_call_gates.append(label)

    def validate(self, observed_calls: int) -> None:
        if tuple(self.call_labels) != EXPECTED_EXTERNAL_CALLS:
            raise AssertionError("EXTERNAL_CALL_MATRIX_INCOMPLETE")
        if set(self.zero_call_gates) != set(EXPECTED_ZERO_CALL_GATES):
            raise AssertionError("ZERO_CALL_GATE_MATRIX_INCOMPLETE")
        if observed_calls != len(EXPECTED_EXTERNAL_CALLS):
            raise AssertionError("EXTERNAL_PROVIDER_CALL_BUDGET_MISMATCH")


@dataclass
class ExternalQueryExecution:
    spec: ExternalQuerySpec
    prepared: PreparedQuery
    decided: DecidedQuery | None
    provider_observation: OpenAIProviderObservation
    model_invocation_record: ModelInvocationRecord
    provider_attempt: ProviderCallAttempt
    provider_receipt: ProviderCallReceipt
    release_currentness: InMemoryReleaseCurrentnessAuthority
    serving_fixture: Any


@dataclass(frozen=True)
class TransportEvidenceScope:
    schema_version: str
    scenario_id: str
    evidence_level: str
    run_id_prefix: str
    transport_boundary: str
    transport_boundary_digest: str
    external_model_boundary: str
    claim_boundary: str
    real_external_transport_attested: bool


def _injected_transport_evidence_scope() -> TransportEvidenceScope:
    """Every caller-supplied transport is deterministic/non-external evidence."""

    return TransportEvidenceScope(
        schema_version=FAKE_SCHEMA_VERSION,
        scenario_id=FAKE_SCENARIO_ID,
        evidence_level=FAKE_EVIDENCE_LEVEL,
        run_id_prefix="day106-l3b-fake-",
        transport_boundary=FAKE_TRANSPORT_BOUNDARY,
        transport_boundary_digest=FAKE_TRANSPORT_BOUNDARY_DIGEST,
        external_model_boundary="NOT_RUN",
        claim_boundary=(
            "One Day106 execution over a real local PostgreSQL/pgvector "
            "lifecycle and security state with five injected deterministic "
            "transport calls. The external model boundary was NOT_RUN; DLP, "
            "production IAM/RLS/TLS/egress, HA/restore, load/soak, and "
            "production readiness remain NOT_RUN/MORE_EVIDENCE_NEEDED."
        ),
        real_external_transport_attested=False,
    )


def _attested_real_transport_evidence_scope(
    transport: OpenAIResponsesTransport,
) -> TransportEvidenceScope:
    """Attest only a fresh internal urllib transport with its original send."""

    if type(transport) is not _ATTESTED_REAL_TRANSPORT_CLASS:
        raise RuntimeError("DAY106_L3B_REAL_TRANSPORT_TYPE_MISMATCH")
    if "send" in getattr(transport, "__dict__", {}):
        raise RuntimeError("DAY106_L3B_REAL_TRANSPORT_INSTANCE_OVERRIDE")
    class_send = getattr(type(transport), "send", None)
    bound_send = getattr(transport, "send", None)
    if (
        class_send is not _ATTESTED_REAL_TRANSPORT_SEND
        or getattr(bound_send, "__self__", None) is not transport
        or getattr(bound_send, "__func__", None)
        is not _ATTESTED_REAL_TRANSPORT_SEND
    ):
        raise RuntimeError("DAY106_L3B_REAL_TRANSPORT_METHOD_MISMATCH")
    return TransportEvidenceScope(
        schema_version=SCHEMA_VERSION,
        scenario_id=SCENARIO_ID,
        evidence_level=EVIDENCE_LEVEL,
        run_id_prefix="day106-l3b-",
        transport_boundary=REAL_TRANSPORT_BOUNDARY,
        transport_boundary_digest=REAL_TRANSPORT_BOUNDARY_DIGEST,
        external_model_boundary="PASS",
        claim_boundary=(
            "One Day106 execution over the same real local "
            "PostgreSQL/pgvector lifecycle and security state plus five "
            "bounded calls through the exact attested urllib OpenAI "
            "Responses HTTPS transport. DLP, production IAM/RLS/TLS/"
            "egress, HA/restore, load/soak, and production readiness "
            "remain NOT_RUN/MORE_EVIDENCE_NEEDED."
        ),
        real_external_transport_attested=True,
    )


def _g2_specs() -> tuple[ExternalQuerySpec, ...]:
    root_half = 1.0 / math.sqrt(2.0)
    q1 = refund_window_claim()
    q2 = application_channel_claim()
    return (
        ExternalQuerySpec(
            "G2_P1_Q1",
            "day106-l3b-G2-Q1",
            q1.question,
            (q1,),
            "G2",
            8,
            "P1",
            1,
            ("A@v1", "C@v1"),
            (1.0, 0.0, 0.0),
            1,
            ("A@v1",),
            True,
        ),
        ExternalQuerySpec(
            "G2_P1_Q2",
            "day106-l3b-G2-Q2",
            q2.question,
            (q2,),
            "G2",
            8,
            "P1",
            1,
            ("A@v1", "C@v1"),
            (0.0, 1.0, 0.0),
            1,
            ("C@v1",),
            True,
        ),
        ExternalQuerySpec(
            "G2_P1_Q3",
            "day106-l3b-G2-Q3",
            "What is the refund window and application channel?",
            (q1, q2),
            "G2",
            8,
            "P1",
            1,
            ("A@v1", "C@v1"),
            (root_half, root_half, 0.0),
            2,
            ("A@v1", "C@v1"),
            True,
        ),
        ExternalQuerySpec(
            "G2_P1_Q3_PENDING",
            "day106-l3b-G2-Q3-pending",
            "What is the refund window and application channel?",
            (q1, q2),
            "G2",
            8,
            "P1",
            1,
            ("A@v1", "C@v1"),
            (root_half, root_half, 0.0),
            2,
            ("A@v1", "C@v1"),
            False,
        ),
    )


def _g3_q2_spec() -> ExternalQuerySpec:
    q2 = application_channel_claim()
    return ExternalQuerySpec(
        "G3_P2_Q2",
        "day106-l3b-G3-Q2",
        q2.question,
        (q2,),
        "G3",
        9,
        "P2",
        2,
        ("C@v1",),
        (0.0, 1.0, 0.0),
        1,
        ("C@v1",),
        True,
    )


def _g3_zero_call_specs() -> tuple[ExternalQuerySpec, ...]:
    q1 = refund_window_claim()
    q2 = application_channel_claim()
    return (
        ExternalQuerySpec(
            "G3_P2_Q1_REQUIRED_A_UNAVAILABLE",
            "day106-l3b-G3-Q1-zero-call",
            q1.question,
            (q1,),
            "G3",
            9,
            "P2",
            2,
            ("C@v1",),
            (1.0, 0.0, 0.0),
            1,
            ("C@v1",),
            False,
        ),
        ExternalQuerySpec(
            "G3_P2_Q3_REQUIRED_A_UNAVAILABLE",
            "day106-l3b-G3-Q3-zero-call",
            "What is the refund window and application channel?",
            (q1, q2),
            "G3",
            9,
            "P2",
            2,
            ("C@v1",),
            (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0),
            1,
            ("C@v1",),
            False,
        ),
    )


def _require_applied(result: Any, label: str) -> None:
    if result.outcome is not CapstoneRepositoryOutcome.APPLIED:
        raise AssertionError(
            f"{label}:{result.outcome.value}:{result.safe_reason}"
        )


def _query_one(
    factory: ConnectionFactory,
    query: str,
    params: tuple[object, ...] = (),
) -> Any:
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
) -> list[Any]:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        return list(cursor.fetchall())
    finally:
        cursor.close()
        connection.close()


def _durable_pre_restart_state(
    factory: ConnectionFactory,
) -> dict[str, object]:
    postmaster = _query_one(
        factory,
        "SELECT pg_postmaster_start_time()",
    )
    if postmaster is None:
        raise AssertionError("POSTMASTER_START_TIME_UNAVAILABLE")
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
        (TENANT_ID,),
    )
    identity_rows = _query_rows(
        factory,
        """
        WITH tenant_requests AS (
          SELECT identity_digest
          FROM day106_l3.request_bindings
          WHERE tenant_id = %s AND pointer_name = %s
        ), tenant_intents AS (
          SELECT intent.intent_id
          FROM day106_l3.response_intents AS intent
          JOIN tenant_requests AS request
            ON request.identity_digest = intent.request_binding_digest
        )
        SELECT artifact_type, identity_digest
        FROM (
          SELECT 'REQUEST_BINDING' AS artifact_type,
                 request.identity_digest
            FROM tenant_requests AS request
          UNION ALL
          SELECT 'RETRIEVAL_CONTEXT_RECEIPT', receipt.identity_digest
            FROM day106_l3.retrieval_context_receipts AS receipt
            JOIN tenant_requests AS request
              ON request.identity_digest = receipt.request_binding_digest
          UNION ALL
          SELECT 'MODEL_INVOCATION', invocation.identity_digest
            FROM day106_l3.model_invocations AS invocation
            JOIN tenant_requests AS request
              ON request.identity_digest = invocation.request_binding_digest
          UNION ALL
          SELECT 'PROVIDER_ATTEMPT', attempt.identity_digest
            FROM day106_l3.provider_call_attempts AS attempt
            JOIN tenant_requests AS request
              ON request.identity_digest = attempt.request_binding_digest
          UNION ALL
          SELECT 'PROVIDER_RECEIPT', receipt.identity_digest
            FROM day106_l3.provider_call_receipts AS receipt
            JOIN tenant_requests AS request
              ON request.identity_digest = receipt.request_binding_digest
          UNION ALL
          SELECT 'ANSWER_RELEASE', release_record.identity_digest
            FROM day106_l3.answer_release_records AS release_record
            JOIN tenant_requests AS request
              ON request.identity_digest = release_record.request_binding_digest
          UNION ALL
          SELECT 'RESPONSE_INTENT', intent.identity_digest
            FROM day106_l3.response_intents AS intent
            JOIN tenant_requests AS request
              ON request.identity_digest = intent.request_binding_digest
          UNION ALL
          SELECT 'DISPATCH_WINNER', winner.identity_digest
            FROM day106_l3.dispatch_winners AS winner
            JOIN tenant_intents AS intent
              ON intent.intent_id = winner.response_intent_id
          UNION ALL
          SELECT 'DISPATCH_RECORD', dispatch.identity_digest
            FROM day106_l3.dispatch_recovery_delivery_records AS dispatch
            JOIN tenant_intents AS intent
              ON intent.intent_id = dispatch.response_intent_id
        ) AS durable
        ORDER BY artifact_type, identity_digest
        """,
        (TENANT_ID, "refund-serving"),
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
    counts = dict(EXPECTED_DURABLE_ARTIFACT_COUNTS)
    for key in counts:
        counts[key] = sum(1 for name, _ in identities if name == key)
    if counts != EXPECTED_DURABLE_ARTIFACT_COUNTS:
        raise AssertionError("PRE_RESTART_DURABLE_STATE_COUNT_MISMATCH")
    if pointer != (("refund-serving", "G3", 9),):
        raise AssertionError("PRE_RESTART_POINTER_MISMATCH")
    if security != (("tenant-refund", "P2", 2),):
        raise AssertionError("PRE_RESTART_SECURITY_SNAPSHOT_MISMATCH")
    started_at = postmaster[0]
    if not isinstance(started_at, datetime) or started_at.tzinfo is None:
        raise AssertionError("PRE_RESTART_POSTMASTER_TIMESTAMP_INVALID")
    postmaster_started_at = started_at.isoformat()
    return {
        "pre_restart_postmaster_started_at": postmaster_started_at,
        "pre_restart_state_digest": stable_hash((
            "DAY106_L3B_DURABLE_STATE_V1",
            pointer,
            security,
            identities,
        )),
        "artifact_counts": counts,
        "artifact_identity_count": len(identities),
    }


def _lineage_content_digest(lineages: dict[str, Any], occurrence_id: str) -> str:
    lineage = lineages.get(occurrence_id)
    return (
        stable_hash(("CONTENT", occurrence_id))
        if lineage is None
        else cast(str, lineage.content_digest)
    )


def _lineage_metadata_digest(lineages: dict[str, Any], occurrence_id: str) -> str:
    lineage = lineages.get(occurrence_id)
    return (
        stable_hash(("METADATA", occurrence_id))
        if lineage is None
        else cast(str, lineage.metadata_digest)
    )


def _patched_occurrence_record(
    original: Any,
    lineages: dict[str, Any],
    occurrence_id: str,
) -> SourceOccurrenceRecord:
    return replace(
        original(occurrence_id),
        content_digest=_lineage_content_digest(lineages, occurrence_id),
        metadata_digest=_lineage_metadata_digest(lineages, occurrence_id),
    )


def _patched_manifest(
    lineages: dict[str, Any],
    occurrence_ids: tuple[str, ...],
) -> Any:
    return manifest_facts(tuple(
        IndexedOccurrence(
            occurrence_id,
            _lineage_content_digest(lineages, occurrence_id),
            _lineage_metadata_digest(lineages, occurrence_id),
            stable_hash((
                "PROVENANCE",
                occurrence_id,
                day105.PROVENANCE_REVISION,
            )),
        )
        for occurrence_id in occurrence_ids
    ))


def _patched_points(
    original: Any,
    lineages: dict[str, Any],
    generation_id: str,
    occurrence_ids: tuple[str, ...],
    authorization_id: str,
) -> tuple[PgVectorPoint, ...]:
    return tuple(
        replace(
            point,
            content_digest=_lineage_content_digest(
                lineages,
                point.occurrence_id,
            ),
            metadata_digest=_lineage_metadata_digest(
                lineages,
                point.occurrence_id,
            ),
        )
        for point in original(
            generation_id,
            occurrence_ids,
            authorization_id,
        )
    )


def _release_snapshot(
    *,
    snapshot_id: str,
    revision: int,
    security_binding: Any,
    eligible_occurrence_ids: tuple[str, ...],
    policy: SecurityPolicyIdentity,
) -> ReleaseCurrentnessSnapshot:
    return ReleaseCurrentnessSnapshot(
        snapshot_id=snapshot_id,
        revision=revision,
        tenant_id=TENANT_ID,
        destination="current-chat",
        source_eligible_occurrence_ids=tuple(sorted(eligible_occurrence_ids)),
        quarantined_occurrence_ids=(),
        provenance_revision=day105.PROVENANCE_REVISION,
        tombstone_revision=day105.TOMBSTONE_REVISION,
        content_security_snapshot_digest=(
            security_binding.content_security_snapshot_digest
        ),
        security_policy_fingerprint=policy.fingerprint,
        dlp_result="PASS",
        metadata_stripping_result="PASS",
        destination_result="PASS",
        evidence_digests=(stable_hash((
            snapshot_id,
            security_binding.content_security_snapshot_digest,
            eligible_occurrence_ids,
        )),),
    )


def _authorization_revision_digest(revision: int) -> str:
    return stable_hash(asdict(classroom_authorization_revisions(
        policy_revision=revision,
        acl_revision=revision,
        authorization_epoch=revision,
    )))


def _seed_release_currentness(
    *,
    factory: ConnectionFactory,
    authority: InMemoryReleaseCurrentnessAuthority,
    spec: ExternalQuerySpec,
    security_binding: RequestSecurityBinding,
    current_security_snapshot: SecuritySnapshot,
    eligible_occurrence_ids: tuple[str, ...],
    policy: SecurityPolicyIdentity,
) -> None:
    """Append P1 before P2 so currentness history cannot start at revision 2."""

    if spec.authorization_revision not in (1, 2):
        raise AssertionError("UNSUPPORTED_RELEASE_CURRENTNESS_REVISION")
    if (
        current_security_snapshot.snapshot_id
        != spec.authorization_snapshot_id
        or current_security_snapshot.revision != spec.authorization_revision
        or security_binding.content_security_snapshot_digest
        != current_security_snapshot.identity_digest
    ):
        raise AssertionError("CURRENT_SECURITY_SNAPSHOT_BINDING_MISMATCH")
    if spec.authorization_revision == 2:
        p1_row = _query_one(
            factory,
            """
            SELECT identity_digest
            FROM day105_l3.security_snapshots
            WHERE tenant_id = %s AND snapshot_id = 'P1' AND revision = 1
            """,
            (TENANT_ID,),
        )
        if p1_row is None:
            raise AssertionError("P1_SECURITY_SNAPSHOT_HISTORY_MISSING")
        p1_binding = replace(
            security_binding,
            authorization_revision=_authorization_revision_digest(1),
            content_security_snapshot_digest=str(p1_row[0]),
        )
        authority.put(_release_snapshot(
            snapshot_id=f"release-currentness:{spec.query_id}:P1",
            revision=1,
            security_binding=p1_binding,
            eligible_occurrence_ids=("A@v1", "C@v1"),
            policy=policy,
        ))
    authority.put(_release_snapshot(
        snapshot_id=f"release-currentness:{spec.query_id}",
        revision=spec.authorization_revision,
        security_binding=security_binding,
        eligible_occurrence_ids=eligible_occurrence_ids,
        policy=policy,
    ))


def _security_binding_from_read_view(
    *,
    factory: ConnectionFactory,
    request_id: str,
    view_id: str,
    generation_id: str,
    authorization_snapshot_id: str,
    pointer_revision: int,
    authorization_revision: int,
    manifest_occurrence_ids: tuple[str, ...],
    security_snapshot: SecuritySnapshot,
    policy: SecurityPolicyIdentity,
    lineages: dict[str, Any],
) -> tuple[RequestSecurityBinding, Any]:
    """Bind DB snapshot identity and serving revision identity separately."""

    base = day105._binding_from_read_view(
        factory,
        request_id=request_id,
        purpose=RETRIEVAL_PURPOSE,
        view_id=view_id,
        generation_id=generation_id,
        # The Day104 ReadView durably pins the application snapshot ID (P1/P2),
        # not the Day100 authorization revision-vector digest.
        authorization_revision=authorization_snapshot_id,
        manifest_occurrence_ids=manifest_occurrence_ids,
        security_snapshot=security_snapshot,
        policy=policy,
    )
    entries = tuple(
        (
            occurrence_id,
            manifest_entry_digest(
                occurrence_id,
                lineages[occurrence_id].source_artifact_id,
                lineages[occurrence_id].source_version,
                lineages[occurrence_id].tenant_id,
                lineages[occurrence_id].resource_id,
                lineages[occurrence_id].content_digest,
                lineages[occurrence_id].metadata_digest,
                lineages[occurrence_id].metadata_version,
                lineages[occurrence_id].provenance_revision,
            ),
        )
        for occurrence_id in sorted(manifest_occurrence_ids)
    )
    lineage_binding = replace(
        base,
        manifest_entries=entries,
        generation_manifest_digest=stable_hash(entries),
    )
    serving = build_canonical_day101_fixture(
        generation_id=generation_id,
        pointer_revision=pointer_revision,
        generation_artifact_fingerprint=(
            lineage_binding.generation_artifact_digest
        ),
        manifest_occurrence_ids=manifest_occurrence_ids,
        authorization_revision=authorization_revision,
    )
    actual_revision_digest = stable_hash(
        asdict(serving.day100.scope.revisions)
    )
    expected_revision_digest = _authorization_revision_digest(
        authorization_revision
    )
    if actual_revision_digest != expected_revision_digest:
        raise AssertionError("SERVING_AUTHORIZATION_REVISION_DIGEST_DRIFT")
    bound = replace(
        lineage_binding,
        authorization_revision=actual_revision_digest,
    )
    if bound.authorization_revision != stable_hash(
        asdict(serving.day100.scope.revisions)
    ):
        raise AssertionError("SECURITY_BINDING_SERVING_REVISION_MISMATCH")
    return bound, serving


def _response_intent(decided: DecidedQuery) -> ResponseIntent | None:
    record = decided.record
    if record.disposition != "RELEASE":
        return None
    if (
        record.response_intent_id is None
        or record.dispatch_idempotency_key is None
        or record.authorized_destination is None
    ):
        raise AssertionError("RELEASED_RECORD_MISSING_RESPONSE_INTENT_BINDINGS")
    return ResponseIntent(
        intent_id=record.response_intent_id,
        request_binding_digest=record.request_binding_digest,
        output_release_decision_digest=(
            record.output_release_decision_digest
        ),
        candidate_digest=record.answer_candidate_digest,
        destination=record.authorized_destination,
        dispatch_idempotency_key=record.dispatch_idempotency_key,
        state=ResponseIntentState.PENDING,
        revision=1,
        created_at=record.created_at,
    )


def _bound_candidate_digest(
    observation: OpenAIProviderObservation,
    prepared: PreparedQuery | None,
) -> str | None:
    """Prove the stored candidate came from this exact provider answer."""

    if observation.outcome != "SUCCEEDED":
        return None
    if prepared is None:
        raise AssertionError("SUCCEEDED_PROVIDER_OUTCOME_WITHOUT_CANDIDATE")
    if observation.answer_digest != prepared.candidate.answer_digest:
        raise AssertionError("PROVIDER_ANSWER_CANDIDATE_DIGEST_DRIFT")
    return prepared.candidate.digest


class ExternalScenario:
    """Orchestrate one shared database execution and one call budget."""

    def __init__(self, transport: OpenAIResponsesTransport) -> None:
        self.transport = transport
        self.budget = ProviderCallBudget(len(EXPECTED_EXTERNAL_CALLS))
        self.accounting = ExternalCallAccounting.empty()
        self.lineages = _lineages(_load_prerequisite_evidence())
        self.executions: dict[str, ExternalQueryExecution] = {}
        self.factory: ConnectionFactory | None = None
        self.lifecycle: PostgresIndexLifecycleRepository | None = None
        self.security: PostgresRagSecurityRepository | None = None
        self.capstone: PostgresRagCapstoneRepository | None = None
        self.base: datetime | None = None

    def attach_database(
        self,
        *,
        factory: ConnectionFactory,
        lifecycle: PostgresIndexLifecycleRepository,
        security: PostgresRagSecurityRepository,
        base: datetime,
    ) -> None:
        self.factory = factory
        self.lifecycle = lifecycle
        self.security = security
        self.capstone = PostgresRagCapstoneRepository(
            factory,
            integration_enabled=True,
        )
        self.base = base

    def _repositories(self) -> tuple[
        ConnectionFactory,
        PostgresIndexLifecycleRepository,
        PostgresRagCapstoneRepository,
        datetime,
    ]:
        if any(item is None for item in (
            self.factory,
            self.lifecycle,
            self.capstone,
            self.base,
        )):
            raise RuntimeError("EXTERNAL_SCENARIO_DATABASE_NOT_ATTACHED")
        return (
            cast(ConnectionFactory, self.factory),
            cast(PostgresIndexLifecycleRepository, self.lifecycle),
            cast(PostgresRagCapstoneRepository, self.capstone),
            cast(datetime, self.base),
        )

    def _capstone_binding(
        self,
        *,
        spec: ExternalQuerySpec,
        security_binding: Any,
        serving_fixture: Any,
        created_at: str,
    ) -> CapstoneRequestBinding:
        factory, _, _, _ = self._repositories()
        row = _query_one(
            factory,
            """
            SELECT view.pointer_name, view.pointer_revision,
                   view.fencing_token, snapshot.source_snapshot_id,
                   snapshot.deletion_snapshot_id, generation.manifest_digest
            FROM day104_l3.read_views AS view
            JOIN day104_l3.generations AS generation
              ON generation.generation_id = view.generation_id
            JOIN day104_l3.build_snapshots AS snapshot
              ON snapshot.build_snapshot_id = generation.build_snapshot_id
            WHERE view.view_id = %s
            """,
            (security_binding.read_view_id,),
        )
        if row is None:
            raise AssertionError("DAY106_L3B_READ_VIEW_BINDING_NOT_FOUND")
        scope = serving_fixture.day100.scope
        selected = serving_fixture.day100.bundle
        return CapstoneRequestBinding(
            request_attempt_id=security_binding.request_id,
            request_id=security_binding.request_id,
            principal_id=security_binding.principal_id,
            tenant_id=security_binding.tenant_id,
            action=scope.action,
            purpose=scope.purpose,
            audience=security_binding.audience,
            pointer_name=str(row[0]),
            generation_id=security_binding.generation_id,
            generation_artifact_digest=(
                security_binding.generation_artifact_digest
            ),
            generation_manifest_digest=str(row[5]),
            build_snapshot_fingerprint=(
                security_binding.build_snapshot_fingerprint
            ),
            pointer_revision=int(row[1]),
            read_view_id=security_binding.read_view_id,
            read_view_fence=int(row[2]),
            read_view_digest=security_binding.read_view_validation_digest,
            source_snapshot_id=str(row[3]),
            authorization_snapshot_id=spec.authorization_snapshot_id,
            deletion_snapshot_id=str(row[4]),
            policy_fingerprint=security_binding.policy.fingerprint,
            security_binding_fingerprint=security_binding.fingerprint,
            retrieval_authorization_revision_digest=stable_hash(
                asdict(scope.revisions)
            ),
            retrieval_authorization_scope_fingerprint=scope.fingerprint,
            selected_retrieval_bundle_id=selected.bundle_id,
            selected_retrieval_bundle_revision=selected.revision,
            selected_retrieval_bundle_fingerprint=selected.fingerprint,
            created_at=created_at,
        )

    def _runtime(
        self,
        *,
        spec: ExternalQuerySpec,
        locals_: dict[str, Any],
    ) -> ExternalGroundingRuntime:
        _, _, capstone, _ = self._repositories()
        contract = day106_openai_grounding_contract()

        def reserve(
            context: GroundingProviderBuildContext,
        ) -> ProviderInvocationReservation:
            if self.budget.used >= self.budget.limit:
                raise RuntimeError("PROVIDER_BUDGET_EXHAUSTED_BEFORE_RESERVATION")
            cross_bound = capstone.append_cross_bound_execution(
                context.request_binding,
                context.retrieval_and_context_receipt,
            )
            _require_applied(cross_bound, "APPEND_CROSS_BOUND_EXECUTION")
            invocation = ModelInvocationRecord(
                model_invocation_id=context.invocation_envelope.envelope_id,
                model_invocation_digest=context.invocation_envelope.digest,
                request_binding_digest=context.request_binding.digest,
                retrieval_context_receipt_digest=(
                    context.retrieval_and_context_receipt.digest
                ),
                retrieval_bundle_digest=context.retrieval_bundle.digest,
                context_manifest_digest=context.context_manifest.digest,
                provider_mode=ProviderMode.EXTERNAL,
                provider_identity_digest=stable_hash((
                    "OPENAI_RESPONSES_PROVIDER",
                    OPENAI_RESPONSES_ENDPOINT,
                )),
                model_identity_digest=stable_hash((
                    "OPENAI_RESPONSES_MODEL",
                    OPENAI_RESPONSES_MODEL,
                )),
                config_digest=context.invocation_envelope.model_config_digest,
                contract_digest=context.grounding_contract.fingerprint,
                created_at=context.retrieval_and_context_receipt.created_at,
            )
            _require_applied(
                capstone.append_model_invocation(invocation),
                "APPEND_EXTERNAL_MODEL_INVOCATION",
            )
            ordinal = self.budget.used + 1
            attempt = ProviderCallAttempt(
                attempt_id=context.provider_invocation_attempt_id,
                request_binding_digest=context.request_binding.digest,
                retrieval_context_receipt_digest=(
                    context.retrieval_and_context_receipt.digest
                ),
                model_invocation_id=context.invocation_envelope.envelope_id,
                model_invocation_digest=context.invocation_envelope.digest,
                call_ordinal=ordinal,
                provider_request_idempotency_digest=(
                    provider_request_idempotency_digest(
                        context.provider_invocation_attempt_id
                    )
                ),
                created_at=context.retrieval_and_context_receipt.created_at,
            )
            _require_applied(
                capstone.reserve_provider_call_attempt(attempt),
                "RESERVE_PROVIDER_CALL_ATTEMPT",
            )
            locals_["invocation"] = invocation
            locals_["attempt"] = attempt
            return ProviderInvocationReservation(
                reservation_id=attempt.attempt_id,
                provider_invocation_attempt_id=attempt.attempt_id,
                request_binding_digest=attempt.request_binding_digest,
                retrieval_and_context_receipt_digest=(
                    attempt.retrieval_context_receipt_digest
                ),
                invocation_envelope_digest=attempt.model_invocation_digest,
            )

        def provider_factory(
            context: GroundingProviderBuildContext,
            reservation: ProviderInvocationReservation,
        ) -> OpenAIResponsesAnswerProvider:
            attempt = cast(ProviderCallAttempt, locals_.get("attempt"))
            if (
                attempt is None
                or reservation.provider_invocation_attempt_id
                != attempt.attempt_id
            ):
                raise RuntimeError("PROVIDER_FACTORY_WITHOUT_DURABLE_RESERVATION")
            provider = OpenAIResponsesAnswerProvider(
                transport=self.transport,
                budget=self.budget,
                binding=OpenAIInvocationBinding(
                    invocation_envelope_digest=(
                        context.invocation_envelope.digest
                    ),
                    provider_invocation_attempt_id=attempt.attempt_id,
                    provider_invocation_reservation_digest=(
                        reservation.digest
                    ),
                    provider_request_idempotency_digest=(
                        attempt.provider_request_idempotency_digest
                    ),
                    context_manifest_digest=context.context_manifest.digest,
                    retrieval_bundle_digest=context.retrieval_bundle.digest,
                    model_config_digest=(
                        context.invocation_envelope.model_config_digest
                    ),
                    expected_operation_id=(
                        "grounding-"
                        + context.retrieval_run.retrieval_request.operation_id
                    ),
                    expected_day101_handoff_digest=(
                        context.retrieval_run.day101_response.handoff_digest
                        or "MISSING"
                    ),
                    expected_contract_fingerprint=(
                        context.grounding_contract.fingerprint
                    ),
                ),
            )
            locals_["provider"] = provider
            return provider

        return ExternalGroundingRuntime(
            grounding_contract=contract,
            model_id=OPENAI_RESPONSES_MODEL,
            model_config_digest=openai_model_config_digest(MAX_OUTPUT_TOKENS),
            reserve_provider_invocation=reserve,
            answer_provider_factory=provider_factory,
        )

    def _append_provider_outcome(
        self,
        *,
        spec: ExternalQuerySpec,
        locals_: dict[str, Any],
        prepared: PreparedQuery | None,
        observed_at: str,
    ) -> ProviderCallReceipt:
        _, _, capstone, _ = self._repositories()
        provider = cast(OpenAIResponsesAnswerProvider, locals_.get("provider"))
        invocation = cast(ModelInvocationRecord, locals_.get("invocation"))
        attempt = cast(ProviderCallAttempt, locals_.get("attempt"))
        if provider is None or invocation is None or attempt is None:
            raise RuntimeError("PROVIDER_OUTCOME_WITHOUT_PRE_SEND_RECORDS")
        observations = provider.observations()
        if len(observations) != 1:
            raise RuntimeError("PROVIDER_OUTCOME_CARDINALITY_CONFLICT")
        observation = observations[0]
        if observation.outcome == "SUCCEEDED":
            status = ProviderCallStatus.SUCCEEDED
        elif observation.reconciliation_required:
            status = ProviderCallStatus.UNKNOWN
        else:
            status = ProviderCallStatus.FAILED
        receipt = ProviderCallReceipt(
            receipt_id=f"provider-receipt:{spec.query_id}",
            provider_attempt_id=attempt.attempt_id,
            request_binding_digest=attempt.request_binding_digest,
            retrieval_context_receipt_digest=(
                attempt.retrieval_context_receipt_digest
            ),
            model_invocation_id=attempt.model_invocation_id,
            model_invocation_digest=attempt.model_invocation_digest,
            call_ordinal=attempt.call_ordinal,
            requested_model_id=observation.requested_model,
            observed_model_id=observation.observed_model,
            provider_response_id_digest=(
                observation.provider_response_id_digest
            ),
            answer_candidate_digest=_bound_candidate_digest(
                observation,
                prepared,
            ),
            input_token_count=observation.input_tokens,
            output_token_count=observation.output_tokens,
            total_token_count=observation.total_tokens,
            status=status,
            safe_reason_code=observation.safe_reason_code,
            observed_at=observed_at,
        )
        _require_applied(
            capstone.append_provider_call_receipt(receipt),
            "APPEND_PROVIDER_CALL_RECEIPT",
        )
        locals_["observation"] = observation
        return receipt

    def _commit_decision(self, decided: DecidedQuery) -> None:
        _, _, capstone, _ = self._repositories()
        result = capstone.commit_release_and_intent(
            decided.record,
            _response_intent(decided),
        )
        _require_applied(result, "COMMIT_RELEASE_AND_INTENT")

    def execute_external_query(
        self,
        *,
        spec: ExternalQuerySpec,
        security_snapshot: SecuritySnapshot,
        policy: SecurityPolicyIdentity,
        offset: float,
    ) -> ExternalQueryExecution:
        factory, lifecycle, _, base = self._repositories()
        before = self.budget.used
        acquired_at = day105._timestamp(base, offset)
        view_id = day105._acquire_view(
            lifecycle,
            request_id=spec.query_id,
            generation_id=spec.generation_id,
            pointer_revision=spec.pointer_revision,
            authorization_id=spec.authorization_snapshot_id,
            acquired_at=acquired_at,
            lease_expires_at=day105._timestamp(base, offset + 120),
        )
        occurrence_ids = day105._query_read_view_ids(
            lifecycle,
            view_id=view_id,
            generation_id=spec.generation_id,
            authorization_id=spec.authorization_snapshot_id,
            query_vector=spec.query_vector,
            top_k=spec.top_k,
            mode=QueryMode.EXACT,
            observed_at=day105._timestamp(base, offset + 0.1),
        )
        if occurrence_ids != spec.expected_occurrence_ids:
            raise AssertionError(f"REAL_PGVECTOR_MISMATCH:{spec.label}")
        security_binding, serving = _security_binding_from_read_view(
            factory=factory,
            request_id=spec.query_id,
            view_id=view_id,
            generation_id=spec.generation_id,
            authorization_snapshot_id=spec.authorization_snapshot_id,
            pointer_revision=spec.pointer_revision,
            authorization_revision=spec.authorization_revision,
            manifest_occurrence_ids=spec.manifest_occurrence_ids,
            security_snapshot=security_snapshot,
            policy=policy,
            lineages=self.lineages,
        )
        retrieval = execute_day101_query(
            serving,
            query_id=spec.query_id,
            query_text=spec.query_text,
            request_attempt_id=spec.query_id,
        )
        binding = self._capstone_binding(
            spec=spec,
            security_binding=security_binding,
            serving_fixture=serving,
            created_at=acquired_at,
        )
        currentness = InMemoryReleaseCurrentnessAuthority()
        _seed_release_currentness(
            factory=factory,
            authority=currentness,
            spec=spec,
            security_binding=security_binding,
            current_security_snapshot=security_snapshot,
            eligible_occurrence_ids=spec.manifest_occurrence_ids,
            policy=policy,
        )
        locals_: dict[str, Any] = {}
        prepared: PreparedQuery | None = None
        try:
            prepared = _prepare_query(
                query_id=spec.query_id,
                bound=BoundAttempt(binding, security_binding),
                serving_fixture=serving,
                release_currentness_authority=currentness,
                retrieval_run=retrieval,
                claims=spec.claims,
                lineages=self.lineages,
                policy=policy,
                observed_at=day105._timestamp(base, offset + 0.2),
                external_grounding=self._runtime(
                    spec=spec,
                    locals_=locals_,
                ),
            )
        except Exception:
            if locals_.get("provider") is not None:
                self._append_provider_outcome(
                    spec=spec,
                    locals_=locals_,
                    prepared=None,
                    observed_at=day105._timestamp(base, offset + 0.3),
                )
            raise
        provider_receipt = self._append_provider_outcome(
            spec=spec,
            locals_=locals_,
            prepared=prepared,
            observed_at=day105._timestamp(base, offset + 0.3),
        )
        decided = None
        if spec.release_immediately:
            decided = _decide_query(
                query_id=spec.query_id,
                prepared=prepared,
                observed_at=day105._timestamp(base, offset + 0.4),
            )
            if decided.record.disposition != "RELEASE":
                raise AssertionError(f"EXPECTED_RELEASE:{spec.label}")
            self._commit_decision(decided)
        released = lifecycle.release_read_view(
            view_id=view_id,
            expected_fencing_token=1,
            released_at=day105._timestamp(base, offset + 0.5),
        )
        if released.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError(f"READ_VIEW_RELEASE_FAILED:{spec.label}")
        after = self.budget.used
        self.accounting.record_call(spec.label, before, after)
        execution = ExternalQueryExecution(
            spec=spec,
            prepared=prepared,
            decided=decided,
            provider_observation=cast(
                OpenAIProviderObservation,
                locals_["observation"],
            ),
            model_invocation_record=cast(
                ModelInvocationRecord,
                locals_["invocation"],
            ),
            provider_attempt=cast(ProviderCallAttempt, locals_["attempt"]),
            provider_receipt=provider_receipt,
            release_currentness=currentness,
            serving_fixture=serving,
        )
        self.executions[spec.label] = execution
        return execution

    def execute_g2_before_p2(
        self,
        lifecycle: PostgresIndexLifecycleRepository,
        factory: ConnectionFactory,
        security: PostgresRagSecurityRepository,
        *,
        security_snapshot: SecuritySnapshot,
        policy: SecurityPolicyIdentity,
        base: datetime,
    ) -> None:
        self.attach_database(
            factory=factory,
            lifecycle=lifecycle,
            security=security,
            base=base,
        )
        for index, spec in enumerate(_g2_specs()):
            self.execute_external_query(
                spec=spec,
                security_snapshot=security_snapshot,
                policy=policy,
                offset=23 + index,
            )

    def block_pending_after_p2(
        self,
        *,
        security_snapshot: SecuritySnapshot,
        policy: SecurityPolicyIdentity,
    ) -> DecidedQuery:
        execution = self.executions["G2_P1_Q3_PENDING"]
        scope = execution.serving_fixture.day100.scope
        current_scope = (
            execution.serving_fixture.day100.authorization.revoke_occurrence(
                tenant_id=scope.tenant_id,
                principal_subject=scope.principal_subject,
                action=scope.action,
                purpose=scope.purpose,
                occurrence_id="A@v1",
            )
        )
        execution.release_currentness.put(_release_snapshot(
            snapshot_id="release-currentness:G2-pending-after-P2",
            revision=2,
            security_binding=replace(
                execution.prepared.bound.security,
                content_security_snapshot_digest=security_snapshot.identity_digest,
                authorization_revision=stable_hash(
                    asdict(current_scope.revisions)
                ),
            ),
            eligible_occurrence_ids=("C@v1",),
            policy=policy,
        ))
        decided = _decide_query(
            query_id="day106-l3b-G2-Q3-pending-after-P2",
            prepared=execution.prepared,
            observed_at=day105._timestamp(cast(datetime, self.base), 48),
        )
        if decided.record.disposition != "BLOCKED":
            raise AssertionError("PENDING_G2_CANDIDATE_NOT_BLOCKED_AFTER_P2")
        self._commit_decision(decided)
        execution.decided = decided
        return decided

    def execute_zero_call_probe(
        self,
        *,
        spec: ExternalQuerySpec,
        security_snapshot: SecuritySnapshot,
        policy: SecurityPolicyIdentity,
        offset: float,
    ) -> str:
        factory, lifecycle, _, base = self._repositories()
        before = self.budget.used
        view_id = day105._acquire_view(
            lifecycle,
            request_id=spec.query_id,
            generation_id=spec.generation_id,
            pointer_revision=spec.pointer_revision,
            authorization_id=spec.authorization_snapshot_id,
            acquired_at=day105._timestamp(base, offset),
            lease_expires_at=day105._timestamp(base, offset + 120),
        )
        observed_ids = day105._query_read_view_ids(
            lifecycle,
            view_id=view_id,
            generation_id=spec.generation_id,
            authorization_id=spec.authorization_snapshot_id,
            query_vector=spec.query_vector,
            top_k=spec.top_k,
            mode=QueryMode.EXACT,
            observed_at=day105._timestamp(base, offset + 0.1),
        )
        if observed_ids != spec.expected_occurrence_ids:
            raise AssertionError(f"ZERO_CALL_PGVECTOR_MISMATCH:{spec.label}")
        security_binding, serving = _security_binding_from_read_view(
            factory=factory,
            request_id=spec.query_id,
            view_id=view_id,
            generation_id=spec.generation_id,
            authorization_snapshot_id=spec.authorization_snapshot_id,
            pointer_revision=spec.pointer_revision,
            authorization_revision=spec.authorization_revision,
            manifest_occurrence_ids=spec.manifest_occurrence_ids,
            security_snapshot=security_snapshot,
            policy=policy,
            lineages=self.lineages,
        )
        retrieval = execute_day101_query(
            serving,
            query_id=spec.query_id,
            query_text=spec.query_text,
            request_attempt_id=spec.query_id,
        )
        binding = self._capstone_binding(
            spec=spec,
            security_binding=security_binding,
            serving_fixture=serving,
            created_at=day105._timestamp(base, offset),
        )
        currentness = InMemoryReleaseCurrentnessAuthority()
        _seed_release_currentness(
            factory=factory,
            authority=currentness,
            spec=spec,
            security_binding=security_binding,
            current_security_snapshot=security_snapshot,
            eligible_occurrence_ids=("C@v1",),
            policy=policy,
        )
        reason = ""
        try:
            _prepare_query(
                query_id=spec.query_id,
                bound=BoundAttempt(binding, security_binding),
                serving_fixture=serving,
                release_currentness_authority=currentness,
                retrieval_run=retrieval,
                claims=spec.claims,
                lineages=self.lineages,
                policy=policy,
                observed_at=day105._timestamp(base, offset + 0.2),
                external_grounding=self._runtime(spec=spec, locals_={}),
            )
        except RuntimeError as exc:
            reason = str(exc)
        if reason != "REQUIRED_EVIDENCE_UNAVAILABLE_BEFORE_PROMPT":
            raise AssertionError(f"ZERO_CALL_GATE_REASON_MISMATCH:{spec.label}")
        released = lifecycle.release_read_view(
            view_id=view_id,
            expected_fencing_token=1,
            released_at=day105._timestamp(base, offset + 0.3),
        )
        if released.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError(f"ZERO_CALL_VIEW_RELEASE_FAILED:{spec.label}")
        self.accounting.record_zero_call_gate(
            spec.label,
            before,
            self.budget.used,
        )
        return reason


def _run_day105_same_execution(
    database_url: str,
    scenario: ExternalScenario,
) -> dict[str, object]:
    """Run Day105 once, injecting G2 calls before its P2 transition."""

    original_reset = day105._reset_and_install
    original_matrix = day105._normal_query_matrix
    original_occurrence = day105._occurrence_record
    original_manifest = day105._manifest
    original_points = day105._points
    previous_flag = os.environ.get("DAY105_L3_INTEGRATION")

    def hooked_matrix(
        repository: PostgresIndexLifecycleRepository,
        factory: ConnectionFactory,
        security_repository: PostgresRagSecurityRepository,
        *,
        security_snapshot: SecuritySnapshot,
        policy: SecurityPolicyIdentity,
        base: datetime,
    ) -> Any:
        matrix, runs = original_matrix(
            repository,
            factory,
            security_repository,
            security_snapshot=security_snapshot,
            policy=policy,
            base=base,
        )
        scenario.execute_g2_before_p2(
            repository,
            factory,
            security_repository,
            security_snapshot=security_snapshot,
            policy=policy,
            base=base,
        )
        return matrix, runs

    day105._reset_and_install = day106_l3a._day106_reset_and_install
    day105._normal_query_matrix = hooked_matrix
    day105._occurrence_record = lambda occurrence_id: _patched_occurrence_record(
        original_occurrence,
        scenario.lineages,
        occurrence_id,
    )
    day105._manifest = lambda occurrence_ids: _patched_manifest(
        scenario.lineages,
        occurrence_ids,
    )
    day105._points = (
        lambda generation_id, occurrence_ids, authorization_id: _patched_points(
            original_points,
            scenario.lineages,
            generation_id,
            occurrence_ids,
            authorization_id,
        )
    )
    os.environ["DAY105_L3_INTEGRATION"] = "1"
    try:
        return day105.run_integration(database_url)
    finally:
        day105._reset_and_install = original_reset
        day105._normal_query_matrix = original_matrix
        day105._occurrence_record = original_occurrence
        day105._manifest = original_manifest
        day105._points = original_points
        if previous_flag is None:
            os.environ.pop("DAY105_L3_INTEGRATION", None)
        else:
            os.environ["DAY105_L3_INTEGRATION"] = previous_flag


def _execution_summary(execution: ExternalQueryExecution) -> dict[str, object]:
    decision = execution.decided
    return {
        "label": execution.spec.label,
        "generation_id": execution.spec.generation_id,
        "authorization_snapshot_id": (
            execution.spec.authorization_snapshot_id
        ),
        "request_binding_digest": execution.prepared.bound.capstone.digest,
        "retrieval_context_receipt_digest": execution.prepared.receipt.digest,
        "retrieval_bundle_digest": (
            execution.prepared.receipt.retrieval_bundle_digest
        ),
        "context_manifest_digest": execution.prepared.context.digest,
        "model_invocation_digest": execution.prepared.invocation.digest,
        "provider_attempt_digest": execution.provider_attempt.digest,
        "provider_receipt_digest": execution.provider_receipt.digest,
        "answer_candidate_digest": execution.prepared.candidate.digest,
        "provider_status": execution.provider_receipt.status.value,
        "call_ordinal": execution.provider_receipt.call_ordinal,
        "input_token_count": execution.provider_receipt.input_token_count,
        "output_token_count": execution.provider_receipt.output_token_count,
        "total_token_count": execution.provider_receipt.total_token_count,
        "release_disposition": (
            "PENDING_RECHECK"
            if decision is None else decision.record.disposition
        ),
        "safe_reason_codes": (
            [] if decision is None else list(decision.record.safe_reason_codes)
        ),
        "unauthorized_prompt_count": (
            execution.prepared.receipt.unauthorized_prompt_count
        ),
    }


def run_fake_dry_run(
    transport: OpenAIResponsesTransport,
) -> dict[str, object]:
    """Exercise the exact five-call schedule without database/API claims."""

    budget = ProviderCallBudget(len(EXPECTED_EXTERNAL_CALLS))
    accounting = ExternalCallAccounting.empty()

    def send(label: str) -> None:
        before = budget.used
        budget.reserve()
        response = transport.send(OpenAIResponsesRequest(
            prompt="SYNTHETIC_DRY_RUN:" + stable_hash(label),
            idempotency_key=stable_hash(("DRY_RUN_ATTEMPT", label)),
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ))
        if response.status_code != 200:
            raise AssertionError(f"FAKE_TRANSPORT_STATUS:{label}")
        accounting.record_call(label, before, budget.used)

    for label in EXPECTED_EXTERNAL_CALLS[:4]:
        send(label)
    accounting.record_zero_call_gate(
        "DAY105_SECURITY_NEGATIVE_CONTROLS",
        budget.used,
        budget.used,
    )
    for label in EXPECTED_ZERO_CALL_GATES[1:]:
        accounting.record_zero_call_gate(label, budget.used, budget.used)
    send(EXPECTED_EXTERNAL_CALLS[4])
    accounting.validate(budget.used)
    payload: dict[str, object] = {
        "schema_version": "day106-l3b-fake-dry-run.v1",
        "scenario_id": SCENARIO_ID,
        "status": "PASS",
        "evidence_level": "DETERMINISTIC_FAKE_TRANSPORT_ONLY",
        "external_call_count": budget.used,
        "external_call_labels": list(accounting.call_labels),
        "zero_call_gates": list(accounting.zero_call_gates),
        "real_database_boundary": "NOT_RUN",
        "external_real_boundary": "NOT_RUN",
        "raw_prompt_logged": False,
        "raw_provider_response_logged": False,
        "raw_secret_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _artifact_digests() -> dict[str, str]:
    missing = [name for name, path in ARTIFACT_PATHS.items() if not path.is_file()]
    if missing:
        raise RuntimeError("L3B_ARTIFACT_MANIFEST_INCOMPLETE:" + ",".join(missing))
    digests = {
        name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in ARTIFACT_PATHS.items()
    }
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip()
    if (
        len(revision) != 40
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise RuntimeError("GIT_BASE_REVISION_UNAVAILABLE")
    digests["base_commit"] = revision
    return digests


def _recover_provider_progress(database_url: str) -> dict[str, object]:
    """Recover durable call state after failure; never infer safe retry."""

    try:
        factory = psycopg2_connection_factory(
            database_url,
            application_name="day106-l3b-failure-recovery-audit",
        )
        row = _query_one(
            factory,
            """
            WITH tenant_requests AS (
              SELECT identity_digest
              FROM day106_l3.request_bindings
              WHERE tenant_id = %s AND pointer_name = %s
            ), tenant_attempts AS (
              SELECT attempt.*
              FROM day106_l3.provider_call_attempts AS attempt
              JOIN tenant_requests AS request
                ON request.identity_digest = attempt.request_binding_digest
            ), tenant_receipts AS (
              SELECT receipt.*
              FROM day106_l3.provider_call_receipts AS receipt
              JOIN tenant_requests AS request
                ON request.identity_digest = receipt.request_binding_digest
            )
            SELECT
              (SELECT COUNT(*) FROM tenant_attempts),
              (SELECT COUNT(*) FROM tenant_receipts),
              (SELECT COUNT(*) FROM tenant_receipts
                 WHERE status = 'SUCCEEDED'),
              (SELECT COUNT(*) FROM tenant_receipts
                 WHERE status = 'FAILED'),
              (SELECT COUNT(*) FROM tenant_receipts
                 WHERE status = 'UNKNOWN'),
              (SELECT COALESCE(MAX(call_ordinal), 0)
                 FROM tenant_attempts)
            """,
            (TENANT_ID, "refund-serving"),
        )
        if row is None:
            raise RuntimeError("PROVIDER_PROGRESS_ROW_UNAVAILABLE")
        attempt_count, receipt_count, succeeded, failed, unknown, latest_ordinal = (
            int(value) for value in row
        )
        identity_rows = _query_rows(
            factory,
            """
            WITH tenant_requests AS (
              SELECT identity_digest
              FROM day106_l3.request_bindings
              WHERE tenant_id = %s AND pointer_name = %s
            )
            SELECT artifact_type, identity_digest
            FROM (
              SELECT 'PROVIDER_ATTEMPT' AS artifact_type,
                     attempt.identity_digest
                FROM day106_l3.provider_call_attempts AS attempt
                JOIN tenant_requests AS request
                  ON request.identity_digest = attempt.request_binding_digest
              UNION ALL
              SELECT 'PROVIDER_RECEIPT', receipt.identity_digest
                FROM day106_l3.provider_call_receipts AS receipt
                JOIN tenant_requests AS request
                  ON request.identity_digest = receipt.request_binding_digest
            ) AS progress
            ORDER BY artifact_type, identity_digest
            """,
            (TENANT_ID, "refund-serving"),
        )
        attempt_digests = tuple(
            str(digest) for artifact_type, digest in identity_rows
            if str(artifact_type) == "PROVIDER_ATTEMPT"
        )
        receipt_digests = tuple(
            str(digest) for artifact_type, digest in identity_rows
            if str(artifact_type) == "PROVIDER_RECEIPT"
        )
        if (
            len(attempt_digests) != attempt_count
            or len(receipt_digests) != receipt_count
        ):
            raise RuntimeError("PROVIDER_PROGRESS_IDENTITY_COUNT_MISMATCH")
        unreceipted = max(0, attempt_count - receipt_count)
        reconciliation_required = unknown > 0 or unreceipted > 0
        if reconciliation_required:
            state = "UNKNOWN"
        elif attempt_count == 0:
            state = "NOT_RUN"
        elif succeeded == receipt_count:
            state = "SUCCEEDED"
        else:
            state = "TERMINAL_MIXED"
        return {
            "attempt_count": attempt_count,
            "receipt_count": receipt_count,
            "succeeded_receipt_count": succeeded,
            "failed_receipt_count": failed,
            "unknown_receipt_count": unknown,
            "unreceipted_attempt_count": unreceipted,
            "latest_call_ordinal": latest_ordinal,
            "attempt_identity_digests": list(attempt_digests),
            "receipt_identity_digests": list(receipt_digests),
            "durable_progress_digest": stable_hash((
                "DAY106_L3B_PROVIDER_PROGRESS_V1",
                attempt_count,
                receipt_count,
                succeeded,
                failed,
                unknown,
                latest_ordinal,
                attempt_digests,
                receipt_digests,
            )),
            "provider_outcome_state": state,
            "reconciliation_required": reconciliation_required,
            "blind_retry_allowed": False,
        }
    except Exception:
        return {
            "attempt_count": None,
            "receipt_count": None,
            "succeeded_receipt_count": None,
            "failed_receipt_count": None,
            "unknown_receipt_count": None,
            "unreceipted_attempt_count": None,
            "latest_call_ordinal": None,
            "attempt_identity_digests": [],
            "receipt_identity_digests": [],
            "durable_progress_digest": None,
            "provider_outcome_state": "UNKNOWN",
            "reconciliation_required": True,
            "blind_retry_allowed": False,
            "safe_reason": "DURABLE_PROVIDER_PROGRESS_UNAVAILABLE",
        }


def _execute_integration(
    database_url: str,
    *,
    transport: OpenAIResponsesTransport,
    evidence_scope: TransportEvidenceScope,
) -> dict[str, object]:
    if os.environ.get(INTEGRATION_FLAG) != "1":
        raise RuntimeError("DAY106_L3B_INTEGRATION_FLAG_REQUIRED")
    if not database_url.strip():
        raise ValueError("DAY106_L3_DATABASE_URL_REQUIRED")
    artifact_digests = _artifact_digests()
    started_at = datetime.now(timezone.utc)
    scenario = ExternalScenario(transport)
    day105_report = _run_day105_same_execution(database_url, scenario)
    if day105_report.get("status") != "PASS":
        raise AssertionError("DAY105_SAME_EXECUTION_PREREQUISITE_FAILED")
    if scenario.budget.used != 4:
        raise AssertionError("DAY105_SECURITY_PHASE_CHANGED_EXTERNAL_CALL_COUNT")
    scenario.accounting.record_zero_call_gate(
        "DAY105_SECURITY_NEGATIVE_CONTROLS",
        4,
        scenario.budget.used,
    )

    factory, lifecycle, _, base = scenario._repositories()
    security = PostgresRagSecurityRepository(factory, integration_enabled=True)
    current = security.current_security_snapshot(day105.TENANT)
    if current is None or current.snapshot_id != "P2" or current.revision != 2:
        raise AssertionError("DAY106_L3B_CURRENT_P2_NOT_FOUND")
    policy = day105._policy()
    pending_decision = scenario.block_pending_after_p2(
        security_snapshot=current,
        policy=policy,
    )
    for index, spec in enumerate(_g3_zero_call_specs()):
        scenario.execute_zero_call_probe(
            spec=spec,
            security_snapshot=current,
            policy=policy,
            offset=50 + index,
        )
    scenario.execute_external_query(
        spec=_g3_q2_spec(),
        security_snapshot=current,
        policy=policy,
        offset=53,
    )
    scenario.accounting.validate(scenario.budget.used)

    rows = _query_one(
        factory,
        """
        SELECT COUNT(*), COUNT(DISTINCT request_binding_digest),
               MIN(call_ordinal), MAX(call_ordinal)
        FROM day106_l3.provider_call_receipts AS receipt
        JOIN day106_l3.request_bindings AS request
          ON request.identity_digest = receipt.request_binding_digest
        WHERE request.tenant_id = %s AND request.pointer_name = %s
        """,
        (TENANT_ID, "refund-serving"),
    )
    if rows is None or tuple(int(value) for value in rows) != (5, 5, 1, 5):
        raise AssertionError("DURABLE_PROVIDER_RECEIPT_MATRIX_MISMATCH")
    executions = [
        _execution_summary(scenario.executions[label])
        for label in EXPECTED_EXTERNAL_CALLS
    ]
    output_token_counts = [
        cast(int, item["output_token_count"])
        for item in executions
    ]
    if any(
        value < 0 or value > MAX_OUTPUT_TOKENS
        for value in output_token_counts
    ):
        raise AssertionError("OBSERVED_OUTPUT_TOKEN_LIMIT_EXCEEDED")
    observed_output_tokens_total = sum(output_token_counts)
    if observed_output_tokens_total > (
        len(EXPECTED_EXTERNAL_CALLS) * MAX_OUTPUT_TOKENS
    ):
        raise AssertionError("OBSERVED_OUTPUT_TOKEN_TOTAL_LIMIT_EXCEEDED")
    pre_restart = _durable_pre_restart_state(factory)
    completed_at = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "schema_version": evidence_scope.schema_version,
        "scenario_id": evidence_scope.scenario_id,
        "run_id": evidence_scope.run_id_prefix + stable_hash((
            started_at.isoformat(),
            evidence_scope.transport_boundary_digest,
            tuple(item["provider_receipt_digest"] for item in executions),
        ))[7:23],
        "status": "PASS",
        "evidence_level": evidence_scope.evidence_level,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "same_database_execution": True,
        "artifact_digests": artifact_digests,
        "day105_execution_checksum": day105_report.get("report_checksum"),
        "external_call_count": scenario.budget.used,
        "observed_output_tokens_total": observed_output_tokens_total,
        "external_calls": executions,
        "zero_call_gates": list(scenario.accounting.zero_call_gates),
        "pending_g2_after_p2": {
            "disposition": pending_decision.record.disposition,
            "safe_reason_codes": list(
                pending_decision.record.safe_reason_codes
            ),
            "response_dispatch_state": (
                pending_decision.record.response_dispatch_state.value
            ),
        },
        "hard_gates": {
            "one_database_execution_not_independent_pass_stitching": "PASS",
            "real_pgvector_readview_each_external_query": "PASS",
            "exact_request_rb_cam_mi_provider_binding": "PASS",
            "model_invocation_persisted_pre_send": "PASS",
            "provider_attempt_reserved_pre_send": "PASS",
            "shared_call_budget_exactly_five": "PASS",
            "each_observed_output_tokens_at_most_64": "PASS",
            "observed_output_tokens_total_at_most_320": "PASS",
            "all_security_negative_controls_zero_external_calls": "PASS",
            "g3_q1_q3_zero_external_calls": "PASS",
            "pending_g2_candidate_blocked_after_p2": "PASS",
            "g3_p2_q2_released": "PASS",
            "unauthorized_occurrence_entering_prompt_zero": "PASS",
            "pre_restart_durable_state_sealed": "PASS",
        },
        "restart_evidence": {
            "status": "PRE_RESTART_SEALED",
            **pre_restart,
            "post_restart_postmaster_started_at": None,
            "post_restart_state_digest": None,
        },
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "raw_provider_response_logged": False,
        "raw_provider_response_id_logged": False,
        "raw_secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning_effort": OPENAI_REASONING_EFFORT,
        "store": False,
        "tools_enabled": False,
        "provider_call_budget": len(EXPECTED_EXTERNAL_CALLS),
        "canonical_python_3_12": "NOT_RUN",
        "transport_boundary": evidence_scope.transport_boundary,
        "transport_boundary_digest": (
            evidence_scope.transport_boundary_digest
        ),
        "external_model_boundary": evidence_scope.external_model_boundary,
        "external_dlp_boundary": "NOT_RUN",
        "production_iam_rls_tls_egress": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "claim_boundary": evidence_scope.claim_boundary,
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def run_integration(
    database_url: str,
    *,
    transport: OpenAIResponsesTransport,
) -> dict[str, object]:
    """Run an injected transport without making an external-real claim."""

    return _execute_integration(
        database_url,
        transport=transport,
        evidence_scope=_injected_transport_evidence_scope(),
    )


def run_real_integration(database_url: str) -> dict[str, object]:
    """Construct and attest the only transport allowed to claim real L3B."""

    transport = _ATTESTED_REAL_TRANSPORT_CLASS()
    evidence_scope = _attested_real_transport_evidence_scope(transport)
    return _execute_integration(
        database_url,
        transport=transport,
        evidence_scope=evidence_scope,
    )


def _fail_closed(
    reason: str,
    error_type: str | None = None,
    *,
    external_call_count: int | None = 0,
    provider_progress: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL_CLOSED",
        "evidence_level": (
            "NOT_RUN" if external_call_count == 0 else "INCONCLUSIVE"
        ),
        "safe_reason": reason,
        "external_call_count": external_call_count,
        "external_real_boundary": (
            "NOT_RUN" if external_call_count == 0 else "INCONCLUSIVE"
        ),
        "durable_provider_progress": provider_progress,
        "blind_retry_allowed": False,
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
    parser.add_argument(
        "--report-path",
        type=Path,
        required=True,
        help="required new report path; existing files are refused",
    )
    arguments = parser.parse_args()
    if os.environ.get(INTEGRATION_FLAG) != "1":
        print(json.dumps(
            _fail_closed("DAY106_L3B_INTEGRATION_FLAG_REQUIRED"),
            indent=2,
            sort_keys=True,
        ))
        return 2
    if os.environ.get(REAL_PROVIDER_FLAG) != "1":
        print(json.dumps(
            _fail_closed("DAY106_L3B_REAL_PROVIDER_FLAG_REQUIRED"),
            indent=2,
            sort_keys=True,
        ))
        return 2
    database_url = os.environ.get(DATABASE_URL_ENV, "")
    if not database_url.strip():
        print(json.dumps(
            _fail_closed("DAY106_L3_DATABASE_URL_REQUIRED"),
            indent=2,
            sort_keys=True,
        ))
        return 2
    report_path = arguments.report_path
    if not report_path.parent.is_dir():
        print(json.dumps(
            _fail_closed("DAY106_L3B_REPORT_PARENT_NOT_FOUND"),
            indent=2,
            sort_keys=True,
        ))
        return 2
    if report_path.exists():
        print(json.dumps(
            _fail_closed("DAY106_L3B_REPORT_PATH_ALREADY_EXISTS"),
            indent=2,
            sort_keys=True,
        ))
        return 2
    try:
        report = run_real_integration(database_url)
    except Exception as exc:
        progress = _recover_provider_progress(database_url)
        failure_report = _fail_closed(
            "DAY106_L3B_INTEGRATION_FAILED",
            type(exc).__name__,
            external_call_count=cast(
                int | None,
                progress.get("attempt_count"),
            ),
            provider_progress=progress,
        )
        try:
            _write_exclusive(report_path, failure_report)
        except Exception as write_exc:
            failure_report = _fail_closed(
                "DAY106_L3B_FAILURE_REPORT_WRITE_FAILED",
                type(write_exc).__name__,
                external_call_count=cast(
                    int | None,
                    progress.get("attempt_count"),
                ),
                provider_progress=progress,
            )
        print(json.dumps(failure_report, indent=2, sort_keys=True))
        return 1
    try:
        _write_exclusive(report_path, report)
    except Exception as exc:
        progress = _recover_provider_progress(database_url)
        print(json.dumps(
            _fail_closed(
                "DAY106_L3B_REPORT_WRITE_FAILED",
                type(exc).__name__,
                external_call_count=cast(
                    int | None,
                    progress.get("attempt_count"),
                ),
                provider_progress=progress,
            ),
            indent=2,
            sort_keys=True,
        ))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
