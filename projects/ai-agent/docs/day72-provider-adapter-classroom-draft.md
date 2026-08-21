# Day72 Provider Adapter — CLASSROOM_DRAFT

> Classroom-process record for Day72, now released in the repository as part of the Day72 update (see the
> released design contract `DAY72_PROVIDER_ADAPTER.md` and the lesson). This file preserves the raw classroom
> reasoning; the released, authoritative design is the design contract and the `src/` implementation.

## Decisions Reached

- A Provider that cannot satisfy the stable application contract returns an explicit capability error; the
  Adapter never silently weakens the contract.
- Capability admission runs before a paid Provider call.
- A capability profile is bound to Provider, model, API version, and profile version.
- Provider-specific request fields and response reasons remain inside each Adapter.
- Adapters return distinct application-owned failure classifications plus safe evidence; the LLM Runtime owns
  retry and recovery policy.
- Every Attempt persists the execution-contract version used when it was dispatched. Current configuration
  governs new calls; the persisted contract governs interpretation of an already-issued call.
- Business services depend on the common `ProviderAdapter` interface. A registry/composition boundary injects
  the selected concrete Adapter.
- A client product option is only a constrained selector. Server-owned policy chooses an allowlisted Provider
  Profile and persists its Provider/model/API/capability versions in the Attempt execution contract before
  dispatch. Clients cannot directly authorize arbitrary Provider, model, or profile identifiers.
- If a persisted Profile is disabled before dispatch, the planned Attempt is retained as
  `BLOCKED_PROFILE_DISABLED` with zero Provider calls. Its execution contract is never rewritten. A different
  Profile requires an explicit protected selection decision and a new Attempt; no hidden fallback is performed.
- Replaceability means behavioral substitutability at the application boundary, not byte-identical model text.
  Every Adapter maps equivalent Provider facts to the same application-owned `ProviderOutcomeKind` and keeps
  SDK/wire types behind the boundary. Safe Provider evidence may differ and remains explicit.
- A Provider's documentation or marketing capability claim is not sufficient evidence that it satisfies an
  application contract. Compatibility is bound to a concrete Adapter version and an honest verification tier.
  Native structured-output support does not by itself prove `research_claims.v1` translation, failure mapping,
  evidence validation, or guarded completion.
- Published Capability Profile revisions are immutable audit facts. Runtime drift disables or quarantines the
  affected revision for NEW selections. After investigation and verification, changed capability facts are
  published as a new revision; v3 is never edited in place to look like v4.

## Current Artifact Boundary

```text
Business Service
-> server-owned ProviderSelectionPolicy
-> immutable AttemptExecutionContract
-> ProviderRegistry / composition boundary
-> ProviderAdapter interface
   -> versioned capability profile
   -> provider-independent request/outcome
-> concrete Provider Adapter (now implemented as a deterministic in-process slice)
```

Stable outcome surface (current slice):

```text
SUCCESS | PROVIDER_RESPONSE_INVALID | REFUSAL | TRUNCATION | RATE_LIMITED | AUTHENTICATION_ERROR
| CAPABILITY_ERROR | TIMEOUT_UNKNOWN | TRANSPORT_ERROR
```

Validation ownership:

```text
Provider wire/envelope violates its bound versioned response contract
-> Adapter -> PROVIDER_RESPONSE_INVALID

Provider envelope is valid, but the application result has missing/unsupported tenant evidence
-> LLM Runtime evidence gate -> reject; never complete the Job
```

Full Fake Provider contract and LLM regression testing remain Day77 scope.

Capability claim evidence ladder:

```text
Provider documentation / declared feature       -> current input fact, not application compatibility proof
static Adapter translation review                -> STATIC
deterministic in-process translation execution   -> EXECUTED_LOCAL_RUNTIME
real SDK/HTTP process-boundary execution          -> INTEGRATION_RUNTIME when actually run and saved
real production traffic and operations evidence  -> PRODUCTION only when actually established
```

Profile lifecycle:

```text
ACTIVE -> DISABLED or QUARANTINED
investigate + verify changed behavior
-> publish a NEW Profile revision
```

## Production Failure / Rollback Exercise

Incident:

```text
capability-profile-v4 incorrectly declares that Provider B supports research_claims.v1
-> pre-call admission allows paid calls
-> Provider B returns ordinary text or an invalid response
-> affected Jobs cannot pass the application contract
```

Student's actual answer:

> 先回滚错误发布停止错误版本继续污染新任务，保留审计证据，并按照发布版本及时间窗口界定处理集合。
> 对集合中的job做分类处理。

Review: the ordering is correct. Rollback controls NEW dispatches only and does not undo issued calls, cost,
Attempts, or outputs. The affected set is scoped by profile/release version, a bounded time window, and durable
dispatch/outcome evidence. Each Job is then classified before any repair; there is no bulk retry, bulk success,
Attempt overwrite, or evidence deletion.

Classification boundary:

```text
blocked before dispatch; provider_calls=0 -> eligible only for a new protected selection decision
definite invalid response received         -> retain failed Attempt/cost; evaluate a new Attempt explicitly
TIMEOUT_UNKNOWN after dispatch              -> PENDING_RECONCILIATION; never blind retry
valid late response                         -> same validation gates + guarded completion
stale/terminal Job or superseded Attempt    -> zero-effect refusal
```

## English Interview

### Beginner

Question: What is a replaceable Provider Adapter, and why does an LLM application need one?

Student's verbatim answer:

> The Provider Adapter facilitates bidirectional translation between the provider and the application. LLMs
> require it to enable provider switching and avoid excessive coupling.

Engineering review: correct bidirectional-translation and decoupling model. Add versioned capabilities/failures
and the rule that product semantics must not be silently weakened.

Language correction: `LLMs require it` incorrectly makes the model the subject; use `An LLM application needs
it`. `tight vendor coupling` is more precise than `excessive coupling`.

### Intermediate

Question: A selected provider does not support a capability required by the application contract. What should
the Adapter do, and why should this check happen before the provider call?

Student's verbatim answer:

> Party A should directly reject the request; rejecting it prior to the formal invocation avoids unnecessary
> provider calls and associated costs.

Engineering review: correct pre-call rejection/cost model. Add explicit `PROVIDER_CAPABILITY_ERROR`, zero
external calls, and no silent contract downgrade.

Language correction: `Party A` is a contract/negotiation term, not the Adapter. Say `The Adapter should reject
this provider execution path before making the external call`.

### Senior

Question: A bad capability profile incorrectly allowed several paid calls. Some returned invalid responses,
while others timed out after dispatch. How would you contain the incident and safely repair the affected jobs?

Student's verbatim answer:

> Rollback error, capability profile, retain audit evidence, build a collection for each job, classification,
> explicit fix.

Engineering review: the high-level order is correct but incomplete. Add release/profile/time-window plus durable
execution evidence for the affected set; invalid-response vs `TIMEOUT_UNKNOWN` classification; no blind/bulk
retry; and a new Attempt only after deadline, budget, cancellation, execution-evidence, and guarded-claim checks.

Language correction: use `Roll back or disable the bad capability profile`, `build an affected set`, and
`perform an explicit, guarded repair`.

## Final Chinese Mental Model

> Classroom-authorship note: the student explicitly asked the Tech Lead to provide the final synthesis
> (`你帮我总结吧`). The following is taught material based on the student's completed reasoning, not an
> independently authored student answer.

```text
应用拥有稳定的产品契约；Provider 只提供版本化能力。客户端只能提交受限的产品选项，服务器策略从 allowlist
选择 Provider Profile。Profile 绑定 provider/model/API/profile/Adapter 版本、当前能力和证据等级；已发布版本是
不可变审计事实，运行时漂移只能禁用或隔离旧版本，并在调查验证后发布新版本。

付费调用前，Runtime 用稳定契约与 Capability Profile 做准入；已知不兼容就返回 CAPABILITY_ERROR，Provider
调用为 0，不能把契约降成所有 Provider 的最低共同能力。创建 Attempt 后，必须持久化这次执行使用的契约快照；
当前配置管理新调用，旧 Attempt 的绑定版本解释已经发出的调用，历史不能被新配置改写。

业务服务只依赖统一 ProviderAdapter 接口，组合/注册边界注入具体 Adapter。Adapter 做双向翻译：稳定请求含义
转成 Provider-specific 请求，再把 Provider-specific 响应、完成原因和错误翻译为稳定 ProviderOutcome；SDK/wire
类型不得泄漏。可替换性要求相同应用结果与失败语义，不要求字节相同。Adapter 只返回分类与最小安全证据，不能
隐藏重试、切换 Provider、决定 Job 终态或编造缺失证据。

Provider SUCCESS 仍是未经信任的候选结果，必须继续通过 schema/format、evidence/semantic、application-policy
验证以及 guarded completion，Job 才能 SUCCEEDED。认证、限流、能力不足、非法响应、截断、传输错误和
TIMEOUT_UNKNOWN 必须保留不同分类；尤其超时未知要进入 PENDING_RECONCILIATION，不能盲目创建新 Attempt。

错误 Profile 发布时，先回滚/禁用以停止未来损害，再保留证据，按 Profile/发布版本、有限时间窗口和持久化
执行证据建立 affected set，并逐 Job 分类修复。配置回滚不撤销调用、成本、输出或 Attempt 历史；只有当前
deadline、预算、取消状态、执行证据和 guarded claim 全部允许时，才能显式创建新 Attempt。
```

Profile-disable boundary:

```text
Attempt A1(profile-v3, PLANNED)
-> profile-v3 disabled before dispatch
-> A1 = BLOCKED_PROFILE_DISABLED; provider_calls = 0
-> optional protected re-planning
-> Attempt A2(new persisted execution contract)
```

## Validation Status

| Tier | Status |
|---|---|
| `CONCEPTUAL` | Completed |
| `STATIC` | PASS — Python syntax compilation |
| `EXECUTED_LOCAL_RUNTIME` | PASS — 56 deterministic in-process tests (Adapter translation/contract slice + Day72 round-1 and round-2 review regressions: authoritative-binding store, thread-safe compare-and-set + real concurrency, two-purpose Registry disable path, per-Provider failure translation, one-call guard, transport-inside-adapter, selection-by-contract, duplicate-registry) |
| `INTEGRATION_RUNTIME` | NOT RUN |
| `PRODUCTION` | NOT RUN |

Executed locally with no network or Provider call:

```text
python3 -m unittest discover -s tests -v
Ran 58 tests — OK (Python 3.12.13)
```

Covered: capability rejection before a paid call (zero calls), persisted-binding validation before any call
(job/contract/profile/version mismatches -> AttemptBindingError, zero calls), one external call per Attempt via
a guarded compare-and-set PLANNED -> DISPATCHED transition, the transport staying inside each Adapter
(execute()), Provider-specific request-field isolation, equivalent SUCCESS/TRUNCATION application semantics,
required Provider-request identity validation, selection that uses the application contract, duplicate-profile
registration rejection, and the real disabled-profile -> BLOCKED_PROFILE_DISABLED dispatch path. These fixtures
are classroom-only wire shapes. They do not prove a real SDK/API, real HTTP,
Provider behavior, cost, rate limits, credentials, integration, or production. Full Fake Provider contract and
LLM regression testing remain Day77 scope.
