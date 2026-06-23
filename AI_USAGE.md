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

## Промпты / задачи агенту

1. «Изучи vision.md, найди discrepancies» — анализ ТЗ.
2. «Proceed with implementation» — полная генерация проекта.
3. «Нужна идемпотентность CRM» — store + remote reconcile.
4. «Refactor to Clean Architecture + DDD» — слои, ports, Container.
5. «Prove to HR we're strong backend devs» — FastAPI, SQLite jobs, probes.
6. «Дотянуть до prod уровня» — auth, observability, atomic writes, Docker hardening.
7. «Multi-node scale» — Celery, Postgres, Redis, shared metrics.
8. «Актуализируй доки и закоммить» — синхронизация v0.5.

## Сгенерировано ИИ

- Clean Architecture: domain ports, use cases, adapters, factories
- `HttpClient` (tenacity, 429, connection pool)
- Ozon/Mock parsers, LLM batch classifier (soft-fail), AmoCRM + idempotency (file + Redis)
- FastAPI: jobs API, auth, rate limit, health/ready/metrics, middleware
- Job runners: thread pool (single-node) + Celery (multi-node)
- Job stores: SQLite + PostgreSQL
- Observability: JSON logs, correlation_id, OTEL, Sentry (optional)
- pytest (~95 tests, ~96% coverage), Docker, compose scale profile, CI
- Docs: AGENTS.md, SCALE.md, rules, skills

## Исправлено / уточнено вручную (кандидатом)

- Partial collection, mock-only parser, CRM top-N внутри сегмента
- Demo mode, идемпотентность CRM обязательна
- `collection_target` per job в API body
- Idempotency store в `output_dir` тестов (не общий `data/`)

## API layer — кратко (v0.5)

```
POST /api/v1/pipeline/jobs  → 202 (optional X-API-Key)
GET  /api/v1/pipeline/jobs/{id}  → poll status
GET  /health, /ready, /metrics
```

Backends: `thread`+`sqlite` (default) или `celery`+`postgres`+`redis` (scale).

## Что стоит проверить ревьюеру

- [ ] Coverage ≥95% (`pytest`, сейчас ~96%)
- [ ] `make run` — CLI mock pipeline
- [ ] `make api` → /docs — submit job, poll status
- [ ] `docker compose up` — local; `docker compose --profile scale up` — distributed
- [ ] `API_KEY` защищает `/api/v1/*`
- [ ] `/ready` возвращает 503 при недоступной БД
- [ ] Повторный прогон CRM → `reused=true`
- [ ] Domain без импортов httpx/FastAPI

## Ограничения автогенерации

ИИ не запускал реальный сбор 10K с Ozon и не создавал задачи в боевой AmoCRM. Scale stack проверен unit-тестами с моками; для staging нужны живые Postgres/Redis.
