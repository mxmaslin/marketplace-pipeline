from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from marketplace_pipeline.domain.entities.enriched_product import EnrichedProduct
from marketplace_pipeline.domain.entities.product import Product
from marketplace_pipeline.domain.value_objects.price_segment import PriceSegment
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient

logger = logging.getLogger(__name__)

SEGMENT_VALUES = {segment.value for segment in PriceSegment}

SYSTEM_PROMPT = (
    "Ты классифицируешь товары маркетплейса по потребительскому сегменту. "
    "Верни только JSON-массив объектов вида "
    '{"id":"...", "segment":"Эконом|Стандарт|Премиум"}. '
    "Не добавляй пояснений."
)


class OpenAiSegmentClassifier:
    """Infrastructure adapter: OpenAI chat completions for batch classification."""

    def __init__(self, settings: Settings, http_client: HttpClient | None = None) -> None:
        self._settings = settings
        self._http = http_client or HttpClient(
            max_retries=settings.http_max_retries,
            base_delay=settings.http_retry_base_delay,
        )

    def classify(self, products: list[Product]) -> list[EnrichedProduct]:
        if not products:
            return []

        if self._settings.mock_llm:
            return [self._mock_classify(product) for product in products]

        segments: dict[str, PriceSegment] = {}
        for batch in _chunk(products, self._settings.llm_batch_size):
            segments.update(self._classify_batch(batch))

        return [
            EnrichedProduct(
                **product.model_dump(),
                segment=segments.get(product.id, PriceSegment.STANDARD),
            )
            for product in products
        ]

    def _classify_batch(self, batch: list[Product]) -> dict[str, PriceSegment]:
        try:
            user_payload = [
                {"id": p.id, "name": p.name, "description": p.description} for p in batch
            ]
            response = self._http.post(
                f"{self._settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._settings.openai_model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps({"items": user_payload}, ensure_ascii=False),
                        },
                    ],
                },
            )
            content = response.json()["choices"][0]["message"]["content"]
            return self._parse_segments(content, expected_ids={p.id for p in batch})
        except Exception as exc:
            logger.warning(
                "LLM batch classification failed for %s products, using fallback: %s",
                len(batch),
                exc,
            )
            return {product.id: PriceSegment.STANDARD for product in batch}

    def _parse_segments(self, content: str, expected_ids: set[str]) -> dict[str, PriceSegment]:
        parsed = json.loads(content)
        items = parsed.get("items") if isinstance(parsed, dict) else parsed
        if not isinstance(items, list):
            raise ValueError("LLM response does not contain items list")

        result: dict[str, PriceSegment] = {}
        for item in items:
            product_id = str(item.get("id", ""))
            segment_raw = str(item.get("segment", "")).strip()
            if product_id not in expected_ids:
                continue
            if segment_raw not in SEGMENT_VALUES:
                segment_raw = PriceSegment.STANDARD.value
            result[product_id] = PriceSegment(segment_raw)

        for missing_id in expected_ids - result.keys():
            result[missing_id] = PriceSegment.STANDARD
        return result

    def _mock_classify(self, product: Product) -> EnrichedProduct:
        name = product.name.lower()
        if any(token in name for token in ("budget", "econom", "дешев")):
            segment = PriceSegment.ECONOMY
        elif any(token in name for token in ("flagship", "pro", "premium", "премиум")):
            segment = PriceSegment.PREMIUM
        elif product.price < 15_000:
            segment = PriceSegment.ECONOMY
        elif product.price > 60_000:
            segment = PriceSegment.PREMIUM
        else:
            segment = PriceSegment.STANDARD

        return EnrichedProduct(**product.model_dump(), segment=segment)


def _chunk(items: list[Product], size: int) -> Iterable[list[Product]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
