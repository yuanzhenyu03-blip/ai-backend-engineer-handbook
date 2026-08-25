# Day74 — Structured Output, JSON Schema and Function/Tool Calling

## 1. Lesson Metadata

```text
Status:          ✅ Completed (classroom scope) — CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME
Version:         v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:      Advanced, taught beginner-first
Estimated Time:  5-6 hours
Prerequisites:   Day73, Day72, Day71, Day53, Day54; reuses Day44 contract thinking
Previous Lesson: Day73 — Prompt Contracts, Prompt Versioning and Compatibility
Next Lesson:     Day75 — Streaming Responses, Caching and Batching
Artifact:        projects/ai-agent/src/output_tool_contracts.py + tests/test_output_tool_contracts.py
```

Evidence honesty:

- `CONCEPTUAL`: completed through one evolving `publish_report` scenario, checkpoints, a failure/rollback
  exercise and three English interview levels.
- `STATIC`: PASS — `py_compile` on four modules/three test files and `mypy` on the same seven files.
- `EXECUTED_LOCAL_RUNTIME`: PASS — 34 deterministic Day74 tests; 131 total with Day72/Day73, Python 3.11.5.
- Python 3.12: NOT RUN — no `python3.12` executable was available in the update environment.
- `INTEGRATION_RUNTIME`: NOT RUN — no real Provider/SDK/HTTP/database/queue/external tool/reconciliation.
- `PRODUCTION`: NOT RUN — no credentials, customer data, sensitive prompts, paid calls or production traffic.

The schema code is a clearly bounded teaching subset. It is not evidence of full JSON Schema compliance or a
Provider's native Structured Output implementation. In-memory stores, locks and counters are not durable or
exactly-once proof.

## 2. Learning Objectives

After this lesson, the student can:

- **Explain** why Provider `SUCCESS`, valid JSON and Schema validity are three different claims and none grants
  permission to execute a side effect.
- **Compare** ordinary text, JSON text, a parsed Python `dict`, JSON Mode, Structured Output and an
  application-owned JSON Schema contract.
- **Implement** strict recursive validation for the taught schema subset and state its limitations honestly.
- **Design** Tool Definition, Registry, Authorization, Admission, Executor, Outcome Verification and Durable
  Store as separate owners.
- **Defend** why model-provided `tenant_id`, tool name, version and arguments remain untrusted.
- **Apply** idempotency, atomic claim, version binding, guarded completion and reconciliation to real side
  effects.
- **Diagnose** parse, schema, semantic, authorization, admission, execution and unknown-outcome failures
  without collapsing them into one retryable error.
- **Answer in English** at beginner, intermediate and senior levels.

## 3. Why This Matters

A model returns this candidate:

```json
{
  "tool_name": "publish_report",
  "arguments": {
    "tenant_id": "tenant-b",
    "report_id": "report-7",
    "force": true
  }
}
```

It may be valid JSON. A Provider may report success. The tool name may even exist. None of those facts answers
the questions that matter in production: Is this the expected version? Is `force` allowed? Is the report a
draft? Does it belong to the authenticated tenant? Did an earlier timeout already publish it? May this one
candidate cross the side-effect boundary?

If an application sends model arguments directly to business services, the model becomes an accidental
authority. Prompt injection can turn into parameter injection; a tenant identifier can become a confused-
deputy bug; timeout retry can duplicate a real effect; an HTTP 200 can incorrectly mark a Job successful.
Day74 places explicit application-owned contracts between probabilistic model output and deterministic backend
side effects.

## 4. Roadmap Position

```text
Day72 — replaceable Provider surface and versioned capabilities
        |
        v
Day73 — immutable Prompt Contract + per-Attempt input binding
        |
        v
Day74 — untrusted output -> validated/admitted tool -> verified completion
        |
        v
Day75 — streaming/caching/batching must preserve complete validated output boundaries
        |
        v
Day76 — routing/fallback must preserve schema, version, identity and authorization
```

Day73 answers “what exact input behavior did this Attempt use?” Day74 answers “what may the application trust
and execute from the resulting candidate?” Day75 and Day76 can optimize transport and selection only after
these contracts exist; they cannot trade them away for latency or availability.

Direct knowledge reused:

- Day44: typed input/output contract thinking;
- Day53: Provider success is not a trusted business result;
- Day54: Attempt identity, timeout unknown, late results and reconciliation;
- Day72: Provider-specific translation stays behind an Adapter;
- Day73: current defaults never reinterpret historical Attempt bindings.

## 5. Lesson Map

```text
Candidate text
-> JSON value
-> strict shape
-> business meaning
-> trusted authority
-> exact tool/version
-> one admitted command
-> idempotent execution
-> verified outcome
-> guarded durable truth
```

## 6. Core Mental Model

```text
Provider Response
  -> Parse
  -> Schema Validation
  -> Tool Registry
  -> Application Authorization
  -> Semantic Validation
  -> Tool Admission
  -> AdmittedToolCall
  -> Tool Execution
  -> Outcome Verification
  -> Guarded Completion / Reconciliation
```

Every arrow is a trust boundary. A later boundary never becomes unnecessary because an earlier one passed.
The model proposes; the application validates, authorizes, admits, executes and records.

## 7. Main Concepts

### Concept 1: Text, JSON and parsed values

**Tech Lead Question:** If `json.loads` succeeds, what do we have?

**Student Thinking:** The student separated parsing from trust and answered: `仍然不可信的 Python dict`.

**Student Answer:** Correct.

**Tech Lead Review:** Ordinary text is a sequence of characters. JSON text uses a data grammar with objects,
arrays, strings, numbers, booleans and `null`. `json.loads` parses it into Python values such as `dict`, `list`,
`str`, numbers, `bool` and `None`. Parsing answers only “can we read this format?” It does not check required
fields, business meaning or permission.

**Engineering Thinking:** Keep malformed transport/data-format failures separate from a well-formed but invalid
contract. Repairing malformed output and rejecting an unauthorized action are not the same recovery policy.

**Production Example:** `{"report_id": 7}` parses successfully, but a contract requiring a string rejects it
as `SCHEMA_INVALID`.

**Framework Connection:** A Provider Adapter may extract JSON text, but application validation remains outside
Provider-specific translation.

**Exercise:** Classify `{"report_id":` and `{"report_id": 7}`. The first is parse failure; the second parses
and then fails Schema.

### Concept 2: JSON Mode, Structured Output and JSON Schema

**Tech Lead Question:** Will an undeclared `force` field automatically fail any object Schema?

**Student Thinking:** The first answer was `会`.

**Student Answer:** Reasonable but incomplete. After the closed-object rule was introduced, the student correctly
classified it as `schema-invalid`.

**Tech Lead Review:** JSON Mode aims to produce syntactically valid JSON. Structured Output is a Provider
capability intended to constrain output to a requested structure. JSON Schema is a declarative structural
contract. Provider support and guarantees vary and are versioned capability facts; application validation is
still required. An object must explicitly use `additionalProperties: false` when unknown fields must fail
closed.

A minimal progression:

```json
{"report_id": "report-7"}
```

```json
{
  "type": "object",
  "properties": {
    "report_id": {"type": "string", "minLength": 1}
  },
  "required": ["report_id"],
  "additionalProperties": false
}
```

**Engineering Thinking:** More constraints reduce ambiguous candidates but increase versioning and compatibility
work. Schema cannot safely express every cross-field business invariant, tenant permission or external state.

**Production Example:** `published=true` together with `error="permission denied"` may pass individual field
types but is semantically contradictory and must be rejected after Schema.

**Framework Connection:** The repository Artifact supports only `type`, `properties`, `required`, `enum`,
length/range keywords, `items` and `additionalProperties`. Unsupported keywords fail loudly; full JSON Schema
compliance is NOT claimed.

**Exercise:** Why does `minLength: 1` reject `""`? Student: `违反了字符串至少包含一个字符，不能是空字符串`.

### Concept 3: Tool Definition versus candidate tool call

**Tech Lead Question:** What happens when the model proposes an unknown tool?

**Student Answer:** `将其分类为 unknown tool 并拒绝`.

**Tech Lead Review:** A Tool Definition declares an application-approved exact name, version and argument
Schema. A model-generated tool call is only a candidate request. The application must resolve the exact
identity through a server-owned Registry. A known name with an unsupported version is different from an
unknown name; a disabled version is different again. All fail closed.

```text
Tool Definition = declaration
Candidate call  = model proposal
Tool Admission  = per-invocation permission decision
Tool Execution  = real side effect
```

**Engineering Thinking:** Function Calling/Tool Calling is a structured proposal channel, not remote-code
execution authority. Model-selected names and arguments may be hallucinated or injected.

**Production Example:** `publish_report@v2` must not silently fall back to v1 because the versions may have
different arguments or semantic guarantees.

**Framework Connection:** The Provider Adapter translates Provider wire fields; the Tool Registry owns the
application identity/version allowlist.

**Exercise:** Classify an existing `publish_report` with requested version `v9`: incompatible tool version,
not unknown tool and not Provider transport failure.

### Concept 4: Authorization, semantics and Tool Admission

**Tech Lead Question:** Can model argument `tenant_id="tenant-b"` authorize access when the server session is
`tenant-a`?

**Student Answer:** `不可以`; authorization belongs to `Application Authorization`.

**Tech Lead Review:** Schema checks shape. Semantic Validation checks whether the combination makes business
sense. Authorization checks whether the trusted identity may perform the action. Tool Admission combines the
validated decisions for one candidate and creates a frozen, server-normalized `AdmittedToolCall`. The Executor
accepts only that type.

The Artifact authorizes before tenant-scoped state lookup. This ordering prevents unauthorized callers from
using detailed semantic failures to discover another tenant's resources.

**Engineering Thinking:** This controls confused-deputy and tenant-isolation risks. Prompt rules are guidance
to the model, never a replacement for server policy.

**Production Example:** A publisher for tenant-a may publish tenant-a's draft `report-7`. A viewer, tenant-b
argument, missing report or already-published report is rejected before execution. Missing and non-publishable
use one safe reason to avoid an existence oracle.

**Framework Connection:** In a future FastAPI integration, authentication dependencies would create trusted
context; Pydantic/request bodies and model arguments would remain untrusted inputs. No FastAPI runtime was run
on Day74.

**Exercise:** The student correctly answered that an already-published report belongs to Semantic Validation,
while viewer permission belongs to Application Authorization.

### Concept 5: Idempotent execution and the side-effect boundary

**Tech Lead Question:** Is `if key not in operations: execute()` enough under concurrency?

**Student Answer:** `需要原子的唯一占位/claim` and “only one logical publish may take effect.”

**Tech Lead Review:** An idempotency key identifies one logical operation. The claim must be atomic; otherwise
two workers can both observe absence and execute. The in-memory Executor uses a lock and returns the original
operation ID for duplicates. A final Registry lifecycle guard catches a version disabled after Admission but
before execution.

**Engineering Thinking:** The local model proves only thread-level deterministic behavior. Production requires
a durable unique constraint/conditional update, ownership or fencing rules, and external idempotency where
supported. A database transaction cannot undo an HTTP request already accepted by another service.

**Production Example:** Eight concurrent calls with one idempotency key produce one simulated effect and seven
`DUPLICATE_SUPPRESSED` results. This is not an external exactly-once guarantee.

**Framework Connection:** PostgreSQL `UPDATE ... WHERE ... RETURNING` or a unique claim is a future production
implementation direction; it was discussed but NOT RUN.

**Exercise:** If Admission passed and v1 is then disabled before execution, the Executor returns
`REJECTED_DISABLED` with zero simulated effects.

### Concept 6: Outcome Verification, completion and reconciliation

**Tech Lead Question:** Should the verifier write `SUCCEEDED` immediately after the tool returns?

**Student Answer:** `只返回 VERIFIED 候选，再由独立的 guarded completion 使用 Durable Store 决定是否提交`.

**Tech Lead Review:** A tool return is another untrusted candidate. Verify its nested Schema, cross-field
semantics and operation/report/version identity. Then the Durable Store checks current job, Attempt, tool call
and terminal state. Only a current verified result commits `SUCCEEDED`.

If dispatch times out, outcome is unknown. `TIMEOUT_UNKNOWN` moves the job to `PENDING_RECONCILIATION`; blind
retry may duplicate a completed external effect. A fully matching late result may complete a still-current
reconciling job. Cancelled, superseded, stale or terminal results have zero completion effect.

**Engineering Thinking:** A function return or HTTP 200 is evidence, not durable business truth. Completion is
a guarded state transition owned by durable application state.

**Production Example:** Dispatch markers and Provider request IDs correlate A4 but do not prove publication.
Reconciliation also needs operation/idempotency state and authoritative external report/version/audit evidence.

**Framework Connection:** Day54's Attempt/late-result model is reused. Real PostgreSQL and external status
lookup were NOT RUN.

**Exercise:** Student: a fully matching late result is a `valid late result` and may pass guarded completion;
a cancelled result cannot overwrite state.

### Concept 7: Failure containment and recovery verbs

**Tech Lead Question:** A bad `publish_report@v2` allowed `force=true`. Should every affected Attempt be retried?

**Student Thinking:** The first rollback wording suggested changing an existing version binding. It was
corrected to stop new v2 work without rewriting history.

**Student Answer:** For A3: `根据副作用是否可逆执行受控的 repair/compensation，并保留原始执行和事故证据`.

**Tech Lead Review:** Classify each Attempt from durable evidence:

| Attempt | State | Correct action |
|---|---|---|
| A1 | v2 bound, not admitted | block; optional explicit safe new Attempt |
| A2 | admitted, not executed | final kill switch rejects |
| A3 | confirmed duplicate effect | repair/compensation if reversible; preserve evidence |
| A4 | dispatched, outcome unknown | reconcile; never blind retry |
| A5 | safe v1 in flight | continue under bound v1 |

Reject refuses one candidate. Re-prompt creates a new Attempt. Disable/rollback contains future harm. Repair
corrects internal durable facts. Compensation is a new authorized/idempotent counter-operation. Reconciliation
recovers truth when outcome is unknown. None deletes historical evidence.

**Engineering Thinking:** Incident containment is not incident resolution. Closure requires every affected
Attempt to reach a known terminal or explicit recovery state and any compensation to be verified.

**Production Example:** The Registry disables v2 immediately, but A4 remains `PENDING_RECONCILIATION` until
authoritative evidence establishes whether it ran.

**Exercise:** Explain why “no operation row found” may still be insufficient after an external timeout.

## 8. Common Misconceptions

**Provider success**

❌ Provider `SUCCESS` means trusted business success.

✅ It means the request/transport reached a Provider-defined success surface; output remains a candidate.

**JSON and Schema**

❌ Parseable JSON automatically satisfies the contract.

✅ Parse, Schema and semantics answer different questions.

**Closed objects**

❌ Every Schema rejects undeclared fields.

✅ Use and test `additionalProperties: false` where strict fail-closed behavior is required.

**Authorization**

❌ A model-supplied tenant or prompt instruction is authority.

✅ Only trusted server context and application policy authorize the action.

**Tool calling**

❌ A tool call means the tool has run.

✅ It is a model proposal; Admission and Execution are separate application boundaries.

**Idempotency**

❌ A pre-execution `if` check prevents duplicates.

✅ Concurrency needs an atomic claim; external exactly-once still requires stronger evidence.

**Timeout**

❌ Timeout means failure, so retry.

✅ Timeout after dispatch may be `TIMEOUT_UNKNOWN`; reconcile before any retry decision.

**Rollback**

❌ Rollback rewrites the old Attempt to a safe version and undoes external requests.

✅ It changes future selection/admission; historical bindings and confirmed effects need separate handling.

## 9. Engineering Trade-offs

### Provider-native Structured Output versus application validation

Provider-native constraints can reduce malformed candidates and repair loops, but capability varies by Provider,
model/API version and Schema subset. Application validation is still required for portability, fail-closed
behavior, semantics and authorization.

### Strict closed Schema versus forward extensibility

Closed objects catch hallucinated/injected fields and make compatibility explicit. They also make adding a
field a versioned contract change. Open extension maps may be appropriate only when explicitly designed and
semantically isolated.

### In-memory lock versus durable claim

The lock is fast, deterministic and useful for teaching. It cannot coordinate processes or survive restart.
A durable claim adds latency and operational complexity but is required for real side effects.

### Holding a lock versus external fencing

Holding the Registry lock across the simulated effect gives a clear local ordering. Holding a process/DB lock
across external HTTP is dangerous. Production prefers short durable claims, lifecycle epochs/fencing and
external idempotency, followed by reconciliation.

### Store full payload versus minimal audit evidence

Full model/tool payloads help debugging but may contain prompts, secrets or customer data. Prefer minimal
identities, versions, hashes, reason codes and protected references with tenant authorization and finite
retention.

## 10. Hands-on Exercises

### Exercise 1: Classify candidates

**Question:** Classify malformed JSON, wrong field type, unknown `force`, viewer role and already-published
report.

**Think First:** Which question does each boundary answer?

**Starter Artifact:** `admit_tool_call` and the three schemas.

**Expected Output:** `PARSE_FAILURE`, `SCHEMA_INVALID`, `SCHEMA_INVALID`, `UNAUTHORIZED`,
`SEMANTICALLY_INVALID`.

**Explanation:** Do not collapse them into one validation/retry error.

**Follow-up Question:** Which failures could a policy-controlled new re-prompt possibly repair, and which must
be rejected without asking the model again?

### Exercise 2: Prove the local idempotency boundary

**Question:** Execute the same admitted call eight times concurrently.

**Think First:** Why must the claim and effect counter share one critical section?

**Starter Artifact:** `InMemoryToolExecutor`.

**Expected Output:** one `EXECUTED`, seven `DUPLICATE_SUPPRESSED`, one simulated effect.

**Explanation:** This is in-process evidence, not a production exactly-once guarantee.

**Follow-up Question:** Translate the claim into a PostgreSQL conditional transition and list what it still
cannot prove about an external HTTP service.

### Exercise 3: Verify then complete

**Question:** Send a correct result, a wrong report version, a superseded Attempt and a valid late result.

**Think First:** Separate verification from state mutation.

**Starter Artifact:** `verify_publish_outcome` and `InMemoryDurableStore`.

**Expected Output:** `VERIFIED` + committed, `IDENTITY_MISMATCH`, `NOOP_STALE`, and committed only for the
current `PENDING_RECONCILIATION` identity.

**Explanation:** Late is not automatically stale; identity and current durable state decide.

**Follow-up Question:** What authoritative external evidence would a real reconciliation worker need?

### Exercise 4: Contain bad v2

**Question:** Classify A1–A5 from the incident table.

**Think First:** Separate containment, known harm and unknown outcomes.

**Starter Artifact:** Registry disable, final Executor guard and Durable Store states.

**Expected Output:** block/new Attempt; rejected execution; repair/compensation; reconciliation; continue v1.

**Explanation:** Bulk retry or binding rewrite destroys correctness.

**Follow-up Question:** What evidence is required before declaring the incident resolved rather than merely
contained?

## 11. Relevant Framework Connections

### Python

Frozen dataclasses express immutable admitted commands and decisions; Enums keep failure states explicit;
`Optional` represents an operation ID absent on rejected execution; `RLock` models an in-process critical
section. Type hints and `mypy` keep ownership surfaces reviewable.

### FastAPI and Pydantic (future integration boundary)

FastAPI/Pydantic can validate HTTP input and typed application models, but authentication dependencies and
business services still own authorization/semantics. No FastAPI or Pydantic runtime was added on Day74; the
standard-library Artifact keeps the boundary provider/framework neutral.

### PostgreSQL (production direction, NOT RUN)

Conditional `UPDATE ... RETURNING`, unique operation identity and guarded completion transactions are natural
durable implementations. They do not make an external HTTP side effect transactionally rollbackable.

## 12. AI Backend Connections

- **Prompt injection:** model-visible instructions cannot grant server authority.
- **Parameter injection:** strict arguments and closed objects reject undeclared execution controls.
- **Agent tools:** candidate call and real execution remain separate even when an agent loop is automated.
- **Tenant isolation:** trusted tenant context scopes authorization and state lookup.
- **Observability:** log safe identities, versions and reason codes; keep secrets/sensitive arguments out of
  ordinary logs.
- **Cost/reliability:** Provider-native constraints may reduce repair calls, but application checks remain.
- **Future streaming/cache/routing:** partial, cached or rerouted candidates must preserve the same contracts.

## 13. English Interview

### Key Vocabulary

untrusted candidate · parse · schema validation · semantic validation · server-side authorization · Tool
Definition · Tool Admission Gate · idempotency key · atomic claim · guarded completion · unknown outcome ·
reconciliation · compensation · fencing token

### Useful Expressions

- “Schema validity proves structure, not authorization or business safety.”
- “The model proposes a tool call; the application decides whether and how to execute it.”
- “A timeout after dispatch is an unknown outcome, so a blind retry may duplicate the side effect.”

### Beginner Question

**Why is a schema-valid tool call still unsafe to execute immediately?**

Student answer:

> Due to incomplete verification, further validation—such as checking signatures and authorizations—is required.

Assessment: passed. Signatures are system-specific; universal remaining boundaries are semantics,
trusted-context authorization, exact tool/version resolution and Admission.

Strong answer:

> Schema validity only proves the candidate's structure. The application must still validate business
> semantics, resolve the exact allowed tool version, authorize the trusted user and tenant, and admit this
> specific call before execution.

### Intermediate Question

**What is the difference between a Tool Definition and a Tool Admission Gate?**

Student answer:

> The tool definition encompasses details such as the tool's version, required parameters, and name, while the
> tool onboarding process involves a series of validation steps that ultimately authorize the tool for invocation.

Assessment: passed with terminology correction. It is Tool **Admission**, not onboarding, and it permits one
candidate invocation rather than granting permanent tool authority.

Strong answer:

> A Tool Definition declares an application-owned name, version and argument schema. The Admission Gate
> evaluates one untrusted candidate against the Registry, schema, trusted authorization and business state,
> then creates a server-normalized command only if every check passes.

### Senior Question

**Does a Registry check immediately before execution guarantee zero effects if disable races with an external
call? What stronger mechanism is required?**

Student answer:

> I think we should use update set returning

Follow-up answer:

> Since external calls and other side effects that have already occurred cannot be undone, one can choose
> between reconciliation and compensation.

Assessment: passed. Atomic conditional claim is the correct direction; the complete design also needs durable
identity, lifecycle epoch/fencing, external idempotency where supported, and reconciliation because DB rollback
cannot undo an accepted external request.

### Common Weak Answer

“The Provider guarantees JSON, so call the function and retry on timeout.” This confuses format with authority
and can create cross-tenant or duplicate side effects.

### Strong Answer

“Treat both model call and tool outcome as untrusted candidates. Validate strict versioned schemas, authorize
from server context, admit one immutable command, claim idempotently, verify outcome identity, and commit only
through guarded durable state. Reconcile timeout-unknown instead of retrying blindly.”

## 14. Mental Model Summary

```text
Provider SUCCESS   = transport/provider fact, not business truth
JSON parse         = readable data, still untrusted
Schema Validation  = structural contract
Semantic Validation= business meaning
Authorization      = trusted identity may act
Tool Definition    = declared name/version/arguments
Tool Admission     = permission for this candidate invocation
AdmittedToolCall   = immutable server-normalized command
Idempotency claim  = one logical operation owner
Outcome Verification = schema + semantics + identity
Guarded Completion = durable current-state decision
TIMEOUT_UNKNOWN    = reconcile, never blind retry
Rollback/disable   = stop future harm, never rewrite history
Compensation       = new authorized operation countering confirmed harm
```

> **Final Chinese synthesis — attribution: supplied by the teaching assistant at the student's explicit
> request; not independently authored by the student.**
>
> Provider 返回的只是模型候选结果。Parse、Schema、语义和授权必须分别通过；模型参数中的 tenant 不是可信身份。
> Tool Admission 为一次候选创建不可变的 `AdmittedToolCall`，Executor 只接收它，并执行生命周期检查与原子幂等
> claim。工具返回仍需验证 operation/report/version/Attempt/tool-call identity，再由 Durable Store guarded
> completion。发送后超时属于 `TIMEOUT_UNKNOWN`，必须依据持久化状态和外部证据 reconciliation；确认可逆错误
> 副作用后才执行受控 repair/compensation，并保留原始证据。

## 15. Today's Takeaway

- **Mental model:** the model proposes; the application validates, authorizes, admits, executes and records.
- **Production risk:** treating valid JSON/tool calls/HTTP 200 as authority creates tenant breaches and duplicate
  effects.
- **Trade-off:** strict versioned contracts and durable claims add lifecycle work but make failure fail-closed,
  auditable and recoverable.
- **Framework connection:** typed web models help at the HTTP boundary; durable conditional transitions are
  still required at the execution/completion boundary.
- **AI Backend connection:** tool calling is safe only as a permissioned application workflow, not autonomous
  execution of model text.
- **Interview answer:** “Schema proves shape; trusted authorization and per-call Admission decide execution.”

## 16. Before Next Lesson Checklist

- [ ] I can distinguish ordinary text, JSON text, Python `dict` and a validated object.
- [ ] I can explain why Provider `SUCCESS`, parse success and Schema success are different claims.
- [ ] I can explain each boundary's owner and whether it occurs before or after tool execution.
- [ ] I can reject unknown fields/tools/versions and model-derived authority fail closed.
- [ ] I can explain why the Executor accepts only `AdmittedToolCall`.
- [ ] I can defend atomic idempotency claim and its external exactly-once limitation.
- [ ] I can separate Outcome Verification from guarded completion.
- [ ] I can choose reject, re-prompt, retry, reconcile, repair or compensation for the right failure class.
- [ ] I can explain why Day75 streaming/cache/batching must preserve complete validated boundaries.
- [ ] I can answer all three English interview levels.

---

Related: [Day74 design contract](../../projects/ai-agent/docs/DAY74_OUTPUT_TOOL_CONTRACTS.md) ·
[Day74 classroom record](../../projects/ai-agent/docs/day74-output-tool-contracts-classroom-draft.md) ·
[ai-agent project](../../projects/ai-agent/README.md) ·
Previous: [Day73 lesson](day73-prompt-contracts-prompt-versioning-and-compatibility.md) ·
Next: Day75 — Streaming Responses, Caching and Batching (Planned).
