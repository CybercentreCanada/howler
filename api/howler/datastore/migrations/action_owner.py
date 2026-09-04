from howler.datastore.exceptions import DataStoreException
from howler.datastore.migrations.base import Migration


class ActionOwnerMigration(Migration):
    """Move the legacy action owner field to the current ownership field."""

    migration_id = "action-owner-id-to-owner"

    def run(self, datastore) -> int:
        collection = datastore.action
        result = collection._update_async(
            collection.name,
            script={
                "lang": "painless",
                "source": (
                    "if (ctx._source.containsKey('owner_id') && ctx._source.owner_id != null) { "
                    "if (!ctx._source.containsKey('owner') || ctx._source.owner == null) { "
                    "ctx._source.owner = ctx._source.owner_id; } "
                    "ctx._source.remove('owner_id'); "
                    "} else { ctx.op = 'noop'; }"
                ),
            },
            query={
                "bool": {
                    "filter": [{"exists": {"field": "owner_id"}}],
                }
            },
            refresh=True,
        )
        updated = result.get("updated")
        if isinstance(updated, bool) or not isinstance(updated, int) or updated < 0:
            raise DataStoreException("Action-owner migration received an invalid update count from Elasticsearch.")
        return updated


class ActionOwnerLegacyFieldCleanupMigration(ActionOwnerMigration):
    """Clean legacy owner fields in deployments where the original migration already ran."""

    migration_id = "action-owner-id-legacy-field-cleanup"
