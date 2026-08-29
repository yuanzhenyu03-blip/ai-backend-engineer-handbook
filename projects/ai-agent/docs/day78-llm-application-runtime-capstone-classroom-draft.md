# Day78 Classroom Record — LLM Application Runtime Capstone

Date: 2026-08-28

This record preserves the live Day78 reasoning, short answers, incomplete
answers, corrections, Artifact evolution, and interview responses. It does not
polish the student into having supplied explanations that were taught later.

## Runtime responsibility boundary

When asked whether Provider `SUCCESS` could directly complete the Job, the
student answered:

> 不能，验证shema、语义、授权、tool admission等

Confirmed: Adapter success is only a stable transport outcome. Application
validation, current authorization, Tool Admission, execution, outcome
verification, and guarded completion remain separate boundaries.

The student identified the owner of the ordering as:

> Runtime orchestration boundary 负责

The final ownership model became more precise:

> 应该由一个统一的 Runtime Attempt lifecycle/store 持有权威状态，而组件只返回验证/决策结果

Components therefore return translation, validation, or decision facts. They
do not each maintain a competing authoritative Job/Attempt state.

## Immutable planning and pre-dispatch gates

For an already-planned Attempt after defaults changed, the student answered:

> 继续使用规划时绑定的 Prompt v3 / Profile P2

For a quarantined bound revision:

> pre-dispatch gate 阻止调用，历史应该保留

The student consistently rejected reinterpretation of historical Attempts,
including late results. Current defaults govern new planning only.

The ordering decision was:

> 先解析并固定本次 Contract requirement，再做 candidate eligibility 和 route selection

This excludes incompatible candidates before price/latency preference. If all
candidates lack current capability evidence, Runtime returns a structured
no-route result; it does not lower the Contract automatically.

When asked how an atomic dispatch claim should be modeled, the student said:

> 应该使用update set returning

The classroom Artifact models that conditional database transition with one
in-process `RLock`; no real database was run.

## Provider request and execution envelope

The class found a real integration seam: Day73 produces ordered structured
messages, while the Day72 `ApplicationRequest` currently accepts a string.
The student required:

> 建立一个应用拥有、确定性且可验证的 message-to-provider-request bridge，并保证发送 payload 与 A1 的 Prompt binding 一致

The Artifact serializes ordered role/content pairs canonically and recomputes
the Day73 rendered hash before dispatch.

The student then required a stable application envelope:

> 定义稳定的应用层 Provider execution envelope，把 ProviderOutcome 与绑定 Job/Attempt identity 的 candidate（或受保护 candidate reference）一起返回

A protected reference remains only integrity/location evidence. The student
correctly added:

> 还需要验证授权

The temporary implementation deliberately fails closed because a real
authorized protected-artifact loader was not integrated.

## Streaming, cache, and batch boundaries

The student rejected partial streaming JSON as a complete candidate, rejected
cache reuse after authorization revocation, and rejected a batch envelope with
missing per-item identity. The integrated rule remained:

```text
first token != complete candidate
cache hit != current authorization
batch summary != per-item truth
```

These were exercised through the existing Day75/Day77 regressions rather than
reimplemented in the Day78 Runtime module.

## Tool Admission, execution, and outcome

For a cache or protected candidate, the student required a complete current
Admission rather than reusing old authority:

> 不能，还需要经过完整tool admission，还有授权不一致

Immediately before execution:

> 必须在 Tool Execution 前再次检查当前 lifecycle

After Tool Execution, the student rejected direct completion:

> 不能，必须验证返回的结果outcome

The Artifact therefore calls the existing Day74 executor and
`verify_publish_outcome()`. Schema/semantic failures reject; operation/report
identity mismatch enters reconciliation; only a verified current identity may
complete.

## Unknown execution and late results

For Provider dispatch uncertainty, the student answered:

> 不能，A3、job进入pending_reconciliation cost reservation 应该保留预算

For a late response whose Attempt remained current:

> 可以继续处理，因为attempt还没有被取代，应使用 绑定的Prompt v3

For a crash around A1 dispatch:

> 不能，A1应该进入pending_reconciliation

The final model is conservative: no A2, no binding rewrite, no reservation
release, and no return to `PREPARED` while execution may have occurred.

## Repair and compensation

One incomplete answer was preserved. For an outcome/version problem the
student first said:

> 不能，应该进行compensate

Correction: classify the original facts in reconciliation first. Repair may
correct internal facts without changing historical meaning. Compensation is
needed only for a confirmed external effect whose business meaning requires a
reverse action.

The student then supplied the correct historical model:

> 还是保留 A3 历史并创建独立的 compensation 操作

When cancellation raced with an already-confirmed external effect, the student
initially said:

> 保留作为审计证据

That was correct but incomplete. The cancelled Job cannot be overwritten as
successful, and a separate compensation may still be necessary.

The student rejected reusing the original operation's idempotency key and
required an unknown compensation to enter reconciliation:

> 不能应该进入pending_reconciliation

After authoritative proof that it did not execute, the student correctly
reopened the same logical compensation identity:

> 应复用原 compensation identity

If the bound compensation tool v1 was disabled after a v2 default appeared,
the student preserved the original binding:

> 原绑定版本

The old record cannot be rewritten to v2. A separately planned replacement may
supersede it only with explicit causal history and a new reservation.

## Cost and transaction boundary

The student supplied the settlement rule:

> cost reservation减去usage将剩下的释放到job的总体budget中

and for a definitely unused old reservation:

> 应该释放

The student explicitly answered `不知道` when asked how to survive a crash
between releasing the old reservation and creating a replacement compensation.
The correction was one transaction for conditional old settlement/release,
new compensation creation, and new reservation. If accounting is external,
use transactional outbox/saga plus an idempotent ledger.

The student correctly rejected external Tool I/O inside the database
transaction. After the transaction but before claim, the new operation remains
ready with its reservation held:

> 处于持有reservation状态等待worker认领，可以

For an external settlement timeout, the student identified the key mechanism:

> 幂等账本

and the recovery identity:

> 使用原 identity 重试查询/提交

Provider and Tool execution are not replayed merely to repair accounting.

## Claims, fencing, and kill switch correction

After claim near an uncertain send, the student said:

> 不能回退持久化事实

An old worker whose lease/fence is stale:

> 不能发送

For the local-check/actual-send race, the student proposed:

> 不能，还需要kill switch

Correction: a kill switch is useful but insufficient. Downstream execution
must reject old fencing tokens or enforce an equivalent conditional business
version. Strong idempotency prevents duplicate effects; it cannot decide
whether a stale first execution is still authorized.

## Structured evidence

The student defined the Runtime response as:

> 返回带有阶段、状态、Job/Attempt identity、recovery action 和 evidence 的结构化结果

The student later answered `不知道` when asked which evidence should explain a
no-route result. The class added Contract and routing-policy revisions,
candidate identity, required and observed capability, exclusion reason,
evidence level, and recovery action. Raw prompts, credentials, customer data,
Provider payloads, and raw candidates are excluded.

When asked about the executed test evidence, the student correctly classified
it as:

> EXECUTED_LOCAL_RUNTIME

The student also asked whether a database should be opened for testing. The
class did not authorize or run one; the checkpoint remained deterministic and
in-process.

## Genuine Artifact error

The first message-bridge test edit produced seven passing tests plus one error
because test code was inserted at the wrong location and referenced undefined
`claimed`. The test was corrected and rerun. This failure is preserved rather
than presenting the Artifact as first-try success.

An earlier run under system Python 3.9.6 also failed on existing `str | None`
syntax. That environment was incompatible with the project and was not
classified as a source regression. Python 3.11.5 was used for final evidence.

## English interview

Beginner answer:

> Responsible for the execution order of each component.

Review: correct direction; expanded with lifecycle gates and authoritative
state ownership.

Intermediate answer:

> Because an audit history is required for review purposes.

Review: auditability is correct; determinism, semantic stability, and payload
agreement were added.

Senior answers:

> Since it is unknown at this point whether an external invocation cost has already been incurred, this is done to avoid a redundant call.

> The results also need to be verified.

> A fence token is also required; an idempotency key only prevents duplicate calls.

The student correctly connected unknown execution to duplicate cost/effects,
Tool execution to outcome verification, and idempotency to duplicate control
rather than stale authority.

## Final synthesis attribution

The student asked:

> 你帮我总结吧

The final Chinese Mental Model was therefore supplied by the teaching assistant
at the student's explicit request. It must not be represented as an independent
student answer.

## Final validation

From `projects/ai-agent`, Python 3.11.5:

```text
PYTHONPATH=src python3.11 -m py_compile src/*.py tests/*.py
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
```

Result: 22 new Day78 tests; 243 cumulative Day72–Day78 tests; all passed.

Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`.

Not run: Python 3.12, real Provider/HTTP/SSE, PostgreSQL, Redis, queue/Worker,
durable fencing, protected-candidate storage, external Tool/compensation,
billing API, integration runtime, or production.
