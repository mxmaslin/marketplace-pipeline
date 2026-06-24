import httpx
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.parser.ozon import OzonParser
from tests.helpers import ozon_parser_for_httpx_mock

WIDGET = '{"sku":101,"title":"Phone A","price":"10 000 ₽"}'


def _ozon_parser(settings: Settings) -> OzonParser:
    return ozon_parser_for_httpx_mock(settings)


def _widget_for_skus(skus: range) -> str:
    return "".join(
        f'{{"sku":{sku},"title":"Phone {sku}","price":"{sku * 100} ₽"}}' for sku in skus
    )


def _page_from_request(request: httpx.Request) -> int:
    url = request.url.params.get("url", "")
    if "page=" not in url:
        return 1
    return int(url.rsplit("page=", maxsplit=1)[-1])


def test_ozon_collect_pagination(httpx_mock: HTTPXMock) -> None:
    settings = Settings(MOCK_PARSER=False, OZON_CATEGORY_PATH="/category/test/")

    def responder(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("url", "")
        if "page=2" in page:
            return httpx.Response(200, json={"widgetStates": {}})
        return httpx.Response(
            200,
            json={"widgetStates": {"tileGridDesktop-1": WIDGET}},
        )

    httpx_mock.add_callback(responder)

    parser = _ozon_parser(settings)
    result = parser.collect(1)

    assert result.collected_count == 1
    assert result.products[0].name == "Phone A"
    assert result.degraded is False


def test_ozon_page_size_caps_products_per_page(httpx_mock: HTTPXMock) -> None:
    page_size = 3
    settings = Settings(MOCK_PARSER=False, OZON_PAGE_SIZE=page_size)
    raw = _widget_for_skus(range(1, 11))
    httpx_mock.add_response(json={"widgetStates": {"tileGridDesktop": raw}})

    result = _ozon_parser(settings).collect(page_size)

    assert result.collected_count == page_size
    assert len(httpx_mock.get_requests()) == 1
    assert result.products[0].id == "1"
    assert result.products[-1].id == "3"


def test_ozon_collect_stops_at_target_with_pagination(httpx_mock: HTTPXMock) -> None:
    page_size = 36
    target = 100
    settings = Settings(
        MOCK_PARSER=False,
        OZON_PAGE_SIZE=page_size,
        OZON_CATEGORY_PATH="/category/test/",
    )

    def responder(request: httpx.Request) -> httpx.Response:
        page = _page_from_request(request)
        start = (page - 1) * page_size + 1
        raw = _widget_for_skus(range(start, start + page_size))
        return httpx.Response(200, json={"widgetStates": {"tileGridDesktop": raw}})

    httpx_mock.add_callback(responder, is_reusable=True)

    result = _ozon_parser(settings).collect(target)

    assert result.collected_count == target
    assert result.exhausted is False
    assert result.degraded is False
    assert len(httpx_mock.get_requests()) == 3


def test_ozon_collect_category_exhausted_before_target(httpx_mock: HTTPXMock) -> None:
    page_size = 36
    settings = Settings(MOCK_PARSER=False, OZON_PAGE_SIZE=page_size)

    def responder(request: httpx.Request) -> httpx.Response:
        page = _page_from_request(request)
        if page == 1:
            raw = _widget_for_skus(range(1, 11))
            return httpx.Response(200, json={"widgetStates": {"tileGridDesktop": raw}})
        return httpx.Response(200, json={"widgetStates": {}})

    httpx_mock.add_callback(responder, is_reusable=True)

    result = _ozon_parser(settings).collect(100)

    assert result.collected_count == 10
    assert result.exhausted is True
    assert result.degraded is False
    assert len(httpx_mock.get_requests()) == 2


def test_ozon_collect_10k_target_smoke(httpx_mock: HTTPXMock) -> None:
    """Smoke: pagination loop honors full TARGET_PRODUCT_COUNT without real Ozon HTTP."""
    page_size = 50
    target = 10_000
    settings = Settings(
        MOCK_PARSER=False,
        DEMO_MODE=False,
        TARGET_PRODUCT_COUNT=target,
        OZON_PAGE_SIZE=page_size,
        OZON_CATEGORY_PATH="/category/test/",
    )
    assert settings.collection_target == target

    def responder(request: httpx.Request) -> httpx.Response:
        page = _page_from_request(request)
        start = (page - 1) * page_size + 1
        raw = _widget_for_skus(range(start, start + page_size))
        return httpx.Response(200, json={"widgetStates": {"tileGridDesktop": raw}})

    httpx_mock.add_callback(responder, is_reusable=True)

    result = _ozon_parser(settings).collect(settings.collection_target)

    assert result.collected_count == target
    assert result.target_count == target
    assert result.exhausted is False
    assert result.degraded is False
    assert len(result.products) == target
    assert len(httpx_mock.get_requests()) == target // page_size
