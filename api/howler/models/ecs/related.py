"""ECS related field set."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import model_validator

from howler.models import HowlerEmbeddedModel, keyword, metadata, register_model
from howler.models import ip as ip_field
from howler.models import uri as uri_field


@register_model(
    index=True,
    store=True,
    description="This field set is meant to facilitate pivoting around a piece of data.",
    embedded=True,
)
class Related(HowlerEmbeddedModel):
    """This field set is meant to facilitate pivoting around a piece of data."""

    hash: list[keyword()] = []
    (
        "All the hashes seen on your event. Populating this field, then using it to search for hashes can help in "
        "situations where you're unsure what the hash algorithm is (and therefore which key name to search)."
    )
    hosts: list[keyword()] = []
    (
        "All hostnames or other host identifiers seen on your event. Example identifiers include FQDNs, domain names, "
        "workstation names, or aliases."
    )
    ip: Annotated[list[ip_field()], metadata(default=[])]
    """All of the IPs seen on your event."""
    user: list[keyword()] = []
    """All the user names or other user identifiers seen on the event."""
    ids: list[keyword()] = []
    """Any identifier that doesn't fit in other related fields like a GUID."""

    # Extra fields not defined in ECS but added for outline purposes
    id: keyword(
        optional=True, deprecated=True, deprecated_description="related.ids should be used instead of related.id."
    )
    """The id related to the event."""
    uri: Annotated[list[uri_field()] | None, metadata(default=None)]
    """All of the URIs related to the event."""
    signature: list[keyword()] | None = None
    """All the signatures/rules that were triggered by the event."""

    @model_validator(mode="before")
    @classmethod
    def _merge_id_into_ids(cls, data: Any) -> Any:
        """Merge the deprecated ``id`` field into ``ids``, matching the legacy ``Related.__init__``."""
        if not isinstance(data, dict) or data.get("id") is None:
            return data

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
        return data
