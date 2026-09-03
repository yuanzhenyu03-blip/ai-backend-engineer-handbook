# Day83 classroom record — teaching closeout

This record preserves real student answers and guided corrections. It is not a repository release record
or proof of independent mastery. Original filename retained for continuity.

## Selected actual answers and precise corrections

| Situation | Student answer | Review / refinement |
|---|---|---|
| Model claims user consent | 不可以 | Correct: text is not authority. |
| Final approval owner | 应用拥有的 durable control boundary 来认定 | Correct. |
| Read vs publish risk | 只需要审批发布动作 | Correct in this public-read scenario; still apply current policy. |
| Artifact/arguments changed | 不能，应该拒绝 | Reject execution with old approval; preserve old decision, request new exact approval. |
| Duplicate callback | 不应该 | No duplicate state/Outbox/reserve. |
| Reused decision identity, different content | 不是 | Conflict, not duplicate; preserve both meanings as evidence. |
| Requester equals approver | 没有效，不应该允许 | Correct separation-of-duties boundary. |
| Approver wrong tenant | 无效 | Correct, role names do not cross tenant scope. |
| Expired approval / revoked authorization / disabled Tool v1 | 不能 | Correct; no silent renewal, permission override or v2 substitution. |
| Concurrent stale candidate | 应该不做任何业务改变的操作，只是查询到第一个进程的记录 | Conditional apply first affects zero rows; reread then identify duplicate vs other change. |
| Committed Outbox before crash | 恢复进程应该继续发布已提交的原 Outbox Intent | Correct original identity; dispatch still checks current facts. |
| Consumer race | 需要原子的幂等 claim | Correct; no external exactly-once inference. |
| Pre-dispatch interrupt | 阻止调用 | Correct; release only proven-unused reservation. |
| Post-dispatch cancellation | 不能 | Correct: cannot infer no publication or zero cost. |
| Worker stops, why no absence proof? | 不能保证立即停止 | Correct but incomplete: already-sent Tool may have published or continue independently even after Worker stops. |
| Stale W1 result | 没有写入权限，拒绝写入，并保留执行证据 | Correct: no current-state write; retain original-identity evidence. |
| Recovery exhausted | 将未解决事项持久化交给有权限的负责人 | Correct; also stop automatic recovery and keep unknown reservation held. |
| Operator says close without evidence | 不能 | Correct; acknowledgement is not resolution. |
| Compensation approval | 还是需要为新的 Compensation Operation 单独申请审批 | Correct new action and approval identity. |
| Bad policy containment | 隔离已经处于工作中的旧V7 停止旧V7继续接受新业务 | Correct; expanded to planning, Outbox/dispatch, lease revocation/fence, no history deletion. |
| Affected scope | tenant、step、job、attempt | Correct identity core; expanded with approval/policy/Checkpoint/Outbox/operation/reservation/late evidence. |
| A1/A2/A3 accounting | release、settle、held | Correct; quantified A1 6000 release, A2 settle1800/release4200, A3 6000 held. |
| Rollback + tests closes incident? | 不足 | Correct; classify impact, retain ownership, controlled rollout evidence. |
| Completed Job cost reconciliation requires reopening? | 不用 | Correct independent lifecycle. |
| Rejected approval automatically resubmitted forever? | 不能，顺便说一句之前在docker安装过postgresql | No retry-until-approved; Docker PostgreSQL is an environment lead only, not validation. |
| Post-interrupt structured result | false `reservation_action`=held 后续处理动作pending_reconcilation | Correct semantics; action KEEP_HELD vs state HELD; spelling PENDING_RECONCILIATION. |
| Wrong implementation vs expected | 修正实现并保留原预期，我觉得根据之前提示词约束需要解释一下第一次出现的名词比如：eval | Correct. Assistant acknowledged teaching omission and explained Eval, Seed Eval, deterministic grader and contract before proceeding. |
| Policy unavailable before dispatch | 暂时阻止发布等待策略恢复 | Correct: missing control policy is not unknown external execution. |
| Policy deadline escalation reason | 创建 Escalation,reason记录recovery_exhausted | Escalation correct; refine root cause APPROVAL_POLICY_UNAVAILABLE and trigger POLICY_WAIT_DEADLINE_EXCEEDED. |
| Owner unavailable | 也给一个处理期限并发出告警？ | Correct; add permitted fallback and distinguish sent/accepted/resolved. |
| Approval unanswered | 记录审批超时并进入升级处理 | Correct, not a fabricated REJECTED decision. |
| Cancelled request, late approved callback | 拒绝，并保留执行证据 | Correct refusal; evidence is callback/decision evidence because no execution occurred. |
| Candidate allowed before apply succeeds | 不能 | Correct, candidate is not execution authority. |

## Mental model evolution

Day82's committed execution/recovery facts were extended to application-owned human-control facts.
Approval is exact, scoped, expiring consent within current authorization. Interrupt limits future work but
does not erase external effects. Escalation preserves uncertainty and assigns permitted responsibility.
Candidates cannot mutate state; conditional apply and execution-time recheck remain mandatory.

The assistant initially overused brief yes/no checks. Later exercises moved to structured outputs, affected
scope, accounting classifications and evidence boundaries. Never claim the student independently supplied
all schema fields or detailed explanations that were taught by the assistant.

## Artifact and validation

Independent archive overlay only; original repository files and remote unchanged. Python 3.11.5 ran 53
Day83 tests, 378 cumulative tests, 26 seed cases and the example successfully. See the adjacent design and
saved evidence for two actual application-fixture failures, corrections, exact commands and limitations.
No PostgreSQL or paid/real Provider call was made. The user said PostgreSQL had previously been installed
in Docker; that statement is not evidence that it was running or used here.

## Actual English interview answers and review

Transcriptions retain the student's wording; incidental standalone backslashes and trailing input noise
are omitted. Model answers below are instructor-authored, not student quotations. Connected concepts were
covered through questions and feedback, not independently answered in full on every subtopic.

### Beginner 1 — Human approval

Student: “Manual iteration is a candidate decision for an iteration generated when facing high-risk execution.”

Review: `Manual iteration` means 人工迭代, not 人工审批. Approval is exact, time-limited human consent;
submitted input is not yet an application-validated approval fact. Candidate control decisions still need apply.

Model answer: Human approval is a time-limited decision made by an authorized person to permit a specific
high-risk action. The application validates and records it. Approval does not replace current authorization
or execution-time checks.

### Beginner 2 — Model-provided consent

Student: “Since the model can only provide recommendations, there has been no comprehensive validation regarding whether they are approved.”

Review: Core direction correct. Authority, not merely completeness of validation, is decisive. `They` is
ambiguous; start with Because and name the approval and authoritative application record.

Model answer: Because the model can propose actions, but it cannot establish approval authority. Only the
application can validate and durably record approval from an authorized person for the exact action.

### Beginner 3 — Interrupt

Student: “Interruptions are categorized into those occurring before and after dispatch. Before dispatch, the worker can halt execution; after dispatch, the outcome is uncertain, necessitating a transition to `pending_reconciliation`.”

Review: Good pre/post distinction. Application boundary must block pre-dispatch calls. Post-dispatch does
not always mean unknown; use trusted results when available. Prefer the system term interrupt.

Model answer: An interrupt is an application-controlled request to stop further execution. Before dispatch,
it should prevent the external call; after dispatch, it cannot guarantee an immediate stop. If the outcome
is unknown, the system moves to pending reconciliation.

### Beginner 4 — Escalation

Student: “There is a time limit for the automatic recovery of application systems; once this limit is reached, an escalation is required to transfer responsibility to the owner, and all records must be preserved.”

Review: Add attempt limit, authorized owner, reason, evidence, deadline and alert. Unknown reservations stay
held. Prefer automated recovery and relevant evidence rather than the overly broad all records.

Model answer: Escalation is a controlled handoff of an unresolved issue to an authorized owner. When
automated recovery reaches its time or attempt limit, the system stops automatic retries and records the
reason, relevant evidence, owner, and resolution deadline.

### Intermediate 1 — Approval versus authorization

Student: “Approval is a high-risk decision made at the human level; upon authorization and successful authentication, the application is granted limited execution privileges.”

Review: Conflates identity, permission and consent. Authentication identifies the actor; authorization
checks current permission; approval records consent to this exact action. Authentication does not grant permission.

Model answer: Approval records an authorized person's consent to a specific high-risk action. Authorization
determines whether the actor is currently permitted to perform that action. A valid approval does not
replace execution-time authorization checks.

### Intermediate 2 — Changed arguments

Student: “If substitution is not explicitly recorded as authorized, the substitution cannot be implemented; verify this prior to inspection.”

Review: Too vague. Changed arguments do not match the original exact approval; a still-approval-required
new action needs new approval. `Before execution` is clearer than `prior to inspection`.

Model answer: No. The approval is bound to the original action and its exact arguments. If those arguments
change, the system must obtain a new approval and validate its binding before execution.

### Intermediate 3 — Duplicate versus conflicting callbacks

Student: “The approach primarily utilizes an idempotent claim mechanism; upon receiving a decision indicating a conflict, execution should be halted, and the conflict resolved by verifying the evidence of execution.”

Review: Separate approval intake deduplication from Worker dispatch claim. Duplicate intake returns the
stored result without repeating business effects. Conflicts are rejected and audited; original decisions
are not overwritten. Evidence is approval evidence, not necessarily execution evidence. Local implementation
also creates a conflict escalation alert intent; that control-plane record is not a repeated publication.

Model answer: An identical callback should be handled idempotently by returning the previously recorded
result without repeating business changes. A conflicting decision should be rejected and audited without
overwriting the original decision.

### Intermediate 4 — Disabled tool after approval

Student: “The system should reject the request, citing the cancellation of the tool as the reason.”

Review: Correct blocking. Disabled is not cancelled. Reject dispatch without automatically rewriting the
original approval as rejected or revoked. Approval cannot override a current disabled-tool fact.

Model answer: The system should block dispatch because the tool is currently disabled and record that
reason in the audit log. A valid approval cannot override execution-time checks.

### Intermediate 5 — Escalation owner timeout

Student: “The system should continue to be upgraded to transfer responsibility to other responsible parties, rather than shelving the matter.”

Review: Use escalated, not upgraded. Require a designated authorized fallback, new deadline, timeout
evidence and alert. Handoff does not authorize blocked business execution or prove resolution.

Model answer: If the owner misses the deadline, the system should record the timeout and escalate the
issue to a designated, authorized fallback owner. It should set a new deadline, trigger an alert, and
keep unsafe execution blocked.

### Intermediate 6 — Failing safety evaluation

Student: “This should be implemented; established rules and expectations must not be altered simply to accommodate specific operational outcomes.”

Review: Correct preserve-expectation principle. Use `The implementation should be fixed` to make the fix explicit.

Model answer: The implementation should be fixed because it violates the approval requirement. We should
preserve the expected result rather than weaken the safety rule just to make the evaluation pass.

### Senior 1 — Crash before execution-intent commit

Student: “No, because there may be other unknown changes during this period, requiring re-verification.”

Review: Revalidation is correct but incomplete: previous validation is not a committed execution intent.
Recover from authoritative durable facts and commit the guarded intent before dispatch.

Model answer: No. A previous validation is not a committed execution intent. The recovery process must read
the durable state, revalidate the current conditions, and atomically commit the execution intent before dispatch.

### Senior 2 — Crash after Outbox commit

Student: “Publish the original intent and use an idempotent claim to prevent duplicate scheduling.”

Review: Correct original identity. Consumer-side atomic claim suppresses repeated execution triggers, not
necessarily duplicate delivery. Local claim cannot guarantee external exactly-once effects after uncertainty.

Model answer: Recovery should publish the original committed Outbox intent. The consumer should use an
atomic idempotent claim to prevent duplicate deliveries from triggering duplicate execution.

### Senior 3 — Expired Worker lease and late success

Student: “Expired worker tasks cannot continue execution, but the execution process can be retained as evidence for subsequent auditing.”

Review: Loss of lease removes authority to write; it does not prove the external operation stopped. Retain
late results with original identity, for verification by the current authorized recovery path.

Model answer: A worker whose lease has expired must not update authoritative state. Its late result should
be preserved as evidence linked to the original attempt and operation. An authorized recovery process can
verify that evidence for reconciliation.

### Senior 4 — Mixed rollback reservations

Student: “Confirmed unused: Release the full 6,000 (1,800 of which is creditable for settlement) and release the remaining 4,200. Usage unknown: Keep the full 6,000 on hold and proceed with the original identity reconciliation.”

Review: A3 correct; A1 and A2 were combined ambiguously, risking double release. Keep them separate:
A1 release6000; A2 settle1800/release4200; A3 held6000. Do not erase this later imprecision merely because
the earlier Chinese classification was correct.

Model answer: For A1, release all 6,000 reserved units. For A2, settle the verified usage of 1,800 and release
the remaining 4,200. For A3, keep all 6,000 on hold and reconcile using the original attempt and operation identities.

### Senior 5 — Completed Job, unresolved accounting

Student: “Jobs and reservations have distinct lifecycles; once a job completes, usage reconciliation can proceed.”

Review: Correct. Lead with No and explicitly state that the Job is not reopened and business action not repeated.

Model answer: No. Jobs and reservations have separate lifecycles. Usage reconciliation can continue after
the job is completed, without reopening the job or repeating the business action.

### Senior 6 — Incident closure

Student: “Is the impact set complete, and are A1, A2, and A3 categorized item by item? Does an erroneous publication require new compensation? Do unknown results and held reservations have clearly defined owners, deadlines, and alerts? Are legacy workers, duplicate messages, and late results still correctly constrained? Are audit records continuous and traceable?”

Review: Strong impact checklist. Lead with a conclusion instead of only questions. Add separate approval
for the compensation operation. Ownership alone is not sufficient closure; explicit closure criteria apply.

Model answer: No. Stopping new work only contains the incident; it does not resolve its existing impact.
Before closure, we must account for affected attempts, verify controls on stale workers and duplicate
messages, and ensure unresolved outcomes have authorized owners, deadlines, alerts, and traceable evidence.
Any required compensation needs its own approval.

### Senior 7 — Local evidence versus real-call authority

Student: “Not allowed; evidence level is EXECUTED_LOCAL_RUNTIME.”

Review: Correct evidence boundary. The student did not independently enumerate real-call bounds; the
instructor supplied them. For this course's optional Provider gate, the stricter original contract applies:
synthetic input, no external business Tool effect, one successful call maximum, immediate authorization,
tiny token/cost budget, timeout, no automatic retry, original-identity unknown handling and redacted evidence.

Model answer: No. Passing local tests provides local runtime evidence, not authorization for external
calls. A real call requires explicit approval for the specific operation, bounded scope and cost, and
execution-time checks.

## Final Chinese mental model — assistant-authored by explicit request

Student: “你帮我总结吧”. After receiving the summary, student: “好的”. These are requests/acknowledgements,
not evidence of an independent final synthesis. Do not attribute the following synthesis to the student.

人批准具体动作，应用掌握执行权；中断不等于外部停止，未知不等于失败，升级不等于问题已解决。

1. 高风险动作由有审批权限的人批准，绑定精确动作、租户、参数、产物版本与期限；应用验证并持久化。
2. 执行前复查当前权限、审批、工具、状态和 fence。受保护事务建立状态、审计与原 Outbox Intent；
   已提交原意图恢复发布，未提交不可直接执行。消费者原子幂等 claim 不等于外部 exactly-once。
3. 派发前阻止调用；派发后不能保证立即停止。未知结果保持原 Attempt/Operation 对账，不盲目再执行。
4. 确认未用释放、确认用量结算余量释放、未知保持 HELD。终态 Job 不因对账重新打开。
5. 自动恢复有界；耗尽停止自动尝试，将原因、身份、证据、负责人、期限与告警持久化交接。
   超时交给有权限的备用负责人；补偿是新的需独立审批的操作。
6. 本地测试是本地证据，不是外部调用许可证；真实 Provider Gate 为 NOT RUN。

## Closeout and remaining limits

Classroom teaching, local checkpoint and guided interviews are wrapped up. The assistant-authored final
summary replaces the requested independent recap at the student's request; independent synthesis is NOT
ASSESSED. At classroom closeout, publication and status updates awaited a separate request.
The user subsequently asked “帮我更新仓库”; the repository coding agent integrated the materials and updated
local progress surfaces. At that stage no commit or push was authorized/performed. The later request
“帮我更新远程GitHub仓库” separately authorized publication. Fresh rerun evidence is in
[repository validation](../evidence/day83-repository-validation.json); classroom evidence remains historical.
Do not claim each required interview subtopic was independently answered: expiry, revocation and cooperative
cancellation were also reinforced through earlier Chinese exercises and guided feedback.
Day84 is Conversation Memory vs Durable Business-state Boundaries: remembered conversational consent is
context, not an authoritative approval or business checkpoint. Day84 has not started.
