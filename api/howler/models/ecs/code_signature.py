"""ECS code signature field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, boolean, date, enum, keyword, register_model


@register_model(
    index=True,
    store=True,
    description="These fields contain information about binary code signatures.",
    embedded=True,
)
class CodeSignature(HowlerEmbeddedModel):
    """These fields contain information about binary code signatures."""

    digest_algorithm: enum(
        values=["md5", "sha1", "sha256", "sha384", "sha512"],
        optional=True,
        description="The hashing algorithm used to sign the process.",
    )
    exists: boolean(optional=True, description="Boolean to capture if a signature is present.")
    signing_id: keyword(optional=True, description="The identifier used to sign the process.")
    status: keyword(optional=True, description="Additional information about the certificate status.")
    subject_name: keyword(optional=True, description="Subject name of the code signer.")
    team_id: keyword(optional=True, description="The team identifier used to sign the process.")
    timestamp: date(optional=True, description="Date and time when the code signature was generated and signed.")
    trusted: boolean(optional=True, description="Stores the trust status of the certificate chain.")
    valid: boolean(
        optional=True, description="Boolean to capture if the digital signature is verified against the binary content."
    )
