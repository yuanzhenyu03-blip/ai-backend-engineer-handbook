# Day85 — Multi-agent Handoff and Coordination Boundaries

## 1. Lesson Metadata

- Phase: 7B — Agent Runtime and MCP Engineering
- Status: completed at guided classroom scope
- Evidence: conceptual + static + executed local runtime
- Runtime: Python 3.11.5
- Direct connection: Day84 bounded one agent's context; Day85 coordinates bounded child work
- Next: Day86 — Agent Security: Prompt Injection, Tool Abuse and Data Exfiltration Defense
- Mandatory runnable checkpoint: no; the surrounding checkpoints remain Day83, Day88 and Day94
- Assessment limit: the final synthesis was instructor-authored at the learner's request; independent synthesis was not assessed

## 2. Learning Objectives

By the end of this lesson, you should be able to:

1. separate supervisor proposal, coordinator acceptance, worker claim, execution authorization, result verification and parent action;
2. define a versioned, idempotent handoff contract;
3. delegate only a bounded subset of authority and budget;
4. use durable claims, leases and fences to control worker ownership;
5. recover from duplicate delivery, lost acknowledgement, crashes and unknown Provider outcomes;
6. aggregate required and optional child results without treating raw messages as facts;
7. distinguish cancellation, reconciliation, rollback and compensation;
8. state exactly what deterministic fake execution proves and what remains not run.

## 3. Why This Matters

Creating several Agent objects is easy. Preserving authority and truth while work crosses those objects is the real backend problem.

A message can be delivered more than once. A Worker can crash before or after an external call. A stale process can continue running after its lease expires. A child can return a structurally valid result for the wrong attempt, tenant, source version or fence. A bad policy can widen delegation across many child jobs before anyone notices.

The application therefore needs a coordination protocol whose important facts survive process loss and whose authority is checked at the moment of action.

## 4. Roadmap Position

Day82 made Agent jobs durable. Day83 added approval, interruption and escalation. Day84 separated context from durable business state. Day85 applies those boundaries across parent and child execution.

```text
Day82 durable Job/Attempt/Step
  + Day83 current human-control decision
  + Day84 bounded, non-authoritative context
  + Day85 handoff, delegation, ownership and fan-in
  -> Day86 security controls across the widened Agent surface
```

Day85 does not replace the earlier boundaries. A verified fan-in result is still only an input to the current Day83 execution decision.

## 5. Lesson Map

1. Roles and first-use vocabulary
2. Handoff acceptance and idempotent identity
3. Delegated authority and budget conservation
4. Claim, lease, fence and dispatch
5. Result verification and fan-in
6. Cancellation, reconciliation and compensation
7. Policy rollback and incident closure
8. Deterministic implementation, exercises and evidence

## 6. Core Mental Model

The supervisor proposes; the coordinator validates and persists; the worker executes only within a current bounded grant.

```text
message delivery
    != durable handoff acceptance
    != worker claim
    != current execution permission
    != verified child result
    != parent publication authority
```

`Supervisor` means the component that selects candidate child work. `Coordinator` means the application validation boundary that reads authoritative facts and controls state transitions. `Worker` means the executor of one accepted child attempt. None of these names alone grants authority.

`Handoff` means the whole controlled lifecycle from parent proposal through acceptance, child execution, verification and fan-in. It is not merely a message.

## 7. Main Concepts

### Concept 1: A handoff package is a proposal, not an authority token

A handoff candidate binds at least:

- tenant, parent Job and child Job;
- child Attempt and Step;
- `handoff_id`, revision, fingerprint and idempotency identity;
- input and output contract versions;
- context manifest, source versions and provenance;
- policy version and deadline;
- requested delegation grant and child allocation;
- aggregation slot and required/optional policy.

The coordinator reads current authoritative facts and either persists an accepted record or produces a typed rejection. Same identity plus same fingerprint returns the existing record without advancing it. Same identity plus different semantics becomes an auditable conflict; last-write-wins is forbidden.

### Concept 2: Context and delegated authority are different planes

A context package tells a child what it may read for this task. A delegation grant tells it what the application currently permits it to do.

The grant must be a strict subset of the parent's delegatable capabilities. It also binds tenant, resource scope, source scope, tool capabilities, expiry, policy version, maximum depth and other applicable limits. A child may never infer `publish` authority from a report, prompt, memory or supervisor message that mentions publication.

Current rechecks apply at acceptance, claim, dispatch and result submission. Revoked or unavailable authority fails closed.

### Concept 3: Reservation, child allocation and context budget are distinct

- Parent reservation: business capacity reserved for the parent plan.
- Child allocation: the portion assigned to one child attempt.
- Context budget: the input capacity for one Provider request.

The conservation invariant is:

```text
sum(active child allocations) <= parent reservation
```

Concurrency is permitted inside budget, fanout, depth and policy bounds. Linear execution is not required. Confirmed unused allocation returns to the parent after verification. Verified usage is settled and only the remainder returns. Unknown external outcomes remain held.

### Concept 4: Claim, lease and fence provide two layers of ownership protection

`Claim` is an idempotent durable transition assigning an attempt to a worker. A crash before claim creates no ownership. A zero-row conditional update requires a reread and classification of current durable state; it does not authorize execution.

`Lease` is time-bounded permission. Expiry does not physically stop a process. `Fence` is a monotonically advancing token checked by guarded writes and before Provider dispatch. After controlled takeover, the new owner receives a new fence and writes from the old owner are rejected.

Every dispatch requires an accepted binding, current grant, active ownership, live lease, matching fence, valid allocation, compatible contracts, current policy and deadline.

### Concept 5: Durable Outbox recovery reuses the original identity

An `Outbox intent` is the durable publication intent stored with accepted state. If the application commits the handoff but crashes before publishing, recovery queries the accepted handoff, child attempt, allocation and the original outbox row whose `published_at` is null.

Lost acknowledgement causes republication of the same intent. It does not create a new child Job, handoff or operation identity. At-least-once delivery is handled by stable identities, atomic claims, guarded transitions and fences—not by persistence alone.

### Concept 6: Child output remains a candidate until verified

A result candidate is correlated against tenant, parent/child Jobs, Attempt, handoff, Step, owner, lease/fence, policy, input/output contracts, source versions, context provenance, dispatch marker, operation identity and result reference.

Verification produces a durable fact, not automatic parent completion:

```text
candidate -> verified fact -> aggregation decision
          -> current parent decision -> guarded parent transition
```

Required unresolved children produce `WAIT`. Missing optional children may produce explicit `PARTIAL/INCOMPLETE` only when policy allows. Contradictory identities or facts produce `CONFLICT`. A late result never reopens an already-terminal parent; it remains audit evidence.

### Concept 7: Unknown outcomes reconcile; they do not blindly retry

After a dispatch marker exists, a lost response means the external effect may have happened. The system enters `pending_reconciliation`, retains all bindings and evidence, holds the allocation, and queries by the original `provider_request_id` or operation identity.

Creating a fresh Attempt immediately could duplicate external effects. A new Attempt and allocation are allowed only after reconciliation and retry policy establish that it is safe and necessary.

### Concept 8: Cancellation, rollback and compensation are separate lifecycles

Pre-dispatch cancellation may release allocation only after proving that no external effect occurred. Post-dispatch cancellation is cooperative; unknown outcomes still reconcile.

Rollback stops future harm from a bad policy version. It blocks new acceptance, claims, undispatched execution and aggregation; freezes expanded grants and suspicious allocations; isolates dispatched children; and preserves bindings, outbox rows, dispatch markers and evidence.

Compensation addresses an already-occurring external effect. It has its own identity, authority, approval, budget and audit trail. It cannot erase or rewrite the original execution history.

## 8. Common Misconceptions

| Misconception | Correct boundary |
|---|---|
| The first duplicate advances and the second is rejected | Exact duplicates return the existing fact without advancing; semantic differences conflict |
| A worker that crashed before claim still owns a lease | No claim means no lease or fence ownership |
| Safe child execution must be linear | Bounded concurrency is valid when allocation, fanout, depth and policy invariants hold |
| A required child still running can be called partial | Required unresolved means `WAIT`; optional absence may be partial only by policy |
| Persistence prevents duplicate effects | Persistence retains evidence; identities, claims, fences and guarded transitions prevent repeats |
| Broker delivery proves receipt and authority | Delivery proves neither durable claim nor permission |
| A verified aggregation can publish | It still needs the current parent execution decision |
| Deleting context undoes a Provider effect | External effects require reconciliation or separately authorized compensation |

## 9. Engineering Trade-offs

| Choice | Benefit | Cost |
|---|---|---|
| Application-owned coordinator | One validation boundary and explicit facts | More state transitions and storage |
| Stable handoff/operation identities | Safe retry and correlation | Identity design must be rigorous |
| Lease plus fence | Limits stale ownership and stale writes | Requires atomic guarded storage operations |
| Per-child allocation | Budget conservation and isolation | More settlement bookkeeping |
| Explicit partial/conflict states | Honest parent decisions | More branches than boolean completion |
| Reconciliation before retry | Avoids duplicate effects | Keeps capacity held and increases latency |
| Independent compensation | Preserves audit truth | Requires separate policy and approval design |

## 10. Hands-on Exercises

### Exercise 1: Duplicate and conflict

Accept one handoff, submit the same identity and fingerprint again, then submit the same identity with a changed contract. Verify `ACCEPTED`, `DUPLICATE` and `SEMANTIC_CONFLICT`, with zero Provider calls.

### Exercise 2: Lease takeover and stale fence

Claim a child with Worker A, let its lease expire, allow Worker B to take over with a new fence, then attempt dispatch using A's old fence. The coordinator must reject it before the Provider boundary.

### Exercise 3: Budgeted fanout and partial fan-in

Allocate two children concurrently within a parent reservation. Keep one required child running and observe `WAIT`; then make only an optional child unavailable under a policy that permits partial aggregation and observe explicit incompleteness.

### Exercise 4: Unknown outcome and cancellation

Create a dispatch marker and lose the response. Verify `pending_reconciliation`, original operation identity and held allocation. Compare it with a confirmed pre-dispatch cancellation that safely releases allocation.

### Exercise 5: Bad-policy containment

Quarantine a policy version. Block new acceptance, claim, dispatch and aggregation; classify affected work as undispatched, verified or unknown; settle known usage; reconcile unknown results; and preserve all evidence.

## 11. Relevant Framework Connections

Agent frameworks can provide graphs, supervisors, workers and message routing, but the application still owns authorization, durable identity, budget, leases, fences, result verification and recovery policy. Framework state is not automatically authoritative business state.

The Day85 domain uses Protocol-style ports and deterministic fakes so a later adapter may target a framework without moving business authority into that framework.

## 12. AI Backend Connections

- PostgreSQL would atomically store acceptance, claims, leases/fences, allocations, outbox rows and verified results.
- An Outbox Relay and Broker would publish and redeliver the original intent.
- Provider dispatch would occur only after the coordinator's current pre-dispatch checks.
- Day84 context would be bound as low-trust provenance, never authority.
- Day83 would continue to control approval and final business effects.
- Day86 security must defend the widened parent/child context and tool surface without weakening these boundaries.

These are design connections. The classroom run did not execute PostgreSQL, a Broker or a real Provider.

## 13. English Interview

### Beginner

**Question:** What is the difference between a handoff message and an accepted handoff?

**Model answer:** A message is only a delivery candidate. An accepted handoff is a durable application fact created after the coordinator validates current identity, authority, contracts and budget. Neither one proves that a worker has claimed the task or may call a provider.

### Intermediate

**Question:** Why do a worker lease and a fence token need to coexist?

**Model answer:** The lease limits ownership in time, but it cannot stop a stale process. The fence token is checked on guarded writes and dispatch, so a worker whose lease expired cannot continue after another worker takes over with a newer fence.

### Senior

**Question:** How would you recover a multi-agent operation after an unknown Provider outcome?

**Model answer:** I would keep the original handoff, attempt, dispatch marker, provider request identity, grant and allocation. The child enters pending reconciliation and the allocation stays held. The coordinator queries the provider by the original identity, verifies the evidence, then settles, completes or escalates. I would not create a fresh attempt until reconciliation proves that retry is safe.

## 14. Mental Model Summary

```text
Supervisor: proposes bounded child work
Coordinator: validates current durable facts and controls transitions
Worker: executes one claimed attempt inside grant + allocation + lease + fence

Context: information
Grant: authority
Allocation: business capacity
Lease: time-bounded ownership
Fence: stale-owner rejection
Result candidate: untrusted output
Verified result: durable coordination fact
Aggregation: parent input, not final action authority
```

## 15. Today's Takeaway

Multi-agent reliability is not the number of Agents. It is the ability to preserve identity, authority, ownership, budget and evidence as work crosses process and role boundaries.

When any external outcome is uncertain, keep the original identity, hold the allocation and reconcile. When a policy is wrong, stop future expansion, preserve history and compensate through a separate lifecycle. When a child result arrives, verify it before aggregation and keep final business execution behind the current parent boundary.

## 16. Before Next Lesson Checklist

- [x] I can distinguish proposal, acceptance, claim, dispatch, verification and publication.
- [x] I can explain exact duplicate versus semantic conflict.
- [x] I can explain claim, lease, fence and controlled takeover.
- [x] I can conserve parent reservation across concurrent child allocations.
- [x] I can distinguish required waiting from optional partial fan-in.
- [x] I can explain pre/post-dispatch cancellation and unknown-outcome reconciliation.
- [x] I can outline bad-policy containment and independent compensation.
- [x] I can state that fake local tests do not prove PostgreSQL, Broker, Provider or production behavior.
- [ ] Independently restate the complete Day85 model without instructor synthesis.

Evidence: 29 Day85 behavior tests + 3 grader tests, 443 cumulative tests, 18/18 Day85 seed cases, 16/16 Day84 and 26/26 Day83 seed regressions, and the deterministic example passed on Python 3.11.5. Python 3.12, PostgreSQL, Outbox Relay, Broker, multi-process Workers, real Provider, external Tools, network partitions, clock skew, production fencing, billing and production deployment were not run.
