import base64
from datetime import timedelta

import pytest

_TEST_TOKEN = f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"


@pytest.fixture(scope="module", autouse=True)
def setup_datastore_with_hits(datastore_with_hits):
    yield datastore_with_hits


def _request(client, from_date, to_date=None, deep_paging_id=None, offset=None, rows=None, timeout=None):
    url = "/api/v1/sync/hit_diffs"

    query_args = {"from_date": from_date}
    if to_date is not None:
        query_args["to_date"] = to_date

    if deep_paging_id is not None:
        query_args["deep_paging_id"] = deep_paging_id
    if offset is not None:
        query_args["offset"] = offset
    if rows is not None:
        query_args["rows"] = rows
    if timeout is not None:
        query_args["timeout"] = timeout

    return client.get(url, query_string=query_args, headers={"Authorization": _TEST_TOKEN})


def test_hit_diffs_with_start_interval(test_client, current_time):
    start_time = current_time - timedelta(days=1)

    response = _request(test_client, from_date=start_time.isoformat())

    assert response.status_code == 200
    hits = response.json.get("api_response")["items"]
    assert len(hits) == 10


def test_hit_diffs_with_start_and_end_interval(test_client, current_time):
    start_time = current_time - timedelta(days=3)
    end_time = current_time - timedelta(days=2, hours=1)

    response = _request(test_client, from_date=start_time.isoformat(), to_date=end_time.isoformat())

    assert response.status_code == 200
    hits = response.json.get("api_response")["items"]
    assert len(hits) == 5


def test_hit_diffs_with_no_start_interval(test_client):
    response = test_client.get("/api/v1/sync/hit_diffs")

    assert response.status_code == 400


def test_hit_diffs_pagination(test_client, current_time):
    start_time = current_time - timedelta(days=1)

    hit_id_set = set()

    # First request to get the first page of results
    response = _request(test_client, from_date=start_time.isoformat(), deep_paging_id="*", rows=5)

    assert response.status_code == 200
    res = response.json.get("api_response")
    assert len(res["items"]) == 5

    hit_id_set.update(item["howler"]["id"] for item in res["items"])

    # Second request to get the next page of results using the deep_paging_id from the first response
    deep_paging_id = res["next_deep_paging_id"]
    response = _request(test_client, from_date=start_time.isoformat(), deep_paging_id=deep_paging_id, offset=5, rows=5)

    assert response.status_code == 200
    res = response.json.get("api_response")
    assert len(res["items"]) == 5

    hit_id_set.update(item["howler"]["id"] for item in res["items"])
    assert len(hit_id_set) == 10


def test_hit_schema(test_client):
    response = test_client.get("/api/v1/sync/schema/hit")

    assert response.status_code == 200
    schema = response.json.get("api_response")
    assert "fields" in schema
    assert schema.get("type") == "struct"
    assert "howler" in (field.get("name") for field in schema["fields"])
