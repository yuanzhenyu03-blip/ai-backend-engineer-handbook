# Day80 Tool Registry, Schema and Permission Model

## Status and scope

Day80 adds an application-owned Agent Tool governance layer above the released Day74/Day78 boundaries and
below the Day79 Controller. It controls model visibility and invocation-time governance. It does not replace
generic Tool Admission, browser-specific authorization, execution, Outcome Verification or Agent control.

Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`.

## Responsibility map

```text
Day80
  Tool catalog + context capability Snapshot
  Schema projection + exact binding
  current Permission/Registry recheck
  Framework translation + Safe Result projection gate
       |
       v
Day74 generic Tool Contract
       |
       v
Day66 browser-specific server-authorized contract
       |
       v
Day78 bounded execution / Outcome Verification
       |
       v
Day79 Controller
```

Passing Day80 means only `READY_FOR_BACKEND_ADMISSION`. It never means admitted, executed or successful.

## Trusted and untrusted inputs

Trusted, server-derived facts:

- tenant, user, role, Job and Step identities;
- current granted exact Tool identities;
- current argument-narrowing constraints;
- authoritative Day74 Registry identity/version/lifecycle;
- current Tool-specific server contract at the backend boundary.

Untrusted data:

- model Tool choice and arguments;
- tenant, Origin, role or approval fields repeated by the model;
- Framework discovery and metadata;
- raw Tool outcome.

## Capability Snapshot

`build_tool_capability_snapshot()`:

1. rejects duplicate Agent catalog identities;
2. sorts exact `name@version` identities deterministically;
3. filters contextual non-grants before the model call;
4. resolves granted entries through Day74 `ToolRegistry`;
5. excludes unknown or disabled definitions;
6. projects only trusted narrowing constraints;
7. records visible/blocked audit decisions;
8. hashes context, decisions and projected Schemas into one Snapshot identity.

The Snapshot is immutable evidence for one context. It is not a reusable bearer permission.

## Schema projection

The projection algorithm deep-copies the base Schema. A constraint may narrow an existing string property to
an enum. It cannot:

- add an unknown property;
- project a non-string property through this teaching subset;
- widen a base enum;
- mutate the Day74 base definition.

Both base and projected SHA-256 values remain visible in the Snapshot. A candidate binds the projected hash.

## Exact invocation binding

`BoundToolInvocation` retains:

```text
Snapshot identity
+ tenant / user / role / Job / Step
+ exact Tool name / version
+ projected Schema hash
```

`check_invocation_governance()` first validates the original binding, then rebuilds the current Snapshot. A
current permission revocation, lifecycle disable, catalog removal, role/context change or projected-Schema
change fails closed. An active v2 never substitutes for a disabled bound v1.

## Permission composition

`compose_permission_layers()` uses deny-overrides:

| Current authoritative layer results | Composite result | Tool calls |
|---|---|---:|
| any `DENY` | `DENIED` | 0 |
| no deny, any `UNKNOWN` | `POLICY_UNAVAILABLE` | 0 |
| all required `ALLOW` | `ALLOWED` | still 0 at this boundary |

Pre-execution `UNKNOWN` is not `PENDING_RECONCILIATION`. Reconciliation requires evidence that an external
execution may already exist.

## Day74 and Day66 composition

`prepare_candidate_for_backend_admission()` rechecks Day80 governance, then calls Day74's public
`validate_schema_subset()`. It stops before Tool-specific Admission.

The tests then call the real local Day66 `validate_tool_proposal()` boundary. Day66 remains the owner of exact
browser operation, tenant, Origin, report scope, session, approval and server contract. Day80 never copies
those checks.

## Framework Adapter rule

`translate_snapshot_for_framework()` accepts only an application-owned Snapshot. It has no discovery input and
therefore cannot union reflected or decorated functions into the published Tool set. Each translated entry
retains the capability Snapshot identity.

The Framework may translate syntax. It cannot create permissions, choose another version or advance business
state.

## Safe Tool Result gate

```text
ACCEPTED            -> WAIT_FOR_TERMINAL_RESULT -> no observation
UNVERIFIED_TERMINAL -> BLOCKED_UNVERIFIED_RESULT -> no observation
VERIFIED_TERMINAL   -> SAFE_RESULT_READY -> minimal SafeToolResult
```

This gate does not verify outcomes or advance Controller state. Day66/Day74/Day78 must supply the trusted
phase and verified minimal result. `202 + task_id` is acceptance evidence only.

## Rollback and recovery

For a bad Registry or Permission rollout:

1. disable/revoke future visibility and invocation;
2. preserve old Snapshots and candidates as immutable audit evidence;
3. rebuild new Snapshots from corrected facts;
4. reject pre-dispatch candidates with zero calls and no reconciliation;
5. preserve and reconcile an original dispatched identity whose outcome is unknown;
6. never create a replacement call merely because Policy was rolled back.

Rollback stops future harm; it cannot prove an external effect did not happen.

## Validation

From `projects/ai-agent`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.11 -m py_compile src/*.py tests/*.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.11 -m unittest discover -s tests -p 'test_day80_tool_governance.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.11 -m unittest discover -s tests -v
```

Expected released evidence: 22 Day80 tests and 273 cumulative tests.

Not run: real LLM/Provider, Framework, HTTP, PostgreSQL, queue/Outbox/Worker, cross-process fencing, Playwright,
browser session/approval service, Integration Runtime, Production, Day81 state machine/budgets or Day82
checkpoint/resume/recovery.
