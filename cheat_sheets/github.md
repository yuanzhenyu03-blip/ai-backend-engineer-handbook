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

## Day18 Merge Strategy & Code Review

Core idea:

```text
History is for humans; a good review improves the code, the developer, and the team.
```

History audiences:

```text
Machine -> needs parent pointers (the DAG).
Humans  -> need a readable history to understand and debug.
```

Development vs product history:

```text
Feature branch = Development History (noisy, personal: wip, fix, wip).
main           = Product History (clean, meaningful: "Add /agent endpoint").
```

Merge strategies:

| Strategy | Result | Use when |
|----------|--------|----------|
| Merge Commit | Preserve full history + join (two parents) | Commits are meaningful; want an integration record |
| Squash Merge | One meaningful product commit | Branch commits are noise; most common for features |
| Rebase Merge | Preserve commits, linear history (rewrites identity) | Few clean commits; want a straight line |

Senior review focus (not formatting):

```text
Architecture     -> fits layers and responsibilities?
Performance      -> scales; no blocking calls / N+1 / unbounded concurrency?
Security         -> auth, input validation, secrets, injection?
Maintainability  -> can the next engineer change it safely?
```

Review the code, not the coder:

```text
Bad:  "You always ignore errors."
Good: "This path can time out; should we handle it and return a clear error?"
```

Three goals of review:

```text
Improve the Code + Improve the Developer + Improve the Team.
Code review is knowledge sharing, not just approval.
```

---

## Day19 GitHub Project Management

Core idea:

```text
Manage work, not only code. If work isn't tracked, it doesn't exist.
```

Hierarchy of concerns:

```text
Issue     = Work        (the unit of work)
Label     = Metadata    (structured description)
Milestone = Goal        (a delivery target of many Issues)
Project   = Workflow    (where the work is in the pipeline)
```

| Layer | Answers | Notes |
|-------|---------|-------|
| Issue | What work exists? | Work item: collaboration, tracking, prioritization, ownership |
| Label | What kind? | Metadata for retrieval, workflow, automation |
| Milestone | Toward what goal? | Delivery target (e.g., AI Backend MVP) |
| Project | Where is it now? | Workflow board: Backlog -> In Progress -> Review -> Done |

Key distinctions:

```text
Ownership != Blame     (responsible to deliver, not at fault).
Issue answers "What work exists?"
Project answers "Where is the work now?"
```

Label is like: database index, metadata, RAG filter, vector-search filter, Kubernetes label.

Complete workflow (Day15-Day19):

```text
Idea -> Issue -> Label -> Milestone -> Project -> Branch -> Commit -> Pull Request
     -> CI -> Review -> Merge -> Deploy -> Release
```

---

## Interview Phrases

- "main is shared, releasable state, so every change goes through a Pull Request."
- "A Pull Request is Review + CI + Discussion + Audit Trail, not just a merge button."
- "CI validates rules; humans validate intent; you need both."
- "Branch Protection makes the safe path the only path, even under pressure."
- "A stale review is an approval for a state that changed, so it needs re-review."
- "Review discussions are a permanent engineering knowledge base of why."
- "Git history is for humans; the machine only needs the parent pointers."
- "Feature branches hold development history; main holds clean product history."
- "Merge commit preserves history; squash makes one product commit; rebase keeps commits linear."
- "Senior review targets architecture, performance, security, and maintainability, not formatting."
- "Review the code, not the coder: specific, kind, and constructive."
- "Code review improves the code, the developer, and the team."
- "Teams manage work, not only code; if work isn't tracked, it doesn't exist."
- "An Issue is a work item, not just a bug report."
- "Ownership means responsibility to deliver, not blame."
- "A Label is structured metadata for retrieval, workflow, and automation."
- "A Milestone is a delivery goal made of many Issues."
- "A Project manages workflow: Issue answers what work exists, Project answers where it is."
