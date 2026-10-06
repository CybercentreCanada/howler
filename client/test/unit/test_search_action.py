import json
from unittest.mock import MagicMock

from howler_client.module.search import Search


def test_action_search_posts_to_action_index():
    connection = MagicMock()
    search = Search(connection)

    search.action("action_id:example", filters="name:example", rows=10)

    path = connection.post.call_args.args[0]
    body = json.loads(connection.post.call_args.kwargs["data"])
    assert path == "api/v1/search/action"
    assert body["query"] == "action_id:example"
    assert body["filters"] == ["name:example"]
    assert body["rows"] == 10
