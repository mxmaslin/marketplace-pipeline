"""Production-hardening unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.domain.exceptions import PipelineConfigurationError
from marketplace_pipeline.domain.services.pipeline_prerequisites import (
    PipelinePrerequisites,
    validate_pipeline_prerequisites,
)
from marketplace_pipeline.infrastructure.adapters.llm.openai_classifier import (
    OpenAiSegmentClassifier,
)
from marketplace_pipeline.infrastructure.adapters.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from marketplace_pipeline.infrastructure.io.atomic import atomic_write_text
from marketplace_pipeline.llm.classifier import SegmentClassifier
from marketplace_pipeline.parser.mock import MockParser


def test_validate_pipeline_prerequisites_ok() -> None:
    validate_pipeline_prerequisites(
        PipelinePrerequisites(
            mock_llm=True,
            mock_crm=True,
            openai_api_key="",
            amocrm_subdomain="",
            amocrm_access_token="",
        )
    )


def test_validate_pipeline_prerequisites_missing_openai() -> None:
    with pytest.raises(PipelineConfigurationError, match="OPENAI_API_KEY"):
        validate_pipeline_prerequisites(
            PipelinePrerequisites(
                mock_llm=False,
                mock_crm=True,
                openai_api_key="",
                amocrm_subdomain="x",
                amocrm_access_token="tok",
            )
        )


def test_sqlite_job_repository_ping(tmp_path: Path) -> None:
    repo = SqliteJobRepository(tmp_path / "jobs.sqlite")
    assert repo.ping() is True


def test_atomic_write_text(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "out.json"
    atomic_write_text(target, '{"ok": true}')
    assert target.read_text(encoding="utf-8") == '{"ok": true}'


def test_llm_batch_soft_fail_on_bad_response(httpx_mock: HTTPXMock) -> None:
    settings = Settings(MOCK_LLM=False, OPENAI_API_KEY="test-key", LLM_BATCH_SIZE=5)
    products = MockParser(settings).collect(3).products
    classifier = OpenAiSegmentClassifier(settings)
    httpx_mock.add_response(status_code=500)
    enriched = classifier.classify(products)
    assert len(enriched) == 3
    assert all(item.segment.value == "Стандарт" for item in enriched)


def test_llm_batch_soft_fail_on_invalid_json(httpx_mock: HTTPXMock) -> None:
    settings = Settings(MOCK_LLM=False, OPENAI_API_KEY="test-key")
    product = MockParser(settings).collect(1).products[0]
    classifier = SegmentClassifier(settings)

    httpx_mock.add_response(
        200,
        json={"choices": [{"message": {"content": '{"wrong": true}'}}]},
    )
    enriched = classifier.classify([product])
    assert len(enriched) == 1
    assert enriched[0].segment.value == "Стандарт"
