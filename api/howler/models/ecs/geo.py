"""ECS geo field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, float_field, keyword, register_model


@register_model(index=True, store=True, description="Longitude and latitude.", embedded=True)
class GeoPoint(HowlerEmbeddedModel):
    """Longitude and latitude."""

    lon: float_field()
    """Longitude"""
    lat: float_field()
    """Latitude"""


@register_model(
    index=True,
    store=True,
    description="Geo fields can carry data about a specific location related to an event.",
    embedded=True,
)
class Geo(HowlerEmbeddedModel):
    """Geo fields can carry data about a specific location related to an event."""

    city_name: keyword(optional=True)
    """City name."""
    continent_code: keyword(optional=True)
    """Two-letter code representing continent's name."""
    continent_name: keyword(optional=True)
    """Name of the continent."""
    country_iso_code: keyword(optional=True)
    """Country ISO code."""
    country_name: keyword(optional=True)
    """Country name."""
    location: GeoPoint | None = None
    """Longitude and latitude."""
    name: keyword(optional=True)
    """User-defined description of a location, at the level of granularity they care about."""
    postal_code: keyword(optional=True)
    """Postal code associated with the location."""
    region_iso_code: keyword(optional=True)
    """Region ISO code."""
    region_name: keyword(optional=True)
    """Region name."""
    timezone: keyword(optional=True)
    """The time zone of the location, such as IANA time zone name."""
