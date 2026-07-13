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
docker run -d --name postgres --network ragnet \
  -e POSTGRES_PASSWORD=example -v pgdata:/var/lib/postgresql/data postgres:16

# The FastAPI container on the same network reaches it as `postgres:5432`
# (NOT localhost, which refers to the FastAPI container itself).
docker run --rm --network ragnet -p 8080:8000 \
  -e DATABASE_URL="postgresql://postgres:example@postgres:5432/app" \
  fastapi-service:local
```

> Multi-service orchestration (running these together declaratively) is Day24 — Docker Compose.
> This example uses individual `docker` commands only.

## Immutable replacement (never edit a running container)

```bash
# Update source/Dockerfile inputs, then:
docker build -t fastapi-service:v2 .
docker run -d --name app-v2 --network ragnet -p 8081:8000 fastapi-service:v2
# health-check app-v2, switch traffic, then:
docker rm -f app-v1
```
