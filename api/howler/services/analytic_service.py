from typing import Any, Literal, Union, overload

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.datastore.operations import OdmUpdateOperation
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Assessment
from howler.odm.models.user import User
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


def does_analytic_exist(analytic_id: str) -> bool:
    """Returns true if the analytic_id is already in use."""
    return datastore().analytic.exists(analytic_id)


@overload
def get_analytic(id: str, as_odm: Literal[True], version: Literal[True]) -> tuple[Analytic, str]: ...


@overload
def get_analytic(id: str, as_odm: Literal[True], version: Literal[False]) -> Analytic: ...


@overload
def get_analytic(id: str, as_odm: Literal[True]) -> Analytic: ...


@overload
def get_analytic(id: str) -> Analytic: ...


@overload
def get_analytic(id: str, as_odm: Literal[False], version: Literal[True]) -> tuple[dict[str, Any], str]: ...


@overload
def get_analytic(id: str, as_odm: Literal[False], version: Literal[False]) -> dict[str, Any]: ...


@overload
def get_analytic(id: str, as_odm: Literal[False]) -> dict[str, Any]: ...


def get_analytic(
    id: str,
    as_odm=False,
    version=False,
):
    """Return analytic object as either an ODM or Dict"""
    return datastore().analytic.get_if_exists(key=id, as_obj=as_odm, version=version)


def update_analytic(
    analytic_id: str,
    operations: list[OdmUpdateOperation],
):
    """Update one or more properties of an analytic in the database."""
    storage = datastore()

    result = storage.analytic.update(analytic_id, operations)

    return result


def get_matching_analytics(hits: Union[list[Hit], list[dict[str, Any]]]) -> list[Analytic]:
    """Get a list of matching analytics for the given list of hits.

    Args:
        hits (Union[list[Hit], list[dict[str, Any]]]): A list of Hit objects or dictionaries representing hits.
    Returns:
        list[Analytic]: A list of Analytic objects that match the analytics referenced in the hits.
    """
    if len(hits) < 1:
        return []

    storage = datastore()

    analytic_names: set[str] = set()
    for hit in hits:
        analytic_names.add(f'"{sanitize_lucene_query(hit["howler"]["analytic"])}"')

    try:
        existing_analytics: list[Analytic] = storage.analytic.search(
            f"name:({' OR '.join(analytic_names)})", as_obj=True
        )["items"]

        return existing_analytics
    except SearchException:
        logger.exception("Exception on analytic matching")
        return []


def save_from_hits(
    hits: Hit | list[Hit],
    user: User,
    refresh: Literal["true", "false", "wait_for"] | None = None,
):
    """Save updates to analytics based on new hits that have been created

    Args:
        hits (Hit | list[Hit]): The newly created hit(s) to use to update the analytic entry/entries
        refresh (Literal["true", "false", "wait_for"] | None): Refresh strategy used when saving analytics.
    """
    storage = datastore()

    if isinstance(hits, Hit):
        hits = [hits]

    # group by analytics for bulk update
    hits_by_analytic: dict[str, list[Hit]] = {}
    for hit in hits:
        hits_by_analytic.setdefault(hit.howler.analytic, []).append(hit)

    analytics = []
    for analytic_name, hit_group in hits_by_analytic.items():
        analytic_update = _get_analytic_updates_from_hit_group(analytic_name, hit_group, user)
        if analytic_update:
            analytics.append(analytic_update)

    if analytics:
        for analytic in analytics[:-1]:
            storage.analytic.save(analytic.analytic_id, analytic)

        # save the last one passing on the refresh parameter
        storage.analytic.save(analytics[-1].analytic_id, analytics[-1], refresh=refresh)


def _get_analytic_updates_from_hit_group(analytic_name: str, hit_group: list[Hit], user: User) -> Analytic | None:
    """Get the new or modified analytic object that should be saved or None if no changes"""
    storage = datastore()

    save = False
    existing_analytics: list[Analytic] = storage.analytic.search(f'name:"{sanitize_lucene_query(analytic_name)}"')[
        "items"
    ]
    if len(existing_analytics) > 0:
        analytic: Analytic = existing_analytics[0]

        if not analytic.owner:
            save = True
            analytic.owner = user.uname

        if user["uname"] not in analytic.contributors:
            analytic.contributors.append(user.uname)
            save = True

        hit_bundle_detections = [hit.howler.detection for hit in hit_group if hit.howler.detection]

        if hit_bundle_detections:
            detection_filter_list = [d.lower() for d in hit_bundle_detections]
            updated_detections = [d for d in analytic.detections if d.lower() not in detection_filter_list]
            updated_detections.extend(hit_bundle_detections)

            new_detections = sorted(updated_detections)

            if new_detections != analytic.as_primitives()["detections"]:
                save = True
                analytic.detections = new_detections

        if len(existing_analytics) > 1:
            logger.warning("Duplicate analytics detected! Removing duplicates...")
            for duplicate in existing_analytics[1:]:
                storage.analytic.delete(duplicate.analytic_id)

    else:
        save = True
        analytic = Analytic(
            {
                "name": analytic_name,
                "owner": user["uname"],
                "contributors": [user["uname"]],
                "detections": [hit.howler.detection for hit in hit_group if hit.howler.detection],
                "description": "Placeholder Description - Défaut Description",
                "triage_settings": {
                    "valid_assessments": Assessment.list(),
                    "skip_rationale": False,
                },
            }
        )

    if save:
        return analytic
    return None
