# LESSON_TEMPLATE_v2.md

# Lesson {{DAY}} — {{TITLE}}

This is the official lesson standard for the AI Backend Engineer Handbook, version 2.

Beginning with Day21, new lessons should use `LESSON_TEMPLATE_v2.md`.

Older lessons (Day01–Day20) remain valid and do not require migration. The original
`LESSON_TEMPLATE.md` is kept for backward compatibility.

---

## Why v2 Exists

The repository evolved significantly through Day15–Day20. It now teaches engineering thinking,
not syntax, and covers Git, GitHub, CI/CD, containers, deployment, Kubernetes, and AI backend
architecture — not only Python.

Version 2 makes the template reflect the actual classroom process rather than a traditional
documentation structure. It must support:

* WHY before HOW
* Classroom interaction
* Engineering reasoning
* Production thinking
* AI Backend thinking
* Overseas interview preparation
* The full software engineering workflow

The strengths of v1 are preserved: explain WHY before HOW, engineering thinking, roadmap
position, lesson map, interview preparation, today's takeaway, checklist, ASCII diagrams,
trade-offs, and production examples. Version 2 improves the structure; it does not remove these.

---

# Lesson Workflow

Every lesson is the written record of a classroom-style engineering process, not standalone
textbook writing.

```text
Tech Lead teaches
        |
        v
Student learns
        |
        v
Student builds the appropriate engineering artifact
        |
        v
Repository Coding Agent generates documentation
        |
        v
Tech Lead / ChatGPT reviews
        |
        v
Repository updates
```

Preserve the important classroom discussions, questions, mistakes, corrections, and engineering
decisions that happened during learning. Write as if a senior engineer is guiding a junior
engineer: checking understanding, connecting to production, and preparing for interviews.

---

# Writing Principles

* Explain WHY before HOW.
* Teach engineering thinking, not only syntax or commands.
* Start every topic from the mental model, then the details.
* Prefer production examples over toy examples.
* Avoid textbook style; keep it conversational and precise.
* Connect every lesson to real backend and AI systems.
* Show trade-offs, not only correct answers.
* Include common misconceptions and why they happen.
* Use diagrams when the mental model matters.
* Make interview readiness part of the lesson, not an afterthought.
* Use the most appropriate engineering artifact; do not assume Python.

---

# AI Collaboration

The repository is maintained through a clear, future-proof collaboration model. Do not hardcode
a specific coding agent.

```text
ChatGPT
   |
Teaching
   |
   v
Repository Coding Agent
(Claude Code / Codex / any capable agent)
   |
Repository Update
   |
   v
ChatGPT Review
   |
   v
Repository Improvement
```

* Teaching model (e.g. ChatGPT): acts as Tech Lead — teaches interactively, asks follow-up
  questions, reviews understanding and generated documentation, preserves engineering depth,
  and prepares the student for overseas interviews.
* Repository coding agent (e.g. Claude Code or Codex): acts as the junior AI backend engineer
  inside the repository — generates lessons, maintains structure and consistency, and updates
  related files following repository conventions.
* GitHub: the single source of truth — stores lessons, projects, interview material, and cheat
  sheets, and preserves history through commits.

The collaboration flow should always improve the repository, not create isolated notes.

---

# Required Lesson Structure

Every v2 lesson must include these sections in this exact order:

1. Lesson Metadata
2. Learning Objectives
3. Why This Matters
4. Roadmap Position
5. Lesson Map
6. Core Mental Model
7. Main Concepts
8. Common Misconceptions
9. Engineering Trade-offs
10. Hands-on Exercises
11. Relevant Framework Connections
12. AI Backend Connections
13. English Interview
14. Mental Model Summary
15. Today's Takeaway
16. Before Next Lesson Checklist

---

# 1. Lesson Metadata

Required. A short header block identifying the lesson.

Include:

```text
Release Badge / Status
Version
Difficulty
Estimated Time
Prerequisite
Next Lesson
```

---

# 2. Learning Objectives

Required.

After completing this lesson, the student should be able to:

* Explain the concept in plain English.
* Explain why the concept exists.
* Explain how the concept appears in backend and AI systems.
* Apply the concept through the appropriate engineering artifact.
* Connect the concept to the relevant technologies for this topic.
* Answer beginner, intermediate, and senior interview questions.

Note: "apply the concept" does not mean Python code. It means the appropriate engineering
artifact for the topic — Python, YAML, Shell, a Dockerfile, a Kubernetes manifest, a GitHub
workflow, an infrastructure configuration, or an architecture diagram.

---

# 3. Why This Matters

Required.

Explain why the topic matters before explaining how it works.

Answer:

* Why should a backend engineer care?
* What production problems does this topic prevent?
* How does it appear in real engineering work?
* How will it appear later in the roadmap?

Start with engineering motivation, not syntax.

---

# 4. Roadmap Position

Required.

Explain where this lesson sits in the full roadmap: previous lesson connection, current focus,
next lesson connection, and future connections. Use an ASCII diagram when helpful.

```text
Previous Lesson
      |
      v
Today's Concept
      |
      v
Future Usage (frameworks, DevOps, AI backend)
      |
      v
Interview Readiness
```

---

# 5. Lesson Map

Required.

Show today's learning path concisely, so the student sees the structure before reading.

---

# 6. Core Mental Model

Required. This section is new in v2 and mandatory.

Every lesson must present the core mental model BEFORE explaining syntax or details. The student
should understand the model first.

Use a short diagram or equation.

Examples:

```text
Git:    Commit -> Immutable Snapshot
GitHub: PR -> Review -> CI -> Merge
CI:     Developer -> Commit -> Pipeline -> Quality Gate -> Production
Docker: Image -> Container -> Runtime
```

Explain the model in one or two sentences, then let the Main Concepts build on it.

---

# 7. Main Concepts

Required.

Every important concept must follow the classroom loop, not a flat "explain A, explain B"
structure. This reflects the real classroom process.

For each major concept:

```markdown
## Concept N: {{Name}}

Tech Lead Question:

{{a question that motivates the concept}}

Student Thinking:

{{the student's reasoning, guesses allowed}}

Student Answer:

{{the student's real answer}}

Tech Lead Review:

{{derive WHY the design works this way, correcting as needed}}

Engineering Thinking:

{{the underlying engineering principle}}

Production Example:

{{a realistic production example}}

Framework Connection:

{{how it appears in the relevant technology for this topic}}

Exercise:

{{a small check or task tied to this concept, optional if a later Hands-on section covers it}}
```

Complete this loop for every important concept. Include ASCII diagrams and progressive examples
from simple to realistic.

---

# 8. Common Misconceptions

Required. New in v2.

Directly address interview mistakes and beginner misunderstandings.

Use a clear wrong-vs-right format:

```markdown
{{Topic}}
❌ {{the common wrong belief}}
✅ {{the correct engineering understanding}}
```

Examples:

```text
Git Branch
❌ Branch is a copy
✅ Branch is a movable reference

CI
❌ CI means automated testing
✅ CI establishes trusted integration

Docker
❌ Container is a virtual machine
✅ Container is an isolated process
```

---

# 9. Engineering Trade-offs

Required. Trade-offs now have a dedicated section.

Every lesson must explicitly answer:

* Why was this design chosen?
* What alternatives exist?
* What does this improve?
* What does it sacrifice?

Present trade-offs as explicit comparisons.

Examples:

```text
Merge Commit vs Squash Merge
Workflow as Code vs Documentation
Hosted Runner vs Self-hosted Runner
Docker vs Virtual Machine
```

---

# 10. Hands-on Exercises

Required.

Exercises should use the most appropriate engineering artifact — do not assume Python.

Supported exercise types include:

```text
Python
YAML
Shell
Dockerfile
GitHub Actions workflow
Terraform / Infrastructure config
Kubernetes manifest
Architecture diagram
System design
Production debugging
```

Each exercise should follow:

```markdown
Question:

Think First:

Starter Artifact:

Expected Output:

Explanation:

Follow-up Question:
```

Exercises should become progressively harder and test the mental model, not just recall.

---

# 11. Relevant Framework Connections

Required. This replaces the fixed "FastAPI Connections" and "Playwright Connections" sections.

Choose only the technologies relevant to the topic. Do not force Playwright (or any single tool)
into every lesson.

Possible connections:

```text
FastAPI, Playwright, Docker, Redis, PostgreSQL, Celery,
GitHub Actions, Kubernetes, Terraform, Prompt Engineering,
MCP, OpenAI API, Vector Database
```

For each chosen technology, explain how today's concept appears in it and what a production
engineer should watch for.

---

# 12. AI Backend Connections

Required. A first-class section, not scattered notes.

Explain how today's concept appears in production AI systems.

Possible topics:

```text
Prompt, Agent, Memory, RAG, Evaluation, Tool Calling,
Queue, Embedding, Vector Database, Observability,
Token Cost, Security, Monitoring, Production Deployment
```

Use realistic AI backend examples that connect the lesson to shipping real AI systems.

---

# 13. English Interview

Required.

Support overseas interviews with key vocabulary, concise example answers, and beginner,
intermediate, and senior questions. Keep answers practical and grounded in engineering
reasoning.

---

# 14. Mental Model Summary

Required. New in v2.

Finish the lesson with concise engineering principles the student can review quickly (e.g. on a
later review day).

Examples:

```text
Commit           = Immutable Snapshot
Branch           = Movable Reference
CI               = Trusted Quality Process
Pipeline         = Standard Workflow
Quality Gate     = Risk Control
CD               = Reliable Delivery
Workflow as Code = Everything as Code
```

---

# 15. Today's Takeaway

Required.

Summarize the lesson as engineering principles, not only facts. Include the most important
mental model, the most important production risk, the most important framework/AI connection,
and the most important interview answer.

---

# 16. Before Next Lesson Checklist

Required.

A checkbox list the student should be able to answer without looking at the notes, preparing
them for the next lesson.

```markdown
- [ ] Can I explain the core mental model in plain English?
- [ ] Can I explain why this design exists?
- [ ] Can I identify the common misconception?
- [ ] Can I explain the main engineering trade-off?
- [ ] Can I connect the topic to a real framework and to AI backend systems?
- [ ] Can I answer an interview question about it in English?
```

---

# Definition of an Excellent Lesson

A lesson is excellent only when the student can:

* Explain the core mental model.
* Explain why the concept exists.
* Apply the concept through the appropriate engineering artifact.
* Identify the common misconception and correct it.
* Explain the engineering trade-off.
* Connect the topic to relevant frameworks and to AI backend systems.
* Answer beginner, intermediate, and senior interview questions.
* Teach the concept to another engineer.

If the student can only repeat definitions, the lesson is not finished.

---

# Compatibility

This template is designed to support every planned Phase 2 topic and beyond:

```text
Git, GitHub, CI/CD, GitHub Actions, Docker, Docker Compose,
Deployment (Nginx, SSL, zero downtime), Kubernetes,
and Production AI Backend Architecture.
```

Because Relevant Framework Connections and Hands-on Exercises are technology-agnostic, the same
structure works for a Python lesson, a YAML/GitHub Actions lesson, a Dockerfile lesson, a
Kubernetes manifest lesson, or a system-design lesson.

---

# Backward Compatibility

* Day01–Day20 lessons remain valid and do not require migration.
* `LESSON_TEMPLATE.md` (v1) is preserved for those lessons.
* Beginning with Day21, new lessons should follow `LESSON_TEMPLATE_v2.md`.
