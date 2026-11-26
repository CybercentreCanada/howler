"""ECS code signature field set."""

from __future__ import annotations

from howler.models import Boolean, Date, HowlerEmbeddedModel, Keyword, enum, register_model


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
    exists: Boolean | None = None
    """Boolean to capture if a signature is present."""
    signing_id: Keyword | None = None
    """The identifier used to sign the process."""
    status: Keyword | None = None
    """Additional information about the certificate status."""
    subject_name: Keyword | None = None
    """Subject name of the code signer."""
    team_id: Keyword | None = None
    """The team identifier used to sign the process."""
    timestamp: Date | None = None
    """Date and time when the code signature was generated and signed."""
    trusted: Boolean | None = None
    """Stores the trust status of the certificate chain."""
    valid: Boolean | None = None
    """Boolean to capture if the digital signature is verified against the binary content."""
