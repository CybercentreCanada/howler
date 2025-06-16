from datetime import datetime
from typing import Any

import pytest

from howler.common.exceptions import HowlerValueError
from howler.helper.workflow import Workflow
from howler.odm.base import UTC_TZ
from howler.services import hit_service


def test_status_transitions_workflow():
    """Validate Hit Transition workflow"""
    workflow: Workflow = hit_service.get_hit_workflow()

    assert len(workflow.transitions) == 19


def test_convert_hit_hash():
    obj = {
        "howler.analytic": "test",
        "howler.detection": "test",
        "howler.score": 1234,
        "howler.data": ["blah blah blah"],
    }

    obj2 = {
        "howler.analytic": "test",
        "howler.detection": "test",
        "howler.score": 1234,
        "howler.data": ["blah blah blah"],
    }

    result_1, _ = hit_service.convert_hit(obj, False)
    result_2, _ = hit_service.convert_hit(obj2, False)

    assert result_1.howler.hash == result_2.howler.hash

    obj2["event.id"] = "whatever"

    result_3, _ = hit_service.convert_hit(obj2, False)

    assert result_2.howler.hash == result_3.howler.hash

    obj2["howler.data"].append("more data")  # type: ignore[attr-defined]

    result_4, _ = hit_service.convert_hit(obj2, False)

    assert result_2.howler.hash != result_4.howler.hash


def test_convert_hit_event():
    obj = {
        "howler.analytic": "test",
        "howler.detection": "test",
        "howler.score": 1234,
        "howler.data": ["blah blah blah"],
    }

    result, _ = hit_service.convert_hit(obj, False)

    assert result.event.created

    create_date = datetime.now(tz=UTC_TZ).replace(year=2500)

    obj["event"] = {"created": create_date}

    result, _ = hit_service.convert_hit(obj, False)

    assert result.event.created == create_date

    obj["event"] = {"kind": "alert"}

    assert result.event.created


def test_convert_hit_mapping():
    data = {"howler.analytic": "test", "labels": {"category": "example"}}

    hit_service.convert_hit(data, True)


def test_convert_hit_list():
    data: dict[str, Any] = {
        "howler.analytic": "test",
        "howler.comment.id": "test",
        "howler.comment.value": "test",
        "howler.comment.user": "test",
        "howler.comment.reactions.thumbs-up": ["test"],
    }

    hit_service.convert_hit(data, True)

    data = {
        "howler.analytic": "test",
        "howler.comment": {
            "id": "test",
            "value": "test",
            "user": "test",
            "reactions": {"thumbs-up": ["test"]},
        },
    }

    hit_service.convert_hit(data, True)

    data = {
        "howler": {
            "analytic": "test",
            "comment": {
                "id": "test",
                "value": "test",
                "user": "test",
                "reactions.thumbs-up": ["test"],
            },
        }
    }

    hit_service.convert_hit(data, True)

    with pytest.raises(HowlerValueError):
        data = {
            "howler.analytic": "test",
            "howler.comment.id": "test",
            "howler.comment.value": "test",
            "howler.comment.user": "test",
            "howler.comment.reactions.thumbs-up.potato": ["test"],
        }

        hit_service.convert_hit(data, True)

    with pytest.raises(HowlerValueError):
        data = {
            "howler.analytic": "test",
            "howler.comment": {
                "id": "test",
                "value": "test",
                "user": "test",
                "reactions": {"thumbs-up": ["test"]},
                "sneaky": "key",
            },
        }

        hit_service.convert_hit(data, True)

    with pytest.raises(HowlerValueError):
        data = {
            "howler": {
                "analytic": "test",
                "comment": {
                    "id": "test",
                    "value": "test",
                    "user": "test",
                    "reactions.thumbs-up": ["test"],
                    "sneaky": "key",
                },
            }
        }

        hit_service.convert_hit(data, True)
