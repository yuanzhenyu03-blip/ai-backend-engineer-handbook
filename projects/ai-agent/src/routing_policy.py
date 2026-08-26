"""Day76 routing policy decision model.

This standard-library-only module extends the Day72 Provider Capability Profile
and immutable Attempt execution contract.  It is deterministic in-process
evidence, not a live router, metrics backend, pricing service, or Provider call.
Latency and cost values are fictional policy units used to test boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from provider_contract import (
    AttemptExecutionContract,
    CapabilityProfile,
    ProfileStatus,
)


@dataclass(frozen=True)
class LatencyEvidence:
    """Versioned evidence for one explicitly named latency boundary."""

    profile_id: str
    boundary: str
    p95_ms: int
    observed_at_ms: int
    max_age_ms: int


@dataclass(frozen=True)
class PricingEvidence:
    """Versioned estimate in fictional units; not a real Provider price."""

    profile_id: str
    revision: str
    estimated_units: int
    observed_at_ms: int
    max_age_ms: int


@dataclass(frozen=True)
class Candidate:
    """One Provider/model/Profile execution option plus current evidence."""

    profile: CapabilityProfile
    current_status: ProfileStatus
    latency: LatencyEvidence
    pricing: PricingEvidence


@dataclass(frozen=True)
class RoutingPolicy:
    """Server-owned, versioned rules for NEW routing decisions."""

    policy_id: str
    revision: str
    preference: Tuple[str, ...]
    max_provider_p95_ms: int
    max_estimated_units: int


@dataclass(frozen=True)
class CandidateDecision:
    profile_id: str
    eligible: bool
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class RoutingDecision:
    """Persistable decision evidence; later policy changes do not rewrite it."""

    job_id: str
    attempt_id: str
    policy_id: str
    policy_revision: str
    selected_profile_id: Optional[str]
    pricing_revision: Optional[str]
    candidate_decisions: Tuple[CandidateDecision, ...]
    decided_at_ms: int


def evaluate_candidate(
    candidate: Candidate,
    application_contract: str,
    policy: RoutingPolicy,
    now_ms: int,
) -> CandidateDecision:
    """Apply hard eligibility gates before preference is considered."""

    reasons: list[str] = []
    profile = candidate.profile

    if candidate.current_status is not ProfileStatus.ACTIVE:
        reasons.append("PROFILE_NOT_ACTIVE")
    if not profile.supports(application_contract):
        reasons.append("CONTRACT_INCOMPATIBLE")

    latency = candidate.latency
    if latency.profile_id != profile.profile_id:
        reasons.append("LATENCY_IDENTITY_MISMATCH")
    elif latency.p95_ms < 0 or latency.max_age_ms < 0:
        reasons.append("LATENCY_EVIDENCE_INVALID")
    elif latency.observed_at_ms > now_ms:
        reasons.append("LATENCY_EVIDENCE_FROM_FUTURE")
    elif now_ms - latency.observed_at_ms > latency.max_age_ms:
        reasons.append("LATENCY_STALE")
    elif latency.boundary != "PROVIDER_COMPLETE":
        reasons.append("LATENCY_BOUNDARY_MISMATCH")
    elif latency.p95_ms > policy.max_provider_p95_ms:
        reasons.append("LATENCY_BUDGET_EXCEEDED")

    pricing = candidate.pricing
    if pricing.profile_id != profile.profile_id:
        reasons.append("PRICING_IDENTITY_MISMATCH")
    elif pricing.estimated_units < 0 or pricing.max_age_ms < 0:
        reasons.append("PRICING_EVIDENCE_INVALID")
    elif pricing.observed_at_ms > now_ms:
        reasons.append("PRICING_EVIDENCE_FROM_FUTURE")
    elif now_ms - pricing.observed_at_ms > pricing.max_age_ms:
        reasons.append("PRICING_STALE")
    elif pricing.estimated_units > policy.max_estimated_units:
        reasons.append("COST_BUDGET_EXCEEDED")

    return CandidateDecision(
        profile_id=profile.profile_id,
        eligible=not reasons,
        reasons=tuple(reasons),
    )


def route(
    *,
    job_id: str,
    attempt_id: str,
    application_contract: str,
    policy: RoutingPolicy,
    candidates: Iterable[Candidate],
    now_ms: int,
    client_selector: Optional[str] = None,
) -> tuple[RoutingDecision, Optional[AttemptExecutionContract]]:
    """Select among eligible candidates and bind one NEW Attempt.

    ``client_selector`` may reorder an already eligible candidate.  It cannot
    admit an unknown, disabled, incompatible, stale, over-latency, or over-cost
    candidate.  No selection produces no binding and therefore no dispatch.
    """

    by_id = {}
    for item in candidates:
        profile_id = item.profile.profile_id
        if profile_id in by_id:
            raise ValueError(f"duplicate candidate profile_id: {profile_id}")
        by_id[profile_id] = item

    decisions = tuple(
        evaluate_candidate(item, application_contract, policy, now_ms)
        for item in by_id.values()
    )
    eligible = {item.profile_id for item in decisions if item.eligible}
    order = list(policy.preference)
    if client_selector in eligible:
        order = [client_selector] + [item for item in order if item != client_selector]

    selected_id = next((item for item in order if item in eligible), None)
    selected = by_id.get(selected_id) if selected_id else None
    decision = RoutingDecision(
        job_id=job_id,
        attempt_id=attempt_id,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        selected_profile_id=selected_id,
        pricing_revision=selected.pricing.revision if selected else None,
        candidate_decisions=decisions,
        decided_at_ms=now_ms,
    )
    if selected is None:
        return decision, None

    binding = AttemptExecutionContract.plan(
        attempt_id,
        job_id,
        selected.profile,
        application_contract,
    )
    return decision, binding
