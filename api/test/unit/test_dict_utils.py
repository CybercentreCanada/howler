from howler.utils.dict_utils import flatten_deep


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
