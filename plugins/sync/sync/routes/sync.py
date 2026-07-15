from datetime import datetime

from howler.api import make_subapi_blueprint, ok
from howler.api.v1.utils.params import parse_parameters
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

from sync.services import sync_service

SUB_API = "sync"
sync_api = make_subapi_blueprint(SUB_API, api_version=1)

logger = get_logger(__file__)


@generate_swagger_docs()
@sync_api.route("/hit_diffs", methods=["GET"])
@parse_parameters(from_date="required", to_date=None)
def get_upserted_hits(*, from_date: str, to_date: str | None = None, **_extra_args):
    """Get the hits that have been created or updated since the last sync.

    Arguments:
    from_date   => The date to check for new or updated hits since, required.

    Optional Arguments:
    to_date     => The date beyond which to ignore any new or updated hits.

    Result Example:
    [
        ...hits  # list of hits that have been created or updated since the last sync
    ]
    """
    last_sync_time = datetime.fromisoformat(from_date)
    optional_end_time = datetime.fromisoformat(to_date) if to_date else None

    hits = [
        hit.json()
        for hit in sync_service.get_upserted_hits(
            data_interval_start=last_sync_time, data_interval_end=optional_end_time
        )
    ]

    return ok(hits)
