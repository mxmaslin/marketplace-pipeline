# Testing

## Quick start

```bash
pytest                          # full suite + coverage
pytest tests/test_crm.py -v     # single module
pytest -k idempotency           # by name
pytest --cov=marketplace_pipeline --cov-report=html  # HTML report → htmlcov/
```

Coverage threshold: **95%** (enforced in `pyproject.toml`).

## Principles

1. **No real external calls in CI** — `MOCK_*=true` in GitHub Actions
2. **HTTP mocking** — `pytest-httpx` for Ozon, OpenAI, AmoCRM
3. **Temp dirs** — `tmp_path` for idempotency store, pipeline output
4. **Deterministic** — `MockParser` for reproducible product sets

## Test layout

```
tests/
  test_parser.py       # factory, mock parser, ozon helpers
  test_ozon_collect.py # ozon pagination with httpx mock
  test_llm.py          # mock + openai batch
  test_crm.py          # selectors, amocrm http
  test_idempotency.py  # store, duplicate tasks, pipeline rerun
  test_pipeline.py     # e2e, degradation, http 429
  test_main.py         # CLI entry
  test_coverage.py     # edge cases for missing branches
```

## Common patterns

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

### Pipeline smoke

```python
Pipeline(Settings(MOCK_PARSER=True, MOCK_LLM=True, MOCK_CRM=True, DEMO_MODE=True),
         output_dir=tmp_path).run()
```

## CI

See [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

```
ruff → pytest (mocks on) → docker build
```

## Raising coverage

When adding code, check:

```bash
pytest --cov=marketplace_pipeline --cov-report=term-missing
```

Target uncovered lines in the report. Prefer focused tests over broad integration tests.
