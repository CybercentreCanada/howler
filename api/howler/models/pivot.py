"""Pivot model."""

from __future__ import annotations

from typing import Any

from howler.common.exceptions import HowlerValueError
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


def validate_group(group: Any) -> None:
    """Validate a slash-separated pivot group path."""
    if group is None:
        return

    if group == "":
        raise HowlerValueError("Group cannot be an empty string")

    if not isinstance(group, str):
        raise HowlerValueError('Data "group" should be a slash-separated string.')

    if any(not section for section in group.split("/")):
        raise HowlerValueError("A group must consist of a relative path with no empty segments (e.g. a/b/c)")


@register_model(
    index=False,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
    embedded=True,
)
class Pivot(HowlerEmbeddedModel):
    """The dossier object stores individual tabs/fields for a given alert."""

    icon: text(
        default="material-symbols:link",
        description="An optional icon to use in the tab display for this dossier.",
    )
    group: optional(
        keyword(coerce=False, index=True),
        description="The folder path this pivot should be presented in when viewed in the UI.",
    )
    description: optional(text(), description="An optional description for the pivot.")
    label: compound(LocalizedLabel, description="Labels for the pivot in the UI.")
    value: keyword(description="The link/plugin information to pivot on.")
    format: keyword(description="The format of the pivot.")
    mappings: list_field(
        compound(Mapping), default=[], description="A list of the mappings to use when activating a pivot."
    )

    def __init__(self, **data: Any) -> None:
        """Validate group syntax and unique mapping keys on construction."""
        validate_group(data.get("group"))
        super().__init__(**data)
        if len(self.mappings) != len({mapping.key for mapping in self.mappings}):
            raise HowlerValueError("One of your pivots has duplicate keys set.")
