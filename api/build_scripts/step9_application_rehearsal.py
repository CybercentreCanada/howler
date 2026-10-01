"""Run an isolated Elasticsearch upgrade with the frozen Howler application corpus.

This is a live synthetic rehearsal, not a status-file consumer. It creates a fresh,
run-owned 8.19.11 donor, seeds the reviewed application-v1 plan before snapshotting,
restores into a second fresh 8.19.11 volume, upgrades that same volume to 9.5.2, and
restores the saved snapshot into a third fresh 8.19.11 volume. The only application
checks are real HTTP requests to a short-lived local WSGI child using the API keys
embedded in the frozen fixture.

All Elasticsearch access uses the reviewed raw-urllib mechanics in
``upgrade_rehearsal.py``. No Howler client or application imports occur in this
process; the WSGI child receives an explicit, sanitized environment before imports.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

BUILD_SCRIPTS = Path(__file__).resolve().parent
API_ROOT = BUILD_SCRIPTS.parent
REPO_ROOT = API_ROOT.parent
if str(BUILD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BUILD_SCRIPTS))

# In the isolated worker worktree the reviewed ES mechanics are intentionally not copied
# into an owned path. Resolve the read-only root implementation until the orchestrator
# integrates both files into the same build_scripts directory.
_runtime_candidates = [parent / "api" / "build_scripts" for parent in (REPO_ROOT, *REPO_ROOT.parents)]
REHEARSAL_RUNTIME_DIR = next(
    (candidate for candidate in _runtime_candidates if (candidate / "upgrade_rehearsal.py").is_file()),
    BUILD_SCRIPTS,
)
if str(REHEARSAL_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(REHEARSAL_RUNTIME_DIR))


def _api_root_argument() -> Path | None:
    """Resolve a CLI ``--api-root`` early so the fixture contract comes from that tree."""
    for index, argument in enumerate(sys.argv):
        if argument.startswith("--api-root="):
            return Path(argument.partition("=")[2]).expanduser().resolve()
        if argument == "--api-root" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).expanduser().resolve()
    return None


_requested_api_root = _api_root_argument()
if _requested_api_root is not None:
    _requested_build_scripts = _requested_api_root / "build_scripts"
    if (_requested_build_scripts / "step9_application.py").is_file():
        sys.path.insert(0, str(_requested_build_scripts))

if TYPE_CHECKING:
    from build_scripts import step9_application as application_fixture  # noqa: E402
    from build_scripts import upgrade_rehearsal as es_rehearsal  # noqa: E402
    from build_scripts.step9_application import (  # noqa: E402
        ACCESS_FIELDS,
        COLLECTION_NAMES,
        DOCUMENT_COUNTS,
        FixtureContractError,
        SeedPlan,
        application_environment,
        build_seed_plan,
    )
else:
    import step9_application as application_fixture  # noqa: E402
    import upgrade_rehearsal as es_rehearsal  # noqa: E402
    from step9_application import (  # noqa: E402
        ACCESS_FIELDS,
        COLLECTION_NAMES,
        DOCUMENT_COUNTS,
        FixtureContractError,
        SeedPlan,
        application_environment,
        build_seed_plan,
    )


def _get_application_module_path() -> Path:
    module_file = application_fixture.__file__
    if module_file is None:
        raise ImportError("The application-v1 fixture module has no source file.")
    return Path(module_file).resolve()


if _requested_api_root is not None:
    _application_module_path = _get_application_module_path()
    _requested_build_scripts = (_requested_api_root / "build_scripts").resolve()
    if not _application_module_path.is_relative_to(_requested_build_scripts):
        raise ImportError(
            f"The application-v1 plan was imported from {_application_module_path}, not the requested API root "
            f"{_requested_api_root}. Set --api-root before importing this runner."
        )

RehearsalAbort = es_rehearsal.RehearsalAbort

REDIS_IMAGE = "redis:7.4.2-alpine"
REDIS_PORT = 6379
RUN_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,35}\Z")
ES_SYSTEM_STREAM_INDEX_PATTERNS = {
    ".logs-elasticsearch.deprecation-default": re.compile(
        r"\.ds-\.logs-elasticsearch\.deprecation-default-\d{4}\.\d{2}\.\d{2}-\d{6}\Z"
    ),
    "ilm-history-7": re.compile(r"\.ds-ilm-history-7-\d{4}\.\d{2}\.\d{2}-\d{6}\Z"),
}
HIT_IDS = tuple(f"00000000-0000-4000-8000-{number:012d}" for number in range(1, 9))
CASE_ID = "10000000-0000-4000-8000-000000000001"
READER_IDS = {
    "step9-reader": [HIT_IDS[0]],
    "step9-restricted-reader": [HIT_IDS[0], HIT_IDS[2], HIT_IDS[5]],
}
READER_COUNTS = {username: len(ids) for username, ids in READER_IDS.items()}
READER_FACETS = {
    "step9-reader": {"open": 1},
    "step9-restricted-reader": {"in-progress": 2, "open": 1},
}


@dataclass(frozen=True)
class RedisHandle:
    """Identity of the dedicated local Redis container used by the WSGI child."""

    name: str
    container_id: str
    host: str
    port: int


@dataclass(frozen=True)
class AppHandle:
    """Running application child and its local ephemeral HTTP endpoint."""

    process: subprocess.Popen[bytes]
    base_url: str
    ready_file: Path


def _require(condition: bool, message: str) -> None:
    es_rehearsal._require(condition, message)


def derive_namespace(run_id: str) -> str:
    """Validate one run token and derive its isolated namespaced Howler prefix."""
    _require(isinstance(run_id, str) and RUN_ID_PATTERN.fullmatch(run_id) is not None, "Invalid Step 9 run ID.")
    namespace = f"step9-app-{run_id}"
    # Let the fixture contract be the authority on namespace syntax and reserved names.
    application_environment(namespace)
    return namespace


def validate_seed_plan(plan: SeedPlan, namespace: str) -> list[str]:
    """Fail closed unless the pure fixture plan is complete and strictly namespaced."""
    _require(plan.namespace == namespace, "Seed plan namespace differs from the requested rehearsal namespace.")
    _require(plan.fixture_version == "application-v1", "Unsupported application seed-plan version.")
    _require(plan.compatibility_validation_required is True, "The fixture no longer requires compatibility validation.")
    _require(
        plan.application_verification_status == "NOT_RUN", "A prefilled application status cannot authorize a run."
    )
    _require(
        plan.environment == application_environment(namespace),
        "Seed-plan process environment differs from the required namespaced, ILM-disabled environment.",
    )
    _require(
        plan.environment.get("HWL_DATASTORE_INDEX_PREFIX") == f"{namespace}-howler",
        "Seed-plan datastore prefix is not exactly <namespace>-howler.",
    )
    _require(plan.environment.get("HWL_DATASTORE__ILM__ENABLED") == "false", "Seed plan must disable ILM.")
    _require(plan.environment.get("HWL_AUTH__INTERNAL__ENABLED") == "false", "Seed plan must disable internal auth.")

    by_collection = {index.collection: index for index in plan.indexes}
    _require(
        len(plan.indexes) == len(COLLECTION_NAMES) and set(by_collection) == set(COLLECTION_NAMES),
        "Seed plan must contain exactly the 11 frozen base collections.",
    )
    expected_indices: list[str] = []
    for collection in COLLECTION_NAMES:
        index = by_collection[collection]
        expected_alias = f"{namespace}-howler-{collection}"
        expected_index = f"{expected_alias}_hot"
        _require(index.alias == expected_alias, f"{collection} alias escapes the per-run namespace.")
        _require(index.index_name == expected_index, f"{collection} physical index is not the legacy _hot name.")
        _require(
            not index.alias.startswith("howler-") and not index.index_name.startswith("howler-"),
            "Default Howler names are forbidden.",
        )
        _require(index.mappings.get("properties") is not None, f"{collection} has no frozen base mapping.")
        _require(
            index.historical_ilm_template is None or isinstance(index.historical_ilm_template, dict),
            "Invalid historical ILM comparison metadata.",
        )
        _require(
            index.create_body().get("aliases") == {expected_alias: {}}, f"{collection} must have one namespaced alias."
        )
        _require(
            "lifecycle.name" not in json.dumps(index.settings, sort_keys=True)
            and "lifecycle.rollover_alias" not in json.dumps(index.settings, sort_keys=True),
            f"{collection} base index settings must not enable ILM.",
        )
        expected_indices.append(expected_index)

    counts = Counter(document.collection for document in plan.documents)
    _require(dict(counts) == DOCUMENT_COUNTS, f"Seed plan document counts changed: {dict(counts)!r}.")
    for document in plan.documents:
        _require(document.collection in by_collection, "Seed document targets an unknown collection.")
        index = by_collection[document.collection]
        _require(document.index_alias == index.alias, "Seed document target differs from its collection alias.")
        _require(document.source.get("id") == document.document_id, "Seed source id must equal the Elasticsearch _id.")
        _require(
            set(ACCESS_FIELDS).issubset(document.source),
            f"Seed document {document.document_id!r} is missing one or more access-control fields.",
        )

    _require(
        set(plan.query_contracts.get("requests", {}))
        == {"default_id_search", "exact_hit_lookup", "status_aggregation", "relevance"},
        "Fixture raw request inventory changed.",
    )
    for request in plan.query_contracts["requests"].values():
        _require(
            request.get("index") == f"{namespace}-howler-hit",
            "Fixture raw query targets an alias outside the run namespace.",
        )
        _require(isinstance(request.get("body"), dict), "Fixture raw query body must be an object.")
    return expected_indices


def validate_fresh_empty_cluster(
    info: dict[str, Any],
    health: dict[str, Any],
    inventory: dict[str, Any],
    *,
    expected_name: str,
) -> None:
    """Gate first fixture writes on exact ES identity, health, and an empty inventory."""
    es_rehearsal.validate_cluster_info(info, expected_name, es_rehearsal.SOURCE_VERSION)
    _require(health.get("status") in {"green", "yellow"}, f"Fresh 8.19 cluster is unhealthy: {health!r}.")
    _require(not inventory, f"Fresh 8.19.11 volume is not empty before fixture writes: {sorted(inventory)}.")


def verify_mapping_parity(
    plan: SeedPlan,
    *,
    api_root: Path,
    fixture_module_dir: Path,
    config_dir: Path,
) -> dict[str, Any]:
    """Compare all frozen mappings/settings with the current base Pydantic/DSL contracts.

    This gate runs in a clean subprocess before any Elasticsearch data write. Plugins and
    Clue are disabled there, matching the actual application child.
    """
    result_path = config_dir / "mapping-parity.json"
    child_source = """\
import json
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from step9_application import build_seed_plan
from howler.datastore.howler_store import INDEXES
from howler.models import model_extensions
from howler.models.schema import document_mapping, index_settings
plan = build_seed_plan(sys.argv[2])
model_extensions.clear()
mismatches = []
for item in plan.indexes:
    model = INDEXES[item.collection]
    finalized = model_extensions.finalize(model) if model is not None else None
    expected_settings = item.settings
    index_settings_body = index_settings(
        finalized,
        shards=expected_settings["index"]["number_of_shards"],
        replicas=expected_settings["index"]["number_of_replicas"],
    )
    actual_mapping = document_mapping(finalized)
    if index_settings_body != expected_settings:
        mismatches.append({"collection": item.collection, "kind": "settings"})
    if actual_mapping != item.mappings:
        mismatches.append({"collection": item.collection, "kind": "mappings"})
result = {"checked_collections": len(plan.indexes), "mismatches": mismatches}
Path(sys.argv[3]).write_text(json.dumps(result, sort_keys=True) + "\\n", encoding="utf-8")
if mismatches:
    raise SystemExit(17)
"""
    env = _minimal_python_environment(
        api_root=api_root,
        api_endpoint="127.0.0.1:1",
        redis_port=1,
        namespace=plan.namespace,
        config_dir=config_dir,
        plugin_dir=config_dir / "plugins",
        log_dir=config_dir / "logs",
    )
    result = subprocess.run(
        [sys.executable, "-c", child_source, str(fixture_module_dir), plan.namespace, str(result_path)],
        cwd=api_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    require_subprocess_success(result.returncode, "current mapping parity", result.stderr or result.stdout)
    try:
        details = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RehearsalAbort("Mapping parity subprocess returned success without a valid result artifact.") from error
    _require(
        details.get("checked_collections") == len(COLLECTION_NAMES), "Mapping parity skipped one or more collections."
    )
    _require(not details.get("mismatches"), f"Current schema mappings differ from application-v1: {details!r}.")
    result_path.unlink(missing_ok=True)
    return {
        "result": "PASS",
        "checked_collections": details["checked_collections"],
        "comparison": "exact settings and mappings; no normalization",
    }


def require_subprocess_success(returncode: int, description: str, output: str = "") -> None:
    """Never let a failed child-process prerequisite be converted into a passing gate."""
    _require(returncode == 0, f"{description} subprocess failed with exit code {returncode}: {output[-1600:]}")


def seed_application_plan(client: Any, plan: SeedPlan) -> None:
    """Write the entire frozen plan to one already-gated fresh donor cluster."""
    for index in plan.indexes:
        client.request("PUT", f"/{urllib.parse.quote(index.index_name, safe='')}", index.create_body())
    for document in plan.documents:
        client.request(
            "PUT",
            f"/{urllib.parse.quote(document.index_alias, safe='')}/_doc/"
            f"{urllib.parse.quote(document.document_id, safe='')}?refresh=wait_for",
            document.source,
        )


def verify_seeded_documents(client: Any, plan: SeedPlan) -> None:
    """Read every seeded source back verbatim; also reject count/source substitutions."""
    for document in plan.documents:
        index = next(item for item in plan.indexes if item.collection == document.collection)
        actual = client.request(
            "GET",
            f"/{urllib.parse.quote(index.index_name, safe='')}/_doc/"
            f"{urllib.parse.quote(document.document_id, safe='')}",
        )
        _require(
            actual.get("found") is True and actual.get("_source") == document.source,
            f"Application-v1 source identity differs for {document.collection}/{document.document_id}.",
        )
    for index in plan.indexes:
        expected = sum(document.collection == index.collection for document in plan.documents)
        actual_count = client.request(
            "POST",
            f"/{urllib.parse.quote(index.index_name, safe='')}/_count",
            {"query": {"match_all": {}}},
        ).get("count")
        _require(
            actual_count == expected, f"{index.index_name} count differs: expected {expected}, got {actual_count!r}."
        )


def capture_plan_queries(client: Any, plan: SeedPlan) -> dict[str, Any]:
    """Execute and retain each fixture raw request and complete raw ES response."""
    captures: dict[str, Any] = {}
    for name, request in plan.query_contracts["requests"].items():
        index = request["index"]
        path = f"/{urllib.parse.quote(index, safe='')}/_search"
        body = copy.deepcopy(request["body"])
        response = client.request("POST", path, body)
        _require(
            isinstance(response, dict) and isinstance(response.get("hits"), dict),
            f"Raw query {name!r} returned no hits object.",
        )
        captures[name] = {
            "request": {"method": "POST", "path": path, "index_alias": index, "body": body},
            "response": response,
        }
    return captures


def capture_application_state(client: Any, names: list[str], max_docs: int) -> dict[str, Any]:
    """Capture exact app state plus all approved ES-owned system data-stream state.

    Elasticsearch 9 may materialize its deprecation-log and ILM-history backing
    indices during the binary upgrade. They are not Howler indices and are never
    seeded by this runner. Their exact names and data-stream ownership are verified
    and the reviewed data capture helper hashes them alongside the fixture before/
    after application requests.
    """
    inventory = es_rehearsal._index_inventory(client)
    _require(set(names).issubset(inventory), "Application index inventory is missing one or more frozen indices.")
    system_indices = sorted(set(inventory) - set(names))
    classified: dict[str, set[str]] = {stream: set() for stream in ES_SYSTEM_STREAM_INDEX_PATTERNS}
    for index_name in system_indices:
        stream_name = next(
            (stream for stream, pattern in ES_SYSTEM_STREAM_INDEX_PATTERNS.items() if pattern.fullmatch(index_name)),
            None,
        )
        if stream_name is None:
            raise RehearsalAbort(f"Unexpected non-application indices in the isolated cluster: {index_name!r}.")
        classified[stream_name].add(index_name)
    for stream_name, expected_backing_indices in classified.items():
        if not expected_backing_indices:
            continue
        streams = client.request("GET", f"/_data_stream/{urllib.parse.quote(stream_name, safe='')}")
        matching_streams = [item for item in streams.get("data_streams", []) if item.get("name") == stream_name]
        backing_indices = {
            item.get("index_name")
            for stream in matching_streams
            for item in stream.get("indices", [])
            if isinstance(item, dict)
        }
        _require(
            len(matching_streams) == 1 and backing_indices == expected_backing_indices,
            f"{stream_name} backing indices do not match the exact ES-owned data stream.",
        )
    names_with_system = sorted([*names, *system_indices])
    complete_state = es_rehearsal.capture_data_state(client, names_with_system, max_docs)
    app_state = {
        key: {name: value for name, value in complete_state[key].items() if name in names}
        for key in ("aliases", "counts", "document_sha256", "index_uuids", "mappings")
    }
    return {
        "application_state": app_state,
        "complete_state": complete_state,
        "inventory": names_with_system,
        "es_internal_indices": system_indices,
    }


def internal_system_state_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Report known ES-owned data-stream changes separately from protected Howler indices."""
    before_names = set(before["es_internal_indices"])
    after_names = set(after["es_internal_indices"])
    shared_names = before_names & after_names
    before_state = before["complete_state"]
    after_state = after["complete_state"]
    state_keys = ("aliases", "counts", "document_sha256", "index_uuids", "mappings")
    changed: dict[str, list[str]] = {}
    for key in state_keys:
        changed[key] = sorted(
            name for name in shared_names if before_state[key].get(name) != after_state[key].get(name)
        )
    return {
        "added_indices": sorted(after_names - before_names),
        "removed_indices": sorted(before_names - after_names),
        "changed_existing_indices": changed,
    }


def assert_raw_query_equivalent(baseline: dict[str, Any], target: dict[str, Any], *, query_name: str) -> None:
    """Compare complete ordered hit/score and aggregation values with no normalization."""
    _require(
        baseline.get("request") == target.get("request"), f"{query_name}: raw request changed between ES versions."
    )
    baseline_response = baseline.get("response", {})
    target_response = target.get("response", {})
    _require(
        baseline_response.get("hits") == target_response.get("hits"),
        f"{query_name}: ordered ES hits, total, max score, source, or per-hit score drifted.",
    )
    _require(
        baseline_response.get("aggregations") == target_response.get("aggregations"),
        f"{query_name}: raw aggregation response drifted.",
    )


def compare_plan_queries(baseline: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Strictly compare every request named by the immutable fixture contract."""
    _require(set(baseline) == set(target), "ES 8 and ES 9 raw query capture inventories differ.")
    results: dict[str, Any] = {}
    for name in baseline:
        try:
            assert_raw_query_equivalent(baseline[name], target[name], query_name=name)
        except RehearsalAbort as error:
            results[name] = {"result": "FAIL", "reason": str(error)}
        else:
            results[name] = {"result": "PASS"}
    return results


def assert_acl_expectations(username: str, actual: dict[str, Any]) -> None:
    """Check user-visible search, count, and facet values against the frozen ACL contract."""
    _require(username in READER_IDS, f"Unexpected test identity {username!r}.")
    expected = {
        "ids": READER_IDS[username],
        "count": READER_COUNTS[username],
        "facets": READER_FACETS[username],
    }
    observed = {key: actual.get(key) for key in expected}
    _require(observed == expected, f"{username} ACL/query response differs: expected {expected!r}, got {observed!r}.")


def assert_resource_etag_contract(resource: str, etag: str | None) -> None:
    """Require the established Hit ETag while preserving the existing Case GET contract."""
    if resource == "hit":
        _require(bool(etag), "restricted-reader GET Hit did not return the required ETag")
        return
    if resource == "case":
        # The current v2 Case GET returns a singleResponse and has never been an ETag route.
        # Do not add a new response-header requirement as part of the Step 9 cutover check.
        return
    raise RehearsalAbort(f"Unknown ETag contract resource {resource!r}.")


def fixture_acl_allows(principal: dict[str, Any], target: dict[str, Any]) -> bool:
    """Evaluate fixture stored access helpers without calling Howler's runtime ACL helper."""
    principal_level = principal.get("__access_lvl__")
    target_level = target.get("__access_lvl__")
    if not (
        isinstance(principal_level, int)
        and not isinstance(principal_level, bool)
        and isinstance(target_level, int)
        and not isinstance(target_level, bool)
    ):
        raise RehearsalAbort("Fixture ACL source is missing a numeric access level.")
    if target_level > principal_level:
        return False

    principal_requirements = set(principal.get("__access_req__") or [])
    target_requirements = set(target.get("__access_req__") or [])
    if not target_requirements.issubset(principal_requirements):
        return False

    for field in ("__access_grp1__", "__access_grp2__"):
        principal_values = set(principal.get(field) or ["__EMPTY__"])
        target_values = set(target.get(field) or ["__EMPTY__"])
        if not target_values.intersection(principal_values | {"__EMPTY__"}):
            return False
    return True


def expected_case_items_for_principal(
    plan: SeedPlan,
    case_source: dict[str, Any],
    principal: dict[str, Any],
) -> list[dict[str, Any]]:
    """Derive Case item visibility from frozen principal/linked-Hit access helpers."""
    hits_by_id = {document.document_id: document.source for document in plan.documents if document.collection == "hit"}
    visible: list[dict[str, Any]] = []
    for item in case_source.get("items", []):
        if item.get("classification") is None:
            visible.append(copy.deepcopy(item))
            continue
        if item.get("type") != "hit":
            raise RehearsalAbort(
                "Cannot independently derive a classified non-Hit Case item without frozen access helper fields."
            )
        target = hits_by_id.get(item.get("value"))
        if not isinstance(target, dict):
            raise RehearsalAbort("Fixture Case item references a Hit missing from the frozen plan.")
        _require(
            target.get("classification") == item.get("classification"),
            "Fixture Case item classification differs from its linked frozen Hit source.",
        )
        if fixture_acl_allows(principal, target):
            visible.append(copy.deepcopy(item))
    return visible


def expected_case_http_response(case_source: dict[str, Any], visible_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Project the frozen source into the existing v2 Case GET singleResponse shape."""
    expected = {
        key: copy.deepcopy(value)
        for key, value in case_source.items()
        if key != "id" and key not in ACCESS_FIELDS and key != "_id"
    }
    expected["items"] = copy.deepcopy(visible_items)
    return expected


def assert_case_read_matches_fixture(actual: Any, expected: dict[str, Any]) -> None:
    """Require exact Case data/classification/items while reporting stable field differences."""
    if not isinstance(actual, dict):
        raise RehearsalAbort("restricted-reader GET Case did not return a JSON object.")
    differing_keys = sorted(key for key in set(actual) | set(expected) if actual.get(key) != expected.get(key))
    difference = {key: {"expected": expected.get(key), "actual": actual.get(key)} for key in differing_keys}
    _require(
        not difference,
        f"restricted-reader GET Case data/classification/items differ: {json.dumps(difference, sort_keys=True)}",
    )


def assert_application_child_alive(process: Any, *, context: str) -> None:
    """Reject an application request sequence if the real WSGI child has exited."""
    returncode = process.poll()
    _require(returncode is None, f"Howler WSGI child exited during {context} (return code {returncode}).")


def finalize_application_checks(process: Any, results: dict[str, Any]) -> dict[str, Any]:
    """Make an exited/failed application child an explicit non-passing application gate."""
    try:
        assert_application_child_alive(process, context="application-check finalization")
    except RehearsalAbort as error:
        results.setdefault("failures", []).append(str(error))
    results["result"] = "PASS" if not results.get("failures") else "FAIL"
    return results


def acceptance_result(gates: dict[str, str]) -> str:
    """Derive acceptance solely from executed gates; there is no operator override."""
    required = {"mapping_parity", "upgrade", "raw_queries", "application", "no_app_mutation", "rollback"}
    if set(gates) != required:
        return "BLOCKED"
    return "PASS" if all(value == "PASS" for value in gates.values()) else "FAIL"


def _minimal_python_environment(
    *,
    api_root: Path,
    api_endpoint: str,
    redis_port: int,
    namespace: str,
    config_dir: Path,
    plugin_dir: Path,
    log_dir: Path,
) -> dict[str, str]:
    """Return a deliberately small environment; all Howler controls are explicit."""
    hosts = [
        {
            "name": "elastic",
            "host": api_endpoint,
            "scheme": "http",
            "username": None,
            "password": None,
            "apikey_id": None,
            "apikey_secret": None,
            "fingerprint": None,
        }
    ]
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(config_dir),
        "TMPDIR": str(config_dir),
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHON_DOTENV_DISABLED": "true",
        "PYTHONPATH": str(api_root),
        "APP_NAME": "howler",
        "HWL_CONF_FOLDER": str(config_dir),
        "HWL_CLASSIFICATION_PATH": str(config_dir / "classification.yml"),
        "HWL_PLUGIN_DIRECTORY": str(plugin_dir),
        "HWL_DATASTORE_INDEX_PREFIX": f"{namespace}-howler",
        "HWL_DATASTORE__HOSTS": json.dumps(hosts, separators=(",", ":")),
        "HWL_DATASTORE__ILM__ENABLED": "false",
        "HWL_AUTH__ALLOW_APIKEYS": "true",
        "HWL_AUTH__INTERNAL__ENABLED": "false",
        "HWL_AUTH__OAUTH__ENABLED": "false",
        "HWL_AUTH__OAUTH__STRICT_APIKEYS": "false",
        "HWL_CORE__PLUGINS": "[]",
        "HWL_CORE__CLUE__ENABLED": "false",
        "HWL_CORE__NOTEBOOK__ENABLED": "false",
        "HWL_CORE__TELEMETRY__ENABLED": "false",
        "HWL_CORE__REDIS__NONPERSISTENT__HOST": "127.0.0.1",
        "HWL_CORE__REDIS__NONPERSISTENT__PORT": str(redis_port),
        "HWL_CORE__REDIS__PERSISTENT__HOST": "127.0.0.1",
        "HWL_CORE__REDIS__PERSISTENT__PORT": str(redis_port),
        "HWL_LOGGING__LOG_DIRECTORY": str(log_dir),
        "HWL_LOGGING__LOG_TO_FILE": "true",
        "HWL_LOGGING__LOG_TO_CONSOLE": "false",
        "HWL_LOGGING__LOG_AS_JSON": "false",
        "HWL_UI__DEBUG": "false",
        "HWL_UI__AUDIT": "false",
        "HWL_UI__ENFORCE_QUOTA": "true",
        "HWL_SYSTEM__RETENTION__ENABLED": "false",
        "HWL_SYSTEM__VIEW_CLEANUP__ENABLED": "false",
        "HWL_SYSTEM__CORRELATION__ENABLED": "false",
        "HWL_SYSTEM__ACTION_QUEUE__ENABLED": "false",
        "HWL_USE_REST_API": "true",
        "HWL_USE_WEBSOCKET_API": "false",
        "HWL_USE_JOB_SYSTEM": "false",
        "HWL_START_BACKGROUND_SERVICES": "false",
        "HWL_UNSECURED_UI": "false",
        "FLASK_SECRET_KEY": uuid.uuid4().hex,
        "HMAC_SECRET_KEY": uuid.uuid4().hex,
        "NO_PROXY": "*",
        "no_proxy": "*",
    }
    return environment


def _write_app_config(work_dir: Path, plan: SeedPlan, *, api_root: Path) -> tuple[Path, Path, Path, str]:
    """Create only run-owned configuration, classifier, plugin, log, and child state paths."""
    config_dir = work_dir / "howler-config"
    plugin_dir = config_dir / "plugins"
    log_dir = work_dir / "howler-logs"
    config_dir.mkdir(mode=0o700)
    plugin_dir.mkdir(mode=0o700)
    log_dir.mkdir(mode=0o700)
    classification_source = api_root / "build_scripts" / "classification.yml"
    classification_target = config_dir / "classification.yml"
    shutil.copyfile(classification_source, classification_target)
    classification_target.chmod(0o400)
    classification_sha256 = hashlib.sha256(classification_target.read_bytes()).hexdigest()

    app_config = {
        "auth": {
            "allow_apikeys": True,
            "allow_extended_apikeys": False,
            "internal": {"enabled": False},
            "oauth": {"enabled": False, "strict_apikeys": False, "providers": {}},
        },
        "core": {
            "plugins": [],
            "telemetry": {"enabled": False},
            "clue": {"enabled": False},
            "notebook": {"enabled": False},
            "redis": {
                "nonpersistent": {"host": "127.0.0.1", "port": 1},
                "persistent": {"host": "127.0.0.1", "port": 1},
            },
        },
        "datastore": {
            "hosts": [
                {
                    "name": "elastic",
                    "host": "127.0.0.1:1",
                    "scheme": "http",
                    "username": None,
                    "password": None,
                    "apikey_id": None,
                    "apikey_secret": None,
                    "fingerprint": None,
                }
            ],
            "ilm": {"enabled": False, "indices": {}},
        },
        "logging": {
            "log_to_console": False,
            "log_to_file": True,
            "log_directory": str(log_dir),
            "log_as_json": False,
        },
        "system": {
            "retention": {"enabled": False},
            "view_cleanup": {"enabled": False},
            "correlation": {"enabled": False},
            "action_queue": {"enabled": False},
        },
        "ui": {"audit": False, "debug": False, "enforce_quota": True},
    }
    config_path = config_dir / "config.yml"
    config_path.write_text(json.dumps(app_config, indent=2) + "\n", encoding="utf-8")
    config_path.chmod(0o400)
    (config_dir / "mappings.yml").write_text("{}\n", encoding="utf-8")
    (config_dir / "mappings.yml").chmod(0o400)
    _require(plan.environment == application_environment(plan.namespace), "App config plan environment changed.")
    return config_dir, plugin_dir, log_dir, classification_sha256


def _inspect_redis(runtime: es_rehearsal.DockerRuntime, handle: RedisHandle) -> dict[str, Any]:
    try:
        response = json.loads(runtime._docker(["inspect", handle.container_id]))[0]
    except (IndexError, json.JSONDecodeError) as error:
        raise RehearsalAbort("Redis Docker inspect did not return its owned container object.") from error
    _require(response.get("Id") == handle.container_id, "Redis container ID changed.")
    _require(response.get("Name", "").lstrip("/") == handle.name, "Redis container name changed.")
    labels = response.get("Config", {}).get("Labels", {})
    _require(
        labels.get(es_rehearsal.LABEL_KEY) == "true"
        and labels.get("howler.step9.run") == runtime.run_id
        and labels.get("howler.step9.role") == "application-redis",
        "Redis container is not owned by this exact Step 9 application rehearsal.",
    )
    _require(
        response.get("Config", {}).get("Image") == REDIS_IMAGE,
        "Redis container image differs from the pinned rehearsal image.",
    )
    _require(response.get("State", {}).get("Status") == "running", "Owned Redis container is not running.")
    host_config = response.get("HostConfig", {})
    _require(host_config.get("NetworkMode") == "bridge", "Redis must use only the separate default Docker bridge.")
    _require(
        not host_config.get("Privileged") and not host_config.get("Devices") and not host_config.get("CapAdd"),
        "Redis container has unexpected elevated host privileges.",
    )
    tmpfs = host_config.get("Tmpfs") or {}
    mounts = response.get("Mounts", [])
    _require(
        set(tmpfs) == {"/data"} and mounts == [] and not host_config.get("Binds"),
        "Rehearsal Redis data must use only its container-owned ephemeral /data tmpfs.",
    )
    bindings = host_config.get("PortBindings") or {}
    expected = bindings.get(f"{REDIS_PORT}/tcp")
    if set(bindings) != {f"{REDIS_PORT}/tcp"} or not isinstance(expected, list) or len(expected) != 1:
        raise RehearsalAbort("Redis publishes unexpected ports.")
    binding = expected[0]
    _require(binding.get("HostIp") == "127.0.0.1", "Redis host port must bind only to IPv4 loopback.")
    _require(
        binding.get("HostPort") in {"", str(handle.port)},
        "Redis requested host port differs from the Docker-assigned ephemeral port.",
    )
    try:
        address = ipaddress.ip_address(binding["HostIp"])
    except (KeyError, ValueError) as error:
        raise RehearsalAbort("Redis host port is not a valid loopback IPv4 binding.") from error
    _require(address == ipaddress.ip_address("127.0.0.1"), "Redis host port is not IPv4 loopback.")
    _require(
        set(response.get("NetworkSettings", {}).get("Networks", {})) == {"bridge"},
        "Redis is attached outside the separate default Docker bridge.",
    )
    published = response.get("NetworkSettings", {}).get("Ports") or {}
    published_binding = published.get(f"{REDIS_PORT}/tcp")
    _require(
        isinstance(published_binding, list)
        and len(published_binding) == 1
        and published_binding[0].get("HostIp") == "127.0.0.1"
        and published_binding[0].get("HostPort") == str(handle.port),
        "Redis runtime port publication differs from its verified configuration.",
    )
    return response


def verify_redis_owned(runtime: es_rehearsal.DockerRuntime, handle: RedisHandle, *, ping: bool = True) -> None:
    """Verify the exact labels, container identity, network, and loopback-only port."""
    _inspect_redis(runtime, handle)
    if ping:
        with socket.create_connection((handle.host, handle.port), timeout=3) as connection:
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = connection.recv(128)
        _require(response == b"+PONG\r\n", f"Owned Redis did not answer PING: {response!r}.")


def start_owned_redis(runtime: es_rehearsal.DockerRuntime) -> RedisHandle:
    """Start a dedicated, ephemeral Redis process on a random loopback host port."""
    name = f"howler-step9-{runtime.run_id}-app-redis"
    existing = set(runtime._docker(["ps", "-a", "--format", "{{.Names}}"], check=True).splitlines())
    _require(name not in existing, f"Refusing a pre-existing application Redis container name: {name!r}.")
    result = runtime._docker(
        [
            "run",
            "-d",
            "--name",
            name,
            "--label",
            f"{es_rehearsal.LABEL_KEY}=true",
            "--label",
            f"howler.step9.run={runtime.run_id}",
            "--label",
            "howler.step9.role=application-redis",
            "--network",
            "bridge",
            "--tmpfs",
            "/data:rw,noexec,nosuid,size=16m",
            "-p",
            f"127.0.0.1::{REDIS_PORT}",
            REDIS_IMAGE,
            "redis-server",
            "--save",
            "",
            "--appendonly",
            "no",
            "--protected-mode",
            "no",
        ]
    )
    container_id = result.strip()
    _require(bool(re.fullmatch(r"[0-9a-f]{12,64}", container_id)), "Docker returned an invalid Redis container ID.")
    try:
        raw = json.loads(runtime._docker(["inspect", container_id]))[0]
        bindings = raw.get("NetworkSettings", {}).get("Ports", {}).get(f"{REDIS_PORT}/tcp") or []
        _require(len(bindings) == 1, "Docker did not assign exactly one ephemeral Redis port.")
        port = int(bindings[0].get("HostPort", "0"))
        _require(1 <= port <= 65535, "Docker assigned an invalid ephemeral Redis port.")
        handle = RedisHandle(name, container_id, "127.0.0.1", port)
        _inspect_redis(runtime, handle)
        deadline = time.monotonic() + min(runtime.timeout, 60)
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((handle.host, handle.port), timeout=3) as connection:
                    connection.sendall(b"*1\r\n$4\r\nPING\r\n")
                    response = connection.recv(128)
            except OSError as error:
                last_error = error
                time.sleep(0.5)
                continue
            _require(response == b"+PONG\r\n", f"Owned Redis did not answer PING: {response!r}.")
            return handle
        raise RehearsalAbort(f"Owned Redis did not become ready: {last_error or 'timeout'}.")
    except Exception:
        _remove_failed_owned_redis(runtime, name, container_id)
        raise


def _remove_failed_owned_redis(runtime: es_rehearsal.DockerRuntime, name: str, container_id: str) -> None:
    """Remove a just-created, failed Redis container only if its exact labels still prove ownership."""
    try:
        response = json.loads(runtime._docker(["inspect", container_id]))[0]
    except (IndexError, json.JSONDecodeError, RehearsalAbort):
        return
    labels = response.get("Config", {}).get("Labels", {})
    if not (
        response.get("Id") == container_id
        and response.get("Name", "").lstrip("/") == name
        and labels.get(es_rehearsal.LABEL_KEY) == "true"
        and labels.get("howler.step9.run") == runtime.run_id
        and labels.get("howler.step9.role") == "application-redis"
        and response.get("Config", {}).get("Image") == REDIS_IMAGE
    ):
        return
    if response.get("State", {}).get("Status") == "running":
        runtime._docker(["stop", "--time", "10", container_id])
    runtime._docker(["rm", "-v", container_id])


def remove_owned_redis(runtime: es_rehearsal.DockerRuntime, handle: RedisHandle) -> None:
    """Stop/remove only the exact Redis identity that still passes ownership checks."""
    _inspect_redis(runtime, handle)
    runtime._docker(["stop", "--time", "10", handle.container_id])
    stopped = json.loads(runtime._docker(["inspect", handle.container_id]))[0]
    _require(stopped.get("State", {}).get("Status") == "exited", "Owned Redis did not stop cleanly.")
    labels = stopped.get("Config", {}).get("Labels", {})
    _require(
        labels.get(es_rehearsal.LABEL_KEY) == "true"
        and labels.get("howler.step9.run") == runtime.run_id
        and labels.get("howler.step9.role") == "application-redis",
        "Redis ownership changed before container removal.",
    )
    runtime._docker(["rm", handle.container_id])
    runtime.resources.setdefault("removed_containers", []).append(
        {"role": "application-redis", "name": handle.name, "container_id": handle.container_id}
    )


def _app_child_source() -> str:
    """Child bootstrap: assert sanitized config before importing/serving the Flask app."""
    return """\
import json
import os
import sys
from pathlib import Path
from howler.config import DEBUG, HWL_USE_JOB_SYSTEM, HWL_USE_WEBSOCKET_API, config
from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.app import app
assert DEBUG is False
assert HWL_USE_JOB_SYSTEM is False
assert HWL_USE_WEBSOCKET_API is False
assert config.ui.debug is False
assert config.auth.internal.enabled is False
assert config.auth.oauth.enabled is False
assert config.auth.allow_apikeys is True
assert config.core.plugins == set()
assert config.core.clue.enabled is False
assert config.core.notebook.enabled is False
assert config.core.telemetry.enabled is False
assert config.datastore.ilm.enabled is False
assert config.system.retention.enabled is False
assert config.system.view_cleanup.enabled is False
assert config.system.correlation.enabled is False
assert config.system.action_queue.enabled is False
assert DATASTORE_INDEX_PREFIX == os.environ["HWL_DATASTORE_INDEX_PREFIX"]
assert config.datastore.hosts[0].host == os.environ["STEP9_ES_ENDPOINT"]
assert config.logging.log_directory == os.environ["HWL_LOGGING__LOG_DIRECTORY"]
from werkzeug.serving import make_server
server = make_server("127.0.0.1", 0, app, threaded=True)
ready = Path(sys.argv[1])
ready.write_text(json.dumps({"port": server.server_port, "pid": os.getpid()}) + "\\n", encoding="utf-8")
server.serve_forever()
"""


def start_application_child(
    work_dir: Path,
    *,
    api_root: Path,
    plan: SeedPlan,
    es_endpoint: str,
    redis_port: int,
    config_dir: Path,
    plugin_dir: Path,
    log_dir: Path,
    timeout: int,
) -> AppHandle:
    """Start the real API in a sanitized subprocess on localhost and an ephemeral port."""
    environment = _minimal_python_environment(
        api_root=api_root,
        api_endpoint=es_endpoint,
        redis_port=redis_port,
        namespace=plan.namespace,
        config_dir=config_dir,
        plugin_dir=plugin_dir,
        log_dir=log_dir,
    )
    environment.update(plan.environment)
    environment["STEP9_ES_ENDPOINT"] = es_endpoint
    # Repeat explicit kill switches after the plan environment so no fixture setting can relax them.
    environment.update(
        {
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
    ready_file = work_dir / "howler-child-ready.json"
    stdout_path = work_dir / "howler-child.stdout.log"
    stderr_path = work_dir / "howler-child.stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            [sys.executable, "-c", _app_child_source(), str(ready_file)],
            cwd=api_root,
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        returncode = process.poll()
        if returncode is not None:
            tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-1600:]
            raise RehearsalAbort(f"Howler WSGI child exited before readiness ({returncode}): {tail}")
        if ready_file.is_file():
            try:
                ready = json.loads(ready_file.read_text(encoding="utf-8"))
                port = int(ready["port"])
                _require(1 <= port <= 65535, "Howler child published an invalid local port.")
                handle = AppHandle(process, f"http://127.0.0.1:{port}", ready_file)
                assert_application_child_alive(process, context="startup")
                _wait_api_ready(handle, timeout=min(timeout, 60))
                return handle
            except (OSError, json.JSONDecodeError, KeyError, ValueError, RehearsalAbort) as error:
                last_error = error
        time.sleep(0.2)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-1600:]
    raise RehearsalAbort(f"Howler WSGI child did not become ready: {last_error or 'timeout'}; {tail}")


def _wait_api_ready(app: AppHandle, *, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        assert_application_child_alive(app.process, context="readiness probe")
        try:
            status, body, _headers = _http_request(app.base_url, "GET", "/api/healthz/ready")
            if status == 200 and body == b"OK":
                return
            last_error = RehearsalAbort(f"Howler readiness returned HTTP {status}: {body[:500]!r}.")
        except (OSError, RehearsalAbort) as error:
            last_error = error
        time.sleep(0.25)
    raise RehearsalAbort(f"Howler application was not ready: {last_error or 'timeout'}.")


def stop_application_child(app: AppHandle) -> None:
    """Stop a child process owned by this invocation without hiding earlier failure."""
    if app.process.poll() is None:
        app.process.terminate()
    try:
        app.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        app.process.kill()
        app.process.wait(timeout=10)
    app.ready_file.unlink(missing_ok=True)


def _http_request(
    base_url: str,
    method: str,
    path: str,
    body: Any = None,
    *,
    authorization: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if authorization is not None:
        request_headers["Authorization"] = authorization
    request_headers.update(headers or {})
    request = urllib.request.Request(f"{base_url}{path}", data=payload, headers=request_headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers.items())
    except urllib.error.URLError as error:
        raise RehearsalAbort(f"Howler HTTP {method} {path} failed: {error}.") from error


def _basic_api_key(username: str, api_key_name: str, api_key_secret: str) -> str:
    value = f"{username}:{api_key_name}:{api_key_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(value).decode("ascii")


def _api_call(
    app: AppHandle,
    username: str,
    credentials: dict[str, Any],
    method: str,
    path: str,
    body: Any = None,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any] | None, dict[str, str]]:
    assert_application_child_alive(app.process, context=f"{method} {path}")
    authorization = _basic_api_key(username, credentials["api_key_name"], credentials["api_key_secret"])
    status, response_body, response_headers = _http_request(
        app.base_url,
        method,
        path,
        body,
        authorization=authorization,
        headers=headers,
    )
    parsed: dict[str, Any] | None = None
    if response_body:
        try:
            value = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RehearsalAbort(f"Howler {method} {path} returned a non-JSON response ({status}).") from error
        if isinstance(value, dict):
            parsed = value
    return status, parsed, response_headers


def _parse_ok(status: int, response: dict[str, Any] | None, *, path: str) -> Any:
    _require(status == 200, f"Howler {path} returned HTTP {status}: {response!r}.")
    if not isinstance(response, dict):
        raise RehearsalAbort(f"Howler {path} response must be a JSON object.")
    _require(response.get("api_status_code") == 200, f"Howler {path} API envelope status is not 200.")
    _require(not response.get("api_error_message"), f"Howler {path} returned an API error: {response!r}.")
    return response.get("api_response")


def verify_user_identity_sources(client: Any, plan: SeedPlan) -> dict[str, Any]:
    """Compare frozen non-admin test identities, including their hashed API keys, verbatim."""
    expected_users = [document for document in plan.documents if document.collection == "user"]
    _require(len(expected_users) == 2, "Application-v1 must carry exactly two non-admin read identities.")
    for document in expected_users:
        response = client.request(
            "GET",
            f"/{urllib.parse.quote(document.index_alias, safe='')}/_doc/"
            f"{urllib.parse.quote(document.document_id, safe='')}",
        )
        _require(
            response.get("found") is True and response.get("_source") == document.source,
            f"Rehearsal user identity {document.document_id!r} differs from the frozen API-key fixture.",
        )
        _require(
            "admin" not in document.source.get("type", []), f"Test identity {document.document_id!r} is privileged."
        )
        keys = document.source.get("apikeys", {})
        _require(
            any(key.get("acl") == ["R"] for key in keys.values() if isinstance(key, dict)),
            f"Test identity {document.document_id!r} has no real read-only API key.",
        )
    return {"result": "PASS", "user_ids": sorted(document.document_id for document in expected_users)}


def run_application_checks(  # noqa: C901
    app: AppHandle,
    *,
    plan: SeedPlan,
    fixture: dict[str, Any],
    redis_runtime: es_rehearsal.DockerRuntime,
    redis: RedisHandle,
) -> dict[str, Any]:
    """Exercise real API authentication, ACL searches/count/facets, and GET/ETag behavior."""
    verify_redis_owned(redis_runtime, redis)
    users = fixture["test_credentials"]
    results: dict[str, Any] = {
        "identity_checks": {},
        "acl_queries": {},
        "denials": {},
        "resource_reads": {},
        "failures": [],
    }

    # Missing and invalid API-key requests use the actual Flask security decorator and
    # real Redis-backed failure/quota paths; no auth function is mocked or bypassed.
    unauth_status, unauth_body, _ = _http_request(
        app.base_url,
        "POST",
        "/api/v2/search/hit",
        {"query": "id:*", "rows": 20},
    )
    wrong_auth = _basic_api_key("step9-reader", "step9-read", "deliberately-wrong-secret")
    wrong_status, wrong_body, _ = _http_request(
        app.base_url,
        "POST",
        "/api/v2/search/hit",
        {"query": "id:*", "rows": 20},
        authorization=wrong_auth,
    )
    results["denials"] = {
        "missing_authorization": {
            "http_status": unauth_status,
            "api_status_code": (json.loads(unauth_body).get("api_status_code") if unauth_body else None),
        },
        "wrong_api_key": {
            "http_status": wrong_status,
            "api_status_code": (json.loads(wrong_body).get("api_status_code") if wrong_body else None),
        },
    }
    if unauth_status != 401 or wrong_status not in {401, 403}:
        results["failures"].append("missing and wrong API-key requests were not denied (401/403 expected)")

    for username, credentials in users.items():
        _require(username in READER_IDS, f"Fixture contains an unexpected Howler test identity {username!r}.")
        _require(
            credentials.get("api_key_name") and credentials.get("api_key_secret"),
            f"{username} has no real API key secret.",
        )
        search_body = {"query": "id:*", "rows": 20, "sort": "id asc", "track_total_hits": True}
        status, response, _headers = _api_call(
            app,
            username,
            credentials,
            "POST",
            "/api/v2/search/hit",
            search_body,
        )
        search_result = _parse_ok(status, response, path="/api/v2/search/hit")
        items = search_result.get("items", []) if isinstance(search_result, dict) else []
        ids = [item.get("id") for item in items if isinstance(item, dict)]

        count_status, count_response, _ = _api_call(
            app,
            username,
            credentials,
            "POST",
            "/api/v2/search/count/hit",
            {"query": "id:*"},
        )
        count_result = _parse_ok(count_status, count_response, path="/api/v2/search/count/hit")

        facet_status, facet_response, _ = _api_call(
            app,
            username,
            credentials,
            "POST",
            "/api/v2/search/facet/hit",
            {"query": "id:*", "fields": ["howler.status"], "mincount": 1, "rows": 20},
        )
        facet_result = _parse_ok(facet_status, facet_response, path="/api/v2/search/facet/hit")
        facets = facet_result.get("howler.status") if isinstance(facet_result, dict) else None

        actual = {
            "ids": ids,
            "count": count_result.get("count") if isinstance(count_result, dict) else count_result,
            "facets": facets,
        }
        results["acl_queries"][username] = {
            "actual": actual,
            "expected": {
                "ids": READER_IDS[username],
                "count": READER_COUNTS[username],
                "facets": READER_FACETS[username],
            },
        }
        try:
            assert_acl_expectations(username, actual)
        except RehearsalAbort as error:
            results["failures"].append(str(error))

    restricted = users["step9-restricted-reader"]
    hit_id = HIT_IDS[5]  # The RESTRICTED//REL TO DEPARTMENT 2 fixture is visible to this reader.
    hit_status, hit_response, hit_headers = _api_call(
        app,
        "step9-restricted-reader",
        restricted,
        "GET",
        f"/api/v1/hit/{hit_id}",
    )
    hit_value = _parse_ok(hit_status, hit_response, path=f"/api/v1/hit/{hit_id}")
    hit_etag = hit_headers.get("ETag") or hit_headers.get("Etag")
    hit_value_id = None
    if isinstance(hit_value, dict):
        hit_value_id = hit_value.get("id")
        howler_value = hit_value.get("howler")
        if not hit_value_id and isinstance(howler_value, dict):
            hit_value_id = howler_value.get("id")
    results["resource_reads"]["hit"] = {
        "http_status": hit_status,
        "id": hit_value_id,
        "etag": hit_etag,
    }
    try:
        assert_resource_etag_contract("hit", hit_etag)
    except RehearsalAbort as error:
        results["failures"].append(str(error))
    if hit_etag:
        conditional_status, _conditional_body, _ = _http_request(
            app.base_url,
            "GET",
            f"/api/v1/hit/{hit_id}",
            authorization=_basic_api_key(
                "step9-restricted-reader",
                restricted["api_key_name"],
                restricted["api_key_secret"],
            ),
            headers={"If-Match": hit_etag},
        )
        results["resource_reads"]["hit"]["if_match_status"] = conditional_status
        if conditional_status != 304:
            results["failures"].append(f"Hit If-Match conditional GET returned HTTP {conditional_status}, expected 304")
    if hit_value_id != hit_id:
        results["failures"].append("restricted-reader GET Hit returned the wrong document")

    case_status, case_response, case_headers = _api_call(
        app,
        "step9-restricted-reader",
        restricted,
        "GET",
        f"/api/v2/case/{CASE_ID}",
    )
    case_value = _parse_ok(case_status, case_response, path=f"/api/v2/case/{CASE_ID}")
    case_etag = case_headers.get("ETag") or case_headers.get("Etag")
    case_value_id = None
    if isinstance(case_value, dict):
        case_value_id = case_value.get("id") or case_value.get("case_id")
    expected_case_source = next(
        document.source
        for document in plan.documents
        if document.collection == "case" and document.document_id == CASE_ID
    )
    restricted_principal = next(
        document.source
        for document in plan.documents
        if document.collection == "user" and document.document_id == "step9-restricted-reader"
    )
    expected_items = expected_case_items_for_principal(plan, expected_case_source, restricted_principal)
    expected_case_response = expected_case_http_response(expected_case_source, expected_items)
    results["resource_reads"]["case"] = {
        "http_status": case_status,
        "id": case_value_id,
        "etag": case_etag,
        "actual": case_value,
        "expected": expected_case_response,
    }
    if case_value_id != CASE_ID:
        results["failures"].append("restricted-reader GET Case returned the wrong document")
    # v2 Case GET is intentionally a singleResponse without ETag. Validate its full
    # frozen payload, including the RESTRICTED/UNRESTRICTED classification and item list.
    assert_resource_etag_contract("case", case_etag)
    try:
        assert_case_read_matches_fixture(case_value, expected_case_response)
    except RehearsalAbort as error:
        results["failures"].append(str(error))

    verify_redis_owned(redis_runtime, redis)
    return finalize_application_checks(app.process, results)


def _assert_repository_ready(client: Any, expected_path: str, name: str) -> None:
    nodes = client.request("GET", "/_nodes/settings")
    _require(
        expected_path in es_rehearsal._seed_snapshot_repo_paths(nodes),
        "ES snapshot path.repo is not the owned workspace.",
    )
    repositories = client.request("GET", "/_snapshot/_all")
    _require(name not in repositories, f"Snapshot repository {name!r} already exists on a fresh cluster.")


def _restore_into_fresh_cluster(
    runtime: es_rehearsal.DockerRuntime,
    *,
    role: str,
    snapshot_repository: str,
    snapshot_name: str,
    repository_path: str,
    indices: list[str],
    expected_state: dict[str, Any],
    donor_uuid: str,
    report: dict[str, Any],
) -> tuple[es_rehearsal.ClusterHandle, es_rehearsal.RestClient, dict[str, Any]]:
    handle = runtime.start(role, es_rehearsal.SOURCE_VERSION, role, repository_readonly=True)
    client, info = es_rehearsal.wait_for_cluster(handle, runtime, runtime.timeout)
    _require(info.get("cluster_uuid") != donor_uuid, f"Fresh {role} cluster reused the donor cluster UUID.")
    _require(not es_rehearsal._index_inventory(client), f"Fresh {role} volume is not empty before snapshot restore.")
    _assert_repository_ready(client, es_rehearsal.REPOSITORY_PATH, snapshot_repository)
    es_rehearsal.register_repository(client, snapshot_repository, repository_path, readonly=True)
    es_rehearsal.restore_snapshot(client, snapshot_repository, snapshot_name, indices)
    health = client.request("GET", "/_cluster/health?wait_for_status=yellow&timeout=600s")
    _require(
        health.get("timed_out") is not True and health.get("status") in {"green", "yellow"},
        f"{role} snapshot restore is unhealthy: {health!r}.",
    )
    inventory = es_rehearsal._index_inventory(client)
    _require(set(inventory) == set(indices), f"{role} restore produced unexpected indices: {sorted(inventory)}.")
    es_rehearsal.upgrade_preflight(client, handle.cluster_name, inventory)
    state = es_rehearsal.capture_data_state(client, indices, es_rehearsal.MAX_DOCS_PER_INDEX)
    es_rehearsal.verify_data_identity(expected_state, state, phase=f"fresh {role} restore", require_uuid_match=False)
    report[role] = {
        "cluster_uuid": info["cluster_uuid"],
        "health": health.get("status"),
        **es_rehearsal._state_summary(state),
    }
    return handle, client, state


def _try_rollback(
    runtime: es_rehearsal.DockerRuntime,
    *,
    snapshot_repository: str,
    snapshot_name: str,
    indices: list[str],
    baseline_state: dict[str, Any] | None,
    donor_uuid: str | None,
    upgraded_uuid: str | None,
    report: dict[str, Any],
) -> bool:
    """Attempt fresh-volume 8.19 restore even after an application gate has failed."""
    if not snapshot_repository or baseline_state is None:
        report["rollback_8_19"] = {
            "result": "BLOCKED_NO_VERIFIED_SNAPSHOT",
            "reason": "No donor snapshot and verified data baseline were available for rollback.",
        }
        return False

    for role in ("cutover", "donor"):
        active = runtime.handles.get(role)
        if active is not None:
            try:
                runtime.stop_and_remove_container(active)
            except Exception as error:  # do not tear down anything whose ownership no longer verifies
                report["rollback_8_19"] = {
                    "result": "FAIL",
                    "reason": f"Could not stop the owned {role} container: {error}",
                }
                return False

    try:
        rollback, client, _rollback_state = _restore_into_fresh_cluster(
            runtime,
            role="rollback",
            snapshot_repository=snapshot_repository,
            snapshot_name=snapshot_name,
            repository_path="/usr/share/elasticsearch/snapshots/rehearsal",
            indices=indices,
            expected_state=baseline_state,
            donor_uuid=donor_uuid or "",
            report=report,
        )
        report["rollback_8_19"] = report.pop("rollback")
        info = es_rehearsal._root(client, rollback.cluster_name, es_rehearsal.SOURCE_VERSION)
        _require(
            rollback.volume != runtime.volumes["cutover"],
            "Rollback must use a fresh data volume from the upgraded target.",
        )
        _require(
            info.get("version", {}).get("number") == es_rehearsal.SOURCE_VERSION,
            "Rollback did not restore onto ES 8.19.11.",
        )
        _require(info.get("cluster_uuid") != upgraded_uuid, "Rollback reused the upgraded cluster UUID.")
        report["rollback_8_19"]["result"] = "PASS"
        report["phases"].append("independent_fresh_8_19_rollback_restore_and_identity_checks_passed")
        return True
    except Exception as error:
        report["rollback_8_19"] = {"result": "FAIL", "reason": f"{type(error).__name__}: {error}"}
        return False


def run_rehearsal(args: argparse.Namespace) -> dict[str, Any]:  # noqa: C901
    """Execute the complete synthetic application rehearsal, always attempting rollback."""
    run_id = args.run_id or uuid.uuid4().hex[:12]
    _require(
        RUN_ID_PATTERN.fullmatch(run_id) is not None,
        "--run-id must be lowercase letters, digits, or hyphens (1-36 chars).",
    )
    namespace = derive_namespace(run_id)
    api_root = Path(getattr(args, "api_root", None) or API_ROOT).expanduser().resolve(strict=True)
    _require(
        (api_root / "howler" / "app.py").is_file() and (api_root / "build_scripts" / "classification.yml").is_file(),
        "--api-root must name a Howler API source tree containing howler/app.py and build_scripts/classification.yml.",
    )
    plan = build_seed_plan(namespace)
    fixture_indices = validate_seed_plan(plan, namespace)
    fixture_module_dir = _get_application_module_path().parent

    work_dir = Path(args.work_dir).expanduser().resolve()
    _require(not work_dir.exists(), f"Work directory already exists; refusing to reuse: {work_dir}.")
    _require(work_dir.parent.is_dir(), "The work directory parent must already exist.")
    _require(
        not work_dir.is_relative_to(api_root),
        "Rehearsal work directory may not be inside the selected API source tree.",
    )
    _require(not work_dir.is_relative_to(REPO_ROOT), "Rehearsal work directory may not be inside the runner worktree.")
    _require("," not in str(work_dir), "Docker bind paths may not contain commas.")
    _require(args.timeout > 0, "Timeout must be positive.")
    # The snapshot repository is bind-mounted into Elasticsearch, which runs as UID 1000.
    # Keep the owned workspace traversable and grant write access only to this disposable
    # snapshot subdirectory; application config/logs remain private to the host user.
    work_dir.mkdir(mode=0o755)
    (work_dir / "seed").mkdir(mode=0o700)
    (work_dir / "rehearsal").mkdir(mode=0o777)
    config_dir, plugin_dir, log_dir, classification_sha256 = _write_app_config(work_dir, plan, api_root=api_root)

    application_verification: dict[str, Any] = {"result": "NOT_RUN", "failures": []}
    report: dict[str, Any] = {
        "run_id": run_id,
        "namespace": namespace,
        "api_root": str(api_root),
        "datastore_index_prefix": plan.environment["HWL_DATASTORE_INDEX_PREFIX"],
        "fixture_version": plan.fixture_version,
        "scope": "synthetic_application_v1_isolated_es_upgrade_not_production_evidence",
        "source_version": es_rehearsal.SOURCE_VERSION,
        "target_version": es_rehearsal.TARGET_VERSION,
        "index_names": fixture_indices,
        "document_counts": dict(Counter(document.collection for document in plan.documents)),
        "classification_sha256": classification_sha256,
        "snapshot": f"step9-app-{run_id}",
        "snapshot_repository": f"step9-app-{run_id}",
        "workflow_result": "BLOCKED",
        "phases": [],
        "gates": {
            "mapping_parity": "NOT_RUN",
            "upgrade": "NOT_RUN",
            "raw_queries": "NOT_RUN",
            "application": "NOT_RUN",
            "no_app_mutation": "NOT_RUN",
            "rollback": "NOT_RUN",
        },
        "application_verification": application_verification,
    }
    runtime = es_rehearsal.DockerRuntime(run_id, work_dir, args.timeout)
    report["resources"] = runtime.resources
    redis: RedisHandle | None = None
    app: AppHandle | None = None
    donor_uuid: str | None = None
    upgraded_uuid: str | None = None
    snapshot_ready = False
    baseline_state: dict[str, Any] | None = None
    raw8: dict[str, Any] | None = None
    cutover_client: es_rehearsal.RestClient | None = None
    rollback_attempted = False

    try:
        _require(args.timeout > 0 and isinstance(plan.query_contracts, dict), "Invalid rehearsal runtime options.")
        report["mapping_parity"] = verify_mapping_parity(
            plan,
            api_root=api_root,
            fixture_module_dir=fixture_module_dir,
            config_dir=config_dir,
        )
        report["gates"]["mapping_parity"] = "PASS"

        runtime._assert_local_context()
        # Check every planned resource name, including the separate Redis container, before
        # the first Docker resource write. DockerRuntime repeats its own exact checks.
        runtime._assert_names_free()
        redis_name = f"howler-step9-{run_id}-app-redis"
        existing_containers = set(runtime._docker(["ps", "-a", "--format", "{{.Names}}"], check=True).splitlines())
        _require(redis_name not in existing_containers, f"Refusing to reuse pre-existing Redis name {redis_name!r}.")
        runtime.create_base_resources()

        donor = runtime.start("donor", es_rehearsal.SOURCE_VERSION, "donor", repository_readonly=False)
        donor_client, donor_info = es_rehearsal.wait_for_cluster(donor, runtime, args.timeout)
        donor_uuid = donor_info["cluster_uuid"]
        if not isinstance(donor_uuid, str) or not donor_uuid or donor_uuid == "_na_":
            raise RehearsalAbort("Cluster UUID is missing.")
        health = donor_client.request("GET", "/_cluster/health")
        inventory = es_rehearsal._index_inventory(donor_client)
        validate_fresh_empty_cluster(donor_info, health, inventory, expected_name=donor.cluster_name)
        _assert_repository_ready(donor_client, es_rehearsal.REPOSITORY_PATH, report["snapshot_repository"])
        report["phases"].append("owned_fresh_8_19_donor_verified_empty_before_writes")

        # This is the only fixture seed point. It is intentionally before snapshot and
        # before the 8.19 restore/9.5 upgrade; there is no post-upgrade seed path.
        seed_application_plan(donor_client, plan)
        _require(
            set(es_rehearsal._index_inventory(donor_client)) == set(fixture_indices),
            "Donor created indices outside the exact fixture namespace.",
        )
        verify_seeded_documents(donor_client, plan)
        verify_user_identity_sources(donor_client, plan)
        donor_state = es_rehearsal.capture_data_state(donor_client, fixture_indices, es_rehearsal.MAX_DOCS_PER_INDEX)

        snapshot_repository = report["snapshot_repository"]
        snapshot_path = "/usr/share/elasticsearch/snapshots/rehearsal"
        es_rehearsal.register_repository(donor_client, snapshot_repository, snapshot_path, readonly=False)
        es_rehearsal.create_snapshot(
            donor_client,
            snapshot_repository,
            report["snapshot"],
            fixture_indices,
            donor.cluster_name,
        )
        snapshot_info = es_rehearsal.snapshot_metadata(donor_client, snapshot_repository, report["snapshot"])
        _require(
            snapshot_info.get("state") == "SUCCESS", f"Application donor snapshot is not successful: {snapshot_info!r}."
        )
        report["donor_snapshot_metadata"] = es_rehearsal.validate_snapshot_version(
            snapshot_info, es_rehearsal.SOURCE_VERSION
        )
        _require(
            sorted(snapshot_info.get("indices", [])) == sorted(fixture_indices),
            "Donor snapshot contains unexpected indices.",
        )
        snapshot_ready = True
        baseline_state = donor_state
        donor_inventory = es_rehearsal._index_inventory(donor_client)
        donor_preflight = es_rehearsal.upgrade_preflight(donor_client, donor.cluster_name, donor_inventory)
        report["donor"] = {
            "cluster_uuid": donor_uuid,
            "preflight": donor_preflight,
            **es_rehearsal._state_summary(donor_state),
        }
        report["phases"].append("application_v1_plan_seeded_on_es8_and_snapshot_verified")
        runtime.stop_and_remove_container(donor)

        # Restore donor snapshot to a new ES 8 volume, then use this restored cluster
        # (not the donor) as the exact query/relevance baseline.
        cutover, cutover_client, state8 = _restore_into_fresh_cluster(
            runtime,
            role="cutover",
            snapshot_repository=snapshot_repository,
            snapshot_name=report["snapshot"],
            repository_path=snapshot_path,
            indices=fixture_indices,
            expected_state=donor_state,
            donor_uuid=donor_uuid,
            report=report,
        )
        verify_user_identity_sources(cutover_client, plan)
        raw8 = capture_plan_queries(cutover_client, plan)
        cutover_info = es_rehearsal._root(cutover_client, cutover.cluster_name, es_rehearsal.SOURCE_VERSION)
        cutover_uuid = cutover_info["cluster_uuid"]
        report["raw_es8"] = raw8
        report["phases"].append("fresh_8_19_snapshot_restore_preflight_and_raw_query_capture_passed")

        upgraded = es_rehearsal.upgrade_same_volume(runtime, cutover)
        upgraded_client, upgraded_info = es_rehearsal.wait_for_cluster(upgraded, runtime, args.timeout)
        upgraded_uuid = upgraded_info["cluster_uuid"]
        es_rehearsal.validate_cluster_info(
            upgraded_info,
            upgraded.cluster_name,
            es_rehearsal.TARGET_VERSION,
            cutover_uuid,
        )
        health9 = upgraded_client.request("GET", "/_cluster/health?wait_for_status=yellow&timeout=600s")
        _require(
            health9.get("timed_out") is not True and health9.get("status") in {"green", "yellow"},
            f"ES 9.5.2 target is unhealthy: {health9!r}.",
        )
        target_capture = capture_application_state(upgraded_client, fixture_indices, es_rehearsal.MAX_DOCS_PER_INDEX)
        state9 = target_capture["application_state"]
        report["es9_internal_indices"] = target_capture["es_internal_indices"]
        es_rehearsal.verify_data_identity(state8, state9, phase="same-volume ES 9.5.2 upgrade", require_uuid_match=True)
        verify_user_identity_sources(upgraded_client, plan)
        raw9 = capture_plan_queries(upgraded_client, plan)
        report["raw_es9"] = raw9
        query_results = compare_plan_queries(raw8, raw9)
        report["raw_query_comparison"] = query_results
        report["gates"]["raw_queries"] = (
            "PASS" if all(item["result"] == "PASS" for item in query_results.values()) else "FAIL"
        )
        report["upgraded_9_5"] = {
            "cluster_uuid": upgraded_uuid,
            "health": health9.get("status"),
            **es_rehearsal._state_summary(state9),
        }
        report["gates"]["upgrade"] = "PASS"
        report["phases"].append("same_volume_es9_upgrade_identity_source_mapping_alias_and_raw_checks_completed")

        # Snapshot every user/source/mapping/alias/UUID invariant immediately before
        # application startup and again after it has shut down.
        before_app_capture = capture_application_state(
            upgraded_client, fixture_indices, es_rehearsal.MAX_DOCS_PER_INDEX
        )
        state_before_app = before_app_capture["complete_state"]
        report["identity_sources_before_application"] = verify_user_identity_sources(upgraded_client, plan)
        report["application_source_state_before"] = es_rehearsal._state_summary(state_before_app)
        report["application_indices_state_before"] = es_rehearsal._state_summary(
            before_app_capture["application_state"]
        )
        report["application_full_cluster_state_before"] = es_rehearsal._state_summary(
            before_app_capture["complete_state"]
        )
        report["application_internal_indices_before"] = before_app_capture["es_internal_indices"]
        report["application_inventory_before"] = before_app_capture["inventory"]

        try:
            redis = start_owned_redis(runtime)
            report["resources"]["application_redis"] = asdict(redis)
            verify_redis_owned(runtime, redis)
            endpoint = upgraded.base_url.removeprefix("http://")
            app = start_application_child(
                work_dir,
                api_root=api_root,
                plan=plan,
                es_endpoint=endpoint,
                redis_port=redis.port,
                config_dir=config_dir,
                plugin_dir=plugin_dir,
                log_dir=log_dir,
                timeout=args.timeout,
            )
            report["application_endpoint"] = app.base_url
            fixture_path = (
                _get_application_module_path().parents[1]
                / "test"
                / "fixtures"
                / "step9_application"
                / "application-v1.json"
            )
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            # The fixture loader has already authenticated the frozen file hash via
            # build_seed_plan; this fresh read supplies the non-secret request credentials.
            result = run_application_checks(app, plan=plan, fixture=fixture, redis_runtime=runtime, redis=redis)
            application_verification = result
            report["application_verification"] = application_verification
            report["gates"]["application"] = result["result"]
        except Exception as error:
            application_verification = {
                "result": "FAIL",
                "failures": [f"{type(error).__name__}: {error}"],
            }
            report["application_verification"] = application_verification
            report["gates"]["application"] = "FAIL"
        finally:
            if app is not None:
                try:
                    stop_application_child(app)
                except Exception as error:
                    application_verification.setdefault("failures", []).append(
                        f"Failed to stop owned Howler child: {type(error).__name__}: {error}"
                    )
                    report["gates"]["application"] = "FAIL"
            if redis is not None:
                try:
                    verify_redis_owned(runtime, redis)
                    remove_owned_redis(runtime, redis)
                    report["resources"].pop("application_redis", None)
                except Exception as error:
                    application_verification.setdefault("failures", []).append(
                        f"Redis ownership/cleanup check failed: {type(error).__name__}: {error}"
                    )
                    report["gates"]["application"] = "FAIL"
                    report["resources"]["application_redis_cleanup_error"] = f"{type(error).__name__}: {error}"

        no_mutation_errors: list[str] = []
        after_app_capture: dict[str, Any] | None = None
        try:
            after_app_capture = capture_application_state(
                upgraded_client, fixture_indices, es_rehearsal.MAX_DOCS_PER_INDEX
            )
        except Exception as error:
            no_mutation_errors.append(f"{type(error).__name__}: {error}")

        if after_app_capture is not None:
            report["application_source_state_after"] = es_rehearsal._state_summary(after_app_capture["complete_state"])
            report["application_indices_state_after"] = es_rehearsal._state_summary(
                after_app_capture["application_state"]
            )
            report["application_full_cluster_state_after"] = report["application_source_state_after"]
            report["application_internal_indices_after"] = after_app_capture["es_internal_indices"]
            report["application_inventory_after"] = after_app_capture["inventory"]
            added_indices = sorted(set(after_app_capture["inventory"]) - set(before_app_capture["inventory"]))
            removed_indices = sorted(set(before_app_capture["inventory"]) - set(after_app_capture["inventory"]))
            report["application_inventory_delta"] = {"added": added_indices, "removed": removed_indices}
            report["application_internal_state_delta"] = internal_system_state_delta(
                before_app_capture, after_app_capture
            )
            try:
                es_rehearsal.verify_data_identity(
                    before_app_capture["application_state"],
                    after_app_capture["application_state"],
                    phase="application HTTP verification of all 11 protected Howler indices and frozen sources",
                    require_uuid_match=True,
                )
            except Exception as error:
                no_mutation_errors.append(f"{type(error).__name__}: {error}")
            try:
                report["identity_sources_after_application"] = verify_user_identity_sources(upgraded_client, plan)
            except Exception as error:
                no_mutation_errors.append(f"{type(error).__name__}: {error}")

        if no_mutation_errors:
            report["application_source_state_after_error"] = "; ".join(no_mutation_errors)
            report["gates"]["no_app_mutation"] = "FAIL"
        else:
            report["gates"]["no_app_mutation"] = "PASS"
        if report["gates"]["application"] == "PASS":
            report["phases"].append("real_authenticated_howler_application_checks_passed_without_es_mutation")
        else:
            report["phases"].append("real_authenticated_howler_application_checks_completed_with_gate_failures")

    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        if report["gates"].get("upgrade") == "NOT_RUN":
            report["gates"]["upgrade"] = "FAIL"
    finally:
        # A verified saved snapshot is the only basis for a safe rollback. This block is
        # intentionally unconditional after snapshot creation, including app ACL/query failures.
        if snapshot_ready and baseline_state is not None:
            rollback_attempted = True
            report["gates"]["rollback"] = (
                "PASS"
                if _try_rollback(
                    runtime,
                    snapshot_repository=report["snapshot_repository"],
                    snapshot_name=report["snapshot"],
                    indices=fixture_indices,
                    baseline_state=baseline_state,
                    donor_uuid=donor_uuid,
                    upgraded_uuid=upgraded_uuid,
                    report=report,
                )
                else "FAIL"
            )
        else:
            report["rollback_8_19"] = {
                "result": "BLOCKED_NO_VERIFIED_SNAPSHOT",
                "reason": "Preflight or donor snapshot gate prevented a safe rollback restore.",
            }
            report["gates"]["rollback"] = "FAIL"
        report["rollback_attempted"] = rollback_attempted
        report["resources"] = runtime.resources
        report["workflow_result"] = acceptance_result(report["gates"])
        report_path = work_dir / "application-rehearsal-report.json"
        es_rehearsal._write_json(report_path, report)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", help="New, non-existing directory for isolated Docker data and evidence.")
    parser.add_argument(
        "--api-root",
        help="Howler API source root used for mapping parity and the WSGI child (defaults to this script's worktree).",
    )
    parser.add_argument("--run-id", help="Unique 1-36 character lowercase-safe run suffix; generated by default.")
    parser.add_argument("--timeout", type=int, default=900, help="Readiness/HTTP timeout in seconds.")
    args = parser.parse_args()
    if not args.run_id:
        args.run_id = uuid.uuid4().hex[:12]
    if not args.work_dir:
        args.work_dir = str(Path("/tmp/opencode") / f"step9-application-{args.run_id}")
    try:
        report = run_rehearsal(args)
    except (RehearsalAbort, FixtureContractError, OSError, subprocess.SubprocessError) as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["workflow_result"] == "PASS":
        return 0
    print(
        f"{report['workflow_result']}: one or more request-derived Step 9 rehearsal gates did not pass; "
        f"inspect {Path(args.work_dir) / 'application-rehearsal-report.json'}.",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
