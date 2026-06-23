# Architecture

## Overview

### CLI pipeline (assignment core)

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐    ┌──────────────┐
│   Parser    │───▶│ SegmentClassifier │───▶│  Selectors  │───▶│  AmoCRMClient │
│ Ozon / Mock │    │  OpenAI / Mock   │    │ top-5 × 2   │    │ + idempotency │
└─────────────┘    └──────────────────┘    └─────────────┘    └──────────────┘
       │                    │                                        │
       ▼                    ▼                                        ▼
  Product[]          EnrichedProduct[]                    data/crm_idempotency.json
       │                    │
       └────────────┬───────┘
                    ▼
         data/enriched_products.json
```

### API layer (v0.5 — production hardening)

```
Client ──POST /api/v1/pipeline/jobs──▶ FastAPI (202)
              │  (API_KEY + rate limit on /api/v1/*) │
              │  optional Idempotency-Key header      │
              │                              ▼
              │                    validate_pipeline_prerequisites
              │                              │
              │                              ▼
              │                    SubmitPipelineJobUseCase
              │                    (+ job idempotency store)
              │                              │
              │                              ▼
              │                    PipelineJobRunner (thread | Celery)
              │                              │
              │                              ▼
              └────GET /jobs/{id}──── RunPipelineUseCase → adapters
                                              │
                                              ▼
                              SQLite WAL | PostgreSQL (Alembic schema)
```

Long-running work never blocks the HTTP thread. Job status persisted in SQLite or PostgreSQL; poll until `completed` or `failed`.

Production: `API_KEY` (`secrets.compare_digest`), `LOG_JSON=true`; `/ready` checks DB + data dir (+ Redis in scale).  
`/health`, `/ready`, `/metrics`, `/docs` are public — no auth or rate limit.  
Rate limit: in-memory per replica, or Redis sliding window when `REDIS_URL` is set.  
Metrics: `MetricsRegistry` in `infrastructure/observability/metrics.py` (in-memory or Redis counters).

## Data model

### Product (parsed)

| Field | Type | Notes |
|-------|------|-------|
| id | str | Marketplace SKU |
| name | str | Title |
| price | float | ≥ 0 |
| currency | str | Default RUB |
| url | HttpUrl | Product page |
| category | str | Fixed per parser |
| collected_at | datetime | UTC |
| description | str | For LLM; may be synthetic |

### EnrichedProduct

Extends `Product` with `segment: PriceSegment` (Эконом | Стандарт | Премиум).

### PipelineJob (API)

| Field | Notes |
|-------|-------|
| id | UUID |
| status | pending → running → completed \| failed |
| collection_target | Per-job override of settings |
| collected_count, classified_count, crm_tasks_count | Filled on completion |
| correlation_id | From `X-Request-ID` header |
| error_message | Set when status=failed |

### CRM flow

1. `build_crm_tasks()` → 0–2 `CRMTaskPayload` (title + markdown product list)
2. `compute_idempotency_key(payload)` → SHA-256
3. Check `IdempotencyStore` → if hit, return `reused=True`
4. Else POST AmoCRM `/api/v4/tasks` with marker `[pipeline:idempotency:KEY]`
5. Persist mapping key → task_id

## Parser layer

### OzonParser

- Uses Ozon composer API (`OZON_API_BASE_URL?url=<category path>`)
- Paginates `?page=N` until target count or empty page (`OZON_PAGE_SIZE` per request)
- Regex extraction from `widgetStates` JSON strings
- On exception: `degraded=True`, return partial list

### MockParser

- Deterministic products `mock-1..N` with tiered prices
- Used when `MOCK_PARSER=true` (CI, local dev)

## LLM layer

- Batches of `LLM_BATCH_SIZE` (default 25)
- OpenAI chat completions, `response_format: json_object`
- Invalid/missing segments → fallback «Стандарт»
- `MOCK_LLM`: keyword + price heuristics

## HTTP layer

`HttpClient` wraps a **shared** httpx sync client (connection pooling):

- Retries: `RateLimitError` (429), `TransportError`
- Backoff: exponential, max 60s
- Configurable via `HTTP_MAX_RETRIES`, `HTTP_RETRY_BASE_DELAY`
- Context manager: `with HttpClient() as client:` closes pool on exit
- `Container` owns one client; job runner closes it after each job

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/pipeline/jobs` | Submit job (202), body: `{ "collection_target": N }` optional; header `Idempotency-Key` optional |
| GET | `/api/v1/pipeline/jobs/{id}` | Poll job status |
| GET | `/api/v1/pipeline/jobs` | List recent jobs (`limit` query param) |
| GET | `/health` | Liveness |
| GET | `/ready` | Readiness |
| GET | `/metrics` | Prometheus-style counters |
| GET | `/docs` | OpenAPI UI |

Middleware: `X-Request-ID`, `X-Response-Time-Ms`, API key auth on `/api/v1/*`, rate limit on `/api/v1/*`.

OpenAPI documents `ApiKeyAuth` / `BearerAuth` security schemes when `API_KEY` is set.

## Configuration

Single `Settings` class (`pydantic-settings`):

- Env file `.env`
- `collection_target` property: demo vs production count
- `job_db_path`, `api_job_workers` for API service

## Extension points

| Change | Approach |
|--------|----------|
| Wildberries | New parser class + factory branch |
| Bitrix24 | New CRM client implementing same `create_task` contract |
| YandexGPT | New classifier or strategy in `SegmentClassifier` |
| PostgreSQL jobs | `PostgresJobRepository` + Alembic migrations (`pipeline_jobs`) |
| PostgreSQL enriched output | `PostgresEnrichedProductRepository` (`enriched_product_snapshots`) |
| Celery/RQ | Replace `PipelineJobRunner` thread pool; keep use cases |

## Failure modes

| Scenario | Behavior |
|----------|----------|
| Ozon 429 | Retry with backoff |
| Ozon persistent error | Graceful degradation |
| Category exhausted | `exhausted=True`, partial OK |
| LLM bad JSON | Soft-fail batch → fallback «Стандарт» (pipeline continues) |
| AmoCRM duplicate run | Idempotency store prevents duplicate POST |
| Missing AmoCRM creds | `CrmConfigurationError` when `MOCK_CRM=false` |
| Pipeline job failure | Job status `failed`, `error_message` set; HTTP 202 already returned |
