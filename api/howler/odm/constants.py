from howler.odm.howler_enum import HowlerEnum


class Status(str, HowlerEnum):
    """Enum representing the status of a record in howler.

    Args:
      OPEN (str): Record is open and unresolved.
      IN_PROGRESS (str): Record is currently being investigated.
      ON_HOLD (str): Record processing is on hold.
      RESOLVED (str): Record has been resolved.
    """

    OPEN = "open"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    RESOLVED = "resolved"

    def __str__(self) -> str:
        return self.value
