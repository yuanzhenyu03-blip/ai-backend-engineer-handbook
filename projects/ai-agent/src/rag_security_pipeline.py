"""Deterministic Day105 application-owned RAG security pipeline."""

from __future__ import annotations

from rag_chunking_contracts import stable_hash
from rag_security_contracts import (
    AnswerCandidate,
    BundleSecurityDecision,
    ContentProvenanceSecurityRecord,
    ContextAssemblyManifest,
    DeniedOccurrence,
    DisclosureEnvelope,
    IngestionSecurityDecision,
    ModelInvocationEnvelope,
    OutputReleaseDecision,
    ReleaseEvidence,
    RequestSecurityBinding,
    RetrievalBundle,
    RetrievalSecurityDecision,
    RetrievedContentTrust,
    RetrievedOccurrence,
    SecurityCaseObservation,
    SecurityDisposition,
    SecurityEvaluationReport,
    SecurityIncidentRecord,
    SecurityPolicyIdentity,
    SecurityResult,
    context_assembly_digest,
)


class SecurityIdentityConflict(ValueError):
    """Raised when two security artifacts do not share exact identity."""


class SecurityGateRejected(ValueError):
    """Raised when a non-PASS artifact is used across a security boundary."""


def _unknown_result(results: tuple[SecurityResult, ...]) -> SecurityResult:
    if SecurityResult.FAIL in results:
        return SecurityResult.FAIL
    if SecurityResult.INCONCLUSIVE in results:
        return SecurityResult.INCONCLUSIVE
    if SecurityResult.NOT_RUN in results:
        return SecurityResult.NOT_RUN
    return SecurityResult.PASS


def _candidate_set_digest(
    candidates: tuple[RetrievedOccurrence, ...],
) -> str:
    return stable_hash(
        tuple((item.identity.occurrence_id, item.fingerprint) for item in candidates)
    )


class RagSecurityPipeline:
    """Own every decision from ingestion evidence to response release."""

    @staticmethod
    def decide_ingestion(
        *,
        decision_id: str,
        record: ContentProvenanceSecurityRecord,
        policy: SecurityPolicyIdentity,
        observed_at: str,
    ) -> IngestionSecurityDecision:
        subject = record.subject
        reasons: tuple[str, ...]
        versions_match = (
            subject.parser_version == policy.parser_version
            and subject.scanner_version == policy.scanner_version
            and subject.detector_version == policy.detector_version
            and subject.security_policy_version == policy.security_policy_version
        )
        if not versions_match:
            result = SecurityResult.INCONCLUSIVE
            disposition = SecurityDisposition.QUARANTINE
            reasons = ("STALE_OR_INCOMPATIBLE_SECURITY_EVIDENCE",)
        elif record.result is SecurityResult.PASS:
            result = SecurityResult.PASS
            disposition = SecurityDisposition.ELIGIBLE
            reasons = ()
        elif record.result is SecurityResult.FAIL:
            result = SecurityResult.FAIL
            disposition = SecurityDisposition.QUARANTINE
            reasons = record.reason_codes or ("CONTENT_SECURITY_FAILED",)
        else:
            result = record.result
            disposition = SecurityDisposition.QUARANTINE
            reasons = record.reason_codes or ("SECURITY_EVIDENCE_UNAVAILABLE",)
        return IngestionSecurityDecision(
            decision_id=decision_id,
            subject_fingerprint=subject.fingerprint,
            policy_fingerprint=policy.fingerprint,
            result=result,
            disposition=disposition,
            evidence_digests=(record.digest,),
            reason_codes=tuple(sorted(reasons)),
            observed_at=observed_at,
        )

    @staticmethod
    def decide_retrieval(
        *,
        decision_id: str,
        binding: RequestSecurityBinding,
        candidates: tuple[RetrievedOccurrence, ...],
        least_context_occurrence_ids: tuple[str, ...],
        observed_at: str,
    ) -> RetrievalSecurityDecision:
        candidate_ids = tuple(item.identity.occurrence_id for item in candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise SecurityIdentityConflict("retrieval candidates must be unique")
        if len(set(least_context_occurrence_ids)) != len(least_context_occurrence_ids):
            raise SecurityIdentityConflict("least-context IDs must be unique")
        if not set(least_context_occurrence_ids).issubset(candidate_ids):
            raise SecurityIdentityConflict(
                "least-context IDs must come from the candidate set"
            )

        allowed: list[str] = []
        denied: list[DeniedOccurrence] = []
        required_failure = False
        required_unknown = False
        manifest_violation = False
        manifest_entries = dict(binding.manifest_entries)
        for item in candidates:
            occurrence_id = item.identity.occurrence_id
            reason: str | None = None
            expected_manifest_entry = manifest_entries.get(occurrence_id)
            if expected_manifest_entry is None:
                manifest_violation = True
                reason = "NOT_IN_SEALED_MANIFEST"
            elif expected_manifest_entry != item.identity.manifest_entry_digest:
                manifest_violation = True
                reason = "MANIFEST_ENTRY_MISMATCH"
            elif item.identity.tenant_id != binding.tenant_id:
                reason = "TENANT_UNAUTHORIZED"
            elif not item.currently_authorized:
                reason = "CURRENT_AUTHORIZATION_DENIED"
            elif not item.provenance_current:
                reason = "STALE_PROVENANCE"
            elif item.tombstoned:
                reason = "TOMBSTONED"
            elif item.quarantined:
                reason = "CONTENT_QUARANTINED"
            elif item.content_security_result is SecurityResult.FAIL:
                reason = "CONTENT_SECURITY_FAILED"
            elif item.content_security_result in {
                SecurityResult.INCONCLUSIVE,
                SecurityResult.NOT_RUN,
            }:
                reason = "CONTENT_SECURITY_EVIDENCE_UNAVAILABLE"
                required_unknown = (
                    required_unknown or occurrence_id in least_context_occurrence_ids
                )
            elif occurrence_id not in least_context_occurrence_ids:
                reason = "OUTSIDE_LEAST_CONTEXT"
            else:
                identity_matches = (
                    item.identity.authorization_revision
                    == binding.authorization_revision
                    and item.identity.provenance_revision == binding.provenance_revision
                    and item.identity.parser_version == binding.policy.parser_version
                    and item.identity.scanner_version == binding.policy.scanner_version
                    and item.identity.detector_version
                    == binding.policy.detector_version
                    and item.identity.security_policy_version
                    == binding.policy.security_policy_version
                )
                if not identity_matches:
                    reason = "SECURITY_IDENTITY_MISMATCH"
                    required_unknown = (
                        required_unknown
                        or occurrence_id in least_context_occurrence_ids
                    )
                else:
                    allowed.append(occurrence_id)
            if reason is not None:
                denied.append(DeniedOccurrence(occurrence_id, reason))
                if occurrence_id in least_context_occurrence_ids and reason in {
                    "CONTENT_QUARANTINED",
                    "CONTENT_SECURITY_FAILED",
                    "CURRENT_AUTHORIZATION_DENIED",
                    "STALE_PROVENANCE",
                    "TENANT_UNAUTHORIZED",
                    "TOMBSTONED",
                }:
                    required_failure = True

        if manifest_violation or required_failure:
            result = SecurityResult.FAIL
        elif required_unknown:
            result = SecurityResult.INCONCLUSIVE
        else:
            result = SecurityResult.PASS
        if result is not SecurityResult.PASS:
            allowed = []
        candidate_set_digest = _candidate_set_digest(candidates)
        return RetrievalSecurityDecision(
            decision_id=decision_id,
            request_binding_fingerprint=binding.fingerprint,
            candidate_set_digest=candidate_set_digest,
            result=result,
            allowed_occurrence_ids=tuple(allowed),
            denied_occurrences=tuple(denied),
            evidence_digests=(
                stable_hash(
                    (
                        binding.generation_manifest_digest,
                        binding.authorization_revision,
                        binding.provenance_revision,
                        binding.tombstone_revision,
                        binding.content_security_snapshot_digest,
                        binding.security_evidence_digests,
                    )
                ),
            ),
            observed_at=observed_at,
        )

    @staticmethod
    def analyze_bundle(
        *,
        decision_id: str,
        binding: RequestSecurityBinding,
        retrieval_decision: RetrievalSecurityDecision,
        candidates: tuple[RetrievedOccurrence, ...],
    ) -> BundleSecurityDecision:
        if retrieval_decision.result is not SecurityResult.PASS:
            raise SecurityGateRejected("retrieval decision is not PASS")
        if retrieval_decision.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("retrieval decision binding changed")
        candidate_set_digest = _candidate_set_digest(candidates)
        if candidate_set_digest != retrieval_decision.candidate_set_digest:
            raise SecurityIdentityConflict(
                "retrieval candidates changed after the security decision"
            )
        by_id = {item.identity.occurrence_id: item for item in candidates}
        try:
            allowed = tuple(
                by_id[item] for item in retrieval_decision.allowed_occurrence_ids
            )
        except KeyError as exc:
            raise SecurityIdentityConflict(
                "allowed occurrence is missing from candidates"
            ) from exc
        tags = {tag for occurrence in allowed for tag in occurrence.attack_tags}
        reasons: set[str] = set()
        if tags.intersection(
            {
                "DOCUMENT_INSTRUCTION_OVERRIDE",
                "EXFILTRATE_CONTEXT",
            }
        ):
            reasons.add("DOCUMENT_PROMPT_INJECTION")
        if {
            "CHAIN_READ_NEXT",
            "CHAIN_EXECUTE_HIDDEN",
        }.issubset(tags):
            reasons.add("CROSS_DOCUMENT_ATTACK_CHAIN")
        result = SecurityResult.FAIL if reasons else SecurityResult.PASS
        occurrence_ids = tuple(item.identity.occurrence_id for item in allowed)
        evidence = stable_hash(
            tuple((item.identity.occurrence_id, item.attack_tags) for item in allowed)
        )
        return BundleSecurityDecision(
            decision_id=decision_id,
            request_binding_fingerprint=binding.fingerprint,
            retrieval_decision_digest=retrieval_decision.digest,
            candidate_set_digest=candidate_set_digest,
            occurrence_ids_digest=stable_hash(occurrence_ids),
            result=result,
            reason_codes=tuple(sorted(reasons)),
            evidence_digests=(evidence,),
        )

    @staticmethod
    def build_retrieval_bundle(
        *,
        bundle_id: str,
        binding: RequestSecurityBinding,
        retrieval_decision: RetrievalSecurityDecision,
        bundle_decision: BundleSecurityDecision,
        candidates: tuple[RetrievedOccurrence, ...],
        created_at: str,
    ) -> RetrievalBundle:
        if retrieval_decision.result is not SecurityResult.PASS:
            raise SecurityGateRejected("only PASS decisions can build a bundle")
        if bundle_decision.result is not SecurityResult.PASS:
            raise SecurityGateRejected("only PASS decisions can build a bundle")
        if retrieval_decision.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("bundle decision binding changed")
        if bundle_decision.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("bundle decision binding changed")
        candidate_set_digest = _candidate_set_digest(candidates)
        if candidate_set_digest != retrieval_decision.candidate_set_digest:
            raise SecurityIdentityConflict(
                "retrieval candidates changed before bundle construction"
            )
        if (
            bundle_decision.retrieval_decision_digest != retrieval_decision.digest
            or bundle_decision.candidate_set_digest != candidate_set_digest
        ):
            raise SecurityIdentityConflict(
                "bundle analysis covered different retrieval evidence"
            )
        if bundle_decision.occurrence_ids_digest != stable_hash(
            retrieval_decision.allowed_occurrence_ids
        ):
            raise SecurityIdentityConflict("bundle analysis covered different IDs")
        by_id = {item.identity.occurrence_id: item for item in candidates}
        try:
            content_digests = tuple(
                by_id[item].identity.content_digest
                for item in retrieval_decision.allowed_occurrence_ids
            )
        except KeyError as exc:
            raise SecurityIdentityConflict(
                "retrieval bundle occurrence is missing"
            ) from exc
        return RetrievalBundle(
            bundle_id=bundle_id,
            request_binding_fingerprint=binding.fingerprint,
            retrieval_decision_digest=retrieval_decision.digest,
            bundle_security_decision_digest=bundle_decision.digest,
            occurrence_ids=retrieval_decision.allowed_occurrence_ids,
            content_digests=content_digests,
            authorization_revision=binding.authorization_revision,
            provenance_revision=binding.provenance_revision,
            tombstone_revision=binding.tombstone_revision,
            security_policy_version=binding.policy.security_policy_version,
            retrieval_config_version=binding.policy.retrieval_config_version,
            created_at=created_at,
        )

    @staticmethod
    def assemble_context(
        *,
        manifest_id: str,
        binding: RequestSecurityBinding,
        bundle: RetrievalBundle,
        included_occurrence_ids: tuple[str, ...],
        context_budget: int,
        actual_context_units: int,
        envelope_schema_version: str,
        serialization_version: str,
        projection_version: str,
        structured_untrusted_data_digest: str,
    ) -> ContextAssemblyManifest:
        if bundle.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("retrieval bundle binding changed")
        if bundle.security_policy_version != binding.policy.security_policy_version:
            raise SecurityIdentityConflict("security policy changed")
        if bundle.retrieval_config_version != binding.policy.retrieval_config_version:
            raise SecurityIdentityConflict("retrieval config changed")
        if not set(included_occurrence_ids).issubset(bundle.occurrence_ids):
            raise SecurityGateRejected("context can only use allowed bundle IDs")
        if not included_occurrence_ids:
            raise SecurityGateRejected("context cannot be assembled without evidence")
        digest_by_id = dict(zip(bundle.occurrence_ids, bundle.content_digests))
        included_digests = tuple(digest_by_id[item] for item in included_occurrence_ids)
        excluded = tuple(
            item
            for item in bundle.occurrence_ids
            if item not in included_occurrence_ids
        )
        assembled_digest = context_assembly_digest(
            envelope_schema_version=envelope_schema_version,
            serialization_version=serialization_version,
            projection_version=projection_version,
            included_occurrence_ids=included_occurrence_ids,
            included_content_digests=included_digests,
            structured_untrusted_data_digest=structured_untrusted_data_digest,
        )
        return ContextAssemblyManifest(
            manifest_id=manifest_id,
            request_binding_fingerprint=binding.fingerprint,
            retrieval_bundle_digest=bundle.digest,
            included_occurrence_ids=included_occurrence_ids,
            included_content_digests=included_digests,
            excluded_occurrence_ids=excluded,
            prompt_template_version=binding.policy.prompt_template_version,
            context_assembler_version=binding.policy.context_assembler_version,
            envelope_schema_version=envelope_schema_version,
            serialization_version=serialization_version,
            projection_version=projection_version,
            structured_untrusted_data_digest=(structured_untrusted_data_digest),
            context_budget=context_budget,
            actual_context_units=actual_context_units,
            assembled_context_digest=assembled_digest,
            bundle_security_decision_digest=(bundle.bundle_security_decision_digest),
        )

    @staticmethod
    def build_model_envelope(
        *,
        envelope_id: str,
        binding: RequestSecurityBinding,
        context_manifest: ContextAssemblyManifest,
        disclosure: DisclosureEnvelope,
        system_policy_digest: str,
        model_id: str,
        model_config_digest: str,
        permitted_tool_capabilities: tuple[str, ...] = (),
        secret_count: int = 0,
    ) -> ModelInvocationEnvelope:
        if context_manifest.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("context manifest binding changed")
        if disclosure.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("disclosure binding changed")
        if disclosure.authorization_revision != binding.authorization_revision:
            raise SecurityIdentityConflict("disclosure authorization changed")
        if disclosure.output_policy_version != binding.policy.output_policy_version:
            raise SecurityIdentityConflict("output policy changed")
        if (
            context_manifest.prompt_template_version
            != binding.policy.prompt_template_version
            or context_manifest.context_assembler_version
            != binding.policy.context_assembler_version
        ):
            raise SecurityIdentityConflict("context assembly identity changed")
        if disclosure.purpose != binding.purpose:
            raise SecurityIdentityConflict("disclosure purpose changed")
        if disclosure.audience != binding.audience:
            raise SecurityIdentityConflict("disclosure audience changed")
        return ModelInvocationEnvelope(
            envelope_id=envelope_id,
            request_binding_fingerprint=binding.fingerprint,
            context_manifest_digest=context_manifest.digest,
            disclosure_envelope_digest=disclosure.digest,
            system_policy_digest=system_policy_digest,
            model_id=model_id,
            model_config_digest=model_config_digest,
            tool_policy_version=binding.policy.tool_policy_version,
            permitted_tool_capabilities=permitted_tool_capabilities,
            destination_policy_version=binding.policy.output_policy_version,
            retrieved_content_trust=RetrievedContentTrust.UNTRUSTED_DATA,
            secret_count=secret_count,
        )

    @staticmethod
    def decide_output_release(
        *,
        decision_id: str,
        binding: RequestSecurityBinding,
        context_manifest: ContextAssemblyManifest,
        disclosure: DisclosureEnvelope,
        model_envelope: ModelInvocationEnvelope,
        candidate: AnswerCandidate,
        evidence: ReleaseEvidence,
        observed_at: str,
    ) -> OutputReleaseDecision:
        if context_manifest.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("context manifest binding changed")
        if disclosure.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("disclosure binding changed")
        if model_envelope.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("model envelope binding changed")
        if model_envelope.context_manifest_digest != context_manifest.digest:
            raise SecurityIdentityConflict("model envelope context changed")
        if model_envelope.disclosure_envelope_digest != disclosure.digest:
            raise SecurityIdentityConflict("model envelope disclosure changed")
        if candidate.invocation_envelope_digest != model_envelope.digest:
            raise SecurityIdentityConflict("candidate came from another invocation")
        if evidence.candidate_digest != candidate.digest:
            raise SecurityIdentityConflict("release evidence covers another candidate")

        failures: set[str] = set()
        unknowns: set[str] = set()
        if evidence.current_authorization_revision != binding.authorization_revision:
            failures.add("CURRENT_AUTHORIZATION_CHANGED")
        if evidence.current_provenance_revision != binding.provenance_revision:
            failures.add("CURRENT_PROVENANCE_CHANGED")
        if evidence.current_tombstone_revision != binding.tombstone_revision:
            failures.add("CURRENT_TOMBSTONE_CHANGED")
        if (
            evidence.current_content_security_snapshot_digest
            != binding.content_security_snapshot_digest
        ):
            failures.add("CURRENT_CONTENT_SECURITY_SNAPSHOT_CHANGED")
        if evidence.current_security_policy_fingerprint != binding.policy.fingerprint:
            failures.add("CURRENT_SECURITY_POLICY_CHANGED")
        if disclosure.authorization_revision != binding.authorization_revision:
            failures.add("DISCLOSURE_AUTHORIZATION_CHANGED")
        if disclosure.output_policy_version != binding.policy.output_policy_version:
            failures.add("OUTPUT_POLICY_CHANGED")

        checks = {
            "DLP": evidence.dlp_result,
            "METADATA_STRIPPING": evidence.metadata_stripping_result,
            "DESTINATION": evidence.destination_result,
        }
        for name, result in checks.items():
            if result is SecurityResult.FAIL:
                failures.add(f"{name}_FAILED")
            elif result in {
                SecurityResult.INCONCLUSIVE,
                SecurityResult.NOT_RUN,
            }:
                unknowns.add(f"{name}_EVIDENCE_UNAVAILABLE")
        if candidate.sensitive_markers:
            failures.add("SENSITIVE_OUTPUT_DETECTED")
        if candidate.proposed_tool_calls:
            failures.add("TOOL_CALL_NOT_ADMITTED")
        observed_claim_ids = set(evidence.observed_claim_ids)
        if set(candidate.claim_ids) != observed_claim_ids:
            failures.add("OUTPUT_CLAIM_MANIFEST_MISMATCH")
        if evidence.unclassified_claim_count:
            failures.add("UNCLASSIFIED_OUTPUT_CLAIM")
        if not observed_claim_ids.issubset(evidence.grounded_claim_ids):
            failures.add("UNGROUNDED_CLAIM")
        if not observed_claim_ids.issubset(disclosure.allowed_fields):
            failures.add("DISCLOSURE_FIELD_NOT_ALLOWED")
        if len(observed_claim_ids) > disclosure.disclosure_budget:
            failures.add("DISCLOSURE_BUDGET_EXCEEDED")

        citation_keys = tuple(
            sorted(
                f"{item.claim_id}:{item.occurrence_id}"
                for item in candidate.proposed_citations
            )
        )
        citation_claim_ids = {item.claim_id for item in candidate.proposed_citations}
        if not observed_claim_ids.issubset(citation_claim_ids):
            failures.add("CLAIM_MISSING_CITATION")
        if not citation_claim_ids.issubset(observed_claim_ids):
            failures.add("CITATION_REFERENCES_UNKNOWN_CLAIM")
        if not set(citation_keys).issubset(evidence.supported_citation_keys):
            failures.add("CITATION_NOT_EXACTLY_SUPPORTED")
        citation_ids = tuple(
            sorted({item.occurrence_id for item in candidate.proposed_citations})
        )
        if not set(citation_ids).issubset(evidence.currently_authorized_occurrence_ids):
            failures.add("CURRENT_CITATION_AUTHORIZATION_DENIED")
        if not set(citation_ids).issubset(context_manifest.included_occurrence_ids):
            failures.add("CITATION_OUTSIDE_CONTEXT")

        if failures:
            result = SecurityResult.FAIL
            disposition = SecurityDisposition.BLOCKED
            reasons = tuple(sorted(failures.union(unknowns)))
            released_citations: tuple[str, ...] = ()
        elif unknowns:
            result = SecurityResult.INCONCLUSIVE
            disposition = SecurityDisposition.BLOCKED
            reasons = tuple(sorted(unknowns))
            released_citations = ()
        elif not observed_claim_ids:
            result = SecurityResult.PASS
            disposition = SecurityDisposition.ABSTAIN
            reasons = ("NO_RELEASABLE_GROUNDED_CLAIMS",)
            released_citations = ()
        else:
            result = SecurityResult.PASS
            disposition = SecurityDisposition.RELEASE
            reasons = ()
            released_citations = citation_ids
        return OutputReleaseDecision(
            decision_id=decision_id,
            request_binding_fingerprint=binding.fingerprint,
            candidate_digest=candidate.digest,
            disclosure_envelope_digest=disclosure.digest,
            release_evidence_digest=evidence.digest,
            result=result,
            disposition=disposition,
            reason_codes=reasons,
            released_citation_occurrence_ids=released_citations,
            observed_at=observed_at,
        )

    @staticmethod
    def cache_identity(
        *,
        binding: RequestSecurityBinding,
        disclosure: DisclosureEnvelope,
        occurrence_ids: tuple[str, ...],
        content_digests: tuple[str, ...],
    ) -> str:
        if disclosure.request_binding_fingerprint != binding.fingerprint:
            raise SecurityIdentityConflict("cache disclosure binding changed")
        if len(occurrence_ids) != len(content_digests):
            raise ValueError("cache occurrences require content digests")
        return stable_hash(
            {
                "request_binding": binding.fingerprint,
                "generation_id": binding.generation_id,
                "manifest_digest": binding.generation_manifest_digest,
                "read_view_id": binding.read_view_id,
                "pointer_revision": binding.pointer_revision,
                "authorization_revision": binding.authorization_revision,
                "provenance_revision": binding.provenance_revision,
                "tombstone_revision": binding.tombstone_revision,
                "content_security_snapshot": (binding.content_security_snapshot_digest),
                "policy": binding.policy.fingerprint,
                "disclosure": disclosure.digest,
                "occurrence_ids": occurrence_ids,
                "content_digests": content_digests,
            }
        )

    @staticmethod
    def evaluate_security_cases(
        *,
        report_id: str,
        policy: SecurityPolicyIdentity,
        cases: tuple[SecurityCaseObservation, ...],
        evidence_level: str,
        not_run_boundaries: tuple[str, ...],
    ) -> SecurityEvaluationReport:
        if not cases:
            raise ValueError("security evaluation requires cases")

        def gate_result(violations: tuple[bool, ...]) -> SecurityResult:
            if any(violations):
                return SecurityResult.FAIL
            evaluator_results = tuple(item.evaluator_result for item in cases)
            if SecurityResult.INCONCLUSIVE in evaluator_results:
                return SecurityResult.INCONCLUSIVE
            if SecurityResult.NOT_RUN in evaluator_results:
                return SecurityResult.NOT_RUN
            return SecurityResult.PASS

        gate_results = {
            "case_evaluator_execution": _unknown_result(
                tuple(item.evaluator_result for item in cases)
            ),
            "citation_exact_binding": gate_result(
                tuple(not item.citations_exact for item in cases)
            ),
            "critical_attack_success_zero": gate_result(
                tuple(item.critical and item.attack_succeeded for item in cases)
            ),
            "cross_tenant_leakage_zero": gate_result(
                tuple(item.cross_tenant_disclosure for item in cases)
            ),
            "normal_quality_preserved": gate_result(
                tuple(not item.normal_quality_passed for item in cases)
            ),
            "protected_metadata_disclosure_zero": gate_result(
                tuple(item.protected_metadata_disclosure for item in cases)
            ),
            "sensitive_output_violation_zero": gate_result(
                tuple(item.sensitive_output_violation for item in cases)
            ),
            "tombstone_resurrection_zero": gate_result(
                tuple(item.tombstone_resurrection for item in cases)
            ),
            "unsafe_rollback_activation_zero": gate_result(
                tuple(item.unsafe_rollback_activated for item in cases)
            ),
            "unauthorized_occurrence_entering_prompt_zero": gate_result(
                tuple(item.unauthorized_entered_prompt for item in cases)
            ),
        }
        overall = _unknown_result(tuple(gate_results.values()))
        return SecurityEvaluationReport(
            report_id=report_id,
            policy_fingerprint=policy.fingerprint,
            adversarial_set_digest=policy.adversarial_set_digest,
            case_digests=tuple(sorted(item.digest for item in cases)),
            result=overall,
            hard_gate_results=tuple(sorted(gate_results.items())),
            evidence_level=evidence_level,
            not_run_boundaries=tuple(sorted(not_run_boundaries)),
        )


class InMemorySecurityIncidentLedger:
    """Append-only incident storage; correction events never rewrite history."""

    def __init__(self) -> None:
        self._records: dict[str, SecurityIncidentRecord] = {}

    def append(self, record: SecurityIncidentRecord) -> None:
        if record.incident_record_id in self._records:
            existing = self._records[record.incident_record_id]
            if existing != record:
                raise SecurityIdentityConflict(
                    "incident record ID cannot be overwritten"
                )
            return
        if record.previous_record_id is not None:
            previous = self._records.get(record.previous_record_id)
            if previous is None:
                raise SecurityIdentityConflict(
                    "incident correction requires the previous record"
                )
            if previous.incident_id != record.incident_id:
                raise SecurityIdentityConflict(
                    "incident correction cannot change incident identity"
                )
            if any(
                existing.previous_record_id == record.previous_record_id
                for existing in self._records.values()
            ):
                raise SecurityIdentityConflict(
                    "incident correction history cannot branch"
                )
        elif any(
            existing.incident_id == record.incident_id
            for existing in self._records.values()
        ):
            raise SecurityIdentityConflict(
                "incident history cannot add a second root event"
            )
        self._records[record.incident_record_id] = record

    def read(self, record_id: str) -> SecurityIncidentRecord | None:
        return self._records.get(record_id)

    def history(self, incident_id: str) -> tuple[SecurityIncidentRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.incident_id == incident_id
        )
