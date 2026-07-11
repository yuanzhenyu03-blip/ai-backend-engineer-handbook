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
