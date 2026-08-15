# Day65 — Browser Failure Recovery and Security Boundaries (design / runbook)

Connected, runnable Day65 artifact inside the EXISTING `projects/fastapi-playwright/` project (no
parallel project). It turns Day64's trusted-Artifact browser flow into a RECOVERABLE, SECURITY-BOUNDED
capability with a pure decision core. It does NOT implement the Day66 durable queue-backed Worker.

## Files

- `src/day65_recovery_security_policy.py` — pure decision core (standard library only), ten areas:
  timeout classification (`UNKNOWN_OUTCOME` vs `SAFE_TO_RETRY`); unknown-outcome reconciliation by
  strict Day64 action identity; diagnostics policy (private/redacted/access-controlled/retention-
  bounded/audited only); navigation/redirect SSRF gate (scheme + exact Origin + resolved IP +
  redirect revalidation); credential release (tenant/session/attempt/origin/purpose/validity, no
  cross-Origin storage-state forwarding); instruction authority (`PROMPT_INJECTION_BLOCKED`); CAPTCHA
  (`HUMAN_VERIFICATION_REQUIRED`); bounded retry eligibility; `Retry-After` vs deadline; and incident
  classification. It reuses `day63_session_gate.final_fence` to revalidate authorization before a
  retry or a credential release.
- `tests/test_day65_recovery_security_policy.py` — focused failure/security tests (EXECUTED_LOCAL_RUNTIME).

The import path is provided by the existing `pytest.ini` (`pythonpath = src`); no `sys.path` hacks.

## Browser Task Decision Contract v1.0

```text
Task / server-side policy
  -> sole authorization source for targets, operations, data, and credentials

Before action
  -> authorization + Session + lease + website policy + SSRF gate

After failure
  -> proven retryable failure: bounded retry
  -> action may have happened: reconcile original action (UNKNOWN_OUTCOME)
  -> security boundary: stop / human review
  -> deadline or budget exhausted: stop new Attempts

Diagnostics
  -> minimal, redacted, private, retention-bounded, audited
  -> never ordinary logs, model context, prompts, or public Artifact

Incident
  -> contain -> scope -> classify -> repair -> controlled rollout
```

## Rules enforced

- A possible POST-ACTION timeout is `UNKNOWN_OUTCOME` (the action may have executed) — never
  `SAFE_TO_RETRY`; a missing captured response is not proof the server never accepted the action.
  Reconcile by the ORIGINAL action's strict `client_request_id`/`report_id`/verified `export_id` + a
  server status/audit lookup — never a broad URL + HTTP 200.
- Diagnostics (screenshots/traces/headers/raw payloads/DOM/Cookies/Authorization/tokens/PII/tenant
  data) may only go to a private, access-controlled, retention-bounded, audited store, redacted when
  sensitive — never ordinary logs, the model context, a prompt, or a public Artifact. A screenshot
  proves page display only, not Export/Artifact success.
- Page content is untrusted input, not authorization. Every navigation/redirect is validated
  server-side by scheme + EXACT Origin (host+port) + resolved IP + task scope; loopback, private,
  link-local, and cloud-metadata (169.254.169.254) targets are blocked, and redirects/DNS-IP changes
  are revalidated.
- Credentials are protected scoped capabilities: release requires the current tenant/session/attempt,
  an approved Origin, an explicit purpose, a valid session, and least privilege. Cross-Origin
  navigation never copies/exports/forwards storage state.
- The task contract + server-side policy are the sole authority; DOM/page/download/network/model
  output are untrusted, and their overreach is `PROMPT_INJECTION_BLOCKED`. A CAPTCHA is
  `HUMAN_VERIFICATION_REQUIRED` — never bypassed/evaded/outsourced/disguised as a retryable failure.
- A bounded retry needs an explicit retryable class, proven non-start/idempotency (no
  `UNKNOWN_OUTCOME`), no security stop, valid authorization, remaining deadline/budget, and one active
  owner. A `Retry-After` beyond the remaining deadline ends the task (`RETRY_DEFERRED`) — never a new
  Attempt.
- An incident is handled `contain -> scope -> classify -> repair -> controlled rollout`; items are
  classified from actually-preserved evidence (`BLOCKED_BEFORE_NAVIGATION` /
  `UNAPPROVED_NAVIGATION_NO_CREDENTIAL_RELEASE` / `POSSIBLE_CREDENTIAL_EXPOSURE` /
  `PUBLISHED_ARTIFACT_AFFECTED` / `UNKNOWN`); `UNKNOWN` is reconciled/investigated, never blindly retried.

## Run

```bash
cd projects/fastapi-playwright
python3 -m pip install pytest==7.4.3
python3 -m pytest -q tests/test_day65_recovery_security_policy.py
# -> 12 passed: pure decision-core failure/security rules. No browser, trace, Object Storage,
#    PostgreSQL, or queue is involved.
```

## Validation matrix (evidence tiers)

```text
[CONCEPTUAL_STATIC]      The LIVE CLASSROOM created a decision-contract design only — no Day65 source,
                         tests, Playwright, traces, screenshots, Object Storage, DB transactions, queue
                         Worker, or production ran in class.
[EXECUTED_LOCAL_RUNTIME] Run by the updating agent: py_compile + the pure recovery/security decision
                         core (timeout/reconcile/diagnostics/SSRF/credential/instruction/CAPTCHA/retry/
                         Retry-After/incident) = 12 passed.
[NOT RUN]                Real Playwright timeout/reconciliation; real trace/screenshot redaction; real
                         redirect/DNS/IP enforcement; real storage-state/Cookie behaviour; real CAPTCHA
                         handling; a real audit lookup; a real Worker/queue; integration; production.
[PRODUCTION]             NOT RUN.
```

Day64's `25 passed` result is Day64-only evidence and is NOT reused as Day65 validation. No secrets,
real credentials, real target URLs, Cookies, tokens, customer data, raw sensitive payloads,
screenshots, or CAPTCHA-bypass logic are committed; all fixtures are synthetic. Day66 (durable
queue-backed permissioned Worker) is future work.
