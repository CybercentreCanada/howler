from howler import odm


@odm.model(
    index=True,
    store=True,
    description=(
        "These fields can represent errors of any kind. Use them for errors that happen while "
        "fetching events or in cases where the event itself contains an error."
    ),
)
class Error(odm.Model):
    code = odm.Optional(odm.Keyword(description="Identifier specific to the error."))
    message = odm.Optional(odm.Keyword(description="Error message provided."))
