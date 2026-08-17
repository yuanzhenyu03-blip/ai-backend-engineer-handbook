# Day23–Day28 Production Engineering Super Cheat Sheet

> Part of the **Production Engineering Second Brain**. See [README.md](README.md) for how the five documents fit together.
> Companion docs: [Architecture & Failure Map](Day23-Day28-Architecture-Failure-Map.md) · [Artifact Templates](Day23-Day28-Artifact-Templates.md) · [Interview Q&A](Day23-Day28-Interview-QA.md) · [One Page](Day23-Day28-OnePage.md)

This is the **explanation** layer: recover the mental model of each day fast. It compresses the lessons; it does not replace them. For the full detail see the source lessons linked at each day header, and the existing [DevOps cheat sheet](../../cheat_sheets/devops.md) / [DevOps interview notes](../../interview/devops.md).

## Whole-phase mental model

```text
A running system is not an architecture. Production engineering means assigning, for every change
and every byte: artifact identity, runtime lifecycle, state ownership, network boundary, desired
state, failure boundary, rollback boundary, data repair, monitoring, and observability.
```

The ten engineering judgments this phase builds:

```text
Artifact Identity  -> the exact immutable thing that runs (image digest, not a moving tag).
Runtime Lifecycle  -> build vs run; request vs job; compute vs data.
State Ownership     -> who durably owns each piece of truth (PostgreSQL) vs who transports it.
Network Boundary   -> what is reachable from where; least access, service DNS not localhost.
Desired State      -> declared invariants a controller continuously reconciles.
Failure Boundary   -> where a fault is contained (Pod, Job, network, provider).
Rollback Boundary  -> restore a known-good desired state; do not fight the reconciler.
Data Repair        -> fix what is already persisted; rollback of compute cannot.
Monitoring         -> detect known-abnormal signals against thresholds/SLOs.
Observability      -> explain WHY, correlating on stable identity.
```

## The Day23–Day28 knowledge chain

```text
Day23 Docker Fundamentals        -> package ONE process into an immutable image, run replaceable containers
  -> Day24 Docker Compose         -> declare a reproducible MULTI-service system on ONE host
  -> Day25 Deployment Foundations -> move a verified artifact into production traffic safely & reversibly
  -> Day26 Kubernetes Foundations -> declare desired state; controllers continuously reconcile it
  -> Day27 Kubernetes Workloads   -> route (Ingress), scale (HPA), replace (Rolling Update), keep identity (StatefulSet), package (Helm)
  -> Day28 AI Backend Production  -> assign responsibility, lifecycle, state, failure, and evidence to the whole system
```

Why the chain holds: each day solves the gap the previous one left. One reproducible container cannot express a multi-service system → Compose. A Compose stack that *starts* is not a *safe public* service → Deployment. A manual deploy runbook stops owning state once the script exits → Kubernetes reconciliation. Reconciled Pods still lack routing/scaling/rollout/state/packaging → Workloads. Deployed components are still not an *architecture* with owned state and evidence → AI Backend Production Architecture. Not six tools — one delivery-to-operation chain.

---

# Day23 — Docker Fundamentals

Source: [docs/devops/day23-docker-fundamentals.md](../devops/day23-docker-fundamentals.md) · Artifact: [examples/docker/fastapi/](../../examples/docker/fastapi/)

## One-sentence Mental Model
`Dockerfile -> build -> Image (immutable) -> run -> Container (replaceable process); durable state lives in a volume/external service, and services reach each other by network DNS, never localhost.`

## Why this lesson exists
Day22 promoted an immutable image digest without explaining the image. Day23 fills that gap: the same source behaves differently across Python versions, OS libraries, dependency versions, working dir, env, or startup command. Docker freezes the app + user-space runtime into one repeatable unit.

## Engineering Problem it solves
"Works on my machine" — the runtime is captured in a versioned Dockerfile (IaC), so the tested image is the run image.

## Core responsibility map
```text
Dockerfile     -> build specification (IaC)
Image          -> immutable, distributable artifact identity (layers, read-only, shared)
Container      -> replaceable runtime instance (isolated process + shared host kernel)
Writable layer -> per-container ephemeral runtime state
Volume/external-> durable state, independent lifecycle
Network        -> explicit reachability via service DNS names
```

## Top concepts to master

- **Container = isolated process, not a VM.** Namespaces isolate what a process *sees*; cgroups bound *how much* CPU/memory it uses; it shares the host kernel. Fast start, lower overhead, weaker isolation than a full VM.
  - *WHY:* run many isolated workloads on one kernel. *Risk:* an unbounded container can exhaust host memory (cgroup limits prevent it). *Memory:* "container = process with isolated views + resource limits."
- **Image vs Container.** Image = immutable template; container = one runtime instance. One image → many containers. A rebuild does NOT update running containers; production changes create a new image and replace containers.
  - *Responsibility:* image owns immutable content; container owns runtime config + writable layer. *Memory:* "class vs instance, but `run` makes a container, not an image."
- **Layers + writable layer + build cache.** Build cache reuses immutable image layers at build time; the writable layer is per-container at runtime. Cache invalidates from the first changed instruction onward → copy dependency manifest and install *before* copying app code.
  - *Memory:* "ask: build time or runtime? deps before code."
- **Dockerfile instructions.** `FROM` (base), `WORKDIR`, `COPY` (explicit inputs), `RUN` (build-time), `CMD`/`ENTRYPOINT` (default runtime process). `python:3.12-slim` is a controlled but MUTABLE tag; `@sha256:<digest>` is immutable (use a real digest, never invent one).
- **Build vs Run.** `docker build` makes the image (does not start the service); `docker run` creates a container, adds a writable layer, applies runtime config (env/ports/limits/network), then starts CMD/ENTRYPOINT. One image → many containers with different config.
- **Volume and state.** Writable layer is ephemeral (gone when the container is removed); a named volume has an independent lifecycle. DB files, uploads, vector indexes must NOT depend on the writable layer. Separate compute lifecycle from data lifecycle; keep app containers stateless.
- **Network.** Each container has its own network namespace, so `localhost` = the current container. Containers on a shared user-defined network reach each other by stable service DNS name (`postgres:5432`), not by IP (IPs change on recreate). Network membership is an access-control decision.
- **Immutable replacement.** Never edit a running production container: the change lives only in its writable layer — not reproducible, auditable, or rollback-able. Rebuild → verify → replace.

## Production scenario
`/chat` returns 500 after a commit → `git log` finds the suspect commit → build a new image → start + health-check a new container → switch traffic → remove the old one. Never `docker exec` a fix into the live container.

## Failure / Rollback boundary
Fault is contained at the container process (cgroup-bounded). Rollback = run the previous immutable image and replace the container. No data is repaired by replacement — durable data lives in the volume/external store.

## Key trade-offs
Container vs VM (fast/low-overhead/shared-kernel vs stronger isolation); writable layer vs volume (ephemeral convenience vs durable independent lifecycle); cache-friendly order vs simplicity; **smallest secure-and-sufficient image, not smallest bytes** (a smaller image speeds transfer/deploy/scan, not app execution); bundle AI model in image vs external model store; broad network vs least access.

## Real classroom misconceptions & corrections
- **"A smaller image runs the app faster."** Reasonable (small feels fast); fails because size affects transfer/deploy/scan/scale-out, not execution speed. Correct: optimize for smallest secure & sufficient runtime.
- **"The writable layer performs container startup."** Reasonable (it's where runtime changes go); fails because the process is launched from image metadata (CMD/ENTRYPOINT). Correct: writable layer = files, not the process launcher.
- **"You can't reach another container because writable layers are separate."** Reasonable (isolation intuition); fails by conflating mechanisms. Correct: reachability comes from network namespaces/membership; filesystem isolation is separate — join a network and use service DNS.
- (Also recorded: image "generates images", rebuild upgrades running containers, ports live in the writable layer, `localhost` reaches another container. Verbatim student answers are preserved in the lesson.)

## Interview memory sentence
`A container is an isolated process sharing the host kernel; build makes the immutable image, run makes a replaceable container; durable state lives in a volume and services talk by DNS, never localhost.`

## Previous → Current → Next
Day22 (verified immutable digest) → **Day23 (what that image is / how to run it)** → Day24 (run many services together).

## Verification results & limitations
The Dockerfile/compose examples are teaching templates; this handbook repo has no runnable FastAPI app, so `docker build`/`docker run` were NOT executed. Only static reasoning applies. `Runtime not verified.`

---

# Day24 — Docker Compose

Source: [docs/devops/day24-docker-compose.md](../devops/day24-docker-compose.md) · Artifact: [examples/docker/compose/](../../examples/docker/compose/)

## One-sentence Mental Model
`Compose = a declarative, version-controlled specification of a multi-service system and its runtime relationships on ONE Docker host — Project → Services → Containers, with networks, volumes, and secrets; "started" ≠ "ready".`

## Why this lesson exists
One reproducible container is not a reproducible *system*. Starting FastAPI + Worker + Redis + PostgreSQL with many `docker run` commands drifts across people (missing flags, different ports/networks/volumes/env). Compose makes the relationships reproducible.

## Engineering Problem it solves
Reproducible system = reproducible images + reproducible runtime config + reproducible service relationships, all version-controlled.

## Core responsibility map
```text
Project   -> boundary for related services/networks/volumes
Service   -> desired runtime spec for one workload role (exists at zero instances)
Container -> a replaceable instance = Image + Service specification
Networks  -> explicit reachability (least access)
Volumes   -> durable state
Env/Secret-> runtime config vs protected credentials (mounted at /run/secrets/<name>)
Health deps-> service_healthy before dependents start
```

## Top concepts to master

- **`depends_on` ≠ healthcheck ≠ application retry.** `depends_on` (short form) waits only for the container to *start*; a healthcheck probes readiness (it does NOT repair/restart); application retry (bounded + backoff) handles transient failures during and after startup. You usually need all three. *Memory:* "started? healthy? able to serve?"
- **Project / Service / Image / Container.** One service can create many containers (3 API replicas = 1 service); one image can back many services (API vs Worker, different commands). Image = immutable content; service spec = command/env/networks/volumes/ports/secrets/scaling.
- **Rebuild vs recreate vs reload.** Image content change → rebuild + recreate; runtime config change → recreate; mounted source change → reload/sync. *Memory:* match the command to the changed layer.
- **Declarative convergence.** `docker compose up` resolves the desired model and creates/starts/recreates only what's necessary (command-triggered, NOT a continuous control loop). YAML indentation *is* the data structure. A top-level network/volume/secret is not granted to a service unless referenced.
- **Host ports + service DNS.** Only the API publishes `8000:8000`; internal calls use `redis:6379` / `postgres:5432` (stable across recreation). Publishing DB ports for convenience enlarges attack surface — prefer `exec`/admin service.
- **Network segmentation (least access).** `queue_network` (API+Worker+Redis) and `database_network` (API+Worker+PostgreSQL); Redis and PostgreSQL share NO network, so a compromised Redis cannot reach PostgreSQL. Membership is one access layer, not a replacement for credentials/auth.
- **Volumes & data lifecycle.** `down` keeps named volumes; `down --volumes` deletes them (destructive locally). No mount → data lives in the writable layer. Volume persistence ≠ backup. Four storage kinds: bind mount, named volume, writable layer, image layer.
- **Env / .env / Secret / business data.** Env var = ordinary config; Secret = protected credential (mounted at `/run/secrets/<name>`, the app must READ the file); business data = governed application data. `.env` is plaintext interpolation input, NOT a secret manager. Least-privilege grants (only the Worker gets `openai_api_key`).
- **Base + dev override.** `compose.yaml` is portable/production-style; `compose.dev.yaml` holds ONLY dev differences (source bind mounts + `--reload`). Don't carry host mounts to production.
- **Compose production boundary.** Fits local/CI/demos and controlled single-host prod (with backups, TLS, monitoring, secrets, limits). It does NOT provide multi-node scheduling, node-failure rescheduling, continuous replica reconciliation, autoscaling, rolling updates, automatic rollback, or DNS/TLS/secret-rotation governance.

## Production scenario
A new engineer clones the repo and runs `docker compose up` for the exact local stack instead of a wiki of `docker run` commands; only the API is reachable, Redis/PostgreSQL are internal-only, PostgreSQL data survives recreation via a named volume.

## Failure / Rollback boundary
Failure isolated per service; `depends_on: service_healthy` prevents "started-not-ready" races; but a single host is one failure domain. Local rollback = `down`/recreate with the previous image; `--volumes` is the destructive line.

## Key trade-offs
`depends_on` vs healthcheck vs retry (usually all three); one network vs segmented (simplicity vs least access); publish DB ports vs exec-only; named volume vs backup; base+override vs one big file; Compose vs Kubernetes/managed platform (single-host simplicity vs multi-node scheduling/self-healing/scaling/rollout).

## Real classroom misconceptions & corrections
- **"'Docker Compose is a multi-container application.'"** (English interview.) Correct: it is a *tool for defining and running* multi-container applications.
- **"Persistence alone is sufficient protection (volume = backup)."** Fails on volume/host loss. Correct: a backup survives volume/host loss and must be restorable — a separate control.
- **"Compose can never be used in production."** Correct: controlled single-host prod can be reasonable *with extra controls*, but Compose lacks scheduling/reconciliation/autoscaling/rollout governance.
- (Also recorded verbatim: started≠ready, service vs instance, healthcheck "repairs", customer data "not a secret because large", "scheduling" terminology.)

## Interview memory sentence
`Compose is a tool for declaring a reproducible multi-service system on one host; depends_on only waits for start, a healthcheck proves readiness, and application retry handles runtime failure.`

## Previous → Current → Next
Day23 (one reproducible container) → **Day24 (declare the multi-service system)** → Day25 (make it a safe public service).

## Verification results & limitations
Template only; the repo has no runnable app. `docker compose up` was NOT executed — only `docker compose config` (static model validation) is meaningful. `Runtime not verified.`

---

# Day25 — Deployment Foundations

Source: [docs/devops/day25-deployment-foundations.md](../devops/day25-deployment-foundations.md) · Artifact: [examples/deployment/](../../examples/deployment/)

## One-sentence Mental Model
`Deployment is a serialized, observable, reversible production state transition that promotes the exact verified artifact while preserving request, job, data, and rollback compatibility.`

## Why this lesson exists
A Compose stack that *starts* is not yet a safe, publicly reachable, zero-downtime service. `Built Artifact != Running Container != Reachable Production Service.`

## Engineering Problem it solves
Move a CI-verified immutable image into live production traffic with a stable public entry, TLS identity, drain, and rollback — without an outage or data-contract break.

## Core responsibility map
```text
DNS            -> where the public entry is (coarse discovery/migration)
Nginx :443     -> which public service accepts the connection; TLS terminates here
Reverse proxy  -> which internal backend receives the request (proxy_pass api:8000)
FastAPI        -> the internal business operation (kept internal by service DNS)
PostgreSQL     -> shared durable contract (evolved with Expand-Migrate-Contract)
```

## Top concepts to master

- **Stable public entry vs replaceable backend.** Goal is NOT hiding port 8000 — it's not exposing the backend port publicly. `Client -> api.example.com -> DNS -> Public IP -> Nginx :443 -> api:8000`. Changing v1→v2 must not change the client's domain/URL.
- **Nginx reverse proxy.** `listen`/`server_name` = public side; `proxy_pass` = internal service. `localhost` inside the Nginx container is Nginx itself → use service DNS `api:8000`.
- **TLS = confidentiality + integrity + server authentication.** A valid cert for the wrong domain is rejected. TLS terminates at Nginx here (protects client→Nginx only). A reverse proxy does not automatically provide TLS.
- **HTTP→HTTPS 308 (and the token misconception).** Use 308 for APIs (preserves method/body). A token sent in the first HTTP request is already exposed before the redirect — redirect is compatibility, not retroactive protection. Long-lived token = longer abuse window, not "more secure".
- **Certificate lifecycle + Nginx master/worker.** An expired cert invalidates identity (outage), it does not make traffic plaintext. Update files → `nginx -t && nginx -s reload` (reload gracefully replaces workers; restart = stop+start). "Worker" is overloaded: Nginx worker process ≠ AI background worker.
- **Trusted proxy context.** Forward `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` for audit/URL/OAuth/rate-limit/security. A header is metadata, NOT identity — needs trusted proxy + normalization + backend isolation + real auth. A trusted `X-Forwarded-For: 127.0.0.1` on an admin route is an access-control bypass.
- **Promote the exact digest.** `Tested = Scanned = Deployed`. Rebuild = new artifact (new digest, new verification); promote = move the SAME verified artifact. Tag = movable reference; digest = immutable identity. Runtime differences live in the service spec, not a per-env rebuild.
- **Blue-green + drain.** Start Green (no prod traffic) → verify directly (not via the URL still serving Blue) → `nginx -t` → switch → observe under real traffic → drain Blue in-flight → roll back or remove Blue after the rollback window. Health/readiness before traffic is necessary but NOT sufficient (real traffic reveals business/AI/streaming failures). `Stateless container != stateless operation` — safe retry needs idempotency/job-id/checkpoints.
- **PostgreSQL Expand-Migrate-Contract.** A destructive schema change breaks a still-running v1 and rollback compatibility. Order: Expand (add column) → compatible code → backfill → verify/end rollback window → Contract (drop old) in a LATER release.
- **Worker rollout ≠ Nginx traffic switch.** Competing consumers are normal scaling; deploy a compatible consumer first (accepts old+new payloads) → observe → new producer → drain old. Duplicates come from at-least-once delivery/retry, needing idempotency.
- **Serialized deploy + identity.** `concurrency: { group: production, cancel-in-progress: false }`. Approval = authorization; concurrency = serialization. On a stuck deploy: timeout → freeze destructive actions → inspect actual state → complete or roll back → verify → record → release lock. Use a least-privilege, short-lived deploy identity (not a long-lived root SSH key).
- **AI streaming + DNS TTL.** Buffering (holds chunks of THIS response) ≠ caching (reuses a response for LATER requests); disable buffering for `/chat`, set larger read/send timeouts. DNS TTL expires per resolver — the switch is gradual, not atomic; lower TTL ahead of migration, keep A/B during propagation.

## Production scenario
Promote the approved digest → start Green → verify → `nginx -t` → graceful switch → observe error rate while draining Blue → if a 20% error rate appears, restore Nginx target to Blue and reload before deleting v2 → record the rollback.

## Failure / Rollback boundary
Contained at the traffic switch and drain window. Rollback = switch traffic back to Blue (compute), preserve evidence. A schema Contract done too early breaks rollback — Expand-Migrate-Contract keeps a rollback path.

## Key trade-offs
Direct exposure vs one Nginx entry; TLS termination vs internal mTLS; redirect UX vs first-request exposure; tags vs digests; blue-green rollback speed vs double resources; long drain vs cost; retry convenience vs duplicate side effects; serialized safety vs blocked emergency releases; buffering throughput vs streaming latency; low vs high DNS TTL.

## Real classroom misconceptions & corrections
- **"An expired certificate makes traffic plaintext."** Correct: it invalidates server identity; compliant clients reject → outage.
- **"A 308 redirect protects a token sent over HTTP."** Correct: the first HTTP request is already exposed; the client must use HTTPS from the start.
- **"Nginx holding stream chunks is caching (set a cache time)."** Correct: that's buffering (chunks of the current response); disable buffering for `/chat`.
- **"DNS TTL is a global counter that must exhaust before the switch."** Correct: each resolver caches until its own TTL expires; the switch is gradual.
- (Also recorded: port "hiding", reversed proxy roles, `X-Forwarded-For` proves identity, rebuild per env, health=success, drain/retry transparency, worker blue-green.)

## Interview memory sentence
`API and worker are replaceable compute (blue-green / compatible-consumer-first); PostgreSQL schema is a shared durable contract evolved with Expand-Migrate-Contract — all under a serialized lock with observation and a rollback path.`

## Previous → Current → Next
Day24 (multi-service on one host) → **Day25 (safe public state transition)** → Day26 (make it continuous desired-state reconciliation).

## Verification results & limitations
`nginx.conf.example` is a `server`-block fragment (no `events`/`http` context) and cannot be passed to `nginx -c` directly; `example.com` and cert paths are placeholders. No domain/cert/app exists, so `nginx -t` and the runbook were NOT executed. `Runtime not verified.`

---

# Day26 — Kubernetes Foundations

Source: [docs/devops/day26-kubernetes-foundations.md](../devops/day26-kubernetes-foundations.md) · Artifact: [examples/kubernetes/ai-backend-baseline.yaml](../../examples/kubernetes/ai-backend-baseline.yaml)

## One-sentence Mental Model
`You declare the desired runtime state; controllers continuously observe → diff → act to reconcile actual to desired. Kubernetes maintains the declared state; it does NOT guarantee the state is correct.`

## Why this lesson exists
Day25's runbook still depended on an operator/script to start, switch, and roll back; nobody continuously owned the running state after the script finished. `Script = act once; Kubernetes = maintain a declaration.`

## Engineering Problem it solves
Continuous availability and discovery: declared replicas are reconciled after a node failure, and a stable Service name survives changing Pod IPs — without manual restarts.

## Core responsibility map
```text
Desired state -> what should be true (declared)
Reconciliation-> observe -> diff -> act, continuously
Pod           -> smallest deployable unit; one or more tightly coupled containers
Deployment    -> Pod template + replica count (recovery, NOT scheduling)
Service       -> stable discovery for label-selected, changing Pods
ConfigMap     -> non-sensitive runtime config outside the immutable image
Secret        -> sensitive values (Base64 = encoding, not encryption; not an auto-vault)
```

## Top concepts to master

- **Desired state vs one-time command.** A script ends and stops owning the count; a Deployment keeps declaring "3 replicas" and reconciles drift. Honest limits: it creates a *replacement* (new name/IP/Node), not the vanished identity; reconciliation is eventual; a *wrong* desired state is enforced just as reliably.
- **Pod = smallest deployable/schedulable unit.** One or more tightly coupled containers: same Node, shared Pod network/IP, `localhost` between them, optional shared volume, shared replacement/lifecycle boundary — but individual containers can restart independently. Co-locate only what must share fate; independent scaling/lifecycle → its own workload (FastAPI + PostgreSQL should NOT share a Pod).
- **Deployment.** `Deployment -> ReplicaSet -> Pods -> Containers`; owns template + count and recreates missing replicas. It does NOT schedule (kube-scheduler places Pods). `replicas: 3` ≠ three business-ready replicas (a bad template is replicated three times).
- **Service.** Stable DNS/VIP fronting label-selected Pods; selector must match Pod labels. `Pod Running != Service has endpoints != request succeeds`. In class: `port: 80`, `targetPort: http` (named container port 8000).
- **ConfigMap.** Non-sensitive runtime config (`MODEL_NAME`, `LOG_LEVEL`, flags, timeouts) outside the image. Stronger reason than saving build resources: preserving the verified digest. `ConfigMap updated != running process env changed` — env injection is read at container start, so Pods usually need replacement.
- **Secret.** Sensitive values; `Base64 = encoding, not encryption`. A Secret is NOT automatically a vault: real protection = Secret + encryption-at-rest + RBAC + namespace/workload isolation + selective mounting + audit + rotation. Least privilege is selective (only the API container gets the key; the logging sidecar must not).
- **Partial-outage rollback.** `/health` 200 ≠ business success. If one rotated-key Pod returns 401 on ~1/3 of traffic: freeze rotation → restore known-good Secret → verify → delete ONLY the faulty Pod (Deployment replaces it) → AI smoke test → observe. Deleting the healthy old Pods while the wrong Secret is current turns a partial outage into a full one.

## Production scenario
A node dies at 03:00 → the Deployment/ReplicaSet controller creates a replacement Pod, kube-scheduler places it, and the Service keeps resolving `rag-api` while Pod IPs churn — no human restart.

## Failure / Rollback boundary
Contained at the Pod (replaced from the template). But reconciliation is a force multiplier in both directions — control the *desired state* (e.g. restore the good Secret) before letting the controller replace anything. Rollback = restore a known-good desired state.

## Key trade-offs
Script vs reconciliation (simple/explicit vs continuous but enforces bad state too); single vs multi-container Pod; hand-written Pods vs Deployment; direct Pod IP vs Service; image-baked config vs ConfigMap; Secret object vs full secret management; broad vs narrow health check; manual ops vs automation (reduces omission but amplifies a bad desired state).

## Real classroom misconceptions & corrections
- **"A Deployment places Pods on Nodes."** Correct: Deployment maintains template+count; kube-scheduler selects Nodes. A Pod can exist without a Deployment.
- **"A Base64-encoded Secret value is encrypted."** Correct: Base64 is encoding; anyone with the content can decode it. Encryption at rest is separate.
- **"A 200 from /health proves the deployment works."** Correct: readiness/liveness are limited evidence; business smoke tests + provider errors + logs + latency + metrics must also be observed.
- **"Reconciliation always makes things better."** Correct: it enforces the desired state, not business correctness; a bad desired state is automated and amplified across replicas.
- (Also recorded: separate Pods imply manual ops, Pod means several containers, shared lifecycle means containers can't restart separately.)

## Interview memory sentence
`A Deployment maintains replicas from a template; the scheduler places Pods; a Service provides stable label-based discovery; Base64 is encoding, not encryption; health 200 is not business success.`

## Previous → Current → Next
Day25 (manual safe transition) → **Day26 (continuous desired-state reconciliation)** → Day27 (routing, scaling, rollout, state, packaging on top).

## Verification results & limitations
`ai-backend-baseline.yaml` is a teaching template with non-pullable `.invalid` image placeholders and PLACEHOLDER `stringData`. No Kubernetes runtime (`kubectl apply`, Pod Ready, Service routing, rollout) was executed — see [examples/kubernetes/README.md](../../examples/kubernetes/README.md). `Runtime not verified.`

---

# Day27 — Kubernetes Workloads

Source: [docs/devops/day27-kubernetes-workloads.md](../devops/day27-kubernetes-workloads.md) · Artifact: [examples/kubernetes/rag-platform/](../../examples/kubernetes/rag-platform/)

## One-sentence Mental Model
`Each workload controller enforces a declared intent — Ingress routes at L7, HPA sets desired replicas from real pressure, Rolling Update replaces gradually, StatefulSet preserves identity/storage (not HA), Helm renders per-environment releases; static validation never proves business correctness.`

## Why this lesson exists
Day26 kept N replaceable Pods alive and discoverable but gave no public L7 routing, metric-driven scaling, availability-preserving version replacement, stable stateful identity/storage, or reusable multi-environment packaging.

## Engineering Problem it solves
Route to workloads (Ingress), scale from meaningful signals (HPA), replace versions without an outage (Rolling Update), give stateful workloads stable identity/storage (StatefulSet), and package it all per environment (Helm).

## Core responsibility map
```text
Ingress        -> L7 Host/Path/TLS routing to Services (resource declares; controller implements)
Service        -> stable L4 discovery/endpoints for current Pods
HPA            -> update desired replicas on a scale target from meaningful pressure
Rolling Update -> gradual same-selector replacement within maxSurge/maxUnavailable
StatefulSet    -> stable Pod identity + per-Pod PVC + ordered lifecycle (NOT replication/HA/backup)
Helm           -> Templates + Values + Release (env-aware, revisioned)
```

## Top concepts to master

- **Ingress = L7 entry before Service.** Split by layer, not "internal vs external": Service routes by ports/endpoints (L4); Ingress routes by Host/Path/TLS (L7). The Ingress *resource* declares intent; an Ingress *Controller* implements it (an Ingress resource alone does nothing). Routing `/admin` is NOT authentication.
- **HPA.** HPA does NOT create Pods — it updates desired replicas on a scale target; the Deployment reconciles Pods and the scheduler places them. CPU is measured relative to container CPU *requests* (must be defined). A low-CPU, external-wait workload needs **queue backlog / backlog-per-worker**, and you scale the *consumer* (worker), not the producer (API). More Pods do NOT create upstream provider capacity — cap `maxReplicas`. With an HPA, don't hard-code `spec.replicas`.
- **Rolling Update.** Gradual under one selector: add ready v2 Pods, remove v1 within `maxSurge`/`maxUnavailable` (no manual Service switch — that's Blue-Green). `maxUnavailable: 0` needs surge capacity; a failing v2 stalls the rollout while v1 keeps serving. Readiness 200 ≠ correct AI result / acceptable error rate / latency.
- **Rolling Update ≠ rollback; deleting Pods ≠ rollback.** Rollback restores a previous desired revision via another controlled rollout (`kubectl rollout undo` / `helm rollback`). Deleting v2 Pods just makes the controller recreate v2 (the desired template is still v2). Limit: rollback cannot undo an incompatible migration or external side effect.
- **StatefulSet.** Stable identities (`postgres-0/1/2`), per-Pod PVCs (`volumeClaimTemplates`), stable reattachment, ordered lifecycle, headless Service. `Independent disks = isolation/identity, NOT replicated bytes.` `StatefulSet != database HA` — HA needs base backup + WAL/streaming replication + leader election/promotion + fencing + write routing, plus independent backups/PITR.
- **Helm.** Every object is a *template*; fields inside every object may vary by *Values*; a *Release* is a rendered, revisioned install. Validation ladder: `helm lint` (structure) → `helm template` (render) → server-side dry run (API/schema/policy) → runtime (scheduling/routing/scaling/storage/readiness/business). Helm does NOT auto-roll back by default; `--atomic --wait --timeout` can attempt rollback on readiness failure, but business failures aren't auto-detected. NEVER commit real Secrets to Values — release history/rendered manifests can leak them; template Secret *references*.

## Production scenario
`https://api.example.com/chat` routes through Ingress → `rag-api` Service → Pods; the RAG worker scales on queue backlog (capped to the provider's rate limit); a broken v2 stalls at `maxUnavailable: 0` while v1 serves; the operator restores revision N via `helm rollback` rather than deleting v2 Pods.

## Failure / Rollback boundary
Contained by `maxUnavailable: 0` (old capacity stays Ready). Rollback = restore the previous desired revision (controlled reverse rollout). External side effects and DB migrations remain outside this boundary → keep schema changes backward compatible.

## Key trade-offs
Ingress edge vs per-Service edges; CPU vs custom/external metric; aggressive vs bounded scaling; `maxUnavailable: 0` vs allowing unavailability; Rolling Update vs Blue-Green; StatefulSet vs Deployment+volume; replicas vs backups; Helm templating vs raw YAML; `--atomic` vs manual rollback; static vs runtime validation.

## Real classroom misconceptions & corrections
- **"Run v1 and v2, then switch the Service to v2."** (For a Rolling Update.) Correct: that's Blue-Green; Rolling Update adds ready v2 Pods under the same selector and removes v1 within surge/unavailability limits.
- **"A StatefulSet with three PVCs replicates the database."** Correct: each PVC holds its own bytes; StatefulSet gives identity/storage, not replication/failover/backup.
- **"Helm auto-rolls back every failed upgrade."** Correct: `helm rollback` restores a revision; `--atomic` can attempt rollback on readiness failure; business failures/external side effects are not auto-reversed.
- **"helm lint / helm template passing means the release works."** Correct: lint/render/API-admission/runtime/business prove different things; only runtime + business smoke tests prove user-visible correctness.
- (Also recorded: Service internal/Ingress external, HPA creates Pods, CPU is always the metric, deleting broken Pods rolls back, one full copy = failover.)

## Interview memory sentence
`Rolling Update with maxUnavailable: 0 keeps old Pods until new ones are Ready; roll back by restoring the previous revision, not by deleting Pods; scale the worker on queue backlog, not CPU; a StatefulSet gives identity/storage, not database HA.`

## Previous → Current → Next
Day26 (desired-state base objects) → **Day27 (routing/scaling/rollout/state/packaging)** → Day28 (assemble them into one AI backend architecture).

## Verification results & limitations
The `rag-platform` Helm chart is a conceptual, teaching-only chart with non-pullable placeholder images. No live Kubernetes/Helm validation occurred — only deterministic static checks (see the chart's `validate_chart.py` and [examples/kubernetes/README.md](../../examples/kubernetes/README.md)). Ingress routing, HPA scaling, Rolling Update, rollback, PVC provisioning, and PostgreSQL replication were NOT run. `Static validation != runtime success.`

---

# Day28 — AI Backend Production Architecture

Source: [docs/devops/day28-ai-backend-production-architecture.md](../devops/day28-ai-backend-production-architecture.md) · Artifact: [examples/ai-backend-architecture/](../../examples/ai-backend-architecture/)

## One-sentence Mental Model
`FastAPI accepts/exposes, Celery executes, Queue/Redis transports, PostgreSQL owns durable truth, Object Storage owns large bytes; at-least-once delivery requires idempotent effects; compute rollback does not repair data.`

## Why this lesson exists
A 500 MB upload with an 8-minute pipeline inside the HTTP request causes Ingress timeout → client retry → duplicate model cost → unclear progress → lost in-memory state on Pod replacement. Deploying components is not an architecture — you must assign responsibility, ownership, delivery guarantees, failure boundaries, recovery, and evidence.

## Engineering Problem it solves
Accept fast (`202 + job_id`), process async, and make every state/byte owned, every effect idempotent, every failure containable, and every incident explainable.

## Core responsibility map
```text
FastAPI        -> control plane: authn/authz, validate, presigned URL, verify upload,
                  create durable Job (+ Outbox) in ONE transaction, return 202 + job_id, expose status
Celery worker  -> execute the long pipeline; retry/ACK; NOT the Job source of truth
Queue / Redis  -> transport/deliver task messages; optional ephemeral cache; NOT durable truth
PostgreSQL     -> durable truth: Job lifecycle, metadata, Outbox, append-only events, checkpoints,
                  leases, attempts, provenance, object references, unique constraints
Object Storage -> large bytes: immutable originals + derived artifacts; object versions; scoped access
Monitoring     -> detect known-abnormal signals vs thresholds/SLOs
Observability  -> explain WHY via metrics + structured logs + traces + durable events
```

## Top concepts to master

- **Request vs Job lifecycle.** `HTTP request lifecycle != long-running job lifecycle`. FastAPI authenticates, validates, commits a durable Job, returns `202 + job_id`, exposes status. A long `async def` inside FastAPI is NOT a durable job system (no durable acceptance, redelivery, retry, progress recovery, or Pod-restart survival).
- **State ownership.** After `202`, the Job is a durable business commitment — PostgreSQL owns EVERY lifecycle state (queued/running/retry_wait/succeeded/failed/invalidated/reprocessing), not just the final result. Redis brokers/caches (transient); FastAPI memory is request-local.
- **DB→Queue consistency + Transactional Outbox.** You cannot atomically write two independent systems. A naive "insert Job, then publish" has a crash gap (QUEUED with no message). Fix: reconciliation scanner and/or Transactional Outbox (insert Job + Outbox event in ONE transaction; a relay publishes and marks sent). Outbox makes state+intent atomic but is still `at-least-once delivery + idempotent processing` (never exactly-once).
- **Checkpoints, leases, idempotency.** Durable stages (UPLOADED→PARSED→CHUNKED→EMBEDDING→INDEXED→SUCCEEDED); atomic claim/lease with expiry; stable idempotency key `(document_id, chunk_hash, model_version)` enforced by a DB **unique constraint + upsert**; ACK the queue ONLY after result+checkpoint are durable. External calls: use provider idempotency keys; a provider call that succeeds before the local checkpoint write can be repeated on redelivery. Progress % = UX; durable checkpoint = recovery; lease = exclusive ownership.
- **Object Storage + control/data plane.** Large bytes → Object Storage (not Pod disk/Redis/PostgreSQL). Stronger reason than capacity: replaceable Pod-local storage has the wrong lifetime and is unshared. Control plane (DB): key/checksum/version/owner/status; data plane (Object Storage): the bytes. An object key is NOT authorization.
- **Presigned multipart upload + Upload Session.** FastAPI issues a short-lived presigned (multipart) URL; the client uploads directly to Object Storage (not through FastAPI). Direct upload does NOT remove network failure (multipart + retry + cleanup still needed). The client "complete" callback is UNTRUSTED — verify existence/size/checksum/version/ownership/scan first, then create the Job in one transaction bound to an immutable object version. Two state machines: Upload Session (INITIATED→UPLOADING→VERIFIED|FAILED|EXPIRED) and Job (QUEUED→RUNNING→RETRY_WAIT→SUCCEEDED|FAILED_TERMINAL).
- **Retry policy.** Exponential backoff + **jitter**; bound by max attempts and/or an overall deadline (a max delay alone allows infinite attempts); classify errors (429 honor Retry-After; 503/timeout retry; 400/parse terminal; 401/403/config stop+contain+alert); global rate limiter / circuit breaker; persist attempt state. `Retry is a controlled recovery policy, not an infinite loop.`
- **Monitoring.** Correlate signals: depth (inventory) + oldest-age (closest to user pain/SLO) + throughput (progress). depth+age rising & throughput ~0 = stall; & throughput normal = under capacity; depth high & age low = burst. A single stuck/poison job keeps oldest-age rising, so don't use it unqualified as a scale trigger (the worker HPA still scales on backlog).
- **Observability.** Correlate on **stable `job_id`** (not `job_status`, which changes and is shared). Scopes: `trace_id`, `attempt_id/count` (app-owned), broker `task_id` (may change), `provider_request_id`. Keep metric labels low-cardinality (job_id belongs in logs/traces). Durable history: `jobs.current_status` projection + append-only `job_events`.
- **Failure containment, rollback, data repair.** `Compute rollback stops future damage; data repair corrects damage already persisted.` Runbook for a wrong-embedding-model release that passed readiness: A contain bad v2 → B restore known-good v1 → C identify/quarantine/invalidate affected results by provenance → D idempotently reprocess from immutable originals into a clean/versioned index → E verify (counts, model/version/dimensions, real RAG quality, errors, latency, cost) then switch the index alias/current pointer.

## Production scenario
`POST /documents` returns `202 {job_id}` in ms; the client uploads 500 MB directly to Object Storage; after server-side verification a Job + Outbox row are written in one transaction; a worker leases, embeds with idempotent upserts, ACKs after durable write; a redelivered task sees `INDEXED` for `(doc, chunk_hash, model_v)` and skips the model call.

## Failure / Rollback boundary
Compute contained at the worker (contain/restore). Data boundary is separate: persisted PostgreSQL state, Object Storage artifacts, and vector indexes need identify → invalidate → reprocess → verify → alias switch. External side effects need compensation/reconciliation.

## Key trade-offs
In-request vs async worker; reconciliation scanner vs Transactional Outbox; coarse checkpoints vs per-chunk rows; presigned direct vs API-proxied upload; Object Storage vs DB blobs vs Redis; aggressive vs bounded+classified retry; sensitive vs tolerant alerts; low-cardinality metrics vs per-job labels; compute rollback vs data repair.

## Real classroom misconceptions & corrections
- **Senior question ("under at-least-once, prevent duplicate durable effects…"): student answered "我忘了" (I forgot).** Preserved as recorded; the senior answer was taught directly — assume at-least-once, idempotent worker, stable key + unique constraint, ACK after durable write, reconcile external systems, never claim exactly-once. This question needs direct teaching because the prerequisite (delivery semantics) was missing.
- **"Redis holds queued jobs, memory holds transient state, PostgreSQL holds only final results."** Correct: after `202`, PostgreSQL owns the whole lifecycle; Redis brokers/caches; memory is request-local.
- **"Query then upsert prevents all duplicates / gives exactly-once."** Correct: a separate read+write can race — enforce a DB unique constraint + atomic upsert; it stops duplicate durable writes for that key, not a duplicate external call already made. Assume at-least-once.
- **"Rolling back the worker fixes everything."** Correct: compute rollback stops future bad execution; persisted state/artifacts/indexes need identify/quarantine/invalidate/reprocess/verify/re-expose.
- (Also recorded verbatim: DB-first alone solves consistency, progress record prevents duplicate work, pod disk is just capacity, direct upload removes network failure, client "completed" means complete, backoff+max wait is complete retry, oldest-age identifies root cause, job_status is the identifier, status unchanged across retries.)

## Interview memory sentence
`Assume at-least-once and make effects idempotent with a stable (job_id, chunk_hash, model_version) key and a unique constraint; ACK after durable write; PostgreSQL owns the Job, Object Storage owns bytes; compute rollback does not repair data.`

## Previous → Current → Next
Day27 (workload primitives) → **Day28 (whole-system responsibility/state/failure/evidence, Phase 2 close)** → Phase 3 Backend Foundations (PostgreSQL, SQL, Redis, Database Design). Day29 is planned; the lesson file does not exist yet — do not assume its content.

## Verification results & limitations
The Day28 artifact is conceptual architecture documentation. No FastAPI/Celery service, Redis broker, PostgreSQL schema, Object Storage bucket, vector index, Kubernetes workload, metrics backend, log pipeline, or tracing system was created or run; no queue-redelivery, provider-failure, load, smoke, rollback, or data-repair test was executed. `Conceptual-only. Not production-ready. Runtime not verified.` See the blueprint's validation-limitations section.

---

# Phase completion check

Without notes, you should be able to:

- [ ] State the whole-phase model: a running system is not an architecture (name the ten judgments).
- [ ] Trace the chain Day23→28 and say what gap each day closes.
- [ ] Distinguish image vs container, build vs run, writable layer vs volume (Day23).
- [ ] Distinguish `depends_on` vs healthcheck vs retry, and Compose vs a cluster (Day24).
- [ ] Explain "Built Artifact != Running Container != Reachable Service" and Expand-Migrate-Contract (Day25).
- [ ] Explain desired state vs a command, and why a bad desired state is amplified (Day26).
- [ ] Explain HPA scale-target, Rolling-Update-vs-rollback, and StatefulSet-is-not-HA (Day27).
- [ ] Explain state ownership, the Transactional Outbox, at-least-once + idempotency, and compute-rollback-vs-data-repair (Day28).
- [ ] Say which layer to inspect for a given failure (see [Architecture & Failure Map](Day23-Day28-Architecture-Failure-Map.md)).

---

# Source Map

| Section | Repository Source |
|---|---|
| Whole-phase model, chain | `docs/devops/day28-ai-backend-production-architecture.md`, `CURRICULUM.md`, `ROADMAP.md` |
| Day23 | `docs/devops/day23-docker-fundamentals.md`, `examples/docker/fastapi/` |
| Day24 | `docs/devops/day24-docker-compose.md`, `examples/docker/compose/` |
| Day25 | `docs/devops/day25-deployment-foundations.md`, `examples/deployment/` |
| Day26 | `docs/devops/day26-kubernetes-foundations.md`, `examples/kubernetes/ai-backend-baseline.yaml`, `examples/kubernetes/README.md` |
| Day27 | `docs/devops/day27-kubernetes-workloads.md`, `examples/kubernetes/rag-platform/`, `examples/kubernetes/README.md` |
| Day28 | `docs/devops/day28-ai-backend-production-architecture.md`, `examples/ai-backend-architecture/` |
