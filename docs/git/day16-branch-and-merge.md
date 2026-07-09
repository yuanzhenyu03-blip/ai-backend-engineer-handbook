# Lesson 16 — Git Branch & Merge

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day15 — Git Fundamentals

Next Lesson: Phase 2 continues — Git collaboration, Linux, Docker

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why branches exist from the engineering problem they solve.
* Explain that a branch is a movable reference, not a copy.
* Explain why branch creation is nearly instant.
* Explain HEAD and how only the current branch moves on commit.
* Explain fast-forward merge as reference movement.
* Explain three-way merge and why a merge commit has two parents.
* Explain why merge conflicts happen and why Git refuses to guess.
* Explain Git history as a Directed Acyclic Graph (DAG).
* Connect branching to FastAPI, Playwright, AI backend, agent, and Docker work.
* Answer beginner, intermediate, and senior branch/merge interview questions.

---

# Why This Matters

Day15 showed that Git is an object model: immutable commits and movable references. Day16
builds directly on that: branches and merges are just references and objects in motion.

Tech Lead Question:

You are running production on `main`. A new AI Agent feature needs two weeks. A login bug must
be fixed today. Can one single line of development serve all three?

Student Thinking:

If I keep coding the two-week feature on `main`, the urgent bug fix is stuck behind unfinished
work. If I fix the bug on the same line, I mix it with half-done feature code.

Student Answer:

"Two independent tasks should proceed without affecting each other. One development line cannot
satisfy both."

Tech Lead Review:

Exactly. That is the entire reason branches exist.

```text
main      -> production, must stay releasable
feature   -> two-week AI Agent work, isolated
hotfix    -> today's login fix, isolated
```

A branch isolates independent work so unfinished changes never block or corrupt a releasable
line. This is not a Git trick; it is a solution to a real engineering problem.

Why this matters for a backend engineer:

```text
Ship a hotfix without shipping half-built features.
Let multiple engineers work in parallel.
Keep main releasable at all times.
Integrate finished work deliberately, through a merge.
```

Today's mental model:

```text
Branch and Merge are the Git object model in motion.
```

---

# Roadmap Position

```text
Day15: Git object model (commits, references, immutability)
        |
        v
Day16: Branch & Merge (references in motion, history as a DAG)
        |
        v
Phase 2 continues: Git collaboration, Linux, Docker
        |
        v
Phase 3+: Backend, FastAPI, databases, AI systems
```

Day15 gave you the objects. Day16 moves the references.

```text
Immutable commits (Day15)
      +
Movable references (Day16 branches)
      |
      v
Parallel work integrated through merges
```

Note: GitHub, pull requests, code review, rebase, and cherry-pick are Phase 2 later lessons,
not today. Today is purely the local branch-and-merge object model.

---

# Lesson Map

```text
Today's Lesson

1. Why Branch Exists
2. Branch = Movable Reference
3. Why Branch Creation is Instant
4. HEAD and Current Branch
5. Fast-forward Merge
6. Three-way Merge
7. Merge Conflict
8. Git as a DAG
9. FastAPI, Playwright, and AI Backend Connections
10. Interview Review
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

## Concept 1: Why Branch Exists

Tech Lead Question:

Before learning any command, tell me: what problem would force us to invent branches?

Student Thinking:

Maybe to keep a backup? Or to let two people edit at once?

Student Answer:

"To let two independent tasks proceed without affecting each other."

Tech Lead Review:

Correct. Derive it from the scenario:

```text
main is running production.
The AI Agent feature needs two weeks.
The login bug must be fixed today.
```

A single development line cannot satisfy both the long feature and the urgent fix without one
blocking or corrupting the other.

Engineering Thinking:

```text
Branch exists to isolate independent work.
Isolation keeps main releasable while other work continues.
```

Production Example:

You branch `hotfix/login`, fix the bug, and release it today, while `feature/agent` keeps
evolving untouched.

Framework Connection:

A FastAPI feature branch lets you build a new `/agent` endpoint without destabilizing the
running `/chat` route on `main`.

## Concept 2: Branch = Movable Reference

Tech Lead Question:

When you run `git branch feature`, does Git copy the project?

Student Thinking:

It probably duplicates the files so I have a separate version.

Student Answer:

"I assumed it copies the code into a new folder."

Tech Lead Review:

No. A branch is not a copy. A branch is only a movable reference to a commit.

Required diagram:

```text
main
  |
  v
Commit3
  ^
  |
feature
```

Both `main` and `feature` are references pointing at the same commit. Nothing was copied.

Relate to Python:

```python
a = obj
b = obj   # a and b reference the same object; no copy
```

Just as `a` and `b` are two names for one object, `main` and `feature` are two references to
one commit.

Engineering Thinking:

```text
A branch is a lightweight pointer, not a duplicate of the project.
```

Framework Connection:

Creating `feature/prompt-v2` for an AI backend does not duplicate the repo; it just adds a
reference you can move as you commit prompt changes.

## Concept 3: Why Branch Creation is Instant

Tech Lead Question:

If your repository were 5GB, how long should creating a branch take?

Student Thinking:

If it copies 5GB, it would take a while.

Student Answer:

"Copying 5GB would be slow, but `git branch` feels instant."

Tech Lead Review:

Exactly. Derive the conclusion:

```text
If Git copied the whole project, branch creation would be slow.
git branch is almost instant.
Therefore Git is not copying the project.
```

Engineering conclusion:

```text
Git creates a new reference, not a new project.
```

A branch is one small file recording a commit hash. Creating it is O(1), no matter how large
the repository is.

Framework Connection:

This is why teams create many short-lived branches (one per feature, per test fix, per prompt
experiment) without any storage or speed cost.

## Concept 4: HEAD and Current Branch

Tech Lead Question:

When you commit on `feature`, what actually moves — HEAD, the branch, or both?

Student Thinking:

Maybe HEAD moves to the new commit.

Student Answer:

"I think the branch moves forward, and HEAD follows it."

Tech Lead Review:

Right. HEAD points to the current branch, and only the current branch moves.

Before commit:

```text
HEAD
  |
  v
feature
  |
  v
Commit3
```

After commit:

```text
HEAD
  |
  v
feature
  |
  v
Commit4
  |
  v
Commit3
```

`main` did not move. Only `feature` advanced, and HEAD still points to `feature`.

Engineering Thinking:

```text
HEAD = the current branch reference.
A commit moves only the branch HEAD points to.
Other branches stay exactly where they were.
```

Framework Connection:

While you commit on `feature/agent`, the `main` reference that production runs from never
moves, so production stays stable.

## Concept 5: Fast-forward Merge

Tech Lead Question:

If `main` has not changed since you branched off, what does merging `feature` back really need
to do?

Student Thinking:

Maybe Git combines the two histories somehow.

Student Answer:

"If main did not move, maybe Git just needs to move main forward to where feature is."

Tech Lead Review:

Exactly. When `main` has not diverged, Git only moves the `main` reference forward. No new
commit is needed.

```text
Before:
main
  |
  v
Commit3        feature -> Commit5 -> Commit4 -> Commit3

After fast-forward:
main ----------------> Commit5
                        (feature is here too)
```

Core idea:

```text
Fast-forward = Reference Movement.
```

Engineering Thinking:

Because `main` had no new commits, there is nothing to reconcile. Git advances the pointer.
History stays linear.

Framework Connection:

A small Playwright test-fix branch, merged while `main` is unchanged, fast-forwards: `main`
simply points to the fixed commit.

## Concept 6: Three-way Merge

Tech Lead Question:

Now `main` has its own new commit AND `feature` has new commits. Can Git just move a pointer?

Student Thinking:

Both sides changed, so moving one pointer would lose the other side's work.

Student Answer:

"No. Both branches moved, so Git cannot just fast-forward without losing history."

Tech Lead Review:

Correct. When both branches have new commits, Git creates a new merge commit that combines
them.

Required diagram:

```text
        MergeCommit
        /         \
   CommitA       CommitB
   (main)        (feature)
```

The merge commit has two parents: the tip of `main` (CommitA) and the tip of `feature`
(CommitB).

Why history cannot be lost:

```text
Commits are immutable (Day15).
Git does not rewrite CommitA or CommitB.
It creates a new MergeCommit that points back to both.
Both histories are preserved and joined.
```

Engineering Thinking:

```text
Three-way Merge = a new commit with two parents.
It integrates two diverged histories without destroying either.
```

Framework Connection:

`main` gets a hotfix while `feature/agent` adds an endpoint; merging creates a merge commit
that keeps both the fix and the feature.

## Concept 7: Merge Conflict

Tech Lead Question:

Two branches changed the same line of the same function differently. What should Git do?

Student Thinking:

Maybe Git picks the newer one, or the bigger change?

Student Answer:

"I am not sure which one is correct — it depends on what we meant."

Tech Lead Review:

Exactly, and that is the key sentence of today:

```text
Git does not fail.
Git refuses to guess business intent.
```

Consider one function changed on each branch:

```python
# main
def handler():
    return "A"

# feature
def handler():
    return "B"
```

Git cannot know whether `"A"` or `"B"` is the correct business behavior. Choosing for you could
ship the wrong logic silently. So Git stops and asks a human to resolve the semantic ambiguity.

Engineering Thinking:

```text
A merge conflict is not a Git error.
It is Git protecting you from a wrong automatic guess.
The human resolves intent; Git records the resolution.
```

Framework Connection:

If two engineers edit the same prompt line differently, Git surfaces a conflict rather than
silently shipping a prompt that changes answer quality.

## Concept 8: Git as a DAG

Tech Lead Question:

After branching and merging, what shape does history have?

Student Thinking:

It is no longer a straight line — it splits and joins.

Student Answer:

"It becomes a graph: commits branch out and merge back."

Tech Lead Review:

Correct. Git history is a Directed Acyclic Graph (DAG).

```text
Commit1 -> Commit2 -> Commit3 -> CommitA -> MergeCommit
                          \                 /
                           CommitB --------
```

```text
Directed : each commit points to its parent(s).
Acyclic  : you can never form a cycle; history only moves forward.
Graph    : branches split and merges join, so it is not a simple line.
```

Relate to earlier graph knowledge:

```text
A commit points to its parent(s), like nodes pointing to earlier nodes.
A merge commit has two parents, creating a join in the graph.
Immutability guarantees no cycles: a new commit only points backward.
```

Engineering Thinking:

Seeing history as a DAG explains branching, merging, and why tools can always trace ancestry
from any commit.

Framework Connection:

Tracing a regression in an AI backend means walking the DAG backward through parents to find
the commit that changed a prompt, route, or Dockerfile.

---

# Engineering Thinking

Reason about branch and merge as the object model in motion.

```text
Commits are immutable objects.
Branches are movable references.
HEAD is the current reference.
A commit moves only the current branch.
Fast-forward is pure reference movement.
Three-way merge is a new commit with two parents.
A conflict is Git refusing to guess intent.
History is a Directed Acyclic Graph.
```

Why this design is good engineering:

```text
Cheap references make parallel work practical.
Immutable commits make integration safe (nothing is overwritten).
Merge commits preserve full history.
Conflicts keep humans in charge of business meaning.
```

Answer WHY before HOW:

```text
Why branch?  -> isolate independent work.
Why cheap?   -> a branch is a reference, not a copy.
Why merge commit? -> preserve two diverged histories.
Why conflict? -> Git will not guess semantics.
```

Tech Lead Review Checklist:

* Is each branch scoped to one independent piece of work?
* Is `main` kept releasable while feature branches evolve?
* Are merges deliberate, with conflicts resolved by a human who understands intent?
* Does the history read clearly as a DAG of intentional integrations?

---

# Classroom Exercises

## Exercise 1: Two Branches, One Commit

Question:

Create a branch and show that both branches point to the same commit.

Think First:

Did creating the branch copy any files?

Starter Code:

```bash
git init
echo "v1" > app.txt
git add .
git commit -m "Commit1"

git branch feature
git log --oneline --decorate
```

Expected Output:

`main` and `feature` both appear on the same commit in `git log --oneline --decorate`.

Explanation:

`git branch feature` created a new reference to the same commit. No project copy happened.

Follow-up Question:

In object-model terms, what did `git branch` actually create?

## Exercise 2: Fast-forward Merge

Question:

Merge a branch while `main` has not moved.

Think First:

If `main` did not change, what does the merge need to do?

Starter Code:

```bash
git checkout -b feature
echo "v2" > app.txt
git commit -am "Commit2"

git checkout main
git merge feature
git log --oneline --decorate
```

Expected Output:

`main` fast-forwards to `feature`'s commit; no merge commit is created.

Explanation:

Because `main` had no new commits, Git only moved the `main` reference forward.

Follow-up Question:

Why was no merge commit needed here?

## Exercise 3: Three-way Merge

Question:

Merge when both branches have new commits.

Think First:

Can Git move a single pointer without losing work?

Starter Code:

```bash
git checkout -b feature
echo "feature change" > feature.txt
git add . && git commit -m "feature commit"

git checkout main
echo "main change" > main.txt
git add . && git commit -m "main commit"

git merge feature
git log --oneline --graph
```

Expected Output:

Git creates a merge commit with two parents; `git log --graph` shows the split and join.

Explanation:

Both branches diverged, so Git built a new merge commit pointing to both tips.

Follow-up Question:

How many parents does the merge commit have, and why?

## Exercise 4: Create and Resolve a Merge Conflict

Question:

Force a conflict on the same line and resolve it.

Think First:

Why would Git refuse to choose automatically?

Starter Code:

```bash
git checkout -b feature
printf 'def handler():\n    return "B"\n' > handler.py
git commit -am "feature returns B"

git checkout main
printf 'def handler():\n    return "A"\n' > handler.py
git commit -am "main returns A"

git merge feature      # conflict
# edit handler.py to the intended result, then:
git add handler.py
git commit
```

Expected Output:

Git reports a conflict in `handler.py`; after you resolve and commit, a merge commit records
the resolution.

Explanation:

Both branches changed the same line differently. Git refuses to guess the business intent and
asks a human to resolve it.

Follow-up Question:

Explain the object model after the resolved merge: what does the merge commit point to?

---

# FastAPI Connections

```text
Feature branch for a new /agent endpoint, isolated from main.
Merge the endpoint back only when it is ready.
Roll main forward with a fast-forward for tiny fixes.
Use a merge commit when main also changed (a hotfix landed).
Resolve conflicts when two branches touch the same route or model.
```

Example:

```text
main runs /chat in production.
feature/agent builds /agent for two weeks.
A login hotfix lands on main.
Merging feature/agent into main creates a merge commit that keeps both.
```

---

# Playwright Connections

```text
A test branch fixes a flaky locator without touching production code.
Small test fixes fast-forward into main.
If main changed meanwhile, the merge creates a merge commit.
A conflict appears if two branches edit the same selector differently.
```

Example:

```text
feature/login-test updates login.py selectors.
main is unchanged, so the merge fast-forwards.
```

---

# AI Backend Connections

```text
Prompt branches: experiment with prompt-v2 in isolation.
Agent workflow branches: change tool definitions without breaking main.
Docker changes: a branch updates the Dockerfile independently.
Merge deliberately once an experiment proves better.
Conflicts protect you when two prompt edits disagree on the same line.
```

Example:

```text
feature/prompt-v2 rewrites the system prompt.
main gets an unrelated Dockerfile fix.
Merging creates a merge commit that keeps both the prompt and the Docker change,
and if both edited the same prompt line, Git asks a human to resolve intent.
```

---

# English Interview

## Key Vocabulary

* branch
* movable reference
* HEAD
* current branch
* fast-forward merge
* three-way merge
* merge commit
* parent commit
* merge conflict
* directed acyclic graph (DAG)

## Why are Git branches lightweight?

A branch is just a movable reference to a commit, essentially a small file holding a commit
hash. Creating one does not copy the project, so branch creation is nearly instant regardless
of repository size.

## Explain fast-forward merge.

If the target branch has not diverged, merging only moves its reference forward to the other
branch's commit. No merge commit is created, and history stays linear.

## Explain three-way merge.

When both branches have new commits, Git creates a new merge commit with two parents — the tips
of both branches — integrating the diverged histories without rewriting either side.

## Why does a merge conflict happen?

A conflict happens when two branches change the same content in incompatible ways, such as the
same line of the same function. Git cannot determine which change reflects the intended
behavior.

## Why doesn't Git automatically choose one version?

Because choosing could silently ship the wrong business logic. Git refuses to guess intent, so
it stops and asks a human to resolve the semantic ambiguity.

## Explain Git as a DAG.

Git history is a Directed Acyclic Graph: each commit points to its parent or parents, edges
only point backward so there are no cycles, and branching and merging make the history a graph
rather than a straight line.

---

# Today's Takeaway

Branch and merge are the Git object model in motion.

```text
Ask always:
What reference is moving?
Did history diverge or not?
Is this a pointer move, a new merge commit, or a conflict to resolve?
```

Today's core principles:

* A branch exists to isolate independent work.
* A branch is a movable reference, not a copy.
* Branch creation is instant because Git makes a reference, not a project.
* HEAD points to the current branch, and a commit moves only that branch.
* Fast-forward merge is pure reference movement.
* Three-way merge is a new commit with two parents that preserves both histories.
* A merge conflict is Git refusing to guess business intent.
* Git history is a Directed Acyclic Graph.

The most important engineering sentence:

```text
Branches move references; merges integrate immutable history; conflicts keep humans in charge.
```

---

# Before Next Lesson Checklist

Before the next Phase 2 lesson, confirm you can answer these without looking at the notes:

- [ ] What engineering problem do branches solve?
- [ ] Why is a branch a movable reference, not a copy?
- [ ] Why is branch creation nearly instant?
- [ ] What does HEAD point to, and what moves when you commit?
- [ ] What is a fast-forward merge, and when does it happen?
- [ ] What is a three-way merge, and why does the merge commit have two parents?
- [ ] Why does a merge conflict happen?
- [ ] Why does Git refuse to choose a version automatically?
- [ ] Why is Git history a Directed Acyclic Graph?
- [ ] How would I use a feature branch for a FastAPI endpoint or an AI prompt experiment?
