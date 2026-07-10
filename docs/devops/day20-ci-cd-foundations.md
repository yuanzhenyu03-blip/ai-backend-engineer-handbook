# Lesson 20 — CI/CD Foundations

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day19 — GitHub Project Management

Next Lesson: Phase 2 continues — Linux, Docker

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why CI establishes a trusted quality process.
* Explain a pipeline as a standard workflow with stage dependency, fail-fast, and fast feedback.
* Explain a quality gate as risk control that protects main, production, the team, and users.
* Explain CD in terms of repeatability, consistency, reliability, and scalability.
* Explain Workflow as Code and Everything as Code.
* Assemble the full software delivery lifecycle tying Day15–Day20 together.
* Connect CI/CD to FastAPI, Playwright, AI backend, Docker, and prompt work.
* Answer beginner, intermediate, and senior CI/CD interview questions.

---

# Why This Matters

Day15–Day19 got work tracked and code integrated. Day20 answers the next question: how does a
team trust that what merges is actually safe to ship — automatically, every time?

Tech Lead Question:

A developer says "it works, I tested it locally." Should that be enough to merge to `main` and
deploy?

Student Thinking:

It ran on their machine, so maybe it is fine? But their machine is not production.

Student Answer:

"No. 'Works on my machine' is one person, one environment, one moment. The team needs a
repeatable, trusted check."

Tech Lead Review:

Exactly. Local testing is unrepeatable and invisible to the team.

```text
"I tested locally" =
  one machine + one environment + one person + one moment.
Trusted quality =
  the same automated checks, every change, visible to everyone.
```

Today's mental model — the delivery lifecycle:

```text
Idea -> Issue -> Project -> Branch -> Commit -> Pull Request
     -> CI -> Pipeline -> Quality Gate -> Merge -> CD -> Production
```

Why this matters for a backend engineer:

```text
CI turns "trust me" into an automated, repeatable process.
A pipeline makes the steps standard, ordered, and fast to fail.
A quality gate stops bad changes before they reach production and users.
CD makes deployment repeatable and reliable instead of a risky manual ritual.
```

CI/CD is how a team moves fast without breaking `main`, production, or users.

---

# Roadmap Position

```text
Day15-Day16: Git object model, branch & merge
Day17-Day18: Pull Requests, CI checks, review, merge strategy
Day19: Project management (Issue, Label, Milestone, Project)
        |
        v
Day20: CI/CD Foundations (automated quality + reliable delivery)
        |
        v
Phase 2 continues: Linux, Docker
```

Day17 introduced CI as a check on a Pull Request. Day20 generalizes it into a full pipeline and
delivery process.

```text
Manual, local trust
      |
      v
Automated pipeline + quality gates + reliable delivery
```

---

# Lesson Map

```text
Today's Lesson

1. Why "I Tested Locally" Is Not Enough
2. CI: A Trusted Quality Process
3. Pipeline: Standard Workflow, Fail Fast, Fast Feedback
4. Quality Gate: Risk Control
5. CD: Reliable, Repeatable Delivery
6. Workflow as Code and Everything as Code
7. The Full Delivery Lifecycle (Day15-Day20)
8. FastAPI, Playwright, and AI Backend Connections
9. Interview Review
```

---

# Estimated Study Time

```text
Reading: 100-130 minutes
Exercises: 60-90 minutes
Hands-on pipeline reasoning: 60-90 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Main Concepts

## Concept 1: CI — A Trusted Quality Process

Tech Lead Question:

CI runs tests automatically. But what is it really giving the team beyond "running tests"?

Student Thinking:

It runs the tests so I do not forget. Maybe that is all?

Student Answer:

"It gives everyone the same automated check on every change, so quality is not based on trust."

Tech Lead Review:

Exactly. CI (Continuous Integration) establishes a trusted quality process.

```text
Before CI: quality depends on each person remembering to test.
With CI:   every change runs the same checks automatically, visible to all.
```

```text
CI = a trusted, repeatable quality process, not just "running tests."
```

Engineering Thinking:

```text
Trust should come from an automated process, not a promise.
CI makes quality objective, repeatable, and shared.
```

Production Example:

A developer forgets to run tests; CI runs them anyway on the Pull Request and catches the
failure before merge.

Framework Connection:

CI runs the FastAPI test suite on every PR, so a broken `/chat` route is caught before it
reaches `main`.

## Concept 2: Pipeline — Standard Workflow, Fail Fast, Fast Feedback

Tech Lead Question:

If CI has to lint, test, build, and scan, should it do them in a random order, or in a
structured one?

Student Thinking:

Some steps depend on others, so order probably matters.

Student Answer:

"A pipeline: ordered stages, where a cheap check runs first and a failure stops the rest."

Tech Lead Review:

Right. A pipeline is a standard workflow of ordered stages.

```text
Pipeline:
  Lint -> Test -> Build -> Security Scan -> Package
   |       |       |          |              |
   +-------+-------+----------+--------------+--> each stage is a gate
```

Four properties:

```text
Standard Workflow -> the same stages run for every change.
Stage Dependency  -> later stages depend on earlier ones passing.
Fail Fast         -> stop at the first failing stage; do not waste time.
Fast Feedback     -> tell the developer quickly what broke.
```

Engineering Thinking:

```text
Run cheap, likely-to-fail checks first (lint) before expensive ones (integration tests).
Failing fast saves time and gives fast feedback.
```

Production Example:

Lint fails in 10 seconds, so the pipeline stops before spending 10 minutes on integration
tests — fast feedback, no wasted compute.

Framework Connection:

A pipeline lints, runs Playwright tests, builds the Docker image, and scans it — in that order,
stopping at the first failure.

## Concept 3: Quality Gate — Risk Control

Tech Lead Question:

Why should the pipeline be allowed to block a merge, not just report results?

Student Thinking:

If it only reports, people might merge anyway. Blocking forces the standard.

Student Answer:

"A quality gate stops a change that fails the checks from moving forward. It controls risk."

Tech Lead Review:

Exactly. A quality gate is risk control: only changes that pass are allowed through.

```text
Quality Gate protects:
  Main       -> keep the shared line releasable.
  Production -> keep what users run stable.
  Team       -> nobody inherits someone else's broken change.
  Users      -> defects are stopped before they ship.
```

Engineering Thinking:

```text
A gate turns "please don't merge broken code" into "you cannot merge broken code."
Risk is controlled at the boundary, automatically.
```

Production Example:

A PR with failing tests or a critical vulnerability is blocked at the gate; it cannot reach
`main` until it passes.

Framework Connection:

A quality gate blocks an AI backend PR whose evaluation checks regress answer quality, protecting
users from a worse prompt.

## Concept 4: CD — Reliable, Repeatable Delivery

Tech Lead Question:

Merging is done. Someone still SSHes into a server and copies files by hand to deploy. What is
wrong with that?

Student Thinking:

It works, but it is manual and easy to get wrong or forget a step.

Student Answer:

"Manual deployment is inconsistent and risky. It should be automated and repeatable."

Tech Lead Review:

Exactly. CD (Continuous Delivery/Deployment) makes releasing an automated, repeatable process.

```text
CD gives:
  Repeatability -> the same deploy steps every time.
  Consistency   -> every environment gets the same process.
  Reliability   -> fewer human errors, predictable outcomes.
  Scalability   -> deploy to many services/environments without more manual work.
```

Engineering Thinking:

```text
Manual deploys do not scale and are unreliable.
CD encodes deployment so it is repeatable, consistent, and safe.
```

Production Example:

Instead of a risky Friday-night manual deploy, CD ships the merged change through the same
tested path automatically.

Framework Connection:

CD builds and deploys the FastAPI Docker image the same way every time, so staging and
production match.

## Concept 5: Workflow as Code and Everything as Code

Tech Lead Question:

The pipeline itself is defined in a file in the repo. Why not configure it by clicking in a UI?

Student Thinking:

A file can be versioned and reviewed; clicks cannot.

Student Answer:

"If the workflow is code, it is versioned, reviewable, and consistent — like the rest of our
code."

Tech Lead Review:

Exactly. Workflow as Code means the pipeline is defined in the repository, not hidden in a UI.

```text
Workflow as Code gives:
  Consistency     -> everyone runs the same defined workflow.
  Version Control  -> changes to the pipeline are tracked in Git.
  Reviewability    -> pipeline changes go through Pull Requests.
  Auditability     -> you can see who changed the process, when, and why.
```

This generalizes to Everything as Code:

```text
Code as code, tests as code, workflow as code, infrastructure as code,
configuration as code, and even prompts as code.
If it is code, it is versioned, reviewed, and reproducible.
```

Engineering Thinking:

```text
UI clicks are invisible and unrepeatable.
Everything as Code makes the whole system versioned, reviewable, and reproducible.
```

Production Example:

A change to the CI pipeline is a PR reviewed like any code, so a risky pipeline edit is caught
before it ships.

Framework Connection:

The Dockerfile (infra as code) and the prompt files (prompts as code) live in Git and flow
through the same reviewed, versioned pipeline.

## Concept 6: The Full Delivery Lifecycle

Tech Lead Question:

Connect Day15 to today. What is the full path from an idea to production?

Student Thinking:

Work becomes code, code goes through checks, then it deploys automatically.

Student Answer:

"An idea becomes tracked work, then a branch and commits, then a PR with CI and a quality gate,
then merge and CD to production."

Tech Lead Review:

Exactly. The complete software delivery lifecycle:

```text
Idea
  |
  v
Issue           (Day19: track work)
  |
  v
Project         (Day19: place on the board)
  |
  v
Branch          (Day16: isolate work)
  |
  v
Commit          (Day15: immutable snapshot)
  |
  v
Pull Request    (Day17: gate the change)
  |
  v
CI              (Day17/Day20: trusted quality process)
  |
  v
Pipeline        (Day20: standard ordered stages)
  |
  v
Quality Gate    (Day20: risk control)
  |
  v
Merge           (Day16/Day18: integrate)
  |
  v
CD              (Day20: reliable delivery)
  |
  v
Production
```

Engineering Thinking:

```text
Work management, code management, quality automation, and delivery are one lifecycle.
Every earlier lesson is a stage in this pipeline.
```

Production Example:

"Add /agent endpoint" becomes an Issue, a branch, commits, a PR that passes CI and the quality
gate, is merged, and is deployed by CD to production — with no manual step.

Framework Connection:

Every AI backend change — a FastAPI route, a prompt, a Dockerfile — travels this exact lifecycle
from idea to production.

---

# Engineering Thinking

Reason about CI/CD as replacing trust and manual work with automated process.

```text
"Works on my machine" is not a quality process.
CI makes quality objective, repeatable, and shared.
A pipeline is ordered stages: fail fast, give fast feedback.
A quality gate controls risk, protecting main, production, the team, and users.
CD makes delivery repeatable, consistent, reliable, and scalable.
Workflow as Code makes the process versioned, reviewable, and auditable.
Everything as Code makes the whole system reproducible.
```

Why this design is good engineering:

```text
Automated quality catches defects no single person would catch reliably.
Fail-fast pipelines save time and money.
Gates stop risk at the boundary instead of in production.
Automated, coded delivery scales safely across services and environments.
```

Answer WHY before HOW:

```text
Why CI?           -> trust from process, not promises.
Why a pipeline?   -> standard, ordered, fail-fast stages.
Why a quality gate? -> control risk before it reaches users.
Why CD?           -> repeatable, reliable delivery instead of manual rituals.
Why workflow as code? -> versioned, reviewable, auditable process.
```

Tech Lead Review Checklist:

* Does every change run the same automated CI, not local trust?
* Is the pipeline ordered to fail fast and give fast feedback?
* Does a quality gate block changes that fail checks?
* Is deployment automated and repeatable, not manual?
* Is the workflow defined as code and reviewed like code?

---

# Classroom Exercises

## Exercise 1: Why "I Tested Locally" Is Insufficient

Question:

Explain why "it works, I tested locally" should not be enough to merge and deploy.

Think First:

How many machines, environments, and moments does a local test cover?

Starter Code:

```text
Developer: "It works on my laptop."
```

Expected Output:

```text
Local testing is one machine, one environment, one person, one moment.
It is unrepeatable and invisible to the team.
Trusted quality needs the same automated checks on every change.
```

Explanation:

CI replaces personal trust with a repeatable, shared quality process.

Follow-up Question:

What does CI provide that a local test cannot?

## Exercise 2: Design a CI Pipeline

Question:

Order the stages of a CI pipeline and justify the order.

Think First:

Which checks are cheap and likely to fail early?

Starter Code:

```text
Stages (unordered): build, test, lint, security scan, package
```

Expected Output:

```text
lint -> test -> build -> security scan -> package
Cheap, fast checks first; fail fast; expensive stages only if earlier stages pass.
```

Explanation:

Stage dependency plus fail-fast gives fast feedback and saves compute.

Follow-up Question:

What happens to later stages when lint fails?

## Exercise 3: Explain a Quality Gate

Question:

What does a quality gate protect, and how?

Think First:

What would reach production without a gate?

Starter Code:

```text
A PR has failing tests and a critical vulnerability.
```

Expected Output:

```text
The quality gate blocks the merge.
It protects main, production, the team, and users by stopping bad changes at the boundary.
```

Explanation:

A gate turns "please don't merge broken code" into "you cannot."

Follow-up Question:

Why is blocking better than only reporting results?

## Exercise 4: Manual Deployment vs CD

Question:

Compare a manual deploy with CD.

Think First:

Which is repeatable and which depends on remembering steps?

Starter Code:

```text
Manual: SSH in, copy files, restart the service by hand.
CD:     the merged change flows through an automated deploy pipeline.
```

Expected Output:

```text
Manual  -> inconsistent, error-prone, does not scale.
CD      -> repeatable, consistent, reliable, scalable.
```

Explanation:

CD encodes deployment so it is the same every time.

Follow-up Question:

Which CD property matters most when deploying to many environments?

## Exercise 5: Explain Workflow as Code

Question:

Why define the pipeline as code in the repo instead of clicking in a UI?

Think First:

Can you review and version a set of UI clicks?

Starter Code:

```text
Option A: configure CI by clicking in a web UI.
Option B: define CI in a versioned file in the repo.
```

Expected Output:

```text
Workflow as Code gives consistency, version control, reviewability, and auditability.
UI clicks are invisible and unrepeatable.
```

Explanation:

If the workflow is code, it is versioned, reviewed, and reproducible — like everything else.

Follow-up Question:

What else should be "as code" (infrastructure, config, prompts)?

---

# FastAPI Connections

```text
CI runs the FastAPI test suite on every PR.
The pipeline lints, tests, builds the image, and scans it, failing fast.
A quality gate blocks a PR with failing tests from reaching main.
CD deploys the FastAPI Docker image the same way to staging and production.
The pipeline is defined as code in the repo and reviewed like any change.
```

Example:

```text
A /agent PR triggers CI; lint and tests pass, the image builds and scans clean,
the gate allows merge, and CD deploys it automatically.
```

---

# Playwright Connections

```text
CI runs the Playwright suite headless on every PR.
Slow browser tests run after fast lint/unit stages (fail fast).
A quality gate blocks merges when end-to-end tests fail.
The test workflow is defined as code, versioned, and reviewable.
```

Example:

```text
A login-flow PR runs Playwright in CI; a failing end-to-end test blocks the gate
until it is fixed.
```

---

# AI Backend Connections

```text
CI runs prompt evaluations and smoke tests on every change.
The pipeline builds the backend image and scans dependencies.
A quality gate blocks a prompt change that regresses answer quality.
CD deploys the backend and its config reliably and repeatably.
Prompts, Dockerfiles, and pipeline definitions are all Everything as Code.
```

Example:

```text
A prompt-v2 PR runs an eval in CI; if quality drops, the gate blocks it;
if it passes, CD deploys the new prompt with the service.
```

---

# English Interview

## Key Vocabulary

* continuous integration (CI)
* continuous delivery / deployment (CD)
* pipeline
* stage dependency
* fail fast
* fast feedback
* quality gate
* repeatability / consistency / reliability / scalability
* workflow as code
* everything as code

## Why CI?

CI establishes a trusted, repeatable quality process. Every change runs the same automated
checks, visible to the whole team, so quality comes from process rather than personal promises.

## Why a pipeline?

A pipeline is a standard workflow of ordered stages with dependencies. It runs cheap checks
first, fails fast at the first problem, and gives fast feedback, saving time and compute.

## What is a quality gate?

A quality gate is risk control: only changes that pass the required checks are allowed to move
forward. It protects `main`, production, the team, and users by stopping bad changes at the
boundary.

## CI vs CD.

CI is about integrating and validating changes automatically — building and testing every
change. CD is about delivering those validated changes to environments repeatably and reliably,
replacing manual deployment.

## Why Workflow as Code?

Because a pipeline defined as code is consistent, version-controlled, reviewable through Pull
Requests, and auditable. UI-configured workflows are invisible and unrepeatable.

## Everything as Code?

Everything as Code means code, tests, workflows, infrastructure, configuration, and even prompts
are defined as versioned, reviewable files, making the whole system reproducible and auditable.

---

# Today's Takeaway

CI/CD replaces trust and manual work with an automated, coded delivery process.

```text
Ask always:
Is quality coming from a process or a promise?
Does the pipeline fail fast and gate risk?
Is delivery repeatable, and is the workflow defined as code?
```

Today's core principles:

* "Works on my machine" is not a quality process.
* CI is a trusted, repeatable quality process.
* A pipeline is ordered stages: standard workflow, stage dependency, fail fast, fast feedback.
* A quality gate is risk control that protects main, production, the team, and users.
* CD makes delivery repeatable, consistent, reliable, and scalable.
* Workflow as Code makes the process versioned, reviewable, and auditable.
* Everything as Code makes the whole system reproducible.
* Day15–Day20 form one software delivery lifecycle from idea to production.

The most important engineering sentence:

```text
CI/CD turns "trust me" into an automated, gated, repeatable path from idea to production.
```

---

# Before Next Lesson Checklist

Before the next Phase 2 lesson, confirm you can answer these without looking at the notes:

- [ ] Why is "I tested locally" not enough?
- [ ] What does CI establish beyond running tests?
- [ ] What are the four properties of a pipeline?
- [ ] What does a quality gate protect, and how?
- [ ] What four things does CD provide?
- [ ] What is the difference between CI and CD?
- [ ] Why define the workflow as code?
- [ ] What does Everything as Code mean?
- [ ] Can I trace the full lifecycle from Idea to Production?
