"""Clue plugin extension models."""

from __future__ import annotations

from typing import Annotated

from howler.models import HowlerEmbeddedModel, Keyword, metadata, model_extensions, register_model
from howler.models.hit import Hit


@register_model(
    index=True, store=True, description="A mapping from a specific field in Howler to a clue type", embedded=True
)
class TypeMap(HowlerEmbeddedModel):
    """A mapping from a specific field in Howler to a clue type."""

    field: Keyword
    """The field whose clue type to override"""
    type: Keyword
    """The clue type to override the field as"""


@register_model(index=True, store=True, description="Clue-specific overrides for this alert", embedded=True)
class Clue(HowlerEmbeddedModel):
    """Clue-specific overrides for this alert."""

    types: list[TypeMap] = []
    """A mapping of howler fields to clue types to augment/override system configuration."""


PLUGIN_NAME = "clue"


def declare_hit_extension() -> None:
    """Declare the ``clue`` field extension for the ``Hit`` model.

    ``howler.datastore.howler_store`` calls this only when ``config.core.clue.enabled``. Declaring
    (or not declaring) this extension before ``Hit`` is finalized is what makes Clue support
    toggle-able.
    """
    model_extensions.declare(
        Hit,
        "clue",
        Annotated[Clue | None, metadata(default=None, description="Clue-specific overrides for this alert")],
        plugin=PLUGIN_NAME,
    )
