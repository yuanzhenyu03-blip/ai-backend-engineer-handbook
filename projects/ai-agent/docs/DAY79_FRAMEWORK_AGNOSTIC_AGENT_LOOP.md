# Day79 Framework-agnostic Agent Loop

## Status and scope

Day79 adds a minimal application-owned Controller above the Day78 Runtime. It is a deterministic,
standard-library-only, in-process classroom model. It does not provide durable state, cross-process fencing,
Tool governance, a complete Agent state machine, loop detection, budgets, checkpoint/resume, a real Agent
framework, Provider integration or production evidence.

Evidence: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`.

## Boundary

```text
AgentStepInput
  trusted: tenant / Job / current Step / Runtime Attempt / terminal flag
           verified observations / RuntimeResult / reconciliation identity / wait fact
  untrusted: model_proposal
        |
        v
decide_control()  -- pure, deterministic, zero effects
        |
        v
AgentStepResult = CONTINUE | COMPLETE | WAIT | FAIL | RECONCILE
        |
        v
InMemoryControlStore.apply_continue()
  terminal -> NOOP_TERMINAL
  duplicate decision -> DUPLICATE_REPLAY
  old source Step -> NOOP_STALE
  current new CONTINUE -> CREATED
        |
        v
only CREATED -> AgentRuntimePort.execute_step() -> Day78 Runtime
```

The Controller owns whether another Step may exist. Day78 owns one bounded execution. The model can propose;
it cannot mutate the Job or choose the authoritative next route.

## Decisions

| Decision | Meaning | New Runtime call |
|---|---|---:|
| `CONTINUE` | Goal not yet proven and one next Step is permitted | only after `CREATED` |
| `COMPLETE` | verified Goal condition met or input is terminal | 0 |
| `WAIT` | known prerequisite pending | 0 |
| `FAIL` | explicit non-recoverable Runtime result | 0 |
| `RECONCILE` | an original external outcome may exist but is unknown | 0 |

Decision priority is terminal, explicit/Runtime reconciliation, explicit Runtime failure, verified Goal,
known wait, then continue. The classroom Goal evaluator uses a required count of unique verified observation
identities. It is deliberately minimal and is not a production semantic Goal evaluator.

## Identity and replay

The pure decision derives stable SHA-256 identities from trusted causal input:

```text
control_decision_id -> next step_id -> next runtime_attempt_id
```

The same decision replay finds the same next Step. New verified facts create a different decision identity.
Idempotency controls duplicates; it does not authorize stale work. Current Step and terminal checks still run
before creation. A production system needs a durable conditional update and downstream fencing.

## Day78 composition

`prepare_next_step_with_day78()` accepts a Day79 `NextStepRequest`, then calls the public Day78
`prepare_runtime_attempt()` and `build_bound_application_request()` functions. It preserves Job, tenant,
Attempt, Prompt and routing bindings and performs no Provider call. Day79 does not copy Day78 logic.

## Late, stale and unknown

- Unknown external outcome: keep the original identity/reservation and reconcile it.
- Late result: validate it under its original binding. Arrival time alone grants no authority.
- Stale or superseded result: it may close its own outcome/cost uncertainty but has zero current control
  effect.
- Terminal Job: preserve history, create no new Step and perform no new Runtime call.

## Framework adapter rule

Application contracts contain no framework types. A future adapter may translate `AgentStepResult` to a
framework primitive, but a translation contradicting the Controller must fail closed. LangGraph `Command`
was illustrative only; Day79 neither selects nor imports LangGraph.

## Validation

From `projects/ai-agent`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.11 -m py_compile src/*.py tests/*.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.11 -m unittest discover -s tests -p 'test_day79_agent_loop.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.11 -m unittest discover -s tests -v
```

The Day79 suite covers the decision table, Runtime identity binding, deterministic identity, duplicate,
terminal, stale and non-continue zero-call behavior, and real in-process Day78 preparation composition.

Not run: Python 3.12, real Provider/SDK/HTTP, PostgreSQL, Redis/queue/Worker, durable conditional transition,
downstream fencing, real Tools/compensation/billing, Agent framework, integration runtime and production.
