# AGENTS.md — Marketplace Pipeline

Instructions for AI coding agents working in this repository.

## Architecture

**Clean Architecture + DDD (v0.5).** Read [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) first.

```
domain/          → entities, value objects, ports, domain services (no infra imports)
application/     → use cases (RunPipelineUseCase, pipeline job use cases)
infrastructure/  → adapters, factories, Container, job runners, workers
interfaces/      → CLI + FastAPI + Celery worker entrypoints
```

Legacy shims at package root (`models.py`, `pipeline.py`) re-export for tests — **prefer layered imports in new code**.

## Commands

```bash
pip install -e ".[dev]"           # local / CI
pip install -e ".[dev,scale]"       # Postgres, Celery, Redis, OTEL, Sentry
ruff check src tests
pytest                            # coverage ≥95% (~95 tests, ~96%)
make run                          # CLI mock pipeline smoke
make api                          # FastAPI on :8000 (OpenAPI /docs)
make scale-up                     # docker compose --profile scale
make ci                           # lint + test
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
| Job runner port | Domain | `domain/ports/job_runner.py` |
| Pre-flight validation | Domain | `domain/services/pipeline_prerequisites.py` |
| New marketplace | Infrastructure | `infrastructure/adapters/parsers/` + port |
| New CRM | Infrastructure | `infrastructure/adapters/crm/` |
| Job store (SQLite / Postgres) | Infrastructure | `infrastructure/adapters/persistence/` |
| Background execution | Infrastructure | `pipeline_job_runner.py` or `celery_job_runner.py` |
| Shared job execution | Infrastructure | `infrastructure/services/pipeline_job_executor.py` |
| Backend factories | Infrastructure | `infrastructure/composition/factories.py` |
| Wire dependencies | Infrastructure | `infrastructure/composition/container.py` |
| Env vars | Infrastructure | `infrastructure/config/settings.py` |
| CLI | Interfaces | `interfaces/cli/main.py` |
| HTTP API | Interfaces | `interfaces/api/` |
| Celery worker | Interfaces | `interfaces/worker/main.py` |

## Runtime backends (env)

| Concern | Default (local/CI) | Scale (multi-node) |
|---------|-------------------|-------------------|
| Job store | `JOB_STORE_BACKEND=sqlite` | `postgres` + `DATABASE_URL` |
| Job runner | `JOB_RUNNER_BACKEND=thread` | `celery` + `REDIS_URL` |
| CRM idempotency | `CRM_IDEMPOTENCY_BACKEND=file` | `redis` |

See [docs/SCALE.md](docs/SCALE.md).

## Business invariants

- Partial collection OK when category exhausted
- Graceful degradation on parser errors; LLM batch soft-fail → «Стандарт»
- CRM idempotency via `domain/services/idempotency_policy.py`
- «Стандарт» classified but not sent to CRM
- `MOCK_PARSER` env-only
- API jobs: `collection_target` in request body overrides settings for that job only
- Production API: optional `API_KEY`, rate limits, real `/ready` probes

## Do NOT

- Import infrastructure from domain or application (use ports)
- Put HTTP/LLM logic in use cases
- Run long pipeline work inside FastAPI request handlers (use `JobRunnerPort`)
- Break port contracts without updating tests + docs
- Commit `.env`, `data/*.json`, `data/*.sqlite`

## Docs index

| Doc | Purpose |
|-----|---------|
| [docs/CLEAN_ARCHITECTURE.md](docs/CLEAN_ARCHITECTURE.md) | Layers, DDD map, API layer |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data flow, APIs, job lifecycle |
| [docs/SCALE.md](docs/SCALE.md) | Multi-node: Celery, Postgres, Redis |
| [docs/HR_DEMO.md](docs/HR_DEMO.md) | HR demo script |
| [docs/REVIEWER_GUIDE.md](docs/REVIEWER_GUIDE.md) | **Инструкция для ревьювера** |
| [docs/TESTING.md](docs/TESTING.md) | Test patterns |
| [docs/ENV.md](docs/ENV.md) | Environment variables |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, prod, observability |
| [vision.md](vision.md) | Original assignment spec |

## Cursor

- Rules: [`.cursor/rules/`](.cursor/rules/)
- Skill: [`.cursor/skills/marketplace-pipeline/SKILL.md`](.cursor/skills/marketplace-pipeline/SKILL.md)
