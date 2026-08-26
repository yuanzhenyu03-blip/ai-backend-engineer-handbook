"""Day75 deterministic streaming/cache/batch boundary tests.

These tests use pure functions and in-memory models only.  They do not prove
real Provider, HTTP/SSE, Redis, PostgreSQL, queue, Worker, tool, integration,
or production behaviour.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from output_tool_contracts import (  # noqa: E402
    AdmissionStatus,
    AuthContext,
    default_registry,
    default_report_store,
)
from streaming_cache_batching import (  # noqa: E402
    BatchCompatibilityKey,
    BatchEnvelopeStatus,
    BatchItem,
    BatchItemOutcome,
    BatchSummaryStatus,
    BoundedBatchQueue,
    CacheKey,
    CacheLookupStatus,
    CacheSensitivity,
    CacheWriteStatus,
    CacheableCandidate,
    CompleteCandidate,
    CurrentItemState,
    DisconnectEffect,
    InMemoryResponseCache,
    PreDispatchStatus,
    ProviderBatchItemResult,
    QueueAdmissionStatus,
    RecoveryAction,
    StreamAssembler,
    StreamAssemblyStatus,
    StreamEvent,
    StreamEventType,
    admit_cached_candidate,
    admit_complete_candidate,
    cancellation_after_dispatch,
    client_disconnect,
    map_batch_results,
    pre_dispatch_fence,
    summarize_batch,
)


def raw_tool_candidate() -> str:
    return json.dumps(
        {
            "kind": "tool_call",
            "tool_call_id": "tc-1",
            "tool_name": "publish_report",
            "tool_version": "v1",
            "arguments": {
                "tenant_id": "tenant-a",
                "report_id": "report-7",
            },
        }
    )


def stream_event(
    sequence: int,
    event_type: StreamEventType,
    data: str = "",
    **changes: str,
) -> StreamEvent:
    values = {
        "tenant_id": "tenant-a",
        "job_id": "job-1",
        "attempt_id": "A1",
        "stream_id": "stream-1",
    }
    values.update(changes)
    return StreamEvent(
        values["tenant_id"],
        values["job_id"],
        values["attempt_id"],
        values["stream_id"],
        sequence,
        event_type,
        data,
    )


def assembler(max_buffer_bytes: int = 64_000) -> StreamAssembler:
    return StreamAssembler(
        tenant_id="tenant-a",
        job_id="job-1",
        attempt_id="A1",
        stream_id="stream-1",
        max_buffer_bytes=max_buffer_bytes,
    )


def complete_candidate(
    *,
    attempt_id: str = "A1",
    raw_output: str | None = None,
) -> CompleteCandidate:
    return CompleteCandidate(
        "tenant-a",
        "job-1",
        attempt_id,
        "stream-1",
        raw_output if raw_output is not None else raw_tool_candidate(),
    )


def cache_key(
    *,
    tenant_id: str = "tenant-a",
    prompt_revision: str = "v4",
    output_version: str = "output.v1",
) -> CacheKey:
    return CacheKey(
        tenant_id=tenant_id,
        authorization_scope="publisher",
        authorization_policy_version="authz.v3",
        application_contract="research.v1",
        input_fingerprint="sha256:input",
        prompt_contract_id="research_prompt",
        prompt_contract_revision=prompt_revision,
        output_contract_version=output_version,
        tool_contract_version="publish_report.v1",
        provider_profile_revision="profile.v2",
        model_id="model-a",
        cache_policy_version="cache.v1",
    )


def cache_entry(
    *,
    attempt_id: str = "A1",
    resource_version: int = 7,
    created_at: int = 0,
    expires_at: int = 10,
    sensitivity: CacheSensitivity = CacheSensitivity.TENANT_PROTECTED,
) -> CacheableCandidate:
    return CacheableCandidate(
        complete_candidate(attempt_id=attempt_id),
        resource_version,
        created_at,
        expires_at,
        sensitivity,
    )


COMPATIBILITY = BatchCompatibilityKey(
    provider_profile_revision="profile.v2",
    model_id="model-a",
    parameter_policy_revision="params.v1",
    output_contract_version="output.v1",
)


def batch_item(
    number: int,
    *,
    tenant_id: str = "tenant-a",
    compatibility: BatchCompatibilityKey = COMPATIBILITY,
    enqueued_at: int = 0,
    deadline: int = 100,
) -> BatchItem:
    return BatchItem(
        item_id=f"item-{number}",
        tenant_id=tenant_id,
        job_id=f"job-{number}",
        attempt_id=f"A{number}",
        tool_call_id=f"tc-{number}",
        idempotency_key=f"idem-{number}",
        compatibility=compatibility,
        enqueued_at=enqueued_at,
        deadline=deadline,
    )


class Day75StreamingTests(unittest.TestCase):
    def test_partial_delta_only_buffers(self):
        result = assembler().accept(
            stream_event(1, StreamEventType.CONTENT_DELTA, "{")
        )
        self.assertIs(result.status, StreamAssemblyStatus.BUFFERING)
        self.assertIsNone(result.candidate)

    def test_progress_event_is_not_candidate_content(self):
        stream = assembler()
        progress = stream.accept(
            stream_event(1, StreamEventType.PROGRESS, "50%")
        )
        completed = stream.accept(
            stream_event(2, StreamEventType.COMPLETED)
        )
        self.assertEqual(
            progress.safe_reason_code,
            "PROGRESS_OBSERVED_NOT_CANDIDATE_CONTENT",
        )
        self.assertEqual(completed.candidate.raw_output, "")

    def test_ordered_completion_emits_complete_candidate(self):
        raw = raw_tool_candidate()
        middle = len(raw) // 2
        stream = assembler()
        stream.accept(
            stream_event(1, StreamEventType.CONTENT_DELTA, raw[:middle])
        )
        stream.accept(
            stream_event(2, StreamEventType.CONTENT_DELTA, raw[middle:])
        )
        result = stream.accept(stream_event(3, StreamEventType.COMPLETED))
        self.assertIs(
            result.status,
            StreamAssemblyStatus.COMPLETE_CANDIDATE,
        )
        self.assertEqual(result.candidate.raw_output, raw)

    def test_complete_candidate_still_runs_day74_admission(self):
        decision = admit_complete_candidate(
            complete_candidate(),
            registry=default_registry(),
            auth=AuthContext("tenant-a", "user-1", "publisher"),
            reports=default_report_store(),
        )
        self.assertIs(decision.status, AdmissionStatus.ALLOWED)

    def test_sequence_gap_is_malformed_even_if_completed(self):
        stream = assembler()
        stream.accept(
            stream_event(1, StreamEventType.CONTENT_DELTA, "{")
        )
        result = stream.accept(stream_event(3, StreamEventType.COMPLETED))
        self.assertIs(result.status, StreamAssemblyStatus.MALFORMED_STREAM)
        self.assertEqual(result.safe_reason_code, "STREAM_SEQUENCE_MISMATCH")

    def test_duplicate_sequence_is_malformed(self):
        stream = assembler()
        stream.accept(
            stream_event(1, StreamEventType.CONTENT_DELTA, "{")
        )
        result = stream.accept(
            stream_event(1, StreamEventType.CONTENT_DELTA, "}")
        )
        self.assertIs(result.status, StreamAssemblyStatus.MALFORMED_STREAM)

    def test_attempt_identity_mismatch_is_malformed(self):
        result = assembler().accept(
            stream_event(
                1,
                StreamEventType.CONTENT_DELTA,
                "{}",
                attempt_id="A2",
            )
        )
        self.assertEqual(result.safe_reason_code, "STREAM_IDENTITY_MISMATCH")

    def test_error_event_never_emits_candidate(self):
        result = assembler().accept(
            stream_event(1, StreamEventType.ERROR, "safe-code")
        )
        self.assertIs(result.status, StreamAssemblyStatus.STREAM_ERROR)
        self.assertIsNone(result.candidate)

    def test_event_after_completion_is_malformed(self):
        stream = assembler()
        stream.accept(stream_event(1, StreamEventType.COMPLETED))
        result = stream.accept(
            stream_event(2, StreamEventType.CONTENT_DELTA, "late")
        )
        self.assertEqual(result.safe_reason_code, "EVENT_AFTER_TERMINAL")

    def test_buffer_limit_counts_utf8_bytes(self):
        result = assembler(max_buffer_bytes=3).accept(
            stream_event(1, StreamEventType.CONTENT_DELTA, "你好")
        )
        self.assertEqual(
            result.safe_reason_code,
            "STREAM_BUFFER_LIMIT_EXCEEDED",
        )

    def test_client_disconnect_ends_subscription_only(self):
        self.assertIs(
            client_disconnect(),
            DisconnectEffect.SUBSCRIPTION_ENDED_ONLY,
        )


class Day75CacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = InMemoryResponseCache()
        self.key = cache_key()
        self.assertIs(
            self.cache.put(self.key, cache_entry()),
            CacheWriteStatus.STORED,
        )

    def lookup(self, key: CacheKey | None = None, **changes: object):
        values = {
            "now": 5,
            "trusted_tenant_id": "tenant-a",
            "currently_authorized": True,
            "current_resource_version": 7,
        }
        values.update(changes)
        return self.cache.get(key or self.key, **values)

    def test_exact_current_entry_hits_as_candidate(self):
        result = self.lookup()
        self.assertIs(result.status, CacheLookupStatus.HIT)
        self.assertEqual(
            result.safe_reason_code,
            "CACHE_HIT_REQUIRES_CURRENT_ADMISSION",
        )

    def test_tenant_dimension_prevents_cross_tenant_hit(self):
        result = self.lookup(
            cache_key(tenant_id="tenant-b"),
            trusted_tenant_id="tenant-b",
        )
        self.assertIs(result.status, CacheLookupStatus.MISS)

    def test_prompt_revision_prevents_old_result_reinterpretation(self):
        result = self.lookup(cache_key(prompt_revision="v5"))
        self.assertIs(result.status, CacheLookupStatus.MISS)

    def test_output_version_prevents_old_result_reinterpretation(self):
        result = self.lookup(cache_key(output_version="output.v2"))
        self.assertIs(result.status, CacheLookupStatus.MISS)

    def test_ttl_expiry_is_not_a_hit(self):
        self.assertIs(
            self.lookup(now=10).status,
            CacheLookupStatus.EXPIRED,
        )

    def test_unexpired_entry_can_be_stale(self):
        self.assertIs(
            self.lookup(current_resource_version=8).status,
            CacheLookupStatus.STALE_RESOURCE,
        )

    def test_current_authorization_is_required_on_hit(self):
        self.assertIs(
            self.lookup(currently_authorized=False).status,
            CacheLookupStatus.UNAUTHORIZED,
        )

    def test_trusted_tenant_must_match_key(self):
        self.assertIs(
            self.lookup(trusted_tenant_id="tenant-b").status,
            CacheLookupStatus.UNAUTHORIZED,
        )

    def test_secret_candidate_is_not_stored_in_ordinary_cache(self):
        result = self.cache.put(
            cache_key(prompt_revision="secret"),
            cache_entry(sensitivity=CacheSensitivity.SECRET),
        )
        self.assertIs(result, CacheWriteStatus.REJECTED_SECRET)

    def test_invalid_ttl_is_rejected(self):
        result = self.cache.put(
            cache_key(prompt_revision="bad-ttl"),
            cache_entry(created_at=10, expires_at=10),
        )
        self.assertIs(result, CacheWriteStatus.REJECTED_INVALID_TTL)

    def test_key_candidate_tenant_mismatch_is_programming_error(self):
        with self.assertRaises(ValueError):
            self.cache.put(cache_key(tenant_id="tenant-b"), cache_entry())

    def test_invalidate_removes_entry(self):
        self.assertTrue(self.cache.invalidate(self.key))
        self.assertIs(self.lookup().status, CacheLookupStatus.MISS)

    def test_cache_hit_is_readmitted_for_new_attempt(self):
        result = admit_cached_candidate(
            self.lookup(),
            current_attempt_id="A2",
            current_job_id="job-1",
            registry=default_registry(),
            auth=AuthContext("tenant-a", "user-1", "publisher"),
            reports=default_report_store(),
        )
        self.assertIs(result.status, AdmissionStatus.ALLOWED)
        self.assertEqual(result.admitted_call.attempt_id, "A2")

    def test_disabled_tool_rejects_previously_cached_candidate(self):
        registry = default_registry()
        registry.disable("publish_report", "v1")
        result = admit_cached_candidate(
            self.lookup(),
            current_attempt_id="A2",
            current_job_id="job-1",
            registry=registry,
            auth=AuthContext("tenant-a", "user-1", "publisher"),
            reports=default_report_store(),
        )
        self.assertIs(result.status, AdmissionStatus.TOOL_DISABLED)


class Day75BatchTests(unittest.TestCase):
    def queue(
        self,
        *,
        capacity: int = 4,
        max_batch_size: int = 3,
        max_wait: int = 5,
        max_items_per_tenant: int = 2,
    ) -> BoundedBatchQueue:
        return BoundedBatchQueue(
            capacity=capacity,
            max_batch_size=max_batch_size,
            max_wait=max_wait,
            max_items_per_tenant=max_items_per_tenant,
        )

    def test_invalid_queue_limits_fail_closed(self):
        with self.assertRaises(ValueError):
            self.queue(capacity=0)

    def test_duplicate_item_identity_is_not_enqueued_twice(self):
        queue = self.queue()
        item = batch_item(1)
        self.assertIs(queue.admit(item), QueueAdmissionStatus.ACCEPTED)
        self.assertIs(
            queue.admit(item),
            QueueAdmissionStatus.DUPLICATE_ITEM,
        )

    def test_bounded_queue_applies_backpressure(self):
        queue = self.queue(capacity=1)
        queue.admit(batch_item(1))
        self.assertIs(
            queue.admit(batch_item(2)),
            QueueAdmissionStatus.BACKPRESSURE_REJECTED,
        )

    def test_underfilled_batch_waits_before_max_wait(self):
        queue = self.queue()
        queue.admit(batch_item(1))
        self.assertEqual(queue.pop_batch(now=4), ())

    def test_max_wait_flushes_underfilled_batch(self):
        queue = self.queue()
        queue.admit(batch_item(1))
        self.assertEqual(queue.pop_batch(now=5), (batch_item(1),))

    def test_max_batch_size_flushes_without_waiting(self):
        queue = self.queue(max_batch_size=2)
        queue.admit(batch_item(1))
        queue.admit(batch_item(2))
        self.assertEqual(len(queue.pop_batch(now=0)), 2)

    def test_incompatible_items_are_not_mixed(self):
        other = BatchCompatibilityKey(
            "profile.v3", "model-b", "params.v1", "output.v1"
        )
        queue = self.queue(max_batch_size=2)
        queue.admit(batch_item(1))
        queue.admit(batch_item(2, compatibility=other))
        selected = queue.pop_batch(now=5)
        self.assertEqual([item.item_id for item in selected], ["item-1"])
        self.assertEqual(len(queue), 1)

    def test_round_robin_prevents_one_tenant_from_filling_batch(self):
        queue = self.queue(max_batch_size=3, max_items_per_tenant=2)
        queue.admit(batch_item(1, tenant_id="tenant-a"))
        queue.admit(batch_item(2, tenant_id="tenant-a"))
        queue.admit(batch_item(3, tenant_id="tenant-b"))
        selected = queue.pop_batch(now=0)
        self.assertEqual(
            [item.tenant_id for item in selected],
            ["tenant-a", "tenant-b", "tenant-a"],
        )

    def test_pre_dispatch_fence_checks_each_current_fact(self):
        item = batch_item(1)
        cases = (
            (
                CurrentItemState("A1", True, False, False),
                1,
                PreDispatchStatus.READY,
            ),
            (
                CurrentItemState("A2", True, False, False),
                1,
                PreDispatchStatus.STALE_ATTEMPT,
            ),
            (
                CurrentItemState("A1", False, False, False),
                1,
                PreDispatchStatus.UNAUTHORIZED,
            ),
            (
                CurrentItemState("A1", True, True, False),
                1,
                PreDispatchStatus.CANCELLED_BEFORE_DISPATCH,
            ),
            (
                CurrentItemState("A1", True, False, False),
                100,
                PreDispatchStatus.DEADLINE_EXPIRED,
            ),
            (
                CurrentItemState("A1", True, False, True),
                1,
                PreDispatchStatus.TERMINAL_NOOP,
            ),
        )
        for state, now, expected in cases:
            with self.subTest(expected=expected):
                self.assertIs(
                    pre_dispatch_fence(item, state=state, now=now),
                    expected,
                )

    def test_exact_item_ids_preserve_per_item_recovery(self):
        items = (batch_item(1), batch_item(2), batch_item(3))
        decision = map_batch_results(
            items,
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
                ProviderBatchItemResult(
                    "item-2", BatchItemOutcome.UNAUTHORIZED
                ),
                ProviderBatchItemResult(
                    "item-3", BatchItemOutcome.TIMEOUT_UNKNOWN
                ),
            ),
        )
        self.assertIs(decision.status, BatchEnvelopeStatus.MAPPED)
        self.assertEqual(
            [result.recovery for result in decision.item_results],
            [
                RecoveryAction.COMPLETE,
                RecoveryAction.REJECT,
                RecoveryAction.RECONCILE,
            ],
        )

    def test_definitely_not_accepted_retries_only_that_item(self):
        decision = map_batch_results(
            (batch_item(1),),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.DEFINITELY_NOT_ACCEPTED
                ),
            ),
        )
        self.assertIs(
            decision.item_results[0].recovery,
            RecoveryAction.RETRY_NEW_ATTEMPT,
        )

    def test_missing_result_identity_is_envelope_failure(self):
        decision = map_batch_results(
            (batch_item(1), batch_item(2)),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
            ),
        )
        self.assertIs(
            decision.status,
            BatchEnvelopeStatus.ENVELOPE_FAILURE,
        )
        self.assertTrue(
            all(
                result.recovery is RecoveryAction.RECONCILE
                for result in decision.item_results
            )
        )

    def test_duplicate_result_identity_is_envelope_failure(self):
        decision = map_batch_results(
            (batch_item(1), batch_item(2)),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
            ),
        )
        self.assertIs(
            decision.status,
            BatchEnvelopeStatus.ENVELOPE_FAILURE,
        )

    def test_partial_success_is_summary_not_per_item_truth(self):
        decision = map_batch_results(
            (batch_item(1), batch_item(2)),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
                ProviderBatchItemResult(
                    "item-2", BatchItemOutcome.OUTPUT_SCHEMA_INVALID
                ),
            ),
        )
        self.assertIs(
            summarize_batch(decision.item_results),
            BatchSummaryStatus.PARTIAL_SUCCESS,
        )
        self.assertEqual(decision.item_results[1].job_id, "job-2")

    def test_all_guarded_success_summarizes_succeeded(self):
        decision = map_batch_results(
            (batch_item(1), batch_item(2)),
            (
                ProviderBatchItemResult(
                    "item-1", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
                ProviderBatchItemResult(
                    "item-2", BatchItemOutcome.GUARDED_SUCCEEDED
                ),
            ),
        )
        self.assertIs(
            summarize_batch(decision.item_results),
            BatchSummaryStatus.SUCCEEDED,
        )

    def test_cancellation_after_dispatch_requires_reconciliation(self):
        self.assertIs(
            cancellation_after_dispatch(),
            RecoveryAction.RECONCILE,
        )


if __name__ == "__main__":
    unittest.main()
