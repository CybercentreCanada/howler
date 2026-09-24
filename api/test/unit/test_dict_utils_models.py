"""Flattening and unknown-field reporting against Pydantic field metadata."""

from howler.models.event import Event
from howler.models.hit import Hit
from howler.utils.dict_utils import extra_keys, flatten


def test_model_flatten_keeps_dynamic_mapping_objects_and_recurses_compounds():
    document = {"howler": {"id": "event-1", "data": ["raw"]}, "labels": {"team": "blue"}}

    assert flatten(document, odm=Event) == {
        "howler.id": "event-1",
        "howler.data": ["raw"],
        "labels": {"team": "blue"},
    }


def test_extra_keys_accepts_mapping_children_but_reports_unknown_fields():
    assert extra_keys(Event, {"labels": {"team": "blue"}, "howler": {"unknown": True}}) == {"howler.unknown"}


def test_extra_keys_rejects_descendants_beneath_scalar_mapping_values():
    assert extra_keys(Hit, {"howler.comment.reactions.thumbs-up": ["user"]}) == set()
    assert extra_keys(Hit, {"howler.comment.reactions.thumbs-up.potato": ["user"]}) == {
        "howler.comment.reactions.thumbs-up.potato"
    }
