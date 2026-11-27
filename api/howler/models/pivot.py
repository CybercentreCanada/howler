"""Pivot model."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import field_validator, model_validator

from howler.common.exceptions import HowlerValueError
from howler.models import HowlerEmbeddedModel, Keyword, StrictKeyword, Text, metadata, register_model
from howler.models.localized_label import LocalizedLabel


@register_model(index=True, store=True, description="The .", embedded=True)
class Mapping(HowlerEmbeddedModel):
    """A single pivot mapping entry."""

    key: Keyword
    """The key to inject the given field as. Exact behaviour depends on the implementation type."""
    field: Keyword
    """The field in the hit to associate with the given key."""
    custom_value: Keyword | None = None
    """An optional custom value to use if the value is not dependent on the alert we are pivoting on"""


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

    icon: Text = "material-symbols:link"
    """An optional icon to use in the tab display for this dossier."""
    group: Annotated[StrictKeyword | None, metadata(index=True)] = None
    """The folder path this pivot should be presented in when viewed in the UI."""
    description: Text | None = None
    """An optional description for the pivot."""
    label: LocalizedLabel
    """Labels for the pivot in the UI."""
    value: Keyword
    """The link/plugin information to pivot on."""
    format: Keyword
    """The format of the pivot."""
    mappings: list[Mapping] = []
    """A list of the mappings to use when activating a pivot."""

    @field_validator("group", mode="before")
    @classmethod
    def _validate_group(cls, value: Any) -> Any:
        validate_group(value)
        return value

    @model_validator(mode="after")
    def _validate_unique_mapping_keys(self) -> Pivot:
        if len(self.mappings) != len({mapping.key for mapping in self.mappings}):
            raise ValueError("One of your pivots has duplicate keys set.")
        return self
