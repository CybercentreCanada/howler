from howler import odm


class Ownership(odm.Model):
    owner: str = odm.Keyword(
        description="The person owning the object.",
    )
    admins: list[str] = odm.List(
        odm.Keyword(),
        description="The group administrator for this object.",
        default=[],
    )
    members: list[str] = odm.List(
        odm.Keyword(),
        description="The group who can modify the object.",
        default=[],
    )
