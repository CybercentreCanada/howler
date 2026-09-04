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
                    "if (ctx._source.containsKey('owner_id') && ctx._source.owner_id != null && "
                    "(!ctx._source.containsKey('owner') || ctx._source.owner == null)) { "
                    "ctx._source.owner = ctx._source.owner_id; "
                    "ctx._source.remove('owner_id'); "
                    "} else { ctx.op = 'noop'; }"
                ),
            },
            query={
                "bool": {
                    "filter": [{"exists": {"field": "owner_id"}}],
                    "must_not": [{"exists": {"field": "owner"}}],
                }
            },
            refresh="wait_for",
        )
        return int(result.get("updated", 0))
