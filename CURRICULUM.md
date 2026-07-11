# Curriculum

This file defines the official curriculum for the AI Backend Engineer Training Camp.

The curriculum is not a list of topics.

It is an engineering training plan. Every lesson must connect concept understanding, production risk, framework usage, coding practice, interview readiness, and repository updates.

---

## Phase 1 — Python Foundations

### Day01

Topic:
Python Object Model

Status:
✅ Completed

Released Lesson:
`docs/python/day01-object-model.md`

---

### Day02

Topic:
Mutable vs Immutable

Status:
✅ Completed

Difficulty:
Foundation

Estimated Study Time:
4-5 hours

Prerequisites:

- Day01 — Python Object Model
- Names, references, and object identity
- `==` vs `is`
- Mutable default argument bug

Learning Objectives:

- Understand mutable and immutable objects.
- Learn how object identity connects to mutability.
- Understand shallow copy vs deep copy.
- Explain why mutable default arguments are dangerous.
- Connect the concept to FastAPI and Playwright.

Key Concepts:

- Mutable objects
- Immutable objects
- Object identity
- Shared references
- Copy
- Deep copy
- Hashability

Engineering Thinking:

- Which objects are safe to share?
- Which objects should be copied?
- Which objects should be isolated per request or per job?
- How can hidden mutation create production bugs?

Deliverables:

- Day02 lesson document
- Python cheat sheet update
- Python interview notes update
- Coding exercises

Homework:

- Copy exercises
- `id()` experiments
- Memory diagrams

Mini Project:

Implement a simple object inspector.

Interview Focus:

- Explain mutable vs immutable objects.
- Explain shallow copy vs deep copy.
- Explain why tuple can be hashable but list cannot.
- Explain how shared mutable state causes backend bugs.

Repository Updates:

- `docs/python/day02-mutable-vs-immutable.md`
- `cheat_sheets/python.md`
- `interview/python.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

Related Lessons:

- Previous: Day01 — Python Object Model
- Next: Day03 — Functions & Parameter Passing

---

### Future Lesson Template

Every future lesson should follow this structure.

#### Day XX

Topic:

Difficulty:

Estimated Study Time:

Prerequisites:

Learning Objectives:

Key Concepts:

Engineering Thinking:

Deliverables:

Homework:

Mini Project:

Interview Focus:

Repository Updates:

Related Lessons:

---

### Day03

Topic:
Functions & Parameter Passing

Status:
✅ Completed

---

### Day04

Topic:
Scope & LEGB

Status:
✅ Completed

Difficulty:
Foundation

Estimated Study Time:
4-5 hours

Prerequisites:

- Day01 — Python Object Model
- Day02 — Mutable vs Immutable
- Day03 — Functions & Parameter Passing

Learning Objectives:

- Understand Python name lookup.
- Explain Local, Enclosing, Global, and Built-in scopes.
- Explain why scope matters in function design.
- Connect scope behavior to FastAPI, Playwright, and AI backend systems.

Key Concepts:

- Local scope
- Enclosing scope
- Global scope
- Built-in scope
- Name lookup
- Shadowing

Repository Updates:

- `docs/python/day04-scope-legb.md`
- `cheat_sheets/python.md`
- `interview/python.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

---

### Day05

Topic:
Closures

Status:
✅ Completed

Difficulty:
Foundation

Estimated Study Time:
4-5 hours

Prerequisites:

- Day01 — Python Object Model
- Day03 — Functions & Parameter Passing
- Day04 — Scope & LEGB

Learning Objectives:

- Understand closures as function objects with captured environments.
- Explain closure use cases in production Python.
- Connect closures to decorators, dependency factories, and AI backend prompt builders.

Key Concepts:

- Closure
- Captured environment
- Factory function
- State preservation
- Late binding review

Repository Updates:

- `docs/python/day05-closures.md`
- `cheat_sheets/python.md`
- `interview/python.md`
- `PROJECT_STATUS.md`
- `TASKS.md`
- `CHANGELOG.md`

---

### Day06

Topic:
Decorators

Status:
✅ Completed

---

### Day07

Topic:
Iterators & Generators

Status:
✅ Completed

---

### Day08

Topic:
Exception Handling

Status:
✅ Completed

---

### Day09

Topic:
Modules & Packages

Status:
✅ Completed

---

### Day10

Topic:
Type Hints

Status:
✅ Completed

---

### Day11

Topic:
Object-Oriented Programming

Status:
✅ Completed

---

### Day12

Topic:
Context Managers

Status:
✅ Completed

---

### Day13

Topic:
Async Programming

Status:
✅ Completed

---

### Day14

Topic:
Mini Project & Backend Architecture

Status:
✅ Completed

Released Lesson:
`docs/python/day14-mini-project.md`

---

## Phase 1 — Complete

All Day01–Day14 Python foundation lessons are completed.

---

## Phase 2 — Engineering Foundations

### Day15

Topic:
Git Fundamentals

Status:
✅ Completed

Released Lesson:
`docs/git/day15-git-fundamentals.md`

---

### Day16

Topic:
Git Branch & Merge

Status:
✅ Completed

Released Lesson:
`docs/git/day16-branch-and-merge.md`

---

### Day17

Topic:
GitHub Workflow & Collaboration

Status:
✅ Completed

Released Lesson:
`docs/git/day17-github-workflow.md`

---

### Day18

Topic:
Merge Strategy & Code Review

Status:
✅ Completed

Released Lesson:
`docs/git/day18-merge-strategy-and-code-review.md`

---

### Day19

Topic:
GitHub Project Management

Status:
✅ Completed

Released Lesson:
`docs/github/day19-project-management.md`

---

### Day20

Topic:
CI/CD Foundations

Status:
✅ Completed

Released Lesson:
`docs/devops/day20-ci-cd-foundations.md`

---

## DevOps Foundations (continued)

### Day21

Topic:
GitHub Actions Fundamentals

Topics:
Workflow, Trigger, Runner, GitHub-hosted Runner, Self-hosted Runner, Job, Step, Action
Marketplace, `uses`, `run`, Secrets, Environment Variables, Basic FastAPI CI

Status:
✅ Completed

Released Lesson:
`docs/devops/day21-github-actions-fundamentals.md`

Template:
LESSON_TEMPLATE_v2

---

### Day22

Topic:
GitHub Actions Advanced

Topics:
Matrix Build, Cache, Artifacts, Reusable Workflow, Composite Actions, Conditional Jobs,
Deployment Pipeline

Status:
Planned

---

## Container Engineering

### Day23

Topic:
Docker Fundamentals

Topics:
Container, Image, Layer, Dockerfile, Build, Run, Volume, Network

Status:
Planned

---

### Day24

Topic:
Docker Compose

Topics:
Multi-service, FastAPI + Redis, PostgreSQL, Environment, Local Development

Status:
Planned

---

## Production Engineering

### Day25

Topic:
Deployment Foundations

Topics:
Reverse Proxy, Nginx, SSL, Domain, CI/CD Deployment, Zero Downtime

Status:
Planned

---

### Day26

Topic:
Kubernetes Foundations

Topics:
Pod, Deployment, Service, ConfigMap, Secret

Status:
Planned

---

### Day27

Topic:
Kubernetes Workloads

Topics:
Ingress, Autoscaling, Rolling Update, StatefulSet, Helm

Status:
Planned

---

### Day28

Topic:
AI Backend Production Architecture

Topics:
FastAPI, Celery, Redis, PostgreSQL, Object Storage, Queue, Monitoring, Observability

Status:
Planned

---

## Why This Curriculum

Phase 2 follows the Software Delivery Lifecycle, not a list of tools:

```text
Git -> GitHub -> Project Management -> CI/CD -> GitHub Actions
    -> Docker -> Deployment -> Kubernetes -> Production AI Backend
```

Students first understand WHY before HOW. Every tool solves an engineering problem introduced in
previous lessons: Git manages code history, GitHub adds collaboration, project management makes
work visible, CI/CD automates quality and delivery, GitHub Actions implements the pipeline as
code, Docker makes environments reproducible, deployment and Kubernetes run it reliably in
production, and the final lesson assembles a production AI backend architecture.

Follow `ROADMAP.md` for the official learning order.

Do not fully expand future days until they become the current lesson.
