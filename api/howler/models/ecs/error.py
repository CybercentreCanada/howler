"""ECS error field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


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

    code: keyword(optional=True)
    """Identifier specific to the error."""
    message: keyword(optional=True)
    """Error message provided."""
