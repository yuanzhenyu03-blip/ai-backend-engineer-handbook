# Day51 — Authentication, Password Security and JWT

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day50 — Idempotent AI Job API and Transactional Outbox Integration
Previous Lesson: Day50 — Idempotent AI Job API and Transactional Outbox Integration
Next Lesson: Day52 — Authorization, Tenant Isolation, Quotas and API Security
Engineering Artifact: projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md
  + runnable day51_authentication_jwt.py + test_day51_authentication_jwt.py (real Argon2id + real RS256 JWT; 34 passed)
```

Main engineering artifact: a provider-neutral authentication control-flow model using **real** Argon2id and **real**
RS256 JWT with ephemeral keys, plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Explain** why a password database stores an adaptive hash only, and why login uses the library `verify`.
- **Decide** what may never go inside a signed JWT payload, and why a normal JWT is readable.
- **Implement** a full JWT verification contract (pin algorithm, trusted key by `kid`, signature + iss + aud + exp +
  nbf + required `sub`) rather than a decode.
- **Design** asymmetric signing-key authority and a K1->K2 rotation, plus emergency revocation of a compromised key.
- **Compare** a stateless short Access Token with a revocable per-device Refresh Session.
- **Apply** a guarded atomic refresh rotation, its all-or-nothing rollback, and a bounded grace/replay state machine.
- **Diagnose** the browser cookie/CSRF boundary and reject a cookie-only cross-site refresh lacking valid
  Origin/CSRF evidence.
- **Separate** authentication (a trusted `user_id`) from Day52 authorization (what that user may do).
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Day50 made AI Job acceptance reliable and idempotent — but it never established **who** the caller is; its
`tenant_id` argument is still untrusted client input. Before Day52 can decide what a user may do, the API needs a
**trusted caller identity**. Getting authentication wrong is catastrophic: storing plaintext (or reversible)
passwords turns one database leak into account takeover everywhere; putting secrets in a JWT payload leaks them
because a normal JWT is readable; a decode-instead-of-verify accepts forged or expired tokens; a symmetric
verification key lets every verifier mint tokens; and a refresh flow without guarded rotation either locks users out
on a lost response or lets a stolen token replay forever. This lesson builds the identity foundation — secure
password verification, signed short-lived JWT access, and revocable per-device refresh sessions — that Day52
authorization sits on top of.

---

## 4. Roadmap Position

```text
Day49 verified Documents (safe input facts)
        |
        v
Day50 idempotent Job acceptance + transactional Outbox (one logical Job accepted reliably)
        |
        v
Day51 authentication: trusted user identity behind API requests   <-- you are here
        |
        v
Day52 authorization + tenant isolation + quotas (what that user may do)
        |
        v
Day53 real Provider  ->  Day55 real Celery/broker delivery + recovery
```

### Knowledge Continuity

```text
Previous Knowledge
  Day47 short UoW + guarded transition; Day50 DB-as-arbiter, rollback on partial persistence, retain evidence
        |
        v
Current Lesson Concept
  password hash/verify; readable-but-signed JWT + full verification; asymmetric keys + rotation;
  revocable per-device Refresh Session; guarded rotation + grace/replay; browser/CSRF boundary
        |
        v
Future Production Usage
  Day52 maps the verified user_id to tenant membership/authorization/quota (a client tenant_id is not authority);
  Day53 puts the real Provider behind this authenticated/authorized path; Day55 runs long work via Celery
```

Day51 authenticates who the caller is; it does not implement Day52 authorization, a real Provider (Day53), or Celery
(Day55). A normal signed JWT is readable unless JWE is deliberately designed — JWE is out of scope here.

---

## 5. Lesson Map

```text
Password hash (adaptive, one-way) -> library verify -> generic failure + needs_rehash
  -> JWT is readable + signed -> minimal non-secret claims
  -> full verification contract (alg pin, trusted key by kid, sig+iss+aud+exp+nbf+sub)
  -> asymmetric authority (private sign / public verify) -> K1->K2 rotation + emergency revoke
  -> Access (stateless, short) vs Refresh (revocable, per-device, hash-stored)
  -> guarded atomic rotation -> rollback -> bounded grace vs replay -> family revoke (retain evidence)
  -> browser: HttpOnly/Secure/SameSite cookie + Origin + CSRF (HttpOnly != CSRF defense)
  -> authentication (trusted user_id) vs Day52 authorization (tenant/permissions/quota)
```

---

## 6. Core Mental Model

```text
Password hash    = one-way password verification evidence (slow adaptive Argon2id; NEVER plaintext/reversible)
Signed JWT       = short-lived, READABLE-but-tamper-evident authenticated identity credential (integrity, not secrecy)
Refresh Session  = server-owned, revocable, PER-DEVICE continuation state (store the hash, not the raw token)
Authentication   = establish a trusted user_id (verified `sub`)   Authorization = Day52 decides what the user may do
```

---

## 7. Main Concepts

### Concept 1: Store a password hash, never the password

**Tech Lead Question:** What should the database store for a user password, and why?

**Student Answer:** "系统应该在数据库中保存密码，不能保存明文密码".

**Tech Lead Review:** Right direction, and let's make it precise. Store an **adaptive password hash only** — a
dedicated slow scheme such as Argon2id with library-managed salt and a configurable work factor. Never plaintext and
never reversibly encrypted. Do not use a fast general hash like SHA-256 for passwords: it is far too cheap to brute
force. The hash is one-way verification evidence, not a recoverable secret.

**Engineering Thinking:** A password store must survive being leaked; slow adaptive hashing makes offline cracking
expensive.

**Production Example:** A dump of Argon2id hashes is dramatically harder to crack than SHA-256, buying time to force
resets.

**Framework Connection:** `PasswordService.hash_password` (real Argon2id) — the stored value starts with
`$argon2id$` and encodes algorithm/salt/cost. `PasswordService()` defaults to argon2-cffi's SECURE production cost
(`time_cost=3`, `memory_cost=65536` KiB, `parallelism=4`), tuned per deployment hardware; tests inject a low-cost
hasher explicitly, and `needs_rehash` upgrades any hash made under an older, weaker policy on the next login.

---

### Concept 2: Verify with the library, and fail generically

**Tech Lead Question:** How does login check the password?

**Student Answer:** "调用密码哈希库提供的 verify(candidate_password, stored_hash)".

**Tech Lead Review:** Exactly — call the library `verify(candidate, stored_hash)`; do not re-hash and compare strings
manually, because the stored hash encodes algorithm/salt/cost. Two more rules: return ONE generic authentication
failure for both an unknown account and a wrong password (reduces account enumeration), and on a successful login use
`needs_rehash` to safely upgrade old parameters — never keep plaintext for a later migration. (A high-entropy random
*refresh* token may use a fast SHA-256 digest because it is not enumerable — that does NOT generalize to passwords.)

**Framework Connection:** `PasswordService.verify_password` / `authenticate` (generic `FAILED` + decoy verify) /
`needs_rehash`.

---

### Concept 3: A signed JWT is readable — keep secrets out

**Tech Lead Question:** Can you put secrets in a JWT because it is signed?

**Student Answer:** "不能".

**Tech Lead Review:** Correct. A normal signed JWT is **encoded, not encrypted**: the signature gives integrity and
issuer authenticity, not confidentiality — anyone can read the payload. Put only minimal non-secret stable claims in
an Access Token (`sub`, `iss`, `aud`, `iat`, `exp`, `jti`). Never a password hash, Provider key, prompt, Document
content, secret, or a client-asserted tenant authority.

**Framework Connection:** `issue_access_token` emits only the allowed claims; a test asserts no
password/tenant/prompt/provider/secret appears in the payload.

---

### Concept 4: Verification is a full contract, not a decode

**Tech Lead Question:** What must you check to trust a JWT beyond the signature?

**Student Answer:** "没有过期，签发者正确" (not expired, issuer correct).

**Tech Lead Review:** Good, but incomplete — you named `exp` and `iss` but omitted `aud`. The full contract is: pin
the allowed algorithm, select ONLY a trusted verification key, verify the signature plus expected issuer, audience,
expiry and not-before, and validate required claims and `sub` before building `AuthenticatedIdentity`. A verified
`sub=user-123` is trusted identity; a request-body `tenant_id=victim-tenant` is not — Day52 owns tenant authorization.

**Engineering Thinking:** A decode trusts attacker-controlled bytes; a contract trusts only what the signature and
claims prove.

**Framework Connection:** `verify_access_token` pins `ALLOWED_ALGS=("RS256",)` and rejects `alg=none`, HS256
confusion, wrong iss/aud, expired, nbf-future, missing `sub`, and tampered signatures.

---

### Concept 5: Asymmetric signing authority and rotation

**Tech Lead Question:** Auth Service issues tokens; API and Worker only verify. Symmetric or asymmetric keys?

**Student Answers:** authority "私钥签名、公钥验证"; planned rollover "K1与K2同时运行，当K1过期以后，其他全部使用K2";
K1 compromise "立即拒绝所有"; unknown kid "只从预先配置或受信任的密钥发布源刷新后再验证，找不到K3拒绝".

**Tech Lead Review:** All correct. Use asymmetric keys: the Auth Service protects the private signing key; verifiers
receive public keys only (shared symmetric verification would give every verifier signing ability). `kid` identifies
a key only within a preconfigured/trusted public-key set — never a URL/file/lookup instruction. Planned K1->K2:
publish K2, trust K1 + K2, sign with K2, retain K1 verification for K1's max token lifetime + skew, then remove K1.
Confirmed K1 compromise: reject K1 immediately, accepting forced reauthentication. An unknown `kid` may trigger one
refresh from a preconfigured trusted source; if still unknown, reject 401 and record a safe security event.

**Framework Connection:** `KeyRing` (private held by Auth Service, public allowlist for verifiers), `revoke_key`
(emergency — blocks BOTH verification and signing; if the revoked key was the current signer, issuance fails closed
until a prepared K2 is promoted via `set_current_signing_kid`), `drop_key` (post-overlap), and the
`refresh_unknown_kid` trusted-source hook.

---

### Concept 6: Access vs Refresh — stateless token vs revocable session

**Tech Lead Question:** A short Access Token limits theft, but does it give you immediate logout or
password-change revocation?

**Student Answer:** "不会" (a stateless JWT does not immediately invalidate issued Access Tokens).

**Tech Lead Review:** Right. Immediate invalidation requires a server-side state check (Session/security-version),
trading local stateless verification for a state dependency. So use a long-lived, revocable **per-device**
`AuthSession` for Refresh. The client holds a high-entropy random Refresh Token; the server stores only its hash
("保存哈希"). The database is the concurrency arbiter ("数据库").

**Framework Connection:** `AuthSessionStore` stores `refresh_token_hash` (never the raw token); `digest_refresh_token`
is a fast digest that is safe ONLY for the high-entropy random secret.

---

### Concept 7: Guarded atomic rotation, rollback, grace vs replay

**Tech Lead Question:** How do you rotate a Refresh Token safely, and what happens if the DB fails mid-rotation, or
the old token reappears?

**Student Answers:** refresh failure "整体回滚"; a used token after grace is suspected replay -> senior answer (see
interview) proposed deleting the family; concurrency winner via `UPDATE ... RETURNING`.

**Tech Lead Review:** Rotate in ONE guarded short transaction matching current hash + active/not-revoked + not
expired, atomically storing the new hash and rotation metadata. A successful `UPDATE ... RETURNING` is the SOLE
winner; zero rows must not issue a token. All-or-nothing: new hash, old-token state, retry-grace state, recovery
material, counter, and revoke state commit together or roll back together — if the DB fails after marking A used but
before B/metadata persist, rolling back keeps A the only valid token and enables a safe retry. A short bounded retry
grace genuinely recovers a lost response: the client that retries the immediately-previous token in-window gets back
the SAME usable replacement token B exactly once — held as short-TTL ENCRYPTED recovery material (never the raw token
in the clear, never a new A->C branch) and consumed after that one recovery. Replay detection covers ANY previously
used token in the family via a per-family used-token ledger (`token_family_id + token_hash`), so replaying the OLDEST
token A after A->B->C is still caught, not only the latest token. A used token AFTER the grace window is
`REPLAY_DETECTED`: reject, revoke and **retain** the `token_family_id` (audit evidence — do NOT delete it), clear
recovery material, isolate the offending device family only (sibling devices keep working), and require
reauthentication.

**Framework Connection:** `rotate_refresh` (lock-guarded, models `UPDATE ... RETURNING`) -> `ROTATED` /
`GRACE_RETRY` / `REPLAY_DETECTED` / `INVALID`; `recovery_ciphertext` (Fernet, ephemeral in-process key) returns the
same usable B once; the `_used_hashes` per-family ledger detects replay of any earlier token; `fail_before_commit`
proves rollback; `_revoke_family_locked` retains the record and ledger.

---

### Concept 8: Browser cookies and CSRF

**Tech Lead Question:** Where does a browser store the Refresh Token, and is `HttpOnly` enough for state-changing
requests?

**Student Answers:** location "还是放在带 HttpOnly、Secure、合适 SameSite 属性的 Cookie"; initial CSRF answer "http only";
corrected decision "拒绝".

**Tech Lead Review:** Cookie choice is right: `HttpOnly`, `Secure`, appropriate `SameSite`; do not return the token
in JS-readable JSON or `localStorage`. But `HttpOnly` is NOT CSRF protection — it blocks JavaScript reads, not the
browser auto-attaching the cookie. For cookie-authenticated state-changing endpoints, combine `SameSite` + Origin
(and Referer where useful) validation + a CSRF token/custom header. `SameSite=None` requires `Secure` and commonly
needs explicit CSRF defense. A cookie-only cross-site request without valid Origin + CSRF evidence is rejected.

**Framework Connection:** `evaluate_state_change_request` returns `REJECT` for a cookie-only cross-site request
lacking a valid Origin and matching CSRF token, `ALLOW` when both are present (contract, not wire runtime).

---

### Concept 9: Authentication vs authorization; per-device logout

**Tech Lead Question:** After verification, what is trusted, and what is a normal `/logout`?

**Student Answers:** trusted input "user-123"; normal logout "撤销当前一个".

**Tech Lead Review:** Only the verified `sub` -> `user_id` is trusted identity; tenant authority is Day52. A normal
`/logout` revokes only the current per-device session; logout-all, password change, key compromise, or confirmed
replay revoke all affected sessions/families. Distinguish an independent per-device family from all of a user's
devices.

**Framework Connection:** `revoke_session` (current device) vs `revoke_all_user_sessions` / `revoke_family`.

---

## 8. Common Misconceptions

Password storage
❌ "Save the password."
✅ Save an adaptive password **hash** only (Argon2id); never plaintext or reversibly encrypted.

Signed JWT
❌ A signed JWT hides its payload, so secrets are safe inside.
✅ A normal signed JWT is readable; the signature is integrity/authenticity, not encryption — keep secrets out.

JWT verification
❌ Check expiry and issuer.
✅ Pin algorithm, use a trusted key, verify signature + iss + aud + exp + nbf + required `sub` — one contract.

HttpOnly as CSRF defense
❌ `HttpOnly` prevents CSRF.
✅ `HttpOnly` blocks JavaScript reads, not automatic cookie attachment; use SameSite + Origin + CSRF token.

Replay handling
❌ Delete the token family on suspected replay.
✅ Reject and revoke while **retaining** the family record for audit; deletion destroys incident evidence.

The `RETURNING` winner
❌ The winning row has "priority".
✅ One guarded transaction wins the rotation; zero rows means stale/revoked/expired/already-used — issue nothing.

Grace window
❌ A retry grace cleanly distinguishes every network retry from theft.
✅ It accepts a small, bounded, one-time replay risk; it must not generate multiple replacement branches.

Symmetric verification key
❌ Share one key for signing and verifying everywhere.
✅ Private key signs (Auth Service); public keys verify (everyone else). Shared symmetric = every verifier can sign.

---

## 9. Engineering Trade-offs

```text
Fast hash (SHA-256) vs adaptive hash (Argon2id) for passwords
Fast: cheap to compute -> cheap to brute force. Rejected for passwords. (Fast digest is fine for a high-entropy refresh secret.)
Adaptive: expensive offline cracking; configurable cost. Chosen.

Symmetric (HS256) vs asymmetric (RS256) signing
Symmetric: one shared secret; every verifier can also sign. Rejected for multi-service verify.
Asymmetric: private signs, public verifies; verifiers cannot mint tokens. Chosen.

Stateless short Access Token vs stateful revocation
Stateless: fast local verify, no DB per request; but no immediate logout/password-change revocation.
Stateful (session/security-version): immediate revocation; costs a state lookup. Use short Access + revocable Refresh.

Refresh grace window vs strict single-use
Strict: any reappearance is replay; but a lost response locks the user out.
Bounded grace: recovers a lost response (same rotation), at a small bounded replay risk. Chosen with audit + family revoke.

Delete vs retain a replayed token family
Delete: tidy; destroys audit evidence. Rejected.
Retain + revoke: preserves incident evidence for investigation. Chosen.
```

---

## 10. Hands-on Exercises

### Exercise 1: What does the password database store, and how does login verify?

Expected Output: an adaptive Argon2id hash only; login calls the library `verify(candidate, stored_hash)`; failures
are generic.

### Exercise 2: What may never go in a signed JWT payload?

Expected Output: password hashes, Provider keys, prompts, Document contents, secrets, client-asserted tenant — the
payload is readable.

### Exercise 3: Required JWT verification checks beyond the signature

Expected Output: pinned algorithm, trusted key by `kid`, issuer, audience, expiry, not-before, required `sub`.

### Exercise 4: Design K1->K2 rotation and emergency invalidation

Expected Output: overlap trust K1 + K2, sign with K2, retain K1 verify for its lifetime + skew, then drop K1; on
confirmed compromise reject K1 immediately.

### Exercise 5: Production refresh failure/rollback (design judgment)

Question: rotation marks A used but cannot write B/metadata.
Expected Output: full transaction rollback keeps A as the only valid token; otherwise the client is irrecoverably
locked out.

### Exercise 6: Production replay (design judgment)

Question: A rotates to B, the response is lost, A retries during grace vs outside grace.
Expected Output: inside grace -> recover the SAME usable B once (`GRACE_RETRY`, from the short-TTL encrypted recovery
slot, never a new C); outside grace, or replaying any earlier family token -> `REPLAY_DETECTED` (per-family used-hash
ledger), revoke and retain the family, isolate other devices, require reauthentication.

### Exercise 7: Reject a cookie-only cross-site refresh

Expected Output: a cookie-authenticated state-changing request lacking a valid Origin + CSRF token is rejected.

---

## 11. Relevant Framework Connections

- **FastAPI** — `/login`, an authenticated API dependency (Bearer -> verify -> identity), `/auth/refresh`,
  `/logout`, generic failures, and the cookie/Origin/CSRF boundary. FastAPI itself is not used as proof here (NOT
  RUN).
- **PostgreSQL / SQLAlchemy / Day47 UoW / Day50** — a unique user identity, a persisted `AuthSession`, a short
  guarded rotation transaction (`UPDATE ... WHERE ... RETURNING`), rollback on partial persistence, and retained
  revocation/audit evidence. PostgreSQL runtime is NOT claimed.
- **Key publication / JWKS** — trusted public-key distribution, a `kid` allowlist lookup, and planned key overlap;
  never a Header-directed URL/file.

---

## 12. AI Backend Connections

- Day50 prevents duplicate expensive AI Job acceptance but must first receive a **trusted** user identity.
- A JWT must not carry prompts, verified Document content, Provider keys, or sensitive job data — a normal JWT
  payload is readable.
- Day52 maps the authenticated user identity to tenant ownership BEFORE Day49 Document admission and Day50 Job
  acceptance; a client-supplied tenant ID is not an authority claim.
- Authentication/authorization are separate from the real Provider (Day53) and worker/broker delivery (Day55).

---

## 13. English Interview

### Key Vocabulary

password hash, Argon2id, salt, work factor, `needs_rehash`, generic authentication failure, JWT (signed vs
encrypted/JWE), claims (`sub`/`iss`/`aud`/`exp`/`nbf`/`jti`), `kid` allowlist, algorithm pinning, asymmetric
signing, key rotation, Access vs Refresh, per-device session, refresh-token hash, guarded rotation, `UPDATE ...
RETURNING`, retry grace, replay detection, token family, HttpOnly/Secure/SameSite, CSRF.

### Beginner Question — password hash vs JWT

Real student answer (preserved): "A password hash is a hash value generated via an algorithm and stored in the
database during registration, whereas a JWT is a short-term authorization token issued after login."

Strong answer: "A password hash is one-way verification evidence stored at registration using a slow adaptive scheme
(Argon2id); the raw password is never stored. A JWT is a short-lived, signed identity credential issued after login —
it is readable, so it carries only non-secret claims and is trusted only after a full verification (algorithm, key,
signature, issuer, audience, expiry, subject)."

### Intermediate Question — how does the guarded refresh rotation pick a single winner?

Real student answer (preserved): "use update set returning,return 0 row,it have not priority,retrun 1 row,have priority".

Correction: "priority" is imprecise; it is a single guarded transaction winner.

Strong answer: "Rotation is one guarded transaction: `UPDATE ... WHERE current_hash matches AND session active AND
not expired RETURNING`. Exactly one concurrent request updates a row and receives it, so exactly one new refresh
token is issued; a request that returns zero rows saw a stale, revoked, expired, or already-used token and must issue
nothing. All rotation state commits together or rolls back together."

### Senior Question — a used refresh token reappears after the grace window

Real student answer (preserved): "The server should reject the request, and the database should delete the token
family ID."

Correction: reject and revoke, but RETAIN the family for audit — deletion loses incident evidence.

Strong answer: "It is a suspected replay. The server rejects the request and revokes the affected token family, but
retains the family record and audit evidence rather than deleting it. It clears any bounded recovery material,
alerts, and requires the affected device to reauthenticate. A short bounded grace window earlier can recover a lost
response for the same rotation, but it accepts a small, bounded replay risk and never branches into multiple
replacement tokens."

### Common Weak Answer

"A signed JWT is secure, so I store the tenant and a session secret in it and just decode it on the server." —
treats a readable token as confidential, trusts client-asserted tenant authority, and decodes instead of verifying.

### Strong Answer

See the senior answer: verify the full contract, trust only `sub`, keep secrets out of the payload, and handle
refresh replay by rejecting + revoking + retaining evidence.

---

## 14. Mental Model Summary

```text
Password       = adaptive one-way hash (Argon2id); library verify; generic failure; needs_rehash upgrade
Signed JWT     = readable + tamper-evident; minimal non-secret claims; verify != decode
Verify contract= pin alg + trusted key (kid allowlist) + signature + iss + aud + exp + nbf + require sub -> user_id
Keys           = private signs (Auth Service), public verifies (everyone); K1->K2 overlap; emergency revoke
Access vs Refresh = short stateless token vs revocable per-device session (store the hash)
Rotation       = one guarded UPDATE ... RETURNING winner; all-or-nothing; rollback keeps A
Grace vs replay= bounded grace recovers same B; post-grace reuse -> revoke + RETAIN family (audit)
Browser/CSRF   = HttpOnly/Secure/SameSite cookie + Origin + CSRF token; HttpOnly != CSRF defense
AuthN vs AuthZ = trusted user_id now; tenant/permissions/quota = Day52
```

---

## 15. Today's Takeaway

- **Most important mental model:** authenticate WHO the caller is (trusted `user_id`) before deciding what they may
  do (Day52).
- **Most important production risk:** plaintext/fast-hashed passwords, secrets in a readable JWT, decode-instead-of-
  verify, or a refresh flow that locks users out or lets tokens replay.
- **Most important trade-off:** short stateless Access Token + revocable per-device Refresh Session; bounded grace at
  a small, audited replay risk.
- **Most important framework connection:** a full JWT verification contract with a pinned algorithm and a trusted
  key resolved by an allowlisted `kid`.
- **Most important AI Backend connection:** never put prompts/Document content/Provider keys/tenant authority in a
  readable JWT; Day52 derives tenant from the verified identity.
- **Most important interview answer:** on refresh replay, reject + revoke + retain the family evidence — do not
  delete it.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain why a password DB stores an adaptive hash and login uses the library verify?
- [ ] Can I list what must never go in a readable signed JWT payload?
- [ ] Can I state the full JWT verification contract (alg, key/kid, signature, iss, aud, exp, nbf, sub)?
- [ ] Can I design asymmetric signing authority, a K1->K2 rotation, and emergency revocation?
- [ ] Can I compare a stateless Access Token with a revocable per-device Refresh Session?
- [ ] Can I run a guarded atomic rotation, roll it back on partial persistence, and handle grace vs replay?
- [ ] Can I explain why HttpOnly is not CSRF defense and reject a cookie-only cross-site refresh?
- [ ] Can I explain why only the verified sub is trusted, while tenant authority is Day52?
- [ ] Can I answer a beginner, intermediate, and senior interview question about this in English?
```

---

## Assistant-assisted final Chinese synthesis

At the student's explicit request ("你帮我总结"), the following synthesis was assistant-assisted (not quoted as the
student's own prose), consolidating the day's corrected model:

```text
认证先解决"调用者是谁"，而不是先解决"调用者能操作哪个租户"。

用户密码只以专用慢哈希保存；登录时由密码库验证，不保存明文，也不把密码或密码哈希放进 JWT。

短期 Access JWT 用签名证明它没有被篡改且来自受信任签发者，但 Payload 默认可读。因此 API 必须固定算法、
使用受信任密钥，并验证签名、iss、aud、exp、nbf 和 sub；验证成功后，只有 sub 对应的 user_id 是可信身份。
tenant_id 的归属与权限由 Day52 决定。

Auth Service 用私钥签发，API/Worker 用公钥验证。计划轮换时 K1/K2 验证重叠直到 K1 Token 自然到期；
K1 私钥泄露时立即停止信任 K1，即使会迫使用户重新登录。

Access Token 短期有效，限制被盗后的风险窗口；长期连续登录依赖服务端持久化、可撤销的 Refresh Session。
Refresh Token 是高熵随机秘密，客户端持有原文，数据库只存 hash；浏览器中使用 HttpOnly、Secure、SameSite
Cookie，并以 Origin 与 CSRF Token 防御 Cookie 自动发送带来的 CSRF。HttpOnly 防 JavaScript 读取，不防 CSRF。

Refresh rotation 是数据库原子状态转换：只有一个 guarded UPDATE ... RETURNING 请求赢得 A->B；全部相关状态
要么一起提交，要么回滚。为网络丢失响应可给旧 Token 极短、一次性的受控重试窗口，但这接受小的重放风险。
旧 Token 在窗口后再出现是疑似重放：拒绝、撤销并保留当前 token family 的审计证据，要求受影响设备重新登录，
而不是删除证据。

Day50 解决"一条逻辑 AI Job 命令只可靠接受一次"；Day51 解决"谁提交了它"；Day52 才解决"这个已认证用户能否
代表某个 tenant 提交、读取或操作它"。
```

---

Engineering artifact + runbook:
[`projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md`](../../projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md).
Runnable model: [`day51_authentication_jwt.py`](../../projects/ai-backend-data-layer/api/day51_authentication_jwt.py);
tests: [`test_day51_authentication_jwt.py`](../../projects/ai-backend-data-layer/api/test_day51_authentication_jwt.py)
(real Argon2id + real RS256 JWT with ephemeral keys; **34 passed**; Python 3.10.12, argon2-cffi 23.1.0, PyJWT 2.8.0,
cryptography 48.0.0, pytest 7.4.3). PostgreSQL / FastAPI / browser / JWKS / integration / production runtime: **NOT
RUN**.
