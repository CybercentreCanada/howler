"""ECS DNS field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import IP, Domain, HowlerEmbeddedModel, Integer, Keyword, metadata, register_model


@register_model(index=True, store=True, description="An answer section returned by the server.", embedded=True)
class DNSAnswer(HowlerEmbeddedModel):
    """An answer section returned by the server."""

    class_: Annotated[Keyword | None, metadata(alias="class")] = None
    """The class of DNS data contained in this resource record."""
    data: Keyword | None = None
    """The data describing the resource."""
    name: Keyword | None = None
    """The domain name to which this resource record pertains."""
    ttl: Integer | None = None
    """The time interval in seconds that this resource record may be cached before it should be discarded."""
    type: Keyword | None = None
    """The type of data contained in this resource record."""


@register_model(
    index=True,
    store=True,
    description="An object encapsulating the question asked to the server.",
    embedded=True,
)
class DNSQuestion(HowlerEmbeddedModel):
    """An object encapsulating the question asked to the server."""

    class_: Annotated[Keyword | None, metadata(alias="class")] = None
    """The class of records being queried."""
    name: Keyword | None = None
    """The name being queried."""
    registered_domain: Domain | None = None
    """The highest registered domain, stripped of the subdomain."""
    subdomain: Keyword | None = None
    """The subdomain is all of the labels under the registered_domain."""
    top_level_domain: Keyword | None = None
    """The effective top level domain (eTLD), also known as the domain suffix, is the last part of the domain name."""
    type: Keyword | None = None
    """The type of record being queried."""


@register_model(index=True, store=True, description="Fields describing DNS queries and answers.", embedded=True)
class DNS(HowlerEmbeddedModel):
    """Fields describing DNS queries and answers."""

    answers: list[DNSAnswer] | None = None
    """An array containing an object for each answer section returned by the server."""
    header_flags: list[Keyword] | None = None
    """Array of 2 letter DNS header flags."""
    id: Keyword | None = None
    """The DNS packet identifier assigned by the program that generated the query."""
    op_code: Keyword | None = None
    """The DNS operation code that specifies the kind of query in the message."""
    question: DNSQuestion | None = None
    """An object encapsulating the question asked to the server."""
    resolved_ip: list[IP] | None = None
    """Array containing all IPs seen in answers.data."""
    response_code: Keyword | None = None
    """The DNS response code."""
    type: Keyword | None = None
    """The type of DNS event captured, query or answer."""
