# Day 88 — Agent Runtime Framework Selection Behind a Replaceable Adapter

> Classroom lesson. Candidate C is accepted only for the recorded course scope;
> production readiness remains `MORE_EVIDENCE_NEEDED`.

## Learning objectives

By the end of Day88, you should be able to:

1. distinguish a framework capability from an enforceable application boundary;
2. translate framework output into a strict application-owned proposal DTO;
3. keep production Tool clients outside framework context;
4. re-read authorization and bindings immediately before a side effect;
5. preserve operation identity across retries and reconciliation;
6. make a versioned, scope-limited framework Decision without claiming universal superiority.

## The key rule

Framework Tool calling is proposal generation, not Tool execution. A valid
proposal still cannot execute until the application Committer has checked the
current grant, approval and canonical intent, policy version, fence, deadline,
cancellation and operation identity. Every mismatch fails closed.

## Selected course Adapter

Day88 accepts Candidate C, `pydantic-ai-slim==2.41.0`. The public core types in
`agent_framework_adapter.py` are application types. PydanticAI-native messages
or checkpoints may be converted inside the Adapter, but cannot become public
authorization, reconciliation or business-state contracts.

The old Day87 Candidate B preference remains unresolved because Day87 did not
persist a candidate-to-framework mapping. Day88's A/B/C mapping is new evidence,
not reconstructed history.

## Failure cases to remember

- revoked grant: deny even when framework memory says active;
- changed amount: deny because approval intent no longer matches;
- stale fence: record evidence, but do not commit a durable transition;
- extra control field: reject the entire proposal;
- duplicate operation with identical intent: replay saved result, no new effect;
- duplicate operation with different intent: conflict and fail closed;
- Tool timeout after possible effect: enter `PENDING_RECONCILIATION`, never blind retry;
- Provider timeout before proposal: bounded Provider retry may use a new attempt ID
  under the same operation ID.

## Evidence interpretation

The comparable A/B/C spike used the same contract, Fake Provider, Fake Tool and
failure matrix. Passing establishes framework abstraction compatibility in the
tested scope. It does not establish production Provider networking, production
Tool idempotency or production deployment readiness.

The weighted ranking is secondary to the hard-constraint gate. Candidate C was
the stable leader under `DAY88-WEIGHTS-001 v0.1`, a post-evidence freeze with 12
normalized sensitivity scenarios and zero winner flips.

## Run the checked-in classroom surface

```bash
cd projects/ai-agent
PYTHONPATH=src python3.12 -m unittest tests/test_day88_agent_framework_adapter.py -v
PYTHONPATH=src python3.12 examples/day88_replaceable_framework_adapter.py
```

The example uses a Fake Tool and makes zero production Provider or Tool calls.

## Enterprise notes

In a real system, authorization data must be read transactionally or with a
well-defined consistency guarantee. Durable transitions need CAS/transactions
and a current fence. Each production Tool requires its own idempotency and
authoritative reconciliation contract before rollout.

Common interview question: “Why not give the Agent SDK a Tool client and ask it
to call an authorization function first?” Because a prompt or recommended call
order is not an enforceable boundary; possession of the client creates a bypass.

## Scope and next step

Accepted: local learning, public source on GitHub, application Adapter, Fake
Provider, Fake Tool, Python 3.12 and the tested dependency snapshot.

Not evaluated: production Provider/Tool, containers, bundled artifacts and
internal or production deployment.

Next: Day89 — MCP Foundations and Protocol Model. MCP is another external
protocol boundary and must preserve the same application-owned controls.
