# Day81 Classroom Record — Agent State Machine, Termination, Loop Detection and Budgets

This is the classroom reasoning record. Student statements are preserved as concise quotations; corrections and
the final synthesis are identified separately. It is not runtime evidence.

## Decisions reached

| Scenario | Classroom decision |
|---|---|
| Verified goal complete and Step budget zero | `COMPLETED/GOAL_SATISFIED`; completion has priority |
| Goal incomplete and Step budget zero | `TERMINATED/STEP_BUDGET_EXHAUSTED`; no automatic retry |
| `TIMEOUT_UNKNOWN` | original Attempt -> `PENDING_RECONCILIATION`; reservation remains held |
| Known prerequisite incomplete | `WAITING`, not reconciliation |
| Repeated activity without verified progress | `TERMINATED/NO_PROGRESS_LOOP_DETECTED` |
| Current authorization revoked | block dispatch, retain history, release only safely releasable reservations |
| Old Tool v1 disabled and v2 exists | do not rewrite; retain v1 Step and create a new authorized Step later |
| Provider 404 plus dispatch evidence | still unknown; reconcile before any retry |
| 6000 tokens reserved, 1800 verified | settle 1800 and release 4200 |
| Unknown Provider cost | hold the reservation pending reconciliation |
| Compensation result unknown | compensation operation enters `PENDING_RECONCILIATION` |

## Student answers and Tech Lead resolution

- “不能以 `BUDGET_EXHAUSTED` 终止” was correct for the already verified-complete goal: the terminal reason is
  `GOAL_SATISFIED`, because budgets are irrelevant after guarded completion.
- “`BUDGET_EXHAUSTED` 不可以自动重试” was accepted for the incomplete-goal case. A retry would consume new
  authority and budget; the state machine cannot manufacture either.
- “让原来的 `A7` 进入 `pending_reconciliation`” was accepted. Unknown external outcome stays attached to the
  original Attempt identity.
- “idempotency key 只是抑制重复副作用” was accepted. Fencing is the stale-writer control.
- “没有取得真实进展，verified observations” established the loop rule: progress is a verified observation,
  not a changed action string or another model turn.
- “应该使用 `NO_PROGRESS_LOOP_DETECTED`” was accepted when a hard loop was proven despite remaining budget.
- “记录1800，剩余的4200释放” was accepted as verified reservation settlement.
- “应该进入 `wait`” was accepted only when the prerequisite and lack of side effect were known.
- “继续保持 `PENDING_RECONCILIATION`” was accepted for unresolved external outcome/cost.
- “应该原子性提交使用 `update set returning`” became the production persistence requirement. The Day81 code
  models the boundary in memory and does not claim a real database transaction.
- “应该保留运行记录” and “不能，lifecycle” established that revocation or rollback cannot delete or rewrite
  Jobs, Steps, Attempts or Tool Calls.
- “能，应该进入 `pending_reconciliation`” was accepted for a compensation operation whose outcome became
  unknown.
- “停止错误版本执行新的step、attempt，回滚错误版本到稳定已验证的版本” became the incident containment rule;
  it was extended with lease revocation, fence advancement and evidence-preserving classification.
- “A1进入replan A2进入terminal A3进入pending_reconcilation A1释放 A2结算 A3剩余[保持]” was refined: A1 may
  release and replan if dispatch is disproven; A2's Attempt can settle terminally while Job goal completion remains
  a separate guard; A3 holds and reconciles.
- “应该采用 compensation” was accepted for already-observed external effects, with compensation represented as
  a new auditable operation rather than history deletion.
- “只返回结构化候选决定，由另一个边界原子应用” became the pure-decision/authoritative-apply split.

## English interview answers

Student answer:

> The state machine controls the target process based on verified audit facts. The model can only provide recommendations.

Accepted. The sharper formulation is: the model proposes; verified facts and legal guards produce a candidate;
the authoritative conditional apply boundary alone changes durable state.

Student answer:

> It should enter `pending_reconciliation` instead of retrying immediately.

Accepted for any dispatched operation whose external outcome remains unknown. The same Attempt identity and held
reservation must be reconciled first.

Student incident answer:

> Suspend new controller planning, step creation, and scheduling; Cancel or isolate erroneous releases/policies;
> Revert subsequent planning to the stable version; Revoke leases for old workers and advance fence tokens;
> Re-examine current lifecycles, releases, and authorizations at the Provider/Tool operational boundary; Determine
> the scope of impact based on release versions, time windows, and identities; Preserve the full history of Jobs,
> Steps, Attempts, Tool Calls, and reservations for all entities; Handle the recovery of in-flight Attempts;
> Separately classify, validate, and reconcile external events that have already occurred using new, auditable
> operations.

Accepted as the incident-recovery sequence. Stable code plus passing tests is not closure by itself; closure also
requires scoped entities, resolved/held outcomes, reservation settlement, audit continuity and controlled rollout.

## Instructor-supplied final Chinese synthesis

> Agent 状态机不是把模型说的话直接变成状态。模型只能给建议；系统用已验证的审计事实、当前生命周期、
> 授权、工具绑定、进展证据和预算守卫生成结构化候选决定，再由一个原子权威边界比较 Job/Step/Attempt、
> 旧状态和 fence token，提交状态、预算预留与新 fence。只有真正 `APPLIED` 的 `CONTINUE` 才能产生新的
> 可执行 Step。未知外部结果进入 `PENDING_RECONCILIATION`，已知前置条件不足进入 `WAITING`；终止不等于
> 删除历史，补偿也不是回写旧 Attempt。预算限制消耗，进展证据决定是否陷入循环，两者不能互相替代。

The student explicitly asked the Tech Lead to provide this final Chinese summary; it is therefore labeled
instructor-supplied rather than attributed to the student.

## Evidence boundary

The classroom discussion drove 20 deterministic tests. No real Provider, Tool, PostgreSQL transaction, durable
queue, billing ledger or production incident was exercised.
