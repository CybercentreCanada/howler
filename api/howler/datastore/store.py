from __future__ import annotations

import logging
import os
import re
from os import environ
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urlparse

import elasticsearch

from howler.common.logging.format import HWL_DATE_FORMAT, HWL_LOG_FORMAT
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.config import Config
from howler.odm.models.config import config as _config

TRANSPORT_TIMEOUT = int(environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT", "10"))
CERTS_PATH = Path(os.environ.get("HWL_CERT_DIRECTORY", "/etc/howler/certs"))

logger = logging.getLogger("howler.datastore.store")
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
logger.addHandler(console)


class ESStore(object):
    """Elasticsearch multi-index datastore backed by one or more ES hosts.

    Manages connections, collection caching, model registration, and date-math
    helpers for Howler's Elasticsearch indices.

    Attributes:
        DEFAULT_SORT: Default sort order for queries.
        DATE_FORMAT: Mapping of abstract time-unit names to ES date-math tokens.
        DATEMATH_MAP: Mapping used by ``to_pydatemath`` to convert internal
            date-math expressions into ES-compatible strings.
        ID: Name of the document identifier field.
    """

    DEFAULT_SORT = "id asc"
    DATE_FORMAT = {
        "NOW": "now",
        "YEAR": "y",
        "MONTH": "M",
        "WEEK": "w",
        "DAY": "d",
        "HOUR": "h",
        "MINUTE": "m",
        "SECOND": "s",
        "MILLISECOND": "ms",
        "MICROSECOND": "micros",
        "NANOSECOND": "nanos",
        "SEPARATOR": "||",
        "DATE_END": "Z",
    }
    DATEMATH_MAP = {
        "NOW": "now",
        "YEAR": "y",
        "MONTH": "M",
        "WEEK": "w",
        "DAY": "d",
        "HOUR": "h",
        "MINUTE": "m",
        "SECOND": "s",
        "DATE_END": "Z||",
    }
    ID = "id"

    def __init__(self, config: Optional[Config] = None, archive_access=True):
        """Initialise the store and open an Elasticsearch connection.

        Host addresses, TLS certificates, API keys, and basic-auth credentials
        are resolved from the supplied ``config`` and from environment variables
        named ``<HOST>_HOST_APIKEY_ID`` / ``<HOST>_HOST_APIKEY_SECRET`` or
        ``<HOST>_HOST_USERNAME`` / ``<HOST>_HOST_PASSWORD``.

        Args:
            config: Application configuration.  Falls back to the global
                ``howler.odm.models.config.config`` singleton when ``None``.
            archive_access: Whether archive indices should be accessible.
        """
        if not config:
            config = _config

        self._apikey: Optional[tuple[str, str]] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._hosts = []
        self._cert: str | None = None
        self._fingerprint: str | None = None

        for host in config.datastore.hosts:
            self._hosts.append(str(host))

            cert = CERTS_PATH / f"{host.name}.crt"
            if cert.exists():
                if self._cert is None:
                    self._cert = str(cert)
                    logger.info("Using certificate %s for elasticsearch network traffic", self._cert)
                else:
                    logger.error("Only a single certificate path is supported - ignoring additional paths.")
                    logger.error(
                        "If you have multiple certificates, bundle them into a single .pem file and specify "
                        "it for the first host."
                    )

            if host.fingerprint:
                if self._fingerprint is None:
                    self._fingerprint = host.fingerprint
                    logger.info("Using certificate fingerprint %s for elasticsearch network traffic", self._fingerprint)
                else:
                    logger.error(
                        "Only a single certificate fingerprint is supported - ignoring additional fingerprints."
                    )

            if os.getenv(f"{host.name.upper()}_HOST_APIKEY_ID", None) is not None:
                self._apikey = (
                    os.environ[f"{host.name.upper()}_HOST_APIKEY_ID"],
                    os.environ[f"{host.name.upper()}_HOST_APIKEY_SECRET"],
                )
            elif os.getenv(f"{host.name.upper()}_HOST_USERNAME") is not None:
                self._username = os.environ[f"{host.name.upper()}_HOST_USERNAME"]
                self._password = os.environ[f"{host.name.upper()}_HOST_PASSWORD"]

        self._closed = False
        self._collections: dict[str, ESCollection] = {}
        self._models: dict[str, Any] = {}
        self.validate = True

        tracer = logging.getLogger("elasticsearch")
        tracer.setLevel(logging.CRITICAL)

        self.client = self.__build_connection()
        self.archive_access = archive_access
        self.url_path = "elastic"

    def __enter__(self):
        return self

    def __exit__(self, ex_type, exc_val, exc_tb):
        self.close()

    def __str__(self):
        return "{0} - {1}".format(self.__class__.__name__, self._hosts)

    def __getitem__(self, name: str) -> ESCollection:
        return self.__getattr__(name)

    def __getattr__(self, name: str) -> ESCollection:
        """Return the ``ESCollection`` registered under *name*.

        Collections are cached after the first access when validation is
        enabled.

        Args:
            name: Registered collection (index) name.

        Returns:
            The ``ESCollection`` instance for *name*.

        Raises:
            KeyError: If *name* has not been registered via ``register``.
        """
        if not self.validate:
            return ESCollection(self, name, model_class=self._models[name], validate=self.validate)

        if name not in self._collections:
            self._collections[name] = ESCollection(self, name, model_class=self._models[name], validate=self.validate)

        return self._collections[name]

    @property
    def now(self):
        return self.DATE_FORMAT["NOW"]

    @property
    def ms(self):
        return self.DATE_FORMAT["MILLISECOND"]

    @property
    def us(self):
        return self.DATE_FORMAT["MICROSECOND"]

    @property
    def ns(self):
        return self.DATE_FORMAT["NANOSECOND"]

    @property
    def year(self):
        return self.DATE_FORMAT["YEAR"]

    @property
    def month(self):
        return self.DATE_FORMAT["MONTH"]

    @property
    def week(self):
        return self.DATE_FORMAT["WEEK"]

    @property
    def day(self):
        return self.DATE_FORMAT["DAY"]

    @property
    def hour(self):
        return self.DATE_FORMAT["HOUR"]

    @property
    def minute(self):
        return self.DATE_FORMAT["MINUTE"]

    @property
    def second(self):
        return self.DATE_FORMAT["SECOND"]

    @property
    def date_separator(self):
        return self.DATE_FORMAT["SEPARATOR"]

    def __build_connection(self) -> elasticsearch.Elasticsearch:
        """Create a new ``Elasticsearch`` client from stored credentials.

        Authentication is selected automatically: API-key auth is preferred,
        then basic auth, then anonymous.

        Returns:
            A freshly constructed ``Elasticsearch`` client.
        """
        if self._apikey is not None:
            return elasticsearch.Elasticsearch(
                hosts=self._hosts,  # type: ignore
                ca_certs=self._cert,  # type: ignore
                ssl_assert_fingerprint=self._fingerprint,  # type: ignore
                api_key=self._apikey,
                max_retries=0,
                request_timeout=TRANSPORT_TIMEOUT,
            )
        elif self._username is not None and self._password is not None:
            return elasticsearch.Elasticsearch(
                hosts=self._hosts,  # type: ignore
                ca_certs=self._cert,  # type: ignore
                ssl_assert_fingerprint=self._fingerprint,  # type: ignore
                basic_auth=(self._username, self._password),
                max_retries=0,
                request_timeout=TRANSPORT_TIMEOUT,
            )
        else:
            return elasticsearch.Elasticsearch(
                hosts=self._hosts,  # type: ignore
                ca_certs=self._cert,  # type: ignore
                ssl_assert_fingerprint=self._fingerprint,  # type: ignore
                max_retries=0,
                request_timeout=TRANSPORT_TIMEOUT,
            )

    def connection_reset(self):
        """Replace the current ES client with a fresh connection."""
        self.client = self.__build_connection()

    def close(self):
        """Mark the store as closed and release the ES client.

        After calling this method any attempt to use the client will raise
        an ``AttributeError``.
        """
        self._closed = True
        # Flatten the client object so that attempts to access without reconnecting errors hard
        # But 'cast' it so that mypy and other linters don't think that its normal for client to be None
        self.client = cast(elasticsearch.Elasticsearch, None)

    def get_hosts(self, safe=False):
        """Return the list of configured ES host addresses.

        Args:
            safe: When ``True``, strip the scheme and port from each URL and
                return only hostnames.

        Returns:
            A list of host strings.
        """
        if not safe:
            return self._hosts
        else:
            out = []
            for h in self._hosts:
                parsed = urlparse(h)
                out.append(parsed.hostname or parsed.path)
            return out

    def get_models(self):
        """Return the mapping of registered collection names to model classes."""
        return self._models

    def is_closed(self):
        """Return ``True`` if the store has been closed."""
        return self._closed

    def ping(self):
        """Ping the Elasticsearch cluster.

        Returns:
            ``True`` if the cluster responded successfully.
        """
        return self.client.ping()

    def register(self, name: str, model_class=None):
        """Register a collection (index) name and its optional ODM model class.

        Args:
            name: Collection name.  Must contain only lowercase letters, digits,
                and underscores.
            model_class: ODM model class used for validation and serialisation.
                ``None`` disables model-level validation for this collection.

        Raises:
            DataStoreException: If *name* contains invalid characters.
        """
        name_match = re.match(r"[a-z0-9_]*", name)
        if not name_match or name_match.string != name:
            raise DataStoreException(
                "Invalid characters in model name. You can only use lower case letters, numbers and underscores."
            )

        self._models[name] = model_class

    def to_pydatemath(self, value):
        """Convert an internal date-math expression to ES date-math syntax.

        Args:
            value: String containing abstract date-math tokens (e.g.
                ``"NOW-1DAY"``).

        Returns:
            The equivalent Elasticsearch date-math string (e.g.
            ``"now-1d"``).
        """
        replace_list = [
            (self.now, self.DATEMATH_MAP["NOW"]),
            (self.year, self.DATEMATH_MAP["YEAR"]),
            (self.month, self.DATEMATH_MAP["MONTH"]),
            (self.week, self.DATEMATH_MAP["WEEK"]),
            (self.day, self.DATEMATH_MAP["DAY"]),
            (self.hour, self.DATEMATH_MAP["HOUR"]),
            (self.minute, self.DATEMATH_MAP["MINUTE"]),
            (self.second, self.DATEMATH_MAP["SECOND"]),
            (self.DATE_FORMAT["DATE_END"], self.DATEMATH_MAP["DATE_END"]),
        ]

        for x in replace_list:
            value = value.replace(*x)

        return value
