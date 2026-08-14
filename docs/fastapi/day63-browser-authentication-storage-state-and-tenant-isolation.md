# Day63 — Browser Authentication, Storage State and Tenant Isolation

## 1. Lesson Metadata

```text
Status:        ✅ Completed — lesson + Session-Gate decision core; EXECUTED_LOCAL_RUNTIME (pure logic + HTTP loopback)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 4-5 hours
Prerequisite:  Day62 per-task BrowserContext ownership; Day60 lease/fencing; Day61 durable-evidence rule
Previous Lesson: Day62 — Playwright Runtime, Locators and Reliable Async Interaction
Next Lesson:   Day64 — Dynamic Extraction, Network Events and Artifact Evidence
Engineering Artifact: projects/fastapi-playwright/ (pure Browser-Session authorization gate + controlled account page + tests)
```

Day63 turns Day62's per-task `BrowserContext` ownership into an AUTHENTICATED, tenant-bound,
revocable browser-session capability. A reusable browser is safe only when each task resolves an
approved session server-side, creates a fresh Context, verifies the actual authenticated identity,
and stays authorized all the way through result publication.

> Evidence honesty: the LIVE CLASSROOM session produced a `CONCEPTUAL_STATIC` artifact — no Day63
> source, tests, browser, PostgreSQL, credential store, queue, or production run was executed in
> class. The repository artifact added here is a PURE Session-Gate decision core plus a controlled
> loopback account page; the updating agent authored and ran its pure-logic + real HTTP-loopback +
> static-contract tests:
>
> ```
> cd projects/fastapi-playwright
> python3 -m pytest -q tests/test_day63_session_gate.py \
>   tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py
> ```
>
> Result: **28 passed, 1 skipped, `EXECUTED_LOCAL_RUNTIME`**. The 1 skipped item is the
> real-Chromium isolation module, gated on the `playwright` package (absent in the agent
> environment). **NOT RUN:** real Chromium `BrowserContext` state isolation / redirect-popup
> observation; real PostgreSQL `UPDATE ... RETURNING` atomic claim; real credential
> encryption/KMS/Object Storage; a real Worker; queue integration; and production. Day62's
> `13 passed, 1 skipped` is Day62-only evidence and is NOT reused as Day63 proof. This gate proves
> the authorization/claim CONTROL FLOW only — never that a real browser, database, or secret store
> behaved as described.

---

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain why `tenant_id` alone does not isolate browser Cookies/Local Storage/Pages/requests, and
  why the `BrowserContext` is the runtime isolation boundary while the Session is the server-side
  authorization capability.
* Design a `BrowserSession` binding: tenant/session/origin/owner, expected identity
  (`principal_id`/`organization_id`), a protected credential reference, and lifecycle + concurrency
  fields (status, expiry, revoked, version, `lease_owner`/`lease_token`/`lease_expires_at`).
* Order the safe Task authorization pipeline: validate binding → atomic claim → read credential →
  fresh Context → verify identity → allowed actions → final fence → publish → close in `finally`.
* Verify a POSITIVE stable identity fact instead of inferring success from the absence of a login
  redirect or a mutable display name.
* Classify `AUTHENTICATION_PRECONDITION_FAILED`, `AUTHORIZATION_SESSION_FAILURE`,
  `UNKNOWN_AUTHORIZATION_STATE`, and `SECURITY_FAILURE`, and explain why none becomes a business
  `no result` or a blind-retry license.
* Filter exported storage state to explicit Origin/Cookie-domain allowlists and treat cross-subdomain
  SSO as an audited exception.
* Defend the arbitrary-subdomain-allowlist rollback drill and distinguish `EXECUTED_LOCAL_RUNTIME`
  from `INTEGRATION_RUNTIME`.

---

## 3. Why This Matters

A Multi-tenant AI Research Platform reuses one Browser Worker across tenants. Tenant A already has an
authenticated target-site session; Tenant B's task arrives. If the Worker reuses A's live Context —
or "cleans it up" and reuses it — B's task can read A's Cookies, act as A's identity, and publish A's
data as B's result. That is a cross-tenant data breach that also poisons any downstream Agent that
consumes the result.

The failure modes are specific and expensive:

- **Tenant leakage**: a shared or wrongly-resolved Session leaks one tenant's authenticated state
  into another tenant's tool output.
- **Credential exposure**: putting `storage_state` in a Job payload, a queue message, a log, or a
  screenshot turns reusable authentication material into a breach waiting to happen.
- **False authorization**: "no login redirect" is read as "logged in as the right user", so the task
  acts under the wrong identity.
- **Stale authority**: a revoked or superseded session keeps publishing because nothing re-checks
  authorization at the moment of the critical action and final publication.

Day63 builds the server-side gate that makes the browser a *permissioned* tool: an approved Session,
a fresh Context, a verified identity, and continuing lease/fencing authority through publication.

---

## 4. Roadmap Position

```text
Day61 durable-evidence rule  +  Day60 ownership/lease/fencing  +  Day62 reliable BrowserContext lifecycle
        |
        v
Day63 authenticated, tenant-bound, revocable browser-session gate            <-- you are here
        |
        v
Day64 dynamic extraction, network/download evidence, Artifact persistence (from the right session)
        |
        v
Day65 recovery, diagnostics, credential/security, SSRF, website-policy, prompt-injection boundaries
        |
        v
Day66 durable queue-backed permissioned Playwright Worker
```

### Knowledge Continuity

```text
Previous Knowledge
  - Day62: Browser = reusable runtime; BrowserContext = per-task isolation; success = fact asserted AND cleanup
  - Day60: one authoritative owner; lease_owner/lease_token/lease_expires_at fencing
  - Day61: durable/observable facts (not impressions) decide what may be claimed
        |
        v
Current Lesson Concept
  - Tenant = business scope; BrowserContext = runtime isolation; Session = revocable authorization capability
  - atomic claim + fencing + positive identity verification + storage-state allowlists
        |
        v
Future Production Usage
  - Day64 persists only authorized-session extraction; Day65 recovers unknown external effects;
    Day66 runs this as a queue-backed permissioned tool on the Day50/Day60 Job lifecycle
```

Reused mental models (named): the **Day60 lease/fencing ownership** (one attempt owns continuing
authority), the **Day61 evidence rule** (observable facts, not impressions), and the **Day62
Context ownership + `finally` cleanup** discipline.

---

## 5. Lesson Map

```text
Job (trusted)  -> validate session/tenant/origin binding
  -> atomic claim (active + not revoked + not expired + lease available)  [authoritative concurrency check]
    -> ONLY winner reads protected credential reference
      -> fresh Task BrowserContext from filtered storage state
        -> verify POSITIVE identity fact at approved Origin
          -> allowed actions + fencing checks
            -> FINAL fence before publish
              -> publish only if still authorized
                -> close Context in finally (every path)
```

---

## 6. Core Mental Model

```text
Tenant         = business authorization / isolation scope
BrowserSession = explicit, tenant/owner/origin-bound, REVOCABLE authorization capability
storage_state  = reusable SENSITIVE auth material (NOT proof of identity)
BrowserContext = one task's runtime state / isolation container (never shared live)
Lease/Fencing  = short-lived, attempt-owned CONTINUING authorization

Task Success
= business fact asserted
AND BrowserContext cleanup completed          (a published result whose close() FAILED is INCOMPLETE, not success)
AND trusted Job -> exact approved Session binding
AND current authenticated principal/org matches expected identity
AND allowed Origin is maintained
AND the FINAL fence passes before critical actions and final publication, where the fence predicate is:
      session active AND session not expired
      AND lease_owner == this attempt_id AND lease_token == worker_token AND lease_expires_at > now
      AND session version == claimed version
```

The final fence must check the FULL lease, not just token/version: an OLD Attempt whose lease has
EXPIRED (or is now owned by a successor) can NEVER publish, even with a matching old token/version.

The one sentence to remember: **a Session authorizes; a Context isolates; a lease keeps you
authorized; and only a positive identity fact — verified in that Context and re-fenced at
publication — proves you may act.**

---
## 7. Main Concepts

### Concept 1: Tenant is the business scope; the BrowserContext is the isolation boundary

#### Tech Lead Question

Tenant B's task arrives while Tenant A holds an authenticated session on a reused Browser. Where does
the isolation boundary live?

#### Student Thinking

The student anchored on the business concept: tenants must be separated, so the boundary "should be
at the Tenant". That is the right *goal* but not yet the right *mechanism*.

#### Student Answer

> 租户边界应该放在 Tenant。

#### Tech Lead Review

Correct business goal, incomplete mechanism. `tenant_id` is a scope label; it does not isolate
browser Cookies, Local Storage, Pages, or in-flight requests. The runtime isolation boundary is the
`BrowserContext` — a fresh, per-task container. So the model is two-layer: Tenant is the business
authorization/isolation scope, and a server-authorized `BrowserSession` (bound to
tenant/owner/origin/expected identity) is resolved into a fresh `BrowserContext` per task. The class
explicitly rejected "share one live Context and clean it up" as a tenant-isolation strategy —
cleanup cannot prove that A's state never reached B.

#### Engineering Thinking

- Why it exists: isolation must be enforced by the runtime container, not by a business label or by
  best-effort cleanup.
- Alternatives: a shared live Context (leaks state, cannot be proven isolated) — rejected.
- Production risk controlled: cross-tenant data leakage.

#### Production Example

Day64 will create each Context per task from controlled tenant-bound storage state; a live shared
Context would leak A's Cookies into B's extraction.

#### Framework Connection

Playwright `browser.new_context()` per task; the Browser is reused, the Context is not.

---

### Concept 2: storage_state is protected credential material, not a file trick

#### Tech Lead Question

How should `storage_state` be managed, and where does it live?

#### Student Thinking

The student first reached for "put it in a special file", then recognized the real question is
protection, not format.

#### Student Answer

> 作为受保护的凭证材料管理。 (initially: storage_state should live in a special file.)

#### Tech Lead Review

The refined answer is right: `storage_state` is reusable SENSITIVE authentication material. Security
comes from protected, encrypted, audited credential management with least-privilege Worker access —
not from a file format. Persist a protected credential *reference* + metadata in PostgreSQL; store
the encrypted credential content in a protected credential/object/secret store. Never commit, log,
screenshot indiscriminately, put it in a Job payload, or pass the whole storage state in a queue
message — even encrypted. And filter exported Origins/Cookie domains to explicit allowlists — the DEFAULT Cookie-domain allowlist is the approved Origin's HOST (e.g. `https://research.example.test` → `research.example.test`), never the full Origin string, so a host-only Cookie survives while a `.example.test` cross-subdomain Cookie is rejected unless it is explicitly, auditably added.

#### Engineering Thinking

- Why it exists: reusable auth material is a credential; treat it like one.
- Alternatives: "encrypted file in the repo/queue" — still leaks the material into the wrong place.
- Production risk controlled: credential exfiltration through payloads/logs/artifacts.

#### Production Example

A Job payload carries `credential_ref="cred://ref/B1"`; the Worker with least privilege resolves and
decrypts it at execution — the queue message never contains the state.

#### Framework Connection

PostgreSQL/SQLAlchemy for the reference + metadata; a KMS/secret store for the encrypted content
(labeled boundaries — NOT implemented/executed in Day63).

---

### Concept 3: Session binding fields — business, credential, identity, lifecycle, concurrency

#### Tech Lead Question

Which fields does a `BrowserSession` need to be a real authorization capability?

#### Student Thinking

The student named the concurrency/lifecycle fields well but first omitted the credential reference
and the expected-identity binding.

#### Student Answer

> tenant_id / session_id / target_origin / owner (+ status / lease_token / lease expiry).

#### Tech Lead Review

Right core, but separate the concerns explicitly: **business binding** (tenant_id, session_id,
target_origin, owner); **credential reference** (protected pointer, never the material); **identity
binding** (expected principal_id and, when present, organization_id); **lifecycle/versioning**
(status, expiry, revoked, version); **concurrency** (`lease_owner=attempt_id`, `lease_token`,
`lease_expires_at`). A client-supplied `session_id` is only a candidate reference — the API must
authorize it before recording it on a Job, and the Worker must re-check and atomically claim it at
execution time.

#### Engineering Thinking

- Why it exists: authorization needs identity and lifecycle, not just a name and a lease.
- Alternatives: a bare (session_id, lease) — cannot detect identity mismatch or revocation.
- Production risk controlled: acting under the wrong or revoked identity.

#### Framework Connection

`SessionBinding` + `SessionMeta` in `day63_session_gate.py`.

---

### Concept 4: The atomic claim is the authoritative current-state check (ordering)

#### Tech Lead Question

Order the pipeline. A student proposed `2 -> 5 -> 4 -> 6 -> 3 -> 1 -> 7`.

#### Student Thinking

The student sequenced plausibly but put identity/context steps before the authoritative claim and
before credential loading.

#### Student Answer

> 2 -> 5 -> 4 -> 6 -> 3 -> 1 -> 7 (later corrected).

#### Tech Lead Review

Corrected order: **`5 -> 2 -> 6 -> 1 -> 4 -> 7 -> 3`**, with these principles — the ATOMIC CLAIM is
the authoritative current-state/concurrency check (not a one-time login check); credential loading
precedes Context creation; identity validation happens INSIDE the Context at the approved Origin; and
the FINAL fencing check follows the browser action, immediately before publication. In the artifact
this reads as: validate binding → atomic claim (`UPDATE ... RETURNING`) → only the winner reads the
credential → fresh Context → verify identity → allowed actions → final fence → publish → close in
`finally`. A claim that is not won reads NO credential and builds NO Context.

#### Engineering Thinking

- Why it exists: concurrency and revocation must be decided by one atomic DB write, not by reading
  then acting.
- Alternatives: check-then-act (a TOCTOU race two Attempts can both pass) — rejected.
- Production risk controlled: double execution and stale-authority publication.

#### Production Example

`classify_claim(...)` returns `CLAIMED` only for the winning `attempt_id`; a second Attempt gets
`LEASE_HELD` until the lease expires.

#### Framework Connection

PostgreSQL `UPDATE ... WHERE ... RETURNING` (planned integration — NOT executed in Day63).

---

### Concept 5: Verify a positive identity fact — a redirect's absence is not proof

#### Tech Lead Question

Does "no login redirect" prove the Context is authenticated as the right user? May any active session
for a tenant be chosen automatically?

#### Student Thinking

The student was initially unsure which page fact proves identity, then landed on the right rule.

#### Student Answer

> 不能 (no login redirect is not proof). 不能 (a tenant's session may not be auto-selected).
> 必须限制到批准的 target_origin (exported state).

#### Tech Lead Review

Exactly. Verify a POSITIVE stable identity fact — a `principal_id`/`organization_id` from an account
page or a protected `/me`-style endpoint — and compare it to the expected Session binding. Do not
infer success from the lack of a login redirect and do not compare only mutable display names.
Auto-selecting "some active session for the tenant" is forbidden; the Job binds an exact,
server-authorized `session_id`. And exported storage state must be restricted to the approved
`target_origin`.

#### Engineering Thinking

- Why it exists: authentication is a positive fact, not the absence of a failure signal.
- Alternatives: "no redirect ⇒ logged in" — a classic false-authorization bug.
- Production risk controlled: acting under an unverified/wrong identity.

#### Framework Connection

`verify_identity(observed, binding)` → `AUTHORIZATION_SESSION_FAILURE` on a missing/mismatched
principal.

---

### Concept 6: Four explicit outcomes; revocation, versioning, and the final fence

#### Tech Lead Question

Classify: identity mismatch; login redirect; a final fencing check that times out after revocation;
an observed unapproved-Origin navigation. When can a second Attempt seize a lease?

#### Student Thinking

The student mapped each signal to a distinct outcome and reasoned about lease seizure and revocation.

#### Student Answer

> 创建 Context 前检查会话的当前状态。 停止并报告会话前置条件失败 (Task Context redirected to login).
> 不能，使用 update set returning (claim/revocation race). attempt_id (lease_owner).
> 不能，应该等待 lease expire (before a second Attempt claims). 只写安全标识并把 Context 关闭
> (identity mismatch diagnostics). UNKNOWN_AUTHORIZATION_STATE (final fencing check times out).

#### Tech Lead Review

All correct. The four publication-blocking outcomes are: identity mismatch ⇒
`AUTHORIZATION_SESSION_FAILURE`; login redirect / inactive or expired session ⇒
`AUTHENTICATION_PRECONDITION_FAILED`; final lease/fencing check timeout ⇒
`UNKNOWN_AUTHORIZATION_STATE`; observed unapproved Origin navigation/popup ⇒ `SECURITY_FAILURE`.
Every non-AUTHORIZED outcome blocks business-result publication, and none becomes a business
`no result` or a blind-retry license. The FINAL fence authorizes publication only when the session is active and not expired AND `lease_owner == this attempt_id` AND `lease_token == worker_token` AND `lease_expires_at > now` AND `version == claimed version`; an expired lease or a lease now owned by a successor ⇒ `AUTHORIZATION_SESSION_FAILURE`, so an old Attempt can never publish on a stale/expired lease. On identity mismatch, write only a SAFE identifier and close
the Context (no raw identity in diagnostics). A second Attempt cannot seize a still-unexpired lease
just because the first looks unhealthy; after expiry it atomically claims a new token and the old
token loses authority at the next fence boundary. Revocation/version replacement prevents new claims
and makes old tokens fail future critical-action/final-publication checks — but it cannot un-send a
request already made (that is a Day65 recovery boundary).

#### Engineering Thinking

- Why it exists: distinct outcomes drive distinct, safe handling (Day65), not a generic retry.
- Alternatives: collapsing everything to "failed/retry" — loses the safety distinctions.
- Production risk controlled: unsafe retries, stale-authority publication, security incidents.

#### Framework Connection

`final_fence(...)` → `UNKNOWN_AUTHORIZATION_STATE` on timeout; `check_navigation(...)` →
`SECURITY_FAILURE`; the orchestrator blocks publication on every non-AUTHORIZED outcome.

---

### Concept 7: Which claims need a real browser vs pure control flow

#### Tech Lead Question

Which assertion requires real Playwright: "a revoked/expired Session cannot create a Context", or
"two Contexts do not share cookies"?

#### Student Thinking

The student first chose the revoked-session case as needing real Playwright.

#### Student Answer

> revoked / expired Session cannot create Context (initially chosen as needing real Playwright).

#### Tech Lead Review

Corrected: the revoked/expired-cannot-create-Context rule is a pure control-flow decision — a fake
Context factory plus the claim logic proves it (a rejected claim never calls the factory), which is
`EXECUTED_LOCAL_RUNTIME`. Real Playwright is necessary to prove `BrowserContext` STATE ISOLATION
(two Contexts don't share cookies) and redirect/popup EVENT/navigation OBSERVATION and no-auto-login
behavior. So: pure Session Store + fake Context factory ⇒ authorization/claim control flow
(`EXECUTED_LOCAL_RUNTIME`); real Chromium + controlled localhost page ⇒ isolation + redirect/popup
observation (`EXECUTED_LOCAL_RUNTIME` while the Session Store is fake); real PostgreSQL atomic claim
+ protected credential storage + Worker + real Playwright ⇒ `INTEGRATION_RUNTIME` only if actually
executed and evidence saved.

#### Engineering Thinking

- Why it exists: pick the cheapest tier that actually proves the claim; don't over-claim.
- Alternatives: calling a fake in-memory store "integration" — dishonest tiering (forbidden).
- Production risk controlled: fabricated evidence.

#### Framework Connection

The Day63 tests: `test_day63_session_gate.py` (pure) and `test_day63_playwright_isolation.py` (gated
real Chromium — NOT RUN here).

---
## 8. Common Misconceptions

**Tenant boundary isolates the browser**

❌ Putting the boundary "at the Tenant" isolates Cookies/Storage/Pages.
✅ `tenant_id` is a business scope; the `BrowserContext` is the runtime isolation boundary. A Session
must be server-authorized and bound to tenant/owner/origin/expected identity.

Why beginners think this: Tenant is the business isolation concept.
How to remember: Tenant authorizes; Context isolates.

**No login redirect means logged in as the right user**

❌ The page didn't redirect to login, so the identity is correct.
✅ Verify a POSITIVE stable `principal_id`/`organization_id` from an account/identity endpoint; the
absence of a redirect and a mutable display name are not proof.

Why beginners think this: a redirect is the visible failure, so its absence feels like success.
How to remember: prove identity with a fact, not with the lack of a failure.

**storage_state is safe if it's in a special file**

❌ Security is a file format/location choice.
✅ Security is protected, encrypted, audited credential management with least-privilege access. Job/
queue payloads must never carry credential material, even encrypted.

Why beginners think this: "a secure file" feels like the deliverable.
How to remember: it's a credential; store a reference, protect the material.

**Any active session for the tenant can be used**

❌ Pick any active session belonging to the tenant.
✅ The Job binds an exact server-authorized `session_id`; the Worker re-checks and atomically claims
it. A client-supplied `session_id` is only a candidate.

Why beginners think this: "same tenant" feels sufficient.
How to remember: bind the exact session, then claim it atomically.

**A second Attempt can seize a lease if the first looks unhealthy**

❌ The first Attempt seems stuck, so take its lease now.
✅ A still-unexpired lease may not be seized; wait for expiry, then atomically claim a new token. The
old token loses authority at the next fence boundary.

Why beginners think this: "unhealthy" feels like permission.
How to remember: only expiry frees a lease; fencing enforces it.

**Revocation reverses a request already sent**

❌ Revoking the Session undoes the external effect.
✅ Revocation prevents new claims and fails future critical-action/final checks; it cannot un-send a
request already made — that is a Day65 recovery/reconciliation boundary.

Why beginners think this: revocation feels total.
How to remember: revocation is forward-looking; external effects need recovery.

---

## 9. Engineering Trade-offs

**Fresh Context per task vs shared live Context + cleanup**

Fresh Context per task (chosen):
- Provable isolation; bounded blast radius; supports per-tenant storage state.
- Slightly more setup per task.

Shared live Context + cleanup:
- Cheap.
- Cannot prove A's state never reached B; couples failures — rejected for tenant isolation.

Tech Lead review: isolation must be structural (a fresh Context), not best-effort cleanup.

**Protected reference + secret store vs storage_state in payload/queue**

Reference + secret store (chosen):
- Credential material stays in a least-privilege, audited store; payloads carry only a pointer.
- Requires a real credential/KMS/object store (a labeled boundary here, not executed).

storage_state in the payload/queue:
- Simple to pass around.
- Leaks reusable auth material into logs/queues/artifacts — rejected.

**Atomic claim (`UPDATE ... RETURNING`) vs check-then-act**

Atomic claim (chosen):
- One authoritative write decides current state + concurrency; no TOCTOU race.
- Requires DB-level support at integration time.

Check-then-act:
- Easy to read.
- Two Attempts can both pass the check — rejected.

**Cross-subdomain SSO: default reject vs convenient allow**

Default reject (chosen): only explicit, audited allowlist entries permit a `.example.com` cookie;
everything else is dropped. Convenient allow (save whatever the site set) leaks scope across
subdomains — rejected. A Tech Lead reviews every allowlist exception as an auditable decision.

---

## 10. Hands-on Exercises

### Exercise 1: Why cleanup cannot prove isolation

Question: Argue why "share one live Context and clean it up between tasks" cannot prove cross-tenant
isolation.

Think First: what evidence would you need, and can cleanup provide it?

Expected Output: cleanup is best-effort and after-the-fact; it cannot prove A's Cookies/Storage never
influenced B. A fresh Context is structural proof.

Follow-up: what does Day64 need from Day63 before it extracts data?

### Exercise 2: Name the Session binding fields (reusable artifact)

Question: List the fields for a `BrowserSession`.

Think First: business, credential, identity, lifecycle, concurrency.

Starter Artifact: `src/day63_session_gate.py::SessionBinding` + `SessionMeta`.

Expected Output: tenant_id, session_id, target_origin, owner, expected principal/org, credential_ref,
status, expiry, revoked, version, lease_owner, lease_token, lease_expires_at.

Follow-up: which of these may a client supply, and which must the server authorize?

### Exercise 3: Order the pipeline (design judgment)

Question: A student proposed `2 -> 5 -> 4 -> 6 -> 3 -> 1 -> 7`. Give the correct order and the
principle behind each move.

Expected Output: `5 -> 2 -> 6 -> 1 -> 4 -> 7 -> 3`; atomic claim is the authoritative concurrency
check, credential loading precedes Context creation, identity validation happens in the Context, and
the final fence follows the browser action.

Follow-up: what must a non-winning claim NOT do?

### Exercise 4: Classify and gate (reusable artifact)

Question: For identity mismatch, login redirect, final-fence timeout, and unapproved navigation, give
the outcome and prove the negative effect.

Starter Artifact: `tests/test_day63_session_gate.py`.

Expected Output: `AUTHORIZATION_SESSION_FAILURE` (no business action / no publish),
`AUTHENTICATION_PRECONDITION_FAILED` (stop, no publish), `UNKNOWN_AUTHORIZATION_STATE` (no publish),
`SECURITY_FAILURE` (close Context, no publish); none becomes `no result` or a blind retry.

Follow-up: which of these needs real Playwright to prove, and which is pure control flow?

### Exercise 5: Arbitrary-subdomain rollback drill (production judgment)

Question: A release allowed Task Context navigation to arbitrary `*.example.com` Origins. What do
you do?

Expected Output: roll back the code/policy first and pause affected new Browser Task claims; preserve
version/time-window/session/attempt/job and approved-vs-actual-Origin audit facts; scope impact using
actual unapproved-Origin navigation evidence; selectively revoke only potentially exposed/unbounded
Sessions; mark affected results untrusted; add redirect/popup allowlist regression tests. Do NOT
delete every Session first, and do NOT claim rollback reverses an external request.

Follow-up: which later lesson owns the external-effect recovery?

---

## 11. Relevant Framework Connections

**Playwright** (primary): Browser reuse; one `BrowserContext` per task; `storage_state` export/import
with Origin/domain filtering; Page/redirect/popup lifecycle; `context.close()` in `finally`; no
auto-login in a Task Context. What to share: the Browser. What to isolate: the Context. Failure: an
unapproved navigation/popup ⇒ `SECURITY_FAILURE`. Review: identity verified with a positive fact; no
`force`-style shortcuts around authorization.

**PostgreSQL / SQLAlchemy Core** (planned artifact — NOT executed in Day63): server-side
`BrowserSession` metadata; tenant/owner/origin constraints; `UPDATE ... RETURNING` atomic claim;
attempt-owned lease, expiry, version/fencing checks. This is a labeled boundary — the Day63 gate
models the decision purely and does not call it executed.

**FastAPI / Celery Worker**: the API authorizes a candidate `session_id` before durable Job
acceptance; the Worker reauthorizes at execution; the Job payload carries a reference, never
credentials; Job/Attempt identity provides authority and audit linkage. This reuses the Day50/Day60
Job lifecycle (Day66 binds the gate to it).

Future connections (labeled, not implemented here): credential encryption/KMS/Object Storage (a
protected store), dynamic extraction + artifact persistence (Day64), and recovery/security/SSRF/
prompt-injection boundaries (Day65).

---
## 12. AI Backend Connections

The Browser Worker is a permissioned AI tool, and Day63 is its authorization gate:

- **Tool result integrity**: incorrect Session reuse leaks one tenant's authenticated data into
  another tenant's tool result, which then poisons downstream Agent reasoning and any data the Agent
  persists. A verified identity + fresh Context keeps the tool's output attributable to the right
  tenant.
- **Credentials never reach the model**: an LLM/Agent must not obtain raw browser credentials in
  prompts, tool arguments, logs, or queue messages. The Job carries a `credential_ref`; the Worker
  resolves it with least privilege; the model sees only authorized results.
- **Authority for publication**: a browser result may be published only with durable Job/Attempt
  authority PLUS browser-session fencing — not because a page rendered. This is the Day61 evidence
  rule applied to authenticated browsing.
- **Isolation as privacy**: per-task Contexts from tenant-bound storage state are the browser-side
  analogue of tenant isolation; login state, cookies, and tokens never cross tasks and are never
  committed.

Production implication: Day64 will persist only authorized-session extraction evidence, Day65 will
recover unknown external effects and harden diagnostics/security, and Day66 will run this gate as a
queue-backed permissioned tool. A tool that cannot prove *which authenticated identity* produced a
result is unsafe to feed an Agent.

---

## 13. English Interview

### Key Vocabulary

```text
Tenant scope · BrowserSession (revocable authorization capability) · storage_state (sensitive material)
BrowserContext isolation · atomic claim (UPDATE ... RETURNING) · lease_owner/lease_token/lease_expires_at
positive identity fact (principal_id/organization_id) · fencing/version check · final fence before publish
AUTHENTICATION_PRECONDITION_FAILED · AUTHORIZATION_SESSION_FAILURE · UNKNOWN_AUTHORIZATION_STATE · SECURITY_FAILURE
```

### Useful Expressions

- "Tenant authorizes; the BrowserContext isolates."
- "storage_state is a credential — store a protected reference, not the material."
- "Verify a positive identity fact; a missing redirect is not proof."
- "Every non-authorized outcome blocks publication and is never a blind retry."

### Beginner Question

Q: Why isn't `tenant_id` enough to isolate two tenants' browser tasks?

Strong Answer: "`tenant_id` is a business scope label; it doesn't isolate Cookies, Local Storage,
Pages, or in-flight requests. The runtime isolation boundary is a fresh `BrowserContext` per task,
resolved from a server-authorized Session that's bound to the tenant, owner, origin, and expected
identity. Sharing one live Context and cleaning it up can't prove one tenant's state never reached
the other."

### Intermediate Question

Q: A Task Context loads and there's no login redirect. Can you publish the result?

Strong Answer: "Not yet. The absence of a redirect isn't proof of the right identity. I verify a
positive, stable identity fact — a `principal_id`/`organization_id` from an account page or a
protected `/me` endpoint — against the expected Session binding, not a mutable display name. Then I
run a final lease/version fence right before publication and publish only if I'm still authorized. If
the identity doesn't match it's `AUTHORIZATION_SESSION_FAILURE`; if it redirected to login it's
`AUTHENTICATION_PRECONDITION_FAILED`; either way I don't publish and I don't blind-retry."

### Senior Question

Q: A release let Task Contexts navigate to arbitrary `*.example.com` Origins. Walk me through the
response.

Strong Answer: "Contain first: roll back the code/policy and pause affected new Browser Task claims —
don't let more tasks run under the vulnerable navigation. Preserve the audit facts:
version/time-window, session/attempt/job, and approved-vs-actual Origin. Scope impact from the actual
unapproved-Origin navigation evidence, then selectively revoke only the potentially exposed or
unbounded Sessions — not every Session as a reflex. Mark affected results untrusted, and add
redirect/popup allowlist regression tests so the boundary can't silently widen again. I wouldn't
claim the rollback reverses any request already sent — un-sending external effects is a Day65
recovery/reconciliation problem."

### Common Weak Answer

"There was no login redirect and the page showed the account, so it's the right user and I published
the result." This infers identity from the absence of a failure and a mutable display, skips the
positive-fact verification and the final fence, and ignores tenant/session binding.

### Strong Answer (summary)

"Task success = business fact asserted AND Context cleanup completed AND the trusted Job maps to the
exact approved Session AND the authenticated principal/org matches the expected identity AND the
approved Origin held AND lease/version fencing passed before the critical action and final
publication."

---

## 14. Mental Model Summary

```text
Tenant           = business authorization / isolation scope
BrowserSession   = revocable authorization capability (tenant/owner/origin/identity-bound)
storage_state    = sensitive credential material (reference in DB, encrypted content in a secret store)
BrowserContext   = per-task runtime isolation (fresh; never shared live)
atomic claim     = UPDATE ... RETURNING (authoritative current-state + concurrency)
lease/fencing    = attempt-owned continuing authority (lease_owner/lease_token/lease_expires_at, version)
identity proof   = positive principal_id/organization_id (not "no redirect", not a display name)
outcomes         = AUTHENTICATION_PRECONDITION_FAILED | AUTHORIZATION_SESSION_FAILURE
                   | UNKNOWN_AUTHORIZATION_STATE | SECURITY_FAILURE  (all block publication; never blind retry)
task success     = fact asserted AND cleanup done AND exact Session AND matching identity
                   AND approved Origin AND FULL fence (owner+token+lease-not-expired+version) before publish
task completion  = SUCCESS (published + cleaned up) | INCOMPLETE (published but close() failed) | FAILED
login persist    = ACTIVATED (state saved + metadata committed) | ORPHAN_INACTIVE (state saved, metadata failed)
                   | PERSIST_CONSISTENCY_FAILED (state NOT saved — never an orphan) | REJECTED_NOT_VERIFIED
```

---

## 15. Today's Takeaway

- **Most important mental model**: Tenant authorizes, the `BrowserContext` isolates, a lease keeps you
  authorized, and only a verified positive identity fact re-fenced at publication lets you act.
- **Most important production risk**: cross-tenant leakage / false authorization from reusing or
  wrongly resolving a session.
- **Most important trade-off**: a fresh per-task Context + protected credential reference over a
  shared live Context or storage-state-in-payload.
- **Most important framework connection**: Playwright Context isolation + `storage_state` filtering,
  backed by a server-side atomic claim and fencing.
- **Most important AI Backend connection**: a permissioned browser tool must prove *which* identity
  produced a result before an Agent consumes it.
- **Most important interview answer**: "A missing login redirect is not proof; verify a positive
  identity fact and re-fence before publishing."

---

## 16. Before Next Lesson Checklist

- [ ] I can explain why `tenant_id` doesn't isolate the browser and the `BrowserContext` does.
- [ ] I can list the Session binding fields (business, credential, identity, lifecycle, concurrency).
- [ ] I can order the pipeline: binding → atomic claim → credential → Context → identity → actions →
      final fence → publish → close.
- [ ] I can name the positive identity fact and why a missing redirect isn't proof.
- [ ] I can classify the four outcomes and explain why none is `no result` or a blind retry.
- [ ] I can filter storage state to Origin/Cookie-domain allowlists and treat cross-subdomain SSO as
      an audited exception.
- [ ] I can defend the arbitrary-subdomain rollback drill.
- [ ] I can distinguish `EXECUTED_LOCAL_RUNTIME` (pure gate + fake Context) from `INTEGRATION_RUNTIME`
      (real PostgreSQL/credential store/Playwright).
- [ ] I can run the artifact: `python3 -m pytest -q tests/test_day63_session_gate.py tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py` (= 28 passed, 1 skipped; the real-Chromium suite is gated on `playwright`).

---

Related: [Day63 design/runbook](../../projects/fastapi-playwright/docs/day63-browser-authentication-storage-state-and-tenant-isolation-design.md) ·
[session gate](../../projects/fastapi-playwright/src/day63_session_gate.py) ·
[controlled account page](../../projects/fastapi-playwright/src/day63_controlled_login_page.py) ·
[gate tests](../../projects/fastapi-playwright/tests/test_day63_session_gate.py) ·
[cheat sheet](../../cheat_sheets/fastapi.md) ·
[interview](../../interview/fastapi.md) ·
Previous: [Day62 lesson](day62-playwright-runtime-locators-and-reliable-async-interaction.md)
