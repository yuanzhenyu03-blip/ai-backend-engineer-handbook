# Day71 — LLM Application Runtime Foundations (Phase 7A)

Provider-independent design foundations for the Phase 7A LLM Application Runtime. This is the **released
static contract** distilled from the Day71 classroom process; the raw session notes live in
[`day71-llm-runtime-foundations-classroom-draft.md`](day71-llm-runtime-foundations-classroom-draft.md).

> Evidence tier — Day71 is **CONCEPTUAL + STATIC only**. This document is provider-independent design; there
> is **no runtime code, no test suite, and no Provider call**. `EXECUTED_LOCAL_RUNTIME`,
> `INTEGRATION_RUNTIME` and `PRODUCTION` are **NOT RUN**. Any Provider token count, context size, or sampling
> behaviour named here is a **versioned current capability**, never a permanent fact. Runtime code begins in
> later Phase 7A days (Day72+); this lesson deliberately does not add it.

## Scope

This is the same cumulative `projects/ai-agent/` Artifact that Phase 7A (Day71–Day78) evolves. Day71
establishes the foundations only. It does **not** implement the Day72 replaceable Provider Adapter, Day73
prompt versioning, Day74 tool calling, Day75 caching/batching, Day76 routing, Day77 regression suite, or the
Day78 capstone.

## 1. Architecture Boundary

```text
Business service (FastAPI request boundary)
-> Provider-independent application contract      (application owns MEANING)
-> LLM Application Runtime
   -> token/context budget policy
   -> input transformation policy
   -> sampling policy (versioned)
   -> layered validation + failure classification
-> Provider Adapter                               (translates VERSIONED capabilities/failures)
-> Provider-specific API
```

Rules:

- The Runtime owns application policy; the Provider does not decide the product contract.
- The Adapter translates Provider-specific capabilities and failures and must **never silently weaken** the
  application contract (`research_claims.v1`).
- Provider/model context sizes, tokenization, and parameter support are **versioned capabilities, not
  permanent constants**.

## 2. Token and Context Budget Contract

```text
input tokens = system instruction + user input + input documents + request/schema overhead

input tokens + reserved output tokens + safety margin <= effective context limit
```

- A token is a **model-specific** text unit — not a fixed character, word, or byte.
- Reserved output tokens are **capacity, not a promise** the model uses them all.
- Admission is checked **before** a paid call.

## 3. Context-Overflow Policy

```text
TRUNCATE   remove content; fast, can destroy meaning/evidence
REJECT     make no Provider call when the contract cannot be met
SUMMARIZE  lossy transformation; only when loss of exact evidence is acceptable
CHUNK      bounded pieces with stable document/chunk identity, then reconcile + aggregate
```

The policy is a **product decision** derived from the business contract. For evidence-critical reports with
required exact citations, prefer `CHUNK`; reserve `REJECT` for requests no transformation can satisfy.

## 4. Chunk Candidate and Aggregation Contract

```text
candidate = { claim_id, claim, document_id, chunk_id, evidence_excerpt, section/time_scope?, status=CANDIDATE }
```

- Overflow chunks normally mean **separate Provider calls with independent finite contexts**.
- Aggregation receives **bounded candidates + necessary evidence excerpts + source references** — never every
  complete document again.
- Aggregation outcome ∈ `{ RESOLVED, CONFLICT, INSUFFICIENT_EVIDENCE }`. Conflicting claims retain provenance
  and enter reconciliation; they are never concatenated as fact.

## 5. Provider-Independent Contract vs Provider-Specific Capability

```text
Provider-specific (VERSIONED): context limit · native structured-output support · sampling params · finish/error evidence
Provider-independent (STABLE): application request/result/failure MEANING
```

If a Provider cannot meet the required contract: validate through an **explicitly supported path** or return
`PROVIDER_CAPABILITY_ERROR`. Never silently accept ordinary text as structured output.

## 6. Sampling Policy

- Sampling selects a next token from a **probability distribution**.
- `temperature` concentrates/relaxes candidate probabilities; `top_p` restricts the candidate mass.
- Exact semantics/support are **Provider/model-specific**.
- Sampling controls **selection behaviour, not factual correctness**.
- **Deterministic** = identical complete conditions necessarily produce the same output. **Reproducible** =
  the recorded procedure can be rerun/reviewed; it does **not** guarantee byte-identical managed-model output.
  A Provider seed may improve repeatability but is not a universal, permanent guarantee.

## 7. Layered Validation and Failure Taxonomy

```text
transport gate -> format/schema gate -> evidence/semantic gate -> application-policy gate -> guarded completion
```

| Classification | Meaning | May complete Job? | Handling boundary |
|---|---|---:|---|
| `HALLUCINATION_OR_UNSUPPORTED_EVIDENCE` | Plausible claim/citation is unsupported | No | Preserve source identity; reject or reconcile |
| `CONTRADICTED_EVIDENCE` | Citation exists but contradicts the claim | No | Evidence gate blocks success |
| `FORMAT_FAILURE` | Output violates application schema/format | No | Schema gate blocks success |
| `TRUNCATION` | Output ended before the required result was complete | No | Inspect finish reason + output budget |
| `TIMEOUT_UNKNOWN` | No complete result before the deadline; execution/cost unknown | No | No blind retry; reconcile |
| `PROVIDER_FAILURE` | Adapter-classified auth/rate-limit/capability/service/transport failure | No | Adapter maps to an application-owned outcome |

HTTP 200 and schema validity do **not** establish factual correctness. **Root cause vs symptom**:
output-budget exhaustion is the primary `TRUNCATION`; the incomplete JSON is a derived `FORMAT_FAILURE`.

## 8. Recovery Decision Boundary

| Situation | Execution certainty | Decision |
|---|---|---|
| Overflow detected before call | Not called | Transform under policy or reject |
| Output budget ends, JSON incomplete | Call ended; incomplete | Primary `TRUNCATION`, derived `FORMAT_FAILURE`; adjust policy before a new call |
| Schema-valid output, unsupported evidence | Received but invalid | Reject; do not mark the Job succeeded |
| Runtime timeout after dispatch | Unknown | `PENDING_RECONCILIATION`; no blind retry |
| Required Provider capability unavailable | Cannot meet contract | Preserve contract; capability error or explicitly authorized alternative |

- `retry` = a NEW external execution; `reject` = refuse this execution/result; `reconciliation` = gather
  evidence for an UNKNOWN outcome.
- Reconciliation preserves the original Attempt identity and cost uncertainty and uses Provider request/status
  evidence through the Adapter. A late result passes the **same** gates; a schema-valid late result with
  unsupported evidence is `COMPLETED_INVALID`.

## 9. Job, Attempt, Guarded Completion, and Rollback

```text
job_id     = stable business-task identity
attempt_id = one concrete execution identity
new Provider call = NEW Attempt   (old Attempts never overwritten or deleted)
```

- A new Attempt requires current deadline, budget, input contract, cancellation state, execution evidence, and
  guarded-claim permission.
- **Guarded completion**: a validated result changes durable state only when the Job is live and the result
  belongs to the currently authorized Attempt. A stale/late result gets a **zero-effect refusal**.
- **Rollback** stops future harm; it never undoes Provider calls, cost, outputs, or durable history. Scope the
  affected set by policy/release version + bounded time window + failure evidence before per-Job repair.

```text
Job job-100: SUCCEEDED
├── Attempt A1: TRUNCATED  (bad budget policy; historical fact retained)
└── Attempt A2: SUCCEEDED  (new authorized call; all gates passed)
```

## 10. Validation Status

| Tier | Status | Evidence |
|---|---|---|
| `CONCEPTUAL` | Completed | Architecture, budgets, chunking, sampling, failure taxonomy, lifecycle, reconciliation, rollback, guarded completion |
| `STATIC` | `PASS` | Required-section checks, balanced fenced blocks, trailing-whitespace scan, credential-pattern scan |
| `EXECUTED_LOCAL_RUNTIME` | `NOT RUN` | No code or tests in Day71 |
| `INTEGRATION_RUNTIME` | `NOT RUN` | No Provider or external process used |
| `PRODUCTION` | `NOT RUN` | No production evidence; no real or paid Provider call |

## Related

- Lesson: [`docs/fastapi/day71-llm-application-architecture-tokens-context-sampling-and-model-failure-modes.md`](../../../docs/fastapi/day71-llm-application-architecture-tokens-context-sampling-and-model-failure-modes.md)
- Classroom draft: [`day71-llm-runtime-foundations-classroom-draft.md`](day71-llm-runtime-foundations-classroom-draft.md)
- Project: [`../README.md`](../README.md)
- Next: Day72 — Provider Capabilities and the Replaceable Provider Adapter (Planned)
