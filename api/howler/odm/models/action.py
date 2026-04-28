# mypy: ignore-errors
from typing import Optional

from howler import odm

VALID_TRIGGERS = ["create", "demote", "promote", "add_label", "remove_label"]


@odm.model(index=True, store=True, description="Model of action operations")
class Operation(odm.Model):
    operation_id: str = odm.Keyword(description="The ID of the action.")
    data_json: Optional[str] = odm.Keyword(
        optional=True,
        description="The data necessary to execute the action, in raw JSON format.",
    )


@odm.model(index=True, store=True, description="Model of actions")
class Action(odm.Model):
    action_id: str = odm.UUID(description="A UUID for this action")
    # TODO: AG : here as well same as the other ones. This is a highlight. Will try and ask more question on monday.
    owner_id: str = odm.List(
        odm.Keyword(), description="The id of the user that created this action", default=[], optional=True
    )

    member_id: list[str] = odm.List(
        odm.Keyword(),
        description="group of person to whom can modify this action.",
        default=[],
        optional=True,
    )
    admin_id: str = odm.List(
        odm.Keyword(),
        description="group of person to whom can administer this action.",
        default=[],
        optional=True,
    )
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
