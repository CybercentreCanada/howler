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
    owner: str = odm.Keyword(
        description="The person(s) to whom this view belongs.",
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

    def get_privilege_mapping(self) -> dict:
        return {
            "administrator": self.admin,
            "member": self.member,
            "owner": self.owner,
        }

    def set_privilege_mapping(self, level: str, users: str | list[str]):
        if level == "owner":
            if isinstance(users, list) and len(users) > 1:
                raise ValueError("Owner level can only have one user. a list was given with multiple users.")
            self.owner = users if isinstance(users, str) else users[0]
        elif level == "administrator":
            self.admin = users if isinstance(users, list) else [users]
        elif level == "member":
            self.member = users if isinstance(users, list) else [users]

    def remove_privilege_mapping(self, level: str, users: str | list[str]):
        if level == "owner":
            if isinstance(users, list) and len(users) > 1:
                raise ValueError("Owner level can only have one user. a list was given with multiple users.")
            self.owner = ""
        elif level == "administrator":
            if isinstance(users, list):
                self.admin = [a for a in self.admin if a not in users]
            else:
                self.admin = [a for a in self.admin if a != users]
        elif level == "member":
            if isinstance(users, list):
                self.member = [m for m in self.member if m not in users]
            else:
                self.member = [m for m in self.member if m != users]
