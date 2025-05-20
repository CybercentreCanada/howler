import functools
import re

from flask import Response, request

from howler.api import not_modified


def add_etag(getter, check_if_match=False):
    """Decorator to add etag handling to a flask response"""

    def wrapper(f):
        @functools.wraps(f)
        def generate_etag(*args, **kwargs):
            obj, version = getter(
                kwargs.get("id", kwargs.get("username", None)),
                as_odm=True,
                version=True,
            )
            if (
                not check_if_match
                and "If-Match" in request.headers
                and request.headers["If-Match"] == version
                and request.method == "GET"
            ):
                return not_modified()

            key = re.sub(r"^\/api\/v\d+\/(\w+)\/.+$", r"cached_\1", request.path)
            kwargs[key] = obj

            values = f(*args, server_version=version, **kwargs)

            # If there is only one return, Its just the response
            if isinstance(values, Response):
                if values.status_code != 409 and values.status_code != 400:
                    values.headers["ETag"] = version
                return values
            # If there is two returns, its the response and the new version
            else:
                if values[0].status_code != 409 and values[0].status_code != 400:
                    values[0].headers["ETag"] = values[1]
                return values[0]

        return generate_etag

    return wrapper
