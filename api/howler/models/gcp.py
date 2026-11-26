"""Google Cloud Platform (GCP) provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(index=True, store=True, description="Fields related to Google Cloud Platform.", embedded=True)
class GCP(HowlerEmbeddedModel):
    """Fields related to Google Cloud Platform."""

    project_id: Keyword | None = None
    """The unique identifier for the GCP project."""
    network_id: Keyword | None = None
    """The unique identifier for a Google Cloud Platform (GCP) network."""
    zone: Keyword | None = None
    """The GCP zone of the instance."""
    service_account_id: Keyword | None = None
    """Unique identifier for a GCP service account."""
    resource_id: Keyword | None = None
    """Unique GCP resource identifier."""
