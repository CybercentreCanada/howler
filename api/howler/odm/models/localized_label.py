# mypy: ignore-errors

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class LocalizedLabel(odm.Model):
    en: str = odm.Text(description="The english localization of a label")
    fr: str = odm.Text(description="The french localization of a label")
