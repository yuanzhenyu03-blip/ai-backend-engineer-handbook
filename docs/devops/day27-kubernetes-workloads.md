# Lesson 27 — Kubernetes Workloads

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day26 — Kubernetes Foundations

Previous Lesson: [Day26 — Kubernetes Foundations](day26-kubernetes-foundations.md)

Next Lesson: Day28 — AI Backend Production Architecture (planned — see [ROADMAP.md](../../ROADMAP.md) and [CURRICULUM.md](../../CURRICULUM.md))

Engineering Artifact: A conceptual, teaching-only Helm chart (`examples/kubernetes/rag-platform/`) that packages the Day26 workload plus Ingress, an autoscaling/v2 HPA, a Rolling Update Deployment, and a StatefulSet + headless Service, with per-environment Values and a static-only validation helper — see [examples/kubernetes/README.md](../../examples/kubernetes/README.md).

DevOps Cheat Sheet: [cheat_sheets/devops.md](../../cheat_sheets/devops.md)

DevOps Interview: [interview/devops.md](../../interview/devops.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 90-120 minutes
Hands-on chart authoring / static validation: 90-120 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Explain Ingress as Layer-7 Host/Path/TLS routing to Services, and the Ingress resource vs Ingress Controller split.
* Explain HPA as updating desired replicas on a scale target (not creating Pods directly), and choose a meaningful pressure signal.
* Explain why a low-CPU, external-wait workload needs queue backlog rather than CPU as its scaling metric.
* Perform a Deployment Rolling Update with `maxSurge`/`maxUnavailable`, and distinguish it from rollback and Blue-Green.
* Explain why deleting v2 Pods is not a rollback, and restore a known-good desired revision instead.
* Explain StatefulSet stable identity, per-Pod PVCs, headless Service, and ordered lifecycle — and why that is not database replication.
* Separate Helm templates from environment Values, and use `helm lint`/`helm template` as static-only validation.
* Explain why real Secrets must never live in Helm Values, and where release history can leak them.
* Answer beginner, intermediate, and senior Kubernetes workload interview questions in English.

The engineering artifact is a Helm chart and validation notes, not application code.

---

# Why This Matters

Day26 gave a declarative desired-state foundation: Deployment maintains replaceable Pods, Service
preserves stable discovery across changing Pod IPs, and ConfigMap/Secret externalize configuration.
But that foundation did not yet provide public HTTP routing, metric-driven scaling, availability-
preserving version replacement, stable stateful identity/storage, or reusable multi-environment
packaging.

Day27's shift:

```text
Day26: keep N replaceable Pods alive and discoverable
Day27: route to them at Layer 7, scale them from real pressure, replace versions without an outage,
       give stateful workloads stable identity/storage, and package it all per environment
```

Why a backend engineer must care:

```text
Routing      -> an Ingress declares Host/Path/TLS intent; the Ingress Controller routes and commonly terminates TLS.
Elasticity   -> HPA changes desired replicas from meaningful signals (often NOT CPU for AI workers).
Availability -> Rolling Update replaces versions while keeping required capacity Ready.
State        -> StatefulSet gives stable identity/storage — but NOT replication, failover, or backup.
Packaging    -> Helm renders one template set into consistent, revisioned, per-environment releases.
Honesty      -> Static validation proves structure/rendering/API acceptance, never business success.
```

The recurring production lesson: every controller here enforces a *declared* intent. Readiness is
not business correctness, scaling does not create upstream capacity, and neither Kubernetes nor Helm
rollback can undo an incompatible migration or an external side effect.

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day25-26)
        |
        v
Current Concept (Day27: production workload patterns — Ingress, HPA, Rolling Update, StatefulSet, Helm)
        |
        v
Future Production Usage (Day28 Production AI Backend architecture)
```

Where Day27 sits:

```text
Safe deployment transition (Day25)
-> Kubernetes desired state & reconciliation (Day26)
-> Kubernetes workloads: routing, scaling, rollout, state, packaging (Day27)
-> Production AI Backend architecture (Day28)
```

Direct prerequisites reused:

```text
Day25 -> Blue-Green / drain / rollback intuition (compared here with Rolling Update).
Day26 -> Pod/Deployment/Service/ConfigMap/Secret and desired-state reconciliation (the base objects).
Day27 -> Wrap those objects with Ingress, HPA, Rolling Update, StatefulSet, and Helm packaging.
```

Future connection only (Day28): FastAPI, Celery, Redis, PostgreSQL, object storage, queues,
monitoring, and observability are assembled into one production AI Backend architecture using these
Day27 primitives. Do not implement Day28 architecture here.

---

# Lesson Map

```text
Ingress (Layer-7 Host/Path/TLS routing; resource vs controller)
  -> Autoscaling (HPA updates desired replicas from meaningful pressure; CPU vs queue backlog)
  -> Rolling Update (maxSurge/maxUnavailable; strategy vs rollback vs Blue-Green)
  -> StatefulSet (stable identity + per-Pod PVC + ordered lifecycle; NOT data replication)
  -> Helm (templates vs Values vs Release; static validation ladder; safe secrets)
  -> Integrated failure & rollback (Readiness 200 != business success)
  -> Final mental model + narrow corrections
```

---

# Core Mental Model

```text
Ingress Controller + Ingress rules
-> route HTTP/HTTPS Host/Path traffic to stable Services

Metrics pipeline + HPA
-> update workload desired replicas from meaningful pressure signals

Deployment Rolling Update
-> replace versions gradually while preserving required availability

StatefulSet + PVC
-> preserve Pod identity and storage attachment (NOT data replication or backup)

Helm Chart + Values + Release
-> render, install, revision, and roll back consistent environment-aware resources

Static validation  -> proves structure / rendering / API acceptance only
Runtime + business -> proves scheduling, routing, scaling, storage, and user-visible correctness
```

Each layer declares intent to a controller. The controllers reconcile toward that intent; they do
not guarantee the intent is correct or that the business behaves.

---

# Main Concepts

## Concept 1: Ingress — Layer-7 Entry Before Service

Tech Lead Question:

The Day26 `rag-api` Service works inside the cluster. Now you must expose `https://api.example.com/chat`
publicly. Do you bind clients to Pod IPs, or add a stable public entry — and how is this different
from the Day26 Service?

Student Thinking:

Clients should hit a stable name, not Pod IPs; but a Service already routes to Pods, so what does
Ingress add?

Student Answer:

> "选B，因为这样可以避免每次都要重新绑定IP，减少人工失误。我还有一个问题，这和day26讲的service的有什么区别"

And on who owns Host/Path routing:

> "应该由ingress在请求进入集群时完成路径分流，因为service最好只是做pod的路由指引而不是再承接从外访问的流量。如果service一多，每一个service都需要做重复性判断"

Tech Lead Review:

Right instinct. The durable split is by layer, not by "internal vs external":

```text
Service = stable DNS/virtual IP and routing to selected Pod endpoints (L3/L4)
Ingress = HTTP/HTTPS Host/Path/TLS routing to Services (L7)
```

Flow:

```text
Client -> DNS / public load balancer -> Ingress Controller -> Ingress Host/Path rule
       -> Service -> current matching Pods
```

Boundaries that matter:

```text
- Not simply "Service internal, Ingress external": some Service types expose workloads externally.
- A normal Service does NOT inspect /chat or /admin; it routes by ports and endpoints.
- The Ingress RESOURCE declares routing intent; an Ingress CONTROLLER implements it.
  An Ingress resource alone does not create a working data plane.
- Routing /admin to an admin Service is NOT authentication or authorization.
- Centralizing edge rules removes duplication but creates shared config, controller capacity,
  and blast-radius concerns.
```

Conceptual Ingress (reference only — no cert, DNS, LB, or controller was created):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rag-api
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-example-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /chat
            pathType: Prefix
            backend:
              service:
                name: rag-api
                port:
                  name: http
```

Engineering Thinking:

Put Host/Path/TLS decisions at one L7 edge; keep Services doing L4 endpoint routing. The edge is
powerful but becomes a shared dependency.

Production Example:

`api.example.com/chat -> rag-api` and `api.example.com/admin -> admin-api` live in one Ingress. The
TLS Secret is referenced, not embedded; the controller (e.g. an Nginx or cloud Ingress Controller)
must exist for any of it to serve traffic.

Framework Connection:

Day25's Nginx reverse proxy is the same L7 idea; a Kubernetes Ingress Controller is often literally
Nginx, driven declaratively by Ingress resources instead of a hand-written `nginx.conf`.

Exercise:

Decide whether `/chat` vs `/admin` routing belongs in a Service or an Ingress, and justify by layer.

## Concept 2: Autoscaling — Scale Desired Capacity From Meaningful Pressure

Tech Lead Question:

Traffic jumps 20x. Three Pods hit high CPU and P95 latency rises. What signal do you scale on, and
what actually creates the new Pods?

Student Thinking:

CPU is high, so scale on CPU utilization.

Student Answer:

> "根据某个可观测指标动态调整副本数，我选择CPU占用率"

Tech Lead Review:

Reasonable first choice for a CPU-bound API. But be precise about ownership:

```text
HPA does NOT directly create Pods.
HPA changes desired replicas on a scale target (Deployment/StatefulSet).
The controller reconciles Pods; the scheduler places them; the Service discovers ready endpoints.
```

Flow:

```text
Metrics pipeline -> HPA compares current vs target -> HPA sets target's desired replicas
-> Deployment creates/removes Pods -> scheduler places new Pods -> Service discovers ready endpoints
```

CPU utilization is measured relative to container CPU **requests**, so requests must be defined:

```yaml
resources:
  requests: { cpu: 500m, memory: 512Mi }
  limits:   { cpu: "1",  memory: 1Gi }
```

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-api
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: rag-api }
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
```

Then the scenario changes:

```text
CPU: 20%   P95 latency: 12s   Queue backlog: increasing
Cause: requests mostly WAIT on an external model service
```

Student Answer (refined signal):

> "不会，我认为Queue backlog"

Correct: CPU-only HPA will not react to an external-wait bottleneck. Use queue pressure — but scale
the workload that actually CONSUMES the queue:

```text
Queue backlog / backlog per worker -> external or custom metric adapter -> HPA
-> WORKER Deployment desired replicas (the queue consumer, NOT the API/producer)
```

Scope note: the Day27 example chart (`examples/kubernetes/rag-platform/`) has only the stateless API,
so its HPA scales the API on CPU and deliberately ships NO queue-backlog metric — wiring queue backlog
to the API would scale the producer, not the consumer. The worker Deployment (a real queue consumer)
and its backlog-driven HPA arrive with the Day28 AI Backend architecture.

Production boundaries:

```text
- HPA needs a working metrics pipeline (Metrics Server for resource; an adapter for external/custom).
- Scaling is not instant: schedule + image pull + startup + Readiness take time.
- Scaling does NOT rescue already-failed or timed-out requests.
- More Pods do NOT create more upstream model-provider capacity.
- Scaling can worsen 429s, retries, provider cost, DB pressure, or downstream saturation.
- min/max replicas, stabilization, cost limits, upstream concurrency, error rates, and retry/backoff
  must be designed together.
- P95 latency is often a symptom, not the correct control signal, when the provider is the bottleneck.
- With an HPA, the Deployment must NOT hard-code `spec.replicas`; otherwise the next `helm upgrade`/
  `kubectl apply` resets the HPA-managed count. Let the HPA own the desired replicas (the example
  chart omits `spec.replicas` when `hpa.enabled`).
```

Engineering Thinking:

Scale on the metric that represents the real bottleneck, and bound scaling by downstream capacity —
not by the most obvious number.

Production Example:

A RAG worker at 20% CPU with a growing queue scales on backlog-per-worker, capped so it never exceeds
the model provider's rate limit (or it just converts a queue into a wall of 429s).

Framework Connection:

FastAPI request latency, worker concurrency, and queue depth are different signals; the AI worker
usually scales on queue pressure, not CPU.

Exercise:

Explain why a low-CPU workload with a rising queue backlog defeats a CPU-based HPA, and pick a better
metric.

## Concept 3: Rolling Update — Preserve Availability While Changing Versions

Tech Lead Question:

You have three healthy `v1` Pods and a possibly broken `v2`. How do you release without an outage?

Student Thinking:

Don't delete v1 first; run both and switch once v2 is proven.

Student Answer:

> "会导致业务中断，应该并行运行V2与V1，先启动V2，进行健康测试，再切换service的路由指向V2 pod,再观察是否正常运行比如错误率、日志、业务指标、延迟，如果正常。就停掉V1并删除V1pod"

Tech Lead Review:

That is closer to **Blue-Green** (full parallel environments + a traffic switch). A standard
Deployment Rolling Update is gradual under one Service selector:

```text
create a small number of v2 Pods -> wait for v2 Readiness -> add ready v2 endpoints to the Service
-> remove a controlled number of v1 Pods -> repeat until replacement completes
```

With the same labels/selector, no manual Service switch is normally required.

```yaml
spec:
  replicas: 3
  revisionHistoryLimit: 5
  progressDeadlineSeconds: 600
  minReadySeconds: 10
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
```

The student reasoned the failure case correctly:

> "3个V1 pod不会中断，因为maxUnavailable=0，表示不能出现不可用，也就是说新增一个的时候不会删除之前的，现在相当于有4个pod同时运行，而这个时候新开的V2失败，并不会影响原来的V1 pod"

```text
3 v1 Pods: Ready and serving
1 v2 Pod:  NotReady, excluded from Service endpoints
rollout:   stalled
business:  still served by the three v1 Pods
```

`maxSurge: 1` allows one extra Pod; `maxUnavailable: 0` forbids reducing available capacity before a
replacement is Ready (this needs surge capacity in the cluster).

Readiness is necessary but not sufficient:

```text
/ready == 200  !=  correct AI result  !=  acceptable error rate  !=  acceptable latency
```

Strategy vs rollback:

```text
Rolling Update = controlled version-replacement strategy
Rollback       = restore the previous desired template/release revision (via another controlled rollout)
```

Deleting broken v2 Pods is NOT a rollback:

```text
delete v2 Pod -> Deployment sees a missing replica -> desired template is STILL v2
-> Deployment creates another v2 Pod
```

Student Answer (correct rollback direction):

> "快速回滚到V1，以保证服务正在运行。因为删除V2 Pod并不能解决服务的持续性提供"

Limit: a Kubernetes/Helm rollback cannot undo an incompatible DB migration, a sent message, an
external API call, or corrupted data. Keep schema changes backward compatible.

Engineering Thinking:

Change the desired state to roll back; do not fight the reconciler by deleting instances it will
recreate.

Production Example:

A broken `v2` stalls at `maxUnavailable: 0` while v1 keeps serving; the operator restores the v1
revision (`kubectl rollout undo` / `helm rollback`) rather than deleting v2 Pods in a loop.

Framework Connection:

This is Day25's rollback principle ("restore known-good, replace only the faulty unit") expressed
through a Deployment's revision history.

Exercise:

Predict the cluster state when v2 Readiness always fails with `maxSurge: 1`, `maxUnavailable: 0`, then
explain why deleting v2 Pods is not a declarative rollback.

## Concept 4: StatefulSet — Stable Identity/Storage Is Not Data Replication

Tech Lead Question:

You need three PostgreSQL instances that keep their identity and storage across restarts
(`postgres-0 -> data-postgres-0`, etc.). Why is a Deployment not the right fit?

Student Thinking:

A replacement Pod loses its local state, so a plain Deployment won't preserve the database.

Student Answer:

> "因为创建的是一个新的pod，里面的state没有保存"

Tech Lead Review:

Container-local files are ephemeral — true. But the nuance: a Deployment *can* mount a persistent
volume. You need a StatefulSet because you need a stable identity-to-storage mapping and ordered
lifecycle, not merely "a volume."

```text
StatefulSet provides:
- stable Pod identities (postgres-0/1/2);
- per-Pod PVCs from volumeClaimTemplates;
- stable reattachment of each identity to its own PVC;
- ordered creation/update/scale by default;
- commonly a headless Service for stable network identity.
```

```yaml
apiVersion: v1
kind: Service
metadata: { name: postgres }
spec:
  clusterIP: None
  selector: { app: postgres }
  ports: [{ name: postgres, port: 5432 }]
---
apiVersion: apps/v1
kind: StatefulSet
metadata: { name: postgres }
spec:
  serviceName: postgres
  replicas: 3
  selector: { matchLabels: { app: postgres } }
  template:
    metadata: { labels: { app: postgres } }
    spec:
      containers:
        - name: postgres
          image: example.invalid/postgres:replace-with-verified-digest
          volumeMounts: [{ name: data, mountPath: /var/lib/postgresql/data }]
  volumeClaimTemplates:
    - metadata: { name: data }
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 20Gi } }
```

Then the key misconception surfaced. Asked whether three PVCs mean three data copies:

> "是的，因为每一个数据盘都是独立的"

Direct correction:

```text
Independent disks = isolation and identity
Independent disks != replicated bytes
StatefulSet        != database high availability
```

The student then proposed a full copy:

> "还需增加数据全量拷贝并发送的机制"

The complete minimum production chain:

```text
initial base backup -> continuous WAL / streaming replication -> Primary health monitoring
-> leader election / controlled promotion -> fencing of the old Primary
-> client write endpoint switches to the current Primary -> independent backup + point-in-time recovery
```

Durable three-layer boundary:

```text
StatefulSet + PVC      = stable identity, stable storage attachment, ordered lifecycle
PostgreSQL HA/Operator = init, WAL replication, leader election, failover, fencing, routing
Backup system          = recovery from deletion, corruption, and replicated logical mistakes
```

Cloud-disk redundancy is not database-level replication or independent backup. HA protects
continuity; backups protect recoverability.

Engineering Thinking:

StatefulSet solves identity and storage attachment. Data safety is a separate, database-aware problem.

Production Example:

`postgres-0/1/2` each keep their PVC across reschedules, but without an operator doing WAL
replication + failover + fencing, they are three isolated databases, not one highly-available one.

Framework Connection:

This bounds Day28: a production PostgreSQL needs an operator/managed service, not a raw StatefulSet.

Exercise:

Decide whether three StatefulSet PVCs imply three copies of the same data, then list the missing
replication/failover/fencing/routing/backup mechanisms.

## Concept 5: Helm — Templates, Values, Releases, and Rollback

Tech Lead Question:

You copied Ingress/Deployment/Service/HPA/ConfigMap/Secret/StatefulSet YAML separately for dev, test,
and prod, and manual edits caused drift. How do you package this?

Student Thinking:

Object structures are common; the environment differences are the config values.

Student Answer:

> "我觉得Ingress、Deployment、Service、HPA、和 StatefulSet作为共同模版，Secret与ConfigMap作为不同环境的可变参数"

Tech Lead Review:

Good split, one correction: every object is a template, and *fields inside every object* may vary by
environment — not only ConfigMap/Secret.

| Shared structure | Common environment-specific values |
|---|---|
| Ingress | hostname, TLS Secret reference, IngressClass |
| Deployment | image digest/tag, replicas, resources, environment configuration |
| Service | ports, type, annotations when genuinely environment-specific |
| HPA | min/max replicas, targets, metric configuration |
| StatefulSet | storage size, StorageClass, replica count |
| ConfigMap | non-sensitive runtime values |
| Secret references | existing Secret name or external-secret path |

Core Helm model:

```text
Templates = reusable Kubernetes object structure
Values    = controlled parameters that are allowed to vary
Release   = rendered Chart installed and revisioned for an environment
```

Validation ladder (each layer proves something different):

```text
helm lint                       -> chart structure, template syntax, some common problems
helm template                   -> render templates with Values into Kubernetes YAML
Kubernetes server-side dry run  -> API versions, schemas, policies, cluster constraints
Runtime validation              -> scheduling, image pulls, controllers, metrics, storage, readiness,
                                   dependencies, and business behavior
```

The student stated the boundary correctly:

> "不能证明，因为helm lint、helm template只是进行了代码规范检查、以及环境变量填写到模版生成一个完整的配置文件，并不能证明在实际运行中就能成功。"

Failure/rollback scenario (revision 5 never becomes Ready):

```bash
helm history rag-platform
helm rollback rag-platform 4 --wait --timeout 10m
```

Lower future risk:

```bash
helm upgrade --install rag-platform ./rag-platform -f values-prod.yaml \
  --atomic --wait --timeout 10m
```

Important correction:

```text
Helm does NOT automatically roll back every upgrade by default.
--atomic can attempt rollback when the upgrade fails its readiness/wait conditions.
Business-level failure AFTER resources are Ready still needs observability and deployment automation.
```

Security boundary:

```text
- Do NOT commit production credentials to values-prod.yaml just because Helm supports Values.
- Template Secret REFERENCES, not real plaintext credentials.
- Use an external Secret manager / External Secrets / Sealed Secrets / protected deploy process.
- Helm release history and rendered manifests can expose plaintext if teams misuse Values for secrets.
```

Engineering Thinking:

Helm removes duplication and drift; it does not add safety or business awareness. Keep secrets out of
Values and treat rollback as a controlled reverse rollout with external-side-effect limits.

Production Example:

`helm rollback rag-platform 4 --wait` restores revision 4's desired state, then Kubernetes reconciles
a controlled reverse rollout — but it cannot un-send an email or reverse a schema migration.

Framework Connection:

Helm packages the whole Day27 workload per environment without rebuilding the application image for
each config difference — the Day26 "config outside the image" idea at release scale.

Exercise:

Separate Helm templates from Values across all Day27 objects, and distinguish `helm lint`,
`helm template`, API validation, runtime validation, and business smoke tests.

## Concept 6: Integrated Production Failure and Rollback

Tech Lead Question:

A release passes Kubernetes Readiness but fails at the AI business layer. What is the safe end-to-end
model across Rolling Update and Helm?

Student Thinking:

Keep old capacity, watch business signals, and restore the previous desired revision if unsafe.

Tech Lead Review:

Production-safe model:

```text
render and review the intended release
-> validate against available schemas/policies
-> begin a controlled Rolling Update
-> keep old capacity while new Pods become Ready
-> observe error rate, latency, logs, queue pressure, and business metrics
-> stop progression when evidence is unsafe
-> restore the previous Deployment/Helm desired revision
-> verify old Pods become Ready and serve real requests
-> confirm Service endpoints and business recovery
-> preserve evidence and investigate the failed version
```

```text
Deleting individual v2 Pods is not a rollback (the controller recreates the current v2 desired state).
helm rollback / Deployment rollback restores the desired revision via a controlled reverse rollout.
Database migration compatibility and external side effects remain explicit limits.
```

Engineering Thinking:

Roll back the declaration, not the instances; and never assume Readiness or Helm proves the business
recovered.

Production Example:

Revision 5 is Ready but returns wrong AI answers; the operator halts the rollout and runs
`helm rollback rag-platform 4 --wait`, then confirms recovery via a real AI smoke test and metrics.

Framework Connection:

Same shape as Day25/Day26 rollback, now spanning routing, scaling, rollout, and packaging.

Exercise:

Order a safe release-and-rollback that keeps old capacity Ready, uses business signals (not just
`/ready`), and restores a previous revision.

---

# Common Misconceptions

## Mental Model Evolution (Day26 -> Day27)

```text
Initial: "Day26 kept N replaceable Pods alive and discoverable, so the workload is production-ready."
Reasoning: Deployment reconciles replicas and a Service gives stable discovery.
Correction: That is the base only — no public L7 routing, no metric-driven scaling, no controlled
            version replacement, no stable stateful identity/storage, no per-environment packaging.
Final: Day27 wraps the Day26 objects with Ingress (L7 routing), HPA (scale from real pressure),
       Rolling Update (availability-preserving replacement), StatefulSet (identity/storage, NOT HA),
       and Helm (environment-aware releases) — while static validation still never proves business
       correctness.
```

## Misconception list

```text
Service vs Ingress
❌ Service is internal, Ingress is external.
✅ Ingress is L7 Host/Path/TLS routing to Services; Service is stable discovery/endpoints. Some
   Service types expose externally, and a normal Service does not inspect HTTP paths.
```

```text
HPA creates Pods
❌ HPA directly creates and deletes Pods.
✅ HPA updates desired replicas on a scale target; the Deployment/StatefulSet reconciles Pods and the
   scheduler places them.
```

```text
CPU is always the scaling signal
❌ CPU utilization is the right HPA metric.
✅ An external-wait workload can sit at low CPU while its queue grows; scale on backlog/backlog-per-
   worker, bounded by upstream capacity.
```

```text
Rolling Update needs a manual Service switch
❌ Run v1 and v2, then switch the Service to v2.
✅ That is Blue-Green. Rolling Update adds ready v2 Pods under the same selector and removes v1 within
   surge/unavailability limits — no manual switch.
```

```text
Rolling Update is a rollback strategy
❌ Rolling Update rolls back.
✅ Rolling Update is controlled replacement; rollback restores a previous desired revision via another
   controlled rollout.
```

```text
Deleting broken Pods rolls back
❌ Deleting v2 Pods recovers the previous version.
✅ If the desired template is still v2, the controller recreates v2. Restore the known-good revision.
```

```text
Three PVCs = three data copies
❌ A StatefulSet with three PVCs replicates the database.
✅ Each PVC holds its own bytes; StatefulSet gives identity/storage, not replication, failover, or
   backup.
```

```text
One full copy = database failover
❌ Copying the data once provides HA.
✅ A base backup only initializes a replica; ongoing writes need WAL/streaming replication, plus
   leader election/promotion and fencing for safe takeover.
```

```text
Only ConfigMap/Secret vary by environment
❌ Templates are fixed; only ConfigMap/Secret change per environment.
✅ Every object is a template; hosts, images, replicas, resources, HPA targets, storage class/size,
   and Secret references may all vary via Values.
```

```text
Helm rolls back automatically
❌ Helm auto-rolls back every failed upgrade.
✅ `helm rollback` restores a revision; `--atomic --wait --timeout` can attempt rollback on readiness
   failure; business failures and external side effects are not auto-detected or reversed.
```

```text
Static validation proves production
❌ helm lint / helm template passing means the release works.
✅ lint/render, API admission, runtime infrastructure, and business verification prove different
   things; only runtime + business smoke tests prove user-visible correctness.
```

---

# Engineering Trade-offs

```text
Ingress edge vs per-Service edges
+ One L7 place for Host/Path/TLS; less duplication.
- Shared controller/config boundary; needs controller capacity and its own security.
```

```text
CPU metric vs custom/external metric
+ CPU: simple, always available.
- CPU: misses I/O-bound / external-wait pressure.
+ Custom/external: represents the real bottleneck.
- Custom/external: extra telemetry + adapter reliability.
```

```text
Aggressive scaling vs bounded scaling
+ Reduces queue delay.
- Can increase provider 429s, DB load, cost, and oscillation. Cap max replicas to upstream capacity.
```

```text
maxUnavailable: 0 vs allowing unavailability
+ Protects capacity during rollout.
- Needs surge resources; can stall when the cluster lacks capacity.
```

```text
Rolling Update vs Blue-Green
+ Rolling: fewer parallel resources.
- Rolling: mixes versions; requires backward compatibility.
+ Blue-Green: clean switch, easy fallback.
- Blue-Green: temporarily doubles infra; still needs schema/state compatibility.
```

```text
StatefulSet vs Deployment+volume
+ StatefulSet: stable identity + per-Pod storage + ordered lifecycle.
- StatefulSet: ordered/storage operational complexity; NOT application-level HA.
```

```text
Database replicas vs backups
+ Replicas improve availability.
- Replicas do not replace backups; replicated mistakes reach every replica.
```

```text
Helm templating vs raw YAML
+ Helm: less duplication and drift; environment-aware releases.
- Helm: over-templating gets hard to read and debug.
```

```text
--atomic vs manual rollback
+ Reduces time stuck in some failed release states.
- Cannot detect every business regression or undo external side effects.
```

```text
Static validation vs runtime validation
+ Static: fast, deterministic.
- Static: limited — no scheduling, routing, scaling, storage, or business proof.
```

---

# Hands-on Exercises

The engineering artifact is a Helm chart (see `examples/kubernetes/rag-platform/`).

## Exercise 1: Why Not a Pod IP

Question: Why should a public client never bind directly to a Pod IP?
Expected Output: Pod IPs are ephemeral; use a stable Service, exposed at L7 through Ingress.
Follow-up: Which layer terminates TLS and routes by Host/Path?

## Exercise 2: Service vs Ingress

Question: Which layer owns Host/Path routing, and why is "internal vs external" the wrong split?
Expected Output: Ingress owns L7 Host/Path/TLS; Service owns L4 discovery/endpoints; some Service
types expose externally.
Follow-up: Does an Ingress resource work without an Ingress Controller?

## Exercise 3: `/chat` and `/admin`

Question: Where does `/chat` vs `/admin` routing belong?
Expected Output: In the Ingress; a normal Service does not inspect paths. Routing `/admin` is not auth.

## Exercise 4: Initial Scaling Metric

Question: Pick an initial scaling metric for a CPU-bound FastAPI workload.
Expected Output: CPU utilization vs requests — valid when CPU-bound.
Follow-up: What breaks this when the workload waits on an external model?

## Exercise 5: Low-CPU, Growing Backlog

Question: Diagnose why CPU-only HPA misses a low-CPU workload with rising queue backlog.
Expected Output: Requests wait externally; CPU stays low while the queue grows. Scale on backlog /
backlog-per-worker, bounded by upstream capacity.
Follow-up: Why can more replicas worsen provider 429s and cost?

## Exercise 6: Surge Rollout

Question: Design a rollout that keeps three v1 replicas available while testing one v2 surge Pod.
Expected Output: `maxSurge: 1`, `maxUnavailable: 0`, `minReadySeconds`, `progressDeadlineSeconds`.
Follow-up: What must the cluster provide for the surge Pod?

## Exercise 7: Stalled Rollout

Question: Predict the state when v2 Readiness always fails with `maxSurge: 1`, `maxUnavailable: 0`.
Expected Output: 3 v1 Ready and serving; 1 v2 NotReady, excluded; rollout stalled; business unaffected.
Follow-up: Why is deleting the v2 Pod not a rollback?

## Exercise 8: Blue-Green vs Rolling Update

Question: Compare Blue-Green switching with Deployment Rolling Update.
Expected Output: Blue-Green = parallel envs + switch; Rolling Update = gradual same-selector
replacement within surge/unavailability limits.

## Exercise 9: Deployment + Volume vs StatefulSet

Question: Why is a Deployment plus a volume not always enough for PostgreSQL identity/storage?
Expected Output: Need stable identity-to-PVC mapping and ordered lifecycle, not merely a volume.

## Exercise 10: Three PVCs

Question: Do three StatefulSet PVCs imply three copies of the same data?
Expected Output: No — isolation/identity, not replication. List missing replication/failover/fencing/
routing/backup.

## Exercise 11: Helm Templates vs Values

Question: Separate Helm templates from environment Values across all Day27 objects.
Expected Output: Every object is a template; hosts, images, replicas, resources, HPA targets, storage,
ConfigMap values, and Secret references are Values.

## Exercise 12: Secrets in Values

Question: Why must real Secrets never be committed to Helm values files?
Expected Output: Values and release history/rendered manifests can leak plaintext; use references to
out-of-band Secrets.

## Exercise 13: Validation Ladder

Question: Distinguish `helm lint`, `helm template`, Kubernetes API validation, runtime validation, and
business smoke tests.
Expected Output: structure/syntax; rendered YAML; API schema/policy; infra behavior; user-visible
correctness — each proves something different.

## Exercise 14: Helm Recovery

Question: Recover a failed Helm revision and reduce partial-upgrade risk.
Expected Output: `helm history` + `helm rollback N --wait --timeout`; future `--atomic --wait
--timeout`; note business failure still needs observability.

## Exercise 15: English Interview

Question: Answer the Beginner, Intermediate, and Senior questions in the English Interview section.
Expected Output: Correct content with the narrow corrections (HPA sets desired replicas; Rolling
Update != rollback; StatefulSet != replication; Helm != auto-rollback).

## Exercise 16: Final Mental Model Synthesis

Question: Produce a Chinese Mental Model connecting Ingress, HPA, Rolling Update, StatefulSet, Helm,
and the validation boundaries.
Expected Output: See the student's synthesis in Mental Model Summary, with the five narrow corrections
applied.

---

# Relevant Framework Connections

## Kubernetes

The whole lesson is Kubernetes workload and routing control: Ingress, HPA (`autoscaling/v2`),
Deployment Rolling Update, StatefulSet, Services, PVCs, metrics, and declarative desired state. Watch
for: resource-vs-controller for Ingress, metrics-pipeline prerequisites for HPA, surge capacity for
`maxUnavailable: 0`, and identity/storage-vs-replication for StatefulSet.

## Day26 Kubernetes Foundations

Day26 objects remain the base:

```text
Ingress -> Service -> Deployment-managed Pods
HPA -> Deployment scale target
ConfigMap/Secret references -> Helm templates and environment Values
```

## Day25 Deployment / Blue-Green / Nginx

The student's first release plan reused Day25-style parallel v1/v2 environments and a traffic switch;
the class compared that Blue-Green model with Rolling Update. Nginx is relevant as one Ingress
Controller implementation — not a claim that a controller was installed.

## FastAPI

FastAPI is the stateless `rag-api` workload behind Service and Ingress. Readiness is separated from
real AI correctness; CPU, concurrency, latency, and queue pressure are treated as different signals.

## PostgreSQL

PostgreSQL supplies the stateful identity/storage scenario. Base backup, WAL/streaming replication,
leader election/promotion, fencing, routing, backups, and PITR are discussed only to define what
StatefulSet does NOT provide.

No Playwright connection is used; it is not forced in.

---

# AI Backend Connections

```text
- Public https://api.example.com/chat routes through Ingress to the RAG API Service.
- Stateless FastAPI replicas remain replaceable and can be updated gradually (Rolling Update).
- External-model waits can produce low CPU with high P95 latency and increasing queue backlog.
- Queue backlog / backlog per worker may beat CPU as the worker scaling signal.
- Scaling is bounded by provider rate limits, concurrency, cost, retries, and 429 behavior.
- Readiness 200 does not prove correct model output or acceptable business behavior.
- Releases need error rate, latency, logs, queue metrics, and business-level smoke tests.
- PostgreSQL needs database-aware replication/failover/backup beyond StatefulSet/PVC.
- Helm packages the Day27 workload for environment-aware releases without rebuilding images.
- Real AI/database credentials must not be committed in Helm Values.
- Day28 will assemble API, workers, Redis, PostgreSQL, object storage, queue, monitoring, and
  observability — a future connection, not built here.
```

---

# English Interview

Key vocabulary: Ingress, Ingress Controller, IngressClass, Host/Path routing, TLS termination, HPA,
scale target, desired replicas, metrics pipeline, queue backlog, Rolling Update, `maxSurge`,
`maxUnavailable`, Readiness, rollback, revision, Blue-Green, StatefulSet, headless Service, PVC,
`volumeClaimTemplates`, WAL replication, failover, fencing, Helm chart, Values, release, `helm lint`,
`helm template`, `--atomic`.

## Beginner

Question:

What is the difference between a Kubernetes Service and an Ingress?

Actual student attempt (preserved):

> "service avoid to use pod ip ,provide a method to switch traffic to pod.ingress provide a entry point,by using domain and path link service"

Technical review: correct direction — refine Service to stable endpoint discovery/routing to current
Pods, and Ingress to HTTP/HTTPS Host/Path routing to Services.

English corrections:

```text
service avoid to use -> a Service avoids clients depending on
pod ip               -> Pod IP addresses
provide a entry      -> provides an entry / HTTP routing
link service         -> routes requests to a Service
```

Strong Answer:

> A Kubernetes Service provides a stable network endpoint for a group of Pods and routes traffic to
> them, so clients do not depend on changing Pod IP addresses. An Ingress provides HTTP or HTTPS
> routing based on hostnames and paths and forwards requests to the appropriate Services.

## Intermediate

Question:

A workload has low CPU usage but its queue backlog keeps increasing. Why might a CPU-based HPA fail,
and what metric would you use instead?

Actual student attempt (preserved):

> "i would use the queue backlog as a metirc."

Technical review: metric choice correct, cause omitted — the workload waits on an external service, so
CPU stays low while requests accumulate. Backlog per worker is more actionable, capped by upstream
capacity and cost.

English corrections:

```text
i -> I ; metirc -> metric
```

Strong Answer:

> A CPU-based HPA may fail because the workload is waiting on an external service instead of consuming
> CPU, so CPU stays low while requests accumulate. I would use queue backlog, preferably backlog per
> worker, and cap the replica count so scaling does not exceed the provider's rate limit.

## Senior

Question:

How would you safely deploy a new application version in Kubernetes, detect a business-level failure,
and roll back without causing an outage?

Actual student attempt (preserved):

> "helm is a great method,it could automatly rollback old version application.when the old version application stable running under smoke test.Kubernetes rolling update old version step by step"

Technical review:

```text
Correct    : connect Helm revision rollback, smoke testing, and Kubernetes Rolling Update.
Incomplete : Helm does not auto-roll back every upgrade by default.
Incomplete : Kubernetes Readiness cannot detect every business-level failure.
Correction : Rolling Update gradually replaces old with new while preserving availability;
             rollback restores the previous desired revision.
```

English corrections:

```text
automatly -> automatically ; old version application -> the previous stable version ;
stable running -> runs stably ; rolling update old version step by step -> gradually replaces the old
version with the new version
```

Strong Answer:

> I would use a Kubernetes Rolling Update with `maxUnavailable: 0` and a controlled `maxSurge`, so old
> Pods remain available until new Pods pass Readiness. During the rollout I would monitor error rate,
> latency, logs, queue pressure, and business metrics rather than only HTTP health checks. If the new
> version caused a business failure, I would stop the rollout and restore the previous Deployment or
> Helm revision. `--atomic`, `--wait`, and a timeout help with readiness failures, but business-level
> rollback still needs observability and deployment automation, and database changes must stay
> backward compatible because Helm cannot undo every external side effect.

---

# Mental Model Summary

```text
Ingress        = L7 Host/Path/TLS routing to Services (resource declares; controller implements)
Service        = stable L4 discovery/endpoints for current Pods
HPA            = update desired replicas on a scale target from meaningful pressure (not CPU-only)
Rolling Update = gradual same-selector replacement within maxSurge/maxUnavailable (not rollback)
Rollback       = restore a previous desired revision via another controlled rollout
StatefulSet    = stable Pod identity + per-Pod PVC + ordered lifecycle (NOT replication/HA/backup)
Helm           = Templates + Values + Release; static validation != business success
Readiness 200  != correct AI result / acceptable error rate / acceptable latency
```

Preserve the student's actual final synthesis:

> "ingress处理http/https请求，通过域名和路径寻找对应的service，HPA是一个水平自动化扩缩容POD，通过判断每个worker中的队列任务的数量，并做最大数量限制，来进行扩缩容。Rolling UPdate是回滚策略，通过设置更新过程中的最大可新增pod数量，以及设置最大不能提供服务pod数量，进行平滑版本替换。stateful是设置了容器名字以及对应的PVC，但是不代表数据就被自动复制了，还需要数据库自带的复制功能，特别是wal配合使用。helm将稳定配置与可变配置进行区分，并且可以通过命令实现自动化回滚。 静态验证通过不能证明runtime没有问题，静态验证大多数时候只是验证了helm的代码规范化、语法、还有稳定配置与变量生成的配置文件。以及对Kubernetes API进行了测试。还需要在runtime的时候进行smoke test,观察日志、错误率、延迟、业务指标等关键要素"

Narrow corrections to that synthesis:

```text
1. HPA does not directly create/delete Pods; it updates desired replicas on a scale target
   (Deployment/StatefulSet), which reconciles Pods.
2. Rolling Update is a version-replacement strategy, NOT a rollback strategy; rollback restores an
   older desired revision via another controlled rollout.
3. StatefulSet defines stable POD identities and PVC mappings, not merely container names.
4. Helm separates templates from Values, but automatic rollback is not the default; --atomic + wait/
   timeout or external automation is needed, and business failure still needs observability.
5. Queue backlog is one useful worker-scaling metric, not a universal HPA metric; choose the metric
   that represents real bottleneck pressure and respect downstream capacity.
```

---

# Today's Takeaway

```text
Most important mental model:
Each workload controller enforces a declared intent — Ingress routes at L7, HPA sets desired replicas,
Rolling Update replaces gradually, StatefulSet preserves identity/storage, Helm renders per-environment
releases. Controllers reconcile intent; they do not guarantee correctness.

Most important production risk:
Readiness 200 is not business success, scaling does not create upstream capacity, and neither
Kubernetes nor Helm rollback undoes an incompatible migration or an external side effect.

Most important framework/AI connection:
A RAG API behind Ingress + Service, scaled by queue backlog (not CPU), released via Rolling Update,
with PostgreSQL identity/storage in a StatefulSet (HA still needs an operator), all packaged by Helm.

Most important interview answer:
Rolling Update with maxUnavailable: 0 keeps old Pods until new ones are Ready; roll back by restoring
the previous revision, not by deleting Pods.
```

Scope honesty: no live Day27 Kubernetes or Helm validation occurred in class, and none is claimed in
this repository beyond deterministic static checks. Ingress Controller/DNS/TLS routing, Metrics
Server/custom adapters, HPA scaling, Rolling Update, rollback, PVC provisioning, StatefulSet ordered
lifecycle, PostgreSQL replication/failover/fencing, and backups/PITR were NOT run or implemented; see
`examples/kubernetes/README.md`.

---

# Before Next Lesson Checklist

- [ ] Can I explain Ingress L7 routing and the resource-vs-controller split in plain English?
- [ ] Can I explain that HPA updates desired replicas on a scale target instead of creating Pods?
- [ ] Can I explain why a low-CPU, external-wait workload needs queue backlog, not CPU?
- [ ] Can I run a Rolling Update with `maxSurge`/`maxUnavailable` and distinguish it from rollback and Blue-Green?
- [ ] Can I explain why deleting v2 Pods is not a rollback?
- [ ] Can I explain StatefulSet identity/storage and why it is not database replication?
- [ ] Can I separate Helm templates from Values and name the validation ladder?
- [ ] Can I explain why real Secrets must never live in Helm Values?
- [ ] Can I answer beginner, intermediate, and senior Kubernetes workload questions in English?
