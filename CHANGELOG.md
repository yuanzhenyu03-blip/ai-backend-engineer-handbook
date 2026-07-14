# CHANGELOG.md

All notable changes to this repository will be documented in this file.

This project follows a practical versioning style:

- `v0.x.x` — training system under construction
- `v1.0.0` — first complete AI Backend Engineer Handbook release

---

## v0.1.41 — Day24 Review Fixes

Date: 2026-07-14

### Changed

- Removed the two placeholder secret values (an example PostgreSQL password and an example OpenAI key) from `examples/docker/compose/README.md`; the secret files are now created via interactive `read -rsp` prompts so no password or API-key value is written into the repository.
- Restructured `docs/devops/day24-docker-compose.md` to the exact LESSON_TEMPLATE_v2 16-section order: added an explicit `# Lesson Metadata` section, moved the study-time estimate into it, promoted `Learning Objectives` to a top-level section, and removed the standalone `Estimated Study Time` section (content preserved, only relocated).
- Added a production image contract to `examples/docker/compose/README.md`: `build:` + `rag-app:local` is local/teaching; a full local start needs `docker compose up --build` (or an explicit build) first; in production, `api` and `worker` should reference the same immutable, CI-built/verified image identity (preferably by digest) rather than rebuilding per environment.

### Notes

- Small-scope review fix; no lesson teaching content or classroom record was rewritten.
- No real or fake secrets remain in the repository; `<digest>` is a syntax placeholder, not a secret.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day23 lesson.

---

## v0.1.40 — Day24 Docker Compose Documentation

Date: 2026-07-14

### Added

- Added `docs/devops/day24-docker-compose.md` (LESSON_TEMPLATE_v2; first lesson under Master Prompt v3.2 with an explicit knowledge-continuity chain and a Day23->Day24 mental-model evolution).
- Added a multi-service Compose example: `examples/docker/compose/compose.yaml`, `compose.dev.yaml`, `.env.example`, and `README.md` (FastAPI API + Worker + Redis + PostgreSQL).
- Added Day24 review material to `cheat_sheets/devops.md`.
- Added Day24 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` and `examples/docker/fastapi/README.md` (replaced the Day24 future note with a link to the released lesson/example).
- Added `.secrets/` to `.gitignore` so local Compose secret files are never committed.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day24 completed.
- Updated `PROJECT_STATUS.md` to mark Day24 completed and set Next to Day25.
- Updated `TASKS.md` with completed Day24 tasks and Day25 preparation.
- Updated `CHANGELOG.md` with the Day24 repository update.

### Notes

- Day24 turns Day23's single reproducible container into a version-controlled multi-service system: why Compose exists, started != ready (`depends_on` short vs `condition: service_healthy`, healthchecks, and application retry), Project/Service/Image/Container and rebuild vs recreate, the declarative model and YAML, host ports/service DNS, network segmentation (queue vs database) for least access, volumes and `down --volumes`, environment vs secret vs governed business data, the local development workflow, base + development override, and the Compose production boundary vs Kubernetes.
- Preserved the actual classroom record: the student's Chinese and English answers (including the imperfect final synthesis and the weak English attempts) and all material misconceptions and corrections, plus the YAML-evidence-over-chat-rendering correction.
- Compose example uses the current Compose Specification (no top-level `version:`), publishes only the API host port, uses service DNS, segments networks, mounts a named `postgres_data` volume, and grants role-scoped secrets via files under a git-ignored `.secrets/` directory. No real secrets, `.env` credentials, API keys, passwords, connection strings, customer prompts, or medical data were committed.
- Validation: `docker` is not available in this environment, so the stack was NOT started; the base and development-override Compose YAML were parsed and structurally validated, and the merged model was checked. `docker compose config` / `up` should be run in a real project that provides the Day23 Dockerfile, `requirements.txt`, an `app/` package, and the local secret files.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `AGENTS.md`, `interview/docker.md`, or any Day01-Day23 lesson.

---

## v0.1.39 — Master Prompt v3.2: Curriculum Continuity & Update Standards

Date: 2026-07-13

### Changed

- Upgraded `prompts/master-prompt.md` from v3.1 to v3.2 (add-only; fully compatible with v3.1, no lesson or structure migration):
  - Added a Knowledge Continuity Requirement to the Roadmap Position section: every lesson must show Previous Knowledge -> Current Concept -> Future Production Usage, name the reused mental models and prerequisite lessons, justify its roadmap position, and identify future dependents.
  - Added a Mental Model Evolution rule to the Student Mistakes section: preserve Initial Mental Model -> Reasoning -> Correction -> Final Engineering Mental Model, not only the mistake.
  - Strengthened Relevant Framework Connections with an explicit "Avoid Forced Technology Connections" rule: connect a technology only when technically meaningful, prefer software-engineering/backend/cloud-native/AI-backend scenarios, and label non-substantive links as future connections.
  - Added `PREVIOUS_LESSON_CONNECTION`, `KNOWLEDGE_CHAIN_POSITION`, and `FUTURE_LESSON_CONNECTION` fields to the Daily Input Block so future agents can place a lesson in the full curriculum.
- Updated `prompts/README.md` to reference Master Prompt v3.2.

### Notes

- This is a repository-update-standard improvement, not a content change: no lesson documents, templates, cheat sheets, interview notes, or folder structure were modified.
- Did not modify `LESSON_TEMPLATE_v2.md`, `LESSON_TEMPLATE.md`, `AGENTS.md`, any Day01–Day23 lesson, or the Day23 completion status.
- Affects Day24+ lesson generation: future daily inputs should provide the continuity fields, and every future lesson must document the knowledge chain and mental-model evolution.

---

## v0.1.38 — Day23 Review: Docker Example & Reproducibility Corrections

Date: 2026-07-13

### Changed

- `examples/docker/fastapi/README.md`: the PostgreSQL demo now sets `-e POSTGRES_DB=app` so the created database matches the FastAPI `DATABASE_URL`, with a note that `POSTGRES_*` init variables only apply the first time the data directory is initialized (an existing `pgdata` volume will not auto-create a new database).
- `examples/docker/fastapi/README.md`: made the immutable-replacement flow self-consistent — it now builds and starts `app-v1`, builds `v2`, starts `app-v2` on a different temporary host port, health-checks `app-v2`, notes that traffic switching needs a reverse proxy/load balancer (zero downtime is Day25), and only then removes `app-v1`.
- `examples/docker/fastapi/Dockerfile`: create and `chown` `/app/data` before `USER appuser` so the non-root user can write to a mounted named volume; corrected the base-image comment to describe `python:3.12-slim` as a constrained (mutable) version line, with a digest-pin option for stronger reproducibility.
- `docs/devops/day23-docker-fundamentals.md` and `cheat_sheets/devops.md`: corrected the `python:3.12-slim` description — a constrained version line, not an immutable pin — and added the digest trade-off (reproducibility vs. deliberate security updates), consistent with Day22's immutable-digest principle.

### Notes

- Small-scope review fix; did not rewrite the Day23 chapter or extend into Day24 Docker Compose.
- No real secrets or `.env` credentials were added; `example` remains a throwaway local placeholder and no image digest was invented.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `AGENTS.md`, or the Day23 completion status in `CURRICULUM.md`/`ROADMAP.md`/`PROJECT_STATUS.md`.

---

## v0.1.37 — Day23 Docker Fundamentals Documentation

Date: 2026-07-13

### Added

- Added `docs/devops/day23-docker-fundamentals.md` (LESSON_TEMPLATE_v2).
- Added a production-oriented FastAPI Docker example: `examples/docker/fastapi/Dockerfile`, `examples/docker/fastapi/.dockerignore`, and `examples/docker/fastapi/README.md` (reproducible build/run, named-volume, and user-defined-network commands).
- Added Day23 review material to `cheat_sheets/devops.md`.
- Added Day23 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day23 Docker example.
- Updated `CURRICULUM.md` to mark Day23 completed (released lesson path + v2 template note).
- Updated `ROADMAP.md` to mark Day23 completed.
- Updated `PROJECT_STATUS.md` to mark Day23 completed and set Next to Day24.
- Updated `TASKS.md` with completed Day23 tasks and Day24 preparation.
- Updated `CHANGELOG.md` with the Day23 repository update.

### Notes

- Day23 explains the immutable Docker image behind Day22's "build once, deploy many": why Docker exists, a container as an isolated process (namespaces + cgroups, not a VM), image vs container, image layers vs the per-container writable layer with build-cache ordering, the Dockerfile (FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT as IaC), build vs run, volumes (separating compute from data lifecycle), networks (service DNS, not localhost), and immutable replacement.
- Preserved the actual classroom record, including the student's original Chinese answers and all 12 misconceptions and corrections (image "generates images", rebuild upgrading running containers, build cache vs writable layer, shared image storage, Dockerfile-vs-IaC, startup vs writable layer, `docker run` vs CMD/ENTRYPOINT, ports in the writable layer, writable layer "cannot" store data, network vs filesystem isolation, container communication default, smaller image vs performance).
- Kept Day23 within scope: Container, Image, Layer, Dockerfile, Build, Run, Volume, Network. Production extensions (non-root user, health check, `.dockerignore`, secrets at runtime, immutable replacement) were kept proportional. Docker Compose implementation is deferred to Day24; no Compose syntax was taught.
- Connected the lesson to FastAPI (slim base, stateless app, service DNS), Docker internals, and GitHub Actions (quality gate before build, cache-aware ordering, deploy the same immutable identity). Playwright was mentioned only in passing.
- The Docker example is example-only (no FastAPI app exists in this repo); it contains no real secrets or `.env` credentials, uses a pinned slim base, a non-root user, and a health check, and keeps a narrow build context via `.dockerignore`.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `LESSON_TEMPLATE.md`, `TRAINING_WORKFLOW.md`, or any Day01–Day22 lesson.

---

## v0.1.36 — Day22 Review: Correct Reusable Workflow Invocation Path

Date: 2026-07-11

### Changed

- Corrected the caller example in `examples/github-actions/reusable-fastapi-ci.example.yml`: removed the invalid `owner/repo/examples/github-actions/...@main` path and documented the real two-step usage — copy the file directly into `.github/workflows/reusable-fastapi-ci.yml` in a shared-workflow repository, then call it at the job level as `owner/repo/.github/workflows/reusable-fastapi-ci.yml@<commit-sha>` (prefer a commit SHA over `@main`).
- Synced `docs/devops/day22-github-actions-advanced.md`: the `examples/` reusable-workflow file is a teaching template, callable only after being copied into `.github/workflows/`; clarified that a composite action may live in any directory and is called via a step-level `uses`, while a reusable workflow must live directly under `.github/workflows/` (no subdirectories) and is called via a job-level `uses`.
- Updated `examples/README.md` reusable-workflow entry accordingly.
- Optional hardening: added a `trap cleanup EXIT` container cleanup to the `verify-image` smoke test in `examples/github-actions/github-actions-advanced.example.yml`.
- Updated `TASKS.md` with the review fix.

### Notes

- Small-scope fix limited to the reusable-workflow invocation path (plus one optional cleanup improvement). Did not rewrite the Day22 chapter.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, `CURRICULUM.md`, `ROADMAP.md`, `PROJECT_STATUS.md`, Day01–Day21 lessons, or the Day22 completion status.
- All example YAML still parses; no credentials are hardcoded.

---

## v0.1.35 — Day22 Review: Image Verification & Workflow Reuse Examples

Date: 2026-07-11

### Added

- Added `examples/github-actions/composite-python-quality/action.yml` — a minimal composite action (`runs.using: composite`, typed inputs, `shell` on every `run` step, no `jobs`/`runs-on`, no hardcoded secrets).
- Added `examples/github-actions/reusable-fastapi-ci.example.yml` — a minimal reusable workflow (`on: workflow_call`, typed inputs, a complete `quality` job, least-privilege permissions), with a caller `jobs.<id>.uses` example in comments.

### Changed

- Reworked `examples/github-actions/github-actions-advanced.example.yml`: the `build` job outputs the immutable image digest; a new `verify-image` job pulls and runs that exact digest and smoke-tests a health endpoint; `deploy` now depends on `build` and `verify-image` and promotes the same digest with no rebuild and no mutable `:latest`.
- Fixed test-report upload to run on failure with `if: always()` and `if-no-files-found: warn`, and switched the test command to also emit `junit.xml` (example; adjust in a real project).
- Synced `docs/devops/day22-github-actions-advanced.md`: added the integrity chain (source tests validate source; image verification validates the built runtime artifact; deployment promotes the exact verified digest), the artifact `if: always()` + `if-no-files-found` note, and references to the new composite and reusable examples.
- Updated `examples/README.md`, and added a minimal note each to `cheat_sheets/devops.md` and `interview/devops.md`.
- Updated `TASKS.md` with the Day22 review fixes.

### Notes

- Small-scope review fix; did not rewrite the Day22 chapter.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, Day01–Day21 lessons, or the Day22 completion status in `CURRICULUM.md`, `ROADMAP.md`, or `PROJECT_STATUS.md`.
- Example workflows remain example-only (not under `.github/workflows/`); all YAML parses, action versions are pinned, and no credentials are hardcoded (only `${{ secrets.* }}`).

---

## v0.1.34 — Day22 GitHub Actions Advanced Documentation

Date: 2026-07-11

### Added

- Added `docs/devops/day22-github-actions-advanced.md` (LESSON_TEMPLATE_v2).
- Added `examples/github-actions/github-actions-advanced.example.yml` (comprehensive advanced CI/CD workflow example).
- Added Day22 review material to `cheat_sheets/devops.md`.
- Added Day22 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day22 example.
- Updated `CURRICULUM.md` to mark Day22 completed (released lesson path + v2 template note).
- Updated `ROADMAP.md` to mark Day22 completed.
- Updated `PROJECT_STATUS.md` to mark Day22 completed and set Next to Day23.
- Updated `TASKS.md` with completed Day22 tasks and Day23 preparation.
- Updated `CHANGELOG.md` with the Day22 repository update.

### Notes

- Day22 extends the basic workflow into a production pipeline: matrix (one job template expanded by variables; does not reduce executions; jobs are isolated), `fail-fast` decision by remaining-combination value, cache (re-creatable acceleration) vs artifact (formal output), composite action (steps) vs reusable workflow (jobs), and the `needs`/`if`/`continue-on-error` control mechanisms.
- Deployment pipeline taught as build once / deploy many: promote one immutable image digest from a container registry (not a rebuild, not a mutable `:latest`), gated by a production Environment with risk-qualified approval and production-only Secrets, serialized with a `concurrency` group and `cancel-in-progress: false`.
- Preserved the actual classroom record, including the student's original wording and all 10 misconceptions and corrections (matrix purpose/environment, fail-fast criterion, composite vs reusable, needs vs artifact, conditional execution, approval ownership, artifact-reuse integrity, `concurrency` shape, Docker digest delivery).
- Corrected terminology in artifacts: `continue-on-error`, `cancel-in-progress`, `concurrency` block, immutable image digest.
- Connected the lesson to FastAPI CI, Docker registry/digest deployment, Playwright cache, and AI backend evaluation-gated releases with production Secrets scoped to the deploy job.
- The example workflow is intentionally NOT under `.github/workflows/` (documentation repository), is valid YAML, pins action versions, and references secrets safely (no hardcoded credentials).
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE.md`, `LESSON_TEMPLATE_v2.md`, `TRAINING_WORKFLOW.md`, or any Day01–Day21 lesson.

---

## v0.1.33 — Add Repository Update Standard (Master Prompt v3.1)

Date: 2026-07-11

### Added

- Added `prompts/master-prompt.md` — the official long-term repository update standard (Claude Code Master Prompt v3.1) for Day21 and all future lessons.

### Changed

- Updated `prompts/README.md` to document the repository update standard and how it pairs with `LESSON_TEMPLATE_v2.md`.

### Notes

- v3.1 aligns with the Day21 review corrections: runner lifecycle language (one runner execution context; hosted fresh/ephemeral vs self-hosted persistent), stronger self-hosted runner security guidance, complete Secrets and Environment Variables coverage, and GitHub Action version pinning (movable tag vs commit SHA).
- No lessons or status files changed; this only adds the standing update standard to the repository.
- Did not modify `LESSON_TEMPLATE.md`, `LESSON_TEMPLATE_v2.md`, `ROADMAP.md`, or `CURRICULUM.md`.

---

## v0.1.32 — Day21 Review Corrections

Date: 2026-07-11

### Changed

- Corrected the universal claim "One Job = One Fresh Runner" in `docs/devops/day21-github-actions-fundamentals.md`: a job is assigned to one runner execution context; GitHub-hosted runners are fresh and ephemeral per job, while self-hosted runners may persist state between jobs unless explicitly made ephemeral or isolated. Updated the core mental model, mappings, concept, misconception, framework connection, mental model summary, takeaway, and checklist consistently.
- Added a new Day21 concept "Secrets and Environment Variables" (required by `CURRICULUM.md`): environment-variable scope at workflow/job/step level, secrets vs environment variables, safe injection with `${{ secrets.NAME }}`, fork-PR secret handling, and a FastAPI/AI backend example. Added a matching common misconception.
- Expanded the self-hosted runner security trade-off: more control does not automatically mean safer. Documented persistent state, untrusted fork PRs, credential leakage, host compromise, and internal blast-radius risks, plus mitigations. Added a security note to the runner concept.
- Clarified action version pinning: `@v4` is a movable major-version tag, while a full commit SHA provides stronger supply-chain immutability. Added guidance in the step concept and the `uses` vs `run` trade-off.

### Notes

- Updated the Day21 lesson, `cheat_sheets/devops.md`, and `interview/devops.md` consistently, and recorded the change here.
- Did not change unrelated files, status files, or other lessons.
- Did not modify the example workflow (`examples/github-actions/fastapi-ci.example.yml`), templates, `ROADMAP.md`, or `CURRICULUM.md`.

---

## v0.1.31 — Day21 GitHub Actions Fundamentals Documentation

Date: 2026-07-10

### Added

- Added `docs/devops/day21-github-actions-fundamentals.md` (first lesson using LESSON_TEMPLATE_v2).
- Added `examples/github-actions/fastapi-ci.example.yml` (example-only FastAPI CI workflow).
- Added `examples/README.md`.
- Added Day21 GitHub Actions review material to `cheat_sheets/devops.md`.
- Added Day21 GitHub Actions interview questions to `interview/devops.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day21 completed (with released lesson path and v2 template note).
- Updated `ROADMAP.md` to mark Day21 completed.
- Updated `PROJECT_STATUS.md` to mark Day21 completed and set Next to Day22.
- Updated `TASKS.md` with completed Day21 tasks and Day22 preparation.
- Updated `CHANGELOG.md` with the Day21 repository update.

### Notes

- Day21 implements the Day20 CI/CD principles with GitHub Actions, taught as engineering thinking: workflow as code, the execution model (Event -> Trigger -> Workflow -> Runner -> Job -> Step -> Result), workflow vs runner, triggers and event-driven cost control, GitHub-hosted vs self-hosted runners (control, not speed), job as one fresh runner, steps with `run`/`uses`/`with`, checkout, and the quality gate before build.
- Preserved the actual classroom misconceptions and corrections: `on` mistaken for the OS, `run` mistaken for a trigger, `uses` mistaken for a shell command, preferring one big job, and Ruff failure not blocking the Docker build.
- Followed LESSON_TEMPLATE_v2: added required Core Mental Model, Common Misconceptions, Engineering Trade-offs, technology-agnostic Hands-on Exercises (YAML artifact), Relevant Framework Connections (not Playwright-forced), first-class AI Backend Connections, and a Mental Model Summary.
- The engineering artifact is a GitHub Actions workflow YAML. The example is intentionally NOT under `.github/workflows/` because this is a documentation repository with no FastAPI app to execute; it is clearly labeled example-only, uses pinned action versions, and references secrets safely (no hardcoded credentials).
- Connected the lesson to FastAPI CI, Docker build stage, and AI backend GPU/self-hosted runners, scheduled evaluation, and prompt regression testing.
- Did not modify `LESSON_TEMPLATE.md`, `LESSON_TEMPLATE_v2.md`, `TRAINING_WORKFLOW.md`, or Day01–Day20 lessons.

---

## v0.1.30 — Lesson Template v2 (Official Standard from Day21)

Date: 2026-07-10

### Added

- Added `LESSON_TEMPLATE_v2.md`, the new official lesson standard starting with Day21.

### Notes

- v2 is built from `LESSON_TEMPLATE.md` and preserves its strengths (WHY before HOW, engineering thinking, roadmap position, lesson map, interview prep, today's takeaway, checklist, ASCII diagrams, trade-offs, production examples).
- New 16-section architecture: Lesson Metadata, Learning Objectives, Why This Matters, Roadmap Position, Lesson Map, Core Mental Model, Main Concepts, Common Misconceptions, Engineering Trade-offs, Hands-on Exercises, Relevant Framework Connections, AI Backend Connections, English Interview, Mental Model Summary, Today's Takeaway, Before Next Lesson Checklist.
- Made the Core Mental Model and Mental Model Summary required sections.
- Required the classroom loop inside Main Concepts (Tech Lead Question -> Student Thinking -> Student Answer -> Tech Lead Review -> Engineering Thinking -> Production Example -> Framework Connection -> Exercise).
- Added required Common Misconceptions (wrong-vs-right) and a dedicated Engineering Trade-offs section.
- Replaced the fixed FastAPI/Playwright sections with a technology-agnostic Relevant Framework Connections section, and made AI Backend Connections a first-class section.
- Made exercises and Learning Objectives artifact-agnostic (Python, YAML, Shell, Dockerfile, Kubernetes manifest, GitHub workflow, infrastructure config, architecture diagram), not Python-only.
- Updated the AI Collaboration model to be future-proof (generic Repository Coding Agent — Claude Code / Codex — instead of hardcoding one).
- Backward compatibility: did not modify `LESSON_TEMPLATE.md` or any Day01–Day20 lesson. Older lessons remain valid and require no migration.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, `CURRICULUM.md`, or existing lessons.

---

## v0.1.29 — Day20 Corrections & Phase 2 Curriculum Upgrade

Date: 2026-07-10

### Changed

- Corrected `docs/devops/day20-ci-cd-foundations.md` to distinguish Continuous Delivery from Continuous Deployment (targeted edits, no rewrite): Delivery keeps an always-ready, production-ready release candidate with optional manual approval, while Deployment releases to production automatically once every required quality gate passes.
- Removed statements implying "CD always deploys automatically"; clarified Delivery = always ready to release, Deployment = actually releasing.
- Updated the delivery lifecycle diagram into a Continuous Delivery version (with optional Manual Approval before Production) and a Continuous Deployment version (Merge -> All Gates Pass -> Automatic Production Deployment).
- Aligned `cheat_sheets/devops.md` and `interview/devops.md` with the Delivery vs Deployment distinction.
- Upgraded `ROADMAP.md` Phase 2 into the official Day15–Day28 roadmap: Git Engineering (Day15-19), DevOps Foundations (Day20-22), Container Engineering (Day23-24), and Production Engineering (Day25-28), with a Software Delivery Lifecycle overview.
- Upgraded `CURRICULUM.md` with Day21–Day28 topics and statuses and a "Why This Curriculum" explanation (WHY before HOW).
- Updated `PROJECT_STATUS.md` Next to Day21 — GitHub Actions Fundamentals.
- Updated `TASKS.md` with Day21 preparation and the Phase 2 Day21–Day28 roadmap.

### Notes

- This is a curriculum alignment update, not a content rewrite. Day15–Day20 lessons were not rewritten.
- `ROADMAP.md` was intentionally updated as part of this official curriculum upgrade.
- Did not modify `TRAINING_WORKFLOW.md` or `LESSON_TEMPLATE.md`.

---

## v0.1.28 — Day20 CI/CD Foundations Documentation

Date: 2026-07-09

### Added

- Added `docs/devops/day20-ci-cd-foundations.md` (new `docs/devops/` folder).
- Added `cheat_sheets/devops.md` (new DevOps cheat sheet).
- Added `interview/devops.md` (new DevOps interview notes).

### Changed

- Updated `CURRICULUM.md` to add Day20 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day20 completed.
- Updated `TASKS.md` with completed Day20 tasks and Day20 review.
- Updated `CHANGELOG.md` with the Day20 repository update.

### Notes

- Day20 teaches CI/CD as replacing trust and manual work with automated process: why "I tested locally" is insufficient, CI as a trusted quality process, a pipeline as a standard workflow with stage dependency, fail-fast, and fast feedback, a quality gate as risk control protecting main/production/team/users, CD as repeatable/consistent/reliable/scalable delivery, Workflow as Code, and Everything as Code.
- Assembled the full software delivery lifecycle connecting Day15-Day20: Idea -> Issue -> Project -> Branch -> Commit -> Pull Request -> CI -> Pipeline -> Quality Gate -> Merge -> CD -> Production.
- Preserved the classroom rhythm and student reasoning across every topic.
- Connected CI/CD to FastAPI, Playwright, AI backend, Docker, and prompt work.
- Added exercises: why local testing is insufficient, design a CI pipeline, explain a quality gate, manual deployment vs CD, and explain workflow as code.
- No `exercises/` directory exists, so Day20 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.27 — Day19 GitHub Project Management Documentation

Date: 2026-07-09

### Added

- Added `docs/github/day19-project-management.md` (new `docs/github/` folder).
- Added Day19 project management material to `cheat_sheets/github.md`.
- Added Day19 project management interview questions to `interview/github.md`.

### Changed

- Updated `CURRICULUM.md` to add Day19 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day19 completed.
- Updated `TASKS.md` with completed Day19 tasks and Day19 review.
- Updated `CHANGELOG.md` with the Day19 repository update.

### Notes

- Day19 teaches GitHub project management as managing work, not clicking UI: why teams manage work not only code, Issue as a work item (collaboration, tracking, prioritization, ownership), Label as structured metadata (retrieval, workflow, automation), Milestone as a product delivery goal, Projects as workflow management, the Issue/Label/Milestone/Project hierarchy, and the complete Idea-to-Release workflow connecting Day15-Day19.
- Preserved the classroom rhythm and student reasoning, including "if work isn't tracked, it doesn't exist" and "ownership is not blame," and related Labels to database indexes, RAG filtering, vector search filtering, and Kubernetes labels.
- Connected project management to FastAPI, Playwright, AI backend, prompt, and Docker work.
- Added exercises: convert feature requests into Issues, assign and justify Labels, group Issues into a Milestone, and build a Project workflow board.
- Deliberately excluded Day20 topics.
- No `exercises/` directory exists, so Day19 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.26 — Day18 Merge Strategy & Code Review Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day18-merge-strategy-and-code-review.md`.
- Added Day18 merge strategy and code review material to `cheat_sheets/github.md`.
- Added Day18 merge strategy and code review interview questions to `interview/github.md`.

### Changed

- Updated `CURRICULUM.md` to add Day18 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day18 completed.
- Updated `TASKS.md` with completed Day18 tasks and Day18 review.
- Updated `CHANGELOG.md` with the Day18 repository update.

### Notes

- Day18 teaches merge strategy and code review as human-facing decisions: Git history is for humans, development history vs product history, merge commit (preserve history), squash merge (product history), rebase merge (linear history), senior review focus (architecture, performance, security, maintainability), "review the code, not the coder," and the three goals (improve the code, the developer, the team).
- Preserved the classroom rhythm and student reasoning across every topic.
- Connected merge strategy and review to FastAPI endpoints, Playwright tests, AI backend prompt and agent changes, and Docker changes.
- Added exercises: compare merge commit vs squash, choose a merge strategy, review a FastAPI endpoint, and rewrite a poor review comment.
- Deliberately excluded Day19 topics.
- No `exercises/` directory exists, so Day18 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.25 — Day17 GitHub Workflow & Collaboration Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day17-github-workflow.md`.
- Added `cheat_sheets/github.md` (new GitHub workflow cheat sheet).
- Added `interview/github.md` (new GitHub workflow interview notes).

### Changed

- Updated `CURRICULUM.md` to add Day17 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day17 completed.
- Updated `TASKS.md` with completed Day17 tasks and Day17 review.
- Updated `CHANGELOG.md` with the Day17 repository update.

### Notes

- Day17 teaches the GitHub collaboration workflow as gates around shared state, not tool clicks: why direct push to main is dangerous, Pull Request as Review + CI + Discussion + Audit Trail, machines validate rules while humans validate intent, Branch Protection, stale reviews, and review discussions as an engineering knowledge base.
- Preserved the classroom rhythm and student reasoning across every topic.
- Included the required workflow mental-model diagram (Developer -> Feature Branch -> Commit -> Push -> Pull Request [CI + Human Review] -> Branch Protection -> Stable main -> Engineering Knowledge Base).
- Connected the workflow to FastAPI endpoints, Playwright tests, AI backend prompt and agent changes, and Docker changes.
- Added pull request lifecycle exercises: open a PR, trigger CI, request changes, approve, simulate a stale review, and merge.
- Deliberately excluded Day18 topics.
- Created dedicated `github.md` cheat sheet and interview files, keeping GitHub collaboration separate from Git internals in `git.md`.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.24 — Day16 Git Branch & Merge Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day16-branch-and-merge.md`.
- Added Day16 Branch & Merge review material to `cheat_sheets/git.md`.
- Added Day16 Branch & Merge interview questions to `interview/git.md`.

### Changed

- Updated `CURRICULUM.md` to add Day16 and mark it completed under Phase 2.
- Updated `PROJECT_STATUS.md` to mark Day16 completed.
- Updated `TASKS.md` with completed Day16 tasks and Day16 review.
- Updated `CHANGELOG.md` with the Day16 repository update.

### Notes

- Day16 teaches branch and merge as the Git object model in motion, not command memorization: why branches exist, branch as a movable reference, instant branch creation, HEAD and current branch, fast-forward merge as reference movement, three-way merge with a two-parent merge commit, merge conflict as Git refusing to guess intent, and Git history as a Directed Acyclic Graph.
- Preserved the classroom rhythm and student reasoning, including the production/feature/hotfix scenario, the "branch is not a copy" correction, the instant-branch derivation, the fast-forward discovery, and the key sentence "Git does not fail; Git refuses to guess business intent."
- Included the required diagrams (branch as reference, HEAD/current branch before and after commit, fast-forward, two-parent three-way merge, merge conflict, DAG).
- Connected branch and merge to FastAPI feature branches, Playwright test branches, AI backend prompt and agent workflow branches, and Docker changes.
- Deliberately excluded Day17+ topics: GitHub, pull requests, code review, GitHub Flow, rebase, and cherry-pick.
- No `exercises/` directory exists, so Day16 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.23 — Day15 Revision

Date: 2026-07-09

### Changed

- Reframed `docs/git/day15-git-fundamentals.md` to derive the Git object model from the Python object model (Day01-Day02) instead of presenting Git commands.
- Added a new first Main Concept "From Python Object Model to Git Object Model" with a Python-to-Git mapping table and the Git Object diagram (`HEAD -> Branch -> Commit -> Tree -> Blob`).
- Added a reflog derivation chain (Commit -> reference removed -> dangling/unreachable -> HEAD history -> `git reflog`) so the recovery mechanism is derived, not just described.
- Relabeled the classroom "Student Thinking" beats for a clearer Tech Lead Question -> Student Thinking -> Student Answer -> Tech Lead Review rhythm.
- Updated the lesson map and renumbered the concepts to include the object-model derivation.
- Added a `## Mental Model Summary` section to `cheat_sheets/git.md`.
- Added a senior interview question linking Git's object model to Python's object model in `interview/git.md`.
- Updated `PROJECT_STATUS.md` and `TASKS.md` to record the Day15 revision.

### Notes

- Preserved all classroom interaction, student reasoning, and derivations; did not convert the lesson into documentation.
- Did not expand Day16 or later.
- Did not modify `ROADMAP.md`, `TRAINING_WORKFLOW.md`, or `LESSON_TEMPLATE.md`.

---

## v0.1.22 — Day15 Git Fundamentals Documentation

Date: 2026-07-09

### Added

- Added `docs/git/day15-git-fundamentals.md` (starts Phase 2 — Engineering Foundations).
- Added `cheat_sheets/git.md` (new Git cheat sheet).
- Added Day15 Git Fundamentals interview questions to `interview/git.md`.

### Changed

- Updated `CURRICULUM.md` to add Phase 2 and mark Day15 as completed.
- Updated `PROJECT_STATUS.md` to start Phase 2 and mark Day15 completed.
- Updated `TASKS.md` with completed Day15 tasks and next Phase 2 preparation.
- Updated `CHANGELOG.md` with the Day15 repository update.

### Notes

- Day15 teaches Git as an engineering system, not command memorization: object model, snapshot vs diff, immutable commits, repository vs working directory, staging area, the three-tree model, HEAD and branch, detached HEAD, reset modes, and reflog.
- Preserved the classroom rhythm and student reasoning, including the IDE-history correction, the snapshot-vs-diff discovery, the immutable-snapshot answer, the staging-area v1/v2 question, the detached HEAD insight, and the reset/reflog corrections.
- Included the required ASCII diagrams (snapshot reuse, working directory to repository flow, HEAD/branch before and after commit, detached HEAD, three-tree model) and the reset soft/mixed/hard table.
- Connected Git to FastAPI rollback and diffing, Playwright locator/test history, and AI backend prompt and configuration versioning.
- Marked Phase 2 as started; did not mark Day16 or later as started.
- No `exercises/` directory exists, so Day15 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.21 — Day14 Review Fix

Date: 2026-07-08

### Added

- Added a concise `## Day14 Interview Review` bullet section to `cheat_sheets/python.md` covering layered architecture, thin router, service layer, browser layer, LLM layer, repository pattern, dependency injection, stateless service, shared mutable state, worker vs async, semaphore, retry, exponential backoff, stable throughput, and horizontal scaling.
- Added four missing Day14 interview questions to `interview/python.md`: why the Browser Layer returns data instead of JSON, what shared mutable state is, async vs worker scaling, and how to design an AI Summary Service.

### Notes

- Did not rewrite the Day14 lesson.
- Did not create duplicate Day14 sections; the new questions extend the existing Day14 interview section and stay grouped by difficulty.
- Verified Day14 lesson section ordering follows `LESSON_TEMPLATE.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.20 — Day14 Mini Project & Backend Architecture Documentation

Date: 2026-07-08

### Added

- Added `docs/python/day14-mini-project.md`.
- Added `cheat_sheets/fastapi.md` (new FastAPI cheat sheet).
- Added Day14 backend architecture review material to `cheat_sheets/python.md`.
- Added Day14 backend architecture interview questions to `interview/python.md`.
- Added Day14 backend architecture interview questions to `interview/fastapi.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day14 as completed and Phase 1 as complete.
- Updated `PROJECT_STATUS.md` to mark Day14 completed and point to Phase 2.
- Updated `TASKS.md` with completed Day14 tasks and Phase 2 preparation tasks.
- Updated `CHANGELOG.md` with the Day14 repository update.

### Notes

- Day14 is an integration lesson, not a Python syntax lesson: it combines Day01–Day13 into a production-shaped, layered AI backend.
- Covered layered architecture (API, Service, Browser, LLM, Repository, Database), each layer's single responsibility and what it must NOT do, thin routers, service orchestration, the browser and LLM as infrastructure behind interfaces, multi-provider architecture, and the repository pattern.
- Covered engineering thinking: separation of concerns, single responsibility, low coupling, high cohesion, dependency injection, stateless services, shared mutable state, interface-first development, and architecture before coding.
- Covered production topics: worker architecture, async vs worker scaling, horizontal scaling, throughput, bottleneck analysis, semaphore, retry, exponential backoff, HTTP 429, and browser/LLM resource management.
- Connected the design to FastAPI request flow with `Depends()`, Playwright browser layer cleanup, and an AI summary service with queue, worker pool, Redis, PostgreSQL, and OpenAI.
- Added a mock interview and 10-level architecture exercises.
- No `exercises/` directory exists, so Day14 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.19 — Day13 Async Programming Documentation

Date: 2026-07-08

### Added

- Added `docs/python/day13-async-programming.md`.
- Added Day13 Async Programming review material to `cheat_sheets/python.md`.
- Added Day13 Async Programming interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day13 as completed and Day14 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day13 as completed and prepare Day14.
- Updated `TASKS.md` with completed Day13 tasks and Day14 preparation tasks.
- Updated `CHANGELOG.md` with the Day13 repository update.

### Notes

- Explained every concept from the Event Loop perspective: what the loop is doing, which Task runs, which is suspended, and why the scheduler switches.
- Covered async motivation (I/O throughput vs CPU), I/O bound vs CPU bound, blocking vs non-blocking (`time.sleep()` vs `asyncio.sleep()`), the Event Loop, coroutine vs coroutine object, Task vs coroutine, `await`, `asyncio.gather()` input-order results, the Task lifecycle, cooperative cancellation and `CancelledError`, exception propagation, and `Semaphore` concurrency control.
- Emphasized stable throughput over maximum concurrency and respecting downstream capacity (OpenAI rate limits, Redis, PostgreSQL pools, GPU, browser memory).
- Connected Day13 concepts to FastAPI async request Tasks and `asyncio.to_thread()`, Playwright async automation with bounded concurrency, and AI backend concurrency with `gather()` and semaphores.
- Documented production risks: blocking the Event Loop, blocking libraries in async code, connection pool exhaustion, too many concurrent OpenAI requests, Redis overload, PostgreSQL connection exhaustion, browser explosion, and memory pressure from excessive Tasks.
- No `exercises/` directory exists, so Day13 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.18 — Day12 Context Managers Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day12-context-managers.md`.
- Added Day12 Context Managers review material to `cheat_sheets/python.md`.
- Added Day12 Context Managers interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day12 as completed and Day13 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day12 as completed and prepare Day13.
- Updated `TASKS.md` with completed Day12 tasks and Day13 preparation tasks.
- Updated `CHANGELOG.md` with the Day12 repository update.

### Notes

- Covered resource lifecycle (Acquire -> Use -> Release), `try / finally`, the `with` statement, `__enter__`, `__exit__`, exception handling in `__exit__`, `@contextmanager`, `yield` vs `return`, and generator pause/resume cleanup.
- Emphasized the principle that business logic should not own resource management.
- Connected Day12 concepts to FastAPI `yield` dependencies and lifespan handlers, Playwright `BrowserContext` cleanup, and AI backend LLM stream, Redis, session, and lock cleanup.
- Documented production risks: database connection leaks, file handle leaks, BrowserContext leaks, Redis connection leaks, LLM stream leaks, and locks not released.
- No `exercises/` directory exists, so Day12 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.17 — Day11 Review Fix

Date: 2026-07-07

### Changed

- Strengthened the Day11 OOP cheat sheet structure in `cheat_sheets/python.md`.
- Added explicit Day11 OOP beginner interview questions for class and instance in `interview/python.md`.
- Added a senior Day11 Dependency Injection interview question in `interview/python.md`.

### Notes

- Did not modify `docs/python/day11-object-oriented-programming.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.16 — Day11 Object-Oriented Programming Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day11-object-oriented-programming.md`.
- Added Day11 Object-Oriented Programming review material to `cheat_sheets/python.md`.
- Added Day11 OOP interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day11 as completed and Day12 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day11 as completed and prepare Day12.
- Updated `TASKS.md` with completed Day11 tasks and Day12 preparation tasks.
- Updated `CHANGELOG.md` with the Day11 repository update.

### Notes

- Covered object, class, instance, state, behavior, `self`, attribute lookup, method lookup, class attributes, instance attributes, inheritance, override, `super()`, MRO, and composition.
- Connected Day11 concepts to FastAPI application/service/dependency objects, Playwright browser/context/page/locator objects, and AI backend service composition.
- No `exercises/` directory exists, so Day11 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.15 — Day10 Type Hints Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day10-type-hints.md`.
- Added Day10 Type Hints review material to `cheat_sheets/python.md`.
- Added Day10 Type Hints interview questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day10 as completed and Day11 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day10 as completed and prepare Day11.
- Updated `TASKS.md` with completed Day10 tasks and Day11 preparation tasks.
- Updated `CHANGELOG.md` with the Day10 repository update.

### Notes

- Covered Type Hints as interface contracts, runtime behavior, parameter and return types, `list[T]`, `dict[K, V]`, `tuple`, `set[T]`, `User | None`, `Optional`, `Union`, type inference, `TypeVar`, and `Generic`.
- Connected Day10 concepts to FastAPI request models, response models, `Depends()`, Pydantic, OpenAPI, Playwright object types, and AI backend tool/message contracts.
- No `exercises/` directory exists, so Day10 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.14 — Day09 Consistency Fix

Date: 2026-07-07

### Changed

- Fixed `PROJECT_STATUS.md` so the Next section consistently points to Day10.
- Standardized the Day09 import execution flow in `docs/python/day09-modules-packages.md`.
- Standardized the Day09 import execution flow in `cheat_sheets/python.md`.

### Notes

- Did not rewrite Day09.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.13 — Day09 Modules and Packages Documentation

Date: 2026-07-07

### Added

- Added `docs/python/day09-modules-packages.md`.
- Added Day09 module, package, import system, and import side effect review material to `cheat_sheets/python.md`.
- Added Day09 interview questions with overseas AI Backend engineering answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day09 as completed and Day10 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day09 as completed and prepare Day10.
- Updated `TASKS.md` with completed Day09 tasks and Day10 preparation tasks.
- Updated `CHANGELOG.md` with the Day09 repository update.

### Notes

- Covered import execution flow, module objects, module cache with `sys.modules`, module vs package, `__init__.py`, namespace packages, absolute imports, relative imports, namespace pollution, and import side effects.
- Connected Day09 concepts to FastAPI package structure, Playwright worker boundaries, and AI backend package architecture.
- No `exercises/` directory exists, so Day09 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.12 — Day08 Exception Handling Polish

Date: 2026-07-07

### Changed

- Polished the Day08 completion badge in `docs/python/day08-exception-handling.md`.
- Preserved classroom code review examples for `divide(a, b)` and `check_age(age)`.
- Improved Playwright timeout specificity by using `PlaywrightTimeoutError`.
- Added Day08 Tech Lead Advice after Today's Takeaway.
- Added a Day08 system design interview question for AI Backend exception handling.
- Added a cheat sheet note about framework-specific exception classes.

### Notes

- Did not rewrite Day08.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.11 — Day08 Exception Handling Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day08-exception-handling.md`.
- Added Day08 exception handling review material to `cheat_sheets/python.md`.
- Added Day08 interview questions with overseas AI Backend engineering answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day08 as completed and Day09 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day08 as completed and prepare Day09.
- Updated `TASKS.md` with completed Day08 tasks and Day09 preparation tasks.
- Updated `CHANGELOG.md` with the Day08 repository update.

### Notes

- Covered `try / except`, precise exception handling, `ZeroDivisionError`, exception control flow, exception propagation, `raise`, custom exceptions, and exception chaining.
- Added `InvalidPromptError`, `LLMRequestError`, `ToolExecutionError`, and `RateLimitError` error-design examples.
- Connected Day08 concepts to FastAPI `HTTPException`, Playwright timeout recovery, and AI backend failure handling.
- No `exercises/` directory exists, so Day08 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.10 — Day07 Classroom Polish

Date: 2026-07-06

### Changed

- Enhanced `docs/python/day07-iterators-generators.md` with additional classroom reasoning, Tech Lead questions, and production bug examples.
- Enhanced `cheat_sheets/python.md` with a Day07 production risk table.
- Enhanced `interview/python.md` with senior-level Day07 questions about accidental generator consumption and shared state.

### Notes

- Added the principle: Data can be shared, state should not be shared.
- Added production bug examples for `list(generator)`, `sum(generator)`, and LLM stream debugging.
- Strengthened Pipeline vs Batch and AI token streaming explanations.
- Confirmed Day07 remains completed and Day08 remains the current lesson.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.9 — Day07 Iterators and Generators Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day07-iterators-generators.md`.
- Added Day07 iterator, generator, lazy evaluation, and streaming review material to `cheat_sheets/python.md`.
- Added Day07 interview questions with standard answers, follow-up questions, and engineering perspectives to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day07 as completed and Day08 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day07 as completed and prepare Day08.
- Updated `TASKS.md` with completed Day07 tasks and Day08 preparation tasks.
- Updated `CHANGELOG.md` with the Day07 repository update.

### Notes

- Covered Iterable, Iterator, `iter()`, `next()`, `StopIteration`, Generator, `yield`, generator lifecycle, lazy evaluation, generator expression, and `yield from`.
- Covered why `StopIteration` does not return `None`, why iterable and iterator are separated, and why generators are pausable and resumable data-flow models.
- Added streaming connections for FastAPI `StreamingResponse`, Playwright data pipelines, and AI backend token streaming.
- No `exercises/` directory exists, so Day07 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.8 — Day06 Decorators Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day06-decorators.md`.
- Added Day06 decorator review material to `cheat_sheets/python.md`.
- Added Day06 interview questions, Chinese explanations, English answers, and overseas interview answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day06 as completed and Day07 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day06 as completed and prepare Day07.
- Updated `TASKS.md` with completed Day06 tasks and Day07 preparation tasks.
- Updated `CHANGELOG.md` with the Day06 repository update.

### Notes

- Covered decorator motivation, cross-cutting concerns, wrapper functions, universal decorators, and `functools.wraps`.
- Covered metadata preservation for `__name__`, `__doc__`, `__annotations__`, and signature/reflection behavior.
- Added production examples for logging, timing, retry, authentication, cache, token tracking, and AI request tracing.
- Connected Day06 concepts to FastAPI route decorators, Playwright retry decorators, and AI backend observability.
- No `exercises/` directory exists, so Day06 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.7 — Day05 Closures Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day05-closures.md`.
- Added Day05 Closure Engineering Notes to `cheat_sheets/python.md`.
- Added Factory Function, Closure vs Class, and Late Binding review material to `cheat_sheets/python.md`.
- Added Day05 interview questions, Chinese explanations, English answers, overseas backend answers, and follow-up questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day05 as completed and Day06 as the current lesson.
- Adjusted `docs/python/day05-closures.md` so required sections remain in the official template order.
- Updated `PROJECT_STATUS.md` to mark Day05 as completed.
- Updated `TASKS.md` with completed Day05 tasks and Day06 preparation tasks.

### Notes

- Covered Closure as Function Object plus Captured Environment.
- Covered captured environment, state preservation, `nonlocal`, `UnboundLocalError`, factory functions, Closure vs Class, and Late Binding.
- Connected Day05 concepts to FastAPI dependency factories, Playwright configuration factories, and AI prompt builders.
- No `exercises/` directory exists, so Day05 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.6 — Day04 Scope and LEGB Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day04-scope-legb.md`.
- Added Day04 LEGB, scope, closure, and late binding review material to `cheat_sheets/python.md`.
- Added Day04 interview questions and English answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day04 as completed and Day05 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day04 as completed.
- Updated `TASKS.md` with completed Day04 tasks and Day05 preparation tasks.

### Notes

- Covered lexical scope, `global`, `nonlocal`, mutation vs rebinding, closure, and late binding.
- Connected Day04 concepts to FastAPI, Playwright, and AI backend engineering.

---

## v0.1.5 — Day03 Functions and Parameter Passing Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day03-functions-parameter-passing.md`.
- Added Day03 function parameter passing review material to `cheat_sheets/python.md`.
- Added Day03 interview questions and English answers to `interview/python.md`.

### Changed

- Updated `PROJECT_STATUS.md` to mark Day03 as completed.
- Updated `TASKS.md` with completed Day03 tasks and Day04 preparation tasks.

### Notes

- Did not modify `CURRICULUM.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.
- No `exercises/` directory exists, so Day03 exercises are included in the lesson document.

---

## v0.1.4 — Day02 Mutable vs Immutable Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day02-mutable-vs-immutable.md`.
- Added Day02 mutable vs immutable review material to `cheat_sheets/python.md`.
- Added Day02 interview questions to `interview/python.md`.

### Changed

- Updated `PROJECT_STATUS.md` to mark Day02 as completed.
- Updated `TASKS.md` with completed Day02 tasks, review tasks, and Day03 preparation tasks.

### Notes

- Did not modify Day01 technical content.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.3 — Release Candidate Workflow Stabilization

Date: 2026-07-03

### Added

- Added `TRAINING_WORKFLOW.md` as the official training operating manual.
- Added daily learning workflow to `README.md`.
- Added repository lifecycle guidance to `REPOSITORY_GUIDE.md`.
- Added Today's Goal and Definition of Done to `PROJECT_STATUS.md`.

### Changed

- Updated `CURRICULUM.md` into a reusable engineering curriculum format.
- Redesigned `TASKS.md` as the daily execution sprint board.
- Updated repository guidance so future lessons follow one stable workflow.

### Notes

- Day01 technical content was not changed.
- Folder structure was not changed.
- Lesson template was not changed.

---

## v0.1.2 — Repository Cleanup and Structure Alignment

Date: 2026-07-02

### Added

- Added topic-based lesson structure under `docs/`.
- Added project README files for every project directory.
- Added `interview/python.md` as the template for future interview handbooks.
- Added `cheat_sheets/python.md` as the template for future cheat sheets.
- Added `prompts/interview.md`.
- Added `prompts/project.md`.
- Added `REPOSITORY_GUIDE.md`.
- Added `CONTRIBUTING.md`.
- Added assets subdirectories for images, diagrams, architecture, and memory models.

### Changed

- Moved Day 1 final lesson to `docs/python/day01-object-model.md`.
- Updated architecture references to use `docs/<topic>/`.
- Updated Codex prompt to use topic-based lesson paths.
- Updated `PROJECT_STATUS.md` and `TASKS.md` for Day 2 readiness.

### Removed

- Removed duplicated Day 1 course structure outside canonical `docs/` organization.

### Future

- Reserved a future `knowledge/` structure in `TASKS.md` without creating it yet.

---

## v0.1.1 — Project Management Layer

Date: 2026-07-02

### Added

- Added `TASKS.md`.
- Added `ARCHITECTURE.md`.
- Added `CHANGELOG.md`.
- Added `DECISIONS.md`.
- Added `ROADMAP.md`.
- Added `GLOSSARY.md`.

### Next

- Add repository directory skeleton.
- Add first final lesson under `docs/`.

---

## v0.1.0 — Repository Foundation

Date: 2026-07-02

### Added

- Created core repository concept.
- Added `README.md`.
- Added `AGENTS.md`.
- Added `PROJECT_STATUS.md`.
- Added `CURRICULUM.md`.
- Added `CODING_STANDARD.md`.
- Added `LESSON_TEMPLATE.md`.

### Learning Progress

- Completed Day 1 discussion.
- Covered Python Object Model.
- Covered Function Objects.
- Covered Callable Objects.
- Covered References.
- Covered `==` vs `is`.
- Covered Mutable Default Argument bug.
