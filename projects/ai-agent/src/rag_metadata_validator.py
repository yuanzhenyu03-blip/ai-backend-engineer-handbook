"""Pure Day97 metadata validation.

Validation can admit descriptive data.  It cannot manufacture ACLs, grants,
tenant membership, ownership, or any other authority-bearing fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_metadata_contracts import (
    MetadataAssertion,
    MetadataContract,
    MetadataProjectionCandidate,
    MetadataValueType,
)


class MetadataValidationOutcome(str, Enum):
    READY_FOR_COMMIT = "READY_FOR_COMMIT"
    CORRELATION_CONFLICT = "CORRELATION_CONFLICT"
    CONTRACT_CONFLICT = "CONTRACT_CONFLICT"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    AUTHORITY_FIELD_REJECTED = "AUTHORITY_FIELD_REJECTED"
    ORIGIN_REJECTED = "ORIGIN_REJECTED"
    TYPE_REJECTED = "TYPE_REJECTED"
    DUPLICATE_FIELD_CONFLICT = "DUPLICATE_FIELD_CONFLICT"


@dataclass(frozen=True)
class MetadataValidationDecision:
    outcome: MetadataValidationOutcome
    safe_reason: str
    candidate: MetadataProjectionCandidate | None = None
    validation_calls: int = 1
    committer_calls: int = 0
    durable_transitions: int = 0

    @property
    def ready(self) -> bool:
        return self.outcome is MetadataValidationOutcome.READY_FOR_COMMIT

    def __post_init__(self) -> None:
        if self.ready != (self.candidate is not None):
            raise ValueError("only a ready decision carries a candidate")
        if self.committer_calls or self.durable_transitions:
            raise ValueError("metadata validation cannot own durable authority")


class MetadataCandidateValidator:
    _AUTHORITY_NAMES = frozenset({
        "acl",
        "admin",
        "authorization",
        "grant",
        "membership",
        "owner",
        "permissions",
        "role",
        "tenant_id",
    })

    def evaluate(
        self,
        *,
        contract: MetadataContract,
        candidate: MetadataProjectionCandidate,
    ) -> MetadataValidationDecision:
        operation = candidate.operation
        if candidate.attempt.operation_id != operation.operation_id:
            return self._blocked(
                MetadataValidationOutcome.CORRELATION_CONFLICT,
                "METADATA_ATTEMPT_DOES_NOT_BIND_OPERATION",
            )
        if operation.contract_fingerprint != contract.fingerprint:
            return self._blocked(
                MetadataValidationOutcome.CONTRACT_CONFLICT,
                "METADATA_CONTRACT_FINGERPRINT_MISMATCH",
            )

        seen: dict[str, MetadataAssertion] = {}
        for assertion in candidate.assertions:
            leaf_name = assertion.qualified_name.rsplit(".", 1)[-1].lower()
            if leaf_name in self._AUTHORITY_NAMES:
                return self._blocked(
                    MetadataValidationOutcome.AUTHORITY_FIELD_REJECTED,
                    "SOURCE_METADATA_CANNOT_CREATE_AUTHORITY",
                )
            definition = contract.field(assertion.qualified_name)
            if definition is None:
                return self._blocked(
                    MetadataValidationOutcome.UNKNOWN_FIELD,
                    "METADATA_FIELD_NOT_IN_APPLICATION_ALLOWLIST",
                )
            if assertion.origin not in definition.allowed_origins:
                return self._blocked(
                    MetadataValidationOutcome.ORIGIN_REJECTED,
                    "METADATA_ORIGIN_NOT_ALLOWED_FOR_FIELD",
                )
            if not self._value_matches(definition.value_type, assertion.value):
                return self._blocked(
                    MetadataValidationOutcome.TYPE_REJECTED,
                    "METADATA_VALUE_TYPE_MISMATCH",
                )
            previous = seen.get(assertion.qualified_name)
            if previous is not None and previous != assertion:
                return self._blocked(
                    MetadataValidationOutcome.DUPLICATE_FIELD_CONFLICT,
                    "METADATA_FIELD_HAS_CONFLICTING_ASSERTIONS",
                )
            seen[assertion.qualified_name] = assertion

        normalized = tuple(seen[name] for name in sorted(seen))
        accepted = MetadataProjectionCandidate(
            candidate.operation,
            candidate.attempt,
            normalized,
        )
        return MetadataValidationDecision(
            MetadataValidationOutcome.READY_FOR_COMMIT,
            "METADATA_CANDIDATE_VALIDATED",
            candidate=accepted,
        )

    @staticmethod
    def _value_matches(
        expected: MetadataValueType,
        value: object,
    ) -> bool:
        if expected is MetadataValueType.STRING:
            return isinstance(value, str) and bool(value.strip())
        if expected is MetadataValueType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if expected is MetadataValueType.BOOLEAN:
            return isinstance(value, bool)
        if expected is MetadataValueType.STRING_LIST:
            return (
                isinstance(value, tuple)
                and all(isinstance(item, str) and item for item in value)
            )
        return False

    @staticmethod
    def _blocked(
        outcome: MetadataValidationOutcome,
        reason: str,
    ) -> MetadataValidationDecision:
        return MetadataValidationDecision(outcome, reason)
