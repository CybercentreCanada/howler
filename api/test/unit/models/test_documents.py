"""Validation and defaults for non-case Howler document models."""

from __future__ import annotations

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


class TestAction:
    """Tests for action fields and trigger validation."""

    def test_action_keeps_owner_and_default_membership_fields(self) -> None:
        action = Action.model_validate(
            {
                "action_id": "action-1",
                "owner": "user-1",
                "name": "My Action",
                "query": "howler.id:*",
                "triggers": ["create", "promote"],
                "operations": [{"operation_id": "operation-1"}],
            }
        )
        primitives = action.as_primitives()

        assert action.owner == "user-1"
        assert primitives["admins"] == []
        assert primitives["members"] == []
        assert "owner_id" not in primitives
        assert primitives["triggers"] == ["create", "promote"]
        assert action.operations[0].operation_id == "operation-1"

    def test_action_rejects_unsupported_trigger(self) -> None:
        with pytest.raises(HowlerModelValidationError):
            Action.model_validate(
                {
                    "action_id": "action-2",
                    "owner": "user-1",
                    "name": "My Action",
                    "query": "howler.id:*",
                    "triggers": ["not-a-trigger"],
                }
            )

    def test_action_name_is_required(self) -> None:
        with pytest.raises(HowlerModelValidationError):
            Action.model_validate({"action_id": "action-3", "query": "howler.id:*"})


class TestAnalytic:
    """Tests for analytic defaults."""

    def test_triage_options_have_independent_default_lists(self) -> None:
        analytic = Analytic.model_validate({"analytic_id": "analytic-1", "name": "My Analytic"})

        assert analytic.triage_settings.skip_rationale is False
        assert analytic.triage_settings.valid_assessments == Assessment.list()
        assert analytic.triage_settings.rationales == []
        assert analytic.triage_settings.dossiers == []

        second = Analytic.model_validate({"analytic_id": "analytic-2", "name": "Another Analytic"})
        analytic.triage_settings.rationales.append("benign")
        assert second.triage_settings.rationales == []


class TestOverviewAndTemplate:
    """Tests for overview and template document fields."""

    def test_overview_keeps_content_and_omits_absent_optional_fields(self) -> None:
        overview = Overview.model_validate(
            {"overview_id": "overview-1", "analytic": "analytic-1", "content": "# Title"}
        )
        primitives = overview.as_primitives()

        assert primitives["analytic"] == "analytic-1"
        assert primitives["content"] == "# Title"
        assert "detection" not in primitives
        assert "owner" not in primitives

    def test_template_accepts_required_analytic_and_key_list(self) -> None:
        template = Template.model_validate(
            {"template_id": "template-1", "analytic": "analytic-1", "type": "global", "keys": ["howler.id"]}
        )
        assert template.analytic == "analytic-1"
        assert template.keys == ["howler.id"]

        with pytest.raises(HowlerModelValidationError):
            Template.model_validate({"template_id": "template-2", "type": "global", "keys": []})


class TestUser:
    """Tests for user defaults and non-indexed access controls."""

    def test_user_has_default_quota_groups_and_classification(self) -> None:
        user = User.model_validate({"name": "Test User", "uname": "test", "password": "hashed-password"})

        assert user.api_quota == 25
        assert user.groups == ["USERS"]
        assert user.is_active is True
        assert user.type == ["user", "actionrunner_basic"]
        assert str(user.classification) == "UNRESTRICTED"

    def test_access_control_mapping_is_disabled(self) -> None:
        access_control = model_registry.mapping(User)["properties"]["access_control"]
        assert access_control["index"] is False
        assert access_control["doc_values"] is False


class TestViewAndDossier:
    """Tests for ownership fields and nested dossier content."""

    def test_view_settings_and_ownership_defaults(self) -> None:
        view = View.model_validate(
            {"view_id": "view-1", "title": "My View", "query": "*:*", "type": "personal", "owner": "me"}
        )

        assert view.owner == "me"
        assert view.admins == []
        assert view.members == []
        assert view.indexes == ["hit"]
        assert view.settings.advance_on_triage is False

    def test_dossier_keeps_embedded_leads_and_pivots(self) -> None:
        dossier = Dossier.model_validate(
            {
                "dossier_id": "dossier-1",
                "title": "My Dossier",
                "owner": "me",
                "type": "personal",
                "leads": [
                    {
                        "label": {"en": "English label", "fr": "Etiquette francaise"},
                        "format": "markdown",
                        "content": "# Some content",
                    }
                ],
                "pivots": [
                    {
                        "label": {"en": "Pivot label", "fr": "Etiquette de pivot"},
                        "value": "some-value",
                        "format": "url",
                        "mappings": [{"key": "id", "field": "howler.id"}],
                    }
                ],
            }
        )

        assert dossier.owner == "me"
        assert dossier.admins == []
        assert dossier.members == []
        assert dossier.leads[0].content == "# Some content"
        assert dossier.pivots[0].icon == "material-symbols:link"
        assert dossier.pivots[0].group is None
