import httpx
import pytest
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.llm.classifier import SegmentClassifier
from marketplace_pipeline.models import PriceSegment, Product
from marketplace_pipeline.parser.mock import MockParser


@pytest.fixture
def products() -> list[Product]:
    parser = MockParser(Settings())
    return parser.collect(12).products


def test_mock_llm_classification() -> None:
    settings = Settings(MOCK_LLM=True)
    classifier = SegmentClassifier(settings)
    products = MockParser(settings).collect(9).products
    enriched = classifier.classify(products)

    assert len(enriched) == 9
    segments = {item.segment for item in enriched}
    assert PriceSegment.ECONOMY in segments
    assert PriceSegment.PREMIUM in segments


def test_openai_batch_classification(httpx_mock: HTTPXMock) -> None:
    settings = Settings(
        MOCK_LLM=False,
        OPENAI_API_KEY="test-key",
        LLM_BATCH_SIZE=5,
    )
    products = MockParser(settings).collect(6).products
    classifier = SegmentClassifier(settings)

    def callback(request: httpx.Request) -> httpx.Response:
        assert "chat/completions" in str(request.url)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"items": ['
                                '{"id":"mock-1","segment":"Эконом"},'
                                '{"id":"mock-2","segment":"Стандарт"},'
                                '{"id":"mock-3","segment":"Премиум"},'
                                '{"id":"mock-4","segment":"Эконом"},'
                                '{"id":"mock-5","segment":"Стандарт"}'
                                "]}"
                            )
                        }
                    }
                ]
            },
        )

    httpx_mock.add_callback(callback)
    httpx_mock.add_callback(callback)

    enriched = classifier.classify(products)
    assert len(enriched) == 6
    assert enriched[0].segment == PriceSegment.ECONOMY


def test_parse_segments_fills_missing() -> None:
    classifier = SegmentClassifier(Settings(MOCK_LLM=True))
    parsed = classifier._parse_segments(
        '{"items":[{"id":"a","segment":"Премиум"}]}',
        expected_ids={"a", "b"},
    )
    assert parsed["a"] == PriceSegment.PREMIUM
    assert parsed["b"] == PriceSegment.STANDARD
