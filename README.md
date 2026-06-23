# Marketplace Pipeline

Пайплайн аналитики маркетплейса: сбор каталога Ozon → LLM-классификация по сегментам → создание задач в AmoCRM.

## Стек

| Компонент | Выбор |
|-----------|-------|
| Маркетплейс | Ozon (категория «Смартфоны») |
| LLM | OpenAI (`gpt-4o-mini`), батчинг по `LLM_BATCH_SIZE` |
| CRM | AmoCRM REST API v4 |

## API (production-style demo)

```bash
make api
# OpenAPI: http://localhost:8000/docs
curl -X POST http://localhost:8000/api/v1/pipeline/jobs -H "Content-Type: application/json" -d '{"collection_target": 50}'
```

Async jobs (202), SQLite store, `/health`, `/ready`, `/metrics`, `X-Request-ID`.  
Полный сценарий для HR: [docs/HR_DEMO.md](docs/HR_DEMO.md).

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

См. [`.env.example`](.env.example).

| Переменная | Описание |
|------------|----------|
| `DEMO_MODE` | Уменьшенный объём сбора |
| `DEMO_PRODUCT_COUNT` | Целевое число товаров в demo (по умолчанию 100) |
| `TARGET_PRODUCT_COUNT` | Полный объём (10 000) |
| `MOCK_PARSER` | Синтетический парсер |
| `MOCK_LLM` | Mock-классификатор |
| `MOCK_CRM` | Mock CRM |
| `OPENAI_API_KEY` | Ключ OpenAI (если `MOCK_LLM=false`) |
| `AMOCRM_SUBDOMAIN`, `AMOCRM_ACCESS_TOKEN` | AmoCRM (если `MOCK_CRM=false`) |
| `CRM_IDEMPOTENCY_ENABLED` | Идемпотентность CRM (по умолчанию `true`) |
| `CRM_IDEMPOTENCY_STORE_PATH` | Путь к JSON-store ключей |
| `JOB_DB_PATH` | SQLite для async jobs (API) |
| `API_JOB_WORKERS` | Размер thread pool для фоновых job |

## Архитектура

Clean Architecture + DDD (v0.3) — [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md).

```
CLI:  interfaces/cli → Container → RunPipelineUseCase → ports → adapters
API:  interfaces/api → pipeline_jobs use cases → PipelineJobRunner → RunPipelineUseCase
```

Фасад `Pipeline` (legacy) делегирует в use case. Результат: `data/enriched_products.json`.  
API jobs: `data/jobs.sqlite`, poll `GET /api/v1/pipeline/jobs/{id}`.

## Бизнес-правила (зафиксированные трактовки)

1. **Partial collection**: если в категории меньше записей, чем `TARGET_PRODUCT_COUNT`, пайплайн завершается успешно с warning в логах.
2. **Graceful degradation**: при ошибках парсера сохраняется уже собранное; LLM/CRM выполняются для доступного объёма.
3. **CRM-сегменты**: в CRM уходят только **Премиум** (топ-5 по `price` DESC) и **Эконом** (топ-5 по `price` ASC). Сегмент **Стандарт** классифицируется, но задачи не создаёт.
4. **Идемпотентность CRM**: повторный прогон с тем же набором товаров не создаёт дубликаты задач. Ключ = SHA-256(title + description). Локальный store `data/crm_idempotency.json`; в AmoCRM в текст задачи добавляется маркер `[pipeline:idempotency:…]`. При пустом store — поиск по маркеру в последних задачах API.
5. **Mock-парсер**: только env-флаг `MOCK_PARSER=true` (без отдельного mock-сервиса).

## Документация

| Файл | Описание |
|------|----------|
| [AGENTS.md](AGENTS.md) | Инструкции для AI-агентов |
| [vision.md](vision.md) | Исходное ТЗ |
| [AI_USAGE.md](AI_USAGE.md) | Лог использования ИИ (deliverable) |
| [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) | Слои Clean Architecture + DDD |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow, API, job lifecycle |
| [docs/HR_DEMO.md](docs/HR_DEMO.md) | Сценарий демо для HR (API, curl, talking points) |
| [docs/ENV.md](docs/ENV.md) | Переменные окружения |
| [docs/TESTING.md](docs/TESTING.md) | Тестирование |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Как контрибутить |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker и prod |

Cursor: правила в [`.cursor/rules/`](.cursor/rules/), skill [`.cursor/skills/marketplace-pipeline/`](.cursor/skills/marketplace-pipeline/SKILL.md).

## Тесты

```bash
make test          # или pytest
make coverage      # HTML-отчёт
```

Покрытие **≥95%**, HTTP-моки через `pytest-httpx`.

## Docker

```bash
docker compose up --build
```

## CI

GitHub Actions: `ruff` → `pytest` → `docker build` (см. [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Известные ограничения

- Реальный парсинг Ozon зависит от доступности composer API и anti-bot политик; для prod рекомендуется официальный seller API или прокси.
- LLM-батчи ограничены `LLM_BATCH_SIZE`; при невалидном ответе сегмент fallback → «Стандарт».
- Remote-reconcile AmoCRM сканирует до 5×250 последних задач; для очень больших аккаунтов может потребоваться расширение.
- Масштабирование до 10K: увеличьте `TARGET_PRODUCT_COUNT`, отключите `DEMO_MODE` и mock-флаги, настройте ключи API.

## Структура проекта

```
src/marketplace_pipeline/
  domain/              # entities, ports, domain services, PipelineJob
  application/         # RunPipelineUseCase, pipeline_jobs use cases
  infrastructure/      # adapters, Container, HttpClient, job runner, SQLite
  interfaces/
    cli/               # marketplace-pipeline
    api/               # marketplace-pipeline-api (FastAPI)
  models.py, pipeline.py, parser/, crm/, llm/   # legacy shims
tests/
  test_api.py, test_job_repository.py, test_job_runner.py
  test_pipeline.py, test_crm.py, ...
```
