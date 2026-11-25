import builtins
from typing import Generic, TypeVar

from typing_extensions import NotRequired, TypedDict

SearchResultType = TypeVar("SearchResultType")


class FieldDescription(TypedDict):
    """Public field descriptor in `/configs` and collection field discovery."""

    default: bool
    indexed: bool
    list: bool
    stored: bool
    deprecated: NotRequired[bool]  # Omitted on dynamic mapping summaries.
    type: str
    description: str | None
    regex: str | None
    values: builtins.list[object] | None  # Plugins may declare non-string enum values.
    deprecated_description: str | None


class SearchResult(TypedDict, Generic[SearchResultType]):
    offset: int
    rows: int
    total: int
    items: list[SearchResultType]
    next_deep_paging_id: NotRequired[str | None]


class AggSearchResult(SearchResult[SearchResultType]):
    aggregations: dict[str, dict]
