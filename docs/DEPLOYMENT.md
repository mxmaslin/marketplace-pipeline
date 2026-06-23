# Deployment

## Local (recommended for demo)

```bash
cp .env.example .env
# edit .env as needed
marketplace-pipeline
```

Default `.env.example` uses all mocks + demo mode (100 products).

## Docker

```bash
docker compose up --build
```

- Image runs `marketplace-pipeline` on start
- Env from `.env.example` baked via `docker-compose.yml`
- Output volume: `./data:/app/data`

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

marketplace-pipeline
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

Back up `crm_idempotency.json` in production to preserve idempotency across redeploys.

## Monitoring (suggested for prod)

- Log lines: `Parser degraded`, `Category exhausted`, `CRM tasks: created=X reused=Y`
- Alert on `degraded=True` or `collected_count == 0`
- Track OpenAI token usage separately

## Scaling notes

- 10K parse: sequential pages; consider async + rate limiter for prod
- LLM: increase `LLM_BATCH_SIZE` cautiously (token limits)
- Idempotency remote scan: 5×250 tasks max; extend if large AmoCRM account
