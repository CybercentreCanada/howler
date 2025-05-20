from howler import odm


@odm.model(
    index=True,
    store=True,
    description="URL fields provide support for complete or partial URLs, and supports "
    "the breaking down into scheme, domain, path, and so on.",
)
class URL(odm.Model):
    domain = odm.Optional(odm.Domain(description='Domain of the url, such as "www.elastic.co".'))
    extension = odm.Optional(
        odm.Keyword(
            description="The field contains the file extension from the original request "
            "url, excluding the leading dot."
        )
    )
    fragment = odm.Optional(odm.Keyword(description='Portion of the url after the #, such as "top".'))
    full = odm.Optional(
        odm.Keyword(
            description="If full URLs are important to your use case, they should be stored "
            "in url.full, whether this field is reconstructed or present in the event source."
        )
    )
    original = odm.Optional(odm.Keyword(description="Unmodified original url as seen in the event source."))
    password = odm.Optional(odm.Keyword(description="Password of the request."))
    path = odm.Optional(odm.Keyword(description='Path of the request, such as "/search".'))
    port = odm.Optional(odm.Integer(description="Port of the request, such as 443."))
    query = odm.Optional(
        odm.Keyword(
            description="The query field describes the query string of the " 'request, such as "q=elasticsearch".'
        )
    )
    registered_domain = odm.Optional(
        odm.Keyword(description="The highest registered url domain, " "stripped of the subdomain.")
    )
    scheme = odm.Optional(odm.Keyword(description='Scheme of the request, such as "https".'))
    subdomain = odm.Optional(
        odm.Keyword(
            description="The subdomain portion of a fully qualified domain name includes "
            "all of the names except the host name under "
            "the registered_domain."
        )
    )
    top_level_domain = odm.Optional(
        odm.Keyword(
            description="The effective top level domain (eTLD), also known as "
            "the domain suffix, is the last part of the domain name."
        )
    )
    username = odm.Optional(odm.Keyword(description="Username of the request."))
