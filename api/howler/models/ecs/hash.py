"""ECS hash field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    keyword,
    md5,
    register_model,
    sha1,
    sha256,
    ssdeep_hash,
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

    md5: md5(optional=True)
    """MD5 hash."""
    sha1: sha1(optional=True)
    """SHA1 hash."""
    sha256: sha256(optional=True)
    """SHA256 hash."""
    sha384: validated_keyword(r"^[a-f0-9]{96}$", optional=True)
    """SHA384 hash."""
    sha512: validated_keyword(r"^[a-f0-9]{128}$", optional=True)
    """SHA512 hash."""
    ssdeep: ssdeep_hash(optional=True)
    """SSDEEP hash."""
    tlsh: keyword(optional=True)
    """TLSH hash."""
