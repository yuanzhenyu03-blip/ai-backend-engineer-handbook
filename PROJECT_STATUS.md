# Project Status

## Current Phase

Phase 2 — Engineering Foundations (Started)

Previous Phase:
Phase 1 — Python Foundations (Complete)

---

## Current Lesson

Day22 — GitHub Actions Advanced

Status:
Completed

Template:
LESSON_TEMPLATE_v2

Completed Time:
2026-07-11

---

## Completed

- ✅ Day01 — Python Object Model
- ✅ Day02 — Mutable vs Immutable
- ✅ Day03 — Functions & Parameter Passing
- ✅ Day04 — Scope & LEGB
- ✅ Day05 — Closures
- ✅ Day06 — Decorators
- ✅ Day07 — Iterators & Generators
- ✅ Day08 — Exception Handling
- ✅ Day09 — Modules & Packages
- ✅ Day10 — Type Hints
- ✅ Day11 — Object-Oriented Programming
- ✅ Day12 — Context Managers
- ✅ Day13 — Async Programming
- ✅ Day14 — Mini Project & Backend Architecture
- ✅ Day15 — Git Fundamentals
- ✅ Day16 — Git Branch & Merge
- ✅ Day17 — GitHub Workflow & Collaboration
- ✅ Day18 — Merge Strategy & Code Review
- ✅ Day19 — GitHub Project Management
- ✅ Day20 — CI/CD Foundations
- ✅ Day21 — GitHub Actions Fundamentals
- ✅ Day22 — GitHub Actions Advanced

---

## In Progress

None.

---

## Last Completed Lesson

Day22 — GitHub Actions Advanced

Completed Time:
2026-07-11

Main Artifact:
Advanced GitHub Actions workflow YAML (examples/github-actions/github-actions-advanced.example.yml)

Completed Work:

- Day22 classroom learning
- Day22 lesson document (LESSON_TEMPLATE_v2)
- Day22 advanced CI/CD workflow example
- Day22 matrix/cache/artifact/deployment exercises
- Day22 devops cheat sheet update
- Day22 devops interview notes update
- Day22 repository status update

---

## Next

- Day23 — Docker Fundamentals

Status:
Not started

---

## Learning Progress

Completed Python Foundations:

- Day01 — Object identity, references, function objects, callable objects
- Day02 — Mutable vs immutable objects, copy behavior, hashability
- Day03 — Function parameter passing, call by sharing, mutation vs rebinding
- Day04 — Scope, LEGB, lexical scope, closure basics, late binding
- Day05 — Closures, captured environment, factory functions, late binding fixes
- Day06 — Decorators, wrappers, universal decorators, metadata preservation
- Day07 — Iterables, iterators, generators, lazy evaluation, streaming pipelines
- Day08 — Exception handling, propagation, custom exceptions, exception chaining, root cause analysis
- Day09 — Modules, packages, import execution, module cache, namespaces, import side effects
- Day10 — Type Hints, interface contracts, collection types, Optional, TypeVar, Generic, framework contracts
- Day11 — Object-oriented programming, class and instance, state and behavior, `self`, lookup, inheritance, `super()`, composition
- Day12 — Context managers, resource lifecycle, `with`, `try / finally`, `__enter__`, `__exit__`, `@contextmanager`, deterministic cleanup
- Day13 — Async programming, event loop, coroutine vs task, `await`, `gather()`, cancellation, exception propagation, semaphore, stable throughput
- Day14 — Mini project and backend architecture, layered design, thin router, service layer, browser/LLM/repository layers, dependency injection, stateless services, worker throughput
- Day15 — Git fundamentals, snapshot vs diff, immutable commits, repository vs working directory, staging area, three-tree model, HEAD/branch, detached HEAD, reset modes, reflog
- Day16 — Git branch and merge, branch as movable reference, instant branch creation, HEAD/current branch, fast-forward merge, three-way merge, merge conflict, Git as a DAG
- Day17 — GitHub workflow, protected main, pull requests, CI vs code review, branch protection, stale review, review discussion as knowledge
- Day18 — Merge strategy and code review, history for humans, development vs product history, merge commit / squash / rebase, senior review focus, review the code not the coder
- Day19 — GitHub project management, manage work not only code, Issue as work item, Label as metadata, Milestone as goal, Projects as workflow, Idea-to-Release pipeline
- Day20 — CI/CD foundations, CI as trusted quality process, pipeline (fail fast, fast feedback), quality gate, CD (repeatable delivery), workflow as code, everything as code
- Day21 — GitHub Actions fundamentals, workflow as code, execution model, trigger vs runner, hosted vs self-hosted runner, job as one fresh runner, run/uses/with, checkout, quality gate, FastAPI CI
- Day22 — GitHub Actions advanced, matrix, fail-fast, cache vs artifact, composite action vs reusable workflow, needs/if/continue-on-error, deployment pipeline, immutable digest, environment, concurrency

---

## Core Abilities Mastered

- Explain LEGB name lookup.
- Explain lexical scope vs dynamic scope.
- Explain why Python searches names based on where a function is defined.
- Explain why `UnboundLocalError` happens with local rebinding.
- Explain when `global` works and why global request state is dangerous.
- Explain `nonlocal` and nearest enclosing scope.
- Explain mutation vs rebinding in scope problems.
- Define closure as function object plus captured environment.
- Explain late binding and the `i=i` default argument fix.
- Connect scope risks to FastAPI, Playwright, and AI backend systems.
- Explain why a closure can access local variables after the outer function returns.
- Explain captured environment and state preservation.
- Explain why `x = x + 1` raises `UnboundLocalError`, not `NameError`.
- Explain how `nonlocal` enables intentional rebinding in the nearest enclosing scope.
- Explain factory function design and how it separates configuration from business logic.
- Compare closure vs class for backend design.
- Build FastAPI dependency factories, Playwright configuration factories, and AI prompt builders.
- Explain production risks caused by captured mutable state.
- Explain why decorators exist for cross-cutting concerns.
- Explain `@decorator` as `func = decorator(func)`.
- Explain why the wrapper function is the callable that actually runs.
- Build universal decorators with `*args` and `**kwargs`.
- Explain why `functools.wraps` preserves metadata.
- Explain how decorators support logging, timing, retry, authentication, cache, and AI tracing.
- Review decorator production risks such as lost return values, broken metadata, and unsafe logging.
- Explain iterable vs iterator.
- Explain `iter()`, `next()`, and `StopIteration`.
- Explain why `StopIteration` is not replaced by `None`.
- Explain generator lifecycle and one-time consumption.
- Explain why `yield` creates pausable and resumable data flow.
- Compare list comprehension and generator expression.
- Explain `yield from`.
- Connect generators to FastAPI `StreamingResponse`, Playwright pipelines, and AI token streaming.
- Explain `try / except` control flow.
- Catch specific exceptions such as `ZeroDivisionError`.
- Explain why broad `except Exception` can hide bugs.
- Explain exception propagation through the call stack.
- Use `raise` for invalid business rules.
- Design custom exceptions such as `InvalidPromptError`.
- Preserve root cause with `raise ... from ...`.
- Connect exceptions to FastAPI `HTTPException`, Playwright recovery, and AI backend error design.
- Explain import as module execution, not source-code copying.
- Explain module objects and module namespaces.
- Explain how `sys.modules` caches imported modules.
- Explain why modules usually execute only once.
- Explain module vs package.
- Explain `__init__.py` and namespace packages.
- Compare `import module`, `from module import name`, and wildcard imports.
- Explain namespace pollution and why `from module import *` is risky.
- Prefer absolute imports for large backend systems.
- Identify import side effects and their production risks.
- Connect package boundaries to FastAPI, Playwright, and AI backend architecture.
- Explain Type Hints as interface contracts.
- Explain why Type Hints are not runtime checks by default.
- Add parameter and return type hints to backend functions.
- Use `list[T]`, `dict[K, V]`, `tuple`, `set[T]`, `User | None`, `Optional`, and `Union`.
- Explain type inference and when local annotations are unnecessary.
- Explain why empty collections often need explicit types.
- Use `TypeVar` to preserve input-output type relationships.
- Explain why `T -> T` is better than `object -> object`.
- Use `Generic` for reusable wrappers such as `Response[T]`.
- Connect Type Hints to FastAPI request models, response models, `Depends()`, Pydantic, and OpenAPI.
- Connect Type Hints to Playwright `Browser`, `BrowserContext`, `Page`, `Locator`, and storage state.
- Connect Type Hints to AI backend `ChatMessage`, `AgentTask`, `AgentResult`, `ToolResult`, and tool calling.
- Explain OOP as responsibility design, not class decoration.
- Explain object, class, instance, state, and behavior.
- Explain `self` as the current instance object.
- Explain `u1.say_hi()` as `User.say_hi(u1)`.
- Explain class attributes, instance attributes, and shadowing.
- Explain attribute lookup and method lookup.
- Explain inheritance as Is-A.
- Explain method override and why lookup stops after the first match.
- Explain why parent `__init__()` does not run automatically.
- Use `super().__init__()` to initialize parent state.
- Explain basic MRO.
- Explain composition as Has-A.
- Explain why modern backend systems often prefer composition over inheritance.
- Connect OOP to FastAPI application, request, response, dependency, and service objects.
- Connect OOP to Playwright `Browser`, `BrowserContext`, `Page`, and `Locator`.
- Connect OOP to AI backend `ChatService`, `LLMClient`, `PromptBuilder`, `VectorStore`, `UserRepository`, and `RedisCache`.
- Explain a context manager as deterministic resource cleanup, not just `with` syntax.
- Explain the resource lifecycle: Acquire, Use, Release.
- Explain why Release is the step most often skipped on failure.
- Use `try / finally` to guarantee cleanup manually.
- Explain what `with` guarantees over plain assignment.
- Implement `__enter__` and `__exit__` for a custom context manager.
- Explain the three `__exit__` arguments and the meaning of returning `True` vs `False`.
- Write `@contextmanager` generators and explain `yield` vs `return`.
- Explain why `yield` must sit inside `try / finally`.
- Explain why business logic should not own resource management.
- Build FastAPI `yield` dependencies and `asynccontextmanager` lifespan handlers.
- Close Playwright `BrowserContext` per job to avoid leaks.
- Wrap LLM streams, Redis connections, sessions, and locks to prevent AI backend leaks.
- Identify database, file, browser, Redis, stream, and lock leaks.
- Explain that async improves I/O throughput, not CPU speed.
- Explain I/O bound vs CPU bound work.
- Explain blocking vs non-blocking from the Event Loop's perspective.
- Explain the Event Loop as a single-threaded cooperative scheduler.
- Explain coroutine, coroutine object, and why calling a coroutine does not run it.
- Explain the difference between a coroutine and a Task.
- Explain what `await` does to the coroutine and the Event Loop.
- Explain why `asyncio.gather()` returns input order, not completion order.
- Explain the Task lifecycle and cooperative cancellation with `CancelledError`.
- Explain exception propagation and "Task exception was never retrieved".
- Explain why a `Semaphore` protects downstream capacity for stable throughput.
- Use `asyncio.to_thread()` for unavoidable blocking work.
- Connect async to FastAPI request Tasks, Playwright automation, and AI backend concurrency.
- Design a layered AI backend: API, Service, Browser, LLM, Repository, Database.
- Explain the single responsibility of each layer and what it must NOT do.
- Keep FastAPI routers thin and move logic into the Service layer.
- Use dependency injection to build stateless, testable services.
- Treat the Browser and LLM as infrastructure behind interfaces.
- Apply the Repository pattern to hide the database.
- Apply separation of concerns, single responsibility, low coupling, and high cohesion.
- Reason about worker architecture, async vs worker scaling, and horizontal scaling.
- Apply Semaphore, retry, and exponential backoff for downstream limits.
- Design a task-status pattern for long-running jobs.
- Answer backend architecture interview questions with engineering reasoning and trade-offs.
- Explain Git as a project history management system, not a backup tool.
- Explain why Git's core model is a snapshot, not a pure diff.
- Explain why a commit is an immutable snapshot object.
- Distinguish the Repository, Working Directory, and a commit.
- Explain the Staging Area as the blueprint of the next commit.
- Explain the three-tree model and describe commands as tree movement.
- Explain HEAD, branch, and detached HEAD as references.
- Explain `git reset --soft`, `--mixed`, and `--hard` using the three trees.
- Recover a mistaken reset with `git reflog`.
- Connect Git to FastAPI rollback, Playwright test history, and AI prompt versioning.
- Explain why branches exist from the engineering problem they solve.
- Explain that a branch is a movable reference, not a copy.
- Explain why branch creation is nearly instant.
- Explain HEAD and how only the current branch moves on commit.
- Explain fast-forward merge as reference movement.
- Explain three-way merge and why a merge commit has two parents.
- Explain why merge conflicts happen and why Git refuses to guess intent.
- Explain Git history as a Directed Acyclic Graph.
- Connect branching to FastAPI, Playwright, AI backend, agent, and Docker work.
- Explain why pushing directly to `main` is dangerous.
- Explain a Pull Request as Review + CI + Discussion + Audit Trail.
- Explain the split: machines validate rules, humans validate intent.
- Explain why Branch Protection protects `main`.
- Explain why a review goes stale after `main` changes.
- Explain why review discussions are preserved as engineering knowledge.
- Connect the GitHub workflow to FastAPI, Playwright, AI backend, prompt, and Docker work.
- Explain why Git history is designed for humans.
- Distinguish development history from product history.
- Explain merge commit, squash merge, and rebase merge, and when to use each.
- Explain what senior engineers review: architecture, performance, security, maintainability.
- Explain "review the code, not the coder."
- Explain the three goals of review: improve the code, the developer, and the team.
- Connect merge strategy and review to FastAPI, Playwright, AI backend, prompt, and Docker work.
- Explain why software teams manage work, not only code.
- Explain an Issue as a work item enabling collaboration, tracking, prioritization, and ownership.
- Explain a Label as structured metadata for retrieval, workflow, and automation.
- Explain a Milestone as a delivery goal made of many Issues.
- Explain GitHub Projects as workflow management, distinct from task management.
- Explain the hierarchy: Issue (Work), Label (Metadata), Milestone (Goal), Project (Workflow).
- Assemble the complete Idea-to-Release workflow tying Day15-Day19 together.
- Distinguish ownership from blame.
- Explain why CI establishes a trusted quality process.
- Explain a pipeline as ordered stages with fail-fast and fast feedback.
- Explain a quality gate as risk control protecting main, production, team, and users.
- Explain CD in terms of repeatability, consistency, reliability, and scalability.
- Explain Workflow as Code and Everything as Code.
- Assemble the full software delivery lifecycle tying Day15-Day20 together.
- Connect CI/CD to FastAPI, Playwright, AI backend, Docker, and prompt work.
- Explain why a repository defines its own workflow as code.
- Explain the GitHub Actions execution model from event to result.
- Compare GitHub-hosted and self-hosted runners and defend the trade-off.
- Design a multi-job workflow based on runner lifecycle, parallelism, and failure isolation.
- Implement a basic FastAPI CI workflow in YAML.
- Distinguish `on`, `runs-on`, `run`, `uses`, and `with` precisely.
- Connect GitHub Actions to FastAPI CI and AI backend GPU/evaluation workloads.
- Explain a matrix as one job template expanded by variables (not a resource optimization).
- Decide `fail-fast: true` vs `false` from the independent value of remaining combinations.
- Distinguish cache (re-creatable acceleration) from artifact (formal workflow output).
- Compare composite action (reusable steps) with reusable workflow (reusable jobs).
- Separate `needs`, `if`, and `continue-on-error` as distinct control mechanisms.
- Design a build-once/deploy-many pipeline with an immutable image digest.
- Explain production Environment protection and serialized deployment concurrency.

---

## Mini Exercises Completed

- LEGB output prediction exercises
- Lexical scope reasoning exercises
- `UnboundLocalError` explanation exercises
- `global` and `nonlocal` exercises
- Mutation vs rebinding exercises
- Closure counter exercise
- Late binding loop exercise
- FastAPI global request state scenario
- Playwright global page scenario
- AI prompt builder closure scenario
- Closure identification exercises
- Closure memory model exercises
- `nonlocal` output prediction exercises
- Factory function exercises
- `make_multiplier()` implementation
- Counter implementation with state preservation
- `UnboundLocalError` repair exercises
- Closure vs class refactoring exercise
- Late binding output prediction exercises
- Late binding fix with `i=i`
- FastAPI dependency factory exercise
- Playwright timeout factory exercise
- AI prompt builder factory exercise
- Closure engineering thinking exercises
- Decorator output prediction exercises
- Decorator execution order exercises
- Wrapper call flow exercises
- Universal decorator implementation
- Timer decorator exercise
- Logging decorator exercise
- `TypeError` analysis exercise
- `functools.wraps` metadata comparison
- FastAPI route decorator reasoning exercise
- Playwright retry decorator exercise
- AI token logger decorator exercise
- Day06 code review exercises
- Iterable vs iterator classification exercises
- `iter()` and `next()` output prediction exercises
- `StopIteration` reasoning exercises
- Generator lifecycle exercises
- Generator expression exercises
- One-time consumption exercises
- `yield from` exercises
- FastAPI `StreamingResponse` thinking exercise
- Playwright pipeline exercise
- AI token streaming exercise
- Pipeline vs batch exercise
- `try / except` output prediction exercises
- `ZeroDivisionError` precise catch exercise
- Exception propagation call stack exercise
- `raise` and `check_age(age)` exercise
- `InvalidPromptError` custom exception exercise
- Exception chaining exercise
- FastAPI `HTTPException` scenario
- Playwright timeout screenshot and cleanup scenario
- AI backend prompt validation and tool error scenario
- Module vs package classification exercises
- Import output prediction exercises
- `__init__.py` execution order exercise
- `sys.modules` cache reasoning exercise
- Namespace pollution review exercise
- Absolute vs relative import exercise
- Import side effect review exercise
- FastAPI package design exercise
- Playwright module boundary exercise
- AI backend package architecture exercise
- Basic Type Hint exercises
- Return type exercises
- `list[T]` and `dict[K, V]` exercises
- `User | None`, `Optional`, and `Union` exercises
- `TypeVar` identity exercise
- `Generic` response wrapper exercise
- FastAPI request and response model exercise
- FastAPI `Depends()` type contract exercise
- Playwright `Page`, `BrowserContext`, and `Locator` typing exercise
- AI backend `ChatMessage`, `AgentTask`, `AgentResult`, and `Response[T]` exercise
- Object model exercises
- Class vs instance exercises
- State vs behavior exercises
- `self` call transformation exercise
- Class attribute and instance attribute exercises
- Attribute lookup and shadowing exercises
- Inheritance and method override exercises
- `super().__init__()` exercise
- Composition refactoring exercise
- FastAPI service layer design exercise
- Playwright object ownership exercise
- AI backend `ChatService` composition exercise
- `with` file rewrite exercise
- `try / finally` cleanup exercise
- `__enter__` implementation exercise
- `__exit__` implementation exercise
- Exception cleanup output prediction exercise
- `@contextmanager` yield exercise
- FastAPI `yield` dependency exercise
- Blocking vs non-blocking exercise
- Coroutine object output prediction exercise
- Task concurrency exercise
- `await` suspension point exercise
- `gather()` input-order exercise
- Task cancellation cleanup exercise
- Task exception propagation exercise
- Semaphore concurrency limit exercise
- FastAPI async lifecycle exercise
- API layer refactor exercise
- Service layer design exercise
- Browser layer boundary exercise
- Dependency injection wiring exercise
- Repository pattern exercise
- Task status design exercise
- Retry strategy with backoff exercise
- Worker architecture exercise
- System design exercise
- Architecture mock interview exercise
- Python reference review exercise (Git connection)
- Git snapshot checkout experiment
- Staging area experiment
- Reset mode experiment
- Reflog recovery experiment
- Two-branches-one-commit experiment
- Fast-forward merge experiment
- Three-way merge experiment
- Merge conflict create-and-resolve experiment
- Open a pull request exercise
- Trigger CI exercise
- Request changes exercise
- Approve exercise
- Simulate stale review exercise
- Merge pull request exercise
- Merge commit vs squash merge comparison exercise
- Merge strategy selection exercise
- FastAPI endpoint review exercise
- Rewrite a poor review comment exercise
- Convert feature requests into Issues exercise
- Assign and justify Labels exercise
- Group Issues into a Milestone exercise
- Build a Project workflow board exercise
- Why "I tested locally" is insufficient exercise
- Design a CI pipeline exercise
- Explain a quality gate exercise
- Manual deployment vs CD exercise
- Explain workflow as code exercise
- Repository-defined workflow reasoning exercise
- Workflow vs runner exercise
- Hosted vs self-hosted runner design exercise
- Multi-job AI backend workflow design exercise
- Basic FastAPI CI workflow YAML exercise
- Matrix expansion exercise
- fail-fast decision exercise
- Cache vs artifact classification exercise
- Composite action vs reusable workflow exercise
- needs/if/continue-on-error classification exercise
- Deployment reliability review exercise
- Comprehensive advanced workflow design exercise

---

## Last Completed Goal

- [x] Complete Lesson
- [x] Complete Coding Exercises
- [x] Complete Mini Exercises
- [x] Update Handbook
- [x] Update Cheat Sheet
- [x] Update Interview Notes
- [x] Commit
- [x] Push to GitHub

---

## Definition of Done

A training day is complete only if:

✓ Lesson finished

✓ Exercises completed

✓ Repository updated

✓ Git committed

✓ Git pushed

✓ Ready for next lesson

---

## Repository Status

Handbook:
🟢 Healthy

Projects:
🟢 Healthy

Interview Notes:
🟢 Healthy

Cheat Sheets:
🟢 Healthy
