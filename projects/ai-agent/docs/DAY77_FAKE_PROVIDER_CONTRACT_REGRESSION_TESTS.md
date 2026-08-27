# Day77 — Fake Provider, Contract Tests and LLM Regression Tests

## Scope

Day77 makes the Day72–Day76 application guarantees executable without a real
Provider call. It adds a deterministic Provider/transport boundary, one shared
Adapter Contract Test suite, and semantic regression tests that observe both
state and side effects.

This is `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`. It is not Provider,
database, queue, Worker, tool, billing, integration, or production evidence.

## Files

- `src/fake_provider_testing.py`: deterministic clock, response gate,
  minimized independent call log, and independently-authored golden model.
- `tests/test_day77_fake_provider_contract_regression.py`: 31 Day77 tests.
- Day72–Day76 source files remain the production seams under test.

## 1. Test boundary

```text
ApplicationRequest
  -> real ProviderAAdapter / ProviderBAdapter
  -> ControlledFakeTransport
  -> scripted Provider-specific response or exception
  -> stable ProviderOutcome
  -> real validation / admission / recovery / guarded-completion seams
  -> observed state + observed side effects
```

The Fake is behind the real Adapter. Tests therefore prove translation into
the application-owned `ProviderOutcome`; a Fake that returned
`ProviderOutcome` directly would bypass the contract being tested.

No SDK object, wire-field spelling, exception class name, or exact prompt text
is part of the stable assertion surface.

## 2. Deterministic failure control

`ControlledFakeTransport` scripts exactly one response or exception per call.
It records the Provider-boundary send before waiting at `release_response`.
With automatic release disabled, the test can:

1. wait for `request_received`;
2. prove call count is exactly one;
3. advance `FakeClock` explicitly;
4. mark the Attempt `TIMEOUT_UNKNOWN` and retain its reservation;
5. release a late response and verify stale/guarded behavior.

The bounded real-time wait is only a deadlock guard for a broken test; it does
not choose application behavior. Application time is controlled only by
`FakeClock`.

The independent log is injected separately from the simulated Worker and
Adapter. Replacing those objects cannot erase call evidence. This teaching log
is in-process, append-only, and thread-safe; it is not a claim of process-crash
durability.

## 3. Evidence minimization

Each call record contains only:

- sequence;
- fictional Provider label;
- model/profile routing label;
- correlation ID.

It excludes raw prompts, Provider payloads, credentials, secrets, customer
content, SDK exception text, and generated output. Missing evidence is never
invented, and unknown cost is never recorded as zero.

## 4. Shared Adapter Contract Tests

The same behavioral suite runs against Provider A and Provider B. It covers:

- success;
- output truncation;
- refusal;
- rate limit;
- authentication failure;
- timeout after possible dispatch -> `TIMEOUT_UNKNOWN`;
- failure definitely before send -> `TRANSPORT_ERROR`;
- malformed Provider response;
- unknown SDK execution certainty -> conservative `TIMEOUT_UNKNOWN`;
- minimized call evidence.

The assertion target is the stable `ProviderOutcome`. Missing a Provider
request ID is not proof that no call happened; dispatch certainty comes from
independent evidence and the Adapter's conservative translation.

## 5. Semantic LLM regressions

Day77 pins application guarantees rather than model wording:

- weakening a required-citations guarantee is breaking;
- an unauthorized tool candidate produces zero tool effects;
- partial or sequence-gapped streams do not produce a complete candidate;
- a cache candidate cannot reuse revoked authorization;
- missing or duplicate batch item identities make the whole result envelope
  unreliable, so every affected item enters reconciliation;
- ordinary fallback preserves A1 and creates A2;
- `TIMEOUT_UNKNOWN` preserves A1, creates no A2, holds its cost reservation,
  and enters `PENDING_RECONCILIATION`;
- retry/fallback cost is aggregated by immutable Attempt;
- a late, stale, or superseded completion has zero state effect;
- routing eligibility still precedes preference.

For output/tool cases, the scripted Provider candidate passes through the real
Day74 validation, authorization, idempotency, execution, outcome-verification,
and guarded-completion chain before final behavior is asserted. A final Job
status alone is insufficient: effect count is a separate required assertion.

## 6. Golden expectations

`BehaviorGolden` is an independent, human-reviewed semantic expectation. A
golden includes contract/policy revision plus the observable outcome, recovery
action, Job status, Provider call count, tool effect count, new-Attempt fact,
and cost status.

Production code produces `BehaviorObservation`; `golden_mismatches` compares
the two. Production output never generates or automatically accepts its own
golden. Snapshot auto-update is intentionally absent because it could bless a
semantic regression.

## 7. Bad Adapter v6 incident exercise

The v6 failure drill treats changed execution-certainty mapping as a semantic
breaking change:

- re-enable the stable Adapter/Profile for new planning;
- stop v6 accepting new Attempts;
- disable automatic error fallback;
- retain A1 and do not create A2 when dispatch may have occurred;
- identify affected Job/Attempt/batch items from version, time window,
  bindings, `RoutingDecision`, persisted outcome, call log, tool facts, and
  cost evidence;
- classify every Attempt by dispatch certainty and outcome;
- repair internal facts only without changing historical meaning;
- compensate already-executed external effects through separately authorized,
  idempotent, verified actions;
- reconcile unknown Provider and compensation outcomes;
- fence late, stale, and superseded results.

Rollback plus green tests is containment evidence, not incident closure.
Closure requires bounded affected scope, resolved unknowns or owned observable
reconciliation, settled known cost, explicitly unknown cost with reservations,
verified repairs/compensation, stale-result safety, and controlled rollout with
cross-verifiable evidence.

## 8. Evidence and limits

Executed from `projects/ai-agent` with Python 3.11.5:

```text
python3.11 -m unittest -v tests.test_day77_fake_provider_contract_regression
31 tests OK
```

The cumulative Day72–Day77 suite and static checks are recorded in the formal
lesson and repository status after final verification.

Not run: a real SDK or HTTP request, a real or paid Provider, PostgreSQL,
Redis, queue/Worker lifecycle, external tool, billing API, integration runtime,
or production traffic. Provider A/B and Adapter v6 are fictional fixtures.

## Related

- `DAY72_PROVIDER_ADAPTER.md`
- `DAY73_PROMPT_CONTRACTS.md`
- `DAY74_OUTPUT_TOOL_CONTRACTS.md`
- `DAY75_STREAMING_CACHING_BATCHING.md`
- `DAY76_MODEL_ROUTING_FALLBACK_LATENCY_COST.md`
