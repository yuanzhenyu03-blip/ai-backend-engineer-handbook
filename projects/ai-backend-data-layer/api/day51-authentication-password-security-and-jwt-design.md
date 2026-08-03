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

Executed: `python3 -m pytest -q test_day51_authentication_jwt.py` -> **27 passed**
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
  K1's max token lifetime + clock skew; then `drop_key(K1)`. Confirmed K1 compromise: `revoke_key(K1)` -> reject
  immediately (before expiry), accepting forced reauthentication.

---

## 4. Access vs Refresh lifecycle

- A short-lived Access Token limits the theft window but does NOT give immediate logout / password-change
  revocation; immediate invalidation needs a server-side state check (Session / security-version), trading stateless
  verification for a state dependency.
- Use a long-lived, revocable **per-device** `AuthSession` for Refresh. The client holds a high-entropy random
  Refresh Token; the server stores only its hash (`refresh_token_hash`). Fields modeled: `session_id`, `user_id`,
  `token_family_id`, `refresh_token_hash`, `created_at`, `expires_at`, `revoked_at`, `last_rotated_at`,
  `rotation_counter`, plus grace fields (`previous_refresh_token_hash`, `previous_used_at`, `retry_grace_expires_at`,
  `grace_result_token_hash`).

---

## 5. Atomic Refresh rotation, grace, replay (`AuthSessionStore`)

```text
rotate_refresh(raw): one guarded critical section (models UPDATE ... WHERE current_hash + active + not-expired RETURNING)
  current-hash match on active, unexpired session -> SOLE winner: store new hash + previous_* + retry grace + counter
       (all-or-nothing; fail_before_commit -> rollback -> A stays the only valid token)  -> ROTATED
  previous-hash match within grace window          -> recover the SAME rotation (never A->C branch)  -> GRACE_RETRY
  previous-hash match AFTER grace (or revoked)     -> REPLAY_DETECTED: revoke + RETAIN the family (audit), issue none
  unknown / expired / revoked                      -> INVALID (zero rows), issue nothing
```

- A successful `UPDATE ... RETURNING` is the **sole winner**; zero rows must not issue a token (concurrent rotate ->
  one `ROTATED`, one `GRACE_RETRY`, one session/family — no C branch).
- **All-or-nothing**: new hash, old-token state, retry-grace state, recovery material, counter, and revoke state
  commit together or roll back together. If the DB fails after marking A used but before B/metadata persist, rolling
  back preserves A as the only valid token and enables a safe retry.
- **Bounded grace trade-off**: a short, tightly bounded retry grace is acceptable for a lost refresh response; it
  recovers the same rotation result, keeps only a narrowly TTL-bounded, strongly-protected recovery reference
  (hash-only persistence), and does NOT distinguish every network retry from theft — a documented residual replay
  risk.
- **Replay after grace** -> reject, revoke/retain the `token_family_id` (per-device family, distinct from all user
  devices), clear recovery material, audit + alert, require reauthentication. **Do not delete the family record** —
  deletion destroys security evidence.
- Revocation scopes: `revoke_session` (normal `/logout`, current device only); `revoke_family` /
  `revoke_all_user_sessions` (logout-all / password change / key compromise / confirmed replay).

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
| kid allowlist + unknown-kid refresh + emergency revoke + K1->K2 overlap | RUN (real crypto) | trusted-set lookup; refresh-then-reject; revoke; drop_key |
| Per-device Refresh: hash-only, guarded rotation, rollback | MODELED (RUN) | in-memory store + lock; UPDATE-RETURNING single winner; mid-tx rollback keeps A |
| Bounded grace + replay -> family revoke (retained) | MODELED (RUN) | grace recovers same B; post-grace replay revokes + retains family |
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
