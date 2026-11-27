"""Generated model data exercises validation and primitive round trips."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from howler.models.action import Action
from howler.models.analytic import Analytic, Notebook
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.user import User
from howler.sample_data import random_data
from howler.sample_data.randomizer import random_minimal_obj, random_model_obj


@pytest.mark.parametrize("model", [Action, Analytic, Event, Hit, User])
@pytest.mark.parametrize("generator", [random_model_obj, random_minimal_obj])
def test_generated_model_round_trips(model, generator):
    instance = generator(model)
    data = instance.as_primitives()
    data.pop("__index", None)
    restored = model.model_validate(data)
    assert restored.as_primitives() == instance.as_primitives()


def _patch_sample_data_dependencies(monkeypatch):
    fields = {f"field_{index}": None for index in range(6)}
    monkeypatch.setattr(random_data.model_registry, "flat_fields", lambda _model: fields)
    monkeypatch.setattr(random_data, "run_modifications", lambda _odm, model, _log=False: model)
    return fields


def _assert_saved_ids_match_models(save_calls, id_field):
    saved_ids = [saved_id for saved_id, _model in save_calls]
    model_ids = [getattr(model, id_field) for _saved_id, model in save_calls]

    assert len(saved_ids) == len(set(saved_ids))
    assert all(saved_ids)
    assert saved_ids == model_ids


def test_create_templates_saves_constructed_templates(monkeypatch):
    _patch_sample_data_dependencies(monkeypatch)
    ds = SimpleNamespace(hit=SimpleNamespace(model_class=Hit), template=Mock())

    random_data.create_templates(ds)

    save_calls = ds.template.save.call_args_list
    saved = [(call.args[0], call.args[1]) for call in save_calls]
    assert len(saved) == 10
    _assert_saved_ids_match_models(saved, "template_id")
    ds.template.commit.assert_called_once_with()

    generated = [template for _template_id, template in saved if template.detection is not None]
    assert len(generated) == 4
    assert {template.detection for template in generated} == {"Detection 1", "Detection 2"}
    assert all(template.type == "global" for template in generated)
    assert all(len(template.keys) == 5 for template in generated)
    assert all(set(template.keys) <= {f"field_{index}" for index in range(6)} for template in generated)

    fixed = [template for _template_id, template in saved if template.detection is None]
    assert len(fixed) == 6
    for analytic in ["Password Checker", "Bad Guy Finder"]:
        templates = [template for template in fixed if template.analytic == analytic]
        assert [(template.owner, template.type, template.keys) for template in templates] == [
            (None, "global", ["howler.id", "howler.hash"]),
            ("admin", "personal", ["howler.id", "howler.hash", "howler.analytic", "agent.id"]),
            ("goose", "personal", ["agent.id", "agent.type", "container.id"]),
        ]


def test_create_overviews_saves_constructed_overviews(monkeypatch):
    _patch_sample_data_dependencies(monkeypatch)
    ds = SimpleNamespace(hit=SimpleNamespace(model_class=Hit), overview=Mock())

    random_data.create_overviews(ds)

    save_calls = ds.overview.save.call_args_list
    saved = [(call.args[0], call.args[1]) for call in save_calls]
    assert len(saved) == 6
    _assert_saved_ids_match_models(saved, "overview_id")
    ds.overview.commit.assert_called_once_with()

    generated = [overview for _overview_id, overview in saved if overview.detection is not None]
    assert len(generated) == 4
    for detection in ["Detection 1", "Detection 2"]:
        matching = [overview for overview in generated if overview.detection == detection]
        assert len(matching) == 2
        assert all(
            overview.analytic in {"Password Checker", "Bad Guy Finder", "SecretAnalytic"} for overview in matching
        )
        assert all(overview.owner == "admin" for overview in matching)
        assert all(overview.content.startswith("# Hello, World!\n\n{") for overview in matching)

    fixed = [overview for _overview_id, overview in saved if overview.detection is None]
    assert len(fixed) == 2
    assert {overview.analytic for overview in fixed} == {"Password Checker", "Bad Guy Finder"}
    assert all(overview.owner == "admin" for overview in fixed)
    assert all(overview.content.lstrip().startswith("# {{howler.analytic}} Alert") for overview in fixed)


def test_create_analytics_constructs_notebook_without_live_services(monkeypatch, tmp_path):
    _patch_sample_data_dependencies(monkeypatch)
    sigma_dir = tmp_path / "sigma"
    sigma_dir.mkdir()
    resolved_sigma_dirs = []

    def isolate_sample_data_path(source_file):
        assert source_file == random_data.__file__
        module_path = tmp_path / "random_data.py"
        resolved_sigma_dirs.append(module_path.parent / "sigma")
        return module_path

    existing_analytic = SimpleNamespace(
        analytic_id="existing-analytic",
        detections=[],
        comment=[],
        notebooks=[],
    )
    analytic_store = Mock()
    analytic_store.search.return_value = {"items": [existing_analytic]}
    users = [SimpleNamespace(uname=name) for name in ["admin", "user", "analyst"]]
    user_store = Mock()
    user_store.search.return_value = {"items": users}
    hit_store = Mock()
    hit_store.model_class = Hit
    ds = SimpleNamespace(analytic=analytic_store, user=user_store, hit=hit_store)

    monkeypatch.setattr(
        random_data,
        "config",
        SimpleNamespace(core=SimpleNamespace(notebook=SimpleNamespace(enabled=True))),
    )
    monkeypatch.setattr(random_data, "Path", isolate_sample_data_path)
    monkeypatch.setattr(random_data, "_keyword_fields", lambda _fields: ["howler.id"])
    monkeypatch.setattr(
        random_data,
        "random_model_obj",
        lambda _model: SimpleNamespace(
            analytic_id="generated-analytic",
            name="Generated analytic",
            detections=[],
            owner=None,
            contributors=[],
            rule=None,
            rule_crontab=None,
            rule_type=None,
            triage_settings=SimpleNamespace(valid_assessments=[]),
            description=None,
        ),
    )

    random_data.create_analytics(ds, num_analytics=0)

    assert resolved_sigma_dirs == [sigma_dir]
    assert list(sigma_dir.iterdir()) == []
    user_store.search.assert_called_once_with("*:*")
    saved_id, saved_analytic = analytic_store.save.call_args_list[0].args
    assert saved_id == "existing-analytic"
    assert saved_analytic is existing_analytic
    assert len(existing_analytic.notebooks) == 1
    notebook = existing_analytic.notebooks[0]
    assert isinstance(notebook, Notebook)
    assert notebook.id
    assert notebook.value == "Link to super notebook"
    assert notebook.name == "Super notebook"
    assert notebook.user in {"admin", "user", "analyst"}
    analytic_store.commit.assert_called_once_with()
    hit_store.commit.assert_called_once_with()
