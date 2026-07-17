#!/usr/bin/env python3
"""Deterministic static checks for the Day27 rag-platform Helm chart.

This does NOT run Helm or contact a cluster. It validates the non-template files as YAML and asserts
the chart's structural invariants at the template-text level (selectors/targets agree because every
template uses the same shared helper). It makes NO claim about `helm lint`, `helm template`,
Kubernetes schema/admission, or runtime behavior.

Dependency: PyYAML. Isolated install if needed:
    python3 -m venv .venv && . .venv/bin/activate && pip install pyyaml

Run from this directory (examples/kubernetes/rag-platform/):
    python3 validate_chart.py
"""
from __future__ import annotations
import os
import re
import sys

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("PyYAML is required. e.g. `python3 -m pip install --user pyyaml`.")

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates")


def read(*parts: str) -> str:
    with open(os.path.join(HERE, *parts), encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    checks: list[tuple[str, bool]] = []

    # 1. Non-template YAML parses
    values = {}
    yaml_ok = True
    for f in ("Chart.yaml", "values.yaml", "values-dev.yaml", "values-prod.yaml"):
        try:
            data = yaml.safe_load(read(f))
            if f == "values.yaml":
                values = data
        except Exception as exc:  # noqa: BLE001
            yaml_ok = False
            print(f"  YAML parse error in {f}: {exc}")
    checks.append(("Chart.yaml and all values files parse as YAML", yaml_ok))

    dep = read("templates", "deployment.yaml")
    svc = read("templates", "service.yaml")
    ing = read("templates", "ingress.yaml")
    hpa = read("templates", "hpa.yaml")
    sts = read("templates", "statefulset.yaml")
    hsvc = read("templates", "headless-service.yaml")

    sel = 'include "rag-platform.selectorLabels"'
    full = 'include "rag-platform.fullname"'
    psel = 'include "rag-platform.postgres.selectorLabels"'
    pfull = 'include "rag-platform.postgres.fullname"'

    # 2. Selectors/labels/targets agree by construction (shared helpers)
    checks.append(("Deployment selector and Pod template use the shared selector helper",
                   dep.count(sel) >= 2))
    checks.append(("Service selector uses the same selector helper as the Deployment",
                   sel in svc))
    checks.append(("HPA scaleTargetRef name and Deployment name use the same fullname helper",
                   full in hpa and full in dep))
    checks.append(("Ingress backend Service name uses the same fullname helper (no dangling route)",
                   full in ing))
    checks.append(("StatefulSet + headless Service share the postgres selector/fullname helpers",
                   psel in sts and psel in hsvc and pfull in sts and pfull in hsvc))

    # 3. Correct API versions
    checks.append(("Ingress uses networking.k8s.io/v1", "networking.k8s.io/v1" in ing))
    checks.append(("HPA uses autoscaling/v2", "autoscaling/v2" in hpa))
    checks.append(("Deployment/StatefulSet use apps/v1",
                   "apps/v1" in dep and "apps/v1" in sts))

    # 4. Rolling Update strategy present and Values-driven
    checks.append(("Deployment RollingUpdate uses maxSurge/maxUnavailable from Values",
                   "type: RollingUpdate" in dep
                   and ".Values.rollingUpdate.maxSurge" in dep
                   and ".Values.rollingUpdate.maxUnavailable" in dep))

    # 5. StatefulSet stable storage + headless
    checks.append(("StatefulSet declares volumeClaimTemplates",
                   "volumeClaimTemplates" in sts))
    checks.append(("Headless Service sets clusterIP: None", "clusterIP: None" in hsvc))

    # 6. CPU HPA consistency: if CPU metric can render, CPU requests exist
    cpu_metric = bool(values.get("hpa", {}).get("cpu", {}).get("enabled"))
    cpu_request = bool(values.get("resources", {}).get("requests", {}).get("cpu"))
    checks.append(("CPU HPA has a matching CPU request defined", (not cpu_metric) or cpu_request))

    # 7. Secret safety: sensitive values referenced, never inlined
    secret_ref_only = (
        isinstance(values.get("existingSecret"), str)
        and "secretKeyRef" in dep
        and ".Values.existingSecret" in dep
    )
    checks.append(("Sensitive values are referenced via existingSecret, not inlined", secret_ref_only))

    # No obvious secret literals in any values file. `existingSecret` is a reference (a Secret
    # NAME, not a credential) and is intentionally allowed.
    reference_keys = {"existingSecret", "tlsSecretName"}
    secretish = re.compile(r"(?i)^\s*([A-Za-z0-9_]*(?:api[_-]?key|password|token))\s*:\s*[\"']?([A-Za-z0-9/+=_-]{12,})")
    leaks = []
    for f in ("values.yaml", "values-dev.yaml", "values-prod.yaml"):
        for line in read(f).splitlines():
            m = secretish.match(line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            if key in reference_keys or "replace" in val.lower():
                continue
            leaks.append((f, line.strip()))
    checks.append(("No secret-looking literals in any values file", not leaks))

    # 8. Images use the non-pullable example.invalid placeholder
    img_ok = (values.get("image", {}).get("repository", "").startswith("example.invalid/")
              and values.get("postgres", {}).get("image", {}).get("repository", "").startswith("example.invalid/"))
    checks.append(("Images use non-pullable example.invalid placeholders", img_ok))

    ok = True
    for name, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    if leaks:
        for f, val in leaks:
            print(f"  possible secret literal in {f}: {val}")

    print("\nStatic chart validation (structure + values):", "PASS" if ok else "FAIL")
    print("helm lint: not run (helm not installed in this environment)")
    print("helm template: not run (helm not installed in this environment)")
    print("Kubernetes schema/admission validation: not performed (no API server)")
    print("Kubernetes/Helm runtime validation: not performed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
