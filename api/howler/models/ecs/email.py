"""ECS email field set."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from howler.models import HowlerEmbeddedModel, date, email, integer, ip, keyword, list_field, register_model
from howler.models.ecs.hash import Hashes


@register_model(index=True, store=True, description="The email Address", embedded=True)
class Address(HowlerEmbeddedModel):
    """The email Address."""

    address: email()
    """The email address."""


@register_model(index=True, store=True, description="Information about the file sent.", embedded=True)
class File(HowlerEmbeddedModel):
    """Information about the file sent."""

    extension: keyword(optional=True)
    """Attachment file extension, excluding the leading dot."""
    hash: Hashes | None = None
    """Hashes, usually file hashes."""
    mime_type: keyword(optional=True)
    """The MIME media type of the attachment."""
    name: keyword(optional=True)
    """Name of the attachment file including the file extension."""
    size: integer(optional=True)
    """Attachment file size in bytes."""


@register_model(
    index=True,
    store=True,
    description="An attachment file sent along with an email message.",
    embedded=True,
)
class Attachment(HowlerEmbeddedModel):
    """An attachment file sent along with an email message."""

    file: File | None = None
    """Information about the file sent."""


@register_model(index=True, store=True, description="Metadata about the parent email.", embedded=True)
class ParentEmail(HowlerEmbeddedModel):
    """Metadata about the parent email."""

    bcc: Address | None = None
    """The email address of BCC recipient."""
    cc: Address | None = None
    """The email address of CC recipient."""
    from_: Annotated[Address | None, Field(alias="from")] = None
    """The email address of the sender, typically from the RFC 5322 From: header field."""
    message_id: keyword(optional=True)
    """Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message."""
    origination_timestamp: date(optional=True)
    """The date and time the email message was composed."""
    subject: keyword(optional=True)
    """A brief summary of the topic of the message."""
    to: Address | None = None
    """The email address of recipient."""
    source: ip(optional=True)
    """The ip the email originated from."""
    destination: ip(optional=True)
    """The ip the email was sent to."""


@register_model(
    index=True,
    store=True,
    description="Event details relating to an email transaction.",
    embedded=True,
)
class Email(HowlerEmbeddedModel):
    """Event details relating to an email transaction."""

    attachments: list_field(Attachment, optional=True)
    """A list of objects describing the attachment files sent along with an email message."""
    bcc: Address | None = None
    """The email address of BCC recipient."""
    cc: Address | None = None
    """The email address of CC recipient."""
    content_type: keyword(optional=True)
    """Information about how the message is to be displayed."""
    delivery_timestamp: date(optional=True)
    """The date and time when the email message was received by the service or client."""
    direction: keyword(optional=True)
    """The direction of the message based on the sending and receiving domains."""
    from_: Annotated[Address | None, Field(alias="from")] = None
    """The email address of the sender, typically from the RFC 5322 From: header field."""
    local_id: keyword(optional=True)
    """Unique identifier given to the email by the source that created the event."""
    message_id: keyword(optional=True)
    """Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message."""
    origination_timestamp: date(optional=True)
    """The date and time the email message was composed."""
    reply_to: Address | None = None
    """The address that replies should be delivered to based on the value in the RFC 5322 Reply-To: header."""
    sender: Address | None = None
    """Per RFC 5322, specifies the address responsible for the actual transmission of the message."""
    subject: keyword(optional=True)
    """A brief summary of the topic of the message."""
    to: Address | None = None
    """The email address of recipient."""
    x_mailer: keyword(optional=True)
    """The name of the application that was used to draft and send the original email message."""

    # Extra fields not defined in ECS but added for outline purposes
    parent: ParentEmail | None = None
    """Metadata about the parent email."""
