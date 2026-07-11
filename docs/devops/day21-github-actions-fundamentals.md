# Lesson 21 — GitHub Actions Fundamentals

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 4-5 hours

Prerequisite: Day20 — CI/CD Foundations

Previous Lesson: Day20 — CI/CD Foundations

Next Lesson: Day22 — GitHub Actions Advanced

Engineering Artifact: GitHub Actions workflow YAML

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why a repository defines its own workflow as code.
* Explain the GitHub Actions execution model from event to result.
* Compare GitHub-hosted and self-hosted runners and defend the trade-off.
* Design a multi-job workflow based on runner lifecycle, parallelism, and failure isolation.
* Implement a basic FastAPI CI workflow in YAML.
* Distinguish `on`, `runs-on`, `run`, `uses`, and `with` precisely.
* Distinguish secrets from environment variables and inject them safely.
* Explain self-hosted runner security risks and why control is not automatically safety.
* Pin actions appropriately (major tag vs full commit SHA) for supply-chain safety.
* Diagnose common GitHub Actions misconceptions in an interview.
* Connect GitHub Actions to FastAPI CI and to AI backend GPU and evaluation workloads.
* Answer beginner, intermediate, and senior interview questions in English.

The engineering artifact for this lesson is a GitHub Actions workflow (YAML), not Python.

---

# Why This Matters

Day20 established the principles: CI is a trusted quality process, a pipeline fails fast, a
quality gate controls risk, and workflow should be code. Day21 implements those principles with
a real tool: GitHub Actions.

The production problem: a team cannot rely on "please run the tests before you push." That is
unrepeatable and invisible. The workflow must be defined in the repository, run automatically on
the right events, and block bad changes.

```text
Principle (Day20)          ->  Implementation (Day21)
Trusted quality process    ->  a workflow that runs on every PR
Fail fast / fast feedback  ->  ordered steps and jobs on a runner
Quality gate               ->  required checks (Ruff, pytest) before build
Workflow as Code           ->  .github/workflows/*.yml, versioned and reviewed
```

Why a backend engineer should care:

```text
Reliability -> automated checks catch defects no person catches every time.
Cost        -> triggers decide when workflows run, controlling runner minutes.
Security    -> secrets and self-hosted runners keep sensitive work protected.
DX          -> fast feedback on a PR keeps the team moving.
Roadmap     -> this is the foundation for Day22 (advanced), Docker, and deployment.
```

---

# Roadmap Position

```text
Day20: CI/CD Foundations (principles)
        |
        v
Day21: GitHub Actions Fundamentals (implement the pipeline as code)
        |
        v
Day22: GitHub Actions Advanced (matrix, cache, reusable, deploy)
        |
        v
Docker / Deployment / Kubernetes
        |
        v
Production AI Backend
```

Day21 sits here because you must be able to express a pipeline as code before you can make it
advanced (Day22) or deploy containers with it (Day23+).

---

# Lesson Map

```text
Event
  -> Trigger (on)
  -> Workflow
  -> GitHub Scheduler
  -> Runner (runs-on)
  -> Job (one runner execution context)
  -> Workspace (checkout)
  -> Step (uses / run / with)
  -> Quality Gate
  -> Build
  -> Deploy
```

---

# Core Mental Model

Understand this model before any YAML syntax:

```text
Git Event
    |
    v
Trigger (`on`)          -> WHEN the workflow runs
    |
    v
Workflow                -> the process, defined as code
    |
    v
GitHub Scheduler        -> schedules the run
    |
    v
Runner (`runs-on`)      -> the machine that executes
    |
    v
Job = One Runner Execution Context -> isolated per job
                        (fresh & ephemeral on GitHub-hosted; may persist on self-hosted)
    |
    v
Workspace (`actions/checkout`)  -> the repo code is downloaded here
    |
    v
Step
    |-- `uses` = Reusable Action
    `-- `run`  = Shell Command
    |
    v
Quality Gate
    |
    v
Build
    |
    v
Deploy
```

One-line mappings to memorize:

```text
Workflow = Process as Code
Trigger  = Event Entry
Runner   = Execution Machine
Job      = One Runner Execution Context
Step     = Concrete Task
uses     = Reusable Action
run      = Shell Command
with     = Action Parameters
```

---

# Main Concepts

## Concept 1: Workflow as Code

### Tech Lead Question

Why must each repository define its own workflow file, instead of GitHub just "knowing" how to
test your project?

### Student Thinking

Maybe GitHub could detect the language and test automatically? But every project builds and
tests differently.

### Student Answer

"Because every repository has its own process, GitHub cannot guess it. The workflow is our
process, so it should live in our repo."

### Tech Lead Review

Correct. A workflow is the team's engineering process expressed as code. GitHub executes what
you define; it does not invent your process.

Because the workflow is code, it is:

```text
Versioned    -> changes are tracked in Git.
Reviewable   -> pipeline changes go through Pull Requests.
Auditable    -> you can see who changed the process and why.
Reversible   -> you can roll back a bad pipeline change.
```

`.github/workflows/` is Convention over Configuration: GitHub looks in that fixed directory, so
you do not configure where workflows live — you follow the convention.

### Engineering Thinking

A process that lives in a UI is invisible and unrepeatable. Workflow as Code makes the process a
first-class, reviewed artifact — the same idea as Everything as Code from Day20.

### Production Example

A change to the CI pipeline (say, adding a security scan) is a PR reviewed like any code, so a
risky pipeline edit is caught before it ships.

### Framework Connection

For a FastAPI service, the workflow file encodes exactly how the API is linted, tested, and
built — reproducibly, for every contributor.

## Concept 2: The Execution Model — Workflow vs Runner

### Tech Lead Question

When a workflow runs, what describes the work, and what actually does the work?

### Student Thinking

The YAML file describes steps. Something must run them — maybe a server?

### Student Answer

"The workflow describes what should happen; a runner is the machine that executes it."

### Tech Lead Review

Exactly. Description and execution are separated.

```text
Git Event -> Trigger -> Workflow -> GitHub Scheduler -> Runner -> Job -> Step -> Result
```

```text
Workflow = what should happen (description).
Runner   = the infrastructure that executes it.
```

### Engineering Thinking

Separating description from execution means the same workflow can run on different runners
(Linux, Windows, GPU, self-hosted). The process is portable; only the execution machine changes.

### Production Example

A general CI job runs on a GitHub-hosted Ubuntu runner, while a GPU evaluation job in the same
workflow runs on a self-hosted GPU runner — same workflow, different execution.

### Framework Connection

GitHub Actions is the scheduler + runner system; your FastAPI CI is the workflow it executes.

## Concept 3: Trigger (`on`) — Event-Driven Execution

### Tech Lead Question

Should every workflow run on every repository event?

### Student Thinking

Running everything on every event guarantees nothing is missed, but that sounds wasteful.

### Student Answer

"No. A trigger decides when a workflow is worth running, so we do not run everything for every
event."

### Tech Lead Review

Correct. GitHub Actions is event-driven. The trigger (`on`) determines when a workflow runs.

```text
on:
  push:
    branches: [main]
  pull_request:
```

`on` controls:

```text
Cost           -> fewer unnecessary runs = fewer runner minutes.
Runner usage   -> capacity is not wasted.
Feedback time  -> relevant runs finish faster.
Developer experience -> noise is reduced.
```

Important: `on` defines the trigger. It does NOT define the operating system.

### Engineering Thinking

Event-driven design means work happens in response to meaningful events (a push, a PR, a
schedule), not continuously. This is the same efficiency idea as async from Day13: do work when
it matters.

### Production Example

Running the full test suite on every PR and on push to `main`, but running an expensive nightly
model evaluation only on a `schedule`, controls cost while keeping quality.

### Framework Connection

A FastAPI CI workflow triggers on `pull_request` (validate before merge) and `push` to `main`
(validate the integrated result).

## Concept 4: Runner — GitHub-hosted vs Self-hosted

### Tech Lead Question

GitHub gives you free hosted runners. Why would a team ever run its own?

### Student Thinking

Hosted is easier. Maybe self-hosted is just faster or cheaper at scale?

### Student Answer

"Maybe for speed?"

### Tech Lead Review

Speed is not the main reason — control is.

```text
GitHub-hosted Runner:
- general, stateless, public CI work
- fast setup, low operational burden
- standardized environment
- limited network and hardware control

Self-hosted Runner:
- internal network access
- custom hardware, GPU, enterprise infrastructure
- greater security control over sensitive data
- higher operational responsibility (you maintain it)
```

The main difference is control, not simply speed.

### Engineering Thinking

Choose based on requirements: public, general CI → hosted. Internal networks, sensitive data, or
GPU → self-hosted. There is no universally best option; it is context-dependent.

Security note: self-hosted gives more control, but control is not the same as safety. A
self-hosted runner can persist state, is exposed to untrusted fork-PR code, and sits inside your
network, so a compromise has a large internal blast radius. It must be secured deliberately
(ephemeral, isolated, least privilege, no secrets for fork PRs).

### Production Example

A prompt regression evaluation that must access an internal model server and a GPU runs on a
self-hosted GPU runner inside the company network; the general lint/test job runs on a hosted
runner.

### Framework Connection

AI backend GPU evaluation and internal deployment use self-hosted runners; standard FastAPI
lint/test uses hosted runners.

## Concept 5: Job — One Runner Execution Context

### Tech Lead Question

Should you put every stage (lint, test, build, deploy) in a single job?

### Student Thinking

One job is simpler and everything shares state. Why split it?

### Student Answer

"At first I wanted everything in one job, but jobs can run in parallel and isolate failures."

### Tech Lead Review

Right. A job is assigned to one runner execution context.

```text
One Job = One Runner Execution Context.
```

Be precise about "fresh," because it depends on the runner type:

```text
GitHub-hosted runner -> a fresh, ephemeral VM per job; no state carries over.
Self-hosted runner   -> the SAME machine may persist state (files, caches,
                        credentials) between jobs, unless it is explicitly made
                        ephemeral or isolated.
```

So "one fresh runner" is accurate for GitHub-hosted runners, but on self-hosted
runners freshness is a configuration choice, not a guarantee.

Jobs enable:

```text
Parallelism         -> independent jobs run at the same time.
Failure isolation   -> one job failing does not corrupt another.
Different OS         -> jobs can target different operating systems.
Different runner types -> hosted for CI, self-hosted GPU for evaluation.
```

Divide jobs by execution environment and dependency, not by business labels.

Note: on GitHub-hosted runners each job starts fresh, so jobs do NOT share a filesystem by
default; passing data between jobs needs artifacts (Day22). On self-hosted runners a shared
filesystem may leak between jobs unless the runner is ephemeral or isolated.

### Engineering Thinking

Job boundaries are about the runtime environment and dependencies, not cosmetic grouping. Ask:
does this stage need a different machine, or can it fail independently?

### Production Example

Job `quality` (lint + test on hosted) and job `gpu-eval` (model evaluation on self-hosted GPU)
run in parallel; a build job depends on `quality` passing.

### Framework Connection

An AI backend workflow: a hosted `quality` job and a self-hosted `gpu-eval` job, with `build`
depending on `quality`.

## Concept 6: Step — `run`, `uses`, and `with`

### Tech Lead Question

Inside a job, what is the difference between running a shell command and using a prebuilt action?

### Student Thinking

Some steps look like shell (`pytest`), others reference `actions/checkout`. Are they the same?

### Student Answer

"No — one runs a command, the other reuses something GitHub provides."

### Tech Lead Review

Correct. Steps execute sequentially inside one job and share that job's workspace and runner.

```text
run  = execute a shell command on the current runner
       (e.g. `python --version`, `pip install`, `ruff check .`, `pytest`)

uses = call a reusable GitHub Action
       (e.g. `actions/checkout@v4`, `actions/setup-python@v5`)

with = pass parameters to an action (mental model: function arguments)
```

```text
uses: actions/setup-python@v5
with:
  python-version: "3.12"
```

`uses` represents reusable capability and standardization; `run` is your own command; `with`
supplies the action's arguments.

Version pinning matters for `uses`:

```text
actions/checkout@v4      -> a MOVABLE major-version tag. Maintainers can repoint v4
                            to new commits, so you get updates but not immutability.
actions/checkout@<sha>   -> a full 40-character commit SHA. Immutable: the exact code
                            is frozen, giving the strongest supply-chain guarantee.
```

`@v4` trades immutability for easy updates; a full commit SHA trades easy updates for
supply-chain immutability. High-security pipelines pin third-party actions to a SHA.

### Engineering Thinking

Prefer a maintained action (`uses`) for standard, reusable capability (checkout, language setup)
and `run` for your project-specific commands. Reuse reduces bugs and standardizes environments.
Pin third-party actions to an explicit version (major tag at minimum, commit SHA for stronger
supply-chain immutability), and do not blindly trust unknown Marketplace actions.

### Production Example

`uses: actions/setup-python@v5 with python-version "3.12"` standardizes the interpreter, then
`run: pytest` executes your project's tests.

### Framework Connection

FastAPI CI uses `actions/checkout` and `actions/setup-python` (via `uses`/`with`) and `run` for
`pip install`, `ruff check .`, and `pytest`.

## Concept 7: Checkout — Initializing the Workspace

### Tech Lead Question

A fresh runner is a clean machine. Where does your repository code come from?

### Student Thinking

I assumed the code was already there. But a fresh runner would be empty.

### Student Answer

"The runner does not have the code yet; a step must download it first."

### Tech Lead Review

Exactly. A fresh runner does not contain repository code. `actions/checkout` creates the
workspace by downloading the target commit.

```text
Fresh Runner (empty)
      |
   actions/checkout
      |
      v
Workspace with the repo at the target commit
      |
      v
install deps -> lint -> test
```

Workspace initialization precedes dependency installation, linting, and testing. Checkout is
almost always the first step.

### Engineering Thinking

Every job starts clean (reproducibility), so every job that touches code must check it out first.
"Fresh and reproducible" is the whole point of a runner.

### Framework Connection

Without checkout, `ruff check .` and `pytest` would have no FastAPI code to run against.

## Concept 8: Secrets and Environment Variables

### Tech Lead Question

Your CI needs an OpenAI API key and a log level. Do you write both directly into the YAML?

### Student Thinking

Hardcoding is easy, but the workflow file is committed to the repo, so the key would be exposed.

### Student Answer

"The API key must be a secret; the log level can be a plain environment variable."

### Tech Lead Review

Correct. Distinguish the two, because they solve different problems.

```text
Environment variable (`env`):
  plain key-value config, visible in logs, for NON-sensitive values (LOG_LEVEL, APP_ENV).

Secret (`${{ secrets.NAME }}`):
  encrypted at rest, masked in logs, for SENSITIVE values (API keys, tokens, DB URLs).
```

Environment variables have a scope, and narrower scope overrides broader:

```text
env at workflow level -> available to every job and step
env at job level      -> available to that job's steps
env at step level     -> available only to that one step
```

Safe injection:

```yaml
env:
  APP_ENV: production                 # non-sensitive, workflow-wide
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - name: Run evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}   # injected from secrets, step scope
        run: python evaluate.py
```

Rules:

```text
Reference secrets with `${{ secrets.NAME }}`; never hardcode them.
Never echo or print a secret; secrets are masked in logs, do not defeat that.
Fork pull requests from untrusted contributors do NOT receive repository secrets by default.
Scope secrets to the step or job that needs them (least privilege).
```

### Engineering Thinking

Separate configuration from credentials: config (env) can be visible and versioned; credentials
(secrets) must be encrypted, masked, and least-privilege. A leaked key is a production incident,
so secrets never live in code or logs.

### Production Example

A FastAPI CI sets `APP_ENV` as an env var and injects `DATABASE_URL` and `OPENAI_API_KEY` from
secrets only in the integration-test step that needs them.

### Framework Connection

AI backend workflows inject `OPENAI_API_KEY`, model endpoints, and database URLs as secrets,
while `LOG_LEVEL` and feature flags are plain env vars. On self-hosted GPU runners, keeping these
as secrets (not host environment values) limits exposure if the host is compromised.

## Concept 9: Quality Gate and the FastAPI CI Flow

### Tech Lead Question

If Ruff (lint) fails, should the Docker build still run?

### Student Thinking

The build might still succeed even if lint fails, so maybe run it anyway?

### Student Answer

"No — if Ruff is part of our quality gate, a lint failure should block the build."

### Tech Lead Review

Correct. Ruff, pytest, review, and security checks form a quality gate. Docker build should begin
only after the required quality checks pass. Build is an artifact stage, not a substitute for
quality validation.

The FastAPI CI flow:

```text
Trigger
  -> Checkout
  -> Setup Python
  -> Install dependencies
  -> Ruff
  -> pytest
  -> Quality Gate (all required checks pass)
  -> Docker Build
  -> Deploy
```

### Engineering Thinking

Building an image from code that fails lint or tests wastes compute and can ship a known-bad
artifact. The gate enforces order: validate, then build, then deploy.

### Production Example

A PR whose `ruff check .` fails stops before Docker build; no image is produced for broken code.

### Framework Connection

The Docker build stage (Day23) consumes the validated FastAPI code only after the gate passes.

---

# Common Misconceptions

```text
`on`
❌ `on` selects the operating system the workflow runs on.
✅ `on` defines the trigger (the event). `runs-on` selects the runner/OS.
Why beginners think this: "on Ubuntu" sounds like it belongs to `on`.
How to remember: on = when (event); runs-on = where (machine).
```

```text
`run`
❌ `run` defines when the workflow runs (a trigger).
✅ `run` executes a shell command on the current runner.
Why beginners think this: the word "run" sounds like "run the workflow."
How to remember: run = a command in a step; on = the trigger.
```

```text
`uses`
❌ `uses` runs a shell command.
✅ `uses` calls a reusable GitHub Action; `run` runs shell commands.
Why beginners think this: both appear as steps.
How to remember: uses = reusable Action; run = raw shell.
```

```text
Job design
❌ Put every stage in one job for simplicity.
✅ Split jobs by runner lifecycle, parallelism, dependency, and failure isolation.
Why beginners think this: one job shares state and looks simpler.
How to remember: one job = one runner execution context; split jobs by environment/dependency. (Fresh & ephemeral on hosted; self-hosted may persist unless isolated.)
```

```text
Secrets vs environment variables
❌ A secret is just an environment variable.
✅ A secret is encrypted at rest and masked in logs; an env var is plain, visible config.
Why beginners think this: both are injected as `KEY=value` into a step.
How to remember: secrets = credentials (masked); env = config (visible).
```

```text
Quality gate vs build
❌ Docker build can run even if Ruff fails.
✅ When Ruff is part of the quality gate, a Ruff failure must block the build.
Why beginners think this: a build can technically still succeed.
How to remember: validate first, build second — build is not validation.
```

---

# Engineering Trade-offs

```text
GitHub-hosted Runner vs Self-hosted Runner

GitHub-hosted:
- lower operational burden, fast setup, standardized environment
- fresh, ephemeral VM per job (no state carried over)
- limited network and hardware control
Self-hosted:
- internal network access, custom hardware/GPU
- more configuration control
- higher operational AND security responsibility
Choose self-hosted when you need internal access, GPU, or data control; otherwise hosted.
```

More control does NOT automatically mean safer. Self-hosted runners add real security risks:

```text
Persistent state    -> the machine may carry files, caches, or credentials between jobs.
Untrusted PRs       -> a fork pull request can run attacker-controlled code on YOUR hardware.
Credential leakage  -> long-lived host credentials can be exfiltrated by a malicious job.
Host compromise     -> a compromised runner exposes the underlying host machine.
Internal blast radius -> the runner lives inside your network, so a breach can reach internal
                       systems (databases, model servers, secrets stores).
```

Mitigations: use ephemeral/isolated runners, never expose secrets to fork PRs, apply least
privilege, and segment the runner's network. Treat self-hosted security as an ongoing
responsibility, not a benefit you get for free.

```text
One Job vs Multiple Jobs

One Job:
- simplest, shared workspace, sequential
- no parallelism, one failure can block everything, one environment only
Multiple Jobs:
- parallel, isolated failures, mixed OS/runner types
- needs artifacts to share data, slightly more complex
Choose multiple jobs when stages need different environments or independent failure/parallelism.
```

```text
Build Before vs After the Quality Gate

Build after gate (recommended):
- never build known-bad code, saves compute, ships only validated artifacts
Build anytime:
- faster image availability, but risks shipping broken artifacts
A Tech Lead reviews: does the build depend on required checks passing?
```

```text
`uses` (reusable Action) vs `run` (raw shell)

uses:
- standardized, maintained, less to get wrong
- supply-chain trust needed; pin versions
run:
- full control, project-specific commands
- you maintain correctness
Prefer maintained actions for standard capability; use run for your own commands.
```

---

# Hands-on Exercises

The engineering artifact here is YAML, not Python.

## Exercise 1: Why Repository-Defined Workflows

Question:

Why does GitHub require each repository to define its own workflow?

Think First:

Could GitHub guess how your project builds and tests?

Starter Artifact:

```text
A new repository with no `.github/workflows/` directory.
```

Expected Output:

A short explanation: the workflow is the team's process; GitHub executes what you define, it does
not invent your process.

Explanation:

Workflow as Code makes the process versioned, reviewable, and auditable.

Follow-up Question:

Why does the workflow live in a fixed directory (`.github/workflows/`)?

## Exercise 2: Workflow vs Runner

Question:

Explain the difference between a workflow and a runner.

Think First:

Which one describes work, and which one performs it?

Starter Artifact:

```text
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
```

Expected Output:

The workflow (the YAML) describes what should happen; the runner (`ubuntu-latest`) is the machine
that executes it.

Explanation:

Description and execution are separated, so the same workflow can run on different runners.

Follow-up Question:

Which line selects the runner?

## Exercise 3: Hosted vs Self-hosted Runner (Design Judgment)

Question:

For each task, choose a hosted or self-hosted runner and justify it.

Think First:

What does each task need — general compute, or internal access / GPU?

Starter Artifact:

```text
Task A: run Ruff and pytest on a public FastAPI repo.
Task B: run a GPU model evaluation against an internal model server.
```

Expected Output:

```text
Task A -> GitHub-hosted (general, stateless, standardized).
Task B -> Self-hosted GPU (internal network + GPU + data control).
```

Explanation:

The deciding factor is control (network, hardware, data), not speed.

Follow-up Question:

What operational cost does self-hosted add?

## Exercise 4: Design a Multi-Job AI Backend Workflow (Design Judgment)

Question:

Design the jobs (not full YAML) for an AI backend CI that runs general checks and a GPU
evaluation, then builds.

Think First:

Which stages need different runners? What must pass before build?

Starter Artifact:

```text
Stages: lint, test, gpu-eval, docker-build
```

Expected Output:

```text
job quality  (hosted): lint + test
job gpu-eval (self-hosted GPU): model evaluation
job build    (hosted): needs: quality   # build only after the gate
```

Explanation:

Jobs are divided by execution environment and dependency; build depends on the quality gate.

Follow-up Question:

Why can `gpu-eval` run in parallel with `quality` but `build` cannot start until `quality`
passes?

## Exercise 5: Write a Basic FastAPI CI Workflow (Reusable Artifact)

Question:

Write the minimal Workflow/Trigger/Job/Runner/Step YAML for FastAPI CI.

Think First:

What is the first step on a fresh runner?

Starter Artifact:

```yaml
name: FastAPI CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      # add steps here
```

Expected Output:

```yaml
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run Ruff
        run: ruff check .
      - name: Run tests
        run: pytest
```

Explanation:

Checkout initializes the workspace; setup-python standardizes the interpreter (via `with`);
install/Ruff/pytest are `run` commands forming the quality gate.

Follow-up Question:

Where would a Docker build step belong, and what must precede it?

A complete example workflow is included in the repository at
`examples/github-actions/fastapi-ci.example.yml` (example only; it is intentionally not placed
under `.github/workflows/` in this documentation repository).

---

# Relevant Framework Connections

Only the technologies genuinely relevant to this lesson are used: GitHub Actions, FastAPI, and
Docker.

## GitHub Actions

```text
Where the concept appears: the whole lesson — workflows, triggers, runners, jobs, steps.
State/lifecycle: each job runs in one runner execution context (fresh & ephemeral on hosted; possibly persistent on self-hosted); steps share the job workspace.
Share: reusable actions via `uses`.
Isolate: each job runs on its own runner.
Failure: a step's non-zero exit fails the job; jobs can fail independently.
Review: pin action versions, justify runner choice, make job dependencies explicit.
```

## FastAPI

```text
Where the concept appears: the CI target — lint and test the API on every PR.
State/lifecycle: checkout -> setup-python -> install -> ruff -> pytest.
Failure: a failing test or lint blocks the gate before build.
Review: are required checks required, and does build depend on them?
```

## Docker

```text
Where the concept appears: the build stage after the quality gate (expanded in Day23).
Isolate: the build produces an image only from validated code.
Failure: never build from code that failed the gate.
Review: build depends on `quality`; no image for broken code.
```

---

# AI Backend Connections

GitHub Actions is how AI backend teams automate quality and evaluation, not just app tests.

```text
GPU Self-hosted Runners:
  Model evaluation and heavy inference run on self-hosted GPU runners inside the network.

Scheduled Model Evaluation:
  An `on: schedule` trigger runs nightly evaluation without spending runner minutes on every push.

Prompt Regression Testing:
  A workflow runs prompt evaluations on PRs that touch prompts; a regression blocks the gate.

Internal Network Access:
  Self-hosted runners reach internal model servers and databases that hosted runners cannot.

Secure Deployment & Secrets:
  Secrets (e.g. `${{ secrets.OPENAI_API_KEY }}`) are referenced, never hardcoded; sensitive work
  stays on enterprise infrastructure.

Quality Gate Before Model Release:
  Evaluation and safety checks act as a gate before a new prompt or model version ships.
```

Production implication: an AI backend CI often has a hosted `quality` job (lint/test) plus a
self-hosted `gpu-eval` job, with prompt-regression results gating a model or prompt release.

---

# English Interview

## Key Vocabulary

* workflow, trigger, runner, job, step
* GitHub-hosted / self-hosted runner
* action, `uses`, `run`, `with`, `runs-on`, `on`
* quality gate, checkout, workspace
* event-driven, artifact

## Useful Expressions

* "The workflow describes the process; the runner executes it."
* "GitHub Actions is event-driven: the trigger decides when it runs."
* "One job runs in one runner execution context (fresh on hosted; self-hosted may persist)."
* "Build should only start after the required quality checks pass."

## Beginner Question

Q: What is a GitHub Actions workflow?

Strong Answer: A workflow is the team's engineering process defined as code in
`.github/workflows/`. It runs on triggers, executes jobs on runners, and each job runs ordered
steps. Because it is code, it is versioned, reviewable, and auditable.

## Intermediate Question

Q: What is the difference between a GitHub-hosted and a self-hosted runner?

Strong Answer: Both execute jobs, but the difference is control. Hosted runners are general,
stateless, standardized, and low-maintenance but limited in network and hardware. Self-hosted
runners give internal network access, custom hardware or GPU, and data control, at the cost of
operational responsibility. I choose self-hosted when I need internal access, GPU, or data
control; otherwise hosted.

## Senior Question

Q: How would you design CI jobs for an AI backend that needs general checks and GPU evaluation?

Strong Answer: I split by execution environment and dependency. A hosted `quality` job runs lint
and tests; a self-hosted GPU `gpu-eval` job runs model evaluation; they run in parallel. A
`build` job depends on `quality` so no image is built from code that fails the gate. Sensitive
evaluation stays on self-hosted infrastructure with secrets referenced safely, and expensive
evaluation can move to a schedule to control cost.

## Common Weak Answer

"GitHub Actions runs my tests automatically when I push." — true but shallow: it misses workflow
as code, triggers controlling cost, runner choice, job isolation, and the quality gate.

## Strong Answer

"GitHub Actions implements CI/CD as code: triggers make it event-driven, runners execute jobs,
jobs isolate environments and failures, steps use reusable actions or shell commands, and a
quality gate blocks the build until required checks pass — all versioned and reviewable."

---

# Mental Model Summary

```text
Workflow = Process as Code
Trigger  = Event Entry (`on` = when)
Runner   = Execution Machine (`runs-on` = where)
Job      = One Runner Execution Context (fresh & ephemeral on hosted; may persist on self-hosted)
Step     = Concrete Task
uses     = Reusable GitHub Action
run      = Shell Command
with     = Action Parameters
Checkout = Initialize the workspace on a fresh runner
Quality Gate = Required checks must pass before build
```

---

# Today's Takeaway

GitHub Actions turns the Day20 CI/CD principles into a workflow defined as code.

```text
Ask always:
When does this run (trigger)? Where does it run (runner)?
Is each job a properly isolated fresh environment?
Does the build wait for the quality gate?
```

* Most important mental model: Event -> Trigger -> Workflow -> Runner -> Job -> Step -> Result.
* Most important production risk: building or deploying code that failed the quality gate.
* Most important trade-off: GitHub-hosted vs self-hosted runner (control, not speed).
* Most important framework connection: FastAPI CI as checkout -> setup -> install -> ruff ->
  pytest -> gate -> build.
* Most important AI backend connection: self-hosted GPU runners and scheduled evaluation gating a
  model/prompt release.
* Most important interview answer: a workflow is process-as-code; a job is one runner execution context;
  `on` is when, `runs-on` is where.

The most important engineering sentence:

```text
A workflow describes the process as code; a runner executes it; the quality gate decides what is
allowed to build and deploy.
```

---

# Before Next Lesson Checklist

Before Day22, confirm you can answer these without looking at the notes:

- [ ] Can I draw the Event -> Trigger -> Workflow -> Runner -> Job -> Step -> Result model?
- [ ] Why must the workflow live in the repository as code?
- [ ] What production cost does the trigger (`on`) control?
- [ ] What is the difference between `on` and `runs-on`?
- [ ] What is the difference between `run`, `uses`, and `with`?
- [ ] Why is checkout the first step on a fresh runner?
- [ ] Why is "one job = one runner execution context" (fresh on hosted, maybe persistent on self-hosted), and when do I split jobs?
- [ ] Why must the build wait for the quality gate?
- [ ] When would I choose a self-hosted (GPU) runner for an AI backend?
- [ ] Can I explain a GitHub Actions workflow in English in an interview?
