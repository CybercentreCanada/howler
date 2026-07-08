"""Tests for the schedule service (blob fetch + Redis cache)."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestFetchSchedules:
    """Tests for the fetch_schedules_from_blob function."""

    def test_fetch_handover_schedules_success(self):
        """Test fetching schedules successfully."""
        from tsx_user_status.services.schedule_service import (
            fetch_schedules_from_blob,
        )

        mock_config = MagicMock()
        mock_config.schedules_account = "testaccount"
        mock_config.schedules_key = "testkey"
        mock_config.schedules_container = "testcontainer"
        mock_config.schedules_blob = "testblob"

        mock_schedules = {"MS": ["Day 7-15"], "CBCS": ["Day 9-17"]}

        with patch("tsx_user_status.services.schedule_service.BlobServiceClient") as mock_blob_service:
            mock_blob_client = MagicMock()
            mock_blob_client.download_blob.return_value.readall.return_value = json.dumps(mock_schedules).encode(
                "utf-8"
            )
            mock_service = mock_blob_service.from_connection_string.return_value
            mock_service.get_blob_client.return_value = mock_blob_client

            result = fetch_schedules_from_blob(mock_config)

        assert result == mock_schedules

    def test_fetch_handover_schedules_with_schedule_wrapper(self):
        """Test fetching schedules when wrapped in 'schedule' key."""
        from tsx_user_status.services.schedule_service import (
            fetch_schedules_from_blob,
        )

        mock_config = MagicMock()
        mock_config.schedules_account = "testaccount"
        mock_config.schedules_key = "testkey"
        mock_config.schedules_container = "testcontainer"
        mock_config.schedules_blob = "testblob"

        wrapped_schedules = {"schedule": {"MS": ["Day 7-15"]}}

        with patch("tsx_user_status.services.schedule_service.BlobServiceClient") as mock_blob_service:
            mock_blob_client = MagicMock()
            mock_blob_client.download_blob.return_value.readall.return_value = json.dumps(wrapped_schedules).encode(
                "utf-8"
            )
            mock_service = mock_blob_service.from_connection_string.return_value
            mock_service.get_blob_client.return_value = mock_blob_client

            result = fetch_schedules_from_blob(mock_config)

        assert result == {"MS": ["Day 7-15"]}

    def test_fetch_handover_schedules_invalid_json(self):
        """Test fetching schedules fails with invalid JSON."""
        from tsx_user_status.services.schedule_service import (
            fetch_schedules_from_blob,
        )

        mock_config = MagicMock()
        mock_config.schedules_account = "testaccount"
        mock_config.schedules_key = "testkey"
        mock_config.schedules_container = "testcontainer"
        mock_config.schedules_blob = "testblob"

        with patch("tsx_user_status.services.schedule_service.BlobServiceClient") as mock_blob_service:
            mock_blob_client = MagicMock()
            mock_blob_client.download_blob.return_value.readall.return_value = b"not valid json"
            mock_service = mock_blob_service.from_connection_string.return_value
            mock_service.get_blob_client.return_value = mock_blob_client

            with pytest.raises(json.JSONDecodeError):
                fetch_schedules_from_blob(mock_config)


class TestGetSchedulesCache:
    """Tests for the cached `get_schedules` accessor."""

    @pytest.fixture
    def mock_config(self):
        """Return a mock plugin config with caching enabled."""
        cfg = MagicMock()
        cfg.schedules_account = "testaccount"
        cfg.schedules_key = "testkey"
        cfg.schedules_container = "testcontainer"
        cfg.schedules_blob = "testblob"
        cfg.schedules_cache_key = "tsx_user_status:schedules:test"
        cfg.schedules_cache_ttl = 3600
        return cfg

    def test_cache_miss_then_hit(self, mock_config):
        """First call fetches from blob; second call serves from cache."""
        from tsx_user_status.services import schedule_service

        mock_schedules = {"MS": ["Day 7-15"], "CBCS": ["Day 9-17"]}
        cache_store: dict[str, str] = {}

        def fake_get(key):
            return cache_store.get(key)

        def fake_set(key, value, ex=None):
            cache_store[key] = value
            return True

        fake_redis = MagicMock()
        fake_redis.get.side_effect = fake_get
        fake_redis.set.side_effect = fake_set

        with (
            patch.object(schedule_service, "redis", fake_redis),
            patch.object(
                schedule_service,
                "fetch_schedules_from_blob",
                return_value=mock_schedules,
            ) as mock_fetch,
        ):
            first = schedule_service.get_schedules(mock_config)
            second = schedule_service.get_schedules(mock_config)

        assert first == mock_schedules
        assert second == mock_schedules
        # Blob should only have been hit once — second call served from cache.
        assert mock_fetch.call_count == 1
        # And the cache write should have included the TTL from config.
        fake_redis.set.assert_called_with(
            mock_config.schedules_cache_key,
            json.dumps(mock_schedules),
            ex=mock_config.schedules_cache_ttl,
        )

    def test_cache_hit_does_not_rewrite(self, mock_config):
        """A cache hit must not call ``redis.set`` again (no TTL refresh)."""
        from tsx_user_status.services import schedule_service

        mock_schedules = {"MS": ["Day 7-15"]}

        fake_redis = MagicMock()
        fake_redis.get.return_value = json.dumps(mock_schedules)

        with (
            patch.object(schedule_service, "redis", fake_redis),
            patch.object(
                schedule_service,
                "fetch_schedules_from_blob",
            ) as mock_fetch,
        ):
            result = schedule_service.get_schedules(mock_config)

        assert result == mock_schedules
        mock_fetch.assert_not_called()
        fake_redis.set.assert_not_called()

    def test_corrupted_cache_falls_back_to_blob(self, mock_config):
        """A corrupted JSON payload in Redis is treated as a cache miss."""
        from tsx_user_status.services import schedule_service

        mock_schedules = {"MS": ["Day 7-15"]}

        fake_redis = MagicMock()
        fake_redis.get.return_value = b"not valid json"

        with (
            patch.object(schedule_service, "redis", fake_redis),
            patch.object(
                schedule_service,
                "fetch_schedules_from_blob",
                return_value=mock_schedules,
            ) as mock_fetch,
        ):
            result = schedule_service.get_schedules(mock_config)

        assert result == mock_schedules
        mock_fetch.assert_called_once()
        # Cache should have been overwritten with the fresh payload.
        fake_redis.set.assert_called_once()

    def test_redis_get_failure_falls_back_to_blob(self, mock_config):
        """If ``redis.get`` raises a Redis error, we still serve schedules from blob."""
        import redis as redis_lib

        from tsx_user_status.services import schedule_service

        mock_schedules = {"MS": ["Day 7-15"]}

        fake_redis = MagicMock()
        fake_redis.get.side_effect = redis_lib.ConnectionError("redis unreachable")

        with (
            patch.object(schedule_service, "redis", fake_redis),
            patch.object(
                schedule_service,
                "fetch_schedules_from_blob",
                return_value=mock_schedules,
            ) as mock_fetch,
        ):
            result = schedule_service.get_schedules(mock_config)

        assert result == mock_schedules
        mock_fetch.assert_called_once()

    def test_redis_set_failure_still_returns_schedules(self, mock_config):
        """A ``redis.set`` failure must not break the response.

        The blob was successfully fetched, so callers should receive the fresh
        schedules even though writing to the cache failed.
        """
        import redis as redis_lib

        from tsx_user_status.services import schedule_service

        mock_schedules = {"MS": ["Day 7-15"]}

        fake_redis = MagicMock()
        fake_redis.get.return_value = None  # cache miss
        fake_redis.set.side_effect = redis_lib.ConnectionError("redis unreachable")

        with (
            patch.object(schedule_service, "redis", fake_redis),
            patch.object(
                schedule_service,
                "fetch_schedules_from_blob",
                return_value=mock_schedules,
            ) as mock_fetch,
        ):
            result = schedule_service.get_schedules(mock_config)

        assert result == mock_schedules
        mock_fetch.assert_called_once()
        fake_redis.set.assert_called_once()
