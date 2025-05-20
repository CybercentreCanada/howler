from howler.common.loader import datastore
from howler.common.logging import get_logger
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


def get_analytic(
    id: str,
    as_obj: bool = False,
    version: bool = False,
):
    """Return analytic object as either an ODM or Dict"""
    return datastore().analytic.get_if_exists(key=id, as_obj=as_obj, version=version)


def update_analytic(
    analytic_id: str,
    operations: list[OdmUpdateOperation],
):
    """Update one or more properties of an analytic in the database."""
    storage = datastore()

    result = storage.analytic.update(analytic_id, operations)

    return result


def save_from_hit(hit: Hit, user: User):
    """Save updates to an analytic based on a new hit that has been created

    Args:
        hit (Hit): The newly created hit to use to update the analytic entry
    """
    storage = datastore()

    save = False
    existing_analytics: list[Analytic] = storage.analytic.search(
        f'name:"{sanitize_lucene_query(hit.howler.analytic)}"'
    )["items"]
    if len(existing_analytics) > 0:
        analytic: Analytic = existing_analytics[0]

        if not analytic.owner:
            save = True
            analytic.owner = user["uname"]

        if user["uname"] not in analytic.contributors:
            analytic.contributors.append(user["uname"])

        if hit.howler.detection:
            new_detections = [d for d in analytic.detections if d.lower() != (hit.howler.detection or "").lower()]
            new_detections.append(hit.howler.detection)

            new_detections = sorted(new_detections)

            if new_detections != analytic.as_primitives()["detections"]:
                save = True
                analytic.detections = new_detections

        if len(existing_analytics) > 1:
            logger.warning("Duplicate analytics detected! Removing duplicates...")
            for duplicate in existing_analytics[1:]:
                storage.analytic.delete(duplicate.analytic_id)

            storage.analytic.commit()
    else:
        save = True
        analytic = Analytic(
            {
                "name": hit.howler.analytic,
                "owner": user["uname"],
                "contributors": [user["uname"]],
                "detections": [hit.howler.detection] if hit.howler.detection else [],
                "description": "Placeholder Description - Défaut Description",
                "triage_settings": {
                    "valid_assessments": Assessment.list(),
                    "skip_rationale": False,
                },
            }
        )

    if save:
        storage.analytic.save(analytic.analytic_id, analytic)

        # This is necessary as we often save over the analytic multiple times in quick succession when saving from hits
        storage.analytic.commit()
