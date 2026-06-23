# HR Demo — что показать на ревью

Краткий сценарий для демонстрации backend-навыков (5–7 минут).

## 1. Запуск API

```bash
make api
# OpenAPI: http://localhost:8000/docs
```

## 2. Submit job (async, 202)

```bash
curl -s -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 50}' | jq
```

Обратите внимание: **`X-Request-ID`** в заголовках — correlation id.

## 3. Poll status

```bash
curl -s http://localhost:8000/api/v1/pipeline/jobs/<JOB_ID> | jq
```

Статусы: `pending` → `running` → `completed`.

## 4. Production probes

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq
curl -s http://localhost:8000/metrics
```

## 5. Архитектура (30 сек устно)

- **Clean Architecture + DDD** — domain не зависит от FastAPI/SQLite
- **Ports & adapters** — Ozon, OpenAI, AmoCRM заменяемы
- **Idempotent CRM** — повторный прогон не дублирует задачи
- **Job API** — long-running work вне HTTP thread (thread pool + SQLite)
- **Connection pooling** — shared `httpx.Client`
- **98%+ test coverage**, CI, Docker

## 6. CLI (как в ТЗ)

```bash
make run
```

## 7. CI

```bash
make ci
```

GitHub Actions: ruff → pytest → docker build.

## Что сказать HR

> «Тестовое закрывает ТЗ (парсинг, LLM batching, CRM, моки, Docker, CI).  
> Поверх — production-паттерны: REST API, async jobs, health/metrics, CA/DDD, idempotency.  
> Всё покрыто тестами, включая API через TestClient.»
