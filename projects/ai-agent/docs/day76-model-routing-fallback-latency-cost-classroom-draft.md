# Day76 Classroom Record — Model Routing, Fallback, Latency and Cost Engineering

## Production scenario

A multi-tenant travel application has several versioned Provider/model Capability Profiles. One Job carries a
Prompt Contract, structured Output Contract, permitted Tool Contract, deadline, tenant policy and budget. The
runtime must choose an eligible execution path, preserve every Attempt, recover without duplicating unknown
side effects, and account for latency and cost without inventing facts.

## Decisions reached

- Eligibility and compatibility run before price/latency preference.
- A client model/provider value is only a server-constrained selector.
- Routing policy is server-owned and versioned; actual selection is immutable per Attempt.
- Retry uses the same execution path; fallback uses a different compatible path; both normally create a new
  Attempt and preserve the source Attempt.
- `TIMEOUT_UNKNOWN` is reconciled rather than blindly retried or rerouted.
- Latency requires an object, stage, boundary and identity; p95 is not a single-request guarantee.
- Batching improves throughput only when a real batch boundary shares measured work; item identity stays
  separate.
- Estimate, reservation, reported usage, actual settlement and unknown cost are different facts.
- Rollback stops new harm but does not close an incident or rewrite history.

## Student's actual answers

1. `满足本次 Prompt、Output、Tool 和 Provider Capability Contract`
2. `只能作为受服务器 Routing Policy 约束的 selector`
3. `不能`
4. `fallback，继续使用A1`
5. `不能`
6. `不能`
7. `应该选择Profile C，使用Durable completion latency`
8. `Profile C，因为A的P95是11s`
9. `不对，剩余的百分之五要超过7s所以不能判断是否满足`
10. `一个就是这个latency是干什么的在工程中，第二个问题就是batch怎么就提高了吞吐，里面的item都是各自执行的为什么会提高吞吐`
11. `不能，现在的问题是在课程主线上吗`
12. `3单位成本，多预留的部分应该回到总预算中`
13. `7单位`
14. `不能`
15. `Provider latency p95 为 10 秒超过了8s`
16. `不能，`
17. `不知道`
18. `不能`
19. `不可以`
20. `不能`
21. `依赖 Durable Store 中 A1 已持久化的 RoutingDecision/Attempt binding`
22. `Profile C`
23. `不能`
24. `回滚到稳定的\`Routing Policy\` version，并停止错误版本接受新的attempt`
25. `pending_reconciliation,保留reservation不释放，actual usage = UNKNOWN`
26. `记录reject，可以释放。不能需要绑定新的attempt`
27. `不能，不应该让A1进行覆盖。而是单独的保留记录并将状态保留为late_result`
28. `还应该做compensation`
29. `不对，TIMEOUT_UNKNOWN不知道是否已经产生了调用。应该是进入pending_reconciliation，并根据审计记录以及外部调用记录进行判断`
30. `不能`
31. `不正确，A1的成本事实应该是pending_reconciliation`
32. Final synthesis request: `你帮我总结吧`

## Authentic misconceptions and corrections

1. **Fallback reused A1.** The answer `fallback，继续使用A1` identified the recovery family but missed
   Attempt identity. A different Provider/model/Profile normally requires A2; A1 remains immutable.
2. **p95 treated as a guarantee.** The student self-corrected: the remaining 5% is unknown. A percentile is
   distribution evidence, and the decision also needs an exact boundary and already-consumed deadline.
3. **Rate-limit recovery was unknown.** If A1 is proved `DEFINITELY_NOT_ACCEPTED`, a current, compatible,
   budget/deadline-eligible path may create A2. If execution is unknown, reconciliation replaces fallback.
4. **Rollback/tests considered for closure.** The student correctly rejected that shortcut. Unknown outcomes,
   effects and costs still require durable classification and reconciliation.
5. **A later cache hit/success could erase unknown cost.** The student corrected this: A1 stays
   `PENDING_RECONCILIATION`; another result cannot turn an already-dispatched unknown Attempt into zero cost.

## Latency and batching clarification requested by the student

Latency engineering makes user experience, deadlines, routing, timeout policy and bottleneck diagnosis
measurable. It is not one generic Provider number: Job, Attempt, batch item and pipeline stage differ.

Independent items can still share envelope creation, network round trips, protocol overhead or accelerator
work if a real Provider supports true batching. That may improve items/time while adding queue wait. Merely
putting requests in a Python list proves neither batching nor throughput improvement.

## Artifact evolution

The repository artifact continues Day72–Day75 rather than copying their responsibilities:

- `routing_policy.py` consumes Day72 Capability Profiles and emits a Day72 Attempt execution binding plus a
  versioned RoutingDecision after eligibility gates.
- `recovery_cost.py` classifies recovery before a new binding and retains estimate/reservation/actual/unknown
  cost facts.
- `test_day76_routing_recovery.py` provides deterministic local boundary evidence without implementing the
  Day77 Fake Provider suite.

## Production failure / rollback exercise

Bad policy v5 admitted incompatible Profile B, read stale latency/health/pricing, amplified fallback calls,
left one original call `TIMEOUT_UNKNOWN`, allowed some effects, and had incomplete tenant cost evidence.

```text
Containment -> v4 for new planning; stop v5; pause auto-fallback; quarantine B; fail closed
J201/A1    -> TIMEOUT_UNKNOWN; hold reservation; actual UNKNOWN; reconcile; no blind A2
J202/B     -> incompatible and proved pre-dispatch; reject; release reservation; new work needs A2
J203/A1    -> late after A2 terminal; preserve/settle A1; no overwrite or tool execution
J204       -> confirmed duplicate effect; repair durable facts + authorized compensation + verification
J205 batch -> preserve total; per-item UNKNOWN; reconcile; never equal-split or write zero as actual
```

Rollback does not rewrite v5 bindings. Closure requires affected-scope proof, Attempt classification,
unknown-resolution paths, verified repair/compensation, cost settlement or retained unknown reservations,
late-result fences, controlled rollout/regression evidence and cross-system verification.

## English interview results

### Beginner — actual answer

> Model routing is a dynamic allocation mechanism that first identifies and excludes models based on
> criteria such as insufficient context, lack of required functionality, non-compliance, or inadequate
> capability levels.

Passed with refinement: `policy-controlled selection process` is more precise because routing may be static
or dynamic; `contract incompatibility` is more precise than `non-compliance`. Eligibility precedes preference.

### Intermediate — actual answer

> A retry involves making a new attempt using the same configuration, whereas a fallback involves making a
> new attempt using a different configuration; the system should enter the `pending_reconciliation` state.

Passed with refinement: reconciliation applies when the original outcome is unknown, not to every retry or
fallback. Both actions preserve the source Attempt.

### Senior — actual answer

> 1. v5 no longer generates new RoutingDecisions or fallbacks.
> 2. Incompatibilities with Profile B have been isolated.
> 3. Travel Jobs/Attempts are fully identified by clicking on the policy version and time window.
> 4. Each attempt is categorized: Success / Rejected / Absolutely Not Accepted / Timeout-Unknown / Stale /
> Terminal.
> 5. TIMEOUT_UNKNOWN issues are resolved or have a clear, persistent reconciliation path.
> 6. Remediation for confirmed consequences is complete, and necessary compensation has been verified.
> 7. All costs are settled, or items remain marked as "unknown" with the booking retained.
> 8. Late, stale, or superseded results cannot overwrite the current Durable State.
> 9. No new routing errors occurred following the controlled rollout/canary deployment.
> 10. Logs, metrics, the Durable Store, and external facts have been cross-verified.

Passed. Language refinements: `affected Jobs and Attempts`, `scoped by`, `DEFINITELY_NOT_ACCEPTED`, and
`reservation retained`. Engineering refinement: repair durable facts and compensate external effects are
separate verified operations.

## Final Chinese mental model

> Attribution: supplied by the teaching assistant at the student's explicit request (`你帮我总结吧`), not
> independently authored by the student.

Model routing 先按当前且带版本的 Prompt、Output、Tool、Capability、授权、deadline 和 budget 事实排除不合格
候选，再由服务器 Routing Policy 在合格候选中选择。客户端只能提供受约束 selector。每个实际选择固化到新的
Attempt；政策变化不改写历史。

Retry 在相同路径创建新 Attempt；fallback 在不同兼容路径创建新 Attempt。`TIMEOUT_UNKNOWN` 不能盲目 retry
或 fallback，必须保留身份、reservation 与未知成本并 reconciliation。未授权、不兼容和业务拒绝不能通过
fallback 绕过。

Latency 必须绑定 Job/Attempt/item、具体阶段和 measurement boundary。p95 不是单次保证，streaming 只改善感知
延迟，真实 batching 才可能通过共享工作提高吞吐并同时增加排队。Cost 必须区分 estimate、reservation、reported、
actual 和 unknown；多个 Attempts 会放大 Job 成本，未知不能记零。

路由、恢复、延迟和成本控制都不能绕过 Day72–Day75 的 Prompt/Output/Tool/Capability Contract、当前 Admission、
幂等执行、Outcome Verification、guarded completion、Durable Store 与 reconciliation。

## Validation status

Repository validation records its own exact commands and counts. Classroom evidence was 18 Day76 + 172
Day72–Day75 deterministic in-process tests on Python 3.11.5. No real Provider, HTTP/SSE, database, queue,
Worker, external tool, production pricing/latency, credentials, customer data or traffic was used.
