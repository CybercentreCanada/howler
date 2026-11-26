"""ECS cloud field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, register_model

_CLOUD_ONTOLOGY_NOTE = (
    "Instead of using this more general field, use a platform-specific field. "
    "For more information, see [Disambiguated Cloud Ontology]"
    "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
)


@register_model(index=True, store=True, description="Cloud account information.", embedded=True)
class Account(HowlerEmbeddedModel):
    """Cloud account information."""

    id: keyword(
        optional=True,
        description="The cloud account or organization id used to identify different entities in a "
        "multi-tenant environment.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )
    name: keyword(
        optional=True,
        description="The cloud account name or alias used to identify different entities in a "
        "multi-tenant environment.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )


@register_model(index=True, store=True, description="Instance information.", embedded=True)
class Instance(HowlerEmbeddedModel):
    """Instance information."""

    id: keyword(optional=True, description="Instance ID of the host machine.")
    name: keyword(optional=True, description="Instance name of the host machine.")


@register_model(index=True, store=True, description="Project information.", embedded=True)
class Project(HowlerEmbeddedModel):
    """Project information."""

    id: keyword(
        optional=True,
        description="The cloud project identifier.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )
    name: keyword(
        optional=True,
        description="The cloud project name.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )


@register_model(index=True, store=True, description="Machine information.", embedded=True)
class Machine(HowlerEmbeddedModel):
    """Machine information."""

    type: keyword(optional=True, description="Machine type of the host machine.")


@register_model(index=True, store=True, description="Service information.", embedded=True)
class Service(HowlerEmbeddedModel):
    """Service information."""

    name: keyword(
        optional=True,
        description="The cloud service name is intended to distinguish services running on different platforms "
        "within a provider, eg AWS EC2 vs Lambda, GCP GCE vs App Engine, Azure VM vs App Server.",
    )


@register_model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
    embedded=True,
)
class Cloud(HowlerEmbeddedModel):
    """Fields related to the cloud or infrastructure the events are coming from."""

    account: compound(
        Account,
        optional=True,
        description="Cloud account information.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )
    availability_zone: keyword(
        optional=True,
        description="Availability zone in which this host, resource, or service is located.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )
    instance: compound(Instance, optional=True, description="Instance information.")
    machine: compound(Machine, optional=True, description="Machine information.")
    project: compound(
        Project,
        optional=True,
        description="Project information.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )
    provider: keyword(
        optional=True, description="Name of the cloud provider. Example values are aws, azure, gcp, or digitalocean."
    )
    region: keyword(optional=True, description="Region in which this host, resource, or service is located.")
    service: compound(Service, optional=True, description="Service information.")

    # Extra fields not defined in ECS but added for outline purposes
    tenant_id: keyword(
        optional=True,
        description="The tenant id associated with this alert.",
        deprecated=True,
        deprecated_description=_CLOUD_ONTOLOGY_NOTE,
    )
