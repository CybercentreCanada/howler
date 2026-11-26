"""ECS container field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, list_field, mapping, register_model


@register_model(index=True, store=True, description="Container hashes information.", embedded=True)
class Hash(HowlerEmbeddedModel):
    """Container hashes information."""

    all: list_field(keyword(), default=[])
    """An array of digests of the image the container was built on."""


@register_model(index=True, store=True, description="Information about the container Image.", embedded=True)
class Image(HowlerEmbeddedModel):
    """Information about the container Image."""

    hash: Hash | None = None
    """Container hashes information."""
    name: keyword(optional=True)
    """Name of the image the container was built on."""
    tag: list_field(keyword(), default=[])
    """Container image tags."""


@register_model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
    embedded=True,
)
class Container(HowlerEmbeddedModel):
    """Container metadata."""

    id: keyword(optional=True)
    """Unique container id."""
    image: Image | None = None
    """Cloud account information."""
    labels: mapping(keyword(), optional=True)
    """Image labels."""
    name: keyword(optional=True)
    """Container name."""
    runtime: keyword(optional=True)
    """Runtime managing this container."""
