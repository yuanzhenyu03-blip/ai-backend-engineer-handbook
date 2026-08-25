# Day74 Output and Tool Contracts — CLASSROOM_DRAFT

> This released classroom-process record preserves the student's real short answers, authentic misconceptions,
> corrections, incident exercise, and interview progression. The final Chinese synthesis was supplied by the
> teaching assistant at the student's explicit request; it is not an independently authored student answer.

## Production scenario

One scenario evolved throughout the lesson: a multi-tenant AI Research Platform asks an LLM to propose
`publish_report`. The server context is `tenant-a`; model arguments may claim another tenant. Publishing is a
real logical side effect. The application, not the model, owns authorization, Admission, execution and durable
completion.

## Decisions reached

- A Provider response is candidate data. `SUCCESS` does not establish trusted content or business success.
- JSON parsing produces an untrusted Python value; Schema proves structure only.
- Parse, Schema, semantics, authorization, Admission, execution, verification and completion are separate.
- Strict object contracts use `additionalProperties: false`; otherwise an undeclared `force` may be accepted.
- Tool name, version and arguments are all untrusted. Unknown/incompatible/disabled versions fail closed.
- Model `tenant_id` is never authority. Authorization comes from trusted server context.
- Executor accepts only an immutable, server-normalized `AdmittedToolCall`.
- Idempotency requires an atomic claim, not a check-then-set.
- Tool success remains a candidate until Outcome Verification and guarded completion.
- `TIMEOUT_UNKNOWN` enters reconciliation; a matching valid late result may complete only a current,
  nonterminal, reconcilable job.
- Disable/rollback, repair, compensation, re-prompt/retry and reconciliation solve different problems.
- Existing Attempt/version bindings are never rewritten.

## Student's actual answers

1. `这个不知道`
2. `Semantic Validation`
3. `Schema Validation`
4. `会`
5. `schema-invalid`
6. `将其分类为 unknown tool 并拒绝`
7. `Application Authorization`
8. `不能`
9. `TIMEOUT_UNKNOWN 后进入 reconciliation`
10. `不能`
11. `违反了字符串至少包含一个字符，不能是空字符串`
12. `按照V1`
13. `仍然不可信的 Python dict`
14. `不可以`
15. `应拒绝当前候选，并且只有在策略允许时创建一次新的 re-prompt Attempt`
16. `execution rejected`
17. `不能`
18. `服务器的持久化状态`
19. `只接收 Admission Gate 创建的 AdmittedToolCall`
20. `只允许同一个逻辑发布生效一次`
21. `python版本是用的Mac上自带的进行的测试吗？还有生成的代码目录在哪里呢`
22. `需要原子的唯一占位/claim`
23. `还是必须根据持久化 operation 状态和外部证据进入 reconciliation`
24. `交给 Semantic Validation 拒绝`
25. `只返回 VERIFIED 候选，再由独立的 guarded completion 使用 Durable Store 决定是否提交`
26. `这种完全匹配的晚到结果应该被视为 valid late result 并允许 guarded completion`
27. `回滚错误版本绑定停止新的job继续使用错误版本`
28. `应阻止 A1，并在确有必要时显式创建新的安全 Attempt`
29. `根据副作用是否可逆执行受控的 repair/compensation，并保留原始执行和事故证据`
30. `不能`
31. `dispatch marker provider_request id`
32. `pending_reconciliation`
33. `Due to incomplete verification, further validation—such as checking signatures and authorizations—is required.`
34. `The tool definition encompasses details such as the tool's version, required parameters, and name, while the tool onboarding process involves a series of validation steps that ultimately authorize the tool for invocation.`
35. `I think we should use update set returning`
36. `Since external calls and other side effects that have already occurred cannot be undone, one can choose between reconciliation and compensation.`
37. Final synthesis request: `你帮我总结吧`

## Authentic misconceptions and corrections

### Unknown fields

The student initially said an undeclared `force` field would be rejected automatically. That is not guaranteed
by an open object schema. The strict contract explicitly closes the object with `additionalProperties: false`.

### Rollback versus history

The first rollback wording suggested changing an existing bad version binding. Correction: disable v2 and
block new harm, but never rewrite an issued Attempt. Re-plan as a new Attempt only when policy permits.

### Correlation versus outcome evidence

`dispatch marker` and `provider_request_id` help correlate a request; they do not prove publication. Recovery
also needs durable operation/idempotency state and authoritative external report/version/audit evidence.

### Schema-valid versus executable

The Beginner English answer correctly named incomplete verification and authorization but mentioned signatures
as universal. Signatures are design-specific. Universal remaining boundaries are semantics, trusted-context
authorization, exact tool/version resolution, Admission and execution policy.

### Admission terminology

The Intermediate answer said “tool onboarding.” Tool Admission is a decision for one candidate invocation;
Tool Definition only declares the name/version/argument contract.

### Database atomicity versus external effects

`UPDATE ... RETURNING` is the right direction for a durable atomic claim. It cannot roll back an external HTTP
request already accepted. Unknown outcomes still require reconciliation; confirmed reversible harm may require
compensation.

## Artifact evolution

```text
ordinary text
-> parseable JSON
-> strict field types
-> required / enum / range / items / closed objects
-> cross-field semantic checks
-> exact versioned Tool Definition
-> trusted authorization + tenant-scoped semantics
-> immutable AdmittedToolCall
-> atomic idempotency claim + final disable guard
-> outcome Schema/semantics/identity verification
-> guarded completion + reconciliation
```

The repository Artifact is `src/output_tool_contracts.py`; it was reimplemented from the classroom reasoning,
not copied as evidence from the temporary directory.

## Production failure / rollback exercise

Bad `publish_report@v2` allowed `force: true`:

- A1 v2-bound/not admitted: block; optional explicit safe new Attempt.
- A2 admitted/not executed: final disable guard rejects, zero simulated effects.
- A3 confirmed duplicate: controlled repair/compensation where reversible; preserve original evidence.
- A4 dispatched/timeout unknown: `PENDING_RECONCILIATION`; no blind retry.
- A5 safe v1 in flight: continue under v1; no bulk rewrite/cancel.

## English interview results

- **Beginner:** passed with the signature refinement above.
- **Intermediate:** passed with “Tool Admission” terminology and per-invocation scope correction.
- **Senior:** proposed `UPDATE ... RETURNING`; passed after explaining that a DB rollback cannot undo accepted
  external effects and reconciliation/compensation remain required.

## Final Chinese mental model

> **Attribution: supplied by the teaching assistant at the student's explicit request; not the student's
> independently authored final answer.**

Provider `SUCCESS` 只产生不可信候选。JSON 解析只产生不可信 Python 值；Schema 只证明结构。工具名称、版本、
参数必须经过 Registry、可信服务器身份授权和业务语义验证。Admission 为这一次候选生成不可变的
`AdmittedToolCall`；Executor 只接收它，并在副作用前执行生命周期检查和原子幂等 claim。工具返回仍不是最终业务
成功：Verifier 必须绑定 operation/report/version/Attempt/tool-call identity，Durable Store 再进行 guarded completion。
发送后超时是 `TIMEOUT_UNKNOWN`，必须 reconciliation；确认可逆的错误副作用才进行受控 repair/compensation，且不
删除原始证据。

## Validation status

- `CONCEPTUAL`: completed through progressive teaching, checkpoints, A1–A5 incident exercise and interviews.
- `STATIC`: PASS — py_compile plus mypy on 7 source/test files.
- `EXECUTED_LOCAL_RUNTIME`: PASS — 34 Day74 tests; 131 total with Day72/Day73, Python 3.11.5.
- Python 3.12: NOT RUN — no Python 3.12 executable in the update environment.
- `INTEGRATION_RUNTIME`: NOT RUN — no real SDK/HTTP/Provider/database/queue/external tool/reconciliation.
- `PRODUCTION`: NOT RUN — no credentials, customer data, sensitive prompts or production traffic.
