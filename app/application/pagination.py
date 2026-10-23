"""Domain-level pagination independent of HTTP concerns."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Page[G]:
    """One page of results with computed totals."""

    items: list[G] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Zero pages for an empty set."""
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


def paginate[G](items: list[G], total: int, page: int, page_size: int) -> Page[G]:
    """Build a Page from repository results."""
    return Page(items=items, total=total, page=page, page_size=page_size)
