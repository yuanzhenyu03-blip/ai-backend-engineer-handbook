"""Day87 evidence boundary for framework and job-market research.

The module is deliberately framework-agnostic and deterministic.  It validates
research records and creates a Day88 handoff; it does not select or install an
Agent framework, browse the web, or execute an external Tool.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Iterable, Mapping, Sequence


class SourceType(str, Enum):
    OFFICIAL_DOCS = "OFFICIAL_DOCS"
    OFFICIAL_REPOSITORY = "OFFICIAL_REPOSITORY"
    OFFICIAL_RELEASE = "OFFICIAL_RELEASE"
    PACKAGE_REGISTRY = "PACKAGE_REGISTRY"
    OFFICIAL_ATS = "OFFICIAL_ATS"
    COMPANY_CAREERS = "COMPANY_CAREERS"
    AGGREGATOR = "AGGREGATOR"


class Freshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceKind(str, Enum):
    DOCUMENTATION = "DOCUMENTATION"
    RELEASE = "RELEASE"
    JOB_POSTING = "JOB_POSTING"
    EXECUTED_SPIKE = "EXECUTED_SPIKE"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    SUPERSEDED = "SUPERSEDED"


class ContractFit(str, Enum):
    NATIVE = "NATIVE"
    ADAPTER = "ADAPTER"
    GAP = "GAP"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class PostingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"
    ACCESS_UNAVAILABLE = "ACCESS_UNAVAILABLE"


class RequirementSignal(str, Enum):
    REQUIRED = "REQUIRED"
    PREFERRED = "PREFERRED"
    INCIDENTAL = "INCIDENTAL"
    NOT_MENTIONED = "NOT_MENTIONED"


class Readiness(str, Enum):
    READY = "READY"
    MORE_EVIDENCE_NEEDED = "MORE_EVIDENCE_NEEDED"
    HARD_CONSTRAINT_FAILED = "HARD_CONSTRAINT_FAILED"


PRIMARY_SOURCE_TYPES = frozenset({
    SourceType.OFFICIAL_DOCS,
    SourceType.OFFICIAL_REPOSITORY,
    SourceType.OFFICIAL_RELEASE,
    SourceType.PACKAGE_REGISTRY,
    SourceType.OFFICIAL_ATS,
    SourceType.COMPANY_CAREERS,
})


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    subject: str
    claim: str
    supported_scope: str
    source_url: str
    publisher: str
    source_type: SourceType
    evidence_kind: EvidenceKind
    observed_version: str
    published_or_updated_at: str
    retrieved_at: str
    freshness: Freshness
    conflicting_evidence: str
    confidence: Confidence
    status: EvidenceStatus = EvidenceStatus.VALID


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def validate_evidence(record: EvidenceRecord) -> None:
    """Reject incomplete facts without converting absence into a negative claim."""
    required = {
        "evidence_id": record.evidence_id,
        "subject": record.subject,
        "claim": record.claim,
        "supported_scope": record.supported_scope,
        "source_url": record.source_url,
        "publisher": record.publisher,
        "observed_version": record.observed_version,
        "published_or_updated_at": record.published_or_updated_at,
        "retrieved_at": record.retrieved_at,
    }
    missing = tuple(name for name, value in required.items() if not value.strip())
    if missing:
        raise ValueError(f"missing evidence fields: {','.join(missing)}")
    if not record.source_url.startswith("https://"):
        raise ValueError("source_url must use https")
    if record.published_or_updated_at != "UNKNOWN":
        _parse_timestamp(record.published_or_updated_at, "published_or_updated_at")
    _parse_timestamp(record.retrieved_at, "retrieved_at")
    if record.conflicting_evidence and record.confidence is Confidence.HIGH:
        raise ValueError("conflicting evidence cannot have HIGH confidence")


def eligible_evidence(records: Iterable[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
    accepted = []
    for record in records:
        validate_evidence(record)
        if record.status is EvidenceStatus.VALID:
            accepted.append(record)
    return tuple(accepted)


@dataclass(frozen=True)
class ContractAssessment:
    candidate: str
    contract_id: str
    hard_constraint: bool
    fit: ContractFit
    evidence_ids: tuple[str, ...]
    requires_executed_spike: bool = False


def assessment_is_proven(
    assessment: ContractAssessment,
    evidence_by_id: Mapping[str, EvidenceRecord],
) -> bool:
    if assessment.fit not in (ContractFit.NATIVE, ContractFit.ADAPTER):
        return False
    records = []
    for evidence_id in assessment.evidence_ids:
        record = evidence_by_id.get(evidence_id)
        if record is None or record.status is not EvidenceStatus.VALID:
            return False
        validate_evidence(record)
        if record.source_type not in PRIMARY_SOURCE_TYPES:
            return False
        if record.freshness is not Freshness.CURRENT:
            return False
        records.append(record)
    if not records:
        return False
    if assessment.requires_executed_spike:
        return any(record.evidence_kind is EvidenceKind.EXECUTED_SPIKE for record in records)
    return True


@dataclass(frozen=True)
class JobPosting:
    company: str
    normalized_role: str
    location: str
    posting_id: str
    canonical_url: str
    status: PostingStatus
    source_type: SourceType
    retrieved_at: str
    framework_signal: RequirementSignal
    named_frameworks: tuple[str, ...] = ()

    @property
    def canonical_key(self) -> tuple[str, str, str, str]:
        return (
            self.company.casefold().strip(),
            self.normalized_role.casefold().strip(),
            self.location.casefold().strip(),
            self.posting_id.casefold().strip(),
        )


def dedupe_active_postings(postings: Iterable[JobPosting]) -> tuple[JobPosting, ...]:
    """Keep verified active primary postings; mirrors and unknowns add no count."""
    unique: dict[tuple[str, str, str, str], JobPosting] = {}
    for posting in postings:
        _parse_timestamp(posting.retrieved_at, "retrieved_at")
        if posting.status is not PostingStatus.ACTIVE:
            continue
        if posting.source_type not in {SourceType.OFFICIAL_ATS, SourceType.COMPANY_CAREERS}:
            continue
        unique.setdefault(posting.canonical_key, posting)
    return tuple(unique.values())


def company_concentration(postings: Sequence[JobPosting]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for posting in dedupe_active_postings(postings):
        counts[posting.company] = counts.get(posting.company, 0) + 1
    return counts


def transferable_signal(posting: JobPosting) -> bool:
    """'Framework X or equivalent' is not an X-specific required signal."""
    return bool(posting.named_frameworks) and posting.framework_signal in {
        RequirementSignal.REQUIRED,
        RequirementSignal.PREFERRED,
    }


def sensitivity_is_unstable(score_scenarios: Sequence[Mapping[str, float]]) -> bool:
    if not score_scenarios:
        raise ValueError("at least one score scenario is required")
    winners = set()
    for scenario in score_scenarios:
        if not scenario:
            raise ValueError("score scenario cannot be empty")
        best = max(scenario.values())
        winners.add(tuple(sorted(name for name, score in scenario.items() if score == best)))
    return len(winners) > 1 or any(len(winner) > 1 for winner in winners)


@dataclass(frozen=True)
class Day88Handoff:
    readiness: Readiness
    candidate: str | None
    blocking_contracts: tuple[str, ...]
    discriminating_spike: str | None
    framework_selection_final: bool = False


def build_day88_handoff(
    *,
    candidate: str,
    assessments: Sequence[ContractAssessment],
    evidence: Sequence[EvidenceRecord],
    score_scenarios: Sequence[Mapping[str, float]],
) -> Day88Handoff:
    evidence_by_id = {record.evidence_id: record for record in eligible_evidence(evidence)}
    hard = [item for item in assessments if item.hard_constraint]
    failed = tuple(
        item.contract_id for item in hard
        if item.fit in (ContractFit.GAP, ContractFit.CONFLICT)
    )
    if failed:
        return Day88Handoff(Readiness.HARD_CONSTRAINT_FAILED, None, failed, None)
    unknown = tuple(
        item.contract_id for item in hard
        if not assessment_is_proven(item, evidence_by_id)
    )
    unstable = sensitivity_is_unstable(score_scenarios)
    if unknown or unstable:
        spike = (
            "Route every framework Tool candidate through the application Adapter; "
            "recheck current authorization immediately before dispatch and prove "
            "that every bypass attempt fails closed."
        )
        return Day88Handoff(
            Readiness.MORE_EVIDENCE_NEEDED, candidate, unknown, spike,
        )
    # Day87 may hand over a fully evidenced candidate, but Day88 owns selection.
    return Day88Handoff(Readiness.READY, candidate, (), None)


def supersede_record(record: EvidenceRecord) -> EvidenceRecord:
    """Preserve the record while removing it from current decision inputs."""
    return replace(record, status=EvidenceStatus.SUPERSEDED)
