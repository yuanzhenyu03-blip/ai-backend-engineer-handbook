# Day76 — Model Routing, Fallback, Latency and Cost Engineering

## Scope

Day76 adds policy-controlled route selection, classified recovery, explicit latency boundaries and durable
cost evidence to the same Phase 7A LLM Application Runtime. The implementation is a standard-library,
deterministic in-process decision model. It does not call a Provider, fetch live capability/health/pricing,
write a durable database, execute a tool, or reconcile an external account.

## Files

- `src/routing_policy.py`: eligibility-first routing and immutable decision evidence.
- `src/recovery_cost.py`: classified fallback, reservations, settlement and incident closure evidence.
- `tests/test_day76_routing_recovery.py`: deterministic Day76 boundary tests.
- Day72–Day75 modules: reused contracts and prerequisite regression evidence.

## 1. Responsibility map

```text
Application/Product Contract = required business behavior
Prompt/Output/Tool Contracts = exact input, candidate and side-effect rules
Capability Profile           = versioned Provider/model claims
Routing Policy               = server-owned selection rules for new Attempts
Model Router                 = eligibility gates, then preference
Fallback Policy              = classified recovery path
Latency Budget               = allowed time at a named boundary
Cost Policy                  = estimate, reserve, settle or reconcile
Durable Store                = Job/Attempt/completion/cost authority
Reconciliation Worker        = recover unknown external facts
```

The Router does not change a Contract. The Adapter does not authorize or route. Fallback does not prove the
old call did not execute. Metrics do not overwrite durable facts.

## 2. Eligibility before preference

`route()` rejects non-active or contract-incompatible profiles and fails closed when required latency or
pricing evidence has the wrong identity, wrong boundary, invalid value, future timestamp or excessive age.
Only after those gates may policy preference or a constrained client selector change ordering.

The fictional `estimated_units` values are local policy fixtures, not real Provider prices. Likewise p95
fixtures do not claim production latency. In a real runtime, Prompt, Output and Tool compatibility must be
proved by their authoritative registries before this composite application contract is treated as eligible.

No eligible candidate means no Attempt execution binding and no Provider call. Fail-open is not permitted
when a required compatibility, lifecycle, latency or pricing fact is missing or stale.

## 3. Immutable routing evidence

Every new Attempt receives two related immutable facts:

1. `RoutingDecision`: candidate decisions, selected profile, policy revision, pricing revision and decision
   time;
2. Day72 `AttemptExecutionContract`: actual Provider/model/API/Profile/Adapter and application contract.

They must be persisted atomically in a production Durable Store. A new default policy affects only new
planning. It never edits A1, even when A2 uses another Provider/model/Profile.

Provider `SUCCESS` remains an untrusted candidate. Routing cannot skip Day73 Prompt binding, Day74 output/tool
validation, current Admission, idempotent execution, outcome verification or guarded completion.

## 4. Classified recovery

```text
same Provider/model path, new Attempt      = retry
different compatible path, new Attempt    = fallback
unknown external execution                = reconciliation
invalid/unauthorized/incompatible request = reject
bad credentials/configuration             = disable path + repair
confirmed internal wrong fact             = repair
confirmed reversible external consequence = authorized/idempotent compensation
```

`plan_recovery()` checks execution certainty first. `TIMEOUT_UNKNOWN` always returns `RECONCILE` with no new
Attempt. Unauthorized and incompatible work is rejected rather than routed around. Authentication or
configuration faults disable the path for repair. A fallback is possible only when its failure class is
allowed, target remains active and compatible, attempt/deadline limits remain, and the Job has enough budget.

Fallback success never removes the source Attempt. A late response is interpreted using its original binding
and cannot overwrite a terminal or superseded Job.

## 5. Latency engineering

Latency is meaningful only with a measurement boundary and correlation identity:

```text
Job end-to-end
  = queueing
  + routing/admission
  + Provider time-to-first-token / complete-result
  + tool execution
  + outcome verification and guarded completion
```

- TTFT is perceived responsiveness, not durable completion.
- Provider p95 says 95% of observed samples were at or below a value; it does not guarantee one request.
- Timeout is an observation/policy boundary; deadline is the remaining Job-level time budget.
- Streaming may improve perceived latency without shortening durable completion.
- Batching may improve measured throughput only when a real batch facility shares transport/protocol/compute
  work; it can also add queueing delay. Per-item identity never merges.
- Cache hits may be faster but still require current safety checks.

## 6. Cost engineering

```text
estimate     = planning projection
reservation  = budget held before dispatch
reported     = Provider-supplied usage evidence
actual       = accepted settled fact
unknown      = unresolved external usage/cost
```

Cost is tracked per Attempt, aggregated per Job and enforced against tenant/account policy. Retry and fallback
amplify Job cost. `settle()` requires the Attempt-bound pricing revision and releases only unused reservation.
`mark_unknown()` retains the reservation and records no invented actual. A batch total without exact per-item
evidence leaves every item unknown; equal allocation is not an actual fact.

Pricing, model and Capability Profile facts are versioned. Cheaper does not mean contract-compatible, timely,
reliable or better for the business outcome.

## 7. Incident containment and closure

Bad policy v5 admitted incompatible Profile B while health/latency/pricing evidence was stale, fallback
amplified calls, one call became `TIMEOUT_UNKNOWN`, some Attempts produced side effects, and costs were
incomplete.

Containment: roll new planning back to v4, stop v5, pause automatic fallback, quarantine B and fail closed on
stale facts. Preserve every v5 decision and Attempt.

Closure requires more than rollback and tests: scope affected Jobs/Attempts, classify every dispatch/outcome,
reconcile unknowns, settle or retain unknown costs, verify repair and compensation, fence late results, run a
controlled rollout and cross-check logs, metrics, Durable Store and external facts.

## 8. Evidence

- CONCEPTUAL: completed in class.
- STATIC: source compilation and document checks are run during repository update.
- EXECUTED_LOCAL_RUNTIME: deterministic in-process Day76 tests plus Day72–Day75 regressions.
- INTEGRATION_RUNTIME: NOT RUN.
- PRODUCTION: NOT RUN.

No real Provider/model capability, price, latency, availability, usage, tool effect, customer data, credential
or production result is claimed.

## Related

- [Day76 lesson](../../../docs/fastapi/day76-model-routing-fallback-latency-and-cost-engineering.md)
- [Day76 classroom record](day76-model-routing-fallback-latency-cost-classroom-draft.md)
- [Day75 design](DAY75_STREAMING_CACHING_BATCHING.md)
- [AI Agent project](../README.md)
