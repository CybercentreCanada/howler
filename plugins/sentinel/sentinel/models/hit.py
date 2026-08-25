"""Typed extension declaration wiring the Sentinel model onto the Hit document.

This is the Pydantic/DSL replacement for ``sentinel.odm.hit.modify_odm``'s
``target.add_namespace(...)`` call. It only *declares* the extension against the model
extension registry; actually finalizing ``Hit`` with this extension applied, and using the
finalized model at runtime, is Step 8 (datastore/consumer cutover) work.
"""

from __future__ import annotations

from howler.models import compound, model_extensions, optional
from howler.models.hit import Hit

from sentinel.models.sentinel import Sentinel

PLUGIN_NAME = "sentinel"


def declare_hit_extension() -> None:
    """Declare the ``sentinel`` field extension for the ``Hit`` model.

    Safe to call multiple times from within this plugin; only the first successful
    declaration is kept.
    """
    if "sentinel" not in model_extensions.pending(Hit) and not model_extensions.is_finalized(Hit):
        model_extensions.declare(
            Hit,
            "sentinel",
            optional(compound(Sentinel), description="Sentinel metadata associated with this alert"),
            plugin=PLUGIN_NAME,
        )
