# Migration Guides

## Migrating Howler 2.12.0 to 3.0.0

This guide will walk you through the process of migrating your Howler installation from version 2.12.0 to 3.0.0.
Version 3.0.0 introduces breaking schema changes that require a complete reindexing of your Elasticsearch data.

### ⚠️ Important Notice

**This is a BREAKING CHANGE migration that requires complete data reindexing.**

- **Downtime Required**: Your Howler instance will be unavailable during the migration process
- **Data Backup**: Create full backups of your Elasticsearch cluster before proceeding

### What's Changed in 3.0.0

#### Schema Changes

Version 3.0.0 introduces several important schema modifications:

1. **New Long Data Type**: Introduction of `odm.Long` for handling large integer values with proper Elasticsearch long
    datatype mapping
2. **Byte Count Field Migration**: `source.bytes` and `destination.bytes` fields migrated from `Integer` to `Long` type
3. **Case-Insensitive Keywords**: Analytic and view titles/names migrated to `odm.CaseInsensitiveKeyword` for improved
    search functionality
4. **Outline Field Changes**: Hit outline values migrated from `odm.Text` to `odm.Keyword` for better indexing and
    querying performance

#### Affected Indexes

The following Elasticsearch indexes require reindexing:

- `analytic` - Analytics data with updated (case-insensitive) name/title fields
- `hit` - Hit data with updated byte counts and converting outline fields to keywords
- `view` - View data with updated (case-insensitive) title fields

### Pre-Migration Checklist

Before starting the migration process, ensure you have:

- [ ] **Full system backup** of your Elasticsearch cluster
- [ ] **Sufficient disk space** (at least 2x current data size)
- [ ] **Maintenance window scheduled** (migration time varies based on data size and cluster performance)
- [ ] **Admin access** to both Howler API and Elasticsearch cluster

### Migration Process

#### Step 1: Backup Your Data

```bash
# Create Elasticsearch snapshot (adjust repository settings as needed)
curl -X PUT "localhost:9200/_snapshot/migration_backup/howler_v2_backup?wait_for_completion=true" -H 'Content-Type: application/json' -d'
{
  "indices": "howler-*",
  "ignore_unavailable": true,
  "include_global_state": false
}'
```

#### Step 2: Stop Howler Services

You should scale down all API pods to halt ingestion during the reindexing, while maintaining a single pod to trigger
the reindexing script. You don't need to run the script from a pod, it's just the easiest way to guarantee connectivity
to the elasticsearch cluster.

#### Step 3: Update Howler to v3

Update your images to Howler V3, and use this version to run the reindxing script.

#### Step 4: Run the Reindexing Script

Howler 3.0.0 includes an improved reindexing script that allows selective index reindexing:

```bash
# Navigate to the API directory
cd /path/to/howler/api

# Run the reindexing script
python howler/external/reindex_data.py
```

The script will:

1. Display a safety warning and countdown
2. Ask for confirmation before proceeding
3. Allow you to select which index to reindex
4. Show which specific indexes will be affected
5. Ask for final confirmation before starting the reindex

**Important**: Run the script separately for each index type you need to migrate. The recommended order is:

1. `view` (typically smallest, good for testing)
2. `analytic`
3. `hit` (typically largest, do this last)

#### Step 5: Verify Migration

After reindexing each index, verify the migration was successful:

```bash
# Check index health
curl -X GET "localhost:9200/_cluster/health?pretty"

# Verify index mappings include new Long type
curl -X GET "localhost:9200/howler-hit-*/_mapping?pretty" | grep -A 5 -B 5 "long"

# Check document counts match expectations
curl -X GET "localhost:9200/howler-*/_count?pretty"
```

#### Step 6: Start Howler Services

Once all indexes have been successfully reindexed, you can scale the ingestion/api pods back up.

#### Step 7: Post-Migration Validation

Perform the following validation steps:

1. **API Health Check**: Verify the API is responding correctly

   ```bash
   curl -X GET "http://your-howler-instance/healthz/"
   ```

2. **Search Functionality**: Test search queries to ensure the Howler ODM works with the new schema
3. **Analytics**: Verify that analytics with case-insensitive names work correctly
4. **Views**: Test that view titles are searchable in a case-insensitive manner
5. **Data Integrity**: Spot-check critical data to ensure it migrated correctly

### Troubleshooting

#### Common Issues

##### Reindexing Fails with Timeout Error

- Increase Elasticsearch timeout settings
- Monitor cluster resources (CPU, memory, disk I/O)
- Consider reindexing during off-peak hours

##### Insufficient Disk Space

- Free up space or add more storage
- Consider temporary deletion of old log files
- Monitor disk usage during reindexing

##### Memory Issues During Migration

- Increase JVM heap size for Elasticsearch
- Reduce concurrent reindexing operations
- Monitor memory usage closely

##### Index Mapping Conflicts

- Verify no custom mappings conflict with new schema
- Check for any manual index modifications
- Ensure clean state before reindexing

#### Recovery Procedures

If migration fails:

1. **Stop all services immediately**
2. **Restore from backup**:

   ```bash
   curl -X POST "localhost:9200/_snapshot/migration_backup/howler_v2_backup/_restore"
   ```

3. **Investigate the failure cause**
4. **Plan retry with fixes applied**

### Migration Time Expectations

**Production migrations should be expected to take several hours**, with the exact duration depending on:

- **Cluster Resources**: CPU, memory, and disk I/O capacity
- **Data Volume**: Total size of indexes being reindexed
- **Replica Configuration**: Number of replicas configured for each index
- **Network Performance**: Speed between Elasticsearch nodes
- **Concurrent Operations**: Other activities running on the cluster

Plan for extended maintenance windows and consider scheduling migrations during off-peak hours.

### Elasticsearch Version Compatibility

**No Elasticsearch version upgrade is required** for Howler v3.0.0. The schema changes are compatible with your
current Elasticsearch installation.

### Plugin Compatibility

**No plugin updates are required**. Existing Howler plugins (Sentinel, Evidence, etc.) will continue to work without
modification as long as they remain enabled during the migration process.

### Configuration Files

**No configuration file changes are required**. This migration only affects the database schema and does not require
updates to Howler configuration files.

### Rollback Procedure

If you need to revert to Howler v2.12.0 after migration:

#### Option 1: Restore from Backup (Recommended)

1. **Stop Howler services**
2. **Restore indexes from backup** using Elasticsearch's stack management:

   ```bash
   curl -X POST "localhost:9200/_snapshot/migration_backup/howler_v2_backup/_restore"
   ```

3. **Revert Howler API** to v2.x:

   ```bash
   # Docker method
   docker pull cccs/howler-api:2.12.0
   # Update docker-compose.yml or deployment manifests
   ```

4. **Restart services** with v2.12.0

#### Option 2: Manual Rollback

If you cannot restore from backup, you'll need to:

1. Manually recreate the old schema mappings
2. Re-migrate the data back to the old field types
3. This is significantly more complex and time-consuming

**Always prefer Option 1 - maintain good backups before migration.**

### API Compatibility

**No API endpoint changes** are included in this migration. This is a database-only change that does not affect:

- REST API endpoints
- Request/response formats
- Authentication mechanisms
- Client application integrations

Your existing client applications and integrations will continue to work without modification.

### Testing Strategy

**Testing in a staging environment is strongly recommended** before production migration.

#### Staging Environment Setup

1. **Create staging cluster** with production-like data volume
2. **Test the complete migration process** using the reindexing script
3. **Validate application functionality** after migration
4. **Measure migration timing** to plan production windows
5. **Practice rollback procedures** to ensure they work correctly

#### Test Scenarios

- **Search functionality** with new case-insensitive keywords
- **Analytics queries** involving byte count fields (now Long type)
- **Plugin operations** to ensure continued compatibility
- **Performance testing** to identify any query optimization needs

#### Pre-Production Checklist

- [ ] Staging migration completed successfully
- [ ] Application functionality validated in staging
- [ ] Migration timing documented for production planning
- [ ] Rollback procedure tested and validated
- [ ] Production maintenance window scheduled
- [ ] All stakeholders notified of the migration schedule

### Summary

This migration guide provides a comprehensive approach to upgrading Howler from v2.12.0 to v3.0.0. The key points to
remember:

- **Plan for several hours of downtime** depending on your data size
- **Always backup before starting** the migration process
- **Test in staging first** to validate the process and timing
- **Use the selective reindexing script** to migrate indexes one at a time
- **Monitor closely** during and after the migration
- **Have a rollback plan ready** in case of issues

With proper preparation and testing, this migration will provide improved search functionality and better data type
handling for large integer values in your Howler deployment.

## Migration: Legacy `_hot` Index to ILM Rollover

When ILM is enabled for an index that was previously using the legacy `_hot` naming convention (e.g. `howler-hit_hot`), Howler **automatically migrates** it on startup. No manual steps are required.

### What happens automatically

When the Howler API starts and `_ensure_collection_ilm()` runs for a collection, it detects one of three states:

1. **ILM indices already exist** (pattern `{name}-0*`): No action needed. The alias is verified and the collection is ready.

2. **Legacy `_hot` index exists** (e.g. `howler-hit_hot`): Automatic migration:
   1. The ILM policy and composable index template are created/updated.
   2. Writes to the old `_hot` index are temporarily blocked.
   3. The `_hot` index is cloned to `{name}-000001` (e.g. `howler-hit-000001`).
   4. ILM lifecycle settings (`lifecycle.name`, `lifecycle.rollover_alias`) are applied to the new index.
   5. The alias (`howler-hit`) is atomically swapped: the old `_hot` index is removed from the alias, and the new `-000001` index is added as the write index.
   6. Writes to the old `_hot` index are unblocked (it remains in the cluster until manually removed).
   7. All data is preserved — the clone is a zero-copy operation at the filesystem level in Elasticsearch.

3. **Fresh install** (no existing index): A new `{name}-000001` index is created with the ILM policy and rollover alias already attached.

### What operators should do

- **Before enabling ILM**: No preparation is needed. The migration is safe to run on a live cluster.
- **After migration**: The old `_hot` index will still exist in the cluster but is no longer referenced by the alias. Operators can delete it at their convenience to reclaim disk space:
  ```
  DELETE /howler-hit_hot
  ```
- **Rollback**: If you need to revert, disable `ilm.enabled` in the config, manually recreate the alias pointing to `_hot`, and delete the `-000001` index. However, any documents written after migration will only be in the new index.

### Configuration

Enable ILM by adding the following to your Howler configuration:

```yaml
datastore:
  ilm:
    enabled: true
    rollover_max_age: "30d"       # Max age before rollover (default: 30d)
    rollover_max_size: "50gb"     # Max primary shard size before rollover (default: 50gb)
    indices:
      hit:
        warm: "30d"               # Move to warm phase after 30 days
        cold: "90d"               # Move to cold phase after 90 days
```

- `rollover_max_age` / `rollover_max_size`: Triggers for creating a new write index. Whichever threshold is hit first causes the rollover.
- `warm`: Optional. Min age before the index transitions to the warm phase (triggers a force-merge). Omit to skip the warm phase.
- `cold`: Optional. Min age before the index transitions to the cold phase. Omit to skip the cold phase.
- There is **no delete phase** — the existing retention cronjob handles document deletion via `delete_by_query` across all tiers using the alias.
- There is **no readonly action** in warm/cold — the retention cronjob needs write access to delete expired documents across all indices.

### Interaction with existing features

- **Retention cronjob**: Continues to work unchanged. It runs `delete_by_query` against the alias, which fans out across all backing indices (hot, warm, cold). No per-tier awareness is needed.
- **Search**: All queries go through the alias and automatically span all backing indices. No changes to search behavior.
- **Ingestion**: New documents are written to the current write index via the alias. Rollover is managed by Elasticsearch's ILM.
