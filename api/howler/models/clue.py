"""Clue plugin extension models."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, list_field, model_extensions, optional, register_model
from howler.models.hit import Hit


@register_model(
    index=True, store=True, description="A mapping from a specific field in Howler to a clue type", embedded=True
)
class TypeMap(HowlerEmbeddedModel):
    """A mapping from a specific field in Howler to a clue type."""

    field: keyword(description="The field whose clue type to override")
    type: keyword(description="The clue type to override the field as")


@register_model(index=True, store=True, description="Clue-specific overrides for this alert", embedded=True)
class Clue(HowlerEmbeddedModel):
    """Clue-specific overrides for this alert."""

    types: list_field(
        compound(TypeMap),
        default=[],
        description="A mapping of howler fields to clue types to augment/override system configuration.",
    )


PLUGIN_NAME = "clue"


def declare_hit_extension() -> None:
    """Declare the ``clue`` field extension for the ``Hit`` model.

    This is the Pydantic/DSL replacement for the legacy ``Hit.add_namespace("clue", ...)`` call
    in ``howler.datastore.howler_store``, which is only made when ``config.core.clue.enabled``.
    Declaring (or not declaring) this extension before ``Hit`` is finalized is what makes Clue
    support toggle-able; actually finalizing ``Hit`` with this extension applied, and using the
    finalized model at runtime, is Step 8 (datastore/consumer cutover) work.
    """
    if "clue" not in model_extensions.pending(Hit) and not model_extensions.is_finalized(Hit):
        model_extensions.declare(
            Hit,
            "clue",
            optional(compound(Clue), description="Clue-specific overrides for this alert"),
            plugin=PLUGIN_NAME,
        )
