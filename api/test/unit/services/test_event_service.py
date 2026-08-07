from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerTypeError, HowlerValueError, ResourceExists
from howler.odm.base import UTC_TZ
from howler.odm.models.event import Event
from howler.services import event_service

# ========================
# convert_event tests
# ========================

SAMPLE_EVENT_DATA: dict[str, Any] = {
    "howler.hash": "abcdef1234567890",
    "howler.data": ["raw_data_entry"],
}


def test_convert_event_basic():
    """Test basic conversion of a dictionary to an Event ODM object."""
    data: dict[str, Any] = {
        "howler.data": ["some raw data"],
    }

    result, warnings = event_service.convert_event(data, unique=False)

    assert isinstance(result, Event)
    assert result.howler.hash is not None
    assert result.howler.id is not None
    assert result.event is not None
    assert result.event.created is not None


def test_convert_event_hash_deterministic():
    """Test that the same data produces the same hash."""
    data1: dict[str, Any] = {"howler.data": ["entry one"]}
    data2: dict[str, Any] = {"howler.data": ["entry one"]}

    result1, _ = event_service.convert_event(data1, unique=False)
    result2, _ = event_service.convert_event(data2, unique=False)

    assert result1.howler.hash == result2.howler.hash


def test_convert_event_hash_differs_on_different_data():
    """Test that different data produces different hashes."""
    data1: dict[str, Any] = {"howler.data": ["entry one"]}
    data2: dict[str, Any] = {"howler.data": ["entry two"]}

    result1, _ = event_service.convert_event(data1, unique=False)
    result2, _ = event_service.convert_event(data2, unique=False)

    assert result1.howler.hash != result2.howler.hash


def test_convert_event_preserves_explicit_hash():
    """Test that an explicitly provided hash is kept."""
    explicit_hash = "deadbeef12345678"
    data: dict[str, Any] = {
        "howler.hash": explicit_hash,
        "howler.data": ["some data"],
    }

    result, _ = event_service.convert_event(data, unique=False)

    assert result.howler.hash == explicit_hash


def test_convert_event_assigns_random_id():
    """Test that each conversion assigns a unique random ID."""
    data: dict[str, Any] = {"howler.data": ["data"]}

    result1, _ = event_service.convert_event({**data}, unique=False)
    result2, _ = event_service.convert_event({**data}, unique=False)

    assert result1.howler.id != result2.howler.id


def test_convert_event_data_serialization():
    """Test that non-string data entries are JSON-serialized."""
    data: dict[str, Any] = {
        "howler.data": [{"key": "value"}, "plain string"],
    }

    result, _ = event_service.convert_event(data, unique=False)

    assert '{"key": "value"}' in result.howler.data
    assert "plain string" in result.howler.data


def test_convert_event_event_defaults():
    """Test that event fields get default values when not provided."""
    data: dict[str, Any] = {"howler.data": ["data"]}

    result, _ = event_service.convert_event(data, unique=False)

    assert result.event is not None
    assert result.event.id == result.howler.id
    assert result.event.created is not None


def test_convert_event_event_preserves_created():
    """Test that an explicitly provided event.created is preserved."""
    create_date = datetime.now(tz=UTC_TZ).replace(year=2500)
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "event": {"created": create_date},
    }

    result, _ = event_service.convert_event(data, unique=False)

    assert result.event.created == create_date


def test_convert_event_event_without_created():
    """Test that event without created gets a default created value."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "event": {"kind": "alert"},
    }

    result, _ = event_service.convert_event(data, unique=False)

    assert result.event.created is not None


def test_convert_event_extra_values_raises():
    """Test that extra values raise HowlerValueError when ignore_extra_values=False."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "nonexistent_field": "bad_value",
    }

    with pytest.raises(HowlerValueError, match="invalid parameters"):
        event_service.convert_event(data, unique=False, ignore_extra_values=False)


def test_convert_event_extra_values_ignored():
    """Test that extra values produce warnings when ignore_extra_values=True."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "nonexistent_field": "bad_value",
    }

    result, warnings = event_service.convert_event(data, unique=False, ignore_extra_values=True)

    assert isinstance(result, Event)
    assert any("nonexistent_field" in w for w in warnings)


def test_convert_event_invalid_type():
    """Test that invalid data types raise HowlerTypeError."""
    data: dict[str, Any] = {
        "howler.hash": 12345,  # should be a string
    }

    with pytest.raises((HowlerTypeError, HowlerValueError)):
        event_service.convert_event(data, unique=False)


@patch("howler.services.event_service.exists", return_value="event")
def test_convert_event_unique_already_exists(mock_exists):
    """Test that unique=True raises ResourceExists when event already exists."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
    }

    with pytest.raises(ResourceExists, match="already exists"):
        event_service.convert_event(data, unique=True)

    mock_exists.assert_called_once()


@patch("howler.services.event_service.exists", return_value=None)
def test_convert_event_unique_does_not_exist(mock_exists):
    """Test that unique=True succeeds when event does not exist."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
    }

    result, _ = event_service.convert_event(data, unique=True)

    assert isinstance(result, Event)
    mock_exists.assert_called_once()


@patch("howler.services.event_service.exists", return_value=False)
def test_convert_event_deprecated_fields(mock_exists):
    """Test that deprecated fields generate warnings."""
    data: dict[str, Any] = {
        **SAMPLE_EVENT_DATA,
        "howler.score": 0.5,
    }

    ff = Event.flat_fields()
    with patch.object(Event, "flat_fields") as mock_flat_fields:
        ff["howler.score"] = MagicMock(deprecated=True)
        mock_flat_fields.return_value = ff

        _, warnings = event_service.convert_event(data, unique=True, ignore_extra_values=True)

        assert any("howler.score" in w and "deprecated" in w for w in warnings)


# ========================
# create_event tests
# ========================


@patch("howler.services.event_service.exists", return_value="event")
def test_create_event_already_exists(mock_exists):
    """Test that create_event raises ResourceExists if event exists and skip_exists=False."""
    event = Event(SAMPLE_EVENT_DATA)

    with pytest.raises(ResourceExists, match="already exists"):
        event_service.create_event("some_id", event)


@patch("howler.services.event_service.datastore")
@patch("howler.services.event_service.exists", return_value=None)
def test_create_event_success(mock_exists, mock_datastore):
    """Test successful creation of an event."""
    mock_event_collection = MagicMock()
    mock_datastore.return_value.event = mock_event_collection
    mock_event_collection.save.return_value = True

    event = Event(SAMPLE_EVENT_DATA)

    result = event_service.create_event("test_id", event)

    assert result is True
    mock_event_collection.save.assert_called_once_with("test_id", event, refresh=None)


@patch("howler.services.event_service.datastore")
@patch("howler.services.event_service.exists", return_value=None)
def test_create_event_with_user(mock_exists, mock_datastore):
    """Test that create_event adds a creation log when user is provided."""
    mock_event_collection = MagicMock()
    mock_datastore.return_value.event = mock_event_collection
    mock_event_collection.save.return_value = True

    event = Event(SAMPLE_EVENT_DATA)

    event_service.create_event("test_id", event, user="test_user")

    # Verify log was added
    assert len(event.howler.log) == 1
    assert event.howler.log[0].user == "test_user"
    assert event.howler.log[0].explanation == "Created event"

    mock_event_collection.save.assert_called_once_with("test_id", event, refresh=None)


@patch("howler.services.event_service.datastore")
@patch("howler.services.event_service.exists", return_value=None)
def test_create_event_without_user(mock_exists, mock_datastore):
    """Test that create_event does not add a log when user is not provided."""
    mock_event_collection = MagicMock()
    mock_datastore.return_value.event = mock_event_collection
    mock_event_collection.save.return_value = True

    event = Event(SAMPLE_EVENT_DATA)

    event_service.create_event("test_id", event)

    # Verify no log was added
    assert len(event.howler.log) == 0

    mock_event_collection.save.assert_called_once_with("test_id", event, refresh=None)


@patch("howler.services.event_service.datastore")
@patch("howler.services.event_service.exists", return_value=None)
def test_create_event_skip_exists(mock_exists, mock_datastore):
    """Test that create_event skips the existence check when skip_exists=True."""
    mock_event_collection = MagicMock()
    mock_datastore.return_value.event = mock_event_collection
    mock_event_collection.save.return_value = True

    event = Event(SAMPLE_EVENT_DATA)

    event_service.create_event("test_id", event, skip_exists=True)

    # exists should NOT have been called
    mock_exists.assert_not_called()
    mock_event_collection.save.assert_called_once()


@patch("howler.services.event_service.datastore")
@patch("howler.services.event_service.exists", return_value=None)
def test_create_event_increments_counter(mock_exists, mock_datastore):
    """Test that create_event increments the CREATED_EVENTS counter."""
    mock_event_collection = MagicMock()
    mock_datastore.return_value.event = mock_event_collection
    mock_event_collection.save.return_value = True

    event = Event(SAMPLE_EVENT_DATA)

    before = event_service.CREATED_EVENTS._value.get()
    event_service.create_event("test_id", event)
    after = event_service.CREATED_EVENTS._value.get()

    assert after == before + 1


@patch("howler.services.event_service.datastore")
def test_create_events_uses_event_collection(mock_datastore):
    """Bulk event ingestion checks and writes the event collection."""
    storage = mock_datastore.return_value
    storage.event.exists.return_value = False
    storage.event.bulk.return_value = True
    bulk_plan = storage.event.get_bulk_plan.return_value
    event = Event(SAMPLE_EVENT_DATA)

    result = event_service.create_events([event], user="test_user", refresh="wait_for")

    assert result is True
    storage.event.exists.assert_called_once_with(event.howler.id)
    bulk_plan.add_insert_operation.assert_called_once_with(event.howler.id, event)
    storage.event.bulk.assert_called_once_with(bulk_plan, refresh="wait_for")
    storage.hit.exists.assert_not_called()
    storage.hit.bulk.assert_not_called()
    assert event.howler.log[0].user == "test_user"
