from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mergedeep.mergedeep import merge

from howler.common.exceptions import ForbiddenException, NotFoundException
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_dossier
from howler.odm.models.dossier import Dossier
from howler.odm.random_data import create_dossiers, wipe_dossiers
from howler.security import InvalidDataException
from howler.services import dossier_service


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_dossiers(ds, num_dossiers=10)

        yield ds
    finally:
        wipe_dossiers(ds)


def test_exists(datastore: HowlerDatastore):
    existing_dossier_id = datastore.dossier.search("dossier_id:*", as_obj=True)["items"][0].dossier_id

    assert dossier_service.exists(existing_dossier_id)


def test_get_dossier(datastore: HowlerDatastore):
    existing_dossier_id = datastore.dossier.search("dossier_id:*", as_obj=True)["items"][0].dossier_id

    assert dossier_service.get_dossier(existing_dossier_id, as_odm=True).dossier_id == existing_dossier_id


def test_create_dossier(datastore: HowlerDatastore):
    users = datastore.user.search("uname:*")["items"]

    result = dossier_service.create_dossier(generate_useful_dossier(users).as_primitives(), username="admin")

    assert len(result.leads) > 0
    assert len(result.leads) < 4


def test_create_dossier_fails(datastore: HowlerDatastore):
    users = datastore.user.search("uname:*")["items"]

    example = generate_useful_dossier(users).as_primitives()

    with pytest.raises(InvalidDataException):
        dossier_service.create_dossier([], username="admin")

    with pytest.raises(InvalidDataException):
        bad_example = merge({}, example)
        del bad_example["title"]
        dossier_service.create_dossier(bad_example, username="admin")

    with pytest.raises(InvalidDataException):
        bad_example = merge({}, example)
        bad_example["query"] = "adjigvq34b895734no787888907089%^&%^&*%^&*%^&*%^&*kmlml,;;l,.[]"
        dossier_service.create_dossier(bad_example, username="admin")


def test_update_dossier_fails(datastore: HowlerDatastore):
    user = datastore.user.search("uname:admin")["items"][0]

    with pytest.raises(NotFoundException):
        dossier_service.update_dossier("potatopotatopotato", {"owner": "test"}, user).owner == "test"

    existing_dossier: Dossier = datastore.dossier.search("type:personal", as_obj=True)["items"][0]

    with pytest.raises(ForbiddenException):
        other_user = datastore.user.search(f"-uname:{existing_dossier.owner} AND -type:admin")["items"][0]
        dossier_service.update_dossier(existing_dossier.dossier_id, {"owner": other_user.uname}, other_user)

    existing_dossier = datastore.dossier.search("type:global", as_obj=True)["items"][0]
    with pytest.raises(ForbiddenException):
        other_user = datastore.user.search(f"-uname:{existing_dossier.owner} AND -type:admin")["items"][0]
        dossier_service.update_dossier(existing_dossier.dossier_id, {"owner": other_user.uname}, other_user)

    user = datastore.user.search(f"uname:{existing_dossier.owner}")["items"][0]
    with pytest.raises(InvalidDataException):
        dossier_service.update_dossier(
            existing_dossier.dossier_id, {"query": "sdklfjnasdvrtvybnuiseybuniosertv897890['['[/]['/]"}, user
        )

    with pytest.raises(InvalidDataException) as exc:
        dossier_service.update_dossier(existing_dossier.dossier_id, {"test": "TEST"}, user)

    assert exc.match("can be updated")


def test_update_dossier(datastore: HowlerDatastore):
    user = datastore.user.search("uname:admin")["items"][0]
    existing_dossier_id = datastore.dossier.search("type:global", as_obj=True)["items"][0].dossier_id

    assert dossier_service.update_dossier(existing_dossier_id, {"owner": "test"}, user).owner == "test"


def test_pivot_with_duplicates(datastore: HowlerDatastore):
    users = datastore.user.search("uname:*")["items"]

    dossier_odm = generate_useful_dossier(users)
    dossier_odm.pivots[0].mappings.append(dossier_odm.pivots[0].mappings[0])

    dossier = dossier_odm.as_primitives()

    with pytest.raises(InvalidDataException):
        dossier_service.create_dossier(dossier, username="admin")


def test_get_matching_dossiers_with_provided_dossiers(datastore: HowlerDatastore):
    """Test get_matching_dossiers when dossiers are explicitly provided."""
    # Create test hit data
    test_hit = {
        "howler": {"analytic": "test_analytic", "detection": "test_detection", "id": "test_hit_123"},
        "event": {"action": "network_connection", "dataset": "security_logs"},
    }

    # Create test dossiers with different query scenarios
    test_dossiers: list[dict[str, Any]] = [
        {
            "dossier_id": "dossier_1",
            "title": "Catch-all Dossier",
            "query": None,  # Should match all hits
            "type": "global",
        },
        {
            "dossier_id": "dossier_2",
            "title": "Specific Analytic Dossier",
            "query": "howler.analytic:test_analytic",  # Should match our test hit
            "type": "personal",
        },
        {
            "dossier_id": "dossier_3",
            "title": "Different Analytic Dossier",
            "query": "howler.analytic:different_analytic",  # Should NOT match
            "type": "global",
        },
        {
            "dossier_id": "dossier_4",
            "title": "Network Events Dossier",
            "query": "event.action:network_connection",  # Should match our test hit
            "type": "personal",
        },
        {
            "dossier_id": "dossier_5",
            "title": "Missing Query Dossier",
            # No query field - should match all hits
            "type": "global",
        },
    ]

    # Test the function
    matching_dossiers = dossier_service.get_matching_dossiers(test_hit, test_dossiers)

    # Verify results
    assert len(matching_dossiers) == 4  # Should match dossiers 1, 2, 4, and 5

    matching_ids = [d["dossier_id"] for d in matching_dossiers]
    assert "dossier_1" in matching_ids  # Catch-all (None query)
    assert "dossier_2" in matching_ids  # Matching analytic query
    assert "dossier_3" not in matching_ids  # Non-matching query
    assert "dossier_4" in matching_ids  # Matching event action query
    assert "dossier_5" in matching_ids  # Missing query field


def test_get_matching_dossiers_without_provided_dossiers(datastore: HowlerDatastore):
    """Test get_matching_dossiers when no dossiers are provided (fetches from datastore)."""
    # Create test hit data
    test_hit = {"howler": {"analytic": "existing_analytic", "detection": "existing_detection", "id": "test_hit_456"}}

    # Test without providing dossiers - should fetch from datastore
    matching_dossiers = dossier_service.get_matching_dossiers(test_hit)

    # Verify it returns a list (exact content depends on datastore state)
    assert isinstance(matching_dossiers, list)

    # All returned items should be dictionaries with expected structure
    for dossier in matching_dossiers:
        assert isinstance(dossier, dict)
        assert "dossier_id" in dossier


def test_get_matching_dossiers_empty_dossier_list(datastore: HowlerDatastore):
    """Test get_matching_dossiers with an empty dossier list."""
    test_hit = {"howler": {"analytic": "test_analytic", "id": "test_hit_789"}}

    # Test with empty dossier list
    matching_dossiers = dossier_service.get_matching_dossiers(test_hit, [])

    # Should return empty list
    assert matching_dossiers == []


def test_get_matching_dossiers_complex_queries(datastore: HowlerDatastore):
    """Test get_matching_dossiers with complex Lucene queries."""
    # Create test hit with multiple fields
    test_hit = {
        "howler": {"analytic": "malware_detection", "detection": "trojan_horse", "id": "complex_hit_001", "score": 85},
        "event": {"action": "file_creation", "outcome": "success", "category": ["malware"]},
        "source": {"ip": "192.168.1.100"},
    }

    # Test dossiers with complex queries
    complex_dossiers = [
        {
            "dossier_id": "complex_1",
            "title": "High Score Malware",
            "query": "howler.analytic:malware_detection AND howler.score:[80 TO *]",
            "type": "global",
        },
        {
            "dossier_id": "complex_2",
            "title": "File Operations",
            "query": "event.action:file_* AND event.outcome:success",
            "type": "personal",
        },
        {
            "dossier_id": "complex_3",
            "title": "Internal Network",
            "query": "source.ip:[192.168.0.0 TO 192.168.255.255]",
            "type": "global",
        },
        {
            "dossier_id": "complex_4",
            "title": "Non-matching Query",
            "query": "howler.analytic:phishing AND event.action:email_send",
            "type": "personal",
        },
    ]

    matching_dossiers = dossier_service.get_matching_dossiers(test_hit, complex_dossiers)

    # Verify complex query matching
    matching_ids = [d["dossier_id"] for d in matching_dossiers]
    assert "complex_1" in matching_ids  # Should match high score malware query
    assert "complex_2" in matching_ids  # Should match file operations query
    assert "complex_3" in matching_ids  # Should match internal network query
    assert "complex_4" not in matching_ids  # Should not match phishing query


def test_get_matching_dossiers_with_malformed_data(datastore: HowlerDatastore):
    """Test get_matching_dossiers with edge cases and malformed data."""
    # Test hit with minimal data
    minimal_hit = {"howler": {"id": "minimal_hit"}}

    # Test dossiers with various edge cases
    edge_case_dossiers: list[dict[str, Any]] = [
        {"dossier_id": "edge_1", "title": "Null Query Dossier", "query": None, "type": "global"},
        {"dossier_id": "edge_2", "title": "Empty String Query", "query": "", "type": "personal"},
        {
            "dossier_id": "edge_3",
            "title": "Missing Query Field",
            "type": "global",
            # No query field at all
        },
        {"dossier_id": "edge_4", "title": "Whitespace Query", "query": "   ", "type": "personal"},
    ]

    matching_dossiers = dossier_service.get_matching_dossiers(minimal_hit, edge_case_dossiers)

    # Dossiers with None, missing, or empty queries should match
    matching_ids = [d["dossier_id"] for d in matching_dossiers]
    assert "edge_1" in matching_ids  # None query should match
    assert "edge_3" in matching_ids  # Missing query should match

    assert "edge_2" not in matching_ids  # Empty string query should not match
    assert "edge_4" not in matching_ids  # Whitespace query should not match


def test_get_matching_dossiers_query_validation_scenarios(datastore: HowlerDatastore):
    """Test various query validation scenarios with get_matching_dossiers."""
    test_hit = {
        "howler": {"analytic": "test_validation", "detection": "test_rule", "id": "validation_hit"},
        "tags": ["suspicious", "network"],
    }

    validation_dossiers = [
        {
            "dossier_id": "valid_1",
            "title": "Simple Field Match",
            "query": "howler.analytic:test_validation",
            "type": "global",
        },
        {"dossier_id": "valid_2", "title": "Wildcard Query", "query": "howler.analytic:test_*", "type": "personal"},
        {"dossier_id": "valid_3", "title": "Array Field Query", "query": "tags:suspicious", "type": "global"},
        {
            "dossier_id": "valid_4",
            "title": "Boolean AND Query",
            "query": "howler.analytic:test_validation AND tags:network",
            "type": "personal",
        },
        {"dossier_id": "valid_5", "title": "Non-existent Field", "query": "nonexistent.field:value", "type": "global"},
    ]

    matching_dossiers = dossier_service.get_matching_dossiers(test_hit, validation_dossiers)

    # Verify that valid queries are processed correctly
    matching_ids = [d["dossier_id"] for d in matching_dossiers]
    assert "valid_1" in matching_ids  # Exact field match
    assert "valid_2" in matching_ids  # Wildcard match
    assert "valid_3" in matching_ids  # Array field match
    assert "valid_4" in matching_ids  # Boolean AND match

    assert "valid_5" not in matching_ids  # Invalid field query


def test_get_matching_dossiers_with_lucene_service_mock(datastore: HowlerDatastore):
    """Test get_matching_dossiers with mocked lucene_service for controlled testing."""
    test_hit = {"howler": {"analytic": "mock_test_analytic", "id": "mock_test_hit"}}

    test_dossiers: list[dict[str, Any]] = [
        {"dossier_id": "mock_1", "title": "Always Match Dossier", "query": "always_match_query", "type": "global"},
        {"dossier_id": "mock_2", "title": "Never Match Dossier", "query": "never_match_query", "type": "personal"},
        {"dossier_id": "mock_3", "title": "No Query Dossier", "query": None, "type": "global"},
    ]

    # Mock the lucene_service.match function to control return values
    with patch("howler.services.dossier_service.lucene_service.match") as mock_match:
        # Configure mock to return True for "always_match_query" and False for "never_match_query"
        def mock_match_side_effect(query, hit):
            if query == "always_match_query":
                return True
            elif query == "never_match_query":
                return False
            else:
                return False

        mock_match.side_effect = mock_match_side_effect

        # Test the function
        matching_dossiers = dossier_service.get_matching_dossiers(test_hit, test_dossiers)

        # Verify results
        matching_ids = [d["dossier_id"] for d in matching_dossiers]
        assert "mock_1" in matching_ids  # Should match due to mocked True return
        assert "mock_2" not in matching_ids  # Should not match due to mocked False return
        assert "mock_3" in matching_ids  # Should match due to None query

        # Verify that lucene_service.match was called correctly
        assert mock_match.call_count == 2  # Should be called for mock_1 and mock_2
        mock_match.assert_any_call("always_match_query", test_hit)
        mock_match.assert_any_call("never_match_query", test_hit)


@patch("howler.services.dossier_service.datastore")
def test_get_matching_dossiers_datastore_integration(mock_datastore, datastore: HowlerDatastore):
    """Test get_matching_dossiers when it fetches dossiers from datastore."""
    test_hit = {"howler": {"analytic": "datastore_test", "id": "datastore_hit"}}

    # Mock datastore response
    mock_dossier_collection = MagicMock()
    mock_datastore.return_value.dossier = mock_dossier_collection

    # Configure mock search response
    mock_search_response = {
        "items": [
            {"dossier_id": "ds_1", "title": "Datastore Dossier 1", "query": None, "type": "global"},
            {
                "dossier_id": "ds_2",
                "title": "Datastore Dossier 2",
                "query": "howler.analytic:datastore_test",
                "type": "personal",
            },
        ]
    }
    mock_dossier_collection.search.return_value = mock_search_response

    # Mock lucene_service.match to return True for our test query
    with patch("howler.services.dossier_service.lucene_service.match", return_value=True):
        # Test the function with no dossiers provided (should fetch from datastore)
        matching_dossiers = dossier_service.get_matching_dossiers(test_hit)

        # Verify datastore was called correctly
        mock_dossier_collection.search.assert_called_once_with("dossier_id:*", as_obj=False, rows=1000)

        # Verify results
        assert len(matching_dossiers) == 2
        matching_ids = [d["dossier_id"] for d in matching_dossiers]
        assert "ds_1" in matching_ids
        assert "ds_2" in matching_ids
