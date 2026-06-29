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

    admins: list[str] = odm.List(
        odm.Keyword(),
        description="The group of person to whom administer this view.",
        default=[],
        optional=True,
    )
    members: list[str] = odm.List(
        odm.Keyword(),
        description="The group of person to whom can modify the view.",
        default=[],
        optional=True,
    )
    settings: Settings = odm.Compound(
        Settings, description="Additional View Settings", default={"advance_on_triage": False}
    )

    def get_privilege_mapping(self) -> dict:
        """
        This function is use to uniformize the call for owner or other component that may have different name due to
        backward compatibility.

        It can also be use in the future for other component that may have different level of privilege

        Returns a dictionary mapping privilege levels to their respective users. of format : {
        "administrator": [list of administrators],
        "member": [list of members],
        "owner": owner_id
        }
        """
        return {
            "administrator": self.admins,
            "member": self.members,
            "owner": self.owner,
        }

    def set_privilege_mapping(self, level: str, user: str | list[str]):
        """
        Sets the users for a given privilege level.
        level: requested level based on priviledge mapping (owner, administrator, member)
        [based on the privilege mapping]
        users: a single user or list of users to assign to the specified level

        return : none
        """
        is_user_list: bool = isinstance(user, list)
        if level == "owner":
            if is_user_list and len(user) > 1:
                raise ValueError("Owner level can only have one user. a list was given with multiple users.")
            self.owner = user if isinstance(user, str) else user[0]  # This is use to transfer ownership.
        elif level == "administrator":
            if is_user_list:
                self.admins.extend(user)
                return
            self.admins.append(user)
        elif level == "member":
            if is_user_list:
                self.members.extend(user)
                return
            self.members.append(user)

    def remove_privilege_mapping(self, level: str, users: str | list[str]):
        """
        Removes the specified users from a given privilege level.
        level: requested level based on priviledge mapping (owner, administrator, member)
        [based on the privilege mapping]
        users: a single user or list of users to remove from the specified level
        return : none
        """
        if level == "owner":
            raise ValueError("You can not remove an owner, only transfer ownership.")
        elif level == "administrator":
            if isinstance(users, list):
                self.admins = [a for a in self.admins if a not in users]
            else:
                self.admins = [a for a in self.admins if a != users]
        elif level == "member":
            if isinstance(users, list):
                self.members = [m for m in self.members if m not in users]
            else:
                self.members = [m for m in self.members if m != users]
