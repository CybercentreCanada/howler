from unittest.mock import patch

from howler.config import config
from howler.helper.discover import get_apps_list


def test_get_apps_list_returns_empty_when_discovery_disabled():
    """When enable_eureka_discovery is False, get_apps_list should return [] immediately."""
    original = config.core.enable_eureka_discovery
    try:
        config.core.enable_eureka_discovery = False
        result = get_apps_list(discovery_url="https://discover.example.com/eureka/apps")
        assert result == []
    finally:
        config.core.enable_eureka_discovery = original


def test_get_apps_list_returns_empty_when_discovery_url_is_none():
    """When discovery_url is None, get_apps_list should return [] regardless of config."""
    original = config.core.enable_eureka_discovery
    try:
        config.core.enable_eureka_discovery = True
        result = get_apps_list(discovery_url=None)
        assert result == []
    finally:
        config.core.enable_eureka_discovery = original


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_calls_discovery_when_enabled(mock_get):
    """When enable_eureka_discovery is True and a URL is provided, discovery is attempted."""
    original = config.core.enable_eureka_discovery
    try:
        config.core.enable_eureka_discovery = True
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {"applications": {"application": []}}

        # Use a unique URL to avoid cache hits
        result = get_apps_list(discovery_url="https://discover.test-enabled.com/eureka/apps")
        assert result == []
        mock_get.assert_called_once()
    finally:
        config.core.enable_eureka_discovery = original
