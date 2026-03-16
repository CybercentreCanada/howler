import sys
from typing import Generic, TypedDict, TypeVar

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired

SearchResultType = TypeVar("SearchResultType")


class SearchResult(TypedDict, Generic[SearchResultType]):
    offset: int
    rows: int
    total: int
    items: list[SearchResultType]
    next_deep_paging_id: NotRequired[str | None]
