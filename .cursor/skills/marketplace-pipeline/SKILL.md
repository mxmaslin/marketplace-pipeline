---
name: marketplace-pipeline
description: >-
  Clean Architecture / DDD pipeline: Ozon→LLM→AmoCRM. Use for domain,
  application use cases, infrastructure adapters, or assignment submission.
---

# Marketplace Pipeline Skill

## Architecture (v0.2)

Clean Architecture + DDD. Read [docs/CLEAN_ARCHITECTURE.md](../../docs/CLEAN_ARCHITECTURE.md).

```
RunPipelineUseCase
  ├── CatalogCollectorPort     → OzonCatalogCollector | MockCatalogCollector
  ├── SegmentClassifierPort    → OpenAiSegmentClassifier
  ├── CrmGatewayPort           → AmoCrmGateway
  └── EnrichedProductRepositoryPort → JsonEnrichedProductRepository
```

Composition root: `infrastructure/composition/container.py`

## First steps

1. [AGENTS.md](../../AGENTS.md)
2. Identify layer before editing
3. `make test`

## Add CRM provider

1. Implement `CrmGatewayPort` in `infrastructure/adapters/crm/`
2. Reuse `domain/services/idempotency_policy.py`
3. Wire in `Container.crm_gateway()`

## Add marketplace

1. Implement `CatalogCollectorPort`
2. Wire in `Container.catalog_collector()`

## Legacy imports (tests)

```python
from marketplace_pipeline.models import Product          # → domain.entities
from marketplace_pipeline.pipeline import Pipeline       # → facade over use case
```

Prefer layered imports in new code.
