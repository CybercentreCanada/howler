"""Integration tests for UserStatusService against real Redis."""

import pytest

from tsx_user_status.services.user_status_service import _status_key

TEST_USER = "integration_test_user@test.com"


@pytest.fixture(autouse=True)
def _cleanup(status_service):
    """Clean up test keys before and after each test."""
    status_service.redis.delete(_status_key(TEST_USER))
    yield
    status_service.redis.delete(_status_key(TEST_USER))


def test_get_status_returns_default_when_no_key(status_service):
    """No key in Redis should return None."""
    assert status_service.get_status(TEST_USER) is None


@pytest.mark.parametrize("status", ["available", "busy", "unavailable", "away"])
def test_set_and_get_status(status_service, status):
    """Setting a valid status should be retrievable."""
    status_service.set_status(TEST_USER, status)
    assert status_service.get_status(TEST_USER) == status


def test_set_none_deletes_key(status_service):
    """Setting status to None should delete the key, returning None on next read."""
    status_service.set_status(TEST_USER, "available")
    assert status_service.get_status(TEST_USER) == "available"

    status_service.set_status(TEST_USER, None)
    assert status_service.get_status(TEST_USER) is None


@pytest.mark.parametrize("status", ["1", "99", "invalid"])
def test_set_invalid_status_raises(status_service, status):
    """Setting an unrecognized status should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid status"):
        status_service.set_status(TEST_USER, status)


# Note: get_all_statuses tests require real users in the datastore.
# These are covered in unit tests with mocked datastore.
