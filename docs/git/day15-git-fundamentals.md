# Lesson 15 — Git Fundamentals

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day14 — Mini Project & Backend Architecture

Next Lesson: Phase 2 continues — Git collaboration, Linux, Docker

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain Git as a project history management system, not a backup tool.
* Explain why Git's core model is a snapshot, not a pure diff.
* Explain why a commit is an immutable snapshot object.
* Distinguish the Repository, Working Directory, and a commit.
* Explain the Staging Area as the blueprint of the next commit.
* Explain the three-tree model and describe commands as tree movement.
* Explain HEAD, branch, and detached HEAD as references.
* Explain `reset --soft`, `--mixed`, and `--hard` using the three trees.
* Recover a mistaken reset with `git reflog`.
* Connect Git to FastAPI, Playwright, and AI backend work.
* Answer beginner, intermediate, and senior Git interview questions.

---

# Why This Matters

Day15 opens Phase 2 — Engineering Foundations.

Day01–Day14 built Python engineering thinking. Phase 2 begins with Git because every real
backend, FastAPI, Playwright, Docker, and AI Agent project depends on version control.

Tech Lead Question:

If you had no Git, how would you recover code you broke yesterday?

Think first.

Student Answer:

"Maybe from the IDE's local history."

Tech Lead Correction:

IDE history can help during personal development, but it is not reliable for:

```text
broken computers
team collaboration
author tracking
review history
production rollback
knowing who changed what and why
```

Engineering conclusion:

Git is not merely saving files.

```text
Git records:
code
   |
who changed it
   |
when it changed
   |
why it changed
   |
how to recover it
   |
how teams collaborate on it
```

Why a backend engineer must understand Git:

```text
Overseas teams review every change through Git history.
Git history explains why code looks the way it does.
Git enables safe rollback of a broken deploy.
Git helps debug a production failure by locating the change that caused it.
FastAPI, Playwright, Docker, prompts, and AI Agents all live in Git.
```

Git is a project history management system. That is the mental model for today.

---

# Roadmap Position

Phase 1 taught how Python behaves. Phase 2 teaches how engineers work.

```text
Phase 1: Python Foundations (Day01-Day14)
        |
        v
Day15: Git Fundamentals  <-- Phase 2 starts here
        |
        v
Phase 2 continues: Git collaboration, Linux, Docker
        |
        v
Phase 3+: Backend, FastAPI, databases, AI systems
```

Git reuses ideas from Day01–Day02:

```text
Names reference objects.
Assignment does not always copy objects.
Shared references matter.
Immutable objects make history reliable.
```

Git applies the same object thinking at the history level.

```text
Python object model
      |
      v
Git object model (snapshots, references, immutability)
```

This is why Git is the first Phase 2 lesson.

---

# Lesson Map

```text
Today's Lesson

1. Why Git Matters
2. Snapshot vs Diff
3. Commit as Immutable Snapshot
4. Repository vs Working Directory vs Commit
5. Staging Area / Index
6. Three Trees Model
7. HEAD and Branch
8. Detached HEAD
9. git reset (soft / mixed / hard)
10. git reflog
11. FastAPI, Playwright, and AI Backend Connections
12. Interview Review
```

---

# Estimated Study Time

```text
Reading: 100-130 minutes
Exercises: 60-90 minutes
Hands-on git practice: 60-90 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Main Concepts

## Concept 1: Snapshot vs Diff

Tech Lead Question:

When you commit, do you think Git stores only the changed lines?

Think first.

Student Answer:

"I think Git only saves the changed parts, like a diff."

Tech Lead Correction:

That is the common beginner model, but Git's core model is a **snapshot**, not a pure diff.

Consider two commits of a project with three files:

```text
Commit1
main.py   ---> A
api.py    ---> B
config.py ---> C

Commit2
main.py   ---> A
api.py    ---> D
config.py ---> C
```

Only `api.py` changed (B -> D).

Tech Lead Question:

If Git stored only diffs, what would happen when you check out a very old version?

Think first.

Student Answer:

"It would have to replay every diff from the beginning to rebuild the file."

Tech Lead Correction:

Exactly. Pure diff would make checking out old versions slow, because Git would rebuild each
file by replaying history.

Key idea:

```text
Git does not copy the whole project every time.
Git creates a new object only for changed content
and reuses references to unchanged objects.
```

So `main.py` (A) and `config.py` (C) are not re-stored in Commit2. Git points to the existing
objects. Only `api.py` (D) is a new object.

Connect to Day01–Day02:

```text
Names reference objects.
Assignment does not always copy.
Shared references save memory.
Immutable objects make sharing safe.
```

Git reuses unchanged objects the same way Python reuses referenced objects.

## Concept 2: Commit as Immutable Snapshot

Tech Lead Question:

Can Git edit an old commit in place?

Think first.

Student Answer:

"Because the snapshot is an immutable object, it can only be created again, not modified."

Tech Lead Correction:

Exactly right.

Teach:

```text
Git does not mutate old commits.
Changing content generates new objects.
Commit identity depends on its content hash.
Modifying old history would corrupt every later commit.
Rollback is reliable because old snapshots stay stable.
```

Analogy from Python immutability:

```python
a = "hello"
a += " world"   # creates a NEW string object, does not mutate the old one
```

Git commits work the same way at the history level: you never change a commit, you create a
new one.

```text
Immutable snapshot -> stable history -> reliable rollback
```

## Concept 3: Repository vs Working Directory vs Commit

Tech Lead Question:

What does a repository contain?

Think first.

Student Answer:

"A commit is a snapshot, and the repository only keeps the current project."

Tech Lead Correction:

The repository is NOT only the current project.

```text
Repository contains:
all commits
all blobs
all trees
branches
tags
full history
```

The current editable files are the **Working Directory**.

Required diagram:

```text
Working Directory
        |
      git add
        |
        v
Staging Area / Index
        |
      git commit
        |
        v
Repository
```

Explain:

```text
Repository stores history.
Working Directory is what the developer edits.
A commit is a historical snapshot inside the repository.
Checkout switches the Working Directory to a snapshot.
Checkout does not delete later commits.
```

## Concept 4: Staging Area / Index

Tech Lead Question:

Why does Git have a Staging Area at all? Why not commit the Working Directory directly?

Think first.

Student Answer:

"So every commit does not have to include all modified files. It gives a preparation and
selection phase before committing."

Tech Lead Correction:

Correct. The Staging Area is not just a temporary folder.

```text
The Staging Area is the blueprint of the next commit.
```

Model:

```text
Working Directory
        |
      git add
        |
        v
Index / Staging Area
        |
      git commit
        |
        v
Repository
```

`git commit` creates a commit from the Index, not directly from the Working Directory.

Classroom Question:

If the Working Directory has `api.py` v2, but the Staging Area still has `api.py` v1, what
does `git commit` save?

Student Answer:

"v1, because the snapshot is based on the Staging Area."

Tech Lead Confirmation:

Correct.

Common Bug:

```text
After committing, `git status` may still show api.py as modified,
because the commit saved the staged v1 while the Working Directory has v2.
```

## Concept 5: Three Trees Model

Git works with three trees.

```text
              Repository
            (history snapshots)
                 ^
                 |
            git commit
                 |
        Staging Area / Index
        (next commit blueprint)
                 ^
                 |
              git add
                 |
       Working Directory
       (currently edited code)
```

Read commands as movement between trees:

```text
git add      : Working Directory -> Index
git commit   : Index -> Repository
git checkout : Repository -> Working Directory, depending on HEAD / branch
git restore  : restore Working Directory or Index depending on arguments
git reset    : move branch / HEAD and optionally reset Index and Working Directory
```

Engineering Thinking:

Once you see the three trees, Git commands stop being magic. Each command just moves data
between the Working Directory, the Index, and the Repository.

## Concept 6: HEAD and Branch

Tech Lead Question:

What is HEAD?

Think first.

Student Answer:

"HEAD is like `current_commit`."

Tech Lead Refinement:

Close, but HEAD is not always a direct pointer to a commit.

Normal state:

```text
HEAD
  |
  v
Branch
  |
  v
Commit
```

Example:

```text
HEAD
  |
  v
main
  |
  v
Commit3
```

Explain:

```text
A branch is a movable reference to a commit.
HEAD usually points to the current branch.
New commits move the branch reference forward.
HEAD stays pointing to the branch while the branch moves.
```

Before commit:

```text
HEAD
 |
 v
main
 |
 v
Commit3
```

After commit:

```text
HEAD
 |
 v
main
 |
 v
Commit4
 |
 v
Commit3
```

Connect to Python references:

```python
a = obj1
a = obj2   # moves the reference; it does not mutate obj1
```

A new commit moves `main` forward the way reassigning `a` moves the name — the old commit is
not mutated.

## Concept 7: Detached HEAD

When you run:

```bash
git checkout <commit-sha>
```

Git does not keep HEAD pointing to `main`. Instead HEAD points directly to a commit.

Required diagram:

```text
main -----> Commit3

HEAD -----> Commit2
```

Teach:

```text
This is Detached HEAD.
HEAD is no longer attached to a branch.
If you create a new commit here, no branch points to it.
The new commit is not owned by any branch.
It may become dangling / unreachable after switching away.
```

Student Insight:

"A commit does not belong to any branch, because a commit is only a new snapshot object. A
branch is just a reference to a snapshot object."

Interview-quality English answer:

"A commit is an immutable snapshot object. A branch is just a movable reference to a commit. If
I create a commit while in detached HEAD state, Git creates a new commit object, but no branch
reference moves to it."

## Concept 8: git reset

Tech Lead Question:

Is `git reset` magic that "undoes" things?

Think first.

Student Answer:

"I think `--soft` only moves the branch or HEAD."

Tech Lead Correction:

Correct for `--soft`. But do not treat reset as magic. Reset moves a reference and optionally
resets trees.

Required table:

| Command | HEAD / Branch | Index | Working Directory |
|---|---|---|---|
| `git reset --soft` | moves | unchanged | unchanged |
| `git reset --mixed` | moves | reset | unchanged |
| `git reset --hard` | moves | reset | reset |

The student needed correction on `--mixed` and `--hard`:

```text
--mixed is the default; it usually means "un-add" (unstage) while keeping code.
--hard is dangerous because it also resets the Working Directory.
```

Use cases:

```text
--soft  : undo the commit but keep changes staged
--mixed : undo staging while keeping the code in the Working Directory
--hard  : discard the pointer move plus staged and working changes
```

Production Warning:

```text
git reset --hard can destroy uncommitted Working Directory changes. It is not recoverable
through reflog, because reflog tracks commits, not un-committed edits.
```

## Concept 9: git reflog

Tech Lead Question:

After `git reset --hard HEAD~1`, is the old commit gone forever?

Think first.

Student Answer:

"The commit is still in the repository, but the branch no longer references it."

Tech Lead Correction:

Exactly. The old commit usually still exists as an unreachable object for a while.

Teach:

```text
git log shows reachable history from the current branch.
git reflog shows where HEAD has been.
reflog can help recover from a mistaken reset.
Git records HEAD movement history.
Dangling / unreachable commits are not always garbage-collected immediately.
```

Recovery example:

```bash
git reflog
# find the old SHA, then either:
git checkout <sha>
# or:
git reset --hard <sha>
```

We do not expand into garbage collection internals today. The key idea: reflog is your safety
net for HEAD movements.

---

# Engineering Thinking

Reason about Git as an engineering system, not a command list.

```text
Git is an object database.
Commits are immutable snapshots.
Git uses references instead of copying.
A branch is a movable pointer.
HEAD is the current reference.
Commit identity comes from content.
The Working Directory and Repository are separate.
The Staging Area is the next commit's blueprint.
Reset is reference movement plus optional tree synchronization.
Reflog is a recovery mechanism for HEAD movement.
```

Why this design matters:

```text
Immutable snapshots make rollback reliable.
References make branching cheap and collaboration possible.
Separation of trees gives control over exactly what is committed.
Commit quality (small, focused, well-described) is what a team reviews.
```

Tech Lead Question:

Why do professional teams care so much about commit quality?

Think first.

Student Answer:

"Because other engineers read the history to understand what changed and why, especially during
review and debugging."

Tech Lead Correction:

Exactly. In a team, your commits are documentation. Clean history is an engineering asset.

---

# Production Topics

Discuss how Git shows up in real production work:

```text
Production rollback: revert or reset to a known-good commit.
Debugging who changed what: git log, git blame, git show.
Locating regressions: bisect the history between good and bad commits.
Recovering mistaken resets: git reflog.
Separating unrelated changes into different commits for clean review.
Preserving clean commit history so reviewers can follow the reasoning.
```

Production habits:

```text
Do not run `git add .` blindly; stage what you actually intend to commit.
Do not run `git reset --hard` before checking `git status`.
Protect work before dangerous commands (commit or stash first).
Remember Git history is central to code review.
```

Tech Lead Review Checklist:

* Is each commit focused on one change?
* Does the commit message explain why, not just what?
* Were unrelated changes split into separate commits?
* Was `git add .` used carelessly, sweeping in unintended files?
* Was `git status` checked before any destructive command?

---

# Classroom Exercises

## Exercise 1: Python Reference Review

Question:

Predict the output and connect it to Git.

Think First:

Does `b = a` copy the dictionary?

Starter Code:

```python
a = {"name": "FastAPI"}
b = a

a["name"] = "AI Backend"

print(a)
print(b)
```

Expected Output:

```python
{'name': 'AI Backend'}
{'name': 'AI Backend'}
```

Explanation:

`b = a` does not create a new dict. Both names reference the same mutable object.

Connect to Git:

Git reuses references to unchanged objects instead of copying the entire project.

Follow-up Question:

How is this like Git reusing unchanged blobs between commits?

## Exercise 2: Git Snapshot Experiment

Question:

Observe how checkout switches the Working Directory between snapshots.

Think First:

Does checking out an old commit delete the newer ones?

Starter Code:

```bash
mkdir git-day15
cd git-day15

git init
echo "v1" > app.txt
git add .
git commit -m "Commit1"

echo "v2" > app.txt
git commit -am "Commit2"

echo "v3" > app.txt
git commit -am "Commit3"

git log --oneline
git checkout <Commit1-SHA>
cat app.txt
git checkout <Commit3-SHA>
cat app.txt
```

Expected Output:

`app.txt` shows `v1` after checking out Commit1 and `v3` after checking out Commit3.

Explanation:

Checkout switches the Working Directory to a snapshot. Commits are not deleted by checkout.

Follow-up Question:

What state is HEAD in after `git checkout <Commit1-SHA>`?

## Exercise 3: Staging Area Experiment

Question:

Show that a commit saves the staged version, not the newest Working Directory version.

Think First:

Which version is committed if you stage v1 and then edit to v2?

Starter Code:

```bash
echo "v1" > api.py
git add api.py

echo "v2" > api.py

git commit -m "stage v1"
cat api.py
git status
```

Expected Output:

The commit contains `api.py` = v1; `cat api.py` shows v2; `git status` shows `api.py` modified.

Explanation:

`git commit` builds the snapshot from the Index, so it saved v1 while the Working Directory has
v2.

Follow-up Question:

What command would stage v2 so the next commit includes it?

## Exercise 4: Reset Mode Experiment

Question:

Determine which tree each reset mode changes.

Think First:

Which reset mode touches the Working Directory?

Starter Code:

```bash
git reset --soft HEAD~1
git status

git reset --mixed HEAD~1
git status

git reset --hard HEAD~1
git status
```

Expected Output:

After `--soft`, changes are staged. After `--mixed`, changes are unstaged but present. After
`--hard`, the changes are gone from the Working Directory.

Explanation:

`--soft` moves HEAD/branch only; `--mixed` also resets the Index; `--hard` also resets the
Working Directory.

Follow-up Question:

Which of these can lose uncommitted work permanently?

## Exercise 5: Reflog Recovery

Question:

Recover a commit after a mistaken hard reset.

Think First:

Why can the old commit still be found?

Starter Code:

```bash
git reflog
git checkout <old-sha>
```

or:

```bash
git reset --hard <old-sha>
```

Expected Output:

The old commit's SHA appears in `git reflog`, and checkout or reset restores it.

Explanation:

The commit still exists as an unreachable object, and reflog records where HEAD has been, so
you can find and restore it.

Follow-up Question:

Would reflog help recover changes that were never committed?

---

# FastAPI Connections

Git is how you manage a FastAPI codebase over time.

```text
Track route changes.
Track dependency injection changes.
Track Pydantic model changes.
Roll back a broken /chat endpoint.
Compare API behavior between commits.
Separate API-change commits from README or Docker changes.
Preserve clean backend history for review.
```

Example:

```text
The /chat endpoint starts returning 500 after a commit.
Use git log to find the suspect commit.
Use git diff to see exactly what changed in the route or model.
Roll back safely to the last working commit while you fix it.
```

Because the Service and Repository layers (Day14) each change for different reasons, keeping
their changes in separate, focused commits makes review and rollback far easier.

---

# Playwright Connections

Git protects browser automation work too.

```text
Track locator changes.
Track browser automation scripts.
Compare yesterday's working selector with today's failing selector.
Separate test changes from production code changes.
Recover a working automation version.
Keep clean history in browser test projects.
```

Example:

```text
login.py worked yesterday but fails today.
Use git diff between the two commits to see whether a locator or the browser
flow changed, then restore the working version.
```

---

# AI Backend Connections

Prompts and configuration are code, so they belong in Git.

```text
Track prompt changes.
Track workflow changes.
Track agent tool definitions.
Track Dockerfile and environment changes.
Track LLM provider abstraction changes.
Recover prompt versions that produced better results.
Separate prompt commits from backend logic commits.
Debug quality regressions caused by prompt or configuration changes.
```

Example:

```text
A prompt change reduces answer quality.
Use git diff to identify the exact prompt line that changed,
then revert to the version that produced better results.
```

This is why prompt engineering in production always lives under version control: a "better
yesterday" is only recoverable if it was committed.

---

# English Interview

## Key Vocabulary

* version control
* repository
* working directory
* staging area
* index
* commit
* snapshot
* immutable object
* branch
* movable reference
* HEAD
* detached HEAD
* dangling commit
* unreachable object
* reflog
* rollback
* code review

## What is Git?

Git is a distributed version control system. It tracks project history as immutable snapshots,
allowing engineers to collaborate, review changes, debug regressions, and roll back safely.

## What is a commit?

A commit is an immutable snapshot of the project at a specific point in time. It records the
project state and points to its parent commit.

## What is a branch?

A branch is a movable reference to a commit. Creating a new branch does not copy the project;
it creates a new reference.

## What is HEAD?

HEAD represents the current position in Git. Usually it points to the current branch, and that
branch points to a commit. In detached HEAD state, HEAD points directly to a commit.

## What is the Staging Area?

The Staging Area, also called the Index, is the blueprint of the next commit. Git commits what
is staged, not necessarily everything in the Working Directory.

## What is Detached HEAD?

Detached HEAD means HEAD points directly to a commit instead of a branch. If you create a new
commit there, no branch reference moves to it unless you create or move a branch.

## What is the difference between `reset --soft`, `--mixed`, and `--hard`?

`reset --soft` moves HEAD or the current branch only. `reset --mixed` also resets the Index.
`reset --hard` resets HEAD, the Index, and the Working Directory.

---

# Today's Takeaway

Git is a project history management system built on immutable snapshots and movable references.

```text
Ask always:
What tree am I touching — Working Directory, Index, or Repository?
Which reference is moving — HEAD or a branch?
Is this operation reversible?
```

Today's core principles:

* Git stores snapshots and reuses unchanged objects, not pure diffs.
* A commit is an immutable snapshot; you create new commits, never edit old ones.
* The Repository holds full history; the Working Directory is what you edit.
* The Staging Area is the blueprint of the next commit.
* The three trees explain every command as data movement.
* A branch is a movable reference; HEAD is the current reference.
* Detached HEAD points directly at a commit with no branch to own new commits.
* `reset` moves a reference and optionally resets the Index and Working Directory.
* `reflog` is your recovery net for HEAD movements.

The most important engineering sentence:

```text
Git is not saving files; it is recording who changed what, when, why, and how to recover it.
```

---

# Before Next Lesson Checklist

Before the next Phase 2 lesson, confirm you can answer these without looking at the notes:

- [ ] Why is Git's core model a snapshot, not a pure diff?
- [ ] Why is a commit immutable, and why does that make rollback reliable?
- [ ] What is the difference between the Repository and the Working Directory?
- [ ] Why does `git commit` build from the Index, not the Working Directory?
- [ ] Can I draw the three-tree model from memory?
- [ ] What is the difference between HEAD and a branch?
- [ ] What is detached HEAD, and what happens to a commit made there?
- [ ] Can I fill in the reset soft/mixed/hard table?
- [ ] Which reset mode can destroy uncommitted work?
- [ ] How do I recover a mistaken reset with reflog?
- [ ] How would I use Git to roll back a broken FastAPI endpoint?
- [ ] Can I explain what Git is in an interview in English?
