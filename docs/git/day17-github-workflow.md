# Lesson 17 — GitHub Workflow & Collaboration

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day16 — Git Branch & Merge

Next Lesson: Phase 2 continues — Linux, Docker

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why pushing directly to `main` is dangerous.
* Explain a Pull Request as Review + CI + Discussion + Audit Trail.
* Explain the split: machines validate rules, humans validate intent.
* Explain why Branch Protection protects `main`.
* Explain why a review goes stale after `main` changes.
* Explain why review discussions are preserved as engineering knowledge.
* Connect the workflow to FastAPI, Playwright, AI backend, prompt, and Docker work.
* Answer beginner, intermediate, and senior GitHub workflow interview questions.

---

# Why This Matters

Day16 gave you branches and merges on your own machine. Day17 is how a team turns that into a
safe, reviewable, auditable workflow on GitHub.

Tech Lead Question:

You finished a feature. You have write access to `main`. Why not just push straight to `main`?

Student Thinking:

It would be faster. My code works on my machine. Why add steps?

Student Answer:

"Because other people also depend on `main`, and my change might break something I did not
test."

Tech Lead Review:

Exactly. `main` is the shared, releasable line. A direct push means unreviewed, untested code
becomes everyone's problem instantly.

```text
Direct push to main
      |
      v
No review, no CI, no discussion, no audit
      |
      v
One person's mistake breaks the whole team's main
```

Why this matters for a backend engineer:

```text
main is what deploys; it must stay trustworthy.
Overseas teams gate every change through Pull Requests.
Review and CI catch bugs before they reach production.
The review history explains why the code is the way it is.
```

Today's mental model:

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

The workflow exists to keep `main` stable and to turn every change into shared knowledge.

---

# Roadmap Position

```text
Day15: Git object model
        |
        v
Day16: Branch & Merge (local integration)
        |
        v
Day17: GitHub Workflow & Collaboration (team integration)
        |
        v
Phase 2 continues: Linux, Docker
        |
        v
Phase 3+: Backend, FastAPI, databases, AI systems
```

Day16 was integration on one machine. Day17 is integration across a team, with machines and
humans as gatekeepers.

```text
Local branches and merges (Day16)
      +
Pull Requests, CI, review, protection (Day17)
      |
      v
Safe collaboration on a shared main
```

---

# Lesson Map

```text
Today's Lesson

1. Why Direct Push to main Is Dangerous
2. Pull Request = Review + CI + Discussion + Audit Trail
3. Machines Validate Rules, Humans Validate Intent
4. Branch Protection
5. Stale Review
6. Review Discussion as Engineering Knowledge
7. FastAPI, Playwright, and AI Backend Connections
8. Interview Review
```

---

# Estimated Study Time

```text
Reading: 100-130 minutes
Exercises: 60-90 minutes
Hands-on PR practice: 60-90 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Main Concepts

## Concept 1: Direct Push vs Protected main

Tech Lead Question:

If everyone can push directly to `main`, what is the worst thing that can happen on a normal
Tuesday?

Student Thinking:

Maybe two people push at once, or someone pushes code that does not build.

Student Answer:

"Someone pushes broken code to `main`, and now everyone pulling `main` is broken too."

Tech Lead Review:

Correct. Direct push to `main` means no gate between a single developer's mistake and the whole
team's shared line.

```text
Direct push:
Developer -> main    (no review, no CI, no record of why)

Protected main:
Developer -> branch -> Pull Request -> checks + review -> main
```

Engineering Thinking:

```text
main is shared state.
Unguarded shared state is where team-scale bugs come from.
A protected main forces every change through a gate.
```

Production Example:

A developer pushes a config change straight to `main` at 5pm; the deploy fails and blocks
everyone. With a protected `main`, CI would have caught it in the Pull Request.

Framework Connection:

A broken FastAPI route pushed directly to `main` can take down `/chat` for the whole team; a
Pull Request with CI runs the tests first.

## Concept 2: Pull Request = Review + CI + Discussion + Audit Trail

Tech Lead Question:

A Pull Request feels like extra bureaucracy. What is it actually giving you?

Student Thinking:

Maybe just a place to click "merge"?

Student Answer:

"It is where the change gets checked and discussed before it is allowed into `main`."

Tech Lead Review:

Right. A Pull Request bundles four things into one gate:

```text
Pull Request =
  Review      (a human reads the change)
+ CI          (machines run tests, lint, build)
+ Discussion  (questions, decisions, rationale)
+ Audit Trail (who changed what, why, and who approved)
```

Engineering Thinking:

```text
A PR is not a merge button.
It is the moment a change becomes reviewed, tested, discussed, and recorded.
```

Production Example:

A Pull Request for a new endpoint shows the diff, runs the test suite, records a reviewer's
question about error handling, and stores the approval — all before it reaches `main`.

Framework Connection:

A prompt change PR runs evaluation checks (CI), gets a teammate's review, captures why the new
wording was chosen (discussion), and leaves an audit trail for future debugging.

## Concept 3: Machines Validate Rules, Humans Validate Intent

Tech Lead Question:

CI passed. Does that mean the change is correct and should merge?

Student Thinking:

If the tests are green, maybe it is fine?

Student Answer:

"Not necessarily. Tests check that it runs, but not that it does the right thing for the
business."

Tech Lead Review:

Exactly. This is the key division of labor:

```text
CI (machine)   -> validates RULES: does it build, pass tests, lint, and meet coverage?
Review (human) -> validates INTENT: is this the right change for the business?
```

```text
Machine: "Does the code follow the rules?"
Human:   "Is this the right thing to do?"
```

Engineering Thinking:

```text
CI cannot judge whether a feature is a good idea.
A human cannot reliably re-run 5,000 tests by hand.
You need both gates: rules and intent.
```

Production Example:

CI confirms the code compiles and tests pass; a reviewer notices the endpoint returns the wrong
status code for an unauthorized user — a business-intent problem no test covered.

Framework Connection:

For an AI backend, CI checks the prompt code runs; a human reviewer judges whether the new
prompt actually improves answer quality — intent a machine cannot assess.

## Concept 4: Branch Protection

Tech Lead Question:

What stops someone from clicking merge before CI finishes or before anyone reviews?

Student Thinking:

Discipline? Hoping people follow the rules?

Student Answer:

"There must be a setting that enforces the checks, not just team etiquette."

Tech Lead Review:

Correct. Branch Protection enforces the gate so the rules are not optional.

```text
Branch Protection on main can require:
- a Pull Request (no direct pushes)
- passing CI checks
- at least one approving review
- up-to-date branch before merge
```

Engineering Thinking:

```text
Rules that depend on memory get skipped under pressure.
Branch Protection makes the safe path the only path.
```

Production Example:

At 2am during an incident, Branch Protection still requires CI and one review, preventing a
panicked direct push from making things worse.

Framework Connection:

Protecting `main` means a Dockerfile or dependency change cannot bypass CI, so the image always
builds before it reaches the shared line.

## Concept 5: Stale Review

Tech Lead Question:

A reviewer approved your PR this morning. Then you pushed three more commits. Is that approval
still meaningful?

Student Thinking:

The approval was for the earlier version, not the new commits.

Student Answer:

"No. They approved code that no longer matches what would be merged."

Tech Lead Review:

Exactly. That is a stale review: the reviewed state changed after approval.

```text
Reviewer approves commit A
        |
        v
You push commit B
        |
        v
Approval no longer covers what will merge -> review is stale
```

Engineering Thinking:

```text
An approval is a statement about a specific state.
Change the state, and the statement no longer applies.
Branch Protection can dismiss stale approvals and require re-review.
```

Production Example:

A reviewer approves a small fix; you then add a risky refactor. Dismissing the stale review
forces a fresh look at the code that will actually merge.

Framework Connection:

If a prompt PR is approved, then you rewrite the system prompt, the earlier approval no longer
reflects the prompt that will ship — it must be re-reviewed.

## Concept 6: Review Discussion as Engineering Knowledge

Tech Lead Question:

Six months later, someone asks "why does this endpoint retry three times?" Where is the answer?

Student Thinking:

Maybe in someone's memory, or a chat that got lost.

Student Answer:

"It should be in the Pull Request discussion where the decision was made."

Tech Lead Review:

Exactly. Review discussions are preserved, so the reasoning behind a change stays with the
change forever.

```text
Code shows WHAT.
Commit message shows a short WHY.
PR discussion preserves the full WHY: alternatives, trade-offs, decisions.
```

Engineering Thinking:

```text
A PR discussion is a permanent engineering knowledge base.
Future engineers read it to understand decisions, not just code.
Losing that discussion means re-litigating solved problems.
```

Production Example:

A future engineer reads the PR thread and learns the retry count was chosen to match a
provider's rate limit — avoiding a "cleanup" that would reintroduce a bug.

Framework Connection:

A prompt PR thread records why a wording was chosen and what regression it fixed, so a later
"improvement" does not silently undo it.

---

# Engineering Thinking

Reason about the workflow as gates around shared state.

```text
main is shared, releasable state.
Every change flows through a Pull Request.
CI validates rules; humans validate intent.
Branch Protection makes the gate mandatory.
Approvals are about a specific state and can go stale.
Discussions turn changes into durable knowledge.
```

Why this design is good engineering:

```text
It protects shared state from unreviewed, untested change.
It splits responsibility: machines on rules, humans on intent.
It records why, not just what, for future engineers.
It scales collaboration beyond trust and memory.
```

Answer WHY before HOW:

```text
Why not push to main? -> it is shared state; mistakes hit everyone.
Why a PR?             -> to bundle review, CI, discussion, and audit.
Why branch protection?-> to make the safe path the only path.
Why re-review?        -> because approval was for a state that changed.
Why keep discussions? -> because the why must outlive the author's memory.
```

Tech Lead Review Checklist:

* Does every change to `main` go through a Pull Request?
* Are CI checks required, not optional?
* Did a human review intent, not just trust green CI?
* Are stale approvals dismissed after new commits?
* Does the PR discussion capture the reasoning for future engineers?

---

# Classroom Exercises

## Exercise 1: Open a Pull Request

Question:

Turn a feature branch into a Pull Request.

Think First:

Why open a PR instead of merging locally into `main`?

Starter Code:

```bash
git checkout -b feature/agent
# make changes, then:
git commit -am "add /agent endpoint"
git push -u origin feature/agent
# open a Pull Request from feature/agent into main on GitHub
```

Expected Output:

A Pull Request exists proposing to merge `feature/agent` into `main`, showing the diff.

Explanation:

A PR proposes the change and opens it to CI, review, discussion, and an audit trail before it
touches `main`.

Follow-up Question:

What four things does the PR bundle together?

## Exercise 2: Trigger CI

Question:

Observe CI run on the Pull Request.

Think First:

What is CI checking that a human should not do by hand?

Starter Code:

```text
Push a commit to the PR branch.
Watch the CI checks (tests, lint, build) run on the PR.
```

Expected Output:

CI status appears on the PR (passing or failing checks).

Explanation:

CI validates the rules automatically: build, tests, lint, coverage.

Follow-up Question:

Does passing CI mean the change is correct for the business?

## Exercise 3: Request Changes

Question:

As a reviewer, request changes on the PR.

Think First:

What kind of problem does a human catch that CI does not?

Starter Code:

```text
Review the diff.
Leave a comment about intent (e.g., wrong status code for unauthorized users).
Select "Request changes".
```

Expected Output:

The PR shows a "changes requested" review with a comment.

Explanation:

Humans validate intent — whether the change is the right thing to do.

Follow-up Question:

Why is intent something CI cannot judge?

## Exercise 4: Approve

Question:

Approve the PR after the fix.

Think First:

What exactly are you approving?

Starter Code:

```text
Push the fix commit.
Re-review the updated diff.
Select "Approve".
```

Expected Output:

The PR shows an approving review.

Explanation:

Approval is a statement about the current reviewed state of the change.

Follow-up Question:

What happens to this approval if new commits are pushed afterward?

## Exercise 5: Simulate a Stale Review

Question:

Make an approval go stale.

Think First:

Why would an old approval no longer apply?

Starter Code:

```text
After approval, push another commit to the PR branch.
Observe that the approval no longer covers the latest commit (or is dismissed).
```

Expected Output:

The prior approval no longer reflects the code that will merge; re-review is needed.

Explanation:

An approval is about a specific state; changing the state makes it stale.

Follow-up Question:

How can Branch Protection enforce re-review automatically?

## Exercise 6: Merge

Question:

Merge the PR into `main`.

Think First:

What conditions should be met before merge is allowed?

Starter Code:

```text
Ensure CI passes and a fresh approval exists.
Merge the Pull Request into main.
```

Expected Output:

The change lands on `main` with CI green, an approval, and a recorded discussion.

Explanation:

The gate (CI + review + protection) is satisfied, so the change safely joins the shared line
with a full audit trail.

Follow-up Question:

Where does the reasoning behind this change live six months from now?

---

# FastAPI Connections

```text
Open a feature branch for a new endpoint; never push it straight to main.
The PR runs the FastAPI test suite in CI.
A reviewer checks status codes, dependency injection, and error handling (intent).
Branch Protection blocks merge until tests pass and one review approves.
The PR thread records why the route was designed this way.
```

Example:

```text
A PR adds /agent. CI runs pytest; a reviewer flags a missing auth check;
after a fix, the stale approval is dismissed and re-approved before merge.
```

---

# Playwright Connections

```text
A test-fix branch opens a PR instead of pushing to main.
CI runs the Playwright suite headless.
A reviewer checks whether the new selector is stable, not just passing today.
Branch Protection keeps flaky test changes out of main until reviewed.
```

Example:

```text
A PR updates login selectors; CI runs the browser tests; the reviewer asks
why the selector changed, and the answer stays in the PR thread.
```

---

# AI Backend Connections

```text
Prompt changes go through a PR, not a direct push.
CI runs evaluation or smoke checks on the prompt or agent code.
A human reviews whether answer quality actually improved (intent).
Branch Protection guards main for prompt, tool-definition, and Dockerfile changes.
The PR discussion records why a prompt or provider change was made.
```

Example:

```text
A PR ships prompt-v2. CI runs an eval; a reviewer confirms quality improved;
the thread records the regression it fixed so nobody reverts it later.
```

---

# English Interview

## Key Vocabulary

* pull request
* code review
* continuous integration (CI)
* branch protection
* required checks
* approving review
* request changes
* stale review
* audit trail
* rules vs intent

## Why shouldn't developers push directly to main?

Because `main` is shared, releasable state. A direct push skips review and CI, so one person's
untested mistake immediately breaks everyone who depends on `main`.

## Why do Pull Requests exist?

A Pull Request bundles review, CI, discussion, and an audit trail into one gate before a change
reaches `main`. It makes every change reviewed, tested, discussed, and recorded.

## What is the difference between CI and code review?

CI is a machine validating rules — build, tests, lint, coverage. Code review is a human
validating intent — whether the change is the right thing to do. You need both.

## Why is Branch Protection important?

Branch Protection enforces the gate so required checks and reviews cannot be skipped. It makes
the safe path the only path, even under pressure.

## What is a stale review?

A stale review is an approval that no longer applies because the code changed after it was
given. The approval was about an earlier state, so re-review is needed.

## Why preserve review discussions?

Because the discussion records why a change was made — alternatives, trade-offs, and decisions.
It becomes a durable engineering knowledge base so future engineers do not re-litigate solved
problems.

---

# Today's Takeaway

The GitHub workflow is a set of gates that protect shared state and preserve knowledge.

```text
Ask always:
Is this change going through the gate, or around it?
Did a machine check the rules and a human check the intent?
Is the reasoning recorded for the next engineer?
```

Today's core principles:

* Direct pushes to `main` expose the team to unreviewed, untested change.
* A Pull Request is Review + CI + Discussion + Audit Trail.
* Machines validate rules; humans validate intent.
* Branch Protection makes the safe path mandatory.
* Approvals are about a specific state and go stale when the state changes.
* Review discussions are a permanent engineering knowledge base.

The most important engineering sentence:

```text
Protect shared state with gates: machines check the rules, humans check the intent, and the
discussion keeps the why.
```

---

# Before Next Lesson Checklist

Before the next Phase 2 lesson, confirm you can answer these without looking at the notes:

- [ ] Why is a direct push to `main` dangerous?
- [ ] What four things does a Pull Request bundle together?
- [ ] What is the difference between CI validating rules and a human validating intent?
- [ ] What does Branch Protection enforce, and why?
- [ ] What is a stale review, and why does it happen?
- [ ] Why are review discussions preserved as engineering knowledge?
- [ ] How would I use this workflow for a FastAPI endpoint or an AI prompt change?
