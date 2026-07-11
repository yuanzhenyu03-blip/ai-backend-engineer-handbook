# examples

Runnable, reference engineering artifacts extracted from lessons (YAML, workflows, configs).

These are example-only artifacts. Files here are not wired to execute in this documentation
repository; copy them into a real project and adjust paths, versions, and commands.

- `github-actions/fastapi-ci.example.yml` — Day21 FastAPI CI workflow
  (see `docs/devops/day21-github-actions-fundamentals.md`).
- `github-actions/github-actions-advanced.example.yml` — Day22 advanced CI/CD workflow: matrix,
  cache, artifacts, continue-on-error, build once, verify the exact immutable digest, deploy it,
  environment, concurrency (see `docs/devops/day22-github-actions-advanced.md`).
- `github-actions/composite-python-quality/action.yml` — Day22 composite action (reusable steps:
  setup, install, Ruff, pytest), runs inside the caller job's runner.
- `github-actions/reusable-fastapi-ci.example.yml` — Day22 reusable workflow (`workflow_call`,
  typed inputs, a complete `quality` job), called at the job level via `uses`.
