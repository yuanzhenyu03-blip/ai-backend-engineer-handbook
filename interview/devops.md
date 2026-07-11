# DevOps Interview

## Purpose

Interview questions and model answers for DevOps: CI/CD, pipelines, quality gates, and delivery.

---

# Day20 CI/CD Foundations Questions

These questions come from the Day20 CI/CD Foundations lesson. They focus on why each part of the
delivery process exists.

## Beginner

### 1. Why CI?

Question:

Why do teams use Continuous Integration?

中文解析:

CI 建立一个可信、可重复的质量流程。每次改动都自动跑同样的检查，全团队可见，让质量来自流程而不是个人承诺。

Standard Answer:

CI establishes a trusted, repeatable quality process. Every change runs the same automated
checks, visible to the whole team, so quality comes from process rather than personal promises.

Follow-up Question:

Why is "I tested locally" not enough?

### 2. Why a pipeline?

Question:

Why structure CI as a pipeline?

中文解析:

流水线是有序阶段的标准工作流，先跑便宜的检查，一旦失败就快速停止并给出快速反馈，节省时间和算力。

Standard Answer:

A pipeline is a standard workflow of ordered stages with dependencies. It runs cheap checks
first, fails fast at the first problem, and gives fast feedback, saving time and compute.

Follow-up Question:

What happens to later stages when an early stage fails?

## Intermediate

### 1. What is a quality gate?

Question:

What is a quality gate?

中文解析:

质量门是风险控制：只有通过必需检查的改动才能继续前进。它在边界拦住坏改动，保护 main、生产、团队和用户。

Standard Answer:

A quality gate is risk control: only changes that pass the required checks are allowed to move
forward. It protects `main`, production, the team, and users by stopping bad changes at the
boundary.

Follow-up Question:

Why is blocking better than only reporting results?

### 2. CI vs CD.

Question:

What is the difference between CI and CD?

中文解析:

CI 关注自动集成和验证每个改动（构建、测试）。CD 有两层：Continuous Delivery 让每次改动都产出可随时发布的候选版本（生产发布可能仍需人工批准）；Continuous Deployment 在所有质量门通过后自动部署到生产。二者不是同一个概念。

Standard Answer:

CI integrates and validates every change automatically (build and test). CD has two levels:
Continuous Delivery keeps every change as an always-ready, production-ready release candidate
(the production release may still need manual approval), while Continuous Deployment
automatically ships to production once all quality gates pass. They are not identical.

Follow-up Question:

What is the difference between Continuous Delivery and Continuous Deployment?

## Senior

### 1. Why Workflow as Code?

Question:

Why define the CI/CD workflow as code?

中文解析:

因为以代码定义的流水线具有一致性、版本控制、可评审（走 PR）和可审计。UI 配置的工作流不可见、不可复现。

Standard Answer:

Because a pipeline defined as code is consistent, version-controlled, reviewable through Pull
Requests, and auditable. UI-configured workflows are invisible and unrepeatable.

Interview Review:

Strong answers tie Workflow as Code to the same benefits as versioning application code.

Production Case:

A change to the CI pipeline is a PR reviewed like any code, so a risky edit is caught before it
ships.

### 2. Explain Everything as Code.

Question:

What does Everything as Code mean?

中文解析:

Everything as Code 指代码、测试、工作流、基础设施、配置甚至提示词都以可版本化、可评审的文件定义，让整个系统可复现、可审计。

Standard Answer:

Everything as Code means code, tests, workflows, infrastructure, configuration, and even prompts
are defined as versioned, reviewable files, making the whole system reproducible and auditable.

Interview Review:

Good answers extend the idea to infrastructure and prompts, not just app code.

Production Case:

Dockerfiles (infra as code) and prompt files (prompts as code) flow through the same reviewed,
versioned pipeline.

### 3. Explain the full delivery lifecycle.

Question:

Trace the software delivery lifecycle from idea to production.

中文解析:

Idea → Issue → Project → Branch → Commit → Pull Request → CI → Pipeline → Quality Gate → Merge → CD → Production，把 Day15-Day20 连成一条交付生命周期。

Standard Answer:

An idea becomes an Issue on the Project board, then a branch and commits, then a Pull Request
validated by CI through a pipeline and a quality gate, then a merge, then CD delivers it to
production. Work management, code management, quality automation, and delivery are one lifecycle.

Interview Review:

Senior answers show every earlier lesson is a stage in one pipeline.

Production Case:

"Add /agent endpoint" flows from an Issue through CI and the quality gate to an automated CD
deploy, with no manual step.

---

# Day21 GitHub Actions Fundamentals Questions

These questions come from the Day21 GitHub Actions Fundamentals lesson. They focus on the
execution model, runner choice, job design, and the quality gate.

## Beginner

### 1. What is a GitHub Actions workflow?

Question:

What is a GitHub Actions workflow?

中文解析:

工作流是团队的工程流程，以代码形式定义在 `.github/workflows/` 中。它由触发器启动，在 runner 上执行 job，每个 job 顺序执行 step。因为是代码，所以可版本化、可评审、可审计。

Standard Answer:

A workflow is the team's engineering process defined as code in `.github/workflows/`. It runs on
triggers, executes jobs on runners, and each job runs ordered steps. Because it is code, it is
versioned, reviewable, and auditable.

Follow-up Question:

Why does the workflow live in a fixed directory?

### 2. What is the difference between `on` and `runs-on`?

Question:

What is the difference between `on` and `runs-on`?

中文解析:

`on` 定义触发器（何时运行），不是操作系统。`runs-on` 选择 job 的 runner/操作系统（在哪运行）。

Standard Answer:

`on` defines the trigger — when the workflow runs. It is not the operating system. `runs-on`
selects the runner/OS for a job — where it runs.

Follow-up Question:

Which one is event-driven?

## Intermediate

### 1. GitHub-hosted vs self-hosted runner.

Question:

What is the difference between a GitHub-hosted and a self-hosted runner?

中文解析:

两者都执行 job，区别是控制权。Hosted 通用、无状态、标准化、维护成本低，但网络和硬件受限。Self-hosted 提供内网访问、GPU/自定义硬件和数据控制，但需要自己运维。

Standard Answer:

Both execute jobs; the difference is control. Hosted runners are general, stateless,
standardized, and low-maintenance but limited in network and hardware. Self-hosted runners give
internal network access, custom hardware or GPU, and data control, at the cost of operational
responsibility. Choose self-hosted for internal access, GPU, or data control; otherwise hosted.

Follow-up Question:

Is speed the main reason to use self-hosted?

Production Case:

A GPU model evaluation against an internal model server runs on a self-hosted GPU runner; general
lint/test runs on a hosted runner.

### 2. What is the difference between `run`, `uses`, and `with`?

Question:

What is the difference between `run`, `uses`, and `with`?

中文解析:

`run` 在当前 runner 上执行 shell 命令；`uses` 调用可复用的 GitHub Action；`with` 给 Action 传参数（相当于函数参数）。

Standard Answer:

`run` executes a shell command on the current runner; `uses` calls a reusable GitHub Action; and
`with` passes parameters to that action, like function arguments.

Follow-up Question:

Why prefer a maintained action over a raw shell command for checkout or language setup?

## Senior

### 1. How would you design CI jobs for an AI backend with GPU evaluation?

Question:

How would you design CI jobs for an AI backend that needs general checks and GPU evaluation?

中文解析:

按执行环境和依赖拆分。hosted 的 quality job 跑 lint/test；self-hosted GPU 的 gpu-eval job 跑模型评估，二者并行。build job 依赖 quality，保证不会用未通过质量门的代码构建镜像。敏感评估留在自托管基础设施上，secrets 安全引用，昂贵评估可用 schedule 控成本。

Standard Answer:

I split by execution environment and dependency. A hosted `quality` job runs lint and tests; a
self-hosted GPU `gpu-eval` job runs model evaluation; they run in parallel. A `build` job depends
on `quality`, so no image is built from code that failed the gate. Sensitive evaluation stays on
self-hosted infrastructure with secrets referenced safely, and expensive evaluation can move to a
schedule to control cost.

Interview Review:

Strong answers divide jobs by runner lifecycle and dependency, not business labels, and make the
build depend on the gate.

Production Case:

Prompt-regression results gate a model or prompt release.

### 2. Why must the build wait for the quality gate?

Question:

If Ruff (lint) fails, should the Docker build still run?

中文解析:

不应该。当 Ruff 是质量门的一部分时，lint 失败应阻止构建。构建只是产出制品的阶段，不能替代质量验证；用未通过检查的代码构建镜像会浪费算力并可能发布已知有缺陷的制品。

Standard Answer:

No. When Ruff is part of the quality gate, a lint failure must block the build. Build is an
artifact stage, not a substitute for quality validation; building from code that failed checks
wastes compute and can ship a known-bad artifact.

Interview Review:

Look for "validate first, build second" and an explicit `needs:` dependency.

Production Case:

A PR whose `ruff check .` fails stops before Docker build; no image is produced for broken code.

### Common Weak vs Strong Answer

Weak: "GitHub Actions runs my tests automatically when I push." (misses workflow-as-code,
triggers/cost, runner choice, job isolation, and the quality gate)

Strong: "GitHub Actions implements CI/CD as code: triggers make it event-driven, runners execute
jobs, jobs isolate environments and failures, steps use reusable actions or shell commands, and a
quality gate blocks the build until required checks pass — all versioned and reviewable."
