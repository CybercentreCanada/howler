# mypy: ignore-errors
from typing import Optional

from howler import odm

VALID_TRIGGERS = ["create", "demote", "promote", "add_label", "remove_label"]


@odm.model(index=True, store=True, description="Model of action operations")
class Operation(odm.Model):
    operation_id: str = odm.Keyword(description="The ID of the action.")
    data_json: Optional[str] = odm.Keyword(
        optional=True,
        description="The data necessary to execute the action, in raw JSON format.",
    )


@odm.model(index=True, store=True, description="Model of actions")
class Action(odm.Model):
    action_id: str = odm.UUID(description="A UUID for this action")
    owner_id: str = odm.Keyword(
        description="The person to whom this action belongs.",
        optional=True,
    )
    members: list[str] = odm.List(
        odm.Keyword(),
        description="group of person to whom can modify this action.",
        default=[],
        optional=True,
    )
    admins: list[str] = odm.List(
        odm.Keyword(),
        description="group of person to whom can administer this action.",
        default=[],
        optional=True,
    )
    name: str = odm.Keyword(description="The name of the action.")
    query: str = odm.Keyword(description="The query this action is run against.")
    triggers: list[str] = odm.List(
        odm.Enum(VALID_TRIGGERS),
        default=[],
        description="A list of events for which trigger this action",
    )
    operations: list[Operation] = odm.List(
        odm.Compound(Operation),
        default=[],
        description="A list of the operations this action consists of.",
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
            "owner": self.owner_id,
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
            self.owner_id = user if isinstance(user, str) else user[0]
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
            if isinstance(users, list) and len(users) > 1:
                raise ValueError("Owner level can only have one user. a list was given with multiple users.")
            raise ValueError("Owner can only be transferred. They should be assigned to another user.")
        elif level == "administrator":
            if isinstance(users, list):
                self.admins = [admin for admin in self.admins if admin not in users]
            else:
                self.admins = [admin for admin in self.admins if admin != users]
        elif level == "member":
            if isinstance(users, list):
                self.members = [member for member in self.members if member not in users]
            else:
                self.members = [member for member in self.members if member != users]
