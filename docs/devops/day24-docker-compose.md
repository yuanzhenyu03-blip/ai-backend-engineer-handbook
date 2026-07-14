# Lesson 24 — Docker Compose

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 5-6 hours

Prerequisite: Day23 — Docker Fundamentals

Previous Lesson: Day23 — Docker Fundamentals

Next Lesson: Day25 — Deployment Foundations

Engineering Artifact: A multi-service `compose.yaml` + `compose.dev.yaml` (+ `.env.example`) for a local FastAPI + Worker + Redis + PostgreSQL stack.

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why individually runnable containers do not make a reproducible system.
* Distinguish `depends_on`, a healthcheck, and application retry ("started" ≠ "ready").
* Distinguish Project, Service, Image, and Container, and decide rebuild vs recreate.
* Write a declarative Compose model with services, networks, volumes, and secrets.
* Use service DNS names and publish only the necessary host port.
* Design network segmentation for least access.
* Separate ordinary configuration, secrets, and governed business data.
* Split a portable base file from a development override.
* State where Compose fits in production and where a cluster is required.
* Answer beginner, intermediate, and senior Compose interview questions in English.

The engineering artifact is Compose YAML, not application code.

---

# Why This Matters

Day23 made one container reproducible. But a real AI backend is several services — FastAPI, a
worker, Redis, PostgreSQL — and starting them by hand with many `docker run` commands does not
scale.

The problem: manual commands drift across developers. Someone forgets a flag, uses a different
port, a different network, a different volume, or a different environment variable. Startup
assumptions live in people's heads, and onboarding is slow.

```text
Reproducible system
  = reproducible Images
  + reproducible runtime configuration
  + reproducible service relationships
```

Docker makes one container reproducible; Compose makes multiple **services and their
relationships** reproducible, as a version-controlled declaration.

Why a backend engineer should care:

```text
Reliability -> the whole stack starts the same way for everyone, every time.
Onboarding  -> `docker compose up` replaces a page of remembered commands.
Security    -> only the API is exposed; secrets and networks are scoped per service.
Correctness -> health-aware startup and least-access networks are declared, not improvised.
Roadmap     -> Day25 deployment and Day26-27 Kubernetes build on these service boundaries.
```

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day23)
        |
        v
Current Concept (Day24: declare a reproducible multi-service system)
        |
        v
Future Production Usage (Day25 deployment, Day26-27 Kubernetes, Day28 AI backend)
```

Where Day24 sits in the full path:

```text
Day22 GitHub Actions Advanced -> build once, promote one immutable image identity
Day23 Docker Fundamentals     -> build and run ONE reproducible container correctly
Day24 Docker Compose          -> declare and coordinate a reproducible MULTI-service system
                                 on one Docker host
Day25 Deployment Foundations  -> reverse proxy, TLS, domain, traffic switching, zero downtime
Day26-Day27 Kubernetes        -> cluster scheduling, Services, config/Secrets, rolling updates
Day28 Production AI Backend    -> FastAPI + Worker + Redis + PostgreSQL + storage + observability
```

Day23 mental models reused directly here:

```text
Container = isolated process, not a small VM.
Image = immutable template; Container = replaceable instance.
Runtime configuration is distinct from image content.
Durable state must not depend on the writable layer.
`localhost` = the current container; cross-container traffic uses a network + service DNS.
Change flows: rebuild/verify/replace, not live mutation.
```

Future lessons depend on Day24's service boundaries. Day24 does NOT provide production traffic
entry, TLS, zero-downtime deployment, multi-node scheduling, or autoscaling — those are labeled as
future connections, not Compose features.

---

# Lesson Map

```text
Why Compose (drift -> declaration)
  -> Started != Ready (depends_on / healthcheck / app retry)
  -> Project / Service / Image / Container (rebuild vs recreate)
  -> Declarative model & YAML
  -> Host ports, networking, service DNS
  -> Network segmentation (least access)
  -> Volumes & data lifecycle
  -> Env vars / .env / Secrets / business data
  -> Local development workflow
  -> Base + dev override
  -> Compose production boundary
```

---

# Estimated Study Time

```text
Reading: 120-150 minutes
Exercises: 70-100 minutes
Hands-on Compose authoring: 70-100 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Core Mental Model

```text
Compose Model
  -> Project           (boundary for related resources)
  -> Services          (desired runtime spec per workload role)
  -> Containers        (replaceable instances of a service)
  -> Networks          (explicit reachability)
  -> Volumes           (durable state)
  -> Environment / Secrets  (runtime config vs protected credentials)
  -> Health Dependencies    (service_healthy before dependents start)
= a version-controlled multi-service application on ONE Docker host
```

The distinctions that carry the lesson:

```text
Started                != Ready
Health Signal          != Recovery
Volume Persistence     != Backup
Environment Variable   != Secret
Bind Mount             != Writable Layer
Image                  != Service Specification
Compose Coordination   != Multi-node Cluster Orchestration
```

Compose core: a declarative, version-controlled specification for defining and running a
reproducible multi-service application — not merely a one-time script that starts several
containers.

---

# Main Concepts

## Concept 1: Why Docker Compose Exists

### Tech Lead Question

You start FastAPI, Redis, and PostgreSQL with three separate `docker run` commands. What goes
wrong as the team grows?

### Student Thinking

Order and flags are easy to forget; everyone runs slightly different commands.

### Student Answer

> "因为 container 之间互相依赖有一个顺序……漏掉启动项，没有按照正确启动顺序启动，没有按照 IaC 的
> 原则进行工程化部署，每个人执行的配置命令都不一样，导致冲突，新加入成员无法快速熟悉项目……解决
> 多容器协调工作问题，避免手动启动出错。"

### Tech Lead Review

Right. Manual commands drift: missing flags, inconsistent ports/networks/volumes/env, hidden
startup assumptions, slow onboarding. Compose turns remembered operations into a
version-controlled declaration.

```text
Reproducible system = reproducible Images + reproducible runtime config + reproducible relationships
```

### Engineering Thinking

Docker made one container reproducible; Compose makes the *relationships* between services
reproducible.

### Production Example

A new engineer clones the repo and runs `docker compose up` to get the exact local stack, instead
of following a wiki of `docker run` commands.

### Framework Connection

The local RAG stack (FastAPI + Worker + Redis + PostgreSQL) becomes one declared system.

### Exercise

Explain why individually runnable containers do not guarantee a reproducible system.

## Concept 2: Started ≠ Ready (`depends_on`, healthcheck, retry)

### Tech Lead Question

PostgreSQL's container starts first but is still initializing when the API queries it. Was the
startup order wrong?

### Student Thinking

In a sequential script, the earlier command finishing usually means the next step can proceed.

### Student Answer

> "depends_on 保证了依赖关系，没有保证 PostgreSQL 已经可以接受查询……服务存在不代表服务就绪……
> 缺少服务就绪检查以及应用重试机制。"

### Tech Lead Review

The container order was satisfied; the readiness contract was not.

```text
depends_on (short form) -> only waits for the dependency container to START.
healthcheck             -> a service-specific probe reporting healthy/unhealthy (NOT repair/restart).
depends_on: condition: service_healthy -> waits for the dependency's healthcheck at startup.
application retry        -> bounded retry + backoff for transient failures during and AFTER startup.
```

Different services need different probes (`redis-cli ping` vs `pg_isready`). Healthcheck timing:
`start_period` (init grace), `interval` (schedule), `timeout` (one probe), `retries` (consecutive
failures before unhealthy). Initial orchestration cannot replace runtime resilience.

### Engineering Thinking

Ask three separate questions: started? healthy? able to serve? A running container can be
unhealthy; a healthy dependency can still fail later.

### Production Example

The API waits for `postgres` `service_healthy`, and still retries a transient connection error
with backoff after startup.

### Framework Connection

Redis healthcheck `redis-cli ping`; PostgreSQL `pg_isready -U app -d app`.

### Exercise

Separate Compose health from application retry for a PostgreSQL startup race.

## Concept 3: Project, Service, Image, Container

### Tech Lead Question

Three API replicas plus one worker — how many services, images, containers?

### Student Thinking

They share an image, so maybe they are "instances" of the same thing?

### Student Answer

> "project 1个，service 4个，container 6个，image 3个。image 决定不可变的部分，service
> specification 决定可变的配置，二者共同构建 container。"

### Tech Lead Review

Correct counting and the key insight:

```text
Project   = boundary for related services, networks, volumes.
Service   = desired runtime spec for one workload role (exists even at zero instances).
Image     = immutable contents.
Container = one replaceable instance from Image + Service specification.
```

One service can create many containers (three API replicas = one service). One image can back many
services with different commands (API vs Worker). Change flows:

```text
Image content change    -> rebuild + recreate
Runtime config change   -> recreate (usually no rebuild)
Mounted source change   -> sync/reload (not necessarily rebuild)
```

### Engineering Thinking

Image supplies immutable contents; the service specification supplies command, env, networks,
volumes, ports, secrets, scaling. Both build the container.

### Production Example

API and Worker are two services built from one `rag-app:local` image with different commands.

### Framework Connection

API command runs Uvicorn; Worker command runs `python -m app.worker`.

### Exercise

Classify Project/Service/Image/Container and count them for the stated architecture.

## Concept 4: Declarative Model and YAML

### Tech Lead Question

What does `docker compose up` actually do — run a script top to bottom?

### Student Thinking

It probably reads the file and starts things in order.

### Student Answer

> "最终期望存在哪些服务与资源……应该检查当前状态并完成必要变化。"

### Tech Lead Review

Correct: Compose resolves the desired model, then creates/starts/recreates what is necessary. It
is command-triggered convergence, not a continuous Kubernetes control loop. Repeated `up` does not
blindly duplicate a project: changed service config or image causes recreation; mounted volumes
are preserved. A top-level resource (network/volume/secret) is not granted to a service unless the
service references it.

YAML indentation IS the data structure. (Classroom event: chat rendering made correct spaces look
missing and the Tech Lead misread the YAML; a student editor screenshot proved real spaces and
list markers. Correction: actual artifact evidence outranks chat rendering.)

### Engineering Thinking

Declare the end state; let Compose converge. Reference resources explicitly.

### Production Example

Adding a `LOG_LEVEL` change and running `up` recreates only the affected service, keeping the
database volume.

### Framework Connection

Use the current Compose Specification (no obsolete top-level `version:` field).

### Exercise

Repair and visually verify YAML indentation; trust the parsed file over chat rendering.

## Concept 5: Host Ports, Networking, and Service DNS

### Tech Lead Question

From the API container, does `redis://localhost:6379` reach the Redis container?

### Student Thinking

Day23 said `localhost` is the current container, so probably not.

### Student Answer

Student correctly used `redis:6379`, `postgres:5432`, and published only `8000:8000` for the API.

### Tech Lead Review

Right.

```text
Host port      = external entry into the project (only API needs 8000:8000).
Container port = internal service endpoint.
Internal calls -> service DNS names (redis:6379, postgres:5432), never localhost.
Service DNS is stable across recreation; a container IP is not the contract.
```

Publishing Redis/PostgreSQL just for convenient maintenance increases attack surface. Prefer
`docker compose exec`, a one-off admin service, or an explicitly local-only temporary binding when
genuinely required.

### Engineering Thinking

Expose the minimum. Address services by name, not IP.

### Production Example

The API is the only reachable entry point; Redis and PostgreSQL are internal-only.

### Framework Connection

Worker and API both reach `redis:6379` and `postgres:5432` by DNS.

### Exercise

Fill a Compose model with service DNS, the single published port, networks, and a named volume.

## Concept 6: Network Segmentation and Least Access

### Tech Lead Question

One shared network works. Why split into two?

### Student Thinking

A single network is simplest, but everything can reach everything.

### Student Answer

> "Redis 与 Postgres 不在同一个 network，防止 Redis 被攻占以后继续通过 network 连接 container……
> 只有一个外部进入入口，其他 container 通过 network 的 service name 连接。"

### Tech Lead Review

Correct. A single shared network grants broad east-west reachability. Final design:

```text
queue_network:    API + Worker + Redis
database_network: API + Worker + PostgreSQL
Redis and PostgreSQL share NO network (limits lateral movement).
```

Network membership is one access layer; it does not replace database credentials, Redis auth, or
application authn/authz. A PostgreSQL backup tool joins only `database_network`. Cache data is not
automatically backup data: if Redis is a rebuildable cache, PostgreSQL is the source of truth; if
Redis carries durable queue state, persistence must be designed explicitly.

### Engineering Thinking

Design networks as access boundaries, not just connectivity.

### Production Example

A compromised Redis cannot reach PostgreSQL because they share no network.

### Framework Connection

A backup tool joins only `database_network` to back up the source of truth.

### Exercise

Design Queue/Database network segmentation and a scoped backup tool.

## Concept 7: Volumes and Data Lifecycle

### Tech Lead Question

`docker compose down` — does it delete the database?

### Student Thinking

"down" sounds destructive, but maybe volumes are separate.

### Student Answer

> "A、B、C 数据继续存在，D 会删除……顶层声明只是做了定义，实际还是在 service 中挂载才能使用……
> 没挂载会保存在 writable layer。"

### Tech Lead Review

Correct.

```text
restart / recreate / `docker compose down` -> named volume PRESERVED.
`docker compose down --volumes`            -> named volume DELETED (destructive locally).
No volume mount                            -> PostgreSQL files live in the writable layer.
```

Four storage kinds:

```text
Bind Mount     = host-owned development files.
Named Volume   = Docker-managed, container-independent data/cache.
Writable Layer = container-owned ephemeral changes.
Image Layer    = immutable packaged application.
```

`./app:/app/app` makes host source visible; Uvicorn `--reload` is the separate reload mechanism.
`pip_cache` and PostgreSQL data may both use named volumes, but cache is disposable while
PostgreSQL is durable state. Volume persistence is not backup — backups and restore tests are
separate controls.

### Engineering Thinking

Separate compute lifecycle from data lifecycle; keep API/Worker stateless.

### Production Example

`postgres_data` at `/var/lib/postgresql/data` survives container recreation.

### Framework Connection

API/Worker have no persistent volume; PostgreSQL owns `postgres_data`.

### Exercise

Compare bind mount, named volume, and writable layer; analyze `down --volumes`.

## Concept 8: Environment, `.env`, Secrets, and Business Data

### Tech Lead Question

Is `.env` a safe place for the PostgreSQL password?

### Student Thinking

Keeping it out of the YAML seems to hide it.

### Student Answer

Student classified `APP_ENV`, `LOG_LEVEL`, `MODEL_NAME` as normal config; `POSTGRES_PASSWORD`, a
credential-bearing `DATABASE_URL`, `OPENAI_API_KEY`, and a private key as secrets; customer prompts
and medical records as business data.

### Tech Lead Review

Correct classification. Four categories:

```text
Environment Variable = ordinary runtime configuration.
Secret               = protected access credential.
Business Data        = governed application data (storage, audit, encryption, retention).
Hardcoded Value      = repository/image-visible static value (avoid for anything sensitive).
```

`.env` is a plaintext interpolation source, not a Secret Manager. `${NAME}` resolves when Compose
parses the model; `environment` defines values passed to the container. Dockerfile `ARG`/`ENV`
must not carry build secrets. Compose secrets are top-level resources, granted per service, mounted
at `/run/secrets/<name>` — and the application must actually READ the file. Least-privilege grants:
API → `postgres_password`; Worker → `postgres_password` + `openai_api_key`; PostgreSQL →
`postgres_password`; Redis → none. Exclude `.env` and `.secrets/` from Git and the build context;
do not blindly ignore `tests/` (CI may need it).

### Engineering Thinking

Classify by semantics and lifecycle, not size. A credential grants access; customer data is
governed data.

### Production Example

Only the Worker receives `openai_api_key` because only it calls the model provider.

### Framework Connection

`POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password`; the app reads the file path.

### Exercise

Classify config/secret/business-data and fill Compose secret grants and `_FILE` paths.

## Concept 9: Local Development Workflow

### Tech Lead Question

You changed `LOG_LEVEL`. Do you run `up --build`?

### Student Thinking

Rebuild seems safest, but it may be unnecessary.

### Student Answer

> "修改源代码 sync/reload，修改依赖 rebuild+recreate，修改配置 recreate。"

### Tech Lead Review

Correct mapping. Match the command to the changed layer:

```text
config      -> parse/interpolate/merge/render the resolved model WITHOUT starting.
up -d --build -> build when needed, start detached.
ps --all    -> observe running and exited containers.
logs -f api -> follow API evidence.
exec api .. -> run inside an existing running container.
run --rm api alembic upgrade head -> one-off container from the API spec, removed after.
stop        -> stop but preserve containers/networks/volumes.
down        -> remove containers + networks, KEEP named volumes.
down --volumes -> also delete named volumes.
```

Debug sequence: observe → identify → hypothesize → test → fix → verify. Deleting all containers
first erases evidence.

### Engineering Thinking

Source change → reload; dependency change → rebuild+recreate; config change → recreate.

### Production Example

Applying `LOG_LEVEL` recreates the affected container; it does not need a rebuild.

### Framework Connection

`run --rm api alembic upgrade head` runs a migration as a one-off container.

### Exercise

Map change types to `up`, `ps`, `logs`, `exec`, `run --rm`, `config`, `stop`, `down`,
`down --volumes`.

## Concept 10: Base Configuration and Development Override

### Tech Lead Question

Where do source bind mounts and `--reload` belong?

### Student Thinking

They are development-only; they should not ship to production.

### Student Answer

Student kept the base portable and put development differences in an override.

### Tech Lead Review

Right.

```text
compose.yaml      -> portable, production-style service model.
compose.dev.yaml  -> ONLY development differences: source bind mounts + Uvicorn --reload.
```

Compose file merge and Uvicorn reload are separate mechanisms. Keeping dev differences in an
override prevents duplication/drift and avoids carrying host source mounts into production.
API/Worker stay stateless; PostgreSQL owns durable state.

### Engineering Thinking

One portable base; a thin override for local ergonomics.

### Production Example

Production uses only `compose.yaml`; developers merge `compose.dev.yaml` for reload.

### Framework Connection

`docker compose -f compose.yaml -f compose.dev.yaml up` merges both.

### Exercise

Split base and dev override; add `.gitignore`/`.dockerignore` rules.

## Concept 11: The Compose Production Boundary

### Tech Lead Question

"Compose can never be used in production" — true or false?

### Student Thinking

It feels dev-only, but it can start production containers.

### Student Answer

Student selected Compose for local/CI, Compose-with-controls for a small single-host internal
system, and a cluster/managed platform for a 99.99% public AI API.

### Tech Lead Review

Correct and nuanced. Compose fits local dev, integration tests, CI dependencies, demos, and
controlled single-host systems whose failure domain is accepted — with added backups + restore
tests, monitoring, logs, alerts, TLS/reverse proxy, firewall, secret management, resource limits,
host patching, and deploy/rollback procedures.

```text
Compose      = multi-service declaration + lifecycle coordination on a Docker host.
Kubernetes / managed platform = distributed desired-state system: multi-node scheduling,
                                self-healing, scaling, controlled rollout.
```

Compose does not by itself provide multi-node scheduling, node-failure rescheduling, continuous
replica reconciliation, autoscaling, production rolling updates, automatic rollback, or public
DNS/TLS/secret-rotation governance. Tool choice depends on availability target, failure domain,
traffic, deployment frequency, recovery needs, data importance, team ability, and cost — not
"small vs large project."

### Engineering Thinking

Say "declaration and lifecycle coordination," not "scheduling." A scheduler chooses a node under
constraints.

### Production Example

A small internal knowledge base runs on Compose on one host with backups, TLS, and monitoring; a
public high-availability AI API needs a cluster.

### Framework Connection

Day25 (deployment) and Day26-27 (Kubernetes) add the capabilities Compose lacks.

### Exercise

Decide Compose vs Compose-with-controls vs cluster for local, CI, single-host internal, and
99.99% public scenarios.

---

# Common Misconceptions

## Mental Model Evolution (Day23 → Day24)

Preserve how understanding evolved, not only the mistakes:

```text
Initial: "Day23 already solved running multiple containers by hand."
Reasoning: Day23 exercises used several `docker run` commands for networks and data.
Correction: Day23 established Image -> Container primitives; Day24 declares and coordinates the
            multi-service system.
Final: Day23 = Dockerfile -> Image -> Container; Day24 = Compose model -> Project of Services.
```

The student's final synthesis was still imperfect (e.g. phrasing Compose as "an engineering
runtime style, not lifecycle coordination"). The corrected, durable model: Compose IS lifecycle
coordination, and its core is a declarative, version-controlled specification of a multi-service
application and its runtime relationships on one Docker host.

## Misconception list

```text
Started vs Ready
❌ PostgreSQL starting first but still initializing means the startup order was wrong.
✅ Container order was satisfied; the readiness contract was not. Ask: started? healthy? serving?
```

```text
Service vs instance
❌ API and Worker sharing an image are two instances.
✅ They are two services/roles; replicas of one service are the multiple instances.
```

```text
Image vs Service specification
❌ Deleting an API container restores all rules from the image.
✅ Image supplies immutable contents; the service spec supplies env/command/networks/volumes/ports/secrets.
```

```text
Rebuild vs recreate
❌ Any config change (or a shared image) means rebuild.
✅ Image content -> rebuild+recreate; runtime config -> recreate; mounted source -> reload/sync.
```

```text
Healthcheck meaning
❌ A healthcheck means the process runs and it repairs/restarts the service.
✅ It runs a probe and reports health; a running container can be unhealthy. It does not repair or replace application retry.
```

```text
Bind mount vs writable layer
❌ Host code changes disappear when the container restarts.
✅ A bind mount is host-owned and survives container replacement while host files exist; reload is a separate behavior.
```

```text
Named volume vs backup
❌ Persistence alone is sufficient protection.
✅ A volume survives the container lifecycle; a backup survives volume/host loss and must be restorable.
```

```text
.env safety
❌ `.env` is safe because it is local and only referenced by Compose.
✅ `.env` is plaintext interpolation input, not a Secret Manager; protect and ignore it, use scoped secrets.
```

```text
Secret vs business data
❌ Customer prompts/medical records are not secrets mainly because they are large.
✅ Classification is by semantics/lifecycle: credentials grant access; customer data is governed data.
```

```text
Compose in production
❌ Compose can never be used in production (yet rolling updates/public TLS are "Compose-suitable").
✅ Controlled single-host prod can be reasonable with extra controls, but Compose lacks multi-node scheduling, reconciliation, autoscaling, and rollout governance.
```

```text
Scheduling terminology
❌ Compose provides single-host multi-service scheduling.
✅ Call it declaration + lifecycle coordination; a scheduler chooses a node under constraints.
```

```text
Docker Compose is a...
❌ "Docker Compose is a multi-container application."
✅ Docker Compose is a TOOL for defining and running multi-container applications.
```

---

# Engineering Trade-offs

```text
depends_on vs healthcheck vs application retry
Simple ordering  vs  readiness proof  vs  runtime resilience. You usually need all three.

One shared network vs segmented networks
Simplicity/connectivity  vs  least access and smaller blast radius.

Publish DB ports vs exec/admin-only access
Convenient maintenance  vs  larger attack surface. Prefer exec or a scoped admin service.

Named volume vs backup
Survives container lifecycle  vs  survives volume/host loss and is restorable. Different controls.

Shallow API health vs dependency-aware readiness
Fast, fewer false negatives  vs  catches broken dependencies but can flap. Choose deliberately.

Base + dev override vs one big file
No duplication/drift, prod-safe  vs  slightly more files to reason about.

Compose vs Kubernetes/managed platform
Operational simplicity on one host  vs  multi-node scheduling, self-healing, scaling, rollout.
```

---

# Hands-on Exercises

The engineering artifact is Compose YAML.

## Exercise 1: Why a Reproducible System

Question: why do individually runnable containers not guarantee a reproducible system?

Think First: what is not captured by separate `docker run` commands?

Expected Output: they capture no single version-controlled declaration of the services and their
runtime relationships; configuration drifts across people.

Follow-up Question: what three things must be reproducible together?

## Exercise 2: Startup Order vs Readiness

Question: PostgreSQL starts first but is initializing; the API fails to query it. Diagnose it.

Think First: started, healthy, or able to serve?

Expected Output: container order was satisfied; readiness was not. Use `depends_on: condition:
service_healthy` with a real `pg_isready` healthcheck, and keep application retry for transient
runtime failures.

Follow-up Question: does a healthcheck repair the service?

## Exercise 3: Count Project/Service/Image/Container

Question: 1 Project, 4 Services, and (under the stated assumptions) 3 distinct Images — how many
Containers, and why?

Expected Output: 6 Containers (e.g. 3 API replicas + Worker + Redis + PostgreSQL); a service can
have many container instances.

Follow-up Question: how can one image back two services?

## Exercise 4: Rebuild vs Recreate

Question: classify each change as rebuild+recreate, recreate, or reload.

Starter Artifact:

```text
Changed LOG_LEVEL; changed requirements.txt; edited bind-mounted source.
```

Expected Output: `LOG_LEVEL` -> recreate; `requirements.txt` -> rebuild+recreate; source -> reload.

Follow-up Question: why does mounted source not need a rebuild?

## Exercise 5: Fill the Compose Model

Question: write services for FastAPI/Worker/Redis/PostgreSQL with DNS, the single published port,
two networks, and a named volume.

Think First: which service publishes a host port?

Expected Output: only `api` publishes `8000:8000`; internal calls use `redis:6379`/`postgres:5432`;
`postgres` mounts `postgres_data`. See `examples/docker/compose/compose.yaml`.

Follow-up Question: which services join which network, and why?

## Exercise 6: Healthchecks + `service_healthy`

Question: add Redis and PostgreSQL healthchecks and long-form `depends_on`.

Expected Output:

```yaml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U app -d app"]
api:
  depends_on:
    redis: { condition: service_healthy }
    postgres: { condition: service_healthy }
```

Follow-up Question: what do `start_period`, `interval`, `timeout`, and `retries` mean?

## Exercise 7: Classify Config, Secrets, and Business Data

Question: classify `APP_ENV`, `LOG_LEVEL`, `MODEL_NAME`, `POSTGRES_PASSWORD`, a credential-bearing
`DATABASE_URL`, `OPENAI_API_KEY`, a customer prompt, and a medical record.

Expected Output: first three = normal config; password/`DATABASE_URL`/API key = secrets; customer
prompt and medical record = governed business data.

Follow-up Question: where does each secret get mounted, and who must read it?

## Exercise 8: Compose vs Cluster Decision

Question: choose Compose, Compose-with-controls, or a cluster/managed platform for: local dev; CI
dependencies; a small single-host internal knowledge base; a 99.99% public AI API with 20x traffic
variation.

Expected Output: local/CI -> Compose; single-host internal -> Compose + controls; public 99.99% ->
cluster/managed platform.

Follow-up Question: which capabilities does Compose not provide by itself?

## Exercise 9: Build the Integrated Stack (Reusable Artifact)

Question: assemble `compose.yaml` for API + Worker + Redis + PostgreSQL, then split
`compose.dev.yaml` for source mounts + `--reload`, and validate both models.

Expected Output: see `examples/docker/compose/` — validate with `docker compose config` and
`docker compose -f compose.yaml -f compose.dev.yaml config`.

Follow-up Question: since only `api` has `build`, what must happen before `worker` can start?

---

# Relevant Framework Connections

Only technologies genuinely used are connected (no forced Playwright).

## Docker / Docker Compose

```text
The direct subject: the service model, networks, volumes, healthchecks, secrets, lifecycle, and CLI.
```

## FastAPI

```text
The API service runs Uvicorn, publishes 8000:8000, exposes /health, and stays stateless. Source
bind mount + `--reload` are development-only (compose.dev.yaml).
```

## Redis

```text
Cache/queue service on queue_network, `redis-cli ping` healthcheck; persistence depends on whether
it is a rebuildable cache or durable queue state.
```

## PostgreSQL

```text
Durable source of truth: named volume, `pg_isready` healthcheck, password via secret file, on
database_network, with a scoped backup tool.
```

## GitHub Actions

```text
Only the relevant CI link: Compose can start integration-test dependencies, and one application
image is built/verified before promotion (Day22). Not a new Actions lesson.
```

## Kubernetes (future connection only)

```text
Used to draw the boundary between command-triggered single-host coordination (Compose) and
continuous multi-node orchestration (Day26-27). Not taught here.
```

---

# AI Backend Connections

```text
A realistic local RAG/AI backend: FastAPI API, background Worker, Redis, PostgreSQL.
The API receives requests; the Worker may call the OpenAI API. Role-based secret grants keep the
OpenAI key away from the API, which does not need it.
Redis may be a rebuildable cache or durable queue state; persistence depends on the role.
PostgreSQL is the durable source of truth.
Customer prompts, documents, and medical data are governed business data, not deployment secrets.
Stateless API/Worker containers stay replaceable; durable state lives outside them.
A public AI API needs stronger operational capabilities (availability, traffic variation, rolling
deployment, GPU scheduling, multi-node recovery) that arrive from Day25 onward.
```

---

# English Interview

## Beginner

Question: What problem does Docker Compose solve, and how is it different from running multiple
`docker run` commands manually?

Student's actual attempt (preserved):

> "the docker compose is a multi-container application what incloud services, networks, volumes,
> and it's a good for team collaboration. it is a reproducibility declarative configuration"

Correction: it is a *tool for defining and running* multi-container applications, not "a
multi-container application."

Strong answer:

> Docker Compose is a tool for defining and running multi-container applications. A Compose file
> declaratively describes the application's services, networks, volumes, and runtime
> configuration. Compared with multiple manual `docker run` commands, it reduces missing
> parameters and configuration drift, and because it is version-controlled, every team member can
> reproduce the same local environment.

## Intermediate

Question: What is the difference between `depends_on`, a healthcheck, and application-level retry?

Student's actual attempt (preserved):

> "the depends_on is startup order, the health check is a tool for check service readiness, and
> application-level retry is a retry with backoff when the application meet runtime failure,
> transient failure"

Correction: the direction is right; tighten that short `depends_on` waits only for the container
to start (not readiness), and that all three are needed because a started container may not be
ready and a healthy dependency may still fail later.

Strong answer:

> `depends_on` controls startup order; with its short syntax it only waits for the dependency
> container to start, not to become ready. A healthcheck tests whether a service can actually
> provide its capability. Application-level retry handles transient failures during and after
> startup, usually with bounded exponential backoff. Initial orchestration cannot replace runtime
> resilience.

## Senior

Question: When would you use Docker Compose in production, and when would you choose Kubernetes or
a managed platform?

Strong answer:

> I would use Compose for a small, single-host production system when the business accepts the host
> as a single failure domain — it is operationally simple — but I would still add backups,
> monitoring, TLS, secret management, resource limits, and a rollback process. I would choose
> Kubernetes or a managed platform when the system needs multi-node scheduling, self-healing,
> autoscaling, and rolling updates. Kubernetes continuously reconciles actual state to desired
> state across a cluster, while Compose coordinates services on one host when commands run. The
> trade-off is operational simplicity versus stronger automation, resilience, and scalability.

---

# Mental Model Summary

```text
Compose Model -> Project -> Services -> Containers -> Networks -> Volumes
              -> Environment / Secrets -> Health Dependencies
Started              != Ready
Health Signal        != Recovery
Volume Persistence   != Backup
Environment Variable != Secret
Bind Mount           != Writable Layer
Image                != Service Specification
Compose Coordination != Multi-node Cluster Orchestration
Compose core = a declarative, version-controlled multi-service specification on one Docker host,
               not a one-time script that starts several containers.
```

---

# Today's Takeaway

Compose turns remembered `docker run` operations into a version-controlled declaration of a
multi-service system and its relationships.

* Most important mental model: Compose model -> Project of Services on one host; started ≠ ready.
* Most important production risk: assuming "started" means "ready," or treating volume persistence
  as backup.
* Most important trade-off: Compose's operational simplicity vs a cluster's scheduling, self-healing,
  and rollout.
* Most important framework connection: only the API publishes a host port; services talk by DNS.
* Most important AI backend connection: role-based secrets (only the Worker gets the OpenAI key);
  PostgreSQL is the source of truth; API/Worker stay stateless.
* Most important interview answer: Compose is a tool for defining and running multi-container apps;
  `depends_on` ≠ healthcheck ≠ retry.

The most important engineering sentence:

```text
Declare the whole system once: reproducible images + runtime configuration + service relationships,
exposing only what must be exposed and persisting durable state outside replaceable containers.
```

---

# Before Next Lesson Checklist

Before Day25 (Deployment Foundations), confirm you can answer these without looking at the notes:

- [ ] Why do individually runnable containers not make a reproducible system?
- [ ] How do `depends_on`, healthcheck, and application retry differ?
- [ ] Project vs Service vs Image vs Container — and rebuild vs recreate?
- [ ] Why publish only the API port and use service DNS internally?
- [ ] Why segment networks, and what can it NOT replace?
- [ ] What does `docker compose down` keep, and what does `--volumes` delete?
- [ ] Environment variable vs secret vs governed business data?
- [ ] Why keep source bind mounts + `--reload` in a dev override only?
- [ ] Where does Compose fit in production, and where is a cluster required?
- [ ] Can I state the Compose core in one sentence in English?
