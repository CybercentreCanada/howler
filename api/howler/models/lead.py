"""Lead model, used by dossiers."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, json_field, keyword, optional, register_model, text
from howler.models.localized_label import LocalizedLabel


@register_model(
    index=False,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
    embedded=True,
)
class Lead(HowlerEmbeddedModel):
    """The dossier object stores individual tabs/fields for a given alert."""

    icon: optional(text(), description="An optional icon to use in the tab display for this dossier.")
    label: compound(LocalizedLabel, description="Labels for the lead in the UI.")
    format: keyword(description="The format of the lead.")
    content: text(
        description="The data for the content. Could be a link, raw markdown text, or other valid lead format."
    )
    metadata: optional(json_field(), description="Metadata associated with this dossier. Use varies based on format.")
