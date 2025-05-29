import howler.odm as odm
from howler.common.logging import get_logger
from howler.odm.models.hit import Hit

from sentinel.odm.models.sentinel import Sentinel

logger = get_logger(__file__)


def modify_odm(target):
    "Add additional internal fields to the ODM"
    logger.info("Modifying ODM with additional fields")

    target.add_namespace(
        "sentinel",
        odm.Optional(odm.Compound(Sentinel, description="Sentinel metadata associated with this alert")),
    )


def generate_useful_hit(hit: Hit) -> Hit:
    "Add cccs-specific changes to hits on generation"
    hit.sentinel = Sentinel({"id": "example-sentinel-id"})

    return ["sentinel"], hit
