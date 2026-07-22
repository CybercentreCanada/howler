from unittest.mock import patch

from howler.config import config
from howler.helper.discover import DISCO_CACHE, get_apps_list


def test_get_apps_list_returns_empty_when_discovery_disabled():
    """When enable_eureka_discovery is False, get_apps_list should return [] immediately."""
    original = config.discovery.enabled
    original_url = config.discovery.url
    try:
        config.discovery.enabled = False
        config.discovery.url = "https://discover.example.com/eureka/apps"
        result = get_apps_list()
        assert result == []
    finally:
        config.discovery.enabled = original
        config.discovery.url = original_url


def test_get_apps_list_returns_empty_when_discovery_url_is_none():
    """When discovery_url is None, get_apps_list should return [] regardless of config."""
    original = config.discovery.enabled
    original_url = config.discovery.url
    try:
        config.discovery.enabled = True
        config.discovery.url = None
        result = get_apps_list()
        assert result == []
    finally:
        config.discovery.enabled = original
        config.discovery.url = original_url


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_calls_discovery_when_enabled(mock_get):
    """When enable_eureka_discovery is True and a URL is provided, discovery is attempted."""
    original = config.discovery.enabled
    original_url = config.discovery.url
    try:
        config.discovery.enabled = True
        config.discovery.url = "https://discover.test-enabled.com/eureka/apps"
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {"applications": {"application": []}}

        DISCO_CACHE.pop(config.discovery.url, None)

        # Use a unique URL to avoid cache hits
        result = get_apps_list()
        assert result == []
        mock_get.assert_called_once()
    finally:
        config.discovery.enabled = original
        DISCO_CACHE.pop(config.discovery.url, None)
        config.discovery.url = original_url


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_includes_non_howler_apps(mock_get):
    """Apps whose hostname does not contain 'howler' are included in the result."""
    original = config.discovery.enabled
    original_url = config.discovery.url
    url = "https://discover.test-include.com/eureka/apps"
    original_cache = DISCO_CACHE.pop(url, None)
    try:
        config.discovery.enabled = True
        config.discovery.url = url
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

        result = get_apps_list()

        assert len(result) == 1
        assert result[0]["name"] == "MY-APP"
        assert result[0]["route"] == "https://myapp.example.com"
    finally:
        config.discovery.enabled = original
        DISCO_CACHE.pop(url, None)
        config.discovery.url = original_url
        if original_cache is not None:
            DISCO_CACHE[url] = original_cache


@patch("howler.helper.discover.requests.get")
def test_get_apps_list_excludes_howler_apps(mock_get):
    """Apps whose hostname contains 'howler' are excluded from the result."""
    original = config.discovery.enabled
    original_url = config.discovery.url
    url = "https://discover.test-exclude.com/eureka/apps"
    original_cache = DISCO_CACHE.pop(url, None)
    try:
        config.discovery.enabled = True
        config.discovery.url = url
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

        result = get_apps_list()

        assert result == []
    finally:
        config.discovery.enabled = original
        DISCO_CACHE.pop(url, None)
        config.discovery.url = original_url
        if original_cache is not None:
            DISCO_CACHE[url] = original_cache
