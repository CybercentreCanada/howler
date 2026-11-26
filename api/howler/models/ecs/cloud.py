"""ECS cloud field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import HowlerEmbeddedModel, keyword, metadata, register_model

_CLOUD_ONTOLOGY_NOTE = (
    "Instead of using this more general field, use a platform-specific field. "
    "For more information, see [Disambiguated Cloud Ontology]"
    "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
)


@register_model(index=True, store=True, description="Cloud account information.", embedded=True)
class Account(HowlerEmbeddedModel):
    """Cloud account information."""

    id: keyword(optional=True, deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)
    """The cloud account or organization id used to identify different entities in a multi-tenant environment."""
    name: keyword(optional=True, deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)
    """The cloud account name or alias used to identify different entities in a multi-tenant environment."""


@register_model(index=True, store=True, description="Instance information.", embedded=True)
class Instance(HowlerEmbeddedModel):
    """Instance information."""

    id: keyword(optional=True)
    """Instance ID of the host machine."""
    name: keyword(optional=True)
    """Instance name of the host machine."""


@register_model(index=True, store=True, description="Project information.", embedded=True)
class Project(HowlerEmbeddedModel):
    """Project information."""

    id: keyword(optional=True, deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)
    """The cloud project identifier."""
    name: keyword(optional=True, deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)
    """The cloud project name."""


@register_model(index=True, store=True, description="Machine information.", embedded=True)
class Machine(HowlerEmbeddedModel):
    """Machine information."""

    type: keyword(optional=True)
    """Machine type of the host machine."""


@register_model(index=True, store=True, description="Service information.", embedded=True)
class Service(HowlerEmbeddedModel):
    """Service information."""

    name: keyword(optional=True)
    (
        "The cloud service name is intended to distinguish services running on different platforms within a provider, "
        "eg AWS EC2 vs Lambda, GCP GCE vs App Engine, Azure VM vs App Server."
    )


@register_model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
    embedded=True,
)
class Cloud(HowlerEmbeddedModel):
    """Fields related to the cloud or infrastructure the events are coming from."""

    account: Annotated[Account | None, metadata(deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)] = None
    """Cloud account information."""
    availability_zone: keyword(optional=True, deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)
    """Availability zone in which this host, resource, or service is located."""
    instance: Instance | None = None
    """Instance information."""
    machine: Machine | None = None
    """Machine information."""
    project: Annotated[Project | None, metadata(deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)] = None
    """Project information."""
    provider: keyword(optional=True)
    """Name of the cloud provider. Example values are aws, azure, gcp, or digitalocean."""
    region: keyword(optional=True)
    """Region in which this host, resource, or service is located."""
    service: Service | None = None
    """Service information."""

    # Extra fields not defined in ECS but added for outline purposes
    tenant_id: keyword(optional=True, deprecated=True, deprecated_description=_CLOUD_ONTOLOGY_NOTE)
    """The tenant id associated with this alert."""
