# Day23–Day28 Production Engineering Interview Q&A

> Part of the **Production Engineering Second Brain**. See [README.md](README.md).
> Companion docs: [Super Cheat Sheet](Day23-Day28-Production-Super-CheatSheet.md) · [Architecture & Failure Map](Day23-Day28-Architecture-Failure-Map.md) · [Artifact Templates](Day23-Day28-Artifact-Templates.md) · [One Page](Day23-Day28-OnePage.md)

This is the **expression & judgment** layer: move from a concept to a spoken engineering answer. It compresses and cross-links; the full question bank lives in [interview/devops.md](../../interview/devops.md).

Integrity notes: `Actual Student Attempt` is preserved verbatim from the lesson only where the repository recorded one (Chinese or imperfect English kept as-is). Where the repository recorded no attempt for a given angle, it says so — none are invented. No interview frequencies are claimed. The strong answers are trimmed for speaking aloud.

Each day is organized Beginner → Intermediate → Senior. Per-question fields: Question · Why interviewers ask · Core mental model · Actual student attempt (if recorded) · Technical error · English error · Strong spoken answer · Senior expansion · Common trap · Related day.

---

# Day23 — Docker Fundamentals

## Beginner — What is a Docker container, and how is it different from a VM?

**Why interviewers ask:** it separates "used Docker" from "understands isolation."
**Core mental model:** a container is an isolated process sharing the host kernel (namespaces + cgroups), not a small VM.
**Actual student attempt (preserved):** "docker container是一个环境隔离的进程。不具备独立操作系统和内核，最核心的区别就是虚拟机有独立操作系统和内核。"
**Technical error:** none — correct.
**English error:** the attempt was in Chinese; for an English interview, translate as below.
**Strong spoken answer:** "A container is an isolated process that runs through the host kernel. Namespaces isolate what it can see and cgroups bound its CPU and memory. Unlike a VM, it does not boot its own guest kernel, so it starts fast with lower overhead but has a generally weaker isolation boundary."
**Senior expansion:** an unbounded container can exhaust host memory and starve neighbours — cgroup limits contain the blast radius.
**Common trap:** calling it "a lightweight VM."
**Related day:** Day23 → Day26 (Pod wraps containers).

## Intermediate — Image vs container, and what happens on a rebuild?

**Why interviewers ask:** tests the immutable-artifact model.
**Core mental model:** image = immutable template; container = runtime instance; a rebuild does not touch running containers.
**Actual student attempt (preserved):** "我觉得image与container类似python中类对象与实例对象的关系。"
**Technical error:** analogy is right; the wording "an image generates images" was corrected — `run` makes a container, not another image.
**English error:** n/a (Chinese).
**Strong spoken answer:** "An image is an immutable template of read-only layers; a container is one runtime instance with its own writable layer and runtime config. One image can back many containers. Rebuilding an image does not upgrade running containers — you start new ones from the new image and replace the old."
**Senior expansion:** editing a live production container leaves the change only in its writable layer — no audit, no reproducibility, no rollback.
**Common trap:** "a rebuild auto-upgrades running containers."
**Related day:** Day25 (promote the digest, don't rebuild).

## Senior — Why avoid modifying a running production container?

**Why interviewers ask:** probes release discipline and rollback thinking.
**Core mental model:** immutable replacement, not live mutation.
**Actual student attempt (preserved):** the lesson records the student-derived answer — the change lives only in the writable layer, disappears on the next container, is not reproducible/auditable, and breaks rollback.
**Technical error:** none.
**Strong spoken answer:** "Because the change only affects that container's writable layer, not the image — it is not reproducible or auditable and it breaks rollback. The correct flow is: update version-controlled inputs, build and verify a new immutable image, start a new container, run health checks, switch traffic, then remove the old container."
**Senior expansion:** this is the same integrity chain as Day22 (build once, deploy the verified digest).
**Common trap:** treating `docker exec` fixes as a hotfix.
**Related day:** Day25 blue-green.

---

# Day24 — Docker Compose

## Beginner — What problem does Compose solve vs manual `docker run`?

**Why interviewers ask:** checks the "reproducible system" idea, not just syntax.
**Core mental model:** Compose is a tool for declaring a reproducible multi-service system on one host.
**Actual student attempt (preserved, English interview):** "the docker compose is a multi-container application what incloud services, networks, volumes, and it's a good for team collaboration. it is a reproducibility declarative configuration"
**Technical error:** "is a multi-container application" — it is a *tool for defining and running* multi-container applications, not the application itself.
**English error:** "incloud" → "includes"; "a reproducibility declarative configuration" → "a reproducible, declarative configuration."
**Strong spoken answer:** "Docker Compose is a tool for defining and running multi-container applications. A Compose file declaratively describes the services, networks, volumes, and runtime config. Versus many manual `docker run` commands, it removes missing parameters and configuration drift, and because it is version-controlled, everyone reproduces the same environment."
**Senior expansion:** reproducible system = reproducible images + runtime config + service relationships.
**Common trap:** describing Compose as an app rather than a tool.
**Related day:** Day26 (cluster vs one host).

## Intermediate — `depends_on` vs healthcheck vs application retry?

**Why interviewers ask:** the classic "started ≠ ready" trap.
**Core mental model:** ordering vs readiness proof vs runtime resilience — you need all three.
**Actual student attempt (preserved, English interview):** "the depends_on is startup order, the health check is a tool for check service readiness, and application-level retry is a retry with backoff when the application meet runtime failure, transient failure"
**Technical error:** direction correct; tighten that short `depends_on` waits only for the container to *start*, not to be ready.
**English error:** "meet" → "meets"; "check service readiness" → "checking service readiness."
**Strong spoken answer:** "`depends_on` controls startup order; with its short syntax it only waits for the dependency to start, not to be ready. A healthcheck tests whether a service can actually serve. Application retry handles transient failures during and after startup, usually with bounded exponential backoff. Initial orchestration cannot replace runtime resilience."
**Senior expansion:** a healthcheck reports health; it does not repair or restart the service.
**Common trap:** believing `depends_on` guarantees readiness.
**Related day:** Day26 readiness/liveness.

## Senior — When is Compose acceptable in production, and when do you need a cluster?

**Why interviewers ask:** tests boundaries and honesty.
**Core mental model:** controlled single-host with extra controls vs multi-node scheduling/self-healing/scaling/rollout.
**Actual student attempt (preserved):** the student selected Compose for local/CI, Compose-with-controls for a small single-host internal system, and a cluster/managed platform for a 99.99% public AI API.
**Technical error:** none — correct and nuanced.
**Strong spoken answer:** "I'd use Compose for a small single-host production system when the business accepts one host as a failure domain — it's operationally simple — but I'd still add backups, monitoring, TLS, secret management, resource limits, and a rollback process. I'd choose Kubernetes or a managed platform when I need multi-node scheduling, self-healing, autoscaling, and rolling updates. Kubernetes continuously reconciles actual to desired state across a cluster; Compose coordinates services on one host when commands run."
**Senior expansion:** the deciding factors are availability target, failure domain, traffic, deployment frequency, recovery needs, data importance, team ability, and cost — not "small vs large project."
**Common trap:** "Compose can never be used in production."
**Related day:** Day25/26.

---

# Day25 — Deployment Foundations

## Beginner — What does a reverse proxy do for a production API?

**Why interviewers ask:** tests the stable-entry / replaceable-backend split.
**Core mental model:** stable public contract (domain/URL/TLS) decoupled from a replaceable backend.
**Actual student attempt (preserved, English interview):** "there are some problem is resolved by reverse proxy, for example, it offer a public entry for client, the interna backend only offer bussiness service. and the TLS is the more safer connect style than http, it's easy to swtich backend replacement"
**Technical error:** direction correct; a reverse proxy can *terminate* TLS when configured (not automatically).
**English error:** "interna" → "internal"; "bussiness" → "business"; "swtich" → "switch"; "the more safer" → "more secure."
**Strong spoken answer:** "A reverse proxy provides a stable public entry, keeps backends internal, can terminate TLS, and forwards requests to the right backend. Because the client talks to the proxy's domain and URL, the backend can be replaced without changing the client's contract."
**Senior expansion:** the goal is not hiding a port but not exposing the backend port publicly.
**Common trap:** "the reverse proxy is just for load balancing."
**Related day:** Day27 Ingress (same idea at L7).

## Intermediate — Walk through a zero-downtime API deployment.

**Why interviewers ask:** tests verify/observe/drain/rollback discipline.
**Core mental model:** promote → start Green → verify → switch → observe + drain → roll back or finish.
**Actual student attempt (preserved):** the student chose keep v1 serving → start v2 → verify → switch traffic; the recorded correction was to say "switch traffic back to Blue," not "rollback the old container," and to stress that health signals differ from real production behavior.
**Technical error:** wording — "rollback the old container" should be "switch traffic back to Blue."
**English error:** n/a (concept correction).
**Strong spoken answer:** "I promote the approved digest, start Green without production traffic, verify it directly with readiness and smoke checks, validate Nginx with `nginx -t`, then gracefully switch traffic. I observe Green under real traffic while draining Blue's in-flight requests. If the error rate is bad, I switch traffic back to Blue and drain v2 safely; if it's healthy, I end the rollback window and remove Blue. Health checks are necessary but not sufficient."
**Senior expansion:** a stateless container is not a stateless operation — safe retry needs idempotency/job-id/checkpoints.
**Common trap:** deleting v1 the instant traffic switches (breaks streaming/drain).
**Related day:** Day27 Rolling Update.

## Senior — How do API, worker, and PostgreSQL differ during a deployment?

**Why interviewers ask:** tests compute-vs-durable-contract judgment.
**Core mental model:** API/worker are replaceable compute; PostgreSQL schema is a shared durable contract.
**Actual student attempt (preserved):** the student first reused the drain model, then correctly ordered Expand-Migrate-Contract; the recorded correction: PostgreSQL does NOT follow the same blue-green steps.
**Technical error:** initial reuse of blue-green for schema — corrected to Expand-Migrate-Contract.
**Strong spoken answer:** "I blue-green the API and roll out a backward-compatible worker consumer first. PostgreSQL schema is a shared durable contract, so I use Expand-Migrate-Contract: add the new column, deploy code compatible with both, backfill, verify, and only contract in a later release after the rollback window. Everything runs under a serialized production lock with a least-privilege short-lived identity, bounded timeouts, observation, and a recorded rollback path."
**Senior expansion:** a destructive schema change breaks a still-running v1 and rollback compatibility.
**Common trap:** renaming a column in one step during deploy.
**Related day:** Day28 (data contracts + idempotency).

---

# Day26 — Kubernetes Foundations

## Beginner — What is a Pod, and why is it not the same as a container?

**Why interviewers ask:** the most common Kubernetes basics check.
**Core mental model:** smallest deployable unit; one or more tightly coupled containers sharing network/lifecycle.
**Actual student attempt (preserved, English interview):** "pod is a sevral compose of container,it depend on deployment schedual.it is the smallest deployable unit.one or more containers share common lifecycle/network in pod."
**Technical error:** a Pod does NOT depend on a Deployment, and a Deployment does not schedule it to a Node (the scheduler does).
**English error:** "sevral" → "several"; "compose of" → "consists of"; "depend" → "depends"; "schedual" → "scheduled."
**Strong spoken answer:** "A Pod is the smallest deployable unit in Kubernetes. It contains one or more tightly coupled containers that share the same network namespace and lifecycle. A Deployment can manage Pod replicas, while the Kubernetes scheduler decides which node runs each Pod."
**Senior expansion:** co-locate only what must share fate/network/volume; independent scaling/lifecycle → its own workload (FastAPI + PostgreSQL should not share a Pod).
**Common trap:** "a Pod must have multiple containers" / "a Deployment schedules Pods."
**Related day:** Day23 container; Day27 workloads.

## Intermediate — A Pod fails and its replacement gets a new IP. How do Deployment and Service keep the app available?

**Why interviewers ask:** tests the reconciliation + discovery split.
**Core mental model:** Deployment maintains replicas; Service provides stable label-based discovery.
**Actual student attempt (preserved, English interview):** "the deployment offer replica recovery pod,service offer stable network access"
**Technical error:** correct distinction, incomplete mechanism (Service selects current Pods by labels).
**English error:** "offer replica recovery pod" → "recreates a replacement Pod"; "offer stable network access" → "provides stable network access."
**Strong spoken answer:** "The Deployment maintains the desired number of replicas, so if a Pod fails it creates a replacement. The Service selects the current Pods by their labels and provides a stable DNS name and virtual IP, so clients never track changing Pod IPs."
**Senior expansion:** `Pod Running != Service has endpoints != request succeeds`; the selector must match the Pod labels.
**Common trap:** binding clients to a Pod IP.
**Related day:** Day27 Ingress → Service → Pods.

## Senior — After a Secret rotation, one replacement Pod reads an invalid key; `/health` is 200 but AI requests return 401. Diagnose and roll back without a full outage.

**Why interviewers ask:** tests "health ≠ business success" and reconciliation-as-amplifier.
**Core mental model:** correct the desired state (Secret) first, then let controlled replacement heal; never delete the healthy Pods.
**Actual student attempt (preserved, English interview):** "the result of return 200 is not meaning logs,bussiness metric,error rate,latency process health.i would recovry old stable secrets,and then delete pod which goes wrong,deployment replace a new replica pod.the new pod recive old secrets."
**Technical error:** rollback direction correct; add freeze, verify Secret restoration, remove only the faulty Pod, run a real business smoke test, observe recovery.
**English error:** "is not meaning" → "does not prove"; "bussiness" → "business"; "recovry" → "restore"; "recive" → "receive."
**Strong spoken answer:** "First I'd freeze further rotation and avoid deleting the two healthy Pods. A 200 from health doesn't prove real AI requests work, so I'd confirm via the 401 rate, logs, and business metrics. Then I'd restore the previous known-good Secret and verify the Secret object updated. I'd delete only the faulty Pod, let the Deployment replace it, verify the new Pod gets the restored credential, then run a real AI smoke test and watch error rate and latency before completing the rollback."
**Senior expansion:** deleting the healthy old Pods while the wrong Secret is current turns a partial outage into a full one — reconciliation amplifies a bad desired state.
**Common trap:** trusting `/health` 200; Base64 "is encryption."
**Related day:** Day28 provenance + data repair.

---

# Day27 — Kubernetes Workloads

## Beginner — Difference between a Service and an Ingress?

**Why interviewers ask:** tests the L4/L7 split, not "internal vs external."
**Core mental model:** Service = stable L4 discovery; Ingress = L7 Host/Path/TLS routing to Services.
**Actual student attempt (preserved, English interview):** "service avoid to use pod ip ,provide a method to switch traffic to pod.ingress provide a entry point,by using domain and path link service"
**Technical error:** direction correct; refine Service to stable endpoint discovery and Ingress to HTTP/HTTPS Host/Path routing.
**English error:** "avoid to use" → "avoids depending on"; "a entry" → "an entry"; "link service" → "routes to a Service."
**Strong spoken answer:** "A Service provides a stable network endpoint for a group of Pods and routes to them, so clients don't depend on changing Pod IPs. An Ingress provides HTTP/HTTPS routing based on hostnames and paths and forwards requests to the right Services."
**Senior expansion:** an Ingress resource does nothing without an Ingress Controller; routing `/admin` is not authentication.
**Common trap:** "Service is internal, Ingress is external."
**Related day:** Day25 Nginx (same L7 idea).

## Intermediate — Low CPU but growing queue backlog. Why can a CPU-based HPA fail, and what metric instead?

**Why interviewers ask:** the classic external-wait scaling trap.
**Core mental model:** scale on the real bottleneck (queue backlog), on the consumer, bounded by upstream capacity.
**Actual student attempt (preserved, English interview):** "i would use the queue backlog as a metirc."
**Technical error:** metric correct, cause omitted — the workload waits on an external service, so CPU stays low.
**English error:** "i" → "I"; "metirc" → "metric."
**Strong spoken answer:** "A CPU-based HPA can fail because the workload is waiting on an external service instead of using CPU, so CPU stays low while requests accumulate. I'd use queue backlog, preferably backlog per worker, and cap the replica count so scaling doesn't exceed the provider's rate limit."
**Senior expansion:** HPA updates desired replicas on a scale target — it doesn't create Pods; more replicas don't create upstream capacity and can worsen 429s/cost.
**Common trap:** "CPU is always the scaling metric."
**Related day:** Day28 (scale the worker consumer, not the API).

## Senior — Safely deploy a new version, detect a business failure, and roll back without an outage.

**Why interviewers ask:** tests Rolling-Update-vs-rollback and Helm honesty.
**Core mental model:** keep old capacity Ready, watch business signals, restore the previous revision.
**Actual student attempt (preserved, English interview):** "helm is a great method,it could automatly rollback old version application.when the old version application stable running under smoke test.Kubernetes rolling update old version step by step"
**Technical error:** Helm does not auto-roll back every upgrade by default; Readiness cannot detect every business failure; Rolling Update replaces (rollback restores a revision).
**English error:** "automatly" → "automatically"; "stable running" → "runs stably"; "rolling update old version step by step" → "gradually replaces the old version."
**Strong spoken answer:** "I'd use a Rolling Update with `maxUnavailable: 0` and a controlled `maxSurge`, so old Pods stay available until new Pods pass Readiness. During the rollout I'd watch error rate, latency, logs, queue pressure, and business metrics — not just health checks. If the new version caused a business failure I'd stop the rollout and restore the previous Deployment or Helm revision. `--atomic`, `--wait`, and a timeout help with readiness failures, but business rollback still needs observability, and database changes must stay backward compatible because Helm can't undo every external side effect."
**Senior expansion:** deleting v2 Pods is not a rollback — the controller recreates the current v2 desired state.
**Common trap:** "delete the broken Pods to roll back"; "helm lint proves it works."
**Related day:** Day28 (compute rollback ≠ data repair).

---

# Day28 — AI Backend Production Architecture

## Beginner — Why run a long job in a Celery worker instead of the FastAPI request?

**Why interviewers ask:** tests request-vs-job lifecycle.
**Core mental model:** accept fast (`202 + job_id`), process async; decouple lifecycles.
**Actual student attempt (preserved, English interview):** "because long time response influence next request."
**Technical error:** right idea, incomplete — add HTTP timeouts and lifecycle decoupling.
**English error:** ungrammatical; "long time response influence next request" → "a long response blocks other requests."
**Strong spoken answer:** "A long job should run in a Celery worker because keeping it in the FastAPI request can cause HTTP timeouts and consume API capacity. A worker decouples the job lifecycle from the request, so the job continues after the client disconnects or the API Pod restarts."
**Senior expansion:** a long `async def` inside FastAPI is not a durable job system (no durable acceptance, redelivery, retry, or restart survival).
**Common trap:** "just make the endpoint async."
**Related day:** Day27 (separate API/worker Deployments).

## Intermediate — Which component owns which state: PostgreSQL, Redis, or Object Storage?

**Why interviewers ask:** state ownership is the core Day28 judgment.
**Core mental model:** PostgreSQL owns durable truth; Redis delivers; Object Storage owns large bytes.
**Actual student attempt (preserved, English interview):** "the postgresql restore state and Object Storage key ,redis restore queue and Object Storage restore document"
**Technical error:** mapping correct, but Redis is the broker (delivers), not the owner.
**English error:** "restore" → "stores."
**Strong spoken answer:** "PostgreSQL stores durable job state, metadata, and object references. Redis acts as the Celery broker and delivers task messages, but it's not the source of truth. Object Storage stores the original documents and large generated results."
**Senior expansion:** after `202`, every accepted job state is a durable commitment in PostgreSQL — memory and the broker are not the truth.
**Common trap:** "queued jobs live in Redis, so Redis owns them."
**Related day:** Day26 (replaceable Pods must not own truth).

## Senior — Under at-least-once delivery, prevent duplicate durable effects and minimize duplicate provider calls. What risk remains?

**Why interviewers ask:** the deepest Day28 idea (idempotency + exactly-once myth).
**Core mental model:** at-least-once + idempotent effects; unique constraint; ACK after durable write; never claim exactly-once.
**Actual student attempt (preserved, English interview):** "我忘了" (I forgot). *Teaching note preserved from the lesson: the student blanked, so the senior answer was taught directly — this question needs direct teaching because the prerequisite delivery-semantics were missing.*
**Technical error:** n/a (no attempt; do not fabricate one).
**English error:** n/a.
**Strong spoken answer:** "I'd assume at-least-once delivery and make the worker idempotent. Each embedding operation uses a stable key of job ID, chunk hash, and model version. I'd store durable step checkpoints in PostgreSQL and use a unique constraint or idempotent upsert for the result, and acknowledge the queue message only after the result and checkpoint are persisted. If the task is redelivered, the new worker detects the completed step and skips the duplicate model call and write. For an external provider or vector store, I'd also use provider idempotency keys or stable vector IDs and reconcile dual-write gaps — I would not claim exactly-once across independent systems."
**Senior expansion:** a provider call that succeeds before the local checkpoint write can still be repeated on redelivery (cost) — the remaining risk that reconciliation, not exactly-once, addresses.
**Common trap:** "read-then-upsert gives exactly-once."
**Related day:** Day27 rollback (compute) + Day28 data repair.

---

# Cross-course System Questions

These integrate Day23–Day28. Each maps to one of the phase's engineering judgments.

## Image vs Container — and why does the distinction matter for deployment?
Image = immutable artifact identity; container = replaceable instance. It matters because deployment *promotes the exact verified image digest* rather than rebuilding — tested = deployed (Day23/25). Trap: "rebuild on the prod host."

## Compose "started" vs "ready" — why is the difference a production risk?
A started container may still be initializing; dependents that assume "started = ready" fail on a race. Use `depends_on: service_healthy` + a real probe + application retry (Day24). Trap: "`depends_on` guarantees readiness."

## Promotion vs Rebuild — why is "build once, deploy many" a safety property?
Rebuilding per environment can drift (base image/deps), so the deployed artifact would differ from the tested one. Promote the immutable digest; runtime differences live in configuration/ConfigMap/Values (Day23/25/26). Trap: "reuse the artifact just to save build time."

## Blue-Green vs Rolling Update — when and how do they differ?
Blue-Green runs two full environments and switches traffic (fast fallback, double resources); Rolling Update replaces gradually under one selector within `maxSurge`/`maxUnavailable` (fewer resources, mixed versions → needs backward compatibility) (Day25/27). Trap: calling a manual Service switch a "Rolling Update."

## Deployment vs Scheduler — who places Pods?
A Deployment maintains a template + replica count and recreates missing Pods; kube-scheduler places Pods on Nodes; HPA sets the desired count. None of them is the same actor (Day26/27). Trap: "the Deployment schedules Pods."

## Service vs Ingress — what layer does each own?
Service = stable L4 discovery/endpoints; Ingress = L7 Host/Path/TLS routing to Services (resource declares, controller implements) (Day27). Trap: "Service internal, Ingress external."

## HPA vs Deployment — what does HPA actually change?
HPA updates the desired replicas on a scale target; the Deployment reconciles Pods; the scheduler places them. Scale on the real bottleneck (queue backlog for external-wait workers), capped by upstream capacity (Day27/28). Trap: "HPA creates Pods."

## StatefulSet vs Database HA — what does a StatefulSet NOT give you?
Stable identity + per-Pod PVC + ordered lifecycle — but not WAL/streaming replication, leader election, failover, fencing, routing, or backup/PITR. Three PVCs = isolation, not three copies (Day27). Trap: "a StatefulSet makes PostgreSQL highly available."

## Request vs Job Lifecycle — where does the work belong and what is committed at `202`?
Long work belongs in a worker; `202 + job_id` commits a durable Job in PostgreSQL, so it survives client disconnect and Pod restart (Day28). Trap: "an async endpoint is a durable job system."

## PostgreSQL vs Redis vs Object Storage — who owns what?
PostgreSQL owns durable truth (Job lifecycle, Outbox, events, provenance, references); Redis delivers/caches (transient); Object Storage owns large immutable/derived bytes. Everything transient must be reconstructable from durable truth (Day28). Trap: "Redis owns the queued job."

## Outbox and At-least-once — why can't you write DB and queue atomically?
Two independent systems can't be written in one transaction; a crash between DB commit and publish loses the message. The Transactional Outbox makes state + intent atomic in the DB and a relay publishes — still at-least-once (Day28). Trap: "the Outbox gives exactly-once."

## Idempotency and the Exactly-once Misconception — what does a unique constraint guarantee?
A DB unique constraint + upsert prevents duplicate *durable writes* for a key; it does not undo a duplicate external call that already succeeded. Assume at-least-once and reconcile external effects; never promise exactly-once across systems (Day28). Trap: "read-then-write prevents all duplicates."

## Monitoring vs Observability — what does each answer?
Monitoring compares known signals to thresholds/SLOs (is something abnormal?); observability correlates metrics + structured logs + traces + durable events on a stable `job_id` to explain WHY. Interpret queue depth + oldest-age + throughput together (Day28). Trap: "correlate on job_status."

## Rollback vs Data Repair — what can't a rollback fix?
Compute rollback (restore the previous desired revision) stops future bad compute; it does not fix persisted PostgreSQL state, Object Storage artifacts, or vector indexes — those need identify-by-provenance → invalidate → reprocess from originals → verify → alias switch (Day27/28). Trap: "rolling back the worker fixes the bad embeddings."

---

# Source Map

| Section | Repository Source |
|---|---|
| Day23 questions | `docs/devops/day23-docker-fundamentals.md`, `interview/devops.md` |
| Day24 questions | `docs/devops/day24-docker-compose.md`, `interview/devops.md` |
| Day25 questions | `docs/devops/day25-deployment-foundations.md`, `interview/devops.md` |
| Day26 questions | `docs/devops/day26-kubernetes-foundations.md`, `interview/devops.md` |
| Day27 questions | `docs/devops/day27-kubernetes-workloads.md`, `interview/devops.md` |
| Day28 questions | `docs/devops/day28-ai-backend-production-architecture.md`, `interview/devops.md` |
| Cross-course system questions | Day23–Day28 lessons above; `examples/ai-backend-architecture/README.md` |
