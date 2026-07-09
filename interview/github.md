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
