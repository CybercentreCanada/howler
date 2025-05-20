from howler import odm


@odm.model(index=True, store=True, description="An answer section returned by the server.")
class DNSAnswer(odm.Model):
    class_ = odm.Optional(odm.Keyword(description="The class of DNS data contained in this resource record."))
    data = odm.Optional(odm.Keyword(description="The data describing the resource."))
    name = odm.Optional(odm.Keyword(description="The domain name to which this resource record pertains."))
    ttl = odm.Optional(
        odm.Integer(
            description="The time interval in seconds that this "
            "resource record may be cached before it should be discarded."
        )
    )
    type = odm.Optional(odm.Keyword(description="The type of data contained in this resource record."))


@odm.model(
    index=True,
    store=True,
    description="An object encapsulating the question asked to the server.",
)
class DNSQuestion(odm.Model):
    class_ = odm.Optional(odm.Keyword(description="The class of records being queried."))
    name = odm.Optional(odm.Keyword(description="The name being queried."))
    registered_domain = odm.Optional(
        odm.Domain(description="The highest registered domain, stripped of the subdomain.")
    )
    subdomain = odm.Optional(odm.Keyword(description="The subdomain is all of the labels under the registered_domain."))
    top_level_domain = odm.Optional(
        odm.Keyword(
            description="The effective top level domain (eTLD), also known as the "
            "domain suffix, is the last part of the domain name."
        )
    )
    type = odm.Optional(odm.Keyword(description="The type of record being queried."))


@odm.model(index=True, store=True, description="Fields describing DNS queries and answers.")
class DNS(odm.Model):
    answers = odm.Optional(
        odm.List(
            odm.Compound(DNSAnswer),
            description="An array containing an object for each answer section returned by the server.",
        )
    )
    header_flags = odm.Optional(odm.List(odm.Keyword(), description="Array of 2 letter DNS header flags."))
    id = odm.Optional(
        odm.Keyword(description="The DNS packet identifier assigned by the program that generated the query.")
    )
    op_code = odm.Optional(
        odm.Keyword(description="The DNS operation code that specifies the kind of query in the message.")
    )
    question = odm.Optional(
        odm.Compound(
            DNSQuestion,
            description="An object encapsulating the question asked to the server.",
        )
    )
    resolved_ip = odm.Optional(odm.List(odm.IP(), description="Array containing all IPs seen in answers.data."))
    response_code = odm.Optional(odm.Keyword(description="The DNS response code."))
    type = odm.Optional(odm.Keyword(description="The type of DNS event captured, query or answer."))
