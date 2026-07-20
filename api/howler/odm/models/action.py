# mypy: ignore-errors
from typing import Optional

from howler import odm
from howler.odm.models.ownership import Ownership

VALID_TRIGGERS = ["create", "demote", "promote", "add_label", "remove_label"]


@odm.model(index=True, store=True, description="Model of action operations")
class Operation(odm.Model):
    operation_id: str = odm.Keyword(description="The ID of the action.")
    data_json: Optional[str] = odm.Keyword(
        optional=True,
        description="The data necessary to execute the action, in raw JSON format.",
    )


@odm.model(index=True, store=True, description="Model of actions")
class Action(Ownership):
    action_id: str = odm.UUID(description="A UUID for this action")
    name: str = odm.Keyword(description="The name of the action.")
    query: str = odm.Keyword(description="The query this action is run against.")
    triggers: list[str] = odm.List(
        odm.Enum(VALID_TRIGGERS),
        default=[],
        description="A list of events for which trigger this action",
    )
    operations: list[Operation] = odm.List(
        odm.Compound(Operation),
        default=[],
        description="A list of the operations this action consists of.",
    )

    def __init__(self, data: dict = None, *args, **kwargs):
        if "owner" not in data and "owner_id" in data:
            data["owner"] = data.pop("owner_id")

        super().__init__(data, *args, **kwargs)
