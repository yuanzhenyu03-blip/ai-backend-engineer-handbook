# Day84 — Conversation Memory vs Durable Business-state Boundaries

Status: IN PROGRESS. Independent classroom overlay; no repository publication.

## Baseline and evidence boundary

- Remote main verified through git ls-remote and the GitHub ref API on 2026-09-03:
  `e38ee35607c09340929e70331807a54a7717dd6d`, identical to the known Day83 release.
- Classroom checkout: `/Users/yuanzhenyu/Documents/AI backend for codex/day84-classroom`,
  detached at that commit. The original modified checkout was left untouched.
- Live teaching prompt, lesson template and complete Day83 lesson read. Related status
  sections and historical evidence were inspected selectively, not all historical logs.
- Seven Day83 executable/seed file SHA-256 hashes matched saved repository-validation
  evidence. Historical Python 3.11.5 results: 53 focused / 378 cumulative tests,
  26/26 version-1 seed cases and local checkpoint PASS. These are not Day84 runs.
- Day83 completion was guided; the final Chinese synthesis was instructor-authored
  at the student's request. Independent final synthesis NOT ASSESSED.
- Day84 implementation, syntax checks, tests, seed eval and scenario: NOT RUN so far.
- Real Provider/summarization API, Memory DB, PostgreSQL, Object Storage, external Tool,
  authentication/callback, Queue/Worker, billing and alert delivery: NOT RUN.

## Actual classroom interaction

### 1. Summary versus current approval

Teacher question: 重启后，聊天摘要写着“报告 v7 已获批准”，但应用中的审批记录还是
PENDING。恢复进程下一步应该依据什么继续处理？

Student: “依据审批记录”

Review: Correct authority selection. Instructor added: reread the current application
record; PENDING keeps publication blocked. Summary loading cannot establish APPROVED.
Even an approved record still requires Day83 execution-time checks. These additional
details were taught, not independently enumerated by the student.

### 2. Storage location does not grant authority

Teacher question: 如果这份聊天摘要也存进了 PostgreSQL，它是否就能成为有效审批的依据？为什么？

Student: “不能”

Review: Correct conclusion. The instructor supplied the explanation: persistence does
not change the writer, validation, scope, lifecycle or authority of a derived summary.
The student did not independently explain the reason in this answer.

### 3. Explicit language preference

Teacher question: 用户说“以后默认用中文回答”。保存这个偏好时，应该更新哪类记录？
需要改变当前 Job 的审批状态吗？

Student: “更新持久化记忆，不需要改变当前job审批状态”

Review: Correctly separates the preference update from the Job's approval lifecycle.
Instructor extension: a context-only preference update also leaves business Job state,
Attempt identity, Reservation and execution Outbox unchanged; no paid model call is
needed for this deterministic preference update. Scope and write authorization still
need to be established by the application.

## Incremental Artifact contract — conceptual, not implemented yet

Continue the existing multi-tenant Research Agent and publish_research_report.v1.

1. Loading a conversation summary does not mutate Approval or create publication Outbox.
2. An accepted explicit language preference changes only the allowed memory record and
   its own revision. It does not advance business state/version, create a business
   Attempt, reserve/release cost or enqueue execution.
3. Future assembly must choose currently accessible, correctly scoped sources before
   model or summarizer exposure. Selection and invalidation contracts are the next step.

## Assessment and remaining work

The three responses above support the limited authority distinction practiced so far.
Scope/lifecycle exercises, working context/history distinctions, assembly, budgeting,
bounded Tool results, compaction, rehydration, executable composition and validation,
rollback, English interviews and final synthesis remain outstanding. No completion or
independent mastery claim. No Day84 Repository Update Input has been generated.

### 4. Pre-model tenant authorization

Student: “做授权验证”

Review: Correct. Instructor added that scope and current permission must be
checked before content reaches the model or summarizer; relevance is not access.

### 5. Expired memory

Student: “不采用这条记忆”

Review: Correct exclusion decision. Instructor added a typed omission reason and
distinguished exclusion from deletion of business or audit records.

### 6. Invalidated source through an old summary

Student: “不能”

Review: Correct conclusion. Instructor supplied the provenance/invalidation
reasoning: an old derived copy does not acquire independent access authority.

### 7. Context budget

Student: “压缩旧对话”

Review: Correct policy choice for optional history. Instructor calculated the
150-token remaining input allowance and explained that compaction must be
remeasured and cannot remove mandatory control inputs.

### 8. Partial long Tool result

Student: “部分数据源查询失败，本次结果不完整”

Review: Correctly preserved the hidden warning. Instructor added the structured
status, coverage, truncation, size and controlled-continuation fields.

### 9. Empty excerpt

Student: “不能”

Review: Correct: no displayed items cannot support a complete-empty claim.
Instructor distinguished original-result incompleteness from context truncation.

### 10. Unknown side-effecting result

Student: “pending_reconciliation”

Review: Correct state classification. Instructor supplied the required action:
verify the original Attempt/operation identity, keep HELD, and do not replay the
side-effecting publication merely to recover a lost response.

### 11. Concurrent source-span change

Student: “检查source span”

Review: Correct. Instructor added the exact scope/head/version/fingerprint checks;
event 51 makes a candidate over events 1–50 stale. A fingerprint is integrity
evidence, not truth or authorization.

### 12. Failure before summary publication

Student: “summary-v7”

Review: Correct committed-version choice. The candidate v8 never becomes active;
no partial publication or business-state mutation is allowed.

### 13. Summary, Checkpoint, Approval and verified outcome

Student: “上下文摘要只能作为模型建议，不能替代数据库checkpoint的业务实际状态，
也不等同人工审批，也不等同被验证的工具输出结果。”

Review: Correct separation of all four records. Instructor refined summary to
“lossy derived representation”: it may contain facts, plans or advice, but none
of those claims acquire Checkpoint, Approval or verified-outcome authority.

### 14. Authority unavailable

Student: “不可以，进入wait”

Review: Correct blocking decision. Instructor distinguished a request-level
WAIT_FOR_AUTHORITY result from overwriting an existing durable Job state. An
unknown prior operation and HELD reservation cannot be converted to zero effect.

### 15. Omitted versus absent

Student: “应该是工具找到了1000条，但是目前本页展示的为0条，但是1000条可能在之后的页”

Review: Correct core distinction. Instructor refined that a later page exists
only when a real controlled cursor says so; otherwise the omitted items may be
available through a protected original-result reference or may be unavailable.

### 16. Bad context-policy affected set

Student listed: “job、attempt、step、state version、checkpoint version、lease、
fence、idempotency key、operation_id、event id、correlation_id、provider request ID、
dispatch marker”.

Review: This was a strong execution-identity chain, but it answered the affected-set
inventory rather than the requested immediate containment actions. Instructor supplied
the containment decision: quarantine the faulty policy version; stop accepting new
assembly and summary-publication work under it; invalidate unpublished candidates and
block their dispatch; stop not-yet-called affected steps; and isolate already-dispatched
Attempts for reconciliation without deleting their evidence. Instructor also added
tenant/user/session, context manifest, summary revision/source span/fingerprint,
Prompt/Tool/Artifact/Approval bindings, Reservation and Outbox to the affected-set
inventory. Time correlation only finds candidates; recorded provenance determines
membership in the affected set.

### 17. A1/A2/A3 rollback classification

Student correctly classified confirmed-not-dispatched A1 for release and a new
identity/reservation if later reauthorized; verified A2 for usage settlement and
remainder release; unknown A3 for PENDING_RECONCILIATION, original Provider request
lookup and HELD; and erroneous verified A2 for a separate compensation lifecycle.

Review: Instructor refined that A1 releases reserved capacity after proving zero
use, a new Attempt requires current authorization, business effect and usage are
separate A2 evidence, and compensation needs its own applicable approval.

### 18. Incident closure

Student: “不足以关闭事故，因为这不能证明之前受印象的job已经修复”

Review: Correct conclusion (“受影响的 Job”). Stable policy plus passing local
tests proves only the repaired new path. Closure also requires a complete affected
set; per-Attempt result/cost/reservation classification; exposure assessment;
verified compensation where needed; resolution or ownership/deadlines for unknowns;
continuous audit; and controlled-rollout stop evidence.

### 19. Expired/revoked result reference

Student: “应用应该拒绝，不能，因为这是权限与起源实效的问题，重试只会被再次拒绝”

Review: Correct refusal and no-replay decision (“来源失效”). Instructor added
that permission failure is only one risk: replaying a side-effecting origin may
repeat publication or cost, and an unavailable reference does not prove that
the original operation failed. Read authorization, source version and reference
availability are rechecked independently.

### 20. Structural checks versus summary semantics

Student: “不能”

Review: Correct conclusion. Instructor supplied the limitation: source/field/
reference/authorization markers are mechanically checkable, but cannot prove
that natural language is complete or faithful.

### 21. Fake summarizer evidence

Student: “能证明调用逻辑控制可以通过，但是不能证明真实LLM的摘要质量”

Review: Correct evidence boundary. The Fake can prove deterministic application
control behavior for its cases; it cannot prove general semantic fidelity,
production safety or real summarizer behavior.

### 22. Untrusted content and context manifest

Student answered “不能” when asked whether an external document can promote
itself to application instructions. Review: correct authority refusal; instructor
supplied the missing classification as sourced untrusted external data.

Student on manifest authority: “还未经过验证只能算作候选”. Review: correct
execution boundary. Instructor refined that a manifest may itself be a committed
trace record, but assembly success means only that input is prepared; it never
grants Approval or business execution.

### 23. Context capacity versus Job reservation

Student: “不能，Context budget 表示provider的一次调用的预算容量包括输入+输出等。
Job 的 token/cost reservation 表示分配的单个业务预算”

Review: Correct. Instructor refined context budget as the request-capacity gate
against both application and Provider limits, while reservation is the Job's
accounting/quota allocation to an Attempt. Both must independently pass.

## First executable increment

`src/context_memory.py` now models permission/scope/freshness-aware memory
selection, fake token estimation with the existing Day81 `ContextBudget`, a
structured bounded view of an already-validated Tool result, and conditional
summary publication by source span and summary revision. It has no business
state write path. `tests/test_day84_context_memory.py` provides deterministic
local checks.

Validation update (Python 3.11.5, EXECUTED_LOCAL_RUNTIME):

- `PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 -m py_compile
  src/context_memory.py tests/test_day84_context_memory.py` — exit 0.
- The first test command used `python3.11 -m unittest
  tests/test_day84_context_memory.py -v` and exited 1 before test execution:
  `tests` is not a Python package, so the loader raised `ModuleNotFoundError`.
  No expected facts or implementation were changed.
- During a later concise rerun, bare system `python3` selected Python 3.9 and
  failed during import because `PYTHONPATH=src` was absent and existing repository
  annotations require a newer interpreter. This is retained as an environment/command
  failure; no test executed and no expected fact changed.
- Correct repository-style Day84 command with Python 3.11.5 — 33 tests passed.
- Cumulative deterministic regression — 411 tests passed (378 prior + 33 Day84).
- Day83 version-1 seed regression — 26/26 passed.
- Day84 version-1 seed — first run 15/16 because the runner classified an empty
  truncated view by the general warning branch. The runner branch order was fixed;
  expected facts were unchanged; the rerun passed 16/16.
- The deterministic runnable scenario exited 0 and recorded zero Provider and
  external-tool calls. It covers permission-scoped memory, context omission manifest,
  partial Tool view, misleading-summary/current-authority recheck, failed conditional
  summary publication, revoked result-reference refusal and evidence boundaries.
- These results prove deterministic in-process structure and control invariants only.
  Real summarization quality, Python 3.12, databases, storage, queue/relay/worker,
  Provider, external tools and production remain NOT RUN.

## English interview

### Beginner

Student: “Conversation memory consists of incomplete, unverified memories,
whereas durable business state represents verified, authoritative facts.”

Review: The authority boundary is correct. Instructor refined the first clause:
conversation memory is not necessarily incomplete or unverified. It can include an
authorized explicit preference or a reference to a validated result, but it remains
context input and cannot grant approval or authorize a business transition. Durable
business state is the authoritative, versioned and auditable source used to decide
business transitions.

### English interview — Intermediate

Question: “After conversation compaction, how should an agent safely resume a
Job that may require human approval?”

Student: “Use a context manifest”.

Review: Partially correct. A context manifest records included and omitted inputs,
source versions and truncation, but it does not prove that approval remains valid.
The agent must use durable identifiers to reload the current Job checkpoint,
approval record, permissions, lease/fence, reservation and external-operation
status, and then recompute the control decision from current authoritative facts.

### Advanced

Question: “A provider request may have executed, but its response was lost. After
rehydration, the summary says it failed. What should the system do, and why?”

Student: “Enter pending_reconciliation”.

Review: Correct. The system must preserve the original Provider request ID and
execution evidence, keep the reservation HELD, query or reconcile the original
request, and prevent blind replay. A lost response means outcome unknown; an
unverified summary cannot convert it to confirmed failure.

### Pro

Question: “A structurally valid summary says an operation was approved, but the
current approval store is unavailable. May the system dispatch the operation?
Explain the trust boundary.”

Student: “This operation cannot be scheduled; it must wait until the approval
function is fully operational.”

Review: Correct refusal. Instructor refined `scheduled` to the narrower action
`dispatched`: the system remains in WAIT until it can read and validate the current
approval record and its Job/Attempt, action, Artifact, Prompt, Tool and expiry
bindings from the authoritative store. Service availability alone is insufficient.
A structurally valid summary remains derived candidate context and grants no
execution authority.

## Instructor-authored final synthesis

The student asked the instructor to provide the final synthesis. This section is
therefore teaching material and must not be presented as an independently produced
student answer. Guided classroom completion is supported; independent final
synthesis is NOT ASSESSED.

The safe flow begins before a model call. Context assembly selects only sources in
the current tenant/user/session/Job scope, checks current access, source version,
expiry and revocation, assigns provenance/role/trust, and accounts for instructions,
messages, Tool schemas/results, format overhead, reserved output and safety margin.
The resulting context manifest records selected and omitted sources, versions,
policy and estimated capacity. It grants no business execution authority.

An oversized Tool result is validated against its Tool contract before projection.
The model receives a structured bounded view that preserves operation/result
identity, status, completeness, warnings, total count, shown count, truncation,
pagination cursor and a protected source reference. An empty excerpt can coexist
with a nonzero total; omitted data must remain unknown rather than being rewritten
as absent. Re-reading a reference requires current scope, permission, source-version,
availability and expiry checks, and must not replay the original side effect.

Compaction creates a lossy candidate summary over an explicit source span. A valid
candidate records scope, event range/fingerprint, summary revision, policy version
and summarizer identity. Required references and next-step authority markers can be
checked structurally, but Fake cases cannot prove general natural-language fidelity.
Publication uses source-head/fingerprint checks, revision CAS and an idempotent
candidate identity. A concurrent new event makes the candidate stale; a failure
before commit leaves the prior summary current.

Rehydration treats the summary as navigation and continuity only. Before a protected
action, the application reloads the current Job, Attempt, Step, state/checkpoint
versions, Approval, Artifact/Prompt binding, lease, fence, Reservation, Outbox/
dispatch evidence and original Provider operation identity from authoritative stores.
It then reruns the existing guarded decision. If authority is unavailable, it waits;
it does not promote the summary to a fallback approval database. Terminal state is
not reopened by a later memory update.

Permission or source invalidation removes content before model/summarizer input and
again blocks later reference reads. A business-state change makes an older projection
or summary stale and requires a current read. An unknown external result enters
PENDING_RECONCILIATION, retains the original Provider request ID and evidence, keeps
the Reservation HELD and forbids blind replay. Confirmed no-dispatch attempts can
release unused reservation; verified results settle verified usage and release the
remainder; an incorrect external effect follows a separate compensation lifecycle.

Context capacity and Job accounting are independent gates. Context budget limits one
Provider request's input plus reserved output and margin. A Job token/cost Reservation
allocates business quota to an Attempt and is settled from verified usage. Truncation
or compaction can reduce request capacity, but cannot release a Reservation, reset a
Job limit, approve an action or prove an external outcome.

For a faulty context policy, quarantine the version, stop accepting new work under it,
invalidate unpublished candidates, stop affected not-yet-called steps, block candidate
dispatch and isolate already-dispatched Attempts for evidence-based reconciliation.
Incident closure additionally requires a complete affected set, per-Attempt outcome
and accounting, exposure assessment, verified compensation where needed, resolution
or owned deadlines for unknowns, audit continuity and controlled-rollout evidence.
Passing tests on the repaired path alone cannot prove earlier affected Jobs are fixed.
