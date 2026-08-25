"""ECS geo field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, float_field, keyword, optional, register_model


@register_model(index=True, store=True, description="Longitude and latitude.", embedded=True)
class GeoPoint(HowlerEmbeddedModel):
    """Longitude and latitude."""

    lon: float_field(description="Longitude")
    lat: float_field(description="Latitude")


@register_model(
    index=True,
    store=True,
    description="Geo fields can carry data about a specific location related to an event.",
    embedded=True,
)
class Geo(HowlerEmbeddedModel):
    """Geo fields can carry data about a specific location related to an event."""

    city_name: optional(keyword(), description="City name.")
    continent_code: optional(keyword(), description="Two-letter code representing continent's name.")
    continent_name: optional(keyword(), description="Name of the continent.")
    country_iso_code: optional(keyword(), description="Country ISO code.")
    country_name: optional(keyword(), description="Country name.")
    location: optional(compound(GeoPoint), description="Longitude and latitude.")
    name: optional(
        keyword(),
        description="User-defined description of a location, at the level of granularity they care about.",
    )
    postal_code: optional(keyword(), description="Postal code associated with the location.")
    region_iso_code: optional(keyword(), description="Region ISO code.")
    region_name: optional(keyword(), description="Region name.")
    timezone: optional(keyword(), description="The time zone of the location, such as IANA time zone name.")
