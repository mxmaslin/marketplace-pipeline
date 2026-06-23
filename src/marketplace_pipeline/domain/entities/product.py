from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Product(BaseModel):
    """Catalog item aggregate root before segmentation."""

    id: str
    name: str
    price: float = Field(ge=0)
    currency: str = "RUB"
    url: HttpUrl
    category: str
    collected_at: datetime
    description: str = ""
