from typing import Any

from flask import Request


def generate_params(request: Request, fields: list[str], multi_fields: list[str], params: dict[str, Any] | None = None):
    """Generate parameters from request data and query arguments.

    Args:
        request: Incoming Flask request object.
        fields: Keys to copy as single values.
        multi_fields: Keys to copy as multi-value lists.
        params: Optional initial parameter mapping.

    Returns:
        A tuple containing the merged parameter dictionary and the source request data.
    """
    # I hate you, python
    if params is None:
        params = {}

    if request.method == "POST":
        parsed = request.get_json(silent=True)
        req_data = {"query": "*:*"} if parsed is None else parsed

        params = {
            **params,
            **{k: req_data[k] for k in fields if k in req_data},
            **{k: req_data[k] for k in multi_fields if k in req_data},
        }

    else:
        req_data = request.args
        params = {
            **params,
            **{k: req_data[k] for k in fields if k in req_data},
            **{k: req_data.getlist(k) for k in multi_fields if k in req_data},
        }

    return params, req_data
