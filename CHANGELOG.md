# CHANGELOG.md

All notable changes to this repository will be documented in this file.

This project follows a practical versioning style:

- `v0.x.x` — training system under construction
- `v1.0.0` — first complete AI Backend Engineer Handbook release

---

## v0.1.53 — Phase 3 Status Consistency Fix

Date: 2026-07-19

### Changed

- Unified the active status fields across `README.md`, `AGENTS.md`, `PROJECT_STATUS.md`, and `TASKS.md` so a new teaching session unambiguously knows the next lesson is Day29 (planned, not started) rather than re-reading the completed Day28.
- Current Phase is now `Phase 3 — Backend Foundations (Planned / Ready — not started)` in `README.md`, `AGENTS.md`, `PROJECT_STATUS.md`, and `TASKS.md` (previously Phase 2 in three of them).
- Current Lesson is now `Day29 — PostgreSQL Foundations and Durable Relational State` with `Status: Planned / Not started` in `PROJECT_STATUS.md` and `TASKS.md`; the Day28-only Current Lesson fields (Template/Completed Time) were removed because they already live under Last Completed Lesson.
- `TASKS.md` Target lesson no longer points at a Day28 file for the current lesson; it states the Day29 file is not created yet (see CURRICULUM.md and ROADMAP.md), and Today's Tasks now reflect the planned/not-started Day29 state.
- Last Completed Lesson remains `Day28 — AI Backend Production Architecture`; no adjacent duplicate Phase 3 status line remains in `README.md`/`AGENTS.md`.

### Notes

- Status-only fix: Phase 3 and Day29 are neither In Progress nor Completed. No Day29 lesson was started; no Day29 lesson file, SQL/Redis design, `projects/ai-backend-data-layer/`, or `knowledge/` was created; no runtime validation was performed or claimed. Day29-Day42 remain Planned.
- Verified with `git diff --check` and a status-consistency search. Did not re-design the Phase 3 curriculum or change `CURRICULUM.md`, `ROADMAP.md`, `docs/devops/day28-ai-backend-production-architecture.md`, the protected prompt/template files, `interview/*`, `cheat_sheets/*`, `examples/*`, or `projects/*`. Historical CHANGELOG entries are unchanged.

---

## v0.1.52 — Phase 3 Backend Foundations Curriculum Planning

Date: 2026-07-18

### Changed

- Planned Phase 3 — Backend Foundations as a Day29-Day42 curriculum (planning only; Day28 remains the last completed lesson and no Phase 3 lesson has started).
- Updated `ROADMAP.md`: Phase 3 heading is now `Phase 3 — Backend Foundations (Day29-Day42)` with an objective, a Day29-Day42 `Planned` table, and refined deliverables. Phase 4 receives no day numbers.
- Updated `CURRICULUM.md`: added a Phase 3 section with the exact Day29 scope, previous/next continuity, and a planned Engineering Artifact, plus concise `Planned` Day30-Day42 entries (title + narrow topic list + status). No lesson bodies, classroom exchanges, or student answers were invented.
- Updated `PROJECT_STATUS.md`: Current Phase is Phase 3 (Planned / Ready — not started); Next Lesson is Day29 — PostgreSQL Foundations and Durable Relational State (Planned / Not started); Day28 stays the last completed lesson.
- Updated `TASKS.md`: replaced the generic Phase 3 preparation block with Day29 preparation tasks and added a Phase 3 Day29-Day42 roadmap with every item unchecked/Planned. Completed Day28 history is unchanged.
- Updated `README.md` and `AGENTS.md`: Next is Day29 with its exact title; Phase 3 is planned/ready but not started; Day28 stays last completed. Engineering and teaching rules are unchanged.
- Updated `docs/devops/day28-ai-backend-production-architecture.md`: the metadata Next Lesson now names Day29's exact planned title, linked to `CURRICULUM.md`/`ROADMAP.md` (the Day29 lesson file does not exist yet, so no broken link is created). The completed Day28 body is unchanged.

### Notes

- Planning only: no Phase 3 lesson document, classroom event, student answer, cheat-sheet/interview content, SQL schema, Redis design, `projects/ai-backend-data-layer/` artifact, or runtime validation was created or completed. SQLAlchemy/Alembic remain Phase 4; Phase 4 day numbers and a Day43 title were not invented.
- Validation actually performed: `git diff --check`, Markdown structure/relative-link inspection of the modified files, and a status-consistency search. No PostgreSQL/SQL/Redis/Docker/migration/transaction/concurrency/backup-restore/integration validation was performed or claimed.
- Did not create `docs/.../day29-*.md`, `projects/ai-backend-data-layer/`, or `knowledge/`; did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, `interview/postgresql.md`, `interview/redis.md`, cheat sheets, examples, or projects. Historical CHANGELOG entries are unchanged.

---

## v0.1.51 — Day28 Review Fixes

Date: 2026-07-18

### Changed

- Corrected an impossible exactly-once implication in the Senior interview question. `docs/devops/day28-ai-backend-production-architecture.md` and `interview/devops.md` now ask how to prevent duplicate durable effects and minimize duplicate provider calls under at-least-once delivery, and what risk still remains, instead of asking to "guarantee a document is not embedded/charged twice". The Chinese explanation now states that DB unique constraint + atomic upsert + checkpoint + ACK-after-durable-write prevent duplicate durable side effects, provider idempotency keys reduce duplicate external calls, and a provider call that succeeds before the local checkpoint write can still be repeated and charged — so exactly-once across independent systems is never promised. The student's real answer ("我忘了") and the "taught directly" note are preserved.
- Fixed a component-ownership wording error in the Day28 lesson: "each component ... owns ONE job" is replaced with "each component has ONE clear responsibility in the Job lifecycle", keeping the core model (FastAPI accepts/exposes; Celery executes; Queue/Redis transports; PostgreSQL owns the durable Job truth; Object Storage owns large bytes).
- Distinguished the worker HPA scaling metric from SLO/diagnostic signals in the Day28 lesson: the worker HPA's primary signal is queue backlog (ideally backlog per worker); oldest queued-job age is closer to user waiting/SLO and is for alerting/diagnosis; throughput indicates progress/under-capacity; a single stuck/poison-pill job can inflate oldest age so it must not be an unqualified scale-up trigger; scaling stays bounded by provider rate limits, cost, and maxReplicas.
- Fixed the stale Day27 metadata: the Next Lesson now links directly to the published Day28 lesson (`day28-ai-backend-production-architecture.md`) instead of describing it as planned.

### Notes

- No runtime validation was performed or claimed. Verified with `git diff --check`, Markdown link checks, and a secret scan of the changed files. No FastAPI/Celery/Redis/PostgreSQL/Object Storage/Kubernetes runtime was built or run. Historical CHANGELOG "Planned" records and Day26/Day27 historical future-connection notes are unchanged. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`, and did not change any student's original answer.

---

## v0.1.50 — Day28 AI Backend Production Architecture Documentation

Date: 2026-07-18

### Added

- Added `docs/devops/day28-ai-backend-production-architecture.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day27->Day28 mental-model evolution). This is the Phase 2 closing lesson.
- Added `examples/ai-backend-architecture/README.md`: a conceptual Production AI Backend Architecture Blueprint (responsibility map, request/upload/job flows, state machines, state/data ownership table, delivery/outbox/idempotency boundaries, retry policy, failure/rollback/data-repair matrix, monitoring/observability signals, security boundaries, and validation limitations with a future runtime validation plan).
- Added Day28 review material to `cheat_sheets/devops.md` (replacing the Day28 placeholder).
- Added Day28 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day28 blueprint and `docs/README.md` to correct the stale directory tree.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day28 completed (no invented Day29/Day30 titles).
- Updated `PROJECT_STATUS.md` to mark Day28 completed, close Phase 2 (Day15-Day28), record the conceptual artifact and validation boundary, and set Next to Phase 3 — Backend Foundations.
- Updated `TASKS.md` with completed Day28 tasks, the Phase 2 Roadmap Day28 status, and Phase 3 preparation.
- Updated `README.md` and `AGENTS.md` progress markers (Phase 2 complete; next Phase 3, no invented lesson number).
- Updated `CHANGELOG.md` with the Day28 repository update.

### Notes

- Day28 assembles FastAPI, Celery, Redis, PostgreSQL, Object Storage, Queue, Monitoring, and Observability into one production AI Backend by defining component responsibilities and lifecycle boundaries: HTTP request lifecycle != long-running job lifecycle (return 202 + job_id, process in a Celery worker); PostgreSQL owns the durable Job truth while Redis delivers/accelerates and Object Storage owns the large bytes; the Transactional Outbox makes business state + intent-to-publish atomic but is still at-least-once, so processing must be idempotent (stable key + unique constraint/upsert, ACK after durable write, leases for exclusive ownership); presigned direct multipart upload with a verified Upload Session; bounded classified retries with backoff/jitter/circuit breaker; monitoring by queue depth vs oldest-age vs throughput; observability correlated on a stable job_id with low-cardinality metrics and append-only events; and a contain -> restore -> identify -> rebuild -> verify data-repair runbook, because compute rollback does not repair persisted data.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (PostgreSQL as final-state-only; DB-first alone solving DB/queue consistency; progress preventing duplicate work; job_status as a correlation id; read-then-upsert treated as exactly-once; code rollback treated as complete). The senior English answer was taught directly after the student said "我忘了", and the internally inconsistent final-summary sentence was corrected.
- Scope/security honesty: the Day28 artifact is conceptual architecture documentation. No FastAPI/Celery/Redis/PostgreSQL/Object Storage/vector/Kubernetes/metrics/log/trace system was created or run; no static code/config/schema validation, queue redelivery, provider failure, load, smoke, rollback, or data-repair test was executed. No real secret, credential, presigned URL, or customer document is committed; at-least-once (not exactly-once) is taught, object keys are not authorization, and metric labels stay low-cardinality.
- Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`; did not create the reserved `knowledge/` structure; did not invent Phase 3 day numbers; and did not rewrite Day01-Day27 lesson bodies.

---

## v0.1.49 — Day27 HPA Metric Fix

Date: 2026-07-17

### Changed

- Made the `rag-platform` API HPA metric configuration explicit. Previously `hpa.cpu.enabled: false` kept the HPA but rendered an empty `metrics:`, which `autoscaling/v2` silently treats as a default 80% average-CPU target — so the switch name did not match the behavior.
- Removed the `hpa.cpu.enabled` toggle from `values.yaml` and the `{{- if .Values.hpa.cpu.enabled }}` condition from `templates/hpa.yaml`. When `hpa.enabled` is true the HPA now always renders one explicit CPU `Resource` metric; when `hpa.enabled` is false no HPA is created and the Deployment renders `replicaCount`.
- Updated `validate_chart.py` to assert there is no `hpa.cpu.enabled` toggle, the HPA template has no `.Values.hpa.cpu.enabled` condition, the HPA always renders an explicit CPU metric, a CPU request exists, the Deployment still guards `spec.replicas` with `if not .Values.hpa.enabled`, and the API HPA still carries no queue-backlog/External worker metric.
- Synced `examples/kubernetes/README.md`, `docs/devops/day27-kubernetes-workloads.md`, and `cheat_sheets/devops.md` to state: the Day27 chart supports one API HPA metric (CPU); `hpa.enabled` controls whether the HPA exists; the explicit CPU target is always rendered when enabled; queue backlog belongs to a worker Deployment and remains a Day28 connection.

### Notes

- Validation actually performed: `git diff --check` clean; `validate_chart.py` PASS (22 structural/values checks). `helm` is not installed and no Kubernetes API server is available, so `helm lint`, `helm template`, schema/admission, and all runtime validation were NOT run / NOT verified and no result is claimed.
- Did not rewrite Day01-Day26, did not start or expand Day28, and did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`. Historical CHANGELOG entries are unchanged.

---

## v0.1.48 — Day27 Review Fixes

Date: 2026-07-17

### Changed

- Fixed image rendering in the `rag-platform` chart: replaced split `image.repository` + `image.tag` with a single `image.reference` (and `postgres.image.reference`) so a deploy-time swap to a `repository@sha256:<digest>` reference renders a valid image. Default stays a non-pullable, mutable, unverified `example.invalid` placeholder.
- Fixed HPA vs Deployment replica ownership: the Deployment now omits `spec.replicas` when `hpa.enabled`, so a `helm upgrade` does not reset the HPA-managed replica count; when the HPA is disabled it renders `replicaCount`.
- Fixed the queue-backlog scaling scope: removed the `queueBacklog` External metric and its Values from the API HPA (wiring it to the API would scale the producer, not the consumer). The classroom conclusion is preserved in the lesson/README/cheat sheet/interview — queue backlog/backlog-per-worker must scale the worker Deployment that consumes the queue, needs an external/custom metrics adapter, and arrives with Day28.
- Resolved a `TASKS.md` status contradiction: the stale unchecked "Day27 Preparation — Kubernetes Workloads" block is now recorded as completed history (Day27 = Completed, Day28 = Planned/Next).
- Added real Markdown cross-links from `docs/devops/day27-kubernetes-workloads.md` (previous lesson, engineering artifact, cheat sheet, interview, roadmap/curriculum).
- Corrected imprecise wording: an Ingress resource declares Host/Path/TLS intent while the Ingress Controller implements routing and commonly performs TLS termination.
- Updated `examples/kubernetes/rag-platform/validate_chart.py` to check the single image reference, the HPA-guarded `spec.replicas`, and the absence of a queue-backlog worker metric; its output no longer hardcodes "helm not installed" and instead states "helm lint/template: not run by this validation script".

### Notes

- Validation actually performed: `git diff --check` clean; `validate_chart.py` PASS (19 structural/values checks, including image `.reference`, HPA-guarded replicas, and no queue metric). `helm` is not installed and no Kubernetes API server is available, so `helm lint`, `helm template`, schema/admission, and all runtime validation were NOT run / NOT verified and no result is claimed.
- Did not rewrite Day01-Day26, did not start or expand Day28, and did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, or `LESSON_TEMPLATE_v2.md`. Historical CHANGELOG entries (including the originally-correct Day27 Planned records) are unchanged.

---

## v0.1.47 — Day27 Kubernetes Workloads Documentation

Date: 2026-07-17

### Added

- Added `docs/devops/day27-kubernetes-workloads.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day26->Day27 mental-model evolution).
- Added the `examples/kubernetes/rag-platform/` teaching-only Helm chart: `Chart.yaml`, base/dev/prod `values*.yaml`, `templates/` (`_helpers.tpl`, configmap, deployment with Rolling Update, service, ingress, `autoscaling/v2` hpa, headless-service, statefulset), and a static-only `validate_chart.py`.
- Added Day27 review material to `cheat_sheets/devops.md`.
- Added Day27 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/kubernetes/README.md` with the Day27 chart layout, validation ladder, prerequisites, and security boundaries.
- Updated `examples/README.md` to index the Day27 Helm chart.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day27 completed (Day28 left Planned).
- Updated `PROJECT_STATUS.md` to mark Day27 completed and set Next to Day28.
- Updated `TASKS.md` with completed Day27 tasks and Day28 preparation.
- Updated `README.md` and `AGENTS.md` progress markers (last completed Day27, next Day28).
- Updated `CHANGELOG.md` with the Day27 repository update.

### Notes

- Day27 extends the Day26 foundation into production workload management: Ingress as L7 Host/Path/TLS routing to Services (resource declares, controller implements); HPA (`autoscaling/v2`) updating desired replicas on a scale target from meaningful pressure (CPU vs queue backlog, bounded by upstream capacity); Deployment Rolling Update with `maxSurge`/`maxUnavailable` distinguished from rollback and Blue-Green; StatefulSet stable identity + per-Pod PVC + headless Service + ordered lifecycle (explicitly NOT database replication/HA); and Helm templates vs Values vs Release with a lint/template/API/runtime validation ladder.
- Preserved the actual classroom record, including the student's Chinese and English answers and the reasonable errors and corrections (Rolling Update called a rollback strategy; three PVCs mistaken for three data copies; Helm assumed to auto-roll back; a Blue-Green plan offered for a Rolling Update; HPA described as directly scaling Pods).
- Security/scope honesty: the chart is teaching-only and not deployable as-is. Sensitive values are referenced via `existingSecret` (never inlined in any values file); no real credential, token, certificate, or verified/represented-as-verified image digest is committed; images use the non-pullable `example.invalid` TLD with a mutable `:replace-with-verified-digest` tag. Readiness 200 is not business success; a StatefulSet is not HA; deleting v2 Pods is not a rollback.
- Validation: `validate_chart.py` ran and passed deterministic static checks (Chart/values YAML parse; Deployment selector == Pod template labels == Service selector via a shared helper; HPA `scaleTargetRef` and Ingress backend use the same fullname helper as the Deployment/Service; `networking.k8s.io/v1`, `autoscaling/v2`, `apps/v1`; Rolling Update `maxSurge`/`maxUnavailable`; StatefulSet `volumeClaimTemplates`; headless `clusterIP: None`; CPU HPA has a CPU request; sensitive values referenced not inlined; non-pullable images). `helm` is not installed in this environment, so `helm lint` and `helm template` were NOT run; with no Kubernetes API server, schema/admission and all runtime validation (Ingress/DNS/TLS routing, HPA scaling, Rolling Update, rollback, PVC provisioning, StatefulSet lifecycle, PostgreSQL replication/failover, backups) were NOT performed and no result is claimed.
- Ingress Controller, DNS, load balancer, TLS material, metrics adapters, and PostgreSQL HA/backup are documented as external prerequisites, not implemented. Day28 (FastAPI/Celery/Redis/PostgreSQL/object storage/queue/monitoring/observability) is labeled a future connection. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day26 lesson body.

---

## v0.1.46 — Roadmap Status Consistency Fix

Date: 2026-07-17

### Changed

- Fixed `ROADMAP.md` Phase 1 table: converted it to the same three-column `Status` format as Phase 2 and marked Day01-Day14 all `✅ Completed`, removing the stale `⏳ Day02` current-lesson marker. Topics and order are unchanged. Phase 2 remains Day15-Day26 Completed, Day27 and Day28 Planned. Now consistent with `CURRICULUM.md`, `PROJECT_STATUS.md`, `TASKS.md`, `README.md`, and `AGENTS.md`.

---

## v0.1.45 — Day26 Review Fixes

Date: 2026-07-17

### Changed

- Fixed `TASKS.md` status consistency: `Current Phase` is now `Phase 2 — Engineering Foundations`, and the Phase 2 Roadmap marks Day26 Completed (Day27 and Day28 remain Planned), removing the Day26 Planned-vs-Completed contradiction.
- Updated the stale repository entry points: `README.md` now shows Phase 2, last completed Day26, next Day27; `AGENTS.md` Current Progress replaces the outdated "Next Lesson: Mutable vs Immutable" with Phase 2 / Day26 completed / Day27 next (engineering and teaching rules unchanged).
- Corrected the Deployment/scheduler responsibility in `docs/devops/day26-kubernetes-foundations.md`: the Deployment/ReplicaSet controller creates or maintains replacement Pods, and kube-scheduler assigns unscheduled Pods to Nodes (the Deployment does not schedule).
- Replaced the invalid `REPLACE_WITH_*` image strings in `examples/kubernetes/ai-backend-baseline.yaml` with syntactically valid, non-pullable OCI references on the reserved `.invalid` TLD (`example.invalid/acme/rag-api:replace-with-verified-digest`, `example.invalid/acme/log-sidecar:replace-with-verified-digest`); comments state the `:replace-...` tag is mutable, not immutable or verified, and must be swapped for a CI-verified `@sha256` digest before deploy. Synced `examples/kubernetes/README.md`.
- Made static validation reproducible: added `examples/kubernetes/validate_manifest.py` (PyYAML-only) and documented an isolated dependency install; the README now shows the actual PASS output.

### Notes

- Static validation actually run: four YAML documents (ConfigMap/Secret/Deployment/Service); Deployment selector == Pod template labels; Service selector == Pod template labels; `replicas == 3`; Service `targetPort` matches a container named port; the API container references the ConfigMap and the Secret; the logging sidecar does NOT reference the Secret — all PASS.
- No Kubernetes API server was available, so `kubectl` schema/admission validation was NOT completed and no Kubernetes runtime result (Pod Ready, Service DNS, Secret injection, Pod replacement, rollback) is claimed.
- Scope unchanged: Day26 is not rewritten and Day27 is not started. No real secret, key, or verified image digest is committed. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day25 lesson body.

---

## v0.1.44 — Day26 Kubernetes Foundations Documentation

Date: 2026-07-17

### Added

- Added `docs/devops/day26-kubernetes-foundations.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day25->Day26 mental-model evolution).
- Added `examples/kubernetes/ai-backend-baseline.yaml` (ConfigMap `rag-api-config`, Secret template `rag-api-secrets` with placeholders only, Deployment `rag-api` with 3 replicas and a FastAPI + logging-sidecar Pod template, Service `rag-api`).
- Added `examples/kubernetes/README.md` (object model, static-vs-runtime validation, security boundaries, and runtime limitations).
- Added Day26 review material to `cheat_sheets/devops.md`.
- Added Day26 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day26 Kubernetes example.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day26 completed (Day27 left Planned).
- Updated `PROJECT_STATUS.md` to mark Day26 completed and set Next to Day27.
- Updated `TASKS.md` with completed Day26 tasks and Day27 preparation.
- Updated `CHANGELOG.md` with the Day26 repository update.

### Notes

- Day26 moves from one-time container startup and manual deployment operations to declarative desired state and continuous reconciliation: desired state vs a one-time command (observe -> diff -> act), Pod as the smallest deployable unit of one or more tightly coupled containers (Pod != container; co-locate only shared fate), Deployment as a Pod template + replica count that recreates replicas but does not schedule (the scheduler picks the Node), Service as stable label-based discovery for changing Pods, ConfigMap as non-sensitive runtime config that keeps the verified image digest unchanged, and Secret as sensitive data requiring controlled access.
- Preserved the actual classroom record, including the student's Chinese and English answers, the reasonable errors (for example "separate Pods imply manual operation", "Deployment schedules Pods", and Base64 `解密` corrected to `解码`), and all material misconceptions and corrections.
- Security/scope honesty: `stringData` is plaintext in the manifest and holds placeholders only; Base64 is encoding, not encryption; a Secret is not an automatic vault. No real key, password, token, certificate, private endpoint, or verified/represented-as-verified image digest is committed; image fields are `REPLACE_*` placeholders supplied out of band. `replicas: 3` is not three business-ready replicas, and `/health` 200 is not business success.
- Validation: static checks ran (YAML parses as four documents ConfigMap/Secret/Deployment/Service; Deployment selector == Pod template labels == Service selector `app: rag-api`; `replicas == 3`). No Kubernetes API server was available, so `kubectl` client/schema validation was NOT completed and no `kubectl apply`, Pod scheduling, image pull, container startup, ConfigMap/Secret injection, Service DNS/routing, Pod replacement, Secret rotation, business smoke test, or failure/rollback runtime result is claimed. Markdown was checked and links to the example resolve.
- Ingress, Autoscaling, Rolling Update, StatefulSet, and Helm are labeled as Day27 future connections, not taught or validated in Day26. Did not modify `prompts/master-prompt.md`, `prompts/teaching-session-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day25 lesson body.

---

## v0.1.43 — Day25 Deployment Foundations Documentation

Date: 2026-07-16

### Added

- Added `docs/devops/day25-deployment-foundations.md` (LESSON_TEMPLATE_v2; Master Prompt v3.2 knowledge-continuity chain and a Day24->Day25 mental-model evolution).
- Added `examples/deployment/nginx/nginx.conf.example` (reverse proxy + TLS termination, HTTP->HTTPS 308, trusted proxy headers, blue-green `api_v2` upstream, AI streaming location).
- Added `examples/deployment/README.md` (request path, zero-downtime blue-green runbook, rollback, and identity notes).
- Added Day25 review material to `cheat_sheets/devops.md`.
- Added Day25 interview questions to `interview/devops.md`.

### Changed

- Updated `examples/README.md` to index the Day25 deployment example.
- Updated `CURRICULUM.md` and `ROADMAP.md` to mark Day25 completed.
- Updated `PROJECT_STATUS.md` to mark Day25 completed and set Next to Day26.
- Updated `TASKS.md` with completed Day25 tasks and Day26 preparation.
- Updated `CHANGELOG.md` with the Day25 repository update.

### Notes

- Day25 turns one CI-verified immutable image into a safely reachable, observable, reversible production service: stable public entry (Domain/DNS/Nginx :443), reverse proxy (listen/server_name/proxy_pass), TLS as confidentiality + integrity + server authentication (terminating at Nginx), HTTP->HTTPS 308 (and why it cannot protect an already-sent credential), certificate lifecycle and Nginx master/worker (reload vs restart), trusted proxy context (header != identity), promoting the exact immutable digest, API blue-green with verify/switch/observe/drain/rollback, PostgreSQL Expand-Migrate-Contract, compatible worker rollout, serialized deployment with a least-privilege short-lived identity, AI streaming (buffering vs caching, four timeouts, heartbeat), and non-atomic DNS TTL.
- Preserved the actual classroom record, including the student's Chinese and English answers, the imperfect wording (for example the accidental "quantity gate" corrected to "quality gate", and the GitHub Actions `${{ }}` vs Nginx `$variable` confusion), and all material misconceptions and corrections.
- The Nginx artifact is example-only: reserved `example.com` domain, placeholder certificate paths, no committed certificate, private key, secret, credential, or business/medical data. No GitHub Actions expressions are used in Nginx.
- Validation: `nginx` is not available in this environment, so `nginx -t` was NOT run and no successful Nginx validation is claimed; the configuration was reviewed statically. The Markdown was checked, links to the example resolve, and no secrets are present.
- `prompts/teaching-session-prompt.md` already exists in the repository (the separate live-teaching standard) and was left unchanged. Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day24 lesson body.

---

## v0.1.42 — Day24 Review: Portable, Restrictive Local Secret Setup

Date: 2026-07-14

### Changed

- Made the local secret-file setup in `examples/docker/compose/README.md` portable across Bash and zsh and more restrictive: replaced the `read`-with-prompt-option form (which fails in zsh with `read: -p: no coprocess`) with `printf '...' >&2` + `IFS= read -rs`, and added `chmod 700 .secrets` and `umask 077` so secret files are created owner-only (`600`) in a `700` directory.
- Updated the Commands section to reference the portable prompt flow.

### Notes

- Documentation-only fix; no secret value (real or fake) is present, and no course content or Compose YAML changed.
- Did not modify `prompts/master-prompt.md`, `LESSON_TEMPLATE_v2.md`, or any Day01-Day24 lesson body.

---

## v0.1.41 — Day24 Review Fixes

Date: 2026-07-14

### Changed

- Removed the two placeholder secret values (an example PostgreSQL password and an example OpenAI key) from `examples/docker/compose/README.md`; the secret files are now created via an interactive prompt flow so no password or API-key value is written into the repository.
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
