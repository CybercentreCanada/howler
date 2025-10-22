# Generating Random Data

To get an idea of what Howler looks like with data, and to test your code, you can use the helper script
`api/howler/odm/random_data.py`. This script contains methods for generating realistic test data for all models used
in Howler.

## Basic Usage

```shell
cd ~/repos/howler/api

# Run without arguments - all indexes are wiped and populated with test data
python howler/odm/random_data.py

# Populate all indexes without wiping existing data
python howler/odm/random_data.py all --no-wipe

# Populate specific indexes only
python howler/odm/random_data.py users hits analytics

# Populate specific indexes without wiping
python howler/odm/random_data.py users hits --no-wipe
```

## Available Indexes

The following indexes can be populated with test data:

- **users** - User accounts with various permission levels and API keys
- **templates** - Hit display templates for different analytics and detections
- **overviews** - Markdown-based overview templates with Handlebars support
- **views** - Saved search queries and filters
- **hits** - Alert/detection data including bundles
- **analytics** - Analytic definitions with rules and triage settings
- **actions** - Automated action configurations
- **dossiers** - Investigation case files

## Generated Test Data

### Users

The script creates several predefined users for testing different scenarios:

| Username | Password | Type | Description |
|----------|----------|------|-------------|
| `admin` | `admin` (or `$DEV_ADMIN_PASS`) | admin, user, automation_basic, automation_advanced | Full admin access with multiple API keys |
| `user` | `user` (or `$DEV_USER_PASS`) | user | Standard user with impersonation keys |
| `shawn-h` | `shawn-h` | admin, user | Admin user for testing |
| `goose` | `goose` | admin, user | Admin user for testing |
| `huey` | `huey` | user | Standard user for testing |

<!-- markdownlint-disable -->
??? tip "Custom Passwords"
    You can customize the admin and user passwords by setting environment variables:

    ```shell
    export DEV_ADMIN_PASS="my_secure_password"
    export DEV_USER_PASS="my_user_password"
    python howler/odm/random_data.py users
    ```
<!-- markdownlint-enable -->

### Hits

By default, the script generates **200 random hits** with realistic data including:

- Various detection types and analytics
- Different status levels (open, in-progress, resolved)
- Random assignments to users
- Assessment data (escalations and scrutiny levels)
- Event categories and metadata

The script also creates **bundles** - groups of related hits linked together.

### Analytics

The script generates analytics in several categories:

- **Existing analytics from hits** - Analytics are automatically created from generated hits
- **Random analytics** (10 by default) - Fully randomized analytic definitions
- **Rule-based analytics** - Analytics with Lucene, EQL, and Sigma rules

Each analytic includes:

- Detections
- Comments (both analytic-level and detection-level)
- Notebooks (if enabled in configuration)
- Triage settings with valid assessments
- Contributors and owners

<!-- markdownlint-disable -->
??? info "Sigma Rules"
    For better test data using Sigma rules, run the Sigma rule generator first:

    ```shell
    python howler/external/generate_sigma_rules.py
    ```
<!-- markdownlint-enable -->

### Templates

Templates are generated for different analytics and detections, including:

- **Global templates** - Available to all users
- **Personal templates** - User-specific templates

Each template defines which hit fields should be displayed and in what order.

### Overviews

Overview templates use Handlebars syntax to create dynamic markdown-based views of hits. The generated overviews
include examples of:

- Conditional rendering based on hit status
- Fetching external data via API calls
- Displaying user avatars
- Status badges and formatting

### Actions

Random automated actions are generated with various operations such as:

- Prioritization adjustments
- Status transitions
- Field updates
- Bulk operations

Each action includes a query to match hits and a series of operations to perform.

### Views

Saved views are created including:

- **Global views** - Shared queries for common use cases
- **Personal views** - User-specific saved searches
- **Readonly views** - Pre-configured filters (e.g., "Assigned to me")

## Environment Variables

The script respects several environment variables:

- `DEV_ADMIN_PASS` - Password for the admin user (default: `admin`)
- `DEV_USER_PASS` - Password for the user account (default: `user`)
- `HWL_PLUGIN_DIRECTORY` - Location of Howler plugins (default: `/etc/howler/plugins`)
- `ELASTIC_HIT_SHARDS` - Number of shards for hits index (set to 1 during setup)
- `ELASTIC_HIT_REPLICAS` - Number of replicas for hits index (set to 1 during setup)
- `ELASTIC_USER_REPLICAS` - Number of replicas for user index (set to 1 during setup)
- `ELASTIC_USER_AVATAR_REPLICAS` - Number of replicas for user avatar index (set to 1 during setup)

## Plugin Integration

The random data generator supports plugins through the `run_modifications` function. If you have custom plugins that
extend Howler's data models, they will automatically be invoked during data generation to populate plugin-specific
fields.

## Use Cases

### Development Environment Setup

Quickly populate a fresh Howler instance with realistic test data:

```shell
python howler/odm/random_data.py all
```

### Testing Specific Features

Populate only the data needed for your feature:

```shell
# Testing user permissions
python howler/odm/random_data.py users --no-wipe

# Testing hit processing
python howler/odm/random_data.py hits analytics --no-wipe

# Testing actions
python howler/odm/random_data.py hits actions --no-wipe
```

### Continuous Integration

Use the `--no-wipe` flag to add test data without destroying existing data during test runs.
