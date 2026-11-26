"""ECS HTTP field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, integer, keyword, register_model


@register_model(index=True, store=True, description="Defines the body of a request/response.", embedded=True)
class Body(HowlerEmbeddedModel):
    """Defines the body of a request/response."""

    bytes: integer(optional=True)
    """Size in bytes of the body."""
    content: keyword(optional=True)
    """The full HTTP body."""


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Request(HowlerEmbeddedModel):
    """Details about an HTTP request."""

    body: Body | None = None
    """Defines the body of a request"""
    bytes: integer(optional=True)
    """Total size in bytes of the request (body and headers)."""
    id: keyword(optional=True)
    """A unique identifier for each HTTP request to correlate logs between clients and servers in transactions."""
    method: keyword(optional=True)
    """HTTP request method."""
    mime_type: keyword(optional=True)
    """Mime type of the body of the request."""
    referrer: keyword(optional=True)
    """Referrer for this HTTP request."""


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Response(HowlerEmbeddedModel):
    """Details about an HTTP response."""

    body: Body | None = None
    """Defines the body of a response"""
    bytes: integer(optional=True)
    """Total size in bytes of the request (body and headers)."""
    mime_type: keyword(optional=True)
    """Mime type of the body of the request."""
    status_code: integer(optional=True)
    """HTTP response status code."""


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class HTTP(HowlerEmbeddedModel):
    """Fields related to HTTP activity."""

    request: Request | None = None
    """Request data."""
    response: Response | None = None
    """Response data."""
    version: keyword(optional=True)
    """HTTP version."""
