# LESSON_TEMPLATE.md

# Lesson {{DAY}} — {{TITLE}}

This template is the official standard for every future lesson in the AI Backend Handbook.

Every lesson must follow the required sections below in order.

The goal is not to create class notes.

The goal is to create a publication-quality handbook chapter that teaches engineering thinking, prepares the student for overseas interviews, and connects each topic to real backend systems.

---

# Lesson Workflow

Every lesson should reflect the real training workflow.

The handbook is not standalone textbook writing.

It is the written record of a classroom-style engineering process:

```text
Tech Lead teaches
        |
        v
Student learns
        |
        v
Student codes
        |
        v
Codex generates documentation
        |
        v
ChatGPT reviews
        |
        v
Repository updates
```

The lesson should preserve the important classroom discussions, questions, mistakes, corrections, and engineering decisions that happened during learning.

Do not write as if the topic appeared from nowhere.

Write as if a senior engineer is guiding a junior engineer through the concept, checking understanding, connecting it to production systems, and preparing the student for interviews.

---

# Writing Principles

Every lesson must follow these writing principles.

* Explain WHY before HOW.
* Teach engineering thinking, not only syntax.
* Prefer production examples over toy examples.
* Avoid textbook style.
* Keep explanations conversational and precise.
* Connect every lesson to FastAPI, Playwright, and AI systems.
* Show trade-offs, not only correct answers.
* Include common mistakes and why they happen.
* Use diagrams when the mental model matters.
* Make interview readiness part of the lesson, not a separate afterthought.

The student should feel like they are learning from a tech lead, not reading disconnected notes.

---

# Definition of an Excellent Lesson

An excellent lesson is complete only when the student can:

* Explain the concept clearly.
* Explain why the concept exists.
* Apply the concept in code.
* Explain production risks.
* Connect the concept to frameworks.
* Connect the concept to AI backend systems.
* Pass beginner, intermediate, and senior interview questions.
* Teach the concept to another engineer.

If the student can only repeat definitions, the lesson is not finished.

If the student can explain the design trade-offs and apply the idea in a real backend system, the lesson is working.

---

# AI Collaboration

The repository is maintained through a clear collaboration model.

## ChatGPT

ChatGPT acts as the Tech Lead and teacher.

Responsibilities:

* Teach concepts interactively.
* Ask follow-up questions.
* Review student understanding.
* Review generated documentation.
* Preserve engineering depth.
* Make sure lessons prepare the student for overseas interviews.

## Codex

Codex acts as the Junior AI Backend Engineer working inside the repository.

Responsibilities:

* Generate lesson documents.
* Maintain repository structure.
* Keep documentation consistent.
* Create examples, exercises, interview material, and cheat sheets.
* Update related repository files when lessons evolve.
* Follow repository conventions instead of inventing a new structure.

## GitHub

GitHub is the single source of truth.

Responsibilities:

* Store lessons.
* Store project work.
* Store interview preparation material.
* Store cheat sheets.
* Preserve history through commits.
* Make the portfolio visible and reviewable.

The collaboration flow should always improve the repository, not create isolated notes outside the source of truth.

---

# Required Lesson Structure

Every lesson must include these sections in this exact order:

1. Why This Matters
2. Roadmap Position
3. Lesson Map
4. Estimated Study Time
5. Main Concepts
6. Engineering Thinking
7. Classroom Exercises
8. FastAPI Connections
9. Playwright Connections
10. English Interview
11. Today's Takeaway
12. Before Next Lesson Checklist

---

# Lesson {{DAY}} — {{TITLE}}

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain the concept in plain English.
* Explain why the concept exists.
* Explain how the concept appears in backend engineering.
* Apply the concept in Python code.
* Connect the concept to FastAPI, Playwright, and AI Agent systems.
* Answer beginner, intermediate, and senior-level interview questions.

---

# Why This Matters

Required for every lesson.

Explain why this topic matters before explaining how it works.

Answer:

* Why should a backend engineer care?
* What production bugs does this topic help prevent?
* How does this topic appear in real engineering work?
* How will it appear later in FastAPI, Playwright, Docker, Redis, PostgreSQL, or AI Agents?

The tone should feel like a tech lead explaining why the topic deserves attention.

Do not start with syntax.

Start with engineering motivation.

---

# Roadmap Position

Required for every lesson.

Explain where this lesson sits in the full roadmap.

Include:

* Previous lesson connection
* Current lesson focus
* Next lesson connection
* Future framework connections

Use an ASCII diagram when helpful.

Example:

```text
Previous Lesson
        |
        v
Today's Concept
        |
        v
FastAPI / Playwright / AI Agent Usage
        |
        v
Interview Readiness
```

The student should understand why this lesson belongs exactly here.

---

# Lesson Map

Required for every lesson.

Show today's learning path.

Keep it concise.

Example:

```text
Today's Lesson

1. Why This Matters
2. Core Mental Model
3. Main Concept 1
4. Main Concept 2
5. Common Bugs
6. FastAPI Connections
7. Playwright Connections
8. Interview Review
9. Today's Takeaway
```

The map should help the student see the structure before reading the full chapter.

---

# Estimated Study Time

Required for every lesson.

Provide realistic time estimates.

Example:

```text
Reading: 90-120 minutes
Exercises: 60-90 minutes
Coding: 45-60 minutes
Review: 30-45 minutes

Total: 4-5 hours
```

Adjust the numbers based on lesson difficulty.

---

# Main Concepts

Required for every lesson.

Explain the core theory.

This section replaces textbook-style explanation with engineering-oriented explanation.

For each major concept, explain:

* What it is
* Why it exists
* How it works
* What trade-offs it creates
* Where it appears in real backend work

Include:

* ASCII diagrams
* Code examples
* Progressive examples from simple to realistic
* Common misunderstandings

Use clear headings for each major concept.

Example:

```markdown
## Concept 1

Explain the idea.

## Concept 2

Explain the next idea.
```

When the lesson involves memory, lifecycle, requests, tasks, queues, browser state, or database state, include a memory model or state diagram.

---

# Engineering Thinking

Required for every lesson.

Teach the student how to reason like an engineer.

Answer:

* If I were the language or framework designer, why would I design it this way?
* What problem does this design solve?
* What trade-offs does this design introduce?
* What can go wrong in production?
* What would a tech lead look for during review?
* What would a CTO care about at system level?

Include a section like:

```markdown
## Tech Lead Questions

Question:

Think first.

Expected student answer:

Explanation:
```

The goal is to move beyond syntax into design judgment.

---

# Classroom Exercises

Required for every lesson.

Add interactive exercises throughout the lesson or as a dedicated section.

Every important concept should include at least one classroom exercise.

Each exercise should follow this format:

```markdown
Question:

Think first.

Expected student answer:

Explanation:
```

For coding exercises, include:

* Starter code
* Expected output
* Explanation
* Follow-up question

Exercises should become progressively harder.

They should test whether the student really understands the mental model, not only whether they can repeat definitions.

---

# FastAPI Connections

Required for every lesson.

Explain how today's concept appears in FastAPI.

Use realistic backend examples instead of abstract descriptions.

Include when relevant:

* Route handlers
* Dependency Injection
* `Depends()`
* Pydantic models
* Request state
* Database sessions
* Authentication
* Background tasks
* Testing

Every FastAPI example should explain:

* Why FastAPI uses this design
* What bug this design helps avoid
* What a production engineer should watch for

---

# Playwright Connections

Required for every lesson.

Explain how today's concept appears in Playwright automation.

Use realistic examples instead of abstract descriptions.

Include when relevant:

* Browser
* Context
* Page
* Locator
* Storage state
* Async API
* Error handling
* Job isolation

Every Playwright example should explain:

* What object owns what state
* What should be shared
* What should be isolated
* What can go wrong in automation workers

---

# English Interview

Required for every lesson.

This section supports overseas interviews.

Keep it concise and practical.

Include:

* Key vocabulary
* Useful expressions
* Short example answers
* Follow-up questions

Example format:

```markdown
## Key Vocabulary

* object identity
* dependency injection
* lifecycle

## Example Answer

In Python, ...
```

English should support the technical lesson, not replace the Chinese engineering explanation.

---

# Today's Takeaway

Required for every lesson.

Summarize the lesson as engineering principles.

Do not only summarize facts.

Include:

* The most important mental model
* The most important production risk
* The most important framework connection
* The most important interview answer

Example:

```text
Today's core idea:

Names are not objects. Names point to objects.
```

---

# Before Next Lesson Checklist

Required for every lesson.

Students should confirm they can answer these questions without looking at the notes.

Use checkbox format.

Example:

```markdown
- [ ] Can I explain the core concept in plain English?
- [ ] Can I explain why this design exists?
- [ ] Can I draw the memory model or lifecycle model?
- [ ] Can I identify the common production bug?
- [ ] Can I connect the topic to FastAPI?
- [ ] Can I connect the topic to Playwright?
- [ ] Can I answer an interview question about it in English?
```

The checklist should prepare the student for the next lesson.

---

# Recommended Supporting Sections

The required sections above define the minimum structure.

Add the following supporting sections when useful.

---

# Common Bugs

Explain typical mistakes.

For each bug:

* Show bad code
* Explain why it fails
* Show corrected code
* Explain the engineering principle

---

# Best Practice

Show production-ready patterns.

Explain:

* Why the pattern is preferred
* What trade-offs it makes
* How it appears in enterprise code

---

# Code Examples

Provide multiple examples.

Start simple.

Increase complexity gradually.

Prefer realistic backend examples once the basic concept is clear.

---

# Interview Questions

Include:

* Beginner questions
* Intermediate questions
* Senior questions
* Expected answers
* Follow-up questions

Senior questions should focus on design trade-offs, production bugs, and framework behavior.

---

# Tech Lead Review

Explain what a senior engineer would reject in review.

For each review case:

* Problem
* Why it matters
* Better design
* Follow-up question

---

# CTO Thinking

Explain how the topic affects architecture, hiring, reliability, maintainability, or business risk.

This section should help the student think beyond local code.

---

# Homework

Include:

* Coding exercise
* Thinking exercise
* Reading assignment

Homework should produce something reusable in the repository when possible.

## Repository Task

Every lesson should include a small repository synchronization task when relevant.

Encourage the student to update or verify:

* `docs`
* `interview`
* `cheat_sheets`
* `projects`

Examples:

* Add the lesson summary to the matching cheat sheet.
* Add new interview questions to the matching interview handbook.
* Add a small exercise or example to the relevant project.
* Update project documentation when the lesson creates reusable code.

The goal is to keep learning, documentation, projects, and interview preparation connected.

---

# Definition of Done

The lesson is complete only if the student can:

* Explain the concept.
* Draw the mental model.
* Solve the exercises.
* Explain the production risk.
* Connect the topic to FastAPI.
* Connect the topic to Playwright.
* Answer interview questions.
* Apply the concept in a project.

---

# Related Topics

Include:

* Previous lesson
* Next lesson
* Future connections

Future connections should mention relevant areas such as:

* FastAPI
* Playwright
* Docker
* Redis
* PostgreSQL
* AI Agent
