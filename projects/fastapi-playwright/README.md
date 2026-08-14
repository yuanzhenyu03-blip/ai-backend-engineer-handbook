# FastAPI Playwright

## Goal

Build an automation backend where FastAPI exposes API endpoints and Playwright performs browser tasks behind the service boundary.

## Learning Objectives

- Combine API design with browser automation.
- Manage browser lifecycle safely.
- Design async workflows and background jobs.
- Return reliable automation results through REST APIs.

## Planned Features

- Submit automation job
- Run Playwright browser task
- Store job status
- Return structured result
- Error recovery
- Tests for API and automation boundaries

## Folder Structure

```text
fastapi-playwright/
├── README.md
├── requirements.txt
├── Dockerfile
├── src/
├── tests/
└── docs/
```

## Progress

Status: Day62 reliable-interaction primitives added (EXECUTED_LOCAL_RUNTIME).

The first connected Day62 artifact lives under `src/`, `tests/` and `docs/`: a controlled
localhost HTTP research page, a pure interaction/cleanup decision core, and an async browser task
with explicit Browser/Context/Page ownership, stable role/test-id Locators, no fixed sleep or
`force=True`, and `finally` Context cleanup that preserves the primary operation error. Run the
pure-logic + HTTP-loopback + static reliability-contract tests with `python3 -m pytest -q tests/`
(= 13 passed, 1 skipped; only the real-Chromium suite is gated on the `playwright` package and skips
when it is absent). No extra setup is needed — `pytest.ini` sets `pythonpath = src` so the tests
import the modules under test directly. See
[`docs/day62-playwright-runtime-locators-and-reliable-async-interaction-design.md`](docs/day62-playwright-runtime-locators-and-reliable-async-interaction-design.md)
and the [Day62 lesson](../../docs/fastapi/day62-playwright-runtime-locators-and-reliable-async-interaction.md).

The Day63 artifact adds an authenticated, tenant-bound, revocable browser-session gate:
`src/day63_session_gate.py` (pure authorization/claim decision core — binding validation, atomic
claim, credential-load gating, positive-identity verification, Origin/security check, final fence,
storage-state allowlist filtering, and an orchestrator that proves the negative effects) and
`src/day63_controlled_login_page.py` (a synthetic loopback account page with account/redirect/
unapproved-origin modes). Run the Day63 suite with
`python3 -m pytest -q tests/test_day63_session_gate.py tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py`
(= 28 passed, 1 skipped; the real-Chromium isolation suite is gated on `playwright`). The LIVE
classroom artifact was `CONCEPTUAL_STATIC`; real PostgreSQL atomic claim, a credential/secret store,
and real Chromium isolation are NOT RUN. See the
[Day63 design/runbook](docs/day63-browser-authentication-storage-state-and-tenant-isolation-design.md)
and the [Day63 lesson](../../docs/fastapi/day63-browser-authentication-storage-state-and-tenant-isolation.md).

Current focus: authenticated, tenant-bound, revocable browser sessions (Day63); Day64 adds dynamic
extraction and artifact evidence from the authorized session. Earlier: Day62 reliable-interaction Context
isolation on this ownership model.

## Future Milestones

- Design job API.
- Add Playwright service wrapper.
- Add background execution.
- Add production error handling.
