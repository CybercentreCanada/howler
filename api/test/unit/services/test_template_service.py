from unittest.mock import MagicMock, patch

from howler.models import construct_partial
from howler.models.hit import Hit
from howler.services import template_service


def test_matching_templates_uses_analytic_name_and_owner_filter():
    hit = construct_partial(Hit, {"howler": {"analytic": "Example Analytic"}})
    storage = MagicMock()
    storage.template.search.return_value = {"items": [{"template_id": "template-1"}]}

    with patch.object(template_service, "datastore", return_value=storage):
        result = template_service.get_matching_templates([hit], uname="analyst")

    assert result == [{"template_id": "template-1"}]
    storage.template.search.assert_called_once_with(
        'analytic:("Example Analytic") AND (type:global OR owner:analyst)',
        as_obj=False,
    )
