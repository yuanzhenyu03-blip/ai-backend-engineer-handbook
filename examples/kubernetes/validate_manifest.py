#!/usr/bin/env python3
"""Static validation for examples/kubernetes/ai-backend-baseline.yaml (Day26).

Repository-level static checks only. This does NOT contact a cluster and makes NO claim about
kubectl schema, API admission, or Kubernetes runtime behavior.

Dependency: PyYAML. Install in an isolated way if it is not already present, e.g.:

    python3 -m venv .venv && . .venv/bin/activate && pip install pyyaml
    # or, if you accept a user-site install:
    python3 -m pip install --user pyyaml

Run from this directory (examples/kubernetes/):

    python3 validate_manifest.py
"""
from __future__ import annotations

import sys

try:
    import yaml
except ModuleNotFoundError:
    sys.exit(
        "PyYAML is required. Install it first, e.g. `python3 -m pip install --user pyyaml` "
        "(see the module docstring for an isolated venv option)."
    )

MANIFEST = "ai-backend-baseline.yaml"


def main() -> int:
    with open(MANIFEST, encoding="utf-8") as fh:
        docs = list(yaml.safe_load_all(fh))

    by_kind = {d["kind"]: d for d in docs}
    checks: list[tuple[str, bool]] = []

    # 1. four documents with the expected kinds
    checks.append(("four documents ConfigMap/Secret/Deployment/Service",
                   set(by_kind) == {"ConfigMap", "Secret", "Deployment", "Service"}
                   and len(docs) == 4))

    dep = by_kind.get("Deployment", {})
    svc = by_kind.get("Service", {})
    tmpl = dep.get("spec", {}).get("template", {}).get("metadata", {}).get("labels")
    containers = dep.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])

    # 2. Deployment selector == Pod template labels
    checks.append(("Deployment selector == Pod template labels",
                   dep.get("spec", {}).get("selector", {}).get("matchLabels") == tmpl and tmpl is not None))

    # 3. Service selector == Pod template labels
    checks.append(("Service selector == Pod template labels",
                   svc.get("spec", {}).get("selector") == tmpl and tmpl is not None))

    # 4. replicas == 3
    checks.append(("replicas == 3", dep.get("spec", {}).get("replicas") == 3))

    # 5. Service targetPort matches a container's named port
    named_ports = {p.get("name") for c in containers for p in c.get("ports", [])}
    svc_target_ports = {p.get("targetPort") for p in svc.get("spec", {}).get("ports", [])}
    checks.append(("Service targetPort matches a container named port",
                   bool(svc_target_ports) and svc_target_ports <= named_ports))

    # 6. API container references ConfigMap and Secret
    api = next((c for c in containers if c.get("name") == "api"), {})
    api_uses_configmap = any("configMapRef" in e for e in api.get("envFrom", []))
    api_uses_secret = any(
        "secretKeyRef" in (e.get("valueFrom") or {}) for e in api.get("env", [])
    )
    checks.append(("API container references ConfigMap", api_uses_configmap))
    checks.append(("API container references Secret", api_uses_secret))

    # 7. Sidecar does NOT reference the Secret
    side = next((c for c in containers if c.get("name") == "log-sidecar"), {})
    side_uses_secret = any(
        "secretKeyRef" in (e.get("valueFrom") or {}) for e in side.get("env", [])
    ) or any("secretRef" in e for e in side.get("envFrom", []))
    checks.append(("logging sidecar does NOT reference the Secret", not side_uses_secret))

    ok = True
    for name, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    print("\nStatic YAML validation:", "PASS" if ok else "FAIL")
    print("kubectl schema/admission validation: not completed (no Kubernetes API server)")
    print("Kubernetes runtime validation: not performed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
