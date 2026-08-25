"""ECS container field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, list_field, mapping, optional, register_model


@register_model(index=True, store=True, description="Container hashes information.", embedded=True)
class Hash(HowlerEmbeddedModel):
    """Container hashes information."""

    all: list_field(keyword(), default=[], description="An array of digests of the image the container was built on.")


@register_model(index=True, store=True, description="Information about the container Image.", embedded=True)
class Image(HowlerEmbeddedModel):
    """Information about the container Image."""

    hash: optional(compound(Hash), description="Container hashes information.")
    name: optional(keyword(), description="Name of the image the container was built on.")
    tag: list_field(keyword(), default=[], description="Container image tags.")


@register_model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
    embedded=True,
)
class Container(HowlerEmbeddedModel):
    """Container metadata."""

    id: optional(keyword(), description="Unique container id.")
    image: optional(compound(Image), description="Cloud account information.")
    labels: optional(mapping(keyword()), description="Image labels.")
    name: optional(keyword(), description="Container name.")
    runtime: optional(keyword(), description="Runtime managing this container.")
