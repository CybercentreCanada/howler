"""Datastore migration execution record."""

from __future__ import annotations

from typing import Annotated

from howler.models import Date, HowlerESModel, Integer, Keyword, enum, metadata, register_model


@register_model(
    index=True,
    store=True,
    description="Record of a datastore migration execution.",
    id_field="migration_id",
)
class MigrationRecord(HowlerESModel):
    """Record of a datastore migration execution."""

    migration_id: Keyword
    """The stable identifier of the migration."""
    status: enum(values=["running", "applied"])
    """The current migration execution status."""
    started_at: Date
    """When execution of the migration started."""
    claim_id: Keyword | None = None
    """Opaque identifier for the execution that owns a running migration claim."""
    applied_at: Date | None = None
    """When the migration completed successfully."""
    affected_documents: Annotated[Integer | None, metadata(ge=0)] = None
    """The number of documents changed by the migration."""
