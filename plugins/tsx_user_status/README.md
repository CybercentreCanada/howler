# tsx_user_status

Status for users

---

**Module**: tsx-user-status

**Authors**: Kevin Issa, Veer Reddy Sathi

## Features

- Get/set user status plus per-user schedule and team assignment
- Atomic combined updates (status + schedule + team) via JSON Merge Patch
- Bulk status retrieval with user info enrichment
- Shared Redis-cached schedule accessor for other plugins

## Prerequisites

- Redis (persistent) connection configured in Howler

[API Plugin Docs](https://github.com/CybercentreCanada/howler/blob/develop/docs/api/plugins.md)

---

## Install Plugin

### Configure Howler to load your plugin

`/workspaces/howler/development/devcontainer/config/config.yml`

```yaml
core:
  plugins:
    - tsx_user_status
```

### Install plugin

```shell
cd /workspaces/howler/api
poetry add --editable ../plugins/tsx_user_status
```

---

## Plugin Configuration

`/workspaces/howler/development/devcontainer/config/tsx_user_status.yml`

```yaml
# Config settings for tsx_user_status
# Schedule blob settings (consumed by the shared schedule cache):
schedules_account: ""
schedules_container: ""
schedules_blob: ""
schedules_key: ""
# Optional cache tuning:
schedules_cache_key: "tsx_user_status:schedules"
schedules_cache_ttl: 18000 # 5h
# Optional Redis key namespacing:
key_prefix: "tsx_user_status:status"
shift_key_prefix: "tsx_user_status:shift"
```

The same settings can be supplied as environment variables, prefixed with
`TSX_USER_STATUS_`:

```shell
TSX_USER_STATUS_SCHEDULES_ACCOUNT
TSX_USER_STATUS_SCHEDULES_CONTAINER
TSX_USER_STATUS_SCHEDULES_BLOB
TSX_USER_STATUS_SCHEDULES_KEY
TSX_USER_STATUS_SCHEDULES_CACHE_KEY    # optional
TSX_USER_STATUS_SCHEDULES_CACHE_TTL    # optional
TSX_USER_STATUS_KEY_PREFIX             # optional
TSX_USER_STATUS_SHIFT_KEY_PREFIX       # optional
```

> **Migration note:** schedule configuration previously lived in the
> `tsxhandover_report` plugin (`TSXHANDOVER_REPORT_SCHEDULES_*` /
> `tsxhandover_report.yml`). It now belongs to `tsx_user_status`. Move these
> values to the `TSX_USER_STATUS_*` namespace, otherwise the schedules
> endpoint and the readiness probe will report the config as missing.

### Schedule cache

`tsx_user_status` also exposes a shared, Redis-cached accessor for shift
schedules stored in Azure Blob Storage. Other plugins can import it directly:

```python
from tsx_user_status.config import config as schedule_config
from tsx_user_status.services.schedule_service import get_schedules

schedules = get_schedules(schedule_config)
```

Cache freshness is governed entirely by the Redis TTL (`schedules_cache_ttl`).

## Routes

| Route                         | Method | Description                                                  |
| ----------------------------- | ------ | ------------------------------------------------------------ |
| /api/v1/status/statuses       | GET    | Get the list of valid status values                          |
| /api/v1/status/schedules      | GET    | Get the team-to-schedules mapping                            |
| /api/v1/status/users          | GET    | Get all users' status, schedule, team, and tags              |
| /api/v1/status/users/\<uname> | GET    | Get a specific user's status, schedule, team, and tags       |
| /api/v1/status/users/\<uname> | PATCH  | Partially update a user's status/schedule/team (merge patch) |
| /api/v1/status/healthz/live   | GET    | Returns 200 OK if plugin is loaded                           |
| /api/v1/status/healthz/ready  | GET    | Returns 200 OK if Redis connection is alive                  |

## Response Format

All user status endpoints return a consistent user object:

```json
{
  "api_response": {
    "uname": "john.doe",
    "name": "John Doe",
    "status": "available",
    "schedule": "Day 7-15",
    "team": "MS",
    "tags": {
      "portfolio": ["portfolio_a"],
      "products": ["product_a"],
      "primary_disciplines": ["discipline_a"]
    }
  }
}
```

- `uname`: The user's unique identifier
- `name`: The user's display name
- `status`: A status string, or `null` if not set
- `schedule`: A schedule string, or `null` if not set
- `team`: A team string, or `null` if not set
- `tags`: The user's tags as stored on the User ODM (value keys match
  those from `GET /api/v1/tags/all`). Resolve display names via the
  `tsx_user_tags` plugin. Users with no tags set return all three lists empty:
  `{"portfolio": [], "products": [], "primary_disciplines": []}`.

### GET /api/v1/status/users

Returns an array of all active users with their status, schedule, team, and tags:

```json
{
  "api_response": [
    {
      "uname": "john.doe",
      "name": "John Doe",
      "status": "available",
      "schedule": "Day 7-15",
      "team": "MS",
      "tags": {
        "portfolio": ["portfolio_a"],
        "products": ["product_a"],
        "primary_disciplines": ["discipline_a"]
      }
    },
    {
      "uname": "jane.smith",
      "name": "Jane Smith",
      "status": null,
      "schedule": null,
      "team": null,
      "tags": {
        "portfolio": [],
        "products": [],
        "primary_disciplines": []
      }
    }
  ]
}
```

### PATCH /api/v1/status/users/<uname>

Partial update using [JSON Merge Patch (RFC 7396)](https://datatracker.ietf.org/doc/html/rfc7396)
semantics:

- Fields **omitted** from the body are left untouched.
- Fields explicitly set to `null` are **cleared**.
- The body must contain at least one of `status`, `schedule`, or `team`.
- `team` must exist in the cached schedules map.
- If both `team` and `schedule` are present after merge, `schedule` must be
  valid for that `team`.
- If only `schedule` is provided (no `team`), the schedule must exist in at
  least one known team.
- Status and schedule/team writes are applied atomically inside a single Redis
  `MULTI`/`EXEC` transaction.

Examples:

Set status only:

```json
{ "status": "available" }
```

Set schedule only:

```json
{ "schedule": "Day 7-15" }
```

Set team only:

```json
{ "team": "MS" }
```

Set all at once (e.g., shift hand-off):

```json
{ "status": "available", "schedule": "Day 7-15", "team": "MS" }
```

Clear all fields atomically:

```json
{ "status": null, "schedule": null, "team": null }
```

## Status Values

Status must be one of the recognized values: the numeric shift codes `"1"`
through `"15"`, or a named status (`"available"`, `"busy"`, `"unavailable"`,
`"away"`). Retrieve the authoritative list via `GET /api/v1/status/statuses`.
Set to `null` to clear.

## Authentication

All endpoints require authentication via the Howler API login.

| Endpoint | Required Privilege |
| -------- | ------------------ |
| GET      | R (read)           |
| PATCH    | W (write)          |

Any authenticated user with the required privilege can read or update any
other user's status/schedule/team (e.g. for cross-team shift hand-offs).

## Error Responses

| Code | Condition                                                       |
| ---- | --------------------------------------------------------------- |
| 400  | Invalid JSON, invalid status, invalid schedule, or invalid team |
| 404  | User not found                                                  |
| 500  | Redis connection error                                          |

## Notes

- Status data is stored in Redis under `<key_prefix>:{uname}` (default:
  `tsx_user_status:status:{uname}`).
- Schedule/team data is stored in Redis under `<shift_key_prefix>:{uname}`
  (default: `tsx_user_status:shift:{uname}`) as
  a JSON-encoded object containing optional `"schedule"` and `"team"` keys.
- Both keys are hash-tagged on the user id (the `{uname}` braces). A given user's
  status and shift keys therefore map to the same Redis Cluster slot, so PATCH can
  write them in a single `MULTI`/`EXEC` transaction, while different users
  distribute across slots.
