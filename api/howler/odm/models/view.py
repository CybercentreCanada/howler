# mypy: ignore-errors
from typing import Literal, Optional, Union

from howler import odm


@odm.model(index=True, store=True, description="The field and width of a column to display in a grid view.")
class GridColumn(odm.Model):
    field: str = odm.Keyword(description="The field key for this column.")
    width: Optional[int] = odm.Optional(odm.Integer(description="The width of this column in pixels."))


@odm.model(index=True, store=True, description="Additional View Settings")
class Settings(odm.Model):
    advance_on_triage: bool = odm.Boolean(
        description="Should the user advance to the next alert when triage is complete?", default=False
    )
    display: Optional[Union[Literal["list"], Literal["grid"]]] = odm.Optional(
        odm.Enum(
            values=["list", "grid"],
            description="The layout to use when opening this view",
        )
    )
    columns: Optional[list[GridColumn]] = odm.Optional(
        odm.List(odm.Compound(GridColumn, description="The columns to display in this view."))
    )


DEFAULT_INDEXES = ["hit"]


@odm.model(index=True, store=True, description="Model of views")
class View(odm.Model):
    view_id: str = odm.UUID(description="A UUID for this view")
    indexes: list[str] = odm.List(
        odm.Keyword(),
        default=DEFAULT_INDEXES,
        description="What indexes this view applies to.",
    )
    title: str = odm.CaseInsensitiveKeyword(description="The name of this view.")
    query: str = odm.Keyword(description="The query to run in this view.")
    sort: str = odm.Keyword(description="The sorting to use with this view.", optional=True)
    span: str = odm.Keyword(
        description="The time span to use by default when opening this view",
        optional=True,
    )
    type: Union[Literal["personal"], Literal["global"], Literal["readonly"]] = odm.Enum(
        values=["personal", "global", "readonly"],
        description="The type of view",
    )
    owner: str = odm.Keyword(
        description="The person to whom this view belongs.",
        optional=True,
    )
    # TODO: AG - Find how to allow multiple owners.
    # From the docs, this is used to query data. We want to avoid
    # heavy modifications so that search functionality remains intact,
    # but we need to support more than one member.
    admin: str = odm.Keyword(
        description="group of person to whom can administer this view.",
        optional=True,
    )
    member: str = odm.Keyword(description="group of person to whom can modify this view.", optional=True)
    settings: Settings = odm.Compound(
        Settings, description="Additional View Settings", default={"advance_on_triage": False}
    )
