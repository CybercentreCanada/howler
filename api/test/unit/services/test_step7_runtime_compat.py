"""Focused Step 7 compatibility tests for consumers migrated in Step 8."""

import inspect
from unittest.mock import MagicMock, patch

from flask import Flask

from howler.api.v1 import analytic as analytic_api
from howler.api.v1 import auth as auth_api
from howler.api.v1.hit import _runtime_hit_fields
from howler.cronjobs import view_cleanup
from howler.datastore.bulk import ElasticBulkPlan
from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmUpdateOperation
from howler.models import construct_partial, validate_field_value
from howler.models.analytic import Analytic, Notebook, TriageOptions
from howler.models.analytic import Comment as AnalyticComment
from howler.models.case import Case
from howler.models.case import CaseItem as SchemaCaseItem
from howler.models.ecs.related import Related
from howler.models.hit import Hit
from howler.models.user import ApiKey, User
from howler.odm.models.case import CaseRule
from howler.odm.models.howler_data import Comment
from howler.services import case_service, correlation_service, hit_service


def _analytic() -> Analytic:
    return Analytic.model_validate(
        {
            "analytic_id": "c09c3f16-53ef-47c2-8f22-6f6584713bd4",
            "name": "Test Analytic",
        }
    )


def test_hit_update_uses_registry_fields_for_pydantic_hits():
    hit = construct_partial(Hit, {"howler": {"labels": {"generic": []}}})
    datastore = MagicMock()
    datastore.hit.get.return_value = (hit, "new-version")

    with patch("howler.services.hit_service.datastore", return_value=datastore):
        data, version = hit_service._update_hit(
            "hit-1",
            [
                OdmUpdateOperation(
                    ESCollection.UPDATE_SET,
                    "howler.labels.generic",
                    ["label"],
                    silent=True,
                )
            ],
            version="old-version",
        )

    assert data is hit
    assert version == "new-version"
    datastore.hit.update.assert_called_once()


def test_hit_label_validation_uses_registry_fields_for_pydantic_hits():
    hit = construct_partial(Hit, {"howler": {"labels": {"generic": []}}})

    assert "howler.labels.generic" in _runtime_hit_fields(hit)
    assert "labels" in hit.howler
    assert "missing" not in hit.howler


def test_legacy_comment_update_value_is_converted_to_primitives():
    comment = Comment({"user": "user-1", "value": "Comment"})

    value = validate_field_value(Hit, "howler.comment", comment, list_item=True)

    assert value["id"] == comment.id
    assert value["user"] == "user-1"
    assert value["value"] == "Comment"


def test_case_related_indicator_collection_accepts_pydantic_model():
    related = Related.model_validate({"ip": ["127.0.0.1"], "hash": ["abc"]})

    assert case_service._collect_indicators_from_related(related) == {"127.0.0.1", "abc"}


def test_view_cleanup_updates_pydantic_user_by_attribute():
    user = construct_partial(
        User,
        {
            "uname": "user-1",
            "dashboard": [
                {
                    "entry_id": "deleted-view",
                    "type": "view",
                    "config": "{}",
                }
            ],
        },
    )
    datastore = MagicMock()
    datastore.user.search.return_value = {"total": 1, "items": [user]}
    datastore.view.search.return_value = {"total": 0, "items": []}

    with patch("howler.common.loader.datastore", return_value=datastore):
        view_cleanup.execute()

    assert user.dashboard == []
    datastore.user.save.assert_called_once_with("user-1", user)


def test_add_apikey_persists_pydantic_embedded_value():
    app = Flask("test")
    app.secret_key = "test"
    user = User.model_validate(
        {
            "uname": "user-1",
            "name": "User One",
            "password": "hash",
            "apikeys": {},
        }
    )
    datastore = MagicMock()
    datastore.user.get_if_exists.return_value = user

    with (
        app.test_request_context(json={"name": "automation", "priv": "RW"}),
        patch("howler.api.v1.auth.datastore", return_value=datastore),
        patch("howler.api.v1.auth.generate_random_secret", return_value="secret"),
        patch("howler.api.v1.auth.bcrypt.hash", return_value="bcrypt-hash"),
        patch("howler.api.v1.auth.auth_service.invalidate_apikey_cache"),
        patch.object(auth_api.config.auth, "max_apikey_duration_amount", None),
        patch.object(auth_api.config.auth, "max_apikey_duration_unit", None),
    ):
        response = inspect.unwrap(auth_api.add_apikey)(user={"uname": "user-1"})

    assert response.status_code == 200
    assert isinstance(user.apikeys["automation"], ApiKey)
    datastore.user.save.assert_called_once_with("user-1", user)
    User.validate_howler(user.as_primitives())


def test_analytic_mutations_persist_pydantic_embedded_values():
    app = Flask("test")
    app.secret_key = "test"
    analytic = _analytic()
    datastore = MagicMock()
    datastore.analytic.get.return_value = analytic
    analytic_service = MagicMock()
    analytic_service.does_analytic_exist.return_value = True
    analytic_service.get_analytic.return_value = analytic

    with (
        patch("howler.api.v1.analytic.datastore", return_value=datastore),
        patch("howler.api.v1.analytic.analytic_service", analytic_service),
        app.test_request_context(json={"triage_settings": {"skip_rationale": True}}),
    ):
        response = inspect.unwrap(analytic_api.update_analytic)("analytic-1", user=MagicMock())
    assert response.status_code == 200
    assert isinstance(analytic.triage_settings, TriageOptions)

    with (
        patch("howler.api.v1.analytic.datastore", return_value=datastore),
        patch("howler.api.v1.analytic.analytic_service", analytic_service),
        app.test_request_context(json={"value": "Investigation note"}),
    ):
        response = inspect.unwrap(analytic_api.add_comment)("analytic-1", user={"uname": "user-1"})
    assert response.status_code == 200
    assert isinstance(analytic.comment[-1], AnalyticComment)

    with (
        patch("howler.api.v1.analytic.datastore", return_value=datastore),
        patch("howler.api.v1.analytic.analytic_service", analytic_service),
        app.test_request_context(
            json={
                "value": "https://nbgallery.example/notebook/1",
                "name": "Investigation",
            }
        ),
    ):
        response = inspect.unwrap(analytic_api.add_notebook)("analytic-1", user={"uname": "user-1"})
    assert response.status_code == 200
    assert isinstance(analytic.notebooks[-1], Notebook)
    assert datastore.analytic.save.call_count == 3
    Analytic.validate_howler(analytic.as_primitives())


def test_correlation_appends_pydantic_case_item_that_bulk_serializes():
    case = Case.model_validate(
        {
            "case_id": "case-1",
            "title": "Case",
            "summary": "Summary",
            "overview": "Overview",
            "escalation": "normal",
        }
    )
    rule = CaseRule(
        {
            "query": "*:*",
            "destination": "related",
            "author": "user-1",
        }
    )
    backing = MagicMock()
    backing.classification = "UNRESTRICTED"

    with (
        patch("howler.services.correlation_service.case_service.get_parent_from_path", return_value=None),
        patch("howler.services.correlation_service.case_service.check_conflicts", return_value=False),
        patch("howler.services.correlation_service.case_service.add_backreference", return_value=False),
    ):
        correlation_service._add_record_to_case(
            case,
            "case-1",
            {"howler": {"id": "hit-1"}, "__index": "hit"},
            rule,
            {("hit", "hit-1"): backing},
        )

    assert isinstance(case.items[-1], SchemaCaseItem)
    plan = ElasticBulkPlan(["case"], Case)
    plan.add_update_operation("case-1", case, fields=["items"])
    assert '"value": "hit-1"' in plan.get_plan_data()
