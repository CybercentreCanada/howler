from datetime import timedelta


def test_hit_diffs_with_start_interval(test_client, current_time):
    start_time = current_time - timedelta(days=1)

    response = test_client.get(f"/api/v1/sync/hit_diffs?from_date={start_time.isoformat()}")

    assert response.status_code == 200
    hits = response.json.get("api_response")
    assert len(hits) == 10


def test_hit_diffs_with_start_and_end_interval(test_client, current_time):
    start_time = current_time - timedelta(days=3)
    end_time = current_time - timedelta(days=2, hours=1)

    response = test_client.get(
        f"/api/v1/sync/hit_diffs?from_date={start_time.isoformat()}&to_date={end_time.isoformat()}"
    )

    assert response.status_code == 200
    hits = response.json.get("api_response")
    assert len(hits) == 5


def test_hit_diffs_with_no_start_interval(test_client):
    response = test_client.get("/api/v1/sync/hit_diffs")

    assert response.status_code == 400
