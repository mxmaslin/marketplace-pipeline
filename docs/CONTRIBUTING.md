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
3. Implement with tests
4. Run quality gates:

```bash
make lint    # or: ruff check src tests
make test    # or: pytest
make run     # mock pipeline smoke test
```

5. Update docs if behavior or env vars change

## Commit messages

Conventional commits (English or Russian):

```
feat(crm): add Bitrix24 task client
fix(parser): handle empty widgetStates page
test(idempotency): cover corrupt store load
docs: update AGENTS.md env table
```

## Pull request checklist

- [ ] `pytest` passes, coverage ≥95%
- [ ] `ruff check src tests` clean
- [ ] New env vars in `.env.example` + `docs/ENV.md`
- [ ] `AGENTS.md` updated if agent workflow changed
- [ ] No secrets, no `data/*.json` commits

## Adding a new parser

1. Subclass `BaseParser` in `parser/<marketplace>.py`
2. Return normalized `Product` models
3. Register in `parser/factory.py`
4. Add env flag `MOCK_<NAME>` if needed (follow `MOCK_PARSER` pattern)
5. Tests in `tests/test_<name>.py` with `pytest-httpx`

## Adding CRM idempotency for new CRM

Reuse `crm/idempotency.py`:

- Same key computation
- Embed marker in task body field supported by CRM API
- Optional remote reconcile via list/search API

## Questions

For assignment submission context, see [`AI_USAGE.md`](../AI_USAGE.md).
