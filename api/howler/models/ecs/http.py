"""ECS HTTP field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, integer, keyword, register_model


@register_model(index=True, store=True, description="Defines the body of a request/response.", embedded=True)
class Body(HowlerEmbeddedModel):
    """Defines the body of a request/response."""

    bytes: integer(optional=True, description="Size in bytes of the body.")
    content: keyword(optional=True, description="The full HTTP body.")


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Request(HowlerEmbeddedModel):
    """Details about an HTTP request."""

    body: compound(Body, optional=True, description="Defines the body of a request")
    bytes: integer(optional=True, description="Total size in bytes of the request (body and headers).")
    id: keyword(
        optional=True,
        description="A unique identifier for each HTTP request to correlate logs between clients "
        "and servers in transactions.",
    )
    method: keyword(optional=True, description="HTTP request method.")
    mime_type: keyword(optional=True, description="Mime type of the body of the request.")
    referrer: keyword(optional=True, description="Referrer for this HTTP request.")


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Response(HowlerEmbeddedModel):
    """Details about an HTTP response."""

    body: compound(Body, optional=True, description="Defines the body of a response")
    bytes: integer(optional=True, description="Total size in bytes of the request (body and headers).")
    mime_type: keyword(optional=True, description="Mime type of the body of the request.")
    status_code: integer(optional=True, description="HTTP response status code.")


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class HTTP(HowlerEmbeddedModel):
    """Fields related to HTTP activity."""

    request: compound(Request, optional=True, description="Request data.")
    response: compound(Response, optional=True, description="Response data.")
    version: keyword(optional=True, description="HTTP version.")
