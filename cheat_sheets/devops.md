# DevOps Cheat Sheet

## Purpose

One-page DevOps review sheet for AI Backend Engineer preparation.

Focused on CI/CD foundations: pipeline, quality gate, delivery, and Everything as Code.

---

## Core Ideas

| Concept | Meaning |
|---------|---------|
| CI | Trusted, repeatable quality process (not just "running tests") |
| Pipeline | Standard workflow of ordered stages |
| Quality Gate | Risk control: only passing changes move forward |
| CD | Reliable, repeatable delivery (not manual deploy) |
| Workflow as Code | Pipeline defined in the repo, versioned and reviewed |
| Everything as Code | Code, tests, workflow, infra, config, prompts all versioned |

---

## Why "I Tested Locally" Is Not Enough

```text
Local test = one machine + one environment + one person + one moment.
Trusted quality = the same automated checks on every change, visible to all.
```

---

## Pipeline

```text
Lint -> Test -> Build -> Security Scan -> Package
```

- Standard Workflow: same stages every time.
- Stage Dependency: later stages need earlier ones to pass.
- Fail Fast: stop at the first failing stage.
- Fast Feedback: tell the developer quickly what broke.

Run cheap, likely-to-fail checks first.

---

## Quality Gate

```text
Protects: Main + Production + Team + Users
```

Only changes that pass required checks may merge. A gate turns "please don't merge broken code"
into "you cannot."

---

## CD

```text
Repeatability + Consistency + Reliability + Scalability
```

CD encodes deployment so it is the same every time, replacing risky manual deploys.

---

## Workflow as Code / Everything as Code

```text
Consistency + Version Control + Reviewability + Auditability
```

If it is code, it is versioned, reviewed, and reproducible: code, tests, workflow,
infrastructure, config, and prompts.

---

## Full Delivery Lifecycle (Day15-Day20)

```text
Idea -> Issue -> Project -> Branch -> Commit -> Pull Request
     -> CI -> Pipeline -> Quality Gate -> Merge -> CD -> Production
```

---

## Interview Phrases

- "CI is a trusted quality process, not just running tests."
- "A pipeline is a standard workflow of ordered stages that fails fast and gives fast feedback."
- "A quality gate is risk control that protects main, production, the team, and users."
- "CI validates changes; CD delivers validated changes repeatably and reliably."
- "Workflow as Code makes the process consistent, versioned, reviewable, and auditable."
- "Everything as Code makes the whole system reproducible."
