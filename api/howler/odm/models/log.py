from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.odm.howler_enum import HowlerEnum


class LogOperationType(str, HowlerEnum):
    APPENDED = "appended"
    REMOVED = "removed"
    SET = "set"


@odm.model(index=True, store=True, description="Log definition.")  # noqa: F821
class Log(odm.Model):
    timestamp = odm.Date(description="Timestamp at which the Log event took place.")
    key = odm.Optional(odm.Keyword(description="The key whose value changed."))
    explanation = odm.Optional(odm.Text(description="A manual description of the changes made."))
    previous_version = odm.Optional(odm.Keyword(description="The version this action was applied to."))
    new_value = odm.Optional(odm.Keyword(description="The value the key is changing to."))
    type = odm.Optional(odm.Enum(values=LogOperationType, description="The operation performed on the value."))
    previous_value = odm.Optional(odm.Keyword(description="The value the key is changing from."))
    user = odm.Keyword(description="User ID who created the log event.")

    def __init__(self, data: dict = None, *args, **kwargs):
        if "explanation" not in data:
            required_keys = {"key", "new_value", "type", "previous_value"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise HowlerValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )

        super().__init__(data, *args, **kwargs)
