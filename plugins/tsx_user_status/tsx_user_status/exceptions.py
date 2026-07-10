"""Custom exceptions for the tsx_user_status plugin."""


class UserStatusError(Exception):
    """Base exception for user status errors."""


class UserStatusReadError(UserStatusError):
    """Exception raised for errors reading user status from Redis."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Status Read Error: {message}")


class UserStatusWriteError(UserStatusError):
    """Exception raised for errors writing user status to Redis."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Status Write Error: {message}")
