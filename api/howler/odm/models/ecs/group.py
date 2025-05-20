from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The group fields are meant to represent groups that are relevant to the event.",
)
class Group(odm.Model):
    domain = odm.Optional(odm.Keyword(description="Name of the directory the group is a member of."))
    id = odm.Optional(odm.Keyword(description="Unique identifier for the group on the system/platform."))
    name = odm.Optional(odm.Keyword(description="Name of the group."))


@odm.model(index=True, store=True, description="Shorter representation of a group.")
class ShortGroup(odm.Model):
    id = odm.Optional(odm.Keyword(description="Unique identifier for the group on the system/platform."))
    name = odm.Optional(odm.Keyword(description="Name of the group."))
