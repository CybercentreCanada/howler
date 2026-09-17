import pytest

from howler.common.exceptions import HowlerValueError
from howler.odm.models.pivot import Pivot


def pivot_data(**overrides):
    data = {
        "label": {"en": "Pivot", "fr": "Pivot"},
        "value": "pivot.value",
        "format": "link",
        "mappings": [{"key": "hostname", "field": "host.name"}],
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("group", ["Folder with spaces/alert #1", "case-id_v1/report.pdf"])
def test_pivot_accepts_case_item_style_group_paths(group):
    assert Pivot(pivot_data(group=group)).group == group


@pytest.mark.parametrize("group", ["", "/group", "group/", "group//child"])
def test_pivot_rejects_empty_group_segments(group):
    with pytest.raises(HowlerValueError):
        Pivot(pivot_data(group=group))


@pytest.mark.parametrize("group", [1, ["group"], {"group": "value"}, True])
def test_pivot_rejects_invalid_group_types(group):
    with pytest.raises(HowlerValueError):
        Pivot(pivot_data(group=group))


def test_pivot_rejects_duplicate_mapping_keys():
    with pytest.raises(HowlerValueError, match="duplicate keys"):
        Pivot(
            pivot_data(
                mappings=[
                    {"key": "hostname", "field": "host.name"},
                    {"key": "hostname", "field": "host.hostname"},
                ]
            )
        )
