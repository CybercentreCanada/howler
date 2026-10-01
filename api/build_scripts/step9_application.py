"""Pure Step 9 application-v1 rehearsal fixture helpers.

The JSON fixture is a permanent, versioned contract artifact. Its collection schemas were
copied from the independent frozen Step 1 inventory, and its stored document sources were
captured from the pinned-HEAD legacy ODM during development. This module deliberately does
not import ``howler.odm`` and never contacts Elasticsearch, Redis, or Howler HTTP endpoints.

``build_seed_plan(namespace)`` is the stable handoff to a future isolated rehearsal runner. It
returns a plan only; it performs no writes. Every alias, physical index, ILM pattern, and raw
query target is rewritten into a required ``step9-...`` namespace. The plan does not authorize
seeding a default ``howler-*`` collection or bypassing compatibility validation. Consumers must
run the current Pydantic/DSL mapping parity gate and validate cluster/Redis/identity ownership
before executing plan actions.

The fixture records raw query and aggregation bodies, but no isolated-cluster ES 8/ES 9
relevance capture or authenticated application verification has been completed. Those gates
remain explicitly ``NOT_CAPTURED`` / ``NOT_RUN`` and must not be reported as a passing cutover
verification.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APPLICATION_FIXTURE_VERSION = "application-v1"
SOURCE_INVENTORY_SHA256 = "6a85a3df82c548ad9d398e6af18c07927e957b2b771ac21c40faea40821add35"
# Updated only alongside the complete fixture after review. This code-pinned fingerprint covers
# the canonical JSON artifact, not a value trusted from its mutable metadata.
APPLICATION_FIXTURE_SHA256 = "e5c6f8f8d4948fef9e49dde93abeb54da8c527351d660150f02ed18617ceac20"
COLLECTION_NAMES = (
    "action",
    "analytic",
    "case",
    "dossier",
    "event",
    "hit",
    "overview",
    "template",
    "user",
    "user_avatar",
    "view",
)
DOCUMENT_COUNTS = {"hit": 8, "case": 1, "user": 2}
ACCESS_FIELDS = ("__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__")
FIXTURE_NAMESPACE = "step9-appverify"
_NAMESPACE_PATTERN = re.compile(r"step9-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "test" / "fixtures" / "step9_application" / "application-v1.json"


class FixtureContractError(ValueError):
    """The frozen application fixture is incomplete, unsafe, or not the supported version."""


@dataclass(frozen=True)
class SeedIndex:
    """One namespaced legacy ``_hot`` index and alias derived from a frozen contract."""

    collection: str
    index_name: str
    alias: str
    settings: dict[str, Any]
    mappings: dict[str, Any]
    historical_ilm_template: dict[str, Any] | None

    def create_body(self) -> dict[str, Any]:
        """Return the application's fresh ``indices.create`` body for this legacy ``_hot`` index."""
        return {
            "settings": deepcopy(self.settings),
            "mappings": deepcopy(self.mappings),
            "aliases": {self.alias: {}},
        }


@dataclass(frozen=True)
class SeedDocument:
    """One frozen stored source and its Elasticsearch ``_id`` in the plan namespace."""

    collection: str
    index_alias: str
    document_id: str
    source: dict[str, Any]

    def bulk_action(self) -> dict[str, Any]:
        """Return a fresh bulk index action; callers still own and must gate all writes."""
        return {
            "_op_type": "index",
            "_index": self.index_alias,
            "_id": self.document_id,
            "_source": deepcopy(self.source),
        }


@dataclass(frozen=True)
class SeedPlan:
    """Exact handoff contract for an isolated rehearsal executor.

    The executor receives process environment, 11 ``_hot`` collection creation bodies, bulk
    document actions, and raw query contracts. Historical ILM templates are comparison metadata
    only; ILM is explicitly disabled for this application startup.
    """

    fixture_version: str
    namespace: str
    indexes: tuple[SeedIndex, ...]
    documents: tuple[SeedDocument, ...]
    query_contracts: dict[str, Any]
    environment: dict[str, str]
    compatibility_validation_required: bool = True
    application_verification_status: str = "NOT_RUN"


def _fixture_path(path: str | Path | None) -> Path:
    return _FIXTURE_PATH if path is None else Path(path)


def _required_dict(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FixtureContractError(f"{description} must be a JSON object")
    return value


def _replace_namespace(value: Any, old_namespace: str, new_namespace: str) -> Any:
    """Deep-copy a query/template payload while changing only namespace-bearing strings."""
    if isinstance(value, dict):
        return {key: _replace_namespace(item, old_namespace, new_namespace) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_namespace(item, old_namespace, new_namespace) for item in value]
    if isinstance(value, str) and (value == old_namespace or value.startswith(f"{old_namespace}-")):
        return new_namespace + value[len(old_namespace) :]
    return deepcopy(value)


def _validate_fixture(fixture: Any) -> dict[str, Any]:
    data = _required_dict(fixture, "application fixture")
    _require_keys(
        data,
        {
            "schema_version",
            "metadata",
            "collections",
            "documents",
            "test_credentials",
            "access_fields",
            "query_contracts",
            "application_verification",
            "application_environment",
        },
        "application fixture",
    )
    if data.get("schema_version") != APPLICATION_FIXTURE_VERSION:
        raise FixtureContractError(f"unsupported application fixture version: {data.get('schema_version')!r}")

    metadata = _required_dict(data.get("metadata"), "fixture metadata")
    _require_keys(
        metadata,
        {
            "source_inventory",
            "source_inventory_sha256",
            "captured_from_commit",
            "collection_contract_source",
            "stored_document_capture",
            "namespace",
            "dynamic_template_order",
        },
        "fixture metadata",
    )
    if metadata.get("source_inventory_sha256") != SOURCE_INVENTORY_SHA256:
        raise FixtureContractError("fixture source inventory hash does not match the frozen Step 1 inventory")
    if metadata.get("namespace") != FIXTURE_NAMESPACE:
        raise FixtureContractError("fixture namespace metadata is missing or unsafe")
    capture = _required_dict(metadata.get("stored_document_capture"), "stored document capture metadata")
    _require_keys(
        capture,
        {
            "producer",
            "timestamp_format",
            "source_postprocessing",
            "runtime_legacy_imports",
            "source_fields",
            "user_password_safety",
        },
        "stored document capture metadata",
    )
    if capture.get("runtime_legacy_imports") is not False:
        raise FixtureContractError("delivered fixture metadata must not require legacy ODM imports")

    _validate_collections(data.get("collections"))
    documents = _validate_documents(data.get("documents"), data.get("test_credentials"))
    _validate_query_contracts(data.get("query_contracts"), documents)
    if data.get("access_fields") != list(ACCESS_FIELDS):
        raise FixtureContractError("fixture access helper inventory must match the four Howler access fields")
    environment = _required_dict(data.get("application_environment"), "application startup environment")
    if environment != _application_environment(FIXTURE_NAMESPACE):
        raise FixtureContractError("fixture startup environment must namespace indices and disable ILM/internal auth")
    verification = _required_dict(data.get("application_verification"), "application verification status")
    if verification.get("status") != "NOT_RUN" or verification.get("must_not_be_reported_as_passed") is not True:
        raise FixtureContractError("application verification must remain explicitly NOT_RUN")
    if not isinstance(verification.get("remaining_gates"), list) or not verification["remaining_gates"]:
        raise FixtureContractError("application verification must enumerate its remaining gates")
    return data


def _require_keys(value: dict[str, Any], expected: set[str], description: str) -> None:
    actual = set(value)
    if actual != expected:
        unknown = actual - expected
        missing = expected - actual
        raise FixtureContractError(f"{description} keys differ; unknown={sorted(unknown)}, missing={sorted(missing)}")


def validate_application_fixture_data(fixture: Any) -> dict[str, Any]:
    """Validate parsed fixture structure without authenticating its complete file fingerprint.

    This is intended for focused structural negative tests. Seed plans must use
    :func:`load_application_fixture`, which additionally checks the canonical artifact SHA.
    """
    return deepcopy(_validate_fixture(fixture))


def _canonical_sha256(fixture: Any) -> str:
    canonical = json.dumps(fixture, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_collections(value: Any) -> None:
    collections = _required_dict(value, "fixture collections")
    if set(collections) != set(COLLECTION_NAMES):
        raise FixtureContractError("fixture must include exactly the 11 legacy collection contracts")
    for name in COLLECTION_NAMES:
        _validate_collection(name, collections[name])


def _validate_collection(name: str, value: Any) -> None:
    contract = _required_dict(value, f"{name} collection contract")
    expected_keys = {"alias", "index_name", "ilm_enabled_by_default", "settings", "mappings", "aliases"}
    if name in {"case", "event", "hit"}:
        expected_keys.add("historical_ilm_template")
    _require_keys(contract, expected_keys, f"{name} collection contract")
    expected_alias = f"{FIXTURE_NAMESPACE}-howler-{name}"
    if contract.get("alias") != expected_alias:
        raise FixtureContractError(f"{name} alias must remain under the fixture namespace")
    if contract.get("index_name") != f"{expected_alias}_hot":
        raise FixtureContractError(f"{name} physical index must use the application _hot convention")
    aliases = contract.get("aliases")
    if isinstance(aliases, dict) and any(isinstance(alias, str) and alias.startswith("howler-") for alias in aliases):
        raise FixtureContractError("default howler-* aliases are forbidden in the application fixture")
    if aliases != {expected_alias: {}}:
        raise FixtureContractError(f"{name} legacy alias body or namespace changed")
    if not isinstance(contract.get("settings"), dict) or not isinstance(contract.get("mappings"), dict):
        raise FixtureContractError(f"{name} must carry complete settings and mappings")
    if not isinstance(contract.get("ilm_enabled_by_default"), bool):
        raise FixtureContractError(f"{name} ILM default must be explicitly recorded")
    mappings = contract["mappings"]
    if not isinstance(mappings.get("properties"), dict) or not isinstance(mappings.get("dynamic_templates"), list):
        raise FixtureContractError(f"{name} mapping is incomplete")
    template = contract.get("historical_ilm_template")
    if template is not None:
        _validate_historical_ilm_template(name, expected_alias, template)


def _validate_historical_ilm_template(name: str, expected_alias: str, value: Any) -> None:
    template = _required_dict(value, f"{name} ILM template")
    if template.get("index_patterns") != [f"{expected_alias}-*"]:
        raise FixtureContractError(f"{name} ILM pattern must remain under the fixture namespace")
    try:
        lifecycle = template["template"]["settings"]["index"]
    except (KeyError, TypeError) as error:
        raise FixtureContractError(f"{name} ILM lifecycle settings are incomplete") from error
    if lifecycle.get("lifecycle.rollover_alias") != expected_alias:
        raise FixtureContractError(f"{name} ILM rollover alias must remain under the fixture namespace")
    expected_policy = f"{expected_alias}_policy"
    if lifecycle.get("lifecycle.name") != expected_policy:
        raise FixtureContractError(f"{name} ILM policy name must remain under the fixture namespace")


def _validate_documents(value: Any, credentials_value: Any) -> dict[str, Any]:
    documents = _required_dict(value, "fixture documents")
    if set(documents) != set(DOCUMENT_COUNTS):
        raise FixtureContractError("fixture documents must contain only Hit, Case, and User seed collections")
    for collection, count in DOCUMENT_COUNTS.items():
        entries = documents[collection]
        if not isinstance(entries, list) or len(entries) != count:
            raise FixtureContractError(f"fixture must contain exactly {count} {collection} documents")
        for entry in entries:
            _validate_document(collection, entry)

    credentials = _required_dict(credentials_value, "test credentials")
    _validate_test_credentials(credentials, documents["user"])
    return documents


def _validate_document(collection: str, value: Any) -> None:
    entry = _required_dict(value, f"{collection} document")
    _require_keys(entry, {"id", "model_primitives", "source"}, f"{collection} document")
    if not isinstance(entry.get("id"), str) or not entry["id"]:
        raise FixtureContractError(f"{collection} document is missing its Elasticsearch _id")
    source = _required_dict(entry.get("source"), f"{collection} source")
    model_primitives = _required_dict(entry.get("model_primitives"), f"{collection} model primitives")
    if "__index" in source or "__index" in model_primitives:
        raise FixtureContractError("frozen sources must not include the synthetic __index annotation")
    if "id" in model_primitives or source.get("id") != entry["id"]:
        raise FixtureContractError(f"{collection} stored source id must equal its Elasticsearch _id")
    expected_source = deepcopy(model_primitives)
    expected_source["id"] = entry["id"]
    if source != expected_source:
        raise FixtureContractError(f"{collection} stored source must equal model primitives plus id == _id")
    if not set(ACCESS_FIELDS).issubset(model_primitives):
        raise FixtureContractError(f"{collection} source must carry all four access helper fields")
    if _contains_now_sentinel(model_primitives):
        raise FixtureContractError(f"{collection} source contains a nondeterministic NOW value")


def _validate_test_credentials(credentials: dict[str, Any], user_entries: list[Any]) -> None:
    user_ids = {entry["id"] for entry in user_entries}
    if set(credentials) != user_ids:
        raise FixtureContractError("test credentials must match exactly the frozen nonadmin User documents")
    for username, identity_value in credentials.items():
        identity = _required_dict(identity_value, f"{username} test credentials")
        _require_keys(identity, {"api_key_name", "api_key_secret"}, f"{username} test credentials")
        user = next(entry["source"] for entry in user_entries if entry["id"] == username)
        if user.get("uname") != username or "admin" in user.get("type", []):
            raise FixtureContractError(f"{username} fixture identity must be nonadmin")
        api_keys = _required_dict(user.get("apikeys"), f"{username} API keys")
        if set(api_keys) != {identity["api_key_name"]}:
            raise FixtureContractError(f"{username} fixture must contain only its declared read-only API key")
        key = _required_dict(api_keys.get(identity["api_key_name"]), f"{username} read API key")
        if key.get("acl") != ["R"] or key.get("agents") != []:
            raise FixtureContractError(f"{username} test API key must carry read-only ACL")
        if user.get("password") in {item.get("password") for item in api_keys.values() if isinstance(item, dict)}:
            raise FixtureContractError(f"{username} internal password hash must differ from API-key hashes")


def _validate_query_contracts(value: Any, documents: dict[str, Any]) -> None:
    query_contracts = _required_dict(value, "query contracts")
    if query_contracts.get("server_versions") != {"baseline": "8.19.11", "target": "9.5.2"}:
        raise FixtureContractError("raw query contracts must pin the Step 9 baseline and target versions")
    requests = _validate_raw_requests(query_contracts.get("requests"))
    expectations = _required_dict(query_contracts.get("source_derived_expectations"), "query expectations")
    _validate_derived_expectations(expectations, requests, documents)
    relevance = _required_dict(expectations.get("relevance"), "relevance capture status")
    if relevance.get("capture_status") != "NOT_CAPTURED" or relevance.get("baseline_es_8_19_11") is not None:
        raise FixtureContractError("uncaptured relevance baselines must remain explicitly unset")
    if relevance.get("target_es_9_5_2") is not None:
        raise FixtureContractError("uncaptured target relevance baseline must remain explicitly unset")


def _validate_raw_requests(value: Any) -> dict[str, Any]:
    requests = _required_dict(value, "raw query requests")
    if set(requests) != {"default_id_search", "exact_hit_lookup", "status_aggregation", "relevance"}:
        raise FixtureContractError("fixture must include id search, lookup, aggregation, and relevance requests")
    for name, request_value in requests.items():
        request = _required_dict(request_value, f"{name} request")
        if request.get("index") != f"{FIXTURE_NAMESPACE}-howler-hit":
            raise FixtureContractError("raw query targets must remain under the fixture namespace")
        _required_dict(request.get("body"), f"{name} request body")
    if requests["default_id_search"]["body"].get("query") != {"query_string": {"query": "id:*"}}:
        raise FixtureContractError("default stored-source search must exercise id:*")
    return requests


def _validate_derived_expectations(
    expectations: dict[str, Any], requests: dict[str, Any], documents: dict[str, Any]
) -> None:
    hits = documents["hit"]
    exact_request = requests["exact_hit_lookup"]["body"].get("query", {}).get("term", {}).get("howler.id")
    if not isinstance(exact_request, str):
        raise FixtureContractError("exact lookup must use a literal howler.id term")
    derived_exact_ids = [
        entry["id"] for entry in hits if entry["model_primitives"].get("howler", {}).get("id") == exact_request
    ]
    if expectations.get("exact_hit_lookup_ids") != derived_exact_ids:
        raise FixtureContractError("exact lookup expectations must be derived from the frozen Hit documents")

    status_counts: dict[str, int] = {}
    for entry in hits:
        status = entry["model_primitives"].get("howler", {}).get("status")
        if not isinstance(status, str):
            raise FixtureContractError("every frozen Hit must carry howler.status for aggregation")
        status_counts[status] = status_counts.get(status, 0) + 1
    derived_status_buckets = [{"key": key, "doc_count": status_counts[key]} for key in sorted(status_counts)]
    if expectations.get("status_aggregation_buckets") != derived_status_buckets:
        raise FixtureContractError("aggregation expectations must be derived from the frozen Hit documents")

    derived_id_search_ids = [entry["id"] for entry in hits if entry["source"].get("id") == entry["id"]]
    if expectations.get("default_id_search_ids") != derived_id_search_ids:
        raise FixtureContractError("id:* search expectations must be derived from stored id fields")


def _contains_now_sentinel(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_now_sentinel(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_now_sentinel(item) for item in value)
    return value == "NOW"


def load_application_fixture(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate a fresh copy of the frozen application-v1 JSON fixture.

    The runtime helper reads only the frozen application fixture; it does not load the legacy
    inventory or any legacy model implementation. A caller-supplied path is primarily useful for
    offline validation and negative tests.
    """
    fixture_path = _fixture_path(path)
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureContractError(f"cannot read application fixture at {fixture_path}") from error
    if _canonical_sha256(fixture) != APPLICATION_FIXTURE_SHA256:
        raise FixtureContractError("application fixture canonical SHA-256 does not match the code-pinned artifact")
    return validate_application_fixture_data(fixture)


def _validate_namespace(namespace: str) -> None:
    if not isinstance(namespace, str) or not _NAMESPACE_PATTERN.fullmatch(namespace) or len(namespace) > 48:
        raise ValueError("namespace must be a non-empty 'step9-<lowercase-safe-name>' namespace")
    if namespace in {"step9-prod", "step9-production", "step9-live", "step9-default"}:
        raise ValueError("production-like namespaces are forbidden for the Step 9 seed plan")
    if namespace == "step9-appverify":
        # The fixed fixture namespace is usable for offline plans; rehearsal callers should pass
        # a unique per-run value instead of sharing aliases across independent runs.
        return


def _application_environment(namespace: str) -> dict[str, str]:
    return {
        "HWL_DATASTORE_INDEX_PREFIX": f"{namespace}-howler",
        "HWL_DATASTORE__ILM__ENABLED": "false",
        "HWL_AUTH__INTERNAL__ENABLED": "false",
    }


def application_environment(namespace: str) -> dict[str, str]:
    """Return the required process environment for a namespaced, ILM-disabled app startup."""
    _validate_namespace(namespace)
    return _application_environment(namespace)


def build_seed_plan(namespace: str) -> SeedPlan:
    """Build a pure, namespaced seed plan; no Elasticsearch write or compatibility bypass occurs.

    The namespace is mandatory to make accidental default-collection targeting difficult. The
    caller must first run the Pydantic/DSL mapping parity check, then validate target-cluster
    identity and disposable namespace ownership before executing any plan action. An executor
    creates each index with ``indices.create(index=index.index_name, **index.create_body())`` and
    bulk-indexes ``document.bulk_action()``. It starts Howler with ``plan.environment``; it must
    not install ``historical_ilm_template`` while ILM is disabled. Existing production documents
    are not part of this seed plan, and an application verification is not performed here.
    """
    _validate_namespace(namespace)
    fixture = load_application_fixture()
    indexes: list[SeedIndex] = []
    for collection in COLLECTION_NAMES:
        contract = fixture["collections"][collection]
        alias = f"{namespace}-howler-{collection}"
        historical_template = contract.get("historical_ilm_template")
        if historical_template is not None:
            historical_template = _replace_namespace(historical_template, FIXTURE_NAMESPACE, namespace)
        indexes.append(
            SeedIndex(
                collection=collection,
                index_name=f"{alias}_hot",
                alias=alias,
                settings=deepcopy(contract["settings"]),
                mappings=deepcopy(contract["mappings"]),
                historical_ilm_template=historical_template,
            )
        )

    documents: list[SeedDocument] = []
    for collection, entries in fixture["documents"].items():
        alias = f"{namespace}-howler-{collection}"
        for entry in entries:
            documents.append(
                SeedDocument(
                    collection=collection,
                    index_alias=alias,
                    document_id=entry["id"],
                    source=deepcopy(entry["source"]),
                )
            )

    return SeedPlan(
        fixture_version=APPLICATION_FIXTURE_VERSION,
        namespace=namespace,
        indexes=tuple(indexes),
        documents=tuple(documents),
        query_contracts=_replace_namespace(fixture["query_contracts"], FIXTURE_NAMESPACE, namespace),
        environment=application_environment(namespace),
    )
