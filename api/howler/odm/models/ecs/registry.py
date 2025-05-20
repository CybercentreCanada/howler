from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Fields related to data written to Windows Registry.",
)
class RegistryData(odm.Model):
    bytes = odm.Optional(odm.Keyword(description="Original bytes written with base64 encoding."))
    strings = odm.Optional(odm.List(odm.Keyword(), description="Content when writing string types."))
    type = odm.Optional(odm.Keyword(description="Standard registry type for encoding contents."))


@odm.model(index=True, store=True, description="Fields related to Windows Registry operations.")
class Registry(odm.Model):
    data = odm.Optional(
        odm.Compound(
            RegistryData,
            description="Fields related to data written to Windows Registry.",
        )
    )
    hive = odm.Optional(odm.Keyword(description="Abbreviated name for the hive."))
    key = odm.Optional(odm.Keyword(description="Hive-relative path of keys."))
    path = odm.Optional(odm.Keyword(description="Full path, including hive, key and value."))
    value = odm.Optional(odm.Keyword(description="Name of the value written."))
