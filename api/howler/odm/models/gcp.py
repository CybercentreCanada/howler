from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Fields related to Google Cloud Platform.",
)
class GCP(odm.Model):
    project_id = odm.Optional(odm.Keyword(description="The unique identifier for the GCP project."))
    network_id = odm.Optional(
        odm.Keyword(description="The unique identifier for a Google Cloud Platform (GCP) network.")
    )
    zone = odm.Optional(odm.Keyword(description="The GCP zone of the instance."))
    service_account_id = odm.Optional(odm.Keyword(description="Unique identifier for a GCP service account."))
    resource_id = odm.Optional(odm.Keyword(description="Unique GCP resource identifier."))
