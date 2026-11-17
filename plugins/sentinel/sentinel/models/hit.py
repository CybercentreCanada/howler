"""Typed extension declaration wiring the Sentinel model onto the Hit document.

This declaration is applied when the datastore finalizes ``Hit`` at startup.
"""

from __future__ import annotations

from howler.models import compound, model_extensions, optional
from howler.models.hit import Hit

from sentinel.models.sentinel import Sentinel

PLUGIN_NAME = "sentinel"


def declare_hit_extension() -> None:
    """Declare the ``sentinel`` field once, before the ``Hit`` model is finalized."""
    model_extensions.declare(
        Hit,
        "sentinel",
        optional(compound(Sentinel), description="Sentinel metadata associated with this alert"),
        plugin=PLUGIN_NAME,
    )
