import math
from types import SimpleNamespace

import pytest
from luqum.parser import parser
from luqum.tree import BoolOperation
from luqum.utils import UnknownOperationResolver

from howler import odm
from howler.common import loader
from howler.common.exceptions import InvalidDataException
from howler.odm.models.hit import Hit
from howler.services import lucene_service
from howler.services.lucene_service import LuceneProcessor, is_case_insensitive_field
from howler.utils.lucene import coerce, normalize_phrase, try_parse_ip, try_parse_number


def _eval_tree(query: str, hit_flat: dict) -> bool:
    tree = UnknownOperationResolver(resolve_to=BoolOperation)(parser.parse(query))
    return LuceneProcessor(track_parents=True).visit(tree, {"hit": hit_flat})


def test_numeric_and_phrase_helpers():
    cases = [(None, None), (True, None), (False, None), (0, 0), (0.0, 0.0), ("-42", -42), ("-3.5", -3.5), ("bad", None)]
    for raw, expected in [*cases, ("Infinity", math.inf), ("+Infinity", math.inf), ("-Infinity", -math.inf)]:
        assert try_parse_number(raw) == expected

    assert (coerce(None, try_parse_number), coerce("0", try_parse_number)) == (None, 0)
    assert (coerce("bad", try_parse_ip), coerce(["0", "-5", "bad"], try_parse_number)) == (None, [0, -5])

    assert normalize_phrase("To", "phrase", case_insensitive=False) == ["To"]
    assert normalize_phrase("To", "phrase", case_insensitive=True) == ["to"]
    assert normalize_phrase("Exploit Patcher", "phrase", case_insensitive=False) == ["Exploit Patcher"]
    assert normalize_phrase("Exploit Patcher", "phrase", case_insensitive=True) == ["exploit patcher"]
    assert normalize_phrase("cmd -Enc dGVzdA==", "word", case_insensitive=False) == [
        "cmd-EncdGVzdA",
        "cmd -Enc dGVzdA",
        "cmd -Enc dGVzdA==",
    ]
    assert normalize_phrase("Password Sprayer!", "word", case_insensitive=True) == [
        "passwordsprayer",
        "password sprayer",
        "password sprayer!",
    ]


def test_is_case_insensitive_field_and_plugin_refresh(monkeypatch):
    for field in ("howler.analytic", "howler.hash", "howler.comment.value", "faas.coldstart", "__text__"):
        assert is_case_insensitive_field(field) is True
    for field in ("threat.indicator.provider", "organization.name", "file.hash.ssdeep", "labels.env_t", "custom_b"):
        assert is_case_insensitive_field(field) is False

    @odm.model(index=True, store=True)
    class PluginData(odm.Model):
        tag = odm.CaseInsensitiveKeyword()
        score = odm.Float()
        active = odm.Boolean()

    odm_mod = SimpleNamespace(modify_odm={"hit": lambda t: t.add_namespace("fake", odm.Compound(PluginData))})
    monkeypatch.setattr(
        "howler.datastore.howler_store.get_plugins",
        lambda: [SimpleNamespace(name="fake", modules=SimpleNamespace(odm=odm_mod))],
    )
    monkeypatch.setattr(loader, "_datastore", None)
    monkeypatch.setattr(lucene_service, "_HIT_FIELDS_CACHE", None)
    try:
        assert is_case_insensitive_field("fake.tag") is True
        assert _eval_tree("fake.score:[-440990.34 TO -440990.34]", {"fake.score": -440990.3408391987}) is True
        assert _eval_tree("fake.active:T", {"fake.active": "true"}) is True
    finally:
        if "fake" in Hit.fields():
            Hit.remove_namespace("fake")
    assert is_case_insensitive_field("fake.tag") is False


def test_lucene_processor_edge_cases():
    for query, hit, expected in [
        ("improve", {"message": "improve"}, True),
        ("missing", {"message": "improve"}, False),
        ("threat.indicator.provider:*", {}, False),
        ("event.risk_score:[-10 TO 10]", {}, False),
        ("labels.env_t:PROD", {"labels.env_t": "prod"}, False),
        ("labels.env_t:PROD", {"labels.env_t": "PROD"}, True),
        ("file.drive_letter:T", {"file.drive_letter": "T"}, True),
        ("file.drive_letter:T", {"file.drive_letter": "True"}, False),
        ("faas.coldstart:T", {"faas.coldstart": True}, True),
        ("faas.coldstart:F", {"faas.coldstart": [False]}, True),
        ("event.risk_score:[-440990.34 TO -440990.34]", {"event.risk_score": -440990.3408391987}, True),
        ("event.risk_score:[-Infinity TO 0.0]", {"event.risk_score": -0.5}, True),
        ("event.risk_score:{0.0 TO 10.0}", {"event.risk_score": 0.0}, False),
        ("event.risk_score:{0.0 TO 10.0}", {"event.risk_score": 10.0}, False),
        ("timestamp:[1742947200000 TO 1743120000000]", {"timestamp": ["2025-03-26T17:26:51.486109Z"]}, True),
        ("related.ip:[199.62.243.0 TO 199.62.243.255]", {"related.ip": ["199.62.243.193"]}, True),
    ]:
        assert _eval_tree(query, hit) is expected, query

    with pytest.raises(InvalidDataException):
        _eval_tree("organization.name:[alpha TO omega]", {"organization.name": "CED"})
