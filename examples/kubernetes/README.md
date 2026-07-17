# examples/kubernetes

Day26 Kubernetes Foundations example: one RAG/FastAPI service declared as four core objects — a
ConfigMap, a Secret template, a three-replica Deployment (FastAPI + logging sidecar Pod template),
and a Service.

**Example / template only.** These are teaching manifests. They are **not deployable as-is** and no
Kubernetes runtime success is claimed. `stringData` values are plaintext placeholders, and image
fields are `REPLACE_*` placeholders supplied out of band. **Never** commit a real API key, password,
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

Checks that need no cluster, credentials, or images:

- the file parses as four YAML documents with kinds ConfigMap, Secret, Deployment, Service;
- the Deployment selector (`spec.selector.matchLabels`) equals the Pod template labels
  (`spec.template.metadata.labels`);
- the Service selector equals the Pod template labels;
- `spec.replicas == 3`;
- no real credential, token, or verified image digest is committed (values are placeholders).

A local YAML parser plus explicit relationship assertions were used for exactly these checks. Example:

```bash
python3 - <<'PY'
import yaml
docs = {d["kind"]: d for d in yaml.safe_load_all(open("ai-backend-baseline.yaml"))}
dep, svc = docs["Deployment"], docs["Service"]
tmpl = dep["spec"]["template"]["metadata"]["labels"]
assert dep["spec"]["selector"]["matchLabels"] == tmpl
assert svc["spec"]["selector"] == tmpl
assert dep["spec"]["replicas"] == 3
print("static checks: PASS")
PY
```

### Runtime Kubernetes validation (NOT run here)

A real `kubectl` client/schema or admission validation can only run after ALL of the following:

- a reachable Kubernetes API server (or a local cluster such as kind/minikube);
- verified image digests substituted for the `REPLACE_*` placeholders;
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
