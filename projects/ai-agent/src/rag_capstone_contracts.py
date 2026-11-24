"""Day106 cumulative Production RAG capstone contracts.

The contracts in this module compose identities owned by Day95-Day105.  They
do not introduce another source, ChunkSet, EmbeddingSet, Generation, serving
pointer, authorization, or release authority.  The only new durable boundary
is response dispatch and delivery after an application-owned release decision.

All values are content-safe: protected source text, prompts, candidate text,
raw vectors, credentials, and reusable attack payloads are deliberately absent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from rag_chunking_contracts import stable_hash


def _require_non_empty(*values: str) -> None:
    if not all(value.strip() for value in values):
        raise ValueError("complete non-empty capstone bindings are required")


def _require_unique(values: tuple[str, ...], *, label: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} cannot contain empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")


def _require_canonical(values: tuple[str, ...], *, label: str) -> None:
    _require_unique(values, label=label)
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be sorted")


class CapstoneResult(str, Enum):
    """Evidence result; execution absence is not a passing observation."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_RUN = "NOT_RUN"


class ResponseIntentState(str, Enum):
    """Durable response state, distinct from release and delivery facts."""

    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    PENDING = "PENDING"
    DELIVERY_UNKNOWN = "DELIVERY_UNKNOWN"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"


class DispatchObservation(str, Enum):
    """Content-safe observation returned by a destination or reconciliation."""

    SEND_STARTED = "SEND_STARTED"
    ACCEPTED = "ACCEPTED"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"
    DELIVERED = "DELIVERED"
    DUPLICATE_RECEIPT = "DUPLICATE_RECEIPT"


@dataclass(frozen=True)
class SourceToOccurrenceLineage:
    """Read-only projection of the existing source-to-occurrence authority."""

    lineage_id: str
    tenant_id: str
    resource_id: str
    source_artifact_id: str
    source_version: str
    source_artifact_digest: str
    parsed_artifact_id: str
    parsed_artifact_digest: str
    parser_contract_version: str
    chunk_set_id: str
    chunk_set_digest: str
    chunker_contract_version: str
    occurrence_id: str
    content_digest: str
    metadata_digest: str
    metadata_version: str
    provenance_revision: str
    embedding_set_id: str
    embedding_record_id: str
    embedding_contract_fingerprint: str
    upstream_evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        strings = tuple(
            value
            for key, value in asdict(self).items()
            if key != "upstream_evidence_digests"
        )
        _require_non_empty(*strings)
        _require_canonical(
            self.upstream_evidence_digests,
            label="upstream evidence digests",
        )
        if not self.upstream_evidence_digests:
            raise ValueError("lineage requires upstream evidence")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class CapstoneRequestBinding:
    """Pre-retrieval identity spine; it intentionally has no retrieved IDs."""

    request_attempt_id: str
    request_id: str
    principal_id: str
    tenant_id: str
    action: str
    purpose: str
    audience: str
    pointer_name: str
    generation_id: str
    generation_artifact_digest: str
    generation_manifest_digest: str
    build_snapshot_fingerprint: str
    pointer_revision: int
    read_view_id: str
    read_view_fence: int
    read_view_digest: str
    source_snapshot_id: str
    authorization_snapshot_id: str
    deletion_snapshot_id: str
    policy_fingerprint: str
    security_binding_fingerprint: str
    retrieval_authorization_revision_digest: str
    retrieval_authorization_scope_fingerprint: str
    selected_retrieval_bundle_id: str
    selected_retrieval_bundle_revision: int
    selected_retrieval_bundle_fingerprint: str
    created_at: str

    def __post_init__(self) -> None:
        strings = tuple(
            str(value)
            for key, value in asdict(self).items()
            if key
            not in {
                "pointer_revision",
                "read_view_fence",
                "selected_retrieval_bundle_revision",
            }
        )
        _require_non_empty(*strings)
        if min(
            self.pointer_revision,
            self.read_view_fence,
            self.selected_retrieval_bundle_revision,
        ) <= 0:
            raise ValueError("pointer, ReadView, and retrieval revisions must be positive")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class Day101ExecutionReceipt:
    """Application-owned proof of which selected bundle produced a handoff."""

    receipt_id: str
    request_id: str
    operation_id: str
    query_hash: str
    selected_bundle_id: str
    selected_bundle_fingerprint: str
    selected_generation_id: str
    selected_pointer_revision: int
    generation_artifact_digest: str
    authorization_scope_fingerprint: str
    original_query_digest: str
    day101_handoff_digest: str
    candidate_pool_digest: str
    exact_occurrence_ids: tuple[str, ...]
    exact_content_digests: tuple[str, ...]
    authority_id: str
    authority_mac: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.receipt_id,
            self.request_id,
            self.operation_id,
            self.query_hash,
            self.selected_bundle_id,
            self.selected_bundle_fingerprint,
            self.selected_generation_id,
            self.generation_artifact_digest,
            self.authorization_scope_fingerprint,
            self.original_query_digest,
            self.day101_handoff_digest,
            self.candidate_pool_digest,
            self.authority_id,
            self.authority_mac,
        )
        if self.selected_pointer_revision <= 0:
            raise ValueError("selected pointer revision must be positive")
        _require_unique(
            self.exact_occurrence_ids,
            label="Day101 exact occurrence IDs",
        )
        if len(self.exact_occurrence_ids) != len(self.exact_content_digests):
            raise ValueError("Day101 exact occurrences require content digests")

    @property
    def signing_digest(self) -> str:
        payload = asdict(self)
        payload.pop("authority_mac")
        return stable_hash(payload)

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ReleaseCurrentnessSnapshot:
    """Content-safe application-owned facts read immediately before release."""

    snapshot_id: str
    revision: int
    tenant_id: str
    destination: str
    source_eligible_occurrence_ids: tuple[str, ...]
    quarantined_occurrence_ids: tuple[str, ...]
    provenance_revision: str
    tombstone_revision: str
    content_security_snapshot_digest: str
    security_policy_fingerprint: str
    dlp_result: str
    metadata_stripping_result: str
    destination_result: str
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(
            self.snapshot_id,
            self.tenant_id,
            self.destination,
            self.provenance_revision,
            self.tombstone_revision,
            self.content_security_snapshot_digest,
            self.security_policy_fingerprint,
            self.dlp_result,
            self.metadata_stripping_result,
            self.destination_result,
        )
        if self.revision <= 0:
            raise ValueError("release-currentness revision must be positive")
        _require_canonical(
            self.source_eligible_occurrence_ids,
            label="source-eligible occurrence IDs",
        )
        _require_canonical(
            self.quarantined_occurrence_ids,
            label="quarantined occurrence IDs",
        )
        _require_canonical(
            self.evidence_digests,
            label="release-currentness evidence digests",
        )
        allowed_results = {"PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"}
        if {
            self.dlp_result,
            self.metadata_stripping_result,
            self.destination_result,
        } - allowed_results:
            raise ValueError("release-currentness results are invalid")
        if not self.evidence_digests:
            raise ValueError("release currentness requires durable evidence")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RetrievalAndContextReceipt:
    """Post-retrieval receipt for exact results and actual model context."""

    receipt_id: str
    request_binding_digest: str
    retrieval_operation_id: str
    retrieval_request_id: str
    day101_execution_receipt_digest: str
    day101_handoff_digest: str
    prompt_authorization_scope_fingerprint: str
    prompt_authorization_revision_digest: str
    retrieval_bundle_id: str
    retrieval_bundle_digest: str
    retrieval_security_decision_digest: str
    bundle_security_decision_digest: str
    exact_occurrence_ids: tuple[str, ...]
    exact_content_digests: tuple[str, ...]
    context_manifest_id: str
    context_manifest_digest: str
    context_occurrence_ids: tuple[str, ...]
    assembled_context_digest: str
    unauthorized_prompt_count: int
    created_at: str

    def __post_init__(self) -> None:
        strings = (
            self.receipt_id,
            self.request_binding_digest,
            self.retrieval_operation_id,
            self.retrieval_request_id,
            self.day101_execution_receipt_digest,
            self.day101_handoff_digest,
            self.prompt_authorization_scope_fingerprint,
            self.prompt_authorization_revision_digest,
            self.retrieval_bundle_id,
            self.retrieval_bundle_digest,
            self.retrieval_security_decision_digest,
            self.bundle_security_decision_digest,
            self.context_manifest_id,
            self.context_manifest_digest,
            self.assembled_context_digest,
            self.created_at,
        )
        _require_non_empty(*strings)
        _require_unique(self.exact_occurrence_ids, label="exact occurrence IDs")
        _require_unique(self.context_occurrence_ids, label="context occurrence IDs")
        if not self.exact_occurrence_ids:
            raise ValueError("retrieval receipt cannot be empty")
        if len(self.exact_occurrence_ids) != len(self.exact_content_digests):
            raise ValueError("each exact occurrence requires one content digest")
        if not set(self.context_occurrence_ids).issubset(self.exact_occurrence_ids):
            raise ValueError("model context must be a subset of the RetrievalBundle")
        if self.unauthorized_prompt_count < 0:
            raise ValueError("unauthorized prompt count cannot be negative")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ResponseIntent:
    """Versioned durable intent, never proof of destination delivery."""

    intent_id: str
    request_binding_digest: str
    output_release_decision_digest: str
    candidate_digest: str
    destination: str
    dispatch_idempotency_key: str
    state: ResponseIntentState
    revision: int
    created_at: str
    dispatch_at: str | None = None
    delivered_at: str | None = None
    provider_message_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            self.intent_id,
            self.request_binding_digest,
            self.output_release_decision_digest,
            self.candidate_digest,
            self.destination,
            self.dispatch_idempotency_key,
            self.created_at,
        )
        if self.revision <= 0:
            raise ValueError("response intent revision must be positive")
        if self.state is ResponseIntentState.NOT_ATTEMPTED:
            raise ValueError("released response intents start PENDING")
        if self.state in {
            ResponseIntentState.DISPATCHED,
            ResponseIntentState.DELIVERED,
        } and not self.dispatch_at:
            raise ValueError("DISPATCHED/DELIVERED requires accepted dispatch evidence")
        if self.state is ResponseIntentState.DELIVERED and (
            not self.delivered_at or not self.provider_message_id
        ):
            raise ValueError("DELIVERED requires an authoritative bound receipt")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class AnswerReleaseRecord:
    """Durable application decision separated from dispatch/delivery evidence."""

    record_id: str
    request_binding_digest: str
    retrieval_context_receipt_digest: str
    model_invocation_id: str
    model_invocation_digest: str
    answer_candidate_id: str
    answer_candidate_digest: str
    release_evidence_id: str
    release_evidence_digest: str
    output_release_decision_id: str
    output_release_decision_digest: str
    disclosure_envelope_digest: str
    tenant_id: str
    principal_id: str
    action: str
    purpose: str
    current_authorization_scope_fingerprint: str
    current_authorization_revision_digest: str
    release_currentness_snapshot_id: str
    release_currentness_snapshot_digest: str
    release_currentness_revision: int
    released_occurrence_ids: tuple[str, ...]
    authorized_destination: str | None
    dispatch_idempotency_key: str | None
    result: str
    disposition: str
    safe_reason_codes: tuple[str, ...]
    response_intent_id: str | None
    response_dispatch_state: ResponseIntentState
    created_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.record_id,
            self.request_binding_digest,
            self.retrieval_context_receipt_digest,
            self.model_invocation_id,
            self.model_invocation_digest,
            self.answer_candidate_id,
            self.answer_candidate_digest,
            self.release_evidence_id,
            self.release_evidence_digest,
            self.output_release_decision_id,
            self.output_release_decision_digest,
            self.disclosure_envelope_digest,
            self.tenant_id,
            self.principal_id,
            self.action,
            self.purpose,
            self.current_authorization_scope_fingerprint,
            self.current_authorization_revision_digest,
            self.release_currentness_snapshot_id,
            self.release_currentness_snapshot_digest,
            self.result,
            self.disposition,
            self.created_at,
        )
        if self.release_currentness_revision <= 0:
            raise ValueError("release-currentness revision must be positive")
        _require_canonical(
            self.released_occurrence_ids,
            label="released occurrence IDs",
        )
        _require_canonical(self.safe_reason_codes, label="safe reason codes")
        releases = self.result == "PASS" and self.disposition == "RELEASE"
        if releases:
            if not self.released_occurrence_ids:
                raise ValueError("RELEASE requires exact released occurrence IDs")
            if not self.response_intent_id:
                raise ValueError("RELEASE requires an atomically bound response intent")
            if not self.authorized_destination or not self.dispatch_idempotency_key:
                raise ValueError("RELEASE requires an authorized destination and key")
            if self.response_dispatch_state is not ResponseIntentState.PENDING:
                raise ValueError("newly committed RELEASE intent must start PENDING")
        elif self.response_intent_id is not None:
            raise ValueError("blocked or abstained output cannot create a response intent")
        elif (
            self.authorized_destination is not None
            or self.dispatch_idempotency_key is not None
        ):
            raise ValueError("non-release output cannot bind dispatch authority")
        elif self.response_dispatch_state is not ResponseIntentState.NOT_ATTEMPTED:
            raise ValueError("non-release output dispatch must remain NOT_ATTEMPTED")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RecoveryAndIncidentRecord:
    """One append-only dispatch/recovery observation."""

    record_id: str
    response_intent_id: str
    previous_record_id: str | None
    transport_attempt_id: str
    dispatch_idempotency_key: str
    observation: DispatchObservation
    safe_reason_code: str
    observed_at: str
    evidence_digests: tuple[str, ...]
    provider_message_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(
            self.record_id,
            self.response_intent_id,
            self.transport_attempt_id,
            self.dispatch_idempotency_key,
            self.safe_reason_code,
            self.observed_at,
        )
        if self.previous_record_id is not None and not self.previous_record_id.strip():
            raise ValueError("previous record ID must be absent or non-empty")
        _require_canonical(self.evidence_digests, label="recovery evidence digests")
        if not self.evidence_digests:
            raise ValueError("recovery observations require content-safe evidence")
        if self.observation in {
            DispatchObservation.ACCEPTED,
            DispatchObservation.DELIVERED,
            DispatchObservation.DUPLICATE_RECEIPT,
        } and not self.provider_message_id:
            raise ValueError("destination acceptance/receipt requires a message ID")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class CapstoneEvaluationDecision:
    """L2 hard-gate decision; production boundaries remain independently scoped."""

    decision_id: str
    execution_id: str
    normal_quality: CapstoneResult
    security_defense: CapstoneResult
    failure_recovery: CapstoneResult
    evidence_replay: CapstoneResult
    external_real_boundary: CapstoneResult
    hard_gates: tuple[tuple[str, CapstoneResult], ...]
    evaluated_artifact_digests: tuple[str, ...]
    overall_hard_gate: CapstoneResult
    evidence_level: str
    production_readiness: str
    safe_reason_codes: tuple[str, ...]
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.decision_id,
            self.execution_id,
            self.evidence_level,
            self.production_readiness,
            self.observed_at,
        )
        names = tuple(name for name, _ in self.hard_gates)
        _require_canonical(names, label="hard-gate names")
        _require_canonical(
            self.evaluated_artifact_digests,
            label="evaluated artifact digests",
        )
        _require_canonical(self.safe_reason_codes, label="evaluation reason codes")
        if not self.hard_gates or not self.evaluated_artifact_digests:
            raise ValueError("capstone evaluation requires hard gates")
        required = (
            self.normal_quality,
            self.security_defense,
            self.failure_recovery,
            *(result for _, result in self.hard_gates),
        )
        expected = self._aggregate(required)
        if self.overall_hard_gate is not expected:
            raise ValueError("overall hard gate does not match required evidence")
        if self.external_real_boundary is CapstoneResult.PASS:
            raise ValueError("Day106 L2 cannot claim an external-real PASS")

    @staticmethod
    def _aggregate(results: tuple[CapstoneResult, ...]) -> CapstoneResult:
        if CapstoneResult.FAIL in results:
            return CapstoneResult.FAIL
        if CapstoneResult.INCONCLUSIVE in results:
            return CapstoneResult.INCONCLUSIVE
        if CapstoneResult.NOT_RUN in results:
            return CapstoneResult.NOT_RUN
        return CapstoneResult.PASS

    @property
    def digest(self) -> str:
        payload = asdict(self)
        payload["hard_gates"] = tuple(
            (name, result.value) for name, result in self.hard_gates
        )
        return stable_hash(payload)


@dataclass(frozen=True)
class EndToEndExecutionManifest:
    """Sealed content-safe identity spine for one deterministic Day106 run."""

    execution_id: str
    repository_revision: str
    config_fingerprint: str
    runtime_boundary: str
    evidence_level: str
    exact_command: str
    started_at: str
    completed_at: str
    lineage_digests: tuple[str, ...]
    request_binding_digests: tuple[str, ...]
    retrieval_context_receipt_digests: tuple[str, ...]
    answer_release_record_digests: tuple[str, ...]
    response_intent_digests: tuple[str, ...]
    recovery_record_digests: tuple[str, ...]
    release_currentness_snapshot_digests: tuple[str, ...]
    prerequisite_evidence_digests: tuple[str, ...]
    evaluation_decision_digest: str
    executed_checks: tuple[str, ...]
    not_run: tuple[str, ...]
    raw_prompt_logged: bool
    protected_chunk_logged: bool
    answer_candidate_text_logged: bool
    secret_logged: bool
    raw_vector_logged: bool

    def __post_init__(self) -> None:
        _require_non_empty(
            self.execution_id,
            self.repository_revision,
            self.config_fingerprint,
            self.runtime_boundary,
            self.evidence_level,
            self.exact_command,
            self.started_at,
            self.completed_at,
            self.evaluation_decision_digest,
        )
        for values, label in (
            (self.lineage_digests, "lineage digests"),
            (self.request_binding_digests, "request binding digests"),
            (self.retrieval_context_receipt_digests, "receipt digests"),
            (self.answer_release_record_digests, "release record digests"),
            (self.response_intent_digests, "response intent digests"),
            (self.recovery_record_digests, "recovery record digests"),
            (
                self.release_currentness_snapshot_digests,
                "release-currentness snapshot digests",
            ),
            (self.prerequisite_evidence_digests, "prerequisite evidence digests"),
            (self.executed_checks, "executed checks"),
            (self.not_run, "NOT_RUN boundaries"),
        ):
            _require_canonical(values, label=label)
        if not all(
            (
                self.lineage_digests,
                self.request_binding_digests,
                self.retrieval_context_receipt_digests,
                self.answer_release_record_digests,
                self.response_intent_digests,
                self.release_currentness_snapshot_digests,
                self.prerequisite_evidence_digests,
                self.executed_checks,
                self.not_run,
            )
        ):
            raise ValueError("execution manifest requires complete evidence bindings")
        if any(
            (
                self.raw_prompt_logged,
                self.protected_chunk_logged,
                self.answer_candidate_text_logged,
                self.secret_logged,
                self.raw_vector_logged,
            )
        ):
            raise ValueError("protected content cannot enter the execution manifest")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))
