"""ECS container field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, mapping, register_model


@register_model(index=True, store=True, description="Container hashes information.", embedded=True)
class Hash(HowlerEmbeddedModel):
    """Container hashes information."""

    all: list[Keyword] = []
    """An array of digests of the image the container was built on."""


@register_model(index=True, store=True, description="Information about the container Image.", embedded=True)
class Image(HowlerEmbeddedModel):
    """Information about the container Image."""

    hash: Hash | None = None
    """Container hashes information."""
    name: Keyword | None = None
    """Name of the image the container was built on."""
    tag: list[Keyword] = []
    """Container image tags."""


@register_model(
    index=True,
    store=True,
    description="Fields related to the cloud or infrastructure the events are coming from.",
    embedded=True,
)
class Container(HowlerEmbeddedModel):
    """Container metadata."""

    id: Keyword | None = None
    """Unique container id."""
    image: Image | None = None
    """Cloud account information."""
    labels: mapping(Keyword, optional=True)
    """Image labels."""
    name: Keyword | None = None
    """Container name."""
    runtime: Keyword | None = None
    """Runtime managing this container."""
