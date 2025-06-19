from datetime import datetime
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerValueError, NotFoundException, ResourceExists
from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmUpdateOperation
from howler.helper.hit import HitStatusTransition
from howler.helper.workflow import Workflow
from howler.odm.base import UTC_TZ
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj
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
                "sneaky": "key",
            }
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
                },
                "sneaky": "key",
            }
        }

        hit_service.convert_hit(data, True)


# A basic hit dictionary for testing
SAMPLE_HIT_DATA = {
    "howler.hash": "1234567890abcdef",
    "howler.analytic": "Test Analytic",
    "howler.detection": "Test Detection",
    "howler.data": {"foo": "bar"},
    "event.kind": "alert",
}


def test_modifies_prop():
    """Test the _modifies_prop helper function."""
    # Test case 1: Property is modified
    operations = [OdmUpdateOperation(ESCollection.UPDATE_SET, "howler.status", "new_status")]
    assert hit_service._modifies_prop("howler.status", operations) is True

    # Test case 2: Property is not modified
    operations = [OdmUpdateOperation(ESCollection.UPDATE_SET, "howler.assignment", "new_user")]
    assert hit_service._modifies_prop("howler.status", operations) is False

    # Test case 3: Empty operations list
    operations = []
    assert hit_service._modifies_prop("howler.status", operations) is False


@patch("howler.services.hit_service.does_hit_exist", return_value=False)
def test_convert_hit_warnings(mock_does_hit_exist):
    """Test that convert_hit generates warnings for extra and deprecated fields."""
    data = {
        **SAMPLE_HIT_DATA,
        "extra_field": "some_value",
        "howler.is_hidden": True,  # Assuming this is a deprecated field for the test
    }

    # Mock the Hit model to have a deprecated field for testing purposes
    ff = Hit.flat_fields()
    with patch.object(Hit, "flat_fields") as mock_flat_fields:
        # We need to mock the return of flat_fields to include a deprecated field
        # for the purpose of this test.
        ff["howler.is_hidden"] = MagicMock(deprecated=True)
        mock_flat_fields.return_value = ff

        _, warnings = hit_service.convert_hit(data, unique=True, ignore_extra_values=True)

        mock_flat_fields.assert_called()

        assert "extra_field is not currently used by howler." in warnings
        assert "howler.is_hidden is deprecated." in warnings


@patch("howler.services.hit_service.get_hit", return_value=None)
def test_transition_hit_not_found(mock_get_hit):
    """Test transition_hit when the hit does not exist."""
    with pytest.raises(NotFoundException, match="Hit does not exist"):
        hit_service.transition_hit(
            "non_existent_id",
            HitStatusTransition.ASSIGN_TO_ME,
            user=User({"uname": "test_user", "name": "Test User", "password": "test_password"}),
        )


@patch("howler.services.hit_service.does_hit_exist", return_value=True)
def test_create_hit_already_exists(mock_does_hit_exist):
    """Test that create_hit raises ResourceExists if the hit exists and overwrite is False."""
    with pytest.raises(ResourceExists):
        hit_service.create_hit("some_id", Hit(SAMPLE_HIT_DATA), overwrite=False)


@patch("howler.services.hit_service._update_hit", return_value=(random_model_obj(cast(Any, Hit)), "version number"))
def test_update_hit_modifies_status(datastore_connection):
    """Test that update_hit raises an error when trying to modify the status directly."""
    with pytest.raises(HowlerValueError, match="Status of a Hit cannot be modified like other properties"):
        hit_service.update_hit(
            "some_id",
            [OdmUpdateOperation(ESCollection.UPDATE_SET, "howler.status", "some_status")],
        )
