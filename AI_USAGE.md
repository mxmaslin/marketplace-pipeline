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
| CRM идемпотентность | SHA-256(title+description), local store + маркер в AmoCRM |
| Clean Architecture + DDD (v0.2) | Разделение domain/application/infrastructure/interfaces |
| FastAPI job API (v0.3) | Production-style слой для HR: async jobs, health, metrics |

## Промпты / задачи агенту

1. «Изучи vision.md, найди discrepancies» — анализ ТЗ, список неоднозначностей.
2. «Proceed with implementation» — полная генерация проекта после уточнения трактовок.
3. «Нужна идемпотентность CRM» — store + remote reconcile по маркеру.
4. «Refactor to Clean Architecture + DDD» — слои, ports, Container, legacy shims.
5. «Prove to HR we're strong backend devs» — FastAPI, SQLite jobs, thread pool, probes.
6. «Актуализируй доки/rules/skills/тесты» — синхронизация с v0.3.

## Сгенерировано ИИ

- Структура пакета `marketplace_pipeline/` (Clean Architecture)
- Pydantic-модели и settings
- `HttpClient` с tenacity и shared connection pool (429 + exponential backoff)
- Ozon/Mock parsers, LLM batch classifier, AmoCRM + idempotency
- `RunPipelineUseCase`, domain ports, `Container`
- FastAPI: job API, health/ready/metrics, `X-Request-ID` middleware
- SQLite `PipelineJob` repository, `PipelineJobRunner`
- pytest + pytest-httpx (~65 tests, ~98% coverage)
- Dockerfile, docker-compose (CLI + API), GitHub Actions
- README, AGENTS.md, docs/, `.cursor/rules/`, skill, AI_USAGE.md

## Исправлено / уточнено вручную (кандидатом)

- Partial collection: OK если нет больше записей в категории
- Mock парсера — только env-флаг, не отдельный сервис
- CRM: сортировка по `price` **внутри** LLM-сегмента
- Demo mode для локальных прогонов
- Идемпотентность CRM обязательна (повторный прогон → `reused=true`)
- API job использует `collection_target` из тела запроса, не только из env

## Батчинг LLM — как решалось

```
Промпт (system): классифицируй items, верни JSON [{id, segment}]
Промпт (user): {"items": [{id, name, description}, ...]}  # до 25 штук
Ответ: {"items": [{"id":"...", "segment":"Эконом|Стандарт|Премиум"}]}
Fallback: если id пропущен или segment невалиден → «Стандарт»
MOCK_LLM: эвристика по ключевым словам и price thresholds
```

## API layer (v0.3) — кратко

```
POST /api/v1/pipeline/jobs  → 202, job id
GET  /api/v1/pipeline/jobs/{id}  → poll status
GET  /health, /ready, /metrics
```

Long-running pipeline в thread pool; состояние в SQLite (`JOB_DB_PATH`).

## Что стоит проверить ревьюеру

- [ ] Coverage ≥95% (`pytest`, сейчас ~98%)
- [ ] `make run` — CLI mock pipeline
- [ ] `make api` → http://localhost:8000/docs — submit job, poll status
- [ ] `docker compose up --build` — CLI и API сервисы
- [ ] Логи partial/degraded collection
- [ ] Формат описания CRM-задач (URL + цена)
- [ ] Повторный прогон не дублирует CRM-задачи (`reused=true` в логах)
- [ ] Clean Architecture: domain без импортов httpx/FastAPI

## Ограничения автогенерации

ИИ не запускал реальный сбор 10K с Ozon и не создавал задачи в боевой AmoCRM — для этого нужны ключи и устойчивый доступ к API. Job API использует thread pool, не Celery/K8s — достаточно для demo, масштабирование описано в `docs/DEPLOYMENT.md`.
