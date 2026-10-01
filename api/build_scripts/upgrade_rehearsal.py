"""Run an isolated Step 9 restore-on-8.19, in-place upgrade, and rollback rehearsal.

The workflow owns every Elasticsearch container, volume, network, and HTTP endpoint it
uses. It accepts no cluster URL or credential, and uses urllib rather than the API
package's Elasticsearch 9 client when talking to 8.19.11.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

SOURCE_VERSION = "8.19.11"
TARGET_VERSION = "9.5.2"
SOURCE_IMAGE = f"docker.elastic.co/elasticsearch/elasticsearch:{SOURCE_VERSION}"
TARGET_IMAGE = f"docker.elastic.co/elasticsearch/elasticsearch:{TARGET_VERSION}"
DATA_PATH = "/usr/share/elasticsearch/data"
REPOSITORY_PATH = "/usr/share/elasticsearch/snapshots"
REINDEX_MARKER = "__reindex"
LABEL_KEY = "howler.step9.rehearsal"
MAX_DOCS_PER_INDEX = 250_000
MAX_DOCS_TOTAL = 500_000
SYNTHETIC_HIT_INDEX = "howler-hit_hot"
SYNTHETIC_CASE_INDEX = "howler-case_hot"
SYNTHETIC_INDICES = [SYNTHETIC_CASE_INDEX, SYNTHETIC_HIT_INDEX]
SYNTHETIC_ALIASES = {SYNTHETIC_HIT_INDEX: "howler-hit", SYNTHETIC_CASE_INDEX: "howler-case"}
SYNTHETIC_MAPPINGS = {
    SYNTHETIC_HIT_INDEX: {
        "properties": {
            "howler": {
                "properties": {
                    "id": {"type": "keyword"},
                    "analytic": {"type": "keyword"},
                    "hash": {"type": "keyword"},
                }
            },
            "classification": {"type": "keyword"},
            "message": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "fixture": {
                "properties": {
                    "sequence": {"type": "integer"},
                    "query_token": {"type": "keyword"},
                    "visibility": {"type": "keyword"},
                }
            },
            "__access_lvl__": {"type": "integer"},
            "__access_req__": {"type": "keyword"},
            "__access_grp1__": {"type": "keyword"},
            "__access_grp2__": {"type": "keyword"},
        }
    },
    SYNTHETIC_CASE_INDEX: {
        "properties": {
            "case_id": {"type": "keyword"},
            "classification": {"type": "keyword"},
            "title": {"type": "text"},
            "summary": {"type": "text"},
            "status": {"type": "keyword"},
            "visible": {"type": "boolean"},
            "items": {
                "properties": {
                    "id": {"type": "keyword"},
                    "parent": {"type": "keyword"},
                    "name": {"type": "text"},
                    "type": {"type": "keyword"},
                    "value": {"type": "text"},
                    "visible": {"type": "boolean"},
                    "classification": {"type": "keyword"},
                }
            },
            "fixture": {
                "properties": {
                    "query_token": {"type": "keyword"},
                    "expected_link_count": {"type": "integer"},
                }
            },
            "__access_lvl__": {"type": "integer"},
            "__access_req__": {"type": "keyword"},
            "__access_grp1__": {"type": "keyword"},
            "__access_grp2__": {"type": "keyword"},
        }
    },
}
SYNTHETIC_HITS = {
    "step9-hit-unrestricted-001": {
        "howler": {"id": "step9-hit-unrestricted-001", "analytic": "step9 synthetic", "hash": "a" * 64},
        "classification": "UNRESTRICTED",
        "message": "STEP9_SYNTHETIC_UNRESTRICTED",
        "tags": ["step9-synthetic", "step9-shared-query"],
        "fixture": {"sequence": 1, "query_token": "STEP9-SHARED", "visibility": "unrestricted"},
        "__access_lvl__": 100,
        "__access_req__": [],
        "__access_grp1__": ["__EMPTY__"],
        "__access_grp2__": ["__EMPTY__"],
    },
    "step9-hit-restricted-002": {
        "howler": {"id": "step9-hit-restricted-002", "analytic": "step9 synthetic", "hash": "b" * 64},
        "classification": "RESTRICTED",
        "message": "STEP9_SYNTHETIC_RESTRICTED",
        "tags": ["step9-synthetic", "step9-shared-query"],
        "fixture": {"sequence": 2, "query_token": "STEP9-SHARED", "visibility": "restricted"},
        "__access_lvl__": 200,
        "__access_req__": [],
        "__access_grp1__": ["__EMPTY__"],
        "__access_grp2__": ["__EMPTY__"],
    },
}
SYNTHETIC_CASE_ID = "00000000-0000-4000-8000-000000000901"
SYNTHETIC_CASE = {
    "case_id": SYNTHETIC_CASE_ID,
    "classification": "RESTRICTED",
    "title": "Step 9 synthetic linked case",
    "summary": "Deterministic 8.19.11 to 9.5.2 migration fixture.",
    "status": "open",
    "visible": True,
    "fixture": {"query_token": "STEP9-CASE", "expected_link_count": 2},
    "items": [
        {
            "id": "00000000-0000-4000-8000-000000000911",
            "parent": None,
            "name": "Unrestricted synthetic hit",
            "type": "hit",
            "value": "step9-hit-unrestricted-001",
            "visible": True,
            "classification": "UNRESTRICTED",
        },
        {
            "id": "00000000-0000-4000-8000-000000000912",
            "parent": None,
            "name": "Restricted synthetic hit",
            "type": "hit",
            "value": "step9-hit-restricted-002",
            "visible": True,
            "classification": "RESTRICTED",
        },
    ],
    "__access_lvl__": 200,
    "__access_req__": [],
    "__access_grp1__": ["__EMPTY__"],
    "__access_grp2__": ["__EMPTY__"],
}


def synthetic_fixture_checksum() -> str:
    """Return the stable SHA-256 of the canonical synthetic index/document manifest."""
    indices = {
        SYNTHETIC_HIT_INDEX: SYNTHETIC_HITS,
        SYNTHETIC_CASE_INDEX: {SYNTHETIC_CASE_ID: SYNTHETIC_CASE},
    }
    manifest = {
        "indices": [
            {
                "name": name,
                "write_alias": SYNTHETIC_ALIASES[name],
                "mapping": SYNTHETIC_MAPPINGS[name],
                "documents": [
                    {"id": document_id, "source": source} for document_id, source in sorted(documents.items())
                ],
            }
            for name, documents in sorted(indices.items())
        ]
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RehearsalAbort(RuntimeError):
    """A safety gate or a required rehearsal check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RehearsalAbort(message)


def _run(command: list[str], *, check: bool = True) -> str:
    environment = os.environ.copy()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        environment.pop(key, None)
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RehearsalAbort(f"Command failed ({result.returncode}): {command[0]} {command[1]}: {detail[:1200]}")
    return result.stdout.strip()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _json_response(response: Any) -> Any:
    return json.loads(response.read().decode("utf-8"))


class RestClient:
    """Small raw HTTP client; intentionally avoids ES-client version negotiation."""

    def __init__(self, url: str, timeout: int):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: Any = None) -> Any:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{self.url}{path}", data=payload, headers=headers, method=method)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self.timeout) as response:
                return _json_response(response)
        except urllib.error.HTTPError as error:
            body_text = error.read().decode("utf-8", errors="replace")
            raise RehearsalAbort(
                f"Elasticsearch {method} {path} returned HTTP {error.code}: {body_text[:1200]}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RehearsalAbort(f"Elasticsearch {method} {path} failed: {error}") from error


@dataclass(frozen=True)
class ClusterHandle:
    role: str
    name: str
    container_id: str
    volume: str
    cluster_name: str
    version: str
    base_url: str
    repository_readonly: bool = False


class DockerRuntime:
    """Create and verify disposable resources owned by one uniquely labelled run."""

    def __init__(self, run_id: str, work_dir: Path, timeout: int, command: Callable[..., str] = _run):
        self.run_id = run_id
        self.work_dir = work_dir
        self.timeout = timeout
        self.command = command
        self.network = f"howler-step9-{run_id}"
        self.volumes = {role: f"howler-step9-{run_id}-{role}-data" for role in ("donor", "cutover", "rollback")}
        self.handles: dict[str, ClusterHandle] = {}
        self.resources: dict[str, Any] = {
            "network": self.network,
            "volumes": dict(self.volumes),
            "containers": {},
            "removed_containers": [],
        }

    def _docker(self, arguments: list[str], *, check: bool = True) -> str:
        return self.command(["docker", "--context", "default", *arguments], check=check)

    def _assert_local_context(self) -> None:
        endpoint = self._docker(["context", "inspect", "default", "--format", "{{json .Endpoints.docker.Host}}"])
        try:
            endpoint = json.loads(endpoint)
        except json.JSONDecodeError:
            pass
        _require(
            isinstance(endpoint, str) and endpoint.startswith("unix://"),
            f"Refusing non-local Docker context endpoint {endpoint!r}; only a local Unix socket is allowed.",
        )

    def _labels(self, role: str) -> list[str]:
        return [
            "--label",
            f"{LABEL_KEY}=true",
            "--label",
            f"howler.step9.run={self.run_id}",
            "--label",
            f"howler.step9.role={role}",
        ]

    def _assert_names_free(self) -> None:
        existing_containers = set(self._docker(["ps", "-a", "--format", "{{.Names}}"], check=True).splitlines())
        existing_volumes = set(self._docker(["volume", "ls", "--format", "{{.Name}}"], check=True).splitlines())
        existing_networks = set(self._docker(["network", "ls", "--format", "{{.Name}}"], check=True).splitlines())
        names = {self.network, *self.volumes.values()}
        names.update(self._container_name(role) for role in ("donor", "cutover", "rollback"))
        collisions = sorted(names & (existing_containers | existing_volumes | existing_networks))
        _require(not collisions, f"Refusing to reuse pre-existing Docker resources: {collisions}.")

    def _container_name(self, role: str) -> str:
        return f"howler-step9-{self.run_id}-{role}"

    def create_base_resources(self) -> None:
        self._assert_local_context()
        self._assert_names_free()
        self._docker(["network", "create", "--internal", *self._labels("network"), self.network])
        network = json.loads(self._docker(["network", "inspect", self.network]))[0]
        network_labels = network.get("Labels", {})
        _require(
            network_labels.get(LABEL_KEY) == "true"
            and network_labels.get("howler.step9.run") == self.run_id
            and network_labels.get("howler.step9.role") == "network",
            "Created Docker network ownership label mismatch.",
        )
        _require(network.get("Driver") == "bridge", "Docker rehearsal network must use the local bridge driver.")
        _require(network.get("Internal") is True, "Docker rehearsal network must be internal (no external routing).")
        for role, volume in self.volumes.items():
            self._docker(["volume", "create", *self._labels(role), volume])
            metadata = json.loads(self._docker(["volume", "inspect", volume]))[0]
            labels = metadata.get("Labels", {})
            _require(
                labels.get(LABEL_KEY) == "true"
                and labels.get("howler.step9.run") == self.run_id
                and labels.get("howler.step9.role") == role
                and metadata.get("Driver") == "local",
                f"Created volume {volume!r} ownership label mismatch.",
            )

    def start(self, role: str, version: str, volume_role: str, *, repository_readonly: bool) -> ClusterHandle:
        self._assert_local_context()
        _require(role not in self.handles, f"Docker role {role!r} already has an active container.")
        name = self._container_name(role)
        volume = self.volumes[volume_role]
        image = SOURCE_IMAGE if version == SOURCE_VERSION else TARGET_IMAGE
        cluster_name = f"howler-step9-{self.run_id}-{role}"
        command = [
            "run",
            "-d",
            "--name",
            name,
            *self._labels(role),
            "--network",
            self.network,
            "--mount",
            f"type=volume,source={volume},target={DATA_PATH}",
            "--mount",
            f"type=bind,source={self.work_dir},target={REPOSITORY_PATH}{',readonly' if repository_readonly else ''}",
            "-e",
            "discovery.type=single-node",
            "-e",
            f"cluster.name={cluster_name}",
            "-e",
            "xpack.security.enabled=false",
            "-e",
            f"path.repo={REPOSITORY_PATH}",
            "-e",
            "ES_JAVA_OPTS=-Xms1g -Xmx1g",
            image,
        ]
        container_id = self._docker(command)
        handle = ClusterHandle(role, name, container_id, volume, cluster_name, version, "", repository_readonly)
        self.handles[role] = handle
        resource_key = f"{role}-{version}"
        self.resources["containers"][resource_key] = asdict(handle)
        address = self._verify_container(handle, expected_state="running")
        handle = ClusterHandle(
            role,
            name,
            container_id,
            volume,
            cluster_name,
            version,
            f"http://{address}:9200",
            repository_readonly,
        )
        self.handles[role] = handle
        self.resources["containers"][resource_key] = asdict(handle)
        return handle

    def _inspect(self, handle: ClusterHandle) -> dict[str, Any]:
        response = json.loads(self._docker(["inspect", handle.container_id]))[0]
        _require(response.get("Id") == handle.container_id, f"Container identity changed for {handle.role}.")
        _require(
            response.get("Name", "").lstrip("/") == handle.name,
            f"Container name changed for {handle.role}.",
        )
        labels = response.get("Config", {}).get("Labels", {})
        _require(
            labels.get(LABEL_KEY) == "true"
            and labels.get("howler.step9.run") == self.run_id
            and labels.get("howler.step9.role") == handle.role,
            f"Container ownership labels failed for {handle.role}.",
        )
        return response

    def _verify_container(self, handle: ClusterHandle, *, expected_state: str) -> str:
        response = self._inspect(handle)
        _require(
            response.get("State", {}).get("Status") == expected_state,
            f"Container {handle.name!r} is not {expected_state}.",
        )
        expected_image = SOURCE_IMAGE if handle.version == SOURCE_VERSION else TARGET_IMAGE
        _require(
            response.get("Config", {}).get("Image") == expected_image, f"Container image mismatch for {handle.role}."
        )
        configured_environment = response.get("Config", {}).get("Env") or []
        secret_environment = [
            entry.split("=", 1)[0]
            for entry in configured_environment
            if any(secret in entry.split("=", 1)[0].upper() for secret in ("PASSWORD", "TOKEN", "API_KEY"))
        ]
        _require(not secret_environment, f"Container {handle.role} has secret-bearing environment variables.")
        mounts = response.get("Mounts", [])
        data_mounts = [mount for mount in mounts if mount.get("Destination") == DATA_PATH]
        _require(
            len(data_mounts) == 1
            and data_mounts[0].get("Type") == "volume"
            and data_mounts[0].get("Name") == handle.volume,
            f"Container {handle.role} is not attached to its dedicated data volume.",
        )
        _require(data_mounts[0].get("RW") is True, "Elasticsearch data mount must be writable on the owned volume.")
        repo_mounts = [mount for mount in mounts if mount.get("Destination") == REPOSITORY_PATH]
        _require(
            len(repo_mounts) == 1
            and repo_mounts[0].get("Type") == "bind"
            and Path(repo_mounts[0].get("Source", "")).resolve() == self.work_dir,
            f"Container {handle.role} is not attached to this run's snapshot workspace.",
        )
        _require(
            repo_mounts[0].get("RW") is (not handle.repository_readonly),
            f"Container {handle.role} snapshot workspace mount mode differs from the planned role.",
        )
        _require(len(mounts) == 2, f"Unexpected additional mount(s) on {handle.role}.")
        port_bindings = response.get("HostConfig", {}).get("PortBindings") or {}
        _require(not any(port_bindings.values()), f"Container {handle.role} must not publish host ports.")
        host_config = response.get("HostConfig", {})
        _require(
            not host_config.get("Privileged")
            and not host_config.get("Devices")
            and not host_config.get("CapAdd")
            and host_config.get("PidMode") != "host"
            and host_config.get("IpcMode") != "host",
            f"Container {handle.role} has unexpected elevated host privileges.",
        )
        _require(host_config.get("NetworkMode") == self.network, f"Container {handle.role} network mode changed.")
        published = response.get("NetworkSettings", {}).get("Ports") or {}
        _require(not any(published.values()), f"Container {handle.role} unexpectedly has host-published ports.")
        networks = response.get("NetworkSettings", {}).get("Networks", {})
        _require(set(networks) == {self.network}, f"Container {handle.role} is outside the private run network.")
        address = networks[self.network].get("IPAddress", "")
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as error:
            raise RehearsalAbort(f"Container {handle.role} has no valid internal bridge IP.") from error
        _require(
            parsed_address.version == 4 and parsed_address.is_private,
            f"Container {handle.role} bridge IP is not private IPv4: {address!r}.",
        )
        network = json.loads(self._docker(["network", "inspect", self.network]))[0]
        _require(
            network.get("Internal") is True and network.get("Driver") == "bridge",
            "Docker network lost its internal isolation or local bridge driver.",
        )
        network_labels = network.get("Labels", {})
        _require(
            network_labels.get(LABEL_KEY) == "true"
            and network_labels.get("howler.step9.run") == self.run_id
            and network_labels.get("howler.step9.role") == "network",
            "Docker network ownership labels changed during the rehearsal.",
        )
        expected_members = {item.container_id for item in self.handles.values()}
        network_containers = network.get("Containers") or {}
        network_members = set(network_containers)
        _require(
            network_members == expected_members,
            f"Private Docker network has unexpected attached containers: {sorted(network_members ^ expected_members)}.",
        )
        member = network_containers.get(handle.container_id, {})
        member_address = str(member.get("IPv4Address", "")).split("/", 1)[0]
        _require(member_address == address, "Network membership IP differs from the inspected container IP.")
        subnet_matches = False
        for config in network.get("IPAM", {}).get("Config") or []:
            try:
                if parsed_address in ipaddress.ip_network(config.get("Subnet", ""), strict=False):
                    subnet_matches = True
            except ValueError:
                continue
        _require(subnet_matches, "Inspected container IP is outside the owned Docker network subnet.")
        return address

    def verify_owned(self, handle: ClusterHandle) -> None:
        self._verify_container(handle, expected_state="running")

    def stop_and_remove_container(self, handle: ClusterHandle) -> None:
        self._assert_local_context()
        self.verify_owned(handle)
        self._docker(["stop", "--time", "120", handle.container_id])
        stopped = self._inspect(handle)
        _require(
            stopped.get("State", {}).get("Status") == "exited",
            f"Container {handle.name!r} did not stop cleanly.",
        )
        data_mounts = [mount for mount in stopped.get("Mounts", []) if mount.get("Destination") == DATA_PATH]
        _require(
            len(data_mounts) == 1 and data_mounts[0].get("Name") == handle.volume,
            "Stopped 8.19 container no longer verifies its dedicated data volume.",
        )
        self._docker(["rm", handle.container_id])  # no -v: data volume is retained
        self.resources["removed_containers"].append(
            {"role": handle.role, "name": handle.name, "container_id": handle.container_id, "volume": handle.volume}
        )
        self.handles.pop(handle.role, None)


def validate_cluster_info(
    info: dict[str, Any], expected_name: str, expected_version: str, expected_uuid: str | None = None
) -> None:
    _require(
        info.get("cluster_name") == expected_name,
        f"Invalid cluster identity: expected {expected_name!r}, got {info.get('cluster_name')!r}.",
    )
    _require(
        info.get("version", {}).get("number") == expected_version,
        f"Invalid cluster version: expected {expected_version}, got {info.get('version', {}).get('number')!r}.",
    )
    cluster_uuid = info.get("cluster_uuid")
    _require(
        isinstance(cluster_uuid, str) and bool(cluster_uuid) and cluster_uuid != "_na_",
        "Cluster UUID is missing.",
    )
    if expected_uuid is not None:
        _require(
            cluster_uuid == expected_uuid,
            f"Cluster UUID changed across restart: expected {expected_uuid}, got {cluster_uuid}.",
        )


def _root(client: RestClient, name: str, version: str, expected_uuid: str | None = None) -> dict[str, Any]:
    info = client.request("GET", "/")
    validate_cluster_info(info, name, version, expected_uuid)
    return info


def wait_for_cluster(handle: ClusterHandle, runtime: DockerRuntime, timeout: int) -> tuple[RestClient, dict[str, Any]]:
    probe = RestClient(handle.base_url, min(timeout, 30))
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        runtime.verify_owned(handle)
        try:
            info = probe.request("GET", "/")
        except RehearsalAbort as error:
            last_error = error
        else:
            # A newly elected 9.x node can answer HTTP while its cluster UUID is
            # still `_na_`. Identity and version mismatches are fatal, but a UUID
            # that has not yet been published must wait for cluster readiness.
            if info.get("cluster_uuid") in (None, "", "_na_"):
                last_error = RehearsalAbort("Cluster UUID is missing.")
            else:
                validate_cluster_info(info, handle.cluster_name, handle.version)
                return RestClient(handle.base_url, timeout), info
        time.sleep(2)
    raise RehearsalAbort(f"Cluster {handle.role!r} did not become ready: {last_error or 'timeout'}.")


def _api(client: RestClient, method: str, path: str, body: Any = None) -> Any:
    return client.request(method, path, body)


def _index_inventory(client: RestClient) -> dict[str, Any]:
    return _api(client, "GET", "/_all/_settings?flat_settings=true&expand_wildcards=all")


def verify_synthetic_fixture(client: RestClient, names: list[str]) -> None:
    _require(
        names == SYNTHETIC_INDICES,
        f"Synthetic fixture must contain exactly {SYNTHETIC_INDICES!r}.",
    )
    expected_documents = {
        SYNTHETIC_HIT_INDEX: SYNTHETIC_HITS,
        SYNTHETIC_CASE_INDEX: {SYNTHETIC_CASE_ID: SYNTHETIC_CASE},
    }
    observed_case: dict[str, Any] | None = None
    for index, documents in expected_documents.items():
        alias_name = SYNTHETIC_ALIASES[index]
        alias_result = _api(client, "GET", f"/{index}/_alias")
        aliases = alias_result.get(index, {}).get("aliases", {})
        _require(
            aliases == {alias_name: {"is_write_index": True}},
            f"Synthetic index {index!r} must retain its explicit write alias {alias_name!r}: {aliases!r}.",
        )
        mapping_result = _api(client, "GET", f"/{index}/_mapping")
        _require(
            mapping_result == {index: {"mappings": SYNTHETIC_MAPPINGS[index]}},
            f"Synthetic index {index!r} mapping differs from its frozen fixture mapping.",
        )
        count = _api(client, "POST", f"/{index}/_count", {"query": {"match_all": {}}}).get("count")
        _require(
            count == len(documents), f"Synthetic index {index!r} expected {len(documents)} documents, found {count!r}."
        )
        for document_id, expected_source in documents.items():
            response = _api(
                client,
                "GET",
                f"/{index}/_doc/{urllib.parse.quote(document_id, safe='')}",
            )
            _require(
                response.get("found") is True and response.get("_source") == expected_source,
                f"Synthetic fixture document {document_id!r} is missing or has unexpected content.",
            )
            if index == SYNTHETIC_CASE_INDEX:
                observed_case = response["_source"]

    hit_ids = set(SYNTHETIC_HITS)
    linked_ids = {item.get("value") for item in (observed_case or {}).get("items", []) if item.get("type") == "hit"}
    _require(linked_ids == hit_ids, "Synthetic case must link to both deterministic hit IDs.")


def _selected_names(inventory: dict[str, Any], pattern: str) -> list[str]:
    names = sorted(name for name in inventory if fnmatch.fnmatchcase(name, pattern))
    _require(bool(names), f"No indices match representative pattern {pattern!r}.")
    _require(
        not any(REINDEX_MARKER in name for name in inventory), "Temporary __reindex index found in cluster inventory."
    )
    _require(not any(REINDEX_MARKER in name for name in names), "Representative selection includes a __reindex index.")
    _require(
        all(not name.startswith(".") for name in names), "Representative pattern must not select hidden/system indices."
    )
    return names


def _flatten_deprecations(value: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("level") and value.get("message"):
            results.append(value)
        for child in value.values():
            results.extend(_flatten_deprecations(child))
    elif isinstance(value, list):
        for child in value:
            results.extend(_flatten_deprecations(child))
    return results


def _index_creation_major(index_data: dict[str, Any]) -> int | None:
    created = index_data.get("settings", {}).get("index.version.created")
    try:
        number = str(created)
        return int(number.split(".", 1)[0]) if "." in number else int(number) // 1_000_000
    except (TypeError, ValueError):
        return None


def _feature_migration_statuses(value: Any) -> list[str]:
    statuses: list[str] = []
    if isinstance(value, dict):
        status = value.get("migration_status")
        if status:
            statuses.append(status)
        for child in value.values():
            statuses.extend(_feature_migration_statuses(child))
    elif isinstance(value, list):
        for child in value:
            statuses.extend(_feature_migration_statuses(child))
    return statuses


def upgrade_preflight(client: RestClient, cluster_name: str, inventory: dict[str, Any]) -> dict[str, Any]:
    info = _root(client, cluster_name, SOURCE_VERSION)
    health = _api(client, "GET", "/_cluster/health")
    _require(health.get("status") in {"green", "yellow"}, f"8.19 source health is not green/yellow: {health!r}.")
    pre8: list[str] = []
    unknown: list[str] = []
    for name, metadata in inventory.items():
        major = _index_creation_major(metadata)
        if major is None:
            unknown.append(name)
        elif major < 8:
            pre8.append(name)
    _require(not pre8, f"Pre-8.0 indices require a separate migration decision: {sorted(pre8)}.")
    _require(not unknown, f"Index creation versions are unknown: {sorted(unknown)}.")
    deprecations = _api(client, "GET", "/_migration/deprecations")
    critical = [item for item in _flatten_deprecations(deprecations) if item.get("level") == "critical"]
    _require(not critical, f"Critical Elasticsearch deprecations must be resolved first: {critical[:10]!r}.")
    feature_status = _api(client, "GET", "/_migration/system_features")
    statuses = _feature_migration_statuses(feature_status)
    _require(
        bool(statuses) and all(status == "NO_MIGRATION_NEEDED" for status in statuses),
        f"System feature migration is not ready: {feature_status!r}.",
    )
    return {
        "ready": True,
        "cluster_uuid": info["cluster_uuid"],
        "critical_deprecations": 0,
        "index_count": len(inventory),
        "system_feature_statuses": statuses,
    }


def snapshot_metadata(client: RestClient, repository: str, snapshot: str) -> dict[str, Any]:
    encoded_repo = urllib.parse.quote(repository, safe="")
    encoded_snapshot = urllib.parse.quote(snapshot, safe="")
    response = _api(client, "GET", f"/_snapshot/{encoded_repo}/{encoded_snapshot}")
    snapshots = response.get("snapshots", [])
    _require(len(snapshots) == 1, f"Expected one snapshot {snapshot!r}, found {len(snapshots)}.")
    return snapshots[0]


def validate_snapshot_version(metadata: dict[str, Any], expected_version: str) -> dict[str, Any]:
    """Accept an exact version or an Elasticsearch mixed-node patch range containing it."""
    raw_version = metadata.get("version")
    version_id = metadata.get("version_id")
    _require(
        isinstance(version_id, int) and not isinstance(version_id, bool) and version_id > 0,
        f"Snapshot metadata has no valid numeric version_id: {version_id!r}.",
    )

    def parse(version: Any) -> tuple[int, int, int] | None:
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            return None
        return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]

    expected = parse(expected_version)
    if expected is None:
        raise RehearsalAbort(f"Invalid expected Elasticsearch version: {expected_version!r}.")
    exact = parse(raw_version)
    if exact is not None:
        _require(exact == expected, f"Snapshot version mismatch: expected {expected_version}, found {raw_version!r}.")
    else:
        range_parts = raw_version.split("-") if isinstance(raw_version, str) else []
        _require(len(range_parts) == 2, f"Unrecognized snapshot version metadata: {raw_version!r}.")
        lower, upper = parse(range_parts[0]), parse(range_parts[1])
        if lower is None or upper is None:
            raise RehearsalAbort(f"Unrecognized snapshot version range: {raw_version!r}.")
        _require(
            lower[:2] == expected[:2] and upper[:2] == expected[:2] and lower <= expected <= upper,
            f"Snapshot version range {raw_version!r} does not contain compatible {expected_version}.",
        )
    return {"version": raw_version, "version_id": version_id, "compatible_with": expected_version}


def register_repository(client: RestClient, name: str, path: str, readonly: bool) -> None:
    _api(
        client,
        "PUT",
        f"/_snapshot/{urllib.parse.quote(name, safe='')}",
        {"type": "fs", "settings": {"location": path, "compress": True, "readonly": readonly}},
    )


def restore_snapshot(client: RestClient, repo: str, snapshot: str, indices: list[str]) -> dict[str, Any]:
    body = {"indices": ",".join(indices), "include_global_state": False, "include_aliases": True}
    response = _api(
        client,
        "POST",
        f"/_snapshot/{urllib.parse.quote(repo, safe='')}/"
        f"{urllib.parse.quote(snapshot, safe='')}/_restore?wait_for_completion=true",
        body,
    )
    _require(isinstance(response, dict), f"Restore response must be an object, found {type(response).__name__}.")
    snapshot_result = response.get("snapshot")
    _require(isinstance(snapshot_result, dict), f"Restore response is missing its snapshot result: {response!r}.")
    _require(
        snapshot_result.get("snapshot") == snapshot,
        f"Restore response snapshot name mismatch: expected {snapshot!r}, found {snapshot_result.get('snapshot')!r}.",
    )
    actual_indices = sorted(snapshot_result.get("indices", []))
    _require(actual_indices == sorted(indices), f"Restore response index list mismatch: {actual_indices!r}.")
    shards = snapshot_result.get("shards")
    _require(isinstance(shards, dict), f"Restore response is missing shard completion details: {response!r}.")
    total = shards.get("total")
    successful = shards.get("successful")
    failed = shards.get("failed")
    _require(
        isinstance(total, int) and total > 0 and successful == total and failed == 0,
        f"Restore did not complete every shard successfully: {shards!r}.",
    )
    state = snapshot_result.get("state")
    _require(state in {None, "SUCCESS"}, f"Restore operation did not succeed: {response!r}.")
    return response


def create_snapshot(client: RestClient, repo: str, snapshot: str, indices: list[str], cluster_name: str) -> None:
    response = _api(
        client,
        "PUT",
        f"/_snapshot/{urllib.parse.quote(repo, safe='')}/"
        f"{urllib.parse.quote(snapshot, safe='')}?wait_for_completion=true",
        {
            "indices": ",".join(indices),
            "include_global_state": False,
            "metadata": {"purpose": "step9-upgrade-rehearsal", "donor_cluster": cluster_name},
        },
    )
    _require(response.get("snapshot", {}).get("state") == "SUCCESS", f"Donor snapshot failed: {response!r}.")


def _document_digest(client: RestClient, index: str, count: int, max_docs: int) -> str:
    _require(count <= max_docs, f"Index {index!r} has {count} documents; configured digest cap is {max_docs}.")
    digests: list[str] = []
    response = _api(
        client,
        "POST",
        f"/{urllib.parse.quote(index, safe='')}/_search?scroll=1m",
        {"size": 1000, "sort": ["_doc"], "query": {"match_all": {}}, "_source": True},
    )
    scroll_id = response.get("_scroll_id")
    try:
        hits = response.get("hits", {}).get("hits", [])
        while hits:
            for hit in hits:
                _require(
                    isinstance(hit.get("_source"), dict),
                    f"Index {index!r} has a document without an available _source; content identity cannot be proven.",
                )
                canonical = json.dumps(
                    {"_id": hit.get("_id"), "_routing": hit.get("_routing"), "_source": hit.get("_source")},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                digests.append(hashlib.sha256(canonical.encode("utf-8")).hexdigest())
            if not scroll_id:
                break
            response = _api(client, "POST", "/_search/scroll", {"scroll": "1m", "scroll_id": scroll_id})
            scroll_id = response.get("_scroll_id", scroll_id)
            hits = response.get("hits", {}).get("hits", [])
        _require(
            len(digests) == count, f"Document scan count changed for {index!r}: count={count}, scanned={len(digests)}."
        )
    finally:
        if scroll_id:
            try:
                _api(client, "DELETE", "/_search/scroll", {"scroll_id": [scroll_id]})
            except RehearsalAbort:
                pass
    return hashlib.sha256("\n".join(sorted(digests)).encode("ascii")).hexdigest()


def capture_data_state(client: RestClient, names: list[str], max_docs: int) -> dict[str, Any]:
    inventory = _index_inventory(client)
    _require(
        set(inventory) == set(names),
        f"Unexpected index inventory: expected {sorted(names)}, found {sorted(inventory)}.",
    )
    indices = ",".join(urllib.parse.quote(name, safe="") for name in names)
    settings = inventory
    mappings = _api(client, "GET", f"/{indices}/_mapping")
    aliases_response = _api(client, "GET", f"/{indices}/_alias")
    aliases = {name: aliases_response.get(name, {}).get("aliases", {}) for name in names}
    counts: dict[str, int] = {}
    digests: dict[str, str] = {}
    uuids: dict[str, str] = {}
    total_docs = 0
    for name in names:
        count = _api(client, "POST", f"/{urllib.parse.quote(name, safe='')}/_count", {"query": {"match_all": {}}})[
            "count"
        ]
        counts[name] = int(count)
        total_docs += counts[name]
        _require(
            total_docs <= MAX_DOCS_TOTAL,
            f"Selected fixture has more than {MAX_DOCS_TOTAL} documents; content hashing cap exceeded.",
        )
        digests[name] = _document_digest(client, name, counts[name], max_docs)
        index_uuid = settings[name].get("settings", {}).get("index.uuid")
        _require(isinstance(index_uuid, str) and bool(index_uuid), f"Index UUID missing for {name!r}.")
        uuids[name] = index_uuid
    _require(set(mappings) == set(names), "Mapping inventory does not match selected indices.")
    return {
        "aliases": aliases,
        "counts": counts,
        "document_sha256": digests,
        "index_uuids": uuids,
        "mappings": mappings,
    }


def verify_data_identity(
    expected: dict[str, Any], actual: dict[str, Any], *, phase: str, require_uuid_match: bool
) -> None:
    for key in ("aliases", "counts", "document_sha256", "mappings"):
        _require(
            expected.get(key) == actual.get(key), f"{phase}: {key} mismatch (equal counts alone are not accepted)."
        )
    if require_uuid_match:
        assert_index_uuids_equal(expected.get("index_uuids", {}), actual.get("index_uuids", {}), phase)
    else:
        _require(
            set(actual.get("index_uuids", {})) == set(expected.get("index_uuids", {})),
            f"{phase}: index UUID inventory mismatch.",
        )


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    shape = {key: state[key] for key in ("aliases", "mappings")}
    shape_sha256 = hashlib.sha256(json.dumps(shape, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "aliases_and_mappings_sha256": shape_sha256,
        "counts": state["counts"],
        "document_sha256": state["document_sha256"],
        "index_uuids": state["index_uuids"],
    }


def assert_index_uuids_equal(before: dict[str, str], after: dict[str, str], phase: str) -> None:
    _require(before == after, f"{phase}: index UUID changed across the in-place 8.19-to-9.5 restart.")


def assert_same_data_volume(before: ClusterHandle, after: ClusterHandle) -> None:
    _require(
        before.role == "cutover" and after.role == "cutover" and before.volume == after.volume,
        "8.19-to-9.5 cutover must restart the same exclusively-owned Docker data volume.",
    )


def assert_fresh_rollback_volume(upgraded: ClusterHandle, rollback: ClusterHandle) -> None:
    _require(
        rollback.role == "rollback" and rollback.volume != upgraded.volume,
        "Rollback must restore into a separate, fresh Docker data volume.",
    )


def upgrade_same_volume(runtime: DockerRuntime, restored8: ClusterHandle) -> ClusterHandle:
    _require(
        restored8.role == "cutover" and restored8.version == SOURCE_VERSION,
        "Major upgrade can only start from the owned 8.19.11 cutover container.",
    )
    runtime.stop_and_remove_container(restored8)
    upgraded = runtime.start("cutover", TARGET_VERSION, "cutover", repository_readonly=True)
    assert_same_data_volume(restored8, upgraded)
    return upgraded


def _copy_seed_repository(source: Path, work_dir: Path) -> None:
    source = source.resolve(strict=True)
    _require(source.is_dir() and any(source.iterdir()), "Seed snapshot repository must be a non-empty directory.")
    symlinks = [str(path) for path in source.rglob("*") if path.is_symlink()]
    _require(not symlinks, f"Refusing seed repositories containing symlinks: {symlinks[:10]}.")
    shutil.copytree(source, work_dir / "seed")
    (work_dir / "rehearsal").mkdir()


def _seed_snapshot_repo_paths(nodes_response: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for node in nodes_response.get("nodes", {}).values():
        settings = node.get("settings", {})
        value = settings.get("path", {}).get("repo", settings.get("path.repo", []))
        if isinstance(value, str):
            paths.add(value)
        elif isinstance(value, list):
            paths.update(item for item in value if isinstance(item, str))
    return paths


def prepare_synthetic_seed(args: argparse.Namespace) -> dict[str, Any]:
    """Validate an owned, empty 8.19.11 Docker seed before writing the canonical fixture."""
    _require(
        re.fullmatch(r"[a-z0-9][a-z0-9-]{0,35}", args.seed_run_id) is not None,
        "Seed run ID must contain lowercase letters, digits, or hyphens and start alphanumeric.",
    )
    seed_repo = Path(args.seed_repository).expanduser().resolve(strict=True)
    _require(
        seed_repo.is_dir() and not any(seed_repo.iterdir()),
        "Synthetic seed repository must exist and be empty before preparation.",
    )
    _require(
        not any(path.is_symlink() for path in seed_repo.rglob("*")),
        "Synthetic seed repository may not contain symlinks.",
    )
    _require("," not in str(seed_repo), "Docker bind paths may not contain commas.")
    _require(args.timeout > 0, "Request timeout must be positive.")

    runtime = DockerRuntime(args.seed_run_id, seed_repo, args.timeout)
    runtime._assert_local_context()
    container_data = json.loads(runtime._docker(["inspect", args.seed_container]))[0]
    _require(
        container_data.get("Name", "").lstrip("/") == args.seed_container,
        "Seed Docker inspect returned a different container name.",
    )
    labels = container_data.get("Config", {}).get("Labels", {})
    container_id = container_data.get("Id")
    _require(isinstance(container_id, str) and bool(container_id), "Seed container ID is missing.")
    _require(
        labels.get(LABEL_KEY) == "true"
        and labels.get("howler.step9.run") == args.seed_run_id
        and labels.get("howler.step9.role") == "seed",
        "Seed container is not labelled for this exact rehearsal run and seed role.",
    )
    mounts = container_data.get("Mounts", [])
    data_mounts = [mount for mount in mounts if mount.get("Destination") == DATA_PATH]
    _require(
        len(data_mounts) == 1 and data_mounts[0].get("Type") == "volume",
        "Seed must use exactly one named Docker data volume.",
    )
    seed_volume = data_mounts[0].get("Name")
    _require(isinstance(seed_volume, str) and bool(seed_volume), "Seed data volume name is missing.")
    _require(
        seed_volume == args.seed_volume,
        f"Seed container is attached to volume {seed_volume!r}, not the explicitly confirmed {args.seed_volume!r}.",
    )
    volume_data = json.loads(runtime._docker(["volume", "inspect", seed_volume]))[0]
    volume_labels = volume_data.get("Labels", {})
    _require(
        volume_data.get("Name") == seed_volume
        and volume_data.get("Driver") == "local"
        and volume_labels.get(LABEL_KEY) == "true"
        and volume_labels.get("howler.step9.run") == args.seed_run_id
        and volume_labels.get("howler.step9.role") == "seed",
        "Seed data volume is not an exclusively labelled local Docker volume.",
    )
    networks = container_data.get("NetworkSettings", {}).get("Networks", {})
    _require(set(networks) == {args.seed_network}, "Seed must attach only to the named private internal network.")
    runtime.network = args.seed_network
    seed_handle = ClusterHandle(
        "seed",
        args.seed_container,
        container_id,
        seed_volume,
        args.confirm_seed_cluster,
        SOURCE_VERSION,
        "",
        False,
    )
    runtime.handles["seed"] = seed_handle
    seed_ip = runtime._verify_container(seed_handle, expected_state="running")
    # Docker reports a running container before Elasticsearch accepts requests. Use the
    # same identity-checked readiness gate as the restore and upgrade phases.
    seed_handle = ClusterHandle(
        "seed",
        args.seed_container,
        container_id,
        seed_volume,
        args.confirm_seed_cluster,
        SOURCE_VERSION,
        f"http://{seed_ip}:9200",
        False,
    )
    runtime.handles["seed"] = seed_handle
    client, _ = wait_for_cluster(seed_handle, runtime, args.timeout)

    # All checks above and these read-only cluster checks precede the first PUT.
    info = _root(client, args.confirm_seed_cluster, SOURCE_VERSION)
    _require(
        args.confirm_seed_cluster.startswith("howler-step9-seed-"),
        "Seed cluster name must use the dedicated howler-step9-seed- prefix.",
    )
    health = client.request("GET", "/_cluster/health")
    _require(health.get("status") in {"green", "yellow"}, f"Seed cluster is not healthy: {health!r}.")
    inventory = _index_inventory(client)
    _require(not inventory, f"Seed cluster must be empty before fixture creation; found {sorted(inventory)}.")
    nodes = client.request("GET", "/_nodes/settings")
    _require(
        REPOSITORY_PATH in _seed_snapshot_repo_paths(nodes),
        f"Seed container path.repo must include {REPOSITORY_PATH!r}.",
    )
    repositories = client.request("GET", "/_snapshot/_all")
    _require(
        "step9-seed" not in repositories,
        "Seed repository name step9-seed is already registered; use a fresh seed cluster.",
    )

    # Probe the empty bind mount as the Elasticsearch UID after every ownership and cluster
    # gate has passed, but before changing cluster state or creating index data.
    probe_path = f"{REPOSITORY_PATH}/.step9-seed-write-probe-{args.seed_run_id}"
    runtime._docker(
        [
            "exec",
            "--user",
            "1000:0",
            container_id,
            "sh",
            "-c",
            'test ! -e "$1" && : > "$1" && rm "$1"',
            "sh",
            probe_path,
        ]
    )

    # Begin cluster-state/index writes only after local-daemon/container/network/volume/identity/empty-state gates.
    for index in SYNTHETIC_INDICES:
        alias = SYNTHETIC_ALIASES[index]
        client.request(
            "PUT",
            f"/{index}",
            {
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": SYNTHETIC_MAPPINGS[index],
                "aliases": {alias: {"is_write_index": True}},
            },
        )
    for hit_id, source in SYNTHETIC_HITS.items():
        client.request(
            "PUT",
            f"/{SYNTHETIC_HIT_INDEX}/_doc/{urllib.parse.quote(hit_id, safe='')}?refresh=wait_for",
            source,
        )
    client.request(
        "PUT",
        f"/{SYNTHETIC_CASE_INDEX}/_doc/{urllib.parse.quote(SYNTHETIC_CASE_ID, safe='')}?refresh=wait_for",
        SYNTHETIC_CASE,
    )
    verify_synthetic_fixture(client, SYNTHETIC_INDICES)
    register_repository(client, "step9-seed", REPOSITORY_PATH, readonly=False)
    create_snapshot(client, "step9-seed", args.seed_snapshot, SYNTHETIC_INDICES, args.confirm_seed_cluster)
    snapshot = snapshot_metadata(client, "step9-seed", args.seed_snapshot)
    _require(snapshot.get("state") == "SUCCESS", f"Canonical seed snapshot failed: {snapshot!r}.")
    version_info = validate_snapshot_version(snapshot, SOURCE_VERSION)
    _require(
        sorted(snapshot.get("indices", [])) == SYNTHETIC_INDICES,
        "Canonical seed snapshot index list differs from fixture contract.",
    )
    return {
        "result": "SEED_READY",
        "cluster_name": info["cluster_name"],
        "cluster_uuid": info["cluster_uuid"],
        "image_version": info["version"]["number"],
        "snapshot": args.seed_snapshot,
        "snapshot_metadata": version_info,
        "manifest_sha256": synthetic_fixture_checksum(),
        "indices": SYNTHETIC_INDICES,
        "hit_ids": sorted(SYNTHETIC_HITS),
        "case_id": SYNTHETIC_CASE_ID,
    }


def _docker_api_wait(handle: ClusterHandle, runtime: DockerRuntime, timeout: int) -> tuple[RestClient, dict[str, Any]]:
    return wait_for_cluster(handle, runtime, timeout)


def _copy_report(work_dir: Path, report: dict[str, Any]) -> None:
    _write_json(work_dir / "rehearsal-report.json", report)


def run_workflow(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or uuid.uuid4().hex[:12]
    _require(
        re.fullmatch(r"[a-z0-9][a-z0-9-]{0,35}", run_id) is not None,
        "--run-id must contain 1-36 lowercase letters, digits, or hyphens and start alphanumeric.",
    )
    seed_repo = Path(args.seed_repository).resolve(strict=True)
    work_dir = Path(args.work_dir).expanduser().resolve()
    _require(not work_dir.exists(), f"Work directory already exists; refusing to reuse: {work_dir}.")
    _require(work_dir.parent.is_dir(), "The work directory parent must already exist.")
    _require(
        not work_dir.is_relative_to(seed_repo),
        "Work directory must not be nested inside the read-only seed snapshot repository.",
    )
    _require("," not in str(work_dir) and "," not in str(seed_repo), "Docker bind paths may not contain commas.")
    _require(
        args.timeout > 0 and args.max_docs > 0,
        "Request timeout and document cap must be positive.",
    )
    _require(
        args.index_pattern.startswith("howler-") and "," not in args.index_pattern,
        "Index pattern must select a Howler family such as howler-*.",
    )
    work_dir.mkdir()
    _copy_seed_repository(seed_repo, work_dir)
    runtime = DockerRuntime(run_id, work_dir, args.timeout)
    report: dict[str, Any] = {
        "run_id": run_id,
        "workflow_result": "ABORTED",
        "scope": "isolated_sanitized_index_data_rehearsal_not_production_evidence",
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "seed_snapshot": args.seed_snapshot,
        "snapshot": f"step9-{run_id}",
        "resources": runtime.resources,
        "phases": [],
        "application_verification": {
            "result": "BLOCKED_UNAVAILABLE",
            "reason": (
                "No executable Howler authentication/ACL/query verifier is configured; "
                "status-only reports are not accepted."
            ),
        },
    }
    if args.synthetic_fixture:
        report["synthetic_fixture"] = {
            "manifest_sha256": synthetic_fixture_checksum(),
            "indices": SYNTHETIC_INDICES,
            "hit_document_ids": sorted(SYNTHETIC_HITS),
            "case_document_id": SYNTHETIC_CASE_ID,
        }
    try:
        runtime.create_base_resources()
        rehearsal_repo_path = f"{REPOSITORY_PATH}/rehearsal"
        seed_repo_path = f"{REPOSITORY_PATH}/seed"

        donor = runtime.start("donor", SOURCE_VERSION, "donor", repository_readonly=False)
        donor_client, donor_info = _docker_api_wait(donor, runtime, args.timeout)
        _require(not _index_inventory(donor_client), "Fresh donor volume is not empty before seed restore.")
        register_repository(donor_client, "step9-seed", seed_repo_path, readonly=True)
        seed = snapshot_metadata(donor_client, "step9-seed", args.seed_snapshot)
        _require(seed.get("state") == "SUCCESS", f"Seed snapshot must be successful: {seed!r}.")
        seed_version = validate_snapshot_version(seed, SOURCE_VERSION)
        report["seed_snapshot_metadata"] = {
            "snapshot": args.seed_snapshot,
            **seed_version,
        }
        seed_inventory = {name: {} for name in seed.get("indices", [])}
        seed_names = _selected_names(seed_inventory, args.index_pattern)
        _require(
            seed_names == sorted(seed_inventory),
            "Seed snapshot contains indices outside the selected Howler scope; use a dedicated sanitized snapshot.",
        )
        restore_snapshot(donor_client, "step9-seed", args.seed_snapshot, seed_names)
        donor_health = donor_client.request("GET", "/_cluster/health?wait_for_status=yellow&timeout=600s")
        _require(
            donor_health.get("timed_out") is not True and donor_health.get("status") in {"green", "yellow"},
            f"Donor restore did not become healthy: {donor_health!r}.",
        )
        donor_inventory = _index_inventory(donor_client)
        names = _selected_names(donor_inventory, args.index_pattern)
        _require(names == seed_names, "Donor restore did not produce the exact selected seed indices.")
        if args.synthetic_fixture:
            verify_synthetic_fixture(donor_client, names)
        donor_preflight = upgrade_preflight(donor_client, donor.cluster_name, donor_inventory)
        donor_state = capture_data_state(donor_client, names, args.max_docs)
        register_repository(donor_client, "step9-rehearsal", rehearsal_repo_path, readonly=False)
        create_snapshot(donor_client, "step9-rehearsal", report["snapshot"], names, donor.cluster_name)
        created = snapshot_metadata(donor_client, "step9-rehearsal", report["snapshot"])
        _require(
            created.get("state") == "SUCCESS",
            f"Donor snapshot did not verify as an 8.19.11 success: {created!r}.",
        )
        report["donor_snapshot_metadata"] = validate_snapshot_version(created, SOURCE_VERSION)
        _require(sorted(created.get("indices", [])) == names, "Donor snapshot has unexpected contents.")
        report["donor"] = {
            "cluster_uuid": donor_info["cluster_uuid"],
            "preflight": donor_preflight,
            **_state_summary(donor_state),
        }
        report["phases"].append("donor_seed_restored_and_8_19_snapshot_created")
        runtime.stop_and_remove_container(donor)

        # Restore into a new 8.19.11 container and a new volume, not into the 9.5 image.
        restored8 = runtime.start("cutover", SOURCE_VERSION, "cutover", repository_readonly=True)
        _require(restored8.volume != donor.volume, "8.19 restore must use a volume separate from the donor.")
        restored8_client, restored8_info = _docker_api_wait(restored8, runtime, args.timeout)
        _require(
            restored8_info["cluster_uuid"] != donor_info["cluster_uuid"],
            "Fresh 8.19 restore must have an independent cluster UUID from its donor.",
        )
        register_repository(restored8_client, "step9-rehearsal", rehearsal_repo_path, readonly=True)
        _require(not _index_inventory(restored8_client), "Fresh 8.19.11 restore volume is not empty.")
        restore_snapshot(restored8_client, "step9-rehearsal", report["snapshot"], names)
        health8 = restored8_client.request("GET", "/_cluster/health?wait_for_status=yellow&timeout=600s")
        _require(
            health8.get("timed_out") is not True and health8.get("status") in {"green", "yellow"},
            f"Fresh 8.19.11 snapshot restore did not become healthy: {health8!r}.",
        )
        inventory8 = _index_inventory(restored8_client)
        preflight8 = upgrade_preflight(restored8_client, restored8.cluster_name, inventory8)
        if args.synthetic_fixture:
            verify_synthetic_fixture(restored8_client, names)
        state8 = capture_data_state(restored8_client, names, args.max_docs)
        verify_data_identity(donor_state, state8, phase="fresh 8.19 restore", require_uuid_match=False)
        report["restored_8_19"] = {
            "cluster_uuid": restored8_info["cluster_uuid"],
            "preflight": preflight8,
            **_state_summary(state8),
        }
        report["phases"].append("snapshot_restored_into_fresh_8_19_volume_and_preflight_passed")

        # Stop/remove only the labelled 8.19 container. The named data volume is retained.
        upgraded = upgrade_same_volume(runtime, restored8)
        upgraded_client, upgraded_info = _docker_api_wait(upgraded, runtime, args.timeout)
        validate_cluster_info(upgraded_info, upgraded.cluster_name, TARGET_VERSION, restored8_info["cluster_uuid"])
        health9 = upgraded_client.request("GET", "/_cluster/health?wait_for_status=yellow&timeout=600s")
        _require(
            health9.get("timed_out") is not True and health9.get("status") in {"green", "yellow"},
            f"9.5.2 upgraded cluster did not become healthy: {health9!r}.",
        )
        inventory9 = _index_inventory(upgraded_client)
        if args.synthetic_fixture:
            verify_synthetic_fixture(upgraded_client, names)
        state9 = capture_data_state(upgraded_client, names, args.max_docs)
        verify_data_identity(state8, state9, phase="9.5.2 same-volume upgrade", require_uuid_match=True)
        _require(
            not any(REINDEX_MARKER in name for name in inventory9),
            "An Elasticsearch __reindex temporary index appeared during the 9.5.2 restart.",
        )
        report["upgraded_9_5"] = {
            "cluster_uuid": upgraded_info["cluster_uuid"],
            "health": health9.get("status"),
            **_state_summary(state9),
        }
        report["phases"].append("same_volume_restarted_on_9_5_2_and_uuid_content_checks_passed")

        report["phases"].append("application_acl_query_gate_blocked_no_executable_verifier")

        # Roll back by restoring the saved 8.19 snapshot into a third, independent 8.19 volume.
        runtime.stop_and_remove_container(upgraded)
        rollback = runtime.start("rollback", SOURCE_VERSION, "rollback", repository_readonly=True)
        rollback_client, rollback_info = _docker_api_wait(rollback, runtime, args.timeout)
        assert_fresh_rollback_volume(upgraded, rollback)
        _require(
            rollback.volume != donor.volume,
            "Independent rollback must not reuse the donor data volume.",
        )
        register_repository(rollback_client, "step9-rehearsal", rehearsal_repo_path, readonly=True)
        _require(not _index_inventory(rollback_client), "Fresh rollback volume is not empty.")
        restore_snapshot(rollback_client, "step9-rehearsal", report["snapshot"], names)
        rollback_health = rollback_client.request("GET", "/_cluster/health?wait_for_status=yellow&timeout=600s")
        _require(
            rollback_health.get("timed_out") is not True and rollback_health.get("status") in {"green", "yellow"},
            f"Fresh 8.19 rollback restore did not become healthy: {rollback_health!r}.",
        )
        rollback_inventory = _index_inventory(rollback_client)
        rollback_preflight = upgrade_preflight(rollback_client, rollback.cluster_name, rollback_inventory)
        if args.synthetic_fixture:
            verify_synthetic_fixture(rollback_client, names)
        rollback_state = capture_data_state(rollback_client, names, args.max_docs)
        verify_data_identity(donor_state, rollback_state, phase="fresh 8.19 rollback restore", require_uuid_match=False)
        _require(
            rollback_info["cluster_uuid"] != upgraded_info["cluster_uuid"],
            "Rollback did not create an independent Elasticsearch cluster identity.",
        )
        _require(
            rollback_info["cluster_uuid"] != donor_info["cluster_uuid"],
            "Rollback cluster identity unexpectedly matches the donor.",
        )
        report["rollback_8_19"] = {
            "cluster_uuid": rollback_info["cluster_uuid"],
            "preflight": rollback_preflight,
            **_state_summary(rollback_state),
        }
        report["phases"].append("independent_fresh_8_19_rollback_restore_and_identity_checks_passed")
        report["workflow_result"] = "BLOCKED_APPLICATION_VERIFICATION_UNAVAILABLE"
        return report
    except Exception as error:
        report["blocker"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["resources"] = runtime.resources
        _copy_report(work_dir, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prepare-synthetic-seed",
        action="store_true",
        help="Safely populate and snapshot the canonical fixture on an explicitly verified empty seed container.",
    )
    parser.add_argument(
        "--seed-repository",
        help="Local, sanitized Elasticsearch 8.19 snapshot repository directory; copied, never modified.",
    )
    parser.add_argument(
        "--seed-snapshot", help="Seed snapshot name to create (prepare mode) or restore (rehearsal mode)."
    )
    parser.add_argument(
        "--work-dir",
        help="New work directory for the copied snapshot repositories and rehearsal report (rehearsal mode).",
    )
    parser.add_argument("--seed-container", help="Exact existing Docker seed-container name (prepare mode).")
    parser.add_argument("--seed-network", help="Exact internal Docker network containing only the seed container.")
    parser.add_argument("--seed-volume", help="Exact local named seed data volume.")
    parser.add_argument("--seed-run-id", help="Run label attached to the seed container/network/volume.")
    parser.add_argument("--confirm-seed-cluster", help="Exact Elasticsearch cluster_name on the seed container.")
    parser.add_argument("--run-id", help="Unique lowercase resource suffix; generated when omitted.")
    parser.add_argument("--index-pattern", default="howler-*", help="Representative Howler indices (default howler-*).")
    parser.add_argument(
        "--synthetic-fixture",
        action="store_true",
        help="Require the exact documented deterministic IDs, classifications, alias, and document contents.",
    )
    parser.add_argument("--timeout", type=int, default=900, help="Per-request/cluster readiness timeout in seconds.")
    parser.add_argument(
        "--max-docs",
        type=int,
        default=MAX_DOCS_PER_INDEX,
        help="Maximum documents per selected index for full content hashing.",
    )
    args = parser.parse_args()
    try:
        if args.prepare_synthetic_seed:
            missing = [
                option
                for option in (
                    "seed_repository",
                    "seed_snapshot",
                    "seed_container",
                    "seed_network",
                    "seed_volume",
                    "seed_run_id",
                    "confirm_seed_cluster",
                )
                if not getattr(args, option)
            ]
            _require(not missing, f"Synthetic seed preparation is missing required options: {missing}.")
            result = prepare_synthetic_seed(args)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        _require(
            args.seed_repository and args.seed_snapshot and args.work_dir,
            "Rehearsal mode requires --seed-repository, --seed-snapshot, and --work-dir.",
        )
        result = run_workflow(args)
    except RehearsalAbort as error:
        print(f"ABORT: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    print(
        "BLOCKED: Elasticsearch phases completed, but executable application ACL/query verification is unavailable.",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
