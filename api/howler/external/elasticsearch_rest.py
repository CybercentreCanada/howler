"""Small, read-only Elasticsearch REST client for cross-major-version checks."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HOWLER_COLLECTION_NAMES = (
    "hit",
    "event",
    "case",
    "template",
    "overview",
    "analytic",
    "action",
    "migration",
    "user",
    "view",
    "dossier",
    "user_avatar",
)
SOURCE_STACK_VERSION = "8.19.11"
NO_MIGRATION_NEEDED = "NO_MIGRATION_NEEDED"


def _validate_credentials(api_key: str | None, username: str | None, password: str | None) -> None:
    if api_key and (username or password):
        raise ValueError("Use either ELASTIC_API_KEY or ELASTIC_USERNAME/ELASTIC_PASSWORD, not both.")
    if bool(username) != bool(password):
        raise ValueError("ELASTIC_USERNAME and ELASTIC_PASSWORD must be set together.")


class ElasticsearchRestError(RuntimeError):
    """A sanitized Elasticsearch HTTP or transport error."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_type: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.reason = reason


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not forward credentials to a redirected endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class ElasticsearchRestClient:
    """A minimal JSON REST client that can issue GET requests only."""

    READ_METHODS = frozenset({"GET"})

    def __init__(  # noqa: C901
        self,
        url: str,
        *,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        ca_certs: Path | None = None,
        insecure: bool = False,
        timeout: int = 60,
        allow_insecure_http_auth: bool = False,
    ) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Elasticsearch URL must include an http(s) scheme and hostname.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Put Elasticsearch credentials in environment variables, not the URL.")
        if parsed.query or parsed.fragment:
            raise ValueError("Elasticsearch URL must not include a query string or fragment.")
        if timeout <= 0:
            raise ValueError("Request timeout must be a positive number of seconds.")
        _validate_credentials(api_key, username, password)
        if parsed.scheme == "http" and (api_key or username) and not allow_insecure_http_auth:
            raise ValueError("Refusing to send Elasticsearch credentials over HTTP; use HTTPS or explicitly allow it.")

        netloc = parsed.netloc
        self._base_url = f"{parsed.scheme}://{netloc}{parsed.path.rstrip('/')}"
        self._timeout = timeout
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "howler-elasticsearch-cutover-check/1",
        }
        self._secrets: list[str] = []
        if api_key:
            self._headers["Authorization"] = f"ApiKey {api_key}"
            self._secrets.append(api_key)
        elif username and password:
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            self._headers["Authorization"] = f"Basic {token}"
            self._secrets.extend((username, password, token))

        if insecure:
            context = ssl._create_unverified_context()  # noqa: S323, SLF001 - explicit operator opt-in
        else:
            context = ssl.create_default_context(cafile=str(ca_certs) if ca_certs else None)
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context),
            _NoRedirectHandler(),
        )

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Issue a JSON request, refusing every method that could mutate the cluster."""
        verb = method.upper()
        if verb not in self.READ_METHODS:
            raise ValueError(f"Read-only Elasticsearch client refuses HTTP method {verb!r}.")
        if not path.startswith("/") or path.startswith("//") or any(character in path for character in "?#\r\n"):
            raise ValueError("Elasticsearch REST paths must be absolute paths on the configured host.")

        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{self._base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers=self._headers, method=verb)  # noqa: S310 - scheme checked above
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            # Never stringify HTTPError: its representation includes the full URL and may
            # expose query parameters if a future caller accidentally adds secrets there.
            body = error.read(64 * 1024)
            error.close()
            error_type, reason = self._error_details(body)
            status_text = f" ({error_type})" if error_type else ""
            reason_text = f": {reason}" if reason else ""
            message = f"Elasticsearch {verb} {path} returned HTTP {error.code}{status_text}{reason_text}."
            raise ElasticsearchRestError(
                message,
                status=error.code,
                error_type=error_type,
                reason=reason,
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            network_reason = error.reason if isinstance(error, urllib.error.URLError) else error
            safe_reason = self._sanitize(str(network_reason))
            raise ElasticsearchRestError(
                f"Elasticsearch {verb} {path} failed: {safe_reason}", reason=safe_reason
            ) from None

        if not body:
            return None
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ElasticsearchRestError(f"Elasticsearch {verb} {path} returned invalid JSON.") from None

    def _sanitize(self, value: str) -> str:
        safe = " ".join(value.split())[:500]
        for secret in self._secrets:
            if secret:
                safe = safe.replace(secret, "[redacted]")
        return safe

    def _error_details(self, body: bytes) -> tuple[str | None, str | None]:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, None
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            error_type = error.get("type") if isinstance(error.get("type"), str) else None
            reason = error.get("reason") if isinstance(error.get("reason"), str) else None
            return self._sanitize(error_type) if error_type else None, self._sanitize(reason) if reason else None
        if isinstance(error, str):
            return None, self._sanitize(error)
        return None, None

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a GET request."""
        return self.request("GET", path, params=params)

    def get_optional(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        """Issue a GET request, returning ``None`` when the resource is absent."""
        try:
            return self.get(path, params)
        except ElasticsearchRestError as error:
            if error.status != 404:
                raise
            return None


def credentials_from_environment() -> dict[str, str]:
    """Return validated credentials from the supported environment variables."""
    api_key = os.environ.get("ELASTIC_API_KEY")
    username = os.environ.get("ELASTIC_USERNAME")
    password = os.environ.get("ELASTIC_PASSWORD")
    _validate_credentials(api_key, username, password)
    if api_key:
        return {"api_key": api_key}
    if username and password:
        return {"username": username, "password": password}
    return {}


def setup_howler_plugin_paths() -> Path:
    """Mirror the plugin path setup in ``howler.app`` without adding package subdirectories."""
    from dotenv import load_dotenv

    load_dotenv()
    plugin_path = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))
    sys.path.insert(0, str(plugin_path))

    from howler.config_models import config

    if config.ui.debug and plugin_path.exists():
        for plugin_dir in plugin_path.iterdir():
            sys.path.append(
                str(Path(os.path.realpath(plugin_dir)) / f"../.venv/lib/python3.{sys.version_info.minor}/site-packages")
            )

    return plugin_path


def load_configured_plugins() -> list[Any]:
    """Load app-configured plugin manifests and fail closed for any missing plugin."""
    setup_howler_plugin_paths()
    from howler.config_models import config
    from howler.plugins import PLUGINS, get_plugins

    plugins = get_plugins()
    missing = sorted(name for name in config.core.plugins if PLUGINS.get(name) is None)
    if missing:
        from howler.common.exceptions import HowlerRuntimeError

        raise HowlerRuntimeError(f"Configured Howler plugin(s) failed to load: {', '.join(missing)}.")
    return plugins


def _complete_primary_layout(shards: dict[str, Any], shard_count: Any) -> bool:
    # ES flat settings are strings. Compare with the observed count before enumerating IDs:
    # a failed primary can be entirely absent from _stats (or only a replica can respond).
    return bool(shards) and str(shard_count) == str(len(shards)) and all(str(i) in shards for i in range(len(shards)))


def primary_shard_sync_issues(index_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe missing configured primary IDs, incomplete stats and unsynced global checkpoints."""
    primary_shards = index_data.get("primary_shards")
    if not isinstance(primary_shards, dict):
        primary_shards = {}
    shard_count = index_setting(index_data, "index.number_of_shards")
    issues: list[dict[str, Any]] = []
    if not _complete_primary_layout(primary_shards, shard_count):
        issues.append(
            {"reason": "incomplete_layout", "number_of_shards": shard_count, "primary_ids": sorted(primary_shards)}
        )
    for shard_id, shard in sorted(primary_shards.items()):
        if not isinstance(shard, dict):
            issues.append({"shard": str(shard_id), "reason": "incomplete"})
            continue
        doc_count = shard.get("doc_count")
        max_seq_no = shard.get("max_seq_no")
        global_checkpoint = shard.get("global_checkpoint")
        if any(strict_int(value) is None for value in (doc_count, max_seq_no, global_checkpoint)):
            issues.append({"shard": str(shard_id), "reason": "incomplete"})
        elif global_checkpoint != max_seq_no:
            issues.append(
                {
                    "shard": str(shard_id),
                    "reason": "unsynced",
                    "max_seq_no": max_seq_no,
                    "global_checkpoint": global_checkpoint,
                }
            )
    return issues


def collect_primary_shard_stats(
    client: ElasticsearchRestClient, index_prefix: str, indices: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Collect per-primary stats; report a total only when every configured primary supplied a count."""
    prefix = urllib.parse.quote(index_prefix, safe="-_.")
    response = client.get(
        f"/{prefix}-*/_stats",
        {"level": "shards", "allow_no_indices": "true", "expand_wildcards": "open"},
    )
    result: dict[str, dict[str, Any]] = {}
    for index_name, index_stats in response.get("indices", {}).items():
        primary_shards: dict[str, dict[str, int | None]] = {}
        for shard_id, copies in index_stats.get("shards", {}).items():
            primary = next(
                (copy for copy in copies if copy.get("routing", {}).get("primary") is True),
                None,
            )
            if primary is None:
                continue
            seq_no = primary.get("seq_no", {})
            docs = primary.get("docs", {})
            primary_shards[str(shard_id)] = {
                "doc_count": _nonnegative(docs.get("count")),
                "max_seq_no": _nonnegative_or_minus_one(seq_no.get("max_seq_no")),
                "global_checkpoint": _nonnegative_or_minus_one(seq_no.get("global_checkpoint")),
            }
        counts = [shard["doc_count"] for shard in primary_shards.values()]
        shard_count = index_setting(indices.get(index_name, {}), "index.number_of_shards")
        complete = _complete_primary_layout(primary_shards, shard_count) and None not in counts
        result[index_name] = {
            "doc_count": sum(count for count in counts if count is not None) if complete else None,
            "primary_shards": primary_shards,
        }
    return result


def collect_index_inventory(client: ElasticsearchRestClient, prefix: str, *, scoped: bool) -> dict[str, Any]:
    """Read index settings, aliases, cat metadata, and primary-shard statistics."""
    encoded_prefix = urllib.parse.quote(prefix, safe="-_.")
    index_pattern = f"/{encoded_prefix}-*" if scoped else "/*"
    indices = client.get(
        index_pattern,
        {
            "features": "aliases,settings",
            "flat_settings": "true",
            "expand_wildcards": "all",
            "allow_no_indices": "true",
        },
    )
    catalog_path = f"/_cat/indices/{encoded_prefix}-*" if scoped else "/_cat/indices"
    catalog_rows = client.get(
        catalog_path,
        {
            "format": "json",
            "h": "index,health,status" if scoped else "index,health,status,docs.count",
            "expand_wildcards": "all",
        },
    )
    catalog = {row.get("index"): row for row in catalog_rows if row.get("index")}
    stats = collect_primary_shard_stats(client, prefix, indices)
    for name, data in indices.items():
        settings = index_setting(data, "index.uuid") or index_setting(data, "uuid")
        row = catalog.get(name, {})
        shard_stats = stats.get(name, {})
        data["uuid"] = settings or data.get("uuid")
        data["doc_count"] = shard_stats.get("doc_count")
        data["primary_shards"] = shard_stats.get("primary_shards", {})
        data["health"] = row.get("health")
        data["status"] = row.get("status")
    return indices


def add_connection_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the common read-only Elasticsearch connection and report flags."""
    parser.add_argument(
        "--url",
        default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"),
        help="Elasticsearch URL. Defaults to ELASTICSEARCH_URL or http://localhost:9200.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path instead of stdout.")
    tls = parser.add_mutually_exclusive_group()
    tls.add_argument("--ca-certs", type=Path, help="Certificate authority bundle for TLS verification.")
    tls.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    parser.add_argument(
        "--allow-insecure-http-auth",
        action="store_true",
        help="Explicitly allow sending credentials over plain HTTP (not recommended).",
    )
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds.")


def client_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> ElasticsearchRestClient:
    """Build the REST client from common CLI options and environment credentials."""
    try:
        return ElasticsearchRestClient(
            args.url,
            **credentials_from_environment(),
            ca_certs=args.ca_certs,
            insecure=args.insecure,
            timeout=args.timeout,
            allow_insecure_http_auth=args.allow_insecure_http_auth,
        )
    except ValueError as error:
        parser.error(str(error))


def write_json_report(report: dict[str, Any], output: Path | None) -> None:
    """Write a deterministic JSON report to a file or stdout."""
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")  # noqa: T201


def is_closed_index(index_data: dict[str, Any]) -> bool:
    """Return whether an Elasticsearch index is closed."""
    return str(index_data.get("status", "")).lower() in {"close", "closed"}


def index_setting(data: dict[str, Any], flat_name: str) -> Any:
    """Read an index setting represented in flat or nested Elasticsearch JSON."""
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        return None
    if flat_name in settings:
        return settings[flat_name]
    value: Any = settings
    nested = flat_name.split(".")
    for position, part in enumerate(nested):
        if not isinstance(value, dict):
            return None
        remaining = ".".join(nested[position:])
        if remaining in value:
            return value[remaining]
        value = value.get(part)
    return value


def canonical_ilm_generation(alias: str, index: str) -> int | None:
    """Return the six-digit generation for a canonical ILM backing index."""
    match = re.fullmatch(rf"{re.escape(alias)}-(\d{{6}})", index)
    return int(match.group(1)) if match else None


def strict_int(value: Any) -> int | None:
    """Return an integer only for a non-boolean integer value."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def walk_deprecations(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], dict[str, Any]]]:
    """Return deprecation objects and their paths from Elasticsearch's nested response."""
    found: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    if isinstance(value, dict):
        if isinstance(value.get("level"), str):
            found.append((path, value))
        for key, child in value.items():
            found.extend(walk_deprecations(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(walk_deprecations(child, (*path, str(index))))
    return found


def _nonnegative_or_minus_one(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= -1 else None


def _nonnegative(value: Any) -> int | None:
    parsed = _nonnegative_or_minus_one(value)
    return parsed if parsed is not None and parsed >= 0 else None
