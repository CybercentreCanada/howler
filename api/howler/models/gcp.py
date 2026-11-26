"""Google Cloud Platform (GCP) provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


@register_model(index=True, store=True, description="Fields related to Google Cloud Platform.", embedded=True)
class GCP(HowlerEmbeddedModel):
    """Fields related to Google Cloud Platform."""

    project_id: keyword(optional=True, description="The unique identifier for the GCP project.")
    network_id: keyword(optional=True, description="The unique identifier for a Google Cloud Platform (GCP) network.")
    zone: keyword(optional=True, description="The GCP zone of the instance.")
    service_account_id: keyword(optional=True, description="Unique identifier for a GCP service account.")
    resource_id: keyword(optional=True, description="Unique GCP resource identifier.")
