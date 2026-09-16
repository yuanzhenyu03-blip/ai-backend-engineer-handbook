# Day93 Classroom Draft — Remote MCP Lifecycle

## Production failure

The Client sent `research.lookup`. Its read wait timed out. The remote service may already have changed
state, but no response reached the caller.

The essential rule is:

> Timeout proves that the caller stopped waiting; it does not prove that the operation did not execute.

## Knowledge chain

```text
Day89 application protocol and binding
→ Day90 controlled Client, correlation and output validation
→ Day91 candidate-only handler; no handler Committer
→ Day92 authenticated principal, current authorization and exact permit
→ Day93 deadline, dispatch evidence, retry/reconciliation and observability
→ Day94 complete Agent + MCP runtime
```

## Five distinctions

1. A timeout is the end of a wait, not an execution fact.
2. A deadline is one absolute end time; phase timeouts divide it but cannot reset it.
3. Cancellation is a request to stop future work; it cannot erase work already performed.
4. Retry eligibility is a policy decision over trusted evidence, not an exception handler.
5. Reconciliation is a read-only search for authoritative result evidence, not a replay of the Tool.

## Core lifecycle

```text
request identity
→ security and capacity gates
→ record dispatch boundary
→ transport attempt
   ├─ proven not executed → independent retry policy
   └─ possibly executed → PENDING_RECONCILIATION
                             → authority query
                             → Committer proposal or alert
```

## Classroom checkpoints

### Checkpoint 1 — timeout and cancellation

- Current capability: one parent deadline caps every phase; cancellation facts preserve uncertainty.
- Mental model: caller control and remote execution are different state machines.
- Maximum risk: treating a read timeout as proof that the handler did not run.
- Why the next stage exists: retry needs explicit execution evidence.

### Checkpoint 2 — retry and reconciliation

- Current capability: bounded policy, backoff/jitter, fresh gates and single-worker dispatch claim.
- Mental model: first converge facts; only then ask policy whether another attempt is allowed.
- Maximum risk: replaying an operation while the first attempt may have produced a side effect.
- Why the next stage exists: reconnect and deployment changes introduce stale responses and capabilities.

### Checkpoint 3 — versioning and observability

- Current capability: generation-scoped correlation, incompatible-version rejection, downgrade-safe permits,
  fail-closed JWKS refresh, safe logs and bounded metrics.
- Mental model: observability explains authority decisions; it never grants authority.
- Maximum risk: trusting an unverified response body, trace, payload tenant or stale permit.
- Why Day94 exists: the full Agent runtime still must compose these contracts end to end.

## Reusable answers from the incident drills

- A connect failure can be retried only when the local adapter proves transport handoff never occurred.
- A read timeout is `phase=READ`, `kind=READ_TIMEOUT`, and normally
  `dispatch=POSSIBLY_SENT`, `execution=POSSIBLY_EXECUTED`.
- A retry retains operation and idempotency identities; protocol request identity and attempt number change.
- A verified server pre-handler rejection can prove non-execution even though the request was sent.
- Unknown JWKS key plus refresh outage returns `503`, with zero handler/service calls.
- Unknown reconciliation result stays pending; exhausted observation budget raises an operational alert.
- Graceful shutdown closes admission, then cancels/drains; unresolved work becomes pending reconciliation
  with zero Committer calls.

## Completion gate

The artifacts and executed validation are necessary but not sufficient for course completion. The learner
must still provide an independent final summary, and that summary must be reviewed and corrected before
Day93 is declared complete. Repository publication remains a separate, explicit “更新仓库” action.
