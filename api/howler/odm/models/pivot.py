# mypy: ignore-errors
from typing import Optional

from howler import odm
from howler.odm.howler_enum import HowlerEnum
from howler.odm.models.localized_label import LocalizedLabel


class Formats(str, HowlerEnum):
    BOREALIS = "borealis"
    LINK = "link"

    def __str__(self) -> str:
        return self.value


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


@odm.model(
    index=False,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class Pivot(odm.Model):
    icon: Optional[str] = odm.Text(
        description="An optional icon to use in the tab display for this dossier.", optional=True
    )
    label: LocalizedLabel = odm.Compound(LocalizedLabel, description="Labels for the pivot in the UI.")
    value: str = odm.Keyword(description="The link/borealis id to pivot on.")
    format: str = odm.Enum(values=Formats, description="The format of the pivot.")
    mappings: list[Mapping] = odm.List(
        odm.Compound(Mapping),
        default=[],
        description="A list of the mappings to use when activating a pivot.",
    )
