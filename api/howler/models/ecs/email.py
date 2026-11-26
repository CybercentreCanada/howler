"""ECS email field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import IP, Date, HowlerEmbeddedModel, Integer, Keyword, metadata, register_model
from howler.models import Email as EmailField
from howler.models.ecs.hash import Hashes


@register_model(index=True, store=True, description="The email Address", embedded=True)
class Address(HowlerEmbeddedModel):
    """The email Address."""

    address: EmailField
    """The email address."""


@register_model(index=True, store=True, description="Information about the file sent.", embedded=True)
class File(HowlerEmbeddedModel):
    """Information about the file sent."""

    extension: Keyword | None = None
    """Attachment file extension, excluding the leading dot."""
    hash: Hashes | None = None
    """Hashes, usually file hashes."""
    mime_type: Keyword | None = None
    """The MIME media type of the attachment."""
    name: Keyword | None = None
    """Name of the attachment file including the file extension."""
    size: Integer | None = None
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
    from_: Annotated[Address | None, metadata(alias="from")] = None
    """The email address of the sender, typically from the RFC 5322 From: header field."""
    message_id: Keyword | None = None
    """Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message."""
    origination_timestamp: Date | None = None
    """The date and time the email message was composed."""
    subject: Keyword | None = None
    """A brief summary of the topic of the message."""
    to: Address | None = None
    """The email address of recipient."""
    source: IP | None = None
    """The ip the email originated from."""
    destination: IP | None = None
    """The ip the email was sent to."""


@register_model(
    index=True,
    store=True,
    description="Event details relating to an email transaction.",
    embedded=True,
)
class Email(HowlerEmbeddedModel):
    """Event details relating to an email transaction."""

    attachments: list[Attachment] | None = None
    """A list of objects describing the attachment files sent along with an email message."""
    bcc: Address | None = None
    """The email address of BCC recipient."""
    cc: Address | None = None
    """The email address of CC recipient."""
    content_type: Keyword | None = None
    """Information about how the message is to be displayed."""
    delivery_timestamp: Date | None = None
    """The date and time when the email message was received by the service or client."""
    direction: Keyword | None = None
    """The direction of the message based on the sending and receiving domains."""
    from_: Annotated[Address | None, metadata(alias="from")] = None
    """The email address of the sender, typically from the RFC 5322 From: header field."""
    local_id: Keyword | None = None
    """Unique identifier given to the email by the source that created the event."""
    message_id: Keyword | None = None
    """Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message."""
    origination_timestamp: Date | None = None
    """The date and time the email message was composed."""
    reply_to: Address | None = None
    """The address that replies should be delivered to based on the value in the RFC 5322 Reply-To: header."""
    sender: Address | None = None
    """Per RFC 5322, specifies the address responsible for the actual transmission of the message."""
    subject: Keyword | None = None
    """A brief summary of the topic of the message."""
    to: Address | None = None
    """The email address of recipient."""
    x_mailer: Keyword | None = None
    """The name of the application that was used to draft and send the original email message."""

    # Extra fields not defined in ECS but added for outline purposes
    parent: ParentEmail | None = None
    """Metadata about the parent email."""
