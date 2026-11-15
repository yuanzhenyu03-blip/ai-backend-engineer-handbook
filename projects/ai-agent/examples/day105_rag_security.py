"""Executable, content-safe Day105 RAG security boundary fixture."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any

from rag_chunking_contracts import stable_hash
from rag_security_contracts import (
    AnswerCandidate,
    ContentProvenanceSecurityRecord,
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
    RetrievedOccurrence,
    SecurityCaseObservation,
    SecurityIncidentRecord,
    SecurityPolicyIdentity,
    SecurityResult,
    manifest_entry_digest,
)
from rag_security_pipeline import (
    InMemorySecurityIncidentLedger,
    RagSecurityPipeline,
)


EVIDENCE_LEVEL = "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE"
TENANT = "tenant-refund"
OBSERVED_AT = "2026-11-15T01:00:00+08:00"


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
        adversarial_set_digest=stable_hash("day105-adversarial-set-v1"),
    )


def _manifest_entry(
    occurrence_id: str,
    *,
    tenant_id: str = TENANT,
    provenance_revision: str = "PROV-R1",
) -> tuple[str, str]:
    source_id, source_version = occurrence_id.split("@", maxsplit=1)
    return (
        occurrence_id,
        manifest_entry_digest(
            occurrence_id,
            source_id,
            f"v{source_version.lstrip('v')}",
            tenant_id,
            f"refund-resource-{source_id}",
            stable_hash(("CONTENT", occurrence_id)),
            stable_hash(("METADATA", occurrence_id)),
            "metadata-v1",
            provenance_revision,
        ),
    )


def _binding(
    query_id: str,
    policy: SecurityPolicyIdentity,
    *,
    generation_id: str = "G2",
    pointer_revision: int = 8,
    authorization_revision: str = "AUTH-R1",
    manifest_occurrence_ids: tuple[str, ...] = ("A@v1", "C@v1"),
    manifest_tenant_overrides: tuple[tuple[str, str], ...] = (),
) -> RequestSecurityBinding:
    tenant_by_id = dict(manifest_tenant_overrides)
    entries = tuple(
        _manifest_entry(
            occurrence_id,
            tenant_id=tenant_by_id.get(occurrence_id, TENANT),
        )
        for occurrence_id in sorted(manifest_occurrence_ids)
    )
    request_id = f"request-{query_id}"
    return RequestSecurityBinding(
        request_id=request_id,
        principal_id="principal-refund-reader",
        tenant_id=TENANT,
        purpose=f"refund-{query_id}",
        audience="current-user",
        generation_id=generation_id,
        generation_artifact_digest=stable_hash((generation_id, "artifact")),
        build_snapshot_fingerprint=stable_hash((generation_id, "build-snapshot")),
        generation_manifest_digest=stable_hash(entries),
        manifest_entries=entries,
        provider_checkpoint_digest=stable_hash((generation_id, "provider-checkpoint")),
        provider_write_fence=7,
        validation_record_digest=stable_hash((generation_id, "validation-record")),
        day103_evaluation_report_checksum=stable_hash(
            (generation_id, "day103-evaluation")
        ),
        active_pointer_digest=stable_hash(
            (generation_id, pointer_revision, "active-pointer")
        ),
        pointer_revision=pointer_revision,
        read_view_id=f"read-view-{query_id}-{generation_id}",
        read_view_fence=17,
        read_view_status="OPEN",
        read_view_unexpired=True,
        read_view_owner_id=request_id,
        read_view_validation_digest=stable_hash((request_id, generation_id, "OPEN")),
        authorization_revision=authorization_revision,
        provenance_revision="PROV-R1",
        tombstone_revision="D1",
        content_security_snapshot_digest=stable_hash(
            (generation_id, "security-snapshot-v1")
        ),
        security_evidence_digests=(
            stable_hash((generation_id, "security-evidence-v1")),
        ),
        policy=policy,
    )


def _occurrence(
    occurrence_id: str,
    binding: RequestSecurityBinding,
    *,
    tenant_id: str = TENANT,
    fact_ids: tuple[str, ...] = (),
    attack_tags: tuple[str, ...] = (),
    tombstoned: bool = False,
    quarantined: bool = False,
    content_security_result: SecurityResult = SecurityResult.PASS,
) -> RetrievedOccurrence:
    source_id, source_version = occurrence_id.split("@", maxsplit=1)
    identity = OccurrenceSecurityIdentity(
        occurrence_id=occurrence_id,
        source_id=source_id,
        source_version=f"v{source_version.lstrip('v')}",
        tenant_id=tenant_id,
        resource_id=f"refund-resource-{source_id}",
        content_digest=stable_hash(("CONTENT", occurrence_id)),
        metadata_digest=stable_hash(("METADATA", occurrence_id)),
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
        tombstoned=tombstoned,
        quarantined=quarantined,
        content_security_result=content_security_result,
    )


@dataclass(frozen=True)
class QueryRun:
    binding: RequestSecurityBinding
    context: ContextAssemblyManifest
    disclosure: DisclosureEnvelope
    invocation: ModelInvocationEnvelope
    candidate: AnswerCandidate
    evidence: ReleaseEvidence
    release: OutputReleaseDecision


def _run_normal_query(
    *,
    query_id: str,
    required_occurrence_ids: tuple[str, ...],
    claim_ids: tuple[str, ...],
    citations: tuple[ProposedCitation, ...],
    policy: SecurityPolicyIdentity,
) -> QueryRun:
    binding = _binding(query_id, policy)
    candidates = (
        _occurrence(
            "A@v1",
            binding,
            fact_ids=("refund_window",),
        ),
        _occurrence(
            "C@v1",
            binding,
            fact_ids=("application_channel",),
        ),
    )
    retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id=f"retrieval-{query_id}",
        binding=binding,
        candidates=candidates,
        least_context_occurrence_ids=required_occurrence_ids,
        observed_at=OBSERVED_AT,
    )
    bundle_security = RagSecurityPipeline.analyze_bundle(
        decision_id=f"bundle-security-{query_id}",
        binding=binding,
        retrieval_decision=retrieval,
        candidates=candidates,
    )
    bundle = RagSecurityPipeline.build_retrieval_bundle(
        bundle_id=f"bundle-{query_id}",
        binding=binding,
        retrieval_decision=retrieval,
        bundle_decision=bundle_security,
        candidates=candidates,
        created_at=OBSERVED_AT,
    )
    context = RagSecurityPipeline.assemble_context(
        manifest_id=f"context-{query_id}",
        binding=binding,
        bundle=bundle,
        included_occurrence_ids=required_occurrence_ids,
        context_budget=len(required_occurrence_ids),
        actual_context_units=len(required_occurrence_ids),
        envelope_schema_version="untrusted-evidence-v1",
        serialization_version="json-escaped-v1",
        projection_version="least-fields-v1",
        structured_untrusted_data_digest=stable_hash(
            ("STRUCTURED-UNTRUSTED-DATA", required_occurrence_ids)
        ),
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
        model_config_digest=stable_hash("model-config-v1"),
    )
    candidate = AnswerCandidate(
        candidate_id=f"candidate-{query_id}",
        invocation_envelope_digest=invocation.digest,
        answer_digest=stable_hash(("ANSWER-CANDIDATE", query_id)),
        claim_ids=claim_ids,
        proposed_citations=citations,
        proposed_tool_calls=(),
        sensitive_markers=(),
        generated_at=OBSERVED_AT,
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
        currently_authorized_occurrence_ids=required_occurrence_ids,
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
        observed_at=OBSERVED_AT,
    )
    return QueryRun(
        binding,
        context,
        disclosure,
        invocation,
        candidate,
        evidence,
        release,
    )


def _ingestion_outcomes(
    policy: SecurityPolicyIdentity,
) -> dict[str, dict[str, Any]]:
    binding = _binding(
        "INGESTION",
        policy,
        generation_id="GI",
        manifest_occurrence_ids=(
            "A@v1",
            "B@v1",
            "C@v1",
            "X@v1",
            "Y@v1",
        ),
    )
    specifications = {
        "A@v1": (SecurityResult.PASS, ()),
        "B@v1": (SecurityResult.PASS, ()),
        "C@v1": (SecurityResult.PASS, ()),
        "X@v1": (
            SecurityResult.FAIL,
            ("DOCUMENT_PROMPT_INJECTION",),
        ),
        "Y@v1": (
            SecurityResult.INCONCLUSIVE,
            ("DETECTOR_TIMEOUT",),
        ),
    }
    outcomes: dict[str, dict[str, Any]] = {}
    for occurrence_id, (result, reason_codes) in specifications.items():
        record = ContentProvenanceSecurityRecord(
            record_id=f"security-record-{occurrence_id}",
            subject=_occurrence(occurrence_id, binding).identity,
            provenance_verified=True,
            result=result,
            evidence_digests=(stable_hash((occurrence_id, result.value)),),
            reason_codes=reason_codes,
            observed_at=OBSERVED_AT,
        )
        decision = RagSecurityPipeline.decide_ingestion(
            decision_id=f"ingestion-{occurrence_id}",
            record=record,
            policy=policy,
            observed_at=OBSERVED_AT,
        )
        outcomes[occurrence_id] = {
            "result": decision.result.value,
            "disposition": decision.disposition.value,
            "reason_codes": list(decision.reason_codes),
            "decision_digest": decision.digest,
        }
    return outcomes


def _retrieval_summary(decision: Any) -> dict[str, Any]:
    result = getattr(decision, "result")
    allowed = getattr(decision, "allowed_occurrence_ids")
    denied = getattr(decision, "denied_occurrences")
    return {
        "result": result.value,
        "allowed": list(allowed),
        "denied": {item.occurrence_id: item.reason_code for item in denied},
    }


def _adversarial_gates(
    policy: SecurityPolicyIdentity,
) -> dict[str, dict[str, Any]]:
    g2 = _binding("Q3-provider-readback", policy)
    g2_candidates = (
        _occurrence("A@v1", g2),
        _occurrence("B@v1", g2, tombstoned=True),
        _occurrence("C@v1", g2),
        _occurrence("T@v1", g2, tenant_id="tenant-private"),
        _occurrence("X@v1", g2),
    )
    g2_integrity = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-G2-unsealed-provider-entries",
        binding=g2,
        candidates=g2_candidates,
        least_context_occurrence_ids=("A@v1", "C@v1"),
        observed_at=OBSERVED_AT,
    )

    gx = _binding(
        "X-attack-lab",
        policy,
        generation_id="GX",
        manifest_occurrence_ids=("X@v1",),
    )
    x = _occurrence(
        "X@v1",
        gx,
        attack_tags=("DOCUMENT_INSTRUCTION_OVERRIDE",),
    )
    x_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-X-attack-lab",
        binding=gx,
        candidates=(x,),
        least_context_occurrence_ids=("X@v1",),
        observed_at=OBSERVED_AT,
    )
    x_bundle = RagSecurityPipeline.analyze_bundle(
        decision_id="bundle-X-attack-lab",
        binding=gx,
        retrieval_decision=x_retrieval,
        candidates=(x,),
    )

    gy = _binding(
        "Y-attack-lab",
        policy,
        generation_id="GY",
        manifest_occurrence_ids=("Y@v1",),
    )
    y = _occurrence(
        "Y@v1",
        gy,
        content_security_result=SecurityResult.INCONCLUSIVE,
    )
    y_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-Y-attack-lab",
        binding=gy,
        candidates=(y,),
        least_context_occurrence_ids=("Y@v1",),
        observed_at=OBSERVED_AT,
    )

    gz = _binding(
        "Z-attack-lab",
        policy,
        generation_id="GZ",
        manifest_occurrence_ids=("Z1@v1", "Z2@v1"),
    )
    z_candidates = (
        _occurrence(
            "Z1@v1",
            gz,
            attack_tags=("CHAIN_READ_NEXT",),
        ),
        _occurrence(
            "Z2@v1",
            gz,
            attack_tags=("CHAIN_EXECUTE_HIDDEN",),
        ),
    )
    z_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-Z-attack-lab",
        binding=gz,
        candidates=z_candidates,
        least_context_occurrence_ids=("Z1@v1", "Z2@v1"),
        observed_at=OBSERVED_AT,
    )
    z_bundle = RagSecurityPipeline.analyze_bundle(
        decision_id="bundle-Z-attack-lab",
        binding=gz,
        retrieval_decision=z_retrieval,
        candidates=z_candidates,
    )

    gt = _binding(
        "T-attack-lab",
        policy,
        generation_id="GT",
        manifest_occurrence_ids=("T@v1",),
        manifest_tenant_overrides=(("T@v1", "tenant-private"),),
    )
    t = _occurrence("T@v1", gt, tenant_id="tenant-private")
    t_retrieval = RagSecurityPipeline.decide_retrieval(
        decision_id="retrieval-T-attack-lab",
        binding=gt,
        candidates=(t,),
        least_context_occurrence_ids=("T@v1",),
        observed_at=OBSERVED_AT,
    )

    return {
        "G2_exact_manifest": {
            "generation_id": "G2",
            "sealed_occurrence_ids": ["A@v1", "C@v1"],
            **_retrieval_summary(g2_integrity),
        },
        "X_document_injection": {
            "generation_id": "GX",
            "fixture_scope": "INDEPENDENT_NEGATIVE_CONTROL",
            "selected_for_serving": False,
            "retrieval_result": x_retrieval.result.value,
            "bundle_result": x_bundle.result.value,
            "bundle_reason_codes": list(x_bundle.reason_codes),
            "entered_prompt": False,
        },
        "Y_detector_timeout": {
            "generation_id": "GY",
            "fixture_scope": "INDEPENDENT_NEGATIVE_CONTROL",
            "selected_for_serving": False,
            **_retrieval_summary(y_retrieval),
            "entered_prompt": False,
        },
        "Z_cross_document_chain": {
            "generation_id": "GZ",
            "fixture_scope": "INDEPENDENT_NEGATIVE_CONTROL",
            "selected_for_serving": False,
            "retrieval_result": z_retrieval.result.value,
            "bundle_result": z_bundle.result.value,
            "bundle_reason_codes": list(z_bundle.reason_codes),
            "entered_prompt": False,
        },
        "T_cross_tenant": {
            "generation_id": "GT",
            "fixture_scope": "INDEPENDENT_NEGATIVE_CONTROL",
            "selected_for_serving": False,
            **_retrieval_summary(t_retrieval),
            "entered_prompt": False,
        },
    }


def _release_with(
    run: QueryRun,
    *,
    decision_id: str,
    evidence: ReleaseEvidence,
) -> OutputReleaseDecision:
    return RagSecurityPipeline.decide_output_release(
        decision_id=decision_id,
        binding=run.binding,
        context_manifest=run.context,
        disclosure=run.disclosure,
        model_envelope=run.invocation,
        candidate=run.candidate,
        evidence=evidence,
        observed_at=OBSERVED_AT,
    )


def _case(
    case_id: str,
    *,
    attack_document_retrieved: bool = False,
    normal_quality_passed: bool = True,
    evaluator_result: SecurityResult = SecurityResult.PASS,
    unsafe_rollback_activated: bool = False,
) -> SecurityCaseObservation:
    return SecurityCaseObservation(
        case_id=case_id,
        critical=True,
        evaluator_result=evaluator_result,
        attack_document_retrieved=attack_document_retrieved,
        unauthorized_entered_prompt=False,
        cross_tenant_disclosure=False,
        tombstone_resurrection=False,
        sensitive_output_violation=False,
        protected_metadata_disclosure=False,
        attack_succeeded=False,
        unsafe_rollback_activated=unsafe_rollback_activated,
        citations_exact=True,
        normal_quality_passed=normal_quality_passed,
    )


def _failure_injections(
    q3: QueryRun,
    policy: SecurityPolicyIdentity,
    ingestion: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    revoked = _release_with(
        q3,
        decision_id="release-after-authorization-revocation",
        evidence=replace(
            q3.evidence,
            evidence_id="evidence-after-authorization-revocation",
            current_authorization_revision="AUTH-R2-REVOKED",
        ),
    )
    dlp_fail = _release_with(
        q3,
        decision_id="release-after-dlp-detection",
        evidence=replace(
            q3.evidence,
            evidence_id="evidence-after-dlp-detection",
            dlp_result=SecurityResult.FAIL,
        ),
    )
    dlp_timeout = _release_with(
        q3,
        decision_id="release-after-dlp-timeout",
        evidence=replace(
            q3.evidence,
            evidence_id="evidence-after-dlp-timeout",
            dlp_result=SecurityResult.INCONCLUSIVE,
        ),
    )
    quarantine_change = _release_with(
        q3,
        decision_id="release-after-quarantine-change",
        evidence=replace(
            q3.evidence,
            evidence_id="evidence-after-quarantine-change",
            current_content_security_snapshot_digest=stable_hash(
                "snapshot-after-quarantine"
            ),
        ),
    )
    reject_all = RagSecurityPipeline.evaluate_security_cases(
        report_id="evaluation-reject-all",
        policy=policy,
        cases=(
            _case(
                "Q1-overblocked",
                normal_quality_passed=False,
                evaluator_result=SecurityResult.FAIL,
            ),
        ),
        evidence_level=EVIDENCE_LEVEL,
        not_run_boundaries=("PRODUCTION",),
    )
    rollback = RagSecurityPipeline.evaluate_security_cases(
        report_id="evaluation-unsafe-rollback",
        policy=policy,
        cases=(
            _case(
                "unsafe-rollback",
                evaluator_result=SecurityResult.FAIL,
                unsafe_rollback_activated=True,
            ),
        ),
        evidence_level=EVIDENCE_LEVEL,
        not_run_boundaries=("PRODUCTION",),
    )
    return {
        "authorization_revocation": {
            "result": revoked.result.value,
            "disposition": revoked.disposition.value,
            "reason_codes": list(revoked.reason_codes),
        },
        "dlp_detected_sensitive_category": {
            "result": dlp_fail.result.value,
            "disposition": dlp_fail.disposition.value,
            "reason_codes": list(dlp_fail.reason_codes),
        },
        "dlp_timeout": {
            "result": dlp_timeout.result.value,
            "disposition": dlp_timeout.disposition.value,
            "reason_codes": list(dlp_timeout.reason_codes),
        },
        "content_quarantine_changed": {
            "result": quarantine_change.result.value,
            "disposition": quarantine_change.disposition.value,
            "reason_codes": list(quarantine_change.reason_codes),
        },
        "detector_timeout": ingestion["Y@v1"],
        "reject_all_quality_gate": {
            "result": reject_all.result.value,
            "normal_quality_gate": dict(reject_all.hard_gate_results)[
                "normal_quality_preserved"
            ].value,
        },
        "unsafe_rollback": {
            "result": rollback.result.value,
            "rollback_gate": dict(rollback.hard_gate_results)[
                "unsafe_rollback_activation_zero"
            ].value,
        },
    }


def _incident_history() -> dict[str, Any]:
    ledger = InMemorySecurityIncidentLedger()
    opened = SecurityIncidentRecord(
        incident_record_id="incident-event-1",
        incident_id="incident-content-safe-egress-simulation",
        previous_record_id=None,
        state=IncidentState.OPEN,
        affected_request_ids=("request-X-attack-lab",),
        affected_generation_ids=("GX",),
        affected_occurrence_ids=("X@v1",),
        affected_sinks=(EgressSink.EXTERNAL_DESTINATION,),
        containment_actions=(
            "BLOCK_EXTERNAL_DESTINATION",
            "QUARANTINE_X",
            "ROTATE_CREDENTIAL",
        ),
        evidence_digests=(stable_hash("incident-evidence-open"),),
        credential_rotation_status="PENDING",
        impact_analysis_digest=stable_hash("impact-analysis-open"),
        actor_id="application-security-control-plane",
        observed_at=OBSERVED_AT,
    )
    contained = SecurityIncidentRecord(
        incident_record_id="incident-event-2",
        incident_id=opened.incident_id,
        previous_record_id=opened.incident_record_id,
        state=IncidentState.CONTAINED,
        affected_request_ids=opened.affected_request_ids,
        affected_generation_ids=opened.affected_generation_ids,
        affected_occurrence_ids=opened.affected_occurrence_ids,
        affected_sinks=opened.affected_sinks,
        containment_actions=opened.containment_actions,
        evidence_digests=(stable_hash("incident-evidence-contained"),),
        credential_rotation_status="COMPLETE",
        impact_analysis_digest=stable_hash("impact-analysis-contained"),
        actor_id="application-security-control-plane",
        observed_at="2026-11-15T01:05:00+08:00",
    )
    ledger.append(opened)
    ledger.append(contained)
    history = ledger.history(opened.incident_id)
    return {
        "append_only": True,
        "raw_secret_logged": False,
        "record_ids": [item.incident_record_id for item in history],
        "states": [item.state.value for item in history],
        "record_digests": [item.digest for item in history],
    }


def _normal_query_summary(run: QueryRun) -> dict[str, Any]:
    return {
        "generation_id": run.binding.generation_id,
        "read_view_id": run.binding.read_view_id,
        "prompt_occurrence_ids": list(run.context.included_occurrence_ids),
        "claim_ids": list(run.candidate.claim_ids),
        "release_result": run.release.result.value,
        "release_disposition": run.release.disposition.value,
        "released_citations": list(run.release.released_citation_occurrence_ids),
    }


def run_example() -> dict[str, Any]:
    """Run normal and adversarial cases without protected source content."""

    policy = _policy()
    q1 = _run_normal_query(
        query_id="Q1",
        required_occurrence_ids=("A@v1",),
        claim_ids=("refund_window",),
        citations=(ProposedCitation("refund_window", "A@v1"),),
        policy=policy,
    )
    q2 = _run_normal_query(
        query_id="Q2",
        required_occurrence_ids=("C@v1",),
        claim_ids=("application_channel",),
        citations=(ProposedCitation("application_channel", "C@v1"),),
        policy=policy,
    )
    q3 = _run_normal_query(
        query_id="Q3",
        required_occurrence_ids=("A@v1", "C@v1"),
        claim_ids=("application_channel", "refund_window"),
        citations=(
            ProposedCitation("application_channel", "C@v1"),
            ProposedCitation("refund_window", "A@v1"),
        ),
        policy=policy,
    )
    ingestion = _ingestion_outcomes(policy)
    adversarial = _adversarial_gates(policy)
    evaluation = RagSecurityPipeline.evaluate_security_cases(
        report_id="day105-deterministic-evaluation",
        policy=policy,
        cases=(
            _case("Q1"),
            _case("Q2"),
            _case("Q3"),
            _case("X", attack_document_retrieved=True),
            _case("Y", attack_document_retrieved=True),
            _case("Z", attack_document_retrieved=True),
            _case("T", attack_document_retrieved=True),
        ),
        evidence_level=EVIDENCE_LEVEL,
        not_run_boundaries=(
            "PRODUCTION_EXTERNAL_EGRESS",
            "PRODUCTION_IAM",
            "REAL_MODEL_PROVIDER",
            "REAL_VECTOR_PROVIDER",
        ),
    )

    old_cache_key = RagSecurityPipeline.cache_identity(
        binding=q3.binding,
        disclosure=q3.disclosure,
        occurrence_ids=q3.context.included_occurrence_ids,
        content_digests=q3.context.included_content_digests,
    )
    g3 = _binding(
        "Q3-new",
        policy,
        generation_id="G3",
        pointer_revision=9,
        authorization_revision="AUTH-R2",
    )
    g3_disclosure = replace(
        q3.disclosure,
        envelope_id="disclosure-Q3-new",
        request_binding_fingerprint=g3.fingerprint,
        purpose=g3.purpose,
        authorization_revision=g3.authorization_revision,
    )
    new_cache_key = RagSecurityPipeline.cache_identity(
        binding=g3,
        disclosure=g3_disclosure,
        occurrence_ids=q3.context.included_occurrence_ids,
        content_digests=q3.context.included_content_digests,
    )
    report: dict[str, Any] = {
        "scenario_id": "day105-refund-rag-security-boundaries-v1",
        "evidence_level": EVIDENCE_LEVEL,
        "fixture_production_eligible": False,
        "identities": {
            "current_generation": "G2",
            "current_pointer_revision": 8,
            "sealed_manifest_occurrence_ids": ["A@v1", "C@v1"],
            "tombstoned_absent_occurrence_ids": ["B@v1"],
            "day104_handoff_bound": True,
            "policy_fingerprint": policy.fingerprint,
        },
        "ingestion": ingestion,
        "normal_queries": {
            "Q1": _normal_query_summary(q1),
            "Q2": _normal_query_summary(q2),
            "Q3": _normal_query_summary(q3),
        },
        "adversarial_gates": adversarial,
        "failure_injections": _failure_injections(
            q3,
            policy,
            ingestion,
        ),
        "cache": {
            "old_request_generation": q3.binding.generation_id,
            "old_request_read_view": q3.binding.read_view_id,
            "old_request_authorization_revision": (q3.binding.authorization_revision),
            "new_request_generation": g3.generation_id,
            "new_request_pointer_revision": g3.pointer_revision,
            "new_request_authorization_revision": (g3.authorization_revision),
            "old_request_remains_pinned": (q3.binding.generation_id == "G2"),
            "cache_identity_changed": old_cache_key != new_cache_key,
            "old_cache_key": old_cache_key,
            "new_cache_key": new_cache_key,
        },
        "evaluation": {
            "result": evaluation.result.value,
            "hard_gates": {
                name: result.value for name, result in evaluation.hard_gate_results
            },
            "checksum": evaluation.checksum,
        },
        "incident": _incident_history(),
        "not_run": {
            "live_external_egress": SecurityResult.NOT_RUN.value,
            "production_iam": SecurityResult.NOT_RUN.value,
            "real_model_provider": SecurityResult.NOT_RUN.value,
            "real_secret_exposure": SecurityResult.NOT_RUN.value,
            "real_vector_provider": SecurityResult.NOT_RUN.value,
        },
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "raw_attack_payloads_logged": False,
        "raw_protected_content_logged": False,
        "raw_secrets_logged": False,
    }
    report["report_checksum"] = stable_hash(report)
    return report


def main() -> None:
    print(json.dumps(run_example(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
