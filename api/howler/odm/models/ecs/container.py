from typing import Optional

from howler import odm


@odm.model(index=True, store=True, description="Container hashes information.")
class Hash(odm.Model):
    all: list[str] = odm.List(
        odm.Keyword(),
        description="An array of digests of the image the container was built on.",
        default=[],
    )


@odm.model(index=True, store=True, description="Information about the container Image.")
class Image(odm.Model):
    hash: Optional[Hash] = odm.Optional(odm.Compound(Hash, description="Container hashes information."))
    name: Optional[str] = odm.Optional(odm.Keyword(description="Name of the image the container was built on."))
    tag: list[str] = odm.List(odm.Keyword(), description="Container image tags.", default=[])


@odm.model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
)
class Container(odm.Model):
    id = odm.Optional(odm.Keyword(description="Unique container id."))
    image = odm.Optional(odm.Compound(Image, description="Cloud account information."))
    labels = odm.Optional(odm.Mapping(odm.Keyword(), description="Image labels."))
    name = odm.Optional(odm.Keyword(description="Container name."))
    runtime = odm.Optional(odm.Keyword(description="Runtime managing this container."))
