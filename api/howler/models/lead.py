"""Lead model, used by dossiers."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Json, Keyword, Text, register_model
from howler.models.localized_label import LocalizedLabel


@register_model(
    index=False,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
    embedded=True,
)
class Lead(HowlerEmbeddedModel):
    """The dossier object stores individual tabs/fields for a given alert."""

    icon: Text | None = None
    """An optional icon to use in the tab display for this dossier."""
    label: LocalizedLabel
    """Labels for the lead in the UI."""
    format: Keyword
    """The format of the lead."""
    content: Text
    """The data for the content. Could be a link, raw markdown text, or other valid lead format."""
    metadata: Json | None = None
    """Metadata associated with this dossier. Use varies based on format."""
