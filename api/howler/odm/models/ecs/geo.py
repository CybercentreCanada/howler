from howler import odm


@odm.model(index=True, store=True, description="Longitude and latitude.")
class GeoPoint(odm.Model):
    lon = odm.Float(description="Longitude")
    lat = odm.Float(description="Latitude")


@odm.model(
    index=True,
    store=True,
    description="Geo fields can carry data about a specific location related to an event.",
)
class Geo(odm.Model):
    city_name = odm.Optional(odm.Keyword(description="City name."))
    continent_code = odm.Optional(odm.Keyword(description="Two-letter code representing continent’s name."))
    continent_name = odm.Optional(odm.Keyword(description="Name of the continent."))
    country_iso_code = odm.Optional(odm.Keyword(description="Country ISO code."))
    country_name = odm.Optional(odm.Keyword(description="Country name."))
    location = odm.Optional(odm.Compound(GeoPoint, description="Longitude and latitude."))
    name = odm.Optional(
        odm.Keyword(
            description="User-defined description of a location, at the level " "of granularity they care about."
        )
    )
    postal_code = odm.Optional(odm.Keyword(description="Postal code associated with the location."))
    region_iso_code = odm.Optional(odm.Keyword(description="Region ISO code."))
    region_name = odm.Optional(odm.Keyword(description="Region name."))
    timezone = odm.Optional(odm.Keyword(description="The time zone of the location, such as IANA time zone name."))
