"""ECS URL field set."""

from __future__ import annotations

from howler.models import Domain, HowlerEmbeddedModel, Integer, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description="URL fields provide support for complete or partial URLs, and supports "
    "the breaking down into scheme, domain, path, and so on.",
    embedded=True,
)
class URL(HowlerEmbeddedModel):
    """URL fields provide support for complete or partial URLs."""

    domain: Domain | None = None
    """Domain of the url, such as "www.elastic.co"."""
    extension: Keyword | None = None
    """The field contains the file extension from the original request url, excluding the leading dot."""
    fragment: Keyword | None = None
    """Portion of the url after the #, such as "top"."""
    full: Keyword | None = None
    (
        "If full URLs are important to your use case, they should be stored in url.full, whether this field is "
        "reconstructed or present in the event source."
    )
    original: Keyword | None = None
    """Unmodified original url as seen in the event source."""
    password: Keyword | None = None
    """Password of the request."""
    path: Keyword | None = None
    """Path of the request, such as "/search"."""
    port: Integer | None = None
    """Port of the request, such as 443."""
    query: Keyword | None = None
    """The query field describes the query string of the request, such as "q=elasticsearch"."""
    registered_domain: Keyword | None = None
    """The highest registered url domain, stripped of the subdomain."""
    scheme: Keyword | None = None
    """Scheme of the request, such as "https"."""
    subdomain: Keyword | None = None
    (
        "The subdomain portion of a fully qualified domain name includes all of the names except the host name under "
        "the registered_domain."
    )
    top_level_domain: Keyword | None = None
    """The effective top level domain (eTLD), also known as the domain suffix, is the last part of the domain name."""
    username: Keyword | None = None
    """Username of the request."""
