from types import SimpleNamespace
from unittest.mock import MagicMock

from howler.actions import change_field
from howler.models import model_extensions
from howler.models.fields import keyword
from howler.models.hit import Hit
from howler.models.registry import model_registry


def test_change_field_accepts_finalized_hit_extension(monkeypatch):
    monkeypatch.setattr(model_extensions, "_pending", {})
    monkeypatch.setattr(model_extensions, "_finalized", {})
    monkeypatch.setattr(model_registry, "_models", dict(model_registry._models))

    field = "plugin_extension"
    model_extensions.declare(Hit, field, keyword(), plugin="test-plugin")
    hit_model = model_extensions.finalize(Hit)

    hit_collection = SimpleNamespace(model_class=hit_model, update_by_query=MagicMock())
    monkeypatch.setattr(change_field, "datastore", lambda: SimpleNamespace(hit=hit_collection))

    options = change_field.specification()["steps"][0]["options"]["field"]
    assert field in options

    result = change_field.execute("*:*", field, "updated")

    assert result[0]["outcome"] == "success"
    hit_collection.update_by_query.assert_called_once()
    update = hit_collection.update_by_query.call_args.args[1][0]
    assert update.key == field
    assert update.value == "updated"
