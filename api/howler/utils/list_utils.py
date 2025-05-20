from typing import Any


def flatten_list(_list: list[list[Any]]):
    "Flatten a nested list"
    flat_list = []
    for sublist in _list:
        for item in sublist:
            flat_list.append(item)

    return flat_list
