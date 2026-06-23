# AGENTS.md — Marketplace Pipeline

Instructions for AI coding agents working in this repository.

## Architecture

**Clean Architecture + DDD.** Read [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) first.

```
domain/          → entities, value objects, ports, domain services (no infra imports)
application/     → use cases (RunPipelineUseCase)
infrastructure/  → adapters (Ozon, OpenAI, AmoCRM), config, Container
interfaces/      → CLI entrypoint
```

Legacy shims at package root (`models.py`, `pipeline.py`) re-export for tests — **prefer layered imports in new code**.

## Commands

```bash
pip install -e ".[dev]"
ruff check src tests
pytest                    # coverage ≥95%
make run                  # mock pipeline smoke
```

## Dependency rule

```
interfaces → application → domain ← infrastructure
```

Infrastructure implements domain **ports**. Application orchestrates ports. Domain never imports httpx, settings, or adapters.

## Where to change what

| Task | Layer | Path |
|------|-------|------|
| Business rules (top-N, segments) | Domain | `domain/services/` |
| Pipeline flow | Application | `application/use_cases/` |
| New marketplace | Infrastructure | `infrastructure/adapters/parsers/` + port |
| New CRM | Infrastructure | `infrastructure/adapters/crm/` |
| Wire dependencies | Infrastructure | `infrastructure/composition/container.py` |
| Env vars | Infrastructure | `infrastructure/config/settings.py` |
| CLI | Interfaces | `interfaces/cli/main.py` |

## Business invariants

- Partial collection OK when category exhausted
- Graceful degradation on parser errors
- CRM idempotency via `domain/services/idempotency_policy.py`
- «Стандарт» classified but not sent to CRM
- `MOCK_PARSER` env-only

## Do NOT

- Import infrastructure from domain or application
- Put HTTP/LLM logic in use cases
- Break port contracts without updating tests + docs
- Commit `.env`, `data/*.json`

## Docs index

| Doc | Purpose |
|-----|---------|
| [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) | Layers, DDD map |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow, APIs |
| [docs/TESTING.md](docs/TESTING.md) | Test patterns |
| [vision.md](vision.md) | Original assignment spec |

## Cursor

- Rules: [`.cursor/rules/`](.cursor/rules/)
- Skill: [`.cursor/skills/marketplace-pipeline/SKILL.md`](.cursor/skills/marketplace-pipeline/SKILL.md)
