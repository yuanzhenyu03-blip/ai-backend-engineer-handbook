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

---

# Day24 Docker Compose Questions

These questions come from the Day24 Docker Compose lesson: multi-service declaration, readiness,
networking, volumes, secrets, and the production boundary.

## Beginner

### 1. What problem does Docker Compose solve?

Question:

What problem does Docker Compose solve, and how is it different from running multiple `docker run`
commands manually?

中文解析:

手动多条 docker run 会漂移：漏参数、端口/网络/卷/环境变量不一致、启动假设藏在人脑里、新人上手慢。Compose 用一个版本化声明描述服务、网络、卷和运行配置，人人可复现同一环境。它是"定义并运行多容器应用的工具"，不是"一个多容器应用"。

Student's actual attempt (preserved):

> "the docker compose is a multi-container application what incloud services, networks, volumes,
> and it's a good for team collaboration. it is a reproducibility declarative configuration"

Standard Answer:

Docker Compose is a tool for defining and running multi-container applications. A Compose file
declaratively describes the services, networks, volumes, and runtime configuration. Compared with
multiple manual `docker run` commands it reduces missing parameters and configuration drift, and
because it is version-controlled, every team member reproduces the same environment.

Follow-up Question:

Why is "Compose is a multi-container application" imprecise?

## Intermediate

### 1. `depends_on` vs healthcheck vs application retry.

Question:

What is the difference between `depends_on`, a healthcheck, and application-level retry?

中文解析:

`depends_on`（短语法）只等依赖容器启动，不等就绪；healthcheck 用探针判断服务是否真的可用（不做修复/重启）；应用重试用有界退避处理启动中和运行时的瞬时故障。三者都要，因为"启动≠就绪"，健康的依赖之后仍可能失败。

Student's actual attempt (preserved):

> "the depends_on is startup order, the health check is a tool for check service readiness, and
> application-level retry is a retry with backoff when the application meet runtime failure,
> transient failure"

Standard Answer:

`depends_on` controls startup order; with the short syntax it only waits for the dependency
container to start, not to become ready. A healthcheck tests whether a service can actually provide
its capability (it does not repair or restart it). Application retry handles transient failures
during and after startup, usually with bounded exponential backoff. Initial orchestration cannot
replace runtime resilience.

Follow-up Question:

Can a running container be unhealthy?

### 2. Rebuild vs recreate, and service vs instance.

Question:

When do you rebuild vs recreate, and are API and Worker (same image) two services or two instances?

中文解析:

镜像内容变了才 rebuild+recreate；运行时配置变了只 recreate；挂载源码变了 reload。API 和 Worker 是两个服务/角色（同一镜像不同命令）；同一个服务的副本才是多个实例。

Standard Answer:

Image content change -> rebuild + recreate; runtime configuration change -> recreate; mounted
source change -> reload. API and Worker are two services/roles built from one image with different
commands; multiple replicas of one service are the multiple instances.

Follow-up Question:

How can one image back two services?

## Senior

### 1. Compose in production vs Kubernetes.

Question:

When would you use Docker Compose in production, and when would you choose Kubernetes or a managed
platform?

中文解析:

当业务接受单主机为单一故障域、流量可控、可接受有限停机时，可用 Compose 做小型单主机生产，但仍需备份+恢复测试、监控、TLS、密钥管理、资源限制和回滚流程。当需要多节点调度、自愈、自动扩缩、滚动更新和更高可用时选 Kubernetes/托管平台——它跨集群持续把实际状态收敛到期望状态，而 Compose 主要在一台主机上按命令协调服务。权衡是运维简单 vs 更强的自动化/弹性/伸缩。

Standard Answer:

I would use Compose for a small, single-host production system when the business accepts the host
as a single failure domain — it is operationally simple — but I would still add backups,
monitoring, TLS, secret management, resource limits, and a rollback process. I would choose
Kubernetes or a managed platform when the system needs multi-node scheduling, self-healing,
autoscaling, and rolling updates. Kubernetes continuously reconciles actual state to desired state
across a cluster, while Compose coordinates services on one host when commands run. The trade-off
is operational simplicity versus stronger automation, resilience, and scalability.

Interview Review:

Strong answers list the extra single-host controls and name what Compose does NOT provide
(multi-node scheduling, reconciliation, autoscaling, rollout governance).

Production Case:

A small internal knowledge base runs on Compose with backups and TLS; a public 99.99% AI API needs
a cluster.

### 2. Secrets, `.env`, and governed business data.

Question:

How do you handle configuration, secrets, and customer data in Compose?

中文解析:

普通配置（APP_ENV/LOG_LEVEL）放 environment/.env；密钥（密码、OPENAI_API_KEY、含密码的 DATABASE_URL）用 Compose secrets，挂载到 /run/secrets 且应用必须读取文件；`.env` 是明文插值源不是密钥管理器，要 gitignore。客户 prompt/病历是受治理的业务数据（存储、审计、加密、留存），不是部署密钥。按最小权限授予：只有 Worker 拿 OPENAI_API_KEY。

Standard Answer:

Ordinary configuration (APP_ENV, LOG_LEVEL) goes in `environment`/`.env`. Secrets (passwords,
`OPENAI_API_KEY`, a password-bearing `DATABASE_URL`) use Compose secrets, mounted at
`/run/secrets/<name>` where the application must read the file; `.env` is a plaintext interpolation
source, not a Secret Manager, and must be git-ignored. Customer prompts and medical records are
governed business data (storage, audit, encryption, retention), not deployment secrets. Grant
least privilege — only the Worker receives the OpenAI key.

Interview Review:

Look for classification by semantics/lifecycle (not size) and "mounting a secret alone does not
configure the app."

Production Case:

The API never receives the OpenAI key because it does not call the model provider.

### Common Weak vs Strong Answer (Day24)

Weak: "Compose starts my containers and `depends_on` makes them ready; `.env` keeps secrets safe."
(misses started≠ready, healthcheck vs retry, and that `.env` is plaintext)

Strong: "Compose is a version-controlled declaration of a multi-service system; `depends_on` orders
startup, a healthcheck proves readiness, and application retry handles transient failures; only the
API is exposed, services talk by DNS, durable state lives in a named volume, and secrets are scoped
files the app reads."

---

# Day25 Deployment Foundations Questions

These questions come from the Day25 Deployment Foundations lesson: reverse proxy, TLS, immutable
promotion, blue-green, drain, schema evolution, and DNS.

## Beginner

### 1. What does a reverse proxy do for a production API?

Question:

What does a reverse proxy do for a production API?

中文解析:

反向代理提供稳定的公共入口，让后端保持内部，可以终止 TLS，并把请求转发到正确的后端服务。客户端只和代理的域名/URL 打交道，所以后端可以替换而不改变客户端契约。后端端口不对公网暴露。

Student's actual attempt (preserved):

> "there are some problem is resolved by reverse proxy, for example, it offer a public entry for
> client, the interna backend only offer bussiness service. and the TLS is the more safer connect
> style than http, it's easy to swtich backend replacement"

Standard Answer:

A reverse proxy provides a stable public entry, keeps the backends internal, can terminate TLS, and
forwards requests to the right backend service. Because the client talks to the proxy's domain and
URL, the backend can be replaced without changing the client's contract.

Follow-up Question:

Does a reverse proxy automatically provide TLS?

## Intermediate

### 1. Walk through a zero-downtime API deployment.

Question:

Walk through a zero-downtime API deployment.

中文解析:

晋级已审批的镜像 digest，启动 Green 但不接生产流量，直接对它做 readiness + smoke 验证，`nginx -t` 校验配置后优雅切流量。在真实流量下观察 Green 并 drain Blue 的在途请求。错误率高就把流量切回 Blue 并安全 drain v2；健康就结束回滚窗口再移除 Blue。健康检查必要但不充分。

Standard Answer:

I promote the approved image digest, start Green without production traffic, verify it directly with
readiness and smoke checks, validate the Nginx config with `nginx -t`, then gracefully switch
traffic. I observe Green under real traffic while draining Blue's in-flight requests. If the error
rate is bad, I switch traffic back to Blue and drain v2 safely; if it is healthy, I end the rollback
window and remove Blue.

Interview Review:

Say "switch traffic back to Blue," not "rollback the old container"; stress health is necessary but
not sufficient.

Follow-up Question:

Why can a passing health check not prove the deployment succeeded?

### 2. Promote vs rebuild, tag vs digest.

Question:

On deploy, do you rebuild the image on production, and what is the difference between a tag and a
digest?

中文解析:

不在生产重建；晋级 CI 已构建/测试/扫描的同一个不可变 digest（Tested=Scanned=Deployed）。Tag 是可移动的人类可读引用，Digest 是不可变的制品身份。环境差异放进 Day24 的 service specification，而不是逐环境重建镜像。

Standard Answer:

I do not rebuild on production; I promote the same immutable digest that CI already built, tested,
and scanned (tested = scanned = deployed). A tag is a movable, human-readable reference; a digest is
the immutable artifact identity. Environment differences belong in the service specification, not in
a per-environment rebuild.

Follow-up Question:

Why does rebuilding per environment break the integrity chain?

## Senior

### 1. How do API, Worker, and PostgreSQL differ during a deployment?

Question:

How do API, Worker, and PostgreSQL differ during a deployment?

中文解析:

API 和 Worker 是可替换的计算版本：API 走 blue-green，Worker 先上向后兼容的消费者。PostgreSQL schema 是共享的持久契约，用 Expand-Migrate-Contract——加列、部署双兼容代码、回填、验证，只有在回滚窗口之后的后续版本才 Contract。全程在串行化生产锁 + 最小权限短期身份 + 有界超时 + 观察 + 可记录回滚下进行。

Standard Answer:

API and Worker are replaceable compute versions: I blue-green the API and roll out a
backward-compatible Worker consumer first. PostgreSQL schema is a shared durable contract, so I use
Expand-Migrate-Contract — add the new column, deploy code compatible with both, backfill, verify,
and only contract in a later release after the rollback window. Everything runs under a serialized
production lock with a least-privilege short-lived identity, bounded timeouts, observation, and a
recorded rollback path.

Interview Review:

The critical correction: PostgreSQL does NOT follow the API blue-green steps.

Production Case:

Renaming `prompt` -> `user_prompt` follows Expand -> compatible code -> backfill -> verify -> end
rollback window -> Contract later; a destructive change would break running v1 and rollback.

### 2. Why is DNS TTL not an atomic switch, and how does it differ from Nginx?

Question:

Why is a DNS change not atomic, and how does it differ from Nginx traffic switching?

中文解析:

权威 DNS 可以立即返回新值，但每个 resolver/客户端会缓存旧答案直到它自己的 TTL 到期，所以有的到 A、有的到 B——切换是渐进的。迁移前至少提前一个旧 TTL 周期降低 TTL，传播期间保持 A/B 可用、观察两者、窗口后再移除 A。DNS 做粗粒度的主机/位置发现与迁移；Nginx 在选定主机上做精确的后端切换。

Standard Answer:

Authoritative DNS may return the new value immediately, but each resolver/client keeps its cached old
answer until its own TTL expires, so some clients reach Server A and others reach Server B — the
switch is gradual. Lower the TTL at least one old-TTL period before migration, keep A and B available
during propagation, observe both, and remove A only after the window. DNS is coarse host/location
discovery; Nginx is precise backend traffic switching on the selected host.

Follow-up Question:

Why is lowering a 24h TTL five minutes before migration a mistake?

### Common Weak vs Strong Answer (Day25)

Weak: "Deployment means restarting the container with the new code, and a health check proves it
worked." (misses artifact promotion, blue-green/drain/rollback, schema contracts, and observation)

Strong: "Deployment is a serialized, observable, reversible production state transition that promotes
the exact verified digest, moves traffic with blue-green + drain, evolves PostgreSQL with
Expand-Migrate-Contract, rolls out workers compatibly, and keeps a bounded, least-privilege, recorded
rollback path."

---

# Day26 Kubernetes Foundations Questions

These questions come from the Day26 Kubernetes Foundations lesson: desired state and reconciliation,
Pod, Deployment, Service, ConfigMap, and Secret. Scope is Day26 only — Ingress, Autoscaling, Rolling
Update, StatefulSet, and Helm are Day27.

## Beginner

### 1. What is a Pod, and why is a Pod not the same as a container?

Question:

What is a Pod in Kubernetes, and why is a Pod not the same as a container?

中文解析:

Pod 是 Kubernetes 最小的可部署/可调度单元，包含一个或多个紧耦合的容器，它们共享同一个网络命名空间和 Pod IP、可通过 localhost 通信、可挂载共享卷、共享 Pod 的生命周期/替换边界，但仍是各自独立的进程，可以独立重启。Deployment 可以管理 Pod 副本，但把 Pod 调度到节点的是调度器，不是 Deployment。

Student's actual attempt (preserved):

> "pod is a sevral compose of container,it depend on deployment schedual.it is the smallest deployable unit.one or more containers share common lifecycle/network in pod."

Technical corrections:

- Correct: smallest deployable unit; one or more containers; shared network/lifecycle boundary.
- Incorrect: a Pod does not depend on a Deployment, and a Deployment does not schedule it to a Node.

English corrections:

```text
sevral -> several ; compose of -> consists of ; container -> containers ;
schedual -> scheduled ; depend -> depends
```

Standard Answer:

A Pod is the smallest deployable unit in Kubernetes. It contains one or more tightly coupled
containers that share the same network namespace and lifecycle. A Deployment can manage Pod replicas,
while the Kubernetes scheduler decides which node runs each Pod.

Follow-up Question:

When should two containers NOT be placed in the same Pod?

## Intermediate

### 1. How do a Deployment and a Service keep an app available when a Pod's IP changes?

Question:

A Pod fails and its replacement gets a new IP address. How do a Deployment and a Service work
together to keep the application available?

中文解析:

Deployment 维持期望副本数：Pod 消失就按模版创建替代 Pod（新名字、新 IP，可能新节点），它维持数量和模版而不是旧 Pod 的身份，也不负责调度。Service 通过标签选择当前的 Pod，提供稳定的 DNS 名和虚拟 IP，客户端只用 Service 名，不用追踪变化的 Pod IP。注意 selector 必须匹配 Pod 标签，且 Pod Running 不等于 Service 有可用 endpoint。

Student's actual attempt (preserved):

> "the deployment offer replica recovery pod,service offer stable network access"

Interview Review:

Correct distinction but incomplete mechanism — name the label selector and the stable DNS/VIP.

Standard Answer:

The Deployment maintains the desired number of replicas. If a Pod fails, it creates a replacement
Pod. The Service selects the current Pods by their labels and provides a stable DNS name and virtual
IP, so clients do not need to track changing Pod IP addresses.

Follow-up Question:

Does a running Pod guarantee the Service has matching endpoints?

### 2. Image, ConfigMap, or Secret?

Question:

Where do `MODEL_NAME`, `LOG_LEVEL`, `OPENAI_API_KEY`, and `DATABASE_PASSWORD` belong?

中文解析:

`MODEL_NAME`/`LOG_LEVEL` 是非敏感运行配置，放 ConfigMap，保持同一个已验证 digest 不变（改代码/依赖才需要新镜像新 digest 走新验证）。`OPENAI_API_KEY`/`DATABASE_PASSWORD` 是敏感数据，放 Secret，且只有 API 容器引用，日志 sidecar 不给。Base64 是编码不是加密；改 ConfigMap/Secret 不会改已运行进程的环境变量，通常要替换 Pod 才生效。

Standard Answer:

`MODEL_NAME` and `LOG_LEVEL` go in a ConfigMap so the verified image digest stays unchanged.
`OPENAI_API_KEY` and `DATABASE_PASSWORD` go in a Secret, referenced only by the API container. Base64
is encoding, not encryption, and updating either object does not change an already-running process
environment.

Follow-up Question:

After editing the ConfigMap, why might running Pods still show old behavior?

## Senior

### 1. Roll back a health-200-but-401 partial outage after a Secret rotation.

Question:

After a Secret rotation, one replacement Pod reads an invalid API key. Its health endpoint still
returns 200, but AI requests routed to that Pod return 401. How would you diagnose and roll back
without turning the partial outage into a full outage?

中文解析:

先冻结进一步的轮换和破坏性操作，不要删两个健康的旧 Pod（它们进程里还是正确的旧 key）。health 200 不代表业务成功，用 401 率、日志、业务指标确认故障并定位到读到新（无效）key 的那个 Pod。恢复到已知良好的旧 Secret 并验证 Secret 对象已恢复，只删除故障 Pod，让 Deployment 重建一个读到恢复后 key 的替代 Pod，跑真实 AI smoke test，观察 401/错误率/延迟/日志，记录最终状态。若在错误 Secret 还是当前值时删掉健康 Pod，所有替代都会读到错误 key，局部故障会变成全量故障。

Student's actual attempt (preserved):

> "the result of return 200 is not meaning logs,bussiness metric,error rate,latency process health.i would recovry old stable secrets,and then delete pod which goes wrong,deployment replace a new replica pod.the new pod recive old secrets."

Interview Review:

Rollback direction correct. Add: freeze rotation, verify Secret restoration, remove only the faulty
Pod, run a real business smoke test, and observe recovery before completing.

English corrections:

```text
is not meaning -> does not prove ; bussiness -> business ; metric -> metrics ;
recovry -> restore ; goes wrong -> is faulty ; recive -> receive
```

Standard Answer:

First, I would freeze further Secret rotation and avoid deleting the two healthy Pods. A 200 from the
health endpoint does not prove real AI requests work, so I would confirm the failure through 401
errors, logs, and business metrics. Then I would restore the previous known-good Secret and verify
the Secret object was updated. I would delete only the faulty Pod, let the Deployment create a
replacement, and verify it receives the restored credential. Finally, I would run a real AI smoke
test and observe the error rate and latency before completing the rollback.

Follow-up Question:

Why can automated reconciliation amplify a bad desired state instead of fixing it?

## Common Weak vs Strong Answer (Day26)

```text
Weak:   "A Deployment schedules three Pods and a Service load-balances them."
Strong: "A Deployment maintains three replicas from a Pod template; the scheduler places Pods on
        Nodes; a Service provides stable label-based discovery for the changing Pod set."

Weak:   "A Secret encrypts the API key."
Strong: "A Secret classifies sensitive data; its values are Base64-encoded, not encrypted. Real
        safety needs encryption at rest, RBAC, isolation, selective mounting, audit, and rotation."

Weak:   "Health returned 200, so the deployment succeeded."
Strong: "Health 200 is limited evidence; I also verify provider 401 rate, business errors, latency,
        and logs, because reconciliation enforces desired state, not business correctness."
```

---

# Day27 Kubernetes Workloads Questions

These questions come from the Day27 Kubernetes Workloads lesson: Ingress, Autoscaling (HPA), Rolling
Update, StatefulSet, and Helm. Scope is Day27 only — the full AI Backend assembly is Day28.

## Beginner

### 1. What is the difference between a Kubernetes Service and an Ingress?

Question:

What is the difference between a Kubernetes Service and an Ingress?

中文解析:

Service 提供稳定的 L4 网络端点，按标签选择当前 Pod 并转发流量，客户端不用追踪变化的 Pod IP。Ingress 是 L7，按域名(Host)和路径(Path)做 HTTP/HTTPS 路由并可终止 TLS，再转给对应的 Service。区别不是"内部 vs 外部"——有些 Service 类型也能对外暴露，而普通 Service 不会检查 HTTP 路径。另外 Ingress 资源只是声明规则，真正实现要靠 Ingress Controller。

Student's actual attempt (preserved):

> "service avoid to use pod ip ,provide a method to switch traffic to pod.ingress provide a entry point,by using domain and path link service"

English corrections:

```text
service avoid to use -> a Service avoids clients depending on ; pod ip -> Pod IP addresses ;
provide a entry -> provides an entry / HTTP routing ; link service -> routes requests to a Service
```

Standard Answer:

A Kubernetes Service provides a stable network endpoint for a group of Pods and routes traffic to
them, so clients do not depend on changing Pod IP addresses. An Ingress provides HTTP or HTTPS routing
based on hostnames and paths and forwards requests to the appropriate Services.

Follow-up Question:

Does an Ingress resource work without an Ingress Controller?

## Intermediate

### 1. Why can a CPU-based HPA fail on a low-CPU workload with growing queue backlog?

Question:

A workload has low CPU usage, but its queue backlog keeps increasing. Why might a CPU-based HPA fail,
and what metric would you use instead?

中文解析:

工作负载大部分时间在等外部模型服务，CPU 很低但请求堆积，所以基于 CPU 的 HPA 不会扩容。应改用队列积压(queue backlog)，最好是每 worker 的积压，并把 maxReplicas 限制在上游(provider)容量内，否则只是把排队变成大量 429 和更高成本。外部/自定义指标需要相应的 metrics adapter，HPA 也只是改期望副本数，由 Deployment 调谐 Pod。

Student's actual attempt (preserved):

> "i would use the queue backlog as a metirc."

English corrections:

```text
i -> I ; metirc -> metric
```

Interview Review:

Metric choice correct; state the cause (external wait keeps CPU low) and cap replicas by upstream
capacity.

Standard Answer:

A CPU-based HPA may fail because the workload is waiting on an external service instead of consuming
CPU, so CPU stays low while requests accumulate. I would use queue backlog, preferably backlog per
worker, to scale the worker Deployment that actually consumes the queue (not the API/producer), via an
external/custom metrics adapter, and cap the replica count so scaling does not exceed the provider's
rate limit.

Follow-up Question:

Does HPA create the new Pods itself?

### 2. Rolling Update vs rollback vs Blue-Green.

Question:

Distinguish a Deployment Rolling Update, a rollback, and Blue-Green.

中文解析:

Rolling Update 在同一个 Service selector 下逐步加入就绪的 v2、按 `maxSurge`/`maxUnavailable` 限制移除 v1，无需手动切流量。Blue-Green 是并行整套 v1/v2 再切流量。Rollback 不是 Rolling Update，而是把期望版本恢复到旧 revision，再由另一次受控 rollout 调谐。删除 v2 Pod 不是回滚——如果模版还是 v2，控制器会再建 v2。

Standard Answer:

A Rolling Update gradually adds ready v2 Pods under the same Service selector and removes v1 within
`maxSurge`/`maxUnavailable` limits, so no manual switch is needed. Blue-Green runs full parallel v1
and v2 environments and switches traffic. A rollback restores a previous desired revision through
another controlled rollout; deleting v2 Pods is not a rollback because the controller recreates the
current v2 desired state.

Follow-up Question:

With `maxSurge: 1` and `maxUnavailable: 0`, what happens if v2 Readiness always fails?

## Senior

### 1. Safe release, business-failure detection, and rollback without an outage.

Question:

How would you safely deploy a new application version in Kubernetes, detect a business-level failure,
and roll back without causing an outage?

中文解析:

用 Rolling Update，`maxUnavailable: 0` + 受控 `maxSurge`，让旧 Pod 一直可用直到新 Pod 通过 Readiness。发布中观察错误率、延迟、日志、队列压力和业务指标，而不是只看 HTTP 健康检查(Readiness 200 不等于业务正确)。出问题就停止 rollout，把 Deployment 或 Helm 恢复到上一个 revision。`helm --atomic --wait --timeout` 能在就绪失败时尝试回滚，但业务级失败仍需可观测性与部署自动化；数据库变更要向后兼容，因为 Helm 无法撤销外部副作用。

Student's actual attempt (preserved):

> "helm is a great method,it could automatly rollback old version application.when the old version application stable running under smoke test.Kubernetes rolling update old version step by step"

Interview Review:

- Correct: connect Helm revision rollback, smoke testing, and Rolling Update.
- Incomplete: Helm does not auto-roll back every upgrade; Readiness cannot detect every business failure.

English corrections:

```text
automatly -> automatically ; old version application -> the previous stable version ;
stable running -> runs stably ; rolling update ... step by step -> gradually replaces old with new
```

Standard Answer:

I would use a Rolling Update with `maxUnavailable: 0` and a controlled `maxSurge`, so old Pods stay
available until new Pods pass Readiness. During the rollout I would monitor error rate, latency, logs,
queue pressure, and business metrics rather than only HTTP health checks. If the new version caused a
business failure, I would stop the rollout and restore the previous Deployment or Helm revision.
`--atomic`, `--wait`, and a timeout help with readiness failures, but business-level rollback still
needs observability and deployment automation, and database changes must stay backward compatible
because Helm cannot undo every external side effect.

Follow-up Question:

Why is a StatefulSet with three PVCs not enough for PostgreSQL high availability?

## Common Weak vs Strong Answer (Day27)

```text
Weak:   "HPA scales the Pods automatically."
Strong: "HPA updates desired replicas on a scale target from a meaningful metric; the Deployment
        reconciles Pods and the scheduler places them. For external-wait workloads I scale on queue
        backlog, not CPU."

Weak:   "A StatefulSet gives me three database copies."
Strong: "A StatefulSet gives stable identity and per-Pod storage, not replication. HA needs WAL
        replication, leader election, failover, fencing, and independent backups."

Weak:   "helm template passed, so the release is safe."
Strong: "helm lint/template prove structure and rendering; API dry-run proves schema; only runtime
        plus business smoke tests prove user-visible correctness."
```
