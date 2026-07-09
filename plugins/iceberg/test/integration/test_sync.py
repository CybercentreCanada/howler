from datetime import timedelta


def test_hit_diffs(test_client, current_time):
    start_time = current_time - timedelta(days=1)

    response = test_client.get(f"/api/v1/sync/hit_diffs?from_date={start_time.isoformat()}")

    assert response.status_code == 200
    hits = response.json.get("api_response")
    assert len(hits) == 10
