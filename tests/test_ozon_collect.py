import httpx
from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.parser.ozon import OzonParser

WIDGET = '{"sku":101,"title":"Phone A","price":"10 000 ₽"}'


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

    parser = OzonParser(settings)
    result = parser.collect(1)

    assert result.collected_count == 1
    assert result.products[0].name == "Phone A"
    assert result.degraded is False
