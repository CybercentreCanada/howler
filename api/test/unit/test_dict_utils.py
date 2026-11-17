from howler.models.event import Event
from howler.models.hit import Hit
from howler.utils.dict_utils import extra_keys, flatten, flatten_deep


def test_flatten_deep():
    test_object = {
        "field": "test",
        "field2": ["test1", "test2"],
        "nested": {
            "field": "test",
            "field2": ["test3", "test4"],
            "list": [
                {"field": "test", "field2": ["test5", "test6"], "list": []},
                {"field": "test7", "field2": ["test8", "test9"], "list": []},
            ],
        },
    }

    flattened = flatten_deep(test_object)

    assert flattened == {
        "field": "test",
        "field2": ["test1", "test2"],
        "nested.field": "test",
        "nested.field2": ["test3", "test4"],
        "nested.list.field": ["test", "test7"],
        "nested.list.field2": ["test5", "test6", "test8", "test9"],
        "nested.list.list": [],
    }


def test_flatten_uses_model_fields_and_preserves_dynamic_mapping_objects():
    document = {"howler": {"id": "event-1", "data": ["raw"]}, "labels": {"team": "blue"}}

    assert flatten(document, odm=Event) == {
        "howler.id": "event-1",
        "howler.data": ["raw"],
        "labels": {"team": "blue"},
    }


def test_extra_keys_accepts_mapping_children_and_reports_unknown_paths():
    assert extra_keys(Event, {"labels": {"team": "blue"}, "howler": {"unknown": True}}) == {"howler.unknown"}


def test_extra_keys_rejects_unknown_descendants_under_scalar_mapping_values():
    assert extra_keys(Hit, {"howler.comment.reactions.thumbs-up": ["user"]}) == set()
    assert extra_keys(Hit, {"howler.comment.reactions.thumbs-up.potato": ["user"]}) == {
        "howler.comment.reactions.thumbs-up.potato"
    }
