"""ECS hash field set."""

from __future__ import annotations

from howler.models import (
    MD5,
    SHA1,
    SHA256,
    HowlerEmbeddedModel,
    Keyword,
    SSDeepHash,
    register_model,
    validated_keyword,
)


@register_model(
    index=True,
    store=True,
    description="The hash fields represent different bitwise hash algorithms and their values.",
    embedded=True,
)
class Hashes(HowlerEmbeddedModel):
    """The hash fields represent different bitwise hash algorithms and their values."""

    md5: MD5 | None = None
    """MD5 hash."""
    sha1: SHA1 | None = None
    """SHA1 hash."""
    sha256: SHA256 | None = None
    """SHA256 hash."""
    sha384: validated_keyword(r"^[a-f0-9]{96}$", optional=True)
    """SHA384 hash."""
    sha512: validated_keyword(r"^[a-f0-9]{128}$", optional=True)
    """SHA512 hash."""
    ssdeep: SSDeepHash | None = None
    """SSDEEP hash."""
    tlsh: Keyword | None = None
    """TLSH hash."""
