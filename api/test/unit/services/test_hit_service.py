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


@patch("howler.services.hit_service.datastore")
@patch("howler.services.hit_service.__match_metadata")
def test_augment_metadata_single_hit_with_template(mock_match_metadata, mock_datastore):
    """Test augment_metadata with a single hit and template metadata."""
    # Setup test data
    test_hit = {"howler": {"analytic": "test_analytic", "detection": "test_detection", "id": "test_hit_1"}}

    test_user = {"uname": "test_user"}

    # Mock template search response
    mock_template_collection = MagicMock()
    mock_datastore.return_value.template = mock_template_collection
    mock_template_collection.search.return_value = {
        "items": [{"analytic": "test_analytic", "type": "global", "template_data": "some_template"}]
    }

    # Mock the match metadata function
    expected_template = {"analytic": "test_analytic", "type": "global"}
    mock_match_metadata.return_value = expected_template

    # Test the function
    hit_service.augment_metadata(test_hit, ["template"], test_user)

    # Verify the template search was called with correct parameters
    mock_template_collection.search.assert_called_once_with(
        'analytic:("test_analytic") AND (type:global OR owner:test_user)', as_obj=False
    )

    # Verify the hit was augmented with template metadata
    assert "__template" in test_hit
    assert test_hit["__template"] == expected_template

    # Verify match_metadata was called correctly
    mock_match_metadata.assert_called_once()


@patch("howler.services.hit_service.datastore")
@patch("howler.services.hit_service.__match_metadata")
def test_augment_metadata_multiple_hits_with_overview(mock_match_metadata, mock_datastore):
    """Test augment_metadata with multiple hits and overview metadata."""
    # Setup test data
    test_hits = [
        {"howler": {"analytic": "analytic_1", "detection": "detection_1", "id": "hit_1"}},
        {"howler": {"analytic": "analytic_2", "detection": "detection_2", "id": "hit_2"}},
    ]

    test_user = {"uname": "test_user"}

    # Mock overview search response
    mock_overview_collection = MagicMock()
    mock_datastore.return_value.overview = mock_overview_collection
    mock_overview_collection.search.return_value = {
        "items": [
            {"analytic": "analytic_1", "overview_data": "overview_1"},
            {"analytic": "analytic_2", "overview_data": "overview_2"},
        ]
    }

    # Mock the match metadata function to return different values
    mock_match_metadata.side_effect = [
        {"analytic": "analytic_1", "overview": "overview_1"},
        {"analytic": "analytic_2", "overview": "overview_2"},
    ]

    # Test the function
    hit_service.augment_metadata(test_hits, ["overview"], test_user)

    # Verify the overview search was called with correct parameters
    try:
        mock_overview_collection.search.assert_called_once_with('analytic:("analytic_1" OR "analytic_2")', as_obj=False)
    except AssertionError:
        mock_overview_collection.search.assert_called_once_with('analytic:("analytic_2" OR "analytic_1")', as_obj=False)

    # Verify both hits were augmented with overview metadata
    assert "__overview" in test_hits[0]
    assert "__overview" in test_hits[1]
    assert test_hits[0]["__overview"]["analytic"] == "analytic_1"
    assert test_hits[1]["__overview"]["analytic"] == "analytic_2"


@patch("howler.services.hit_service.datastore")
@patch("howler.services.hit_service.dossier_service.get_matching_dossiers")
def test_augment_metadata_with_dossiers(mock_get_matching_dossiers, mock_datastore):
    """Test augment_metadata with dossiers metadata."""
    # Setup test data
    test_hit = {"howler": {"analytic": "security_analytic", "detection": "threat_detection", "id": "security_hit_1"}}

    test_user = {"uname": "security_analyst"}

    # Mock dossier search response
    mock_dossier_collection = MagicMock()
    mock_datastore.return_value.dossier = mock_dossier_collection
    mock_dossier_collection.search.return_value = {
        "items": [
            {
                "dossier_id": "dossier_1",
                "title": "Security Investigation",
                "query": "howler.analytic:security_analytic",
            },
            {"dossier_id": "dossier_2", "title": "General Threats", "query": None},
        ]
    }

    # Mock the get_matching_dossiers function
    expected_dossiers = [
        {"dossier_id": "dossier_1", "title": "Security Investigation"},
        {"dossier_id": "dossier_2", "title": "General Threats"},
    ]
    mock_get_matching_dossiers.return_value = expected_dossiers

    # Test the function
    hit_service.augment_metadata(test_hit, ["dossiers"], test_user)

    # Verify the dossier search was called
    mock_dossier_collection.search.assert_called_once_with("dossier_id:*", as_obj=False, rows=1000)

    # Verify the hit was augmented with dossier metadata
    assert "__dossiers" in test_hit
    assert test_hit["__dossiers"] == expected_dossiers

    # Verify get_matching_dossiers was called correctly
    mock_get_matching_dossiers.assert_called_once()


@patch("howler.services.hit_service.datastore")
@patch("howler.services.hit_service.__match_metadata")
@patch("howler.services.hit_service.dossier_service.get_matching_dossiers")
def test_augment_metadata_all_metadata_types(mock_get_matching_dossiers, mock_match_metadata, mock_datastore):
    """Test augment_metadata with all metadata types: template, overview, and dossiers."""
    # Setup test data
    test_hit = {
        "howler": {
            "analytic": "comprehensive_analytic",
            "detection": "comprehensive_detection",
            "id": "comprehensive_hit",
        }
    }

    test_user = {"uname": "comprehensive_user"}

    # Mock datastore collections
    mock_template_collection = MagicMock()
    mock_overview_collection = MagicMock()
    mock_dossier_collection = MagicMock()

    mock_datastore.return_value.template = mock_template_collection
    mock_datastore.return_value.overview = mock_overview_collection
    mock_datastore.return_value.dossier = mock_dossier_collection

    # Mock search responses
    mock_template_collection.search.return_value = {"items": [{"type": "global"}]}
    mock_overview_collection.search.return_value = {"items": [{"analytic": "comprehensive_analytic"}]}
    mock_dossier_collection.search.return_value = {"items": [{"dossier_id": "test_dossier"}]}

    # Mock return values
    mock_match_metadata.side_effect = [
        {"template": "test_template"},  # For template call
        {"overview": "test_overview"},  # For overview call
    ]
    mock_get_matching_dossiers.return_value = [{"dossier": "test_dossier"}]

    # Test the function with all metadata types
    hit_service.augment_metadata(test_hit, ["template", "overview", "dossiers"], test_user)

    # Verify all metadata was added
    assert "__template" in test_hit
    assert "__overview" in test_hit
    assert "__dossiers" in test_hit

    # Verify all datastore searches were called
    mock_template_collection.search.assert_called_once()
    mock_overview_collection.search.assert_called_once()
    mock_dossier_collection.search.assert_called_once()

    # Verify match_metadata was called twice (for template and overview)
    assert mock_match_metadata.call_count == 2

    # Verify get_matching_dossiers was called once
    mock_get_matching_dossiers.assert_called_once()


def test_augment_metadata_empty_metadata_list():
    """Test augment_metadata with empty metadata list (should do nothing)."""
    test_hit = {"howler": {"analytic": "test_analytic", "id": "test_hit"}}

    test_user = {"uname": "test_user"}
    original_hit = test_hit.copy()

    # Test with empty metadata list
    hit_service.augment_metadata(test_hit, [], test_user)

    # Verify no metadata was added
    assert test_hit == original_hit
    assert "__template" not in test_hit
    assert "__overview" not in test_hit
    assert "__dossiers" not in test_hit


@patch("howler.services.hit_service.datastore")
@patch("howler.services.hit_service.__match_metadata")
def test_augment_metadata_no_matching_templates(mock_match_metadata, mock_datastore):
    """Test augment_metadata when no templates match."""
    test_hit = {"howler": {"analytic": "no_match_analytic", "id": "test_hit"}}

    test_user = {"uname": "test_user"}

    # Mock template search with no results
    mock_template_collection = MagicMock()
    mock_datastore.return_value.template = mock_template_collection
    mock_template_collection.search.return_value = {"items": []}

    # Mock match_metadata to return None (no match)
    mock_match_metadata.return_value = None

    # Test the function
    hit_service.augment_metadata(test_hit, ["template"], test_user)

    # Verify the hit was augmented with None
    assert "__template" in test_hit
    assert test_hit["__template"] is None


@patch("howler.services.hit_service.datastore")
@patch("howler.services.hit_service.__match_metadata")
def test_augment_metadata_duplicate_analytics(mock_match_metadata, mock_datastore):
    """Test augment_metadata with multiple hits having the same analytic."""
    test_hits = [
        {"howler": {"analytic": "same_analytic", "detection": "detection_1", "id": "hit_1"}},
        {"howler": {"analytic": "same_analytic", "detection": "detection_2", "id": "hit_2"}},
    ]

    test_user = {"uname": "test_user"}

    # Mock template search response
    mock_template_collection = MagicMock()
    mock_datastore.return_value.template = mock_template_collection
    mock_template_collection.search.return_value = {"items": [{"analytic": "same_analytic", "type": "global"}]}

    # Mock match_metadata
    mock_match_metadata.return_value = {"analytic": "same_analytic", "type": "global"}

    # Test the function
    hit_service.augment_metadata(test_hits, ["template"], test_user)

    # Verify search was called with deduplicated analytics
    expected_query = 'analytic:("same_analytic") AND (type:global OR owner:test_user)'
    mock_template_collection.search.assert_called_once_with(expected_query, as_obj=False)

    # Verify both hits received the same template
    assert test_hits[0]["__template"] == test_hits[1]["__template"]


@patch("howler.services.hit_service.datastore")
def test_augment_metadata_user_permission_filtering(mock_datastore):
    """Test that template search includes proper user permission filtering."""
    test_hit = {"howler": {"analytic": "permission_test_analytic", "id": "permission_hit"}}

    test_user = {"uname": "specific_user"}

    # Mock template search
    mock_template_collection = MagicMock()
    mock_datastore.return_value.template = mock_template_collection
    mock_template_collection.search.return_value = {"items": []}

    # Test the function
    hit_service.augment_metadata(test_hit, ["template"], test_user)

    # Verify the search query includes user permission filtering
    expected_query = 'analytic:("permission_test_analytic") AND (type:global OR owner:specific_user)'
    mock_template_collection.search.assert_called_once_with(expected_query, as_obj=False)


def test_augment_metadata_single_hit_as_dict():
    """Test augment_metadata properly handles single hit passed as dictionary."""
    test_hit = {"howler": {"analytic": "single_hit_analytic", "id": "single_hit"}}

    test_user = {"uname": "test_user"}

    with patch("howler.services.hit_service.datastore") as mock_datastore:
        # Mock collections to avoid actual datastore calls
        mock_datastore.return_value.template = MagicMock()
        mock_datastore.return_value.template.search.return_value = {"items": []}

        with patch("howler.services.hit_service.__match_metadata", return_value=None):
            # Test with single hit (not in a list)
            hit_service.augment_metadata(test_hit, ["template"], test_user)

            # Verify the hit was processed (metadata field added)
            assert "__template" in test_hit


def test__compare_metadata_priority():
    # personal > readonly > global
    personal = {"type": "personal"}
    readonly = {"type": "readonly"}
    _global = {"type": "global"}
    # a > b > c
    assert hit_service.__compare_metadata(personal, readonly) < 0
    assert hit_service.__compare_metadata(readonly, _global) < 0
    assert hit_service.__compare_metadata(personal, _global) < 0
    assert hit_service.__compare_metadata(readonly, personal) > 0
    assert hit_service.__compare_metadata(_global, readonly) > 0
    assert hit_service.__compare_metadata(_global, personal) > 0
    # Same type, detection present
    global_detection = {"type": "global", "detection": "foo"}
    assert hit_service.__compare_metadata(global_detection, _global) < 0
    assert hit_service.__compare_metadata(_global, global_detection) > 0
    # Same type, both have detection
    f = {"type": "global", "detection": "foo"}
    g = {"type": "global", "detection": "bar"}
    assert hit_service.__compare_metadata(f, g) == 0


def test__match_metadata_basic():
    hit = {"howler": {"analytic": "A", "detection": "D"}}
    candidates = [
        {"analytic": "A", "detection": "D", "type": "global"},
        {"analytic": "A", "detection": "X", "type": "readonly"},
        {"analytic": "B", "detection": "D", "type": "personal"},
    ]
    result = hit_service.__match_metadata(candidates, hit)
    assert result == {"analytic": "A", "detection": "D", "type": "global"}


def test__match_metadata_case_insensitive():
    hit = {"howler": {"analytic": "aNALYTIC", "detection": "dEtEctION"}}
    candidates = [
        {"analytic": "analytic", "detection": "detection", "type": "global"},
        {"analytic": "analytic", "detection": "other", "type": "readonly"},
    ]
    result = hit_service.__match_metadata(candidates, hit)
    assert result == {"analytic": "analytic", "detection": "detection", "type": "global"}


def test__match_metadata_no_detection_in_candidate():
    hit = {"howler": {"analytic": "A", "detection": "D"}}
    candidates = [
        {"analytic": "A", "type": "global"},
        {"analytic": "A", "detection": "D", "type": "readonly"},
    ]
    result = hit_service.__match_metadata(candidates, hit)
    assert result == {"analytic": "A", "detection": "D", "type": "readonly"}


def test__match_metadata_no_detection_in_hit():
    hit = {"howler": {"analytic": "A"}}
    candidates = [
        {"analytic": "A", "detection": "D", "type": "global"},
        {"analytic": "A", "type": "readonly"},
    ]
    result = hit_service.__match_metadata(candidates, hit)
    assert result == {"analytic": "A", "type": "readonly"}


def test__match_metadata_no_match():
    hit = {"howler": {"analytic": "A", "detection": "D"}}
    candidates = [
        {"analytic": "B", "detection": "D", "type": "global"},
        {"analytic": "A", "detection": "X", "type": "readonly"},
    ]
    result = hit_service.__match_metadata(candidates, hit)
    assert result is None
