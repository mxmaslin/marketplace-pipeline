.PHONY: install install-scale lint test run api docker scale-up clean coverage ci

install:
	pip install -e ".[dev]"

install-scale:
	pip install -e ".[dev,scale]"

lint:
	ruff check src tests

test:
	pytest

coverage:
	pytest --cov=marketplace_pipeline --cov-report=html --cov-report=term-missing

run:
	MOCK_PARSER=true MOCK_LLM=true MOCK_CRM=true DEMO_MODE=true marketplace-pipeline

api:
	MOCK_PARSER=true MOCK_LLM=true MOCK_CRM=true DEMO_MODE=true marketplace-pipeline-api

docker:
	docker compose up --build

scale-up:
	docker compose --profile scale up --build

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

ci: lint test
