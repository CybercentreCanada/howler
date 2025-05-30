from random import randint

import howler.odm as odm
from howler.common.logging import get_logger
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj

from evidence.odm.models.evidence import Evidence

logger = get_logger(__file__)


def modify_odm(target: odm.Model):
    "Add additional internal fields to the ODM"
    logger.info("Modifying ODM with additional fields")

    target.add_namespace(
        "evidence",
        odm.List(
            odm.Compound(Evidence),
            default=[],
            description="A list of additional ECS objects.",
        ),
    )


def generate_useful_hit(hit: Hit) -> Hit:
    "Add cccs-specific changes to hits on generation"
    hit.evidence = [random_model_obj(Evidence) for _ in range(randint(1, 3))]

    return ["evidence"], hit
