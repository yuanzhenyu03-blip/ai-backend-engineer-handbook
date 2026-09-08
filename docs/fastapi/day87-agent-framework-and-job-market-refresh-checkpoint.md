# Day87 — Agent Framework and Job-Market Refresh Checkpoint

## 1. Lesson Metadata

- Status: Completed at guided classroom scope
- Template: `LESSON_TEMPLATE_v2`
- Version: Classroom draft v1
- Difficulty: Intermediate
- Estimated time: 3–4 hours
- Prerequisites: Day79–Day86 application-owned Agent Runtime contracts
- Previous lesson: Day86 — Agent Security Boundaries
- Next lesson: Day88 — Framework Selection Behind a Replaceable Adapter
- Main engineering artifact: deterministic framework/job evidence validator and Day88 handoff
- Evidence level: `CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME`

This lesson did not select or install a framework and did not modify the formal
repository or application runtime.

Related artifacts: [Day86 security lesson](day86-agent-security-prompt-injection-tool-abuse-data-exfiltration-and-sandboxing.md),
[Day87 design](../../projects/ai-agent/docs/DAY87_FRAMEWORK_JOB_MARKET_REFRESH.md),
[research snapshot](../../projects/ai-agent/research/day87-framework-market-refresh.md), and
[deterministic handoff example](../../projects/ai-agent/examples/day87_framework_selection_handoff.py).

## 2. Learning Objectives

After the lesson, the learner can:

- distinguish a framework feature claim, application-contract fit and production evidence;
- collect current primary evidence with version, time, scope, conflict and confidence fields;
- classify contract fit as `NATIVE`, `ADAPTER`, `GAP`, `CONFLICT` or `UNKNOWN`;
- keep hard constraints ahead of weighted preferences;
- deduplicate active job postings and classify named-framework signals;
- state the geographic, seniority and company biases of a bounded sample;
- detect sensitivity-driven ranking instability;
- create a fail-closed Day88 handoff without selecting a framework on Day87.

## 3. Why This Matters

Choosing a popular Agent framework too early can move authorization, persistence
or coordination ownership out of the application. The result may look productive
while creating direct Tool-dispatch paths, stale approval reuse, duplicate
external effects or framework memory treated as business truth.

Teams also overread job ads. A named framework in a posting may be preferred,
incidental, or one example in “X or equivalent.” Sampling only one framework name
then counting every mirror produces a circular result. Day87 makes both decisions
auditable before Day88 spends integration effort.

## 4. Roadmap Position

```text
Day79–Day86 stable application-owned contracts
        |
        v
Day87 current framework + job evidence
        |
        v
Day88 version-pinned replaceable-adapter spike and selection decision
        |
        v
Day89–Day94 MCP lifecycle and integration
```

Day87 is deliberately after the framework-agnostic runtime. The framework is
replaceable infrastructure; it is not the business model or authorization
authority.

## 5. Lesson Map

```text
claim -> primary source -> versioned evidence -> supported scope
      -> contract-fit matrix -> hard gate -> weighted preferences
      -> sensitivity check -> Day88 handoff

role-first query -> official posting -> active verification -> canonical dedupe
                 -> signal classification -> bias statement -> bounded inference
```

## 6. Core Mental Model

```text
Feature exists
    != application contract fits
    != integration was executed
    != production is proven

Job mention
    != framework-specific requirement
    != market share
    != architecture authority
```

The shortest decision rule is:

```text
hard constraints first
weighted preferences second
unknown hard constraint -> MORE_EVIDENCE_NEEDED
```

## 7. Main Concepts

### Concept 1: Claims Need a Supported Scope

#### Tech Lead Question

If official documentation says a framework has persistence, does that prove the
Day82 durable Agent Job contract?

#### Student Thinking

The learner connected persistence to authoritative database facts and noticed
that framework memory may be stale after the database changes.

#### Student Answer

No. Framework memory is not database-persisted authoritative truth, and the
documentation has not proved the complete boundary.

#### Tech Lead Review

Correct. A native checkpoint can be useful, but Day82 also binds Job, Attempt,
Step, operation ID, state version, fence, reservation, Outbox and reconciliation.
Only the narrow documented claim becomes `NATIVE`; unchecked cells stay
`UNKNOWN` or `ADAPTER_REQUIRED`.

#### Engineering Thinking

This prevents feature-name equivalence. The application can use framework state
as a candidate or cache while continuing to own business facts.

#### Production Example

A framework checkpoint says “approved,” but the authoritative approval was
revoked after the checkpoint. Resume must reread the current approval rather than
trusting serialized memory.

#### Framework Connection

LangGraph documents persistence and node restart on interrupt/resume. Those are
narrow native behaviors, not proof of the full Day82/Day83 contract.

#### Exercise

Record the source, observed version, retrieved time, claim, supported scope,
conflict and confidence without filling absent facts from memory.

### Concept 2: Hard Constraints Precede Preference

#### Tech Lead Question

Can frequent job mentions or easier learning compensate for a Tool path that
bypasses application authorization?

#### Student Thinking

The learner classified Adapter/current-authorization placement as a hard
constraint and ease of learning as a weighted preference.

#### Student Answer

No. Occurrence count cannot prove that a framework contains the application's
hard constraints.

#### Tech Lead Review

Correct. The required path is:

```text
framework Tool candidate
  -> application Adapter
  -> current authorization and binding checks
  -> controlled dispatcher
  -> result candidate verification
```

The Coordinator validates and coordinates; it does not authorize itself.

#### Engineering Thinking

Hard constraints protect correctness and security. Weighted preferences improve
developer experience only among eligible candidates.

#### Production Example

A framework built-in Tool decorator is convenient. If it can invoke an effect
without current tenant, approval, grant, policy and fence checks, the integration
is ineligible regardless of ecosystem popularity.

#### Framework Connection

All three candidates remain possible replaceable infrastructure. Their official
feature claims do not move application authorization into the framework.

#### Exercise

Create two small weight scenarios. If the winner changes while a hard cell is
unknown, output a discriminating spike rather than a final ranking.

### Concept 3: Job Evidence Is Bounded Evidence

#### Tech Lead Question

Does “LangGraph or similar” in a required section prove LangGraph-specific
market demand?

#### Student Thinking

The learner first treated an explicit named item as required, then separated the
required general competency from the named example.

#### Student Answer

It is a required framework-class signal, but not a LangGraph-only requirement.

#### Tech Lead Review

Correct. Preserve both facts: the competency may be required, while the named
framework is one acceptable example. Required, preferred and incidental signals
must not be merged.

#### Engineering Thinking

Role-first queries reduce candidate-name sampling bias. Canonical identity uses
company, normalized role, location and posting ID. Mirrors do not add count;
distinct roles at the same company can, with concentration reported.

#### Production Example

Three distinct Fluid AI roles count as three postings because their work and
URLs differ. They also create a visible company-concentration bias, so the sample
cannot be described as three independent market participants.

#### Framework Connection

Job signals can influence learning-priority weights after contract eligibility.
They cannot choose the runtime architecture.

#### Exercise

Given active, closed, unknown and aggregator results, retain only active official
ATS/company pages and state what the remaining sample cannot prove.

### Concept 4: Evidence Has a Lifecycle

#### Tech Lead Question

Can an old PASS remain current after the observed framework version changes?

#### Student Thinking

The learner rejected reuse of the old result and preserved the record rather
than deleting it.

#### Student Answer

No. Keep it and mark it `INVALID` or `SUPERSEDED`.

#### Tech Lead Review

Correct. Quarantine downstream matrix cells, scores, shortlist and handoff facts
that depend on the old snapshot. A green replacement source does not
automatically repair conclusions still referencing the old evidence ID.

#### Engineering Thinking

Append-only research history supports audit and rollback without letting stale
facts authorize a current decision.

#### Production Example

GitHub shows one release while a package page snapshot shows another. Preserve
both, lower confidence, mark current version `UNKNOWN_PENDING_REFRESH`, and
reconcile package identity before integration.

#### Framework Connection

PydanticAI had this exact checked-source conflict during class. No version was
silently selected.

#### Exercise

Supersede one evidence record and verify that it stays readable but leaves the
current decision input set.

## 8. Common Misconceptions

### “The feature name proves our contract”

❌ Persistence, HITL or handoff names prove Day82–Day85 semantics.

✅ They establish only the scope explicitly documented or executed.

### “More job mentions win”

❌ Popularity can cover an authorization-boundary failure.

✅ Job signals are weighted preferences after hard eligibility.

### “Not found means unsupported”

❌ Checked documentation silence proves absence.

✅ Record `UNKNOWN` or `NOT_FOUND_IN_CHECKED_SOURCES`.

### “The Day87 validator is production framework code”

❌ Passing validator tests means candidate B is integrated.

✅ The validator processes offline evidence and changes no runtime Tool path.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost or risk |
|---|---|---|
| Broader candidate set | More discovery | Diluted evidence depth and slower refresh |
| Strict primary-source gate | Stronger provenance | More `UNKNOWN` when pages are unavailable |
| Version-pinned spike | Reproducible scoped proof | Must rerun after relevant upgrades |
| Application-owned Adapter | Preserves contracts and replacement | Additional integration code |
| Small job sample | Auditable and current | Cannot support global inference |

No option is universally best. The Day87 choice favors auditable boundaries
because the next step can cheaply resolve one decision-critical unknown.

## 10. Hands-on Exercises

### Exercise 1: Validate Evidence

Question: What must happen when a source has no published date?

Think First: Missing is a fact; invented precision is not.

Starter Artifact: `EvidenceRecord`

Expected Output: `published_or_updated_at="UNKNOWN"` with a real `retrieved_at`.

Explanation: Retrieval time dates the observation without forging source time.

Follow-up Question: What changes if two current official sources disagree?

### Exercise 2: Deduplicate Jobs

Question: Should a mirror increase the active posting count?

Think First: Compare canonical company, role, location and posting ID.

Starter Artifact: `dedupe_active_postings`

Expected Output: one canonical posting.

Explanation: URLs are evidence locations, not necessarily independent jobs.

Follow-up Question: Why can two distinct roles on one careers page count twice?

### Exercise 3: Build the Day88 Handoff

Question: Candidate B scores highest but the Tool authorization boundary is
`UNKNOWN`. What is the output?

Think First: Apply the hard gate before preferences.

Starter Artifact: `build_day88_handoff`

Expected Output: `MORE_EVIDENCE_NEEDED` and a fail-closed adapter spike.

Explanation: Day87 informs Day88; it does not preselect the framework.

Follow-up Question: What does a passing spike still not prove?

## 11. Relevant Framework Connections

- **LangGraph:** documented persistence, durable execution and interrupt/resume
  are relevant. Node restart semantics require idempotent effect boundaries.
- **OpenAI Agents SDK:** current release identity and high-level Tool, handoff and
  tracing patterns are relevant. Exact Day82–Day86 fit remains unproved in the
  checked evidence.
- **PydanticAI:** typed Agent/Tool concepts and durable integrations are relevant.
  The observed graph API is beta and the checked version sources conflict.

These are evidence observations, not a ranking or final selection.

## 12. AI Backend Connections

Agent frameworks sit above model/provider calls but below application business
policy. In a multi-tenant AI backend, the framework may plan and produce Tool
candidates. The application must continue to own durable Job identity,
authorization, approvals, budgets, operation reconciliation, Egress, result
verification and audited state transitions.

## 13. English Interview

The learner explicitly chose to skip the English interview because it was not
useful for this lesson's current technical objective. Status:
`SKIPPED_BY_LEARNER_AS_OUT_OF_SCOPE`. This is not a failed assessment. No English
answers are attributed to the learner. Interview practice may be revisited at the
dedicated Day94 checkpoint if relevant.

## 14. Mental Model Summary

```text
official feature claim = bounded evidence
application fit        = explicit contract comparison
production proof       = executed production-relevant evidence

hard UNKNOWN           -> MORE_EVIDENCE_NEEDED
hard GAP/CONFLICT      -> candidate ineligible
all hard proven        -> preferences may be compared
ranking flip           -> discriminating spike

active official job    -> may enter bounded sample
closed/unknown/mirror  -> adds zero active count
```

## 15. Today's Takeaway

Candidate B is not selected. Its central application-owned Tool authorization
boundary remains `UNKNOWN`, and the illustrative preference ranking is
sensitive. The honest result is a version-pinned Day88 spike behind a replaceable
Adapter. The Day87 code protects research decisions; it does not enter the
application runtime.

## 16. Before Next Lesson Checklist

- [x] Distinguish feature, contract fit and production evidence.
- [x] Keep scope, freshness, conflict, confidence, version and time.
- [x] Use `UNKNOWN` rather than inventing negative evidence.
- [x] Put hard constraints before weighted preferences.
- [x] Deduplicate job mirrors and exclude closed/unknown postings.
- [x] State sample concentration and geography limits.
- [x] Preserve invalid/superseded history without scoring it.
- [x] Produce `MORE_EVIDENCE_NEEDED` for the unknown hard boundary.
- [x] Keep Day87 code outside the application runtime.
- [ ] Run the Day88 version-pinned replaceable-adapter spike.
- [ ] Make the framework decision only from Day88 evidence.
