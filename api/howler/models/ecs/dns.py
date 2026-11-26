"""ECS DNS field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, domain, integer, ip, keyword, register_model


@register_model(index=True, store=True, description="An answer section returned by the server.", embedded=True)
class DNSAnswer(HowlerEmbeddedModel):
    """An answer section returned by the server."""

    class_: keyword(optional=True, alias="class")
    """The class of DNS data contained in this resource record."""
    data: keyword(optional=True)
    """The data describing the resource."""
    name: keyword(optional=True)
    """The domain name to which this resource record pertains."""
    ttl: integer(optional=True)
    """The time interval in seconds that this resource record may be cached before it should be discarded."""
    type: keyword(optional=True)
    """The type of data contained in this resource record."""


@register_model(
    index=True,
    store=True,
    description="An object encapsulating the question asked to the server.",
    embedded=True,
)
class DNSQuestion(HowlerEmbeddedModel):
    """An object encapsulating the question asked to the server."""

    class_: keyword(optional=True, alias="class")
    """The class of records being queried."""
    name: keyword(optional=True)
    """The name being queried."""
    registered_domain: domain(optional=True)
    """The highest registered domain, stripped of the subdomain."""
    subdomain: keyword(optional=True)
    """The subdomain is all of the labels under the registered_domain."""
    top_level_domain: keyword(optional=True)
    """The effective top level domain (eTLD), also known as the domain suffix, is the last part of the domain name."""
    type: keyword(optional=True)
    """The type of record being queried."""


@register_model(index=True, store=True, description="Fields describing DNS queries and answers.", embedded=True)
class DNS(HowlerEmbeddedModel):
    """Fields describing DNS queries and answers."""

    answers: list[DNSAnswer] | None = None
    """An array containing an object for each answer section returned by the server."""
    header_flags: list[keyword()] | None = None
    """Array of 2 letter DNS header flags."""
    id: keyword(optional=True)
    """The DNS packet identifier assigned by the program that generated the query."""
    op_code: keyword(optional=True)
    """The DNS operation code that specifies the kind of query in the message."""
    question: DNSQuestion | None = None
    """An object encapsulating the question asked to the server."""
    resolved_ip: list[ip()] | None = None
    """Array containing all IPs seen in answers.data."""
    response_code: keyword(optional=True)
    """The DNS response code."""
    type: keyword(optional=True)
    """The type of DNS event captured, query or answer."""
