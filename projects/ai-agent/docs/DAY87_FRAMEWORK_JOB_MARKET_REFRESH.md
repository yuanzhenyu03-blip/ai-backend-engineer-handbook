# Day 87 — Agent Framework and Job-Market Refresh Checkpoint

> Classroom design note. It is not a framework selection, application integration, hiring forecast or production-readiness claim.

## Purpose

Day87 converts current framework and job-posting observations into bounded,
versioned evidence that can be handed to Day88. It protects the Day79-Day86
application-owned contracts from framework feature claims and market popularity.

## First-use glossary

- **Supported scope**: the smallest claim actually established by a source or run.
- **Freshness**: whether the observed evidence is current for the decision time.
- **Conflicting evidence**: primary sources that disagree and require reconciliation.
- **Contract fit**: `NATIVE`, `ADAPTER`, `GAP`, `CONFLICT` or `UNKNOWN`.
- **Hard constraint**: a condition whose failure cannot be traded for popularity or convenience.
- **Weighted preference**: a comparative benefit considered only after hard constraints pass.
- **Discriminating spike**: a minimal run designed to distinguish plausible candidates or resolve a decision-critical unknown.
- **Canonical job identity**: company, normalized role, location and posting ID.
- **Handoff readiness**: whether the evidence package is ready for Day88 work; it is not final framework approval.

## Evidence flow

```text
bounded candidate set
  -> current primary sources
  -> scoped, versioned evidence records
  -> Day79-Day86 contract-fit matrix
  -> hard-constraint gate
  -> weighted preferences and sensitivity
  -> MORE_EVIDENCE_NEEDED plus discriminating spike
  -> Day88 replaceable-adapter checkpoint
```

Job research follows a separate path:

```text
role-first query -> official ATS/careers page -> active-state verification
-> canonical dedupe -> required/preferred/incidental classification
-> sample-bias statement -> bounded transferable-skill signal
```

The two paths meet only at weighted preferences. Job evidence cannot bypass the
hard-constraint gate.

## Core invariants

1. A framework feature claim is not application-contract fit.
2. A local Fake run is not production evidence.
3. Documentation silence is `UNKNOWN`, not proof of absence.
4. Current official evidence is preferred; newest is not automatically most stable.
5. Version disagreement is preserved as conflicting evidence and reconciled before use.
6. Framework memory cannot replace authoritative business-state persistence.
7. Framework Tool dispatch remains behind the application Adapter and current authorization.
8. A built-in handoff cannot replace delegated grants, claims, leases, fences, verification and fan-in.
9. A job mirror does not increase the posting count.
10. `X or equivalent` is a transferable competency signal, not X-specific demand.
11. Distinct roles at one company may count separately, with concentration bias reported.
12. Invalid evidence and downstream conclusions remain in history as `INVALID` or `SUPERSEDED`.
13. A small-weight ranking flip requires a discriminating spike.
14. Day87 cannot make the final framework selection.

## Hard constraints and preferences

The primary hard constraint is that every candidate-framework Tool call remains
after the application Adapter and a current authorization check. Other hard
constraints preserve Day82 durable operation identity/reconciliation, Day83
exact approval binding, Day84 authoritative-state separation, Day85 handoff and
fan-in boundaries, and Day86 security admission.

Learning ease, documentation quality, ecosystem fit, observed job mentions and
implementation effort are weighted preferences. They are useful only after the
hard constraints have evidence-backed passes.

## Implemented classroom surface

- immutable evidence records with required provenance and time fields;
- explicit current/stale/unknown freshness and conflict handling;
- contract-fit proof checks that can require an executed spike;
- active primary-posting filtering and canonical deduplication;
- required/preferred/incidental framework-signal preservation;
- company-concentration reporting;
- sensitivity-flip detection;
- a fail-closed Day88 handoff with no final selection;
- 22 deterministic policy tests and one deterministic example.

## Honest execution boundary

The code validates offline records. It does not import any candidate framework,
modify the application runtime, call a Provider or Tool, access a database or
broker, or run a real authorization service. The 12-posting sample is a dated,
bounded sample, not a global labor-market census. Real Day88 adapter behavior,
Python 3.12, production infrastructure and hiring outcomes are not run or proved.

## Day88 checkpoint

The provisional handoff is `MORE_EVIDENCE_NEEDED`. Run a version-pinned spike
that forces framework Tool candidates through the application Adapter, rechecks
current authorization immediately before dispatch, and proves that direct
dispatch, revoked grant, stale approval and stale fence attempts fail closed.
Preserve the exact runtime, version, configuration, commands, results and
fake/real boundary.
