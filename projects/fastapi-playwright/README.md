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
pure-logic + HTTP-loopback tests with `python3 -m pytest -q tests/` (the real-Chromium suite is
gated on the `playwright` package). See
[`docs/day62-playwright-runtime-locators-and-reliable-async-interaction-design.md`](docs/day62-playwright-runtime-locators-and-reliable-async-interaction-design.md)
and the [Day62 lesson](../../docs/fastapi/day62-playwright-runtime-locators-and-reliable-async-interaction.md).

Current focus: reliable async interaction primitives; Day63 adds tenant-authenticated Context
isolation on this ownership model.

## Future Milestones

- Design job API.
- Add Playwright service wrapper.
- Add background execution.
- Add production error handling.
