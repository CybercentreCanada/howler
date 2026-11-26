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

    digest_algorithm: enum(values=["md5", "sha1", "sha256", "sha384", "sha512"], optional=True)
    """The hashing algorithm used to sign the process."""
    exists: boolean(optional=True)
    """Boolean to capture if a signature is present."""
    signing_id: keyword(optional=True)
    """The identifier used to sign the process."""
    status: keyword(optional=True)
    """Additional information about the certificate status."""
    subject_name: keyword(optional=True)
    """Subject name of the code signer."""
    team_id: keyword(optional=True)
    """The team identifier used to sign the process."""
    timestamp: date(optional=True)
    """Date and time when the code signature was generated and signed."""
    trusted: boolean(optional=True)
    """Stores the trust status of the certificate chain."""
    valid: boolean(optional=True)
    """Boolean to capture if the digital signature is verified against the binary content."""
