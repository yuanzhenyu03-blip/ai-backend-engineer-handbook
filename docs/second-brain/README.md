# Production Engineering Second Brain (Day23–Day28)

A long-term review, engineering-practice, and interview-preparation system for **Phase 2 Production Engineering**: Docker → Docker Compose → Deployment → Kubernetes Foundations → Kubernetes Workloads → Production AI Backend Architecture.

This is **not** a re-telling of the lessons. It compresses them, connects them across days, extracts memory models, and links back to the formal courses and real artifacts. The lessons remain the single source of truth.

## The five documents

| Document | Role | Use it when |
|---|---|---|
| [Day23-Day28-OnePage.md](Day23-Day28-OnePage.md) | **Recall** — the whole phase on one page | Daily 5–10 minute review; the night before an interview |
| [Day23-Day28-Production-Super-CheatSheet.md](Day23-Day28-Production-Super-CheatSheet.md) | **Explain** — per-day mental model, responsibility map, trade-offs, real misconceptions | Recovering a specific day's model after 3 months; 30-minute interview prep |
| [Day23-Day28-Architecture-Failure-Map.md](Day23-Day28-Architecture-Failure-Map.md) | **Connect** — cross-course Mermaid networks + unified Failure Matrix | Production incident triage; architecture/ownership reasoning |
| [Day23-Day28-Artifact-Templates.md](Day23-Day28-Artifact-Templates.md) | **Execute** — reusable artifact patterns with source links | While developing; when you need a Dockerfile/Compose/Nginx/K8s/Helm/architecture pattern |
| [Day23-Day28-Interview-QA.md](Day23-Day28-Interview-QA.md) | **Express** — Beginner/Intermediate/Senior Q&A with real student attempts | English interview practice; converting concepts to spoken judgment |

Content is intentionally **not** duplicated across them: the cheat sheet explains, the map connects, the templates execute, the Q&A expresses, and the one-page recalls.

## Recommended review order

**First pass (building the model), ~1 session:**

```text
1. OnePage            -> get the whole chain and the ultimate model in your head
2. Super Cheat Sheet  -> one day at a time, Day23 -> Day28
3. Architecture & Failure Map -> see how the days connect into one system
4. Artifact Templates -> open each linked example file alongside
5. Interview QA       -> say the strong answers out loud
```

**Daily 5-minute review:** OnePage only.

**Before an interview (30 minutes):** OnePage → Interview QA → the Failure Matrix in the Architecture & Failure Map.

**During a production incident:** Failure Matrix first (which layer owns the fault), then the relevant day in the Super Cheat Sheet.

**Returning after 3 months:** OnePage → Super Cheat Sheet "Real classroom misconceptions" sections → Architecture & Failure Map.

## The ten engineering judgments this phase builds

```text
Artifact Identity · Runtime Lifecycle · State Ownership · Network Boundary · Desired State
Failure Boundary · Rollback Boundary · Data Repair · Monitoring · Observability
```

The point is not memorizing tool names. It is being able to say, for any change: what exactly runs, who owns each piece of state, what is reachable from where, what is declared, where a fault stops, how it is reversed, what evidence proves it worked — and what rollback cannot fix.

## Source lessons and detailed references

| Day | Lesson | Primary artifact |
|---|---|---|
| Day23 | [Docker Fundamentals](../devops/day23-docker-fundamentals.md) | [examples/docker/fastapi/](../../examples/docker/fastapi/) |
| Day24 | [Docker Compose](../devops/day24-docker-compose.md) | [examples/docker/compose/](../../examples/docker/compose/) |
| Day25 | [Deployment Foundations](../devops/day25-deployment-foundations.md) | [examples/deployment/](../../examples/deployment/) |
| Day26 | [Kubernetes Foundations](../devops/day26-kubernetes-foundations.md) | [examples/kubernetes/ai-backend-baseline.yaml](../../examples/kubernetes/ai-backend-baseline.yaml) |
| Day27 | [Kubernetes Workloads](../devops/day27-kubernetes-workloads.md) | [examples/kubernetes/rag-platform/](../../examples/kubernetes/rag-platform/) |
| Day28 | [AI Backend Production Architecture](../devops/day28-ai-backend-production-architecture.md) | [examples/ai-backend-architecture/](../../examples/ai-backend-architecture/) |

Detailed reference material (not duplicated here): [cheat_sheets/devops.md](../../cheat_sheets/devops.md) and [interview/devops.md](../../interview/devops.md). Curriculum context: [CURRICULUM.md](../../CURRICULUM.md), [ROADMAP.md](../../ROADMAP.md).

## Validation boundary (read this before trusting any snippet)

Every Day23–Day28 example in this repository is a **teaching / conceptual template**. This handbook repo has no runnable FastAPI application, domain, TLS certificate, Kubernetes cluster, registry, or model-provider account. Therefore:

```text
NOT executed: docker build / docker run / docker compose up / nginx -t /
              kubectl apply / helm install / any AI backend runtime,
              queue redelivery, provider failure injection, load, smoke,
              runtime rollback, or data-repair drill.

Applies only: static reasoning, `docker compose config`, `helm lint` / `helm template`,
              and the repository's deterministic static check scripts.

Static validation != runtime success.
```

Placeholder images use the reserved `.invalid` TLD or mutable `:replace-...` tags; `example.com` is a reserved example domain; all secrets are placeholders injected out of band. No real secret, token, password, credential, or presigned URL appears in these documents.

## Knowledge boundary

This Second Brain covers Day23–Day28 only. Phase 3 (Backend Foundations: PostgreSQL, SQL, Redis, Database Design) deepens the durable-data, transaction, and schema-design boundaries introduced in Day28. Day29 is planned in the curriculum but its lesson file does not exist yet — nothing about its content is assumed here.
