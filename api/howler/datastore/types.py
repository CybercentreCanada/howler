from typing import Generic, TypedDict, TypeVar

SearchResultType = TypeVar("SearchResultType")


class _SearchResult(TypedDict, Generic[SearchResultType]):
    offset: int
    rows: int
    total: int
    items: list[SearchResultType]


class SearchResult(_SearchResult, total=False):
    next_deep_paging_id: str | None
