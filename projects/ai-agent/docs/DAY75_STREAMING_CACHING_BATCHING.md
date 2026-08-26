# Day75 — Streaming, Caching and Batching

## Scope

Day75 improves delivery latency, safe reuse and throughput without weakening Day74. The implementation is a
standard-library, in-process decision model. It does not implement real SSE/HTTP, Redis, PostgreSQL, a queue,
cross-process coordination, a Provider or an external tool.

## Files

- `src/streaming_cache_batching.py`: streaming assembly, response-cache policy and bounded fair batching.
- `tests/test_streaming_cache_batching.py`: deterministic Day75 boundary tests.
- `src/output_tool_contracts.py`: reused Day74 admission and guarded-completion contracts.

## 1. Non-negotiable boundary

```text
stream chunks -> CompleteCandidate -> Day74 Parse/Schema/Registry/Auth/Semantics/Admission
cache entry   -> current candidate -> Day74 current Admission
batch item    -> independent result -> Day74 verification/guarded completion or reconciliation
```

Streaming does not prove completeness, caching does not prove current truth or permission, and batching does
not merge identity or outcomes.

## 2. Streaming assembly

`StreamAssembler` binds trusted `tenant_id`, `job_id`, `attempt_id` and `stream_id`. It accepts framed event
types with an exact monotonic sequence and a bounded UTF-8 buffer. `DELTA` appends bytes; `PROGRESS` is safe
metadata rather than candidate content; `COMPLETED` emits one `CompleteCandidate`; `ERROR`, a sequence gap,
identity mismatch, buffer overflow or post-terminal event fails closed.

A completion marker is necessary but insufficient: the emitted candidate still passes Day74. A client
disconnect returns `SUBSCRIPTION_ONLY`; it does not change Provider execution or durable Job truth.

## 3. Cache identity and policy

`CacheKey` covers trusted tenant, authorization scope/policy, canonical input fingerprint, Prompt revision,
Output/Tool contract versions, Provider/model/Capability Profile and cache-policy version. Exact-key lookup is
required; no historical result is reinterpreted under a new contract.

`InMemoryResponseCache` rejects secret material and invalid TTLs. A hit is usable only when TTL, resource
version and current authorization all pass. TTL is a maximum age, not a truth lease. Entries remain
discardable copies and may be invalidated at any time.

`admit_cached_candidate` creates a candidate for the current Job/Attempt and reruns Day74 Admission. It never
reuses an old `AdmittedToolCall`.

## 4. Batch planning

`BoundedBatchQueue` partitions by a compatibility key, caps total/per-tenant queued items, rejects duplicate
item identity, flushes at maximum size or wait, and selects tenants round-robin with a per-batch tenant cap.
The queue is an in-process teaching model; production fairness and backpressure require durable/distributed
enforcement.

Every `BatchItem` retains tenant, Job, Attempt, contract/profile, tool-call and idempotency identity. Before
dispatch, `pre_dispatch_fence` checks current persisted-style facts per item. Cancelled, terminal, stale,
unauthorized or expired items do not ride along with valid items.

## 5. Per-item results and recovery

`map_batch_results` requires an exact one-to-one item-id mapping. Missing, duplicate or unknown identities make
the envelope unreliable; dispatched items become `TIMEOUT_UNKNOWN` and require reconciliation rather than
positional guessing.

```text
SUCCEEDED               -> guarded completion
DEFINITELY_NOT_ACCEPTED -> retry policy may create a new Attempt for this item
UNAUTHORIZED / INVALID  -> reject
TIMEOUT_UNKNOWN         -> reconcile, never blind retry
```

`PARTIAL_SUCCESS` is only an operational summary. Each item stores its actual result. Cancellation after
dispatch likewise maps to reconciliation when non-execution cannot be proven.

## 6. Incident containment

For a bad cache policy that omitted tenant identity and promoted partial streams:

1. disable/rollback the policy, force bypass and invalidate/quarantine the affected namespace;
2. reject partial, non-admitted candidates; optionally create a new safe Attempt;
3. use the final kill switch for admitted-but-not-executed calls;
4. preserve confirmed effects, repair durable facts and use authorized/idempotent compensation when reversible;
5. put dispatched/unknown work in `PENDING_RECONCILIATION`.

Never delete historical evidence or retry a whole batch.

## 7. Evidence

Repository evidence is limited to CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME. The Day75 suite contains 41
deterministic in-process tests; 172 cumulative tests pass with 131 Day72–Day74 prerequisite regressions
(Python 3.11.5). Those regressions are not new Day75 evidence. INTEGRATION_RUNTIME and PRODUCTION are NOT RUN.

## Related

- [Day75 lesson](../../../docs/fastapi/day75-streaming-caching-and-batching-for-llm-applications.md)
- [Day75 classroom record](day75-streaming-caching-batching-classroom-draft.md)
- [Day74 design](DAY74_OUTPUT_TOOL_CONTRACTS.md)
