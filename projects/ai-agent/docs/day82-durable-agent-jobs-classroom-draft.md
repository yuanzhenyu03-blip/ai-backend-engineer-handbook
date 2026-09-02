# Day82 Classroom Record — Durable Agent Jobs, Checkpoint, Resume and Recovery

This file preserves the real classroom reasoning. It is not runtime evidence. Student wording is retained where
useful; corrections are explicit rather than silently rewriting the student into an expert.

## Repository facts used

- Remote `main`: `6d59775e1b7338d9f5e078220fe997ca3e62b748`.
- It was identical to the known Day81 release commit.
- Day81 was Completed with 20 focused / 293 cumulative tests on Python 3.11.5.
- Day82 was Planned and no formal Day82 lesson or Artifact existed.
- A dirty local clone was deliberately not used or modified; the later repository update used a clean isolated
  clone.

## Student reasoning and decisions

| Scenario | Student answer | Review |
|---|---|---|
| Restart source | “从已提交的权威 Job 状态与 Checkpoint继续” | Correct. Process memory/model context is not truth. |
| Committed Outbox, not published | “继续发布原来已经提交的 Outbox Intent” | Correct; no new Step or Reservation. |
| Publish checkpoint missing | “不能可以进行发布” | Correct intent: cannot infer no publish; may republish the same event. |
| Duplicate Queue Message | “识别为 A1 的重复投递” | Correct; duplicate transport is not a new business Attempt. |
| W1 stale fence | “不能” | Correct; old Worker cannot write after W2 advances the fence. |
| Late result | “保留为证据并根据原 Attempt identity 进行分类” | Correct; evidence does not restore authority. |
| A0 Checkpoint for A1 | “不可以” | Correct identity mismatch refusal. |
| Checkpoint state version 12 vs current 13 | “先拒绝并重新读取当前权威事实” | Correct compare-and-set mental model. |
| Tool v1 -> v2 | “不可以” silently replace | Correct; historical binding is immutable. |
| v1 disabled, definitely not dispatched | “保留 A1 并执行 Replan” | Correct; new planning must pass current guards. |
| Provider response lost | “原来的 A1 进入 PENDING_RECONCILIATION” | Correct; no blind A2. |
| Provider 404 | “不能” prove never executed | Correct; contract/identity/retention evidence is required. |
| Retry prerequisites | “重新检查reservation” | Correct but incomplete; lifecycle/auth/deadline/budget/version/fence were added. |
| 6000 reserved, 1800 verified | “结算1800剩下的4200进行释放” | Correct. |
| Goal complete, cost unknown | Job may complete; cost remains reconciliation | Correct; Reservation stays HELD. |
| Candidate before transaction crash | “不存在，不能” | Correct; candidate is not commit evidence. |
| Committed Outbox recovery | Read the `published_at` null “raw” | Correct concept; `raw` corrected to database `row`. |
| Wrong internal Checkpoint pointer | “Repair” | Correct; no external effect to compensate. |
| Confirmed wrong publication | Preserve A2 and create Compensation | Correct; Compensation is a new operation. |
| Bounded recovery exhaustion | “停止自动恢复并升级处理，不能” release | Correct; unknown remains unknown/held. |
| Recovery count in Worker memory | “没有效，应该保存在数据库中” | Correct. |
| Evidence level | “execution_loacation_runtime” | Correct idea; name corrected to `EXECUTED_LOCAL_RUNTIME`. |

## Important corrections

### Containment does not delete Outbox history

The student proposed cancelling pending Outbox Events. The safe refinement was to preserve and quarantine/suppress
them with audit evidence because some may already have been published.

### Scope is more than release plus time

Release version plus publish-to-disable time was a correct starting point. It was expanded with a padded window,
tenant/Job/Step/Attempt/Checkpoint/event/reservation/lease/fence/external-operation/binding identities, and
commit/publish/delivery/claim/dispatch/outcome/late-result evidence.

### Verified terminal does not automatically mean Compensation

The student first classified A2 directly as Compensation. The correction preserved A2 as verified terminal,
settled 1800 and released 4200, then created Compensation only if the confirmed effect was unwanted.

### Reservation is not the budget

The final synthesis called Reservation “预算”. It was refined to capacity held against a budget for one Attempt.

### Republish is not a second business dispatch

“Worker重新第二次分发” was refined: Relay may republish the same Outbox Event identity; Consumer must not create
a second business Attempt or effect.

## Crash Window Exercise

- Case A: no commit -> no new durable facts; reread and re-decide.
- Case B: state/Checkpoint/Reservation/Outbox committed -> resume them; no double reserve.
- Case C: publish may have succeeded before `published_at` -> republish same identity; Consumer deduplicates.
- Case D: W2 fence 9 rejects W1 fence 8; preserve W1 late result as evidence.
- Case E: dispatched operation with lost response/ACK -> original identity + HELD Reservation + reconciliation.

## Failure / rollback exercise

The student's containment correctly restored a verified stable release, blocked new bad-release work, isolated
Workers and stopped scheduling. The final sequence also quarantined affected Outbox work without deletion,
revoked leases, advanced fences, preserved history and required controlled rollout.

The student initially classified:

> A1可以进入reject A2进入compensation A3进入pending_reconcilation A1释放 A2结算后释放剩余的 A3继续保持held

Final classification:

- A1: definitely not dispatched -> reject old execution, release 6000, then replan/retry only after current guards.
- A2: verified terminal -> settle 1800/release 4200; compensate only for an unwanted effect.
- A3: TIMEOUT_UNKNOWN -> original Tool-v1 operation identity, 6000 HELD, no new Attempt.

The student correctly rejected incident closure based on stable rollback and tests alone and supplied a complete
English closure-evidence sequence: quarantine, stop planning/scheduling, revoke lease, preserve audit, classify
Attempt/Reservation outcomes and use controlled rollout.

## English interview record

Beginner answer about process memory correctly identified restart/failure loss. It was strengthened with the term
“volatile” and the fact that per-Worker memory is not shared authoritative truth.

The Checkpoint answer was strong:

> A checkpoint contains committed recovery facts bound to a specific Job, Step, Attempt, state version, fence
> token, and immutable execution bindings. Unlike a log or a conversation summary, it represents an authoritative
> recovery position that a new worker must validate before continuing.

The Resume/Retry answer used generic “Recovery” and reversed two actions. Correction: definitely-not-executed may
allow a new Retry Attempt; a confirmed unwanted external effect requires a separate Compensation operation.

The Outbox answer correctly used `published_at IS NULL`, at-least-once and database idempotency. It was refined to
say “republish the existing Intent with the same event ID” and add lifecycle/version/fence guards.

The late-result answer correctly retained evidence but initially omitted the primary control: W1's stale-fence
authoritative write must affect zero rows.

The senior A1/A2/A3 and incident-closure answers were technically complete. Vocabulary corrections included
`dispatch` rather than `shipment`, `replanning` rather than `rescheduling`, and `Compensation Operation` rather
than `compensation entry`.

## Student's final Chinese synthesis

> durable job是一个持久化在数据库中的业务请求，authoritative Checkpoint是job执行过程中的存于数据库中的
> 可恢复事实， transaction + Outbox包含了写入预算、写入Checkpoint、写入state version等与分发意图。
> 即使崩溃可以worker可以通过核对持久化事实重新第二次分发。resume/recovery classification，resume属于
> recovery的其中一种恢复方式，表示继续使用原来的job/attempt。每一个worker分配了lease与fence，给了一个
> 权限期限以及fence可以防止过期的worker去覆盖已经接管工作的worker的结果，防止过期worker写入数据库。
> reservation为预算，在明确未调用或者已准确结算才进行预算释放。不然进入核对状态保持held.evidence honesty
> 则是执行证据也需要存于数据库中进行审计与核对

Final correction: a durable Job is an execution entity, not merely a stored request; Reservation is held capacity
against a budget; republishing the same event is not a second business action; durable evidence may use protected
references rather than persisting sensitive raw payloads.

## Validation record

An isolated scratch model first reached 22 tests. The repository Artifact then evolved to 32 focused tests.
`py_compile` and 32 focused tests passed on Python 3.11.5; 325 cumulative project tests passed.

One repository focused-test invocation failed because it addressed `tests.test_day82_durable_agent_jobs` as a
Python package even though `tests/` has no package initializer. The corrected discovery command passed. No real
PostgreSQL, Outbox, Broker, Worker process, Provider, Tool, billing system or production environment participated.
