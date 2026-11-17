"""ECS code signature field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, boolean, date, enum, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="These fields contain information about binary code signatures.",
    embedded=True,
)
class CodeSignature(HowlerEmbeddedModel):
    """These fields contain information about binary code signatures."""

    digest_algorithm: optional(
        enum(values=["md5", "sha1", "sha256", "sha384", "sha512"]),
        description="The hashing algorithm used to sign the process.",
    )
    exists: optional(boolean(), description="Boolean to capture if a signature is present.")
    signing_id: optional(keyword(), description="The identifier used to sign the process.")
    status: optional(keyword(), description="Additional information about the certificate status.")
    subject_name: optional(keyword(), description="Subject name of the code signer.")
    team_id: optional(keyword(), description="The team identifier used to sign the process.")
    timestamp: optional(date(), description="Date and time when the code signature was generated and signed.")
    trusted: optional(boolean(), description="Stores the trust status of the certificate chain.")
    valid: optional(
        boolean(),
        description="Boolean to capture if the digital signature is verified against the binary content.",
    )
