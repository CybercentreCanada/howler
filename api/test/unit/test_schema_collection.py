"""Unit tests for schema-model-driven ``ESCollection`` behavior (Step 6).

Mocks the Elasticsearch client so these run without a live cluster. Covers:

* ``_get_index_settings``/``_get_index_mappings`` delegating to ``howler.models.schema`` when a
  ``schema_model`` is registered, and falling back to the legacy ``build_mapping`` path when it
  is not (ad hoc/legacy-only callers, ``schema_model=None``).
* ``fields()`` computed from ``field_caps`` + a live mapping GET + ``model_registry``, preserving
  the legacy return shape and the legacy Mapping-child de-duplication quirk.
* Explicit multi-index conflict handling (never silently picking an arbitrary index/type).
* Reconciliation (``_check_fields``) adding safe explicit fields across every physical index and
  refusing additions that would require a new/changed dynamic template.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import elasticsearch
import pytest

from howler.common.exceptions import HowlerRuntimeError, HowlerValueError
from howler.datastore.collection import ESCollection
from howler.models import HowlerESModel, keyword, mapping, register_model
from howler.models import schema as new_schema

KEYWORD_MAPPING = {"type": "keyword", "ignore_above": 8191}


@register_model(index=True, store=True, id_field="key")
class ReconcileDoc(HowlerESModel):
    """A small top-level schema model dedicated to these collection-reconciliation tests."""

    key: keyword()
    name: keyword(description="A plain, statically-typed field.")
    tags: mapping(keyword(), default={}, description="A dynamic-key mapping field.")


@pytest.fixture(autouse=True)
def skip_ensure_collection():
    ESCollection.IGNORE_ENSURE_COLLECTION = True
    yield
    ESCollection.IGNORE_ENSURE_COLLECTION = False


@pytest.fixture()
def mock_datastore():
    ds = MagicMock()
    ds.client = MagicMock()
    ds.client.indices = MagicMock()
    ds.DEFAULT_SORT = "id asc"
    return ds


def _make_collection(mock_datastore, schema_model=ReconcileDoc):
    mock_datastore._models = {"testcol": None}
    return ESCollection(mock_datastore, "testcol", model_class=None, schema_model=schema_model)


class TestIndexSettingsAndMappingsDelegateToSchema:
    def test_settings_use_schema_when_present(self, mock_datastore):
        col = _make_collection(mock_datastore)
        settings = col._get_index_settings()
        assert settings == new_schema.index_settings(ReconcileDoc, shards=col.shards, replicas=col.replicas)

    def test_mappings_use_schema_when_present(self, mock_datastore):
        col = _make_collection(mock_datastore)
        assert col._get_index_mappings() == new_schema.document_mapping(ReconcileDoc)

    def test_legacy_path_preserved_when_schema_model_is_none(self, mock_datastore):
        """``schema_model=None`` preserves schema-less/legacy-runtime-model behavior untouched."""
        col = _make_collection(mock_datastore, schema_model=None)
        # No model_class either: exactly the historical schema-less collection contract.
        mappings = col._get_index_mappings()
        assert mappings["dynamic_templates"] == new_schema.default_dynamic_templates
        settings = col._get_index_settings()
        assert settings["index"]["mapping"]["total_fields"]["limit"] == 1500


class TestFieldsFromSchema:
    def test_matches_legacy_return_shape(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": {"type": "keyword", "ignore_above": 8191, "index": True, "doc_values": True},
                        "name": {"type": "keyword", "ignore_above": 8191, "index": True, "doc_values": True},
                        "tags": {"type": "object"},
                        "id": {"type": "keyword", "store": True, "doc_values": True},
                    }
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword": {"type": "keyword", "searchable": True, "aggregatable": True}},
                "name": {"keyword": {"type": "keyword", "searchable": True, "aggregatable": True}},
                "id": {"keyword": {"type": "keyword", "searchable": True, "aggregatable": True}},
            }
        }

        fields = col.fields()

        assert "id" not in fields  # synthetic id field is always popped
        assert fields["key"] == {
            "default": False,
            "indexed": True,
            "list": False,
            # ReconcileDoc is registered with store=True, which cascades to any field (like
            # ``key``) that does not set its own explicit ``store``.
            "stored": True,
            "deprecated": False,
            "type": "keyword",
            # ``key`` has no explicit description; legacy's ``field_model.description if
            # field_model else ""`` only substitutes "" when the field itself is entirely
            # unknown to the model, not when a known field's own description is None.
            "description": None,
            "regex": None,
            "values": None,
            "deprecated_description": None,
        }
        assert fields["name"]["description"] == "A plain, statically-typed field."

    def test_dynamic_mapping_child_produces_parent_summary_entry(self, mock_datastore):
        """A live dynamic key under an enabled Mapping field produces a parent-summary entry."""
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": KEYWORD_MAPPING,
                        "name": KEYWORD_MAPPING,
                        "tags": {
                            "properties": {
                                "first_key": {"type": "keyword", "index": True},
                            }
                        },
                    }
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword": {"type": "keyword", "searchable": True}},
                "name": {"keyword": {"type": "keyword", "searchable": True}},
                "tags.first_key": {"keyword": {"type": "keyword", "searchable": True}},
            }
        }

        fields = col.fields()

        assert "tags" in fields
        assert fields["tags"]["description"] == "A dynamic-key mapping field."
        assert fields["tags"]["type"] == "keyword"
        # Legacy quirk preserved: the first live dynamic child also gets its own entry.
        assert "tags.first_key" in fields
        assert "deprecated" not in fields["tags"]  # legacy's parent-summary branch omits this key

    def test_skip_mapping_children_omits_child_entries(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": KEYWORD_MAPPING,
                        "name": KEYWORD_MAPPING,
                        "tags": {"properties": {"first_key": {"type": "keyword", "index": True}}},
                    }
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {"fields": {}}

        fields = col.fields(skip_mapping_children=True)

        assert "tags" in fields
        assert "tags.first_key" not in fields

    def test_multi_index_mapping_conflict_is_raised_explicitly(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {"mappings": {"properties": {"key": KEYWORD_MAPPING}}},
            "testcol-000002": {"mappings": {"properties": {"key": {"type": "text", "index": True}}}},
        }
        mock_datastore.client.field_caps.return_value = {"fields": {}}

        with pytest.raises(HowlerRuntimeError, match="conflicting mappings"):
            col.fields()

    def test_multi_type_field_caps_conflict_is_raised_explicitly(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {"mappings": {"properties": {"key": KEYWORD_MAPPING}}},
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {
                    "keyword": {"type": "keyword", "searchable": True},
                    "text": {"type": "text", "searchable": True},
                }
            }
        }

        with pytest.raises(HowlerRuntimeError, match="conflicting types"):
            col.fields()


class TestCheckFieldsFromSchema:
    def test_adds_missing_safe_static_field_to_every_physical_index(self, mock_datastore):
        col = _make_collection(mock_datastore)
        col._index_list = ["testcol-000001", "testcol-000002"]
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        # `name` is present, `key` is (deliberately) missing from the live mapping.
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {"name": KEYWORD_MAPPING},
                    "dynamic_templates": expected_templates,
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {"name": {"keyword": {"type": "keyword", "searchable": True}}}
        }
        mock_datastore.client.indices.exists_template.return_value = False

        col._check_fields()

        put_mapping_calls = mock_datastore.client.indices.put_mapping.call_args_list
        indexes_called = {call.kwargs["index"] for call in put_mapping_calls}
        assert indexes_called == set(col.index_list_full)
        for call in put_mapping_calls:
            assert "key" in call.kwargs["properties"]

    def test_refuses_missing_dynamic_template(self, mock_datastore):
        """A brand-new dynamic template (not yet present on the live index) is refused."""
        col = _make_collection(mock_datastore)
        col._index_list = ["testcol_hot"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": KEYWORD_MAPPING,
                        "name": KEYWORD_MAPPING,
                    },
                    "dynamic_templates": [],
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword": {"type": "keyword", "searchable": True}},
                "name": {"keyword": {"type": "keyword", "searchable": True}},
            }
        }
        mock_datastore.client.indices.exists_template.return_value = False

        with pytest.raises(HowlerValueError, match="Refusing to add or change dynamic mapping templates"):
            col._check_fields()
        mock_datastore.client.indices.put_mapping.assert_not_called()
        mock_datastore.client.indices.put_settings.assert_not_called()

    def test_matching_dynamic_template_is_not_refused(self, mock_datastore):
        """An already-correct, matching dynamic template does not trigger a refusal."""
        col = _make_collection(mock_datastore)
        col._index_list = ["testcol_hot"]
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": KEYWORD_MAPPING,
                        "name": KEYWORD_MAPPING,
                    },
                    "dynamic_templates": expected_templates,
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword": {"type": "keyword", "searchable": True}},
                "name": {"keyword": {"type": "keyword", "searchable": True}},
            }
        }
        mock_datastore.client.indices.exists_template.return_value = False

        col._check_fields()  # must not raise

    def test_extra_dynamic_template_is_retained_with_warning(self, mock_datastore, caplog):
        """Templates left by a disabled plugin do not prevent startup."""
        col = _make_collection(mock_datastore)
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        extra_template = {
            "disabled_plugin.*_tpl": {
                "path_match": "disabled_plugin.*",
                "mapping": {"type": "keyword", "index": True},
            }
        }
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "dynamic_templates": [*expected_templates, extra_template],
                }
            }
        }

        with caplog.at_level("WARNING", logger="howler.api.datastore"):
            col._check_dynamic_templates()

        assert "retains dynamic templates not used by the active schema" in caplog.text

    def test_refuses_template_missing_from_one_backing_index(self, mock_datastore):
        """Every expected template must be present on every rollover index."""
        col = _make_collection(mock_datastore)
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {"mappings": {"dynamic_templates": expected_templates}},
            "testcol-000002": {
                "mappings": {
                    "dynamic_templates": [
                        template for template in expected_templates if next(iter(template)) != "tags.*_tpl"
                    ]
                }
            },
        }

        with pytest.raises(HowlerValueError, match="tags\\.\\*_tpl"):
            col._check_dynamic_templates()

    def test_refuses_reordered_active_dynamic_templates(self, mock_datastore):
        """Expected template precedence must match on every backing index."""
        col = _make_collection(mock_datastore)
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {"mappings": {"dynamic_templates": list(reversed(expected_templates))}}
        }

        with pytest.raises(HowlerValueError, match="order differs"):
            col._check_dynamic_templates()

    def test_field_cap_limit_error_expands_limit_and_retries(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get.return_value = {}
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {"name": KEYWORD_MAPPING},
                    "dynamic_templates": expected_templates,
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {"name": {"keyword": {"type": "keyword", "searchable": True}}}
        }
        mock_datastore.client.indices.exists_template.return_value = False

        error_body = {"error": {"reason": "Limit of total fields [10] has been exceeded"}}
        api_error = elasticsearch.BadRequestError("boom", MagicMock(), error_body)
        mock_datastore.client.indices.put_mapping.side_effect = [api_error, None]

        col._check_fields()

        mock_datastore.client.indices.put_settings.assert_called_once_with(
            index=[col.index_name], settings={"index.mapping.total_fields.limit": 510}
        )
        assert mock_datastore.client.indices.put_mapping.call_count == 2

    @pytest.mark.parametrize(
        ("live_mapping", "capability", "message"),
        [
            (
                {"type": "text", "index": True},
                {"type": "text", "searchable": True},
                "expected store type",
            ),
            (
                {"type": "keyword", "index": False},
                {"type": "keyword", "searchable": False},
                "incompatible indexing",
            ),
            (
                {"type": "keyword", "ignore_above": 128},
                {"type": "keyword", "searchable": True},
                "incompatible ignore_above",
            ),
        ],
    )
    def test_refuses_incompatible_existing_field(
        self,
        mock_datastore,
        live_mapping,
        capability,
        message,
    ):
        col = _make_collection(mock_datastore)
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": live_mapping,
                        "name": {"type": "keyword", "ignore_above": 8191},
                    },
                    "dynamic_templates": expected_templates,
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword" if capability["type"] == "keyword" else "text": capability},
                "name": {"keyword": {"type": "keyword", "searchable": True}},
            }
        }
        mock_datastore.client.indices.exists_template.return_value = False

        with pytest.raises(HowlerRuntimeError, match=message):
            col._check_fields()

    def test_refuses_conflicting_active_dynamic_templates_across_indices(self, mock_datastore):
        col = _make_collection(mock_datastore)
        expected_templates = new_schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {
                "mappings": {
                    "dynamic_templates": expected_templates,
                }
            },
            "testcol-000002": {
                "mappings": {
                    "dynamic_templates": [
                        template
                        if next(iter(template)) != "tags.*_tpl"
                        else {"tags.*_tpl": {"path_match": "tags.*", "mapping": {"type": "text", "index": True}}}
                        for template in expected_templates
                    ]
                }
            },
        }

        with pytest.raises(HowlerValueError, match="tags\\.\\*_tpl"):
            col._check_dynamic_templates()
