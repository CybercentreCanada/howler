"""Google Cloud Platform (GCP) provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(index=True, store=True, description="Fields related to Google Cloud Platform.", embedded=True)
class GCP(HowlerEmbeddedModel):
    """Fields related to Google Cloud Platform."""

    project_id: optional(keyword(), description="The unique identifier for the GCP project.")
    network_id: optional(keyword(), description="The unique identifier for a Google Cloud Platform (GCP) network.")
    zone: optional(keyword(), description="The GCP zone of the instance.")
    service_account_id: optional(keyword(), description="Unique identifier for a GCP service account.")
    resource_id: optional(keyword(), description="Unique GCP resource identifier.")
