"""Runnable Day106 deterministic Production RAG capstone checkpoint.

The example composes the public Day100-Day105 runtime seams around one aligned
refund-domain identity spine.  Day95-Day99 committed artifacts are represented
as immutable, content-safe lineage receipts because a serving request does not
rerun ingestion, chunking, or embedding.  Their saved reports remain explicit
prerequisite evidence and are never promoted to Day106 end-to-end evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import json
from pathlib import Path
from typing import Any, Protocol

from examples.day106_capstone_support import (
    DAY101_EXECUTION_RECEIPT_AUTHORITY,
    CanonicalClaim,
    CanonicalGroundingRun,
    CanonicalRetrievalRun,
    TENANT_ID,
    PRINCIPAL_ID,
    application_channel_claim,
    build_canonical_day101_fixture,
    execute_day101_query,
    execute_grounding_from_day101,
    refund_window_claim,
)
from rag_capstone_contracts import (
    AnswerReleaseRecord,
    CapstoneRequestBinding,
    CapstoneResult,
    DispatchObservation,
    RecoveryAndIncidentRecord,
    ReleaseCurrentnessSnapshot,
    ResponseIntent,
    ResponseIntentState,
    RetrievalAndContextReceipt,
    SourceToOccurrenceLineage,
)
from rag_capstone_orchestrator import (
    CapstoneComposer,
    InMemoryReleaseCurrentnessAuthority,
    InMemoryResponseLedger,
    seal_execution,
)
from rag_authorized_retriever import (
    InMemoryRetrievalAuthorization,
    RetrievalAuthorizationUnavailable,
    classroom_authorization_revisions,
)
from rag_chunking_contracts import stable_hash
from rag_grounding_adapters import AnswerProvider, EvidenceVerifier
from rag_grounding_contracts import Day102Outcome, GroundingContract
from rag_index_lifecycle_committer import (
    IndexLifecycleCommitter,
    InMemoryIndexLifecycleStore,
    ReadyOutcome,
)
from rag_index_lifecycle_contracts import (
    ActivePointer,
    BuildSnapshot,
    EvaluationDecision,
    EvaluationEvidence,
    EvaluationRuler,
    ImmutableBinding,
)
from rag_index_lifecycle_orchestrator import (
    BuildValidationOutcome,
    DeterministicSealedIndexProvider,
    IndexLifecycleOrchestrator,
    IndexedOccurrence,
)
from rag_index_read_views import IndexReadViewManager, ReadViewOutcome
from rag_security_contracts import (
    AnswerCandidate,
    ContextAssemblyManifest,
    DisclosureEnvelope,
    ModelInvocationEnvelope,
    OccurrenceSecurityIdentity,
    OutputReleaseDecision,
    ProposedCitation,
    ReleaseEvidence,
    RequestSecurityBinding,
    RetrievalBundle as SecurityRetrievalBundle,
    RetrievedOccurrence,
    SecurityDisposition,
    SecurityPolicyIdentity,
    SecurityResult,
)
from rag_security_pipeline import RagSecurityPipeline


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_LEVEL = "EXECUTED_LOCAL_RUNTIME"
RUNTIME_BOUNDARY = "IN_PROCESS_DETERMINISTIC_ADAPTERS"
PRODUCTION_READINESS = "MORE_EVIDENCE_NEEDED"
POINTER_NAME = "refund-serving"
EXECUTION_ID = "day106-refund-capstone-l2-v1"
STARTED_AT = "2026-11-23T09:00:00+08:00"
COMPLETED_AT = "2026-11-23T09:10:00+08:00"
EXACT_COMMAND = (
    "PYTHONPATH=src:. python examples/day106_production_rag_capstone.py"
)


@dataclass(frozen=True)
class LifecycleGeneration:
    snapshot: BuildSnapshot
    manifest: Any
    artifact: Any


@dataclass(frozen=True)
class BoundAttempt:
    capstone: CapstoneRequestBinding
    security: RequestSecurityBinding


@dataclass(frozen=True)
class GroundingProviderBuildContext:
    """Exact application-owned spine available to a provider factory."""

    query_id: str
    request_binding: CapstoneRequestBinding
    retrieval_bundle: SecurityRetrievalBundle
    context_manifest: ContextAssemblyManifest
    invocation_envelope: ModelInvocationEnvelope
    retrieval_and_context_receipt: RetrievalAndContextReceipt
    retrieval_run: CanonicalRetrievalRun
    grounding_contract: GroundingContract

    def __post_init__(self) -> None:
        if (
            self.context_manifest.retrieval_bundle_digest
            != self.retrieval_bundle.digest
        ):
            raise ValueError("provider context RetrievalBundle identity drift")
        if (
            self.invocation_envelope.context_manifest_digest
            != self.context_manifest.digest
        ):
            raise ValueError("provider context manifest identity drift")
        if self.retrieval_run.day101_response.handoff_digest is None:
            raise ValueError("provider context requires a Day101 handoff")
        if (
            self.context_manifest.request_binding_fingerprint
            != self.request_binding.security_binding_fingerprint
            or self.invocation_envelope.request_binding_fingerprint
            != self.request_binding.security_binding_fingerprint
        ):
            raise ValueError("provider context request binding drift")
        if (
            self.retrieval_and_context_receipt.request_binding_digest
            != self.request_binding.digest
            or self.retrieval_and_context_receipt.retrieval_bundle_digest
            != self.retrieval_bundle.digest
            or self.retrieval_and_context_receipt.context_manifest_digest
            != self.context_manifest.digest
        ):
            raise ValueError("provider context durable receipt drift")

    @property
    def provider_invocation_attempt_id(self) -> str:
        return stable_hash((
            "DAY106_PROVIDER_INVOCATION_ATTEMPT_V1",
            self.request_binding.request_attempt_id,
            self.retrieval_and_context_receipt.digest,
            self.invocation_envelope.digest,
        ))


@dataclass(frozen=True)
class ProviderInvocationReservation:
    """Content-safe proof that MI + provider attempt were durably reserved."""

    reservation_id: str
    provider_invocation_attempt_id: str
    request_binding_digest: str
    retrieval_and_context_receipt_digest: str
    invocation_envelope_digest: str

    def __post_init__(self) -> None:
        if not all((
            self.reservation_id,
            self.provider_invocation_attempt_id,
            self.request_binding_digest,
            self.retrieval_and_context_receipt_digest,
            self.invocation_envelope_digest,
        )):
            raise ValueError("complete provider reservation binding is required")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


class ProviderInvocationReserver(Protocol):
    """Application callback that must durably reserve before any send."""

    def __call__(
        self,
        context: GroundingProviderBuildContext,
    ) -> ProviderInvocationReservation:
        """Persist the MI and attempt, then return their exact reservation."""


class ExternalAnswerProviderFactory(Protocol):
    """Build a provider only after a valid durable reservation exists."""

    def __call__(
        self,
        context: GroundingProviderBuildContext,
        reservation: ProviderInvocationReservation,
    ) -> AnswerProvider:
        """Return a provider bound to the reserved exact identity spine."""


@dataclass(frozen=True)
class ExternalGroundingRuntime:
    """Optional factory seam; omission preserves the deterministic L2 path."""

    grounding_contract: GroundingContract
    model_id: str
    model_config_digest: str
    reserve_provider_invocation: ProviderInvocationReserver
    answer_provider_factory: ExternalAnswerProviderFactory
    evidence_verifier: EvidenceVerifier | None = None

    def __post_init__(self) -> None:
        if not self.model_id or not self.model_config_digest:
            raise ValueError("external model identity and config are required")
        if self.grounding_contract.immutable_generator_revision != self.model_id:
            raise ValueError("external model and grounding contract must agree")


@dataclass(frozen=True)
class PreparedQuery:
    bound: BoundAttempt
    authorization_authority: InMemoryRetrievalAuthorization
    release_currentness_authority: InMemoryReleaseCurrentnessAuthority
    grounding: CanonicalGroundingRun
    receipt: RetrievalAndContextReceipt
    context: ContextAssemblyManifest
    disclosure: DisclosureEnvelope
    invocation: ModelInvocationEnvelope
    provider_invocation_reservation: ProviderInvocationReservation | None
    candidate: AnswerCandidate
    claim_ids: tuple[str, ...]
    occurrence_ids: tuple[str, ...]
    citation_keys: tuple[str, ...]
    grounding_evidence_digests: tuple[str, ...]


@dataclass(frozen=True)
class DecidedQuery:
    prepared: PreparedQuery
    evidence: ReleaseEvidence
    decision: OutputReleaseDecision
    record: AnswerReleaseRecord


def _load_prerequisite_evidence() -> dict[str, str]:
    """Bind exact saved prerequisites without claiming they reran here."""

    names = (
        "day95-validation.json",
        "day96-validation.json",
        "day97-validation.json",
        "day98-validation.json",
        "day99-validation.json",
        "day100-validation.json",
        "day101-validation.json",
        "day102-validation.json",
        "day103-rag-evaluation-report.json",
        "day104-index-lifecycle-report.json",
        "day105-rag-security-report.json",
        "day104-l3-integration-report.json",
        "day105-l3-integration-report.json",
    )
    result: dict[str, str] = {}
    for name in names:
        payload = json.loads((ROOT / "evidence" / name).read_text(encoding="utf-8"))
        result[name] = stable_hash(payload)
    return result


def _lineages(
    prerequisite: dict[str, str],
) -> dict[str, SourceToOccurrenceLineage]:
    upstream = tuple(
        sorted(
            prerequisite[f"day{day}-validation.json"]
            for day in range(95, 100)
        )
    )
    definitions = {
        "A@v1": "The refund window is 14 days for unopened goods.",
        "C@v1": "The refund application channel is online customer service.",
    }
    return {
        occurrence_id: SourceToOccurrenceLineage(
            lineage_id=f"lineage-{occurrence_id}",
            tenant_id=TENANT_ID,
            resource_id=f"refund-resource-{occurrence_id[0]}",
            source_artifact_id=f"source-{occurrence_id[0]}",
            source_version="v1",
            source_artifact_digest=stable_hash(
                ("SOURCE_ARTIFACT", occurrence_id, text)
            ),
            parsed_artifact_id=f"parsed-{occurrence_id[0]}-v1",
            parsed_artifact_digest=stable_hash(
                ("PARSED_ARTIFACT", occurrence_id, text)
            ),
            parser_contract_version="parser-v1",
            chunk_set_id="refund-chunk-set-v1",
            chunk_set_digest=stable_hash(
                ("CHUNK_SET", "refund-chunk-set-v1", occurrence_id)
            ),
            chunker_contract_version="chunker-v1",
            occurrence_id=occurrence_id,
            content_digest=stable_hash(text),
            metadata_digest=stable_hash(
                ("METADATA", occurrence_id, "refund-domain")
            ),
            metadata_version="metadata-v1",
            provenance_revision="PROV-R1",
            embedding_set_id="refund-embedding-set-v1",
            embedding_record_id=f"embedding-{occurrence_id}",
            embedding_contract_fingerprint="sha256:day98-document-contract",
            upstream_evidence_digests=upstream,
        )
        for occurrence_id, text in definitions.items()
    }


def _binding(identity: str, digest_input: object) -> ImmutableBinding:
    return ImmutableBinding(identity, stable_hash(digest_input))


def _snapshot(
    *,
    snapshot_id: str,
    authorization_revision_digest: str,
    included: tuple[SourceToOccurrenceLineage, ...],
    source_snapshot_digest: str,
) -> BuildSnapshot:
    if not included:
        raise ValueError("build snapshot requires eligible occurrence lineage")
    embedding_contracts = {
        item.embedding_contract_fingerprint for item in included
    }
    if len(embedding_contracts) != 1:
        raise ValueError("build snapshot requires one embedding contract")
    return BuildSnapshot(
        build_snapshot_id=snapshot_id,
        scope_id="refund-rag",
        source_snapshot=ImmutableBinding("S1", source_snapshot_digest),
        authorization_snapshot=ImmutableBinding(
            authorization_revision_digest,
            stable_hash(
                (
                    authorization_revision_digest,
                    authorization_revision_digest,
                )
            ),
        ),
        embedding_contract=ImmutableBinding(
            included[0].embedding_contract_fingerprint,
            stable_hash(included[0].embedding_contract_fingerprint),
        ),
        index_schema=_binding("IS1", "day106-index-schema-v1"),
        source_watermark="W1",
        deletion_snapshot=_binding("D1", ("TOMBSTONED", "B@v1")),
    )


def _ruler(prerequisite: dict[str, str]) -> EvaluationRuler:
    return EvaluationRuler(
        dataset_fingerprint=stable_hash("day106-refund-Q1-Q2-Q3-v1"),
        evaluator_fingerprint=stable_hash("day103-evaluator-v1"),
        policy_fingerprint=stable_hash(
            ("day106-hard-gate-policy-v1", prerequisite["day103-rag-evaluation-report.json"])
        ),
    )


def _indexed_occurrences(
    lineages: tuple[SourceToOccurrenceLineage, ...],
) -> tuple[IndexedOccurrence, ...]:
    return tuple(
        IndexedOccurrence(
            occurrence_id=item.occurrence_id,
            content_digest=item.content_digest,
            metadata_digest=item.metadata_digest,
            provenance_digest=stable_hash(item.provenance_revision),
        )
        for item in sorted(lineages, key=lambda value: value.occurrence_id)
    )


def _evaluation_evidence(
    *,
    generation_id: str,
    snapshot: BuildSnapshot,
    manifest_digest: str,
    ruler: EvaluationRuler,
    prerequisite: dict[str, str],
) -> EvaluationEvidence:
    return EvaluationEvidence(
        evidence_id=f"day106-evaluation-{generation_id}",
        generation_id=generation_id,
        build_snapshot_fingerprint=snapshot.fingerprint,
        manifest_digest=manifest_digest,
        dataset_fingerprint=ruler.dataset_fingerprint,
        evaluator_fingerprint=ruler.evaluator_fingerprint,
        policy_fingerprint=ruler.policy_fingerprint,
        evaluation_report_checksum=stable_hash(
            (
                "DAY106_GENERATION_EVALUATION",
                generation_id,
                manifest_digest,
                prerequisite["day103-rag-evaluation-report.json"],
            )
        ),
        evidence_level=EVIDENCE_LEVEL,
        decision=EvaluationDecision.PASS,
        observed_at=STARTED_AT,
    )


def _build_generation(
    *,
    generation_id: str,
    snapshot: BuildSnapshot,
    included: tuple[SourceToOccurrenceLineage, ...],
    provider_fence: int,
    ruler: EvaluationRuler,
    prerequisite: dict[str, str],
    store: InMemoryIndexLifecycleStore,
    committer: IndexLifecycleCommitter,
    orchestrator: IndexLifecycleOrchestrator,
) -> LifecycleGeneration:
    store.set_current_build_snapshot(snapshot)
    validation = orchestrator.build_and_validate(
        generation_id=generation_id,
        build_snapshot=snapshot,
        evaluation_ruler=ruler,
        expected_occurrences=_indexed_occurrences(included),
        expected_absent_occurrence_ids=("B@v1",),
        physical_namespace=f"refund/{generation_id}",
        provider_write_fence=provider_fence,
        validation_id=f"day106-validation-{generation_id}",
        validator_version="day106-validator-v1",
        observed_at=STARTED_AT,
    )
    if (
        validation.outcome is not BuildValidationOutcome.VALIDATING
        or validation.manifest is None
    ):
        raise RuntimeError(f"{generation_id} validation failed: {validation.safe_reason}")
    evaluation = _evaluation_evidence(
        generation_id=generation_id,
        snapshot=snapshot,
        manifest_digest=validation.manifest.digest,
        ruler=ruler,
        prerequisite=prerequisite,
    )
    committer.record_evaluation(evaluation)
    lifecycle = store.read_lifecycle(generation_id)
    if lifecycle is None:
        raise RuntimeError("generation lifecycle was not registered")
    ready = committer.mark_ready(
        generation_id=generation_id,
        expected_state_version=lifecycle.state_version,
        validation_record_id=f"day106-validation-{generation_id}",
        evaluation_evidence_id=evaluation.evidence_id,
    )
    if ready.outcome is not ReadyOutcome.READY or ready.artifact is None:
        raise RuntimeError(f"{generation_id} READY failed: {ready.safe_reason}")
    return LifecycleGeneration(snapshot, validation.manifest, ready.artifact)


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
        adversarial_set_digest=stable_hash("day106-adversarial-set-v1"),
    )


def _release_currentness_snapshot(
    *,
    snapshot_id: str,
    revision: int,
    generation: LifecycleGeneration,
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
        provenance_revision="PROV-R1",
        tombstone_revision=generation.snapshot.deletion_snapshot.identity,
        content_security_snapshot_digest=stable_hash(
            (generation.artifact.fingerprint, policy.fingerprint)
        ),
        security_policy_fingerprint=policy.fingerprint,
        dlp_result=SecurityResult.PASS.value,
        metadata_stripping_result=SecurityResult.PASS.value,
        destination_result=SecurityResult.PASS.value,
        evidence_digests=(
            stable_hash(
                (
                    snapshot_id,
                    generation.artifact.generation_id,
                    generation.artifact.fingerprint,
                    eligible_occurrence_ids,
                    "CURRENT_RELEASE_FACTS",
                )
            ),
        ),
    )


def _occurrence_identity(
    lineage: SourceToOccurrenceLineage,
    *,
    authorization_revision: str,
    policy: SecurityPolicyIdentity,
) -> OccurrenceSecurityIdentity:
    return OccurrenceSecurityIdentity(
        occurrence_id=lineage.occurrence_id,
        source_id=lineage.source_artifact_id,
        source_version=lineage.source_version,
        tenant_id=lineage.tenant_id,
        resource_id=lineage.resource_id,
        content_digest=lineage.content_digest,
        metadata_digest=lineage.metadata_digest,
        metadata_version=lineage.metadata_version,
        authorization_revision=authorization_revision,
        provenance_revision=lineage.provenance_revision,
        parser_version=policy.parser_version,
        scanner_version=policy.scanner_version,
        detector_version=policy.detector_version,
        security_policy_version=policy.security_policy_version,
    )


def _bind_attempt(
    *,
    attempt_id: str,
    pointer: ActivePointer,
    generation: LifecycleGeneration,
    serving_fixture: Any,
    lineages: tuple[SourceToOccurrenceLineage, ...],
    policy: SecurityPolicyIdentity,
    views: IndexReadViewManager,
    observed_at: str,
) -> BoundAttempt:
    acquired = views.acquire(
        view_id=f"read-view-{attempt_id}",
        pointer_name=pointer.pointer_name,
        expected_generation_id=pointer.generation_id,
        expected_pointer_revision=pointer.revision,
        owner_id=attempt_id,
        now=observed_at,
        lease_expires_at="2026-11-23T10:00:00+08:00",
    )
    if acquired.outcome is not ReadViewOutcome.ACQUIRED or acquired.view is None:
        raise RuntimeError(f"ReadView acquire failed: {acquired.safe_reason}")
    view = acquired.view
    manifest_entries = tuple(
        (
            item.occurrence_id,
            _occurrence_identity(
                item,
                authorization_revision=(
                    generation.snapshot.authorization_snapshot.identity
                ),
                policy=policy,
            ).manifest_entry_digest,
        )
        for item in sorted(lineages, key=lambda value: value.occurrence_id)
    )
    security = RequestSecurityBinding(
        request_id=attempt_id,
        principal_id=PRINCIPAL_ID,
        tenant_id=TENANT_ID,
        purpose=serving_fixture.day100.scope.purpose,
        audience="current-user",
        generation_id=generation.artifact.generation_id,
        generation_artifact_digest=generation.artifact.fingerprint,
        build_snapshot_fingerprint=generation.snapshot.fingerprint,
        # Day105's projection digest is intentionally distinct from the
        # Day104 GenerationManifest digest carried by CapstoneRequestBinding.
        generation_manifest_digest=stable_hash(manifest_entries),
        manifest_entries=manifest_entries,
        provider_checkpoint_digest=stable_hash(
            (generation.artifact.physical_namespace, "SEALED")
        ),
        provider_write_fence=pointer.revision,
        validation_record_digest=generation.artifact.validation_record_digest,
        day103_evaluation_report_checksum=(
            generation.artifact.evaluation_report_digest
        ),
        active_pointer_digest=stable_hash(asdict(pointer)),
        pointer_revision=pointer.revision,
        read_view_id=view.view_id,
        read_view_fence=view.fencing_token,
        read_view_status=view.status.value,
        read_view_unexpired=True,
        read_view_owner_id=view.owner_id,
        read_view_validation_digest=stable_hash(asdict(view)),
        authorization_revision=(
            generation.snapshot.authorization_snapshot.identity
        ),
        provenance_revision="PROV-R1",
        tombstone_revision=generation.snapshot.deletion_snapshot.identity,
        content_security_snapshot_digest=stable_hash(
            (generation.artifact.fingerprint, policy.fingerprint)
        ),
        security_evidence_digests=(
            stable_hash(
                (
                    generation.artifact.generation_id,
                    generation.artifact.fingerprint,
                    "CONTENT_SECURITY_EVIDENCE",
                )
            ),
        ),
        policy=policy,
    )
    capstone = CapstoneComposer.bind_request(
        request_attempt_id=attempt_id,
        pointer=pointer,
        read_view=view,
        build_snapshot=generation.snapshot,
        manifest=generation.manifest,
        artifact=generation.artifact,
        security_binding=security,
        selected_retrieval_bundle=serving_fixture.day100.bundle,
        retrieval_authorization_scope=serving_fixture.day100.scope,
        lineages=lineages,
        created_at=observed_at,
    )
    return BoundAttempt(capstone, security)


def _facts_for_occurrence(occurrence_id: str) -> tuple[str, ...]:
    mapping = {
        "A@v1": ("claim:refund-window",),
        "C@v1": ("claim:application-channel",),
    }
    return mapping.get(occurrence_id, ())


def _prepare_query(
    *,
    query_id: str,
    bound: BoundAttempt,
    serving_fixture: Any,
    release_currentness_authority: InMemoryReleaseCurrentnessAuthority,
    retrieval_run: CanonicalRetrievalRun,
    claims: tuple[CanonicalClaim, ...],
    lineages: dict[str, SourceToOccurrenceLineage],
    policy: SecurityPolicyIdentity,
    observed_at: str,
    external_grounding: ExternalGroundingRuntime | None = None,
) -> PreparedQuery:
    def read_current_authorization():
        try:
            scope = serving_fixture.day100.authorization.read(
                tenant_id=bound.capstone.tenant_id,
                principal_subject=bound.capstone.principal_id,
                action=bound.capstone.action,
                purpose=bound.capstone.purpose,
            )
        except RetrievalAuthorizationUnavailable as exc:
            raise RuntimeError("CURRENT_AUTHORIZATION_UNAVAILABLE") from exc
        if scope is None:
            raise RuntimeError("CURRENT_AUTHORIZATION_NOT_FOUND")
        return scope

    required_occurrence_ids = tuple(
        sorted(
            {
                occurrence_id
                for claim in claims
                for occurrence_id in claim.occurrence_ids
            }
        )
    )
    day101_occurrence_ids = {
        hit.identity.occurrence_id
        for hit in retrieval_run.day101_response.hits
    }
    if not set(required_occurrence_ids).issubset(day101_occurrence_ids):
        raise RuntimeError("REQUIRED_EVIDENCE_UNAVAILABLE_BEFORE_PROMPT")
    authorization_before_security = read_current_authorization()
    authorized_before_security = set(
        authorization_before_security.allowed_occurrence_ids
    )
    candidates = tuple(
        RetrievedOccurrence(
            identity=_occurrence_identity(
                lineages[hit.identity.occurrence_id],
                authorization_revision=bound.security.authorization_revision,
                policy=policy,
            ),
            fact_ids=_facts_for_occurrence(hit.identity.occurrence_id),
            attack_tags=(),
            currently_authorized=(
                hit.identity.occurrence_id in authorized_before_security
            ),
            tombstoned=False,
            quarantined=False,
            content_security_result=SecurityResult.PASS,
        )
        for hit in retrieval_run.day101_response.hits
    )
    occurrence_ids = required_occurrence_ids
    retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id=f"retrieval-security-{query_id}",
        binding=bound.security,
        candidates=candidates,
        least_context_occurrence_ids=occurrence_ids,
        observed_at=observed_at,
    )
    bundle_security = RagSecurityPipeline.analyze_bundle(
        decision_id=f"bundle-security-{query_id}",
        binding=bound.security,
        retrieval_decision=retrieval,
        candidates=candidates,
    )
    bundle = RagSecurityPipeline.build_retrieval_bundle(
        bundle_id=f"retrieval-bundle-{query_id}",
        binding=bound.security,
        retrieval_decision=retrieval,
        bundle_decision=bundle_security,
        candidates=candidates,
        created_at=observed_at,
    )
    authorization_before_context = read_current_authorization()
    if (
        authorization_before_context.fingerprint
        != authorization_before_security.fingerprint
        or not set(occurrence_ids).issubset(
            authorization_before_context.allowed_occurrence_ids
        )
    ):
        raise RuntimeError("AUTHORIZATION_CHANGED_BEFORE_CONTEXT_ASSEMBLY")
    context = RagSecurityPipeline.assemble_context(
        manifest_id=f"context-manifest-{query_id}",
        binding=bound.security,
        bundle=bundle,
        included_occurrence_ids=occurrence_ids,
        context_budget=len(occurrence_ids),
        actual_context_units=len(occurrence_ids),
        envelope_schema_version="untrusted-evidence-v1",
        serialization_version="json-escaped-v1",
        projection_version="least-fields-v1",
        structured_untrusted_data_digest=stable_hash(
            (
                retrieval_run.day101_response.handoff_digest,
                occurrence_ids,
                "UNTRUSTED_DATA",
            )
        ),
    )
    claim_ids = tuple(sorted(item.claim_id for item in claims))
    disclosure = DisclosureEnvelope(
        envelope_id=f"disclosure-{query_id}",
        request_binding_fingerprint=bound.security.fingerprint,
        purpose=bound.security.purpose,
        audience=bound.security.audience,
        allowed_fields=claim_ids,
        destination="current-chat",
        disclosure_budget=len(claim_ids),
        authorization_revision=bound.security.authorization_revision,
        output_policy_version=policy.output_policy_version,
    )
    invocation = RagSecurityPipeline.build_model_envelope(
        envelope_id=f"model-invocation-{query_id}",
        binding=bound.security,
        context_manifest=context,
        disclosure=disclosure,
        system_policy_digest=stable_hash("day106-system-policy-no-secrets"),
        model_id=(
            external_grounding.model_id
            if external_grounding
            else "day102-deterministic-answer-provider"
        ),
        model_config_digest=(
            external_grounding.model_config_digest
            if external_grounding
            else stable_hash("day102-grounding-contract-v1")
        ),
    )
    authorization_before_model = read_current_authorization()
    if (
        authorization_before_model.fingerprint
        != authorization_before_context.fingerprint
        or not set(context.included_occurrence_ids).issubset(
            authorization_before_model.allowed_occurrence_ids
        )
    ):
        raise RuntimeError("AUTHORIZATION_CHANGED_BEFORE_MODEL_INVOCATION")
    if retrieval_run.execution_receipt is None:
        raise RuntimeError("DAY101_EXECUTION_RECEIPT_UNAVAILABLE")
    receipt = CapstoneComposer.record_retrieval_and_context(
        receipt_id=f"retrieval-context-receipt-{query_id}",
        binding=bound.capstone,
        retrieval_request=retrieval_run.retrieval_request,
        day101_response=retrieval_run.day101_response,
        day101_execution_receipt=retrieval_run.execution_receipt,
        day101_receipt_authority=DAY101_EXECUTION_RECEIPT_AUTHORITY,
        retrieval_bundle=bundle,
        context_manifest=context,
        current_authorization_scope=authorization_before_model,
        created_at=observed_at,
    )
    # Only now, after the Day105 retrieval and context gates have passed, may
    # the deterministic Day102 generator/verifier execute.
    answer_provider = None
    grounding_contract = None
    evidence_verifier = None
    provider_reservation = None
    if external_grounding is not None:
        grounding_contract = external_grounding.grounding_contract
        evidence_verifier = external_grounding.evidence_verifier
        provider_context = GroundingProviderBuildContext(
            query_id=query_id,
            request_binding=bound.capstone,
            retrieval_bundle=bundle,
            context_manifest=context,
            invocation_envelope=invocation,
            retrieval_and_context_receipt=receipt,
            retrieval_run=retrieval_run,
            grounding_contract=grounding_contract,
        )
        provider_reservation = (
            external_grounding.reserve_provider_invocation(provider_context)
        )
        expected_reservation = ProviderInvocationReservation(
            reservation_id=provider_reservation.reservation_id,
            provider_invocation_attempt_id=(
                provider_context.provider_invocation_attempt_id
            ),
            request_binding_digest=bound.capstone.digest,
            retrieval_and_context_receipt_digest=receipt.digest,
            invocation_envelope_digest=invocation.digest,
        )
        if provider_reservation != expected_reservation:
            raise ValueError("provider invocation reservation identity drift")
        answer_provider = external_grounding.answer_provider_factory(
            provider_context,
            provider_reservation,
        )
    grounding = execute_grounding_from_day101(
        serving_fixture,
        retrieval=retrieval_run,
        claims=claims,
        grounding_contract=grounding_contract,
        answer_provider=answer_provider,
        evidence_verifier=evidence_verifier,
    )
    if grounding.day102_response.outcome is not Day102Outcome.FULL:
        raise RuntimeError(
            f"{query_id} grounding was not FULL: "
            f"{grounding.day102_response.safe_reason}"
        )
    proposed_citations = tuple(
        ProposedCitation(
            claim_id=claim.claim_id,
            occurrence_id=citation.source_identity.occurrence_id,
        )
        for claim in sorted(
            grounding.day102_response.released_claims,
            key=lambda value: value.claim_id,
        )
        for citation in sorted(
            claim.citations,
            key=lambda value: value.source_identity.occurrence_id,
        )
    )
    candidate = AnswerCandidate(
        candidate_id=f"answer-candidate-{query_id}",
        invocation_envelope_digest=invocation.digest,
        answer_digest=stable_hash(grounding.day102_response.answer_text),
        claim_ids=claim_ids,
        proposed_citations=proposed_citations,
        proposed_tool_calls=(),
        sensitive_markers=(),
        generated_at=observed_at,
    )
    citation_keys = tuple(
        sorted(
            f"{item.claim_id}:{item.occurrence_id}"
            for item in proposed_citations
        )
    )
    grounding_evidence = tuple(
        sorted(
            {
                grounding.grounding_audit_checksum,
                *((provider_reservation.digest,) if provider_reservation else ()),
                *(
                    claim.verification_digest
                    for claim in grounding.day102_response.released_claims
                    if claim.verification_digest is not None
                ),
            }
        )
    )
    grounded_occurrence_ids = tuple(
        sorted(
            {
                citation.source_identity.occurrence_id
                for claim in grounding.day102_response.released_claims
                for citation in claim.citations
            }
        )
    )
    if grounded_occurrence_ids != occurrence_ids:
        raise RuntimeError("DAY102_CONTEXT_IDENTITY_CONFLICT")
    if tuple(
        sorted(item.claim_id for item in grounding.day102_response.released_claims)
    ) != claim_ids:
        raise RuntimeError("DAY102_CLAIM_IDENTITY_CONFLICT")
    return PreparedQuery(
        bound=bound,
        authorization_authority=serving_fixture.day100.authorization,
        release_currentness_authority=release_currentness_authority,
        grounding=grounding,
        receipt=receipt,
        context=context,
        disclosure=disclosure,
        invocation=invocation,
        provider_invocation_reservation=provider_reservation,
        candidate=candidate,
        claim_ids=claim_ids,
        occurrence_ids=occurrence_ids,
        citation_keys=citation_keys,
        grounding_evidence_digests=grounding_evidence,
    )


def _decide_query(
    *,
    query_id: str,
    prepared: PreparedQuery,
    observed_at: str,
) -> DecidedQuery:
    try:
        current_scope = prepared.authorization_authority.read(
            tenant_id=prepared.bound.capstone.tenant_id,
            principal_subject=prepared.bound.capstone.principal_id,
            action=prepared.bound.capstone.action,
            purpose=prepared.bound.capstone.purpose,
        )
    except RetrievalAuthorizationUnavailable as exc:
        raise RuntimeError("CURRENT_AUTHORIZATION_UNAVAILABLE") from exc
    if current_scope is None:
        raise RuntimeError("CURRENT_AUTHORIZATION_NOT_FOUND")
    current_release = prepared.release_currentness_authority.read(
        tenant_id=prepared.bound.capstone.tenant_id,
        destination=prepared.disclosure.destination,
    )
    if current_release is None:
        raise RuntimeError("CURRENT_RELEASE_EVIDENCE_NOT_FOUND")
    current_authorization_revision_digest = stable_hash(
        asdict(current_scope.revisions)
    )
    currently_authorized_occurrence_ids = tuple(
        sorted(
            set(current_scope.allowed_occurrence_ids)
            .intersection(current_release.source_eligible_occurrence_ids)
            .difference(current_release.quarantined_occurrence_ids)
        )
    )
    evidence = ReleaseEvidence(
        evidence_id=f"release-evidence-{query_id}",
        candidate_digest=prepared.candidate.digest,
        observed_claim_ids=prepared.claim_ids,
        unclassified_claim_count=0,
        grounded_claim_ids=prepared.claim_ids,
        supported_citation_keys=prepared.citation_keys,
        current_authorization_revision=(
            current_authorization_revision_digest
        ),
        currently_authorized_occurrence_ids=tuple(
            sorted(currently_authorized_occurrence_ids)
        ),
        current_provenance_revision=current_release.provenance_revision,
        current_tombstone_revision=current_release.tombstone_revision,
        current_content_security_snapshot_digest=(
            current_release.content_security_snapshot_digest
        ),
        current_security_policy_fingerprint=(
            current_release.security_policy_fingerprint
        ),
        dlp_result=SecurityResult(current_release.dlp_result),
        metadata_stripping_result=SecurityResult(
            current_release.metadata_stripping_result
        ),
        destination_result=SecurityResult(current_release.destination_result),
        evidence_digests=tuple(
            sorted(
                {
                    *prepared.grounding_evidence_digests,
                    current_authorization_revision_digest,
                    current_release.digest,
                    *current_release.evidence_digests,
                }
            )
        ),
    )
    decision = RagSecurityPipeline.decide_output_release(
        decision_id=f"output-release-{query_id}",
        binding=prepared.bound.security,
        context_manifest=prepared.context,
        disclosure=prepared.disclosure,
        model_envelope=prepared.invocation,
        candidate=prepared.candidate,
        evidence=evidence,
        observed_at=observed_at,
    )
    record = CapstoneComposer.record_answer_release(
        record_id=f"answer-release-record-{query_id}",
        response_intent_id=f"response-intent-{query_id}",
        binding=prepared.bound.capstone,
        receipt=prepared.receipt,
        disclosure=prepared.disclosure,
        invocation=prepared.invocation,
        candidate=prepared.candidate,
        release_evidence=evidence,
        decision=decision,
        current_authorization_scope=current_scope,
        release_currentness_snapshot=current_release,
        dispatch_idempotency_key=f"dispatch-key-{query_id}",
        created_at=observed_at,
    )
    return DecidedQuery(prepared, evidence, decision, record)


def _attack_identity(
    occurrence_id: str,
    binding: RequestSecurityBinding,
    *,
    tenant_id: str = TENANT_ID,
) -> OccurrenceSecurityIdentity:
    return OccurrenceSecurityIdentity(
        occurrence_id=occurrence_id,
        source_id=f"attack-source-{occurrence_id}",
        source_version="v1",
        tenant_id=tenant_id,
        resource_id=f"attack-resource-{occurrence_id}",
        content_digest=stable_hash(("ATTACK_CONTENT", occurrence_id)),
        metadata_digest=stable_hash(("ATTACK_METADATA", occurrence_id)),
        metadata_version="metadata-v1",
        authorization_revision=binding.authorization_revision,
        provenance_revision=binding.provenance_revision,
        parser_version=binding.policy.parser_version,
        scanner_version=binding.policy.scanner_version,
        detector_version=binding.policy.detector_version,
        security_policy_version=binding.policy.security_policy_version,
    )


def _attack_binding(
    base: RequestSecurityBinding,
    *,
    case_id: str,
    occurrence_ids: tuple[str, ...],
    tenant_overrides: tuple[tuple[str, str], ...] = (),
) -> RequestSecurityBinding:
    provisional = replace(
        base,
        request_id=f"attack-lab-{case_id}",
        generation_id=f"G-{case_id}",
        generation_artifact_digest=stable_hash(("ATTACK_LAB", case_id)),
        build_snapshot_fingerprint=stable_hash(("ATTACK_BS", case_id)),
        provider_checkpoint_digest=stable_hash(("ATTACK_PROVIDER", case_id)),
        validation_record_digest=stable_hash(("ATTACK_VALIDATION", case_id)),
        day103_evaluation_report_checksum=stable_hash(
            ("ATTACK_EVALUATION", case_id)
        ),
        active_pointer_digest=stable_hash(("UNSELECTED_ATTACK_LAB", case_id)),
        read_view_id=f"attack-view-{case_id}",
        read_view_owner_id=f"attack-lab-{case_id}",
        read_view_validation_digest=stable_hash(("ATTACK_VIEW", case_id)),
        content_security_snapshot_digest=stable_hash(
            ("ATTACK_SECURITY", case_id)
        ),
        security_evidence_digests=(stable_hash(("ATTACK_EVIDENCE", case_id)),),
        manifest_entries=(("placeholder", stable_hash("placeholder")),),
        generation_manifest_digest=stable_hash(
            (("placeholder", stable_hash("placeholder")),)
        ),
    )
    tenant_by_id = dict(tenant_overrides)
    entries = tuple(
        (
            occurrence_id,
            _attack_identity(
                occurrence_id,
                provisional,
                tenant_id=tenant_by_id.get(occurrence_id, TENANT_ID),
            ).manifest_entry_digest,
        )
        for occurrence_id in sorted(occurrence_ids)
    )
    return replace(
        provisional,
        manifest_entries=entries,
        generation_manifest_digest=stable_hash(entries),
    )


def _security_negative_cases(
    base: RequestSecurityBinding,
) -> dict[str, dict[str, object]]:
    x_binding = _attack_binding(
        base,
        case_id="X",
        occurrence_ids=("X@v1",),
    )
    x = RetrievedOccurrence(
        identity=_attack_identity("X@v1", x_binding),
        fact_ids=(),
        attack_tags=("DOCUMENT_INSTRUCTION_OVERRIDE",),
    )
    x_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-X-retrieval",
        binding=x_binding,
        candidates=(x,),
        least_context_occurrence_ids=("X@v1",),
        observed_at=COMPLETED_AT,
    )
    x_bundle = RagSecurityPipeline.analyze_bundle(
        decision_id="negative-X-bundle",
        binding=x_binding,
        retrieval_decision=x_retrieval,
        candidates=(x,),
    )

    z_binding = _attack_binding(
        base,
        case_id="Z",
        occurrence_ids=("Z1@v1", "Z2@v1"),
    )
    z_candidates = (
        RetrievedOccurrence(
            identity=_attack_identity("Z1@v1", z_binding),
            fact_ids=(),
            attack_tags=("CHAIN_READ_NEXT",),
        ),
        RetrievedOccurrence(
            identity=_attack_identity("Z2@v1", z_binding),
            fact_ids=(),
            attack_tags=("CHAIN_EXECUTE_HIDDEN",),
        ),
    )
    z_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-Z-retrieval",
        binding=z_binding,
        candidates=z_candidates,
        least_context_occurrence_ids=("Z1@v1", "Z2@v1"),
        observed_at=COMPLETED_AT,
    )
    z_bundle = RagSecurityPipeline.analyze_bundle(
        decision_id="negative-Z-bundle",
        binding=z_binding,
        retrieval_decision=z_retrieval,
        candidates=z_candidates,
    )

    y_binding = _attack_binding(
        base,
        case_id="Y",
        occurrence_ids=("Y@v1",),
    )
    y = RetrievedOccurrence(
        identity=_attack_identity("Y@v1", y_binding),
        fact_ids=(),
        content_security_result=SecurityResult.INCONCLUSIVE,
    )
    y_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-Y-retrieval",
        binding=y_binding,
        candidates=(y,),
        least_context_occurrence_ids=("Y@v1",),
        observed_at=COMPLETED_AT,
    )

    b_binding = _attack_binding(
        base,
        case_id="B",
        occurrence_ids=("B@v1",),
    )
    b = RetrievedOccurrence(
        identity=_attack_identity("B@v1", b_binding),
        fact_ids=(),
        tombstoned=True,
    )
    b_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-B-retrieval",
        binding=b_binding,
        candidates=(b,),
        least_context_occurrence_ids=("B@v1",),
        observed_at=COMPLETED_AT,
    )
    t_binding = _attack_binding(
        base,
        case_id="T",
        occurrence_ids=("T@v1",),
        tenant_overrides=(("T@v1", "tenant-private"),),
    )
    t = RetrievedOccurrence(
        identity=_attack_identity(
            "T@v1",
            t_binding,
            tenant_id="tenant-private",
        ),
        fact_ids=(),
    )
    t_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-T-retrieval",
        binding=t_binding,
        candidates=(t,),
        least_context_occurrence_ids=("T@v1",),
        observed_at=COMPLETED_AT,
    )

    acl_binding = _attack_binding(
        base,
        case_id="ACL",
        occurrence_ids=("ACL@v1",),
    )
    acl_denied = RetrievedOccurrence(
        identity=_attack_identity("ACL@v1", acl_binding),
        fact_ids=(),
        currently_authorized=False,
    )
    acl_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-ACL-retrieval",
        binding=acl_binding,
        candidates=(acl_denied,),
        least_context_occurrence_ids=("ACL@v1",),
        observed_at=COMPLETED_AT,
    )

    provenance_binding = _attack_binding(
        base,
        case_id="PROVENANCE",
        occurrence_ids=("P@v1",),
    )
    stale_provenance = RetrievedOccurrence(
        identity=_attack_identity("P@v1", provenance_binding),
        fact_ids=(),
        provenance_current=False,
    )
    provenance_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="negative-PROVENANCE-retrieval",
        binding=provenance_binding,
        candidates=(stale_provenance,),
        least_context_occurrence_ids=("P@v1",),
        observed_at=COMPLETED_AT,
    )

    def denied_reason(decision: Any) -> str | None:
        return (
            decision.denied_occurrences[0].reason_code
            if decision.denied_occurrences
            else None
        )

    return {
        "X_document_injection": {
            "retrieval": x_retrieval.result.value,
            "bundle": x_bundle.result.value,
            "safe_reason_codes": list(x_bundle.reason_codes),
            "entered_prompt": False,
            "selected_for_serving": False,
        },
        "Y_detector_inconclusive": {
            "retrieval": y_retrieval.result.value,
            "entered_prompt": False,
            "selected_for_serving": False,
        },
        "Z_composed_attack": {
            "retrieval": z_retrieval.result.value,
            "bundle": z_bundle.result.value,
            "safe_reason_codes": list(z_bundle.reason_codes),
            "entered_prompt": False,
            "selected_for_serving": False,
        },
        "T_cross_tenant": {
            "retrieval": t_retrieval.result.value,
            "safe_reason_code": denied_reason(t_retrieval),
            "entered_prompt": False,
        },
        "B_tombstoned": {
            "retrieval": b_retrieval.result.value,
            "safe_reason_code": denied_reason(b_retrieval),
            "entered_prompt": False,
        },
        "ACL_current_authorization_denied": {
            "retrieval": acl_retrieval.result.value,
            "safe_reason_code": denied_reason(acl_retrieval),
            "entered_prompt": False,
        },
        "PROVENANCE_stale": {
            "retrieval": provenance_retrieval.result.value,
            "safe_reason_code": denied_reason(provenance_retrieval),
            "entered_prompt": False,
        },
    }


def _recovery_record(
    *,
    record_id: str,
    intent_id: str,
    previous_record_id: str | None,
    transport_attempt_id: str,
    idempotency_key: str,
    observation: DispatchObservation,
    safe_reason_code: str,
    observed_at: str,
    provider_message_id: str | None = None,
) -> RecoveryAndIncidentRecord:
    return RecoveryAndIncidentRecord(
        record_id=record_id,
        response_intent_id=intent_id,
        previous_record_id=previous_record_id,
        transport_attempt_id=transport_attempt_id,
        dispatch_idempotency_key=idempotency_key,
        observation=observation,
        safe_reason_code=safe_reason_code,
        observed_at=observed_at,
        evidence_digests=(
            stable_hash((record_id, observation.value, safe_reason_code)),
        ),
        provider_message_id=provider_message_id,
    )


def _deliver_immediately(
    *,
    ledger: InMemoryResponseLedger,
    decided: DecidedQuery,
    destination: str,
) -> None:
    key = decided.record.dispatch_idempotency_key
    if key is None:
        raise RuntimeError("released query is missing its dispatch key")
    intent = ledger.commit_decision_and_intent(
        release_record=decided.record,
        destination=destination,
        dispatch_idempotency_key=key,
    )
    if intent is None:
        raise RuntimeError("released query did not create a response intent")
    send = _recovery_record(
        record_id=f"{intent.intent_id}-send",
        intent_id=intent.intent_id,
        previous_record_id=None,
        transport_attempt_id=f"transport-{intent.intent_id}-1",
        idempotency_key=key,
        observation=DispatchObservation.SEND_STARTED,
        safe_reason_code="DISPATCH_STARTED",
        observed_at="2026-11-23T09:04:00+08:00",
    )
    ledger.append_observation(send)
    accepted = _recovery_record(
        record_id=f"{intent.intent_id}-accepted",
        intent_id=intent.intent_id,
        previous_record_id=send.record_id,
        transport_attempt_id=send.transport_attempt_id,
        idempotency_key=key,
        observation=DispatchObservation.ACCEPTED,
        safe_reason_code="DESTINATION_ACCEPTED",
        observed_at="2026-11-23T09:04:01+08:00",
        provider_message_id=f"message-{intent.intent_id}",
    )
    ledger.append_observation(accepted)
    delivered = _recovery_record(
        record_id=f"{intent.intent_id}-delivered",
        intent_id=intent.intent_id,
        previous_record_id=accepted.record_id,
        transport_attempt_id=send.transport_attempt_id,
        idempotency_key=key,
        observation=DispatchObservation.DELIVERED,
        safe_reason_code="AUTHORITATIVE_DELIVERY_RECEIPT",
        observed_at="2026-11-23T09:04:02+08:00",
        provider_message_id=f"message-{intent.intent_id}",
    )
    ledger.append_observation(delivered)


def _exercise_unknown_recovery(
    *,
    ledger: InMemoryResponseLedger,
    decided: DecidedQuery,
) -> tuple[InMemoryResponseLedger, str]:
    key = "dispatch-key-G3-Q2"
    intent = ledger.commit_decision_and_intent(
        release_record=decided.record,
        destination="current-chat",
        dispatch_idempotency_key=key,
    )
    if intent is None:
        raise RuntimeError("G3 Q2 did not create a response intent")
    send1 = _recovery_record(
        record_id="G3-Q2-send-1",
        intent_id=intent.intent_id,
        previous_record_id=None,
        transport_attempt_id="G3-Q2-transport-1",
        idempotency_key=key,
        observation=DispatchObservation.SEND_STARTED,
        safe_reason_code="DISPATCH_STARTED",
        observed_at="2026-11-23T09:06:00+08:00",
    )
    ledger.append_observation(send1)
    unknown = _recovery_record(
        record_id="G3-Q2-unknown",
        intent_id=intent.intent_id,
        previous_record_id=send1.record_id,
        transport_attempt_id=send1.transport_attempt_id,
        idempotency_key=key,
        observation=DispatchObservation.UNKNOWN,
        safe_reason_code="DESTINATION_OUTCOME_UNKNOWN",
        observed_at="2026-11-23T09:06:01+08:00",
    )
    ledger.append_observation(unknown)

    # Deterministic L2 restart: only exported durable values are rehydrated.
    restarted = InMemoryResponseLedger.restore(
        ledger.export_state(),
        authorization_authority=decided.prepared.authorization_authority,
        release_currentness_authority=(
            decided.prepared.release_currentness_authority
        ),
    )
    recoverable = restarted.recoverable_intents()
    if tuple(item.intent_id for item in recoverable) != (intent.intent_id,):
        raise RuntimeError("restart did not recover the same unknown intent")
    not_found = _recovery_record(
        record_id="G3-Q2-reconciled-not-found",
        intent_id=intent.intent_id,
        previous_record_id=unknown.record_id,
        transport_attempt_id="G3-Q2-reconcile-1",
        idempotency_key=key,
        observation=DispatchObservation.NOT_FOUND,
        safe_reason_code="IDEMPOTENCY_LOOKUP_NOT_FOUND",
        observed_at="2026-11-23T09:07:00+08:00",
    )
    restarted.append_observation(not_found)
    send2 = _recovery_record(
        record_id="G3-Q2-send-2",
        intent_id=intent.intent_id,
        previous_record_id=not_found.record_id,
        transport_attempt_id="G3-Q2-transport-2",
        idempotency_key=key,
        observation=DispatchObservation.SEND_STARTED,
        safe_reason_code="BOUNDED_RETRY_AFTER_NOT_FOUND",
        observed_at="2026-11-23T09:07:01+08:00",
    )
    restarted.append_observation(send2)
    accepted = _recovery_record(
        record_id="G3-Q2-accepted",
        intent_id=intent.intent_id,
        previous_record_id=send2.record_id,
        transport_attempt_id=send2.transport_attempt_id,
        idempotency_key=key,
        observation=DispatchObservation.ACCEPTED,
        safe_reason_code="DESTINATION_ACCEPTED",
        observed_at="2026-11-23T09:07:02+08:00",
        provider_message_id="provider-message-G3-Q2",
    )
    restarted.append_observation(accepted)
    delivered = _recovery_record(
        record_id="G3-Q2-delivered",
        intent_id=intent.intent_id,
        previous_record_id=accepted.record_id,
        transport_attempt_id=send2.transport_attempt_id,
        idempotency_key=key,
        observation=DispatchObservation.DELIVERED,
        safe_reason_code="AUTHORITATIVE_DELIVERY_RECEIPT",
        observed_at="2026-11-23T09:07:03+08:00",
        provider_message_id="provider-message-G3-Q2",
    )
    restarted.append_observation(delivered)
    duplicate = _recovery_record(
        record_id="G3-Q2-duplicate-receipt",
        intent_id=intent.intent_id,
        previous_record_id=delivered.record_id,
        transport_attempt_id="G3-Q2-reconcile-2",
        idempotency_key=key,
        observation=DispatchObservation.DUPLICATE_RECEIPT,
        safe_reason_code="DUPLICATE_RECEIPT_DEDUPED",
        observed_at="2026-11-23T09:08:00+08:00",
        provider_message_id="provider-message-G3-Q2",
    )
    final_intent = restarted.append_observation(duplicate)
    if final_intent.state is not ResponseIntentState.DELIVERED:
        raise RuntimeError("delivery recovery did not reach DELIVERED")
    return restarted, final_intent.digest


def _artifact_set_fingerprint() -> str:
    explicit_paths = {
        ROOT / "src" / "rag_capstone_contracts.py",
        ROOT / "src" / "rag_capstone_orchestrator.py",
        ROOT / "examples" / "day106_capstone_support.py",
        ROOT / "examples" / "day106_production_rag_capstone.py",
        ROOT / "evals" / "day106_production_rag_capstone_seed.jsonl",
        ROOT / "evals" / "run_day106_seed_eval.py",
        ROOT / "evals" / "run_day106_evidence_replay.py",
        ROOT / "tests" / "test_day106_capstone_pipeline.py",
        ROOT / "tests" / "test_day106_capstone_recovery.py",
        ROOT / "tests" / "test_day106_seed_grader.py",
        ROOT / "requirements-day88.txt",
        ROOT / "requirements-day90.txt",
    }
    dependency_paths = {
        *ROOT.joinpath("src").glob("rag_*.py"),
        *ROOT.joinpath("examples").glob("day9[5-9]_*.py"),
        *ROOT.joinpath("examples").glob("day10[0-6]_*.py"),
        *ROOT.joinpath("evals").glob("*day9[5-9]*"),
        *ROOT.joinpath("evals").glob("*day10[0-6]*"),
        *ROOT.joinpath("tests").glob("test_day9[5-9]_*.py"),
        *ROOT.joinpath("tests").glob("test_day10[0-6]_*.py"),
    }
    paths = tuple(
        sorted(
            explicit_paths.union(dependency_paths),
            key=lambda path: str(path.relative_to(ROOT)),
        )
    )
    return stable_hash(
        tuple(
            (str(path.relative_to(ROOT)), stable_hash(path.read_text(encoding="utf-8")))
            for path in paths
        )
    )


def _query_summary(
    decided: DecidedQuery,
    ledger: InMemoryResponseLedger,
) -> dict[str, object]:
    final_intent_expected = (
        decided.decision.result is SecurityResult.PASS
        and decided.decision.disposition is SecurityDisposition.RELEASE
    )
    intent = (
        ledger.read_intent(decided.record.response_intent_id)
        if decided.record.response_intent_id is not None
        else None
    )
    return {
        "request_attempt_id": decided.prepared.bound.capstone.request_attempt_id,
        "generation_id": decided.prepared.bound.capstone.generation_id,
        "pointer_revision": decided.prepared.bound.capstone.pointer_revision,
        "read_view_id": decided.prepared.bound.capstone.read_view_id,
        "retrieval_request_id": decided.prepared.receipt.retrieval_request_id,
        "retrieval_operation_id": decided.prepared.receipt.retrieval_operation_id,
        "day101_execution_receipt_digest": (
            decided.prepared.receipt.day101_execution_receipt_digest
        ),
        "retrieval_bundle_digest": decided.prepared.receipt.retrieval_bundle_digest,
        "context_manifest_digest": decided.prepared.receipt.context_manifest_digest,
        "model_invocation_digest": decided.prepared.invocation.digest,
        "prompt_occurrence_ids": list(decided.prepared.occurrence_ids),
        "answer_candidate_digest": decided.prepared.candidate.digest,
        "release_evidence_digest": decided.evidence.digest,
        "disclosure_envelope_digest": decided.prepared.disclosure.digest,
        "output_release_decision_digest": decided.decision.digest,
        "current_authorization_revision_digest": (
            decided.evidence.current_authorization_revision
        ),
        "current_provenance_revision": (
            decided.evidence.current_provenance_revision
        ),
        "current_tombstone_revision": (
            decided.evidence.current_tombstone_revision
        ),
        "dlp_result": decided.evidence.dlp_result.value,
        "destination_result": decided.evidence.destination_result.value,
        "release_result": decided.decision.result.value,
        "release_disposition": decided.decision.disposition.value,
        "safe_reason_codes": list(decided.decision.reason_codes),
        "response_intent_expected": final_intent_expected,
        "final_response_state": (
            intent.state.value
            if intent is not None
            else decided.record.response_dispatch_state.value
        ),
        "raw_answer_logged": False,
    }


def run_example() -> dict[str, object]:
    """Execute the aligned deterministic capstone and return safe evidence."""

    prerequisite = _load_prerequisite_evidence()
    lineage_by_id = _lineages(prerequisite)
    all_lineages = tuple(
        lineage_by_id[key] for key in sorted(lineage_by_id)
    )
    source_snapshot_digest = stable_hash(
        tuple(item.digest for item in all_lineages)
    )
    policy = _policy()
    ruler = _ruler(prerequisite)
    p1_authorization_digest = stable_hash(
        asdict(
            classroom_authorization_revisions(
                policy_revision=1,
                acl_revision=1,
                authorization_epoch=1,
            )
        )
    )
    store = InMemoryIndexLifecycleStore()
    committer = IndexLifecycleCommitter(store)
    lifecycle_orchestrator = IndexLifecycleOrchestrator(
        provider=DeterministicSealedIndexProvider(),
        committer=committer,
    )
    views = IndexReadViewManager(store)
    bs1 = _snapshot(
        snapshot_id="BS1",
        authorization_revision_digest=p1_authorization_digest,
        included=all_lineages,
        source_snapshot_digest=source_snapshot_digest,
    )
    g2 = _build_generation(
        generation_id="G2",
        snapshot=bs1,
        included=all_lineages,
        provider_fence=8,
        ruler=ruler,
        prerequisite=prerequisite,
        store=store,
        committer=committer,
        orchestrator=lifecycle_orchestrator,
    )
    release_currentness_authority = InMemoryReleaseCurrentnessAuthority()
    release_currentness_authority.put(
        _release_currentness_snapshot(
            snapshot_id="release-currentness-G2-P1",
            revision=1,
            generation=g2,
            eligible_occurrence_ids=("A@v1", "C@v1"),
            policy=policy,
        )
    )
    store.seed_active_pointer(
        pointer=ActivePointer(POINTER_NAME, "G2", 8),
        provider_alias_generation_id="G2",
    )
    pointer_g2 = store.read_pointer(POINTER_NAME)
    if pointer_g2 is None:
        raise RuntimeError("G2/r8 pointer was not seeded")

    authorization_authority = InMemoryRetrievalAuthorization()
    g2_serving = build_canonical_day101_fixture(
        generation_id="G2",
        pointer_revision=8,
        generation_artifact_fingerprint=g2.artifact.fingerprint,
        manifest_occurrence_ids=("A@v1", "C@v1"),
        authorization_revision=1,
        authorization=authorization_authority,
    )
    query_specs: tuple[
        tuple[str, str, tuple[CanonicalClaim, ...]], ...
    ] = (
        ("Q1", "What is the refund window?", (refund_window_claim(),)),
        (
            "Q2",
            "Where must a refund request be submitted?",
            (application_channel_claim(),),
        ),
        (
            "Q3",
            "What is the refund window and where is the request submitted?",
            (refund_window_claim(), application_channel_claim()),
        ),
    )
    normal: dict[str, DecidedQuery] = {}
    request_bindings: list[CapstoneRequestBinding] = []
    retrieval_receipts: list[RetrievalAndContextReceipt] = []
    for query_id, query_text, claims in query_specs:
        attempt_id = f"R-G2-{query_id}"
        bound = _bind_attempt(
            attempt_id=attempt_id,
            pointer=pointer_g2,
            generation=g2,
            serving_fixture=g2_serving,
            lineages=all_lineages,
            policy=policy,
            views=views,
            observed_at="2026-11-23T09:01:00+08:00",
        )
        retrieval_run = execute_day101_query(
            g2_serving,
            query_id=f"G2-{query_id}",
            query_text=query_text,
            request_attempt_id=attempt_id,
        )
        prepared = _prepare_query(
            query_id=f"G2-{query_id}",
            bound=bound,
            serving_fixture=g2_serving,
            release_currentness_authority=(
                release_currentness_authority
            ),
            retrieval_run=retrieval_run,
            claims=claims,
            lineages=lineage_by_id,
            policy=policy,
            observed_at="2026-11-23T09:02:00+08:00",
        )
        decided = _decide_query(
            query_id=f"G2-{query_id}",
            prepared=prepared,
            observed_at="2026-11-23T09:03:00+08:00",
        )
        normal[query_id] = decided
        request_bindings.append(bound.capstone)
        retrieval_receipts.append(prepared.receipt)

    # Complete the historical P1 controls before the later P2 revocation.
    ledger = InMemoryResponseLedger(
        authorization_authority=authorization_authority,
        release_currentness_authority=release_currentness_authority,
    )
    for query_id in ("Q1", "Q2", "Q3"):
        _deliver_immediately(
            ledger=ledger,
            decided=normal[query_id],
            destination="current-chat",
        )

    # A second Q3 reaches candidate state under G2/P1, but is not released yet.
    pending_bound = _bind_attempt(
        attempt_id="R-G2-Q3-PENDING",
        pointer=pointer_g2,
        generation=g2,
        serving_fixture=g2_serving,
        lineages=all_lineages,
        policy=policy,
        views=views,
        observed_at="2026-11-23T09:01:10+08:00",
    )
    pending_retrieval = execute_day101_query(
        g2_serving,
        query_id="G2-Q3-PENDING",
        query_text="What is the refund window and application channel?",
        request_attempt_id="R-G2-Q3-PENDING",
    )
    pending_prepared = _prepare_query(
        query_id="G2-Q3-PENDING",
        bound=pending_bound,
        serving_fixture=g2_serving,
        release_currentness_authority=release_currentness_authority,
        retrieval_run=pending_retrieval,
        claims=(refund_window_claim(), application_channel_claim()),
        lineages=lineage_by_id,
        policy=policy,
        observed_at="2026-11-23T09:02:10+08:00",
    )
    request_bindings.append(pending_bound.capstone)
    retrieval_receipts.append(pending_prepared.receipt)

    # P2 is authoritative immediately; old ReadViews retain identity, not permission.
    p2_scope = authorization_authority.revoke_occurrence(
        tenant_id=TENANT_ID,
        principal_subject=PRINCIPAL_ID,
        action=g2_serving.day100.scope.action,
        purpose=g2_serving.day100.scope.purpose,
        occurrence_id="A@v1",
    )
    p2_authorization_digest = stable_hash(asdict(p2_scope.revisions))
    c_only = (lineage_by_id["C@v1"],)
    bs2 = _snapshot(
        snapshot_id="BS2",
        authorization_revision_digest=p2_authorization_digest,
        included=c_only,
        source_snapshot_digest=source_snapshot_digest,
    )
    g3 = _build_generation(
        generation_id="G3",
        snapshot=bs2,
        included=c_only,
        provider_fence=9,
        ruler=ruler,
        prerequisite=prerequisite,
        store=store,
        committer=committer,
        orchestrator=lifecycle_orchestrator,
    )
    lease = store.issue_activation_lease(
        pointer_name=POINTER_NAME,
        committer_id="day106-capstone-committer",
        issued_at="2026-11-23T09:04:00+08:00",
    )
    activation = committer.activate(
        activation_id="activate-G3-after-P2",
        pointer_name=POINTER_NAME,
        target_generation_id="G3",
        expected_generation_id="G2",
        expected_revision=8,
        committer_id="day106-capstone-committer",
        committer_fence=lease.fencing_token,
        committed_at="2026-11-23T09:04:10+08:00",
        previous_retire_after="2026-11-23T10:00:00+08:00",
    )
    if activation.pointer is None or activation.activation is None:
        raise RuntimeError(f"G3 activation failed: {activation.safe_reason}")
    pointer_g3 = activation.pointer
    release_currentness_authority.put(
        _release_currentness_snapshot(
            snapshot_id="release-currentness-G3-P2",
            revision=2,
            generation=g3,
            eligible_occurrence_ids=("C@v1",),
            policy=policy,
        )
    )

    old_after_p2 = _decide_query(
        query_id="G2-Q3-PENDING-AFTER-P2",
        prepared=pending_prepared,
        observed_at="2026-11-23T09:04:20+08:00",
    )
    old_retry = execute_day101_query(
        g2_serving,
        query_id="G2-Q3-RETRIEVAL-AFTER-P2",
        query_text="What is the refund window and application channel?",
        request_attempt_id="R-G2-Q3-PENDING",
    )

    g3_serving = build_canonical_day101_fixture(
        generation_id="G3",
        pointer_revision=9,
        generation_artifact_fingerprint=g3.artifact.fingerprint,
        manifest_occurrence_ids=("C@v1",),
        authorization_revision=2,
        authorization=authorization_authority,
        authorization_scope=p2_scope,
    )
    g3_q2_bound = _bind_attempt(
        attempt_id="R-G3-Q2",
        pointer=pointer_g3,
        generation=g3,
        serving_fixture=g3_serving,
        lineages=c_only,
        policy=policy,
        views=views,
        observed_at="2026-11-23T09:05:00+08:00",
    )
    g3_q2_retrieval = execute_day101_query(
        g3_serving,
        query_id="G3-Q2",
        query_text="Where must a refund request be submitted?",
        request_attempt_id="R-G3-Q2",
    )
    g3_q2_prepared = _prepare_query(
        query_id="G3-Q2",
        bound=g3_q2_bound,
        serving_fixture=g3_serving,
        release_currentness_authority=release_currentness_authority,
        retrieval_run=g3_q2_retrieval,
        claims=(application_channel_claim(),),
        lineages=lineage_by_id,
        policy=policy,
        observed_at="2026-11-23T09:05:10+08:00",
    )
    g3_q2 = _decide_query(
        query_id="G3-Q2",
        prepared=g3_q2_prepared,
        observed_at="2026-11-23T09:05:20+08:00",
    )
    request_bindings.append(g3_q2_bound.capstone)
    retrieval_receipts.append(g3_q2_prepared.receipt)

    g3_blocked: dict[str, dict[str, object]] = {}
    for query_id, query_text, claims in (
        ("Q1", "What is the refund window?", (refund_window_claim(),)),
        (
            "Q3",
            "What is the refund window and application channel?",
            (refund_window_claim(), application_channel_claim()),
        ),
    ):
        bound = _bind_attempt(
            attempt_id=f"R-G3-{query_id}",
            pointer=pointer_g3,
            generation=g3,
            serving_fixture=g3_serving,
            lineages=c_only,
            policy=policy,
            views=views,
            observed_at="2026-11-23T09:05:30+08:00",
        )
        request_bindings.append(bound.capstone)
        result = execute_day101_query(
            g3_serving,
            query_id=f"G3-{query_id}",
            query_text=query_text,
            request_attempt_id=f"R-G3-{query_id}",
        )
        hit_ids = tuple(
            item.identity.occurrence_id for item in result.day101_response.hits
        )
        required_ids = {
            occurrence_id
            for claim in claims
            for occurrence_id in claim.occurrence_ids
        }
        blocked_before_prompt = not required_ids.issubset(hit_ids)
        g3_blocked[query_id] = {
            "request_attempt_id": bound.capstone.request_attempt_id,
            "generation_id": bound.capstone.generation_id,
            "pointer_revision": bound.capstone.pointer_revision,
            "stage_outcome": "BLOCKED_BEFORE_PROMPT",
            "safe_reason": "REQUIRED_EVIDENCE_UNAVAILABLE",
            "retrieved_occurrence_ids": list(hit_ids),
            "revoked_A_used": "A@v1" in hit_ids,
            "blocked_before_prompt": blocked_before_prompt,
            "generator_calls": 0,
            "response_dispatch": ResponseIntentState.NOT_ATTEMPTED.value,
        }

    security_negatives = _security_negative_cases(pending_bound.security)

    blocked_intent = ledger.commit_decision_and_intent(
        release_record=old_after_p2.record,
        destination="",
        dispatch_idempotency_key="",
    )
    if blocked_intent is not None:
        raise RuntimeError("revoked old candidate created a dispatch intent")
    ledger, recovered_intent_digest = _exercise_unknown_recovery(
        ledger=ledger,
        decided=g3_q2,
    )

    expected_answer_records: tuple[AnswerReleaseRecord, ...] = (
        normal["Q1"].record,
        normal["Q2"].record,
        normal["Q3"].record,
        old_after_p2.record,
        g3_q2.record,
    )
    answer_records, response_intents, durable_histories = ledger.export_state()
    if {item.digest for item in answer_records} != {
        item.digest for item in expected_answer_records
    }:
        raise RuntimeError("DURABLE_RELEASE_RECORD_SET_CONFLICT")
    recovery_records = tuple(
        item for _, history in durable_histories for item in history
    )
    release_currentness_snapshots = release_currentness_authority.history()

    security_negative_pass = (
        security_negatives["X_document_injection"].get("bundle") == "FAIL"
        and "DOCUMENT_PROMPT_INJECTION"
        in security_negatives["X_document_injection"].get(
            "safe_reason_codes", []
        )
        and security_negatives["Y_detector_inconclusive"].get("retrieval")
        == "INCONCLUSIVE"
        and security_negatives["Z_composed_attack"].get("bundle") == "FAIL"
        and "CROSS_DOCUMENT_ATTACK_CHAIN"
        in security_negatives["Z_composed_attack"].get(
            "safe_reason_codes", []
        )
        and security_negatives["T_cross_tenant"].get("safe_reason_code")
        == "TENANT_UNAUTHORIZED"
        and security_negatives["B_tombstoned"].get("safe_reason_code")
        == "TOMBSTONED"
        and security_negatives["ACL_current_authorization_denied"].get(
            "safe_reason_code"
        )
        == "CURRENT_AUTHORIZATION_DENIED"
        and security_negatives["PROVENANCE_stale"].get("safe_reason_code")
        == "STALE_PROVENANCE"
    )
    forbidden_evidence_fields = {
        "prompt",
        "source_text",
        "protected_chunk",
        "answer_text",
        "secret",
        "raw_vector",
        "attack_payload",
    }
    evidence_contract_fields = {
        item.name
        for contract in (
            SourceToOccurrenceLineage,
            CapstoneRequestBinding,
            RetrievalAndContextReceipt,
            AnswerReleaseRecord,
            ResponseIntent,
            RecoveryAndIncidentRecord,
        )
        for item in fields(contract)
    }
    evidence_schema_content_safe = not bool(
        forbidden_evidence_fields.intersection(evidence_contract_fields)
    )

    hard_gate_facts = {
        "activation_cas_G2_r8_to_G3_r9": (
            pointer_g3.generation_id == "G3" and pointer_g3.revision == 9
        ),
        "current_G3_Q2_released": (
            g3_q2.decision.result is SecurityResult.PASS
            and g3_q2.decision.disposition is SecurityDisposition.RELEASE
        ),
        "durable_decision_intent_delivery_separated": (
            ledger.read_intent(g3_q2.record.response_intent_id or "") is not None
            and len(ledger.history(g3_q2.record.response_intent_id or "")) >= 6
        ),
        "evidence_content_safe": evidence_schema_content_safe,
        "exact_citations": all(
            item.decision.result is SecurityResult.PASS
            and item.decision.released_citation_occurrence_ids
            == item.prepared.occurrence_ids
            and item.evidence.supported_citation_keys
            == item.prepared.citation_keys
            for item in (*normal.values(), g3_q2)
        ),
        "new_G3_Q1_Q3_do_not_use_A": all(
            not bool(item["revoked_A_used"])
            and bool(item["blocked_before_prompt"])
            for item in g3_blocked.values()
        ),
        "normal_Q1_Q2_Q3_quality": all(
            item.decision.disposition is SecurityDisposition.RELEASE
            for item in normal.values()
        ),
        "old_G2_candidate_blocked_after_P2": (
            old_after_p2.decision.result is SecurityResult.FAIL
            and old_after_p2.decision.disposition is SecurityDisposition.BLOCKED
            and old_after_p2.record.response_dispatch_state
            is ResponseIntentState.NOT_ATTEMPTED
        ),
        "old_G2_retrieval_rechecks_current_authorization": (
            "A@v1"
            not in {
                item.identity.occurrence_id
                for item in old_retry.day101_response.hits
            }
        ),
        "release_currentness_authority_rechecked": (
            len(release_currentness_snapshots) == 2
            and "CURRENT_AUTHORIZATION_CHANGED"
            in old_after_p2.decision.reason_codes
            and "CURRENT_CONTENT_SECURITY_SNAPSHOT_CHANGED"
            in old_after_p2.decision.reason_codes
            and g3_q2.evidence.dlp_result is SecurityResult.PASS
            and g3_q2.evidence.destination_result is SecurityResult.PASS
        ),
        "security_X_Y_Z_T_B_fail_closed": security_negative_pass
        and all(
            not bool(item["entered_prompt"])
            for item in security_negatives.values()
        ),
        "tenant_acl_provenance_exact_reason_codes": security_negative_pass,
        "unauthorized_occurrence_entering_prompt_zero": all(
            item.unauthorized_prompt_count == 0 for item in retrieval_receipts
        ),
        "unknown_reconciled_before_bounded_retry": (
            ledger.read_intent(g3_q2.record.response_intent_id or "") is not None
            and ledger.read_intent(g3_q2.record.response_intent_id or "").state
            is ResponseIntentState.DELIVERED
        ),
    }
    hard_gates = tuple(
        (name, CapstoneResult.PASS if passed else CapstoneResult.FAIL)
        for name, passed in sorted(hard_gate_facts.items())
    )
    evaluated_artifact_digests = tuple(
        sorted(
            {
                *(item.digest for item in all_lineages),
                *(item.digest for item in request_bindings),
                *(item.digest for item in retrieval_receipts),
                *(item.digest for item in answer_records),
                *(item.digest for item in response_intents),
                *(item.digest for item in recovery_records),
                *(item.digest for item in release_currentness_snapshots),
            }
        )
    )
    evaluation = CapstoneComposer.evaluate(
        decision_id="day106-capstone-evaluation-v1",
        execution_id=EXECUTION_ID,
        normal_quality=(
            CapstoneResult.PASS
            if hard_gate_facts["normal_Q1_Q2_Q3_quality"]
            else CapstoneResult.FAIL
        ),
        security_defense=(
            CapstoneResult.PASS
            if hard_gate_facts["security_X_Y_Z_T_B_fail_closed"]
            else CapstoneResult.FAIL
        ),
        failure_recovery=(
            CapstoneResult.PASS
            if hard_gate_facts["unknown_reconciled_before_bounded_retry"]
            else CapstoneResult.FAIL
        ),
        evidence_replay=CapstoneResult.NOT_RUN,
        external_real_boundary=CapstoneResult.NOT_RUN,
        hard_gates=hard_gates,
        evaluated_artifact_digests=evaluated_artifact_digests,
        evidence_level=EVIDENCE_LEVEL,
        production_readiness=PRODUCTION_READINESS,
        safe_reason_codes=(),
        observed_at=COMPLETED_AT,
    )
    manifest = seal_execution(
        execution_id=EXECUTION_ID,
        repository_revision=(
            "8c1056cbc6d1805b2a8c3d1c19e3191cf6ce576a+UNCOMMITTED_WORKTREE"
        ),
        config_fingerprint=_artifact_set_fingerprint(),
        runtime_boundary=RUNTIME_BOUNDARY,
        evidence_level=EVIDENCE_LEVEL,
        exact_command=EXACT_COMMAND,
        started_at=STARTED_AT,
        completed_at=COMPLETED_AT,
        lineages=all_lineages,
        request_bindings=tuple(request_bindings),
        retrieval_receipts=tuple(retrieval_receipts),
        answer_release_records=answer_records,
        response_intents=response_intents,
        recovery_records=recovery_records,
        release_currentness_snapshots=release_currentness_snapshots,
        prerequisite_evidence_digests=tuple(sorted(prerequisite.values())),
        evaluation=evaluation,
        executed_checks=tuple(sorted(hard_gate_facts)),
        not_run=(
            "aligned Day95-Day99 authority-store execution in this Day106 run",
            "canary traffic and production incident drill",
            "canonical CPython 3.12 local validation",
            "external real Provider/model/DLP",
            "HA/failover/restore and physical purge",
            "load/soak/capacity/cost",
            "production IAM/RLS/TLS and network egress enforcement",
            "Day106 PostgreSQL/pgvector/Docker integration",
            "real process/container restart replay",
        ),
    )

    report: dict[str, object] = {
        "schema_version": "day106-production-rag-capstone-evidence.v2",
        "day": 106,
        "scenario_id": EXECUTION_ID,
        "evidence_level": EVIDENCE_LEVEL,
        "runtime_boundary": RUNTIME_BOUNDARY,
        "fixture_clock": "LOGICAL_DETERMINISTIC_TIMESTAMPS",
        "fixture_production_eligible": False,
        "overall_status": evaluation.overall_hard_gate.value,
        "overall_status_scope": (
            "DETERMINISTIC_L2_RUNTIME_HARD_GATES_AT_SEAL; "
            "EXCLUDES_OFFLINE_REPLAY, COURSE_MASTERY, CANONICAL_PYTHON_3_12, "
            "EXTERNAL_REAL, AND PRODUCTION_READINESS"
        ),
        "day106_overall_status": "NOT_CLAIMED_BY_RUNTIME_REPORT",
        "production_readiness": PRODUCTION_READINESS,
        "repository_state": {
            "base_revision": (
                "8c1056cbc6d1805b2a8c3d1c19e3191cf6ce576a"
            ),
            "worktree": "UNCOMMITTED",
            "branch": "day106-production-rag-capstone",
            "config_fingerprint": manifest.config_fingerprint,
        },
        "prerequisite_evidence": {
            "digests": prerequisite,
            "day105_handoff_seal_time_l3": "NOT_RUN",
            "later_append_only_day105_bounded_l3": "PASS",
            "prerequisite_does_not_imply_day106_e2e": True,
        },
        "lineage": {
            item.occurrence_id: {
                "lineage_id": item.lineage_id,
                "digest": item.digest,
                "source_version": item.source_version,
                "chunk_set_id": item.chunk_set_id,
                "embedding_set_id": item.embedding_set_id,
                "content_digest": item.content_digest,
            }
            for item in all_lineages
        },
        "release_currentness_history": [
            {
                "snapshot_id": item.snapshot_id,
                "revision": item.revision,
                "digest": item.digest,
                "source_eligible_occurrence_ids": list(
                    item.source_eligible_occurrence_ids
                ),
                "quarantined_occurrence_ids": list(
                    item.quarantined_occurrence_ids
                ),
                "provenance_revision": item.provenance_revision,
                "tombstone_revision": item.tombstone_revision,
                "content_security_snapshot_digest": (
                    item.content_security_snapshot_digest
                ),
                "security_policy_fingerprint": (
                    item.security_policy_fingerprint
                ),
                "dlp_result": item.dlp_result,
                "metadata_stripping_result": (
                    item.metadata_stripping_result
                ),
                "destination_result": item.destination_result,
            }
            for item in release_currentness_snapshots
        ],
        "lifecycle": {
            "initial": {
                "authorization": "P1",
                "build_snapshot": "BS1",
                "generation": "G2",
                "pointer_revision": 8,
                "manifest_occurrence_ids": ["A@v1", "C@v1"],
            },
            "revocation": {
                "authorization": "P2",
                "revoked_occurrence_id": "A@v1",
                "effective_immediately": True,
            },
            "current": {
                "build_snapshot": "BS2",
                "generation": pointer_g3.generation_id,
                "pointer_revision": pointer_g3.revision,
                "manifest_occurrence_ids": ["C@v1"],
                "activation_record_digest": activation.activation.digest,
            },
            "old_readview_identity_preserved": (
                pending_bound.capstone.generation_id == "G2"
                and pending_bound.capstone.pointer_revision == 8
            ),
        },
        "normal_queries": {
            key: _query_summary(value, ledger)
            for key, value in sorted(normal.items())
        },
        "revocation_behavior": {
            "old_G2_candidate": _query_summary(old_after_p2, ledger),
            "old_G2_retrieval_after_P2": {
                "day101_occurrence_ids": [
                    item.identity.occurrence_id
                    for item in old_retry.day101_response.hits
                ],
                "stage_outcome": "BLOCKED_BEFORE_PROMPT",
                "safe_reason": "REQUIRED_EVIDENCE_UNAVAILABLE",
                "generator_calls": 0,
            },
            "new_G3_Q2": _query_summary(g3_q2, ledger),
            "new_G3_blocks": g3_blocked,
        },
        "security_negative_controls": security_negatives,
        "recovery": {
            "response_intent_digest": recovered_intent_digest,
            "final_state": ledger.read_intent(
                g3_q2.record.response_intent_id or ""
            ).state.value,
            "history": [
                {
                    "record_id": item.record_id,
                    "previous_record_id": item.previous_record_id,
                    "transport_attempt_id": item.transport_attempt_id,
                    "observation": item.observation.value,
                    "safe_reason_code": item.safe_reason_code,
                    "digest": item.digest,
                }
                for item in ledger.history(g3_q2.record.response_intent_id or "")
            ],
            "decision_rewritten": False,
            "candidate_rewritten": False,
            "append_only": True,
        },
        "evaluation": {
            "normal_quality": evaluation.normal_quality.value,
            "security_defense": evaluation.security_defense.value,
            "failure_recovery": evaluation.failure_recovery.value,
            "evidence_replay_at_runtime_seal": evaluation.evidence_replay.value,
            "external_real_boundary": evaluation.external_real_boundary.value,
            "overall_hard_gate": evaluation.overall_hard_gate.value,
            "hard_gates": {
                name: result.value for name, result in evaluation.hard_gates
            },
            "decision_digest": evaluation.digest,
        },
        "execution_manifest": asdict(manifest),
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "secret_logged": False,
        "raw_vector_logged": False,
        "not_run": list(manifest.not_run),
        "claim_boundary": (
            "This PASS is a deterministic Day106 L2 end-to-end application "
            "contract result over aligned lineage receipts. Day95-Day99 authority "
            "stores were prerequisite evidence, not rerun in this identity spine; "
            "same-process state rehydration is not a real restart. Canonical Python "
            "3.12, external-real boundaries, and production readiness remain "
            "NOT_RUN/MORE_EVIDENCE_NEEDED."
        ),
    }
    report["report_checksum"] = stable_hash(report)
    return report


def main() -> None:
    print(json.dumps(run_example(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
