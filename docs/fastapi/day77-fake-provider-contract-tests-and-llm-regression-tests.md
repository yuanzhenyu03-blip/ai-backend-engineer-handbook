# Day77 — Fake Provider, Contract Tests and LLM Regression Tests

## 1. Lesson Metadata

- Phase: 7A — LLM Application Engineering
- Date: 2026-08-27
- Prerequisites: Day72–Day76; testing roots from Day57
- Evidence target: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`
- Explicitly not claimed: real Provider, integration runtime, or production

## 2. Learning Objectives

By the end of Day77, you can:

1. place a deterministic Fake at the Provider/transport boundary behind a real Adapter;
2. control response timing and application time without behavioral sleeps;
3. run one stable `ProviderOutcome` Contract Test suite against two Adapters;
4. distinguish definitely-not-sent from possibly-sent failures conservatively;
5. test semantic outcomes, Job state, Provider calls, tool effects, Attempts, and cost;
6. maintain independent, human-reviewed golden expectations;
7. contain and reconcile a bad Adapter release without rewriting history.

## 3. Why This Matters

An LLM application can return valid JSON and still violate the product
contract. It can cite no evidence, execute an unauthorized tool, accept an
incomplete batch, duplicate a Provider call after an ambiguous timeout, charge
twice, or let a stale result overwrite the current Job.

Real Provider calls are slow, costly, nondeterministic, and unable to create
every dangerous timing window on demand. A deterministic Fake Provider makes
those application guarantees locally executable. It does not turn local tests
into Provider or production evidence.

The classroom began with `provider request id` as the proposed proof of a
call. That is incomplete: an ID can be missing after dispatch. Independent call
evidence and conservative execution certainty are required.

## 4. Roadmap Position

```text
Day72 stable Provider Adapter
  -> Day73 immutable Prompt/Attempt binding
  -> Day74 output/tool admission and guarded completion
  -> Day75 streaming/cache/batch boundaries
  -> Day76 routing/fallback/latency/cost
  -> Day77 deterministic contract + semantic regression evidence
  -> Day78 capstone (not implemented here)
```

Day77 adds a verification layer around the existing design. It does not replace
the Adapter or pre-implement the Day78 capstone.

## 5. Lesson Map

1. Define the Fake boundary.
2. Make calls, failures, and time deterministic.
3. Test both Adapters against one stable contract.
4. Drive candidates through the real validation chain.
5. Observe state and side effects separately.
6. Pin semantic behavior with independent goldens.
7. Rehearse a bad-v6 incident and its closure evidence.

## 6. Core Mental Model

```text
scripted Provider-specific fact
    ↓
ControlledFakeTransport (records call, waits at explicit gate)
    ↓
real Provider Adapter (translation boundary)
    ↓
stable ProviderOutcome
    ↓
real application validation / admission / recovery / completion
    ↓
BehaviorObservation
    ↕ compare
independent human-reviewed BehaviorGolden
```

The Fake controls the uncertainty. The Adapter still translates it. The
Runtime still decides what the product is allowed to do. Tests observe both
state and effects.

## 7. Main Concepts

### 7.1 A Fake is not a mock of the answer you want

If the Fake returns the final approved application result, the test bypasses
the Adapter and validation chain. Day77 instead places
`ControlledFakeTransport` behind `ProviderAAdapter` or `ProviderBAdapter`.
Provider-specific response shapes and exceptions must become the same stable
`ProviderOutcome` semantics.

### 7.2 Deterministic response gate

With automatic release disabled, the Fake records the send and signals
`request_received`, but does not return until the test opens
`release_response`. This creates an exact window for timeout, Worker loss, or a
late result.

The test does not sleep and hope the race happens. A short bounded wait exists
only to prevent a broken test from deadlocking.

### 7.3 FakeClock

Application deadlines use an injected integer-millisecond `FakeClock`:

```python
clock = FakeClock(initial_ms=1_000)
clock.advance_ms(250)
assert clock.now_ms() == 1_250
```

Time advances only when the test says so. This proves a deadline decision, not
operating-system scheduling behavior.

### 7.4 Independent minimized call evidence

The call log is injected independently of a Worker or Adapter object. It keeps
only sequence, fictional Provider label, model label, and correlation ID. It
does not store prompts, generated content, SDK messages, credentials, or
customer data.

This demonstrates the evidence boundary during simulated object loss. Because
the store is in-process, it is not real crash durability.

### 7.5 Shared Adapter Contract Tests

One suite runs against both Provider fixtures and asserts only stable outcomes:

| Provider fact | Stable application outcome |
|---|---|
| valid completion | `SUCCESS` |
| output limit reached | `TRUNCATION` |
| refusal | `REFUSAL` |
| throttling | `RATE_LIMIT` |
| bad credentials | `AUTH_ERROR` |
| definitely failed before send | `TRANSPORT_ERROR` |
| may have dispatched / certainty unknown | `TIMEOUT_UNKNOWN` |
| malformed response | `INVALID_RESPONSE` |

Unknown SDK certainty is not converted into a convenient retryable transport
error. It is `TIMEOUT_UNKNOWN` because a duplicate call could duplicate cost or
effects.

### 7.6 Semantic regression, not wording snapshot

The test protects `required citations remain required`, not an exact prompt
sentence. Weakening that guarantee is a semantic breaking change even when the
JSON schema is unchanged.

Similarly, an output candidate must pass the real Day74 chain:

```text
parse -> schema -> registry/lifecycle -> trusted authorization
-> tenant semantics -> immutable admission -> idempotent execution
-> outcome verification -> guarded completion
```

Only then can the test assert final behavior.

### 7.7 State and side effects are separate

`FAILED` is not enough evidence for an unauthorized tool case. The test must
also prove:

```text
tool_effect_count == 0
```

The same principle applies to Provider calls, new Attempts, reservations,
compensations, and stale completion writes.

### 7.8 Attempts and ambiguous execution

Known-safe fallback preserves A1 and creates A2. It never rewrites A1.

`TIMEOUT_UNKNOWN` is different:

```text
keep A1
create A2? no
Job -> PENDING_RECONCILIATION
cost -> UNKNOWN
reservation -> retained
```

Rollback can stop future planning on a bad version; it cannot undo or disprove
an already-issued Provider call.

### 7.9 Stream, cache, and batch regression boundaries

- Partial streams and sequence gaps never emit a complete candidate.
- A cache hit is still a candidate and needs current authorization.
- A batch requires exact one-to-one item identity. Missing or duplicate results
  make the envelope unreliable; all affected items reconcile.

The classroom initially accepted the remaining items after one batch result was
missing. That was corrected because without exact mapping the system cannot
prove which result belongs to which item.

### 7.10 Independent golden expectations

A golden is written and reviewed independently from the observed result. It
pins outcome, recovery, Job state, Provider-call count, tool-effect count,
new-Attempt creation, and cost state, together with contract/policy revisions.

Production output cannot auto-update the golden. Automatic snapshot acceptance
would make the system capable of approving its own regression.

### 7.11 Cost facts

Known usage is settled. Unknown usage remains `UNKNOWN`, and its reservation is
retained until reconciliation. Missing usage is never written as zero. Retry
and fallback cost is aggregated across immutable Attempts rather than replacing
the original cost record.

### 7.12 Bad Adapter v6 containment and closure

Changing unknown execution into `TRANSPORT_ERROR` is a semantic breaking
change. Containment is:

1. enable the stable Adapter/Profile for new planning;
2. stop v6 accepting new Attempts;
3. disable automatic error fallback;
4. bound affected Jobs/Attempts/batch items from immutable facts;
5. classify each Attempt by dispatch certainty and outcome;
6. reconcile unknowns and costs;
7. repair internal facts without rewriting their meaning;
8. authorize, idempotently execute, and verify external compensation;
9. fence late, stale, and superseded outcomes.

Rollback and green tests prove neither affected scope nor settled effects.
Incident closure needs cross-verifiable durable facts, call evidence, tool
facts, cost evidence, owned reconciliation, and a clean controlled rollout.

## 8. Common Misconceptions

### “No Provider request ID means no call happened.”

False. The response containing the ID may be lost after dispatch. Use
independent evidence; otherwise remain conservative.

### “A Fake should replace the Adapter.”

False for Adapter Contract Tests. Put it below the real Adapter so translation
is exercised.

### “A final error status proves safety.”

False. Assert call and effect counts independently.

### “A timeout can always fall back to another profile.”

False. When execution may have happened, creating A2 risks a duplicate call.

### “A deterministic test proves the real Provider.”

False. It proves local application logic under the scripted contract only.

### “A partial batch can accept the results it did receive.”

Not without an exact trustworthy envelope. Missing or duplicate identity makes
the mapping unreliable.

### “Rollback closes the incident.”

Rollback contains future harm. Historical calls, cost, effects, unknowns, and
compensations still require evidence and reconciliation.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost / limit |
|---|---|---|
| Fake below Adapter | tests real translation | fixtures must model each wire contract |
| explicit response gate | exact timing windows | thread orchestration needs a deadlock guard |
| FakeClock | fast deterministic deadlines | does not test real scheduler timing |
| independent call log | separates evidence from Worker object | in-process version is not durable infrastructure |
| semantic golden | detects product regressions | requires intentional human maintenance |
| conservative unknown | avoids duplicate external calls | reconciliation may delay completion |
| zero-effect assertions | proves safety beyond status | requires observable effect boundary |

## 10. Hands-on Exercises

### Exercise A — Adapter equivalence

Run the same success, truncation, refusal, throttling, auth, transport, timeout,
and invalid-response cases against both Adapters. Assert stable outcomes only.

### Exercise B — Controlled unknown window

Hold a response at the gate, wait until call count is one, advance
`FakeClock`, mark A1 unknown, retain its reservation, and prove A2 was not
created.

### Exercise C — Unauthorized tool

Pass a Provider candidate through real output/tool admission. Assert rejection,
no admitted execution, tool-effect count zero, and no guarded completion.

### Exercise D — Batch identity

Remove or duplicate one result ID. Assert every item enters reconciliation.

### Exercise E — Golden regression

Compare an independent golden with an observation whose tool-effect count is
one instead of zero. The mismatch must name `tool_effect_count`.

### Exercise F — v6 incident

Treat an unknown SDK error as possibly dispatched. Prove automatic fallback is
forbidden, cost remains unknown with reservation held, and rollback plus tests
does not satisfy the complete closure checklist.

## 11. Relevant Framework Connections

- `unittest` provides parameterized subtests and deterministic assertions.
- dependency injection places the Fake transport and clock at explicit seams.
- `threading.Event` provides a response gate; it does not provide production
  queue or Worker evidence.
- immutable dataclasses model golden and observed behavior.
- a production implementation would replace the in-process evidence store with
  a durable append-only store and guarded transactional writes.

These connections are architectural patterns, not claims that a specific SDK,
database, or queue was integrated today.

## 12. AI Backend Connections

Day77 binds together the entire application chain:

- Day72: Provider-specific facts become stable outcomes.
- Day73: prompt guarantees and immutable Attempt bindings remain enforced.
- Day74: candidates remain untrusted and tools permissioned.
- Day75: completion, reuse, and batch identity remain exact.
- Day76: route eligibility, fallback certainty, and cost settlement remain
  conservative.
- Day53/54/57 foundations: guarded completion, late results, and deterministic
  fake-based evidence retain their original safety meaning.

The central production principle is evidence-preserving behavior under
uncertainty.

## 13. English Interview

### Key Vocabulary

- deterministic Fake Provider
- contract test
- semantic regression
- execution certainty
- response gate
- guarded completion
- side-effect count
- pending reconciliation
- independently reviewed golden

### Useful Expressions

- “The Fake sits behind the real Adapter, so the test exercises translation.”
- “A missing request ID is not proof that the request was never dispatched.”
- “We assert state and external effects independently.”
- “Unknown usage retains its reservation until reconciliation.”

### Beginner

**Question:** What does a Fake Provider enable?

Student answer:

> It enables `execution_local_runtime` without requiring an actual call to the provider.

Completed answer: It enables deterministic local execution of application
contracts without a real Provider call. It does not prove real network,
Provider, integration, or production behavior.

### Intermediate

**Question:** What should happen when Provider usage is unknown?

Student answer:

> Pending action: review of the cost budget and provider usage data is required.

Completed answer: Mark cost as `UNKNOWN`, retain the reservation, expose an
owned reconciliation path, and never turn missing usage into zero.

### Advanced

**Question:** Can fallback use another profile after an ambiguous timeout?

Student answer:

> A rollback is not possible; instead, a new attempt is made using a different profile version. However, in an "unknown" state, it is unclear whether the provider has already been called. To prevent a duplicate provider call, the system should transition to a `pending_reconciliation` state.

Correction: rollback can stop the bad version for future planning, but cannot
undo an issued call. A new profile may be used only when non-execution is
known. For unknown execution, keep the original Attempt, create no fallback
Attempt, retain cost uncertainty, and reconcile.

### Common Weak Answer

“The Fake returns the expected JSON, and if the final status is failed there
were no side effects.” This bypasses Adapter translation and does not prove
Provider-call or tool-effect count.

### Strong Answer

“I inject a deterministic Fake transport behind every real Adapter, run the
same stable-outcome suite, and then drive candidates through the application’s
actual validation and guarded-completion seams. I assert state, calls, effects,
Attempts, and cost independently. Possible dispatch remains
`TIMEOUT_UNKNOWN`: retain A1 and its reservation, create no A2, and reconcile.”

## 14. Mental Model Summary

以下总结由教学助手在学生明确提出“你帮我总结吧”后提供，不是学生原话：

Fake Provider 的价值不是伪造一个成功答案，而是把 Provider 边界上的响应、失败、
调用证据和时间窗口变成可控事实。Contract Test 必须经过真实 Adapter，断言稳定的
`ProviderOutcome`；Regression Test 必须继续经过真实验证、授权、执行和
guarded-completion，并同时观察状态与副作用。已知未发送才能安全重试或 fallback；
可能已发送就保留原 Attempt、成本预留和未知事实，进入 `pending_reconciliation`。
Golden 必须独立、人工审查，不能由被测输出自动批准。回滚只阻止未来伤害，事故关闭
还需要受影响范围、调用、工具效果、成本、repair、compensation、未知结果和迟到结果
防护之间可交叉验证的证据。

## 15. Today's Takeaway

Deterministic local testing is valuable only when it preserves the real
application seams and observes the effects that matter. Stable outcomes,
immutable Attempts, conservative unknown handling, zero-effect proofs, and
independent goldens turn LLM behavior into an engineering contract.

Day77 evidence: 31 new deterministic tests, 221 cumulative Day72–Day77 tests,
Python 3.11.5, no real Provider call. Final cumulative and static results are
recorded after repository verification.

## 16. Before Next Lesson Checklist

- [x] Fake transport sits behind each real Adapter.
- [x] One stable `ProviderOutcome` suite runs for Provider A and B.
- [x] Response timing is controlled by an explicit gate.
- [x] Application time advances through `FakeClock`.
- [x] Call evidence is independent and prompt-free.
- [x] Unauthorized tool behavior asserts effect count zero.
- [x] Stream, cache, batch, fallback, cost, and stale-result regressions exist.
- [x] `TIMEOUT_UNKNOWN` keeps A1, creates no A2, and retains reservation.
- [x] Goldens are independent and human-reviewed.
- [x] v6 containment, reconciliation, repair/compensation, and closure evidence
  are explicit.
- [x] No real SDK/HTTP/Provider/database/queue/tool/billing system was invoked.
- [ ] Day78 capstone remains future work.
