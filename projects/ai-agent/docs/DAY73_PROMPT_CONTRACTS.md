# Day73 — Prompt Contracts, Prompt Versioning and Compatibility (Phase 7A)

> Evidence tier — Day73 is **CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME** (39 deterministic in-process
> Day73 tests; the Day72 regression suite still passes, 97 total). `INTEGRATION_RUNTIME` and `PRODUCTION` are
> **NOT RUN**: no real/paid Provider call, no SDK, no HTTP, no database-backed store, no queue/worker, no
> encryption/KMS, no protected-artifact storage. The `provider_calls` counter models crossing the in-process
> Runtime gate toward the Provider boundary only — it is NOT proof of a real Provider/SDK/HTTP/DB call.

## Scope

The application-owned **Prompt Contract** boundary that must be settled *before* Day72's Provider capability
admission and adapter dispatch: immutable versioned prompt revisions + a separate lifecycle overlay, a durable
per-Attempt prompt binding, deterministic rendering + audit hashing, directional (backward/forward) and
structural + semantic compatibility, explicit non-mutating migration, a fail-closed pre-Provider Runtime gate,
and late-response / timeout-unknown reconciliation.

## Files

```text
projects/ai-agent/
├── src/prompt_contracts.py            # PromptContractRevision, PromptLifecycle, PromptContractRegistry,
│                                      #   VariableSpec/MessageTemplate, validation + deterministic renderer,
│                                      #   AttemptPromptBinding + InMemoryAttemptPromptStore (guarded CAS),
│                                      #   prepare_dispatch pre-Provider gate, compatibility + migration,
│                                      #   reconciliation / late-response classification
├── tests/test_prompt_contracts.py     # 39 deterministic EXECUTED_LOCAL_RUNTIME tests
└── docs/
    ├── DAY73_PROMPT_CONTRACTS.md       # this released design contract
    └── day73-prompt-contracts-classroom-draft.md
```

## 1. Boundary and ownership

```text
Application business authorization  (may the tenant/user do this at all? — NOT a prompt variable)
        |
        v
LLM Runtime (this module)
  load authoritative Attempt prompt binding
  -> lifecycle (ACTIVE?) -> variables/schema -> application compatibility
  -> deterministic render -> verify rendered hash -> guarded PLANNED -> DISPATCHED
        |
        v
Provider capability admission (Day72)  ->  Provider Adapter translation + dispatch (Day72)
        |
        v
Output/business validation (Day74+)  — Provider SUCCESS is an untrusted candidate
```

Owners kept distinct: **business authorization** (application), **prompt behaviour** (Prompt Contract),
**sampling/limits** (a separately versioned Model Parameter Policy), **provider translation** (Day72 Adapter),
and **output validation** (Runtime/business). A prompt variable is never authorization evidence; the Adapter
never chooses or rewrites the prompt revision.

## 2. Immutable revision + lifecycle overlay

`PromptContractRevision` is an immutable published fact: `prompt_contract_id`, `revision`, ordered
`MessageTemplate`s (role + text), `VariableSpec`s (required/optional, type, enum allow-set, safe default),
`compatible_application_contracts`, `semantic_guarantees` (e.g. `citations_required`), `renderer_version`, and
the status it was published with. Re-publishing the same `(id, revision)` with a different definition is
rejected — a change is a **new** revision.

`PromptLifecycle` is a **separate** overlay mapping `(id, revision) -> ACTIVE | DISABLED | QUARANTINED`. An
unregistered revision reports **`UNKNOWN`**, and every caller **fails closed** on it (never assume ACTIVE). A
live disable/quarantine changes new selection and dispatch admission; it never edits a published revision or
reinterprets a bound Attempt.

## 3. Durable per-Attempt binding

`AttemptPromptBinding` (immutable) records `prompt_contract_id + revision`, `renderer_version`,
`parameter_policy_id + parameter_policy_revision`, `application_contract`, `input_fingerprint` (canonical
SHA-256 over validated inputs), `rendered_message_hash` (SHA-256 over ordered rendered messages), and an
optional `rendered_artifact_ref`. `plan_attempt_binding(...)` validates + renders deterministically, then
computes the fingerprint and hash. `InMemoryAttemptPromptStore` holds the authoritative binding + state and
guards `PLANNED -> DISPATCHED` / `PLANNED -> BLOCKED_PROMPT_DISABLED` with a compare-and-set bound to
(identity + full binding + expected state).

The **current default** (`PromptContractRegistry.select_default_for_new_attempt`) is used **only** for new
planning; `prepare_dispatch` always resolves the revision the Attempt is **bound** to.

## 4. The pre-Provider Runtime gate

`prepare_dispatch(request_binding, variables, store, registry)` gates in order, each failure with
`provider_calls=0`:

| Order | Check | Failure outcome | Attempt state |
|---|---|---|---|
| 1 | caller binding == authoritative store binding | `BINDING_MISMATCH` | stays `PLANNED` |
| 1 | state is `PLANNED` | `PromptStateError` | unchanged |
| 2 | bound revision registered | `UNKNOWN_PROMPT` | stays `PLANNED` |
| 3 | lifecycle status ACTIVE | `UNKNOWN_PROMPT` (unknown) / `BLOCKED_PROMPT_DISABLED` (disabled/quarantined) | `PLANNED` / `BLOCKED_PROMPT_DISABLED` |
| 4 | revision supports application contract | `INCOMPATIBLE_CONTRACT` | stays `PLANNED` |
| 5 | variables valid + input fingerprint and re-rendered hash match bound evidence | `VARIABLE_INVALID` / `INPUT_FINGERPRINT_MISMATCH` / `RENDER_HASH_MISMATCH` | stays `PLANNED` |
| ok | guarded `PLANNED -> DISPATCHED` | `READY`, `provider_calls=1` | `DISPATCHED` |

A **dispatch-vs-binding mismatch** is rejected before a valid transition (stays `PLANNED`), which is distinct
from `BLOCKED_PROMPT_DISABLED` (the authoritative **bound** revision is itself disabled).

## 5. Compatibility (directional, structural + semantic)

`backward_incompatibilities(old, new)` returns the reasons `new` is not backward compatible with `old`:

- removing any previously accepted variable is breaking, including an old optional variable;
- removing a previously supported application contract is breaking;

* a required variable of `old` removed (e.g. a rename without an alias) — **structural** break;
* a new required variable without a default — old callers cannot satisfy it;
* a variable type change or an ENUM narrowed — structural break;
* a semantic guarantee present in `old` but dropped in `new` (e.g. `citations_required` -> optional) —
  **semantic** break even if variables/schema are identical.

Adding an **optional** variable with a deterministic default is compatible. Forward compatibility means an
older runtime safely handles or **rejects** unknown fields — never silently accepts them.

## 6. Migration (explicit, non-mutating, fail-closed)

`apply_migration(raw, alias_map)` applies `old_name -> new_name` aliases: agreeing values collapse; a conflict
between an alias and its replacement raises `AliasConflictError`. Migration produces a new normalized input and
never rewrites a historical Attempt binding. An unknown enum value (e.g. `tenant_policy`) fails closed in
`validate_and_fill_variables`.

## 7. Audit evidence

Minimal operational evidence only: ids/revisions, lifecycle decision, `input_fingerprint`,
`rendered_message_hash`, dispatch/outcome ids, state transition and failure classification. A full rendered
prompt is sensitive; if retained it is a protected artifact (encryption, tenant-aware authorization, access
audit, finite retention). A hash is integrity evidence, not encryption; a `rendered_artifact_ref` is a
pointer, not authorization.

## 8. Production failure / rollback exercise

`v2` weakened "citations required" to "optional." Containment: **disable** `v2` for new dispatch, **rollback**
the new-planning default to `v1`, do not mutate bindings or delete evidence. Scope by prompt_contract_id +
revision, renderer/parameter-policy versions, release/time window, durable dispatch/outcome evidence. Classify
each Attempt: PLANNED-never-dispatched → block/explicit re-plan; dispatched-successful → untrusted candidate,
revalidate the guarantee; definitely-invalid → explicit failure/reconciliation; `TIMEOUT_UNKNOWN` →
`PENDING_RECONCILIATION`, no blind retry; valid-late → interpret with the **bound** revision; stale/terminal/
superseded → never overwrite. Recovery: repair through explicit auditable transitions, verify under
schema/evidence/policy, publish a new immutable `v3`, controlled rollout. Four verbs kept distinct:
**disable** / **rollback** / **migration** / **re-release**.

## 9. Validation Status

| Tier | Status | Evidence |
|---|---|---|
| `CONCEPTUAL` | Completed | prompt-as-contract, immutable revisions + overlay, binding, rendering + hash, directional/structural/semantic compatibility, migration, pre-Provider gate, reconciliation, rollback exercise |
| `STATIC` | `PASS` | `python3 -m py_compile src/prompt_contracts.py tests/test_prompt_contracts.py`; required sections; balanced fences; whitespace/credential scans |
| `EXECUTED_LOCAL_RUNTIME` | `PASS` | `python3 -m unittest discover -s tests -v` → 97 tests OK (39 Day73 + 58 Day72 regression), Python 3.11.5; in-memory stores + pure functions only |
| `INTEGRATION_RUNTIME` | `NOT RUN` | no real SDK, HTTP, Provider, database, queue/worker, encryption/KMS, or protected-artifact storage |
| `PRODUCTION` | `NOT RUN` | no credentials, customer data, sensitive prompt, or production traffic |

Run the tests:

```bash
cd projects/ai-agent
python3 -m unittest discover -s tests -v
```

## Related

- Lesson: [`docs/fastapi/day73-prompt-contracts-prompt-versioning-and-compatibility.md`](../../../docs/fastapi/day73-prompt-contracts-prompt-versioning-and-compatibility.md)
- Classroom draft: [`day73-prompt-contracts-classroom-draft.md`](day73-prompt-contracts-classroom-draft.md)
- Day72 design contract: [`DAY72_PROVIDER_ADAPTER.md`](DAY72_PROVIDER_ADAPTER.md)
