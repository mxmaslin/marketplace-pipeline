# Multi-node scale stack

Distributed deployment: **PostgreSQL** (jobs) + **Redis** (Celery broker, idempotency, shared metrics) + **Celery workers**.

## Quick start (Docker)

```bash
docker compose --profile scale up --build
# API: http://localhost:8000/docs
```

Services: `postgres`, `redis`, `api-scale`, `worker`.

## Install

```bash
pip install -e ".[scale]"
```

## Environment

| Variable | Value (scale) |
|----------|----------------|
| `JOB_STORE_BACKEND` | `postgres` |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/pipeline` |
| `JOB_RUNNER_BACKEND` | `celery` |
| `REDIS_URL` | `redis://host:6379/0` |
| `CELERY_BROKER_URL` | same as Redis (optional override) |
| `CRM_IDEMPOTENCY_BACKEND` | `redis` |
| `JOB_IDEMPOTENCY_TTL_SECONDS` | `86400` (optional) |

See [`.env.scale.example`](../.env.scale.example).

## Database migrations

When using PostgreSQL, apply Alembic migrations before starting API or workers:

```bash
export DATABASE_URL=postgresql://pipeline:pipeline@localhost:5432/pipeline
alembic upgrade head
```

Migrations create `pipeline_jobs` and `enriched_product_snapshots` tables. Schema is owned by Alembic — do not rely on runtime DDL.

In Docker scale profile, run migrations once after Postgres is healthy:

```bash
docker compose --profile scale run --rm api-scale alembic upgrade head
```

(`alembic.ini` and `alembic/` must be present in the image — included in scale builds.)

## Processes

| Command | Role |
|---------|------|
| `marketplace-pipeline-api` | FastAPI — submit/poll jobs |
| `marketplace-pipeline-worker` | Celery worker — runs pipelines |
| `marketplace-pipeline` | CLI one-shot (unchanged) |

## Observability (optional)

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318/v1/traces
SENTRY_DSN=https://...
```

Requires `pip install -e ".[scale]"`.

## Architecture

```
API (N replicas) ──enqueue──▶ Redis/Celery ──▶ Worker (M replicas)
       │                              │
       ▼                              ▼
  PostgreSQL ◀─────────────────────────┘
       │
  Redis (idempotency + metrics counters)
```

Local / CI default remains `sqlite` + `thread` pool — no Redis required.
