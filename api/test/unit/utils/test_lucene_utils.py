import math

import pytest
from luqum.parser import parser
from luqum.tree import BoolOperation
from luqum.utils import UnknownOperationResolver

from howler.common.exceptions import InvalidDataException
from howler.services.lucene_service import LuceneProcessor, is_case_insensitive_field
from howler.utils.lucene import coerce, normalize_phrase, try_parse_ip, try_parse_number


def _eval_tree(query: str, hit_flat: dict) -> bool:
    tree = UnknownOperationResolver(resolve_to=BoolOperation)(parser.parse(query))
    return LuceneProcessor(track_parents=True).visit(tree, {"hit": hit_flat})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        (True, None),
        (False, None),
        (0, 0),
        (0.0, 0.0),
        (-42, -42),
        ("-42", -42),
        ("-3.5", -3.5),
        ("Infinity", math.inf),
        ("+Infinity", math.inf),
        ("-Infinity", -math.inf),
        ("not-a-number", None),
    ],
)
def test_try_parse_number(raw, expected):
    assert try_parse_number(raw) == expected


def test_coerce_preserves_zero_and_handles_none():
    assert coerce(None, try_parse_number) is None
    assert coerce(["0", "-5", "bad"], try_parse_number) == [0, -5]
    assert coerce("0", try_parse_number) == 0
    assert coerce("not-an-ip", try_parse_ip) is None


def test_normalize_phrase_respects_case_sensitivity():
    assert normalize_phrase("To", "phrase", case_insensitive=False) == ["To"]
    assert normalize_phrase("To", "phrase", case_insensitive=True) == ["to"]
    assert normalize_phrase("Exploit Patcher", "phrase", case_insensitive=False) == ["Exploit Patcher"]
    assert normalize_phrase("Exploit Patcher", "phrase", case_insensitive=True) == ["exploit patcher"]

    word_cs = normalize_phrase("powershell.exe -EncodedCommand dGVzdA==", "word", case_insensitive=False)
    assert "powershell.exe -EncodedCommand dGVzdA" in word_cs
    assert "powershell.exe -EncodedCommand dGVzdA==" in word_cs
    assert all("encodedcommand" not in entry for entry in word_cs)

    word_ci = normalize_phrase("Password Sprayer!", "word", case_insensitive=True)
    assert "passwordsprayer" in word_ci
    assert "password sprayer" in word_ci


def test_is_case_insensitive_field():
    assert is_case_insensitive_field("howler.analytic") is True
    assert is_case_insensitive_field("howler.detection") is True
    assert is_case_insensitive_field("howler.hash") is True
    assert is_case_insensitive_field("file.hash.sha256") is True
    assert is_case_insensitive_field("howler.comment.value") is True
    assert is_case_insensitive_field("faas.coldstart") is True
    assert is_case_insensitive_field("__text__") is True
    assert is_case_insensitive_field("custom_t") is True
    assert is_case_insensitive_field("custom_b") is True

    assert is_case_insensitive_field("threat.indicator.provider") is False
    assert is_case_insensitive_field("organization.name") is False
    assert is_case_insensitive_field("file.hash.ssdeep") is False
    assert is_case_insensitive_field("custom_s") is False


def test_lucene_processor_edge_cases():
    # Unfielded query
    assert _eval_tree("improve", {"message": "improve"}) is True
    assert _eval_tree("missing", {"message": "improve"}) is False

    # Missing fields on word and range queries
    assert _eval_tree("threat.indicator.provider:*", {}) is False
    assert _eval_tree("event.risk_score:[-10 TO 10]", {}) is False

    # Single-letter T/F on non-boolean Keyword vs Boolean fields
    assert _eval_tree("file.drive_letter:T", {"file.drive_letter": "T"}) is True
    assert _eval_tree("file.drive_letter:T", {"file.drive_letter": "True"}) is False
    assert _eval_tree("faas.coldstart:T", {"faas.coldstart": True}) is True
    assert _eval_tree("custom_flag_b:F", {"custom_flag_b": [False]}) is True

    # Negative ranges, open-ended -Infinity, and 32-bit Float overflow fallback
    assert _eval_tree("event.risk_score:[-440990.34 TO -440990.34]", {"event.risk_score": -440990.3408391987}) is True
    assert _eval_tree("event.risk_score:[-Infinity TO 0.0]", {"event.risk_score": -0.5}) is True
    assert _eval_tree("event.risk_score:[0.0 TO 1e100]", {"event.risk_score": 1e50}) is True
    assert _eval_tree("event.risk_score:{0.0 TO 10.0}", {"event.risk_score": 0.0}) is False
    assert _eval_tree("event.risk_score:{0.0 TO 10.0}", {"event.risk_score": 10.0}) is False

    # List-valued dates and IPs in ranges
    assert (
        _eval_tree(
            "timestamp:[1742947200000 TO 1743120000000]",
            {"timestamp": ["2025-03-26T17:26:51.486109Z"]},
        )
        is True
    )
    assert _eval_tree("related.ip:[199.62.243.0 TO 199.62.243.255]", {"related.ip": ["199.62.243.193"]}) is True

    with pytest.raises(InvalidDataException):
        _eval_tree("organization.name:[alpha TO omega]", {"organization.name": "CED"})
