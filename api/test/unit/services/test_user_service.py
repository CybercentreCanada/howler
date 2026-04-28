"""Unit tests for the access_control path in user_service.parse_user_data.

Specifically tests the three branches that govern whether add_access_control()
is called and the user is saved after OAuth profile sync:

  1. User data changed -> add_access_control + save
  2. User data unchanged, access_control missing -> add_access_control + save
  3. User data unchanged, access_control already present -> no save

The tests mock every collaborator (datastore, parse_profile, etc.) so no
running server or Elasticsearch is required.
"""

from unittest.mock import MagicMock, patch  # noqa: I001

from howler.services import user_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(uname="alice", email="alice@example.com") -> dict:
    return {
        "uname": uname,
        "email": email,
        "name": "Alice Example",
        "classification": "UNRESTRICTED",
        "type": ["user"],
        "groups": [],
        "password": "hashed",
        "access": True,
    }


def _make_existing_user(uname="alice", email="alice@example.com", **extra) -> dict:
    base = {
        "uname": uname,
        "email": email,
        "name": "Alice Example",
        "classification": "UNRESTRICTED",
        "type": ["user"],
        "groups": [],
        "password": "hashed",
    }
    base.update(extra)
    return base


def _mock_storage(existing_user: dict | None):
    """Build a mock datastore() return value that returns existing_user on user.search."""
    storage = MagicMock()
    if existing_user is not None:
        storage.user.search.return_value = {"items": [existing_user]}
    else:
        storage.user.search.return_value = {"items": []}
        storage.user.exists.return_value = False
    return storage


def _base_patches(storage, profile: dict, provider_config):
    """Return a dict of patch targets shared across all parse_user_data tests."""
    return {
        "howler.services.user_service.datastore": MagicMock(return_value=storage),
        "howler.services.user_service.parse_profile": MagicMock(return_value=profile),
        "howler.services.user_service.get_dynamic_classification": MagicMock(return_value=profile["classification"]),
        "howler.services.user_service.config": MagicMock(
            auth=MagicMock(oauth=MagicMock(providers={"test_provider": provider_config}))
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseUserDataAccessControl:
    """Tests for the access_control population branches inside parse_user_data."""

    def _provider_config(self, auto_sync=True, auto_create=True):
        cfg = MagicMock()
        cfg.auto_sync = auto_sync
        cfg.auto_create = auto_create
        cfg.required_groups = []
        cfg.user_get = None
        return cfg

    def _run(self, patches: dict, profile: dict, app_context: MagicMock):
        """Apply all patches and call parse_user_data with a minimal Flask app context."""
        with (
            patch("howler.services.user_service.datastore", patches["howler.services.user_service.datastore"]),
            patch("howler.services.user_service.parse_profile", patches["howler.services.user_service.parse_profile"]),
            patch(
                "howler.services.user_service.get_dynamic_classification",
                patches["howler.services.user_service.get_dynamic_classification"],
            ),
            patch("howler.services.user_service.config", patches["howler.services.user_service.config"]),
            patch("howler.services.user_service.current_app", app_context),
            patch("howler.services.user_service.request", MagicMock(args={})),
            patch(
                "howler.services.user_service.add_access_control",
                wraps=lambda u: u.update({"access_control": "mock_acl"}),
            ) as mock_aac,
            patch("howler.services.user_service.User", MagicMock()),
        ):
            user_service.parse_user_data({"sub": "abc"}, "test_provider", skip_setup=True)
            return mock_aac

    def _make_app(self):
        oauth_mock = MagicMock()
        oauth_mock.parse_id_token = None
        app = MagicMock()
        app.extensions = {
            "authlib.integrations.flask_client": MagicMock(create_client=MagicMock(return_value=oauth_mock))
        }
        return app

    def test_changed_user_triggers_add_access_control_and_save(self):
        """When existing user data differs from the OAuth profile, add_access_control and save are called."""
        existing = _make_existing_user(name="Old Name")  # name differs from profile
        profile = _make_profile()  # name = "Alice Example"
        storage = _mock_storage(existing)
        provider_config = self._provider_config()
        patches = _base_patches(storage, profile, provider_config)
        app = self._make_app()

        mock_aac = self._run(patches, profile, app)

        mock_aac.assert_called_once()
        storage.user.save.assert_called()

    def test_unchanged_user_without_access_control_triggers_save(self):
        """When existing user is up-to-date but lacks access_control, add_access_control and save are called."""
        profile = _make_profile()
        existing = _make_existing_user()  # identical to profile, no access_control key
        storage = _mock_storage(existing)
        provider_config = self._provider_config()
        patches = _base_patches(storage, profile, provider_config)
        app = self._make_app()

        mock_aac = self._run(patches, profile, app)

        mock_aac.assert_called_once()
        storage.user.save.assert_called()

    def test_unchanged_user_with_access_control_skips_save(self):
        """When existing user is up-to-date and has access_control, no save occurs."""
        profile = _make_profile()
        existing = _make_existing_user(access_control="(__access_grp1__:__EMPTY__) AND __access_lvl__:[0 TO 100]")
        storage = _mock_storage(existing)
        provider_config = self._provider_config()
        patches = _base_patches(storage, profile, provider_config)
        app = self._make_app()

        with (
            patch("howler.services.user_service.datastore", patches["howler.services.user_service.datastore"]),
            patch("howler.services.user_service.parse_profile", patches["howler.services.user_service.parse_profile"]),
            patch(
                "howler.services.user_service.get_dynamic_classification",
                patches["howler.services.user_service.get_dynamic_classification"],
            ),
            patch("howler.services.user_service.config", patches["howler.services.user_service.config"]),
            patch("howler.services.user_service.current_app", app),
            patch("howler.services.user_service.request", MagicMock(args={})),
            patch("howler.services.user_service.add_access_control") as mock_aac,
            patch("howler.services.user_service.User", MagicMock()),
        ):
            user_service.parse_user_data({"sub": "abc"}, "test_provider", skip_setup=True)

        mock_aac.assert_not_called()
        storage.user.save.assert_not_called()
