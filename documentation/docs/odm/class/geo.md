??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Geo

> Geo fields can carry data about a specific location related to an event.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| city_name | Keyword | City name. | :material-minus-box-outline: Optional | `None` |
| continent_code | Keyword | Two-letter code representing continent’s name. | :material-minus-box-outline: Optional | `None` |
| continent_name | Keyword | Name of the continent. | :material-minus-box-outline: Optional | `None` |
| country_iso_code | Keyword | Country ISO code. | :material-minus-box-outline: Optional | `None` |
| country_name | Keyword | Country name. | :material-minus-box-outline: Optional | `None` |
| location | [GeoPoint](/howler-docs/odm/class/geopoint) | Longitude and latitude. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | User-defined description of a location, at the level of granularity they care about. | :material-minus-box-outline: Optional | `None` |
| postal_code | Keyword | Postal code associated with the location. | :material-minus-box-outline: Optional | `None` |
| region_iso_code | Keyword | City name. | :material-minus-box-outline: Optional | `None` |
| region_name | Keyword | Region name. | :material-minus-box-outline: Optional | `None` |
| timezone | Keyword | The time zone of the location, such as IANA time zone name. | :material-minus-box-outline: Optional | `None` |
