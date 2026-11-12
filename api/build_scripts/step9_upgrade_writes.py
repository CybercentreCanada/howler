"""Prove real Howler collection writes against a freshly upgraded Step 9 application corpus.

This runner composes the reviewed read-only Step 9 fixture/upgrade helpers instead of
copying their Elasticsearch, snapshot, Docker-ownership, and rollback implementation. It
adds one write-probe hook around the existing full rehearsal and runs registered
``ESCollection`` operations in a separate, sanitized child process. Every ES cluster,
volume, snapshot directory, Redis instance, configuration file, and log directory is
owned by the one labelled rehearsal run.

The application-v2 fixture captures the exact document JSON passed by origin/main's
legacy ``ESCollection.save`` path. In particular, its Hit and Case sources include the
persisted ``__index`` helper before index creation and snapshotting; no seed-time source
patching is performed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import ipaddress
import json
import re
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def _requested_api_root() -> Path | None:
    """Read an explicit API root before loading any API/build-script module."""
    for index, argument in enumerate(sys.argv):
        if argument.startswith("--api-root="):
            return Path(argument.partition("=")[2]).expanduser().resolve()
        if argument == "--api-root" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).expanduser().resolve()
    return None


API_ROOT = (_requested_api_root() or Path(__file__).resolve().parents[1]).resolve()
BUILD_SCRIPTS = API_ROOT / "build_scripts"
_required_helpers = (
    BUILD_SCRIPTS / "upgrade_rehearsal.py",
    BUILD_SCRIPTS / "step9_application.py",
    BUILD_SCRIPTS / "step9_application_rehearsal.py",
)
if not all(path.is_file() for path in _required_helpers):
    raise ImportError(f"The selected API root is missing reviewed Step 9 helpers: {API_ROOT}")
sys.path.insert(0, str(BUILD_SCRIPTS))
sys.dont_write_bytecode = True

import step9_application as application_fixture  # noqa: E402
import step9_application_rehearsal as application_rehearsal  # noqa: E402
import upgrade_rehearsal as es_rehearsal  # noqa: E402

for _module in (application_fixture, application_rehearsal, es_rehearsal):
    _module_path = Path(_module.__file__ or "").resolve()
    if not _module_path.is_relative_to(BUILD_SCRIPTS.resolve()):
        raise ImportError(f"Step 9 helper {_module.__name__} was imported outside --api-root: {_module_path}")


RehearsalAbort = es_rehearsal.RehearsalAbort
_RUN_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,35}\Z")
_SOURCE_COMMIT = application_fixture.LEGACY_SOURCE_COMMIT
_RUNTIME_INSTANCES: list[Any] = []


def _require(condition: bool, message: str) -> None:
    es_rehearsal._require(condition, message)


def derive_namespace(run_id: str) -> str:
    """Derive and verify the non-default index prefix for exactly one owned run."""
    _require(isinstance(run_id, str) and _RUN_ID_PATTERN.fullmatch(run_id) is not None, "Invalid Step 9 run ID.")
    namespace = application_rehearsal.derive_namespace(run_id)
    _require(namespace == f"step9-app-{run_id}", "Write probe namespace is not the unique per-run namespace.")
    _require(not namespace.startswith("howler-"), "The default Howler namespace is forbidden.")
    return namespace


def validate_legacy_storage_plan(plan: Any) -> Any:
    """Require application-v2 seed sources to match captured legacy save output exactly."""
    _require(plan.fixture_version == "application-v2", "Write probe only supports application-v2.")
    _require(
        plan.application_verification_status == "NOT_RUN",
        "A prefilled application status cannot authorize the write rehearsal.",
    )
    counts: dict[str, int] = {}
    for document in plan.documents:
        counts[document.collection] = counts.get(document.collection, 0) + 1
        source = document.source
        _require(source.get("id") == document.document_id, "Fixture document ID/source mismatch; refusing to seed.")
        expected_helper = application_fixture.LEGACY_INDEX_HELPERS.get(document.collection)
        if expected_helper is None:
            _require("__index" not in source, f"Unexpected legacy __index helper in {document.collection} source.")
        else:
            _require(
                source.get("__index") == expected_helper,
                f"Captured {document.collection} source is missing persisted __index={expected_helper}.",
            )

    _require(counts == application_fixture.DOCUMENT_COUNTS, f"Fixture document inventory changed: {counts!r}.")
    return plan


def validate_legacy_helper_provenance(api_root: Path) -> dict[str, Any]:
    """Prove origin/main emitted and persisted the source helpers stored in application-v2."""
    api_root = api_root.resolve(strict=True)
    _require((api_root / "howler" / "app.py").is_file(), "--api-root is not a Howler API source tree.")
    fixture = application_fixture.load_application_fixture()
    source_commit = fixture["metadata"].get("captured_from_commit")
    _require(
        source_commit == _SOURCE_COMMIT,
        "Legacy source provenance must match the exact origin/main capture commit.",
    )
    provenance = fixture["metadata"]["stored_document_capture"]["provenance"]
    source_hashes = provenance["legacy_source_file_sha256"]
    source_texts: dict[str, str] = {}

    def show(path: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(api_root), "show", f"{source_commit}:api/{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        _require(result.returncode == 0, f"Could not read pinned legacy source {path}: {result.stderr.strip()[:500]}.")
        expected_hash = source_hashes.get(path)
        actual_hash = hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()
        _require(expected_hash == actual_hash, f"Pinned legacy source file hash changed for {path}.")
        source_texts[path] = result.stdout
        return result.stdout

    for path in source_hashes:
        show(path)

    serializers: dict[str, dict[str, str]] = {}
    for collection, path in (
        ("hit", "howler/odm/models/record.py"),
        ("case", "howler/odm/models/case.py"),
    ):
        text = source_texts[path]
        _require(
            'result["__index"] = self.__class__.__name__.lower()' in text,
            f"Pinned origin/main {collection} serializer does not prove the __index helper contract.",
        )
        serializers[collection] = {"git_path": f"api/{path}", "emitted_value": collection}

    collection_path = "howler/datastore/collection.py"
    collection_source = source_texts[collection_path]
    save_start = collection_source.find("    def save(")
    save_end = collection_source.find("\n    def delete(", save_start)
    _require(save_start >= 0 and save_end > save_start, "Pinned legacy ESCollection.save implementation is missing.")
    save_source = collection_source[save_start:save_end]
    _require(
        "saved_data = data.as_primitives(hidden_fields=True)" in save_source
        and 'saved_data["id"] = key' in save_source
        and "document=json.dumps(saved_data)" in save_source
        and 'saved_data.pop("__index"' not in save_source,
        "Pinned origin/main ESCollection.save no longer proves serialized __index is stored in _source.",
    )

    postprocessing = fixture["metadata"]["stored_document_capture"]["source_postprocessing"]
    _require(
        not any("__index" in item and "remov" in item.lower() for item in postprocessing),
        "The refreshed fixture must not remove an __index helper emitted by legacy save.",
    )
    return {
        "source_commit": source_commit,
        "serializer_contract": serializers,
        "persistence_contract": {
            "git_path": f"api/{collection_path}",
            "method": "ESCollection.save",
            "serializes_hidden_fields": True,
            "adds_id_then_json_encodes_saved_data": True,
            "removes___index_before_write": False,
        },
        "fixture_representation": {
            "source_postprocessing_removed___index": False,
            "conclusion": "application-v2 preserves the exact origin/main ESCollection.save payload.",
        },
        "source_file_sha256": source_hashes,
        "capture_command": provenance["capture_command"],
    }


def validate_write_probe_target(runtime: Any, handle: Any, plan: Any) -> dict[str, Any]:
    """Fail closed unless the child will target this run's private ES 9.5 cutover volume."""
    run_id = getattr(runtime, "run_id", None)
    namespace = derive_namespace(run_id) if isinstance(run_id, str) else ""
    _require(plan.namespace == namespace, "Seed-plan namespace differs from the owned Docker run.")
    _require(runtime.handles.get("cutover") is handle, "Write probe target is not this runtime's cutover handle.")
    _require(handle.role == "cutover", "Write probe may only target the restored cutover role.")
    _require(handle.version == es_rehearsal.TARGET_VERSION, "Write probe requires the same-volume ES 9.5 target.")
    _require(handle.cluster_name == f"howler-step9-{run_id}-cutover", "Cutover cluster name is not run-owned.")
    _require(handle.volume == runtime.volumes.get("cutover"), "Cutover container is not on its owned volume.")
    _require(handle.repository_readonly is True, "Cutover snapshot repository must be mounted read-only.")
    parsed = urlsplit(handle.base_url)
    _require(
        parsed.scheme == "http"
        and parsed.port == 9200
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment,
        "Write probe target must be an unauthenticated private bridge ES endpoint.",
    )
    _require(parsed.hostname is not None, "Cutover target endpoint has no host.")
    try:
        endpoint_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError as error:
        raise RehearsalAbort("Write probe target must be a private bridge IPv4 endpoint.") from error
    _require(endpoint_ip.version == 4 and endpoint_ip.is_private, "Write probe target is not a private IPv4 endpoint.")
    expected_indices = [index.index_name for index in plan.indexes]
    _require(
        len(expected_indices) == len(application_fixture.COLLECTION_NAMES)
        and all(name.startswith(f"{namespace}-howler-") and name.endswith("_hot") for name in expected_indices),
        "Write probe physical indices are not exactly under the per-run Howler namespace.",
    )
    return {
        "run_id": run_id,
        "namespace": namespace,
        "cluster_name": handle.cluster_name,
        "cluster_version": handle.version,
        "cluster_uuid": None,
        "volume": handle.volume,
        "endpoint_host": parsed.hostname,
        "index_names": expected_indices,
    }


def validate_stale_version_observation(observation: dict[str, Any]) -> None:
    """Require a stale save to conflict and leave both source and current token untouched."""
    _require(
        observation.get("exception_type") == "VersionConflictException",
        "A stale full-model save was not rejected with VersionConflictException.",
    )
    _require(
        observation.get("source_unchanged") is True,
        "The stale full-model save changed the current document source.",
    )
    _require(
        observation.get("version_before") == observation.get("version_after"),
        "The stale full-model save changed the current document version token.",
    )


def validate_owned_clone_ids(clone_ids: list[str], fixture_ids: set[str]) -> None:
    """Allow cleanup only for two unique, valid UUIDs outside the frozen fixture corpus."""
    _require(len(clone_ids) == 2 and len(set(clone_ids)) == 2, "Probe clone cleanup IDs must be exactly two uniques.")
    for clone_id in clone_ids:
        try:
            normalized = str(uuid.UUID(clone_id))
        except (AttributeError, TypeError, ValueError) as error:
            raise RehearsalAbort(f"Probe clone cleanup ID is not a UUID: {clone_id!r}.") from error
        _require(normalized == clone_id, "Probe clone cleanup ID is not in canonical UUID format.")
        _require(clone_id not in fixture_ids, "Probe clone cleanup ID overlaps a frozen fixture document.")


def validate_write_state(
    before: dict[str, Any],
    after: dict[str, Any],
    expected_names: list[str],
    *,
    expected_dynamic_fields: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Prove identity/source stability and allow only explicitly derived dynamic mappings."""
    before_inventory = set(before["inventory"])
    after_inventory = set(after["inventory"])
    _require(before_inventory == after_inventory, "Write probe changed the index inventory.")
    _require(
        not any("__reindex" in name for name in before_inventory | after_inventory),
        "A __reindex temporary index exists in the write-probe inventory.",
    )
    before_state = before["application_state"]
    after_state = after["application_state"]
    _require(
        sorted(before_state["index_uuids"]) == sorted(expected_names),
        "Pre-write UUID inventory differs from the 11 expected application-v2 indices.",
    )
    _require(
        before_state["index_uuids"] == after_state["index_uuids"],
        "Write probe changed one or more physical index UUIDs.",
    )
    for key in ("aliases", "counts", "document_sha256"):
        _require(before_state[key] == after_state[key], f"Write probe did not restore application {key} exactly.")
    mapping_changes = sorted(
        name for name in before_state["mappings"] if before_state["mappings"][name] != after_state["mappings"].get(name)
    )
    expected_dynamic_fields = expected_dynamic_fields or {}
    _require(
        set(mapping_changes) == set(expected_dynamic_fields),
        f"Write probe changed application mappings outside the exact allowance: {mapping_changes!r}.",
    )
    explained_mapping_changes: dict[str, Any] = {}
    for index_name, field_name in expected_dynamic_fields.items():
        _require(
            index_name in expected_names, f"Dynamic mapping allowance targets an unexpected index: {index_name!r}."
        )
        expected_mapping = copy.deepcopy(before_state["mappings"][index_name])
        mapping_body = expected_mapping.get("mappings", {})
        properties = mapping_body.get("properties", {})
        labels = properties.get("labels")
        _require(
            isinstance(labels, dict) and labels.get("type") == "object" and "properties" not in labels,
            f"Expected empty object mapping at {index_name}:labels before the write probe.",
        )
        templates = mapping_body.get("dynamic_templates", [])
        _require(
            bool(templates) and isinstance(templates[0], dict) and "strings_as_keywords" in templates[0],
            f"Could not prove the first dynamic template for {index_name} labels.",
        )
        field_mapping = copy.deepcopy(templates[0]["strings_as_keywords"]["mapping"])
        _require(
            field_mapping == {"ignore_above": 8191, "type": "keyword"},
            f"Unexpected strings_as_keywords dynamic mapping contract for {index_name}: {field_mapping!r}.",
        )
        labels.pop("type")
        labels["properties"] = {field_name: field_mapping}
        _require(
            after_state["mappings"][index_name] == expected_mapping,
            f"Dynamic mapping change for {index_name}:{field_name} differs from the exact allowed template output.",
        )
        explained_mapping_changes[index_name] = {
            "field": f"labels.{field_name}",
            "mapping": field_mapping,
            "reason": (
                "Typed SET temporarily added a string key to the previously empty labels object; "
                "Elasticsearch applied the first strings_as_keywords dynamic template. The source was restored."
            ),
        }
    return {
        "result": "PASS",
        "inventory_before": sorted(before_inventory),
        "inventory_after": sorted(after_inventory),
        "index_uuids_before": before_state["index_uuids"],
        "index_uuids_after": after_state["index_uuids"],
        "aliases_before": before_state["aliases"],
        "aliases_after": after_state["aliases"],
        "mappings_before": before_state["mappings"],
        "mappings_after": after_state["mappings"],
        "mappings_unchanged": not explained_mapping_changes,
        "explained_mapping_changes": explained_mapping_changes,
        "document_sha256_before": before_state["document_sha256"],
        "document_sha256_after": after_state["document_sha256"],
        "application_state_before": before_state,
        "application_state_after": after_state,
        "reindex_indices": [],
    }


def write_state_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Retain exact before/after identity and mapping evidence, including failed drift."""
    before_state = before["application_state"]
    after_state = after["application_state"]
    changed: dict[str, list[str]] = {}
    for key in ("index_uuids", "aliases", "mappings", "counts", "document_sha256"):
        names = set(before_state.get(key, {})) | set(after_state.get(key, {}))
        changed[key] = sorted(
            name for name in names if before_state.get(key, {}).get(name) != after_state.get(key, {}).get(name)
        )
    return {
        "inventory_before": sorted(before["inventory"]),
        "inventory_after": sorted(after["inventory"]),
        "inventory_unchanged": set(before["inventory"]) == set(after["inventory"]),
        "changed": changed,
        "mapping_changes": {
            name: {
                "before": before_state.get("mappings", {}).get(name),
                "after": after_state.get("mappings", {}).get(name),
            }
            for name in changed["mappings"]
        },
        "application_state_before": before_state,
        "application_state_after": after_state,
    }


_WRITE_PROBE_CHILD_SOURCE = r"""
import copy
import json
import os
import sys
import traceback
from pathlib import Path

from howler.common.loader import DATASTORE_INDEX_PREFIX, datastore
from howler.config import DEBUG, HWL_USE_JOB_SYSTEM, HWL_USE_WEBSOCKET_API, config
from howler.datastore.collection import CREATE_TOKEN
from howler.datastore.exceptions import VersionConflictException


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def response_body(response):
    return response.body if hasattr(response, "body") else response


def raw_get(client, index, doc_id):
    result = response_body(client.get(index=index, id=doc_id))
    return result


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


spec = json.loads(Path(os.environ["STEP9_WRITE_PROBE_SPEC"]).read_text(encoding="utf-8"))
result_path = Path(os.environ["STEP9_WRITE_PROBE_RESULT"])
result = {
    "result": "FAIL",
    "collection": "hit",
    "document_id": spec.get("hit_id"),
    "write_effects": [],
    "stale_version": {},
    "cleanup": {"attempted": [], "removed": []},
    "source_restore": {},
    "failures": [],
}
registered_store = None
collection = None
client = None
baseline_source = None
clone_ids = list(spec.get("clone_ids", []))

try:
    require(DEBUG is False and HWL_USE_JOB_SYSTEM is False and HWL_USE_WEBSOCKET_API is False,
            "Debug/jobs/websockets must be disabled in the write child.")
    require(config.ui.debug is False, "Howler UI debug must be disabled in the write child.")
    require(config.auth.internal.enabled is False and config.auth.oauth.enabled is False,
            "Internal auth and OAuth must be disabled in the write child.")
    require(config.auth.allow_apikeys is True, "API keys must remain enabled for the Howler application contract.")
    require(config.core.plugins == set() and config.core.clue.enabled is False,
            "Plugins and Clue must be disabled in the write child.")
    require(config.core.notebook.enabled is False and config.core.telemetry.enabled is False,
            "Notebook and telemetry must be disabled in the write child.")
    require(config.datastore.ilm.enabled is False, "ILM must be disabled for the _hot source probe.")
    require(config.system.retention.enabled is False and config.system.view_cleanup.enabled is False,
            "Background cleanup jobs must be disabled in the write child.")
    require(config.system.correlation.enabled is False and config.system.action_queue.enabled is False,
            "Correlation/action jobs must be disabled in the write child.")
    require(os.environ.get("HWL_START_BACKGROUND_SERVICES") == "false",
            "Background services must remain disabled in the write child.")
    require(
        DATASTORE_INDEX_PREFIX == spec["index_prefix"],
        "Registered datastore prefix differs from the run namespace.",
    )
    require(DATASTORE_INDEX_PREFIX == os.environ["HWL_DATASTORE_INDEX_PREFIX"],
            "Registered datastore prefix differs from the sanitized environment.")
    require(config.datastore.hosts[0].host == os.environ["STEP9_ES_ENDPOINT"],
            "Application datastore host differs from the verified cutover endpoint.")
    require(config.logging.log_directory == os.environ["HWL_LOGGING__LOG_DIRECTORY"],
            "Application log directory escaped the owned rehearsal workspace.")

    registered_store = datastore(archive_access=False)
    collection = registered_store.hit
    client = collection.datastore.client
    require(collection.model_class.__name__ == "Hit", "The registered hit collection is not the Hit model.")
    require(collection.name == spec["alias"], "Registered hit alias differs from the exact run namespace.")
    require(collection.index_name == spec["index_name"], "Registered hit _hot physical index differs from fixture.")
    require(collection.ilm_config is None, "The hit collection unexpectedly enabled ILM.")
    require(collection.index_list_full == [spec["index_name"]],
            "The write probe found a historical/rollover index outside the one _hot physical index.")

    hit_id = spec["hit_id"]
    original_raw = raw_get(client, collection.name, hit_id)
    baseline_source = copy.deepcopy(original_raw["_source"])
    require(baseline_source == spec["expected_source"], "Seeded legacy hit source is corrupt or differs from fixture.")
    require(baseline_source.get("__index") == "hit", "Legacy hit source is missing its proven __index helper.")
    result["write_effects"].append({"action": "registered_get_raw_baseline", "index": original_raw["_index"]})

    record, original_version = collection.get(hit_id, version=True)
    require(record is not None and record.meta.id == hit_id, "Registered collection.get did not return the seeded Hit.")
    require(isinstance(original_version, str) and len(original_version.split("---")) == 2,
            "Non-ILM Hit get returned an unexpected version token contract.")
    initial_score = float(record.howler.score)
    full_score = round(initial_score + 0.125, 3)
    full_model = record.model_copy(deep=True)
    full_model.howler.score = full_score
    full_saved = collection.save(hit_id, full_model, version=original_version, refresh="wait_for")
    require(full_saved is True, "Registered full-model save did not return True.")
    full_record, full_version = collection.get(hit_id, version=True)
    full_source = raw_get(client, collection.name, hit_id)["_source"]
    expected_full_source = copy.deepcopy(baseline_source)
    expected_full_source["howler"]["score"] = full_score
    require(full_record.howler.score == full_score, "Full-model save was not visible through registered get.")
    require(full_version != original_version, "Full-model save did not advance the ES version token.")
    require(full_source == expected_full_source, "Full-model save changed fields beyond declared howler.score.")
    result["write_effects"].append({
        "action": "registered_full_model_save",
        "field": "howler.score",
        "before": initial_score,
        "after": full_score,
        "version_before": original_version,
        "version_after": full_version,
        "refresh": "wait_for",
        "returned": full_saved,
    })

    stale_model = full_record.model_copy(deep=True)
    stale_model.howler.score = round(full_score + 50.0, 3)
    stale_exception = None
    try:
        collection.save(hit_id, stale_model, version=original_version, refresh="wait_for")
    except VersionConflictException as error:
        stale_exception = type(error).__name__
    current_after_stale, version_after_stale = collection.get(hit_id, version=True)
    source_after_stale = raw_get(client, collection.name, hit_id)["_source"]
    result["stale_version"] = {
        "exception_type": stale_exception,
        "source_unchanged": source_after_stale == full_source,
        "version_before": full_version,
        "version_after": version_after_stale,
    }
    require(current_after_stale.howler.score == full_score, "Stale save changed the current Hit score.")
    require(stale_exception == "VersionConflictException", "Stale full-model save was not refused.")
    require(source_after_stale == full_source and version_after_stale == full_version,
            "Stale save changed the current source or version.")
    result["write_effects"].append({
        "action": "registered_stale_full_model_save_refused",
        "stale_version": original_version,
        "current_version": full_version,
        "exception_type": stale_exception,
        "source_unchanged": source_after_stale == full_source,
    })

    partial_score = round(full_score + 0.125, 3)
    partial_result = collection.update(
        hit_id,
        [(collection.UPDATE_SET, "howler.score", partial_score)],
        version=full_version,
        refresh="wait_for",
    )
    require(isinstance(partial_result, tuple) and len(partial_result) == 2 and partial_result[0] is True,
            "Registered typed SET partial update did not return (True, version).")
    partial_record, partial_version = collection.get(hit_id, version=True)
    partial_source = raw_get(client, collection.name, hit_id)["_source"]
    expected_partial_source = copy.deepcopy(baseline_source)
    expected_partial_source["howler"]["score"] = partial_score
    require(partial_record.howler.score == partial_score, "Registered typed SET was not visible through get.")
    require(partial_source == expected_partial_source, "Typed SET changed undeclared Hit source fields.")
    result["write_effects"].append({
        "action": "registered_typed_partial_set",
        "field": "howler.score",
        "value": partial_score,
        "version_before": full_version,
        "version_after": partial_version,
        "refresh": "wait_for",
        "returned": partial_result[0],
    })

    tags_before = copy.deepcopy(partial_source.get("tags", []))
    require(isinstance(tags_before, list) and all(isinstance(tag, str) for tag in tags_before),
            "Seeded Hit tags are not a typed string list.")
    appended_tag = "step9-write-probe-" + spec["run_id"]
    append_result = collection.update(
        hit_id,
        [(collection.UPDATE_APPEND, "tags", appended_tag)],
        version=partial_version,
        refresh="wait_for",
    )
    require(isinstance(append_result, tuple) and len(append_result) == 2 and append_result[0] is True,
            "Registered typed APPEND partial update did not return (True, version).")
    appended_record, appended_version = collection.get(hit_id, version=True)
    appended_source = raw_get(client, collection.name, hit_id)["_source"]
    expected_appended_source = copy.deepcopy(expected_partial_source)
    expected_appended_source["tags"] = [*tags_before, appended_tag]
    require(appended_tag in appended_record.tags, "Typed APPEND was not visible through registered get.")
    require(appended_source == expected_appended_source, "Typed APPEND changed undeclared Hit source fields.")
    result["write_effects"].append({
        "action": "registered_typed_partial_append",
        "field": "tags",
        "value": appended_tag,
        "version_before": partial_version,
        "version_after": appended_version,
        "refresh": "wait_for",
        "returned": append_result[0],
    })

    remove_result = collection.update(
        hit_id,
        [(collection.UPDATE_REMOVE, "tags", appended_tag)],
        version=appended_version,
        refresh="wait_for",
    )
    require(isinstance(remove_result, tuple) and len(remove_result) == 2 and remove_result[0] is True,
            "Registered typed list removal did not return (True, version).")
    removed_record, removed_version = collection.get(hit_id, version=True)
    removed_source = raw_get(client, collection.name, hit_id)["_source"]
    require(removed_record.tags == tags_before, "Typed list removal did not restore the original Hit tags.")
    require(removed_source == expected_partial_source, "Typed list removal changed undeclared Hit source fields.")
    result["write_effects"].append({
        "action": "registered_typed_partial_remove",
        "field": "tags",
        "value": appended_tag,
        "version_before": appended_version,
        "version_after": removed_version,
        "refresh": "wait_for",
        "returned": remove_result[0],
    })

    labels_before = copy.deepcopy(expected_partial_source.get("labels", {}))
    require(isinstance(labels_before, dict), "Seeded Hit labels are not a typed mapping.")
    delete_key = "step9-write-probe-" + spec["run_id"]
    labels_with_probe_key = {**labels_before, delete_key: "delete-me"}
    labels_set_result = collection.update(
        hit_id,
        [(collection.UPDATE_SET, "labels", labels_with_probe_key)],
        version=removed_version,
        refresh="wait_for",
    )
    require(
        isinstance(labels_set_result, tuple) and len(labels_set_result) == 2 and labels_set_result[0] is True,
        "Registered typed mapping SET did not return (True, version).",
    )
    labels_set_version = labels_set_result[1]
    expected_labels_set_source = copy.deepcopy(expected_partial_source)
    expected_labels_set_source["labels"] = labels_with_probe_key
    labels_set_source = raw_get(client, collection.name, hit_id)["_source"]
    require(labels_set_source == expected_labels_set_source, "Typed mapping SET changed undeclared Hit source fields.")
    result["write_effects"].append({
        "action": "registered_typed_partial_set_mapping_key",
        "field": "labels",
        "key": delete_key,
        "version_before": removed_version,
        "version_after": labels_set_version,
        "refresh": "wait_for",
        "returned": labels_set_result[0],
    })

    labels_delete_result = collection.update(
        hit_id,
        [(collection.UPDATE_DELETE, "labels", delete_key)],
        version=labels_set_version,
        refresh="wait_for",
    )
    require(
        isinstance(labels_delete_result, tuple) and len(labels_delete_result) == 2 and labels_delete_result[0] is True,
        "Registered typed mapping DELETE did not return (True, version).",
    )
    labels_deleted_version = labels_delete_result[1]
    labels_deleted_source = raw_get(client, collection.name, hit_id)["_source"]
    require(
        labels_deleted_source == expected_partial_source,
        "Typed mapping DELETE did not restore the captured Hit labels/source.",
    )
    result["write_effects"].append({
        "action": "registered_typed_partial_delete_mapping_key",
        "field": "labels",
        "key": delete_key,
        "version_before": labels_set_version,
        "version_after": labels_deleted_version,
        "refresh": "wait_for",
        "returned": labels_delete_result[0],
    })

    clone_id, bulk_clone_id = clone_ids
    for clone in clone_ids:
        missing, token = collection.get(clone, version=True)
        require(missing is None and token == CREATE_TOKEN,
                "Registered collection.get did not return CREATE_TOKEN for a fresh clone.")
    clone_source = copy.deepcopy(expected_partial_source)
    clone_source["id"] = clone_id
    clone_source["howler"]["id"] = clone_id
    created = collection.save(clone_id, clone_source, version=CREATE_TOKEN, refresh="wait_for")
    require(created is True, "Registered create-only full-model save with CREATE_TOKEN failed.")
    created_model, created_version = collection.get(clone_id, version=True)
    require(created_model is not None and created_model.meta.id == clone_id,
            "Registered get did not return the created clone.")
    require(created_model.howler.id == clone_id, "Created clone has a mismatched nested Howler ID.")
    result["write_effects"].append({
        "action": "registered_create_clone_with_CREATE_TOKEN",
        "clone_id": clone_id,
        "version_after": created_version,
        "refresh": "wait_for",
        "returned": created,
    })

    direct_deleted = collection.delete(clone_id, refresh="wait_for")
    require(direct_deleted is True, "Registered collection.delete did not delete the created Hit clone.")
    direct_missing, direct_token = collection.get(clone_id, version=True)
    require(direct_missing is None and direct_token == CREATE_TOKEN,
            "Registered collection.delete left the created Hit clone readable.")
    result["write_effects"].append({
        "action": "registered_collection_delete_clone",
        "clone_id": clone_id,
        "refresh": "wait_for",
        "returned": direct_deleted,
    })

    bulk_score = round(partial_score + 0.125, 3)
    bulk_source = copy.deepcopy(expected_partial_source)
    bulk_source["id"] = bulk_clone_id
    bulk_source["howler"]["id"] = bulk_clone_id
    bulk_plan = collection.get_bulk_plan()
    bulk_plan.add_update_operation(
        hit_id,
        {"howler": {"score": bulk_score}, "message": "THIS_FIELD_MUST_NOT_BE_MERGED"},
        fields=["howler.score"],
    )
    bulk_plan.add_insert_operation(bulk_clone_id, bulk_source)
    bulk_ok = collection.bulk(bulk_plan, refresh="wait_for")
    require(bulk_ok is True, "Registered bulk field-merge/create plan returned errors.")
    bulk_record, bulk_version = collection.get(hit_id, version=True)
    after_bulk_source = raw_get(client, collection.name, hit_id)["_source"]
    expected_bulk_source = copy.deepcopy(baseline_source)
    expected_bulk_source["howler"]["score"] = bulk_score
    require(bulk_record.howler.score == bulk_score, "Bulk field-merge SET was not visible through get.")
    require(bulk_record.message == baseline_source.get("message", ""),
            "Bulk field-merge overwrote the unselected message field.")
    require(after_bulk_source == expected_bulk_source, "Bulk field-merge changed fields outside howler.score.")
    bulk_created, bulk_created_version = collection.get(bulk_clone_id, version=True)
    require(bulk_created is not None and bulk_created.meta.id == bulk_clone_id,
            "Bulk create did not produce a readable registered Hit clone.")
    require(bulk_created.howler.id == bulk_clone_id, "Bulk-created clone has a mismatched nested Howler ID.")
    result["write_effects"].append({
        "action": "registered_bulk_field_merge_and_create_clone",
        "field": "howler.score",
        "value": bulk_score,
        "unselected_field": "message",
        "version_after": bulk_version,
        "bulk_clone_id": bulk_clone_id,
        "bulk_clone_version": bulk_created_version,
        "refresh": "wait_for",
        "returned": bulk_ok,
    })

    delete_plan = collection.get_bulk_plan()
    delete_plan.add_delete_operation(bulk_clone_id)
    deleted = collection.bulk(delete_plan, refresh="wait_for")
    require(deleted is True, "Registered bulk delete plan returned errors.")
    bulk_missing, bulk_token = collection.get(bulk_clone_id, version=True)
    require(bulk_missing is None and bulk_token == CREATE_TOKEN, "Bulk delete left its clone readable.")
    result["write_effects"].append({
        "action": "registered_bulk_delete_clone",
        "clone_id": bulk_clone_id,
        "refresh": "wait_for",
        "returned": deleted,
    })
    result["result"] = "PASS"

except Exception as error:
    result["failures"].append(f"{type(error).__name__}: {error}")
    result["traceback"] = traceback.format_exc()[-4000:]

finally:
    if collection is not None and client is not None and baseline_source is not None:
        for clone in clone_ids:
            try:
                result["cleanup"]["attempted"].append(clone)
                if collection.exists(clone):
                    collection.delete(clone, refresh="wait_for")
                require(not collection.exists(clone), f"Owned clone cleanup left {clone!r} behind.")
                result["cleanup"]["removed"].append(clone)
            except Exception as error:
                result["result"] = "FAIL"
                result["failures"].append(f"clone cleanup {clone}: {type(error).__name__}: {error}")

        try:
            current_raw = raw_get(client, collection.name, spec["hit_id"])
            result["source_restore"]["source_before_restore_sha256"] = __import__("hashlib").sha256(
                canon(current_raw["_source"]).encode("utf-8")
            ).hexdigest()
            if current_raw["_source"] != baseline_source:
                restore_result = response_body(client.index(
                    index=collection.name,
                    id=spec["hit_id"],
                    document=baseline_source,
                    if_seq_no=current_raw["_seq_no"],
                    if_primary_term=current_raw["_primary_term"],
                    refresh="wait_for",
                ))
                require(restore_result.get("result") in {"updated", "created"},
                        "Exact logical fixture source restore did not update the seeded Hit.")
                result["source_restore"]["restore_result"] = restore_result.get("result")
            else:
                result["source_restore"]["restore_result"] = "already_equal"
            restored_raw = raw_get(client, collection.name, spec["hit_id"])
            result["source_restore"]["exact_match"] = restored_raw["_source"] == baseline_source
            result["source_restore"]["source_after_restore_sha256"] = __import__("hashlib").sha256(
                canon(restored_raw["_source"]).encode("utf-8")
            ).hexdigest()
            result["source_restore"]["version_after_restore"] = (
                f"{restored_raw['_seq_no']}---{restored_raw['_primary_term']}"
            )
            require(result["source_restore"]["exact_match"], "Exact original logical fixture source was not restored.")
            result["write_effects"].append({
                "action": "restore_exact_seeded_logical_fixture_source",
                "document_id": spec["hit_id"],
                "serialization_helper": "__index=hit (captured in application-v2 legacy save source)",
                "exact_match": True,
            })
        except Exception as error:
            result["result"] = "FAIL"
            result["failures"].append(f"source restore: {type(error).__name__}: {error}")

    if registered_store is not None:
        try:
            registered_store.ds.close()
        except Exception as error:
            result["result"] = "FAIL"
            result["failures"].append(f"datastore close: {type(error).__name__}: {error}")

    result_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")

if result["result"] != "PASS":
    raise SystemExit(1)
"""


def _sanitized_probe_environment(
    *,
    api_root: Path,
    plan: Any,
    es_endpoint: str,
    redis: Any,
    config_dir: Path,
    plugin_dir: Path,
    log_dir: Path,
) -> dict[str, str]:
    environment = application_rehearsal._minimal_python_environment(
        api_root=api_root,
        api_endpoint=es_endpoint,
        redis_port=redis.port,
        namespace=plan.namespace,
        config_dir=config_dir,
        plugin_dir=plugin_dir,
        log_dir=log_dir,
        redis_host=redis.host,
    )
    environment.update(plan.environment)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "STEP9_ES_ENDPOINT": es_endpoint,
            "HWL_UI__DEBUG": "false",
            "HWL_USE_JOB_SYSTEM": "false",
            "HWL_START_BACKGROUND_SERVICES": "false",
            "HWL_USE_WEBSOCKET_API": "false",
            "HWL_AUTH__OAUTH__ENABLED": "false",
            "HWL_AUTH__INTERNAL__ENABLED": "false",
            "HWL_CORE__PLUGINS": "[]",
            "HWL_CORE__CLUE__ENABLED": "false",
            "HWL_CORE__TELEMETRY__ENABLED": "false",
            "HWL_DATASTORE__ILM__ENABLED": "false",
        }
    )
    return environment


def run_registered_collection_probe(
    runtime: Any,
    *,
    handle: Any,
    plan: Any,
    redis: Any,
    api_root: Path,
    timeout: int,
) -> dict[str, Any]:
    """Run real model-backed CRUD and bulk calls in a private sanitized API subprocess."""
    target = validate_write_probe_target(runtime, handle, plan)
    runtime.verify_owned(handle)
    application_rehearsal.verify_redis_owned(runtime, redis)
    work_dir = runtime.work_dir.resolve(strict=True)
    _require(not work_dir.is_relative_to(api_root.resolve(strict=True)), "Probe workspace may not be inside API root.")
    config_dir = work_dir / "howler-config"
    plugin_dir = config_dir / "plugins"
    log_dir = work_dir / "howler-logs"
    _require(config_dir.is_dir() and plugin_dir.is_dir() and log_dir.is_dir(), "Owned app config/log dirs are missing.")
    _require(
        all(not path.is_symlink() for path in (config_dir, plugin_dir, log_dir)),
        "App config/log paths must be ordinary run-owned directories.",
    )
    index = next(item for item in plan.indexes if item.collection == "hit")
    hit = next(item for item in plan.documents if item.collection == "hit")
    _require(hit.source.get("__index") == "hit", "Write probe expected the legacy Hit helper in the seed source.")
    run_uuid = uuid.uuid4()
    clone_ids = [str(run_uuid), str(uuid.uuid5(run_uuid, "step9-bulk-clone"))]
    validate_owned_clone_ids(clone_ids, {document.document_id for document in plan.documents})
    spec = {
        "run_id": runtime.run_id,
        "namespace": plan.namespace,
        "index_prefix": plan.environment["HWL_DATASTORE_INDEX_PREFIX"],
        "alias": index.alias,
        "index_name": index.index_name,
        "hit_id": hit.document_id,
        "expected_source": copy.deepcopy(hit.source),
        "clone_ids": clone_ids,
    }
    spec_path = work_dir / "write-probe-spec.json"
    result_path = work_dir / "write-probe-result.json"
    stdout_path = work_dir / "write-probe-child.stdout.log"
    stderr_path = work_dir / "write-probe-child.stderr.log"
    for path in (spec_path, result_path, stdout_path, stderr_path):
        _require(not path.exists(), f"Refusing pre-existing write-probe artifact: {path}.")
    spec_path.write_text(json.dumps(spec, sort_keys=True) + "\n", encoding="utf-8")
    spec_path.chmod(0o600)
    endpoint = handle.base_url.removeprefix("http://")
    environment = _sanitized_probe_environment(
        api_root=api_root,
        plan=plan,
        es_endpoint=endpoint,
        redis=redis,
        config_dir=config_dir,
        plugin_dir=plugin_dir,
        log_dir=log_dir,
    )
    environment["STEP9_WRITE_PROBE_SPEC"] = str(spec_path)
    environment["STEP9_WRITE_PROBE_RESULT"] = str(result_path)
    result = subprocess.run(
        [sys.executable, "-c", _WRITE_PROBE_CHILD_SOURCE],
        cwd=api_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    child_result: dict[str, Any] = {}
    if result_path.is_file():
        try:
            child_result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RehearsalAbort("Write-probe child produced corrupt result JSON.") from error
    _require(bool(child_result), "Write-probe child exited without its request-derived result artifact.")
    if child_result.get("result") == "PASS":
        validate_stale_version_observation(child_result.get("stale_version", {}))
        if result.returncode != 0:
            child_result["result"] = "FAIL"
            child_result.setdefault("failures", []).append(
                f"Write-probe child returned exit {result.returncode}: {result.stderr[-1000:]}"
            )
    elif result.returncode == 0:
        child_result["result"] = "FAIL"
        child_result.setdefault("failures", []).append("Write-probe child exited successfully without a passing gate.")
    target["cluster_uuid"] = es_rehearsal._root(
        es_rehearsal.RestClient(handle.base_url, timeout), handle.cluster_name, es_rehearsal.TARGET_VERSION
    )["cluster_uuid"]
    child_result["target"] = target
    child_result["child_exit_code"] = result.returncode
    if result.returncode != 0:
        child_result["child_stderr_tail"] = result.stderr[-1000:]
    child_result["child_stdout_tail"] = result.stdout[-500:]
    return child_result


def _fixture_storage_report(plan: Any, provenance: dict[str, Any]) -> dict[str, Any]:
    documents = [
        {"collection": document.collection, "id": document.document_id, "source": document.source}
        for document in sorted(plan.documents, key=lambda item: (item.collection, item.document_id))
    ]
    canonical = json.dumps(documents, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "fixture_version": plan.fixture_version,
        "frozen_fixture_sha256": application_fixture.APPLICATION_FIXTURE_SHA256,
        "frozen_fixture_mutated": False,
        "effective_seed_documents_sha256": hashlib.sha256(canonical).hexdigest(),
        "effective_seed_document_counts": dict(application_fixture.DOCUMENT_COUNTS),
        "legacy_helper_contract": provenance,
        "pre_snapshot_source_mutation": {
            "result": "NONE",
            "reason": "Hit/Case __index values were captured from origin/main ESCollection.save into application-v2.",
        },
    }


def validate_cleanup_container(
    response: dict[str, Any],
    *,
    run_id: str,
    name: str,
    role: str,
    image: str,
    expected_id: str | None = None,
) -> str:
    """Fail closed before cleanup unless an exact container is labelled for this run."""
    container_id = response.get("Id")
    labels = response.get("Config", {}).get("Labels", {})
    _require(
        isinstance(container_id, str) and bool(container_id) and (expected_id is None or container_id == expected_id),
        f"Refusing cleanup for {name!r}: container ID differs from this run's recorded identity.",
    )
    _require(
        response.get("Name", "").lstrip("/") == name
        and labels.get(es_rehearsal.LABEL_KEY) == "true"
        and labels.get("howler.step9.run") == run_id
        and labels.get("howler.step9.role") == role
        and response.get("Config", {}).get("Image") == image,
        f"Refusing cleanup for {name!r}: run ownership, role, or image labels do not match.",
    )
    return str(container_id)


def validate_cleanup_resource(response: dict[str, Any], *, run_id: str, name: str, role: str, kind: str) -> None:
    """Check the exact Docker name and run/role labels before removing a volume/network."""
    labels = response.get("Labels", {})
    _require(
        response.get("Name") == name
        and labels.get(es_rehearsal.LABEL_KEY) == "true"
        and labels.get("howler.step9.run") == run_id
        and labels.get("howler.step9.role") == role,
        f"Refusing cleanup for {kind} {name!r}: ownership labels do not match this run.",
    )


def _docker_objects(runtime: Any, arguments: list[str], *, description: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(runtime._docker(arguments))
    except (RehearsalAbort, json.JSONDecodeError) as error:
        raise RehearsalAbort(f"Could not inspect owned {description}: {error}.") from error
    _require(isinstance(value, list), f"Docker inspect returned an invalid {description} inventory.")
    return value


def cleanup_owned_resources(runtime: Any) -> dict[str, Any]:
    """Remove only the exact Docker resources labelled for this rehearsal run."""
    run_id = runtime.run_id
    removed: list[dict[str, str]] = []
    try:
        # Reuse the rehearsal's strict container/network/volume identity checks for live ES
        # handles; a failed ownership check intentionally prevents destructive cleanup.
        for handle in list(runtime.handles.values()):
            runtime.stop_and_remove_container(handle)
            removed.append({"kind": "container", "name": handle.name, "role": handle.role})

        existing_containers = set(runtime._docker(["ps", "-a", "--format", "{{.Names}}"], check=True).splitlines())
        redis_name = f"howler-step9-{run_id}-app-redis"
        redis_network_name = f"howler-step9-{run_id}-app-redis-network"
        expected_containers = {
            redis_name: ("application-redis", application_rehearsal.REDIS_IMAGE),
        }
        for name, (role, image) in expected_containers.items():
            if name not in existing_containers:
                continue
            response = _docker_objects(runtime, ["inspect", name], description=f"container {name}")[0]
            container_id = validate_cleanup_container(response, run_id=run_id, name=name, role=role, image=image)
            handle_config = response.get("HostConfig", {})
            mounts = response.get("Mounts", [])
            _require(
                handle_config.get("NetworkMode") == redis_network_name
                and set(handle_config.get("Tmpfs") or {}) == {"/data"}
                and not mounts
                and not handle_config.get("Binds"),
                "Refusing application Redis cleanup: its run-owned ephemeral topology changed.",
            )
            application_rehearsal._inspect_owned_redis_network(
                runtime, redis_network_name, expected_members={container_id}
            )
            bindings = handle_config.get("PortBindings") or {}
            _require(
                not any(bindings.values()) and not handle_config.get("PublishAllPorts"),
                "Refusing application Redis cleanup: its port must remain unpublished on the host.",
            )
            published = response.get("NetworkSettings", {}).get("Ports") or {}
            _require(not any(published.values()), "Refusing Redis cleanup while a host-published port exists.")
            if response.get("State", {}).get("Status") == "running":
                runtime._docker(["stop", "--time", "10", container_id])
                response = _docker_objects(runtime, ["inspect", container_id], description=f"container {name}")[0]
                validate_cleanup_container(
                    response,
                    run_id=run_id,
                    name=name,
                    role=role,
                    image=image,
                    expected_id=container_id,
                )
                _require(response.get("State", {}).get("Status") == "exited", "Owned Redis did not stop cleanly.")
            runtime._docker(["rm", container_id])
            removed.append({"kind": "container", "name": name, "role": role})

        remaining = set(runtime._docker(["ps", "-a", "--format", "{{.Names}}"], check=True).splitlines())
        expected_es_names = {f"howler-step9-{run_id}-{role}" for role in ("donor", "cutover", "rollback")}
        remaining_owned = remaining & (expected_es_names | set(expected_containers))
        _require(
            not remaining_owned,
            f"Owned rehearsal containers remain after cleanup: {sorted(remaining_owned)}.",
        )

        existing_networks = set(runtime._docker(["network", "ls", "--format", "{{.Name}}"], check=True).splitlines())
        expected_networks = {
            runtime.network: "network",
            redis_network_name: "application-redis-network",
        }
        for name, role in expected_networks.items():
            if name not in existing_networks:
                continue
            network = _docker_objects(runtime, ["network", "inspect", name], description=f"network {name}")[0]
            validate_cleanup_resource(network, run_id=run_id, name=name, role=role, kind="network")
            _require(
                network.get("Driver") == "bridge"
                and network.get("Internal") is True
                and not (network.get("Containers") or {}),
                f"Refusing rehearsal network cleanup: {name!r} is not an empty, internal owned bridge.",
            )
            runtime._docker(["network", "rm", name])
            removed.append({"kind": "network", "name": name, "role": role})

        existing_volumes = set(runtime._docker(["volume", "ls", "--format", "{{.Name}}"], check=True).splitlines())
        for role, name in runtime.volumes.items():
            if name not in existing_volumes:
                continue
            volume = _docker_objects(runtime, ["volume", "inspect", name], description=f"volume {name}")[0]
            validate_cleanup_resource(volume, run_id=run_id, name=name, role=role, kind="volume")
            _require(volume.get("Driver") == "local", f"Refusing non-local rehearsal volume cleanup: {name!r}.")
            attached = runtime._docker(["ps", "-a", "--filter", f"volume={name}", "--format", "{{.Names}}"])
            _require(
                not attached, f"Refusing rehearsal volume cleanup while containers reference {name!r}: {attached}."
            )
            runtime._docker(["volume", "rm", name])
            removed.append({"kind": "volume", "name": name, "role": role})
    except Exception as error:
        return {
            "result": "FAIL",
            "removed": removed,
            "error": f"{type(error).__name__}: {error}",
        }
    return {"result": "PASS", "removed": removed}


def run_write_rehearsal(args: argparse.Namespace) -> dict[str, Any]:  # noqa: C901
    """Run the full reviewed 8.19 -> snapshot restore -> same-volume 9.5 + write proof."""
    run_id = args.run_id or uuid.uuid4().hex[:12]
    _require(_RUN_ID_PATTERN.fullmatch(run_id) is not None, "--run-id must be lowercase-safe and 1-36 characters.")
    namespace = derive_namespace(run_id)
    api_root = Path(args.api_root or API_ROOT).expanduser().resolve(strict=True)
    provenance = validate_legacy_helper_provenance(api_root)
    _require(args.timeout > 0, "Timeout must be positive.")

    original_builder = application_rehearsal.build_seed_plan
    original_checks = application_rehearsal.run_application_checks
    original_runtime_class = es_rehearsal.DockerRuntime
    plan_holder: dict[str, Any] = {}
    write_report: dict[str, Any] = {"result": "NOT_RUN", "failures": ["application write hook did not run"]}

    class CapturingDockerRuntime(original_runtime_class):
        def __init__(self, *runtime_args: Any, **runtime_kwargs: Any):
            super().__init__(*runtime_args, **runtime_kwargs)
            _RUNTIME_INSTANCES.append(self)

    def build_actual_legacy_plan(requested_namespace: str) -> Any:
        _require(requested_namespace == namespace, "Reviewed rehearsal requested an unexpected namespace.")
        plan = original_builder(requested_namespace)
        application_rehearsal.validate_seed_plan(plan, requested_namespace)
        captured_plan = validate_legacy_storage_plan(plan)
        application_rehearsal.validate_seed_plan(captured_plan, requested_namespace)
        plan_holder["plan"] = captured_plan
        return captured_plan

    def checks_with_registered_writes(
        app: Any,
        *,
        plan: Any,
        fixture: dict[str, Any],
        redis_runtime: Any,
        redis: Any,
        before_application_state: dict[str, Any] | None = None,
    ):
        nonlocal write_report
        results: dict[str, Any]
        target: Any = None
        try:
            results = original_checks(
                app,
                plan=plan,
                fixture=fixture,
                redis_runtime=redis_runtime,
                redis=redis,
                before_application_state=before_application_state,
            )
        except Exception as error:
            results = {"identity_checks": {}, "acl_queries": {}, "denials": {}, "resource_reads": {}, "failures": []}
            results["failures"].append(f"read-only application checks: {type(error).__name__}: {error}")

        if results.get("read_only_state", {}).get("result") != "PASS":
            write_report = {
                "result": "BLOCKED_PREREQUISITE",
                "failures": ["Write probe was not started because read-only application checks changed ES state."],
            }
            results["write_probe"] = write_report
            results.setdefault("failures", []).append("read-only application state gate did not pass")
            results["result"] = "FAIL"
            return results

        before: dict[str, Any] | None = None
        after: dict[str, Any] | None = None
        try:
            _require(plan is plan_holder.get("plan"), "Write hook plan differs from the snapshot seed plan.")
            handle = redis_runtime.handles.get("cutover")
            _require(handle is not None, "No live cutover container remains for the write probe.")
            target = validate_write_probe_target(redis_runtime, handle, plan)
            client = es_rehearsal.RestClient(handle.base_url, redis_runtime.timeout)
            expected_names = [index.index_name for index in plan.indexes]
            before = application_rehearsal.capture_application_state(
                client, expected_names, es_rehearsal.MAX_DOCS_PER_INDEX
            )
            _require(
                not any("__reindex" in name for name in before["inventory"]),
                "Pre-write inventory contains a __reindex temporary index.",
            )
            child = run_registered_collection_probe(
                redis_runtime,
                handle=handle,
                plan=plan,
                redis=redis,
                api_root=api_root,
                timeout=redis_runtime.timeout,
            )
            after = application_rehearsal.capture_application_state(
                client, expected_names, es_rehearsal.MAX_DOCS_PER_INDEX
            )
            hit_index = next(index for index in plan.indexes if index.collection == "hit")
            probe_label_key = f"step9-write-probe-{redis_runtime.run_id}"
            state = validate_write_state(
                before,
                after,
                expected_names,
                expected_dynamic_fields={hit_index.index_name: probe_label_key},
            )
            target["cluster_uuid"] = es_rehearsal._root(client, handle.cluster_name, es_rehearsal.TARGET_VERSION)[
                "cluster_uuid"
            ]
            write_report = {
                **child,
                "result": "PASS" if child.get("result") == "PASS" else "FAIL",
                "target": target,
                "state_after_restore": state,
                "write_effects_are_request_derived": True,
            }
            if child.get("result") != "PASS":
                write_report.setdefault("failures", []).append("Registered collection child write gate failed.")
        except Exception as error:
            write_report = {
                "result": "FAIL",
                "failures": [f"{type(error).__name__}: {error}"],
                "target": target,
            }
            if before is not None:
                write_report["application_state_before"] = before.get("application_state")
            if before is not None and after is not None:
                write_report["state_delta"] = write_state_delta(before, after)
            if before is not None and after is None:
                try:
                    expected_names = [index.index_name for index in plan.indexes]
                    after = application_rehearsal.capture_application_state(
                        es_rehearsal.RestClient(redis_runtime.handles["cutover"].base_url, redis_runtime.timeout),
                        expected_names,
                        es_rehearsal.MAX_DOCS_PER_INDEX,
                    )
                    write_report["state_delta"] = write_state_delta(before, after)
                    write_report["state_after_restore_attempt"] = validate_write_state(before, after, expected_names)
                except Exception as capture_error:
                    write_report["state_after_restore_error"] = f"{type(capture_error).__name__}: {capture_error}"

        results["write_probe"] = write_report
        if write_report.get("result") != "PASS":
            results.setdefault("failures", []).append("registered collection write probe did not pass")
        results["result"] = "PASS" if not results.get("failures") else "FAIL"
        return results

    application_rehearsal.build_seed_plan = build_actual_legacy_plan
    application_rehearsal.run_application_checks = checks_with_registered_writes
    es_rehearsal.DockerRuntime = CapturingDockerRuntime
    try:
        report = application_rehearsal.run_rehearsal(
            argparse.Namespace(
                run_id=run_id,
                work_dir=str(Path(args.work_dir).expanduser()),
                api_root=str(api_root),
                timeout=args.timeout,
            )
        )
    finally:
        application_rehearsal.build_seed_plan = original_builder
        application_rehearsal.run_application_checks = original_checks
        es_rehearsal.DockerRuntime = original_runtime_class

    report["fixture_storage_capture"] = (
        _fixture_storage_report(plan_holder["plan"], provenance)
        if "plan" in plan_holder
        else {
            "result": "NOT_RUN",
            "legacy_helper_contract": provenance,
        }
    )
    if write_report.get("result") == "NOT_RUN" and report.get("workflow_result") != "PASS":
        prerequisite = report.get("fatal_error", "a required application rehearsal gate did not pass")
        write_report = {
            "result": "BLOCKED_PREREQUISITE",
            "failures": [f"Write probe was not started because its prerequisite gate failed: {prerequisite}"],
        }
    report["write_probe"] = write_report
    report["write_probe"]["independent_rollback"] = report.get("rollback_8_19")
    report["write_probe"]["rollback_attempted"] = report.get("rollback_attempted", False)
    report["write_probe"]["rollback_gate"] = report.get("gates", {}).get("rollback", "NOT_RUN")
    report["write_probe"]["full_rehearsal_result"] = report.get("workflow_result", "BLOCKED")
    report_path = Path(args.work_dir).expanduser().resolve() / "application-rehearsal-report.json"
    es_rehearsal._write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-root", default=str(API_ROOT), help="Howler API source root (default: this worktree).")
    parser.add_argument("--work-dir", help="New, non-existing owned workspace for snapshots and evidence.")
    parser.add_argument("--run-id", help="Unique 1-36 character lowercase-safe suffix; generated by default.")
    parser.add_argument(
        "--report",
        default="/tmp/opencode/step9-wrap/writes-report.json",
        help="External JSON report path, written before owned Docker-resource cleanup.",
    )
    parser.add_argument("--timeout", type=int, default=900, help="Cluster, child, and rollback timeout in seconds.")
    args = parser.parse_args()
    if not args.run_id:
        args.run_id = uuid.uuid4().hex[:12]
    if not args.work_dir:
        args.work_dir = str(Path("/tmp/opencode/step9-wrap") / f"writes-run-{args.run_id}")

    report_destination = Path(args.report).expanduser()
    if report_destination.is_symlink() or report_destination.exists():
        print(f"ABORT: Refusing to overwrite report: {report_destination}.", file=sys.stderr)
        return 2
    report_path = report_destination.resolve()
    command = "poetry run python " + " ".join(shlex.quote(arg) for arg in sys.argv)
    _RUNTIME_INSTANCES.clear()
    exit_code = 2
    try:
        _require(report_path.parent.is_dir(), f"Report directory does not exist: {report_path.parent}.")
        report: dict[str, Any] = run_write_rehearsal(args)
        write_result = report.get("write_probe", {}).get("result")
        exit_code = 0 if report.get("workflow_result") == "PASS" and write_result == "PASS" else 3
    except Exception as error:
        report = {
            "run_id": args.run_id,
            "workflow_result": "FAIL",
            "fatal_error": f"{type(error).__name__}: {error}",
            "gates": {},
            "write_probe": {"result": "FAIL", "failures": [f"{type(error).__name__}: {error}"]},
        }
        work_report = Path(args.work_dir).expanduser() / "application-rehearsal-report.json"
        if work_report.is_file():
            try:
                report["application_rehearsal_report"] = json.loads(work_report.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as report_error:
                report["partial_report_error"] = f"{type(report_error).__name__}: {report_error}"
        if _RUNTIME_INSTANCES:
            report["resources"] = _RUNTIME_INSTANCES[-1].resources

    report["execution"] = {
        "command": command,
        "working_directory": str(Path.cwd()),
        "report_path": str(report_path),
        "exit_code": exit_code,
    }
    report["docker_cleanup"] = {"result": "PENDING", "removed": []}
    # Persist evidence before touching any Docker resource. The final report is rewritten
    # after cleanup so cleanup failures cannot be hidden behind a previous PASS.
    es_rehearsal._write_json(report_path, report)

    cleanup_results = [cleanup_owned_resources(runtime) for runtime in reversed(_RUNTIME_INSTANCES)]
    cleanup_errors = [item for item in cleanup_results if item.get("result") != "PASS"]
    report["docker_cleanup"] = {
        "result": "FAIL" if cleanup_errors else "PASS",
        "runs": cleanup_results,
        "removed": [entry for item in cleanup_results for entry in item.get("removed", [])],
    }
    if cleanup_errors:
        report["workflow_result"] = "FAIL_RESOURCE_CLEANUP"
        report["write_probe"]["result"] = "FAIL"
        report["write_probe"].setdefault("failures", []).append("Owned Docker resource cleanup did not complete.")
        exit_code = 3 if exit_code != 2 else 2
    report["execution"]["exit_code"] = exit_code
    es_rehearsal._write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
