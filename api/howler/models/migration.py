"""Datastore migration execution record."""

from __future__ import annotations

from howler.models import HowlerESModel, date, enum, integer, keyword, register_model


@register_model(
    index=True,
    store=True,
    description="Record of a datastore migration execution.",
    id_field="migration_id",
)
class MigrationRecord(HowlerESModel):
    """Record of a datastore migration execution."""

    migration_id: keyword()
    """The stable identifier of the migration."""
    status: enum(values=["running", "applied"])
    """The current migration execution status."""
    started_at: date()
    """When execution of the migration started."""
    claim_id: keyword(optional=True)
    """Opaque identifier for the execution that owns a running migration claim."""
    applied_at: date(optional=True)
    """When the migration completed successfully."""
    affected_documents: integer(min=0, optional=True)
    """The number of documents changed by the migration."""
