# ARCHITECTURE.md

# Repository Architecture

This repository is designed as an AI Backend Engineer operating system.

It is not only a learning notebook. It is a long-term engineering knowledge base that can be used by the student, ChatGPT, Codex, and other AI coding assistants.

---

## Core Idea

GitHub is the single source of truth.

Chat is used for discussion and teaching.

Notion is used for reading and review.

Codex is used for implementation and project work.

---

## Root Files

### `README.md`

High-level project introduction.

### `AGENTS.md`

Rules for AI assistants working in this repository.

### `PROJECT_STATUS.md`

Current learning status and next lesson.

### `TASKS.md`

Current work queue and task board.

### `CURRICULUM.md`

The full training roadmap.

### `CODING_STANDARD.md`

Engineering coding standards for all projects.

### `LESSON_TEMPLATE.md`

Standard format for every lesson.

### `CHANGELOG.md`

Versioned history of changes.

### `DECISIONS.md`

Important technical and curriculum decisions.

### `ROADMAP.md`

Career and learning path from Python to overseas AI Backend work.

### `GLOSSARY.md`

Technical vocabulary and English interview terms.

### `REPOSITORY_GUIDE.md`

Practical guide for new AI assistants and developers working in the repository.

### `CONTRIBUTING.md`

Contribution rules for branches, commits, Markdown, lessons, projects, and reviews.

---

## Directories

### `docs/`

Canonical final lesson documents.

Lessons are organized by topic.

Example:

```text
docs/python/day01-object-model.md
```

Do not create duplicate course folders outside `docs/`.

### `projects/`

Production-style coding projects. Every project directory must contain its own `README.md`.

### `interview/`

Interview question banks and model answers. `interview/python.md` is the template for future interview documents.

### `cheat_sheets/`

One-page review notes for interview preparation.

### `prompts/`

Reusable prompts for Codex, ChatGPT, interview generation, project generation, and review workflows.

### `progress/`

Weekly and monthly learning progress logs.

### `assets/`

Images, diagrams, architecture sketches, and memory model visuals.

Recommended structure:

```text
assets/images/
assets/diagrams/
assets/architecture/
assets/memory-model/
```

### `templates/`

Reusable Markdown and project templates.

### `scripts/`

Automation scripts for the repository.

---

## Workflow

1. Learn through conversation.
2. Convert discussion into a final Markdown lesson.
3. Store the lesson under `docs/<topic>/`.
4. Update `PROJECT_STATUS.md`.
5. Update `TASKS.md`.
6. Update `CHANGELOG.md`.
7. Use Codex to implement projects under `projects/`.
8. Convert projects into interview stories under `interview/` and quick review notes under `cheat_sheets/`.

---

## AI Handoff Order

Any AI assistant should read files in this order:

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

Only after reading these files should the assistant begin coding or writing lessons.
