from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from marketplace_pipeline.domain.entities.product import Product
from marketplace_pipeline.domain.models.collection_result import CollectionResult
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient

logger = logging.getLogger(__name__)

CATEGORY_NAME = "Смартфоны"


class OzonCatalogCollector:
    """Infrastructure adapter: Ozon composer API → domain Product entities."""

    def __init__(self, settings: Settings, http_client: HttpClient | None = None) -> None:
        self._settings = settings
        self._http = http_client or HttpClient(
            max_retries=settings.http_max_retries,
            base_delay=settings.http_retry_base_delay,
            timeout=settings.ozon_request_timeout,
        )

    def collect(self, target_count: int) -> CollectionResult:
        products: list[Product] = []
        page = 1
        degraded = False
        error_message: str | None = None
        seen_ids: set[str] = set()

        while len(products) < target_count:
            try:
                batch = self._fetch_page(page)
            except Exception as exc:
                degraded = True
                error_message = str(exc)
                logger.error("Parser degraded on page %s: %s", page, exc)
                break

            if not batch:
                logger.info("Category exhausted at page %s with %s products", page, len(products))
                break

            for product in batch:
                if product.id in seen_ids:
                    continue
                seen_ids.add(product.id)
                products.append(product)
                if len(products) >= target_count:
                    break

            page += 1

        exhausted = len(products) < target_count and not degraded
        return CollectionResult(
            products=products[:target_count],
            target_count=target_count,
            collected_count=len(products[:target_count]),
            exhausted=exhausted,
            degraded=degraded,
            error_message=error_message,
        )

    def _fetch_page(self, page: int) -> list[Product]:
        params = {"url": self._page_url(page)}
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MarketplacePipeline/0.1)",
            "Accept": "application/json",
        }
        response = self._http.get(
            self._settings.ozon_api_base_url,
            headers=headers,
            params=params,
        )
        return self._parse_products(response.json())

    def _page_url(self, page: int) -> str:
        base = self._settings.ozon_category_path.rstrip("/")
        if page <= 1:
            return f"{base}/"
        return f"{base}/?page={page}"

    def _parse_products(self, payload: dict) -> list[Product]:
        widgets = payload.get("widgetStates") or {}
        collected_at = datetime.now(tz=UTC)
        products: list[Product] = []

        for raw_state in widgets.values():
            if not isinstance(raw_state, str):
                continue
            if "tileGridDesktop" not in raw_state and "sku" not in raw_state:
                continue
            products.extend(self._extract_from_widget(raw_state, collected_at))

        return products

    def _extract_from_widget(self, raw_state: str, collected_at: datetime) -> list[Product]:
        products: list[Product] = []
        sku_blocks = re.findall(
            r'"sku"\s*:\s*(\d+).*?"title"\s*:\s*"([^"]+)".*?"price"\s*:\s*"([^"]+)"',
            raw_state,
            flags=re.DOTALL,
        )
        for sku, title, price_raw in sku_blocks:
            price = self._parse_price(price_raw)
            if price is None:
                continue
            product_id = str(sku)
            products.append(
                Product(
                    id=product_id,
                    name=title.replace("\\u0026", "&"),
                    price=price,
                    currency="RUB",
                    url=f"https://www.ozon.ru/product/{product_id}/",
                    category=CATEGORY_NAME,
                    collected_at=collected_at,
                    description=f"Категория: {CATEGORY_NAME}. {title}",
                )
            )
        return products

    @staticmethod
    def _parse_price(value: str) -> float | None:
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            return None
        return float(digits)
