from datetime import datetime, timedelta
from unittest import mock

from mock import MagicMock

from howler.config import config
from howler.services import jwt_service

time = datetime.now() + timedelta(seconds=10)


def test_config_service_config_on_oauth():
    config.auth.oauth.strict_apikeys = True
    config.auth.max_apikey_duration_amount = 180
    config.auth.max_apikey_duration_unit = "days"

    jwt_service.decode = MagicMock(return_value={"exp": time.timestamp()})

    request = MagicMock()

    request.headers = {"Authorization": "Bearer ."}

    with mock.patch("howler.services.config_service.request", request):
        from howler.services import config_service

        result = config_service.get_configuration(user=None, discovery_url=None)

        assert result["configuration"]["auth"]["max_apikey_duration_amount"] <= 10
        assert result["configuration"]["auth"]["max_apikey_duration_unit"] <= "seconds"
