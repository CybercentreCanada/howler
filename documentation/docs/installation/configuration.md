??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality
    will always be documented and available on release.

# Config

Main Howler configuration model.

The root configuration object that aggregates all configuration sections
including authentication, datastore, logging, system settings, UI, and core
services. Configuration can be loaded from YAML files or environment variables
with the HWL_ prefix.

Environment variables use double underscores (__) for nested properties.
For example: HWL_DATASTORE__TYPE=elasticsearch

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `auth` | [`Auth`](#auth) | Authentication configuration for Howler.      Configures all authentication methods supported by Howler, including     internal username/password authentication and OAuth providers. Also     controls API key settings and restrictions.      | :material-checkbox-marked-outline: Yes | See [Auth](#auth) for details. |
| `core` | [`Core`](#core) | Core application configuration for Howler.      Aggregates all core service configurations including Redis, metrics,     and external integrations like Borealis and nbgallery notebooks.     Also manages the loading of external plugins.      | :material-checkbox-marked-outline: Yes | See [Core](#core) for details. |
| `datastore` | [`Datastore`](#datastore) | Datastore configuration for Howler.      Defines the backend datastore used by Howler for storing hits and metadata.     Currently supports Elasticsearch as the datastore type.      | :material-checkbox-marked-outline: Yes | See [Datastore](#datastore) for details. |
| `logging` | [`Logging`](#logging) | Logging configuration for Howler.      Defines how and where Howler logs should be output, including console,     file, and syslog destinations. Also controls log level, format, and     metric export intervals.      | :material-checkbox-marked-outline: Yes | See [Logging](#logging) for details. |
| `system` | [`System`](#system) | System-level configuration for Howler.      Defines global system settings including deployment type (production,     staging, or development) and configuration for automated maintenance     jobs like data retention and view cleanup.      | :material-checkbox-marked-outline: Yes | See [System](#system) for details. |
| `ui` | [`UI`](#ui) | User interface and web server configuration.      Defines settings for the Howler web UI including Flask configuration,     session validation, API auditing, static file locations, and WebSocket     integration for real-time updates.      | :material-checkbox-marked-outline: Yes | See [UI](#ui) for details. |
| `mapping` | `dict[str, str]` | Mapping of alert keys to borealis type | :material-checkbox-marked-outline: Yes | `{}`


# Auth

Authentication configuration for Howler.

Configures all authentication methods supported by Howler, including
internal username/password authentication and OAuth providers. Also
controls API key settings and restrictions.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `allow_apikeys` | `bool` | Allow API keys? | :material-checkbox-marked-outline: Yes | `True`
| `allow_extended_apikeys` | `bool` | Allow extended API keys? | :material-checkbox-marked-outline: Yes | `True`
| `max_apikey_duration_amount` | `int` | Amount of unit of maximum duration for API keys | :material-minus-box-outline: Optional | `None`
| `max_apikey_duration_unit` | `Literal[seconds, minutes, hours, days, weeks]` | Unit of maximum duration for API keys | :material-minus-box-outline: Optional | `None`
| `internal` | [`Internal`](#internal) | Internal authentication configuration.      Defines settings for Howler's built-in username/password authentication,     including password requirements and brute-force protection via login     failure tracking.      | :material-checkbox-marked-outline: Yes | See [Internal](#internal) for details. |
| `oauth` | [`OAuth`](#oauth) | OAuth authentication configuration.      Top-level OAuth settings including enabling/disabling OAuth authentication,     Gravatar integration, and a dictionary of configured OAuth providers.     Also controls API key lifetime restrictions for OAuth-authenticated users.      | :material-checkbox-marked-outline: Yes | See [OAuth](#oauth) for details. |


# Internal

Internal authentication configuration.

Defines settings for Howler's built-in username/password authentication,
including password requirements and brute-force protection via login
failure tracking.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | Internal authentication allowed? | :material-checkbox-marked-outline: Yes | `True`
| `failure_ttl` | `int` | How long to wait after `max_failures` before re-attempting login? | :material-checkbox-marked-outline: Yes | `60`
| `max_failures` | `int` | Maximum number of fails allowed before timeout | :material-checkbox-marked-outline: Yes | `5`
| `password_requirements` | [`PasswordRequirement`](#passwordrequirement) | Password complexity requirements for internal authentication.      Defines the rules for password creation and validation, including     character type requirements and minimum length.      | :material-checkbox-marked-outline: Yes | See [PasswordRequirement](#passwordrequirement) for details. |


# PasswordRequirement

Password complexity requirements for internal authentication.

Defines the rules for password creation and validation, including
character type requirements and minimum length.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `lower` | `bool` | Password must contain lowercase letters | :material-checkbox-marked-outline: Yes | `False`
| `number` | `bool` | Password must contain numbers | :material-checkbox-marked-outline: Yes | `False`
| `special` | `bool` | Password must contain special characters | :material-checkbox-marked-outline: Yes | `False`
| `upper` | `bool` | Password must contain uppercase letters | :material-checkbox-marked-outline: Yes | `False`
| `min_length` | `int` | Minimum password length | :material-checkbox-marked-outline: Yes | `12`


# OAuth

OAuth authentication configuration.

Top-level OAuth settings including enabling/disabling OAuth authentication,
Gravatar integration, and a dictionary of configured OAuth providers.
Also controls API key lifetime restrictions for OAuth-authenticated users.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | Enable use of OAuth? | :material-checkbox-marked-outline: Yes | `False`
| `gravatar_enabled` | `bool` | Enable gravatar? | :material-checkbox-marked-outline: Yes | `True`
| `providers` | `dict[str, OAuthProvider]` | OAuth provider configuration | :material-checkbox-marked-outline: Yes | `{}`
| `strict_apikeys` | `bool` | Only allow apikeys that last as long as the access token used to log in | :material-checkbox-marked-outline: Yes | `False`


# OAuthProvider

OAuth provider configuration.

Defines the connection and authentication settings for an OAuth 2.0 provider.
Includes user auto-creation, group mapping, JWT validation, and various
OAuth endpoints required for the authentication flow.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `auto_create` | `bool` | Auto-create users if they are missing | :material-checkbox-marked-outline: Yes | `True`
| `auto_sync` | `bool` | Should we automatically sync with OAuth provider? | :material-checkbox-marked-outline: Yes | `False`
| `auto_properties` | `list[OAuthAutoProperty]` | Automatic role and classification assignments | :material-checkbox-marked-outline: Yes | `[]`
| `uid_randomize` | `bool` | Should we generate a random username for the authenticated user? | :material-checkbox-marked-outline: Yes | `False`
| `uid_randomize_digits` | `int` | How many digits should we add at the end of the username? | :material-checkbox-marked-outline: Yes | `0`
| `uid_randomize_delimiter` | `str` | What is the delimiter used by the random name generator? | :material-checkbox-marked-outline: Yes | `-`
| `uid_regex` | `str` | Regex used to parse an email address and capture parts to create a user ID out of it | :material-minus-box-outline: Optional | `None`
| `uid_format` | `str` | Format of the user ID based on the captured parts from the regex | :material-minus-box-outline: Optional | `None`
| `client_id` | `str` | ID of your application to authenticate to the OAuth provider | :material-minus-box-outline: Optional | `None`
| `client_secret` | `str` | Password to your application to authenticate to the OAuth provider | :material-minus-box-outline: Optional | `None`
| `request_token_url` | `str` | URL to request token | :material-minus-box-outline: Optional | `None`
| `request_token_params` | `str` | Parameters to request token | :material-minus-box-outline: Optional | `None`
| `required_groups` | `list[str]` | The groups the JWT must contain in order to allow access | :material-checkbox-marked-outline: Yes | `[]`
| `role_map` | `dict[str, str]` | A mapping of OAuth groups to howler roles | :material-checkbox-marked-outline: Yes | `{}`
| `access_token_url` | `str` | URL to get access token | :material-minus-box-outline: Optional | `None`
| `access_token_params` | `str` | Parameters to get access token | :material-minus-box-outline: Optional | `None`
| `authorize_url` | `str` | URL used to authorize access to a resource | :material-minus-box-outline: Optional | `None`
| `authorize_params` | `str` | Parameters used to authorize access to a resource | :material-minus-box-outline: Optional | `None`
| `api_base_url` | `str` | Base URL for downloading the user's and groups info | :material-minus-box-outline: Optional | `None`
| `audience` | `str` | The audience to validate against. Only must be set if audience is different than the client id. | :material-minus-box-outline: Optional | `None`
| `scope` | `str` | The scope to validate against | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `picture_url` | `str` | URL for downloading the user's profile | :material-minus-box-outline: Optional | `None`
| `groups_url` | `str` | URL for accessing additional data about the user's groups | :material-minus-box-outline: Optional | `None`
| `groups_key` | `str` | Path to the list of groups in the response returned from groups_url | :material-minus-box-outline: Optional | `None`
| `iss` | `str` | Optional issuer field for JWT validation | :material-minus-box-outline: Optional | `None`
| `jwks_uri` | `str` | URL used to verify if a returned JWKS token is valid | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `user_get` | `str` | Path from the base_url to fetch the user info | :material-minus-box-outline: Optional | `None`


# OAuthAutoProperty

Automatic property assignment based on OAuth attributes.

Defines rules for automatically assigning user properties (roles,
classifications, or access levels) based on pattern matching against
OAuth provider data.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `field` | `str` | Field to apply `pattern` to | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `pattern` | `str` | Regex pattern for auto-prop assignment | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `type` | `Literal[access, classification, role]` | Type of property assignment on pattern match | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `value` | `str` | Assigned property value | :material-checkbox-marked-outline: Yes | `PydanticUndefined`


# Core

Core application configuration for Howler.

Aggregates all core service configurations including Redis, metrics,
and external integrations like Borealis and nbgallery notebooks.
Also manages the loading of external plugins.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `plugins` | `set[str]` | A list of external plugins to load | :material-checkbox-marked-outline: Yes | `set()`
| `metrics` | [`Metrics`](#metrics) | Metrics collection configuration.      Configures how Howler collects and exports application metrics,     including integration with external APM servers.      | :material-checkbox-marked-outline: Yes | See [Metrics](#metrics) for details. |
| `redis` | [`Redis`](#redis) | Redis configuration for Howler.      Defines connections to both persistent and non-persistent Redis instances.     The non-persistent instance is used for volatile data like caches, while     the persistent instance is used for data that needs to survive restarts.      | :material-checkbox-marked-outline: Yes | See [Redis](#redis) for details. |
| `borealis` | [`Borealis`](#borealis) | Borealis enrichment service integration configuration.      Defines settings for integrating with Borealis, an external enrichment     service that can provide additional context and status information for     hits displayed in the Howler UI.      | :material-checkbox-marked-outline: Yes | See [Borealis](#borealis) for details. |
| `notebook` | [`Notebook`](#notebook) | Jupyter notebook integration configuration.      Defines settings for integrating with nbgallery, a collaborative     Jupyter notebook platform, allowing users to access and share     notebooks related to their Howler analysis work.      | :material-checkbox-marked-outline: Yes | See [Notebook](#notebook) for details. |


# Metrics

Metrics collection configuration.

Configures how Howler collects and exports application metrics,
including integration with external APM servers.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `apm_server` | [`APMServer`](#apmserver) | Application Performance Monitoring (APM) server configuration.      Defines the connection details for an external APM server used to     collect and analyze application performance metrics.      | :material-checkbox-marked-outline: Yes | See [APMServer](#apmserver) for details. |


# APMServer

Application Performance Monitoring (APM) server configuration.

Defines the connection details for an external APM server used to
collect and analyze application performance metrics.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `server_url` | `str` | URL to API server | :material-minus-box-outline: Optional | `None`
| `token` | `str` | Authentication token for server | :material-minus-box-outline: Optional | `None`


# Redis

Redis configuration for Howler.

Defines connections to both persistent and non-persistent Redis instances.
The non-persistent instance is used for volatile data like caches, while
the persistent instance is used for data that needs to survive restarts.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `nonpersistent` | [`RedisServer`](#redisserver) | Configuration for a single Redis server instance.      Defines the connection parameters for a Redis server, including     the hostname and port number.      | :material-checkbox-marked-outline: Yes | See [RedisServer](#redisserver) for details. |
| `persistent` | [`RedisServer`](#redisserver) | Configuration for a single Redis server instance.      Defines the connection parameters for a Redis server, including     the hostname and port number.      | :material-checkbox-marked-outline: Yes | See [RedisServer](#redisserver) for details. |


# RedisServer

Configuration for a single Redis server instance.

Defines the connection parameters for a Redis server, including
the hostname and port number.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `host` | `str` | Hostname of Redis instance | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `port` | `int` | Port of Redis instance | :material-checkbox-marked-outline: Yes | `PydanticUndefined`


# RedisServer

Configuration for a single Redis server instance.

Defines the connection parameters for a Redis server, including
the hostname and port number.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `host` | `str` | Hostname of Redis instance | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `port` | `int` | Port of Redis instance | :material-checkbox-marked-outline: Yes | `PydanticUndefined`


# Borealis

Borealis enrichment service integration configuration.

Defines settings for integrating with Borealis, an external enrichment
service that can provide additional context and status information for
hits displayed in the Howler UI.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | Should borealis integration be enabled? | :material-checkbox-marked-outline: Yes | `False`
| `url` | `str` | What url should Howler connect to to interact with Borealis? | :material-checkbox-marked-outline: Yes | `http://enrichment-rest.enrichment.svc.cluster.local:5000`
| `status_checks` | `list[str]` | A list of borealis fetchers that return status results given a Howler ID to show in the UI. | :material-checkbox-marked-outline: Yes | `[]`


# Notebook

Jupyter notebook integration configuration.

Defines settings for integrating with nbgallery, a collaborative
Jupyter notebook platform, allowing users to access and share
notebooks related to their Howler analysis work.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | Should nbgallery notebook integration be enabled? | :material-checkbox-marked-outline: Yes | `False`
| `scope` | `str` | The scope expected by nbgallery for JWTs | :material-minus-box-outline: Optional | `None`
| `url` | `str` | The url to connect to nbgallery at | :material-checkbox-marked-outline: Yes | `http://nbgallery.nbgallery.svc.cluster.local:3000`


# Datastore

Datastore configuration for Howler.

Defines the backend datastore used by Howler for storing hits and metadata.
Currently supports Elasticsearch as the datastore type.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `hosts` | `list[Host]` | List of hosts used for the datastore | :material-checkbox-marked-outline: Yes | `[http://elastic:devpass@localhost:9200]`
| `type` | `Literal[elasticsearch]` | Type of application used for the datastore | :material-checkbox-marked-outline: Yes | `elasticsearch`


# Host

Configuration for a remote host connection.

Defines connection parameters for external services, including authentication
credentials (username/password or API key) and connection details.
Environment variables can override username and password using the pattern
{NAME}_HOST_USERNAME and {NAME}_HOST_PASSWORD.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `name` | `str` | Name of the host | :material-checkbox-marked-outline: Yes | `PydanticUndefined`
| `username` | `str` | Username to login with | :material-minus-box-outline: Optional | `None`
| `password` | `str` | Password to login with | :material-minus-box-outline: Optional | `None`
| `apikey_id` | `str` | ID of the API Key to use when connecting | :material-minus-box-outline: Optional | `None`
| `apikey_secret` | `str` | Secret data of the API Key to use when connecting | :material-minus-box-outline: Optional | `None`
| `scheme` | `str` | Scheme to use when connecting | :material-minus-box-outline: Optional | `http`
| `host` | `str` | URL to connect to | :material-checkbox-marked-outline: Yes | `PydanticUndefined`


# Logging

Logging configuration for Howler.

Defines how and where Howler logs should be output, including console,
file, and syslog destinations. Also controls log level, format, and
metric export intervals.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `log_level` | `Literal[DEBUG, INFO, WARNING, ERROR, CRITICAL, DISABLED]` | What level of logging should we have? | :material-checkbox-marked-outline: Yes | `INFO`
| `log_to_console` | `bool` | Should we log to console? | :material-checkbox-marked-outline: Yes | `True`
| `log_to_file` | `bool` | Should we log to files on the server? | :material-checkbox-marked-outline: Yes | `False`
| `log_directory` | `str` | If `log_to_file: true`, what is the directory to store logs? | :material-checkbox-marked-outline: Yes | `/var/log/howler/`
| `log_to_syslog` | `bool` | Should logs be sent to a syslog server? | :material-checkbox-marked-outline: Yes | `False`
| `syslog_host` | `str` | If `log_to_syslog: true`, provide hostname/IP of the syslog server? | :material-checkbox-marked-outline: Yes | `localhost`
| `syslog_port` | `int` | If `log_to_syslog: true`, provide port of the syslog server? | :material-checkbox-marked-outline: Yes | `514`
| `export_interval` | `int` | How often, in seconds, should counters log their values? | :material-checkbox-marked-outline: Yes | `5`
| `log_as_json` | `bool` | Log in JSON format? | :material-checkbox-marked-outline: Yes | `True`


# System

System-level configuration for Howler.

Defines global system settings including deployment type (production,
staging, or development) and configuration for automated maintenance
jobs like data retention and view cleanup.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `type` | `Literal[production, staging, development]` | Type of system | :material-checkbox-marked-outline: Yes | `development`
| `retention` | [`Retention`](#retention) | Hit retention policy configuration.      Defines the automatic data retention policy for hits, including     the maximum age of hits before they are purged and the schedule     for running the retention cleanup job.      | :material-checkbox-marked-outline: Yes | See [Retention](#retention) for details. |
| `view_cleanup` | [`ViewCleanup`](#viewcleanup) | View cleanup job configuration.      Defines the schedule and behavior for cleaning up stale dashboard views     that reference non-existent backend data.      | :material-checkbox-marked-outline: Yes | See [ViewCleanup](#viewcleanup) for details. |


# Retention

Hit retention policy configuration.

Defines the automatic data retention policy for hits, including
the maximum age of hits before they are purged and the schedule
for running the retention cleanup job.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | Whether to enable the hit retention limit. If enabled, hits will be purged after the specified duration. | :material-checkbox-marked-outline: Yes | `True`
| `limit_unit` | `Literal[days, seconds, microseconds, milliseconds, minutes, hours, weeks]` | The unit to use when computing the retention limit | :material-checkbox-marked-outline: Yes | `days`
| `limit_amount` | `int` | The number of limit_units to use when computing the retention limit | :material-checkbox-marked-outline: Yes | `350`
| `crontab` | `str` | The crontab that denotes how often to run the retention job | :material-checkbox-marked-outline: Yes | `0 0 * * *`


# ViewCleanup

View cleanup job configuration.

Defines the schedule and behavior for cleaning up stale dashboard views
that reference non-existent backend data.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | Whether to enable the view cleanup. If enabled, views pinned to the dashboard that no longer exist in the backend will be cleared. | :material-checkbox-marked-outline: Yes | `True`
| `crontab` | `str` | The crontab that denotes how often to run the view_cleanup job | :material-checkbox-marked-outline: Yes | `0 0 * * *`


# UI

User interface and web server configuration.

Defines settings for the Howler web UI including Flask configuration,
session validation, API auditing, static file locations, and WebSocket
integration for real-time updates.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| `audit` | `bool` | Should API calls be audited and saved to a separate log file? | :material-checkbox-marked-outline: Yes | `True`
| `debug` | `bool` | Enable debugging? | :material-checkbox-marked-outline: Yes | `False`
| `static_folder` | `str` | The directory where static assets are stored. | :material-minus-box-outline: Optional | `/home/mdrafus/repos/howler/api/howler/odm/models/../../../static`
| `discover_url` | `str` | Discovery URL | :material-minus-box-outline: Optional | `None`
| `enforce_quota` | `bool` | Enforce the user's quotas? | :material-checkbox-marked-outline: Yes | `True`
| `secret_key` | `str` | Flask secret key to store cookies, etc. | :material-checkbox-marked-outline: Yes | `This is the default flask secret key... you should change this!`
| `validate_session_ip` | `bool` | Validate if the session IP matches the IP the session was created from | :material-checkbox-marked-outline: Yes | `True`
| `validate_session_useragent` | `bool` | Validate if the session useragent matches the useragent the session was created with | :material-checkbox-marked-outline: Yes | `True`
| `websocket_url` | `str` | The url to hit when emitting websocket events on the cluster | :material-minus-box-outline: Optional | `None`

