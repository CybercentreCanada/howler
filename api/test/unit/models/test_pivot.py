import pytest

from howler.common.exceptions import HowlerValueError
from howler.models import HowlerModelValidationError
from howler.models.dossier import Dossier
from howler.models.pivot import Pivot, validate_group

PIVOT = {"label": {"en": "Pivot", "fr": "Pivot"}, "value": "pivot.value", "format": "link"}
DUPLICATES = [{"key": "host", "field": "host.name"}, {"key": "host", "field": "host.hostname"}]


@pytest.mark.parametrize("group", ["Folder with spaces/alert #1", "case-id_v1/report.pdf"])
def test_pivot_accepts_case_item_style_group_paths(group):
    assert Pivot(**PIVOT, group=group).group == group


@pytest.mark.parametrize("group", ["", "/group", "group/", "group//child", 1, ["group"], {"group": "value"}, True])
def test_pivot_rejects_invalid_groups(group):
    with pytest.raises(HowlerValueError):
        Pivot(**PIVOT, group=group)


def test_pivot_defaults_and_duplicate_mappings():
    validate_group(None)
    assert Pivot(**PIVOT).icon == "material-symbols:link"
    with pytest.raises(HowlerValueError, match="duplicate keys"):
        Pivot(**PIVOT, mappings=DUPLICATES)


@pytest.mark.parametrize(
    ("extra", "error"),
    [
        ({"group": "bad//group"}, "empty segments"),
        ({"mappings": DUPLICATES}, "duplicate keys"),
    ],
)
def test_pivot_validators_run_in_nested_dossier(extra, error):
    with pytest.raises(HowlerModelValidationError, match=error):
        Dossier.model_validate(
            {"title": "Dossier", "type": "global", "owner": "analyst", "pivots": [{**PIVOT, **extra}]}
        )
