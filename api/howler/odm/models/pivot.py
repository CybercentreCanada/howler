# mypy: ignore-errors
from typing import Any, Optional

from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.odm.models.localized_label import LocalizedLabel


@odm.model(
    index=True,
    store=True,
    description="The .",
)
class Mapping(odm.Model):
    key: str = odm.Keyword(
        description="The key to inject the given field as. Exact behaviour depends on the implementation type."
    )
    field: str = odm.Keyword(description="The field in the hit to associate with the given key.")
    custom_value: Optional[str] = odm.Keyword(
        description="An optional custom value to use if the value is not dependent on the alert we are pivoting on",
        optional=True,
    )


def validate_group(group: str | Any) -> None:
    """Validate a slash-separated pivot group path."""
    if group is None:
        return

    if group == "":
        raise HowlerValueError("Group cannot be an empty string")

    if not isinstance(group, str):
        raise HowlerValueError('Data "group" should be a slash-separated string.')

    if any(not section for section in group.split("/")):
        raise HowlerValueError("A group must consist of a relative path with no empty segments (e.g. a/b/c)")


@odm.model(
    index=False,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class Pivot(odm.Model):
    icon: str = odm.Text(
        description="An optional icon to use in the tab display for this dossier.", default="material-symbols:link"
    )
    group: str | None = odm.Keyword(
        description="The folder path this pivot should be presented in when viewed in the UI.",
        optional=True,
        index=True,
        coerce=False,
    )
    label: LocalizedLabel = odm.Compound(LocalizedLabel, description="Labels for the pivot in the UI.")
    value: str = odm.Keyword(description="The link/plugin information to pivot on.")
    format: str = odm.Keyword(description="The format of the pivot.")
    mappings: list[Mapping] = odm.List(
        odm.Compound(Mapping),
        default=[],
        description="A list of the mappings to use when activating a pivot.",
    )

    def __init__(self, data: dict = None, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

        validate_group(self.group)

        if len(self.mappings) != len({mapping.key for mapping in self.mappings}):
            raise HowlerValueError("One of your pivots has duplicate keys set.")
