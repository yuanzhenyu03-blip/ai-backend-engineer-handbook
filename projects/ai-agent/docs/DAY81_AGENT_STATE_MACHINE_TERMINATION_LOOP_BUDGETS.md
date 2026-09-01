# Day81 Agent State Machine, Termination, Loop Detection and Budgets

## Scope

Day81 adds an application-owned state machine above the Day79 controller and the Day80 governed Tool surface.
The model remains an adviser: it may propose a next action, but only verified audit facts can drive a legal
transition and only the authoritative apply boundary may reserve capacity and publish executable work.

This artifact is a deterministic in-process teaching implementation. It proves decision ordering, identity
binding, conditional apply, fence advancement and reservation accounting with local tests. It does **not** prove
PostgreSQL transactions, queue publication, distributed concurrency, Provider integration, billing settlement or
production behavior.

## Authority boundary

```text
model recommendation
  -> Day79 validated result
  -> verified lifecycle / authorization / budget facts
  -> pure candidate transition
  -> authoritative conditional apply + reservation + fence advance
  -> executable effect only when status == APPLIED and action == CONTINUE
```

`decide_transition()` is pure. It returns a `TransitionDecision`; it never mutates state, spends money, creates a
Step or schedules work. `InMemoryAgentStateStore.apply()` is the teaching authority boundary. A production
implementation should use one durable conditional transaction, conceptually `UPDATE ... SET ... WHERE ...
RETURNING`, together with durable reservation rows and an Outbox where dispatch is required.

## State model

| State | Meaning | New planning allowed? |
|---|---|---:|
| `READY` | admitted but not executing | yes, through the authority boundary |
| `RUNNING` | active controller lifecycle | yes, if all guards pass |
| `WAITING` | known prerequisite is incomplete | no |
| `PENDING_RECONCILIATION` | an externally relevant outcome is unknown | no |
| `COMPLETED` | verified goal satisfied | terminal |
| `TERMINATED` | policy, budget or no-progress stop | terminal |
| `FAILED` | verified non-recoverable failure | terminal |
| `CANCELLED` | explicit cancellation | terminal |

`WAITING` and `PENDING_RECONCILIATION` are deliberately different. Waiting means the missing prerequisite is
known. Reconciliation means a side effect, dispatch, usage or outcome may already exist and must be classified
against the original identity before any new attempt is considered.

## Transition priority

The pure decision function applies this ordering:

1. terminal state -> `NOOP_TERMINAL`;
2. existing or newly verified outcome uncertainty -> `PENDING_RECONCILIATION`;
3. verified goal satisfied -> `COMPLETED`;
4. known prerequisite -> `WAITING`;
5. verified non-recoverable failure -> `FAILED`;
6. verified hard no-progress loop -> `TERMINATED/NO_PROGRESS_LOOP_DETECTED`;
7. revoked current authorization -> `TERMINATED/AUTHORIZATION_REVOKED`;
8. Tool governance drift -> terminate on revoked permission, otherwise wait and replan;
9. step, context, token and cost guards;
10. `CONTINUE` candidate with the exact Day79 `NextStepRequest`.

This ordering explains two important cases:

- goal 3/3 verified plus zero remaining Steps -> `COMPLETED/GOAL_SATISFIED`;
- goal 2/3 plus zero remaining Steps -> `TERMINATED/STEP_BUDGET_EXHAUSTED`, with no automatic retry.

## Progress and loop detection

Activity is not progress. A different natural-language action can still reproduce the same unresolved state.
Day81 therefore records a `ProgressSnapshot` whose fingerprint represents verified change in goal, evidence,
external state or authorized lifecycle. Repetition without a new verified fingerprint may trip a hard loop guard.

A hard no-progress loop terminates with `NO_PROGRESS_LOOP_DETECTED` even when nominal budget remains. Budgets
bound consumption; they do not prove useful progress.

## Budget guards

The four guards are independent:

- Step budget: remaining controller transitions.
- Token budget: application-owned reserved/available token capacity.
- Cost budget: reserved/available spend; unknown external usage stays held.
- Context budget: one request must satisfy
  `input_tokens + reserved_output_tokens + safety_margin <= application_context_budget <= provider_limit`.

A Provider advertising 128k context does not admit a 33k request when the application contract is 32k. Token
budget is a Job-level consumption guard; context budget is a per-request fit guard.

Reservation lifecycle is explicit. If 6000 tokens were reserved and verified usage is 1800, settle 1800 and
release 4200. If the Provider outcome or cost is unknown, keep the reservation `HELD` until reconciliation.

## Identity, idempotency and fences

Every decision binds `job_id`, `step_id`, `attempt_id`, expected state and expected fence token. Idempotency keys
suppress duplicate side effects for the same semantic operation; they do not stop a stale worker from writing a
new value. Fence tokens reject stale writers after lease revocation or ownership change.

The in-memory store demonstrates:

- duplicate transition replay does not consume budget twice;
- stale fences and stale Step identities cannot mutate the record;
- terminal states reject old `CONTINUE` candidates;
- apply-time budget changes reject a previously valid candidate;
- state, reservations and fence advancement appear as one atomic in-process mutation.

## Governance and recovery

Current authorization is rechecked before apply. Revocation blocks dispatch, retains the existing Step and audit
history, and releases only reservations known to be safe to release. A disabled or superseded Tool binding is not
rewritten from v1 to v2: the old Step remains evidence and a newly authorized planning operation may create a new
Step with the new binding.

For `TIMEOUT_UNKNOWN`, ambiguous Provider `404`, lost acknowledgements or uncertain dispatch, preserve the
original Job/Step/Attempt/Tool Call identity and enter `PENDING_RECONCILIATION`. Recovery uses new auditable
operations. Compensation is a separate operation with its own identity; if compensation times out, it too enters
reconciliation rather than being declared successful or blindly repeated.

## Incident recovery contract

When a bad controller release or policy executes:

1. suspend new planning, Step creation and scheduling;
2. cancel or isolate the bad release/policy;
3. revert future planning to a stable verified version;
4. revoke old worker leases and advance fence tokens;
5. re-examine lifecycle, release and authorization at the Provider/Tool boundary;
6. scope impact by release version, time window and identity;
7. preserve Jobs, Steps, Attempts, Tool Calls and reservations;
8. recover in-flight Attempts without rewriting history;
9. classify and reconcile already-observed external events through new auditable operations.

Example classification: A1 not dispatched -> release reservation and replan; A2 verified terminal -> settle its
usage but decide Job completion independently; A3 outcome unknown -> hold reservation and reconcile the original
identity.

## Evidence

- `src/agent_state_machine.py`: typed pure decision and in-memory conditional apply model.
- `tests/test_day81_agent_state_machine.py`: 20 deterministic Day81 tests.
- Full project result: 293 local in-process tests passed under Python 3.11.5.
- Evidence level: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`.
- Not run: Python 3.12, PostgreSQL, queue/Outbox, real Provider or Tool, billing, distributed worker, integration
  runtime and production.
