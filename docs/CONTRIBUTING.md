# Contributing

## Setup

```bash
git clone <repo>
cd cryprobez
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Development workflow

1. Read [`AGENTS.md`](../AGENTS.md) and [`vision.md`](../vision.md)
2. Create a branch: `feat/...` or `fix/...`
3. Implement with tests (Clean Architecture layers — see [`docs/CLEAN_ARCHITECTURE.md`](CLEAN_ARCHITECTURE.md))
4. Run quality gates:

```bash
make lint    # or: ruff check src tests
make test    # or: pytest (~65 tests, ≥95% coverage)
make run     # CLI mock pipeline smoke
make api     # FastAPI on :8000 (optional)
```

5. Update docs if behavior or env vars change (`docs/ENV.md`, `AGENTS.md`, rules/skills)

## Commit messages

Conventional commits (English or Russian):

```
feat(api): add job cancellation endpoint
fix(parser): handle empty widgetStates page
test(api): cover job failure status
docs: update CLEAN_ARCHITECTURE for v0.3
```

## Pull request checklist

- [ ] `pytest` passes, coverage ≥95%
- [ ] `ruff check src tests` clean
- [ ] New env vars in `.env.example` + `docs/ENV.md`
- [ ] `AGENTS.md` / skill updated if agent workflow changed
- [ ] API changes reflected in `docs/ARCHITECTURE.md` and `docs/HR_DEMO.md` if user-facing
- [ ] No secrets, no `data/*.json` / `data/*.sqlite` commits

## Adding a new parser

1. Implement `CatalogCollectorPort` in `infrastructure/adapters/parsers/`
2. Wire in `Container.catalog_collector()`
3. Add env flag `MOCK_<NAME>` if needed (follow `MOCK_PARSER` pattern)
4. Tests in `tests/test_<name>.py` with `pytest-httpx`

Legacy path `parser/<marketplace>.py` is a shim — add logic in infrastructure adapters.

## Adding CRM idempotency for new CRM

Reuse `domain/services/idempotency_policy.py`:

- Same key computation
- Embed marker in task body field supported by CRM API
- Optional remote reconcile via list/search API

## Adding API endpoints

1. Define request/response schemas in `interfaces/api/schemas/`
2. Thin route handler → application use case (no business logic in routes)
3. Wire dependencies via `app.state` in `lifecycle.py`
4. Tests in `tests/test_api.py` with `TestClient` + lifespan

## Questions

For assignment submission context, see [`AI_USAGE.md`](../AI_USAGE.md).  
HR demo script: [`docs/HR_DEMO.md`](HR_DEMO.md).
