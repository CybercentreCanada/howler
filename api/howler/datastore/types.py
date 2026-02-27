from typing import Generic, NotRequired, TypedDict, TypeVar

SearchResultType = TypeVar("SearchResultType")


class SearchResult(TypedDict, Generic[SearchResultType]):
    offset: int
    rows: int
    total: int
    items: list[SearchResultType]
    next_deep_paging_id: NotRequired[str | None]
