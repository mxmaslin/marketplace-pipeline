# Clean Architecture & DDD

## Layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│  interfaces/          CLI, future HTTP API                   │
├─────────────────────────────────────────────────────────────┤
│  application/         Use cases (RunPipelineUseCase)        │
├─────────────────────────────────────────────────────────────┤
│  domain/              Entities, VOs, domain services, ports  │
├─────────────────────────────────────────────────────────────┤
│  infrastructure/      Adapters, config, HTTP, composition   │
└─────────────────────────────────────────────────────────────┘
         Dependencies point INWARD only ↑
```

## Domain (`domain/`)

| Package | Contents |
|---------|----------|
| `entities/` | `Product`, `EnrichedProduct` |
| `value_objects/` | `PriceSegment` |
| `models/` | `CollectionResult`, `CrmTaskRequest`, `CrmTaskOutcome` |
| `services/` | `ProductSelectionService`, `CrmTaskFactory`, `idempotency_policy` |
| `ports/` | Protocol interfaces (collector, classifier, CRM, repository, store) |
| `exceptions/` | `DomainError`, `CrmConfigurationError` |

**No imports** from application or infrastructure.

## Application (`application/`)

- `use_cases/run_pipeline.py` — orchestrates ports, no HTTP/Ozon/AmoCRM details
- `dto/pipeline_result.py` — use case output

Depends on **domain only** (ports + services).

## Infrastructure (`infrastructure/`)

| Adapter | Port | Path |
|---------|------|------|
| `OzonCatalogCollector` | `CatalogCollectorPort` | `adapters/parsers/` |
| `MockCatalogCollector` | `CatalogCollectorPort` | `adapters/parsers/` |
| `OpenAiSegmentClassifier` | `SegmentClassifierPort` | `adapters/llm/` |
| `AmoCrmGateway` | `CrmGatewayPort` | `adapters/crm/` |
| `FileIdempotencyStore` | `IdempotencyStorePort` | `adapters/crm/` |
| `JsonEnrichedProductRepository` | `EnrichedProductRepositoryPort` | `adapters/persistence/` |

- `composition/container.py` — **composition root** (DI wiring)
- `config/settings.py` — env configuration (not domain)

## Interfaces (`interfaces/`)

- `cli/main.py` — entrypoint, builds `Container`, runs use case

## Legacy shims (root package)

Files like `models.py`, `pipeline.py`, `parser/ozon.py` re-export new types for backward compatibility. **New code should import from layered packages.**

## DDD mapping

| DDD concept | Implementation |
|-------------|----------------|
| Entity | `Product`, `EnrichedProduct` |
| Value Object | `PriceSegment` |
| Domain Service | `ProductSelectionService`, `CrmTaskFactory` |
| Repository (port) | `EnrichedProductRepositoryPort` |
| Anti-corruption layer | Ozon/OpenAI/AmoCRM adapters |
| Application Service | `RunPipelineUseCase` |
| Factory | `Container`, `CrmTaskFactory` |

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
| Container | Smoke / e2e via `Pipeline` facade |

See [TESTING.md](TESTING.md).
