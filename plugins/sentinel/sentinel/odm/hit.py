from typing import TYPE_CHECKING

import howler.odm as odm
from howler.common.logging import get_logger
from howler.odm.models.azure import Azure

from sentinel.odm.models.sentinel import Sentinel

if TYPE_CHECKING:
    from howler.odm.models.hit import Hit


logger = get_logger(__file__)


def modify_odm(target):
    "Add additional internal fields to the ODM"
    target.add_namespace(
        "sentinel",
        odm.Optional(odm.Compound(Sentinel, description="Sentinel metadata associated with this alert")),
    )


def generate(hit: "Hit") -> "Hit":  # pragma: no cover
    "Add cccs-specific changes to hits on generation"
    hit.sentinel = Sentinel({"id": "example-sentinel-id"})

    if not hit.azure:
        hit.azure = Azure({"tenant_id": "example-tenant-id"})
    else:
        hit.azure.tenant_id = "example-tenant-id"

    return ["sentinel"], hit
