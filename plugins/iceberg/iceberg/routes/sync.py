from datetime import datetime

from flask import request
from howler.api import make_subapi_blueprint, ok
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

from iceberg.services import sync_service

SUB_API = "sync"
iceberg_api = make_subapi_blueprint(SUB_API, api_version=1)

logger = get_logger(__file__)


@generate_swagger_docs()
@iceberg_api.route("/hit_diffs", methods=["GET"])
def get_upserted_hits():
    """Get the hits that have been created or updated since the last sync."""
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    last_sync_time = datetime.fromisoformat(from_date) if from_date else None
    optional_end_time = datetime.fromisoformat(to_date) if to_date else None

    hits = [
        hit.json()
        for hit in sync_service.get_upserted_hits(
            data_interval_start=last_sync_time, data_interval_end=optional_end_time
        )
    ]

    return ok(hits)
