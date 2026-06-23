from datetime import UTC, datetime

import pytest
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.parser.factory import build_parser
from marketplace_pipeline.parser.mock import MockParser
from marketplace_pipeline.parser.ozon import OzonParser


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        MOCK_PARSER=True,
        MOCK_LLM=True,
        MOCK_CRM=True,
        DEMO_MODE=True,
        DEMO_PRODUCT_COUNT=20,
    )


def test_build_parser_uses_mock(mock_settings: Settings) -> None:
    parser = build_parser(mock_settings)
    assert isinstance(parser, MockParser)


def test_build_parser_uses_ozon() -> None:
    settings = Settings(MOCK_PARSER=False)
    parser = build_parser(settings)
    assert isinstance(parser, OzonParser)


def test_mock_parser_collects_target(mock_settings: Settings) -> None:
    parser = MockParser(mock_settings)
    result = parser.collect(15)
    assert result.collected_count == 15
    assert len(result.products) == 15
    assert result.products[0].currency == "RUB"


def test_ozon_parse_price() -> None:
    assert OzonParser._parse_price("12 990 ₽") == 12990.0
    assert OzonParser._parse_price("invalid") is None


def test_ozon_page_url_pagination() -> None:
    parser = OzonParser(Settings(OZON_CATEGORY_PATH="/category/test/"))
    assert parser._page_url(1) == "/category/test/"
    assert parser._page_url(2) == "/category/test/?page=2"


def test_ozon_parse_products_skips_invalid_widgets() -> None:
    parser = OzonParser(Settings())
    products = parser._parse_products(
        {
            "widgetStates": {
                "num": 123,
                "empty": "no sku here",
                "ok": '{"sku":9,"title":"X","price":"100 ₽"}',
            }
        }
    )
    assert len(products) == 1


def test_ozon_collect_stops_at_target(httpx_mock: HTTPXMock) -> None:
    raw = (
        '{"sku":1,"title":"A","price":"100 ₽"}'
        '{"sku":2,"title":"B","price":"200 ₽"}'
        '{"sku":3,"title":"C","price":"300 ₽"}'
    )
    httpx_mock.add_response(json={"widgetStates": {"w": raw}})
    parser = OzonParser(Settings(MOCK_PARSER=False))
    result = parser.collect(2)
    assert result.collected_count == 2
    assert len(httpx_mock.get_requests()) == 1


def test_ozon_extract_products_from_widget() -> None:
    parser = OzonParser(Settings())
    raw = (
        '{"sku":123,"title":"Phone X","price":"15 000 ₽"}'
        '{"sku":456,"title":"Phone Y","price":"25 000 ₽"}'
    )
    products = parser._extract_from_widget(raw, datetime.now(tz=UTC))
    assert len(products) >= 1
