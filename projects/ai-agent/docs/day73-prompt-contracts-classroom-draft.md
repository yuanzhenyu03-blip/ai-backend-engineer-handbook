# Day73 Prompt Contracts — CLASSROOM_DRAFT

> A recorded classroom-process draft for Day73. It preserves the real student answers, the authentic
> misconceptions and their corrections, the three English interview levels, and the teaching-assistant-supplied
> final Chinese mental model. The released design contract is
> [`DAY73_PROMPT_CONTRACTS.md`](DAY73_PROMPT_CONTRACTS.md); the released lesson is
> [`day73-prompt-contracts-prompt-versioning-and-compatibility.md`](../../../docs/fastapi/day73-prompt-contracts-prompt-versioning-and-compatibility.md).

## Decisions Reached

- A prompt is an **application-owned, versioned execution contract**, not a mutable string and not a Provider
  capability declaration.
- Published revisions are **immutable**; operational status is a **separate lifecycle overlay** (ACTIVE /
  DISABLED / QUARANTINED; unknown fails closed).
- Every Attempt **durably binds** the revision + renderer version + parameter-policy id/revision + application
  contract + input fingerprint + rendered-message hash (+ optional protected artifact ref).
- The **current default** selects a revision for a **new** Attempt only; it never reinterprets an already
  planned or dispatched Attempt.
- The **LLM Runtime** enforces the pre-Provider gate; **business authorization** is a separate earlier owner;
  **model parameters** are a separately versioned Model Parameter Policy; the **Provider Adapter** does not
  choose the prompt revision; **output validation** decides whether a transport SUCCESS is trusted.
- Compatibility is **directional** and both **structural** and **semantic**.
- Incident verbs are distinct: **disable**, **rollback**, **migration**, **re-release** — never rewrite
  history.

## Student's actual answers (verbatim)

1. `A1 应该使用它规划时绑定的 v1`
2. `阻止 A1`
3. `应该由 LLM Runtime`
4. `没有这个边界会产生无效调用provider，应该由LLM runtime检查阻止，并在provider之前`
5. `团队把系统规则从"必须引用证据"改成"引用证据是可选的`
6. `是，不是`
7. `应该拒绝`
8. `不需要，应该由Model Parameter Policy记录`
9. `不是`
10. `不能，应该由应用业务授权逻辑阻止`
11. `是`
12. `应该拒绝`
13. `disable v2 并把新任务默认选择 rollback 到 v1`
14. `不能应该进入PENDING_RECONCILIATION`
15. `A1 绑定的 v2 来解释这个响应，不能`
16. `不能，还应该绑定Renderer version`
17. `不能，rendered_artifact_ref指向受保护的artifact`
18. `以 Attempt Store 中的 v1 为准，A1 状态为blaocked  Provider 调用次数为0`
19. `可以，因为状态还是planned`
20. `因为没有经过组件边界的运行`
21. `不能`

## Authentic misconceptions and corrections

- **Compatibility reasoning.** The student first said renaming `evidence` -> `sources` was backward compatible
  "because the meanings appear similar." Correction: compatibility is not human resemblance; existing callers
  send field names/structures, so without an alias/migration the rename is structurally breaking, and semantic
  guarantees must also be preserved.
- **Attempt-state reasoning.** For a binding mismatch the student said the Attempt should be `blocked`.
  Correction: a dispatch-payload mismatch is rejected before a valid transition — the authoritative Attempt
  stays `PLANNED`, zero Provider calls. `BLOCKED_PROMPT_DISABLED` applies only when the authoritative bound
  revision is itself disabled.
- **Reproducibility evidence.** The student named `renderer_version` (necessary but incomplete). Correction:
  reliable reproduction also needs the prompt revision, parameter-policy revision, application contract,
  canonical input fingerprint, rendered-message hash, and — policy permitting — a protected rendered artifact.
- **Beginner interview boundary.** The student's first English answer mixed Prompt Contract evolution with
  Provider feature/parameter changes. Correction: Prompt Contracts are application-owned behavioural contracts;
  provider capabilities and model parameters are related but separately owned and versioned concerns.
- **Intermediate/senior completeness.** The student correctly identified pre-call runtime validation and
  incident containment, but the intermediate answer omitted lifecycle, authorization, variable/schema
  validation, and authoritative-binding checks; the senior outline needed explicit per-Attempt classifications
  and reconciliation rules.

## Current Artifact Boundary

- `PromptContractRevision` (immutable) + `PromptLifecycle` (overlay, fail-closed UNKNOWN) +
  `PromptContractRegistry` (published revisions + current default for new planning, fail-closed selection).
- `VariableSpec` / `MessageTemplate`; `validate_and_fill_variables` (missing/unknown/type/enum fail closed);
  deterministic `render_messages`; `compute_input_fingerprint` / `compute_rendered_hash`.
- `AttemptPromptBinding` + `InMemoryAttemptPromptStore` (guarded compare-and-set) + `plan_attempt_binding`.
- `prepare_dispatch` pre-Provider gate (BINDING_MISMATCH / UNKNOWN_PROMPT / BLOCKED_PROMPT_DISABLED /
  INCOMPATIBLE_CONTRACT / VARIABLE_INVALID / RENDER_HASH_MISMATCH / READY), each failure `provider_calls=0`.
- `backward_incompatibilities` / `is_backward_compatible`; `apply_migration` (alias conflict fails closed).
- `classify_timeout_unknown` -> PENDING_RECONCILIATION; `interpret_late_response` (interpret with the bound
  revision; refuse terminal/not-awaiting/binding-mismatch).

## English Interview

### Beginner

Student (verbatim): *"A 'Prompt Contract' is an agreement regarding prompt specifications. LLM applications
require prompt versioning because providers may update features, resulting in changes to the parameters
required by the Prompt Contract."* — partial; confused application-owned contract with Provider capabilities.

Reference: *"A prompt contract is an application-owned, versioned definition of the messages, required
variables, and semantic guarantees used to create a model request. Versioning makes each Attempt reproducible
and auditable, lets compatibility be checked explicitly, and lets a bad revision be disabled or rolled back
without rewriting history."*

### Intermediate

Student (verbatim): *"The LLM runtime should verify compatibility with the previous prompt version before the
provider is invoked. Current approaches do not enforce this binding, which can lead to the tampering of
history and render auditing impossible."* — correct direction; needs the full gate list and the authoritative
bound-revision reference.

Reference: *"Before the Provider call, the LLM Runtime reads the Attempt's authoritative prompt binding,
confirms the bound revision is active, validates authorization context and required variables, checks
application-contract compatibility, renders deterministically, and verifies the rendered hash. An existing
Attempt stays bound to its original revision; the current default governs only new planning."*

### Senior

Student outline (verbatim): *"Contain -> disable v2 -> rollback default selection to v1; Scope ->
prompt_contract_id + revision -> renderer_version -> release/time window -> durable dispatch/outcome evidence;
Classify each Attempt -> repair explicitly -> verify -> controlled re-release as v3."* — strong structure;
enumerate per-Attempt handling (planned, successful-candidate, invalid, unknown, late, stale, terminal).

## Final Chinese Mental Model

> **Attribution: supplied by the teaching assistant at the student's explicit request; this is not the
> student's original wording.**

Prompt 不是一段可以随时替换的普通字符串，而是应用拥有的、可版本化的执行合同。每个 Attempt 在规划时必须绑定不可变的 Prompt
Contract revision，并同时记录 renderer version、参数策略版本、应用合同、输入指纹和渲染结果哈希。当前默认版本只影响新任务，不能
重新解释历史任务。

Provider 调用前，应用业务逻辑先负责授权；LLM Runtime 再从权威 Attempt Store 读取绑定，检查 Prompt 生命周期、变量、schema、
兼容性并进行确定性渲染；之后才进入 Provider capability admission 和 Provider Adapter。Adapter 只负责 Provider 特定翻译与错误
归一化，不能选择 Prompt 版本。Provider 返回 `SUCCESS` 也只代表拿到了候选输出，仍需通过输出结构、证据、策略和业务验证。

兼容性既是结构问题也是语义问题，而且有方向。增加有安全默认值的可选变量可能向后兼容；字段改名如果没有 alias/migration 就不兼容；
把"必须引用证据"改成"可选"即使 schema 不变，也是语义破坏。已发布 revision 不可原地修改；出现坏版本时应 disable 该版本、把新任务
默认 rollback 到安全版本、按持久化证据逐个分类 Attempt，并以新的不可变 revision 重新发布。TIMEOUT_UNKNOWN 必须先
reconciliation，不能盲目重试。审计日志只记录最小标识、指纹和哈希；完整渲染 Prompt 若必须保留，应进入受保护、加密、按租户授权、
可审计且有限保留的 artifact 存储。

## Validation Status

- `CONCEPTUAL`: completed through the live scenario, artifact evolution, checkpoints, incident exercise, and
  three interview levels.
- `STATIC`: `PASS` — `py_compile` on the module + tests; sections/fences/whitespace/credential scans.
- `EXECUTED_LOCAL_RUNTIME`: `PASS` — 39 Day73 in-process tests (97 total with the Day72 regression), Python
  3.10.12; in-memory stores + pure functions only.
- `INTEGRATION_RUNTIME`: **NOT RUN** — no real SDK/HTTP/Provider/database/queue/worker/encryption/protected
  artifact.
- `PRODUCTION`: **NOT RUN** — no credentials, customer data, sensitive prompt, or production traffic.

The classroom `/tmp` directory (`/tmp/day73-prompt-contract.bnZaG3`, 11 tests, Python 3.9.6) was NOT copied
into the repository; the repository artifact was reimplemented and re-tested against the latest remote `main`.
The `provider_calls` counter models an in-process boundary crossing only.
