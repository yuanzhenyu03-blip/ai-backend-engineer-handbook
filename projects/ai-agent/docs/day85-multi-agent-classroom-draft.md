# Day 85 Classroom Record — Multi-agent Handoff and Coordination Boundaries

> Draft classroom record in an isolated baseline. It is not the formal lesson, release, or repository completion record.

## Baseline

- Remote SSOT: `yuanzhenyu03-blip/ai-backend-engineer-handbook`
- Fixed baseline commit: `72656f9aa407ec6cb6b4deff1e21f70a582f500e`
- Baseline status: Day 84 completed; Day 85 planned/not started
- Day 85 is not a mandatory phase checkpoint
- Real integration gate: not opened

## Teaching outcome

The learner can now describe the controlled handoff chain:

> The supervisor proposes a handoff. The coordinator validates current durable facts and persists an accepted binding. A worker obtains bounded execution permission through an idempotent claim, live lease, and current fence. Any returned output is only a result candidate until the coordinator verifies identity, evidence, authority, and contract. Fan-in aggregates verified facts, while the parent still needs the current execution decision before any final external action.

The most important separation is:

`message delivery ≠ durable acceptance ≠ worker claim ≠ execution permission ≠ verified result ≠ parent publication`

## Learner reasoning demonstrated during class

The learner correctly concluded that:

- a stale fence must be rejected and the provider must not be called;
- a post-dispatch unknown outcome enters `pending_reconciliation`, retains the original operation identity, and holds its allocation;
- child C can receive 2500 units when a 9000 parent reservation has 2500 actual usage and 4000 still held;
- conflicts must be resolved rather than guessed;
- revoked context access must follow current authority;
- pre-dispatch and post-dispatch cancellation require different handling;
- an unpublished outbox row is recovered from the original accepted handoff and durable identities;
- late results for a terminal parent remain audit evidence;
- erroneous policy versions require containment, evidence preservation, and controlled recovery;
- compensation is separate from context management and may withdraw or notify under its own authority;
- recursive delegation cannot exceed bound depth, fanout, budget, or grant scope;
- a handoff message is only a proposal/notification, not proof of acceptance, claim, or authority;
- coordinator unavailability requires waiting for authoritative storage rather than inventing state.

The learner gave a particularly strong incident-containment answer covering acceptance, claims, dispatch, fan-in, grant freeze, allocation freeze, reconciliation, evidence continuity, affected-set identification, settlement, compensation, and monitoring exit.

## Misconceptions corrected

1. **Duplicate handoff** — The learner first proposed advancing the first request and rejecting the second. The corrected rule is: same identity plus same fingerprint returns the existing fact without advancing; same identity plus different semantics is a conflict.
2. **Crash before claim** — The learner initially treated the crashed worker as if it held a lease. No claim means no lease or fence; another worker may claim. A live lease blocks takeover, while an expired lease permits controlled takeover with a new fence.
3. **Concurrency and budget** — The learner initially required a linear sequence. Safe concurrency is valid when active child allocations remain within the parent reservation and all other bounds.
4. **Partial fan-in** — The learner initially labeled a state partial while a required child was unresolved. Required work means `WAIT`; only missing optional work may be explicitly partial when policy permits.
5. **Persistence and duplicates** — Persistence retains evidence but does not alone prevent duplicate effects. Idempotent identities, atomic claims, guarded transitions, and fences provide the protection.
6. **Result verification chain** — “It still needs validation” was directionally correct but incomplete. The full chain is candidate → verified durable fact → aggregation decision → current parent decision → guarded parent state transition.
7. **Day 82/83/84 composition** — The learner did not yet have a compact combined answer. The corrected composition is: Day 82 supplies bounded context, Day 84 evaluates output as evidence, Day 85 verifies child coordination facts, and Day 83 alone authorizes the final business action.
8. **Fake evidence boundary** — The learner correctly noted the local execution location, but the evidence is narrower: it does not exercise real provider, PostgreSQL, broker, network, multiprocess scheduling, clock skew, billing, or production failure modes.
9. **English terminology** — “Proxy switching” was corrected to “agent handoff”; `undispatched child task`, `parent reservation`, and `EXECUTED_LOCAL_RUNTIME` are the precise terms used in this course.

## Teacher-authored final synthesis

This final synthesis was produced by the instructor at the learner's request.

Day 85 is about preserving authority and truth while work moves across agents. A supervisor may choose a candidate, but the coordinator is the durable validation boundary. It binds tenant, parent, child, job, attempt, handoff, contract, policy, context provenance, grant, allocation, and operation identity before a worker may act. The worker's permission is temporary and bounded by claim ownership, lease, fence, scope, budget, depth, fanout, concurrency, deadline, and current policy.

The system must assume at-least-once delivery, crashes, lost acknowledgements, stale workers, late results, and unknown external outcomes. Therefore retries reuse stable identities; duplicates return existing facts; semantic conflicts stop; unknown outcomes reconcile through the original provider request; and capacity remains held until evidence permits settlement. A result is never trusted simply because a child produced it. It must be correlated and verified before fan-in, and even a ready aggregation does not authorize publication.

The failure boundary is equally important. Pre-dispatch work can be cancelled and released only after proving there was no effect. Post-dispatch cancellation is cooperative. Already-occurring effects are not erased; they are audited and, where justified, handled by a separately approved compensation lifecycle. During a bad-policy incident, the system first stops expansion, freezes authority and capacity, preserves evidence, classifies every affected operation, settles what is known, reconciles what is unknown, and recovers only through explicit exit criteria.

The classroom artifact demonstrates these semantics with deterministic in-memory components. It proves decision logic, not production integration. No real provider, PostgreSQL, broker, or business side effect was exercised.

**Assessment note:** instructor-authored synthesis completed; learner independent synthesis **NOT ASSESSED**.

## English interview assessment

- Beginner: message/acceptance/claim distinctions became clear after terminology correction.
- Intermediate: budget, lease/fence, required/optional fan-in, and at-least-once reasoning were substantially correct; identity binding needed expansion.
- Senior: incident containment and rollback reasoning were strong; Day 82/83/84 composition and test-evidence limitations required instruction.
- Independent final synthesis: **NOT ASSESSED** because the learner explicitly requested an instructor summary.

## Practical artifact

The isolated implementation includes:

- `src/multi_agent_coordination.py`
- `tests/test_day85_multi_agent_coordination.py`
- `tests/test_day85_seed_grader.py`
- `evals/day85_multi_agent_seed.jsonl`
- `evals/run_day85_seed_eval.py`
- `examples/day85_multi_agent_handoff.py`

The example ends with a verified aggregation fact while `parent_completed=false` and `publish_authorized=false`, making the Day 83 boundary visible.

## Suggested exercises

1. Add a PostgreSQL repository adapter whose conditional claim and fence checks are performed atomically, while preserving the current domain API.
2. Add a broker adapter and prove that lost ACK recovery republishes the original outbox intent without generating a new handoff identity.
3. Add a reconciliation adapter that queries a fake provider by `provider_request_id` and settles held allocations only after a verified outcome.
4. Add property tests for reservation conservation across concurrent accept, cancel, settle, and reconcile transitions.
5. Add a separately authorized compensation record and demonstrate that it cannot mutate the original execution evidence.

## Connection to Day 86

Day 85 establishes trustworthy child execution facts. Day 86 can build higher-level evaluation or optimization only on top of those verified identities, evidence records, and explicit aggregation states; it must not bypass coordination boundaries by treating raw child messages as truth.
