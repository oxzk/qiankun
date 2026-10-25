"""Generic page envelope built on top of the application-layer Page."""

from __future__ import annotations

from app.api.schemas.response import ResponseModel


class PageResponse[T](ResponseModel):
    """Serialization shape of a paginated collection."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
