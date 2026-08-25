"""ECS DNS field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    domain,
    integer,
    ip,
    keyword,
    list_field,
    optional,
    register_model,
)


@register_model(index=True, store=True, description="An answer section returned by the server.", embedded=True)
class DNSAnswer(HowlerEmbeddedModel):
    """An answer section returned by the server."""

    class_: optional(keyword(), alias="class", description="The class of DNS data contained in this resource record.")
    data: optional(keyword(), description="The data describing the resource.")
    name: optional(keyword(), description="The domain name to which this resource record pertains.")
    ttl: optional(
        integer(),
        description="The time interval in seconds that this "
        "resource record may be cached before it should be discarded.",
    )
    type: optional(keyword(), description="The type of data contained in this resource record.")


@register_model(
    index=True,
    store=True,
    description="An object encapsulating the question asked to the server.",
    embedded=True,
)
class DNSQuestion(HowlerEmbeddedModel):
    """An object encapsulating the question asked to the server."""

    class_: optional(keyword(), alias="class", description="The class of records being queried.")
    name: optional(keyword(), description="The name being queried.")
    registered_domain: optional(domain(), description="The highest registered domain, stripped of the subdomain.")
    subdomain: optional(keyword(), description="The subdomain is all of the labels under the registered_domain.")
    top_level_domain: optional(
        keyword(),
        description="The effective top level domain (eTLD), also known as the "
        "domain suffix, is the last part of the domain name.",
    )
    type: optional(keyword(), description="The type of record being queried.")


@register_model(index=True, store=True, description="Fields describing DNS queries and answers.", embedded=True)
class DNS(HowlerEmbeddedModel):
    """Fields describing DNS queries and answers."""

    answers: optional(
        list_field(compound(DNSAnswer)),
        description="An array containing an object for each answer section returned by the server.",
    )
    header_flags: optional(list_field(keyword()), description="Array of 2 letter DNS header flags.")
    id: optional(keyword(), description="The DNS packet identifier assigned by the program that generated the query.")
    op_code: optional(keyword(), description="The DNS operation code that specifies the kind of query in the message.")
    question: optional(compound(DNSQuestion), description="An object encapsulating the question asked to the server.")
    resolved_ip: optional(list_field(ip()), description="Array containing all IPs seen in answers.data.")
    response_code: optional(keyword(), description="The DNS response code.")
    type: optional(keyword(), description="The type of DNS event captured, query or answer.")
