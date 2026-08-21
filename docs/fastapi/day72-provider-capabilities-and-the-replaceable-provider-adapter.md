# Day72 — Provider Capabilities and the Replaceable Provider Adapter

## 1. Lesson Metadata

```text
Status:        ✅ Completed (classroom scope) — CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME (28 deterministic in-process tests). INTEGRATION_RUNTIME and PRODUCTION are NOT RUN; no real or paid Provider call, no SDK, no HTTP, no database.
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 5-6 hours
Prerequisite:  Day71 (provider-independent LLM Application Runtime foundations) · Day53 (Provider boundary, ProviderRequest -> ProviderOutcome seam, structured output) · Day61 (real-HTTP Provider Adapter foundation, correlation vs Provider request identity, evidence honesty)
Previous Lesson: Day71 — LLM Application Architecture, Tokens, Context, Sampling and Model Failure Modes (DIRECT PREREQUISITE)
Next Lesson:   Day73 — Prompt Contracts, Prompt Versioning and Compatibility
Engineering Artifact: projects/ai-agent/ (Phase 7A — src/provider_contract.py + src/provider_adapters.py + tests/test_provider_adapters.py + docs/DAY72_PROVIDER_ADAPTER.md + classroom draft)
```

Day71 established the provider-independent LLM Application Runtime mental model but left the replaceable
Adapter unimplemented (CONCEPTUAL + STATIC only). Day72 makes that boundary **executable**: versioned
capability admission before a paid call, a replaceable `ProviderAdapter` that translates Provider-specific
requests/responses/failures without silently weakening the product contract, and immutable per-Attempt
execution contracts.

> Evidence honesty — Day72 spans three tiers and stops there:
>
> * `CONCEPTUAL` — completed in class: capability admission, versioned Capability Profile, bidirectional
>   Adapter translation, stable failure taxonomy + ownership, persisted execution contract, real
>   replaceability via a Registry, server-owned selection with immutable Attempts, untrusted Provider
>   success, strict-contract-vs-lowest-common-denominator, capability evidence ladder, and the rollback
>   exercise.
> * `STATIC` — `PASS`: `python3 -m py_compile` on both modules; required doc sections present; fenced blocks
>   balanced; trailing-whitespace and credential-pattern scans clean.
> * `EXECUTED_LOCAL_RUNTIME` — `PASS`: `python3 -m unittest discover -s tests -v` → **28 deterministic
>   in-process tests OK** (Python 3.10.12) — the original translation/contract slice plus the round-1 and
>   round-2 review regressions: the store holds the **authoritative** immutable `AttemptExecutionContract`
>   (a self-consistent forged request+contract+Adapter trio is rejected with `AttemptBindingError`, zero
>   calls); a **thread-safe** compare-and-set (RLock) with a real two-thread `threading.Barrier` concurrency
>   test proving exactly one external call; the two-purpose Registry (`get_selectable` for new tasks vs
>   `resolve_bound_attempt` for a bound Attempt) driving the real `PLANNED -> BLOCKED_PROFILE_DISABLED` path
>   after a lifecycle disable (no directly-constructed disabled Adapter); and per-Provider failure
>   translation (REFUSAL / RATE_LIMITED / AUTHENTICATION_ERROR / TIMEOUT_UNKNOWN / TRANSPORT_ERROR /
>   PROVIDER_RESPONSE_INVALID / TRUNCATION / SUCCESS) from structured SDK error types, with `TIMEOUT_UNKNOWN`
>   never a second call and never a retryable transport error. They use classroom wire-shape fixtures and a
>   `RecordingTransport` only; the concurrency result is **in-process evidence only**, and the in-memory
>   Attempt state store MODELS a compare-and-set boundary — it is NOT a production database (a production
>   deployment needs a durable DB conditional UPDATE / transaction).
> * `INTEGRATION_RUNTIME` — **NOT RUN**: no real SDK, no real HTTP process boundary, no Provider, no
>   PostgreSQL or other external process.
> * `PRODUCTION` — **NOT RUN**: no credentials, customer data, paid call, production traffic or operational
>   evidence.
>
> The 28 tests prove the RULES of the boundary; they do **not** prove real SDK/model behaviour, cost, rate
> limits, or credentials. The full Fake Provider contract and LLM regression suite remain **Day77** scope.
> Every Provider capability named below is a **current, versioned fact** bound to a Provider + model + API
> version + profile version + Adapter version + verification tier — never a permanent, Provider-wide claim.
> Provider A/B wire fields are fictional classroom fixtures, not real API claims.

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain why a Provider that cannot satisfy the stable application contract must return an explicit
  **capability error** rather than wrap ordinary text or silently weaken the contract.
* Place **capability admission before a paid Provider call**, and explain why a passing pre-call check still
  does not guarantee runtime success.
* Design a **versioned Capability Profile** bound to Provider + model + API version + profile version +
  Adapter version + verification tier, and treat published revisions as immutable audit facts.
* Implement **bidirectional Adapter translation** that keeps Provider-specific request fields and response
  reason codes inside the Adapter and maps them to a stable `ProviderOutcome` surface by semantic
  equivalence, not data-type matching.
* Preserve a **stable failure taxonomy** (authentication, rate-limit, capability, invalid-response,
  truncation, timeout-unknown, transport) because recovery differs — and keep recovery policy in the Runtime,
  not the Adapter.
* Interpret a **late response using its persisted execution contract**, while current configuration governs
  new calls.
* Achieve **real replaceability** via a Protocol + Registry/composition boundary (not business-service
  conditionals), defining replaceability as stable application semantics, not identical model bytes.
* Keep a Provider `SUCCESS` **untrusted** until schema/evidence/policy validation and guarded completion.
* Contain a bad capability-profile release: roll back to stop future harm, scope the affected set, and
  classify each Job without bulk retry or history rewrite.

Note: the Day72 artifact is standard-library-only Python plus design documentation — the appropriate
artifact for a replaceable-Adapter boundary. It does not implement Day73–Day78.

## 3. Why This Matters

An LLM product that hard-codes one Provider's request syntax, trusts its `SUCCESS`, or silently downgrades
the contract to whatever a new Provider happens to support becomes unmaintainable and unsafe the moment the
vendor landscape changes — which it always does.

Production problems Day72 prevents:

* **Vendor lock-in through leaked wire types.** If business code writes `max_tokens` for Provider A and
  `maxOutputTokens` for Provider B, every routing or fallback decision later (Day76) becomes a rewrite. The
  Adapter boundary keeps Provider syntax contained.
* **Silent contract downgrade.** Accepting ordinary text because a Provider lacks native structured output
  ships a field the model never actually guaranteed. Explicit `CAPABILITY_ERROR` with zero calls is honest
  and cheap.
* **Paying for known-invalid calls.** Capability admission before a paid call stops known-incompatible
  requests from ever reaching the Provider.
* **Rewriting history to look clean.** Editing a published capability profile in place, or rewriting a
  blocked Attempt onto a different Profile, destroys the audit trail that incident repair depends on.
* **Trusting a green Provider response.** A valid envelope can still carry a nonexistent citation; only the
  Runtime evidence gate can catch that.

The continuous scenario is unchanged: the multi-tenant AI Research Platform accepts Research Report requests,
uses `research_claims.v1` with required citations, and must keep that product meaning stable while Providers
come and go.

## 4. Roadmap Position

```text
Day53 Provider boundary + ProviderRequest -> ProviderOutcome seam + structured output
   \
Day61 real-HTTP Provider Adapter foundation (correlation vs Provider request id; timeout != non-execution)
   \
Day71 provider-independent LLM Application Runtime foundations (CONCEPTUAL + STATIC)
   -> Day72 versioned capability admission + replaceable Provider Adapter  (YOU ARE HERE)
   -> Day73 versioned Prompt contracts (DIRECT CONSUMER of the stable Provider surface)
   -> Day74 structured output / JSON Schema / tool calling (owns its schema impl; reuses Day72 capability facts)
   -> Day75 streaming / caching / batching
   -> Day76 model routing / fallback / cost (OWNS provider switching; Day72 must NOT hide it)
   -> Day77 full Fake Provider contract + LLM regression suite (OWNS full test system)
   -> Day78 Phase 7A capstone
```

### Knowledge Continuity

```text
Previous Knowledge (direct technical prerequisites)
   Day53 application-owned ProviderRequest -> ProviderOutcome seam; SDK-type containment; untrusted-success
         boundary; versioned execution contract; explicit failure classification; cost uncertainty; guarded
         completion ownership.
   Day61 real-HTTP Adapter foundation: pre-call correlation identity vs Provider-minted request identity;
         timeout != non-execution; response-contract validation; data minimization; evidence honesty.
   Day71 provider-independent runtime: application-owned meaning; finite token/context; versioned Provider
         capabilities; layered validation; TIMEOUT_UNKNOWN -> PENDING_RECONCILIATION; Job vs Attempt;
         guarded completion; rollback that never erases history.
        |
        v
Current Lesson Concept
   Versioned Capability Profile + capability admission before a paid call + a replaceable ProviderAdapter
   (Protocol + Registry) that translates Provider-specific requests/responses/failures without weakening the
   product contract; immutable per-Attempt execution contracts; server-owned Profile selection.
        |
        v
Future Production Usage
   Day73 versioned Prompt contracts on the stable surface; Day74 structured output/tool calling; Day76
   routing/fallback (owns switching); Day77 full regression system; Day78 capstone.
```

**Previous-lesson connection:** Day71 is a **direct prerequisite** — Day72 makes Day71's replaceable-Adapter
boundary executable. **Technical foundations:** Day53 supplies the `ProviderRequest -> ProviderOutcome` seam
and SDK-type containment; Day61 supplies the real-HTTP Adapter foundation (correlation vs Provider request
id, timeout ≠ non-execution, evidence honesty). Day61's deterministic fake-HTTP evidence is **not** real-model
or Production proof, and Day72 did not execute real HTTP.

## 5. Lesson Map

```text
Capability failure + pre-call admission (CAPABILITY_ERROR, zero calls)
  -> Versioned Capability Profile (Provider/model/API/profile/Adapter version + verification tier)
  -> Bidirectional Adapter translation (Provider-specific fields inside; semantic equivalence)
  -> Stable failure taxonomy + ownership (Adapter observes facts; Runtime owns recovery)
  -> Persisted execution contract (bound version interprets an already-issued call)
  -> Real replaceability (Protocol + Registry/composition; not conditionals)
  -> Server-owned selection + immutable Attempts (BLOCKED_PROFILE_DISABLED, never rewrite A1)
  -> Provider SUCCESS still untrusted (Adapter wire gate vs Runtime evidence gate)
  -> Strict contract vs lowest common denominator
  -> Capability evidence ladder + immutable revisions
  -> Rollback exercise (bad capability-profile-v4)
```

## 6. Core Mental Model

```text
Application owns a STABLE product contract  (research_claims.v1 + required citations)
Provider offers only VERSIONED capabilities (bound to a Capability Profile revision)

client ProductOption (constrained selector)
  -> server ProviderSelectionPolicy (allowlist)   -> approved CapabilityProfile
  -> capability admission BEFORE a paid call        -> incompatible => CAPABILITY_ERROR, 0 calls
  -> immutable AttemptExecutionContract (persist the bound versions)
  -> ProviderRegistry / composition boundary        -> ProviderAdapter (Protocol)
       -> build_wire_request()   (Provider-specific request syntax, inside the Adapter)
       -> ONE authorized Provider call = ONE Attempt
       -> translate_outcome()    (Provider-specific finish/error -> stable ProviderOutcome)
  -> Provider SUCCESS is an UNTRUSTED candidate
  -> Runtime: schema -> evidence -> policy -> guarded completion
```

Two sentences: **the application owns meaning; the Provider owns only a versioned capability**, and the
Adapter translates syntax while **exposing** capability differences that change product meaning — it never
hides them. And **a Provider `SUCCESS` is a candidate, not a fact** — it becomes a business result only after
Runtime validation and guarded completion.

## 7. Main Concepts

### Concept 1: Capability failure and pre-call admission

Tech Lead Question:

Provider B cannot satisfy `research_claims.v1`. Do you wrap its ordinary text to "make it fit," or reject it?

Student Thinking:

Wrapping would keep the call "successful," but it would ship a contract the Provider never met.

Student Answer:

`明确返回能力不支持` — "explicitly return capability-not-supported."

And on where the check belongs:

`这个检查应该放在发出付费 Provider 请求之前` — "this check should happen before issuing the paid Provider
request."

Tech Lead Review:

Correct on both. Incompatibility returns a `CAPABILITY_ERROR` with **zero Provider calls** — the contract is
never silently weakened. Admission happens **before** a paid call. One nuance the class added: a passing
pre-call check **reduces** known-invalid calls but does **not** guarantee runtime success — the actual
response is still new evidence the Runtime must classify.

Engineering Thinking:

Pre-call admission is cost control and honesty at once. Wrapping ordinary text is invisible debt that breaks
a downstream consumer who trusts a field that was never guaranteed.

Production Example:

`admit_capability(profile, "research_claims.v1")` returns a `CAPABILITY_ERROR` outcome and the dispatch helper
returns `provider_calls=0` when the profile does not verifiably support the contract.

Framework Connection:

This extends the Day53 `ProviderCapabilityError` from a per-call reaction into a **pre-call admission gate**.

### Concept 2: The versioned Capability Profile

Tech Lead Question:

Is `provider_name` enough to describe what a Provider can do?

Student Thinking:

A provider name alone hides which model and which API version you actually bound.

Student Answer:

`` `provider_name`，模型与版本信息 `` — "`provider_name`, plus model and version information."

Tech Lead Review:

Right. A `CapabilityProfile` binds `profile_id`, Provider, model, API version, profile version, the supported
application contracts, request-identity requirements, Adapter version, and verification tier. Provider
capabilities are **current, versioned facts**, never permanent Provider-wide claims.

Engineering Thinking:

Versioning is what makes capability drift auditable and rollback possible. If a profile were "Provider B
supports JSON," you could never say *which* B, *when*, or *proven how*.

Production Example:

```text
CapabilityProfile(profile_id="prof-B-v1", provider_name="provider_b", model="b-pro",
                  api_version="2026-08-01", profile_version="v1", adapter_version="1.0.0",
                  supported_contracts={"research_claims.v1"}, requires_request_identity=True,
                  verification_tier=EXECUTED_LOCAL_RUNTIME, status=ACTIVE)
```

Framework Connection:

PostgreSQL/durable state is referenced for storing these immutable profile facts; **no database was executed
in Day72**.

### Concept 3: Bidirectional Adapter translation

Tech Lead Question:

Where do Provider-specific request fields live, and is matching data types enough to translate an outcome?

Student Thinking:

If business code writes provider syntax, every provider swap is a rewrite.

Student Answer:

`各自的 Provider Adapter` — "each in its own Provider Adapter."

And on two Providers reporting an output limit differently:

`统一返回截断` — "map both to a unified TRUNCATION."

Tech Lead Review:

Correct. Provider-specific request fields and response reasons belong **inside** each Adapter. Translation
requires **semantic equivalence**, not merely matching data types. Provider A's `finish_reason="length"` and
Provider B's `completionState="MAX_TOKENS"` are two different wire facts that both map to application
`TRUNCATION`. Stable classification does **not** delete the minimized safe Provider evidence (the Adapter
keeps the finish label). And Provider **wire/envelope** validation belongs to the Adapter; **application**
schema/evidence/policy validation belongs to the Runtime.

Engineering Thinking:

The Adapter is a translator, not a policy engine. It converts one Provider's dialect into the stable surface
so the rest of the system speaks one language.

Production Example (from the artifact):

```python
# Provider A adapter
if finish == "length":  return ProviderOutcome(TRUNCATION, detail="finish_reason=length")
# Provider B adapter
if state == "MAX_TOKENS": return ProviderOutcome(TRUNCATION, detail="completionState=MAX_TOKENS")
```

Framework Connection:

Concrete Adapters own Provider SDK/wire types (Day53 boundary); the `ProviderAdapter` Protocol is the only
seam business code sees.

### Concept 4: Stable failure taxonomy and ownership

Tech Lead Question:

Should the Adapter collapse authentication, rate-limit, capability, invalid-response, timeout and transport
into one "error," and should it decide whether to retry?

Student Thinking:

Collapsing looks simpler, but each failure needs a different recovery.

Student Answer:

`保留不同的应用级分类` — "preserve the distinct application-level classifications."

And on who decides recovery:

`只返回分类与安全证据，由 LLM Runtime 的恢复策略决定是否、何时创建下一次调用` — "return only the
classification and safe evidence; the LLM Runtime's recovery policy decides whether and when to create the
next call."

Tech Lead Review:

Exactly. Preserve `AUTHENTICATION_ERROR`, `RATE_LIMITED`, `CAPABILITY_ERROR`, `PROVIDER_RESPONSE_INVALID`,
`TRUNCATION`, `TIMEOUT_UNKNOWN`, `TRANSPORT_ERROR` and `SUCCESS` because recovery differs. The Adapter
**observes and translates facts**; the Runtime owns deadline/budget/cancellation/recovery/new-Attempt policy.
The Adapter does **not** hide retries — a new external call is a **new Attempt** under Day71's model.

Engineering Thinking:

If the Adapter silently retried, you would lose the Job/Attempt audit trail and could double Provider cost.
Separation of "what happened" (Adapter) from "what to do" (Runtime) is what keeps recovery safe.

Production Example:

A `RATE_LIMITED` outcome carries safe `retry_after` evidence but the Adapter takes no action; Day56/Day71
recovery policy decides backoff.

Framework Connection:

Reuses the Day53 typed `ProviderOutcome` union and Day71's `TIMEOUT_UNKNOWN -> PENDING_RECONCILIATION`.

### Concept 5: The persisted execution contract

Tech Lead Question:

Configuration moved from profile-v3 to v4. A late response arrives for an Attempt dispatched under v3. Which
version interprets it?

Student Thinking:

The response was produced under v3's rules, so v3 must interpret it.

Student Answer:

`按照该 Attempt 发出时持久化绑定的 v3 来解释和接收这个响应` — "interpret and receive this response using the
v3 that was persistently bound when the Attempt was dispatched."

Tech Lead Review:

Correct. The **historical binding** answers *what a response means*; the **current Job/Attempt state** answers
*whether it may write*. Current configuration governs **new** calls; persisted execution facts govern
**already-issued** calls. The `AttemptExecutionContract` snapshot is never rewritten to v4.

Engineering Thinking:

Without a persisted contract, a config change would retroactively reinterpret in-flight calls — a
correctness and audit disaster.

Production Example:

`AttemptExecutionContract.plan(attempt_id, job_id, profile_v3, "research_claims.v1")` is stored at plan time;
a v4 rollout does not touch it.

Framework Connection:

Extends Day53's `ExecutionContract` binding to the Provider-profile version.

### Concept 6: Real replaceability and composition

Tech Lead Question:

How does business code get the right Adapter — `if provider == "A"` branches, or something else? And does
replaceability mean identical output text?

Student Thinking:

Conditionals in business code re-introduce coupling.

Student Answer:

`依赖统一的 ProviderAdapter 接口，由组合/注册边界注入具体 Adapter` — "depend on one unified ProviderAdapter
interface; a composition/registry boundary injects the concrete Adapter."

And, with honest uncertainty, on what replaceability requires:

`要求它们保持相同的应用级结果与失败语义？` — "require them to keep the same application-level result and
failure semantics?" (correct direction, expressed as a question)

Tech Lead Review:

Correct direction — confirmed. Replaceability is **behavioral substitutability at the application boundary**:
every Adapter maps equivalent Provider facts to the same `ProviderOutcomeKind` and keeps SDK/wire types
behind the boundary. It is **not** byte-identical model text; safe Provider evidence may differ and stays
explicit.

Engineering Thinking:

A Protocol + Registry means adding Provider C is a new Adapter registration, not a business-logic edit — the
precondition for Day76 routing.

Production Example:

`registry.register(ProviderAAdapter(...))`; business code calls `registry.get(profile_id)` and depends only
on the `ProviderAdapter` Protocol.

Framework Connection:

Dependency injection / composition: `ProviderRegistry` / `ProviderSelectionPolicy` inject a concrete Adapter
behind the stable Protocol.

### Concept 7: Server-owned selection and immutable Attempts

Tech Lead Question:

Can a client send `model=gpt-whatever, profile=v9`? And if profile-v3 is disabled after A1 was planned but
before dispatch, do you rewrite A1 onto another profile?

Student Thinking:

Client-authorized providers would bypass server policy; rewriting A1 would erase what was planned.

Student Answer:

`只能提交受限的产品选项，由服务器策略选择并持久化一个允许的 Provider Profile` — "the client may only submit a
constrained product option; server policy selects and persists an allowlisted Provider Profile."

And on the disabled profile:

`停止 A1，并通过显式、受保护的新决策流程重新选择` — "stop A1, and re-select through an explicit, protected
new decision process."

Tech Lead Review:

Correct. A client `ProductOption` is only a **selector**; server allowlist policy chooses and persists the
approved Profile. If v3 is disabled before dispatch, A1 is retained as `BLOCKED_PROFILE_DISABLED` with
`provider_calls=0`; A1's execution contract is **never** rewritten. Any re-plan is an explicit, protected
**new Attempt** — no hidden fallback.

Engineering Thinking:

Server-owned selection + immutable Attempts is what keeps Provider choice governed and auditable under
incidents.

Production Example (EXECUTED_LOCAL_RUNTIME):

`registry.get(disabled_profile_id)` raises `ProfileDisabledError` (fail closed) at selection time; and when
an already-selected Adapter's profile is disabled before dispatch, `dispatch_attempt` drives A1 through the
real guarded state path `PLANNED -> BLOCKED_PROFILE_DISABLED` with zero calls. A1 keeps `profile_version="v3"`;
it is never rewritten to v4, and choosing another Profile requires an explicit new Attempt (A2).

Framework Connection:

FastAPI accepts the product request; the client option is a selector, not Provider/model authority.

### Concept 8: Provider success remains untrusted

Tech Lead Question:

The Adapter returns `SUCCESS`. Is the Job now `SUCCEEDED`?

Student Thinking:

A green outcome is tempting to treat as done, but validation still hasn't run.

Student Answer:

`不能，因为还需要经过validate` — "no, because it still needs to pass validation."

And on who owns which gate:

`第一种adapter第二种LLM Runtime 的 evidence gate 负责` — "the first [wire/envelope] is the Adapter's; the
second [evidence] is the LLM Runtime's evidence gate."

Tech Lead Review:

Correct. The pipeline is: Provider response → **Adapter** wire validation/translation → schema/format →
**Runtime** evidence/semantic → application policy → guarded completion. A missing required Provider request
identity is an **Adapter** `PROVIDER_RESPONSE_INVALID`; a valid envelope containing a **nonexistent citation**
fails at the **Runtime evidence gate**.

Engineering Thinking:

Two gates because they see different things: the Adapter sees wire correctness; only the Runtime sees whether
the claim is actually supported by tenant evidence.

Production Example (tests 5 + review):

`translate_outcome({"finish_reason":"stop"})` with no `id` → `PROVIDER_RESPONSE_INVALID`; a well-formed
envelope with a fake citation is rejected later at the Runtime evidence gate.

Framework Connection:

Day71 layered validation + guarded completion; Day53 untrusted-success boundary.

### Concept 9: Strict contract vs lowest common denominator, and immutable revisions

Tech Lead Question:

Two Providers differ. Do you weaken `research_claims.v1` to their lowest common capability so both "work"? And
when a live v3 profile drifts, do you edit v3 to match reality?

Student Thinking:

Weakening would make everything compatible but would destroy the product; editing v3 would erase the audit
fact.

Student Answer:

`保留严格产品契约并允许部分 Provider Profile 明确不兼容` — "keep the strict product contract and allow some
Provider Profiles to be explicitly incompatible."

On what proves compatibility:

`需要验证 Adapter 的具体翻译路径和失败行为` — "you must validate the Adapter's concrete translation path and
failure behavior."

On drift handling:

`先禁用/隔离 v3，并在调查和验证后发布新的 Profile 版本` — "first disable/quarantine v3, and after
investigation and verification publish a new Profile version."

Tech Lead Review:

All correct. Keep the strict contract; let incompatible Profiles be explicit. Provider documentation/marketing
is an **input fact, not proof** — compatibility is bound to a concrete Adapter version and an honest
verification tier; native structured-output support alone does not prove `research_claims.v1` translation,
failure mapping, evidence validation, or guarded completion. Published revisions are **immutable**: drift
disables/quarantines the old revision for **new** selections; a **new** revision is published after
verification. v3 is never edited in place to look like v4.

Engineering Thinking:

Lowest-common-denominator design quietly deletes your product's differentiation; immutable revisions keep the
capability history honest for audits and rollbacks.

Production Example:

The capability evidence ladder: `DECLARED -> STATIC -> EXECUTED_LOCAL_RUNTIME -> INTEGRATION_RUNTIME ->
PRODUCTION`, each only when actually established.

Framework Connection:

`VerificationTier` on the `CapabilityProfile`; profile lifecycle `ACTIVE -> DISABLED/QUARANTINED -> new
revision`.

## 8. Common Misconceptions

```text
Provider incompatibility
❌ Wrap ordinary text so the call "succeeds."
✅ Return CAPABILITY_ERROR with zero Provider calls; never weaken the contract.
```

```text
Capability description
❌ provider_name is enough.
✅ Bind provider + model + API version + profile version + Adapter version + verification tier (a versioned fact).
```

```text
Adapter translation
❌ Matching data types is translation.
✅ Translation is semantic equivalence (finish_reason=length AND completionState=MAX_TOKENS both -> TRUNCATION).
```

```text
Failure handling ownership
❌ The Adapter retries and picks another Provider.
✅ The Adapter reports classified facts + safe evidence; the Runtime owns retry/recovery/new-Attempt; a new call is a new Attempt.
```

```text
Config change and late responses
❌ The current profile version interprets every response.
✅ The persisted execution contract interprets an already-issued call; current config governs new calls.
```

```text
Replaceability
❌ Replaceable means identical model output text.
✅ Replaceable means equivalent application-level result/failure semantics; bytes may differ.
```

```text
Provider SUCCESS
❌ Adapter SUCCESS => Job SUCCEEDED.
✅ SUCCESS is an untrusted candidate; schema/evidence/policy + guarded completion still decide.
```

```text
Capability claim
❌ Provider docs/marketing prove application-contract compatibility.
✅ Docs are DECLARED input; proof is a validated concrete Adapter translation + failure path at an honest tier.
```

```text
Drift and revisions
❌ Edit the live v3 profile to match new behavior.
✅ Disable/quarantine v3 for new selections; publish a new verified revision; never edit history in place.
```

Note the classroom record: **no major engineering misconception persisted** — the student consistently chose
fail-closed, versioned, evidence-preserving boundaries. The only uncertainty was phrased as a question
(`要求它们保持相同的应用级结果与失败语义？`), confirmed correct. Do not read that as a wrong initial model.

## 9. Engineering Trade-offs

```text
Explicit CAPABILITY_ERROR vs wrapping ordinary text
Explicit: honest, zero cost on incompatibility, keeps the contract; some Providers are explicitly unusable for a contract.
Wrapping: everything "works" until a consumer trusts an ungrounded field; invisible debt.
Choose explicit rejection whenever product meaning would be silently weakened.
```

```text
Strict product contract vs lowest common denominator
Strict: preserves differentiation (required citations); some Profiles are incompatible.
LCD: maximal Provider coverage; erased product meaning.
Keep strict; let incompatibility be explicit and versioned.
```

```text
Adapter owns retries vs Runtime owns recovery
Adapter-owns: fewer moving parts, but hidden retries break Job/Attempt audit and can double cost.
Runtime-owns: one place for deadline/budget/cancellation/new-Attempt policy; Adapter stays a translator.
Keep recovery in the Runtime; the Adapter only reports classified facts.
```

```text
Mutable profile vs immutable revisions
Mutable: "just fix v3" is convenient; destroys the audit fact and breaks rollback.
Immutable: disable/quarantine + publish a new revision; more steps, honest history.
Prefer immutable revisions.
```

```text
Protocol + Registry vs business-service conditionals
Protocol/Registry: adding Provider C is a registration; enables Day76 routing.
Conditionals: fast to write once, but each new Provider edits business logic and leaks wire types.
Prefer the Protocol/Registry boundary.
```

## 10. Hands-on Exercises

These reproduce the classroom exercises against the `projects/ai-agent/` artifact (std-lib only; no real
Provider). All 28 tests are `EXECUTED_LOCAL_RUNTIME`.

### Exercise 1: Capability rejection makes zero calls

Question: A profile does not support `research_claims.v1`. What outcome and how many Provider calls?

Think First: When does admission run?

Expected Output: `CAPABILITY_ERROR`, `provider_calls == 0` (EXECUTED_LOCAL_RUNTIME).

Follow-up: Does a passing pre-call check guarantee runtime success? (No — the response is still new evidence.)

### Exercise 2: Provider-specific request-field isolation

Question: Build wire requests for Provider A and B from the same `ApplicationRequest`. What differs?

Expected Output: A uses `max_tokens`, B uses `maxOutputTokens`; the values are equal (same meaning) but the
keys are Provider-specific (EXECUTED_LOCAL_RUNTIME).

Follow-up: Why must business code never see these keys?

### Exercise 3: Equivalent success and truncation semantics

Question: Map Provider A `finish_reason` and Provider B `completionState` for both a completed and a
budget-limited response.

Expected Output: `stop`/`COMPLETE` → `SUCCESS`; `length`/`MAX_TOKENS` → `TRUNCATION` (tests 3, 4).

Follow-up: Why keep the finish label as safe evidence instead of discarding it?

### Exercise 4: Missing Provider request identity

Question: A profile requires request identity; the response omits it. Classify it.

Expected Output: `PROVIDER_RESPONSE_INVALID` at the Adapter gate (EXECUTED_LOCAL_RUNTIME).

Follow-up: Where would a *nonexistent citation* be caught instead? (Runtime evidence gate.)

### Exercise 5: Registry injection

Question: How does business code obtain the concrete Adapter without branching on Provider identity?

Expected Output: `ProviderRegistry.get(profile_id)` returns a `ProviderAdapter`; dispatch succeeds with
`provider_calls == 1` (EXECUTED_LOCAL_RUNTIME).

### Exercise 6: Disabled profile fails closed, Attempt preserved

Question: profile-v3 is disabled after A1 was planned. What happens to A1 and to Provider calls?

Expected Output: `ProfileDisabledError` (fail closed), zero calls; A1 kept as `BLOCKED_PROFILE_DISABLED` with
`profile_version="v3"` — never rewritten (EXECUTED_LOCAL_RUNTIME).

Follow-up: How is a different Profile chosen? (Explicit, protected new Attempt.)

### Exercise 7 (design): Bad capability-profile-v4 rollback

Question: v4 wrongly claims Provider B satisfies `research_claims.v1`, allowing paid calls that return ordinary
text/invalid responses or time out. Contain and repair.

Expected Output (the student's sequence + taught additions): roll back/disable v4 to stop new contamination →
retain audit evidence → scope the affected set by profile/release version + bounded time window + durable
dispatch/outcome evidence → classify each Job. No bulk retry/success, no history deletion, no Attempt
overwrite. (Section 15 / rollback exercise.)

## 11. Relevant Framework Connections

**FastAPI.** Accepts the product request; the client `ProductOption` is a **selector**, not Provider/model
authority. Server `ProviderSelectionPolicy` chooses the allowlisted Profile.

**Provider SDK/API boundary.** The concrete Adapter owns Provider wire fields, response envelopes, reason
codes, and SDK types (Day53 containment). **Current real APIs were not called or claimed** in Day72; Provider
A/B are fictional fixtures.

**Dependency injection / composition.** `ProviderRegistry` / `ProviderSelectionPolicy` inject a concrete
Adapter behind the stable `ProviderAdapter` Protocol — the seam Day76 routing will build on.

**PostgreSQL / durable state.** Referenced for immutable Attempt execution contracts, dispatch evidence,
affected-set evidence, and guarded completion. **No database was executed in Day72.**

**Day61 HTTP integration.** Reused as a foundation only; Day72 did **not** execute real HTTP.

## 12. AI Backend Connections

* **Multi-tenant product policy and cost boundary before paid calls** — capability admission stops
  known-incompatible spend.
* **Versioned model/provider capabilities and honest incompatibility** — a Profile is a current fact, and
  "incompatible" is a legitimate, explicit result.
* **Stable failure semantics** for authentication, rate-limit, capability, invalid-response, truncation,
  timeout-unknown, and transport failures — because recovery differs.
* **Untrusted model results, evidence validation, reconciliation, Attempt identity, guarded completion** —
  a Provider `SUCCESS` is a candidate; `TIMEOUT_UNKNOWN` reconciles.
* **Configuration rollback vs durable business-history repair** — rollback stops future harm; history is
  never rewritten.

## 13. English Interview

### Key Vocabulary

Provider Adapter · capability profile · capability admission · versioned capability · verification tier ·
bidirectional translation · wire fields · finish reason · replaceability · Registry / composition ·
allowlist · selector vs authority · execution contract · immutable revision · disable/quarantine ·
PROVIDER_RESPONSE_INVALID · TIMEOUT_UNKNOWN · affected set.

### Useful Expressions

* "The application owns the contract; the Provider offers a versioned capability."
* "Reject an incompatible capability before the external call — `PROVIDER_CAPABILITY_ERROR`, zero calls, no
  contract downgrade."
* "Replaceable means equivalent application semantics, not identical model text."
* "A published capability revision is immutable; drift disables it and we publish a new revision."

### Beginner Question

Actual Question: What is a replaceable Provider Adapter, and why does an LLM application need one?

Student's Verbatim Answer: *"The Provider Adapter facilitates bidirectional translation between the provider
and the application. LLMs require it to enable provider switching and avoid excessive coupling."*

Language Correction: `LLMs require it` makes the model the subject — use **"An LLM application needs it"**;
`excessive coupling` → **"tight vendor coupling."**

Engineering Concept Correction: the bidirectional-translation and decoupling model is correct; add that the
Adapter translates **versioned** capabilities/failures and must **not silently weaken** product semantics.

Strong Interview Answer: "A replaceable Provider Adapter translates, both ways, between one Provider's request/
response/failure syntax and the application's stable contract. An LLM application needs it to avoid tight
vendor coupling and to switch Providers without rewriting business code — while keeping product meaning
stable and exposing, not hiding, capability differences."

### Intermediate Question

Actual Question: A selected provider does not support a capability required by the application contract. What
should the Adapter do, and why should this check happen before the provider call?

Student's Verbatim Answer: *"Party A should directly reject the request; rejecting it prior to the formal
invocation avoids unnecessary provider calls and associated costs."*

Language Correction: `Party A` is a contract/negotiation term, not the Adapter — say **"The Adapter should
reject this provider execution path before making the external call."** `formal invocation` → **"before making
the external call."**

Engineering Concept Correction: the pre-call rejection/cost model is correct; add an explicit
**`PROVIDER_CAPABILITY_ERROR`, zero external calls, and no silent contract downgrade.**

Strong Interview Answer: "The Adapter (or the admission gate in front of it) rejects the provider execution
path before making the external call, returning `PROVIDER_CAPABILITY_ERROR` with zero calls and no contract
downgrade. Doing it pre-call avoids paying for a known-invalid request; the check reduces known-invalid calls
but the real response would still be new evidence to classify."

### Senior Question

Actual Question: A bad capability profile incorrectly allowed several paid calls. Some returned invalid
responses, others timed out after dispatch. How would you contain the incident and safely repair the affected
jobs?

Student's Verbatim Answer (a terse keyword outline): *"Rollback error, capability profile, retain audit
evidence, build a collection for each job, classification, explicit fix."*

Review: the high-level ordering is correct but incomplete. Taught directly (added): scope the affected set by
release/profile version **plus a bounded time window and durable execution evidence**; classify
**invalid-response vs `TIMEOUT_UNKNOWN`**; **no blind/bulk retry**; and create a **new Attempt only after**
deadline, budget, cancellation, execution-evidence and guarded-claim checks.

Language Correction: use **"Roll back or disable the bad capability profile," "build an affected set,"** and
**"perform an explicit, guarded repair."**

Strong Interview Answer: "Roll back or disable the bad capability profile to stop new contamination; retain
audit evidence; build an affected set scoped by profile/release version, a bounded time window, and durable
dispatch/outcome evidence; then classify each Job — pre-dispatch blocked (0 calls) may re-plan, a definite
invalid response retains its failed Attempt/cost, `TIMEOUT_UNKNOWN` goes to `PENDING_RECONCILIATION` with no
blind retry, a valid late response passes the same gates, and a stale/terminal/superseded Attempt gets a
zero-effect refusal. A new Attempt is created only when all guard conditions allow it; history is never
overwritten or deleted."

### Follow-up Questions

* Why is `TIMEOUT_UNKNOWN` the most dangerous class in the affected set? (`不可以，最危险的那一类是已经未知的
  那一类` — unknown execution/cost; bulk A2 creation is prohibited.)
* Why classify deterministic in-process Adapter tests as `EXECUTED_LOCAL_RUNTIME` and not higher? (Student:
  `` `EXECUTED_LOCAL_RUNTIME` `` — no real SDK/HTTP/Provider.)
* Why can a Provider's marketing claim never be the proof of contract compatibility?

## 14. Mental Model Summary

```text
Application contract   = STABLE product meaning (research_claims.v1 + citations)
Provider capability    = VERSIONED fact bound to provider/model/api/profile/adapter version + verification tier
Capability admission   = BEFORE a paid call; incompatible => CAPABILITY_ERROR, 0 calls; never weaken the contract
Capability Profile     = immutable audit fact; drift -> DISABLE/QUARANTINE -> new revision (never edit in place)
Adapter                = bidirectional translation by SEMANTIC equivalence; wire types stay inside
Adapter ownership      = observe + classify facts + safe evidence; NOT retry/switch/terminal-state
Failure taxonomy       = auth | rate-limit | capability | invalid-response | truncation | timeout-unknown | transport
Execution contract     = persisted per Attempt; interprets an ALREADY-ISSUED call; current config governs NEW calls
Replaceability         = equivalent application result/failure semantics (NOT identical bytes)
Selection              = client ProductOption is a SELECTOR; server allowlist is the AUTHORITY
Disabled profile       = fail closed; A1 = BLOCKED_PROFILE_DISABLED (0 calls); never rewrite A1
Provider SUCCESS       = untrusted candidate -> schema -> evidence -> policy -> guarded completion
TIMEOUT_UNKNOWN        = PENDING_RECONCILIATION; no blind retry
Rollback               = stop future harm; scope affected set; classify per Job; never erase history
```

## 15. Today's Takeaway

* **Most important mental model:** the application owns the contract; the Provider is a versioned capability
  behind a replaceable Adapter that translates syntax but exposes capability differences and never weakens
  product meaning.
* **Most important production risk:** silent contract downgrade (wrapping ordinary text) or hidden Adapter
  retries — both destroy honesty and audit; and trusting a Provider `SUCCESS` before validation.
* **Most important trade-off:** strict product contract vs lowest common denominator — keep strict, let
  incompatibility be explicit and versioned.
* **Most important framework connection:** a `ProviderAdapter` Protocol + `ProviderRegistry` composition
  boundary keeps Provider SDK/wire types contained and enables Day76 routing.
* **Most important AI-backend connection:** versioned capability admission before paid calls + a stable
  failure taxonomy + immutable Attempts is what makes multi-Provider LLM backends operable.
* **Most important interview answer:** reject an incompatible capability **before** the external call —
  `PROVIDER_CAPABILITY_ERROR`, zero calls, no downgrade.

## 16. Before Next Lesson Checklist

- [ ] Can I explain why an incompatible capability returns `CAPABILITY_ERROR` with zero calls instead of
      wrapping ordinary text?
- [ ] Can I list the fields of a versioned Capability Profile and why `provider_name` alone is insufficient?
- [ ] Can I explain bidirectional translation by semantic equivalence (two output-limit states → TRUNCATION)?
- [ ] Can I say who owns failure classification vs recovery, and why a new call is a new Attempt?
- [ ] Can I explain why a late response is interpreted by its persisted execution contract?
- [ ] Can I define replaceability as stable application semantics, not identical text, and implement it with a
      Protocol + Registry?
- [ ] Can I explain why a Provider `SUCCESS` is still untrusted and which gate catches a fake citation?
- [ ] Can I contain a bad capability-profile release without bulk retry or history rewrite, in English?

---

Related: [Day72 artifact — Provider Adapter design contract](../../projects/ai-agent/docs/DAY72_PROVIDER_ADAPTER.md)
· [Day72 classroom draft](../../projects/ai-agent/docs/day72-provider-adapter-classroom-draft.md)
· [ai-agent project](../../projects/ai-agent/README.md)
· Cheat sheet: [`cheat_sheets/fastapi.md`](../../cheat_sheets/fastapi.md) (Day72)
· Interview: [`interview/fastapi.md`](../../interview/fastapi.md) (Day72)
· Previous: [Day71 lesson](day71-llm-application-architecture-tokens-context-sampling-and-model-failure-modes.md) (DIRECT PREREQUISITE)
· Next: Day73 — Prompt Contracts, Prompt Versioning and Compatibility (Planned)
