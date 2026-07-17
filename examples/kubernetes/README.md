# examples/kubernetes

Day26 Kubernetes Foundations example: one RAG/FastAPI service declared as four core objects — a
ConfigMap, a Secret template, a three-replica Deployment (FastAPI + logging sidecar Pod template),
and a Service.

**Example / template only.** These are teaching manifests. They are **not deployable as-is** and no
Kubernetes runtime success is claimed. `stringData` values are plaintext placeholders, and the image
fields use syntactically valid but non-pullable references on the reserved `.invalid` TLD
(`example.invalid/acme/rag-api:replace-with-verified-digest`) whose `:replace-...` tag is mutable —
not immutable and not verified — and must be swapped for a CI-verified `@sha256:...` digest out of band. **Never** commit a real API key, password,
token, certificate, private endpoint, or a real/represented-as-verified image digest.

Lesson: `docs/devops/day26-kubernetes-foundations.md`

## Files

- `ai-backend-baseline.yaml` — ConfigMap `rag-api-config`, Secret template `rag-api-secrets`,
  Deployment `rag-api` (3 replicas), and Service `rag-api`. Deployment selector, Pod template labels,
  and Service selector all agree on `app: rag-api`.

## Object model

```text
ConfigMap  rag-api-config   -> non-sensitive runtime config (MODEL_NAME, LOG_LEVEL)
Secret     rag-api-secrets  -> sensitive values (placeholders only)
Deployment rag-api          -> Pod template + replicas: 3 (controller-managed replacement)
Service    rag-api          -> stable discovery for Pods labeled app: rag-api (port 80 -> targetPort http)

Cluster caller -> Service rag-api -> current Pods (app: rag-api) -> api container :8000
```

Only the `api` container references the Secret. The `log-sidecar` shares the Pod and the
`application-logs` volume but must not receive API/database credentials.

## Validating the manifest

Validation happens at two levels, and only the first can run inside this repository.

### Repository-level static validation (runs here)

`validate_manifest.py` performs these checks with no cluster, credentials, or images:

- the file parses as four YAML documents with kinds ConfigMap, Secret, Deployment, Service;
- the Deployment selector (`spec.selector.matchLabels`) equals the Pod template labels
  (`spec.template.metadata.labels`);
- the Service selector equals the Pod template labels;
- `spec.replicas == 3`;
- the Service `targetPort` matches a container's named port;
- the `api` container references the ConfigMap (`envFrom.configMapRef`) and the Secret
  (`env[].valueFrom.secretKeyRef`);
- the `log-sidecar` does NOT reference the Secret.

It depends only on PyYAML. From this directory (`examples/kubernetes/`):

```bash
# One-time dependency (an isolated venv keeps your system Python clean):
python3 -m venv .venv && . .venv/bin/activate && pip install pyyaml
# Or a user-site install: python3 -m pip install --user pyyaml

python3 validate_manifest.py
```

Expected output (actually produced in this repository environment):

```text
[PASS] four documents ConfigMap/Secret/Deployment/Service
[PASS] Deployment selector == Pod template labels
[PASS] Service selector == Pod template labels
[PASS] replicas == 3
[PASS] Service targetPort matches a container named port
[PASS] API container references ConfigMap
[PASS] API container references Secret
[PASS] logging sidecar does NOT reference the Secret

Static YAML validation: PASS
kubectl schema/admission validation: not completed (no Kubernetes API server)
Kubernetes runtime validation: not performed
```

No real credential, token, or verified image digest is committed; the Secret and image references
are placeholders (the images use the non-pullable `example.invalid` TLD with a mutable `:replace-...`
tag).

### Runtime Kubernetes validation (NOT run here)

A real `kubectl` client/schema or admission validation can only run after ALL of the following:

- a reachable Kubernetes API server (or a local cluster such as kind/minikube);
- CI-verified immutable image digests (`registry/name@sha256:...`) substituted for the non-pullable
  `example.invalid/...:replace-with-verified-digest` placeholders;
- real Secret values injected out of band (never committed);
- appropriate namespace, RBAC, and encryption-at-rest configuration for the Secret.

Only then would you run, in order:

```bash
kubectl apply --dry-run=client -f ai-backend-baseline.yaml   # client-side schema
kubectl apply --dry-run=server -f ai-backend-baseline.yaml   # API admission (needs a cluster)
```

Do not treat the commands above as already-passing here — they are what to run *after* the runtime
preconditions are met, not evidence of a run in this repository.

This environment has no reachable Kubernetes API server. The live class attempted `kubectl`
client/schema validation, but `kubectl` tried to fetch OpenAPI/API discovery from
`http://localhost:8080` with no API server available, so that check was **NOT completed**. No
`kubectl apply`, Pod scheduling, image pull, container startup, ConfigMap/Secret injection, Service
DNS/routing, Pod replacement, Secret rotation, business smoke test, or failure/rollback runtime
result is claimed. The manifest was reviewed statically only.

## Security boundaries

- `stringData` is plaintext in the manifest; Base64 in a Secret is encoding, not encryption.
- Real values must be injected out of band; a committed manifest with a real secret is unsafe.
- A Secret object is not automatically encrypted at rest or least-privileged — pair it with RBAC,
  namespace/workload isolation, selective references, audit, and rotation.
- Rotation needs a compatibility window and verified, controlled Pod replacement before revoking the
  old credential.

> Ingress, Autoscaling, Rolling Update, StatefulSet, and Helm are Day27 topics and are intentionally
> not part of this Day26 baseline.

---

# Day27 Kubernetes Workloads — `rag-platform/` Helm chart

`rag-platform/` is a **teaching-only** Helm chart that extends the Day26 baseline into production
workload patterns. It is **not production-ready and not deployable as-is**.

Lesson: `docs/devops/day27-kubernetes-workloads.md`

## Chart layout

```text
rag-platform/
├── Chart.yaml
├── values.yaml          # base values (every field is a Value; no real secrets)
├── values-dev.yaml      # dev overrides
├── values-prod.yaml     # prod overrides
├── validate_chart.py    # deterministic static checks (PyYAML only)
└── templates/
    ├── _helpers.tpl         # shared name/label helpers so selectors & targets agree
    ├── configmap.yaml       # non-sensitive runtime config
    ├── deployment.yaml      # stateless FastAPI, RollingUpdate (maxSurge 1 / maxUnavailable 0)
    ├── service.yaml         # stable L4 access to the API Pods
    ├── ingress.yaml         # networking.k8s.io/v1 Host/Path/TLS (references a TLS Secret)
    ├── hpa.yaml             # autoscaling/v2; scales the API Deployment on CPU (API-appropriate)
    ├── headless-service.yaml# clusterIP: None for StatefulSet identity
    └── statefulset.yaml      # PostgreSQL identity/storage ONLY (not HA)
```

## What this chart does and does NOT provide

- Deployment: Rolling Update `maxSurge: 1` / `maxUnavailable: 0`, `minReadySeconds`,
  `progressDeadlineSeconds`, `revisionHistoryLimit`, CPU/memory requests+limits. Readiness gates
  Service endpoints but **does not prove AI business correctness**. When the HPA is enabled the
  Deployment **omits `spec.replicas`** so a `helm upgrade` does not reset the HPA-managed count;
  when the HPA is disabled the Deployment renders `replicaCount`.
- HPA: `autoscaling/v2` with Values-driven `minReplicas`/`maxReplicas`, and it **owns the desired
  replica count** for the API Deployment. It scales the **stateless API** on CPU utilization (an
  API-appropriate signal that requires the CPU request, which is present) — **this chart does not
  install Metrics Server or any adapter**. Queue-backlog / backlog-per-worker scaling is the classroom
  conclusion for a **queue consumer**, and it must scale the **worker Deployment that actually
  consumes the queue** via an external/custom metrics adapter. There is no worker Deployment in this
  Day27 chart, so no queue-backlog metric is wired to the API HPA; the worker workload arrives with
  Day28.
- Ingress/Service: the Service gives stable access; the Ingress adds Host/Path/TLS. A matching
  **Ingress Controller, DNS, public load balancer, and real TLS Secret are external runtime
  prerequisites** that this chart does not create. The Ingress only routes to the Service it defines.
- StatefulSet: stable Pod identity + per-Pod PVCs (`volumeClaimTemplates`) + a headless Service. This
  is an **identity/storage teaching example, not PostgreSQL HA** — no WAL/streaming replication,
  leader election, failover, fencing, write routing, backup, or point-in-time recovery.
- Secrets: sensitive values are **referenced** via `existingSecret` (created out of band), never
  placed in any values file. Helm release history and rendered manifests can leak plaintext if teams
  misuse Values for credentials.
- Images use a **single complete reference** field (`image.reference`, `postgres.image.reference`) so a
  deploy-time swap to a digest form (`registry.example.com/rag-api@sha256:<digest>`) renders a valid
  reference. The default is the non-pullable `example.invalid` TLD with a **mutable**
  `:replace-with-verified-digest` tag — not verified, not immutable — and must be replaced with a
  CI-verified immutable digest.

## Validating the chart

Validation has layers, and only the first runs in this repository.

### Repository-level static validation (runs here)

`validate_chart.py` needs only PyYAML. From `examples/kubernetes/rag-platform/`:

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install pyyaml   # one-time (isolated)
python3 validate_chart.py
```

It parses `Chart.yaml` and every `values*.yaml`, and asserts the chart's structural invariants at the
template level: the Deployment selector, Pod template labels, and Service selector share one helper;
the HPA `scaleTargetRef` and Ingress backend use the same fullname helper as the Deployment/Service;
the StatefulSet and headless Service share the postgres helpers; API versions are correct
(`networking.k8s.io/v1`, `autoscaling/v2`, `apps/v1`); Rolling Update `maxSurge`/`maxUnavailable` are
Values-driven; the StatefulSet has `volumeClaimTemplates`; the headless Service is `clusterIP: None`;
CPU HPA has a matching CPU request; the Deployment guards `spec.replicas` with
`if not .Values.hpa.enabled` (so the HPA owns replicas); the API HPA carries no queue-backlog/External
worker metric; images use a single `.reference` field with the non-pullable placeholder; and sensitive
values are referenced (not inlined). Actual output produced here:

```text
Static chart validation (structure + values): PASS
helm lint/template: not run by this validation script
Kubernetes schema/admission validation: not run by this validation script
Kubernetes/Helm runtime validation: not performed
```

### Helm and runtime validation (NOT run here)

`helm` is not installed in this environment, so the commands below were **NOT run / NOT verified** and
no lint, render, schema, admission, or runtime result is claimed. When Helm and a cluster are
available, render both environments and confirm the invariants below:

```bash
helm lint ./examples/kubernetes/rag-platform

helm template rag-platform ./examples/kubernetes/rag-platform \
  -f ./examples/kubernetes/rag-platform/values-dev.yaml
helm template rag-platform ./examples/kubernetes/rag-platform \
  -f ./examples/kubernetes/rag-platform/values-prod.yaml

# With a reachable cluster (schema/admission):
helm template rag-platform ./examples/kubernetes/rag-platform -f .../values-prod.yaml \
  | kubectl apply --dry-run=server -f -
```

Confirm in the rendered output: with `hpa.enabled: true` the Deployment has **no** `spec.replicas`;
with `hpa.enabled: false` the Deployment includes `replicaCount`; both images accept a full
`repository@sha256:<digest>` reference; the HPA has **no** queue-backlog worker metric; the HPA
`scaleTargetRef` points at the API Deployment; the Ingress backend points at the real Service; and the
StatefulSet and headless Service names/selectors agree.

`helm lint` and `helm template` prove structure and rendering only. API dry-run proves schema/policy
acceptance. None of them prove scheduling, image pulls, Ingress/DNS/TLS routing, HPA scaling, PVC
provisioning, StatefulSet ordered lifecycle, PostgreSQL replication/failover, or business behavior —
those require a real cluster, dependencies, credentials, time, and observability.

> Day28 (future connection) assembles FastAPI, Celery, Redis, PostgreSQL, object storage, queues,
> monitoring, and observability into one production AI Backend architecture using these primitives.
