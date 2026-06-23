# Architecture

## Overview

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

`HttpClient` wraps httpx sync client:

- Retries: `RateLimitError` (429), `TransportError`
- Backoff: exponential, max 60s
- Configurable via `HTTP_MAX_RETRIES`, `HTTP_RETRY_BASE_DELAY`

## Configuration

Single `Settings` class (`pydantic-settings`):

- Env file `.env`
- `collection_target` property: demo vs production count

## Extension points

| Change | Approach |
|--------|----------|
| Wildberries | New parser class + factory branch |
| Bitrix24 | New CRM client implementing same `create_task` contract |
| YandexGPT | New classifier or strategy in `SegmentClassifier` |
| PostgreSQL | Insert persistence between pipeline stages |

## Failure modes

| Scenario | Behavior |
|----------|----------|
| Ozon 429 | Retry with backoff |
| Ozon persistent error | Graceful degradation |
| Category exhausted | `exhausted=True`, partial OK |
| LLM bad JSON | Raise in batch (pipeline fails) — consider soft-fail in prod |
| AmoCRM duplicate run | Idempotency store prevents duplicate POST |
| Missing AmoCRM creds | `ValueError` when `MOCK_CRM=false` |
