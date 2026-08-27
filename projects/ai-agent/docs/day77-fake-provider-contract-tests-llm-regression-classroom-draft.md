# Day77 Classroom Record — Fake Provider, Contract Tests and LLM Regression Tests

Date: 2026-08-27

This record preserves the live answers, corrections, and incident reasoning
used to produce the released Day77 lesson. Short answers are intentionally not
polished into answers the student did not give.

## Warm-up: what proves whether a Provider call happened?

Student answer:

> provider request id

Correction: a request ID is useful evidence, but its absence is not proof that
no request crossed the Provider boundary. A timeout may occur after dispatch
and before an ID is returned. Day77 therefore uses an independent call log and
call count. Unknown dispatch remains unknown.

Student direction:

> attempt进行pending_reconciliation

Confirmed and completed: keep the original Attempt, retain the reservation,
create no replacement Attempt, and move the Job to
`pending_reconciliation`.

## Contract-Test boundary

Student answer:

> 断言 Adapter 输出的稳定 `ProviderOutcome`

Confirmed. Contract Tests assert the application-owned outcome, never SDK
types or wire syntax.

For an SDK error whose execution certainty cannot be established, the class
worked through these candidates:

> `TIMEOUT_UNKNOWN`

> TRANSPORT_ERROR

Final rule: definitely-not-sent is `TRANSPORT_ERROR`; possibly sent or unknown
is conservatively `TIMEOUT_UNKNOWN`. This protects the application guarantee
against duplicate external calls.

Student formulation:

> 保护应用依赖的语义保证

Confirmed. A regression test protects behavior the application relies on, not
the exact text of a prompt or a Provider response.

## Real validation and side effects

Student correction:

> 应该把这个候选结果送入现有的真实验证与 guarded-completion 链后，再断言最终行为

Confirmed. Returning a pre-approved final object from a Fake would skip the
boundary under test.

When asked whether final Job status was sufficient, the student answered:

> 不够，

and added:

> 工具执行次数应该是0

Confirmed. State and side effects are separate observations. An unauthorized
tool result must have tool-effect count zero.

## Determinism

Student requirements:

> 独立于 Worker 生命周期

> 使用一个由测试显式控制的响应闸门

> 入 `FakeClock` 并显式推进时间

All three are implemented. The response gate establishes exact interleavings;
`FakeClock` controls application time without behavioral sleeps; the call log
is separately injected so simulated Worker object loss does not erase the
send evidence.

Student requirement:

> 运行同一套稳定 `ProviderOutcome` Contract Tests

Confirmed for Provider A and Provider B through their real Adapters.

## Attempts, streams, cache, and batches

For an ordinary authorized fallback, the student said:

> 保留 A1 并创建 A2，

Confirmed. A new external path is a new immutable Attempt.

For timeout-unknown, the student rejected creating A2:

> 不可以，应该进入pending_reconciliation.

Confirmed. Possible prior execution forbids blind duplication.

The student repeatedly answered `不可以` when asked whether partial streams,
sequence gaps, revoked cache authorization, stale results, or missing safety
facts could be treated as success. These were converted into explicit negative
regressions.

For a malformed sequence the student classified it as:

> 判定为错误

For a normal complete compatible path, the student answered:

> 可以

One important batch misconception was preserved: when asked whether a batch
with a missing item result could accept the remaining responses, the student
answered `可以`. Correction: exact one-to-one item identity is the envelope
contract. A missing or duplicate result makes the envelope unreliable; every
affected item enters reconciliation rather than silently accepting a subset.

## Fake placement and golden expectations

Student correction:

> 放在真实 Adapter 后面的 Provider/transport 边界，从而让测试真正经过 Adapter 翻译

Confirmed. The Fake does not replace `ProviderAdapter`; it replaces the
Provider-specific transport below it.

On how the expected behavior should be stored:

> 还是作为独立、人工审查的 golden expectation 固定下来

Confirmed. Production output cannot auto-update the expected golden.

When a proposed self-generated snapshot was offered, the student answered:

> 不正确

Confirmed: that could approve the regression it was meant to catch.

A weakening of required citations was classified as:

> 语义 breaking change

Confirmed even when JSON shape remains compatible.

## Bad Adapter v6 incident

Student containment decision:

> 回滚adapter版本到稳定版本，并隔离或停止v6接受新的attempt

Student affected-scope requirement:

> 根据version、time Windows、binding、RoutingDecision、outcome持久化事实精确定位 v6 事故影响的 Job/Attempt

Student rejected treating possibly dispatched v6 errors as safe fallback:

> 不能，应该分为pending_reconciliation

Student distinguished repair from compensation:

> 内部错误事实可以repair但是要在不改变语义的情况下，已发生的外部副作用使用compensation

Confirmed. Further `不能` / `不可以` answers rejected deleting historical
Attempts, rewriting their bindings, zeroing unknown cost, or allowing late
superseded results to overwrite current state.

## English interview answers

Student answer:

> It enables `execution_local_runtime` without requiring an actual call to the provider.

This is directionally correct. The completed answer adds that deterministic
Fake Provider tests can prove local application semantics, but do not prove
real Provider, network, database, or production behavior.

Student answer:

> Pending action: review of the cost budget and provider usage data is required.

This was used to explain that unknown cost stays explicitly `UNKNOWN`, retains
its reservation, and needs owned reconciliation rather than being written as
zero.

Student answer:

> A rollback is not possible; instead, a new attempt is made using a different profile version. However, in an "unknown" state, it is unclear whether the provider has already been called. To prevent a duplicate provider call, the system should transition to a `pending_reconciliation` state.

Correction: rollback can stop v6 for future planning, but cannot undo an
already-issued call. A different profile may create a new Attempt only when
execution is known not to have happened. In an unknown state, no fallback call
is authorized; reconciliation comes first.

## Final incident-closure checklist

The student supplied this checklist:

> Containment
>
> - Stable Adapter/Profile enabled
> - v6 stopped accepting new Attempts
> - Automatic error fallback disabled
>
> Affected scope
>
> - Affected Jobs, A1/A2, and Batch items fully identified
> - Each Attempt categorized by dispatch certainty and outcome
>
> Unknowns
>
> - TIMEOUT_UNKNOWNs resolved
>   or persistent, observable reconciliation paths with assigned owners established
>
> Cost
>
> - Known costs settled
> - Unknown costs remain explicitly marked UNKNOWN with reservations retained
> - Missing data not recorded as zero
>
> Effects
>
> - Internal repairs verified
> - External compensation authorized, executed idempotently, and verified
> - Unknown outcomes of the compensation process itself handled
>
> Safety
>
> - Late, stale, or superseded results cannot overwrite current state
> - Controlled rollout generated no new errors
> - Durable Store, Fake/Provider call logs, tool facts, and cost evidence cross-verifiable

This is the release-level closure standard. Rollback and a green test run alone
do not close the incident.

## Attribution

At the end, the student asked:

> 你帮我总结吧

The final Chinese mental-model synthesis in the formal lesson was therefore
supplied by the teaching assistant at the student's explicit request. It is
not represented as a verbatim student answer.
