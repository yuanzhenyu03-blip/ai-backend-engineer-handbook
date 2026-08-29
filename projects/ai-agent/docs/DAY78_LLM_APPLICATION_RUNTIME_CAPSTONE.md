# Day78 — LLM Application Runtime Capstone

## Scope

Day78 composes the Day72–Day76 public boundaries into one application-owned
Runtime checkpoint while keeping Day77 regressions. It does not implement the
Day79 Agent Loop or Day80 tool governance.

## Contract

```text
resolve -> eligibility/route -> immutable preparation -> claim/gates
-> bound request -> stable ProviderOutcome envelope -> candidate validation
-> current Tool Admission -> guarded execution -> outcome verification
-> guarded completion/reconciliation -> settlement -> RuntimeResult
```

`RuntimeResult` carries stage, status, Job/Attempt identity, recovery action,
safe reason, operation identity when relevant, minimized evidence and evidence
level. It excludes prompts, credentials, customer data and raw payloads.

## Reused public boundaries

- Day72: `ApplicationRequest`, `AttemptExecutionContract`, `ProviderOutcome`.
- Day73: Prompt selection, binding, rendering and hash.
- Day74: Tool Admission, executor and `verify_publish_outcome()`.
- Day76: eligibility-first `route()` and immutable `RoutingDecision`.
- Day77: shared Adapter Contract and semantic regression suite.

## Lifecycle and identity

The in-process store models one authoritative lifecycle and atomic claim. The
claim issues a monotonic in-process fence token, and the Tool effect boundary
rechecks owner, lifecycle, call identity, idempotency identity and that token.
Unknown dispatch cannot reopen the Attempt. Tool execution is recorded
separately from outcome verification. Identity mismatch reconciles; verified
current identity completes. This is executable contract evidence, not a claim
of durable downstream fencing.

The canonical message bridge preserves Day73 role/order and verifies the bound
hash before building the Day72 request. The Provider execution envelope binds
Job/Attempt/correlation identity and candidate integrity. Protected references
fail closed because an authorized loader was not integrated.

Cancellation after a confirmed effect preserves the source Attempt. A
compensation gets a separate identity/key and causal source references. An
unknown compensation stays under that identity.

The cost store binds one settlement identity to one Job/Attempt/reservation,
reconciles unknown settlement, rejects identity rebinding, and releases only
unused reservation. It models an idempotent ledger; no billing API ran.

## Validation

Python 3.11.5 from `projects/ai-agent`:

```text
PYTHONPATH=src python3.11 -m py_compile src/*.py tests/*.py
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
```

Result: 22 Day78 tests; 243 cumulative Day72–Day78 tests; all passed.

Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`.

Not run: Python 3.12, real SDK/HTTP/Provider/SSE, PostgreSQL, Redis,
queue/Worker, durable fencing, protected artifact storage, external Tool or
compensation, billing, integration runtime, or production.
