"""ETag utility module for handling HTTP ETags in Flask responses.

ETags (Entity Tags) are HTTP headers used for web cache validation and conditional requests.
They help optimize performance by allowing clients to cache responses and only fetch
new data when the resource has actually changed.
"""

import functools
import re

from flask import Response, request

from howler.api import not_modified


def add_etag(getter, check_if_match=True):
    """Decorator to add ETag handling to a Flask response.

    This decorator implements HTTP ETag functionality for API endpoints, enabling:
    - Conditional requests using If-Match headers
    - Cache validation to prevent unnecessary data transfers
    - Version tracking for resources

    Args:
        getter: Function that retrieves the object and its version
        check_if_match (bool): Whether to check If-Match headers for conditional requests

    Returns:
        Decorated function with ETag support
    """

    def wrapper(f):
        """Inner wrapper function that applies ETag functionality to the decorated function."""

        @functools.wraps(f)
        def generate_etag(*args, **kwargs):
            """Generate and handle ETags for the HTTP response."""
            # Retrieve the object and its version using the provided getter function
            # The getter should return (object, version) tuple
            obj, version = getter(
                kwargs.get("id", kwargs.get("username", None)),
                as_odm=True,
                version=True,
            )

            # Handle conditional requests with If-Match header
            # If the client's version matches the current version and it's a GET request
            # without metadata parameter, return 304 Not Modified to save bandwidth
            if (
                check_if_match
                and "If-Match" in request.headers
                and request.headers["If-Match"] == version
                and request.method == "GET"
                and "metadata" not in request.args
            ):
                return not_modified()

            # Extract the resource type from the API path and create a cache key
            # e.g., "/api/v1/users/123" becomes "cached_users"
            key = re.sub(r"^\/api\/v\d+\/(\w+)\/.+$", r"cached_\1", request.path)
            kwargs[key] = obj

            # Call the original function with the cached object and version
            values = f(*args, server_version=version, **kwargs)

            # Handle different return value formats from the decorated function
            # If there is only one return, it's just the response
            if isinstance(values, Response):
                # Only add ETag header for successful responses (not 409 Conflict or 400 Bad Request)
                if values.status_code != 409 and values.status_code != 400:
                    values.headers["ETag"] = version
                return values

            # If there are two returns, it's the response and the new version
            # This happens when the function modifies the resource and returns an updated version
            else:
                if values[0].status_code != 409 and values[0].status_code != 400:
                    # Add the new ETag version to successful responses
                    values[0].headers["ETag"] = values[1]
                return values[0]

        return generate_etag

    return wrapper
