"""Localized label model."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, register_model, text


@register_model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
    embedded=True,
)
class LocalizedLabel(HowlerEmbeddedModel):
    """A label localized to English and French."""

    en: text(description="The english localization of a label")
    fr: text(description="The french localization of a label")
