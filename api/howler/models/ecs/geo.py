"""ECS geo field set."""

from __future__ import annotations

from howler.models import Float, HowlerEmbeddedModel, Keyword, register_model


@register_model(index=True, store=True, description="Longitude and latitude.", embedded=True)
class GeoPoint(HowlerEmbeddedModel):
    """Longitude and latitude."""

    lon: Float
    """Longitude"""
    lat: Float
    """Latitude"""


@register_model(
    index=True,
    store=True,
    description="Geo fields can carry data about a specific location related to an event.",
    embedded=True,
)
class Geo(HowlerEmbeddedModel):
    """Geo fields can carry data about a specific location related to an event."""

    city_name: Keyword | None = None
    """City name."""
    continent_code: Keyword | None = None
    """Two-letter code representing continent's name."""
    continent_name: Keyword | None = None
    """Name of the continent."""
    country_iso_code: Keyword | None = None
    """Country ISO code."""
    country_name: Keyword | None = None
    """Country name."""
    location: GeoPoint | None = None
    """Longitude and latitude."""
    name: Keyword | None = None
    """User-defined description of a location, at the level of granularity they care about."""
    postal_code: Keyword | None = None
    """Postal code associated with the location."""
    region_iso_code: Keyword | None = None
    """Region ISO code."""
    region_name: Keyword | None = None
    """Region name."""
    timezone: Keyword | None = None
    """The time zone of the location, such as IANA time zone name."""
