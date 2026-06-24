# Environment variables

All settings loaded via `pydantic-settings` from env and optional `.env` file.

## Modes

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEMO_MODE` | bool | false | Use reduced collection target |
| `DEMO_PRODUCT_COUNT` | int | 100 | Target when demo mode |
| `TARGET_PRODUCT_COUNT` | int | 10000 | Full collection target |
| `MOCK_PARSER` | bool | false | Synthetic catalog |
| `MOCK_LLM` | bool | false | Heuristic classification |
| `MOCK_CRM` | bool | false | Skip AmoCRM HTTP |

## Ozon

| Variable | Default |
|----------|---------|
| `OZON_CATEGORY_PATH` | `/category/smartfony-15502/` |
| `OZON_API_BASE_URL` | `https://www.ozon.ru/api/composer-api.bx/page/json/v2` |
| `OZON_PAGE_SIZE` | 36 |
| `OZON_REQUEST_TIMEOUT` | 30.0 |
| `OZON_REQUEST_DELAY_SECONDS` | 1.0 | Pause between Ozon page fetches (fixed when min/max unset) |
| `OZON_REQUEST_DELAY_MIN_SECONDS` | (unset) | Random jitter lower bound (with max, overrides fixed delay) |
| `OZON_REQUEST_DELAY_MAX_SECONDS` | (unset) | Random jitter upper bound |
| `OZON_FOLLOW_REDIRECTS` | true | Follow Ozon `__rr=1` redirects |
| `OZON_WARMUP_SESSION` | true | GET category page before composer API |
| `OZON_ROTATE_USER_AGENTS` | true | Random browser UA per retry |
| `OZON_PROXY_LIST` | (empty) | Comma-separated HTTP(S) proxies; rotated on 403/429 |
| `OZON_COOKIE` | (empty) | Optional `Cookie` header copied from browser session |

## proxy.market (live Ozon)

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_MARKET_API_KEY` | (empty) | Dashboard API key; enables pre-flight traffic check |
| `PROXY_MARKET_MIN_TRAFFIC_BYTES` | 1048576 | Fail fast when remaining package traffic is below this (1 MB) |

When `MOCK_PARSER=false`, `OZON_PROXY_LIST` is set, and `PROXY_MARKET_API_KEY` is set, the pipeline checks proxy.market packages before collection. Exhausted traffic → `ProxyQuotaExhaustedError` (CLI exit 1, API `402 Payment Required`). API docs: https://api.dashboard.proxy.market/docs

**Never commit** real `OZON_PROXY_LIST`, `PROXY_MARKET_API_KEY`, or `OZON_COOKIE` — use local `.env` only.

## OpenAI

| Variable | Default |
|----------|---------|
| `OPENAI_API_KEY` | (empty) |
| `OPENAI_MODEL` | gpt-4o-mini |
| `OPENAI_BASE_URL` | https://api.openai.com/v1 |
| `LLM_BATCH_SIZE` | 25 |
| `LLM_PROVIDER` | openai |

## AmoCRM

| Variable | Default |
|----------|---------|
| `AMOCRM_SUBDOMAIN` | (empty) |
| `AMOCRM_ACCESS_TOKEN` | (empty) |
| `AMOCRM_RESPONSIBLE_USER_ID` | 0 |
| `CRM_IDEMPOTENCY_ENABLED` | true |
| `CRM_IDEMPOTENCY_STORE_PATH` | data/crm_idempotency.json |

## HTTP / logging

| Variable | Default |
|----------|---------|
| `HTTP_MAX_RETRIES` | 5 |
| `HTTP_RETRY_BASE_DELAY` | 1.0 |
| `LOG_LEVEL` | INFO |

## API service (FastAPI)

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_DB_PATH` | data/jobs.sqlite | SQLite file for async job state |
| `API_JOB_WORKERS` | 2 | Thread pool size for background pipeline runs |
| `API_KEY` | (empty) | When set, protects `/api/v1/*` (header `X-API-Key` or Bearer) |
| `API_RATE_LIMIT_PER_MINUTE` | 60 | Per-IP sliding window on `/api/v1/*`; `0` disables. Public paths exempt. Uses Redis when `REDIS_URL` set |
| `JOB_IDEMPOTENCY_TTL_SECONDS` | 86400 | Job submit idempotency TTL when `Idempotency-Key` header is sent |
| `LOG_JSON` | false | Emit structured JSON logs to stdout |

Used by `marketplace-pipeline-api` / `make api`. CLI-only runs ignore these unless API is started.

## Distributed scale (`pip install -e ".[scale]"`)

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_STORE_BACKEND` | sqlite | `sqlite` or `postgres` |
| `DATABASE_URL` | (empty) | Required when `JOB_STORE_BACKEND=postgres` |
| `JOB_RUNNER_BACKEND` | thread | `thread` (single-node) or `celery` |
| `REDIS_URL` | (empty) | Celery broker, shared metrics, Redis idempotency, distributed API rate limit |
| `CELERY_BROKER_URL` | (empty) | Defaults to `REDIS_URL` |
| `CRM_IDEMPOTENCY_BACKEND` | file | `file` or `redis` |
| `OTEL_ENABLED` | false | OpenTelemetry traces |
| `OTEL_SERVICE_NAME` | marketplace-pipeline | Service name in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | http://localhost:4318/v1/traces | OTLP HTTP endpoint |
| `SENTRY_DSN` | (empty) | Sentry error tracking |
| `SENTRY_ENVIRONMENT` | production | Sentry environment tag |

Full guide: [docs/SCALE.md](SCALE.md).

## Recommended profiles

### Local dev / CI

```env
DEMO_MODE=true
MOCK_PARSER=true
MOCK_LLM=true
MOCK_CRM=true
```

### API demo (HR)

```env
DEMO_MODE=true
MOCK_PARSER=true
MOCK_LLM=true
MOCK_CRM=true
JOB_DB_PATH=data/jobs.sqlite
API_JOB_WORKERS=2
```

Start: `make api` → http://localhost:8000/docs

### Staging (real APIs, small volume)

```env
DEMO_MODE=true
DEMO_PRODUCT_COUNT=50
MOCK_PARSER=false
MOCK_LLM=false
MOCK_CRM=false
OPENAI_API_KEY=...
AMOCRM_SUBDOMAIN=...
AMOCRM_ACCESS_TOKEN=...
```

### Production

```env
DEMO_MODE=false
TARGET_PRODUCT_COUNT=10000
MOCK_PARSER=false
MOCK_LLM=false
MOCK_CRM=false
CRM_IDEMPOTENCY_ENABLED=true
JOB_DB_PATH=/var/lib/marketplace-pipeline/jobs.sqlite
API_JOB_WORKERS=4
API_KEY=your-secret-key
API_RATE_LIMIT_PER_MINUTE=120
LOG_JSON=true
```
