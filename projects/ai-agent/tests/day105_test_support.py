"""Deterministic A/B/C/X/Y/Z/T fixtures for Day105 tests."""

from __future__ import annotations

from dataclasses import dataclass

from rag_chunking_contracts import stable_hash
from rag_security_contracts import (
    AnswerCandidate,
    BundleSecurityDecision,
    ContextAssemblyManifest,
    DisclosureEnvelope,
    ModelInvocationEnvelope,
    OccurrenceSecurityIdentity,
    ProposedCitation,
    RequestSecurityBinding,
    RetrievalBundle,
    RetrievalSecurityDecision,
    RetrievedOccurrence,
    SecurityPolicyIdentity,
    SecurityResult,
    manifest_entry_digest,
)
from rag_security_pipeline import RagSecurityPipeline


def classroom_policy(**changes: str) -> SecurityPolicyIdentity:
    values = {
        "security_policy_version": "SP1",
        "parser_version": "parser-v1",
        "scanner_version": "scanner-v1",
        "detector_version": "detector-v1",
        "retrieval_config_version": "retrieval-v1",
        "context_assembler_version": "assembler-v1",
        "prompt_template_version": "prompt-v1",
        "model_policy_version": "model-policy-v1",
        "tool_policy_version": "tool-policy-v1",
        "output_policy_version": "output-policy-v1",
        "adversarial_set_digest": stable_hash("day105-attacks-v1"),
    }
    values.update(changes)
    return SecurityPolicyIdentity(**values)


def classroom_binding(
    *,
    policy: SecurityPolicyIdentity | None = None,
    authorization_revision: str = "AUTH-R1",
    provenance_revision: str = "PROV-R1",
    tombstone_revision: str = "D1",
    generation_id: str = "G2",
    pointer_revision: int = 8,
    manifest_occurrence_ids: tuple[str, ...] = ("A@v1", "C@v1"),
    manifest_tenant_overrides: tuple[tuple[str, str], ...] = (),
) -> RequestSecurityBinding:
    tenant_by_id = dict(manifest_tenant_overrides)
    manifest_entries = tuple(
        (
            occurrence_id,
            manifest_entry_digest(
                occurrence_id,
                occurrence_id.split("@", maxsplit=1)[0],
                f"v{occurrence_id.split('@', maxsplit=1)[1].lstrip('v')}",
                tenant_by_id.get(occurrence_id, "tenant-refund"),
                ("refund-resource-" f"{occurrence_id.split('@', maxsplit=1)[0]}"),
                stable_hash(("CONTENT", occurrence_id)),
                stable_hash(("METADATA", occurrence_id)),
                "metadata-v1",
                provenance_revision,
            ),
        )
        for occurrence_id in sorted(manifest_occurrence_ids)
    )
    return RequestSecurityBinding(
        request_id="request-Q3",
        principal_id="principal-refund-reader",
        tenant_id="tenant-refund",
        purpose="refund-Q3",
        audience="current-user",
        generation_id=generation_id,
        generation_artifact_digest=stable_hash((generation_id, "artifact")),
        build_snapshot_fingerprint=stable_hash((generation_id, "build-snapshot")),
        generation_manifest_digest=stable_hash(manifest_entries),
        manifest_entries=manifest_entries,
        provider_checkpoint_digest=stable_hash((generation_id, "checkpoint")),
        provider_write_fence=7,
        validation_record_digest=stable_hash((generation_id, "validation")),
        day103_evaluation_report_checksum=stable_hash((generation_id, "day103")),
        active_pointer_digest=stable_hash((generation_id, pointer_revision)),
        pointer_revision=pointer_revision,
        read_view_id=f"read-view-{generation_id}-r{pointer_revision}",
        read_view_fence=11,
        read_view_status="OPEN",
        read_view_unexpired=True,
        read_view_owner_id="request-Q3",
        read_view_validation_digest=stable_hash(
            (
                generation_id,
                pointer_revision,
                "OPEN",
            )
        ),
        authorization_revision=authorization_revision,
        provenance_revision=provenance_revision,
        tombstone_revision=tombstone_revision,
        content_security_snapshot_digest=stable_hash("security-snapshot-v1"),
        security_evidence_digests=(
            stable_hash((generation_id, "content-security-evidence")),
        ),
        policy=policy or classroom_policy(),
    )


def classroom_occurrence(
    occurrence_id: str,
    *,
    binding: RequestSecurityBinding | None = None,
    tenant_id: str = "tenant-refund",
    fact_ids: tuple[str, ...] = (),
    attack_tags: tuple[str, ...] = (),
    currently_authorized: bool = True,
    provenance_current: bool = True,
    tombstoned: bool = False,
    quarantined: bool = False,
    content_security_result: SecurityResult = SecurityResult.PASS,
) -> RetrievedOccurrence:
    bound = binding or classroom_binding()
    source_id, source_version = occurrence_id.split("@", maxsplit=1)
    policy = bound.policy
    identity = OccurrenceSecurityIdentity(
        occurrence_id=occurrence_id,
        source_id=source_id,
        source_version=f"v{source_version.lstrip('v')}",
        tenant_id=tenant_id,
        resource_id=f"refund-resource-{source_id}",
        content_digest=stable_hash(("CONTENT", occurrence_id)),
        metadata_digest=stable_hash(("METADATA", occurrence_id)),
        metadata_version="metadata-v1",
        authorization_revision=bound.authorization_revision,
        provenance_revision=bound.provenance_revision,
        parser_version=policy.parser_version,
        scanner_version=policy.scanner_version,
        detector_version=policy.detector_version,
        security_policy_version=policy.security_policy_version,
    )
    return RetrievedOccurrence(
        identity=identity,
        fact_ids=tuple(sorted(fact_ids)),
        attack_tags=tuple(sorted(attack_tags)),
        currently_authorized=currently_authorized,
        provenance_current=provenance_current,
        tombstoned=tombstoned,
        quarantined=quarantined,
        content_security_result=content_security_result,
    )


@dataclass(frozen=True)
class HappyPath:
    binding: RequestSecurityBinding
    occurrences: tuple[RetrievedOccurrence, ...]
    retrieval: RetrievalSecurityDecision
    bundle_security: BundleSecurityDecision
    bundle: RetrievalBundle
    context: ContextAssemblyManifest
    disclosure: DisclosureEnvelope
    invocation: ModelInvocationEnvelope
    candidate: AnswerCandidate


def build_happy_path() -> HappyPath:
    binding = classroom_binding()
    occurrences = (
        classroom_occurrence(
            "A@v1",
            binding=binding,
            fact_ids=("refund_window",),
        ),
        classroom_occurrence(
            "C@v1",
            binding=binding,
            fact_ids=("application_channel",),
        ),
    )
    retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-Q3",
        binding=binding,
        candidates=occurrences,
        least_context_occurrence_ids=("A@v1", "C@v1"),
        observed_at="2026-11-15T01:00:00+08:00",
    )
    bundle_security = RagSecurityPipeline.analyze_bundle(
        decision_id="bundle-security-Q3",
        binding=binding,
        retrieval_decision=retrieval,
        candidates=occurrences,
    )
    bundle = RagSecurityPipeline.build_retrieval_bundle(
        bundle_id="bundle-Q3",
        binding=binding,
        retrieval_decision=retrieval,
        bundle_decision=bundle_security,
        candidates=occurrences,
        created_at="2026-11-15T01:00:01+08:00",
    )
    context = RagSecurityPipeline.assemble_context(
        manifest_id="context-Q3",
        binding=binding,
        bundle=bundle,
        included_occurrence_ids=("A@v1", "C@v1"),
        context_budget=2,
        actual_context_units=2,
        envelope_schema_version="untrusted-evidence-v1",
        serialization_version="json-escaped-v1",
        projection_version="least-fields-v1",
        structured_untrusted_data_digest=stable_hash(
            ("STRUCTURED-UNTRUSTED-DATA", "A@v1", "C@v1")
        ),
    )
    disclosure = DisclosureEnvelope(
        envelope_id="disclosure-Q3",
        request_binding_fingerprint=binding.fingerprint,
        purpose=binding.purpose,
        audience=binding.audience,
        allowed_fields=("application_channel", "refund_window"),
        destination="current-chat",
        disclosure_budget=2,
        authorization_revision=binding.authorization_revision,
        output_policy_version=binding.policy.output_policy_version,
    )
    invocation = RagSecurityPipeline.build_model_envelope(
        envelope_id="invocation-Q3",
        binding=binding,
        context_manifest=context,
        disclosure=disclosure,
        system_policy_digest=stable_hash("system-policy-without-secret"),
        model_id="controlled-model-v1",
        model_config_digest=stable_hash("model-config-v1"),
    )
    candidate = AnswerCandidate(
        candidate_id="candidate-Q3",
        invocation_envelope_digest=invocation.digest,
        answer_digest=stable_hash("protected-answer-Q3"),
        claim_ids=("application_channel", "refund_window"),
        proposed_citations=(
            ProposedCitation("application_channel", "C@v1"),
            ProposedCitation("refund_window", "A@v1"),
        ),
        proposed_tool_calls=(),
        sensitive_markers=(),
        generated_at="2026-11-15T01:00:02+08:00",
    )
    return HappyPath(
        binding,
        occurrences,
        retrieval,
        bundle_security,
        bundle,
        context,
        disclosure,
        invocation,
        candidate,
    )
