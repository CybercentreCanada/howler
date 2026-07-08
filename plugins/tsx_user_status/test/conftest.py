"""Conftest for tsx_user_status tests."""

import dotenv
import pytest
from howler import config as howler_config

from tsx_user_status.services import UserStatusService

dotenv.load_dotenv()


@pytest.fixture(scope="module")
def status_service():
    """Provide a UserStatusService backed by the test Redis instance."""
    service = UserStatusService(howler_config.redis_persistent)
    yield service
