# Training Workflow

This document is the official operating manual for the AI Backend Engineer Training Camp.

The goal is to make the repository stable enough that every future lesson can follow the same workflow without redesign.

GitHub is the single source of truth.

---

# Purpose

The training camp exists to build production-ready AI backend engineering ability.

The repository should grow lesson by lesson:

```text
Lesson
  |
  v
Coding Practice
  |
  v
Documentation
  |
  v
Interview Preparation
  |
  v
Portfolio Evidence
```

The repository is not a notebook dump.

It is the permanent engineering record of the training process.

---

# Daily Workflow

Every training day follows the same flow:

```text
ChatGPT Teaching
        |
        v
Coding Practice
        |
        v
Codex Documentation
        |
        v
ChatGPT Review
        |
        v
Git Commit
        |
        v
GitHub Push
        |
        v
Next Lesson
```

Daily work should update the repository, not only the chat.

At the end of each day, the repository should show what was learned, what was practiced, and what remains next.

---

# Weekly Workflow

At the end of each week:

1. Review completed lessons.
2. Review project progress.
3. Review interview notes.
4. Review cheat sheets.
5. Check unfinished homework.
6. Update status files.
7. Commit and push all repository updates.

Weekly review prevents the repository from drifting away from the real training progress.

---

# How ChatGPT Is Used

ChatGPT acts as the Tech Lead and teacher.

Responsibilities:

- Teach concepts interactively.
- Ask follow-up questions.
- Explain why designs exist.
- Connect lessons to FastAPI, Playwright, and AI systems.
- Review student understanding.
- Review generated documentation.
- Decide when a lesson is ready to release.

ChatGPT is responsible for teaching quality and engineering judgment.

---

# How Codex Is Used

Codex acts as the repository engineer.

Responsibilities:

- Generate lesson documents.
- Maintain repository files.
- Keep Markdown consistent.
- Update `docs`, `interview`, `cheat_sheets`, and `projects`.
- Preserve the existing architecture.
- Commit and push completed work when requested.

Codex should not redesign the repository unless explicitly instructed.

---

# How GitHub Is Used

GitHub is the single source of truth.

GitHub stores:

- Released lessons
- Project work
- Interview notes
- Cheat sheets
- Repository standards
- Training progress
- Change history

Chat history is useful for teaching, but GitHub is the official record.

---

# Definition of Done

A training day is complete only if:

- Lesson finished
- Exercises completed
- Repository updated
- Git committed
- Git pushed
- Ready for next lesson

If the repository is not updated, the training day is not complete.

---

# Repository Update Order

Use this order when finishing a lesson:

1. Update the lesson in `docs/`.
2. Update the matching cheat sheet in `cheat_sheets/`.
3. Update the matching interview notes in `interview/`.
4. Update relevant project notes in `projects/`.
5. Update `PROJECT_STATUS.md`.
6. Update `TASKS.md`.
7. Update `CHANGELOG.md`.
8. Commit changes.
9. Push to GitHub.

This order keeps learning, practice, interview readiness, and history synchronized.

---

# Lesson Release Process

Every lesson should move through this lifecycle:

```text
Draft
  |
  v
Codex Generation
  |
  v
ChatGPT Review
  |
  v
Repository Polish
  |
  v
Released
```

Release criteria:

- The lesson follows `LESSON_TEMPLATE.md`.
- The lesson explains why before how.
- The lesson includes engineering thinking.
- The lesson includes classroom exercises.
- The lesson connects to FastAPI and Playwright.
- The lesson includes interview preparation.
- Related repository files are updated.

Released lessons become part of the permanent handbook.
