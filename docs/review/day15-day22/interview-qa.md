# Day15–Day22 Engineering Foundations Interview Q&A

> Part of the **Day15–Day22 Engineering Foundations Second Brain**.
> Companion documents: [super-cheatsheet.md](super-cheatsheet.md) · [memory-map.md](memory-map.md) · [code-templates.md](code-templates.md) · [one-page.md](one-page.md)

This is the **expression & judgment** layer of the Second Brain. It trains you to move *from a concept to an engineering decision*, not to recite definitions. The `30-Second Answer` is meant to be said aloud in an English or Chinese interview; the `Engineering Expansion` explains system behavior, state changes, and failure paths.

Notes on integrity: `Common Wrong Answer` uses a real recorded classroom misconception where one exists; where the repository recorded no incorrect belief, it says so rather than inventing one. No interview frequencies are claimed, and no answer is presented as the single "standard" wording.

---

# Day15 — Git Fundamentals

## Question: Is Git's core storage model a diff or a snapshot?

### 30-Second Answer
Git stores snapshots. Each commit references a full tree of the project, and Git creates new objects only for changed content while reusing references to unchanged blobs.

### Engineering Expansion
A pure-diff model would rebuild any old version by replaying every diff from the start, making checkout slow. Snapshots plus object reuse make checking out any commit direct, and immutability by content hash makes rollback reliable.

### Production Example
Restoring a known-good state after a bad deploy is instant because the old snapshot already exists as an object; Git points at it rather than reconstructing it.

### Trade-off
Snapshots cost more conceptual complexity than "just diffs," and require content-addressed storage, but buy fast checkout and reliable rollback.

### Common Wrong Answer
"Git only saves the changed lines, like a diff." (Recorded classroom belief.) It fails because retrieving old versions would require replaying history.

### Follow-up Questions
Why is a commit immutable? How does object reuse relate to Python shared references?

### Source
`docs/git/day15-git-fundamentals.md`

---

## Question: What is the difference between HEAD and a branch?

### 30-Second Answer
A branch is a movable reference to a commit; HEAD is the current reference, usually pointing to a branch. A new commit moves the branch HEAD points to.

### Engineering Expansion
Normally `HEAD -> branch -> commit`. Committing advances the branch and HEAD follows. In detached HEAD, HEAD points directly at a commit, so a new commit there is owned by no branch and can become unreachable.

### Production Example
Checking out an old SHA to investigate a bug puts you in detached HEAD; any commit you make is not on a branch until you create one.

### Trade-off
The extra indirection (HEAD → branch → commit) enables cheap branching and clear "current position," at the cost of a model beginners initially find surprising.

### Common Wrong Answer
"HEAD is just the current commit." (Recorded classroom belief.) It misses that HEAD usually points to a branch, and the detached case.

### Follow-up Questions
What happens to a commit made in detached HEAD? How do you recover it?

### Source
`docs/git/day15-git-fundamentals.md`

---

## Question: Explain `reset --soft` vs `--mixed` vs `--hard`.

### 30-Second Answer
All three move HEAD/the branch. `--soft` stops there; `--mixed` also resets the Index (un-stage); `--hard` also resets the Working Directory, discarding uncommitted edits.

### Engineering Expansion
Reset is reference movement plus optional tree synchronization. `--soft` keeps changes staged, `--mixed` keeps them in the Working Directory unstaged, `--hard` throws them away. Only `--hard` can destroy uncommitted work irrecoverably.

### Production Example
To un-commit but keep everything staged for re-commit, use `--soft`; to un-stage while keeping edits, use `--mixed`.

### Trade-off
`--hard` gives a clean slate fast but risks unrecoverable loss; `--soft`/`--mixed` are safer but leave you to re-handle the changes.

### Common Wrong Answer
Believing all resets are equally safe. The recorded student correctly knew `--soft` moves the reference but needed correction that `--mixed` resets the Index and `--hard` also resets the Working Directory.

### Follow-up Questions
Which reset can lose uncommitted work? Can reflog recover a `--hard` that wiped uncommitted edits?

### Source
`docs/git/day15-git-fundamentals.md`

---

## Question: How does `git reflog` recover a mistaken reset?

### 30-Second Answer
Reflog records every position HEAD has held. Even after a reset removes a branch reference, the commit object still exists, so you find its SHA in reflog and reset or check out to it.

### Engineering Expansion
`git log` shows reachable history; `git reflog` shows HEAD movement. Because commits are immutable and not immediately garbage-collected, an "unreachable" commit is still restorable via its SHA — but only if it was committed.

### Production Example
After `git reset --hard HEAD~1`, `git reflog` reveals the old SHA and `git reset --hard <sha>` restores it.

### Trade-off
Reflog is a powerful safety net for commits, but it does nothing for changes that were never committed.

### Common Wrong Answer
"A hard reset deletes the commit forever." It usually remains as an unreachable object for a while.

### Follow-up Questions
Would reflog help with uncommitted edits? What is the difference between `git log` and `git reflog`?

### Source
`docs/git/day15-git-fundamentals.md`

---

# Day16 — Branch & Merge

## Question: Why is creating a branch nearly instant, even in a huge repository?

### 30-Second Answer
A branch is a movable reference — one small file holding a commit hash — not a copy of the project. Creating it is O(1) regardless of repo size.

### Engineering Expansion
If `git branch` copied a 5GB project it would be slow; it is instant, which proves it only writes a reference. This is why teams freely create many short-lived branches.

### Production Example
Every feature, test fix, and prompt experiment gets its own branch at no storage or speed cost.

### Trade-off
Cheap branches make parallel work easy, but the work still must be integrated deliberately through a merge.

### Common Wrong Answer
"`git branch` copies the code into a new folder." (Recorded classroom belief.) Copying would be slow; branch creation is instant.

### Follow-up Questions
In object-model terms, what did `git branch` create? What moves when you commit on it?

### Source
`docs/git/day16-branch-and-merge.md`

---

## Question: Fast-forward vs three-way merge — what is the difference?

### 30-Second Answer
Fast-forward just advances the target reference when it has not diverged (no merge commit, linear history). A three-way merge, when both branches have new commits, creates a merge commit with two parents.

### Engineering Expansion
Fast-forward is pure reference movement because there is nothing to reconcile. A three-way merge preserves both diverged histories without rewriting either — the merge commit points back to both tips.

### Production Example
A tiny fix onto an unchanged `main` fast-forwards; a two-week feature merged after `main` got a hotfix creates a merge commit keeping both.

### Trade-off
Fast-forward keeps history linear but records no explicit integration point; a merge commit preserves both histories at the cost of an extra node.

### Common Wrong Answer
"Merging always creates a merge commit." Not when the target has not diverged.

### Follow-up Questions
How many parents does a merge commit have, and why? Why can't a divergent merge just move one pointer?

### Source
`docs/git/day16-branch-and-merge.md`

---

## Question: Why does Git stop on a merge conflict instead of choosing a version?

### 30-Second Answer
Because choosing could silently ship the wrong business logic. When two branches change the same line differently, Git cannot know which is correct, so it refuses to guess and asks a human.

### Engineering Expansion
A conflict is not an error; it is Git protecting you from an unsafe automatic guess. The human resolves intent, and Git records the resolution as a merge commit.

### Production Example
Two engineers edit the same prompt line differently; Git surfaces a conflict rather than shipping a prompt that changes answer quality.

### Trade-off
Human resolution is slower than auto-merging, but it keeps semantic correctness in human hands.

### Common Wrong Answer
"Git should just take the newer or bigger change." That risks shipping wrong logic silently.

### Follow-up Questions
What does the merge commit point to after resolution? Why is a conflict evidence of good design?

### Source
`docs/git/day16-branch-and-merge.md`

---

# Day17 — GitHub Workflow & Collaboration

## Question: Why shouldn't developers push directly to `main`?

### 30-Second Answer
`main` is shared, releasable state. A direct push skips review and CI, so one person's untested mistake instantly breaks everyone who depends on `main`.

### Engineering Expansion
Unguarded shared state is where team-scale bugs come from. Routing every change through a Pull Request inserts a gate between an individual mistake and the team's line.

### Production Example
A config change pushed straight to `main` at 5pm fails the deploy and blocks everyone; a PR with CI would have caught it.

### Trade-off
The gate adds latency to each change, but prevents team-wide breakage and preserves an audit trail.

### Common Wrong Answer
`Not established in Day15–Day22 repository sources` — the recorded student answered this correctly ("other people depend on `main`"). A generic weak answer would be "direct push is faster and my code works locally."

### Follow-up Questions
What four things does a Pull Request bundle? What makes the gate mandatory rather than optional?

### Source
`docs/git/day17-github-workflow.md`

---

## Question: What is the difference between CI validating rules and a human validating intent?

### 30-Second Answer
CI is a machine validating rules — build, tests, lint, coverage. Code review is a human validating intent — whether the change is the right thing for the business. You need both.

### Engineering Expansion
CI cannot judge whether a feature is a good idea; a human cannot reliably re-run thousands of tests. Green CI means the rules pass, not that the change is correct.

### Production Example
CI passes, but a reviewer notices the endpoint returns 200 for an unauthorized user — an intent bug no test covered.

### Trade-off
Requiring both maximizes safety but costs reviewer time; relying on only one leaves a gap (missed bugs or missed intent).

### Common Wrong Answer
"If CI is green, the change is correct and can merge." It only proves the rules pass.

### Follow-up Questions
Give an example of an intent bug CI cannot catch. Why keep the review discussion afterward?

### Source
`docs/git/day17-github-workflow.md`

---

## Question: What is a stale review, and why does Branch Protection dismiss it?

### 30-Second Answer
A stale review is an approval that no longer applies because new commits were pushed after it. The approval was about an earlier state, so protection can dismiss it and require re-review.

### Engineering Expansion
An approval is a statement about a specific reviewed state. Changing the state invalidates the statement, so the approval must not carry over to code that was never reviewed.

### Production Example
A reviewer approves a small fix; you then add a risky refactor. Dismissing the stale approval forces a fresh look at what will actually merge.

### Trade-off
Re-review adds friction after late changes, but prevents unreviewed code from riding an old approval into `main`.

### Common Wrong Answer
"Once approved, always approved." The approval only covered the earlier commit.

### Follow-up Questions
How can Branch Protection enforce re-review automatically? Why is approval tied to a specific state?

### Source
`docs/git/day17-github-workflow.md`

---

# Day18 — Merge Strategy & Code Review

## Question: When would you choose squash vs merge commit vs rebase merge?

### 30-Second Answer
Squash for a noisy feature branch (one clean product commit). Merge commit when individual commits are meaningful and you want an explicit integration record. Rebase for a few clean commits when you want linear history — but never on shared history.

### Engineering Expansion
Merge strategy chooses what humans read on `main`. Squash discards development noise; merge commit preserves all commits plus a two-parent join; rebase replays commits linearly but rewrites identity (`C -> C'`).

### Production Example
A 40-commit "wip" branch squashes into "Add /agent endpoint with auth"; a deliberate multi-step migration uses a merge commit so each step stays visible.

### Trade-off
Squash keeps `main` clean but loses step history; merge commit keeps detail but can clutter; rebase gives a straight line but rewrites identity (unsafe if shared).

### Common Wrong Answer
`Not established in Day15–Day22 repository sources` — the recorded student reasoned correctly. A generic weak answer: "always squash everything" ignores cases where step history matters.

### Follow-up Questions
Which strategy rewrites commit identity, and why does that limit its use? What belongs in product vs development history?

### Source
`docs/git/day18-merge-strategy-and-code-review.md`

---

## Question: What do senior engineers focus on in code review?

### 30-Second Answer
Architecture, performance, security, and maintainability — the risks machines cannot judge. Formatting and style are left to linters.

### Engineering Expansion
Human attention is scarce, so it should go to design fit, scaling risks (N+1 queries, blocking calls), auth/input-validation/secret handling, and whether the next engineer can safely change the code.

### Production Example
A reviewer approves well-formatted code that opens a blocking DB call inside an async endpoint — a performance bug the linter never saw.

### Trade-off
Deep review catches serious risks but costs senior time; delegating style to tools frees that time.

### Common Wrong Answer
Reviewing only indentation and variable names — missing the architecture, performance, and security risks.

### Follow-up Questions
Which of those issues would CI likely miss? How does "review the code, not the coder" keep review productive?

### Source
`docs/git/day18-merge-strategy-and-code-review.md`

---

# Day19 — GitHub Project Management

## Question: Is a GitHub Issue just a bug report?

### 30-Second Answer
No. An Issue is any work item — bug, feature, task, chore, question, or spike. It provides collaboration, tracking, prioritization, and ownership.

### Engineering Expansion
Untracked work lives in memory and chat and disappears. Making work an Issue gives it an owner (responsibility to deliver, not blame), a priority, and a place in the plan.

### Production Example
"We should add rate limiting," said in a meeting, evaporates; as an Issue it has an owner and a priority and can be scheduled.

### Trade-off
Tracking everything adds process overhead, but prevents dropped work and hidden priorities.

### Common Wrong Answer
"Issues are for bugs." (Recorded classroom belief.) Features and tasks also need tracking or they vanish.

### Follow-up Questions
Why does ownership not mean blame? What four problems does an Issue solve at once?

### Source
`docs/github/day19-project-management.md`

---

## Question: What is the difference between an Issue and a Project (board)?

### 30-Second Answer
An Issue answers "what work exists?"; a Project answers "where is the work now?" Issues are units of work; a Project manages workflow — the movement of work through stages.

### Engineering Expansion
A board (Backlog → In Progress → Review → Done) exposes flow and bottlenecks. Issue management is about the units; project management is about their stage in the pipeline.

### Production Example
Standup becomes "what is stuck in Review?" because the board shows every Issue's current column.

### Trade-off
A board adds upkeep but makes flow, bottlenecks, and priorities visible to the whole team.

### Common Wrong Answer
Treating a Project as just a place to store tasks, rather than a workflow view.

### Follow-up Questions
How is a Label like a database index or RAG metadata filter? What does a Milestone show that an Issue cannot?

### Source
`docs/github/day19-project-management.md`

---

## Question: Why is a Label more than a colored tag?

### 30-Second Answer
A Label is structured metadata on work. It enables retrieval (filter by `security`), workflow (states like `needs-review`), and automation (routing or triggers).

### Engineering Expansion
Labels make thousands of Issues searchable and automatable, the same way database indexes speed lookup, RAG filters documents by metadata, and Kubernetes selects resources by label.

### Production Example
Filtering `label:security label:priority-high` surfaces exactly the risky work to do first.

### Trade-off
Consistent labels require taxonomy discipline, but unlock filtering and automation at scale.

### Common Wrong Answer
"A label just groups Issues by color." It is queryable, structured metadata.

### Follow-up Questions
Which of retrieval, workflow, or automation does a given label serve? How does labeling relate to routing work to a team?

### Source
`docs/github/day19-project-management.md`

---

# Day20 — CI/CD Foundations

## Question: Why is "it works on my machine" not enough to merge and deploy?

### 30-Second Answer
Local testing is one machine, one environment, one person, one moment — unrepeatable and invisible to the team. Trusted quality needs the same automated checks on every change.

### Engineering Expansion
CI replaces personal trust with an objective, repeatable, shared process. Quality should come from process, not a promise, so a forgotten local test is still caught on the PR.

### Production Example
A developer forgets to run tests; CI runs them on the Pull Request and catches the failure before merge.

### Trade-off
CI requires building and maintaining a pipeline, but removes reliance on individual discipline.

### Common Wrong Answer
"If it passes locally, it's fine." One environment and one moment do not represent the team or production.

### Follow-up Questions
What does CI provide that a local test cannot? What are the four properties of a pipeline?

### Source
`docs/devops/day20-ci-cd-foundations.md`

---

## Question: What is the difference between Continuous Delivery and Continuous Deployment?

### 30-Second Answer
Continuous Delivery keeps you always *ready* to release — it builds a production-ready candidate, but a human may still approve the actual release. Continuous Deployment ships to production *automatically* once every required gate passes.

### Engineering Expansion
Delivery guarantees a validated artifact exists; Deployment removes the manual approval step. Both provide repeatability, consistency, reliability, and scalability. Choose Deployment only when the gates are trusted enough to ship without a human.

### Production Example
A regulated team uses Delivery with a human approving each production release; a fast-moving team uses Deployment where passing gates ship automatically.

### Trade-off
Deployment maximizes speed but removes a human safety check; Delivery keeps that check at the cost of slower release.

### Common Wrong Answer
Conflating the two — "CD always deploys automatically." The lesson explicitly flags this industry confusion; Delivery may still require approval.

### Follow-up Questions
When would you deliberately keep manual approval? What must be true of your gates before choosing Deployment?

### Source
`docs/devops/day20-ci-cd-foundations.md`

---

## Question: What does a quality gate protect, and why block rather than only report?

### 30-Second Answer
A quality gate is risk control: only changes that pass required checks move forward. It protects `main`, production, the team, and users by stopping bad changes at the boundary.

### Engineering Expansion
Blocking turns "please don't merge broken code" into "you cannot." If a gate only reports, people merge anyway under pressure; enforcement makes the safe path the only path.

### Production Example
A PR with failing tests or a critical vulnerability is blocked at the gate and cannot reach `main` until it passes.

### Trade-off
A hard gate can slow urgent changes, but prevents defects from reaching users; the fix is faster checks, not a weaker gate.

### Common Wrong Answer
"The pipeline should just report results and let people decide." Reporting without enforcement gets skipped.

### Follow-up Questions
Why run cheap checks first? What does "fail fast" save?

### Source
`docs/devops/day20-ci-cd-foundations.md`

---

# Day21 — GitHub Actions Fundamentals

## Question: What is the difference between `on` and `runs-on`?

### 30-Second Answer
`on` is the trigger — *when* the workflow runs (an event like push or pull_request). `runs-on` selects the runner — *where* a job executes (the machine/OS).

### Engineering Expansion
GitHub Actions is event-driven; `on` controls cost, runner usage, and feedback time. `runs-on` picks the execution environment. Description (workflow) and execution (runner) are separated.

### Production Example
Run the full suite on every PR and push to `main`, but an expensive nightly evaluation only `on: schedule`, while each job's `runs-on` picks hosted or self-hosted.

### Trade-off
Precise triggers save runner minutes; broad triggers guarantee coverage at higher cost.

### Common Wrong Answer
"`on` selects the operating system." (Recorded classroom misconception.) `on` = when; `runs-on` = where.

### Follow-up Questions
What production cost does the trigger control? Why is the workflow/runner separation useful?

### Source
`docs/devops/day21-github-actions-fundamentals.md`

---

## Question: GitHub-hosted vs self-hosted runner — what really differs?

### 30-Second Answer
Control, not speed. Hosted runners are general, stateless, standardized, and low-maintenance but limited in network and hardware. Self-hosted runners give internal network access, custom hardware/GPU, and data control, at the cost of operational and security responsibility.

### Engineering Expansion
Choose self-hosted for internal access, GPU, or sensitive data; otherwise hosted. More control does not mean safer: self-hosted runners can persist state, are exposed to untrusted fork-PR code, and sit inside your network, so a compromise has a large internal blast radius.

### Production Example
A GPU model evaluation against an internal model server runs on a self-hosted GPU runner; general lint/test runs on a hosted runner.

### Trade-off
Self-hosted unlocks internal/GPU workloads but adds maintenance and security burden; hosted is easy but constrained.

### Common Wrong Answer
"Self-hosted is mainly faster." (Recorded classroom belief — the student said "maybe for speed?") The real reason is control.

### Follow-up Questions
Why is a self-hosted runner not automatically safer? What mitigations reduce its blast radius?

### Source
`docs/devops/day21-github-actions-fundamentals.md`

---

## Question: What is the difference between a secret and an environment variable in a workflow?

### 30-Second Answer
An environment variable (`env`) is plain, visible config for non-sensitive values like `APP_ENV`. A secret (`${{ secrets.NAME }}`) is encrypted at rest and masked in logs for sensitive values like API keys and tokens.

### Engineering Expansion
Separate configuration from credentials. Env vars can be visible and versioned; secrets must be encrypted, masked, least-privilege, scoped to the step that needs them, and never printed or exposed to untrusted fork PRs.

### Production Example
CI sets `APP_ENV` as an env var and injects `OPENAI_API_KEY` from secrets only in the step that runs the evaluation.

### Trade-off
Secrets add management overhead (rotation, scoping) but a leaked key is a production incident, so credentials never live in code or logs.

### Common Wrong Answer
"A secret is just an environment variable." (Recorded classroom misconception.) Secrets are encrypted and masked; env vars are plain config.

### Follow-up Questions
What are the workflow/job/step scopes? Why don't untrusted fork PRs get repository secrets by default?

### Source
`docs/devops/day21-github-actions-fundamentals.md`

---

## Question: If Ruff (lint) fails, should the Docker build still run?

### 30-Second Answer
No. If Ruff is part of the quality gate, a lint failure must block the build. Build is an artifact stage, not a substitute for validation.

### Engineering Expansion
The gate enforces order: validate, then build, then deploy. Building from code that failed lint or tests wastes compute and can ship a known-bad artifact; `needs:` makes the build depend on the quality job.

### Production Example
A PR whose `ruff check .` fails stops before Docker build, so no image is produced for broken code.

### Trade-off
Gating the build delays image availability slightly but guarantees only validated code is built.

### Common Wrong Answer
"The build might still succeed, so run it anyway." (Recorded classroom reasoning, then corrected.) A successful build of bad code is still bad.

### Follow-up Questions
Where does the build step belong in the flow? What must precede it?

### Source
`docs/devops/day21-github-actions-fundamentals.md`

---

# Day22 — GitHub Actions Advanced

## Question: Does a matrix build save runner resources?

### 30-Second Answer
No. A matrix normally still creates N jobs — one per combination. What it removes is duplicated YAML, keeping environments aligned to one definition and preventing config drift.

### Engineering Expansion
A matrix is one job template expanded by variables. Distinguish wall-clock time (how long you wait) from runner-minutes (sum of job time): four 5-minute jobs may finish in ~5 minutes but consume ~20 runner-minutes. Matrix jobs are isolated — no shared filesystem or dependencies.

### Production Example
A public SDK tests every supported Python/OS combination from one matrix so a broken environment is impossible to forget.

### Trade-off
More coverage and consistency vs more jobs, runner cost, and possible combinatorial explosion.

### Common Wrong Answer
"Matrix saves resources by avoiding three jobs." (Recorded classroom belief — student said the main problem was "wasting resources.") It usually still produces N jobs.

### Follow-up Questions
Do matrix jobs share installed dependencies? What is the difference between wall-clock and runner-minutes?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

## Question: Cache or artifact — how do you decide?

### 30-Second Answer
Cache is re-creatable acceleration data (dependency downloads, browser binaries) keyed by OS plus a dependency hash; the workflow must still be correct on a cache miss. An artifact is this run's formal output (coverage, reports, packages) transferred between jobs and retained for audit.

### Engineering Expansion
Ask: can the file be re-downloaded/regenerated (cache), or does it represent this run's official result (artifact)? Never use a cache as the store for a current-run result — it can be absent, stale, or evicted. Jobs do not share a filesystem, so artifacts are how results move between jobs.

### Production Example
pip downloads and Playwright Chromium binaries are cached; `coverage.xml` and `evaluation-results.json` are artifacts.

### Trade-off
Cache trades speed against stale-state risk; artifacts trade auditability and cross-job delivery against storage cost and sensitive-data exposure.

### Common Wrong Answer
"Cache and artifacts both just store files." (Recorded classroom weak answer.) They solve different problems.

### Follow-up Questions
Why must a workflow be correct on a cache miss? Why can't a later job just read the earlier job's files directly?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

## Question: Composite action vs reusable workflow — what is the unit of reuse?

### 30-Second Answer
A composite action reuses **steps** and runs inside the caller's job (no `jobs`/`runs-on`). A reusable workflow reuses whole **jobs** — it owns `jobs`, `runs-on`, and `needs`, and is called via `workflow_call`.

### Engineering Expansion
Use a composite action for a repeated step sequence (setup + lint + test); use a reusable workflow to enforce one `lint -> test -> build` pipeline across many repos. A reusable workflow must live directly under `.github/workflows/`; subdirectories are not supported.

### Production Example
An organization ships one reusable FastAPI CI workflow so every service repo runs the same gates and standards do not drift.

### Trade-off
Composite actions give small, flexible step reuse; reusable workflows give central job-level governance at the cost of repo autonomy and a wider blast radius when the central definition changes.

### Common Wrong Answer
"A repeated sequence of steps is a reusable workflow." (Recorded classroom inversion — the student first mapped steps to a reusable workflow.) Repeated steps are a composite action.

### Follow-up Questions
Which one owns `jobs`, `runs-on`, and `needs`? Why pin a called reusable workflow to a commit SHA?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

## Question: How do you make a Docker deployment reliable in GitHub Actions?

### 30-Second Answer
Build the image once, push it to a registry, and deploy the immutable digest — never rebuild in deploy or ship a mutable `:latest`. Gate the deploy behind a production Environment with required reviewers and production-only secrets, and serialize with a concurrency group using `cancel-in-progress: false`.

### Engineering Expansion
"Build once, deploy many" is about integrity: what was tested must be, byte-for-byte, what ships. Source tests validate source; image verification pulls and runs the exact digest to validate the runtime artifact. Rebuilding in deploy can drift (base images, dependencies). Concurrency serializes production so deploys never overlap and half-apply.

### Production Example
A tagged release builds one image, verifies the exact digest with a smoke test, an accountable owner approves the `production` environment, and the same digest deploys under a serialized concurrency group.

### Trade-off
Approval and serialization add release latency but buy accountability and safe, deterministic promotion.

### Common Wrong Answer
"Run `deploy.sh` after tests pass"; "deploy reuses the artifact mainly to save rebuild resources"; "set `concurrency` to false." (Recorded classroom beliefs.) The real reason is integrity, and `concurrency` is a config block, not a boolean.

### Follow-up Questions
Why is cancelling an in-progress production deploy dangerous? Where does the immutable digest come from?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

# Cross-Course System Questions

These integrate Day15–Day22. Each is answerable only because the whole chain was taught.

## Question: How does a single change move from a local edit into a reviewable, releasable state?

### 30-Second Answer
Edit → commit (immutable snapshot) → feature branch (isolation) → push → Pull Request (review + CI + discussion + audit) → quality gate → merge into `main`. The change is now traceable, reviewed, and validated.

### Engineering Expansion
Each stage adds a property: the commit adds traceable history, the branch adds isolation, the PR adds review/CI/audit, the gate adds enforced validation, and the merge integrates history with a chosen strategy.

### Production Example
"Add /agent endpoint" becomes a commit on `feature/agent`, a PR that passes CI and review, and a squash-merge into `main`.

### Trade-off
Every stage adds latency but converts a private edit into a trusted, shared, auditable change.

### Common Wrong Answer
Skipping stages ("just push to main") loses review, validation, and audit.

### Follow-up Questions
Which stage adds traceability? Which adds enforced validation?

### Source
`docs/git/day15-git-fundamentals.md`, `docs/git/day16-branch-and-merge.md`, `docs/git/day17-github-workflow.md`, `docs/devops/day20-ci-cd-foundations.md`

---

## Question: Why does passing CI not mean the change is safe to deploy?

### 30-Second Answer
CI validates rules against the source (build, tests, lint). It does not validate intent, nor does it validate the built runtime artifact or the deployment process. Safety needs human review, image verification, and a controlled deployment.

### Engineering Expansion
Green CI can still hide an intent bug (wrong status code), and source tests do not run the built image. Reliable delivery adds review, image verification of the exact digest, approval, and serialized promotion.

### Production Example
CI passes, a reviewer catches an auth bug, and only after verifying the exact image digest does the change deploy.

### Trade-off
Layering review + verification + approval on top of CI costs time but closes the gaps CI cannot cover.

### Common Wrong Answer
"Green CI means ship it." It only proves the source rules pass.

### Follow-up Questions
What does image verification add over unit tests? Who should approve a production release?

### Source
`docs/git/day17-github-workflow.md`, `docs/devops/day20-ci-cd-foundations.md`, `docs/devops/day22-github-actions-advanced.md`

---

## Question: Why can't a cache and an artifact be treated as the same thing?

### 30-Second Answer
A cache is re-creatable acceleration that may be missing, stale, or evicted, so a workflow must be correct without it. An artifact is this run's official output that must persist and transfer between jobs. Using a cache as the result store risks shipping absent or stale data.

### Engineering Expansion
Their guarantees differ: a cache miss should only cost time; a missing official result is a correctness failure. Jobs do not share a filesystem, so artifacts — not caches — carry results forward.

### Production Example
pip downloads are cached; the evaluation report that approves a release is an artifact.

### Trade-off
Caches speed builds at the risk of stale state; artifacts add storage and exposure cost but are auditable and reliable.

### Common Wrong Answer
"They both store files, so either works." Their reliability guarantees are opposite.

### Follow-up Questions
What happens on a cache miss? Why store an evaluation result as an artifact, not a cache?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

## Question: How does merge strategy affect auditing and rollback?

### 30-Second Answer
Merge strategy decides what history humans can read and revert. A merge commit preserves every step and an explicit integration point; a squash gives one revertible product commit; a rebase gives a linear log but rewrites identity. Readable history makes locating and rolling back a bad change fast.

### Engineering Expansion
Rollback and audit walk the DAG. Squash makes a feature one atomic revert; merge commits keep granular steps for fine-grained rollback; rebase must not be used on shared history because rewritten identities break others' references.

### Production Example
A regression traced to a squash-merged feature is reverted as one commit; a multi-step migration kept as a merge commit allows reverting one step.

### Trade-off
Clean product history (squash) eases high-level rollback but loses step-level granularity; detailed history (merge commit) enables fine rollback but is noisier.

### Common Wrong Answer
"Merge strategy is only cosmetic." It directly shapes what you can audit and revert.

### Follow-up Questions
Which strategy makes a feature a single revert? Why avoid rebasing shared history?

### Source
`docs/git/day18-merge-strategy-and-code-review.md`, `docs/git/day16-branch-and-merge.md`

---

## Question: Why must secrets not be written directly into a workflow file?

### 30-Second Answer
The workflow file is committed to the repository, so a hardcoded key would be exposed in history and logs. Secrets must come from `${{ secrets.NAME }}`, encrypted at rest and masked in logs, scoped to the step that needs them, and withheld from untrusted fork PRs.

### Engineering Expansion
Configuration (env) can be visible; credentials must be encrypted, masked, and least-privilege. A leaked key is a production incident that is hard to remediate once in Git history.

### Production Example
`APP_ENV` is a plain env var; `OPENAI_API_KEY` is injected from secrets only in the evaluation step and never printed.

### Trade-off
Managing secrets (rotation, scoping) costs effort but prevents credential leakage.

### Common Wrong Answer
"Just put the key in the YAML for convenience." It exposes the key in versioned history.

### Follow-up Questions
Why don't fork PRs receive secrets by default? How do workflow/job/step scopes limit exposure?

### Source
`docs/devops/day21-github-actions-fundamentals.md`, `docs/devops/day22-github-actions-advanced.md`

---

## Question: What is the reuse boundary between a reusable workflow and a composite action?

### 30-Second Answer
The unit of reuse. A composite action reuses steps and cannot define jobs, `runs-on`, or dependency topology. A reusable workflow reuses whole jobs and owns exactly those. If it needs its own `jobs`/`runs-on`/`needs`, it is a reusable workflow.

### Engineering Expansion
Composite actions standardize repeated operations inside a job; reusable workflows enforce pipeline policy across repositories. Location matters: reusable workflows must live directly under `.github/workflows/`.

### Production Example
"Setup + lint + test" is a composite action; an org-wide `lint -> test -> build` pipeline is a reusable workflow.

### Trade-off
Composite actions are flexible and local; reusable workflows centralize governance but widen the blast radius of a central change.

### Common Wrong Answer
"Any reuse of steps is a reusable workflow." Reused steps are a composite action.

### Follow-up Questions
Which owns `needs`? Why must a reusable workflow avoid subdirectories?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

## Question: Why is "build once, deploy many" a safety property, not a cost optimization?

### 30-Second Answer
Because rebuilding in deploy can produce a different artifact (base-image, dependency, or environment drift), so what ships would differ from what was tested. Promoting the exact immutable digest guarantees tested = deployed. Saving compute is a side benefit, not the point.

### Engineering Expansion
The integrity chain is: unit tests validate source, image verification validates the built runtime artifact by running the exact digest, and deployment promotes that same digest. A mutable `:latest` breaks the guarantee.

### Production Example
The digest that evaluation approved is the digest that deploys; no rebuild happens in the deploy job.

### Trade-off
Registry + digest handling adds pipeline complexity, but guarantees deployment integrity.

### Common Wrong Answer
"Reuse the artifact mainly to save rebuild time." (Recorded classroom belief.) The primary reason is integrity.

### Follow-up Questions
Why not `:latest`? What does image verification catch that source tests cannot?

### Source
`docs/devops/day22-github-actions-advanced.md`

---

## Question: How do Day15–Day22 combine into one software delivery lifecycle?

### 30-Second Answer
Git tracks history, branches isolate work, GitHub adds collaboration, PR/review gate integration, project management makes work visible, CI/CD automates quality and delivery, GitHub Actions expresses the pipeline as code, and advanced Actions scale, reuse, and deploy a verified digest. Together they make a change traceable, reviewable, verifiable, reproducible, and recoverable.

### Engineering Expansion
Each lesson solves the next lesson's exposed gap, so the tools are one pipeline, not a toolbox. The unifying test is whether one change can enter production with all five properties intact.

### Production Example
An Issue becomes a branch, a PR with CI and review, a squash-merge, a built-and-verified image, and a serialized production deploy of the exact digest — fully traceable end to end.

### Trade-off
The full lifecycle adds process and infrastructure, but replaces trust and manual work with an auditable, repeatable path.

### Common Wrong Answer
Treating each tool as isolated ("Git for code, Actions for tests") misses that they form one delivery chain.

### Follow-up Questions
Which property does each stage add? What is the next problem Docker (Day23) solves in this chain?

### Source
`docs/devops/day20-ci-cd-foundations.md`, `docs/github/day19-project-management.md`, `CURRICULUM.md`

---

# Source Map

| Section | Repository Source |
|---|---|
| Day15 questions | `docs/git/day15-git-fundamentals.md` |
| Day16 questions | `docs/git/day16-branch-and-merge.md` |
| Day17 questions | `docs/git/day17-github-workflow.md` |
| Day18 questions | `docs/git/day18-merge-strategy-and-code-review.md` |
| Day19 questions | `docs/github/day19-project-management.md` |
| Day20 questions | `docs/devops/day20-ci-cd-foundations.md` |
| Day21 questions | `docs/devops/day21-github-actions-fundamentals.md` |
| Day22 questions | `docs/devops/day22-github-actions-advanced.md` |
| Cross-course system questions | Day15–Day22 lessons above, `CURRICULUM.md` |
