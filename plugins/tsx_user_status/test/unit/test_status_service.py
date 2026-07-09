"""Unit tests for UserStatusService."""

import importlib
import json
from collections.abc import Iterable
from unittest.mock import MagicMock, patch

import pytest
from redis import RedisError
from redis.cluster import RedisClusterException

import tsx_user_status.config as config_module
from tsx_user_status.constants import DEFAULT_STATUS, KEY_PREFIX, SHIFT_KEY_PREFIX, UserStatus
from tsx_user_status.exceptions import UserStatusReadError, UserStatusWriteError
from tsx_user_status.services import UNSET, UserStatusService
from tsx_user_status.services.user_status_service import _shift_key, _status_key


@pytest.fixture()
def mock_redis():
    """Provide a mocked Redis client."""
    return MagicMock()


@pytest.fixture()
def service(mock_redis):
    """Provide a UserStatusService with a mocked Redis client."""
    return UserStatusService(mock_redis)


def _decode_redis_key(key):
    """Decode a Redis key returned by the fake Redis clients."""
    return key.decode("utf-8") if isinstance(key, bytes) else str(key)


class FakeBulkPipeline:
    """Minimal pipeline implementation for bulk GET tests."""

    def __init__(self, values):
        self._values = values
        self._keys = []

    def get(self, key):
        self._keys.append(_decode_redis_key(key))
        return self

    def execute(self):
        return [self._values.get(key) for key in self._keys]


class FakeBulkRedis:
    """Redis fake that can simulate standalone and cluster bulk reads."""

    def __init__(self, values, *, cluster_mode):
        self._values = values
        self._cluster_mode = cluster_mode

    def scan_iter(self, pattern):
        prefix = pattern[:-1] if pattern.endswith("*") else pattern
        return iter(key.encode("utf-8") for key in self._values if key.startswith(prefix))

    def mget(self, keys, *extra_keys):
        decoded_keys = self._normalize_keys(keys, extra_keys)
        if self._cluster_mode:
            slots = {self._slot_for_key(key) for key in decoded_keys}
            if len(slots) > 1:
                raise RedisClusterException("MGET - all keys must map to the same key slot")
        return [self._values.get(key) for key in decoded_keys]

    def get(self, key):
        return self._values.get(_decode_redis_key(key))

    def pipeline(self, transaction=False):
        assert transaction is False
        return FakeBulkPipeline(self._values)

    @staticmethod
    def _normalize_keys(keys, extra_keys):
        raw_keys: Iterable[bytes | str]
        if extra_keys:
            raw_keys = (keys, *extra_keys)
        elif isinstance(keys, (list, tuple)):
            raw_keys = keys
        else:
            raw_keys = [keys]
        return [_decode_redis_key(key) for key in raw_keys]

    @staticmethod
    def _slot_for_key(key):
        slot_start = key.find("{")
        slot_end = key.find("}", slot_start + 1)
        if slot_start >= 0 and slot_end > slot_start:
            return key[slot_start + 1 : slot_end]
        return key


class TestGetStatus:
    """Tests for get_status."""

    def test_returns_default_when_key_missing(self, service, mock_redis):
        mock_redis.get.return_value = None
        assert service.get_status("user@test.com") is None

    def test_returns_stored_status_as_string(self, service, mock_redis):
        mock_redis.get.return_value = b"5"
        assert service.get_status("user@test.com") == "5"
        mock_redis.get.assert_called_once_with(_status_key("user@test.com"))

    def test_raises_on_redis_error(self, service, mock_redis):
        mock_redis.get.side_effect = RedisError("connection lost")
        with pytest.raises(UserStatusReadError):
            service.get_status("user@test.com")


class TestSetStatus:
    """Tests for set_status."""

    @pytest.mark.parametrize("status", ["available", "busy", "unavailable", "away"])
    def test_sets_valid_status(self, service, mock_redis, status):
        service.set_status("user@test.com", status)
        mock_redis.set.assert_called_once_with(_status_key("user@test.com"), status)

    def test_none_deletes_key(self, service, mock_redis):
        service.set_status("user@test.com", None)
        mock_redis.delete.assert_called_once_with(_status_key("user@test.com"))
        mock_redis.set.assert_not_called()

    @pytest.mark.parametrize("bad_status", ["", "   ", "1", 7, [], {}])
    def test_rejects_invalid_status(self, service, bad_status):
        with pytest.raises(ValueError, match="Invalid status"):
            service.set_status("user@test.com", bad_status)

    def test_raises_on_redis_error(self, service, mock_redis):
        mock_redis.set.side_effect = RedisError("connection lost")
        with pytest.raises(UserStatusWriteError):
            service.set_status("user@test.com", "available")


class TestGetShift:
    """Tests for get_shift."""

    def test_returns_none_when_key_missing(self, service, mock_redis):
        mock_redis.get.return_value = None
        assert service.get_shift("user@test.com") is None

    def test_returns_parsed_shift(self, service, mock_redis):
        mock_redis.get.return_value = json.dumps({"team": "MS", "schedule": "Day 7-15"}).encode()
        assert service.get_shift("user@test.com") == {"team": "MS", "schedule": "Day 7-15"}
        mock_redis.get.assert_called_once_with(_shift_key("user@test.com"))

    def test_maps_legacy_shift_field_to_schedule(self, service, mock_redis):
        mock_redis.get.return_value = json.dumps({"team": "MS", "shift": "Day 7-15"}).encode()
        assert service.get_shift("user@test.com") == {"team": "MS", "schedule": "Day 7-15"}

    def test_raises_on_corrupted_payload(self, service, mock_redis):
        mock_redis.get.return_value = b"not valid json"
        with pytest.raises(UserStatusReadError):
            service.get_shift("user@test.com")

    def test_raises_on_redis_error(self, service, mock_redis):
        mock_redis.get.side_effect = RedisError("down")
        with pytest.raises(UserStatusReadError):
            service.get_shift("user@test.com")


class TestSetShift:
    """Tests for set_shift."""

    def test_sets_valid_shift(self, service, mock_redis):
        service.set_shift("user@test.com", {"team": "MS", "schedule": "Day 7-15"})
        mock_redis.set.assert_called_once()
        assert mock_redis.set.call_args.args[0] == _shift_key("user@test.com")
        assert json.loads(mock_redis.set.call_args.args[1]) == {"team": "MS", "schedule": "Day 7-15"}

    def test_none_deletes_key(self, service, mock_redis):
        service.set_shift("user@test.com", None)
        mock_redis.delete.assert_called_once_with(_shift_key("user@test.com"))
        mock_redis.set.assert_not_called()

    @pytest.mark.parametrize(
        "bad",
        [
            "not a dict",
            123,
            {},
            {"team": "MS", "schedule": "Day 7-15", "extra": "x"},
            {"team": "", "shift": "Day 7-15"},
            {"team": "MS", "schedule": "   "},
            {"team": [], "schedule": "Day 7-15"},
        ],
    )
    def test_rejects_invalid_shapes(self, service, bad):
        with pytest.raises(ValueError):
            service.set_shift("user@test.com", bad)

    def test_raises_on_redis_error(self, service, mock_redis):
        mock_redis.set.side_effect = RedisError("down")
        with pytest.raises(UserStatusWriteError):
            service.set_shift("user@test.com", {"team": "MS", "schedule": "Day 7-15"})


class TestApplyPatch:
    """Tests for apply_patch (atomic, pipelined partial update)."""

    def test_no_fields_is_noop(self, service, mock_redis):
        service.apply_patch("user@test.com")
        mock_redis.pipeline.assert_not_called()

    def test_status_only_set(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        service.apply_patch("user@test.com", status="available")
        mock_redis.pipeline.assert_called_once_with(transaction=True)
        pipe.set.assert_called_once_with(_status_key("user@test.com"), "available")
        pipe.delete.assert_not_called()
        pipe.execute.assert_called_once()

    def test_status_null_clears(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        service.apply_patch("user@test.com", status=None)
        pipe.delete.assert_called_once_with(_status_key("user@test.com"))
        pipe.set.assert_not_called()
        pipe.execute.assert_called_once()

    def test_schedule_only_set(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        mock_redis.get.return_value = None
        with patch.object(
            service,
            "_load_valid_schedules",
            return_value={"MS": ["Day 7-15"]},
        ):
            service.apply_patch("user@test.com", schedule="Day 7-15")
        pipe.set.assert_called_once()
        assert pipe.set.call_args.args[0] == _shift_key("user@test.com")
        assert json.loads(pipe.set.call_args.args[1]) == {"schedule": "Day 7-15"}
        pipe.execute.assert_called_once()

    def test_team_only_set(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        mock_redis.get.return_value = None
        with patch.object(
            service,
            "_load_valid_schedules",
            return_value={"MS": ["Day 7-15"]},
        ):
            service.apply_patch("user@test.com", team="MS")
        pipe.set.assert_called_once()
        assert pipe.set.call_args.args[0] == _shift_key("user@test.com")
        assert json.loads(pipe.set.call_args.args[1]) == {"team": "MS"}
        pipe.execute.assert_called_once()

    def test_combined_clear_all(self, service, mock_redis):
        """Reset clears status, schedule, and team in one transaction."""
        pipe = mock_redis.pipeline.return_value
        mock_redis.get.return_value = json.dumps({"team": "MS", "schedule": "Day 7-15"}).encode()
        service.apply_patch("user@test.com", status=None, schedule=None, team=None)
        assert pipe.delete.call_count == 2
        pipe.delete.assert_any_call(_status_key("user@test.com"))
        pipe.delete.assert_any_call(_shift_key("user@test.com"))
        pipe.execute.assert_called_once()

    def test_combined_set_all(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        mock_redis.get.return_value = None
        with patch.object(
            service,
            "_load_valid_schedules",
            return_value={"CBCS": ["Night 22-06"]},
        ):
            service.apply_patch(
                "user@test.com",
                status="available",
                schedule="Night 22-06",
                team="CBCS",
            )
        pipe.set.assert_any_call(_status_key("user@test.com"), "available")
        shift_set_call = [c for c in pipe.set.call_args_list if c.args[0] == _shift_key("user@test.com")][0]
        assert json.loads(shift_set_call.args[1]) == {"team": "CBCS", "schedule": "Night 22-06"}
        pipe.execute.assert_called_once()

    def test_unset_leaves_fields_untouched(self, service, mock_redis):
        """Fields left as UNSET must not result in any pipe call for that key."""
        pipe = mock_redis.pipeline.return_value
        service.apply_patch("user@test.com", status="available", schedule=UNSET, team=UNSET)
        pipe.set.assert_called_once_with(_status_key("user@test.com"), "available")
        # No shift key touched
        for call in pipe.set.call_args_list + pipe.delete.call_args_list:
            assert SHIFT_KEY_PREFIX not in call.args[0]

    def test_schedule_update_preserves_existing_team(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        mock_redis.get.return_value = json.dumps({"team": "MS", "schedule": "Night 22-06"}).encode()

        with patch.object(
            service,
            "_load_valid_schedules",
            return_value={"MS": ["Night 22-06", "Day 7-15"]},
        ):
            service.apply_patch("user@test.com", schedule="Day 7-15")

        pipe.set.assert_called_once()
        assert pipe.set.call_args.args[0] == _shift_key("user@test.com")
        assert json.loads(pipe.set.call_args.args[1]) == {"team": "MS", "schedule": "Day 7-15"}
        pipe.execute.assert_called_once()

    def test_team_update_preserves_existing_schedule(self, service, mock_redis):
        pipe = mock_redis.pipeline.return_value
        mock_redis.get.return_value = json.dumps({"team": "MS", "schedule": "Night 22-06"}).encode()

        with patch.object(
            service,
            "_load_valid_schedules",
            return_value={"MS": ["Night 22-06"], "CBCS": ["Night 22-06"]},
        ):
            service.apply_patch("user@test.com", team="CBCS")

        pipe.set.assert_called_once()
        assert pipe.set.call_args.args[0] == _shift_key("user@test.com")
        assert json.loads(pipe.set.call_args.args[1]) == {"team": "CBCS", "schedule": "Night 22-06"}
        pipe.execute.assert_called_once()

    def test_rejects_unknown_team(self, service, mock_redis):
        mock_redis.get.return_value = None
        with patch.object(service, "_load_valid_schedules", return_value={"MS": ["Day 7-15"]}):
            with pytest.raises(ValueError, match="Invalid team"):
                service.apply_patch("user@test.com", team="NOPE")
        mock_redis.pipeline.assert_not_called()

    def test_rejects_schedule_not_in_team(self, service, mock_redis):
        mock_redis.get.return_value = None
        with patch.object(service, "_load_valid_schedules", return_value={"MS": ["Day 7-15"]}):
            with pytest.raises(ValueError, match="Invalid schedule"):
                service.apply_patch("user@test.com", team="MS", schedule="Night 22-06")
        mock_redis.pipeline.assert_not_called()

    def test_rejects_team_change_when_existing_schedule_not_valid(self, service, mock_redis):
        mock_redis.get.return_value = json.dumps({"team": "MS", "schedule": "Night 22-06"}).encode()
        with patch.object(
            service,
            "_load_valid_schedules",
            return_value={"MS": ["Night 22-06"], "CBCS": ["Day 7-15"]},
        ):
            with pytest.raises(ValueError, match="Invalid schedule"):
                service.apply_patch("user@test.com", team="CBCS")
        mock_redis.pipeline.assert_not_called()

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"status": ""},
            {"schedule": ""},
            {"team": []},
        ],
    )
    def test_invalid_input_raises_before_pipeline(self, service, mock_redis, kwargs):
        with pytest.raises(ValueError):
            service.apply_patch("user@test.com", **kwargs)
        mock_redis.pipeline.assert_not_called()

    def test_redis_error_wrapped(self, service, mock_redis):
        mock_redis.pipeline.return_value.execute.side_effect = RedisError("down")
        with pytest.raises(UserStatusWriteError):
            service.apply_patch("user@test.com", status="available")


class TestScanSimpleValues:
    """Tests for _scan_simple_values."""

    def test_reads_all_values_in_standalone_mode(self):
        service = UserStatusService(
            FakeBulkRedis(
                {
                    _status_key("alice"): b"available",
                    _status_key("bob"): b"busy",
                },
                cluster_mode=False,
            )
        )

        result = service._scan_simple_values(KEY_PREFIX)

        assert result == {
            "alice": "available",
            "bob": "busy",
        }


class TestConfiguredKeyPrefixes:
    """Tests for configurable Redis key prefixes."""

    def test_defaults_are_preserved_when_env_unset(self):
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.delenv("TSX_USER_STATUS_KEY_PREFIX", raising=False)
            monkeypatch.delenv("TSX_USER_STATUS_SHIFT_KEY_PREFIX", raising=False)
            importlib.reload(config_module)

            assert config_module.config.key_prefix == KEY_PREFIX
            assert config_module.config.shift_key_prefix == SHIFT_KEY_PREFIX
            assert _status_key("alice") == f"{KEY_PREFIX}:{{alice}}"
            assert _shift_key("alice") == f"{SHIFT_KEY_PREFIX}:{{alice}}"

        importlib.reload(config_module)

    def test_custom_env_vars_change_key_format(self, service, mock_redis):
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setenv("TSX_USER_STATUS_KEY_PREFIX", "custom:status")
            monkeypatch.setenv("TSX_USER_STATUS_SHIFT_KEY_PREFIX", "custom:shift")
            importlib.reload(config_module)

            assert config_module.config.key_prefix == "custom:status"
            assert config_module.config.shift_key_prefix == "custom:shift"
            assert _status_key("alice") == "custom:status:{alice}"
            assert _shift_key("alice") == "custom:shift:{alice}"

            with patch("howler.common.loader.datastore") as mock_ds:
                mock_ds.return_value.user.stream_search.return_value = iter([{"uname": "alice", "name": "Alice"}])
                mock_redis.scan_iter.side_effect = lambda pattern: iter(
                    [_status_key("alice").encode()] if pattern == "custom:status:*" else []
                )
                pipe = MagicMock()
                pipe.get.return_value = pipe
                pipe.execute.return_value = [b"available"]
                mock_redis.pipeline.return_value = pipe

                assert service.get_all_statuses() == [
                    {
                        "uname": "alice",
                        "name": "Alice",
                        "status": "available",
                        "schedule": None,
                        "team": None,
                        "tags": {"portfolio": [], "products": [], "primary_disciplines": []},
                    }
                ]
                assert mock_redis.scan_iter.call_args_list[0].args[0] == "custom:status:*"
                assert mock_redis.scan_iter.call_args_list[1].args[0] == "custom:shift:*"

        importlib.reload(config_module)


class TestGetAllStatuses:
    """Tests for get_all_statuses (includes schedule and team)."""

    @staticmethod
    def _mock_pipeline(mock_redis, values):
        pipe = MagicMock()
        pipe.get.return_value = pipe
        pipe.execute.return_value = values
        mock_redis.pipeline.return_value = pipe
        return pipe

    @patch("howler.common.loader.datastore")
    def test_returns_empty_when_no_users(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter([])
        assert service.get_all_statuses() == []

    @patch("howler.common.loader.datastore")
    def test_returns_all_users_with_status_and_shift(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter(
            [
                {
                    "uname": "alice",
                    "name": "Alice Smith",
                    "tags": {"portfolio": ["portfolio_a"]},
                },
                {"uname": "bob", "name": "Bob Jones"},
            ]
        )

        def scan_iter(pattern: str):
            if pattern.startswith(KEY_PREFIX):
                return iter([_status_key("alice").encode(), _status_key("bob").encode()])
            if pattern.startswith(SHIFT_KEY_PREFIX):
                return iter([_shift_key("alice").encode()])
            return iter([])

        mock_redis.scan_iter.side_effect = scan_iter
        pipe = MagicMock()
        pipe.get.return_value = pipe
        pipe.execute.side_effect = [
            [b"available", b"busy"],
            [json.dumps({"team": "MS", "schedule": "Day 7-15"}).encode()],
        ]
        mock_redis.pipeline.return_value = pipe

        result = service.get_all_statuses()
        by_name = {r["uname"]: r for r in result}
        assert mock_redis.pipeline.call_count == 2
        assert all(call.kwargs == {"transaction": False} for call in mock_redis.pipeline.call_args_list)
        assert pipe.get.call_count == 3
        mock_redis.mget.assert_not_called()
        assert by_name["alice"] == {
            "uname": "alice",
            "name": "Alice Smith",
            "status": "available",
            "schedule": "Day 7-15",
            "team": "MS",
            "tags": {"portfolio": ["portfolio_a"], "products": [], "primary_disciplines": []},
        }
        assert by_name["bob"] == {
            "uname": "bob",
            "name": "Bob Jones",
            "status": "busy",
            "schedule": None,
            "team": None,
            "tags": {"portfolio": [], "products": [], "primary_disciplines": []},
        }

    @patch("howler.common.loader.datastore")
    def test_corrupted_shift_payload_becomes_none(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter([{"uname": "alice", "name": "Alice"}])

        def scan_iter(pattern: str):
            if pattern.startswith(SHIFT_KEY_PREFIX):
                return iter([_shift_key("alice").encode()])
            return iter([])

        mock_redis.scan_iter.side_effect = scan_iter
        self._mock_pipeline(mock_redis, [b"not json"])

        result = service.get_all_statuses()
        assert result == [
            {
                "uname": "alice",
                "name": "Alice",
                "status": None,
                "schedule": None,
                "team": None,
                "tags": {"portfolio": [], "products": [], "primary_disciplines": []},
            }
        ]

    @patch("howler.common.loader.datastore")
    def test_uses_uname_as_name_fallback(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter([{"uname": "ghost"}])
        mock_redis.scan_iter.return_value = iter([])

        result = service.get_all_statuses()
        assert result == [
            {
                "uname": "ghost",
                "name": "ghost",
                "status": None,
                "schedule": None,
                "team": None,
                "tags": {"portfolio": [], "products": [], "primary_disciplines": []},
            }
        ]

    @patch("howler.common.loader.datastore")
    def test_raises_on_scan_redis_error(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter([{"uname": "alice", "name": "Alice"}])
        mock_redis.scan_iter.side_effect = RedisError("down")
        with pytest.raises(UserStatusReadError):
            service.get_all_statuses()

    @patch("howler.common.loader.datastore")
    def test_raises_on_mget_redis_error(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter([{"uname": "alice", "name": "Alice"}])
        mock_redis.scan_iter.return_value = iter([_status_key("alice").encode()])
        pipe = MagicMock()
        pipe.get.return_value = pipe
        pipe.execute.side_effect = RedisError("down")
        mock_redis.pipeline.return_value = pipe
        with pytest.raises(UserStatusReadError):
            service.get_all_statuses()

    @patch("howler.common.loader.datastore")
    def test_uses_non_transactional_pipeline_for_bulk_reads(self, mock_ds, service, mock_redis):
        mock_ds.return_value.user.stream_search.return_value = iter([{"uname": "alice", "name": "Alice"}])

        def scan_iter(pattern: str):
            if pattern.startswith(KEY_PREFIX):
                return iter([_status_key("alice").encode()])
            return iter([])

        mock_redis.scan_iter.side_effect = scan_iter
        pipe = self._mock_pipeline(mock_redis, [b"available"])

        result = service.get_all_statuses()

        assert result == [
            {
                "uname": "alice",
                "name": "Alice",
                "status": "available",
                "schedule": None,
                "team": None,
                "tags": {"portfolio": [], "products": [], "primary_disciplines": []},
            }
        ]
        mock_redis.pipeline.assert_called_once_with(transaction=False)
        pipe.get.assert_called_once_with(_status_key("alice").encode())
        mock_redis.mget.assert_not_called()

    @patch("howler.common.loader.datastore")
    def test_cluster_mode_reads_keys_across_slots(self, mock_ds):
        mock_ds.return_value.user.stream_search.return_value = iter(
            [
                {
                    "uname": "alice",
                    "name": "Alice Smith",
                    "tags": {"portfolio": ["portfolio_a"]},
                },
                {
                    "uname": "bob",
                    "name": "Bob Jones",
                    "tags": {"products": ["product_b"]},
                },
            ]
        )
        service = UserStatusService(
            FakeBulkRedis(
                {
                    _status_key("alice"): b"available",
                    _status_key("bob"): b"busy",
                    _shift_key("alice"): json.dumps({"team": "MS", "schedule": "Day 7-15"}).encode(),
                    _shift_key("bob"): json.dumps({"team": "CBCS", "schedule": "Night 22-06"}).encode(),
                },
                cluster_mode=True,
            )
        )

        result = service.get_all_statuses()

        by_name = {entry["uname"]: entry for entry in result}
        assert by_name["alice"] == {
            "uname": "alice",
            "name": "Alice Smith",
            "status": "available",
            "schedule": "Day 7-15",
            "team": "MS",
            "tags": {"portfolio": ["portfolio_a"], "products": [], "primary_disciplines": []},
        }
        assert by_name["bob"] == {
            "uname": "bob",
            "name": "Bob Jones",
            "status": "busy",
            "schedule": "Night 22-06",
            "team": "CBCS",
            "tags": {"portfolio": [], "products": ["product_b"], "primary_disciplines": []},
        }


class TestUserStatusEnum:
    """Tests for UserStatus enum."""

    def test_enum_contains_expected_values(self):
        expected = {"available", "busy", "unavailable", "away"}
        actual = {s.value for s in UserStatus}
        assert actual == expected

    def test_default_status_is_none(self):
        assert DEFAULT_STATUS is None
