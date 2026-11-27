"""Localized label model."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Text, register_model


@register_model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
    embedded=True,
)
class LocalizedLabel(HowlerEmbeddedModel):
    """A label localized to English and French."""

    en: Text
    """The english localization of a label"""
    fr: Text
    """The french localization of a label"""
