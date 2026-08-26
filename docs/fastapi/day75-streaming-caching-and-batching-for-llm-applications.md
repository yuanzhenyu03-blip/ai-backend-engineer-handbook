# Day75 — Streaming, Caching and Batching for LLM Applications

## 1. Lesson Metadata

- **Phase:** 7A — LLM Application Engineering
- **Prerequisites:** Day73 input binding; Day74 output/tool boundary; Day54 independent connection, Provider
  request and Durable Job lifecycles
- **Artifact:** [`projects/ai-agent/`](../../projects/ai-agent/README.md)
- **Evidence:** CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME; INTEGRATION_RUNTIME/PRODUCTION NOT RUN
- **Next:** Day76 — Model Routing, Fallback, Latency and Cost Engineering

Day75 optimizes delivery, reuse and throughput. It does not relax correctness or authority.

## 2. Learning Objectives

By the end, you can:

1. distinguish token, stream chunk, transport event, application progress event, complete candidate and durable result;
2. assemble streams with exact identity, framing, order, limits and completion;
3. design a tenant-safe, versioned cache key and explain why TTL is not truth;
4. treat cache hits as candidates that require current checks and Day74 re-admission;
5. batch compatible requests without sharing identity, authorization or outcomes;
6. map per-item failures to retry, reject or reconciliation;
7. design bounded queues with wait limits, deadlines, fairness and backpressure;
8. contain a poisoned cache without deleting evidence or bulk retrying work.

## 3. Why This Matters

LLM latency invites early display, repeated prompts invite caching, and Provider APIs invite batching. Each
optimization can amplify a correctness bug:

- a partial JSON fragment can look executable;
- a prompt-only cache key can leak a tenant's result to another tenant;
- an unexpired entry can be stale or unauthorized;
- a whole-batch retry can repeat already executed side effects;
- a browser disconnect can be mistaken for cancellation or business failure.

The safe design keeps optimization surfaces outside the durable authority boundary.

## 4. Roadmap Position

```text
Day73 versioned/bound input
  -> Day74 validated output and permissioned tool execution
  -> Day75 optimizes streaming/reuse/throughput while preserving those contracts
  -> Day76 uses latency/cost facts for routing and fallback
  -> Day77 pins behavior with Fake Provider and regression tests
```

Day75 deliberately does not implement Day76 routing or Day77's full Fake Provider suite.

## 5. Lesson Map

| Part | Production question | Boundary produced |
|---|---|---|
| Streaming | When does partial transport become a candidate? | Identity-bound `StreamAssembler` |
| Caching | What may two requests safely share? | Exact versioned `CacheKey` + current checks |
| Batching | What may travel together without becoming one operation? | Compatible, bounded, fair planner |
| Recovery | What happens after partial/unknown outcomes? | Per-item retry/reject/reconcile |
| Incident | How is a poisoned cache release contained? | Disable, bypass, invalidate, classify, preserve |

The scenario is a multi-tenant research platform whose LLM may propose `publish_report`, a real side effect.

## 6. Core Mental Model

```text
framed stream events
  -> exact identity/order/buffer/completion
  -> CompleteCandidate
  -> Day74 Parse -> Schema -> Registry -> trusted Auth -> Semantics -> Admission
  -> idempotent Tool Execution -> Outcome Verification
  -> Durable Store guarded completion OR reconciliation
```

The same downstream chain applies to a cached candidate and every batch item.

Three lifecycles remain independent:

```text
HTTP client connection = a transient subscription
Provider request       = a transient external execution/stream
Durable Job            = persisted business truth
```

Therefore UI output is not completion, a cache hit is not authorization, and a batch summary is not per-item
truth. Only current persisted facts and exact identity may authorize guarded completion.

## 7. Main Concepts

### Concept 1: Framed streaming assembly

Provider fragments such as these are not JSON objects or tool calls:

```text
chunk 1: {"kind":"tool_
chunk 2: call","tool_name":"publish_report",
chunk 3: "arguments":{"tenant_id":"tenant-a"
```

A robust assembler binds trusted tenant/Job/Attempt/stream identity, validates event type and an exact
monotonic sequence, bounds UTF-8 bytes, and requires an explicit completion marker. `PROGRESS` is safe
application metadata, not candidate text. A missing sequence followed by `completed` is malformed/truncated.

Classroom check: can partial chunks enter Tool Admission?

> Student: `不能，应该全部chunk都搜集到的时候再进行组合`

Refinement: collecting all observed chunks is insufficient; framing, identity, order and completion must also
be proven. Even then, assembly emits only `CompleteCandidate`, not an admitted call.

Client reconnect reads persisted Job state plus safe progress/application events. Raw token replay is not
assumed. A protected resumable-assembly store is separate from the successful response cache and must bind
tenant + Job + Attempt + stream + sequence.

### Concept 2: Cache identity, freshness and authority

A cache is a temporary, discardable, rebuildable copy. A key must include every material sharing dimension:

```text
trusted tenant + auth scope/policy
+ canonical business-input fingerprint
+ Prompt revision + Output/Tool versions
+ Provider/model/Capability Profile revision
+ cache-policy version
```

Model-provided tenant values are never authority. A v1 output cannot be silently interpreted under v2.

TTL sets a maximum age, not a truth lease:

```text
12:00 cached report-7 v7 = draft, TTL 10m
12:02 durable report-7 v8 = published
12:03 entry is unexpired but stale
```

A hit still checks current authorization, Registry lifecycle, resource version and durable state. Invalidation
makes entries unusable for future reads; bypass skips cache for one request; TTL bounds time. None replaces the
others, and a final atomic guard handles invalidation races.

Classroom misconception: A2 could reuse A1's deterministic `AdmittedToolCall`. Correction: Admission is
current permission for one candidate/Attempt/tool-call. A2 reruns Registry/Auth/Semantics/Admission. A logical
idempotency key may remain stable for the same business operation, but Attempt/tool-call identity is new.

Secrets, authorization decisions, one-time capabilities, partial buffers and unbounded sensitive material do
not belong in an ordinary shared response cache.

### Concept 3: Per-item batching

A batch envelope is a transport/scheduling container, not a business aggregate. Every item keeps tenant, Job,
Attempt, Prompt/Output/Tool contracts, Provider Profile, tool-call and idempotency identity. Authorization and
validation are per item.

```text
item-1 -> complete/validated -> guarded SUCCEEDED
item-2 -> OUTPUT_SCHEMA_INVALID or UNAUTHORIZED -> reject; no tool execution
item-3 -> TIMEOUT_UNKNOWN -> PENDING_RECONCILIATION; no blind retry
```

`PARTIAL_SUCCESS` may summarize the envelope but never replaces actual per-item facts. Results require exact
correlation identity. Missing/duplicate/mismatched correlation is an envelope failure; do not guess by array
position unless a validated Provider contract guarantees order, count and identity.

Recovery classification:

- definitely not accepted, and policy/deadline/budget allow -> retry only that item as a new Attempt;
- unauthorized, invalid or incompatible -> reject;
- dispatched with unknown outcome -> reconcile.

The student's concise classification was `retry，reject，reconcile`.

### Concept 4: Latency, fairness and backpressure

Larger batches can raise throughput but add queueing latency. A production planner needs compatible
partitions, maximum batch size, maximum wait/flush time, per-item deadlines, bounded queues, per-tenant quotas,
fair scheduling and explicit backpressure.

A tenant-a flood can otherwise starve low-volume tenant-b forever. The student's diagnosis was
`低流量tenant长期处于等待，加入a`; the required correction is a fairness mechanism such as round-robin plus
quota, not merely a larger global queue.

Immediately before dispatch, each item uses current persisted facts. Pre-dispatch cancellation yields zero
Provider calls for that item while others may proceed. Post-dispatch cancellation is best effort; if
non-execution cannot be proved, retain cost/idempotency evidence and reconcile.

### Concept 5: Incident containment

A bad cache policy omitted tenant identity, promoted partial streams to successful entries and fed batch
items. The student correctly chose `立即停止新的错误 cache hit` rather than waiting for TTL.

```text
contain -> disable/rollback policy; force bypass; invalidate/quarantine namespace
A1 partial/not admitted -> reject + invalidate; optional NEW authorized Attempt
A2 admitted/not executed -> final Registry kill switch; reject; zero effect
A3 confirmed wrong effect -> preserve evidence; repair facts; compensate if reversible; verify
A4 dispatched/unknown -> PENDING_RECONCILIATION; no blind retry
```

The original `A1应该修复后retry A2kill switch A3repaire A4recociliation` captured containment categories but
needed two refinements: A1's poisoned candidate is rejected rather than rewritten, and A3 may require an
authorized/idempotent compensation beyond internal repair.

## 8. Common Misconceptions

| Misconception | Why it fails | Correct rule |
|---|---|---|
| Completion event means business success | It proves only transport completion | Emit candidate, then run Day74 and guarded completion |
| Client disconnected, so work stopped | Lifecycles are independent | End subscription; inspect durable facts |
| Unexpired means current | Durable facts may change before TTL | Verify auth/lifecycle/resource version/current state |
| Temperature zero means cacheable | Determinism is neither permission nor safe identity | Apply explicit cacheability policy |
| Reuse `AdmittedToolCall` across Attempts | Authority and identity can change | Rerun Admission for the new Attempt |
| Retry an unauthorized item after “fixing” output | Output cannot grant permission | Reject; only a separately authorized new request may proceed |
| Retry the whole failed batch | Successful/unknown work may duplicate | Recover per item |
| Repair is enough after external harm | Internal truth and external effect differ | Preserve, repair, compensate when authorized, verify |

## 9. Engineering Trade-offs

| Choice | Benefit | Cost/risk | Boundary |
|---|---|---|---|
| Early token display | Better perceived latency | Partial/misleading UI | Label provisional; no business completion |
| Resume buffer | Faster reconnect | Sensitive partial retention | Protected, identity-bound, finite retention |
| Longer TTL | More hits/lower cost | Larger stale window | Current checks + invalidation + final guard |
| Broader cache sharing | Higher reuse | Cross-tenant/auth/version risk | Exact trusted key; fail closed |
| Larger batch | Throughput | Queue latency/deadline misses | max size + max wait + deadline |
| Per-tenant quota | Isolation/fairness | Possible unused capacity | Tune with metrics, preserve boundedness |
| Post-dispatch cancellation | May reduce work | Outcome may remain unknown | Best effort + reconciliation |

## 10. Hands-on Exercises

1. Feed deltas with sequence `0, 2, completed=3`. Expect malformed/truncated, no candidate.
2. Disconnect a subscriber mid-stream. Confirm the Job is unchanged and reconnect uses durable state/events.
3. Compare cache keys across tenant, Prompt revision and Output version. Every mismatch is a miss/bypass.
4. Keep TTL valid but advance `resource_version`. Expect stale, not hit.
5. Look up a valid cached tool candidate after Registry disable. Expect current Admission rejection.
6. Enqueue compatible items from a flooding tenant and a low-volume tenant. Verify bounded round-robin selection.
7. Map success, unauthorized and timeout-unknown in one envelope. Persist three separate outcomes.
8. Remove a correlation id. Mark the envelope unreliable; do not guess position.
9. Cancel one item before dispatch and one after dispatch. Expect zero call vs reconciliation.
10. Run the repository suite:

```bash
cd projects/ai-agent
python3 -m unittest discover -s tests -v
```

## 11. Relevant Framework Connections

- **FastAPI/Starlette streaming:** `StreamingResponse` transports bytes; it does not create durable success.
- **SSE/WebSocket:** event ids, framing, reconnect and safe progress need application contracts.
- **Pydantic/JSON Schema:** validate only after the complete candidate boundary; partial fragments are not models.
- **Redis-style caches:** TTL, deletion and namespaces are availability mechanisms, not database authority.
- **Queues/workers:** batch wait, deadlines, quotas and backpressure belong to explicit scheduling policy.
- **Database transactions:** current identity/state and atomic guarded completion remain the source of truth.

These are conceptual connections. The Day75 artifact uses none of those real integrations.

## 12. AI Backend Connections

- Provider adapters translate provider-specific stream/batch envelopes but do not authorize or complete Jobs.
- Prompt/output/tool/profile revisions become cache and compatibility dimensions.
- Streaming telemetry should distinguish provider start, output assembly and durable completion.
- Cached structured output remains an untrusted candidate under current policy.
- Tool side effects require stable logical idempotency and fresh per-Attempt Admission.
- Timeout unknown preserves Attempt, dispatch and cost evidence for reconciliation.
- Day76 can consume measured queue/cache/latency facts, but routing is not implemented here.

## 13. English Interview

### Beginner Question

What is the difference between a streaming chunk and a complete business result?

Actual answer:

> Streaming processing blocks can form a complete result, but auditing is still required.

Assessment: passed with refinement. Use `streaming chunks`; ordered assembly plus completion forms a complete
candidate, and validation/guarded completion—not “auditing” alone—makes a durable result.

Strong answer:

> A streaming chunk is only a transport fragment. The application must assemble all ordered chunks and receive
> a valid completion marker before it has a complete candidate. That candidate still needs schema, semantic,
> authorization and guarded-completion checks before it becomes a durable business result.

### Intermediate Question

Why does a cache hit not prove that the result is currently authorized and correct?

Actual answer:

> Authorization decisions must be based on database facts, as a mere server hit could—across gateways—result
> in accessing a server belonging to a different provider.

Assessment: passed after replacing `server hit` with `cache hit`. Cross-tenant reuse, revoked permission,
stale state and incompatible versions are the central risks—not which Provider server answered.

Strong answer:

> A cache hit only proves that an entry exists for a key. It does not prove current authorization or current
> business truth. I recheck trusted tenant and authorization context, contract versions, resource version,
> lifecycle and durable state before using the candidate.

### Senior Question

A batch contains one successful item, one unauthorized item and one item that timed out after dispatch. How do
you recover without duplicating effects?

Actual answer:

> Each specific result of the batch should be handled separately. The first item completes the guard check;
> the second encounters an authorization rejection but undergoes a fix, followed by a retry; the third enters
> a `pending_reconciliation` state, where a decision is made based on persisted database facts and external
> call records rather than proceeding directly to a retry.

Assessment: passed after correcting the unauthorized item: reject it without retry. The successful item may
pass guarded completion if identity/current state match. The unknown item retains original Attempt,
idempotency and cost evidence for reconciliation. Never replay the whole batch.

## 14. Mental Model Summary

> Attribution: the following Chinese synthesis was supplied by the teaching assistant at the student's
> explicit request (`你帮我总结吧`), not independently authored by the student.

Streaming 只优化渐进传输。chunk、token 和 event 都不是完整业务对象；只有 identity、framing、sequence 与
completion 完整时才生成 `CompleteCandidate`。断线只结束订阅，Durable Job 仍由持久化事实决定。

Caching 只优化安全复用。key 覆盖可信 tenant/auth、业务输入及 Prompt/Output/Tool/Profile/Provider/model/
cache-policy 版本。TTL 不等于真相；命中后仍查当前授权、生命周期、资源版本与 Durable Store。Admission 不跨
Attempt 复用，partial/secret/sensitive 数据不能无边界进入普通缓存。

Batching 只优化吞吐。每个 item 保留自身 tenant、Job、Attempt、Contract、tool-call、idempotency、结果和恢复。
Partial success 分项记录；retryable、rejected 与 unknown 分别 retry、reject、reconcile。

三者都必须保留 Day74 的完整验证、当前 Admission、幂等执行、Outcome Verification 与 guarded completion。

## 15. Today's Takeaway

```text
Streaming optimizes delivery; it does not prove completeness, authorization or durable success.
Caching optimizes reuse; it does not prove current truth, permission or execution authority.
Batching optimizes throughput; it does not merge identity, authorization, outcomes or recovery.
```

When execution may already have crossed an external boundary, preserve evidence and reconcile—never let a
cache or batch convenience turn uncertainty into a blind retry.

## 16. Before Next Lesson Checklist

- [ ] I can explain why a completion marker emits only a candidate.
- [ ] I keep connection, Provider-request and Durable-Job lifecycles separate.
- [ ] My cache key contains trusted tenant/auth, input and all material versions/policies.
- [ ] I know TTL can be unexpired while data is stale.
- [ ] I rerun current Admission for cached candidates/new Attempts.
- [ ] I preserve per-item batch identity, result and recovery.
- [ ] I use max size, max wait, deadlines, fairness, quotas and backpressure.
- [ ] I distinguish retry, reject and `PENDING_RECONCILIATION`.
- [ ] I never guess missing batch correlation or replay a whole partial-success batch.
- [ ] I understand Day75 evidence is in-process only; real integration/production remains unproven.

Next: Day76 will use these latency, throughput, cache-identity and failure facts for routing, fallback and cost
engineering without changing the durable correctness boundary.

