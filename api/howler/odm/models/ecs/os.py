from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The OS fields contain information about the operating system.",
)
class OS(odm.Model):
    family = odm.Optional(odm.Keyword(description="OS family (such as redhat, debian, freebsd, windows)."))
    full = odm.Optional(odm.Keyword(description="Operating system name, including the version or code name."))
    kernel = odm.Optional(odm.Keyword(description="Operating system kernel version as a raw string."))
    name = odm.Optional(odm.Keyword(description="Operating system name, without the version."))
    platform = odm.Optional(odm.Keyword(description="Operating system platform (such centos, ubuntu, windows)."))
    type = odm.Optional(
        odm.Keyword(
            description="Use the os.type field to categorize the operating "
            "system into one of the broad commercial families."
        )
    )
    version = odm.Optional(odm.Keyword(description="Operating system version as a raw string."))
