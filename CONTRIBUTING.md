# CONTRIBUTING.md

# Contributing Guide

This repository is a long-term AI Backend Engineer training system. Contributions should preserve the existing architecture and improve production-quality learning.

---

## Branch Naming

Use clear branch names:

```text
feat/<short-description>
fix/<short-description>
docs/<short-description>
refactor/<short-description>
chore/<short-description>
```

Examples:

```text
docs/python-day02-mutable-immutable
feat/fastapi-auth-skeleton
chore/update-task-board
```

---

## Commit Style

Use conventional prefixes:

```text
feat:
fix:
refactor:
docs:
test:
chore:
```

Examples:

```text
docs: add Python interview handbook
feat: add FastAPI auth skeleton
chore: update project status
```

---

## Markdown Conventions

- Use clear headings.
- Use fenced code blocks with language labels.
- Prefer short paragraphs.
- Keep lists consistent.
- Use lowercase kebab-case file names for lesson and guide files when possible.
- Keep internal links updated when files move.

---

## Lesson Conventions

Lessons must follow `LESSON_TEMPLATE.md`.

Every lesson should include:

- Learning Objectives
- Why This Matters
- Core Theory
- Memory Model
- Engineering Thinking
- Enterprise Practice
- Common Bugs
- Best Practice
- Code Examples
- Interview Questions
- Tech Lead Review
- CTO Thinking
- English for Interviews
- Cheat Sheet
- Homework
- Definition of Done
- Related Topics
- Notes

Lessons should explain WHY before HOW.

Lessons belong under `docs/<topic>/`.

---

## Project Conventions

Every project directory must include its own `README.md`.

Each project should eventually contain:

```text
README.md
requirements.txt
Dockerfile
src/
tests/
docs/
```

Each project README must explain:

- Goal
- Learning objectives
- Planned features
- Folder structure
- Progress
- Future milestones

Implementation should follow `CODING_STANDARD.md`.

---

## Pull Request Checklist

Before opening or merging a pull request, verify:

- Repository structure remains consistent.
- Existing conventions are followed.
- No duplicate files or folders were introduced.
- Markdown formatting is clean.
- Internal links are valid.
- Lessons follow `LESSON_TEMPLATE.md`.
- Projects include README files.
- Code uses type hints and follows `CODING_STANDARD.md`.
- `PROJECT_STATUS.md`, `TASKS.md`, and `CHANGELOG.md` are updated when needed.

---

## Review Process

Reviews should check:

- correctness
- clarity
- maintainability
- interview usefulness
- enterprise relevance
- consistency with repository architecture

Use `prompts/review.md` as the standard review guide.

---

## Non-Goals

Do not redesign the repository unless explicitly requested.

Do not create duplicate knowledge systems.

Do not skip roadmap phases.

Do not turn production projects into short demos.
