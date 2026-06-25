from typing import Literal, Optional

from howler import odm
from howler.odm.models.lead import Lead
from howler.odm.models.pivot import Pivot


@odm.model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class Dossier(odm.Model):
    dossier_id: str = odm.UUID(description="A UUID for this dossier.")
    leads: list[Lead] = odm.List(
        odm.Compound(Lead),
        default=[],
        description="A list of the leads to show when the query matches the given alert.",
    )
    pivots: list[Pivot] = odm.List(
        odm.Compound(Pivot),
        default=[],
        description="A list of the pivots to show when the query matches the given alert.",
    )
    title: str = odm.Keyword(description="The title of this dossier.")

    # TODO : AG find better language for them
    owner: str = odm.Keyword(
        description="The person to whom this dossier belongs.",
        optional=True,
    )
    admins: list[str] = odm.List(
        odm.Keyword(),
        description="The group of person to whom this dossier is administer.",
        default=[],
        optional=True,
    )
    members: list[str] = odm.List(
        odm.Keyword(),
        description=("The group of person to whom this dossier is assigned."),
        default=[],
        optional=True,
    )

    query: Optional[str] = odm.Keyword(
        description="The query that controls when this dossier should be shown in the UI.", optional=True, default=None
    )
    type: Literal["personal"] | Literal["global"] = odm.Enum(
        values=["personal", "global"],
        description="The type of dossier - personal or global.",
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
    level: requested level based on privilege mapping (owner, administrator, member)
    users: a single user or list of users to assign to the specified level

    return : none
    """
    if level == "owner":
        if isinstance(user, list):
            if len(user) > 1:
                raise ValueError("Owner level can only have one user. A list was given with multiple users.")
            self.owner = user[0] if user else ""  # Or handle empty lists if necessary
        else:
            self.owner = user

    elif level == "administrator":
        if isinstance(user, list):
            self.admins.extend(user)
        else:
            self.admins.append(user)

    elif level == "member":
        if isinstance(user, list):
            self.members.extend(user)
        else:
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
                self.admins = [admin for admin in self.admins if admin not in users]
            else:
                self.admins = [admin for admin in self.admins if admin != users]
        elif level == "member":
            if isinstance(users, list):
                self.members = [member for member in self.members if member not in users]
            else:
                self.members = [member for member in self.members if member != users]
