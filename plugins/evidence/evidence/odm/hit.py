"""Synthetic-data hook; field declarations live in evidence.models.hit."""

from random import randint

from howler.models.hit import Hit
from howler.sample_data.randomizer import random_model_obj

from evidence.models.evidence import Evidence


def generate_useful_hit(hit: Hit) -> tuple[list[str], Hit]:
    """Populate the finalized Evidence extension with synthetic ECS records."""
    hit["evidence"] = [random_model_obj(Evidence) for _ in range(randint(1, 3))]
    return ["evidence"], hit
