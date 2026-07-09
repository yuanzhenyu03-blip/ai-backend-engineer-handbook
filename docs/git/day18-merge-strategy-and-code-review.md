# Lesson 18 — Merge Strategy & Code Review

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day17 — GitHub Workflow & Collaboration

Next Lesson: Phase 2 continues — Linux, Docker

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why Git history is designed for humans.
* Distinguish development history from product history.
* Explain merge commit, squash merge, and rebase merge, and when to use each.
* Explain what senior engineers review: architecture, performance, security, maintainability.
* Explain the principle "review the code, not the coder."
* Explain the three goals of review: improve the code, the developer, and the team.
* Connect merge strategy and review to FastAPI, Playwright, AI backend, prompt, and Docker work.
* Answer beginner, intermediate, and senior merge/review interview questions.

---

# Why This Matters

Day17 got changes safely into `main` through Pull Requests. Day18 is about the shape of the
history you leave behind and the quality of the review that shapes it.

Tech Lead Question:

Git could record history any way it wants. Who is that history actually for — the computer or
the people?

Student Thinking:

The computer needs parents to rebuild versions. But I also read `git log` to understand
changes.

Student Answer:

"The machine only needs the parent links. The readable history is for humans."

Tech Lead Review:

Exactly. The machine only needs the DAG to function. Everything readable — commit messages, a
clean log, a meaningful history — exists so humans can understand the project later.

```text
Machine needs: parent pointers (the DAG works either way).
Humans need:   a history they can read, review, and debug from.
```

Why this matters for a backend engineer:

```text
Merge strategy decides what future engineers read in the history.
Code review decides whether the change is safe, maintainable, and understood.
Both are about people, not just code correctness.
```

Today's mental model:

```text
History is for humans; review is how a team thinks together.
```

---

# Roadmap Position

```text
Day16: Branch & Merge (local integration)
        |
        v
Day17: GitHub Workflow (Pull Requests, CI, protection)
        |
        v
Day18: Merge Strategy & Code Review (history shape + review quality)
        |
        v
Phase 2 continues: Linux, Docker
```

Day17 was the gate. Day18 is what the gate leaves behind: a readable history and a stronger
team.

```text
Safe integration (Day17)
      +
Readable history + high-quality review (Day18)
      |
      v
A codebase future engineers can trust and understand
```

---

# Lesson Map

```text
Today's Lesson

1. Git History Is for Humans
2. Development History vs Product History
3. Merge Commit
4. Squash Merge
5. Rebase Merge
6. What Senior Engineers Review
7. Review the Code, Not the Coder
8. Three Goals of Review
9. FastAPI, Playwright, and AI Backend Connections
10. Interview Review
```

---

# Estimated Study Time

```text
Reading: 100-130 minutes
Exercises: 60-90 minutes
Hands-on merge/review practice: 60-90 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Main Concepts

## Concept 1: Git History Is for Humans

Tech Lead Question:

If Git only needs parent pointers to function, why do we care about clean commit messages and a
readable log?

Student Thinking:

The code runs the same either way, so maybe it does not matter?

Student Answer:

"It matters for the people who read the history later to understand or debug it."

Tech Lead Review:

Correct. History has two audiences with different needs:

```text
Machine: needs the DAG (parents) to rebuild and traverse versions.
Humans:  need a readable story of what changed and why.
```

Engineering Thinking:

```text
A history the machine can use but humans cannot read is a liability.
Merge strategy is a choice about how readable that history is.
```

Production Example:

Six months later, someone runs `git log` to find why a change was made. A clean, human-oriented
history answers in seconds; a noisy one wastes an afternoon.

Framework Connection:

Debugging an AI backend regression means reading history to find the commit that changed a
prompt or route — readable history is what makes that fast.

## Concept 2: Development History vs Product History

Tech Lead Question:

While building a feature you commit "wip", "fix typo", "try again", "actually fix it". Should
`main` show all of that?

Student Thinking:

That is how I actually worked, but it is noisy for others.

Student Answer:

"The messy commits are my development process; `main` should show the finished, meaningful
change."

Tech Lead Review:

Exactly. There are two kinds of history:

```text
Development History (feature branch):
  wip -> fix typo -> try again -> actually fix it
  = how the work really happened, noisy, personal.

Product History (main):
  "Add /agent endpoint with auth"
  = what the product gained, clean, meaningful.
```

Engineering Thinking:

```text
The feature branch is your workshop; main is the showroom.
Merge strategy decides how much of the workshop shows up in the showroom.
```

Production Example:

A two-week feature has 40 messy commits. On `main`, the team wants to read one clear entry:
what the product gained.

Framework Connection:

A prompt experiment branch may have 20 trial commits; `main` should record the single decision:
"Adopt prompt-v2 for better summaries."

## Concept 3: Merge Commit

Tech Lead Question:

When would you want to keep every commit from the feature branch in `main`?

Student Thinking:

Maybe when the individual steps are meaningful and worth preserving.

Student Answer:

"When the full engineering history matters and I want to see how it was built."

Tech Lead Review:

Right. A merge commit preserves the complete engineering history.

```text
main:    A --------------------- M
                                 / \
feature:            B -> C -> D -
```

`M` is the merge commit with two parents; all of `B, C, D` remain in history.

```text
Merge Commit = preserve complete development history + a join point.
```

Engineering Thinking:

```text
Use it when the individual commits carry real meaning,
or when you want an explicit record that a branch was integrated.
```

Production Example:

Integrating a long-lived release branch, where each commit is a deliberate step, favors a merge
commit so nothing is flattened.

Framework Connection:

Merging a large FastAPI migration where each commit migrates one module keeps those steps
visible for future debugging.

## Concept 4: Squash Merge

Tech Lead Question:

Your feature branch has 40 noisy commits. What should land on `main`?

Student Thinking:

Not all 40 — that would bury the meaningful change.

Student Answer:

"Compress them into one clean commit that describes the finished feature."

Tech Lead Review:

Exactly. Squash merge compresses many noisy commits into one meaningful product commit.

```text
feature: wip -> fix -> wip -> fix -> done
                     |
                  squash
                     v
main:    "Add /agent endpoint with auth"   (one clean commit)
```

```text
Squash Merge = product history: one meaningful commit per feature.
```

Engineering Thinking:

```text
Use it when the branch's individual commits are noise,
and only the finished change matters to the product history.
This is the most common strategy for feature branches.
```

Production Example:

A UI or endpoint feature with dozens of "wip" commits squashes into one entry so `main` stays
readable.

Framework Connection:

A Playwright test-fix branch with many "try selector" commits squashes into one: "Stabilize
login test selectors."

## Concept 5: Rebase Merge

Tech Lead Question:

You want to keep your individual commits, but you also want `main` to stay a straight line with
no merge commits. Can you have both?

Student Thinking:

Merge commit keeps commits but adds a join; squash loses the commits. Is there a middle option?

Student Answer:

"Replay my commits on top of main so they stay separate but the history is linear."

Tech Lead Review:

Correct. Rebase merge preserves the individual commits while keeping history linear.

```text
Before:
main:    A -> B
feature:      \-> C -> D

After rebase merge:
main:    A -> B -> C' -> D'      (linear, no merge commit, commits preserved)
```

```text
Rebase Merge = preserve commits + linear history (no merge commit).
```

Engineering Thinking:

```text
Use it when each commit is meaningful AND you want a clean straight line.
Note: it rewrites commit identity (C -> C'), so it is for branch integration,
not for shared/published history.
```

Production Example:

A well-crafted feature with a few clean, meaningful commits rebases onto `main` for a tidy
linear log.

Framework Connection:

A Dockerfile change split into "add base image", "install deps", "copy app" can rebase so each
clean step stays, linearly, on `main`.

## Concept 6: What Senior Engineers Review

Tech Lead Question:

A junior reviewer comments only on indentation and variable names. What are they missing?

Student Thinking:

Formatting matters, but there must be bigger things to check.

Student Answer:

"They are missing the important stuff: design, performance, security, whether it is
maintainable."

Tech Lead Review:

Exactly. Formatting is what a linter handles. Senior reviewers focus on what machines cannot
judge.

```text
Architecture     -> does this fit the layers and responsibilities? (Day14)
Performance      -> will this scale; any N+1 queries, blocking calls, unbounded concurrency?
Security         -> auth, input validation, secrets, injection risks?
Maintainability  -> can the next engineer understand and change this safely?
```

Engineering Thinking:

```text
Let tools handle formatting and style.
Spend human attention on architecture, performance, security, and maintainability.
Review the big risks before the small nits.
```

Production Example:

A reviewer approves nicely formatted code that opens a blocking DB call inside an async
endpoint (Day13) — a performance bug the linter never saw.

Framework Connection:

Reviewing an AI backend PR: does it bound concurrency to the OpenAI rate limit, validate the
prompt input, and keep the service stateless?

## Concept 7: Review the Code, Not the Coder

Tech Lead Question:

Which comment is better: "You always write sloppy code" or "This function has two
responsibilities; can we split it?"

Student Thinking:

The first attacks the person; the second talks about the code.

Student Answer:

"The second. It focuses on the code and suggests an improvement."

Tech Lead Review:

Exactly. Good review targets the code, not the person.

```text
Bad:  "You always forget error handling."   (about the coder)
Good: "This path can raise; should we handle the timeout here?"  (about the code)
```

Engineering Thinking:

```text
Review the code, not the coder.
Be specific, be kind, propose a direction.
The goal is a better change, not a judged person.
```

Production Example:

Rewriting "this is wrong" into "this returns 200 on an auth failure; should it be 401?" keeps
the discussion productive and specific.

Framework Connection:

On a prompt PR, "your prompt is bad" helps no one; "this wording may cause the model to skip
citations — can we make it explicit?" improves the prompt.

## Concept 8: Three Goals of Review

Tech Lead Question:

Beyond catching bugs, what else is a code review for?

Student Thinking:

Maybe teaching, or spreading knowledge across the team?

Student Answer:

"It improves the code, but also helps the developer learn and keeps the team aligned."

Tech Lead Review:

Exactly. Review has three goals at once:

```text
Improve the Code      -> catch bugs, risks, and design issues.
Improve the Developer -> share knowledge so the author grows.
Improve the Team      -> spread understanding and shared standards.
```

Engineering Thinking:

```text
A review that only gatekeeps wastes most of its value.
The best reviews teach, align the team, and raise everyone's bar.
Code review is knowledge sharing, not just approval.
```

Production Example:

A senior explains why an endpoint should be stateless; the author learns it, and the whole team
reads the thread and applies it next time.

Framework Connection:

A review thread about bounding OpenAI concurrency becomes a lesson the entire AI backend team
reuses in future PRs.

---

# Engineering Thinking

Reason about merge strategy and review as human-facing decisions.

```text
Git history serves humans, not just the machine.
Feature branches hold development history; main holds product history.
Merge commit preserves history; squash makes product history; rebase keeps commits linear.
Senior review targets architecture, performance, security, and maintainability.
Good review targets the code, not the coder.
Review improves the code, the developer, and the team.
```

Why this design is good engineering:

```text
Readable history makes future debugging fast.
The right merge strategy keeps main meaningful without losing needed detail.
Review on real risks prevents production incidents machines cannot catch.
Kind, specific review builds a stronger, aligned team.
```

Answer WHY before HOW:

```text
Why care about history? -> humans read it to understand and debug.
Why multiple strategies? -> different branches need different history shapes.
Why review architecture first? -> tools handle formatting; humans handle risk.
Why "code not coder"?   -> to keep review productive and the team strong.
```

Tech Lead Review Checklist:

* Does `main` read as clean product history?
* Was the merge strategy chosen deliberately (preserve, squash, or linear)?
* Did review cover architecture, performance, security, and maintainability?
* Were comments about the code, specific, and constructive?
* Did the review teach something the team can reuse?

---

# Classroom Exercises

## Exercise 1: Merge Commit vs Squash Merge

Question:

A feature branch has commits: "wip", "fix", "wip", "done". Compare what `main` looks like after
a merge commit versus a squash merge.

Think First:

Which strategy keeps all four commits, and which produces one?

Starter Code:

```bash
# Merge commit:
git checkout main
git merge --no-ff feature      # keeps B, C, D + a merge commit M

# Squash merge:
git checkout main
git merge --squash feature
git commit -m "Add feature X"  # one clean commit
```

Expected Output:

Merge commit keeps all feature commits plus a join; squash produces a single product commit on
`main`.

Explanation:

Merge commit preserves development history; squash creates clean product history.

Follow-up Question:

Which one would you want on `main` for a noisy 40-commit branch?

## Exercise 2: Choose a Merge Strategy

Question:

For each case, pick merge commit, squash, or rebase and justify it.

Think First:

Are the individual commits meaningful, noisy, or clean-and-few?

Starter Code:

```text
Case A: 40 "wip" commits for one small feature.
Case B: a release branch where each commit is a deliberate migration step.
Case C: 3 clean, meaningful commits; team wants a linear main.
```

Expected Output:

```text
Case A -> Squash (noise into one product commit).
Case B -> Merge commit (preserve meaningful steps + integration point).
Case C -> Rebase (keep commits, linear history).
```

Explanation:

Match the strategy to how meaningful the commits are and the history shape you want.

Follow-up Question:

Which strategy rewrites commit identity, and why does that limit its use?

## Exercise 3: Review a FastAPI Endpoint

Question:

Review this endpoint. What senior-level issues do you raise?

Think First:

Look past formatting: architecture, performance, security, maintainability.

Starter Code:

```python
@app.get("/user/{id}")
async def get_user(id):
    conn = connect_db()               # blocking, unclosed
    user = conn.execute(f"SELECT * FROM users WHERE id = {id}")  # SQL injection
    return user
```

Expected Output:

```text
Security: SQL injection via f-string; use parameters.
Performance: blocking DB call in an async endpoint; use an async driver or to_thread.
Architecture: route talks to the DB directly; move to a service/repository (Day14).
Maintainability: missing type hints and error handling.
```

Explanation:

Senior review targets risk and design, not indentation.

Follow-up Question:

Which of these would CI likely miss?

## Exercise 4: Rewrite a Poor Review Comment

Question:

Turn a bad comment into a constructive one.

Think First:

Is the comment about the coder or the code? Is it specific and actionable?

Starter Code:

```text
Bad comment: "This is messy and you always ignore errors."
```

Expected Output:

```text
Good comment: "This request can time out and raise; can we handle the timeout and return a
clear error here? Splitting the parsing and the request into two functions would also make it
easier to test."
```

Explanation:

Review the code, not the coder: specific, kind, and actionable, aimed at a better change.

Follow-up Question:

Which of the three review goals (code, developer, team) does a good comment serve?

---

# FastAPI Connections

```text
Squash a noisy endpoint feature branch into one clean product commit on main.
Use a merge commit for a large, multi-module migration where steps matter.
Review endpoints for architecture (thin router/service), performance (no blocking calls),
security (auth, input validation), and maintainability (types, error handling).
Keep comments about the code, specific and constructive.
```

Example:

```text
A /agent PR with 30 wip commits is squashed into "Add /agent endpoint with auth";
the reviewer flags a blocking DB call as a performance issue before merge.
```

---

# Playwright Connections

```text
Squash "try selector" churn into one commit: "Stabilize login test selectors."
Review whether a new selector is robust and maintainable, not just green today.
Keep review comments about the test code, not the author.
```

Example:

```text
A test branch with many selector attempts squashes into a single meaningful commit;
the reviewer asks whether the selector is stable across locales.
```

---

# AI Backend Connections

```text
Squash prompt-experiment branches into one decision commit: "Adopt prompt-v2."
Use a merge commit when a change set has meaningful, separable steps.
Review prompt and agent PRs for correctness of intent, concurrency limits, and safety.
Frame prompt feedback about the prompt, not the author.
Review threads about rate limits and statelessness become team knowledge.
```

Example:

```text
A prompt branch with 20 trials squashes into "Adopt prompt-v2 for better summaries";
the reviewer notes it must stay under the OpenAI rate limit, and the team reuses that.
```

---

# English Interview

## Key Vocabulary

* development history
* product history
* merge commit
* squash merge
* rebase merge
* linear history
* code review
* architecture / performance / security / maintainability
* review the code, not the coder

## Why does Git support multiple merge strategies?

Because different branches need different history shapes. Some changes should preserve every
commit, some should collapse noise into one product commit, and some should stay linear. The
strategy is a choice about what humans read in the history.

## Merge commit vs squash merge.

A merge commit preserves the full development history and adds a join with two parents. A squash
merge compresses many commits into a single meaningful product commit, keeping `main` clean.

## When would you use a rebase merge?

When each commit is meaningful and you want a linear history with no merge commit. Rebase
replays the commits on top of the target, so it rewrites commit identity and is used for
integrating a branch, not for shared published history.

## What do senior reviewers focus on?

Architecture, performance, security, and maintainability — the risks machines cannot judge.
Formatting and style are left to linters.

## Why is Git history important?

Because history is for humans: future engineers read it to understand decisions and debug
regressions. A readable history makes that fast; a noisy one wastes time.

## Explain "review the code, not the coder."

Good review comments target the code, are specific and constructive, and propose a direction.
They avoid personal criticism, so the review stays productive and improves the code, the
developer, and the team.

---

# Today's Takeaway

Merge strategy shapes the history humans read; review shapes the code and the team.

```text
Ask always:
Is main readable as product history?
Did I pick the merge strategy on purpose?
Did I review real risk, about the code, in a way that teaches?
```

Today's core principles:

* Git history is designed for humans, not just the machine.
* Feature branches hold development history; `main` holds product history.
* Merge commit preserves history; squash makes clean product history; rebase keeps commits
  linear.
* Senior review targets architecture, performance, security, and maintainability.
* Review the code, not the coder — specific, kind, constructive.
* Review improves the code, the developer, and the team.

The most important engineering sentence:

```text
History is for humans; a good review improves the code, the developer, and the team.
```

---

# Before Next Lesson Checklist

Before the next Phase 2 lesson, confirm you can answer these without looking at the notes:

- [ ] Why is Git history designed for humans?
- [ ] What is the difference between development history and product history?
- [ ] When would you use a merge commit?
- [ ] When would you use a squash merge?
- [ ] When would you use a rebase merge, and what does it rewrite?
- [ ] What do senior engineers review beyond formatting?
- [ ] What does "review the code, not the coder" mean?
- [ ] What are the three goals of code review?
- [ ] How would I choose a merge strategy for a FastAPI or prompt feature branch?
