# mypy: ignore-errors
import logging
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

from howler.common.logging.format import HWL_DATE_FORMAT, HWL_LOG_FORMAT

APP_NAME = os.environ.get("APP_NAME", "howler")

logger = logging.getLogger("howler.odm.models.config")
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
logger.addHandler(console)


class RedisServer(BaseModel):
    """Configuration for a single Redis server instance.

    Defines the connection parameters for a Redis server, including
    the hostname and port number.
    """

    host: str = Field(description="Hostname of Redis instance")
    port: int = Field(description="Port of Redis instance")


class Redis(BaseModel):
    """Redis configuration for Howler.

    Defines connections to both persistent and non-persistent Redis instances.
    The non-persistent instance is used for volatile data like caches, while
    the persistent instance is used for data that needs to survive restarts.
    """

    nonpersistent: RedisServer = Field(
        default=RedisServer(host="127.0.0.1", port=6379), description="A volatile Redis instance"
    )

    persistent: RedisServer = Field(
        default=RedisServer(host="127.0.0.1", port=6380), description="A persistent Redis instance"
    )


class Host(BaseModel):
    """Configuration for a remote host connection.

    Defines connection parameters for external services, including authentication
    credentials (username/password or API key) and connection details.
    Environment variables can override username and password using the pattern
    {NAME}_HOST_USERNAME and {NAME}_HOST_PASSWORD.
    """

    name: str = Field(description="Name of the host")
    username: Optional[str] = Field(description="Username to login with", default=None)
    password: Optional[str] = Field(description="Password to login with", default=None)
    apikey_id: Optional[str] = Field(description="ID of the API Key to use when connecting", default=None)
    apikey_secret: Optional[str] = Field(description="Secret data of the API Key to use when connecting", default=None)
    scheme: Optional[str] = Field(description="Scheme to use when connecting", default="http")
    host: str = Field(description="URL to connect to")

    def __repr__(self):
        result = ""

        if self.scheme:
            result += f"{self.scheme}://"

        username = os.getenv(f"{self.name.upper()}_HOST_USERNAME", self.username)
        password = os.getenv(f"{self.name.upper()}_HOST_PASSWORD", self.password)

        if username and password:
            result += f"{username}:{password}@"

        result += self.host

        return result

    def __str__(self):
        return self.__repr__()


class Datastore(BaseModel):
    """Datastore configuration for Howler.

    Defines the backend datastore used by Howler for storing hits and metadata.
    Currently supports Elasticsearch as the datastore type.
    """

    hosts: list[Host] = Field(
        default=[Host(name="elastic", username="elastic", password="devpass", scheme="http", host="localhost:9200")],  # noqa: S106
        description="List of hosts used for the datastore",
    )
    type: Literal["elasticsearch"] = Field(
        default="elasticsearch", description="Type of application used for the datastore"
    )


class Logging(BaseModel):
    """Logging configuration for Howler.

    Defines how and where Howler logs should be output, including console,
    file, and syslog destinations. Also controls log level, format, and
    metric export intervals.
    """

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "DISABLED"] = Field(
        default="INFO",
        description="What level of logging should we have?",
    )
    log_to_console: bool = Field(default=True, description="Should we log to console?")
    log_to_file: bool = Field(default=False, description="Should we log to files on the server?")
    log_directory: str = Field(
        default=f"/var/log/{APP_NAME.replace('-dev', '')}/",
        description="If `log_to_file: true`, what is the directory to store logs?",
    )
    log_to_syslog: bool = Field(default=False, description="Should logs be sent to a syslog server?")
    syslog_host: str = Field(
        default="localhost", description="If `log_to_syslog: true`, provide hostname/IP of the syslog server?"
    )
    syslog_port: int = Field(default=514, description="If `log_to_syslog: true`, provide port of the syslog server?")
    export_interval: int = Field(default=5, description="How often, in seconds, should counters log their values?")
    log_as_json: bool = Field(default=True, description="Log in JSON format?")


class PasswordRequirement(BaseModel):
    """Password complexity requirements for internal authentication.

    Defines the rules for password creation and validation, including
    character type requirements and minimum length.
    """

    lower: bool = Field(default=False, description="Password must contain lowercase letters")
    number: bool = Field(default=False, description="Password must contain numbers")
    special: bool = Field(default=False, description="Password must contain special characters")
    upper: bool = Field(default=False, description="Password must contain uppercase letters")
    min_length: int = Field(default=12, description="Minimum password length")


class Internal(BaseModel):
    """Internal authentication configuration.

    Defines settings for Howler's built-in username/password authentication,
    including password requirements and brute-force protection via login
    failure tracking.
    """

    enabled: bool = Field(default=True, description="Internal authentication allowed?")
    failure_ttl: int = Field(
        default=60, description="How long to wait after `max_failures` before re-attempting login?"
    )
    max_failures: int = Field(default=5, description="Maximum number of fails allowed before timeout")
    password_requirements: PasswordRequirement = PasswordRequirement()


class OAuthAutoProperty(BaseModel):
    """Automatic property assignment based on OAuth attributes.

    Defines rules for automatically assigning user properties (roles,
    classifications, or access levels) based on pattern matching against
    OAuth provider data.
    """

    field: str = Field(description="Field to apply `pattern` to")
    pattern: str = Field(description="Regex pattern for auto-prop assignment")
    type: Literal["access", "classification", "role"] = Field(
        description="Type of property assignment on pattern match",
    )
    value: str = Field(description="Assigned property value")


class OAuthProvider(BaseModel):
    """OAuth provider configuration.

    Defines the connection and authentication settings for an OAuth 2.0 provider.
    Includes user auto-creation, group mapping, JWT validation, and various
    OAuth endpoints required for the authentication flow.
    """

    auto_create: bool = Field(default=True, description="Auto-create users if they are missing")
    auto_sync: bool = Field(default=False, description="Should we automatically sync with OAuth provider?")
    auto_properties: list[OAuthAutoProperty] = Field(
        default=[],
        description="Automatic role and classification assignments",
    )
    uid_randomize: bool = Field(
        default=False,
        description="Should we generate a random username for the authenticated user?",
    )
    uid_randomize_digits: int = Field(
        default=0,
        description="How many digits should we add at the end of the username?",
    )
    uid_randomize_delimiter: str = Field(
        default="-",
        description="What is the delimiter used by the random name generator?",
    )
    uid_regex: Optional[str] = Field(
        default=None,
        description="Regex used to parse an email address and capture parts to create a user ID out of it",
    )
    uid_format: Optional[str] = Field(
        default=None,
        description="Format of the user ID based on the captured parts from the regex",
    )
    client_id: Optional[str] = Field(
        default=None,
        description="ID of your application to authenticate to the OAuth provider",
    )
    client_secret: Optional[str] = Field(
        default=None,
        description="Password to your application to authenticate to the OAuth provider",
    )
    request_token_url: Optional[str] = Field(default=None, description="URL to request token")
    request_token_params: Optional[str] = Field(default=None, description="Parameters to request token")
    required_groups: list[str] = Field(
        default=[],
        description="The groups the JWT must contain in order to allow access",
    )
    role_map: dict[str, str] = Field(
        default={},
        description="A mapping of OAuth groups to howler roles",
    )
    access_token_url: Optional[str] = Field(default=None, description="URL to get access token")
    access_token_params: Optional[str] = Field(default=None, description="Parameters to get access token")
    authorize_url: Optional[str] = Field(default=None, description="URL used to authorize access to a resource")
    authorize_params: Optional[str] = Field(
        default=None, description="Parameters used to authorize access to a resource"
    )
    api_base_url: Optional[str] = Field(default=None, description="Base URL for downloading the user's and groups info")
    audience: Optional[str] = Field(
        default=None,
        description="The audience to validate against. Only must be set if audience is different than the client id.",
    )
    scope: str = Field(description="The scope to validate against")
    picture_url: Optional[str] = Field(default=None, description="URL for downloading the user's profile")
    groups_url: Optional[str] = Field(
        default=None,
        description="URL for accessing additional data about the user's groups",
    )
    groups_key: Optional[str] = Field(
        default=None,
        description="Path to the list of groups in the response returned from groups_url",
    )
    iss: Optional[str] = Field(default=None, description="Optional issuer field for JWT validation")
    jwks_uri: str = Field(description="URL used to verify if a returned JWKS token is valid")
    user_get: Optional[str] = Field(default=None, description="Path from the base_url to fetch the user info")


class OAuth(BaseModel):
    """OAuth authentication configuration.

    Top-level OAuth settings including enabling/disabling OAuth authentication,
    Gravatar integration, and a dictionary of configured OAuth providers.
    Also controls API key lifetime restrictions for OAuth-authenticated users.
    """

    enabled: bool = Field(default=False, description="Enable use of OAuth?")
    gravatar_enabled: bool = Field(default=True, description="Enable gravatar?")
    providers: dict[str, OAuthProvider] = Field(
        default={},
        description="OAuth provider configuration",
    )
    strict_apikeys: bool = Field(
        description="Only allow apikeys that last as long as the access token used to log in",
        default=False,
    )


class Auth(BaseModel):
    """Authentication configuration for Howler.

    Configures all authentication methods supported by Howler, including
    internal username/password authentication and OAuth providers. Also
    controls API key settings and restrictions.
    """

    allow_apikeys: bool = Field(default=True, description="Allow API keys?")
    allow_extended_apikeys: bool = Field(default=True, description="Allow extended API keys?")
    max_apikey_duration_amount: Optional[int] = Field(
        default=None, description="Amount of unit of maximum duration for API keys"
    )
    max_apikey_duration_unit: Optional[Literal["seconds", "minutes", "hours", "days", "weeks"]] = Field(
        default=None,
        description="Unit of maximum duration for API keys",
    )
    internal: Internal = Internal()
    oauth: OAuth = OAuth()


class APMServer(BaseModel):
    """Application Performance Monitoring (APM) server configuration.

    Defines the connection details for an external APM server used to
    collect and analyze application performance metrics.
    """

    server_url: Optional[str] = Field(default=None, description="URL to API server")
    token: Optional[str] = Field(default=None, description="Authentication token for server")


class Metrics(BaseModel):
    """Metrics collection configuration.

    Configures how Howler collects and exports application metrics,
    including integration with external APM servers.
    """

    apm_server: APMServer = APMServer()


class Retention(BaseModel):
    """Hit retention policy configuration.

    Defines the automatic data retention policy for hits, including
    the maximum age of hits before they are purged and the schedule
    for running the retention cleanup job.
    """

    enabled: bool = Field(
        default=True,
        description=(
            "Whether to enable the hit retention limit. If enabled, hits will "
            "be purged after the specified duration."
        ),
    )
    limit_unit: Literal["days", "seconds", "microseconds", "milliseconds", "minutes", "hours", "weeks"] = Field(
        description="The unit to use when computing the retention limit",
        default="days",
    )
    limit_amount: int = Field(
        default=350,
        description="The number of limit_units to use when computing the retention limit",
    )
    crontab: str = Field(
        default="0 0 * * *",
        description="The crontab that denotes how often to run the retention job",
    )


class ViewCleanup(BaseModel):
    """View cleanup job configuration.

    Defines the schedule and behavior for cleaning up stale dashboard views
    that reference non-existent backend data.
    """

    enabled: bool = Field(
        default=True,
        description=(
            "Whether to enable the view cleanup. If enabled, views pinned "
            "to the dashboard that no longer exist in the backend will be cleared."
        ),
    )
    crontab: str = Field(
        default="0 0 * * *",
        description="The crontab that denotes how often to run the view_cleanup job",
    )


class System(BaseModel):
    """System-level configuration for Howler.

    Defines global system settings including deployment type (production,
    staging, or development) and configuration for automated maintenance
    jobs like data retention and view cleanup.
    """

    type: Literal["production", "staging", "development"] = Field(default="development", description="Type of system")
    retention: Retention = Retention()
    "Retention Configuration"
    view_cleanup: ViewCleanup = ViewCleanup()
    "View Cleanup Configuration"


class UI(BaseModel):
    """User interface and web server configuration.

    Defines settings for the Howler web UI including Flask configuration,
    session validation, API auditing, static file locations, and WebSocket
    integration for real-time updates.
    """

    audit: bool = Field(description="Should API calls be audited and saved to a separate log file?", default=True)
    debug: bool = Field(default=False, description="Enable debugging?")
    static_folder: Optional[str] = Field(
        default=os.path.dirname(__file__) + "/../../../static",
        description="The directory where static assets are stored.",
    )
    discover_url: Optional[str] = Field(default=None, description="Discovery URL")
    enforce_quota: bool = Field(default=True, description="Enforce the user's quotas?")
    secret_key: str = Field(
        default=os.environ.get("FLASK_SECRET_KEY", "This is the default flask secret key... you should change this!"),
        description="Flask secret key to store cookies, etc.",
    )
    validate_session_ip: bool = Field(
        default=True, description="Validate if the session IP matches the IP the session was created from"
    )
    validate_session_useragent: bool = Field(
        default=True, description="Validate if the session useragent matches the useragent the session was created with"
    )
    websocket_url: Optional[str] = Field(
        default=None,
        description="The url to hit when emitting websocket events on the cluster",
    )


class Borealis(BaseModel):
    """Borealis enrichment service integration configuration.

    Defines settings for integrating with Borealis, an external enrichment
    service that can provide additional context and status information for
    hits displayed in the Howler UI.
    """

    enabled: bool = Field(default=False, description="Should borealis integration be enabled?")

    url: str = Field(
        default="http://enrichment-rest.enrichment.svc.cluster.local:5000",
        description="What url should Howler connect to to interact with Borealis?",
    )

    status_checks: list[str] = Field(
        default=[],
        description="A list of borealis fetchers that return status results given a Howler ID to show in the UI.",
    )


class Notebook(BaseModel):
    """Jupyter notebook integration configuration.

    Defines settings for integrating with nbgallery, a collaborative
    Jupyter notebook platform, allowing users to access and share
    notebooks related to their Howler analysis work.
    """

    enabled: bool = Field(default=False, description="Should nbgallery notebook integration be enabled?")

    scope: Optional[str] = Field(default=None, description="The scope expected by nbgallery for JWTs")

    url: str = Field(
        default="http://nbgallery.nbgallery.svc.cluster.local:3000", description="The url to connect to nbgallery at"
    )


class Core(BaseModel):
    """Core application configuration for Howler.

    Aggregates all core service configurations including Redis, metrics,
    and external integrations like Borealis and nbgallery notebooks.
    Also manages the loading of external plugins.
    """

    plugins: set[str] = Field(description="A list of external plugins to load", default=set())

    metrics: Metrics = Metrics()
    "Configuration for Metrics Collection"

    redis: Redis = Redis()
    "Configuration for Redis instances"

    borealis: Borealis = Borealis()
    "Configuration for Borealis Integration"

    notebook: Notebook = Notebook()
    "Configuration for Notebook Integration"


root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    root_path / "conf" / "config.yml",
    root_path / "conf" / "mappings.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / "config.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / "mappings.yml",
]

if os.getenv("AZURE_TEST_CONFIG", None) is not None:
    import re

    logger.info("Azure build environment detected, adding additional config path")

    work_dir_parent = Path("/__w")
    work_dir: Path | None = None
    for sub_path in work_dir_parent.iterdir():
        if not sub_path.is_dir():
            continue

        logger.info("Testing sub path %s", sub_path)

        if re.match(r"\d+", str(sub_path.name)):
            work_dir = work_dir_parent / sub_path

        if work_dir is not None:
            logger.info("Subpath %s exists, checking for test path", work_dir)
            test_config_path = work_dir / "s" / "test" / "config" / "config.yml"

            if test_config_path.exists():
                config_locations.append(test_config_path)
                logger.info("Path %s added as config path", test_config_path)
                break

            logger.error("Config path not found at path %s", test_config_path)
            logger.info("Available files:\n%s", "\n".join(sorted(str(path) for path in (work_dir / "s").glob("**/*"))))
            work_dir = None

logger.info("Fetching configuration files from %s", ":".join(str(c) for c in config_locations))


class Config(BaseSettings):
    """Main Howler configuration model.

    The root configuration object that aggregates all configuration sections
    including authentication, datastore, logging, system settings, UI, and core
    services. Configuration can be loaded from YAML files or environment variables
    with the HWL_ prefix.

    Environment variables use double underscores (__) for nested properties.
    For example: HWL_DATASTORE__TYPE=elasticsearch
    """

    auth: Auth = Auth()
    core: Core = Core()
    datastore: Datastore = Datastore()
    logging: Logging = Logging()
    system: System = System()
    ui: UI = UI()
    mapping: dict[str, str] = Field(description="Mapping of alert keys to borealis type", default={})

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix="hwl_",
    )

    @classmethod
    def settings_customise_sources(
        cls,  # noqa: ANN102
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN002, ANN102
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        "Adds a YamlConfigSettingsSource object at the end of the settings_customize_sources response."
        return (*super().settings_customise_sources(*args, **kwargs), YamlConfigSettingsSource(cls))


config = Config()

if __name__ == "__main__":
    # When executed, the config model will print the default values of the configuration
    import yaml

    print(yaml.safe_dump(Config().model_dump(mode="json")))  # noqa: T201
