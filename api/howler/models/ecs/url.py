"""ECS URL field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, domain, integer, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="URL fields provide support for complete or partial URLs, and supports "
    "the breaking down into scheme, domain, path, and so on.",
    embedded=True,
)
class URL(HowlerEmbeddedModel):
    """URL fields provide support for complete or partial URLs."""

    domain: optional(domain(), description='Domain of the url, such as "www.elastic.co".')
    extension: optional(
        keyword(),
        description="The field contains the file extension from the original request url, excluding the leading dot.",
    )
    fragment: optional(keyword(), description='Portion of the url after the #, such as "top".')
    full: optional(
        keyword(),
        description="If full URLs are important to your use case, they should be stored "
        "in url.full, whether this field is reconstructed or present in the event source.",
    )
    original: optional(keyword(), description="Unmodified original url as seen in the event source.")
    password: optional(keyword(), description="Password of the request.")
    path: optional(keyword(), description='Path of the request, such as "/search".')
    port: optional(integer(), description="Port of the request, such as 443.")
    query: optional(
        keyword(),
        description='The query field describes the query string of the request, such as "q=elasticsearch".',
    )
    registered_domain: optional(keyword(), description="The highest registered url domain, stripped of the subdomain.")
    scheme: optional(keyword(), description='Scheme of the request, such as "https".')
    subdomain: optional(
        keyword(),
        description="The subdomain portion of a fully qualified domain name includes "
        "all of the names except the host name under the registered_domain.",
    )
    top_level_domain: optional(
        keyword(),
        description="The effective top level domain (eTLD), also known as "
        "the domain suffix, is the last part of the domain name.",
    )
    username: optional(keyword(), description="Username of the request.")
