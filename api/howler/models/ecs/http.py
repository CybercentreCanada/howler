"""ECS HTTP field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Integer, Keyword, register_model


@register_model(index=True, store=True, description="Defines the body of a request/response.", embedded=True)
class Body(HowlerEmbeddedModel):
    """Defines the body of a request/response."""

    bytes: Integer | None = None
    """Size in bytes of the body."""
    content: Keyword | None = None
    """The full HTTP body."""


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Request(HowlerEmbeddedModel):
    """Details about an HTTP request."""

    body: Body | None = None
    """Defines the body of a request"""
    bytes: Integer | None = None
    """Total size in bytes of the request (body and headers)."""
    id: Keyword | None = None
    """A unique identifier for each HTTP request to correlate logs between clients and servers in transactions."""
    method: Keyword | None = None
    """HTTP request method."""
    mime_type: Keyword | None = None
    """Mime type of the body of the request."""
    referrer: Keyword | None = None
    """Referrer for this HTTP request."""


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class Response(HowlerEmbeddedModel):
    """Details about an HTTP response."""

    body: Body | None = None
    """Defines the body of a response"""
    bytes: Integer | None = None
    """Total size in bytes of the request (body and headers)."""
    mime_type: Keyword | None = None
    """Mime type of the body of the request."""
    status_code: Integer | None = None
    """HTTP response status code."""


@register_model(index=True, store=True, description="These fields can represent errors of any kind.", embedded=True)
class HTTP(HowlerEmbeddedModel):
    """Fields related to HTTP activity."""

    request: Request | None = None
    """Request data."""
    response: Response | None = None
    """Response data."""
    version: Keyword | None = None
    """HTTP version."""
