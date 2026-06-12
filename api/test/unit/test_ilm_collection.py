"""Unit tests for ILM methods on ESCollection.

These tests mock the Elasticsearch client to verify the correct ILM policy,
index template, and _ensure_collection_ilm logic without requiring a running ES.
"""

from unittest.mock import MagicMock, patch

import pytest

from howler.datastore.collection import ESCollection
from howler.odm.models.config import ILMConfig, ILMIndexConfig


@pytest.fixture(autouse=True)
def skip_ensure_collection():
    """Prevent ESCollection from calling _ensure_collection on init."""
    ESCollection.IGNORE_ENSURE_COLLECTION = True
    yield
    ESCollection.IGNORE_ENSURE_COLLECTION = False


@pytest.fixture()
def mock_datastore():
    """Create a mock ESStore with a mock ES client."""
    ds = MagicMock()
    ds.client = MagicMock()
    ds.client.ilm = MagicMock()
    ds.client.indices = MagicMock()
    ds.DEFAULT_SORT = "id asc"
    return ds


@pytest.fixture()
def ilm_global():
    """Default global ILM config for tests."""
    return ILMConfig(
        enabled=True,
        rollover_max_age="30d",
        rollover_max_size="50gb",
        indices={"testcol": ILMIndexConfig(warm="30d", cold="90d")},
    )


def _make_collection(mock_datastore, ilm_config=None):
    """Helper to create an ESCollection with the given ILM config."""
    mock_datastore._models = {"testcol": None}
    col = ESCollection(mock_datastore, "testcol", model_class=None, ilm_config=ilm_config)
    return col


class TestCreateILMPolicy:
    """Tests for _create_ilm_policy."""

    def test_hot_only(self, mock_datastore):
        """No warm or cold phases configured — only hot with rollover."""
        ilm_index = ILMIndexConfig()  # no warm/cold
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        ilm_global = ILMConfig(enabled=True, rollover_max_age="7d", rollover_max_size="25gb")

        col._create_ilm_policy(ilm_global)

        mock_datastore.client.ilm.put_lifecycle.assert_called_once()
        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "hot" in policy["phases"]
        assert policy["phases"]["hot"]["actions"]["rollover"]["max_age"] == "7d"
        assert policy["phases"]["hot"]["actions"]["rollover"]["max_primary_shard_size"] == "25gb"
        assert "warm" not in policy["phases"]
        assert "cold" not in policy["phases"]
        assert "delete" not in policy["phases"]

    def test_warm_and_cold(self, mock_datastore, ilm_global):
        """Both warm and cold phases configured with default forcemerge segments."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "hot" in policy["phases"]
        assert "warm" in policy["phases"]
        assert policy["phases"]["warm"]["min_age"] == "30d"
        assert policy["phases"]["warm"]["actions"]["forcemerge"]["max_num_segments"] == 3  # default
        assert "cold" in policy["phases"]
        assert policy["phases"]["cold"]["min_age"] == "90d"
        assert policy["phases"]["cold"]["actions"] == {}  # no forcemerge allowed in cold
        assert "delete" not in policy["phases"]

    def test_custom_forcemerge_segments(self, mock_datastore, ilm_global):
        """Custom forcemerge segment count in warm phase."""
        ilm_index = ILMIndexConfig(warm="30d", warm_forcemerge_segments=5, cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert policy["phases"]["warm"]["actions"]["forcemerge"]["max_num_segments"] == 5
        assert policy["phases"]["cold"]["actions"] == {}  # no forcemerge in cold

    def test_skip_forcemerge_with_none(self, mock_datastore, ilm_global):
        """Setting forcemerge segments to None skips forcemerge action in warm."""
        ilm_index = ILMIndexConfig(warm="30d", warm_forcemerge_segments=None, cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "warm" in policy["phases"]
        assert "forcemerge" not in policy["phases"]["warm"]["actions"]
        assert "cold" in policy["phases"]
        assert policy["phases"]["cold"]["actions"] == {}

    def test_warm_only_no_cold(self, mock_datastore, ilm_global):
        """Warm phase configured but no cold phase."""
        ilm_index = ILMIndexConfig(warm="14d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "warm" in policy["phases"]
        assert "cold" not in policy["phases"]

    def test_cold_only_no_warm(self, mock_datastore, ilm_global):
        """Cold phase configured but no warm phase."""
        ilm_index = ILMIndexConfig(cold="60d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "warm" not in policy["phases"]
        assert "cold" in policy["phases"]
        assert policy["phases"]["cold"]["min_age"] == "60d"

    def test_policy_name(self, mock_datastore, ilm_global):
        """Policy name follows the {APP_NAME}-{collection}_policy convention."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        assert call_kwargs.kwargs["name"] == f"{col.name}_policy"

    def test_no_readonly_in_warm(self, mock_datastore, ilm_global):
        """Warm phase must NOT have readonly — retention cronjob needs write access."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "readonly" not in policy["phases"]["warm"]["actions"]
        assert "readonly" not in policy["phases"]["cold"].get("actions", {})

    def test_no_delete_phase(self, mock_datastore, ilm_global):
        """Delete phase must never be present — retention cronjob handles deletion."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "delete" not in policy["phases"]


class TestCreateIndexTemplate:
    """Tests for _create_index_template."""

    def test_template_name_and_pattern(self, mock_datastore, ilm_global):
        """Template name and index pattern follow naming convention."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_index_template(ilm_global)

        call_kwargs = mock_datastore.client.indices.put_index_template.call_args
        assert call_kwargs.kwargs["name"] == f"{col.name}_template"
        assert call_kwargs.kwargs["index_patterns"] == [f"{col.name}-*"]

    def test_template_includes_ilm_settings(self, mock_datastore, ilm_global):
        """Template includes lifecycle.name and lifecycle.rollover_alias."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_index_template(ilm_global)

        call_kwargs = mock_datastore.client.indices.put_index_template.call_args
        template = call_kwargs.kwargs["template"]

        assert template["settings"]["index"]["lifecycle.name"] == f"{col.name}_policy"
        assert template["settings"]["index"]["lifecycle.rollover_alias"] == col.name

    def test_template_includes_mappings(self, mock_datastore, ilm_global):
        """Template includes the mappings (id field at minimum)."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_index_template(ilm_global)

        call_kwargs = mock_datastore.client.indices.put_index_template.call_args
        template = call_kwargs.kwargs["template"]

        assert "mappings" in template
        assert "id" in template["mappings"]["properties"]


class TestEnsureCollectionILM:
    """Tests for _ensure_collection_ilm bootstrap logic."""

    def test_fresh_install_creates_initial_index(self, mock_datastore, ilm_global):
        """On a fresh install, creates {name}-000001 with alias and ILM settings."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        # No ILM indices exist, no legacy _hot index
        mock_datastore.client.indices.get.return_value = {}
        mock_datastore.client.indices.exists.return_value = False
        mock_datastore.client.indices.exists_alias.return_value = False

        with (
            patch.object(col, "_create_ilm_policy") as mock_policy,
            patch.object(col, "_create_index_template") as mock_template,
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            mock_policy.assert_called_once()
            mock_template.assert_called_once()

            # Should create the initial index
            mock_datastore.client.indices.create.assert_called_once()
            create_kwargs = mock_datastore.client.indices.create.call_args.kwargs
            assert create_kwargs["index"] == f"{col.name}-000001"
            assert col.name in create_kwargs["aliases"]
            assert create_kwargs["aliases"][col.name]["is_write_index"] is True
            assert "lifecycle.name" in create_kwargs["settings"]["index"]

        # index_name should be updated
        assert col.index_name == f"{col.name}-000001"

    def test_existing_ilm_indices_skips_creation(self, mock_datastore, ilm_global):
        """When ILM indices already exist, no new index is created."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        mock_datastore.client.indices.get.return_value = {
            f"{col.name}-000001": {},
            f"{col.name}-000002": {},
        }
        mock_datastore.client.indices.exists_alias.return_value = True

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            # Should not create or clone any index
            mock_datastore.client.indices.create.assert_not_called()
            mock_datastore.client.indices.clone.assert_not_called()

        # index_name should be updated to the latest ILM index
        assert col.index_name == f"{col.name}-000002"

    def test_existing_ilm_indices_without_alias_creates_alias(self, mock_datastore, ilm_global):
        """When ILM indices exist but alias is missing, creates the alias."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        mock_datastore.client.indices.get.return_value = {
            f"{col.name}-000001": {},
            f"{col.name}-000002": {},
        }
        mock_datastore.client.indices.exists_alias.return_value = False

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            # Should put alias on the latest index
            mock_datastore.client.indices.put_alias.assert_called_once()
            put_alias_kwargs = mock_datastore.client.indices.put_alias.call_args.kwargs
            assert put_alias_kwargs["index"] == f"{col.name}-000002"
            assert put_alias_kwargs["name"] == col.name
            assert put_alias_kwargs["is_write_index"] is True

        # index_name should be updated to the latest ILM index
        assert col.index_name == f"{col.name}-000002"

    def test_legacy_hot_index_migration(self, mock_datastore, ilm_global):
        """Legacy _hot index gets cloned to -000001 and alias is swapped."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        hot_index_name = col.index_name  # e.g. howler-testcol_hot

        # No ILM indices, but legacy _hot exists
        mock_datastore.client.indices.get.return_value = {}
        mock_datastore.client.indices.exists.return_value = True  # _hot exists
        mock_datastore.client.indices.exists_alias.return_value = True  # alias on _hot

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_safe_index_copy") as mock_copy,
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            # Should block writes on _hot
            mock_datastore.client.indices.put_settings.assert_any_call(
                index=hot_index_name,
                settings={"index.blocks.write": True},
            )

            # Should clone _hot to -000001
            mock_copy.assert_called_once()
            clone_args = mock_copy.call_args
            assert clone_args.args[1] == hot_index_name
            assert clone_args.args[2] == f"{col.name}-000001"

            # Should update aliases
            mock_datastore.client.indices.update_aliases.assert_called_once()
            alias_actions = mock_datastore.client.indices.update_aliases.call_args.kwargs["actions"]
            # Should have an add action for the new index
            add_action = [a for a in alias_actions if "add" in a][0]
            assert add_action["add"]["index"] == f"{col.name}-000001"
            assert add_action["add"]["is_write_index"] is True

        assert col.index_name == f"{col.name}-000001"


class TestEnsureCollectionILMDispatch:
    """Tests that _ensure_collection dispatches to ILM path when ilm_config is set."""

    def test_dispatches_to_ilm_when_configured(self, mock_datastore):
        """When ilm_config is set, _ensure_collection calls _ensure_collection_ilm."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        with patch.object(col, "_ensure_collection_ilm") as mock_ilm, patch.object(col, "_check_fields"):
            col._ensure_collection()
            mock_ilm.assert_called_once()

    def test_does_not_dispatch_without_ilm(self, mock_datastore):
        """When ilm_config is None, _ensure_collection uses legacy path."""
        col = _make_collection(mock_datastore, ilm_config=None)

        # Mock away the ES calls for the legacy path
        mock_datastore.client.indices.exists.return_value = True
        mock_datastore.client.indices.exists_alias.return_value = True

        with patch.object(col, "_ensure_collection_ilm") as mock_ilm, patch.object(col, "_check_fields"):
            col._ensure_collection()
            mock_ilm.assert_not_called()


class TestAddFieldsILMTemplateSync:
    """Tests that _add_fields updates the index template when ILM is active."""

    def test_add_fields_updates_template_when_ilm(self, mock_datastore, ilm_global):
        """When ILM is configured, _add_fields re-creates the index template."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        col._index_list = []

        # Mock the fields that need to be added
        mock_field = MagicMock()
        mock_field.name = None

        # Make build_mapping return valid properties
        with (
            patch("howler.datastore.collection.build_mapping", return_value=({"new_field": {"type": "keyword"}}, [])),
            patch.object(col, "_create_index_template") as mock_template,
            patch.object(
                ESCollection, "index_list_full", new_callable=lambda: property(lambda self: [self.index_name])
            ),
        ):
            col._add_fields({"test_field": mock_field})

            # Should have updated the template
            mock_template.assert_called_once()

    def test_add_fields_does_not_update_template_without_ilm(self, mock_datastore):
        """Without ILM, _add_fields does not touch any index template."""
        col = _make_collection(mock_datastore, ilm_config=None)
        col._index_list = []

        mock_field = MagicMock()
        mock_field.name = None

        with (
            patch("howler.datastore.collection.build_mapping", return_value=({"new_field": {"type": "keyword"}}, [])),
            patch.object(
                ESCollection, "index_list_full", new_callable=lambda: property(lambda self: [self.index_name])
            ),
        ):
            # Ensure no legacy template exists
            mock_datastore.client.indices.exists_template.return_value = False

            col._add_fields({"test_field": mock_field})

            mock_datastore.client.indices.put_index_template.assert_not_called()
