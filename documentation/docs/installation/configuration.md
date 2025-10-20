??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Config

> Howler Deployment Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| auth | [Auth](#auth) | Authentication module configuration | :material-checkbox-marked-outline: Yes | See [Auth](#auth) for more details. |
| core | [Core](#core) | Core component configuration | :material-checkbox-marked-outline: Yes | See [Core](#core) for more details. |
| datastore | [Datastore](#datastore) | Datastore configuration | :material-checkbox-marked-outline: Yes | See [Datastore](#datastore) for more details. |
| filestore | [Filestore](#filestore) | Filestore configuration | :material-checkbox-marked-outline: Yes | See [Filestore](#filestore) for more details. |
| logging | [Logging](#logging) | Logging configuration | :material-checkbox-marked-outline: Yes | See [Logging](#logging) for more details. |
| system | [System](#system) | System configuration | :material-checkbox-marked-outline: Yes | See [System](#system) for more details. |
| ui | [UI](#ui) | UI configuration parameters | :material-checkbox-marked-outline: Yes | See [UI](#ui) for more details. |


## APMServer

> None

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| server_url | Keyword | URL to API server | :material-minus-box-outline: Optional | `None` |
| token | Keyword | Authentication token for server | :material-minus-box-outline: Optional | `None` |


## Auth

> Authentication Methods

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| allow_apikeys | Boolean | Allow API keys? | :material-checkbox-marked-outline: Yes | `None` |
| allow_extended_apikeys | Boolean | Allow extended API keys? | :material-checkbox-marked-outline: Yes | `None` |
| max_apikey_duration_amount | Integer | Amount of unit of maximum duration for API keys | :material-minus-box-outline: Optional | `None` |
| max_apikey_duration_unit | Enum | Unit of maximum duration for API keys<br>Values:<br>`"days", "hours", "minutes", "seconds", "weeks"` | :material-minus-box-outline: Optional | `None` |
| internal | [Internal](#internal) | Internal authentication settings | :material-checkbox-marked-outline: Yes | See [Internal](#internal) for more details. |
| oauth | [OAuth](#oauth) | OAuth settings | :material-checkbox-marked-outline: Yes | See [OAuth](#oauth) for more details. |


## Core

> Howler Core Component Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| metrics | [Metrics](#metrics) | Configuration for Metrics Collection | :material-checkbox-marked-outline: Yes | See [Metrics](#metrics) for more details. |
| redis | [Redis](#redis) | Configuration for Redis instances | :material-checkbox-marked-outline: Yes | See [Redis](#redis) for more details. |


## Datastore

> Datastore Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| hosts | List [[Host](#host)] | List of hosts used for the datastore | :material-checkbox-marked-outline: Yes | `None` |
| ilm | [ILM](#ilm) | Index Lifecycle Management Policy | :material-checkbox-marked-outline: Yes | See [ILM](#ilm) for more details. |
| type | Enum | Type of application used for the datastore<br>Values:<br>`"elasticsearch"` | :material-checkbox-marked-outline: Yes | `None` |


## Filestore

> Filestore Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| storage | List [[Host](#host)] | List of filestores used for storage | :material-checkbox-marked-outline: Yes | `None` |


## Host

> Host Entries

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| name | Keyword | Name of the host | :material-checkbox-marked-outline: Yes | `None` |
| username | Keyword | Username to login with | :material-minus-box-outline: Optional | `None` |
| password | Keyword | Password to login with | :material-minus-box-outline: Optional | `None` |
| apikey_id | Keyword | ID of the API Key to use when connecting | :material-minus-box-outline: Optional | `None` |
| apikey_secret | Keyword | Secret data of the API Key to use when connecting | :material-minus-box-outline: Optional | `None` |
| scheme | Keyword | Scheme to use when connecting | :material-minus-box-outline: Optional | `http` |
| host | Keyword | URL to connect to | :material-checkbox-marked-outline: Yes | `None` |


## ILM

> Index Lifecycle Management

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| enabled | Boolean | Are we enabling ILM across indices? | :material-checkbox-marked-outline: Yes | `None` |
| days_until_archive | Integer | Days until documents get archived | :material-checkbox-marked-outline: Yes | `None` |
| indexes | Mapping [[ILMParams](#ilmparams)] | Index-specific ILM policies | :material-checkbox-marked-outline: Yes | See [ILMParams](#ilmparams) for more details. |
| update_archive | Boolean | Do we want to update documents in the archive? | :material-checkbox-marked-outline: Yes | `None` |


## ILMParams

> Parameters associated to ILM Policies

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| warm | Integer | How long, per unit of time, should a document remain in the 'warm' tier? | :material-checkbox-marked-outline: Yes | `None` |
| cold | Integer | How long, per unit of time, should a document remain in the 'cold' tier? | :material-checkbox-marked-outline: Yes | `None` |
| delete | Integer | How long, per unit of time, should a document remain before being deleted? | :material-checkbox-marked-outline: Yes | `None` |
| unit | Enum | Unit of time used by `warm`, `cold`, `delete` phases<br>Values:<br>`"d", "h", "m"` | :material-checkbox-marked-outline: Yes | `None` |


## Internal

> Internal Authentication Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| enabled | Boolean | Internal authentication allowed? | :material-checkbox-marked-outline: Yes | `None` |
| failure_ttl | Integer | How long to wait after `max_failures` before re-attempting login? | :material-checkbox-marked-outline: Yes | `None` |
| max_failures | Integer | Maximum number of fails allowed before timeout | :material-checkbox-marked-outline: Yes | `None` |
| password_requirements | [PasswordRequirement](#passwordrequirement) | Password requirements | :material-checkbox-marked-outline: Yes | See [PasswordRequirement](#passwordrequirement) for more details. |


## Logging

> Model Definition for the Logging Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| log_level | Enum | What level of logging should we have?<br>Values:<br>`"CRITICAL", "DEBUG", "DISABLED", "ERROR", "INFO", "WARNING"` | :material-checkbox-marked-outline: Yes | `None` |
| log_to_console | Boolean | Should we log to console? | :material-checkbox-marked-outline: Yes | `None` |
| log_to_file | Boolean | Should we log to files on the server? | :material-checkbox-marked-outline: Yes | `None` |
| log_directory | Keyword | If `log_to_file: true`, what is the directory to store logs? | :material-checkbox-marked-outline: Yes | `None` |
| log_to_syslog | Boolean | Should logs be sent to a syslog server? | :material-checkbox-marked-outline: Yes | `None` |
| syslog_host | Keyword | If `log_to_syslog: true`, provide hostname/IP of the syslog server? | :material-checkbox-marked-outline: Yes | `None` |
| syslog_port | Integer | If `log_to_syslog: true`, provide port of the syslog server? | :material-checkbox-marked-outline: Yes | `None` |
| export_interval | Integer | How often, in seconds, should counters log their values? | :material-checkbox-marked-outline: Yes | `None` |
| log_as_json | Boolean | Log in JSON format? | :material-checkbox-marked-outline: Yes | `None` |


## Metrics

> Metrics Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| apm_server | [APMServer](#apmserver) | APM server configuration | :material-checkbox-marked-outline: Yes | See [APMServer](#apmserver) for more details. |


## OAuth

> OAuth Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| enabled | Boolean | Enable use of OAuth? | :material-checkbox-marked-outline: Yes | `None` |
| gravatar_enabled | Boolean | Enable gravatar? | :material-checkbox-marked-outline: Yes | `None` |
| providers | Mapping [[OAuthProvider](#oauthprovider)] | OAuth provider configuration | :material-checkbox-marked-outline: Yes | See [OAuthProvider](#oauthprovider) for more details. |
| strict_apikeys | Boolean | Only allow apikeys that last as long as the access token used to log in | :material-checkbox-marked-outline: Yes | `False` |


## OAuthAutoProperty

> None

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| field | Keyword | Field to apply `pattern` to | :material-checkbox-marked-outline: Yes | `None` |
| pattern | Keyword | Regex pattern for auto-prop assignment | :material-checkbox-marked-outline: Yes | `None` |
| type | Enum | Type of property assignment on pattern match<br>Values:<br>`"access", "classification", "role"` | :material-checkbox-marked-outline: Yes | `None` |
| value | Keyword | Assigned property value | :material-checkbox-marked-outline: Yes | `None` |


## OAuthProvider

> OAuth Provider Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| auto_create | Boolean | Auto-create users if they are missing | :material-checkbox-marked-outline: Yes | `True` |
| auto_sync | Boolean | Should we automatically sync with OAuth provider? | :material-checkbox-marked-outline: Yes | `False` |
| auto_properties | List [[OAuthAutoProperty](#oauthautoproperty)] | Automatic role and classification assignments | :material-checkbox-marked-outline: Yes | `[]` |
| uid_randomize | Boolean | Should we generate a random username for the authenticated user? | :material-checkbox-marked-outline: Yes | `False` |
| uid_randomize_digits | Integer | How many digits should we add at the end of the username? | :material-checkbox-marked-outline: Yes | `0` |
| uid_randomize_delimiter | Keyword | What is the delimiter used by the random name generator? | :material-checkbox-marked-outline: Yes | `-` |
| uid_regex | Keyword | Regex used to parse an email address and capture parts to create a user ID out of it | :material-minus-box-outline: Optional | `None` |
| uid_format | Keyword | Format of the user ID based on the captured parts from the regex | :material-minus-box-outline: Optional | `None` |
| client_id | Keyword | ID of your application to authenticate to the OAuth provider | :material-minus-box-outline: Optional | `None` |
| client_secret | Keyword | Password to your application to authenticate to the OAuth provider | :material-minus-box-outline: Optional | `None` |
| request_token_url | Keyword | URL to request token | :material-minus-box-outline: Optional | `None` |
| request_token_params | Keyword | Parameters to request token | :material-minus-box-outline: Optional | `None` |
| required_groups | List [Keyword] | The groups the JWT must contain in order to allow access | :material-checkbox-marked-outline: Yes | `[]` |
| role_map | Mapping [Keyword] | A mapping of OAuth groups to howler roles | :material-checkbox-marked-outline: Yes | `{}` |
| access_token_url | Keyword | URL to get access token | :material-minus-box-outline: Optional | `None` |
| access_token_params | Keyword | Parameters to get access token | :material-minus-box-outline: Optional | `None` |
| authorize_params | Keyword | Parameters used to authorize access to a resource | :material-minus-box-outline: Optional | `None` |
| api_base_url | Keyword | Base URL for downloading the user's and groups info | :material-minus-box-outline: Optional | `None` |
| audience | Keyword | The audience to validate against. Only must be set if audience is different than the client id. | :material-minus-box-outline: Optional | `None` |
| scope | Keyword | The scope to validate against | :material-checkbox-marked-outline: Yes | `None` |
| picture_url | Keyword | URL for downloading the user's profile | :material-minus-box-outline: Optional | `None` |
| groups_url | Keyword | URL for accessing additional data about the user's groups | :material-minus-box-outline: Optional | `None` |
| groups_key | Keyword | Path to the list of groups in the response returned from groups_url | :material-minus-box-outline: Optional | `None` |
| iss | Keyword | Optional issuer field for JWT validation | :material-minus-box-outline: Optional | `None` |
| jwks_uri | Keyword | URL used to verify if a returned JWKS token is valid | :material-checkbox-marked-outline: Yes | `None` |
| user_get | Keyword | Path from the base_url to fetch the user info | :material-minus-box-outline: Optional | `None` |


## PasswordRequirement

> Password Requirement

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| lower | Boolean | Password must contain lowercase letters | :material-checkbox-marked-outline: Yes | `None` |
| number | Boolean | Password must contain numbers | :material-checkbox-marked-outline: Yes | `None` |
| special | Boolean | Password must contain special characters | :material-checkbox-marked-outline: Yes | `None` |
| upper | Boolean | Password must contain uppercase letters | :material-checkbox-marked-outline: Yes | `None` |
| min_length | Integer | Minimum password length | :material-checkbox-marked-outline: Yes | `None` |


## Redis

> Redis Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| nonpersistent | [RedisServer](#redisserver) | A volatile Redis instance | :material-checkbox-marked-outline: Yes | See [RedisServer](#redisserver) for more details. |
| persistent | [RedisServer](#redisserver) | A persistent Redis instance | :material-checkbox-marked-outline: Yes | See [RedisServer](#redisserver) for more details. |


## RedisServer

> Redis Service configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| host | Keyword | Hostname of Redis instance | :material-checkbox-marked-outline: Yes | `None` |
| port | Integer | Port of Redis instance | :material-checkbox-marked-outline: Yes | `None` |


## Retention

> Retention Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| enabled | Boolean | Whether to enable the hit retention limit. If enabled, hits will be purged after the specified duration. | :material-checkbox-marked-outline: Yes | `True` |
| limit_unit | Enum | The unit to use when computing the retention limit<br>Values:<br>`"days", "hours", "microseconds", "milliseconds", "minutes", "seconds", "weeks"` | :material-checkbox-marked-outline: Yes | `days` |
| limit_amount | Integer | The number of limit_units to use when computing the retention limit | :material-checkbox-marked-outline: Yes | `350` |
| crontab | Keyword | The crontab that denotes how often to run the retention job | :material-checkbox-marked-outline: Yes | `0 0 * * *` |


## System

> System Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| type | Enum | Type of system<br>Values:<br>`"development", "production", "staging"` | :material-checkbox-marked-outline: Yes | `None` |
| retention | [Retention](#retention) | Retention Configuration | :material-checkbox-marked-outline: Yes | See [Retention](#retention) for more details. |


## UI

> UI Configuration

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| audit | Boolean | Should API calls be audited and saved to a separate log file? | :material-checkbox-marked-outline: Yes | `None` |
| banner | Mapping [Keyword] | Banner message display on the main page (format: {<language_code>: message}) | :material-minus-box-outline: Optional | `None` |
| banner_level | Enum | Banner message level<br>Values:<br>`"error", "info", "success", "warning"` | :material-checkbox-marked-outline: Yes | `None` |
| debug | Boolean | Enable debugging? | :material-checkbox-marked-outline: Yes | `None` |
| static_folder | Keyword | The directory where static assets are stored. | :material-minus-box-outline: Optional | `None` |
| discover_url | Keyword | Discover URL | :material-minus-box-outline: Optional | `None` |
| email | Email | Assemblyline admins email address | :material-minus-box-outline: Optional | `None` |
| enforce_quota | Boolean | Enforce the user's quotas? | :material-checkbox-marked-outline: Yes | `None` |
| secret_key | Keyword | Flask secret key to store cookies, etc. | :material-checkbox-marked-outline: Yes | `None` |
| validate_session_ip | Boolean | Validate if the session IP matches the IP the session was created from | :material-checkbox-marked-outline: Yes | `None` |
| validate_session_useragent | Boolean | Validate if the session useragent matches the useragent the session was created with | :material-checkbox-marked-outline: Yes | `None` |
| websocket_url | Keyword | The url to hit when emitting websocket events on the cluster | :material-minus-box-outline: Optional | `None` |
