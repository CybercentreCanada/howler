# mypy: ignore-errors
from typing import Literal, Union

from howler import odm


@odm.model(index=True, store=True, description="Additional View Settings")
class Settings(odm.Model):
    advance_on_triage: bool = odm.Boolean(
        description="Should the user advance to the next alert when triage is complete?", default=False
    )


@odm.model(index=True, store=True, description="Model of views")
class View(odm.Model):
    view_id: str = odm.UUID(description="A UUID for this view")
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
    # Kept as owner id for backwards compatibility, but should be owner to match other models
    owner: str = odm.Keyword(
        description="The person to whom this view belongs.",
        optional=True,
    )

    admin: list[str] = odm.List(
        odm.Keyword(),
        description="The group of person to whom administer this view.",
        default=[],
        optional=True,
    )
    member: list[str] = odm.List(
        odm.Keyword(),
        description="The group of person to whom can modify the view.",
        default=[],
        optional=True,
    )
    settings: Settings = odm.Compound(
        Settings, description="Additional View Settings", default={"advance_on_triage": False}
    )

    # use in every object to help with the owner_id problem in this object and to match the other models,but kept owner_
    # id for backwards compatibility
    def get_privilege_mapping(self) -> dict:
        return {
            "administrator": self.admins,
            "member": self.members,
            "owner": self.owner_id,
        }
