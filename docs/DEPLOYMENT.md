# Deployment

## Local CLI (assignment deliverable)

```bash
cp .env.example .env
# edit .env as needed
marketplace-pipeline
# or: make run
```

Default `.env.example` uses all mocks + demo mode (100 products).

## Local API (HR / production-style demo)

```bash
make api
# OpenAPI: http://localhost:8000/docs
```

Submit jobs via `POST /api/v1/pipeline/jobs`. Job state in `data/jobs.sqlite` (configurable via `JOB_DB_PATH`).

## Docker

```bash
docker compose up --build
```

Two services in `docker-compose.yml`:

| Service | Command | Port |
|---------|---------|------|
| `pipeline` | `marketplace-pipeline` | — (one-shot CLI) |
| `api` | `marketplace-pipeline-api` | 8000 |

- Env from `.env.example` via `docker-compose.yml`
- Volume: `./data:/app/data` (enriched JSON, idempotency store, jobs SQLite)

```bash
docker compose up api --build   # API only
```

## Production-like run

```bash
DEMO_MODE=false
TARGET_PRODUCT_COUNT=10000
MOCK_PARSER=false
MOCK_LLM=false
MOCK_CRM=false

OPENAI_API_KEY=sk-...
AMOCRM_SUBDOMAIN=yourcompany
AMOCRM_ACCESS_TOKEN=...
AMOCRM_RESPONSIBLE_USER_ID=123456

marketplace-pipeline          # sync CLI
# or
marketplace-pipeline-api      # async job API
```

### Prerequisites

| Service | Requirement |
|---------|-------------|
| Ozon | Stable access to composer API; may need proxy if blocked |
| OpenAI | API key, sufficient quota (~400 batch calls for 10K) |
| AmoCRM | OAuth token with tasks scope |

## CI/CD

GitHub Actions on push/PR to `main`:

1. Lint (`ruff`)
2. Test (`pytest`, mocks enabled)
3. Docker build

No deploy step — assignment scope is build + test only.

## Data artifacts

| Path | Purpose | Git |
|------|---------|-----|
| `data/enriched_products.json` | Last run output | ignored |
| `data/crm_idempotency.json` | CRM dedupe store | ignored |
| `data/jobs.sqlite` | API job state | ignored |

Back up `crm_idempotency.json` and `jobs.sqlite` in production to preserve state across redeploys.

## Monitoring

Built-in (API):

- `GET /health` — liveness
- `GET /ready` — readiness (SQLite ping + writable data dir; returns 503 when not ready)
- `GET /metrics` — Prometheus counters + avg latency gauges
- Response headers: `X-Request-ID`, `X-Response-Time-Ms`
- Structured JSON logs when `LOG_JSON=true` (includes `correlation_id` on job runs)

Security (production):

- Set `API_KEY` — required for `/api/v1/*` via `X-API-Key` or `Authorization: Bearer`
- `API_RATE_LIMIT_PER_MINUTE` — per-IP rate limit on `/api/v1/*` (default 60/min); public paths exempt; Redis-backed when `REDIS_URL` set

Suggested alerts:

- Log lines: `Parser degraded`, `Category exhausted`, `CRM tasks: created=X reused=Y`, `Job … failed`
- Alert on `degraded=True` or `collected_count == 0`
- Track OpenAI token usage separately

## Scaling notes

- **Single-node (default):** `sqlite` + `thread` pool — no Redis required
- **Multi-node:** `pip install -e ".[scale]"` — see [docs/SCALE.md](SCALE.md)
- `docker compose --profile scale up --build` — Postgres + Redis + API + Celery worker
- API replicas share job state via PostgreSQL; workers scale horizontally via Celery
- Redis: Celery broker, CRM idempotency, job submit idempotency (`Idempotency-Key`), shared Prometheus job counters
- Enriched product output: JSON file (single-node) or PostgreSQL snapshots (`enriched_product_snapshots`) when `JOB_STORE_BACKEND=postgres`
- Run `alembic upgrade head` before scale deploy — see [docs/SCALE.md](SCALE.md)
- Optional: `OTEL_ENABLED`, `SENTRY_DSN` for distributed tracing / errors
