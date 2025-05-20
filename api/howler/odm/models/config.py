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
    host: str = Field(description="Hostname of Redis instance")
    port: int = Field(description="Port of Redis instance")


class Redis(BaseModel):
    nonpersistent: RedisServer = Field(
        default=RedisServer(host="127.0.0.1", port=6379), description="A volatile Redis instance"
    )

    persistent: RedisServer = Field(
        default=RedisServer(host="127.0.0.1", port=6380), description="A persistent Redis instance"
    )


class Host(BaseModel):
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
    hosts: list[Host] = Field(
        default=[Host(name="elastic", username="elastic", password="devpass", scheme="http", host="localhost:9200")],  # noqa: S106
        description="List of hosts used for the datastore",
    )
    type: Literal["elasticsearch"] = Field(
        default="elasticsearch", description="Type of application used for the datastore"
    )


class Logging(BaseModel):
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
    lower: bool = Field(default=False, description="Password must contain lowercase letters")
    number: bool = Field(default=False, description="Password must contain numbers")
    special: bool = Field(default=False, description="Password must contain special characters")
    upper: bool = Field(default=False, description="Password must contain uppercase letters")
    min_length: int = Field(default=12, description="Minimum password length")


class Internal(BaseModel):
    enabled: bool = Field(default=True, description="Internal authentication allowed?")
    failure_ttl: int = Field(
        default=60, description="How long to wait after `max_failures` before re-attempting login?"
    )
    max_failures: int = Field(default=5, description="Maximum number of fails allowed before timeout")
    password_requirements: PasswordRequirement = PasswordRequirement()


class OAuthAutoProperty(BaseModel):
    field: str = Field(description="Field to apply `pattern` to")
    pattern: str = Field(description="Regex pattern for auto-prop assignment")
    type: Literal["access", "classification", "role"] = Field(
        description="Type of property assignment on pattern match",
    )
    value: str = Field(description="Assigned property value")


class OAuthProvider(BaseModel):
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
    "APM server configuration"

    server_url: Optional[str] = Field(default=None, description="URL to API server")
    token: Optional[str] = Field(default=None, description="Authentication token for server")


class Metrics(BaseModel):
    apm_server: APMServer = APMServer()


class Retention(BaseModel):
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


class System(BaseModel):
    type: Literal["production", "staging", "development"] = Field(default="development", description="Type of system")
    retention: Retention = Retention()
    "Retention Configuration"


class UI(BaseModel):
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
    enabled: bool = Field(default=False, description="Should nbgallery notebook integration be enabled?")

    scope: Optional[str] = Field(default=None, description="The scope expected by nbgallery for JWTs")

    url: str = Field(
        default="http://nbgallery.nbgallery.svc.cluster.local:3000", description="The url to connect to nbgallery at"
    )


class Core(BaseModel):
    plugins: list[str] = Field(description="A list of external plugins to load", default=[])

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
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / "config.yml",
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
    auth: Auth = Auth()
    core: Core = Core()
    datastore: Datastore = Datastore()
    logging: Logging = Logging()
    system: System = System()
    ui: UI = UI()

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
