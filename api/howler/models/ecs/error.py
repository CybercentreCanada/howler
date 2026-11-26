"""ECS error field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description=(
        "These fields can represent errors of any kind. Use them for errors that happen while "
        "fetching events or in cases where the event itself contains an error."
    ),
    embedded=True,
)
class Error(HowlerEmbeddedModel):
    """These fields can represent errors of any kind."""

    code: Keyword | None = None
    """Identifier specific to the error."""
    message: Keyword | None = None
    """Error message provided."""
