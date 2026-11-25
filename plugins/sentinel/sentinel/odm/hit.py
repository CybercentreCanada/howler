"""Synthetic-data hook; field declarations live in sentinel.models.hit."""

from howler.models.azure import Azure
from howler.models.hit import Hit

from sentinel.models.sentinel import Sentinel


def generate(hit: Hit) -> tuple[list[str], Hit]:
    """Populate the finalized Sentinel extension with example metadata."""
    hit["sentinel"] = Sentinel(id="example-sentinel-id")
    if not hit.azure:
        hit.azure = Azure(tenant_id="example-tenant-id")
    else:
        hit.azure.tenant_id = "example-tenant-id"
    return ["sentinel"], hit
