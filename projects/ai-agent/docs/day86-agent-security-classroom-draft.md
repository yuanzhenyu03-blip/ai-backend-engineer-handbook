# Day 86 Classroom Record — Agent Security

> Draft classroom record in an isolated baseline. It is not the formal repository release or a production-security claim.

## Baseline

- Remote SSOT: `yuanzhenyu03-blip/ai-backend-engineer-handbook`
- Fixed baseline commit: `c58386845d822ec03628a071ea8a053cbfde5aeb`
- Baseline status: Day85 completed; Day86 planned/not started
- Day86 is not a mandatory Phase 7B runnable checkpoint
- Formal repository, real Provider/Tool/Egress and production Sandbox gates: not opened

## Teaching outcome

The learner can now reason across this chain:

```text
untrusted content -> model candidate -> application security admission
-> controlled dispatch -> result candidate -> verified external outcome
-> required security fan-in -> current parent business decision
```

The durable rule is: **the model may suggest, but only trusted application components can authorize and physically cross a Tool, Egress, credential or Sandbox boundary.**

## Learner reasoning demonstrated during class

The learner independently concluded that:

- hostile web content must not invoke the publish Tool;
- a classifier, delimiter or model self-check cannot make external content trusted;
- direct injection is introduced through user input, while indirect injection is embedded in web, document or Tool content;
- a low-privilege child cannot borrow a privileged Coordinator's publish ability;
- schema-valid cross-tenant access must be rejected by semantic validation;
- the model should receive a controlled credential reference rather than a Provider API key;
- Base64 does not make sensitive data safe to disclose;
- Provider permission does not automatically authorize disclosure to a log or another sink;
- the model cannot expand a deny-network Sandbox profile;
- Sandbox output requesting another Tool call is a new untrusted result candidate;
- timeout or kill after a dispatch marker enters `PENDING_RECONCILIATION`;
- the same operation identity with report-v1 and report-v2 is a semantic conflict;
- Tool chaining needs new authorization;
- approval for report-v1 cannot authorize the model's report-v2 candidate;
- an old-fence Worker result is rejected for current effects and retained as evidence;
- a quarantined required child blocks parent progress;
- a bad policy must be immediately quarantined and prevented from creating new execution or Egress;
- undispatched, verified and unknown incident operations require different capacity handling;
- green results under a repaired policy are insufficient until the whole affected set is resolved;
- the security core should emit only structured `ALLOW / DENY / WAIT / QUARANTINE` decisions;
- `ALLOW`, dispatch and verified outcome are distinct facts;
- compensation cannot rewrite the audit record to claim that exfiltration never happened;
- Fake runtime evidence does not prove real Provider, Tool, Sandbox or production-resource behaviour.

The learner independently reviewed seed case AS16's apparently surprising combination: a pre-dispatch `ALLOW` is compatible with a post-dispatch `PENDING_RECONCILIATION` state.

## Important questions raised by the learner

The learner asked why a Coordinator described as an audit/validation boundary would have publication ability. This exposed the confused-deputy risk and improved the design: the security Coordinator produces structured decisions, while a separate controlled dispatcher owns the actual effect capability.

The learner also noticed that the lesson had used several first-appearance terms before defining them. The teaching flow was corrected by explicitly defining trusted instruction, untrusted content, provenance, Tool candidate, security admission, delegated grant, confused deputy, schema/semantic validation, sensitive data, Egress, exfiltration and credential reference. This is a valid course-design correction, not a learner misconception.

## Misconceptions and incomplete answers corrected

1. **“Illegal input”** — The initial action was safe, but the durable classification is untrusted content with an injection signal. Untrusted data may still be useful; it simply has no instruction authority.
2. **Direct vs indirect naming** — “Bad injection” and “untrust injection” were replaced by direct injection and indirect injection.
3. **Cleanup failure** — The learner initially allowed overall success while retaining the cleanup fact. The corrected model separates Tool business success from overall security completion: cleanup failure leaves `INCOMPLETE` residual risk.
4. **Old approval** — Approval for v1 does not authorize the current v2 candidate. The v1 action is possible only if an exact current v1 candidate independently passes all checks.
5. **Old-fence result** — “Reject the Worker” was refined to reject the stale result's current write/effect while preserving it as evidence.
6. **Tool SUCCESS example** — A cross-tenant schema-valid call describes pre-dispatch semantic failure, not a mismatch between returned status and real effect. The learner corrected the example to claimed customer delivery contradicted by independent evidence.
7. **Outcome contract precision** — Customer non-receipt contradicts Tool `SUCCESS` only if `SUCCESS` promises delivery; if it promises acceptance, delivery remains a separate state.
8. **Incident closure** — An unresolved unknown effect with an owner and deadline remains managed but not resolved. Closure needs verified resolution or explicit residual-risk acceptance.
9. **Fake evidence** — “It passed in the execution runtime” was correct but incomplete; real API semantics, OS isolation, IAM, races, resource exhaustion and production configuration remain unproved.

## Instructor-authored final synthesis

This synthesis was produced by the instructor because the learner explicitly requested a summary.

Day86 secures the complete Agent path by refusing to treat generated text as authority. The application assigns trust according to a verified control channel and binds every user, webpage, document, Tool, Agent and Sandbox output as content with provenance. Direct and indirect injection classifiers can raise risk signals, but neither classifiers nor delimiters can promote content into trusted instruction.

The model sees Tools and suggests candidates. The application owns authorization. Immediately before dispatch it rechecks the original requester, current delegated grant, tenant, resource, exact Tool/version/arguments, approval, policy, fence, purpose, audience, destination and allowed fields. This prevents a privileged Coordinator from becoming a confused deputy. Raw credentials remain outside the model and are resolved from opaque references only inside a trusted adapter after authorization.

Egress and Sandbox controls reduce different risks. Egress permits only the minimum approved disclosure to one bound recipient. A Sandbox constrains files, network, environment, processes and resources, but it cannot create business authorization, make output trusted or prove that a killed process produced no external effect. Tool and Sandbox outputs therefore remain result candidates. `SUCCESS` is interpreted under an explicit outcome contract and verified against independent external evidence.

Once dispatch may have occurred, timeout or termination produces `PENDING_RECONCILIATION`. The original operation identity and reservation are retained, and blind retry is forbidden. Cleanup failure leaves an `INCOMPLETE` security result even if Tool work succeeded. Required quarantined security children block fan-in, and successful fan-in still does not authorize the parent action.

During an incident, the system first quarantines the bad policy and stops new expansion. It identifies the complete affected set, preserves append-only evidence, releases only confirmed-unused capacity, settles verified usage, reconciles unknown effects, revokes or rotates exposed credentials, and performs any withdrawal, deletion or notification through separately authorized compensation. A repaired policy is not sufficient for closure until prior affected work has been resolved or residual risk has been explicitly accepted.

The classroom implementation makes these decisions deterministic, but it is not a production security certification. It used Fake ports and an in-memory policy model, not real Provider, Tool, network Egress, OS/container Sandbox, database, Broker, Worker fleet or Secret manager.

**Assessment note:** instructor-authored synthesis completed; learner independent synthesis **NOT ASSESSED**.

## English interview assessment

- Beginner: direct/indirect injection was accurately distinguished; the core definition and trusted-instruction wording needed refinement.
- Intermediate: current authorization, credential references, Egress rechecks and Day85/Day86 composition were strong; Sandbox cleanup and outcome-contract precision needed correction.
- Senior: unknown-outcome reconciliation and bad-policy incident scope were strong; the multi-sink threat model required instruction.
- Independent final synthesis: `NOT ASSESSED` because the learner requested an instructor summary.

## Practical artifact and evidence

- `src/agent_security.py`
- `tests/test_day86_agent_security.py`
- `tests/test_day86_seed_grader.py`
- `evals/day86_agent_security_seed.jsonl`
- `evals/run_day86_seed_eval.py`
- `examples/day86_agent_security_boundary.py`

Recorded runtime results before documentation finalization: Python 3.11.5; 31/31 focused Day86 tests; 474/474 cumulative tests; 25/25 Day86 seed; 18/18 Day85 seed regression; deterministic example pass. Final repository/document checks are recorded separately and must not be inferred from this classroom note.

## Connection to Day87

Day87 should compare current frameworks and job-market expectations against the application-owned Day79–Day86 contracts. It must not pre-lock a framework or let framework routing become the security authority.
