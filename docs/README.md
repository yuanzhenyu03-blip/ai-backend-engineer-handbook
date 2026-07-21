# Docs

Canonical lesson documents live here.

Lessons are organized by topic so the repository has one clear course structure.

```text
docs/
├── python/        # Day01-Day14 Python foundations
├── git/           # Day15-Day18 Git
├── github/        # Day19 GitHub project management
├── devops/        # Day20-Day28 CI/CD, containers, deployment, Kubernetes, production architecture
│   └── day28-ai-backend-production-architecture.md   # Phase 2 close
├── postgresql/    # Day29+ Phase 3 Backend Foundations
│   ├── day29-postgresql-foundations-and-durable-relational-state.md
│   ├── day30-sql-data-manipulation-and-query-fundamentals.md
│   ├── day31-relational-modeling-and-data-integrity.md
│   └── day32-sql-joins-aggregation-and-operational-queries.md         # latest
├── fastapi/
├── playwright/
└── n8n/
```

Rules:

- Do not create duplicate lesson folders outside `docs/`.
- Use lowercase kebab-case lesson file names.
- Day01-Day20 lessons remain valid with the original template (`LESSON_TEMPLATE.md`).
- Day21 and later final lessons must follow `LESSON_TEMPLATE_v2.md`.
