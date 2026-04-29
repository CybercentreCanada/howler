from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerTypeError, HowlerValueError, ResourceExists
from howler.odm.base import UTC_TZ
from howler.odm.models.observable import Observable
from howler.services import observable_service

# ========================
# convert_observable tests
# ========================

SAMPLE_OBSERVABLE_DATA: dict[str, Any] = {
    "howler.hash": "abcdef1234567890",
    "howler.data": ["raw_data_entry"],
}


def test_convert_observable_basic():
    """Test basic conversion of a dictionary to an Observable ODM object."""
    data: dict[str, Any] = {
        "howler.data": ["some raw data"],
    }

    result, warnings = observable_service.convert_observable(data, unique=False)

    assert isinstance(result, Observable)
    assert result.howler.hash is not None
    assert result.howler.id is not None
    assert result.event is not None
    assert result.event.created is not None


def test_convert_observable_hash_deterministic():
    """Test that the same data produces the same hash."""
    data1: dict[str, Any] = {"howler.data": ["entry one"]}
    data2: dict[str, Any] = {"howler.data": ["entry one"]}

    result1, _ = observable_service.convert_observable(data1, unique=False)
    result2, _ = observable_service.convert_observable(data2, unique=False)

    assert result1.howler.hash == result2.howler.hash


def test_convert_observable_hash_differs_on_different_data():
    """Test that different data produces different hashes."""
    data1: dict[str, Any] = {"howler.data": ["entry one"]}
    data2: dict[str, Any] = {"howler.data": ["entry two"]}

    result1, _ = observable_service.convert_observable(data1, unique=False)
    result2, _ = observable_service.convert_observable(data2, unique=False)

    assert result1.howler.hash != result2.howler.hash


def test_convert_observable_preserves_explicit_hash():
    """Test that an explicitly provided hash is kept."""
    explicit_hash = "deadbeef12345678"
    data: dict[str, Any] = {
        "howler.hash": explicit_hash,
        "howler.data": ["some data"],
    }

    result, _ = observable_service.convert_observable(data, unique=False)

    assert result.howler.hash == explicit_hash


def test_convert_observable_assigns_random_id():
    """Test that each conversion assigns a unique random ID."""
    data: dict[str, Any] = {"howler.data": ["data"]}

    result1, _ = observable_service.convert_observable({**data}, unique=False)
    result2, _ = observable_service.convert_observable({**data}, unique=False)

    assert result1.howler.id != result2.howler.id


def test_convert_observable_data_serialization():
    """Test that non-string data entries are JSON-serialized."""
    data: dict[str, Any] = {
        "howler.data": [{"key": "value"}, "plain string"],
    }

    result, _ = observable_service.convert_observable(data, unique=False)

    assert '{"key": "value"}' in result.howler.data
    assert "plain string" in result.howler.data


def test_convert_observable_event_defaults():
    """Test that event fields get default values when not provided."""
    data: dict[str, Any] = {"howler.data": ["data"]}

    result, _ = observable_service.convert_observable(data, unique=False)

    assert result.event is not None
    assert result.event.id == result.howler.id
    assert result.event.created is not None


def test_convert_observable_event_preserves_created():
    """Test that an explicitly provided event.created is preserved."""
    create_date = datetime.now(tz=UTC_TZ).replace(year=2500)
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "event": {"created": create_date},
    }

    result, _ = observable_service.convert_observable(data, unique=False)

    assert result.event.created == create_date


def test_convert_observable_event_without_created():
    """Test that event without created gets a default created value."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "event": {"kind": "alert"},
    }

    result, _ = observable_service.convert_observable(data, unique=False)

    assert result.event.created is not None


def test_convert_observable_extra_values_raises():
    """Test that extra values raise HowlerValueError when ignore_extra_values=False."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "nonexistent_field": "bad_value",
    }

    with pytest.raises(HowlerValueError, match="invalid parameters"):
        observable_service.convert_observable(data, unique=False, ignore_extra_values=False)


def test_convert_observable_extra_values_ignored():
    """Test that extra values produce warnings when ignore_extra_values=True."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
        "nonexistent_field": "bad_value",
    }

    result, warnings = observable_service.convert_observable(data, unique=False, ignore_extra_values=True)

    assert isinstance(result, Observable)
    assert any("nonexistent_field" in w for w in warnings)


def test_convert_observable_invalid_type():
    """Test that invalid data types raise HowlerTypeError."""
    data: dict[str, Any] = {
        "howler.hash": 12345,  # should be a string
    }

    with pytest.raises((HowlerTypeError, HowlerValueError)):
        observable_service.convert_observable(data, unique=False)


@patch("howler.services.observable_service.exists", return_value="observable")
def test_convert_observable_unique_already_exists(mock_exists):
    """Test that unique=True raises ResourceExists when observable already exists."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
    }

    with pytest.raises(ResourceExists, match="already exists"):
        observable_service.convert_observable(data, unique=True)

    mock_exists.assert_called_once()


@patch("howler.services.observable_service.exists", return_value=None)
def test_convert_observable_unique_does_not_exist(mock_exists):
    """Test that unique=True succeeds when observable does not exist."""
    data: dict[str, Any] = {
        "howler.data": ["data"],
    }

    result, _ = observable_service.convert_observable(data, unique=True)

    assert isinstance(result, Observable)
    mock_exists.assert_called_once()


@patch("howler.services.observable_service.exists", return_value=False)
def test_convert_observable_deprecated_fields(mock_exists):
    """Test that deprecated fields generate warnings."""
    data: dict[str, Any] = {
        **SAMPLE_OBSERVABLE_DATA,
        "howler.score": 0.5,
    }

    ff = Observable.flat_fields()
    with patch.object(Observable, "flat_fields") as mock_flat_fields:
        ff["howler.score"] = MagicMock(deprecated=True)
        mock_flat_fields.return_value = ff

        _, warnings = observable_service.convert_observable(data, unique=True, ignore_extra_values=True)

        assert any("howler.score" in w and "deprecated" in w for w in warnings)


# ========================
# create_observable tests
# ========================


@patch("howler.services.observable_service.exists", return_value="observable")
def test_create_observable_already_exists(mock_exists):
    """Test that create_observable raises ResourceExists if observable exists and skip_exists=False."""
    observable = Observable(SAMPLE_OBSERVABLE_DATA)

    with pytest.raises(ResourceExists, match="already exists"):
        observable_service.create_observable("some_id", observable)


@patch("howler.services.observable_service.datastore")
@patch("howler.services.observable_service.exists", return_value=None)
def test_create_observable_success(mock_exists, mock_datastore):
    """Test successful creation of an observable."""
    mock_observable_collection = MagicMock()
    mock_datastore.return_value.observable = mock_observable_collection
    mock_observable_collection.save.return_value = True

    observable = Observable(SAMPLE_OBSERVABLE_DATA)

    result = observable_service.create_observable("test_id", observable)

    assert result is True
    mock_observable_collection.save.assert_called_once_with("test_id", observable)


@patch("howler.services.observable_service.datastore")
@patch("howler.services.observable_service.exists", return_value=None)
def test_create_observable_with_user(mock_exists, mock_datastore):
    """Test that create_observable adds a creation log when user is provided."""
    mock_observable_collection = MagicMock()
    mock_datastore.return_value.observable = mock_observable_collection
    mock_observable_collection.save.return_value = True

    observable = Observable(SAMPLE_OBSERVABLE_DATA)

    observable_service.create_observable("test_id", observable, user="test_user")

    # Verify log was added
    assert len(observable.howler.log) == 1
    assert observable.howler.log[0].user == "test_user"
    assert observable.howler.log[0].explanation == "Created observable"

    mock_observable_collection.save.assert_called_once_with("test_id", observable)


@patch("howler.services.observable_service.datastore")
@patch("howler.services.observable_service.exists", return_value=None)
def test_create_observable_without_user(mock_exists, mock_datastore):
    """Test that create_observable does not add a log when user is not provided."""
    mock_observable_collection = MagicMock()
    mock_datastore.return_value.observable = mock_observable_collection
    mock_observable_collection.save.return_value = True

    observable = Observable(SAMPLE_OBSERVABLE_DATA)

    observable_service.create_observable("test_id", observable)

    # Verify no log was added
    assert len(observable.howler.log) == 0

    mock_observable_collection.save.assert_called_once_with("test_id", observable)


@patch("howler.services.observable_service.datastore")
@patch("howler.services.observable_service.exists", return_value=None)
def test_create_observable_skip_exists(mock_exists, mock_datastore):
    """Test that create_observable skips the existence check when skip_exists=True."""
    mock_observable_collection = MagicMock()
    mock_datastore.return_value.observable = mock_observable_collection
    mock_observable_collection.save.return_value = True

    observable = Observable(SAMPLE_OBSERVABLE_DATA)

    observable_service.create_observable("test_id", observable, skip_exists=True)

    # exists should NOT have been called
    mock_exists.assert_not_called()
    mock_observable_collection.save.assert_called_once()


@patch("howler.services.observable_service.datastore")
@patch("howler.services.observable_service.exists", return_value=None)
def test_create_observable_increments_counter(mock_exists, mock_datastore):
    """Test that create_observable increments the CREATED_OBSERVABLES counter."""
    mock_observable_collection = MagicMock()
    mock_datastore.return_value.observable = mock_observable_collection
    mock_observable_collection.save.return_value = True

    observable = Observable(SAMPLE_OBSERVABLE_DATA)

    before = observable_service.CREATED_OBSERVABLES._value.get()
    observable_service.create_observable("test_id", observable)
    after = observable_service.CREATED_OBSERVABLES._value.get()

    assert after == before + 1
