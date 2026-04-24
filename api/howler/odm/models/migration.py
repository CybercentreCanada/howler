from datetime import datetime

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Record of a datastore migration execution.",
    id_field="migration_id",
)
class MigrationRecord(odm.Model):
    migration_id: str = odm.Keyword(description="The stable identifier of the migration.")
    status: str = odm.Enum({"running", "applied"}, description="The current migration execution status.")
    started_at: datetime = odm.Date(description="When execution of the migration started.")
    claim_id: str | None = odm.Keyword(
        optional=True,
        description="Opaque identifier for the execution that owns a running migration claim.",
    )
    applied_at: datetime | None = odm.Date(
        optional=True,
        description="When the migration completed successfully.",
    )
    affected_documents: int | None = odm.Integer(
        optional=True,
        min=0,
        description="The number of documents changed by the migration.",
    )
