# Day75 Classroom Record — Streaming, Caching and Batching

## Production scenario

A multi-tenant AI Research Platform streams an LLM-produced `publish_report` candidate, may reuse a cached
response, and may group independent Jobs into one Provider batch. Publishing is a side effect. Day74's exact
Registry, trusted authorization, per-candidate Admission, idempotency, outcome verification and guarded
completion remain authoritative.

## Decisions reached

- Partial chunks are transport fragments. Ordered, identity-bound assembly plus a legal completion marker
  produces only a `CompleteCandidate`.
- HTTP disconnect ends one subscription, not necessarily the Provider request or durable Job. Reconnect reads
  persisted Job state and safe progress/application events.
- Cache entries are disposable copies. Exact versioned identity, current authorization, resource state and a
  final guard are required even before TTL expiry.
- An `AdmittedToolCall` is per candidate/Attempt and is never ordinary cache material.
- A batch preserves every item's identity, authorization, outcome and recovery. Whole-batch retry is unsafe.
- Retry, reject and reconcile are distinct. Unknown post-dispatch outcomes enter `PENDING_RECONCILIATION`.

## Student's actual answers

1. `不能，应该全部chunk都搜集到的时候再进行组合`
2. `判定为异常流`
3. `不能`
4. `读取持久化 Job 状态和安全的 progress/application events`
5. `后台 Durable Store 的 guarded completion 决定`
6. `不安全，这里发生了跨租户调用`
7. `不能`
8. `是的`
9. `在真实工具执行前拒绝该发布操作`
10. `可以`
11. `是先通过当前 Registry 检查并拒绝`
12. `不能`
13. `不能`
14. `应该分别记录实际结果`
15. `不能`
16. `retry，reject，reconcile`
17. `低流量tenant长期处于等待，加入a`
18. `不应该，应该在数据库持久化事实中检查`
19. `不能，应该是pending_reconciliation`
20. `立即停止新的错误 cache hit`
21. `A1应该修复后retry A2kill switch A3repaire A4recociliation`
22. `是创建一个新的 Attempt 并保留原失败记录`
23. Beginner: `Streaming processing blocks can form a complete result, but auditing is still required.`
24. Intermediate: `Authorization decisions must be based on database facts, as a mere server hit could—across gateways—result in accessing a server belonging to a different provider.`
25. Senior: `Each specific result of the batch should be handled separately.The first item completes the guard check; the second encounters an authorization rejection but undergoes a fix, followed by a retry; the third enters a pending_reconciliation state, where a decision is made based on persisted database facts and external call records rather than proceeding directly to a retry.`
26. Final synthesis request: `你帮我总结吧`

## Authentic misconceptions and corrections

1. **TTL mistaken for truth.** An unexpired entry can already be stale. TTL only bounds age; current durable
   state, authorization, lifecycle, resource version and final atomic guards still apply.
2. **Admission treated as cacheable.** Determinism does not make A1's `AdmittedToolCall` reusable by A2. A2 is
   a new Attempt and reruns current Registry/Auth/Semantics/Admission; only a deliberate logical idempotency
   identity may remain stable.
3. **Poisoned partial candidate described as repair-and-retry.** Reject and invalidate/quarantine it. A still
   authorized request may create a new cache-bypassing Attempt; never overwrite the failure.
4. **Repair treated as sufficient after confirmed harm.** Repair fixes internal facts; a reversible external
   effect may also require a newly authorized/idempotent compensation and verification.
5. **Unauthorized item described as fix-and-retry.** Reject without retry. Only a separately established
   permission/policy change could authorize a new request.

English refinements: `processing blocks` -> `streaming chunks`; `auditing` -> assembly plus validation;
`server hit` -> `cache hit`; `completes the guard check` -> `passes guarded completion`; `external call
records` -> `authoritative external execution evidence`.

## Artifact evolution

The classroom used a temporary 12-test model under `/tmp`. The repository artifact was independently evolved
to `src/streaming_cache_batching.py` and `tests/test_streaming_cache_batching.py`, reusing Day74 rather than
copying the temporary model. It covers framed stream assembly, exact cache identity/freshness/current auth,
new-Attempt re-admission, bounded/fair compatible batching, pre-dispatch fences and per-item recovery.

## Production failure / rollback exercise

A bad cache-policy release omitted tenant identity, marked partial streams complete and served them to batch
items. The immediate response was disable/rollback, cache bypass and invalidation/quarantine—not waiting for
TTL. Classification:

```text
A1 partial hit, not admitted -> reject + invalidate; optional NEW safe Attempt
A2 admitted, not executed   -> final kill switch; reject execution; zero effect
A3 confirmed wrong effect   -> preserve evidence; repair; compensate if reversible; verify
A4 dispatched/unknown       -> PENDING_RECONCILIATION; no blind retry
```

The affected set uses release/cache-policy version, time window, namespace and persisted tenant/Job/Attempt/
Admission/dispatch/execution evidence. History is preserved; no bulk retry.

## English interview results

### Beginner

The answer passed with terminology refinement. Strong version: a chunk is only a transport fragment. Ordered
assembly and a valid completion marker form a complete candidate, which still needs schema, semantic,
authorization and guarded-completion checks.

### Intermediate

The answer passed after replacing `server hit` with `cache hit` and centering trusted tenant/auth, contract
versions, resource version, lifecycle and durable state rather than Provider-server selection.

### Senior

The answer passed after one correction: the unauthorized item is rejected without retry. A successful item
may pass guarded completion, while the timeout-unknown item preserves identity/cost evidence and reconciles.
The whole batch is never replayed.

## Final Chinese mental model

> Attribution: supplied by the teaching assistant at the student's explicit request (`你帮我总结吧`), not
> independently authored by the student.

Streaming 只优化渐进传输：chunk/token/event 不是完整业务对象，只有身份与序列完整且收到合法 completion marker
才产生 `CompleteCandidate`，随后仍走 Day74。断开连接只结束订阅，不决定 Durable Job。

Caching 只优化复用：Cache Store 不是授权或当前真相；key 必须覆盖可信 tenant/auth、输入和所有相关 Contract/
Provider/model/policy 版本。TTL 不保证新鲜；命中后仍检查当前事实。历史 Admission、partial、secret 和无边界敏感
数据不能作为普通共享缓存。

Batching 只优化吞吐：每个 item 保留 tenant、Job、Attempt、Contract、tool-call、idempotency、结果与恢复身份。
Partial success 分项记录；可确认未接受、拒绝类和未知结果分别 retry、reject、reconcile。

三种优化都不能绕过 Day74 的完整候选验证、当前 Admission、幂等执行、Outcome Verification 和 Durable Store
guarded completion。已 dispatch 后的断线、取消或超时可能是未知结果，必须保留证据并 reconciliation。

## Validation status

The repository update reruns static and cumulative tests separately. Evidence remains deterministic and
in-process. No real Provider, SSE/HTTP, Redis, PostgreSQL, queue, Worker, external tool, sensitive prompt,
customer data or production traffic is claimed.

