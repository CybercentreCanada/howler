import os
import pytest

from howler_client import get_client

UI_HOST = os.getenv("UI_HOST", "http://localhost:5000")

original_skip = pytest.skip

# Check if we are in an unattended build environment where skips won't be noticed
IN_CI_ENVIRONMENT = any(
    indicator in os.environ
    for indicator in ["CI", "BITBUCKET_BUILD_NUMBER", "AGENT_JOBSTATUS"]
)


def skip_or_fail(message):
    """Skip or fail the current test, based on the environment"""
    if IN_CI_ENVIRONMENT:
        pytest.fail(message)
    else:
        original_skip(message)


@pytest.fixture(scope="module")
def client():
    return get_client(UI_HOST, verify=False, retries=1)
