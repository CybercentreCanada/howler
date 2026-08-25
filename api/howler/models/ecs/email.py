"""ECS email field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    email,
    integer,
    ip,
    keyword,
    list_field,
    optional,
    register_model,
)
from howler.models.ecs.hash import Hashes


@register_model(index=True, store=True, description="The email Address", embedded=True)
class Address(HowlerEmbeddedModel):
    """The email Address."""

    address: email(description="The email address.")


@register_model(index=True, store=True, description="Information about the file sent.", embedded=True)
class File(HowlerEmbeddedModel):
    """Information about the file sent."""

    extension: optional(keyword(), description="Attachment file extension, excluding the leading dot.")
    hash: optional(compound(Hashes), description="Hashes, usually file hashes.")
    mime_type: optional(keyword(), description="The MIME media type of the attachment.")
    name: optional(keyword(), description="Name of the attachment file including the file extension.")
    size: optional(integer(), description="Attachment file size in bytes.")


@register_model(
    index=True,
    store=True,
    description="An attachment file sent along with an email message.",
    embedded=True,
)
class Attachment(HowlerEmbeddedModel):
    """An attachment file sent along with an email message."""

    file: optional(compound(File), description="Information about the file sent.")


@register_model(index=True, store=True, description="Metadata about the parent email.", embedded=True)
class ParentEmail(HowlerEmbeddedModel):
    """Metadata about the parent email."""

    bcc: optional(compound(Address), description="The email address of BCC recipient.")
    cc: optional(compound(Address), description="The email address of CC recipient.")
    from_: optional(
        compound(Address),
        alias="from",
        description="The email address of the sender, typically from the RFC 5322 From: header field.",
    )
    message_id: optional(
        keyword(),
        description="Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message.",
    )
    origination_timestamp: optional(date(), description="The date and time the email message was composed.")
    subject: optional(keyword(), description="A brief summary of the topic of the message.")
    to: optional(compound(Address), description="The email address of recipient.")
    source: optional(ip(), description="The ip the email originated from.")
    destination: optional(ip(), description="The ip the email was sent to.")


@register_model(
    index=True,
    store=True,
    description="Event details relating to an email transaction.",
    embedded=True,
)
class Email(HowlerEmbeddedModel):
    """Event details relating to an email transaction."""

    attachments: optional(
        list_field(compound(Attachment)),
        description="A list of objects describing the attachment files sent along with an email message.",
    )
    bcc: optional(compound(Address), description="The email address of BCC recipient.")
    cc: optional(compound(Address), description="The email address of CC recipient.")
    content_type: optional(keyword(), description="Information about how the message is to be displayed.")
    delivery_timestamp: optional(
        date(), description="The date and time when the email message was received by the service or client."
    )
    direction: optional(
        keyword(), description="The direction of the message based on the sending and receiving domains."
    )
    from_: optional(
        compound(Address),
        alias="from",
        description="The email address of the sender, typically from the RFC 5322 From: header field.",
    )
    local_id: optional(
        keyword(), description="Unique identifier given to the email by the source that created the event."
    )
    message_id: optional(
        keyword(),
        description="Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message.",
    )
    origination_timestamp: optional(date(), description="The date and time the email message was composed.")
    reply_to: optional(
        compound(Address),
        description="The address that replies should be delivered to "
        "based on the value in the RFC 5322 Reply-To: header.",
    )
    sender: optional(
        compound(Address),
        description="Per RFC 5322, specifies the address responsible for the actual transmission of the message.",
    )
    subject: optional(keyword(), description="A brief summary of the topic of the message.")
    to: optional(compound(Address), description="The email address of recipient.")
    x_mailer: optional(
        keyword(),
        description="The name of the application that was used to draft and send the original email message.",
    )

    # Extra fields not defined in ECS but added for outline purposes
    parent: optional(compound(ParentEmail), description="Metadata about the parent email.")
