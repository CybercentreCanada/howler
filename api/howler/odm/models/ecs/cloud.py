from typing import Optional

from howler import odm


@odm.model(index=True, store=True, description="Cloud account information.")
class Account(odm.Model):
    id: Optional[str] = odm.Optional(
        odm.Keyword(
            description="The cloud account or organization id used to identify different entities in a "
            "multi-tenant environment.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        ),
    )
    name: Optional[str] = odm.Optional(
        odm.Keyword(
            description="The cloud account name or alias used to identify different entities in a "
            "multi-tenant environment.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        ),
    )


@odm.model(index=True, store=True, description="Instance information.")
class Instance(odm.Model):
    id = odm.Optional(odm.Keyword(description="Instance ID of the host machine."))
    name = odm.Optional(odm.Keyword(description="Instance name of the host machine."))


@odm.model(index=True, store=True, description="Project information.")
class Project(odm.Model):
    id = odm.Optional(
        odm.Keyword(
            description="The cloud project identifier.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        )
    )
    name = odm.Optional(
        odm.Keyword(
            description="The cloud project name.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        )
    )


@odm.model(index=True, store=True, description="Machine information.")
class Machine(odm.Model):
    type = odm.Optional(odm.Keyword(description="Machine type of the host machine."))


@odm.model(index=True, store=True, description="Service information.")
class Service(odm.Model):
    name = odm.Optional(
        odm.Keyword(
            description="The cloud service name is intended to distinguish services running on different platforms "
            "within a provider, eg AWS EC2 vs Lambda, GCP GCE vs App Engine, Azure VM vs App Server."
        )
    )


@odm.model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
)
class Cloud(odm.Model):
    account = odm.Optional(
        odm.Compound(
            Account,
            description="Cloud account information.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        )
    )
    availability_zone = odm.Optional(
        odm.Keyword(
            description="Availability zone in which this host, resource, or service is located.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        )
    )
    instance = odm.Optional(odm.Compound(Instance, description="Instance information."))
    machine = odm.Optional(odm.Compound(Machine, description="Machine information."))
    project = odm.Optional(
        odm.Compound(
            Project,
            description="Project information.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        )
    )
    provider = odm.Optional(
        odm.Keyword(description="Name of the cloud provider. Example values are aws, azure, gcp, or digitalocean.")
    )
    region = odm.Optional(odm.Keyword(description="Region in which this host, resource, or service is located."))
    service = odm.Optional(odm.Compound(Service, description="Service information."))

    # Extra fields not defined in ECS but added for outline purposes
    tenant_id = odm.Optional(
        odm.Keyword(
            description="The tenant id associated with this alert.",
            deprecated=True,
            deprecated_description=(
                "Instead of using this more general field, use a platform-specific field. "
                "For more information, see [Disambiguated Cloud Ontology]"
                "(https://confluence.devtools.cse-cst.gc.ca/display/DASI2/Disambiguated+Cloud+Ontology)"
            ),
        )
    )
