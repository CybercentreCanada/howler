"""Standalone, fail-closed ES 8.19.11/9.5.2 differential; no Howler runtime/store imports.

Offline (bypass application conftest and its runtime imports):
    poetry run pytest --noconftest -q test/integration/regression/test_step9_es8_es9_baseline.py
Live, ONLY after all datastore-mutating suites have stopped:
    STEP9_PAIRED_LIVE=1 STEP9_SERIAL_CONFIRMED=1 poetry run pytest --noconftest -q \
        test/integration/regression/test_step9_es8_es9_baseline.py
Observe complete raw evidence on stdout (never writes/updates the frozen fixture):
    STEP9_SERIAL_CONFIRMED=1 poetry run python -m \
        test.integration.regression.test_step9_es8_es9_baseline --observe

Only the two named, Docker-labeled isolated rehearsal containers below are allowed.
The 9.x Python client cannot talk to ES8: urllib transports ordinary JSON instead.
Scores have NO tolerance/rounding; hits and buckets are NEVER reordered. A difference
fails pending explicit user approval; there is deliberately no golden-update switch.
This small corpus is a search regression gate, not a full snapshot/upgrade rehearsal.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

import pytest

from howler.models import HowlerESModel, date, integer, keyword, list_field, optional, register_model, text

# schema.py's logger normally imports howler.config (Redis/cache/quota initialization).
# Replace ONLY its logging factory during import; use the real, unmodified schema builders.
# The scoped patch is restored immediately, without initializing any application runtime.
with patch("howler.common.logging.get_logger", logging.getLogger):
    from howler.models.schema import document_mapping, index_settings

if not __debug__:
    raise RuntimeError("This destructive test harness must not run with Python assertions disabled")

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS_PATH = FIXTURES / "step9_es8_es9_corpus.json"
RESULTS_PATH = FIXTURES / "step9_es8_es9_results.json"
CORPUS = json.loads(CORPUS_PATH.read_text())
TARGETS = (
    {
        "version": "8.19.11",
        "container": "howler-step9-canonical-seed-20261001",
        "cluster": "howler-step9-seed-canonical-20261001",
        "role": "seed",
        "run": "canonical-seed-20261001",
    },
    {
        "version": "9.5.2",
        "container": "howler-step9-canonical-20261001-cutover",
        "cluster": "howler-step9-canonical-20261001-cutover",
        "role": "cutover",
        "run": "canonical-20261001",
    },
)
APPROVAL = "Any difference requires explicit user approval; never silently replace the ES8 baseline."


@register_model(index=True, store=True, id_field="key")
class PairedCorpusDocument(HowlerESModel):
    key: keyword()
    message: text(copyto=["__text__"])
    status: keyword()
    owner: optional(keyword())
    severity: integer()
    tags: list_field(keyword())
    observed: date()


def contract():
    settings = index_settings(PairedCorpusDocument, shards=1, replicas=0)
    # Pin term-statistics topology, refresh boundary and BM25 defaults explicitly.
    settings["index"].update(refresh_interval="-1", similarity={"default": {"type": "BM25", "k1": 1.2, "b": 0.75}})
    return {"mappings": document_mapping(PairedCorpusDocument), "settings": settings, "aliases": {}}


def requests():
    """Translate the copied oracle's query semantics without using a datastore client."""
    cases = []
    for case in CORPUS["searches"]:
        cases.append(("search/" + case["name"], case, 20, 0, None))
    page = CORPUS["pagination"]
    for number in range(len(page["pages"])):
        cases.append((f"page/{number}", page, page["rows"], number * page["rows"], None))
    for case in CORPUS["aggregations"]:
        cases.append(("aggregation/" + case["name"], case, 0, 0, CORPUS["aggregation_request"]))
    output = {}
    for name, case, size, offset, aggs in cases:
        filters = list(case.get("filters", []))
        if case.get("access_control"):
            filters.append(case["access_control"])
        body = {
            "query": {
                "bool": {
                    "must": {"query_string": {"query": case["query"], "default_field": "__text__"}},
                    "filter": [{"query_string": {"query": item}} for item in filters],
                }
            },
            "sort": [dict([item.split()]) for item in case.get("sort", ["key asc"])],
            "size": size,
            "from": offset,
            "track_total_hits": True,
            "track_scores": True,
            "_source": False,
        }
        if aggs is not None:
            body["aggs"] = deepcopy(aggs)
        output[name] = body
    return output


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AssertionError(f"Refusing Elasticsearch HTTP redirect ({code})")


class RawES:
    def __init__(self, url):
        self.url = url
        # Neither environment proxies nor redirects may send writes to a different host.
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

    def request(self, method, path, body=None, *, missing=False):
        content_type = "application/json"
        if isinstance(body, bytes):
            data, content_type = body, "application/x-ndjson"
        else:
            data = json.dumps(body, allow_nan=False).encode() if body is not None else None
        request = Request(
            self.url + path,
            data=data,
            method=method,
            headers={"Accept": "application/json", "Content-Type": content_type},
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                assert response.headers.get("X-Elastic-Product") == "Elasticsearch"
                payload = response.read()
                return json.loads(payload) if payload else {}
        except HTTPError as error:
            if missing and error.code == 404:
                return None
            raise AssertionError(f"{method} {path}: HTTP {error.code}: {error.read().decode()}") from error


def docker(*args):
    return json.loads(subprocess.check_output(["docker", *args], text=True, timeout=15))


def validate_container(target, container, network):
    assert container["Name"] == "/" + target["container"], "Wrong container identity"
    assert container["State"]["Running"], "Container not running"
    assert container["Config"]["Image"] == "docker.elastic.co/elasticsearch/elasticsearch:" + target["version"]
    labels = container["Config"]["Labels"]
    for key, expected in {"rehearsal": "true", "role": target["role"], "run": target["run"]}.items():
        assert labels.get("howler.step9." + key) == expected, "Unowned container"
    assert "cluster.name=" + target["cluster"] in container["Config"]["Env"]
    assert "discovery.type=single-node" in container["Config"]["Env"]
    assert container["HostConfig"]["NetworkMode"] != "host"
    assert not container["HostConfig"]["PortBindings"], "Must use an unpublished isolated bridge"
    assert len(container["NetworkSettings"]["Networks"]) == 1
    endpoint = next(iter(container["NetworkSettings"]["Networks"].values()))
    assert network["Id"] == endpoint["NetworkID"]
    assert network["Internal"] is True and network["Driver"] == "bridge", "Network not isolated"
    ip = endpoint["IPAddress"]
    assert re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", ip), "Expected direct bridge IPv4 address"
    return "http://" + ip + ":9200"


def assert_identity(client, target, expected_uuid=None):
    info = client.request("GET", "/")
    assert info["cluster_name"] == target["cluster"], "Wrong cluster identity"
    assert info["version"]["number"] == target["version"], "Wrong cluster version"
    assert info["cluster_uuid"] not in (None, "", "_na_"), "Missing cluster UUID"
    if expected_uuid is not None:
        assert info["cluster_uuid"] == expected_uuid, "Cluster changed during run"
    return info


def discover(target):
    container = docker("inspect", target["container"])[0]
    networks = container["NetworkSettings"]["Networks"]
    assert len(networks) == 1, "Expected exactly one isolated bridge"
    network = docker("network", "inspect", next(iter(networks)))[0]
    url = validate_container(target, container, network)
    client = RawES(url)
    info = assert_identity(client, target)
    evidence = {
        "url": url,
        "info": info,
        "container_id": container["Id"],
        "container_name": container["Name"],
        "image_id": container["Image"],
        "image": container["Config"]["Image"],
        "ownership_labels": {k: v for k, v in container["Config"]["Labels"].items() if k.startswith("howler.step9.")},
        "network_id": network["Id"],
        "network_name": network["Name"],
        "network_internal": network["Internal"],
    }
    return client, evidence


def owned_name(index, token):
    assert re.fullmatch(r"[0-9a-f]{32}", token), "Invalid ownership token"
    assert index == "step9-paired-" + token, "Requires exact owned concrete index (no aliases/wildcards)"


def assert_owned(client, index, token):
    owned_name(index, token)
    mapping = client.request("GET", f"/{index}/_mapping", missing=True)
    if mapping is None:
        return False
    assert set(mapping) == {index}, "Alias or multiple indices resolved"
    assert mapping[index]["mappings"].get("_meta") == {"step9_paired_owner": token}, "Wrong ownership marker"
    aliases = client.request("GET", f"/{index}/_alias")
    assert aliases == {index: {"aliases": {}}}, "Refusing an index associated with aliases"
    return True


def cleanup(client, target, uuid, index, token):
    owned_name(index, token)
    assert_identity(client, target, uuid)
    if not assert_owned(client, index, token):
        return
    assert client.request("DELETE", f"/{index}")["acknowledged"], "Cleanup not acknowledged"
    assert client.request("HEAD", f"/{index}", missing=True) is None, "Cleanup left index behind"


def inventory(client):
    rows = client.request("GET", "/_cat/indices?format=json&h=index,uuid,docs.count&expand_wildcards=all")
    return {row["index"]: {"uuid": row["uuid"], "docs.count": row["docs.count"]} for row in rows}


def effective_contract(client, index):
    """Exclude only documented per-index identity/version metadata, not semantic settings."""
    result = client.request("GET", f"/{index}")
    assert set(result) == {index}
    value = deepcopy(result[index])
    value["mappings"].pop("_meta")
    settings = value["settings"]["index"]
    for key in ("creation_date", "uuid", "version", "provided_name"):
        settings.pop(key)
    return value


def collect(client, target, info, index, token, body):
    uuid = info["cluster_uuid"]
    owned_name(index, token)
    assert_identity(client, target, uuid)
    assert client.request("HEAD", f"/{index}", missing=True) is None, "Refusing pre-existing index or alias"
    try:
        assert client.request("PUT", f"/{index}", body)["acknowledged"]
        assert assert_owned(client, index, token)
        applied = effective_contract(client, index)
        bulk = []
        for document in reversed(CORPUS["documents"]):
            PairedCorpusDocument.model_validate(document)
            bulk.extend([{"create": {"_id": document["key"]}}, document])
        assert_identity(client, target, uuid)
        result = client.request("POST", f"/{index}/_bulk", ("\n".join(json.dumps(row) for row in bulk) + "\n").encode())
        assert result["errors"] is False, result
        assert len(result["items"]) == len(CORPUS["documents"])
        assert all(item["create"]["status"] == 201 and item["create"]["_index"] == index for item in result["items"])
        assert_identity(client, target, uuid)
        assert client.request("POST", f"/{index}/_refresh")["_shards"]["failed"] == 0
        assert client.request("GET", f"/{index}/_count")["count"] == len(CORPUS["documents"])
        health = client.request("GET", f"/_cluster/health/{index}?wait_for_status=green&timeout=10s")
        assert health["status"] == "green" and not health["timed_out"]
        raw = {name: client.request("POST", f"/{index}/_search", request) for name, request in requests().items()}
        results = {name: comparable(response, index) for name, response in raw.items()}
        assert_identity(client, target, uuid)
        return {"effective_contract": applied, "raw_responses": raw, "results": results}
    finally:
        # Also handles partial setup/bulk failure. Never adopts pre-existing/unmarked data.
        cleanup(client, target, uuid, index, token)


def comparable(response, index):
    assert response["timed_out"] is False, "Search timed out"
    assert response["_shards"]["failed"] == 0, "Partial search response"
    assert response["_shards"]["successful"] == response["_shards"]["total"] == 1
    assert response["hits"]["total"]["relation"] == "eq"
    hits = response["hits"]["hits"]
    ids = [hit["_id"] for hit in hits]
    assert len(ids) == len(set(ids)), "Duplicate result IDs"
    assert all(hit["_index"] == index for hit in hits), "Search escaped owned index"
    # Omit ONLY transient transport/index metadata. Keep all hit fields, scores and sort values.
    return {
        "total": response["hits"]["total"],
        "max_score": response["hits"]["max_score"],
        "hits": [{key: value for key, value in hit.items() if key != "_index"} for hit in hits],
        "aggregations": response.get("aggregations"),
    }


def differences(expected, actual, path=""):
    """Report every difference, including order and exact unrounded numeric score drift."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        output = []
        for key in dict.fromkeys([*expected, *actual]):
            child = path + "/" + key
            if key not in expected or key not in actual:
                output.append(
                    {"path": child, "expected": expected.get(key), "actual": actual.get(key), "missing_key": True}
                )
            else:
                output.extend(differences(expected[key], actual[key], child))
        return output
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [{"path": path, "expected": expected, "actual": actual}]
        return [diff for i, (a, b) in enumerate(zip(expected, actual)) for diff in differences(a, b, f"{path}/{i}")]
    return [] if expected == actual else [{"path": path, "expected": expected, "actual": actual}]


def oracle_differences(results):
    output = []
    for case in CORPUS["searches"]:
        name = "search/" + case["name"]
        actual = [hit["_id"] for hit in results[name]["hits"]]
        output.extend(differences(case["ids"], actual, name + "/ordered_ids"))
        output.extend(differences(case["total"], results[name]["total"]["value"], name + "/total"))
        if set(actual) != set(case["ids"]):
            output.append({"path": name + "/result_set", "expected": case["ids"], "actual": actual})
    page = CORPUS["pagination"]
    for number, expected in enumerate(page["pages"]):
        name = f"page/{number}"
        output.extend(differences(expected, [hit["_id"] for hit in results[name]["hits"]], name + "/ids"))
        output.extend(differences(page["total"], results[name]["total"]["value"], name + "/total"))
    for case in CORPUS["aggregations"]:
        name = "aggregation/" + case["name"]
        output.extend(differences(case["expected"], results[name]["aggregations"], name))
        output.extend(differences(case["total"], results[name]["total"]["value"], name + "/total"))
        output.extend(differences([], results[name]["hits"], name + "/hits"))
    return output


def serial_gate():
    assert os.environ.get("STEP9_SERIAL_CONFIRMED") == "1", "Confirm no other datastore-mutating suite is running"
    assert "PYTEST_XDIST_WORKER" not in os.environ, "Run serially without xdist"
    # Defense in depth, not a distributed lock: the operator must coordinate other hosts/runners.
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit() and int(entry.name) != os.getpid():
            try:
                args = (entry / "cmdline").read_bytes().decode().split("\0")
            except (OSError, UnicodeError):
                continue
            if args and ("python" in Path(args[0]).name or Path(args[0]).name in {"pytest", "py.test"}):
                assert not any(Path(arg).name in {"pytest", "py.test"} for arg in args), (
                    f"Other pytest active: {entry.name}"
                )


def run_pair():
    serial_gate()
    # Validate BOTH targets before performing ANY mutation, then seed/search/clean serially.
    discovered = [discover(target) for target in TARGETS]
    assert discovered[0][1]["info"]["cluster_uuid"] != discovered[1][1]["info"]["cluster_uuid"]
    token = uuid4().hex
    index = "step9-paired-" + token
    body = contract()
    body["mappings"]["_meta"] = {"step9_paired_owner": token}
    report: dict[str, Any] = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "command": "STEP9_SERIAL_CONFIRMED=1 poetry run python -m "
        "test.integration.regression.test_step9_es8_es9_baseline --observe",
        "invocation": shlex.join(sys.argv),
        "working_directory": str(Path.cwd()),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "schema_dependencies": {package: package_version(package) for package in ("pydantic", "elasticsearch")},
        "corpus_sha256": hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "source_provenance": CORPUS["source_provenance"],
        "approval_policy": APPROVAL,
        "contract": contract(),
        "requests": requests(),
        "index": index,
        "ingestion_order": [doc["key"] for doc in reversed(CORPUS["documents"])],
        "observations": {},
    }
    for target, (client, evidence) in zip(TARGETS, discovered):
        serial_gate()
        before = inventory(client)
        observed = collect(client, target, evidence["info"], index, token, deepcopy(body))
        after = inventory(client)
        assert before == after, "Existing indices changed during serial run; evidence is not stable"
        report["observations"][target["version"]] = {
            **evidence,
            **observed,
            "existing_indices_before": before,
            "existing_indices_after": after,
            "owned_index_cleanup_verified": True,
        }
    es8, es9 = (report["observations"][target["version"]] for target in TARGETS)
    report["pair_differences"] = differences(es8["results"], es9["results"], "results")
    report["contract_differences"] = differences(
        es8["effective_contract"], es9["effective_contract"], "effective_contract"
    )
    report["oracle_differences"] = {
        version: oracle_differences(observation["results"]) for version, observation in report["observations"].items()
    }
    return report


def frozen_differences(report, frozen):
    output = differences(frozen["corpus_sha256"], report["corpus_sha256"], "corpus_sha256")
    for key in ("contract", "requests"):
        output.extend(differences(frozen[key], report[key], key))
    baseline = frozen["observations"]["8.19.11"]
    for version, observation in report["observations"].items():
        for key in ("results", "effective_contract"):
            output.extend(differences(baseline[key], observation[key], version + "/frozen_es8/" + key))
    return output


def assert_gate(report, frozen):
    diffs = [*report["pair_differences"], *report["contract_differences"], *frozen_differences(report, frozen)]
    for value in report["oracle_differences"].values():
        diffs.extend(value)
    assert not diffs, APPROVAL + "\n" + json.dumps(diffs, indent=2)


def test_fixture_and_frozen_provenance():
    assert [doc["key"] for doc in CORPUS["documents"]] == list("abcdefgh")
    for doc in CORPUS["documents"]:
        assert PairedCorpusDocument.model_validate(doc).key == doc["key"]
    assert len(requests()) == 18
    frozen = json.loads(RESULTS_PATH.read_text())
    assert frozen["schema_version"] == 1
    assert frozen["corpus_sha256"] == hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    assert frozen["contract"] == contract()
    assert frozen["requests"] == requests()
    assert frozen["source_provenance"] == CORPUS["source_provenance"]
    for target in TARGETS:
        observed = frozen["observations"][target["version"]]
        assert observed["info"]["version"]["number"] == target["version"]
        assert observed["info"]["cluster_name"] == target["cluster"]
        assert observed["owned_index_cleanup_verified"] is True
        assert observed["existing_indices_before"] == observed["existing_indices_after"]
        assert observed["results"] == {
            name: comparable(raw, frozen["index"]) for name, raw in observed["raw_responses"].items()
        }
        assert not oracle_differences(observed["results"])
    # A captured ES9 difference remains a visible failing gate, never an accepted ES9 golden.
    assert_gate(frozen, frozen)


def test_standalone_import_and_schema_build_do_not_initialize_runtime():
    script = """
import sys
from unittest.mock import patch
with patch('socket.socket.connect', side_effect=AssertionError('Unexpected network access')):
    from test.integration.regression import test_step9_es8_es9_baseline as harness
    harness.contract()
    harness.requests()
    for document in harness.CORPUS['documents']:
        harness.PairedCorpusDocument.model_validate(document)
for forbidden in ('howler.config', 'howler.config_models', 'howler.datastore.store',
                  'howler.datastore.collection', 'howler.app', 'howler.common.forge'):
    assert forbidden not in sys.modules, forbidden
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=30)


@pytest.mark.parametrize("both_versions_drift", [False, True])
def test_gate_rejects_score_drift_without_rewriting_frozen_baseline(both_versions_drift):
    before = RESULTS_PATH.read_bytes()
    frozen = json.loads(before)
    report = deepcopy(frozen)
    versions = ("8.19.11", "9.5.2") if both_versions_drift else ("9.5.2",)
    for version in versions:
        report["observations"][version]["results"]["search/text-relevance-with-tie-break"]["hits"][0]["_score"] += 1e-12
    # Even stale/empty pair_differences cannot hide equal drift on BOTH new clusters.
    with pytest.raises(AssertionError, match="explicit user approval"):
        assert_gate(report, frozen)
    assert frozen == json.loads(before)
    assert RESULTS_PATH.read_bytes() == before


@pytest.mark.skipif(
    os.environ.get("STEP9_PAIRED_LIVE") != "1", reason="Set STEP9_PAIRED_LIVE=1 for serial isolated live gate"
)
def test_live_pair_matches_frozen_es8():
    assert_gate(run_pair(), json.loads(RESULTS_PATH.read_text()))


@pytest.mark.parametrize("index", ["*", "step9-paired-*", "howler-hit_hot", "step9-paired-alias", "a,b", "../_all"])
def test_cleanup_rejects_non_owned_names_without_network(index):
    client = Mock()
    with pytest.raises(AssertionError, match="exact owned"):
        cleanup(client, TARGETS[0], "uuid", index, "a" * 32)
    assert not client.mock_calls


@pytest.mark.parametrize("marker", [None, {"step9_paired_owner": "b" * 32}])
def test_cleanup_refuses_wrong_marker(marker):
    client = Mock()
    index = "step9-paired-" + "a" * 32
    client.request.side_effect = [
        {"cluster_name": TARGETS[0]["cluster"], "cluster_uuid": "uuid", "version": {"number": "8.19.11"}},
        {index: {"mappings": {"_meta": marker}}},
    ]
    with pytest.raises(AssertionError, match="ownership marker"):
        cleanup(client, TARGETS[0], "uuid", index, "a" * 32)
    assert all(call.args[0] == "GET" for call in client.request.call_args_list)


def test_cleanup_requires_same_cluster():
    client = Mock()
    info = {"cluster_name": TARGETS[0]["cluster"], "cluster_uuid": "changed", "version": {"number": "8.19.11"}}
    client.request.return_value = info
    with pytest.raises(AssertionError, match="Cluster changed"):
        cleanup(client, TARGETS[0], "uuid", "step9-paired-" + "a" * 32, "a" * 32)
    client.request.assert_called_once_with("GET", "/")


@pytest.mark.parametrize("changed", ["version", "cluster", "uuid"])
def test_identity_gate_rejects_mismatches(changed):
    info: dict[str, Any] = {
        "cluster_name": TARGETS[0]["cluster"],
        "cluster_uuid": "uuid",
        "version": {"number": "8.19.11"},
    }
    if changed == "version":
        info["version"]["number"] = "8.19.0"
    elif changed == "cluster":
        info["cluster_name"] = "shared-production"
    else:
        info["cluster_uuid"] = "_na_"
    client = Mock()
    client.request.return_value = info
    with pytest.raises(AssertionError):
        assert_identity(client, TARGETS[0])
    client.request.assert_called_once_with("GET", "/")


@pytest.mark.parametrize("fault", ["name", "label", "version", "network", "published", "stopped"])
def test_docker_safety_rejects_unowned_or_unisolated_targets(fault):
    target = TARGETS[0]
    container: dict[str, Any] = {
        "Name": "/" + target["container"],
        "State": {"Running": True},
        "Config": {
            "Image": "docker.elastic.co/elasticsearch/elasticsearch:8.19.11",
            "Labels": {
                "howler.step9.rehearsal": "true",
                "howler.step9.role": "seed",
                "howler.step9.run": target["run"],
            },
            "Env": ["cluster.name=" + target["cluster"], "discovery.type=single-node"],
        },
        "HostConfig": {"NetworkMode": "bridge", "PortBindings": {}},
        "NetworkSettings": {"Networks": {"test": {"NetworkID": "network", "IPAddress": "172.28.4.2"}}},
    }
    network: dict[str, Any] = {"Id": "network", "Internal": True, "Driver": "bridge"}
    assert validate_container(target, container, network) == "http://172.28.4.2:9200"
    if fault == "name":
        container["Name"] = "/someone-else"
    elif fault == "label":
        container["Config"]["Labels"].pop("howler.step9.rehearsal")
    elif fault == "version":
        container["Config"]["Image"] = "docker.elastic.co/elasticsearch/elasticsearch:latest"
    elif fault == "network":
        network["Internal"] = False
    elif fault == "published":
        container["HostConfig"]["PortBindings"] = {"9200/tcp": [{"HostPort": "9200"}]}
    else:
        container["State"]["Running"] = False
    with pytest.raises(AssertionError):
        validate_container(target, container, network)


@pytest.mark.parametrize(
    "fault", ["alias_resolution", "attached_alias", "unacknowledged", "delete_error", "leftover", None]
)
def test_exact_cleanup_and_failure_propagation(fault):
    client = Mock()
    token = "a" * 32
    index = "step9-paired-" + token
    calls = []

    def respond(method, path, **kwargs):
        calls.append((method, path))
        if path == "/":
            return {"cluster_name": TARGETS[0]["cluster"], "cluster_uuid": "uuid", "version": {"number": "8.19.11"}}
        if path.endswith("/_mapping"):
            return {
                (index if fault != "alias_resolution" else "other"): {
                    "mappings": {"_meta": {"step9_paired_owner": token}}
                }
            }
        if path.endswith("/_alias"):
            return {index: {"aliases": {"shared": {}} if fault == "attached_alias" else {}}}
        if method == "DELETE":
            if fault == "delete_error":
                raise RuntimeError("delete failed")
            return {"acknowledged": fault != "unacknowledged"}
        assert method == "HEAD"
        return {} if fault == "leftover" else None

    client.request.side_effect = respond
    if fault:
        with pytest.raises((AssertionError, RuntimeError)):
            cleanup(client, TARGETS[0], "uuid", index, token)
    else:
        cleanup(client, TARGETS[0], "uuid", index, token)
    deletes = [(method, path) for method, path in calls if method == "DELETE"]
    assert deletes == ([] if fault in {"alias_resolution", "attached_alias"} else [("DELETE", "/" + index)])


@pytest.mark.parametrize("failure", ["preexisting", "create", "bulk"])
def test_partial_setup_never_leaks_owned_index_or_deletes_preexisting(monkeypatch, failure):
    client = Mock()
    token = "a" * 32
    index = "step9-paired-" + token
    info = {"cluster_name": TARGETS[0]["cluster"], "cluster_uuid": "uuid", "version": {"number": "8.19.11"}}
    state = {"exists": failure == "preexisting"}
    mutations = []

    def respond(method, path, body=None, **kwargs):
        if path == "/":
            return info
        if method == "HEAD":
            return {} if state["exists"] else None
        if method == "PUT":
            mutations.append((method, path))
            if failure == "create":
                raise RuntimeError("create failed")
            state["exists"] = True
            return {"acknowledged": True}
        if path.endswith("/_mapping"):
            return {index: {"mappings": {"_meta": {"step9_paired_owner": token}}}} if state["exists"] else None
        if path.endswith("/_alias"):
            return {index: {"aliases": {}}}
        if path.endswith("/_bulk"):
            mutations.append((method, path))
            rows = [json.loads(line) for line in body.splitlines()]
            assert [item["create"]["_id"] for item in rows[::2]] == list("hgfedcba")
            assert all("_index" not in item["create"] for item in rows[::2])
            return {"errors": True, "items": []}
        assert method == "DELETE" and path == "/" + index
        mutations.append((method, path))
        state["exists"] = False
        return {"acknowledged": True}

    client.request.side_effect = respond
    monkeypatch.setattr(sys.modules[__name__], "effective_contract", lambda *_: {})
    with pytest.raises((AssertionError, RuntimeError)):
        collect(client, TARGETS[0], info, index, token, contract())
    if failure == "preexisting":
        assert not mutations
        assert state["exists"]
    else:
        assert not state["exists"]
        assert ("DELETE", "/" + index) in mutations if failure == "bulk" else len(mutations) == 1


def test_discover_both_clusters_before_any_write(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "serial_gate", lambda: None)
    collect_mock = Mock()
    monkeypatch.setattr(sys.modules[__name__], "collect", collect_mock)
    discovery = Mock(side_effect=[(Mock(), {}), RuntimeError("ES9 unavailable")])
    monkeypatch.setattr(sys.modules[__name__], "discover", discovery)
    with pytest.raises(RuntimeError, match="ES9 unavailable"):
        run_pair()
    assert discovery.call_count == 2
    collect_mock.assert_not_called()


@pytest.mark.parametrize("fault", ["timeout", "partial", "duplicate", "wrong_index", "inexact_total"])
def test_invalid_search_response_is_never_compared(fault):
    raw: dict[str, Any] = {
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "failed": 0},
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "max_score": 0.5,
            "hits": [{"_id": "a", "_index": "owned", "_score": 0.5}],
        },
    }
    if fault == "timeout":
        raw["timed_out"] = True
    elif fault == "partial":
        raw["_shards"]["failed"] = 1
    elif fault == "duplicate":
        raw["hits"]["hits"] *= 2
    elif fault == "wrong_index":
        raw["hits"]["hits"][0]["_index"] = "shared"
    else:
        raw["hits"]["total"]["relation"] = "gte"
    with pytest.raises(AssertionError):
        comparable(raw, "owned")


def test_redirects_and_http_errors_are_not_silently_accepted():
    from io import BytesIO

    with pytest.raises(AssertionError, match="redirect"):
        NoRedirects().redirect_request(None, None, 307, "moved", {}, "http://other-host/")
    client = RawES("http://127.0.0.1:1")
    client.opener = Mock()
    for status in (401, 403, 500):
        client.opener.open.side_effect = HTTPError(client.url, status, "failed", {}, BytesIO(b"test error"))
        with pytest.raises(AssertionError, match=f"HTTP {status}"):
            client.request("GET", "/", missing=True)
    client.opener.open.side_effect = HTTPError(client.url, 404, "missing", {}, BytesIO(b"missing"))
    assert client.request("HEAD", "/owned", missing=True) is None


def test_serial_gate_requires_explicit_acknowledgement_and_no_xdist(monkeypatch):
    monkeypatch.delenv("STEP9_SERIAL_CONFIRMED", raising=False)
    with pytest.raises(AssertionError, match="Confirm"):
        serial_gate()
    monkeypatch.setenv("STEP9_SERIAL_CONFIRMED", "1")
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    with pytest.raises(AssertionError, match="xdist"):
        serial_gate()


@pytest.mark.parametrize("path", ["total", "order", "score", "bucket_order", "zero_bucket", "error_count"])
def test_comparison_detects_unsorted_unrounded_drift(path):
    original: dict[str, Any] = {
        "total": {"value": 2, "relation": "eq"},
        "hits": [{"_id": "b", "_score": 0.12345678}, {"_id": "a", "_score": 0.12345678}],
        "aggs": {"error": 0, "buckets": [{"key": 0, "count": 0}, {"key": 1, "count": 2}]},
    }
    changed = deepcopy(original)
    if path == "total":
        changed["total"]["value"] = 3
    elif path == "order":
        changed["hits"].reverse()
    elif path == "score":
        changed["hits"][0]["_score"] += 1e-12
    elif path == "bucket_order":
        changed["aggs"]["buckets"].reverse()
    elif path == "zero_bucket":
        changed["aggs"]["buckets"].pop(0)
    else:
        changed["aggs"]["error"] = 1
    assert differences(original, changed)
    assert not differences(original, deepcopy(original))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observe", action="store_true", required=True, help="Print raw evidence; never update golden")
    parser.parse_args()
    report = run_pair()
    # An initial observation is evidence only; subsequent runs must also match frozen ES8.
    report["frozen_differences"] = (
        frozen_differences(report, json.loads(RESULTS_PATH.read_text())) if RESULTS_PATH.exists() else []
    )
    print(json.dumps(report, indent=2, allow_nan=False))  # noqa: T201 - explicit stdout evidence, never update golden
    sys.exit(
        int(
            bool(
                report["pair_differences"]
                or report["contract_differences"]
                or report["frozen_differences"]
                or any(report["oracle_differences"].values())
            )
        )
    )
