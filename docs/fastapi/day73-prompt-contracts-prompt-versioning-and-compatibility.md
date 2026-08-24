# Day73 — Prompt Contracts, Prompt Versioning and Compatibility

## 1. Lesson Metadata

```text
Status:        ✅ Completed (classroom scope) — CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME (39 deterministic in-process tests). INTEGRATION_RUNTIME and PRODUCTION are NOT RUN; no real or paid Provider call, no SDK, no HTTP, no database.
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 5-6 hours
Prerequisite:  Day72 (replaceable Provider Adapter + versioned capability admission) · Day71 (provider-independent LLM Application Runtime) · Day53 (Provider boundary, structured output, untrusted success) · Day54 (Attempt lifecycle, timeout-unknown, late-result identity binding)
Previous Lesson: Day72 — Provider Capabilities and the Replaceable Provider Adapter (DIRECT PREREQUISITE)
Next Lesson:   Day74 — Structured Output, JSON Schema and Function/Tool Calling
Engineering Artifact: projects/ai-agent/ (Phase 7A — src/prompt_contracts.py + tests/test_prompt_contracts.py + docs/DAY73_PROMPT_CONTRACTS.md + classroom draft)
```

Day72 made the Provider **replaceable**: an already-admitted internal request is translated to a
provider-specific call behind a stable `ProviderAdapter`, and capability admission runs before an invalid
paid call. Day73 answers an **earlier** question — one that must be settled *before* any adapter or Provider
capability admission runs:

> Which exact prompt behaviour was authorized for **this** Attempt, can the Runtime reproduce it
> deterministically, and is it compatible — before any adapter or Provider call?

The answer is the **Prompt Contract**: an application-owned, versioned execution contract. Not a mutable
string, and not a Provider Adapter capability declaration.

> Evidence honesty — Day73 spans three tiers and stops there:
>
> * `CONCEPTUAL` — completed in class: prompt-as-contract, immutable revisions + lifecycle overlay, durable
>   Attempt binding, deterministic rendering + audit hash, directional (backward/forward) compatibility,
>   pre-Provider Runtime enforcement, responsibility boundaries, disable/rollback/migration/re-release, and
>   the production failure/recovery exercise.
> * `STATIC` — `PASS`: `python3 -m py_compile` on the module and tests; required doc sections present; fenced
>   blocks balanced; trailing-whitespace and credential-pattern scans clean.
> * `EXECUTED_LOCAL_RUNTIME` — `PASS`: `python3 -m unittest discover -s tests -v` → **39 deterministic
>   Day73 in-process tests OK** (Python 3.11.5), and the Day72 regression suite still passes (58 tests; 97
>   total). Tests use in-memory stores and pure functions only. The `provider_calls` counter models crossing
>   the in-process Runtime gate toward the Provider boundary — it is **not** proof of a Provider Adapter, SDK,
>   HTTP, network, database, or external call.
> * `INTEGRATION_RUNTIME` — **NOT RUN**: no real SDK, HTTP, Provider, database-backed Attempt/lifecycle store,
>   queue, worker, callback, encryption/KMS, or protected-artifact storage.
> * `PRODUCTION` — **NOT RUN**: no credentials, customer data, sensitive prompt, or production traffic.
>
> Day72's existing repository tests are **prerequisite evidence only** and are not Day73 validation. The full
> Fake Provider contract and LLM regression suite remain **Day77** scope.

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* **Explain** why a prompt must be an application-owned, versioned execution contract rather than a mutable
  string edited in place, and why that is different from a Provider capability declaration.
* **Design** an immutable `PromptContractRevision` (ordered message templates + roles, required/optional
  variables, input schema, semantic guarantees, compatible application contracts, renderer version) with a
  separate lifecycle overlay.
* **Implement** a durable per-Attempt prompt binding and a pre-Provider LLM Runtime gate that fails closed on
  a binding mismatch, a disabled bound revision, an unknown revision, incompatible contract, invalid
  variables, an input-fingerprint mismatch, or a rendered-hash mismatch — each with **zero** Provider calls.
* **Diagnose** backward vs forward compatibility as both a **structural** and a **semantic**, **directional**
  property; distinguish a safe optional-variable-with-default from a breaking rename or a weakened guarantee.
* **Apply** the four incident verbs — **disable**, **rollback**, **migration**, **re-release** — to a bad
  revision without rewriting history.
* **Defend** the responsibility split among business authorization, LLM Runtime, Model Parameter Policy,
  Provider Adapter, and output validation.
* **Answer in English** at beginner, intermediate, and senior levels about prompt contracts and versioning.

## 3. Why This Matters

A team ships a "small prompt tweak": the system message changes *"citations are required"* to *"citations are
optional."* No code changed, no schema changed, no variable changed. Yet every research report produced after
that deploy silently lost an application guarantee customers relied on. Worse, some Attempts were dispatched
under the old rule, some under the new one, and a few timed out and returned *later* — which rule interprets
those?

If a prompt is "just a string" that the latest deploy overwrites, you cannot answer any of the questions a
production incident demands: *Which behaviour did Attempt A1 actually run? Can we reproduce it byte-for-byte
for an audit? Was the change compatible? Which Attempts are affected, and how do we repair them without
inventing results or deleting evidence?*

The production risks are concrete: **silent guarantee loss** (a semantic break with no structural signal),
**non-reproducibility** (you cannot re-derive what was sent), **history rewrite** (overwriting a binding
destroys audit truth), **compatibility surprises** (a rename that "means the same thing" breaks existing
callers), and **unsafe recovery** (blindly retrying timeout-unknown Attempts or letting a stale late response
overwrite authoritative state). Prompt contracts and versioning are the discipline that makes an LLM
application auditable, reproducible, and safely reversible.

## 4. Roadmap Position

```text
Day72 — Replaceable Provider Adapter (versioned capability admission before a paid call)
        |
        v
Day73 — Prompt Contract (application-owned versioned execution contract + immutable Attempt binding)
        |
        v
Day74 — Structured Output, JSON Schema, Function/Tool Calling (constrain and validate the OUTPUT)
```

Day72 stabilized the **provider surface**. Day73 versions the **input behaviour** and pins it to each
Attempt *before* dispatch. Day74 will constrain the **output** with schema and tool calls — preserving the
rule that transport `SUCCESS` is never sufficient for a trusted business result.

### Knowledge Continuity

```text
Previous Knowledge
  - Day53: Provider boundary, structured output, Provider SUCCESS is an untrusted candidate
  - Day54: Job vs Attempt, timeout-unknown -> PENDING_RECONCILIATION, late-result identity binding
  - Day71: provider-independent Runtime; validation is layered (transport -> schema -> evidence -> policy)
  - Day72: immutable per-Attempt execution contract, lifecycle overlay, fail-closed Registry, guarded CAS
        |
        v
Current Lesson Concept
  - The prompt is an application-owned, versioned execution contract
  - Each Attempt durably binds the revision + renderer + parameter policy + fingerprint + rendered hash
  - The LLM Runtime enforces lifecycle/variables/compatibility/rendering BEFORE any Provider call
        |
        v
Future Production Usage
  - Day74 structured output + JSON Schema + tool calling on this versioned input boundary
  - Day76 routing/fallback still binds the authorized prompt revision per Attempt
  - Day77 fake-Provider contract + regression tests pin prompt-contract behaviour deterministically
```

Mental models reused by name: the Day72 **immutable revision + lifecycle overlay**, the Day72 **authoritative
Attempt binding + guarded compare-and-set**, the Day72 **fail-closed `UNKNOWN` status**, the Day54 **Attempt
identity binding for late results**, and the Day53/Day71 **untrusted-success** principle.

## 5. Lesson Map

```text
Business authorization (may the tenant/user do this at all?)
  -> LLM Runtime loads the Attempt's authoritative immutable prompt binding
  -> validate prompt lifecycle (ACTIVE?) + variables + application compatibility
  -> deterministic render + verify rendered hash (reproduce the exact request)
  -> [only now] Provider capability admission (Day72)
  -> Provider Adapter translation + dispatch (Day72)
  -> returned output = untrusted candidate -> schema -> evidence -> policy -> guarded completion (Day74+)
```

## 6. Core Mental Model

```text
Prompt Contract      = application-owned, versioned execution contract (immutable revisions)
Revision             = one immutable published behaviour fact (messages + roles + variables + guarantees + renderer)
Lifecycle overlay    = ACTIVE / DISABLED / QUARANTINED / UNKNOWN (separate from the immutable revision)
Attempt binding      = { prompt_contract_id + revision, renderer_version, parameter_policy_id+revision,
                         application_contract, input_fingerprint, rendered_message_hash, [artifact_ref] }
Current default       = selects a revision for a NEW Attempt only — never reinterprets an existing one
Runtime gate          = fail-closed pre-Provider check; each failure = zero Provider calls
Compatibility         = directional (backward / forward) AND structural + semantic
```

The one-line version: **a prompt is a versioned contract bound immutably to each Attempt; the current default
governs only new planning; everything is validated and reproduced before any Provider call.**

## 7. Main Concepts

### Concept 1: The prompt is a versioned execution contract, not a string

#### Tech Lead Question

If Attempt A1 was planned when the default prompt was `v1`, and the team later makes `v2` the default, which
revision should interpret A1?

#### Student Thinking

The student had internalized the Day72 rule that an Attempt binds its execution config immutably, and applied
the same reasoning here rather than reaching for "whatever is current."

#### Student Answer (verbatim)

> `A1 应该使用它规划时绑定的 v1`

#### Tech Lead Review

Correct. The **current default only affects new planning**. A1 durably bound `v1` at plan time; that binding
is an immutable historical execution fact. Reinterpreting A1 with `v2` would rewrite history and destroy
auditability. In the artifact, `PromptContractRegistry.select_default_for_new_attempt(...)` is used **only**
when planning a new Attempt; `prepare_dispatch(...)` reads the **authoritative** binding from the store and
resolves the revision the Attempt was bound to — never the default.

#### Engineering Thinking

A prompt string edited in place has no identity, no history, and no reproducibility. Making it a versioned
contract gives every Attempt a stable answer to "what exactly ran," which is the precondition for audit,
incident scoping, and safe rollback.

#### Production Example

An audit asks you to reproduce a report generated three weeks ago. With immutable revisions + Attempt
bindings you re-resolve `v1`, re-render from the persisted input fingerprint, and confirm the
`rendered_message_hash` matches. With a mutable string, the original prompt is simply gone.

#### Framework Connection

Mirrors Day72's `AttemptExecutionContract` and `CapabilityProfile` immutability, and Alembic-style
"never edit a published migration; add a new revision" discipline.

### Concept 2: Immutable revision + separate lifecycle overlay

#### Tech Lead Question

A `v2` revision turned out to weaken a guarantee. Do you edit `v2` to fix it?

#### Student Answer (verbatim, from the incident exercise)

> `disable v2 并把新任务默认选择 rollback 到 v1`

#### Tech Lead Review

Right. You never edit a published revision in place. Operational status lives in a **separate lifecycle
overlay** (`ACTIVE` / `DISABLED` / `QUARANTINED`), so disabling `v2` stops it from **new** dispatch without
altering or deleting its historical definition. The published `v2` remains an audit fact; the fix is a **new**
immutable `v3`.

#### Engineering Thinking

Separating "what the revision is" (immutable) from "may we use it now" (mutable overlay) is what lets you
respond to an incident instantly (flip status) while preserving the evidence trail. It is the exact pattern
from Day72's `ProfileLifecycle`.

#### Production Example

`v2` is quarantined at 14:02; new Attempts plan `v1` again by 14:03; already-planned `v2` Attempts are
blocked before dispatch; `v3` is published and rolled out under monitoring the next day.

### Concept 3: The durable Attempt binding — reproducibility needs more than the renderer

#### Tech Lead Question

To reproduce exactly what was sent, is the renderer version enough?

#### Student Answer (verbatim)

> `不能，还应该绑定Renderer version`

#### Tech Lead Review

The student correctly named `renderer_version` — necessary but **incomplete**. Reliable reproduction also
needs the **prompt revision**, the **parameter-policy revision**, the **application contract**, a **canonical
input fingerprint**, the **rendered-message hash**, and — only when policy permits — a **protected rendered
artifact**. The artifact's `AttemptPromptBinding` records all of these; `plan_attempt_binding(...)` computes
the fingerprint and hash at plan time.

#### Engineering Thinking

Each field closes a reproduction gap: the revision fixes the templates/guarantees; the renderer fixes *how*
variables become text; the parameter policy fixes temperature/limits (versioned **independently**, not hidden
in the prompt); the fingerprint fixes the inputs; the hash proves the exact bytes.

#### Production Example

Two Attempts with identical topics but different `tone` defaults produce different fingerprints and hashes —
so a "why did these differ?" investigation is answerable from evidence alone.

### Concept 4: The pre-Provider Runtime gate (and who owns it)

#### Tech Lead Question

Who checks prompt compatibility and lifecycle before the Provider call, and why must it happen *before* the
Provider?

#### Student Answer (verbatim)

> `应该由 LLM Runtime`
>
> `没有这个边界会产生无效调用provider，应该由LLM runtime检查阻止，并在provider之前`

#### Tech Lead Review

Correct and well-motivated. Without a pre-Provider gate you pay for **invalid** Provider calls and you may run
a **disabled** or **incompatible** prompt. The **LLM Runtime** owns prompt selection, immutable binding,
lifecycle enforcement, variable/schema validation, compatibility checks, deterministic rendering, binding
verification, and guarded state transitions. Business authorization is a **separate, earlier** owner.

#### Engineering Thinking

`prepare_dispatch(...)` gates in order: authoritative-binding match → revision resolved → lifecycle ACTIVE →
contract compatible → variables valid → rendered-hash verified → guarded `PLANNED -> DISPATCHED`. Any failure
returns a classification with `provider_calls=0`.

#### Production Example

A caller replays an old dispatch payload naming `v1` for an Attempt whose authoritative binding is `v2`. The
gate returns `BINDING_MISMATCH`, the Attempt stays `PLANNED`, and **zero** Provider calls occur.

### Concept 5: Compatibility is directional, structural AND semantic

#### Tech Lead Question

Is renaming the variable `evidence` to `sources` backward compatible? Is changing "citations required" to
"optional" compatible if the schema is unchanged?

#### Student Answer (verbatim)

> (rename) initially answered compatible "because the meanings are similar"; corrected to `应该拒绝`
>
> (guarantee change) `团队把系统规则从"必须引用证据"改成"引用证据是可选的`; a weakening — not compatible
>
> `是，不是` (backward compatible is achievable for some changes; this one is not)

#### Tech Lead Review

Compatibility is **not** based on human semantic resemblance of names. Existing callers send **field names and
structures**; without an explicit **alias or migration**, renaming `evidence` → `sources` is a **structural**
break. And dropping a **semantic guarantee** (`citations_required`) is a **semantic** break even if variables
and schema are byte-identical. The artifact's `backward_incompatibilities(old, new)` reports both: a removed
required variable *and* a dropped guarantee.

#### Engineering Thinking

Backward compatibility = a newer revision accepts valid **older** inputs and preserves the guarantees old
callers relied on. Forward compatibility = an older runtime safely handles data/metadata produced by a
**newer** version (usually by safely handling or **rejecting** unknown fields — never silently accepting
them).

#### Production Example

Adding an optional `tone` with a deterministic `neutral` default is backward compatible (old inputs still
render). Renaming a required field is not. Weakening a guarantee is not.

### Concept 6: Migration is explicit, non-mutating, auditable — and fails closed on conflict

#### Tech Lead Question

If both the old alias `evidence` and the new `sources` are present with different values, what happens?

#### Student Answer (verbatim)

> `应该拒绝`

#### Tech Lead Review

Correct. `apply_migration(raw, {"evidence": "sources"})` collapses agreeing values but raises
`AliasConflictError` when the alias and its replacement **disagree** — never silently picking a winner.
Migration records source→target and produces a **new** normalized input; it does not rewrite an old Attempt.
An **unknown** `tenant_policy` value must **fail closed** (rejected by enum validation), never fall back to a
permissive default.

#### Engineering Thinking

A migration is a new execution fact, not a mutation of history. Failing closed on conflicting or unknown
inputs is the security-relevant default: ambiguity must never resolve toward "more permissive."

### Concept 7: Boundaries — Prompt Contract vs Parameter Policy vs Provider vs authorization

#### Tech Lead Question

Should the Prompt Contract also record temperature and max tokens? Can a prompt variable authorize a tenant?

#### Student Answer (verbatim)

> `不需要，应该由Model Parameter Policy记录`
>
> `不能，应该由应用业务授权逻辑阻止`

#### Tech Lead Review

Both correct. **Model execution parameters** (temperature, token limits) are owned by a **versioned Model
Parameter Policy**, bound **independently** in the Attempt — not hidden inside the Prompt Contract.
**Authorization** belongs to **application business logic**; a prompt variable is **never** authorization
evidence. The Provider **Adapter** owns provider-specific translation/error-normalization and must **not**
choose or rewrite the prompt revision. **Output validation** decides whether a transport `SUCCESS` is a
trusted business result.

#### Engineering Thinking

Collapsing these concerns creates hidden coupling: a "prompt change" that silently alters sampling, or an
"authorization" that a caller can spoof through a template variable. Separate ownership keeps each concern
independently versioned, testable, and auditable.

### Concept 8: Audit evidence — hash is integrity, a ref is a pointer

#### Tech Lead Question

Should normal logs store the full rendered prompt? Is a `rendered_artifact_ref` enough to read it?

#### Student Answer (verbatim)

> `不能，rendered_artifact_ref指向受保护的artifact`

#### Tech Lead Review

Correct. Normal logs carry only **minimal** operational evidence: ids/revisions, lifecycle decision, input
fingerprint, rendered-message hash, dispatch/outcome ids, state transition and failure classification. A full
rendered prompt may contain sensitive data; if retained it goes to a **protected artifact** with encryption,
tenant-aware authorization, access auditing, and **finite retention**. A **hash is integrity evidence, not
encryption**; a `rendered_artifact_ref` is **only a pointer** — it is not authorization by itself.

### Concept 9: Immutable-history failure semantics

#### Tech Lead Question

Dispatch says `v2` but the Attempt Store binding says `v1`. And separately: the Attempt is bound to `v2` but
`v2` is now disabled. What are the outcomes and the Provider call counts?

#### Student Answer (verbatim)

> `以 Attempt Store 中的 v1 为准，A1 状态为blaocked  Provider 调用次数为0` *(sic — "blocked")*
>
> `阻止 A1`
>
> `A1 绑定的 v2 来解释这个响应，不能` (a late response is interpreted with the Attempt's bound revision)

#### Tech Lead Review

The **authoritative** store binding wins. On a dispatch-vs-binding mismatch the payload is **rejected before**
a valid lifecycle transition — the authoritative Attempt stays **`PLANNED`**, `provider_calls=0`. This is a
`BINDING_MISMATCH`, **not** `BLOCKED_PROMPT_DISABLED` — a subtle correction below. When the **bound** revision
itself is disabled, the Attempt is a guarded `PLANNED -> BLOCKED_PROMPT_DISABLED` with `provider_calls=0`. A
valid **late** response is interpreted with the revision the Attempt is **bound** to, never the current
default; a stale/terminal/superseded response must not overwrite authoritative state.

## 8. Common Misconceptions

```text
Renaming a field is "compatible if the meaning is similar"

❌ evidence -> sources is fine because both mean "supporting material".
✅ Compatibility is structural + semantic, not human resemblance. Existing callers send the field NAME;
   without an alias/migration the rename is a structural break, and a dropped guarantee is a semantic break.

Why beginners think this: names read like synonyms, so the change "feels" safe.
How to remember: callers send bytes and rely on guarantees, not on what a name evokes.
```

```text
A binding mismatch means the Attempt is "blocked"

❌ If dispatch says v2 but the store says v1, mark the Attempt BLOCKED.
✅ A dispatch-payload mismatch is REJECTED before any valid lifecycle transition: the authoritative Attempt
   stays PLANNED with zero Provider calls (BINDING_MISMATCH). BLOCKED_PROMPT_DISABLED is only for when the
   authoritative BOUND revision is itself disabled/quarantined.

Why beginners think this: both feel like "stop it," so they collapse two distinct states.
How to remember: mismatch = "not a valid transition at all" (stay PLANNED); disabled-bound = "valid Attempt,
blocked revision" (transition to BLOCKED).
```

```text
The renderer version is enough to reproduce a prompt

❌ Store renderer_version and you can reproduce the request.
✅ You also need the prompt revision, parameter-policy revision, application contract, canonical input
   fingerprint, rendered-message hash, and (policy permitting) a protected rendered artifact.

Why beginners think this: the renderer turns variables into text, so it feels central.
How to remember: reproduction = same revision + same renderer + same params + same inputs + proof (hash).
```

```text
A Prompt Contract should track model parameters and provider features

❌ Put temperature and provider capabilities inside the Prompt Contract.
✅ Prompt Contracts are application-owned behavioural contracts. Model parameters are a separately versioned
   Model Parameter Policy; provider capabilities are the Day72 Adapter's concern.

Why beginners think this: "it's all one API call," so everything lands in one object.
How to remember: prompt behaviour, sampling parameters, and provider capability are three owners.
```

## 9. Engineering Trade-offs

```text
Immutable revisions + lifecycle overlay vs a single mutable prompt string

Immutable + overlay:
- Full audit history and byte-level reproducibility
- Instant incident response (flip status) without deleting evidence
- More moving parts: revision ids, defaults, a lifecycle store

Mutable string:
- Trivial to change
- No history, no reproducibility, no safe rollback; incidents are unrecoverable

When to choose the alternative: a throwaway prototype with no audit/compliance needs. Never in production
with real customers.
```

```text
Bind the prompt per Attempt vs resolve the current default at dispatch

Per-Attempt binding:
- History is stable; late results and audits are answerable
- Requires a durable binding store and guarded transitions

Resolve-at-dispatch:
- Simpler; "always latest"
- Rewrites history on every deploy; a timed-out Attempt's later response has no stable revision to interpret it
```

```text
Store full rendered prompts vs store only hashes + minimal evidence

Full prompts:
- Perfect forensic detail
- Sensitive-data exposure; needs encryption, tenant-aware authz, access audit, finite retention

Hashes + minimal evidence:
- Integrity proof with far lower exposure
- Cannot read the exact text later unless a protected artifact was also retained under policy

A Tech Lead reviews: is the retention justified, protected, and time-bounded?
```

## 10. Hands-on Exercises

### Exercise 1: Historical binding beats the current default

Question: A1 bound `v1`; `v2` becomes the default. Show that a new Attempt selects `v2` while A1 still gates
on `v1`.

Think First: which call is "new planning" and which is "already planned"?

Starter Artifact: `select_default_for_new_attempt(...)` vs `prepare_dispatch(...)`.

Expected Output: new Attempt → `v2`; A1 gate → `READY` on `v1`.

Explanation: the default governs new planning only; the store binding is authoritative.

Follow-up: what interprets A1's late response — `v1` or `v2`?

### Exercise 2: Binding mismatch makes zero Provider calls

Question: forge a `v1` dispatch payload for an Attempt bound to `v2`. Assert `BINDING_MISMATCH`,
`provider_calls == 0`, state still `PLANNED`.

### Exercise 3: Disabled bound revision blocks with zero calls

Question: disable the bound `v2`, dispatch, assert `BLOCKED_PROMPT_DISABLED`, `provider_calls == 0`.

### Exercise 4: Compatibility classification

Question: for (a) add optional `tone` default, (b) rename `evidence`→`sources`, (c) drop
`citations_required` — classify each with `backward_incompatibilities(old, new)`.

Expected Output: (a) `[]`; (b) structural break reason; (c) semantic break reason.

### Exercise 5: Alias conflict fails closed

Question: `apply_migration({"evidence":"a","sources":"b"}, {"evidence":"sources"})` must raise
`AliasConflictError`.

### Exercise 6 (design): Semantic-guarantee incident

Question: `v2` changed "citations required" to "optional." Write the containment plan (disable → rollback →
scope → classify → re-release as `v3`) without rewriting history. Which Attempts revalidate the citation
guarantee, and which enter reconciliation?

## 11. Relevant Framework Connections

* **FastAPI + PostgreSQL (production shape).** The in-memory `InMemoryAttemptPromptStore` models a durable
  Attempt prompt-binding table; production uses a DB row with a conditional `UPDATE ... RETURNING` for the
  guarded `PLANNED -> DISPATCHED` / `PLANNED -> BLOCKED_PROMPT_DISABLED` transition — the same discipline as
  Day60's guarded claim and Day72's compare-and-set. **NOT RUN** here.
* **Alembic / migrations.** Immutable published revisions + a new revision for every change is the same rule
  as "never edit a released migration."
* **Day72 Provider Adapter.** The gate runs *before* Day72's capability admission and adapter dispatch; the
  adapter must not choose or rewrite the prompt revision.

## 12. AI Backend Connections

* **Prompt regression + evaluation.** Immutable revisions + rendered hashes make prompt regression tests
  deterministic: a change of behaviour changes the hash. This is the foundation Day77's fake-Provider
  regression suite builds on.
* **Reproducibility for audits and incidents.** The Attempt binding is exactly what an audit or a
  post-incident review needs to reproduce "what ran," scope the affected set, and repair safely.
* **Cost/safety.** The pre-Provider gate prevents paying for invalid/disabled/incompatible prompt calls, and
  fails closed on unknown policy inputs — a real cost and safety control, not a decorative check.
* **Data privacy.** Full rendered prompts are treated as sensitive: minimal logs by default, protected
  artifacts (encryption, tenant-aware authz, access audit, finite retention) only when policy permits.

## 13. English Interview

### Key Vocabulary

prompt contract · revision · immutable published fact · lifecycle overlay (active/disabled/quarantined) ·
Attempt binding · current default vs historical binding · renderer version · model parameter policy ·
input fingerprint · rendered-message hash · rendered artifact reference · backward/forward compatibility ·
structural vs semantic break · alias / migration · fail closed · reconciliation · untrusted candidate.

### Useful Expressions

"A prompt is an application-owned, versioned execution contract, not a mutable string." · "The current default
governs new planning only; an existing Attempt stays bound to its original revision." · "Reject before a valid
transition — the Attempt stays PLANNED with zero Provider calls." · "Compatibility is directional, and both
structural and semantic." · "A hash is integrity evidence, not encryption; a ref is a pointer, not
authorization."

### Beginner Question

*What is a Prompt Contract and why does an LLM application need prompt versioning?*

Student's actual answer (verbatim):

> A "Prompt Contract" is an agreement regarding prompt specifications. LLM applications require prompt
> versioning because providers may update features, resulting in changes to the parameters required by the
> Prompt Contract.

Assessment: partial. It recognized "an agreement" and a versioning need, but confused the **application-owned**
Prompt Contract with **Provider** capabilities and parameter evolution.

Strong answer:

> A prompt contract is an application-owned, versioned definition of the messages, required variables, and
> semantic guarantees used to create a model request. An LLM application needs prompt versioning so each
> Attempt is reproducible and auditable, compatibility can be checked explicitly, and a bad revision can be
> disabled or rolled back without rewriting history.

### Intermediate Question

*What must the LLM Runtime verify before the Provider call, and why bind the Attempt to a specific revision?*

Student's actual answer (verbatim):

> The LLM runtime should verify compatibility with the previous prompt version before the provider is invoked.
> Current approaches do not enforce this binding, which can lead to the tampering of history and render
> auditing impossible.

Assessment: correct direction (LLM Runtime, pre-Provider enforcement, immutable history, auditability); needs
a fuller list of gates and a precise reference to the Attempt's authoritative bound revision.

Strong answer:

> Before the Provider call, the LLM Runtime reads the Attempt's authoritative prompt binding, confirms the
> bound revision is active, validates authorization context and required variables, and verifies compatibility
> with the application contract, then renders deterministically and checks the rendered hash. An existing
> Attempt stays bound to its original revision because the current default governs only new planning;
> overwriting the binding would rewrite historical execution facts and make auditing impossible.

### Senior Question

*A `v2` revision weakened "citations required" to "optional." Contain and repair.*

Student's actual outline (verbatim):

> Contain -> disable v2 -> rollback default selection to v1
> Scope -> prompt_contract_id + revision -> renderer_version -> release/time window -> durable dispatch/outcome evidence
> Classify each Attempt -> repair explicitly -> verify -> controlled re-release as v3

Assessment: strong structure (contain, scope, classify, repair, verify, controlled re-release). A complete
answer enumerates per-Attempt handling.

Strong answer:

> Disable `v2` for new dispatch and roll the default back to `v1`; do not mutate bindings or delete evidence.
> Scope the affected set by prompt_contract_id + revision, renderer/parameter-policy versions, a release/time
> window, and durable dispatch/outcome evidence. Classify each Attempt: PLANNED-never-dispatched → block or
> explicitly re-plan; dispatched-with-successful-transport → treat output as an untrusted candidate and
> revalidate the citation guarantee; definitely-invalid → explicit failure/reconciliation reason;
> TIMEOUT_UNKNOWN → reconciliation, never blind retry; valid-late → interpret with the Attempt's bound
> revision; stale/terminal/superseded → never overwrite authoritative state. Publish a new immutable `v3` and
> roll it out under monitoring.

### Common Weak Answer

"Just update the prompt and redeploy; the latest version is the source of truth." — rewrites history, breaks
reproducibility, and cannot interpret in-flight or timed-out Attempts.

### Strong Answer

See the senior answer above: immutable revisions, per-Attempt binding, fail-closed gate, directional
compatibility, and the four incident verbs (disable / rollback / migration / re-release).

## 14. Mental Model Summary

```text
Prompt Contract = application-owned, versioned execution contract (NOT a string, NOT a provider capability)
Revision        = immutable published behaviour fact
Lifecycle       = ACTIVE / DISABLED / QUARANTINED / UNKNOWN (overlay; UNKNOWN fails closed)
Attempt binding = revision + renderer + parameter-policy + app-contract + input fingerprint + rendered hash
Default         = new planning only; never reinterprets an existing Attempt
Runtime gate    = auth (app) -> load binding -> lifecycle -> variables -> compatibility -> render+hash -> [Provider]
Gate failure    = zero Provider calls (mismatch stays PLANNED; disabled-bound -> BLOCKED_PROMPT_DISABLED)
Compatibility   = directional (backward/forward) AND structural + semantic
Incident verbs  = disable | rollback | migration | re-release  (never rewrite history)
Late/timeout    = interpret with the BOUND revision; TIMEOUT_UNKNOWN -> reconcile, never blind retry
Evidence        = minimal logs (ids/fingerprint/hash); full prompt only as a protected, finite-retention artifact
```

> **Final Chinese mental model — attribution: supplied by the teaching assistant at the student's explicit
> request; this is not the student's original wording.**
>
> Prompt 不是一段可以随时替换的普通字符串，而是应用拥有的、可版本化的执行合同。每个 Attempt 在规划时必须绑定不可变的
> Prompt Contract revision，并同时记录 renderer version、参数策略版本、应用合同、输入指纹和渲染结果哈希。当前默认版本只影响
> 新任务，不能重新解释历史任务。
>
> Provider 调用前，应用业务逻辑先负责授权；LLM Runtime 再从权威 Attempt Store 读取绑定，检查 Prompt 生命周期、变量、schema、
> 兼容性并进行确定性渲染；之后才进入 Provider capability admission 和 Provider Adapter。Adapter 只负责 Provider 特定翻译与
> 错误归一化，不能选择 Prompt 版本。Provider 返回 `SUCCESS` 也只代表拿到了候选输出，仍需通过输出结构、证据、策略和业务验证。
>
> 兼容性既是结构问题也是语义问题，而且有方向。增加有安全默认值的可选变量可能向后兼容；字段改名如果没有 alias/migration 就
> 不兼容；把"必须引用证据"改成"可选"即使 schema 不变，也是语义破坏。已发布 revision 不可原地修改；出现坏版本时应 disable 该
> 版本、把新任务默认 rollback 到安全版本、按持久化证据逐个分类 Attempt，并以新的不可变 revision 重新发布。TIMEOUT_UNKNOWN
> 必须先 reconciliation，不能盲目重试。审计日志只记录最小标识、指纹和哈希；完整渲染 Prompt 若必须保留，应进入受保护、加密、
> 按租户授权、可审计且有限保留的 artifact 存储。

## 15. Today's Takeaway

* **Most important mental model:** the prompt is a versioned execution contract bound immutably to each
  Attempt; the current default governs only new planning.
* **Most important production risk:** silent guarantee loss + history rewrite when a prompt is a mutable
  string.
* **Most important trade-off:** immutable revisions + per-Attempt binding cost more moving parts but buy
  auditability, reproducibility, and safe rollback.
* **Most important framework connection:** the pre-Provider Runtime gate sits *before* Day72's capability
  admission and adapter dispatch, using the same guarded-transition discipline.
* **Most important AI Backend connection:** rendered hashes make prompt regression deterministic and keep
  full prompts out of normal logs.
* **Most important interview answer:** "current default governs new planning only; an existing Attempt stays
  bound to its original revision — otherwise you rewrite history and cannot audit."

## 16. Before Next Lesson Checklist

- [ ] I can state why a prompt is a versioned execution contract, not a mutable string.
- [ ] I can explain WHY the current default must not reinterpret an already-planned Attempt.
- [ ] I can name the production risks: silent guarantee loss, non-reproducibility, history rewrite, unsafe
  recovery.
- [ ] I can correct the misconception that a field rename is "compatible if the meaning is similar."
- [ ] I can defend the trade-off between storing full rendered prompts and storing only hashes.
- [ ] I can run `python3 -m unittest discover -s tests -v` in `projects/ai-agent/` and read the Day73 results.
- [ ] I can connect the pre-Provider gate to Day72's capability admission and the Day54 late-result binding.
- [ ] I can explain how prompt versioning enables deterministic prompt regression tests (Day77).
- [ ] I can answer, in English, beginner/intermediate/senior questions on prompt contracts and versioning.

---

Related: [Day73 design contract](../../projects/ai-agent/docs/DAY73_PROMPT_CONTRACTS.md) ·
[Day73 classroom draft](../../projects/ai-agent/docs/day73-prompt-contracts-classroom-draft.md) ·
[ai-agent project](../../projects/ai-agent/README.md) ·
Previous: [Day72 lesson](day72-provider-capabilities-and-the-replaceable-provider-adapter.md) ·
Next: Day74 — Structured Output, JSON Schema and Function/Tool Calling (Planned).
