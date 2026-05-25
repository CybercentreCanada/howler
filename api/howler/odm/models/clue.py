from howler import odm


@odm.model(index=True, store=True, description="A mapping from a specific field in Howler to a clue type")
class TypeMap(odm.Model):
    field: str = odm.Keyword(description="The field whose clue type to override")
    type: str = odm.Keyword(description="The clue type to override the field as")


@odm.model(index=True, store=True, description="Clue-specific overrides for this alert")
class Clue(odm.Model):
    types: list[TypeMap] = odm.List(
        odm.Compound(TypeMap),
        default=[],
        description="A mapping of howler fields to clue types to augment/override system configuration.",
    )
