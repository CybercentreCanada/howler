from howler import odm


@odm.model(
    index=True,
    store=True,
    description="This field set is meant to facilitate pivoting around a piece of data.",
)
class Related(odm.Model):
    hash: list[str] = odm.List(
        odm.Keyword(),
        description="All the hashes seen on your event. Populating this field, then using it to search "
        "for hashes can help in situations where you're unsure what the hash algorithm is "
        "(and therefore which key name to search).",
        default=[],
    )
    hosts: list[str] = odm.List(
        odm.Keyword(),
        description="All hostnames or other host identifiers seen on your event. Example identifiers "
        "include FQDNs, domain names, workstation names, or aliases.",
        default=[],
    )
    ip: list[str] = odm.List(odm.IP(), description="All of the IPs seen on your event.", default=[])
    user: list[str] = odm.List(
        odm.Keyword(),
        description="All the user names or other user identifiers seen on the event.",
        default=[],
    )
    ids: list[str] = odm.List(
        odm.Keyword(),
        description="Any identifier that doesn't fit in other related fields like a GUID.",
        default=[],
    )

    # Extra fields not defined in ECS but added for outline purposes
    id = odm.Optional(odm.Keyword(description="The id related to the event."))

    uri = odm.Optional(odm.List(odm.URI(), description="All of the URIs related to the event."))

    signature = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="All the signatures/rules that were triggered by the event.",
        )
    )
