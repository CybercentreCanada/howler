"""Pytest configuration for tsx_user_tags unit tests.

Initializes Flask cache for testing the analytics providers that use
@cache.memoize decorator.
"""

import pytest
from flask import Flask
from howler.config import cache


@pytest.fixture(scope="module", autouse=True)
def flask_app():
    """Create Flask app with cache initialized for memoize decorator tests.

    The analytics providers use @cache.memoize which requires Flask app context.
    This fixture ensures the cache is properly initialized before any tests run.
    """
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test", TESTING=True)  # noqa: S106
    cache.init_app(app)

    with app.app_context():
        yield app
