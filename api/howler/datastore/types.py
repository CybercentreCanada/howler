from typing import Generic, TypeVar

from howler.utils.compat import NotRequired, TypedDict

SearchResultType = TypeVar("SearchResultType")


class SearchResult(TypedDict, Generic[SearchResultType]):
    offset: int
    rows: int
    total: int
    items: list[SearchResultType]
    next_deep_paging_id: NotRequired[str | None]
