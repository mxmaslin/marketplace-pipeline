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

С `API_KEY` в prod:

```bash
curl -s -X POST http://localhost:8000/api/v1/pipeline/jobs \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"collection_target": 50}'
```

## 3. Poll status

```bash
curl -s http://localhost:8000/api/v1/pipeline/jobs/<JOB_ID> | jq
```

Статусы: `pending` → `running` → `completed`.

## 4. Production probes

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq    # DB + data dir (+ Redis в scale mode)
curl -s http://localhost:8000/metrics
```

## 5. Архитектура (30 сек устно)

- **Clean Architecture + DDD** — domain не зависит от FastAPI/БД
- **Ports & adapters** — Ozon, OpenAI, AmoCRM заменяемы
- **Idempotent CRM** — file или Redis store
- **Job API** — long-running work вне HTTP thread
- **Scale** — Celery workers + PostgreSQL (`docs/SCALE.md`)
- **Production** — API_KEY, rate limits, structured logs, OTEL/Sentry
- **≥95% test coverage**, CI, Docker

## 6. Scale demo (опционально)

```bash
docker compose --profile scale up --build
```

API + worker + Postgres + Redis в одной команде.

## 7. CLI (как в ТЗ)

```bash
make run
```

## 8. CI

```bash
make ci
```

GitHub Actions: ruff → pytest → docker build.

## Talking points

- Почему 202 + polling, а не sync endpoint
- Как `collection_target` в body переопределяет env
- Что происходит при partial collection / parser degraded
- Как идемпотентность защищает от дублей в AmoCRM
- Как переключить single-node → multi-node через env
