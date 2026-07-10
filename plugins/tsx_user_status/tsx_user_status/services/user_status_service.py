"""Service for managing user status, schedule, and team via Redis."""

import json
from typing import Any

from howler.common.logging import get_logger
from redis import Redis, RedisError

from tsx_user_status.constants import DEFAULT_STATUS, DEFAULT_TAGS, UserStatus
from tsx_user_status.exceptions import UserStatusReadError, UserStatusWriteError

logger = get_logger(__file__)

# Sentinel used to distinguish "field not provided" from "field set to None"
# in :meth:`UserStatusService.apply_patch`.
UNSET: Any = object()

# All recognized assignment status values.
_VALID_STATUSES: frozenset[str] = frozenset(member.value for member in UserStatus)


def _validate_status(status: str | int | None) -> str | None:
    """Validate and coerce a status value.

    Args:
        status: Status to validate. Integers are coerced to strings.
            ``None`` is allowed and means "clear".

    Returns:
        The validated status string, or ``None``.

    Raises:
        ValueError: If status is not a recognized status value.
    """
    if status is None:
        return None
    if isinstance(status, int):
        status = str(status)
    if not isinstance(status, str) or not status.strip():
        raise ValueError("Invalid status: must be a non-empty string, or null to clear.")
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}': not a recognized status value.")
    return status


def _validate_optional_text(field_name: str, value: str | int | None) -> str | None:
    """Validate a nullable text field.

    Args:
        field_name: Name of the field for error messages.
        value: Field value to validate.

    Returns:
        A cleaned string value, or ``None``.

    Raises:
        ValueError: If the value is not a non-empty string (when not null).
    """
    if value is None:
        return None
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {field_name}: must be a non-empty string, or null to clear.")
    return value


def _normalize_shift_payload(shift: dict[str, Any] | None) -> dict[str, str] | None:
    """Validate and normalize schedule/team payload.

    A legacy ``shift`` field is mapped to ``schedule`` for backward compatibility
    when reading old Redis values.

    Args:
        shift: Either ``None`` (clear) or a dict containing optional
            ``"schedule"`` and ``"team"`` fields.

    Returns:
        Normalized dict with optional ``"schedule"`` / ``"team"`` keys,
        or ``None``.

    Raises:
        ValueError: If the payload has the wrong shape or empty fields.
    """
    if shift is None:
        return None
    if not isinstance(shift, dict):
        raise ValueError("Invalid schedule/team payload: must be an object or null.")  # noqa: TRY004

    normalized = dict(shift)
    if "shift" in normalized and "schedule" not in normalized:
        normalized["schedule"] = normalized.pop("shift")

    allowed = {"schedule", "team"}
    unknown = set(normalized.keys()) - allowed
    if unknown:
        unknown_fields = ", ".join(sorted(unknown))
        raise ValueError(f"Invalid schedule/team payload: unsupported field(s): {unknown_fields}.")
    if not normalized:
        raise ValueError("Invalid schedule/team payload: provide at least one of 'schedule' or 'team'.")

    out: dict[str, str] = {}
    if "schedule" in normalized:
        schedule = _validate_optional_text("schedule", normalized["schedule"])
        if schedule is None:
            raise ValueError(
                "Invalid schedule/team payload: use null clearing via PATCH fields, not nested null values."
            )
        out["schedule"] = schedule
    if "team" in normalized:
        team = _validate_optional_text("team", normalized["team"])
        if team is None:
            raise ValueError(
                "Invalid schedule/team payload: use null clearing via PATCH fields, not nested null values."
            )
        out["team"] = team

    return out or None


def _status_key(user_id: str) -> str:
    """Build the status Redis key, hash-tagged on the user id."""
    from tsx_user_status.config import config as plugin_config

    return f"{plugin_config.key_prefix}:{{{user_id}}}"


def _shift_key(user_id: str) -> str:
    """Build the shift Redis key, hash-tagged on the user id."""
    from tsx_user_status.config import config as plugin_config

    return f"{plugin_config.shift_key_prefix}:{{{user_id}}}"


class UserStatusService:
    """Service for managing user status, schedule, and team using Redis."""

    def __init__(self, redis_client: Redis) -> None:
        """Initialize the UserStatusService.

        Args:
            redis_client: An instance of a Redis client.
        """
        self.redis = redis_client

    # ------------------------------------------------------------------ status

    def get_status(self, user_id: str) -> str | None:
        """Retrieve a user's status from Redis.

        Args:
            user_id: The user's unique identifier.

        Returns:
            The status string, or None if no key exists.

        Raises:
            UserStatusReadError: If Redis read fails.
        """
        try:
            value = self.redis.get(_status_key(user_id))
        except RedisError as e:
            logger.exception("Redis error reading status for user %s", user_id)
            raise UserStatusReadError(f"Failed to read status for user {user_id}: {str(e)}") from e

        if value is None:
            return DEFAULT_STATUS

        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    def set_status(self, user_id: str, status: str | int | None) -> None:
        """Set a user's status in Redis.

        Setting status to None deletes the key.

        Args:
            user_id: The user's unique identifier.
            status: The status to set. Must be a valid status string, or None to clear.

        Raises:
            ValueError: If the status is not valid.
            UserStatusWriteError: If Redis write fails.
        """
        status = _validate_status(status)
        try:
            if status is None:
                self.redis.delete(_status_key(user_id))
            else:
                self.redis.set(_status_key(user_id), status)
        except RedisError as e:
            logger.exception("Redis error writing status for user %s", user_id)
            raise UserStatusWriteError(f"Failed to write status for user {user_id}: {str(e)}") from e

    # ---------------------------------------------------------- schedule + team

    def get_shift(self, user_id: str) -> dict[str, str] | None:
        """Retrieve a user's schedule/team assignment from Redis.

        Args:
            user_id: The user's unique identifier.

        Returns:
            A dict with optional ``"schedule"`` and ``"team"`` keys,
            or ``None`` if not set.

        Raises:
            UserStatusReadError: If Redis read fails or the stored payload is corrupted.
        """
        try:
            value = self.redis.get(_shift_key(user_id))
        except RedisError as e:
            logger.exception("Redis error reading schedule/team for user %s", user_id)
            raise UserStatusReadError(f"Failed to read schedule/team for user {user_id}: {str(e)}") from e

        if value is None:
            return None

        raw = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.exception("Corrupted schedule/team payload for user %s", user_id)
            raise UserStatusReadError(f"Corrupted schedule/team payload for user {user_id}: {str(e)}") from e

        try:
            return _normalize_shift_payload(parsed)
        except ValueError as e:
            logger.exception("Invalid schedule/team payload schema for user %s", user_id)
            raise UserStatusReadError(f"Invalid schedule/team payload for user {user_id}: {str(e)}") from e

    def set_shift(self, user_id: str, shift: dict[str, str] | None) -> None:
        """Set a user's schedule/team assignment in Redis.

        Setting shift to None deletes the key.

        Args:
            user_id: The user's unique identifier.
            shift: ``{"schedule": str, "team": str}`` (partial allowed), or ``None`` to clear.

        Raises:
            ValueError: If the payload is malformed.
            UserStatusWriteError: If Redis write fails.
        """
        shift = _normalize_shift_payload(shift)
        try:
            if shift is None:
                self.redis.delete(_shift_key(user_id))
            else:
                self.redis.set(_shift_key(user_id), json.dumps(shift))
        except RedisError as e:
            logger.exception("Redis error writing schedule/team for user %s", user_id)
            raise UserStatusWriteError(f"Failed to write schedule/team for user {user_id}: {str(e)}") from e

    def _load_valid_schedules(self) -> dict[str, list[str]]:
        """Load valid team/schedule combinations from the shared schedule cache.

        Returns:
            Mapping of team name to allowed schedule names.

        Raises:
            UserStatusWriteError: If schedules cannot be loaded or are malformed.
        """
        try:
            from tsx_user_status.config import config as plugin_config
            from tsx_user_status.services.schedule_service import get_schedules

            schedules = get_schedules(plugin_config)
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load schedules for validation")
            raise UserStatusWriteError(f"Failed to load schedules for validation: {str(e)}") from e

        if not isinstance(schedules, dict):
            raise UserStatusWriteError("Failed to load schedules for validation: payload is not a dict")

        normalized: dict[str, list[str]] = {}
        for team, team_schedules in schedules.items():
            if not isinstance(team, str) or not team.strip():
                continue
            if not isinstance(team_schedules, list):
                continue
            normalized[team] = [s for s in team_schedules if isinstance(s, str) and s.strip()]
        return normalized

    def _validate_schedule_and_team(self, team: str | None, schedule: str | None) -> None:
        """Validate team and schedule values against the cached schedule map.

        Rules:
            - If ``team`` is set, it must exist in the schedule map.
            - If both ``team`` and ``schedule`` are set, ``schedule`` must exist
              within that team's allowed schedules.
            - If only ``schedule`` is set, it must exist in at least one team.

        Args:
            team: Final team value after merge, or ``None``.
            schedule: Final schedule value after merge, or ``None``.

        Raises:
            ValueError: If values are invalid against known schedules.
            UserStatusWriteError: If the schedule map cannot be loaded.
        """
        if team is None and schedule is None:
            return

        valid_schedules = self._load_valid_schedules()

        if team is not None and team not in valid_schedules:
            raise ValueError(f"Invalid team '{team}': unknown team.")

        if schedule is None:
            return

        if team is not None:
            if schedule not in valid_schedules.get(team, []):
                raise ValueError(f"Invalid schedule '{schedule}' for team '{team}'.")
            return

        if not any(schedule in schedules for schedules in valid_schedules.values()):
            raise ValueError(f"Invalid schedule '{schedule}': unknown schedule.")

    # ------------------------------------------------------------- patch combo

    def apply_patch(
        self,
        user_id: str,
        *,
        status: Any = UNSET,
        schedule: Any = UNSET,
        team: Any = UNSET,
    ) -> None:
        """Apply a partial update to a user's status/schedule/team atomically.

        Fields left as :data:`UNSET` are not touched. Fields set to ``None``
        are cleared. Both writes are issued inside a single Redis MULTI/EXEC
        transaction so a partial failure cannot leave the user in a
        half-cleared state.

        Args:
            user_id: The user's unique identifier.
            status: New status value, ``None`` to clear, or :data:`UNSET` to leave alone.
            schedule: New schedule value, ``None`` to clear, or :data:`UNSET`.
            team: New team value, ``None`` to clear, or :data:`UNSET`.

        Raises:
            ValueError: If any provided field is malformed.
            UserStatusWriteError: If the pipelined Redis write fails.
        """
        if status is UNSET and schedule is UNSET and team is UNSET:
            return

        validated_status = _validate_status(status) if status is not UNSET else UNSET
        validated_schedule = _validate_optional_text("schedule", schedule) if schedule is not UNSET else UNSET
        validated_team = _validate_optional_text("team", team) if team is not UNSET else UNSET

        shift_touched = validated_schedule is not UNSET or validated_team is not UNSET
        updated_shift = (
            self._compute_updated_shift(user_id, validated_schedule, validated_team) if shift_touched else None
        )

        if updated_shift is None:
            self._validate_schedule_and_team(team=None, schedule=None)
        elif shift_touched:
            self._validate_schedule_and_team(
                team=updated_shift.get("team"),
                schedule=updated_shift.get("schedule"),
            )

        self._write_patch(user_id, validated_status, shift_touched, updated_shift)

    def _compute_updated_shift(
        self,
        user_id: str,
        validated_schedule: Any,
        validated_team: Any,
    ) -> dict[str, str] | None:
        """Merge validated schedule/team values onto the user's current shift.

        Args:
            user_id: The user's unique identifier.
            validated_schedule: New schedule, ``None`` to clear, or :data:`UNSET`.
            validated_team: New team, ``None`` to clear, or :data:`UNSET`.

        Returns:
            The merged shift dict, or ``None`` if the result is empty.
        """
        updated_shift = dict(self.get_shift(user_id) or {})

        if validated_schedule is not UNSET:
            if validated_schedule is None:
                updated_shift.pop("schedule", None)
            else:
                updated_shift["schedule"] = validated_schedule

        if validated_team is not UNSET:
            if validated_team is None:
                updated_shift.pop("team", None)
            else:
                updated_shift["team"] = validated_team

        return updated_shift or None

    def _write_patch(
        self,
        user_id: str,
        validated_status: Any,
        shift_touched: bool,
        updated_shift: dict[str, str] | None,
    ) -> None:
        """Write the validated status/shift changes in a single Redis transaction.

        Args:
            user_id: The user's unique identifier.
            validated_status: New status, ``None`` to clear, or :data:`UNSET`.
            shift_touched: Whether the shift (schedule/team) should be written.
            updated_shift: The merged shift dict, or ``None`` to clear it.

        Raises:
            UserStatusWriteError: If the pipelined Redis write fails.
        """
        try:
            pipe = self.redis.pipeline(transaction=True)
            if validated_status is not UNSET:
                key = _status_key(user_id)
                if validated_status is None:
                    pipe.delete(key)
                else:
                    pipe.set(key, validated_status)
            if shift_touched:
                key = _shift_key(user_id)
                if updated_shift is None:
                    pipe.delete(key)
                else:
                    pipe.set(key, json.dumps(updated_shift))
            pipe.execute()
        except RedisError as e:
            logger.exception("Redis error applying patch for user %s", user_id)
            raise UserStatusWriteError(f"Failed to apply patch for user {user_id}: {str(e)}") from e

    # ------------------------------------------------------------------- bulk

    def get_all_statuses(self) -> list[dict[str, Any]]:
        """Retrieve all users with their status, schedule, team, and tags.

        Returns:
            A list of dicts with keys ``"uname"``, ``"name"``, ``"status"``,
            ``"schedule"``, ``"team"``, and ``"tags"`` for all active users.
            Users without an explicit value have ``None`` for that field
            (or empty tag lists for ``"tags"``).

        Raises:
            UserStatusReadError: If Redis read fails.
        """
        from howler.common.loader import datastore

        ds = datastore()
        all_users = ds.user.stream_search(
            "is_active:true", fl="uname,name,tags.portfolio,tags.products,tags.primary_disciplines", as_obj=False
        )

        user_map: dict[str, dict[str, Any]] = {}
        for user in all_users:
            uname = user.get("uname")
            if uname:
                user_map[uname] = user

        if not user_map:
            return []

        from tsx_user_status.config import config as plugin_config

        statuses = self._scan_simple_values(plugin_config.key_prefix)
        shifts_raw = self._scan_simple_values(plugin_config.shift_key_prefix)

        shifts: dict[str, dict[str, str] | None] = {}
        for uname, raw in shifts_raw.items():
            try:
                shifts[uname] = _normalize_shift_payload(json.loads(raw))
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Ignoring corrupted schedule/team payload for user %s", uname)
                shifts[uname] = None

        result: list[dict[str, Any]] = []
        for uname, user in user_map.items():
            result.append(
                {
                    "uname": uname,
                    "name": user.get("name", uname),
                    "status": statuses.get(uname),
                    "schedule": (shifts.get(uname) or {}).get("schedule"),
                    "team": (shifts.get(uname) or {}).get("team"),
                    "tags": {**DEFAULT_TAGS, **(user.get("tags") or {})},
                }
            )
        return result

    def _scan_simple_values(self, prefix: str) -> dict[str, str]:
        """Scan all keys matching ``{prefix}:*`` and return ``{uname: raw_value}``.

        Args:
            prefix: Redis key prefix (without trailing ``:``).

        Returns:
            Mapping of uname to its decoded raw value.

        Raises:
            UserStatusReadError: If scanning or fetching values fails.
        """
        try:
            keys = list(self.redis.scan_iter(f"{prefix}:*"))
        except RedisError as e:
            logger.exception("Redis error scanning keys with prefix %s", prefix)
            raise UserStatusReadError(f"Failed to scan keys for prefix {prefix}: {str(e)}") from e

        if not keys:
            return {}

        try:
            pipe = self.redis.pipeline(transaction=False)
            for key in keys:
                pipe.get(key)
            values = pipe.execute()
        except RedisError as e:
            logger.exception("Redis error reading bulk values for prefix %s", prefix)
            raise UserStatusReadError(f"Failed to read bulk values for prefix {prefix}: {str(e)}") from e

        prefix_len = len(f"{prefix}:")
        out: dict[str, str] = {}
        for key, value in zip(keys, values):
            if value is None:
                continue
            raw_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            uname = raw_key[prefix_len:].strip("{}")
            out[uname] = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        return out
