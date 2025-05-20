from howler import odm


@odm.model(
    index=True,
    store=True,
    description="These fields contain information about binary code signatures.",
)
class CodeSignature(odm.Model):
    digest_algorithm = odm.Optional(
        odm.Enum(
            values=["md5", "sha1", "sha256", "sha384", "sha512"],
            description="The hashing algorithm used to sign the process.",
        )
    )
    exists = odm.Optional(odm.Boolean(description="Boolean to capture if a signature is present."))
    signing_id = odm.Optional(odm.Keyword(description="The identifier used to sign the process."))
    status = odm.Optional(odm.Keyword(description="Additional information about the certificate status."))
    subject_name = odm.Optional(odm.Keyword(description="Subject name of the code signer."))
    team_id = odm.Optional(odm.Keyword(description="The team identifier used to sign the process."))
    timestamp = odm.Optional(odm.Date(description="Date and time when the code signature was generated and signed."))
    trusted = odm.Optional(odm.Boolean(description="Stores the trust status of the certificate chain."))
    valid = odm.Optional(
        odm.Boolean(
            description="Boolean to capture if the digital signature" " is verified against the binary content."
        )
    )
