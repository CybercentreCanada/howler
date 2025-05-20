from typing import Callable, Optional, TypedDict, Union

from howler.common.exceptions import HowlerException
from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmUpdateOperation


class WorkflowException(HowlerException):
    "Exception for errors caused during processing of a workflow"


class Transition(TypedDict):
    """Typed Dict outlining the propertyies of a valid transition object"""

    source: Optional[Union[str, list[str]]]
    transition: str
    dest: Optional[str]
    actions: list[Callable[..., list[OdmUpdateOperation]]]


def validate_transition(transition: Transition):
    "Ensure the given transition is valid"
    return bool(
        transition
        # We want to check if a source is provided. If it is, it must have a value
        # If it isn't, we'll allow this transition from any status
        and ("source" not in transition or transition["source"] != "")
        and transition["transition"]
        # We want to check if a destination is provided. If it is, it must have a value
        # If it isn't, we won't change the status of the hit
        and ("dest" not in transition or transition["dest"] != "")
        and isinstance(transition["actions"], list)
        and all(callable(a) for a in transition["actions"])
    )


class Workflow:
    """A simple state-like machine that generates OdmUpdateOperations on a given transition

    NOTE: This does not keep track of state, it merely provides the update operations of a transition.
    """

    def __init__(self, status_prop: str, transitions: list[Transition]):
        self.status_prop = status_prop

        if any(not validate_transition(t) for t in transitions):
            raise WorkflowException("One or more transitions provided were invalid.")

        self.transitions = {}
        identifiers = []
        for t in transitions:
            if t.get("source", False) and isinstance(t["source"], list):
                for s in t["source"]:
                    self.transitions[f'{s}{t["transition"]}'] = t
                    identifiers.append(f'{s}{t["transition"]}{t.get("dest", None) or ""}')
            else:
                self.transitions[f'{t.get("source", "") or ""}{t["transition"]}'] = t
                identifiers.append(f'{t.get("source", "") or ""}{t["transition"]}{t.get("dest", "") or ""}')

        if len(set(identifiers)) != len(identifiers):
            raise WorkflowException("There are duplicate transitions (same source, transition and dest values).")

    def transition(self, current_status: str, transition: str, **kwargs) -> list[OdmUpdateOperation]:
        "Generate a list of ODM updates based on the current status and a given transition step"
        _transition: Optional[Transition] = self.transitions.get(
            f"{current_status}{transition}", self.transitions.get(transition, None)
        )
        if not _transition:
            raise WorkflowException(f"Current status '{current_status}' does not allow the '{transition}' transition.")

        # Check if we can actually perform this transition
        source = _transition.get("source")
        if source and (isinstance(source, list) and current_status not in source) and current_status != source:
            raise WorkflowException(f"Current status '{current_status}' does not allow the '{transition}' transition.")

        updates_dict: dict[str, OdmUpdateOperation] = {}

        for action in _transition.get("actions", []):
            for update in action(transition=_transition, **kwargs):
                # Check if an update already exists for this property and if it's value is different
                if updates_dict.get(update.key) and updates_dict[update.key].value != update.value:
                    raise WorkflowException(
                        f"Transition {transition} attempted to update the same property {update.key} with \
                            different values."
                    )

                updates_dict[update.key] = update

        if self.status_prop not in updates_dict and _transition.get("dest", False):
            updates_dict[self.status_prop] = OdmUpdateOperation(
                ESCollection.UPDATE_SET,
                self.status_prop,
                _transition.get("dest"),
            )

        self.current_status = _transition.get("dest", current_status)

        return list(updates_dict.values())

    def get_transitions(self, current_status: str):
        "Get a list of all given transitions"
        return list(
            set(
                [
                    t["transition"]
                    for t in self.transitions.values()
                    if (t["source"] and current_status in t["source"]) or not t["source"]
                ]
            )
        )
