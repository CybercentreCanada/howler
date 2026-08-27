"""Tests for the plugin manifest configuration parsing in ``howler.plugins.config``.

Covers the pre-existing ``modules.odm.modify_odm``/``modules.odm.generation`` shorthand
expansion (previously untested directly) alongside the new ``modules.models.declare_extensions``
shorthand added for the Step-6 typed model-extension declaration hook, which mirrors the same
``True`` -> ``"{plugin}.{...}:{...}"`` convention.

Uses an obviously nonexistent plugin package name (``_howler_test_nonexistent_plugin_``) so the
resulting ``ImportString`` resolution deterministically fails regardless of which real plugin
packages happen to be importable in a given environment (e.g. a system-wide plugin fixture
directory added to ``sys.path`` by ``test/conftest.py``); only the *dotted path text* produced by
the shorthand expansion is under test here, not real plugin import behavior.
"""

from __future__ import annotations

import pytest
from pydantic import ImportString

from howler.plugins.config import BasePluginConfig, ModelModules, ODMModules

FAKE_PLUGIN = "_howler_test_nonexistent_plugin_"


@pytest.mark.parametrize(
    "manifest,expected_path",
    [
        (
            {"name": FAKE_PLUGIN, "modules": {"odm": {"modify_odm": {"hit": True}}}},
            f"{FAKE_PLUGIN}.odm.hit:modify_odm",
        ),
        (
            {"name": FAKE_PLUGIN, "modules": {"odm": {"generation": {"hit": True}}}},
            f"{FAKE_PLUGIN}.odm.hit:generate",
        ),
        (
            {"name": FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {"hit": True}}}},
            f"{FAKE_PLUGIN}.models.hit:declare_hit_extension",
        ),
        (
            {"name": FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {"clue": True}}}},
            f"{FAKE_PLUGIN}.models.clue:declare_clue_extension",
        ),
    ],
)
def test_true_shorthand_expands_to_conventional_import_path(manifest: dict, expected_path: str) -> None:
    """``True`` expands to the plugin's conventional module path for each declaration kind."""
    with pytest.raises(Exception) as excinfo:  # noqa: PT011 - ImportError wrapped by pydantic
        BasePluginConfig.model_validate(manifest)
    assert excinfo.value.errors()[0]["input"] == expected_path


def test_explicit_import_path_is_preserved_verbatim() -> None:
    """A manifest may bypass the shorthand and give an explicit dotted import path."""
    manifest = {
        "name": FAKE_PLUGIN,
        "modules": {"models": {"declare_extensions": {"hit": f"{FAKE_PLUGIN}.custom.path:custom_declare"}}},
    }
    with pytest.raises(Exception) as excinfo:  # noqa: PT011
        BasePluginConfig.model_validate(manifest)
    assert excinfo.value.errors()[0]["input"] == f"{FAKE_PLUGIN}.custom.path:custom_declare"


def test_false_disables_declaration_entirely() -> None:
    """``False`` drops the entry rather than expanding it to an import path."""
    manifest = {"name": FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {"hit": False}}}}
    config = BasePluginConfig.model_validate(manifest)
    assert config.modules.models.declare_extensions == {}


def test_models_and_odm_shorthands_are_independent() -> None:
    """Declaring only ``models`` (no ``odm`` block) is valid and does not require the other."""
    manifest = {"name": FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {"hit": False}}}}
    config = BasePluginConfig.model_validate(manifest)
    assert config.modules.odm.modify_odm == {}
    assert config.modules.models.declare_extensions == {}


def test_no_models_block_is_valid() -> None:
    """A manifest without any ``modules.models`` block validates fine (all-legacy plugins)."""
    manifest = {"name": FAKE_PLUGIN, "modules": {"odm": {"modify_odm": {"hit": False}}}}
    config = BasePluginConfig.model_validate(manifest)
    assert config.modules.models.declare_extensions == {}


def test_declare_extensions_field_accepts_import_string_type() -> None:
    """``declare_extensions`` values are typed as ``ImportString`` like the legacy ``modify_odm``."""
    assert ODMModules.model_fields["modify_odm"].annotation == dict[str, ImportString]
    assert ModelModules.model_fields["declare_extensions"].annotation == dict[str, ImportString]
