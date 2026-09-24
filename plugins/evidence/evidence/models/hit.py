"""Typed extension declaration wiring the Evidence model onto the Hit document.

This declaration is applied when the datastore finalizes ``Hit`` at startup.
"""

from __future__ import annotations

from howler.models import compound, list_field, model_extensions
from howler.models.hit import Hit

from evidence.models.evidence import Evidence

PLUGIN_NAME = "evidence"


def declare_hit_extension() -> None:
    """Declare the ``evidence`` field extension for the ``Hit`` model.

    Safe to call multiple times; the underlying registry rejects a second declaration of the
    same field name only when it comes from a *different* plugin, so accidental double-import
    within the same plugin does not raise, but only the first successful declaration wins.
    """
    if "evidence" not in model_extensions.pending(Hit) and not model_extensions.is_finalized(Hit):
        model_extensions.declare(
            Hit,
            "evidence",
            list_field(compound(Evidence), default=[], description="A list of additional ECS objects."),
            plugin=PLUGIN_NAME,
        )
