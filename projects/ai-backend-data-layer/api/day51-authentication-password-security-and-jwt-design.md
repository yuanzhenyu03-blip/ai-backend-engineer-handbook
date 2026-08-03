# Day51 — Authentication, Password Security and JWT (Design + Runbook)

Engineering artifact for `docs/fastapi/day51-authentication-password-security-and-jwt.md`.
Runnable model: [`day51_authentication_jwt.py`](day51_authentication_jwt.py); tests:
[`test_day51_authentication_jwt.py`](test_day51_authentication_jwt.py); deps:
[`requirements-day51.txt`](requirements-day51.txt).

Continues the existing `projects/ai-backend-data-layer/` artifact. Reuses Day47 short UoW + guarded transitions and
Day50's "database as the concurrent arbiter, roll back on partial persistence, retain evidence under uncertainty".

---

## 0. Evidence label (read first)

```text
CONCEPTUAL / CLASSROOM DESIGN     : COMPLETED
STATIC DAY51 FILE CHECKS          : RUN (py_compile of module + tests)
REAL-CRYPTO CONTROL-FLOW RUNTIME  : RUN (real Argon2id + real RS256 JWT with ephemeral keys; in-memory store)
POSTGRESQL RUNTIME                : NOT RUN (no server; no UNIQUE/tx/isolation/UPDATE ... RETURNING proof)
FASTAPI / BROWSER RUNTIME         : NOT RUN (no real cookies/SameSite/Origin/CSRF at the wire; no JWKS endpoint)
INTEGRATION / PRODUCTION          : NOT RUN
```

The tests use REAL crypto primitives (argon2-cffi Argon2id; PyJWT + cryptography RS256) with keys generated
in-process, over an in-memory user + AuthSession store that MODELS guarded rotation. This proves the crypto +
application control flow — it is NOT database, HTTP/browser, or production runtime. Three claims are kept separate:
**Conceptual Artifact**, **Static / real-library control-flow Verification** (what ran), and **Real Runtime
Verification** (NOT RUN). Day50 evidence is not inherited.

Executed: `python3 -m pytest -q test_day51_authentication_jwt.py` -> **37 passed**
(Python 3.10.12; argon2-cffi 23.1.0, PyJWT 2.8.0, cryptography 48.0.0, pytest 7.4.3).

SECURITY: no plaintext password, refresh token, JWT, Provider key, real/operational signing key, signed URL,
database URL, or user data is committed; test signing keys are generated in-process and never written to disk; raw
credentials / JWT payloads are never logged.

---

## 1. Core mental model

```text
Password hash    = one-way password verification evidence (slow adaptive Argon2id; NEVER plaintext/reversible)
Signed JWT       = short-lived, READABLE-but-tamper-evident authenticated identity credential (integrity, not secrecy)
Refresh Session  = server-owned, revocable, PER-DEVICE continuation state (store the hash, not the raw token)
Authentication   = establish a trusted user_id (verified `sub`)     Authorization = Day52 decides what that user may do
```

A verified `sub=user-123` is trusted identity; a request-body `tenant_id` is NOT trusted — Day52 owns tenant
authority.

---

## 2. Passwords (real Argon2id)

- Store an adaptive password **hash only** (Argon2id with library-managed salt + configurable work factor); never
  plaintext or reversibly encrypted. Do NOT use a fast general hash (SHA-256) for user passwords.
- **Secure default cost**: `PasswordService()` uses argon2-cffi's SECURE production default (`PasswordHasher()` —
  `time_cost=3`, `memory_cost=65536` KiB, `parallelism=4`), NOT a test-tuned value. Operators MUST benchmark against
  real deployment hardware and raise the cost until a single hash takes a deliberate fraction of a second. Tests that
  need speed inject an explicit low-cost hasher; that weak value is never the module default (`needs_rehash` then
  transparently upgrades any hash made under an older, weaker policy on the next successful login).
- Login verifies with `PasswordService.verify_password(candidate, stored_hash)` -> the library `PasswordHasher.verify`
  (the stored hash encodes algorithm/salt/cost; never re-hash-and-compare strings).
- `authenticate` returns ONE generic failure for an unknown account AND a wrong password (anti-enumeration), and
  runs a decoy verify for an unknown user to equalize timing.
- A successful login can `needs_rehash` to upgrade old parameters; never retain plaintext for a later migration.
- A cryptographically random **refresh** secret may use a fast SHA-256 digest (`digest_refresh_token`) because it is
  high-entropy and not enumerable — this rule does NOT generalize to user passwords.

---

## 3. JWT — asymmetric RS256, full verification contract

- A normal signed JWT is **encoded, not encrypted**: the signature gives integrity + issuer authenticity, not
  confidentiality. Put ONLY minimal non-secret stable claims in an Access Token (`sub/iss/aud/iat/exp/jti`). Never a
  password hash, Provider key, prompt, Document content, secret, or client-asserted tenant.
- **Verification is a full contract, not a decode** (`verify_access_token`): pin the algorithm (`ALLOWED_ALGS =
  ("RS256",)`), resolve a TRUSTED public key by allowlisted `kid`, verify signature + expected issuer + audience +
  `exp` + `nbf`, and require `sub` before building `AuthenticatedIdentity(user_id=sub)`. Any failure raises and
  yields no identity. Rejected: `alg=none`, HS256 algorithm-confusion, wrong iss/aud, expired, not-yet-valid,
  missing `sub`, tampered signature, unknown/revoked `kid`.

### Signing-key authority + rotation

- Auth Service protects the private signing key; verifiers hold **public keys only** (`KeyRing`). Shared symmetric
  verification would give every verifier signing ability.
- `kid` identifies a key ONLY within a preconfigured/trusted public-key set — never a URL/file/lookup instruction.
  An unknown `kid` may trigger ONE refresh from a preconfigured trusted source (`refresh_unknown_kid`); if still
  unknown -> reject 401 + safe security event. Never trust Header-directed URLs/files.
- Planned K1->K2: publish K2 public key; verifiers trust K1 + K2; sign new Tokens with K2; retain K1 verification for
  K1's max token lifetime + clock skew; then `drop_key(K1)`.
- **Confirmed K1 compromise fails closed for BOTH verify and sign**: `revoke_key(K1)` immediately stops trusting K1
  for verification (`public_pem_for -> None`) AND refuses to SIGN with it (`signing_key` raises). If K1 was the
  current signing key, `revoke_key` clears `current_signing_kid` so `issue_access_token` fails closed — no token is
  minted — until an operator promotes a prepared, non-revoked K2 via `set_current_signing_kid("K2")` (which itself
  refuses a revoked key). We deliberately do NOT auto-pick a replacement. Already-issued K1 tokens fail verification
  at once; forced reauthentication is accepted.

---

## 4. Access vs Refresh lifecycle

- A short-lived Access Token limits the theft window but does NOT give immediate logout / password-change
  revocation; immediate invalidation needs a server-side state check (Session / security-version), trading stateless
  verification for a state dependency.
- Use a long-lived, revocable **per-device** `AuthSession` for Refresh. The client holds a high-entropy random
  Refresh Token; the server stores only its hash (`refresh_token_hash`). Fields modeled: `session_id`, `user_id`,
  `token_family_id`, `refresh_token_hash`, `created_at`, `expires_at`, `revoked_at`, `last_rotated_at`,
  `rotation_counter`, plus grace fields (`previous_refresh_token_hash`, `previous_used_at`, `retry_grace_expires_at`,
  `grace_result_token_hash`, and `recovery_ciphertext` — a short-TTL ENCRYPTED copy of the raw replacement token B for
  a lost-response recovery, never the raw token in the clear). The store also keeps a per-family **used-token ledger**
  (`token_family_id + token_hash` for every retired token) so replay of ANY earlier token in the family is detected.

---

## 5. Atomic Refresh rotation, grace, replay (`AuthSessionStore`)

```text
rotate_refresh(raw): one guarded critical section (models UPDATE ... WHERE current_hash + active + not-expired RETURNING)
  (1) current-hash match on active, unexpired session -> SOLE winner: store new hash + previous_* + retry grace +
       counter + ENCRYPT raw B into recovery_ciphertext + ledger the retired hash
       (all-or-nothing; fail_before_commit -> rollback -> A stays the only valid token; A not yet ledgered)  -> ROTATED
  (2) immediately-previous hash within grace window   -> decrypt recovery_ciphertext, return the SAME usable B ONCE
       (consume the recovery slot; never an A->C branch)                                          -> GRACE_RETRY(B)
       (already consumed within the window            -> GRACE_RETRY(None): documented safe failure, re-authenticate)
  sweep_expired_recovery_material(now): for every session past retry_grace_expires_at, DESTROY recovery_ciphertext +
       grace_result_token_hash even if A never returned (fail-closed on time); RETAIN the used-token ledger + audit.
       Models a reliable scheduled cleanup job; a real PostgreSQL deployment MUST run it (cron / pg_cron).
  (3) ANY used family token via the used-hash ledger  -> REPLAY_DETECTED: revoke the family + RETAIN records/ledger
       (audit), clear recovery material, isolate other device families, issue nothing
  (4) unknown / expired / revoked                     -> INVALID (zero rows), issue nothing
```

- A successful `UPDATE ... RETURNING` is the **sole winner**; zero rows must not issue a token (concurrent rotate ->
  one `ROTATED`, one `GRACE_RETRY`, one session/family — no C branch).
- **All-or-nothing**: new hash, old-token state, retry-grace state, recovery material, counter, and revoke state
  commit together or roll back together. If the DB fails after marking A used but before B/metadata persist, rolling
  back preserves A as the only valid token and enables a safe retry.
- **Bounded grace trade-off**: a short, tightly bounded retry grace genuinely recovers a lost refresh response — the
  client retrying the immediately-previous token in-window receives the SAME usable replacement token B exactly once.
  The recoverable material is the raw B held as Fernet **ciphertext** under an ephemeral in-process key (a real
  deployment uses a KMS/HSM), bounded by `retry_grace_expires_at`, consumed after one recovery, and cleared on grace
  expiry / replay / revoke — the raw token is never persisted in the clear, never logged, and never a plain durable
  field. The grace does NOT distinguish every network retry from theft — a documented residual replay risk — and once
  the single recovery is consumed the honest fallback is reauthentication.
- **Minimum-retention lifecycle (do not depend on the client retrying)**: recovery material lives ONLY until
  `retry_grace_expires_at`. `A -> B` arms `recovery_ciphertext` + `grace_result_token_hash`; once the window expires,
  both MUST be destroyed EVEN IF the old A is never resubmitted — a client that abandons the flow must not leave
  recoverable B material in the record. `sweep_expired_recovery_material(now)` is an explicit, testable cleanup that
  clears them for every past-grace session, is **fail-closed on time** (no `retry_grace_expires_at` or an in-window
  session is left untouched), and RETAINS the used-token ledger + Session audit record. Clearing recovery material
  does NOT delete the retired-token ledger, so a post-grace replay of A stays `REPLAY_DETECTED`, never a degraded
  `INVALID`. All revoke paths (`revoke_session`, family revoke, `revoke_all_user_sessions`) destroy recovery material
  immediately through the shared `_clear_recovery_material` helper; the sweep is ONLY the expiry fallback for an
  abandoned token that never returns. **Real deployment**: run this as
  a reliable scheduled job (periodic sweep / cron / `pg_cron`) bounded by `retry_grace_expires_at` — the in-memory
  method models that job; relying on "clear it when the old token is next seen" is unsafe because the client may never
  retry.
- **Replay of ANY used family token after grace** -> reject, revoke/retain the `token_family_id` (per-device family,
  distinct from other user devices), clear recovery material, audit + alert, require reauthentication. Detection uses
  the per-family **used-token ledger**, so replaying the OLDEST token A after A->B->C is caught (not only the latest
  token). Revocation isolates only that device family; a sibling device for the same user keeps working. **Do not
  delete the family record or ledger** — deletion destroys security evidence.
- Revocation scopes: `revoke_session` (normal `/logout`, current device only); `revoke_family` /
  `revoke_all_user_sessions` (logout-all / password change / key compromise / confirmed replay). EVERY revoke path
  (single, family, all-user) destroys the session's recovery material IMMEDIATELY via the shared
  `_clear_recovery_material` helper — a revoked session never keeps a decryptable grace-window token waiting for the
  sweep. The expiry `sweep_expired_recovery_material` is only the fallback for sessions whose grace window lapses
  because the old token is never resubmitted. Both keep the used-token ledger + audit record (post-grace replay stays
  `REPLAY_DETECTED`).

---

## 6. Browser boundary and CSRF (contract, not wire runtime)

- For browsers, prefer the Refresh Token in an `HttpOnly`, `Secure`, appropriately `SameSite` Cookie; do NOT return
  it in JS-readable JSON or `localStorage`.
- `HttpOnly` reduces XSS token exfiltration but does NOT stop the browser from auto-attaching the Cookie — it is NOT
  CSRF protection. For cookie-authenticated state-changing endpoints, combine `SameSite` + Origin (and Referer where
  useful) validation + a CSRF-token/custom-header. `SameSite=None` requires `Secure` and commonly needs explicit
  CSRF defense; restrict Cookie Domain/Path.
- `evaluate_state_change_request(...)` models the DECISION (cookie-only cross-site without valid Origin + matching
  CSRF -> reject). Real cookie/header handling is FastAPI/browser runtime, NOT exercised here.

---

## 7. FastAPI integration contract (not run)

`/login` (verify password -> issue Access + create Refresh Session), an authenticated API dependency (extract Bearer
-> `verify_access_token` -> `AuthenticatedIdentity`), `/auth/refresh` (guarded `rotate_refresh`), `/logout`
(`revoke_session`), generic failures, and the cookie/Origin/CSRF boundary. Day52 consumes `AuthenticatedIdentity`
for tenant membership/authorization/quota; a client-supplied `tenant_id` is not authority. FastAPI itself is not
used as proof here (NOT RUN).

---

## 8. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| Static file checks | RUN | `py_compile` module + tests |
| Real Argon2id password hash/verify | RUN | argon2-cffi; hash!=plaintext, verify T/F, generic failure, needs_rehash |
| Real RS256 JWT full-contract verification | RUN | PyJWT+cryptography ephemeral keys; alg pin, iss/aud/exp/nbf/sub, alg=none/HS256/tamper rejected |
| kid allowlist + unknown-kid refresh + emergency revoke + K1->K2 overlap | RUN (real crypto) | trusted-set lookup; refresh-then-reject; revoke blocks verify AND sign; revoking current signer fails closed then promote K2; drop_key |
| Per-device Refresh: hash-only, guarded rotation, rollback | MODELED (RUN) | in-memory store + lock; UPDATE-RETURNING single winner; mid-tx rollback keeps A |
| Bounded grace recovers the SAME usable B (once, encrypted, never A->C) | MODELED (RUN) | lost-response retry returns the same usable B; one-time consume; raw never plain-persisted |
| Recovery-material minimum retention: swept at grace expiry even if A never returns | MODELED (RUN) | `sweep_expired_recovery_material` clears ciphertext + grace hash past grace; fail-closed on time; ledger/audit retained; replay still `REPLAY_DETECTED` |
| Reliable scheduled cleanup of recovery material | NOT RUN | needs a real periodic job (cron / `pg_cron` / worker) bound to `retry_grace_expires_at` |
| Replay of ANY used family token -> family revoke (retained), devices isolated | MODELED (RUN) | per-family used-hash ledger; replay of oldest token after A->B->C revokes+retains; sibling device unaffected |
| CSRF/browser decision | MODELED (RUN) | `evaluate_state_change_request` cookie/Origin/CSRF logic |
| Real PostgreSQL UNIQUE/tx/isolation/`UPDATE ... RETURNING` | NOT RUN | needs a server + async driver + Day42 raw SQL + a Day48-safe additive AuthSession migration |
| Real FastAPI/browser (cookies/SameSite/Origin/CSRF) + JWKS endpoint | NOT RUN | HTTP-layer runtime |
| Integration + production | NOT RUN | — |

`Real crypto + in-memory control-flow tests do not prove PostgreSQL constraints/transactions/isolation, real
FastAPI/browser cookie/CSRF behavior, a real JWKS distribution, integration, or production.`

---

## 9. Schema honesty

The `AuthSession` per-device table (with `token_family_id`, `refresh_token_hash`, rotation + grace + revoke columns)
is MODELED in-memory here; the real schema would add it via a **Day48-safe FORWARD additive migration** (a new table
+ unique/index on the current hash, via a branch revision) — NOT implemented here, and no published Alembic revision
is rewritten. Users already have a unique identity in the schema; only a `password_hash` column and the AuthSession
table are new-facts for a real deployment.

---

## 10. Boundaries preserved (not implemented here)

Day51 authenticates WHO the caller is; it does NOT implement Day52 tenant membership/authorization/quota/rate-limit,
Day53 real Provider SDK, or Day55 Celery runtime. JWE (encrypted JWT) is out of scope — a normal signed JWT is
readable. No integration/production/browser runtime is claimed.
