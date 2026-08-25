"""ECS HTTP field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, integer, keyword, optional, register_model


@register_model(index=True, store=True, description="Defines the body of a request/response.", embedded=True)
class Body(HowlerEmbeddedModel):
    """Defines the body of a request/response."""

    bytes: optional(integer(), description="Size in bytes of the body.")
    content: optional(keyword(), description="The full HTTP body.")


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Request(HowlerEmbeddedModel):
    """Details about an HTTP request."""

    body: optional(compound(Body), description="Defines the body of a request")
    bytes: optional(integer(), description="Total size in bytes of the request (body and headers).")
    id: optional(
        keyword(),
        description="A unique identifier for each HTTP request to correlate logs between clients "
        "and servers in transactions.",
    )
    method: optional(keyword(), description="HTTP request method.")
    mime_type: optional(keyword(), description="Mime type of the body of the request.")
    referrer: optional(keyword(), description="Referrer for this HTTP request.")


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Response(HowlerEmbeddedModel):
    """Details about an HTTP response."""

    body: optional(compound(Body), description="Defines the body of a response")
    bytes: optional(integer(), description="Total size in bytes of the request (body and headers).")
    mime_type: optional(keyword(), description="Mime type of the body of the request.")
    status_code: optional(integer(), description="HTTP response status code.")


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class HTTP(HowlerEmbeddedModel):
    """Fields related to HTTP activity."""

    request: optional(compound(Request), description="Request data.")
    response: optional(compound(Response), description="Response data.")
    version: optional(keyword(), description="HTTP version.")
