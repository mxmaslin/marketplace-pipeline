---
name: marketplace-pipeline
description: >-
  Clean Architecture / DDD pipeline: Ozon→LLM→AmoCRM + FastAPI job API.
  Use for domain, use cases, adapters, API layer, or assignment submission.
---

# Marketplace Pipeline Skill

## Architecture (v0.3)

Clean Architecture + DDD. Read [docs/CLEAN_ARCHITECTURE.md](../../docs/CLEAN_ARCHITECTURE.md).

### Sync pipeline (CLI / use case)

```
RunPipelineUseCase
  ├── CatalogCollectorPort     → OzonCatalogCollector | MockCatalogCollector
  ├── SegmentClassifierPort    → OpenAiSegmentClassifier
  ├── CrmGatewayPort           → AmoCrmGateway
  └── EnrichedProductRepositoryPort → JsonEnrichedProductRepository
```

### Async jobs (API)

```
POST /api/v1/pipeline/jobs
  → SubmitPipelineJobUseCase
  → PipelineJobRunner (thread pool)
  → RunPipelineUseCase(collection_target=job.collection_target)
  → SqliteJobRepository (JobRepositoryPort)
```

Composition root: `infrastructure/composition/container.py`  
API wiring: `interfaces/api/lifecycle.py`

## First steps

1. [AGENTS.md](../../AGENTS.md)
2. Identify layer before editing (domain / application / infrastructure / interfaces)
3. `make test` (≥95% coverage)
4. API smoke: `make api` → http://localhost:8000/docs

## Add CRM provider

1. Implement `CrmGatewayPort` in `infrastructure/adapters/crm/`
2. Reuse `domain/services/idempotency_policy.py`
3. Wire in `Container.crm_gateway()`

## Add marketplace

1. Implement `CatalogCollectorPort`
2. Wire in `Container.catalog_collector()`

## Add API feature

1. Application use case in `application/use_cases/`
2. Route + schema in `interfaces/api/`
3. Register router in `interfaces/api/app.py`
4. Test with `TestClient(create_app())` context manager + `JOB_DB_PATH` in tmp_path

## Key env vars

| Var | Purpose |
|-----|---------|
| `MOCK_PARSER` / `MOCK_LLM` / `MOCK_CRM` | Offline dev |
| `JOB_DB_PATH` | SQLite jobs (API) |
| `API_JOB_WORKERS` | Background thread pool size |
| `CRM_IDEMPOTENCY_STORE_PATH` | Dedupe store |

Full list: [docs/ENV.md](../../docs/ENV.md)

## Legacy imports (tests)

```python
from marketplace_pipeline.models import Product          # → domain.entities
from marketplace_pipeline.pipeline import Pipeline       # → facade over use case
```

Prefer layered imports in new code.

## HR demo

[docs/HR_DEMO.md](../../docs/HR_DEMO.md) — 5–7 min script: API, probes, architecture talking points.
