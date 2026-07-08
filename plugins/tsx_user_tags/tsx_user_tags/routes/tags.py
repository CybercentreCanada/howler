from howler.api import internal_error, make_subapi_blueprint, ok
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.security import api_login

SUB_API = "tags"
tags_api = make_subapi_blueprint(SUB_API, api_version=1)
tags_api._doc = "Allow analysts to manage personal tags (portfolio, products, disciplines)"

logger = get_logger(__file__)


@generate_swagger_docs()
@tags_api.route("/all", methods=["GET"])
@api_login(required_priv=["R"], required_type=["user"])
def get_all_tags(**kwargs):
    """Get all available tags (controlled lists for portfolio, products, primary_disciplines).

    Returns all tag options that users can select from when configuring their
    personal tags. Each tag type is backed by a configurable provider (e.g.,
    static config or analytics datastore).

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    {
        "portfolio": [
            {"value": "ACME Corp", "name": "ACME Corp"},
            {"value": "Widget Inc", "name": "Widget Inc"}
        ],
        "products": [
            {"value": "crowdstrike", "name": "CrowdStrike"},
            {"value": "sentinel", "name": "Microsoft Sentinel"}
        ],
        "primary_disciplines": [
            {"value": "identity", "name": "Identity"},
            {"value": "malware", "name": "Malware"}
        ]
    }
    """
    try:
        from tsx_user_tags.config import tag_service

        all_tags = tag_service.fetch_all()
        return ok(all_tags)
    except Exception:
        logger.exception("Failed to fetch tags")
        return internal_error(err="Failed to fetch tags")


@generate_swagger_docs()
@tags_api.route("/cache", methods=["DELETE"])
@api_login(required_priv=["W"], required_type=["admin"])
def invalidate_tags_cache(**kwargs):
    """Invalidate the cached analytics tag lists (admin only).

    Forces portfolio and product tags to be refetched on the next request,
    across all workers. Use after new analytics or hit data is ingested.

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    {"version": 4}
    """
    try:
        from tsx_user_tags.providers.analytics import invalidate_cache

        version = invalidate_cache()
        return ok({"version": version})
    except Exception:
        logger.exception("Failed to invalidate tags cache")
        return internal_error(err="Failed to invalidate tags cache")
