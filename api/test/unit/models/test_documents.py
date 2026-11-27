import pytest

from howler.models import HowlerModelValidationError, model_registry
from howler.models.action import Action
from howler.models.analytic import Analytic
from howler.models.dossier import Dossier
from howler.models.howler_data import Assessment
from howler.models.overview import Overview
from howler.models.template import Template
from howler.models.user import User
from howler.models.view import View


def test_action_fields_and_triggers():
    data = {"action_id": "action-1", "owner": "user-1", "name": "My Action", "query": "howler.id:*"}
    action = Action.model_validate({**data, "triggers": ["create", "promote"], "operations": [{"operation_id": "op"}]})
    primitives = action.as_primitives()
    assert primitives["owner"] == "user-1" and "owner_id" not in primitives
    assert primitives["admins"] == primitives["members"] == []
    assert primitives["triggers"] == ["create", "promote"] and action.operations[0].operation_id == "op"
    with pytest.raises(HowlerModelValidationError):
        Action.model_validate({**data, "triggers": ["not-a-trigger"]})


def test_analytic_triage_defaults_are_independent():
    first = Analytic.model_validate({"name": "First"}).triage_settings
    second = Analytic.model_validate({"name": "Second"}).triage_settings
    assert not first.skip_rationale and first.valid_assessments == Assessment.list()
    assert first.rationales == first.dossiers == []
    first.rationales.append("benign")
    assert second.rationales == []


def test_overview_and_template():
    overview = Overview.model_validate({"analytic": "analytic-1", "content": "# Title"}).as_primitives()
    assert overview["content"] == "# Title" and "detection" not in overview and "owner" not in overview
    template = Template.model_validate({"analytic": "analytic-1", "type": "global", "keys": ["howler.id"]})
    assert template.keys == ["howler.id"]
    with pytest.raises(HowlerModelValidationError):
        Template.model_validate({"type": "global", "keys": []})


def test_user_defaults_and_access_control_mapping():
    user = User.model_validate({"name": "Test User", "uname": "test", "password": "hashed-password"})
    assert user.api_quota == 25 and user.groups == ["USERS"] and user.is_active
    assert user.type == ["user", "actionrunner_basic"] and str(user.classification) == "UNRESTRICTED"
    access_control = model_registry.mapping(User)["properties"]["access_control"]
    assert access_control["index"] is False and access_control["doc_values"] is False


def test_view_and_dossier_defaults():
    view = View.model_validate({"title": "View", "query": "*:*", "type": "personal", "owner": "me"})
    assert view.owner == "me" and view.admins == view.members == []
    assert view.indexes == ["hit"] and not view.settings.advance_on_triage
    dossier = Dossier.model_validate(
        {
            "title": "Dossier",
            "owner": "me",
            "type": "personal",
            "leads": [{"label": {"en": "Lead", "fr": "Etiquette"}, "format": "markdown", "content": "# Content"}],
            "pivots": [{"label": {"en": "Pivot", "fr": "Pivot"}, "value": "value", "format": "url"}],
        }
    )
    assert dossier.leads[0].content == "# Content"
    assert dossier.pivots[0].icon == "material-symbols:link" and dossier.pivots[0].group is None
