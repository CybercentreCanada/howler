import pytest

from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmUpdateOperation
from howler.helper.workflow import Transition, Workflow, WorkflowException

DUMMY_WORKFLOW_STATE_KEY = "prop"

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


@pytest.fixture(scope="module")
def workflow_with_state_setting_action():
    return Workflow(
        DUMMY_WORKFLOW_STATE_KEY,
        [
            *DUMMY_WORKFLOW_TRANSITIONS,
            Transition(
                {
                    "transition": "legal-set-state",
                    "source": "state1",
                    "dest": "state3",
                    "actions": [
                        lambda **kwargs: [
                            OdmUpdateOperation(ESCollection.UPDATE_SET, DUMMY_WORKFLOW_STATE_KEY, "state3")
                        ]
                    ],
                }
            ),
        ],
    )


@pytest.fixture(scope="module")
def workflow_with_invalid_set_state_action():
    return Workflow(
        DUMMY_WORKFLOW_STATE_KEY,
        [
            *DUMMY_WORKFLOW_TRANSITIONS,
            Transition(
                {
                    "transition": "illegal-set-state",
                    "source": "state1",
                    "dest": "state3",
                    "actions": [
                        lambda **kwargs: [
                            OdmUpdateOperation(ESCollection.UPDATE_REMOVE, DUMMY_WORKFLOW_STATE_KEY, "state2")
                        ]
                    ],
                }
            ),
        ],
    )


def test_workflow():
    workflow: Workflow = Workflow(DUMMY_WORKFLOW_STATE_KEY, DUMMY_WORKFLOW_TRANSITIONS)

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


def test_workflow_with_state_setting_action(workflow_with_state_setting_action):
    workflow: Workflow = workflow_with_state_setting_action

    assert len(workflow.transitions) == 3

    # Run the "legal-set-state" transition
    updates: list[OdmUpdateOperation] = workflow.transition("state1", "legal-set-state")
    assert len(updates) == 1
    assert updates[0].key == DUMMY_WORKFLOW_STATE_KEY
    assert updates[0].value == "state3"


def test_workflow_with_invalid_set_state_action(workflow_with_invalid_set_state_action):
    workflow: Workflow = workflow_with_invalid_set_state_action

    assert len(workflow.transitions) == 3

    # Run the "illegal-set-state" transition
    with pytest.raises(WorkflowException):
        workflow.transition("state1", "illegal-set-state")


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
