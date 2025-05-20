from howler import odm


@odm.model(
    index=True,
    store=True,
)
class SharepointUser(odm.Model):
    email: str = odm.Optional(odm.Email(description="The email of the sharepoint user associated with this item."))
    full_name: str = odm.Optional(
        odm.Keyword(description="The full name of the sharepoint user associated with this item.")
    )
    id: str = odm.Optional(odm.Keyword(description="The id of the sharepoint user associated with this item."))


@odm.model(
    index=True,
    store=True,
)
class SharepointData(odm.Model):
    application: str = odm.Optional(odm.Keyword(description="The associated application."))
    user: str = odm.Optional(odm.Keyword(description="The associated application."))


@odm.model(
    index=True,
    store=True,
)
class Sharepoint(odm.Model):
    created: SharepointData = odm.Optional(
        odm.Compound(SharepointData, description="Information about how the item was created.")
    )
    modified: SharepointData = odm.Optional(
        odm.Compound(SharepointData, description="Information about how the item was modified.")
    )


@odm.model(
    index=True,
    store=True,
    description="The cbs fields contain any data obtained from CBS relating to the alert.",
)
class CBS(odm.Model):
    sharepoint: Sharepoint = odm.Optional(odm.Compound(Sharepoint, description="Sharepoint metadata"))
