"""Tests for lenient Pydantic model construction."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    compound,
    construct_safe,
    integer,
    keyword,
    list_field,
    uuid,
)


class SafeFlag(HowlerEmbeddedModel):
    """Flag used by safe-construction tests."""

    uuid: uuid()
    name: keyword()
    fans: list_field(integer(), default=[])


class SafeSpeed(HowlerEmbeddedModel):
    """Nested values used by safe-construction tests."""

    fast: integer(default=1)
    slow: keyword(default="abc")
    count: list_field(integer())


class SafeDocument(HowlerESModel):
    """Document used by safe-construction tests."""

    speed: compound(SafeSpeed, default={})
    flags: list_field(compound(SafeFlag))


def test_construct_safe_matches_legacy_drop_behavior() -> None:
    """Valid sub-values survive while rejected values retain their original paths."""
    model, dropped = construct_safe(
        SafeDocument,
        {
            "speed": {"fast": "abc", "count": ["100", 100, "hundred", "9dy"]},
            "flags": [
                "abc",
                {"uuid": "bad"},
                {"name": "good"},
                {"name": "some-good", "fans": [1, "99", "many"]},
            ],
            "cats": "red",
        },
    )

    assert isinstance(model, SafeDocument)
    assert model.speed.fast == 1
    assert model.speed.slow == "abc"
    assert model.speed.count == [100, 100]
    assert len(model.flags) == 2
    assert model.flags[0].name == "good"
    assert model.flags[0].uuid
    assert model.flags[0].fans == []
    assert model.flags[1].name == "some-good"
    assert model.flags[1].fans == [1, 99]

    assert dropped["cats"] == "red"
    assert dropped["speed"]["fast"] == "abc"
    assert set(dropped["speed"]["count"]) == {"hundred", "9dy"}
    assert dropped["flags"][0] == "abc"
    assert dropped["flags"][1] == {"uuid": "bad"}
    assert dropped["flags"][2] == {"fans": ["many"]}


def test_construct_safe_rejects_non_mapping_documents() -> None:
    """Non-object input cannot produce a model and is returned unchanged."""
    model, dropped = construct_safe(SafeDocument, "invalid")
    assert model is None
    assert dropped == "invalid"
