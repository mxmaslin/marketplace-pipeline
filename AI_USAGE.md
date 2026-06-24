# AI Usage Log

Документ описывает, как использовался ИИ-агент (Cursor) при выполнении тестового задания.

## Исходный запрос

Реализовать пайплайн из `vision.md`: парсинг маркетплейса, LLM-классификация, интеграция с CRM, pytest ≥70%, Docker, CI, README.

## Архитектурные решения (согласованы с кандидатом)

| Решение | Обоснование |
|---------|-------------|
| Ozon + OpenAI + AmoCRM | Соответствует стеку вакансии Интерика Лаб |
| `MOCK_PARSER` как env-флаг | Явное требование кандидата; симметрично `MOCK_LLM` / `MOCK_CRM` |
| Partial collection OK | Если категория исчерпана до 10K — не ошибка |
| Demo 100 товаров | Быстрая локальная проверка; код масштабируется на 10K |
| Батчинг LLM (`LLM_BATCH_SIZE=25`) | Снижает число запросов с 10K до ~400 |
| Стандарт не в CRM | Классифицируется, но задачи только для Premium/Economy |
| CRM идемпотентность | SHA-256(title+description), store + маркер в AmoCRM |
| Clean Architecture + DDD (v0.2) | Разделение domain/application/infrastructure/interfaces |
| FastAPI job API (v0.3) | Async jobs, health, metrics |
| Production hardening (v0.4) | API_KEY, rate limit, real /ready, structured logs, LLM soft-fail |
| Scale stack (v0.5) | Celery + PostgreSQL + Redis + OTEL/Sentry |
| Alembic + enriched snapshots | Postgres schema via migrations; `enriched_product_snapshots` table |
| Job submit idempotency | `Idempotency-Key` header, memory/Redis store, configurable TTL |
| Distributed rate limit | Redis sliding window when `REDIS_URL` set; public paths exempt |

## Промпты / задачи агенту

1. «Изучи vision.md, найди discrepancies» — анализ ТЗ.
2. «Proceed with implementation» — полная генерация проекта.
3. «Нужна идемпотентность CRM» — store + remote reconcile.
4. «Refactor to Clean Architecture + DDD» — слои, ports, Container.
5. «Prove to HR we're strong backend devs» — FastAPI, SQLite jobs, probes.
6. «Дотянуть до prod уровня» — auth, observability, atomic writes, Docker hardening.
7. «Multi-node scale» — Celery, Postgres, Redis, shared metrics.
8. «Production hardening v0.5.1» — Alembic migrations, job `Idempotency-Key`, Redis rate limit, `MetricsRegistry` in infrastructure.
9. «Актуализируй доки и закоммить» — синхронизация docs/tests.

## Сгенерировано ИИ

- Clean Architecture: domain ports, use cases, adapters, factories
- `HttpClient` (tenacity, 429, connection pool)
- Ozon/Mock parsers, LLM batch classifier (soft-fail), AmoCRM + idempotency (file + Redis)
- FastAPI: jobs API, auth (`compare_digest`), rate limit (memory/Redis), health/ready/metrics, OpenAPI security
- Job runners: thread pool (single-node) + Celery (multi-node)
- Job stores: SQLite + PostgreSQL; Alembic migrations
- Job idempotency: `Idempotency-Key` on submit (memory/Redis)
- Observability: `MetricsRegistry` (in-memory or Redis), JSON logs, correlation_id, OTEL, Sentry (optional)
- pytest (~144 tests, ~95% coverage), Docker, compose scale profile, CI
- Docs: AGENTS.md, SCALE.md, rules, skills

## Исправлено / уточнено вручную (кандидатом)

- Partial collection, mock-only parser, CRM top-N внутри сегмента
- Demo mode, идемпотентность CRM обязательна
- `collection_target` per job в API body
- Idempotency store в `output_dir` тестов (не общий `data/`)

## API layer — кратко (v0.5)

```
POST /api/v1/pipeline/jobs  → 202 (optional X-API-Key, Idempotency-Key)
GET  /api/v1/pipeline/jobs/{id}  → poll status
GET  /health, /ready, /metrics  → public (no auth)
```

Backends: `thread`+`sqlite` (default) или `celery`+`postgres`+`redis` (scale).

## Что стоит проверить ревьюеру

**Полная пошаговая инструкция (40–60 мин):** [docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md)  
**Быстрый live-demo (5–7 мин):** [docs/HR_DEMO.md](docs/HR_DEMO.md)

Ниже — самодостаточный чеклист для проверки **соответствия [vision.md](vision.md)** без реальных ключей OpenAI / AmoCRM / Ozon (всё на mock-режиме).

### Подготовка (≈3 мин)

```bash
git clone https://github.com/mxmaslin/marketplace-pipeline.git
cd marketplace-pipeline

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,scale]"
cp .env.example .env    # MOCK_PARSER/MOCK_LLM/MOCK_CRM=true по умолчанию
```

### 1. Технические требования ТЗ

| Требование vision.md | Команда / артефакт | Ожидание |
|----------------------|-------------------|----------|
| pytest, coverage ≥70% | `make ci` | ruff clean, **144 passed**, coverage **≥95%** |
| Моки внешних HTTP | `pytest tests/test_ozon_collect.py tests/test_llm.py tests/test_crm.py -v` | все green, без сети |
| AI_USAGE.md | этот файл | промпты, архитектура, ограничения |
| docker-compose | `docker compose up api --build` | API на :8000, `curl /health` → 200 |
| CI/CD | `.github/workflows/ci.yml` + [Actions](https://github.com/mxmaslin/marketplace-pipeline/actions) | lint → pytest → docker build |
| README + .env.example | корень репозитория | установка, env, запуск, архитектура |

### 2. Парсинг маркетплейса (раздел 1 vision.md)

| Требование | Как проверить | Ожидание |
|------------|---------------|----------|
| Ozon, одна категория | `.env.example` → `OZON_CATEGORY_PATH` | смартфоны (`smartfony-15502`) |
| Цель 10 000 товаров | `settings.py` → `TARGET_PRODUCT_COUNT=10000` | smoke: `pytest tests/test_ozon_collect.py::test_ozon_collect_10k_target_smoke -v` |
| Пагинация | `tests/test_ozon_collect.py` | `test_ozon_collect_stops_at_target_with_pagination` |
| `OZON_PAGE_SIZE` | `test_ozon_page_size_caps_products_per_page` | лимит товаров на страницу |
| Retry 429 + exponential backoff | `tests/test_pipeline.py::test_http_client_retries_on_429` | tenacity, без падения |
| Graceful degradation | `tests/test_pipeline.py::test_pipeline_graceful_degradation` | partial data, `degraded=True`, exit 0 |
| proxy.market traffic exhausted | `tests/test_proxy_market_quota.py` | pre-flight `ProxyQuotaExhaustedError`, API 402 |
| Partial collection (категория исчерпана) | `test_ozon_collect_category_exhausted_before_target` | `exhausted=True`, warning, не crash |
| DEMO_MODE (50–100 товаров) | `make run` | собирает **100** (`DEMO_PRODUCT_COUNT`, настраивается) |

**CLI smoke:**

```bash
make run
# exit 0; лог: Collected N/N; data/enriched_products.json создан
jq '.meta.collected_count, (.products | length)' data/enriched_products.json
```

### 3. LLM-классификация (раздел 2 vision.md)

| Требование | Где смотреть | Как проверить |
|------------|--------------|---------------|
| Pydantic-схема (id, name, price, currency, url, category, collected_at, description) | `domain/entities/product.py` | поля в коде / enriched output |
| 3 сегмента: Эконом / Стандарт / Премиум | `domain/value_objects/price_segment.py` | enum из 3 значений |
| Поле `segment` | `domain/entities/enriched_product.py` | есть в `data/enriched_products.json` |
| Батчинг (не 10K отдельных запросов) | `openai_classifier.py`, `LLM_BATCH_SIZE=25` | `pytest tests/test_llm.py -v` |
| MOCK_LLM=true | `.env.example` | `make run` без `OPENAI_API_KEY` |
| Graceful degradation LLM | `tests/test_prod_hardening.py` | bad JSON → fallback «Стандарт» |

```bash
jq '[.products[].segment] | unique' data/enriched_products.json
# ожидается подмножество ["Эконом", "Стандарт", "Премиум"]
```

### 4. CRM (раздел 3 vision.md)

| Требование | Где смотреть | Как проверить |
|------------|--------------|---------------|
| Топ-5 дорогих в **Премиум** | `domain/services/crm_task_factory.py` | 1 задача, до 5 товаров |
| Топ-5 дешёвых в **Эконом** | там же | 1 задача, до 5 товаров |
| **Стандарт** не уходит в CRM | `crm_task_factory.py` | всего **2** задачи, не 3 |
| REST AmoCRM + auth + логи | `infrastructure/adapters/crm/amocrm_gateway.py` | `pytest tests/test_crm.py -v` |
| URL и цена в описании задачи | `crm_task_factory.py` → `_format_lines` | `name: price currency — url` |
| MOCK_CRM=true | `.env.example` | `make run` без AmoCRM токена |
| Идемпотентность (бонус, сверх ТЗ) | `domain/services/idempotency_policy.py` | повторный `make run` → `reused=2` |

```bash
make run && make run
# второй прогон: CRM tasks: created=0 reused=2 (или аналогично)
pytest tests/test_idempotency.py -v
```

### 5. Mock-режимы (раздел 4 vision.md)

| Флаг | Назначение | Проверка |
|------|------------|----------|
| `MOCK_LLM=true` | LLM без OpenAI | `make run` без ключа |
| `MOCK_CRM=true` | CRM без AmoCRM | `make run` без токена |
| `MOCK_PARSER=true` | Парсер без Ozon (расширение) | CI и локальные тесты |

Все три включены в `.env.example` и CI (`.github/workflows/ci.yml`).

### 6. API — async jobs (сверх ТЗ, опционально)

```bash
make api   # терминал 1
```

```bash
curl -s -D - -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 20}'
# → 202, X-Request-ID, status: pending

curl -s http://localhost:8000/api/v1/pipeline/jobs/$JOB_ID | jq
# → pending → running → completed; crm_tasks_count=2

curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq
curl -s http://localhost:8000/metrics
```

Swagger: **http://localhost:8000/docs**

### 7. Архитектура (бонус, не блокирует ТЗ)

```bash
rg "from marketplace_pipeline\.(infrastructure|interfaces|application)" src/marketplace_pipeline/domain/
# → 0 совпадений
```

Маршрут чтения: `docs/CLEAN_ARCHITECTURE.md` → `application/use_cases/run_pipeline.py` → `infrastructure/composition/container.py`.

### 8. Production-фичи (бонус v0.4+)

| Фича | Быстрая проверка |
|------|------------------|
| `API_KEY` | без ключа POST `/api/v1/*` → 401; с `X-API-Key` → 202 |
| Pre-flight | `MOCK_LLM=false`, пустой `OPENAI_API_KEY` → POST job → 422 |
| Rate limit | `/health` не лимитируется; `/api/v1/*` при `API_RATE_LIMIT_PER_MINUTE=1` → 429 |
| Job `Idempotency-Key` | повторный POST с тем же ключом → тот же job id |
| `/ready` 503 | удалить `data/jobs.sqlite` → GET `/ready` → 503 |

Подробные curl-примеры: [docs/REVIEWER_GUIDE.md §6](docs/REVIEWER_GUIDE.md).

### 9. Итоговый чеклист «сдать / не сдать»

**Минимум по vision.md:**

- [ ] `make ci` — green (144 tests, ≥95% coverage)
- [ ] `make run` — exit 0, `data/enriched_products.json` с сегментами
- [ ] CRM: 2 задачи (Премиум + Эконом), Стандарт только в JSON
- [ ] Повторный `make run` → CRM `reused=true`
- [ ] Graceful degradation покрыт тестами (parser + LLM)
- [ ] `AI_USAGE.md`, `README.md`, `.env.example`, `docker-compose.yml`, CI — на месте
- [ ] `docker compose up api --build` — health OK

**Бонус (сверх ТЗ):**

- [ ] API jobs: POST → 202, poll → completed
- [ ] Clean Architecture: domain без infra-импортов
- [ ] `API_KEY`, rate limit, `/ready` probes
- [ ] Scale: `docker compose --profile scale up` + `alembic upgrade head`

### 10. Что сознательно не проверялось автоматически

- Реальный сбор **10 000** товаров с живым Ozon — только mock + unit/smoke тесты
- Создание задач в **боевой** AmoCRM — нужен OAuth token
- Полный staging Postgres/Redis/Celery — unit-тесты с моками; см. [docs/SCALE.md](docs/SCALE.md)

**Live Ozon + proxy.market:** при `PROXY_MARKET_API_KEY` пайплайн делает pre-flight проверку трафика; исчерпанный пакет → явная ошибка (CLI exit 1, API 402), не тихий `collected=0`. См. [docs/REVIEWER_GUIDE.md §15](docs/REVIEWER_GUIDE.md).

Это ограничение тестового задания, не дефект реализации.

## Статистика экономии контекста (lean-ctx MCP v3.8.5)

Данные по сессии разработки **marketplace-pipeline** (`/Users/bulrathi/_cryprobez`), период **2026-06-23 — 2026-06-24** (~12 ч активной работы агента). Источник: `lean-ctx` (`stats.json`, `ctx_session status`) — это кэш **чтений файлов/инструментов**, не кэш ответов LLM.

### Запросы к контексту: кэш vs промах

| Метрика | Значение |
|---------|----------|
| **Попадания в кэш** (`ctx_read` cache hit) | **151** |
| **Промахи** (повторное чтение с диска / cold read) | **130** |
| **Всего обращений к кэшируемым чтениям** | **281** |
| **Hit rate** | **53.7%** |
| **Miss rate** | **46.3%** |

Текущая сессия (на момент фиксации): **119** вызовов lean-ctx, **23 788** токенов сэкономлено за счёт сжатия; hit rate в последнем срезе **38%** (5 hit / 13 read).

### Сжатие контекста при чтении

| | Токены |
|---|--------|
| Исходный объём прочитанного | 266 911 |
| После compression modes | 132 389 |
| **Сэкономлено** | **134 522 (50.4%)** |

Использованные режимы `ctx_read`: `full`, `map`, `signatures`, `auto`, `lines:N-M` — diversity **100%** (CEP).

### Оценка оптимальности настроек экономии кэша

**Итоговая оценка: 7.5/10 (хорошо, с резервом)**

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| Hit rate 53.7% | ★★★☆☆ | Выше случайного, но далеко от «теплого» идеала 70–80% |
| Compression 50% | ★★★★☆ | Режимы `map` / `signatures` / `lines` работают |
| Mode diversity | ★★★★★ | Нет зацикливания на одном режиме |
| CEP score (последний) | **54/100** | Architectural — ожидаемо для рефакторинга |
| Стабильность сессии | ★★★☆☆ | После паузы hit rate падал с **61% → 0%** (cold cache) |

**Что настроено правильно**

- Правила `.cursor/rules/lean-ctx.mdc` и `mcp-efficiency.mdc` — приоритет `ctx_read` / `ctx_search` над полными чтениями
- `ctx_search` с `head_limit` и `files_with_matches` для discovery
- Post-edit re-read через кэш (~13 токенов на повторное чтение vs полный файл)

**Что снижает hit rate (промахи 46%)**

- Активная разработка: после каждого `edit` кэш файла инвалидируется → закономерные промахи
- Периодические **native** `Read`/`Grep`/`Shell` вместо `ctx_*` — обходят общий кэш lean-ctx
- Длинные сессии с новыми файлами (`ozon_http.py`, `proxy_market_quota_checker.py`) — cold reads в начале работы с модулем

**Рекомендации для следующих сессий**

1. После правки — `ctx_read(path, mode="diff")`, не `full`
2. Ориентация — `signatures` / `map`; полный `full` только перед edit
3. Не дублировать поиск: один `ctx_semantic_search` → stop
4. Держать сессию непрерывной или явно `ctx_cache(action="status")` перед большими рефакторами
5. Auto-run lean-ctx в Cursor Settings — меньше friction → выше доля cache hits

## Ограничения автогенерации

ИИ не запускал реальный сбор 10K с Ozon и не создавал задачи в боевой AmoCRM. Scale stack проверен unit-тестами с моками; для staging нужны живые Postgres/Redis.
