from howler import odm


class OwnershipObject(odm.Model):
    owner: str = odm.Keyword(
        description="The person to whom this object belongs.",
        optional=True,
    )
    admins: list[str] = odm.List(
        odm.Keyword(),
        description="The group of people to whom this object is administered.",
        default=[],
        optional=True,
    )
    members: list[str] = odm.List(
        odm.Keyword(),
        description=("The group of people to whom this object is assigned."),
        default=[],
        optional=True,
    )
