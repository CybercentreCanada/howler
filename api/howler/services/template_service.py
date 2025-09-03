from typing import Any, Optional, Union

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


def get_matching_templates(
    hits: Union[list[Hit], list[dict[str, Any]]], uname: Optional[str] = None, as_odm: bool = False
) -> Union[list[dict[str, Any]], list[Analytic]]:
    """Generate a list of templates matching a given list of analytic names, and optionally a user.

    Args:
        hits (list[Hit] | list[dict[str, Any]]]: List of hits, each containing analytic information.
        uname (Optional[str], optional): Username to filter templates by owner. Defaults to None.
        as_odm (bool, optional): If True, return results as ODM objects. If False, return as dicts. Defaults to False.

    Returns:
        list[dict[str, Any]] | list[Analytic]: List of matching templates, either as dicts or Analytic ODM objects.
    """
    if len(hits) < 1:
        return []

    analytic_names: set[str] = set()
    for hit in hits:
        analytic_names.add(f'"{sanitize_lucene_query(hit["howler"]["analytic"])}"')

    if len(analytic_names) < 1:
        return []

    try:
        template_candidates = datastore().template.search(
            f"analytic:({' OR '.join(analytic_names)}) AND (type:global OR owner:{uname or '*'})",
            as_obj=as_odm,
        )["items"]

        return template_candidates
    except SearchException:
        logger.exception("Exception on analytic matching")
        return []
