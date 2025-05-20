from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The organization fields enrich data with information "
    "about the company or entity the data is associated with.",
)
class Organization(odm.Model):
    id = odm.Optional(odm.Keyword(description="Unique identifier for the organization."))
    name = odm.Keyword(description="Organization name.")
