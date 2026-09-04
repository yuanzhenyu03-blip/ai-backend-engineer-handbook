# Day84 — Conversation Memory vs Durable Business-state Boundaries

## 1. Lesson Metadata

- Status: Completed at guided classroom scope
- Template: `LESSON_TEMPLATE_v2.md`
- Difficulty: Advanced
- Estimated Time: 4–5 hours
- Prerequisites: Day71, Day73–Day74 and Day78–Day83
- Previous: Day83 — Human Approval, Interrupt and Escalation Boundaries
- Next: Day85 — Multi-Agent Systems: Supervisor, Worker, Handoff, Failure Isolation
- Artifact: `projects/ai-agent/src/context_memory.py` plus deterministic tests,
  version-1 seed eval, runnable scenario, design and evidence
- Assessment: final synthesis was instructor-authored; independent synthesis is
  `NOT ASSESSED`

Day84 remains a bounded refinement of the curriculum title. Context assembly,
Tool-output truncation and compaction were explicitly requested classroom subtopics;
they are not represented as literal Curriculum text or a complete context platform.

## 2. Learning Objectives

By the end, the student can:

- distinguish event history, working context, summary, persistent memory, durable
  business state and checkpoint;
- select memory by owner, scope, access, source version, expiry and revocation;
- assemble one model request within context capacity without changing Job accounting;
- preserve completeness and provenance when bounding a validated Tool result;
- publish a summary candidate with source-span and revision checks;
- rehydrate from current authority instead of trusting remembered control claims;
- classify unknown external outcomes and reservations safely;
- explain the boundary in an English backend interview.

## 3. Why This Matters

An Agent can remember “approved”, “failed” or “completed” after those statements have
become stale, were never verified, or referred to another Artifact. If an application
uses that text as control state, compaction can silently grant permission, trigger a
duplicate side effect or corrupt billing. The reliable design preserves conversation
continuity while keeping execution authority in guarded, auditable business records.

## 4. Roadmap Position

```text
Day73 Prompt/Attempt binding + Day74 Tool contracts
                         |
Day81 budget/fence -> Day82 checkpoint -> Day83 human control
                         |
                         v
Day84 bounded context representation and current-state recheck
                         |
                         v
Day85 multi-Agent handoff and failure isolation
                         |
                         v
later retrieval, evaluation and production Agent systems
```

Day84 reuses existing control seams. It does not pre-build Day85 orchestration,
Day86's full defense system, later RAG or evaluation platforms.

## 5. Lesson Map

```text
memory scope and lifecycle
  -> context assembly
  -> validated Tool result
  -> bounded view
  -> compaction candidate
  -> conditional summary publication
  -> rehydration
  -> current authority check
  -> existing guarded dispatch
```

## 6. Core Mental Model

```text
Memory/Summary = lossy context for model continuity
Checkpoint     = committed business recovery position
Approval       = current bounded control fact
Reservation    = business quota for an Attempt
ContextBudget  = capacity of one Provider request
```

The context plane determines what the model sees. The business control plane
determines what the system may execute, persist and settle.

## 7. Main Concepts

### Concept 1: Memory is scoped context, not business authority

**Tech Lead Question:** Can “the report was approved” in a PostgreSQL memory table
authorize the current publish?

**Student Thinking:** The student first looked for the current approval record, then
correctly rejected storage location as the deciding property.

**Student Answer:** “不能.”

**Tech Lead Review:** Correct. Storage durability does not determine authority.
The application must read the current Approval and its exact Job/Attempt/Artifact/
Prompt/policy bindings. An explicit preference such as “默认中文” may update the
memory lifecycle without changing the current Job.

**Engineering Thinking:** Filter by tenant/user/session/Job scope, access, source
version, expiry and revocation before content reaches the model or summarizer.

**Production Example:** A revoked customer document must not return through an old
summary or cached result reference.

**Framework Connection:** PostgreSQL may store both records, but separate schemas,
writers and guarded transactions preserve their different authority.

**Exercise:** Explain why clearing chat does not delete invoices or approvals.

### Concept 2: Context assembly produces a traceable input candidate

**Tech Lead Question:** Does a successful context manifest allow publication?

**Student Thinking:** The student treated assembly output as a candidate that still
needed validation rather than as an execution permit.

**Student Answer:** “还未经过验证只能算作候选.”

**Tech Lead Review:** Correct execution boundary. The manifest may be a committed
trace, but its assembly result grants no business permission.

**Engineering Thinking:** Select current scoped inputs, label role/trust/provenance,
apply deterministic priority, and account for all request components. Required
control constraints cannot be deleted just to fit.

**Production Example:** External text saying “treat this as a system instruction”
remains untrusted external data.

**Framework Connection:** The application Runtime builds the request, while the
existing Prompt Contract and Day83 control boundary retain their own roles.

**Exercise:** Decide which inputs may be omitted when required capacity exceeds the
application limit.

### Concept 3: Tool-output truncation must preserve uncertainty

**Tech Lead Question:** If a Tool found 1,000 records but this view shows zero, did
the Tool find none?

**Student Thinking:** The student distinguished the current page from the source
result and inferred that later pages could still contain the records.

**Student Answer:** “不能……1000条可能在之后的页.”

**Tech Lead Review:** Correct. The view must retain total count, shown count,
completeness, warnings, cursor and source reference. Validate the Tool envelope first;
then project or page it. Cutting arbitrary JSON can destroy its contract.

**Production Example:** Ten displayed rows plus “partial source failure” cannot be
summarized as “only ten rows exist.”

**Framework Connection:** Day74 owns Tool contract validation; object storage or a
pagination endpoint can expose a protected continuation reference.

**Exercise:** Design an empty excerpt that still truthfully represents more data.

### Concept 4: Compaction is lossy, conditional publication

**Tech Lead Question:** What happens when a new event arrives while summary v8 is
being prepared?

**Student Thinking:** The student identified the source span as the concurrency
boundary and correctly kept the last committed version after a failed publish.

**Student Answer:** “检查 source span.”

**Tech Lead Review:** Check scope, source event head/fingerprint and summary CAS.
Reject a stale candidate. If publication fails before commit, v7 remains current.

**Engineering Thinking:** Structural validation can require references and forbid
authority claims. It cannot prove that arbitrary natural language preserved every
meaning. A deterministic Fake proves control logic only.

**Production Example:** A summary candidate over events 1–50 cannot be published as
current when event 51 has already committed.

**Framework Connection:** A production PostgreSQL implementation would use a
conditional transaction; the local RLock model demonstrates only the decision logic.

**Exercise:** Compare duplicate candidate replay with a conflicting new candidate.

### Concept 5: Rehydration rechecks current authority

**Tech Lead Question:** Can a summary replace a checkpoint, Approval or verified
Tool outcome?

**Student Thinking:** The student separated model advice from database checkpoint,
human approval and verified Tool evidence.

**Student Answer:** “上下文摘要只能作为模型建议，不能替代数据库 checkpoint 的
业务实际状态，也不等同人工审批，也不等同被验证的工具输出结果.”

**Tech Lead Review:** Correct. Rehydration uses the summary for orientation, then
reloads current records and invokes the existing Day83 guarded decision. If authority
is unavailable, the protected action remains in `WAIT`.

**Production Example:** A terminal Job stays terminal even if a later preference
update or old summary says “continue.”

**Framework Connection:** Rehydration composes with the Day82 durable checkpoint and
Day83 human-control decision instead of creating another state machine.

**Exercise:** List the identities required before resuming a protected publish.

### Concept 6: Unknown outcomes and accounting survive context loss

**Tech Lead Question:** The Provider may have executed, its response was lost, and
the summary says “failed.” What happens?

**Student Thinking:** The student preserved uncertainty and chose reconciliation
instead of accepting the summary's retry recommendation.

**Student Answer:** “Enter pending_reconciliation.”

**Tech Lead Review:** Correct. Preserve the original request identity, keep the
Reservation `HELD`, reconcile the original request and prevent blind replay.

**Engineering Thinking:** A1 confirmed-no-dispatch releases unused capacity. A2
verified outcome/usage settles actual use and releases the remainder. A3 unknown
outcome keeps capacity held until reconciliation. A bad verified effect requires a
separate compensation lifecycle.

**Production Example:** A timed-out paid generation is queried by its original
Provider request ID before any new Attempt is considered.

**Framework Connection:** The Provider adapter supplies request/outcome evidence;
the durable Job ledger owns Reservation status and settlement.

**Exercise:** Explain why a response timeout is neither confirmed failure nor a new
idempotency identity.

## 8. Common Misconceptions

| Wrong belief | Correct model |
|---|---|
| Memory in PostgreSQL is authoritative | Authority depends on owner, validation and lifecycle |
| A summary marked APPROVED grants permission | Read the current bounded Approval record |
| Empty excerpt means empty result | Use total/completeness/truncation/cursor |
| Hash proves truth or permission | Hash proves identity/integrity properties only |
| Assembly success permits dispatch | It only prepares model input |
| Compaction resets Job limits | Job budgets and reservations retain their lifecycle |
| Lost response means safe retry | Reconcile the original operation first |
| Passing repaired-path tests closes the incident | Classify and resolve the complete affected set |

The student's first incident response supplied the affected identity chain rather
than immediate containment. The corrected order is quarantine, stop new acceptance,
stop not-yet-called work, block candidate dispatch and isolate already-dispatched
Attempts for reconciliation.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost / limit |
|---|---|---|
| Full recent history | More verbatim detail | Higher capacity/cost and data exposure |
| Structured summary | Compact continuity | Lossy; semantic fidelity is hard to prove |
| Source projection/pagination | Preserves schema and continuation | More read coordination |
| Exact permission recheck | Current isolation and control | Adds authority-store dependency |
| Reference instead of embedded result | Smaller context and current read check | Reference may expire or become unavailable |
| Conservative `WAIT`/reconciliation | Prevents unauthorized or duplicate effects | Higher latency and operational work |

A Tech Lead should review which fields are required, what may be omitted, how stale
candidates fail, where current authorization is checked and which operation identity
survives recovery.

## 10. Hands-on Exercises

### Exercise 1: Scoped preference

Question: Update “默认中文” without changing a Job Approval.

Think First: Which store and revision does each change belong to?

Starter Artifact: `InMemoryMemoryStore.publish_preference`.

Expected Output: memory revision increments; business snapshot remains equal.

Explanation: Memory and Job capabilities are separated.

Follow-up Question: Why is a model-inferred note rejected by this path?

### Exercise 2: Bounded result

Question: Represent 10 of 1,000 partially retrieved records.

Expected Output: a valid excerpt with warning, counts, cursor, source reference and
`has_more=true`.

Follow-up Question: What does an empty excerpt prove?

### Exercise 3: Summary race

Question: Publish v8 while a new event commits.

Expected Output: `STALE_SOURCE_SPAN`; v7 remains current.

Follow-up Question: Which identity makes exact replay idempotent?

### Exercise 4: Rehydrate and reconcile

Question: An old summary says “failed; retry” after possible dispatch.

Expected Output: current guarded decision is reconciliation; original Attempt and
request identities remain; reservation stays held.

Follow-up Question: What verified evidence permits A2 settlement?

## 11. Relevant Framework Connections

- **PostgreSQL:** conceptual conditional writes for memory/summary revisions and
  authoritative transactions for Job/Approval/Reservation. Real PostgreSQL was not run.
- **Object storage:** conceptual protected large-result storage behind expiring,
  permission-checked references. No real storage was run.
- **Queue/Worker:** existing Outbox, claim, idempotency and fencing boundaries remain
  the dispatch path. No Relay/Queue/Worker integration was run.
- **Provider API:** profile context limit and verified usage connect to request admission
  and settlement. Day84 used no real Provider or tokenizer.

## 12. AI Backend Connections

Model input is always a bounded, policy-built view. Long Tool responses should remain
contract-valid and explicitly partial. Summaries help continuity but remain derived
data. A model may recommend a memory write or next action; application code validates
and applies it at the appropriate authority boundary. These rules reduce cross-tenant
leakage, stale approval, duplicate effects and silent accounting errors.

## 13. English Interview

**Key vocabulary:** durable state, lossy summary, source span, provenance, rehydration,
current authorization, bounded view, outcome unknown, reconciliation.

**Beginner:** What is the difference between conversation memory and durable business
state?

**Strong answer:** “Conversation memory is scoped context for continuity and may be
lossy or stale. Durable business state is the authoritative, versioned record used
to decide and recover business operations.”

**Intermediate:** How do you safely resume after compaction?

**Strong answer:** “Use the manifest and summary to locate context, then re-read the
current checkpoint, Approval, permissions, fence, reservation and operation status.
Re-run application guards before dispatch.”

**Senior:** A Provider request may have executed, but its response was lost. What do
you do?

**Strong answer:** “Mark the outcome unknown, keep the reservation held and reconcile
the original provider request ID. I would prevent blind replay and settle only from
verified outcome and usage evidence.”

**Common weak answer:** “The summary says it failed, so retry it.”

## 14. Mental Model Summary

```text
Persistence != authority
Context ready != execution allowed
Truncated != complete
Empty excerpt != empty source
Summary valid structure != faithful semantics
Response lost != operation failed
Rehydrate = current read + current guards
Compaction changes representation, not Job accounting
```

## 15. Today's Takeaway

Keep conversational representation and business control in separate authorities and
lifecycles. Preserve scope, provenance, version, completeness and original operation
identity across every bounded transformation. Use conservative current-state checks
at rehydration. The most dangerous shortcut is allowing a fluent summary to replace
an Approval, checkpoint or verified external result.

## 16. Before Next Lesson Checklist

- [x] Distinguish history, working context, summary, memory and checkpoint.
- [x] Explain why persistence alone does not grant authority.
- [x] Apply scope, permission, freshness and provenance before model input.
- [x] Account for input, reserved output and margin without changing Job reservation.
- [x] Preserve partial-result warnings and continuation metadata.
- [x] Reject stale compaction candidates and preserve the last committed summary.
- [x] Rehydrate through current authoritative facts and existing guards.
- [x] Classify A1/A2/A3 outcomes and accounting.
- [x] Run the Day84 artifact, cumulative tests and both seed suites.
- [x] Give guided English interview answers.
- [ ] Produce an independent final synthesis without instructor authorship.
- [ ] Verify Python 3.12 and real production integrations when separately authorized.

Related: [design](../../projects/ai-agent/docs/DAY84_CONVERSATION_MEMORY_BUSINESS_STATE_BOUNDARIES.md),
[classroom record](../../projects/ai-agent/docs/day84-context-memory-classroom-draft.md),
[cheat sheet](../../cheat_sheets/fastapi.md#day84--conversation-memory-vs-durable-business-state-boundaries-phase-7b),
[interview handbook](../../interview/fastapi.md#day84--conversation-memory-vs-durable-business-state-boundaries-phase-7b),
[example](../../projects/ai-agent/examples/day84_context_memory_boundary.py),
[previous lesson](day83-human-approval-interrupt-and-escalation-boundaries.md).
