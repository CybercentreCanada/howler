from howler import odm


@odm.model(index=True, store=True, description="Hit outline header.")
class Header(odm.Model):
    threat: str | None = odm.Keyword(description="The threat of the record.", optional=True)
    target: str | None = odm.Keyword(description="The target of the record.", optional=True)
    indicators: list[str] = odm.List(odm.Keyword(description="Indicators of the record."), default=[])
    summary: str | None = odm.Keyword(description="Summary of the record.", optional=True)
