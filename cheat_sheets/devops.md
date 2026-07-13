# DevOps Cheat Sheet

## Purpose

One-page DevOps review sheet for AI Backend Engineer preparation.

Focused on CI/CD foundations: pipeline, quality gate, delivery, and Everything as Code.

---

## Core Ideas

| Concept | Meaning |
|---------|---------|
| CI | Trusted, repeatable quality process (not just "running tests") |
| Pipeline | Standard workflow of ordered stages |
| Quality Gate | Risk control: only passing changes move forward |
| CD | Continuous Delivery (always ready to release) and Continuous Deployment (auto-release after gates) |
| Workflow as Code | Pipeline defined in the repo, versioned and reviewed |
| Everything as Code | Code, tests, workflow, infra, config, prompts all versioned |

---

## Why "I Tested Locally" Is Not Enough

```text
Local test = one machine + one environment + one person + one moment.
Trusted quality = the same automated checks on every change, visible to all.
```

---

## Pipeline

```text
Lint -> Test -> Build -> Security Scan -> Package
```

- Standard Workflow: same stages every time.
- Stage Dependency: later stages need earlier ones to pass.
- Fail Fast: stop at the first failing stage.
- Fast Feedback: tell the developer quickly what broke.

Run cheap, likely-to-fail checks first.

---

## Quality Gate

```text
Protects: Main + Production + Team + Users
```

Only changes that pass required checks may merge. A gate turns "please don't merge broken code"
into "you cannot."

---

## CD — Delivery vs Deployment

```text
Continuous Delivery   = Always ready to release (a production-ready candidate is built).
                        Production release may need manual approval.
Continuous Deployment = Actually releasing automatically once every quality gate passes.
```

Shared qualities: Repeatability + Consistency + Reliability + Scalability.
Do not treat Delivery and Deployment as identical.

---

## Workflow as Code / Everything as Code

```text
Consistency + Version Control + Reviewability + Auditability
```

If it is code, it is versioned, reviewed, and reproducible: code, tests, workflow,
infrastructure, config, and prompts.

---

## Full Delivery Lifecycle (Day15-Day20)

```text
Idea -> Issue -> Project -> Branch -> Commit -> Pull Request
     -> CI -> Pipeline -> Quality Gate -> Merge -> CD -> Production
```

---

## Day21 GitHub Actions Fundamentals

Core idea:

```text
A workflow describes the process as code; a runner executes it.
```

Execution model:

```text
Git Event -> Trigger (on) -> Workflow -> Scheduler -> Runner (runs-on)
          -> Job (one fresh runner) -> Workspace (checkout) -> Step (uses/run) -> Result
```

Key mappings:

```text
Workflow = Process as Code
Trigger  = Event Entry      (on = WHEN)
Runner   = Execution Machine (runs-on = WHERE)
Job      = One Runner Execution Context
Step     = Concrete Task
uses     = Reusable GitHub Action
run      = Shell Command
with     = Action Parameters
```

| Keyword | Meaning |
|---------|---------|
| `on` | The trigger (event). NOT the operating system. |
| `runs-on` | Selects the runner/OS for a job. |
| `run` | Runs a shell command on the runner. |
| `uses` | Calls a reusable Action (e.g. `actions/checkout@v4`). |
| `with` | Passes parameters to an Action (like function args). |
| `needs` | Makes a job depend on another (e.g. build `needs: quality`). |

Runner choice (control, not speed):

```text
GitHub-hosted -> general, fresh & ephemeral per job, standardized; limited network/hardware.
Self-hosted   -> internal network, GPU, custom hardware; you operate AND secure it.
```

Self-hosted security: control != safety. Risks: persistent state, untrusted fork PRs running on
your hardware, credential leakage, host compromise, internal blast radius. Mitigate with
ephemeral/isolated runners, no secrets for fork PRs, least privilege, network segmentation.

Rules:

- `.github/workflows/` is Convention over Configuration.
- Checkout is the first step (a fresh runner is empty).
- One job = one runner execution context; fresh & ephemeral on hosted, self-hosted may persist.
- Split jobs by environment, dependency, parallelism, isolation.
- Build only after the quality gate (Ruff/pytest) passes.
- Secrets vs env: secrets are encrypted + masked (credentials); env is plain config; env scope is
  workflow/job/step (narrower overrides broader).
- Reference secrets safely: `${{ secrets.NAME }}` — never hardcode or echo them.
- Pin actions: `@v4` is a movable major tag; a full commit SHA is immutable (stronger supply chain).

FastAPI CI flow:

```text
Trigger -> Checkout -> Setup Python -> Install -> Ruff -> pytest -> Quality Gate -> Build -> Deploy
```

Common mistakes:

```text
❌ on = OS         ✅ on = trigger; runs-on = OS
❌ run = trigger   ✅ run = shell command
❌ uses = shell    ✅ uses = reusable Action
❌ one big job     ✅ split by runner/dependency
❌ build after lint fails  ✅ gate blocks the build
```

---

## Day22 GitHub Actions Advanced

Core mappings:

```text
Matrix             = One job template expanded by variables (still N isolated jobs)
fail-fast          = Stop early OR collect complete independent results
Cache              = Re-creatable acceleration data
Artifact           = Formal workflow output
Composite Action   = Reusable steps
Reusable Workflow  = Reusable jobs / workflow
needs              = Dependency graph (who finishes first)
if                 = Execution decision (should this run)
continue-on-error  = Failure does not block the flow
Environment        = Protected deployment boundary
Concurrency        = Serialized environment mutation
Immutable Digest   = Exact deployable identity
Deployment         = Controlled promotion of a verified artifact
```

Matrix:

```text
2 python × 2 os = 4 isolated jobs (no shared filesystem/deps).
Wall-clock time = wait; Runner-minutes = sum of all jobs.
Matrix does NOT reduce executions; it removes duplicated YAML + config drift.
```

fail-fast: decide by whether remaining combinations still have independent value.
`false` = full compatibility (public SDK). `true` = one early signal is enough (costly probe).

Cache vs Artifact:

| | Cache | Artifact |
|--|-------|----------|
| Meaning | Re-creatable acceleration | This run's official output |
| Examples | pip, Playwright Chromium | coverage.xml, app.tar.gz, evaluation-results.json |
| On miss | Slower, still correct | N/A |
| Key | `${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}` | name + path |

Never use a cache as the official store for a result.

Composite Action (steps) vs Reusable Workflow (jobs): if it needs its own `jobs`/`runs-on`/`needs`, it is a Reusable Workflow.

Conditions (three separate mechanisms):

```text
needs             = who must finish first (+ access to needs.<job>.result)
if                = when to run: branch/tag/event/input/result (success/failure/always/cancelled)
continue-on-error = executed and failed WITHOUT blocking (≠ skipped)
notify:  needs: [test, build]   if: always()
```

Deployment pipeline:

```text
Build once -> push to registry -> capture immutable digest -> deploy the SAME digest.
What we tested = what we deployed. Prefer my-api@sha256:... over my-api:latest.
environment: production   -> required reviewers + prod secrets + protection + history.
concurrency: { group: production, cancel-in-progress: false }  -> serialize, do not interrupt.
Approval = accountable, risk-qualified owner (not one fixed job title).
```

Integrity chain: source tests validate source; `verify-image` pulls and runs the exact digest
(smoke test) to validate the runtime artifact; deploy promotes the same verified digest.
Upload reports even on test failure with `if: always()` + `if-no-files-found: warn`
(`always()` runs the step; it does not guarantee the files exist).

Simplified: `PR -> lint+test -> tag -> build once -> push digest -> verify digest -> scan/eval -> approval -> serial deploy -> smoke -> monitor/rollback`.

---

## Day23 Docker Fundamentals

Core mental model:

```text
Dockerfile --docker build--> Image (immutable layers) --docker run--> Container (isolated process)
                                                                        + writable layer + network
Container --> Volume / external service = persistent state
```

Key mappings:

```text
Dockerfile      = build spec (Infrastructure as Code)
Image           = immutable, read-only, distributable artifact
Container       = replaceable runtime instance (process + namespaces + cgroups + shared host kernel)
Image layer     = build/cache unit (read-only, shared)
Writable layer  = per-container runtime state (ephemeral)
Volume          = data lifecycle, independent of the container
Network         = reachability via service DNS names
```

Container vs VM: a container is an isolated process sharing the host kernel (namespaces isolate
views, cgroups limit CPU/memory); a VM boots its own guest OS + kernel.

Dockerfile instructions:

```text
FROM  = base image; constrain to a version line e.g. python:3.12-slim (not `latest`).
        A tag is mutable; pin to a digest (python:3.12-slim@sha256:...) for reproducibility.
WORKDIR = working directory
COPY  = copy explicit build inputs
RUN   = build-time command (build time)
CMD / ENTRYPOINT = default runtime process (runtime)
```

Cache order (deps before code):

```text
COPY requirements.txt .   -> RUN pip install ...   -> COPY app ./app
Cache invalidates from the first changed instruction onward; copy changing code LAST.
```

Build vs Run:

```text
docker build = make the image (does NOT start the service)
docker run   = create + start a container from CMD/ENTRYPOINT (unless overridden)
Host port vs container port are distinct (-p host:container).
```

Rules:

- Image is immutable; containers are replaceable. Rebuilding an image does not upgrade running containers.
- Never edit a running production container; rebuild -> verify -> start new -> health check -> switch traffic -> remove old.
- Durable state (DB files, uploads, vector indexes) -> volumes/external storage, never the writable layer.
- `localhost` = the current container. Reach other containers on a shared network via service DNS (`postgres:5432`), not container IPs.
- `.dockerignore` keeps `.env`, secrets, caches, tests, notebooks out of the build context.
- Smaller image helps transfer/deploy/scan, not app speed; optimize for smallest secure and sufficient runtime.
- Inject secrets at runtime; never bake them into the image. Run as a non-root user.

---

## Interview Phrases

- "CI is a trusted quality process, not just running tests."
- "A pipeline is a standard workflow of ordered stages that fails fast and gives fast feedback."
- "A quality gate is risk control that protects main, production, the team, and users."
- "Continuous Delivery keeps you always ready to release; Continuous Deployment ships automatically once gates pass."
- "Workflow as Code makes the process consistent, versioned, reviewable, and auditable."
- "Everything as Code makes the whole system reproducible."
- "A workflow describes the process as code; a runner executes it."
- "`on` is the trigger (when); `runs-on` is the runner (where)."
- "`run` is a shell command; `uses` calls a reusable Action; `with` passes its parameters."
- "One job runs in one runner execution context (fresh on hosted; self-hosted may persist); checkout is first."
- "Split jobs by runner lifecycle, dependency, parallelism, and failure isolation."
- "The build must wait for the quality gate; build is not validation."
- "Choose GitHub-hosted vs self-hosted runners for control (GPU, internal network, data), not speed — but control is not safety."
- "Secrets are encrypted and masked; environment variables are plain config; scope is workflow/job/step."
- "`@v4` is a movable tag; pin to a full commit SHA for supply-chain immutability."
- "A matrix expands one job definition into isolated jobs; it does not reduce executions."
- "Cache is re-creatable acceleration; an artifact is this run's official output."
- "Composite action = reusable steps; reusable workflow = reusable jobs."
- "`needs` orders jobs, `if` decides execution, `continue-on-error` tolerates failure — three mechanisms."
- "Build once, deploy many: deploy the immutable digest you tested, not `:latest`."
- "Serialize production with a concurrency group and `cancel-in-progress: false`."
- "A container is an isolated process sharing the host kernel, not a small virtual machine."
- "An image is immutable; a container is a replaceable runtime instance with a private writable layer."
- "`RUN` is build time; `CMD`/`ENTRYPOINT` defines the default runtime process."
- "Copy dependencies before application code so the install layer stays cached."
- "Durable state belongs in a volume or external service, never the container writable layer."
- "`localhost` means the current container; reach others by service DNS on a shared network."
- "Never edit a running production container; rebuild, verify, replace, and keep a rollback path."
