# Day71 LLM Runtime Foundations — CLASSROOM_DRAFT

> Status: `CLASSROOM_DRAFT`. This file records only concepts reached in the live Day71 class. It is not a
> released lesson, repository fact, or completed Day71 implementation.

## Production Scenario

```text
Multi-tenant AI Research Platform
-> FastAPI accepts a Research Report request
-> LLM Application Runtime builds a bounded Provider request
-> system instruction + user input + input documents + reserved output compete for finite context
-> the Runtime classifies and handles unsafe or incomplete outcomes
```

## Current Architecture Boundary

```text
Business service
-> Provider-independent application contract
-> LLM Application Runtime
   -> token/context budget policy
   -> input transformation policy
   -> sampling policy
   -> validation and failure classification
-> Provider Adapter
-> Provider-specific API
```

- The Runtime owns application policy; the Provider does not decide the product contract.
- The Adapter translates Provider-specific capabilities and failures; it must not silently weaken the
  application contract.
- Provider/model context sizes, tokenization, and parameter support are versioned capabilities, not permanent
  constants.

## Token and Context Budget Model

```text
input tokens
= system instruction
 + user input
 + input documents
 + request/schema overhead

input tokens + reserved output tokens + safety margin <= effective context limit
```

Token is a model-specific text unit, not a fixed character, word, or byte. Output reservation is capacity,
not a promise that the model will use every reserved token.

If the request does not fit, the Runtime applies an explicit product policy:

- `TRUNCATE`: remove content; fast but can destroy meaning or evidence.
- `REJECT`: make no Provider call; honest when the contract cannot be met.
- `SUMMARIZE`: lossy transformation; suitable only when loss of exact evidence is allowed.
- `CHUNK`: process bounded pieces with stable source identity, then reconcile and aggregate.

For evidence-critical research reports, the current classroom decision is to prefer chunking over silent
whole-document summarization.

## Chunk Result Contract (Conceptual)

```text
claim_id
claim
document_id
chunk_id
evidence_excerpt
section / time_scope when relevant
status = CANDIDATE
```

Separate chunk calls do not share unlimited Provider context. Aggregation receives bounded structured
candidates, necessary evidence excerpts, and source references rather than blindly resending every complete
document. Conflicts remain explicit: `RESOLVED | CONFLICT | INSUFFICIENT_EVIDENCE`.

## Sampling Mental Model

- Sampling selects a next token from a probability distribution.
- `temperature` changes how concentrated candidate probabilities are; `top_p` restricts the candidate mass.
- Exact support and semantics are Provider/model-specific.
- Lower sampling variability may improve output stability, but it does not prove factual correctness.
- Deterministic means the same complete conditions necessarily produce the same output. Reproducible means the
  recorded procedure can be rerun and reviewed; it does not guarantee byte-identical managed-model output.

## Failure and Observability Matrix (Current Slice)

| Classification | Meaning | May complete Job? | Current handling boundary |
|---|---|---:|---|
| `HALLUCINATION_OR_UNSUPPORTED_EVIDENCE` | Plausible claim or citation is unsupported/contradicted | No | Preserve source identity; reject or reconcile |
| `FORMAT_FAILURE` | Output violates the application schema/format | No | Validation gate blocks success |
| `TRUNCATION` | Generation ended before the required result was complete | No | Inspect completion reason and budget |
| `TIMEOUT_UNKNOWN` | Runtime did not receive a complete result before its deadline | No | Do not infer non-execution or blind retry |
| `PROVIDER_FAILURE` | Classified auth/rate-limit/capability/service/transport failure | No | Adapter maps to an application-owned outcome |

HTTP success and schema validity are necessary at some boundaries but do not establish factual correctness.
Structured model output remains untrusted until application validation and evidence checks pass.

## Request / Response Lifecycle (Current Slice)

```text
application request
-> token/context admission
-> Provider-independent request contract
-> Provider Adapter call
-> translated Provider outcome
-> format/schema validation
-> evidence/semantic validation
-> application-policy validation
-> guarded completion OR classified non-success
```

Validation is layered. A result may pass transport and schema gates but fail the evidence gate. A citation
that exists but contradicts its claim is `CONTRADICTED_EVIDENCE`, not a successful research result.

## Recovery Decision Boundary

| Situation | Execution certainty | Decision |
|---|---|---|
| Context overflow detected before call | Definitely not called | Transform input under policy or reject |
| Output budget ends and JSON is incomplete | Call ended; result incomplete | Primary `TRUNCATION`, derived `FORMAT_FAILURE`; adjust policy before a new call |
| Schema-valid output has unsupported evidence | Result received but invalid | Reject result; do not mark the Job succeeded |
| Runtime timeout after dispatch | Unknown | `PENDING_RECONCILIATION`; no blind retry |
| Required Provider capability is unavailable | Definitely cannot meet contract | Preserve contract; return capability failure or use an explicitly authorized alternative |

Reconciliation is evidence gathering, not a delayed retry. It preserves the original Attempt identity and
cost uncertainty, uses Provider-specific evidence through the Adapter when available, and sends any late
result through the same validation gates. A schema-valid late result with unsupported evidence is
`COMPLETED_INVALID`; lateness never weakens the application contract.

## Failure Rollback and Attempt Identity

Configuration rollback stops future requests from using a bad policy version; it does not undo completed
Provider calls, cost, outputs, or durable history. An affected set is bounded by policy/release version, time
window, and recorded failure evidence before per-Job repair decisions are made.

```text
job_id = stable business task identity
attempt_id = one concrete execution identity
new Provider call = new Attempt
```

Example after a bad output-budget policy is rolled back:

```text
Job job-100: SUCCEEDED
├── Attempt A1: TRUNCATED  (bad budget policy; historical fact retained)
└── Attempt A2: SUCCEEDED  (new authorized call; all validation gates passed)
```

An old Attempt is never overwritten or deleted to make the Job history look clean. A new Attempt is allowed
only after current deadline, budget, input contract, cancellation state, execution evidence, and guarded
claim checks permit another external call.

## Guarded Completion

A validated model result still has no automatic authority to change durable business state. Completion is
allowed only when the Job is live and the result belongs to the currently authorized Attempt. A stale or
late result receives a zero-effect refusal and cannot replace an existing Result Artifact merely because a
human thinks its prose is better.

```text
Job job-100 current Attempt: A2
late result Attempt:          A1
-> STALE_LATE_RESULT
-> preserve safe evidence
-> no Job status, Artifact, success Event, or cost-history overwrite
```

## Integrated Chunk Failure Scenario

```text
chunk-1 -> valid candidate
chunk-2 -> TIMEOUT_UNKNOWN
chunk-3 -> valid candidate
```

The Runtime must not ignore chunk-2 and claim a complete report. It retains the valid candidates, keeps the
Job `PENDING_RECONCILIATION`, reconciles the exact chunk-2 Attempt, and aggregates only after the application
contract's evidence-completeness rule is satisfied.

## Final Engineering Mental Model

```text
Business request
-> Provider-independent application contract
-> LLM Application Runtime
   -> calculate model-specific tokens and finite context budget
   -> reserve output capacity and safety margin
   -> apply explicit reject / summarize / chunk policy
   -> bind a versioned sampling policy
-> Provider Adapter translates current Provider-specific capabilities
-> one authorized Provider call belongs to one Attempt
-> translated outcome passes transport, schema, evidence, and application-policy gates
-> guarded completion may write the Result Artifact and move the stable Job to SUCCEEDED
```

Sampling changes token-selection behavior; it does not establish factual correctness. HTTP success and
schema validity do not establish evidence support. A timeout is `TIMEOUT_UNKNOWN`, not proof of
non-execution or zero cost, so the Job enters `PENDING_RECONCILIATION` and the original Attempt is retained.
A new Provider call requires a new Attempt. Configuration rollback stops future harm but never erases prior
calls, cost, outputs, or failure history.

> Classroom-authorship note: the student explicitly asked the Tech Lead to provide the final Chinese Mental
> Model (`你帮我总结吧`). This section is taught material based on the completed classroom reasoning, not an
> independently authored student answer.

## Validation Status

| Tier | Status | Evidence |
|---|---|---|
| `CONCEPTUAL` | Reviewed in class so far | Architecture, budgets, chunking, sampling, failure taxonomy |
| `STATIC` | `PASS` | File/required-section checks, balanced fenced blocks, trailing-whitespace scan and credential-pattern scan |
| `EXECUTED_LOCAL_RUNTIME` | `NOT RUN` | No code or tests yet |
| `INTEGRATION_RUNTIME` | `NOT RUN` | No Provider or external process used |
| `PRODUCTION` | `NOT RUN` | No production evidence |
