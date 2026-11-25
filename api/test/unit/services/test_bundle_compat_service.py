from unittest.mock import MagicMock, patch

from howler.models import construct_partial
from howler.models.case import Case, CaseItemTypes
from howler.models.hit import Hit
from howler.services import bundle_compat_service


def test_synthesize_bundle_response_filters_children_for_user():
    case = MagicMock()
    case.case_id = "case-001"
    child = MagicMock(type=CaseItemTypes.HIT, value="restricted-hit")
    case.items = [child]

    root_hit = MagicMock()
    root_hit.howler.id = "root-hit"
    root_hit.as_primitives.return_value = {"howler": {}}
    user = MagicMock()

    with patch.object(
        bundle_compat_service.hit_service,
        "filter_accessible_hits",
        return_value=[],
    ) as filter_hits:
        result = bundle_compat_service.synthesize_bundle_response(case, root_hit, user=user)

    filter_hits.assert_called_once_with(user, ["restricted-hit"])
    assert result["howler"]["hits"] == []
    assert result["howler"]["bundle_size"] == 0


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


def test_synthesized_bundle_contains_compatibility_response_fields():
    root_hit = construct_partial(Hit, {"howler": {"id": "root-hit", "related": []}})
    case = construct_partial(
        Case,
        {
            "case_id": "case-1",
            "items": [
                {"type": "hit", "value": "root-hit"},
                {"type": "folder", "name": "hits"},
                {"type": "hit", "value": "child-hit"},
            ],
        },
    )

    response = bundle_compat_service.synthesize_bundle_response(case, root_hit, warnings=["warning"])

    assert response["howler"]["is_bundle"] is True
    assert response["howler"]["hits"] == ["child-hit"]
    assert response["howler"]["bundle_size"] == 1
    assert response["_case_id"] == "case-1"
    assert response["_warnings"] == ["warning"]
    assert response["_deprecation"] == bundle_compat_service.DEPRECATION_MESSAGE
