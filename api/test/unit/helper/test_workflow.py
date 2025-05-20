import pytest

from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmUpdateOperation
from howler.helper.workflow import Transition, Workflow, WorkflowException

DUMMY_WORKFLOW_TRANSITIONS = [
    Transition({"transition": "first", "source": "state1", "dest": "state2", "actions": []}),
    Transition(
        {
            "transition": "second",
            "source": "state2",
            "dest": "state1",
            "actions": [lambda **kwargs: [OdmUpdateOperation(ESCollection.UPDATE_SET, "user", "random_user")]],
        }
    ),
]


def test_workflow():
    workflow: Workflow = Workflow("prop", DUMMY_WORKFLOW_TRANSITIONS)

    assert len(workflow.transitions) == 2

    # Run the "first" transition
    updates_first: list[OdmUpdateOperation] = workflow.transition("state1", "first")
    assert len(updates_first) == 1
    assert updates_first[0].key == "prop"
    assert updates_first[0].value == "state2"

    # Run the "second" transition
    updates_second: list[OdmUpdateOperation] = workflow.transition("state2", "second")
    assert len(updates_second) == 2
    assert updates_second[0].key == "user"
    assert updates_second[0].value == "random_user"
    assert updates_second[1].key == "prop"
    assert updates_second[1].value == "state1"


def test_workflow_missing_transition_props():
    with pytest.raises(WorkflowException):
        Workflow(
            "prop",
            [
                Transition(
                    {
                        "transition": "",
                        "source": "state1",
                        "dest": "state2",
                        "actions": [],
                    }
                )
            ],
        )

    with pytest.raises(WorkflowException):
        Workflow(
            "prop",
            [
                Transition(
                    {
                        "transition": "key1",
                        "source": "",
                        "dest": "state2",
                        "actions": [],
                    }
                )
            ],
        )

    with pytest.raises(WorkflowException):
        Workflow(
            "prop",
            [
                Transition(
                    {
                        "transition": "key1",
                        "source": "state1",
                        "dest": "",
                        "actions": [],
                    }
                )
            ],
        )

    with pytest.raises(WorkflowException):
        Workflow(
            "prop",
            [
                Transition(
                    {
                        "transition": "key1",
                        "source": "state1",
                        "dest": "state2",
                        "actions": "not a callable",
                    }
                )
            ],
        )


def test_workflow_duplicate_transition_keys():
    with pytest.raises(WorkflowException):
        Workflow(
            "prop",
            [
                Transition(
                    {
                        "transition": "key1",
                        "source": "state1",
                        "dest": "state2",
                        "actions": [],
                    }
                ),
                Transition(
                    {
                        "transition": "key1",
                        "source": "state1",
                        "dest": "state2",
                        "actions": [],
                    }
                ),
            ],
        )
