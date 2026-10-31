"""Independent Day99 readback and Exact/Flat validation."""

from __future__ import annotations

from dataclasses import dataclass

from rag_vector_adapter import (
    ApplicationVectorAdapter,
    ExactFlatReference,
    ProviderReadback,
    ProviderWriteAck,
)
from rag_vector_contracts import (
    EvidenceGate,
    EvidenceState,
    GateEvidence,
    GenerationEvidence,
    GenerationManifest,
    VectorPoint,
    generation_manifest,
)
from rag_vector_index_planner import VectorBatchPlan


@dataclass(frozen=True)
class VectorValidationDecision:
    ready_to_seal: bool
    safe_reason: str
    provider_checkpoint: str
    evidence: GenerationEvidence


class VectorGenerationValidator:
    def evaluate(
        self,
        *,
        expected_points: tuple[VectorPoint, ...],
        expected_manifest: GenerationManifest,
        plan: VectorBatchPlan,
        acknowledgements: tuple[ProviderWriteAck, ...],
        request_id: str,
        readback: ProviderReadback,
        adapter: ApplicationVectorAdapter,
        score_tolerance: float = 1e-12,
    ) -> VectorValidationDecision:
        expected_acks = {batch.batch_id: batch for batch in plan.batches}
        ack_ids = tuple(ack.batch_id for ack in acknowledgements)
        if len(set(ack_ids)) != len(ack_ids):
            return self._reject(
                "DUPLICATE_DATABASE_BATCH_ACK", readback.checkpoint
            )
        if set(ack_ids) != set(expected_acks):
            return self._reject(
                "MISSING_OR_UNKNOWN_DATABASE_BATCH_ACK", readback.checkpoint
            )
        for ack in acknowledgements:
            batch = expected_acks[ack.batch_id]
            if (
                ack.generation_id != batch.generation_id
                or ack.namespace != batch.namespace
                or ack.tenant_id != batch.tenant_id
                or ack.request_id != request_id
                or ack.operation_id != plan.operation_id
            ):
                return self._reject(
                    "DATABASE_ACK_CORRELATION_MISMATCH", readback.checkpoint
                )
            expected_ids = tuple(point.point_id for point in batch.points)
            if ack.accepted_point_ids != expected_ids:
                return self._reject(
                    "PARTIAL_OR_UNKNOWN_DATABASE_POINT_ACK",
                    readback.checkpoint,
                )
        if not readback.points:
            return self._reject(
                "READBACK_MANIFEST_MISMATCH", readback.checkpoint
            )
        observed = generation_manifest(
            readback.points,
            embedding_set_id=expected_manifest.embedding_set_id,
            contract_fingerprint=expected_manifest.contract_fingerprint,
        )
        if observed != expected_manifest:
            return self._reject(
                "READBACK_MANIFEST_MISMATCH", readback.checkpoint
            )
        if not expected_points:
            return self._reject("EMPTY_GENERATION", readback.checkpoint)

        generation_id = expected_points[0].generation_id
        if readback.generation_id != generation_id:
            return self._reject(
                "READBACK_GENERATION_MISMATCH", readback.checkpoint
            )
        tenant_id = expected_points[0].tenant_id
        top_k = min(3, len(expected_points))
        for probe in expected_points:
            expected = ExactFlatReference.search(
                points=expected_points,
                query_vector=probe.vector,
                tenant_id=tenant_id,
                top_k=top_k,
            )
            actual = adapter.search(
                generation_id=generation_id,
                query_vector=probe.vector,
                tenant_id=tenant_id,
                top_k=top_k,
            )
            if tuple(item.point_id for item in actual) != tuple(
                item.point_id for item in expected
            ):
                return self._reject(
                    "EXACT_REFERENCE_ORDER_MISMATCH", readback.checkpoint
                )
            if any(
                abs(left.similarity - right.similarity) > score_tolerance
                for left, right in zip(actual, expected, strict=True)
            ):
                return self._reject(
                    "APPLICATION_SCORE_SEMANTICS_MISMATCH",
                    readback.checkpoint,
                )

        forbidden = adapter.search(
            generation_id=generation_id,
            query_vector=expected_points[0].vector,
            tenant_id="tenant-forbidden-probe",
            top_k=top_k,
        )
        if forbidden:
            return self._reject(
                "FAKE_TENANT_FILTER_MISMATCH", readback.checkpoint
            )
        evidence = GenerationEvidence((
            GateEvidence(
                EvidenceGate.CONTENT_READBACK,
                EvidenceState.PASS,
                "EXECUTED_LOCAL_FAKE",
                "MANIFEST_AND_CHECKPOINT_MATCH",
            ),
            GateEvidence(
                EvidenceGate.SCORE_SEMANTICS,
                EvidenceState.PASS,
                "EXECUTED_LOCAL_FAKE",
                "COSINE_DISTANCE_TRANSLATED_TO_SIMILARITY",
            ),
            GateEvidence(
                EvidenceGate.EXACT_PARITY,
                EvidenceState.PASS,
                "EXECUTED_LOCAL_FAKE",
                "FAKE_FLAT_MATCHES_APPLICATION_EXACT_REFERENCE",
            ),
            GateEvidence(
                EvidenceGate.TENANT_FILTER,
                EvidenceState.PASS,
                "EXECUTED_LOCAL_FAKE",
                "SYNTHETIC_OTHER_TENANT_RETURNED_ZERO",
            ),
            GateEvidence(
                EvidenceGate.ANN_RECALL,
                EvidenceState.NOT_RUN,
                "REAL_PROVIDER",
                "NO_REAL_ANN_INDEX_EXECUTED",
            ),
            GateEvidence(
                EvidenceGate.LATENCY_CAPACITY,
                EvidenceState.NOT_RUN,
                "REAL_PROVIDER",
                "NO_PRODUCTION_SCALE_OR_LATENCY_RUN",
            ),
            GateEvidence(
                EvidenceGate.RECOVERY,
                EvidenceState.NOT_RUN,
                "DISTRIBUTED_RUNTIME",
                "NO_DURABLE_BACKUP_OR_RESTORE_DRILL",
            ),
            GateEvidence(
                EvidenceGate.REAL_PROVIDER,
                EvidenceState.NOT_RUN,
                "REAL_PROVIDER",
                "DETERMINISTIC_FAKE_ONLY",
            ),
        ))
        return VectorValidationDecision(
            True,
            "READBACK_AND_LOCAL_EXACT_REFERENCE_VERIFIED",
            readback.checkpoint,
            evidence,
        )

    @staticmethod
    def _reject(
        reason: str, checkpoint: str
    ) -> VectorValidationDecision:
        return VectorValidationDecision(
            False,
            reason,
            checkpoint,
            GenerationEvidence((GateEvidence(
                EvidenceGate.CONTENT_READBACK,
                EvidenceState.FAIL,
                "EXECUTED_LOCAL_FAKE",
                reason,
            ),)),
        )
