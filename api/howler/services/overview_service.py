from typing import Any, Union

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.odm.models.hit import Hit
from howler.odm.models.overview import Overview
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


def get_matching_overviews(
    hits: Union[list[Hit], list[dict[str, Any]]], as_odm: bool = False
) -> Union[list[dict[str, Any]], list[Overview]]:
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
        overview_candidates = datastore().overview.search(
            f"analytic:({' OR '.join(analytic_names)})",
            as_obj=as_odm,
        )["items"]

        return overview_candidates
    except SearchException:
        logger.exception("Exception on analytic matching")
        return []
