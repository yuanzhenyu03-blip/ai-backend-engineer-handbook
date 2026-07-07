# CHANGELOG.md

All notable changes to this repository will be documented in this file.

This project follows a practical versioning style:

- `v0.x.x` — training system under construction
- `v1.0.0` — first complete AI Backend Engineer Handbook release

---

## v0.1.12 — Day08 Exception Handling Polish

Date: 2026-07-07

### Changed

- Polished the Day08 completion badge in `docs/python/day08-exception-handling.md`.
- Preserved classroom code review examples for `divide(a, b)` and `check_age(age)`.
- Improved Playwright timeout specificity by using `PlaywrightTimeoutError`.
- Added Day08 Tech Lead Advice after Today's Takeaway.
- Added a Day08 system design interview question for AI Backend exception handling.
- Added a cheat sheet note about framework-specific exception classes.

### Notes

- Did not rewrite Day08.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.11 — Day08 Exception Handling Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day08-exception-handling.md`.
- Added Day08 exception handling review material to `cheat_sheets/python.md`.
- Added Day08 interview questions with overseas AI Backend engineering answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day08 as completed and Day09 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day08 as completed and prepare Day09.
- Updated `TASKS.md` with completed Day08 tasks and Day09 preparation tasks.
- Updated `CHANGELOG.md` with the Day08 repository update.

### Notes

- Covered `try / except`, precise exception handling, `ZeroDivisionError`, exception control flow, exception propagation, `raise`, custom exceptions, and exception chaining.
- Added `InvalidPromptError`, `LLMRequestError`, `ToolExecutionError`, and `RateLimitError` error-design examples.
- Connected Day08 concepts to FastAPI `HTTPException`, Playwright timeout recovery, and AI backend failure handling.
- No `exercises/` directory exists, so Day08 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.10 — Day07 Classroom Polish

Date: 2026-07-06

### Changed

- Enhanced `docs/python/day07-iterators-generators.md` with additional classroom reasoning, Tech Lead questions, and production bug examples.
- Enhanced `cheat_sheets/python.md` with a Day07 production risk table.
- Enhanced `interview/python.md` with senior-level Day07 questions about accidental generator consumption and shared state.

### Notes

- Added the principle: Data can be shared, state should not be shared.
- Added production bug examples for `list(generator)`, `sum(generator)`, and LLM stream debugging.
- Strengthened Pipeline vs Batch and AI token streaming explanations.
- Confirmed Day07 remains completed and Day08 remains the current lesson.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.9 — Day07 Iterators and Generators Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day07-iterators-generators.md`.
- Added Day07 iterator, generator, lazy evaluation, and streaming review material to `cheat_sheets/python.md`.
- Added Day07 interview questions with standard answers, follow-up questions, and engineering perspectives to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day07 as completed and Day08 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day07 as completed and prepare Day08.
- Updated `TASKS.md` with completed Day07 tasks and Day08 preparation tasks.
- Updated `CHANGELOG.md` with the Day07 repository update.

### Notes

- Covered Iterable, Iterator, `iter()`, `next()`, `StopIteration`, Generator, `yield`, generator lifecycle, lazy evaluation, generator expression, and `yield from`.
- Covered why `StopIteration` does not return `None`, why iterable and iterator are separated, and why generators are pausable and resumable data-flow models.
- Added streaming connections for FastAPI `StreamingResponse`, Playwright data pipelines, and AI backend token streaming.
- No `exercises/` directory exists, so Day07 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.8 — Day06 Decorators Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day06-decorators.md`.
- Added Day06 decorator review material to `cheat_sheets/python.md`.
- Added Day06 interview questions, Chinese explanations, English answers, and overseas interview answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day06 as completed and Day07 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day06 as completed and prepare Day07.
- Updated `TASKS.md` with completed Day06 tasks and Day07 preparation tasks.
- Updated `CHANGELOG.md` with the Day06 repository update.

### Notes

- Covered decorator motivation, cross-cutting concerns, wrapper functions, universal decorators, and `functools.wraps`.
- Covered metadata preservation for `__name__`, `__doc__`, `__annotations__`, and signature/reflection behavior.
- Added production examples for logging, timing, retry, authentication, cache, token tracking, and AI request tracing.
- Connected Day06 concepts to FastAPI route decorators, Playwright retry decorators, and AI backend observability.
- No `exercises/` directory exists, so Day06 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.7 — Day05 Closures Documentation

Date: 2026-07-06

### Added

- Added `docs/python/day05-closures.md`.
- Added Day05 Closure Engineering Notes to `cheat_sheets/python.md`.
- Added Factory Function, Closure vs Class, and Late Binding review material to `cheat_sheets/python.md`.
- Added Day05 interview questions, Chinese explanations, English answers, overseas backend answers, and follow-up questions to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day05 as completed and Day06 as the current lesson.
- Adjusted `docs/python/day05-closures.md` so required sections remain in the official template order.
- Updated `PROJECT_STATUS.md` to mark Day05 as completed.
- Updated `TASKS.md` with completed Day05 tasks and Day06 preparation tasks.

### Notes

- Covered Closure as Function Object plus Captured Environment.
- Covered captured environment, state preservation, `nonlocal`, `UnboundLocalError`, factory functions, Closure vs Class, and Late Binding.
- Connected Day05 concepts to FastAPI dependency factories, Playwright configuration factories, and AI prompt builders.
- No `exercises/` directory exists, so Day05 exercises are included in the lesson document.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.6 — Day04 Scope and LEGB Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day04-scope-legb.md`.
- Added Day04 LEGB, scope, closure, and late binding review material to `cheat_sheets/python.md`.
- Added Day04 interview questions and English answers to `interview/python.md`.

### Changed

- Updated `CURRICULUM.md` to mark Day04 as completed and Day05 as the current lesson.
- Updated `PROJECT_STATUS.md` to mark Day04 as completed.
- Updated `TASKS.md` with completed Day04 tasks and Day05 preparation tasks.

### Notes

- Covered lexical scope, `global`, `nonlocal`, mutation vs rebinding, closure, and late binding.
- Connected Day04 concepts to FastAPI, Playwright, and AI backend engineering.

---

## v0.1.5 — Day03 Functions and Parameter Passing Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day03-functions-parameter-passing.md`.
- Added Day03 function parameter passing review material to `cheat_sheets/python.md`.
- Added Day03 interview questions and English answers to `interview/python.md`.

### Changed

- Updated `PROJECT_STATUS.md` to mark Day03 as completed.
- Updated `TASKS.md` with completed Day03 tasks and Day04 preparation tasks.

### Notes

- Did not modify `CURRICULUM.md`.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.
- No `exercises/` directory exists, so Day03 exercises are included in the lesson document.

---

## v0.1.4 — Day02 Mutable vs Immutable Documentation

Date: 2026-07-03

### Added

- Added `docs/python/day02-mutable-vs-immutable.md`.
- Added Day02 mutable vs immutable review material to `cheat_sheets/python.md`.
- Added Day02 interview questions to `interview/python.md`.

### Changed

- Updated `PROJECT_STATUS.md` to mark Day02 as completed.
- Updated `TASKS.md` with completed Day02 tasks, review tasks, and Day03 preparation tasks.

### Notes

- Did not modify Day01 technical content.
- Did not modify `ROADMAP.md`.
- Did not modify `TRAINING_WORKFLOW.md`.
- Did not modify `LESSON_TEMPLATE.md`.

---

## v0.1.3 — Release Candidate Workflow Stabilization

Date: 2026-07-03

### Added

- Added `TRAINING_WORKFLOW.md` as the official training operating manual.
- Added daily learning workflow to `README.md`.
- Added repository lifecycle guidance to `REPOSITORY_GUIDE.md`.
- Added Today's Goal and Definition of Done to `PROJECT_STATUS.md`.

### Changed

- Updated `CURRICULUM.md` into a reusable engineering curriculum format.
- Redesigned `TASKS.md` as the daily execution sprint board.
- Updated repository guidance so future lessons follow one stable workflow.

### Notes

- Day01 technical content was not changed.
- Folder structure was not changed.
- Lesson template was not changed.

---

## v0.1.2 — Repository Cleanup and Structure Alignment

Date: 2026-07-02

### Added

- Added topic-based lesson structure under `docs/`.
- Added project README files for every project directory.
- Added `interview/python.md` as the template for future interview handbooks.
- Added `cheat_sheets/python.md` as the template for future cheat sheets.
- Added `prompts/interview.md`.
- Added `prompts/project.md`.
- Added `REPOSITORY_GUIDE.md`.
- Added `CONTRIBUTING.md`.
- Added assets subdirectories for images, diagrams, architecture, and memory models.

### Changed

- Moved Day 1 final lesson to `docs/python/day01-object-model.md`.
- Updated architecture references to use `docs/<topic>/`.
- Updated Codex prompt to use topic-based lesson paths.
- Updated `PROJECT_STATUS.md` and `TASKS.md` for Day 2 readiness.

### Removed

- Removed duplicated Day 1 course structure outside canonical `docs/` organization.

### Future

- Reserved a future `knowledge/` structure in `TASKS.md` without creating it yet.

---

## v0.1.1 — Project Management Layer

Date: 2026-07-02

### Added

- Added `TASKS.md`.
- Added `ARCHITECTURE.md`.
- Added `CHANGELOG.md`.
- Added `DECISIONS.md`.
- Added `ROADMAP.md`.
- Added `GLOSSARY.md`.

### Next

- Add repository directory skeleton.
- Add first final lesson under `docs/`.

---

## v0.1.0 — Repository Foundation

Date: 2026-07-02

### Added

- Created core repository concept.
- Added `README.md`.
- Added `AGENTS.md`.
- Added `PROJECT_STATUS.md`.
- Added `CURRICULUM.md`.
- Added `CODING_STANDARD.md`.
- Added `LESSON_TEMPLATE.md`.

### Learning Progress

- Completed Day 1 discussion.
- Covered Python Object Model.
- Covered Function Objects.
- Covered Callable Objects.
- Covered References.
- Covered `==` vs `is`.
- Covered Mutable Default Argument bug.
