# GitHub Workflow Interview

## Purpose

Interview questions and model answers for GitHub collaboration: Pull Requests, CI, code review,
and branch protection.

---

# Day17 GitHub Workflow Questions

These questions come from the Day17 GitHub Workflow & Collaboration lesson. They focus on why
each part of the workflow exists.

## Beginner

### 1. Why shouldn't developers push directly to main?

Question:

Why shouldn't developers push directly to `main`?

中文解析:

main 是团队共享、可发布的分支。直接推送跳过了 review 和 CI，一个人未经测试的错误会立刻影响所有依赖 main 的人。

Standard Answer:

Because `main` is shared, releasable state. A direct push skips review and CI, so one person's
untested mistake immediately breaks everyone who depends on `main`.

Follow-up Question:

What gate replaces the direct push?

### 2. Why do Pull Requests exist?

Question:

Why do Pull Requests exist?

中文解析:

Pull Request 把 review、CI、讨论和审计记录打包成一个门禁，在改动进入 main 之前完成。它让每个改动都被审查、测试、讨论并留痕。

Standard Answer:

A Pull Request bundles review, CI, discussion, and an audit trail into one gate before a change
reaches `main`. It makes every change reviewed, tested, discussed, and recorded.

Follow-up Question:

What four things does a PR bundle together?

## Intermediate

### 1. Difference between CI and code review.

Question:

What is the difference between CI and code review?

中文解析:

CI 是机器校验规则：构建、测试、lint、覆盖率。Code review 是人校验意图：这个改动是不是该做的正确的事。两者都需要。

Standard Answer:

CI is a machine validating rules — build, tests, lint, coverage. Code review is a human
validating intent — whether the change is the right thing to do. You need both.

Follow-up Question:

Does passing CI mean the change is correct?

Production Case:

CI is green, but a reviewer spots that an endpoint returns the wrong status code for
unauthorized users — an intent problem no test covered.

### 2. Why is Branch Protection important?

Question:

Why is Branch Protection important?

中文解析:

分支保护强制执行门禁，让必需的检查和 review 无法被跳过。它把安全路径变成唯一路径，即使在压力下也是如此。

Standard Answer:

Branch Protection enforces the gate so required checks and reviews cannot be skipped. It makes
the safe path the only path, even under pressure.

Follow-up Question:

What conditions can Branch Protection require before merge?

## Senior

### 1. What is a stale review?

Question:

What is a stale review?

中文解析:

stale review 是指批准之后代码又发生了变化，导致该批准不再适用。批准针对的是某个特定状态，状态变了就需要重新 review。

Standard Answer:

A stale review is an approval that no longer applies because the code changed after it was
given. The approval was about an earlier state, so re-review is needed.

Interview Review:

Strong answers frame an approval as a statement about a specific state.

Production Case:

A reviewer approves a small fix; a risky refactor is pushed afterward, so the stale approval is
dismissed and the new code is re-reviewed.

### 2. Why preserve review discussions?

Question:

Why preserve review discussions?

中文解析:

讨论记录了改动的"为什么"——备选方案、权衡和决策，成为持久的工程知识库，让未来的工程师不必重新争论已解决的问题。

Standard Answer:

Because the discussion records why a change was made — alternatives, trade-offs, and decisions.
It becomes a durable engineering knowledge base so future engineers do not re-litigate solved
problems.

Interview Review:

Good answers separate WHAT (code), short WHY (commit message), and full WHY (PR discussion).

Production Case:

Months later, a PR thread explains that a retry count matches a provider's rate limit,
preventing a "cleanup" that would reintroduce a bug.

### 3. Explain the full GitHub workflow mental model.

Question:

Walk through the GitHub collaboration workflow and why each step exists.

中文解析:

开发者在 feature 分支提交并推送，开 Pull Request；PR 上 CI 校验规则、人审查意图；分支保护强制门禁；通过后合入稳定的 main；讨论沉淀为工程知识库。

Standard Answer:

A developer commits on a feature branch and pushes it, then opens a Pull Request. The PR runs
CI to validate rules and a human review to validate intent. Branch Protection enforces the
gate, so only reviewed, tested changes reach a stable `main`, and the discussion becomes a
lasting engineering knowledge base.

Interview Review:

Senior answers tie every step to protecting shared state and preserving the why.

Production Case:

A prompt-v2 PR runs an eval in CI, a human confirms quality improved, protection blocks merge
until approval, and the thread records the regression it fixed.

---

# Day18 Merge Strategy & Code Review Questions

These questions come from the Day18 Merge Strategy & Code Review lesson. They focus on why
merge strategies and review practices exist.

## Beginner

### 1. Why is Git history important?

Question:

Why is Git history important?

中文解析:

历史是给人看的。未来的工程师通过历史理解决策、排查回归。可读的历史让这件事很快，嘈杂的历史则浪费时间。机器只需要父指针。

Standard Answer:

Because history is for humans: future engineers read it to understand decisions and debug
regressions. A readable history makes that fast; a noisy one wastes time. The machine only needs
the parent pointers.

Follow-up Question:

Who is the readable part of history actually for?

### 2. Development history vs product history.

Question:

What is the difference between development history and product history?

中文解析:

开发历史是功能分支上真实、嘈杂的过程（wip、fix）。产品历史是 main 上干净、有意义的记录（"新增 /agent 接口"）。分支是工作间，main 是展厅。

Standard Answer:

Development history is the real, noisy process on a feature branch (wip, fix). Product history is
the clean, meaningful record on `main` ("Add /agent endpoint"). The branch is the workshop; main
is the showroom.

Follow-up Question:

Which merge strategy turns development history into product history?

## Intermediate

### 1. Why does Git support multiple merge strategies?

Question:

Why does Git support multiple merge strategies?

中文解析:

因为不同分支需要不同的历史形状：有的要保留每个提交，有的要把噪声压成一个产品提交，有的要保持线性。策略是关于人读到什么样的历史。

Standard Answer:

Because different branches need different history shapes. Some changes should preserve every
commit, some should collapse noise into one product commit, and some should stay linear. The
strategy is a choice about what humans read in the history.

Follow-up Question:

Which strategy is most common for a noisy feature branch?

### 2. Merge commit vs squash merge.

Question:

What is the difference between a merge commit and a squash merge?

中文解析:

merge commit 保留完整开发历史并加一个有两个父的合并点。squash 把多个提交压成一个有意义的产品提交，让 main 保持干净。

Standard Answer:

A merge commit preserves the full development history and adds a join with two parents. A squash
merge compresses many commits into a single meaningful product commit, keeping `main` clean.

Follow-up Question:

When would you prefer to keep all the commits?

## Senior

### 1. When would you use a rebase merge?

Question:

When would you use a rebase merge?

中文解析:

当每个提交都有意义、且你想要没有合并提交的线性历史时。rebase 把提交重放到目标之上，会重写提交身份，所以用于整合分支，而不是已发布的共享历史。

Standard Answer:

When each commit is meaningful and you want a linear history with no merge commit. Rebase replays
the commits on top of the target, so it rewrites commit identity and is used for integrating a
branch, not for shared published history.

Interview Review:

Strong answers mention that rebase rewrites commit identity.

Production Case:

A few clean commits for a feature rebase onto main for a tidy linear log.

### 2. What do senior reviewers focus on?

Question:

What do senior reviewers focus on?

中文解析:

架构、性能、安全、可维护性——机器无法判断的风险。格式和风格交给 linter。

Standard Answer:

Architecture, performance, security, and maintainability — the risks machines cannot judge.
Formatting and style are left to linters.

Interview Review:

Good answers separate machine concerns (formatting) from human concerns (risk and design).

Production Case:

A reviewer catches a blocking DB call inside an async endpoint — a performance bug CI missed.

### 3. Explain "review the code, not the coder."

Question:

Explain "review the code, not the coder."

中文解析:

好的评审针对代码，具体、友善、可执行，并给出方向；避免人身批评，这样评审保持高效，同时改进代码、开发者和团队。

Standard Answer:

Good review comments target the code, are specific and constructive, and propose a direction.
They avoid personal criticism, so the review stays productive and improves the code, the
developer, and the team.

Interview Review:

Strong answers connect this to the three goals: improve the code, the developer, and the team.

Production Case:

Rewriting "this is wrong" into "this returns 200 on an auth failure; should it be 401?" keeps the
discussion specific and useful.

---

# Day19 GitHub Project Management Questions

These questions come from the Day19 GitHub Project Management lesson. They focus on why teams
manage work with Issues, Labels, Milestones, and Projects.

## Beginner

### 1. Why do teams need Issues?

Question:

Why do teams need Issues?

中文解析:

因为团队要管理"工作"，不只是代码。Issue 是可追踪、可归属、可排优先级的工作项。没被追踪的工作活在记忆和聊天里，会丢失——工作没被追踪，就等于不存在。

Standard Answer:

Because teams must manage work, not only code. An Issue is a trackable, ownable, prioritizable
work item. Untracked work lives in memory and chat and gets lost — if work isn't tracked, it
doesn't exist.

Follow-up Question:

Is an Issue only for bugs?

### 2. Why use Labels?

Question:

Why use Labels?

中文解析:

Label 是工作上的结构化元数据，支持检索（过滤）、流程（如 needs-review 状态）和自动化（路由或触发），类似数据库索引、RAG 元数据过滤和 Kubernetes labels。

Standard Answer:

A Label is structured metadata on work. It enables retrieval (filtering), workflow (states like
needs-review), and automation (routing or triggers) — similar to database indexes, RAG metadata
filtering, and Kubernetes labels.

Follow-up Question:

Which of retrieval, workflow, and automation does `priority-high` serve?

## Intermediate

### 1. Difference between an Issue and a Milestone.

Question:

What is the difference between an Issue and a Milestone?

中文解析:

Issue 管理一个任务；Milestone 把多个 Issue 组成一个产品交付目标，并显示交付进度。

Standard Answer:

An Issue manages one task. A Milestone groups many Issues into one product delivery goal and
shows progress toward shipping it.

Follow-up Question:

What does a Milestone show that an individual Issue cannot?

### 2. What is GitHub Projects?

Question:

What is GitHub Projects?

中文解析:

GitHub Projects 管理的是工作流，不是任务。它是一个看板，显示每项工作在流水线中的位置（Backlog、In Progress、Review、Done），暴露流动和瓶颈。

Standard Answer:

GitHub Projects manages workflow, not tasks. It is a board that shows where each piece of work
is in the pipeline (Backlog, In Progress, Review, Done), exposing flow and bottlenecks.

Follow-up Question:

What question does a Project answer that an Issue does not?

## Senior

### 1. Difference between Issue management and Project management.

Question:

What is the difference between Issue management and Project management?

中文解析:

Issue 管理回答"存在哪些工作"——工作单元。Project 管理回答"工作现在在哪"——每个单元在流水线中的阶段。

Standard Answer:

Issue management answers "what work exists?" — the units of work. Project management answers
"where is the work now?" — the stage of each unit in the pipeline.

Interview Review:

Strong answers frame Issue as the unit and Project as the flow.

Production Case:

Standup becomes "what is stuck in Review?" because the board shows every Issue's column.

### 2. Explain ownership vs blame.

Question:

Explain ownership vs blame.

中文解析:

Ownership 是指某人负责把一项工作推进到完成；blame 是出问题后追究过错。分配 ownership 让工作前进；把它当成 blame 会让人不敢承担。

Standard Answer:

Ownership means someone is responsible for driving a piece of work to done. Blame is about fault
after something breaks. Assigning ownership makes work move; treating it as blame discourages
people from taking it.

Interview Review:

Good answers connect ownership to healthy team culture.

Production Case:

An owner drives the rate-limit Issue to done; the team treats a resulting incident as a system
fix, not a personal fault.

### 3. Explain the full Idea-to-Release workflow.

Question:

Trace the workflow from an idea to a release.

中文解析:

Idea → Issue（追踪工作）→ Project（放上看板）→ Feature Branch → Commit → Pull Request → CI → Review → Merge → Deploy → Release，把 Day15-Day19 连成一条流水线。

Standard Answer:

An idea becomes an Issue, is placed on the Project board, becomes a feature branch, is committed,
opened as a Pull Request, validated by CI, reviewed, merged, deployed, and released. Work
management and code management are one continuous pipeline.

Interview Review:

Senior answers show that work and code management are one pipeline, not separate tools.

Production Case:

"Add /agent endpoint" flows from an MVP Issue through the board, branch, PR, review, and merge to
deploy, then the Issue closes.
