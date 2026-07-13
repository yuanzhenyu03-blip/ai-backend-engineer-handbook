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

### 3. Secrets vs environment variables.

Question:

What is the difference between a secret and an environment variable in GitHub Actions?

中文解析:

环境变量是明文配置（如 LOG_LEVEL、APP_ENV），会出现在日志里；secret 是加密存储、日志中被遮蔽的敏感值（API key、token、数据库连接串）。env 有作用域：workflow/job/step，越窄越优先。用 `${{ secrets.NAME }}` 注入，绝不硬编码或打印。

Standard Answer:

An environment variable is plain, visible configuration (LOG_LEVEL, APP_ENV) and can appear in
logs. A secret is an encrypted-at-rest, log-masked sensitive value (API keys, tokens, DB URLs).
Env vars have scope — workflow, job, or step, with narrower overriding broader. Inject secrets
with `${{ secrets.NAME }}`, never hardcode or echo them.

Follow-up Question:

Do fork pull requests from untrusted contributors receive repository secrets by default?

Production Case:

A FastAPI CI sets APP_ENV as an env var and injects OPENAI_API_KEY and DATABASE_URL from secrets
only in the step that needs them.

### 4. Is a self-hosted runner more secure?

Question:

Self-hosted runners give more control. Does that make them more secure?

中文解析:

不一定。更多控制不等于更安全。自托管 runner 的风险包括：状态在 job 间残留、fork PR 会在你的硬件上运行攻击者代码、长期凭证被窃取、主机被攻陷、以及它位于内网导致的内部爆炸半径。要靠 ephemeral/隔离 runner、不给 fork PR secrets、最小权限、网络隔离来缓解。

Standard Answer:

Not automatically. More control is not the same as more security. Self-hosted risks include
persistent state between jobs, untrusted fork PRs running attacker-controlled code on your
hardware, credential leakage, host compromise, and a large internal blast radius because the
runner sits inside your network. You mitigate with ephemeral/isolated runners, no secrets for
fork PRs, least privilege, and network segmentation.

Interview Review:

Strong answers explicitly separate "control" from "safety" and name the fork-PR and blast-radius
risks.

Production Case:

A GPU self-hosted runner reaching an internal model server must be isolated so a malicious job
cannot pivot into the internal network.

### 5. How do you pin third-party actions safely?

Question:

Is `actions/checkout@v4` an immutable pin?

中文解析:

不是。`@v4` 是可移动的主版本标签，维护者可以把它指向新的提交，方便更新但不保证不可变。要更强的供应链保证，就固定到完整的 40 位 commit SHA，冻结确切代码。高安全流水线会用 SHA 固定第三方 action，并避免盲目使用未知 Marketplace action。

Standard Answer:

No. `@v4` is a movable major-version tag — maintainers can repoint it to new commits, which gives
easy updates but not immutability. For a stronger supply-chain guarantee, pin to a full 40-character
commit SHA, which freezes the exact code. High-security pipelines pin third-party actions to a SHA
and avoid blindly using unknown Marketplace actions.

Interview Review:

Look for the trade-off: major tag = easy updates; commit SHA = immutability.

Production Case:

A security-sensitive AI backend pipeline pins every third-party action to a commit SHA.

### Common Weak vs Strong Answer

Weak: "GitHub Actions runs my tests automatically when I push." (misses workflow-as-code,
triggers/cost, runner choice, job isolation, and the quality gate)

Strong: "GitHub Actions implements CI/CD as code: triggers make it event-driven, runners execute
jobs, jobs isolate environments and failures, steps use reusable actions or shell commands, and a
quality gate blocks the build until required checks pass — all versioned and reviewable."

---

# Day22 GitHub Actions Advanced Questions

These questions come from the Day22 GitHub Actions Advanced lesson: matrix, cache vs artifact,
composite vs reusable, conditions, and reliable deployment.

## Beginner

### 1. What does a matrix build do?

Question:

What does a matrix build do, and does it reduce the number of jobs?

中文解析:

矩阵把一个 job 定义按一组变量展开，生成每个组合一个独立 job（隔离环境，不共享文件系统/依赖）。它通常不减少执行次数，而是消除重复 YAML、防止配置漂移。

Standard Answer:

A matrix expands one job definition across a set of variables (Python versions, OSes), generating
one isolated job per combination. It normally does not reduce the number of executions; it removes
duplicated YAML and prevents configuration drift.

Follow-up Question:

What is the difference between wall-clock time and runner-minutes?

## Intermediate

### 1. Cache vs artifact.

Question:

What is the difference between a cache and an artifact?

中文解析:

Cache 是可重新生成的加速数据（依赖下载、浏览器二进制），用 OS + 依赖哈希做 key；cache miss 时工作流仍必须正确，只是更慢。Artifact 是本次运行的正式产物（覆盖率、报告、包），在 job 间传递并留存审计。绝不能把 cache 当作正式结果的存储。

Standard Answer:

A cache is re-creatable acceleration data (dependency downloads, browser binaries) keyed by OS and a
dependency hash; a workflow must still be correct on a cache miss, only slower. An artifact is a
formal output of this run (coverage, reports, packages) transferred between jobs and retained for
audit. Never use a cache as the official store for a result.

Follow-up Question:

Why must a workflow still succeed on a cache miss?

### 2. Composite action vs reusable workflow.

Question:

When do you use a composite action versus a reusable workflow?

中文解析:

Composite Action 复用的是「步骤」（装依赖、跑 Ruff/pytest、Docker 登录推送）；Reusable Workflow 复用的是「job/整条工作流」（lint→test→build、矩阵、安全扫描、部署门）。若复用单元需要自己的 jobs/runs-on/needs，就用 Reusable Workflow。

Standard Answer:

A composite action reuses steps (install deps, run Ruff/pytest, a Docker login/push group). A
reusable workflow reuses whole jobs or a pipeline (lint→test→build, matrix, security scan, deploy
gates). If the reusable unit needs its own `jobs`, `runs-on`, or `needs`, use a reusable workflow.

Follow-up Question:

What organization-level problem does a reusable workflow prevent?

### 3. `needs` vs `if` vs `continue-on-error`.

Question:

Explain `needs`, `if`, and `continue-on-error`.

中文解析:

三者是不同机制：`needs` 定义依赖顺序（谁先完成，并可访问依赖结果）；`if` 决定是否执行（分支/标签/事件/输入/结果）；`continue-on-error` 让步骤/job 执行并记录失败但不阻断流程（不等于跳过）。「无论成败都通知」用 `needs: [test, build]` + `if: always()`。

Standard Answer:

They are three separate mechanisms. `needs` defines dependency and ordering (who finishes first, and
gives access to dependency results). `if` decides whether to run based on context — branch, tag,
event, input, or result. `continue-on-error` runs the step/job and records failure without blocking
the flow (not the same as skipped). To notify regardless of outcome, use `needs: [test, build]` with
`if: always()`.

Follow-up Question:

Why is `needs` alone not enough for a notify-on-failure job?

## Senior

### 1. How do you make a Docker deployment reliable?

Question:

How do you make a Docker deployment reliable in GitHub Actions?

中文解析:

一次构建、多次部署：构建一次镜像、推到镜像仓库、部署不可变 digest，绝不在部署阶段重建或部署可变的 `:latest`，保证「测的就是部署的」。部署放在 production Environment 后面，要求有风险资格的审批者和仅限生产的 secrets，并用 concurrency group + `cancel-in-progress: false` 串行化，避免部署重叠。再加冒烟测试、监控和回滚。

Standard Answer:

Build the image once, push it to a container registry, and deploy the immutable digest — never rebuild
in deploy or deploy a mutable `:latest`, so what was tested is what ships. Gate the deploy behind a
production Environment with required, risk-qualified reviewers and production-only Secrets, and
serialize with a concurrency group using `cancel-in-progress: false` so deployments never overlap. Add
smoke tests, monitoring, and a rollback path.

Interview Review:

Strong answers say "build once, deploy many," name the immutable digest, and separate approval from a
fixed job title (accountable, risk-qualified owner).

Production Case:

An AI backend deploys the exact digest its evaluation approved; production Secrets never reach general
CI jobs. A `verify-image` job pulls and runs that exact digest and smoke-tests it before deploy, so
source tests are backed by runtime verification of the built artifact.

### 2. When do you set `fail-fast: false`, and why is `concurrency` not a boolean?

Question:

When is `fail-fast: false` correct, and what is the shape of `concurrency`?

中文解析:

当剩余组合仍有独立的诊断/兼容/发布价值时用 `fail-fast: false`（如公开 SDK 支持所有组合）；只需早期信号且成本高时用 `true`。`concurrency` 是配置块不是布尔：`group` 决定哪些部署共享一把锁，`cancel-in-progress` 才是布尔，决定是否打断进行中的部署（生产用 false 排队而非打断）。

Standard Answer:

Use `fail-fast: false` when the remaining combinations still carry independent diagnostic,
compatibility, or release value (a public SDK supporting all combinations); use `true` when one early
signal is enough and runs are costly. `concurrency` is a configuration block, not a boolean: `group`
decides which deployments share a lock, and `cancel-in-progress` is the boolean deciding whether a new
run interrupts the active one — production uses `false` to queue rather than interrupt.

Interview Review:

Look for the decision criterion (independent value) and the group/cancel-in-progress split.

Production Case:

Cancelling an in-progress production deploy risks half-applied migrations and a mixed-version fleet.

### Common Weak vs Strong Answer (Day22)

Weak: "Matrix saves resources, cache and artifacts both store files, and I run `deploy.sh` after
tests." (misses matrix isolation, cache-vs-artifact, immutable promotion, approval, concurrency)

Strong: "Advanced Actions scale with matrices, accelerate with caches, transfer official outputs as
artifacts, reuse steps (composite) and pipelines (reusable workflow), control flow with
`needs`/`if`/`continue-on-error`, and deploy one immutable, approved digest under a serialized
production Environment."

---

# Day23 Docker Fundamentals Questions

These questions come from the Day23 Docker Fundamentals lesson: container model, image vs
container, build vs run, volumes, and networking.

## Beginner

### 1. What is a Docker container?

Question:

What is a Docker container?

中文解析:

容器是通过宿主机内核运行的隔离进程。它有隔离的文件系统、进程和网络视图，可用 cgroups 限制资源。与虚拟机不同，它不启动自己的 guest 内核。

Standard Answer:

A Docker container is an isolated process that runs through the host operating system kernel. It
has isolated filesystem, process, and network views, and it can be constrained with cgroups.
Unlike a typical virtual machine, it does not boot its own guest kernel.

Follow-up Question:

What isolates what a container can see, and what limits how much it can consume?

### 2. What is the difference between an image and a container?

Question:

What is the difference between an image and a container?

中文解析:

镜像是不可变、可分发的模板，由只读层组成；容器是镜像的一个运行实例，有自己的可写层和运行时配置。重建镜像不会更新已经在运行的容器。

Standard Answer:

An image is an immutable, distributable template made of read-only layers. A container is one
runtime instance of that image with its own writable layer and runtime configuration. Rebuilding
an image does not update containers that are already running.

Follow-up Question:

How do you roll out a code change if you must not edit the running container?

## Intermediate

### 1. `docker build` vs `docker run`.

Question:

What is the difference between `docker build` and `docker run`?

中文解析:

docker build 执行 Dockerfile 指令、产出不可变镜像；docker run 从镜像创建容器、应用运行时隔离和配置，并启动镜像的默认进程（除非被覆盖）。构建成功不代表服务已经在运行。

Standard Answer:

`docker build` executes Dockerfile instructions and produces an immutable image. `docker run`
creates a container from that image, applies runtime isolation and configuration, and starts the
image's default process unless it is overridden. A successful build does not mean the service is
running.

Follow-up Question:

Is the published host port set at build time or run time?

### 2. Image layers, cache, and Dockerfile order.

Question:

How does build cache ordering affect a Dockerfile?

中文解析:

构建缓存从第一条改变的指令开始失效，所以把稳定、低频的步骤放前面、把频繁变化的应用代码放后面：先 COPY requirements、RUN 安装依赖，最后 COPY 代码，这样依赖层能命中缓存。

Standard Answer:

The build cache is invalidated from the first changed instruction onward, so put stable,
low-frequency steps first and frequently changing app code last: copy the dependency manifest,
install dependencies, then copy the application code. That keeps the dependency-install layer
cached when only the code changes.

Follow-up Question:

What is the difference between an image layer and the container writable layer?

## Senior

### 1. Why avoid modifying a running production container?

Question:

Why should we avoid modifying a running Docker container directly in production?

中文解析:

因为改动只作用于该容器的可写层，而不是原镜像；不可复现、不可审计、难以回滚。正确做法是更新版本化输入、构建并验证新的不可变镜像、启动新容器、健康检查、切流量，然后移除旧容器。

Standard Answer:

Because the changes affect only that container's writable layer, not the original image. They are
not reproducible or auditable and make rollback difficult. The correct approach is to update
version-controlled inputs, build and verify a new immutable image, start a new container, run
health checks, switch traffic, and then remove the old container.

Interview Review:

Strong answers name reproducibility, auditability, and rollback, and give the replace-not-mutate
flow.

Production Case:

A hotfix typed into a live container disappears on the next deploy and cannot be rolled back.

### 2. Why does `localhost` not reach another container, and where does state live?

Question:

Why does `localhost` not reach another container, and where should persistent data live?

中文解析:

每个容器有自己的网络命名空间，localhost 指向当前容器，所以要在共享网络上用服务 DNS 名（如 postgres:5432）而不是容器 IP。持久化数据（数据库文件、上传、向量索引）应放在卷或外部存储，而不是随容器消失的可写层。

Standard Answer:

Each container has its own network namespace, so `localhost` refers to the current container. On a
shared Docker network, communicate through stable service DNS names (for example `postgres:5432`)
rather than container IPs, which change on recreation. Persistent data — database files, uploads,
vector indexes — must live in a volume or external storage, not the ephemeral writable layer.

Interview Review:

Look for the compute-vs-data lifecycle separation and least-access network membership.

Production Case:

A RAG backend keeps FastAPI stateless and persists PostgreSQL and vector data in volumes so app
containers stay replaceable.

### Common Weak vs Strong Answer (Day23)

Weak: "A container is a lightweight VM, an image and a container are basically the same, and I edit
the container to fix production." (misses the process/kernel model, image immutability, and
immutable replacement)

Strong: "A container is an isolated process sharing the host kernel; an image is the immutable
artifact and a container is a replaceable instance; durable state lives in volumes; services talk
over a network by DNS name; and I roll out changes by rebuilding and replacing, never by editing a
running container."
