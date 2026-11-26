"""ECS URL field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, domain, integer, keyword, register_model


@register_model(
    index=True,
    store=True,
    description="URL fields provide support for complete or partial URLs, and supports "
    "the breaking down into scheme, domain, path, and so on.",
    embedded=True,
)
class URL(HowlerEmbeddedModel):
    """URL fields provide support for complete or partial URLs."""

    domain: domain(optional=True)
    """Domain of the url, such as "www.elastic.co"."""
    extension: keyword(optional=True)
    """The field contains the file extension from the original request url, excluding the leading dot."""
    fragment: keyword(optional=True)
    """Portion of the url after the #, such as "top"."""
    full: keyword(optional=True)
    (
        "If full URLs are important to your use case, they should be stored in url.full, whether this field is "
        "reconstructed or present in the event source."
    )
    original: keyword(optional=True)
    """Unmodified original url as seen in the event source."""
    password: keyword(optional=True)
    """Password of the request."""
    path: keyword(optional=True)
    """Path of the request, such as "/search"."""
    port: integer(optional=True)
    """Port of the request, such as 443."""
    query: keyword(optional=True)
    """The query field describes the query string of the request, such as "q=elasticsearch"."""
    registered_domain: keyword(optional=True)
    """The highest registered url domain, stripped of the subdomain."""
    scheme: keyword(optional=True)
    """Scheme of the request, such as "https"."""
    subdomain: keyword(optional=True)
    (
        "The subdomain portion of a fully qualified domain name includes all of the names except the host name under "
        "the registered_domain."
    )
    top_level_domain: keyword(optional=True)
    """The effective top level domain (eTLD), also known as the domain suffix, is the last part of the domain name."""
    username: keyword(optional=True)
    """Username of the request."""
