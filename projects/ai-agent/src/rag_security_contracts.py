"""Application-owned Day105 RAG security value contracts.

Retrieved content remains data, every request stays bound to one Day104
ReadView and one security-policy revision, and model output cannot release
itself. Control-plane records contain identities and digests, not source text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from rag_chunking_contracts import stable_hash


def _require_non_empty(*values: str) -> None:
    if not all(value.strip() for value in values):
        raise ValueError("complete non-empty identity bindings are required")


def _require_unique(values: tuple[str, ...], *, label: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{label} cannot contain empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")


def _require_canonical(values: tuple[str, ...], *, label: str) -> None:
    _require_unique(values, label=label)
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be sorted")


def manifest_entry_digest(
    occurrence_id: str,
    source_id: str,
    source_version: str,
    tenant_id: str,
    resource_id: str,
    content_digest: str,
    metadata_digest: str,
    metadata_version: str,
    provenance_revision: str,
) -> str:
    """Bind one read-back occurrence to its sealed Manifest identity."""

    _require_non_empty(
        occurrence_id,
        source_id,
        source_version,
        tenant_id,
        resource_id,
        content_digest,
        metadata_digest,
        metadata_version,
        provenance_revision,
    )
    return stable_hash(
        (
            occurrence_id,
            source_id,
            source_version,
            tenant_id,
            resource_id,
            content_digest,
            metadata_digest,
            metadata_version,
            provenance_revision,
        )
    )


class SecurityResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_RUN = "NOT_RUN"


class SecurityDisposition(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    WAIT = "WAIT"
    QUARANTINE = "QUARANTINE"
    DENY = "DENY"
    RELEASE = "RELEASE"
    ABSTAIN = "ABSTAIN"
    BLOCKED = "BLOCKED"


class RetrievedContentTrust(str, Enum):
    UNTRUSTED_DATA = "UNTRUSTED_DATA"


def context_assembly_digest(
    *,
    envelope_schema_version: str,
    serialization_version: str,
    projection_version: str,
    included_occurrence_ids: tuple[str, ...],
    included_content_digests: tuple[str, ...],
    structured_untrusted_data_digest: str,
) -> str:
    """Bind a receipt to the actual projected and serialized context."""

    _require_non_empty(
        envelope_schema_version,
        serialization_version,
        projection_version,
        structured_untrusted_data_digest,
    )
    return stable_hash(
        {
            "schema": envelope_schema_version,
            "serialization": serialization_version,
            "projection": projection_version,
            "trust": RetrievedContentTrust.UNTRUSTED_DATA.value,
            "occurrence_ids": included_occurrence_ids,
            "content_digests": included_content_digests,
            "structured_untrusted_data_digest": (structured_untrusted_data_digest),
        }
    )


class EgressSink(str, Enum):
    RESPONSE = "RESPONSE"
    CITATION = "CITATION"
    CACHE = "CACHE"
    LOG = "LOG"
    TELEMETRY = "TELEMETRY"
    EXTERNAL_DESTINATION = "EXTERNAL_DESTINATION"


class IncidentState(str, Enum):
    OPEN = "OPEN"
    CONTAINED = "CONTAINED"
    RECOVERING = "RECOVERING"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class SecurityPolicyIdentity:
    security_policy_version: str
    parser_version: str
    scanner_version: str
    detector_version: str
    retrieval_config_version: str
    context_assembler_version: str
    prompt_template_version: str
    model_policy_version: str
    tool_policy_version: str
    output_policy_version: str
    adversarial_set_digest: str

    def __post_init__(self) -> None:
        _require_non_empty(*asdict(self).values())

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class OccurrenceSecurityIdentity:
    occurrence_id: str
    source_id: str
    source_version: str
    tenant_id: str
    resource_id: str
    content_digest: str
    metadata_digest: str
    metadata_version: str
    authorization_revision: str
    provenance_revision: str
    parser_version: str
    scanner_version: str
    detector_version: str
    security_policy_version: str

    def __post_init__(self) -> None:
        _require_non_empty(*asdict(self).values())

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))

    @property
    def manifest_entry_digest(self) -> str:
        return manifest_entry_digest(
            self.occurrence_id,
            self.source_id,
            self.source_version,
            self.tenant_id,
            self.resource_id,
            self.content_digest,
            self.metadata_digest,
            self.metadata_version,
            self.provenance_revision,
        )


@dataclass(frozen=True)
class ContentProvenanceSecurityRecord:
    """Append-only observations, not the final ingestion decision."""

    record_id: str
    subject: OccurrenceSecurityIdentity
    provenance_verified: bool
    result: SecurityResult
    evidence_digests: tuple[str, ...]
    reason_codes: tuple[str, ...]
    observed_at: str
    manual_review_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.record_id, self.observed_at)
        _require_canonical(self.evidence_digests, label="evidence digests")
        _require_canonical(self.reason_codes, label="reason codes")
        if self.result is SecurityResult.PASS and not self.evidence_digests:
            raise ValueError("PASS requires evidence")
        if self.result is SecurityResult.PASS and not self.provenance_verified:
            raise ValueError("PASS requires verified provenance")
        if self.result is SecurityResult.FAIL and (
            not self.evidence_digests or not self.reason_codes
        ):
            raise ValueError("FAIL requires evidence and an observed reason")

    @property
    def digest(self) -> str:
        return stable_hash(
            {
                **asdict(self),
                "subject_fingerprint": self.subject.fingerprint,
            }
        )


@dataclass(frozen=True)
class IngestionSecurityDecision:
    decision_id: str
    subject_fingerprint: str
    policy_fingerprint: str
    result: SecurityResult
    disposition: SecurityDisposition
    evidence_digests: tuple[str, ...]
    reason_codes: tuple[str, ...]
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.decision_id,
            self.subject_fingerprint,
            self.policy_fingerprint,
            self.observed_at,
        )
        _require_canonical(self.evidence_digests, label="evidence digests")
        _require_canonical(self.reason_codes, label="reason codes")
        if self.result is SecurityResult.PASS:
            if self.disposition is not SecurityDisposition.ELIGIBLE:
                raise ValueError("PASS ingestion must be ELIGIBLE")
            if not self.evidence_digests:
                raise ValueError("PASS ingestion requires evidence")
        elif self.disposition is SecurityDisposition.ELIGIBLE:
            raise ValueError("unknown or failed ingestion cannot be eligible")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RequestSecurityBinding:
    """One request attempt, one ReadView, and one security revision."""

    request_id: str
    principal_id: str
    tenant_id: str
    purpose: str
    audience: str
    generation_id: str
    generation_artifact_digest: str
    build_snapshot_fingerprint: str
    generation_manifest_digest: str
    manifest_entries: tuple[tuple[str, str], ...]
    provider_checkpoint_digest: str
    provider_write_fence: int
    validation_record_digest: str
    day103_evaluation_report_checksum: str
    active_pointer_digest: str
    pointer_revision: int
    read_view_id: str
    read_view_fence: int
    read_view_status: str
    read_view_unexpired: bool
    read_view_owner_id: str
    read_view_validation_digest: str
    authorization_revision: str
    provenance_revision: str
    tombstone_revision: str
    content_security_snapshot_digest: str
    security_evidence_digests: tuple[str, ...]
    policy: SecurityPolicyIdentity

    def __post_init__(self) -> None:
        strings = (
            self.request_id,
            self.principal_id,
            self.tenant_id,
            self.purpose,
            self.audience,
            self.generation_id,
            self.generation_artifact_digest,
            self.build_snapshot_fingerprint,
            self.generation_manifest_digest,
            self.provider_checkpoint_digest,
            self.validation_record_digest,
            self.day103_evaluation_report_checksum,
            self.active_pointer_digest,
            self.read_view_id,
            self.read_view_status,
            self.read_view_owner_id,
            self.read_view_validation_digest,
            self.authorization_revision,
            self.provenance_revision,
            self.tombstone_revision,
            self.content_security_snapshot_digest,
        )
        _require_non_empty(*strings)
        if any(len(item) != 2 for item in self.manifest_entries):
            raise ValueError("Manifest entries require occurrence ID and digest")
        occurrence_ids = tuple(item[0] for item in self.manifest_entries)
        _require_canonical(occurrence_ids, label="Manifest occurrence IDs")
        if not occurrence_ids:
            raise ValueError("Manifest entries cannot be empty")
        if any(not item[1].strip() for item in self.manifest_entries):
            raise ValueError("Manifest entry digests cannot be empty")
        if self.generation_manifest_digest != stable_hash(self.manifest_entries):
            raise ValueError("Generation Manifest digest does not match entries")
        _require_canonical(
            self.security_evidence_digests,
            label="security evidence digests",
        )
        if not self.security_evidence_digests:
            raise ValueError("request binding requires security evidence")
        if (
            min(
                self.provider_write_fence,
                self.pointer_revision,
                self.read_view_fence,
            )
            <= 0
        ):
            raise ValueError("Provider, pointer, and ReadView fences must be positive")
        if self.read_view_status != "OPEN":
            raise ValueError("Day105 requires a validated OPEN ReadView")
        if not self.read_view_unexpired:
            raise ValueError("Day105 requires an unexpired ReadView")
        if self.read_view_owner_id != self.request_id:
            raise ValueError("ReadView must be owned by this request")

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                **asdict(self),
                "policy_fingerprint": self.policy.fingerprint,
            }
        )


@dataclass(frozen=True)
class RetrievedOccurrence:
    """Content-safe serving observation for one retrieved occurrence."""

    identity: OccurrenceSecurityIdentity
    fact_ids: tuple[str, ...]
    attack_tags: tuple[str, ...] = ()
    currently_authorized: bool = True
    provenance_current: bool = True
    tombstoned: bool = False
    quarantined: bool = False
    content_security_result: SecurityResult = SecurityResult.PASS
    trust: RetrievedContentTrust = RetrievedContentTrust.UNTRUSTED_DATA

    def __post_init__(self) -> None:
        _require_canonical(self.fact_ids, label="fact IDs")
        _require_canonical(self.attack_tags, label="attack tags")
        if self.trust is not RetrievedContentTrust.UNTRUSTED_DATA:
            raise ValueError("retrieved content can only be untrusted data")

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                **asdict(self),
                "identity_fingerprint": self.identity.fingerprint,
            }
        )


@dataclass(frozen=True)
class DeniedOccurrence:
    occurrence_id: str
    reason_code: str

    def __post_init__(self) -> None:
        _require_non_empty(self.occurrence_id, self.reason_code)


@dataclass(frozen=True)
class RetrievalSecurityDecision:
    decision_id: str
    request_binding_fingerprint: str
    candidate_set_digest: str
    result: SecurityResult
    allowed_occurrence_ids: tuple[str, ...]
    denied_occurrences: tuple[DeniedOccurrence, ...]
    evidence_digests: tuple[str, ...]
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.decision_id,
            self.request_binding_fingerprint,
            self.candidate_set_digest,
            self.observed_at,
        )
        _require_unique(
            self.allowed_occurrence_ids,
            label="allowed occurrence IDs",
        )
        denied_ids = tuple(item.occurrence_id for item in self.denied_occurrences)
        _require_unique(denied_ids, label="denied occurrence IDs")
        if set(self.allowed_occurrence_ids).intersection(denied_ids):
            raise ValueError("an occurrence cannot be both allowed and denied")
        _require_canonical(self.evidence_digests, label="evidence digests")
        if self.result is SecurityResult.PASS and not self.evidence_digests:
            raise ValueError("PASS retrieval requires evidence")
        if self.result is not SecurityResult.PASS and self.allowed_occurrence_ids:
            raise ValueError("non-PASS retrieval cannot release occurrences")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class BundleSecurityDecision:
    decision_id: str
    request_binding_fingerprint: str
    retrieval_decision_digest: str
    candidate_set_digest: str
    occurrence_ids_digest: str
    result: SecurityResult
    reason_codes: tuple[str, ...]
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(
            self.decision_id,
            self.request_binding_fingerprint,
            self.retrieval_decision_digest,
            self.candidate_set_digest,
            self.occurrence_ids_digest,
        )
        _require_canonical(self.reason_codes, label="reason codes")
        _require_canonical(self.evidence_digests, label="evidence digests")
        if self.result is SecurityResult.PASS and not self.evidence_digests:
            raise ValueError("PASS bundle analysis requires evidence")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RetrievalBundle:
    bundle_id: str
    request_binding_fingerprint: str
    retrieval_decision_digest: str
    bundle_security_decision_digest: str
    occurrence_ids: tuple[str, ...]
    content_digests: tuple[str, ...]
    authorization_revision: str
    provenance_revision: str
    tombstone_revision: str
    security_policy_version: str
    retrieval_config_version: str
    created_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.bundle_id,
            self.request_binding_fingerprint,
            self.retrieval_decision_digest,
            self.bundle_security_decision_digest,
            self.authorization_revision,
            self.provenance_revision,
            self.tombstone_revision,
            self.security_policy_version,
            self.retrieval_config_version,
            self.created_at,
        )
        _require_unique(self.occurrence_ids, label="bundle occurrence IDs")
        if not self.occurrence_ids:
            raise ValueError("retrieval bundle cannot be empty")
        if len(self.occurrence_ids) != len(self.content_digests):
            raise ValueError("each occurrence requires one content digest")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ContextAssemblyManifest:
    """Content-safe receipt for what actually entered model context."""

    manifest_id: str
    request_binding_fingerprint: str
    retrieval_bundle_digest: str
    included_occurrence_ids: tuple[str, ...]
    included_content_digests: tuple[str, ...]
    excluded_occurrence_ids: tuple[str, ...]
    prompt_template_version: str
    context_assembler_version: str
    envelope_schema_version: str
    serialization_version: str
    projection_version: str
    structured_untrusted_data_digest: str
    context_budget: int
    actual_context_units: int
    assembled_context_digest: str
    bundle_security_decision_digest: str

    def __post_init__(self) -> None:
        required = (
            self.manifest_id,
            self.request_binding_fingerprint,
            self.retrieval_bundle_digest,
            self.prompt_template_version,
            self.context_assembler_version,
            self.envelope_schema_version,
            self.serialization_version,
            self.projection_version,
            self.structured_untrusted_data_digest,
            self.assembled_context_digest,
            self.bundle_security_decision_digest,
        )
        _require_non_empty(*required)
        _require_unique(
            self.included_occurrence_ids,
            label="included occurrence IDs",
        )
        _require_unique(
            self.excluded_occurrence_ids,
            label="excluded occurrence IDs",
        )
        if not self.included_occurrence_ids:
            raise ValueError("assembled context cannot be empty")
        if set(self.included_occurrence_ids).intersection(self.excluded_occurrence_ids):
            raise ValueError("included and excluded occurrences must be disjoint")
        if len(self.included_occurrence_ids) != len(self.included_content_digests):
            raise ValueError("each included occurrence requires a digest")
        if self.context_budget <= 0:
            raise ValueError("context budget must be positive")
        if not 0 < self.actual_context_units <= self.context_budget:
            raise ValueError("actual context must fit the positive budget")
        expected_digest = context_assembly_digest(
            envelope_schema_version=self.envelope_schema_version,
            serialization_version=self.serialization_version,
            projection_version=self.projection_version,
            included_occurrence_ids=self.included_occurrence_ids,
            included_content_digests=self.included_content_digests,
            structured_untrusted_data_digest=(self.structured_untrusted_data_digest),
        )
        if self.assembled_context_digest != expected_digest:
            raise ValueError("assembled context digest does not match projection")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class DisclosureEnvelope:
    """Application-owned maximum permitted disclosure for one request."""

    envelope_id: str
    request_binding_fingerprint: str
    purpose: str
    audience: str
    allowed_fields: tuple[str, ...]
    destination: str
    disclosure_budget: int
    authorization_revision: str
    output_policy_version: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.envelope_id,
            self.request_binding_fingerprint,
            self.purpose,
            self.audience,
            self.destination,
            self.authorization_revision,
            self.output_policy_version,
        )
        _require_canonical(self.allowed_fields, label="allowed fields")
        if not self.allowed_fields or self.disclosure_budget <= 0:
            raise ValueError("disclosure requires fields and a positive budget")
        if self.disclosure_budget > len(self.allowed_fields):
            raise ValueError("disclosure budget cannot exceed allowed fields")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ModelInvocationEnvelope:
    """Application-owned immutable input to one model invocation."""

    envelope_id: str
    request_binding_fingerprint: str
    context_manifest_digest: str
    disclosure_envelope_digest: str
    system_policy_digest: str
    model_id: str
    model_config_digest: str
    tool_policy_version: str
    permitted_tool_capabilities: tuple[str, ...]
    destination_policy_version: str
    retrieved_content_trust: RetrievedContentTrust
    secret_count: int = 0

    def __post_init__(self) -> None:
        _require_non_empty(
            self.envelope_id,
            self.request_binding_fingerprint,
            self.context_manifest_digest,
            self.disclosure_envelope_digest,
            self.system_policy_digest,
            self.model_id,
            self.model_config_digest,
            self.tool_policy_version,
            self.destination_policy_version,
        )
        _require_canonical(
            self.permitted_tool_capabilities,
            label="tool capabilities",
        )
        if self.retrieved_content_trust is not RetrievedContentTrust.UNTRUSTED_DATA:
            raise ValueError("retrieved context must remain untrusted data")
        if self.secret_count != 0:
            raise ValueError("unneeded secrets cannot enter the model envelope")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ProposedCitation:
    claim_id: str
    occurrence_id: str

    def __post_init__(self) -> None:
        _require_non_empty(self.claim_id, self.occurrence_id)


@dataclass(frozen=True)
class AnswerCandidate:
    """Unreleased model output represented without protected answer text."""

    candidate_id: str
    invocation_envelope_digest: str
    answer_digest: str
    claim_ids: tuple[str, ...]
    proposed_citations: tuple[ProposedCitation, ...]
    proposed_tool_calls: tuple[str, ...]
    sensitive_markers: tuple[str, ...]
    generated_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.candidate_id,
            self.invocation_envelope_digest,
            self.answer_digest,
            self.generated_at,
        )
        _require_unique(self.claim_ids, label="claim IDs")
        citation_keys = tuple(
            f"{item.claim_id}:{item.occurrence_id}" for item in self.proposed_citations
        )
        _require_unique(citation_keys, label="proposed citations")
        _require_canonical(
            self.proposed_tool_calls,
            label="proposed tool calls",
        )
        _require_canonical(self.sensitive_markers, label="sensitive markers")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class ReleaseEvidence:
    """Independent grounding, currentness, DLP, and metadata evidence."""

    evidence_id: str
    candidate_digest: str
    observed_claim_ids: tuple[str, ...]
    unclassified_claim_count: int
    grounded_claim_ids: tuple[str, ...]
    supported_citation_keys: tuple[str, ...]
    current_authorization_revision: str
    currently_authorized_occurrence_ids: tuple[str, ...]
    current_provenance_revision: str
    current_tombstone_revision: str
    current_content_security_snapshot_digest: str
    current_security_policy_fingerprint: str
    dlp_result: SecurityResult
    metadata_stripping_result: SecurityResult
    destination_result: SecurityResult
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(
            self.evidence_id,
            self.candidate_digest,
            self.current_authorization_revision,
            self.current_provenance_revision,
            self.current_tombstone_revision,
            self.current_content_security_snapshot_digest,
            self.current_security_policy_fingerprint,
        )
        _require_canonical(self.grounded_claim_ids, label="grounded claim IDs")
        _require_canonical(self.observed_claim_ids, label="observed claim IDs")
        _require_canonical(
            self.supported_citation_keys,
            label="supported citation keys",
        )
        _require_canonical(
            self.currently_authorized_occurrence_ids,
            label="currently authorized occurrence IDs",
        )
        _require_canonical(self.evidence_digests, label="evidence digests")
        if self.unclassified_claim_count < 0:
            raise ValueError("unclassified claim count cannot be negative")
        observed_results = (
            self.dlp_result,
            self.metadata_stripping_result,
            self.destination_result,
        )
        if (
            any(
                result in {SecurityResult.PASS, SecurityResult.FAIL}
                for result in observed_results
            )
            and not self.evidence_digests
        ):
            raise ValueError("observed release checks require evidence")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class OutputReleaseDecision:
    """The only contract allowed to authorize an external response."""

    decision_id: str
    request_binding_fingerprint: str
    candidate_digest: str
    disclosure_envelope_digest: str
    release_evidence_digest: str
    result: SecurityResult
    disposition: SecurityDisposition
    reason_codes: tuple[str, ...]
    released_citation_occurrence_ids: tuple[str, ...]
    observed_at: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self.decision_id,
            self.request_binding_fingerprint,
            self.candidate_digest,
            self.disclosure_envelope_digest,
            self.release_evidence_digest,
            self.observed_at,
        )
        _require_canonical(self.reason_codes, label="reason codes")
        _require_canonical(
            self.released_citation_occurrence_ids,
            label="released citation occurrence IDs",
        )
        if self.result is SecurityResult.PASS:
            if self.disposition not in {
                SecurityDisposition.RELEASE,
                SecurityDisposition.ABSTAIN,
            }:
                raise ValueError("PASS output must RELEASE or ABSTAIN")
            if self.disposition is SecurityDisposition.RELEASE and self.reason_codes:
                raise ValueError("PASS output cannot contain failure reasons")
            if (
                self.disposition is SecurityDisposition.ABSTAIN
                and self.released_citation_occurrence_ids
            ):
                raise ValueError("abstention cannot release citations")
        elif self.disposition is SecurityDisposition.RELEASE:
            raise ValueError("non-PASS output cannot RELEASE")

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class SecurityCaseObservation:
    """Stage-by-stage facts for one normal or adversarial evaluation case."""

    case_id: str
    critical: bool
    evaluator_result: SecurityResult
    attack_document_retrieved: bool
    unauthorized_entered_prompt: bool
    cross_tenant_disclosure: bool
    tombstone_resurrection: bool
    sensitive_output_violation: bool
    protected_metadata_disclosure: bool
    attack_succeeded: bool
    unsafe_rollback_activated: bool
    citations_exact: bool
    normal_quality_passed: bool

    def __post_init__(self) -> None:
        _require_non_empty(self.case_id)

    @property
    def digest(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class SecurityEvaluationReport:
    report_id: str
    policy_fingerprint: str
    adversarial_set_digest: str
    case_digests: tuple[str, ...]
    result: SecurityResult
    hard_gate_results: tuple[tuple[str, SecurityResult], ...]
    evidence_level: str
    not_run_boundaries: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(
            self.report_id,
            self.policy_fingerprint,
            self.adversarial_set_digest,
            self.evidence_level,
        )
        _require_canonical(self.case_digests, label="case digests")
        gate_names = tuple(item[0] for item in self.hard_gate_results)
        _require_unique(gate_names, label="hard gate names")
        _require_canonical(
            self.not_run_boundaries,
            label="NOT_RUN boundaries",
        )

    @property
    def checksum(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class SecurityIncidentRecord:
    """Content-safe append-only incident or correction event."""

    incident_record_id: str
    incident_id: str
    previous_record_id: str | None
    state: IncidentState
    affected_request_ids: tuple[str, ...]
    affected_generation_ids: tuple[str, ...]
    affected_occurrence_ids: tuple[str, ...]
    affected_sinks: tuple[EgressSink, ...]
    containment_actions: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    credential_rotation_status: str
    impact_analysis_digest: str
    actor_id: str
    observed_at: str
    raw_secret_logged: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        _require_non_empty(
            self.incident_record_id,
            self.incident_id,
            self.credential_rotation_status,
            self.impact_analysis_digest,
            self.actor_id,
            self.observed_at,
        )
        _require_canonical(
            self.affected_request_ids,
            label="affected request IDs",
        )
        _require_canonical(
            self.affected_generation_ids,
            label="affected generation IDs",
        )
        _require_canonical(
            self.affected_occurrence_ids,
            label="affected occurrence IDs",
        )
        sink_values = tuple(item.value for item in self.affected_sinks)
        _require_canonical(sink_values, label="affected sinks")
        _require_canonical(
            self.containment_actions,
            label="containment actions",
        )
        _require_canonical(self.evidence_digests, label="evidence digests")
        if self.previous_record_id == self.incident_record_id:
            raise ValueError("incident record cannot supersede itself")
        if self.raw_secret_logged:
            raise ValueError("incident records cannot contain raw secrets")

    @property
    def digest(self) -> str:
        return stable_hash(
            {
                **asdict(self),
                "affected_sinks": tuple(item.value for item in self.affected_sinks),
            }
        )
