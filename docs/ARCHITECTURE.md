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

### API layer (v0.3 — production-style demo)

```
Client ──POST /api/v1/pipeline/jobs──▶ FastAPI (202)
              │                              │
              │                              ▼
              │                    SubmitPipelineJobUseCase
              │                              │
              │                              ▼
              │                    PipelineJobRunner (thread pool)
              │                              │
              │                              ▼
              └────GET /jobs/{id}──── RunPipelineUseCase → adapters
                                              │
                                              ▼
                                    SQLite (data/jobs.sqlite)
```

Long-running work never blocks the HTTP thread. Job status persisted in SQLite; poll until `completed` or `failed`.

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
- Paginates `?page=N` until target count or empty page
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
| POST | `/api/v1/pipeline/jobs` | Submit job (202), body: `{ "collection_target": N }` optional |
| GET | `/api/v1/pipeline/jobs/{id}` | Poll job status |
| GET | `/api/v1/pipeline/jobs` | List recent jobs (`limit` query param) |
| GET | `/health` | Liveness |
| GET | `/ready` | Readiness |
| GET | `/metrics` | Prometheus-style counters |
| GET | `/docs` | OpenAPI UI |

Middleware: `X-Request-ID`, `X-Response-Time-Ms`.

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
| PostgreSQL | Replace `SqliteJobRepository` or add enriched-product store |
| Celery/RQ | Replace `PipelineJobRunner` thread pool; keep use cases |

## Failure modes

| Scenario | Behavior |
|----------|----------|
| Ozon 429 | Retry with backoff |
| Ozon persistent error | Graceful degradation |
| Category exhausted | `exhausted=True`, partial OK |
| LLM bad JSON | Raise in batch (pipeline fails) — consider soft-fail in prod |
| AmoCRM duplicate run | Idempotency store prevents duplicate POST |
| Missing AmoCRM creds | `CrmConfigurationError` when `MOCK_CRM=false` |
| Pipeline job failure | Job status `failed`, `error_message` set; HTTP 202 already returned |
