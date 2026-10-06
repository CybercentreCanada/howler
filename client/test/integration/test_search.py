import json
from uuid import uuid4

from utils import create_hit_and_get_id


def test_hit(client):
    hit_id = create_hit_and_get_id(client)
    res = client.search.hit("howler.id:{}".format(hit_id))

    assert res["total"] == 1
    assert res["items"][0]["howler"]["id"] == hit_id

    res = client.search.hit("howler.id:*", offset=5)
    assert res["total"] > 1


def test_action(client):
    action = client.action.create(
        {
            "name": f"Client integration search action {uuid4()}",
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": f"search-{uuid4()}"}),
                }
            ],
        },
        refresh="wait_for",
    )

    result = client.search.action(f"action_id:{action['action_id']}", rows=1)

    assert result["total"] == 1
    assert result["items"][0]["action_id"] == action["action_id"]
