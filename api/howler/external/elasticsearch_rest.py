"""Small, read-only Elasticsearch REST client for cross-major-version checks."""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

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
    """A minimal JSON REST client that can issue GET and HEAD requests only."""

    READ_METHODS = frozenset({"GET", "HEAD"})

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
        if api_key and (username or password):
            raise ValueError("Use either ELASTIC_API_KEY or ELASTIC_USERNAME/ELASTIC_PASSWORD, not both.")
        if bool(username) != bool(password):
            raise ValueError("ELASTIC_USERNAME and ELASTIC_PASSWORD must be set together.")
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

        if verb == "HEAD" or not body:
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

    def head(self, path: str, params: dict[str, Any] | None = None) -> None:
        """Issue a HEAD request."""
        self.request("HEAD", path, params=params)


def credentials_from_environment() -> dict[str, str]:
    """Return validated credentials from the supported environment variables."""
    api_key = os.environ.get("ELASTIC_API_KEY")
    username = os.environ.get("ELASTIC_USERNAME")
    password = os.environ.get("ELASTIC_PASSWORD")
    if api_key and (username or password):
        raise ValueError("Use either ELASTIC_API_KEY or ELASTIC_USERNAME/ELASTIC_PASSWORD, not both.")
    if bool(username) != bool(password):
        raise ValueError("ELASTIC_USERNAME and ELASTIC_PASSWORD must be set together.")
    if api_key:
        return {"api_key": api_key}
    if username and password:
        return {"username": username, "password": password}
    return {}


def setup_howler_plugin_paths() -> Path:
    """Mirror the plugin path setup in ``howler.app`` without adding package subdirectories."""
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


def primary_shard_sync_issues(primary_shards: Any) -> list[dict[str, Any]]:
    """Describe incomplete primary stats and any shard whose global checkpoint trails its max sequence number."""
    if not isinstance(primary_shards, dict) or not primary_shards:
        return [{"shard": None, "reason": "incomplete"}]

    issues: list[dict[str, Any]] = []
    for shard_id, shard in sorted(primary_shards.items()):
        if not isinstance(shard, dict):
            issues.append({"shard": str(shard_id), "reason": "incomplete"})
            continue
        doc_count = shard.get("doc_count")
        max_seq_no = shard.get("max_seq_no")
        global_checkpoint = shard.get("global_checkpoint")
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (doc_count, max_seq_no, global_checkpoint)
        ):
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


def collect_primary_shard_stats(client: ElasticsearchRestClient, index_prefix: str) -> dict[str, dict[str, Any]]:
    """Collect primary document counts and sequence/checkpoint values from one stats response."""
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
        primary_count = _nonnegative(index_stats.get("primaries", {}).get("docs", {}).get("count"))
        if primary_shards:
            primary_count = (
                sum(count for count in counts if count is not None)
                if all(count is not None for count in counts)
                else None
            )
        result[index_name] = {
            "doc_count": primary_count,
            "primary_shards": primary_shards,
        }
    return result


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
