from howler import odm
from howler.odm.models.ecs.group import Group


@odm.model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
)
class UserNested(odm.Model):
    domain = odm.Optional(odm.Keyword(description="Name of the directory the user is a member of."))
    email = odm.Optional(odm.Email(description="User email address."))
    full_name = odm.Optional(odm.Keyword(description="User’s full name, if available."))
    hash = odm.Optional(
        odm.Keyword(description="Unique user hash to correlate information for a user in anonymized form.")
    )
    id = odm.Optional(odm.Keyword(description="Unique identifier of the user."))
    name = odm.Optional(odm.Keyword(description="Short name or login of the user."))
    roles = odm.Optional(
        odm.List(
            odm.Keyword(),
            default=[],
            description="Array of user roles at the time of the event.",
        )
    )


@odm.model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
)
class User(odm.Model):
    domain = odm.Optional(odm.Keyword(description="Name of the directory the user is a member of."))
    email = odm.Optional(odm.Email(description="User email address."))
    full_name = odm.Optional(odm.Keyword(description="User's full name, if available."))
    group = odm.Optional(odm.Compound(Group, description="User's group relevant to the event."))
    hash = odm.Optional(
        odm.Keyword(description="Unique user hash to correlate information for a user in anonymized form.")
    )
    id = odm.Optional(odm.Keyword(description="Unique identifier of the user."))
    name = odm.Optional(odm.Keyword(description="Short name or login of the user."))
    roles = odm.Optional(
        odm.List(
            odm.Keyword(),
            default=[],
            description="Array of user roles at the time of the event.",
        )
    )


@odm.model(index=True, store=True, description="Shorter representation of a user.")
class ShortUser(odm.Model):
    id = odm.Optional(odm.Keyword(description="Unique identifier of the user."))
    name = odm.Optional(odm.Keyword(description="Short name or login of the user."))
    domain = odm.Optional(odm.Keyword(description="Name of the directory the user is a member of."))
    email = odm.Optional(odm.Email(description="User email address."))
