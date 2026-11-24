import pytest

from howler.common.exceptions import HowlerValueError
from howler.odm.models.notification import Notification


def notification_data(**overrides):
    data = {
        "notification_id": "0b6f8c1e-6f1c-4c55-9d3e-3c7d6a1f2b9a",
        "resource_type": "analytic",
        "recipient": "owner",
        "resource_id": "d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "sender": "analyst",
        "resource_name": "Suspicious Login",
        "message": "analyst commented on your analytic Suspicious Login.",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "url_path",
    [
        "/analytics/d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "/",
        "/hits?query=howler.id:*",
        "/analytics/abc#comments",
    ],
)
def test_notification_accepts_relative_url_paths(url_path):
    assert Notification(notification_data(url_path=url_path)).url_path == url_path


def test_notification_url_path_is_optional():
    assert Notification(notification_data()).url_path is None


@pytest.mark.parametrize(
    "url_path",
    [
        "https://example.com/analytics/abc",
        "http://localhost:3000/analytics",
        "//example.com/analytics",
        "/\\example.com/analytics",
        "javascript:alert(1)",
        "example.com/analytics",
        "analytics/abc",
        "/analytics/a b",
    ],
)
def test_notification_rejects_non_path_urls(url_path):
    with pytest.raises(HowlerValueError):
        Notification(notification_data(url_path=url_path))
