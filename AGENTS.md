# AGENTS.md — Marketplace Pipeline

Instructions for AI coding agents working in this repository.

## Architecture

**Clean Architecture + DDD (v0.3).** Read [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) first.

```
domain/          → entities, value objects, ports, domain services (no infra imports)
application/     → use cases (RunPipelineUseCase, pipeline job use cases)
infrastructure/  → adapters (Ozon, OpenAI, AmoCRM, SQLite), config, Container, job runner
interfaces/      → CLI + FastAPI (async jobs, health, metrics)
```

Legacy shims at package root (`models.py`, `pipeline.py`) re-export for tests — **prefer layered imports in new code**.

## Commands

```bash
pip install -e ".[dev]"
ruff check src tests
pytest                    # coverage ≥95% (currently ~98%)
make run                  # CLI mock pipeline smoke
make api                  # FastAPI on :8000 (OpenAPI /docs)
make ci                   # lint + test
```

## Dependency rule

```
interfaces → application → domain ← infrastructure
```

Infrastructure implements domain **ports**. Application orchestrates ports. Domain never imports httpx, FastAPI, settings, or adapters.

## Where to change what

| Task | Layer | Path |
|------|-------|------|
| Business rules (top-N, segments) | Domain | `domain/services/` |
| Pipeline flow | Application | `application/use_cases/run_pipeline.py` |
| Async job submit/poll | Application | `application/use_cases/pipeline_jobs.py` |
| Job entity / status | Domain | `domain/models/pipeline_job.py` |
| Job persistence port | Domain | `domain/ports/job_repository.py` |
| New marketplace | Infrastructure | `infrastructure/adapters/parsers/` + port |
| New CRM | Infrastructure | `infrastructure/adapters/crm/` |
| Job SQLite store | Infrastructure | `infrastructure/adapters/persistence/sqlite_job_repository.py` |
| Background execution | Infrastructure | `infrastructure/services/pipeline_job_runner.py` |
| Wire dependencies | Infrastructure | `infrastructure/composition/container.py` |
| Env vars | Infrastructure | `infrastructure/config/settings.py` |
| CLI | Interfaces | `interfaces/cli/main.py` |
| HTTP API | Interfaces | `interfaces/api/` |

## Business invariants

- Partial collection OK when category exhausted
- Graceful degradation on parser errors
- CRM idempotency via `domain/services/idempotency_policy.py`
- «Стандарт» classified but not sent to CRM
- `MOCK_PARSER` env-only
- API jobs: `collection_target` in request body overrides settings for that job only

## Do NOT

- Import infrastructure from domain or application
- Put HTTP/LLM logic in use cases
- Run long pipeline work inside FastAPI request handlers (use `PipelineJobRunner`)
- Break port contracts without updating tests + docs
- Commit `.env`, `data/*.json`, `data/*.sqlite`

## Docs index

| Doc | Purpose |
|-----|---------|
| [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) | Layers, DDD map, API layer |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow, APIs, job lifecycle |
| [docs/HR_DEMO.md](docs/HR_DEMO.md) | HR demo script (API + talking points) |
| [docs/TESTING.md](docs/TESTING.md) | Test patterns |
| [docs/ENV.md](docs/ENV.md) | Environment variables |
| [vision.md](vision.md) | Original assignment spec |

## Cursor

- Rules: [`.cursor/rules/`](.cursor/rules/)
- Skill: [`.cursor/skills/marketplace-pipeline/SKILL.md`](.cursor/skills/marketplace-pipeline/SKILL.md)
