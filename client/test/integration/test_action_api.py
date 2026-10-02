"""Integration tests for the action client module."""

import json
from uuid import uuid4

from utils import create_hit_and_get_id

from howler_client.client import Client


def test_create_list_get_and_execute_action(client: Client):
    """Actions created through the client can be listed, fetched, and executed."""
    action_name = f"Client integration action {uuid4()}"
    label = f"client-integration-{uuid4()}"
    hit_id = create_hit_and_get_id(client)
    action = client.action.create(
        {
            "name": action_name,
            "query": f"howler.id:{hit_id}",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": label}),
                }
            ],
        },
        refresh="wait_for",
    )

    fetched = client.action(action["action_id"])
    actions = client.action.list()
    reports = client.action.execute(action["action_id"], str(uuid4()))

    assert fetched["action_id"] == action["action_id"]
    assert fetched["name"] == action_name
    assert action["action_id"] in [item["action_id"] for item in actions]
    assert reports["add_label"][0]["outcome"] == "success"

    updated_hit = client.hit(hit_id)
    assert label in updated_hit["howler"]["labels"]["generic"]
