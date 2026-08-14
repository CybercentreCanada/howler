from howler import odm


class Ownership(odm.Model):
    owner: str = odm.Keyword(
        description="The person owning the object.",
        optional=True,
    )
    admins: list[str] = odm.List(
        odm.Keyword(),
        description="The group administrator for this object.",
        default=[],
        optional=True,
    )
    members: list[str] = odm.List(
        odm.Keyword(),
        description=("The group who can modify the object."),
        default=[],
        optional=True,
    )
