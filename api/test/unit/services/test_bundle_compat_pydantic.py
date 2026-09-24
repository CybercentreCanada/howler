"""Bundle compatibility responses use registered Pydantic documents."""

from unittest.mock import MagicMock, patch

from howler.models import construct_partial
from howler.models.case import Case
from howler.models.hit import Hit
from howler.services import bundle_compat_service


def test_find_bundle_case_from_pydantic_backreference():
    hit = construct_partial(Hit, {"howler": {"related": ["case-1"]}})
    case = construct_partial(
        Case,
        {"case_id": "case-1", "items": [{"type": "hit", "value": "root-hit"}]},
    )
    datastore = MagicMock()
    datastore.case.get.return_value = case

    with (
        patch.object(bundle_compat_service.hit_service, "get_hit", return_value=hit),
        patch.object(bundle_compat_service, "datastore", return_value=datastore),
    ):
        assert bundle_compat_service.find_case_for_bundle("root-hit") is case


def test_synthesized_bundle_preserves_legacy_response_shape_for_pydantic_models():
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
