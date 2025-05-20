from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The hash fields represent different bitwise hash algorithms and their values.",
)
class Hashes(odm.Model):
    md5 = odm.Optional(odm.MD5(description="MD5 hash."))
    sha1 = odm.Optional(odm.SHA1(description="SHA1 hash."))
    sha256 = odm.Optional(odm.SHA256(description="SHA256 hash."))
    sha384 = odm.Optional(odm.ValidatedKeyword(r"^[a-f0-9]{96}$", description="SHA384 hash."))
    sha512 = odm.Optional(odm.ValidatedKeyword(r"^[a-f0-9]{128}$", description="SHA512 hash."))
    ssdeep = odm.Optional(odm.SSDeepHash(description="SSDEEP hash."))
    tlsh = odm.Optional(odm.Keyword(description="TLSH hash."))
