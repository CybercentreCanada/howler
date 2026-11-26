"""ECS email field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, date, email, integer, ip, keyword, list_field, register_model
from howler.models.ecs.hash import Hashes


@register_model(index=True, store=True, description="The email Address", embedded=True)
class Address(HowlerEmbeddedModel):
    """The email Address."""

    address: email(description="The email address.")


@register_model(index=True, store=True, description="Information about the file sent.", embedded=True)
class File(HowlerEmbeddedModel):
    """Information about the file sent."""

    extension: keyword(optional=True, description="Attachment file extension, excluding the leading dot.")
    hash: compound(Hashes, optional=True, description="Hashes, usually file hashes.")
    mime_type: keyword(optional=True, description="The MIME media type of the attachment.")
    name: keyword(optional=True, description="Name of the attachment file including the file extension.")
    size: integer(optional=True, description="Attachment file size in bytes.")


@register_model(
    index=True,
    store=True,
    description="An attachment file sent along with an email message.",
    embedded=True,
)
class Attachment(HowlerEmbeddedModel):
    """An attachment file sent along with an email message."""

    file: compound(File, optional=True, description="Information about the file sent.")


@register_model(index=True, store=True, description="Metadata about the parent email.", embedded=True)
class ParentEmail(HowlerEmbeddedModel):
    """Metadata about the parent email."""

    bcc: compound(Address, optional=True, description="The email address of BCC recipient.")
    cc: compound(Address, optional=True, description="The email address of CC recipient.")
    from_: compound(
        Address,
        optional=True,
        alias="from",
        description="The email address of the sender, typically from the RFC 5322 From: header field.",
    )
    message_id: keyword(
        optional=True,
        description="Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message.",
    )
    origination_timestamp: date(optional=True, description="The date and time the email message was composed.")
    subject: keyword(optional=True, description="A brief summary of the topic of the message.")
    to: compound(Address, optional=True, description="The email address of recipient.")
    source: ip(optional=True, description="The ip the email originated from.")
    destination: ip(optional=True, description="The ip the email was sent to.")


@register_model(
    index=True,
    store=True,
    description="Event details relating to an email transaction.",
    embedded=True,
)
class Email(HowlerEmbeddedModel):
    """Event details relating to an email transaction."""

    attachments: list_field(
        compound(Attachment),
        optional=True,
        description="A list of objects describing the attachment files sent along with an email message.",
    )
    bcc: compound(Address, optional=True, description="The email address of BCC recipient.")
    cc: compound(Address, optional=True, description="The email address of CC recipient.")
    content_type: keyword(optional=True, description="Information about how the message is to be displayed.")
    delivery_timestamp: date(
        optional=True, description="The date and time when the email message was received by the service or client."
    )
    direction: keyword(
        optional=True, description="The direction of the message based on the sending and receiving domains."
    )
    from_: compound(
        Address,
        optional=True,
        alias="from",
        description="The email address of the sender, typically from the RFC 5322 From: header field.",
    )
    local_id: keyword(
        optional=True, description="Unique identifier given to the email by the source that created the event."
    )
    message_id: keyword(
        optional=True,
        description="Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message.",
    )
    origination_timestamp: date(optional=True, description="The date and time the email message was composed.")
    reply_to: compound(
        Address,
        optional=True,
        description="The address that replies should be delivered to "
        "based on the value in the RFC 5322 Reply-To: header.",
    )
    sender: compound(
        Address,
        optional=True,
        description="Per RFC 5322, specifies the address responsible for the actual transmission of the message.",
    )
    subject: keyword(optional=True, description="A brief summary of the topic of the message.")
    to: compound(Address, optional=True, description="The email address of recipient.")
    x_mailer: keyword(
        optional=True,
        description="The name of the application that was used to draft and send the original email message.",
    )

    # Extra fields not defined in ECS but added for outline purposes
    parent: compound(ParentEmail, optional=True, description="Metadata about the parent email.")
