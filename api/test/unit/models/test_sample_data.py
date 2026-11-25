"""Generated model data exercises validation and primitive round trips."""

import pytest

from howler.models.action import Action
from howler.models.analytic import Analytic
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.user import User
from howler.sample_data.randomizer import random_minimal_obj, random_model_obj


@pytest.mark.parametrize("model", [Action, Analytic, Event, Hit, User])
@pytest.mark.parametrize("generator", [random_model_obj, random_minimal_obj])
def test_generated_model_round_trips(model, generator):
    instance = generator(model)
    data = instance.as_primitives()
    data.pop("__index", None)
    restored = model.model_validate(data)
    assert restored.as_primitives() == instance.as_primitives()
