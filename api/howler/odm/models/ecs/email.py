from howler import odm
from howler.odm.models.ecs.hash import Hashes


@odm.model(index=True, store=True, description="The email Address")
class Address(odm.Model):
    address = odm.Email(description="The email address.")


@odm.model(index=True, store=True, description="Information about the file sent.")
class File(odm.Model):
    extension = odm.Optional(odm.Keyword(description="Attachment file extension, excluding the leading dot."))
    hash = odm.Optional(odm.Compound(Hashes, description="Hashes, usually file hashes."))
    mime_type = odm.Optional(odm.Keyword(description="The MIME media type of the attachment."))
    name = odm.Optional(odm.Keyword(description="Name of the attachment file including the file extension."))
    size = odm.Optional(odm.Integer(description="Attachment file size in bytes."))


@odm.model(
    index=True,
    store=True,
    description="An attachment file sent along with an email message.",
)
class Attachment(odm.Model):
    file = odm.Optional(odm.Compound(File, description="Information about the file sent."))


@odm.model(
    index=True,
    store=True,
    description="Metadata about the parent email.",
)
class ParentEmail(odm.Model):
    bcc = odm.Optional(odm.Compound(Address, description="The email address of BCC recipient."))
    cc = odm.Optional(odm.Compound(Address, description="The email address of CC recipient."))
    from_ = odm.Optional(
        odm.Compound(
            Address,
            description="The email address of the sender, typically " "from the RFC 5322 From: header field.",
        )
    )
    message_id = odm.Optional(
        odm.Keyword(
            description="Identifier from the RFC 5322 Message-ID: email header "
            "that refers to a particular email message."
        )
    )
    origination_timestamp = odm.Optional(odm.Date(description="The date and time the email message was composed."))
    subject = odm.Optional(odm.Keyword(description="A brief summary of the topic of the message."))
    to = odm.Optional(odm.Compound(Address, description="The email address of recipient."))
    source = odm.Optional(odm.IP(description="The ip the email originated from."))
    destination = odm.Optional(odm.IP(description="The ip the email was sent to."))


@odm.model(
    index=True,
    store=True,
    description="Event details relating to an email transaction.",
)
class Email(odm.Model):
    attachments = odm.Optional(
        odm.List(
            odm.Compound(
                Attachment,
                description="A list of objects describing the attachment files sent along with an email message.",
            )
        )
    )
    bcc = odm.Optional(odm.Compound(Address, description="The email address of BCC recipient."))
    cc = odm.Optional(odm.Compound(Address, description="The email address of CC recipient."))
    content_type = odm.Optional(odm.Keyword(description="Information about how the message is to be displayed."))
    delivery_timestamp = odm.Optional(
        odm.Date(description="The date and time when the email message " "was received by the service or client.")
    )
    direction = odm.Optional(
        odm.Keyword(description="The direction of the message based on the " "sending and receiving domains.")
    )
    from_ = odm.Optional(
        odm.Compound(
            Address,
            description="The email address of the sender, typically " "from the RFC 5322 From: header field.",
        )
    )
    local_id = odm.Optional(
        odm.Keyword(description="Unique identifier given to the email by the source " "that created the event.")
    )
    message_id = odm.Optional(
        odm.Keyword(
            description="Identifier from the RFC 5322 Message-ID: email header "
            "that refers to a particular email message."
        )
    )
    origination_timestamp = odm.Optional(odm.Date(description="The date and time the email message was composed."))
    reply_to = odm.Optional(
        odm.Compound(
            Address,
            description="The address that replies should be delivered to "
            "based on the value in the RFC 5322 Reply-To: header.",
        )
    )
    sender = odm.Optional(
        odm.Compound(
            Address,
            description="Per RFC 5322, specifies the address responsible for "
            "the actual transmission of the message.",
        )
    )
    subject = odm.Optional(odm.Keyword(description="A brief summary of the topic of the message."))
    to = odm.Optional(odm.Compound(Address, description="The email address of recipient."))
    x_mailer = odm.Optional(
        odm.Keyword(
            description="The name of the application that was used to draft " "and send the original email message."
        )
    )

    # Extra fields not defined in ECS but added for outline purposes
    parent = odm.Optional(
        odm.Compound(
            ParentEmail,
            description="Metadata about the parent email.",
        )
    )
