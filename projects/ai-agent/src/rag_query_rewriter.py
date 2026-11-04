"""Bounded deterministic Day101 rewrite reference and validation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from rag_chunking_contracts import stable_hash
from rag_query_rewrite_contracts import (
    ContentSafeRewriteAudit,
    OriginalQueryContract,
    QueryRewriteContract,
    QueryRewriteDegradationPolicy,
    QueryVariant,
    QueryVariantSource,
    QueryVariantValidation,
    RewriteCandidate,
    RewriteEgressPolicy,
    RewriteFailureReason,
    RewriteMode,
    RewriteSet,
    normalized_query_text,
    protected_query_digest,
)


class RewriteProviderMode(str, Enum):
    NORMAL = "NORMAL"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class RewriteError(RuntimeError):
    def __init__(self, reason: RewriteFailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class DeterministicRewriteProvider:
    """A content-safe fake. It is not real rewrite-quality evidence."""

    def __init__(
        self,
        outputs: tuple[RewriteCandidate, ...],
        mode: RewriteProviderMode = RewriteProviderMode.NORMAL,
    ) -> None:
        self._outputs = outputs
        self._mode = mode
        self.calls = 0

    def generate(
        self,
        *,
        original: OriginalQueryContract,
        contract: QueryRewriteContract,
    ) -> tuple[RewriteCandidate, ...]:
        del original, contract
        self.calls += 1
        if self._mode is RewriteProviderMode.FAILED:
            raise RewriteError(RewriteFailureReason.REWRITE_PROVIDER_FAILED)
        if self._mode is RewriteProviderMode.TIMEOUT:
            raise RewriteError(RewriteFailureReason.REWRITE_PROVIDER_TIMEOUT)
        return self._outputs


class ContentSafeRewriteAuditSink:
    def __init__(self) -> None:
        self._events: list[ContentSafeRewriteAudit] = []

    def record(self, event: ContentSafeRewriteAudit) -> None:
        self._events.append(event)

    def events(self) -> tuple[ContentSafeRewriteAudit, ...]:
        return tuple(self._events)


@dataclass(frozen=True)
class RewriteValidationResult:
    accepted: tuple[RewriteCandidate, ...]
    rejected: tuple[tuple[str, str], ...]


class QueryVariantValidator:
    def __init__(
        self,
        scope_oracle: Callable[[OriginalQueryContract, RewriteCandidate], bool],
    ) -> None:
        self._scope_oracle = scope_oracle

    def validate(
        self,
        *,
        original: OriginalQueryContract,
        contract: QueryRewriteContract,
        candidates: tuple[RewriteCandidate, ...],
        digest_secret: bytes,
    ) -> RewriteValidationResult:
        accepted: list[RewriteCandidate] = []
        rejected: list[tuple[str, str]] = []
        seen = {normalized_query_text(original.protected_text)}
        total_bytes = len(original.protected_text.encode("utf-8"))
        for candidate in sorted(candidates, key=lambda item: item.provider_ordinal):
            digest = protected_query_digest(
                digest_secret, original.tenant_id, candidate.protected_text
            )
            reason: str | None = None
            normalized = normalized_query_text(candidate.protected_text)
            encoded_bytes = len(candidate.protected_text.encode("utf-8"))
            if candidate.source not in contract.allowed_sources:
                reason = "REWRITE_SOURCE_NOT_ALLOWED"
            elif candidate.locale != contract.locale:
                reason = "REWRITE_LOCALE_MISMATCH"
            elif not normalized:
                reason = "REWRITE_OUTPUT_EMPTY"
            elif len(candidate.protected_text) > contract.max_variant_chars:
                reason = "REWRITE_VARIANT_TOO_LONG"
            elif normalized in seen:
                reason = "REWRITE_NORMALIZED_DUPLICATE"
            elif len(accepted) >= contract.max_generated_variants:
                reason = RewriteFailureReason.REWRITE_BUDGET_EXHAUSTED.value
            elif total_bytes + encoded_bytes > contract.max_total_utf8_bytes:
                reason = RewriteFailureReason.REWRITE_BUDGET_EXHAUSTED.value
            elif not self._scope_oracle(original, candidate):
                reason = RewriteFailureReason.SEMANTIC_DRIFT_REJECTED.value
            if reason is not None:
                rejected.append((digest, reason))
                continue
            accepted.append(candidate)
            seen.add(normalized)
            total_bytes += encoded_bytes
        return RewriteValidationResult(tuple(accepted), tuple(rejected))


class BoundedQueryRewriter:
    def __init__(
        self,
        *,
        contract: QueryRewriteContract,
        degradation: QueryRewriteDegradationPolicy,
        egress: RewriteEgressPolicy,
        provider: DeterministicRewriteProvider,
        validator: QueryVariantValidator,
        audit: ContentSafeRewriteAuditSink,
        digest_secret: bytes,
    ) -> None:
        self.contract = contract
        self.degradation = degradation
        self.egress = egress
        self.provider = provider
        self.validator = validator
        self.audit = audit
        self._secret = digest_secret

    def rewrite(self, original: OriginalQueryContract) -> RewriteSet:
        reason = RewriteFailureReason.NONE
        candidates: tuple[RewriteCandidate, ...] = ()
        provider_allowed = (
            self.contract.provider in self.egress.allowed_providers
            and self.egress.allow_protected_query_egress
            and self.egress.policy_version == self.contract.egress_policy_version
        )
        if not provider_allowed:
            reason = RewriteFailureReason.REWRITE_EGRESS_DENIED
            if not self.degradation.allow_original_only_on_egress_denied:
                raise RewriteError(reason)
        else:
            try:
                candidates = self.provider.generate(
                    original=original, contract=self.contract
                )
            except RewriteError as exc:
                reason = exc.reason
                allowed = (
                    exc.reason is RewriteFailureReason.REWRITE_PROVIDER_TIMEOUT
                    and self.degradation.allow_original_only_on_timeout
                ) or (
                    exc.reason is RewriteFailureReason.REWRITE_PROVIDER_FAILED
                    and self.degradation.allow_original_only_on_provider_failure
                )
                if not allowed:
                    raise

        validation = self.validator.validate(
            original=original,
            contract=self.contract,
            candidates=candidates,
            digest_secret=self._secret,
        )
        if validation.rejected and not self.degradation.allow_partial_valid_variants:
            raise RewriteError(RewriteFailureReason.REWRITE_OUTPUT_INVALID)

        rewrite_set_id = stable_hash((
            "DAY101_REWRITE_SET",
            original.fingerprint,
            self.contract.fingerprint,
            tuple(
                protected_query_digest(
                    self._secret, original.tenant_id, item.protected_text
                )
                for item in validation.accepted
            ),
        ))
        original_variant = QueryVariant(
            original.operation_id,
            rewrite_set_id,
            stable_hash((rewrite_set_id, 0, original.query_digest)),
            0,
            QueryVariantSource.ORIGINAL,
            original.query_digest,
            self.contract.fingerprint,
            self.contract.locale,
            QueryVariantValidation.APPROVED,
            original.protected_text,
        )
        generated = tuple(
            QueryVariant(
                original.operation_id,
                rewrite_set_id,
                stable_hash((rewrite_set_id, ordinal, protected_query_digest(
                    self._secret, original.tenant_id, candidate.protected_text
                ))),
                ordinal,
                candidate.source,
                protected_query_digest(
                    self._secret, original.tenant_id, candidate.protected_text
                ),
                self.contract.fingerprint,
                candidate.locale,
                QueryVariantValidation.APPROVED,
                candidate.protected_text,
            )
            for ordinal, candidate in enumerate(validation.accepted, start=1)
        )
        if generated and validation.rejected:
            mode = RewriteMode.PARTIAL_REWRITE
        elif generated:
            mode = RewriteMode.FULL_REWRITE
        else:
            mode = RewriteMode.ORIGINAL_ONLY_FALLBACK
            if reason is RewriteFailureReason.NONE and validation.rejected:
                reason = RewriteFailureReason.REWRITE_OUTPUT_INVALID
        result = RewriteSet(
            rewrite_set_id,
            original.fingerprint,
            self.contract.fingerprint,
            self.degradation.fingerprint,
            mode,
            (original_variant,) + generated,
            validation.rejected,
            reason,
        )
        self.audit.record(ContentSafeRewriteAudit(
            original.operation_id,
            original.query_digest,
            rewrite_set_id,
            mode.value,
            len(result.variants),
            len(validation.rejected),
            reason.value,
        ))
        return result
