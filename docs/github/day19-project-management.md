# Lesson 19 — GitHub Project Management

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day18 — Merge Strategy & Code Review

Next Lesson: Phase 2 continues — Linux, Docker

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why software teams manage work, not only code.
* Explain an Issue as a work item that enables collaboration, tracking, prioritization, and ownership.
* Explain a Label as structured metadata for retrieval, workflow, and automation.
* Explain a Milestone as a product goal, distinct from a single Issue.
* Explain GitHub Projects as workflow management, distinct from task management.
* Explain the engineering hierarchy: Issue, Label, Milestone, Project.
* Assemble the complete Idea-to-Release workflow tying Day15–Day19 together.
* Connect project management to FastAPI, Playwright, AI backend, prompt, and Docker work.
* Answer beginner, intermediate, and senior project-management interview questions.

---

# Why This Matters

Day15–Day18 managed code: commits, branches, merges, reviews. Day19 manages the work itself —
what to build, who owns it, and where it is in the pipeline.

Tech Lead Question:

Your code is perfectly version-controlled. But five people are building an AI backend. What is
still missing?

Student Thinking:

The code is tracked, but who decides what to build next, and who is doing what?

Student Answer:

"We are managing code, but not the work. Nobody can see what exists, who owns it, or where it
stands."

Tech Lead Review:

Exactly. Version control tracks code; project management tracks work.

```text
Git / GitHub PRs  -> manage CODE (what changed).
Issues / Projects -> manage WORK (what to do, who, and where it is).
```

Today's guiding sentence:

```text
If work isn't tracked, it doesn't exist.
```

Why this matters for a backend engineer:

```text
Teams need to see all work, not just merged code.
Priorities and ownership must be explicit, not in someone's head.
A delivery goal (an MVP) needs to be tracked across many tasks.
The pipeline stage of each task must be visible to everyone.
```

Today's mental model:

```text
Idea -> Issue -> Label -> Milestone -> Project -> Branch -> Commit -> Pull Request
     -> CI -> Review -> Merge -> Deploy -> Release
```

This lesson is not about clicking GitHub's UI. It is about why each layer of work management
exists.

---

# Roadmap Position

```text
Day15: Git object model
Day16: Branch & Merge
Day17: GitHub Workflow (PRs, CI, protection)
Day18: Merge Strategy & Code Review
        |
        v
Day19: GitHub Project Management (Issue, Label, Milestone, Projects)
        |
        v
Phase 2 continues: Linux, Docker
```

Day15–Day18 were about code integration. Day19 puts a work-management layer on top, so the code
workflow serves a visible, prioritized plan.

```text
Code workflow (Day15-Day18)
      +
Work management (Day19: Issues, Labels, Milestones, Projects)
      |
      v
A team that can see, prioritize, and deliver work
```

---

# Lesson Map

```text
Today's Lesson

1. Why Teams Manage Work, Not Only Code
2. Why Issue Exists
3. Why Label Exists
4. Why Milestone Exists
5. Why Projects Exists
6. Engineering Hierarchy
7. Complete AI Backend Workflow
8. FastAPI, Playwright, and AI Backend Connections
9. Interview Review
```

---

# Estimated Study Time

```text
Reading: 100-130 minutes
Exercises: 60-90 minutes
Hands-on board practice: 60-90 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Main Concepts

## Concept 1: Why Issue Exists

Tech Lead Question:

Is a GitHub Issue just a bug report?

Student Thinking:

The name sounds like "something is wrong," so maybe only bugs?

Student Answer:

"I thought Issues were for bugs, but features and tasks also need to be tracked somewhere."

Tech Lead Review:

Correct. An Issue is not only for bugs. An Issue is a work item — any unit of work.

```text
Issue = Work Item
(bug, feature, task, chore, question, spike — anything to be done)
```

An Issue solves four problems at once:

```text
Collaboration   -> a shared place to discuss the work.
Tracking        -> the work is visible and does not get lost.
Prioritization  -> it can be ordered against other work.
Ownership       -> someone is responsible for moving it forward.
```

Key sentence:

```text
If work isn't tracked, it doesn't exist.
```

Important distinction:

```text
Ownership != Blame.
Ownership means "who drives this to done," not "who to blame if it breaks."
```

Engineering Thinking:

```text
Untracked work lives in memory and chat, and quietly disappears.
An Issue makes work real, assignable, and prioritizable.
```

Production Example:

"We should add rate limiting" said in a meeting evaporates. As an Issue, it has an owner, a
priority, and a place in the plan.

Framework Connection:

An AI backend Issue like "Bound OpenAI concurrency with a semaphore" captures the work, assigns
an owner, and can be prioritized against other tasks.

## Concept 2: Why Label Exists

Tech Lead Question:

A Label looks like a colored tag. Is it just decoration or categorization?

Student Thinking:

Maybe it just sorts Issues into groups by color?

Student Answer:

"It groups Issues, but there must be a reason beyond just color."

Tech Lead Review:

Right. A Label is structured metadata attached to work. It serves three purposes:

```text
1. Retrieval  -> filter and find work: all `bug`, all `security`, all `prompt`.
2. Workflow   -> drive process: `needs-review`, `blocked`, `ready`.
3. Automation -> trigger actions: `ci-skip`, auto-assign, auto-route.
```

Relate Labels to metadata you already know:

```text
Database indexes     -> fast lookup by a field.
Metadata             -> data about data.
RAG filtering        -> filter documents by tags before retrieval.
Vector search filter -> restrict a similarity search by metadata.
Kubernetes labels    -> select and route resources by label.
```

Engineering Thinking:

```text
A Label is not a color; it is queryable, structured metadata on work.
Good labels make thousands of Issues searchable and automatable.
```

Production Example:

Filtering `label:security label:priority-high` surfaces exactly the risky work to do first.

Framework Connection:

Labeling `area:prompt` vs `area:docker` lets the AI backend team route and filter work the same
way RAG filters documents by metadata before retrieval.

## Concept 3: Why Milestone Exists

Tech Lead Question:

If an Issue tracks one task, what tracks a shippable goal made of many tasks?

Student Thinking:

Grouping several Issues together toward one release?

Student Answer:

"A Milestone — it collects the Issues that together deliver a product goal."

Tech Lead Review:

Exactly.

```text
Issue     -> manages ONE task.
Milestone -> manages ONE product goal (a delivery target).
```

Example — an AI Backend MVP milestone contains:

```text
AI Backend MVP
├── Login
├── Memory
├── Prompt
├── Docker
└── Deploy
```

Engineering Thinking:

```text
A Milestone represents a delivery target, not an individual task.
It answers: are we on track to ship this goal?
```

Production Example:

The "MVP" milestone shows 3 of 5 Issues done, so the team can see delivery progress at a glance.

Framework Connection:

An "AI Backend MVP" milestone groups the FastAPI auth, prompt, memory, Docker, and deploy Issues
into one trackable release goal.

## Concept 4: Why Projects Exists

Tech Lead Question:

Issues and Milestones tell you what work exists. What tells you where each piece of work is
right now?

Student Thinking:

A board that shows the stage of each Issue?

Student Answer:

"GitHub Projects — it shows where work is in the pipeline, not just that it exists."

Tech Lead Review:

Correct. A Project does not manage tasks; it manages workflow — the movement of work through
stages.

```text
Ideas -> Backlog -> Ready -> In Progress -> Review -> Testing -> Deploy -> Done
```

The key distinction:

```text
Issue answers:   "What work exists?"
Project answers: "Where is the work now?"
```

Engineering Thinking:

```text
An Issue is a unit of work; a Project is the pipeline the work flows through.
The board makes flow, bottlenecks, and stage visible to the whole team.
```

Production Example:

Standup becomes "what is stuck in Review?" because the board shows every Issue's current column.

Framework Connection:

A Project board tracks the AI backend features moving from Backlog to Deploy, so anyone can see
that "prompt-v2" is in Review and "Docker deploy" is still in Backlog.

## Concept 5: Engineering Hierarchy

Tech Lead Question:

How do Issue, Label, Milestone, and Project fit together as layers?

Student Thinking:

They each do something different; maybe they stack.

Student Answer:

"Issue is the work, Label describes it, Milestone groups it toward a goal, Project shows its
flow."

Tech Lead Review:

Exactly. They form a hierarchy of concerns:

```text
Issue
  |
Label
  |
Milestone
  |
Project
```

```text
Issue     = Work        (the unit of work)
Label     = Metadata    (structured description of the work)
Milestone = Goal        (a delivery target made of Issues)
Project   = Workflow    (where the work is in the pipeline)
```

Engineering Thinking:

```text
Each layer answers a different question:
Issue: what work? Label: what kind? Milestone: toward what goal? Project: at what stage?
```

Framework Connection:

An AI backend task is one Issue, labeled `area:prompt`, inside the `MVP` milestone, sitting in
the `In Progress` column of the Project board.

## Concept 6: Complete AI Backend Workflow

Tech Lead Question:

Connect everything from Day15 to today. What is the full path from an idea to a release?

Student Thinking:

An idea becomes tracked work, then code, then it ships.

Student Answer:

"It starts as an Issue, moves through the board, becomes a branch and a PR, gets reviewed and
merged, then deploys."

Tech Lead Review:

Exactly. Here is the complete engineering flow:

```text
Idea
  |
  v
Issue            (Day19: track the work)
  |
  v
Project          (Day19: place it on the board)
  |
  v
Feature Branch   (Day16: isolate the work)
  |
  v
Commit           (Day15: immutable snapshot)
  |
  v
Pull Request     (Day17: gate the change)
  |
  v
CI               (Day17: machine validates rules)
  |
  v
Review           (Day18: human validates intent, chosen merge strategy)
  |
  v
Merge            (Day16/Day18: integrate history)
  |
  v
Deploy
  |
  v
Release
```

Engineering Thinking:

```text
Work management (Issue, Project) and code management (branch, PR, review, merge)
are one continuous pipeline, not separate tools.
```

Production Example:

"Add /agent endpoint" starts as an Issue in the MVP milestone, moves to In Progress on the
board, becomes `feature/agent`, is committed, opened as a PR, passes CI, is reviewed and
squash-merged, then deploys — and the Issue closes.

Framework Connection:

Every AI backend feature — a FastAPI endpoint, a prompt change, a Docker update — flows through
this exact path from Issue to Release.

---

# Engineering Thinking

Reason about project management as making work visible and prioritized.

```text
Teams must manage work, not only code.
An Issue is a work item; untracked work does not exist.
Ownership means responsibility to deliver, not blame.
A Label is structured metadata for retrieval, workflow, and automation.
A Milestone is a delivery goal made of many Issues.
A Project manages workflow: where work is, not just what it is.
Issue, Label, Milestone, and Project are a hierarchy of concerns.
Work management and code management form one pipeline.
```

Why this design is good engineering:

```text
Visible work prevents dropped tasks and hidden priorities.
Metadata makes large backlogs searchable and automatable.
Goals connect scattered tasks to a shippable outcome.
Workflow boards expose bottlenecks so the team can unblock them.
```

Answer WHY before HOW:

```text
Why Issues?    -> untracked work disappears.
Why Labels?    -> to retrieve, route, and automate work.
Why Milestones?-> to track a delivery goal across tasks.
Why Projects?  -> to see where each piece of work is.
```

Tech Lead Review Checklist:

* Is every real piece of work an Issue, with an owner?
* Are Labels consistent enough to filter and automate?
* Does each Milestone map to a real delivery goal?
* Does the Project board reflect true stages and reveal bottlenecks?
* Do Issues connect cleanly to branches, PRs, and releases?

---

# Classroom Exercises

## Exercise 1: Convert Feature Requests into Issues

Question:

Turn these requests into well-formed Issues.

Think First:

What makes work "tracked" rather than a vague idea?

Starter Code:

```text
Requests:
- "The app should remember past chats."
- "It keeps hitting the OpenAI rate limit."
- "We need a Dockerfile."
```

Expected Output:

```text
Issue: Add conversation memory to the chat service (owner, priority)
Issue: Bound OpenAI concurrency with a semaphore to avoid 429s (owner, priority)
Issue: Add a Dockerfile for the backend service (owner, priority)
```

Explanation:

Each request becomes a tracked, ownable, prioritizable work item. If it is not an Issue, it does
not exist.

Follow-up Question:

Why does "ownership" here not mean "blame"?

## Exercise 2: Assign Labels and Explain Why

Question:

Label the three Issues above and justify each label.

Think First:

Which of retrieval, workflow, and automation does each label serve?

Starter Code:

```text
Available labels: area:prompt, area:infra, area:backend, priority-high,
security, needs-review, blocked
```

Expected Output:

```text
Memory Issue     -> area:backend
Rate-limit Issue -> area:backend, priority-high, security
Dockerfile Issue -> area:infra
```

Explanation:

Labels are structured metadata: they let you retrieve (filter by `area:infra`), drive workflow
(`needs-review`), and automate (route `area:infra` to the platform team).

Follow-up Question:

How is this like filtering documents by metadata in RAG?

## Exercise 3: Group Issues into a Milestone

Question:

Group the Issues into a delivery goal.

Think First:

What single product outcome do these tasks add up to?

Starter Code:

```text
Issues: Login, Memory, Prompt, Docker, Deploy
```

Expected Output:

```text
Milestone: AI Backend MVP
├── Login
├── Memory
├── Prompt
├── Docker
└── Deploy
```

Explanation:

A Milestone is a delivery target; it shows progress toward shipping the MVP, not just individual
tasks.

Follow-up Question:

What does a Milestone tell you that an individual Issue cannot?

## Exercise 4: Build a Project Workflow Board

Question:

Place the MVP Issues on a workflow board.

Think First:

Does the board track what work exists, or where it is?

Starter Code:

```text
Columns: Ideas | Backlog | Ready | In Progress | Review | Testing | Deploy | Done
```

Expected Output:

```text
In Progress: Prompt
Review:      Memory
Backlog:     Docker, Deploy
Done:        Login
```

Explanation:

The Project board answers "where is the work now?" and exposes bottlenecks (e.g., too much in
Review).

Follow-up Question:

How does an Issue's journey on this board connect to its branch, PR, and release?

---

# FastAPI Connections

```text
Track each endpoint as an Issue with an owner and priority.
Label endpoints: area:backend, security, priority-high.
Group endpoints into an MVP milestone toward a release.
Move each endpoint across the Project board from Backlog to Deploy.
The Issue links to feature/<endpoint>, its PR, CI, review, and merge.
```

Example:

```text
"Add /agent endpoint" is an Issue in the MVP milestone; it moves to In Progress,
becomes feature/agent, passes CI and review, merges, deploys, and the Issue closes.
```

---

# Playwright Connections

```text
Track flaky-test fixes and new test coverage as Issues.
Label them area:tests, flaky, priority-high.
Group test hardening into a quality milestone.
The board shows which test work is in progress vs done.
```

Example:

```text
"Stabilize login test selectors" is an Issue labeled area:tests, flaky;
it moves through the board and links to its PR and merge.
```

---

# AI Backend Connections

```text
Track prompt experiments, tool definitions, and infra as Issues.
Label them area:prompt, area:infra, area:agent for retrieval and routing.
Group them into an MVP or release milestone.
The board shows prompt-v2 in Review and Docker deploy in Backlog.
Each Issue flows to a branch, PR, review, merge, deploy, and release.
```

Example:

```text
"Adopt prompt-v2" is an Issue labeled area:prompt in the MVP milestone;
it moves to In Progress, becomes a branch and PR, is reviewed and squash-merged, then ships.
```

---

# English Interview

## Key Vocabulary

* issue / work item
* label / metadata
* milestone / delivery goal
* project / workflow board
* ownership vs blame
* backlog
* pipeline / workflow stage

## Why do teams need Issues?

Because teams must manage work, not only code. An Issue is a trackable, ownable, prioritizable
work item. Untracked work lives in memory and chat and gets lost — if work isn't tracked, it
doesn't exist.

## What is the difference between an Issue and a Milestone?

An Issue manages one task. A Milestone groups many Issues into one product delivery goal and
shows progress toward shipping it.

## Why use Labels?

A Label is structured metadata on work. It enables retrieval (filtering), workflow (states like
needs-review), and automation (routing or triggers) — similar to database indexes, RAG metadata
filtering, and Kubernetes labels.

## What is GitHub Projects?

GitHub Projects manages workflow, not tasks. It is a board that shows where each piece of work
is in the pipeline (Backlog, In Progress, Review, Done), exposing flow and bottlenecks.

## What is the difference between Issue management and Project management?

Issue management answers "what work exists?" — the units of work. Project management answers
"where is the work now?" — the stage of each unit in the pipeline.

## Explain ownership vs blame.

Ownership means someone is responsible for driving a piece of work to done. Blame is about fault
after something breaks. Assigning ownership makes work move; treating it as blame discourages
people from taking it.

---

# Today's Takeaway

Project management makes work visible, prioritized, and connected to the code pipeline.

```text
Ask always:
Is this work an Issue, or is it invisible?
What does its label let us retrieve and automate?
What goal (milestone) does it serve, and where is it on the board?
```

Today's core principles:

* Teams manage work, not only code.
* An Issue is a work item; if work isn't tracked, it doesn't exist.
* Ownership means responsibility to deliver, not blame.
* A Label is structured metadata for retrieval, workflow, and automation.
* A Milestone is a delivery goal made of many Issues.
* A Project manages workflow: where the work is, not just what it is.
* Issue, Label, Milestone, and Project form a hierarchy: Work, Metadata, Goal, Workflow.
* Work and code management are one pipeline from Idea to Release.

The most important engineering sentence:

```text
Issue answers what work exists; Project answers where the work is; together they turn ideas into
releases.
```

---

# Before Next Lesson Checklist

Before the next Phase 2 lesson, confirm you can answer these without looking at the notes:

- [ ] Why must teams manage work, not only code?
- [ ] Why is an Issue a work item, not just a bug report?
- [ ] What four problems does an Issue solve?
- [ ] Why does ownership not mean blame?
- [ ] What three purposes does a Label serve?
- [ ] How is a Label like a database index or RAG metadata filter?
- [ ] What is the difference between an Issue and a Milestone?
- [ ] What does a Project manage that an Issue does not?
- [ ] Can I state the hierarchy: Issue, Label, Milestone, Project?
- [ ] Can I trace the full workflow from Idea to Release?
