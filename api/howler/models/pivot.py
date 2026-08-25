"""Pivot model."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    keyword,
    list_field,
    optional,
    register_model,
    text,
)
from howler.models.localized_label import LocalizedLabel


@register_model(index=True, store=True, description="The .", embedded=True)
class Mapping(HowlerEmbeddedModel):
    """A single pivot mapping entry."""

    key: keyword(
        description="The key to inject the given field as. Exact behaviour depends on the implementation type."
    )
    field: keyword(description="The field in the hit to associate with the given key.")
    custom_value: optional(
        keyword(),
        description="An optional custom value to use if the value is not dependent on the alert we are pivoting on",
    )


@register_model(
    index=False,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
    embedded=True,
)
class Pivot(HowlerEmbeddedModel):
    """The dossier object stores individual tabs/fields for a given alert."""

    icon: optional(text(), description="An optional icon to use in the tab display for this dossier.")
    label: compound(LocalizedLabel, description="Labels for the pivot in the UI.")
    value: keyword(description="The link/plugin information to pivot on.")
    format: keyword(description="The format of the pivot.")
    mappings: list_field(
        compound(Mapping), default=[], description="A list of the mappings to use when activating a pivot."
    )
