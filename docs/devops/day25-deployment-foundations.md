# Lesson 25 — Deployment Foundations

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 6-7 hours

Prerequisite: Day24 — Docker Compose

Previous Lesson: Day24 — Docker Compose

Next Lesson: Day26 — Kubernetes Foundations

Engineering Artifact: A production request-path architecture (Client -> DNS -> Nginx -> FastAPI), an example Nginx reverse-proxy/TLS configuration, and a zero-downtime deployment + rollback runbook.

Estimated Study Time:

```text
Reading: 130-160 minutes
Exercises: 80-110 minutes
Hands-on Nginx / runbook authoring: 80-110 minutes
Review: 30-45 minutes

Total: 6-7 hours
```

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Explain the stable public entry (Domain -> DNS -> Nginx :443 -> Backend) and why the backend port stays internal.
* Configure an Nginx reverse proxy: `listen`, `server_name`, `proxy_pass`, and trusted proxy headers.
* Explain TLS as confidentiality + integrity + server authentication, and where it terminates.
* Redirect HTTP to HTTPS (308) and explain why redirect cannot protect an already-sent credential.
* Explain the certificate lifecycle and Nginx master/worker processes (`reload` vs `restart`).
* Promote one CI-verified immutable image digest instead of rebuilding per environment.
* Perform an API blue-green switch with verify, observe, drain, and rollback.
* Apply Expand-Migrate-Contract to a PostgreSQL schema change and roll out a worker compatibly.
* Serialize production deployment with a concurrency lock and a least-privilege short-lived identity.
* Configure AI streaming (buffering off, correct timeouts) and reason about DNS TTL propagation.
* Answer beginner, intermediate, and senior deployment interview questions in English.

The engineering artifact is an Nginx configuration and a deployment runbook, not application code.

---

# Why This Matters

Day24 declared a reproducible multi-service system on one Docker host. But a Compose stack that
starts correctly is not yet a safe, publicly reachable, zero-downtime production service.

Day25's central equation:

```text
Built Artifact != Running Container != Reachable Production Service

Successful Deployment
= Verified Artifact Identity
+ Controlled Production State Transition
+ Real-traffic Observation
+ Drain
+ Rollback Capability
+ Audit Record
```

Why a backend engineer must care:

```text
Reachability -> a stable public entry (Domain/DNS/Nginx) instead of a raw app port.
Security     -> TLS identity + termination, trusted proxy context, least-privilege deploy identity.
Availability -> blue-green switch, drain, and rollback keep the service up during change.
Correctness  -> Expand-Migrate-Contract and compatible worker rollout preserve data/job contracts.
Roadmap      -> Day26-27 Kubernetes formalizes these ideas as continuous desired-state control.
```

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day22-24)
        |
        v
Current Concept (Day25: promote the verified artifact and move production traffic safely)
        |
        v
Future Production Usage (Day26-27 Kubernetes; Day28 Production AI Backend)
```

Where Day25 sits:

```text
Git / GitHub -> CI/CD -> GitHub Actions quality gates -> immutable Docker image
-> Docker Compose service model -> Deployment Foundations (Day25)
-> Kubernetes control & workloads (Day26-27) -> Production AI Backend (Day28)
```

Direct prerequisites reused:

```text
Day22 -> CI builds, tests, scans, and verifies ONE immutable image identity.
Day23 -> Image is an immutable artifact; container is a replaceable runtime instance.
Day24 -> Image + service specification produces the multi-service runtime; started != ready.
Day25 -> Promote the same verified artifact and safely move production traffic to it.
```

Future connection only: Kubernetes (Day26-27) turns manual blue-green/drain/rollback into
continuous desired-state reconciliation. Do not teach Day26/27 YAML here.

---

# Lesson Map

```text
Stable public entry (DNS -> Nginx :443 -> backend)
  -> Nginx reverse proxy (listen/server_name/proxy_pass)
  -> TLS (confidentiality + integrity + server authentication)
  -> HTTP->HTTPS 308 (and why it can't protect a sent credential)
  -> Certificate lifecycle + Nginx master/worker (reload vs restart)
  -> Trusted proxy context (X-Forwarded-*; header != identity)
  -> Build once, promote the exact digest (tag vs digest)
  -> API blue-green + real zero-downtime (verify/switch/observe/drain/rollback)
  -> Drain, long AI requests, idempotent retry
  -> PostgreSQL Expand-Migrate-Contract
  -> Worker rollout (compatible consumer first)
  -> Serialized deploy + least-privilege short-lived identity
  -> Integrated runbook + rollback
  -> AI streaming (buffering vs caching; timeouts)
  -> DNS TTL is not atomic
```

---

# Core Mental Model

```text
Source Commit
-> CI quality gates -> build/test/scan ONE immutable image digest -> push to registry
-> production approval -> acquire production concurrency lock -> inspect actual state
-> pull the exact verified digest

If shared data contracts change:  PostgreSQL Expand -> compatible code -> backfill/migrate
                                  -> Contract only after the rollback window (later release).
If worker contracts change:       compatible consumer first -> observe queue/worker
                                  -> new producer -> drain old worker/payload.
API:  start Green (no prod traffic) -> readiness+smoke -> nginx -t -> graceful switch
      -> observe real traffic + drain Blue -> switch back on failure
      -> end rollback window and remove Blue on success.
Always: bounded timeout + failure handler + least-privilege short-lived identity
        + monitoring + actual-state inspection + deploy/rollback record
        -> release the lock only in a known final state.
```

The most durable sentence:

```text
Deployment is not copying code or restarting a container. It is a serialized, observable,
reversible production state transition that promotes the exact verified artifact while preserving
request, job, data, and rollback compatibility.
```

The request path:

```text
Client -> api.example.com -> DNS -> Public IP -> Nginx :443 -> api:8000 (FastAPI)
```

---

# Main Concepts

## Concept 1: Stable Public Entry vs Replaceable Backend

### Tech Lead Question

The Day24 stack runs FastAPI on port 8000. What is missing to make it a real public service?

### Student Answer

> "第一个没有进行域名映射，让域名与IP进行绑定。第二没有隐藏端口。"

(Missing: domain-to-IP mapping, and "hiding" the port.)

### Tech Lead Review

The domain instinct is right; reframe the port point (Instruction 6):

```text
The goal is not to hide port 8000.
The goal is to NOT expose the backend port to the public Internet.

DNS           = where the public entry is.
Port 443      = which public service accepts the connection.
Reverse Proxy = which internal backend receives the request.
FastAPI       = which business operation runs.
```

Stable path:

```text
Client -> api.example.com -> DNS -> Public IP -> Nginx :443 -> api:8000
```

Changing FastAPI v1 to v2 must not change the client's domain or URL. The public contract stays
stable; Nginx changes the backend target.

### Engineering Thinking

A reverse proxy decouples the public contract (domain/URL/TLS) from the replaceable backend.

### Framework Connection

The Day24 `api` service stays internal; only Nginx is published.

## Concept 2: Nginx Reverse Proxy Mental Model

### Tech Lead Question

Write the minimal Nginx block that proxies `api.example.com` to the FastAPI container.

### Student Answer

First attempt reversed the roles:

```nginx
listen 8000;
server_name api;
proxy_pass http://api.example.com;
```

### Tech Lead Review

Corrected model:

```text
listen       = where Nginx receives public traffic
server_name  = which public Host/Domain matches the server block
proxy_pass   = which internal service handles the request
```

```nginx
server {
    listen 80;
    server_name api.example.com;
    location / {
        proxy_pass http://api:8000;
    }
}
```

The student correctly reused Day24: `localhost` inside the Nginx container is the Nginx container
itself, not FastAPI. Cross-container traffic uses Docker service DNS (`api:8000`).

### Framework Connection

`proxy_pass http://api:8000;` reaches the FastAPI service by its Compose DNS name.

## Concept 3: TLS Is More Than Encryption

### Tech Lead Question

Why is HTTPS more than "encrypting the bytes"?

### Student Answer

Initially: HTTP leaks customer data; TLS provides encrypted transmission. (Student also said
"一致性" where "integrity" was meant.)

### Tech Lead Review

Expand the model (Instruction 5):

```text
TLS = Confidentiality + Integrity + Server Authentication
```

A valid certificate for `admin.example.com` must be rejected for `api.example.com`: encryption
without correct domain identity is not enough. Clients validate the certificate SAN, trust chain,
validity period, and signature. In this topology TLS terminates at Nginx:

```text
Client --HTTPS--> Nginx --internal HTTP--> FastAPI
```

This protects only client-to-Nginx. Cross-host or untrusted internal networks may need TLS/mTLS as
a separate control. A reverse proxy does not automatically provide TLS; it can terminate TLS when
configured.

## Concept 4: HTTP-to-HTTPS Redirect and the Bearer Token Misconception

### Tech Lead Question

Should port 80 keep serving business traffic, reject users, or redirect? And does redirect protect
a token sent over HTTP?

### Student Answer

Correctly chose to redirect (for UX + security), but twice tied token lifetime / initial
authorization to future transport protection.

### Tech Lead Review

Use a 308 for an API so method and body are preserved:

```nginx
return 308 https://$host$request_uri;
```

Durable correction (Instruction 7):

```text
Authentication/Authorization = whether a token is valid and what it may do.
TLS                          = protection for each individual transmission.
Secure issuance does not guarantee secure later use.
Long-lived Token != More Secure; it is a longer abuse window after leakage.
```

A bearer token sent in the first HTTP request is already exposed before Nginx can return 308.
Clients must use HTTPS from the start; redirect is compatibility guidance, not retroactive
protection. HSTS reduces downgrade exposure but does not replace correct client configuration.

## Concept 5: Certificate Lifecycle and Nginx Master/Worker

### Tech Lead Question

What happens when a certificate expires, and how do you update Nginx after renewing it?

### Student Answer

Chose automated renewal; initially thought an expired certificate makes traffic "become
plaintext."

### Tech Lead Review

An expired certificate does not turn ciphertext into plaintext; it invalidates server identity, so
compliant clients reject the connection and production becomes unavailable.

```text
Prove domain control -> issue -> store cert + private key securely -> monitor expiration
-> renew before expiration -> validate files/config -> nginx -t -> graceful reload
-> verify the served certificate externally -> alert on failure
```

Process distinctions the student asked about:

```text
Nginx Master Process = reads config/certs, receives signals, manages workers.
Nginx Worker Process = handles network connections and proxy work.
AI Backend Worker    = consumes background jobs (a different meaning of "worker").

Start   = create the first running generation.
Reload  = the existing master loads new config and gracefully replaces workers.
Restart = stop, then start again.
```

Updating certificate files on disk does not update Nginx memory: prefer `nginx -t && nginx -s
reload` over restarting the container for a normal certificate/config update.

## Concept 6: Trusted Proxy Context

### Tech Lead Question

FastAPI sees the Nginx container IP and an internal HTTP connection. Does it need any extra
request context?

### Student Answer

Correctly explained FastAPI sees Nginx, but initially concluded FastAPI needs no metadata because
it "should only do business logic."

### Tech Lead Review

Good separation instinct; correct the conclusion:

```text
FastAPI does not proxy, but it may need trusted original request context for audit logs, URL
generation, OAuth callbacks, rate limits, and security investigation.
```

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

Security boundary:

```text
Proxy header = request metadata, NOT identity proof.
Trusted proxy + normalized header policy + backend network isolation + real authn/authz
= defensible request context.
```

The student correctly diagnosed a forged `X-Forwarded-For: 127.0.0.1` trusted by an admin route as
an access-control bypass that can start a larger attack chain. The root cause is not only one
missing Nginx line: header normalization, trusted-proxy config, backend isolation, and real auth
are all required.

## Concept 7: Build Once, Promote the Exact Artifact

### Tech Lead Question

On deploy, do you rebuild the image on the production host or pull the CI-verified one?

### Student Answer

Chose to pull the CI-verified image because another build may produce different content. (Said
"quantity gate"; the term is **quality gate**.)

### Tech Lead Review

```text
Tested Artifact = Scanned Artifact = Deployed Artifact
```

Runtime environment differences belong in the Day24 service specification/configuration, not in a
per-environment image rebuild.

```text
Rebuild = create a NEW artifact (needs new verification and a new digest if done by CI).
Promote = move the SAME already-verified artifact to the next environment.

Image Tag          = movable, human-readable reference.
Image Digest       = immutable artifact identity.
Container Registry = artifact storage/distribution service.
Container          = runtime instance created from the artifact.
```

The student decomposed `ghcr.io/acme/rag-app:v2.4.0` into registry, repository, and tag, and
identified the digest as the missing immutable identity.

## Concept 8: API Blue-Green and Real Zero-downtime Conditions

### Tech Lead Question

To deploy v2 with zero downtime, do you stop v1 first?

### Student Answer

Correctly chose: keep v1 serving -> start v2 separately -> verify v2 -> switch traffic.

### Tech Lead Review

```text
Start Green -> verify Green DIRECTLY (not through the public URL still serving Blue)
-> validate Nginx config -> switch new traffic -> observe Green under real traffic
-> drain Blue in-flight requests -> roll back or complete -> remove Blue only after the rollback window
```

Two containers can both listen on container port 8000 (separate network namespaces); Nginx targets
`api_v1:8000` and `api_v2:8000` without publishing both host ports. Health/readiness before traffic
is necessary but not sufficient (Instruction 8): real traffic can reveal business errors, latency,
AI model failures, streaming defects, and data-specific failures.

## Concept 9: Drain, Long AI Requests, and Recoverability

### Tech Lead Question

Can you remove v1 the instant you switch traffic?

### Student Answer

Correctly said immediate removal can interrupt streaming, and that Observe + Drain were missing;
chose a finite drain timeout.

### Tech Lead Review

```text
Traffic switch = change the target for NEW requests.
Drain          = let old-target in-flight requests finish.
Observe        = decide whether the new target is stable.
```

Nginx graceful reload cannot preserve an upstream request after the deployment script forcibly
deletes the old FastAPI container (Instruction 9). A timed-out request cannot always be
transparently restarted (Instruction 10):

```text
Stateless Container != Stateless Business Operation
```

Safe retry needs idempotency, a job ID, durable state/checkpoints, or explicit client retry. Blind
retry may duplicate email, orders, database writes, model cost, or tool side effects.

## Concept 10: PostgreSQL Expand-Migrate-Contract

### Tech Lead Question

Rename column `prompt` -> `user_prompt` during a deploy. Can you just drain old requests first?

### Student Answer

First reused the drain model. Then correctly ordered the safe steps: `B, C, D, E, A`.

### Tech Lead Review

v1 can stay running yet fail because its shared schema contract was destroyed, and a destructive
schema change also destroys rollback compatibility (Instructions 11-12).

```text
B. Add user_prompt
C. Deploy code compatible with BOTH
D. Backfill
E. Confirm old versions are gone and the rollback window ended
A. Remove prompt in a LATER release
```

```text
Expand -> compatible code -> backfill/migrate -> verify -> end rollback window -> Contract later
```

Schema operations also need lock/load/large-transaction review. API, worker, scripts, and rollback
targets must all stop depending on the old field before Contract. Distinguish shared durable state
from replaceable compute.

## Concept 11: Worker Rollout Is Not Nginx Traffic Switching

### Tech Lead Question

Can you blue-green the worker the same way you did the API?

### Student Answer

Correctly said no; first described the risk as "job competition causing confused results."

### Tech Lead Review

```text
Competing consumers are a NORMAL scaling model.
The deployment risk is that a job may be handled nondeterministically by v1 OR v2, so payload,
schema, side effects, retry, ACK/lease, and delivery semantics must be compatible.
Duplicate execution comes from at-least-once delivery/retry/failure, not merely from two workers,
and needs idempotency protection (Instruction 13).
```

Compatible rollout (student chose consumer-first):

```text
Deploy Worker v2 that accepts old + new payloads -> observe worker/queue health
-> deploy API v2 producer -> drain old format/worker -> remove old compatibility later
```

Worker health = job success, retry, queue lag, processing latency, dead-letter count, duplicate
side effects, database failures, and model cost/errors — not only a running process.

## Concept 12: Serialized Deployment, Failure Handling, and Identity

### Tech Lead Question

Two production deploys overlap. Cancel the running one?

### Student Answer

Forgot the mechanism name but correctly chose to wait for a known state over blind cancellation
("因为可以回滚可以追溯").

### Tech Lead Review

```yaml
concurrency:
  group: production
  cancel-in-progress: false
```

```text
Approval    = authorization gate.
Concurrency = serialization/lock for shared production mutation.
```

Cancelling a production deployment differs from cancelling obsolete CI: it may be mid-migration,
mid-switch, or mid-drain, and must end in a known successful or known rolled-back state. For a stuck
deploy: add timeout and actual-state inspection.

```text
Timeout -> freeze destructive actions -> inspect Nginx/containers/digest/migration
-> complete forward or roll back -> verify -> record -> release lock
```

Least-privilege short-lived deployment identity beats a long-lived root SSH key:

```text
Secret storage       = how a credential is protected before use.
Least privilege      = what it may do.
Short lifetime       = how long stolen power is useful.
Environment approval = when it may be released.
Audit                = who used it and why.
```

Registry pull identity, host deployment identity, database migration identity, and Nginx admin
capability should not be combined by default — combining them enlarges blast radius from image pull
to direct production mutation.

## Concept 13: Integrated Deployment Runbook and Rollback

### Tech Lead Question

Order the full deployment. (The student placed the lock too late and Observe before the switch.)

### Tech Lead Review

Corrected order:

```text
Verified digest -> approval -> acquire lock -> inspect actual production state
-> pull exact digest -> start Green without production traffic -> verify Green directly
-> prepare Nginx config -> nginx -t -> graceful traffic switch -> verify public path
-> observe Green + drain Blue -> roll back or finish rollback window -> remove Blue
-> record final state -> release lock
```

Pre-switch health/smoke verification and post-switch real-traffic observation are separate. For a
20% post-switch error rate, restore traffic before deleting v2:

```text
Freeze destructive actions -> keep Blue alive -> restore Nginx target to Blue -> nginx -t
-> graceful reload -> verify public recovery -> stop new v2 work -> drain/terminate v2 safely
-> preserve evidence -> record rollback -> release lock after state is known
```

Record `in_progress` and state transitions, not only the final result.

## Concept 14: AI Streaming — Buffering vs Caching and Timeouts

### Tech Lead Question

Nginx holds streamed response data. Is that caching, and how do you tune it?

### Student Answer

Noticed Nginx held response data but called it caching and proposed a cache-time setting. Also
believed `proxy_read_timeout 60s` would survive 90s of upstream silence because
`proxy_send_timeout` was unset.

### Tech Lead Review

```text
Buffering = holds chunks within the CURRENT response before forwarding.
Caching   = stores a response for reuse by LATER requests.
```

```nginx
location /chat {
    proxy_pass http://api_v2:8000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

The four timeouts (Instruction 16):

```text
proxy_connect_timeout = connect to upstream
proxy_send_timeout    = inactivity while WRITING request to upstream
proxy_read_timeout    = inactivity between READS from upstream response
send_timeout          = inactivity while writing response to client
```

The student then correctly explained that a valid heartbeat every 30s resets a 60s upstream
inactivity window. Heartbeat does not replace a bounded total job timeout, client-disconnect
handling, cancellation, concurrency limits, or durable async job design. Do not disable buffering
for every endpoint: ordinary REST optimizes throughput; AI streaming optimizes time-to-first-token.

## Concept 15: DNS TTL Is Not an Atomic Traffic Switch

### Tech Lead Question

You change a DNS record. Do all users switch at once?

### Student Answer

Correctly said not all users switch immediately, but first phrased TTL as a global counter that
must exhaust before DNS "executes" the change.

### Tech Lead Review

```text
Authoritative DNS may return the new value immediately.
Each resolver/client keeps its own cached old answer until ITS OWN remaining TTL expires.
```

So some clients reach Server A while others reach Server B (Instruction 17). Lower TTL at least one
old-TTL period before migration, wait for old high-TTL caches, keep A/B available during
propagation, observe both, and remove A only after the migration window. DNS rollback is also
gradual. The student correctly rejected lowering a 24h TTL five minutes before migration and then
closing Server A.

```text
DNS   = coarse host/location discovery and migration.
Nginx = precise backend traffic switching on the selected host.
```

---

# Common Misconceptions

## Mental Model Evolution (Day24 -> Day25)

```text
Initial: "A Compose stack that starts is basically deployed."
Reasoning: Day24 made the multi-service stack start correctly.
Correction: Starting != publicly reachable, secure, observable, reversible.
Final: Deployment is a serialized, observable, reversible production state transition that
       promotes the exact verified artifact while preserving request/job/data/rollback compatibility.
```

## Misconception list

```text
Port "hiding"
❌ Security means hiding port 8000.
✅ Do not expose the backend port publicly; the public entry is DNS + Nginx :443.
```

```text
Reverse proxy roles
❌ `listen` = backend target; `proxy_pass` = the public domain.
✅ `listen`/`server_name` = public side; `proxy_pass` = internal service (api:8000).
```

```text
TLS scope
❌ TLS just encrypts bytes.
✅ TLS = confidentiality + integrity + server authentication; a wrong-domain cert is rejected.
```

```text
Redirect protects credentials
❌ A 308 redirect protects a token sent over HTTP.
✅ The first HTTP request is already exposed; redirect is compatibility, not retroactive protection.
```

```text
Certificate expiry
❌ An expired cert makes traffic plaintext.
✅ It invalidates server identity; compliant clients reject the connection -> outage.
```

```text
Proxy headers
❌ `X-Forwarded-For` proves the client identity.
✅ Headers are request metadata; trust needs a trusted proxy + normalization + isolation + real auth.
```

```text
Rebuild on deploy
❌ Rebuild the image per environment.
✅ Promote the exact verified digest; runtime differences live in the service specification.
```

```text
Health = success
❌ A passing health check proves the deployment succeeded.
✅ Pre-switch health is necessary but not sufficient; real traffic reveals business/AI failures.
```

```text
Drain / retry
❌ Any timed-out AI request can transparently restart in a new container.
✅ Stateless container != stateless operation; safe retry needs idempotency/job-id/checkpoints.
```

```text
Schema change
❌ Drain old requests, then rename the column.
✅ Expand-Migrate-Contract; a destructive change breaks running v1 and rollback compatibility.
```

```text
Worker blue-green
❌ Two workers inherently duplicate every job; copy the API blue-green.
✅ Competing consumers are normal; roll out a compatible consumer first; duplicates come from delivery/retry.
```

```text
Buffering vs caching
❌ Nginx holding stream chunks is caching; set a cache time.
✅ Buffering holds chunks of the current response; caching reuses a response; disable buffering for /chat.
```

```text
DNS TTL
❌ TTL is a global counter that must exhaust before DNS switches.
✅ Each resolver caches until its own TTL expires; the switch is gradual, not atomic.
```

---

# Engineering Trade-offs

```text
Direct FastAPI exposure vs one Nginx public entry.
TLS termination on one host vs internal TLS/mTLS across trust boundaries.
HTTP redirect usability vs the first HTTP request already being unprotected.
Automatic certificate renewal vs automation/permission/monitoring complexity.
Proxy context usefulness vs header-spoofing and trust-chain risk.
Tags for readability vs digests for immutable identity.
Blue-green rollback speed vs temporary double resource use.
Long drain windows for AI requests vs CPU/memory/GPU cost and release speed.
Retry convenience vs duplicate side effects; idempotency/checkpoint complexity.
Expand-Contract availability/rollback vs temporary schema/code complexity.
Compatible worker overlap vs deterministic versioned-queue isolation.
Serialized deployment safety vs waiting/blocked emergency releases.
Short-lived least-privilege identity vs setup and operational complexity.
Nginx buffering throughput vs AI streaming latency.
Long proxy timeout vs resource exhaustion; heartbeat vs total task timeout.
Low DNS TTL migration speed vs query load; high TTL resilience vs slow rollback.
```

---

# Hands-on Exercises

The engineering artifacts are an Nginx config and a deployment runbook (see
`examples/deployment/`).

## Exercise 1: Correct the Reverse Proxy

Question: fix the reversed block (`listen 8000; server_name api; proxy_pass http://api.example.com;`).

Expected Output:

```nginx
server {
    listen 80;
    server_name api.example.com;
    location / {
        proxy_pass http://api:8000;
    }
}
```

Follow-up Question: why does `localhost` inside the Nginx container not reach FastAPI?

## Exercise 2: HTTP -> HTTPS and the Token Question

Question: redirect HTTP to HTTPS for an API, and explain whether it protects a token already sent
over HTTP.

Expected Output: `return 308 https://$host$request_uri;`. Redirect does not protect the already-sent
token; the client must use HTTPS from the start.

Follow-up Question: does a longer-lived token make leakage safer?

## Exercise 3: Trusted Proxy Headers

Question: forward original request context to FastAPI and explain the trust boundary.

Expected Output: set `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`; a header is
metadata, not identity — needs trusted proxy + normalization + isolation + real auth.

Follow-up Question: why is a trusted `X-Forwarded-For: 127.0.0.1` on an admin route dangerous?

## Exercise 4: Promote a Digest

Question: decompose `ghcr.io/acme/rag-app:v2.4.0` and add the missing immutable identity.

Expected Output: registry `ghcr.io`, repository `acme/rag-app`, tag `v2.4.0`; add the digest
`@sha256:<digest>` (immutable identity). Promote, do not rebuild.

Follow-up Question: what belongs in the service specification instead of a rebuild?

## Exercise 5: Blue-Green + Drain

Question: order the API deployment for zero downtime.

Expected Output: start Green (no traffic) -> verify directly -> `nginx -t` -> switch -> observe +
drain Blue -> roll back or finish -> remove Blue after the rollback window.

Follow-up Question: why is a passing health check not proof of success?

## Exercise 6: Expand-Migrate-Contract

Question: order the rename `prompt -> user_prompt`.

Expected Output: `B, C, D, E, A` (Expand -> compatible code -> backfill -> verify/end window ->
Contract later).

Follow-up Question: why can running v1 fail even though its container is healthy?

## Exercise 7: Streaming Timeouts

Question: configure `/chat` for AI streaming and match each timeout to its role.

Expected Output: `proxy_buffering off; proxy_cache off; proxy_read_timeout 300s;
proxy_send_timeout 300s;`; connect/send/read/`send_timeout` map to connect/write-request/read-
response/write-response inactivity.

Follow-up Question: does a 30s heartbeat remove the need for a total job timeout?

## Exercise 8: DNS Migration

Question: migrate from Server A to Server B via DNS with a 24h TTL.

Expected Output: lower TTL at least one old-TTL period ahead, keep A/B during propagation, observe
both, remove A only after the window. Do not lower TTL 5 minutes before and close A.

Follow-up Question: what is DNS for vs what is Nginx for?

---

# Relevant Framework Connections

Only technologies genuinely used are connected (no forced Playwright).

## Nginx

```text
The public entry: listen/server_name/proxy_pass, TLS termination, 308 redirect, trusted proxy
headers, graceful reload, blue-green upstream switching, and a streaming location.
```

## FastAPI

```text
The internal backend behind Nginx: reached by service DNS (api:8000), needs trusted request
context, and is deployed as replaceable Green/Blue compute.
```

## Docker / Compose

```text
api_v1/api_v2 containers share container port 8000 via separate namespaces; the same verified image
digest is promoted; runtime differences live in the service specification.
```

## GitHub Actions

```text
CI builds/tests/scans and verifies one immutable digest; production deployment is serialized with
`concurrency: { group: production, cancel-in-progress: false }` and gated by approval.
```

## PostgreSQL

```text
Shared durable contract evolved with Expand-Migrate-Contract, not blue-green.
```

## Kubernetes (future connection only)

```text
Day26-27 turn manual blue-green/drain/rollback into continuous desired-state reconciliation. Not taught here.
```

---

# AI Backend Connections

```text
AI streaming (/chat) needs buffering off and larger read/send timeouts for time-to-first-token.
Long model requests need bounded total timeouts, heartbeats, client-disconnect handling, and
cancellation — not an unbounded proxy wait.
Blind retry of an AI job can duplicate model cost and tool side effects; safe retry needs
idempotency, a job ID, or checkpoints.
Worker rollout for AI jobs must keep payload/side-effect/delivery semantics compatible; worker
health includes model cost/errors, queue lag, and dead-letter count.
Deploy the exact evaluated image digest; runtime model/routing config lives in the service spec.
Least-privilege short-lived deploy identity limits blast radius for a production AI service.
```

---

# English Interview

## Beginner

Question: What does a reverse proxy do for a production API?

Student's actual attempt (preserved):

> "there are some problem is resolved by reverse proxy, for example, it offer a public entry for
> client, the interna backend only offer bussiness service. and the TLS is the more safer connect
> style than http, it's easy to swtich backend replacement"

Strong answer:

> A reverse proxy provides a stable public entry, keeps the backends internal, can terminate TLS,
> and forwards requests to the right backend service. Because the client talks to the proxy's
> domain and URL, the backend can be replaced without changing the client's contract.

## Intermediate

Question: Walk through a zero-downtime API deployment.

Correction preserved: say "switch traffic back to Blue," not "rollback the old container," and
stress that limited health signals differ from real production behavior.

Strong answer:

> I promote the approved image digest, start Green without production traffic, verify it directly
> with readiness and smoke checks, validate the Nginx config with `nginx -t`, then gracefully switch
> traffic. I observe Green under real traffic while draining Blue's in-flight requests. If the error
> rate is bad, I switch traffic back to Blue and drain v2 safely; if it is healthy, I end the
> rollback window and remove Blue. Health checks are necessary but not sufficient.

## Senior

Question: How do API, worker, and PostgreSQL differ during a deployment?

Correction preserved: PostgreSQL does NOT follow the same blue-green steps.

Strong answer:

> API and worker are replaceable compute versions: I blue-green the API and roll out a
> backward-compatible worker consumer first. PostgreSQL schema is a shared durable contract, so I use
> Expand-Migrate-Contract — add the new column, deploy code compatible with both, backfill, verify,
> and only contract in a later release after the rollback window. Everything runs under a serialized
> production lock with a least-privilege short-lived identity, bounded timeouts, observation, and a
> recorded rollback path.

```text
API/Worker = replaceable compute versions.
PostgreSQL Schema = shared durable contract using Expand-Migrate-Contract.
```

---

# Mental Model Summary

```text
Built Artifact != Running Container != Reachable Production Service
DNS = coarse host/location discovery; Nginx = precise backend switching
TLS = confidentiality + integrity + server authentication
Redirect != retroactive credential protection
Certificate expiry = invalid identity (outage), not plaintext
Proxy header = metadata, not identity
Tag = movable reference; Digest = immutable identity; Promote != rebuild
Blue-Green: start -> verify -> switch -> observe -> drain -> roll back / complete
Stateless container != stateless operation; safe retry needs idempotency
PostgreSQL = Expand-Migrate-Contract (shared durable contract)
Worker = compatible consumer first (competing consumers are normal)
Concurrency = serialized production mutation; least-privilege short-lived identity
Buffering != caching; heartbeat != total job timeout
DNS TTL expires per resolver; the switch is gradual, not atomic
```

---

# Today's Takeaway

Deployment turns one CI-verified immutable image into a safely reachable, observable, reversible
production service.

* Most important mental model: Built Artifact != Running Container != Reachable Production Service.
* Most important production risk: switching traffic (or a schema) without observation, drain, and a
  rollback path — or rebuilding instead of promoting the verified digest.
* Most important trade-off: blue-green rollback speed vs temporary double resources; serialized
  safety vs blocked emergency releases.
* Most important framework connection: Nginx is the stable public entry; FastAPI stays internal by
  service DNS.
* Most important AI backend connection: streaming needs buffering off + bounded timeouts; retries
  must be idempotent.
* Most important interview answer: API/worker are replaceable compute; PostgreSQL schema is a shared
  contract evolved with Expand-Migrate-Contract.

The most important engineering sentence:

```text
Deployment is a serialized, observable, reversible production state transition that promotes the
exact verified artifact while preserving request, job, data, and rollback compatibility.
```

---

# Before Next Lesson Checklist

Before Day26 (Kubernetes Foundations), confirm you can answer these without looking at the notes:

- [ ] Why does the backend port stay internal, and what is the stable public path?
- [ ] What do `listen`, `server_name`, and `proxy_pass` mean?
- [ ] What are the three properties of TLS, and where does it terminate here?
- [ ] Why can a 308 redirect not protect a token already sent over HTTP?
- [ ] What does an expired certificate actually break, and how do you reload Nginx safely?
- [ ] Why is a proxy header metadata, not identity?
- [ ] Why promote the exact digest instead of rebuilding per environment?
- [ ] Can you order a blue-green deploy with verify, switch, observe, drain, and rollback?
- [ ] Why is Expand-Migrate-Contract used for PostgreSQL instead of blue-green?
- [ ] Why is DNS TTL not an atomic switch?
