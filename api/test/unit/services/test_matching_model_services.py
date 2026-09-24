"""Matching queries accept both stored dictionaries and Pydantic hit projections."""

from unittest.mock import MagicMock, patch

import pytest

from howler.models import construct_partial
from howler.models.hit import Hit
from howler.services import overview_service, template_service


@pytest.mark.parametrize(
    ("service", "collection"),
    [(overview_service, "overview"), (template_service, "template")],
)
@pytest.mark.parametrize("as_model", [False, True])
def test_matching_queries_accept_hit_models_and_dictionaries(service, collection, as_model):
    hit_data = {"howler": {"analytic": "Example Analytic"}}
    hit = construct_partial(Hit, hit_data) if as_model else hit_data
    storage = MagicMock()
    getattr(storage, collection).search.return_value = {"items": ["matched"]}

    with patch.object(service, "datastore", return_value=storage):
        result = (
            service.get_matching_templates([hit], as_odm=as_model)
            if collection == "template"
            else service.get_matching_overviews([hit], as_odm=as_model)
        )

    assert result == ["matched"]
    query = getattr(storage, collection).search.call_args.args[0]
    assert 'analytic:("Example Analytic")' in query
    assert getattr(storage, collection).search.call_args.kwargs["as_obj"] is as_model
