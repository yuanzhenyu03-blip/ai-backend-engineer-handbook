# Day23–Day28 Production Artifact Templates

> Part of the **Production Engineering Second Brain**. See [README.md](README.md).
> Companion docs: [Super Cheat Sheet](Day23-Day28-Production-Super-CheatSheet.md) · [Architecture & Failure Map](Day23-Day28-Architecture-Failure-Map.md) · [Interview Q&A](Day23-Day28-Interview-QA.md) · [One Page](Day23-Day28-OnePage.md)

This is the **execution** layer: the reusable artifact patterns from Day23–Day28, extracted from the repository's real example files. For the *why*, see the [Super Cheat Sheet](Day23-Day28-Production-Super-CheatSheet.md).

**Honesty rules honored here.** Every template links to its source example. Every one of these examples is a **teaching / conceptual template** in this handbook repo (there is no runnable FastAPI app, domain, certificate, cluster, or provider account), so unless stated otherwise: `Teaching-only / Conceptual-only · Not production-ready · Runtime not verified`. Placeholder images use the reserved `.invalid` TLD or mutable `:replace-...` tags; `example.com` is a reserved example domain; secrets are placeholders mounted out of band. No real secret, token, password, domain credential, or presigned URL appears. Code snippets are trimmed to the core (< 40 lines); open the source file for the full artifact.

---

## Template 1 — Cache-friendly FastAPI Dockerfile (Day23)

### Source file
[examples/docker/fastapi/Dockerfile](../../examples/docker/fastapi/Dockerfile) · Lesson [Day23](../devops/day23-docker-fundamentals.md)

### Problem it solves
Package a FastAPI app + its runtime into one immutable, cache-efficient image; run as non-root.

### When to use
Any Python service you deploy as a container.

### When NOT to copy mechanically
Different Python version/manager, GPU base, or a monorepo layout; adjust before use.

### Fields to change
Base image (and optionally `@sha256:<digest>`), `requirements.txt`, `app` package, health path, port, UID.

### Security boundary
`.dockerignore` excludes `.env`/secrets/caches; secrets injected at runtime, never baked; non-root user; digest pin is optional but stronger for supply chain (use a real digest).

### Core
```dockerfile
FROM python:3.12-slim              # controlled but MUTABLE tag; pin @sha256 for reproducibility
WORKDIR /app
COPY requirements.txt .            # deps first: install layer caches when manifest is unchanged
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app                     # app code last: changes most often
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser                       # least privilege
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]  # 0.0.0.0, not loopback
```

### Static validation
Reviewed statically only (dependency-before-code order, non-root, `0.0.0.0`).

### Runtime prerequisites
A real `requirements.txt` + `app.main:app` and a Docker daemon.

### Has the repo actually run it?
No — `Runtime not verified` (this repo has no FastAPI app).

---

## Template 2 — Immutable Replacement (Docker runtime pattern) (Day23)

### Source file
Lesson [Day23](../devops/day23-docker-fundamentals.md) (Concept 3 / Exercise 8; no standalone script file)

### Problem it solves
Ship a change without editing a live container (which leaves no audit/rollback).

### When to use
Every production change to a containerized service.

### When NOT to copy mechanically
When an orchestrator (Compose/Kubernetes) performs the replacement — use its rollout instead of manual steps.

### Fields to change
Image reference, container name, health path/port.

### Security boundary
Never `docker exec` a fix into production; the change would live only in the writable layer.

### Core
```text
update version-controlled inputs
-> docker build (new immutable image)  -> test / scan
-> docker run the NEW container         -> health check + smoke test
-> switch traffic to the new container
-> remove the OLD container             (keep a rollback path to the previous image)
```

### Static validation
Conceptual sequence from the lesson.

### Runtime prerequisites
A registry/host and a health endpoint.

### Has the repo actually run it?
No — conceptual sequence, `Runtime not verified`.

---

## Template 3 — Compose Multi-service Model (Day24)

### Source file
[examples/docker/compose/compose.yaml](../../examples/docker/compose/compose.yaml) · Lesson [Day24](../devops/day24-docker-compose.md)

### Problem it solves
Declare a reproducible API + Worker + Redis + PostgreSQL stack on one host, with least access.

### When to use
Local dev, integration tests, CI dependencies, controlled single-host systems (with added controls).

### When NOT to copy mechanically
A public high-availability service — Compose lacks multi-node scheduling/self-healing/autoscaling.

### Fields to change
Image/build path, env values, DB/user names, published port, secret file paths.

### Security boundary
Only the API publishes a host port; Redis/PostgreSQL are internal; network segmentation (Redis and PostgreSQL share no network); the OpenAI key is granted only to the Worker; secrets are files under `./.secrets/` (not committed).

### Core (trimmed)
```yaml
name: rag-app
services:
  api:
    build: ../fastapi
    image: rag-app:local
    ports: ["8000:8000"]           # the ONLY published host port
    environment:
      REDIS_URL: redis://redis:6379/0   # internal calls use service DNS, not localhost
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password   # app must READ this path
    secrets: [postgres_password]
    networks: [queue_network, database_network]
    depends_on:
      postgres: { condition: service_healthy }   # wait for READY, not just started
  # worker (same image, different command) + redis + postgres ... (see source)
networks: { queue_network: , database_network: }   # redis & postgres share NO network
volumes: { postgres_data: }
secrets:
  postgres_password: { file: ./.secrets/postgres_password.txt }   # NOT committed
```

### Static validation
Meaningful check is `docker compose config` (static model validation) only.

### Runtime prerequisites
A runnable app image and local secret files (see the compose README).

### Has the repo actually run it?
No — `docker compose up` was NOT executed; `Runtime not verified`.

---

## Template 4 — Healthcheck + Retry Boundary (Day24)

### Source file
[examples/docker/compose/compose.yaml](../../examples/docker/compose/compose.yaml) (healthchecks) · Lesson [Day24](../devops/day24-docker-compose.md) (Concept 2)

### Problem it solves
Distinguish "started" from "ready" so dependents wait for a real probe (and keep app retry for later failures).

### When to use
Any service with a dependency that initializes slowly (databases, brokers).

### When NOT to copy mechanically
A healthcheck does not repair/restart the service, and it does not replace application-level retry — keep both.

### Fields to change
Probe command per service (`redis-cli ping` vs `pg_isready`), timing fields.

### Security boundary
Probe an application capability, not mere process existence.

### Core
```yaml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s ; timeout: 3s ; start_period: 5s ; retries: 5
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
api:
  depends_on:
    redis:    { condition: service_healthy }
    postgres: { condition: service_healthy }   # + bounded application retry at runtime
```

### Static validation
YAML shape reviewed; `start_period`/`interval`/`timeout`/`retries` semantics per the lesson.

### Runtime prerequisites
Running Redis/PostgreSQL containers.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 5 — Base + Development Override (Day24)

### Source file
[examples/docker/compose/compose.dev.yaml](../../examples/docker/compose/compose.dev.yaml) · Lesson [Day24](../devops/day24-docker-compose.md) (Concept 10)

### Problem it solves
Keep one portable production-style base and put dev-only ergonomics (source mount + `--reload`) in an override.

### When to use
Local development on top of a production-shaped `compose.yaml`.

### When NOT to copy mechanically
Never merge the dev override into production (host source mounts must not ship).

### Fields to change
Bind-mount source path, reload command.

### Security boundary
Dev override is not production; it is merged explicitly with `-f`.

### Core
```yaml
services:
  api:
    command: ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload"]  # dev only
    volumes: ["../fastapi/app:/app/app"]   # host-owned source visible in the container
# merge: docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

### Static validation
Reviewed statically (Compose file merge and Uvicorn reload are separate mechanisms).

### Runtime prerequisites
The base stack.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 6 — Nginx Reverse Proxy + TLS + Streaming (Day25)

### Source file
[examples/deployment/nginx/nginx.conf.example](../../examples/deployment/nginx/nginx.conf.example) · Lesson [Day25](../devops/day25-deployment-foundations.md)

### Problem it solves
Stable public entry: 308 to HTTPS, TLS termination, trusted proxy headers, and AI streaming tuning.

### When to use
Fronting an internal FastAPI backend on a single host.

### When NOT to copy mechanically
This is a `server`-block **fragment** (no `events`/`http` context) — it cannot be passed to `nginx -c` directly; include it inside an existing `http {}`. Do not disable buffering globally (only for streaming).

### Fields to change
`server_name`, real cert/key paths (out of band), upstream target (`api_v2:8000`), streaming location.

### Security boundary
`example.com` and cert paths are placeholders — **no certificate/key/secret committed**; a proxy header is metadata, not identity (pair with trusted-proxy policy + backend isolation + real auth).

### Core (trimmed)
```nginx
server { listen 80; server_name api.example.com;
  return 308 https://$host$request_uri; }          # does NOT protect a token already sent over HTTP
server { listen 443 ssl; server_name api.example.com;
  ssl_certificate /etc/nginx/certs/fullchain.pem;   # placeholder path
  ssl_certificate_key /etc/nginx/certs/privkey.pem; # placeholder path
  location / {
    proxy_pass http://api_v2:8000;                  # service DNS, not localhost/IP
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }
  location /chat {                                   # AI streaming: time-to-first-token
    proxy_pass http://api_v2:8000; proxy_http_version 1.1;
    proxy_buffering off; proxy_cache off;            # buffering != caching
    proxy_read_timeout 300s; proxy_send_timeout 300s; } }
```

### Static validation
Reviewed statically. `nginx -t` also needs readable cert files and a resolvable `api_v2` upstream — NOT available here.

### Runtime prerequisites
A real domain, certificate, and upstream.

### Has the repo actually run it?
No — `nginx -t` NOT executed; do not claim it passed. `Runtime not verified`.

---

## Template 7 — Blue-Green Deployment + Rollback Runbook (Day25)

### Source file
[examples/deployment/README.md](../../examples/deployment/README.md) · Lesson [Day25](../devops/day25-deployment-foundations.md) (Concepts 8–13)

### Problem it solves
Zero-downtime API release with verify → switch → observe → drain → rollback.

### When to use
Promoting a verified digest into live traffic on one host.

### When NOT to copy mechanically
Do not reuse this for the worker (competing-consumer rollout) or for PostgreSQL schema (Expand-Migrate-Contract).

### Fields to change
Digest, Nginx upstream names, drain window, observation thresholds.

### Security boundary
Serialize with `concurrency: { group: production, cancel-in-progress: false }`; use a least-privilege short-lived deploy identity.

### Core
```text
verified digest -> approval -> acquire lock -> inspect actual state -> pull exact digest
-> start Green (no prod traffic) -> verify Green DIRECTLY -> nginx -t -> graceful switch
-> observe real traffic + drain Blue -> if bad: restore Nginx target to Blue, reload, drain v2
-> if good: end rollback window, remove Blue -> record final state -> release lock
```

### Static validation
Conceptual runbook from the lesson.

### Runtime prerequisites
Two running backends and an editable Nginx upstream.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 8 — Kubernetes Deployment + Service + ConfigMap + Secret (Day26)

### Source file
[examples/kubernetes/ai-backend-baseline.yaml](../../examples/kubernetes/ai-backend-baseline.yaml) · Lesson [Day26](../devops/day26-kubernetes-foundations.md)

### Problem it solves
Declare 3 reconciled replicas (API + logging sidecar) with stable discovery and externalized config/secrets.

### When to use
A stateless service that needs continuous replica maintenance and stable access.

### When NOT to copy mechanically
Placeholder `.invalid` images and PLACEHOLDER `stringData` must be replaced; the sidecar must not get credentials.

### Fields to change
Image → CI-verified `@sha256` digest; ConfigMap values; Secret values (out of band); labels.

### Security boundary
`Base64 = encoding, not encryption`; a Secret is not an auto-vault (needs RBAC + encryption-at-rest + audit + rotation); only the API container references the Secret.

### Core (trimmed)
```yaml
kind: Deployment
spec:
  replicas: 3
  selector: { matchLabels: { app: rag-api } }     # selector == template labels == Service selector
  template:
    metadata: { labels: { app: rag-api } }
    spec:
      containers:
        - name: api
          image: example.invalid/acme/rag-api:replace-with-verified-digest  # non-pullable placeholder
          envFrom: [{ configMapRef: { name: rag-api-config } }]
          env:
            - name: OPENAI_API_KEY
              valueFrom: { secretKeyRef: { name: rag-api-secrets, key: OPENAI_API_KEY } }
        - name: log-sidecar                          # shares Pod/volume, NO credentials
          image: example.invalid/acme/log-sidecar:replace-with-verified-digest
---
kind: Service
spec: { selector: { app: rag-api }, ports: [{ name: http, port: 80, targetPort: http }] }
```

### Static validation
Structure reviewed; see [examples/kubernetes/validate_manifest.py](../../examples/kubernetes/validate_manifest.py) (deterministic static checks).

### Runtime prerequisites
A cluster and real pullable images.

### Has the repo actually run it?
No — no `kubectl apply` / Pod Ready / routing executed. `Runtime not verified`.

---

## Template 9 — Ingress Pattern (Day27)

### Source file
[examples/kubernetes/rag-platform/templates/ingress.yaml](../../examples/kubernetes/rag-platform/templates/ingress.yaml) · Lesson [Day27](../devops/day27-kubernetes-workloads.md) (Concept 1)

### Problem it solves
L7 Host/Path/TLS routing to a Service (the resource declares intent; a controller implements it).

### When to use
Exposing an HTTP service publicly with TLS.

### When NOT to copy mechanically
An Ingress resource alone does nothing without an Ingress Controller; routing `/admin` is not authentication.

### Fields to change
Host, `ingressClassName`, existing TLS Secret name, path.

### Security boundary
References an existing TLS Secret — never embeds a certificate/key.

### Core (Helm-templated)
```yaml
kind: Ingress
spec:
  ingressClassName: {{ .Values.ingress.className }}
  tls:
    - hosts: [ {{ .Values.ingress.host | quote }} ]
      secretName: {{ .Values.ingress.tlsSecretName }}   # existing Secret reference
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: {{ .Values.ingress.path }}
            pathType: {{ .Values.ingress.pathType }}
            backend: { service: { name: {{ include "rag-platform.fullname" . }}, port: { name: http } } }
```

### Static validation
`helm lint` / `helm template` render only; see [validate_chart.py](../../examples/kubernetes/rag-platform/validate_chart.py).

### Runtime prerequisites
An Ingress Controller, DNS, and a real TLS Secret.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 10 — HPA + Rolling Update (Day27)

### Source file
[hpa.yaml](../../examples/kubernetes/rag-platform/templates/hpa.yaml) + [deployment.yaml](../../examples/kubernetes/rag-platform/templates/deployment.yaml) · Lesson [Day27](../devops/day27-kubernetes-workloads.md) (Concepts 2–3)

### Problem it solves
Scale desired replicas on a signal and replace versions gradually while preserving availability.

### When to use
A stateless workload that must absorb load and roll out without an outage.

### When NOT to copy mechanically
This HPA scales the **API on CPU**; queue-backlog scaling belongs to the **worker** consumer (Day28). With an HPA enabled, don't hard-code `spec.replicas`. `maxUnavailable: 0` needs surge capacity.

### Fields to change
`minReplicas`/`maxReplicas`, CPU target, `maxSurge`/`maxUnavailable`, CPU requests.

### Security boundary
None specific; cap `maxReplicas` to upstream provider capacity to avoid a 429 storm.

### Core
```yaml
# Deployment
spec:
  {{- if not .Values.hpa.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  strategy: { type: RollingUpdate, rollingUpdate: { maxSurge: 1, maxUnavailable: 0 } }
---
# HPA (autoscaling/v2) — HPA sets desired replicas; the Deployment reconciles Pods
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef: { kind: Deployment, name: {{ include "rag-platform.fullname" . }} }
  minReplicas: {{ .Values.hpa.minReplicas }} ; maxReplicas: {{ .Values.hpa.maxReplicas }}
  metrics: [{ type: Resource, resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } } }]
```

### Static validation
Render-only; an empty `metrics:` would silently default to 80% CPU — the chart always renders one explicit CPU metric.

### Runtime prerequisites
A Metrics Server (CPU) or a custom/external metric adapter (queue backlog), and surge capacity.

### Has the repo actually run it?
No — no scaling/rollout executed. `Runtime not verified`.

---

## Template 11 — StatefulSet + Headless Service (Day27)

### Source file
[statefulset.yaml](../../examples/kubernetes/rag-platform/templates/statefulset.yaml) + [headless-service.yaml](../../examples/kubernetes/rag-platform/templates/headless-service.yaml) · Lesson [Day27](../devops/day27-kubernetes-workloads.md) (Concept 4)

### Problem it solves
Stable Pod identity + per-Pod PVC + ordered lifecycle + stable network identity.

### When to use
Workloads that need identity-to-storage mapping (e.g. a database Pod set).

### When NOT to copy mechanically
`StatefulSet != database HA`: no WAL/streaming replication, leader election, failover, fencing, routing, or backup/PITR. Three PVCs = three isolated disks, not three data copies. Production PostgreSQL needs an operator/managed service.

### Fields to change
`replicas`, storage size/class, image digest, port.

### Security boundary
Storage isolation/identity only; data safety is a separate database-aware problem.

### Core (trimmed)
```yaml
kind: Service                       # headless: stable network identity
spec: { clusterIP: None, selector: {...}, ports: [{ name: postgres, port: 5432, targetPort: postgres }] }
---
kind: StatefulSet
spec:
  serviceName: {{ include "rag-platform.postgres.fullname" . }}
  replicas: {{ .Values.postgres.replicas }}
  volumeClaimTemplates:             # per-Pod PVC (isolation/identity, NOT replication)
    - metadata: { name: data }
      spec: { accessModes: [ReadWriteOnce], resources: { requests: { storage: {{ .Values.postgres.storage.size | quote }} } } }
```

### Static validation
Render-only.

### Runtime prerequisites
A cluster with a StorageClass/provisioner.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 12 — Helm Templates + Values + Validation Ladder (Day27)

### Source file
[examples/kubernetes/rag-platform/](../../examples/kubernetes/rag-platform/) (`values.yaml`, `values-dev.yaml`, `values-prod.yaml`) · Lesson [Day27](../devops/day27-kubernetes-workloads.md) (Concept 5)

### Problem it solves
Package the whole workload once and render consistent, revisioned, per-environment releases.

### When to use
Multi-environment deployment of the same object set.

### When NOT to copy mechanically
Every object is a template (not just ConfigMap/Secret); never put real Secrets in Values (release history/rendered manifests can leak them); Helm does not auto-roll back by default.

### Fields to change
Per-environment Values: host, image reference, replicas/resources, HPA targets, storage, existing Secret name.

### Security boundary
Template Secret **references** (`existingSecret`), not plaintext; use an external Secret manager / Sealed Secrets.

### Core (commands + validation ladder)
```bash
helm lint ./rag-platform                              # structure/syntax
helm template ./rag-platform -f values-prod.yaml      # render Values -> YAML
# server-side dry run -> API versions/schema/policy (needs a cluster)
helm upgrade --install rag-platform ./rag-platform -f values-prod.yaml --atomic --wait --timeout 10m
helm history rag-platform ; helm rollback rag-platform 4 --wait --timeout 10m   # restore a revision
```

### Static validation
`helm lint` / `helm template` prove structure/render only — NOT runtime or business success (per the lesson and the chart README).

### Runtime prerequisites
Helm + a cluster; real images/Secrets.

### Has the repo actually run it?
No — only deterministic static checks in `validate_chart.py`; `Static validation != runtime success`.

---

## Template 13 — Production AI Backend Responsibility Blueprint (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md)

### Problem it solves
Assign one clear responsibility per component so an accepted job survives retry and Pod replacement.

### When to use
Designing any async, provider-calling AI backend.

### When NOT to copy mechanically
It is a conceptual blueprint, not a runnable service; adapt models/queues to your stack.

### Fields to change
Component choices (broker, storage, DB), stage names, provenance fields.

### Security boundary
Short-lived scoped access; server-controlled object keys; least privilege per component; no secrets/customer data committed.

### Core (responsibility map)
```text
FastAPI        -> accept/expose: authn/authz, presigned URL, verify, create Job (+Outbox), 202 + job_id, status
Celery worker  -> execute: parse/chunk/embed/index; retry/ACK; NOT the source of truth
Queue / Redis  -> transport/cache; NOT durable truth
PostgreSQL     -> durable truth: Job lifecycle, metadata, Outbox, events, checkpoints, leases, provenance, refs
Object Storage -> large bytes: immutable originals + derived artifacts; scoped access
Monitoring     -> detect known signals; Observability -> explain WHY (stable job_id)
```

### Static validation
Conceptual review only.

### Runtime prerequisites
The full stack (planned future validation is listed in the blueprint).

### Has the repo actually run it?
No — `Conceptual-only. Not production-ready. Runtime not verified.`

---

## Template 14 — Job & Upload-Session State Machines (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) (§3) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md) (Concepts 1, 6, 10)

### Problem it solves
Separate the untrusted upload lifecycle from the durable job lifecycle, with a repair path.

### When to use
Any large-file → async-processing flow.

### When NOT to copy mechanically
Create the Job only after server-side verification; keep the two machines distinct.

### Fields to change
Stage names, terminal states.

### Security boundary
The client "complete" callback is untrusted; bind the Job to an immutable object version (avoid TOCTOU).

### Core
```text
Upload Session: INITIATED -> UPLOADING -> VERIFIED | FAILED | EXPIRED
Job:            QUEUED -> RUNNING -> RETRY_WAIT -> (RUNNING ...) -> SUCCEEDED | FAILED_TERMINAL
Repair path:    SUCCEEDED -> INVALIDATED -> REPROCESSING -> SUCCEEDED   (event history preserved)
Durable stages: UPLOADED -> PARSED -> CHUNKED -> EMBEDDING -> INDEXED -> SUCCEEDED
```

### Static validation
Conceptual; states from the blueprint.

### Runtime prerequisites
A DB schema implementing the states.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 15 — Transactional Outbox Flow (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) (§5) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md) (Concept 3)

### Problem it solves
Close the DB→queue crash gap without pretending two systems can be written atomically.

### When to use
Whenever a durable record must reliably trigger a queue message.

### When NOT to copy mechanically
The Outbox is still at-least-once — pair it with idempotent consumers; never claim exactly-once.

### Fields to change
Event table columns, relay batch size/interval.

### Security boundary
Relay runs with least privilege; do not log payload secrets.

### Core
```text
ONE PostgreSQL transaction: INSERT Job (QUEUED) + INSERT Outbox event (sent_at = NULL)
Relay: SELECT outbox WHERE sent_at IS NULL -> publish to Queue -> mark sent_at
Crash after publish, before mark -> republish (duplicate) -> absorbed by idempotent worker
Fallback: reconciliation scanner re-publishes stale QUEUED jobs
=> at-least-once delivery + idempotent processing
```

### Static validation
Conceptual logic from the blueprint.

### Runtime prerequisites
PostgreSQL + a broker + a relay process.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 16 — Idempotent Worker Flow (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) (§5) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md) (Concept 4)

### Problem it solves
Prevent duplicate durable effects under at-least-once delivery and worker crashes.

### When to use
Every queue consumer that writes durable state or calls a paid provider.

### When NOT to copy mechanically
A read-then-write check can race — enforce a DB unique constraint; a unique constraint stops duplicate *durable writes*, not a duplicate external call already made.

### Fields to change
Idempotency key tuple, checkpoint stages.

### Security boundary
Use a provider idempotency key for external calls; reconcile dual-write gaps.

### Core
```text
claim work with an owner/lease (expiry allows recovery)
for each stage: check durable checkpoint -> if done, SKIP (idempotent)
idempotency key = (document_id, chunk_hash, model_version)
enforce with a DB UNIQUE constraint + idempotent UPSERT
ACK the queue message ONLY after result + checkpoint are durably recorded
external provider: use provider idempotency key; reconcile if it succeeded before local write
```

### Static validation
Conceptual logic from the blueprint.

### Runtime prerequisites
A DB with unique constraints and a broker with manual ACK.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 17 — Retry Policy + Circuit Breaker (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) (§6) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md) (Concept 7)

### Problem it solves
Recover from provider 429/503/timeouts without a self-inflicted retry storm.

### When to use
Any call to a rate-limited or degradable external provider.

### When NOT to copy mechanically
A max delay alone allows infinite attempts — bound by max attempts and/or an overall deadline, and classify errors.

### Fields to change
Backoff base/cap, jitter, max attempts/deadline, breaker thresholds.

### Security boundary
Do not log provider secrets; persist `provider_request_id` for evidence.

### Core
```text
exponential backoff + JITTER
bound: max attempts AND/OR overall retry deadline
classify: 429 -> honor Retry-After / rate-limit ; 503,timeout -> retry in policy
          400,parse -> terminal ; 401,403,config -> stop + contain globally + alert
global rate limiter / circuit breaker when the provider is degraded
persist: attempt_count, next_retry_at, last_error, retry_deadline, provider_request_id
```

### Static validation
Conceptual policy from the blueprint.

### Runtime prerequisites
A worker runtime with scheduling and a shared breaker.

### Has the repo actually run it?
No — `Runtime not verified`.

---

## Template 18 — Failure / Rollback / Data-Repair Runbook (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) (§7) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md) (Concept 10)

### Problem it solves
Recover from a wrong-model release that passed readiness and persisted bad data.

### When to use
Any incident where compute produced incorrect *persisted* results.

### When NOT to copy mechanically
Compute rollback does NOT repair data; never blind-delete — identify by provenance.

### Fields to change
Provenance fields, index alias/version names.

### Security boundary
Preserve evidence; re-expose only after verification.

### Core
```text
A. Pause/contain bad v2 workers (no new wrong results)
B. Restore known-good v1 desired release; verify model/config + readiness
C. Identify + quarantine/invalidate affected results by provenance
   (job_id, worker_release, processing_version, embedding_model/version, index version, checksum)
D. Idempotently reprocess from immutable originals into a clean/versioned index
E. Verify (counts, dimensions, real RAG quality, errors, latency, cost) -> switch index alias -> resume
=> Compute rollback stops future damage; data repair corrects damage already persisted.
```

### Static validation
Conceptual runbook from the blueprint.

### Runtime prerequisites
Provenance metadata and versioned indexes.

### Has the repo actually run it?
No — no data-repair drill executed. `Runtime not verified`.

---

## Template 19 — Observability Field Set (Day28)

### Source file
[examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md) (§8) · Lesson [Day28](../devops/day28-ai-backend-production-architecture.md) (Concept 9)

### Problem it solves
Correlate an incident across components and keep metrics scalable.

### When to use
Structuring logs/traces/metrics for any async system.

### When NOT to copy mechanically
Do not use `job_status` to correlate (it changes and is shared); do not use `job_id` as a metric label (high cardinality).

### Fields to change
Service names, safe error codes.

### Security boundary
Never log document content, presigned URLs, keys, tokens, passwords, or unnecessary personal data.

### Core
```text
Correlate on STABLE job_id. Scopes: trace_id (path), attempt_id/count (app), broker task_id (delivery,
  may change), provider_request_id (provider evidence).
Structured log fields: service, job_id, trace_id, task_id, attempt_id/count, stage, state, duration, safe_error_code
Metrics: LOW-cardinality labels only (job_id belongs in logs/traces)
Durable history: jobs.current_status (projection) + append-only job_events (history)
Queue interpretation: depth + oldest-age + throughput (stall vs under-capacity vs burst)
```

### Static validation
Field set from the blueprint.

### Runtime prerequisites
A logging/metrics/tracing pipeline.

### Has the repo actually run it?
No — `Runtime not verified`.

---

# Source Map

| Template | Repository Source |
|---|---|
| 1 Dockerfile | `examples/docker/fastapi/Dockerfile`, `docs/devops/day23-docker-fundamentals.md` |
| 2 Immutable replacement | `docs/devops/day23-docker-fundamentals.md` |
| 3 Compose model | `examples/docker/compose/compose.yaml`, `docs/devops/day24-docker-compose.md` |
| 4 Healthcheck + retry | `examples/docker/compose/compose.yaml`, `docs/devops/day24-docker-compose.md` |
| 5 Base + dev override | `examples/docker/compose/compose.dev.yaml`, `docs/devops/day24-docker-compose.md` |
| 6 Nginx proxy/TLS/streaming | `examples/deployment/nginx/nginx.conf.example`, `docs/devops/day25-deployment-foundations.md` |
| 7 Blue-green runbook | `examples/deployment/README.md`, `docs/devops/day25-deployment-foundations.md` |
| 8 K8s Deployment/Service/Config/Secret | `examples/kubernetes/ai-backend-baseline.yaml`, `docs/devops/day26-kubernetes-foundations.md` |
| 9 Ingress | `examples/kubernetes/rag-platform/templates/ingress.yaml`, `docs/devops/day27-kubernetes-workloads.md` |
| 10 HPA + Rolling Update | `examples/kubernetes/rag-platform/templates/{hpa,deployment}.yaml`, `docs/devops/day27-kubernetes-workloads.md` |
| 11 StatefulSet + headless | `examples/kubernetes/rag-platform/templates/{statefulset,headless-service}.yaml`, `docs/devops/day27-kubernetes-workloads.md` |
| 12 Helm + validation ladder | `examples/kubernetes/rag-platform/`, `docs/devops/day27-kubernetes-workloads.md` |
| 13 Responsibility blueprint | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
| 14 State machines | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
| 15 Transactional Outbox | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
| 16 Idempotent worker | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
| 17 Retry + circuit breaker | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
| 18 Failure/rollback/data-repair | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
| 19 Observability field set | `examples/ai-backend-architecture/README.md`, `docs/devops/day28-ai-backend-production-architecture.md` |
