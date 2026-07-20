# Project Status

## Current Phase

Phase 3 — Backend Foundations (In Progress)

Previous Phase:
Phase 2 — Engineering Foundations (Complete)

---

## Current Lesson

Day31 — Relational Modeling and Data Integrity

Status:
Planned / Not started

(The Day31 lesson has not started and no Day31 lesson file exists yet; see CURRICULUM.md and ROADMAP.md.
Day30 details are recorded under Last Completed Lesson.)

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
- ✅ Day23 — Docker Fundamentals
- ✅ Day24 — Docker Compose
- ✅ Day25 — Deployment Foundations
- ✅ Day26 — Kubernetes Foundations
- ✅ Day27 — Kubernetes Workloads
- ✅ Day28 — AI Backend Production Architecture
- ✅ Day29 — PostgreSQL Foundations and Durable Relational State
- ✅ Day30 — SQL Data Manipulation and Query Fundamentals

---

## In Progress

None.

---

## Last Completed Lesson

Day30 — SQL Data Manipulation and Query Fundamentals

Completed Time:
2026-07-20

Main Artifact:
Day30 increment of the Production AI Backend Data Layer — a raw, parameterized SQL operations pack (projects/ai-backend-data-layer/sql/002_job_crud_and_guarded_transitions.sql) with explicit affected-row contracts

Validation Boundary:
Conceptual/manual review of the SQL semantics was completed in class. The repository update performed a static file review only (balanced syntax, guard direction, RETURNING presence, parameter usage, absence of transactions/locks/constraints/indexes, no credentials). PostgreSQL parser/runtime execution, Python-driver parameter binding, FastAPI/Celery/Object Storage integration, transaction/concurrency runtime tests, and production validation were NOT RUN — no psql/PostgreSQL server was available. Day29's PostgreSQL 14.18 classroom evidence applies to 001_create_jobs.sql only and is not Day30 runtime evidence.

Completed Work:

- Day30 classroom learning
- Day30 lesson document (LESSON_TEMPLATE_v2, v3.2 continuity + Day29->Day30 mental-model evolution)
- Day30 parameterized SQL operations pack and project README increment
- Day30 deterministic SELECT / NULL logic / INSERT defaults / parameter boundary / guarded transitions / DELETE precedence / lost update / 842-row incident exercises
- Day30 PostgreSQL cheat sheet append
- Day30 PostgreSQL interview notes append
- Day30 repository status update

---

## Next

- Day31 — Relational Modeling and Data Integrity (Phase 3 — Backend Foundations)

Status:
Planned / Not started

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
- Day23 — Docker fundamentals, container as isolated process (namespaces/cgroups), image vs container, image layers vs writable layer, Dockerfile, build vs run, volumes, networks, immutable replacement
- Day24 — Docker Compose, multi-service declaration, started vs ready (depends_on/healthcheck/retry), project/service/image/container, service DNS, network segmentation, volumes, env/secrets/business data, base + dev override, production boundary
- Day25 — Deployment foundations, stable public entry (DNS/Nginx/TLS), reverse proxy, HTTP->HTTPS, trusted proxy context, promote immutable digest, API blue-green + drain + rollback, Expand-Migrate-Contract, worker rollout, serialized deploy identity, AI streaming timeouts, DNS TTL
- Day26 — Kubernetes foundations, desired state vs one-time command, reconciliation control loop, Pod (one or more tightly coupled containers), Deployment (template + replicas, not scheduling), Service (stable label-based discovery), ConfigMap (non-sensitive config, same digest), Secret (Base64 != encryption, not an automatic vault), config/secret env not mutating running processes, health 200 != business success, reconciliation != business correctness, safe partial-outage rollback
- Day27 — Kubernetes workloads, Ingress L7 Host/Path/TLS routing (resource vs controller), HPA updates desired replicas on a scale target (CPU vs queue backlog, upstream limits), Rolling Update (maxSurge/maxUnavailable, strategy vs rollback vs Blue-Green), deleting v2 Pods is not a rollback, StatefulSet stable identity/PVC/headless Service/ordered lifecycle (not replication/HA), Helm templates vs Values vs Release, validation ladder (lint/template/API/runtime), never commit secrets to Values, readiness 200 != business success
- Day28 — AI Backend production architecture, request vs job lifecycle (202 + job_id), state ownership (PostgreSQL truth / Redis deliver / Object Storage bytes / memory transient), Transactional Outbox + at-least-once + idempotent processing, durable checkpoints/leases/idempotency keys (unique constraint/upsert, ACK after durable), presigned multipart upload + Upload Session verification, retry (backoff+jitter+max attempts/deadline+classification+circuit breaker), monitoring (depth vs oldest-age vs throughput), observability (stable job_id correlation, low-cardinality metrics, append-only events), failure containment + compute rollback != data repair (contain/restore/identify/rebuild/verify)
- Day29 — PostgreSQL foundations and durable relational state, write+commit the Job row before 202, server/cluster/database/schema/table/row/column boundaries, psql connects to a database (qualified name vs search_path; public is a default namespace), Job types/defaults (uuid PK gen_random_uuid, text, integer, boolean, timestamptz now(), bounded jsonb), typed columns vs JSONB-only, type vs relationship cardinality, NULL per lifecycle, NOT NULL rejects only NULL (empty/'banana' accepted), DEFAULT VALUES + RETURNING, primary key vs idempotency key, timestamptz as one absolute instant, validation ladder, durability != integrity, code rollback vs guarded data repair
- Day30 — SQL data manipulation and query fundamentals, clause chain SELECT/FROM/WHERE/ORDER BY/LIMIT, explicit columns and a unique ORDER BY tie-breaker, three-valued logic (WHERE keeps only TRUE; IS NULL; why `<> 'timeout'` drops no-error rows), INSERT with database defaults + RETURNING (rows not a count), parameterized SQL and the injection boundary (values only; identifiers need an allowlist; it does not authorize or fix concurrency), WHERE as the modification boundary with current-state guards, zero rows means the transition did not apply, AND/OR precedence in destructive statements, lost-update awareness (database-side increment or expected-old-value guard), and the contain->evidence->identify->reconcile->guarded repair->verify incident order

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
- Explain a container as an isolated process (namespaces + cgroups), not a small VM.
- Distinguish an image (immutable template) from a container (runtime instance).
- Explain image layers, the writable layer, and build-cache ordering.
- Write a Dockerfile and explain FROM/WORKDIR/COPY/RUN/CMD/ENTRYPOINT.
- Distinguish `docker build` from `docker run`.
- Separate compute lifecycle from data lifecycle using volumes.
- Connect containers over an explicit network using service DNS names, not localhost.
- Apply immutable replacement instead of mutating a running production container.
- Explain why individually runnable containers do not make a reproducible system.
- Distinguish `depends_on`, a healthcheck, and application retry (started != ready).
- Distinguish Project, Service, Image, and Container, and decide rebuild vs recreate.
- Write a declarative Compose model with services, networks, volumes, and secrets.
- Use service DNS names and publish only the necessary host port.
- Design network segmentation for least access.
- Separate ordinary configuration, secrets, and governed business data.
- Split a portable base file from a development override.
- State where Compose fits in production and where a cluster is required.
- Explain the stable public entry (Domain -> DNS -> Nginx :443 -> backend) and keeping the backend port internal.
- Configure an Nginx reverse proxy and trusted proxy headers.
- Explain TLS as confidentiality + integrity + server authentication, and where it terminates.
- Redirect HTTP to HTTPS (308) and explain why it cannot protect an already-sent credential.
- Explain the certificate lifecycle and Nginx master/worker (reload vs restart).
- Promote one CI-verified immutable image digest instead of rebuilding per environment.
- Perform an API blue-green switch with verify, observe, drain, and rollback.
- Apply Expand-Migrate-Contract to a PostgreSQL schema change and roll out a worker compatibly.
- Serialize deployment with a concurrency lock and a least-privilege short-lived identity.
- Configure AI streaming (buffering off, correct timeouts) and reason about DNS TTL propagation.
- Distinguish a one-time command from a declared desired state that is continuously reconciled.
- Explain a Pod as the smallest deployable unit of one or more tightly coupled containers, and when not to co-locate.
- Explain a Deployment as a Pod template plus a replica count with controller replacement, not scheduling.
- Explain a Service as stable label-based discovery for a changing set of Pods.
- Separate non-sensitive runtime config (ConfigMap) from the immutable image and preserve the verified digest.
- Classify sensitive values into a Secret and explain why Base64 is encoding, not encryption.
- Explain why a ConfigMap/Secret change does not mutate an already-running process environment.
- Diagnose a partial AI outage where /health returns 200 but one Pod uses an invalid rotated key.
- Order a safe rollback that preserves healthy Pods and replaces only the faulty Pod.
- Keep Deployment selector, Pod template labels, and Service selector consistent.
- Explain Ingress as L7 Host/Path/TLS routing to Services and the resource-vs-controller split.
- Explain that HPA updates desired replicas on a scale target rather than creating Pods directly.
- Choose a meaningful scaling metric (queue backlog for external-wait workloads, not CPU) and bound it by upstream capacity.
- Perform a Deployment Rolling Update with maxSurge/maxUnavailable and distinguish it from rollback and Blue-Green.
- Explain why deleting v2 Pods is not a rollback and restore a known-good desired revision instead.
- Explain StatefulSet stable identity, per-Pod PVCs, headless Service, and ordered lifecycle — and why it is not database replication/HA.
- Separate Helm templates from environment Values across all objects and name the validation ladder.
- Explain why real Secrets must never live in Helm Values and where release history can leak them.
- Separate the FastAPI request lifecycle from a long-running Celery job lifecycle and return 202 + job_id.
- Assign every job state/byte to PostgreSQL (truth), Redis (deliver/cache), Object Storage (bytes), or memory (transient).
- Explain the database-to-queue crash gap and derive the Transactional Outbox with at-least-once + idempotent processing.
- Design durable checkpoints, atomic claim/lease, and a stable idempotency key enforced by a unique constraint/upsert, ACKing after durable write.
- Design presigned direct multipart upload with an Upload Session and server-side verification.
- Design a bounded, classified provider retry policy with backoff, jitter, and a circuit breaker.
- Choose monitoring signals (queue depth vs oldest-age vs throughput) and stable observability correlation identity (job_id, not job_status).
- Order a failure-containment/rollback/data-repair runbook and explain why compute rollback does not repair persisted data.
- Explain at-least-once delivery, why exactly-once across independent systems is not promised, and how object keys are not authorization.
- Explain why the Job row must be committed before FastAPI returns 202.
- Distinguish PostgreSQL server/cluster/database/schema/table/row/column and what a psql session connects to.
- Distinguish a PostgreSQL Schema (namespace) from a table schema (definition/contract).
- Choose Job model types/defaults and defend UUID vs integer identity with real trade-offs.
- Explain why core facts use typed columns while JSONB stays bounded auxiliary metadata.
- Interpret NULL per field lifecycle and state what NOT NULL does not enforce.
- Distinguish a primary key (row identity) from an idempotency key (request identity).
- Explain timestamptz as one absolute instant rendered in the session time zone.
- Classify conceptual / syntax / runtime / integration / production validation evidence.
- Repair durable-but-wrong rows with a guarded UPDATE and explain why code rollback cannot.
- Write a deterministic SELECT with explicit columns, a filter, a unique tie-breaker, and LIMIT.
- Explain SQL three-valued logic and why WHERE discards both FALSE and UNKNOWN.
- Use IS NULL correctly and include no-error rows explicitly instead of losing them to `<>`.
- Insert with database defaults and return generated facts with RETURNING.
- Explain what parameterized SQL prevents and the three things it does not solve.
- Write guarded state transitions with identity plus current-state predicates.
- Interpret zero returned rows honestly without claiming the row does not exist.
- Correct AND/OR precedence in destructive statements and use RETURNING as evidence.
- Diagnose a lost update and fix it with a database-side increment or an expected-old-value guard.
- Order an incident response: contain, preserve evidence, identify, reconcile, repair, verify.

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
- Container vs VM exercise
- Image vs container exercise
- Layer/cache exercise
- Dockerfile exercise
- Build vs run exercise
- Volume exercise
- RAG architecture design exercise
- Image optimization exercise
- Minimal FastAPI Dockerfile authoring exercise
- Why-a-reproducible-system exercise
- Started-vs-ready diagnosis exercise
- Project/service/image/container counting exercise
- Rebuild-vs-recreate exercise
- Compose model authoring exercise
- Healthcheck + service_healthy exercise
- Config/secret/business-data classification exercise
- Compose-vs-cluster decision exercise
- Integrated Compose stack build exercise
- Correct-the-reverse-proxy exercise
- HTTP->HTTPS + token question exercise
- Trusted proxy headers exercise
- Promote-a-digest exercise
- Blue-green + drain exercise
- Expand-Migrate-Contract exercise
- Streaming timeouts exercise
- DNS migration exercise
- One-time-startup vs desired-state exercise
- Pod boundary (FastAPI + sidecar) exercise
- Three Pods vs one Deployment exercise
- New-IP failure diagnosis exercise
- Service with label selection exercise
- ConfigMap vs new image exercise
- Secret classification (Base64) exercise
- Health-200-but-401 partial outage diagnosis exercise
- Secret-rotation rollback ordering exercise
- Kubernetes English interview exercise
- Final Kubernetes mental model synthesis exercise
- Service vs Ingress layer exercise
- /chat vs /admin routing ownership exercise
- Initial CPU scaling metric exercise
- Low-CPU growing-backlog HPA diagnosis exercise
- Surge rollout (maxSurge/maxUnavailable) design exercise
- Stalled v2 Readiness prediction exercise
- Blue-Green vs Rolling Update comparison exercise
- Deployment+volume vs StatefulSet exercise
- Three-PVCs-not-three-copies exercise
- Helm templates vs Values separation exercise
- Secrets-not-in-Values exercise
- Helm validation-ladder exercise
- Helm failed-revision recovery exercise
- Kubernetes workloads English interview exercise
- Final Kubernetes workloads mental model synthesis exercise
- Request-vs-worker boundary exercise
- Job state ownership assignment exercise
- DB-first vs queue-first + Transactional Outbox derivation exercise
- Worker crash checkpoint/lease/idempotency recovery exercise
- 500 MB storage choice exercise
- Presigned direct upload + verification/cleanup exercise
- Upload Session vs Job lifecycle separation exercise
- Provider retry (429/503, 20-min outage) design exercise
- Queue depth vs oldest-age vs throughput interpretation exercise
- Cross-component correlation identity exercise
- Failure/rollback/data-repair runbook ordering exercise
- Production architecture English interview exercise
- Final AI Backend production architecture mental model synthesis exercise
- Minimum durable facts before 202 exercise
- PostgreSQL types/defaults selection exercise
- app.jobs not-found diagnosis (database/schema/search_path) exercise
- public vs app namespace exercise
- Typed columns vs JSONB-only comparison exercise
- Nullable lifecycle field interpretation exercise
- Row identity vs request/idempotency identity exercise
- psql session diagnostic checklist exercise
- Validation-level classification exercise
- DEFAULT VALUES + RETURNING default-proof exercise
- timestamptz UTC vs Asia/Shanghai comparison exercise
- queud guarded data repair exercise
- PostgreSQL restart persistence exercise
- PostgreSQL English interview exercise
- Final PostgreSQL durable-state mental model synthesis exercise
- Deterministic oldest-queued SELECT exercise
- Unfinished Jobs IS NULL exercise
- Why NULL rows vanish from `<> 'timeout'` exercise
- INSERT provider_metadata with defaults + RETURNING exercise
- Parameter binding / injection boundary exercise
- Guarded queued->running transition exercise
- Zero-row interpretation exercise
- Guarded DELETE with AND/OR precedence exercise
- attempt_count lost-update exercise
- Guarded running->succeeded exercise
- 842-row accidental UPDATE incident exercise
- SQL data manipulation English interview exercise
- Final SQL manipulation mental model synthesis exercise

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
