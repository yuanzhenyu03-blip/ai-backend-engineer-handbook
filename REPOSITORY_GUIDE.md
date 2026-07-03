# REPOSITORY_GUIDE.md

# Repository Guide

This guide helps new AI assistants, developers, and future contributors understand how to work in this repository without redesigning it.

---

## Reading Order

Before making changes, read these files in order:

1. `README.md`
2. `ARCHITECTURE.md`
3. `AGENTS.md`
4. `PROJECT_STATUS.md`
5. `TASKS.md`
6. `CODING_STANDARD.md`
7. `CURRICULUM.md`
8. `LESSON_TEMPLATE.md`
9. `DECISIONS.md`
10. `REPOSITORY_GUIDE.md`
11. `TRAINING_WORKFLOW.md`

This order gives the contributor the mission, architecture, current progress, active tasks, coding standards, and curriculum context.

---

## Repository Philosophy

This repository is an AI Backend Engineer operating system.

It is not a random note collection.

GitHub is the single source of truth.

Every change should improve long-term engineering capability, interview readiness, or production-style portfolio quality.

Do not chase tools.

Build engineering capability.

---

## Folder Responsibilities

### `docs/`

Canonical lesson documents.

Lessons are organized by topic:

```text
docs/python/
docs/fastapi/
docs/playwright/
docs/docker/
docs/n8n/
```

### `projects/`

Production-style portfolio projects. Every project must have its own `README.md` and should eventually contain `src/`, `tests/`, `docs/`, `requirements.txt`, and `Dockerfile`.

### `interview/`

Interview question banks and model answers. `interview/python.md` is the template for future interview files.

### `cheat_sheets/`

One-page review sheets for fast interview preparation.

### `prompts/`

Reusable prompts for Codex, ChatGPT, review workflows, interview generation, and project generation.

### `assets/`

Images, diagrams, architecture sketches, and memory model visuals.

### `progress/`

Weekly and monthly learning progress logs.

### `templates/`

Reusable Markdown and project templates.

### `scripts/`

Automation scripts for repository maintenance.

---

## Daily Workflow

1. Read the current repository status.
2. Check `TASKS.md` for the active priority.
3. Create or update the requested lesson, project, interview file, or prompt.
4. Keep file names consistent and lowercase where possible.
5. Update internal references when paths change.
6. Update `PROJECT_STATUS.md`, `TASKS.md`, and `CHANGELOG.md` when work is completed.

---

## Repository Lifecycle

Each important repository file answers a different operational question.

### `ROADMAP.md`

Question:
Where are we going?

Role:
Defines the official long-term learning order from Python Foundations to Interview Preparation.

### `CURRICULUM.md`

Question:
How should each lesson be structured?

Role:
Defines the engineering curriculum format for the current lesson and future lessons.

### `PROJECT_STATUS.md`

Question:
Where are we right now?

Role:
Tracks the current phase, current lesson, today's goal, definition of done, and repository health.

### `TASKS.md`

Question:
What should we execute today?

Role:
Acts as the daily sprint board for lesson work, repository tasks, interview tasks, homework, blockers, backlog, and completed work.

### `CHANGELOG.md`

Question:
What changed over time?

Role:
Records meaningful repository updates so the training history remains visible.

### `DECISIONS.md`

Question:
Why did we choose this direction?

Role:
Records architecture and workflow decisions that should not be rediscovered repeatedly.

### `AGENTS.md`

Question:
How should AI coding assistants behave here?

Role:
Defines the operating rules for assistants working in this repository.

### `LESSON_TEMPLATE.md`

Question:
What standard must every lesson follow?

Role:
Defines the permanent lesson specification based on the released Day01 Gold Standard.

### `TRAINING_WORKFLOW.md`

Question:
How does a training day operate from teaching to GitHub push?

Role:
Defines the official daily workflow, weekly workflow, repository update order, and lesson release process.

---

## ChatGPT and Codex Collaboration

ChatGPT is the teacher and tech lead.

The student is the repository owner.

Codex is the junior AI backend engineer responsible for implementation, maintenance, documentation, and cleanup.

The collaboration flow is:

```text
ChatGPT -> Student -> Codex -> GitHub -> Notion
```

Chat is for teaching and discussion.

GitHub is the source of truth.

Notion is the reading and review layer.

---

## How Lessons Become Projects

Lessons explain concepts, engineering thinking, interview questions, and homework.

Projects convert those lessons into production-style implementation.

Example:

```text
Python object model lesson
-> python-fundamentals examples
-> Python interview answers
-> Python cheat sheet
```

A lesson is not complete until it can support code, interview explanation, and project work.

---

## How Projects Become Interview Preparation

Each project should produce:

- a clear problem statement
- architecture explanation
- implementation notes
- testing strategy
- deployment notes
- trade-off discussion
- interview-ready project story

Interview files should reuse project lessons without duplicating full project documentation.

---

## Maintenance Rules

- Preserve the existing architecture.
- Prefer improving existing files over creating duplicates.
- Keep naming consistent.
- Keep Markdown clean and readable.
- Avoid placeholder-only project directories.
- Do not create future knowledge-base folders until `TASKS.md` says to do so.
