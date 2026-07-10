from unittest.mock import patch

from howler.config import config
from howler.helper.discover import DISCO_CACHE, get_apps_list


def test_get_apps_list_returns_empty_when_discovery_disabled():
    """When enable_eureka_discovery is False, get_apps_list should return [] immediately."""
    original = config.discovery.enabled
    try:
        config.discovery.enabled = False
        result = get_apps_list(discovery_url="https://discover.example.com/eureka/apps")
        assert result == []
    finally:
        config.discovery.enabled = original


def test_get_apps_list_returns_empty_when_discovery_url_is_none():
    """When discovery_url is None, get_apps_list should return [] regardless of config."""
    original = config.discovery.enabled
    try:
        config.discovery.enabled = True
        result = get_apps_list(discovery_url=None)
        assert result == []
    finally:
        config.discovery.enabled = original


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_calls_discovery_when_enabled(mock_get):
    """When enable_eureka_discovery is True and a URL is provided, discovery is attempted."""
    original = config.discovery.enabled
    try:
        config.discovery.enabled = True
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {"applications": {"application": []}}

        # Use a unique URL to avoid cache hits
        result = get_apps_list(discovery_url="https://discover.test-enabled.com/eureka/apps")
        assert result == []
        mock_get.assert_called_once()
    finally:
        config.discovery.enabled = original


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_includes_non_howler_apps(mock_get):
    """Apps whose hostname does not contain 'howler' are included in the result."""
    original = config.discovery.enabled
    url = "https://discover.test-include.com/eureka/apps"
    original_cache = DISCO_CACHE.pop(url, None)
    try:
        config.discovery.enabled = True
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {
            "applications": {
                "application": [
                    {
                        "name": "MY-APP",
                        "instance": [
                            {
                                "hostName": "https://myapp.example.com",
                                "metadata": {
                                    "alternateText": "My App",
                                    "imageDark": "/img/dark.png",
                                    "imageLight": "/img/light.png",
                                    "classification": "TLP:WHITE",
                                },
                            }
                        ],
                    }
                ]
            }
        }

        result = get_apps_list(discovery_url=url)

        assert len(result) == 1
        assert result[0]["name"] == "MY-APP"
        assert result[0]["route"] == "https://myapp.example.com"
    finally:
        config.discovery.enabled = original
        DISCO_CACHE.pop(url, None)
        if original_cache is not None:
            DISCO_CACHE[url] = original_cache


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_excludes_howler_apps(mock_get):
    """Apps whose hostname contains 'howler' are excluded from the result."""
    original = config.discovery.enabled
    url = "https://discover.test-exclude.com/eureka/apps"
    original_cache = DISCO_CACHE.pop(url, None)
    try:
        config.discovery.enabled = True
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {
            "applications": {
                "application": [
                    {
                        "name": "HOWLER-API",
                        "instance": [
                            {
                                "hostName": "https://howler.internal.example.com",
                                "metadata": {
                                    "alternateText": "Howler",
                                    "imageDark": "/img/dark.png",
                                    "imageLight": "/img/light.png",
                                    "classification": "TLP:WHITE",
                                },
                            }
                        ],
                    }
                ]
            }
        }

        result = get_apps_list(discovery_url=url)

        assert result == []
    finally:
        config.discovery.enabled = original
        DISCO_CACHE.pop(url, None)
        if original_cache is not None:
            DISCO_CACHE[url] = original_cache
