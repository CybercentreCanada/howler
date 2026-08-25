"""Differential tests for the remaining top-level models: action, analytic, overview, template,
user, view, and dossier (with its embedded lead/pivot/localized_label models)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from howler.models import model_registry
from howler.models.action import Action as NewAction
from howler.models.analytic import Analytic as NewAnalytic
from howler.models.dossier import Dossier as NewDossier
from howler.models.overview import Overview as NewOverview
from howler.models.template import Template as NewTemplate
from howler.models.user import User as NewUser
from howler.models.view import View as NewView
from howler.odm.models.action import Action as LegacyAction
from howler.odm.models.analytic import Analytic as LegacyAnalytic
from howler.odm.models.dossier import Dossier as LegacyDossier
from howler.odm.models.overview import Overview as LegacyOverview
from howler.odm.models.template import Template as LegacyTemplate
from howler.odm.models.user import User as LegacyUser
from howler.odm.models.view import View as LegacyView


def test_action_primitives_match_legacy() -> None:
    """Action documents (with enum-typed triggers) match the legacy ODM."""
    data = {
        "action_id": "a-1",
        "owner_id": "user-1",
        "name": "My Action",
        "query": "howler.id:*",
        "triggers": ["create", "promote"],
        "operations": [{"operation_id": "op-1"}],
    }
    legacy = LegacyAction(data)
    new = NewAction.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()


def test_action_rejects_invalid_trigger_like_legacy() -> None:
    """An unsupported trigger value is rejected by both implementations."""
    data = {
        "action_id": "a-2",
        "owner_id": "user-1",
        "name": "My Action",
        "query": "howler.id:*",
        "triggers": ["not-a-real-trigger"],
    }
    with pytest.raises(Exception):  # noqa: B017, PT011
        LegacyAction(data)
    with pytest.raises(ValidationError):
        NewAction.model_validate(data)


def test_analytic_default_triage_settings_match_legacy() -> None:
    """Default triage settings (including the assessment-derived valid_assessments) match."""
    data = {"analytic_id": "an-1", "name": "My Analytic"}
    legacy = LegacyAnalytic(data)
    new = NewAnalytic.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()


def test_overview_primitives_match_legacy() -> None:
    """Overview documents match the legacy ODM, including optional field omission."""
    data = {"overview_id": "o-1", "analytic": "an-1", "content": "# Title"}
    legacy = LegacyOverview(data)
    new = NewOverview.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()


def test_template_primitives_match_legacy() -> None:
    """Template documents match the legacy ODM."""
    data = {"template_id": "t-1", "analytic": "an-1", "type": "global", "keys": ["howler.id", "howler.status"]}
    legacy = LegacyTemplate(data)
    new = NewTemplate.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()


def test_user_defaults_and_classification_match_legacy() -> None:
    """User documents (with user-scoped classification and password/API-quota defaults) match."""
    data = {"name": "Test User", "uname": "test", "password": "hashed-password"}
    legacy = LegacyUser(data)
    new = NewUser.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()


def test_user_access_control_remains_unindexed() -> None:
    """The optional access-control expression retains its non-indexed legacy mapping."""
    access_control = model_registry.mapping(NewUser)["properties"]["access_control"]
    assert access_control["index"] is False
    assert access_control["doc_values"] is False


def test_view_settings_default_matches_legacy() -> None:
    """View documents (with nested Settings default) match the legacy ODM."""
    data = {"view_id": "v-1", "title": "My View", "query": "*:*", "type": "personal"}
    legacy = LegacyView(data)
    new = NewView.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()


def test_dossier_with_leads_and_pivots_matches_legacy() -> None:
    """Dossier documents, including nested leads/pivots/localized labels, match the legacy ODM."""
    data = {
        "dossier_id": "d-1",
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
    legacy = LegacyDossier(data)
    new = NewDossier.model_validate(data)
    assert new.as_primitives() == legacy.as_primitives()
