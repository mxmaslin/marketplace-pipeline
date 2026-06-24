# Инструкция для ревьювера

Подробный чеклист: как поднять проект, что проверить и куда смотреть в коде.  
Расчётное время: **15–20 мин** (быстрый проход) или **40–60 мин** (полный).

---

## 0. Что это за проект

Пайплайн по [vision.md](../vision.md):

```
Ozon (парсинг) → OpenAI (сегменты) → AmoCRM (задачи)
```

Дополнительно сверх ТЗ:

- **Clean Architecture + DDD** (слои, ports & adapters)
- **FastAPI** — async jobs (202 + polling)
- **Production hardening** — auth, rate limit, probes, metrics
- **Scale stack** (опционально) — Celery + PostgreSQL + Redis

Версия: **v0.5.0**. Лог работы с ИИ: [AI_USAGE.md](../AI_USAGE.md).

---

## 1. Требования к окружению

| Компонент | Версия |
|-----------|--------|
| Python | 3.11+ |
| pip | актуальный |
| Docker + Compose | для контейнерного прогона (опционально) |
| `jq` | удобно для curl, не обязательно |

Ключи OpenAI / AmoCRM / доступ к Ozon **не нужны** для базовой проверки — всё работает на mock-режиме.

---

## 2. Быстрый старт (рекомендуемый порядок)

### Шаг 1 — клонирование и установка

```bash
git clone https://github.com/mxmaslin/marketplace-pipeline.git
cd marketplace-pipeline

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev,scale]"
cp .env.example .env             # можно не редактировать — моки уже включены
```

### Шаг 2 — quality gates (≈2 мин)

```bash
make ci
# эквивалент: ruff check src tests && pytest
```

**Ожидаемый результат:**

- `ruff` — без ошибок
- `pytest` — **137 passed**, coverage **≥95%** (сейчас ~95%)

HTML-отчёт покрытия (опционально):

```bash
make coverage
open htmlcov/index.html
```

### Шаг 3 — CLI smoke (≈30 сек)

```bash
make run
```

**Ожидаемый результат:**

- Процесс завершается с кодом 0
- В логах: `Collected N/N products`, `CRM tasks: created=… reused=…`
- Файл `data/enriched_products.json` создан/обновлён

### Шаг 4 — API smoke (≈3 мин)

Терминал 1:

```bash
make api
```

Открыть в браузере: **http://localhost:8000/docs**

Терминал 2 — submit job:

```bash
curl -s -D - -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 20}'
```

**На что обратить внимание в ответе:**

| Что | Ожидание |
|-----|----------|
| HTTP статус | `202 Accepted` |
| Заголовок | `X-Request-ID: <uuid>` |
| Тело JSON | `"status": "pending"`, поле `"id"` |

Poll до завершения (подставить `JOB_ID`):

```bash
export JOB_ID="<id из ответа>"
curl -s http://localhost:8000/api/v1/pipeline/jobs/$JOB_ID | jq
```

**Ожидаемая цепочка статусов:** `pending` → `running` → `completed`

В финальном ответе:

- `collected_count` = 20
- `classified_count` = 20
- `crm_tasks_count` = 2 (Премиум + Эконом, по 5 товаров в задаче)
- `error_message` = null

### Шаг 5 — probes и metrics (≈1 мин)

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq
curl -s http://localhost:8000/metrics
```

**`/health`** — всегда 200, `"status": "ok"`, `"version": "0.5.0"`.

**`/ready`** — 200, `"ready": true`, `"job_db_ok": true`, `"data_dir_writable": true`.

**`/metrics`** — Prometheus-текст с `pipeline_jobs_submitted_total`, `pipeline_jobs_completed_total`, `http_requests_total`.

---

## 3. Swagger UI — куда тыкать

URL: **http://localhost:8000/docs**

| Раздел | Действие | Что проверить |
|--------|----------|---------------|
| **Pipeline Jobs → POST** | `Try it out` → body `{"collection_target": 15}` → Execute | 202, схема `JobResponse` |
| **Pipeline Jobs → GET /{job_id}** | Вставить id из POST | Статус, счётчики |
| **Pipeline Jobs → GET** (list) | Execute | `count` ≥ 1 |
| **Health → GET /health** | Execute | 200 |
| **Health → GET /ready** | Execute | 200, детальные checks |

Схемы запросов/ответов — внизу каждого endpoint (OpenAPI).

---

## 4. Проверка требований ТЗ (vision.md)

### 4.1 Парсинг

| Требование | Где смотреть | Как проверить |
|------------|--------------|---------------|
| Категория Ozon | `infrastructure/adapters/parsers/ozon_collector.py` | `OZON_CATEGORY_PATH` в `.env.example` |
| Пагинация | `ozon_collector.py` → `collect()` | `tests/test_ozon_collect.py` |
| `OZON_PAGE_SIZE` | `settings.ozon_page_size` | `test_ozon_collect_10k_target_smoke` |
| Retry 429 | `infrastructure/http/http_client.py` | `tests/test_coverage.py::test_http_client_post_retries_429` |
| Graceful degradation | `ozon_collector.py` → `degraded=True` | `tests/test_ozon_collect.py::test_ozon_collect_degraded` |
| DEMO_MODE | `settings.py` → `collection_target` | `make run` собирает 100, не 10K |

### 4.2 LLM

| Требование | Где смотреть | Как проверить |
|------------|--------------|---------------|
| Pydantic-схема | `domain/entities/product.py`, `enriched_product.py` | типы в OpenAPI / коде |
| 3 сегмента | `domain/value_objects/price_segment.py` | Эконом / Стандарт / Премиум |
| Батчинг | `openai_classifier.py` → `_chunk()` | `LLM_BATCH_SIZE=25`, тесты `test_llm.py` |
| MOCK_LLM | `settings.mock_llm` | `make run` без OpenAI ключа |
| Soft-fail | `openai_classifier.py` → fallback «Стандарт» | `tests/test_prod_hardening.py` |

### 4.3 CRM

| Требование | Где смотреть | Как проверить |
|------------|--------------|---------------|
| Топ-5 Премиум / Эконом | `domain/services/crm_task_factory.py` | логи `make run`: 2 задачи |
| Стандарт не в CRM | `crm_task_factory.py` | только 2 задачи, не 3 |
| REST AmoCRM | `infrastructure/adapters/crm/amocrm_gateway.py` | `tests/test_crm.py` (httpx mock) |
| Идемпотентность | `domain/services/idempotency_policy.py` | `pytest -k idempotency` |
| MOCK_CRM | `settings.mock_crm` | `make run` без AmoCRM |

### 4.4 Инфраструктура ТЗ

| Требование | Где |
|------------|-----|
| pytest ≥70% | `pyproject.toml` → `--cov-fail-under=95` |
| AI_USAGE.md | корень репозитория |
| docker-compose | `docker-compose.yml` |
| CI | `.github/workflows/ci.yml` |
| README + .env.example | корень |

---

## 5. Архитектура — куда смотреть в коде

Рекомендуемый маршрут (15 мин чтения):

```
1. docs/CLEAN_ARCHITECTURE.md     — карта слоёв
2. domain/ports/                  — контракты (Protocol)
3. application/use_cases/run_pipeline.py  — оркестрация
4. infrastructure/composition/container.py — DI
5. infrastructure/composition/factories.py   — выбор SQLite/Postgres, thread/Celery
6. interfaces/api/routes/jobs.py  — тонкий HTTP-слой
```

**Правило зависимостей:** `domain/` не импортирует `httpx`, `fastapi`, `settings`.

Проверка одной командой:

```bash
rg "from marketplace_pipeline\.(infrastructure|interfaces|application)" src/marketplace_pipeline/domain/
# ожидается: 0 совпадений
```

---

## 6. Production-фичи (v0.4+)

### 6.1 API Key

В `.env`:

```env
API_KEY=test-secret-key
```

Перезапустить API. Без ключа:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 5}'
# ожидается: 401
```

С ключом:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "X-API-Key: test-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 5}'
# ожидается: 202
```

`/health`, `/ready`, `/metrics`, `/docs` остаются без ключа.

### 6.2 Pre-flight validation

```bash
# В .env: MOCK_LLM=false, OPENAI_API_KEY пустой
curl -s -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 5}' | jq
# ожидается: 422, detail про OPENAI_API_KEY
```

### 6.3 Идемпотентность CRM (повторный прогон)

```bash
make run    # первый раз — created=2
make run    # второй раз — reused=2 в логах
```

Или: `pytest tests/test_idempotency.py -v`

### 6.4 Rate limit

Публичные пути (`/health`, `/ready`, `/metrics`, `/docs`, OpenAPI) **не** лимитируются.  
При `REDIS_URL` — распределённый лимитер (Redis); иначе in-memory per replica.

```bash
# API_RATE_LIMIT_PER_MINUTE=1 в .env, перезапуск
curl -s http://localhost:8000/health                    # 200 (exempt)
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/v1/pipeline/jobs              # 200
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/v1/pipeline/jobs              # 429
```

### 6.5 Job submit idempotency (`Idempotency-Key`)

Повторный POST с тем же заголовком возвращает тот же job id (202), без второго запуска:

```bash
curl -s -D - -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-1" \
  -d '{"collection_target": 10}'
# повторить — тот же id в теле
```

Store: in-memory (default) или Redis при `REDIS_URL`. TTL: `JOB_IDEMPOTENCY_TTL_SECONDS` (default 86400).

Тесты: `pytest tests/test_api.py -k idempotency -v`

---

## 7. Docker

### Локальный профиль (CLI + API)

```bash
docker compose up --build
```

| Сервис | Порт | Назначение |
|--------|------|------------|
| `api` | 8000 | FastAPI |
| `pipeline` | — | one-shot CLI |

Проверка: `curl http://localhost:8000/health`

Только API:

```bash
docker compose up api --build
```

### Scale-профиль (опционально, ≈5 мин)

```bash
docker compose --profile scale up --build
# или: make scale-up
```

Перед первым запуском с Postgres (вне Docker): `alembic upgrade head` — см. [SCALE.md](SCALE.md).

Поднимает: **postgres**, **redis**, **api-scale**, **worker**.

```bash
curl -s http://localhost:8000/ready | jq
# redis_ok: true, job_store: "postgres"
```

Подробнее: [docs/SCALE.md](SCALE.md).

---

## 8. Структура тестов

```bash
pytest tests/test_api.py -v           # API end-to-end
pytest tests/test_pipeline.py -v      # CLI pipeline
pytest tests/test_idempotency.py -v   # CRM dedupe
pytest tests/test_crm.py -v           # AmoCRM HTTP mocks
pytest tests/test_scale.py -v         # Celery/Postgres/Redis factories
pytest tests/domain/ -v               # чистая domain-логика
```

Все внешние HTTP замоканы через `pytest-httpx` — **реальный интернет не нужен**.

---

## 9. Артефакты на диске

После прогонов появляются (в `.gitignore`, в репозиторий не коммитятся):

| Файл | Содержимое |
|------|------------|
| `data/enriched_products.json` | Результат последнего pipeline |
| `data/crm_idempotency.json` | Ключи идемпотентности CRM |
| `data/jobs.sqlite` | Состояние async jobs (API) |

Проверить enriched output:

```bash
jq '.meta.collected_count, (.products | length)' data/enriched_products.json
```

---

## 10. Чеклист ревьюера

### Минимум (сдать/не сдать)

- [ ] `make ci` проходит
- [ ] `make run` завершается успешно, `data/enriched_products.json` есть
- [ ] API: POST job → 202, poll → `completed`
- [ ] `GET /health`, `/ready`, `/metrics` отвечают
- [ ] `AI_USAGE.md` заполнен
- [ ] README понятен, `.env.example` есть
- [ ] `docker compose up --build` собирается

### Архитектура

- [ ] Слои разделены (domain / application / infrastructure / interfaces)
- [ ] Ports в domain, адаптеры в infrastructure
- [ ] Use case не содержит HTTP/LLM-деталей
- [ ] Долгие job не блокируют HTTP-thread

### Бизнес-логика

- [ ] Partial collection — warning, не crash
- [ ] Parser degraded — partial OK
- [ ] CRM: 2 задачи (Премиум top-5, Эконом top-5)
- [ ] Повторный прогон → `reused=true`
- [ ] Стандарт классифицируется, но не уходит в CRM

### Production (бонус)

- [ ] `API_KEY` блокирует `/api/v1/*`
- [ ] `/ready` возвращает 503 при недоступной БД (можно удалить `data/jobs.sqlite` при остановленном API)
- [ ] Метрики инкрементируются после job
- [ ] Scale profile поднимается (если есть Docker)

---

## 11. Типичные проблемы

| Симптом | Решение |
|---------|---------|
| `pytest` не найден | `pip install -e ".[dev,scale]"` |
| Порт 8000 занят | `lsof -i :8000`, убить процесс или сменить порт uvicorn |
| Job зависает в `pending` | Проверить логи API; `API_JOB_WORKERS` ≥ 1 |
| `ready: false` | Права на `./data`, SQLite доступен |
| Docker build падает | `docker compose build --no-cache` |
| Scale: worker не стартует | `docker compose logs worker`, проверить redis/postgres health |

---

## 12. Карта документации

| Документ | Для чего |
|----------|----------|
| [README.md](../README.md) | Обзор, quick start |
| [vision.md](../vision.md) | Исходное ТЗ |
| [AI_USAGE.md](../AI_USAGE.md) | Лог ИИ (deliverable) |
| [docs/CLEAN_ARCHITECTURE.md](CLEAN_ARCHITECTURE.md) | Слои и DDD |
| [docs/ARCHITECTURE.md](ARCHITECTURE.md) | Data flow, API |
| [docs/ENV.md](ENV.md) | Все переменные окружения |
| [docs/TESTING.md](TESTING.md) | Паттерны тестов |
| [docs/DEPLOYMENT.md](DEPLOYMENT.md) | Docker, prod |
| [docs/SCALE.md](SCALE.md) | Multi-node |
| [docs/HR_DEMO.md](HR_DEMO.md) | Короткий сценарий 5–7 мин |

---

## 13. Сценарий live-demo (5–7 мин)

Если кандидат показывает устно — см. [docs/HR_DEMO.md](HR_DEMO.md). Кратко:

1. `make ci` — «всё зелёное, 108+ тестов»
2. `make api` → `/docs` — submit job
3. Poll → `completed`, показать счётчики
4. `/metrics`, `/ready`
5. `make run` — CLI из ТЗ
6. Открыть `docs/CLEAN_ARCHITECTURE.md` — слои
7. Показать `idempotency_policy.py` + повторный `make run` → reused

---

## 14. Что сознательно вне scope

- Реальный сбор 10K с Ozon без mock (нужен доступ к API, anti-bot, **proxy.market трафик**)
- Боевые задачи в AmoCRM (нужен OAuth token)
- Kubernetes / Terraform
- Полноценный staging с OTEL collector (хуки есть, деплой — на стороне ops)

Это описано в README и `AI_USAGE.md` — не баг, а ограничение тестового задания.

---

## 15. Live Ozon + proxy.market (опционально)

> **Секреты не в репозитории.** Для live-сбора нужны **свои** учётные данные в локальном `.env` (файл в `.gitignore`): прокси-лист, API-ключ proxy.market, при необходимости `OZON_COOKIE`, OpenAI, AmoCRM. В репозитории только плейсхолдеры в `.env.example`.

Для **реального** сбора (не mock) кандидат может использовать [proxy.market](https://proxy.market) — резидентские прокси RU, липкая сессия.

| Переменная | Назначение |
|------------|------------|
| `MOCK_PARSER=false` | Включить живой Ozon |
| `OZON_PROXY_LIST` | `http://login:pass@pool.proxy.market:10000` |
| `PROXY_MARKET_API_KEY` | API-ключ из ЛК (доки: https://api.dashboard.proxy.market/docs) |

**Pre-flight:** при наличии API-ключа пайплайн проверяет остаток трафика в пакете **до** сбора. Если трафик закончился:

- CLI → exit `1`, сообщение `PROXY_MARKET traffic exhausted … Top up at https://proxy.market`
- API → HTTP `402 Payment Required` на `POST /api/v1/pipeline/jobs`

**Для ревьюера:** mock-режим (`make run`) **не требует** прокси и API-ключа. Проверка quota покрыта unit-тестами (`tests/test_proxy_market_quota.py`).

**Ориентир по трафику:** демо 50 товаров ~20–80 MB; полный 10K может потребовать 0.5–2 GB (зависит от 403/ретраев).
