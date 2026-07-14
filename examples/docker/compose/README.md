# examples/docker/compose

A Day24 Docker Compose example: a portable, production-style multi-service model for a local
RAG/AI backend (FastAPI `api`, background `worker`, `redis`, `postgres`), plus a development
override.

**Example / template only.** This handbook repo has no runnable FastAPI app (see Day23), so this
stack is a teaching template. `docker compose up` has **not** been run here; only
`docker compose config` (static model validation) is meaningful until you copy the files into a
real project that provides the Day23 `Dockerfile`, `requirements.txt`, and an `app/` package.

Lesson: `docs/devops/day24-docker-compose.md`

## Files

- `compose.yaml` — the portable base model (production-style; no host source mounts).
- `compose.dev.yaml` — development-only override: source bind mounts + Uvicorn `--reload`.
- `.env.example` — non-sensitive configuration template. Copy to `.env` (git-ignored).

## Service roles

- Only `api` publishes a host port (`8000:8000`); `worker`, `redis`, and `postgres` are internal.
- `api` and `worker` share the **same** image `rag-app:local` but use different commands
  (`uvicorn ...` vs `python -m app.worker`). The `api` service has `build:`; `worker` reuses the
  built image, so a full-stack `up --build` (or building the image first) must create the image
  before `worker` can start.
- Internal traffic uses **service DNS names** (`redis:6379`, `postgres:5432`), never `localhost`.
- Network segmentation: `queue_network` (api, worker, redis) and `database_network`
  (api, worker, postgres). Redis and PostgreSQL share no network (least access).
- `postgres` owns the named volume `postgres_data`; `api`/`worker` stay stateless and replaceable.

## Secrets (you supply these locally; they are not committed)

Compose secrets are mounted at `/run/secrets/<name>`, and the **application must read the file**
— mounting a secret alone does not configure anything. Create the files the model references:

```bash
mkdir -p .secrets
printf '%s' 'a-strong-local-password' > .secrets/postgres_password.txt
printf '%s' 'sk-your-local-openai-key' > .secrets/openai_api_key.txt
```

`.secrets/` and `.env` are git-ignored. Never commit real passwords, API keys, or a
`DATABASE_URL` containing a password. Least-privilege grants: `api` gets `postgres_password`;
`worker` gets `postgres_password` + `openai_api_key`; `postgres` gets `postgres_password`; `redis`
gets none.

## Commands

```bash
# 1. Prepare configuration and secrets.
cp .env.example .env
mkdir -p .secrets && printf '%s' 'a-strong-local-password' > .secrets/postgres_password.txt \
  && printf '%s' 'sk-your-local-openai-key' > .secrets/openai_api_key.txt

# 2. Validate the resolved model WITHOUT starting anything.
docker compose config
# Base + development override merged:
docker compose -f compose.yaml -f compose.dev.yaml config

# 3. Build and start (needs a real FastAPI app; this template has none).
docker compose -f compose.yaml -f compose.dev.yaml up -d --build

# 4. Observe, follow logs, run one-off tasks.
docker compose ps --all
docker compose logs -f api
docker compose run --rm api alembic upgrade head

# 5. Stop / tear down.
docker compose stop                 # keep containers/networks/volumes
docker compose down                 # remove containers + networks, KEEP named volumes
docker compose down --volumes       # ALSO delete named volumes (destroys local DB data)
```

> `docker compose down --volumes` deletes `postgres_data`. Volume persistence is not a backup —
> real backups and restore tests are separate controls.

> Multi-node scheduling, self-healing, autoscaling, rolling updates, and public TLS/domain
> governance are **not** Compose features; those are covered from Day25 (Deployment) and
> Day26–Day27 (Kubernetes).
