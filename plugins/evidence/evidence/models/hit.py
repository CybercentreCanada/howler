"""Typed extension declaration wiring the Evidence model onto the Hit document.

This declaration is applied when the datastore finalizes ``Hit`` at startup.
"""

from __future__ import annotations

from howler.models import list_field, model_extensions
from howler.models.hit import Hit

from evidence.models.evidence import Evidence

PLUGIN_NAME = "evidence"


def declare_hit_extension() -> None:
    """Declare the ``evidence`` field once, before the ``Hit`` model is finalized."""
    model_extensions.declare(
        Hit,
        "evidence",
        list_field(Evidence, default=[], description="A list of additional ECS objects."),
        plugin=PLUGIN_NAME,
    )
