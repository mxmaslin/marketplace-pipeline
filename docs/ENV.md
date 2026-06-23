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

## Recommended profiles

### Local dev / CI

```env
DEMO_MODE=true
MOCK_PARSER=true
MOCK_LLM=true
MOCK_CRM=true
```

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
```
