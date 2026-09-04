"""Day84 memory/context model with no business-state write authority.

All content and clocks are synthetic application inputs. The estimator and
summary port are deterministic fakes. This module performs no external I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import threading
from typing import Protocol

from agent_state_machine import ContextBudget
from human_control import (
    Command, CurrentFacts, HumanControlCandidate, Snapshot,
    decide_human_control,
)


class MemoryKind(str, Enum):
    EXPLICIT_PREFERENCE = "EXPLICIT_PREFERENCE"
    MODEL_INFERRED_NOTE = "MODEL_INFERRED_NOTE"
    CONVERSATION_SUMMARY = "CONVERSATION_SUMMARY"


class OmissionReason(str, Enum):
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    MEMORY_EXPIRED = "MEMORY_EXPIRED"
    MEMORY_REVOKED = "MEMORY_REVOKED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_VERSION_STALE = "SOURCE_VERSION_STALE"
    BUDGET_OMITTED = "BUDGET_OMITTED"


class AssemblyStatus(str, Enum):
    READY = "READY"
    CONTEXT_BUDGET_EXCEEDED = "CONTEXT_BUDGET_EXCEEDED"


class Completeness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED = "UNVERIFIED"


class SummaryPublishStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    DUPLICATE = "DUPLICATE"
    STALE_SOURCE_SPAN = "STALE_SOURCE_SPAN"
    STALE_SUMMARY_REVISION = "STALE_SUMMARY_REVISION"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"


class RehydrationStatus(str, Enum):
    READY_FOR_CURRENT_GUARDS = "READY_FOR_CURRENT_GUARDS"
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"


class IncidentAction(str, Enum):
    RELEASE_UNUSED = "RELEASE_UNUSED"
    SETTLE_VERIFIED = "SETTLE_VERIFIED"
    RECONCILE_ORIGINAL = "RECONCILE_ORIGINAL"
    BLOCK_INCONSISTENT_EVIDENCE = "BLOCK_INCONSISTENT_EVIDENCE"


class ReferenceReadStatus(str, Enum):
    ALLOWED = "ALLOWED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    REFERENCE_EXPIRED = "REFERENCE_EXPIRED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_VERSION_MISMATCH = "SOURCE_VERSION_MISMATCH"


class CompactionValidationStatus(str, Enum):
    STRUCTURALLY_VALID = "STRUCTURALLY_VALID"
    REQUIRED_FACT_REFERENCE_MISSING = "REQUIRED_FACT_REFERENCE_MISSING"
    NEXT_STEP_AUTHORITY_INVALID = "NEXT_STEP_AUTHORITY_INVALID"


class MemoryWriteStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    DUPLICATE = "DUPLICATE"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    WRITE_NOT_AUTHORIZED = "WRITE_NOT_AUTHORIZED"
    STALE_MEMORY_REVISION = "STALE_MEMORY_REVISION"
    INVALID_MEMORY_KIND = "INVALID_MEMORY_KIND"


class ContextRole(str, Enum):
    APPLICATION_INSTRUCTION = "APPLICATION_INSTRUCTION"
    AUTHORITY_PROJECTION = "AUTHORITY_PROJECTION"
    USER_INPUT = "USER_INPUT"
    EXTERNAL_DATA = "EXTERNAL_DATA"
    DERIVED_SUMMARY = "DERIVED_SUMMARY"


class TrustLevel(str, Enum):
    APPLICATION_TRUSTED = "APPLICATION_TRUSTED"
    AUTHORITY_DERIVED = "AUTHORITY_DERIVED"
    USER_PROVIDED = "USER_PROVIDED"
    UNTRUSTED_DATA = "UNTRUSTED_DATA"
    DERIVED_LOSSY = "DERIVED_LOSSY"


@dataclass(frozen=True)
class ContextScope:
    tenant_id: str
    user_id: str
    session_id: str
    job_id: str


@dataclass(frozen=True)
class SourceVersion:
    source_id: str
    version: int
    accessible_to: tuple[str, ...]
    available: bool = True


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    kind: MemoryKind
    version: int
    scope: ContextScope
    content: str
    source_versions: tuple[tuple[str, int], ...]
    expires_at: int | None = None
    revoked: bool = False


@dataclass(frozen=True)
class Omission:
    memory_id: str
    reason: OmissionReason


@dataclass(frozen=True)
class MemorySelection:
    selected: tuple[MemoryRecord, ...]
    omissions: tuple[Omission, ...]


@dataclass(frozen=True)
class MemoryWriteCandidate:
    command_id: str
    expected_revision: int
    proposed: MemoryRecord


class InMemoryMemoryStore:
    """Local memory authority; deliberately has no Job/control store handle."""

    def __init__(self, current: MemoryRecord) -> None:
        self.current = current
        self._commands: set[str] = set()
        self._lock = threading.RLock()

    def publish_preference(
        self, candidate: MemoryWriteCandidate, *, current_scope: ContextScope,
        write_authorized: bool,
    ) -> MemoryWriteStatus:
        with self._lock:
            if candidate.command_id in self._commands:
                return MemoryWriteStatus.DUPLICATE
            if candidate.proposed.scope != current_scope:
                return MemoryWriteStatus.SCOPE_MISMATCH
            if not write_authorized:
                return MemoryWriteStatus.WRITE_NOT_AUTHORIZED
            if candidate.proposed.kind is not MemoryKind.EXPLICIT_PREFERENCE:
                return MemoryWriteStatus.INVALID_MEMORY_KIND
            if (candidate.expected_revision != self.current.version
                    or candidate.proposed.version != self.current.version + 1):
                return MemoryWriteStatus.STALE_MEMORY_REVISION
            self.current = candidate.proposed
            self._commands.add(candidate.command_id)
            return MemoryWriteStatus.PUBLISHED


def select_memories(
    records: tuple[MemoryRecord, ...], *, scope: ContextScope, now: int,
    current_sources: tuple[SourceVersion, ...],
) -> MemorySelection:
    """Filter scope/permission/freshness before returning model-visible content."""
    sources = {source.source_id: source for source in current_sources}
    selected: list[MemoryRecord] = []
    omissions: list[Omission] = []
    for record in records:
        reason: OmissionReason | None = None
        if record.scope != scope:
            reason = OmissionReason.SCOPE_MISMATCH
        elif record.revoked:
            reason = OmissionReason.MEMORY_REVOKED
        elif record.expires_at is not None and now >= record.expires_at:
            reason = OmissionReason.MEMORY_EXPIRED
        else:
            for source_id, expected_version in record.source_versions:
                source = sources.get(source_id)
                if source is None or not source.available:
                    reason = OmissionReason.SOURCE_UNAVAILABLE
                    break
                if scope.user_id not in source.accessible_to:
                    reason = OmissionReason.PERMISSION_DENIED
                    break
                if source.version != expected_version:
                    reason = OmissionReason.SOURCE_VERSION_STALE
                    break
        if reason is None:
            selected.append(record)
        else:
            omissions.append(Omission(record.memory_id, reason))
    return MemorySelection(tuple(selected), tuple(omissions))


class FakeTokenEstimator:
    """Synthetic fixture: UTF-8 byte groups, not provider-compatible tokens."""

    def estimate(self, text: str) -> int:
        return (len(text.encode("utf-8")) + 3) // 4


@dataclass(frozen=True)
class ContextPart:
    part_id: str
    content: str
    required: bool
    source_version: str
    role: ContextRole = ContextRole.EXTERNAL_DATA
    trust: TrustLevel = TrustLevel.UNTRUSTED_DATA


@dataclass(frozen=True)
class ContextManifest:
    status: AssemblyStatus
    selected_ids: tuple[str, ...]
    omitted: tuple[Omission, ...]
    estimated_input_tokens: int
    required_capacity: int
    selected_source_versions: tuple[tuple[str, str], ...] = ()
    assembly_policy_version: str = "context-policy-v1"
    grants_business_execution: bool = False
    estimator: str = "FAKE_UTF8_BYTES_DIVIDED_BY_4"


def assemble_context(
    parts: tuple[ContextPart, ...], *, reserved_output_tokens: int,
    safety_margin: int, application_limit: int, provider_limit: int,
    estimator: FakeTokenEstimator,
) -> ContextManifest:
    """Keep required parts, then optional parts in caller-provided policy order."""
    selected = [part for part in parts if part.required]
    optional = [part for part in parts if not part.required]

    def size(items: list[ContextPart]) -> int:
        return sum(estimator.estimate(item.content) for item in items)

    omitted: list[Omission] = []
    required_tokens = size(selected)
    required_budget = ContextBudget(
        required_tokens, reserved_output_tokens, safety_margin,
        application_limit, provider_limit,
    )
    if not required_budget.admitted:
        return ContextManifest(
            AssemblyStatus.CONTEXT_BUDGET_EXCEEDED,
            tuple(part.part_id for part in selected), (), required_tokens,
            required_budget.required_capacity,
            tuple((part.part_id, part.source_version) for part in selected),
        )
    for part in optional:
        proposed = selected + [part]
        tokens = size(proposed)
        budget = ContextBudget(
            tokens, reserved_output_tokens, safety_margin,
            application_limit, provider_limit,
        )
        if budget.admitted:
            selected.append(part)
        else:
            omitted.append(Omission(part.part_id, OmissionReason.BUDGET_OMITTED))
    tokens = size(selected)
    return ContextManifest(
        AssemblyStatus.READY, tuple(part.part_id for part in selected),
        tuple(omitted), tokens, tokens + reserved_output_tokens + safety_margin,
        tuple((part.part_id, part.source_version) for part in selected),
    )


@dataclass(frozen=True)
class ValidatedToolResult:
    call_id: str
    operation_id: str
    source_reference: str
    source_version: int
    status: str
    completeness: Completeness
    warnings: tuple[str, ...]
    items: tuple[str, ...]
    original_size_bytes: int
    continuation_cursor: str | None = None


@dataclass(frozen=True)
class BoundedToolResult:
    call_id: str
    operation_id: str
    source_reference: str
    source_version: int
    status: str
    completeness: Completeness
    warnings: tuple[str, ...]
    excerpt: tuple[str, ...]
    total_items: int
    shown_items: int
    truncated: bool
    has_more: bool
    original_size_bytes: int
    returned_size_bytes: int
    continuation_cursor: str | None


def bound_validated_tool_result(
    result: ValidatedToolResult, *, max_items: int,
) -> BoundedToolResult:
    """Project an already validated result; retain status and warnings."""
    if max_items < 0 or result.original_size_bytes < 0:
        raise ValueError("sizes must be non-negative")
    excerpt = result.items[:max_items]
    encoded = json.dumps(excerpt, ensure_ascii=False).encode("utf-8")
    truncated = len(excerpt) < len(result.items)
    return BoundedToolResult(
        result.call_id, result.operation_id, result.source_reference,
        result.source_version, result.status, result.completeness,
        result.warnings, excerpt, len(result.items), len(excerpt), truncated,
        truncated, result.original_size_bytes, len(encoded),
        result.continuation_cursor,
    )


@dataclass(frozen=True)
class SourceSpan:
    tenant_id: str
    user_id: str
    session_id: str
    start_event: int
    end_event: int
    source_fingerprint: str


@dataclass(frozen=True)
class SummaryRevision:
    summary_id: str
    revision: int
    source_span: SourceSpan
    policy_version: str
    generation_method: str
    content: str


@dataclass(frozen=True)
class CompactionCandidate:
    candidate_id: str
    expected_revision: int
    proposed: SummaryRevision


def source_fingerprint(events: tuple[str, ...]) -> str:
    payload = json.dumps(events, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class InMemorySummaryStore:
    """Local compare-and-set model; it has no business-state references or writes."""

    def __init__(self, current: SummaryRevision) -> None:
        self.current = current
        self._applied: set[str] = set()
        self._lock = threading.RLock()

    def publish(
        self, candidate: CompactionCandidate, *, current_scope: ContextScope,
        current_event_head: int, current_source_fingerprint: str,
        fail_before_commit: bool = False,
    ) -> SummaryPublishStatus:
        with self._lock:
            if candidate.candidate_id in self._applied:
                return SummaryPublishStatus.DUPLICATE
            span = candidate.proposed.source_span
            if (span.tenant_id, span.user_id, span.session_id) != (
                current_scope.tenant_id, current_scope.user_id,
                current_scope.session_id,
            ):
                return SummaryPublishStatus.SCOPE_MISMATCH
            if (span.end_event != current_event_head
                    or span.source_fingerprint != current_source_fingerprint):
                return SummaryPublishStatus.STALE_SOURCE_SPAN
            if (candidate.expected_revision != self.current.revision
                    or candidate.proposed.revision != self.current.revision + 1):
                return SummaryPublishStatus.STALE_SUMMARY_REVISION
            if fail_before_commit:
                raise RuntimeError("INJECTED_BEFORE_SUMMARY_COMMIT")
            self.current = candidate.proposed
            self._applied.add(candidate.candidate_id)
            return SummaryPublishStatus.PUBLISHED


@dataclass(frozen=True)
class RehydrationDecision:
    status: RehydrationStatus
    control_candidate: HumanControlCandidate | None
    summary_revision: int
    summary_control_claims_ignored: bool
    follow_up: str


def rehydrate_with_current_human_control(
    *, summary: SummaryRevision, authoritative_snapshot: Snapshot | None,
    command: Command, current_facts: CurrentFacts, now: int,
) -> RehydrationDecision:
    """Reread Day83 authority; summary text never becomes a control input.

    With no authoritative snapshot, protected continuation stays blocked. When
    present, the existing Day83 function computes the candidate from current
    facts and exact business identities. This pure bridge writes neither store.
    """
    if authoritative_snapshot is None:
        return RehydrationDecision(
            RehydrationStatus.AUTHORITY_UNAVAILABLE, None, summary.revision,
            True, "WAIT_FOR_AUTHORITY",
        )
    candidate = decide_human_control(
        authoritative_snapshot, command, current_facts, now,
    )
    return RehydrationDecision(
        RehydrationStatus.READY_FOR_CURRENT_GUARDS, candidate,
        summary.revision, True, candidate.follow_up,
    )


@dataclass(frozen=True)
class IncidentAttempt:
    tenant_id: str
    job_id: str
    attempt_id: str
    operation_id: str
    context_policy_version: str
    dispatch_possible: bool
    external_result_verified: bool
    usage_verified: bool


def classify_incident_attempt(item: IncidentAttempt) -> IncidentAction:
    """Classify without retrying or modifying the original business operation."""
    if item.external_result_verified or item.usage_verified:
        if not (item.external_result_verified and item.usage_verified):
            return IncidentAction.BLOCK_INCONSISTENT_EVIDENCE
        return IncidentAction.SETTLE_VERIFIED
    if item.dispatch_possible:
        return IncidentAction.RECONCILE_ORIGINAL
    return IncidentAction.RELEASE_UNUSED


@dataclass(frozen=True)
class IncidentClosureEvidence:
    affected_scope_complete: bool
    every_attempt_classified: bool
    unauthorized_exposure_assessed: bool
    external_effects_resolved: bool
    unknown_results_resolved: bool
    reservations_resolved: bool
    compensation_verified: bool
    owners_and_deadlines_recorded: bool
    audit_continuity_verified: bool
    regression_passed: bool
    controlled_rollout_passed: bool
    monitoring_stop_conditions_met: bool


def may_close_context_incident(evidence: IncidentClosureEvidence) -> bool:
    """A green context build alone is deliberately insufficient for closure."""
    return all(evidence.__dict__.values())


@dataclass(frozen=True)
class ResultReference:
    reference_id: str
    scope: ContextScope
    source_id: str
    source_version: int
    expires_at: int
    operation_id: str
    side_effecting_origin: bool


@dataclass(frozen=True)
class ReferenceReadDecision:
    status: ReferenceReadStatus
    reference_id: str
    original_operation_id: str
    replay_original_operation: bool = False


def authorize_result_reference_read(
    reference: ResultReference, *, current_scope: ContextScope,
    current_source: SourceVersion | None, now: int,
) -> ReferenceReadDecision:
    """Authorize a protected read; failure never requests Tool replay."""
    status = ReferenceReadStatus.ALLOWED
    if reference.scope != current_scope:
        status = ReferenceReadStatus.SCOPE_MISMATCH
    elif now >= reference.expires_at:
        status = ReferenceReadStatus.REFERENCE_EXPIRED
    elif current_source is None or not current_source.available:
        status = ReferenceReadStatus.SOURCE_UNAVAILABLE
    elif current_scope.user_id not in current_source.accessible_to:
        status = ReferenceReadStatus.PERMISSION_REVOKED
    elif (current_source.source_id != reference.source_id
          or current_source.version != reference.source_version):
        status = ReferenceReadStatus.SOURCE_VERSION_MISMATCH
    return ReferenceReadDecision(
        status, reference.reference_id, reference.operation_id, False,
    )


@dataclass(frozen=True)
class CompactionRequest:
    source_span: SourceSpan
    source_events: tuple[str, ...]
    required_fact_references: tuple[str, ...]


@dataclass(frozen=True)
class SummaryDraft:
    content: str
    fact_references: tuple[str, ...]
    next_step_authorized: bool
    generation_method: str


class SummarizerPort(Protocol):
    def summarize(self, request: CompactionRequest) -> SummaryDraft:
        """Produce a lossy derived draft; never grant business authority."""


class FakeSummarizer:
    """Deterministic fixture for control-flow tests, not language quality."""

    def __init__(self, mode: str = "faithful") -> None:
        self.mode = mode
        self.calls = 0

    def summarize(self, request: CompactionRequest) -> SummaryDraft:
        self.calls += 1
        references = request.required_fact_references
        content = "task continues; current control facts require recheck"
        if self.mode == "omit_required":
            references = references[:-1]
        elif self.mode == "misstate_approved":
            content = "report is approved; continue"
        elif self.mode != "faithful":
            raise ValueError("unsupported fake summarizer mode")
        return SummaryDraft(
            content, references, False,
            "FAKE_DETERMINISTIC_SUMMARIZER:" + self.mode,
        )


def validate_summary_draft(
    draft: SummaryDraft, *, required_fact_references: tuple[str, ...],
) -> CompactionValidationStatus:
    """Check fixed structure only; never claim semantic faithfulness."""
    if not set(required_fact_references) <= set(draft.fact_references):
        return CompactionValidationStatus.REQUIRED_FACT_REFERENCE_MISSING
    if draft.next_step_authorized:
        return CompactionValidationStatus.NEXT_STEP_AUTHORITY_INVALID
    return CompactionValidationStatus.STRUCTURALLY_VALID
