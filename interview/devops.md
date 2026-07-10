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

CI 关注自动集成和验证每个改动（构建、测试）。CD 关注把验证过的改动可重复、可靠地交付到各环境，取代手动部署。

Standard Answer:

CI is about integrating and validating changes automatically — building and testing every
change. CD is about delivering those validated changes to environments repeatably and reliably,
replacing manual deployment.

Follow-up Question:

Which four properties does CD provide?

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
