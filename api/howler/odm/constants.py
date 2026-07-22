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


class CaseEscalation(str, HowlerEnum):
    """Enum representing the escalation of a case in Howler.

    Args:
      NORMAL (str): Default escalation level.
      FOCUS (str): Elevated escalation level requiring extra attention.
      CRISIS (str): Highest escalation level requiring urgent response.
    """

    NORMAL = "normal"
    FOCUS = "focus"
    CRISIS = "crisis"
