# GitHub Workflow Cheat Sheet

## Purpose

One-page GitHub collaboration review sheet for AI Backend Engineer preparation.

Focused on Pull Requests, CI, code review, and branch protection — the team workflow around a
shared `main`.

---

## Mental Model

```text
Developer
   |
   v
Feature Branch
   |
   v
Commit
   |
   v
Push
   |
   v
Pull Request
   |     \
   |      +-- CI (machine validates rules)
   |      +-- Human Review (validates intent)
   v
Branch Protection
   |
   v
Stable main
   |
   v
Engineering Knowledge Base
```

---

## Core Ideas

| Concept | Meaning |
|---------|---------|
| Direct push to main | Dangerous: unreviewed, untested change hits everyone |
| Pull Request | Review + CI + Discussion + Audit Trail |
| CI | Machine validates rules (build, tests, lint, coverage) |
| Code Review | Human validates intent (is this the right change?) |
| Branch Protection | Makes the gate mandatory; the safe path is the only path |
| Stale Review | Approval no longer applies because the code changed |
| Review Discussion | Preserves the "why" as engineering knowledge |

---

## Rules vs Intent

```text
CI (machine)   -> "Does the code follow the rules?"
Review (human) -> "Is this the right thing to do?"
```

Passing CI does not mean the change is correct for the business.

---

## Branch Protection can require

- a Pull Request (no direct pushes to main)
- passing CI checks
- at least one approving review
- an up-to-date branch before merge
- dismissing stale approvals after new commits

---

## Stale Review

```text
Reviewer approves commit A
        |
        v
You push commit B
        |
        v
Approval no longer covers what will merge -> stale -> re-review
```

An approval is a statement about a specific state.

---

## Interview Phrases

- "main is shared, releasable state, so every change goes through a Pull Request."
- "A Pull Request is Review + CI + Discussion + Audit Trail, not just a merge button."
- "CI validates rules; humans validate intent; you need both."
- "Branch Protection makes the safe path the only path, even under pressure."
- "A stale review is an approval for a state that changed, so it needs re-review."
- "Review discussions are a permanent engineering knowledge base of why."
