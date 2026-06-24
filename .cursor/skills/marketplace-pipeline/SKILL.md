---
name: marketplace-pipeline
description: >-
  Clean Architecture / DDD pipeline: Ozon→LLM→AmoCRM + FastAPI job API.
  Use for domain, use cases, adapters, API layer, or assignment submission.
---

# Marketplace Pipeline Skill

## Architecture (v0.5)

Clean Architecture + DDD. Read [docs/CLEAN_ARCHITECTURE.md](../../docs/CLEAN_ARCHITECTURE.md).

### Sync pipeline (CLI / use case)

```
RunPipelineUseCase
  ├── CatalogCollectorPort     → OzonCatalogCollector | MockCatalogCollector
  ├── SegmentClassifierPort    → OpenAiSegmentClassifier
  ├── CrmGatewayPort           → AmoCrmGateway
  └── EnrichedProductRepositoryPort → JsonEnrichedProductRepository | PostgresEnrichedProductRepository
```

Enriched output: `build_enriched_product_repository()` — JSON file (default) or Postgres when `JOB_STORE_BACKEND=postgres`.

### Async jobs (API)

```
POST /api/v1/pipeline/jobs
  → validate_pipeline_prerequisites
  → SubmitPipelineJobUseCase (+ optional Idempotency-Key)
  → JobRunnerPort (thread pool | Celery)
  → pipeline_job_executor → RunPipelineUseCase
  → JobRepositoryPort (SQLite | PostgreSQL via Alembic)
```

Composition: `infrastructure/composition/container.py` + `factories.py`  
API wiring: `interfaces/api/lifecycle.py`

## First steps

1. [AGENTS.md](../../AGENTS.md)
2. Identify layer before editing
3. `pip install -e ".[dev,scale]"` for full test suite
4. `make test` (≥95% coverage, ~108 tests)
5. `make api` → http://localhost:8000/docs

## Key env vars

| Var | Purpose |
|-----|---------|
| `MOCK_PARSER` / `MOCK_LLM` / `MOCK_CRM` | Offline dev |
| `JOB_STORE_BACKEND` | `sqlite` (default) or `postgres` |
| `JOB_RUNNER_BACKEND` | `thread` (default) or `celery` |
| `JOB_DB_PATH` / `DATABASE_URL` | Job persistence |
| `API_KEY` | Protect `/api/v1/*` (`compare_digest`) |
| `JOB_IDEMPOTENCY_TTL_SECONDS` | TTL for `Idempotency-Key` on job submit |
| `CRM_IDEMPOTENCY_BACKEND` | `file` or `redis` |

Scale: run `alembic upgrade head` before Postgres deploy.  
Full list: [docs/ENV.md](../../docs/ENV.md) · Scale: [docs/SCALE.md](../../docs/SCALE.md)

## Add API feature

1. Application use case in `application/use_cases/`
2. Route + schema in `interfaces/api/`
3. Register router in `interfaces/api/app.py`
4. Test with `TestClient(create_app())` + `JOB_DB_PATH` in tmp_path

## HR demo

[docs/HR_DEMO.md](../../docs/HR_DEMO.md) — 5–7 min script.
