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
- `github-actions/reusable-fastapi-ci.example.yml` — Day22 reusable workflow teaching template.
  Copy it to `.github/workflows/reusable-fastapi-ci.yml` in a real shared-workflow repository before
  calling it via a job-level `uses` (`owner/repo/.github/workflows/reusable-fastapi-ci.yml@<commit-sha>`);
  it is not callable from this `examples/` path.
- `docker/fastapi/` — Day23 production-oriented FastAPI `Dockerfile` + `.dockerignore` with
  reproducible build/run, named-volume, and user-defined-network commands
  (see `docs/devops/day23-docker-fundamentals.md`).
- `docker/compose/` — Day24 multi-service Compose example (FastAPI + Worker + Redis + PostgreSQL):
  `compose.yaml`, `compose.dev.yaml`, `.env.example` with segmented networks, healthchecks, secrets,
  and a named volume (see `docs/devops/day24-docker-compose.md`).
- `deployment/` — Day25 deployment foundations: an example Nginx reverse-proxy/TLS config
  (`nginx/nginx.conf.example`) and a zero-downtime blue-green deployment + rollback runbook
  (see `docs/devops/day25-deployment-foundations.md`).
- `kubernetes/` — Day26 Kubernetes foundations: an example baseline manifest
  (`ai-backend-baseline.yaml`) with a ConfigMap, a Secret template, a three-replica Deployment
  (FastAPI + logging sidecar), and a Service, plus a README separating static from runtime
  validation (see `docs/devops/day26-kubernetes-foundations.md`).
- `kubernetes/rag-platform/` — Day27 Kubernetes workloads: a teaching-only Helm chart packaging the
  workload with Ingress, an `autoscaling/v2` HPA, a Rolling Update Deployment, and a PostgreSQL
  StatefulSet + headless Service, with per-environment Values and a static-only `validate_chart.py`
  (see `docs/devops/day27-kubernetes-workloads.md`).
- `ai-backend-architecture/` — Day28 conceptual Production AI Backend Architecture Blueprint (RAG
  ingestion): responsibility map, request/upload/job flows, state machines, a state/data ownership
  table, outbox/idempotency boundaries, a failure/rollback/data-repair matrix, monitoring/observability
  signals, and validation limitations (see `docs/devops/day28-ai-backend-production-architecture.md`).
