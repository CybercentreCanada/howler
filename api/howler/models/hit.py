"""Hit model — Howler's primary alert document."""

from __future__ import annotations

from howler.models import compound, register_model
from howler.models.howler_data import HowlerData
from howler.models.record import Record


@register_model(
    index=True,
    store=True,
    description="Howler Outline schema which is an extended version of Elastic Common Schema (ECS)",
    id_field="howler.id",
)
class Hit(Record):
    """Howler Outline schema which is an extended version of Elastic Common Schema (ECS)."""

    # Howler extended fields. Deviates from ECS
    howler: compound(
        HowlerData,
        description="Howler specific definition of the hit that matches the outline.",
        reference="https://confluence.devtools.cse-cst.gc.ca/display/~jjgalar/Hit+Schema",
    )
