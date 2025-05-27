from howler.config import config
from howler.security.utils import get_disco_url


def test_get_disco_url():
    result = get_disco_url("https://howler.example.com")

    assert result == "https://discover.example.com/eureka/apps"


def test_valid_conversion():
    url = "howler.example.com/extra/path?query=string"

    converted_url = get_disco_url(url)

    assert converted_url == "https://discover.example.com/eureka/apps"


def test_local_url():
    url = "http://localhost:3000/search?span=date.range.1.week&sort=event.created+desc"

    converted_url = get_disco_url(url)

    assert converted_url == config.ui.discover_url
