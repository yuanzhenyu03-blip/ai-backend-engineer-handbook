"""Day100 query-encoder boundary with explicit egress and vector validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import math
import re
from typing import Protocol

from rag_chunking_contracts import stable_hash
from rag_retrieval_contracts import QueryEncoderContract


class QuerySensitivity(str, Enum):
    NORMAL = "NORMAL"
    PII = "PII"
    SUSPECTED_SECRET = "SUSPECTED_SECRET"


class FakeQueryEncoderMode(str, Enum):
    NORMAL = "NORMAL"
    TIMEOUT = "TIMEOUT"
    WRONG_DIMENSIONS = "WRONG_DIMENSIONS"
    NON_FINITE = "NON_FINITE"


@dataclass(frozen=True)
class QueryEgressPolicy:
    policy_version: str
    allowed_providers: frozenset[str]
    allowed_sensitivities: frozenset[QuerySensitivity]
    allow_external: bool

    def __post_init__(self) -> None:
        if not self.policy_version or not self.allowed_providers:
            raise ValueError("query egress policy bindings are required")


@dataclass(frozen=True)
class EncodedQuery:
    query_hash: str
    contract_fingerprint: str
    vector: tuple[float, ...] = field(repr=False)
    sensitivity: QuerySensitivity
    provider: str


class QueryEncodingError(RuntimeError):
    def __init__(self, reason: str, *, provider_called: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.provider_called = provider_called


class QueryEncoderProviderPort(Protocol):
    external: bool

    def encode(
        self,
        *,
        contract: QueryEncoderContract,
        protected_query: str,
    ) -> tuple[float, ...]: ...


class DeterministicFakeQueryEncoder:
    """Content-safe deterministic fake; never evidence for a real Provider."""

    external = False

    def __init__(self, mode: FakeQueryEncoderMode = FakeQueryEncoderMode.NORMAL) -> None:
        self.mode = mode
        self.calls: list[str] = []

    def encode(
        self,
        *,
        contract: QueryEncoderContract,
        protected_query: str,
    ) -> tuple[float, ...]:
        self.calls.append(stable_hash(("QUERY", protected_query)))
        if self.mode is FakeQueryEncoderMode.TIMEOUT:
            raise TimeoutError("QUERY_ENCODER_TIMEOUT")
        digest = hashlib.sha256(protected_query.encode("utf-8")).digest()
        values = tuple(
            ((digest[index % len(digest)] / 255.0) * 2.0) - 1.0
            for index in range(contract.dimensions)
        )
        norm = math.sqrt(sum(value * value for value in values))
        vector = tuple(value / norm for value in values)
        if self.mode is FakeQueryEncoderMode.WRONG_DIMENSIONS:
            return vector + (0.0,)
        if self.mode is FakeQueryEncoderMode.NON_FINITE:
            return (float("nan"),) + vector[1:]
        return vector


class QueryEncoderAdapter:
    def __init__(
        self,
        *,
        contract: QueryEncoderContract,
        provider: QueryEncoderProviderPort,
        egress_policy: QueryEgressPolicy,
    ) -> None:
        self.contract = contract
        self.provider = provider
        self.egress_policy = egress_policy

    @property
    def calls(self) -> int:
        calls = getattr(self.provider, "calls", ())
        return len(calls)

    def encode(
        self,
        *,
        query_text: str,
        expected_contract_fingerprint: str,
    ) -> EncodedQuery:
        if expected_contract_fingerprint != self.contract.fingerprint:
            raise QueryEncodingError(
                "QUERY_ENCODER_CONTRACT_MISMATCH", provider_called=False
            )
        sensitivity = classify_query_sensitivity(query_text)
        if self.contract.egress_policy_version != self.egress_policy.policy_version:
            raise QueryEncodingError(
                "QUERY_EGRESS_POLICY_VERSION_MISMATCH", provider_called=False
            )
        if self.contract.provider not in self.egress_policy.allowed_providers:
            raise QueryEncodingError(
                "QUERY_PROVIDER_NOT_ALLOWED", provider_called=False
            )
        if sensitivity not in self.egress_policy.allowed_sensitivities:
            raise QueryEncodingError(
                "QUERY_EGRESS_SENSITIVITY_DENIED", provider_called=False
            )
        if self.provider.external and not self.egress_policy.allow_external:
            raise QueryEncodingError(
                "EXTERNAL_QUERY_EGRESS_DENIED", provider_called=False
            )
        protected_query = self.contract.query_prefix + query_text
        try:
            vector = self.provider.encode(
                contract=self.contract,
                protected_query=protected_query,
            )
        except TimeoutError as exc:
            raise QueryEncodingError(
                "QUERY_ENCODER_TIMEOUT", provider_called=True
            ) from exc
        if len(vector) != self.contract.dimensions:
            raise QueryEncodingError(
                "QUERY_ENCODER_DIMENSIONS_MISMATCH", provider_called=True
            )
        if any(not math.isfinite(value) for value in vector):
            raise QueryEncodingError(
                "QUERY_ENCODER_NON_FINITE_VECTOR", provider_called=True
            )
        norm = math.sqrt(sum(value * value for value in vector))
        if self.contract.normalization == "UNIT_L2" and not math.isclose(
            norm, 1.0, rel_tol=1e-6, abs_tol=1e-6
        ):
            raise QueryEncodingError(
                "QUERY_ENCODER_NORMALIZATION_MISMATCH", provider_called=True
            )
        return EncodedQuery(
            stable_hash(("PROTECTED_QUERY", query_text)),
            self.contract.fingerprint,
            vector,
            sensitivity,
            self.contract.provider,
        )


def classify_query_sensitivity(query_text: str) -> QuerySensitivity:
    secret_pattern = re.compile(
        r"(?:sk-[A-Za-z0-9_-]{6,}|api[_-]?key\s*[:=]|bearer\s+[A-Za-z0-9._-]+)",
        re.IGNORECASE,
    )
    email_pattern = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
    if secret_pattern.search(query_text):
        return QuerySensitivity.SUSPECTED_SECRET
    if email_pattern.search(query_text):
        return QuerySensitivity.PII
    return QuerySensitivity.NORMAL
