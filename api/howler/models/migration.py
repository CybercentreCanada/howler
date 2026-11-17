"""Datastore migration execution record."""

from __future__ import annotations

from howler.models import HowlerESModel, date, enum, integer, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="Record of a datastore migration execution.",
    id_field="migration_id",
)
class MigrationRecord(HowlerESModel):
    """Record of a datastore migration execution."""

    migration_id: keyword(description="The stable identifier of the migration.")
    status: enum(values=["running", "applied"], description="The current migration execution status.")
    started_at: date(description="When execution of the migration started.")
    claim_id: optional(
        keyword(),
        description="Opaque identifier for the execution that owns a running migration claim.",
    )
    applied_at: optional(date(), description="When the migration completed successfully.")
    affected_documents: optional(integer(min=0), description="The number of documents changed by the migration.")
