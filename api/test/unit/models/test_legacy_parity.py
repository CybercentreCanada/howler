"""Check the Pydantic public contracts against independent, offline legacy captures."""

import hashlib
import json
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest

from howler.datastore.collection import ESCollection
from howler.datastore.howler_store import INDEXES
from howler.models import ModelExtensionRegistry, schema
from howler.models.case import Case
from howler.models.hit import Hit

FIXTURES = Path(__file__).with_name("fixtures")
INDEX_CONTRACT = json.loads((FIXTURES / "legacy_public_contract.json").read_text())
EXAMPLES = json.loads((FIXTURES / "legacy_public_contract_examples.json").read_text())


def _digest(value):
    # Elasticsearch objects are unordered, but the first matching dynamic template wins.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _assert_index_contract(model, expected):
    assert _digest(schema.index_settings(model, shards=1, replicas=0)) == expected["settings"]
    assert _digest(schema.document_mapping(model)) == expected["mappings"]


def _finalized_hit(monkeypatch, extensions):
    registry = ModelExtensionRegistry()
    plugins = Path(__file__).resolve().parents[4] / "plugins"
    for name in extensions.split("+"):
        if name == "clue":
            module = import_module("howler.models.clue")
        else:
            monkeypatch.syspath_prepend(plugins / name)
            module = import_module(f"{name}.models.hit")
        monkeypatch.setattr(module, "model_extensions", registry)
        module.declare_hit_extension()
    return registry.finalize(Hit)


@pytest.mark.parametrize("name", INDEX_CONTRACT["collections"])
def test_core_index_contract(name):
    _assert_index_contract(INDEXES[name], INDEX_CONTRACT["collections"][name])


@pytest.mark.parametrize("extensions", INDEX_CONTRACT["hit_extensions"])
def test_finalized_hit_index_contract(monkeypatch, extensions):
    _assert_index_contract(_finalized_hit(monkeypatch, extensions), INDEX_CONTRACT["hit_extensions"][extensions])


def test_case_reads_and_resaves_legacy_source(monkeypatch):
    source = EXAMPLES["case_source"]
    store = Mock()
    monkeypatch.setattr(ESCollection, "IGNORE_ENSURE_COLLECTION", True)
    collection = ESCollection(store, "case", model_class=Case)

    case = collection.normalize(source, doc_id=source["id"], read=True)
    collection.save(case.meta.id, case)

    store.client.index.assert_called_once()
    assert json.loads(store.client.index.call_args.kwargs["document"]) == source


def test_hit_serialized_primitives():
    hit = Hit.model_validate(
        {
            "timestamp": "2024-01-02T03:04:05.000000Z",
            "howler": {"id": "hit-1", "analytic": "My Analytic", "hash": "abcd1234", "assessment": None},
            "related": {"ip": ["127.0.0.1"]},
            "source": {"ip": "127.0.0.1", "original": {"domain": "Example.COM"}},
        }
    )
    assert hit.as_primitives(ip_format="int") == EXAMPLES["hit_ip_int"]


def test_finalized_hit_extension_primitives(monkeypatch):
    model = _finalized_hit(monkeypatch, "clue+evidence+sentinel")
    timestamp = "2024-01-02T03:04:05Z"
    hit = model.model_validate(
        {
            "timestamp": timestamp,
            "howler": {"id": "hit-1", "analytic": "Parity", "hash": "abcd"},
            "clue": {"types": [{"field": "agent.id", "type": "sensor"}]},
            "evidence": [
                {"timestamp": timestamp, "agent": {"id": "sensor-1"}, "tags": ["source-A"]},
                {"timestamp": timestamp, "tags": ["source-B"]},
            ],
            "sentinel": {"alert_id": "alert-1"},
        }
    )
    primitives = hit.as_primitives()
    assert {name: primitives[name] for name in ("clue", "evidence", "sentinel")} == EXAMPLES["extension_primitives"]
