# examples/deployment

Day25 Deployment Foundations examples: a production request path plus a zero-downtime deployment
and rollback runbook.

**Example / template only.** This handbook repo has no deployable application, domain, or
certificate, so these artifacts are teaching templates. `example.com` is a reserved example domain;
certificate paths are placeholders. **Never** commit a certificate, private key, API key, SSH key,
password, registry token, domain credential, customer prompt, or business/medical data.

Lesson: `docs/devops/day25-deployment-foundations.md`

## Files

- `nginx/nginx.conf.example` — reverse proxy + TLS termination, HTTP->HTTPS 308 redirect, trusted
  proxy headers, a blue-green upstream target (`api_v2:8000`), and an AI streaming location.

## Request path

```text
Client -> api.example.com -> DNS -> Public IP -> Nginx :443 -> api:8000 (FastAPI)
```

The public contract (domain/URL/TLS) is stable; Nginx changes the internal backend target. The
backend port is never published to the public Internet.

## Validating the Nginx config

If a real Nginx binary/container is available:

```bash
nginx -t -c /absolute/path/to/nginx.conf.example    # syntax check only
```

If Nginx is not available, do not claim `nginx -t` succeeded. In this environment it was not run.

## Zero-downtime deployment runbook (blue-green)

```text
Verified digest
-> production approval
-> acquire production concurrency lock (cancel-in-progress: false)
-> inspect actual production state
-> pull the exact verified image digest
-> start Green (api_v2) WITHOUT production traffic
-> verify Green directly (readiness + smoke), not through the public URL still serving Blue
-> prepare the Nginx config (proxy_pass -> api_v2:8000)
-> nginx -t
-> graceful traffic switch (nginx -s reload)
-> verify the public path
-> observe Green under real traffic + drain Blue in-flight requests
-> roll back OR finish the rollback window
-> remove Blue only after the rollback window
-> record the final state
-> release the lock (only in a known final state)
```

Pre-switch health/smoke verification and post-switch real-traffic observation are separate. A
passing health check is necessary but not sufficient.

## Rollback (e.g. a 20% post-switch error rate)

```text
Freeze destructive actions
-> keep Blue alive
-> restore the Nginx target to Blue
-> nginx -t
-> graceful reload
-> verify public recovery
-> stop new v2 work
-> drain/terminate v2 safely
-> preserve evidence
-> record the rollback
-> release the lock after the state is known
```

## Data and worker contracts (do NOT copy the API blue-green blindly)

```text
PostgreSQL schema (shared durable contract): Expand -> compatible code -> backfill/migrate
-> verify -> end rollback window -> Contract in a LATER release.

Worker (competing consumers are normal): deploy a compatible consumer first -> observe queue/worker
-> deploy the new producer -> drain the old format/worker -> remove compatibility later.
```

## Identity

Use a least-privilege, short-lived, environment-scoped deployment identity — not a long-lived root
SSH key. Registry pull, host deployment, database migration, and Nginx administration should not be
combined by default (combining them enlarges blast radius).

> Continuous desired-state reconciliation, replica control, and cluster recovery are **not** part of
> this single-host deployment; they arrive in Day26–Day27 (Kubernetes).
