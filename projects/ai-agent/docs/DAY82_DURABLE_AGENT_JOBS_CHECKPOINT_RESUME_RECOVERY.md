# Day82 Durable Agent Jobs, Checkpoint, Resume and Recovery

## Scope

Day82 evolves the Day78–Day81 application-owned Agent Runtime with an identity-bound Checkpoint and a structured
recovery boundary. It composes the existing Runtime, Controller, Tool Governance and State Machine contracts; it
does not give a framework, model, Worker, queue or log independent lifecycle authority.

The executable Artifact is a deterministic in-process teaching model. Its types describe facts that a production
PostgreSQL implementation would persist, but `InMemoryDurableAgentJobStore` is not durable and does not prove
database transactions, queue delivery, multi-process fencing, Provider reconciliation or crash recovery.

## Core authority boundary

```text
durable Job + current Checkpoint + Reservation + execution evidence
-> pure `decide_durable_recovery()` candidate
-> compare tenant / Job / Step / Attempt / state / version / fence
-> one authoritative apply boundary
-> state + Checkpoint + Reservation + Audit + Outbox Intent
```

The application owns legal lifecycle semantics. A production database would enforce the conditional transition.
If a conditional `UPDATE ... WHERE ... RETURNING` affected zero rows, no executable Outbox Intent could be
committed.

## Checkpoint contract

`DurableCheckpoint` binds:

- tenant, Job, Step, Attempt and Checkpoint identities;
- Checkpoint version, authoritative state and state version;
- fence token and lease/execution generation;
- controller release and immutable Prompt/Provider/Tool/Policy bindings;
- progress fingerprint and verified observation references;
- Reservation and pending-reconciliation identities;
- previous Checkpoint identity.

It records where authoritative state was committed. It is not process memory, a model summary, a log, a cache,
a queue ACK, an HTTP response, a pickle, a framework-owned truth source or new authorization.

`state_version`, `checkpoint_version`, `fence_token` and controller release are independent:

- state version detects decisions based on superseded business state;
- Checkpoint version orders/versions Checkpoint records;
- fence rejects a superseded execution owner;
- release identifies the code/controller contract that produced historical facts.

## Recovery classification

| Decision | Meaning |
|---|---|
| `RESUME` | Continue the same valid durable identity from a committed Checkpoint. |
| `RETRY` | Create a new Attempt only after definitely-not-dispatched/accepted or explicit safe-retry evidence. |
| `REPLAN` | Preserve the old Step; create a new plan because current facts invalidate the old binding. |
| `RECONCILE` | Query/classify the original external operation while preserving identity and held Reservation. |
| `REPAIR` | Correct an internal durable reference without changing historical meaning. |
| `SETTLE` | Settle verified usage and release unused reserved capacity. |
| `COMPENSATE` | Create a new authorized, idempotent operation for a confirmed unwanted effect. |
| `ESCALATE` | Stop bounded automation while preserving unknown truth and held capacity. |
| `TERMINAL_NOOP` | Refuse old business work that would reopen a terminal Job. |
| `REJECT_STALE` | Reject an identity, state-version or fence mismatch. |

Current defaults govern new planning only. Historical Attempt interpretation always uses the original immutable
bindings. Disabling Tool v1 does not rewrite A1 as Tool v2. A separate current governance check decides whether a
new operation is allowed.

## Transaction and Outbox design

A production transaction would atomically model:

1. guarded authoritative lifecycle update;
2. new Checkpoint;
3. Reservation hold/release/settlement;
4. immutable Audit Event;
5. Outbox Intent;
6. new state version and, where ownership changes, fence generation.

Commit is not publication. A Relay scans committed unpublished rows and may publish the same event more than
once if it crashes after Broker acceptance but before its publication checkpoint. Delivery is at-least-once.
Consumers still require event identity, semantic-identity conflict detection, current lifecycle guards and
fencing. No exactly-once cross-system effect is claimed.

## Lease, fence and late results

A lease grants time-bounded execution ownership. Expiry allows a new Worker to take over, but does not prove the
old Worker never called a Provider or Tool. Takeover advances the fence. The old Worker's write is rejected, while
its result reference remains audit/reconciliation evidence. Evidence value does not restore control authority.

## Reservation continuation

Reservation is capacity held against a budget, not the budget or final usage. Duplicate recovery and Queue
delivery do not reserve twice. If 6000 units were held and 1800 are verified, settle 1800 and release 4200. If
usage is unknown, keep the Reservation `HELD`; missing evidence is not zero.

Job Goal and accounting lifecycles remain separate. A `COMPLETED` Job rejects new business execution but may
continue bounded reconciliation, settlement or repair without reopening its Goal lifecycle.

## Bounded recovery

Recovery attempt count, limit, deadline, generation and evidence fingerprint must be durable in production. A
process-local counter would reset on restart. Exhaustion stops automated queries and creates an escalation
candidate; it does not convert unknown into failure or release held capacity. Day83 will add the full human
approval/interrupt/escalation workflow.

## Crash-window results

- Candidate before commit: no durable Step/Checkpoint/Reservation/Outbox exists.
- Commit before publish: resume committed state and publish the original Outbox Intent.
- Publish before publication checkpoint: republish the same event; Consumer deduplicates.
- Lease expiry after dispatch: advance fence, reject old writes, retain late evidence.
- Provider/Tool response lost: preserve original identity and Reservation; reconcile before Retry.

## Bad-release recovery

Contain the release, stop new planning/scheduling, quarantine affected Outbox work, revoke leases, advance fences,
preserve history and build the affected set from release plus padded time and the complete identity/evidence graph.

- A1 definitely not dispatched: release, then replan/retry only under current guards.
- A2 verified terminal, 1800/6000 used: settle 1800, release 4200; compensate only if the effect is unwanted.
- A3 TIMEOUT_UNKNOWN: preserve identity and Tool-v1 binding, keep 6000 held, reconcile the original operation.

Rollback and passing tests stop future contamination but cannot close an incident without classified outcomes,
settled/owned reconciliation, stale-worker protection, audit continuity and a controlled rollout.

## Evidence

- `src/durable_agent_jobs.py`: typed Checkpoint/recovery model and in-memory conditional apply.
- `tests/test_day82_durable_agent_jobs.py`: 32 deterministic Day82 tests.
- Cumulative `projects/ai-agent` result: 325 deterministic tests on Python 3.11.5.
- Evidence level: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`.
- NOT RUN: Python 3.12, PostgreSQL, real transaction/Outbox, queue/Relay/Worker redelivery, process crash/restart,
  multi-process fencing, Provider/Tool/billing reconciliation, integration runtime and production.
