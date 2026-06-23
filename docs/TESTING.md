# Testing

## Quick start

```bash
pytest                          # full suite + coverage (~95 tests, ~96%)
pytest tests/test_api.py -v     # FastAPI integration
pytest tests/test_scale.py -v   # multi-node factories (mocked)
pytest -k idempotency           # by name
pytest --cov=marketplace_pipeline --cov-report=html  # HTML report → htmlcov/
make ci                           # ruff + pytest
```

Coverage threshold: **95%** (enforced in `pyproject.toml`).

Install for scale tests: `pip install -e ".[dev,scale]"` (CI uses this).

## Principles

1. **No real external calls in CI** — `MOCK_*=true` in GitHub Actions
2. **HTTP mocking** — `pytest-httpx` for Ozon, OpenAI, AmoCRM
3. **Temp dirs** — `tmp_path` for idempotency store, pipeline output, `JOB_DB_PATH`
4. **Deterministic** — `MockParser` for reproducible product sets
5. **API tests** — always use `with TestClient(create_app()) as client:` so lifespan runs
6. **Scale backends** — mock Postgres/Redis/Celery; no real services in unit tests

## Test layout

```
tests/
  domain/
    test_domain_services.py   # pure domain unit tests
  test_parser.py              # factory, mock parser, ozon helpers
  test_ozon_collect.py        # ozon pagination with httpx mock
  test_llm.py                 # mock + openai batch + soft-fail
  test_crm.py                 # selectors, amocrm http
  test_idempotency.py         # store, duplicate tasks, pipeline rerun
  test_pipeline.py            # e2e, degradation, http 429
  test_main.py                # CLI entry
  test_api.py                 # health, ready, auth, rate limit, jobs
  test_job_repository.py      # SQLite job CRUD
  test_job_runner.py          # thread pool success/failure
  test_prod_hardening.py      # prerequisites, atomic IO, LLM soft-fail
  test_scale.py               # Postgres/Redis/Celery factories, OTEL/Sentry
  test_coverage.py            # edge branches
```

## Common patterns

### API client fixture

```python
@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PARSER", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_CRM", "true")
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.sqlite"))
    monkeypatch.delenv("API_KEY", raising=False)
    with TestClient(create_app()) as client:
        yield client
```

### Mock AmoCRM create

```python
httpx_mock.add_response(json={"_embedded": {"tasks": []}})  # remote search
httpx_mock.add_response(json={"_embedded": {"tasks": [{"id": 42}]}})  # create
```

### Idempotent duplicate

```python
client = AmoCRMClient(settings, idempotency_store_path=tmp_path / "store.json")
first = client.create_task(payload)
second = client.create_task(payload)
assert second.reused is True
```

### Job runner isolation

Patch `pipeline_job_executor.Container` to control pipeline outcome without HTTP.

## CI

See [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

```
ruff → pytest (mocks on, .[scale] installed) → docker build
```

Env in CI: `MOCK_*=true`, `DEMO_MODE=true`, `DEMO_PRODUCT_COUNT=50`.

## Raising coverage

```bash
pytest --cov=marketplace_pipeline --cov-report=term-missing
```

Prefer focused tests in `test_coverage.py` / `test_scale.py` over duplicate e2e.
