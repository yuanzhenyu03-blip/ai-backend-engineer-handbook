# Day71 — LLM Application Architecture, Tokens, Context, Sampling and Model Failure Modes

## 1. Lesson Metadata

```text
Status:        ✅ Completed (classroom scope) — CONCEPTUAL + STATIC only. The Day71 artifact is provider-independent design documentation; EXECUTED_LOCAL_RUNTIME, INTEGRATION_RUNTIME and PRODUCTION are NOT RUN. No real or paid Provider call was made.
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 5-6 hours
Prerequisite:  Day53 Provider boundary + structured output · Day54 streaming/lifecycle · Day56 resilience/token cost/backpressure · Day57 Fake Provider/contract tests/failure injection · Day58 correlated observability/evidence · Day61 Provider Adapter over real HTTP
Previous Lesson: Day70 — n8n + FastAPI + AI Tool Integration Capstone (chronological previous / Phase 6 close; PHASE TRANSITION, not the technical prerequisite)
Next Lesson:   Day72 — Provider Capabilities and the Replaceable Provider Adapter
Engineering Artifact: projects/ai-agent/ (Phase 7A LLM Application Runtime foundations: classroom draft + provider-independent design contract; no runtime code yet)
```

Day71 opens **Phase 7A — LLM Application Engineering**. Phase 6 (Day67–Day70) orchestrated backends with n8n
but never owned an LLM application layer. Day71 builds the first **provider-independent foundations** of an
LLM Application Runtime on top of the Day53 Provider boundary: finite token/context budgeting, an explicit
input-transformation policy, sampling boundaries, layered output validation, a model-failure taxonomy,
reconciliation, Attempt identity, and guarded completion.

> Evidence honesty — Day71 is CONCEPTUAL + STATIC only, and nothing here is executed:
>
> * `CONCEPTUAL` — completed in the live class: architecture boundary, token/context budget, chunking and
>   aggregation, sampling, the validation/failure matrix, request lifecycle, reconciliation, rollback,
>   Attempt identity, guarded completion, and the final Mental Model.
> * `STATIC` — `PASS`: the artifact documents are non-empty, required sections are present, fenced blocks are
>   balanced, and trailing-whitespace and common credential-pattern scans returned no matches.
> * `EXECUTED_LOCAL_RUNTIME` — **NOT RUN**. There is no runtime code, no test suite, and no fake-Provider
>   execution in Day71.
> * `INTEGRATION_RUNTIME` — **NOT RUN**. No Provider, database, or external process was exercised.
> * `PRODUCTION` — **NOT RUN**. No real or paid Provider call; no credentials; no customer data.
>
> The Day53–Day61 runtime evidence is a named **prerequisite**, not Day71 validation. Day71 does not upgrade
> any earlier tier. Any Provider token count, context-window size, or sampling-parameter behaviour named
> below is a **versioned current capability**, never a permanent fact.

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain the LLM Application Runtime architecture boundary in plain English: the application owns the
  contract; the Provider does not decide the product.
* Explain why a token is a **model-specific text unit**, not a fixed character, word, or byte, and why the
  context window is a **finite shared budget**.
* Separate **input tokens**, **reserved output tokens**, and the **token budget**, and treat reserved output
  as capacity, not a promise.
* Choose an explicit context-overflow policy — `TRUNCATE`, `REJECT`, `SUMMARIZE`, or `CHUNK` — from the
  business contract, and defend the trade-off.
* Explain sampling (`temperature`, `top_p`) as **selection behaviour, not factual control**, and distinguish
  **deterministic** from **reproducible**.
* Classify model failure modes (hallucination/unsupported evidence, contradicted evidence, format failure,
  truncation, timeout-unknown, provider failure) and separate **root cause from symptom**.
* Apply layered validation, distinguish **retry / reject / reconciliation**, and explain **Job vs Attempt**
  and **guarded completion**.
* Contain a bad configuration release: roll back future behaviour without erasing historical facts.
* Answer beginner, intermediate, and senior interview questions in English on tokens, context, timeout, and
  incident repair.

Note: the Day71 "engineering artifact" is **provider-independent design documentation and a static
contract**, not Python code. That is the correct artifact for a foundations lesson; runtime code begins in
later Phase 7A days.

## 3. Why This Matters

A backend engineer who calls an LLM the way they call a normal REST API ships an unreliable product. The
model runs on **finite context**, charges by **tokens**, returns **plausible but sometimes unsupported**
output, and can **time out after money has already been spent**. None of that is visible from a single happy
-path call.

The production problems Day71 prevents:

* **Silent truncation.** A request that does not fit the context window gets quietly cut, and the report
  loses exactly the evidence a customer needed. Cost impact: you paid for a call that produced an unusable
  result and did not know why.
* **Trusting HTTP 200.** A transport success and a schema-valid body do not make a claim true. Accepting
  model output as fact ships hallucinations to customers.
* **Blind retry after timeout.** A timeout is **unknown**, not "did not happen." Retrying can double the
  Provider cost or duplicate an external side effect.
* **Overwriting history to look clean.** Deleting a failed Attempt or letting a late result silently replace
  an accepted Artifact destroys audit truth and breaks reconciliation.

This is the multi-tenant AI Research Platform scenario the whole camp has been building: a tenant asks for a
research report with exact citations, and the Runtime must admit, budget, call, validate, and either complete
under guard or classify the non-success — never guess.

## 4. Roadmap Position

```text
Day53 Provider boundary + structured-output validation
   -> Day54 streaming + independent HTTP/Provider/durable-Job lifecycles
   -> Day56 resilience, token cost, rate limits, backpressure
   -> Day57 Fake Provider, contract tests, failure injection
   -> Day58 correlated observability + evidence tiers
   -> Day61 Provider Adapter over real HTTP + Object Storage + OpenTelemetry evidence
   -> Day71 LLM Application Runtime foundations  (YOU ARE HERE — Phase 7A begins)
   -> Day72 replaceable Provider capabilities (Provider Adapter)
   -> Day73 versioned prompt contracts
   -> Day74-Day78 structured output / streaming-caching / routing / regression / capstone
   -> Day79+ framework-agnostic Agent Runtime (indirect consumer)
```

### Knowledge Continuity

```text
Previous Knowledge (technical prerequisites)
   Day53 Provider boundary + structured output
   Day54 streaming and lifecycle boundaries
   Day56 resilience, cost, backpressure
   Day57 Fake Provider + contract tests
   Day58 observability + evidence tiers
   Day61 Provider Adapter HTTP integration evidence
        |
        v
Current Lesson Concept
   LLM Application Runtime foundations:
   token/context budget · input policy · sampling · failure taxonomy ·
   reconciliation · Attempt identity · guarded completion
        |
        v
Future Production Usage
   Day72 replaceable Provider Adapter
   Day73 versioned prompt contracts
   Day74+ structured output / streaming / routing / tests
   Day79+ Agent Runtime as an indirect consumer
```

**Previous-lesson connection (read carefully).** Day70 is the **chronological** previous lesson and the
Phase 6 capstone, but it is **not** the technical prerequisite of Day71. `Day70 -> Day71` is a
`PHASE_TRANSITION` (Phase 6 -> Phase 7A). **n8n has no direct dependency on Day71.** n8n may *later* be an
external consumer/orchestrator of an LLM Application Runtime, but Day71 does not depend on it, does not
extend it, and does not require it. Day70's boundary still holds where it applies — n8n orchestrates, FastAPI
authenticates/authorizes and enforces transitions, PostgreSQL owns durable truth — but the technical roots of
Day71 are Day53–Day61.

**Why here.** Phase 6 could move work between services but had no principled LLM application layer. Before
Phase 7A can make the Provider replaceable (Day72) or version prompts (Day73), the application must first own
its finite-budget, failure-aware runtime contract. That is Day71.

## 5. Lesson Map

```text
Architecture boundary (application owns the contract)
  -> Tokens (model-specific unit)
  -> Context window (finite shared budget: system + user + docs + overhead + reserved output + margin)
  -> Overflow policy (TRUNCATE / REJECT / SUMMARIZE / CHUNK)
  -> Chunking + bounded aggregation (candidates, provenance, RESOLVED/CONFLICT/INSUFFICIENT_EVIDENCE)
  -> Provider-independent contract vs Provider-specific capability
  -> Sampling (temperature / top_p; deterministic vs reproducible; not factual control)
  -> Layered validation (transport -> schema -> evidence -> policy -> guarded completion)
  -> Failure taxonomy (hallucination / contradicted / format / truncation / timeout-unknown / provider)
  -> Recovery (retry / reject / reconciliation; timeout = PENDING_RECONCILIATION)
  -> Job vs Attempt + guarded completion
  -> Rollback (stop future harm, never erase history)
```

## 6. Core Mental Model

```text
Business request
  -> Provider-independent application contract
  -> LLM Application Runtime
       -> token/context budget policy
       -> input transformation policy (reject / summarize / chunk)
       -> sampling policy (versioned)
       -> layered validation + failure classification
  -> Provider Adapter (translates versioned Provider capabilities/failures)
  -> ONE authorized Provider call belongs to ONE Attempt
  -> translated outcome -> transport -> schema -> evidence -> policy gates
  -> guarded completion OR classified non-success
```

Two sentences to hold onto: **the application owns the contract, the Provider owns only a capability** — the
Adapter translates but must never silently weaken the contract. And **a valid-looking model result has no
authority**: it becomes a business fact only after layered validation and a guarded completion bound to the
currently authorized Attempt.

## 7. Main Concepts

### Concept 1: The LLM Application Runtime architecture boundary

Tech Lead Question:

When a tenant asks for a Research Report, who owns the product contract — your application or the model
Provider?

Student Thinking:

Early instinct is that the model "does the work," so the model decides the result. But the camp has spent
Day53–Day61 insisting the *application* owns truth, authz, and durability.

Student Answer:

The application owns the contract; the Provider is a capability behind an Adapter.

Tech Lead Review:

Correct. The Runtime owns application policy — token/context budget, input transformation, sampling policy,
validation, and failure classification. The **Provider Adapter** translates Provider-specific capabilities
and failures, but it must **never silently weaken the application contract**. Provider/model context sizes,
tokenization, and parameter support are **versioned capabilities, not permanent constants** — writing a
specific number into the contract as if it were forever is a bug.

Engineering Thinking:

The boundary exists so the product does not change meaning every time a Provider changes a limit or a
parameter. Alternatives (let the SDK shape drive your API, or hardcode one Provider's limits) couple your
product to a vendor and make Day72's replaceable Adapter impossible.

Production Example:

FastAPI accepts the Research Report business request. It does **not** delegate product truth to Provider
output — the model's text is a proposal until the Runtime validates it.

Framework Connection:

FastAPI owns the request boundary; the Day53 Provider Adapter is the seam where Provider specifics are
translated into application-owned outcomes.

### Concept 2: Tokens and the finite context budget

Tech Lead Question:

Is a token a character? A word? A byte?

Student Thinking:

It "feels like" a word or a fixed number of characters.

Student Answer:

None of those — a token is a model-specific text unit.

Tech Lead Review:

Right. A token is a **model-specific** unit produced by that model's tokenizer; it is not a fixed character,
word, or byte, and it differs across models. The **context window** is a **finite capacity shared** by the
system instruction, user input, input documents, request/schema overhead, generated output, and a safety
margin.

```text
input tokens = system instruction + user input + input documents + request/schema overhead

input tokens + reserved output tokens + safety margin <= effective context limit
```

Reserved output tokens are **capacity, not a promise** that every reserved token will be used. Tokenization,
context sizes, and parameter support are versioned capabilities.

Engineering Thinking:

If you do not admit a request against the budget **before** calling, you pay for a call that can truncate. The
budget check is admission control for a paid, finite resource.

Production Example:

Token/context admission runs **before** a paid call: if system + user + documents + reserved output +
margin exceeds the limit, the Runtime applies an explicit policy instead of hoping it fits.

Framework Connection:

This is the Day56 token-cost/backpressure mindset applied at the request boundary, not after the bill.

### Concept 3: Context-overflow policy — TRUNCATE / REJECT / SUMMARIZE / CHUNK

Tech Lead Question:

An evidence-critical report does not fit the context window. What do you do?

Student Thinking:

The generic reflex is "summarize it so it fits."

Student Answer (initial):

`我认为应该采用摘要` — "I think we should use summarization."

Tech Lead Review:

Reasonable as a first instinct, but incomplete. Name the four policies precisely:

```text
TRUNCATE   remove content; fast, but can destroy meaning or evidence
REJECT     make no Provider call when the contract cannot be met
SUMMARIZE  a LOSSY transformation, not lossless compression
CHUNK      process bounded pieces with stable document/chunk identity, then reconcile and aggregate
```

Then the business constraint arrived: the report needs **exact citations**. Summarization is lossy, so it can
destroy the exact evidence the contract requires.

Student Answer (evolved):

`使用分块` — "use chunking."

Tech Lead Review:

That is the correct evolution. When exact evidence is a business requirement, prefer chunking over silent
whole-document summarization. The mental-model trajectory matters more than the final word:

```text
Initial model:  overflow -> summarize (generic default)
Reasoning:      exact citations are required; summarize is lossy
Correction:     choose the transformation from the business contract
Final model:    evidence-critical -> CHUNK; lossy summary only when loss is acceptable
```

Engineering Thinking:

The policy is a **product decision**, not a technical convenience. `REJECT` is the honest answer when no
transformation can meet the contract — no call is better than a call that silently violates it.

Production Example:

The Research Platform chunks long source documents with stable identity so citations survive, and reserves
`REJECT` for requests that cannot be satisfied at all.

Framework Connection:

The chunk contract reuses the Day44 Pydantic-style structured-field discipline: each candidate is a typed,
bounded record, not free text.

### Concept 4: Chunking and bounded aggregation

Tech Lead Question:

You produced three overflow-driven chunks. How many Provider calls is that?

Student Thinking:

Genuinely unsure whether chunking fixes the number of calls or only the input size.

Student Question:

`我还有个问题，分块以后是分了三次调用provider吗还是都放在一个provider context里` — "one more question: after
chunking, is it three separate Provider calls, or do they all go into one Provider context?"

Tech Lead Review:

Good question — this is exactly the point people get wrong. Chunking is first an **input-division strategy**;
by definition it does **not** fix a specific number of Provider calls. The number of calls is decided by the
Runtime's **processing plan**, each call's **context budget**, the **evidence-completeness** requirement, and
the **Provider capability** — not by the word "chunk." In **this** Day71 scenario the three chunks are
overflow-driven: each one needs independent processing and they cannot all fit in one context, so it is
normally **three independent processing calls**. If the results must then be combined, there is a **separate
bounded aggregation call** — so this specific scenario is usually **three processing calls + one aggregation
call**. Other product scenarios differ: a task might process only some chunks, or, when the budget allows,
place several chunks in one call. Do **not** turn "one chunk = one Provider call" into a universal rule. The
aggregation call receives **bounded structured candidates, necessary evidence excerpts, and source
references** — not every complete document again.

A conceptual candidate carries:

```text
claim_id · claim · document_id · chunk_id · evidence_excerpt · section/time_scope (when relevant)
status = CANDIDATE   (untrusted until validated)
```

On aggregation input the student was precise:

Student Answer:

`只传"结构化候选结论、必要证据片段和来源引用` — "only pass structured candidate claims, necessary evidence
excerpts, and source references."

And on conflicting chunk claims:

Student Answer:

`我觉得应该先保留这两条结论进入reconcile` — "keep both conclusions and enter reconciliation."

Tech Lead Review:

Exactly. Aggregation outcomes are `RESOLVED | CONFLICT | INSUFFICIENT_EVIDENCE`. Conflicting claims **retain
provenance and enter reconciliation** — they are never concatenated as if both were facts.

Engineering Thinking:

Aggregation is a second finite-context problem. Passing raw documents again reintroduces overflow and buries
provenance; passing bounded candidates keeps the citation chain intact.

Production Example:

Two chunks disagree on a figure; the Runtime keeps both candidates with their `document_id`/`chunk_id` and
marks the aggregate `CONFLICT` for reconciliation instead of averaging them into a false "fact."

Framework Connection:

This is the same provenance discipline as Day64's evidence-Artifact extraction: a claim without a source is
not a result.

### Concept 5: Provider-independent contract vs Provider-specific capability

Tech Lead Question:

Provider B does not natively support JSON Schema structured output. Do you weaken your contract to match it?

Student Thinking:

It would be easy to "just accept the text this time."

Student Answer:

`还是保持原契约并验证或拒绝这次调用` — "keep the original contract and validate, or reject this call."

Tech Lead Review:

Correct and important. Separate the two:

```text
Provider-specific capability:  current context limit, native structured-output support,
                               sampling parameters, Provider error/finish evidence  (VERSIONED)
Provider-independent contract: application-owned request/result/failure MEANING       (STABLE)
```

The Adapter translates capabilities and failures but must **never silently weaken `research_claims.v1`**. If a
Provider cannot meet the required contract, either validate through an **explicitly supported path** or return
`PROVIDER_CAPABILITY_ERROR` — do **not** silently accept ordinary text and call it structured output.

Engineering Thinking:

Silent weakening is invisible debt: it "works" until a downstream consumer trusts a field the model never
actually guaranteed. An explicit capability error is honest and keeps Day72's replaceable Adapter viable.

Production Example:

The Adapter for a schema-less Provider runs an explicit validate-and-repair path or returns
`PROVIDER_CAPABILITY_ERROR`; it never downgrades `research_claims.v1` to "whatever text came back."

Framework Connection:

This is the Day53 Provider-boundary contract made explicit for Phase 7A and set up for Day72.

### Concept 6: Sampling — selection behaviour, not factual control

Tech Lead Question:

If you lower the temperature and the model repeats the same answer, does that prove the answer is correct?

Student Thinking:

Repeatability *feels* like reliability.

Student Answer:

`不能` — "no."

Tech Lead Review:

Correct, immediately. Sampling selects a next token from a **probability distribution**. `temperature`
changes how concentrated the candidate probabilities are; `top_p` restricts the candidate mass. Exact
semantics and support are **Provider/model-specific**. Sampling controls **selection behaviour, not factual
correctness** — a confidently repeated claim can be confidently wrong.

A three-candidate illustration introduces probability without requiring probability theory:

```text
next-token candidates:  "increased" (0.62) · "decreased" (0.28) · "stabilized" (0.10)
low temperature  -> distribution sharpens toward "increased"
top_p = 0.9      -> restrict to the smallest candidate set whose mass >= 0.9
```

Deterministic vs reproducible:

```text
Deterministic: identical COMPLETE conditions necessarily produce the same output.
Reproducible:  the recorded procedure can be rerun and reviewed; it does NOT guarantee
               byte-identical managed-model output. A Provider seed may improve repeatability
               but is not a universal, permanent guarantee.
```

Engineering Thinking:

Teams reach for low temperature or a fixed seed hoping for "truth." What they actually get is more stable
*selection*. Factual correctness comes from the evidence gate, not the sampler.

Production Example:

The Runtime versions its sampling policy (for audit and reproducibility of the *procedure*) but never records
"low temperature" as a factual-quality control.

Framework Connection:

The OpenAI-style `temperature`/`top_p` parameters are Provider-specific capabilities translated by the
Adapter — never baked into the application contract as fixed semantics.

### Concept 7: Layered validation and the model-failure taxonomy

Tech Lead Question:

The Provider returned HTTP 200 and the JSON matches your schema. Is the research result correct?

Student Thinking:

Green transport and valid schema look like success.

Student Answer:

No — transport and schema success do not establish factual correctness.

Tech Lead Review:

Right. Validation is **layered**:

```text
transport gate -> format/schema gate -> evidence/semantic gate -> application-policy gate -> guarded completion
```

A result can pass transport and schema and still fail the evidence gate. The failure taxonomy the class used:

```text
HALLUCINATION_OR_UNSUPPORTED_EVIDENCE  plausible claim/citation lacks support
CONTRADICTED_EVIDENCE                  citation exists but contradicts the claim
FORMAT_FAILURE                         application schema/format violation
TRUNCATION                             output ends before the required result is complete
TIMEOUT_UNKNOWN                        deadline passed without a complete result; remote execution/cost may be unknown
PROVIDER_FAILURE                       Adapter-classified auth/rate-limit/capability/service/transport failure
```

The class exercised three sharp cases:

* Valid schema, citation to a document that does not exist:

  Student Answer: `hallucination / unsupported evidence`.

* A real citation that contradicts the claim:

  Student Answer: `第三个验证阶段，结论不受证据支撑` — "the third validation stage: the claim is not supported
  by the evidence." (This is `CONTRADICTED_EVIDENCE`, caught at the evidence gate.)

* Truncated JSON because the output budget ran out:

  Student Answer: `记录其他主要原因并调整处理策略` — "record the other primary cause and adjust the handling
  strategy."

Tech Lead Review:

The truncation case is the key precision point: **root cause and symptom are distinct.** Output-budget
exhaustion is the **primary** `TRUNCATION`; the incomplete JSON is a **derived** `FORMAT_FAILURE`. If you log
only "bad JSON," you fix the wrong thing and it recurs.

Engineering Thinking:

Each gate exists because the previous one cannot see the next kind of error. Transport cannot see schema;
schema cannot see evidence; evidence cannot see business policy. Collapsing them hides failures.

Production Example:

A schema-valid report with an unsupported citation is rejected at the evidence gate and never marks the Job
succeeded.

Framework Connection:

The schema gate reuses Day44/Day53 structured-output validation; the evidence gate is application-specific and
cannot be delegated to the Provider.

### Concept 8: Recovery — retry, reject, reconciliation

Tech Lead Question:

The Runtime dispatched a call and then hit its own timeout. Do you retry?

Student Thinking:

Retry is the reflex for "something went wrong."

Student Answer:

`进行协调` — "reconcile."

Tech Lead Review:

Correct. Separate the three recovery actions:

```text
retry          a NEW external execution
reject         refuse this execution/result
reconciliation gather evidence for an UNKNOWN outcome
```

A **timeout after dispatch** enters `PENDING_RECONCILIATION`: the Provider may have received, executed, and
charged for the call — you do not know. So the Runtime **holds the original Attempt identity and cost
uncertainty** and **forbids blind retry**. Provider-specific request/status/callback evidence may support
reconciliation **through the Adapter**. A **late** result passes the **same** validation gates; lateness never
weakens the contract.

On an **invalid** late result:

Student Answer: `不能` — "it cannot" (complete the Job). A schema-valid late result with unsupported evidence
is `COMPLETED_INVALID`.

Engineering Thinking:

Blind retry after an unknown outcome is how teams double-charge Providers or duplicate side effects.
Reconciliation is evidence gathering, not a delayed retry.

Production Example:

After a Runtime timeout, the Job sits `PENDING_RECONCILIATION` while the Adapter queries Provider
request/status evidence; only proven non-execution justifies a new Attempt.

Framework Connection:

This is the Day56/Day68 `OUTCOME_UNKNOWN` discipline applied to Provider calls.

### Concept 9: Job vs Attempt, rollback, and guarded completion

Tech Lead Question:

A bad output-budget policy (v2) caused truncation. You roll it back. Does rollback undo the truncated call?

Student Thinking:

Rolling back "fixes" things — maybe it erases the bad Attempt.

Student Answer:

`配置回滚，不能。` — "configuration rollback; it cannot [undo the calls]."

Tech Lead Review:

Correct. **Configuration rollback stops future harm; it cannot undo Provider calls, outputs, cost, or durable
facts.** Scope the affected set by **policy/release version, a bounded time window, and audit/failure
evidence** before per-Job repair.

Job vs Attempt:

```text
job_id     = stable business-task identity
attempt_id = one concrete execution identity
new Provider call = NEW Attempt   (old Attempts are never overwritten or deleted)
```

On a new Provider call:

Student Answer: `创建新的 Attempt` — "create a new Attempt."

On the final states after repair:

Student Answer: `不能删除，job保留success，两个attempt保留各自的状态` — "cannot delete; the Job keeps SUCCEEDED;
both Attempts keep their own state."

```text
Job job-100: SUCCEEDED
├── Attempt A1: TRUNCATED  (bad budget policy; historical fact retained)
└── Attempt A2: SUCCEEDED  (new authorized call; all validation gates passed)
```

A new Attempt is allowed only after current **deadline, budget, contract, cancellation/execution evidence, and
guarded claim permission** are satisfied.

**Guarded completion.** A valid model result has **no automatic authority** to change durable business state.
Completion requires a **live Job** and the **exact currently authorized Attempt** binding. A stale/late result
has **zero effect** on Job status, Result Artifact, and success Event.

On a stale A1 trying to replace A2:

Student Answer: `不能` — "cannot."

```text
Job job-100 current Attempt: A2
late result Attempt:          A1
-> STALE_LATE_RESULT -> zero-effect refusal
-> no Job status, Artifact, success Event, or cost-history overwrite
```

Better prose from an old Attempt cannot silently replace an already accepted Artifact; a desired new version
requires an **explicit authorized business workflow**.

Engineering Thinking:

Job vs Attempt is what makes retries auditable. If a retry overwrote the Attempt, you would lose the record
that the first call cost money and truncated — exactly the evidence reconciliation and billing need.

Production Example:

On the integrated scenario — chunk-1 valid, chunk-2 `TIMEOUT_UNKNOWN`, chunk-3 valid — the student was
explicit:

Student Answer: `不能，进入pending_reconcilation` — "cannot [complete]; enter PENDING_RECONCILIATION."

The Runtime keeps chunk-1/3 candidates, holds the Job `PENDING_RECONCILIATION`, reconciles chunk-2, and
aggregates only after the evidence-completeness policy is satisfied.

Framework Connection:

Job/Attempt/guarded-completion is the same durable-truth ownership taught in Day59–Day61 and reused for LLM
calls; PostgreSQL/durable state is referenced only for that truth — Day71 executed no real database.

## 8. Common Misconceptions

```text
Token
❌ A token is a fixed number of characters/words/bytes.
✅ A token is a model-specific text unit that differs across models and Providers.
```

Why beginners think this: examples often say "~4 characters per token." How to remember: the tokenizer is part
of the model, so the unit is model-specific and versioned.

```text
Context window
❌ A bigger context window is unlimited memory and automatic quality.
✅ It is a finite budget shared by system + user + documents + overhead + reserved output + margin.
```

Why beginners think this: "128k context" sounds like "fits everything." How to remember: output and margin
compete with input inside the same budget.

```text
Reserved output tokens
❌ Reserving output tokens guarantees the model uses them.
✅ Reservation is capacity, not a promise; the model may use fewer.
```

```text
Overflow handling
❌ Summarize to make it fit.
✅ Choose TRUNCATE/REJECT/SUMMARIZE/CHUNK from the business contract; exact evidence favors chunking; summary is lossy.
```

Why beginners think this: summarize is the generic "make it smaller" reflex. How to remember: summarize is
lossy — if exact citations matter, chunk (or reject).

```text
Sampling
❌ Low temperature / fixed seed proves the output is factually correct.
✅ Sampling controls selection behaviour; correctness comes from the evidence gate. Reproducible ≠ deterministic ≠ true.
```

```text
HTTP 200 + valid schema
❌ Transport success and schema validity mean the result is correct.
✅ They are necessary at some gates but never establish factual/evidence correctness.
```

```text
Root cause vs symptom
❌ Incomplete JSON is a formatting bug.
✅ Output-budget exhaustion is the primary TRUNCATION; the incomplete JSON is a derived FORMAT_FAILURE.
```

```text
Timeout
❌ A timeout means the call did not happen (safe to retry).
✅ A timeout is TIMEOUT_UNKNOWN — execution/cost may have occurred; enter PENDING_RECONCILIATION, no blind retry.
```

```text
Rollback / history
❌ Rolling back a bad policy undoes its calls and lets you delete failed Attempts.
✅ Rollback stops future harm only; Provider calls, cost, outputs, and Attempt history are preserved.
```

Note the terse-answer classroom record: `pending_reconcilation` was a **spelling error only** — the
engineering concept was correct. Correct spelling: `PENDING_RECONCILIATION`.

## 9. Engineering Trade-offs

```text
SUMMARIZE vs CHUNK (for an evidence-critical report)

SUMMARIZE:
- Fewer Provider calls, lower latency and cost
- Lossy: exact citations and figures can disappear
- Acceptable only when loss of exact evidence is allowed

CHUNK:
- Preserves stable document/chunk identity and provenance
- More Provider calls + an aggregation step (more cost/latency/complexity)
- Required when the contract needs exact evidence

Tech Lead review: choose from the contract, not from convenience.
```

```text
REJECT vs force-fit (TRUNCATE)

REJECT: no Provider call, no spend, honest failure when the contract cannot be met.
TRUNCATE: a result, but possibly missing the exact content the customer needed.
Choose REJECT when a silent contract violation is worse than a clear "cannot satisfy."
```

```text
Low temperature / seed vs evidence validation (for "reliability")

Sampling stability: cheaper, improves output stability and procedure repeatability.
Evidence validation: the only thing that establishes factual support; costs an extra gate.
Do not substitute sampling stability for the evidence gate — they solve different problems.
```

```text
Blind retry vs reconciliation (after a timeout)

Blind retry: simple, but can double Provider cost or duplicate a side effect on an unknown outcome.
Reconciliation: gathers Provider request/status evidence, preserves Attempt identity, retries only when proven safe.
Prefer reconciliation whenever execution/cost is unknown.
```

```text
Provider-specific contract vs Provider-independent contract

Provider-specific: uses each Provider's native features directly; fast, but couples the product to a vendor.
Provider-independent: stable application meaning behind an Adapter; enables Day72 replaceability and honest capability errors.
When a Provider cannot meet the contract: explicit supported path or PROVIDER_CAPABILITY_ERROR, never silent weakening.
```

## 10. Hands-on Exercises

These are **design/reasoning** exercises. Day71 produces provider-independent documentation and a static
contract — **no runtime code, no Provider call**.

### Exercise 1: Choose an overflow policy

Question: An evidence-critical report with required exact citations does not fit the context window. Pick from
TRUNCATE / REJECT / SUMMARIZE / CHUNK and justify it.

Think First: Which policies are lossy? What does the contract require?

Starter Artifact:

```text
required: exact citations
candidate policies: TRUNCATE | REJECT | SUMMARIZE | CHUNK
```

Expected Output: CHUNK (stable document/chunk identity preserves citations); SUMMARIZE is rejected as lossy;
REJECT is the honest fallback if no transformation can meet the contract.

Explanation: the policy is a product decision derived from the business contract.

Follow-up Question: When would SUMMARIZE be acceptable?

### Exercise 2: Decide aggregation inputs under a finite budget

Question: Three chunk calls returned candidates. What do you pass to the aggregation call?

Think First: Aggregation is itself a finite-context problem.

Starter Artifact:

```text
per candidate: claim_id · claim · document_id · chunk_id · evidence_excerpt · scope · status=CANDIDATE
```

Expected Output: pass **bounded structured candidates + necessary evidence excerpts + source references** —
not every complete document again.

Explanation: resending raw documents reintroduces overflow and buries provenance.

Follow-up Question: Two candidates conflict. What is the aggregate outcome? (Answer: `CONFLICT` -> reconcile
with provenance; never concatenate as fact.)

### Exercise 3: Separate root cause from symptom

Question: The Provider returned incomplete JSON because the output budget ran out. Classify it.

Think First: What actually failed first?

Expected Output: primary `TRUNCATION`; derived `FORMAT_FAILURE`. Adjust the budget policy before a new call.

Explanation: logging only "bad JSON" fixes the wrong layer and lets it recur.

Follow-up Question: What evidence tells you it was budget exhaustion rather than a schema bug? (Completion/
finish reason + reserved-output budget.)

### Exercise 4: Recover from a timeout after dispatch

Question: The Runtime timed out after dispatching the call. Decide the next state and action.

Expected Output: `PENDING_RECONCILIATION`; hold the original Attempt identity and cost uncertainty; no blind
retry; use Adapter request/status evidence; a late result passes the same gates.

Follow-up Question: A late result arrives that is schema-valid but has an unsupported citation. What state?
(Answer: `COMPLETED_INVALID` — reject; do not complete the Job.)

### Exercise 5: Contain a bad output-budget policy release

Question: Policy v2 reduced output reservation and caused truncation across many Jobs. Contain and repair.

Think First: What can rollback actually undo?

Expected Output (the student's five-step answer): (1) roll back configuration to stop future harm; (2) preserve
evidence; (3) scope the affected set by policy/release version + time window + failure evidence; (4) per-Job
eligibility checks; (5) controlled new Attempts only. No bulk success, no unconditional retry, no history
deletion.

Explanation: rollback stops future behaviour; it never erases prior calls, cost, outputs, or Attempt history.

Follow-up Question: Why must each repaired Job get a **new** Attempt rather than an overwrite? (Audit + billing
truth.)

### Exercise 6: Preserve a strict contract against a weaker Provider

Question: Provider B lacks native JSON Schema support. Keep `research_claims.v1`?

Expected Output: keep the contract; validate through an explicitly supported path or return
`PROVIDER_CAPABILITY_ERROR`; never silently accept ordinary text.

Follow-up Question: How does this decision make Day72's replaceable Adapter possible?

## 11. Relevant Framework Connections

**FastAPI.** FastAPI accepts the Research Report business request and owns the request boundary. It does not
delegate product truth to Provider output — the model's response is a proposal that must pass the Runtime's
gates before it becomes a Result Artifact. Token/context admission happens before a paid call, at this
boundary.

**OpenAI API (as a Provider capability, via the Adapter).** `temperature`, `top_p`, context sizes, native
structured-output support, and finish/error evidence are **Provider-specific, versioned capabilities**. The
Provider Adapter translates SDK/API request identity, finish/error evidence, and Provider failures into
application-owned outcomes. Never hardcode a specific Provider's token count, context size, or
sampling-parameter semantics as permanent fact; never let the SDK's convenience weaken `research_claims.v1`.

**PostgreSQL / durable state (referenced, not executed).** Job/Attempt/Artifact identity and guarded
completion are durable-truth concepts owned by the backend. Day71 **references** this ownership for reasoning
only — **no real database was executed** in this lesson.

**n8n (explicitly excluded as a prerequisite).** n8n is **not** a Day71 dependency. It remains only a possible
future external consumer/orchestrator of an LLM Application Runtime. Do not model Day71 as an n8n extension.

## 12. AI Backend Connections

Day71 is entirely an AI-backend lesson; the connections are the substance:

* **Token/context admission before a paid call.** Admission control for a finite, billed resource prevents
  silent truncation and wasted spend.
* **Evidence-preserving chunking and bounded aggregation.** Long-document RAG-style inputs must keep
  provenance so citations survive; aggregation passes bounded candidates, not raw documents.
* **Sampling policy versioning without claiming factual control.** Version the sampling policy for procedure
  reproducibility and audit — never as a factual-quality guarantee.
* **Provider capability translation behind an application contract.** The Adapter absorbs Provider
  differences; the product contract stays stable (the foundation Day72 builds on).
* **Model-output validation and the failure taxonomy.** Hallucination/unsupported, contradicted, format,
  truncation, timeout-unknown, and provider-failure classification is how an AI backend refuses to ship
  plausible-but-wrong output.
* **Cost uncertainty, reconciliation, Attempt identity, guarded completion, and rollback/repair boundaries.**
  These are the durable-truth mechanics that make paid, side-effecting Provider calls safe to operate.

The single continuous scenario remains the **multi-tenant AI Research Platform**.

## 13. English Interview

### Key Vocabulary

token · tokenizer · context window · input tokens · reserved output tokens · token budget · truncation ·
chunking · aggregation · provenance · sampling · temperature · top_p · deterministic · reproducible ·
hallucination · unsupported evidence · contradicted evidence · format failure · timeout · reconciliation ·
Job · Attempt · guarded completion · rollback · affected set.

### Useful Expressions

* "A token is a model-specific unit, so token counts are versioned capabilities, not constants."
* "HTTP 200 and a valid schema are necessary, but they do not establish factual correctness."
* "A timeout is unknown, not a proven non-event, so we reconcile instead of blindly retrying."
* "Rollback stops future harm; it never erases prior calls, cost, or Attempt history."

### Beginner Question

Actual Question: What is a context window, and why should an LLM application reserve output tokens?

Student's Verbatim Answer: *"The context window is the limit on the number of tokens for a single model invocation, encompassing input tokens, application instructions, documents, output tokens, and so on.Failure to implement construction production tokens could result in the interruption of production outcomes."*

Language Correction: `construction production tokens` -> **reserve output tokens** (an English wording slip; the rest of the sentence is understandable).

Engineering Concept Correction: reserving output tokens matters because the reserved output competes for the same finite budget — if the application does not reserve enough output space, generation can hit the limit and produce **output truncation or an incomplete result**.

Strong Interview Answer: "The context window is the finite token budget for a single model call. System instructions, user input, documents, request overhead, the reserved output, and a safety margin all compete inside it. We reserve output tokens so the model has room to finish; without that reservation, generation can be truncated and the result is incomplete."

### Intermediate Question

Q: A Provider call timed out after you dispatched it. What state is the Job in and why?

Student's real answer (verbatim): *"At this point, it is unclear whether a provider call was made, an artifact
was generated, or costs were incurred; therefore, the process must enter the pending_reconciliation state."*

Language note: precise phrasing is that the application **attempted/sent** the call; what is unknown is whether
the Provider **received, executed, or completed** it and **incurred cost**.

Strong Answer: "It's `TIMEOUT_UNKNOWN`. We sent the call, but we don't know if the Provider received,
executed, completed, or charged for it. So the Job goes to `PENDING_RECONCILIATION`, we keep the original
Attempt identity and cost uncertainty, and we reconcile using Provider request/status evidence instead of a
blind retry."

### Senior Question

Q: A bad output-budget policy (v2) caused truncation across many Jobs. Contain and repair it.

Common Weak Answer: "Halt all new requests and retry the failed Jobs." (Too broad, and blind retry is unsafe.)

Refinement made in class: stop **new requests that use the faulty v2**; safe **v1** traffic may continue, while
uncertain impact can justify pausing admission.

Strong Answer (the student's correct five-step answer): "Roll back the configuration to stop future harm;
preserve failure evidence; scope the affected set by policy/release version, a bounded time window, and audit
evidence; run per-Job eligibility checks; and issue controlled new Attempts only. No bulk success, no
unconditional retry, no history deletion — each repaired Job gets a new Attempt and the old Attempt keeps its
state."

### Follow-up Questions

* Why is reproducible not the same as deterministic for a managed model?
* Why is a schema-valid answer with a nonexistent citation still a failure, and at which gate is it caught?
* Why can a late, better-worded result not replace an already accepted Artifact?

## 14. Mental Model Summary

```text
Token              = model-specific text unit (versioned, not fixed chars/words/bytes)
Context window     = finite shared budget (system + user + docs + overhead + reserved output + margin)
Reserved output    = capacity, not a promise
Overflow policy    = product decision: TRUNCATE | REJECT | SUMMARIZE(lossy) | CHUNK(evidence-preserving)
Aggregation input  = bounded candidates + evidence excerpts + sources (never raw docs again)
Provider capability= versioned; Provider-independent contract = stable meaning
Adapter            = translate capabilities/failures; NEVER silently weaken the contract
Sampling           = selection behaviour, not factual control
Deterministic      ≠ Reproducible ≠ True
Validation         = transport -> schema -> evidence -> policy -> guarded completion
Timeout            = TIMEOUT_UNKNOWN -> PENDING_RECONCILIATION -> no blind retry
Job                = stable business identity ; Attempt = one execution identity ; new call = new Attempt
Guarded completion = live Job + exact authorized Attempt ; stale/late = zero-effect
Rollback           = stop future harm ; never erase calls/cost/outputs/history
```

## 15. Today's Takeaway

* **Most important mental model:** the application owns the contract and finite budget; the Provider is a
  versioned capability behind an Adapter; a model result is a proposal until layered validation and guarded
  completion make it a fact.
* **Most important production risk:** treating a timeout as a non-event (blind retry) or trusting HTTP 200 +
  schema as correctness — both ship unsafe or wrong results and can double cost.
* **Most important trade-off:** SUMMARIZE vs CHUNK for evidence-critical inputs — choose from the contract, not
  convenience; REJECT beats a silent contract violation.
* **Most important framework connection:** FastAPI owns the request boundary and admission; the Provider
  Adapter translates versioned capabilities without weakening the contract.
* **Most important AI-backend connection:** finite token/context budgeting + failure taxonomy +
  reconciliation + Job/Attempt/guarded completion is what makes paid, side-effecting model calls operable.
* **Most important interview answer:** a timeout is `TIMEOUT_UNKNOWN` -> `PENDING_RECONCILIATION`, never a
  blind retry.

## 16. Before Next Lesson Checklist

- [ ] Can I explain, in plain English, why the application (not the Provider) owns the contract?
- [ ] Can I explain why a token is model-specific and what competes inside the context window?
- [ ] Can I choose TRUNCATE/REJECT/SUMMARIZE/CHUNK from a business contract and defend it?
- [ ] Can I explain why sampling stability does not prove factual correctness, and deterministic vs
      reproducible?
- [ ] Can I list the failure taxonomy and separate a TRUNCATION root cause from a FORMAT_FAILURE symptom?
- [ ] Can I explain why a timeout is `TIMEOUT_UNKNOWN` and leads to `PENDING_RECONCILIATION`?
- [ ] Can I explain Job vs Attempt and why guarded completion refuses a stale/late result?
- [ ] Can I contain a bad policy release without erasing history, in English?

---

Related: [Day71 artifact — LLM Application Runtime foundations](../../projects/ai-agent/docs/DAY71_FOUNDATIONS.md)
· [Day71 classroom draft](../../projects/ai-agent/docs/day71-llm-runtime-foundations-classroom-draft.md)
· [ai-agent project](../../projects/ai-agent/README.md)
· Cheat sheet: [`cheat_sheets/fastapi.md`](../../cheat_sheets/fastapi.md) (Day71)
· Interview: [`interview/fastapi.md`](../../interview/fastapi.md) (Day71)
· Previous: [Day70 lesson](day70-n8n-fastapi-ai-tool-integration-capstone-and-interview.md) (Phase 6 close; PHASE TRANSITION)
· Next: Day72 — Provider Capabilities and the Replaceable Provider Adapter (Planned)
