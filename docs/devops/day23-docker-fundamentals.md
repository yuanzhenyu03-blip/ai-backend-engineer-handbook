# Lesson 23 — Docker Fundamentals

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 5-6 hours

Prerequisite: Day22 — GitHub Actions Advanced

Previous Lesson: Day22 — GitHub Actions Advanced

Next Lesson: Day24 — Docker Compose

Engineering Artifact: A production-oriented FastAPI `Dockerfile` and `.dockerignore`, with documented build/run, volume, and network workflows.

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why Docker exists and what problem a reproducible image solves.
* Explain a container as an isolated process (namespaces + cgroups), not a small VM.
* Distinguish an image (immutable template) from a container (runtime instance).
* Explain image layers, the container writable layer, and build-cache ordering.
* Write a Dockerfile and explain `FROM`/`WORKDIR`/`COPY`/`RUN`/`CMD`/`ENTRYPOINT`.
* Distinguish `docker build` (make the artifact) from `docker run` (start an instance).
* Separate compute lifecycle from data lifecycle using volumes.
* Connect containers over an explicit network using service DNS names, not `localhost`.
* Apply immutable replacement instead of mutating a running production container.
* Answer beginner, intermediate, and senior Docker interview questions in English.

The engineering artifact is a FastAPI `Dockerfile` and `.dockerignore`, not application code.

---

# Why This Matters

Day22 established "build once, deploy many": the artifact tested by the pipeline must be the exact
artifact deployed. Day23 explains the Docker image that serves as that immutable deployable
artifact.

The production problem: the same source code behaves differently when the Python version,
operating-system libraries, dependency versions, working directory, environment variables, or
startup command differ. Docker packages the application and its user-space runtime into one
repeatable build-and-delivery unit.

```text
Same source, different environments -> "works on my machine" failures.
Docker image -> the app + its runtime, built once, run the same everywhere.
```

Why a backend engineer should care:

```text
Reliability -> the image you tested is the image you run (Day22 integrity chain).
Reproducibility -> the runtime is captured in a versioned Dockerfile, not tribal knowledge.
Scalability -> one image spawns many replaceable containers.
Security -> a narrow build context and runtime secrets keep credentials out of the image.
Roadmap -> Day24 (Compose) and later deployment/Kubernetes run these images.
```

---

# Roadmap Position

```text
Day22: GitHub Actions Advanced (build once, verify, deploy the same digest)
        |
        v
Day23: Docker Fundamentals (WHAT that immutable image is, and how to run it)
        |
        v
Day24: Docker Compose (run multiple containers together)
        |
        v
Deployment / Kubernetes / Production AI Backend
```

Day22 promoted an immutable image digest without explaining the image itself. Day23 fills that
gap: the Dockerfile, the layers, the container, its storage, and its network.

---

# Lesson Map

```text
Why Docker
  -> Container = isolated process (namespaces + cgroups)
  -> Image vs Container
  -> Layers + writable layer + build cache order
  -> Dockerfile (FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT)
  -> Build vs Run
  -> Volume (data lifecycle)
  -> Network (service DNS, not localhost)
  -> Immutable replacement
```

---

# Estimated Study Time

```text
Reading: 110-140 minutes
Exercises: 70-100 minutes
Hands-on Dockerfile authoring: 70-100 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Core Mental Model

```text
Dockerfile
    |
    | docker build
    v
Image = immutable, read-only, distributable layers
    |
    | docker run + runtime configuration
    v
Container = isolated process + shared host kernel
            + namespaces + cgroups
            + private writable layer
            + explicit network membership
    |
    +--> Volume / external service = persistent state
```

One-line mappings:

```text
Dockerfile      = build specification (Infrastructure as Code)
Image           = immutable, distributable artifact
Container       = replaceable runtime instance (isolated process)
Image layer     = build/cache unit (read-only, shared)
Writable layer  = per-container runtime state (ephemeral)
Volume          = data lifecycle, independent of the container
Network         = explicit reachability via service DNS names
```

---

# Main Concepts

## Concept 1: Why Docker Exists

### Tech Lead Question

The tests pass on your laptop. Why might the same source code still fail on another machine?

### Student Thinking

The code is the same, but the environment around it — Python version, OS libraries, dependency
versions — is not.

### Student Answer

The same source can behave differently when Python versions, OS libraries, dependency versions,
the working directory, environment variables, or the startup command differ.

### Tech Lead Review

Exactly. Docker packages the application and its user-space runtime into one repeatable build and
delivery unit. This continues Day22 directly: CI builds and verifies an image once; later
environments deploy that same immutable image identity.

### Engineering Thinking

The image freezes the runtime, so "works on my machine" becomes "works as the image."

### Production Example

A FastAPI service that needs `python:3.12` and specific system libraries ships as one image that
runs identically in CI, staging, and production.

### Framework Connection

The image built and verified by the Day22 pipeline is the exact artifact deployed — no rebuild
per environment.

### Exercise

Name three environment differences an image removes.

## Concept 2: Container Mental Model

### Tech Lead Question

Is a container a small virtual machine?

### Student Thinking

It feels VM-like because it is "isolated," but it starts too fast to boot an OS.

### Student Answer

> "docker container是一个环境隔离的进程。不具备独立操作系统和内核，最核心的区别就是虚拟机有独立
> 操作系统和内核。"

(A container is an environment-isolated process; it has no independent OS or kernel — the core
difference from a VM is that a VM has its own OS and kernel.)

### Tech Lead Review

Correct. A container is a process running through the host kernel with isolated views and
resource controls.

```text
Linux namespaces  -> isolate what a process can SEE: processes, filesystem mounts,
                     network interfaces, hostname, and related views.
cgroups           -> control HOW MUCH CPU and memory the workload may consume.
Shared host kernel-> containers share the host kernel; a VM normally has a guest OS and kernel.
```

Trade-off: containers start quickly with lower overhead, but sharing a kernel gives a generally
weaker isolation boundary than a full VM.

### Engineering Thinking

To the host, a containerized FastAPI process is just a process — isolated by namespaces, bounded
by cgroups.

### Production Example

An unbounded container can consume all host memory and starve other containers; cgroup limits
prevent one workload from taking down the host.

### Framework Connection

A model or embedding service with a memory leak can exhaust the host without resource controls.

### Exercise

True/false: every container has its own kernel; different Python versions require different
kernels.

## Concept 3: Image vs Container

### Tech Lead Question

What is the relationship between an image and a container?

### Student Thinking

It resembles something from Python — a template and its instances.

### Student Answer

> "我觉得image与container类似python中类对象与实例对象的关系。"

(Image is to container as a Python class is to an instance.)

### Tech Lead Review

A useful analogy, with one wording fix (see Misconception 1):

```text
Image     = immutable, read-only, distributable TEMPLATE.
Container = one runtime INSTANCE created from an image.
```

* One image can create multiple containers.
* Rebuilding an image does NOT update already-running containers.
* Production changes create a new image and replace containers — never mutate a running
  container by hand.

### Engineering Thinking

The image is the class; a container is an instance. `docker run` creates a container, not another
image.

### Production Example

Editing a live production container is not a release: the change lives only in that container's
writable layer, is not auditable, and cannot be reproduced or rolled back.

### Framework Connection

Updating a FastAPI service means building a new image and replacing the container, not editing the
running one.

### Exercise

True/false: an image rebuild auto-upgrades running containers; editing a container changes the
image.

## Concept 4: Image Layers and the Writable Layer

### Tech Lead Question

Why not repackage the whole image on every build?

### Student Thinking

Rebuilding everything wastes resources; there must be reuse.

### Student Answer

> "如果每次重新打包整个镜象消耗资源。container里包含image layer 与writable layer。image layer为
> 基础环境，每次只用修改writable layer就可以了。"

(Repacking the whole image wastes resources; a container has image layers and a writable layer.)

### Tech Lead Review

Right about layers, with one correction (see Misconception 3): build cache reuses immutable image
layers during `docker build`; the writable layer belongs to a runtime container after
`docker run`.

```text
Image layers   -> created during `docker build`; read-only, cacheable, shared between containers.
Writable layer -> created per container at runtime; runtime file changes go here only.
Build cache    -> invalidated from the first changed instruction/input onward.
```

Because cache invalidates from the first change onward, put stable, low-frequency instructions
before frequently changing application code:

```text
Recommended dependency-cache order:
  copy dependency manifest -> install dependencies -> copy application code
```

### Engineering Thinking

Multiple containers share read-only image layers; each gets its own writable layer instead of
copying the whole image.

### Production Example

If `requirements.txt` is unchanged, the dependency-install layer is reused from cache, so only the
application-copy layer rebuilds.

### Framework Connection

A cache-aware Dockerfile ordering reduces CI build time (Day22).

### Exercise

True/false: unchanged requirements reuse the dependency cache; frequently changing app code should
be copied first.

## Concept 5: Dockerfile

### Tech Lead Question

Why can Docker not just scan your imports and figure out how to build the image?

### Student Thinking

Docker does not know the intended Python version, the needed OS packages, or how to start the app.

### Student Answer

> "dockerfile里进行layer分层，变化频率高的步骤放后面，变化频率低的步骤放前面。减少CI/CD时间...
> docker是不知道需要什么python环境的...也不知道需要启动什么命令。dockerfile的步骤相当于人提供给
> docker的执行步骤计划。"

### Tech Lead Review

Correct. A Dockerfile is a declarative build specification and an Infrastructure-as-Code artifact.
Docker cannot reliably infer the Python version, CPU/GPU dependency variant, version pins,
production-only files, or startup command from source imports.

Key instructions:

```text
FROM        -> choose the base runtime image (e.g. python:3.12-slim, not `latest`).
WORKDIR     -> set the working directory inside the image/container.
COPY        -> copy explicit build inputs.
RUN         -> execute a BUILD-TIME command and contribute to image state.
CMD/ENTRYPOINT -> define the default RUNTIME process via image metadata.
```

```text
RUN            = build time.
CMD/ENTRYPOINT = runtime configuration.
```

### Engineering Thinking

The Dockerfile is the human-authored execution plan Docker follows; it is versioned, reviewable,
and reproducible (IaC).

### Production Example

`python:3.12-slim` constrains the base to the Python 3.12 slim version LINE — more controlled than
an unqualified `latest` — but it is still a MUTABLE tag, not an immutable identity:

```text
python:3.12-slim               = a constrained version line (controlled, but the tag can move)
python:3.12-slim@sha256:<digest> = a fixed image content (stronger build reproducibility)
```

Digest pinning improves reproducibility and supply-chain determinism (consistent with Day22's
immutable-digest principle), but a digest does not auto-receive new security fixes, so update it
deliberately. Use a real, verified digest; never invent one.

### Framework Connection

A FastAPI image declares its base, dependency install, app copy, and Uvicorn startup command
explicitly.

### Exercise

True/false: `RUN pip install` happens at runtime; `CMD` defines the default process.

## Concept 6: Build vs Run Lifecycle

### Tech Lead Question

After a successful `docker build`, is the FastAPI service running?

### Student Thinking

Build produced an image, but nothing has started a process yet.

### Student Answer

> "docker build创建image docker run运行了个container...现在没有运行container，没有container
> runtime，只有启动一个容器以后才会通过指令自动启动服务。"

### Tech Lead Review

Correct — build and run are separate.

```text
docker build -> reads the Dockerfile, runs build instructions, reuses/creates image layers,
                and produces an IMAGE artifact. It does NOT start the service.
docker run   -> locates the image, creates a container, adds a writable layer, configures
                namespace/cgroup isolation and runtime settings, then starts the process from
                CMD/ENTRYPOINT (unless overridden).
```

The writable layer stores runtime filesystem changes; it does not execute the startup command
(see Misconception 6). Build and runtime are separate so one verified image creates many
containers with different environment variables, port mappings, resource limits, and networks.

Host port mapping and the port the app listens on inside the container are distinct concerns.

### Engineering Thinking

One image, many containers: runtime configuration (env, ports, limits, network) is applied at
`docker run`, not baked into the writable layer.

### Production Example

The same image runs as a container on port 8000 in staging and behind a different published host
port in production.

### Framework Connection

`docker run -p 8080:8000` maps host 8080 to the container's 8000 where Uvicorn listens.

### Exercise

True/false: a successful build starts FastAPI; the startup process comes from `CMD`/`ENTRYPOINT`.

## Concept 7: Volume and State

### Tech Lead Question

Where should a PostgreSQL container keep its database files?

### Student Thinking

Not everything should persist, or resources fill up; but real data must survive container
removal.

### Student Answer

> "volume与container writable layer的区别是一个是永久保存，一个是临时的变化空间。当删除container
> 以后，临时变化空间也就消失了。"

### Tech Lead Review

Correct. The writable layer is tied to the container lifecycle; a volume has an independent
lifecycle and survives ordinary container replacement/removal by default.

```text
Writable layer -> ephemeral runtime files (logs, temp); gone when the container is removed.
Volume         -> persistent state, independent lifecycle; survives container replacement.
```

Database files, user uploads, and vector indexes must NOT depend on the writable layer.
PostgreSQL and a vector database can run as containerized processes while their data lives in
volumes or external managed storage.

Core principle:

```text
Separate compute lifecycle from data lifecycle; keep application containers replaceable and
preferably stateless.
```

Note (Misconception 9): the writable layer CAN store files while the container exists — but
important state must not rely on it.

### Engineering Thinking

Make the app container disposable; put durable state in a volume or external service so replacing
the container never loses data.

### Production Example

Removing and recreating a PostgreSQL container keeps its data because the data lives in a named
volume, not the writable layer.

### Framework Connection

A RAG backend persists documents, embeddings, metadata, and vector indexes outside replaceable
application containers.

### Exercise

True/false: removing a container removes its named volume by default; important DB data belongs in
the writable layer.

## Concept 8: Docker Network

### Tech Lead Question

Inside the FastAPI container, does `localhost:5432` reach the PostgreSQL container?

### Student Thinking

Each container is isolated, so `localhost` might not mean what I expect.

### Student Answer

> "因为每一个container都是独立的隔离运行空间...container network应该解决了container之间互相连接。"

### Tech Lead Review

Right idea, with the precise model (see Misconceptions 10 and 11): each container has its own
network namespace, so `localhost` refers to the current container, not another one.

```text
localhost (in FastAPI container) -> the FastAPI container itself, NOT PostgreSQL.
Shared user-defined network      -> containers on it can reach each other.
Service DNS name (postgres:5432) -> stable; prefer it over container IPs, which change on recreate.
```

Network reachability comes from network namespaces, routing, and network membership — separate
from filesystem/writable-layer isolation. Follow least-access design: not every service needs
direct database access.

### Engineering Thinking

Connect containers on an explicit network by service DNS name; treat network membership as an
access-control decision.

### Production Example

FastAPI reaches PostgreSQL as `postgres:5432` on a shared network; Redis is on the same network,
but a public-facing worker that does not need the database is not attached to it.

### Framework Connection

FastAPI connects to PostgreSQL/Redis/vector services through network DNS names, never `localhost`.

### Exercise

Why does `localhost` fail to reach another container, and what should you use instead?

---

# Common Misconceptions

```text
Image "generates images"
❌ An image can repeatedly generate images.
✅ Dockerfile/build inputs create an image; `docker run` creates a container (not another image).
Why: the class/instance analogy is right, but the produced object was misstated.
How to remember: Dockerfile -> build -> Image -> run -> Container.
```

```text
Rebuild upgrades running containers
❌ Changing an image updates already-running containers.
✅ New containers use the new image; already-running containers keep their original image.
How to remember: containers do not auto-upgrade; replace them.
```

```text
Build cache vs writable layer
❌ Rebuild optimization happens by modifying the container writable layer.
✅ Build cache reuses immutable image layers during build; the writable layer is per-container runtime.
How to remember: ask "build time or runtime?"
```

```text
Shared image storage
❌ Identical services copy the full image each time.
✅ Containers share read-only image layers; each gets its own writable layer.
How to remember: layers are shared; writable layers are private.
```

```text
Dockerfile purpose vs IaC
❌ A Dockerfile is not for defining a repeatable image because its value is IaC.
✅ Both are compatible: it is a version-controlled IaC artifact whose job is declaring a reproducible build.
How to remember: IaC is the category; a reproducible image is the concrete output.
```

```text
Startup vs writable layer
❌ The writable layer performs container startup.
✅ The runtime starts the command from image metadata (CMD/ENTRYPOINT); the writable layer only holds runtime file changes.
How to remember: writable layer = files, not the process launcher.
```

```text
docker run vs the app command
❌ Because `docker run` starts the container, the command does not come from CMD/ENTRYPOINT.
✅ `docker run` requests start; Docker then runs the image's ENTRYPOINT/CMD as the main process unless overridden.
How to remember: run = request; CMD/ENTRYPOINT = what runs.
```

```text
Ports live in the writable layer
❌ Variable ports are stored in the writable layer.
✅ Ports, env vars, resource limits, and networks are runtime configuration, not writable-layer files.
How to remember: runtime config != file state.
```

```text
Writable layer "cannot" store data
❌ The writable layer cannot store data.
✅ It can store files while the container exists, but important state must not rely on it (its lifecycle is the container's).
How to remember: it can hold data; it must not own durable data.
```

```text
Network isolation = filesystem isolation
❌ You cannot reach another container because writable layers are separate (and memory could leak).
✅ Reachability comes from network namespaces, routing, and network membership; writable layers isolate files.
How to remember: network reachability and filesystem isolation are different mechanisms.
```

```text
Containers "cannot" talk to each other
❌ Containers cannot access each other.
✅ Reachability depends on network configuration; on a shared network they can, and `localhost` always means the current container.
How to remember: join a network + use service DNS.
```

```text
Smaller image = faster app
❌ A smaller image runs the application faster.
✅ Smaller images usually improve transfer/deploy/scan/scale-out time, not application execution speed.
How to remember: optimize for the smallest secure, sufficient runtime — not an arbitrary byte count.
```

---

# Engineering Trade-offs

```text
Container vs Virtual Machine
Fast start, low overhead, shared kernel  vs  stronger isolation with a full guest OS/kernel.

Writable layer vs Volume / external storage
Convenient ephemeral runtime files  vs  durable, independent-lifecycle persistent state.

Cache-friendly Dockerfile order vs simplicity
Faster incremental builds (deps before code)  vs  a slightly more verbose Dockerfile.

Smaller image vs sufficient runtime
Faster transfer/deploy/scan  vs  the risk of removing libraries the app actually needs.
Optimize for smallest SECURE and SUFFICIENT, not smallest bytes.

Bundle an AI model in the image vs external model storage
Immutable, self-contained deploy  vs  independent model updates and smaller images.
Record the trade-off; there is no universal answer.

Broad network membership vs least access
Simple connectivity  vs  smaller attack surface (not every service needs the database).
```

---

# Hands-on Exercises

The engineering artifact is a `Dockerfile` and `.dockerignore`.

## Exercise 1: Container vs VM (true/false)

Question: mark each true or false.

Think First: does a container boot its own kernel?

Starter Artifact:

```text
A. The host sees a containerized FastAPI as a process.
B. Every container has its own kernel.
C. Different Python versions require different kernels.
D. An unlimited container cannot affect others.
```

Expected Output:

```text
A true; B false; C false; D false (an unbounded container can exhaust host memory and starve others).
```

Follow-up Question: which mechanism bounds container memory?

## Exercise 2: Image vs Container (true/false)

Question: mark each true or false.

Think First: do running containers auto-upgrade?

Starter Artifact:

```text
A. Rebuilding an image auto-upgrades running containers.
B. One image creates multiple containers sharing layers.
C. Editing a container changes the image.
D. Editing production containers is a good release method.
```

Expected Output:

```text
A false (run new, stop old); B true; C false; D false (no traceability or rollback).
```

Follow-up Question: what is the correct release flow instead of editing a container?

## Exercise 3: Layers / Cache (true/false)

Question: mark each true or false.

Think First: build time or runtime?

Starter Artifact:

```text
A. Unchanged requirements can reuse the dependency cache.
B. Editing container files modifies the image.
C. Identical services copy the full image.
D. Frequently changing app code should be copied first.
```

Expected Output:

```text
A true; B false (writable layer only); C false (shared read-only layers); D false (copy code last).
```

Follow-up Question: why does copying code last improve cache reuse?

## Exercise 4: Dockerfile (true/false)

Question: mark each true or false.

Think First: is the instruction build time or runtime?

Starter Artifact:

```text
A. `RUN pip install` happens at runtime.
B. `CMD` defines the default process.
C. A Dockerfile cannot define a repeatable image (it is only IaC).
D. Blindly `COPY . .` minimizes image size.
```

Expected Output:

```text
A false (build time); B true; C false (IaC AND reproducible image); D false (pulls in junk/secrets).
```

Follow-up Question: what can Docker NOT infer from your imports?

## Exercise 5: Build vs Run (true/false)

Question: mark each true or false.

Think First: does building start a process?

Starter Artifact:

```text
A. `docker build` starts FastAPI.
B. One image can start multiple containers.
C. The startup process comes from CMD/ENTRYPOINT.
D. Containers from one image can have different writable layers.
```

Expected Output:

```text
A false; B true; C true; D true.
```

Follow-up Question: where is the published host port configured — build or run?

## Exercise 6: Volume (true/false)

Question: mark each true or false.

Think First: what survives container removal?

Starter Artifact:

```text
A. Removing a container removes its named volume by default.
B. PostgreSQL should persist data outside its writable layer.
C. Important user/database data belongs in the writable layer.
D. FastAPI should normally be stateless.
```

Expected Output:

```text
A false (explicit volume removal can, but not by default); B true; C false; D true.
```

Follow-up Question: what is the core principle about compute vs data lifecycle?

## Exercise 7: RAG Architecture Design (Design Judgment)

Question: place FastAPI, Redis, PostgreSQL, and a vector database into containers, storage, and
network.

Think First: what is replaceable, what is durable, and how do services find each other?

Student Answer (preserved):

> "当前RAG服务应该包含Fast API、redis、postgresql、Vector Database...postgresql、Vector Database
> 生成的数据应放在Volume。FastAPI通过container network连接PostgreSQL。因为localhost是container里面
> 的本地地址...连接方式通过域名的方式进行连接...再通过run运行一个container，进行测试，测试通过，
> 再停掉删除之前的container，进行替换。"

Expected Output:

```text
FastAPI, Redis, PostgreSQL, vector DB -> separate containers.
PostgreSQL data + vector indexes/metadata -> volumes or external managed storage.
FastAPI -> PostgreSQL over an explicit network via a service DNS name (not localhost).
FastAPI -> stateless where practical; inject secrets at runtime.
Update flow -> change inputs, build a new image, start + health-check the new container,
               switch traffic, then remove the old container.
```

Follow-up Question: why start and validate the new container before removing the old one?

## Exercise 8: Production Interview — Modifying a Running Container

Question: why is entering a running production container to edit code or install packages a bad
release method?

Expected Output (student-derived):

```text
The change lives only in that container's writable layer, disappears on the next container, is
not reproducible or auditable, and breaks rollback. Correct flow: update version-controlled
inputs -> build a new immutable image -> test/scan -> start a new container -> health check ->
switch traffic -> remove the old container.
```

Follow-up Question: which properties (reproducibility, audit, rollback) does the manual edit
break?

## Exercise 9: Image Optimization (true/false)

Question: mark each true or false.

Think First: what could a careless build context leak?

Starter Artifact:

```text
A. Blindly `COPY . .` is fine.
B. Use a `.dockerignore` to exclude unnecessary/sensitive files.
C. A smaller image always means better performance.
D. Build for the minimum sufficient runtime.
```

Expected Output:

```text
A false (may include .env/secrets/logs/caches); B true; C false; D true.
```

Follow-up Question: when might bundling a large AI model in the image still be the right call?

## Exercise 10: Write a Minimal FastAPI Dockerfile (Reusable Artifact)

Question: write the minimal Dockerfile for a FastAPI service.

Think First: what is the cache-friendly order?

Student Answer (preserved):

> "最少应该包含From python的base layer，以及copy依赖，run安装依赖，copy项目代码，以及开启服务的
> 命令CMD。"

Expected Output:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Explanation: `0.0.0.0` lets the service listen on the container's network interfaces, not loopback
only. A fuller production version is in `examples/docker/fastapi/` (non-root user, health check,
`.dockerignore`).

Follow-up Question: why `--host 0.0.0.0` instead of `127.0.0.1`?

---

# Relevant Framework Connections

Only the technologies genuinely used are connected: FastAPI, Docker, and GitHub Actions (Playwright
only in passing).

## FastAPI

```text
Package a FastAPI service: Python slim base + dependency layer + app layer + Uvicorn command.
Listen on 0.0.0.0 in the container.
Keep API containers stateless; inject configuration/secrets at runtime.
Connect to PostgreSQL/Redis/vector services by network DNS name, not localhost.
Build and replace the image/container when code changes.
```

## Docker

```text
Dockerfile, build cache, image layers, the runtime writable layer, volumes, networks, health
checks, runtime configuration, and immutable replacement were taught directly.
```

## GitHub Actions

```text
The Day22 quality gate passes before the Docker build.
Cache-aware Dockerfile ordering reduces CI time.
Build once, verify the image, and deploy the same immutable identity — no rebuild per environment.
```

## Playwright

```text
Only in passing: short-lived isolated CI workloads can run in disposable containers. No forced
detailed mapping.
```

---

# AI Backend Connections

```text
RAG architecture with separate FastAPI, Redis, PostgreSQL, and vector database services.
Persist documents, embeddings, metadata, and vector indexes OUTSIDE replaceable app containers.
AI model/runtime dependencies can make images large: distinguish required runtime content from
notebooks, training data, local caches, and secrets.
GPU/CPU dependency variants cannot be inferred from imports; Dockerfile inputs must express intent.
A model/embedding service with a memory leak can exhaust the host without cgroup limits.
CI builds and tests the AI backend image; production promotes the same verified immutable artifact.
```

Production implication: keep the AI application container stateless and replaceable; let vectors,
metadata, and databases live in volumes or managed services, and control container resources.

---

# English Interview

## Key Vocabulary

* image, container, layer, writable layer
* namespaces, cgroups, host kernel
* Dockerfile, build context, `.dockerignore`
* `FROM`, `WORKDIR`, `COPY`, `RUN`, `CMD`, `ENTRYPOINT`
* build vs run, volume, named volume, network, service DNS
* immutable image, replaceable container, rollback

## What is a Docker container?

A Docker container is an isolated process that runs through the host operating system kernel. It
has isolated filesystem, process, and network views, and it can be constrained with cgroups.
Unlike a typical virtual machine, it does not boot its own guest kernel.

## What is the difference between an image and a container?

An image is an immutable, distributable template made of read-only layers. A container is one
runtime instance of that image with its own writable layer and runtime configuration. Rebuilding
an image does not update containers that are already running.

## What is the difference between `docker build` and `docker run`?

`docker build` executes Dockerfile instructions and produces an immutable image. `docker run`
creates a container from that image, applies runtime isolation and configuration, and starts the
image's default process unless it is overridden.

## Why should we avoid modifying a running Docker container directly in production?

Because the changes affect only that container's writable layer, not the original image. They are
not reproducible or auditable and make rollback difficult. The correct approach is to update
version-controlled inputs, build and verify a new immutable image, start a new container, run
health checks, switch traffic, and then remove the old container.

## Why does `localhost` not reach another container?

Each container has its own network namespace, so `localhost` refers to the current container.
Services on a shared Docker network should communicate through stable service DNS names instead of
fixed container IP addresses.

---

# Mental Model Summary

```text
Dockerfile      = build specification (IaC)
Image           = immutable, read-only, distributable layers
Container       = isolated process + shared kernel + namespaces + cgroups + writable layer + network
Image layer     = build/cache unit (read-only, shared)
Writable layer  = per-container runtime state (ephemeral)
RUN             = build time; CMD/ENTRYPOINT = default runtime process
docker build    = make the artifact; docker run = create and start an instance
Volume          = persistent state, independent lifecycle
localhost       = the current container; use explicit networks + service DNS names
Immutable ops   = rebuild, verify, replace, keep a rollback path
```

---

# Today's Takeaway

Docker turns an app plus its runtime into an immutable image, then runs replaceable containers with
explicit storage and networking.

* Most important mental model: Dockerfile -> build -> Image -> run -> Container; volume/external =
  state.
* Most important production risk: mutating a running container instead of rebuilding — no audit, no
  rollback.
* Most important trade-off: smallest secure and sufficient runtime, not smallest bytes.
* Most important framework connection: the image built and verified in CI is the exact one deployed.
* Most important AI backend connection: keep app containers stateless; persist vectors/metadata/DB
  outside them.
* Most important interview answer: a container is an isolated process sharing the host kernel, not a
  VM.

The most important engineering sentence:

```text
Build the immutable image once; run replaceable containers; keep durable state in volumes and
reach services by network DNS, never localhost.
```

---

# Before Next Lesson Checklist

Before Day24 (Docker Compose), confirm you can answer these without looking at the notes:

- [ ] Why does the same source fail across environments, and how does an image fix it?
- [ ] Why is a container an isolated process, not a small VM (namespaces vs cgroups)?
- [ ] What is the difference between an image and a container?
- [ ] What is the difference between an image layer and the writable layer?
- [ ] Why put dependency install before copying application code?
- [ ] What do `FROM`, `WORKDIR`, `COPY`, `RUN`, and `CMD`/`ENTRYPOINT` do?
- [ ] Why is `docker build` separate from `docker run`?
- [ ] Why must durable state live in a volume, not the writable layer?
- [ ] Why does `localhost` not reach another container, and what do you use instead?
- [ ] Why rebuild and replace instead of editing a running production container?
