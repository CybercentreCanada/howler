"""ECS container field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, list_field, mapping, register_model


@register_model(index=True, store=True, description="Container hashes information.", embedded=True)
class Hash(HowlerEmbeddedModel):
    """Container hashes information."""

    all: list_field(keyword(), default=[], description="An array of digests of the image the container was built on.")


@register_model(index=True, store=True, description="Information about the container Image.", embedded=True)
class Image(HowlerEmbeddedModel):
    """Information about the container Image."""

    hash: compound(Hash, optional=True, description="Container hashes information.")
    name: keyword(optional=True, description="Name of the image the container was built on.")
    tag: list_field(keyword(), default=[], description="Container image tags.")


@register_model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
    embedded=True,
)
class Container(HowlerEmbeddedModel):
    """Container metadata."""

    id: keyword(optional=True, description="Unique container id.")
    image: compound(Image, optional=True, description="Cloud account information.")
    labels: mapping(keyword(), optional=True, description="Image labels.")
    name: keyword(optional=True, description="Container name.")
    runtime: keyword(optional=True, description="Runtime managing this container.")
