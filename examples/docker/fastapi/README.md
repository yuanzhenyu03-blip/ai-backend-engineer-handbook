# examples/docker/fastapi

A production-oriented FastAPI Docker example (Day23 — Docker Fundamentals).

Example only: this handbook repo has no FastAPI app. Copy the `Dockerfile` and `.dockerignore`
into a real project that provides `requirements.txt` and an `app/` package exposing
`app.main:app`, then adjust the health-check path and commands.

Lesson: `docs/devops/day23-docker-fundamentals.md`

## Build (make the immutable image)

```bash
docker build -t fastapi-service:local .
```

## Run (create and start a container)

```bash
# Map host port 8080 to the container's 8000 (host port vs container port are distinct).
docker run --rm -p 8080:8000 fastapi-service:local
```

Inject configuration/secrets at runtime — never bake them into the image:

```bash
docker run --rm -p 8080:8000 --env-file .env fastapi-service:local
```

## Named volume (data lifecycle independent of the container)

```bash
docker volume create app-data
docker run --rm -p 8080:8000 -v app-data:/app/data fastapi-service:local
# Removing/recreating the container keeps data in the `app-data` volume.
```

## User-defined network + service DNS (reach another container by name)

```bash
docker network create ragnet

# A PostgreSQL container joins the network with a stable DNS name `postgres`.
# POSTGRES_DB creates the `app` database so it matches the DATABASE_URL below.
# (`example` is a throwaway local password placeholder, never a real secret.)
docker run -d --name postgres --network ragnet \
  -e POSTGRES_PASSWORD=example -e POSTGRES_DB=app \
  -v pgdata:/var/lib/postgresql/data postgres:16

# The FastAPI container on the same network reaches it as `postgres:5432`
# (NOT localhost, which refers to the FastAPI container itself).
docker run --rm --network ragnet -p 8080:8000 \
  -e DATABASE_URL="postgresql://postgres:example@postgres:5432/app" \
  fastapi-service:local
```

> Note: `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` only take effect the FIRST time
> the data directory is initialized. If `pgdata` is already initialized, changing these variables
> will not create a new database — use a fresh volume (a different `-v` name) or create the
> database manually with `psql` / a migration.

> Multi-service orchestration (running these together declaratively) is Day24 — Docker Compose.
> This example uses individual `docker` commands only.

## Immutable replacement (never edit a running container)

Rebuild and replace; do not `docker exec` into a running container to change code. The steps
below are self-contained (each container name is created before it is used).

```bash
# 1. Build v1 and start it as app-v1 on host port 8080.
docker build -t fastapi-service:v1 .
docker run -d --name app-v1 --network ragnet -p 8080:8000 fastapi-service:v1

# 2. After changing source/Dockerfile inputs, build a new immutable image v2.
docker build -t fastapi-service:v2 .

# 3. Start v2 as app-v2 on a DIFFERENT temporary host port (8081) so both run.
docker run -d --name app-v2 --network ragnet -p 8081:8000 fastapi-service:v2

# 4. Health-check app-v2 before sending it any real traffic.
curl -fsS http://localhost:8081/health

# 5. Switch traffic to app-v2. A plain `docker run` does NOT do this by itself:
#    in production, a reverse proxy or load balancer (e.g. Nginx) moves traffic
#    from the old container to the new one. Zero-downtime deployment is covered
#    in Day25 — Deployment Foundations.

# 6. Only after traffic is on app-v2, remove the old container.
docker rm -f app-v1
```
