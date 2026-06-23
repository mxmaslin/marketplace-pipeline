# Clean Architecture & DDD

## Layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│  interfaces/     CLI + FastAPI + Celery worker               │
├─────────────────────────────────────────────────────────────┤
│  application/    Use cases (pipeline + job management)         │
├─────────────────────────────────────────────────────────────┤
│  domain/         Entities, VOs, domain services, ports       │
├─────────────────────────────────────────────────────────────┤
│  infrastructure/ Adapters, factories, HTTP, composition      │
└─────────────────────────────────────────────────────────────┘
         Dependencies point INWARD only ↑
```

## Domain (`domain/`)

| Package | Contents |
|---------|----------|
| `entities/` | `Product`, `EnrichedProduct` |
| `value_objects/` | `PriceSegment` |
| `models/` | `CollectionResult`, `CrmTaskRequest`, `CrmTaskOutcome`, `PipelineJob` |
| `services/` | `ProductSelectionService`, `CrmTaskFactory`, `idempotency_policy`, `pipeline_prerequisites` |
| `ports/` | Collector, classifier, CRM, idempotency store, **job repository**, **job runner**, **job idempotency store** |
| `exceptions/` | `DomainError`, `CrmConfigurationError`, `PipelineConfigurationError` |

**No imports** from application or infrastructure.

## Application (`application/`)

| Use case | Role |
|----------|------|
| `run_pipeline.py` | Orchestrates catalog → LLM → CRM → JSON output |
| `pipeline_jobs.py` | Submit / get / list async pipeline jobs (API layer) |

Depends on **domain only** (ports + services). Job submit delegates to `JobRunnerPort` wired at the interface boundary.

## Infrastructure (`infrastructure/`)

| Adapter | Port | Path |
|---------|------|------|
| `OzonCatalogCollector` | `CatalogCollectorPort` | `adapters/parsers/` |
| `MockCatalogCollector` | `CatalogCollectorPort` | `adapters/parsers/` |
| `OpenAiSegmentClassifier` | `SegmentClassifierPort` | `adapters/llm/` |
| `AmoCrmGateway` | `CrmGatewayPort` | `adapters/crm/` |
| `FileIdempotencyStore` | `IdempotencyStorePort` | `adapters/crm/` |
| `RedisIdempotencyStore` | `IdempotencyStorePort` | `adapters/crm/` |
| `JsonEnrichedProductRepository` | `EnrichedProductRepositoryPort` | `adapters/persistence/` |
| `SqliteJobRepository` | `JobRepositoryPort` | `adapters/persistence/` |
| `PostgresJobRepository` | `JobRepositoryPort` | `adapters/persistence/` |
| `PostgresEnrichedProductRepository` | `EnrichedProductRepositoryPort` | `adapters/persistence/` |
| `MemoryJobIdempotencyStore` | `JobIdempotencyStorePort` | `adapters/persistence/` |
| `RedisJobIdempotencyStore` | `JobIdempotencyStorePort` | `adapters/persistence/` |

| Service | Role |
|---------|------|
| `pipeline_job_executor` | Shared execute logic (thread pool + Celery) |
| `PipelineJobRunner` | Single-node thread pool |
| `CeleryJobRunner` | Multi-node enqueue to Celery |
| `HttpClient` | Shared httpx pool, retries, 429 handling |

| Composition | Role |
|-------------|------|
| `container.py` | DI wiring for pipeline adapters |
| `factories.py` | Select job store / runner / idempotency by settings |

| Workers | Role |
|---------|------|
| `workers/celery_app.py` | Celery application |
| `workers/tasks.py` | `pipeline.execute_job` task |

- `config/settings.py` — env configuration (not domain)
- `observability/metrics.py` — `MetricsRegistry` (in-memory or Redis Prometheus counters)
- `observability/tracing.py` — optional OTEL + Sentry
- `rate_limit/redis_sliding_window.py` — distributed API rate limit
- `alembic/` (repo root) — PostgreSQL schema migrations

## Interfaces (`interfaces/`)

| Entry | Role |
|-------|------|
| `cli/main.py` | Synchronous one-shot pipeline |
| `api/app.py` | FastAPI: auth, rate limit (memory/Redis), metrics, OpenAPI security |
| `api/routes/jobs.py` | `POST/GET /api/v1/pipeline/jobs` (202 async) |
| `api/routes/health.py` | `/health`, `/ready` (DB + data dir + Redis) |
| `api/lifecycle.py` | Startup: factories, metrics, observability |
| `worker/main.py` | `marketplace-pipeline-worker` (Celery) |

## Legacy shims (root package)

Files like `models.py`, `pipeline.py`, `parser/ozon.py` re-export new types for backward compatibility. **New code should import from layered packages.**

## DDD mapping

| DDD concept | Implementation |
|-------------|----------------|
| Entity | `Product`, `EnrichedProduct`, `PipelineJob` |
| Value Object | `PriceSegment`, `JobStatus` |
| Domain Service | `ProductSelectionService`, `CrmTaskFactory`, `pipeline_prerequisites` |
| Repository (port) | `EnrichedProductRepositoryPort`, `JobRepositoryPort` |
| Anti-corruption layer | Ozon/OpenAI/AmoCRM adapters |
| Application Service | `RunPipelineUseCase`, `SubmitPipelineJobUseCase` |
| Factory | `Container`, `factories`, `CrmTaskFactory` |

## Adding a feature (example: Bitrix24)

1. Define port contract (already `CrmGatewayPort`)
2. Implement `Bitrix24Gateway` in `infrastructure/adapters/crm/`
3. Wire in `Container.crm_gateway()` via settings flag
4. Domain/application **unchanged**

## Testing strategy

| Layer | Test type |
|-------|-----------|
| Domain services | Pure unit tests, no mocks |
| Use cases | Mock ports (Protocol fakes) |
| Adapters | `pytest-httpx` integration tests |
| Job repository | `tmp_path` SQLite; Postgres mocked in `test_scale.py` |
| API | `TestClient` + lifespan context manager |
| Scale stack | `test_scale.py`, `test_prod_hardening.py` |
| Container | Smoke / e2e via `Pipeline` facade |

See [TESTING.md](TESTING.md).
