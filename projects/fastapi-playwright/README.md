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

Status: Planned

Current focus: complete FastAPI and Playwright fundamentals first.

## Future Milestones

- Design job API.
- Add Playwright service wrapper.
- Add background execution.
- Add production error handling.
