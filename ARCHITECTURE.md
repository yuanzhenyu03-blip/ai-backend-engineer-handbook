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

---

## Directories

### `docs/`

Final lesson documents.

Example:

```text
docs/day01-python-object-model.md
```

### `projects/`

Production-style coding projects.

### `interview/`

Interview question banks and model answers.

### `cheat_sheets/`

One-page review notes.

### `prompts/`

Reusable prompts for Codex, ChatGPT, and other AI assistants.

### `progress/`

Weekly and monthly learning progress logs.

### `assets/`

Diagrams, images, architecture sketches, and screenshots.

### `templates/`

Reusable Markdown and project templates.

### `scripts/`

Automation scripts for the repository.

---

## Workflow

1. Learn through conversation.
2. Convert discussion into a final Markdown lesson.
3. Store the lesson under `docs/`.
4. Update `PROJECT_STATUS.md`.
5. Update `TASKS.md`.
6. Update `CHANGELOG.md`.
7. Use Codex to implement projects under `projects/`.

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

Only after reading these files should the assistant begin coding or writing lessons.
