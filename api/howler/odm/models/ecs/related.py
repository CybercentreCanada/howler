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
    id = odm.Optional(
        odm.Keyword(
            description="The id related to the event.",
            deprecated=True,
            deprecated_description="related.ids should be used instead of related.id.",
        )
    )

    uri = odm.Optional(odm.List(odm.URI(), description="All of the URIs related to the event."))

    signature = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="All the signatures/rules that were triggered by the event.",
        )
    )

    def __init__(self, data: dict = None, *args, **kwargs):
        if data is not None and "id" in data and data["id"] is not None:
            # Avoid mutating the caller-provided dict
            data = dict(data)

            existing_ids = data.get("ids")
            if isinstance(existing_ids, (list, tuple)):
                merged_ids = list(existing_ids)
            elif existing_ids is None:
                merged_ids = []
            else:
                merged_ids = [existing_ids]

            if data["id"] not in merged_ids:
                merged_ids.append(data["id"])

            data["ids"] = merged_ids

        super().__init__(data, *args, **kwargs)
