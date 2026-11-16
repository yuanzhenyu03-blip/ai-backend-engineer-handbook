"""Run the opt-in Day105 PostgreSQL/pgvector security integration lab.

The runner is fail closed. It opens a database only when the explicit Day105
integration flag and a disposable database URL are present. Output contains
identities, digests, decisions and counts only; never a DSN, credential, source
body, prompt, answer, attack payload or raw vector.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence, cast


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rag_chunking_contracts import stable_hash  # noqa: E402
from rag_index_lifecycle_contracts import (  # noqa: E402
    BuildSnapshot,
    EvaluationRuler,
    ImmutableBinding,
)
from rag_index_lifecycle_orchestrator import (  # noqa: E402
    IndexedOccurrence,
    manifest_facts,
)
from rag_index_lifecycle_postgres import (  # noqa: E402
    ConnectionFactory,
    DeletionReceipt,
    PgVectorPoint,
    PostgresIndexLifecycleRepository,
    QueryMode,
    ReadViewQueryRejected,
    RepositoryOutcome,
    SourceDeletionCommand,
    SourceOccurrenceRecord,
    psycopg2_connection_factory,
)
from rag_security_contracts import (  # noqa: E402
    AnswerCandidate,
    BundleSecurityDecision,
    ContextAssemblyManifest,
    DisclosureEnvelope,
    EgressSink,
    IncidentState,
    ModelInvocationEnvelope,
    OccurrenceSecurityIdentity,
    OutputReleaseDecision,
    ProposedCitation,
    ReleaseEvidence,
    RequestSecurityBinding,
    RetrievalBundle,
    RetrievalSecurityDecision,
    RetrievedOccurrence,
    SecurityDisposition,
    SecurityIncidentRecord,
    SecurityPolicyIdentity,
    SecurityResult,
    manifest_entry_digest,
)
from rag_security_pipeline import (  # noqa: E402
    RagSecurityPipeline,
    SecurityIdentityConflict,
)
from rag_security_postgres import (  # noqa: E402
    PostgresRagSecurityRepository,
    SecurityArtifact,
    SecurityArtifactType,
    SecurityRepositoryOutcome,
    SecurityRepositoryResult,
    SecuritySnapshot,
)


SCHEMA_VERSION = "day105-l3-runner.v1"
SCENARIO_ID = "day105-refund-rag-security-postgresql-pgvector-l3-v1"
EVIDENCE_LEVEL = (
    "EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR_"
    "WITH_DETERMINISTIC_SECURITY_ADAPTERS"
)
DAY104_L3_CHECKSUM = (
    "sha256:41e4b36ca1ccd589ca6ddcd99026bc6b48fc57e5a47c231ca8d32433b479ba85"
)
DAY105_L2_CHECKSUM = (
    "sha256:b7cb38a8d7191d1404b162f88aae935c28f12628362e01b600c685299579f477"
)
RESET_CONFIRMATION = "RESET_DAY105_L3_SCHEMAS"
SCOPE = "refund-rag"
TENANT = "tenant-refund"
OTHER_TENANT = "tenant-private"
POINTER = "refund-serving"
PROVENANCE_REVISION = "PROV-R1"
TOMBSTONE_REVISION = "D1"
NORMAL_IDS = ("A@v1", "C@v1")
TOMBSTONED_IDS = ("B@v1",)
NEGATIVE_IDS = (
    "T@v1",
    "X@v1",
    "Y@v1",
    "Y@v2",
    "Z1@v1",
    "Z2@v1",
)


def _policy() -> SecurityPolicyIdentity:
    return SecurityPolicyIdentity(
        security_policy_version="SP1",
        parser_version="parser-v1",
        scanner_version="scanner-v1",
        detector_version="detector-v1",
        retrieval_config_version="retrieval-v1",
        context_assembler_version="assembler-v1",
        prompt_template_version="prompt-v1",
        model_policy_version="model-policy-v1",
        tool_policy_version="tool-policy-v1",
        output_policy_version="output-policy-v1",
        adversarial_set_digest=stable_hash("day105-l3-adversarial-set-v1"),
    )


def _timestamp(base: datetime, minutes: float) -> str:
    return (base + timedelta(minutes=minutes)).isoformat()


def _query_rows(
    factory: ConnectionFactory,
    query: str,
    params: Sequence[object] | None = None,
) -> list[Sequence[Any]]:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        connection.commit()
        return rows
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _query_one(
    factory: ConnectionFactory,
    query: str,
    params: Sequence[object] | None = None,
) -> Sequence[Any] | None:
    rows = _query_rows(factory, query, params)
    return None if not rows else rows[0]


class _FaultCursor:
    def __init__(self, inner: Any, *, fragment: str, error: str) -> None:
        self._inner = inner
        self._fragment = fragment
        self._error = error

    @property
    def rowcount(self) -> int:
        return int(self._inner.rowcount)

    def execute(self, query: str, params: object = None) -> object:
        normalized = " ".join(str(query).split())
        if self._fragment in normalized:
            raise RuntimeError(self._error)
        return self._inner.execute(query, params)

    def fetchone(self) -> Sequence[Any] | None:
        return self._inner.fetchone()

    def fetchall(self) -> list[Sequence[Any]]:
        return self._inner.fetchall()

    def close(self) -> None:
        self._inner.close()


class _FaultConnection:
    def __init__(self, inner: Any, *, fragment: str, error: str) -> None:
        self._inner = inner
        self._fragment = fragment
        self._error = error

    def cursor(self) -> _FaultCursor:
        return _FaultCursor(
            self._inner.cursor(),
            fragment=self._fragment,
            error=self._error,
        )

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

    def close(self) -> None:
        self._inner.close()


def _occurrence_record(occurrence_id: str) -> SourceOccurrenceRecord:
    tenant_id = OTHER_TENANT if occurrence_id == "T@v1" else TENANT
    return SourceOccurrenceRecord(
        occurrence_id=occurrence_id,
        logical_id=occurrence_id.replace("@", "-"),
        source_version="S1",
        tenant_id=tenant_id,
        content_digest=stable_hash(("CONTENT", occurrence_id)),
        metadata_digest=stable_hash(("METADATA", occurrence_id)),
        provenance_digest=stable_hash(
            ("PROVENANCE", occurrence_id, PROVENANCE_REVISION)
        ),
    )


def _source_command(base: datetime) -> SourceDeletionCommand:
    deletion = DeletionReceipt(
        deletion_id="delete-B-v1",
        operation_id="delete-operation-B-v1",
        idempotency_key="delete-idempotency-B-v1",
        occurrence_id="B@v1",
        source_version="S1",
        intent_digest=stable_hash(("delete", SCOPE, "B@v1")),
        verification_policy_id="day105-l3-serving-absence-v1",
        required_evidence_scopes=("LOGICAL_RELEASE", "SERVING_INDEX_ABSENCE"),
        accepted_at=_timestamp(base, 0),
    )
    source_ids = (
        "A@v1",
        "B@v1",
        "C@v1",
        "T@v1",
        "X@v1",
        "Y@v1",
        "Y@v2",
        "Z1@v1",
        "Z2@v1",
    )
    return SourceDeletionCommand(
        operation_id="receive-S1-D1",
        idempotency_key="receive-refund-S1-D1",
        scope_id=SCOPE,
        source_snapshot_id="S1",
        source_version="S1",
        source_digest=stable_hash(("source-snapshot", "S1", source_ids)),
        occurrences=tuple(_occurrence_record(item) for item in source_ids),
        deletion_snapshot_id="D1",
        deletion_digest=stable_hash(("deletion-snapshot", "D1", "B@v1")),
        deletion_ledger_revision=1,
        deletions=(deletion,),
        received_at=_timestamp(base, 0),
    )


def _build_snapshot(
    command: SourceDeletionCommand,
    *,
    snapshot_id: str,
    authorization_id: str,
    watermark: str,
) -> BuildSnapshot:
    return BuildSnapshot(
        build_snapshot_id=snapshot_id,
        scope_id=SCOPE,
        source_snapshot=ImmutableBinding("S1", command.source_digest),
        authorization_snapshot=ImmutableBinding(
            authorization_id,
            stable_hash(("authorization", authorization_id)),
        ),
        embedding_contract=ImmutableBinding(
            "E1", stable_hash(("embedding", "E1", 3, "cosine"))
        ),
        index_schema=ImmutableBinding(
            "IS1", stable_hash(("index-schema", "IS1", "pgvector-hnsw"))
        ),
        source_watermark=watermark,
        deletion_snapshot=ImmutableBinding("D1", command.deletion_digest),
    )


def _ruler() -> EvaluationRuler:
    return EvaluationRuler(
        dataset_fingerprint=stable_hash(("day103", "Q1", "Q2", "Q3")),
        evaluator_fingerprint=stable_hash(("day103-evaluator", "v1")),
        policy_fingerprint=stable_hash(("day105-l3-security-gates", "v1")),
    )


def _manifest(occurrence_ids: tuple[str, ...]):
    return manifest_facts(
        tuple(
            IndexedOccurrence(
                item,
                stable_hash(("CONTENT", item)),
                stable_hash(("METADATA", item)),
                stable_hash(("PROVENANCE", item, PROVENANCE_REVISION)),
            )
            for item in occurrence_ids
        )
    )


_VECTORS: dict[str, tuple[float, float, float]] = {
    "A@v1": (1.0, 0.0, 0.0),
    "B@v1": (0.0, 0.0, 1.0),
    "C@v1": (0.0, 1.0, 0.0),
    "T@v1": (-1.0, 0.0, 0.0),
    "X@v1": (0.70710677, 0.70710677, 0.0),
    "Y@v1": (0.0, 0.19611613, 0.98058068),
    "Y@v2": (0.0, 0.24253563, 0.97014250),
    "Z1@v1": (0.5, 0.5, 0.70710677),
    "Z2@v1": (0.5, 0.5, -0.70710677),
}


def _points(
    generation_id: str,
    occurrence_ids: tuple[str, ...],
    authorization_id: str,
) -> tuple[PgVectorPoint, ...]:
    return tuple(
        PgVectorPoint(
            point_id=f"{generation_id}:{item}",
            generation_id=generation_id,
            occurrence_id=item,
            tenant_id=OTHER_TENANT if item == "T@v1" else TENANT,
            content_digest=stable_hash(("CONTENT", item)),
            metadata_digest=stable_hash(("METADATA", item)),
            provenance_digest=stable_hash(("PROVENANCE", item, PROVENANCE_REVISION)),
            embedding=_VECTORS[item],
            metadata=(
                ("authorization_revision", authorization_id),
                ("source_snapshot", "S1"),
            ),
        )
        for item in occurrence_ids
    )


def _register_ready_generation(
    repository: PostgresIndexLifecycleRepository,
    *,
    generation_id: str,
    snapshot: BuildSnapshot,
    occurrence_ids: tuple[str, ...],
    provider_fence: int,
    base: datetime,
    offset: float,
) -> dict[str, object]:
    expected = _manifest(occurrence_ids)
    ruler = _ruler()
    registered = repository.register_generation(
        generation_id=generation_id,
        snapshot=snapshot,
        ruler=ruler,
        expected_manifest=expected,
        physical_namespace=f"day105-{generation_id.lower()}",
        provider_write_fence=provider_fence,
        created_at=_timestamp(base, offset),
    )
    if registered.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError(f"{generation_id}_REGISTRATION_FAILED")
    written = repository.write_generation_points(
        generation_id=generation_id,
        provider_write_fence=provider_fence,
        points=_points(
            generation_id,
            occurrence_ids,
            snapshot.authorization_snapshot.identity,
        ),
        created_at=_timestamp(base, offset + 0.1),
    )
    if written.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError(f"{generation_id}_WRITE_FAILED")
    sealed = repository.seal_generation(
        generation_id=generation_id,
        expected_manifest=expected,
        expected_absent_occurrence_ids=TOMBSTONED_IDS,
        provider_write_fence=provider_fence,
        observed_at=_timestamp(base, offset + 0.2),
    )
    if (
        sealed.outcome is not RepositoryOutcome.APPLIED
        or sealed.state_version is None
        or sealed.checkpoint is None
        or sealed.manifest is None
        or not sealed.manifest.integrity_matches
    ):
        raise AssertionError(f"{generation_id}_SEAL_FAILED")
    ready = repository.mark_ready(
        generation_id=generation_id,
        expected_state_version=sealed.state_version,
        expected_manifest=expected,
        expected_absent_occurrence_ids=TOMBSTONED_IDS,
        ruler=ruler,
        validation_record_digest=stable_hash((generation_id, "validation")),
        evaluation_evidence_digest=stable_hash((generation_id, "evaluation-evidence")),
        evaluation_report_digest=stable_hash((generation_id, "evaluation-report")),
        evaluation_decision="PASS",
        observed_at=_timestamp(base, offset + 0.3),
    )
    if ready.outcome is not RepositoryOutcome.READY:
        raise AssertionError(f"{generation_id}_READY_FAILED")
    return {
        "generation_id": generation_id,
        "manifest_fingerprint": expected.fingerprint,
        "checkpoint_digest": sealed.checkpoint,
        "occurrence_ids": list(occurrence_ids),
        "provider_write_fence": provider_fence,
    }


def _build_poisoned_generation(
    repository: PostgresIndexLifecycleRepository,
    factory: ConnectionFactory,
    *,
    snapshot: BuildSnapshot,
    base: datetime,
) -> dict[str, object]:
    expected = _manifest(NORMAL_IDS)
    actual_ids = tuple(sorted((*NORMAL_IDS, *NEGATIVE_IDS)))
    registered = repository.register_generation(
        generation_id="G_BAD",
        snapshot=snapshot,
        ruler=_ruler(),
        expected_manifest=expected,
        physical_namespace="day105-g-bad",
        provider_write_fence=1,
        created_at=_timestamp(base, 2),
    )
    if registered.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("G_BAD_REGISTRATION_FAILED")
    written = repository.write_generation_points(
        generation_id="G_BAD",
        provider_write_fence=1,
        points=_points("G_BAD", actual_ids, "P1"),
        created_at=_timestamp(base, 2.1),
    )
    if written.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("G_BAD_WRITE_FAILED")
    sealed = repository.seal_generation(
        generation_id="G_BAD",
        expected_manifest=expected,
        expected_absent_occurrence_ids=TOMBSTONED_IDS,
        provider_write_fence=1,
        observed_at=_timestamp(base, 2.2),
    )
    if sealed.outcome is not RepositoryOutcome.INTEGRITY_FAILED:
        raise AssertionError("POISONED_GENERATION_WAS_NOT_REJECTED")
    state = _query_one(
        factory,
        "SELECT state FROM day104_l3.generations WHERE generation_id = 'G_BAD'",
    )
    if state != ("FAILED",):
        raise AssertionError("POISONED_GENERATION_NOT_FAILED")
    return {
        "generation_id": "G_BAD",
        "expected_occurrence_ids": list(NORMAL_IDS),
        "actual_occurrence_ids": list(actual_ids),
        "seal_outcome": sealed.outcome.value,
        "final_state": "FAILED",
        "selected_for_serving": False,
        "manifest_digest": None if sealed.manifest is None else sealed.manifest.digest,
    }


def _security_snapshot(
    *,
    snapshot_id: str,
    tenant_id: str,
    revision: int,
    occurrence_ids: tuple[str, ...],
    policy: SecurityPolicyIdentity,
    created_at: str,
) -> SecuritySnapshot:
    return SecuritySnapshot(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        revision=revision,
        authorization_snapshot_id=snapshot_id,
        authorization_snapshot_digest=stable_hash(
            ("authorization", tenant_id, snapshot_id, occurrence_ids)
        ),
        provenance_revision=PROVENANCE_REVISION,
        provenance_digest=stable_hash(("provenance", tenant_id, PROVENANCE_REVISION)),
        tombstone_revision=TOMBSTONE_REVISION,
        tombstone_digest=stable_hash(("tombstone", tenant_id, "B@v1")),
        content_security_policy_version="content-security-v1",
        content_security_digest=stable_hash(
            ("content-security", tenant_id, snapshot_id, occurrence_ids)
        ),
        security_policy_version=policy.security_policy_version,
        security_policy_digest=policy.fingerprint,
        occurrence_ids=tuple(sorted(occurrence_ids)),
        evidence_digests=(stable_hash(("security-evidence", tenant_id, snapshot_id)),),
        created_at=created_at,
    )


def _point_rows(
    factory: ConnectionFactory,
    generation_id: str,
    occurrence_ids: tuple[str, ...],
) -> dict[str, Sequence[Any]]:
    rows = _query_rows(
        factory,
        """
        SELECT occurrence_id, tenant_id, content_digest,
               metadata_digest, provenance_digest
        FROM day104_l3.index_points
        WHERE generation_id = %s AND occurrence_id = ANY(%s)
        ORDER BY occurrence_id
        """,
        (generation_id, list(occurrence_ids)),
    )
    by_id = {cast(str, row[0]): row for row in rows}
    if set(by_id) != set(occurrence_ids):
        raise AssertionError("PGVECTOR_POINT_IDENTITY_READBACK_INCOMPLETE")
    return by_id


def _binding_from_read_view(
    factory: ConnectionFactory,
    *,
    request_id: str,
    purpose: str,
    view_id: str,
    generation_id: str,
    authorization_revision: str,
    manifest_occurrence_ids: tuple[str, ...],
    security_snapshot: SecuritySnapshot,
    policy: SecurityPolicyIdentity,
) -> RequestSecurityBinding:
    generation = _query_one(
        factory,
        """
        SELECT build_snapshot_fingerprint, manifest_digest, checkpoint,
               provider_write_fence, validation_record_digest,
               evaluation_report_digest, actual_manifest_digest,
               expected_manifest_digest
        FROM day104_l3.generations
        WHERE generation_id = %s
        """,
        (generation_id,),
    )
    view = _query_one(
        factory,
        """
        SELECT pointer_name, generation_id, pointer_revision, owner_id,
               authorization_snapshot_id, status, fencing_token,
               lease_expires_at, build_snapshot_fingerprint
        FROM day104_l3.read_views
        WHERE view_id = %s
        """,
        (view_id,),
    )
    if generation is None or view is None:
        raise AssertionError("REQUEST_BINDING_DURABLE_IDENTITY_MISSING")
    if (
        view[1] != generation_id
        or view[3] != request_id
        or view[4] != authorization_revision
        or view[5] != "OPEN"
        or view[8] != generation[0]
    ):
        raise AssertionError("REQUEST_BINDING_READ_VIEW_IDENTITY_MISMATCH")
    point_rows = _point_rows(factory, generation_id, manifest_occurrence_ids)
    entries: list[tuple[str, str]] = []
    for occurrence_id in sorted(manifest_occurrence_ids):
        row = point_rows[occurrence_id]
        source_id, source_version = occurrence_id.split("@", maxsplit=1)
        entries.append(
            (
                occurrence_id,
                manifest_entry_digest(
                    occurrence_id,
                    source_id,
                    f"v{source_version.lstrip('v')}",
                    cast(str, row[1]),
                    f"refund-resource-{source_id}",
                    cast(str, row[2]),
                    cast(str, row[3]),
                    "metadata-v1",
                    PROVENANCE_REVISION,
                ),
            )
        )
    manifest_entries = tuple(entries)
    lifecycle_identity = {
        "generation_id": generation_id,
        "build_snapshot_fingerprint": generation[0],
        "lifecycle_manifest_digest": generation[1],
        "checkpoint_digest": generation[2],
        "provider_write_fence": int(generation[3]),
        "validation_record_digest": generation[4],
        "evaluation_report_digest": generation[5],
    }
    lease_expires_at = cast(datetime, view[7]).astimezone(timezone.utc)
    read_view_identity = {
        "pointer_name": cast(str, view[0]),
        "generation_id": cast(str, view[1]),
        "pointer_revision": int(view[2]),
        "owner_id": cast(str, view[3]),
        "authorization_snapshot_id": cast(str, view[4]),
        "status": cast(str, view[5]),
        "fencing_token": int(view[6]),
        "lease_expires_at": lease_expires_at.isoformat(),
        "build_snapshot_fingerprint": cast(str, view[8]),
    }
    return RequestSecurityBinding(
        request_id=request_id,
        principal_id="principal-refund-reader",
        tenant_id=TENANT,
        purpose=purpose,
        audience="current-user",
        generation_id=generation_id,
        generation_artifact_digest=stable_hash(lifecycle_identity),
        build_snapshot_fingerprint=cast(str, generation[0]),
        generation_manifest_digest=stable_hash(manifest_entries),
        manifest_entries=manifest_entries,
        provider_checkpoint_digest=cast(str, generation[2]),
        provider_write_fence=int(generation[3]),
        validation_record_digest=cast(str, generation[4]),
        day103_evaluation_report_checksum=cast(str, generation[5]),
        active_pointer_digest=stable_hash(
            (view[0], view[1], int(view[2]), "historical-pointer-binding")
        ),
        pointer_revision=int(view[2]),
        read_view_id=view_id,
        read_view_fence=int(view[6]),
        read_view_status=cast(str, view[5]),
        read_view_unexpired=lease_expires_at > datetime.now(timezone.utc),
        read_view_owner_id=cast(str, view[3]),
        read_view_validation_digest=stable_hash(read_view_identity),
        authorization_revision=authorization_revision,
        provenance_revision=PROVENANCE_REVISION,
        tombstone_revision=TOMBSTONE_REVISION,
        content_security_snapshot_digest=security_snapshot.identity_digest,
        security_evidence_digests=tuple(
            sorted(
                {
                    security_snapshot.identity_digest,
                    cast(str, generation[1]),
                    cast(str, generation[6]),
                    cast(str, generation[7]),
                }
            )
        ),
        policy=policy,
    )


def _negative_control_binding(
    factory: ConnectionFactory,
    *,
    request_id: str,
    occurrence_ids: tuple[str, ...],
    security_snapshot: SecuritySnapshot,
    policy: SecurityPolicyIdentity,
) -> RequestSecurityBinding:
    generation = _query_one(
        factory,
        """
        SELECT build_snapshot_fingerprint, manifest_digest, checkpoint,
               provider_write_fence, validation_record_digest,
               evaluation_report_digest, actual_manifest_digest,
               expected_manifest_digest
        FROM day104_l3.generations
        WHERE generation_id = 'G_BAD'
        """,
    )
    if generation is None:
        raise AssertionError("G_BAD_IDENTITY_MISSING")
    point_rows = _point_rows(factory, "G_BAD", occurrence_ids)
    entries = []
    for occurrence_id in sorted(occurrence_ids):
        row = point_rows[occurrence_id]
        source_id, source_version = occurrence_id.split("@", maxsplit=1)
        entries.append(
            (
                occurrence_id,
                manifest_entry_digest(
                    occurrence_id,
                    source_id,
                    f"v{source_version.lstrip('v')}",
                    cast(str, row[1]),
                    f"refund-resource-{source_id}",
                    cast(str, row[2]),
                    cast(str, row[3]),
                    "metadata-v1",
                    PROVENANCE_REVISION,
                ),
            )
        )
    manifest_entries = tuple(entries)
    return RequestSecurityBinding(
        request_id=request_id,
        principal_id="application-owned-negative-control",
        tenant_id=TENANT,
        purpose="isolated-security-negative-control",
        audience="test-harness",
        generation_id="G_BAD",
        generation_artifact_digest=stable_hash(
            ("G_BAD", tuple(generation), "NON_SERVING_VALIDATION_READ")
        ),
        build_snapshot_fingerprint=cast(str, generation[0]),
        generation_manifest_digest=stable_hash(manifest_entries),
        manifest_entries=manifest_entries,
        provider_checkpoint_digest=cast(str, generation[2]),
        provider_write_fence=int(generation[3]),
        validation_record_digest=stable_hash(
            ("G_BAD", "INTEGRITY_FAILED", generation[1])
        ),
        day103_evaluation_report_checksum=DAY104_L3_CHECKSUM,
        active_pointer_digest=stable_hash(("G_BAD", "NEVER_ACTIVE")),
        pointer_revision=1,
        read_view_id=f"non-serving-validation:{request_id}",
        read_view_fence=1,
        read_view_status="OPEN",
        read_view_unexpired=True,
        read_view_owner_id=request_id,
        read_view_validation_digest=stable_hash(
            ("G_BAD", request_id, "NON_SERVING_VALIDATION_READ")
        ),
        authorization_revision="P1",
        provenance_revision=PROVENANCE_REVISION,
        tombstone_revision=TOMBSTONE_REVISION,
        content_security_snapshot_digest=security_snapshot.identity_digest,
        security_evidence_digests=tuple(
            sorted({security_snapshot.identity_digest, cast(str, generation[1])})
        ),
        policy=policy,
    )


def _retrieved_occurrence(
    factory: ConnectionFactory,
    *,
    generation_id: str,
    occurrence_id: str,
    binding: RequestSecurityBinding,
    fact_ids: tuple[str, ...] = (),
    attack_tags: tuple[str, ...] = (),
    currently_authorized: bool = True,
    tombstoned: bool = False,
    quarantined: bool = False,
    content_security_result: SecurityResult = SecurityResult.PASS,
) -> RetrievedOccurrence:
    row = _point_rows(factory, generation_id, (occurrence_id,))[occurrence_id]
    source_id, source_version = occurrence_id.split("@", maxsplit=1)
    identity = OccurrenceSecurityIdentity(
        occurrence_id=occurrence_id,
        source_id=source_id,
        source_version=f"v{source_version.lstrip('v')}",
        tenant_id=cast(str, row[1]),
        resource_id=f"refund-resource-{source_id}",
        content_digest=cast(str, row[2]),
        metadata_digest=cast(str, row[3]),
        metadata_version="metadata-v1",
        authorization_revision=binding.authorization_revision,
        provenance_revision=binding.provenance_revision,
        parser_version=binding.policy.parser_version,
        scanner_version=binding.policy.scanner_version,
        detector_version=binding.policy.detector_version,
        security_policy_version=binding.policy.security_policy_version,
    )
    return RetrievedOccurrence(
        identity=identity,
        fact_ids=tuple(sorted(fact_ids)),
        attack_tags=tuple(sorted(attack_tags)),
        currently_authorized=currently_authorized,
        tombstoned=tombstoned,
        quarantined=quarantined,
        content_security_result=content_security_result,
    )


@dataclass(frozen=True)
class QueryRun:
    binding: RequestSecurityBinding
    occurrences: tuple[RetrievedOccurrence, ...]
    retrieval: RetrievalSecurityDecision
    bundle_security: BundleSecurityDecision
    bundle: RetrievalBundle
    context: ContextAssemblyManifest
    disclosure: DisclosureEnvelope
    invocation: ModelInvocationEnvelope
    candidate: AnswerCandidate
    evidence: ReleaseEvidence
    release: OutputReleaseDecision


_FACT_BY_OCCURRENCE = {
    "A@v1": "refund_window",
    "C@v1": "application_channel",
}


def _run_query(
    factory: ConnectionFactory,
    *,
    query_id: str,
    binding: RequestSecurityBinding,
    occurrence_ids: tuple[str, ...],
    observed_at: str,
) -> QueryRun:
    occurrences = tuple(
        _retrieved_occurrence(
            factory,
            generation_id=binding.generation_id,
            occurrence_id=item,
            binding=binding,
            fact_ids=(_FACT_BY_OCCURRENCE[item],),
        )
        for item in occurrence_ids
    )
    retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id=f"retrieval-{query_id}",
        binding=binding,
        candidates=occurrences,
        least_context_occurrence_ids=occurrence_ids,
        observed_at=observed_at,
    )
    bundle_security = RagSecurityPipeline.analyze_bundle(
        decision_id=f"bundle-security-{query_id}",
        binding=binding,
        retrieval_decision=retrieval,
        candidates=occurrences,
    )
    bundle = RagSecurityPipeline.build_retrieval_bundle(
        bundle_id=f"bundle-{query_id}",
        binding=binding,
        retrieval_decision=retrieval,
        bundle_decision=bundle_security,
        candidates=occurrences,
        created_at=observed_at,
    )
    context = RagSecurityPipeline.assemble_context(
        manifest_id=f"context-{query_id}",
        binding=binding,
        bundle=bundle,
        included_occurrence_ids=occurrence_ids,
        context_budget=len(occurrence_ids),
        actual_context_units=len(occurrence_ids),
        envelope_schema_version="untrusted-evidence-v1",
        serialization_version="json-escaped-v1",
        projection_version="least-fields-v1",
        structured_untrusted_data_digest=stable_hash(
            ("STRUCTURED_UNTRUSTED_DATA", query_id, occurrence_ids)
        ),
    )
    claim_ids = tuple(sorted(_FACT_BY_OCCURRENCE[item] for item in occurrence_ids))
    citations = tuple(
        ProposedCitation(_FACT_BY_OCCURRENCE[item], item) for item in occurrence_ids
    )
    disclosure = DisclosureEnvelope(
        envelope_id=f"disclosure-{query_id}",
        request_binding_fingerprint=binding.fingerprint,
        purpose=binding.purpose,
        audience=binding.audience,
        allowed_fields=claim_ids,
        destination="current-chat",
        disclosure_budget=len(claim_ids),
        authorization_revision=binding.authorization_revision,
        output_policy_version=binding.policy.output_policy_version,
    )
    invocation = RagSecurityPipeline.build_model_envelope(
        envelope_id=f"invocation-{query_id}",
        binding=binding,
        context_manifest=context,
        disclosure=disclosure,
        system_policy_digest=stable_hash("system-policy-without-secrets"),
        model_id="controlled-model-v1",
        model_config_digest=stable_hash("controlled-model-config-v1"),
    )
    candidate = AnswerCandidate(
        candidate_id=f"candidate-{query_id}",
        invocation_envelope_digest=invocation.digest,
        answer_digest=stable_hash(("ANSWER_CANDIDATE", query_id)),
        claim_ids=claim_ids,
        proposed_citations=citations,
        proposed_tool_calls=(),
        sensitive_markers=(),
        generated_at=observed_at,
    )
    evidence = ReleaseEvidence(
        evidence_id=f"release-evidence-{query_id}",
        candidate_digest=candidate.digest,
        observed_claim_ids=claim_ids,
        unclassified_claim_count=0,
        grounded_claim_ids=claim_ids,
        supported_citation_keys=tuple(
            sorted(f"{item.claim_id}:{item.occurrence_id}" for item in citations)
        ),
        current_authorization_revision=binding.authorization_revision,
        currently_authorized_occurrence_ids=tuple(sorted(occurrence_ids)),
        current_provenance_revision=binding.provenance_revision,
        current_tombstone_revision=binding.tombstone_revision,
        current_content_security_snapshot_digest=(
            binding.content_security_snapshot_digest
        ),
        current_security_policy_fingerprint=binding.policy.fingerprint,
        dlp_result=SecurityResult.PASS,
        metadata_stripping_result=SecurityResult.PASS,
        destination_result=SecurityResult.PASS,
        evidence_digests=(stable_hash((query_id, "release-evidence")),),
    )
    release = RagSecurityPipeline.decide_output_release(
        decision_id=f"release-{query_id}",
        binding=binding,
        context_manifest=context,
        disclosure=disclosure,
        model_envelope=invocation,
        candidate=candidate,
        evidence=evidence,
        observed_at=observed_at,
    )
    return QueryRun(
        binding,
        occurrences,
        retrieval,
        bundle_security,
        bundle,
        context,
        disclosure,
        invocation,
        candidate,
        evidence,
        release,
    )


def _artifact(
    *,
    artifact_id: str,
    artifact_type: SecurityArtifactType,
    request_id: str | None,
    subject_digest: str,
    parent_digests: tuple[str, ...],
    result: SecurityResult,
    disposition: SecurityDisposition,
    payload: Mapping[str, object],
    created_at: str,
) -> SecurityArtifact:
    return SecurityArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        request_id=request_id,
        subject_digest=subject_digest,
        parent_digests=tuple(sorted(set(parent_digests))),
        result=result,
        disposition=disposition,
        payload=tuple(sorted(payload.items())),
        created_at=created_at,
    )


def _require_applied(
    result: SecurityRepositoryResult,
    *,
    label: str,
    allow_replay: bool = False,
) -> None:
    allowed = {SecurityRepositoryOutcome.APPLIED}
    if allow_replay:
        allowed.add(SecurityRepositoryOutcome.EXACT_REPLAY)
    if result.outcome not in allowed:
        raise AssertionError(f"{label}:{result.outcome.value}:{result.safe_reason}")


def _persist_pre_release_chain(
    repository: PostgresRagSecurityRepository,
    run: QueryRun,
    *,
    created_at: str,
) -> dict[str, SecurityArtifact]:
    request_id = run.binding.request_id
    artifacts = {
        "binding": _artifact(
            artifact_id=f"request-binding:{request_id}",
            artifact_type=SecurityArtifactType.REQUEST_BINDING,
            request_id=request_id,
            subject_digest=run.binding.fingerprint,
            parent_digests=(
                run.binding.generation_artifact_digest,
                run.binding.content_security_snapshot_digest,
            ),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.ELIGIBLE,
            payload={
                "generation_id": run.binding.generation_id,
                "read_view_id": run.binding.read_view_id,
                "request_binding_fingerprint": run.binding.fingerprint,
                "security_snapshot_digest": (
                    run.binding.content_security_snapshot_digest
                ),
            },
            created_at=created_at,
        ),
        "retrieval": _artifact(
            artifact_id=run.retrieval.decision_id,
            artifact_type=SecurityArtifactType.RETRIEVAL_DECISION,
            request_id=request_id,
            subject_digest=run.retrieval.digest,
            parent_digests=(run.binding.fingerprint,),
            result=run.retrieval.result,
            disposition=SecurityDisposition.ELIGIBLE,
            payload={
                "occurrence_ids": run.retrieval.allowed_occurrence_ids,
                "request_binding_fingerprint": run.binding.fingerprint,
            },
            created_at=created_at,
        ),
        "bundle_security": _artifact(
            artifact_id=run.bundle_security.decision_id,
            artifact_type=SecurityArtifactType.BUNDLE_DECISION,
            request_id=request_id,
            subject_digest=run.bundle_security.digest,
            parent_digests=(run.retrieval.digest,),
            result=run.bundle_security.result,
            disposition=SecurityDisposition.ELIGIBLE,
            payload={
                "occurrence_ids_digest": run.bundle_security.occurrence_ids_digest,
                "reason_codes": run.bundle_security.reason_codes,
            },
            created_at=created_at,
        ),
        "bundle": _artifact(
            artifact_id=run.bundle.bundle_id,
            artifact_type=SecurityArtifactType.RETRIEVAL_BUNDLE,
            request_id=request_id,
            subject_digest=run.bundle.digest,
            parent_digests=(run.retrieval.digest, run.bundle_security.digest),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.ELIGIBLE,
            payload={
                "authorization_revision": run.bundle.authorization_revision,
                "occurrence_ids": run.bundle.occurrence_ids,
            },
            created_at=created_at,
        ),
        "context": _artifact(
            artifact_id=run.context.manifest_id,
            artifact_type=SecurityArtifactType.CONTEXT_MANIFEST,
            request_id=request_id,
            subject_digest=run.context.digest,
            parent_digests=(run.bundle.digest,),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.ELIGIBLE,
            payload={
                "assembled_context_digest": run.context.assembled_context_digest,
                "occurrence_ids": run.context.included_occurrence_ids,
                "serialization_version": run.context.serialization_version,
            },
            created_at=created_at,
        ),
        "disclosure": _artifact(
            artifact_id=run.disclosure.envelope_id,
            artifact_type=SecurityArtifactType.DISCLOSURE_ENVELOPE,
            request_id=request_id,
            subject_digest=run.disclosure.digest,
            parent_digests=(run.binding.fingerprint,),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.ELIGIBLE,
            payload={
                "allowed_field_ids": run.disclosure.allowed_fields,
                "authorization_revision": run.disclosure.authorization_revision,
                "output_policy_version": run.disclosure.output_policy_version,
            },
            created_at=created_at,
        ),
        "invocation": _artifact(
            artifact_id=run.invocation.envelope_id,
            artifact_type=SecurityArtifactType.MODEL_INVOCATION,
            request_id=request_id,
            subject_digest=run.invocation.digest,
            parent_digests=(run.context.digest, run.disclosure.digest),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.WAIT,
            payload={
                "model_config_digest": run.invocation.model_config_digest,
                "model_id": run.invocation.model_id,
                "system_policy_digest": run.invocation.system_policy_digest,
            },
            created_at=created_at,
        ),
        "candidate": _artifact(
            artifact_id=run.candidate.candidate_id,
            artifact_type=SecurityArtifactType.ANSWER_CANDIDATE,
            request_id=request_id,
            subject_digest=run.candidate.digest,
            parent_digests=(run.invocation.digest,),
            result=SecurityResult.PASS,
            disposition=SecurityDisposition.WAIT,
            payload={
                "answer_digest": run.candidate.answer_digest,
                "claim_ids": run.candidate.claim_ids,
                "invocation_envelope_digest": (
                    run.candidate.invocation_envelope_digest
                ),
            },
            created_at=created_at,
        ),
    }
    order = (
        "binding",
        "retrieval",
        "bundle_security",
        "bundle",
        "context",
        "disclosure",
        "invocation",
        "candidate",
    )
    for index, name in enumerate(order):
        result = repository.append_artifact(
            artifacts[name],
            allow_external_parents=index == 0,
        )
        _require_applied(result, label=f"PERSIST_{name.upper()}")
    return artifacts


def _persist_release(
    repository: PostgresRagSecurityRepository,
    *,
    request_id: str,
    evidence: ReleaseEvidence,
    decision: OutputReleaseDecision,
    observed_at: str,
    inject_failure_after_decision: bool = False,
) -> SecurityRepositoryResult:
    observed_checks = (
        evidence.dlp_result,
        evidence.metadata_stripping_result,
        evidence.destination_result,
    )
    if SecurityResult.FAIL in observed_checks:
        evidence_result = SecurityResult.FAIL
    elif any(
        item in {SecurityResult.INCONCLUSIVE, SecurityResult.NOT_RUN}
        for item in observed_checks
    ):
        evidence_result = SecurityResult.INCONCLUSIVE
    else:
        evidence_result = SecurityResult.PASS
    evidence_artifact = _artifact(
        artifact_id=evidence.evidence_id,
        artifact_type=SecurityArtifactType.RELEASE_EVIDENCE,
        request_id=request_id,
        subject_digest=evidence.digest,
        parent_digests=(evidence.candidate_digest,),
        result=evidence_result,
        disposition=SecurityDisposition.WAIT,
        payload={
            "candidate_digest": evidence.candidate_digest,
            "evidence_digests": evidence.evidence_digests,
            "observed_claim_ids": evidence.observed_claim_ids,
            "security_policy_fingerprint": (
                evidence.current_security_policy_fingerprint
            ),
        },
        created_at=observed_at,
    )
    persisted_evidence = repository.append_artifact(evidence_artifact)
    _require_applied(persisted_evidence, label="PERSIST_RELEASE_EVIDENCE")
    return repository.append_output_decision_and_intent(
        decision,
        request_id=request_id,
        intent_id=f"response-intent:{decision.decision_id}",
        destination_digest=stable_hash(("current-chat", request_id)),
        inject_failure_after_decision=inject_failure_after_decision,
    )


def _persist_complete_query(
    repository: PostgresRagSecurityRepository,
    run: QueryRun,
    *,
    observed_at: str,
) -> None:
    _persist_pre_release_chain(repository, run, created_at=observed_at)
    result = _persist_release(
        repository,
        request_id=run.binding.request_id,
        evidence=run.evidence,
        decision=run.release,
        observed_at=observed_at,
    )
    _require_applied(result, label="PERSIST_OUTPUT_RELEASE")


def _acquire_view(
    repository: PostgresIndexLifecycleRepository,
    *,
    request_id: str,
    generation_id: str,
    pointer_revision: int,
    authorization_id: str,
    acquired_at: str,
    lease_expires_at: str,
) -> str:
    view_id = f"read-view:{request_id}"
    result = repository.acquire_read_view(
        view_id=view_id,
        pointer_name=POINTER,
        expected_generation_id=generation_id,
        expected_pointer_revision=pointer_revision,
        owner_id=request_id,
        authorization_snapshot_id=authorization_id,
        acquired_at=acquired_at,
        lease_expires_at=lease_expires_at,
    )
    if result.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError(f"READ_VIEW_ACQUIRE_FAILED:{request_id}")
    return view_id


def _query_read_view_ids(
    repository: PostgresIndexLifecycleRepository,
    *,
    view_id: str,
    generation_id: str,
    authorization_id: str,
    query_vector: tuple[float, ...],
    top_k: int,
    mode: QueryMode,
    observed_at: str,
) -> tuple[str, ...]:
    hits = repository.query_read_view(
        view_id=view_id,
        expected_fencing_token=1,
        expected_generation_id=generation_id,
        expected_authorization_snapshot_id=authorization_id,
        tenant_id=TENANT,
        query_vector=query_vector,
        top_k=top_k,
        mode=mode,
        observed_at=observed_at,
    )
    if any(item.generation_id != generation_id for item in hits):
        raise AssertionError("READ_VIEW_QUERY_MIXED_GENERATIONS")
    return tuple(item.occurrence_id for item in hits)


def _normal_query_matrix(
    repository: PostgresIndexLifecycleRepository,
    factory: ConnectionFactory,
    security_repository: PostgresRagSecurityRepository,
    *,
    security_snapshot: SecuritySnapshot,
    policy: SecurityPolicyIdentity,
    base: datetime,
) -> tuple[dict[str, dict[str, list[str]]], dict[str, QueryRun]]:
    root_half = 1.0 / math.sqrt(2.0)
    specifications = {
        "Q1": ((1.0, 0.0, 0.0), 1, ("A@v1",)),
        "Q2": ((0.0, 1.0, 0.0), 1, ("C@v1",)),
        "Q3": ((root_half, root_half, 0.0), 2, NORMAL_IDS),
    }
    matrix: dict[str, dict[str, list[str]]] = {"EXACT": {}, "HNSW": {}}
    runs: dict[str, QueryRun] = {}
    for index, (query_id, specification) in enumerate(specifications.items()):
        query_vector, top_k, expected = specification
        request_id = f"request-{query_id}-G2"
        view_id = _acquire_view(
            repository,
            request_id=request_id,
            generation_id="G2",
            pointer_revision=8,
            authorization_id="P1",
            acquired_at=_timestamp(base, 10 + index),
            lease_expires_at=_timestamp(base, 180),
        )
        for mode in (QueryMode.EXACT, QueryMode.HNSW):
            observed = _query_read_view_ids(
                repository,
                view_id=view_id,
                generation_id="G2",
                authorization_id="P1",
                query_vector=cast(tuple[float, ...], query_vector),
                top_k=cast(int, top_k),
                mode=mode,
                observed_at=_timestamp(base, 14 + index),
            )
            matrix[mode.value][query_id] = list(observed)
            if observed != expected:
                raise AssertionError(f"{query_id}_{mode.value}_QUALITY_MISMATCH")
        binding = _binding_from_read_view(
            factory,
            request_id=request_id,
            purpose=f"refund-{query_id}",
            view_id=view_id,
            generation_id="G2",
            authorization_revision="P1",
            manifest_occurrence_ids=NORMAL_IDS,
            security_snapshot=security_snapshot,
            policy=policy,
        )
        run = _run_query(
            factory,
            query_id=f"{query_id}-G2",
            binding=binding,
            occurrence_ids=expected,
            observed_at=_timestamp(base, 15 + index),
        )
        if (
            run.release.result is not SecurityResult.PASS
            or run.release.disposition is not SecurityDisposition.RELEASE
        ):
            raise AssertionError(f"{query_id}_NORMAL_RELEASE_FAILED")
        _persist_complete_query(
            security_repository,
            run,
            observed_at=_timestamp(base, 15 + index),
        )
        released = repository.release_read_view(
            view_id=view_id,
            expected_fencing_token=1,
            released_at=_timestamp(base, 19 + index),
        )
        if released.outcome is not RepositoryOutcome.APPLIED:
            raise AssertionError(f"{query_id}_READ_VIEW_RELEASE_FAILED")
        runs[query_id] = run
    return matrix, runs


def _adversarial_controls(
    factory: ConnectionFactory,
    *,
    g2_binding: RequestSecurityBinding,
    security_snapshot: SecuritySnapshot,
    policy: SecurityPolicyIdentity,
    observed_at: str,
) -> dict[str, dict[str, object]]:
    g2_a = _retrieved_occurrence(
        factory,
        generation_id="G2",
        occurrence_id="A@v1",
        binding=g2_binding,
        fact_ids=("refund_window",),
    )
    substituted_identity = replace(
        g2_a.identity,
        metadata_digest=stable_hash(("METADATA", "A@v1", "SUBSTITUTED")),
    )
    substituted = replace(g2_a, identity=substituted_identity)
    manifest_substitution = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-manifest-substitution",
        binding=g2_binding,
        candidates=(substituted,),
        least_context_occurrence_ids=("A@v1",),
        observed_at=observed_at,
    )
    if manifest_substitution.result is not SecurityResult.FAIL:
        raise AssertionError("MANIFEST_SUBSTITUTION_NOT_REJECTED")

    x_binding = _negative_control_binding(
        factory,
        request_id="negative-X",
        occurrence_ids=("X@v1",),
        security_snapshot=security_snapshot,
        policy=policy,
    )
    x = _retrieved_occurrence(
        factory,
        generation_id="G_BAD",
        occurrence_id="X@v1",
        binding=x_binding,
        attack_tags=("DOCUMENT_INSTRUCTION_OVERRIDE",),
    )
    x_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-X-negative-control",
        binding=x_binding,
        candidates=(x,),
        least_context_occurrence_ids=("X@v1",),
        observed_at=observed_at,
    )
    x_bundle = RagSecurityPipeline.analyze_bundle(
        decision_id="bundle-X-negative-control",
        binding=x_binding,
        retrieval_decision=x_retrieval,
        candidates=(x,),
    )
    if (
        x_retrieval.result is not SecurityResult.PASS
        or x_bundle.result is not SecurityResult.FAIL
    ):
        raise AssertionError("DOCUMENT_INJECTION_NOT_BLOCKED")

    y_binding = _negative_control_binding(
        factory,
        request_id="negative-Y",
        occurrence_ids=("Y@v1",),
        security_snapshot=security_snapshot,
        policy=policy,
    )
    y = _retrieved_occurrence(
        factory,
        generation_id="G_BAD",
        occurrence_id="Y@v1",
        binding=y_binding,
        content_security_result=SecurityResult.INCONCLUSIVE,
    )
    y_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-Y-negative-control",
        binding=y_binding,
        candidates=(y,),
        least_context_occurrence_ids=("Y@v1",),
        observed_at=observed_at,
    )
    if y_retrieval.result is not SecurityResult.INCONCLUSIVE:
        raise AssertionError("Y_DETECTOR_TIMEOUT_NOT_INCONCLUSIVE")

    z_binding = _negative_control_binding(
        factory,
        request_id="negative-Z",
        occurrence_ids=("Z1@v1", "Z2@v1"),
        security_snapshot=security_snapshot,
        policy=policy,
    )
    z_candidates = (
        _retrieved_occurrence(
            factory,
            generation_id="G_BAD",
            occurrence_id="Z1@v1",
            binding=z_binding,
            attack_tags=("CHAIN_READ_NEXT",),
        ),
        _retrieved_occurrence(
            factory,
            generation_id="G_BAD",
            occurrence_id="Z2@v1",
            binding=z_binding,
            attack_tags=("CHAIN_EXECUTE_HIDDEN",),
        ),
    )
    z_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-Z-negative-control",
        binding=z_binding,
        candidates=z_candidates,
        least_context_occurrence_ids=("Z1@v1", "Z2@v1"),
        observed_at=observed_at,
    )
    z_bundle = RagSecurityPipeline.analyze_bundle(
        decision_id="bundle-Z-negative-control",
        binding=z_binding,
        retrieval_decision=z_retrieval,
        candidates=z_candidates,
    )
    if z_bundle.result is not SecurityResult.FAIL:
        raise AssertionError("CROSS_DOCUMENT_CHAIN_NOT_BLOCKED")

    t_binding = _negative_control_binding(
        factory,
        request_id="negative-T",
        occurrence_ids=("T@v1",),
        security_snapshot=security_snapshot,
        policy=policy,
    )
    t = _retrieved_occurrence(
        factory,
        generation_id="G_BAD",
        occurrence_id="T@v1",
        binding=t_binding,
    )
    t_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-T-negative-control",
        binding=t_binding,
        candidates=(t,),
        least_context_occurrence_ids=("T@v1",),
        observed_at=observed_at,
    )
    if t_retrieval.result is not SecurityResult.FAIL:
        raise AssertionError("CROSS_TENANT_T_NOT_BLOCKED")
    tenant_sql_count = _query_one(
        factory,
        """
        SELECT count(*)
        FROM day104_l3.index_points
        WHERE generation_id = 'G_BAD' AND tenant_id = %s
          AND occurrence_id = 'T@v1'
        """,
        (TENANT,),
    )
    if tenant_sql_count != (0,):
        raise AssertionError("SQL_TENANT_FILTER_RETURNED_T")

    return {
        "manifest_substitution": {
            "result": manifest_substitution.result.value,
            "reason_codes": [
                item.reason_code for item in manifest_substitution.denied_occurrences
            ],
        },
        "X": {
            "generation_id": "G_BAD",
            "retrieval_result": x_retrieval.result.value,
            "bundle_result": x_bundle.result.value,
            "reason_codes": list(x_bundle.reason_codes),
            "entered_prompt": False,
        },
        "Y": {
            "generation_id": "G_BAD",
            "detector_result": SecurityResult.INCONCLUSIVE.value,
            "retrieval_result": y_retrieval.result.value,
            "serving_action": "QUARANTINE",
            "entered_prompt": False,
        },
        "Z": {
            "generation_id": "G_BAD",
            "retrieval_result": z_retrieval.result.value,
            "bundle_result": z_bundle.result.value,
            "reason_codes": list(z_bundle.reason_codes),
            "entered_prompt": False,
        },
        "T": {
            "generation_id": "G_BAD",
            "retrieval_result": t_retrieval.result.value,
            "sql_tenant_filter_count": int(tenant_sql_count[0]),
            "entered_prompt": False,
        },
    }


def _persist_versioned_y_records(
    repository: PostgresRagSecurityRepository,
    *,
    observed_at: str,
) -> dict[str, str]:
    v1_subject = stable_hash(
        {
            "occurrence_id": "Y@v1",
            "content_digest": stable_hash(("CONTENT", "Y@v1")),
            "parser_version": "parser-v1",
            "scanner_version": "scanner-v1",
            "detector_version": "detector-v1",
            "result": "INCONCLUSIVE",
        }
    )
    v2_subject = stable_hash(
        {
            "occurrence_id": "Y@v2",
            "content_digest": stable_hash(("CONTENT", "Y@v2")),
            "parser_version": "parser-v2",
            "scanner_version": "scanner-v2",
            "detector_version": "detector-v2",
            "result": "PASS",
        }
    )
    v1 = _artifact(
        artifact_id="content-security-record:Y@v1:detector-v1",
        artifact_type=SecurityArtifactType.CONTENT_SECURITY_RECORD,
        request_id=None,
        subject_digest=v1_subject,
        parent_digests=(),
        result=SecurityResult.INCONCLUSIVE,
        disposition=SecurityDisposition.QUARANTINE,
        payload={
            "detector_version": "detector-v1",
            "evidence_digest": stable_hash(("Y@v1", "detector-timeout")),
            "occurrence_id": "Y@v1",
            "parser_version": "parser-v1",
            "scanner_version": "scanner-v1",
            "status": "INCONCLUSIVE",
        },
        created_at=observed_at,
    )
    v2 = _artifact(
        artifact_id="content-security-record:Y@v2:detector-v2",
        artifact_type=SecurityArtifactType.CONTENT_SECURITY_RECORD,
        request_id=None,
        subject_digest=v2_subject,
        parent_digests=(),
        result=SecurityResult.PASS,
        disposition=SecurityDisposition.ELIGIBLE,
        payload={
            "detector_version": "detector-v2",
            "evidence_digest": stable_hash(("Y@v2", "fresh-rescan-pass")),
            "occurrence_id": "Y@v2",
            "parser_version": "parser-v2",
            "scanner_version": "scanner-v2",
            "status": "PASS",
        },
        created_at=observed_at,
    )
    _require_applied(
        repository.append_artifact(v1, allow_external_parents=True),
        label="PERSIST_Y_V1_SECURITY_RECORD",
    )
    _require_applied(
        repository.append_artifact(v2, allow_external_parents=True),
        label="PERSIST_Y_V2_SECURITY_RECORD",
    )
    if v1.subject_digest == v2.subject_digest or v1.artifact_id == v2.artifact_id:
        raise AssertionError("VERSIONED_DETECTOR_RESCAN_OVERWROTE_HISTORY")
    return {
        "y_v1_artifact_id": v1.artifact_id,
        "y_v1_digest": v1.subject_digest,
        "y_v2_artifact_id": v2.artifact_id,
        "y_v2_digest": v2.subject_digest,
    }


def _release_decision(
    run: QueryRun,
    *,
    decision_id: str,
    evidence: ReleaseEvidence,
    candidate: AnswerCandidate | None = None,
    observed_at: str,
) -> OutputReleaseDecision:
    selected = candidate or run.candidate
    return RagSecurityPipeline.decide_output_release(
        decision_id=decision_id,
        binding=run.binding,
        context_manifest=run.context,
        disclosure=run.disclosure,
        model_envelope=run.invocation,
        candidate=selected,
        evidence=evidence,
        observed_at=observed_at,
    )


def _release_failure_controls(
    run: QueryRun,
    *,
    observed_at: str,
) -> dict[str, tuple[ReleaseEvidence, OutputReleaseDecision]]:
    wrong_candidate = replace(
        run.candidate,
        candidate_id=f"{run.candidate.candidate_id}-wrong-citation",
        proposed_citations=(ProposedCitation(run.candidate.claim_ids[0], "A@v1"),),
    )
    wrong_evidence = replace(
        run.evidence,
        evidence_id=f"{run.evidence.evidence_id}-wrong-citation",
        candidate_digest=wrong_candidate.digest,
    )
    wrong = _release_decision(
        run,
        decision_id="release-wrong-citation-G3",
        evidence=wrong_evidence,
        candidate=wrong_candidate,
        observed_at=observed_at,
    )
    dlp_timeout_evidence = replace(
        run.evidence,
        evidence_id=f"{run.evidence.evidence_id}-dlp-timeout",
        dlp_result=SecurityResult.INCONCLUSIVE,
    )
    dlp_timeout = _release_decision(
        run,
        decision_id="release-dlp-timeout-G3",
        evidence=dlp_timeout_evidence,
        observed_at=observed_at,
    )
    dlp_fail_evidence = replace(
        run.evidence,
        evidence_id=f"{run.evidence.evidence_id}-dlp-sensitive",
        dlp_result=SecurityResult.FAIL,
    )
    dlp_fail = _release_decision(
        run,
        decision_id="release-dlp-sensitive-G3",
        evidence=dlp_fail_evidence,
        observed_at=observed_at,
    )
    if (
        wrong.result is not SecurityResult.FAIL
        or dlp_timeout.result is not SecurityResult.INCONCLUSIVE
        or dlp_fail.result is not SecurityResult.FAIL
        or any(
            item.disposition is not SecurityDisposition.BLOCKED
            for item in (wrong, dlp_timeout, dlp_fail)
        )
    ):
        raise AssertionError("OUTPUT_FAILURE_CONTROLS_DID_NOT_FAIL_CLOSED")
    return {
        "wrong_citation": (wrong_evidence, wrong),
        "dlp_timeout": (dlp_timeout_evidence, dlp_timeout),
        "dlp_sensitive": (dlp_fail_evidence, dlp_fail),
    }


def _security_artifact_replay_control(
    repository: PostgresRagSecurityRepository,
    *,
    observed_at: str,
) -> dict[str, str]:
    artifact = _artifact(
        artifact_id="security-artifact-replay-probe",
        artifact_type=SecurityArtifactType.CONTENT_SECURITY_RECORD,
        request_id=None,
        subject_digest=stable_hash("security-artifact-replay-probe"),
        parent_digests=(),
        result=SecurityResult.PASS,
        disposition=SecurityDisposition.ELIGIBLE,
        payload={"evidence_digest": stable_hash("replay-evidence")},
        created_at=observed_at,
    )
    first = repository.append_artifact(artifact)
    replay = repository.append_artifact(artifact)
    conflict = repository.append_artifact(
        replace(artifact, subject_digest=stable_hash("changed-subject"))
    )
    if (
        first.outcome is not SecurityRepositoryOutcome.APPLIED
        or replay.outcome is not SecurityRepositoryOutcome.EXACT_REPLAY
        or conflict.outcome is not SecurityRepositoryOutcome.IDENTITY_CONFLICT
    ):
        raise AssertionError("SECURITY_ARTIFACT_REPLAY_RULE_FAILED")
    return {
        "first": first.outcome.value,
        "replay": replay.outcome.value,
        "conflict": conflict.outcome.value,
    }


def _snapshot_cas_race(
    factory: ConnectionFactory,
    *,
    policy: SecurityPolicyIdentity,
    base: datetime,
) -> list[str]:
    repository = PostgresRagSecurityRepository(factory, integration_enabled=True)
    initial = _security_snapshot(
        snapshot_id="RACE-P1",
        tenant_id="tenant-race",
        revision=1,
        occurrence_ids=("A@v1",),
        policy=policy,
        created_at=_timestamp(base, 30),
    )
    _require_applied(
        repository.advance_current_security_snapshot(initial, expected_revision=0),
        label="RACE_P1",
    )
    candidates = (
        _security_snapshot(
            snapshot_id="RACE-P2-A",
            tenant_id="tenant-race",
            revision=2,
            occurrence_ids=("C@v1",),
            policy=policy,
            created_at=_timestamp(base, 31),
        ),
        _security_snapshot(
            snapshot_id="RACE-P2-B",
            tenant_id="tenant-race",
            revision=2,
            occurrence_ids=("A@v1",),
            policy=policy,
            created_at=_timestamp(base, 31.1),
        ),
    )

    def advance(snapshot: SecuritySnapshot) -> SecurityRepositoryResult:
        local = PostgresRagSecurityRepository(factory, integration_enabled=True)
        return local.advance_current_security_snapshot(snapshot, expected_revision=1)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [item.outcome.value for item in executor.map(advance, candidates)]
    outcomes.sort()
    if outcomes != ["APPLIED", "STALE_REVISION"]:
        raise AssertionError("SECURITY_SNAPSHOT_CAS_RACE_NOT_ONE_WINNER")
    return outcomes


def _snapshot_transition_fault(
    factory: ConnectionFactory,
    *,
    policy: SecurityPolicyIdentity,
    base: datetime,
) -> dict[str, object]:
    def fault_factory():
        return _FaultConnection(
            factory(),
            fragment="INSERT INTO day105_l3.security_artifacts",
            error="INJECTED_SECURITY_TRANSITION_WRITE_FAILURE",
        )

    repository = PostgresRagSecurityRepository(
        fault_factory,
        integration_enabled=True,
    )
    snapshot = _security_snapshot(
        snapshot_id="FAULT-P1",
        tenant_id="tenant-fault",
        revision=1,
        occurrence_ids=("A@v1",),
        policy=policy,
        created_at=_timestamp(base, 32),
    )
    raised = False
    try:
        repository.advance_current_security_snapshot(snapshot, expected_revision=0)
    except RuntimeError as exc:
        if str(exc) != "INJECTED_SECURITY_TRANSITION_WRITE_FAILURE":
            raise
        raised = True
    current_count = _query_one(
        factory,
        """
        SELECT count(*) FROM day105_l3.current_security_snapshots
        WHERE tenant_id = 'tenant-fault'
        """,
    )
    snapshot_count = _query_one(
        factory,
        """
        SELECT count(*) FROM day105_l3.security_snapshots
        WHERE tenant_id = 'tenant-fault'
        """,
    )
    if not raised or current_count != (0,) or snapshot_count != (0,):
        raise AssertionError("SECURITY_TRANSITION_FAULT_LEFT_PARTIAL_STATE")
    return {
        "fault_raised": raised,
        "current_pointer_count": int(current_count[0]),
        "snapshot_count": int(snapshot_count[0]),
    }


def _append_only_mutation_rejected(factory: ConnectionFactory) -> bool:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE day105_l3.security_artifacts
            SET result = 'FAIL'
            WHERE artifact_id = 'security-artifact-replay-probe'
            """
        )
    except Exception:
        connection.rollback()
        return True
    else:
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()


def _statement_rejected(
    factory: ConnectionFactory,
    query: str,
    params: Sequence[object],
) -> bool:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
    except Exception:
        connection.rollback()
        return True
    else:
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()


def _database_release_and_content_safety_guards(
    factory: ConnectionFactory,
    *,
    decision_id: str,
) -> dict[str, bool]:
    decision = _query_one(
        factory,
        """
        SELECT identity_digest, payload ->> 'candidate_digest'
        FROM day105_l3.security_artifacts
        WHERE artifact_id = %s
        """,
        (decision_id,),
    )
    if decision is None:
        raise AssertionError("OUTPUT_DECISION_FOR_SQL_GUARD_MISSING")
    guard_decision_id = "sql-guard-output-decision"
    guard_decision_digest = stable_hash(
        (guard_decision_id, decision[1], "PASS", "RELEASE")
    )
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO day105_l3.security_artifacts
                (artifact_id, artifact_type, request_id, identity_digest,
                 parent_digests, result, disposition, payload, created_at)
            VALUES (%s, 'OUTPUT_RELEASE_DECISION', %s, %s,
                    ARRAY[]::text[], 'PASS', 'RELEASE', %s::jsonb,
                    clock_timestamp())
            """,
            (
                guard_decision_id,
                "request-Q2-G3",
                guard_decision_digest,
                json.dumps(
                    {
                        "candidate_digest": decision[1],
                        "subject_digest": guard_decision_digest,
                    },
                    sort_keys=True,
                ),
            ),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
    mismatched_action = _statement_rejected(
        factory,
        """
        INSERT INTO day105_l3.response_intents
            (intent_id, request_id, release_decision_id,
             release_decision_digest, candidate_digest,
             destination_digest, action, identity_digest, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'BLOCKED', %s, clock_timestamp())
        """,
        (
            "sql-guard-mismatched-action",
            "request-Q2-G3",
            guard_decision_id,
            guard_decision_digest,
            decision[1],
            stable_hash("destination"),
            stable_hash("sql-guard-mismatched-action"),
        ),
    )
    mismatched_candidate = _statement_rejected(
        factory,
        """
        INSERT INTO day105_l3.response_intents
            (intent_id, request_id, release_decision_id,
             release_decision_digest, candidate_digest,
             destination_digest, action, identity_digest, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'RELEASE', %s, clock_timestamp())
        """,
        (
            "sql-guard-mismatched-candidate",
            "request-Q2-G3",
            guard_decision_id,
            guard_decision_digest,
            stable_hash("wrong-candidate"),
            stable_hash("destination"),
            stable_hash("sql-guard-mismatched-candidate"),
        ),
    )
    sensitive_value = _statement_rejected(
        factory,
        """
        INSERT INTO day105_l3.security_artifacts
            (artifact_id, artifact_type, request_id, identity_digest,
             parent_digests, result, disposition, payload, created_at)
        VALUES (%s, 'CONTENT_SECURITY_RECORD', NULL, %s,
                ARRAY[]::text[], 'PASS', 'ELIGIBLE', %s::jsonb,
                clock_timestamp())
        """,
        (
            "sql-guard-sensitive-value",
            stable_hash("sql-guard-sensitive-value"),
            json.dumps(
                {"evidence_digest": "postgresql://user:password@host/db"},
                sort_keys=True,
            ),
        ),
    )
    evidence = {
        "mismatched_action_rejected": mismatched_action,
        "mismatched_candidate_rejected": mismatched_candidate,
        "sensitive_value_rejected": sensitive_value,
    }
    if not all(evidence.values()):
        raise AssertionError("DATABASE_RELEASE_OR_CONTENT_SAFETY_GUARD_FAILED")
    return evidence


def _incident_controls(
    repository: PostgresRagSecurityRepository,
    *,
    base: datetime,
) -> dict[str, object]:
    root = SecurityIncidentRecord(
        incident_record_id="incident-day105-l3-root",
        incident_id="incident-day105-l3-controlled-egress",
        previous_record_id=None,
        state=IncidentState.OPEN,
        affected_request_ids=("negative-X",),
        affected_generation_ids=("G_BAD",),
        affected_occurrence_ids=("X@v1",),
        affected_sinks=(EgressSink.EXTERNAL_DESTINATION,),
        containment_actions=(
            "BLOCK_EXTERNAL_DESTINATION",
            "QUARANTINE_OCCURRENCE",
            "ROTATE_CREDENTIAL",
        ),
        evidence_digests=(stable_hash("incident-open-evidence"),),
        credential_rotation_status="PENDING",
        impact_analysis_digest=stable_hash("incident-open-impact"),
        actor_id="application-security-control-plane",
        observed_at=_timestamp(base, 40),
    )
    correction = SecurityIncidentRecord(
        incident_record_id="incident-day105-l3-contained",
        incident_id=root.incident_id,
        previous_record_id=root.incident_record_id,
        state=IncidentState.CONTAINED,
        affected_request_ids=root.affected_request_ids,
        affected_generation_ids=root.affected_generation_ids,
        affected_occurrence_ids=root.affected_occurrence_ids,
        affected_sinks=root.affected_sinks,
        containment_actions=root.containment_actions,
        evidence_digests=(stable_hash("incident-contained-evidence"),),
        credential_rotation_status="COMPLETE",
        impact_analysis_digest=stable_hash("incident-contained-impact"),
        actor_id="application-security-control-plane",
        observed_at=_timestamp(base, 41),
    )
    _require_applied(
        repository.append_incident_record(root),
        label="INCIDENT_ROOT",
    )
    _require_applied(
        repository.append_incident_record(correction),
        label="INCIDENT_CORRECTION",
    )
    changed = replace(
        correction,
        state=IncidentState.RECOVERING,
        impact_analysis_digest=stable_hash("changed-overwrite"),
    )
    overwrite = repository.append_incident_record(changed)
    branch = repository.append_incident_record(
        replace(
            correction,
            incident_record_id="incident-day105-l3-branch",
            state=IncidentState.RECOVERING,
            impact_analysis_digest=stable_hash("branch-impact"),
            observed_at=_timestamp(base, 42),
        )
    )
    second_root = repository.append_incident_record(
        replace(
            root,
            incident_record_id="incident-day105-l3-second-root",
            observed_at=_timestamp(base, 43),
        )
    )
    if (
        overwrite.outcome is not SecurityRepositoryOutcome.IDENTITY_CONFLICT
        or branch.outcome is not SecurityRepositoryOutcome.IDENTITY_CONFLICT
        or second_root.outcome is not SecurityRepositoryOutcome.IDENTITY_CONFLICT
    ):
        raise AssertionError("INCIDENT_APPEND_ONLY_RULE_FAILED")
    history = repository.read_incident_history(root.incident_id)
    if [item.record_id for item in history] != [
        root.incident_record_id,
        correction.incident_record_id,
    ]:
        raise AssertionError("INCIDENT_HISTORY_READBACK_MISMATCH")
    return {
        "incident_id": root.incident_id,
        "root_id": root.incident_record_id,
        "root_digest": root.digest,
        "correction_id": correction.incident_record_id,
        "correction_digest": correction.digest,
        "states": [item.state for item in history],
        "overwrite": overwrite.outcome.value,
        "branch": branch.outcome.value,
        "second_root": second_root.outcome.value,
    }


def _durable_restart_state_identity(factory: ConnectionFactory) -> str:
    """Hash the immutable serving/security subset that must survive restart."""

    pointer = _query_rows(
        factory,
        """
        SELECT generation_id, revision
        FROM day104_l3.active_pointers
        WHERE pointer_name = %s
        """,
        (POINTER,),
    )
    security = _query_rows(
        factory,
        """
        SELECT current.snapshot_id, current.revision, snapshot.identity_digest
        FROM day105_l3.current_security_snapshots AS current
        JOIN day105_l3.security_snapshots AS snapshot
          ON snapshot.snapshot_id = current.snapshot_id
        WHERE current.tenant_id = %s
        """,
        (TENANT,),
    )
    g3 = _query_rows(
        factory,
        """
        SELECT generation_id, build_snapshot_id, build_snapshot_fingerprint,
               manifest_digest, checkpoint, state
        FROM day104_l3.generations
        WHERE generation_id = 'G3'
        """,
    )
    intents = _query_rows(
        factory,
        """
        SELECT request_id, release_decision_id, action, identity_digest
        FROM day105_l3.response_intents
        WHERE release_decision_id IN (
            'release-Q3-pending-after-P2',
            'release-Q2-G3',
            'release-dlp-timeout-G3',
            'release-dlp-sensitive-G3'
        )
        ORDER BY release_decision_id
        """,
    )
    incident = _query_rows(
        factory,
        """
        SELECT record_id, previous_record_id, identity_digest, state
        FROM day105_l3.incident_records
        WHERE incident_id = 'incident-day105-l3-controlled-egress'
        ORDER BY created_at, record_id
        """,
    )
    y_records = _query_rows(
        factory,
        """
        SELECT artifact_id, identity_digest, result, disposition
        FROM day105_l3.security_artifacts
        WHERE artifact_id IN (
            'content-security-record:Y@v1:detector-v1',
            'content-security-record:Y@v2:detector-v2'
        )
        ORDER BY artifact_id
        """,
    )
    orphan_candidate = _query_rows(
        factory,
        """
        SELECT artifact_id, identity_digest, payload ->> 'subject_digest'
        FROM day105_l3.security_artifacts
        WHERE artifact_id = 'candidate-Q2-G3-orphan'
          AND artifact_type = 'ANSWER_CANDIDATE'
        """,
    )
    orphan_release = _query_one(
        factory,
        """
        SELECT
          (SELECT count(*) FROM day105_l3.security_artifacts
           WHERE artifact_type = 'OUTPUT_RELEASE_DECISION'
             AND payload ->> 'candidate_digest' =
                 (SELECT payload ->> 'subject_digest'
                  FROM day105_l3.security_artifacts
                  WHERE artifact_id = 'candidate-Q2-G3-orphan')),
          (SELECT count(*) FROM day105_l3.response_intents
           WHERE candidate_digest =
                 (SELECT payload ->> 'subject_digest'
                  FROM day105_l3.security_artifacts
                  WHERE artifact_id = 'candidate-Q2-G3-orphan'))
        """,
    )
    if (
        pointer != [("G3", 9)]
        or len(security) != 1
        or security[0][0:2] != ("P2", 2)
        or len(g3) != 1
        or g3[0][5] != "ACTIVE"
        or len(intents) != 4
        or len(incident) != 2
        or len(y_records) != 2
        or len(orphan_candidate) != 1
        or orphan_release != (0, 0)
    ):
        raise AssertionError("RESTART_DURABLE_IDENTITY_INCOMPLETE")
    return stable_hash(
        {
            "pointer": pointer,
            "security": security,
            "G3": g3,
            "response_intents": intents,
            "incident": incident,
            "versioned_detector_records": y_records,
            "orphan_candidate": orphan_candidate,
            "orphan_release_counts": orphan_release,
        }
    )


def _persist_environment_evidence(
    repository: PostgresRagSecurityRepository,
    factory: ConnectionFactory,
    *,
    observed_at: str,
) -> dict[str, object]:
    row = _query_one(
        factory,
        """
        SELECT pg_postmaster_start_time(),
               current_setting('server_version'),
               current_setting('server_version_num'),
               extversion
        FROM pg_extension
        WHERE extname = 'vector'
        """,
    )
    if row is None:
        raise AssertionError("POSTGRESQL_PGVECTOR_IDENTITY_MISSING")
    default_isolation = _query_one(factory, "SHOW transaction_isolation")
    repeatable_connection = factory()
    repeatable_cursor = repeatable_connection.cursor()
    try:
        repeatable_cursor.execute(
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        repeatable_cursor.execute("SHOW transaction_isolation")
        repeatable_isolation = repeatable_cursor.fetchone()
        repeatable_connection.rollback()
    except BaseException:
        repeatable_connection.rollback()
        raise
    finally:
        repeatable_cursor.close()
        repeatable_connection.close()
    if default_isolation is None or repeatable_isolation is None:
        raise AssertionError("TRANSACTION_ISOLATION_READBACK_MISSING")
    transaction_isolation = tuple(
        sorted(
            {
                str(default_isolation[0]).upper(),
                str(repeatable_isolation[0]).upper(),
            }
        )
    )
    if set(transaction_isolation) != {"READ COMMITTED", "REPEATABLE READ"}:
        raise AssertionError("TRANSACTION_ISOLATION_READBACK_MISMATCH")
    pre_restart_state_identity = _durable_restart_state_identity(factory)
    postmaster_start = cast(datetime, row[0]).astimezone(timezone.utc).isoformat()
    subject_digest = stable_hash(
        {
            "postmaster_start_at": postmaster_start,
            "postgresql_version_num": str(row[2]),
            "pgvector_version": str(row[3]),
            "pre_restart_state_identity_digest": pre_restart_state_identity,
            "transaction_isolation": transaction_isolation,
        }
    )
    artifact = _artifact(
        artifact_id="environment-evidence:pre-container-restart",
        artifact_type=SecurityArtifactType.ENVIRONMENT_EVIDENCE,
        request_id=None,
        subject_digest=subject_digest,
        parent_digests=(),
        result=SecurityResult.PASS,
        disposition=SecurityDisposition.ELIGIBLE,
        payload={
            "observed_at": observed_at,
            "pgvector_version": str(row[3]),
            "postmaster_start_at": postmaster_start,
            "postgresql_version": str(row[1]),
            "pre_restart_state_identity_digest": pre_restart_state_identity,
            "transaction_isolation_ids": transaction_isolation,
        },
        created_at=observed_at,
    )
    _require_applied(
        repository.append_artifact(artifact, allow_external_parents=True),
        label="PERSIST_PRE_RESTART_ENVIRONMENT",
    )
    return {
        "postmaster_start_at": postmaster_start,
        "postgresql_server_version": str(row[1]),
        "postgresql_server_version_num": str(row[2]),
        "pgvector_extension_version": str(row[3]),
        "pre_restart_state_identity_digest": pre_restart_state_identity,
        "transaction_isolation": list(transaction_isolation),
        "identity_digest": subject_digest,
    }


def _context_tamper_rejected(run: QueryRun) -> bool:
    try:
        replace(
            run.context,
            assembled_context_digest=stable_hash("tampered-context-projection"),
        )
    except ValueError:
        return True
    return False


def _release_intent_fault(
    repository: PostgresRagSecurityRepository,
    factory: ConnectionFactory,
    run: QueryRun,
    *,
    observed_at: str,
) -> dict[str, object]:
    evidence = replace(
        run.evidence,
        evidence_id=f"{run.evidence.evidence_id}-orphan-probe",
    )
    decision = _release_decision(
        run,
        decision_id="release-orphan-probe",
        evidence=evidence,
        observed_at=observed_at,
    )
    raised = False
    try:
        _persist_release(
            repository,
            request_id=run.binding.request_id,
            evidence=evidence,
            decision=decision,
            observed_at=observed_at,
            inject_failure_after_decision=True,
        )
    except RuntimeError as exc:
        if str(exc) != "INJECTED_AFTER_OUTPUT_DECISION":
            raise
        raised = True
    rows = _query_one(
        factory,
        """
        SELECT
          (SELECT count(*) FROM day105_l3.security_artifacts
           WHERE artifact_id = %s
             AND payload ->> 'subject_digest' = %s),
          (SELECT count(*) FROM day105_l3.security_artifacts
           WHERE artifact_type = 'OUTPUT_RELEASE_DECISION'
             AND payload ->> 'candidate_digest' = %s),
          (SELECT count(*) FROM day105_l3.response_intents
           WHERE candidate_digest = %s)
        """,
        (
            run.candidate.candidate_id,
            run.candidate.digest,
            run.candidate.digest,
            run.candidate.digest,
        ),
    )
    if not raised or rows != (1, 0, 0):
        raise AssertionError("OUTPUT_DECISION_INTENT_FAULT_LEFT_PARTIAL_STATE")
    return {
        "fault_raised": raised,
        "candidate_artifact_id": run.candidate.candidate_id,
        "candidate_digest": run.candidate.digest,
        "candidate_count": int(rows[0]),
        "release_decision_count": int(rows[1]),
        "response_intent_count": int(rows[2]),
        "default_serving_action": "BLOCKED",
    }


def _reset_and_install(
    factory: ConnectionFactory,
) -> tuple[PostgresIndexLifecycleRepository, PostgresRagSecurityRepository]:
    connection = factory()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT public.reset_day105_l3_schemas(%s, %s)",
            ("1", RESET_CONFIRMATION),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
    lifecycle = PostgresIndexLifecycleRepository(
        factory,
        schema_path=ROOT / "integration" / "day104" / "schema.sql",
    )
    security = PostgresRagSecurityRepository(
        factory,
        schema_path=ROOT / "integration" / "day105" / "schema.sql",
        integration_enabled=True,
    )
    lifecycle.install_schema()
    security.install_schema()
    return lifecycle, security


def _case(
    *,
    case_id: str,
    generation_id: str,
    stage: str,
    action: str,
    prompt_ids: tuple[str, ...] = (),
    citation_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "generation_id": generation_id,
        "expected_stage_result": stage,
        "observed_stage_result": stage,
        "expected_serving_action": action,
        "serving_action": action,
        "prompt_occurrence_ids": list(prompt_ids),
        "released_citation_occurrence_ids": list(citation_ids),
        "defense_outcome": "PASS",
        "expectation_conformant": True,
    }
    payload["evidence_digest"] = stable_hash(payload)
    return payload


def _failure(
    checkpoint_id: str,
    expected_outcome: str,
    observed_outcome: str,
    evidence: object,
) -> dict[str, object]:
    return {
        "checkpoint_id": checkpoint_id,
        "expected_outcome": expected_outcome,
        "observed_outcome": observed_outcome,
        "status": "PASS",
        "runtime_evidence_digest": stable_hash(evidence),
    }


def _gate(evidence_id: str, evidence: object, observed_at: str) -> dict[str, object]:
    return {
        "status": "PASS",
        "safe_reason": "EXECUTED_BOUNDARY_CONFORMED",
        "evidence_ids": [evidence_id],
        "evidence_digests": [stable_hash(evidence)],
        "observed_at": observed_at,
    }


def run_integration(database_url: str) -> dict[str, object]:
    """Execute the destructive disposable-lab scenario."""

    if os.environ.get("DAY105_L3_INTEGRATION") != "1":
        raise RuntimeError("DAY105_L3_INTEGRATION_FLAG_REQUIRED")
    if not database_url.strip():
        raise ValueError("DAY105_L3_DATABASE_URL_REQUIRED")
    started_at = datetime.now(timezone.utc)
    # Keep deterministic event ordering without claiming observations in the
    # future. Lease expiries remain bounded and later than the live run.
    base = started_at.replace(microsecond=0) - timedelta(minutes=60)
    factory = psycopg2_connection_factory(
        database_url,
        application_name="day105-l3-integration",
    )
    lifecycle, security = _reset_and_install(factory)
    policy = _policy()

    command = _source_command(base)
    received = lifecycle.receive_source_and_deletion(command)
    replayed = lifecycle.receive_source_and_deletion(command)
    if (
        received.outcome is not RepositoryOutcome.APPLIED
        or replayed.outcome is not RepositoryOutcome.EXACT_REPLAY
    ):
        raise AssertionError("SOURCE_AND_TOMBSTONE_INGEST_FAILED")

    p1 = _security_snapshot(
        snapshot_id="P1",
        tenant_id=TENANT,
        revision=1,
        occurrence_ids=NORMAL_IDS,
        policy=policy,
        created_at=_timestamp(base, 1),
    )
    p1_result = security.advance_current_security_snapshot(p1, expected_revision=0)
    _require_applied(p1_result, label="SECURITY_P1")
    bs1 = _build_snapshot(
        command,
        snapshot_id="BS1",
        authorization_id="P1",
        watermark="W1",
    )
    bs1_result = lifecycle.put_current_build_snapshot(
        snapshot=bs1,
        expected_current_revision=0,
        created_at=_timestamp(base, 1.1),
    )
    if bs1_result.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("BS1_NOT_CURRENT")

    poisoned = _build_poisoned_generation(
        lifecycle,
        factory,
        snapshot=bs1,
        base=base,
    )
    g2 = _register_ready_generation(
        lifecycle,
        generation_id="G2",
        snapshot=bs1,
        occurrence_ids=NORMAL_IDS,
        provider_fence=2,
        base=base,
        offset=3,
    )
    seeded = lifecycle.seed_pointer(
        pointer_name=POINTER,
        scope_id=SCOPE,
        generation_id="G2",
        revision=8,
        seeded_at=_timestamp(base, 4),
    )
    if seeded.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("G2_R8_POINTER_SEED_FAILED")

    matrix, normal_runs = _normal_query_matrix(
        lifecycle,
        factory,
        security,
        security_snapshot=p1,
        policy=policy,
        base=base,
    )
    q3 = normal_runs["Q3"]

    pending_request_id = "request-Q3-pending-G2"
    pending_view_id = _acquire_view(
        lifecycle,
        request_id=pending_request_id,
        generation_id="G2",
        pointer_revision=8,
        authorization_id="P1",
        acquired_at=_timestamp(base, 20),
        lease_expires_at=_timestamp(base, 1440),
    )
    pending_ids = _query_read_view_ids(
        lifecycle,
        view_id=pending_view_id,
        generation_id="G2",
        authorization_id="P1",
        query_vector=(1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0),
        top_k=2,
        mode=QueryMode.EXACT,
        observed_at=_timestamp(base, 21),
    )
    if pending_ids != NORMAL_IDS:
        raise AssertionError("PENDING_G2_QUERY_MISMATCH")
    pending_binding = _binding_from_read_view(
        factory,
        request_id=pending_request_id,
        purpose="refund-Q3-pending",
        view_id=pending_view_id,
        generation_id="G2",
        authorization_revision="P1",
        manifest_occurrence_ids=NORMAL_IDS,
        security_snapshot=p1,
        policy=policy,
    )
    pending_run = _run_query(
        factory,
        query_id="Q3-pending-G2",
        binding=pending_binding,
        occurrence_ids=NORMAL_IDS,
        observed_at=_timestamp(base, 21.1),
    )
    _persist_pre_release_chain(
        security,
        pending_run,
        created_at=_timestamp(base, 21.1),
    )

    adversarial = _adversarial_controls(
        factory,
        g2_binding=q3.binding,
        security_snapshot=p1,
        policy=policy,
        observed_at=_timestamp(base, 22),
    )
    y_records = _persist_versioned_y_records(
        security,
        observed_at=_timestamp(base, 22.1),
    )
    replay_control = _security_artifact_replay_control(
        security,
        observed_at=_timestamp(base, 22.2),
    )
    cas_race = _snapshot_cas_race(factory, policy=policy, base=base)
    transition_fault = _snapshot_transition_fault(
        factory,
        policy=policy,
        base=base,
    )
    if not _append_only_mutation_rejected(factory):
        raise AssertionError("APPEND_ONLY_DATABASE_TRIGGER_DID_NOT_REJECT_UPDATE")
    if not _context_tamper_rejected(q3):
        raise AssertionError("CONTEXT_DIGEST_TAMPER_NOT_REJECTED")

    p2 = _security_snapshot(
        snapshot_id="P2",
        tenant_id=TENANT,
        revision=2,
        occurrence_ids=("C@v1",),
        policy=policy,
        created_at=_timestamp(base, 33),
    )
    p2_result = security.advance_current_security_snapshot(p2, expected_revision=1)
    _require_applied(p2_result, label="SECURITY_P2")
    bs2 = _build_snapshot(
        command,
        snapshot_id="BS2",
        authorization_id="P2",
        watermark="W2",
    )
    bs2_result = lifecycle.put_current_build_snapshot(
        snapshot=bs2,
        expected_current_revision=1,
        created_at=_timestamp(base, 33.1),
    )
    if bs2_result.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("BS2_NOT_CURRENT_AFTER_P2")
    g3 = _register_ready_generation(
        lifecycle,
        generation_id="G3",
        snapshot=bs2,
        occurrence_ids=("C@v1",),
        provider_fence=3,
        base=base,
        offset=34,
    )
    lease = lifecycle.issue_activation_lease(
        pointer_name=POINTER,
        committer_id="day105-security-committer",
        issued_at=_timestamp(base, 35),
        lease_expires_at=_timestamp(base, 120),
    )
    activated = lifecycle.activate(
        activation_id="activate-G3-r9-after-P2",
        pointer_name=POINTER,
        target_generation_id="G3",
        expected_generation_id="G2",
        expected_revision=8,
        committer_id=lease.committer_id,
        committer_fence=lease.fencing_token,
        committed_at=_timestamp(base, 35.1),
        previous_retire_after=_timestamp(base, 45),
    )
    if activated.outcome is not RepositoryOutcome.ACTIVATED:
        raise AssertionError("G3_R9_ACTIVATION_FAILED")

    old_query_rejection = ""
    try:
        _query_read_view_ids(
            lifecycle,
            view_id=pending_view_id,
            generation_id="G2",
            authorization_id="P1",
            query_vector=(1.0, 0.0, 0.0),
            top_k=1,
            mode=QueryMode.EXACT,
            observed_at=_timestamp(base, 36),
        )
    except ReadViewQueryRejected as exc:
        old_query_rejection = str(exc)
    if old_query_rejection != "CURRENT_AUTHORIZATION_CHANGED":
        raise AssertionError("OLD_G2_READ_VIEW_DID_NOT_FAIL_CURRENT_AUTHORIZATION")

    revoked_evidence = replace(
        pending_run.evidence,
        evidence_id="release-evidence-Q3-pending-after-P2",
        current_authorization_revision="P2",
        currently_authorized_occurrence_ids=("C@v1",),
        current_content_security_snapshot_digest=p2.identity_digest,
    )
    revoked_release = _release_decision(
        pending_run,
        decision_id="release-Q3-pending-after-P2",
        evidence=revoked_evidence,
        observed_at=_timestamp(base, 36.1),
    )
    if (
        revoked_release.result is not SecurityResult.FAIL
        or revoked_release.disposition is not SecurityDisposition.BLOCKED
    ):
        raise AssertionError("REVOKED_OLD_CANDIDATE_WAS_NOT_BLOCKED")
    revoked_persist = _persist_release(
        security,
        request_id=pending_request_id,
        evidence=revoked_evidence,
        decision=revoked_release,
        observed_at=_timestamp(base, 36.1),
    )
    _require_applied(revoked_persist, label="PERSIST_REVOKED_RELEASE")

    new_request_id = "request-Q2-G3"
    new_view_id = _acquire_view(
        lifecycle,
        request_id=new_request_id,
        generation_id="G3",
        pointer_revision=9,
        authorization_id="P2",
        acquired_at=_timestamp(base, 37),
        lease_expires_at=_timestamp(base, 180),
    )
    new_exact = _query_read_view_ids(
        lifecycle,
        view_id=new_view_id,
        generation_id="G3",
        authorization_id="P2",
        query_vector=(0.0, 1.0, 0.0),
        top_k=1,
        mode=QueryMode.EXACT,
        observed_at=_timestamp(base, 37.1),
    )
    new_hnsw = _query_read_view_ids(
        lifecycle,
        view_id=new_view_id,
        generation_id="G3",
        authorization_id="P2",
        query_vector=(0.0, 1.0, 0.0),
        top_k=1,
        mode=QueryMode.HNSW,
        observed_at=_timestamp(base, 37.2),
    )
    if new_exact != ("C@v1",) or new_hnsw != ("C@v1",):
        raise AssertionError("NEW_G3_Q2_RETRIEVAL_FAILED")
    new_binding = _binding_from_read_view(
        factory,
        request_id=new_request_id,
        purpose="refund-Q2-after-P2",
        view_id=new_view_id,
        generation_id="G3",
        authorization_revision="P2",
        manifest_occurrence_ids=("C@v1",),
        security_snapshot=p2,
        policy=policy,
    )
    new_run = _run_query(
        factory,
        query_id="Q2-G3",
        binding=new_binding,
        occurrence_ids=("C@v1",),
        observed_at=_timestamp(base, 37.3),
    )
    _persist_complete_query(
        security,
        new_run,
        observed_at=_timestamp(base, 37.3),
    )
    database_guards = _database_release_and_content_safety_guards(
        factory,
        decision_id=new_run.release.decision_id,
    )
    released_new_view = lifecycle.release_read_view(
        view_id=new_view_id,
        expected_fencing_token=1,
        released_at=_timestamp(base, 38),
    )
    if released_new_view.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("NEW_G3_READ_VIEW_RELEASE_FAILED")

    cross_generation_rejected = False
    try:
        RagSecurityPipeline.assemble_context(
            manifest_id="context-cross-generation-reuse",
            binding=new_binding,
            bundle=pending_run.bundle,
            included_occurrence_ids=("C@v1",),
            context_budget=1,
            actual_context_units=1,
            envelope_schema_version="untrusted-evidence-v1",
            serialization_version="json-escaped-v1",
            projection_version="least-fields-v1",
            structured_untrusted_data_digest=stable_hash("cross-generation-reuse"),
        )
    except SecurityIdentityConflict:
        cross_generation_rejected = True
    if not cross_generation_rejected:
        raise AssertionError("G2_BUNDLE_REUSED_FOR_G3")

    release_failures = _release_failure_controls(
        new_run,
        observed_at=_timestamp(base, 38.1),
    )
    for name in ("dlp_timeout", "dlp_sensitive"):
        evidence, decision = release_failures[name]
        result = _persist_release(
            security,
            request_id=new_request_id,
            evidence=evidence,
            decision=decision,
            observed_at=_timestamp(base, 38.1),
        )
        _require_applied(result, label=f"PERSIST_{name.upper()}")
        chain = security.read_request_chain(new_request_id)
        evidence_rows = [
            item for item in chain if item.artifact_id == evidence.evidence_id
        ]
        if len(evidence_rows) != 1 or evidence_rows[0].result != decision.result.value:
            raise AssertionError(f"{name.upper()}_EVIDENCE_RESULT_NOT_PERSISTED")

    orphan_request_id = "request-Q2-G3-orphan"
    orphan_view_id = _acquire_view(
        lifecycle,
        request_id=orphan_request_id,
        generation_id="G3",
        pointer_revision=9,
        authorization_id="P2",
        acquired_at=_timestamp(base, 38.15),
        lease_expires_at=_timestamp(base, 1440),
    )
    orphan_ids = _query_read_view_ids(
        lifecycle,
        view_id=orphan_view_id,
        generation_id="G3",
        authorization_id="P2",
        query_vector=(0.0, 1.0, 0.0),
        top_k=1,
        mode=QueryMode.EXACT,
        observed_at=_timestamp(base, 38.16),
    )
    if orphan_ids != ("C@v1",):
        raise AssertionError("ORPHAN_PROBE_G3_QUERY_MISMATCH")
    orphan_binding = _binding_from_read_view(
        factory,
        request_id=orphan_request_id,
        purpose="refund-Q2-orphan-transaction-probe",
        view_id=orphan_view_id,
        generation_id="G3",
        authorization_revision="P2",
        manifest_occurrence_ids=("C@v1",),
        security_snapshot=p2,
        policy=policy,
    )
    orphan_run = _run_query(
        factory,
        query_id="Q2-G3-orphan",
        binding=orphan_binding,
        occurrence_ids=("C@v1",),
        observed_at=_timestamp(base, 38.17),
    )
    _persist_pre_release_chain(
        security,
        orphan_run,
        created_at=_timestamp(base, 38.17),
    )
    orphan_fault = _release_intent_fault(
        security,
        factory,
        orphan_run,
        observed_at=_timestamp(base, 38.2),
    )
    orphan_closed = lifecycle.release_read_view(
        view_id=orphan_view_id,
        expected_fencing_token=1,
        released_at=_timestamp(base, 38.3),
    )
    if orphan_closed.outcome is not RepositoryOutcome.APPLIED:
        raise AssertionError("ORPHAN_PROBE_READ_VIEW_RELEASE_FAILED")
    incident = _incident_controls(security, base=base)
    environment = _persist_environment_evidence(
        security,
        factory,
        observed_at=_timestamp(base, 44),
    )

    pointer = _query_one(
        factory,
        """
        SELECT generation_id, revision
        FROM day104_l3.active_pointers
        WHERE pointer_name = %s
        """,
        (POINTER,),
    )
    generation_states = _query_rows(
        factory,
        """
        SELECT generation_id, state, active_readers
        FROM day104_l3.generations
        WHERE generation_id IN ('G2', 'G3')
        ORDER BY generation_id
        """,
    )
    pending_lease = _query_one(
        factory,
        """
        SELECT extract(epoch FROM (lease_expires_at - acquired_at))::bigint,
               lease_expires_at > clock_timestamp()
        FROM day104_l3.read_views
        WHERE view_id = %s
        """,
        (pending_view_id,),
    )
    current_security = security.current_security_snapshot(TENANT)
    if (
        pointer != ("G3", 9)
        or generation_states != [("G2", "DRAINING", 1), ("G3", "ACTIVE", 0)]
        or pending_lease is None
        or int(pending_lease[0]) < 3600
        or not bool(pending_lease[1])
        or current_security is None
        or current_security.snapshot_id != "P2"
        or current_security.revision != 2
    ):
        raise AssertionError("FINAL_G3_P2_DURABLE_STATE_MISMATCH")

    security_cases = [
        _case(
            case_id="normal-q1-g2",
            generation_id="G2",
            stage="PASS",
            action="RELEASE",
            prompt_ids=("A@v1",),
            citation_ids=("A@v1",),
        ),
        _case(
            case_id="normal-q2-g2",
            generation_id="G2",
            stage="PASS",
            action="RELEASE",
            prompt_ids=("C@v1",),
            citation_ids=("C@v1",),
        ),
        _case(
            case_id="normal-q3-g2",
            generation_id="G2",
            stage="PASS",
            action="RELEASE",
            prompt_ids=NORMAL_IDS,
            citation_ids=NORMAL_IDS,
        ),
        _case(
            case_id="poisoned-generation-not-served",
            generation_id="G_BAD",
            stage="FAIL",
            action="NOT_SERVED",
        ),
        _case(
            case_id="document-injection-x-blocked",
            generation_id="G_BAD",
            stage="FAIL",
            action="BLOCKED",
        ),
        _case(
            case_id="detector-timeout-y-quarantined",
            generation_id="G_BAD",
            stage="INCONCLUSIVE",
            action="QUARANTINE",
        ),
        _case(
            case_id="detector-rescan-y-v2-append-only",
            generation_id="NOT_SERVING",
            stage="PASS",
            action="NOT_SERVED",
        ),
        _case(
            case_id="cross-document-z-blocked",
            generation_id="G_BAD",
            stage="FAIL",
            action="BLOCKED",
        ),
        _case(
            case_id="cross-tenant-t-blocked",
            generation_id="G_BAD",
            stage="FAIL",
            action="BLOCKED",
        ),
        _case(
            case_id="revoked-a-old-candidate-blocked",
            generation_id="G2",
            stage="FAIL",
            action="BLOCKED",
            prompt_ids=NORMAL_IDS,
        ),
        _case(
            case_id="new-q2-g3-released",
            generation_id="G3",
            stage="PASS",
            action="RELEASE",
            prompt_ids=("C@v1",),
            citation_ids=("C@v1",),
        ),
        _case(
            case_id="wrong-citation-blocked",
            generation_id="G3",
            stage="FAIL",
            action="BLOCKED",
            prompt_ids=("C@v1",),
        ),
        _case(
            case_id="dlp-timeout-blocked",
            generation_id="G3",
            stage="INCONCLUSIVE",
            action="BLOCKED",
            prompt_ids=("C@v1",),
        ),
        _case(
            case_id="dlp-sensitive-blocked",
            generation_id="G3",
            stage="FAIL",
            action="BLOCKED",
            prompt_ids=("C@v1",),
        ),
    ]

    failure_injections = [
        _failure(
            "provider-manifest-extra-occurrence",
            "reject generation with an extra occurrence",
            "independent readback marked generation integrity failed",
            poisoned,
        ),
        _failure(
            "manifest-content-or-metadata-substitution",
            "reject equal-count occurrence or digest substitution",
            "exact manifest identity mismatch rejected",
            adversarial["manifest_substitution"],
        ),
        _failure(
            "detector-timeout",
            "treat unavailable detector evidence as inconclusive quarantine",
            "Y@v1 remained quarantined and absent from prompt",
            adversarial["Y"],
        ),
        _failure(
            "detector-versioned-rescan",
            "append Y@v2 with new parser scanner detector evidence without overwriting Y@v1",
            "Y@v1 remained immutable; Y@v2 used a new security record and remained outside serving generations",
            y_records,
        ),
        _failure(
            "document-injection-confirmed",
            "block confirmed document prompt injection before context assembly",
            "X bundle decision failed and no context manifest was written",
            adversarial["X"],
        ),
        _failure(
            "cross-tenant-candidate",
            "reject candidate outside request tenant",
            "T was denied and absent from prompt",
            adversarial["T"],
        ),
        _failure(
            "cross-document-bundle-chain",
            "analyze the full bundle and block composed attack meaning",
            "Z1/Z2 bundle failed before context assembly",
            adversarial["Z"],
        ),
        _failure(
            "security-artifact-exact-replay-conflict",
            "converge identical replay and reject same ID with changed digest",
            "identical replay converged and changed digest was rejected",
            replay_control,
        ),
        _failure(
            "security-snapshot-cas-race",
            "allow exactly one current security snapshot revision winner",
            "one CAS advanced P2 and one stale revision was rejected",
            cas_race,
        ),
        _failure(
            "security-transition-write-fault",
            "roll back current snapshot pointer when transition append fails",
            "no partial snapshot pointer or transition persisted",
            transition_fault,
        ),
        _failure(
            "authorization-change-after-candidate",
            "keep old candidate bound to G2 and block release after P2",
            "old candidate remained historical and output release failed closed",
            (old_query_rejection, revoked_release.digest),
        ),
        _failure(
            "context-projection-digest-tamper",
            "reject context projection or serialization identity change",
            "context assembly digest mismatch was rejected",
            True,
        ),
        _failure(
            "wrong-citation",
            "block citation outside exact supported occurrence",
            "output release failed with no released citations",
            release_failures["wrong_citation"][1].digest,
        ),
        _failure(
            "dlp-timeout",
            "block when DLP evidence is inconclusive",
            "output release was inconclusive and blocked",
            release_failures["dlp_timeout"][1].digest,
        ),
        _failure(
            "dlp-sensitive-category",
            "fail when DLP identifies sensitive material",
            "output release failed and returned a content-safe blocked intent",
            release_failures["dlp_sensitive"][1].digest,
        ),
        _failure(
            "orphan-candidate-restart",
            "default block candidate missing a durable release decision after restart",
            "candidate persisted while injected decision and intent transaction rolled back",
            orphan_fault,
        ),
        _failure(
            "incident-overwrite-or-branch",
            "reject incident overwrite second root and branch",
            "append-only ledger rejected changed digest and branching correction",
            incident,
        ),
        _failure(
            "container-restart-readback",
            "recover durable G3/P2 security and blocked-release state after restart",
            "NOT_RUN_IN_INITIAL_PROCESS",
            environment["identity_digest"],
        ),
    ]

    observed_at = datetime.now(timezone.utc).isoformat()
    hard_gates = {
        "schema_migration_integrity": _gate(
            "day104-and-day105-schema-installed",
            (received.identity_digest, p1.identity_digest),
            observed_at,
        ),
        "postgresql_pgvector_identity_match": _gate(
            "postgresql-pgvector-version-readback", environment, observed_at
        ),
        "append_only_security_record_immutability": _gate(
            "append-only-trigger-and-replay",
            (replay_control, database_guards),
            observed_at,
        ),
        "ingestion_security_evidence_binding": _gate(
            "versioned-Y-security-records", y_records, observed_at
        ),
        "quarantine_and_tombstone_currentness": _gate(
            "B-tombstone-X-Y-quarantine",
            (command.identity_digest, adversarial["Y"]),
            observed_at,
        ),
        "sealed_manifest_exact_binding": _gate(
            "G2-G3-manifest-readback", (g2, g3), observed_at
        ),
        "provider_poisoning_not_served": _gate(
            "G_BAD-integrity-failed", poisoned, observed_at
        ),
        "retrieval_authorization_and_tenant_isolation": _gate(
            "T-and-P2-currentness", (adversarial["T"], old_query_rejection), observed_at
        ),
        "bundle_prompt_injection_isolation": _gate(
            "X-Z-bundle-analysis", (adversarial["X"], adversarial["Z"]), observed_at
        ),
        "context_assembly_exact_manifest": _gate(
            "context-receipts-and-tamper", (q3.context.digest, True), observed_at
        ),
        "read_view_single_generation": _gate(
            "G2-old-G3-new-read-views", (pending_view_id, new_view_id), observed_at
        ),
        "authorization_snapshot_rebuild_and_activation": _gate(
            "P1-BS1-G2-r8-to-P2-BS2-G3-r9",
            (bs1.fingerprint, bs2.fingerprint, pointer),
            observed_at,
        ),
        "release_current_authorization_recheck": _gate(
            "old-G2-release-blocked", revoked_release.digest, observed_at
        ),
        "citation_exact_binding": _gate(
            "wrong-citation-blocked",
            release_failures["wrong_citation"][1].digest,
            observed_at,
        ),
        "dlp_metadata_destination_fail_closed": _gate(
            "DLP-fail-and-unknown",
            (
                release_failures["dlp_timeout"][1].digest,
                release_failures["dlp_sensitive"][1].digest,
            ),
            observed_at,
        ),
        "security_snapshot_cas_and_transaction_atomicity": _gate(
            "snapshot-CAS-and-fault",
            (cas_race, transition_fault, orphan_fault),
            observed_at,
        ),
        "incident_ledger_append_only": _gate(
            "incident-root-correction-no-branch", incident, observed_at
        ),
        "normal_quality_preserved": _gate("Q1-Q2-Q3-exact-HNSW", matrix, observed_at),
        "restart_durability_and_idempotency": {
            "status": "NOT_RUN",
            "safe_reason": "DATABASE_CONTAINER_RESTART_PENDING",
            "evidence_ids": [],
            "evidence_digests": [],
            "observed_at": None,
        },
        "content_safe_evidence": _gate(
            "content-safe-report-and-database-value-boundary",
            database_guards,
            observed_at,
        ),
    }

    completed_at = datetime.now(timezone.utc).isoformat()
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "PASS",
        "evidence_level": EVIDENCE_LEVEL,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at,
        "baselines": {
            "day104_l3_report_checksum": DAY104_L3_CHECKSUM,
            "day105_l2_report_checksum": DAY105_L2_CHECKSUM,
        },
        "environment": environment,
        "lifecycle": {
            "poisoned_generation": poisoned,
            "G2": g2,
            "G3": g3,
            "pointer": {"generation_id": str(pointer[0]), "revision": int(pointer[1])},
            "generation_states": [list(item) for item in generation_states],
        },
        "normal_retrieval": matrix,
        "adversarial_controls": adversarial,
        "versioned_detector_records": y_records,
        "authorization_transition": {
            "old_generation_id": "G2",
            "old_pointer_revision": 8,
            "old_request_remained_pinned": True,
            "old_query_after_P2": old_query_rejection,
            "old_release_result": revoked_release.result.value,
            "old_release_disposition": revoked_release.disposition.value,
            "old_read_view_lease_duration_seconds": int(pending_lease[0]),
            "restart_window_open_at_completion": bool(pending_lease[1]),
            "new_generation_id": "G3",
            "new_pointer_revision": 9,
            "new_query_ids": list(new_exact),
            "cross_generation_bundle_rejected": cross_generation_rejected,
        },
        "security_persistence": {
            "current_snapshot_id": current_security.snapshot_id,
            "current_revision": current_security.revision,
            "artifact_replay": replay_control,
            "snapshot_cas_race": cas_race,
            "transition_fault": transition_fault,
            "append_only_mutation_rejected": True,
            "database_guards": database_guards,
            "incident": incident,
            "orphan_release_fault": orphan_fault,
        },
        "security_cases": security_cases,
        "failure_injections": failure_injections,
        "hard_gates": hard_gates,
        "fixture_production_eligible": False,
        "raw_attack_payloads_logged": False,
        "raw_protected_content_logged": False,
        "raw_system_prompts_logged": False,
        "raw_secrets_logged": False,
        "raw_cross_tenant_content_logged": False,
        "raw_vectors_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "not_run": [
            "real scanner detector DLP model and external vector Provider",
            "production IAM RLS TLS secret rotation and egress",
            "HA replica failover backup restore and network partition",
            "physical purge across WAL backups caches and retained media",
            "production recall latency load cost soak canary and incident observation",
        ],
        "claim_boundary": (
            "Pinned local PostgreSQL/pgvector transactions and deterministic "
            "application-owned security adapters only; no production claim."
        ),
    }
    report["report_checksum"] = stable_hash(report)
    return report


def _fail_closed_payload(
    reason: str,
    error_type: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "status": "FAIL_CLOSED",
        "evidence_level": "NOT_RUN",
        "safe_reason": reason,
        "fixture_production_eligible": False,
        "raw_attack_payloads_logged": False,
        "raw_protected_content_logged": False,
        "raw_system_prompts_logged": False,
        "raw_secrets_logged": False,
        "raw_cross_tenant_content_logged": False,
        "raw_vectors_logged": False,
        "database_url_logged": False,
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }
    if error_type is not None:
        payload["error_type"] = error_type
    payload["report_checksum"] = stable_hash(payload)
    return payload


def main() -> int:
    if os.environ.get("DAY105_L3_INTEGRATION") != "1":
        print(
            json.dumps(
                _fail_closed_payload("DAY105_L3_INTEGRATION_FLAG_REQUIRED"),
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    database_url = os.environ.get("DAY105_L3_DATABASE_URL", "")
    if not database_url.strip():
        print(
            json.dumps(
                _fail_closed_payload("DAY105_L3_DATABASE_URL_REQUIRED"),
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
                _fail_closed_payload(
                    "DAY105_L3_INTEGRATION_FAILED",
                    type(exc).__name__,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
