# Marketplace Pipeline

Пайплайн аналитики маркетплейса: сбор каталога Ozon → LLM-классификация по сегментам → создание задач в AmoCRM.

## Стек

| Компонент | Выбор |
|-----------|-------|
| Маркетплейс | Ozon (категория «Смартфоны») |
| LLM | OpenAI (`gpt-4o-mini`), батчинг по `LLM_BATCH_SIZE` |
| CRM | AmoCRM REST API v4 |
| API | FastAPI, async jobs, optional auth + rate limits |
| Scale (optional) | Celery + PostgreSQL + Redis |

## API

```bash
make api
# OpenAPI: http://localhost:8000/docs
curl -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 50}'
```

Async jobs (202), optional `Idempotency-Key`, `/health`, `/ready`, `/metrics`, `X-Request-ID`.  
Production: `API_KEY`, `LOG_JSON=true`; Redis-backed rate limit when `REDIS_URL` set.  
Подробная инструкция для ревьювера: [docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md).

### Multi-node (scale)

```bash
pip install -e ".[scale]"
docker compose --profile scale up --build
```

См. [docs/SCALE.md](docs/SCALE.md).

## Быстрый старт (CLI)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
marketplace-pipeline
```

Локальный прогон по умолчанию (через `.env.example`):

- `DEMO_MODE=true` — цель сбора 100 товаров вместо 10 000
- `MOCK_PARSER=true` — синтетический каталог без HTTP к Ozon
- `MOCK_LLM=true` — эвристическая классификация без OpenAI
- `MOCK_CRM=true` — логирование задач без AmoCRM

## Переменные окружения

См. [`.env.example`](.env.example) и [docs/ENV.md](docs/ENV.md).

| Переменная | Описание |
|------------|----------|
| `DEMO_MODE` / `TARGET_PRODUCT_COUNT` | Объём сбора |
| `MOCK_PARSER` / `MOCK_LLM` / `MOCK_CRM` | Offline режим |
| `JOB_DB_PATH` | SQLite jobs (default API store) |
| `JOB_STORE_BACKEND` | `sqlite` или `postgres` |
| `JOB_RUNNER_BACKEND` | `thread` или `celery` |
| `API_KEY` | Защита `/api/v1/*` (пусто = без auth) |
| `JOB_IDEMPOTENCY_TTL_SECONDS` | TTL для `Idempotency-Key` на submit job |
| `OZON_PAGE_SIZE` | Размер страницы Ozon (default 36) |
| `REDIS_URL` | Celery broker, Redis idempotency, shared metrics, distributed rate limit |

## Архитектура

Clean Architecture + DDD (v0.5) — [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md).

```
CLI:  interfaces/cli → Container → RunPipelineUseCase → ports → adapters
API:  interfaces/api → pipeline_jobs → JobRunnerPort → RunPipelineUseCase
Scale: marketplace-pipeline-worker (Celery) → shared executor → Postgres jobs
```

## Бизнес-правила

1. **Partial collection** — успех, если категория исчерпана.
2. **Graceful degradation** — парсер/LLM не валят пайплайн целиком.
3. **CRM-сегменты** — только Премиум (топ-5 DESC) и Эконом (топ-5 ASC).
4. **Идемпотентность CRM** — SHA-256, file или Redis store.
5. **Mock-парсер** — только `MOCK_PARSER=true`.

## Документация

| Файл | Описание |
|------|----------|
| [AGENTS.md](AGENTS.md) | Инструкции для AI-агентов |
| [vision.md](vision.md) | Исходное ТЗ |
| [AI_USAGE.md](AI_USAGE.md) | Лог использования ИИ |
| [docs/SCALE.md](docs/SCALE.md) | Multi-node deploy |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow, API |
| [docs/HR_DEMO.md](docs/HR_DEMO.md) | Демо для HR |
| [docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md) | **Инструкция для ревьювера** |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker и prod |

## Тесты

```bash
make test          # pytest, ≥95% coverage (~108 tests)
make ci            # ruff + pytest
```

## Docker

```bash
docker compose up --build              # local (CLI + API)
docker compose --profile scale up --build   # Postgres + Redis + worker
```

## CI

GitHub Actions: `ruff` → `pytest` (`.[scale]`) → `docker build`.

## Структура проекта

```
src/marketplace_pipeline/
  domain/              # entities, ports, domain services
  application/         # use cases
  infrastructure/      # adapters, factories, workers, observability
  interfaces/
    cli/               # marketplace-pipeline
    api/               # marketplace-pipeline-api
    worker/            # marketplace-pipeline-worker
tests/
  test_api.py, test_scale.py, test_prod_hardening.py, ...
```
