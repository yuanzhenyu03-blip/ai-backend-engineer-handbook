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
  proxy headers, a blue-green upstream target (`api_v2:8000`), and an AI streaming location. It is a
  `server`-block **fragment** meant to be included inside an Nginx `http {}` context (e.g. dropped
  into `/etc/nginx/conf.d/`), not a standalone main configuration.

## Request path

```text
Client -> api.example.com -> DNS -> Public IP -> Nginx :443 -> api:8000 (FastAPI)
```

The public contract (domain/URL/TLS) is stable; Nginx changes the internal backend target. The
backend port is never published to the public Internet.

## Validating the Nginx config

`nginx.conf.example` is a `server`-block fragment to be included inside an Nginx `http {}` context.
It has no `events {}` / `http {}` main context, so it **cannot** be passed to `nginx -c` directly
(`nginx -t -c nginx.conf.example` fails with `"server" directive is not allowed here`). Validation
happens at two levels, and only the first can run inside this repository.

### Repository-level static validation (runs here)

Checks that do not need Nginx, certificates, or a live upstream:

- the file is a `server`-block fragment (no `events {}` / `http {}` main context);
- every `proxy_pass` sits inside a `location` context;
- the fragment is never passed directly to `nginx -c`;
- no real certificate, private key, or secret is committed (paths are placeholders).

### Runtime Nginx validation (NOT run here)

A real `nginx -t` can only succeed after ALL of the following are in place:

- a complete Nginx main configuration providing `events {}` and `http {}`;
- this fragment included inside that `http {}` (e.g. copied to `/etc/nginx/conf.d/api.conf`);
- readable test certificate and private-key files at the `ssl_certificate` /
  `ssl_certificate_key` paths (or the paths edited to point at test certs);
- `api_v2` resolvable on the test network (or an explicit test substitute upstream);
- an Nginx binary or a working Docker daemon available.

Once those runtime preconditions are all satisfied, the final syntax check is simply:

```bash
nginx -t
```

Do not treat the command above as already-passing in this repository — it is the command to run
*after* the preconditions are met, not evidence of a successful run here.

This environment has no local Nginx. The Docker CLI is installed, but the Docker daemon is
unavailable. Required certificate files and a resolvable `api_v2` test upstream are also
unavailable, so `nginx -t` was not run and no successful runtime validation is claimed. The
fragment was reviewed statically only.

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
