# Lesson 22 — GitHub Actions Advanced

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 5-6 hours

Prerequisite: Day21 — GitHub Actions Fundamentals

Previous Lesson: Day21 — GitHub Actions Fundamentals

Next Lesson: Day23 — Docker Fundamentals

Engineering Artifact: GitHub Actions workflow YAML (matrix, cache, artifacts, reusable workflow, deployment)

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain a matrix as one job template expanded by variables, not a resource optimization.
* Decide `fail-fast: true` vs `false` from the independent value of remaining combinations.
* Distinguish cache (re-creatable acceleration) from artifact (formal workflow output).
* Compare a composite action (reusable steps) with a reusable workflow (reusable jobs).
* Separate `needs`, `if`, and `continue-on-error` as three distinct control mechanisms.
* Design a reliable deployment pipeline: build once, deploy many, with an immutable image digest.
* Explain production Environment protection and serialized deployment concurrency.
* Implement an advanced CI/CD workflow in YAML.
* Connect these mechanisms to FastAPI, Docker, and AI backend release pipelines.
* Answer beginner, intermediate, and senior interview questions in English.

The engineering artifact for this lesson is a GitHub Actions workflow (YAML).

---

# Why This Matters

Day21 built a basic workflow: trigger, runner, job, steps, quality gate. Day22 turns that into a
production-capable pipeline that scales, reuses process, controls execution, and deploys safely.

The bridge from Day21 is one fact:

```text
Different jobs do not share a filesystem by default.
Data that must move between jobs needs an explicit transfer mechanism.
```

From a basic workflow to a production one:

```text
Basic Workflow
      |
      v
Scale Execution       -> Matrix
Reduce Repeated Work  -> Cache
Transfer Results      -> Artifacts
Reuse Process         -> Reusable Workflow
Reuse Steps           -> Composite Action
Control Execution     -> Conditions (needs / if / continue-on-error)
Deliver Safely        -> Deployment Pipeline
```

Why a backend engineer should care:

```text
Reliability -> deploy the exact artifact you tested, serialized and recoverable.
Cost        -> caches and matrix design control runner minutes.
Security    -> production Secrets and Environment protection limit blast radius.
Consistency -> reusable workflows stop organization-wide configuration drift.
Roadmap     -> this pipeline deploys the Docker images built from Day23 onward.
```

---

# Roadmap Position

```text
Day20: CI/CD Foundations (principles)
Day21: GitHub Actions Fundamentals (basic workflow as code)
        |
        v
Day22: GitHub Actions Advanced (scale, reuse, control, deploy)
        |
        v
Day23: Docker Fundamentals (the images this pipeline builds and deploys)
        |
        v
Deployment / Kubernetes / Production AI Backend
```

Day22 sits here because a real pipeline must scale testing, move results between jobs, reuse
process across repositories, and deploy a verified artifact — before containers (Day23) and
deployment targets are introduced.

---

# Lesson Map

```text
Matrix (scale)
  -> fail-fast (early stop vs full diagnosis)
  -> Cache vs Artifact (accelerate vs transfer/preserve)
  -> Composite Action vs Reusable Workflow (reuse steps vs jobs)
  -> needs / if / continue-on-error (order, decision, tolerance)
  -> Deployment Pipeline (build once, immutable digest, environment, concurrency)
```

---

# Estimated Study Time

```text
Reading: 110-140 minutes
Exercises: 70-100 minutes
Hands-on workflow authoring: 70-100 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Core Mental Model

```text
Matrix             = One job template expanded by variables
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

The single most important sentence:

```text
Build once, deploy many: what was tested must be, byte-for-byte, what is deployed.
```

---

# Main Concepts

## Concept 1: Matrix Build

### Tech Lead Question

You need to test Python 3.10, 3.11, and 3.12. You wrote three almost identical jobs. What is the
engineering problem, and what should GitHub Actions offer instead?

### Student Thinking

Three jobs work, but the YAML is duplicated. There should be a way to share the configuration.

### Student Answer

> "这种写三个 Job 的方式可以正常运行。它最大的工程问题是浪费资源，同一种 workflow 采用了三个
> job 进行工作。GitHub Actions 应该提供一种可以共享配置环境的方式。"

(Reconstruction: "Three jobs run, but duplicating them is wasteful; GitHub Actions should let me
share the configuration.")

### Tech Lead Review

The instinct — remove duplication — is right, but be precise about the benefit. A matrix is:

```text
One Job Template  +  A Set of Variables  =  Multiple Generated Jobs
```

Matrix does NOT normally reduce the number of executions. Three versions still produce three
jobs. What it removes is duplicated YAML, so environments stay aligned to one definition.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pytest
```

Multi-axis matrix multiplies combinations:

```text
2 Python versions × 2 operating systems = 4 jobs
ubuntu + 3.10, ubuntu + 3.11, windows + 3.10, windows + 3.11
```

And distinguish two kinds of time:

```text
Wall-clock time = how long the user waits
Runner time     = sum of all job execution time
```

Four 5-minute jobs may finish in ~5 minutes (if parallel capacity exists) while still consuming
~20 runner-minutes.

### Engineering Thinking

A matrix is a maintainability and consistency tool: one definition, many aligned environments. It
trades more compatibility coverage against more jobs, runner cost, and possible combinatorial
explosion (3 × 3 × 2 = 18 jobs).

### Production Example

A public SDK tests every supported Python and OS combination from one matrix, so a dropped or
broken environment is impossible to forget.

### Framework Connection

Test a FastAPI service against every supported Python version from one matrix definition.

### Exercise

Given `python-version: ["3.10","3.11"]` and `os: [ubuntu-latest, windows-latest]`, how many jobs,
and do they share installed dependencies?

## Concept 2: Matrix `fail-fast`

### Tech Lead Question

Python 3.10 failed; 3.11 is running; 3.12 is queued. Should GitHub stop the rest?

### Student Thinking

Sometimes I want to stop fast to fix quickly; sometimes I want all results together.

### Student Answer

> "尽快失败适合不同配置环境，收集完整结果适合运行相同配置环境不同运行参数的场景。"

(Reconstruction: the student first tied the decision to whether configs are "same or different.")

### Tech Lead Review

That criterion is not quite right. The real question is:

```text
After one combination fails, do the remaining combinations still have
independent diagnostic, compatibility, or release value?
        |
   +----+----+
   No        Yes
   |          |
fail-fast   collect all (fail-fast: false)
```

```text
fail-fast: true  -> one failure is enough; remaining runs are costly and add little.
fail-fast: false -> each environment is an independent commitment; you need full results.
```

```yaml
strategy:
  fail-fast: false
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
```

### Engineering Thinking

`fail-fast` trades fast termination and cost against complete compatibility and diagnosis. Decide
by the value of the remaining results, not by whether configs look similar.

### Production Example

A public SDK supporting all Python/PostgreSQL combinations uses `fail-fast: false`; a temporary,
expensive performance test seeking an early regression signal uses `fail-fast: true`.

### Framework Connection

An AI evaluation matrix across model providers uses `fail-fast: false` when each provider's result
is an independent release signal.

### Exercise

Public SDK across six Python/PostgreSQL combinations vs an expensive one-off performance probe —
which `fail-fast` for each?

## Concept 3: Cache vs Artifact

### Tech Lead Question

You need to (A) speed up repeated dependency installs and (B) move `coverage.xml` from the test
job to a report job. Same mechanism for both?

### Student Thinking

They feel different — one is about speed, one is about passing a real output.

### Student Answer

> "不应该使用同一种机制。第一个需求是加速重复工作，需求 B 是在 Job 之间传递正式输出。Cache 应该
> 解决第一个，Artifact 应该解决需求 B。"

### Tech Lead Review

Correct.

```text
Cache    = Re-creatable acceleration data
Artifact = Formal output produced by THIS workflow run
```

Decision model:

```text
Can the file be downloaded or regenerated? -> Cache candidate.
Does it represent this run's official result? -> Prefer Artifact.
```

Cache keys:

```text
OS + Dependency file hash = Cache identity
```

```yaml
- name: Cache pip downloads
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

Artifacts move formal outputs between jobs (remember: jobs do not share a filesystem):

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: coverage.xml
```

```yaml
report:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - uses: actions/download-artifact@v4
      with:
        name: coverage-report
```

A workflow must still be correct on a cache miss — only slower. Never use a cache as the official
store for a current-run result: a cache can be absent, stale, partially matched, or evicted.

### Engineering Thinking

Cache trades faster builds against the risk of stale state hiding a broken clean build. Artifact
trades auditability and cross-job delivery against upload/download time, storage cost, and
sensitive-data exposure.

### Production Example

`pip` downloads and Playwright Chromium binaries are cached; `coverage.xml`, `app.tar.gz`, and
`evaluation-results.json` are artifacts.

### Framework Connection

Cache Playwright's downloaded Chromium (reproducible, expensive dependency); store an AI
`evaluation-results.json` as an artifact (this run's official result).

### Exercise

Classify: pip cache, `coverage.xml`, `app.tar.gz`, Playwright Chromium binary,
`evaluation-results.json`.

## Concept 4: Composite Action vs Reusable Workflow

### Tech Lead Question

You keep repeating "install Python, install deps, run Ruff, run pytest." Is that a composite
action or a reusable workflow? And what about a whole `lint -> test -> build` pipeline?

### Student Thinking

Both reuse things. A sequence of steps sounds like a reusable workflow?

### Student Answer

> Initial: "复用 Step 像是 Reusable Workflow." After correction:
> "Composite Action、Reusable Workflow、Composite Action、Reusable Workflow、Composite Action."

### Tech Lead Review

The initial mapping was inverted. The distinction is the unit of reuse:

```text
Composite Action  = Reusable STEPS
Reusable Workflow = Reusable JOBS / workflow
```

| Dimension | Composite Action | Reusable Workflow |
|---|---|---|
| Reuse unit | Steps | Jobs / workflow |
| Defines `jobs` | No | Yes |
| Defines `runs-on` | No | Yes |
| Controls `needs` topology | No | Yes |
| Main use | Repeated operations | Shared pipeline policy |

A composite action owns a step sequence (install deps, run Ruff+pytest, a Docker login/push
group). It does NOT own `jobs`, `runs-on`, or dependency topology. A reusable workflow owns whole
jobs — matrix, security scan, build/deploy gates, organization-wide CI/CD standards.

### Engineering Thinking

Copy-pasted workflows drift: repositories evolve separately, and security/quality standards become
inconsistent. Composite actions trade small flexible step reuse; reusable workflows trade
centralized job-level governance (at the cost of repo autonomy and a wider blast radius when the
central definition changes).

### Production Example

A composite action standardizes "setup + lint + test" steps; a reusable workflow enforces one
`lint -> test -> build` pipeline across every service repo.

### Framework Connection

An organization ships one reusable FastAPI CI workflow so every service repo runs the same gates.

### Exercise

Classify: install Python+deps+Ruff; company-wide `lint -> test -> build`; Docker login/push steps;
matrix+security+build+approval pipeline; version-number shell steps.

## Concept 5: Conditional Jobs — `needs`, `if`, `continue-on-error`

### Tech Lead Question

Notify the team after both `test` and `build`, whether they pass or fail. Is `needs` enough?

### Student Thinking

`needs` makes the notify job wait for the others, so maybe that is all I need.

### Student Answer

> Initial: "needs 只是用于 Artifact 正常上传日志... Conditional Job 就是在出现意外情况时也能继续执行。"
> Mechanism exercise: "needs、if、if、continue-on-error、needs" — the last item was corrected to
> `needs + if: always()`.

### Tech Lead Review

These are three separate mechanisms; do not conflate them:

```text
needs             = dependency graph and ordering (who must finish first)
if                = execution decision (under what context/result)
continue-on-error = whether a failure blocks the formal flow
```

`needs` also corrected a misconception: it is not mainly for artifact transfer. It defines
dependencies and gives access to dependency results. `if` decides execution from context — branch,
tag, event, inputs, dependency result, previous step status:

```yaml
if: startsWith(github.ref, 'refs/tags/v')
```
```yaml
if: failure()
```
```yaml
if: always()
```

`continue-on-error` runs the step/job, records failure, but does not block the flow. It is not the
same as skipping:

```text
Skipped         = did not execute
Allowed failure = executed and failed without blocking
```

Notification pattern (run regardless of outcome, then inspect results):

```yaml
notify:
  needs: [test, build]
  if: always()
```
```yaml
${{ needs.test.result }}   # success | failure | cancelled | skipped
${{ needs.build.result }}
```

Failure-report pattern (allow the condition to evaluate despite a dependency failure):

```yaml
report:
  needs: test
  if: always() && needs.test.result == 'failure'
```

### Engineering Thinking

Separate the three questions: who must finish first (`needs`), should this run (`if`), and does a
failure block (`continue-on-error`). Conflating them produces pipelines that either never notify
on failure or wrongly block on tolerated failures.

### Production Example

An experimental Python 3.13 job uses `continue-on-error: true` so its failure does not block the
release; a deployment job uses `if: startsWith(github.ref, 'refs/tags/v')` so it runs only on tags.

### Framework Connection

An AI backend runs experimental model/Python compatibility checks with `continue-on-error`, while
evaluation gates use `if` on the dependency result.

### Exercise

Classify with `needs`, `if`, or `continue-on-error`: build waits for test; tag-only deploy; upload
logs after failure; experimental 3.13 may fail; notify after test and build regardless.

## Concept 6: Deployment Pipeline

### Tech Lead Question

Is "tests passed, then run `deploy.sh`" a reliable production deployment?

### Student Thinking

It deploys after tests, but a lot could still go wrong — approvals, rebuilds, overlapping runs.

### Student Answer

> Initial: "需要让其他人员评估，需要产品经理进行系统性评估。因为重新构建会消耗资源。资源抢占，
> 同时修改生产环境，导致生产环境污染。"
> Reliability exercise: "最大风险是重复 build Docker、没有 environment 审批、两个部署可以同时运行...
> concurrency 应该为 false。"

### Tech Lead Review

"Run deploy.sh" is not yet reliable. A reliable deployment is:

```text
Reliable Deployment
= Verified Artifact + Controlled Promotion + Protected Credentials
+ Concurrency Control + Observability + Recovery Plan
```

It must answer: what is deployed, who can deploy, when, can deployments overlap, what happens on
failure, and which version was deployed.

Build once, deploy many — the primary reason is integrity, not resource savings:

```text
Build once -> Test the artifact -> Approve it -> Promote the SAME artifact -> Deploy it
What we tested = what we deployed.
```

Rebuilding in the deploy job can produce a different output (changed base images, dependency
drift, env changes, system packages, non-determinism).

Docker image transfer — `docker save`/`docker load` as an artifact is technically possible, but
production uses:

```text
Build once -> Push to a container registry -> Capture the immutable image digest -> Deploy that digest
```

```text
Ordinary file output -> GitHub Artifact
Container image      -> Container Registry + immutable digest
Avoid mutable tags:  my-api:latest
Prefer the digest:   my-api@sha256:...
```

Artifacts still store digest metadata, SBOMs, scan results, evaluation reports, and manifests.

Production Environment adds protection:

```yaml
environment: production
```

It provides required reviewers, production Secrets, protection rules, deployment history, and
isolation. Approval is not a fixed job title: business timing may belong to a product owner, while
technical, infrastructure, and security risk belong to accountable engineering/platform/security
owners. The principle is accountable, risk-qualified approval.

Concurrency serializes environment mutation:

```yaml
concurrency:
  group: production
  cancel-in-progress: false
```

`concurrency` is a configuration block, not a boolean. `group: production` puts all production
deployments in one lock; `cancel-in-progress: false` queues a new deployment instead of
interrupting the active one. Blindly cancelling a production deploy risks half-applied migrations,
partially updated fleets, skipped cleanup, and a mixed-version environment.

Simplified pipeline:

```text
PR -> Lint + Test -> Merge / Version Tag -> Build image once -> Push immutable digest
   -> Security scan / evaluation -> Production approval -> Serialized deploy -> Smoke test -> Monitor / rollback
```

### Engineering Thinking

Deployment approval trades risk control and accountability against release speed; serial deployment
trades safe deterministic promotion against waiting time for newer releases. Choose deliberately.

### Production Example

A tagged release builds one image, pushes it, an owner approves the `production` environment, and
the exact digest deploys under a serialized concurrency group, then a smoke test runs.

### Framework Connection

An AI backend builds one service image, runs an evaluation gate, stores the evaluation report as an
artifact, approves in the `production` environment, and deploys the exact digest.

### Exercise

Review a workflow that builds `my-api:latest`, rebuilds in deploy, uses production Secrets directly,
has no Environment approval, and allows concurrent deploys. What do you fix?

---

# Common Misconceptions

```text
Matrix purpose
❌ Matrix mainly saves runner resources by avoiding three jobs.
✅ Matrix normally still creates N jobs; it removes duplicated YAML and prevents config drift.
Why beginners think this: matrix replaces three repeated job blocks with one.
How to remember: count the combinations — that is usually the number of generated jobs.
```

```text
Matrix environment
❌ Matrix jobs share one configuration/runner environment.
✅ Matrix shares a job DEFINITION, not a runner; each combination is an isolated job.
Why beginners think this: "shared config" sounds like a shared machine.
How to remember: files installed in one matrix job do not appear in another.
```

```text
fail-fast criterion
❌ fail-fast depends on whether the configurations are the same or different.
✅ It depends on whether the remaining combinations still have independent value.
Why beginners think this: "different environments" feels like the deciding factor.
How to remember: after one fails, would the rest change diagnosis or release decisions?
```

```text
Reusable unit
❌ A repeated sequence of steps is a Reusable Workflow.
✅ Repeated steps = Composite Action; repeated jobs/workflow = Reusable Workflow.
Why beginners think this: both "reuse" things.
How to remember: if it needs its own `jobs`, `runs-on`, or `needs`, it is a Reusable Workflow.
```

```text
needs vs artifact
❌ `needs` is mainly for downloading an artifact in a later job.
✅ `needs` defines dependency/ordering; artifacts transfer files. Different problems.
Why beginners think this: they are often used together.
How to remember: needs = who finishes first; artifact = which files move.
```

```text
Conditional execution
❌ Conditions mainly handle unexpected failures.
✅ Conditions decide execution from normal and abnormal context: event, branch, tag, inputs, result.
Why beginners think this: they first meet `if` via `if: failure()`.
How to remember: a tag-only deployment is conditional even when nothing failed.
```

```text
Production approval owner
❌ A Product Manager should perform the production evaluation.
✅ Approval ownership depends on the risk; technical/infra risk belongs to accountable engineers.
Why beginners think this: "approval" sounds like a business/PM sign-off.
How to remember: can the approver evaluate and own THIS release's specific risk?
```

```text
Artifact reuse reason
❌ Deploy reuses the artifact mainly to save rebuild resources.
✅ The primary reason is integrity: the exact tested artifact must be the deployed artifact.
Why beginners think this: rebuilding obviously costs time.
How to remember: is what we deploy byte-for-byte what we tested?
```

```text
concurrency shape
❌ `concurrency` should be set to `false`.
✅ `concurrency` is a config block; `cancel-in-progress` is the boolean decision.
Why beginners think this: they collapse the whole idea into one on/off switch.
How to remember: group = which deploys share a lock; cancel-in-progress = cancel the active one?
```

```text
Docker image delivery
❌ Ship the Docker image only as a GitHub Artifact.
✅ Use a container registry + immutable digest; artifacts hold reports, SBOMs, and digest metadata.
Why beginners think this: `docker save`/`load` makes it look like a file artifact.
How to remember: container image -> registry + digest; file output -> artifact.
```

---

# Engineering Trade-offs

```text
Matrix coverage vs cost
More environments and compatibility confidence  vs  more runner time, latency, combinatorial growth.

fail-fast vs complete diagnosis
Fast termination and lower cost  vs  complete compatibility and diagnostic information.

Cache vs clean reproducibility
Faster builds  vs  risk of stale state and hidden clean-build failures.

Artifact retention vs storage overhead
Auditability and cross-job delivery  vs  upload/download time, storage cost, sensitive-data risk.

Composite Action vs Reusable Workflow
Small flexible step reuse  vs  centralized job-level pipeline governance.

Central reusable workflow vs repository autonomy
Consistent organization standards  vs  reduced flexibility and wider blast radius of central changes.

Deployment approval vs delivery speed
Risk control and accountability  vs  slower release flow.

Serial deployment vs cancellation
Safe deterministic promotion  vs  potential waiting time for newer releases.
```

---

# Hands-on Exercises

The engineering artifact is YAML.

## Exercise 1: Matrix Expansion

Question:

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11"]
    os: [ubuntu-latest, windows-latest]
```

Think First: how many combinations, and do the jobs share installed dependencies?

Expected Output:

```text
4 jobs: ubuntu+3.10, ubuntu+3.11, windows+3.10, windows+3.11.
Each is an isolated job; no shared filesystem or dependencies. ~20 runner-minutes for four 5-min jobs.
```

Explanation: matrix shares the definition, not the environment.

Follow-up Question: what is the difference between wall-clock time and runner-minutes here?

## Exercise 2: `fail-fast` Decision

Question: choose `fail-fast` for each.

Think First: do the remaining combinations still carry independent value?

Starter Artifact:

```text
1. Public SDK officially supports six Python/PostgreSQL combinations.
2. Temporary expensive performance workflow needs only an early regression signal.
```

Expected Output:

```text
1 -> fail-fast: false   (each combination is an independent support commitment)
2 -> fail-fast: true    (one signal is enough; remaining runs are costly)
```

Follow-up Question: what question do you ask after the first combination fails?

## Exercise 3: Cache or Artifact

Question: classify each.

Think First: re-creatable acceleration, or this run's official output?

Starter Artifact:

```text
pip download cache, coverage.xml, app.tar.gz, Playwright Chromium binary, evaluation-results.json
```

Expected Output:

```text
pip -> Cache; coverage.xml -> Artifact; app.tar.gz -> Artifact;
Playwright Chromium -> Cache; evaluation-results.json -> Artifact
```

Follow-up Question: why must a workflow still be correct on a cache miss?

## Exercise 4: Composite Action or Reusable Workflow

Question: classify each.

Think First: is the reuse unit steps or whole jobs?

Starter Artifact:

```text
install Python+deps+Ruff; company-wide lint->test->build; Docker login+push steps;
matrix+security+build+approval pipeline; version-number shell steps
```

Expected Output:

```text
Composite Action; Reusable Workflow; Composite Action; Reusable Workflow; Composite Action
```

Follow-up Question: which one owns `jobs`, `runs-on`, and `needs`?

## Exercise 5: `needs`, `if`, or `continue-on-error`

Question: classify each.

Think First: order, decision, or tolerance?

Starter Artifact:

```text
build waits for test; tag-only deployment; upload logs after failure;
experimental Python 3.13 may fail; notify after test and build regardless
```

Expected Output:

```text
needs; if; if (if: failure()); continue-on-error; needs + if: always()
```

Follow-up Question: why is `needs` alone not enough for the notify job?

## Exercise 6: Deployment Reliability Review

Question: review a workflow that builds `my-api:latest`, rebuilds in deploy, uses production
Secrets directly, has no Environment approval, and permits concurrent deploys.

Think First: what breaks "what we tested = what we deployed"?

Expected Output:

```text
Deploy the immutable digest from a registry (not a rebuild, not :latest).
Protect Secrets behind the production Environment with required reviewers.
Use a production concurrency group with cancel-in-progress: false.
```

Follow-up Question: why is cancelling an in-progress production deploy dangerous?

## Exercise 7: Comprehensive Day22 Design (Design Judgment + Reusable Artifact)

Question: choose a mechanism for each requirement.

Expected Output:

```text
Python 3.10-3.12 tests      -> Matrix
Complete compatibility data -> fail-fast: false
pip acceleration            -> Cache
test reports                -> Artifact
build after formal tests    -> needs
experimental Python 3.13    -> continue-on-error
Docker delivery             -> Registry + immutable digest
tag-only deployment         -> if
approval and production keys -> environment
one production deployment   -> concurrency group (cancel-in-progress: false)
notification regardless     -> needs + if: always()
complete pipeline reuse     -> Reusable Workflow
```

A full runnable version is in `examples/github-actions/github-actions-advanced.example.yml`
(example only; not placed under `.github/workflows/` in this documentation repository).

Follow-up Question: where does the immutable digest come from, and why not `my-api:latest`?

---

# Relevant Framework Connections

Only the technologies genuinely used are connected: GitHub Actions, FastAPI, Docker, and Playwright
(cache example only).

## GitHub Actions

```text
Where it appears: matrix, fail-fast, actions/cache, upload/download-artifact, composite actions,
reusable workflows, needs, if, status functions, continue-on-error, environments, secrets,
concurrency groups, deployment.
Review: pin actions, cap matrix size, gate deploy on approval, serialize with concurrency.
```

## FastAPI

```text
Test a FastAPI service across supported Python versions via matrix; share org-level FastAPI CI via
a reusable workflow; build one deployable image and deploy the exact tested artifact.
```

## Docker

```text
Build the image once, push to a registry, promote an immutable digest, and never rebuild in deploy
or deploy a mutable :latest tag.
```

## Playwright

```text
Cache downloaded Chromium binaries — reproducible, expensive dependencies — a cache candidate. No
further Playwright connection is forced.
```

---

# AI Backend Connections

```text
Matrix across Python versions, operating systems, model providers, or evaluation datasets.
fail-fast trade-offs for expensive GPU/model evaluation.
Cache for AI libraries and reusable downloads.
Artifact for evaluation-results.json, reports, SBOMs, and deployment evidence.
Evaluation report as release-approval evidence (a quality gate before model release).
Exact AI backend image digest promotion (what was evaluated is what ships).
Prompt/model routing configuration as versioned release artifacts.
Production deployment gates for AI services; production Secrets limited to the deploy job.
Post-deployment smoke tests, monitoring, and rollback.
```

AI backend release flow:

```text
Commit -> Test -> Build image -> Run evaluation -> Save image digest + evaluation report
       -> Approval -> Deploy exact image digest -> Smoke test -> Monitor / rollback
```

Production implication: the evaluation that approves a model release must run against the exact image
digest that ships, and production Secrets must not be exposed to general CI jobs.

---

# English Interview

## Key Vocabulary

* matrix, axis, combinatorial explosion
* `fail-fast`, wall-clock time, runner-minutes
* cache, artifact, cache key, cache miss
* composite action, reusable workflow
* `needs`, `if`, `continue-on-error`, status function
* environment, required reviewers, concurrency, `cancel-in-progress`
* immutable image digest, container registry, build once deploy many

## Useful Expressions

* "A matrix is one job template expanded by variables."
* "Cache is re-creatable acceleration; an artifact is this run's official output."
* "Build once, deploy many — what we tested is what we deploy."
* "Concurrency serializes production; `cancel-in-progress: false` queues, it does not interrupt."

## Beginner Question

Q: What does a matrix build do?

Strong Answer: It expands one job definition across a set of variables (Python versions, OSes),
generating one isolated job per combination. It removes duplicated YAML and keeps environments
aligned; it does not normally reduce the number of executions.

## Intermediate Question

Q: What is the difference between a cache and an artifact?

Strong Answer: A cache is re-creatable acceleration data (dependency downloads, browser binaries)
keyed by OS and a dependency hash; a workflow must still be correct on a cache miss, only slower. An
artifact is a formal output of this run (coverage, reports, packages) transferred between jobs and
retained for audit. Never use a cache as the official store for a result.

## Senior Question

Q: How do you make a Docker deployment reliable in GitHub Actions?

Strong Answer: Build the image once, push it to a container registry, and deploy the immutable
digest — never rebuild in deploy or deploy a mutable `:latest`, so what was tested is what ships. Gate
the deploy behind a production Environment with required, risk-qualified reviewers and
production-only Secrets, and serialize with a concurrency group using `cancel-in-progress: false` so
deployments never overlap. Add smoke tests, monitoring, and a rollback path.

## Common Weak Answer

"Matrix saves resources, cache and artifacts both just store files, and I run `deploy.sh` after the
tests pass." — this misses matrix isolation, the cache-vs-artifact distinction, immutable promotion,
approvals, and concurrency.

## Strong Answer

"Advanced Actions scale with matrices, accelerate with caches, transfer official outputs as
artifacts, reuse steps via composite actions and whole pipelines via reusable workflows, control flow
with `needs`/`if`/`continue-on-error`, and deploy by promoting one immutable, approved digest under a
serialized production Environment."

---

# Mental Model Summary

```text
Matrix             = One job template expanded by variables
fail-fast          = Stop early OR collect complete independent results
Cache              = Re-creatable acceleration data
Artifact           = Formal workflow output
Composite Action   = Reusable steps
Reusable Workflow  = Reusable jobs / workflow
needs              = Dependency graph
if                 = Execution decision
continue-on-error  = Failure does not block
Environment        = Protected deployment boundary
Concurrency        = Serialized environment mutation
Immutable Digest   = Exact deployable identity
Deployment         = Controlled promotion of a verified artifact
```

---

# Today's Takeaway

Day22 turns a basic workflow into a production pipeline that scales, reuses, controls, and deploys
safely.

* Most important mental model: build once, deploy many — what was tested is what is deployed.
* Most important production risk: rebuilding or deploying a mutable tag so the deployed artifact
  differs from the tested one; overlapping production deploys.
* Most important trade-off: matrix coverage vs cost, and deployment approval/serialization vs speed.
* Most important framework connection: build one Docker image, deploy its immutable digest.
* Most important AI backend connection: the evaluation that approves a release runs against the exact
  shipped digest; production Secrets stay in the deploy job.
* Most important interview answer: cache is re-creatable acceleration; an artifact is the official
  output; a matrix expands one definition into isolated jobs.

The most important engineering sentence:

```text
Scale with matrices, transfer with artifacts, reuse with workflows, control with conditions, and
deploy one verified, immutable digest under a protected, serialized Environment.
```

---

# Before Next Lesson Checklist

Before Day23, confirm you can answer these without looking at the notes:

- [ ] Why does a matrix normally not reduce the number of executions?
- [ ] Do matrix jobs share a filesystem or installed dependencies?
- [ ] How do you decide `fail-fast: true` vs `false`?
- [ ] What is the difference between a cache and an artifact, and what happens on a cache miss?
- [ ] Composite action vs reusable workflow — what is the unit of reuse?
- [ ] How do `needs`, `if`, and `continue-on-error` differ?
- [ ] How do you notify after two jobs regardless of their outcome?
- [ ] Why "build once, deploy many," and why an immutable digest instead of `:latest`?
- [ ] What does a production Environment protect, and who should approve?
- [ ] Why serialize production with `concurrency` and `cancel-in-progress: false`?
