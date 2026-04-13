import sys
from typing import Generic, TypeVar

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    # typing_extensions.TypedDict supports Generic mixing on Python < 3.11
    from typing_extensions import NotRequired, TypedDict

SearchResultType = TypeVar("SearchResultType")


class SearchResult(TypedDict, Generic[SearchResultType]):
    offset: int
    rows: int
    total: int
    items: list[SearchResultType]
    next_deep_paging_id: NotRequired[str | None]
