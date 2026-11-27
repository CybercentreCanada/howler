from unittest.mock import MagicMock, patch

from howler.models import construct_partial
from howler.models.case import Case, CaseItemTypes
from howler.models.hit import Hit
from howler.services import bundle_compat_service


def test_synthesize_bundle_response_filters_children_for_user():
    case = MagicMock()
    case.case_id = "case-001"
    child = MagicMock(type=CaseItemTypes.HIT, value="restricted-hit")
    case.items = [child, MagicMock(type=CaseItemTypes.HIT, value="root-hit"), MagicMock(type=CaseItemTypes.FOLDER)]

    root_hit = MagicMock()
    root_hit.howler.id = "root-hit"
    root_hit.as_primitives.side_effect = lambda: {"howler": {}}
    user = MagicMock()

    with patch.object(
        bundle_compat_service.hit_service,
        "filter_accessible_hits",
        return_value=[],
    ) as filter_hits:
        result = bundle_compat_service.synthesize_bundle_response(case, root_hit, user=user, warnings=["warning"])

    filter_hits.assert_called_once_with(user, ["restricted-hit"])
    assert result["howler"]["hits"] == []
    assert result["howler"]["bundle_size"] == 0
    assert result["_warnings"] == ["warning"]
    unfiltered = bundle_compat_service.synthesize_bundle_response(case, root_hit)
    assert unfiltered["howler"]["hits"] == ["restricted-hit"]
    assert "_warnings" not in unfiltered


def test_find_bundle_case_uses_the_root_hit_backreference():
    hit = construct_partial(Hit, {"howler": {"related": ["case-1"]}})
    case = construct_partial(Case, {"case_id": "case-1", "items": [{"type": "hit", "value": "root-hit"}]})
    datastore = MagicMock()
    datastore.case.get.return_value = case

    with (
        patch.object(bundle_compat_service.hit_service, "get_hit", return_value=hit),
        patch.object(bundle_compat_service, "datastore", return_value=datastore),
    ):
        assert bundle_compat_service.find_case_for_bundle("root-hit") is case
