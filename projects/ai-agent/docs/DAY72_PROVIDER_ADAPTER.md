# Day72 — Provider Capabilities and the Replaceable Provider Adapter (Phase 7A)

Released design contract for the Day72 slice of the Phase 7A LLM Application Runtime. It makes Day71's
replaceable-Adapter boundary executable: versioned capability admission before a paid call, a replaceable
`ProviderAdapter` that translates Provider-specific requests/responses/failures without weakening the product
contract, and immutable per-Attempt execution contracts. The raw session notes are in
[`day72-provider-adapter-classroom-draft.md`](day72-provider-adapter-classroom-draft.md).

> Evidence tier — Day72 is **CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME** (21 deterministic in-process
> tests — the
> original translation/contract slice plus the Day72 review regressions). `INTEGRATION_RUNTIME` and `PRODUCTION` are **NOT RUN**: no real SDK, no real HTTP process boundary,
> no Provider, no PostgreSQL, no credentials, no paid call, no production traffic. The tests use classroom
> wire-shape fixtures and a `RecordingTransport`; they prove the RULES, not real model/SDK behaviour. Provider
> A/B wire fields are fictional fixtures. Every capability named here is a **current, versioned fact** bound
> to a Capability Profile revision, never a permanent Provider-wide claim. The full Fake Provider contract and
> LLM regression suite remain **Day77** scope.

## Scope

Same cumulative `projects/ai-agent/` Phase 7A Artifact (Day71–Day78). Day72 adds the capability + adapter
slice only. It does **not** implement Day73 prompt versioning, Day74 JSON Schema / tool calling, Day75
streaming/caching/batching, Day76 routing/fallback (Day76 owns provider switching — Day72 must not hide it),
Day77 full Fake Provider/regression suite, or the Day78 capstone.

## Files

```text
projects/ai-agent/
├── src/provider_contract.py        # stable surface: ProviderOutcomeKind, ApplicationRequest, immutable
│                                    #   CapabilityProfile + AttemptExecutionContract (no mutable state),
│                                    #   validate_attempt_binding + AttemptBindingError, AttemptStateStore
│                                    #   Protocol + InMemoryAttemptStateStore (compare-and-set),
│                                    #   admit_capability, ProviderAdapter Protocol (execute()),
│                                    #   ProviderRegistry (rejects duplicate profile_id),
│                                    #   ProviderSelectionPolicy (uses the application contract)
├── src/provider_adapters.py        # RecordingTransport + ProviderAAdapter/ProviderBAdapter (each owns its
│                                    #   transport, exposes execute()) + guarded single-call dispatch_attempt
├── tests/test_provider_adapters.py # 21 deterministic EXECUTED_LOCAL_RUNTIME tests
└── docs/DAY72_PROVIDER_ADAPTER.md  # this file  (+ the classroom draft)
```

## 1. Architecture Boundary

```text
Business Service (FastAPI request boundary; client option is a SELECTOR)
-> server-owned ProviderSelectionPolicy (allowlist + REQUIRES the application contract)
                                                        -> approved CapabilityProfile (else ProviderIncompatibleError)
-> immutable AttemptExecutionContract (persisted versions) + Attempt state = PLANNED (AttemptStateStore)
-> ProviderRegistry / composition boundary (rejects duplicate profile_id)  -> ProviderAdapter (Protocol)
   pre-call gates, in order (each fails with ZERO Provider calls):
     1. validate_attempt_binding()  -> AttemptBindingError on any job/contract/profile/version mismatch
     2. capability admission        -> CAPABILITY_ERROR if the contract is unsupported;
                                       disabled/quarantined -> guarded PLANNED -> BLOCKED_PROFILE_DISABLED
     3. compare-and-set PLANNED -> DISPATCHED   -> guards the SINGLE external call
   -> adapter.execute()  (Adapter uses its OWN transport: build_wire_request -> send -> translate_outcome)
   -> ONE authorized Provider call = ONE Attempt (provider_calls is 0 or 1 for THIS dispatch)
-> Provider SUCCESS is an UNTRUSTED candidate
-> Runtime: schema -> evidence -> policy -> guarded completion
```

- The application owns the stable product contract; Providers offer only versioned capabilities.
- The Adapter translates and must **not** hide retries, switch Providers, or decide Job terminal state.

## 2. Stable Outcome Surface

```text
SUCCESS | PROVIDER_RESPONSE_INVALID | REFUSAL | TRUNCATION | RATE_LIMITED | AUTHENTICATION_ERROR
| CAPABILITY_ERROR | TIMEOUT_UNKNOWN | TRANSPORT_ERROR
```

Distinctions are preserved because recovery differs. `ProviderOutcome` carries only minimized safe evidence
(a Provider request id, a short finish/reason label) — never SDK objects, raw prompts, secrets, or full
payloads.

## 3. Capability Admission (before a paid call)

- A selectable (`ACTIVE`) profile that **verifiably** supports the exact application contract is admitted.
- Otherwise `admit_capability()` returns a `CAPABILITY_ERROR` and **no Provider call** is made
  (`provider_calls=0`). The contract is never weakened to a lowest-common-denominator.
- A passing pre-call check does **not** guarantee runtime success — the real response is new evidence the
  Runtime still classifies.

## 4. Versioned Capability Profile

```text
CapabilityProfile(profile_id, provider_name, model, api_version, profile_version, adapter_version,
                  supported_contracts, requires_request_identity, verification_tier, status)
```

- Immutable audit fact; a published revision is never mutated in place.
- Lifecycle: `ACTIVE -> DISABLED or QUARANTINED` (for NEW selections) -> investigate/verify -> publish a NEW
  revision.
- Capability evidence ladder (honest tiers):

```text
Provider documentation / declared feature      -> DECLARED (input fact, not compatibility proof)
static Adapter translation review               -> STATIC
deterministic in-process translation execution  -> EXECUTED_LOCAL_RUNTIME
real SDK/HTTP process-boundary execution         -> INTEGRATION_RUNTIME (only when actually run + saved)
real production traffic and operations evidence -> PRODUCTION (only when actually established)
```

## 5. Bidirectional Adapter Translation + Ownership

- Provider-specific request fields and response reason codes live **inside** each Adapter. Translation is by
  **semantic equivalence**, not data-type matching. Example: Provider A `finish_reason="length"` and Provider
  B `completionState="MAX_TOKENS"` both map to `TRUNCATION`.
- Validation ownership:

```text
Provider wire/envelope violates its bound versioned response contract
-> Adapter -> PROVIDER_RESPONSE_INVALID   (e.g. a required Provider request id is missing)

Provider envelope is valid, but the application result has missing/unsupported tenant evidence
-> LLM Runtime evidence gate -> reject; never complete the Job   (e.g. a nonexistent citation)
```

- The Adapter observes and classifies facts + safe evidence; the **Runtime** owns
  deadline/budget/cancellation/recovery/new-Attempt policy. A new external call is a **new Attempt**.

## 6. Persisted Execution Contract

```text
AttemptExecutionContract.plan(attempt_id, job_id, profile, application_contract)  # snapshot bound versions
```

- The historical binding answers *what a response means*; current Job/Attempt state answers *whether it may
  write*. Current configuration governs **new** calls; the persisted contract interprets an
  **already-issued** call. It is never rewritten to another profile.

## 7. Real Replaceability + Server-owned Selection

- Business code depends only on the `ProviderAdapter` Protocol; each concrete Adapter owns its transport and
  exposes `execute()`, so callers never pass a transport. `ProviderRegistry` injects the concrete Adapter
  through a composition boundary (no business-service conditionals); `get()` fails closed on
  `DISABLED`/`QUARANTINED`, and `register()` REJECTS a conflicting duplicate `profile_id`
  (`DuplicateProfileRegistrationError`) — changing a Profile's Adapter behaviour requires a NEW revision (an
  identical same-instance re-registration is an idempotent no-op).
- Replaceability = equivalent application result/failure semantics, **not** identical model bytes.
- A client `ProductOption` is a **selector**; `ProviderSelectionPolicy` (server allowlist) is the authority
  and REQUIRES the Profile to support the requested application contract — a known-incompatible selection
  fails closed with `ProviderIncompatibleError` BEFORE any Attempt is persisted or any paid call is made (no
  lowest-common-denominator downgrade, no automatic fallback to another Profile).
- If a persisted Profile is disabled before dispatch, `dispatch_attempt` drives the Attempt through the real
  guarded state path `PLANNED -> BLOCKED_PROFILE_DISABLED` with `provider_calls=0`; its execution contract is
  never rewritten. A different Profile requires an explicit, protected new selection and a NEW Attempt — no
  hidden fallback.
- One Attempt makes AT MOST one external call: a compare-and-set `PLANNED -> DISPATCHED` transition (via the
  injected `AttemptStateStore`) guards the single call; a repeated or non-`PLANNED` dispatch is rejected
  (`AttemptStateError`) with zero new Provider calls. The in-memory store MODELS this compare-and-set; it is
  NOT a production-grade durable database.

## 8. Production Failure / Rollback Exercise

Incident: capability-profile-v4 incorrectly declares Provider B satisfies `research_claims.v1`, so pre-call
admission allows paid calls that return ordinary text / invalid responses or time out after dispatch.

Sequence (student's answer + taught additions): roll back / disable v4 to stop new contamination → retain
audit evidence → scope the affected set by profile/release version + a bounded time window + durable
dispatch/outcome evidence → classify each Job. Rollback controls **new** dispatches only; it does not undo
issued calls, cost, Attempts, or outputs.

```text
blocked before dispatch; provider_calls=0 -> eligible only for a new protected selection decision
definite invalid response received         -> retain failed Attempt/cost; evaluate a new Attempt explicitly
TIMEOUT_UNKNOWN after dispatch              -> PENDING_RECONCILIATION; never blind retry (most dangerous class)
valid late response                         -> same validation gates + guarded completion
stale/terminal Job or superseded Attempt    -> zero-effect refusal
```

No bulk retry, bulk success, Attempt overwrite, or evidence deletion. A new Attempt requires current
deadline, budget, cancellation, execution evidence, application contract, and a guarded claim.

## 9. Validation Status

| Tier | Status | Evidence |
|---|---|---|
| `CONCEPTUAL` | Completed | admission, versioned profile, translation, ownership, execution contract, replaceability, selection, untrusted success, strict-vs-LCD, evidence ladder, rollback |
| `STATIC` | `PASS` | `python3 -m py_compile src/provider_contract.py src/provider_adapters.py`; required sections; balanced fences; whitespace/credential scans |
| `EXECUTED_LOCAL_RUNTIME` | `PASS` | `python3 -m unittest discover -s tests -v` → 21 tests OK (Python 3.10.12); RecordingTransport + fixtures only |
| `INTEGRATION_RUNTIME` | `NOT RUN` | no real SDK, HTTP process boundary, Provider, PostgreSQL or external process |
| `PRODUCTION` | `NOT RUN` | no credentials, customer data, paid call, production traffic, or operational evidence |

Run the tests:

```bash
cd projects/ai-agent
python3 -m unittest discover -s tests -v
```

## Related

- Lesson: [`docs/fastapi/day72-provider-capabilities-and-the-replaceable-provider-adapter.md`](../../../docs/fastapi/day72-provider-capabilities-and-the-replaceable-provider-adapter.md)
- Classroom draft: [`day72-provider-adapter-classroom-draft.md`](day72-provider-adapter-classroom-draft.md)
- Day71 foundations: [`DAY71_FOUNDATIONS.md`](DAY71_FOUNDATIONS.md)
- Project: [`../README.md`](../README.md)
- Next: Day73 — Prompt Contracts, Prompt Versioning and Compatibility (Planned)
