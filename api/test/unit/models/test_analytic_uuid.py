import uuid
from datetime import datetime

import pytest
from pydantic import TypeAdapter

from howler.models import UUID, HowlerModelValidationError
from howler.models.action import Action
from howler.models.analytic import Analytic, Comment, Notebook
from howler.models.case import Case, CaseItem, CaseRule, CaseTask
from howler.models.dossier import Dossier
from howler.models.event import EventData
from howler.models.howler_data import Comment as HitComment
from howler.models.howler_data import HowlerData
from howler.models.overview import Overview
from howler.models.template import Template
from howler.models.view import View
from howler.utils.uid import get_random_id

UUID_FIELDS = [
    (Action, "action_id"),
    (Analytic, "analytic_id"),
    (Comment, "id"),
    (Notebook, "id"),
    (Case, "case_id"),
    (CaseItem, "id"),
    (CaseRule, "rule_id"),
    (CaseTask, "id"),
    (Dossier, "dossier_id"),
    (EventData, "id"),
    (HitComment, "id"),
    (HowlerData, "id"),
    (Overview, "overview_id"),
    (Template, "template_id"),
    (View, "view_id"),
]

ANALYTIC_ENTRIES = [
    (Comment, {"user": "analyst", "value": "Investigation note"}),
    (Notebook, {"user": "analyst", "name": "Investigation", "value": "https://nbgallery.example/notebook/1"}),
]


@pytest.mark.parametrize(("model", "field_name"), UUID_FIELDS)
def test_uuid_fields_declare_their_factory_for_static_constructors(model, field_name):
    field = model.model_fields[field_name]

    assert field.default_factory is get_random_id
    assert not field.is_required()


@pytest.mark.parametrize(("model", "data"), ANALYTIC_ENTRIES)
def test_analytic_entry_constructor_generates_an_id(model, data):
    entry = model(**data)

    assert entry.id
    assert entry.id == str(entry.id)


def test_comment_constructor_keeps_other_runtime_defaults():
    comment = Comment(user="analyst", value="Investigation note")

    assert isinstance(comment.timestamp, datetime)
    assert isinstance(comment.modified, datetime)
    assert comment.reactions == {}


@pytest.mark.parametrize(("model", "data"), ANALYTIC_ENTRIES)
def test_analytic_entry_constructor_preserves_explicit_id(model, data):
    explicit_id = uuid.UUID("10000000-0000-4000-8000-000000000001")

    entry = model(id=explicit_id, **data)

    assert entry.id == str(explicit_id)


@pytest.mark.parametrize(("model", "data"), ANALYTIC_ENTRIES)
def test_analytic_entry_constructor_generates_an_id_for_null(model, data):
    entry = model(id=None, **data)

    assert entry.id


def test_analytic_entry_constructor_keeps_model_validation_errors():
    with pytest.raises(HowlerModelValidationError, match="value"):
        Comment(user="analyst")


def test_uuid_alias_keeps_its_external_null_validation_behavior():
    generated_id = TypeAdapter(UUID).validate_python(None)

    assert generated_id
    assert generated_id == str(generated_id)
