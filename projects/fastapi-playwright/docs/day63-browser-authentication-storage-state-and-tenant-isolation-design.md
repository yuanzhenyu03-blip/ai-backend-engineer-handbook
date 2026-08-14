# Day63 — Browser Authentication, Storage State and Tenant Isolation (design / runbook)

Connected, runnable Day63 artifact inside the EXISTING `projects/fastapi-playwright/` project (no
parallel Playwright project). It turns Day62's per-task `BrowserContext` ownership into an
AUTHENTICATED, tenant-bound, revocable browser-session capability, and proves the authorization/
claim CONTROL FLOW with pure logic plus a controlled loopback page. It does NOT implement Day64
extraction/artifacts, Day65 recovery/security/SSRF/prompt-injection, or Day66 queue integration.

## Files

- `src/day63_session_gate.py` — pure decision core (standard library only): Job-binding validation,
  the atomic-claim classifier (`UPDATE ... RETURNING` semantics), credential-load gating, identity
  verification (positive `principal_id`/`organization_id` fact), Origin/navigation security check,
  the final fence, storage-state Origin/Cookie-domain allowlist filtering, the connection-flow
  persist classifier (verified login → new active version only after protected-state + metadata/audit
  commit), and an orchestrator that proves the NEGATIVE effects.
- `src/day63_controlled_login_page.py` — a controlled localhost account page (synthetic identity
  facts; `account` / `login_redirect` / `unapproved_origin` modes) for the gated real-browser suite
  and a browserless HTTP-loopback contract test.
- `tests/test_day63_session_gate.py` — pure-logic + NEGATIVE-effect tests + static gate-source
  contract checks (all EXECUTED_LOCAL_RUNTIME).
- `tests/test_day63_controlled_login_page_http.py` — REAL HTTP-loopback page-contract tests.
- `tests/test_day63_playwright_isolation.py` — the real-Chromium suite ONLY: Context cookie isolation,
  a REAL popup to an UNAPPROVED Origin observed and driven through the Gate to `SECURITY_FAILURE`
  (Context closed, nothing published), and a login-redirect proving no auto-login yields
  `AUTHENTICATION_PRECONDITION_FAILED`. GATED on the
  `playwright` package via a module-level `importorskip` (this file — and only this file — skips when
  the package is absent). The static contract checks live in `test_day63_session_gate.py` so they are
  never swallowed by the skip.

The import path is provided by the existing `projects/fastapi-playwright/pytest.ini`
(`pythonpath = src`); no `sys.path` hacks and no package install.

## Model + pipeline

```text
Tenant = business scope ; BrowserSession = revocable authorization capability ;
storage_state = sensitive credential material ; BrowserContext = per-task runtime isolation ;
lease/fencing = attempt-owned continuing authority.

validate binding -> atomic claim (active + not revoked + not expired + lease available)
  -> ONLY winner reads protected credential reference
    -> fresh Context from filtered storage state
      -> verify POSITIVE identity fact at approved Origin
        -> allowed actions + fencing checks
          -> FINAL fence before publish (active + not expired + lease_owner==attempt + token +
             lease_expires_at>now + version) -> publish only if authorized
            -> close Context in finally (every path); a published result whose close() FAILED is
               reported INCOMPLETE (TaskCompletion), never SUCCESS
```

Outcomes (every non-AUTHORIZED blocks publication; none is business `no result`; none permits a blind
retry): `AUTHENTICATION_PRECONDITION_FAILED`, `AUTHORIZATION_SESSION_FAILURE`,
`UNKNOWN_AUTHORIZATION_STATE`, `SECURITY_FAILURE`.

## Threat / failure boundaries

- Credential material never enters a Job payload, a queue message, a log, a screenshot, or the repo;
  only a protected reference + metadata are durable, and the encrypted content lives in a
  least-privilege, audited store (a LABELED boundary — not implemented/executed in Day63).
- Exported storage state is filtered to explicit Origin/Cookie-domain allowlists. The DEFAULT
  Cookie-domain allowlist is the approved Origin's HOST (parsed hostname), never the full Origin
  string, so a host-only Cookie survives while a `.example.test` cross-subdomain Cookie is rejected
  unless explicitly, auditably added; Local Storage is kept only for the exact approved Origin.
- A verified login becomes a new ACTIVE Session version ONLY after protected-state persistence AND
  the metadata/audit commit both succeed. Only `state saved + metadata failed` is `ORPHAN_INACTIVE`
  (a protected-but-inactive candidate); `state NOT saved` is `PERSIST_CONSISTENCY_FAILED` — there is
  no protected material, so it is never an orphan and never active.
- A client-supplied `session_id` is only a candidate; the API authorizes it before recording it on a
  Job and the Worker re-checks + atomically claims it.
- Revocation/version replacement prevents new claims and fails future critical-action/final checks;
  it does NOT un-send a request already made (a Day65 recovery boundary).

## Run

```bash
cd projects/fastapi-playwright
python3 -m pip install pytest==7.4.3
python3 -m pytest -q tests/test_day63_session_gate.py \
  tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py
# -> 28 passed, 1 skipped: pure logic + NEGATIVE-effect + static contract + HTTP-loopback all run;
#    only the real-Chromium isolation module skips (playwright not installed) — honestly NOT RUN.

# OPT-IN real browser (EXECUTED_LOCAL_RUNTIME for isolation/redirect observation):
python3 -m pip install playwright==1.44.0 && python3 -m playwright install chromium
python3 -m pytest -q tests/test_day63_playwright_isolation.py
```

## Validation matrix (evidence tiers)

```text
[CONCEPTUAL_STATIC]      The LIVE CLASSROOM session — no Day63 source/tests/browser/PostgreSQL/
                         credential-store/queue/production run was executed in class.
[EXECUTED_LOCAL_RUNTIME] Run by the updating agent: py_compile + the pure Session-Gate logic +
                         NEGATIVE-effect orchestrator tests + static gate-source contract + the
                         controlled account page over REAL HTTP loopback = 28 passed, 1 skipped.
[EXECUTED_LOCAL_RUNTIME] (OPT-IN, NOT RUN here) real Chromium + the controlled page: BrowserContext
                         cookie isolation; a REAL popup to an unapproved Origin driven through the
                         Gate to SECURITY_FAILURE (Context closed, no publish); a login-redirect
                         proving no auto-login -> AUTHENTICATION_PRECONDITION_FAILED. Gated on
                         `playwright`; SKIPPED in the agent environment — these browser facts are
                         NOT claimed as verified until Playwright/Chromium actually run them.
[INTEGRATION_RUNTIME]    NOT RUN — real PostgreSQL `UPDATE ... RETURNING` atomic claim, protected
                         credential encryption/KMS/Object Storage, a real Worker, and real Playwright,
                         only if actually executed and evidence saved.
[PRODUCTION]             NOT RUN.
```

Day62's `13 passed, 1 skipped` is Day62-only evidence and is NOT reused as Day63 proof. No secrets,
real credentials, real target URLs, real tenant data, screenshots, cookies, tokens, or storage-state
exports are committed; all identifiers are synthetic and the page is served on 127.0.0.1.
