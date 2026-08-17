# Day15–Day22 Engineering Foundations Super Cheat Sheet

> Part of the **Day15–Day22 Engineering Foundations Second Brain**.
> Companion documents: [memory-map.md](memory-map.md) · [code-templates.md](code-templates.md) · [interview-qa.md](interview-qa.md) · [one-page.md](one-page.md)

## How to Use This Document

This is the **explanation** layer of the Second Brain. Reach for it when you need to:

- **Quickly review** a single day's core ideas without rereading the full lesson.
- **Debug engineering problems** by recalling which state, gate, or boundary is involved.
- **Prepare for interviews** by recovering the mental model behind each concept.
- **Recover a lost mental model** three months later.

Retrieval roles across the Second Brain: this file *explains*, [memory-map.md](memory-map.md) *connects*, [code-templates.md](code-templates.md) *executes*, [interview-qa.md](interview-qa.md) *expresses*, and [one-page.md](one-page.md) is the 5-minute *recall*. Content is intentionally not duplicated across them.

Each day gives you the mental model first, then only the 4–7 concepts that actually carry the day. Commands are kept to the ones worth reusing, and each is described by *what state it changes*.

---

## Whole-Stage Core Mental Model

```text
Software delivery is not uploading code to a server. It is letting one change
enter the target environment in a way that is traceable, reviewable, verifiable,
reproducible, and recoverable.
```

Day15–Day22 build exactly the capabilities that sentence requires:

```text
traceable   -> Git history, commits, PR audit trail, Issues
reviewable  -> Pull Request, review, branch protection
verifiable  -> CI, quality gate, matrix, image verification
reproducible-> workflow as code, immutable digest, "build once, deploy many"
recoverable -> reflog, revert, rollback, serialized deployment
```

---

## The Day15–Day22 Knowledge Chain

```text
Git manages local history
  -> Branch isolates parallel change
  -> GitHub adds remote collaboration
  -> Pull Request / Review controls integration quality
  -> Project Management makes work visible
  -> CI/CD automates quality and delivery feedback
  -> GitHub Actions expresses the pipeline as code
  -> Advanced Actions add reuse, matrix, cache, artifact, and deployment control
```

Why the chain holds: each lesson solves the *next* engineering problem the previous one exposed. Git records history but cannot isolate parallel work → branches. Branches integrate locally but not across a team → GitHub PRs. PRs gate code but not *work* → Project Management. Visible work still relies on "trust me" quality → CI/CD. Principles need an implementation → GitHub Actions. A basic workflow cannot scale, reuse, or deploy safely → Advanced Actions. These are not eight isolated tools; they are one delivery pipeline.

---

# Day15 — Git Fundamentals

## One-line Mental Model
`Git = a project history management system built on immutable snapshots and movable references.`

## Previous Lesson Connection
Reuses the Day01–Day02 Python object model: names reference objects, assignment does not always copy, immutability makes sharing safe. Git applies the same thinking at the *history* level.

## Why It Exists
IDE local history and manual backups cannot answer *who changed what, when, why, and how to recover it* across broken machines, teams, and production rollbacks.

## Engineering Problem
Recover broken code reliably, know the author and reason for every change, and roll back a bad state — without copying the whole project each time.

## Core Concepts

- **Snapshot, not diff.** A commit stores a snapshot; Git creates new objects only for changed content and *reuses references* to unchanged blobs/trees. Pure diff would make checking out old versions slow (replay every diff).
- **Commit = immutable snapshot.** You never edit an old commit; changing content creates a new object. Commit identity is its content hash, which is why rollback is reliable.
- **Three trees.** `Working Directory --git add--> Staging Area/Index --git commit--> Repository`. Every command is data movement between these three trees. `git commit` builds from the **Index**, not the Working Directory.
- **HEAD vs Branch.** A branch is a movable reference to a commit; HEAD is the current reference (usually pointing at a branch). A new commit moves only the branch HEAD points to.
- **Detached HEAD.** `git checkout <sha>` points HEAD directly at a commit. A commit made here is owned by no branch and can become dangling.
- **reset modes** — reference movement plus optional tree sync (see decision table below).
- **reflog.** Records where HEAD has been, so a mistaken reset is recoverable *because the commit object is immutable and still in the object database*.

## Production Scenario
A `/chat` endpoint starts returning 500 after a commit. Use `git log` to find the suspect commit, `git diff` to see the exact change, and roll back to the last good commit while you fix it.

## Trade-offs
Snapshots + reference reuse make branching and rollback cheap and safe, at the cost of a mental model that is not "just diffs." The Staging Area adds a preparation step (more control over what is committed) but also a common bug: committing staged v1 while the Working Directory holds v2.

## Real Classroom Misconceptions & Corrections

**Misconception 1 — "Git only saves changed parts, like a diff."**
- *Why it looked reasonable:* saving only diffs seems space-efficient.
- *Where it fails:* checking out an old version would require replaying every diff from the start.
- *Correct model:* Git stores snapshots and reuses references to unchanged objects; only changed content becomes a new object.

**Misconception 2 — "HEAD is like `current_commit`."**
- *Why it looked reasonable:* HEAD does track "where you are."
- *Where it fails:* HEAD normally points to a *branch*, not directly to a commit; in detached HEAD it points at a commit.
- *Correct model:* HEAD = current reference (usually a branch); a branch = movable reference to a commit.

**Misconception 3 — reset: "`--soft` only moves the branch" (correct), but `--mixed`/`--hard` were unclear.**
- *Correct model:* `--mixed` also resets the Index (un-stage, keep code); `--hard` also resets the Working Directory (destroys uncommitted edits, not recoverable via reflog).

## reset Decision Table

| Command | HEAD / Branch | Index | Working Directory | Use when |
|---|---|---|---|---|
| `git reset --soft` | moves | unchanged | unchanged | undo commit, keep changes staged |
| `git reset --mixed` (default) | moves | reset | unchanged | un-stage, keep code in Working Directory |
| `git reset --hard` | moves | reset | reset | discard pointer move + staged + working edits (**destructive**) |

## Engineering Checklist
- [ ] I can name which tree I am touching (Working Directory / Index / Repository).
- [ ] I check `git status` before any destructive command.
- [ ] I never run `git reset --hard` on uncommitted work I might need.
- [ ] I can recover a mistaken reset with `git reflog`.

## Next Lesson Connection
Immutable commits + movable references are the raw material Day16 puts *in motion* through branches and merges.

---

# Day16 — Branch & Merge

## One-line Mental Model
`Branch and merge are the Git object model in motion: references move, immutable history integrates.`

## Previous Lesson Connection
Day15 gave immutable commits and references; Day16 moves those references to enable parallel work.

## Why It Exists
Production `main`, a two-week feature, and an urgent hotfix cannot share one development line without blocking or corrupting each other.

## Engineering Problem
Isolate independent work so `main` stays releasable, then integrate finished work deliberately.

## Core Concepts

- **Branch = movable reference, not a copy.** `git branch feature` creates one small file holding a commit hash. No project copy happens.
- **Branch creation is O(1).** Because it is a reference, not a project, creation is instant regardless of repo size (a 5GB repo branches instantly).
- **HEAD and current branch.** A commit moves only the current branch; other branches stay put.
- **Fast-forward merge = pure reference movement.** If `main` did not diverge, Git just advances the `main` pointer; no merge commit, linear history.
- **Three-way merge = new commit with two parents.** When both branches have new commits, Git creates a merge commit pointing to both tips; nothing is overwritten (commits are immutable).
- **Merge conflict = Git refusing to guess intent.** When two branches change the same line differently, Git stops rather than silently shipping the wrong business logic.
- **History is a DAG.** Directed (commits point to parents), Acyclic (no cycles; only points backward), Graph (branches split, merges join).

## Production Scenario
`main` runs `/chat`; `feature/agent` builds a new endpoint for two weeks; a login hotfix lands on `main`. Merging `feature/agent` creates a merge commit that keeps both.

## Trade-offs
Cheap references make parallel work practical; immutable commits make integration safe. Fast-forward keeps history linear but records no explicit integration point; three-way merge preserves both histories but adds a merge commit; conflicts keep humans in charge of meaning at the cost of manual resolution.

## Real Classroom Misconception & Correction

**Misconception — "`git branch feature` copies the code into a new folder."**
- *Why it looked reasonable:* a "separate version" sounds like separate files.
- *Where it fails:* copying would make branch creation slow; it is actually instant.
- *Correct model:* a branch is a movable reference; nothing is copied. `main` and `feature` can both point at the same commit.

## Merge Decision Table

| Situation | What Git does | Result shape |
|---|---|---|
| Target branch did not diverge | Fast-forward (move pointer) | Linear, no merge commit |
| Both branches have new commits | Three-way merge (new commit, 2 parents) | Split + join in the DAG |
| Same line changed differently | Conflict (stop, ask human) | Human resolves intent, Git records it |

## Engineering Checklist
- [ ] Each branch is scoped to one independent piece of work.
- [ ] `main` stays releasable while feature branches evolve.
- [ ] I know whether a given merge fast-forwards or creates a merge commit.
- [ ] Conflicts are resolved by a human who understands the intent.

## Next Lesson Connection
Local branch/merge works on one machine; Day17 turns it into safe, reviewable *team* integration on GitHub.

---

# Day17 — GitHub Workflow & Collaboration

## One-line Mental Model
`Protect shared state with gates: machines check the rules, humans check the intent, and the discussion keeps the why.`

## Previous Lesson Connection
Day16 integrated work locally; Day17 adds team gates (PR, CI, review, protection) around a shared `main`.

## Why It Exists
A direct push to `main` sends unreviewed, untested code to everyone instantly, turning one person's mistake into the whole team's problem.

## Engineering Problem
Let many engineers integrate into a shared, releasable line without one mistake breaking everyone.

## Core Concepts

- **`main` is shared state.** Unguarded shared state is where team-scale bugs come from.
- **Pull Request = Review + CI + Discussion + Audit Trail.** Not a merge button — it is the moment a change becomes reviewed, tested, discussed, and recorded.
- **Machines validate rules; humans validate intent.** CI checks build/tests/lint/coverage; a human judges whether the change is the *right* thing for the business. You need both.
- **Branch Protection makes the safe path the only path.** It can require a PR, passing CI, an approving review, and an up-to-date branch — so rules are not skipped under pressure.
- **Stale review.** An approval is a statement about a *specific state*; pushing new commits after approval makes it stale, and protection can dismiss it.
- **Review discussion = durable engineering knowledge.** Code shows *what*, the commit message a short *why*, the PR thread the full *why* (alternatives, trade-offs, decisions).

## Production Scenario
CI confirms the code compiles and tests pass; a reviewer notices the endpoint returns the wrong status code for an unauthorized user — a business-intent bug no test covered.

## Trade-offs
Gates protect shared state and split responsibility (rules vs intent) at the cost of added process latency. Preserving discussions costs nothing to store and saves future engineers from re-litigating solved problems.

## Real Classroom Misconceptions & Corrections
`Not established in Day15–Day22 repository sources.` In the recorded Day17 session the student answered the core questions correctly (e.g. "other people depend on `main`", "tests check that it runs, not that it does the right thing"). No incorrect belief was recorded to preserve; do not invent one. The reusable *comparison* to internalize is Rules vs Intent below.

## Rules vs Intent Comparison

| Gate | Validates | Examples | Cannot judge |
|---|---|---|---|
| CI (machine) | rules | build, tests, lint, coverage | whether the feature is a good idea |
| Review (human) | intent | correctness for the business, design | 5,000 tests re-run by hand |

## Engineering Checklist
- [ ] Every change to `main` goes through a PR.
- [ ] CI checks are required, not optional.
- [ ] A human reviewed intent, not just trusted green CI.
- [ ] Stale approvals are dismissed after new commits.
- [ ] The PR discussion captures the reasoning for future engineers.

## Next Lesson Connection
Day17 got changes *safely in*; Day18 governs the *shape of the history* left behind and the *quality of the review* that shapes it.

---

# Day18 — Merge Strategy & Code Review

## One-line Mental Model
`History is for humans; a good review improves the code, the developer, and the team.`

## Previous Lesson Connection
Day17 was the gate; Day18 is what the gate leaves behind — a readable history and a stronger team.

## Why It Exists
The machine only needs parent pointers to function; everything readable (messages, clean log) exists so humans can understand and debug later.

## Engineering Problem
Choose how much development noise reaches `main`, and review the risks machines cannot judge.

## Core Concepts

- **Development history vs product history.** The feature branch is the workshop (noisy `wip`, `fix typo`); `main` is the showroom (one meaningful change). Merge strategy decides how much workshop shows up.
- **Merge commit** — preserves complete development history + an explicit join (two parents). Use when individual commits carry real meaning.
- **Squash merge** — compresses many noisy commits into one product commit. The most common feature-branch strategy.
- **Rebase merge** — replays commits onto the target for a linear history with no merge commit. Rewrites commit identity (`C -> C'`), so it is for integrating a branch, not shared/published history.
- **What senior engineers review:** architecture, performance, security, maintainability — not formatting (linters handle that).
- **Review the code, not the coder.** Specific, kind, actionable comments aimed at a better change.
- **Three goals of review:** improve the code, the developer, and the team (knowledge sharing, not just approval).

## Production Scenario
A reviewer approves nicely formatted code that opens a blocking DB call inside an async endpoint — a performance bug the linter never saw.

## Trade-offs
Merge commit preserves detail but can clutter `main`; squash keeps `main` clean but discards step-by-step history; rebase gives a clean linear log but rewrites identity (unsafe on shared history). Reviewing real risk prevents incidents but costs senior attention.

## Real Classroom Misconceptions & Corrections
`Not established in Day15–Day22 repository sources.` The recorded Day18 session shows the student reasoning correctly (e.g. "the machine only needs parent links; readable history is for humans", "compress them into one clean commit"). No incorrect belief was recorded; the durable artifact is the merge-strategy decision table below.

## Merge Strategy Decision Table

| Strategy | Keeps individual commits? | History shape | Rewrites identity? | Use when |
|---|---|---|---|---|
| Merge commit | Yes | Split + join (2 parents) | No | commits are meaningful / want an explicit integration record |
| Squash | No (one commit) | Linear | Yes (new commit) | branch commits are noise; only the finished change matters |
| Rebase | Yes | Linear (no merge commit) | Yes (`C -> C'`) | few clean commits + want a straight line; not on shared history |

## Engineering Checklist
- [ ] `main` reads as clean product history.
- [ ] The merge strategy was chosen on purpose.
- [ ] Review covered architecture, performance, security, maintainability.
- [ ] Comments were about the code, specific, and constructive.

## Next Lesson Connection
Day15–Day18 managed *code*; Day19 adds a layer to manage the *work* the code implements.

---

# Day19 — GitHub Project Management

## One-line Mental Model
`Issue answers what work exists; Project answers where the work is; together they turn ideas into releases.`

## Previous Lesson Connection
Code is version-controlled (Day15–Day18), but the *work* — what to build, who owns it, where it stands — is still invisible.

## Why It Exists
`If work isn't tracked, it doesn't exist.` Version control tracks code; project management tracks work.

## Engineering Problem
Make work visible, prioritized, owned, and connected to the code pipeline.

## Core Concepts

- **Issue = work item** (not just a bug): bug, feature, task, chore, question, spike. Solves collaboration, tracking, prioritization, and ownership at once. *Ownership ≠ blame* — it means "who drives this to done."
- **Label = structured metadata.** Serves retrieval (filter `security`), workflow (`needs-review`, `blocked`), and automation (routing/triggers). Analogous to database indexes, RAG metadata filters, and Kubernetes labels.
- **Milestone = delivery goal** made of many Issues (e.g. an "AI Backend MVP"). Answers "are we on track to ship this goal?"
- **Project = workflow management**, not task management. A board showing *where* each Issue is (Backlog → In Progress → Review → Done), exposing flow and bottlenecks.
- **Engineering hierarchy:** Issue (Work) → Label (Metadata) → Milestone (Goal) → Project (Workflow).
- **Idea-to-Release workflow** ties Day15–Day19 into one pipeline.

## Production Scenario
"We should add rate limiting," said in a meeting, evaporates. As an Issue it has an owner, a priority, and a place in the plan; on the board the team sees it move from Backlog to Done.

## Trade-offs
Tracking every piece of work adds overhead but prevents dropped tasks and hidden priorities. Labels add taxonomy discipline but make large backlogs searchable and automatable.

## Real Classroom Misconception & Correction

**Misconception — "Issues are for bugs."**
- *Why it looked reasonable:* the word "issue" sounds like "something is wrong."
- *Where it fails:* features, tasks, chores, and spikes also need tracking or they vanish.
- *Correct model:* an Issue is any unit of work; if work isn't tracked, it doesn't exist.

## Work Hierarchy Comparison

| Layer | Answers | Analogy |
|---|---|---|
| Issue | what work exists? | one unit of work |
| Label | what kind? | database index / RAG metadata filter |
| Milestone | toward what goal? | a shippable delivery target |
| Project | at what stage? | pipeline board |

## Engineering Checklist
- [ ] Every real piece of work is an Issue with an owner.
- [ ] Labels are consistent enough to filter and automate.
- [ ] Each Milestone maps to a real delivery goal.
- [ ] The board reflects true stages and reveals bottlenecks.

## Next Lesson Connection
Work is now visible, but quality still relies on "trust me." Day20 automates quality and delivery.

---

# Day20 — CI/CD Foundations

## One-line Mental Model
`CI/CD turns "trust me" into an automated, gated, repeatable path from idea to production.`

## Previous Lesson Connection
Day15–Day19 tracked work and integrated code; Day20 answers how a team *automatically* trusts that what merges is safe to ship.

## Why It Exists
"I tested locally" = one machine, one environment, one person, one moment — unrepeatable and invisible to the team.

## Engineering Problem
Establish objective, repeatable quality and reliable delivery instead of personal promises and manual deploys.

## Core Concepts

- **CI = a trusted quality process**, not just "running tests": every change runs the same automated checks, visible to all.
- **Pipeline = standard workflow** with four properties: standard stages, stage dependency, fail fast, fast feedback. Run cheap likely-to-fail checks (lint) before expensive ones (integration).
- **Quality gate = risk control** that protects `main`, production, the team, and users: only passing changes move forward. Turns "please don't merge broken code" into "you cannot."
- **CD = two distinct ideas.** *Continuous Delivery* = always ready to release (a production-ready candidate is built; a human may still approve the production release). *Continuous Deployment* = once every required gate passes, production deployment happens automatically. Both give repeatability, consistency, reliability, scalability.
- **Workflow as Code / Everything as Code.** The pipeline lives in the repo (versioned, reviewable, auditable), and so do infra, config, and prompts.

## Production Scenario
A regulated team uses Continuous Delivery (every merge builds a production-ready candidate; a human approves the release). A fast-moving team uses Continuous Deployment (once gates pass, it ships automatically).

## Trade-offs
Automation catches defects no single person catches reliably and scales delivery, at the cost of building and maintaining the pipeline. Choosing Continuous Deployment over Delivery trades a human safety check for release speed — only when the automated gates are trusted enough.

## Real Classroom Misconceptions & Corrections
The lesson explicitly flags an **industry-level** confusion (not a recorded student error): *conflating Continuous Delivery with Continuous Deployment.* The student's own answer was on the right track; the Tech Lead's correction is what to preserve:
- *Wrong framing:* "CD always deploys automatically."
- *Correct model:* Delivery = always *ready* to release (may need manual approval); Deployment = actually releasing automatically once gates pass. Distinguish `Delivery = ready` from `Deployment = live`.

## CI vs CD vs Deployment Comparison

| Term | Question | Guarantee |
|---|---|---|
| Continuous Integration | is every change validated automatically? | same checks, every change, visible |
| Continuous Delivery | are we always ready to release? | a production-ready candidate exists (approval optional) |
| Continuous Deployment | does it ship automatically? | production deploy after all gates pass, no manual step |

## Engineering Checklist
- [ ] Every change runs the same automated CI, not local trust.
- [ ] The pipeline is ordered to fail fast and give fast feedback.
- [ ] A quality gate blocks changes that fail checks.
- [ ] Delivery/deployment is automated and repeatable.
- [ ] The workflow is defined as code and reviewed like code.

## Next Lesson Connection
Day20 is the *principles*; Day21 implements them with a real tool — GitHub Actions.

---

# Day21 — GitHub Actions Fundamentals

## One-line Mental Model
`A workflow describes the process as code; a runner executes it; the quality gate decides what is allowed to build and deploy.`

## Previous Lesson Connection
Directly implements Day20: trusted quality process → a workflow on every PR; fail fast → ordered jobs/steps; quality gate → required checks before build; workflow as code → `.github/workflows/*.yml`.

## Why It Exists
"Please run the tests before you push" is unrepeatable and invisible. The workflow must live in the repo, run automatically on the right events, and block bad changes.

## Engineering Problem
Express a CI pipeline as versioned, event-driven code that runs on the correct machine.

## Core Concepts (execution model)

```text
Git Event -> Trigger (on) -> Workflow -> Scheduler -> Runner (runs-on)
          -> Job (one runner execution context) -> Workspace (checkout)
          -> Step (uses / run / with) -> Quality Gate -> Build -> Deploy
```

- **Workflow as Code.** GitHub executes what you define; it does not invent your process. `.github/workflows/` is Convention over Configuration.
- **Workflow vs Runner.** Description (workflow) and execution (runner) are separated, so the same workflow runs on different machines.
- **Trigger (`on`) = event-driven.** Controls cost, runner usage, feedback time, DX. `on` = *when* (event), NOT the OS.
- **Runner: hosted vs self-hosted.** The main difference is **control**, not speed. Hosted = general/stateless/standardized, fresh ephemeral VM per job. Self-hosted = internal network, GPU, data control — with higher operational *and* security responsibility. More control ≠ more safety.
- **Job = one runner execution context.** Fresh & ephemeral on hosted; may persist state on self-hosted unless made ephemeral/isolated. Split jobs by execution environment and dependency, not business labels.
- **Step: `run` / `uses` / `with`.** `run` = shell command; `uses` = reusable Action; `with` = action parameters (function arguments).
- **Checkout** initializes the workspace — a fresh runner has no repo code.
- **Secrets vs env vars.** `env` = plain, visible config (`APP_ENV`, `LOG_LEVEL`); `${{ secrets.NAME }}` = encrypted at rest, masked in logs (API keys, tokens, DB URLs). Scope: workflow → job → step.
- **Quality gate before build.** If Ruff is part of the gate, a lint failure must block the Docker build; build is an artifact stage, not validation.

## Production Scenario
An AI backend CI has a hosted `quality` job (lint/test) plus a self-hosted `gpu-eval` job (model evaluation) running in parallel, with `build` depending on `quality` so no image is built from code that failed the gate.

## Trade-offs
See Day21's four trade-offs: hosted vs self-hosted runner (control vs operational/security burden), one job vs many (simplicity vs parallelism/isolation), build before vs after the gate (safety vs image availability), `uses` vs `run` (standardization + supply-chain trust vs full control). **Action pinning:** `@v4` = movable major tag (easy updates); full commit SHA = immutable (stronger supply-chain guarantee) — prefer SHA for third-party/high-security actions.

## Real Classroom Misconceptions & Corrections

| Wrong belief | Why it seemed reasonable | Correct engineering model |
|---|---|---|
| `on` selects the OS | "on Ubuntu" sounds like it belongs to `on` | `on` = trigger (when); `runs-on` = runner/OS (where) |
| `run` defines when the workflow runs | "run" sounds like "run the workflow" | `run` = a shell command in a step |
| `uses` runs a shell command | both appear as steps | `uses` = reusable Action; `run` = raw shell |
| Put every stage in one job | one job shares state and looks simpler | split by runner lifecycle, parallelism, dependency, failure isolation |
| A secret is just an env var | both inject `KEY=value` | secret = encrypted + masked; env = plain visible config |
| Docker build can run even if Ruff fails | a build can technically still succeed | when Ruff is in the gate, its failure must block the build |
| Self-hosted is mainly *faster* | hosted is easy, so self-hosted must add speed | the reason is **control** (network/GPU/data), not speed |
| The code is already on the runner | local dev always has the code | a fresh runner is empty; `checkout` downloads the target commit first |

## Engineering Checklist
- [ ] I can draw Event → Trigger → Workflow → Runner → Job → Step → Result.
- [ ] I know the difference between `on`, `runs-on`, `run`, `uses`, `with`.
- [ ] Checkout is the first step on any job that needs code.
- [ ] Secrets come from `${{ secrets.* }}`, never hardcoded or printed.
- [ ] Build depends on the quality gate passing.

## Next Lesson Connection
A basic workflow cannot scale, reuse process, or deploy safely — Day22 adds matrix, cache, artifact, reuse, conditions, and a deployment pipeline.

---

# Day22 — GitHub Actions Advanced

## One-line Mental Model
`Build once, deploy many: what was tested must be, byte-for-byte, what is deployed.`

## Previous Lesson Connection
Bridges from one Day21 fact: **different jobs do not share a filesystem by default**, so data between jobs needs an explicit transfer mechanism (artifacts).

## Why It Exists
A basic workflow must become production-capable: scale testing, move results between jobs, reuse process across repos, control execution, and deploy a *verified* artifact.

## Engineering Problem
Scale, reuse, control, and safely promote exactly the artifact that was tested.

## Core Concepts

- **Matrix = one job template expanded by variables.** It normally still creates N jobs; it removes duplicated YAML and prevents config drift. Distinguish *wall-clock time* (how long you wait) from *runner-minutes* (sum of job time).
- **`fail-fast`.** Decide by whether the *remaining* combinations still have independent diagnostic/compatibility/release value — not by whether configs "look similar." `true` = one failure is enough; `false` = each environment is an independent commitment.
- **Cache vs Artifact.** Cache = re-creatable acceleration data (keyed by OS + dependency-file hash); a workflow must still be correct on a cache miss. Artifact = this run's formal output, transferred between jobs and retained for audit. Never use a cache as the official store for a result.
- **Composite Action vs Reusable Workflow.** Composite Action = reusable **steps** (no `jobs`/`runs-on`; runs inside the caller job). Reusable Workflow = reusable **jobs/workflow** (owns `jobs`, `runs-on`, `needs`; called via `workflow_call`). A reusable workflow must live *directly* under `.github/workflows/`.
- **`needs` / `if` / `continue-on-error`** are three separate mechanisms: dependency/ordering, execution decision, failure tolerance. `continue-on-error` (executed and failed, does not block) ≠ skipped (did not execute).
- **Deployment pipeline.** Reliable deployment = verified artifact + controlled promotion + protected credentials + concurrency control + observability + recovery. Build once → verify the *exact digest* → approve → deploy the same immutable digest. Source tests validate source; image verification validates the built runtime artifact. Use a **registry + immutable digest** (`my-api@sha256:...`), never a mutable `:latest`. `environment: production` adds required reviewers + production Secrets; `concurrency` is a *config block* (`group` + `cancel-in-progress: false`) that serializes deploys.

## Production Scenario
A tagged release builds one image, pushes it, verifies the exact digest (pull, run, smoke test), an accountable owner approves the `production` environment, and the *same digest* deploys under a serialized concurrency group.

## Trade-offs
Matrix coverage vs cost; `fail-fast` fast stop vs complete diagnosis; cache speed vs stale-state risk; artifact auditability vs storage/exposure; composite (small step reuse) vs reusable workflow (central governance, wider blast radius); deployment approval vs speed; serial deploy vs waiting for newer releases.

## Real Classroom Misconceptions & Corrections

| Wrong belief (verbatim / reconstructed) | Correct engineering model |
|---|---|
| "Matrix's main problem is *wasting resources* / it saves resources by avoiding three jobs" | Matrix normally still creates N jobs; it removes duplicated YAML and prevents drift |
| "`fail-fast` depends on whether configs are the same or different" | It depends on whether remaining combinations still have independent value |
| "Reusing **steps** is like a Reusable Workflow" (inverted) | Composite Action = reusable steps; Reusable Workflow = reusable jobs/workflow |
| "`needs` is mainly for uploading/downloading an artifact in a later job" | `needs` defines dependency/ordering; artifacts transfer files — different problems |
| "Deploy reuses the artifact mainly to *save rebuild resources*" | The primary reason is **integrity**: what we deploy must be byte-for-byte what we tested |
| "A Product Manager should perform the production evaluation" | Approval belongs to whoever can own THIS release's specific risk (often engineering/platform/security) |
| "Set `concurrency` to `false`" | `concurrency` is a config block; `cancel-in-progress` is the boolean decision |
| "Ship the Docker image as a GitHub Artifact" | Use a container registry + immutable digest; artifacts hold reports/SBOMs/digest metadata |

## Cache vs Artifact Comparison

| | Cache | Artifact |
|---|---|---|
| Purpose | re-creatable acceleration | this run's formal output |
| Identity | OS + dependency-file hash | run + name |
| On miss/absence | slower, still correct | the output is lost (never rely on it as store) |
| Examples | pip downloads, Playwright Chromium | `coverage.xml`, `app.tar.gz`, `evaluation-results.json` |

## Engineering Checklist
- [ ] I can count the jobs a matrix generates and know they do not share a filesystem.
- [ ] I choose `fail-fast` by the value of the remaining combinations.
- [ ] I classify each file as cache (re-creatable) or artifact (official output).
- [ ] I deploy an immutable digest, never `:latest`, and never rebuild in deploy.
- [ ] Production is protected (environment approval) and serialized (`cancel-in-progress: false`).

## Next Lesson Connection (knowledge boundary)
Day22 builds and deploys *images* it does not yet know how to create. **Day23 Docker** provides the container/image model those digests represent. Docker itself is **not taught here** — it is the next problem, not a Day15–Day22 capability.

---

# Day15–Day22 Mental Model Evolution

One continuous chain of how understanding changed across the phase (each step is corrected against a real lesson):

```text
Git = saving/backing up files
  -> Git = managing immutable objects, references, and history (snapshot, not diff)
  -> Branch = a full copy of the code
  -> Branch = a movable reference; merge integrates immutable history, conflict keeps humans in charge
  -> Pushing to main is just faster
  -> main is shared state; a Pull Request is a gate (rules + intent + discussion + audit)
  -> History just needs to work
  -> History is for humans; merge strategy chooses what they read; review improves code, dev, team
  -> An Issue is a bug report
  -> An Issue is a work item; Project shows where work is; untracked work does not exist
  -> "It works on my machine" is enough
  -> CI is a trusted process; a quality gate controls risk; Delivery (ready) differs from Deployment (live)
  -> A workflow just runs my tests
  -> A workflow is process-as-code; a job is one runner execution context; on = when, runs-on = where
  -> Matrix saves resources; reusing steps is a reusable workflow; deploy reuses artifacts to save rebuilds
  -> Matrix expands one definition into isolated jobs; composite = steps, reusable workflow = jobs;
     build once and deploy the exact immutable digest for integrity
```

---

# Cross-Course Comparison Tables

Each comparison below was taught in Day15–Day22. Format: essence · when to use · common error · trade-off.

### Working Tree / Staging Area / Repository (Day15)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Working Directory | files you currently edit | active editing | expecting `commit` to save this directly | freedom to edit vs not yet recorded |
| Staging Area / Index | blueprint of the next commit | selecting what to commit | committing staged v1 while WD has v2 | control over commit content vs extra step |
| Repository | all commits, blobs, trees, refs | history, rollback | thinking it holds only the current project | full history vs storage |

### Commit / Branch / Tag (Day15–Day16)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Commit | immutable snapshot object | record a state | thinking it can be edited in place | reliable rollback vs immutability |
| Branch | movable reference to a commit | isolate parallel work | thinking it copies the project | cheap parallelism vs must be integrated |
| Tag | reference marking a point (e.g. release) | mark a release (`v*` triggers, Day22) | confusing a tag with a branch | stable label vs not a working line |

### Merge / Rebase (Day16, Day18)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Merge | new commit joining two histories | integrate diverged work | expecting Git to auto-resolve intent | preserves both histories vs merge commit |
| Rebase | replay commits onto a new base | linear history, few clean commits | rebasing shared/published history | clean linear log vs rewritten identity |

### Merge Commit / Squash / Rebase Merge (Day18)
| Strategy | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Merge commit | keep all commits + join | meaningful steps | flattening meaningful history | detail vs `main` noise |
| Squash | one product commit | noisy feature branch | losing needed step history | clean `main` vs lost steps |
| Rebase merge | linear, commits kept | few clean commits | using on shared history | straight line vs rewritten identity |

### Issue / Milestone / Project (Day19)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Issue | one work item | track any task | treating it as bugs-only | visible work vs tracking overhead |
| Milestone | delivery goal of many Issues | track a release target | confusing a goal with a task | progress visibility vs planning effort |
| Project | workflow board (where work is) | see stage/bottlenecks | treating it as task storage | flow visibility vs board upkeep |

### CI / Continuous Delivery / Continuous Deployment (Day20)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| CI | trusted, repeatable validation | every change | "just running tests" | shared quality vs pipeline maintenance |
| Continuous Delivery | always ready to release (candidate) | regulated / approval needed | assuming it auto-deploys | ready-to-ship vs manual approval |
| Continuous Deployment | auto-ship once gates pass | trusted gates | shipping with weak gates | speed vs no human safety check |

### Workflow / Job / Step / Action (Day21)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Workflow | process as code | define the pipeline | configuring in a UI instead | versioned/reviewable vs YAML upkeep |
| Job | one runner execution context | isolate environment/failure | putting everything in one job | isolation/parallelism vs no shared filesystem |
| Step | a concrete task in a job | ordered work | confusing `run` and `uses` | sequential clarity vs shared job workspace |
| Action | reusable capability via `uses` | standard operations | trusting unpinned third-party actions | reuse vs supply-chain risk (pin versions) |

### Cache / Artifact (Day22)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Cache | re-creatable acceleration | speed up repeated installs | using it as the result store | faster builds vs stale-state risk |
| Artifact | formal run output | move/preserve results | assuming it must exist (see `if-no-files-found`) | auditability vs storage/exposure |

### Reusable Workflow / Composite Action (Day22)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Composite Action | reusable **steps** | repeated operation sequences | thinking it owns `jobs` | flexible step reuse vs no job control |
| Reusable Workflow | reusable **jobs/workflow** | org-wide pipeline policy | placing it in a subdirectory | central governance vs wider blast radius |

### Environment Variable / Secret (Day21)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| Environment variable | plain, visible config | `APP_ENV`, `LOG_LEVEL` | storing credentials in `env` | simple/versioned vs exposed |
| Secret | encrypted at rest, masked in logs | API keys, tokens, DB URLs | hardcoding or printing it | protected vs must be managed/scoped |

### GitHub-hosted / Self-hosted Runner (Day21)
| Concept | Essence | When | Common error | Trade-off |
|---|---|---|---|---|
| GitHub-hosted | general, stateless, fresh ephemeral VM | public/general CI | assuming it can reach internal systems | low burden vs limited network/hardware |
| Self-hosted | your machine (internal net, GPU) | internal access, GPU, data control | assuming "more control = safer" | control vs operational + security responsibility |

---

# Stage Completion Check

Have you actually built the software-delivery mental model? You should be able to, without notes:

- [ ] Explain the whole-stage sentence: delivery = traceable, reviewable, verifiable, reproducible, recoverable change.
- [ ] Trace one change from local edit → commit → branch → PR → CI/gate → merge → deploy.
- [ ] Say which layer to inspect for a given failure (see [memory-map.md](memory-map.md) Failure Reasoning Map).
- [ ] Distinguish Delivery (ready) from Deployment (live).
- [ ] Distinguish cache (re-creatable) from artifact (official output).
- [ ] Distinguish composite action (steps) from reusable workflow (jobs).
- [ ] Explain why a deployment must promote an immutable digest, not `:latest`.
- [ ] Name why Docker (Day23) is the *next* problem, not a capability you already have.

---

# Source Map

| Section | Repository Source |
|---|---|
| Whole-stage model, knowledge chain | `docs/git/day15-git-fundamentals.md`, `docs/devops/day20-ci-cd-foundations.md`, `CURRICULUM.md` |
| Day15 concepts, reset table, misconceptions | `docs/git/day15-git-fundamentals.md` |
| Day16 concepts, merge table, misconception | `docs/git/day16-branch-and-merge.md` |
| Day17 concepts, Rules vs Intent | `docs/git/day17-github-workflow.md` |
| Day18 concepts, merge-strategy table | `docs/git/day18-merge-strategy-and-code-review.md` |
| Day19 concepts, work hierarchy | `docs/github/day19-project-management.md` |
| Day20 concepts, CI/CD/Deployment table | `docs/devops/day20-ci-cd-foundations.md` |
| Day21 concepts, misconceptions, runner/secret tables | `docs/devops/day21-github-actions-fundamentals.md` |
| Day22 concepts, misconceptions, cache/artifact tables | `docs/devops/day22-github-actions-advanced.md` |
| Day23 boundary note | `CURRICULUM.md`, `ROADMAP.md` |
