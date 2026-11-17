"""ECS hash field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    keyword,
    md5,
    optional,
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

    md5: optional(md5(), description="MD5 hash.")
    sha1: optional(sha1(), description="SHA1 hash.")
    sha256: optional(sha256(), description="SHA256 hash.")
    sha384: optional(validated_keyword(r"^[a-f0-9]{96}$"), description="SHA384 hash.")
    sha512: optional(validated_keyword(r"^[a-f0-9]{128}$"), description="SHA512 hash.")
    ssdeep: optional(ssdeep_hash(), description="SSDEEP hash.")
    tlsh: optional(keyword(), description="TLSH hash.")
