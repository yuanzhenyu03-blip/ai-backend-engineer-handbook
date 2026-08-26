"""Day75 streaming, caching, and batching boundaries for LLM applications.

The module extends Day74 without weakening it:

* streaming may emit a complete candidate, never an admitted tool call;
* a cache hit is a reusable candidate, never current authorization or truth;
* a batch groups transport work, never tenant/Job/Attempt authority.

Everything here is deterministic and in process.  It is not evidence for a
real Provider stream, Redis, PostgreSQL, a distributed queue, an external
tool, integration runtime, or production behaviour.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Dict, Iterable, Optional, Tuple

from output_tool_contracts import (
    AdmissionDecision,
    AuthContext,
    InMemoryReportStore,
    ToolRegistry,
    admit_tool_call,
)


class StreamEventType(str, Enum):
    CONTENT_DELTA = "CONTENT_DELTA"
    PROGRESS = "PROGRESS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class StreamAssemblyStatus(str, Enum):
    BUFFERING = "BUFFERING"
    COMPLETE_CANDIDATE = "COMPLETE_CANDIDATE"
    MALFORMED_STREAM = "MALFORMED_STREAM"
    STREAM_ERROR = "STREAM_ERROR"


class DisconnectEffect(str, Enum):
    SUBSCRIPTION_ENDED_ONLY = "SUBSCRIPTION_ENDED_ONLY"


@dataclass(frozen=True)
class StreamEvent:
    tenant_id: str
    job_id: str
    attempt_id: str
    stream_id: str
    sequence: int
    event_type: StreamEventType
    data: str = ""


@dataclass(frozen=True)
class CompleteCandidate:
    tenant_id: str
    job_id: str
    attempt_id: str
    stream_id: str
    raw_output: str


@dataclass(frozen=True)
class StreamAssemblyDecision:
    status: StreamAssemblyStatus
    safe_reason_code: str
    candidate: Optional[CompleteCandidate] = None


class StreamAssembler:
    """Validate one stream identity and assemble monotonic content events."""

    def __init__(
        self,
        *,
        tenant_id: str,
        job_id: str,
        attempt_id: str,
        stream_id: str,
        max_buffer_bytes: int = 64_000,
    ) -> None:
        if max_buffer_bytes <= 0:
            raise ValueError("max_buffer_bytes must be positive")
        self._tenant_id = tenant_id
        self._job_id = job_id
        self._attempt_id = attempt_id
        self._stream_id = stream_id
        self._max_buffer_bytes = max_buffer_bytes
        self._next_sequence = 1
        self._buffer_bytes = 0
        self._parts: list[str] = []
        self._terminal = False

    def accept(self, event: StreamEvent) -> StreamAssemblyDecision:
        if self._terminal:
            return StreamAssemblyDecision(
                StreamAssemblyStatus.MALFORMED_STREAM,
                "EVENT_AFTER_TERMINAL",
            )
        if (
            event.tenant_id != self._tenant_id
            or event.job_id != self._job_id
            or event.attempt_id != self._attempt_id
            or event.stream_id != self._stream_id
        ):
            self._terminal = True
            return StreamAssemblyDecision(
                StreamAssemblyStatus.MALFORMED_STREAM,
                "STREAM_IDENTITY_MISMATCH",
            )
        if event.sequence != self._next_sequence:
            self._terminal = True
            return StreamAssemblyDecision(
                StreamAssemblyStatus.MALFORMED_STREAM,
                "STREAM_SEQUENCE_MISMATCH",
            )
        self._next_sequence += 1

        if event.event_type is StreamEventType.CONTENT_DELTA:
            delta_bytes = len(event.data.encode("utf-8"))
            if self._buffer_bytes + delta_bytes > self._max_buffer_bytes:
                self._terminal = True
                return StreamAssemblyDecision(
                    StreamAssemblyStatus.MALFORMED_STREAM,
                    "STREAM_BUFFER_LIMIT_EXCEEDED",
                )
            self._parts.append(event.data)
            self._buffer_bytes += delta_bytes
            return StreamAssemblyDecision(
                StreamAssemblyStatus.BUFFERING,
                "CONTENT_BUFFERED",
            )

        if event.event_type is StreamEventType.PROGRESS:
            return StreamAssemblyDecision(
                StreamAssemblyStatus.BUFFERING,
                "PROGRESS_OBSERVED_NOT_CANDIDATE_CONTENT",
            )

        self._terminal = True
        if event.event_type is StreamEventType.ERROR:
            return StreamAssemblyDecision(
                StreamAssemblyStatus.STREAM_ERROR,
                "PROVIDER_STREAM_ERROR",
            )

        candidate = CompleteCandidate(
            tenant_id=self._tenant_id,
            job_id=self._job_id,
            attempt_id=self._attempt_id,
            stream_id=self._stream_id,
            raw_output="".join(self._parts),
        )
        return StreamAssemblyDecision(
            StreamAssemblyStatus.COMPLETE_CANDIDATE,
            "STREAM_COMPLETED",
            candidate,
        )


def client_disconnect() -> DisconnectEffect:
    """A client disconnect changes no Provider or durable Job fact."""

    return DisconnectEffect.SUBSCRIPTION_ENDED_ONLY


def admit_complete_candidate(
    candidate: CompleteCandidate,
    *,
    registry: ToolRegistry,
    auth: AuthContext,
    reports: InMemoryReportStore,
) -> AdmissionDecision:
    """Run a complete streamed candidate through the unchanged Day74 gate."""

    return admit_tool_call(
        candidate.raw_output,
        attempt_id=candidate.attempt_id,
        job_id=candidate.job_id,
        registry=registry,
        auth=auth,
        reports=reports,
    )


@dataclass(frozen=True)
class CacheKey:
    tenant_id: str
    authorization_scope: str
    authorization_policy_version: str
    application_contract: str
    input_fingerprint: str
    prompt_contract_id: str
    prompt_contract_revision: str
    output_contract_version: str
    tool_contract_version: str
    provider_profile_revision: str
    model_id: str
    cache_policy_version: str


class CacheSensitivity(str, Enum):
    TENANT_PROTECTED = "TENANT_PROTECTED"
    SECRET = "SECRET"


@dataclass(frozen=True)
class CacheableCandidate:
    """A complete candidate copy; never an AdmittedToolCall or permission."""

    candidate: CompleteCandidate
    resource_version: int
    created_at: int
    expires_at: int
    sensitivity: CacheSensitivity = CacheSensitivity.TENANT_PROTECTED


class CacheWriteStatus(str, Enum):
    STORED = "STORED"
    REJECTED_SECRET = "REJECTED_SECRET"
    REJECTED_INVALID_TTL = "REJECTED_INVALID_TTL"


class CacheLookupStatus(str, Enum):
    HIT = "HIT"
    MISS = "MISS"
    EXPIRED = "EXPIRED"
    STALE_RESOURCE = "STALE_RESOURCE"
    UNAUTHORIZED = "UNAUTHORIZED"


@dataclass(frozen=True)
class CacheLookupDecision:
    status: CacheLookupStatus
    safe_reason_code: str
    candidate: Optional[CompleteCandidate] = None


class InMemoryResponseCache:
    """Exact-key candidate cache; not durable truth or distributed evidence."""

    def __init__(self) -> None:
        self._entries: Dict[CacheKey, CacheableCandidate] = {}

    def put(
        self,
        key: CacheKey,
        entry: CacheableCandidate,
    ) -> CacheWriteStatus:
        if entry.sensitivity is CacheSensitivity.SECRET:
            return CacheWriteStatus.REJECTED_SECRET
        if entry.expires_at <= entry.created_at:
            return CacheWriteStatus.REJECTED_INVALID_TTL
        if entry.candidate.tenant_id != key.tenant_id:
            raise ValueError("cache key tenant does not match candidate tenant")
        self._entries[key] = entry
        return CacheWriteStatus.STORED

    def get(
        self,
        key: CacheKey,
        *,
        now: int,
        trusted_tenant_id: str,
        currently_authorized: bool,
        current_resource_version: int,
    ) -> CacheLookupDecision:
        if trusted_tenant_id != key.tenant_id or not currently_authorized:
            return CacheLookupDecision(
                CacheLookupStatus.UNAUTHORIZED,
                "CURRENT_AUTHORIZATION_REQUIRED",
            )
        entry = self._entries.get(key)
        if entry is None:
            return CacheLookupDecision(CacheLookupStatus.MISS, "CACHE_MISS")
        if now >= entry.expires_at:
            return CacheLookupDecision(
                CacheLookupStatus.EXPIRED,
                "CACHE_ENTRY_EXPIRED",
            )
        if entry.resource_version != current_resource_version:
            return CacheLookupDecision(
                CacheLookupStatus.STALE_RESOURCE,
                "CACHE_RESOURCE_VERSION_STALE",
            )
        return CacheLookupDecision(
            CacheLookupStatus.HIT,
            "CACHE_HIT_REQUIRES_CURRENT_ADMISSION",
            entry.candidate,
        )

    def invalidate(self, key: CacheKey) -> bool:
        return self._entries.pop(key, None) is not None

    def invalidate_tenant(self, tenant_id: str) -> int:
        keys = [key for key in self._entries if key.tenant_id == tenant_id]
        for key in keys:
            del self._entries[key]
        return len(keys)


def admit_cached_candidate(
    decision: CacheLookupDecision,
    *,
    current_attempt_id: str,
    current_job_id: str,
    registry: ToolRegistry,
    auth: AuthContext,
    reports: InMemoryReportStore,
) -> AdmissionDecision:
    """Rebind a hit to current identity and rerun Day74 Admission."""

    if decision.status is not CacheLookupStatus.HIT:
        raise ValueError("only a cache hit can be considered for Admission")
    if decision.candidate is None:
        raise ValueError("cache hit is missing its candidate")
    return admit_tool_call(
        decision.candidate.raw_output,
        attempt_id=current_attempt_id,
        job_id=current_job_id,
        registry=registry,
        auth=auth,
        reports=reports,
    )


@dataclass(frozen=True)
class BatchCompatibilityKey:
    provider_profile_revision: str
    model_id: str
    parameter_policy_revision: str
    output_contract_version: str


@dataclass(frozen=True)
class BatchItem:
    item_id: str
    tenant_id: str
    job_id: str
    attempt_id: str
    tool_call_id: str
    idempotency_key: str
    compatibility: BatchCompatibilityKey
    enqueued_at: int
    deadline: int


class QueueAdmissionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE_ITEM = "DUPLICATE_ITEM"
    BACKPRESSURE_REJECTED = "BACKPRESSURE_REJECTED"


class BoundedBatchQueue:
    """Bounded deterministic queue with per-batch tenant round-robin."""

    def __init__(
        self,
        *,
        capacity: int,
        max_batch_size: int,
        max_wait: int,
        max_items_per_tenant: int,
    ) -> None:
        if min(capacity, max_batch_size, max_wait, max_items_per_tenant) <= 0:
            raise ValueError("queue limits must be positive")
        self._capacity = capacity
        self._max_batch_size = max_batch_size
        self._max_wait = max_wait
        self._max_items_per_tenant = max_items_per_tenant
        self._items: Deque[BatchItem] = deque()
        self._ids: set[str] = set()

    def admit(self, item: BatchItem) -> QueueAdmissionStatus:
        if item.item_id in self._ids:
            return QueueAdmissionStatus.DUPLICATE_ITEM
        if len(self._items) >= self._capacity:
            return QueueAdmissionStatus.BACKPRESSURE_REJECTED
        self._items.append(item)
        self._ids.add(item.item_id)
        return QueueAdmissionStatus.ACCEPTED

    def should_flush(self, *, now: int) -> bool:
        if not self._items:
            return False
        compatible_count = sum(
            item.compatibility == self._items[0].compatibility
            for item in self._items
        )
        oldest_wait = now - self._items[0].enqueued_at
        return (
            compatible_count >= self._max_batch_size
            or oldest_wait >= self._max_wait
        )

    def pop_batch(self, *, now: int) -> Tuple[BatchItem, ...]:
        if not self.should_flush(now=now):
            return ()
        compatibility = self._items[0].compatibility
        compatible = [
            item for item in self._items if item.compatibility == compatibility
        ]
        tenant_order: list[str] = []
        by_tenant: Dict[str, Deque[BatchItem]] = {}
        for item in compatible:
            if item.tenant_id not in by_tenant:
                tenant_order.append(item.tenant_id)
                by_tenant[item.tenant_id] = deque()
            by_tenant[item.tenant_id].append(item)

        selected: list[BatchItem] = []
        tenant_counts: Dict[str, int] = {tenant: 0 for tenant in tenant_order}
        while len(selected) < self._max_batch_size:
            progress = False
            for tenant_id in tenant_order:
                if len(selected) >= self._max_batch_size:
                    break
                if tenant_counts[tenant_id] >= self._max_items_per_tenant:
                    continue
                queue = by_tenant[tenant_id]
                if not queue:
                    continue
                selected.append(queue.popleft())
                tenant_counts[tenant_id] += 1
                progress = True
            if not progress:
                break

        selected_ids = {item.item_id for item in selected}
        self._items = deque(
            item for item in self._items if item.item_id not in selected_ids
        )
        self._ids.difference_update(selected_ids)
        return tuple(selected)

    def __len__(self) -> int:
        return len(self._items)


@dataclass(frozen=True)
class CurrentItemState:
    current_attempt_id: str
    authorized: bool
    cancellation_requested: bool
    terminal: bool


class PreDispatchStatus(str, Enum):
    READY = "READY"
    STALE_ATTEMPT = "STALE_ATTEMPT"
    UNAUTHORIZED = "UNAUTHORIZED"
    CANCELLED_BEFORE_DISPATCH = "CANCELLED_BEFORE_DISPATCH"
    DEADLINE_EXPIRED = "DEADLINE_EXPIRED"
    TERMINAL_NOOP = "TERMINAL_NOOP"


def pre_dispatch_fence(
    item: BatchItem,
    *,
    state: CurrentItemState,
    now: int,
) -> PreDispatchStatus:
    if state.terminal:
        return PreDispatchStatus.TERMINAL_NOOP
    if state.current_attempt_id != item.attempt_id:
        return PreDispatchStatus.STALE_ATTEMPT
    if not state.authorized:
        return PreDispatchStatus.UNAUTHORIZED
    if state.cancellation_requested:
        return PreDispatchStatus.CANCELLED_BEFORE_DISPATCH
    if now >= item.deadline:
        return PreDispatchStatus.DEADLINE_EXPIRED
    return PreDispatchStatus.READY


class BatchItemOutcome(str, Enum):
    GUARDED_SUCCEEDED = "GUARDED_SUCCEEDED"
    OUTPUT_SCHEMA_INVALID = "OUTPUT_SCHEMA_INVALID"
    DEFINITELY_NOT_ACCEPTED = "DEFINITELY_NOT_ACCEPTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"


class RecoveryAction(str, Enum):
    COMPLETE = "COMPLETE"
    REJECT = "REJECT"
    RETRY_NEW_ATTEMPT = "RETRY_NEW_ATTEMPT"
    RECONCILE = "RECONCILE"


@dataclass(frozen=True)
class ProviderBatchItemResult:
    item_id: str
    outcome: BatchItemOutcome


@dataclass(frozen=True)
class BatchItemResult:
    item_id: str
    tenant_id: str
    job_id: str
    attempt_id: str
    outcome: BatchItemOutcome
    recovery: RecoveryAction


class BatchEnvelopeStatus(str, Enum):
    MAPPED = "MAPPED"
    ENVELOPE_FAILURE = "ENVELOPE_FAILURE"


class BatchSummaryStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED_OR_UNRESOLVED = "FAILED_OR_UNRESOLVED"


@dataclass(frozen=True)
class BatchResultDecision:
    status: BatchEnvelopeStatus
    safe_reason_code: str
    item_results: Tuple[BatchItemResult, ...]


def recovery_for_outcome(outcome: BatchItemOutcome) -> RecoveryAction:
    if outcome is BatchItemOutcome.GUARDED_SUCCEEDED:
        return RecoveryAction.COMPLETE
    if outcome is BatchItemOutcome.DEFINITELY_NOT_ACCEPTED:
        return RecoveryAction.RETRY_NEW_ATTEMPT
    if outcome is BatchItemOutcome.TIMEOUT_UNKNOWN:
        return RecoveryAction.RECONCILE
    return RecoveryAction.REJECT


def map_batch_results(
    items: Iterable[BatchItem],
    provider_results: Iterable[ProviderBatchItemResult],
) -> BatchResultDecision:
    item_tuple = tuple(items)
    result_tuple = tuple(provider_results)
    item_by_id = {item.item_id: item for item in item_tuple}
    result_ids = [result.item_id for result in result_tuple]
    exact_identity = (
        len(item_by_id) == len(item_tuple)
        and len(set(result_ids)) == len(result_ids)
        and set(result_ids) == set(item_by_id)
    )
    if not exact_identity:
        unresolved = tuple(
            BatchItemResult(
                item.item_id,
                item.tenant_id,
                item.job_id,
                item.attempt_id,
                BatchItemOutcome.TIMEOUT_UNKNOWN,
                RecoveryAction.RECONCILE,
            )
            for item in item_tuple
        )
        return BatchResultDecision(
            BatchEnvelopeStatus.ENVELOPE_FAILURE,
            "BATCH_RESULT_IDENTITY_UNRELIABLE",
            unresolved,
        )

    mapped = tuple(
        BatchItemResult(
            result.item_id,
            item_by_id[result.item_id].tenant_id,
            item_by_id[result.item_id].job_id,
            item_by_id[result.item_id].attempt_id,
            result.outcome,
            recovery_for_outcome(result.outcome),
        )
        for result in result_tuple
    )
    return BatchResultDecision(
        BatchEnvelopeStatus.MAPPED,
        "BATCH_RESULTS_MAPPED_BY_EXACT_ITEM_ID",
        mapped,
    )


def summarize_batch(
    item_results: Iterable[BatchItemResult],
) -> BatchSummaryStatus:
    results = tuple(item_results)
    if results and all(
        result.outcome is BatchItemOutcome.GUARDED_SUCCEEDED
        for result in results
    ):
        return BatchSummaryStatus.SUCCEEDED
    if any(
        result.outcome is BatchItemOutcome.GUARDED_SUCCEEDED
        for result in results
    ):
        return BatchSummaryStatus.PARTIAL_SUCCESS
    return BatchSummaryStatus.FAILED_OR_UNRESOLVED


def cancellation_after_dispatch() -> RecoveryAction:
    """Best-effort cancellation does not prove remote non-execution."""

    return RecoveryAction.RECONCILE
