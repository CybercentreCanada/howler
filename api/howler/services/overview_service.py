from typing import Any, Literal, overload

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.odm.models.hit import Hit
from howler.odm.models.overview import Overview
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


@overload
def get_matching_overviews(
    hits: list[Hit] | list[dict[str, Any]], as_odm: Literal[False] = False
) -> list[dict[str, Any]]: ...


@overload
def get_matching_overviews(hits: list[Hit] | list[dict[str, Any]], as_odm: Literal[True]) -> list[Overview]: ...


def get_matching_overviews(hits: list[Hit] | list[dict[str, Any]], as_odm=False):
    """Generate a list of overviews matching a given list of analytic names from the provided hits.

    Args:
        hits (list[Hit] | list[dict[str, Any]]): A list of Hit objects or dictionaries containing analytic information.
        as_odm (bool, optional): If True, return Overview objects; otherwise, return dictionaries. Defaults to False.

    Returns:
        list[dict[str, Any]] | list[Overview]: A list of matching overviews, either as dictionaries or Overview objects.
    """
    if len(hits) < 1:
        return []

    analytic_names: set[str] = set()
    for hit in hits:
        analytic_names.add(f'"{sanitize_lucene_query(hit["howler"]["analytic"])}"')

    if len(analytic_names) < 1:
        return []

    try:
        return datastore().overview.search(
            f"analytic:({' OR '.join(analytic_names)})",
            as_obj=as_odm,
        )["items"]
    except SearchException:
        logger.exception("Exception on analytic matching")
        return []
