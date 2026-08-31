# Day79 Classroom Record — Framework-agnostic Agent Loop and Control Flow

This record preserves the real classroom answers, objections, mistakes and corrections. It is not a polished
replacement for the released lesson.

## Terminology and authority

The student chose the authority for the next Step:

> 应用拥有的 Agent Controller

The first response to `PENDING_RECONCILIATION` was:

> 选择runtime的控制结果

Correction: Day78 reports the execution fact; the Controller interprets it and returns `RECONCILE`.

The assistant used Agent terminology too early. The student correctly stopped the class:

> 不能，我还有个问题按照开课时候的提示词应该会解释一些第一次出现的名词，为什么这节课没有解释agent等一些名词

The repaired definitions were Agent = Goal + Controller + trusted state + controlled actions + verified
observations; Agent Loop = trusted-state control cycle; Job = one Goal execution; Step = one control advance;
Attempt = one concrete Runtime execution; action = proposal; observation = verified result. The student then
correctly answered that the LLM, Runtime and Controller individually:

> 都不能称为完整AI agent

## Trusted input and termination

Student selection:

> job_id / current_step_id
> 用户目标
> 当前 Job 是否终止
> 已验证的 observations
> 当前 RuntimeResult
> 等待 reconciliation 的 identity

The class added tenant and Attempt binding, with `model_proposal` marked untrusted. Asked what must be checked
before model `CONTINUE`, the answer was:

> 不知道

Correction: determine whether verified observations already satisfy the Goal. Runtime completion is not Job
completion.

When the third action had not executed, the student initially called it:

> external_outcome_unknown

Correction: that is known non-execution. With an incomplete Goal, return `CONTINUE`. When a dispatched third
call timed out with unknown outcome, the answer was correctly:

> RECONCILE

## Framework boundary

The assistant introduced LangGraph `Command` without first defining it. The student objected:

> 不是，我还有个问题你是否先解释一下什么是LangGraph 的 `Command` 对象？

The correction explained that `Command` can combine graph-state update, dynamic goto, parent graph routing
and interrupt resume. It belongs behind a future replaceable adapter. If its route contradicts application
`COMPLETE`, fail closed. The student chose the correct authority:

> 应该相信 Controller 的业务决策

## Identity, state and zero effects

For `CONTINUE`, the student required:

> 创建一个具有新 `step_id` 的下一步并通过 Day78 Runtime 边界处理

For duplicate delivery:

> 两次都解析到同一个 `S2`

For explicit refusal after recovery:

> `FAIL`

The student twice answered `不能` when asked whether old control history should be rewritten or an old Worker
could advance a newer/terminal Job. The terminal behavior was:

> 还是返回 `NOOP_TERMINAL` 并保持 Job 为 `COMPLETE`

Zero-new-Runtime-call cases selected by the student were:

> `NOOP_TERMINAL`、`NOOP_STALE`、`DUPLICATE_REPLAY`、`RECONCILE`、`COMPLETE`、`FAIL`

The class added `WAIT`. The student rejected allowing the pure decision function to call Day78 and rejected
an all-Fake suite as complete evidence:

> 不能

The in-process real Day78 composition evidence was correctly classified:

> `EXECUTED_LOCAL_RUNTIME`

## Failure exercise

Fault: agent-loop-v1 maps pending reconciliation to continue, so S4/A4 is unknown and accidental S5/A5 is
dispatched.

Containment:

> 先阻止事故继续扩大，阻止错误版本发送新的业务请求

Affected-scope starting fields:

> job_id step_id attempt_id dispatch mark provider_request_id

The class added tenant, controller version, decision identity/reason, input Runtime status, causality,
correlation, reservation/cost identity and time window.

For late A4:

> 继续视为待验证的 late candidate

For unknown A5:

> 还是保留 A5 identity 和 reservation 进入 reconciliation

For recovery:

> 数据库事实可以repair，外部副作用compensation

Correction: compensate only a confirmed unwanted effect using a separate authorized identity. A4 and A5
reconcile independently.

Initial closure evidence was incomplete:

> 绿色单元测试、代码 rollback 或“没有新告警”

The class added complete affected inventory, per-Attempt reconciliation, late/stale zero-effect proof,
repair/compensation verification, cost settlement, regression, bounded canary, audit correlation and explicit
limits. With C5 still pending, the student correctly said incident closure was:

> 不可以

## English interview

Beginner:

> It is a workflow control mechanism that guides the next steps of the work.

Intermediate:

> The model can only offer suggestions; the controller makes the final decision on the next step based on
> verified observations derived from certified runtime results.

Senior:

> Immediately terminate agent-loop-v1 while preserving all remaining Job/step/Attempt records; establish a
> bounded set of affected items and then classify them; reconciliation must be performed separately; handle
> internal remediation, while external components require independent compensation.

The corrections were to name application ownership and closed outcomes; use “structured Runtime result”
rather than “certified”; disable new v1 decisions without ambiguously terminating in-flight work; and require
per-identity effect/cost closure.

## Final student synthesis

> agent loop是一个控制智能体进行下一步工作。Controller是agent工作的控制器 模型给出下一步建议 Day78 Runtime是一次具体执行 一次 step 要先进过验证最终Controller决定下一步如何执行 unknown进入pending_reconciliation late只要在有效期内还是可以继续使用 stale则需要保存审计历史不修改现在的状态 terminal则不进行下一步操作 framework只是一个框架，无法替代实际业务工作流

Final correction: late-result authority is not decided by a validity period. It requires original identity,
binding validation and current control authority. Superseded or terminal results have zero current control
effect.

## Classroom validation record

Python 3.11.5 compiled the source/tests. The first command,
`python3.11 -m unittest -v tests.test_day79_agent_loop`, failed with `ModuleNotFoundError` because `tests/` is
not a Python package. The corrected discovery command ran 8 Day79 tests successfully. The classroom temporary
copy then ran 251 cumulative tests. Repository reconstruction must re-run these checks against its own bytes.

No real Provider, database, queue/Worker, framework, external Tool or production system ran.
