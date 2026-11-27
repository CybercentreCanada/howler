"""Check public contracts against independent pre-migration captures."""

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

# Captured from pre-migration ODM at 24940da (core) and 3bd051b (extensions).
# SHA-256 of sorted-key compact JSON; array order, including template precedence, is preserved.
COMMON_SETTINGS = "963418a11293ddecf77782dbe2c44afa4463d2babf03322df56cdbcc5db746e0"
CORE_MAPPINGS = {
    "action": "64a47e0aaaf9dbbd2eb9203209ca786450cdfeb8ac3f69a94f083b1ec5123886",
    "analytic": "6d712565dc8f1b98ed7bc159e302dbbf1aff822db5dca644e2c39addd5e7a8da",
    "case": "ecd87622789453563aae0c4ffa5b8548a334c7efc4a6e5c6a3e76cbaa0678b33",
    "dossier": "bc3e3a3870e0c77ca44062116fcf4a23760c9641fb51e20a7304b770fad5ef1f",
    "event": "6db01a0bdb906aaf5497e4cf6245628af4c40aa0fae5101965eee69b8f8f6b70",
    "hit": "528047e597e75425bf0058c1970561efa0c52d7829e797ebf56f1f83a7faf26d",
    "migration": "97fc36383297bea737d6ce91198615da3e5ad7ac658b1083af74747ca36a8b4f",
    "overview": "297cd38bbe367f50965d56f571b9acb3c72317df3271c767b98cca13ca0a3b76",
    "template": "f712b68c1f2d519f4b0123d1f42836e68ebd9960a01aaf9b224ce0824840ecc5",
    "user": "afdcfb927c3ec64f3dd0cd8c67fc9136c110591325b8ecbeb8d8b1e5749e2c12",
    "user_avatar": "05075c14b7a47ea517fd761ede9e625e0b3d5315f7803986d78aa63de38e2528",
    "view": "9f3cc7ff31cd89017fa056f71c259844e648b5b8ab4a216cba904279c437f589",
}

EXTENSION_CONTRACTS = {
    "clue+evidence+sentinel": (
        "33563e38b71f486179bb2ef8bd4b0bd86d34a043ec777fbb6e76f5dbb9295650",
        "ed07bd6ba41dda0ac3887a896cb23701998d74bd8d26a4db9cf15f9e03263f1a",
    ),
    "clue+evidence": (
        "6276b15a6d9cedffdcff228bde011ca4a32e080cf47cdaeb947e68454631dc96",
        "26c3655f3942153133679b05f85a8e04d4dc773afec156278622c4f9fb4b2581",
    ),
    "clue+sentinel": (COMMON_SETTINGS, "9b2bbf7ec1767797d8289f72d50c3fe6653bc4eae5a76995a346855580ab207c"),
    "clue": (COMMON_SETTINGS, "40062d59170f7a86e8cfe9a9dac6851654fa59c4c6029a74313c392de9c85178"),
    "evidence+sentinel": (
        "7e94d0669245a5cfd39dd8bae36157d01bca628e112837788f02dcb48c50d56d",
        "f076286335c9d3916557fdaf5c9271a47eb4d0db33a2afc2def7c8948449a546",
    ),
    "evidence": (
        "8b9582fadb270c98f6695e5f954d278a8335626ad7a5f697da2a243c9c913338",
        "54d14de993951491c33568b6bc4571adc7212f3067309d40f88457f1c66abac1",
    ),
    "sentinel": (COMMON_SETTINGS, "dbc77468a9149349d5b78ec309dc5e01f6d461cc7181935b173b54fc73aaa9e3"),
}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _assert_index_contract(model, settings, mapping):
    assert _digest(schema.index_settings(model, shards=1, replicas=0)) == settings
    assert _digest(schema.document_mapping(model)) == mapping


@pytest.mark.parametrize("name", CORE_MAPPINGS)
def test_core_index_contract(name):
    _assert_index_contract(INDEXES[name], COMMON_SETTINGS, CORE_MAPPINGS[name])


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


@pytest.mark.parametrize("extensions", EXTENSION_CONTRACTS)
def test_finalized_hit_index_contract(monkeypatch, extensions):
    _assert_index_contract(_finalized_hit(monkeypatch, extensions), *EXTENSION_CONTRACTS[extensions])


def test_case_reads_and_resaves_legacy_source(monkeypatch):
    # Exact legacy ESCollection.save body from application-v2.json at 24940da.
    source = {
        "__access_grp1__": ["__EMPTY__"],
        "__access_grp2__": ["__EMPTY__"],
        "__access_lvl__": 100,
        "__access_req__": [],
        "__index": "case",
        "case_id": "10000000-0000-4000-8000-000000000001",
        "id": "10000000-0000-4000-8000-000000000001",
        "classification": "UNRESTRICTED",
        "created": "2025-09-15T12:00:00.000000Z",
        "escalation": "normal",
        "status": "open",
        "visible": True,
        "title": "Step9 application-v1 linked case",
        "summary": "Deterministic case linked to the first frozen Hit.",
        "participants": ["step9-reader", "step9-restricted-reader"],
        **{name: [] for name in ("enrichments", "indicators", "log", "rules", "targets", "tasks", "threats")},
        "items": [
            {
                "classification": "UNRESTRICTED",
                "id": "20000000-0000-4000-8000-000000000001",
                "name": "Step9 appverify amber alert",
                "type": "hit",
                "visible": True,
                "value": "00000000-0000-4000-8000-000000000001",
            }
        ],
    }
    store = Mock()
    monkeypatch.setattr(ESCollection, "IGNORE_ENSURE_COLLECTION", True)
    collection = ESCollection(store, "case", model_class=Case)

    case = collection.normalize(source, metadata={"id": source["id"]}, read=True)
    collection.save(case.meta.id, case)

    store.client.index.assert_called_once()
    saved = json.loads(store.client.index.call_args.kwargs["document"])
    assert saved == source


def test_hit_serialized_primitives():
    # Exact legacy integer-IP capture from the ODM at 3071fc4.
    hit = Hit.model_validate(
        {
            "timestamp": "2024-01-02T03:04:05.000000Z",
            "howler": {"id": "hit-1", "analytic": "My Analytic", "hash": "abcd1234", "assessment": None},
            "related": {"ip": ["127.0.0.1"]},
            "source": {"ip": "127.0.0.1", "original": {"domain": "Example.COM"}},
        }
    )
    assert hit.model_dump(by_alias=True, exclude_none=True, context={"include_index": True, "ip_format": "int"}) == {
        "__index": "hit",
        "classification": "UNRESTRICTED",
        "ecs": {"version": "8.3.0"},
        "howler": {
            "analytic": "My Analytic",
            "assignment": "unassigned",
            "escalation": "hit",
            "hash": "abcd1234",
            "id": "hit-1",
            "score": 0,
            "scrutiny": "unseen",
            "status": "open",
            **{name: [] for name in ("comment", "data", "dossier", "incidents", "links", "log", "related")},
            "labels": {
                name: []
                for name in (
                    "assignments",
                    "campaign",
                    "generic",
                    "insight",
                    "mitigation",
                    "operation",
                    "threat",
                    "tuning",
                    "victim",
                )
            },
            "votes": {name: [] for name in ("benign", "malicious", "obscure")},
        },
        "labels": {},
        "message": "",
        "tags": [],
        "timestamp": "2024-01-02T03:04:05.000000Z",
        "related": {**{name: [] for name in ("hash", "hosts", "ids", "user")}, "ip": [2130706433]},
        "source": {"ip": 2130706433, "original": {"domain": "example.com"}},
    }


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
    # Exact legacy extension output captured at 3bd051b.
    defaults = {"timestamp": "2024-01-02T03:04:05.000000Z", "labels": {}, "message": "", "ecs": {"version": "8.3.0"}}
    assert {key: primitives[key] for key in ("clue", "evidence", "sentinel")} == {
        "clue": {"types": [{"field": "agent.id", "type": "sensor"}]},
        "evidence": [
            {**defaults, "agent": {"id": "sensor-1"}, "tags": ["source-A"]},
            {**defaults, "tags": ["source-B"]},
        ],
        "sentinel": {"alert_id": "alert-1"},
    }
