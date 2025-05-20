from typing import Any, TypedDict, Union

from howler.odm import Model
from howler.odm.models.hit import Hit


class SearchResult(TypedDict):
    """Search Results for an Elastic search query.

    TypedDict's are used in the same way as a normal Dict, but provides typing for InteliSense
    """

    offset: int
    rows: int
    total: int
    items: list[Union[Model, dict[str, Any]]]


class HitSearchResult(SearchResult):
    """Hit specific typing for Elastic search query"""

    items: list[Union[Hit, dict[str, Any]]]  # type: ignore[misc]
