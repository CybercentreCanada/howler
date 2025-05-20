from howler import odm


@odm.model(
    index=True,
    store=True,
    description="These fields contain Windows Portable Executable (PE) metadata.",
)
class PE(odm.Model):
    architecture = odm.Optional(odm.Keyword(description="CPU architecture target for the file."))
    company = odm.Optional(odm.Keyword(description="Internal company name of the file, provided at compile-time."))
    description = odm.Optional(odm.Keyword(description="Internal description of the file, provided at compile-time."))
    file_version = odm.Optional(odm.Keyword(description="Internal version of the file, provided at compile-time."))
    imphash = odm.Optional(odm.Keyword(description="A hash of the imports in a PE file."))
    original_file_name = odm.Optional(odm.Keyword(description="Internal name of the file, provided at compile-time."))
    pehash = odm.Optional(odm.Keyword(description="A hash of the PE header and data from one or more PE sections."))
    product = odm.Optional(odm.Keyword(description="Internal product name of the file, provided at compile-time."))
