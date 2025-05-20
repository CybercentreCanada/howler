from howler import odm


@odm.model(index=True, store=True, description="Defines the body of a request/response.")
class Body(odm.Model):
    bytes = odm.Optional(odm.Integer(description="Size in bytes of the body."))
    content = odm.Optional(odm.Keyword(description="The full HTTP body."))


@odm.model(index=True, store=True, description="These fields can represent errors of any kind.")
class Request(odm.Model):
    body = odm.Optional(odm.Compound(Body, description="Defines the body of a request"))
    bytes = odm.Optional(odm.Integer(description="Total size in bytes of the request (body and headers)."))
    id = odm.Optional(
        odm.Keyword(
            description="A unique identifier for each HTTP request to correlate logs between clients "
            "and servers in transactions."
        )
    )
    method = odm.Optional(odm.Keyword(description="HTTP request method."))
    mime_type = odm.Optional(odm.Keyword(description="Mime type of the body of the request."))
    referrer = odm.Optional(odm.Keyword(description="Referrer for this HTTP request."))


@odm.model(index=True, store=True, description="These fields can represent errors of any kind.")
class Response(odm.Model):
    body = odm.Optional(odm.Compound(Body, description="Defines the body of a response"))
    bytes = odm.Optional(odm.Integer(description="Total size in bytes of the request (body and headers)."))
    mime_type = odm.Optional(odm.Keyword(description="Mime type of the body of the request."))
    status_code = odm.Optional(odm.Integer(description="HTTP response status code."))


@odm.model(index=True, store=True, description="These fields can represent errors of any kind.")
class HTTP(odm.Model):
    request = odm.Optional(odm.Compound(Request, description="Request data."))
    response = odm.Optional(odm.Compound(Response, description="Response data."))
    version = odm.Optional(odm.Keyword(description="HTTP version."))
